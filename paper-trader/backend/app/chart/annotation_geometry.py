"""Closed annotation geometry with exact arithmetic and separate causal timing.

Decimal inputs use the canonical market-truth string spelling (128 characters
maximum). Derived values are reduced fractions, never rounded prices. Anchors
are coordinates, not assertions of observed market data. Nothing here grants
revision ownership, research eligibility, or execution authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from fractions import Fraction
import json
import re
from typing import ClassVar

from app.ir.hashing import canonical_json, content_address

MAX_DECIMAL_CHARACTERS = 128
MAX_RATIOS = 32
MAX_PAYLOAD_BYTES = 64 * 1024
GEOMETRY_SCHEMA = "normalized-annotation-geometry/1"
APPLICABILITY_SCHEMA = "annotation-applicability/1"
_DECIMAL = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]*[1-9])?\Z")
_TIMESTAMP = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]{1,6})?(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])\Z"
)


class GeometryError(ValueError):
    """A semantic value is malformed, ambiguous, or outside its input bounds."""


class Extension(str, Enum):
    SEGMENT = "SEGMENT"
    RIGHT_RAY = "RIGHT_RAY"
    BOTH = "BOTH"


class Direction(str, Enum):
    UP = "UP"
    DOWN = "DOWN"


class FibonacciMode(str, Enum):
    RETRACEMENT = "RETRACEMENT"
    EXTENSION = "EXTENSION"


class Unavailable(Enum):
    OUTSIDE_GEOMETRY = "OUTSIDE_GEOMETRY"


def _decimal(value: str) -> Fraction:
    if (type(value) is not str or not 1 <= len(value) <= MAX_DECIMAL_CHARACTERS
            or _DECIMAL.fullmatch(value) is None or value == "-0"):
        raise GeometryError("expected a bounded canonical decimal string")
    return Fraction(value)


def _utc(value: datetime) -> datetime:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise GeometryError("timestamp must be an aware datetime")
    try:
        return value.astimezone(timezone.utc)
    except (OverflowError, ValueError) as exc:
        raise GeometryError("timestamp is outside the UTC datetime range") from exc


def _time_text(value: datetime) -> str:
    return value.isoformat(timespec="microseconds")


def _read_time(value: object) -> datetime:
    if type(value) is not str or len(value) > 32 or _TIMESTAMP.fullmatch(value) is None:
        raise GeometryError("expected a bounded aware ISO timestamp at microsecond precision")
    try:
        return _utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except ValueError as exc:
        raise GeometryError("invalid timestamp") from exc


def _microseconds(start: datetime, end: datetime) -> int:
    delta = end - start
    return delta.days * 86_400_000_000 + delta.seconds * 1_000_000 + delta.microseconds


def _rational(value: Fraction) -> dict[str, str]:
    return {"numerator": str(value.numerator), "denominator": str(value.denominator)}


def _encoded(document: dict) -> bytes:
    encoded = canonical_json(document).encode("utf-8")
    if len(encoded) > MAX_PAYLOAD_BYTES:
        raise GeometryError("canonical semantic payload exceeds 64 KiB")
    return encoded


class _SemanticValue:
    __slots__ = ()

    def to_dict(self) -> dict:
        raise NotImplementedError

    @property
    def canonical_bytes(self) -> bytes:
        return _encoded(self.to_dict())

    @property
    def address(self) -> str:
        document = self.to_dict()
        _encoded(document)
        return content_address(document)


@dataclass(frozen=True, slots=True)
class Anchor:
    time: datetime
    price: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "time", _utc(self.time))
        _decimal(self.price)

    def to_dict(self) -> dict:
        return {"time": _time_text(self.time), "price": self.price}


def _anchors(start: Anchor, end: Anchor) -> None:
    if type(start) is not Anchor or type(end) is not Anchor:
        raise GeometryError("coordinates must be immutable Anchors")
    if start.time >= end.time:
        raise GeometryError("anchor times must be distinct and increasing")


@dataclass(frozen=True, slots=True)
class PriceBand:
    lower: Fraction
    upper: Fraction

    def __post_init__(self) -> None:
        if type(self.lower) is not Fraction or type(self.upper) is not Fraction or self.lower > self.upper:
            raise GeometryError("price band must contain ordered exact fractions")

    def contains(self, price: str) -> bool:
        return self.lower <= _decimal(price) <= self.upper


@dataclass(frozen=True, slots=True)
class Level(_SemanticValue):
    price: str
    KIND: ClassVar[str] = "LEVEL"

    def __post_init__(self) -> None:
        _decimal(self.price)

    def at(self, event: datetime) -> Fraction:
        _utc(event)
        return _decimal(self.price)

    def to_dict(self) -> dict:
        return {"schema": GEOMETRY_SCHEMA, "kind": self.KIND, "price": self.price}


@dataclass(frozen=True, slots=True)
class Zone(_SemanticValue):
    lower: str
    upper: str
    KIND: ClassVar[str] = "ZONE"

    def __post_init__(self) -> None:
        if _decimal(self.lower) > _decimal(self.upper):
            raise GeometryError("zone lower must not exceed upper")

    def at(self, event: datetime) -> PriceBand:
        _utc(event)
        return PriceBand(_decimal(self.lower), _decimal(self.upper))

    def to_dict(self) -> dict:
        return {"schema": GEOMETRY_SCHEMA, "kind": self.KIND, "lower": self.lower, "upper": self.upper}


@dataclass(frozen=True, slots=True)
class Line(_SemanticValue):
    start: Anchor
    end: Anchor
    extension: Extension
    KIND: ClassVar[str] = "LINE"

    def __post_init__(self) -> None:
        _anchors(self.start, self.end)
        if type(self.extension) is not Extension:
            raise GeometryError("line extension must be explicit")

    @property
    def slope_per_microsecond(self) -> Fraction:
        return (_decimal(self.end.price) - _decimal(self.start.price)) / _microseconds(self.start.time, self.end.time)

    def at(self, event: datetime) -> Fraction | Unavailable:
        event = _utc(event)
        if self.extension is Extension.SEGMENT and not self.start.time <= event <= self.end.time:
            return Unavailable.OUTSIDE_GEOMETRY
        if self.extension is Extension.RIGHT_RAY and event < self.start.time:
            return Unavailable.OUTSIDE_GEOMETRY
        return _decimal(self.start.price) + self.slope_per_microsecond * _microseconds(self.start.time, event)

    def to_dict(self) -> dict:
        return {"schema": GEOMETRY_SCHEMA, "kind": self.KIND, "start": self.start.to_dict(),
                "end": self.end.to_dict(), "extension": self.extension.value,
                "slope_per_microsecond": _rational(self.slope_per_microsecond)}


@dataclass(frozen=True, slots=True)
class Channel(_SemanticValue):
    center: Line
    half_width: str
    KIND: ClassVar[str] = "CHANNEL"

    def __post_init__(self) -> None:
        if type(self.center) is not Line:
            raise GeometryError("channel center must be a Line")
        if _decimal(self.half_width) < 0:
            raise GeometryError("channel half-width must be nonnegative")

    def at(self, event: datetime) -> PriceBand | Unavailable:
        center = self.center.at(event)
        if isinstance(center, Unavailable):
            return center
        width = _decimal(self.half_width)
        return PriceBand(center - width, center + width)

    def to_dict(self) -> dict:
        return {"schema": GEOMETRY_SCHEMA, "kind": self.KIND,
                "center": self.center.to_dict(), "half_width": self.half_width}


@dataclass(frozen=True, slots=True)
class Fibonacci(_SemanticValue):
    start: Anchor
    end: Anchor
    direction: Direction
    mode: FibonacciMode
    ratios: tuple[str, ...]
    KIND: ClassVar[str] = "FIBONACCI"

    def __post_init__(self) -> None:
        _anchors(self.start, self.end)
        if type(self.direction) is not Direction or type(self.mode) is not FibonacciMode:
            raise GeometryError("Fibonacci direction and mode must be explicit")
        movement = _decimal(self.end.price) - _decimal(self.start.price)
        if movement == 0 or (movement > 0) != (self.direction is Direction.UP):
            raise GeometryError("Fibonacci direction must match distinct anchor prices")
        if type(self.ratios) is not tuple or not 1 <= len(self.ratios) <= MAX_RATIOS:
            raise GeometryError("Fibonacci needs 1 through 32 immutable ordered ratios")
        ratios = tuple(_decimal(r) for r in self.ratios)
        if len(set(ratios)) != len(ratios):
            raise GeometryError("Fibonacci ratios must be unique")
        if self.mode is FibonacciMode.RETRACEMENT and any(not 0 <= r <= 1 for r in ratios):
            raise GeometryError("retracement ratios must be in [0, 1]")
        if self.mode is FibonacciMode.EXTENSION and any(r < 1 for r in ratios):
            raise GeometryError("extension ratios must be at least 1")

    @property
    def levels(self) -> tuple[Fraction, ...]:
        start, end = _decimal(self.start.price), _decimal(self.end.price)
        movement = end - start
        if self.mode is FibonacciMode.RETRACEMENT:
            return tuple(end - _decimal(r) * movement for r in self.ratios)
        return tuple(start + _decimal(r) * movement for r in self.ratios)

    def at(self, event: datetime) -> tuple[Fraction, ...]:
        _utc(event)
        return self.levels

    def to_dict(self) -> dict:
        return {"schema": GEOMETRY_SCHEMA, "kind": self.KIND, "start": self.start.to_dict(),
                "end": self.end.to_dict(), "direction": self.direction.value, "mode": self.mode.value,
                "ratios": list(self.ratios), "levels": [_rational(p) for p in self.levels]}


Geometry = Level | Zone | Line | Channel | Fibonacci


@dataclass(frozen=True, slots=True)
class CausalApplicability(_SemanticValue):
    known_at: datetime
    locked_at: datetime
    effective_from: datetime
    effective_to: datetime | None = None

    def __post_init__(self) -> None:
        for name in ("known_at", "locked_at", "effective_from"):
            object.__setattr__(self, name, _utc(getattr(self, name)))
        if self.effective_to is not None:
            object.__setattr__(self, "effective_to", _utc(self.effective_to))
        if not self.known_at <= self.locked_at <= self.effective_from:
            raise GeometryError("require known_at <= locked_at <= effective_from")
        if self.effective_to is not None and self.effective_to <= self.effective_from:
            raise GeometryError("expiry must be strictly after effective_from")

    def is_applicable(self, event: datetime, as_of: datetime) -> bool:
        event, as_of = _utc(event), _utc(as_of)
        return (as_of >= event and as_of >= self.locked_at
                and event > self.locked_at and event >= self.effective_from
                and (self.effective_to is None or event < self.effective_to))

    def to_dict(self) -> dict:
        return {"schema": APPLICABILITY_SCHEMA, "known_at": _time_text(self.known_at),
                "locked_at": _time_text(self.locked_at), "effective_from": _time_text(self.effective_from),
                "effective_to": _time_text(self.effective_to) if self.effective_to is not None else None}


def _closed(document: object, fields: set[str]) -> dict:
    if type(document) is not dict or document.keys() != fields:
        raise GeometryError("semantic object has missing or unknown fields")
    return document


def _pairs(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise GeometryError("duplicate semantic JSON key")
        result[key] = value
    return result


def _reject_number(value: str) -> None:
    raise GeometryError("semantic numbers must be exact strings")


def _load(payload: str | bytes) -> dict:
    if type(payload) not in (str, bytes) or len(payload) > MAX_PAYLOAD_BYTES:
        raise GeometryError("semantic payload must be bounded JSON text or bytes")
    try:
        raw = payload.encode("utf-8") if type(payload) is str else payload
        if len(raw) > MAX_PAYLOAD_BYTES:
            raise GeometryError("semantic payload exceeds 64 KiB")
        document = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                              parse_float=_reject_number, parse_int=_reject_number,
                              parse_constant=_reject_number)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise GeometryError("invalid closed semantic JSON") from exc
    if type(document) is not dict:
        raise GeometryError("semantic payload must be an object")
    return document


def _read_anchor(document: object) -> Anchor:
    document = _closed(document, {"time", "price"})
    return Anchor(_read_time(document["time"]), document["price"])


def _enum(enum_type: type[Enum], value: object) -> Enum:
    if type(value) is not str:
        raise GeometryError("semantic enum must be a string")
    try:
        return enum_type(value)
    except ValueError as exc:
        raise GeometryError("unknown semantic enum") from exc


def _read_geometry(document: object, *, line_only: bool = False) -> Geometry:
    if type(document) is not dict or document.get("schema") != GEOMETRY_SCHEMA:
        raise GeometryError("unknown geometry schema")
    kind = document.get("kind")
    if type(kind) is not str or (line_only and kind != "LINE"):
        raise GeometryError("inconsistent geometry kind")
    common = {"schema", "kind"}
    if kind == "LEVEL":
        _closed(document, common | {"price"})
        value = Level(document["price"])
    elif kind == "ZONE":
        _closed(document, common | {"lower", "upper"})
        value = Zone(document["lower"], document["upper"])
    elif kind == "LINE":
        _closed(document, common | {"start", "end", "extension", "slope_per_microsecond"})
        value = Line(_read_anchor(document["start"]), _read_anchor(document["end"]),
                     _enum(Extension, document["extension"]))
        if document["slope_per_microsecond"] != _rational(value.slope_per_microsecond):
            raise GeometryError("serialized slope disagrees with exact anchors")
    elif kind == "CHANNEL":
        _closed(document, common | {"center", "half_width"})
        value = Channel(_read_geometry(document["center"], line_only=True), document["half_width"])
    elif kind == "FIBONACCI":
        _closed(document, common | {"start", "end", "direction", "mode", "ratios", "levels"})
        ratios = document["ratios"]
        if type(ratios) is not list or not 1 <= len(ratios) <= MAX_RATIOS:
            raise GeometryError("Fibonacci needs 1 through 32 ratios")
        value = Fibonacci(_read_anchor(document["start"]), _read_anchor(document["end"]),
                          _enum(Direction, document["direction"]), _enum(FibonacciMode, document["mode"]), tuple(ratios))
        if document["levels"] != [_rational(p) for p in value.levels]:
            raise GeometryError("serialized Fibonacci levels disagree with exact anchors/ratios")
    else:
        raise GeometryError("unknown geometry kind")
    value.canonical_bytes  # Enforce the canonical bound after normalization too.
    return value


def decode_geometry(payload: str | bytes) -> Geometry:
    """Decode a closed document, verifying every serialized derived value."""
    return _read_geometry(_load(payload))


def decode_applicability(payload: str | bytes) -> CausalApplicability:
    document = _closed(_load(payload), {"schema", "known_at", "locked_at", "effective_from", "effective_to"})
    if document["schema"] != APPLICABILITY_SCHEMA:
        raise GeometryError("unknown applicability schema")
    return CausalApplicability(_read_time(document["known_at"]), _read_time(document["locked_at"]),
                               _read_time(document["effective_from"]),
                               _read_time(document["effective_to"]) if document["effective_to"] is not None else None)
