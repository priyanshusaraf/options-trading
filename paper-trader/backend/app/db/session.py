"""Engine + session factory + one-time schema/seed init."""
from __future__ import annotations

from sqlalchemy import create_engine, event, select, text
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
    # A pooled connection can outlive the file it points at: deploy.sh restores a
    # `.db.predeploy-*`, prune_db.py VACUUMs, a restore swaps the file. Without a
    # pre-ping the stale handle is handed to whichever request draws it next, and
    # the error surfaces far from its cause. The ping is one `SELECT 1` on a local
    # SQLite file — cheaper than the debugging it prevents.
    pool_pre_ping=True,
    # Default is 30s. A request that cannot get a connection for 10s is not going
    # to be saved by waiting 20 more — it is going to hold a worker thread while
    # the pool is already exhausted, which is how a slow lane becomes an outage.
    # Fail fast and let it surface (the readiness probe now reports it).
    pool_timeout=10,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_conn, _rec):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
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
    from app.core.execution_book import capital_for_book, resolve_book

    if sess.scalar(select(CapitalState).limit(1)) is None:
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
        if pos.lot_size == inst.lot_size:
            # H6: lot_size already records the true full lot, so pos.qty < lot_size is a
            # genuine PARTIAL fill — NOT the legacy one-unit bug (which mis-recorded
            # lot_size too). Never inflate a real partial to a full lot: that debits cash
            # never spent and leaves a position the account can't back / the bot can't close.
            continue
        old_cost = pos.entry_cost
        pos.qty = inst.lot_size
        pos.lot_size = inst.lot_size
        pos.entry_charges = compute_charges(
            pos.exchange, "BUY", pos.entry_premium, pos.qty)["total"]
        pos.entry_cost = pos.entry_premium * pos.qty + pos.entry_charges
        # Debit the ledger of the book that OWNS this position, not row 1. Repairing a
        # paper position used to move the live book's cash — the exact contamination
        # L1.3B exists to prevent, in a path that runs on every startup.
        capital_for_book(sess, resolve_book(pos.mode)).cash -= pos.entry_cost - old_cost
        fixed += 1
    return fixed


def _migrate_schema() -> None:
    """FROZEN as of Alembic revision 0001 (2026-08-02). Do not add to this dict.

    This was the project's whole migration mechanism: additive, idempotent SQLite
    ALTERs. It can only ADD COLUMN — it cannot rename, drop, retype, constrain, or
    roll back, and it carries no version number, so there was no way to ask a
    database what shape it was in.

    It is kept, and still runs, for exactly one job: carrying a database written
    before Alembic existed up to the baseline schema, after which
    `app/db/migrate.py` stamps it and takes over. Every schema change from here on
    is a revision in `migrations/versions/`. `tests/test_migrate_schema_frozen.py`
    fails the build if a column is added below.

    For a fresh DB, create_all already made these columns, so every ALTER is
    skipped; for an existing live DB, the new columns are appended in place
    (non-destructive — the owner's paper_trader.db keeps all its data)."""
    from sqlalchemy import text
    additions = {
        "capital_state": [
            ("account_baseline", "FLOAT"),
            ("anchored_at", "DATETIME"),
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
            ("entry_atr", "FLOAT"),
            ("ratchet_hw", "FLOAT"),
            ("spot_stop", "FLOAT"),
            ("ratchet_last_bar_ts", "DATETIME"),
            ("mode", "VARCHAR(8) DEFAULT 'paper'"),
            ("entry_sl_pct", "FLOAT"),
            ("entry_tp_pct", "FLOAT"),
            # peak-excursion telemetry (E0.3)
            ("mfe", "FLOAT DEFAULT 0.0"),
            ("mae", "FLOAT DEFAULT 0.0"),
        ],
        "trades": [
            ("held_overnight", "BOOLEAN DEFAULT 0"),
            ("overnight_pnl", "FLOAT DEFAULT 0.0"),
            ("intraday_pnl", "FLOAT DEFAULT 0.0"),
            ("reinforcements", "INTEGER DEFAULT 0"),
            ("mode", "VARCHAR(8) DEFAULT 'paper'"),
            ("segment", "VARCHAR(16) DEFAULT 'options'"),
            ("strategy_key", "VARCHAR(64)"),
            ("exit_price_estimated", "BOOLEAN DEFAULT 0"),
            # peak-excursion telemetry (E0.3)
            ("mfe", "FLOAT DEFAULT 0.0"),
            ("mae", "FLOAT DEFAULT 0.0"),
            # build provenance — NO DEFAULT on purpose: existing production rows
            # must stay NULL. Backfilling them with the current SHA would assert
            # a build they were not executed by.
            ("build_sha", "VARCHAR(64)"),
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
            # synthetic-premium backtest (audit C6) — Black-Scholes-on-realised-vol
            # premium path, computed alongside the spot cell so a premium bug never
            # kills the underlying result.
            ("premium_trades", "INTEGER DEFAULT 0"),
            ("premium_win_rate", "FLOAT DEFAULT 0.0"),
            ("premium_net_pnl", "FLOAT DEFAULT 0.0"),
            ("premium_return_pct", "FLOAT DEFAULT 0.0"),
            ("premium_profit_factor", "FLOAT"),
            ("premium_max_drawdown_pct", "FLOAT DEFAULT 0.0"),
            ("premium_expectancy", "FLOAT DEFAULT 0.0"),
            ("premium_charges", "FLOAT DEFAULT 0.0"),
            ("premium_trades_json", "TEXT DEFAULT '[]'"),
            ("premium_error", "VARCHAR(200) DEFAULT ''"),
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
        # Release every idle pooled connection before dropping. `DROP TABLE`
        # needs an exclusive lock, and in WAL mode a pooled connection that
        # still holds a read transaction blocks it until `busy_timeout` gives
        # up — reported as "database is locked" against whichever table came
        # first, pointing at code that has nothing to do with it. In the suite
        # that was an intermittent failure in `test_health_endpoint.py`, whose
        # TestClient lifespan resets, caused by a session leaked by an earlier
        # test. Disposing the pool is the fix at the source rather than one
        # leak at a time.
        #
        # Safe on the box: this branch is mock-only (see the guard above), and
        # a destructive reset should not be reusing connections opened before
        # the schema changed underneath them.
        engine.dispose()
        Base.metadata.drop_all(engine)
        # drop_all leaves alembic_version behind (it is not a mapped table), which
        # would tell the next init_schema() this is a managed database while every
        # real table is gone. Drop it too so a reset returns to the empty state.
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
    # Versioned migrations own the schema now. Empty DB -> create_all + stamp head;
    # pre-Alembic DB -> frozen legacy ALTERs, stamp baseline, then upgrade; managed
    # DB -> upgrade. See app/db/migrate.py for why all three converge.
    from app.db.migrate import init_schema
    init_schema(engine,
                create_all=lambda: Base.metadata.create_all(engine),
                legacy_migrate=_migrate_schema)
    s = get_settings()
    with SessionLocal() as sess:
        # The legacy deployment must exist before anything can write a row: every
        # executed-row table carries a NOT NULL deployment_id defaulting to it.
        # Seeded here for databases built by create_all (which runs no revision) and
        # by migration 0002 for databases that were migrated — whichever happens
        # first, the other is a no-op.
        from app.core.deployments import ensure_legacy_deployment
        from app.editor.graph_artifacts import ensure_catalogue_seed
        ensure_legacy_deployment(sess)
        ensure_catalogue_seed(sess)
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
