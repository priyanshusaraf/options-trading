---
{
  "id": "strategy-os-v0-zerodha-data-static-scope",
  "lineage_id": "strategy-os-v0-coupon-trigger-relation-recovery-replan",
  "phase": "v0",
  "status": "accepted",
  "kind": "critical_read_only_trigger_relation_recovery_replan",
  "goal": "Define the smallest fresh correction that binds every required 0049 coupon trigger to its exact protected relation in SQLite and PostgreSQL current-head validation.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "One zero-product-write decision freezes exact relation-aware validation, tamper matrix, paths, preserved Critical evidence and fresh review."},
  "risk_tags": ["critical", "migration", "postgresql", "sqlite", "trigger", "schema-readiness"],
  "depends_on": ["strategy-os-v0-coupon-trial-dynamic-validity-correction"],
  "dependency_gate": {"recheck_verdict": ".agent/runs/strategy-os-v0-coupon-trial-dynamic-validity-correction/review/recheck-verdict.json", "recheck_verdict_sha256": "3ef1ee917a163ff2f8ae796930cca77220df9f2f72765770a2fcde7ec7c30504", "closed": ["V0-CDV-CR-002"], "open": ["V0-CDV-CR-001-R1"], "policy": "Preserve accepted 0049 service/migration/PG evidence and correct only trigger-to-table validation."},
  "required_docs": [
    {"path": ".agent/runs/strategy-os-v0-coupon-trial-dynamic-validity-correction/review/recheck-verdict.json", "sections": ["findings", "closed_findings", "independent_checks", "nonclaims"]},
    {"path": ".agent/runs/strategy-os-v0-coupon-trial-dynamic-validity-replan/migration-matrix.json", "sections": ["matrix", "operational_sequence"]},
    {"path": "paper-trader/backend/app/db/migrate.py", "sections": ["current 0049 schema and trigger validation"]}
  ],
  "allowed_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-coupon-trigger-relation-recovery-replan.md", ".agent/runs/strategy-os-v0-coupon-trigger-relation-recovery-replan"],
  "new_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-coupon-trigger-relation-recovery-replan.md", ".agent/runs/strategy-os-v0-coupon-trigger-relation-recovery-replan"],
  "protected_paths": ["paper-trader/backend", "paper-trader/frontend", "/Users/priyanshusaraf/dev/strategy-os-frontend", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/programme/PROGRAMME.json", "paper-trader/scripts/deploy.sh"],
  "scope": ["Inventory every required SQLite/PostgreSQL coupon shape/privacy/capacity/source trigger with exact name, relation, timing, operation and function/body identity.", "Define relation-aware current-head validation using SQLite sqlite_master.tbl_name and PostgreSQL catalog joins such as pg_trigger→pg_class/pg_namespace plus function identity, not name-only presence.", "Freeze tamper tests moving unchanged triggers/functions to wrong relations, duplicate same-name variants, wrong schema, disabled/internal states and missing expected trigger; all must refuse with unchanged head/rows.", "Name the smallest successor owning migrate.py and exact schema/migration tests only unless inspection proves another validation module is required.", "Preserve the corrected package's service semantics and real PG16 444/444 evidence; rerun only proportional regression plus one fresh Critical review."],
  "acceptance": ["Decision lists exact required trigger-to-relation map for both dialects and a fail-closed catalog query/normalization rule.", "Successor paths/tests/review are exact; no migration/service/schema definition changes unless directly required.", "Wrong-relation/missing/duplicate/function/schema/disabled tamper matrix and current-head unchanged-state proof are sealed.", "All prior fixed/dynamic/PG/copy/restore/frozen evidence remains bound; architecture/protected hashes pass with zero product writes."],
  "test_plan": ["Read-only current validation/catalog inspection, residual probe review, exact successor and tamper matrix, architecture/protected hashes."],
  "risk_classification": {"tier": "Critical", "reason": "False current-head readiness can accept a migration marker whose entitlement capacity/source safeguards protect the wrong table."},
  "parallel_budget": 1,
  "assignments": [{"id": "v0_coupon_trigger_relation_recovery_replan_owner", "agent": "worker", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "fork_turns": "none", "mode": "read-only-trigger-relation-replan", "depends_on": [], "write_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-coupon-trigger-relation-recovery-replan.md", ".agent/runs/strategy-os-v0-coupon-trigger-relation-recovery-replan"], "output": ".agent/runs/strategy-os-v0-coupon-trigger-relation-recovery-replan/decision.json"}],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "/root",
  "review": {"required": false, "assignment_id": "v0_coupon_trigger_relation_recovery_replan_owner", "agent": "worker", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "reason": "Read-only Critical recovery replan; successor receives one fresh Critical review.", "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c", "package": ".agent/runs/strategy-os-v0-coupon-trigger-relation-recovery-replan/decision.json", "review_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-coupon-trigger-relation-recovery-replan.md", ".agent/runs/strategy-os-v0-coupon-trigger-relation-recovery-replan"], "exclude_paths": ["paper-trader/backend", "paper-trader/frontend", "paper-trader/scripts/deploy.sh"], "output": ".agent/runs/strategy-os-v0-coupon-trigger-relation-recovery-replan/decision.json", "verdicts": ["SQLITE", "POSTGRESQL", "READINESS", "SUCCESSOR"], "max_rechecks": 0},
  "owner_gates": ["No product/migration/service edit, shared resume, provider/money, commit, deployment or V0 claim."],
  "stop_conditions": ["Relation binding cannot be inspected consistently on a supported dialect.", "Correction requires changing coupon service/schema semantics.", "Concurrent ownership appears on migrate/test paths."],
  "deployment_impact": {"classification": "none for replan; successor readiness-critical", "release_deployable": false, "production_rehearsed": false, "deployed": false},
  "nonclaims": ["No readiness fix, shared publication, deployment, release readiness or V0 completion."]
}
---

# Coupon trigger relation recovery replan

Bind required 0049 triggers to their exact protected relations. Name and function
identity alone are insufficient readiness evidence.

## Sealed decision

Keep revision 0049 and the accepted coupon service, migration, PostgreSQL 16,
copy, restore, health, and schema behavior. Harden only current-head readiness.
`V0-CDV-CR-001-R1` remains open until a fresh correction and Critical review
prove exact trigger-to-relation binding. This replan makes zero product writes.

The authoritative machine-readable decision is
`.agent/runs/strategy-os-v0-coupon-trigger-relation-recovery-replan/decision.json`.
Its model-derived DDL inventory is recorded under
`v0_coupon_trigger_relation_recovery_replan_owner/model-ddl-inventory.log`.

## Exact relation map

SQLite requires eight persistent `sqlite_master` triggers:

| Trigger | Protected relation | Timing and operation |
| --- | --- | --- |
| `platform_coupon_definitions_privacy_insert` | `platform_coupon_definitions` | `BEFORE INSERT` |
| `platform_coupon_definitions_privacy_update` | `platform_coupon_definitions` | `BEFORE UPDATE` |
| `platform_coupon_redemptions_capacity` | `platform_coupon_redemptions` | `BEFORE INSERT` |
| `platform_coupon_redemptions_privacy_insert` | `platform_coupon_redemptions` | `BEFORE INSERT` |
| `platform_coupon_redemptions_privacy_update` | `platform_coupon_redemptions` | `BEFORE UPDATE` |
| `platform_entitlement_events_source_exact` | `platform_entitlement_events` | `BEFORE INSERT` |
| `platform_entitlement_events_privacy_insert` | `platform_entitlement_events` | `BEFORE INSERT` |
| `platform_entitlement_events_privacy_update` | `platform_entitlement_events` | `BEFORE UPDATE` |

Each row must have its exact `tbl_name` and normalized model-generated SQL.
SQLite has no enabled or internal-trigger catalog bit, so presence as one exact
persistent `sqlite_master.type='trigger'` row is the enabled/non-internal
contract. A temp-schema object cannot satisfy a missing persistent trigger.

PostgreSQL requires five non-internal, enabled triggers in `current_schema()`:

| Trigger | Protected relation | Timing/operation (`tgtype`) | Exact function |
| --- | --- | --- | --- |
| `platform_coupon_definitions_privacy_guard` | `platform_coupon_definitions` | `BEFORE INSERT OR UPDATE` (`23`) | `platform_coupon_definitions_privacy_guard_fn` |
| `platform_coupon_redemptions_capacity` | `platform_coupon_redemptions` | `BEFORE INSERT` (`7`) | `platform_coupon_redemptions_capacity_fn` |
| `platform_coupon_redemptions_privacy_guard` | `platform_coupon_redemptions` | `BEFORE INSERT OR UPDATE` (`23`) | `platform_coupon_redemptions_privacy_guard_fn` |
| `platform_entitlement_events_source_exact` | `platform_entitlement_events` | `BEFORE INSERT` (`7`) | `platform_entitlement_events_source_exact_fn` |
| `platform_entitlement_events_privacy_guard` | `platform_entitlement_events` | `BEFORE INSERT OR UPDATE` (`23`) | `platform_entitlement_events_privacy_guard_fn` |

Every PostgreSQL row must have `tgenabled='O'`, `tgisinternal=false`, no `WHEN`,
the exact relation and function schema, exact function name and normalized body,
`plpgsql`, and no `SECURITY DEFINER`. The decision records the exact body hashes.

## Fail-closed validation

SQLite must select `name,tbl_name,sql` from `sqlite_master` for the required
names and compare the sorted row list with the model-derived expected list.
Do not collapse rows into a name-keyed dictionary. Require exactly eight rows,
one per name, with exact relation and normalized SQL.

PostgreSQL must query all rows bearing a required name, without filtering away
wrong-schema or internal rows, through
`pg_trigger -> pg_class -> pg_namespace` and
`pg_trigger -> pg_proc -> pg_namespace`, plus `pg_language`. Compare the row
multiset against the five exact expected records. Require one row per name and
exact relation, schemas, trigger state/type/qualification, function, body,
language, and security state. A correct row plus a same-name row elsewhere is a
duplicate and must refuse.

## Successor boundary and proof

The smallest successor owns only:

- `paper-trader/backend/app/db/migrate.py`
- `paper-trader/backend/tests/test_v0_account_commerce_migration.py`

It must not change models, revision 0049, service behavior, copy/restore
contracts, frontend, or shared publication. Parameterize wrong-relation cases
across all eight SQLite and five PostgreSQL triggers. Add missing, duplicate,
wrong-schema, disabled/internal, wrong timing/operation/WHEN, and wrong
function/schema/body cases. Each refusal must preserve exact head `0049` and
pre/post definition, redemption, and entitlement-event row digests. Exact
unmodified controls must return `0049` without writes.

Run the focused SQLite migration tests and the same migration file on the real
isolated PostgreSQL 16 harness with zero skips. Hash-bind the accepted 444/444
service/migration/copy/restore/health/schema evidence. Rerun broader behavior
only if the implementation escapes the sealed validation seam. Package direct
RED-to-GREEN evidence, protected hashes, architecture validation, and one fresh
independent Critical review. Both SPEC and QUALITY must pass and explicitly
close `V0-CDV-CR-001-R1` before acceptance.

## Gates and nonclaims

Dynamic activation and shared publication remain blocked. Writer quiescence,
one 0049 migration owner, verified backup/clean restore, exact readiness, and
0049-only readers/writers remain mandatory. This capsule authorizes no product
implementation, commit, deployment, provider or money access, production
migration, release-readiness claim, or V0 completion claim.
