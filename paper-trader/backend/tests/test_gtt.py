"""GTT safety-net stop payload. A SINGLE Good-Till-Triggered order that SELLs the
bot's long option when the premium falls to the stop — it lives on Zerodha's
servers, so it protects the position even if the bot/laptop/internet dies."""
from app.engine.gtt import stop_gtt_params


def test_single_sell_stop_payload():
    p = stop_gtt_params("NIFTY25CE", "NFO", 75, trigger_price=110.004,
                        last_price=150.0, product="NRML")
    assert p["trigger_type"] == "single"
    assert p["tradingsymbol"] == "NIFTY25CE" and p["exchange"] == "NFO"
    assert p["trigger_values"] == [110.0]            # rounded to tick precision
    assert p["last_price"] == 150.0
    o = p["orders"][0]
    assert o["transaction_type"] == "SELL"
    assert o["quantity"] == 75
    assert o["order_type"] == "LIMIT" and o["price"] == 110.0
    assert o["product"] == "NRML"
