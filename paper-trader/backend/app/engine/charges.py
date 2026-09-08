"""Versioned, fail-closed brokerage and statutory charge calculations.

``zerodha_charges_v1`` reconstructs the historical Strategy OS calculation for
known segments. Existing runner callers remain on that version so this research
correction cannot silently change live accounting. Unknown segments no longer
inherit NFO under any mode.

Corrected research and simulated-Paper results select
``zerodha_resident_individual_standard_charges_v2`` explicitly. Its authoritative
outputs are integer paise. Rupee floats returned by :func:`compute_charges` are
compatibility projections made only after exact minor-unit closure.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from decimal import Decimal, DecimalException, ROUND_HALF_UP
from types import MappingProxyType
from typing import Any, Mapping, Sequence


ZERODHA_CHARGES_V1 = "zerodha_charges_v1"
ZERODHA_CHARGES_V2 = "zerodha_resident_individual_standard_charges_v2"
DEFAULT_RUNTIME_CHARGE_SCHEDULE = ZERODHA_CHARGES_V1
CORRECTED_RESEARCH_CHARGE_SCHEDULE = ZERODHA_CHARGES_V2
ROUNDING_POLICY_V2 = "price_paise_half_up__stt_rupee_half_up__components_paise_half_up__sum_minor_v2"
APPLICATION_MODE_V2 = "current_public_schedule_counterfactual_as_of_2026_08_29"
MAX_TURNOVER_MINOR = 100_000_000_000_000  # ₹1 trillion per leg.
CHARGE_COMPONENTS = (
    "brokerage", "stt_ctt", "exchange_txn", "sebi", "stamp", "dp", "gst"
)


class ChargeScheduleRefusal(ValueError):
    """Typed refusal raised before a charge answer can affect a result or fill."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class SegmentRate:
    product_class: str
    turnover_unit: str = "price_minor_times_quantity"
    brokerage_flat_minor: int = 0
    brokerage_rate: str = "0"
    brokerage_cap_minor: int | None = None
    exchange_rate: str = "0"
    tax_buy_rate: str = "0"
    tax_sell_rate: str = "0"
    stamp_buy_rate: str = "0"
    sebi_rate: str = "0.000001"
    dp_sell_base_minor: int = 0
    gst_rate: str = "0.18"
    supported_sides: tuple[str, str] = ("BUY", "SELL")


# Historical bytes expressed as read-only mappings. Rates and binary-float
# rounding deliberately match the old implementation for known segments.
_legacy_v1_values: dict[str, dict[str, float]] = {
    "NFO": {"brokerage_flat": 20.0, "txn_pct": 0.0003503, "tax_sell_pct": 0.001,
            "stamp_buy_pct": 0.00003, "sebi_pct": 1e-6, "gst_pct": 0.18},
    "BFO": {"brokerage_flat": 20.0, "txn_pct": 0.000325, "tax_sell_pct": 0.001,
            "stamp_buy_pct": 0.00003, "sebi_pct": 1e-6, "gst_pct": 0.18},
    "MCX": {"brokerage_flat": 20.0, "txn_pct": 0.0005, "tax_sell_pct": 0.0005,
            "stamp_buy_pct": 0.00003, "sebi_pct": 1e-6, "gst_pct": 0.18},
    "NCDEX": {"brokerage_flat": 20.0, "txn_pct": 0.00006, "tax_sell_pct": 0.0,
              "stamp_buy_pct": 0.00002, "sebi_pct": 1e-6, "gst_pct": 0.18},
    "NSE_EQ": {"brokerage_flat": 0.0, "txn_pct": 0.0000297,
               "tax_buy_pct": 0.001, "tax_sell_pct": 0.001,
               "stamp_buy_pct": 0.00015, "sebi_pct": 1e-6,
               "dp_sell_flat": 13.5, "gst_pct": 0.18},
    "BSE_EQ": {"brokerage_flat": 0.0, "txn_pct": 0.0000375,
               "tax_buy_pct": 0.001, "tax_sell_pct": 0.001,
               "stamp_buy_pct": 0.00015, "sebi_pct": 1e-6,
               "dp_sell_flat": 13.5, "gst_pct": 0.18},
    "NFO_FUT": {"brokerage_pct": 0.0003, "brokerage_cap": 20.0,
                "txn_pct": 0.0000173, "tax_sell_pct": 0.0002,
                "stamp_buy_pct": 0.00002, "sebi_pct": 1e-6, "gst_pct": 0.18},
    "BFO_FUT": {"brokerage_pct": 0.0003, "brokerage_cap": 20.0,
                "txn_pct": 0.0000173, "tax_sell_pct": 0.0002,
                "stamp_buy_pct": 0.00002, "sebi_pct": 1e-6, "gst_pct": 0.18},
    "MCX_FUT": {"brokerage_pct": 0.0003, "brokerage_cap": 20.0,
                "txn_pct": 0.000021, "tax_sell_pct": 0.0001,
                "stamp_buy_pct": 0.00002, "sebi_pct": 1e-6, "gst_pct": 0.18},
    "NCDEX_FUT": {"brokerage_pct": 0.0003, "brokerage_cap": 20.0,
                  "txn_pct": 0.00006, "tax_sell_pct": 0.0,
                  "stamp_buy_pct": 0.00002, "sebi_pct": 1e-6, "gst_pct": 0.18},
    "NSE_INTRADAY": {"brokerage_pct": 0.0003, "brokerage_cap": 20.0,
                     "txn_pct": 0.0000297, "tax_sell_pct": 0.00025,
                     "stamp_buy_pct": 0.00003, "sebi_pct": 1e-6, "gst_pct": 0.18},
    "BSE_INTRADAY": {"brokerage_pct": 0.0003, "brokerage_cap": 20.0,
                     "txn_pct": 0.0000375, "tax_sell_pct": 0.00025,
                     "stamp_buy_pct": 0.00003, "sebi_pct": 1e-6, "gst_pct": 0.18},
}
_LEGACY_V1: Mapping[str, Mapping[str, float]] = MappingProxyType({
    segment: MappingProxyType(dict(values))
    for segment, values in _legacy_v1_values.items()
})
del _legacy_v1_values
CHARGE_SCHEDULE = _LEGACY_V1


_V2_SEGMENTS: Mapping[str, SegmentRate] = MappingProxyType({
    "NFO": SegmentRate(
        product_class="equity_option_premium", brokerage_flat_minor=2_000,
        exchange_rate="0.0003553", tax_sell_rate="0.0015",
        stamp_buy_rate="0.00003"),
    "BFO": SegmentRate(
        product_class="bse_index_option_premium", brokerage_flat_minor=2_000,
        exchange_rate="0.000325", tax_sell_rate="0.0015",
        stamp_buy_rate="0.00003"),
    "NSE_EQ": SegmentRate(
        product_class="equity_delivery_standard_resident_individual",
        exchange_rate="0.0000307", tax_buy_rate="0.001",
        tax_sell_rate="0.001", stamp_buy_rate="0.00015",
        dp_sell_base_minor=1_300),
    "BSE_EQ": SegmentRate(
        product_class="equity_delivery_standard_resident_individual",
        exchange_rate="0.0000375", tax_buy_rate="0.001",
        tax_sell_rate="0.001", stamp_buy_rate="0.00015",
        dp_sell_base_minor=1_300),
    "NFO_FUT": SegmentRate(
        product_class="equity_future_price", brokerage_rate="0.0003",
        brokerage_cap_minor=2_000, exchange_rate="0.0000183",
        tax_sell_rate="0.0005", stamp_buy_rate="0.00002"),
})

_UNVERIFIED_V2 = MappingProxyType({
    "BFO_FUT": "independent official BSE futures transaction-rate evidence is unavailable",
    "NSE_INTRADAY": "published average-price round-trip STT semantics are unresolved",
    "BSE_INTRADAY": "published average-price round-trip STT semantics are unresolved",
    "MCX": "linked MCX transaction-charge circular returned HTTP 403",
    "MCX_FUT": "linked MCX transaction-charge circular returned HTTP 403",
    "NCDEX": "absent from Zerodha current public charge schedule",
    "NCDEX_FUT": "absent from Zerodha current public charge schedule",
})

_SOURCE_REFS: tuple[tuple[str, str], ...] = (
    ("ZERODHA_CURRENT_CHARGES_2026_08_29",
     "90e6916b1fd2124d1e252e128d91b91207641087340085244f041b17fd39c1bd"),
    ("ZERODHA_STT_ROUNDING_2026",
     "2d5fda58be7bdedd949df1795ef34caf5ea3cbb7dd2a5d6ef282844b8365f935"),
    ("NSE_STT_CIRCULAR_02_2026",
     "f4cbd1f917f88dcb9d59b95e0e9ef8bbb98017edbbdd16669a3d40776416a9f6"),
    ("NSE_TRANSACTION_CIRCULAR_05_2024",
     "85b816208f33bdd1c6c0d827b1ba996aba1fe08fe883a6d31c6a2c0ad55304a4"),
    ("NSE_CURRENT_LEVIES_2026_04_17",
     "46eaa0f8aa0f5037613c49c85e200a1ee42a0fe41a287091f568ae89928ef3e6"),
    ("SEBI_TRUE_TO_LABEL_2024",
     "99019f16ea1ff449e1c42d3177ea2fa9e66c81e4a02d028079c8078bce2bba11"),
    ("BSE_AUTHORED_TRUE_TO_LABEL_DISCLOSURE_2024",
     "1a01b33fa91a7d320cc2dcfb74760286d8fec24a9c5641be0d5948ac9775df95"),
)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _schedule_payload(schedule_id: str) -> dict[str, Any]:
    if schedule_id == ZERODHA_CHARGES_V1:
        return {
            "id": schedule_id,
            "status": "legacy_historical_reconstruction_only",
            "effective_contract": "historical code schedule; no current-rate claim",
            "rounding_policy": {
                "id": "legacy_binary_float_python_round_v1",
                "public_result": "two-decimal binary-float projection",
            },
            "segments": {
                key: {name: repr(value) for name, value in sorted(values.items())}
                for key, values in sorted(_LEGACY_V1.items())
            },
        }
    if schedule_id == ZERODHA_CHARGES_V2:
        return {
            "id": schedule_id,
            "status": "verified_public_simulation_profile",
            "retrieved_at_utc": "2026-08-29T18:15:47Z",
            "effective_from": "2026-04-01",
            "profile": "Zerodha resident individual standard published rates; no cohort discount",
            "application_mode": APPLICATION_MODE_V2,
            "rounding_policy": {
                "id": ROUNDING_POLICY_V2,
                "price": "nearest paise, ROUND_HALF_UP, before turnover",
                "stt_ctt": "nearest whole rupee, ROUND_HALF_UP",
                "other_components": "nearest paise, ROUND_HALF_UP, each component",
                "gst": "18% of rounded brokerage + exchange + SEBI + DP base; nearest paise, ROUND_HALF_UP",
                "aggregate": "integer-paise sum",
            },
            "sources": [
                {"id": source_id, "sha256": sha256}
                for source_id, sha256 in _SOURCE_REFS
            ],
            "segments": {
                key: {**asdict(value), "supported_sides": list(value.supported_sides)}
                for key, value in sorted(_V2_SEGMENTS.items())
            },
            "refused_segments": dict(sorted(_UNVERIFIED_V2.items())),
            "nonclaims": [
                "private contract-note equality",
                "cohort-discounted DP or brokerage rates",
                "exercised or physically settled options",
                "live authority",
            ],
        }
    raise ChargeScheduleRefusal(
        "CHARGE_SCHEDULE_UNKNOWN", f"unknown charge schedule {schedule_id!r}"
    )


def charge_schedule_address(schedule_id: str) -> str:
    payload = _schedule_payload(schedule_id)
    return "sha256:" + hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def charge_schedule_document(schedule_id: str) -> dict[str, Any]:
    """Return a detached canonical document with its content address."""
    payload = _schedule_payload(schedule_id)
    return json.loads(_canonical_json({**payload, "address": charge_schedule_address(schedule_id)}))


def _require_side(side: Any) -> str:
    if side not in ("BUY", "SELL"):
        raise ChargeScheduleRefusal(
            "CHARGE_SIDE_INVALID", "charge side must be exactly BUY or SELL"
        )
    return side


def _require_qty(qty: Any) -> int:
    if type(qty) is not int or qty <= 0 or qty > 1_000_000_000:
        raise ChargeScheduleRefusal(
            "CHARGE_QUANTITY_INVALID", "charge quantity must be a positive bounded integer"
        )
    return qty


def _price_minor(price: Any) -> int:
    if isinstance(price, bool):
        raise ChargeScheduleRefusal("CHARGE_PRICE_INVALID", "charge price must be finite and positive")
    try:
        value = Decimal(str(price))
    except (DecimalException, TypeError, ValueError):
        raise ChargeScheduleRefusal(
            "CHARGE_PRICE_INVALID", "charge price must be finite and positive"
        ) from None
    if not value.is_finite() or value <= 0:
        raise ChargeScheduleRefusal(
            "CHARGE_PRICE_INVALID", "charge price must be finite and positive"
        )
    if value > Decimal(MAX_TURNOVER_MINOR) / 100:
        raise ChargeScheduleRefusal(
            "CHARGE_TURNOVER_EXCESSIVE", "charge turnover exceeds the supported bound"
        )
    try:
        return int((value * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except DecimalException:
        raise ChargeScheduleRefusal(
            "CHARGE_TURNOVER_EXCESSIVE", "charge turnover exceeds the supported bound"
        ) from None


def monetary_minor(value: Any) -> int:
    """Convert a closed non-negative rupee amount to integer paise."""
    if isinstance(value, bool):
        raise ChargeScheduleRefusal(
            "CHARGE_MONEY_INVALID", "charge money must be finite and non-negative"
        )
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount < 0:
            raise ChargeScheduleRefusal(
                "CHARGE_MONEY_INVALID", "charge money must be finite and non-negative"
            )
        if amount > Decimal(MAX_TURNOVER_MINOR) / 100:
            raise ChargeScheduleRefusal(
                "CHARGE_TURNOVER_EXCESSIVE", "charge money exceeds the supported bound"
            )
        return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except ChargeScheduleRefusal:
        raise
    except (DecimalException, TypeError, ValueError):
        raise ChargeScheduleRefusal(
            "CHARGE_MONEY_INVALID", "charge money must be finite and non-negative"
        ) from None


def _require_turnover(price_minor: int, qty: int) -> int:
    turnover_minor = price_minor * qty
    if turnover_minor <= 0:
        raise ChargeScheduleRefusal(
            "CHARGE_TURNOVER_INVALID", "charge turnover must be positive"
        )
    if turnover_minor > MAX_TURNOVER_MINOR:
        raise ChargeScheduleRefusal(
            "CHARGE_TURNOVER_EXCESSIVE", "charge turnover exceeds the supported bound"
        )
    return turnover_minor


def _round_paise(value_rupees: Decimal) -> int:
    return int((value_rupees * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _round_rupee_minor(value_rupees: Decimal) -> int:
    return int(value_rupees.quantize(Decimal("1"), rounding=ROUND_HALF_UP)) * 100


def _v2_rate(segment: Any) -> SegmentRate:
    if not isinstance(segment, str) or segment not in _V2_SEGMENTS:
        if isinstance(segment, str) and segment in _UNVERIFIED_V2:
            raise ChargeScheduleRefusal(
                "CHARGE_SEGMENT_UNVERIFIED",
                f"unverified charge segment {segment!r}: {_UNVERIFIED_V2[segment]}",
            )
        raise ChargeScheduleRefusal(
            "CHARGE_SEGMENT_UNKNOWN", f"unknown segment {segment!r}"
        )
    return _V2_SEGMENTS[segment]


def compute_charges_exact(segment: str, side: str, premium: Any, qty: int, *,
                          schedule_id: str = ZERODHA_CHARGES_V2,
                          expected_schedule_address: str | None = None) -> dict[str, Any]:
    """Return one corrected leg as exact integer paise and bound identity facts."""
    if schedule_id != ZERODHA_CHARGES_V2:
        _schedule_payload(schedule_id)
        raise ChargeScheduleRefusal(
            "CHARGE_EXACT_SCHEDULE_REQUIRED", "exact charge calculation requires corrected v2"
        )
    schedule_address = charge_schedule_address(schedule_id)
    if (expected_schedule_address is not None
            and expected_schedule_address != schedule_address):
        raise ChargeScheduleRefusal(
            "CHARGE_SCHEDULE_STALE",
            "charge schedule address does not match the verified executable schedule",
        )
    rate = _v2_rate(segment)
    side = _require_side(side)
    qty = _require_qty(qty)
    price_minor = _price_minor(premium)
    turnover_minor = _require_turnover(price_minor, qty)
    try:
        turnover = Decimal(turnover_minor) / 100

        if rate.brokerage_rate != "0":
            brokerage_raw = turnover * Decimal(rate.brokerage_rate)
            if rate.brokerage_cap_minor is not None:
                brokerage_raw = min(
                    brokerage_raw, Decimal(rate.brokerage_cap_minor) / 100
                )
            brokerage_minor = _round_paise(brokerage_raw)
        else:
            brokerage_minor = rate.brokerage_flat_minor

        tax_rate = Decimal(rate.tax_buy_rate if side == "BUY" else rate.tax_sell_rate)
        stt_ctt_minor = _round_rupee_minor(turnover * tax_rate) if tax_rate else 0
        exchange_minor = _round_paise(turnover * Decimal(rate.exchange_rate))
        sebi_minor = _round_paise(turnover * Decimal(rate.sebi_rate))
        stamp_minor = (
            _round_paise(turnover * Decimal(rate.stamp_buy_rate)) if side == "BUY" else 0
        )
        dp_minor = rate.dp_sell_base_minor if side == "SELL" else 0
        gst_base = Decimal(brokerage_minor + exchange_minor + sebi_minor + dp_minor) / 100
        gst_minor = _round_paise(gst_base * Decimal(rate.gst_rate))
    except DecimalException:
        raise ChargeScheduleRefusal(
            "CHARGE_TURNOVER_EXCESSIVE", "charge arithmetic exceeds the supported bound"
        ) from None

    components = {
        "brokerage_minor": brokerage_minor,
        "stt_ctt_minor": stt_ctt_minor,
        "exchange_txn_minor": exchange_minor,
        "sebi_minor": sebi_minor,
        "stamp_minor": stamp_minor,
        "dp_minor": dp_minor,
        "gst_minor": gst_minor,
    }
    return {
        "schedule_id": schedule_id,
        "schedule_address": schedule_address,
        "application_mode": APPLICATION_MODE_V2,
        "rounding_policy": ROUNDING_POLICY_V2,
        "segment": segment,
        "product_class": rate.product_class,
        "turnover_unit": rate.turnover_unit,
        "side": side,
        "qty": qty,
        "price_minor": price_minor,
        "turnover_minor": turnover_minor,
        **components,
        "total_minor": sum(components.values()),
    }


def _legacy_compute(segment: str, side: str, premium: Any, qty: int) -> dict[str, Any]:
    if not isinstance(segment, str) or segment not in CHARGE_SCHEDULE:
        raise ChargeScheduleRefusal(
            "CHARGE_SEGMENT_UNKNOWN", f"unknown segment {segment!r}"
        )
    side = _require_side(side)
    qty = _require_qty(qty)
    try:
        price = float(premium)
    except (TypeError, ValueError):
        raise ChargeScheduleRefusal(
            "CHARGE_PRICE_INVALID", "charge price must be finite and positive"
        ) from None
    if not math.isfinite(price) or price <= 0:
        raise ChargeScheduleRefusal(
            "CHARGE_PRICE_INVALID", "charge price must be finite and positive"
        )
    turnover = price * qty
    if not math.isfinite(turnover) or turnover * 100 > MAX_TURNOVER_MINOR:
        raise ChargeScheduleRefusal(
            "CHARGE_TURNOVER_EXCESSIVE", "charge turnover exceeds the supported bound"
        )
    sch = CHARGE_SCHEDULE[segment]
    is_buy, is_sell = side == "BUY", side == "SELL"
    if sch.get("brokerage_pct", 0.0) > 0:
        brokerage = min(sch.get("brokerage_cap", math.inf), turnover * sch["brokerage_pct"])
    else:
        brokerage = sch.get("brokerage_flat", 0.0)
    tax_pct = sch.get("tax_buy_pct", 0.0) if is_buy else sch.get("tax_sell_pct", 0.0)
    tax = turnover * tax_pct
    exchange_txn = turnover * sch.get("txn_pct", 0.0)
    sebi = turnover * sch.get("sebi_pct", 0.0)
    stamp = turnover * sch.get("stamp_buy_pct", 0.0) if is_buy else 0.0
    dp = sch.get("dp_sell_flat", 0.0) if is_sell else 0.0
    gst = sch.get("gst_pct", 0.18) * (brokerage + exchange_txn + sebi + dp)
    total = brokerage + tax + exchange_txn + sebi + stamp + dp + gst
    return {
        "schedule_id": ZERODHA_CHARGES_V1,
        "schedule_address": charge_schedule_address(ZERODHA_CHARGES_V1),
        "segment": segment,
        "side": side,
        "turnover": round(turnover, 2),
        "brokerage": round(brokerage, 2),
        "stt_ctt": round(tax, 2),
        "exchange_txn": round(exchange_txn, 2),
        "sebi": round(sebi, 2),
        "stamp": round(stamp, 2),
        "dp": round(dp, 2),
        "gst": round(gst, 2),
        "total": round(total, 2),
    }


def compute_charges(segment: str, side: str, premium: Any, qty: int, *,
                    schedule_id: str = DEFAULT_RUNTIME_CHARGE_SCHEDULE) -> dict[str, Any]:
    """Compatibility API with explicit schedule selection and no segment fallback."""
    if schedule_id == ZERODHA_CHARGES_V1:
        return _legacy_compute(segment, side, premium, qty)
    if schedule_id != ZERODHA_CHARGES_V2:
        _schedule_payload(schedule_id)  # raises a typed schedule refusal
    exact = compute_charges_exact(segment, side, premium, qty, schedule_id=schedule_id)
    projected = dict(exact)
    projected["price"] = exact["price_minor"] / 100
    projected["turnover"] = exact["turnover_minor"] / 100
    for component in CHARGE_COMPONENTS:
        projected[component] = exact[f"{component}_minor"] / 100
    projected["total"] = exact["total_minor"] / 100
    return projected


def legs_for(direction: str) -> tuple[str, str]:
    """Return the real order sequence for LONG or SHORT positions."""
    if direction not in ("LONG", "SHORT"):
        raise ChargeScheduleRefusal(
            "CHARGE_DIRECTION_INVALID", "charge direction must be exactly LONG or SHORT"
        )
    return ("SELL", "BUY") if direction == "SHORT" else ("BUY", "SELL")


def round_trip_charges_exact(segment: str, direction: str, entry_premium: Any,
                             exit_premium: Any, qty: int, *,
                             schedule_id: str = ZERODHA_CHARGES_V2) -> dict[str, Any]:
    entry_side, exit_side = legs_for(direction)
    entry = compute_charges_exact(
        segment, entry_side, entry_premium, qty, schedule_id=schedule_id
    )
    exit_ = compute_charges_exact(
        segment, exit_side, exit_premium, qty, schedule_id=schedule_id
    )
    aggregate = {
        f"{component}_minor": (
            entry[f"{component}_minor"] + exit_[f"{component}_minor"]
        )
        for component in CHARGE_COMPONENTS
    }
    return {
        "schedule_id": schedule_id,
        "schedule_address": charge_schedule_address(schedule_id),
        "entry": entry,
        "exit": exit_,
        **aggregate,
        "total_minor": sum(aggregate.values()),
    }


def round_trip_charges(segment: str, entry_premium: Any, exit_premium: Any, qty: int, *,
                       schedule_id: str = DEFAULT_RUNTIME_CHARGE_SCHEDULE) -> float:
    buy = compute_charges(
        segment, "BUY", entry_premium, qty, schedule_id=schedule_id
    )["total"]
    sell = compute_charges(
        segment, "SELL", exit_premium, qty, schedule_id=schedule_id
    )["total"]
    return round(buy + sell, 2)


def allocate_minor_units(total_minor: int, quantities: Sequence[int]) -> tuple[int, ...]:
    """Allocate paise deterministically while preserving the exact total."""
    if type(total_minor) is not int or total_minor < 0:
        raise ChargeScheduleRefusal(
            "CHARGE_ALLOCATION_INVALID", "minor-unit total must be a non-negative integer"
        )
    if (not quantities or any(type(qty) is not int or qty <= 0 for qty in quantities)):
        raise ChargeScheduleRefusal(
            "CHARGE_ALLOCATION_INVALID", "allocation quantities must be positive integers"
        )
    denominator = sum(quantities)
    parts: list[int] = []
    remainders: list[int] = []
    for qty in quantities:
        part, remainder = divmod(total_minor * qty, denominator)
        parts.append(part)
        remainders.append(remainder)
    missing = total_minor - sum(parts)
    order = sorted(range(len(parts)), key=lambda index: (-remainders[index], index))
    for index in order[:missing]:
        parts[index] += 1
    return tuple(parts)


def allocate_charge_components(breakdown: Mapping[str, Any],
                               quantities: Sequence[int]) -> tuple[dict[str, int], ...]:
    """Allocate every component independently and retain per-slice closure."""
    component_allocations: dict[str, tuple[int, ...]] = {}
    for component in CHARGE_COMPONENTS:
        key = f"{component}_minor"
        value = breakdown.get(key)
        if type(value) is not int or value < 0:
            raise ChargeScheduleRefusal(
                "CHARGE_ALLOCATION_INVALID",
                f"charge allocation requires non-negative integer {key}",
            )
        component_allocations[key] = allocate_minor_units(value, quantities)
    rows = []
    for index in range(len(quantities)):
        row = {
            key: allocations[index]
            for key, allocations in component_allocations.items()
        }
        rows.append({**row, "total_minor": sum(row.values())})
    return tuple(rows)


__all__ = [
    "APPLICATION_MODE_V2", "CHARGE_COMPONENTS", "CHARGE_SCHEDULE",
    "CORRECTED_RESEARCH_CHARGE_SCHEDULE",
    "DEFAULT_RUNTIME_CHARGE_SCHEDULE", "MAX_TURNOVER_MINOR", "ROUNDING_POLICY_V2",
    "ZERODHA_CHARGES_V1", "ZERODHA_CHARGES_V2", "ChargeScheduleRefusal",
    "allocate_charge_components", "allocate_minor_units", "charge_schedule_address",
    "charge_schedule_document",
    "compute_charges", "compute_charges_exact", "legs_for", "round_trip_charges",
    "monetary_minor", "round_trip_charges_exact",
]
