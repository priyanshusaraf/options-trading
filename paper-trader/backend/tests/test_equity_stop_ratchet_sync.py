"""Fix C (2026-07-14): keep the exchange-side SL-M in sync with the ratcheted
internal stop.

2026-07-13 SUZLON: at 11:26 the lockstep ratcheted the stop 53.65 → 53.08, but the
exchange `modify_order` was REJECTED ("difference between limit and trigger price …
beyond the permissible range Rs. 1.59"). The old code only logged the error, so the
resting SL-M stayed at 53.65 while the bot's internal stop moved to 53.08 — a silent
divergence. On a rejected ratchet we now cancel + replace the resting SL-M so the
exchange backstop tracks the internal stop, and we skip the exchange modify entirely
when the stop is already crossing (it fires this tick — the modify would only draw the
same rejection).
"""
from tests.test_live_broker import FakeClient, _broker, _open_eq


class ModifyRejectClient(FakeClient):
    """SL-M `modify_stop_order` is rejected by the exchange (the SUZLON permissible-range
    error); `place_stop_order` returns distinct ids so a replacement is observable."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self._place_seq = 0

    def place_stop_order(self, tradingsymbol, exchange, qty, trigger_price, side="SELL", tag=None):
        self._place_seq += 1
        self.stop_orders.append((tradingsymbol, trigger_price, side, exchange))
        self.log.append(("place_stop", tradingsymbol))
        return f"SLM-{self._place_seq}"

    def modify_stop_order(self, order_id, trigger_price):
        self.stop_modified.append((order_id, trigger_price))
        self.log.append(("modify_stop", order_id))
        raise Exception("Difference between limit price and trigger price for SL orders "
                        "is beyond the exchange's permissible range of Rs. 1.59")


class CancelRejectClient(ModifyRejectClient):
    """As above, but the CANCEL is also refused — we must not place a second stop."""

    def cancel(self, order_id):
        self.log.append(("cancel", order_id))
        raise Exception("order cannot be cancelled")


def test_rejected_ratchet_cancels_and_replaces_the_sl_m():
    c = ModifyRejectClient(fill_price=53.12)
    b = _broker(c)
    pos = _open_eq(b, "SHORT", 53.12, 940)       # BUY SL-M above entry protects the short
    first_oid = pos.gtt_trigger_id
    assert first_oid == "SLM-1"
    pos.stop_price = 53.08                        # ratchet toward breakeven; modify will reject
    b.update_stop_protection(pos, 52.60)          # spot below the buy-stop → not firing yet
    # stale stop cancelled, fresh one placed at the new trigger — no divergence
    assert first_oid in c.cancelled
    assert len(c.stop_orders) == 2
    assert c.stop_orders[-1][:3] == (pos.tradingsymbol, 53.08, "BUY")
    assert pos.gtt_trigger_id == "SLM-2" and pos.gtt_trigger_id != first_oid


def test_ratchet_skipped_when_stop_already_crossed():
    c = ModifyRejectClient(fill_price=53.12)
    b = _broker(c)
    pos = _open_eq(b, "SHORT", 53.12, 940)
    c.stop_modified.clear(); c.cancelled.clear()
    pos.stop_price = 53.08
    b.update_stop_protection(pos, 53.20)          # spot already ABOVE the buy-stop → firing now
    assert c.stop_modified == [] and c.cancelled == []   # no invalid order sent


def test_cancel_refused_does_not_place_a_second_stop():
    c = CancelRejectClient(fill_price=53.12)
    b = _broker(c)
    pos = _open_eq(b, "SHORT", 53.12, 940)
    before = len(c.stop_orders)
    pos.stop_price = 53.08
    b.update_stop_protection(pos, 52.60)
    # cancel refused → leave the (still protective) stale stop, do NOT double-place
    assert len(c.stop_orders) == before
    assert pos.gtt_trigger_id == "SLM-1"          # unchanged; internal stop is authoritative
