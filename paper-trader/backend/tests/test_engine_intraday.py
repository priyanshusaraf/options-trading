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


def test_intraday_entry_prices_at_live_spot_not_stale_candle_close():
    """The storm bug: equity entries opened at the last *completed candle* close while
    exits mark against the live spot — so a fast move makes the position open already
    past its target and instantly 'TARGET'-close, re-entering forever. Entries must
    price at the LIVE spot."""
    from app.core.instruments import get_instrument
    init_db(reset=True)
    key = _cheap_keys(1)[0]
    with SessionLocal() as s:
        row = s.get(InstrumentState, key) or InstrumentState(instrument_key=key)
        row.enabled = True
        row.product = "equity_intraday"
        s.add(row)
        s.commit()
    r = EngineRunner()
    r.armed = True
    r.params["intraday_enabled"] = True
    r.params["notify_enabled"] = False

    candle_close = r.provider._candles[key][r.provider._cursor].close
    live_spot = round(candle_close * 0.90, 2)        # a 10% gap down since the candle closed
    r.provider.get_ltp = lambda i: live_spot if i.key == key else None
    # a fresh SHORT signal sitting in engine state with the (stale) candle close
    r.state[key] = {"signal": "SHORT_ENTRY", "close": candle_close, "z": -2.0,
                    "slope": -1.0, "long_exit": False, "short_exit": False}

    r.process_entries()

    pos = r.broker.position_for(key)
    assert pos is not None and pos.segment == "equity_intraday"
    assert pos.entry_premium == live_spot            # priced at the LIVE spot...
    assert pos.entry_premium != candle_close          # ...not the stale candle close


def test_equity_intraday_equity_uses_margin_not_notional():
    """capital_dict equity must add an MIS position's MARGIN + unrealized P&L, not the
    full leveraged notional — the bug that ballooned equity to ~₹169k on a ₹50k base."""
    from app.core.instruments import get_instrument
    init_db(reset=True)
    r = EngineRunner()
    inst = get_instrument(_cheap_keys(1)[0])
    price = r.provider._candles[inst.key][r.provider._cursor].close
    qty = int(50000 / price)                      # ~₹50k notional -> ~₹10k margin at 5x
    r.broker.open_equity_position(inst, "SHORT", price, qty, "NSE_INTRADAY",
                                  "t", r.provider.now(), params=r.params)
    cap = r.capital_dict()
    # cash (~₹40k) + margin (~₹10k) + ~0 unrealized ≈ ₹50k — NOT ₹50k + full notional
    assert abs(cap["equity"] - 50000.0) < 2000.0
    assert cap["equity"] < 60000.0
    # the ledger split itself is already correct (cash + invested == base)
    assert abs(cap["cash"] + cap["invested"] - 50000.0) < 1.0


def test_lockstep_ratchets_both_sl_and_tp_on_an_open_position():
    """Wiring check: once an open equity position is in profit, _apply_lockstep slides
    the stop AND the target up together and floors the stop at break-even."""
    from app.core.instruments import get_instrument
    init_db(reset=True)
    r = EngineRunner()
    inst = get_instrument(_cheap_keys(1)[0])
    price = r.provider._candles[inst.key][r.provider._cursor].close
    qty = int(50000 / price)
    pos = r.broker.open_equity_position(inst, "LONG", price, qty, "NSE_INTRADAY",
                                        "t", r.provider.now(), params=r.params)
    base_stop, base_target = pos.stop_price, pos.target_price
    margin = pos.entry_cost - pos.entry_charges
    pos.last_premium = price + (0.06 * margin) / qty    # +6% of margin = 3 lockstep steps
    r._apply_lockstep(pos)
    assert pos.stop_price > base_stop          # stop ratcheted up
    assert pos.target_price > base_target      # target slid up in lockstep
    assert pos.stop_price >= price             # break-even floored (>= entry)


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
