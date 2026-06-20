"""The trade log needs the underlying spot at entry/exit and the % moves of both
the underlying and the option premium, alongside P&L — so a closed Trade must
serialise all of that."""
from app.core.instruments import get_instrument
from app.db.session import init_db
from app.engine.broker import PaperBroker
from app.providers.mock import MockProvider


def test_trade_to_dict_exposes_spots_and_moves():
    init_db(reset=True)
    b = PaperBroker(MockProvider())
    inst = get_instrument("NIFTY")
    chain = b.provider.get_option_chain(inst)
    q = min((x for x in chain.quotes if x.option_type == "CE"),
            key=lambda x: abs(x.strike - chain.spot))
    pos = b.open_position(inst, "LONG", q, "t", b.provider.now(), chain.spot)
    tr = b.close_position(pos, q.ltp * 1.5, "TARGET", b.provider.now(), chain.spot * 1.02)
    d = tr.to_dict()
    assert d["entry_spot"] == round(chain.spot, 2)
    assert d["exit_spot"] == round(chain.spot * 1.02, 2)
    assert d["spot_move_pct"] == 2.0           # underlying +2%
    assert d["premium_move_pct"] == 50.0       # option premium 1.5x = +50%
