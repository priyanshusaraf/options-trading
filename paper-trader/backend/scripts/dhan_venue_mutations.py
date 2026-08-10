"""Prove the Dhan venue's guards can go red. Each mutation is a plausible refactor by analogy
with the Kite adapter — which is exactly how a second broker goes wrong."""
import pathlib, subprocess, sys

ROOT = pathlib.Path("/Users/priyanshusaraf/dev/options-trading/.claude/worktrees/codex-execution-foundation/paper-trader/backend")
VENUE = ROOT / "app/engine/dhan_venue.py"
CLIENT = ROOT / "app/engine/dhan_order_client.py"
PY = "/Users/priyanshusaraf/dev/options-trading/paper-trader/backend/.venv/bin/python"
TEST = "tests/test_dhan_venue.py"

MUTATIONS = [
    # the refusal becomes a substitution — the single most tempting wrong move
    ("server-trigger-silently-becomes-a-resting-stop", VENUE,
     """        if kind not in self.PROTECTIVE_KINDS:
            raise UnsupportedProtection(""",
     """        if False:
            raise UnsupportedProtection("""),
    ("protective-kinds-widened-to-include-gtt", VENUE,
     "PROTECTIVE_KINDS = frozenset({ProtectiveStopKind.RESTING_STOP})",
     "PROTECTIVE_KINDS = frozenset({ProtectiveStopKind.RESTING_STOP, ProtectiveStopKind.SERVER_TRIGGER})"),
    # Kite's vocabulary leaking into the second adapter
    ("product-copied-from-kite", VENUE,
     'return "INTRADAY" if tenor is Tenor.INTRADAY else default',
     'return "MIS" if tenor is Tenor.INTRADAY else default'),
    ("exchange-copied-from-kite", VENUE,
     '"NFO": "NSE_FNO",',
     '"NFO": "NFO",'),
    ("unmapped-segment-passed-through", VENUE,
     """        raise UnsupportedSegment(
            f"dhan has no segment for charge-segment {charge_segment!r}; known: "
            f"{sorted(_DHAN_EXCHANGE)}") from None""",
     "        return charge_segment"),
    # the status vocabulary
    ("filled-status-copied-from-kite", CLIENT,
     'FILLED_STATUS = "TRADED"',
     'FILLED_STATUS = "COMPLETE"'),
    ("filled-stop-read-as-live-in-the-inventory", VENUE,
     '"status": ("dead" if status in {"REJECTED", "CANCELLED", "COMPLETE", "EXPIRED"}',
     '"status": ("dead" if status in {"REJECTED", "CANCELLED", "EXPIRED"}'),
    # money-critical wire details
    ("rejected-order-returned-as-a-successful-placement", CLIENT,
     """    if status in DEAD_STATUSES:""",
     "    if False:"),
    ("trigger-not-snapped-to-the-real-tick", CLIENT,
     "        trigger = self.round_to_tick(trigger_price, tradingsymbol, exchange)",
     "        trigger = trigger_price"),
    ("over-long-tag-truncated-instead-of-refused", CLIENT,
     """            if len(tag) > 30:
                raise DhanOrderRejected(""",
     """            tag = tag[:30]
            if False:
                raise DhanOrderRejected("""),
    ("margin-probe-guesses-instead-of-failing-closed", CLIENT,
     """            log.warn(f"dhan margin probe failed: {e}", event="MARGIN_PROBE_FAIL")
            return 0.0""",
     """            log.warn(f"dhan margin probe failed: {e}", event="MARGIN_PROBE_FAIL")
            return float(req.qty) * 100.0"""),
    ("unreadable-inventory-reported-as-empty", VENUE,
     """            raise NotImplementedError(
                "this Dhan client cannot list orders, so the resting-stop inventory is unknown "
                "— refusing to report it as empty")""",
     "            return []"),
    ("modify-sent-as-a-post-like-kite", CLIENT,
     'return self.transport.put(f"/orders/{order_id}", body)',
     'return self.transport.post(f"/orders/{order_id}", body)'),
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
