"""Per-strategy option tenor: expiry selection, the live entry wiring, and the
premium-backtest default. Strategies without `option_tenor_days` keep the nearest
expiry exactly as before."""
import datetime as dt

from app.backtest.premium import DEFAULT_PREMIUM_PARAMS
from app.core.instruments import get_instrument
from app.providers.base import pick_expiry
from app.strategy.registry import get_strategy

D = dt.date


def test_pick_expiry_rules():
    ex = [D(2026, 10, 1), D(2026, 10, 27), D(2026, 11, 24), D(2026, 12, 22)]
    today = D(2026, 10, 8)
    assert pick_expiry(ex, today) == D(2026, 10, 27)                 # nearest future
    assert pick_expiry(ex, today, 30) == D(2026, 11, 24)             # first >= 30 days
    assert pick_expiry(ex, today, 400) == D(2026, 12, 22)            # none that far -> farthest
    assert pick_expiry(ex, D(2027, 1, 1)) == D(2026, 12, 22)         # all past -> last listed


def test_mock_chain_honours_min_dte():
    from app.providers.factory import get_provider
    prov = get_provider()
    inst = get_instrument("NIFTY")
    near = prov.get_option_chain(inst)
    far = prov.get_option_chain(inst, min_dte=30)
    assert near is not None and far is not None
    assert far.expiry >= near.expiry
    assert far.expiry == pick_expiry(prov._expiries, prov.now().date(), 30)


def test_only_band_reversion_declares_a_tenor():
    assert get_strategy("vwap_band_reversion").option_tenor_days == 30
    for k in ("spike_fade", "shock_reversal", "trend_impulse_v3", "gold_month_turn"):
        assert getattr(get_strategy(k), "option_tenor_days", None) is None


def test_live_entry_requests_the_tenor(monkeypatch):
    from app.db.session import init_db
    from app.engine.runner import EngineRunner
    init_db(reset=True)
    r = EngineRunner()
    r.params["entry_min_days_to_expiry"] = 0
    calls = []
    orig = r.provider.get_option_chain

    def spy(inst, *a, **k):
        calls.append(k.get("min_dte"))
        return orig(inst, *a, **k)

    monkeypatch.setattr(r.provider, "get_option_chain", spy)
    r.strategy_keys["NIFTY"] = "vwap_band_reversion"
    r.arm(True)
    r.state["NIFTY"] = {"signal": "LONG_ENTRY", "z": 1.5, "slope": 1.0, "close": 100.0,
                        "long_exit": False, "short_exit": False}
    r.process_entries()
    assert 30 in calls
    pos = r.broker.position_for("NIFTY")
    assert pos is not None
    assert pos.expiry == pick_expiry(r.provider._expiries, r.provider.now().date(), 30)


def test_default_strategy_calls_chain_unchanged(monkeypatch):
    from app.db.session import init_db
    from app.engine.runner import EngineRunner
    init_db(reset=True)
    r = EngineRunner()
    r.params["entry_min_days_to_expiry"] = 0
    seen = []
    orig = r.provider.get_option_chain

    def spy(inst, *a, **k):
        seen.append((a, k))
        return orig(inst, *a, **k)

    monkeypatch.setattr(r.provider, "get_option_chain", spy)
    r.arm(True)
    r.state["NIFTY"] = {"signal": "LONG_ENTRY", "z": 1.5, "slope": 1.0, "close": 100.0,
                        "long_exit": False, "short_exit": False}
    r.process_entries()
    assert seen and seen[0] == ((), {})            # the legacy one-argument call


def test_premium_default_tenor():
    """A 30-day tenor prices the same entry as a dearer (longer-dated) option."""
    from app.backtest.premium import simulate_premium
    from tests.test_option_exits import EnterOnce, Inst, _tape
    short, long_ = EnterOnce(), EnterOnce()
    long_.option_tenor_days = 30
    assert DEFAULT_PREMIUM_PARAMS["entry_dte_days"] == 14
    a, _ = simulate_premium(_tape(), Inst(), "60minute", strategy=short)
    b, _ = simulate_premium(_tape(), Inst(), "60minute", strategy=long_)
    assert a and b and b[0].entry_price > a[0].entry_price * 1.2   # ~sqrt(30/14) dearer
    c, _ = simulate_premium(_tape(), Inst(), "60minute", strategy=long_,
                            params={"entry_dte_days": 14})          # explicit param wins
    assert c[0].entry_price == a[0].entry_price
