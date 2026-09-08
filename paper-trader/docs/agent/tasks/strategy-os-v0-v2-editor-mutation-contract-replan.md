---
{
  "id": "strategy-os-v0-v2-editor-mutation-contract-replan",
  "phase": "v0",
  "status": "accepted",
  "kind": "critical_read_only_v2_editor_authority_replan",
  "goal": "Define the one canonical v2 editor mutation, validation, version, receipt and presentation contract required to make the verified 243-row language constructible without mapping through the incompatible v1 editor.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "The v1/v2 authority mismatch is reproduced; existing v2 persistence/API/validator/resolver and v1 editor seams are mapped; one smallest implementation capsule is sealed for owner-scoped batch mutation, rollback validation, immutable publish/version receipts, undo/redo and presentation-state separation using the single REGISTRY/validate_document/resolve_v2 authorities. No product/test/schema/frontend/control write occurs."},
  "risk_tags": ["critical", "ir-v2", "editor", "canonical-identity", "versioning", "tenant-isolation", "frontend-blocker"],
  "required_docs": [
    {"path": ".agent/runs/strategy-os-v0-frontend-product-acceptance-recovery/catalogue-editor-mapping-audit/report.md", "sections": ["all output"]},
    {"path": ".agent/runs/strategy-os-v0-frontend-product-acceptance-recovery/review/verdict.json", "sections": ["all output"]},
    {"path": "paper-trader/docs/agent/tasks/strategy-os-v0-verified-language-catalogue.md", "sections": ["Terminal Critical-review receipt"]},
    {"path": "paper-trader/docs/agent/tasks/phase3-4-ir-v2-api-contract.md", "sections": ["all output"]},
    {"path": "paper-trader/docs/engineering/decisions/0012-execution-state-ownership.md", "sections": ["2.1 Ownership — who owns which fact"]}
  ],
  "dependency_gate": "The frontend correction is frozen after mapping audit SHA-256 bfbe4e7fe5b5537f9e1886b5b07fcaeb1361dd2a1abfb45f87cbc73cb5475713 proved no v2→v1 adapter. The verified catalogue, v2 validator/resolver/persistence and accepted frontend correction bytes are read-only inputs.",
  "allowed_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-v2-editor-mutation-contract-replan.md", ".agent/runs/strategy-os-v0-v2-editor-mutation-contract-replan"],
  "new_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-v2-editor-mutation-contract-replan.md", ".agent/runs/strategy-os-v0-v2-editor-mutation-contract-replan"],
  "protected_paths": ["paper-trader/backend", "paper-trader/frontend", "/Users/priyanshusaraf/dev/strategy-os-frontend", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/programme/PROGRAMME.json", "paper-trader/scripts/deploy.sh"],
  "scope": [
    "Reproduce why v2 catalogue documents validate/resolve while v1 editor insertion/publication refuses them; record incompatible shared IDs/ports and reject client maps/aliases.",
    "Reuse the one v2 REGISTRY, descriptor/node-contract maps, validate_document, resolve_v2, canonical document address and existing v2 GraphVersion persistence. Do not create a second registry, validator, resolver, hash, graph table or component identity.",
    "Define closed owner-scoped semantic batch commands for add/remove/connect/disconnect/parameter override/output binding, deterministic optimistic revision, rollback-only validation and immutable publish/version receipt.",
    "Keep presentation add/move/layout/viewport/selection outside executable identity with its own optimistic revision and receipt. Undo/redo must invert accepted commands rather than restore arbitrary client JSON.",
    "Define create/read/edit/validate/publish/reload APIs and typed refusals for stale revision, bad port/type/cardinality/cycle/unit/data requirement/capability. v1 editor remains versioned legacy and cannot silently accept v2.",
    "Map exact frontend reactivation contract: authoritative palette row becomes a v2 semantic command using its published node contract/ports; no raw JSON or fixture fallback.",
    "Produce one fresh implementation capsule with exact paths, no-schema decision or exact owner gate, tests, resource/performance/deployability evidence and integrated Critical review."
  ],
  "acceptance": [
    "Authority map proves one v2 identity/validation/version path and explicit v1 compatibility boundary.",
    "Command/receipt/API schemas are closed and cover add/connect/inspect/edit/delete/undo/redo/validate/publish/reload plus presentation separation.",
    "Failure matrix covers cross-owner access, stale/concurrent batches, invalid ports/types/cardinality/cycles/units/capabilities, no-write validation and deterministic replay.",
    "Successor capsule names exact backend/test/frontend integration dependencies without overlapping platform 0046 or reopening accepted IR contracts.",
    "Protected hashes and zero product/control writes are sealed."
  ],
  "test_plan": ["Inventory v1/v2 API/persistence/validator/port contracts read-only; construct valid/invalid v2 command examples; build authority/failure/resource/deployability matrices; validate successor capsule and zero writes."],
  "parallel_budget": 1,
  "assignments": [{"id": "v0_v2_editor_mutation_contract_replan_owner", "agent": "worker", "model": "gpt-5.6-sol", "reasoning_effort": "high", "fork_turns": "none", "mode": "write-evidence-only", "depends_on": [], "read_paths": ["paper-trader/backend/app/ir", "paper-trader/backend/app/api", "paper-trader/backend/tests", "paper-trader/docs/agent/tasks/strategy-os-v0-verified-language-catalogue.md", ".agent/runs/strategy-os-v0-frontend-product-acceptance-recovery/catalogue-editor-mapping-audit"], "write_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-v2-editor-mutation-contract-replan.md", ".agent/runs/strategy-os-v0-v2-editor-mutation-contract-replan"], "output": ".agent/runs/strategy-os-v0-v2-editor-mutation-contract-replan/report.md"}],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "high", "fork_turns": "none", "service_tier": "priority", "routing_note": "Read-only Critical architecture escalation for a missing canonical v2 editor authority."},
  "owner_task": "/root/v2_editor_contract_replan",
  "review": {"required": false, "assignment_id": "v0_v2_editor_mutation_contract_replan_owner", "agent": "owner", "model": "gpt-5.6-sol", "reasoning_effort": "high", "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c", "package": ".agent/runs/strategy-os-v0-v2-editor-mutation-contract-replan/review-package.json", "review_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-v2-editor-mutation-contract-replan.md", ".agent/runs/strategy-os-v0-v2-editor-mutation-contract-replan"], "exclude_paths": ["paper-trader/backend", "paper-trader/frontend", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/programme/PROGRAMME.json", "paper-trader/scripts/deploy.sh"], "output": ".agent/runs/strategy-os-v0-v2-editor-mutation-contract-replan/report.md", "verdicts": ["AUTHORITY_MAP", "COMMAND_CONTRACT", "SUCCESSOR_CAPSULE"], "max_rechecks": 0},
  "owner_gates": ["No product/frontend/schema/dependency write; root must accept and materialize successor before frontend resumes.", "Any proposal that maps v2 IDs/ports through v1, creates a second IR authority or widens live/execution authority stops."],
  "stop_conditions": ["A safe editor requires changing accepted v2 identity/validator/resolver semantics rather than adding the missing command/version layer.", "A schema/dependency/licence decision or active path collision is required."],
  "deployment_impact": {"classification": "none for replan; successor is an architecture-changing authenticated API/editor contract requiring deterministic build/browser/performance/rollback evidence", "required_evidence": "Zero writes now; exact successor deployment obligations. No deployment claim."},
  "decision": "KEEP + HARDEN",
  "delivery_status": "accepted",
  "schema_decision": {
    "semantic": "reuse owner-scoped GraphArtifact draft/revision and immutable IrV2GraphVersion; no new semantic table",
    "presentation": "one additive USER-plane ir_v2_editor_presentations table in planned linear revision 0047 after terminally accepted and released platform 0046",
    "backfill": "none; absent row is empty presentation revision 0",
    "collision_gate": "strategy-os-v0-platform-operations-persistence owns shared 0046 model/copy/restore/migration paths until its terminal review passes"
  },
  "output_artifacts": {
    "report": {"path": ".agent/runs/strategy-os-v0-v2-editor-mutation-contract-replan/report.md", "sha256": "cd2b61dded96ddd7ba88d9d18701a43b74da978b2302b8c43af66b4de98ded35"},
    "successor_capsule": {"path": ".agent/runs/strategy-os-v0-v2-editor-mutation-contract-replan/successor-capsule.json", "sha256": "8ca0d31e9297d2bfb4aed19b62034cbabd163404dbc196b8fee189c7a3a3aa9c", "id": "strategy-os-v0-v2-editor-mutation-contract-correction"},
    "evidence_manifest": {"path": ".agent/runs/strategy-os-v0-v2-editor-mutation-contract-replan/evidence-manifest.json", "sha256": "856ed398d16557960940a28664e0add851d596091cf3f2e5805349731b5c30fc"},
    "review_package": {"path": ".agent/runs/strategy-os-v0-v2-editor-mutation-contract-replan/review-package.json", "sha256": "f55b91cd087ef55e2d8d46d2ec8d75efd4acc3b605205ac2caef061a3769860a"},
    "replan_seal": {"path": ".agent/runs/strategy-os-v0-v2-editor-mutation-contract-replan/replan-seal.json", "sha256": "ede87cfe1f0284c9a497b6f0abbc8494cc956626b2f8908fb7df532bda135532"}
  },
  "nonclaims": ["No v2 editor, frontend acceptance, graph publication, deployment or V0 completion is implemented by this replan."]
}
---

# V0 v2 editor mutation contract replan

Define the missing canonical v2 editing/versioning layer. Do not translate the
verified v2 language through the incompatible legacy v1 editor.

## Terminal replan receipt

Verdict: `AUTHORITY MAP PASS / COMMAND CONTRACT KEEP + HARDEN / SUCCESSOR CAPSULE SEALED`.

A fresh current-byte probe reproduced the boundary. A canonical v2 graph using
`logic.and@1` and `logic.or@1` validates and resolves. The legacy editor refuses
`analytical.close@2`, selects the incompatible v1 `logic.and@1` contract, and
refuses v2 `value -> input` ports. The only two exact shared keys are dangerous
collisions, not aliases.

The sealed contract uses one closed semantic batch over the owner-scoped
`GraphArtifact` draft revision, then the existing `REGISTRY`,
`validate_document`, `resolve_v2`, and canonical v2 addresses. Rollback
validation uses the identical path and always writes zero. Publication inserts
the existing immutable `IrV2GraphVersion` and advances the draft pointers in one
transaction. Undo, redo, and replay use forward/inverse commands and exact
address checks, never replacement JSON.

Presentation positions, groups, viewport, and selection use a separate command
and revision. The legacy layout table cannot be reused because its foreign key
targets v1 `graph_versions`. The successor therefore plans one additive
`ir_v2_editor_presentations` table in linear revision `0047`, only after the
platform `0046` capsule receives terminal acceptance and releases shared paths.
It performs no backfill. V1 remains explicit versioned legacy.

The backend successor remains blocked on root acceptance and the `0046` release.
Frontend correction remains frozen until that successor receives integrated
Critical `SPEC PASS / QUALITY PASS`. Product, test, schema, migration, frontend,
control, provider, live, execution, money, credential, VPS, and deployment writes
for this replan are zero. The 1,216-file protected source/config baseline and
final aggregate are byte-identical at
`4aba02c9aa34e4e8ff44610a4a9f0a2ab75ab667117accb4ebc39a82100e6eee`.

The report is `.agent/runs/strategy-os-v0-v2-editor-mutation-contract-replan/report.md`.
No v2 editor implementation, frontend acceptance, graph publication, research
admission, provider capability, deployability, production readiness, deployment,
or V0 completion follows from this receipt.
