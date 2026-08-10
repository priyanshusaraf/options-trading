"""A test that builds engine runners must not leave the connection pool poorer.

`PaperBroker` holds a SQLAlchemy session for its lifetime and `EngineRunner.__init__` builds
one, so a test that constructs runners and walks away leaves connections checked out of a
15-slot pool (`pool_size=5 + max_overflow=10`). The conftest fixture
`close_broker_sessions_opened_by_this_test` closes them at teardown.

**This exists because the leak's symptom never names the leak.** When the pool runs out, the
`TimeoutError` is raised by whichever test happens to ask for connection sixteen — a test that
passes in isolation, has no defect, and changes identity as the suite grows. Measured
2026-08-11 on `test_shadow_deployment_engine.py`, where a comprehension built one runner per
enabled instrument and exhausted the pool inside a single test; the reported failure was about
strategy bindings and the cause was arithmetic.

Garbage collection returns these connections eventually, which is why the suite mostly
survived and why this is a flake rather than a hard failure. "Eventually" is not a schedule,
and a suite whose greenness depends on GC timing is one that fails on a slower machine.

Ordering matters and is the point: test A leaks, test B observes. A single test cannot check
this, because the fixture releases at *teardown* — after the assertion would run.
"""
from __future__ import annotations

from app.db.session import engine, init_db
from app.engine.runner import EngineRunner

#: Comfortably over `pool_size` (5) and under the 15 the pool can serve at once, so this file
#: demonstrates the leak without ever tripping the timeout it exists to prevent.
RUNNERS = 8


def test_a_leaves_eight_runners_behind():
    init_db(reset=True)
    for _ in range(RUNNERS):
        EngineRunner()
    assert engine.pool.checkedout() > 0, (
        "no connections were checked out at all — if EngineRunner stopped holding a broker "
        "session, this guard is measuring nothing and should be re-derived, not deleted")


def test_b_finds_the_pool_returned_to_baseline():
    assert engine.pool.checkedout() == 0, (
        f"{engine.pool.checkedout()} connections are still checked out from the previous "
        f"test. The autouse fixture in conftest.py is not releasing broker sessions, and the "
        f"next suite failure will be a pool TimeoutError naming an innocent test.")
