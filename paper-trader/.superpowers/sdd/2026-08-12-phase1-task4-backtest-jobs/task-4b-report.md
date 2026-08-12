# Phase 1 Task 4B — Durable Sweep Claims and Bounded Admission

Status: implementation complete; final independent review remains pending.

Final hardening after the first review:

- Removed the unfenced repository-level `reconcile_stale_runs` mutator. Recovery now
  changes only expired leases (or historical claimless rows), while release, cancellation,
  result persistence and terminal transitions stay claim-token fenced.
- A cancellation observed during descriptor/provider/universe resolution, whether after a
  restart claim or a fresh `start_sweep` claim, now becomes the token-aware `cancelled`
  terminal state before any worker thread starts. It cannot be dispatched again or be
  converted into an error by the resolution exception path.
- Parallel gauges are keyed by owner and run in production. Their process-pool and
  in-flight values are cleared in `finally` for ordinary exceptions and a lost claim,
  without overwriting another same-owner run's gauges.
- A successful `0026 -> 0025` downgrade removes its empty recovery-proof table and the
  resulting backtest table/index contract matches a clean 0025 database exactly.

Final focused evidence:

- `backend/.venv/bin/python -m pytest -q` over the six new fencing, cancellation,
  gauge and migration cases: `6 passed`.
- `backend/.venv/bin/python -m py_compile app/backtest/repository.py
  app/backtest/sweep.py migrations/versions/20260812_0026_backtest_resume_cells.py`
  and `git diff --check`: pass.

Delivered:

- Revision `0025` adds durable queue, claim, heartbeat, attempt, cancellation and requested-worker fields to `backtest_runs`, with owner/status/queue and lease-expiry indexes.
- The SQLite migration rebuild is based on the accepted `0024` source-bound, target-manifest proof/recovery pattern. It preserves 0024 evidence bytes, restores caller FK mode, recovers proved promotion, refuses unproved source-absent temps and refuses downgrade after durable claim state has been recorded.
- `app.backtest.repository` exposes explicit-owner enqueue, atomic pending/expired claim, heartbeat, token-fenced batch persistence, terminal transitions, owner cancellation and expired-only reconciliation. The token is never an API response.
- `sweep.start_sweep` reserves admission and creates/claims the durable run in one SQLite `BEGIN IMMEDIATE` transaction. Local worker threads are an owner/run-keyed registry for observation and joins only; they do not decide admission. Workers receive the owner and claim token, and no stale/replaced/cancelled claimant can write results or a terminal state.
- Admission is defined by measured workload budget configuration: active jobs, owner active/queued jobs, requested cells and requested worker slots. It contains no product user-count constant and rejects before provider data reads or worker launch.
- Backtest status remains owner-local and now reports timing/cancellation/attempt metadata. The owner-local cancel endpoint collapses foreign and absent IDs to the same response.

Red/green evidence:

- Initial claim tests failed with absent durable repository APIs.
- Initial sweep admission test failed at the old process-global `_running` refusal.
- Initial zero-capacity test reached a provider path because there was no workload admission check.
- After implementation, `backend/.venv/bin/python -m pytest -q backend/tests/test_backtest_job_claims.py --tb=short` reported `9 passed`.
- `backend/.venv/bin/python -m pytest -q backend/tests/test_schema_migrations.py -k '0025 or models_and_migrations_agree' --tb=short` reported `13 passed`: populated parity, downgrade safety, FK modes, forged/unproved temp refusal, promoted recovery, all four durable upgrade interruption phases, and row/schema tamper refusal.
- Full migration suite: JUnit `221 passed, 0 failures, 0 errors` in 112.697s.
- Affected backtest gate (batch persistence, parallel, pinned and pinned-worker, tenant isolation and durable jobs): JUnit `67 passed, 0 failures, 0 errors` in 57.641s.
- Targeted compile and `git diff --check` passed.

Mutation evidence:

- Replacing the active-claim token equality predicate with `claim_token IS NOT NULL` made the stale-worker fencing test fail: the old claim appended a result after a replacement claim. The equality predicate was restored.

Scope:

- No protected broker files were edited or staged.
- No frontend and no PostgreSQL switch were introduced; the repository seam and portable fields are prepared for the Phase 2 PostgreSQL worker implementation.
