"""audit H2: the LIVE ratchet (scan_signals driving RatchetState on the underlying,
restoring from persisted state each scan) must reproduce the backtest-validated
RatchetState exactly — same stop, same close-confirmed hit — including across a
'restart' (an incremental multi-scan drive == a single uninterrupted drive)."""
import datetime as dt

from app.backtest.ratchet import RatchetState, wilder_atr
from app.core.instruments import get_instrument
from app.db.session import init_db
from app.engine.runner import EngineRunner, _to_df
from app.providers.base import Candle

RM = {"atr_length": 14, "initial_risk_atr": 1.25, "trail_start_r": 1.75, "trail_atr": 3.0,
      "use_mfe_capture_floor": True, "capture_start_r": 1.25, "capture_pct": 0.35}


def _mk_candles(entry_ts, seq):
    return [Candle(ts=entry_ts + dt.timedelta(minutes=15 * (i + 1)),
                   open=c, high=h, low=l, close=c, volume=0.0)
            for i, (h, l, c) in enumerate(seq)]


def test_live_ratchet_incremental_drive_matches_a_single_drive():
    init_db(reset=True)
    r = EngineRunner()
    nifty = get_instrument("NIFTY")
    q = r.provider.get_option_chain(nifty).quotes[0]
    entry_ts = r.provider.now()
    entry_spot, entry_atr = 20000.0, 8.0
    pos = r.broker.open_position(nifty, "LONG", q, "t", entry_ts, entry_spot, params={})
    r._seed_ratchet(pos, entry_spot, RM, entry_atr, "expanding_z_v4")
    assert pos.entry_atr == entry_atr and pos.spot_stop == entry_spot - 1.25 * entry_atr

    seq = [(entry_spot + 20, entry_spot, entry_spot + 18),
           (entry_spot + 45, entry_spot + 15, entry_spot + 40),
           (entry_spot + 60, entry_spot + 35, entry_spot + 55),
           (entry_spot + 40, entry_spot - 10, entry_spot - 5)]   # last bar dumps below the ratchet
    candles = _mk_candles(entry_ts, seq)

    # reference: one uninterrupted RatchetState drive (the backtest way)
    atr = wilder_atr(_to_df(candles), RM["atr_length"])
    ref = RatchetState.restore("LONG", entry_spot, entry_atr, RM, hw=entry_spot, stop=pos.spot_stop)
    for i, c in enumerate(candles):
        ref.update(c.high, c.low, c.close, float(atr.iloc[i]))

    # live: two scans, restoring persisted state between (a 'restart' mid-position)
    r._apply_ratchet(pos, candles[:2], RM)
    hit = r._apply_ratchet(pos, candles, RM)

    assert pos.spot_stop == ref.stop            # same ratcheted stop
    assert pos.ratchet_hw == ref.hw             # same high-water
    assert hit == ref.stop_hit(candles[-1].close) is True   # the dump trips the stop


def test_default_strategy_position_is_not_ratchet_managed():
    init_db(reset=True)
    r = EngineRunner()
    nifty = get_instrument("NIFTY")
    q = r.provider.get_option_chain(nifty).quotes[0]
    pos = r.broker.open_position(nifty, "LONG", q, "t", r.provider.now(), 20000.0, params={})
    # the default v3 strategy declares no risk_model -> no seeding -> legacy trail still runs
    assert pos.entry_atr is None
