Reference: [section index](../codex-supervisor-review-2026-08-09.md). Read with its scope; this is not a new assignment.

# Strategy OS supervisor review: architecture baseline and living checkpoints

**Review date:** 2026-08-09\
**Repository reviewed:** `/Users/priyanshusaraf/dev/options-trading`\
**Branch and commit:** `feat/exec-completeness` at `1ccb9d4de3640889f3b583f4424291028aed03a0`\
**Worktree state at review:** clean and equal to `origin/feat/exec-completeness`\
**Role:** product, architecture, engineering, execution-safety, research-integrity, and commercial-readiness supervisor\
**Decision rule:** reject a claim until code, persistence, tests, or measured behaviour proves it.

## Living checkpoint — 2026-08-09, `codex/execution-foundation` at `1e96b52`

The review metadata above and Sections 1–15 below are the historical baseline from
`feat/exec-completeness` at `1ccb9d4`. They remain intact because they record the evidence and
reasoning that selected the execution-first work. They are not a current-state report by
themselves. This checkpoint records what changed after that review and rejects superseded claims.

**Repository state:** the source revision is `1e96b52` before this documentation update; the
branch is not pushed or deployed. The current branch-wide gate collected 3,712 backend/research
tests: 3,706 passed and 6 expected skips. The frontend passed 223/223 tests, TypeScript checking,
and its production build. The deterministic dry run ended `LEDGER OK`; the backtest smoke
completed 16/16 cells with `SWEEP OK`; migration head remains `0014`; no live broker call or
deployment occurred.

### Current implementation delta

1. **Durable live-entry lifecycle is implemented and branch-wide verified through `9827e23`.**
   Migration `0014` adds immutable entry intents and observations. Live entry intent and
   `SUBMIT_STARTED` commit before submit; recovery scopes unresolved entries by deployment,
   account, and `kite:legacy` connection; cumulative observations book positive fill deltas only;
   protection acknowledgement and protected quantity must become durable before the booked
   watermark clears reconciliation; telemetry derives latency and adverse slippage from persisted
   facts. Legacy entry journal rows remain recoverable. Existing exits remain on the legacy
   market-order journal path.
2. **Configurable live entry order selection is implemented and branch-wide verified.**
   `f48beec` defines the approved policy, `5b3ac76` adds the closed `AUTO | MARKET | LIMIT`
   setting, `11d1db4` separates order purpose (`ENTRY | EXIT`) from side (`BUY | SELL`), and
   `1e96b52` routes effective MARKET or LIMIT instructions through live option/equity entries.
   Venue-tick normalization occurs before `ExecutionIntent` freezes `order_type` and
   `limit_price`; unresolved LIMIT orders are not repriced or resubmitted automatically.
3. **Paper/backtest LIMIT parity is still open.** `PaperBroker` accepts the live planner shape
   for interface compatibility, but paper execution does not simulate resting-limit touch,
   penetration, time-in-force, price improvement, or non-fill. The backtester remains a
   next-bar-open market-fill model with adverse cost. Cache identity does not yet include a
   versioned limit-fill model. A MARKET/LIMIT control in the live path is not evidence that paper
   or backtest results model that control.
4. **Exit routing has not changed.** Exits retain their legacy journal/recovery path and use
   market orders for risk reduction. Limit exits require a separate safety design and are not
   part of the configurable-entry slice.

### Current phase verdict

| Area | Verdict at this checkpoint | Evidence ceiling |
|---|---|---|
| Durable live entries, recovery, protection, telemetry | **COMPLETE through `9827e23`** | Entry-only; no claim about migrated exits or deployment. |
| Configurable live MARKET/LIMIT entries | **COMPLETE WITHIN THE LIVE-ENTRY SCOPE** | Backend/research, frontend, typecheck/build, ledger dry run, and sweep smoke pass. Paper/backtest LIMIT parity and release/deployment remain outside this claim. |
| Causal strategy admission | **PARTIAL** | Prefix causality and mutation tests exist; closed causal declarations and admission/runtime parity remain. |
| Content-addressed backtest cache | **CLAIM REJECTED** | Last-timestamp reuse is not candle-content identity; strategy/cost identity and complete cached artifacts remain open. |
| 100 × 5 performance | **UNPROVEN** | No operation-budget or full workload percentile gate. |
| Separate data and execution connections | **PARTIAL SEAM** | Capability tests exist; runtime still composes execution from one provider. |
| 100-user deployment | **NOT READY** | Current guarded single-owner VPS topology is not an account-worker topology. |
| Novice research product | **PARTIAL** | Existing frontend is substantial; guided novice journey and usability evidence remain open. |
| Additional brokers | **DEFERRED** | No second adapter should precede role composition. |
| Customer auth and tenancy | **DEFERRED; COMMERCIAL BLOCKER** | Single-owner bearer-token principal seam only. |

### Superseded and rejected claims

- The historical F-04 claim that a live entry can proceed without durable intent is fixed for the
  new live-entry path through `9827e23`. It remains historical evidence, not current truth.
- The historical F-05 claim that new-entry recovery is wholly unscoped is fixed for deployment,
  account, and connection in the new lifecycle. Exits and other legacy journal paths are not
  promoted to the new lifecycle by that fix.
- The historical “no immutable order/fill history” statement is now too broad. Immutable order
  observations and durable fill progress exist. A separate immutable broker-execution `Fill`
  entity and multi-leg allocation model still do not.
- “Configurable order modes are complete across live, paper, and backtest” is rejected. The
  verified slice controls live entries only.
- “Paper and backtest results reflect LIMIT execution” is rejected. They do not yet.
- “The application is ready for 100 users because a single-user deploy script exists” is
  rejected. Deploy mechanics and multi-account execution topology are different claims.
- “A second-broker-shaped capability test proves split data/execution runtime composition” is
  rejected. It proves only that shared gates no longer branch on the Kite name.

### Deployment direction without a readiness claim

The accepted path to roughly 100 users is a shared control plane plus account-isolated execution
workers, initially no more than five active accounts per worker and at least two hosts. Required
proof includes a 50-account soak, duplicate-worker fencing, crash recovery, token expiry, broker
throttling, restore, failover, and measured latency/RPO/RTO.

At roughly 1,000 users, bounded execution cells add versioned placement, resource limits,
primary/standby assignment, consistent account routing, PostgreSQL work ownership, leases, and
fencing. A message bus is justified only for notification fan-out and cache invalidation after
measurement. Per-user VPSs remain optional premium isolation. None of this topology is currently
implemented or load-proven.

The current next gates are causal admission, correct cache identity, measured 100 × 5 operation
budgets, explicit data/execution/account role bindings, and the 100-user worker/fencing soak.
Additional brokers and commercial tenancy remain deferred until those foundations exist.
