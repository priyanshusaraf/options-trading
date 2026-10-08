"""
ReplayProvider — replays REAL historical bars through the live engine.

Not used by the provider factory (never a default): `scripts/replay_mcx.py`
installs it explicitly so `EngineRunner` runs its real live path (candle fetch,
stale-signal / session / entry-window guards, option picker, routing, paper fills,
mark-to-market, SL/TP, overnight rules, capital ledger) on recorded prices, with
no Kite login and no network.

Data contract: one DataFrame per instrument key, indexed by the bar START time
(naive IST wall-clock, Kite's convention), columns open/high/low/close[/volume],
at `base_minutes` resolution (15 for the Moneycontrol MCX prints).

NO LOOK-AHEAD — the invariants the offline test pins:
  * `get_candles` returns only bars COMPLETED by the clock (bar end <= now),
    like Kite (which drops the still-forming bar), and only bars that started
    within `days` calendar days of now.
  * `get_ltp` at clock t inside a bar walks the standard OHLC path of THAT bar:
    open for the first 5 min, then the extreme nearer the open, then the other
    extreme, then the close in its last minute (bullish bar O→L→H→C, bearish
    O→H→L→C). Between bars it is the last completed bar's close. A bar's
    extremes therefore only show up once that part of the bar has "printed";
    candle data never reveals an incomplete bar.
  * option volatility comes from the trailing 20-daily-close realised vol keyed by
    the day it becomes AVAILABLE (`backtest/premium._daily_rv_by_date`), so pricing
    on day d never uses day d's close.

Option chain (synthetic — MCX option history is unavailable):
  * expiries: one per month, supplied by the caller as (option_expiry,
    futures_expiry) pairs; `pick_expiry` (providers/base.py) honours `min_dte`
    exactly as KiteProvider does.
  * strikes: ATM ± 10 × `inst.strike_step` around the LTP (as KiteProvider).
  * premium: Black-Scholes (`options/pricing.bs_price`, the platform's model) on
    clamp(RV20, 10%, 200%) × `iv_rv_multiplier`, T to the expiry at 23:30 IST.
  * bid/ask = mid × (1 ∓ spread_pct/2), LTP = mid, OI = `oi` (passes the picker).
  * the option's underlying is its OWN futures month: the stitched front-month
    price plus the roll gap(s) still ahead of it (`rolls`), so a held option
    never jumps when the stitched series rolls to the next contract. The chain's
    `spot` is the front-month LTP, exactly like KiteProvider (which quotes the
    near future even for a later-month chain).
"""
from __future__ import annotations

import bisect
import math
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

import pandas as pd

from app.core import market_hours
from app.core.instruments import Instrument
from app.options.pricing import bs_price
from app.providers.base import (Candle, MarketDataProvider, OptionChain, OptionQuote,
                                pick_expiry)

_MONTH = ["", "JAN", "FEB", "MAR", "APR", "MAY", "JUN",
          "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
_INTERVAL_MIN = {"minute": 1, "3minute": 3, "5minute": 5, "10minute": 10,
                 "15minute": 15, "30minute": 30, "60minute": 60}
MCX_OPTION_EXPIRY_TIME = time(23, 30)


@dataclass(frozen=True)
class Roll:
    """A front-month switch in a stitched futures series: from `at` on, the series
    quotes the next contract; `old_expiry` is the expiring contract's expiry date;
    `gap_pts` = new − old contract price at the switch."""
    at: datetime
    old_expiry: date
    gap_pts: float


class _Series:
    """One instrument's bars as numpy-friendly arrays + resample caches."""

    def __init__(self, df: pd.DataFrame, base_minutes: int) -> None:
        df = df.sort_index()
        df = df[~df.index.duplicated(keep="last")]
        self.base = int(base_minutes)
        self.starts = [t.to_pydatetime() for t in df.index]
        self.o = df["open"].astype(float).tolist()
        self.h = df["high"].astype(float).tolist()
        self.l = df["low"].astype(float).tolist()
        self.c = df["close"].astype(float).tolist()
        vol = (df["volume"].astype(float).fillna(0.0) if "volume" in df.columns
               else pd.Series(0.0, index=df.index))
        # all-zero volume (Moneycontrol prints carry none) -> constant 1.0: a
        # volume-weighted indicator then degrades to equal weights, never 0/0.
        if float(vol.abs().sum()) == 0.0:
            vol = pd.Series(1.0, index=df.index)
        self.v = vol.tolist()
        self.ends = [s + timedelta(minutes=self.base) for s in self.starts]
        self._resampled: dict[int, tuple[list, list, list]] = {}

    def resampled(self, minutes: int) -> tuple[list[Candle], list[datetime], list[datetime]]:
        """(candles, starts, ends) at `minutes`, bars anchored at 09:00 IST like
        Kite's MCX intraday candles; a bar ends when its last constituent ends."""
        if minutes == self.base:
            key = minutes
            if key not in self._resampled:
                cs = [Candle(s, o, h, l, c, v) for s, o, h, l, c, v in
                      zip(self.starts, self.o, self.h, self.l, self.c, self.v)]
                self._resampled[key] = (cs, self.starts, self.ends)
            return self._resampled[key]
        if minutes not in self._resampled:
            groups: dict[datetime, list[int]] = {}
            order: list[datetime] = []
            for i, s in enumerate(self.starts):
                anchor = s.replace(hour=9, minute=0, second=0, microsecond=0)
                k = int((s - anchor).total_seconds() // 60 // minutes)
                gs = anchor + timedelta(minutes=k * minutes)
                if gs not in groups:
                    groups[gs] = []
                    order.append(gs)
                groups[gs].append(i)
            cs, st, en = [], [], []
            for gs in order:
                ix = groups[gs]
                cs.append(Candle(gs, self.o[ix[0]], max(self.h[i] for i in ix),
                                 min(self.l[i] for i in ix), self.c[ix[-1]],
                                 sum(self.v[i] for i in ix)))
                st.append(gs)
                en.append(min(gs + timedelta(minutes=minutes), self.ends[ix[-1]])
                          if ix[-1] + 1 >= len(self.starts)
                          or self.starts[ix[-1] + 1].date() != gs.date()
                          else gs + timedelta(minutes=minutes))
            self._resampled[minutes] = (cs, st, en)
        return self._resampled[minutes]

    def price_at(self, t: datetime) -> float | None:
        """Tape price at `t` (see module doc): intra-bar OHLC path, else the last
        completed close. None before the first bar."""
        i = bisect.bisect_right(self.starts, t) - 1
        if i < 0:
            return None
        if t < self.ends[i]:
            m = (t - self.starts[i]).total_seconds() / 60.0
            o, h, l, c = self.o[i], self.h[i], self.l[i], self.c[i]
            first, second = (l, h) if c >= o else (h, l)
            if m < 5:
                return o
            if m < 10:
                return first
            if m < self.base - 1:
                return second
            return c
        return self.c[i]


class ReplayProvider(MarketDataProvider):
    name = "replay"

    def __init__(self, frames: dict[str, pd.DataFrame], *, base_minutes: int = 15,
                 option_expiries: dict[str, list[tuple[date, date]]] | None = None,
                 rolls: dict[str, list[Roll]] | None = None,
                 spread_pct: float = 0.02, iv_rv_multiplier: float = 1.15,
                 risk_free_rate: float = 0.065, oi: int = 5000,
                 start: datetime | None = None) -> None:
        from app.backtest.premium import _daily_rv_by_date
        self.series = {k: _Series(df, base_minutes) for k, df in frames.items()}
        self.base = int(base_minutes)
        self.option_expiries = {k: sorted(v) for k, v in (option_expiries or {}).items()}
        self.rolls = {k: sorted(v, key=lambda r: r.at) for k, v in (rolls or {}).items()}
        self.spread_pct = float(spread_pct)
        self.mult = float(iv_rv_multiplier)
        self.r = float(risk_free_rate)
        self.oi = int(oi)
        self._rv = {k: _daily_rv_by_date(s.resampled(s.base)[0]) for k, s in self.series.items()}
        first = min((s.starts[0] for s in self.series.values() if s.starts), default=None)
        self._now: datetime = start or (first + timedelta(minutes=1) if first else datetime(2000, 1, 1))

    # ── clock ─────────────────────────────────────────────────────────────
    def is_authenticated(self) -> bool:
        return True

    def now(self) -> datetime:
        return self._now

    def set_now(self, t: datetime) -> None:
        self._now = t

    def advance(self) -> bool:
        """Jump to 1 minute after the next bar start of any instrument (the first
        tick at which that bar's predecessor is a completed candle). False at end."""
        nxt = None
        for s in self.series.values():
            i = bisect.bisect_right(s.starts, self._now)
            if i < len(s.starts):
                cand = s.starts[i] + timedelta(minutes=1)
                nxt = cand if nxt is None or cand < nxt else nxt
        if nxt is None:
            return False
        self._now = nxt
        return True

    def is_tradable_now(self, inst: Instrument) -> bool:
        # same gate as KiteProvider: the venue session clock, not data availability
        return (market_hours.is_open(inst.spot_exchange, self._now)
                or market_hours.is_open(inst.segment, self._now))

    # ── underlying ────────────────────────────────────────────────────────
    def get_candles(self, inst: Instrument, interval: str, days: int,
                    end: str | None = None) -> list[Candle]:
        s = self.series.get(inst.key)
        if s is None:
            return []
        minutes = _INTERVAL_MIN.get(interval)
        if minutes is None or minutes < s.base or minutes % s.base:
            return []          # finer than the recorded bars ('day' unsupported)
        cs, starts, ends = s.resampled(minutes)
        now = self._now
        lo = bisect.bisect_left(starts, now - timedelta(days=days))
        hi = bisect.bisect_right(starts, now)          # started at/before now …
        while hi > lo and ends[hi - 1] > now:          # … and COMPLETED by now
            hi -= 1
        out = cs[lo:hi]
        if end:
            ed = date.fromisoformat(end)
            out = [c for c in out if c.ts.date() <= ed]
        return list(out)

    def get_ltp(self, inst: Instrument) -> float | None:
        s = self.series.get(inst.key)
        return s.price_at(self._now) if s else None

    # ── options ───────────────────────────────────────────────────────────
    def _sigma(self, key: str, day: date) -> float | None:
        from app.backtest.premium import _sigma_for
        rv = self._rv.get(key) or {}
        sig = _sigma_for(rv, day, self.mult)
        if sig is None:     # a no-bar day (e.g. weekend tick): last value known before it
            past = [d for d in rv if d <= day]
            if past:
                sig = _sigma_for(rv, max(past), self.mult)
        return sig

    def _fut_expiry_for(self, key: str, opt_expiry: date) -> date:
        for oe, fe in self.option_expiries.get(key, []):
            if oe == opt_expiry:
                return fe
        return opt_expiry

    def underlying_for(self, key: str, opt_expiry: date, t: datetime | None = None) -> float | None:
        """The futures price an option of `opt_expiry` sits on: the stitched
        front-month tape plus every roll gap still ahead of now whose expiring
        contract is earlier than this option's futures month."""
        t = t or self._now
        s = self.series.get(key)
        px = s.price_at(t) if s else None
        if px is None:
            return None
        fut = self._fut_expiry_for(key, opt_expiry)
        adj = sum(r.gap_pts for r in self.rolls.get(key, [])
                  if t < r.at and r.old_expiry < fut)
        return px + adj

    def _T(self, expiry: date) -> float:
        exp = datetime.combine(expiry, MCX_OPTION_EXPIRY_TIME)
        return max((exp - self._now).total_seconds() / (365 * 86400), 0.5 / 365)

    def _premium(self, key: str, F: float, strike: float, expiry: date, otype: str) -> float | None:
        sigma = self._sigma(key, self._now.date())
        if sigma is None:
            return None
        if self._now >= datetime.combine(expiry, MCX_OPTION_EXPIRY_TIME):
            px = max(0.0, F - strike) if otype == "CE" else max(0.0, strike - F)
        else:
            px = bs_price(F, strike, self._T(expiry), self.r, sigma,
                          "c" if otype == "CE" else "p")
        return round(max(px, 0.05) / 0.05) * 0.05

    @staticmethod
    def symbol(inst: Instrument, expiry: date, strike: float, otype: str) -> str:
        k = int(strike) if float(strike).is_integer() else strike
        return f"{inst.option_name}{expiry:%y}{_MONTH[expiry.month]}{k}{otype}"

    def get_option_chain(self, inst: Instrument, min_dte: int | None = None) -> OptionChain | None:
        today = self._now.date()
        exps = [oe for oe, _ in self.option_expiries.get(inst.key, []) if oe >= today]
        if not exps:
            return None
        expiry = pick_expiry(exps, today, min_dte)
        spot = self.get_ltp(inst)
        F = self.underlying_for(inst.key, expiry)
        if not spot or not F:
            return None
        step = inst.strike_step
        atm = round(spot / step) * step
        quotes: list[OptionQuote] = []
        for k in range(-10, 11):
            strike = atm + k * step
            if strike <= 0:
                continue
            for otype in ("CE", "PE"):
                mid = self._premium(inst.key, F, strike, expiry, otype)
                if mid is None:
                    return None        # RV warm-up: no quotable chain yet
                half = self.spread_pct / 2.0
                bid = max(0.05, round(mid * (1 - half), 2))
                ask = round(mid * (1 + half), 2)
                quotes.append(OptionQuote(
                    instrument_key=inst.key,
                    tradingsymbol=self.symbol(inst, expiry, strike, otype),
                    exchange=inst.segment, strike=float(strike), expiry=expiry,
                    option_type=otype, lot_size=inst.lot_size,
                    ltp=round(mid, 2), bid=bid, ask=ask,
                    volume=self.oi // 4, oi=self.oi))
        return OptionChain(instrument_key=inst.key, spot=spot, expiry=expiry, quotes=quotes)

    def option_ltp(self, inst: Instrument, tradingsymbol: str, strike: float,
                   expiry: date, option_type: str) -> float | None:
        F = self.underlying_for(inst.key, expiry)
        if F is None:
            return None
        return self._premium(inst.key, F, float(strike), expiry, option_type)
