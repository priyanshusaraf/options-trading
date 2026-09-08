---
{
  "id": "post-phase5-indicator-accuracy-contract-assurance",
  "phase": "post-phase5",
  "status": "completed",
  "kind": "independent_accuracy_assurance",
  "goal": "Independently prove canonical contract/binding closure, frozen v1 identities and fail-closed parameter/history/role binding before numerical implementation.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Independently prove canonical contract/binding closure, frozen v1 identities and fail-closed parameter/history/role binding before numerical implementation. Complete only with named source-bound evidence, protected-byte proof and the acceptance checks below; this does not authorize later scope."
  },
  "risk_tags": [
    "critical",
    "research-integrity",
    "semantic-versioning",
    "complete-universe"
  ],
  "required_docs": [
    {
      "path": ".agent/runs/post-phase5-indicator-accuracy-correction-replan/architecture-decision.md",
      "sections": [
        "Immutable version 1",
        "Parameter-dependent contracts: bounded extension, no expression language",
        "Validity, sessions and outputs",
        "Source and oracle independence",
        "Sequencing and stopping rule"
      ]
    },
    {
      "path": ".agent/runs/post-phase5-indicator-accuracy-correction-replan/legacy-cache-result-policy.md",
      "sections": [
        "Version and graph identity",
        "Cache and result disposition",
        "Authority and compatibility"
      ]
    },
    {
      "path": ".agent/runs/post-phase5-indicator-accuracy-correction-replan/binding-contract-spec.json",
      "sections": [
        "source_contract",
        "binding_registration",
        "bound_contract",
        "validation_rules",
        "legacy"
      ]
    },
    {
      "path": ".agent/runs/post-phase5-indicator-accuracy-correction-replan/source-access-policy.md",
      "sections": [
        "Inspected sources",
        "Reference environment gate",
        "Deferred numerical conventions"
      ]
    },
    {
      "path": ".agent/runs/post-phase5-indicator-accuracy-correction-replan/verification-contract.md",
      "sections": [
        "Thresholds",
        "Complete-array comparators",
        "Adversarial fixtures",
        "Operational evidence"
      ]
    }
  ],
  "dependency_gate": "post-phase5-indicator-accuracy-contract-foundation",
  "allowed_paths": [
    "paper-trader/backend/tests/test_indicator_accuracy_contract_assurance.py",
    ".agent/runs/post-phase5-indicator-accuracy-contract-assurance",
    "paper-trader/docs/agent/tasks/post-phase5-indicator-accuracy-contract-assurance.md"
  ],
  "protected_paths": [
    "paper-trader/backend/app/ir/first_party/analytical.py",
    "paper-trader/frontend",
    "/Users/priyanshusaraf/dev/strategy-os-frontend",
    "paper-trader/backend/app/engine",
    "paper-trader/backend/app/execution",
    "paper-trader/backend/app/providers",
    "paper-trader/backend/migrations",
    "paper-trader/scripts/deploy.sh"
  ],
  "nonclaims": [
    "No frontend, provider network/credentials, private TradingView, dependency adoption, SQL migration, deployment/VPS, live/order/money, or Phase 6 work. No edits to legacy analytical.py or accepted component semantics.",
    "Planning records and test totals are not a numerical or deployment acceptance."
  ],
  "owner_gates": [
    "Start only after the predecessor is accepted and this exact bounded assignment is authorized by the programme/owner.",
    "Stop before an in-place v1 semantic/address change, an undeclared schema/dependency/provider/execution change, or a cross-wave shared-file edit.",
    "Before provisioning any reference executor, obtain explicit owner approval for the exact disposable TA-Lib 0.7.1 oracle environment. No product dependency or lock change is authorized."
  ],
  "stop_conditions": [
    "Any claimed component/output/contract field is missing or a test expected value is self-derived from product math.",
    "A v1 source, descriptor, contract, declaration or implementation address changes.",
    "An unaccepted v2 implementation becomes product-eligible, or registry/cache/result identity is silently rewritten.",
    "A writer reaches a path owned by another wave without serial integration ownership."
  ],
  "deployment_impact": {
    "classification": "evidence-only",
    "required_evidence": "Name exact artifacts, locked runtime, resource bounds, semantic/cache identity and refusal evidence; unresolved release assembly belongs to strategy-os-v0-security-operations-deployability before its acceptance."
  },
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "medium",
    "service_tier": "priority"
  },
  "parallel_budget": 0,
  "assignments": [],
  "component_scope": [],
  "acceptance": [
    "Independently enumerate all 125 v1 identities and every /1 and /2 contract field.",
    "Real omission, stale-address and underdeclared-history mutations are killed in isolated copies and exactly restored.",
    "Foundation product bytes are frozen and do not change during evidence generation."
  ],
  "test_plan": [
    "Separate consumer of current-catalogue.json and independently serialized binding cases.",
    "At least one boundary-level RED\u2192GREEN per binding/refusal class, not only helper unit tests."
  ],
  "review": {
    "required": false,
    "assignment_id": "post_phase5_indicator_accuracy_contract_assurance_owner",
    "agent": "owner",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "medium",
    "base_sha": "HEAD",
    "package": ".agent/runs/post-phase5-indicator-accuracy-contract-assurance/review-package.json",
    "review_paths": [
      "paper-trader/backend/tests/test_indicator_accuracy_contract_assurance.py",
      ".agent/runs/post-phase5-indicator-accuracy-contract-assurance"
    ],
    "exclude_paths": [
      "paper-trader/backend/app/ir/first_party/analytical.py",
      "paper-trader/frontend",
      "paper-trader/backend/app/engine",
      "paper-trader/backend/app/execution",
      "paper-trader/backend/app/providers",
      "paper-trader/backend/migrations",
      "paper-trader/scripts/deploy.sh"
    ],
    "output": ".agent/runs/post-phase5-indicator-accuracy-contract-assurance/report.md",
    "verdicts": [
      "ASSURANCE"
    ],
    "max_rechecks": 0
  },
  "independence": "Must be a different owner from the corresponding implementation. Read product code, but author expected vectors independently; no product mutation. Product-changing findings return to an explicitly bounded correction.",
  "owner_authorization": "Owner authorized proceeding now with independent indicator accuracy contract assurance in this separate task; no numerical correction or later scope.",
  "assurance": {
    "verdict": "ASSURANCE PASS",
    "owner_task": "01a04748-debe-76a1-bc69-4d3d3a8ae038",
    "report": ".agent/runs/post-phase5-indicator-accuracy-contract-assurance/report.md",
    "independent_tests": 343,
    "combined_tests": 626,
    "v1_identities_unchanged": 125,
    "isolated_guards_killed_restored": 3,
    "product_edits": 0,
    "numerical_accuracy_claim": false,
    "publication_authority": false,
    "deployment_authority": false,
    "programme_transition": "Coordinating owner only; accept assurance and pause before authorizing core math."
  }
}

---

# Contract assurance

Independently prove canonical contract/binding closure, frozen v1 identities and fail-closed parameter/history/role binding before numerical implementation.

The owner opened this bounded assurance on 2026-08-28 in a separate task. Product code remains read-only. CURRENT.md and PROGRAMME.json remain coordinating-owner paths.
