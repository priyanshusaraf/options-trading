---
{
  "id": "post-phase5-indicator-accuracy-session-context-binding-assurance",
  "phase": "post-phase5",
  "status": "assigned_waiting_sealed_START",
  "kind": "independent_contract_assurance",
  "goal": "Independently verify the exact three-field session-context grammar correction and its complete unpublished-v2 identity impact before session-data resumes.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Seal ASSURANCE PASS or REJECT from independently authored consumer checks, exact identity evidence, compatibility, resources and mutations; no product edits."
  },
  "risk_tags": [
    "critical",
    "research-integrity",
    "contract-identity"
  ],
  "dependency_gate": "post-phase5-indicator-accuracy-session-context-binding-correction",
  "required_docs": [
    {
      "path": ".agent/runs/post-phase5-indicator-accuracy-session-context-binding-correction/report.md",
      "sections": [
        "Verdict",
        "Identity transition",
        "Verification and limits"
      ]
    },
    {
      "path": ".agent/runs/post-phase5-indicator-accuracy-session-context-binding-correction/evidence.json",
      "sections": [
        "identity",
        "tests",
        "mutations",
        "limits"
      ]
    },
    {
      "path": ".agent/runs/post-phase5-indicator-accuracy-correction-replan/binding-contract-spec.json",
      "sections": [
        "source_contract",
        "bound_contract",
        "validation_rules",
        "legacy"
      ]
    }
  ],
  "allowed_paths": [
    "paper-trader/backend/tests/test_indicator_accuracy_session_context_binding_assurance.py",
    "paper-trader/backend/research_tests/test_indicator_accuracy_session_context_binding_oracle.py",
    ".agent/runs/post-phase5-indicator-accuracy-session-context-binding-assurance",
    "paper-trader/docs/agent/tasks/post-phase5-indicator-accuracy-session-context-binding-assurance.md"
  ],
  "new_paths": [
    "paper-trader/backend/tests/test_indicator_accuracy_session_context_binding_assurance.py",
    "paper-trader/backend/research_tests/test_indicator_accuracy_session_context_binding_oracle.py"
  ],
  "protected_paths": [
    "paper-trader/backend/app",
    "paper-trader/backend/research",
    "paper-trader/backend/tests/test_indicator_accuracy_session_context_binding_correction.py",
    "paper-trader/backend/app/ir/first_party/analytical_v2/session_data.py",
    "paper-trader/backend/tests/test_indicator_accuracy_session_data.py",
    "paper-trader/frontend",
    "/Users/priyanshusaraf/dev/strategy-os-frontend",
    "paper-trader/backend/migrations",
    "paper-trader/scripts/deploy.sh"
  ],
  "stable_input_hashes": [
    {
      "path": ".agent/runs/post-phase5-indicator-accuracy-session-context-binding-correction/closure-seal.json",
      "sha256": "5fa803a4782136d6f41d3317c36312ebba583cdcd7b24ff964ef0ec2dc8a0204"
    },
    {
      "path": "paper-trader/backend/app/ir/registry.py",
      "sha256": "4c1d83e9f8714d9e8a11e571426cde6b7a896fe47aec3d3fe1a44b4f58bf120f"
    },
    {
      "path": "paper-trader/backend/tests/test_indicator_accuracy_session_context_binding_correction.py",
      "sha256": "9660901b07576432c7da228619fda9358b1af3d70f45ce9370041235d86da44a"
    }
  ],
  "scope": [
    "Author independent exact field/role/session/derived-local/address consumer checks before inspecting owner test helpers.",
    "Verify125 legacy and84 source/binding contracts exact,84 implementation identities honestly moved, old plans/receipts/research checkpoints refuse, numerical behavior unchanged.",
    "No self-derived expected values, product edits, publication or session-data resumption."
  ],
  "acceptance": [
    "Exactly three fields accepted and every fourth/wrong/forged variant refused through real resolver/materializer/compiler consumers.",
    "Complete identity/compatibility evidence and at least four genuine mutations with exact restoration.",
    "All sealed predecessor artifacts/current protected source hashes exact."
  ],
  "test_plan": [
    "Fresh consumer tests, accepted numerical compatibility, resource measurement and isolated mutations under safe offline runtime."
  ],
  "parallel_budget": 0,
  "assignments": [],
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "medium",
    "service_tier": "priority"
  },
  "owner_task": "01a04b27-a6e3-7940-b1ea-1b56afd593f5",
  "owner_gates": [
    "Fresh owner distinct from implementation owner; zero agents; exact sealed START required."
  ],
  "stop_conditions": [
    "Any product edit, missing sealed artifact, unsupported fourth field or unexplained drift."
  ],
  "review": {
    "required": false,
    "assignment_id": "post_phase5_indicator_accuracy_session_context_binding_assurance",
    "agent": "owner",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "medium",
    "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c",
    "package": ".agent/runs/post-phase5-indicator-accuracy-session-context-binding-assurance/review-package.json",
    "review_paths": [
      "paper-trader/backend/tests/test_indicator_accuracy_session_context_binding_assurance.py",
      "paper-trader/backend/research_tests/test_indicator_accuracy_session_context_binding_oracle.py",
      ".agent/runs/post-phase5-indicator-accuracy-session-context-binding-assurance"
    ],
    "exclude_paths": [],
    "output": ".agent/runs/post-phase5-indicator-accuracy-session-context-binding-assurance/report.md",
    "verdicts": [
      "ASSURANCE"
    ],
    "max_rechecks": 0
  },
  "deployment_impact": {
    "classification": "read-only assurance; no deployment change"
  },
  "nonclaims": [
    "No publication, provider/calendar availability, frontend, migration, paper/live, deployment or V0 completion."
  ],
  "routing": {
    "path": ".agent/runs/post-phase5-indicator-accuracy-session-context-binding-assurance/routing/decision.json",
    "sha256": "dbc582c4f3acaf79e5bbeac60cd6558c4d15965294047b15dcfb0e779c6c36f2"
  }
}
---

# Session context binding assurance

Independently challenge the three-field grammar correction and its complete unpublished identity transition.
