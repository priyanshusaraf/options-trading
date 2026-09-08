---
{
  "id": "phase4-resolved-topology-identity-correction",
  "phase": "phase4",
  "status": "accepted",
  "goal": "Close CUR-H2 by making resolved Component IR v2 identity complete for every execution-relevant topology fact and proving fresh-process refusal of stale receipts.",
  "goal_contract": {
    "create_before_work": true,
    "owner_authorization": "The accepted Phase 4 authority-foundation architecture correction authorizes this serial CUR-H2 correction only after its dependency gate. Authority is limited to the listed resolver, graph-version, test, and evidence paths; schema, provider, runtime enablement, frontend, deployment, production, live, and money boundaries remain closed.",
    "stopping_condition": "Complete only after every execution-relevant resolved-topology fact enters one canonical address, every assigned adversarial row has direct identity-change or refusal evidence, and a fresh process reconstructs the topology and rejects stale receipts before the retained V2_RUNTIME_UNAVAILABLE boundary. Stop with the goal active at any named owner gate or unresolved acceptance failure."
  },
  "risk_tags": ["high", "canonical-identity", "ir-v2", "fresh-process"],
  "required_docs": [{"path": "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md", "sections": ["3. One accepted executable architecture", "13. Authority-foundation correction contract"]}, {"path": "paper-trader/docs/superpowers/plans/phase4-strategy-os.md", "sections": ["8. Authority-correction serial route"]}],
  "dependency_gate": "phase4-authority-foundation-architecture-correction",
  "allowed_paths": [
    "paper-trader/backend/app/ir/resolve.py",
    "paper-trader/backend/app/ir/v2_graph_versions.py",
    "paper-trader/backend/tests/test_phase4_resolved_topology_identity.py",
    ".agent/runs/phase4-resolved-topology-identity-correction"
  ],
  "nonclaims": ["No schema, provider, runtime, frontend, deployment, live, or money authority.", "The stable V2_RUNTIME_UNAVAILABLE refusal remains required."],
  "owner_gates": ["Stop if closure requires a second resolver/hash/IR, schema edit, provider/runtime work, or presentation state in executable identity."],
  "stop_conditions": ["Any semantic topology mutation leaves the address unchanged or a fresh loader accepts a stale receipt.", "Protected hashes or out-of-scope paths change."],
  "deployment_impact": {"classification": "schema-free-resolved-identity-hardening", "required_evidence": "No dependency/config/schema/service change; fresh-process topology recomputation and refusal; SQLite and PostgreSQL are unaffected."},
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "service_tier": "default"},
  "parallel_budget": 0,
  "assignments": [],
  "adversarial_rows": ["ADV-001", "ADV-017", "ADV-018", "ADV-019", "ADV-020", "ADV-024", "ADV-025"],
  "acceptance": [
    "resolved-v2-topology/2 canonical bytes include authored address, registry payload/address, implementation/declaration closures, nodes, edges, bundles, assembly/order, inputs, outputs, defaults, compound lowering, bindings, member types, and provenance",
    "edge-only, order, default, boundary, binding, type, and provenance mutations change identity and kill stale receipt reuse",
    "a writer process persists the receipt, exits, and a fresh real loader reruns resolution before reaching V2_RUNTIME_UNAVAILABLE",
    "legacy v1 identity and presentation exclusion remain unchanged"
  ],
  "test_plan": ["Produce one real-path ledger entry for every adversarial_rows ID, including seam, process boundary, expected refusal/identity change, observed result, and artifact address; focused topology identity and fresh-process tests; protected hashes; scoped diff; logged architecture validation."],
  "review": {"required": false, "assignment_id": "phase4_resolved_topology_owner", "agent": "owner", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "base_sha": "HEAD", "package": ".agent/review-package.json", "review_paths": ["paper-trader/backend/app/ir/resolve.py","paper-trader/backend/app/ir/v2_graph_versions.py","paper-trader/backend/tests/test_phase4_resolved_topology_identity.py"], "exclude_paths": [], "output": ".agent/runs/phase4-resolved-topology-identity-correction/owner/report.md", "verdicts": ["IMPLEMENTATION"]}
}
---

# Phase 4 resolved-topology identity correction

Own only CUR-H2 and the listed paths. Preserve the accepted resolver. Replace the incomplete node-only address payload with the closed document in design §13.1. The loader must reconstruct and compare that document after process death. Design §13.3 row IDs in `adversarial_rows` are mandatory individual evidence cases, not a grouped mutation test. Record every killed mutation and retain the pre-runtime refusal.
