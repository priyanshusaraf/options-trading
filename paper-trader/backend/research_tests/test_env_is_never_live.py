"""Mirror of tests/test_no_live_under_pytest.py, from the OTHER suite root.

This suite is where the 2026-07-28 leak actually lived: `pytest research_tests`
loaded no safety env and resolved to the live Kite provider, real-money execution
and the production ledger (docs/incidents/2026-07-28-test-env-live-leak.md).

The assertion has to exist HERE. A copy under `tests/` proves the guard works when
`tests/` is collected — which was already true before the fix, and is exactly the
collection-order accident that hid the hole. Only a check that runs in a
`research_tests`-only invocation can fail if the rootdir conftest stops applying.
"""
from __future__ import annotations

import os
import tempfile


def test_this_suite_root_is_not_live():
    from app.core.config import get_settings
    from app.engine.broker_factory import live_execution_enabled

    s = get_settings()
    assert s.provider == "mock", f"provider is {s.provider!r} — .env is bleeding through"
    assert s.execution != "live", f"execution is {s.execution!r}"
    assert not s.live_ack, f"live_ack is {s.live_ack!r}"
    assert live_execution_enabled() is False


def test_this_suite_root_cannot_touch_the_production_ledger():
    from app.core.config import get_settings

    db = os.path.abspath(get_settings().db_path)
    repo_ledger = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "paper_trader.db"))

    assert db != repo_ledger
    assert db.startswith(os.path.abspath(tempfile.gettempdir()))
    assert "paper-trader-pytest-" in db
