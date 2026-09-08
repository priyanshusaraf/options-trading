"""Pure compatibility projections for current product quantity/allocation rules."""
from __future__ import annotations

import dataclasses
import decimal


class CompatibilityRefused(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _decimal(value: object, *, field: str) -> decimal.Decimal:
    if isinstance(value, bool):
        raise CompatibilityRefused(f"INVALID_{field.upper()}")
    try:
        result = decimal.Decimal(str(value))
    except (decimal.InvalidOperation, ValueError) as exc:
        raise CompatibilityRefused(f"INVALID_{field.upper()}") from exc
    if not result.is_finite() or result <= 0:
        raise CompatibilityRefused(f"INVALID_{field.upper()}")
    return result


def fixed_option_quantity(lot_size: object) -> int:
    if isinstance(lot_size, bool) or not isinstance(lot_size, int) or lot_size < 1:
        raise CompatibilityRefused("INVALID_LOT_SIZE")
    return lot_size


def legacy_equity_quantity(*, margin: object, leverage: object, price: object) -> int:
    """Exact positive-input equivalent of equity_entry.equity_qty."""
    margin_value = _decimal(margin, field="margin")
    leverage_value = _decimal(leverage, field="leverage")
    price_value = _decimal(price, field="price")
    return int((margin_value * leverage_value) // price_value)


def broker_margin_equity_quantity(
        *, per_share_margin: object, target_margin: object) -> int:
    """Exact positive-input equivalent of equity_entry.qty_for_margin."""
    per_share = _decimal(per_share_margin, field="per_share_margin")
    target = _decimal(target_margin, field="target_margin")
    return int(target // per_share)


def futures_quantity_from_margin(
        *, margin_per_lot: object, target_margin: object,
        lot_size: object) -> tuple[int, decimal.Decimal] | None:
    margin = _decimal(margin_per_lot, field="margin_per_lot")
    target = _decimal(target_margin, field="target_margin")
    if isinstance(lot_size, bool) or not isinstance(lot_size, int) or lot_size < 1:
        raise CompatibilityRefused("INVALID_LOT_SIZE")
    lots = int(target // margin)
    return (lots * lot_size, lots * margin) if lots else None


def paper_futures_quantity(
        *, price: object, lot_size: object, margin_pct: object,
        target_margin: object) -> tuple[int, decimal.Decimal] | None:
    price_value = _decimal(price, field="price")
    pct = _decimal(margin_pct, field="margin_pct")
    if pct > 1:
        raise CompatibilityRefused("INVALID_MARGIN_PCT")
    if isinstance(lot_size, bool) or not isinstance(lot_size, int) or lot_size < 1:
        raise CompatibilityRefused("INVALID_LOT_SIZE")
    return futures_quantity_from_margin(
        margin_per_lot=price_value * lot_size * pct,
        target_margin=target_margin, lot_size=lot_size)


@dataclasses.dataclass(frozen=True)
class CompatibilityCandidate:
    instrument_key: str
    direction: str
    cost_minor: int
    priority: int

    def __post_init__(self) -> None:
        if not self.instrument_key or self.direction not in {"LONG", "SHORT"}:
            raise CompatibilityRefused("INVALID_CANDIDATE")
        for value, field, minimum in (
            (self.cost_minor, "cost_minor", 1),
            (self.priority, "priority", 0),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
                raise CompatibilityRefused(f"INVALID_{field.upper()}")


@dataclasses.dataclass(frozen=True)
class CompatibilityAllocation:
    funded: tuple[CompatibilityCandidate, ...]
    skipped: tuple[tuple[CompatibilityCandidate, str], ...]


def allocate_compatibility(
        candidates: tuple[CompatibilityCandidate, ...], *,
        available_cash_minor: int) -> CompatibilityAllocation:
    """Current fund-all/priority-greedy/no-resize policy with explicit priorities."""
    if (isinstance(available_cash_minor, bool)
            or not isinstance(available_cash_minor, int)
            or available_cash_minor < 0):
        raise CompatibilityRefused("INVALID_AVAILABLE_CASH")
    ordered = sorted(candidates, key=lambda item: (item.priority, item.instrument_key))
    funded = []
    skipped = []
    remaining = available_cash_minor
    for candidate in ordered:
        if candidate.cost_minor <= remaining:
            funded.append(candidate)
            remaining -= candidate.cost_minor
        else:
            skipped.append((candidate, "INSUFFICIENT_CAPITAL"))
    return CompatibilityAllocation(tuple(funded), tuple(skipped))


__all__ = [
    "CompatibilityAllocation", "CompatibilityCandidate", "CompatibilityRefused",
    "allocate_compatibility", "broker_margin_equity_quantity",
    "fixed_option_quantity", "futures_quantity_from_margin",
    "legacy_equity_quantity", "paper_futures_quantity",
]
