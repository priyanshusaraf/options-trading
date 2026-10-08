"""Gold Month-Turn — own MCX gold across the turn of the calendar month only.

Idea (self-derived from the 2019-2026 MCX-proxy research on GOLDPETAL): gold's
returns are not spread evenly over the month. The last few sessions of a month
are weak and the first two sessions of the next month are strong, in rupees AND
in pure USD, before and after 2024. Holding gold from the last bar of the last
business day of a month to the first open of the 3rd session of the new month
(~2.5 sessions incl. three nights) earned, gross per month:

                    2019-23 (IS)             2024-26 (OOS)
    INR proxy    +63 bps (t 2.7, hit 62%)    +77 bps (t 2.7, hit 65%)
    USD spot     +47 bps (t ~2.4)            +67 bps
    random 2.5-session long windows, same periods: +14 / +33 bps (INR)
    p(random timing >= TOM): 0.006 IS / 0.10 OOS (INR); 0.025 / 0.12 (USD)

So the window earns ~45-50 bps a month MORE than a random window of the same
length in both periods — the excess did not grow with the 2024-26 bull market,
which is what separates it from plain long exposure. It is in the market only
~12% of the time and pays the ~15 bps GOLDPETAL round trip once a month against a
~60-75 bps average gross trade. Plausible drivers (not proven here): month-start
allocation flows into gold products and month-end rebalancing / COMEX option
expiry pressure in the last week.

Engine results (app.backtest.engine, 1 lot, full Zerodha MCX charges + slippage
per side, 60m bars, defaults; IS = 2019-2023, OOS = 2024-01 -> 2026-10):
    GOLDPETAL   IS +Rs852 (PF 1.71, 57 trades, DD Rs277) | OOS +Rs1,528 (PF 2.01, 29, DD Rs1,033)
    GOLDGUINEA  IS +Rs7.2k (PF 1.77)                     | OOS +Rs13.2k (PF 2.13)
    GOLDM       IS +Rs111k (PF 2.04)                     | OOS +Rs186k (PF 2.35)
    every calendar year 2019-2026 positive on all three; 15m/30m agree; at 2x
    slippage GOLDPETAL IS +Rs695 / OOS +Rs1,341. Buy-and-hold GOLDPETAL earned
    Rs2,730 IS / Rs7,787 OOS for ~100% exposure (B&H x 12% exposure: Rs335 / Rs912).
    The same trades measured on USD spot: +40 bps (t 2.1) IS / +89 bps (t 2.9) OOS.

Layers (each a param so its contribution can be measured):
  L1  long the month turn (default): entry decision on the bar
      `entry_bars_before_close` bars before the close of the LAST BUSINESS DAY of
      the month (fills at the next bar's open, inside the session); exit after
      `hold_sessions` sessions of the new month — default `exit_at="next_session"`
      decides on the following session's first bar ending >= `entry_minute`
      (09:30 IST, inside the live engine's window; keeps the overnight);
      `"next_open"` decides on the H-th session's last bar so the engine fills at
      the next first open (backtest-only timing — a live engine drops a signal
      from the session's last candle); `"close"` exits one bar before the H-th
      session's close (gives up the last night — it lost OOS).
  L2  month-end short (off by default, `short_bday` = None): short on the
      `short_bday`-th last business day when the market is stretched up
      (5-session return z >= `short_z`), cover one bar before the long entry.
      Rejected: across 16 engine configs (k 4-7, z -inf/0/0.5/1) its IS
      contribution was small and non-monotonic (-Rs215 .. +Rs474) and the
      unconditional version lost OOS (-Rs300 .. -Rs1,400). Kept as a switch so
      the claim can be re-tested on real MCX data.

Calendar: "last business day" = the last Monday-Friday of the month (the
exchange calendar is known in advance — no look-ahead). If MCX is shut that day
the month is skipped. Holds are counted in observed sessions.

Regime: any — a calendar/flow effect, not a trend or reversion signal. It was
positive in every calendar year 2019-2026 on the proxy, including the flat 2021
and the 2026 drawdown (gold fell ~25% from its January 2026 peak).

Independent verification (lead researcher, research/commodity/verify_gold_month_turn.py):
  * futures carry: the proxy is SPOT gold; an MCX futures long also loses the
    futures premium as it decays to spot (~6.5%/yr ≈ 1.8 bps per calendar day;
    the average hold is ~4 calendar days). Carry-adjusted GOLDPETAL 60m: IS
    +Rs670 / OOS +Rs1,301 — still positive;
  * UNSEEN data 2005-2018 (USD daily, close of the last business day -> open of
    the 3rd business day): +16.6 bps a month (t 1.3), only +7.5 bps above random
    windows of the same length — versus +41 bps excess in 2019-23 and +20 bps in
    2024-26 with the identical daily method. The effect is real-looking but much
    weaker outside the discovery period; on GOLDPETAL (~15 bps round trip) the
    2005-2018 version would have been roughly break-even after costs. Treat it as
    a LOW-CONVICTION calendar overlay, preferably on GOLDGUINEA / GOLDM (lower
    cost per gram).
  * MCX gold contracts expire around the month turn — trade the contract that
    stays live through the hold (it carries the premium accounted for above).

Limitations: one trade a month, so samples are small (58 IS / 34 OOS months);
the profit per 1 g lot is a few rupees per trade (GOLDGUINEA / GOLDM carry the
same edge at lower cost per gram); built on a Dukascopy XAUUSD x USDINR proxy, not
MCX prints — re-validate on Kite MCX candles before any use.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.strategy.ta import atr, bar_minutes, bars_to_session_close, minutes_of_day, session_key

from .base import Strategy


def _bdays_left_in_month(dates: pd.Series) -> pd.Series:
    """Business days (Mon-Fri) remaining in the calendar month AFTER each date:
    0 on the last business day, 4 on the 5th-last. Calendar only (no data needed)."""
    d = pd.to_datetime(dates).dt.normalize()
    uniq = pd.DatetimeIndex(d.unique())
    mend = uniq + pd.offsets.MonthEnd(0)
    left = np.array([np.busday_count((u + pd.Timedelta(days=1)).date(), (m + pd.Timedelta(days=1)).date())
                     for u, m in zip(uniq, mend)], dtype=int)
    return d.map(pd.Series(left, index=uniq)).astype(int)


class GoldMonthTurn(Strategy):
    key = "gold_month_turn"
    display_name = "Gold Month-Turn (calendar long)"
    default_params = {
        "entry_bars_before_close": 1,   # decide this many bars before the last-bday close
        "hold_sessions": 2,             # sessions of the new month held
        "exit_at": "next_session",      # next_session (live-compatible) | next_open | close
        "entry_minute": 570,            # next_session exit: first bar ending >= 09:30 IST
        "short_bday": None,             # L2: k-th last business day to short on (None = off)
        "short_z": 0.5,                 # L2: 5-session return z needed to short
        "session_close": None,          # IST minutes; None = MCX schedule (23:30 / 23:55)
    }
    session_flat = False
    warmup_columns = ("atr",)
    min_history_days = 40

    def compute(self, df: pd.DataFrame, entry_bars_before_close: int = 1, hold_sessions: int = 2,
                exit_at: str = "next_session", entry_minute: int = 570,
                short_bday: int | None = None, short_z: float = 0.5,
                session_close: int | None = None) -> pd.DataFrame:
        out = df.copy()
        n = len(out)
        key = session_key(out)
        to_close = bars_to_session_close(out, session_close).to_numpy()
        left = _bdays_left_in_month(out["date"]).to_numpy()
        sess_ids = pd.Series(np.arange(key.nunique()), index=sorted(key.unique()))
        bar_sess = key.map(sess_ids).to_numpy()
        k = max(1, int(entry_bars_before_close))

        # L1 — long entry on the last business day of the month, k bars before close
        long_entry = (left == 0) & (to_close == k)

        # exit H sessions after the entry session
        H = max(1, int(hold_sessions))
        last_entry = pd.Series(np.where(long_entry, bar_sess, np.nan)).ffill().to_numpy()
        since = bar_sess - last_entry
        if exit_at == "close":
            long_exit = (since >= H) & (to_close == 1)
        elif exit_at == "next_session":
            bar_end = (minutes_of_day(out) + bar_minutes(out)).to_numpy()
            late = pd.Series(bar_end >= int(entry_minute), index=out.index)
            first_late = (late & (late.astype(int).groupby(key).cumsum() == 1)).to_numpy()
            long_exit = (since >= H + 1) & first_late
        else:   # next_open: decide on the H-th session's last bar -> fills at the next open
            long_exit = (since >= H) & (to_close == 0)
        long_exit = np.nan_to_num(long_exit, nan=False).astype(bool)

        # L2 — optional month-end short when stretched up; covered before the long entry
        short_entry = np.zeros(n, dtype=bool)
        short_exit = np.zeros(n, dtype=bool)
        z5 = np.full(n, np.nan)
        if short_bday is not None and int(short_bday) >= 2:
            g = out.groupby(key, sort=True)
            s_close = g["close"].last()
            sd = np.log(s_close).diff().rolling(20, min_periods=15).std()
            ref = s_close.shift(5)          # close of the session 5 before the current one
            # current session j uses completed sessions only: ref_j = close[j-5], sd from j-1
            ref_b = key.map(ref).to_numpy(dtype=float)
            sd_b = key.map(sd.shift(1)).to_numpy(dtype=float)
            z5 = np.log(out["close"].to_numpy(float) / ref_b) / (sd_b * np.sqrt(5.0))
            short_entry = (left == int(short_bday) - 1) & (to_close == k) & (z5 >= float(short_z))
            short_exit = (left == 0) & (to_close == k + 1)
            # failsafe: never carry the short past the month turn
            short_exit |= (left > int(short_bday)) & (to_close == 0)
            short_entry = np.nan_to_num(short_entry, nan=False).astype(bool)

        out["atr"] = atr(out, 14)
        out["bdaysLeft"] = left
        out["z5"] = z5
        out["longEntry"] = long_entry.astype(bool)
        out["shortEntry"] = short_entry
        out["longExit"] = long_exit
        out["shortExit"] = short_exit.astype(bool)
        return out


STRATEGY = GoldMonthTurn()
