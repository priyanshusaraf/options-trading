"""Engine + session factory + one-time schema/seed init."""
from __future__ import annotations

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core import instruments as inst_registry
from app.db.models import Base, CapitalState, InstrumentState, Position, UniverseInstrument
from app.engine.charges import compute_charges

_settings = get_settings()
engine = create_engine(
    f"sqlite:///{_settings.db_path}",
    future=True,
    connect_args={"check_same_thread": False},  # engine task + API threads
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_conn, _rec):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")   # concurrent reads while engine writes
    cur.execute("PRAGMA synchronous=NORMAL")
    cur.execute("PRAGMA busy_timeout=10000") # P2: wait out a contended write (engine +
                                             # API threadpool + backtest thread) instead
                                             # of failing 'database is locked'
    cur.close()


SessionLocal = sessionmaker(bind=engine, future=True, expire_on_commit=False)


def _sync_seed_universe(sess) -> None:
    """Keep persisted seed rows aligned with curated contract metadata.

    User-added rows are left alone. Seed rows may need updates when exchange
    symbol names or fallback lot sizes are corrected in code.
    """
    for inst in inst_registry.seed_instruments():
        row = sess.get(UniverseInstrument, inst.key)
        if row is None:
            sess.add(UniverseInstrument(
                key=inst.key, name=inst.name, segment=inst.segment,
                spot_exchange=inst.spot_exchange, spot_symbol=inst.spot_symbol,
                option_name=inst.option_name, lot_size=inst.lot_size,
                strike_step=inst.strike_step, priority=inst.priority,
                has_options=inst.has_options, source="seed",
                on_home=inst.on_home, active=True,
                mock_spot=inst.mock_spot, mock_vol=inst.mock_vol))
            continue
        if row.source != "seed":
            continue
        row.name = inst.name
        row.segment = inst.segment
        row.spot_exchange = inst.spot_exchange
        row.spot_symbol = inst.spot_symbol
        row.option_name = inst.option_name
        row.lot_size = inst.lot_size
        row.strike_step = inst.strike_step
        row.priority = inst.priority
        row.has_options = inst.has_options
        row.mock_spot = inst.mock_spot
        row.mock_vol = inst.mock_vol


def _repair_open_position_lot_sizes(sess) -> int:
    """Repair old open fills that were recorded as one unit instead of one lot."""
    cap = sess.get(CapitalState, 1)
    if cap is None:
        return 0
    fixed = 0
    rows = {r.key: r for r in sess.scalars(select(UniverseInstrument))}
    for pos in sess.scalars(select(Position)):
        inst = rows.get(pos.instrument_key)
        if not inst or not inst.active or inst.lot_size <= 0:
            continue
        if pos.qty == inst.lot_size and pos.lot_size == inst.lot_size:
            continue
        if pos.qty > inst.lot_size:
            continue
        old_cost = pos.entry_cost
        pos.qty = inst.lot_size
        pos.lot_size = inst.lot_size
        pos.entry_charges = compute_charges(
            pos.exchange, "BUY", pos.entry_premium, pos.qty)["total"]
        pos.entry_cost = pos.entry_premium * pos.qty + pos.entry_charges
        cap.cash -= pos.entry_cost - old_cost
        fixed += 1
    return fixed


def _migrate_schema() -> None:
    """Additive, idempotent SQLite migrations (no Alembic in this project).

    For a fresh DB, create_all already made these columns, so every ALTER is
    skipped; for an existing live DB, the new columns are appended in place
    (non-destructive — the owner's paper_trader.db keeps all its data)."""
    from sqlalchemy import text
    additions = {
        "capital_state": [
            ("account_baseline", "FLOAT"),
        ],
        "instrument_state": [
            ("live_interval", "VARCHAR(12) DEFAULT '15minute'"),
            ("entries_blocked", "BOOLEAN DEFAULT 0"),
            # dual-segment / multi-strategy assignment (Phase 0)
            ("strategy_key", "VARCHAR(64)"),
            ("priority_flag", "BOOLEAN DEFAULT 0"),
            ("product", "VARCHAR(16) DEFAULT 'options'"),
            ("overtrade_flag", "BOOLEAN DEFAULT 0"),
        ],
        "positions": [
            ("segment", "VARCHAR(16) DEFAULT 'options'"),
            ("strategy_key", "VARCHAR(64)"),
            ("last_mark_time", "DATETIME"),
            ("high_water_premium", "FLOAT DEFAULT 0.0"),
            ("reinforcement_count", "INTEGER DEFAULT 0"),
            ("last_reinforce_time", "DATETIME"),
            ("held_overnight", "BOOLEAN DEFAULT 0"),
            ("overnight_pnl", "FLOAT DEFAULT 0.0"),
            ("session_close_premium", "FLOAT DEFAULT 0.0"),
            ("last_squareoff_date", "DATE"),
            ("manual_target", "BOOLEAN DEFAULT 0"),
            ("no_take_profit", "BOOLEAN DEFAULT 0"),
            ("gtt_trigger_id", "VARCHAR(32)"),
            ("mode", "VARCHAR(8) DEFAULT 'paper'"),
        ],
        "trades": [
            ("held_overnight", "BOOLEAN DEFAULT 0"),
            ("overnight_pnl", "FLOAT DEFAULT 0.0"),
            ("intraday_pnl", "FLOAT DEFAULT 0.0"),
            ("reinforcements", "INTEGER DEFAULT 0"),
            ("mode", "VARCHAR(8) DEFAULT 'paper'"),
            ("segment", "VARCHAR(16) DEFAULT 'options'"),
            ("strategy_key", "VARCHAR(64)"),
        ],
        "equity_snapshots": [
            ("segment", "VARCHAR(16)"),
            ("strategy_key", "VARCHAR(64)"),
        ],
        "backtest_results": [
            ("params_hash", "VARCHAR(64) DEFAULT ''"),
            ("last_candle_ts", "INTEGER DEFAULT 0"),
            ("schema_version", "INTEGER DEFAULT 1"),
            ("from_cache", "BOOLEAN DEFAULT 0"),
            ("computed_at", "DATETIME"),
            ("calmar", "FLOAT"),
            ("consistency", "FLOAT"),
            ("max_consec_losses", "INTEGER DEFAULT 0"),
            ("time_underwater_pct", "FLOAT DEFAULT 0.0"),
            # round-1 honesty columns (additive, non-destructive)
            ("sharpe", "FLOAT"),
            ("worst_trade_pnl", "FLOAT DEFAULT 0.0"),
            ("worst_mae_pct", "FLOAT DEFAULT 0.0"),
            ("notional", "FLOAT DEFAULT 0.0"),
            ("lots", "INTEGER DEFAULT 0"),
            ("affordable", "BOOLEAN DEFAULT 1"),
            ("option_cost", "FLOAT DEFAULT 0.0"),
            ("open_at_end", "BOOLEAN DEFAULT 0"),
            ("win_rate_realised", "FLOAT DEFAULT 0.0"),
            ("return_pct_realised", "FLOAT DEFAULT 0.0"),
            ("bh_return_pct", "FLOAT"),
            ("first_ts", "INTEGER DEFAULT 0"),
            ("last_ts", "INTEGER DEFAULT 0"),
            ("effective_days", "INTEGER DEFAULT 0"),
            ("clamped", "BOOLEAN DEFAULT 0"),
            ("bh_curve_json", "TEXT DEFAULT '[]'"),
            ("strategy_key", "VARCHAR(64) DEFAULT 'trend_impulse_v3'"),
        ],
        "backtest_runs": [
            ("window", "VARCHAR(64) DEFAULT ''"),
            ("instruments", "VARCHAR(400) DEFAULT ''"),
            ("strategies", "VARCHAR(400) DEFAULT ''"),
        ],
    }
    with engine.begin() as conn:
        for table, cols in additions.items():
            existing = {r[1] for r in conn.execute(text(f"PRAGMA table_info({table})"))}
            if not existing:
                continue  # table not created yet; create_all handles fresh schema
            for name, ddl in cols:
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


def init_db(reset: bool = False) -> None:
    # Fail closed: a destructive reset is only ever legitimate in mock mode (the
    # sim clock restarts each run). In any other provider, refuse to DROP — this
    # is the last line of defence against a stray init_db(reset=True) (e.g. a bare
    # `python -c` run outside the pytest/conftest isolation) wiping the live book.
    if reset and get_settings().provider != "mock":
        raise RuntimeError(
            "init_db(reset=True) refused: destructive reset is only allowed in mock "
            "mode (provider='mock'). Refusing to DROP tables on a non-mock database."
        )
    if reset:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    _migrate_schema()
    s = get_settings()
    with SessionLocal() as sess:
        if sess.get(CapitalState, 1) is None:
            sess.add(CapitalState(id=1, initial_capital=s.initial_capital,
                                  cash=s.initial_capital, realized_pnl=0.0))
        _sync_seed_universe(sess)
        sess.commit()
        # enable each active universe instrument for trading by default
        for row in sess.scalars(select(UniverseInstrument)):
            if row.active and sess.get(InstrumentState, row.key) is None:
                sess.add(InstrumentState(instrument_key=row.key, enabled=True))
        _repair_open_position_lot_sizes(sess)
        sess.commit()
    inst_registry.load_universe()  # populate the in-memory registry from the DB
