"""Pure fixed-point sizing contracts; no database, provider, broker or order I/O."""
from __future__ import annotations

import dataclasses
import datetime as dt

from app.execution.product_policy import contract_address, require_address


PPM = 1_000_000
MODES = frozenset({
    "FIXED_UNITS", "FIXED_LOTS", "FIXED_CAPITAL", "CAPITAL_PCT",
    "EQUITY_PCT", "RISK_STOP", "VOLATILITY_TARGET",
})


class SizingRefused(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _integer(value: object, *, field: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise SizingRefused(f"INVALID_{field.upper()}")
    return value


@dataclasses.dataclass(frozen=True)
class SizingPolicy:
    policy_id: str
    version: int
    mode: str
    currency: str = "INR"
    fixed_units: int | None = None
    fixed_lots: int | None = None
    amount_minor: int | None = None
    rate_ppm: int | None = None
    risk_budget_minor: int | None = None
    target_volatility_ppm: int | None = None
    min_quantity: int = 1
    max_quantity: int | None = None
    max_capital_minor: int | None = None
    fee_buffer_minor: int = 0
    safety_buffer_minor: int = 0
    allow_resize: bool = False

    def __post_init__(self) -> None:
        if not self.policy_id or self.mode not in MODES:
            raise SizingRefused("INVALID_POLICY")
        _integer(self.version, field="version", minimum=1)
        if len(self.currency) != 3 or self.currency.upper() != self.currency:
            raise SizingRefused("INVALID_CURRENCY")
        _integer(self.min_quantity, field="min_quantity", minimum=1)
        _integer(self.fee_buffer_minor, field="fee_buffer_minor")
        _integer(self.safety_buffer_minor, field="safety_buffer_minor")
        if not isinstance(self.allow_resize, bool):
            raise SizingRefused("INVALID_ALLOW_RESIZE")
        if self.max_quantity is not None:
            _integer(self.max_quantity, field="max_quantity", minimum=1)
            if self.max_quantity < self.min_quantity:
                raise SizingRefused("INVALID_QUANTITY_CAP")
        if self.max_capital_minor is not None:
            _integer(self.max_capital_minor, field="max_capital_minor", minimum=1)

        mode_values = {
            "FIXED_UNITS": self.fixed_units,
            "FIXED_LOTS": self.fixed_lots,
            "FIXED_CAPITAL": self.amount_minor,
            "CAPITAL_PCT": self.rate_ppm,
            "EQUITY_PCT": self.rate_ppm,
            "RISK_STOP": self.risk_budget_minor,
            "VOLATILITY_TARGET": self.target_volatility_ppm,
        }
        selected = mode_values[self.mode]
        _integer(selected, field=self.mode.lower(), minimum=1)
        if self.mode in {"CAPITAL_PCT", "EQUITY_PCT", "VOLATILITY_TARGET"} \
                and selected > PPM:
            raise SizingRefused("RATE_OUT_OF_RANGE")
        supplied = [
            self.fixed_units is not None,
            self.fixed_lots is not None,
            self.amount_minor is not None,
            self.rate_ppm is not None,
            self.risk_budget_minor is not None,
            self.target_volatility_ppm is not None,
        ]
        # CAPITAL_PCT and EQUITY_PCT intentionally share rate_ppm.
        if sum(supplied) != 1:
            raise SizingRefused("AMBIGUOUS_PRIMARY_MODE")

    @property
    def address(self) -> str:
        return contract_address("sizing-policy/1", self)


@dataclasses.dataclass(frozen=True)
class SizingInputs:
    decision_at: dt.datetime
    observed_at: dt.datetime
    max_age_seconds: int
    quantity_step: int
    lot_size: int
    capital_per_step_minor: int
    notional_per_step_minor: int
    risk_per_step_minor: int | None
    available_capital_minor: int
    equity_minor: int
    observed_volatility_ppm: int | None
    estimated_fees_minor: int
    source_addresses: tuple[str, ...]

    def __post_init__(self) -> None:
        for value, field, minimum in (
            (self.max_age_seconds, "max_age_seconds", 1),
            (self.quantity_step, "quantity_step", 1),
            (self.lot_size, "lot_size", 1),
            (self.capital_per_step_minor, "capital_per_step_minor", 1),
            (self.notional_per_step_minor, "notional_per_step_minor", 1),
            (self.available_capital_minor, "available_capital_minor", 0),
            (self.equity_minor, "equity_minor", 0),
            (self.estimated_fees_minor, "estimated_fees_minor", 0),
        ):
            _integer(value, field=field, minimum=minimum)
        if self.risk_per_step_minor is not None:
            _integer(self.risk_per_step_minor, field="risk_per_step_minor", minimum=1)
        if self.observed_volatility_ppm is not None:
            _integer(self.observed_volatility_ppm,
                     field="observed_volatility_ppm", minimum=1)
        if self.lot_size % self.quantity_step:
            raise SizingRefused("LOT_STEP_MISMATCH")
        if (self.decision_at.tzinfo is None or self.decision_at.utcoffset() is None
                or self.observed_at.tzinfo is None
                or self.observed_at.utcoffset() is None):
            raise SizingRefused("NAIVE_TIME")
        if (not self.source_addresses
                or tuple(sorted(set(self.source_addresses))) != self.source_addresses):
            raise SizingRefused("INVALID_SOURCE_ADDRESSES")
        for address in self.source_addresses:
            require_address(address, field="source_address")

    @property
    def address(self) -> str:
        return contract_address("sizing-inputs/1", self)


@dataclasses.dataclass(frozen=True)
class SizingDecision:
    policy_address: str
    product_address: str
    inputs_address: str
    accepted: bool
    requested_quantity: int
    admitted_quantity: int
    required_capital_minor: int
    estimated_fees_minor: int
    binding_constraint: str
    reason_code: str
    resized: bool
    input_addresses: tuple[str, ...]

    @property
    def address(self) -> str:
        return contract_address("sizing-decision/1", self)


def _decision(
        policy: SizingPolicy, product_address: str, inputs: SizingInputs, *,
        accepted: bool, requested: int, admitted: int, required: int,
        constraint: str, reason: str, resized: bool = False) -> SizingDecision:
    require_address(product_address, field="product_address")
    return SizingDecision(
        policy.address, product_address, inputs.address, accepted,
        requested, admitted, required, inputs.estimated_fees_minor,
        constraint, reason, resized, inputs.source_addresses)


def _raw_quantity(policy: SizingPolicy, inputs: SizingInputs) -> int:
    step = inputs.quantity_step
    if policy.mode == "FIXED_UNITS":
        return int(policy.fixed_units)
    if policy.mode == "FIXED_LOTS":
        return int(policy.fixed_lots) * inputs.lot_size
    if policy.mode == "FIXED_CAPITAL":
        return (int(policy.amount_minor) // inputs.capital_per_step_minor) * step
    if policy.mode == "CAPITAL_PCT":
        budget = inputs.available_capital_minor * int(policy.rate_ppm) // PPM
        return (budget // inputs.capital_per_step_minor) * step
    if policy.mode == "EQUITY_PCT":
        budget = inputs.equity_minor * int(policy.rate_ppm) // PPM
        return (budget // inputs.capital_per_step_minor) * step
    if policy.mode == "RISK_STOP":
        if inputs.risk_per_step_minor is None:
            raise SizingRefused("RISK_INPUT_REQUIRED")
        return (int(policy.risk_budget_minor) // inputs.risk_per_step_minor) * step
    if inputs.observed_volatility_ppm is None:
        raise SizingRefused("VOLATILITY_INPUT_REQUIRED")
    target_exposure = (
        inputs.equity_minor * int(policy.target_volatility_ppm)
        // inputs.observed_volatility_ppm)
    return (target_exposure // inputs.notional_per_step_minor) * step


def size_position(
        policy: SizingPolicy, *, product_address: str,
        inputs: SizingInputs) -> SizingDecision:
    """Return one deterministic fixed-point decision. No external lookup occurs."""
    require_address(product_address, field="product_address")
    age = (inputs.decision_at.astimezone(dt.timezone.utc)
           - inputs.observed_at.astimezone(dt.timezone.utc)).total_seconds()
    if age < 0:
        raise SizingRefused("FUTURE_INPUT")
    if age > inputs.max_age_seconds:
        raise SizingRefused("STALE_INPUT")

    raw = _raw_quantity(policy, inputs)
    step = inputs.quantity_step
    rounded = (raw // step) * step
    rounded_by_step = rounded != raw
    if rounded < policy.min_quantity:
        return _decision(
            policy, product_address, inputs, accepted=False,
            requested=raw, admitted=0, required=0,
            constraint="minimum_quantity", reason="BELOW_MINIMUM")

    fee_and_buffers = (inputs.estimated_fees_minor + policy.fee_buffer_minor
                       + policy.safety_buffer_minor)
    available_for_steps = max(0, inputs.available_capital_minor - fee_and_buffers)
    capacity_quantity = (
        available_for_steps // inputs.capital_per_step_minor) * step
    cap_quantity = policy.max_quantity if policy.max_quantity is not None else rounded
    if policy.max_capital_minor is not None:
        by_capital = max(
            0, (policy.max_capital_minor - fee_and_buffers)
            // inputs.capital_per_step_minor) * step
        cap_quantity = min(cap_quantity, by_capital)
    allowed = min(rounded, capacity_quantity, cap_quantity)
    allowed = (allowed // step) * step
    constrained = allowed < rounded
    if constrained and not policy.allow_resize:
        constraint = (
            "available_capital" if capacity_quantity < rounded
            else "policy_cap")
        required = ((rounded // step) * inputs.capital_per_step_minor
                    + fee_and_buffers)
        return _decision(
            policy, product_address, inputs, accepted=False,
            requested=raw, admitted=0, required=required,
            constraint=constraint, reason="RESIZE_NOT_ALLOWED")
    if allowed < policy.min_quantity:
        return _decision(
            policy, product_address, inputs, accepted=False,
            requested=raw, admitted=0, required=0,
            constraint="minimum_quantity", reason="BELOW_MINIMUM")
    required = ((allowed // step) * inputs.capital_per_step_minor
                + fee_and_buffers)
    return _decision(
        policy, product_address, inputs, accepted=True,
        requested=raw, admitted=allowed, required=required,
        constraint=("explicit_resize" if constrained else
                    "quantity_step" if rounded_by_step else "none"),
        reason=("EXPLICIT_RESIZE" if constrained else
                "ROUNDED" if rounded_by_step else "SIZED"),
        resized=constrained)


__all__ = [
    "MODES", "PPM", "SizingDecision", "SizingInputs", "SizingPolicy",
    "SizingRefused", "size_position",
]
