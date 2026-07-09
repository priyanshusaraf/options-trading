"""audit P2: SQLite writers (engine session, API threadpool, backtest thread) can
collide. SQLAlchemy's implicit 5s connect timeout is short for that 3-way
contention and relies on a library default; set busy_timeout explicitly to 10s so
a contended writer waits it out instead of erroring with 'database is locked'."""
from app.db.session import engine


def test_connection_has_explicit_busy_timeout():
    with engine.connect() as conn:
        got = conn.exec_driver_sql("PRAGMA busy_timeout").scalar()
    assert got == 10000
