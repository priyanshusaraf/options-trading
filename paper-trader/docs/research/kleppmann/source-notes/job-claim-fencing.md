# First packet: research-job claim fencing

Status: bounded current-code inspection and local experiments. Overall research-durability audit remains open.

## External evidence

[How to do distributed locking](https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html), 8 February 2016, was read with both technical diagrams. Relevant sections concern lock purpose, resource protection and fencing. The failure model permits an old process to resume after a replacement acquired the lease; the protected sink must reject stale effects. The diagrams show the late write first corrupting storage, then being rejected when a newer token has been observed. The 2016 Redis-specific implementation discussion is historical, not a finding about today's Redis. The author's linked rebuttal is recorded but has not been reviewed here.

[Hermitage](https://martin.kleppmann.com/2014/11/25/hermitage-testing-the-i-in-acid.html), 25 November 2014, was read with its isolation diagram. It motivates tests of concrete transaction histories instead of treating a database label as proof. The diagram distinguishes transactional and register/session guarantees; arrows are not an implementation certificate. The separate Hermitage repository remains unreviewed.

[PostgreSQL 16 §13.2.1](https://www.postgresql.org/docs/16/transaction-iso.html#XACT-READ-COMMITTED) explains how an updating statement rechecks its condition against a concurrently updated row. This is supporting implementation documentation, not an executed PostgreSQL result.

Raw source hashes, extracted text and three inspected images are retained in `.agent/runs/kleppmann-professional-review-20260828/`. Blog footers declare CC BY 3.0 except where otherwise specified; separately linked papers/artifacts require their own licence check. No third-party code was copied.

## Actual repository correspondence

| Boundary | Current implementation | What it does / does not establish |
| --- | --- | --- |
| Claim | `backend/app/backtest/repository.py:338`, `claim_run` | Conditional owner/run/status/expiry update installs a fresh random token. A UUID is not an ordered fencing sequence; here the exact token is checked on the same authoritative database row. |
| Active writer | `repository.py:540`, `_active_claim` | Owner, run, running state, token, expiry and cancellation participate in the write predicate. |
| Batch commit | `repository.py:718`, `append_claimed_result_batch` | Fenced savepoint verifies attribution and deduplicates durable cell identity. This is more than a pre-write client-side lease check. |
| Terminal commit | `repository.py:819`, `complete_claim` | Fenced terminal write and event producer share the caller transaction/savepoint. |
| Test entry points | `backend/tests/test_backtest_job_claims.py:98` and `test_backtest_batch_persistence.py` | Existing tests cover replacement/cancellation and durable batches. The test named claim race uses sequential calls, so it alone would not prove simultaneous contention. |
| Independent contention | `scripts/probe_job_claim.py` | Two threads and separate sessions synchronize before claiming the same real run. After takeover, the old token and foreign owner are rejected; the current claimant persists. |

All paths beginning `backend/` are relative to `paper-trader/`. Exact current source hashes belong to the verification package. Inspect the symbols when line numbers move.

## Decision

**KEEP.** The specific stale claimant hazard is addressed in these database writers. Do not add Redis, a monotonic remote lock service, or a workflow engine merely to reproduce a protection that already exists. A random equality token is sufficient for this local conditional-write design; it would not automatically fence an independent broker, object store or other external side effect.

Existing selected tests and the independent probe use fresh SQLite databases and mocked provider/paper settings. They do not prove process-kill recovery, cross-host clock behavior, actual PostgreSQL failover, complete optimisation lineage, or every remote artifact sink. These remain explicit obligations for the research-durability audit and the accepted `strategy-os-v0-canonical-research-spine` / `strategy-os-v0-security-operations-deployability` gates.

The optional probe mutation removes only the token comparison in its own Python process. It must make the stale-terminal assertion fail. The production module on disk stays unchanged; a clean run checks restoration. Results are recorded in the verification report, not inferred from the existence of this probe.
