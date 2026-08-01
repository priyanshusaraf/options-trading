"""C-P2 — replay closed trades under alternative exit parameters.

Why this exists: across the first 72 real trades, `TARGET` fired ZERO times. The engine's
own exits netted −₹2,927 while every rupee of profit came from the owner closing by hand.
The exit knobs were being retuned blind because nothing could answer "what would these
settings actually have produced on MY trades?".

**What this can and cannot know.** Each trade carries two scalars — MFE (best unrealised
excursion, ₹) and MAE (worst, ₹) — not a path. So:

  • "would a ₹X stop have been hit?"   → answerable (MAE reached it or it didn't)
  • "would a ₹Y target have been hit?" → answerable (MFE reached it or it didn't)
  • "which came FIRST when both were reached?" → **unknowable**

That third case is reported as an explicit band (pessimistic = stopped, optimistic =
targeted), the headline figure is always the pessimistic end, and any parameter set whose
result leans on ambiguous trades is marked `trustworthy=False`. A sweep that quietly picked
one side would manufacture exactly the false confidence that made hand-tuning fail.

Trades booked before MFE/MAE landed carry NULLs; they are EXCLUDED and counted, never
treated as "never moved" — that would drag every candidate toward the status quo and make
the parameters look irrelevant.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ReplayTrade:
    """One closed trade, as the ledger recorded it."""
    tradingsymbol: str
    direction: str
    entry_price: float
    qty: int
    mfe: float | None          # best unrealised P&L, ₹ (None = pre-telemetry)
    mae: float | None          # worst unrealised P&L, ₹ (negative)
    net_pnl: float             # what actually happened, net of charges
    charges: float = 0.0

    @property
    def notional(self) -> float:
        return abs(self.entry_price * self.qty)

    @property
    def has_telemetry(self) -> bool:
        """Trades booked before MFE/MAE landed (2026-07-24) do NOT carry NULL — the ORM
        default wrote 0.0 into both columns, so they look like perfectly flat trades. A
        real position cannot end a session having never moved a paisa in either
        direction, so mfe == mae == 0 is the missing-data marker. Reading those as "never
        moved" would make every candidate policy collapse onto the actual outcome and
        report, falsely, that the exit parameters barely matter."""
        if self.mfe is None or self.mae is None:
            return False
        return not (self.mfe == 0.0 and self.mae == 0.0)


@dataclass(frozen=True)
class ExitParams:
    """A candidate exit policy. Percentages are of ENTRY NOTIONAL, matching how the live
    engine derives stop/target prices from entry × (1 ± pct)."""
    stop_pct: float
    target_pct: float
    lock_threshold: float = 0.0    # ₹ of unrealised profit that arms the give-back floor
    lock_frac: float = 0.0         # fraction of the peak the floor keeps

    def label(self) -> str:
        base = f"SL {self.stop_pct:.3%} / TP {self.target_pct:.3%}"
        if self.lock_threshold > 0 and self.lock_frac > 0:
            base += f" / lock ₹{self.lock_threshold:,.0f}×{self.lock_frac:.0%}"
        return base


@dataclass(frozen=True)
class ReplayResult:
    reason: str
    pnl: float
    pnl_pessimistic: float
    pnl_optimistic: float
    ambiguous: bool


def replay(t: ReplayTrade, p: ExitParams) -> ReplayResult:
    """What this trade would have booked under `p`.

    Precedence mirrors the live engine: protective stop, then target, then the give-back
    lock, then — if none of them were ever reached — the outcome that actually occurred."""
    stop_rs = p.stop_pct * t.notional
    target_rs = p.target_pct * t.notional
    mfe = float(t.mfe or 0.0)
    mae = float(t.mae or 0.0)

    hit_stop = stop_rs > 0 and (-mae) >= stop_rs
    hit_target = target_rs > 0 and mfe >= target_rs

    if hit_stop and hit_target:
        # Both levels were reached at some point; the order is unknowable.
        pess = -stop_rs - t.charges
        opt = target_rs - t.charges
        return ReplayResult("AMBIGUOUS", pess, pess, opt, True)
    if hit_stop:
        v = -stop_rs - t.charges
        return ReplayResult("STOP_LOSS", v, v, v, False)
    if hit_target:
        v = target_rs - t.charges
        return ReplayResult("TARGET", v, v, v, False)

    # Give-back lock: armed once the peak cleared the threshold. It can only IMPROVE on
    # what really happened — if the actual exit already beat the floor, the floor was
    # never the binding constraint and the trade is left alone.
    if p.lock_threshold > 0 and p.lock_frac > 0 and mfe >= p.lock_threshold:
        floor = mfe * p.lock_frac - t.charges
        if floor > t.net_pnl:
            return ReplayResult("PROFIT_LOCK", floor, floor, floor, False)

    return ReplayResult("ACTUAL", t.net_pnl, t.net_pnl, t.net_pnl, False)


@dataclass
class SweepRow:
    params: ExitParams
    trades: int
    total_pnl: float                 # headline = pessimistic on every ambiguous trade
    total_pnl_pessimistic: float
    total_pnl_optimistic: float
    win_rate: float
    ambiguous_trades: int
    skipped_no_telemetry: int
    reasons: dict[str, int] = field(default_factory=dict)

    @property
    def trustworthy(self) -> bool:
        """False when more than a quarter of the sample is coin-flips, or when the
        ambiguity band is wider than the headline edge itself. Either way the ranking is
        being driven by what we cannot know, and acting on it would be tuning on noise."""
        if not self.trades:
            return False
        if self.ambiguous_trades / self.trades > 0.25:
            return False
        band = self.total_pnl_optimistic - self.total_pnl_pessimistic
        return band <= abs(self.total_pnl) or band == 0.0

    def as_dict(self) -> dict:
        return {"params": self.params.label(), "trades": self.trades,
                "total_pnl": round(self.total_pnl, 2),
                "band": [round(self.total_pnl_pessimistic, 2),
                         round(self.total_pnl_optimistic, 2)],
                "win_rate": round(self.win_rate, 4),
                "ambiguous": self.ambiguous_trades,
                "skipped_no_telemetry": self.skipped_no_telemetry,
                "trustworthy": self.trustworthy, "reasons": self.reasons}


def sweep(trades: list[ReplayTrade], grid: list[ExitParams]) -> list[SweepRow]:
    """Rank every candidate policy over the same trades. Best headline P&L first.

    Returns [] on an empty sample rather than a row of confident zeros."""
    usable = [t for t in trades if t.has_telemetry]
    skipped = len(trades) - len(usable)
    if not usable:
        return []

    rows: list[SweepRow] = []
    for p in grid:
        results = [replay(t, p) for t in usable]
        reasons: dict[str, int] = {}
        for r in results:
            reasons[r.reason] = reasons.get(r.reason, 0) + 1
        wins = sum(1 for r in results if r.pnl > 0)
        rows.append(SweepRow(
            params=p, trades=len(usable),
            total_pnl=sum(r.pnl for r in results),
            total_pnl_pessimistic=sum(r.pnl_pessimistic for r in results),
            total_pnl_optimistic=sum(r.pnl_optimistic for r in results),
            win_rate=wins / len(usable),
            ambiguous_trades=sum(1 for r in results if r.ambiguous),
            skipped_no_telemetry=skipped,
            reasons=reasons,
        ))
    return sorted(rows, key=lambda r: -r.total_pnl)


def default_grid() -> list[ExitParams]:
    """The search space around the live settings (SL 0.8%, TP 1.5%, lock ₹450×0.3).

    Targets go down to 0.4% because the first run against real trades showed TARGET
    firing zero times at every level from 1% up — the peaks simply never get there, so a
    grid that started at 1% could only ever report "targets don't work" without showing
    where they would start to."""
    out = []
    for sl in (0.004, 0.006, 0.008, 0.010, 0.015, 0.020):
        for tp in (0.004, 0.006, 0.008, 0.010, 0.015, 0.020, 0.030, 0.040):
            if tp < sl:
                continue                     # never risk more than the reward sought
            out.append(ExitParams(sl, tp))
            for thr in (100.0, 150.0, 200.0, 300.0, 450.0, 600.0):
                for frac in (0.3, 0.5, 0.7, 0.85):
                    out.append(ExitParams(sl, tp, thr, frac))
    return out


def excursion_profile(trades: list[ReplayTrade]) -> dict:
    """How far these trades actually travelled, as a fraction of entry notional.

    This is the context that makes a sweep interpretable. If the median winner peaks at
    0.3% of notional, a 3% target is not "aggressive" — it is unreachable, and no amount
    of tuning around it will ever produce a TARGET exit. That was exactly the state of
    the production book: zero TARGET exits in 72 trades."""
    usable = [t for t in trades if t.has_telemetry and t.notional > 0]
    if not usable:
        return {"trades": 0}

    def pct(vals, q):
        s = sorted(vals)
        return s[min(len(s) - 1, int(q * len(s)))]

    mfe_pct = [abs(t.mfe or 0.0) / t.notional for t in usable]
    mae_pct = [abs(t.mae or 0.0) / t.notional for t in usable]
    return {
        "trades": len(usable),
        "mfe_pct_median": pct(mfe_pct, 0.5), "mfe_pct_p75": pct(mfe_pct, 0.75),
        "mfe_pct_max": max(mfe_pct),
        "mae_pct_median": pct(mae_pct, 0.5), "mae_pct_p75": pct(mae_pct, 0.75),
        "mae_pct_max": max(mae_pct),
        "mfe_rs_median": pct([abs(t.mfe or 0.0) for t in usable], 0.5),
        "mae_rs_median": pct([abs(t.mae or 0.0) for t in usable], 0.5),
    }
