"""The single most important guarantee: this platform can NEVER place a real
order. SafePaperKite hard-disables every money-moving endpoint while leaving the
read-only market-data methods intact."""
import pytest

from app.providers.safe_kite import (
    DISABLED_METHODS,
    OrderPlacementDisabled,
    SafePaperKite,
)

READONLY = ["quote", "ltp", "ohlc", "historical_data", "instruments",
            "profile", "login_url", "orders", "positions", "holdings", "trades"]


@pytest.fixture
def kite():
    return SafePaperKite(api_key="dummy")


@pytest.mark.parametrize("method", DISABLED_METHODS)
def test_order_methods_raise(kite, method):
    with pytest.raises(OrderPlacementDisabled):
        getattr(kite, method)(variety="regular", tradingsymbol="X")


def test_place_order_specifically_blocked(kite):
    # the canonical money-mover — must never reach the exchange
    with pytest.raises(OrderPlacementDisabled):
        kite.place_order(variety="regular", exchange="NFO", tradingsymbol="NIFTY",
                         transaction_type="BUY", quantity=75, product="NRML",
                         order_type="MARKET")


@pytest.mark.parametrize("method", READONLY)
def test_readonly_methods_not_blocked(kite, method):
    # these must remain callable attributes (data access, no money movement)
    assert callable(getattr(kite, method))


def test_disabled_list_covers_known_movers():
    for m in ("place_order", "modify_order", "cancel_order", "exit_order",
              "place_gtt", "place_mf_order", "convert_position"):
        assert m in DISABLED_METHODS


# ── C2: transport-layer airtightness (the back door) ─────────────────────────
# Blocking only the named high-level methods leaves the low-level _post/_request
# transport reachable. A mutating route must be refused at the transport layer too.

@pytest.mark.parametrize("route", [
    "order.place", "order.modify", "order.cancel", "portfolio.positions.convert",
    "mf.order.place", "mf.sip.place", "gtt.place", "gtt.modify", "gtt.delete",
])
def test_mutating_route_blocked_at_transport(kite, route):
    # the back door: bypass the named method and hit the raw transport directly
    with pytest.raises(OrderPlacementDisabled):
        kite._post(route, url_args={"variety": "regular", "order_id": "1",
                                    "trigger_id": "1", "sip_id": "1"}, params={})


def test_raw_request_for_order_blocked(kite):
    with pytest.raises(OrderPlacementDisabled):
        kite._request("order.place", "POST", url_args={"variety": "regular"}, params={})


@pytest.mark.parametrize("route", [
    "market.quote.ltp", "market.quote", "market.historical", "market.instruments",
    "user.profile", "api.token", "orders", "portfolio.positions",
])
def test_readonly_route_not_blocked_by_guard(kite, route):
    # The guard must PERMIT read-only/auth routes. We don't have network/auth here,
    # so the call fails some other way — the point is it must NOT be the order block.
    try:
        kite._request(route, "GET", url_args={"exchange": "NFO",
                      "instrument_token": "1", "interval": "day"})
    except OrderPlacementDisabled:
        pytest.fail(f"read-only route '{route}' must not be blocked by the order guard")
    except Exception:
        pass  # network / auth / missing-token failure is expected and acceptable
