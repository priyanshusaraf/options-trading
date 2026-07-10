"""The additive ALTER-based migration must upgrade an old DB in place, idempotently."""
from sqlalchemy import create_engine, text


def test_migration_adds_missing_columns(tmp_path, monkeypatch):
    db = tmp_path / "old.db"
    eng = create_engine(f"sqlite:///{db}", future=True)
    # an "old" schema missing every new column
    with eng.begin() as c:
        c.execute(text("CREATE TABLE instrument_state ("
                       "instrument_key VARCHAR(32) PRIMARY KEY, enabled BOOLEAN)"))
        c.execute(text("INSERT INTO instrument_state VALUES ('NIFTY', 1)"))
        c.execute(text("CREATE TABLE positions (id INTEGER PRIMARY KEY, last_spot FLOAT)"))
        c.execute(text("CREATE TABLE backtest_results (id INTEGER PRIMARY KEY, error VARCHAR(400))"))

    import app.db.session as sess
    monkeypatch.setattr(sess, "engine", eng)
    sess._migrate_schema()

    with eng.begin() as c:
        istate = {r[1] for r in c.execute(text("PRAGMA table_info(instrument_state)"))}
        pos = {r[1] for r in c.execute(text("PRAGMA table_info(positions)"))}
        bt = {r[1] for r in c.execute(text("PRAGMA table_info(backtest_results)"))}
    assert {"live_interval", "entries_blocked"} <= istate
    assert {"last_mark_time", "high_water_premium"} <= pos
    assert {"params_hash", "last_candle_ts", "schema_version", "from_cache", "computed_at"} <= bt
    # round-1 honesty columns must be added in place too (additive, non-destructive)
    assert {"notional", "lots", "affordable", "first_ts", "last_ts", "effective_days",
            "clamped", "open_at_end", "win_rate_realised", "return_pct_realised",
            "bh_return_pct", "worst_trade_pnl", "sharpe", "worst_mae_pct",
            "bh_curve_json"} <= bt
    # synthetic-premium backtest (audit C6) columns must be added in place too
    assert {"premium_trades", "premium_win_rate", "premium_net_pnl",
            "premium_return_pct", "premium_profit_factor", "premium_max_drawdown_pct",
            "premium_expectancy", "premium_charges", "premium_trades_json",
            "premium_error"} <= bt

    # existing data preserved + idempotent (second run must not raise)
    with eng.begin() as c:
        assert c.execute(text("SELECT live_interval FROM instrument_state")).scalar() == "15minute"
    sess._migrate_schema()


def test_migration_adds_dual_segment_columns(tmp_path, monkeypatch):
    """Dual-segment / multi-strategy columns must be appended to an old DB in place
    so the owner's existing paper_trader.db gains segment + strategy dimensions
    without losing data, and existing options rows backfill to segment='options'."""
    db = tmp_path / "old.db"
    eng = create_engine(f"sqlite:///{db}", future=True)
    with eng.begin() as c:
        c.execute(text("CREATE TABLE instrument_state ("
                       "instrument_key VARCHAR(32) PRIMARY KEY, enabled BOOLEAN)"))
        c.execute(text("CREATE TABLE positions (id INTEGER PRIMARY KEY, last_spot FLOAT)"))
        c.execute(text("INSERT INTO positions (id, last_spot) VALUES (1, 100.0)"))
        c.execute(text("CREATE TABLE trades (id INTEGER PRIMARY KEY, net_pnl FLOAT)"))
        c.execute(text("CREATE TABLE equity_snapshots (id INTEGER PRIMARY KEY, equity FLOAT)"))
        c.execute(text("CREATE TABLE backtest_results (id INTEGER PRIMARY KEY, error VARCHAR(400))"))

    import app.db.session as sess
    monkeypatch.setattr(sess, "engine", eng)
    sess._migrate_schema()

    with eng.begin() as c:
        istate = {r[1] for r in c.execute(text("PRAGMA table_info(instrument_state)"))}
        pos = {r[1] for r in c.execute(text("PRAGMA table_info(positions)"))}
        trd = {r[1] for r in c.execute(text("PRAGMA table_info(trades)"))}
        eq = {r[1] for r in c.execute(text("PRAGMA table_info(equity_snapshots)"))}
        bt = {r[1] for r in c.execute(text("PRAGMA table_info(backtest_results)"))}
    assert {"strategy_key", "priority_flag", "product"} <= istate
    assert {"segment", "strategy_key"} <= pos
    assert {"segment", "strategy_key"} <= trd
    assert {"segment", "strategy_key"} <= eq
    assert "strategy_key" in bt

    # existing options positions backfill to segment='options'
    with eng.begin() as c:
        assert c.execute(text("SELECT segment FROM positions WHERE id=1")).scalar() == "options"
    sess._migrate_schema()  # idempotent
