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

    # existing data preserved + idempotent (second run must not raise)
    with eng.begin() as c:
        assert c.execute(text("SELECT live_interval FROM instrument_state")).scalar() == "15minute"
    sess._migrate_schema()
