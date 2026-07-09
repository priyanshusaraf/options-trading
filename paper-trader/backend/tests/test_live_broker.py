"""LiveBroker: real-order fills booked at the ACTUAL price, and the ownership
boundary — it will not close a position the live account doesn't back (your
position, a manual exit, a margin glitch). No real exchange: a fake order client
and a fake account-positions feed."""
from sqlalchemy import select

from app.core.instruments import get_instrument
from app.db.models import Trade
from app.db.session import init_db
from app.engine.execution_policy import OrderPlan
from app.engine.live_broker import LiveBroker
from app.providers.mock import MockProvider

MKT = OrderPlan("MARKET", None, "tight", 0.005)


class FakeClient:
    def __init__(self, fill_price=100.0, status="COMPLETE", filled_qty=None,
                 status_seq=None):
        self.fill_price = fill_price
        self._status = status
        self._filled_qty = filled_qty       # None -> the full requested qty filled
        self._seq = status_seq              # optional [(status, filled_qty), ...]
        self._seq_i = 0
        self.placed = []
        self._req = None
        self.gtt_placed = []
        self.gtt_modified = []
        self.gtt_deleted = []
        self.stop_orders = []                # (tradingsymbol, trigger, side, exchange) SL-M stops
        self.stop_modified = []              # (order_id, trigger) SL-M re-prices
        self.cancelled = []                  # order ids passed to cancel()
        self.log = []                        # ordered call log across orders + GTTs

    def place(self, req):
        self.placed.append(req)
        self._req = req
        self.log.append(("place", req.side))
        return "OID-1"

    def cancel(self, order_id):
        self.cancelled.append(order_id)
        self.log.append(("cancel", order_id))

    def status(self, order_id):
        if self._seq is not None:
            st, fq = self._seq[min(self._seq_i, len(self._seq) - 1)]
            self._seq_i += 1
            return {"status": st, "filled_qty": fq,
                    "avg_price": self.fill_price, "reason": "x"}
        fq = self._req.qty if self._filled_qty is None else self._filled_qty
        return {"status": self._status, "filled_qty": fq,
                "avg_price": self.fill_price, "reason": "x"}

    def place_stop_gtt(self, tradingsymbol, exchange, qty, trigger_price, last_price, side="SELL"):
        self.gtt_placed.append((tradingsymbol, trigger_price, side, exchange))
        self.log.append(("place_gtt", tradingsymbol))
        return "GTT-1"

    def place_stop_order(self, tradingsymbol, exchange, qty, trigger_price, side="SELL", tag=None):
        self.stop_orders.append((tradingsymbol, trigger_price, side, exchange))
        self.log.append(("place_stop", tradingsymbol))
        return "SLM-1"

    def modify_stop_order(self, order_id, trigger_price):
        self.stop_modified.append((order_id, trigger_price))
        self.log.append(("modify_stop", order_id))

    def modify_stop_gtt(self, trigger_id, tradingsymbol, exchange, qty, trigger_price, last_price, side="SELL"):
        self.gtt_modified.append((trigger_id, trigger_price))
        self.log.append(("modify_gtt", trigger_id))

    def delete_gtt(self, trigger_id):
        self.gtt_deleted.append(trigger_id)
        self.log.append(("delete_gtt", trigger_id))


def _broker(client, account=None):
    init_db(reset=True)
    prov = MockProvider()
    prov.account_positions = lambda: (account or [])
    return LiveBroker(prov, client, poll_seconds=0.0, timeout_seconds=0.0)


def _open(b, client):
    inst = get_instrument("NIFTY")
    chain = b.provider.get_option_chain(inst)
    q = min((x for x in chain.quotes if x.option_type == "CE"),
            key=lambda x: abs(x.strike - chain.spot))
    return b.open_position(inst, "LONG", q, "t", b.provider.now(), chain.spot,
                           params={}, plan=MKT), q, chain


def test_reconcile_books_equity_via_the_equity_path_not_options():
    """An orphaned intraday-equity position must be booked through the EQUITY close
    (margin-based, direction-aware) — not the options close, which mistook the
    released notional for profit (+₹40k on a ₹10k margin) and mislabeled it 'options'."""
    import datetime as dt
    from app.db.session import SessionLocal
    from app.engine.broker import PaperBroker
    c = FakeClient()
    b = _broker(c, account=[])      # account backs nothing -> every position is an orphan
    inst = get_instrument("NIFTY")
    # a pre-existing intraday-equity SHORT in the ledger (booked via PaperBroker)
    pos = PaperBroker.open_equity_position(b, inst, "SHORT", 100.0, 10, "NSE_INTRADAY",
                                           "t", b.provider.now(), params={})
    pos.entry_time = b.provider.now() - dt.timedelta(minutes=5)   # aged past the 60s guard
    pos.last_premium = 99.0          # short entered 100, now 99 -> a small real profit
    b.commit()
    # orphan_confirm_count defaults to 2 -> needs two consecutive orphaned reads
    b.reconcile_orphans(b.provider.now())
    b.reconcile_orphans(b.provider.now())
    with SessionLocal() as s:
        trades = list(s.scalars(select(Trade)))
    assert len(trades) == 1
    tr = trades[0]
    assert tr.exit_reason == "RECONCILED_EXTERNAL_EXIT"
    assert tr.segment == "equity_intraday"          # NOT mislabeled 'options'
    assert tr.gross_pnl == 10.0                      # (entry-exit)*qty for a short, NOT -10
    assert tr.net_pnl < 100.0                        # tiny real P&L, NOT ~+notional


# ── live MIS (intraday-equity) real order routing ────────────────────────────
def _open_eq(b, direction="LONG", price=100.0, qty=10):
    inst = get_instrument("NIFTY")   # the NSE_INTRADAY charge-segment forces the equity path
    return b.open_equity_position(inst, direction, price, qty, "NSE_INTRADAY",
                                  "t", b.provider.now(), params={})


def test_open_equity_long_places_a_mis_buy_and_books_the_fill():
    c = FakeClient(fill_price=100.0)
    b = _broker(c)
    pos = _open_eq(b, "LONG", 100.0, 10)
    assert pos is not None and pos.segment == "equity_intraday"
    req = c.placed[-1]
    assert req.side == "BUY" and req.product == "MIS" and req.exchange == "NSE"   # NSE_INTRADAY -> NSE
    assert pos.qty == 10 and pos.entry_premium == 100.0


def test_open_equity_short_places_a_mis_sell():
    c = FakeClient(fill_price=100.0)
    b = _broker(c)
    pos = _open_eq(b, "SHORT", 100.0, 10)
    assert pos is not None and pos.direction == "SHORT"
    assert c.placed[-1].side == "SELL" and c.placed[-1].product == "MIS"


# ── #7 GTT-orphan hardening: abort the close if the exchange GTT can't be cancelled ──
class FailCancelClient(FakeClient):
    def delete_gtt(self, trigger_id):
        raise RuntimeError("GTT cancel rejected by broker")


# ── #18: an intraday (MIS) protective stop is an SL-M order, not a GTT (GTT is not
# allowed for MIS). Cancelling it that fails must ABORT the close, same as #7. ──
class FailStopCancelClient(FakeClient):
    def cancel(self, order_id):
        raise RuntimeError("SL-M cancel rejected by broker")


def test_cancel_gtt_returns_true_on_success_or_noop():
    b = _broker(FakeClient())
    assert b._cancel_gtt("GTT-9", "NIFTY") is True
    assert b._cancel_gtt(None, "NIFTY") is True           # nothing to cancel -> ok


def test_cancel_gtt_returns_false_on_failure():
    b = _broker(FailCancelClient())
    assert b._cancel_gtt("GTT-9", "NIFTY") is False


def test_equity_close_aborts_when_stop_cancel_fails():
    from sqlalchemy import select as _select

    from app.db.models import Trade as _Trade
    from app.db.session import SessionLocal
    c = FailStopCancelClient(fill_price=100.0)
    b = _broker(c, account=[{"tradingsymbol": "NIFTY", "quantity": 10}])  # account backs the long
    pos = _open_eq(b, "LONG", 100.0, 10)
    assert pos.gtt_trigger_id is not None                 # SL-M order id stored
    placed_before = len(c.placed)
    res = b.close_equity_position(pos, 101.0, "STOP_LOSS", b.provider.now())
    assert res is None                                    # close ABORTED — SL-M still resting
    assert len(c.placed) == placed_before                 # NO closing order was sent
    with SessionLocal() as s:
        assert list(s.scalars(_select(_Trade))) == []     # nothing booked closed


# ── #3 keep-both-stops, fix the race: the broker GTT and the bot SL can't BOTH fill ──
def test_close_aborts_if_position_vanished_mid_close_no_double_fill():
    """If the position disappears from the account between the ownership check and the
    send (its GTT fired, or the owner exited) the bot sends NO closing order — so the
    GTT and the bot can never both fill (oversell / reversed position). The orphan
    reconciler books it instead. This is what makes 'keep both stops' safe."""
    from sqlalchemy import select as _sel

    from app.db.models import Trade as _Tr
    from app.db.session import SessionLocal
    c = FakeClient(fill_price=100.0)            # GTT cancel SUCCEEDS here; the race is at the re-check
    b = _broker(c)
    pos = _open_eq(b, "LONG", 100.0, 10)
    placed_after_open = len(c.placed)
    # account backs the long at the FIRST check, then reads flat at the RE-check (GTT fired)
    state = {"n": 0}

    def acct():
        state["n"] += 1
        return [{"tradingsymbol": "NIFTY", "quantity": 10}] if state["n"] == 1 else []
    b.provider.account_positions = acct
    res = b.close_equity_position(pos, 101.0, "STOP_LOSS", b.provider.now())
    assert res is None                                    # aborted at the GTT-fired re-check
    assert len(c.placed) == placed_after_open             # NO second order — no double-fill
    with SessionLocal() as s:
        assert list(s.scalars(_sel(_Tr))) == []           # not booked by us; reconciler will


def test_open_equity_short_places_a_buy_sl_m_above_entry():
    # MIS short: protective SL-M BUY (cover) resting ABOVE entry — NOT a GTT (GTT is
    # rejected for MIS; the mock used to hide that).
    c = FakeClient(fill_price=100.0)
    b = _broker(c)
    pos = _open_eq(b, "SHORT", 100.0, 10)
    assert c.gtt_placed == []                   # no GTT on the MIS path
    sym, trig, side, exch = c.stop_orders[-1]
    assert side == "BUY" and trig > 100.0 and exch == "NSE"
    assert pos.gtt_trigger_id == "SLM-1"         # the resting SL-M order id


def test_open_equity_long_places_a_sell_sl_m_below_entry():
    c = FakeClient(fill_price=100.0)
    b = _broker(c)
    pos = _open_eq(b, "LONG", 100.0, 10)
    assert c.gtt_placed == []
    sym, trig, side, exch = c.stop_orders[-1]
    assert side == "SELL" and trig < 100.0
    assert pos.gtt_trigger_id == "SLM-1"


def test_equity_close_cancels_the_sl_m_before_selling():
    # cancel-then-sell: the resting SL-M must be pulled BEFORE the market close, or a
    # gap could fire both (oversell / reversed position) — same guarantee as the GTT path.
    c = FakeClient(fill_price=100.0)
    b = _broker(c)
    pos = _open_eq(b, "LONG", 100.0, 10)
    b.provider.account_positions = lambda: [{"tradingsymbol": pos.tradingsymbol, "quantity": 10}]
    c.log.clear()
    b.close_equity_position(pos, 101.0, "MANUAL_CLOSE", b.provider.now())
    cancel_i = c.log.index(("cancel", "SLM-1"))
    sell_i = c.log.index(("place", "SELL"))
    assert cancel_i < sell_i                     # backstop pulled BEFORE the sell


def test_equity_trail_reprices_the_sl_m():
    # ratcheting the software stop must re-price the resting SL-M so the backstop follows.
    c = FakeClient(fill_price=100.0)
    b = _broker(c)
    pos = _open_eq(b, "LONG", 100.0, 10)
    pos.stop_price = 98.5
    b.update_stop_protection(pos, 103.0)
    assert c.stop_modified and c.stop_modified[-1] == ("SLM-1", 98.5)
    assert c.gtt_modified == []                   # not a GTT


def test_reconciled_equity_orphan_cancels_its_sl_m():
    import datetime as dt
    c = FakeClient(fill_price=100.0)
    b = _broker(c, account=[])                    # nothing backs it -> orphan
    pos = _open_eq(b, "LONG", 100.0, 10)
    pos.entry_time = b.provider.now() - dt.timedelta(minutes=5)   # aged past the 60s grace
    b.commit()
    need = b.settings.orphan_confirm_count
    for _ in range(need):
        b.reconcile_orphans(b.provider.now())
    assert c.cancelled == ["SLM-1"]               # the resting SL-M was pulled, no GTT delete
    assert c.gtt_deleted == []


def test_close_equity_long_sells_when_account_backs_it():
    c = FakeClient(fill_price=100.0)
    b = _broker(c)
    pos = _open_eq(b, "LONG", 100.0, 10)
    b.provider.account_positions = lambda: [{"tradingsymbol": pos.tradingsymbol, "quantity": 10}]
    tr = b.close_equity_position(pos, 101.0, "MANUAL_CLOSE", b.provider.now())
    assert tr is not None and c.placed[-1].side == "SELL" and c.placed[-1].product == "MIS"


def test_close_equity_short_buys_to_cover_when_account_is_short():
    c = FakeClient(fill_price=100.0)
    b = _broker(c)
    pos = _open_eq(b, "SHORT", 100.0, 10)
    b.provider.account_positions = lambda: [{"tradingsymbol": pos.tradingsymbol, "quantity": -10}]  # account is short
    tr = b.close_equity_position(pos, 99.0, "MANUAL_CLOSE", b.provider.now())
    assert tr is not None and c.placed[-1].side == "BUY"


def test_close_equity_short_blocked_when_account_is_not_short():
    c = FakeClient(fill_price=100.0)
    b = _broker(c)
    pos = _open_eq(b, "SHORT", 100.0, 10)
    b.provider.account_positions = lambda: []   # account holds 0 -> not backed
    before = len(c.placed)
    tr = b.close_equity_position(pos, 99.0, "MANUAL_CLOSE", b.provider.now())
    assert tr is None and len(c.placed) == before   # no cover order sent


def test_open_books_the_actual_fill_price():
    c = FakeClient(fill_price=123.45)
    b = _broker(c)
    pos, q, _ = _open(b, c)
    assert pos is not None
    assert pos.entry_premium == 123.45            # real fill, not the snapshot ltp
    assert c.placed[0].side == "BUY" and c.placed[0].order_type == "MARKET"


def test_open_returns_none_and_records_nothing_when_not_filled():
    c = FakeClient(status="REJECTED")
    b = _broker(c)
    pos, _, _ = _open(b, c)
    assert pos is None
    assert len(b.open_positions()) == 0


def test_close_blocked_when_account_does_not_back_the_position():
    c = FakeClient(fill_price=100.0)
    b = _broker(c, account=[])                     # the account holds nothing
    pos, q, chain = _open(b, c)
    assert pos is not None
    res = b.close_position(pos, 90.0, "STOP_LOSS", b.provider.now(), chain.spot)
    assert res is None                             # NO sell order sent
    assert b.position_for("NIFTY") is not None     # position protected, still held


def test_close_sells_when_account_backs_the_position():
    c = FakeClient(fill_price=100.0)
    b = _broker(c)
    pos, q, chain = _open(b, c)
    b.provider.account_positions = lambda: [{"tradingsymbol": pos.tradingsymbol,
                                             "quantity": pos.qty}]
    c.fill_price = 140.0
    tr = b.close_position(pos, 140.0, "TARGET", b.provider.now(), chain.spot)
    assert tr is not None
    assert b.position_for("NIFTY") is None
    assert c.placed[-1].side == "SELL" and tr.exit_premium == 140.0


# ── GTT safety-net stop ──────────────────────────────────────────────────────
def test_open_places_a_gtt_backstop():
    c = FakeClient(fill_price=100.0)
    b = _broker(c)
    pos, q, _ = _open(b, c)
    assert pos.gtt_trigger_id == "GTT-1"
    assert c.gtt_placed and c.gtt_placed[0][0] == pos.tradingsymbol


def test_trail_modifies_the_gtt():
    c = FakeClient(fill_price=100.0)
    b = _broker(c)
    pos, q, _ = _open(b, c)
    pos.stop_price = 95.0
    b.update_stop_protection(pos, 130.0)
    assert c.gtt_modified and c.gtt_modified[0] == ("GTT-1", 95.0)


# ── 2026-07-08 LODHA incident: the initial SL-M placement failed (tick-size reject)
# and gtt_trigger_id stayed None forever — every later ratchet tick silently did
# nothing, so the position ran naked at the broker for its whole life. A ratchet (or
# any per-tick check) must instead PLACE a fresh backstop when none is resting. ─────
def test_update_stop_protection_places_a_fresh_sl_m_if_none_was_resting():
    c = FakeClient(fill_price=100.0)
    b = _broker(c)
    pos = _open_eq(b, "LONG", 100.0, 10)
    pos.gtt_trigger_id = None            # simulate the initial SL-M placement having failed
    c.stop_orders.clear()
    pos.stop_price = 97.0
    b.update_stop_protection(pos, 103.0)
    assert c.stop_modified == []                              # nothing was resting to MODIFY
    assert c.stop_orders and c.stop_orders[-1][:3] == (pos.tradingsymbol, 97.0, "SELL")
    assert pos.gtt_trigger_id == "SLM-1"                       # now actually resting


def test_update_stop_protection_places_a_fresh_gtt_if_none_was_resting():
    c = FakeClient(fill_price=100.0)
    b = _broker(c)
    pos, q, _ = _open(b, c)
    pos.gtt_trigger_id = None            # simulate the initial GTT placement having failed
    c.gtt_placed.clear()
    pos.stop_price = 90.0
    b.update_stop_protection(pos, 110.0)
    assert c.gtt_modified == []                                # nothing was resting to MODIFY
    assert c.gtt_placed and c.gtt_placed[-1][0] == pos.tradingsymbol
    assert pos.gtt_trigger_id == "GTT-1"


# ── ensure_stop_protection: the cheap per-tick self-healing check, called every risk-
# loop tick regardless of whether the ratchet moved this tick (so a naked position that
# never ratchets — flat or underwater all day — still gets retried, not just one that
# happens to move into profit). ──────────────────────────────────────────────────────
def test_ensure_stop_protection_is_a_noop_when_a_stop_already_rests():
    c = FakeClient(fill_price=100.0)
    b = _broker(c)
    pos = _open_eq(b, "LONG", 100.0, 10)
    assert pos.gtt_trigger_id == "SLM-1"
    c.log.clear()
    b.ensure_stop_protection(pos, 101.0)
    assert c.log == []                   # single attribute check — no broker call at all


def test_ensure_stop_protection_places_a_fresh_stop_when_missing():
    c = FakeClient(fill_price=100.0)
    b = _broker(c)
    pos = _open_eq(b, "LONG", 100.0, 10)
    pos.gtt_trigger_id = None
    c.stop_orders.clear()
    b.ensure_stop_protection(pos, 101.0)
    assert c.stop_orders and pos.gtt_trigger_id == "SLM-1"


def test_self_close_cancels_the_gtt():
    c = FakeClient(fill_price=100.0)
    b = _broker(c)
    pos, q, chain = _open(b, c)
    b.provider.account_positions = lambda: [{"tradingsymbol": pos.tradingsymbol,
                                             "quantity": pos.qty}]
    b.close_position(pos, 140.0, "TARGET", b.provider.now(), chain.spot)
    assert c.gtt_deleted == ["GTT-1"]      # backstop removed when the bot exits itself


# ── L1: a partial / late BUY fill is ADOPTED, never dropped ──────────────────
def test_partial_open_books_the_actual_filled_qty_and_protects_it():
    # A market BUY of one lot fills only part (the rest cancels). The bot must book
    # the REAL filled qty at the REAL price AND place its GTT — never return None and
    # leave a real, stopless position untracked.
    c = FakeClient(fill_price=120.0, status="CANCELLED", filled_qty=25)
    b = _broker(c)
    pos, q, _ = _open(b, c)
    assert pos is not None
    assert pos.qty == 25                      # the ACTUAL fill, not the full lot
    assert pos.lot_size == q.lot_size         # true lot size preserved for display
    assert pos.entry_premium == 120.0         # real avg fill price
    assert pos.gtt_trigger_id == "GTT-1"      # the partial is protected


def test_timeout_open_adopts_a_late_fill_via_requery():
    # The poll times out reporting nothing, but the order actually filled at the
    # buzzer. A re-query of the order finds the fill — adopt it.
    from app.engine.order_executor import OrderResult
    c = FakeClient(fill_price=130.0, status="COMPLETE", filled_qty=50)
    b = _broker(c)
    filled, avg = b._actual_fill(OrderResult("TIMEOUT", "OID-1", 0, 0.0, "no fill"))
    assert filled == 50 and avg == 130.0


def test_timeout_open_with_no_real_fill_records_nothing():
    from app.engine.order_executor import OrderResult
    c = FakeClient(status="OPEN", filled_qty=0)
    b = _broker(c)
    filled, avg = b._actual_fill(OrderResult("TIMEOUT", "OID-1", 0, 0.0, "no fill"))
    assert filled == 0


# ── L2: a partial / late SELL never oversells; the ledger tracks reality ─────
def _back_full(b, pos):
    b.provider.account_positions = lambda: [{"tradingsymbol": pos.tradingsymbol,
                                             "quantity": pos.qty}]


def test_partial_close_books_the_sold_portion_and_keeps_the_remainder():
    c = FakeClient(fill_price=100.0)
    b = _broker(c)
    pos, q, chain = _open(b, c)
    full_qty = pos.qty
    _back_full(b, pos)
    c._status, c.fill_price, c._filled_qty = "CANCELLED", 140.0, 30  # SELL only part-fills
    res = b.close_position(pos, 140.0, "TARGET", b.provider.now(), chain.spot)
    assert res is None                                   # NOT a full close
    pos2 = b.position_for("NIFTY")
    assert pos2 is not None and pos2.qty == full_qty - 30  # remainder still held
    assert pos2.gtt_trigger_id == "GTT-1"                # remainder re-protected
    assert b.reconcile()["diff"] == 0.0                  # cash ledger invariant intact
    trades = list(b.s.scalars(select(Trade)))
    assert len(trades) == 1 and trades[0].qty == 30      # only the sold portion realized


def test_partial_close_realizes_the_correct_pnl_on_the_sold_portion():
    # Direct check of the partial-close booking math (PaperBroker.book_partial_close).
    c = FakeClient(fill_price=100.0)
    b = _broker(c)
    pos, q, chain = _open(b, c)
    entry = pos.entry_premium
    realized0 = b.capital().realized_pnl
    sell_qty, sell_px = 30, entry * 1.5
    b.book_partial_close(pos, sell_qty, sell_px, "TARGET", b.provider.now(), chain.spot)
    tr = b.s.scalars(select(Trade)).first()
    assert tr.qty == sell_qty
    assert abs(tr.gross_pnl - (sell_px - entry) * sell_qty) < 1e-6
    assert b.capital().realized_pnl == realized0 + tr.net_pnl
    assert b.reconcile()["diff"] == 0.0


def test_timeout_close_with_a_late_full_fill_books_closed():
    # The SELL poll times out reporting nothing, but the order actually filled — a
    # re-query catches it and books the close, so the next tick can't re-send and
    # oversell into the owner's account.
    c = FakeClient(fill_price=100.0)
    b = _broker(c)
    pos, q, chain = _open(b, c)               # opens cleanly (COMPLETE)
    _back_full(b, pos)
    full_qty = pos.qty
    # now make the SELL time out, then show fully filled on the re-query
    c._seq = [("OPEN", 0), ("COMPLETE", full_qty)]
    c._seq_i = 0
    c.fill_price = 138.0
    b.poll_seconds = 0.001                     # one poll, then timeout
    res = b.close_position(pos, 138.0, "TARGET", b.provider.now(), chain.spot)
    assert res is not None and res.exit_premium == 138.0
    assert b.position_for("NIFTY") is None


# ── L6: GTT-vs-bot double-sell race ──────────────────────────────────────────
def test_close_cancels_the_gtt_before_sending_the_sell():
    c = FakeClient(fill_price=100.0)
    b = _broker(c)
    pos, q, chain = _open(b, c)
    b.provider.account_positions = lambda: [{"tradingsymbol": pos.tradingsymbol,
                                             "quantity": pos.qty}]
    c.log.clear()
    b.close_position(pos, 140.0, "TARGET", b.provider.now(), chain.spot)
    del_i = c.log.index(("delete_gtt", "GTT-1"))
    sell_i = c.log.index(("place", "SELL"))
    assert del_i < sell_i      # backstop gone BEFORE we sell — no double-sell window


def test_close_aborts_without_selling_if_gtt_fired_mid_close():
    c = FakeClient(fill_price=100.0)
    b = _broker(c)
    pos, q, chain = _open(b, c)
    calls = {"n": 0}

    def acct():
        calls["n"] += 1
        # backs the position at the top check, vanished by the pre-send re-check
        # (the GTT just fired) -> the bot must NOT also send a SELL.
        return ([{"tradingsymbol": pos.tradingsymbol, "quantity": pos.qty}]
                if calls["n"] == 1 else [])

    b.provider.account_positions = acct
    sells_before = sum(1 for r in c.placed if r.side == "SELL")
    res = b.close_position(pos, 90.0, "STOP_LOSS", b.provider.now(), chain.spot)
    assert res is None
    assert sum(1 for r in c.placed if r.side == "SELL") == sells_before  # no SELL


def test_aborted_close_restores_the_gtt_backstop():
    # If the pre-send re-check fails on a TRANSIENT account-feed glitch (not a real
    # GTT fire), the still-real position must not be left without the backstop we
    # cancelled — restore it.
    c = FakeClient(fill_price=100.0)
    b = _broker(c)
    pos, q, chain = _open(b, c)
    calls = {"n": 0}

    def acct():
        calls["n"] += 1
        return ([{"tradingsymbol": pos.tradingsymbol, "quantity": pos.qty}]
                if calls["n"] == 1 else [])      # backs at top check, glitches at re-check

    b.provider.account_positions = acct
    placed_before = len(c.gtt_placed)
    res = b.close_position(pos, 90.0, "STOP_LOSS", b.provider.now(), chain.spot)
    assert res is None
    assert b.position_for("NIFTY") is not None
    assert len(c.gtt_placed) == placed_before + 1   # backstop restored after the abort
    assert pos.gtt_trigger_id == "GTT-1"


def test_failed_close_replaces_the_gtt_so_the_position_stays_protected():
    c = FakeClient(fill_price=100.0)
    b = _broker(c)
    pos, q, chain = _open(b, c)
    b.provider.account_positions = lambda: [{"tradingsymbol": pos.tradingsymbol,
                                             "quantity": pos.qty}]
    c._status = "REJECTED"                   # the closing SELL will not fill
    placed_before = len(c.gtt_placed)
    res = b.close_position(pos, 90.0, "STOP_LOSS", b.provider.now(), chain.spot)
    assert res is None
    assert b.position_for("NIFTY") is not None
    assert len(c.gtt_placed) == placed_before + 1   # backstop restored after the cancel
    assert pos.gtt_trigger_id == "GTT-1"


# ── L11: a failed alert must be logged, never silently swallowed ─────────────
def test_notify_logs_when_the_notifier_raises():
    from app.core.logging import log

    class BoomNotifier:
        def _emit(self, text):
            raise RuntimeError("telegram down")

    c = FakeClient()
    b = _broker(c)
    b.notifier = BoomNotifier()
    b._notify("CRITICAL: GTT NOT placed")          # must not propagate
    errs = [e for e in log.recent(50) if e.get("event") == "NOTIFY_FAIL"]
    assert errs and "CRITICAL: GTT NOT placed" in errs[-1]["msg"]


# ── outstanding-order tracking: never two working bot orders on one contract ──
def test_ensure_no_inflight_proceeds_when_there_is_no_prior_order():
    c = FakeClient()
    b = _broker(c)
    assert b._ensure_no_inflight("SYM") is True


def test_ensure_no_inflight_cancels_a_still_working_prior_order():
    # A prior order recorded as in-flight is still OPEN at the exchange -> cancel it
    # and confirm before allowing a new order, so the contract never has two live orders.
    c = FakeClient(status="OPEN", filled_qty=0)
    b = _broker(c)
    b._inflight["SYM"] = "OID-7"
    assert b._ensure_no_inflight("SYM") is True
    assert c.cancelled == ["OID-7"]
    assert "SYM" not in b._inflight                 # cleared


def test_ensure_no_inflight_aborts_if_the_prior_order_already_filled():
    # The in-flight order actually FILLED since we recorded it. Placing another would
    # double up (a second BUY, or an oversell on SELL) -> abort and surface instead.
    c = FakeClient(status="COMPLETE", filled_qty=50)
    b = _broker(c)
    b._inflight["SYM"] = "OID-7"
    assert b._ensure_no_inflight("SYM") is False
    assert c.cancelled == []                        # nothing to cancel; it's done
    assert "SYM" not in b._inflight


def test_ensure_no_inflight_aborts_when_a_stuck_order_cannot_be_cancelled():
    # If we can't kill the working order, do NOT place a new one (avoid a double fill).
    class Stuck(FakeClient):
        def cancel(self, order_id):
            raise RuntimeError("cancel failed")
    c = Stuck(status="OPEN", filled_qty=0)
    b = _broker(c)
    b._inflight["SYM"] = "OID-7"
    assert b._ensure_no_inflight("SYM") is False


def test_timed_out_open_records_the_order_inflight():
    # A BUY that times out with no fill may still be working at the exchange — record
    # it so the next attempt cancels it first (never a silent second BUY).
    c = FakeClient(status="OPEN", filled_qty=0)
    b = _broker(c)
    b.poll_seconds = 0.001
    pos, q, _ = _open(b, c)
    assert pos is None
    assert b._inflight.get(q.tradingsymbol) == "OID-1"


def test_status_poll_error_during_close_also_records_inflight():
    # A status poll that ERRORS mid-flight leaves an order that may still be working at
    # the exchange — track it too, so the next tick cancels it before re-sending.
    c = FakeClient(fill_price=100.0)
    b = _broker(c)
    pos, q, chain = _open(b, c)
    _back_full(b, pos)

    def boom(order_id):
        raise RuntimeError("network blip")

    c.status = boom
    res = b.close_position(pos, 90.0, "STOP_LOSS", b.provider.now(), chain.spot)
    assert res is None
    assert b._inflight.get(pos.tradingsymbol) == "OID-1"


def test_timed_out_sell_is_cancelled_before_the_next_sell_is_sent():
    c = FakeClient(fill_price=100.0)                 # clean COMPLETE open
    b = _broker(c)
    pos, q, chain = _open(b, c)
    _back_full(b, pos)
    b.poll_seconds = 0.001
    c._status, c._filled_qty = "OPEN", 0            # the SELL never fills -> TIMEOUT still-working
    r1 = b.close_position(pos, 90.0, "STOP_LOSS", b.provider.now(), chain.spot)
    assert r1 is None
    assert b._inflight.get(pos.tradingsymbol) == "OID-1"
    c.log.clear()
    b.close_position(pos, 90.0, "STOP_LOSS", b.provider.now(), chain.spot)
    assert ("cancel", "OID-1") in c.log
    assert c.log.index(("cancel", "OID-1")) < c.log.index(("place", "SELL"))


# ── #17: a bot entry that fills AFTER the poll window is ADOPTED, never orphaned ──
# (the BSE 2026-07-03 incident: the entry filled just after the open, outside the 30s
#  confirm window → an untracked, stopless position invisible to the engine.)
def test_timed_out_equity_entry_records_a_pending_entry():
    c = FakeClient(status="OPEN", filled_qty=0)   # entry never confirms within the window
    b = _broker(c)
    b.poll_seconds = 0.001
    pos = _open_eq(b, "LONG", 100.0, 13)
    assert pos is None                             # nothing booked at entry time
    assert len(b._pending_entries) == 1            # ...but tracked (by tradingsymbol) for adoption


def test_late_filled_entry_is_adopted_with_a_stop():
    c = FakeClient(status="OPEN", filled_qty=0)
    b = _broker(c)
    b.poll_seconds = 0.001
    assert _open_eq(b, "LONG", 100.0, 13) is None  # timed out, no fill yet
    assert b.position_for("NIFTY") is None
    c._status, c._filled_qty, c.fill_price = "COMPLETE", 13, 100.0   # it fills later
    adopted = b.adopt_pending_entries(b.provider.now())
    assert "NIFTY" in adopted
    p = b.position_for("NIFTY")
    assert p is not None and p.qty == 13 and p.entry_premium == 100.0
    assert p.gtt_trigger_id == "SLM-1"             # adopted WITH a protective SL-M stop
    assert "NIFTY" not in b._pending_entries        # cleared once adopted


def test_dead_pending_entry_is_dropped_without_adoption():
    c = FakeClient(status="OPEN", filled_qty=0)
    b = _broker(c)
    b.poll_seconds = 0.001
    _open_eq(b, "LONG", 100.0, 13)
    c._status, c._filled_qty = "REJECTED", 0       # the order died with no fill
    assert b.adopt_pending_entries(b.provider.now()) == []
    assert b.position_for("NIFTY") is None
    assert "NIFTY" not in b._pending_entries        # nothing to adopt → dropped


def test_still_working_pending_entry_is_retained():
    c = FakeClient(status="OPEN", filled_qty=0)
    b = _broker(c)
    b.poll_seconds = 0.001
    _open_eq(b, "LONG", 100.0, 13)
    assert b.adopt_pending_entries(b.provider.now()) == []   # still OPEN, unfilled
    assert len(b._pending_entries) == 1             # kept — it may still fill


def test_adoption_does_not_double_book_an_existing_position():
    c = FakeClient(status="OPEN", filled_qty=0)
    b = _broker(c)
    b.poll_seconds = 0.001
    _open_eq(b, "LONG", 100.0, 13)
    # a position for the key already exists (e.g. adopted on a prior pass / re-entered)
    b.provider.account_positions = lambda: []
    existing = super(LiveBroker, b).open_equity_position(
        get_instrument("NIFTY"), "LONG", 100.0, 13, "NSE_INTRADAY", "t", b.provider.now(), params={})
    c._status, c._filled_qty, c.fill_price = "COMPLETE", 13, 100.0
    b.adopt_pending_entries(b.provider.now())
    assert len([p for p in b.open_positions() if p.instrument_key == "NIFTY"]) == 1  # no duplicate


def _reinforce_params():
    return {
        "reinforce_enabled": True, "reinforce_min_profit_pct": 0.10,
        "reinforce_lock_pct": 0.05, "reinforce_extend_tp": True,
        "reinforce_tp_extend_pct": 0.20, "reinforce_tp_max_pct": 1.50,
        "reinforce_cooldown_minutes": 15.0, "max_reinforcements": 3,
    }


def test_reinforcement_resyncs_the_exchange_gtt():
    # L3: a reinforcement ratchets the stop up — the exchange GTT must follow, or the
    # server-side backstop still protects at the looser pre-reinforcement stop.
    c = FakeClient(fill_price=100.0)
    b = _broker(c)
    pos, q, chain = _open(b, c)
    b.mark(pos, premium=130.0, spot=chain.spot, now=b.provider.now())  # +30% -> reinforces
    b.commit()
    r = b.reinforce_position(pos, _reinforce_params(), b.provider.now())
    assert r["applied"] is True
    assert c.gtt_modified and c.gtt_modified[-1] == ("GTT-1", pos.stop_price)


def test_skipped_reinforcement_does_not_touch_the_gtt():
    # No applicable reinforcement (not profitable enough) -> no GTT churn.
    c = FakeClient(fill_price=100.0)
    b = _broker(c)
    pos, q, chain = _open(b, c)
    r = b.reinforce_position(pos, _reinforce_params(), b.provider.now())
    assert r["applied"] is False
    assert c.gtt_modified == []


def _age_out(b, pos):
    import datetime as dt
    pos.entry_time = b.provider.now() - dt.timedelta(minutes=5)   # older than the 60s grace
    b.commit()


def test_a_single_orphan_read_does_not_book_closed():
    # L8: one positions() read showing the position gone could be a transient feed
    # glitch — it must NOT book a phantom close on its own.
    c = FakeClient(fill_price=100.0)
    b = _broker(c)
    pos, q, chain = _open(b, c)
    _age_out(b, pos)
    b.provider.account_positions = lambda: []                    # vanished — but only once seen
    booked = b.reconcile_orphans(b.provider.now())
    assert booked == []
    assert b.position_for("NIFTY") is not None                   # still held — not booked yet
    assert c.gtt_deleted == []                                   # GTT left intact


def test_orphan_books_closed_only_after_consecutive_confirmations():
    c = FakeClient(fill_price=100.0)
    b = _broker(c)
    need = b.settings.orphan_confirm_count
    assert need >= 2
    pos, q, chain = _open(b, c)
    _age_out(b, pos)
    b.provider.account_positions = lambda: []                    # vanished from the account
    placed_before = len(c.placed)
    for _ in range(need - 1):
        assert b.reconcile_orphans(b.provider.now()) == []       # not yet confirmed
        assert b.position_for("NIFTY") is not None
    booked = b.reconcile_orphans(b.provider.now())               # Nth consecutive read
    assert "NIFTY" in booked
    assert b.position_for("NIFTY") is None                       # booked closed in the ledger
    assert len(c.placed) == placed_before                        # but NO sell order sent
    assert c.gtt_deleted == ["GTT-1"]                            # and its GTT cancelled


def test_a_backed_read_resets_the_orphan_confirmation_counter():
    # An intervening read where the account DOES back the position resets the streak,
    # so a single later glitch still can't book it.
    c = FakeClient(fill_price=100.0)
    b = _broker(c)
    pos, q, chain = _open(b, c)
    _age_out(b, pos)
    backed = [{"tradingsymbol": pos.tradingsymbol, "quantity": pos.qty}]
    feed = {"acct": []}
    b.provider.account_positions = lambda: feed["acct"]
    b.reconcile_orphans(b.provider.now())                        # streak = 1 (orphaned)
    feed["acct"] = backed
    b.reconcile_orphans(b.provider.now())                        # backed -> streak reset
    feed["acct"] = []
    booked = b.reconcile_orphans(b.provider.now())              # orphaned again, streak = 1
    assert booked == []
    assert b.position_for("NIFTY") is not None                  # not booked — streak was reset


def test_failed_account_read_never_phantom_closes():
    # audit C4: account_positions() returns None on API/auth failure (e.g. the daily
    # ~06:00 IST token expiry). A None read must NEVER be treated as a flat account —
    # no matter how many consecutive times it fails, the real held position is not booked.
    c = FakeClient(fill_price=100.0)
    b = _broker(c)
    pos, q, chain = _open(b, c)
    _age_out(b, pos)
    b.provider.account_positions = lambda: None                  # read failed (dead token)
    for _ in range(5):                                           # far past orphan_confirm_count
        assert b.reconcile_orphans(b.provider.now()) == []
    assert b.position_for("NIFTY") is not None                   # still held — NOT phantom-closed
    assert c.gtt_deleted == []                                   # GTT left intact


# ── C3: an OPTIONS entry that fills after the poll window must be adopted too ──
# (#17 fixed this for equity_intraday only; options — the default segment — was left
#  recording just _inflight, so a late-filled option became an invisible, stopless
#  position the engine never adopted.)
def test_timed_out_options_entry_records_a_pending_entry():
    c = FakeClient(status="OPEN", filled_qty=0)     # entry never confirms within the window
    b = _broker(c)
    b.poll_seconds = 0.001
    pos, q, chain = _open(b, c)
    assert pos is None                              # nothing booked at entry time
    assert q.tradingsymbol in b._pending_entries    # ...but tracked for adoption (C3)


def test_late_filled_options_entry_is_adopted_with_a_gtt():
    c = FakeClient(status="OPEN", filled_qty=0)
    b = _broker(c)
    b.poll_seconds = 0.001
    pos, q, chain = _open(b, c)
    assert pos is None and b.position_for("NIFTY") is None
    c._status, c._filled_qty, c.fill_price = "COMPLETE", q.lot_size, 100.0   # it fills later
    adopted = b.adopt_pending_entries(b.provider.now())
    assert "NIFTY" in adopted
    p = b.position_for("NIFTY")
    assert p is not None and p.gtt_trigger_id == "GTT-1"    # adopted WITH a GTT backstop
    assert q.tradingsymbol not in b._pending_entries        # cleared once adopted


def test_dead_pending_options_entry_is_dropped_without_adoption():
    c = FakeClient(status="OPEN", filled_qty=0)
    b = _broker(c)
    b.poll_seconds = 0.001
    pos, q, chain = _open(b, c)
    c._status, c._filled_qty = "REJECTED", 0        # order died with no fill
    assert b.adopt_pending_entries(b.provider.now()) == []
    assert b.position_for("NIFTY") is None
    assert q.tradingsymbol not in b._pending_entries
