"""The order-capable live client allows ONLY read + order + GTT routes (still
fail-closed: MF/SIP/convert and anything unknown stay blocked). It is the one
class that can place a real order, and it exists only behind the live-exec flags."""
import pytest

from app.providers.live_kite import LiveExecutionKite
from app.providers.safe_kite import OrderPlacementDisabled


@pytest.fixture
def k():
    return LiveExecutionKite(api_key="dummy")


@pytest.mark.parametrize("route", ["order.place", "order.modify", "order.cancel",
                                   "gtt.place", "gtt.modify", "gtt.delete"])
def test_order_and_gtt_routes_allowed(k, route):
    # allowed by the guard -> it fails at the network/auth layer, NOT with the block
    try:
        k._request(route, "POST", url_args={"variety": "regular", "order_id": "1",
                                             "trigger_id": "1"}, params={})
    except OrderPlacementDisabled:
        pytest.fail(f"order route '{route}' must be allowed for the live client")
    except Exception:
        pass


@pytest.mark.parametrize("route", ["mf.order.place", "mf.sip.place",
                                   "portfolio.positions.convert"])
def test_non_order_mutations_still_blocked(k, route):
    with pytest.raises(OrderPlacementDisabled):
        k._request(route, "POST", url_args={"order_id": "1", "sip_id": "1"}, params={})


def test_read_routes_allowed(k):
    try:
        k._request("market.quote.ltp", "GET", params={"i": ["NSE:INFY"]})
    except OrderPlacementDisabled:
        pytest.fail("read routes must be allowed")
    except Exception:
        pass
