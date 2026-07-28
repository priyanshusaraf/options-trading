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
import types

import pytest

import app.engine.broker_factory as bf
from app.engine.broker import PaperBroker
from app.providers.mock import MockProvider


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
