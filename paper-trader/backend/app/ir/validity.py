"""Closed numeric-validity envelope for opted-in Component IR v2 values.

This is deliberately a value contract, not a second evaluator.  The v2
runtime remains the sole graph evaluator and the PlatformRegistry remains the
sole place that declares how a component handles invalid input.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Any, Iterable


class ValidityState(str, Enum):
    VALID = "VALID"
    MISSING = "MISSING"
    STALE = "STALE"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    MATHEMATICALLY_UNDEFINED = "MATHEMATICALLY_UNDEFINED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    NOT_IN_SESSION = "NOT_IN_SESSION"
    NOT_LISTED = "NOT_LISTED"
    NO_TRADE = "NO_TRADE"
    INVALID = "INVALID"


@dataclass(frozen=True)
class NumericValue:
    """An executable finite value or a non-executable, diagnostic-only state."""

    state: ValidityState
    value: Any = None
    causes: tuple[ValidityState, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.state, ValidityState):
            raise ValueError("numeric validity state is not closed")
        causes = tuple(sorted(set(self.causes), key=lambda item: item.value))
        if any(not isinstance(cause, ValidityState) or cause is ValidityState.VALID for cause in causes):
            raise ValueError("invalid causes must be known non-VALID states")
        object.__setattr__(self, "causes", causes)
        if self.state is ValidityState.VALID:
            try:
                value = _closed_finite_value(self.value)
            except (TypeError, ValueError):
                value = None
            if causes or value is None:
                raise ValueError("VALID must carry one finite typed value and no causes")
            object.__setattr__(self, "value", value)
        elif self.value is not None:
            raise ValueError("invalid numeric values carry no executable value")


def valid(value: Any) -> NumericValue:
    return NumericValue(ValidityState.VALID, value)


def invalid(state: ValidityState, *, causes: Iterable[ValidityState] = ()) -> NumericValue:
    if state is ValidityState.VALID:
        raise ValueError("use valid() for VALID")
    return NumericValue(state, causes=tuple(causes))


def propagate(values: Iterable[NumericValue]) -> NumericValue | None:
    """Return the deterministic invalid result, or ``None`` when all are valid."""
    invalids = [item for item in values if item.state is not ValidityState.VALID]
    if not invalids:
        return None
    states = {item.state for item in invalids}
    if len(states) == 1:
        return invalids[0] if len(invalids) == 1 else invalid(next(iter(states)))
    causes = tuple(sorted(states, key=lambda item: item.value))
    return invalid(ValidityState.INVALID, causes=causes)


def fallback(value: NumericValue, replacement: NumericValue, accepted_states: Iterable[ValidityState]) -> NumericValue:
    """Apply only an explicitly declared fallback policy."""
    accepted = frozenset(accepted_states)
    if value.state is ValidityState.VALID:
        return value
    if value.state not in accepted:
        return value
    if replacement.state is not ValidityState.VALID:
        return replacement
    return replacement


def entry_authorized(value: NumericValue) -> bool:
    """Only a finite, explicitly true boolean may authorize a new entry."""
    return value.state is ValidityState.VALID and value.value is True


def _closed_finite_value(value: Any) -> Any:
    """Return the immutable numeric value owned by this envelope.

    Arrays and series are accepted only through their plain ``tolist`` value.
    The caller's mutable container is never retained.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if not math.isfinite(value):
            raise ValueError("numeric value must be finite")
        return value
    if isinstance(value, tuple):
        return tuple(_closed_finite_value(item) for item in value)
    # Pandas Series / numpy arrays expose a sequence through tolist without
    # making pandas part of the validity contract's dependency surface.
    tolist = getattr(value, "tolist", None)
    if callable(tolist):
        try:
            plain = _lists_to_tuples(tolist())
            return _closed_finite_value(plain)
        except (TypeError, ValueError, OverflowError):
            raise ValueError("array value is not a closed finite numeric value") from None
    raise TypeError("value is not a closed numeric scalar or tuple")


def _lists_to_tuples(value: Any) -> Any:
    if isinstance(value, list):
        return tuple(_lists_to_tuples(item) for item in value)
    return value


__all__ = ["NumericValue", "ValidityState", "entry_authorized", "fallback", "invalid", "propagate", "valid"]
