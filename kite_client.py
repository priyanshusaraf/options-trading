"""
Thin wrapper around KiteConnect: handles the daily login/token flow,
verifies instrument tokens against the live dump, and fetches candles + LTP.
"""
from __future__ import annotations
import os
import json
import datetime as dt

from kiteconnect import KiteConnect

TOKEN_FILE = os.path.join(os.path.dirname(__file__), "access_token.json")


class KiteClient:
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.kite = KiteConnect(api_key=api_key)
        self.access_token = None
        self._instruments_cache = None
        self._load_saved_token()

    # ---- auth -------------------------------------------------------------
    def _load_saved_token(self):
        """Kite access tokens expire each morning; reuse today's if present."""
        if os.path.exists(TOKEN_FILE):
            try:
                data = json.load(open(TOKEN_FILE))
                if data.get("date") == str(dt.date.today()) and data.get("access_token"):
                    self.kite.set_access_token(data["access_token"])
                    self.access_token = data["access_token"]
            except Exception:
                pass

    def login_url(self) -> str:
        return self.kite.login_url()

    def complete_session(self, request_token: str):
        data = self.kite.generate_session(request_token, api_secret=self.api_secret)
        self.access_token = data["access_token"]
        self.kite.set_access_token(self.access_token)
        json.dump({"date": str(dt.date.today()), "access_token": self.access_token},
                  open(TOKEN_FILE, "w"))

    def is_authenticated(self) -> bool:
        if not self.access_token:
            return False
        try:
            self.kite.profile()
            return True
        except Exception:
            return False

    # ---- data -------------------------------------------------------------
    def resolve_token(self, ltp_symbol: str, fallback_token: int) -> int:
        """Verify/repair an index instrument_token from the live dump.
        Index tokens rarely change, but this keeps candles working if they do."""
        try:
            exch, name = ltp_symbol.split(":", 1)
            if self._instruments_cache is None:
                self._instruments_cache = self.kite.instruments(exch)
            for ins in self._instruments_cache:
                if ins.get("tradingsymbol") == name or ins.get("name") == name:
                    return ins["instrument_token"]
        except Exception:
            pass
        return fallback_token

    def ltp(self, symbol: str):
        r = self.kite.ltp([symbol])
        return r.get(symbol, {}).get("last_price")

    def candles(self, instrument_token: int, interval: str, days: int):
        now = dt.datetime.now()
        return self.kite.historical_data(
            instrument_token,
            from_date=now - dt.timedelta(days=days),
            to_date=now,
            interval=interval,
        )
