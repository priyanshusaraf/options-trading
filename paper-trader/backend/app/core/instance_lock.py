"""Single-instance guard (audit C7).

Two backend processes pointed at the same persistent DB would each run their own
signal/risk loops and their own LiveBroker with empty in-flight state, so both
could place a real order for the same instrument on the same account. An exclusive
advisory flock keyed to the DB path lets only one backend run at a time.

flock (not a plain pidfile) is used deliberately: the lock is tied to the open
file and released by the OS when the holder dies, so a crashed backend never
leaves a stale lock that blocks a restart.
"""
from __future__ import annotations

import fcntl
import os


def acquire_db_lock(db_path: str):
    """Take the single-instance lock for this DB/account. Returns the held file
    handle — keep it alive for the whole process lifetime (closing it, or the
    process exiting, releases the lock). Raises RuntimeError if another live
    backend already holds it."""
    lock_path = f"{db_path}.lock"
    fh = open(lock_path, "w")
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        raise RuntimeError(
            f"another paper-trader backend already holds {lock_path} — refusing to "
            f"start a second instance on the same account/DB. If no other backend is "
            f"running, the lock will have been auto-released; check `ps` for a stray "
            f"uvicorn.")
    fh.write(str(os.getpid()))
    fh.flush()
    return fh
