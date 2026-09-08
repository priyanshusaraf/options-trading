"""Bounded owner-scoped index of canonical persisted research datasets."""
from __future__ import annotations

import datetime as dt
import hashlib
from zoneinfo import ZoneInfo
from typing import Literal
from types import SimpleNamespace

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.api.principal import Principal, get_principal, owner_id_for
from app.backtest.dataset_store import DatasetManifest, DatasetSegment
from app.db.models import Project
from app.db.session import SessionLocal
from app.market_truth.identity import MarketTruthError, load_canonical_instrument
from app.market_data.dataset_authority import load_normalization_transform
from research.config import research_database_url
from research.data.canonical_dataset import FIELD_SETS, INTERVALS, decode_observation_index
from research.data.user_csv_import import (
    CsvColumnMapping,
    MAX_CSV_BYTES,
    UserCsvImportRefused,
    UserCsvSpec,
    inspect_user_csv,
    observed_at_for_import,
    prepare_user_csv,
    publish_user_csv,
)
from research.data.imported_sessions import ImportedSessionsRefused, MAX_BYTES as MAX_SESSION_BYTES, validate_sessions
from research.domain.base import init_research_db, make_engine, make_sessionmaker, research_database_exists
from research.domain.models import (
    ResearchDatasetManifestSegmentV2,
    ResearchDatasetManifestV2,
    ResearchDatasetSegmentV2,
)


router = APIRouter(prefix="/api/ir")
MAX_DATASET_SCAN = 500


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class DatasetIndexItem(_Closed):
    manifest_address: str
    instrument_address: str
    canonical_instrument_label: str
    instrument_display_name: str | None = None
    provider_selection_address: str | None = None
    asset_class: str
    contract_kind: str
    interval: str
    event_start: str
    event_end: str
    availability_end: str
    as_of: str
    bar_count: int
    fields: list[str]
    provider_evidence_state: Literal["VERIFIED_REFERENCES_PRESENT", "USER_CSV_SHAPE_VALIDATED"]
    market_truth_state: Literal["VERIFIED_REFERENCES_PRESENT", "RECONSTRUCTED_WITH_GAPS"]
    gaps: list[dict]
    backtest_eligibility: Literal["ELIGIBLE_Q03", "UNAVAILABLE"]
    refusal_code: str | None
    source_type: Literal["PROVIDER_AUTHORITY", "USER_SUPPLIED"]
    historical_source_availability: Literal["DECLARED", "NOT_SUPPLIED"]
    calendar_coverage: Literal["DECLARED", "NOT_ASSERTED"]
    rights_scope: Literal["PROVIDER_CONTRACT", "PERSONAL_RESEARCH_ONLY"]
    research_compatibility: Literal["PRIMARY_BACKTEST", "BENCHMARK_INPUT_ONLY", "UNAVAILABLE"]


class DatasetIndexResponse(_Closed):
    schema_version: Literal["strategy-os-canonical-dataset-index/1"] = Field(
        default="strategy-os-canonical-dataset-index/1", alias="schema")
    project_id: str
    items: list[DatasetIndexItem]
    next_cursor: str | None


class CsvColumns(_Closed):
    instrument: str | None = Field(default=None, min_length=1, max_length=128)
    date: str = Field(min_length=1, max_length=128)
    open: str = Field(min_length=1, max_length=128)
    high: str = Field(min_length=1, max_length=128)
    low: str = Field(min_length=1, max_length=128)
    close: str = Field(min_length=1, max_length=128)
    volume: str | None = Field(default=None, min_length=1, max_length=128)


class UserCsvDatasetSpec(_Closed):
    instrument: str = Field(min_length=1, max_length=128)
    source_label: str = Field(default="User CSV upload", min_length=1, max_length=128)
    venue_code: Literal["XNSE", "XBOM"]
    asset_class: Literal["INDEX", "EQUITY"]
    columns: CsvColumns
    date_format: Literal["%d %b %Y", "%Y-%m-%d"] = "%d %b %Y"
    date_timezone: Literal["Asia/Kolkata"] = "Asia/Kolkata"
    interval: Literal["day"] = "day"
    contract_kind: Literal["SPOT"] = "SPOT"
    currency: Literal["INR"] = "INR"

    def importer_spec(self) -> UserCsvSpec:
        return UserCsvSpec(
            **self.model_dump(exclude={"columns", "instrument"}),
            authority_namespace=f"user-csv:{self.venue_code}:{self.asset_class}:{self.instrument}",
            authority_version="1", provider_symbol=self.instrument,
            expected_instrument=self.instrument,
            columns=CsvColumnMapping(**self.columns.model_dump()),
        )


class CsvInspectionResponse(_Closed):
    schema_version: Literal["strategy-os-user-csv-inspection/1"] = Field(
        default="strategy-os-user-csv-inspection/1", alias="schema")
    source_type: Literal["USER_SUPPLIED"] = "USER_SUPPLIED"
    source_sha256: str
    byte_count: int
    row_count: int
    source_order: Literal["ASCENDING", "DESCENDING"]
    fields: list[str]
    interval: Literal["day"] = "day"
    event_start: str
    event_end: str
    historical_source_availability: Literal["NOT_SUPPLIED"] = "NOT_SUPPLIED"
    calendar_coverage: Literal["NOT_ASSERTED"] = "NOT_ASSERTED"
    rights_scope: Literal["PERSONAL_RESEARCH_ONLY"] = "PERSONAL_RESEARCH_ONLY"


class CsvImportResponse(CsvInspectionResponse):
    schema_version: Literal["strategy-os-user-csv-import/1"] = Field(
        default="strategy-os-user-csv-import/1", alias="schema")
    project_id: str
    manifest_address: str
    instrument_address: str
    imported_at: str
    ready_as_of: str


class CsvSessionMetadataRead(_Closed):
    state: Literal["USER_DECLARED_COMPLETE"] = "USER_DECLARED_COMPLETE"
    schema_version: Literal["user-declared-daily-sessions/1"] = Field(
        default="user-declared-daily-sessions/1", alias="schema")
    source: str
    row_count: int
    source_sha256: str
    byte_count: int


class CsvSessionInspectionResponse(CsvInspectionResponse):
    schema_version: Literal["strategy-os-user-csv-inspection/2"] = Field(
        default="strategy-os-user-csv-inspection/2", alias="schema")
    session_metadata: CsvSessionMetadataRead


class CsvSessionImportResponse(CsvImportResponse):
    schema_version: Literal["strategy-os-user-csv-import/2"] = Field(
        default="strategy-os-user-csv-import/2", alias="schema")
    session_metadata: CsvSessionMetadataRead


class ProviderHistoryRequest(_Closed):
    selection_address: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    start_date: str = Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
    end_date: str = Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
    interval: Literal["day"] = "day"

    @field_validator("start_date", "end_date")
    @classmethod
    def calendar_date(cls, value):
        dt.date.fromisoformat(value)
        return value


class ProviderHistoryResponse(_Closed):
    schema_version: Literal["strategy-os-provider-history-import/1"] = Field(
        default="strategy-os-provider-history-import/1", alias="schema")
    project_id: str
    selection_address: str
    requested_start: str
    requested_end: str
    returned_start: str
    returned_end: str
    request_count: int
    empty_request_count: int
    request_window_days: int
    application_bar_limit: int
    provider_retention: Literal["UNKNOWN"] = "UNKNOWN"
    reused: bool = False
    item: DatasetIndexItem


def _label(physical, address: str, declared: str | None = None) -> str:
    # No provider symbol is canonical.  This compact label uses only the verified
    # physical fact and an unambiguous fragment of its content address.
    prefix = f"{declared} · " if declared else ""
    return f"{prefix}{physical.venue_code} · {physical.asset_class} {physical.contract_kind} · {address[7:19]}"


def _classification(manifest, physical, interval: str) -> tuple[bool, str | None]:
    eligible = (
        manifest.mode == "RESEARCH"
        and _eligible_physical(physical)
        and interval != "UNAVAILABLE"
        and not manifest.gaps
        and tuple(manifest.fields) in FIELD_SETS
    )
    if eligible:
        return True, None
    if physical.asset_class == "INDEX":
        return False, "CANONICAL_INDEX_BENCHMARK_ONLY"
    return False, "CANONICAL_HISTORY_UNSUPPORTED"


def _eligible_physical(physical) -> bool:
    return (physical.asset_class, physical.contract_kind, physical.currency) == \
        ("EQUITY", "SPOT", "INR") and physical.venue_code in {"XNSE", "XBOM"}


def _research_compatibility(eligible: bool, asset_class: str) -> str:
    if eligible:
        return "PRIMARY_BACKTEST"
    return "BENCHMARK_INPUT_ONLY" if asset_class == "INDEX" else "UNAVAILABLE"


def _visible_in_project(row: ResearchDatasetManifestV2, project_id: str) -> bool:
    try:
        purpose = DatasetManifest.from_bytes(bytes(row.canonical_bytes)).purpose
    except (ValueError, TypeError, KeyError):
        return True
    prefix = "user-supplied-personal-research:"
    return not purpose.startswith(prefix) or purpose == prefix + project_id


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def _project(session, project_id: str, owner_id: str) -> None:
    if session.scalar(select(Project.project_id).where(
        Project.project_id == project_id, Project.owner_id == owner_id,
        Project.status == "active",
    )) is None:
        raise HTTPException(status_code=404, detail="project not found")


def _parse_spec(raw: str) -> UserCsvDatasetSpec:
    try:
        return UserCsvDatasetSpec.model_validate_json(raw)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail={
            "code": "CSV_MAPPING_INVALID", "message": "CSV import mapping is invalid",
        }) from exc


async def _read_csv(file: UploadFile) -> bytes:
    raw = await file.read(MAX_CSV_BYTES + 1)
    if len(raw) > MAX_CSV_BYTES:
        raise HTTPException(status_code=413, detail={
            "code": "CSV_SIZE_INVALID", "message": "CSV file exceeds 1 MiB",
        })
    return raw


async def _read_session_metadata(file: UploadFile | None) -> bytes | None:
    if file is None:
        return None
    raw = await file.read(MAX_SESSION_BYTES + 1)
    if len(raw) > MAX_SESSION_BYTES:
        raise HTTPException(status_code=413, detail={
            "code": "CSV_SESSION_METADATA_SIZE_INVALID", "message": "Session metadata exceeds 1 MiB",
        })
    return raw


def _session_metadata_response(raw, inspection, spec):
    if raw is None:
        return None
    labels = [dt.datetime.combine(bar.session_date, dt.time.min, ZoneInfo(spec.date_timezone))
              for bar in inspection.bars]
    document = validate_sessions(raw, labels=labels, timezone=spec.date_timezone)
    return CsvSessionMetadataRead(source=document["source"], row_count=len(document["rows"]),
        source_sha256=hashlib.sha256(raw).hexdigest(), byte_count=len(raw))


def _csv_response(inspection, session_metadata, *, imported=False, **fields):
    data = {**_inspection_response(inspection), **fields}
    if session_metadata is not None:
        model = CsvSessionImportResponse if imported else CsvSessionInspectionResponse
        return model(**data, session_metadata=session_metadata)
    model = CsvImportResponse if imported else CsvInspectionResponse
    return model(**data)


def _inspection_response(inspection) -> dict:
    return {
        "source_sha256": inspection.source_sha256,
        "byte_count": inspection.byte_count,
        "row_count": len(inspection.bars),
        "source_order": inspection.source_order,
        "fields": list(inspection.fields),
        "event_start": inspection.event_start.isoformat(),
        "event_end": inspection.event_end.isoformat(),
    }


def _csv_error(exc: UserCsvImportRefused | ImportedSessionsRefused) -> HTTPException:
    return HTTPException(status_code=422, detail={"code": exc.code, "message": str(exc)})


@router.post(
    "/projects/{project_id}/research-datasets/inspect-csv",
    response_model=CsvInspectionResponse | CsvSessionInspectionResponse,
)
async def inspect_research_csv(
    project_id: str,
    metadata: str = Form(..., min_length=2, max_length=8_192),
    file: UploadFile = File(...),
    session_metadata: UploadFile | None = File(default=None),
    principal: Principal = Depends(get_principal),
) -> CsvInspectionResponse | CsvSessionInspectionResponse:
    owner_id = owner_id_for(principal)
    with SessionLocal() as session:
        _project(session, project_id, owner_id)
    try:
        spec = _parse_spec(metadata).importer_spec()
        inspection = inspect_user_csv(await _read_csv(file), spec, observed_at=_now())
        sessions = _session_metadata_response(await _read_session_metadata(session_metadata), inspection, spec)
    except (UserCsvImportRefused, ImportedSessionsRefused) as exc:
        raise _csv_error(exc) from exc
    return _csv_response(inspection, sessions)


@router.post(
    "/projects/{project_id}/research-datasets/import-csv",
    response_model=CsvImportResponse | CsvSessionImportResponse,
)
async def import_research_csv(
    project_id: str,
    metadata: str = Form(..., min_length=2, max_length=8_192),
    file: UploadFile = File(...),
    session_metadata: UploadFile | None = File(default=None),
    principal: Principal = Depends(get_principal),
) -> CsvImportResponse | CsvSessionImportResponse:
    owner_id = owner_id_for(principal)
    with SessionLocal() as execution_session:
        _project(execution_session, project_id, owner_id)
    raw, spec = await _read_csv(file), _parse_spec(metadata).importer_spec()
    session_raw = await _read_session_metadata(session_metadata)
    try:
        inspection = inspect_user_csv(raw, spec, observed_at=_now())
        sessions = _session_metadata_response(session_raw, inspection, spec)
    except (UserCsvImportRefused, ImportedSessionsRefused) as exc:
        raise _csv_error(exc) from exc
    authority_url = research_database_url()
    engine = make_engine(authority_url)
    try:
        init_research_db(engine)
        ResearchSession = make_sessionmaker(engine)
        with SessionLocal.begin() as execution_session:
            _project(execution_session, project_id, owner_id)
            observed_at = observed_at_for_import(
                execution_session, owner_id=owner_id, project_id=project_id,
                raw=raw, spec=spec, proposed=_now(), session_metadata=session_raw)
            imported = prepare_user_csv(
                execution_session, owner_id=owner_id, project_id=project_id,
                raw=raw, spec=spec, observed_at=observed_at, session_metadata=session_raw)
        with SessionLocal() as execution_session, ResearchSession.begin() as research_session:
            _project(execution_session, project_id, owner_id)
            publish_user_csv(research_session, execution_session, imported)
    except (UserCsvImportRefused, ImportedSessionsRefused) as exc:
        raise _csv_error(exc) from exc
    finally:
        engine.dispose()
    inspection = inspect_user_csv(raw, spec, observed_at=imported.observed_at)
    return _csv_response(
        inspection, sessions, imported=True, project_id=project_id,
        manifest_address=imported.manifest.manifest_address,
        instrument_address=imported.instrument.address,
        imported_at=imported.observed_at.isoformat(),
        ready_as_of=imported.ready_as_of.isoformat(),
    )


def _provider_response(execution_session, research_session, fetched, result, *, reused=False):
    from research.data.canonical_dataset import MAX_ROWS, load_canonical_datasets
    from app.providers.zerodha_data_runtime import HISTORICAL_REQUEST_DAYS
    cutoff = dt.datetime.fromisoformat(_replay_cutoff(result.manifest))
    _, dataset = load_canonical_datasets(research_session, execution_session=execution_session,
        owner_id=fetched.owner_id, selections=[SimpleNamespace(
            manifest_address=result.manifest.manifest_address, as_of=cutoff)], now=cutoff)[0]
    row = research_session.get(ResearchDatasetManifestV2,
        (fetched.owner_id, result.manifest.manifest_address))
    item = _item(research_session, execution_session, row)
    if item.provider_selection_address != fetched.selection_address:
        raise ValueError("dataset selection does not match this request")
    binding = dataset.binding["historical_capture"]
    return ProviderHistoryResponse(project_id=fetched.project_id,
        selection_address=fetched.selection_address,
        requested_start=binding["requested_start"], requested_end=binding["requested_end"],
        returned_start=binding["returned_start"], returned_end=binding["returned_end"],
        request_count=binding["request_count"], empty_request_count=binding["empty_request_count"],
        request_window_days=HISTORICAL_REQUEST_DAYS["day"], application_bar_limit=MAX_ROWS,
        item=item, reused=reused)


def _provider_dataset_result(execution_session, research_session, prior, fetched):
    from app.market_truth.identity import persist_canonical_instrument
    from research.data.provider_history_bundle import publish_historical_bundle
    from research.domain.strategy_admissions import persist_verified_dataset_authority
    if prior is not None:
        manifest, segments = prior
        return persist_verified_dataset_authority(research_session, manifest=manifest, segments=segments,
            execution_session=execution_session, at_time=dt.datetime.fromisoformat(manifest.recorded_at))
    persist_canonical_instrument(execution_session, fetched.instrument)
    return publish_historical_bundle(execution_session, research_session, fetched)


def _publish_provider_dataset(principal, *, project_id, selection_address, start, end, fetched=None):
    from app.db.concurrency import begin_reservation
    from app.providers.data_connection_service import _active_identity
    from research.data.provider_history_publication import find_history_publication, retain_history_publication
    engine = None
    try:
        with SessionLocal() as execution_session:
            begin_reservation(execution_session, scope=f"provider-history:{owner_id_for(principal)}")
            owner_id, _, _ = _active_identity(execution_session, principal, lock=True)
            _project(execution_session, project_id, owner_id)
            prior = find_history_publication(execution_session, owner_id=owner_id,
                selection_address=selection_address, start=start, end=end)
            if prior is None and fetched is None:
                return None
            engine = make_engine(research_database_url())
            init_research_db(engine)
            with make_sessionmaker(engine)() as research_session:
                result = _provider_dataset_result(execution_session, research_session, prior, fetched)
                context = SimpleNamespace(owner_id=owner_id, project_id=project_id, selection_address=selection_address)
                response = _provider_response(execution_session, research_session, context, result, reused=prior is not None)
                if prior is None:
                    retain_history_publication(execution_session, result, project_id=project_id,
                        selection_address=selection_address, start=start, end=end)
                # The first commit includes the exact canonical output, so a
                # failed research commit can resume without another acquisition.
                execution_session.commit()
                research_session.commit()
                return response
    finally:
        if engine is not None:
            engine.dispose()


def _provider_import_error(exc):
    status = {"HISTORICAL_FETCH_GRANT_UNAVAILABLE": 409,
        "HISTORICAL_FETCH_ACCESS_CHANGED": 409,
        "HISTORICAL_FETCH_UNAVAILABLE": 503, "DATA_CONNECTION_UNAVAILABLE": 409,
        "DATA_REAUTH_REQUIRED": 409, "DATA_PROVIDER_BUSY": 503,
        "DATA_VAULT_UNAVAILABLE": 503}.get(exc.code, 422)
    return HTTPException(status_code=status, detail={"code": exc.code, "message": str(exc)})


@router.post("/projects/{project_id}/research-datasets/from-provider", response_model=ProviderHistoryResponse)
def import_provider_history(project_id: str, request: ProviderHistoryRequest,
                            principal: Principal = Depends(get_principal)):
    from research.data.provider_history_fetch import HistoricalFetchRefused, fetch_provider_history
    from research.data.historical_capture import HistoricalCaptureRefused
    from app.providers.connection_store import ConnectionNotFound, DataConnectionUnavailable
    owner_id = owner_id_for(principal)
    timezone = ZoneInfo("Asia/Kolkata")
    start = dt.datetime.combine(dt.date.fromisoformat(request.start_date), dt.time.min, timezone)
    end = dt.datetime.combine(dt.date.fromisoformat(request.end_date), dt.time(23, 59, 59), timezone)
    try:
        publication = dict(project_id=project_id, selection_address=request.selection_address, start=start, end=end)
        saved = _publish_provider_dataset(principal, **publication)
        if saved is not None:
            return saved
        fetched = fetch_provider_history(SessionLocal, principal, project_id=project_id,
            selection_address=request.selection_address, from_date=start, to_date=end)
        if (fetched.owner_id, fetched.project_id, fetched.selection_address) != (owner_id, project_id, request.selection_address):
            raise DataConnectionUnavailable("the acquisition does not match its request")
        return _publish_provider_dataset(principal, **publication, fetched=fetched)
    except (HistoricalFetchRefused, HistoricalCaptureRefused) as exc:
        raise _provider_import_error(exc) from None
    except (ConnectionNotFound, DataConnectionUnavailable):
        raise HTTPException(status_code=409, detail={"code": "HISTORICAL_FETCH_ACCESS_CHANGED",
            "message": "Data access changed before saving. Reconnect the provider and fetch the range again."}) from None
    except (ValueError, TypeError, KeyError):
        raise HTTPException(status_code=422, detail={"code": "HISTORICAL_DATASET_UNAVAILABLE",
            "message": "The retained history could not become a verified input. Check the instrument and date range, then fetch again."}) from None
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail={"code": "HISTORICAL_DATASET_SAVE_FAILED",
            "message": "The data could not be saved. Retry the request; incomplete research inputs are not published."}) from None


def _declared_instrument(execution_session, manifest, segments):
    if not manifest.purpose.startswith("user-supplied-personal-research:"):
        return None
    transform = load_normalization_transform(
        execution_session, segments[0].normalization_transform_addresses[0])
    return dict(transform.parameters).get("expected_instrument")


def _instrument_display_name(execution_session, manifest, physical, declared):
    """Use a declared CSV name or a verified historical alias, never an address."""
    if declared:
        symbol = declared
    elif manifest.provider_observation_addresses:
        from app.market_data.observations import load_provider_observation
        from app.market_truth.identity import load_provider_alias
        observation = load_provider_observation(execution_session, manifest.provider_observation_addresses[0])
        alias = load_provider_alias(execution_session, observation.mapping_address)
        if observation.owner_id != manifest.owner_id or alias.canonical_instrument_address != physical.address:
            raise MarketTruthError("instrument display source does not match the dataset")
        symbol = alias.provider_symbol
    else:
        return None
    return f"{symbol} · {physical.venue_code} · {physical.asset_class} {physical.contract_kind}"


def _item_authority(research_session, execution_session, row: ResearchDatasetManifestV2):
    try:
        manifest = DatasetManifest.from_bytes(bytes(row.canonical_bytes))
        if manifest.manifest_address != row.manifest_address or len(manifest.instrument_addresses) != 1:
            raise ValueError("manifest identity is not singular")
        links = research_session.scalars(select(ResearchDatasetManifestSegmentV2).where(
            ResearchDatasetManifestSegmentV2.owner_id == row.owner_id,
            ResearchDatasetManifestSegmentV2.manifest_address == row.manifest_address,
        ).order_by(ResearchDatasetManifestSegmentV2.ordinal)).all()
        if [link.segment_address for link in links] != list(manifest.segment_addresses):
            raise ValueError("manifest segment order does not reconstruct")
        segments = []
        resolutions = set()
        for link in links:
            stored = research_session.get(
                ResearchDatasetSegmentV2, (row.owner_id, link.segment_address))
            if stored is None:
                raise ValueError("dataset segment authority is absent")
            segment = DatasetSegment.from_bytes(bytes(stored.canonical_bytes))
            if segment.segment_address != link.segment_address:
                raise ValueError("dataset segment address does not reconstruct")
            segments.append(segment)
            index = decode_observation_index(bytes(stored.object_bytes))
            resolutions.add(int(index["resolution_seconds"]))
        physical = load_canonical_instrument(execution_session, manifest.instrument_addresses[0])
        declared = _declared_instrument(execution_session, manifest, segments)
        display_name = _instrument_display_name(execution_session, manifest, physical, declared)
    except (ValueError, TypeError, KeyError, MarketTruthError) as exc:
        raise HTTPException(status_code=409, detail={
            "code": "CANONICAL_DATASET_AUTHORITY_CORRUPT",
            "message": "Stored canonical dataset authority failed verification",
        }) from exc

    return manifest, segments, resolutions, physical, declared, display_name


def _source_description(imported, historical=False):
    if imported:
        return {
            "provider_evidence_state": "USER_CSV_SHAPE_VALIDATED",
            "market_truth_state": "RECONSTRUCTED_WITH_GAPS",
            "source_type": "USER_SUPPLIED",
            "historical_source_availability": "NOT_SUPPLIED",
            "calendar_coverage": "NOT_ASSERTED",
            "rights_scope": "PERSONAL_RESEARCH_ONLY",
        }
    return {
        "provider_evidence_state": "VERIFIED_REFERENCES_PRESENT",
        "market_truth_state": "VERIFIED_REFERENCES_PRESENT",
        "source_type": "PROVIDER_AUTHORITY",
        "historical_source_availability": "NOT_SUPPLIED" if historical else "DECLARED",
        "calendar_coverage": "NOT_ASSERTED" if historical else "DECLARED",
        "rights_scope": "PROVIDER_CONTRACT",
    }


def _replay_cutoff(manifest):
    from research.data.historical_capture import PURPOSE as HISTORICAL_PURPOSE
    from research.data.provider_capture import PURPOSE as CURRENT_PURPOSE
    cutoff = max(manifest.recorded_at, manifest.availability_end)
    if not manifest.purpose.startswith((HISTORICAL_PURPOSE, CURRENT_PURPOSE)):
        return cutoff
    instant = dt.datetime.fromisoformat(cutoff)
    # User replay cutoffs use whole seconds; receipt facts retain their precision.
    if instant.microsecond:
        instant = instant.replace(microsecond=0) + dt.timedelta(seconds=1)
    return instant.isoformat()


def _provider_index_selection(execution_session, manifest):
    from research.data.provider_history_bundle import provider_selection_for_manifest
    try:
        return provider_selection_for_manifest(execution_session, manifest)
    except (ValueError, TypeError, LookupError):
        raise HTTPException(status_code=409, detail={"code": "CANONICAL_DATASET_AUTHORITY_CORRUPT",
            "message": "Stored instrument evidence could not be verified. Choose another saved dataset or fetch the range again."}) from None


def _item(research_session, execution_session, row: ResearchDatasetManifestV2) -> DatasetIndexItem:
    manifest, segments, resolutions, physical, declared, display_name = _item_authority(
        research_session, execution_session, row)
    resolution = resolutions.pop() if len(resolutions) == 1 else 0
    interval = INTERVALS.get(resolution, "UNAVAILABLE")
    imported = manifest.purpose.startswith("user-supplied-personal-research:")
    from research.data.historical_capture import PURPOSE as HISTORICAL_PURPOSE
    historical = manifest.purpose.startswith(HISTORICAL_PURPOSE)
    selection_address = _provider_index_selection(execution_session, manifest) if historical else None
    source_description = _source_description(imported, historical)
    if selection_address is not None:
        source_description["market_truth_state"] = "RECONSTRUCTED_WITH_GAPS"
    eligible, refusal_code = _classification(manifest, physical, interval)
    as_of = _replay_cutoff(manifest)
    return DatasetIndexItem(
        manifest_address=manifest.manifest_address,
        instrument_address=manifest.instrument_addresses[0],
        canonical_instrument_label=_label(physical, manifest.instrument_addresses[0], declared),
        instrument_display_name=display_name,
        provider_selection_address=selection_address,
        asset_class=physical.asset_class,
        contract_kind=physical.contract_kind,
        interval=interval,
        event_start=manifest.event_start,
        event_end=manifest.event_end,
        availability_end=manifest.availability_end,
        as_of=as_of,
        bar_count=sum(segment.row_end - segment.row_start for segment in segments),
        fields=list(manifest.fields),
        gaps=[dict(gap) for gap in manifest.gaps],
        backtest_eligibility="ELIGIBLE_Q03" if eligible else "UNAVAILABLE",
        refusal_code=refusal_code,
        **source_description,
        research_compatibility=_research_compatibility(eligible, physical.asset_class),
    )


@router.get("/projects/{project_id}/research-datasets", response_model=DatasetIndexResponse)
def get_research_datasets(
    project_id: str,
    limit: int = Query(default=25, ge=1, le=50),
    after: str | None = Query(default=None, pattern=r"^sha256:[0-9a-f]{64}$"),
    principal: Principal = Depends(get_principal),
) -> DatasetIndexResponse:
    owner_id = owner_id_for(principal)
    with SessionLocal() as execution_session:
        if execution_session.scalar(select(Project.project_id).where(
            Project.project_id == project_id, Project.owner_id == owner_id,
            Project.status == "active",
        )) is None:
            raise HTTPException(status_code=404, detail="project not found")
        authority = research_database_url()
        if not research_database_exists(authority):
            return DatasetIndexResponse(project_id=project_id, items=[], next_cursor=None)
        engine = make_engine(authority)
        try:
            init_research_db(engine)
            with make_sessionmaker(engine)() as research_session:
                query = select(ResearchDatasetManifestV2).where(
                    ResearchDatasetManifestV2.owner_id == owner_id,
                ).order_by(ResearchDatasetManifestV2.manifest_address).limit(MAX_DATASET_SCAN)
                if after is not None:
                    query = query.where(ResearchDatasetManifestV2.manifest_address > after)
                scanned = research_session.scalars(query).all()
                rows = [row for row in scanned if _visible_in_project(row, project_id)]
                items = [_item(research_session, execution_session, row) for row in rows[:limit]]
                next_cursor = None
                if len(rows) > limit:
                    next_cursor = rows[limit - 1].manifest_address
                elif len(scanned) == MAX_DATASET_SCAN:
                    next_cursor = scanned[-1].manifest_address
                return DatasetIndexResponse(
                    project_id=project_id,
                    items=items,
                    next_cursor=next_cursor,
                )
        finally:
            engine.dispose()


__all__ = ["get_research_datasets", "router"]
