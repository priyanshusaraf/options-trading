"""
Black-Scholes pricing, greeks and implied-volatility inversion.

Ported verbatim (math-wise) from the existing stock-market-analyst options engine
so the numbers are identical to code already trusted in this repo. `flag` is
'c' for calls / 'p' for puts.
"""
from __future__ import annotations

import math
from typing import Optional

from scipy.optimize import brentq
from scipy.stats import norm


def bs_price(S: float, K: float, T: float, r: float, sigma: float, flag: str) -> float:
    """Black-Scholes option price. flag: 'c' or 'p'."""
    if T <= 0 or sigma <= 0:
        return max(0.0, (S - K) if flag == "c" else (K - S))
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    if flag == "c":
        return S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
    return K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)


def implied_vol(
    market_price: float, S: float, K: float, T: float, r: float, flag: str,
    tol: float = 1e-6,
) -> Optional[float]:
    """Implied volatility via Brent's method. None if it can't be solved."""
    intrinsic = max(0.0, (S - K) if flag == "c" else (K - S))
    if market_price <= intrinsic + tol or T <= 0:
        return None
    try:
        iv = brentq(
            lambda sigma: bs_price(S, K, T, r, sigma, flag) - market_price,
            1e-6, 10.0, xtol=tol, maxiter=200,
        )
        return float(iv) if 0 < iv < 10 else None
    except (ValueError, RuntimeError):
        return None


def bs_greeks(S: float, K: float, T: float, r: float, sigma: float, flag: str) -> dict:
    """delta, gamma, theta, vega, rho."""
    if T <= 0 or sigma <= 0:
        return {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0, "rho": 0.0}
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    gamma = norm.pdf(d1) / (S * sigma * math.sqrt(T))
    vega = S * norm.pdf(d1) * math.sqrt(T) / 100
    if flag == "c":
        delta = norm.cdf(d1)
        theta = (-(S * norm.pdf(d1) * sigma) / (2 * math.sqrt(T))
                 - r * K * math.exp(-r * T) * norm.cdf(d2)) / 365
        rho = K * T * math.exp(-r * T) * norm.cdf(d2) / 100
    else:
        delta = norm.cdf(d1) - 1
        theta = (-(S * norm.pdf(d1) * sigma) / (2 * math.sqrt(T))
                 + r * K * math.exp(-r * T) * norm.cdf(-d2)) / 365
        rho = -K * T * math.exp(-r * T) * norm.cdf(-d2) / 100
    return {"delta": delta, "gamma": gamma, "theta": theta, "vega": vega, "rho": rho}


def bs_delta(S: float, K: float, T: float, r: float, sigma: float, flag: str) -> float:
    return bs_greeks(S, K, T, r, sigma, flag)["delta"]
