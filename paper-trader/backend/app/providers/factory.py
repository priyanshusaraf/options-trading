"""Pick the provider from config. `mock` (default) needs nothing; `kite` is live."""
from __future__ import annotations

from app.core.config import get_settings
from app.core.logging import log
from app.providers.base import MarketDataProvider

_provider: MarketDataProvider | None = None


def get_provider() -> MarketDataProvider:
    """Process-wide singleton provider."""
    global _provider
    if _provider is not None:
        return _provider
    s = get_settings()
    if s.provider == "kite":
        from app.providers.kite import KiteProvider
        _provider = KiteProvider()
        log.info("provider: KITE (live Zerodha)")
    else:
        from app.providers.mock import MockProvider
        _provider = MockProvider()
        log.info("provider: MOCK (synthetic market — no Kite needed)")
    return _provider
