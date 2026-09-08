Reference: [section index](../10-ADVERSARIAL-FAILURE-HYPOTHESES.md). Read with its scope; this is not a new assignment.

# Adversarial failure hypotheses

The register includes direct defects, missing invariants/tests, and negative conclusions. Severity is based on reachable consequence, not source prestige or diff size.

## Central finding register

### KPV5-A-001 — experiment specification identity collision

| Field | Decision |
|---|---|
| New/prior relation | New direct counterexample; prior work did not force a collision. |
| Source claim/location/assumptions | `KLEPPMANN_HASHCODE_2012_V5`, stable serialization and cross-process hash sections; assumes persisted identity. |
| Code evidence | `research/orchestrator/run.py:124-134,270-293`; forced RED log `.agent/runs/kleppmann-reaudit-v5/pass-a/red-experiment-spec-collision.log`. |
| Failure and consequence | Different canonical recipes reuse one immutable `ExperimentSpec`; run provenance can name the wrong recipe. |
| Severity / likelihood / reachability | Important evidence-integrity defect; natural 128-bit collision extremely unlikely, forced collision certain; V0 route reachable. |
| Classification / release | **CONFIRMED DEFECT**; **V0 NON-BLOCKING HARDENING**, V1 foundation if migration needed. |
| Smallest safe response / proof | Compare stored canonical bytes on reuse; add full 256-bit address additively; force-collision, restart, SQLite/PostgreSQL and legacy compatibility tests. |
| Migration/rollback/confidence | Preserve legacy IDs as aliases; never rewrite old evidence. HIGH behavior confidence, LOW natural likelihood. |

### KPV5-A-002 — qualification consumes later OOS rows

| Field | Decision |
|---|---|
| New/prior relation | Confirms and sharpens prior research-validity concern with a direct row-span probe. |
| Source claim/location/assumptions | Direct repository source `STRATEGY_OS_V5_PASS_A_PROBES_20260831`; assumes “locked/untouched OOS” means no prior selection use. |
| Code evidence | `research/orchestrator/run.py:346-435`; RED test/log `test_oos_qualification_contamination.py` and `red-oos-qualification-contamination-recheck.log`. |
| Failure and consequence | Full history qualifies an instrument before the same rows are called OOS; users may treat selection-contaminated performance as independent. |
| Severity / likelihood / reachability | Critical research claim; deterministic on every current full-data run; V0 reachable. |
| Classification / release | **CONFIRMED DEFECT / RESEARCH VALIDITY**; **V0 BLOCKER** for locked/untouched OOS claims. |
| Smallest safe response / proof | Seal train/qualification/embargo/OOS before selection or label exploratory; suffix mutation must not change qualification. |
| Migration/rollback/confidence | Old evidence keeps original method label; corrected method gets new identity. HIGH. |

### KPV5-A-003 — legacy sweep remains reachable in V0

| Field | Decision |
|---|---|
| New/prior relation | New route-policy counterexample; contradicts an API-only canonical-manifest reading of V0. |
| Source claim/location/assumptions | Direct probe source; assumes V0 authority applies to both API prefixes and non-UI callers. |
| Code evidence | `app/core/release_profile.py:143-182`, `app/api/backtest_routes.py:61-90`, `app/backtest/universe.py:40-134`; RED policy log. |
| Failure and consequence | Authenticated caller starts research from current provider universe or curated/mock fallback and receives V0-labelled historical output. |
| Severity / likelihood / reachability | High market-truth consequence; reachable policy path; provider work not started in audit. |
| Classification / release | **CONFIRMED DEFECT / MARKET-TRUTH RELEASE BOUNDARY**; **V0 BLOCKER**. |
| Smallest safe response / proof | Deny legacy sweep in V0 or require `canonical_manifest_v2` at shared boundary; prove refusal before provider dispatch. |
| Migration/rollback/confidence | No data migration; standard profile may retain legacy route. HIGH. |

### KPV5-A-004 — completed observations permit impossible availability ordering

| Field | Decision |
|---|---|
| New/prior relation | Confirms NMT-002; current Q03 containment is newer than prior audit. |
| Source claim/location/assumptions | Stream/event-time sources reviewed in Pass A; completed value cannot be known before interval completion. |
| Code evidence | `app/market_data/observations.py:28-35,143-164,237-261,317-334`; shadow direct characterization. |
| Failure and consequence | Future consumer checks `available_at` alone and consumes a completed value mid-bar. Current Q03 checks both and requires equality. |
| Severity / likelihood / reachability | Potential high look-ahead; producer reachability medium; no current Q03 wrong result. |
| Classification / release | **MISSING INVARIANT**; V0 provider-capture blocker, current Q03 contained. |
| Smallest safe response / proof | Inventory forming/completed producers, then require `available_at >= completed_at` for completed observations; persistence/loader/prefix tests. |
| Migration/rollback/confidence | Preserve bad historical facts but exclude from new authority; do not rewrite addresses. HIGH gap, MEDIUM reachability. |

### KPV5-A-005 — IID trade bootstrap assumption is unstated

| Field | Decision |
|---|---|
| New/prior relation | New method-assumption finding. |
| Source claim/location/assumptions | Repository method evidence plus broader statistical source required in Chat 2; no Kleppmann source establishes bootstrap validity. |
| Code evidence | `research/stats/evidence.py:14-24`, `research/pipeline/qualify.py:32-50`, `validate.py:33-52`. |
| Failure and consequence | Clustered/correlated trades yield too-narrow lower bound and false confidence. |
| Severity / likelihood / reachability | Important research label; likelihood unknown until dependent fixtures; V0 reachable. |
| Classification / release | **MISSING TEST / METHOD ASSUMPTION**; V0 exploratory label or blocker before confidence claim. |
| Smallest safe response / proof | State IID approximation; compare IID control and block/autocorrelated fixtures before choosing a method. |
| Migration/rollback/confidence | New method/version creates new evidence; old rows unchanged. MEDIUM. |

### KPV5-A-006 — correction lineage is absent from the general projection

| Field | Decision |
|---|---|
| New/prior relation | New future-seam finding; no current production consumer found. |
| Source claim/location/assumptions | Stream/temporal sources in Pass A; correction selection needs revision and knowledge cutoff. |
| Code evidence | `app/market_data/observations.py:305-422`. |
| Failure and consequence | Future general consumer either cannot select a correction or breaks causality. |
| Severity / likelihood / reachability | Future destructive assumption; current likelihood zero on searched routes. |
| Classification / release | **FUTURE DESTRUCTIVE ASSUMPTION / MISSING INVARIANT**; **SEAM ONLY**. |
| Smallest safe response / proof | Add versioned revision/cutoff identity only when a producer/consumer exists; before/after cutoff and tie-refusal fixtures. |
| Migration/rollback/confidence | Additive projection version; preserve old bytes. MEDIUM. |

### KPV5-A-007 — optimization reconstruction is under-proved

| Field | Decision |
|---|---|
| New/prior relation | Confirms prior reproducibility concern but rejects a current wrong-result claim. |
| Source claim/location/assumptions | Derived-state/rebuild principles; assumes accepted evidence must survive code/schema evolution. |
| Code evidence | `research/orchestrator/run.py:234-267,388-475`, `research/pipeline/optimize.py:122-174`, `research/domain/models.py:685-707`. |
| Failure and consequence | Later build cannot reconstruct exact candidate order, `is_sharpe`, PBO inputs or selected population. |
| Severity / likelihood / reachability | Important evidence gap; actual failure unverified; V0 results reachable. |
| Classification / release | **RESEARCH EVIDENCE GAP**; V0 robustness. |
| Smallest safe response / proof | First reconstruct from current stored rows after restart/migration; add only irreconstructible identities. |
| Migration/rollback/confidence | Additive fields/version; legacy rows retain limitation. MEDIUM-HIGH omissions, UNVERIFIABLE failure. |

### KPV5-B-001 — published graph execution omits ResourcePlan

| Field | Decision |
|---|---|
| New/prior relation | Confirms existing F03 and its named programme owner. |
| Source claim/location/assumptions | Cache/dependency and runtime-state sources; assumes accepted work carries its answer/cost-changing plan. |
| Code evidence | `research/orchestrator/graph_experiment.py:193-222` versus `app/ir/resource_plan.py:171-471`; RED characterization/log. |
| Failure and consequence | Canonical graph work runs without declared memory/storage/artifact/provider/concurrency bounds or matching refusal evidence. |
| Severity / likelihood / reachability | High release-contract impact; deterministic route gap; V0 graph research reachable. |
| Classification / release | **MISSING INVARIANT**; **V0 BLOCKER** under existing F03. |
| Smallest safe response / proof | Existing F03 owner wires exact accepted plan and retains address in spec/evidence; mutate every plan dimension. |
| Migration/rollback/confidence | Additive identity/persistence if required; no competing planner. HIGH. |

### KPV5-B-002 — terminal order conflict mislabels a complete fill

| Field | Decision |
|---|---|
| New/prior relation | New direct state-machine counterexample. |
| Source claim/location/assumptions | `KLEPPMANN_EVENT_ORDER_2018_V5`, ordering section; `KLEPPMANN_ISABELLE_2022_V5`, loss/duplication/reordering model. |
| Code evidence | `app/engine/execution_lifecycle.py:180-302`; RED `test_execution_terminal_observation_conflict.py`. |
| Failure and consequence | Cancel/complete race yields `CANCELLED` with full fill; evidence and user status conflict, recovery requires manual interpretation. |
| Severity / likelihood / reachability | Critical money-path type but V0 denied; provider-specific likelihood unknown. |
| Classification / release | **CONFIRMED DEFECT**; **V1 FOUNDATION / EXECUTION**. |
| Smallest safe response / proof | Declare status partial order/conflict state; complete/cancel races, corrections, duplicates, lower cumulative and restart property tests. |
| Migration/rollback/confidence | Reducer version/projection rebuild must preserve raw events; rollback selects old reducer but does not rewrite events. HIGH behavior, unknown live frequency. |

### KPV5-B-003 — current claim-race validation times out; PostgreSQL evidence is unavailable

| Field | Decision |
|---|---|
| New/prior relation | Contradicts earlier shadow positive evidence after later inherited backend edits; exact defect remains unlocalized. |
| Source claim/location/assumptions | Failure/recovery sources; assumes multiple workers and process death. |
| Code evidence | `app/db/concurrency.py` and claim predicates; isolated `test_claim_race_allows_exactly_one_token_and_never_blocks_another_owner` times out after 45 seconds in `backtest-job-claims-timeboxed.log`; PostgreSQL/Docker unavailable. |
| Failure and consequence | The current validation gate can deadlock or fail to terminate; the safety hypothesis remains stale-worker/double-owner behavior until localized. |
| Severity / likelihood / reachability | Important current test/release blocker; user-facing runtime reachability unproved. |
| Classification / release | **REQUIRES FRESH TEST / CURRENT VALIDATION FAILURE**; V0 release evidence, V1 foundation. |
| Smallest safe response / proof | Reconcile inherited claim/concurrency edits and make the isolated SQLite race terminate deterministically, then run exact PostgreSQL process-kill/takeover cases. |
| Migration/rollback/confidence | No migration until localized; revert/disable only inside the active owner capsule. HIGH timeout evidence, UNKNOWN cause. |
