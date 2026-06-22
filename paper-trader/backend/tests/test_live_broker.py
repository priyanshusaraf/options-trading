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
        self.log = []                        # ordered call log across orders + GTTs

    def place(self, req):
        self.placed.append(req)
        self._req = req
        self.log.append(("place", req.side))
        return "OID-1"

    def status(self, order_id):
        if self._seq is not None:
            st, fq = self._seq[min(self._seq_i, len(self._seq) - 1)]
            self._seq_i += 1
            return {"status": st, "filled_qty": fq,
                    "avg_price": self.fill_price, "reason": "x"}
        fq = self._req.qty if self._filled_qty is None else self._filled_qty
        return {"status": self._status, "filled_qty": fq,
                "avg_price": self.fill_price, "reason": "x"}

    def place_stop_gtt(self, tradingsymbol, exchange, qty, trigger_price, last_price):
        self.gtt_placed.append((tradingsymbol, trigger_price))
        self.log.append(("place_gtt", tradingsymbol))
        return "GTT-1"

    def modify_stop_gtt(self, trigger_id, tradingsymbol, exchange, qty, trigger_price, last_price):
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


def test_reconcile_orphan_books_closed_without_an_order():
    import datetime as dt
    c = FakeClient(fill_price=100.0)
    b = _broker(c)
    pos, q, chain = _open(b, c)
    pos.entry_time = b.provider.now() - dt.timedelta(minutes=5)   # older than the 60s grace
    b.commit()
    b.provider.account_positions = lambda: []                    # vanished from the account
    placed_before = len(c.placed)
    booked = b.reconcile_orphans(b.provider.now())
    assert "NIFTY" in booked
    assert b.position_for("NIFTY") is None                       # booked closed in the ledger
    assert len(c.placed) == placed_before                        # but NO sell order sent
    assert c.gtt_deleted == ["GTT-1"]                            # and its GTT cancelled
