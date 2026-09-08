# 05 — Architecture Decisions: AWS Scale-Up, Performance, Reliability, Durable Jobs

**Context:** the owner has confirmed infrastructure scale-up — AWS for client deployment,
droplet not a constraint, whichever service fits best. This removes the standing deferral on
several decisions and creates new ones. Each decision below states: choice, rationale, and what
must be true before it counts as made.

## D1 — Target production topology: PostgreSQL-only, containers, managed

- **Choice:** production = PostgreSQL 16 (already built: three plane profiles, cutover copy,
  restore proof in Phase 2), app tier containerized, deployed on AWS via ECS/Fargate or EKS
  depending on operational appetite; RDS Postgres for data; ALB + TLS at edge.
- **Rationale:** Phase 2 already did the hard part (dual-dialect semantics, timezone/JSON parity,
  verified copy/restore). The droplet's SQLite dev profile remains for local development only.
- **Before it counts:** a deployability capsule that proves image build → migrate → health-check →
  rollback on disposable AWS-shaped infra; secrets via AWS-managed secret store, never env files in
  images; `deploy.sh` remains the only sanctioned path until explicitly superseded by an owner-gated
  replacement.
- **Nonclaim to preserve:** nothing is deployed today from either branch; the live bot on the
  droplet runs older code. Cutover is its own owner-gated slice with reconciliation evidence.

## D2 — Concurrency model: fix the pool deliberately, add leading indicators

The measured cliff (40 anyio workers vs default 15 connections; failures once holds ≳4s) was left
unfixed *only* because of the 1 GB droplet. Now:

- Set `pool_size` / `max_overflow` explicitly from a measured load profile, not defaults.
- Add `statement_timeout` per connection so no query can hold a slot indefinitely.
- **Saturation telemetry on `/api/health`**: pool in-use/idle/waiting counts. The audit named the
  missing leading indicator; this is the fix. Health stays honest (503 on total exhaustion) but now
  degrades *visibly* first.
- Request-level deadlines: every route gets a budget; on breach, return a structured degraded
  response — never a silent hang. This is the "no request timeouts without users knowing"
  requirement at the transport layer.

## D3 — Backpressure and rate limiting: adaptive limits at two seams

Your requirement — a strategy needing 10 calls/sec must be told upfront if we can't serve it —
needs both *admission-time truth* and *runtime enforcement*:

- **Admission time (Phase 5 slice):** capacity receipts (doc 04 §4) — required-vs-available call
  rates computed at deployment preview; loud blocked/degraded states with exact numbers.
- **Runtime:** token buckets per provider connection (`aiolimiter` pattern, MIT) at the adapter
  seam; adaptive concurrency limits between services using the Netflix `concurrency-limits`
  algorithms (Gradient2/Vegas — Apache-2.0, portable concepts). Circuit breakers around broker and
  data calls with half-open probes; state surfaced on health and cockpit.
- **Load shedding policy, stated openly:** under saturation, shed *research/backtest* work before
  *live signal loops*, and never shed exits (house invariant: ARM gates entries only). Priority
  classes belong in the job/worker boundary Phase 2 started.

## D4 — Durable orchestration: adopt patterns, don't build a second engine

Phase 2 built durable sweep jobs, worker fencing, reclaim authority, exactly-once ambitions.
`dbos-transact-py` (MIT, already cloned) is essentially the spec: workflows checkpointed in
Postgres, queues, recovery, no external broker. Recommendations:

- Keep your own typed authority/receipt machinery (it is better than anything off the shelf for
  your domain); borrow DBOS's *mechanics*: checkpoint-before-effect, idempotency keys, queue-based
  concurrency caps, recovery-on-restart semantics.
- Do not adopt Temporal/Kafka/NATS now — the repo has twice (correctly) rejected message-bus
  infrastructure until scale demands it. Revisit at multi-region or >1 worker-pool scale.

## D5 — Migration integrity: mechanize A-01's prevention invariant

- Add a CI gate that lints every migration for *complete contract installation*: tables, indexes,
  constraints, triggers, marker — validated by actually applying each migration to a fixture and
  diffing the full schema contract (`ariga/atlas`'s lint approach, Apache-2.0 — inspect its checks;
  adoption mode: CLI reference or wrapped tool, not vendored code).
- Per-stage validation inside migrations themselves (the A-01 fix) so even out-of-CI execution
  cannot advance on an incomplete contract.
- For zero-downtime PostgreSQL changes later: `xataio/pgroll`'s expand/contract pattern (Apache-2.0)
  as the reference shape.

## D6 — Tenancy authorization: stay with owner-scoped queries; keep openfga in reserve

Phase 1's owner/account scoping covers current needs. Zanzibar-style fine-grained authz
(`openfga`, already cloned with sample multi-tenant stores) becomes relevant when sharing rules
appear (teams, strategy-IP sharing in Phase 8–10). Adopting it early would add a second authority
system — against the house rule. Record as a named future decision, revisit at Phase 8.

## D7 — Node editor substrate: buy the rendering, build the semantics

- `xyflow` (MIT) as the canvas substrate — the library ledger already calls this "a buy, not a
  build".
- Study `langflow` for component→JSON→runtime round-trip discipline and `comfyui` for typed node
  registries where custom nodes are indistinguishable from built-ins (your C13 goal).
- `superalgos` (Apache-2.0) is direct product prior art — mine its UX flows, not its code tangle.
- Your semantic layer (IR v2 Ports, admission, preflight) has no equivalent anywhere; that part
  stays yours.

## D8 — Observability: structured, proportional

Prometheus client + Grafana for the metrics above (pool, queue depth, provider budgets, loop
liveness — the watchdog exists since July), structured logs with request IDs, and the existing
Telegram alerting kept for operator paging. No distributed tracing until there are ≥2 moving
production services; then OpenTelemetry.

## Decision log format going forward

Each of these should land as a short ADR in `docs/engineering/decisions/` when activated, per the
existing convention — one page: choice, evidence, nonclaims, owner gate touched (if any).
