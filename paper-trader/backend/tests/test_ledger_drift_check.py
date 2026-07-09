"""audit H10: the cash-invariant self-check (reconcile()) existed but ran only in
the offline dry-run — never in production. A live drift (a bad write, a partial
commit) compounded unnoticed until the owner hand-diffed against Kite. The engine
now runs it periodically and alerts on drift."""
from app.db.session import init_db
from app.engine.runner import EngineRunner


def _runner():
    init_db(reset=True)
    return EngineRunner()


def test_balanced_ledger_does_not_alert():
    r = _runner()
    r._maybe_check_ledger()
    assert r._ledger_drift_alerted is False


def test_drift_is_detected_and_alerted():
    r = _runner()
    r._maybe_check_ledger()                      # balanced first
    assert r._ledger_drift_alerted is False
    cap = r.broker.capital()
    cap.cash += 500.0                            # inject a ledger drift
    r.broker.s.commit()
    r._next_ledger_epoch = 0.0                   # clear the throttle so it re-checks
    r._maybe_check_ledger()
    assert r._ledger_drift_alerted is True


def test_drift_flag_clears_when_ledger_returns_to_balance():
    r = _runner()
    cap = r.broker.capital()
    cap.cash += 500.0
    r.broker.s.commit()
    r._maybe_check_ledger()
    assert r._ledger_drift_alerted is True
    cap.cash -= 500.0                            # corrected
    r.broker.s.commit()
    r._next_ledger_epoch = 0.0
    r._maybe_check_ledger()
    assert r._ledger_drift_alerted is False
