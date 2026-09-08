---
{
  "id": "strategy-os-v0-auth-session-evidence-recovery",
  "phase": "v0",
  "status": "accepted",
  "kind": "critical_evidence_recovery",
  "goal": "Create one fresh, complete, immutable Q01 evidence lineage against the exact corrected sources without modifying product or tests.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "A complete new evidence package is sealed, every referenced byte resolves, corrected sources remain exact, and no reviewer has started. This is evidence readiness only, not Q01 acceptance."
  },
  "risk_tags": [
    "critical",
    "security",
    "migration",
    "tenancy",
    "evidence-lineage"
  ],
  "dependency_gate": "strategy-os-v0-auth-session-evidence-recovery-replan",
  "accepted_replan": {
    "path": ".agent/runs/strategy-os-v0-auth-session-evidence-recovery-replan/decision.json",
    "sha256": "550aebaf7470d5743b9c7856a92ead6a4014f93e10c4184b3b3eeed32d162b90"
  },
  "programme_assignment": {
    "assignment_id": "v0_auth_session_evidence_recovery",
    "parent_stage": "post-phase5-indicator-accuracy-session-data",
    "primary_programme_owner": false,
    "coordinator": "01a04ac0-ee97-7230-9ffb-1f4e6cdbf1d6",
    "routing_state": "assigned_waiting_sealed_START",
    "carry_rule": "If the main stage advances before completion, carry this exact assignment, paths, owner, and dependency without widening it."
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
      "path": ".agent/runs/strategy-os-v0-auth-session-transport/review/recheck/review.md",
      "sections": [
        "Verdicts",
        "Union finding disposition",
        "Blocking recheck finding",
        "Fresh verification",
        "Retained gates and nonclaims"
      ]
    },
    {
      "path": ".agent/runs/strategy-os-v0-auth-session-transport/review/recheck/verdict.json",
      "sections": [
        "findings",
        "evidence_summary",
        "recheck"
      ]
    }
  ],
  "allowed_paths": [
    ".agent/runs/strategy-os-v0-auth-session-evidence-recovery",
    "paper-trader/docs/agent/tasks/strategy-os-v0-auth-session-evidence-recovery.md"
  ],
  "protected_paths": [
    "paper-trader/backend",
    "paper-trader/frontend",
    "/Users/priyanshusaraf/dev/strategy-os-frontend",
    ".agent/runs/strategy-os-v0-auth-session-transport",
    ".agent/runs/strategy-os-v0-auth-session-evidence-recovery-replan",
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
    "Zero product, test, schema, dependency, lock, frontend, capsule-control, or old-Q01-run edits. Existing code and tests are executable read-only inputs.",
    "Before inspecting historical runner scripts, author evidence-protocol.json with unique recovery filenames, commands, test identities, source checks, temporary databases, ports, process cleanup, and failure retention. Never reuse an old evidence filename as an output target.",
    "Re-execute the complete corrected Q01 boundary: backend auth/session/tenancy, SQLite migration/interruption/restore, disposable PG16 copy/restore/concurrency, actual HTTPS invited-user enrollment/login/restart/tenant/CSRF/password/revoke/Secure-cookie journey, frontend tests/build/lint, source and boundary audits, architecture validation, and genuine isolated mutations for all three closed findings and the original critical guards.",
    "Record source hashes immediately before and after every long-running browser or PostgreSQL command. Use fresh per-command databases and ports, mock/paper mode, disabled dotenv, empty live acknowledgement, and no HOME/CODEX_HOME override.",
    "The new review package may cite the failed Q01 lineage only as preserved history. Every acceptance evidence item must resolve inside the new recovery run and be generated under the new protocol."
  ],
  "acceptance": [
    "All 27 source hashes match the accepted replan before, during, and after the evidence run.",
    "The complete fresh evidence inventory resolves exactly; no missing, overwritten, mixed-lineage, copied-without-provenance, or draft bytes.",
    "All product and migration behaviors required by the auth contract and the three closed findings are freshly exercised; failures remain failures and block sealing.",
    "A review-package.json and local-evidence-seal.json are generated only after sources, commands, output identities, cleanup, and artifact hashes freeze."
  ],
  "test_plan": [
    "Use the corrected package only as a historical test/command inventory, then reconcile the selected identities to the auth contract and fresh protocol; do not inherit its evidence files as acceptance proof.",
    "Run the full fresh backend, SQLite, PG16, HTTPS, frontend, mutation, cleanup, and preservation matrix declared in evidence-protocol.json.",
    "Run .codex/scripts/validate_agent_architecture.py against the final package and verify both repository heads/branches/indexes without modifying them."
  ],
  "parallel_budget": 0,
  "assignments": [],
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "medium",
    "service_tier": "priority"
  },
  "fork_turns": "none",
  "owner_task": "01a04b0b-fbc4-7963-a216-8efa0c5a6e76",
  "owner_gates": [
    "Fresh direct saved-worktree owner, zero agents, distinct from the Q01 product owner and exhausted reviewer.",
    "No review dispatch until the complete new package and local seal exist. No self-acceptance.",
    "No provider network, credentials, live/VPS, orders, money, deployment, destructive database action, or dependency changes."
  ],
  "stop_conditions": [
    "Any stable input mismatch, product/test write, missing artifact, unsafe runtime setting, unexplained drift, or need for product correction.",
    "First automatic compaction requires a same-directory fresh-task handoff before a second."
  ],
  "review": {
    "required": false,
    "assignment_id": "v0_auth_session_evidence_recovery_owner",
    "agent": "owner",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "medium",
    "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c",
    "package": ".agent/runs/strategy-os-v0-auth-session-evidence-recovery/review-package.json",
    "review_paths": [
      ".agent/runs/strategy-os-v0-auth-session-evidence-recovery",
      "paper-trader/docs/agent/tasks/strategy-os-v0-auth-session-evidence-recovery.md"
    ],
    "exclude_paths": [],
    "output": ".agent/runs/strategy-os-v0-auth-session-evidence-recovery/report.md",
    "verdicts": [
      "EVIDENCE_READY_PENDING_INDEPENDENT_REVIEW"
    ],
    "max_rechecks": 0,
    "next_capsule": "paper-trader/docs/agent/tasks/strategy-os-v0-auth-session-evidence-recovery-final-review.md"
  },
  "deployment_impact": {
    "classification": "evidence-only",
    "product_change": false,
    "deployment_authority": false,
    "release_gate": "strategy-os-v0-security-operations-deployability"
  },
  "nonclaims": [
    "No Q01 acceptance from this decision or from passing product corrections.",
    "No public signup, email verification, recovery, MFA, dependency clearance, production migration, deployment, or V0 completion."
  ],
  "routing": {
    "path": ".agent/runs/strategy-os-v0-auth-session-evidence-recovery/routing/decision.json",
    "sha256": "0ec242dfe91a931354d80b1819f6b6923d20192adfc611a06020b9b5a4f963b1"
  },
  "completion": {
    "verdict": "EVIDENCE_READY_PENDING_INDEPENDENT_REVIEW",
    "owner_task": "01a04b0b-fbc4-7963-a216-8efa0c5a6e76",
    "review_dispatched": false,
    "independent_acceptance": false,
    "manifest_entries": 148,
    "logical_manifest_sha256": "ca748512622d79aaf2093197cb49937066d75249492f32da2175ec6f804bf6b3",
    "promotion_ledger_sha256": "4724934fef367d231652d78e1ef615f490c2893c31f64aac66d07a4fdb516f5e",
    "review_package_sha256": "85c62a165d6d15032ec7bacff690cd52442374a6d0ee510eb40c1898e1a03e8f",
    "report_sha256": "76335782cb4d30280718560e6c90ce6647e7af589f4accf18fc4046b7927d151",
    "final_package_integrity_sha256": "4a007ba579bb655c021404b0db4643dca6f230d590c7ecac97dd5095cfc0224e",
    "stable_sources": 27,
    "backend_tests": 459,
    "backend_postgresql_skips_rerun": 2,
    "postgresql16_tests": 12,
    "frontend_tests": 84,
    "https_cases": 10,
    "isolated_product_guard_mutations": 9,
    "package_integrity_mutation": "PASS -> isolated exact FAIL -> exact restore PASS",
    "q01_accepted": false,
    "deployment": false,
    "v0_complete": false
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

# Q01 fresh evidence recovery

This capsule may rerun the corrected product but may not edit it. The prior failed reviews and missing bytes remain historical facts.
