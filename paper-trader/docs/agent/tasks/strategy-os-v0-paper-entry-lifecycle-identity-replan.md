---
{
  "id": "strategy-os-v0-paper-entry-lifecycle-identity-replan",
  "phase": "v0",
  "status": "accepted",
  "kind": "critical_read_only_paper_money_identity_replan",
  "goal": "Replan the rejected 0045 Paper charge-allocation grouping around one canonical durable entry lifecycle identity so independent equal-valued entries never merge, partial exits reconstruct exactly and historical NULL remains truthful without repurposing PositionCampaign.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "The immutable V0-PCA-R1-001 counterexample is reproduced; every Paper entry/reinforcement/partial/full/retry path and existing intent/campaign/tranche fact is mapped; one canonical lifecycle-identity decision and fresh correction capsule are sealed with migration compatibility, legacy NULL, collision/concurrency and review gates. No product, test, schema, migration, control, frontend or deployment write occurs."
  },
  "risk_tags": ["critical", "paper-money", "lifecycle-identity", "entry-intent", "partial-close", "restart", "schema", "migration", "historical-null"],
  "required_docs": [
    {"path": ".agent/runs/strategy-os-v0-paper-charge-authority-and-legacy-identity-correction/review/recheck-verdict.json", "sections": ["all output"]},
    {"path": "paper-trader/docs/agent/tasks/strategy-os-v0-paper-charge-authority-and-legacy-identity-correction.md", "sections": ["V0 Paper charge authority and legacy identity correction"]},
    {"path": "paper-trader/docs/engineering/decisions/0012-execution-state-ownership.md", "sections": ["2.1 Ownership — who owns which fact", "3. The smallest safe paper/shadow deployment architecture"]},
    {"path": "paper-trader/docs/engineering/decisions/0018-position-campaign-tranche-lineage.md", "sections": ["Decision", "Invariants", "Legacy rows and migration", "Required evidence"]},
    {"path": "paper-trader/docs/agent/DEPLOYABILITY.md", "sections": ["Current verdict", "Open obligations", "V1 release gate"]}
  ],
  "dependency_gate": "The fresh 0045 Paper charge-authority capsule exhausted its focused recheck at verdict SHA-256 064ea0541651503214f2d11abc4e4308bcac9d890fae8b50db807cf626b029ea. Its product/test/schema bytes are frozen; revision 0045 is unaccepted and all successors remain blocked.",
  "allowed_paths": [
    "paper-trader/docs/agent/tasks/strategy-os-v0-paper-entry-lifecycle-identity-replan.md",
    ".agent/runs/strategy-os-v0-paper-entry-lifecycle-identity-replan"
  ],
  "new_paths": [
    "paper-trader/docs/agent/tasks/strategy-os-v0-paper-entry-lifecycle-identity-replan.md",
    ".agent/runs/strategy-os-v0-paper-entry-lifecycle-identity-replan"
  ],
  "protected_paths": [
    "paper-trader/docs/agent/CURRENT.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/backend",
    "paper-trader/frontend",
    "/Users/priyanshusaraf/dev/strategy-os-frontend",
    "paper-trader/scripts/deploy.sh"
  ],
  "scope": [
    "Reproduce V0-PCA-R1-001 exactly: two valid independent equal-valued Paper entries with NULL entry_intent_id must remain distinct through close, receipt reconstruction and restart.",
    "Trace open/reinforce/manual/strategy-driven/futures/options/equity, full/partial/remaining exit, stale retry and restart paths through ExecutionIntent, Position, Trade, PositionCampaign, PositionTranche and FillAllocation. State which fact owns one entry lifecycle and which are operational/legacy only.",
    "Evaluate mandatory unique persisted entry_intent_id for every new Paper entry, a new narrowly named immutable Paper charge-allocation lifecycle address, or another existing canonical fact. Reject timestamps/prices/instruments/quantities, labels and other heuristic tuples.",
    "Freeze ADR 0018 PositionCampaign meaning and reserve future EconomicPosition. Do not make PositionCampaign a charge-allocation id, add order lifecycle to Position, create a second execution intent, or infer campaigns/intents for legacy rows.",
    "Preserve historical NULL entry identity. Legacy exits must remain risk-reducing and truthful; unknown lifecycle may limit aggregation/analytics but cannot strand an open Paper position or invent attribution.",
    "Define exact uniqueness, FK/content-address, copy/restore, partial/reinforcement, retry, concurrency and migration behavior. If revision 0045 must change, it remains the unaccepted single head; no 0046 or branch migration may be created by this replan.",
    "Output one fresh correction capsule with exact allowed/protected paths, RED/GREEN/mutation matrix, deployment evidence and new Critical review lineage. No implementation or reviewer launch."
  ],
  "acceptance": [
    "An authority/state-flow map covers every current Paper entry and exit path and proves why the chosen identity is canonical, durable and unique per independent lifecycle.",
    "The decision returns KEEP, KEEP + HARDEN, REFACTOR, REPLACE or DEFER and explicitly rejects heuristic tuple expansion and PositionCampaign repurposing.",
    "Equal-valued/time-coincident entries, same/different intents, reinforcement, partial slices, remaining Position, retry/restart and two-owner/account/deployment cases have exact successor tests and mutations.",
    "Legacy NULL behavior and migration/copy/restore semantics are exact; no backfill/inference occurs and exits remain available.",
    "One validator-ready fresh correction capsule and collision/dependency receipt are sealed with zero product/test/schema/control writes."
  ],
  "test_plan": [
    "Run the immutable reviewer counterexample read-only and inventory entry lifecycle call sites, columns, uniqueness/FKs and persisted facts.",
    "Build candidate decision and failure-hypothesis matrices covering identity collision, partial/reinforcement allocation, legacy NULL and restart/concurrency.",
    "Validate protected hashes, zero writes, architecture and successor capsule metadata; seal report/review package."
  ],
  "parallel_budget": 1,
  "assignments": [
    {
      "id": "v0_paper_entry_lifecycle_identity_replan_owner",
      "agent": "worker",
      "model": "gpt-5.6-sol",
      "reasoning_effort": "high",
      "fork_turns": "none",
      "mode": "write-evidence-only",
      "depends_on": [],
      "reason": "Second Critical rejection crosses Paper money allocation, execution-intent authority, ADR 0018 lineage and an unaccepted migration head.",
      "read_paths": [
        ".agent/runs/strategy-os-v0-paper-charge-authority-and-legacy-identity-correction",
        "paper-trader/backend/app/engine/broker.py",
        "paper-trader/backend/app/db/models.py",
        "paper-trader/backend/app/execution",
        "paper-trader/backend/app/core",
        "paper-trader/backend/migrations/versions/20260830_0045_paper_charge_authority.py",
        "paper-trader/backend/tests",
        "paper-trader/docs/engineering/decisions/0012-execution-state-ownership.md",
        "paper-trader/docs/engineering/decisions/0018-position-campaign-tranche-lineage.md"
      ],
      "write_paths": [
        "paper-trader/docs/agent/tasks/strategy-os-v0-paper-entry-lifecycle-identity-replan.md",
        ".agent/runs/strategy-os-v0-paper-entry-lifecycle-identity-replan"
      ],
      "output": ".agent/runs/strategy-os-v0-paper-entry-lifecycle-identity-replan/report.md"
    }
  ],
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "high",
    "fork_turns": "none",
    "service_tier": "priority",
    "routing_note": "Bounded read-only architecture escalation after a second Critical Paper money/identity rejection."
  },
  "owner_task": "01a04c7c-257a-7210-9dd3-f639c661db00",
  "review": {
    "required": false,
    "assignment_id": "v0_paper_entry_lifecycle_identity_replan_owner",
    "agent": "owner",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c",
    "package": ".agent/runs/strategy-os-v0-paper-entry-lifecycle-identity-replan/review-package.json",
    "review_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-paper-entry-lifecycle-identity-replan.md", ".agent/runs/strategy-os-v0-paper-entry-lifecycle-identity-replan"],
    "exclude_paths": ["paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/programme/PROGRAMME.json", "paper-trader/backend", "paper-trader/frontend", "paper-trader/scripts/deploy.sh"],
    "output": ".agent/runs/strategy-os-v0-paper-entry-lifecycle-identity-replan/report.md",
    "verdicts": ["AUTHORITY_MAP", "IDENTITY_DECISION", "SUCCESSOR_CAPSULE"],
    "max_rechecks": 0
  },
  "owner_gates": [
    "This replan owns no product/test/schema/migration/control/frontend/deployment path and cannot accept or modify 0045.",
    "Any proposal that changes live authority, reuses PositionCampaign contrary to ADR 0018, invents legacy identity or requires production/provider access stops for root/owner direction."
  ],
  "stop_conditions": [
    "No existing or additive identity can distinguish independent Paper entry lifecycles without a second intent/deployment/position authority.",
    "Safe legacy exits require backfill/inference, or the design would block risk-reducing exits.",
    "A proposed write overlaps another active owner or requires revision 0046/branch migration before 0045 acceptance."
  ],
  "deployment_impact": {
    "classification": "none for replan; successor may amend unaccepted 0045 and Paper runtime identity, requiring fresh migration/restart/copy/restore evidence",
    "required_evidence": "Exact single-head 0045 lineage, mixed-version policy, legacy NULL preservation, restart/reconciliation and rollback/forward repair. No deployment claim."
  },
  "decision": "KEEP + HARDEN",
  "delivery_status": "accepted",
  "canonical_lifecycle_identity": "execution_intents.client_intent_id",
  "output_artifacts": {
    "report": {
      "path": ".agent/runs/strategy-os-v0-paper-entry-lifecycle-identity-replan/report.md",
      "sha256": "d5cf1f16d6fb1df427256b702cf231d5bd3ce0841a2b76e4d4bdd36a79397711"
    },
    "successor_capsule": {
      "path": ".agent/runs/strategy-os-v0-paper-entry-lifecycle-identity-replan/successor-capsule.json",
      "sha256": "325cd3088e3276f1ffbb877b30e9b81aa9c981dbfa46aa549fd1d455c95cdebc",
      "id": "strategy-os-v0-paper-entry-lifecycle-identity-correction"
    },
    "evidence_manifest": {
      "path": ".agent/runs/strategy-os-v0-paper-entry-lifecycle-identity-replan/evidence-manifest.json",
      "sha256": "e865ad17c7980b47ae1f87d13e23c3589d9e7ce31c2162da32b37385d4ea8a17"
    },
    "review_package": {
      "path": ".agent/runs/strategy-os-v0-paper-entry-lifecycle-identity-replan/review-package.json",
      "sha256": "3bdb7afdd4487d7d1b6b5b36d67ec7985d81a4d8056788d822c1aaded64f2eb5"
    },
    "replan_seal": {
      "path": ".agent/runs/strategy-os-v0-paper-entry-lifecycle-identity-replan/replan-seal.json",
      "sha256": "c8c6323e0b5ccfae8861364afac86c32bf86ff7634926d846b379dad89c72837"
    }
  },
  "nonclaims": [
    "No 0045 acceptance, Paper runtime completion, frontend, live execution, deployment, production readiness or V0 completion follows from this replan."
  ]
}
---

# V0 Paper entry lifecycle identity replan

The rejected 0045 lineage cannot be corrected again. This read-only capsule
selects one canonical durable identity for independent Paper entry lifecycles
without repurposing PositionCampaign or inferring legacy attribution.

## Terminal replan receipt

Verdict: `AUTHORITY MAP PASS / IDENTITY DECISION KEEP + HARDEN / SUCCESSOR CAPSULE SEALED`.

The immutable V0-PCA-R1-001 fixture reproduced against the frozen current
product bytes. Every current Paper entry path bypasses the existing durable
`ExecutionIntent`: strategy options and equity omit its optional argument,
manual options omit it through `manual_open`, and futures expose no argument.
Full and partial exits already copy Position identity to Trade, but today that
identity is NULL. The heuristic equality tuple therefore merges independent
equal-valued entries after restart.

The selected successor makes `ExecutionIntent.client_intent_id` mandatory for
every new Paper entry and uses it as the sole lifecycle selector. Position and
all Trade slices copy the exact ID. Scope facts validate the selected rows but
never become a fallback key. Current stop/target reinforcement keeps the ID
because it changes no quantity. ADR 0018 PositionCampaign, PositionTranche and
FillAllocation meanings remain frozen and no legacy lineage is inferred.

Historical NULL stays NULL. Legacy full and partial exits remain available;
receipts report the entry lifecycle and authority as unknown and do not scan
sibling NULL rows. The fresh successor amends the unaccepted single-head 0045
in place so known Paper entry-schedule authority requires the existing intent
FK. It adds no lifecycle column/table/address, 0046 or branch migration. Stale
rejected-0045 catalogs and mixed writers refuse.

The evidence-backed successor is
`.agent/runs/strategy-os-v0-paper-entry-lifecycle-identity-replan/successor-capsule.json`.
No implementation or reviewer was launched. Product, test, schema, migration,
control, frontend and deployment writes are zero; the protected-set digest is
identical at baseline and closure.
