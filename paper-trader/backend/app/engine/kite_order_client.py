"""
OrderClient adapter over a LiveExecutionKite — the bridge between our
broker-agnostic order_executor and Kite's order API.

  place(req)  -> kite.place_order(...) -> order id
  status(id)  -> last kite.order_history(id) row, normalised

variety="regular", product="NRML" so options can be carried overnight (the engine
supports overnight holding). The owner's discretionary positions are never touched
by this client — it only ever places the specific orders the LiveBroker hands it.
"""
from __future__ import annotations

from app.engine.gtt import TICK_SIZE, round_to_tick, stop_gtt_params
from app.engine.kite_venue import kite_exchange, kite_product_for_charge_segment
from app.engine.order_executor import OrderRequest
from app.engine.venue import INTRADAY_EQUITY_CHARGE_SEGMENTS

# Charge-segments that trade as intraday equity (MIS): same-day, leveraged, the
# broker auto-squares-off near close. Everything else (options/futures) is NRML.
# Kept as a module-level name for existing importers; the definition now lives in
# venue.py as the *neutral* classification, with the Kite spelling in kite_venue.
EQUITY_INTRADAY_SEGMENTS = INTRADAY_EQUITY_CHARGE_SEGMENTS

LEGACY_BOT_TAG = "pt-bot"
INTENT_TAG_PREFIX = "pti-"


class PreWireProtectionRejected(ValueError):
    """Local validation proved that no protective request reached the broker."""


class CredentialWithdrawn(RuntimeError):
    """The connection had an access token and no longer does.

    Distinct from "never authenticated": this means a credential that WAS working has been
    revoked, rotated out, or become unreadable. Nothing may be sent on the cached one.

    A `RuntimeError` rather than a `ProviderReadError` deliberately — this is not a failed read
    of market data, it is a refusal to act, and `execute_order` must not classify it as a
    transient data problem to be retried.
    """


def is_strategy_os_tag(tag: object) -> bool:
    """Recognise only the legacy bot tag or a durable 20-character intent tag."""
    if tag == LEGACY_BOT_TAG:
        return True
    if not isinstance(tag, str) or len(tag) != 20 or not tag.startswith(INTENT_TAG_PREFIX):
        return False
    return all(ch in "0123456789abcdef" for ch in tag[len(INTENT_TAG_PREFIX):])


def product_for_segment(segment: str, default: str = "NRML") -> str:
    """Kite product code for a charge-segment: MIS for intraday equity, else the
    client default (NRML for options/futures so they can carry overnight).

    Kept as the historical entry point (runner.py imports it); the mapping itself
    now lives once, in kite_venue, behind the neutral `Tenor` vocabulary."""
    return kite_product_for_charge_segment(segment, default)


def exchange_for_segment(segment: str) -> str:
    """Real Kite exchange for a charge-segment. Intraday-equity charge-segments carry
    an _INTRADAY suffix for the charge schedule; the exchange Kite wants is the bare
    NSE/BSE. Options/futures segments (NFO/BFO/MCX/NCDEX) are already Kite exchanges."""
    return kite_exchange(segment)


class KiteOrderClient:
    def __init__(self, kite, *, token_source=None,
                 product: str = "NRML", variety: str = "regular",
                 market_protection: float = -1.0, tick_source=None) -> None:
        self.kite = kite
        self.product = product
        self.variety = variety
        # tick_source(tradingsymbol, exchange) -> float | None — the real per-
        # instrument exchange tick (sourced from the Kite instrument dump). Every
        # trigger/limit price sent to Zerodha must land on THIS grid, not a
        # hardcoded 0.05 one: the 2026-07-15 incident was 2,437 SL-M placements
        # rejected outright because LT (tick 0.10) and MARUTI (tick 1.00) don't
        # trade on the 0.05 grid. No source, a lookup failure, or an unresolved
        # symbol all fall back to the standard 0.05 grid (see `_tick`).
        self._tick_source = tick_source
        # Market protection for MARKET/SL-M orders. Mandatory since SEBI's 1-Apr-2026
        # rule: a market order placed via API WITHOUT non-zero protection is REJECTED
        # (all segments, MCX included). -1 = automatic exchange-guideline protection;
        # >0..100 = an explicit cap %. A 0 means "unprotected" and would be rejected,
        # so it is coerced to -1 at send time — we never send an unprotected market order.
        self.market_protection = market_protection
        # callable returning the data provider's CURRENT access token. Synced before
        # every Kite call so a daily re-login (which refreshes the provider token)
        # flows through to order placement without rebuilding the broker.
        self._token_source = token_source
        self._last_token: str | None = None
        # Latched, and never reset. `_last_token` alone was not enough: `_sync_token` cleared it
        # before raising, so the SECOND withdrawn call saw None, took the never-authenticated
        # branch and returned normally — the refusal fired exactly once and then went quiet.
        # Orders after that reached Kite with a blanked token and failed as a generic
        # TokenException, which `find_fill` swallows into `None`. Found by the same review.
        self._ever_authenticated = False
        # Adopt the credential HERE, so construction and refresh are the same code path.
        #
        # This line closes a hole that an independent execution-safety review found in the very
        # fix that was supposed to close it (2026-08-10). `broker_factory` authenticated the wire
        # object itself — `token = conn.token_source(); kite.set_access_token(token)` — and then
        # built this client with `_last_token = None`. So the client HELD a live token it had
        # never recorded, and `_sync_token`'s withdrawal branch (`if self._last_token is not
        # None`) could never fire. A connection revoked after startup went on placing REAL orders
        # for the life of the process, which is precisely the defect the withdrawal branch exists
        # to prevent. The tests missed it because they called `_sync_token()` first, seeding
        # `_last_token` — a shape production never takes.
        #
        # Swallowing here is deliberate and narrow: a client constructed before the connection
        # has authenticated is the ordinary pre-Connect-Kite state, and it must not prevent the
        # broker from being built. It leaves `_last_token` None, which is the honest "never
        # authenticated" state, and the first successful sync records it.
        try:
            self._sync_token()
        except Exception:                          # noqa: BLE001 — see above
            pass

    def _sync_token(self) -> None:
        """Adopt the connection's current access token, and REFUSE if it has been withdrawn.

        The refusal is the part that was missing, and its absence was a real hole (found by an
        independent security review, 2026-08-10). This method used to read

            if tok and tok != self._last_token: ...

        so a `None` was simply discarded and `self.kite` kept whatever token was set when the
        broker was constructed. Three separate docstrings — two of them in
        `providers/connection_store.py` — asserted that a `None` from the token source meant the
        order would be "refused unauthenticated". **No such mechanism existed.** Revoking a
        connection, rotating `PT_CREDENTIAL_KEY`, or a database read failure all produced a
        `None` that changed nothing, and the engine kept placing REAL orders on that account for
        the life of the process while every health check stayed green.

        The withdrawal case is treated separately from "never had one" on purpose:

          * **Never had a token** (`_ever_authenticated is False`) — unchanged. A connection
            that has not authenticated yet fails at Kite with its own auth error, which is the
            pre-existing behaviour and is already safe.
          * **Had one, and it is now gone** — the credential was WITHDRAWN. Clearing it and
            raising is the only correct move: the alternative is authenticating as an account
            whose owner has just told us they no longer want us there.

        The flag is `_ever_authenticated`, **not** `_last_token`, and it is latched. Keying the
        branch on `_last_token` was wrong twice over: the composition root authenticated the wire
        object without recording it (so the branch never fired at all in production), and
        clearing it before raising meant the second withdrawn call took the never-authenticated
        branch and proceeded silently.

        Raising rather than returning a sentinel because every caller here is a wire call, and
        `execute_order` already turns an exception on `place` into a non-placement rather than an
        assumed fill. A refused cancel likewise stops the caller sending a closing order, which
        is the conservative direction.
        """
        if not self._token_source:
            return
        tok = self._token_source()
        if tok:
            if tok != self._last_token:
                self.kite.set_access_token(tok)
                self._last_token = tok
            self._ever_authenticated = True
            return
        if self._ever_authenticated:
            self._last_token = None
            try:
                self.kite.set_access_token("")
            except Exception:                      # noqa: BLE001 — clearing must never mask the refusal
                pass
            raise CredentialWithdrawn(
                "the execution connection no longer holds an access token (revoked, key "
                "rotated, or the credential could not be read). Refusing to place or modify an "
                "order with the previously cached token.")

    def _tick(self, tradingsymbol: str | None, exchange: str | None) -> float:
        """Resolve the real exchange tick for this instrument. No tick source, no
        symbol, an unrecognised symbol, or any lookup failure (transient dump
        error) all fall back to the standard 0.05 grid rather than risk sending
        an unrounded or wrongly-rounded trigger."""
        if not self._tick_source or not tradingsymbol:
            return TICK_SIZE
        try:
            tick = self._tick_source(tradingsymbol, exchange)
        except Exception:
            return TICK_SIZE
        return float(tick) if tick else TICK_SIZE

    def tick_size(self, tradingsymbol: str, exchange: str | None = None) -> float:
        """Public form of `_tick` — the `ExecutionVenue.tick_size` verb. Same
        fail-safe fallback to the 0.05 grid; no new behaviour."""
        return self._tick(tradingsymbol, exchange)

    # ── GTT safety-net stop (lives on Zerodha's servers) ──────────────────
    def place_stop_gtt(self, tradingsymbol: str, exchange: str, qty: int,
                       trigger_price: float, last_price: float, side: str = "SELL") -> str:
        # Zerodha accepts GTTs only for CNC/NRML — an equity-exchange (MIS) GTT is
        # rejected server-side, silently leaving the position stopless (the
        # 2026-07-03 class of failure: option GTTs worked, intraday ones never
        # existed). Refuse locally and loudly; the MIS backstop is place_stop_order.
        if exchange in ("NSE", "BSE"):
            raise PreWireProtectionRejected(
                f"GTT not supported on equity exchange {exchange} "
                f"(intraday/MIS) — use place_stop_order (SL-M) instead")
        self._sync_token()
        res = self.kite.place_gtt(**stop_gtt_params(
            tradingsymbol, exchange, qty, trigger_price, last_price, self.product, side,
            tick_size=self._tick(tradingsymbol, exchange)))
        tid = res.get("trigger_id") if isinstance(res, dict) else res
        return str(tid)

    def modify_stop_gtt(self, trigger_id: str, tradingsymbol: str, exchange: str,
                        qty: int, trigger_price: float, last_price: float, side: str = "SELL"):
        if exchange in ("NSE", "BSE"):
            raise ValueError(f"GTT not supported on equity exchange {exchange} "
                             f"(intraday/MIS) — use modify_stop_order (SL-M) instead")
        self._sync_token()
        return self.kite.modify_gtt(trigger_id=trigger_id, **stop_gtt_params(
            tradingsymbol, exchange, qty, trigger_price, last_price, self.product, side,
            tick_size=self._tick(tradingsymbol, exchange)))

    def delete_gtt(self, trigger_id: str):
        self._sync_token()
        return self.kite.delete_gtt(trigger_id=trigger_id)

    # ── SL-M protective stop (a real resting order — the MIS backstop) ────
    def place_stop_order(self, tradingsymbol: str, exchange: str, qty: int,
                         trigger_price: float, side: str = "SELL",
                         tag: str | None = None) -> str:
        """Rest a Stop-Loss-Market order at the exchange as the protective stop for an
        intraday (MIS) position — GTT can't be used for MIS (Zerodha allows GTT only on
        CNC/NRML). It triggers a MARKET order when the LTP crosses `trigger_price`: a
        LONG is protected by a SELL below entry, a SHORT by a BUY (cover) above. Returns
        the broker order id."""
        self._sync_token()
        product = "MIS" if exchange in ("NSE", "BSE") else self.product
        kw = dict(variety=self.variety, exchange=exchange, tradingsymbol=tradingsymbol,
                  transaction_type=side, quantity=int(qty), product=product,
                  order_type="SL-M",
                  trigger_price=round_to_tick(trigger_price, self._tick(tradingsymbol, exchange)),
                  # SL-M fires a MARKET order → same SEBI 1-Apr-2026 protection as MARKET.
                  market_protection=self.market_protection or -1.0)
        if tag:
            kw["tag"] = tag
        return str(self.kite.place_order(**kw))

    def modify_stop_order(self, order_id: str, trigger_price: float,
                          tradingsymbol: str | None = None, exchange: str | None = None,
                          quantity: int | None = None):
        """Re-price a resting SL-M stop's trigger (trailing the stop as it ratchets).
        `tradingsymbol`/`exchange`, when supplied, resolve the instrument's real tick
        so the re-price lands on the SAME grid the initial placement used — without
        them this falls back to the standard 0.05 grid."""
        self._sync_token()
        kw = dict(
            variety=self.variety, order_id=order_id,
            trigger_price=round_to_tick(trigger_price, self._tick(tradingsymbol, exchange)))
        if quantity is not None:
            kw["quantity"] = int(quantity)
        return self.kite.modify_order(**kw)

    def place(self, req: OrderRequest) -> str:
        self._sync_token()
        # req.product overrides the client default (MIS for intraday equity); the
        # options/futures path passes None and keeps the client's NRML.
        product = req.product or self.product
        kw = dict(variety=self.variety, exchange=req.exchange,
                  tradingsymbol=req.tradingsymbol, transaction_type=req.side,
                  quantity=req.qty, product=product, order_type=req.order_type)
        if req.order_type == "LIMIT" and req.limit_price is not None:
            # E9: every trigger path snaps to the real per-instrument tick, but the entry
            # LIMIT price was forwarded untouched — and execution_policy computes it on a
            # hardcoded 0.05 grid. On a coarser-grid contract the exchange rejects the
            # order outright ("Tick size for this script is …") = a silently missed entry.
            kw["price"] = round_to_tick(req.limit_price,
                                        self._tick(req.tradingsymbol, req.exchange))
        if req.order_type == "MARKET":
            # never unprotected: a 0/falsy value would be rejected -> fall back to -1 (auto)
            kw["market_protection"] = self.market_protection or -1.0
        if req.tag:
            kw["tag"] = req.tag
        return self.kite.place_order(**kw)

    def cancel(self, order_id: str):
        """Cancel a working order (same variety it was placed with). Used to kill a
        timed-out-but-still-working order before placing another on the same contract,
        so a contract never has two live bot orders at once."""
        self._sync_token()
        return self.kite.cancel_order(variety=self.variety, order_id=order_id)

    def status(self, order_id: str) -> dict:
        self._sync_token()
        hist = self.kite.order_history(order_id) or []
        last = hist[-1] if hist else {}
        return {
            "status": last.get("status"),
            "filled_qty": int(last.get("filled_quantity", 0) or 0),
            "avg_price": float(last.get("average_price", 0.0) or 0.0),
            "reason": last.get("status_message") or "",
        }

    def gtt_status(self, trigger_id) -> dict:
        """State of a resting GTT, normalized to {status, triggered}. A GTT trigger_id is
        NOT an order_id, so `status()`/order_history can't answer this — it needs
        `kite.get_gtt`. Used by reconcile_orphans (E6) to tell the bot's OWN GTT stop
        firing apart from a genuinely external exit."""
        self._sync_token()
        g = self.kite.get_gtt(trigger_id) or {}
        status = str(g.get("status", "")).lower()
        return {"status": status, "triggered": status == "triggered"}

    def gtts(self) -> list[dict]:
        """List GTT identity fields needed to reconcile an uncertain stop submit."""
        self._sync_token()
        normalized = []
        for trigger in self.kite.get_gtts() or []:
            condition = trigger.get("condition") or {}
            orders = trigger.get("orders") or []
            order = orders[0] if orders else {}
            trigger_id = trigger.get("trigger_id", trigger.get("id"))
            normalized.append({
                "trigger_id": str(trigger_id) if trigger_id is not None else None,
                "status": trigger.get("status"),
                "tradingsymbol": condition.get("tradingsymbol"),
                "exchange": condition.get("exchange"),
                "side": order.get("transaction_type"),
                "qty": int(order.get("quantity", 0) or 0),
                "trigger_price": float((condition.get("trigger_values") or [0.0])[0] or 0.0),
            })
        return normalized

    def orders(self) -> list[dict]:
        """Today's order identities for entry and protective-stop recovery."""
        self._sync_token()
        raw = self.kite.orders()
        if raw is None:
            raise RuntimeError("broker order book is unavailable")
        return [{
            "order_id": o.get("order_id"),
            "tradingsymbol": o.get("tradingsymbol"),
            "tag": o.get("tag"),
            "status": o.get("status"),
            "filled_qty": int(o.get("filled_quantity", 0) or 0),
            "avg_price": float(o.get("average_price", 0.0) or 0.0),
            "transaction_type": o.get("transaction_type"),
            "exchange": o.get("exchange"),
            "quantity": int(o.get("quantity", 0) or 0),
            "trigger_price": float(o.get("trigger_price", 0.0) or 0.0),
        } for o in raw]

    def find_fill(self, tradingsymbol: str, side: str = "SELL") -> dict | None:
        """Find today's REAL fill for `tradingsymbol`/`side` (e.g. the SELL that
        actually closed a long option) — used by reconcile_orphans (E0.1) so an
        external/reconciled close is booked at the true fill, not the last mark.
        Scans `kite.orders()` (today's order book) for the most-recent COMPLETE
        order matching both the symbol and transaction_type with a real fill;
        returns None if nothing matches. Defensive: a broker read failure here must
        never crash reconcile, so any exception is swallowed and treated as 'no
        fill found' (the caller falls back to the last mark)."""
        try:
            self._sync_token()
            candidates = [
                o for o in (self.kite.orders() or [])
                if o.get("tradingsymbol") == tradingsymbol
                and str(o.get("transaction_type", "")).upper() == side.upper()
                and str(o.get("status", "")).upper() == "COMPLETE"
                and int(o.get("filled_quantity", 0) or 0) > 0
            ]
            if not candidates:
                return None
            # kite.orders() is chronological; the most recent matching fill wins.
            last = candidates[-1]
            avg = float(last.get("average_price", 0.0) or 0.0)
            filled = int(last.get("filled_quantity", 0) or 0)
            if avg <= 0 or filled <= 0:
                return None
            return {"avg_price": avg, "filled_qty": filled}
        except Exception:
            return None
