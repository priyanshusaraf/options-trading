"""#17 WIRING: the runner's throttled reconcile pass must also run the adopt-pending-
entries sweep, so a bot entry that filled late is brought into the book — not only the
orphan reconciliation. Broker-level adoption is covered in test_live_broker.py."""
from app.db.session import init_db
from app.engine.runner import EngineRunner


def test_reconcile_pass_runs_the_adoption_sweep():
    init_db(reset=True)
    r = EngineRunner()
    calls = []
    r.broker.adopt_pending_entries = lambda now: calls.append(now) or []
    r.broker.reconcile_orphans = lambda now: []
    r._next_reconcile_epoch = 0.0            # force the ~30s throttle open
    r._maybe_reconcile_orphans()
    assert calls                             # the adoption sweep ran this pass
