# ADR 0014: SQLite stays until topology forces Postgres, not until headcount does

- **Status:** **ACCEPTED (2026-08-10).** Verdict is **DEFER the migration, KEEP + HARDEN the
  seam.** One bounded correction is approved and is not the migration itself.
- **Date:** 2026-08-10
- **Owners:** WS-07 infrastructure, WS-06 deployment
- **Question asked:** with a 500-user target, does Postgres now make sense — for efficiency and
  for better deployment options?
- **Depends on:** the 500-user correction in
  `superpowers/specs/2026-08-09-scale-and-cost-corrections-design.md`
- **Prior art, both consulted rather than redone:**
  `reference/architecture-extension-review-2026-08-07.md` §"DB contention" — *"SQLite is
  plausible at 100 users with WAL if writes stay short… Do not migrate speculatively. The
  trigger is a measured lock-wait, not a headcount."* And
  `reference/codex-supervisor-review-2026-08-09.md` §4 — *"Move to Postgres and isolated workers
  when multi-user execution or multiple app replicas become real, not before."*

---

## 1. The verdict, and the reason it is not about scale

**DEFER.** The disqualifying condition for SQLite is **topology, not user count**.

SQLite has no network protocol. It is an in-process library over a local file, so every writer
must be a process on the same host, and multi-host file locking over NFS is famously unreliable.
The moment execution workers span two hosts — which the roadmap wants for *failure isolation*,
not throughput — SQLite is disqualified outright. That is a hard boundary and it is a decision
made when multi-host is built, not in advance of it.

Below that boundary, 500 users is not obviously a problem. In WAL mode SQLite serialises writers
but does not block readers, and this system's write path is narrow: the engine writes a handful
of rows per tick, and users mostly read. The 2026-07-23 outage was full-table ORM scans and a
WebSocket leak — application-level, already fixed, and Postgres would not have prevented either.

## 2. What the migration actually costs here

This is not "change one URL". The SQLite-specific surface, counted:

| Surface | Extent | Why it matters |
|---|---|---|
| Immutability triggers using `RAISE(ABORT, …)` | **~18 DDL statements** across `db/models.py` and 4 migrations | **SQLite-only syntax.** Postgres needs PL/pgSQL trigger functions with `RAISE EXCEPTION`. These enforce invariants, not conveniences — `execution_order_events` (append-only, on the **live order path**), `graph_versions` (immutable executable versions, an RFC invariant), `project_review_snapshots`, product objects |
| `PRAGMA` setup | 4 (`foreign_keys`, `journal_mode=WAL`, `synchronous`, `busy_timeout`) | No translation; Postgres handles this natively. An *argument for* Postgres, not against |
| Hardcoded engine URL | `session.py:14`, `f"sqlite:///{db_path}"` | Trivial, but it is what makes a switch untestable today |
| Alembic revisions | 14, head `0014` | Structure is portable; the raw DDL inside several of them is not |
| File-level operations | `.db.lock` flock (the C7 single-instance guard), `.db.predeploy-*` backup/restore in `deploy.sh`, `prune_db.py` VACUUM, four rsync exclude patterns | All disappear or become different operations. `deploy.sh`'s single-instance guard in particular is a *file* lock; the Postgres equivalent is an advisory lock or a lease, which is a different design |

The triggers are the real cost, and they are the one line item whose cost **grows with delay** —
every new immutable entity adds more SQLite-only DDL.

## 3. Invariants in the blast radius

- **Language — "immutable executable graph versions."** Enforced by `graph_versions` triggers.
  A port must reproduce refusal at the database, not in application code, or the invariant
  degrades from *enforced* to *intended*.
- **Authority — append-only execution events.** `execution_order_events` triggers are new
  (migration `0014`, phase 1) and sit on the live order path.
- **Money — paper/live book separation.** Columns plus CHECK constraints; portable as-is.
- **Delivery — "deploys go only through `scripts/deploy.sh`."** Its DB handling is entirely
  file-based today.

None of these *forbids* Postgres. All of them mean the port is a reviewed slice with its own
proofs, not a config change.

## 4. Sequencing: doing it now means paying twice

Tenancy (phase 10) adds an owner dimension to **every** resource — projects, graphs,
deployments, research, caches — plus durable encrypted broker connections and accounts, with a
backfill of every existing row. That is the largest schema change still ahead.

Migrating engines *before* that means porting a schema that is about to change fundamentally,
then porting again. Iterating the tenancy schema is far cheaper in SQLite, where a migration is
a local file operation.

## 5. Honest arguments on the other side

Recorded so this is a judgement, not a reflex:

- **Managed Postgres is genuinely better ops.** Backups, PITR, failover and replicas stop being
  `deploy.sh`'s problem. That is real, and it is the strongest form of the "better deployment
  options" argument. It costs roughly $15–60/month and is worth paying *when there is something
  to fail over to.*
- **Concurrency headroom.** MVCC removes the single-writer ceiling. This was the one result
  that could have overturned the ADR on efficiency grounds alone, and it has now been
  **measured (`c47acc9`) — it does not.** With batched writes, one SQLite writer in WAL mode
  persists **16,000 rows in 2.64 s (6,056 rows/s)** and **50,000 rows in 9.69 s**, at
  1.5–1.9 ms/transaction. Against ~22 minutes of compute for the same workload, persistence is
  0.2% of the run. (Unbatched, one row per transaction, the same tiers cost 11.99 s and 54.02 s —
  still not a ceiling, which is why batching was worth doing on its own merits rather than as
  Postgres preparation.)
- **It is not free on latency.** SQLite is in-process; Postgres adds a network round-trip per
  query. For the risk loop, which issues many small reads per tick, a migration makes the live
  path *slower*, not faster. "More efficient" is not unconditionally true and should not be
  assumed.

## 6. The approved correction — seam only

Cheap now, expensive later, and explicitly **not** the migration:

1. **Make the engine URL configuration-driven** rather than hardcoded `sqlite:///`, keeping
   SQLite as the default and the PRAGMA hook SQLite-conditional. Two-line change; it is what
   makes a future port testable instead of theoretical.
2. **Route immutability triggers through one helper** that emits dialect-appropriate DDL, so new
   immutable entities stop adding raw `RAISE(ABORT)`. This caps the growing cost. The helper
   must keep emitting byte-identical SQLite DDL today — proven by the existing immutability
   tests going red if refusal stops working.

Neither changes runtime behaviour. Both are refused if they alter a single emitted statement on
SQLite.

## 7. What would overturn this

Any one of these, and the answer changes:

- Execution is decided to run on **more than one host** (failover, or account-isolated workers
  spread for resilience). This is the primary trigger and it is a topology decision.
- A **measured** lock-wait ceiling — `busy_timeout=10000` actually being reached under real load
  rather than in theory. ~~Write throughput~~ is **settled**: see §5, SQLite sustains the
  50,000-row tier with room to spare, so this trigger is now only about *contention*, not volume.
- Tenancy lands and the schema settles, at which point the port is a normal slice against a
  stable shape.
- More than one application replica is needed for availability.

Until one of those is true, the honest answer to "should we move to Postgres" is: **not yet, and
the trigger is a measurement or a topology decision — not the number 500.**
