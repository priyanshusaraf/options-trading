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
