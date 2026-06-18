"""
App config. Set your Kite credentials via environment variables:
    export KITE_API_KEY=xxxx
    export KITE_API_SECRET=xxxx
...or just paste them into API_KEY / API_SECRET below.

You need the PAID Kite Connect plan for market data — the free Personal plan
returns no quotes/candles.
"""
import os

API_KEY = os.environ.get("KITE_API_KEY", "")
API_SECRET = os.environ.get("KITE_API_SECRET", "")

# Redirect URL to register in your Kite developer console for OAuth login:
#   http://127.0.0.1:5000/api/session
REDIRECT_PORT = 5000

# Underlyings you can pick in the UI.
#   ltp_symbol  -> string used by kite.ltp() for the live price
#   token       -> instrument_token used by kite.historical_data() for candles
#   strike_step -> used later by the options/ATM phase (harmless now)
# Index tokens below are the commonly-used ones; the backend verifies them
# against the live instruments dump on startup and self-corrects if needed.
UNDERLYINGS = {
    "NIFTY 50":          {"ltp_symbol": "NSE:NIFTY 50",          "token": 256265, "strike_step": 50},
    "NIFTY BANK":        {"ltp_symbol": "NSE:NIFTY BANK",        "token": 260105, "strike_step": 100},
    "NIFTY FIN SERVICE": {"ltp_symbol": "NSE:NIFTY FIN SERVICE", "token": 257801, "strike_step": 50},
    "SENSEX":            {"ltp_symbol": "BSE:SENSEX",            "token": 265,    "strike_step": 100},
}

# Strategy params (mirror the Pine inputs)
DEFAULTS = {
    "ema_length": 50,
    "z_length": 50,
    "entry_z": 1.0,
    "slope_lookback": 5,
    "interval": "5minute",   # default candle size
    "days": 10,              # how much history to pull for warmup + view
}

# Candle sizes offered in the UI (value = Kite interval string)
INTERVALS = ["minute", "3minute", "5minute", "15minute", "30minute", "60minute", "day"]
