# Strategy OS deployment contract

Use the smallest applicable subset, but account for every affected row.

| Dimension | Required evidence when affected |
| --- | --- |
| Build | Reproducible backend/frontend artifacts; pinned runtime and installable dependencies; exact build identity. |
| Configuration | Environment-backed secrets; validated required variables; safe defaults; production refuses SQLite and mock/live ambiguity. |
| PostgreSQL | Supported major and driver; separate execution, research, and ledger schemas; least-privilege roles; aggregate engine/process connection budget; effective workload-specific statement/lock/idle-transaction bounds and TLS policy. |
| Migrations | Empty install and supported upgrade path reach exact heads; restart is idempotent; partial/stale schemas fail closed. |
| Data cutover | Frozen-source copy rehearsal, content-addressed report, row/PK/digest/sequence checks, credential-key readiness, and quarantined failures. |
| Backup/restore | PostgreSQL 16 tools preserve configured transport/TLS policy; signed manifest, encrypted retained artifact plan, clean-target restore, current-schema verification, and recovery time measured at representative retained volume. |
| Services | Explicit API/worker/scheduler/research roles; dependency ordering; restart policy; single-writer or lease semantics; graceful shutdown. |
| Health | Readiness checks database, schema head, engine lanes, provider state, build identity, and frontend availability without reporting false green. |
| Security | No static credentials; network exposure, TLS, database roles, host permissions, secret rotation, and audit trail are specified and tested proportionally. |
| Observability | Structured logs, bounded retention, metrics, alerts, job/lease visibility, database capacity, backup age, and failure diagnostics. |
| Capacity | CPU, memory, disk, connection, subscription, queue, cache, and data-retention budgets have tested ceilings and degradation behavior. |
| Rollout/rollback | Maintenance window, preflight, dry run, rollback trigger, old-authority preservation, forward-repair policy, and post-deploy smoke evidence. |

## Evidence levels

- `locally_runnable`: isolated non-production runtime starts and focused behavior passes.
- `release_deployable`: clean artifact, install, configuration, migration, health, and rollback paths pass in a production-shaped environment.
- `production_rehearsed`: restored production-like data and topology complete cutover, restore, failure, capacity, and rollback rehearsals with recorded RPO/RTO where claimed.
- `deployed`: the sanctioned exact-head deployment completed and post-deploy checks bind the running build. This level always requires the owner gate.

## Ownership

Assign each affected requirement to the current workstream and release decision.
Use WORKING-PLAN.md and the accepted capability scope; old phase numbers do not
postpone a current V0 obligation. Record a named owner, verification and trigger
for later work instead of assigning every operational gap to a future phase.

Local PostgreSQL or Compose proves a development substrate only. Managed PITR, VPS topology, production credentials, real-data cutover, external TLS, and live provider behavior remain unproven until their named rehearsals run.
