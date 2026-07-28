"""Rootdir conftest — a test run must be STRUCTURALLY incapable of going live.

Why this file exists (incident, 2026-07-28)
-------------------------------------------
The safety env was set in `tests/conftest.py`. A conftest only applies to its own
directory, so it protected `pytest tests` and nothing else. `pytest research_tests`
loaded no such guard and resolved, against the owner's real `.env`, to:

    PROVIDER='kite'  EXECUTION='live'  ACK='I_UNDERSTAND_REAL_MONEY'
    DB_PATH='paper_trader.db'  LIVE_EXECUTION_ENABLED=True

— the live Kite provider, real-money execution armed at the factory, and the
*production* ledger as the target of `init_db(reset=True)`. `pytest tests
research_tests` happened to be safe only because collecting `tests/` imported its
conftest first and `os.environ` is process-global: a collection-order accident, not
a guarantee. `deploy.sh` relied on that accident on every deploy.

The fix is placement, not vigilance. As the rootdir conftest this module is imported
by pytest before ANY test module, and therefore before any `app.*` import — which
matters because `app.db.session` builds its SQLAlchemy engine from `PT_DB_PATH` at
import time, so a later fixture would be far too late to redirect it.

On PT_LIVE_ACK: it is forced to the empty string rather than deleted. Deleting it is
what the instinct says "unset" means, and it is actively wrong here — pydantic-settings
falls back to `.env` when the OS var is absent, so `os.environ.pop("PT_LIVE_ACK")`
resolves to `'I_UNDERSTAND_REAL_MONEY'` (verified). Only a present-but-empty OS var
shadows `.env`. Empty is how the app spells "unset"; `live_execution_enabled()` reads
it as falsy.

Defence in depth, since env alone is a soft guarantee:
  - `_forbid_live_execution` re-asserts and *verifies* the resolved Settings each
    session, failing the run rather than proceeding on a bad config
  - `app/engine/broker_factory.py` raises outright if it ever resolves a real
    LiveBroker while PYTEST_CURRENT_TEST is set — see tests/test_no_live_under_pytest.py
"""
import atexit
import os
import shutil
import tempfile

# Unique per run. It used to be a fixed path in $TMPDIR, which two concurrent pytest
# runs would clobber — that produced a phantom 27-test failure that cost a debugging
# session chasing a bug that did not exist. A private dir cannot be shared by accident.
_TMP_DIR = tempfile.mkdtemp(prefix="paper-trader-pytest-")
atexit.register(shutil.rmtree, _TMP_DIR, True)

# A real OS env var takes precedence over .env in pydantic-settings, so these win.
SAFE_TEST_ENV = {
    "PT_PROVIDER": "mock",     # never the live Kite data client
    "PT_EXECUTION": "paper",   # live_execution_enabled() needs exactly "live"
    "PT_LIVE_ACK": "",         # empty, NOT deleted — see the module docstring
    "PT_DB_PATH": os.path.join(_TMP_DIR, "paper_trader.db"),
}
os.environ.update(SAFE_TEST_ENV)

import pytest  # noqa: E402  — must not precede the env forcing above


@pytest.fixture(scope="session", autouse=True)
def _forbid_live_execution():
    """Assert the safety env actually took, against the *resolved* Settings.

    The env is set at import time above; this proves it survived — that nothing
    imported earlier cached a live Settings, and that PT_DB_PATH really points at
    the throwaway file rather than the production ledger. It runs before the first
    test and fails the session outright if any of it is untrue: a misconfigured run
    must not start, rather than start and be trusted.
    """
    for key, expected in SAFE_TEST_ENV.items():
        assert os.environ.get(key) == expected, (
            f"{key} is {os.environ.get(key)!r}, expected {expected!r} — the test "
            f"safety env was overwritten after conftest import"
        )

    from app.core.config import get_settings
    from app.engine.broker_factory import live_execution_enabled

    s = get_settings()
    assert s.provider == "mock", f"resolved provider is {s.provider!r}, not mock"
    assert s.execution != "live", f"resolved execution is {s.execution!r}"
    assert not s.live_ack, f"resolved live_ack is {s.live_ack!r} — .env is bleeding through"
    assert not live_execution_enabled(), \
        "live execution resolved TRUE inside a test run — refusing to run the suite"

    # The engine is built from this path at import time; if it is the real ledger,
    # any test calling init_db(reset=True) drops the production trades table.
    db = os.path.abspath(s.db_path)
    assert db.startswith(os.path.abspath(_TMP_DIR)), \
        f"PT_DB_PATH resolved to {db!r}, outside the throwaway dir {_TMP_DIR!r}"

    yield


# Skip macOS/iCloud "… 2.py" Desktop-sync duplicate files (a space + digit before
# .py) — they otherwise break collection with import-file-mismatch.
collect_ignore_glob = ["* [0-9].py", "* [0-9][0-9].py"]
