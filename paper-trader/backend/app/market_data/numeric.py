"""The one authoritative raw-market-numeric ingress rule (audit A-02 / DP-011).

Python ``bool`` is a subtype of ``int``, so ``float(True) == 1.0``: a raw
boolean crossing an innocent-looking coercion becomes an executable price.
Foundation-audit finding A-02 demonstrated exactly that path through provider
preparation and the dataset encoder.

Prevention invariant: **reject host-language booleans before any coercion, at
every raw market numeric ingress**, under this single rule.  Every adapter and
storage boundary imports ``market_float`` from here; none re-implements the
check.  Callers keep their own failure vocabulary (providers wrap this into
``ProviderReadError``; the dataset encoder into ``DatasetStoreError``) — what
they may not do is coerce first and validate after.

Non-finite floats are refused on the same boundary: a NaN candle price would
poison dataset identity exactly as silently as a coerced boolean.

IEEE-754 signed zero is normalized here as well.  Positive and negative zero
are the same market value, so their sign bit must not split observation,
dataset, or result-cache identity after this ingress.
"""
from __future__ import annotations

import math

try:  # NumPy is installed with pandas, but keep this leaf usable without it.
    from numpy import bool_ as _numpy_bool
except ImportError:  # pragma: no cover - the supported backend installs NumPy
    _BOOLEAN_SCALARS = (bool,)
else:
    _BOOLEAN_SCALARS = (bool, _numpy_bool)


class NumericIngressError(ValueError):
    """A raw market number was not a real, finite number before coercion."""


def market_float(value, *, field: str) -> float:
    """Return ``value`` as a plain float, refusing booleans and non-numbers.

    Boolean scalar types are rejected *before* coercion precisely because they
    otherwise coerce cleanly.  All other values accepted by the historical
    ``float(value)`` boundary remain accepted, including Decimal, numeric text,
    and NumPy numeric scalars.  The result is always exactly ``float`` type.
    """
    if isinstance(value, _BOOLEAN_SCALARS):
        raise NumericIngressError(
            f"{field}: boolean scalar {type(value).__name__} is not a market number")
    try:
        out = float(value)
    except (TypeError, ValueError, OverflowError):
        raise NumericIngressError(
            f"{field}: expected a float-coercible number, got {type(value).__name__}") from None
    if not math.isfinite(out):
        raise NumericIngressError(f"{field}: non-finite value {value!r}")
    return 0.0 if out == 0.0 else out
