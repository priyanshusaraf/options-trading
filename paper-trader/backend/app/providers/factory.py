"""Pick the provider from config. `mock` (default) needs nothing; `kite` is live."""
from __future__ import annotations

from app.core.config import get_settings
from app.core.logging import log
from app.providers.base import MarketDataProvider

_provider: MarketDataProvider | None = None


class UnknownProvider(ValueError):
    """A provider name no adapter answers to. Loud, because the alternative is a
    silent fall-through to the mock — a synthetic market wearing production's
    clothes, which `config.py`'s startup warning already exists to prevent."""


def provider_named(name: str) -> MarketDataProvider:
    """Construct the adapter called `name`, reusing the process singleton when it is
    the same one.

    Reuse is not an optimisation. A second `KiteProvider` would carry its own
    throttle (Kite's per-endpoint limits are per *client*, not per process, so two
    of them breach 1 req/s together) and its own `access_token`, which the OAuth
    callback sets on exactly one instance — the singleton. A split-role config that
    names `kite` for execution must therefore land on the object Connect Kite
    actually authenticated, not a fresh one that will never hold a token.

    Unlike `get_provider`, this refuses an unrecognised name instead of defaulting.
    `get_provider` reads a long-standing setting whose fall-through to mock is
    documented and warned about at startup; this reads a new one, where a typo
    would otherwise mean "route orders to a synthetic market".
    """
    wanted = (name or "").strip().lower()
    if wanted == (get_settings().provider or "").strip().lower():
        return get_provider()
    # The two simulators. Deliberately NOT in the broker registry: they are not brokers, and
    # listing them there would put a synthetic market in the set a user picks a broker from.
    if wanted == "mock":
        from app.providers.mock import MockProvider
        return MockProvider()
    if wanted == "replay":
        from app.providers.replay import ReplayProvider
        return ReplayProvider(get_settings().replay_path)
    # Everything else is a real broker, and the registry is the single answer to which of those
    # exist. Repeating the list here is how the two drift and the operator cannot tell which is
    # right; `test_broker_registry.py` holds them to agreement.
    from app.providers.brokers import BrokerNotSupported, data_adapter
    try:
        return data_adapter(wanted)()
    except BrokerNotSupported as e:
        raise UnknownProvider(str(e)) from e


def get_provider() -> MarketDataProvider:
    """Process-wide singleton provider."""
    global _provider
    if _provider is not None:
        return _provider
    s = get_settings()
    if s.provider == "replay":
        from app.providers.replay import ReplayProvider
        _provider = ReplayProvider(s.replay_path)
        log.info(f"provider: REPLAY ({s.replay_path}) — recorded session, "
                 f"cannot authenticate, cannot trade")
        return _provider
    if s.provider == "upstox":
        from app.providers.upstox import UpstoxProvider
        _provider = UpstoxProvider()
        # Said at startup because the consequence is invisible otherwise: this connection
        # serves prices and places nothing. Without PT_EXECUTION_PROVIDER naming a broker
        # that can, `make_broker` has no live path to build and the session is paper.
        log.info("provider: UPSTOX (data only — set PT_EXECUTION_PROVIDER for orders)")
        return _provider
    if s.provider == "kite":
        from app.providers.kite import KiteProvider
        _provider = KiteProvider()
        log.info("provider: KITE (live Zerodha)")
    else:
        from app.providers.mock import MockProvider
        _provider = MockProvider()
        log.info("provider: MOCK (synthetic market — no Kite needed)")
    return _provider
