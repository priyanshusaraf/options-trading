# Source-to-code matrix

## Current-tree verification receipt

The five Chat 1 characterizations were rerun after the handoff against the current
dirty tree.

- Three tests ran directly and remained RED: legacy V0 sweep, missing graph
  `ResourcePlan`, and contradictory terminal order reduction.
- Two tests initially errored because their audit directory did not inherit the
  sibling `research_tests/conftest.py`. The harness failure is preserved.
- Loading that conftest explicitly made both tests run and remain RED: forced spec
  collision and full-history qualification/OOS contamination.

Evidence:

- `.agent/runs/chat2-v5/repository-synthesis/chat1-characterizations-current-tree-rerun.log`
- `.agent/runs/chat2-v5/repository-synthesis/data-research-characterizations-current-tree.log`

## Highest-impact mappings

| Finding | Source principle and assumptions | Current repository evidence | Failure consequence | Decision |
| --- | --- | --- | --- | --- |
| OOS qualification contamination | DSR/PBO require a declared complete trial population and selection-free evaluation; OOS cannot influence qualification. | `research/orchestrator/run.py:346-435`; RED shows qualification `[400,400]` and validation `[400,400]`. | Selection-contaminated output can be presented as independent evidence. | `V0 BLOCKER`; seal selection boundaries or label exploratory. |
| Legacy sweep reachable in V0 | Point-in-time market truth requires addressed dataset/instrument/rulebook facts; UI hiding is not authorization. | `app/core/release_profile.py`, `app/api/backtest_routes.py`, `app/backtest/universe.py`; denial policy returns `None`. | Authenticated API caller can produce V0-labelled research through current universe/provider/fallback. | `V0 BLOCKER`; refuse before dispatch or require canonical manifest. |
| Graph route omits ResourcePlan | SRE overload and Strategy OS resource contracts require bounded demand before work starts. | `research/orchestrator/graph_experiment.py:193-222` never consumes `app/ir/resource_plan.py`; RED structural test. | Accepted graph work can exceed its declared bounds and evidence omits the plan. | `V0 BLOCKER` under existing F03 owner. |
| Experiment spec collision | AWS idempotent APIs require token plus original-parameter equality; stable hashing requires canonical bytes. | `research/orchestrator/run.py:124-134,270-293`; forced `0*32` digest reuses one row for different slippage recipes. | Run provenance can name immutable bytes that were not requested. | `V0 NON-BLOCKING HARDENING`; canonical-byte mismatch refusal, then additive full address. |
| Complete fill remains CANCELLED | Broker timestamps/postbacks do not prove causal terminal order; raw events need an explicit reconciliation policy. | `app/engine/execution_lifecycle.py:180-302`; RED yields `CANCELLED` with `10/10` filled. | Position/ledger/user state can disagree with a real full fill. | `V1 EXECUTION`; preserve raw events and introduce versioned conflict state/policy. |
| `available_at < completed_at` accepted | SQL temporal/event-time sources require explicit valid/completion/availability ordering for completed values. | `app/market_data/observations.py`; independent constructor RED. Current Q03 checks both timestamps. | Future producer/consumer could expose a completed value before bar completion. | `PROVIDER-CAPTURE BLOCKER`, current Q03 contained; producer inventory before fix. |
| Optimization reconstruction incomplete | DSR/PBO require the search population/order and exact statistical inputs. | `run.py`, `optimize.py`, `domain/models.py`; candidate order, resolved search space and some vectors are not durable. | A later build may not reconstruct acceptance from stored evidence. | `V0 EVIDENCE HARDENING`; prove reconstruction first, add only irreconstructible facts. |
| Claim-race gate does not terminate | PostgreSQL/Jepsen require engine-specific concurrent histories and whole-operation retry/termination. | Isolated SQLite case exceeds 45 seconds after inherited edits; PostgreSQL unavailable. | Current evidence cannot establish safe claim progress/takeover. | `CURRENT VALIDATION FAILURE`; localize before changing code/test. |
| Connected socket revocation unspecified | OWASP authorization applies throughout access, not only handshake. | Auth before join; receive loop does not revalidate expiry/revocation/membership. V0 route denied. | Future revoked session may keep receiving private frames. | `V1 SECURITY`; owner sets revocation bound before design. |
| P0/P1 workload isolation absent | Google SRE says overload must be measured and lower-priority work shed before collapse. | Bounded local queues exist; no measured protection/reconciliation scheduler; V0 execution denied. | Future research saturation may delay protection. | `V1 MEASUREMENT`; no queue/service adoption now. |

## Canonical adversarial scenarios

| # | Scenario | Current result | Evidence/next proof |
| ---: | --- | --- | --- |
| 1 | Future provider correction enters historical backtest | Contained only in narrow Q03; broader path unverified | Same-event corrections before/after cutoff; immutable revision identity. |
| 2 | Present contract metadata projected backward | Reachable in legacy sweep/current universe; V0 policy FAIL | Deny legacy route; effective-dated contract-master fixtures. |
| 3 | Forming higher-timeframe bar leaks future | Bounded completed-bar foundations exist; broad proof incomplete | Prefix and forming/completed fixtures through one converter. |
| 4 | Stale/skewed multi-instrument entry | Narrow Q03 excludes multi-instrument; future gap | Explicit as-of/freshness/skew refusal. |
| 5 | Missing/closed/not-listed/provider-down collapse | Canonical validity types exist; adapter breadth unverified | Provider-specific absence fixtures and no zero fallback. |
| 6 | Semantic cache collision | Phase 4 keys strong; full consumer audit incomplete | Mutate every answer-changing field including plan/provider/rulebook. |
| 7 | Changed upload appears unchanged | No accepted user upload journey | Future upload content/recipe/owner identity and safe parser tests. |
| 8 | Optimizer resume changes experiment | Under-proved | Exact search space/order/trials/seed/build reconstruction after kill/restart. |
| 9 | OOS used during selection | `FAIL`, direct RED | OOS suffix mutation cannot alter qualification or candidate selection. |
| 10 | Simultaneous signals overreserve | Foundation exists, unwired | PostgreSQL simultaneous transactions and restart/rollback. |
| 11 | Timeout retry duplicates order | V0 unreachable; future unknown-submit contract partly exists | Synthetic broker timeout after accept and exact-tag reconciliation. |
| 12 | Duplicate/out-of-order fill/cancel/modify | `FAIL` for cancel/complete | Property/state-machine events and coherent conflict result. |
| 13 | Crash after broker effect before local commit | Foundations exist; live unavailable | Crash at every send/ack/fill/booking boundary. |
| 14 | New strategy version manages old positions | Exact revision lineage exists in inspected paths | Mutation/restart proof before execution release. |
| 15 | Broker netting erases strategy ownership | Virtual ownership foundation exists | Partial close/netting/restart reconciliation fixtures. |
| 16 | Worker resumes entries without state | V0 live denied; future warming policy incomplete | Restart with missing/corrupt state must block entries while exits remain available. |
| 17 | Optimization starves protection | V0 N/A; future unmeasured | Mixed-load p95/p99 protection/reconciliation latency. |
| 18 | Queue/backlog unbounded | Local queues bounded; system-wide proof absent | Queue age/depth, admission and reclaim under sustained/burst load. |
| 19 | Provider semantics change silently | Capability/version foundations exist; lifecycle proof incomplete | Exact before/after capability receipts and revalidation. |
| 20 | Cache loss destroys authority | Inspected caches/views are derived | Delete/rebuild fixtures and explicit degraded state. |
| 21 | Migration changes old evidence meaning | No Chat 2 migration authorized | Expand-contract, old-reader/new-reader and rollback proof. |
| 22 | Background job reads another tenant | Focused suites positive; repository-wide proof absent | A/B tenant claim/artifact/finalization tests. |
| 23 | Logs expose strategy/secrets | Redaction structures exist; exhaustive audit absent | Sentinel strategy/token/bank strings across logs/traces/errors. |
| 24 | Malformed upload/custom node exhausts resources | No accepted upload journey; custom-node audit incomplete | Size/decompression/CPU/memory/state timeboxes and cleanup. |
| 25 | Restore cannot reconstruct lineage | `UNVERIFIED` | Isolated PostgreSQL three-plane restore and exact address reconciliation. |
| 26 | Dynamic Watchlist refresh duplicates/loses policy | Future only | Versioned definition/snapshot/rank/hysteresis/leave-policy identity. |
| 27 | Historically nonexistent option selected | Broad options history unsupported | Point-in-time listing/strike/expiry master and refusal. |
| 28 | Selector recenters exact held option | Identity seam exists; execution proof absent | Hold original contract across recenter/restart/exit. |
| 29 | Signal-only path reaches execution | V0 negative route tests pass; legacy sweep still violates research boundary | Preserve release-profile denial and mutation test. |
| 30 | Paper/live share mutable state/credentials | Structural separation tests exist; no live claim | Exact database/profile/credential sentinel and no-live-under-test. |

## Already correct or intentionally unavailable

- One canonical IR, validator, resolver, registry and execution binding remain.
- Q03 canonical-manifest research is narrow, causal and provider-fetch-free.
- V0 live execution and execution WebSockets are denied.
- Database outbox facts remain authoritative over notifications.
- Capital admission foundation is transaction/fence based but intentionally unwired.
- No Redis, Kafka, workflow engine, second ledger or service extraction is needed.

## Current-tree caveat

The active V0 convergence task is concurrently editing product/programme paths. It
acknowledged Chat 2 ownership only for reports 13–25 and the three named architecture
pages. Product findings are valid current-tree observations, but implementation must
wait for a collision-free capsule and refreshed hashes.
