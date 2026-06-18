"""
KiteProvider — live Zerodha Kite Connect implementation of MarketDataProvider.

This is the drop-in replacement for MockProvider once the owner has a Kite
Connect subscription. Set PT_PROVIDER=kite and KITE_API_KEY/KITE_API_SECRET,
complete the one-time OAuth in the dashboard, and the exact same engine runs
against the real market — nothing else changes.

Design notes:
  - Auth + token persistence ported from the repo's original kite_client.py.
  - Underlyings: indices use their spot feed (NSE/BSE); MCX/NCDEX commodities
    have no spot, so the near-month FUTURES contract is used as the underlying
    for both candles and LTP (this is also what the options are written on).
  - Instruments dumps are cached per-exchange per-day and used to resolve tokens,
    lot sizes, expiries and the option chain dynamically (contract specs change).
  - If an instrument has no live option chain (e.g. an illiquid agri month), the
    methods return None and the engine simply skips + logs it.
"""
from __future__ import annotations

import datetime as dt
import json
import os

from app.core.config import get_settings
from app.core.instruments import Instrument
from app.core.logging import log
from app.providers.base import Candle, MarketDataProvider, OptionChain, OptionQuote

TOKEN_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "access_token.json")


class KiteProvider(MarketDataProvider):
    name = "kite"

    def __init__(self) -> None:
        from kiteconnect import KiteConnect

        self.s = get_settings()
        self.api_key = os.environ.get("KITE_API_KEY", "")
        self.api_secret = os.environ.get("KITE_API_SECRET", "")
        self.kite = KiteConnect(api_key=self.api_key)
        self.access_token: str | None = None
        self._dumps: dict[str, tuple[str, list]] = {}   # exchange -> (date, instruments)
        self._fut_cache: dict[str, dict] = {}            # inst.key -> near future row
        self._load_saved_token()

    # ── auth (ported) ─────────────────────────────────────────────────────
    def _load_saved_token(self) -> None:
        if os.path.exists(TOKEN_FILE):
            try:
                data = json.load(open(TOKEN_FILE))
                if data.get("date") == str(dt.date.today()) and data.get("access_token"):
                    self.kite.set_access_token(data["access_token"])
                    self.access_token = data["access_token"]
            except Exception:
                pass

    def login_url(self) -> str | None:
        return self.kite.login_url()

    def complete_session(self, request_token: str) -> None:
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

    # ── instrument resolution ─────────────────────────────────────────────
    def _instruments(self, exchange: str) -> list:
        today = str(dt.date.today())
        cached = self._dumps.get(exchange)
        if cached and cached[0] == today:
            return cached[1]
        rows = self.kite.instruments(exchange)
        self._dumps[exchange] = (today, rows)
        return rows

    def _index_token(self, inst: Instrument) -> int | None:
        for row in self._instruments(inst.spot_exchange):
            if row.get("tradingsymbol") == inst.spot_symbol or row.get("name") == inst.spot_symbol:
                return row["instrument_token"]
        return None

    def _near_future(self, inst: Instrument) -> dict | None:
        today = dt.date.today()
        futs = [r for r in self._instruments(inst.spot_exchange)
                if r.get("name") == inst.option_name
                and r.get("instrument_type") == "FUT"
                and _as_date(r.get("expiry")) and _as_date(r["expiry"]) >= today]
        if not futs:
            return None
        futs.sort(key=lambda r: _as_date(r["expiry"]))
        self._fut_cache[inst.key] = futs[0]
        return futs[0]

    def _underlying_token(self, inst: Instrument) -> int | None:
        if inst.spot_exchange in ("NSE", "BSE"):
            return self._index_token(inst)
        fut = self._near_future(inst)
        return fut["instrument_token"] if fut else None

    def _underlying_quote_key(self, inst: Instrument) -> str | None:
        if inst.spot_exchange in ("NSE", "BSE"):
            return f"{inst.spot_exchange}:{inst.spot_symbol}"
        fut = self._near_future(inst)
        return f"{inst.spot_exchange}:{fut['tradingsymbol']}" if fut else None

    # ── market data ───────────────────────────────────────────────────────
    def get_candles(self, inst: Instrument, interval: str, days: int) -> list[Candle]:
        token = self._underlying_token(inst)
        if not token:
            log.warn(f"no underlying token resolved", instrument=inst.key)
            return []
        now = dt.datetime.now()
        raw = self.kite.historical_data(
            token, from_date=now - dt.timedelta(days=days), to_date=now, interval=interval)
        if not raw:
            return []
        raw = raw[:-1]  # drop the still-forming bar
        return [Candle(ts=r["date"].replace(tzinfo=None), open=r["open"], high=r["high"],
                       low=r["low"], close=r["close"], volume=float(r.get("volume", 0)))
                for r in raw]

    def get_ltp(self, inst: Instrument) -> float | None:
        key = self._underlying_quote_key(inst)
        if not key:
            return None
        try:
            return self.kite.ltp([key]).get(key, {}).get("last_price")
        except Exception as e:
            log.error(f"ltp failed: {e}", instrument=inst.key)
            return None

    def get_option_chain(self, inst: Instrument) -> OptionChain | None:
        today = dt.date.today()
        opts = [r for r in self._instruments(inst.segment)
                if r.get("name") == inst.option_name
                and r.get("instrument_type") in ("CE", "PE")
                and _as_date(r.get("expiry")) and _as_date(r["expiry"]) >= today]
        if not opts:
            log.warn("no live option chain", instrument=inst.key)
            return None
        expiry = min(_as_date(r["expiry"]) for r in opts)
        opts = [r for r in opts if _as_date(r["expiry"]) == expiry]

        spot = self.get_ltp(inst)
        if not spot:
            return None
        step = inst.strike_step
        atm = round(spot / step) * step
        near = [r for r in opts if abs(r["strike"] - atm) <= 10 * step]
        if not near:
            return None

        keys = [f"{inst.segment}:{r['tradingsymbol']}" for r in near]
        try:
            quotes_raw = self.kite.quote(keys)
        except Exception as e:
            log.error(f"quote failed: {e}", instrument=inst.key)
            return None

        out: list[OptionQuote] = []
        for r in near:
            key = f"{inst.segment}:{r['tradingsymbol']}"
            q = quotes_raw.get(key)
            if not q:
                continue
            depth = q.get("depth", {})
            bid = (depth.get("buy") or [{}])[0].get("price", 0.0)
            ask = (depth.get("sell") or [{}])[0].get("price", 0.0)
            ltp = q.get("last_price", 0.0)
            out.append(OptionQuote(
                instrument_key=inst.key,
                tradingsymbol=r["tradingsymbol"],
                exchange=inst.segment,
                strike=float(r["strike"]),
                expiry=expiry,
                option_type=r["instrument_type"],
                lot_size=int(r.get("lot_size") or inst.lot_size),
                ltp=ltp, bid=bid or ltp, ask=ask or ltp,
                volume=int(q.get("volume", 0)),
                oi=int(q.get("oi", 0)),
            ))
        if not out:
            return None
        return OptionChain(instrument_key=inst.key, spot=spot, expiry=expiry, quotes=out)

    def option_ltp(self, inst: Instrument, tradingsymbol: str, strike: float,
                   expiry: dt.date, option_type: str) -> float | None:
        key = f"{inst.segment}:{tradingsymbol}"
        try:
            return self.kite.ltp([key]).get(key, {}).get("last_price")
        except Exception as e:
            log.error(f"option ltp failed: {e}", instrument=inst.key)
            return None


def _as_date(v) -> dt.date | None:
    if v is None:
        return None
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    try:
        return dt.datetime.strptime(str(v), "%Y-%m-%d").date()
    except Exception:
        return None
