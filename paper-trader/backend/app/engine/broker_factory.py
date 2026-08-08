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


def make_broker(provider, notifier=None, deployment_id=None):
    """Build the broker for `deployment_id`'s book.

    `deployment_id=None` means "the legacy deployment" — resolved inside the broker
    rather than here, so the default lives in exactly one place (models.LEGACY_
    DEPLOYMENT_ID) and callers that predate deployments keep working unchanged."""
    if live_execution_enabled() and caps.provider_supports(provider, caps.LIVE_EXECUTION):
        from app.engine.kite_order_client import KiteOrderClient
        from app.engine.live_broker import LiveBroker
        from app.providers.live_kite import LiveExecutionKite
        s = get_settings()
        kite = LiveExecutionKite(api_key=s.kite_api_key or os.environ.get("KITE_API_KEY", ""))
        token = getattr(provider, "access_token", None)
        if token:
            kite.set_access_token(token)
        log.warn("🔴 LIVE EXECUTION ENABLED — the bot can place REAL orders on your "
                 "account (still gated by ARM, daily-loss halt, routing, and the "
                 "ownership guard).")
        # token_source keeps the order client's token in lock-step with the data
        # provider's: after a daily re-login the provider refreshes access_token, and
        # the order client picks it up on the next order — no backend restart needed.
        # tick_source resolves each order's REAL exchange tick from the provider's
        # Kite instrument dump (LT/MARUTI-class symbols don't trade on the
        # hardcoded 0.05 grid — the 2026-07-15 incident). Falls back to 0.05
        # inside KiteOrderClient if the provider has no such method.
        client = KiteOrderClient(kite, token_source=lambda: getattr(provider, "access_token", None),
                                 market_protection=s.market_protection_pct,
                                 tick_source=getattr(provider, "tick_size", None))
        broker = LiveBroker(provider, client, notifier=notifier,
                            poll_seconds=s.order_poll_seconds,
                            timeout_seconds=s.order_timeout_seconds,
                            **({} if deployment_id is None else {'deployment_id': deployment_id}))
        _refuse_live_broker_under_pytest(broker)
        return broker
    return PaperBroker(provider,
                       **({} if deployment_id is None else {'deployment_id': deployment_id}))
