---
{
  "id": "strategy-os-v0-data-only-connection-contract",
  "phase": "v0",
  "kind": "bounded_parallel_implementation",
  "status": "accepted",
  "goal": "Implement one owner-scoped Zerodha data-only connection lifecycle over the existing encrypted store without execution authority",
  "goal_contract": {"create_before_work": true, "stopping_condition": "Exact backend lifecycle/refusal/tenant/restart/resource/mutation evidence and one independent SPEC PASS/QUALITY PASS. Capability stays BLOCKED; no provider/deployment/V0 claim."},
  "risk_tags": ["critical", "credentials", "tenant-isolation", "provider-role-separation", "parallel-owned"],
  "required_docs": [
    {"path": "paper-trader/docs/strategy-os-v0-release-audit-2026-08-27/03-V0-SCOPE-AND-GOLDEN-PATH.md", "sections": ["Public V0 scope", "Golden path"]},
    {"path": "paper-trader/docs/strategy-os-v0-release-audit-2026-08-27/05-ARCHITECTURE-AND-RELEASE-PROFILE.md", "sections": ["Required V0 profile", "Execution hard-disable", "Provider and data architecture"]},
    {"path": "paper-trader/docs/strategy-os-v0-release-audit-2026-08-27/06-TEST-SECURITY-DATA-AND-DEPLOYMENT-GATES.md", "sections": ["Security and tenancy", "Data and licensing gates", "Zerodha", "Deployability gates"]},
    {"path": ".agent/runs/strategy-os-v0-data-only-connection-materialization/contract.md", "sections": ["Scope", "Data-only identity and lifecycle", "Consumers and proof"]}
  ],
  "dependency_gate": "strategy-os-v0-release-profile-foundation",
  "programme_assignment": {"assignment_id": "v0_data_only_connection", "queue_id": "Q02", "parent_stage": "post-phase5-indicator-accuracy-session-data", "owner_task": "/root/v0_data_only_connection", "primary_programme_owner": false, "prerequisite": "Satisfied by accepted Q01, accepted launch-convergence replan, retired reviewed slots and the exact stable-input rebind."},
  "allowed_paths": [
    "paper-trader/backend/app/api/connection_routes.py",
    "paper-trader/backend/app/providers/connection_store.py",
    "paper-trader/backend/tests/test_connection_routes.py",
    "paper-trader/backend/tests/test_connection_store.py",
    "paper-trader/docs/agent/tasks/strategy-os-v0-data-only-connection-contract.md",
    ".agent/runs/strategy-os-v0-data-only-connection-contract"
  ],
  "new_paths": [],
  "protected_paths": [
    "AGENTS.md", ".agents", ".codex", ".github", "paper-trader/backend/app/main.py",
    "paper-trader/backend/app/api/principal.py", "paper-trader/backend/app/core/config.py",
    "paper-trader/backend/app/core/release_profile.py", "paper-trader/backend/app/core/credential_vault.py",
    "paper-trader/backend/app/db", "paper-trader/backend/migrations", "paper-trader/backend/app/providers/brokers.py",
    "paper-trader/backend/app/providers/capabilities.py", "paper-trader/backend/app/providers/broker_auth.py",
    "paper-trader/backend/app/providers/kite.py", "paper-trader/backend/app/engine", "paper-trader/backend/app/execution",
    "paper-trader/backend/app/ir", "paper-trader/backend/tests/conftest.py", "paper-trader/backend/requirements.lock",
    "paper-trader/backend/research", "paper-trader/frontend", "/Users/priyanshusaraf/dev/strategy-os-frontend",
    "paper-trader/scripts/deploy.sh"
  ],
  "stable_input_hashes": [],
  "stable_inputs_rebind_at_dispatch": false,
  "stable_input_rebind": {"path": ".agent/runs/strategy-os-v0-data-only-connection-materialization/stable-input-rebind.json", "status": "accepted", "actual_start": true},
  "scope": [
    "Implement the complete frozen data-only contract only in the existing route/store and their two natural tests. Reuse current vault/session/OAuth/provider registry; no second authority/schema/capability vocabulary.",
    "Server derives a strict implemented data-only capability set; all execution/account/unbuilt roles refuse. Capability/release-profile/frontend/provider opening stays coordinator-owned later.",
    "Queued only until Q01 review/closure, exact stable rebind/current-stage carry and fresh Sol-medium/no-history/zero-agent owner START."
  ],
  "acceptance": ["Owner/tenant/credential/OAuth/revoke/restart/concurrency and execution-unreachability evidence with honest UNVERIFIED provider expiry/quota.", "One independent critical SPEC PASS and QUALITY PASS; provider/legal/data/public/deployment gates remain."],
  "test_plan": ["Focused real HTTP/store RED-GREEN on both mounts and Q01 sessions; fake adapter/authenticator with poisoned execution/network.", "Affected connection/auth/capability/release tests, bounded resources and genuine isolated guard mutations with exact restoration."],
  "parallel_budget": 0, "assignments": [],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "service_tier": "priority"},
  "required_skills": ["executing-strategy-os-slices", "provider-adapter-conformance", "tenant-isolation-audit", "auth-and-session-hardening", "auditing-strategy-os-deployability"],
  "review": {"required": true, "assignment_id": "v0_data_only_connection_review", "agent": "critical-reviewer", "model": "gpt-5.6-sol", "reasoning_effort": "high", "reason": "Credential/tenant/provider-role mistakes could expose secrets or execution authority.", "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c", "package": ".agent/runs/strategy-os-v0-data-only-connection-contract/review-package.json", "output": ".agent/runs/strategy-os-v0-data-only-connection-contract/review.md", "review_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-data-only-connection-contract.md", ".agent/runs/strategy-os-v0-data-only-connection-contract"], "exclude_paths": [], "verdicts": ["SPEC", "QUALITY"], "max_rechecks": 1},
  "first_review": {
    "review_task": "01a04d04-0ede-7e10-b6da-acbd8b8c2f48",
    "verdict": "SPEC FAIL / QUALITY FAIL",
    "verdict_path": ".agent/runs/strategy-os-v0-data-only-connection-contract/review.md",
    "verdict_sha256": "532dbebda57cd9f3013374e5fd54ad4e09ad82721c9249a2736ccb20d9eefd5a",
    "finding_ids": ["F1", "F2", "F3", "F4"],
    "rechecks_used": 0,
    "rechecks_remaining": 1
  },
  "correction_scope": [
    "Replace the returned raw KiteProvider class with a closed data-only facade/closure exposing only the four admitted observation operations and an internal late-credential binding; poison account, margin, position, order, trade, venue/builder, execution-import and network surfaces.",
    "Make every late credential read atomically require a current active Zerodha BrokerAccount whose id, owner and broker still match the bound active connection; owner/broker/status changes withdraw access immediately.",
    "Capture one OAuth initiation timestamp and derive both created_at and expires_at from it so persisted lifetime is never more than exactly ten minutes.",
    "Add concurrent OAuth initiation, callback-versus-revoke, process/store restart, measured query/memory/request ceilings and real browser-cookie Origin/CSRF route evidence with same-owner controls.",
    "Rebuild the corrected package and route only the one allowed same-reviewer recheck; capability remains blocked and no provider network/schema/shared-protected edit is permitted."
  ],
  "deployment_impact": {"classification": "unpublished backend data-role contract; no capability/schema/dependency/provider/deployment opening", "integration_owner": "strategy-os-v0-zerodha-data-static-scope", "release_assembly_owner": "strategy-os-v0-security-operations-deployability", "rollback": "No deployment/schema. Revert only exact unaccepted route/store/test delta after owner decision; preserve encrypted/audit rows."},
  "owner_gates": ["Standing all-V0/parallel authority; no routine token. Reviewed slot/stable-owner seal still required."],
  "stop_conditions": ["Q01 recheck changes a stable interface; create sealed successor before dispatch.", "Any schema/vault/principal/release-profile/adapter change is required; reproduce and route separately before mutation."],
  "nonclaims": ["No real Zerodha credential/network/conformance/expiry/quota/data-right, capability/frontend/public readiness, deployment or whole-V0 completion."]
  ,
  "implementation": {
    "verdict": "CORRECTED IMPLEMENTATION PASS",
    "report": ".agent/runs/strategy-os-v0-data-only-connection-contract/report.md",
    "report_sha256": "ef249dc096d3d861ef3f43a465d1ed4d7b6e093e58632e256590fc9230693ad0",
    "evidence": ".agent/runs/strategy-os-v0-data-only-connection-contract/evidence.json",
    "evidence_sha256": "617dd7a478807f999b2264d687b43880be67ef5106ebf803e28063738d5ab5f4",
    "focused_tests_passed": 100,
    "affected_tests_passed": 348,
    "guard_mutations_killed": 7,
    "provider_network": false,
    "capability_open": false,
    "deployment": false,
    "independent_review_accepted": true,
    "correction": {
      "finding_ids": ["F1", "F2", "F3", "F4"],
      "targeted_tests": "PASS",
      "same_reviewer_recheck_task": "01a04d04-0ede-7e10-b6da-acbd8b8c2f48",
      "rechecks_used": 1,
      "rechecks_remaining": 0
    }
  },
  "final_review": {
    "review_task": "01a04d04-0ede-7e10-b6da-acbd8b8c2f48",
    "verdict": "SPEC PASS / QUALITY PASS",
    "verdict_path": ".agent/runs/strategy-os-v0-data-only-connection-contract/review.md",
    "verdict_sha256": "36c0f3aa79e962d406e94a3b48f632fa913ee915d08d5ea02ebc49aa2e1f90f9",
    "hash_seal_sha256": "21e7e5a84c15a94623c4e119db0b99df994523ad164fbde73c68a625fab99634",
    "review_package_sha256": "c050e5e957b33688d0d408dc93031ac7c3eaae91644e60529161648dc5936471",
    "rechecks_used": 1,
    "rechecks_remaining": 0,
    "capability_open": false,
    "deployment": false
  }
}
---

# Owner-scoped data-only provider connection

Exact stable inputs are rebound and ACTUAL START is open. Capability remains closed and no provider network is authorized.
