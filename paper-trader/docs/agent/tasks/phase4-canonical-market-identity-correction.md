---
{
  "id": "phase4-canonical-market-identity-correction",
  "phase": "phase4",
  "status": "accepted",
  "goal": "Close CUR-C2, CUR-C3, and CUR-H1 with exact canonical underlier identity, separate provider entity/product/contract identity, distinct raw and normalized observations, and additive execution persistence.",
  "goal_contract": {
    "create_before_work": true,
    "owner_authorization": "The accepted Phase 4 authority-foundation architecture correction authorizes this serial CUR-C2, CUR-C3, and CUR-H1 correction only after its dependency gate. Authority is limited to the listed canonical-market models, migration, test, and evidence paths; provider adapters, runtime enablement, frontend, deployment, production, live, and money boundaries remain closed.",
    "stopping_condition": "Complete only after canonical physical-instrument and exact economic-underlier identity, provider entity/product/contract separation, and distinct raw and normalized observation facts have immutable canonical bytes and addresses; additive execution persistence survives fresh install, supported upgrade, restart, and atomicity checks with SQLite and disposable PostgreSQL parity; and every assigned adversarial row has direct refusal or identity-change evidence. Stop with the goal active at any named owner gate or unresolved acceptance failure."
  },
  "risk_tags": ["critical", "canonical-identity", "provider-provenance", "migration"],
  "required_docs": [{"path": "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md", "sections": ["5. Canonical instrument and market-truth model", "6. Data observations, alignment, and causality", "13. Authority-foundation correction contract"]}, {"path": "paper-trader/docs/superpowers/plans/phase4-strategy-os.md", "sections": ["8. Authority-correction serial route"]}, {"path": "paper-trader/docs/agent/DEPLOYABILITY.md", "sections": ["Open obligations", "Phase 4 ownership"]}],
  "dependency_gate": "phase4-resolved-topology-identity-correction",
  "allowed_paths": [
    "paper-trader/backend/app/market_truth/identity.py",
    "paper-trader/backend/app/market_data/observations.py",
    "paper-trader/backend/app/db/models.py",
    "paper-trader/backend/migrations/versions/20260817_0038_phase4_authority_facts.py",
    "paper-trader/backend/tests/test_phase4_canonical_market_identity.py",
    "paper-trader/backend/tests/test_phase4_authority_execution_migration.py",
    "paper-trader/backend/tests/test_phase4_market_truth_persistence.py",
    ".agent/runs/phase4-canonical-market-identity-correction"
  ],
  "nonclaims": ["Schema installation does not grant C4 truth, capability, or assessment authority.", "No provider adapter, credential, entitlement inference, feed correctness, runtime, deployment, live, or money claim."],
  "owner_gates": ["Stop before provider adapter/network/credential work or if entity, product, contract, alias, raw observation, normalized observation, physical instrument, or underlier collapse into one identifier."],
  "stop_conditions": ["A derivative can use a label/token as underlier; raw and normalized facts share a type/address; a generic JSON row or copied digest reloads as authority; SQLite passes while PostgreSQL fails."],
  "deployment_impact": {"classification": "additive-execution-authority-schema", "required_evidence": "Execution 0037->0038 fresh/upgrade/restart, model-DDL parity, exact head, atomicity, constraints/triggers, legacy-unverified refusal, downgrade refusal on SQLite and disposable PostgreSQL 16."},
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "service_tier": "default"},
  "parallel_budget": 0,
  "assignments": [],
  "adversarial_rows": ["ADV-001", "ADV-002", "ADV-003", "ADV-009", "ADV-010", "ADV-011", "ADV-012", "ADV-013", "ADV-014", "ADV-015", "ADV-016", "ADV-017", "ADV-018", "ADV-020", "ADV-021", "ADV-022", "ADV-023", "ADV-025", "ADV-026", "ADV-027"],
  "acceptance": [
    "closed canonical-instrument/1 binds the exact economic_underlier_address and exact derivative terms",
    "provider-entity/1, provider-product/1, and owner-scoped provider-contract/1 have separate addresses and equality",
    "provider alias intervals and product namespaces reject overlap and collision without treating tokens as physical identity",
    "provider-observation/1 binds raw bytes/range/schema/contract/correction; normalized-market-observation/1 binds canonical instrument/raw inputs/transform/truth provenance",
    "execution 0038 stores all C2/C3 facts plus the C4 storage shape; legacy rows remain non-authoritative",
    "fresh loaders recompute canonical bytes/addresses and copied columns; wrong owner/product/contract/underlier and raw/normalized substitutions refuse"
  ],
  "test_plan": ["Produce one real-path ledger entry for every adversarial_rows ID, including seam, database/process boundary, expected refusal/identity change, observed result, and artifact address; focused identity/observation mutations; execution migration parity on SQLite and PostgreSQL; update and rerun the retained destructive-downgrade/forward-repair contract against exact head 0038; protected hashes and scoped diff."],
  "review": {"required": false, "assignment_id": "phase4_canonical_market_owner", "agent": "owner", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "base_sha": "HEAD", "package": ".agent/review-package.json", "review_paths": ["paper-trader/backend/app/market_truth/identity.py","paper-trader/backend/app/market_data/observations.py","paper-trader/backend/app/db/models.py","paper-trader/backend/migrations/versions/20260817_0038_phase4_authority_facts.py","paper-trader/backend/tests/test_phase4_canonical_market_identity.py","paper-trader/backend/tests/test_phase4_authority_execution_migration.py","paper-trader/backend/tests/test_phase4_market_truth_persistence.py"], "exclude_paths": [], "output": ".agent/runs/phase4-canonical-market-identity-correction/owner/report.md", "verdicts": ["IMPLEMENTATION"]}
}
---

# Phase 4 canonical market identity correction

Implement the design §13.1 canonical identity and observation documents. Migration `0038` has sole ownership of execution authority storage, including the rows the next capsule loads. Mark old opaque rows `LEGACY_UNVERIFIED`; do not invent missing source bytes or underliers. Design §13.3 row IDs in `adversarial_rows` are mandatory individual evidence cases.
