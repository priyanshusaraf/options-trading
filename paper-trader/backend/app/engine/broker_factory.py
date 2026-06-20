"""
Broker selection. PaperBroker is the default everywhere. The order-placing
LiveBroker is built ONLY when BOTH live-execution flags are set AND the live Kite
data provider is active — two independent gates on top of the arm-to-trade gate.

  PT_EXECUTION=live
  PT_LIVE_ACK=I_UNDERSTAND_REAL_MONEY

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
    return (os.environ.get("PT_EXECUTION", "").strip().lower() == "live"
            and os.environ.get("PT_LIVE_ACK", "") == _ACK)


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
        return LiveBroker(provider, KiteOrderClient(kite), notifier=notifier)
    return PaperBroker(provider)
