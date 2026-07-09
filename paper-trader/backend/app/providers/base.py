"""
The provider contract.

Everything the engine needs from "the market" goes through `MarketDataProvider`.
Two implementations satisfy it:
  - MockProvider — a self-contained synthetic market (default; needs no Kite)
  - KiteProvider — live Zerodha Kite Connect

Because the engine only ever touches this interface, switching from paper-on-mock
to paper-on-live is a single config flag with zero code changes elsewhere.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime

from app.core.instruments import Instrument


@dataclass
class Candle:
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

    def to_dict(self) -> dict:
        return {
            "time": int(self.ts.timestamp()),
            "open": round(self.open, 2),
            "high": round(self.high, 2),
            "low": round(self.low, 2),
            "close": round(self.close, 2),
            "volume": self.volume,
        }


@dataclass
class OptionQuote:
    """One row of an option chain (+ greeks the picker fills in)."""
    instrument_key: str
    tradingsymbol: str
    exchange: str            # kite exchange prefix: NFO / BFO / MCX / NCDEX
    strike: float
    expiry: date
    option_type: str         # "CE" | "PE"
    lot_size: int
    ltp: float
    bid: float
    ask: float
    volume: int
    oi: int
    iv: float | None = None      # filled by the picker (Black-Scholes inversion)
    delta: float | None = None   # filled by the picker

    @property
    def spread(self) -> float:
        return max(0.0, self.ask - self.bid)

    @property
    def spread_pct(self) -> float:
        # No genuine two-sided market (a side has no resting depth, so bid or ask is 0)
        # reads as maximally illiquid, not ~0 — otherwise a missing side collapses the
        # spread and defeats the liquidity filter, letting the picker choose an
        # unfillable strike (audit C8).
        if self.bid <= 0 or self.ask <= 0 or self.ltp <= 0:
            return 1.0
        return self.spread / self.ltp

    def to_dict(self) -> dict:
        return {
            "tradingsymbol": self.tradingsymbol,
            "strike": self.strike,
            "expiry": self.expiry.isoformat(),
            "option_type": self.option_type,
            "lot_size": self.lot_size,
            "ltp": round(self.ltp, 2),
            "bid": round(self.bid, 2),
            "ask": round(self.ask, 2),
            "spread_pct": round(self.spread_pct, 4),
            "volume": self.volume,
            "oi": self.oi,
            "iv": round(self.iv, 4) if self.iv is not None else None,
            "delta": round(self.delta, 4) if self.delta is not None else None,
        }


@dataclass
class OptionChain:
    instrument_key: str
    spot: float
    expiry: date
    quotes: list[OptionQuote]


class MarketDataProvider(ABC):
    name: str = "base"

    # ── auth ──────────────────────────────────────────────────────────────
    @abstractmethod
    def is_authenticated(self) -> bool: ...

    def login_url(self) -> str | None:
        return None

    def complete_session(self, request_token: str) -> None:
        return None

    # ── live account (real broker only) ───────────────────────────────────
    def account_funds(self) -> dict | None:
        """Live account funds/margins: {available, net}. None if unavailable
        (mock, not authenticated, or a transient error)."""
        return None

    def account_positions(self) -> list[dict] | None:
        """Live net positions in the account: [{tradingsymbol, quantity, ...}].
        [] = genuinely flat; None = read failed (unavailable/unauthenticated). Callers
        must fail closed on None, never treat it as flat (audit C4). Used to keep the
        bot off the owner's positions."""
        return []

    def account_equity(self) -> float | None:
        """Best-effort live account net equity, for the bot-vs-you P&L split. None
        if unavailable (mock / not authenticated)."""
        return None

    # ── clock (real for Kite, simulated for Mock) ─────────────────────────
    def now(self) -> datetime:
        return datetime.now()

    def advance(self) -> bool:
        """Move the simulated clock one candle forward. No-op for live providers.
        Returns False when a mock has run out of history."""
        return True

    def is_tradable_now(self, inst: Instrument) -> bool:
        """Is this instrument's market in session right now? Always True for the
        mock (its synthetic clock is always 'open'); segment-hours-gated for Kite."""
        return True

    # ── market data ───────────────────────────────────────────────────────
    @abstractmethod
    def get_candles(self, inst: Instrument, interval: str, days: int) -> list[Candle]:
        """Completed candles, oldest first, newest (current) last."""

    @abstractmethod
    def get_ltp(self, inst: Instrument) -> float | None:
        """Latest traded price of the underlying (index spot / near future)."""

    def get_live_price(self, inst: Instrument) -> float | None:
        """Underlying price for the expanded per-instrument live view. Defaults to
        the LTP; the mock overrides it with display-only jitter. (Live providers
        get this for free — the per-instrument WebSocket relies on it.)"""
        return self.get_ltp(inst)

    def live_snapshot(self, instruments: list[Instrument], positions: list) -> dict:
        """Batch-ish latest spot/option ticks for UI chart updates.

        Providers with batch APIs should override this. The default keeps mock
        and tests simple.
        """
        by_key = {p.instrument_key: p for p in positions}
        out = {}
        for inst in instruments:
            pos = by_key.get(inst.key)
            spot = self.get_live_price(inst)
            premium = None
            # intraday-equity positions (option_type "EQ") have no option to price —
            # they mark to spot. Only price an actual option contract.
            if pos and pos.option_type != "EQ":
                premium = self.option_ltp(
                    inst, pos.tradingsymbol, pos.strike, pos.expiry, pos.option_type)
            out[inst.key] = {
                "time": self.now().isoformat(),
                "spot": spot,
                "option_premium": premium,
                "tradingsymbol": pos.tradingsymbol if pos else None,
            }
        return out

    @abstractmethod
    def get_option_chain(self, inst: Instrument) -> OptionChain | None:
        """Nearest tradable expiry chain, or None if none is available."""

    @abstractmethod
    def option_ltp(
        self,
        inst: Instrument,
        tradingsymbol: str,
        strike: float,
        expiry: date,
        option_type: str,
    ) -> float | None:
        """Current premium of a specific contract — used to reprice open positions
        and to feed the per-instrument option price chart."""
