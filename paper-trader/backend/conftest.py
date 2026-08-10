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

The variables below are a DENYLIST and are kept only as backup. The primary control
is in `app/core/config.py`: `Settings.model_config` sets `env_file=None` whenever
pytest is in `sys.modules`, so `.env` is not read at all during a test run. That
matters because forcing four variables left `KITE_API_KEY`/`KITE_API_SECRET`
resolving from `.env` — real credentials for the owner's real account — and would
have left every setting added later exposed by default, silently.

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
#
# ALL THREE databases are redirected, not just the execution one. `PT_DB_PATH` was
# isolated per-run (the fix for the phantom 27-test failure); `ledger.db` and
# `research.db` were not, and their defaults are FIXED paths — an absolute one under
# backend/ for the ledger, a cwd-relative one for research. So two concurrent pytest
# runs shared them, which is the same clobbering bug in two tables nobody had looked
# at yet, and it fails in the worst possible way: as unrelated test failures in
# whichever run happened to lose the race.
#
# It also means a bare `pytest` was reading and writing the developer's REAL
# journal (ledger.db is the live money record on the VPS — see the memory note that
# ledger.db, not journal.db, is THE ledger). Tests must not be able to touch it.
SAFE_TEST_ENV = {
    "PT_PROVIDER": "mock",     # never the live Kite data client
    "PT_EXECUTION": "paper",   # live_execution_enabled() needs exactly "live"
    "PT_LIVE_ACK": "",         # empty, NOT deleted — see the module docstring
    "PT_DB_PATH": os.path.join(_TMP_DIR, "paper_trader.db"),
    "PT_LEDGER_DB_PATH": os.path.join(_TMP_DIR, "ledger.db"),
    "PT_RESEARCH_DB_PATH": os.path.join(_TMP_DIR, "research.db"),
    # The backtest dataset store is a DIRECTORY of candle blobs, and its default
    # is cwd-relative — a bare `pytest` would otherwise grow gigabytes of them
    # inside backend/. Same reasoning as the three databases above.
    "PT_BACKTEST_DATASET_DIR": os.path.join(_TMP_DIR, "backtest_datasets"),
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

    from app.core.config import Settings, get_settings
    from app.engine.broker_factory import live_execution_enabled

    # PRIMARY control: .env must not be in the resolution chain at all. Checked
    # first because everything below is only a backstop for this.
    assert Settings.model_config.get("env_file") is None, (
        "Settings is still reading .env during a test run — production "
        "credentials are resolvable. See _env_file_for_this_process()."
    )
    s = get_settings()
    assert not s.kite_api_key, "KITE_API_KEY leaked from .env into the test run"
    assert not s.kite_api_secret, "KITE_API_SECRET leaked from .env into the test run"

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


@pytest.fixture(autouse=True)
def restore_the_shared_provider_clock():
    """Undo any per-test override of the market clock on the shared provider.

    `get_provider()` returns a **process-wide singleton**, so `r.provider.now = lambda:
    <fixed datetime>` — the idiom sixteen call sites across five wiring tests use to pin a
    session time — does not end with the test that wrote it. It stays for the rest of the
    run, and the last writer wins.

    Nothing depended on that until an entry test needed the clock to be inside a trading
    session: with `now` frozen at 09:20 by an unrelated file, every subsequent entry is
    refused by the 09:30 entry-window gate and the failure reads as "no position opened",
    pointing at the innocent test rather than the leak. Ten tests failed in the suite and
    passed in isolation.

    Restoring here rather than at the sixteen sites: the leak is the shape, not the site,
    and a fixture makes the next one harmless too. Deletes the instance attribute when the
    test added one, so the class's real `now` is what remains.

    **The cursor is the same leak by a second mechanism, and it is not optional.**
    `MockProvider.now()` is `self._times[self._cursor]` and `advance()` mutates that cursor
    on the same singleton, so every test that steps the synthetic market moves the clock
    for every test after it — permanently, and without ever touching the `now` attribute
    this fixture originally guarded.

    That is not theoretical. Measured on 2026-08-08, `test_notifies_on_auto_open` passed
    under `pytest tests` and failed under `pytest tests research_tests` on a **one-position**
    difference in the shared cursor:

        cursor=1149 -> now = 2025-03-05 15:15   (after the 09:30 gate — entry taken)
        cursor=1150 -> now = 2025-03-06 09:15   (before it — "ENTRY WINDOW closed")

    The cursor sat exactly on a session boundary, so a single extra `advance()` anywhere
    earlier in the run rolled the clock to the next morning and refused the entry. The
    failure named the innocent test, and suite greenness became a function of which tests
    ran before it — which is precisely what an exact-head CI contract cannot tolerate.

    Restoring the cursor keeps `advance()` observable *within* a test (nothing here stops a
    test stepping the market and asserting on it) while making it invisible *between* them.
    """
    from app.providers.factory import get_provider

    provider = get_provider()
    had = "now" in provider.__dict__
    was = provider.__dict__.get("now")
    cursor = getattr(provider, "_cursor", None)
    yield
    if had:
        provider.__dict__["now"] = was
    else:
        provider.__dict__.pop("now", None)
    if cursor is not None and getattr(provider, "_cursor", None) != cursor:
        provider._cursor = cursor


@pytest.fixture
def give_futures_price_feed(monkeypatch):
    """Give a provider a futures price feed the way a real adapter would: the method AND the
    capability declaration.

    `runner._process_futures_entries` refuses to open when the connection does not declare
    `FUTURES_QUOTES`, because no shipped provider implements `get_futures_ltp` and a position
    that cannot be marked is worse than no position. Tests that inject the method are
    simulating a connection that CAN price futures, so they must say so — otherwise the
    declaration stops being the contract and the guard grows a second source of truth.
    """
    from app.providers import capabilities as caps

    def _give(provider, fn):
        monkeypatch.setattr(provider, "get_futures_ltp", fn, raising=False)
        monkeypatch.setattr(provider, "CAPABILITIES",
                            frozenset(provider.CAPABILITIES) | {caps.FUTURES_QUOTES},
                            raising=False)

    return _give


@pytest.fixture(autouse=True)
def close_broker_sessions_opened_by_this_test():
    """Close every `EngineRunner`'s broker session at the end of the test that built it.

    `PaperBroker` holds a SQLAlchemy session for its lifetime, and `EngineRunner.__init__`
    builds one. A test that constructs a runner and walks away therefore leaks a pooled
    connection, and the pool is `pool_size=5 + max_overflow=10` = **fifteen**. Nothing bounds
    how many runners a file builds: `tests/test_shadow_deployment_engine.py` builds one per
    test and four inside a single dict comprehension, so it crosses fifteen partway through
    and the *next* checkout blocks for the pool timeout.

    The failure that produces is the worst shape this suite has:

        sqlalchemy/pool/impl.py:167: TimeoutError

    — raised by whichever test happens to ask for connection sixteen. It is not that test's
    defect, it passes in isolation, and it moves as the file grows. Measured 2026-08-11:
    `test_the_managed_binding_does_not_change_authoritative_selection` failed inside the full
    run and inside its own file, passed alone, and reproduced identically in a clean worktree
    at `efc0b1f` — i.e. it had nothing to do with the slice that surfaced it, and it is
    intermittent, so a single green run does not clear it.

    Fixed here rather than at the call sites for the same reason the clock fixture above is:
    the leak is the shape, not the site. Closing at the sites means every future test that
    builds a runner has to remember, and this repo has now paid for that lesson three times
    (`PaperBroker.close()` in fixtures, the shared provider clock, the cursor).

    Tracks instances by wrapping construction rather than scanning `gc`: a `gc.get_objects()`
    sweep would also collect runners a *previous* test deliberately kept alive, and closing
    someone else's session mid-suite is the bug this fixture exists to prevent, not a fix
    for it. Close failures are swallowed — a runner whose broker never opened a session, or
    which a test already closed, must not turn teardown into an error and mask the real
    result.
    """
    from app.engine.runner import EngineRunner

    built: list = []
    original = EngineRunner.__init__

    def tracking_init(self, *args, **kwargs):
        original(self, *args, **kwargs)
        built.append(self)

    EngineRunner.__init__ = tracking_init
    try:
        yield
    finally:
        EngineRunner.__init__ = original
        for runner in built:
            broker = getattr(runner, "broker", None)
            close = getattr(broker, "close", None)
            if close is None:
                continue
            try:
                close()
            except Exception:                       # noqa: BLE001 — see the docstring
                pass
