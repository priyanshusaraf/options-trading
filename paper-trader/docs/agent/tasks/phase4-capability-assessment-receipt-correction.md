---
{
  "id": "phase4-capability-assessment-receipt-correction",
  "phase": "phase4",
  "status": "accepted",
  "goal": "Make the persisted Phase 4 receipt carry and verify the exact typed capability-assessment/2 authority document so a legitimate receipt survives process death without weakening authority checks.",
  "goal_contract": {
    "create_before_work": true,
    "owner_authorization": "The owner authorized all bounded work needed to finish Phase 4 and permits Sol-medium ownership for repeated Critical architecture failures. Authority is limited to this receipt-identity correction, its exact persistence validators, focused regressions, deployment-ledger accuracy, and ignored evidence. Frontend, provider adapters, runtime enablement, deployment, credentials, production, live, and money authority remain closed.",
    "stopping_condition": "Complete only after a constructor-authorized receipt embeds one closed capability-assessment/2 authority document whose canonical bytes recompute the bound typed address; execution and research persistence reject incomplete, legacy, forged, wrong-schema, wrong-algorithm/version, stale-address, and dependency-mismatched documents; a real write, process death, fresh registry/database reload, reconstruction, and terminal V2_RUNTIME_UNAVAILABLE path passes; affected accepted selectors are current; mutation/restoration and protected/scoped checks pass. Stop with the goal active if closure requires a schema migration, generic fact dispatcher, compatibility downgrade, live/runtime authority, or any path outside this capsule.",
    "evidence_stopping_condition": "Retain the pre-edit counterexample, exact focused selector logs, one real fresh-interpreter lifecycle log, direct negative cases for every receipt field that participates in typed identity, byte-restored mutation evidence, a scoped hash map, and a concise owner report under the declared run directory. Historical PASS labels cannot substitute for current-tree evidence."
  },
  "risk_tags": [
    "critical",
    "authority",
    "content-addressing",
    "persistence",
    "fresh-process"
  ],
  "required_docs": [
    {
      "path": "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
      "sections": [
        "7.3 Capability and identity chain",
        "9. Ownership, authority, and persistence",
        "13.1 Fact and equality matrix",
        "13.2 Persistence, reconstruction, and refusal",
        "13.3 Adversarial owner matrix",
        "13.5 Stale evidence and revalidation"
      ]
    },
    {
      "path": "paper-trader/docs/superpowers/plans/phase4-strategy-os.md",
      "sections": [
        "5. Verification cadence",
        "8. Authority-correction serial route"
      ]
    },
    {
      "path": "paper-trader/docs/agent/DEFECT_PATTERNS.md",
      "sections": [
        "DP-001 — Distinct facts collapsed into one representation",
        "DP-002 — Syntactic self-consistency mistaken for authority",
        "DP-003 — Mocked seam presented as lifecycle evidence",
        "DP-005 — Address-bearing metadata mistaken for a typed authoritative fact"
      ]
    },
    {
      "path": "paper-trader/docs/agent/DEPLOYABILITY.md",
      "sections": [
        "Current verdict",
        "Open obligations",
        "Phase 4 ownership"
      ]
    }
  ],
  "dependency_gate": "phase4-dataset-assessment-authority-correction",
  "allowed_paths": [
    "paper-trader/backend/app/market_data/capability.py",
    "paper-trader/backend/app/strategy/admission.py",
    "paper-trader/backend/app/ir/v2_graph_versions.py",
    "paper-trader/backend/app/core/strategy_admissions.py",
    "paper-trader/backend/research/domain/admissions.py",
    "paper-trader/backend/tests/test_phase4_capability_admission.py",
    "paper-trader/backend/tests/test_phase4_v2_graph_persistence.py",
    "paper-trader/backend/research_tests/test_phase4_v2_receipt_authority.py",
    "paper-trader/docs/reports/phase4-implementation.md",
    "paper-trader/docs/agent/DEPLOYABILITY.md",
    ".agent/runs/phase4-capability-assessment-receipt-correction"
  ],
  "nonclaims": [
    "This correction does not accept Phase 4 or make the authority-integration gate, review package, deployment, production, provider, runtime, frontend, money, or live path ready.",
    "No existing receipt is silently upgraded or relabelled as typed authority. An incomplete legacy receipt must fail closed; local fixtures may be recreated explicitly.",
    "The correction does not add a second assessment identity, generic fact loader, schema migration, service, configuration, dependency, or executable v2 runtime."
  ],
  "owner_gates": [
    "Stop if the typed capability-assessment/2 envelope cannot remain the sole authoritative assessment representation in new Phase 4 receipts.",
    "Stop if compatibility would require accepting an incomplete legacy projection as equivalent to the tagged typed fact.",
    "Stop if a migration, backfill, runtime/provider change, or live/money authority change becomes necessary."
  ],
  "stop_conditions": [
    "The receipt can still bind one address while embedding different assessment bytes, schema, algorithm, version, result rows, owner, mode, plan, registry, dataset, truth, policy, evidence, or assessed time.",
    "Either persistence plane accepts a partial or untagged assessment document, or fresh-process reconstruction trusts copied metadata instead of recomputing the typed address.",
    "The stale assessment= fixture path remains presented as current lifecycle evidence, a required mutation survives, restored bytes differ, or protected/scoped checks fail."
  ],
  "deployment_impact": {
    "classification": "schema-free-application-receipt-identity-hardening",
    "required_evidence": "No schema, migration, dependency, service, configuration, provider, or frontend change. Prove local SQLite execution/research persistence plus real fresh-interpreter reload/refusal; rerun affected disposable PostgreSQL selectors only if the canonical persistence path differs by database. Record that pre-correction incomplete local receipts fail closed and require explicit recreation. No deployability or production claim."
  },
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "medium",
    "service_tier": "default"
  },
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": [
    "the receipt embeds the exact closed capability-assessment/2 schema envelope and fact used to derive phase4_data_binding.capability_assessment_address",
    "fresh reconstruction recomputes the typed authority address from the embedded canonical document and separately checks every repeated owner, mode, plan, registry, dataset, truth, policy, evidence, algorithm/version, time, and result/coverage invariant",
    "execution and research canonicalizers reject partial, untagged legacy, wrong-schema, forged-address, wrong-algorithm/version, stale-dependency, malformed-result, and cross-owner/mode receipt variants before write",
    "one real constructor-authorized two-plane persist, process death, fresh interpreter, independently reconstructed registry and authorities, receipt reload, verification, and terminal V2_RUNTIME_UNAVAILABLE lifecycle passes",
    "the stale capability-admission reconstruction selector uses the current database-backed admission interface and no monkeypatch supplies the assessment or loader",
    "focused current-tree regressions plus byte-restored mutations prove the authority envelope, address derivation, persistence guards, reconstruction guards, and legacy refusal",
    "protected hashes, scoped hashes, diff check, deployability ledger accuracy, and explicit nonclaims pass"
  ],
  "test_plan": [
    "Reproduce and retain the integration-gate address mismatch before editing. Freeze one receipt-envelope interface, then run only focused capability-admission, v2 graph persistence, research receipt-authority, typed-authority compatibility, and real fresh-interpreter selectors.",
    "Use controlled reversible mutations after product/test freeze for at least the schema tag, algorithm/version, address recomputation, repeated dependency equality, and persistence/reconstruction exact-type guards. Restore bytes exactly and rerun the focused selector.",
    "Do not run a broad suite for confidence. PostgreSQL work is limited to an affected canonicalizer parity selector if code inspection shows a database-specific path."
  ],
  "review": {
    "required": false,
    "assignment_id": "phase4_capability_assessment_receipt_owner",
    "agent": "owner",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "medium",
    "base_sha": "HEAD",
    "package": ".agent/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/market_data/capability.py",
      "paper-trader/backend/app/strategy/admission.py",
      "paper-trader/backend/app/ir/v2_graph_versions.py",
      "paper-trader/backend/app/core/strategy_admissions.py",
      "paper-trader/backend/research/domain/admissions.py",
      "paper-trader/backend/tests/test_phase4_capability_admission.py",
      "paper-trader/backend/tests/test_phase4_v2_graph_persistence.py",
      "paper-trader/backend/research_tests/test_phase4_v2_receipt_authority.py",
      "paper-trader/docs/reports/phase4-implementation.md",
      "paper-trader/docs/agent/DEPLOYABILITY.md"
    ],
    "exclude_paths": [],
    "output": ".agent/runs/phase4-capability-assessment-receipt-correction/owner/report.md",
    "verdicts": [
      "CORRECTED",
      "BLOCKED"
    ]
  }
}
---

# Phase 4 capability-assessment receipt correction

The stopped integration gate proved that the receipt binds the tagged typed
assessment address but persists an older untagged projection. Preserve one
typed authority: the receipt must carry the exact closed
`capability-assessment/2` authority document, and every writer and fresh-process
reader must recompute that same address. Refuse incomplete historical receipts;
never weaken the typed loader or substitute the legacy digest.

This is a bounded product correction. When it passes, reactivate the existing
authority-integration capsule and rerun the full 27-row integration evidence.
No result from this capsule alone opens final review.
