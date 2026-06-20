"""
SafePaperKite — a KiteConnect subclass that makes real order placement
structurally impossible.

The whole platform is paper-only: fills are simulated internally and Kite is
used for MARKET DATA ONLY (quotes, historical candles, the instruments dump).
To guarantee — even against a future code change or a stray call — that no real
money can ever move, every state-changing endpoint on the SDK is overridden to
raise immediately. Read-only endpoints (quote/ltp/ohlc/historical_data/
instruments/profile, and the GET-only orders/positions/holdings/gtt *readers*)
are left untouched.

If anything ever tries to place/modify/cancel an order, GTT, MF order or convert
a position, it fails loudly here instead of hitting the exchange.
"""
from __future__ import annotations

from kiteconnect import KiteConnect

# Every SDK method that creates, modifies, cancels or converts a real
# order / GTT / SIP / position. These are hard-disabled. The list mirrors the
# mutating methods on kiteconnect's KiteConnect (pykiteconnect v4/v5); any new
# mutating method should be added here.
DISABLED_METHODS = (
    "place_order",
    "modify_order",
    "cancel_order",
    "exit_order",
    "place_autoslice_order",
    "place_gtt",
    "modify_gtt",
    "delete_gtt",
    "place_mf_order",
    "cancel_mf_order",
    "place_mf_sip",
    "modify_mf_sip",
    "cancel_mf_sip",
    "convert_position",
)


class OrderPlacementDisabled(RuntimeError):
    """Raised if any code path attempts a real (money-moving) Kite call."""


# Defense in depth: blocking the named methods above only guards the front door.
# Every SDK call — including the named methods — funnels through `_request(route,
# method, ...)`. We enforce a FAIL-CLOSED allowlist there: only these read-only,
# auth, and margin/charge-CALCULATOR routes are permitted; every other route
# (now or added by a future SDK version) is refused. This closes the back door
# where `kite._post("order.place", ...)` would otherwise reach the exchange.
ALLOWED_ROUTES = frozenset({
    # auth / session (login + token lifecycle)
    "api.token", "api.token.renew", "api.token.invalidate",
    # read-only account / portfolio (GET only)
    "user.profile", "user.margins", "user.margins.segment",
    "orders", "order.info", "trades", "order.trades",
    "portfolio.positions", "portfolio.holdings", "portfolio.holdings.auction",
    "mf.orders", "mf.order.info", "mf.sips", "mf.sip.info",
    "mf.holdings", "mf.instruments",
    # market data — the platform's actual use
    "market.instruments", "market.instruments.all", "market.margins",
    "market.historical", "market.trigger_range",
    "market.quote", "market.quote.ohlc", "market.quote.ltp",
    # GTT reads only (NOT place/modify/delete)
    "gtt", "gtt.info",
    # margin / charge CALCULATORS — compute only, place no order
    "order.margins", "order.margins.basket", "order.contract_note",
})


class SafePaperKite(KiteConnect):
    """Drop-in for KiteConnect with all order-placement endpoints disabled —
    at the named-method layer AND the transport layer (fail-closed allowlist)."""

    def _blocked(self, _name: str):
        def _raise(*_args, **_kwargs):
            raise OrderPlacementDisabled(
                f"paper-trading: '{_name}' is disabled — this platform never "
                f"places real orders. Kite is used for market data only."
            )
        return _raise

    def __getattribute__(self, name: str):
        # Intercept the disabled methods before the real bound method is returned.
        if name in DISABLED_METHODS:
            return object.__getattribute__(self, "_blocked")(name)
        return object.__getattribute__(self, name)

    def _request(self, route, method, url_args=None, params=None,
                 is_json=False, query_params=None):
        # The single chokepoint: refuse any non-allowlisted route before it can
        # form a URL or touch the network. Fail-closed — unknown routes are blocked.
        if route not in ALLOWED_ROUTES:
            raise OrderPlacementDisabled(
                f"paper-trading: route '{route}' ({method}) is blocked at the "
                f"transport layer — this platform never places real orders. Only "
                f"read-only market-data and auth routes are permitted."
            )
        return KiteConnect._request(self, route, method, url_args=url_args,
                                    params=params, is_json=is_json,
                                    query_params=query_params)
