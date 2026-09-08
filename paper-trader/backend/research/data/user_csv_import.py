"""Bounded user CSV ingestion into the existing canonical research authority."""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import io
from dataclasses import dataclass
from itertools import islice
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.backtest.dataset_store import DatasetManifest, DatasetSegment, dataset_byte_digest
from app.ir.hashing import canonical_json, content_address
from app.ir.validity import valid
from app.market_data import dataset_authority as authority
from app.market_data.authority import persist_capability_profile, persist_provider_conformance
from app.market_data.capability import CapabilityProfile, ProviderConformance
from app.market_data.numeric import NumericIngressError, market_float
from app.market_data.observations import (
    NormalizedMarketObservation,
    ProviderObservation,
    RawObservationSegment,
    persist_normalized_observation,
    persist_provider_observation,
    persist_raw_segment,
    load_raw_segment,
    retain_observation_dependencies,
)
from app.market_truth.authority import persist_market_truth_snapshot
from app.market_truth.identity import (
    CanonicalPhysicalInstrument,
    ProviderContract,
    ProviderEntity,
    ProviderInstrumentAlias,
    ProviderProduct,
    Quality,
    Reconstruction,
    persist_canonical_instrument,
    persist_provider_alias,
    persist_provider_identity,
)
from app.market_truth.rulebook import MarketTruthSnapshot
from app.market_truth.temporal import to_sql_utc_naive
from research.data.canonical_dataset import CODEC_V2, encode_observation_index
from research.domain.strategy_admissions import persist_verified_dataset_authority


MAX_CSV_BYTES = 1 * 1024 * 1024
MAX_CSV_ROWS = 2_000
UTC = dt.timezone.utc
DATE_TIMEZONE = ZoneInfo("Asia/Kolkata")
PRICE_FIELDS = ("OPEN", "HIGH", "LOW", "CLOSE")


class UserCsvImportRefused(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def _refuse(code: str, message: str):
    raise UserCsvImportRefused(code, message)


@dataclass(frozen=True)
class CsvColumnMapping:
    instrument: str | None
    date: str
    open: str
    high: str
    low: str
    close: str
    volume: str | None = None

    @property
    def fields(self) -> tuple[str, ...]:
        return PRICE_FIELDS + (("VOLUME",) if self.volume else ())

    def source_column(self, field: str) -> str:
        return getattr(self, field.lower())


@dataclass(frozen=True)
class UserCsvSpec:
    source_label: str
    authority_namespace: str
    authority_version: str
    provider_symbol: str
    expected_instrument: str
    venue_code: str
    asset_class: str
    columns: CsvColumnMapping
    date_format: str = "%d %b %Y"
    date_timezone: str = "Asia/Kolkata"
    interval: str = "day"
    contract_kind: str = "SPOT"
    currency: str = "INR"


@dataclass(frozen=True)
class CsvBar:
    session_date: dt.date
    open: float
    high: float
    low: float
    close: float
    volume: float | None


@dataclass(frozen=True)
class CsvInspection:
    source_sha256: str
    byte_count: int
    source_order: str
    fields: tuple[str, ...]
    bars: tuple[CsvBar, ...]

    @property
    def event_start(self) -> dt.datetime:
        return _event_time(self.bars[0].session_date)

    @property
    def event_end(self) -> dt.datetime:
        return _completed_at(self.bars[-1].session_date)


@dataclass(frozen=True)
class ImportedDataset:
    manifest: DatasetManifest
    instrument: CanonicalPhysicalInstrument
    observed_at: dt.datetime
    segments: dict

    @property
    def ready_as_of(self) -> dt.datetime:
        return self.observed_at + dt.timedelta(seconds=1)


def _event_time(value: dt.date) -> dt.datetime:
    return dt.datetime.combine(value, dt.time.min, DATE_TIMEZONE).astimezone(UTC)


def _completed_at(value: dt.date) -> dt.datetime:
    return _event_time(value) + dt.timedelta(days=1)


def _validate_identity_spec(spec: UserCsvSpec) -> None:
    text_values = (spec.source_label, spec.authority_namespace, spec.authority_version,
                   spec.provider_symbol, spec.expected_instrument)
    if any(not isinstance(value, str) or not value.strip() or len(value) > 128
           for value in text_values):
        _refuse("CSV_MAPPING_INVALID", "Dataset identity mapping is incomplete")
    identity = spec.venue_code, spec.asset_class, spec.contract_kind, spec.currency
    if identity not in {("XNSE", asset, "SPOT", "INR") for asset in ("INDEX", "EQUITY")} \
            | {("XBOM", asset, "SPOT", "INR") for asset in ("INDEX", "EQUITY")}:
        _refuse("CSV_MAPPING_UNSUPPORTED", "Only declared Indian daily spot mappings are supported")
    if (spec.interval, spec.date_timezone, spec.date_format) not in {
        ("day", "Asia/Kolkata", "%d %b %Y"),
        ("day", "Asia/Kolkata", "%Y-%m-%d"),
    }:
        _refuse("CSV_MAPPING_UNSUPPORTED", "Only declared Indian daily spot mappings are supported")


def _validate_columns(spec: UserCsvSpec) -> None:
    columns = [spec.columns.date,
               *(spec.columns.source_column(field) for field in spec.columns.fields)]
    if spec.columns.instrument is not None:
        columns.append(spec.columns.instrument)
    if any(not isinstance(value, str) or not value or len(value) > 128 for value in columns):
        _refuse("CSV_MAPPING_INVALID", "CSV column mapping is incomplete")
    if len(columns) != len(set(columns)):
        _refuse("CSV_MAPPING_INVALID", "CSV columns must map to distinct fields")


def _validate_spec(spec: UserCsvSpec) -> None:
    _validate_identity_spec(spec)
    _validate_columns(spec)


def _number(value: object, *, field: str, row: int) -> float:
    try:
        result = market_float(value, field=f"CSV row {row} {field.lower()}")
    except NumericIngressError:
        _refuse("CSV_VALUE_INVALID", f"Row {row} has an invalid {field.lower()} value")
    if result < 0 if field == "VOLUME" else result <= 0:
        _refuse("CSV_VALUE_INVALID", f"Row {row} has an invalid {field.lower()} value")
    return result


def _parse_bar(row: dict[str, str], spec: UserCsvSpec, row_number: int) -> CsvBar:
    if (spec.columns.instrument is not None
            and row[spec.columns.instrument].strip() != spec.expected_instrument):
        _refuse("CSV_INSTRUMENT_MISMATCH", f"Row {row_number} does not match the declared instrument")
    raw_date = row[spec.columns.date].strip()
    try:
        session_date = dt.datetime.strptime(raw_date, spec.date_format).date()
    except ValueError:
        _refuse("CSV_DATE_INVALID", f"Row {row_number} has an invalid date")
    values = {
        field: _number(row[spec.columns.source_column(field)].strip(),
                       field=field, row=row_number)
        for field in spec.columns.fields
    }
    if not values["LOW"] <= min(values["OPEN"], values["CLOSE"]) \
            <= max(values["OPEN"], values["CLOSE"]) <= values["HIGH"]:
        _refuse("CSV_OHLC_INVALID", f"Row {row_number} has an invalid OHLC envelope")
    return CsvBar(session_date, *(values[field] for field in PRICE_FIELDS), values.get("VOLUME"))


def _csv_rows(raw: bytes, spec: UserCsvSpec) -> list[dict[str, str]]:
    try:
        text = raw.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
        if not _valid_headers(reader.fieldnames, spec):
            _refuse("CSV_HEADER_MISMATCH", "CSV headers do not exactly match the declared columns")
        rows = list(islice(reader, MAX_CSV_ROWS + 1))
    except (UnicodeError, csv.Error):
        _refuse("CSV_MALFORMED", "CSV file is not valid UTF-8 CSV")
    if not 0 < len(rows) <= MAX_CSV_ROWS:
        _refuse("CSV_ROW_COUNT_INVALID", "CSV must contain 1 to 2000 complete rows")
    if any(None in row or None in row.values() for row in rows):
        _refuse("CSV_ROW_COUNT_INVALID", "CSV must contain 1 to 2000 complete rows")
    return rows


def _expected_columns(spec: UserCsvSpec) -> set[str]:
    expected = {spec.columns.date,
                *(spec.columns.source_column(field) for field in spec.columns.fields)}
    if spec.columns.instrument is not None:
        expected.add(spec.columns.instrument)
    return expected


def _valid_headers(headers, spec: UserCsvSpec) -> bool:
    return (headers is not None and len(headers) == len(set(headers))
            and set(headers) == _expected_columns(spec))


def _ordered(bars: tuple[CsvBar, ...]) -> tuple[tuple[CsvBar, ...], str]:
    dates = [bar.session_date for bar in bars]
    if len(dates) == 1:
        return bars, "ASCENDING"
    if len(set(dates)) != len(dates):
        _refuse("CSV_DUPLICATE_DATE", "CSV contains a duplicate date")
    ascending = dates == sorted(dates)
    descending = dates == sorted(dates, reverse=True)
    if len(dates) > 1 and not (ascending or descending):
        _refuse("CSV_DATE_ORDER_INVALID", "CSV dates must be strictly ascending or descending")
    return (tuple(reversed(bars)) if descending else bars,
            "DESCENDING" if descending else "ASCENDING")


def _ordered_bars(rows: list[dict[str, str]], spec: UserCsvSpec, observed_at: dt.datetime):
    bars, order = _ordered(tuple(
        _parse_bar(row, spec, index) for index, row in enumerate(rows, start=2)))
    if _completed_at(bars[-1].session_date) > observed_at:
        _refuse("CSV_FUTURE_BAR", "CSV contains a daily bar that was not complete at import time")
    return bars, order


def inspect_user_csv(raw: bytes, spec: UserCsvSpec, *, observed_at: dt.datetime) -> CsvInspection:
    _validate_spec(spec)
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_CSV_BYTES:
        _refuse("CSV_SIZE_INVALID", "CSV file is empty or exceeds 1 MiB")
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        _refuse("CSV_OBSERVED_AT_INVALID", "Import time must be timezone-aware")
    observed_at = observed_at.astimezone(UTC).replace(microsecond=0)
    bars, source_order = _ordered_bars(_csv_rows(raw, spec), spec, observed_at)
    return CsvInspection(hashlib.sha256(raw).hexdigest(), len(raw), source_order,
                         spec.columns.fields, bars)


def _instrument(spec: UserCsvSpec) -> CanonicalPhysicalInstrument:
    return CanonicalPhysicalInstrument(
        spec.authority_namespace, spec.authority_version, spec.venue_code,
        spec.asset_class, spec.contract_kind, spec.currency, None)


def _product(entity: ProviderEntity, instrument: CanonicalPhysicalInstrument,
             spec: UserCsvSpec, project_id: str) -> ProviderProduct:
    identity = content_address({
        "schema": "user-csv-import-identity/1", "project_id": project_id,
        "instrument": instrument.address, "source_label": spec.source_label,
        "provider_symbol": spec.provider_symbol,
        "expected_instrument": spec.expected_instrument,
        "date_format": spec.date_format, "date_timezone": spec.date_timezone,
        "interval": spec.interval, "columns": {
            field: getattr(spec.columns, field)
            for field in ("instrument", "date", "open", "high", "low", "close", "volume")},
    })[7:23]
    instrument_namespace = instrument.address[7:23]
    return ProviderProduct(
        entity.address, f"daily-csv:{instrument_namespace}:{identity}",
        f"user-csv:{instrument_namespace}:{identity}", identity)


def _session_retry_time(session, source, metadata):
    if metadata is None:
        return source.recorded_at
    from app.db.models import AuthorityRawSegment
    from research.data.imported_sessions import SCHEMA
    rows = session.scalars(select(AuthorityRawSegment).where(
        AuthorityRawSegment.owner_id == source.owner_id,
        AuthorityRawSegment.product_address == source.product_address,
        AuthorityRawSegment.contract_address == source.contract_address,
        AuthorityRawSegment.byte_digest == hashlib.sha256(metadata).hexdigest(),
        AuthorityRawSegment.byte_length == len(metadata),
    )).all()
    for row in rows:
        stored = load_raw_segment(session, row.address)
        if (stored.raw_schema == SCHEMA and stored.payload == metadata
                and stored.recorded_at == source.recorded_at):
            return source.recorded_at
    _refuse("CSV_SESSION_METADATA_RETRY_MISMATCH",
        "This CSV was imported with different or absent session metadata. "
        "Import both files together initially, or use a separate project.")


def observed_at_for_import(execution_session, *, owner_id: str, project_id: str,
                           raw: bytes, spec: UserCsvSpec,
                           proposed: dt.datetime, session_metadata: bytes | None = None) -> dt.datetime:
    """Reuse the first real observation time for an exact-byte retry."""
    from app.db.models import AuthorityRawSegment

    digest = hashlib.sha256(raw).hexdigest()
    entity = ProviderEntity("strategy-os", "USER_CSV", "User-supplied file")
    product = _product(entity, _instrument(spec), spec, project_id)
    candidates = execution_session.scalars(select(AuthorityRawSegment).where(
        AuthorityRawSegment.owner_id == owner_id,
        AuthorityRawSegment.product_address == product.address,
        AuthorityRawSegment.byte_digest == digest,
        AuthorityRawSegment.byte_length == len(raw),
    )).all()
    for row in candidates:
        if bytes(row.raw_bytes) == raw:
            segment = load_raw_segment(execution_session, row.address)
            if segment.raw_schema == "user-csv-daily/1":
                return _session_retry_time(execution_session, segment, session_metadata)
    return proposed.astimezone(UTC).replace(microsecond=0)


def _coverage(field: str, inspection: CsvInspection, lag: int) -> dict:
    return {
        "instrument": {"role": "primary", "type": "PHYSICAL"},
        "field": field, "resolution_seconds": 86_400,
        "history": {"from": inspection.event_start, "to": inspection.event_end,
                    "bars": len(inspection.bars)},
        "maximum_freshness_seconds": lag,
        "depth": {"kind": "NONE", "levels": None}, "session": "ALL_RECORDED",
        "alignment": {"kind": "EXACT", "maximum_skew_seconds": 0},
        "derived_local": False, "entitlement": "VERIFIED",
    }


def _offer(field: str, inspection: CsvInspection, lag: int) -> dict:
    return {
        "instrument": {"role": "primary", "type": "PHYSICAL"},
        "field": field, "timeframes": [86_400],
        "maximum_history_bars": len(inspection.bars),
        "available_from": inspection.event_start, "available_to": inspection.event_end,
        "maximum_freshness_seconds": lag,
        "depth": {"kind": "NONE", "levels": None}, "session": "ALL_RECORDED",
        "alignment": {"kind": "EXACT", "maximum_skew_seconds": 0},
        "derived_local": False, "entitled": True, "known": True,
    }


def _mapping_parameters(spec: UserCsvSpec, fields: tuple[str, ...]):
    parameters = [
        (f"column_{field.lower()}", spec.columns.source_column(field))
        for field in fields
    ] + [
        ("column_date", spec.columns.date), ("date_format", spec.date_format),
        ("date_timezone", spec.date_timezone),
        ("expected_instrument", spec.expected_instrument),
        ("source_label", spec.source_label),
    ]
    if spec.columns.instrument is not None:
        parameters.append(("column_instrument", spec.columns.instrument))
    return tuple(sorted(parameters))


def _refuse_revised_import(execution_session, raw_segment, inspection):
    from app.db.models import AuthorityProviderObservation

    dates = tuple(to_sql_utc_naive(_event_time(bar.session_date), "event_time")
                  for bar in inspection.bars)
    existing = execution_session.scalar(select(AuthorityProviderObservation.address).where(
        AuthorityProviderObservation.owner_id == raw_segment.owner_id,
        AuthorityProviderObservation.product_address == raw_segment.product_address,
        AuthorityProviderObservation.event_time.in_(dates),
        AuthorityProviderObservation.raw_segment_address != raw_segment.address,
    ).limit(1))
    if existing is not None:
        _refuse(
            "CSV_REVISION_UNSUPPORTED",
            "A different source file already covers one or more of these dates. "
            "Import dates without overlap; replacing recorded observations is not supported.",
        )


def _session_source(payload, inspection, spec, raw):
    from research.data.imported_sessions import SCHEMA, validate_sessions
    if payload is None:
        return None
    validate_sessions(payload, labels=[_event_time(bar.session_date)
        for bar in inspection.bars], timezone=spec.date_timezone)
    source = RawObservationSegment(raw.owner_id, raw.product_address, raw.contract_address,
        "application/json", SCHEMA, payload, raw.recorded_at)
    return source


def _session_evidence(raw, session_source):
    return tuple(sorted([raw.address] + ([session_source.address] if session_source else [])))


def _calendar_caveat(session_source):
    return "user-declared complete session metadata" if session_source else "exchange calendar coverage not supplied"


@retain_observation_dependencies
def prepare_user_csv(
    execution_session,
    *,
    owner_id: str,
    project_id: str,
    raw: bytes,
    spec: UserCsvSpec,
    observed_at: dt.datetime,
    session_metadata: bytes | None = None,
) -> ImportedDataset:
    observed_at = observed_at.astimezone(UTC).replace(microsecond=0)
    inspection = inspect_user_csv(raw, spec, observed_at=observed_at)
    instrument = _instrument(spec)
    entity = ProviderEntity("strategy-os", "USER_CSV", "User-supplied file")
    instrument_namespace = instrument.address[7:23]
    product = _product(entity, instrument, spec, project_id)
    evidence = content_address({"schema": "user-csv-source/1",
                                "sha256": inspection.source_sha256})
    contract = ProviderContract(
        owner_id, product.address, "RESEARCH", ("PERSONAL_RESEARCH",),
        inspection.event_start, None, evidence,
    )
    raw_segment = RawObservationSegment(
        owner_id, product.address, contract.address, "text/csv",
        "user-csv-daily/1", raw, observed_at,
    )
    alias = ProviderInstrumentAlias(
        product.address, spec.expected_instrument, spec.provider_symbol,
        instrument.address, "1", inspection.event_start, None,
        product.observation_namespace, raw_segment.address,
    )
    algorithm = authority.DeterministicAlgorithm(
        owner_id, "user-csv-daily-normalization", "1",
        content_address({"schema": "user-csv-normalizer/1"}),
        (content_address({"schema": "user-csv-validation/1", "fields": inspection.fields}),),
        observed_at,
    )
    session_source = _session_source(session_metadata, inspection, spec, raw_segment)
    truth = MarketTruthSnapshot(
        (), inspection.event_start, inspection.event_end, observed_at,
        Quality.RECONSTRUCTED,
        Reconstruction("user-declared-date-mapping", "1", (
            _calendar_caveat(session_source),
            "historical source availability timestamps not supplied",
        )),
        "RESEARCH", observed_at, (instrument.address,), _session_evidence(raw_segment, session_source),
    )
    alignment = authority.AlignmentPolicy(
        owner_id, "USER_DECLARED_DATE_LABEL", "ALL_RECORDED", spec.date_timezone,
        86_400, truth.address, algorithm.address, observed_at,
    )
    missing = authority.MissingDataPolicy(owner_id, "REFUSE", (), algorithm.address, observed_at)
    adjustment = authority.AdjustmentPolicy(
        owner_id, (instrument.address,), (truth.address,), "NONE", algorithm.address, observed_at)
    roll = authority.RollPolicy(
        owner_id, (instrument.address,), (truth.address,), "NONE", algorithm.address,
        observed_at, "NOT_APPLICABLE")
    mapping_parameters = _mapping_parameters(spec, inspection.fields)
    schema = authority.RawSchema(
        owner_id, product.address, contract.address, raw_segment.raw_schema,
        tuple(sorted((field.lower(), "number") for field in inspection.fields)),
        raw_segment.address, observed_at,
    )
    transform = authority.NormalizationTransform(
        owner_id, (schema.address,), "strategy-bar/1", mapping_parameters,
        algorithm.address, observed_at,
    )
    lag = int((observed_at - inspection.event_end).total_seconds())
    conformance = ProviderConformance(
        product.address, inspection.fields, (86_400,), "bounded-user-csv-validation", "1",
        observed_at, observed_at + dt.timedelta(seconds=1), (raw_segment.address,), "PASS",
        tuple(_coverage(field, inspection, lag) for field in inspection.fields),
    )
    profile = CapabilityProfile(
        owner_id, "RESEARCH", 1, observed_at, observed_at + dt.timedelta(days=1),
        conformance.address, tuple(_offer(field, inspection, lag) for field in inspection.fields),
        0, entity.address, product.address, contract.address,
    )

    _refuse_revised_import(execution_session, raw_segment, inspection)
    persist_canonical_instrument(execution_session, instrument)
    persist_provider_identity(execution_session, entity, product, contract)
    persist_raw_segment(execution_session, raw_segment)
    if session_source is not None:
        persist_raw_segment(execution_session, session_source)
    persist_provider_alias(execution_session, alias)
    authority.persist_deterministic_algorithm(execution_session, algorithm)
    persist_market_truth_snapshot(execution_session, truth)
    authority.persist_alignment_policy(execution_session, alignment)
    authority.persist_missing_data_policy(execution_session, missing)
    authority.persist_adjustment_policy(execution_session, adjustment)
    authority.persist_roll_policy(execution_session, roll)
    authority.persist_raw_schema(execution_session, schema)
    authority.persist_normalization_transform(execution_session, transform)
    persist_provider_conformance(execution_session, conformance)
    persist_capability_profile(execution_session, profile)

    source_addresses, normalized_addresses, index_rows = [], [], []
    raw_digest = hashlib.sha256(raw).hexdigest()
    for bar in inspection.bars:
        event, completed = _event_time(bar.session_date), _completed_at(bar.session_date)
        numbers = (*((getattr(bar, field.lower())) for field in PRICE_FIELDS),
                   *((bar.volume,) if "VOLUME" in inspection.fields else ()))
        refs = []
        for field, number in zip(inspection.fields, numbers, strict=True):
            sequence = f"{instrument_namespace}:{bar.session_date.isoformat()}:{field}"
            source = ProviderObservation(
                owner_id, entity.address, product.address, contract.address, alias.address,
                spec.expected_instrument, raw_segment.raw_schema, field.lower(), 86_400,
                event, completed, observed_at, observed_at,
                sequence, sequence, raw_segment.address,
                0, len(raw), raw_digest, valid(number).state,
            )
            persist_provider_observation(execution_session, source)
            normalized = NormalizedMarketObservation(
                instrument.address, (source.address,), transform.address, "1", alignment.address,
                algorithm.address, "1", truth.address, transform.output_schema, field, 86_400,
                event, completed, observed_at, observed_at, valid(number),
            )
            persist_normalized_observation(execution_session, normalized)
            source_addresses.append(source.address)
            normalized_addresses.append(normalized.address)
            refs.append(normalized.address)
        index_rows.append(refs)
    creation = authority.DatasetCreationEvidence(
        owner_id, "strategy-os-user-csv/1",
        tuple(sorted((*source_addresses, *normalized_addresses))),
        (raw_segment.address,), algorithm.address, observed_at,
    )
    authority.persist_dataset_creation_evidence(execution_session, creation)
    index = encode_observation_index(
        instrument.address, 86_400, index_rows, fields=inspection.fields, codec=CODEC_V2)
    availability_end = observed_at + dt.timedelta(seconds=1)
    segment = DatasetSegment(
        owner_id=owner_id, object_address=dataset_byte_digest(index),
        byte_digest=dataset_byte_digest(index), byte_length=len(index),
        media_type="application/json", raw_schema_address=schema.address,
        row_start=0, row_end=len(inspection.bars), instrument_addresses=(instrument.address,),
        fields=tuple(sorted(inspection.fields)),
        event_start=inspection.event_start.isoformat(), event_end=inspection.event_end.isoformat(),
        availability_start=observed_at.isoformat(), availability_end=availability_end.isoformat(),
        provider_product_addresses=(product.address,), provider_contract_addresses=(contract.address,),
        provider_observation_addresses=tuple(sorted(source_addresses)),
        normalized_observation_addresses=tuple(sorted(normalized_addresses)),
        normalization_transform_addresses=(transform.address,),
        algorithm_addresses=(algorithm.address,), correction_addresses=(),
        creation_evidence_address=creation.address,
    )
    manifest = DatasetManifest(
        owner_id=owner_id, purpose=f"user-supplied-personal-research:{project_id}", mode="RESEARCH",
        segment_addresses=(segment.segment_address,), aggregate_byte_digest=dataset_byte_digest(index),
        aggregate_byte_length=len(index), instrument_addresses=(instrument.address,),
        fields=segment.fields, event_start=segment.event_start, event_end=segment.event_end,
        availability_start=segment.availability_start, availability_end=segment.availability_end,
        gaps=(), correction_addresses=(), provider_entity_addresses=(entity.address,),
        provider_product_addresses=(product.address,), provider_contract_addresses=(contract.address,),
        provider_observation_addresses=tuple(sorted(source_addresses)),
        normalized_observation_addresses=tuple(sorted(normalized_addresses)),
        raw_schema_addresses=(schema.address,), normalization_transform_addresses=(transform.address,),
        truth_snapshot_addresses=(truth.address,), creation_evidence_addresses=(creation.address,),
        capability_profile_address=profile.capability_profile_address,
        alignment_policy_address=alignment.address, missing_data_policy_address=missing.address,
        adjustment_policy_address=adjustment.address, roll_policy_address=roll.address,
        algorithm_addresses=(algorithm.address,), created_at=observed_at.isoformat(),
        recorded_at=observed_at.isoformat(),
    )
    segments = {segment.segment_address: (segment, index)}
    return ImportedDataset(manifest, instrument, observed_at, segments)


def publish_user_csv(research_session, execution_session, imported: ImportedDataset) -> None:
    persist_verified_dataset_authority(
        research_session, manifest=imported.manifest, segments=imported.segments,
        execution_session=execution_session, at_time=imported.ready_as_of,
    )


def persist_user_csv(
    execution_session,
    research_session,
    *,
    owner_id: str,
    project_id: str,
    raw: bytes,
    spec: UserCsvSpec,
    observed_at: dt.datetime,
    session_metadata: bytes | None = None,
) -> ImportedDataset:
    imported = prepare_user_csv(
        execution_session, owner_id=owner_id, project_id=project_id, raw=raw,
        spec=spec, observed_at=observed_at, session_metadata=session_metadata)
    publish_user_csv(research_session, execution_session, imported)
    return imported


__all__ = [
    "CsvColumnMapping", "CsvInspection", "ImportedDataset", "MAX_CSV_BYTES",
    "UserCsvImportRefused", "UserCsvSpec", "inspect_user_csv", "observed_at_for_import",
    "persist_user_csv", "prepare_user_csv", "publish_user_csv",
]
