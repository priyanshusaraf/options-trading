"""A test run must be INCAPABLE of resolving to live execution.

Incident, 2026-07-28: the safety env lived in `tests/conftest.py`, so it applied to
`pytest tests` and nothing else. `pytest research_tests` resolved against the owner's
real `.env` to PROVIDER='kite', EXECUTION='live', ACK set, and DB_PATH pointing at the
*production* ledger. `pytest tests research_tests` was safe only because collecting
`tests/` imported that conftest first — collection order, not a guarantee.

These tests pin both halves of the remediation: the rootdir conftest that makes the
safe env unconditional, and the factory-level raise that holds even if the env is
subverted from inside a test.
"""
from __future__ import annotations

import os
import sys
import types
from unittest import mock

import pytest

import app.engine.broker_factory as bf
from app.engine.broker import PaperBroker
from app.providers.mock import MockProvider
from app.providers.kite import KiteProvider as _KiteForCaps


# ── .env is out of the resolution chain entirely ────────────────────────────

def test_dotenv_is_not_read_at_all_during_a_test_run():
    """The primary control. Forcing four PT_* vars was a denylist: KITE_API_KEY and
    KITE_API_SECRET went on resolving from .env — real credentials for a real
    account — and every setting added later would have inherited that exposure
    silently. With env_file=None the only sources are defaults and what a test sets."""
    from app.core.config import Settings

    assert Settings.model_config.get("env_file") is None


def test_production_credentials_do_not_resolve_under_pytest():
    from app.core.config import get_settings

    s = get_settings()
    assert s.kite_api_key == ""
    assert s.kite_api_secret == ""
    assert s.telegram_bot_token == ""


def test_a_real_process_still_reads_dotenv(monkeypatch):
    """The isolation must not follow the code into production, where .env is the
    entire configuration mechanism."""
    from app.core.config import _env_file_for_this_process

    monkeypatch.delenv("PT_DISABLE_DOTENV", raising=False)
    assert _env_file_for_this_process() is None          # here: pytest is imported
    with mock.patch.dict(sys.modules):
        del sys.modules["pytest"]
        assert _env_file_for_this_process() == ".env"    # a real process


def test_dotenv_can_be_disabled_outside_pytest_too(monkeypatch):
    """PT_DISABLE_DOTENV=1 gives the same isolation to anything that needs it."""
    from app.core.config import _env_file_for_this_process

    monkeypatch.setenv("PT_DISABLE_DOTENV", "1")
    with mock.patch.dict(sys.modules):
        del sys.modules["pytest"]
        assert _env_file_for_this_process() is None


# ── the environment every test runs in ──────────────────────────────────────

def test_the_resolved_settings_are_never_live():
    from app.core.config import get_settings
    s = get_settings()
    assert s.provider == "mock"
    assert s.execution != "live"
    assert not s.live_ack
    assert bf.live_execution_enabled() is False


def test_the_db_path_is_a_throwaway_never_the_production_ledger():
    """init_db(reset=True) drops and recreates every table. If PT_DB_PATH ever
    resolved to the real ledger, one such test would destroy 34 real trades.

    Asserted against the invariant rather than by importing the rootdir conftest:
    three conftest.py files are in play (rootdir, tests/, research_tests/) and a
    bare `import conftest` binds to whichever pytest registered under that name,
    which varies with the collection set.
    """
    import tempfile
    from app.core.config import get_settings

    db = os.path.abspath(get_settings().db_path)
    repo_ledger = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                               "paper_trader.db"))

    assert db != repo_ledger, "the suite is pointed at the PRODUCTION ledger"
    assert db.startswith(os.path.abspath(tempfile.gettempdir()))
    # Per-run unique dir. A fixed shared path is not merely untidy: two concurrent
    # pytest runs clobbered each other's SQLite file and produced 27 phantom
    # failures that cost a debugging session chasing a bug that did not exist.
    assert "paper-trader-pytest-" in db
    assert db == os.path.abspath(os.environ["PT_DB_PATH"])


def test_live_ack_is_empty_not_absent():
    """Regression on the subtle half of the fix: pydantic-settings falls back to
    .env when an OS var is ABSENT, so `del os.environ["PT_LIVE_ACK"]` resolves to
    the real ack phrase. Only a present-but-empty var shadows .env."""
    assert "PT_LIVE_ACK" in os.environ, \
        "PT_LIVE_ACK must be present-and-empty; deleting it re-exposes .env"
    assert os.environ["PT_LIVE_ACK"] == ""


# ── the factory-level raise ─────────────────────────────────────────────────

def _kite_looking_provider():
    p = MockProvider()
    p.name = "kite"              # satisfies the provider half of the live gate
    p.CAPABILITIES = _KiteForCaps.CAPABILITIES
    p.access_token = "tok"
    return p


def _stub_the_kite_plumbing(monkeypatch):
    """Fake everything that would touch the network, but leave LiveBroker REAL —
    the real class is precisely what the guard must catch."""
    monkeypatch.setattr(
        "app.providers.live_kite.LiveExecutionKite",
        lambda **k: types.SimpleNamespace(set_access_token=lambda t: None),
    )
    monkeypatch.setattr(
        "app.engine.kite_order_client.KiteOrderClient",
        lambda *a, **k: object(),
    )


def test_make_broker_raises_if_it_ever_resolves_a_real_live_broker(monkeypatch):
    """THE test. Subvert the env from inside a test exactly as a leak would, and
    assert make_broker refuses rather than handing back a real-money broker."""
    monkeypatch.setenv("PT_EXECUTION", "live")
    monkeypatch.setenv("PT_LIVE_ACK", "I_UNDERSTAND_REAL_MONEY")
    monkeypatch.setattr(bf, "get_settings", lambda: _live_settings())
    _stub_the_kite_plumbing(monkeypatch)

    assert bf.live_execution_enabled() is True, "precondition: the gate is open"

    with pytest.raises(RuntimeError, match="real LiveBroker inside a pytest run"):
        bf.make_broker(_kite_looking_provider())


def test_the_raise_names_the_offending_test(monkeypatch):
    """The message has to be actionable — which test leaked, not just that one did."""
    monkeypatch.setattr(bf, "get_settings", lambda: _live_settings())
    _stub_the_kite_plumbing(monkeypatch)

    with pytest.raises(RuntimeError) as e:
        bf.make_broker(_kite_looking_provider())
    assert "test_the_raise_names_the_offending_test" in str(e.value)
    assert "REAL orders" in str(e.value)


def test_the_guard_targets_the_real_class_and_a_rename_breaks_the_build():
    """A string-matching guard can look correct while matching nothing.

    `_refuse_live_broker_under_pytest` identifies LiveBroker by module + qualname,
    so moving or renaming the class silently turns it into a comparison that can
    never be true — the guard would still be there, still read fine, and never
    fire again. This pins the constants to the class's actual identity so that
    change fails here instead.

    (Two other guards this week had the same shape: deploy.sh Guard 0, and the
    `*.db-*` exclude that matched none of the files its comment claimed.)
    """
    from app.engine.live_broker import LiveBroker

    assert LiveBroker.__module__ == bf._LIVE_BROKER_MODULE, \
        "LiveBroker moved — update _LIVE_BROKER_MODULE or the pytest guard is dead"
    assert LiveBroker.__name__ == bf._LIVE_BROKER_NAME, \
        "LiveBroker was renamed — update _LIVE_BROKER_NAME or the pytest guard is dead"

    # And the constants actually make the guard fire on a genuine instance.
    with pytest.raises(RuntimeError):
        bf._refuse_live_broker_under_pytest(LiveBroker.__new__(LiveBroker))


def test_make_broker_really_does_construct_a_genuine_live_broker(monkeypatch):
    """Proves the raise-test above is not passing vacuously.

    With the guard neutralised, this exact wiring returns a REAL LiveBroker — the
    object that holds a real KiteOrderClient against the owner's account. So when
    the guard is active and that call raises, it is raising on the genuine class,
    not on a stub or a near-miss."""
    from app.engine.live_broker import LiveBroker

    monkeypatch.setattr(bf, "get_settings", lambda: _live_settings())
    _stub_the_kite_plumbing(monkeypatch)
    monkeypatch.setattr(bf, "_refuse_live_broker_under_pytest", lambda b: None)

    broker = bf.make_broker(_kite_looking_provider())
    assert type(broker) is LiveBroker
    assert type(broker).__module__ == bf._LIVE_BROKER_MODULE


def test_the_guard_is_keyed_on_pytest_current_test(monkeypatch):
    """Outside a test run the guard is inert — production must still get its
    LiveBroker. Proven directly on the guard, since make_broker() cannot be called
    without PYTEST_CURRENT_TEST from in here."""
    from app.engine.live_broker import LiveBroker

    real = LiveBroker.__new__(LiveBroker)          # a real instance, no __init__
    with pytest.raises(RuntimeError):
        bf._refuse_live_broker_under_pytest(real)   # PYTEST_CURRENT_TEST is set

    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    bf._refuse_live_broker_under_pytest(real)       # inert — must not raise


def test_the_guard_does_not_fire_on_the_paper_broker():
    bf._refuse_live_broker_under_pytest(PaperBroker(MockProvider()))


def test_the_guard_tolerates_the_stubbed_live_broker_used_by_wiring_tests():
    """tests/test_broker_factory.py monkeypatches LiveBroker to a stub returning a
    string. Those tests assert real wiring with a harmless object and must keep
    passing — the guard identifies the real class, not the patched name."""
    bf._refuse_live_broker_under_pytest("LB")
    bf._refuse_live_broker_under_pytest(object())


def _live_settings():
    """Settings with both live flags set, everything else from the real defaults."""
    from app.core.config import Settings
    s = Settings()
    object.__setattr__(s, "execution", "live")
    object.__setattr__(s, "live_ack", "I_UNDERSTAND_REAL_MONEY")
    return s
