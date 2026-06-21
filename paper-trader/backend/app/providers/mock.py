"""
MockProvider — a fully self-contained synthetic market.

It exists so the entire platform (signals -> picker -> paper fills -> exits ->
analytics -> dashboard) can run and prove itself with NO Kite account.

What it fakes, and how it stays realistic:
  - Per-instrument price paths use regime-switching drift on top of vol-scaled
    noise, so EMA-slope flips and z-score crosses of ±entry_z actually happen
    (both winning and losing trades emerge naturally).
  - Option chains are Black-Scholes priced off each instrument's vol with a mild
    smile; open interest peaks at-the-money and bid/ask spreads widen with
    moneyness — so the liquidity filter and delta-targeting in the picker have
    real structure to bite on.
  - A single shared cursor is the simulated clock; `advance()` steps one candle
    forward for every instrument at once. `now()` returns the simulated time, so
    time-to-expiry and timestamps are internally consistent.

Everything is seeded (config PT_MOCK_SEED) → identical run every time.
"""
from __future__ import annotations

import math
from datetime import date, datetime, time, timedelta

import numpy as np

from app.core.config import get_settings
from app.core.instruments import Instrument, all_instruments
from app.options.pricing import bs_price
from app.providers.base import Candle, MarketDataProvider, OptionChain, OptionQuote

_MONTH = ["", "JAN", "FEB", "MAR", "APR", "MAY", "JUN",
          "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


def _oi_base(inst: Instrument) -> int:
    if inst.segment == "NFO":
        return 9000
    if inst.segment == "BFO":
        return 7000
    if inst.segment == "NCDEX":
        return 800
    if inst.key in {"GOLDM", "SILVERM", "CRUDEOIL", "NATURALGAS", "COPPERM"}:
        return 3500
    return 1500  # ZINC, LEAD (thin MCX)


class MockProvider(MarketDataProvider):
    name = "mock"

    def __init__(self) -> None:
        self.s = get_settings()
        self.minutes = self.s.candle_minutes
        self.per_day = max(1, 375 // self.minutes)
        self.n = max(self.s.mock_history_days * self.per_day, 800)
        self.r = self.s.risk_free_rate

        self._times = self._gen_times(self.n, self.minutes)
        self._expiries = self._gen_expiries(
            self._times[0].date(), self._times[-1].date() + timedelta(days=21))

        self._candles: dict[str, list[Candle]] = {}
        for idx, inst in enumerate(all_instruments()):
            self._candles[inst.key] = self._gen_candles(inst, idx)

        # start with enough history behind the cursor for EMA50/z50 warmup,
        # leaving a long runway of future candles to advance into.
        self._cursor = min(160, self.n - 1)

    # ── clock ─────────────────────────────────────────────────────────────
    def is_authenticated(self) -> bool:
        return True

    def now(self) -> datetime:
        return self._times[self._cursor]

    def advance(self) -> bool:
        if self._cursor >= self.n - 1:
            return False
        self._cursor += 1
        return True

    # ── underlying ────────────────────────────────────────────────────────
    def _spot(self, inst: Instrument) -> float:
        return self._candles[inst.key][self._cursor].close

    def get_candles(self, inst: Instrument, interval: str, days: int,
                    end: str | None = None) -> list[Candle]:
        window = max(days * self.per_day, self.s.z_length + self.s.ema_length + 10)
        lo = max(0, self._cursor - window + 1)
        out = self._candles[inst.key][lo: self._cursor + 1]
        # backtest-only date anchoring: when an explicit end date is given, drop
        # any candle dated after it so a custom [start,end] window ends at `end`,
        # not at the simulated "now" (mirrors the live KiteProvider date range).
        if end:
            ed = date.fromisoformat(end)
            out = [c for c in out if c.ts.date() <= ed]
        return out

    def get_ltp(self, inst: Instrument) -> float | None:
        return self._spot(inst)

    def get_live_price(self, inst: Instrument) -> float:
        # display-only jitter for the expanded live view; does NOT affect P&L
        spot = self._spot(inst)
        rng = np.random.default_rng(self._cursor * 131 + hash(inst.key) % 9973)
        return round(spot * (1 + rng.normal(0, 0.0004)), 2)

    # ── options ───────────────────────────────────────────────────────────
    def _active_expiry(self, now: datetime) -> date:
        for e in self._expiries:
            if (e - now.date()).days >= 1:
                return e
        return self._expiries[-1]

    def _T(self, expiry: date, now: datetime) -> float:
        expiry_dt = datetime.combine(expiry, time(15, 30))
        years = (expiry_dt - now).total_seconds() / (365 * 86400)
        return max(years, 0.5 / 365)

    def _sigma(self, inst: Instrument, strike: float, spot: float) -> float:
        m = (strike - spot) / spot
        return inst.mock_vol * (1.0 + 0.7 * m * m)  # mild symmetric smile

    def _symbol(self, inst: Instrument, expiry: date, strike: float, otype: str) -> str:
        return f"{inst.option_name}{expiry:%y}{_MONTH[expiry.month]}{int(strike)}{otype}"

    def get_option_chain(self, inst: Instrument) -> OptionChain | None:
        now = self.now()
        spot = self._spot(inst)
        expiry = self._active_expiry(now)
        T = self._T(expiry, now)
        step = inst.strike_step
        atm = round(spot / step) * step
        base_oi = _oi_base(inst)
        rng = np.random.default_rng(self._cursor * 7919 + (hash(inst.key) % 9973))

        quotes: list[OptionQuote] = []
        for k in range(-10, 11):
            strike = atm + k * step
            if strike <= 0:
                continue
            m = abs(strike - spot) / spot
            oi = int(base_oi * math.exp(-((m / 0.035) ** 2)) * rng.uniform(0.85, 1.15))
            vol = int(oi * rng.uniform(0.15, 0.6))
            rel_spread = 0.004 + 2.0 * m
            for otype, flag in (("CE", "c"), ("PE", "p")):
                sigma = self._sigma(inst, strike, spot)
                px = bs_price(spot, strike, T, self.r, sigma, flag)
                ltp = round(max(px, 0.05) / 0.05) * 0.05
                half = ltp * rel_spread / 2
                quotes.append(OptionQuote(
                    instrument_key=inst.key,
                    tradingsymbol=self._symbol(inst, expiry, strike, otype),
                    exchange=inst.segment,
                    strike=float(strike),
                    expiry=expiry,
                    option_type=otype,
                    lot_size=inst.lot_size,
                    ltp=round(ltp, 2),
                    bid=round(max(ltp - half, 0.05), 2),
                    ask=round(ltp + half, 2),
                    volume=vol,
                    oi=oi,
                ))
        return OptionChain(instrument_key=inst.key, spot=spot, expiry=expiry, quotes=quotes)

    def option_ltp(self, inst: Instrument, tradingsymbol: str, strike: float,
                   expiry: date, option_type: str) -> float | None:
        now = self.now()
        spot = self._spot(inst)
        T = self._T(expiry, now)
        flag = "c" if option_type == "CE" else "p"
        sigma = self._sigma(inst, strike, spot)
        px = bs_price(spot, strike, T, self.r, sigma, flag)
        return round(max(px, 0.05) / 0.05) * 0.05

    # ── generators ────────────────────────────────────────────────────────
    def _gen_times(self, n: int, minutes: int) -> list[datetime]:
        times: list[datetime] = []
        d = date(2025, 1, 1)
        per_day = max(1, 375 // minutes)
        while len(times) < n:
            if d.weekday() < 5:  # weekdays only
                start = datetime(d.year, d.month, d.day, 9, 15)
                for k in range(per_day):
                    times.append(start + timedelta(minutes=minutes * k))
                    if len(times) >= n:
                        break
            d += timedelta(days=1)
        return times

    def _gen_expiries(self, start: date, end: date) -> list[date]:
        d = start
        while d.weekday() != 3:  # next Thursday
            d += timedelta(days=1)
        out = []
        while d <= end:
            out.append(d)
            d += timedelta(days=7)
        return out

    def _gen_candles(self, inst: Instrument, offset: int) -> list[Candle]:
        rng = np.random.default_rng(self.s.mock_seed * 1000 + offset)
        n = self.n
        candles_per_year = 252 * self.per_day
        sigma = inst.mock_vol / math.sqrt(candles_per_year)

        # Regime-switching drift so trends (and thus crossovers) form — but kept
        # weak relative to the noise term, so the series whipsaws like a real
        # market. A momentum-friendly mock would hand the strategy fake easy wins
        # and a misleading equity curve; choppiness gives realistic ~50% hit-rate
        # and genuine drawdowns. Real edge only shows up on live Kite data.
        drift = np.zeros(n)
        t = 0
        while t < n:
            length = int(rng.integers(15, 45))
            mag = rng.uniform(0.10, 0.45) * sigma
            direction = rng.choice([-1.0, 0.0, 1.0], p=[0.40, 0.20, 0.40])
            drift[t:t + length] = direction * mag
            t += length

        shocks = rng.standard_normal(n) * sigma
        rets = drift + shocks

        candles: list[Candle] = []
        price = inst.mock_spot
        for i in range(n):
            prev = price
            if i > 0:
                price = prev * math.exp(rets[i])
            o = prev if i > 0 else inst.mock_spot
            cl = price
            rng_bar = abs(rng.normal(0, 1)) * sigma * price
            hi = max(o, cl) + rng_bar * rng.uniform(0.0, 1.0)
            lo = min(o, cl) - rng_bar * rng.uniform(0.0, 1.0)
            candles.append(Candle(
                ts=self._times[i],
                open=round(o, 2), high=round(hi, 2),
                low=round(lo, 2), close=round(cl, 2),
                volume=float(int(rng.uniform(1000, 50000))),
            ))
        return candles
