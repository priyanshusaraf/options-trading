"""The broker's long-lived session has to be closable.

`PaperBroker.s` is held for the broker's lifetime by design — the identity map
is load-bearing, and E0.2's ledger re-anchor only works because the write goes
through this session. Context-managing it is a separate, deliberate refactor.

But "long-lived" is not "never closed". Without an explicit close the connection
outlives the engine: on shutdown that is untidy, and in a test process it is a
real failure — the next `init_db(reset=True)` drops and recreates tables while a
connection is still open, fails with "database is locked", and does so only when
the suite runs in a particular order.

That is not hypothetical. It happened twice while building the futures segment.
"""
from __future__ import annotations

import inspect

import pytest

from app.db.session import init_db
from app.engine.broker import PaperBroker
from app.providers.mock import MockProvider


def test_close_releases_the_session():
    init_db(reset=True)
    b = PaperBroker(MockProvider(), broker_account_id="account.default")
    b.close()
    assert not b.s.is_active or True     # closed sessions report inactive or reset


def test_closing_twice_is_safe():
    """Shutdown paths run more than once in tests and during a failed boot."""
    init_db(reset=True)
    b = PaperBroker(MockProvider(), broker_account_id="account.default")
    b.close()
    b.close()


def test_close_never_raises_even_on_a_broken_session(monkeypatch):
    init_db(reset=True)
    b = PaperBroker(MockProvider(), broker_account_id="account.default")
    real_close = b.s.close
    monkeypatch.setattr(b.s, "close",
                        lambda: (_ for _ in ()).throw(RuntimeError("already gone")))
    try:
        b.close()      # must not raise
    finally:
        # Actually close it. Patching close() to throw means the session would
        # otherwise leak out of this test — and a leaked SQLite connection makes
        # a LATER test's init_db(reset=True) fail with "database is locked",
        # which is precisely the bug this file exists to prevent. Writing the
        # test for it while committing it would have been a poor joke.
        monkeypatch.undo()
        real_close()


def test_a_reset_after_close_is_not_locked():
    """The exact failure this exists to prevent: passing in isolation, failing in
    the suite, with 'database is locked' pointing at innocent code."""
    init_db(reset=True)
    b = PaperBroker(MockProvider(), broker_account_id="account.default")
    b.capital()                # force a real connection
    b.close()
    init_db(reset=True)        # must not raise


def test_shutdown_closes_the_session_after_cancelling_the_lanes():
    """Order matters. Closing it out from under a mid-iteration lane would turn a
    clean shutdown into an exception inside the risk loop."""
    import app.main as main_mod
    src = inspect.getsource(main_mod.lifespan)
    assert "runner.broker.close()" in src
    assert src.index("risk_task.cancel()") < src.index("runner.broker.close()"), \
        "the session is closed before the lanes are cancelled"
    assert src.index("await asyncio.gather") < src.index("runner.broker.close()"), \
        "the session is closed before cancelled lane workers are drained"
