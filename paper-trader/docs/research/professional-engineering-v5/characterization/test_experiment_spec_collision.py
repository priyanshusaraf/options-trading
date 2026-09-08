"""Chat 1 characterization only; production code remains read-only.

This test forces the collision branch that an actual 128-bit digest collision would
reach. A safe implementation must either create a distinct full identity or refuse
after comparing the stored canonical recipe. The current path silently reuses the
first recipe.
"""

import json

from research.domain.models import ExperimentSpec
from research.orchestrator import run as run_module
from research_tests.test_orchestrator import _run


def test_truncated_spec_collision_never_reuses_a_different_recipe(
        research_session, inst_factory, candles_factory, monkeypatch):
    monkeypatch.setattr(run_module, "spec_hash", lambda _recipe: "0" * 32)

    first = _run(
        research_session, inst_factory, candles_factory, slippage_bps=5.0)
    second = _run(
        research_session, inst_factory, candles_factory, slippage_bps=6.0)

    specs = research_session.query(ExperimentSpec).all()
    assert first["spec_id"] != second["spec_id"] or len(specs) == 2, (
        "different canonical recipes collided and silently reused one immutable spec"
    )
    assert {json.loads(spec.recipe_json)["cost_assumptions"]["slippage_bps"]
            for spec in specs} == {5.0, 6.0}
