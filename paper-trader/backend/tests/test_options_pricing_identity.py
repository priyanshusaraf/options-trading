"""Black-Scholes numbers must not move, and the fast path must stay the exact path.

`bs_price` is called ~7,600 times per synthetic-premium backtest cell. Profiling the
10,000 x 5 sweep tier found that 74% of premium replay time was `scipy.stats.norm.cdf`
— not the maths, but the generic `rv_continuous` wrapper around it (argsreduce,
broadcast_arrays, support masks) paid twice per option price on scalar inputs.

`scipy.stats.norm.cdf` computes its answer by calling `scipy.special.ndtr`. Calling
`ndtr` directly is therefore not an approximation of the old behaviour — it is the same
function with the wrapper removed, and it is ~230x faster on scalars.

That claim is what these tests defend. The danger is not the change made here; it is a
future change that replaces `ndtr` with a hand-rolled `math.erf` expression, which is
*nearly* identical and would silently move every backtested option price. Bit-identity
is the contract, so `pytest.approx` is deliberately not used anywhere in this file.
"""
from __future__ import annotations

import struct

import numpy as np
import pytest
from scipy.stats import norm

from app.options.pricing import _normal_cdf, bs_greeks, bs_price


def _bits(x: float) -> bytes:
    return struct.pack("<d", float(x))


def _sample() -> np.ndarray:
    rng = np.random.default_rng(20260809)
    return np.concatenate([
        rng.uniform(-40.0, 40.0, 20_000),      # far tails, where cheap approximations fail
        rng.normal(0.0, 1.0, 10_000),          # the body, where d1/d2 actually live
        np.array([0.0, -0.0, 1e-300, -1e-300, 8.2, -8.2, 37.5, -37.5,
                  np.inf, -np.inf]),           # edges and saturation points
    ])


def test_normal_cdf_is_bit_identical_to_scipy_norm_cdf():
    """The optimisation's whole claim. An approximation makes this red."""
    differing = [float(x) for x in _sample()
                 if _bits(_normal_cdf(float(x))) != _bits(norm.cdf(float(x)))]
    assert not differing, (
        f"{len(differing)} of {len(_sample())} inputs differ from scipy.stats.norm.cdf; "
        f"first few: {differing[:5]}. The normal CDF here must be exact, not close — "
        f"every backtested option price is downstream of it.")


def test_normal_cdf_saturates_at_both_tails():
    assert _normal_cdf(-np.inf) == 0.0
    assert _normal_cdf(np.inf) == 1.0
    assert 0.0 <= _normal_cdf(-50.0) < 1e-300
    assert _normal_cdf(50.0) == 1.0


@pytest.mark.parametrize("S,K,T,r,sigma,flag,expected", [
    # Golden values captured from the scipy.stats.norm.cdf implementation before the
    # change, at full float64 repr. Any numerical drift in the pricing path moves these.
    (20000.0, 20000.0, 30 / 365, 0.06, 0.15, "c", 393.69051368728833),
    (20000.0, 20000.0, 30 / 365, 0.06, 0.15, "p", 295.303175014551),
    (20000.0, 20500.0, 7 / 365, 0.06, 0.22, "c", 77.7398770407508),
    (20000.0, 19500.0, 7 / 365, 0.06, 0.22, "p", 63.92252232122519),
    (100.0, 100.0, 1.0, 0.05, 0.20, "c", 10.450583572185565),
])
def test_bs_price_is_unchanged(S, K, T, r, sigma, flag, expected):
    assert _bits(bs_price(S, K, T, r, sigma, flag)) == _bits(expected)


def test_degenerate_inputs_still_return_intrinsic():
    assert bs_price(120.0, 100.0, 0.0, 0.05, 0.2, "c") == 20.0
    assert bs_price(80.0, 100.0, 0.0, 0.05, 0.2, "p") == 20.0
    assert bs_price(120.0, 100.0, 1.0, 0.05, 0.0, "c") == 20.0
    assert bs_price(80.0, 100.0, 1.0, 0.05, -1.0, "p") == 20.0


def test_greeks_still_agree_with_scipy_bit_for_bit():
    """`bs_greeks` shares the CDF; its delta/theta/rho must not drift either."""
    g = bs_greeks(20000.0, 20000.0, 30 / 365, 0.06, 0.15, "c")
    d1 = (np.log(20000.0 / 20000.0) + (0.06 + 0.5 * 0.15 ** 2) * (30 / 365)) / (
        0.15 * np.sqrt(30 / 365))
    assert _bits(g["delta"]) == _bits(norm.cdf(d1))
