# Phase 2 capacity rehearsal

`scripts/phase2_load.py` records workload vectors, not product limits. The `validation-500` and
`execution-50-soak` presets are named validation points. Every dimension can be overridden within a
high operator safety bound; none is an admission constant.

Run each retained tier once after the small contract passes twice:

```bash
python scripts/phase2_load.py --preset ci --seed 20260813 --output evidence/ci-1.json
python scripts/phase2_load.py --preset ci --seed 20260813 --output evidence/ci-2.json
python scripts/phase2_load.py --preset validation-500 --seed 20260813 \
  --output evidence/validation-500.json
python scripts/phase2_load.py --preset execution-50-soak --seed 20260813 \
  --output evidence/execution-50-soak.json
```

The local contract measures in-process latency, throughput, errors, admission rejection, RSS,
bounded queue depth, fanout serialization and WebSocket bytes. Database pool waits, PostgreSQL lock
waits, WAL/backup bytes, recovery durations and dated cloud prices require an instrumented service
environment. Missing values remain `UNMEASURED`; they never become zero. Therefore the local reports
do not approve production capacity or cost.

An environment-level rehearsal must add request/job p50/p95/p99, pool checkout and timeout per
plane, connection/lock counts, worker and event lag, disconnect/backpressure, lease/job/outbox
takeover time, oldest unknown age, cgroup memory, storage/WAL/backup/egress quantities, and a dated
price-input snapshot. Separate saturation, admission rejection and failure. Overload may reject work
as long as queues and RSS remain bounded and it creates no cross-tenant data, money mutation, or
duplicate durable work.
