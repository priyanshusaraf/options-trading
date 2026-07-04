"""#19: re-anchor a live ledger that has drifted from the real Kite account (the
2026-07-03 divergence — internal cash ₹47,159 / baseline ₹23,706 vs a real ₹22,757
account). Pure planner; the script that reads Kite + writes the DB wraps it."""
import pytest

from app.engine.ledger_reconcile import plan_reanchor


def test_reanchor_rebases_a_flat_ledger_to_the_real_equity():
    new, _ = plan_reanchor(real_equity=22757.30, cash=47159.57, initial_capital=50000.0,
                           realized_pnl=-2840.43, account_baseline=23705.9, open_entry_cost=0.0)
    assert new == {"initial_capital": 22757.30, "cash": 22757.30,
                   "realized_pnl": 0.0, "account_baseline": 22757.30}


def test_reanchor_preserves_the_flat_ledger_invariant():
    # cash == initial + realized − Σ(open); flat → cash == initial + realized
    new, _ = plan_reanchor(real_equity=30000.0, cash=1.0, initial_capital=1.0,
                           realized_pnl=0.0, account_baseline=None, open_entry_cost=0.0)
    assert new["cash"] == pytest.approx(new["initial_capital"] + new["realized_pnl"])


def test_reanchor_refuses_when_positions_are_open():
    # re-anchoring while holding a position would corrupt the invariant — refuse.
    with pytest.raises(ValueError):
        plan_reanchor(real_equity=22757.30, cash=47159.57, initial_capital=50000.0,
                      realized_pnl=-2840.43, account_baseline=23705.9, open_entry_cost=9925.11)


def test_reanchor_refuses_nonpositive_equity():
    with pytest.raises(ValueError):
        plan_reanchor(real_equity=0.0, cash=1.0, initial_capital=1.0, realized_pnl=0.0,
                      account_baseline=1.0, open_entry_cost=0.0)


def test_reanchor_notes_describe_the_change():
    _, notes = plan_reanchor(real_equity=22757.30, cash=47159.57, initial_capital=50000.0,
                             realized_pnl=-2840.43, account_baseline=23705.9, open_entry_cost=0.0)
    joined = "\n".join(notes)
    assert "47,159" in joined and "22,757" in joined   # shows before → after
