"""E3 — keep the exchange-side options GTT in sync with the ratcheted internal stop.

The SUZLON divergence class, fixed for equity SL-M (Fix C, 2026-07-14) but still live
on the OPTIONS GTT path — which is the default segment. `update_stop_protection` only
logged a rejected `modify_stop_gtt`, and `pos.gtt_trigger_id` stayed non-None, so
`ensure_stop_protection`'s self-heal (which only fires when the id is None) never
retried. The exchange GTT sat at the old, looser trigger while the internal stop had
ratcheted up — and it bites precisely when the GTT is the only thing left protecting
the position (bot down, or the risk loop stalled).
"""
from tests.test_live_broker import FakeClient, _broker, _open


class GttModifyRejectClient(FakeClient):
    """`modify_stop_gtt` is refused; `place_stop_gtt` returns distinct ids so a
    replacement is observable."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self._gtt_seq = 0

    def place_stop_gtt(self, tradingsymbol, exchange, qty, trigger_price, last_price, side="SELL"):
        self._gtt_seq += 1
        self.gtt_placed.append((tradingsymbol, trigger_price, side, exchange))
        self.log.append(("place_gtt", tradingsymbol))
        return f"GTT-{self._gtt_seq}"

    def modify_stop_gtt(self, trigger_id, tradingsymbol, exchange, qty, trigger_price,
                        last_price, side="SELL"):
        self.gtt_modified.append((trigger_id, trigger_price))
        self.log.append(("modify_gtt", trigger_id))
        raise Exception("gtt modify rejected by the exchange")


class GttCancelRejectClient(GttModifyRejectClient):
    """As above, but the GTT delete is also refused — we must not leave two live."""

    def delete_gtt(self, trigger_id):
        self.log.append(("delete_gtt", trigger_id))
        raise Exception("gtt cannot be deleted")


def test_rejected_gtt_ratchet_cancels_and_replaces_the_gtt():
    c = GttModifyRejectClient()
    b = _broker(c)
    pos, q, chain = _open(b, c)
    first = pos.gtt_trigger_id
    assert first == "GTT-1"

    pos.stop_price = pos.entry_premium * 1.10      # ratchet up; the modify will reject
    b.update_stop_protection(pos, pos.entry_premium * 1.30)

    assert first in c.gtt_deleted, "stale GTT was left resting at the old trigger"
    assert len(c.gtt_placed) == 2, "no replacement GTT was placed"
    assert c.gtt_placed[-1][1] == pos.stop_price, "replacement is not at the ratcheted stop"
    assert pos.gtt_trigger_id == "GTT-2" != first


def test_gtt_cancel_refused_does_not_place_a_second_gtt():
    """Two live GTTs on one position is an oversell risk — keep the stale, still
    protective one and alert instead."""
    c = GttCancelRejectClient()
    b = _broker(c)
    pos, q, chain = _open(b, c)
    before = len(c.gtt_placed)

    pos.stop_price = pos.entry_premium * 1.10
    b.update_stop_protection(pos, pos.entry_premium * 1.30)

    assert len(c.gtt_placed) == before, "placed a second GTT while the first still rests"


def test_failed_gtt_replace_clears_the_id_so_selfheal_retries():
    """If the replace fails, `gtt_trigger_id` must NOT stay pointing at a cancelled
    GTT — otherwise ensure_stop_protection's self-heal never retries and the position
    is left with no exchange backstop at all, silently."""
    c = GttModifyRejectClient()
    b = _broker(c)
    pos, q, chain = _open(b, c)

    def dead_place(*a, **k):
        c.log.append(("place_gtt_failed",))
        raise Exception("place refused")
    c.place_stop_gtt = dead_place

    pos.stop_price = pos.entry_premium * 1.10
    b.update_stop_protection(pos, pos.entry_premium * 1.30)

    assert not pos.gtt_trigger_id, (
        "id still points at the cancelled GTT — self-heal is permanently disabled")
