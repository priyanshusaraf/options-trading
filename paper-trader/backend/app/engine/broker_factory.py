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

_ACK = "I_UNDERSTAND_REAL_MONEY"


def live_execution_enabled() -> bool:
    """True only if execution=live AND the exact ack phrase are set. Prefers the
    .env-backed Settings (the single source of truth) and falls back to a real
    exported environment variable, so both `.env` and `export` paths work."""
    s = get_settings()
    execution = (s.execution or os.environ.get("PT_EXECUTION", "")).strip().lower()
    ack = (s.live_ack or os.environ.get("PT_LIVE_ACK", "")).strip()
    return execution == "live" and ack == _ACK


def make_broker(provider, notifier=None):
    if live_execution_enabled() and getattr(provider, "name", "") == "kite":
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
        client = KiteOrderClient(kite, token_source=lambda: getattr(provider, "access_token", None))
        return LiveBroker(provider, client, notifier=notifier,
                          poll_seconds=s.order_poll_seconds,
                          timeout_seconds=s.order_timeout_seconds)
    return PaperBroker(provider)
