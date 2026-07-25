"""The one-off `table journal_days already exists` crash at startup.

`_get_sessionmaker()` was an UNLOCKED lazy singleton: two concurrent requests both saw
`_SessionLocal is None` and both ran `init_journal_db` + the seeders. `create_all` is
checkfirst=True, but that check-then-CREATE is not atomic, so the loser raised
OperationalError and its request 500'd. The dashboard polls 8 endpoints every 5s, so
first-touch-after-restart is exactly when two land together.

Deterministic rather than probabilistic: a barrier releases every thread at once and the
patched init sleeps, so without mutual exclusion the overlap is guaranteed.
"""
import threading
import time

from app.journal import routes


def _reset():
    routes._engine = None
    routes._SessionLocal = None


def test_concurrent_first_touch_initialises_exactly_once():
    _reset()
    real = routes.init_journal_db
    calls = []
    lock = threading.Lock()

    def slow_init(engine):
        with lock:
            calls.append(1)
        time.sleep(0.05)          # hold the window open so an unlocked racer gets in
        return real(engine)

    routes.init_journal_db = slow_init
    n = 8
    barrier = threading.Barrier(n)
    errors = []

    def worker():
        barrier.wait()
        try:
            routes._get_sessionmaker()
        except Exception as e:                 # noqa: BLE001
            errors.append(e)

    try:
        threads = [threading.Thread(target=worker) for _ in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    finally:
        routes.init_journal_db = real

    assert not errors, f"concurrent first touch raised: {errors}"
    assert len(calls) == 1, (
        f"journal DB initialised {len(calls)}x concurrently — the check-then-CREATE "
        f"race that produced 'journal_days already exists'")


def test_init_journal_db_is_idempotent_when_called_again():
    _reset()
    routes._get_sessionmaker()
    routes.init_journal_db(routes._engine)     # must not raise on an existing schema


def test_all_callers_get_the_same_sessionmaker():
    _reset()
    assert routes._get_sessionmaker() is routes._get_sessionmaker()
