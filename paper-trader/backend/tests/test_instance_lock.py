"""audit C7: two backend processes must not trade the same account. A single-
instance advisory lock keyed to the DB path refuses a second start; the lock is
an flock, so it is auto-released if the holder dies (no stale-pidfile problem)."""
import pytest

from app.core.instance_lock import acquire_db_lock


def test_second_backend_on_same_db_is_refused(tmp_path):
    db = str(tmp_path / "paper_trader.db")
    fh1 = acquire_db_lock(db)                     # first backend holds the lock
    try:
        with pytest.raises(RuntimeError, match="another"):
            acquire_db_lock(db)                  # second backend, same DB -> refused
    finally:
        fh1.close()


def test_lock_released_on_close_allows_restart(tmp_path):
    db = str(tmp_path / "paper_trader.db")
    fh1 = acquire_db_lock(db)
    fh1.close()                                  # first backend exits -> lock released
    fh2 = acquire_db_lock(db)                    # restart is allowed
    fh2.close()


def test_different_dbs_do_not_conflict(tmp_path):
    fh1 = acquire_db_lock(str(tmp_path / "a.db"))
    fh2 = acquire_db_lock(str(tmp_path / "b.db"))   # unrelated account/DB -> fine
    fh1.close()
    fh2.close()
