"""RED characterization for KPV5-B-001.

The canonical published-graph research entry point must retain and verify the
ResourcePlan that bounds the accepted work.  This is intentionally outside the
production suite until the separately owned F03 repair is implemented.
"""

import inspect

from research.orchestrator.graph_experiment import run_published_graph_experiment


def test_published_graph_experiment_requires_a_resource_plan_boundary():
    source = inspect.getsource(run_published_graph_experiment)

    assert "resource_plan" in source.lower(), (
        "published graph execution reaches run_experiment without accepting, "
        "reconstructing, or recording a ResourcePlan"
    )
