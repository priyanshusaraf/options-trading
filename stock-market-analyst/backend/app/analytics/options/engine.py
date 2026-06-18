"""
Options & Derivatives Engine.

Sources (priority order):
  1. Zerodha Kite API (if authenticated) — live options chain for NSE
  2. NSE India public API — options chain fallback (no key needed)
  3. yfinance — global options for non-NSE symbols

Computes:
  - Implied Volatility (IV) via Black-Scholes inversion (Newton-Raphson)
  - IV Surface (strike × expiry grid)
  - IV Skew (put/call IV differential)
  - Put-Call Ratio (PCR) — volume and OI based
  - OI change analysis (accumulation vs unwinding)
  - Max Pain level
  - Smart money positioning signals
  - Volatility breakout probability
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd
import requests
from scipy.optimize import brentq
from scipy.stats import norm

from backend.app.core.cache import cached
from backend.app.core.config import get_settings
from backend.app.core.logging import logger

# ── Black-Scholes ─────────────────────────────────────────────────────────────

def _bs_price(S: float, K: float, T: float, r: float, sigma: float, flag: str) -> float:
    """Black-Scholes option price. flag: 'c' or 'p'."""
    if T <= 0 or sigma <= 0:
        return max(0.0, (S - K) if flag == "c" else (K - S))
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    if flag == "c":
        return S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
    return K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)


def _bs_vega(S: float, K: float, T: float, r: float, sigma: float) -> float:
    if T <= 0 or sigma <= 0:
        return 0.0
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    return S * norm.pdf(d1) * math.sqrt(T)


def implied_vol(
    market_price: float,
    S: float,
    K: float,
    T: float,
    r: float,
    flag: str,
    tol: float = 1e-6,
) -> Optional[float]:
    """
    Compute implied volatility via Brent's method.
    Returns None if IV cannot be computed (deep ITM/OTM, zero time, etc.).
    """
    intrinsic = max(0.0, (S - K) if flag == "c" else (K - S))
    if market_price <= intrinsic + tol or T <= 0:
        return None
    try:
        iv = brentq(
            lambda sigma: _bs_price(S, K, T, r, sigma, flag) - market_price,
            1e-6,
            10.0,
            xtol=tol,
            maxiter=200,
        )
        return float(iv) if 0 < iv < 10 else None
    except (ValueError, RuntimeError):
        return None


def _bs_greeks(S: float, K: float, T: float, r: float, sigma: float, flag: str) -> dict:
    """Return delta, gamma, theta, vega, rho."""
    if T <= 0 or sigma <= 0:
        return {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0, "rho": 0.0}
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    gamma = norm.pdf(d1) / (S * sigma * math.sqrt(T))
    vega = S * norm.pdf(d1) * math.sqrt(T) / 100
    if flag == "c":
        delta = norm.cdf(d1)
        theta = (-(S * norm.pdf(d1) * sigma) / (2 * math.sqrt(T)) - r * K * math.exp(-r * T) * norm.cdf(d2)) / 365
        rho = K * T * math.exp(-r * T) * norm.cdf(d2) / 100
    else:
        delta = norm.cdf(d1) - 1
        theta = (-(S * norm.pdf(d1) * sigma) / (2 * math.sqrt(T)) + r * K * math.exp(-r * T) * norm.cdf(-d2)) / 365
        rho = -K * T * math.exp(-r * T) * norm.cdf(-d2) / 100
    return {"delta": delta, "gamma": gamma, "theta": theta, "vega": vega, "rho": rho}


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class OptionRow:
    strike: float
    expiry: date
    option_type: str          # "CE" or "PE"
    ltp: float                # Last traded price
    bid: float = 0.0
    ask: float = 0.0
    volume: int = 0
    oi: int = 0
    oi_change: int = 0
    iv: Optional[float] = None
    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None


@dataclass
class OptionsChainResult:
    symbol: str
    spot_price: float
    expiry: date
    risk_free_rate: float

    chain: list[OptionRow] = field(default_factory=list)

    # Aggregated analytics
    pcr_volume: float = 0.0       # Put-Call Ratio by volume
    pcr_oi: float = 0.0           # Put-Call Ratio by OI
    max_pain: float = 0.0         # Strike causing maximum loss to option buyers
    atm_iv: float = 0.0           # ATM implied volatility
    iv_skew: float = 0.0          # 25-delta put IV - 25-delta call IV
    term_structure: dict = field(default_factory=dict)

    # Signals
    smart_money_signal: str = "NEUTRAL"   # BULLISH / BEARISH / NEUTRAL
    vol_breakout_prob: float = 0.0
    signal_reasons: list[str] = field(default_factory=list)


# ── NSE Options Chain fetcher ─────────────────────────────────────────────────

NSE_CHAIN_URL = "https://www.nseindia.com/api/option-chain-indices"
NSE_STOCK_URL = "https://www.nseindia.com/api/option-chain-equities"
NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}


class OptionsEngine:

    def __init__(self):
        self.settings = get_settings()
        self.rf = self.settings.risk_free_rate
        self._session: Optional[requests.Session] = None

    # ── Public API ─────────────────────────────────────────────────────────────

    def analyze(
        self,
        symbol: str,
        spot_price: float,
        expiry: Optional[date] = None,
        use_nse: bool = True,
    ) -> OptionsChainResult:
        """
        Main entry point. Fetch options chain and compute full analytics.
        """
        expiry = expiry or self._next_expiry()
        chain_data = None

        if use_nse:
            try:
                chain_data = self._fetch_nse_chain(symbol)
            except Exception as e:
                logger.warning(f"[Options] NSE fetch failed for {symbol}: {e}")

        if chain_data is None:
            try:
                chain_data = self._fetch_yfinance_chain(symbol, expiry)
            except Exception as e:
                logger.warning(f"[Options] yfinance options failed for {symbol}: {e}")

        if chain_data is None or not chain_data:
            logger.error(f"[Options] All sources failed for {symbol}")
            return OptionsChainResult(
                symbol=symbol, spot_price=spot_price, expiry=expiry, risk_free_rate=self.rf
            )

        result = self._build_result(symbol, spot_price, expiry, chain_data)
        self._compute_signals(result)
        return result

    def compute_iv_surface(
        self,
        symbol: str,
        spot_price: float,
        chain_data: list[OptionRow],
    ) -> pd.DataFrame:
        """
        Build a 2D IV surface: rows = strikes, columns = expiries.
        Returns a DataFrame with strike as index, expiry dates as columns.
        """
        records = []
        for row in chain_data:
            if row.iv is not None:
                records.append(
                    {"strike": row.strike, "expiry": str(row.expiry), "iv": row.iv, "type": row.option_type}
                )
        if not records:
            return pd.DataFrame()

        df = pd.DataFrame(records)
        pivot = df.groupby(["strike", "expiry"])["iv"].mean().unstack("expiry")
        return pivot.round(4)

    def max_pain(self, chain: list[OptionRow], spot: float) -> float:
        """
        Max pain: strike where total option buyer losses are maximized.
        Computed by summing intrinsic value of all options at each strike.
        """
        strikes = sorted(set(r.strike for r in chain))
        if not strikes:
            return spot

        pain: dict[float, float] = {}
        for test_strike in strikes:
            total_pain = 0.0
            for row in chain:
                if row.option_type == "CE":
                    total_pain += max(0.0, test_strike - row.strike) * row.oi
                else:
                    total_pain += max(0.0, row.strike - test_strike) * row.oi
            pain[test_strike] = total_pain

        return min(pain, key=pain.get)  # type: ignore

    # ── NSE fetcher ────────────────────────────────────────────────────────────

    @cached(ttl=900, prefix="nse:chain")  # 15-min cache for live data
    def _fetch_nse_chain(self, symbol: str) -> Optional[list[dict]]:
        """Fetch options chain from NSE public API."""
        session = self._get_nse_session()
        url = NSE_CHAIN_URL if symbol.upper() in ("NIFTY", "BANKNIFTY", "FINNIFTY") else NSE_STOCK_URL
        params = {"symbol": symbol.upper()}

        logger.info(f"[Options/NSE] Fetching chain for {symbol}")
        resp = session.get(url, params=params, headers=NSE_HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        records = data.get("records", {})
        return records.get("data", [])

    def _get_nse_session(self) -> requests.Session:
        """NSE requires a cookie from the homepage before API calls work."""
        if self._session is None:
            self._session = requests.Session()
            try:
                self._session.get("https://www.nseindia.com", headers=NSE_HEADERS, timeout=10)
            except Exception:
                pass
        return self._session

    def _parse_nse_chain(
        self, raw: list[dict], spot: float, expiry: date
    ) -> list[OptionRow]:
        rows = []
        T = max((expiry - date.today()).days / 365.0, 1 / 365)

        for entry in raw:
            for opt_type in ("CE", "PE"):
                opt = entry.get(opt_type, {})
                if not opt:
                    continue
                strike = float(entry.get("strikePrice", 0))
                ltp = float(opt.get("lastPrice", 0))
                flag = "c" if opt_type == "CE" else "p"
                iv = None
                if ltp > 0 and strike > 0:
                    iv = implied_vol(ltp, spot, strike, T, self.rf, flag)

                greeks = _bs_greeks(spot, strike, T, self.rf, iv or 0.2, flag) if iv else {}
                row = OptionRow(
                    strike=strike,
                    expiry=expiry,
                    option_type=opt_type,
                    ltp=ltp,
                    volume=int(opt.get("totalTradedVolume", 0)),
                    oi=int(opt.get("openInterest", 0)),
                    oi_change=int(opt.get("changeinOpenInterest", 0)),
                    iv=iv,
                    **{k: greeks.get(k) for k in ("delta", "gamma", "theta", "vega")},
                )
                rows.append(row)
        return rows

    # ── yfinance fallback ─────────────────────────────────────────────────────

    @cached(ttl=1800, prefix="yf:options")
    def _fetch_yfinance_chain(self, symbol: str, expiry: date) -> Optional[list[dict]]:
        """Fallback: fetch options from yfinance (US stocks mainly)."""
        import yfinance as yf
        logger.info(f"[Options/yfinance] Fetching chain for {symbol}")
        ticker = yf.Ticker(symbol)
        exps = ticker.options
        if not exps:
            return None
        # Pick closest expiry
        target = str(expiry)
        chosen = min(exps, key=lambda e: abs((pd.Timestamp(e) - pd.Timestamp(target)).days))
        chain = ticker.option_chain(chosen)
        calls = chain.calls.assign(option_type="CE")
        puts = chain.puts.assign(option_type="PE")
        return pd.concat([calls, puts]).to_dict("records")

    def _parse_yfinance_chain(self, raw: list[dict], spot: float, expiry: date) -> list[OptionRow]:
        rows = []
        T = max((expiry - date.today()).days / 365.0, 1 / 365)
        for entry in raw:
            opt_type = entry.get("option_type", "CE")
            strike = float(entry.get("strike", 0))
            ltp = float(entry.get("lastPrice", 0))
            flag = "c" if opt_type == "CE" else "p"
            iv = float(entry.get("impliedVolatility", 0)) or None
            if iv and iv > 10:
                iv = None  # yfinance sometimes returns absurd values
            if iv is None and ltp > 0 and strike > 0:
                iv = implied_vol(ltp, spot, strike, T, self.rf, flag)
            greeks = _bs_greeks(spot, strike, T, self.rf, iv or 0.2, flag) if iv else {}
            rows.append(OptionRow(
                strike=strike,
                expiry=expiry,
                option_type=opt_type,
                ltp=ltp,
                volume=int(entry.get("volume", 0) or 0),
                oi=int(entry.get("openInterest", 0) or 0),
                iv=iv,
                **{k: greeks.get(k) for k in ("delta", "gamma", "theta", "vega")},
            ))
        return rows

    # ── Analytics ─────────────────────────────────────────────────────────────

    def _build_result(
        self, symbol: str, spot: float, expiry: date, raw: list[dict]
    ) -> OptionsChainResult:
        # Detect source and parse accordingly
        if raw and isinstance(raw[0], dict) and "CE" in raw[0] or "PE" in raw[0]:
            chain = self._parse_nse_chain(raw, spot, expiry)
        else:
            chain = self._parse_yfinance_chain(raw, spot, expiry)

        result = OptionsChainResult(
            symbol=symbol, spot_price=spot, expiry=expiry, risk_free_rate=self.rf, chain=chain
        )

        calls = [r for r in chain if r.option_type == "CE" and r.ltp > 0]
        puts = [r for r in chain if r.option_type == "PE" and r.ltp > 0]

        # ── PCR ──────────────────────────────────────────────────────────────
        total_call_vol = sum(r.volume for r in calls)
        total_put_vol = sum(r.volume for r in puts)
        total_call_oi = sum(r.oi for r in calls)
        total_put_oi = sum(r.oi for r in puts)

        result.pcr_volume = total_put_vol / total_call_vol if total_call_vol > 0 else 0.0
        result.pcr_oi = total_put_oi / total_call_oi if total_call_oi > 0 else 0.0

        # ── Max Pain ─────────────────────────────────────────────────────────
        result.max_pain = self.max_pain(chain, spot)

        # ── ATM IV ───────────────────────────────────────────────────────────
        atm_strike = min((r.strike for r in chain), key=lambda s: abs(s - spot), default=spot)
        atm_ivs = [r.iv for r in chain if r.strike == atm_strike and r.iv is not None]
        result.atm_iv = float(np.mean(atm_ivs)) if atm_ivs else 0.0

        # ── IV Skew: 10% OTM put IV - 10% OTM call IV ────────────────────────
        otm_put_strike = spot * 0.90
        otm_call_strike = spot * 1.10
        otm_put = min(
            (r for r in puts if r.iv), key=lambda r: abs(r.strike - otm_put_strike), default=None
        )
        otm_call = min(
            (r for r in calls if r.iv), key=lambda r: abs(r.strike - otm_call_strike), default=None
        )
        if otm_put and otm_call and otm_put.iv and otm_call.iv:
            result.iv_skew = otm_put.iv - otm_call.iv

        return result

    def _compute_signals(self, result: OptionsChainResult) -> None:
        """
        Detect smart money positioning from PCR, OI changes, and IV skew.
        """
        reasons = []
        bull_votes = 0
        bear_votes = 0

        # PCR interpretation
        # PCR > 1.3: contrarian bullish (excessive put buying = market near bottom)
        # PCR < 0.7: contrarian bearish (excessive call buying = complacency)
        if result.pcr_oi > 1.3:
            bull_votes += 2
            reasons.append(f"High PCR (OI={result.pcr_oi:.2f}) signals excessive put hedging — contrarian bullish.")
        elif result.pcr_oi < 0.7:
            bear_votes += 2
            reasons.append(f"Low PCR (OI={result.pcr_oi:.2f}) signals call accumulation — potential complacency.")
        elif 0.9 <= result.pcr_oi <= 1.1:
            reasons.append(f"PCR balanced ({result.pcr_oi:.2f}) — no directional bias.")

        # OI unwinding / buildup analysis
        calls = [r for r in result.chain if r.option_type == "CE"]
        puts = [r for r in result.chain if r.option_type == "PE"]

        call_oi_add = sum(r.oi_change for r in calls if r.oi_change > 0)
        put_oi_add = sum(r.oi_change for r in puts if r.oi_change > 0)
        call_oi_shed = sum(r.oi_change for r in calls if r.oi_change < 0)
        put_oi_shed = sum(r.oi_change for r in puts if r.oi_change < 0)

        if put_oi_add > call_oi_add * 1.5:
            bear_votes += 1
            reasons.append(f"Put OI being built aggressively — hedging or directional bear bets.")
        if call_oi_add > put_oi_add * 1.5:
            bull_votes += 1
            reasons.append(f"Call OI building faster than puts — bullish speculation rising.")
        if put_oi_shed > 0 and call_oi_add > 0:
            bull_votes += 1
            reasons.append("Put OI unwinding + call OI building — classic bull positioning.")

        # IV Skew
        if result.iv_skew > 0.05:
            bear_votes += 1
            reasons.append(f"Significant IV skew ({result.iv_skew:.2%}) — demand for downside protection elevated.")
        elif result.iv_skew < -0.02:
            bull_votes += 1
            reasons.append(f"Negative IV skew ({result.iv_skew:.2%}) — upside calls in demand.")

        # Max pain vs spot
        if result.max_pain > 0:
            mp_dist = (result.max_pain - result.spot_price) / result.spot_price
            if abs(mp_dist) < 0.02:
                reasons.append(f"Spot near max pain ({result.max_pain:.0f}) — expect pinning action near expiry.")
            elif mp_dist > 0.05:
                bull_votes += 1
                reasons.append(f"Max pain ({result.max_pain:.0f}) significantly above spot — gravity pull up.")
            elif mp_dist < -0.05:
                bear_votes += 1
                reasons.append(f"Max pain ({result.max_pain:.0f}) below spot — potential drift down.")

        # Volatility breakout: IV vs historical vol
        if result.atm_iv > 0.30:
            result.vol_breakout_prob = min(1.0, result.atm_iv / 0.50)
            reasons.append(f"ATM IV elevated ({result.atm_iv:.1%}) — market pricing large move.")

        # Final signal
        if bull_votes > bear_votes + 1:
            result.smart_money_signal = "BULLISH"
        elif bear_votes > bull_votes + 1:
            result.smart_money_signal = "BEARISH"
        else:
            result.smart_money_signal = "NEUTRAL"

        result.signal_reasons = reasons

    # ── Utilities ─────────────────────────────────────────────────────────────

    @staticmethod
    def _next_expiry() -> date:
        """Return the next weekly NSE expiry (Thursday)."""
        today = date.today()
        days_ahead = 3 - today.weekday()  # Thursday = 3
        if days_ahead <= 0:
            days_ahead += 7
        return today + timedelta(days=days_ahead)
