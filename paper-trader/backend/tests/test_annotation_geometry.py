"""Exact normalized geometry and causal boundaries, not chart/provider parity."""
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext
from fractions import Fraction
import json

import pytest

from app.chart.annotation_geometry import (
    Anchor, CausalApplicability, Channel, Direction, Extension, Fibonacci,
    FibonacciMode, GeometryError, Level, Line, PriceBand, Unavailable, Zone,
    decode_applicability, decode_geometry,
)
from app.ir.hashing import canonical_json, content_address

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def t(microseconds):
    return T0 + timedelta(microseconds=microseconds)


def line(extension=Extension.BOTH):
    return Line(Anchor(t(0), "1"), Anchor(t(3), "2"), extension)


def fib(direction=Direction.UP, mode=FibonacciMode.RETRACEMENT, ratios=None):
    start, end = ("100", "140") if direction is Direction.UP else ("140", "100")
    if ratios is None:
        ratios = ("0", "0.25", "0.618", "1") if mode is FibonacciMode.RETRACEMENT else ("1", "1.5", "2.618")
    return Fibonacci(Anchor(t(0), start), Anchor(t(3), end), direction, mode, ratios)


def test_level_zone_and_inclusive_endpoints():
    assert Level("12.5").at(t(0)) == Fraction(25, 2)
    band = Zone("-2.5", "3.25").at(t(0))
    assert band == PriceBand(Fraction(-5, 2), Fraction(13, 4))
    assert band.contains("-2.5") and band.contains("3.25") and band.contains("0")
    assert not band.contains("-2.50001") and not band.contains("3.25001")
    assert Zone("0", "0").at(t(0)).contains("0")


@pytest.mark.parametrize("extension", list(Extension))
def test_line_exact_slope_and_extension(extension):
    value = line(extension)
    assert value.slope_per_microsecond == Fraction(1, 3)
    assert value.at(t(0)) == 1
    assert value.at(t(1)) == Fraction(4, 3)
    assert value.at(t(3)) == 2
    expected_before = Fraction(2, 3) if extension is Extension.BOTH else Unavailable.OUTSIDE_GEOMETRY
    expected_after = Unavailable.OUTSIDE_GEOMETRY if extension is Extension.SEGMENT else Fraction(3)
    assert value.at(t(-1)) == expected_before
    assert value.at(t(6)) == expected_after


def test_descending_flat_and_day_boundary_lines():
    descending = Line(Anchor(t(0), "10"), Anchor(t(4), "2"), Extension.BOTH)
    assert descending.at(t(1)) == 8 and descending.at(t(5)) == 0
    flat = Line(Anchor(t(0), "0"), Anchor(t(4), "0"), Extension.RIGHT_RAY)
    assert flat.at(t(1)) == 0 and flat.at(t(999)) == 0
    day = timedelta(days=1)
    spanning = Line(Anchor(T0 - day, "0"), Anchor(T0 + day, "2"), Extension.BOTH)
    assert spanning.at(T0) == 1
    assert spanning.at(T0 - day - timedelta(microseconds=1)) == Fraction(-1, 86_400_000_000)


def test_channel_tracks_exact_center_and_extension():
    value = Channel(line(), "0.25")
    assert value.at(t(1)) == PriceBand(Fraction(13, 12), Fraction(19, 12))
    assert value.at(t(6)) == PriceBand(Fraction(11, 4), Fraction(13, 4))
    assert Channel(line(), "0").at(t(1)) == PriceBand(Fraction(4, 3), Fraction(4, 3))
    assert Channel(line(Extension.SEGMENT), "0.25").at(t(4)) is Unavailable.OUTSIDE_GEOMETRY


@pytest.mark.parametrize(("direction", "mode", "expected"), [
    (Direction.UP, FibonacciMode.RETRACEMENT, (140, 130, Fraction(2882, 25), 100)),
    (Direction.DOWN, FibonacciMode.RETRACEMENT, (100, 110, Fraction(3118, 25), 140)),
    (Direction.UP, FibonacciMode.EXTENSION, (140, 160, Fraction(5118, 25))),
    (Direction.DOWN, FibonacciMode.EXTENSION, (100, 80, Fraction(882, 25))),
])
def test_fibonacci_independent_exact_vectors(direction, mode, expected):
    value = fib(direction, mode)
    assert value.levels == expected
    assert value.at(t(-100)) == expected  # Coordinates do not establish causal permission.
    assert decode_geometry(value.canonical_bytes).levels == expected


def test_declared_ratio_order_is_semantic_without_hidden_defaults():
    normal = fib(ratios=("0", "0.25", "1"))
    reordered = fib(ratios=("1", "0", "0.25"))
    assert reordered.levels == (100, 140, 130)
    assert normal.address != reordered.address
    assert fib(ratios=("0.25",)).levels == (130,)


def test_exact_arithmetic_is_independent_of_decimal_context():
    price = "123456789012345678901234567890.123456789"
    with localcontext() as ctx:
        ctx.prec = 4
        value = Level(price)
        assert value.at(t(0)) == Fraction(123456789012345678901234567890123456789, 10**9)
        assert decode_geometry(value.canonical_bytes) == value
        assert line().at(t(1)) == Fraction(4, 3)
    with localcontext() as ctx:
        ctx.prec = 50
        independently_calculated = Decimal("140") - Decimal("0.618") * Decimal("40")
    assert fib().levels[2] == Fraction(independently_calculated)


@pytest.mark.parametrize("value", [Level("0"), Zone("0", "0"), line(), Channel(line(), "0.25"), fib()])
def test_immutable_closed_roundtrip_uses_existing_hash(value):
    wire = value.to_dict()
    assert value.canonical_bytes == canonical_json(wire).encode()
    assert value.address == content_address(wire)
    assert decode_geometry(value.canonical_bytes) == value
    assert decode_geometry(json.dumps(wire, indent=2)).address == value.address
    wire["presentation"] = {"color": "red"}
    assert "presentation" not in value.to_dict()
    with pytest.raises(GeometryError):
        decode_geometry(json.dumps(wire))
    field = next(iter(value.__dataclass_fields__))
    with pytest.raises(FrozenInstanceError):
        setattr(value, field, None)
    assert not hasattr(value, "__dict__")


def test_nested_values_are_frozen_and_serialization_detached():
    value = fib()
    with pytest.raises(FrozenInstanceError):
        value.start.price = "50"
    wire = value.to_dict()
    wire["start"]["price"] = "50"
    wire["ratios"][0] = "0.5"
    wire["levels"][0]["numerator"] = "0"
    assert value.start.price == "100" and value.ratios[0] == "0" and value.levels[0] == 140


def test_utc_equivalence_precision_and_semantic_identity():
    offset = timezone(timedelta(hours=5, minutes=30))
    equivalent = Line(Anchor(t(0).astimezone(offset), "1"), Anchor(t(3).astimezone(offset), "2"), Extension.BOTH)
    assert equivalent == line() and equivalent.address == line().address
    wire = line().to_dict()
    wire["start"]["time"] = "2026-01-01T05:30:00+05:30"
    wire["end"]["time"] = "2026-01-01T05:30:00.000003+05:30"
    assert decode_geometry(json.dumps(wire)).address == line().address
    assert line().start.to_dict()["time"] == "2026-01-01T00:00:00.000000+00:00"
    assert replace(line(), end=Anchor(t(4), "2")).address != line().address
    assert replace(line(), extension=Extension.RIGHT_RAY).address != line().address
    assert Level("1").address != Zone("1", "1").address
    assert Channel(line(), "0").address != Channel(line(), "1").address


@pytest.mark.parametrize("bad", [True, False, 1, 1.0, Decimal("1"), Fraction(1), None,
                                   "", "NaN", "Infinity", "-Infinity", "1e3", "+1", " 1", "1 ",
                                   "01", "1.0", "-0", "-0.0", ".5", "1.", "１", "1\n", "9" * 129])
def test_decimal_inputs_reject_ambiguity_and_unbounded_values(bad):
    with pytest.raises(GeometryError):
        Level(bad)


@pytest.mark.parametrize("factory", [
    lambda: Zone("2", "1"), lambda: Channel(line(), "-0.1"),
    lambda: Channel(Level("1"), "1"), lambda: PriceBand(Fraction(2), Fraction(1)),
    lambda: PriceBand(1, 2), lambda: Anchor(T0.replace(tzinfo=None), "1"),
    lambda: Line(Anchor(t(0), "1"), Anchor(t(0), "2"), Extension.BOTH),
    lambda: Line(Anchor(t(1), "1"), Anchor(t(0), "2"), Extension.BOTH),
    lambda: Line({"time": T0, "price": "1"}, Anchor(t(1), "2"), Extension.BOTH),
    lambda: replace(line(), extension="BOTH"),
    lambda: replace(fib(), end=Anchor(t(0), "140")),
    lambda: replace(fib(), end=Anchor(t(3), "100")),
    lambda: replace(fib(), direction=Direction.DOWN),
    lambda: replace(fib(), direction="UP"), lambda: replace(fib(), mode="RETRACEMENT"),
    lambda: fib(ratios=[]), lambda: fib(ratios=()), lambda: fib(ratios=("0", "0")),
    lambda: fib(ratios=("-0.1",)), lambda: fib(ratios=("1.01",)),
    lambda: fib(mode=FibonacciMode.EXTENSION, ratios=("0.99",)),
    lambda: fib(ratios=tuple(str(i) for i in range(33))),
    lambda: fib(ratios=(True,)), lambda: fib(ratios=("9" * 129,)),
])
def test_constructor_rejections(factory):
    with pytest.raises(GeometryError):
        factory()


@pytest.mark.parametrize("bad_time", ["2026-01-01", "2026-01-01T00:00:00", "2026-01-01T00:00:00.0000001Z",
                                      "2026-01-01T00:00:00+00:60", "2026-01-01T00:00:00+24:00",
                                      "2026-02-30T00:00:00Z", "0001-01-01T00:00:00+01:00", None, True])
def test_timestamp_decoder_refuses_truncation_and_invalid_instants(bad_time):
    wire = line().to_dict()
    wire["start"]["time"] = bad_time
    with pytest.raises(GeometryError):
        decode_geometry(json.dumps(wire))


@pytest.mark.parametrize("mutation", [
    lambda w: w.update(schema="normalized-annotation-geometry/2"),
    lambda w: w.update(kind="SPLINE"), lambda w: w.update(kind=[]),
    lambda w: w.update(color="red"), lambda w: w.update(owner="someone"),
    lambda w: w.pop("extension"), lambda w: w.update(extension="AUTO"),
    lambda w: w["start"].update(title="hidden presentation"),
    lambda w: w["slope_per_microsecond"].update(numerator="2"),
    lambda w: w["slope_per_microsecond"].update(numerator="2", denominator="6"),
    lambda w: w["slope_per_microsecond"].update(unit="seconds"),
    lambda w: w["start"].update(price="1.1"),
])
def test_decoder_rejects_unknown_fields_and_unverified_equations(mutation):
    wire = line().to_dict()
    mutation(wire)
    with pytest.raises(GeometryError):
        decode_geometry(json.dumps(wire))


def test_decoder_checks_fibonacci_derived_prices_and_channel_dimensions():
    wire = fib().to_dict()
    wire["levels"][0]["numerator"] = "141"
    with pytest.raises(GeometryError):
        decode_geometry(json.dumps(wire))
    wire = fib().to_dict()
    wire["ratios"] = list(reversed(wire["ratios"]))
    with pytest.raises(GeometryError):
        decode_geometry(json.dumps(wire))
    wire = Channel(line(), "1").to_dict()
    wire["center"] = Level("1").to_dict()
    with pytest.raises(GeometryError):
        decode_geometry(json.dumps(wire))
    wire["center"] = wire.copy()  # Reject nested channel before recursing further.
    wire["center"]["center"] = Level("1").to_dict()
    with pytest.raises(GeometryError):
        decode_geometry(json.dumps(wire))


@pytest.mark.parametrize("payload", [b"\xff", "[]", "null", "{}", "{", '{"kind":"LEVEL","kind":"ZONE"}',
                                     '{"price":1}', '{"price":1.2}', '{"price":NaN}',
                                     "[" * 2000 + "]" * 2000, "\ud800", b" " * 65537])
def test_decoder_rejects_malformed_duplicate_and_oversized_json(payload):
    with pytest.raises(GeometryError):
        decode_geometry(payload)


def test_maximum_decimal_ratio_and_payload_bounds():
    huge = "9" * 128
    assert Level(huge).at(t(0)) == 10**128 - 1
    tiny = "0." + "0" * 125 + "1"
    assert Level(tiny).at(t(0)) == Fraction(1, 10**126)
    ratios = tuple(str(10**127 + i) for i in range(32))
    value = Fibonacci(Anchor(t(0), "-" + "9" * 127), Anchor(t(1), huge), Direction.UP, FibonacciMode.EXTENSION, ratios)
    assert len(value.levels) == 32
    assert value.levels[0] == -(10**127 - 1) + 10**127 * (11 * 10**127 - 2)
    assert decode_geometry(value.canonical_bytes) == value
    assert len(value.canonical_bytes) < 65536
    wire = Level("0").canonical_bytes
    assert decode_geometry(wire + b" " * (65536 - len(wire))) == Level("0")
    with pytest.raises(GeometryError):
        decode_geometry(wire + b" " * (65537 - len(wire)))


def test_full_datetime_range_uses_integer_differences():
    start = datetime.min.replace(tzinfo=timezone.utc)
    end = datetime.max.replace(tzinfo=timezone.utc)
    value = Line(Anchor(start, "0"), Anchor(end, "1"), Extension.SEGMENT)
    assert value.slope_per_microsecond == Fraction(1, 315537897599999999)
    assert value.at(start + timedelta(microseconds=1)) == Fraction(1, 315537897599999999)
    assert value.at(end) == 1
    with pytest.raises(GeometryError):
        Anchor(datetime.min.replace(tzinfo=timezone(timedelta(hours=1))), "0")


def test_causal_boundaries_and_as_of_guard():
    value = CausalApplicability(t(0), t(2), t(3), t(5))
    expected = {
        (0, 10): False, (1, 10): False, (2, 10): False,
        (3, 2): False, (3, 3): True, (3, 10): True,
        (4, 3): False, (4, 4): True, (5, 5): False, (6, 10): False,
    }
    for (event, as_of), result in expected.items():
        assert value.is_applicable(t(event), t(as_of)) is result


def test_causal_lock_equality_is_unavailable_even_if_effective():
    value = CausalApplicability(t(0), t(2), t(2))
    assert value.is_applicable(t(2), t(2)) is False
    assert value.is_applicable(t(2), t(20)) is False
    assert value.is_applicable(t(3), t(3)) is True
    assert value.is_applicable(t(3), t(1)) is False


def test_future_append_cannot_change_earlier_applicability():
    original = CausalApplicability(t(0), t(2), t(3))
    later = CausalApplicability(t(10), t(12), t(13))
    events = [t(i) for i in range(10)]
    before = [tuple(v.address for v in [original] if v.is_applicable(e, e)) for e in events]
    after = [tuple(v.address for v in [original, later] if v.is_applicable(e, e)) for e in events]
    assert before == after
    assert not any(later.is_applicable(e, t(100)) for e in events)


@pytest.mark.parametrize("args", [(t(2), t(1), t(3)), (t(0), t(3), t(2)),
                                  (t(0), t(1), t(2), t(2)), (t(0), t(1), t(2), t(1)),
                                  (T0.replace(tzinfo=None), t(1), t(2))])
def test_causal_invalid_ordering_and_naive_values(args):
    with pytest.raises(GeometryError):
        CausalApplicability(*args)


def test_causal_roundtrip_utc_identity_and_unknown_field_rejection():
    value = CausalApplicability(t(0), t(2), t(3), t(5))
    assert decode_applicability(value.canonical_bytes) == value
    assert value.address == content_address(value.to_dict())
    assert decode_applicability(CausalApplicability(t(0), t(0), t(0)).canonical_bytes).effective_to is None
    offset = timezone(timedelta(hours=-4))
    assert CausalApplicability(*(x.astimezone(offset) for x in (t(0), t(2), t(3), t(5)))).address == value.address
    assert replace(value, locked_at=t(1)).address != value.address
    with pytest.raises(FrozenInstanceError):
        value.locked_at = t(1)
    for key, bad in (("schema", "other"), ("style", "red"), ("effective_to", "2026-01-01")):
        wire = value.to_dict()
        wire[key] = bad
        with pytest.raises(GeometryError):
            decode_applicability(json.dumps(wire))
    for event, as_of in ((T0.replace(tzinfo=None), t(3)), (t(3), T0.replace(tzinfo=None))):
        with pytest.raises(GeometryError):
            value.is_applicable(event, as_of)


def test_exact_generated_linear_grid_against_independent_interpolation():
    # Bounded analytic sweep: direct barycentric equation, not the implementation's slope.
    for p0, p1 in (("-2.25", "7.125"), ("0", "0"), ("12345678901234567890", "-0.001")):
        for duration in (1, 3, 11, 86400000001):
            value = Line(Anchor(t(0), p0), Anchor(t(duration), p1), Extension.BOTH)
            for event in (-1, 0, 1, duration, duration + 1):
                expected = (Fraction(p0) * (duration - event) + Fraction(p1) * event) / duration
                assert value.at(t(event)) == expected
