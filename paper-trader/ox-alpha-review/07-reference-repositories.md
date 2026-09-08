# 07 — Reference Repositories: Inventory Verdict, What to Take, What to Clone Next

**Basis:** full inventory of `~/dev/multiverse-of-ideas` (32 shallow clones, ~4.9 GB, 32 completed
reviews + `_PATTERNS.md` with 13 reusable patterns + licence ledger) plus this review's
recommendations for new clones.

## 1. Verdict on the existing library

The library is in good shape and *mined*, not raw: every repo has a written review, licences are
recorded against pinned commits, and the "reviews are the only artefact that crosses over" rule
keeps licence risk out of the product. Highlights that matter most for Phases 5–7:

| Repo | Licence | Take this |
|---|---|---|
| `xyflow` | MIT | **The node-editor substrate. Buy, don't build.** Only repo the ledger marks dependency-safe to build on |
| `dbos-transact-py` / `-ts` | MIT | The spec for Postgres-backed durable workflows: checkpoint-before-effect, queues, recovery. Maps onto Phase 2's job machinery |
| `dvc-data` | Apache-2.0 | Content-addressed object-store layout (hash-file dirs, transfer, index) for datasets |
| `langflow` | MIT | Component→JSON→runtime round-trip discipline; React-Flow builder precedent |
| `comfyui` | GPL-3.0 (reference only) | Typed node registry where custom nodes = built-ins; execution engine shape |
| `superalgos` | Apache-2.0 | **Direct product prior art** (visual strategy → backtest → live). Mine UX flows |
| `nautilus_trader` | LGPL-3.0 | Backtest/live parity architecture, event bus, risk engine. Linking OK; no vendoring |
| `lean` (QuantConnect) | Apache-2.0 | Contract identity, provider/broker plugin seams, research→deploy pipeline |
| `ccxt` | MIT | Capability-flag pattern across 100+ venues; built-in rate limiter concepts |
| `openfga` (+ sample stores) | Apache-2.0 | Zanzibar authz + literal multi-tenant policy fixtures — reserve for Phase 8–10 sharing rules |
| `hummingbot` / `vnpy` | Apache-2.0 / MIT | In-flight order reconciliation; gateway/OMS separation |
| `hftbacktest` | MIT | Queue-position & latency-aware fill simulation — relevant to execution integrity (CONTINUE §4 item 6) |
| `optuna` | MIT | RDB-backed trial storage + pruning for parameter sweeps |
| Indian broker SDKs (`pykiteconnect`, `upstox-python`, `dhanhq-py`) | MIT | Wrap at the adapter seam per existing capability architecture |

**Licence traps already correctly flagged by your ledger:** GPL-3.0 (`freqtrade`, `backtrader`,
`comfyui`, `lumibot`) behaviour-reference only; `vectorbt` is Apache-2.0 **+ Commons Clause** —
hosting it in a paid product is the prohibited case, so patterns only; `nautilus_trader` LGPL
linking OK, derivation not.

## 2. Coverage gaps in the current library

Two of our live problem areas have **no HIGH-rated coverage** in the library:

1. **Schema-migration integrity tooling** (the A-01/A-03 war).
2. **Load shedding / adaptive concurrency / circuit breaking** (the no-silent-outage requirement).

## 3. Recommended new clones (with checks to run at clone time)

For each: verify licence file, last-commit recency, and record against `_meta/LICENCES.md`.

| Repo | Licence | Why it fills a gap | Adoption mode |
|---|---|---|---|
| `ariga/atlas` | Apache-2.0 | Migration linting: detects destructive changes, schema drift, incomplete contracts — mechanizes A-01's prevention invariant as a CI gate | CLI tool / reference its check catalog |
| `xataio/pgroll` | Apache-2.0 | Zero-downtime PostgreSQL migrations via explicit expand/contract phases — the shape Phase 6+ schema changes should follow when clients are live | Reference pattern; possibly wrap CLI later |
| `Netflix/concurrency-limits` | Apache-2.0 | Adaptive concurrency-limit algorithms (Gradient2, Vegas) — principled backpressure instead of static pools | Port algorithms to Python behind your own seam |
| `aiolimiter` | MIT | Tiny async token bucket — enforceable per-provider call budgets at the adapter seam (your 10-calls/sec contract) | Direct dependency candidate |
| `prometheus/client_python` | Apache-2.0 | Metrics for pool saturation, queue depth, budget burn — the leading indicators | Direct dependency candidate |
| `temporalio/temporal` | MIT | Reference only: how durable execution handles retry/idempotency/recovery at scale — study before finalizing reclaim/finalization semantics | Behaviour reference |

Optional, lower priority: `resilience4j` (Apache-2.0, Java — circuit-breaker/bulkhead state-machine
reference), `envoyproxy/envoy` (Apache-2.0 — overload management + rate-limit service design,
useful when designing the AWS edge), `nats-io/nats-server` (Apache-2.0 — only if you ever need a
bus; the repo has twice rejected one, correctly).

## 4. Out-of-the-box note you asked for: networks & request management

The most transferable idea from network engineering for Strategy OS is **admission control as a
first-class typed fact**: exactly what your IR does for strategies, applied to requests. Concretely:
every deployment declares required throughput (calls/sec, WS msgs/sec, backtest CPU-minutes);
preflight compares against measured budgets and produces a receipt; runtime enforces with token
buckets + adaptive limits and degrades loudly. Envoy's overload manager, Netflix's limiters, and
Kite's own per-category rate cards all converge on this shape — and it composes cleanly with the
capability vocabulary you already have. That is doc 05 D3/D5's design, sourced.

## 5. Hygiene rule going forward

Keep the library rule: reviews cross over, code doesn't (except MIT/Apache dependencies wrapped at
declared seams). When a clone informs an ADR or capsule, cite the review path, not the repo path —
that's what keeps licence posture auditable.
