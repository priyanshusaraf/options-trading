# 04 — Way Forward: Fastest Safe Path to Phase 5 and Phase 6

**Objective (yours):** solidify every overlooked foundation item, kill user-facing performance
bugs, keep security gates at maximum rigor, and *accelerate*. This document is the sequencing.

## 0. The order of operations

```
NOW        Stabilize: commit the tree; restore suite collectability
T+1–3d     A-02 boolean-ingress fix          (small, dangerous, fully specified)
T+2–7d     Owner decision: narrow migration contract
T+3–10d    A-01 migration fix + repo-native evidence replacement (Steps 2/4 of doc 03)
T+7–14d    Recheck FND-05/06/12 → Phase 5 gate opens
PARALLEL   Phase 5 capsules begin on disjoint surfaces while closure finishes
```

Nothing above requires Recovery 9 to converge. If Recovery 9's consolidated repair lands first and
passes, fold it in; if it fails, the reserved successor is *not activated in-form* — the split
harness from doc 03 §4 replaces it.

## 1. Stabilization details (do first, this week)

1. **Commit per capsule to `codex/execution-foundation`.** The capsule boundary is the natural
   commit boundary: capsule accepted → commit. This restores the governance system's own premise
   (repo + capsule + evidence = handoff) and makes every SHA-pinned evidence file git-protected.
   374 dirty entries is one `git checkout -- .` away from catastrophe, and agents in this repo are
   explicitly authorized to run tree-mutating git commands in other contexts.
2. **Quarantine or finish the two collection breakers** (`DeclaredNativeAdapter` import;
   `phase3_causal_gate` shard drift). If they belong to an unfinished capsule, finish it; if they
   are orphaned edits from a stopped owner, revert them deliberately and record the disposition.
3. **Tag the current state** (`git tag pre-phase5-foundation` or similar) after the commit sweep so
   the audit's frozen hashes and the tree state become jointly reproducible forever.

## 2. Phase 5 readiness — what actually gates it

From the master sequence and the audit: Phase 5 requires the foundation closure, nothing more.
Phase 5 itself (first-party language + scalable research) decomposes cleanly into **parallel
capsules** — the policies already allow up to 4 children with disjoint write ownership:

| Capsule | Surface | Reference repos (see doc 07) |
|---|---|---|
| Node library breadth — indicators | `app/ir/library.py` contributors, vector/streaming kernels | `nautilus_trader`, `vectorbt` (reference only), `comfyui` registry shape |
| Node library breadth — logic/state/execution-intent | same seam | `node-red` semantics, `langflow` component model |
| Conformance harness (one shared) | tests/ under CI | your own provider-conformance contract (Aug 9) is the template |
| Content-addressed datasets | dataset store identity | `dvc-data` object layout |
| Bounded parallel sweeps + measured tiers | backtest sweep | `optuna` storage shape; your G-3 job/worker boundary |

The five visible node families stay the product surface; platform layers stay hidden (global
constraint) — the library work is breadth *within* the existing IR, which is exactly what the
architecture review said was safe to extend.

## 3. Performance work — the user-facing bugs, in priority order

The measured facts (from the Aug 8 hardening record) plus the AWS decision change the calculus:

1. **Connection pool is now unblocked.** The only reason pool sizing was deferred was the 1 GB
   droplet OOM history. On AWS: set `pool_size`/`max_overflow` explicitly from a load test, add
   `statement_timeout`, and — most important — **report pool utilization on `/api/health`** so
   saturation is visible *before* it is total (the audit's named missing leading indicator).
2. **Bound every read at both layers** (query + request) — the `recent_trades` pattern. Sweep for
   siblings: any route that filters in Python after an unbounded SELECT. The hardening record fixed
   one; the pattern class should be closed with a test that fails on any new unbounded read.
3. **Backtest performance baseline** (~100 securities × 5 timeframes + parameter variation) —
   already on the agenda; profile before optimizing, per the house rule. `vectorbt`'s vectorization
   *patterns* (not code — Commons Clause) are the reference for the sweep inner loop.
4. **WS feed hygiene** — the July hardening already offloaded per-tick work off the event loop;
   keep that invariant when Phase 5 adds subscriptions.

## 4. Capacity transparency — your "10 API calls/sec" requirement

This is the requirement: *if the interface cannot deliver what a strategy needs, the user knows
before activation, not after a timeout.* It maps onto machinery that already exists in design:

- `app/providers/capabilities.py` already declares per-connection capability vocabularies.
- Phase 6 preflight already plans receipts that refuse activation with exact block reasons.

**Recommendation: pull a minimal slice of that forward into Phase 5** as a read-only
*capacity receipt*: every provider connection declares its measured rate budget; every strategy
declares (or gets measured on) its required call rate per interval; the deployment preview
computes `required ≤ available` and renders a loud degraded/blocked state with exact numbers when
false. No enforcement authority changes — it is an admission *surface*, consistent with "causal
admission is necessary but never sufficient". Client-side: `aiolimiter`-style token buckets at the
adapter seam (MIT, tiny) make the budget enforceable rather than advisory.

## 5. Speed levers (what to change in the operating model)

1. **Commit-per-capsule** (above) — removes the audit-hash drift problem and makes every review
   diff reviewable.
2. **Parallel capsules with disjoint ownership** for Phase 5 breadth — the policies permit it;
   the serial chain was right for authority work and is wrong for node-library breadth.
3. **Pre-build review packages during implementation**, not after freeze — several review FAILs
   were packaging/evidence-shape failures (DP-016 class). Building the package alongside the code
   converts review round-trips from days to hours.
4. **Stop re-proving settled invariants.** The 29 RFC clauses have permanent tests. New capsules
   should *reference* those guards, not re-derive them. The transitive-invalidation map is the
   tool for deciding when re-proof is actually required.
5. **Timebox evidence-only children** and prefer one independent consumer test over five
   attestation documents (DP-003's own rule).
6. **Keep the review rigor exactly as-is for authority/money surfaces.** The speedup comes from
   scope discipline and parallelism, not from thinner reviews. The immutable-verdict +
   bounded-correction loop converged Phase 3 and Phase 4; it works.

## 6. What "done" looks like for this phase

- [ ] Tree committed; suite collects; full suite green on committed bytes
- [ ] A-01 fixed with per-stage contract validation + permanent regression in CI
- [ ] A-02 fixed with full-chain bool refusal + mutation-killed guard
- [ ] Migration contract narrowed by owner decision, documented, refusal paths tested
- [ ] FND-05/06/12 recheck PASS at narrowed scope → Phase 5 gate open
- [ ] Pool sized + saturation telemetry live in dev profile
- [ ] Capacity receipt surface specced (implementation may land in Phase 5/6)
