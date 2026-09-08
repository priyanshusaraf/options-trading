# 12 — End-to-End Audit Matrix (master checklist)

**Purpose:** every risk class that gates real-money, multi-user operation — each cell names
its evidence state. Nothing may move to LIVE-MONEY READY while any cell is UNPROVEN or RED.
This document drives the remaining sessions; update in place, never rewrite history.

Status vocabulary:
`PROVEN` (named passing adversarial evidence) · `CONTAINED` (fails closed today, full proof
pending) · `UNPROVEN` · `RED` (failing on current bytes) · `NONCLAIM` (deliberately out of
scope, recorded).

## A. State & foundation

| Cell | Status | Evidence / owner |
|---|---|---|
| A1 Supported upgrade path (SQLite 0004→head, genuine states) | PROVEN | `test_foundation_a01_migration_upgrade.py`, mutation-proven |
| A2 Interrupted-stage recovery (0006 additive swap) | PROVEN | mutation-proven this session |
| A3 Staged trigger contracts (0005 install) | PROVEN | mutation-proven |
| A4 Marker dialect contract | PROVEN | A-05 pin |
| A5 Operation-plane legacy migrations (0002/0003 recovery) | RED | 4 failures — forward-replay treatment pending |
| A6 Execution-plane migrations 0035–0039 | PROVEN | suites green (PG harness skips local) |
| A7 Populated-old PostgreSQL upgrade | UNPROVEN | needs disposable-PG harness run (owner infra) |

## B. Concurrency & races

| Cell | Status | Evidence / gap |
|---|---|---|
| B1 Engine lane serialization (signal/risk shared session) | CONTAINED | `_lock` + shutdown-drain fix b243b59 lineage; needs interleaving stress test |
| B2 Sweep workers / dataset store thread safety | PARTIAL | boundary payload test exists; worker-crash reclaim is NONCLAIM `P5-ADV-006-RUNTIME` |
| B3 SQLite locking under API+engine concurrency | PARTIAL | busy_timeout set; no concurrent-writer stress evidence on this tree |
| B4 PG pool sizing + saturation telemetry | UNPROVEN | AWS decision unblocks; not built |
| B5 Two backends, one account (single-instance lock) | **PROVEN** | `test_instance_lock.py` 3/3 on current bytes |
| B6 Authority withdraw mid-tick (stale signal suppression) | PROVEN | L1.4 `_withdraw_superseded_signals` + mutations |

## C. Order lifecycle truth

| Cell | Status | Evidence / gap |
|---|---|---|
| C1 Partial fills, avg price, ack ambiguity | PARTIAL | July H/L series unit coverage; no kill-mid-order integration proof |
| C2 Idempotent placement on retry/restart | UNPROVEN | order-journal exists (H13); replay-on-restart proof stale on this tree |
| C3 Cancel/fill races | PARTIAL | unit-level only |
| C4 Broker reconciliation + drift alarm | CONTAINED | H10 periodic alarm; failed-read≠flat-account C4 fix; needs live-broker rehearsal pre-cutover |
| C5 Protection band / SL-TP on every entry path | PARTIAL | market-protection gated tests exist; futures path OFF by flag |

## D. Real-time data

| Cell | Status | Evidence / gap |
|---|---|---|
| D1 Completed-candle causality | PROVEN | prefix-equality, both strategies + IR |
| D2 Feed anomaly → health propagation | PROVEN | e2e chain fixed this session (`provider_feed`) |
| D3 Provider failure channel (auth latch) | PROVEN | `ProviderReadError` + latch tests |
| D4 WS tick reorder/staleness at scale | UNPROVEN | no load-shape evidence; mock-only so far |

## E. Tenancy & leaks

| Cell | Status | Evidence / gap |
|---|---|---|
| E1 Cross-owner read isolation | CONTAINED→stronger | 26 ordering reds FIXED (genuine-era fixtures); durable-account contract enforced at cockpit/experiment seams; systematic per-route probe still to write |
| E2 WebSocket authz per owner | UNPROVEN | no probe exists |
| E3 Cache/export/dataset isolation | PARTIAL | dataset authority receipts prove refusal chains; export paths unaudited |

## F. Availability & operations

| Cell | Status | Evidence / gap |
|---|---|---|
| F1 Health semantics (public neutral + authed readiness 503-on-fail) | PROVEN | this session, 15 tests |
| F2 Leading saturation indicators (pool util, queue depth) | UNPROVEN | designed (doc 05 D2), not built |
| F3 Deploy path + backup/restore on target infra | UNPROVEN | AWS cutover slice |
| F4 Alert delivery (Telegram) under outage | PARTIAL | free-tier alerts; delivery-loss semantics unstated |

## G. Research integrity (leakage)

| Cell | Status | Evidence / gap |
|---|---|---|
| G1 Strategy causality | PROVEN | prefix-equality guards |
| G2 Backtest fill/slippage/blackout parity | PROVEN | next-open + adverse slippage + shared blackout table |
| G3 Cache-key dimensionality (data+params in key) | **PROVEN** | `test_backtest_identity.py`: every candle/input/source/policy/premium mutation changes the address; phase4 identity adversarially pinned |
| G4 DSR/PBO deflation correctness | **PROVEN** | var_sr threaded through optimize→scorecard; `test_deflation_engages.py` pins the exact historical bug shape (12 tests) |
| G5 Survivorship disclosure completeness | **PROVEN** | buckets are disjoint SQL predicates; payload test now pins all three buckets + visible+skipped==total identity |

## Rule going forward

Every session appends its findings here and to `devops-log.md`. A cell moves to PROVEN only
with a named command + output on current bytes. RED cells block the phase gate; UNPROVEN
cells block LIVE-MONEY regardless of green tests elsewhere.
