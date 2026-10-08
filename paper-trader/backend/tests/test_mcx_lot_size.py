"""Kite's MCX instrument dump reports lot_size=1 for every contract; P&L needs the
contract multiplier (quote units per lot). The backtest universe, and MCX rows
loaded into the live registry, must use the real multiplier."""
from types import SimpleNamespace

from app.backtest.universe import _mcx_commodities
from app.core.instruments import MCX_UNITS_PER_LOT, _row_to_instrument, mcx_lot_size


def _dump(names):
    rows = []
    for n in names:
        for k in (100.0, 105.0, 110.0):
            for t in ("CE", "PE"):
                rows.append({"name": n, "instrument_type": t, "lot_size": 1, "strike": k,
                             "tradingsymbol": f"{n}{int(k)}{t}", "expiry": "2026-10-23"})
    return rows


class FakeProvider:
    def __init__(self, rows):
        self.rows = rows

    def _instruments(self, exch):
        return self.rows


def test_backtest_universe_uses_contract_multiplier():
    insts = {i.key: i for i in _mcx_commodities(FakeProvider(_dump(
        ["NATGASMINI", "CRUDEOILM", "GOLDM", "GOLD", "SILVERM", "NATURALGAS", "CRUDEOIL"])))}
    assert insts["NATGASMINI"].lot_size == 250
    assert insts["CRUDEOILM"].lot_size == 10
    assert insts["GOLDM"].lot_size == 10          # 100 g quoted per 10 g
    assert insts["GOLD"].lot_size == 100
    assert insts["SILVERM"].lot_size == 5
    assert insts["NATURALGAS"].lot_size == 1250
    assert insts["CRUDEOIL"].lot_size == 100
    assert insts["NATGASMINI"].strike_step == 5.0


def test_unknown_contract_keeps_reported_or_one():
    insts = {i.key: i for i in _mcx_commodities(FakeProvider(_dump(["MYSTERYCMDTY"])))}
    assert insts["MYSTERYCMDTY"].lot_size == 1
    assert mcx_lot_size("MYSTERYCMDTY", reported=40) == 40
    assert mcx_lot_size("MYSTERYCMDTY", reported=1, fallback=7) == 7


def test_stored_mcx_row_with_lot_one_is_repaired_on_load():
    row = SimpleNamespace(key="NATGASMINI", name="NATGASMINI", segment="MCX",
                          spot_exchange="MCX", spot_symbol="NATGASMINI",
                          option_name="NATGASMINI", lot_size=1, strike_step=5.0,
                          priority=100, mock_spot=300.0, mock_vol=0.5, has_options=True,
                          on_home=True, source="user")
    assert _row_to_instrument(row).lot_size == 250
    nfo = SimpleNamespace(**{**vars(row), "segment": "NFO", "key": "X", "lot_size": 1})
    assert _row_to_instrument(nfo).lot_size == 1     # only MCX rows are touched


def test_table_is_consistent_with_seed_contracts():
    from app.core.instruments import SEED_INSTRUMENTS
    for k, inst in SEED_INSTRUMENTS.items():
        if inst.segment == "MCX" and k in MCX_UNITS_PER_LOT:
            assert MCX_UNITS_PER_LOT[k] == inst.lot_size, k
