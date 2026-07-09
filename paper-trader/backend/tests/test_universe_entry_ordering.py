"""audit H11: config-mutating routes ran on a threadpool thread and mutated the
engine's shared in-memory collections while the loops read them. Individual
set/dict writes are GIL-atomic and the loops snapshot with list(), so the only
non-benign window was a multi-field add applied out of order — the loop could see
an enabled key before its interval/product/strategy were set. Fix: enable LAST on
add, disable FIRST on remove, so the engine always sees a consistent view."""
from app.db.session import init_db
from app.engine.runner import EngineRunner


def _runner():
    init_db(reset=True)
    return EngineRunner()


def test_entry_is_enabled_only_after_its_config_is_set():
    r = _runner()
    captured = {}

    class TrackingSet(set):
        def add(self, k):
            captured["intervals"] = dict(r.intervals)
            captured["products"] = dict(r.products)
            captured["strategies"] = dict(r.strategy_keys)
            super().add(k)

    r.enabled = TrackingSet(r.enabled)
    r.apply_universe_entry("NIFTY", {"interval": "30minute", "product": "options",
                                     "strategy_key": "trend_impulse_v3"})
    assert "NIFTY" in r.enabled
    # every config field was already in place at the moment the key was enabled
    assert captured["intervals"].get("NIFTY") == "30minute"
    assert captured["products"].get("NIFTY") == "options"
    assert captured["strategies"].get("NIFTY") == "trend_impulse_v3"


def test_remove_disables_and_clears_config():
    r = _runner()
    r.apply_universe_entry("NIFTY", {"interval": "30minute", "product": "options",
                                     "strategy_key": "k"})
    r.remove_universe_entry("NIFTY")
    assert "NIFTY" not in r.enabled
    assert "NIFTY" not in r.intervals and "NIFTY" not in r.products
