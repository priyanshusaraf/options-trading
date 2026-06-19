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


class SafePaperKite(KiteConnect):
    """Drop-in for KiteConnect with all order-placement endpoints disabled."""

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
