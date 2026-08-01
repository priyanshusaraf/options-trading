"""The reported equity must be the REAL account equity, not the synthetic ₹50k seed.

Production evidence (2026-08-01): the live cockpit reported ₹49,833.63 — exactly
`50,000 − realized(−166.37)` — while the real Zerodha account was a fraction of that. The
E0.2 auto-reanchor could never fire because its guards required a ledger that had NEVER
traded, and the production ledger has traded since 2026-07-13. So the anchor was wrong for
three weeks and every %-return, drawdown and equity-curve figure derived from it was wrong.

New rule: re-anchor ONCE PER DAY, before the day's first trade, when the book is flat and
the ledger has drifted from the broker beyond tolerance. That keeps the curve honest without
ever moving the anchor underneath a live session (which would silently reset intraday
drawdown semantics mid-flight).

`should_reanchor` is the pure decision; the runner is the only caller.
"""
import datetime as dt

from app.engine.ledger_reconcile import should_reanchor

TODAY = dt.date(2026, 8, 3)


def _decide(**over):
    kw = dict(is_live=True, real_equity=22_757.0, internal_equity=49_833.63,
              open_entry_cost=0.0, trades_today=0, last_anchor_date=None,
              today=TODAY, tolerance=250.0, enabled=True)
    kw.update(over)
    return should_reanchor(**kw)


def test_reanchors_a_traded_ledger_that_has_drifted():
    """THE production case: ledger has history, is flat, has not traded today, and is
    ₹27k adrift. The old guards refused this forever; it must now re-anchor."""
    ok, why = _decide()
    assert ok is True
    assert "27,076" in why or "drift" in why.lower()


def test_never_reanchors_once_the_day_has_traded():
    """Moving the anchor after entries would reset today's drawdown/profit-lock frame
    mid-session. Wait for tomorrow."""
    ok, why = _decide(trades_today=1)
    assert ok is False
    assert "traded" in why.lower()


def test_never_reanchors_while_holding_positions():
    """plan_reanchor breaks the cash invariant unless Σ(open entry_cost) == 0."""
    ok, why = _decide(open_entry_cost=9_800.0)
    assert ok is False
    assert "flat" in why.lower()


def test_only_once_per_day():
    ok, why = _decide(last_anchor_date=TODAY)
    assert ok is False
    assert "already" in why.lower()

    ok, _ = _decide(last_anchor_date=TODAY - dt.timedelta(days=1))
    assert ok is True


def test_no_op_when_the_ledger_already_matches_the_broker():
    """Within tolerance there is nothing to correct — do not churn the ledger daily."""
    ok, why = _decide(real_equity=49_900.0, internal_equity=49_833.63)
    assert ok is False
    assert "tolerance" in why.lower()

    # Just outside tolerance, it fires.
    ok, _ = _decide(real_equity=50_120.0, internal_equity=49_833.63)
    assert ok is True


def test_paper_and_mock_never_reanchor():
    ok, why = _decide(is_live=False)
    assert ok is False
    assert "live" in why.lower()


def test_unreadable_or_absurd_broker_equity_is_refused():
    """Funds that fail to read must never be interpreted as a real ₹0 account and wipe
    the anchor to zero."""
    for bad in (0.0, -1.0, None):
        ok, why = _decide(real_equity=bad)
        assert ok is False, bad
        assert "equity" in why.lower()


def test_can_be_switched_off():
    ok, why = _decide(enabled=False)
    assert ok is False
    assert "disabled" in why.lower()
