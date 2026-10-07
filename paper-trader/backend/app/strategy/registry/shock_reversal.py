"""Shock Reversal — fade a commodity's volatility-shock day for a few sessions.

Idea (self-derived from the 2019-2026 MCX-proxy research): after a session whose
return is extreme relative to its own recent daily volatility (|z| >= z_entry),
crude and natural gas have tended to give part of the move back over the next
1-3 sessions — an overreaction to inventory / weather / headline shocks. Event
study on CRUDEOILM (in-session return, next-open -> close 3 sessions later):
  up-shock  z>2: −200 bps (2019-23) / −153 bps (2024-26)
  down-shock z<−2: +147 bps (2019-23) / +145 bps (2024-26)
NATGASMINI: close-to-close up-spikes z>1.5 faded in both periods (−150 bps h3 IS,
−116 bps h1 OOS); NG down-spikes did not revert reliably.

Mechanics (all causal):
  * one value per completed session: in-session return log(close/open)
    (shock_mode="session", immune to contract-roll gaps) or close-to-close with
    the overnight gap clipped to ±gap_clip (shock_mode="close");
  * z = return / stdev(previous `z_len` session returns);
  * the decision is taken on the session's LAST bar (from the exchange schedule)
    and fills at the next session's first open; the position is held for
    `hold_sessions` sessions and closed near that session's close
    (exit_at="close": decision on the second-to-last bar → fills at the last
    bar's open) or at the following open (exit_at="next_open");
  * `side` limits it to fading up-shocks ("short"), down-shocks ("long") or both;
  * a fresh same-direction shock while in the trade can add one lot
    (pyramiding — a second shock is a bigger overreaction).

Defaults = CRUDEOILM, chosen in-sample: in-session z >= 2 vs 60 sessions, both
sides, hold 3 sessions, and only shocks AGAINST the 20-session trend (fading a
shock that extends the trend was worse; a 2nd-shock pyramid add and a 6-ATR stop
did not help). Crude IS +₹28k (PF 2.13, every IS year positive) -> OOS +₹16k
(PF 2.11, 17 trades), net of charges + slippage. For natural gas use the
`spike_fade` module (up-spikes only); gold shocks did not revert.

Regime: EXPANSION → reversion. It is the counterpart of the trend tools: it
expects the shock to be overdone, so it should be paused when a regime turns
into a persistent TREND (ADX high and rising after the shock).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.strategy.ta import atr, bars_to_session_close, session_key

from .base import Strategy


class ShockReversal(Strategy):
    key = "shock_reversal"
    display_name = "Shock Reversal (multi-session fade)"
    default_params = {
        "shock_mode": "session",      # session | close
        "gap_clip": 0.015,            # close mode: overnight gap clipped to ±1.5%
        "z_len": 60, "z_entry": 2.0,
        "side": "both",               # both | long | short
        "trend_sessions": 20,         # 0 = off; else trend = sign(close vs close N sessions ago)
        "trend_rule": "against",      # any | against (fade only counter-trend shocks) | with
        "hold_sessions": 3,
        "exit_at": "close",           # close | next_open
        "session_close": None,        # IST minutes; None = MCX schedule
    }
    pyramiding = None
    session_flat = False
    warmup_columns = ("atr",)

    def compute(self, df: pd.DataFrame, shock_mode: str = "session", gap_clip: float = 0.015,
                z_len: int = 60, z_entry: float = 2.0, side: str = "both",
                trend_sessions: int = 0, trend_rule: str = "any",
                hold_sessions: int = 3, exit_at: str = "close",
                session_close: int | None = None) -> pd.DataFrame:
        out = df.copy()
        key = session_key(out)
        to_close = bars_to_session_close(out, session_close)
        last_bar = (to_close == 0).to_numpy()

        # one row per session (values only USED on that session's last bar)
        g = out.groupby(key, sort=True)
        s_open = g["open"].first()
        s_close = g["close"].last()
        if shock_mode == "close":
            gap = np.log(s_open / s_close.shift(1)).clip(-gap_clip, gap_clip)
            ret = gap.fillna(0.0) + np.log(s_close / s_open)
        else:
            ret = np.log(s_close / s_open)
        sd = ret.rolling(int(z_len), min_periods=max(10, int(z_len) // 2)).std().shift(1)
        z = ret / sd
        sess_idx = pd.Series(np.arange(len(z)), index=z.index)

        bar_z = key.map(z).to_numpy(dtype=float)
        bar_sess = key.map(sess_idx).to_numpy()
        up_shock = last_bar & (bar_z >= z_entry)
        dn_shock = last_bar & (bar_z <= -z_entry)
        if trend_sessions and trend_rule != "any":
            # trend BEFORE the shock session: previous close vs close N sessions earlier
            prior = np.sign(s_close.shift(1) - s_close.shift(1 + int(trend_sessions)))
            bar_tr = key.map(prior).to_numpy(dtype=float)
            if trend_rule == "against":     # up-shock in a downtrend / down-shock in an uptrend
                up_shock &= bar_tr < 0
                dn_shock &= bar_tr > 0
            else:                           # "with": shock extends the prior trend
                up_shock &= bar_tr > 0
                dn_shock &= bar_tr < 0
        long_entry = dn_shock if side in ("both", "long") else np.zeros(len(out), bool)
        short_entry = up_shock if side in ("both", "short") else np.zeros(len(out), bool)

        # time exit: H sessions after the most recent shock session (per direction)
        H = max(1, int(hold_sessions))
        exit_bar = (to_close == (1 if exit_at == "close" else 0)).to_numpy()

        def sessions_since(flags: np.ndarray) -> np.ndarray:
            last = pd.Series(np.where(flags, bar_sess, np.nan)).ffill().to_numpy()
            return bar_sess - last

        since_long = sessions_since(long_entry)
        since_short = sessions_since(short_entry)
        long_exit = exit_bar & (since_long >= H)
        short_exit = exit_bar & (since_short >= H)

        out["atr"] = atr(out, 14)
        out["shockZ"] = bar_z
        out["longEntry"] = long_entry
        out["shortEntry"] = short_entry
        out["longExit"] = np.nan_to_num(long_exit, nan=False).astype(bool)
        out["shortExit"] = np.nan_to_num(short_exit, nan=False).astype(bool)
        out["longAdd"] = long_entry
        out["shortAdd"] = short_entry
        return out


STRATEGY = ShockReversal()
