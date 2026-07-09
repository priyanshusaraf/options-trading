"""audit H14: at startup the bot never checked the reverse direction — a REAL Kite
position the ledger has no row for was invisible. It cannot safely adopt one (the
account also holds the owner's own trades, and positions() carries no bot tag), so
it surfaces untracked positions for the operator instead of touching them."""
from app.db.session import init_db
from app.engine.runner import EngineRunner


def _runner():
    init_db(reset=True)
    return EngineRunner()


def test_untracked_account_position_is_surfaced_and_alerted():
    r = _runner()
    r.provider.account_positions = lambda: [{"tradingsymbol": "NIFTY2570024000CE",
                                             "quantity": 75}]
    sent = []
    r.notifier._emit = lambda m: sent.append(m)
    untracked = r.startup_account_reconcile()
    assert untracked == ["NIFTY2570024000CE"]
    assert sent                                   # the operator was alerted


def test_flat_or_failed_read_surfaces_nothing():
    r = _runner()
    r.provider.account_positions = lambda: []      # flat account
    assert r.startup_account_reconcile() == []
    r.provider.account_positions = lambda: None     # read failed
    assert r.startup_account_reconcile() == []
