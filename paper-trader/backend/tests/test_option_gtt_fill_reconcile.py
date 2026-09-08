"""E6 — the bot's OWN options GTT firing must not be booked as an EXTERNAL exit.

The equity branch of `reconcile_orphans` asks the resting stop order whether it filled
(R3) and books STOP_LOSS, excluded from the runner's same-day re-entry auto-block. The
options branch booked `RECONCILED_EXTERNAL_EXIT` unconditionally — so when the bot's own
GTT stop fired, the trade was mislabelled (corrupting exit-reason analytics, which is
what the backtest-vs-live comparison is built on) and the instrument got a false
same-day re-entry block.

E0.1 already fixed the PRICE on this path (find_fill → the real SELL fill). What remains
is the label and the attribution. A GTT trigger_id is NOT an order_id, so `status()`
can't answer this — it needs the GTT's own state.
"""
import datetime as dt

from sqlalchemy import select

from app.core.instruments import get_instrument
from app.db.models import Trade
from app.db.session import SessionLocal
from app.engine.broker import PaperBroker
from tests.admitted_entry import persist_admitted_entry
from tests.test_live_broker import FakeClient, _broker

REAL_FILL = {"avg_price": 42.5, "filled_qty": 75}


class GttFiredClient(FakeClient):
    """The resting GTT reads as already triggered — the bot's own stop closed this."""

    def gtt_status(self, trigger_id):
        return {"status": "triggered"}


class GttActiveClient(FakeClient):
    """The GTT is still resting, so whatever flattened the account was external."""

    def gtt_status(self, trigger_id):
        return {"status": "active"}


class GttStatusBrokenClient(FakeClient):
    def gtt_status(self, trigger_id):
        raise Exception("gtt read failed")


def _open_option_orphan(b, gid="GTT-9"):
    inst = get_instrument("NIFTY")
    chain = b.provider.get_option_chain(inst)
    q = min((x for x in chain.quotes if x.option_type == "CE"),
            key=lambda x: abs(x.strike - chain.spot))
    admission = persist_admitted_entry(b.s)
    pos = PaperBroker.open_position(b, inst, "LONG", q, "t", b.provider.now(), chain.spot,
                                    **admission)
    pos.entry_time = b.provider.now() - dt.timedelta(minutes=5)   # past the 60s guard
    pos.gtt_trigger_id = gid
    b.commit()
    return pos


def _reconcile_twice(b):
    b.reconcile_orphans(b.provider.now())            # streak=1, not yet confirmed
    return b.reconcile_orphans(b.provider.now())     # confirmed -> books it


def _the_trade():
    with SessionLocal() as s:
        trades = list(s.scalars(select(Trade)))
    assert len(trades) == 1, trades
    return trades[0]


def test_own_gtt_fill_is_booked_stop_loss_not_external():
    c = GttFiredClient(found_fill=REAL_FILL)
    b = _broker(c, account=[])
    _open_option_orphan(b)

    booked = _reconcile_twice(b)

    assert booked == [], "the bot's own GTT fill triggered a false re-entry block"
    tr = _the_trade()
    assert tr.exit_reason == "STOP_LOSS", (
        f"own GTT fill mislabelled '{tr.exit_reason}' — corrupts exit-reason analytics")
    assert tr.exit_premium == REAL_FILL["avg_price"]   # E0.1's real fill, preserved


def test_own_gtt_fill_is_not_cancelled_again():
    c = GttFiredClient(found_fill=REAL_FILL)
    b = _broker(c, account=[])
    _open_option_orphan(b)

    _reconcile_twice(b)

    assert c.gtt_deleted == [], "tried to cancel a GTT that had already fired"


def test_a_still_resting_gtt_means_a_genuinely_external_exit():
    """Guard the other direction: if the GTT never fired, today's behaviour stands —
    external exit, re-entry blocked, and the resting GTT pulled."""
    c = GttActiveClient(found_fill=REAL_FILL)
    b = _broker(c, account=[])
    _open_option_orphan(b)

    booked = _reconcile_twice(b)

    assert booked == ["NIFTY"]
    assert _the_trade().exit_reason == "RECONCILED_EXTERNAL_EXIT"
    assert c.gtt_deleted == ["GTT-9"]


def test_a_failed_gtt_read_falls_back_to_external():
    """Conservative fallback, mirroring the equity path: an unreadable GTT must not be
    assumed to have fired (that would silently skip the re-entry block)."""
    c = GttStatusBrokenClient(found_fill=REAL_FILL)
    b = _broker(c, account=[])
    _open_option_orphan(b)

    booked = _reconcile_twice(b)

    assert booked == ["NIFTY"]
    assert _the_trade().exit_reason == "RECONCILED_EXTERNAL_EXIT"


def test_a_client_without_gtt_status_still_reconciles():
    """Older/paper clients don't implement gtt_status — must not crash reconcile."""
    c = FakeClient(found_fill=REAL_FILL)
    b = _broker(c, account=[])
    _open_option_orphan(b)

    booked = _reconcile_twice(b)

    assert booked == ["NIFTY"]
    assert _the_trade().exit_reason == "RECONCILED_EXTERNAL_EXIT"
