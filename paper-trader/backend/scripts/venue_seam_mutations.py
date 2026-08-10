"""Prove the venue-boundary guards can go red.

Two families of mutation, because the boundary has two failure modes and only one of
them is about vocabulary:

  * **routing** — the broker reaches past the venue and speaks Kite directly again.
    This is the regression the seam exists to prevent.
  * **normalisation** — the venue still answers, but with the wrong reading of Kite's
    dump. This one is worse: nothing looks broken, the reconciliation just silently
    stops matching a stop that is really there, and a second one gets placed.

Every mutation must redden. A GREEN line means that behaviour is unguarded.
Run from `backend/`.
"""
import pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
LB = ROOT / "app/engine/live_broker.py"
KV = ROOT / "app/engine/kite_venue.py"
NEUTRAL = ROOT / "app/engine/venue.py"
PY = "/Users/priyanshusaraf/dev/options-trading/paper-trader/backend/.venv/bin/python"
TESTS = ["tests/test_live_broker_speaks_no_kite.py", "tests/test_venue_boundary.py",
         "tests/test_dhan_venue.py"]

MUTATIONS = [
    # ── routing: put a Kite verb back in the broker ────────────────────────
    ("gtt-place-back-to-kite", LB,
     """tid = self.venue.place_protective_stop(
                ProtectiveStopKind.SERVER_TRIGGER, tradingsymbol=pos.tradingsymbol,
                exchange=exchange, qty=pos.qty, trigger_price=pos.stop_price,
                side=side, last_price=last_price)""",
     """tid = self.client.place_stop_gtt(pos.tradingsymbol, exchange, pos.qty,
                                             pos.stop_price, last_price, side=side)"""),
    ("slm-place-back-to-kite", LB,
     """oid = self.venue.place_protective_stop(
                ProtectiveStopKind.RESTING_STOP, tradingsymbol=pos.tradingsymbol,
                exchange=exchange, qty=pos.qty, trigger_price=pos.stop_price,
                side=side, tag=TAG)""",
     """oid = self.client.place_stop_order(pos.tradingsymbol, exchange, pos.qty,
                                               pos.stop_price, side=side, tag=TAG)"""),
    ("gtt-cancel-back-to-kite", LB,
     "self.venue.cancel_protective_stop(ProtectiveStopKind.SERVER_TRIGGER, gid)",
     "self.client.delete_gtt(gid)"),
    ("slm-cancel-back-to-kite", LB,
     "self.venue.cancel_protective_stop(ProtectiveStopKind.RESTING_STOP, oid)",
     "self.client.cancel(oid)"),
    ("fired-back-to-kite-probe", LB,
     """state = self.venue.protective_stop_state(
                ProtectiveStopKind.SERVER_TRIGGER, gid)
            return bool((state or {}).get("triggered"))""",
     """probe = getattr(self.client, "gtt_status", None)
            if probe is None:
                return False
            return bool((probe(gid) or {}).get("triggered"))"""),
    # the kind must be carried, not guessed: Kite rejects each at the other's endpoint
    ("cancel-kind-collapsed", LB,
     "self.venue.cancel_protective_stop(ProtectiveStopKind.SERVER_TRIGGER, gid)",
     "self.venue.cancel_protective_stop(ProtectiveStopKind.RESTING_STOP, gid)"),

    # ── vocabulary: the broker computes the wire name itself ───────────────
    ("exchange-computed-by-the-broker", LB,
     """        exchange = self.venue.exchange_for(pos.exchange)
        try:
            tid = self.venue.place_protective_stop(""",
     """        exchange = pos.exchange
        try:
            tid = self.venue.place_protective_stop("""),
    ("inventory-read-past-the-venue", LB,
     "rows = list(self.venue.protective_inventory(kind))",
     "rows = list(getattr(self.client, 'gtts', lambda: [])() or [])"),

    # ── normalisation: the venue answers, wrongly ──────────────────────────
    ("unreadable-inventory-reported-as-empty", KV,
     """            raise NotImplementedError(
                    "this Kite client cannot list orders, so the resting-stop inventory "
                    "is unknown — refusing to report it as empty")""",
     "            return []"),
    ("filled-resting-stop-read-as-live", KV,
     '_DEAD_ORDER_STATUSES = frozenset({"REJECTED", "CANCELLED", "COMPLETE"})',
     '_DEAD_ORDER_STATUSES = frozenset({"REJECTED", "CANCELLED"})'),
    ("missing-gtt-status-read-as-dead", KV,
     'str(raw or "active").lower() in _DEAD_GTT_STATUSES',
     'str(raw or "cancelled").lower() in _DEAD_GTT_STATUSES'),
    # F6/F7 from the execution-safety review, 2026-08-10.
    ("a-none-reader-reported-as-an-empty-inventory", NEUTRAL,
     """    rows = reader()
    if rows is None:""",
     """    rows = reader()
    if False:"""),
    ("preflight-computes-the-protective-kind-by-its-own-rule", LB,
     """        protective_kind = protective_kind_for_book_segment(
            "options" if kind == "options" else "equity_intraday")""",
     """        protective_kind = (ProtectiveStopKind.SERVER_TRIGGER if kind == "options"
                           else ProtectiveStopKind.RESTING_STOP)"""),

    ("carry-product-forced-back-to-nrml", KV,
     'return kite_product(tenor, self._carry_product())',
     'return kite_product(tenor, "NRML")'),
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
