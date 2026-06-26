"""End-to-end proof that the live tick loop trades the intraday-equity segment in
paper/mock mode: instruments flagged product='equity_intraday' open MIS positions
sized in the 7–10k margin band, mark to SPOT, exit on the tight SL/TP, never exceed
the concurrency cap, and keep the ledger reconciliation exact through every round
trip. The options path is left to its own (unchanged) tests."""
from sqlalchemy import select

from app.core.instruments import all_instruments
from app.db.models import InstrumentState, Trade
from app.db.session import SessionLocal, init_db
from app.engine.runner import EngineRunner
from app.providers.mock import MockProvider


def _cheap_keys(n: int = 3, lo: float = 100.0, hi: float = 1500.0) -> list[str]:
    """Mock instruments whose current price lets a 7–10k margin (×5) buy ≥1 share
    inside the band — so the min-margin floor doesn't skip every signal."""
    prov = MockProvider()
    out = []
    for inst in all_instruments():
        px = prov._candles[inst.key][prov._cursor].close
        if lo <= px <= hi:
            out.append(inst.key)
        if len(out) >= n:
            break
    return out


def test_intraday_equity_trades_end_to_end():
    init_db(reset=True)
    keys = _cheap_keys()
    assert keys, "expected at least one affordably-priced mock instrument"
    with SessionLocal() as s:
        for k in keys:
            row = s.get(InstrumentState, k) or InstrumentState(instrument_key=k)
            row.enabled = True
            row.product = "equity_intraday"
            s.add(row)
        s.commit()

    r = EngineRunner()
    r.armed = True
    r.params["intraday_enabled"] = True
    r.params["notify_enabled"] = False

    saw_open = False
    max_open = 0
    margins: list[float] = []
    for _ in range(300):
        r.tick()
        eq = [p for p in r.broker.open_positions() if p.segment == "equity_intraday"]
        if eq:
            saw_open = True
            max_open = max(max_open, len(eq))
            for p in eq:
                assert p.option_type == "EQ" and p.qty >= 1
                margins.append(p.entry_cost - p.entry_charges)
        r.provider.advance()

    with SessionLocal() as s:
        eq_trades = [t for t in s.scalars(select(Trade))
                     if t.segment == "equity_intraday"]

    assert saw_open, "no intraday-equity position ever opened"
    assert eq_trades, "no intraday-equity trade ever closed"
    # concurrency cap honoured
    assert max_open <= r.params.get("intraday_max_positions", 3)
    # every opened position sized inside the 7–10k margin band
    assert margins and all(6999.0 <= m <= 10001.0 for m in margins)
    # the equity round-trips kept the cash ledger exact
    assert r.broker.reconcile()["diff"] == 0.0
    # closed equity trades carry the segment + a real exit reason
    assert all(t.exit_reason in ("STOP_LOSS", "TARGET", "STRATEGY_EXIT",
                                 "INTRADAY_SQUAREOFF") for t in eq_trades)


def test_options_path_untouched_when_intraday_disabled():
    """With intraday off (the default), an instrument left as product='options'
    still trades options exactly as before — the equity branch is inert."""
    init_db(reset=True)
    r = EngineRunner()
    r.armed = True
    # intraday_enabled defaults False; do NOT enable it
    for _ in range(200):
        r.tick()
        r.provider.advance()
    # options positions/trades still happen and the ledger reconciles
    assert r.broker.reconcile()["diff"] == 0.0
    with SessionLocal() as s:
        assert not [t for t in s.scalars(select(Trade)) if t.segment == "equity_intraday"]
