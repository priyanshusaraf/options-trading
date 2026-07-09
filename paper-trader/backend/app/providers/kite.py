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
import threading
import time as _time
from datetime import datetime

from app.core import market_hours
from app.core.config import get_settings
from app.core.instruments import Instrument
from app.core.logging import log
from app.providers.base import Candle, MarketDataProvider, OptionChain, OptionQuote

TOKEN_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "access_token.json")

# Kite documented rate limits: quote/ltp/ohlc = 1 req/s, historical = 3 req/s.
# We keep a small safety margin under each.
_MIN_INTERVAL = {"quote": 1.05, "historical": 0.40}


class _Throttle:
    """Serialises calls per category so we never breach Kite's per-endpoint
    rate limits (which would return HTTP 429). Thread-safe: the engine loop and
    the per-instrument WebSocket can both call through it."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last: dict[str, float] = {}

    def wait(self, category: str) -> None:
        interval = _MIN_INTERVAL.get(category, 1.05)
        with self._lock:
            now = _time.monotonic()
            last = self._last.get(category, 0.0)
            delay = interval - (now - last)
            if delay > 0:
                _time.sleep(delay)
            self._last[category] = _time.monotonic()


class KiteProvider(MarketDataProvider):
    name = "kite"

    def __init__(self) -> None:
        from app.providers.safe_kite import SafePaperKite

        self.s = get_settings()
        # Prefer the loaded Settings (reads .env via pydantic); fall back to a
        # real OS env var if one is exported.
        self.api_key = self.s.kite_api_key or os.environ.get("KITE_API_KEY", "")
        self.api_secret = self.s.kite_api_secret or os.environ.get("KITE_API_SECRET", "")
        # SafePaperKite hard-disables every order-placement endpoint — this
        # platform is paper-only and uses Kite for market data exclusively.
        self.kite = SafePaperKite(api_key=self.api_key)
        self.access_token: str | None = None
        self._dumps: dict[str, tuple[str, list]] = {}   # exchange -> (date, instruments)
        self._fut_cache: dict[str, dict] = {}            # inst.key -> near future row
        self._throttle = _Throttle()
        self._load_saved_token()

    # ── throttled Kite calls (respect documented rate limits) ─────────────
    def _ltp(self, keys: list[str]) -> dict:
        self._throttle.wait("quote")
        return self.kite.ltp(keys)

    def _quote(self, keys: list[str]) -> dict:
        self._throttle.wait("quote")
        return self.kite.quote(keys)

    def _historical(self, token: int, frm, to, interval: str) -> list:
        self._throttle.wait("historical")
        return self.kite.historical_data(token, from_date=frm, to_date=to, interval=interval)

    def is_tradable_now(self, inst: Instrument) -> bool:
        # Gate on the venue that prints the candles we trade on (spot_exchange),
        # which is also where the option chain's underlying trades.
        return market_hours.is_open(inst.spot_exchange) or market_hours.is_open(inst.segment)

    # ── clock ─────────────────────────────────────────────────────────────
    def now(self) -> datetime:
        """IST wall-clock, tz-naive — matching the candle epoch convention.

        Historical candles in this app carry IST wall-clock timestamps (the raw
        Kite bar tz is stripped in get_candles, keeping the IST wall time), and
        the frontend re-anchors any offset-less time to +05:30. The inherited
        base.now() returns naive *server-local* time, so on a UTC host (the cloud
        default) the live snapshot/ws timestamps would land 5.5h behind the IST
        candles — live bars would never form (time <= prev.time) and 'last update'
        would render at the wrong clock. Returning IST wall-clock keeps the live
        feed consistent with the historical bars. Clock only — no auth/order/quote
        path is touched."""
        return market_hours.now_ist().replace(tzinfo=None)

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

    # ── live account reads (margins + positions are read-only, allowlisted) ─
    def account_funds(self) -> dict | None:
        try:
            m = self.kite.margins()
        except Exception as e:
            log.warn(f"margins() failed: {e}")
            return None
        eq = (m or {}).get("equity", {}) or {}
        avail = eq.get("available", {}) or {}
        live = avail.get("live_balance")
        if live is None:
            live = avail.get("cash", 0.0)
        return {"available": float(live or 0.0), "net": float(eq.get("net", 0.0) or 0.0)}

    def account_equity(self) -> float | None:
        funds = self.account_funds()
        return funds["net"] if funds else None

    def account_positions(self) -> list[dict] | None:
        try:
            pos = self.kite.positions()
        except Exception as e:
            log.warn(f"positions() failed: {e}")
            return None   # read failed — NOT a flat account (audit C4). Callers fail closed.
        net = (pos or {}).get("net", []) or []
        return [{"tradingsymbol": r.get("tradingsymbol"),
                 "quantity": int(r.get("quantity", 0) or 0),
                 "exchange": r.get("exchange"),
                 "product": r.get("product")}
                for r in net]

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
        try:
            rows = self.kite.instruments(exchange)
        except Exception as e:
            # not authenticated yet / transient API error — degrade gracefully so
            # callers (candles, option chain, ltp) return empty instead of 500.
            log.warn(f"instruments({exchange}) failed: {e}")
            return []
        self._dumps[exchange] = (today, rows)
        return rows

    def _index_token(self, inst: Instrument) -> int | None:
        for row in self._instruments(inst.spot_exchange):
            if row.get("tradingsymbol") == inst.spot_symbol or row.get("name") == inst.spot_symbol:
                return row["instrument_token"]
        return None

    def _name_candidates(self, inst: Instrument) -> list[str]:
        """Names as Kite may publish them.

        MCX mini commodity contracts are sometimes configured internally with an
        `M` suffix (e.g. COPPERM) while Kite publishes the live derivatives under
        the base commodity name (COPPER). Keep exact names first, then fall back
        to the stripped form.
        """
        names: list[str] = []
        for value in (inst.option_name, inst.spot_symbol, inst.key):
            if value and value not in names:
                names.append(value)
            if inst.segment in ("MCX", "NCDEX") and value.endswith("M"):
                base = value[:-1]
                if base and base not in names:
                    names.append(base)
        return names

    def _contract_lot_size(self, inst: Instrument, row: dict) -> int:
        """Effective unit count for one paper lot.

        Kite's MCX instrument dump reports `lot_size=1` for commodity option
        rows. The quoted premium is still per commodity unit for our risk/cash
        accounting, so use the universe contract unit as the floor for MCX/NCDEX.
        """
        row_lot = int(row.get("lot_size") or 0)
        if inst.segment in ("MCX", "NCDEX") and row_lot <= 1:
            return inst.lot_size
        return row_lot or inst.lot_size

    def _near_future(self, inst: Instrument) -> dict | None:
        today = dt.date.today()
        names = set(self._name_candidates(inst))
        futs = [r for r in self._instruments(inst.spot_exchange)
                if r.get("name") in names
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
        now = self.now()   # IST wall-clock (naive), NOT server-local — a UTC host would
                           # otherwise truncate the window ~5.5h early and drop recent bars (H7)
        try:
            raw = self._historical(token, now - dt.timedelta(days=days), now, interval)
        except Exception as e:
            log.error(f"historical_data failed: {e}", instrument=inst.key)
            return []
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
            return self._ltp([key]).get(key, {}).get("last_price")
        except Exception as e:
            log.error(f"ltp failed: {e}", instrument=inst.key)
            return None

    def live_snapshot(self, instruments: list[Instrument], positions: list) -> dict:
        now = self.now().isoformat()
        out = {inst.key: {"time": now, "spot": None, "option_premium": None,
                          "tradingsymbol": None}
               for inst in instruments}

        underlying_keys: dict[str, str] = {}
        for inst in instruments:
            key = self._underlying_quote_key(inst)
            if key:
                underlying_keys[inst.key] = key
        if underlying_keys:
            try:
                raw = self._ltp(list(underlying_keys.values()))
                for inst_key, quote_key in underlying_keys.items():
                    out[inst_key]["spot"] = raw.get(quote_key, {}).get("last_price")
            except Exception as e:
                log.error(f"live underlying snapshot failed: {e}")

        by_inst = {p.instrument_key: p for p in positions}
        option_keys: dict[str, str] = {}
        for inst in instruments:
            pos = by_inst.get(inst.key)
            if pos:
                option_keys[inst.key] = f"{inst.segment}:{pos.tradingsymbol}"
                out[inst.key]["tradingsymbol"] = pos.tradingsymbol
        if option_keys:
            try:
                raw = self._ltp(list(option_keys.values()))
                for inst_key, quote_key in option_keys.items():
                    out[inst_key]["option_premium"] = raw.get(quote_key, {}).get("last_price")
            except Exception as e:
                log.error(f"live option snapshot failed: {e}")

        return out

    def get_option_chain(self, inst: Instrument) -> OptionChain | None:
        today = dt.date.today()
        names = set(self._name_candidates(inst))
        opts = [r for r in self._instruments(inst.segment)
                if r.get("name") in names
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
            quotes_raw = self._quote(keys)
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
                lot_size=self._contract_lot_size(inst, r),
                # keep raw bid/ask (0 when a depth side is empty) — do NOT substitute
                # ltp, which would hide a one-sided book and collapse spread_pct (C8)
                ltp=ltp, bid=bid, ask=ask,
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
            return self._ltp([key]).get(key, {}).get("last_price")
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
