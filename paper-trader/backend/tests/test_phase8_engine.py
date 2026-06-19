"""Engine wiring for reinforcement, overnight holding, option-data cache,
and runtime-config overrides."""
from app.db.session import init_db, SessionLocal
from app.engine.runner import EngineRunner
from app.core.instruments import get_instrument
from app.core import runtime_config


def _runner_with_long():
    init_db(reset=True)
    r = EngineRunner()
    nifty = get_instrument("NIFTY")
    chain = r.provider.get_option_chain(nifty)
    # near-ATM call -> stable, modest cost regardless of the shared mock cursor
    q = min((x for x in chain.quotes if x.option_type == "CE"),
            key=lambda x: abs(x.strike - chain.spot))
    pos = r.broker.open_position(nifty, "LONG", q, "t", r.provider.now(), chain.spot)
    return r, nifty, chain, q, pos


def test_reinforcement_applied_via_engine():
    r, nifty, chain, q, pos = _runner_with_long()
    base_stop = pos.stop_price
    r.broker.mark(pos, premium=q.ltp * 1.25, spot=chain.spot, now=r.provider.now())
    r.broker.commit()
    r.state["NIFTY"] = {"signal": "LONG_ENTRY", "z": 1.5, "slope": 1.0, "close": chain.spot}
    r.process_entries()
    p = r.broker.position_for("NIFTY")
    assert p.reinforcement_count == 1
    assert p.stop_price > base_stop            # ratcheted up by the reinforcement
    assert len(r.broker.open_positions()) == 1  # no pyramiding — still one position


def test_overnight_keep_then_book_gap():
    r, nifty, chain, q, pos = _runner_with_long()
    r.params["overnight_auto_pct"] = 5.0       # force auto-hold regardless of size
    r.params["overnight_max_pct"] = 5.0
    r.params["overnight_min_days_to_expiry"] = 0   # disable the expiry gate for this test
    now = r.provider.now()
    r.square_off_for_overnight(now)
    p = r.broker.position_for("NIFTY")
    assert p.held_overnight is True and p.session_close_premium > 0
    r.broker.mark(p, premium=q.ltp * 1.3, spot=chain.spot, now=now); r.broker.commit()
    r.book_overnight_gap(now)
    assert r.broker.position_for("NIFTY").overnight_pnl > 0


def test_overnight_squareoff_closes_position():
    r, nifty, chain, q, pos = _runner_with_long()
    r.params["overnight_auto_pct"] = 0.001
    r.params["overnight_max_pct"] = 0.002      # force square-off (position too big)
    r.square_off_for_overnight(r.provider.now())
    assert r.broker.position_for("NIFTY") is None


def test_option_cache_persist_and_throttle():
    init_db(reset=True)
    r = EngineRunner()
    from app.options import cache
    cache._last_snapshot.clear()
    nifty = get_instrument("NIFTY")
    chain = r.provider.get_option_chain(nifty)
    now = r.provider.now()
    n = cache.persist_chain(chain, nifty, now, 15.0)
    assert n > 0
    assert cache.persist_chain(chain, nifty, now, 15.0) == 0   # throttled within cadence
    assert cache.stats()["rows"] == n


def test_runtime_override_roundtrip():
    init_db(reset=True)
    runtime_config.clear_override("reinforce_lock_pct")
    runtime_config.set_override("reinforce_lock_pct", 0.10)
    assert runtime_config.effective()["reinforce_lock_pct"] == 0.10
    assert any(row["key"] == "reinforce_lock_pct" for row in runtime_config.schema())
    assert "error" in runtime_config.set_override("bogus_key", 1)   # whitelist guard
