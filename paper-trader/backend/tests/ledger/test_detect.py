from datetime import datetime

from sqlalchemy.orm import sessionmaker

from app.ledger.db import init_ledger_db, make_engine
from app.ledger.detect import detect_manual_fills as _detect_manual_fills
from app.ledger.models import LedgerManualFill
from app.providers.kite import KiteProvider as _KiteForCaps
from app.db.models import LEGACY_BROKER_ACCOUNT_ID, LEGACY_OWNER_ID


def detect_manual_fills(*args, **kwargs):
    kwargs.setdefault("owner_id", LEGACY_OWNER_ID)
    kwargs.setdefault("broker_account_id", LEGACY_BROKER_ACCOUNT_ID)
    return _detect_manual_fills(*args, **kwargs)


class _Provider:
    name = "kite"
    CAPABILITIES = _KiteForCaps.CAPABILITIES  # a double impersonating Kite must declare what Kite declares

    def __init__(self, orders, trades=None):
        self._o, self._t = orders, trades or []

    def account_orders(self):
        return self._o

    def account_trades(self):
        return self._t


def _sm(tmp_path):
    engine = make_engine(str(tmp_path / "l.db"))
    init_ledger_db(engine)
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


def order(**kw):
    base = {"order_id": "o1", "tag": None, "tradingsymbol": "NIFTY25000CE",
            "status": "COMPLETE", "transaction_type": "BUY",
            "filled_quantity": 65, "average_price": 120.5, "product": "NRML",
            "exchange": "NFO", "order_timestamp": datetime(2026, 7, 31, 9, 30)}
    base.update(kw)
    return base


NOW = datetime(2026, 7, 31, 9, 31)


def test_a_manual_order_is_persisted(tmp_path):
    sm = _sm(tmp_path)
    n = detect_manual_fills(_Provider([order()]), None, sm, NOW,
                            bot_ids=set(), bot_symbols=set())
    assert n == 1
    with sm() as s:
        assert s.get(LedgerManualFill, "o1").verdict == "MANUAL"


def test_a_bot_order_is_not_persisted(tmp_path):
    sm = _sm(tmp_path)
    n = detect_manual_fills(_Provider([order(tag="pt-bot")]), None, sm, NOW,
                            bot_ids=set(), bot_symbols=set())
    assert n == 0
    with sm() as s:
        assert s.get(LedgerManualFill, "o1") is None


def test_needs_review_is_persisted_and_labelled(tmp_path):
    sm = _sm(tmp_path)
    detect_manual_fills(_Provider([order(tradingsymbol="RELIANCE")]), None, sm,
                        NOW, bot_ids=set(), bot_symbols={"RELIANCE"})
    with sm() as s:
        assert s.get(LedgerManualFill, "o1").verdict == "NEEDS_REVIEW"


def test_repolling_the_same_order_does_not_duplicate(tmp_path):
    sm = _sm(tmp_path)
    p = _Provider([order()])
    detect_manual_fills(p, None, sm, NOW, bot_ids=set(), bot_symbols=set())
    detect_manual_fills(p, None, sm, NOW, bot_ids=set(), bot_symbols=set())
    with sm() as s:
        assert s.query(LedgerManualFill).count() == 1


def test_a_claimed_row_is_never_overwritten_by_a_repoll(tmp_path):
    sm = _sm(tmp_path)
    p = _Provider([order()])
    detect_manual_fills(p, None, sm, NOW, bot_ids=set(), bot_symbols=set())
    with sm() as s, s.begin():
        s.get(LedgerManualFill, "o1").claimed_trade = "tr_1"
    detect_manual_fills(p, None, sm, NOW, bot_ids=set(), bot_symbols=set())
    with sm() as s:
        assert s.get(LedgerManualFill, "o1").claimed_trade == "tr_1"


def test_a_failed_read_persists_nothing_and_does_not_raise(tmp_path):
    # None means "we could not look", which must never be recorded as "you
    # placed no manual trades today".
    sm = _sm(tmp_path)
    assert detect_manual_fills(_Provider(None), None, sm, NOW,
                               bot_ids=set(), bot_symbols=set()) == 0
    with sm() as s:
        assert s.query(LedgerManualFill).count() == 0


def test_an_empty_orderbook_is_distinct_from_a_failed_read(tmp_path):
    sm = _sm(tmp_path)
    assert detect_manual_fills(_Provider([]), None, sm, NOW,
                               bot_ids=set(), bot_symbols=set()) == 0


def test_unfilled_orders_are_ignored(tmp_path):
    sm = _sm(tmp_path)
    n = detect_manual_fills(
        _Provider([order(status="CANCELLED", filled_quantity=0)]), None, sm,
        NOW, bot_ids=set(), bot_symbols=set())
    assert n == 0


def test_the_whole_kite_dict_is_kept_for_forensics(tmp_path):
    # Kite's orderbook is same-day only; we cannot re-ask tomorrow.
    sm = _sm(tmp_path)
    detect_manual_fills(_Provider([order()]), None, sm, NOW,
                        bot_ids=set(), bot_symbols=set())
    with sm() as s:
        assert "NIFTY25000CE" in s.get(LedgerManualFill, "o1").raw


def test_broker_price_and_qty_are_recorded_so_the_owner_never_types_them(tmp_path):
    sm = _sm(tmp_path)
    detect_manual_fills(_Provider([order()]), None, sm, NOW,
                        bot_ids=set(), bot_symbols=set())
    with sm() as s:
        row = s.get(LedgerManualFill, "o1")
    assert row.avg_price == 120.5
    assert row.qty == 65
    assert row.side == "BUY"
    assert row.order_ts == datetime(2026, 7, 31, 9, 30)
