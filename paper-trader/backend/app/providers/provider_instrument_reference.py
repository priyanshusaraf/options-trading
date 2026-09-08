"""Bounded provider catalogue descriptors, never canonical research instruments."""
from __future__ import annotations

import datetime as dt
import re
import unicodedata
from decimal import Decimal, InvalidOperation

from app.ir.hashing import content_address


FIELDS = frozenset({"token", "symbol", "name", "exchange", "segment", "instrument_type",
                    "expiry", "strike", "lot_size", "tick_size"})
DECIMAL_FIELDS = ("strike", "lot_size", "tick_size")


class ProviderReferenceInvalid(ValueError):
    """A catalogue row or selected descriptor is malformed or incomplete."""


def _text(value, maximum, *, empty=False):
    if (type(value) is not str or not int(not empty) <= len(value) <= maximum
            or value != value.strip() or unicodedata.normalize("NFC", value) != value
            or any(ord(character) < 32 or ord(character) == 127 for character in value)):
        raise ProviderReferenceInvalid("provider reference text is invalid")
    return value


def _token(value):
    if type(value) is not int or not 1 <= value <= 4_294_967_295:
        raise ProviderReferenceInvalid("provider reference token is invalid")
    return value


def _expiry(value):
    if value is None:
        return None
    if type(value) is not str or len(value) != 10:
        raise ProviderReferenceInvalid("provider expiry is invalid")
    try:
        parsed = dt.date.fromisoformat(value)
    except ValueError:
        raise ProviderReferenceInvalid("provider expiry is invalid") from None
    if parsed.isoformat() != value:
        raise ProviderReferenceInvalid("provider expiry is not canonical")
    return value


def _decimal_number(value):
    if type(value) not in (str, int, float, Decimal) or len(str(value)) > 64:
        raise ProviderReferenceInvalid("provider decimal is invalid")
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        raise ProviderReferenceInvalid("provider decimal is invalid") from None
    if not number.is_finite() or number < 0:
        raise ProviderReferenceInvalid("provider decimal must be finite and nonnegative")
    return number


def _decimal(value):
    if value is None or value == "":
        return None
    number = _decimal_number(value)
    if number == 0:
        return "0"
    if not -24 <= number.adjusted() <= 24:
        raise ProviderReferenceInvalid("provider decimal exceeds its bound")
    rendered = format(number, "f")
    return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered


def validate_reference(reference):
    """Validate a closed normalized descriptor without claiming economic identity."""
    if type(reference) is not dict or set(reference) != FIELDS:
        raise ProviderReferenceInvalid("provider reference fields are invalid")
    result = {"token": _token(reference["token"]), "symbol": _text(reference["symbol"], 64),
              "name": _text(reference["name"], 128, empty=True),
              "exchange": _text(reference["exchange"], 16),
              "segment": _text(reference["segment"], 32),
              "instrument_type": _text(reference["instrument_type"], 32),
              "expiry": _expiry(reference["expiry"])}
    if re.fullmatch(r"[A-Za-z0-9_-]+", result["exchange"]) is None:
        raise ProviderReferenceInvalid("provider exchange is invalid")
    for field in DECIMAL_FIELDS:
        value = reference[field]
        if value is not None and (type(value) is not str or _decimal(value) != value):
            raise ProviderReferenceInvalid("provider decimal is not canonical")
        result[field] = value
    return result


def reference_from_row(row):
    """Project catalogue terms only; volatile last_price and unknown fields stay out."""
    if type(row) is not dict:
        raise ProviderReferenceInvalid("provider row is invalid")
    expiry = row.get("expiry")
    if type(expiry) is dt.date:
        expiry = expiry.isoformat()
    reference = {"token": row.get("instrument_token"), "symbol": row.get("tradingsymbol"),
                 "name": row.get("name", ""), "exchange": row.get("exchange"),
                 "segment": row.get("segment"), "instrument_type": row.get("instrument_type"),
                 "expiry": None if expiry == "" else expiry}
    reference.update({field: _decimal(row.get(field)) for field in DECIMAL_FIELDS})
    return validate_reference(reference)


def reference_fingerprint(reference):
    return content_address({"schema": "provider-instrument-reference/1",
                            "reference": validate_reference(reference)})
