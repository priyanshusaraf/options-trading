"""
LiveExecutionKite — the ONLY Kite client that can place a real order.

It reuses SafePaperKite's fail-closed transport allowlist and simply ADDS the
order + GTT routes. Everything else (MF, SIP, position convert, and any future
unknown route) stays blocked. It is constructed exclusively by the broker factory
when BOTH live-execution flags are set; the default everywhere else remains
SafePaperKite (which can place nothing).
"""
from __future__ import annotations

from kiteconnect import KiteConnect

from app.providers.safe_kite import ALLOWED_ROUTES, OrderPlacementDisabled

# The extra routes a real-money path needs: place/modify/cancel orders, and GTT
# triggers for the hybrid safety-net stop (D1).
ORDER_ROUTES = frozenset({
    "order.place", "order.modify", "order.cancel",
    "gtt.place", "gtt.modify", "gtt.delete",
})
LIVE_ALLOWED_ROUTES = ALLOWED_ROUTES | ORDER_ROUTES


class LiveExecutionKite(KiteConnect):
    """KiteConnect with the read allowlist + order/GTT routes; still fail-closed."""

    def _request(self, route, method, url_args=None, params=None,
                 is_json=False, query_params=None):
        if route not in LIVE_ALLOWED_ROUTES:
            raise OrderPlacementDisabled(
                f"live-exec: route '{route}' ({method}) is not permitted — the live "
                f"client allows only read, order and GTT routes."
            )
        return KiteConnect._request(self, route, method, url_args=url_args,
                                    params=params, is_json=is_json,
                                    query_params=query_params)
