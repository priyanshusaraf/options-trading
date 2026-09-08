---
{
  "id": "strategy-os-v0-auth-session-evidence-recovery-final-review",
  "phase": "v0",
  "status": "accepted",
  "kind": "critical_review",
  "goal": "Independently decide Q01 SPEC and QUALITY from the complete fresh evidence lineage while preserving both original failed review iterations.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "One fresh reviewer seals separate SPEC and QUALITY verdicts against the exact recovery package. PASS requires complete evidence lineage and direct independent verification; product fixes or totals alone do not suffice."
  },
  "risk_tags": [
    "critical",
    "security",
    "migration",
    "tenancy",
    "evidence-lineage"
  ],
  "dependency_gate": "strategy-os-v0-auth-session-evidence-recovery",
  "accepted_replan": {
    "path": ".agent/runs/strategy-os-v0-auth-session-evidence-recovery-replan/decision.json",
    "sha256": "550aebaf7470d5743b9c7856a92ead6a4014f93e10c4184b3b3eeed32d162b90"
  },
  "required_docs": [
    {
      "path": ".agent/runs/strategy-os-v0-auth-session-evidence-recovery-replan/decision.json",
      "sections": [
        "verified_facts",
        "alternatives",
        "selected_plan",
        "stopping_conditions"
      ]
    },
    {
      "path": ".agent/runs/strategy-os-v0-auth-dataset-parallel-materialization/auth-contract.md",
      "sections": [
        "Scope and authority",
        "Enrollment and credential boundary",
        "Browser transport and sole authority",
        "Persistence and browser experience",
        "Required proof and limits"
      ]
    },
    {
      "path": ".agent/runs/strategy-os-v0-auth-session-transport/review-iteration-1-authoritative/review.md",
      "sections": [
        "Verdicts",
        "Prioritized findings",
        "Evidence assessment",
        "Owner gates and recheck scope"
      ]
    },
    {
      "path": ".agent/runs/strategy-os-v0-auth-session-transport/review/recheck/review.md",
      "sections": [
        "Verdicts",
        "Union finding disposition",
        "Blocking recheck finding",
        "Retained gates and nonclaims"
      ]
    }
  ],
  "allowed_paths": [
    ".agent/runs/strategy-os-v0-auth-session-evidence-recovery-final-review",
    "paper-trader/docs/agent/tasks/strategy-os-v0-auth-session-evidence-recovery-final-review.md"
  ],
  "protected_paths": [
    "paper-trader/backend",
    "paper-trader/frontend",
    "/Users/priyanshusaraf/dev/strategy-os-frontend",
    ".agent/runs/strategy-os-v0-auth-session-transport",
    ".agent/runs/strategy-os-v0-auth-session-evidence-recovery-replan",
    ".agent/runs/strategy-os-v0-auth-session-evidence-recovery",
    "paper-trader/docs/agent/CURRENT.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/DEPLOYABILITY.md",
    ".codex"
  ],
  "stable_input_hashes": [
    {
      "path": "/Users/priyanshusaraf/dev/strategy-os-frontend/src/App.test.tsx",
      "sha256": "736f3bd9d16ddc6d28c0533539bd9e46702fec4bdad3adfbf63b93371ba1f5db"
    },
    {
      "path": "/Users/priyanshusaraf/dev/strategy-os-frontend/src/App.tsx",
      "sha256": "0026b300ac6ca0b1e8efe83096ee2b8e610a883a38ae614bccf0ebda97af2814"
    },
    {
      "path": "/Users/priyanshusaraf/dev/strategy-os-frontend/src/auth/AuthGate.test.tsx",
      "sha256": "0131897c0947c6f397d688db6f1956251630b5881cb977003fdbe561db145b63"
    },
    {
      "path": "/Users/priyanshusaraf/dev/strategy-os-frontend/src/auth/AuthGate.tsx",
      "sha256": "af1e0e66759f2b0b5beedee4cd7b53cd8ed584bfe368612cc7fdd624e286af28"
    },
    {
      "path": "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/PrecisionShell.tsx",
      "sha256": "22757eac9b8f2c3744e3f3f47233b7faa5b60c26fa0bebb4d0d31dbecb7d39d7"
    },
    {
      "path": "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/api.ts",
      "sha256": "a3a69e720fe9a1e055a669a88c177c6502a041e38f52386d7dc59fb0a6652da7"
    },
    {
      "path": "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/contracts.ts",
      "sha256": "fd13fed90f45d3ec67763434ce379983f0a33aad64c32e6df527cf883713548d"
    },
    {
      "path": "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/precision.css",
      "sha256": "1334185979cf1738140f8350f643825078062b7705b1c8b70d3dd2a706ed7093"
    },
    {
      "path": "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/shell.test.tsx",
      "sha256": "0300f93a22cf124cb28a42e069fdd73e7512f76efe80ae9eea7cd2e4d2a13fec"
    },
    {
      "path": "paper-trader/backend/app/accounts/__init__.py",
      "sha256": "ab36c2926d8891ac6b49d4047659443b747ba0c98f37c464904bdbec834bd8c4"
    },
    {
      "path": "paper-trader/backend/app/accounts/browser_auth.py",
      "sha256": "c53c7873b5c27bb90129e18204f7610cffbe2f4b21a2c2de5214b0754e5ad4c0"
    },
    {
      "path": "paper-trader/backend/app/api/auth_session_routes.py",
      "sha256": "bc8c5b1b7309ef53ece4559acf00316e87a81f50560337e92cc1671381c83df2"
    },
    {
      "path": "paper-trader/backend/app/api/principal.py",
      "sha256": "ac684f3ce71b2324be7c15a3b78a19cc29bcfe99f0f026cb35488b6d814e7d6e"
    },
    {
      "path": "paper-trader/backend/app/core/config.py",
      "sha256": "4a81806eb43481a10f84a1c9764dc36dd6a3ea09763c873a01f2101dfbf6f6b3"
    },
    {
      "path": "paper-trader/backend/app/db/copy_contract.py",
      "sha256": "82151a37f451377c0089eab65e94f0a8c81bfeb36c8189e000dbac10df3ecc63"
    },
    {
      "path": "paper-trader/backend/app/db/models.py",
      "sha256": "7c91efedf998218e6ecad2725be562368edece679fd10f71c5410b7ffa458936"
    },
    {
      "path": "paper-trader/backend/app/db/planes.py",
      "sha256": "132b53251ea34c39891d580ac293bc9f80dcff31697bf960cb816a549a115fde"
    },
    {
      "path": "paper-trader/backend/app/main.py",
      "sha256": "3300b0ea777c6288b30d2b060762a322d2fb3b5db9da05cb22b6bba462722794"
    },
    {
      "path": "paper-trader/backend/migrations/versions/20260829_0043_browser_auth.py",
      "sha256": "79a97d2dfa12b401dde31e4b0a3a5176a280e0643f850248c97b10017208cb8f"
    },
    {
      "path": "paper-trader/backend/scripts/create_enrollment_invite.py",
      "sha256": "df68d313a48a8c1eafbab4651a982cdef8c9bd1de5354d007696ff6d6a4960f7"
    },
    {
      "path": "paper-trader/backend/tests/test_api_auth.py",
      "sha256": "ba9d7ef97847d947e5eb287bc4f894b9be31011b121cae6d64de5904cfbd7bf3"
    },
    {
      "path": "paper-trader/backend/tests/test_browser_auth.py",
      "sha256": "479adf342d52d2aa94b291798063ad05174502a249348446070b8601220731b6"
    },
    {
      "path": "paper-trader/backend/tests/test_browser_auth_migration.py",
      "sha256": "d1c3cc9d2f4dab3fe48b49011a3708508dd1a3f23ef3a1173a01c3f9a36b043f"
    },
    {
      "path": "paper-trader/backend/tests/test_db_planes.py",
      "sha256": "ccee0c6d0427c9779c8f97e31572cb8447d47d45facc73dceee0f852cf784a3f"
    },
    {
      "path": "paper-trader/backend/tests/test_postgresql_restore_contract.py",
      "sha256": "002acce2d477f0e79484fd94784306d627d1fa651dfedc6eaf2de5d7f6da6106"
    },
    {
      "path": "paper-trader/backend/tests/test_schema_migrations.py",
      "sha256": "b669dfa2247b8b949a8fe00802db3f82bf3f0bbee2c18b73ced61180592fbf36"
    },
    {
      "path": "paper-trader/backend/tests/test_user_sessions.py",
      "sha256": "5d6aacced3a9201bed586f27a4ad4b6f369d19a10880ca81569684f00c1161c5"
    }
  ],
  "scope": [
    "Fresh reviewer must be distinct from the product owner, evidence recovery owner, exhausted Q01 reviewer, and unrelated Q03 reviewer.",
    "Verify every recovery-package artifact and source hash before inspecting conclusions. Treat the two original failed Q01 iterations as immutable retained history, not acceptance evidence.",
    "Independently rerun the declared critical backend, SQLite/PG16, HTTPS, frontend, and source-preservation checks, including false-logout, future/excess restore refusal, and verifier repr/log redaction.",
    "Reject missing, overwritten, mixed-lineage, draft, or post-package evidence. Do not repair or rewrite evidence/product during review."
  ],
  "acceptance": [
    "Every package and evidence hash resolves before judgment; all 27 source inputs match the accepted recovery seal.",
    "Independent critical tests cover authentication, tenancy, SQLite/PG16 migration and restore, HTTPS restart and revocation, frontend transport, and the three closed product findings.",
    "Separate SPEC PASS and QUALITY PASS are both required. A test count or product correctness without immutable evidence cannot pass QUALITY."
  ],
  "test_plan": [
    "Verify the recovery package, local seal, command inventory, test identities, cleanup, and all current source hashes directly.",
    "Independently rerun the critical backend, migration/restore, HTTPS, frontend, and source-preservation cases declared by the recovery capsule.",
    "Inspect genuine mutation evidence and run independent counterchecks for false logout, bounded restore, verifier redaction, tenant isolation, restart, CSRF, and revocation."
  ],
  "parallel_budget": 0,
  "assignments": [],
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "high",
    "service_tier": "priority"
  },
  "fork_turns": "none",
  "owner_task": "/root/v0_auth_session_evidence_recovery_final_review",
  "review": {
    "required": true,
    "assignment_id": "v0_auth_session_evidence_recovery_final_review",
    "agent": "critical-reviewer",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "reason": "Critical authentication, tenancy, migration, and evidence-lineage acceptance after an exhausted failed review.",
    "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c",
    "package": ".agent/runs/strategy-os-v0-auth-session-evidence-recovery/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/accounts/__init__.py",
      "paper-trader/backend/app/accounts/browser_auth.py",
      "paper-trader/backend/app/api/auth_session_routes.py",
      "paper-trader/backend/app/api/principal.py",
      "paper-trader/backend/app/core/config.py",
      "paper-trader/backend/app/db/copy_contract.py",
      "paper-trader/backend/app/db/models.py",
      "paper-trader/backend/app/db/planes.py",
      "paper-trader/backend/app/main.py",
      "paper-trader/backend/migrations/versions/20260829_0043_browser_auth.py",
      "paper-trader/backend/scripts/create_enrollment_invite.py",
      "paper-trader/backend/tests/test_api_auth.py",
      "paper-trader/backend/tests/test_browser_auth.py",
      "paper-trader/backend/tests/test_browser_auth_migration.py",
      "paper-trader/backend/tests/test_db_planes.py",
      "paper-trader/backend/tests/test_postgresql_restore_contract.py",
      "paper-trader/backend/tests/test_schema_migrations.py",
      "paper-trader/backend/tests/test_user_sessions.py"
    ],
    "exclude_paths": [],
    "output": ".agent/runs/strategy-os-v0-auth-session-evidence-recovery-final-review/review.md",
    "verdicts": [
      "SPEC",
      "QUALITY"
    ],
    "max_rechecks": 1
  },
  "owner_gates": [
    "Start only after the current coordinator verifies the recovery seal and routes this exact one reviewer.",
    "No replacement or reviewer swarm. One focused recheck only if the fresh review returns a bounded correctable finding.",
    "No product/control edits, public capability, deployment, or V0 acceptance by the reviewer."
  ],
  "stop_conditions": [
    "Any recovery artifact or source hash mismatch, missing required proof, or evidence-owner/product-owner overlap.",
    "A substantive product defect returns to an explicit separately owned correction/replan; reviewer cannot patch it."
  ],
  "deployment_impact": {
    "classification": "review-only",
    "product_change": false,
    "deployment_authority": false,
    "release_gate": "strategy-os-v0-security-operations-deployability"
  },
  "nonclaims": [
    "No Q01 acceptance from this decision or from passing product corrections.",
    "No public signup, email verification, recovery, MFA, dependency clearance, production migration, deployment, or V0 completion."
  ],
  "routing": {
    "path": ".agent/runs/strategy-os-v0-auth-session-evidence-recovery-final-review/review-routing.json",
    "sha256": "d94865c1cb746cf3785c71d13dc67aa36081a0db2d17ce93c204a09efeafbc0c"
  },
  "acceptance_result": {
    "status": "accepted",
    "SPEC": "PASS",
    "QUALITY": "PASS",
    "review_sha256": "85fd471859317cb8d5e3f595eea708fd56f7c1f72fe4b267cea3b1891cbc67db",
    "verdict_sha256": "8576d6db175ea4e6287b19d32ca4b270b273ed959099bbd7d04ac224e77405c9",
    "review_seal_sha256": "63729a3c06939ae239d0ba34f346b16069c468da20d952da1d09ad71858e51db",
    "closure": {
      "path": ".agent/runs/strategy-os-v0-auth-session-evidence-recovery/coordinator-acceptance/decision.json",
      "sha256": "f42e233119bba92852501cfdbf0b996c1b6349298f875582ebee42235c142dd5"
    },
    "publication": false,
    "deployment": false,
    "v0_complete": false
  }
}
---

# Q01 fresh evidence final review

Only the current programme coordinator may dispatch this reviewer after the recovery package is sealed and re-audited.
