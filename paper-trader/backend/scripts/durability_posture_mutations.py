"""Prove tests/test_durability_posture.py can go red — including on the exact drift that
produced it: an ADR sentence moved back into the 'Enforced now' section."""
import pathlib, subprocess, sys

ROOT = pathlib.Path("/Users/priyanshusaraf/dev/options-trading/.claude/worktrees/codex-execution-foundation/paper-trader/backend")
SESSION = ROOT / "app/db/session.py"
ADR = ROOT.parent / "docs/engineering/decisions/0015-three-planes-and-the-home-of-a-credential.md"
PY = "/Users/priyanshusaraf/dev/options-trading/paper-trader/backend/.venv/bin/python"
TEST = "tests/test_durability_posture.py"

import fcntl as _fcntl
# A mutation sweep writes mutants into the WORKING TREE and restores from an in-memory baseline,
# so two sweeps at once is destructive rather than slow: the second captures its baseline while
# the first has a mutant applied, and its restore writes that mutant back permanently. On
# 2026-08-10 that silently removed credential destruction from `OwnedConnectionStore.revoke`,
# and the only reason it surfaced was a stale-anchor SKIP in the next run.
_LOCK_FD = open(pathlib.Path(__file__).resolve().parent / ".mutation-sweep.lock", "w")
try:
    _fcntl.flock(_LOCK_FD, _fcntl.LOCK_EX | _fcntl.LOCK_NB)
except BlockingIOError:
    print("REFUSED: another mutation sweep is already running in this tree.")
    raise SystemExit(2)


MUTATIONS = [
    ("synchronous-raised-without-updating-the-adr", SESSION,
     'cur.execute("PRAGMA synchronous=NORMAL")',
     'cur.execute("PRAGMA synchronous=FULL")'),
    ("wal-turned-off", SESSION,
     'cur.execute("PRAGMA journal_mode=WAL")',
     'cur.execute("PRAGMA journal_mode=DELETE")'),
    ("foreign-keys-off", SESSION,
     'cur.execute("PRAGMA foreign_keys=ON")',
     'cur.execute("PRAGMA foreign_keys=OFF")'),
    ("contended-write-fails-instead-of-waiting", SESSION,
     'cur.execute("PRAGMA busy_timeout=10000")',
     'cur.execute("PRAGMA busy_timeout=0")'),
    # THE original defect, replayed: the false claim put back under "Enforced now".
    ("the-false-adr-claim-comes-back", ADR,
     "Deliberately NOT done now:\n\n- **`synchronous=FULL` for the money plane.",
     "- **The money plane commits with `synchronous=FULL`.** Enforced.\n\n"
     "Deliberately NOT done now:\n\n- **`synchronous=FULL` for the money plane."),
]

baselines = {p: p.read_bytes() for p in {m[1] for m in MUTATIONS}}
bad = 0
try:
    for name, path, orig, mutant in MUTATIONS:
        src = baselines[path].decode()
        if orig not in src:
            print(f"  SKIP  {name}: anchor not found"); bad += 1; continue
        path.write_text(src.replace(orig, mutant, 1))
        r = subprocess.run([PY, "-m", "pytest", TEST, "-q"], cwd=ROOT,
                           capture_output=True, text=True)
        red = r.returncode != 0
        print(f"  {'RED ' if red else 'GREEN'}  {name}{'' if red else '   <-- UNGUARDED'}")
        bad += 0 if red else 1
        path.write_bytes(baselines[path])
finally:
    for p, b in baselines.items():
        p.write_bytes(b)
print("RESTORED byte-identical:", all(p.read_bytes() == b for p, b in baselines.items()))
sys.exit(1 if bad else 0)
