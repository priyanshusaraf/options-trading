"""Prove the split-routing and Upstox-conformance guards can go red.

Three families:

  * **routing** — the composition root collapses the two roles back into one, which is the
    pre-phase-6 behaviour and the silent one: the operator configures live, the engine looks
    healthy, and orders authenticate as the wrong account (or as nobody).
  * **refusal** — a data-only connection named for execution stops refusing. This is the
    failure the whole seam exists to prevent, and it presents as "the bot just doesn't trade".
  * **adapter semantics** — the Upstox adapter answers, wrongly. Nothing raises; the numbers
    are just not the numbers.

A GREEN line means that behaviour is unguarded. Run from `backend/`.
"""
import pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONN = ROOT / "app/providers/connection.py"
BF = ROOT / "app/engine/broker_factory.py"
UPS = ROOT / "app/providers/upstox.py"
BASE = ROOT / "app/providers/base.py"
PY = "/Users/priyanshusaraf/dev/options-trading/paper-trader/backend/.venv/bin/python"
TESTS = ["tests/test_split_routing.py", "tests/test_provider_conformance.py",
         "tests/test_execution_connection.py", "tests/test_upstox_adapter.py"]

MUTATIONS = [
    # ── routing ────────────────────────────────────────────────────────────
    ("split-collapsed-back-to-one-connection", CONN,
     "    executor = provider_named(chosen)",
     "    return None\n    executor = provider_named(chosen)"),
    ("execution-scope-reuses-the-legacy-book", CONN,
     'return connection_for(executor, scope=f"{chosen}:execution")',
     "return connection_for(executor)"),

    # ── refusal ────────────────────────────────────────────────────────────
    ("data-only-connection-silently-paper-trades", BF,
     "            raise ConnectionCannotExecute(\n"
     '                f"connection {conn.scope!r} (broker {conn.broker!r}) was named for execution "',
     "            pass\n        if False:\n            raise ConnectionCannotExecute(\n"
     '                f"connection {conn.scope!r} (broker {conn.broker!r}) was named for execution "'),

    # ── adapter semantics ──────────────────────────────────────────────────
    ("forming-bar-kept", UPS,
     "return [b for b in ordered if b.ts <= cutoff]",
     "return ordered"),
    ("interval-rounded-instead-of-refused", UPS,
     """        raise UnsupportedInterval(
            f"upstox does not serve interval {interval!r}; supported: "
            f"{sorted(INTERVAL_MAP)} — refusing rather than substituting a nearby interval")""",
     '        return ("minutes", 1)'),
    ("candle-timezone-left-aware", UPS,
     'ts = (ts.astimezone(IST) if ts.tzinfo is not None else ts).replace(tzinfo=None)',
     'ts = ts.astimezone(IST) if ts.tzinfo is not None else ts'),
    ("intraday-endpoint-never-read", UPS,
     """        intraday = self._transport.get(
            f"/v3/historical-candle/intraday/{key}/{unit}/{size}")
        intraday_rows = _candle_rows(intraday)""",
     "        intraday_rows = []"),

    # ── the optional-method default that let a data-only adapter exist ─────
    ("option_ltp-invents-a-price-instead-of-refusing", BASE,
     '''        and to feed the per-instrument option price chart. `None` = cannot price."""
        return None''',
     '''        and to feed the per-instrument option price chart. `None` = cannot price."""
        return 1.0'''),
]


# ── concurrency guard ─────────────────────────────────────────────────────
# A mutation sweep writes mutants into the WORKING TREE and restores from an in-memory baseline.
# Two sweeps running at once is therefore destructive, not merely slow: sweep B captures its
# baseline while sweep A has a mutant applied, and B's restore writes A's mutant back
# permanently. That happened on 2026-08-10 — `OwnedConnectionStore.revoke` silently lost
# `credential_ciphertext = None`, so revocation stopped destroying the credential, and the only
# reason it was caught is that the sweep reported the anchor as stale.
#
# An exclusive lock on the repo makes the second sweep refuse instead of corrupting the first.
import fcntl
_LOCK_PATH = pathlib.Path(__file__).resolve().parent / ".mutation-sweep.lock"
_LOCK_FD = open(_LOCK_PATH, "w")
try:
    fcntl.flock(_LOCK_FD, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    print("REFUSED: another mutation sweep is already running in this tree. Running two at once "
          "restores one sweep's mutant permanently over the other's baseline.")
    sys.exit(2)


baselines = {p: p.read_bytes() for p in {m[1] for m in MUTATIONS}}
bad = 0
try:
    for name, path, orig, mutant in MUTATIONS:
        src = baselines[path].decode()
        if orig not in src:
            print(f"  SKIP  {name}: anchor not found — this table is stale")
            bad += 1
            continue
        path.write_text(src.replace(orig, mutant, 1))
        r = subprocess.run([PY, "-m", "pytest", *TESTS, "-q"], cwd=ROOT,
                           capture_output=True, text=True)
        red = r.returncode != 0
        print(f"  {'RED ' if red else 'GREEN'}  {name}{'' if red else '   <-- UNGUARDED'}")
        bad += 0 if red else 1
        path.write_bytes(baselines[path])
finally:
    for p, b in baselines.items():
        p.write_bytes(b)
print("RESTORED byte-identical:",
      all(p.read_bytes() == b for p, b in baselines.items()))
sys.exit(1 if bad else 0)
