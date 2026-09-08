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
import secrets
import shutil
import sys
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
    # A developer shell can carry the future production authority even though
    # pytest detaches .env. Tests must still bind only to their throwaway SQLite
    # file unless a specific opt-in integration test builds its own engine.
    "PT_DATABASE_URL": "",
    "PT_PRODUCTION": "0",
    "PT_DB_PATH": os.path.join(_TMP_DIR, "paper_trader.db"),
    "PT_LEDGER_DB_PATH": os.path.join(_TMP_DIR, "ledger.db"),
    "PT_RESEARCH_DB_PATH": os.path.join(_TMP_DIR, "research.db"),
    # Semantic editor receipts use the deployment-stable event secret. Tests
    # receive one process-local random value before any app import; child
    # processes inherit it without the value entering logs or fixtures.
    "PT_EVENT_CURSOR_SECRET": secrets.token_urlsafe(32),
    # The backtest dataset store is a DIRECTORY of candle blobs, and its default
    # is cwd-relative — a bare `pytest` would otherwise grow gigabytes of them
    # inside backend/. Same reasoning as the three databases above.
    "PT_BACKTEST_DATASET_DIR": os.path.join(_TMP_DIR, "backtest_datasets"),
}
os.environ.update(SAFE_TEST_ENV)

import pytest  # noqa: E402  — must not precede the env forcing above


def pytest_sessionstart(session):
    # Collection reads sealed vectors, so inputs must exist before importing tests.
    from pathlib import Path
    from tests.indicator_assurance_fixtures import restore_assurance_inputs
    restore_assurance_inputs(Path(__file__).resolve().parents[2])


@pytest.fixture
def admitted_entry_identity():
    """Persist one real current IR receipt for tests that intentionally open exposure.

    Entry tests opt in explicitly. Refusal and legacy-recovery tests therefore keep
    exercising absent/forged receipt behavior instead of inheriting authority from an
    autouse fixture. Admission is cached as immutable Python evidence; each reset test
    persists it into its fresh database before using the returned keyword arguments.
    """
    from app.db.session import SessionLocal
    from tests.admitted_entry import persist_admitted_entry

    def persist(session=None, *, owner_id="owner"):
        owns_session = session is None
        current = session or SessionLocal()
        try:
            result = persist_admitted_entry(current, owner_id=owner_id)
            if owns_session:
                current.commit()
        finally:
            if owns_session:
                current.close()
        return result

    return persist


@pytest.fixture
def admitted_backtest_receipt(admitted_entry_identity):
    """Persist and expose only the receipt accepted by backtest boundaries.

    Backtests execute the graph bound by the receipt and must not pass a second,
    caller-selected strategy identity alongside it.  Entry/broker tests retain
    ``admitted_entry_identity`` because their intent boundary checks the complete
    graph identity triple.
    """
    def persist(session=None, *, owner_id="owner"):
        identity = admitted_entry_identity(session, owner_id=owner_id)
        return {"admission_address": identity["admission_address"]}

    return persist


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


def _mapping_snapshot(owner, attribute):
    mapping = getattr(owner, attribute, None)
    if not isinstance(mapping, dict):
        return None
    return owner, attribute, mapping, dict(mapping)


def _restore_mapping(snapshot):
    if snapshot is None:
        return
    owner, attribute, original, values = snapshot
    if getattr(owner, attribute, None) is not original:
        setattr(owner, attribute, original)
    original.clear()
    original.update(values)


def _restore_object_dict(snapshot):
    if snapshot is None:
        return
    owner, original, values = snapshot
    if owner.__dict__ is not original:
        object.__setattr__(owner, "__dict__", original)
    original.clear()
    original.update(values)


@pytest.fixture(autouse=True)
def restore_declared_process_state():
    """Restore every declared process-wide test surface after each test.

    Provider state generalizes the former clock/cursor fixture to the singleton's
    complete attribute map. Values are shallow snapshots: immutable candle payloads
    are not copied, while added methods, keys and scalar cursor changes are undone.

    FastAPI and strategy modules are observed only when normal test collection has
    already loaded them. This fixture never imports either module early. Both mapping
    contents and the original mapping objects are restored, so a test may replace a
    registry or overrides dictionary without leaking that replacement.

    The provider seam has already loaded app.core.config, so the canonical Settings
    object can be snapshotted without changing import order. Its values stay in memory
    and are never serialized. Replacing the LRU-cached object is refused: module-level
    references and the provider would otherwise keep the old instance while later
    get_settings() calls receive a different one.
    """
    from app.providers.factory import get_provider

    provider = get_provider()
    provider_snapshot = (provider, "__dict__", provider.__dict__, dict(provider.__dict__))

    config_module = sys.modules.get("app.core.config")
    get_settings = getattr(config_module, "get_settings", None)
    settings = get_settings() if callable(get_settings) else None
    settings_snapshot = (
        settings, settings.__dict__, dict(settings.__dict__)
    ) if settings is not None else None

    app_snapshots = ()
    main_module = sys.modules.get("app.main")
    loaded_app = getattr(main_module, "app", None) if main_module is not None else None
    if loaded_app is not None:
        app_snapshots = (
            _mapping_snapshot(loaded_app.state, "_state"),
            _mapping_snapshot(loaded_app, "dependency_overrides"),
        )

    registry_snapshots = ()
    registry_module = sys.modules.get("app.strategy.registry")
    if registry_module is not None:
        registry_snapshots = (
            _mapping_snapshot(registry_module, "_REGISTRY"),
            _mapping_snapshot(registry_module, "_GENERATED_REGISTRY"),
        )

    try:
        yield
    finally:
        settings_identity_replaced = (
            settings is not None and get_settings() is not settings
        )
        for snapshot in app_snapshots:
            _restore_mapping(snapshot)
        _restore_mapping(provider_snapshot)
        for snapshot in registry_snapshots:
            _restore_mapping(snapshot)
        _restore_object_dict(settings_snapshot)
        if settings_identity_replaced:
            pytest.fail(
                "SETTINGS_CACHE_IDENTITY_REPLACED: patch the cached Settings instance; "
                "do not clear the process cache"
            )


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
