# Deterministic-execution audit — 2026-08-02

The Phase-1 brief asks to *verify* deterministic execution across: order placement,
retries, reconnects, broker failures, VPS recovery, kill switch, arm/disarm, and
duplicate-order prevention.

**Method:** for each item, find the guard, then write a test that asserts the *property*
rather than the code shape — and check the test can fail. Reading a guard and agreeing with
it is not verification; a later refactor can preserve the shape and lose the guarantee.

**Headline:** most of this was genuinely covered. One item was not, and it was the kill
switch — the control you reach for when things are already going wrong.

---

## Verdicts

| Item | Verdict |
|---|---|
| Kill switch | **DEFECT FOUND AND FIXED** — a failing cancel stopped the square-off |
| Duplicate-order prevention | **Holds**, now asserted |
| Arm/disarm | **Holds** — disarmed opens nothing, however many times entries run |
| Order placement | Covered by the existing live-path suite |
| Retries / broker failures | Covered — circuit breaker, order-fail streak, fail-closed sizing |
| Reconnects | Partially covered — see gap below |
| VPS recovery | Covered by journal replay + readiness probe |

---

## 1. Kill switch — DEFECT

`kill()` ran `cancel_working_entries()` between the disarm and the square-off with **no
isolation**. That is a broker call, made at the exact moment things are already going wrong.
If it threw:

- the exception propagated to the caller (an API route and a UI button),
- **the square-off never ran**,
- and the operator was left believing they had stopped the bot while positions stayed open
  and unmanaged.

A half-completed kill is worse than an obvious failure, because it looks like success.

**Fixed** (`e273d54`): disarm first and unconditionally — it is the one step that must not
fail, since it is what stops the engine opening *more* positions while someone is trying to
stop it. Cancel and square-off are each isolated, each logging `KILL_PARTIAL` with what was
left undone. A failed square-off says explicitly that the engine is disarmed but positions
may still be open. A failed Telegram notify can never mask a successful kill.

Three of the six tests were red against the old code.

## 2. Duplicate-order prevention — holds

Two guards: `key in held` (one position per instrument) and `signal_already_evaluated` (a
completed bar produces at most one entry decision). Both correct; neither had a test
asserting the property. Now: running the entry path five times on the same signal opens at
most one position, and the ledger still reconciles to the paisa afterwards — a duplicate
that was booked and then rejected would leave cash short.

**Note on method:** the first version of that test synthesised a plausible-looking state
dict and hit `KeyError: 'z'`. `process_entries` reads more of the signal frame than a stub
provides, so the test now drives the real `scan_signals()`. A guard tested against a fake
state shape is not tested against the one it really sees.

## 3. Arm/disarm — holds

Disarmed opens nothing however many times the entry path runs. Worth restating because
ARM's asymmetry is a hard invariant: it gates **entries only, never exits** — the risk loop
marks and fires SL/TP regardless of arm state. Not getting out is worse than any other
failure.

## 4. Reconnects — the remaining gap

`test_kite_provider` covers auth/session handling and the bad-token latch, and the engine
demonstrably survives a token expiry (it latches and probes with one instrument per loop
rather than hammering every name). What is **not** covered is a mid-session WebSocket drop
and re-establish, because the live feed is polled rather than streamed — so there is no
socket to drop. Recorded here so the gap is known rather than assumed closed.

---

## What changed in this audit

1. **Kill switch made best-effort** (§1) — the one real defect.
2. **Duplicate-prevention and arm/disarm invariants asserted** (§2, §3).

## Still open

- A reconnect test would need a streaming feed to exist first (§4).
- The broker's long-lived session (tracked separately) surfaced here too: test fixtures that
  build a `PaperBroker` must close it explicitly or the next `init_db(reset=True)` fails with
  "database is locked" — passing in isolation, failing in the suite.
