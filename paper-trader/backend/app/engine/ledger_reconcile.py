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
