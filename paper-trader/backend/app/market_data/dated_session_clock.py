"""Retained provider bar clocks, independently verifiable before dataset policy.

The initial implementation admits only the exact isolated synthetic fixture.
A real provider needs separately supported completion evidence; a declaration
of exchange hours does not establish when its candles become complete.
"""
from __future__ import annotations

from dataclasses import dataclass
import datetime as dt

from app.ir.hashing import canonical_json
from app.market_data.observations import RawObservationSegment, load_raw_segment
from app.market_truth.dated_sessions import DatedSessions, parse_dated_sessions
from app.market_truth.identity import ProviderEntity, load_provider_identity

SCHEMA = "dated-trading-sessions/1"
COMPLETION_SCHEMA = "synthetic-provider-bar-completion/1"
COMPLETION_RULE = "SESSION_OPEN_CLIP_CLOSE_V1"
_BINDING_FIELDS = {"calendar_source_address", "completion_source_address",
                   "calendar_address", "resolution_seconds"}


def _require(condition):
    if not condition:
        raise ValueError("DATED_SESSION_BINDING_UNAVAILABLE")


@dataclass(frozen=True, slots=True)
class RetainedSessionClock:
    calendar: DatedSessions
    calendar_source: RawObservationSegment
    completion_source: RawObservationSegment
    resolution_seconds: int

    @property
    def source_address(self):
        return self.calendar_source.address

    @property
    def completion_source_address(self):
        return self.completion_source.address

    def metadata(self):
        return {"calendar_address": self.calendar.address, "source_address": self.source_address,
                "provenance": self.calendar.provenance, "timezone": self.calendar.timezone,
                "completion_rule": COMPLETION_RULE,
                "completion_source_address": self.completion_source_address}

    def receipt_binding(self):
        return {"calendar_source_address": self.source_address,
                "completion_source_address": self.completion_source_address,
                "calendar_address": self.calendar.address,
                "resolution_seconds": self.resolution_seconds}


def _fixture_identity(entity, product, contract, owner_id):
    from app.core.config import get_settings
    fixture = ProviderEntity("synthetic", "kite", "Synthetic provider authority")
    _require(entity.address == fixture.address and get_settings().provider == "mock")
    _require(product.entity_address == entity.address and contract.product_address == product.address)
    _require(contract.owner_id == owner_id and contract.mode == "RESEARCH"
             and contract.permitted_uses == ("HISTORICAL",))


def _source(raw, schema, owner_id, product_address, contract_address, as_of):
    _require(type(raw) is RawObservationSegment)
    _require((raw.raw_schema, raw.media_type, raw.owner_id, raw.product_address, raw.contract_address)
             == (schema, "application/json", owner_id, product_address, contract_address))
    _require(raw.recorded_at <= as_of)


def _completion(calendar, raw, product, contract, resolution_seconds):
    expected = {"schema": COMPLETION_SCHEMA, "calendar_address": calendar.address,
                "product_address": product.address, "contract_address": contract.address,
                "resolution_seconds": resolution_seconds,
                "completion_rule": COMPLETION_RULE, "provenance": "SYNTHETIC"}
    _require(raw.payload == canonical_json(expected).encode("utf-8"))
    _require(calendar.recorded_at <= raw.recorded_at)


def prepare_session_clock(*, owner_id, entity, product, contract, instrument,
        resolution_seconds, calendar_source, completion_source, as_of):
    """Validate supplied facts; persistence reloads their exact retained versions."""
    _require(type(as_of) is dt.datetime and as_of.tzinfo is dt.timezone.utc)
    _require(type(resolution_seconds) is int and resolution_seconds in {900, 1800, 3600})
    _fixture_identity(entity, product, contract, owner_id)
    for raw, schema in ((calendar_source, SCHEMA), (completion_source, COMPLETION_SCHEMA)):
        _source(raw, schema, owner_id, product.address, contract.address, as_of)
    # Timezone is part of the closed, hashed calendar document. The alignment
    # policy verifies its own exact timezone against this parsed result later.
    from app.market_truth.dated_sessions import _document
    timezone = _document(calendar_source.payload)["timezone"]
    calendar = parse_dated_sessions(calendar_source.payload, instrument_address=instrument.address,
        venue_code=instrument.venue_code, timezone=timezone, as_of=as_of, allow_synthetic=True)
    _require(calendar.provenance == "SYNTHETIC" and calendar.recorded_at <= calendar_source.recorded_at)
    _completion(calendar, completion_source, product, contract, resolution_seconds)
    return RetainedSessionClock(calendar, calendar_source, completion_source, resolution_seconds)


def verify_session_clock(clock, *, owner_id, entity, product, contract, instrument,
                         resolution_seconds, as_of):
    _require(type(clock) is RetainedSessionClock and clock.resolution_seconds == resolution_seconds)
    verified = prepare_session_clock(owner_id=owner_id, entity=entity, product=product,
        contract=contract, instrument=instrument, resolution_seconds=resolution_seconds,
        calendar_source=clock.calendar_source, completion_source=clock.completion_source, as_of=as_of)
    _require(verified == clock)
    return verified


def load_session_clock(session, *, owner_id, instrument, product_address, contract_address,
                       binding, as_of):
    """Reload all clock evidence; no dataset or newly minted policy is required."""
    _require(type(binding) is dict and set(binding) == _BINDING_FIELDS)
    entity, product, contract = load_provider_identity(session, contract_address)
    _require(product.address == product_address)
    result = prepare_session_clock(owner_id=owner_id, entity=entity, product=product,
        contract=contract, instrument=instrument, resolution_seconds=binding["resolution_seconds"],
        calendar_source=load_raw_segment(session, binding["calendar_source_address"]),
        completion_source=load_raw_segment(session, binding["completion_source_address"]), as_of=as_of)
    _require(result.receipt_binding() == binding)
    return result
