---
{
  "id": "strategy-os-v0-zerodha-data-static-scope",
  "lineage_id": "strategy-os-v0-coupon-trial-dynamic-validity-replan",
  "phase": "v0",
  "status": "accepted",
  "kind": "critical_read_only_coupon_dynamic_entitlement_validity_replan",
  "goal": "Define a schema-safe dynamic-duration coupon effect that lets a server-authored 15-day trial coupon redeem at a later real UTC instant while preserving fixed-envelope coupons, single-use, capacity, owner isolation and exact entitlement attribution.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "One zero-product-write migration/service/operations correction freezes dynamic versus fixed coupon effect identity, expand-contract/backfill, exact paths/tests/review and shared-assembly resume gate."},
  "risk_tags": ["critical", "schema", "migration", "entitlements", "coupon", "time", "tenancy", "privacy"],
  "depends_on": ["strategy-os-v0-account-commerce-local-service-foundation", "strategy-os-v0-account-commerce-shared-assembly"],
  "dependency_gate": {"finding": ".agent/runs/strategy-os-v0-account-commerce-shared-assembly/coupon-real-time-blocker.json", "finding_sha256": "23f035e6e7932bbb96e481829837bb1cba96a74b09ec034efa61089b2dd37e57", "red_sha256": "e7d3b8e47a8032222d09ee48de3970c6066f7a8dbebf25105add4038bf6f977c", "policy": "No clock freezing/rounding or publication workaround. Plan a durable dynamic-duration effect and preserve frozen shared bytes."},
  "required_docs": [
    {"path": ".agent/runs/strategy-os-v0-account-commerce-shared-assembly/coupon-real-time-blocker.json", "sections": ["service_evidence", "failure_hypothesis", "real_time_red", "required_invariant", "correction_evidence_required"]},
    {"path": "paper-trader/backend/app/account_commerce/service.py", "sections": ["grant_coupon_trial", "existing trial grant"]},
    {"path": "paper-trader/backend/app/platform_operations/repository.py", "sections": ["define_coupon", "redeem_coupon", "append_entitlement_event"]},
    {"path": "paper-trader/backend/app/db/models.py", "sections": ["PlatformCouponDefinitionRow", "PlatformCouponRedemptionRow", "entitlement source exact guards"]},
    {"path": "paper-trader/backend/app/db/migrate.py", "sections": ["current head", "upgrade and validation"]},
    {"path": "paper-trader/backend/AGENTS.md", "sections": ["Database and migration constraints"]}
  ],
  "allowed_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-coupon-trial-dynamic-validity-replan.md", ".agent/runs/strategy-os-v0-coupon-trial-dynamic-validity-replan"],
  "new_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-coupon-trial-dynamic-validity-replan.md", ".agent/runs/strategy-os-v0-coupon-trial-dynamic-validity-replan"],
  "protected_paths": ["paper-trader/backend", "paper-trader/frontend", "/Users/priyanshusaraf/dev/strategy-os-frontend", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/programme/PROGRAMME.json", "paper-trader/scripts/deploy.sh"],
  "scope": ["Audit current coupon definition/redemption/event schema and SQLite/PostgreSQL guards. Separate coupon redemption window from entitlement effect: fixed absolute envelope versus dynamic duration from authoritative redemption time.", "Prefer additive expand-contract: introduce a closed effect-timing discriminator and/or bounded duration field, permit null fixed timestamps only for dynamic duration, and enforce exact exclusive shape in ORM/schema/migration. Existing fixed definitions remain byte/semantic compatible through backfill/default.", "Resolve dynamic trial valid_from as current server redemption time and valid_until as exactly +1296000 seconds; persist actual resolved dates in redemption/trial/event rows so entitlement source guards remain exact.", "Require definition trial_policy_address/effect/policy/code/transition/duration and coupon active window to match; wrong/missing/ambiguous/stale/duration/fixed-envelope facts fail closed. Browser/request never authors time/duration.", "Preserve coupon digest-only lookup, plaintext absence, capacity/per-owner limits, single-use/replay, cross-owner isolation, transaction rollback and restart/rebuild attribution.", "Freeze exact 0049-or-next additive migration, SQLite/PostgreSQL expand/backfill/downgrade/rollback policy, current-head reorientation, protected paths and one Critical correction/review capsule.", "Preserve frozen shared assembly hashes and define exact resume/regression gates after correction acceptance."],
  "acceptance": ["Decision proves fixed-envelope and dynamic-duration shapes are unambiguous, reconstructible and enforced in ORM plus both supported databases.", "Migration plan preserves existing coupon/redemption/event rows and old readers during expand; current-head/fresh/upgrade/copy/restore/downgrade safety and backup/rollback obligations are exact.", "Service/operations correction derives actual dates only from server redemption time and accepted duration, with exact event-source attribution and no definition mutation.", "RED/GREEN matrix covers separate creation/redemption instants, exact 15 days, boundary/expiry/replay/concurrency/capacity/wrong policy/duration/effect/cross-owner/plaintext/rollback/restart.", "One smallest Critical successor, independent Critical review, shared-assembly frozen/resume hashes, deployment impact and architecture/protected equality are sealed with zero product writes."],
  "test_plan": ["Read-only schema/service/operations/migration/test inventory; reproduce/confirm RED; compare SQLite/PostgreSQL constraints and current head; seal exact successor/tests/review/protected hashes. Implementation belongs to successor."],
  "risk_classification": {"tier": "Critical", "reason": "Coupon timing writes durable entitlement authority and requires a schema migration; a wrong correction can grant or deny access or break restart attribution."},
  "parallel_budget": 1,
  "assignments": [{"id": "v0_coupon_trial_dynamic_validity_replan_owner", "agent": "worker", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "fork_turns": "none", "mode": "read-only-schema-service-replan", "depends_on": [], "write_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-coupon-trial-dynamic-validity-replan.md", ".agent/runs/strategy-os-v0-coupon-trial-dynamic-validity-replan"], "output": ".agent/runs/strategy-os-v0-coupon-trial-dynamic-validity-replan/decision.json"}],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "/root",
  "review": {"required": false, "assignment_id": "v0_coupon_trial_dynamic_validity_replan_owner", "agent": "worker", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "reason": "Read-only Critical replan; implementation receives independent Critical review.", "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c", "package": ".agent/runs/strategy-os-v0-coupon-trial-dynamic-validity-replan/decision.json", "review_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-coupon-trial-dynamic-validity-replan.md", ".agent/runs/strategy-os-v0-coupon-trial-dynamic-validity-replan"], "exclude_paths": ["paper-trader/backend", "paper-trader/frontend", "paper-trader/scripts/deploy.sh"], "output": ".agent/runs/strategy-os-v0-coupon-trial-dynamic-validity-replan/decision.json", "verdicts": ["SCHEMA", "ENTITLEMENT", "MIGRATION", "SUCCESSOR"], "max_rechecks": 0},
  "owner_gates": ["No product/schema/migration edit, coupon definition mutation, clock workaround, provider/money, shared resume, commit, deployment or V0 claim."],
  "stop_conditions": ["No expand-compatible representation can preserve existing fixed coupons/readers.", "Dynamic duration conflicts with accepted coupon/business policy.", "Current migration head or shared path receives concurrent ownership."],
  "deployment_impact": {"classification": "none for read-only replan; successor migration-critical", "release_deployable": false, "production_rehearsed": false, "deployed": false},
  "replan_result": {"verdict": "COUPON DYNAMIC VALIDITY REPLAN PASS", "decision": "KEEP + HARDEN WITH ONE 0049 EXPAND-CONTRACT CORRECTION", "observed_head": "0048", "target_head": "0049", "successor": "strategy-os-v0-coupon-trial-dynamic-validity-correction", "decision_path": ".agent/runs/strategy-os-v0-coupon-trial-dynamic-validity-replan/decision.json", "product_writes": 0, "shared_assembly_frozen": true, "deployment": false},
  "nonclaims": ["No coupon fix, schema/migration, shared publication, provider, deployment, release readiness or V0 completion."]
}
---

# Coupon trial dynamic validity replan

Replace the impossible exact-redemption-time equality with a durable,
server-resolved dynamic-duration effect. Do not weaken fixed coupons or attribution.

## Sealed decision

`KEEP + HARDEN WITH ONE 0049 EXPAND-CONTRACT CORRECTION`.

The current execution head is tool-confirmed as `0048`; no `0049` revision exists.
The successor therefore owns the exact additive revision
`20260902_0049_coupon_dynamic_entitlement_validity.py` with `down_revision =
"0048"`. The correction adds one closed definition-time discriminator,
`FIXED_ABSOLUTE | DYNAMIC_DURATION`, and one nullable duration field. Existing
rows backfill to `FIXED_ABSOLUTE` without changing their timestamps or meaning.

The two shapes are exclusive. A fixed definition keeps its non-null absolute
start, an optional increasing absolute end, and no duration. The only dynamic
shape accepted in V0 has no absolute definition timestamps, has a trial policy
and no discount policy, grants access, and has an exact duration of `1296000`
seconds. A broader duration or effect vocabulary needs a separate owner-approved
policy and migration.

At redemption, the operations repository locks the digest-selected definition,
rechecks its active half-open window, policy, capacity and per-owner limits, and
derives the actual entitlement interval from the authoritative UTC server
`redeemed_at`. It persists that interval on the redemption. The account-commerce
service requires the interval to equal the accepted policy candidate, then copies
the persisted redemption dates to the trial-use and entitlement-event rows. The
repository and SQLite/PostgreSQL source-exact guards keep comparing those actual
dates. Restart and rebuild use the persisted facts; they do not recalculate from
the current clock or mutate the coupon definition.

Old code remains compatible with existing fixed rows. It cannot safely consume a
dynamic row because it knows only absolute definition timestamps. Migration and
activation therefore require writer quiescence and a capability barrier: reach
and validate exact head `0049`, deploy only the `0049`-capable binary, and admit a
dynamic definition only after the GREEN evidence and Critical review pass. Mixed-
version dynamic activation is rejected.

## Migration and recovery seal

The correction proves fresh install and exact populated `0048 -> 0049` upgrade on
SQLite and real disposable PostgreSQL 16. It must cover model equality, constraints,
indexes, foreign keys, capacity and source triggers, stale/branch/partial refusal,
interruption and retry, concurrent migration ownership, repeated startup, SQLite
to PostgreSQL copy, clean-target restore, and meaningful row/content digests. The
managed PostgreSQL runner must accept only exact `0048 -> 0049`; every other stale
head still fails before writes.

A lossless downgrade to `0048` is supported only while no dynamic definition
exists. The downgrade preflight must refuse before writes when one exists. After
dynamic activation, an old schema or binary cannot represent the definition, so
rollback is forward repair under writer quiescence. A pre-migration restore is
valid only when no post-backup write must be retained. No durable access fact may
be dropped to make a rollback appear successful.

## Safety, tenancy and privacy seal

The browser never authors time, duration, owner, policy effect or access outcome.
Tenant identity remains server-derived. Tests use two unrelated owners and a
revoked member, with a legitimate same-owner control. They must prove replay,
capacity, rollback, restart and cross-owner denial without a side effect or event
leak. Coupon plaintext remains transient; only its SHA-256 digest may reach
persistence. The two new definition fields contain policy timing metadata, not
customer content. Resolved timestamps remain pseudonymous access evidence in the
existing redemption/trial/event stores. This slice creates no cache, socket, job,
artifact, analytics, support, LLM or external-processor flow and selects no new
retention or legal policy.

## Successor and review gate

The smallest successor is
`strategy-os-v0-coupon-trial-dynamic-validity-correction`. Its exact paths,
constraints, RED/GREEN/concurrency/restart/migration matrix and one independent
Critical review are frozen in
`.agent/runs/strategy-os-v0-coupon-trial-dynamic-validity-replan/`.

The account-commerce shared assembly remains frozen at the hashes in
`coupon-real-time-blocker.json`. It may resume only after the correction receives
SPEC PASS and QUALITY PASS on exact bytes. The shared owner must then rerun the
backend and frontend packages, supported-runtime frontend build, an isolated
browser coupon journey with distinct creation and redemption instants, frozen
hash equality, and its Important integrated review.

## Evidence index

- `decision.json`: accepted architecture, timing and activation decision.
- `schema-matrix.json`: exclusive fixed and dynamic row shapes.
- `migration-matrix.json`: heads, upgrade, downgrade, restore and rollback.
- `service-operations-matrix.json`: server-time resolution and exact source flow.
- `test-matrix.json`: RED/GREEN, adversarial and mutation evidence.
- `privacy-tenancy-matrix.json`: scoped data flow and two-tenant controls.
- `successor-capsule.json`: exact correction ownership and Critical review.
- `architecture.json`: `KEEP + HARDEN`, rejected alternatives and invariants.
- `protected-hashes.json`: zero-product-write and shared-frozen equality receipt.

No product/schema/migration/shared bytes, provider, money, commit or deployment
were changed by this read-only replan. It does not claim a coupon fix, release
deployability, production rehearsal, deployment, release readiness or V0 completion.
