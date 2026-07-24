"""E0.2 — auto-reanchor the internal ledger to the REAL Kite account equity, once, on a
fresh live account.

The equity curve is built from `EquitySnapshot` rows (`cap.cash + mtm`); `cap.cash` starts
at the synthetic ₹50k `initial_capital` (config.py). In LIVE mode the curve should start
from the real broker equity instead. Rather than change the snapshot formula, re-anchor
`capital_state` ONCE via the existing pure planner `ledger_reconcile.plan_reanchor` the
first time `_maybe_refresh_funds` sees real funds on a FRESH, untouched, FLAT ledger.

It must NEVER fire once there is any live trade history or an open position — that would
zero out real realized P&L / rewrite the curve. That case is handled by the owner via
`scripts/reconcile_ledger.py`.
"""
from app.db.session import init_db, SessionLocal
from app.db.models import CapitalState, Trade
from app.engine.runner import EngineRunner


def _runner():
    init_db(reset=True)
    return EngineRunner()


class _KiteFunds:
    name = "kite"

    def __init__(self, net=73_250.0, available=70_000.0):
        self.net = net
        self.available = available
        self.calls = 0

    def account_funds(self):
        self.calls += 1
        return {"available": self.available, "net": self.net}

    def now(self):
        import datetime as dt
        return dt.datetime.now()


def test_fresh_live_account_reanchors_to_real_equity():
    import datetime as dt
    r = _runner()
    r.provider = _KiteFunds(net=73_250.0)
    r._next_funds_epoch = 0.0

    # Simulate the engine having already touched the broker's long-lived session
    # (exactly as every real tick does via mark/snapshot) BEFORE the reanchor
    # fires, and HOLD A STRONG REFERENCE to the CapitalState instance it returns.
    # SQLAlchemy's identity map holds instances via a weak-value mapping, so a
    # write through a *different*, unrelated session can look deceptively
    # "correct" in a naive test — the moment the last strong ref to the stale
    # cached object drops out of scope, CPython's refcounting GC evicts it from
    # the identity map and the *next* .get() silently re-fetches fresh data,
    # masking the bug. Real broker code (`broker.py` cash mutations in
    # close_position/mark/snapshot) does not keep such a reference either, but a
    # correct test must hold one to deterministically exercise the exact object
    # every other broker call would have reused had this tick's cash mutation
    # landed a moment sooner — i.e. it proves whether the WRITE reached the
    # broker session's live instance, not merely the DB row.
    pre = r.broker.snapshot(dt.datetime(2026, 1, 2, 9, 0))
    assert pre.equity == 50_000.0
    cap_ref = r.broker.capital()
    assert cap_ref.initial_capital == 50_000.0

    r._maybe_refresh_funds()

    # Through a fresh SessionLocal — proves the DB row itself was written.
    with SessionLocal() as s:
        cap = s.get(CapitalState, 1)
        assert cap.initial_capital == 73_250.0
        assert cap.cash == 73_250.0
        assert cap.realized_pnl == 0.0
        assert cap.account_baseline == 73_250.0
    assert r._reanchored is True

    # THROUGH THE BROKER'S OWN (long-lived) SESSION — this is the regression guard.
    # If the reanchor were written via a *separate* session (the bug), this
    # already-cached instance would still read the stale synthetic ₹50k base.
    assert cap_ref.initial_capital == 73_250.0
    assert cap_ref.cash == 73_250.0
    assert cap_ref.account_baseline == 73_250.0

    # A subsequent .get() on the broker session must return the SAME (now
    # correctly mutated) object, not a fresh re-query masking a stale write.
    cap_again = r.broker.capital()
    assert cap_again is cap_ref
    assert cap_again.initial_capital == 73_250.0

    # STRONGER: the next equity snapshot (which reads self.capital() on the
    # broker session, see broker.py:435) must reflect the real base, not 50000.
    snap = r.broker.snapshot(dt.datetime(2026, 1, 2, 10, 0))
    assert snap.equity == 73_250.0
    assert snap.equity != 50_000.0


def test_does_not_reanchor_when_trade_history_exists():
    import datetime as dt
    r = _runner()
    with SessionLocal() as s:
        s.add(Trade(
            instrument_key="NIFTY", direction="LONG", option_type="CE",
            tradingsymbol="NIFTY26JAN20000CE", exchange="NFO", segment="options",
            strike=20000.0, expiry=dt.date(2026, 1, 29), qty=50,
            entry_premium=100.0, entry_cost=5000.0, entry_spot=20000.0,
            entry_time=dt.datetime(2026, 1, 1),
            exit_premium=110.0, exit_charges=5.0, exit_spot=20050.0,
            exit_time=dt.datetime(2026, 1, 1, 1),
            exit_reason="TARGET",
            gross_pnl=500.0, charges_total=10.0, net_pnl=490.0,
            return_pct=9.8, holding_minutes=60.0, win=True,
        ))
        s.commit()

    r.provider = _KiteFunds(net=73_250.0)
    r._next_funds_epoch = 0.0
    r._maybe_refresh_funds()

    with SessionLocal() as s:
        cap = s.get(CapitalState, 1)
        assert cap.initial_capital == 50_000.0
    assert r._reanchored is False


def test_does_not_reanchor_when_realized_pnl_nonzero():
    r = _runner()
    with SessionLocal() as s:
        cap = s.get(CapitalState, 1)
        cap.realized_pnl = 250.0
        s.commit()

    r.provider = _KiteFunds(net=73_250.0)
    r._next_funds_epoch = 0.0
    r._maybe_refresh_funds()

    with SessionLocal() as s:
        cap = s.get(CapitalState, 1)
        assert cap.initial_capital == 50_000.0
    assert r._reanchored is False


def test_does_not_reanchor_when_position_open():
    import datetime as dt
    r = _runner()
    from app.db.models import Position
    with SessionLocal() as s:
        s.add(Position(
            instrument_key="NIFTY", direction="LONG", option_type="CE",
            tradingsymbol="NIFTY26JAN20000CE", exchange="NFO", segment="options",
            strike=20000.0, expiry=dt.date(2026, 1, 29), lot_size=50, qty=50,
            entry_premium=100.0, entry_charges=5.0, entry_cost=5005.0,
            entry_spot=20000.0, entry_time=dt.datetime(2026, 1, 1),
            stop_price=65.0, target_price=160.0,
        ))
        s.commit()

    r.provider = _KiteFunds(net=73_250.0)
    r._next_funds_epoch = 0.0
    r._maybe_refresh_funds()

    with SessionLocal() as s:
        cap = s.get(CapitalState, 1)
        assert cap.initial_capital == 50_000.0
    assert r._reanchored is False


def test_mock_provider_never_reanchors():
    r = _runner()
    r._next_funds_epoch = 0.0
    r._maybe_refresh_funds()   # provider.name != "kite" -> early return, no-op

    with SessionLocal() as s:
        cap = s.get(CapitalState, 1)
        assert cap.initial_capital == 50_000.0
    assert r._reanchored is False


def test_idempotent_second_refresh_is_a_noop():
    r = _runner()
    r.provider = _KiteFunds(net=73_250.0)
    r._next_funds_epoch = 0.0
    r._maybe_refresh_funds()
    assert r._reanchored is True

    r._next_funds_epoch = 0.0   # bypass the throttle to force a second poll
    r._maybe_refresh_funds()    # must be a no-op — no exception, values unchanged

    with SessionLocal() as s:
        cap = s.get(CapitalState, 1)
        assert cap.initial_capital == 73_250.0
        assert cap.cash == 73_250.0
