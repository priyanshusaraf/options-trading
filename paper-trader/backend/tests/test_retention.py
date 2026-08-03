"""Bounded growth for the append-only telemetry tables.

Measured on production 2026-08-01: `paper_trader.db` is 108 MB and grows ~5 MB/day —
option_data ~17k rows/day, signal_events ~9k/day, equity_snapshots ~8.6k/day. The droplet
has 1 GB of RAM, 134 MB free, and there is no resize coming. Two memory leaks have already
OOM'd this box.

The rule that matters: **the money record is never pruned.** Trades, positions, the order
journal and the capital state are the ledger; losing a row there is unrecoverable and would
break the cash invariant. Only regenerable/telemetry rows age out, and the equity curve is
DOWNSAMPLED rather than deleted so history keeps its shape.
"""
import datetime as dt

from app.db.models import (
    CapitalState, EquitySnapshot, IrShadowDivergence, OptionData, OrderJournal,
    SignalEvent, Trade,
)
from app.db.session import SessionLocal, init_db
from app.engine.retention import RetentionPolicy, prune

NOW = dt.datetime(2026, 8, 1, 18, 0)


def _seed():
    init_db(reset=True)
    with SessionLocal() as s:
        for age_days in (0, 3, 30, 120):
            ts = NOW - dt.timedelta(days=age_days)
            s.add(OptionData(instrument_key="NIFTY", tradingsymbol=f"N{age_days}",
                             expiry=dt.date(2026, 8, 28), strike=24000.0,
                             option_type="CE", ts=ts, spot=24000.0, ltp=100.0,
                             bid=99.0, ask=101.0, volume=10, oi=1000, iv=0.12,
                             delta=0.5))
            s.add(SignalEvent(instrument_key="NIFTY", time=ts, signal="LONG_ENTRY",
                              close=24000.0, z=1.2, slope=1.0))
            s.add(IrShadowDivergence(
                observed_at=ts, bar_time=ts, instrument_key="NIFTY",
                authoritative_strategy_key="expanding_z_v4",
                shadow_strategy_key="ir.strategy.expanding_z_impulse",
                graph_address="sha256:deadbeef", warmup_state="settled",
                declared_warmup=302, frame_id="sha256:feed", frame_bars=400,
                reason="FLAG_DIVERGENCE", detail="longEntry", eval_ms=8.0,
                market_open=True))
        # equity: one row a minute for the last two hours, plus older days
        for i in range(120):
            s.add(EquitySnapshot(time=NOW - dt.timedelta(minutes=i), equity=50000.0,
                                 cash=50000.0, invested=0.0, realized_pnl=0.0,
                                 open_count=0))
        for i in range(120):
            s.add(EquitySnapshot(time=NOW - dt.timedelta(days=30, minutes=i),
                                 equity=49000.0, cash=49000.0, invested=0.0,
                                 realized_pnl=0.0, open_count=0))
        s.add(Trade(
            instrument_key="NIFTY", direction="LONG", option_type="CE",
            tradingsymbol="OLDTRADE", exchange="NFO", segment="options",
            strike=24000.0, expiry=dt.date(2025, 1, 29), qty=75,
            entry_premium=100.0, entry_cost=7500.0, entry_spot=24000.0,
            entry_time=NOW - dt.timedelta(days=300),
            exit_premium=110.0, exit_charges=5.0, exit_spot=24050.0,
            exit_time=NOW - dt.timedelta(days=300), exit_reason="TARGET",
            gross_pnl=750.0, charges_total=20.0, net_pnl=730.0,
            return_pct=9.7, holding_minutes=30.0, win=True))
        s.add(OrderJournal(order_id="OLD", tradingsymbol="X", instrument_key="X",
                           side="BUY", kind="equity", intent="ENTRY", qty=1,
                           status="TERMINAL",
                           placed_at=NOW - dt.timedelta(days=300)))
        s.commit()


def _counts():
    with SessionLocal() as s:
        return {
            "option_data": s.query(OptionData).count(),
            "signal_events": s.query(SignalEvent).count(),
            "equity": s.query(EquitySnapshot).count(),
            "trades": s.query(Trade).count(),
            "journal": s.query(OrderJournal).count(),
            "capital": s.query(CapitalState).count(),
            "ir_shadow_divergences": s.query(IrShadowDivergence).count(),
        }


def test_the_money_record_is_never_pruned():
    """A 300-day-old trade and its journal row outlive every retention window. This is
    the ledger — the cash invariant is computed from it and it is not regenerable."""
    _seed()
    prune(NOW, RetentionPolicy(option_data_days=1, signal_events_days=1,
                               equity_full_days=0, equity_downsample_minutes=15))
    c = _counts()
    assert c["trades"] == 1
    assert c["journal"] == 1
    assert c["capital"] == 1


def test_old_telemetry_ages_out_and_recent_telemetry_survives():
    _seed()
    report = prune(NOW, RetentionPolicy(option_data_days=90, signal_events_days=90))
    c = _counts()
    assert c["option_data"] == 3        # 0, 3, 30 days old kept; 120 dropped
    assert c["signal_events"] == 3
    assert report["option_data"] == 1
    assert report["signal_events"] == 1


def test_equity_history_is_downsampled_not_deleted():
    """The curve must keep its shape at every age — deleting old snapshots outright
    would truncate the equity chart, which is the one long-run record of how the bot
    performed."""
    _seed()
    before = _counts()["equity"]
    prune(NOW, RetentionPolicy(equity_full_days=7, equity_downsample_minutes=15))
    after = _counts()["equity"]

    assert after < before
    with SessionLocal() as s:
        recent = s.query(EquitySnapshot).filter(
            EquitySnapshot.time >= NOW - dt.timedelta(days=7)).count()
        old = s.query(EquitySnapshot).filter(
            EquitySnapshot.time < NOW - dt.timedelta(days=7)).count()
    assert recent == 120, "inside the full-resolution window nothing is touched"
    assert 0 < old <= 12, "older history is thinned to ~1 row per 15 min, not erased"


def test_prune_is_idempotent():
    _seed()
    p = RetentionPolicy(option_data_days=90, signal_events_days=90, equity_full_days=7)
    prune(NOW, p)
    after_first = _counts()
    second = prune(NOW, p)
    assert _counts() == after_first
    assert sum(second.values()) == 0


def test_retention_can_be_switched_off_entirely():
    _seed()
    before = _counts()
    prune(NOW, RetentionPolicy(enabled=False))
    assert _counts() == before


def test_a_zero_or_negative_window_disables_that_table_rather_than_deleting_everything():
    """A misconfigured `0` must mean "keep forever", never "delete the lot". The opposite
    reading turns a fat-fingered setting into permanent data loss."""
    _seed()
    before = _counts()
    prune(NOW, RetentionPolicy(option_data_days=0, signal_events_days=-1,
                               equity_full_days=0, equity_downsample_minutes=0))
    c = _counts()
    assert c["option_data"] == before["option_data"]
    assert c["signal_events"] == before["signal_events"]
    assert c["equity"] == before["equity"]
    assert c["ir_shadow_divergences"] == before["ir_shadow_divergences"]


def test_report_names_every_table_it_touched():
    """Ops needs to see what was removed; a silent prune is indistinguishable from a
    prune that failed to run."""
    _seed()
    report = prune(NOW, RetentionPolicy(option_data_days=90, signal_events_days=90,
                                        equity_full_days=7))
    assert set(report) == {"option_data", "signal_events", "equity_snapshots",
                           "ir_shadow_divergences"}
    assert all(isinstance(v, int) for v in report.values())


def test_shadow_divergences_age_out_on_the_signal_telemetry_window():
    """The shadow record is telemetry of the same class as `signal_events` and shares its
    window deliberately — a separate knob would be a new setting invisible in the Settings
    UI, and there is no reason to keep a disagreement longer than the signal it concerns."""
    _seed()
    assert _counts()["ir_shadow_divergences"] == 4

    report = prune(NOW, RetentionPolicy(signal_events_days=90))

    assert report["ir_shadow_divergences"] == 1        # the 120-day-old row only
    assert _counts()["ir_shadow_divergences"] == 3
