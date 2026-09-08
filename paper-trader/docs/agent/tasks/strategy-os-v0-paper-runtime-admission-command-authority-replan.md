---
{
  "id": "strategy-os-v0-zerodha-data-static-scope",
  "lineage_id": "strategy-os-v0-paper-runtime-admission-command-authority-replan",
  "phase": "v0",
  "status": "accepted",
  "kind": "critical_read_only_exhausted_runtime_authority_replan",
  "goal": "Replan the exhausted paper-runtime lineage around two exact residual defects: missing durable StrategyAdmission authentication and incomplete PaperCommand-to-PaperInstrumentAuthority relationship validation.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "One zero-product-write decision defines exact existing durable admission authority, complete command/authority field relations, failure semantics, mutation gates, paths, collisions and a fresh successor correction capsule."},
  "risk_tags": ["critical", "paper-trading", "execution", "admission", "authority", "reconciliation", "exhausted-recheck"],
  "depends_on": ["strategy-os-v0-paper-trading-runtime-foundation"],
  "dependency_gate": {"first_verdict_sha256": "b0ebccad02d6395021489176ca19d8e1a49cac7ddae7fdea5f8bda90f37587f6", "exhausted_recheck_sha256": "496b0a24d8ac132e9af83dc2104bc75bcaa8b70eaa400ebf130fafcdc8eb5a33", "policy": "The rejected lineage cannot receive another correction; a fresh bounded successor requires this architecture decision."},
  "required_docs": [
    {"path": ".agent/runs/strategy-os-v0-paper-trading-runtime-foundation/review/verdict.json", "sections": ["SPEC", "QUALITY", "remaining_evidence_gaps"]},
    {"path": ".agent/runs/strategy-os-v0-paper-trading-runtime-foundation/review/recheck-verdict.json", "sections": ["SPEC", "QUALITY", "independent_verification", "remaining_evidence_gaps", "owner_gates"]},
    {"path": ".agent/runs/strategy-os-v0-paper-trading-runtime-replan/decision.json", "sections": ["existing_accepted_authorities", "chosen_architecture", "state_and_recovery_requirements", "external_gates"]}
  ],
  "allowed_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-paper-runtime-admission-command-authority-replan.md", ".agent/runs/strategy-os-v0-paper-runtime-admission-command-authority-replan"],
  "new_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-paper-runtime-admission-command-authority-replan.md", ".agent/runs/strategy-os-v0-paper-runtime-admission-command-authority-replan"],
  "protected_paths": ["paper-trader/backend", "paper-trader/frontend", "/Users/priyanshusaraf/dev/strategy-os-frontend", "paper-trader/scripts/deploy.sh", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/programme/PROGRAMME.json"],
  "scope": ["Trace the exact immutable StrategyAdmission model, owner/strategy/graph/implementation/status fields and current verification semantics already accepted; reject any second admission authority.", "Define the complete field-by-field relation from PaperInstrumentAuthority and MonitoringSignalEvent into PaperCommand and canonical runtime context, including positive deployment and action-sensitive quantity.", "Specify alert-independent closed PAPER refusal for missing/corrupt/mismatched admission before intent, position, charge, reservation consumption or cash effect.", "Define construction, strict decode, context validation and broker-use checks plus direct forged/missing relation mutations.", "Name the smallest fresh successor paths and tests without changing provider, live, API, frontend, schema or deployment boundaries."],
  "acceptance": ["Decision names the exact durable StrategyAdmission lookup key and every verified field/status; a missing row cannot authorize paper effects.", "Decision provides a complete command/authority/event relation matrix with no self-authenticating address or duplicated authority.", "Successor is additive over the accepted paper runtime and preserves Alerts/Paper independence, risk-reducing exits, capital reservation convergence and live fail-closed behavior.", "Exact RED/GREEN, mutation, restart, affected-suite and Critical review gates are declared; architecture passes with zero product writes."],
  "test_plan": ["Read-only source/model/test/evidence inspection and architecture validation; product tests belong to the fresh successor."],
  "risk_classification": {"tier": "Critical", "reason": "A false admission or authority-conflicting command can create a user-visible paper position and corrupt PnL."},
  "parallel_budget": 1,
  "assignments": [{"id": "v0_paper_runtime_admission_command_replan_owner", "agent": "worker", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "fork_turns": "none", "mode": "read-only-architecture-evidence", "depends_on": [], "write_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-paper-runtime-admission-command-authority-replan.md", ".agent/runs/strategy-os-v0-paper-runtime-admission-command-authority-replan"], "output": ".agent/runs/strategy-os-v0-paper-runtime-admission-command-authority-replan/decision.json"}],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "/root",
  "review": {"required": false, "assignment_id": "v0_paper_runtime_admission_command_replan_owner", "agent": "worker", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "reason": "Read-only exhausted-lineage architecture decision; the successor receives the Critical recheck lineage.", "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c", "package": ".agent/runs/strategy-os-v0-paper-runtime-admission-command-authority-replan/decision.json", "review_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-paper-runtime-admission-command-authority-replan.md", ".agent/runs/strategy-os-v0-paper-runtime-admission-command-authority-replan"], "exclude_paths": ["paper-trader/backend", "paper-trader/frontend", "paper-trader/scripts/deploy.sh"], "output": ".agent/runs/strategy-os-v0-paper-runtime-admission-command-authority-replan/decision.json", "verdicts": ["ARCHITECTURE", "AUTHORITY", "EXECUTION_SAFETY"], "max_rechecks": 0},
  "owner_gates": ["No live/provider/network/data-right, second IR/admission/capital authority, schema/migration, shared API/frontend, production account/data, VPS/deployment or live money action."],
  "stop_conditions": ["Exact StrategyAdmission semantics cannot be reused without schema or canonical-authority change.", "A complete command relationship requires changing monitoring, admission, capital or live authority meaning."],
  "deployment_impact": {"classification": "none; read-only exhausted-lineage replan", "highest_current_claim": "locally_runnable", "release_deployable": false, "production_rehearsed": false, "deployed": false},
  "replan_result": {"verdict": "KEEP + HARDEN IN ONE FRESH SUCCESSOR", "decision_sha256": "1c77e983f024cffe5cf06b33dc8c943702a82ebed522e3157ccdb3ed0b1812e0", "authority_matrix_sha256": "6b0fa3c9d83307bdb246a469bc5393725e46af9ad3400fcca938a9d20308b47b", "successor": "strategy-os-v0-paper-runtime-admission-command-authority-correction", "product_writes": 0, "deployment": false},
  "nonclaims": ["No product correction, paper-runtime acceptance, PostgreSQL contention, provider/live/API/frontend/deployment or V0 completion."]
}
---

# Paper runtime admission and command authority replan

Fresh architecture decision after the paper-runtime correction lineage exhausted its
sole Critical recheck with two exact authority gaps.

## Sealed architecture decision

**KEEP + HARDEN IN ONE FRESH SUCCESSOR.** Reuse the existing immutable
`StrategyAdmission` and paper-runtime contracts. Do not add a second admission,
command, lifecycle, capital, or broker authority and do not change a schema.

The durable admission lookup key is exactly `(owner_id, admission_address)` through
`app.core.strategy_admissions.get`. The successor must parse the row's canonical
`artifact_json` with the existing admission constructor and call
`strategy_admissions.require_current`. It must then compare the reconstructed receipt's
owner, graph identifier, graph version, graph address, execution identity, and, for the
Phase 4 receipt used by this lineage, `phase4_data_binding` resolved-graph and
implementation-closure addresses with the exact runtime assignment, instrument
authority, monitoring event, and paper command.

`StrategyAdmission` deliberately has no mutable status, revocation, or withdrawal
column. Presence plus canonical current verification is the admission fact. Assignment
status and withdrawal remain in the existing monitoring/runtime lifecycle authority:
`ACTIVE` may author entries; `PAUSED` and `WITHDRAWN` refuse entries; an exact held-
position `EXIT` remains available. Deployment active/armed/halted state remains the
entry gate. The successor must not invent admission status or copy withdrawal into the
admission row.

Missing, malformed, non-canonical, owner-mismatched, identity-mismatched, stale, or
dependency-mismatched admission evidence returns a closed PAPER refusal before intent
creation, position/trade mutation, charge computation, reservation consumption, or cash
effect. ALERTS remains an independently attempted and idempotent branch for `BOTH`.
Persisted intent or effect rows never substitute for the current admission check.

The complete field relation and every enforcement location are sealed in
`.agent/runs/strategy-os-v0-paper-runtime-admission-command-authority-replan/authority-matrix.json`.
The decision, successor gates, collision baseline, deployment nonclaims, and evidence
hashes are sealed beside it in `decision.json`, `report.md`, and `hashes.json`.

## Fresh successor

The exact successor capsule is
`paper-trader/docs/agent/tasks/strategy-os-v0-paper-runtime-admission-command-authority-correction.md`.
Its only product paths are:

- `paper-trader/backend/app/paper_runtime/contracts.py`
- `paper-trader/backend/app/paper_runtime/service.py`
- `paper-trader/backend/app/engine/broker.py`
- `paper-trader/backend/tests/test_v0_paper_runtime.py`
- `paper-trader/backend/tests/test_v0_paper_runtime_recovery.py`

It may import the existing admission/model seams but must not edit them. It must start
from a new dirty-tree hash baseline because all three product files and both focused
tests already contain concurrent inherited edits.

The successor opens with RED missing/corrupt/mismatched admission probes and a
field-by-field forged command/context matrix. GREEN requires closed PAPER refusal with
independent ALERTS, positive `deployment_id`, quantity zero only for `HOLD`, positive
quantity for every non-`HOLD`, strict source-aware command/context decoding, and broker-
use revalidation. Killed/restored mutations must disable the admission lookup,
canonical-byte check, each cross-field equality, positive deployment guard, non-HOLD
quantity guard, and broker validation. Restart evidence covers before intent, after
intent, after paper commit, stale/missing admission on retry, exact exit retry, lease
loss/reclaim, and reservation convergence. The affected suite is the two V0 paper
runtime files plus existing paper authority, execution admission attribution, paper
money, lifecycle-manifest, and no-live-under-pytest guards. After an integrated evidence
package exists, one Critical reviewer evaluates SPEC and QUALITY; the fresh lineage has
at most one recheck.

No provider, network, live, API, frontend, schema, migration, PostgreSQL contention,
capacity, retention, production-readiness, deployment, or V0-completion claim follows.
