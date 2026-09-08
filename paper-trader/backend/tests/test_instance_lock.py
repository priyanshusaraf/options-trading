"""audit C7: two backend processes must not trade the same account. A single-
instance advisory lock keyed to the DB path refuses a second start; the lock is
an flock, so it is auto-released if the holder dies (no stale-pidfile problem)."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.core.instance_lock import acquire_db_lock

BACKEND_DIR = Path(__file__).resolve().parents[1]


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


# --------------------------------------------------------------------------
# B5: process-boundary proof. Acquiring the lock twice inside one interpreter
# only exercises the helper; the contract is between two OPERATING SYSTEM
# processes. These subprocess proofs use a temporary database and paper-only
# settings. They are a LOCAL process-boundary proof — not production or
# multi-host evidence.
# --------------------------------------------------------------------------

_HOLDER = (
    "import sys, time\n"
    "from app.core.instance_lock import acquire_db_lock\n"
    "fh = acquire_db_lock(sys.argv[1])\n"
    "print('HELD', flush=True)\n"
    "time.sleep(120)\n"
)


def _child(db: str, code: str) -> subprocess.Popen:
    environment = os.environ.copy()
    environment["PT_DOTENV_DISABLED"] = "1"   # paper-only, no dotenv side effects
    return subprocess.Popen(
        [sys.executable, "-c", code, db],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, cwd=BACKEND_DIR, env=environment,
    )


def test_second_process_on_same_db_is_refused_then_replacement_starts(tmp_path):
    """1) Process A takes the lock. 2) Independent process B against the SAME
    target refuses. 3) A dies (SIGKILL). 4) A replacement process starts."""
    db = str(tmp_path / "paper_trader.db")
    holder = _child(db, _HOLDER)
    try:
        assert holder.stdout.readline().strip() == "HELD"

        refused = subprocess.run(
            [sys.executable, "-c",
             "import sys\n"
             "from app.core.instance_lock import acquire_db_lock\n"
             "try:\n"
             "    acquire_db_lock(sys.argv[1])\n"
             "    print('STARTED')\n"
             "except RuntimeError as error:\n"
             "    print('REFUSED:', error)\n",
             db],
            capture_output=True, text=True, cwd=BACKEND_DIR,
            env={**os.environ, "PT_DOTENV_DISABLED": "1"}, timeout=60)
        assert refused.returncode == 0, refused.stderr
        assert refused.stdout.startswith("REFUSED:"), refused.stdout
        assert "already holds" in refused.stdout

        holder.kill()                              # holder dies hard
        holder.wait(timeout=30)
    finally:
        if holder.poll() is None:
            holder.kill()
            holder.wait(timeout=30)

    replacement = _child(db, _HOLDER)
    try:
        # flock releases on holder death: replacement must be able to start.
        assert replacement.stdout.readline().strip() == "HELD"
    finally:
        replacement.kill()
        replacement.wait(timeout=30)


def test_two_concurrent_processes_cannot_both_hold(tmp_path):
    """Race-shaped variant: launch many contenders against one target; exactly
    one wins, the rest refuse — across real processes."""
    db = str(tmp_path / "paper_trader.db")
    contenders = [_child(db, _HOLDER.replace("time.sleep(120)", "time.sleep(3)"))
                  for _ in range(4)]
    outcomes = []
    try:
        for contender in contenders:
            line = contender.stdout.readline().strip()
            code = contender.wait(timeout=60)
            err = contender.stderr.read()
            outcomes.append((code, line, err))
    finally:
        for contender in contenders:
            if contender.poll() is None:
                contender.kill()
                contender.wait(timeout=30)
    held = [line for code, line, _err in outcomes if line == "HELD"]
    refused = [(code, err) for code, line, err in outcomes if line != "HELD"]
    assert len(held) == 1, f"expected exactly one lock winner, got {outcomes}"
    # Every loser is a real process that exited refusing: nonzero exit with
    # the single-instance message on stderr.
    assert all(code != 0 and "already holds" in err for code, err in refused), \
        outcomes
