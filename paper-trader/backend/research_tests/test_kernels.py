"""The reuse boundary: research imports the pure simulation kernels from the
execution codebase, and doing so must never cross the capital boundary.

`test_importing_kernels_does_not_cross_capital_boundary` is the load-bearing one:
in a fresh interpreter, importing the kernels must not import any capital-moving
module nor bind the execution DB engine. That is what makes "reuse the simulation
math, never touch capital" a checkable property rather than a hope.
"""
import dataclasses
import datetime as dt
import os
import subprocess
import sys

from research.evaluation import kernels


@dataclasses.dataclass
class _Candle:
    ts: dt.datetime
    open: float
    high: float
    low: float
    close: float


class _Inst:
    segment = "NSE"
    lot_size = 1
    strike_step = 1.0
    has_options = False
    key = "TEST"
    name = "TEST"


def _series(n=160):
    base = dt.datetime(2024, 1, 1, 9, 15)
    out = []
    px = 100.0
    for i in range(n):
        px += 1.0 if (i // 12) % 2 == 0 else -0.8  # deterministic trend/chop alternation
        out.append(_Candle(base + dt.timedelta(days=i), px, px + 1.0, px - 1.0, px + 0.5))
    return out


def test_kernels_run_offline_and_return_metrics():
    trades, m = kernels.simulate(_series(), _Inst(), "day", capital=50_000)
    assert isinstance(m, kernels.BTMetrics)
    assert m.trades >= 0


def test_importing_kernels_does_not_cross_capital_boundary():
    code = (
        "import research.evaluation.kernels, sys;"
        "from research.guards import FORBIDDEN_MODULES;"
        "bad=[m for m in FORBIDDEN_MODULES if m in sys.modules];"
        "assert not bad, ('forbidden imported: %s' % bad);"
        "assert 'app.db.session' not in sys.modules, 'execution DB engine bound';"
        "print('ok')"
    )
    env = {**os.environ, "PYTHONPATH": "."}
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    assert "ok" in r.stdout
