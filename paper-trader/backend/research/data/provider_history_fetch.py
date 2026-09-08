"""Fetch retained daily responses using an owner selection and existing grant.

No provider request establishes a grant. This service publishes no authority
facts and owns no commit; the existing runtime retains its token-invalidation
behavior. The caller registers the sourced root and publishes returned facts.
"""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass, replace

from sqlalchemy import or_, select

from app.core.credential_vault import CredentialVaultUnavailable, CredentialDecryptionFailed
from app.core.provider_selections import (
    load_provider_selection, ProviderSelectionInvalid, ProviderSelectionNotFound)
from app.db.models import AuthorityProviderContract, Project
from app.ir.hashing import canonical_json
from app.market_data import kite_historical_attribution as attribution
from app.market_truth.cash_reference import source_reference_for_symbol
from app.market_truth.identity import (
    CanonicalPhysicalInstrument, ProviderEntity, ProviderProduct, ProviderContract, load_provider_identity)
from app.providers import data_connection_service as connections
from app.providers.connection_store import ConnectionNotFound, DataConnectionUnavailable
from app.providers.zerodha_data_runtime import (
    _history_windows, MAX_HISTORY_RESPONSE_BYTES, MAX_INSTRUMENT_RESPONSE_BYTES,
    ZerodhaDataUnavailable, ZerodhaReauthRequired, ZerodhaTransientError)

UTC = dt.timezone.utc
EXCHANGE_TIME = dt.timezone(dt.timedelta(hours=5, minutes=30))


class HistoricalFetchRefused(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def _require(condition, code, message):
    if not condition:
        raise HistoricalFetchRefused(code, message)


def _now():
    return dt.datetime.now(UTC)


def _received(value):
    _require(type(value) is dt.datetime and value.tzinfo is not None
             and value.utcoffset() == dt.timedelta(0), "HISTORICAL_FETCH_CAPTURE_INVALID",
             "The provider response has no exact UTC receipt time. Fetch the range again.")
    return value


def _request_utc(value):
    if value.utcoffset() is None:
        value = value.replace(tzinfo=EXCHANGE_TIME)
    return value.astimezone(UTC)


def _windows(from_date, to_date):
    try:
        windows = tuple((_request_utc(start), _request_utc(end))
                        for start, end in _history_windows(from_date, to_date, "day"))
    except (ValueError, TypeError, AttributeError, OverflowError, ZerodhaDataUnavailable):
        raise HistoricalFetchRefused("HISTORICAL_FETCH_RANGE_INVALID",
            "Choose a valid daily date range within the request budget. Request chunks do not describe total history retention.") from None
    _require(windows[-1][1].astimezone(EXCHANGE_TIME).date() < _now().astimezone(EXCHANGE_TIME).date(),
        "HISTORICAL_FETCH_INCOMPLETE_DAY",
        "Choose a range ending before today; daily history requires completed date labels.")
    return windows


@dataclass(frozen=True)
class HistoricalResponseCapture:
    payload: bytes
    received_at: dt.datetime
    recorded_at: dt.datetime
    requested_start: dt.datetime
    requested_end: dt.datetime
    interval: str
    row_count: int
    current_reference: CurrentReferenceCapture | None = None


@dataclass(frozen=True)
class CurrentReferenceCapture:
    payload: bytes
    received_at: dt.datetime
    recorded_at: dt.datetime
    exchange: str


@dataclass(frozen=True)
class HistoricalFetchResult:
    owner_id: str
    project_id: str
    selection_address: str
    data_account_id: str
    connection_id: int
    instrument: CanonicalPhysicalInstrument
    definition_evidence: bytes
    requested_start: dt.datetime
    requested_end: dt.datetime
    current_reference: CurrentReferenceCapture
    captures: tuple[HistoricalResponseCapture, ...]
    sources: tuple[attribution.HistoricalAttribution, ...]


@dataclass(frozen=True)
class _Access:
    owner_id: str
    data_account_id: str
    connection_id: int
    selection: bytes
    entity: ProviderEntity
    product: ProviderProduct
    contract: ProviderContract
    instrument: CanonicalPhysicalInstrument
    definition_evidence: bytes


def _grant(session, owner_id, when):
    rows = session.scalars(select(AuthorityProviderContract).where(
        AuthorityProviderContract.owner_id == owner_id,
        AuthorityProviderContract.mode == "RESEARCH",
        AuthorityProviderContract.effective_from <= when.replace(tzinfo=None),
        or_(AuthorityProviderContract.effective_to.is_(None),
            AuthorityProviderContract.effective_to > when.replace(tzinfo=None)))).all()
    verified = [load_provider_identity(session, row.address) for row in rows]
    admitted = [values for values in verified if values[0].entity_code == "kite"
                and (values[1].product_code, values[1].product_version) == ("kite-connect-v3", "3")
                and "HISTORICAL" in values[2].permitted_uses]
    reason = "No active" if not admitted else "Multiple active"
    _require(len(admitted) == 1, "HISTORICAL_FETCH_GRANT_UNAVAILABLE",
        f"{reason} historical research grants are recorded for this owner and the supported Kite Connect v3 product. Resolve the missing or ambiguous grant before fetching.")
    return admitted[0]



def _cash_root(reference):
    sourced = source_reference_for_symbol(reference["symbol"], reference["exchange"])
    _require(sourced is not None, "HISTORICAL_FETCH_ROOT_UNAVAILABLE",
             "This watchlist selection is valid, but its research instrument definition is not available yet.")
    instrument, evidence = sourced
    segment = "INDICES" if instrument.asset_class == "INDEX" else reference["exchange"]
    _require((reference["segment"], reference["instrument_type"], reference["expiry"]) == (segment, "EQ", None),
        "HISTORICAL_FETCH_ROOT_UNAVAILABLE",
        "This provider contract remains available in the watchlist, but it has no supported cash research definition.")
    return instrument, evidence

def _access(session_factory, principal, project_id, selection_address, *, build_runtime=False):
    with session_factory() as session:
        store, connection_id = connections._instrument_connection(session, principal, session_factory)
        project = session.scalar(select(Project.project_id).where(Project.project_id == project_id,
            Project.owner_id == store.owner_id, Project.status == "active"))
        _require(project is not None, "HISTORICAL_FETCH_PROJECT_UNAVAILABLE",
                 "Choose an active project owned by this account before fetching history.")
        selected = load_provider_selection(session, owner_id=store.owner_id, selection_address=selection_address)["selection"]
        _require(selected["data_account_id"] == store.broker_account_id, "HISTORICAL_FETCH_SELECTION_UNAVAILABLE",
                 "The saved selection belongs to a different data account. Select the instrument again with the current account.")
        reference = selected["reference"]
        instrument, evidence = _cash_root(reference)
        entity, product, contract = _grant(session, store.owner_id, _now())
        access = _Access(store.owner_id, store.broker_account_id, connection_id,
            canonical_json(selected).encode(), entity, product, contract, instrument, canonical_json(evidence).encode())
        runtime = store.zerodha_data_runtime(connection_id) if build_runtime else None
        return runtime, access


def verify_captured_reference(payload, reference):
    """Verify the full saved descriptor against original CSV without provider access."""
    _require(type(payload) is bytes and 0 < len(payload) <= MAX_INSTRUMENT_RESPONSE_BYTES,
        "HISTORICAL_FETCH_CAPTURE_INVALID", "The original instrument response is missing or exceeds its bound. Fetch again.")
    parsed = attribution._reference_rows(payload)
    for row in parsed:
        token = row["instrument_token"]
        row["instrument_token"] = int(token) if token.isdecimal() else token
    return connections._verified_provider_selection(parsed, reference)


def _reference_capture(runtime, reference):
    captures = []
    def retain(payload, received_at, exchange):
        captures.append(CurrentReferenceCapture(payload, _received(received_at), _now(), exchange))
    rows = runtime.instruments(reference["exchange"], capture_response=retain)
    connections._verified_provider_selection(rows, reference)
    _require(len(captures) == 1 and captures[0].exchange == reference["exchange"],
        "HISTORICAL_FETCH_CAPTURE_INVALID", "The original current instrument response was not captured. Fetch again.")
    captured = captures[0]
    verify_captured_reference(captured.payload, reference)
    _require(captured.received_at <= captured.recorded_at, "HISTORICAL_FETCH_CAPTURE_INVALID",
             "The current instrument receipt time is inconsistent. Fetch again.")
    return captured


def _capture(payload, received_at, start, end, interval, *, expected_interval="day"):
    _require(type(payload) is bytes and 0 < len(payload) <= MAX_HISTORY_RESPONSE_BYTES,
        "HISTORICAL_FETCH_CAPTURE_INVALID", "The original historical response is missing or exceeds its bound. Fetch a shorter range.")
    document = attribution._closed(attribution._json(payload), ("status", "data"))
    _require(document["status"] == "success", "HISTORICAL_FETCH_CAPTURE_INVALID",
             "The retained historical response was not successful. Fetch again.")
    rows = attribution._closed(document["data"], ("candles",))["candles"]
    _require(type(rows) is list, "HISTORICAL_FETCH_CAPTURE_INVALID",
             "The retained historical response has malformed candle rows. Fetch again.")
    received, recorded = _received(received_at), _now()
    _require(received <= recorded and interval == expected_interval
             and interval in attribution.INTERVAL_SECONDS, "HISTORICAL_FETCH_CAPTURE_INVALID",
             "The historical receipt time or interval is inconsistent. Fetch again.")
    return HistoricalResponseCapture(payload, received, recorded, _request_utc(start), _request_utc(end), interval, len(rows))


def _history_captures(runtime, reference, windows, interval="day"):
    captures = []
    runtime.historical_data(reference["token"], windows[0][0], windows[-1][1], interval,
        continuous=False, oi=False,
        capture_response=lambda *response: captures.append(_capture(*response, expected_interval=interval)))
    actual = tuple((capture.requested_start, capture.requested_end) for capture in captures)
    _require(actual == windows, "HISTORICAL_FETCH_CAPTURE_INVALID",
             "The retained responses do not cover every requested chunk exactly. Fetch the range again.")
    _require(any(capture.row_count for capture in captures), "HISTORICAL_FETCH_EMPTY",
             "No completed bars were returned for this range. Choose another range; this response does not establish the provider's total history limit.")
    return tuple(captures)


def _sources(access, reference, reference_capture, captures, as_of, clock_binding=None):
    for capture in captures:
        attribution._grant(access.contract, capture.received_at)
    _require(all(reference_capture.received_at <= capture.received_at for capture in captures),
        "HISTORICAL_FETCH_CAPTURE_INVALID", "The historical response predates its current instrument reference. Fetch again.")
    common = dict(owner_id=access.owner_id, connection_id=access.connection_id,
        entity=access.entity, product=access.product, contract=access.contract, instrument=access.instrument,
        token=reference["token"], symbol=reference["symbol"], exchange=reference["exchange"],
        current_reference_bytes=reference_capture.payload, reference_received_at=reference_capture.received_at,
        reference_recorded_at=reference_capture.recorded_at, as_of=as_of, clock_binding=clock_binding)
    return tuple(attribution.prepare_historical_attribution(**common,
        interval=capture.interval,
        requested_start=capture.requested_start, requested_end=capture.requested_end,
        historical_response_bytes=capture.payload, captured_at=capture.received_at, recorded_at=capture.recorded_at)
        for capture in captures if capture.row_count)



def _source_failure(exc):
    categories = (
        (ZerodhaReauthRequired, "DATA_REAUTH_REQUIRED", "Reconnect your data provider, then fetch history again."),
        (ZerodhaTransientError, "DATA_PROVIDER_BUSY", "The data provider is temporarily unavailable. Wait a moment and retry."),
        ((CredentialVaultUnavailable, CredentialDecryptionFailed), "DATA_VAULT_UNAVAILABLE",
         "Data connection credentials are unavailable. Retry when the service recovers."),
        ((ConnectionNotFound, DataConnectionUnavailable, ZerodhaDataUnavailable), "DATA_CONNECTION_UNAVAILABLE",
         "An active owner data connection is required. Configure application keys and reconnect before fetching history."),
        ((connections.InstrumentSelectionUnavailable, ProviderSelectionInvalid, ProviderSelectionNotFound),
         "HISTORICAL_FETCH_SELECTION_UNAVAILABLE",
         "The saved selection is unavailable or its current provider terms have changed. Review and select the instrument again."),
        ((ValueError, TypeError, KeyError, AttributeError), "HISTORICAL_FETCH_CAPTURE_INVALID",
         "The retained provider response or its authority is malformed. Check the selection and grant, then fetch again."),
    )
    for types, code, message in categories:
        if isinstance(exc, types):
            return HistoricalFetchRefused(code, message)
    return HistoricalFetchRefused("HISTORICAL_FETCH_UNAVAILABLE",
        "Historical data or its current source authority is unavailable. Check the saved selection, connection and grant, then fetch again.")

def _load_clock(session_factory, access, binding, as_of):
    from app.market_data.dated_session_clock import load_session_clock
    with session_factory() as session:
        return load_session_clock(session, owner_id=access.owner_id, instrument=access.instrument,
            product_address=access.product.address, contract_address=access.contract.address,
            binding=binding, as_of=as_of)


def _monitoring_windows(from_date, to_date, interval, clock_binding, cutoff_at):
    from app.market_truth.dated_sessions import expected_bars
    _require(interval in {"15minute", "30minute", "60minute"}
             and clock_binding.resolution_seconds == attribution.INTERVAL_SECONDS[interval],
             "HISTORICAL_FETCH_CLOCK_UNAVAILABLE", "The selected interval has no matching retained bar clock.")
    requested = tuple((_request_utc(start), _request_utc(end))
                      for start, end in _history_windows(from_date, to_date, interval))
    bars = expected_bars(clock_binding.calendar, requested_start=requested[0][0],
        requested_end=requested[-1][1], resolution_seconds=clock_binding.resolution_seconds, cutoff_at=cutoff_at)
    _require(bool(bars), "MONITORING_INPUT_NO_COMPLETED_BAR",
             "No new completed bar is available in the declared sessions yet.")
    return tuple((_request_utc(start), _request_utc(end))
        for start, end in _history_windows(requested[0][0], bars[-1][0], interval))


def _fetch_history(session_factory, principal, *, project_id, selection_address, from_date, to_date,
                   interval="day", clock_binding_addresses=None):
    try:
        cutoff_at = _now()
        windows = _windows(from_date, to_date) if interval == "day" else None
        runtime, initial = _access(session_factory, principal, project_id, selection_address, build_runtime=True)
        clock_binding = None
        if interval != "day":
            clock_binding = _load_clock(session_factory, initial, clock_binding_addresses, cutoff_at)
            windows = _monitoring_windows(from_date, to_date, interval, clock_binding, cutoff_at)
        reference = json.loads(initial.selection)["reference"]
        current_reference = _reference_capture(runtime, reference)
        captures = _history_captures(runtime, reference, windows, interval)
        if clock_binding is not None:
            captures = tuple(replace(item, current_reference=current_reference) for item in captures)
        _, current = _access(session_factory, principal, project_id, selection_address)
        _require(current == initial, "HISTORICAL_FETCH_ACCESS_CHANGED",
                 "The owner, project, connection or research grant changed during fetching. Review access and fetch again.")
        if clock_binding is not None:
            reloaded = _load_clock(session_factory, current, clock_binding_addresses, cutoff_at)
            _require(reloaded == clock_binding, "HISTORICAL_FETCH_ACCESS_CHANGED",
                     "The retained calendar or completion evidence changed during fetching.")
        sources = _sources(initial, reference, current_reference, captures, _now(), clock_binding)
        return HistoricalFetchResult(initial.owner_id, project_id, selection_address,
            initial.data_account_id, initial.connection_id, initial.instrument, initial.definition_evidence,
            windows[0][0], windows[-1][1], current_reference, captures, sources)
    except HistoricalFetchRefused:
        raise
    except Exception as exc:
        raise _source_failure(exc) from None


def fetch_provider_history(session_factory, principal, *, project_id, selection_address, from_date, to_date):
    """Daily research reads and rechecks; publication remains caller-owned."""
    return _fetch_history(session_factory, principal, project_id=project_id, selection_address=selection_address,
                          from_date=from_date, to_date=to_date)


def fetch_monitoring_history(session_factory, principal, *, project_id, selection_address,
        from_date, to_date, interval, clock_binding_addresses):
    """Internal DATA-only intraday acquisition with retained, pre-request bar clocks."""
    _require(type(interval) is str and interval in {"15minute", "30minute", "60minute"},
        "HISTORICAL_FETCH_CLOCK_UNAVAILABLE", "Choose a supported intraday monitoring interval.")
    return _fetch_history(session_factory, principal, project_id=project_id, selection_address=selection_address,
        from_date=from_date, to_date=to_date, interval=interval, clock_binding_addresses=clock_binding_addresses)
