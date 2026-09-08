---
{
  "id": "strategy-os-v0-v2-editor-edge-identity-replan",
  "phase": "v0",
  "status": "accepted",
  "kind": "critical_read_only_v2_edge_identity_replan",
  "goal": "Replan the exhausted V2 editor lineage so a sealed inverse restores every validator-accepted imported edge identifier byte-for-byte without exposing an unsealed client-controlled identity seam or creating a second graph identity authority.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "The immutable V0-V2EM-R1-001 HTTP and pure counterexamples are reproduced; accepted imported, editor-created and receipt-replayed edge identity paths are mapped; one smallest authority-preserving inverse design and fresh correction capsule are sealed with exact paths, mutations, all affected identity/resource/tenant/migration gates and a fresh Critical-review lineage. No product/test/schema/migration/frontend/control write occurs."},
  "risk_tags": ["critical", "ir-v2", "edge-identity", "receipt-replay", "canonical-identity", "tenant-lineage", "resource-boundary", "frontend-blocker"],
  "depends_on": ["strategy-os-v0-v2-editor-mutation-contract-correction"],
  "dependency_gate": {"predecessor_recheck_verdict_sha256": "1c1c520f6be30fe1c46716dc13048fcbdff5a53f543652e25f98f10c614f4318", "finding": "V0-V2EM-R1-001", "rechecks_remaining": 0, "migration_head": "0047", "frozen_0047_sha256": "71743f2bf014575b0ea4586e90f16a30e8ec7f7c32c02e32f4d9c3e1b4bc2fe9", "frontend": "frozen"},
  "required_docs": [
    {"path": ".agent/runs/strategy-os-v0-v2-editor-mutation-contract-correction/review/recheck-verdict.json", "sections": ["all output"]},
    {"path": ".agent/runs/strategy-os-v0-v2-editor-mutation-contract-replan/command-contract.md", "sections": ["all output"]},
    {"path": "paper-trader/docs/agent/tasks/strategy-os-v0-v2-editor-mutation-contract-correction.md", "sections": ["V0 v2 editor mutation contract correction"]}
  ],
  "allowed_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-v2-editor-edge-identity-replan.md", ".agent/runs/strategy-os-v0-v2-editor-edge-identity-replan"],
  "new_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-v2-editor-edge-identity-replan.md", ".agent/runs/strategy-os-v0-v2-editor-edge-identity-replan"],
  "protected_paths": ["paper-trader/backend", "paper-trader/frontend", "/Users/priyanshusaraf/dev/strategy-os-frontend", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/programme/PROGRAMME.json", "paper-trader/scripts/deploy.sh"],
  "scope": [
    "Reproduce the exact pure and authenticated HTTP imported-edge counterexamples from the consumed recheck and freeze their pre/post graph bytes, edge IDs, addresses, revisions and refusal state.",
    "Map edge identity creation and acceptance through v2 document import, GraphArtifact draft persistence, add/connect/remove commands, server-sealed inverse receipts, undo/redo/replay, validate_document, resolve_v2 and immutable publication.",
    "Choose one authority-preserving design that restores the original validator-accepted edge_id exactly while keeping ordinary client EDIT closed, receipt lineage mandatory and a single canonical v2 validator/hash authority.",
    "Reject silent edge rekeying, graph-address exceptions, raw document replacement, migration/schema changes, unsealed client edge identity, v1 translation and a second registry/validator/resolver/hash.",
    "Specify at-limit/first-over inverse/resource behavior, imported/editor-created controls, tampered/foreign receipt refusals, cold replay, tenant isolation and address equality through SQLite/PostgreSQL without changing 0047.",
    "Produce a fresh correction capsule with exact paths, RED/GREEN/mutation evidence, unchanged migration/protected hashes and one new Critical review lineage before frontend reactivation."
  ],
  "acceptance": [
    "One edge-identity authority map covers import, editor creation, inverse construction, receipt verification, replay and publication.",
    "The successor design restores arbitrary validator-accepted imported edge IDs and editor-derived edge IDs byte-for-byte with identical content/graph addresses.",
    "Ordinary client edits cannot forge identity; only a verified server-sealed lineage may restore a prior edge ID, and tampered/foreign receipts refuse atomically.",
    "Resource ceilings admit only edits whose exact inverse remains replayable; at-limit and first-over behavior is explicit.",
    "Fresh successor capsule, zero-write seal and deployment disposition are complete."
  ],
  "test_plan": ["Read-only reproduce reviewer pure/HTTP failures; freeze identity/address truth tables; compare sealed internal-command versus closed restoration-token designs; produce attack/resource/migration/deployability matrices; validate successor capsule and protected zero-write seal."],
  "parallel_budget": 1,
  "assignments": [{"id": "v0_v2_editor_edge_identity_replan_owner", "agent": "worker", "model": "gpt-5.6-sol", "reasoning_effort": "high", "fork_turns": "none", "mode": "write-evidence-only", "depends_on": [], "read_paths": ["paper-trader/backend/app/editor/v2_mutations.py", "paper-trader/backend/app/editor/v2_editor_store.py", "paper-trader/backend/app/api/ir_v2_edit_routes.py", "paper-trader/backend/app/editor/graph_artifacts.py", "paper-trader/backend/app/ir/formats/v2.py", "paper-trader/backend/app/ir/resolve.py", "paper-trader/backend/app/ir/v2_graph_versions.py", "paper-trader/backend/tests/test_ir_v2_editor_mutations.py", "paper-trader/backend/tests/test_ir_v2_editor_api.py", ".agent/runs/strategy-os-v0-v2-editor-mutation-contract-correction/review"], "write_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-v2-editor-edge-identity-replan.md", ".agent/runs/strategy-os-v0-v2-editor-edge-identity-replan"], "output": ".agent/runs/strategy-os-v0-v2-editor-edge-identity-replan/report.md"}],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "high", "fork_turns": "none", "service_tier": "priority", "reason": "Second critical rejection crosses canonical imported edge identity, sealed replay lineage and frontend construction semantics; a bounded read-only architecture escalation is proportionate."},
  "owner_task": "/root/v2_editor_edge_identity_replan",
  "review": {"required": false, "assignment_id": "v0_v2_editor_edge_identity_replan_owner", "agent": "owner", "model": "gpt-5.6-sol", "reasoning_effort": "high", "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c", "package": ".agent/runs/strategy-os-v0-v2-editor-edge-identity-replan/review-package.json", "review_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-v2-editor-edge-identity-replan.md", ".agent/runs/strategy-os-v0-v2-editor-edge-identity-replan"], "exclude_paths": ["paper-trader/backend", "paper-trader/frontend", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/programme/PROGRAMME.json", "paper-trader/scripts/deploy.sh"], "output": ".agent/runs/strategy-os-v0-v2-editor-edge-identity-replan/report.md", "verdicts": ["IDENTITY_AUTHORITY", "REPLAY_CONTRACT", "SUCCESSOR_CAPSULE"], "max_rechecks": 0},
  "owner_gates": ["Read-only; no backend/test/schema/migration/frontend/control/deploy write.", "No new parser/dependency/edge authority/raw-document replacement or weakened tenant/receipt seal."],
  "stop_conditions": ["Exact restoration requires changing accepted v2 identity/hash/validator semantics, a schema migration, unsealed client identity control or a second authority.", "A protected-path write or active owner collision is required."],
  "deployment_impact": {"classification": "none for replan", "successor_ceiling": "locally runnable only after exact identity/replay/migration evidence and fresh Critical review", "release_deployable": false, "production_rehearsed": false, "deployed": false},
  "decision": "KEEP + HARDEN",
  "delivery_status": "accepted_successor_materialized",
  "output_artifacts": {
    "report": {"path": ".agent/runs/strategy-os-v0-v2-editor-edge-identity-replan/report.md", "sha256": "472bc77b95ffd2d3beb4d2d317879ac3b0af3615ac4f9ca8041a0c079bfd9472"},
    "authority_map": {"path": ".agent/runs/strategy-os-v0-v2-editor-edge-identity-replan/edge-identity-authority-map.md", "sha256": "c6ecc77f13b3a56dc8cb44cf4db974cdf56ec416633cd099e93e48a9afb1801f"},
    "receipt_contract": {"path": ".agent/runs/strategy-os-v0-v2-editor-edge-identity-replan/receipt-and-command-contract.md", "sha256": "ef3c8c5331e558869be9f5f1528f01995d50c85403c21b26baf48ffde1b4087d"},
    "attack_resource_cas_matrix": {"path": ".agent/runs/strategy-os-v0-v2-editor-edge-identity-replan/attack-resource-cas-matrix.md", "sha256": "8420de2d8df9dc1126ff0a4c92ea77f12ad856bff398263c6bcf448949d438a0"},
    "deployment_impact": {"path": ".agent/runs/strategy-os-v0-v2-editor-edge-identity-replan/deployment-impact.md", "sha256": "938c59b57c60caeb698063bcbe57e9358ee70e4882eef4a0bf921d28378e473b"},
    "successor_capsule": {"path": ".agent/runs/strategy-os-v0-v2-editor-edge-identity-replan/successor-correction-capsule.md", "sha256": "ee9d0564f5f8c8f5931d5d7979eb9b6fec22b1d4fb26480ad1713d0f73c3e195", "id": "strategy-os-v0-v2-editor-edge-identity-correction"}
  },
  "nonclaims": ["No V2 editor acceptance, frontend reactivation, research admission, provider/execution/live/money authority, release readiness, deployment or V0 completion follows."]
}
---

# V0 V2 editor edge-identity replan

Replan exact inverse restoration for validator-accepted imported edge identities.
Keep backend, migration 0047, frontend and deployment paths frozen.

## Terminal replan receipt

The read-only owner reproduced `V0-V2EM-R1-001` from the frozen inherited bytes in pure and authenticated mock/paper HTTP paths. The 31-edge at-limit case accepted a 32-command inverse but rekeyed every imported edge and changed both content and graph addresses. The 32-edge first-over case refused atomically. The authenticated route accepted `caller.edge.identity`, committed removal at revision 1, then refused the exact receipt-driven inverse with `REPLAY_DIVERGED` while preserving the reduced revision-1 state.

Decision: `KEEP + HARDEN`. Public EDIT remains unable to supply edge identity. A proposed private `restore_edge_from_receipt` command carries the complete removed canonical edge only inside a semantic receipt v2 whose domain-separated server MAC, content address, owner, project, graph, registry, version, revision, intent, commit state, commands, and source/target addresses all verify before execution. The existing unkeyed receipt hash is explicitly insufficient server provenance. Canonical V2 validation, resolution, hashing, import, and immutable publication semantics remain unchanged.

The fresh proposed correction capsule is `.agent/runs/strategy-os-v0-v2-editor-edge-identity-replan/successor-correction-capsule.md`. It requires root acceptance, RED/GREEN and mutation evidence, random per-run test secrets with no product fallback, same-secret cold replay, fail-closed rotation, SQLite/PostgreSQL CAS, unchanged 0047 and protected hashes, and one new integrated Critical SPEC/QUALITY review before frontend reactivation.

No product, test, schema, migration, frontend, CURRENT, PROGRAMME, deployment, provider, execution, live, money, credential, or VPS path changed. This receipt gives no V2 editor acceptance, frontend acceptance, release readiness, deployment, or V0-complete claim.
