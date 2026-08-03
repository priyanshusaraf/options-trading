# ADR 0005: Research operations use an atomic current/last receipt

- **Status:** Accepted for S4.4
- **Date:** 2026-08-03
- **Owners:** WS-03 Research with WS-07 operational persistence and WS-08 surface
- **Depends on:** ADR 0002 graph research binding, ADR 0003 evidence, ADR 0004 findings

## Context

`python -m research.nightly` enforces isolation, builds a bounded server-owned plan, collects data,
runs baseline experiments, explores generated strategies and writes reports. The module docstring
claims it runs under a lockfile, but no lock is acquired. Only successful/started experiments leave
rows. A zero-plan attempt, plan/collection failure, generation failure, overlapping invocation or
process interruption has no durable status. Operators must infer scheduler health from logs.

`ExperimentRun` is the evidence ledger for one immutable ExperimentSpec. It cannot truthfully
represent an enclosing scheduler attempt before a spec exists or after all experiments finish.

## Rejected approaches

| Approach | Reason rejected |
|---|---|
| Create a fake ExperimentSpec/Run for the scheduler | It pollutes research evidence and gives a non-experiment an executable recipe identity. |
| Add operation fields to ResearchProgram or Finding | Those objects have different identities and lifecycles. |
| Add an operation SQL table in S4.4 | The required state is one active/last operational receipt, including failures before DB setup. Introducing a second Alembic track for research.db is disproportionate here. History can migrate later without changing the receipt contract. |
| Treat report files or process logs as status | They are absent on early failure, unbounded, not canonical and not an API contract. |
| Accept a plan or provider payload through HTTP | It creates a remote arbitrary-work surface and lets clients claim executable/data identity. |
| Record exception strings or tracebacks | They can contain credentials, paths or provider payloads and are not stable product feedback. |
| Use only an in-process mutex | Cron/manual processes can overlap and restart loses state. |

## Decision

### Persistence and identity

One configured JSON receipt file, defaulting beside `research.db`, stores:

```json
{
  "schema_version": 1,
  "content_address": "sha256:...",
  "operations": {"active": null, "last": {"...": "..."}}
}
```

The address is derived from canonical `operations`. Writes use a mode-0600 temporary file, flush,
`fsync` and atomic `os.replace`. Reads require the exact closed envelope, canonical bytes and valid
address. Corrupt state fails closed; it is never rendered as “no attempt”. The file is operational
status, not experiment evidence or long-term audit history.

Each server-created operation records:

- opaque server id, trigger (`nightly` or `manual_script`), build and provider mode;
- started/completed timestamps and `running | completed | failed` state;
- current stage from a closed vocabulary;
- canonical server plan address plus bounded safe plan summary (program/hypothesis/strategy,
  instrument keys, interval, days and optimize flag);
- completed ExperimentRun ids and counts;
- stable failure stage/code/message, never traceback or arbitrary exception/provider data.

Dataset identities and statistical outcomes remain in each linked ExperimentRun evidence envelope.
The operation receipt references run ids; it does not copy or weaken that ledger.

### Concurrency and interruption

Nightly and the manual script acquire the same non-blocking OS file lock for the entire operation.
If held, the second invocation exits non-zero with a stable `RESEARCH_OPERATION_ALREADY_RUNNING`
message and does not mutate the active receipt. This makes the existing lockfile claim real.

When a process obtains the lock and finds a persisted `active=running` receipt, the prior process is
no longer holding the lock. It atomically converts that stale operation to `last=failed` with
`RESEARCH_OPERATION_INTERRUPTED`, then starts the new active receipt. Completion/failure atomically
moves active to last. At most one active and one last receipt exist.

### Integration

Isolation guards and the disabled freeze gate remain before receipt mutation. An enabled operation
starts after the lock is acquired. Nightly derives the plan and provider mode; the manual script uses
its bounded code-owned plan. Neither accepts HTTP plan input.

`run_nightly` receives an optional progress callback after each committed experiment so the receipt
can expose run ids without changing pipeline semantics. Generation reports update through the same
bounded receipt integration.

A closed read-only status API exposes verified current/last state and is mirrored under `/api/v1`.
There is no HTTP start/cancel/retry/plan endpoint in S4.4. The product surface shows stage, plan
summary, completed runs and safe failure feedback.

## Rollback

No database schema changes. Reverting code leaves one unused JSON receipt and lock file beside the
research database. Removing them is optional and recoverable; experiment/finding/candidate rows are
unchanged.

## Guard proofs

S4.4 must prove:

1. two processes cannot own an operation concurrently;
2. a stale active receipt becomes interrupted only after the new process owns the lock;
3. raw plan/provider/error/evidence input has no HTTP route;
4. receipt corruption/address mismatch fails closed rather than appearing empty;
5. reads perform no provider, planner, orchestrator, evaluator, gate or execution action;
6. failure stages persist stable bounded feedback without exception secrets;
7. successful mock nightly reloads the same plan address and linked run ids;
8. research isolation guards still reject execution DB alias and live execution before status writes.

## Boundary

S4.4 adds observability and real overlap exclusion. It does not add a scheduler daemon, remote run
control, arbitrary plans, credentials, dataset ingestion policy, execution, deployment, arming,
orders, Python input or live IR-runtime adoption.
