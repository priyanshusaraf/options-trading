"""Immutable owner watchlist selections, separate from canonical data authority."""
from __future__ import annotations

import datetime as dt
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.concurrency import begin_reservation, caller_owned_savepoint
from app.db.models import Organization, OwnerProviderInstrumentSelection as Selection
from app.ir.hashing import canonical_json, content_address
from app.market_truth.temporal import require_sql_utc_naive, to_sql_utc_naive
from app.providers.provider_instrument_reference import validate_reference, reference_fingerprint

SCHEMA = "owner-provider-instrument-selection/1"
_FIELDS = {"schema", "owner_id", "data_account_id", "connection_id", "provider", "reference", "observed_at"}


class ProviderSelectionInvalid(ValueError):
    pass


class ProviderSelectionNotFound(LookupError):
    pass


def _require(condition, message):
    if not condition:
        raise ProviderSelectionInvalid(message)


def _text(value):
    _require(type(value) is str and 1 <= len(value) <= 64, "selection identity text is invalid")
    _require(value == value.strip() and all(ord(character) >= 32 for character in value),
             "selection identity text must be trimmed without control characters")
    return value


def _observed_at(value):
    if type(value) is str:
        value = dt.datetime.fromisoformat(value)
    _require(type(value) is dt.datetime and value.tzinfo is not None
             and value.utcoffset() == dt.timedelta(0), "selection observation requires exact UTC")
    return value


def _fact(*, owner_id, data_account_id, connection_id, provider, reference, observed_at):
    _require(type(connection_id) is int and 0 < connection_id <= 9_223_372_036_854_775_807,
             "selection connection is invalid")
    _require(provider == "ZERODHA", "selection provider is unsupported")
    return {"schema": SCHEMA, "owner_id": _text(owner_id), "data_account_id": _text(data_account_id),
            "connection_id": connection_id, "provider": provider, "reference": validate_reference(reference),
            "observed_at": _observed_at(observed_at).isoformat()}


def _document(raw):
    try:
        _require(type(raw) is str and len(raw.encode()) <= 8192, "selection document exceeds its bound")
        value = json.loads(raw)
        _require(type(value) is dict and set(value) == _FIELDS and value["schema"] == SCHEMA,
                 "selection document fields are invalid")
        result = _fact(**{key: value[key] for key in _FIELDS - {"schema"}})
        _require(canonical_json(result) == raw, "selection document is not canonical")
        return result
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError) as exc:
        raise ProviderSelectionInvalid("selection document is invalid") from exc


def _row_envelope(row):
    fact = _document(row.canonical_json)
    observed = _observed_at(fact["observed_at"])
    checks = (
        (row.selection_address, content_address(fact)), (row.owner_id, fact["owner_id"]),
        (row.data_account_id, fact["data_account_id"]), (row.connection_id, fact["connection_id"]),
        (row.provider, fact["provider"]), (row.reference_fingerprint, reference_fingerprint(fact["reference"])),
        (require_sql_utc_naive(row.observed_at, "observed_at"), to_sql_utc_naive(observed, "observed_at")),
    )
    _require(all(left == right for left, right in checks), "selection copied columns or address differ")
    return {"selection_address": row.selection_address, "selection": fact}


def _owner_exists(session, owner_id):
    if session.scalar(select(Organization.organization_id).where(Organization.organization_id == owner_id)) is None:
        raise ProviderSelectionNotFound("owner selection is unavailable")


def load_provider_selection(session, *, owner_id, selection_address):
    owner_id = _text(owner_id)
    if type(selection_address) is not str or len(selection_address) != 71:
        raise ProviderSelectionNotFound("owner selection is unavailable")
    row = session.scalar(select(Selection).where(Selection.owner_id == owner_id,
        Selection.selection_address == selection_address).execution_options(populate_existing=True))
    if row is None:
        raise ProviderSelectionNotFound("owner selection is unavailable")
    return _row_envelope(row)


def _existing_selection(session, fact, fingerprint):
    row = session.scalar(select(Selection).where(Selection.owner_id == fact["owner_id"],
        Selection.data_account_id == fact["data_account_id"], Selection.provider == fact["provider"],
        Selection.reference_fingerprint == fingerprint).execution_options(populate_existing=True))
    if row is None:
        return None
    envelope = _row_envelope(row)
    _require(envelope["selection"]["reference"] == fact["reference"], "selection fingerprint collision")
    return envelope


def persist_provider_selection(session, *, owner_id, data_account_id, connection_id, provider, reference, observed_at):
    """Reuse the first descriptor receipt; reserve before any standalone reads."""
    fact = _fact(owner_id=owner_id, data_account_id=data_account_id, connection_id=connection_id,
                 provider=provider, reference=reference, observed_at=observed_at)
    fingerprint = reference_fingerprint(fact["reference"])
    begin_reservation(session, scope=f"provider-selection:{owner_id}")
    _owner_exists(session, owner_id)
    existing = _existing_selection(session, fact, fingerprint)
    if existing is not None:
        return existing
    row = Selection(owner_id=owner_id, selection_address=content_address(fact), data_account_id=data_account_id,
        connection_id=connection_id, provider=provider, reference_fingerprint=fingerprint,
        observed_at=to_sql_utc_naive(_observed_at(fact["observed_at"]), "observed_at"), canonical_json=canonical_json(fact))
    with caller_owned_savepoint(session, scope="provider-selection-insert"):
        session.add(row)
        session.flush()
    return _row_envelope(row)


def validate_persisted_provider_selections(connection):
    """Restore metadata integrity without looking up MONEY connection state."""
    with Session(bind=connection) as session:
        seen = set()
        for row in session.scalars(select(Selection).execution_options(yield_per=100)):
            _row_envelope(row)
            _owner_exists(session, row.owner_id)
            identity = (row.owner_id, row.data_account_id, row.provider, row.reference_fingerprint)
            _require(identity not in seen, "selection descriptor is duplicated")
            seen.add(identity)
