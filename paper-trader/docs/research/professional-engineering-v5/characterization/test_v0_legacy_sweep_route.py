"""Chat 1 characterization of the pure V0 route policy."""

from app.core.release_profile import denied_route, manifest


def test_v0_refuses_legacy_current_universe_sweep_before_dispatch():
    assert manifest(
        "v0_research_signal", research_enabled=True,
    )["capabilities"]["backtesting"]["state"] == "ENABLED_WITH_LIMIT"
    assert denied_route(
        "v0_research_signal", "POST", "/api/backtest/sweep"
    ) is not None, (
        "V0 route policy permits the legacy sweep that resolves today's universe/provider path"
    )
