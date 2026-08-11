"""
Broker selection. PaperBroker is the default everywhere. The order-placing
LiveBroker is built ONLY when BOTH live-execution flags are set AND the live Kite
data provider is active — two independent gates on top of the arm-to-trade gate.

  PT_EXECUTION=live
  PT_LIVE_ACK=I_UNDERSTAND_REAL_MONEY

These are read from .env (via Settings) so they are the single source of truth —
no shell exports needed. A real exported env var still works as a fallback.
Absent either, or on the mock provider, you get the paper broker, which can place
no real order.
"""
from __future__ import annotations

import os

from app.core.config import get_settings
from app.core.logging import log
from app.engine.broker import PaperBroker
from app.providers import capabilities as caps
from app.providers.connection import ConnectionCannotExecute, connection_for

_ACK = "I_UNDERSTAND_REAL_MONEY"

# The real order-placing class, identified by name rather than by import — see
# _refuse_live_broker_under_pytest for why. Hoisted into constants so the identity
# is assertable: tests/test_no_live_under_pytest.py pins these against the actual
# class, so moving or renaming LiveBroker fails the build instead of quietly
# turning the guard into a comparison that can never match.
_LIVE_BROKER_MODULE = "app.engine.live_broker"
_LIVE_BROKER_NAME = "LiveBroker"


def _refuse_live_broker_under_pytest(broker):
    """Last line of defence: a test run must be INCAPABLE of resolving to live.

    The env guards in backend/conftest.py are the primary mechanism, but they are a
    soft guarantee — a stray monkeypatch.setenv, a new test root without the rootdir
    conftest, or a direct make_broker() call can undo them. This one cannot be
    undone from a test, because it fires on the object that was actually built.

    Identified by module + qualname rather than isinstance: the legitimate wiring
    tests in tests/test_broker_factory.py monkeypatch
    `app.engine.live_broker.LiveBroker` to a stub, so the name bound inside
    make_broker() IS the stub and `isinstance(broker, LiveBroker)` would compare
    against it. Matching the real class by name lets those tests keep asserting the
    live wiring with a harmless fake, while a genuine LiveBroker — one holding a real
    KiteOrderClient pointed at the owner's account — always trips.
    """
    if not os.environ.get("PYTEST_CURRENT_TEST"):
        return
    t = type(broker)
    if t.__module__ == _LIVE_BROKER_MODULE and t.__name__ == _LIVE_BROKER_NAME:
        raise RuntimeError(
            "make_broker() resolved a real LiveBroker inside a pytest run "
            f"({os.environ['PYTEST_CURRENT_TEST']}). This broker places REAL orders "
            "on the owner's Zerodha account. The test environment leaked live "
            "credentials or flags — check backend/conftest.py. Refusing to return it."
        )


def live_execution_enabled() -> bool:
    """True only if execution=live AND the exact ack phrase are set. Prefers the
    .env-backed Settings (the single source of truth) and falls back to a real
    exported environment variable, so both `.env` and `export` paths work."""
    s = get_settings()
    execution = (s.execution or os.environ.get("PT_EXECUTION", "")).strip().lower()
    ack = (s.live_ack or os.environ.get("PT_LIVE_ACK", "")).strip()
    return execution == "live" and ack == _ACK


def make_broker(provider, notifier=None, deployment_id=None, execution_connection=None,
                *, broker_account_id: str, owner_id: str):
    """Build the broker for `deployment_id`'s book.

    `deployment_id=None` means "the legacy deployment" — resolved inside the broker
    rather than here, so the default lives in exactly one place (models.LEGACY_
    DEPLOYMENT_ID) and callers that predate deployments keep working unchanged.

    `execution_connection=None` means "the data provider is also the execution
    connection", which is what production runs today: one Kite login serving prices,
    account and orders. Naming a connection is how a caller trades through a broker
    other than the one it reads prices from.

    **The asymmetry between the two is deliberate.** An unnamed connection that cannot
    execute keeps the historical silent fall-back to `PaperBroker`, because mock and
    replay are not brokers and `PT_EXECUTION=live` against them has always meant paper —
    a dev configuration, not a mistake. A *named* connection that cannot execute is a
    caller asserting an intent that is wrong, and it refuses: see
    `ConnectionCannotExecute` for why silence there is the dangerous option."""
    named = execution_connection is not None
    conn = execution_connection if named else connection_for(provider)
    book = {"broker_account_id": broker_account_id, "owner_id": owner_id}
    if deployment_id is not None:
        book["deployment_id"] = deployment_id

    # PaperBroker owns the legacy deployment default. Passing ``None`` explicitly
    # suppresses that constructor default and makes position reads unscoped.
    paper_book = {"broker_account_id": broker_account_id, "owner_id": owner_id}
    if deployment_id is not None:
        paper_book["deployment_id"] = deployment_id

    if not live_execution_enabled():
        return PaperBroker(provider, **paper_book)

    if not conn.supports(caps.LIVE_EXECUTION):
        if named:
            raise ConnectionCannotExecute(
                f"connection {conn.scope!r} (broker {conn.broker!r}) was named for execution "
                f"but does not declare {caps.LIVE_EXECUTION!r}; it declares "
                f"{sorted(conn.capabilities)}. Refusing to return a PaperBroker under a live "
                f"configuration — that would look exactly like trading and place no order."
            )
        return PaperBroker(provider, **paper_book)

    # Declaring LIVE_EXECUTION says "a live order client can be built from this
    # connection". WHICH client is the registry's answer, not this function's: until
    # 2026-08-10 this read `if conn.broker != "kite": raise`, and a hardcoded broker
    # name in the one place that decides whether real orders go out is exactly what the
    # registry exists to remove. The refusal is unchanged — a connection whose broker
    # has no order client in this build is refused rather than having its credential
    # sent to another broker's endpoint — it is now a lookup rather than a comparison.
    from app.providers.brokers import BrokerNotSupported, build_live_venue
    s = get_settings()
    try:
        client, venue = build_live_venue(conn, s)
    except BrokerNotSupported as e:
        raise ConnectionCannotExecute(str(e)) from e

    from app.engine.live_broker import LiveBroker
    log.warn("🔴 LIVE EXECUTION ENABLED — the bot can place REAL orders on your "
             "account (still gated by ARM, daily-loss halt, routing, and the "
             "ownership guard).")
    # The venue is passed rather than defaulted so the composition root, not the broker,
    # decides which dialect the wire speaks.
    broker = LiveBroker(provider, client, notifier=notifier,
                        poll_seconds=s.order_poll_seconds,
                        timeout_seconds=s.order_timeout_seconds,
                        connection=conn, venue=venue, **book)
    _refuse_live_broker_under_pytest(broker)
    return broker
