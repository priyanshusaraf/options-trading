"""The research-run driver's plan must sweep BOTH 15m and 30m so each strategy is
evaluated on both of its native timeframes (the strategy is invalid on anything
slower or faster). The dev-blacklist filtering must still apply on every interval."""
import importlib


def _load():
    import scripts.research_run as rr
    return importlib.reload(rr)


def test_plan_sweeps_both_15m_and_30m(monkeypatch):
    monkeypatch.delenv("PT_WATCHLIST_SNAPSHOT", raising=False)
    rr = _load()
    plan = rr._plan(lambda k: k)          # identity instrument factory
    assert {item["interval"] for item in plan} == {"15minute", "30minute"}


def test_plan_runs_every_strategy_on_every_interval(monkeypatch):
    monkeypatch.delenv("PT_WATCHLIST_SNAPSHOT", raising=False)
    rr = _load()
    plan = rr._plan(lambda k: k)
    pairs = {(item["strategy_key"], item["interval"]) for item in plan}
    assert len(pairs) == len(plan)        # no duplicate (strategy, interval) cell
    for sk in ("trend_impulse_v3", "expanding_z_v4"):
        for iv in ("15minute", "30minute"):
            assert (sk, iv) in pairs


def test_plan_respects_dev_blacklist_on_every_interval(monkeypatch, tmp_path):
    import json
    snap = tmp_path / "wl.json"
    snap.write_text(json.dumps({"in_watchlists": ["NIFTY", "BANKNIFTY"]}))
    monkeypatch.setenv("PT_WATCHLIST_SNAPSHOT", str(snap))
    rr = _load()
    plan = rr._plan(lambda k: k)
    # NIFTY/BANKNIFTY are committed (and not in the always-allowed sandbox) -> excluded
    for item in plan:
        assert "NIFTY" not in item["instruments"]
        assert "BANKNIFTY" not in item["instruments"]
    # every interval is still represented after filtering
    assert {item["interval"] for item in plan} == {"15minute", "30minute"}
