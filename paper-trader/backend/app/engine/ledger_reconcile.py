"""#19 — re-anchor a live ledger that has drifted from the real Kite account.

The internal `capital_state` (initial/cash/realized) is a paper-style ledger anchored at
the bot's starting capital; `account_baseline` anchors the bot-vs-you account P&L. After a
live session these can drift from the real account (2026-07-03: internal cash ₹47,159 /
baseline ₹23,706 while the real account opened at ₹22,757). Live sizing is already capped by
the real account funds, so the drift is a bookkeeping/anchor issue — but the anchor should
be reset to reality before re-arming, so bot-vs-you and the ledger read true.

Pure planner (no DB, no Kite) so it is unit-tested in isolation; `scripts/reconcile_ledger.py`
reads the real equity + current state, prints the plan, and (with --commit) writes it.
"""
from __future__ import annotations

import datetime as dt


def should_reanchor(*, is_live: bool, real_equity: float | None, internal_equity: float,
                    open_entry_cost: float, trades_today: int,
                    last_anchor_date: dt.date | None, today: dt.date,
                    tolerance: float, enabled: bool = True) -> tuple[bool, str]:
    """Decide whether TODAY's ledger should be re-anchored to the real broker equity.

    The original E0.2 auto-reanchor only fired on a ledger that had never traded, so on
    the production book (trading since 2026-07-13) it was dead code and the cockpit
    reported the synthetic ₹50k seed for three weeks. This replaces "once, ever, on a
    virgin ledger" with "once a day, before the day's first entry, when it has actually
    drifted" — which is the only window where moving the anchor cannot change the meaning
    of an in-flight session.

    Every guard fails CLOSED (no re-anchor) and returns the reason, which is logged and
    surfaced, so a ledger that silently stops tracking reality is visible rather than
    mysterious. Returns (should_reanchor, human-readable reason)."""
    if not enabled:
        return False, "auto re-anchor disabled (ledger_auto_reanchor=false)"
    if not is_live:
        return False, "not live — the paper ledger is the truth in paper mode"
    if real_equity is None or real_equity <= 0:
        return False, (f"broker equity unreadable or non-positive ({real_equity}) — "
                       f"refusing to anchor the ledger to it")
    if abs(open_entry_cost) > 0.01:
        return False, (f"book not flat (Σ open entry_cost = ₹{open_entry_cost:,.2f}) — "
                       f"re-anchoring would break the cash invariant")
    if trades_today > 0:
        return False, (f"already traded today ({trades_today} trade(s)) — moving the anchor "
                       f"mid-session would reset today's drawdown frame")
    if last_anchor_date == today:
        return False, "already re-anchored today"
    drift = real_equity - internal_equity
    if abs(drift) <= tolerance:
        return False, (f"ledger within tolerance (drift ₹{drift:,.2f} <= ₹{tolerance:,.2f})")
    return True, (f"ledger drift ₹{drift:,.2f} — internal ₹{internal_equity:,.2f} vs real "
                  f"₹{real_equity:,.2f}")


def plan_reanchor(*, real_equity: float, cash: float, initial_capital: float,
                  realized_pnl: float, account_baseline: float | None,
                  open_entry_cost: float) -> tuple[dict, list[str]]:
    """Compute a re-anchored `capital_state` from the real account equity.

    ONLY valid when FLAT (Σ open entry_cost == 0): re-anchoring while holding positions
    would break the ledger invariant `cash == initial + realized − Σ(open)`. Re-bases the
    internal ledger AND the bot-vs-you baseline to the real equity — initial = cash =
    baseline = real_equity, realized = 0 — a clean slate matching reality (mirrors the
    go-live reset). Returns (new_state, human-readable before→after notes)."""
    if abs(open_entry_cost) > 0.01:
        raise ValueError(f"not flat (Σ open entry_cost = ₹{open_entry_cost:,.2f}) — "
                         f"square off everything before re-anchoring the ledger")
    if real_equity <= 0:
        raise ValueError(f"real_equity must be positive, got {real_equity}")
    eq = round(real_equity, 2)
    new = {"initial_capital": eq, "cash": eq, "realized_pnl": 0.0, "account_baseline": eq}
    notes = [
        f"initial_capital  {initial_capital:>13,.2f} → {eq:>13,.2f}",
        f"cash             {cash:>13,.2f} → {eq:>13,.2f}",
        f"realized_pnl     {realized_pnl:>13,.2f} → {0.0:>13,.2f}",
        f"account_baseline {(account_baseline or 0.0):>13,.2f} → {eq:>13,.2f}",
    ]
    return new, notes
