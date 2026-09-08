---
{
  "id": "strategy-os-v0-signal-alert-attention-contract",
  "phase": "v0",
  "status": "rejected_replan_required",
  "kind": "critical_unpublished_monitoring_domain_contract",
  "goal": "Freeze pure canonical contracts for a monitoring-domain event, SignalAlert, delivery attempt and append-only attention history without persistence, routes, registry publication or execution authority.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "The five distinct immutable facts and their deterministic derivation/projection rules are implemented and directly proven, legacy execution SignalEvent meaning is untouched, and one independent Critical reviewer returns SPEC PASS and QUALITY PASS."
  },
  "risk_tags": [
    "critical",
    "monitoring-truth",
    "tenant-isolation",
    "alert-idempotency",
    "attention-reconstructibility",
    "execution-authority-separation"
  ],
  "required_docs": [
    {
      "path": "paper-trader/docs/strategy-os-v1-v2-v3/STRATEGY_OS_V0_V6_OWNER_DIRECTION_RECONCILIATION_2026-08-29.md",
      "sections": ["Conflict decisions", "Current V0 programme reconciliation"]
    },
    {
      "path": ".agent/runs/strategy-os-v0-launch-convergence/architecture-decision.md",
      "sections": ["Monitoring-only lifecycle", "SignalTransition", "Protection intent", "Architecture invariant matrix"]
    },
    {
      "path": ".agent/runs/strategy-os-v0-launch-convergence/agents/nodes-signals/report.md",
      "sections": ["Smallest V0 monitoring-only lifecycle", "Candidate durable schemas", "Contradictions and missing seams", "Candidate tests and false results prevented"]
    },
    {
      "path": ".agent/runs/strategy-os-v0-monitoring-intent-contract/report.md",
      "sections": ["Verdict", "Evidence", "Boundary"]
    }
  ],
  "dependency_gate": "Accepted V0-V6 reconciliation and sealed monitoring-intent implementation package; no independent family-assurance or registry-publication claim is consumed by this pure contract.",
  "allowed_paths": [
    "paper-trader/backend/app/monitoring/__init__.py",
    "paper-trader/backend/app/monitoring/contracts.py",
    "paper-trader/backend/tests/test_v0_signal_alert_attention_contract.py",
    "paper-trader/docs/agent/tasks/strategy-os-v0-signal-alert-attention-contract.md",
    ".agent/runs/strategy-os-v0-signal-alert-attention-contract"
  ],
  "new_paths": [
    "paper-trader/backend/app/monitoring/__init__.py",
    "paper-trader/backend/app/monitoring/contracts.py",
    "paper-trader/backend/tests/test_v0_signal_alert_attention_contract.py",
    ".agent/runs/strategy-os-v0-signal-alert-attention-contract"
  ],
  "protected_paths": [
    "paper-trader/backend/app/db",
    "paper-trader/backend/migrations",
    "paper-trader/backend/app/api",
    "paper-trader/backend/app/main.py",
    "paper-trader/backend/app/engine",
    "paper-trader/backend/app/execution",
    "paper-trader/backend/app/providers",
    "paper-trader/backend/app/core/deployments.py",
    "paper-trader/backend/app/ir/library.py",
    "paper-trader/backend/app/ir/registry.py",
    "paper-trader/backend/app/ir/runtime.py",
    "paper-trader/backend/app/ir/hashing.py",
    "paper-trader/backend/app/ir/first_party/monitoring_intent_v2.py",
    "paper-trader/docs/agent/tasks/strategy-os-v0-monitoring-persistence.md",
    "paper-trader/frontend",
    "/Users/priyanshusaraf/dev/strategy-os-frontend",
    "paper-trader/scripts/deploy.sh"
  ],
  "frozen_contract": {
    "facts": [
      "MonitoringSignalEvent is the immutable monitoring-domain strategy decision fact and is never the legacy execution SignalEvent.",
      "SignalAlert is a canonical tenant-facing fact derived at most once from one eligible MonitoringSignalEvent.",
      "AlertDeliveryAttempt is an append-only attempt outcome; failure cannot erase or mutate SignalAlert.",
      "AlertAttentionEvent is an append-only READ, ACKNOWLEDGE or DISMISS action with deterministic request identity and sequence.",
      "AlertAttentionProjection is rebuilt only from attention events; initial unread state and read/acknowledged/dismissed timestamps never change signal validity or expiry."
    ],
    "derivation": [
      "BUY, SELL and EXIT may derive exactly one alert when the event, freshness, entry reference and authored SL/TP evidence are valid.",
      "HOLD, refusal, missing/invalid/stale data, repeated target state or invalid protection geometry returns a typed no-alert result, not an alert guess.",
      "The alert identity is a canonical content address over owner, assignment, monitoring-event identity and immutable display/evidence facts.",
      "Alert event time, latest consumed data time, knowledge cutoff and valid-until remain distinct UTC facts; attention does not extend them.",
      "Owner, assignment, strategy/graph/implementation/admission, canonical instrument, state, reason and lineage identities remain attributable through alert and attention."
    ],
    "v0_attention": ["READ", "ACKNOWLEDGE", "DISMISS"],
    "v0_delivery_channels": ["IN_APP"],
    "reserved_not_implemented": ["snooze policy", "email", "push", "SMS", "webhook delivery", "retention policy", "analytics policy"]
  },
  "scope": [
    "Implement immutable typed value objects, canonical serialization/addressing, validation, one event-to-alert derivation result, delivery-attempt validation and a pure attention reducer.",
    "Reuse the canonical IR hashing helper without changing it. Accept monitoring-intent evidence as validated immutable input; do not publish or execute IR.",
    "Reject owner/alert/assignment mismatches, non-UTC or non-monotonic time, unknown actions/channels/outcomes, non-canonical decimals/addresses, sequence gaps, duplicate request identities with different facts and any order/broker/account/capital/position/deployment field.",
    "Keep display-safe symbol and tenant-visible reason evidence in tenant facts only. Add no operator/admin projection, analytics event or unrestricted text field."
  ],
  "acceptance": [
    "Distinct type/schema identities and import boundaries prove no alias or dependency on legacy execution SignalEvent, engine, execution, provider, database or routes.",
    "Golden BUY/SELL/EXIT alert payloads preserve entry reference plus authored and resolved SL/TP facts; HOLD and every invalid/freshness/refusal condition return typed no-alert outcomes.",
    "Repeated derivation is byte-identical and content-address identical; a material immutable input change changes the address.",
    "Delivery failure leaves the canonical alert unchanged; duplicate attempt identity with different content refuses.",
    "Attention replay is deterministic across restart, rejects cross-owner/cross-alert events and sequence gaps, and proves read/acknowledge/dismiss cannot change alert validity/expiry.",
    "Focused, full affected compatibility, 100,000-fact resource, restart/serialization and genuine isolated mutation checks pass with exact restoration and protected hashes.",
    "One fresh independent Critical reviewer returns SPEC PASS and QUALITY PASS."
  ],
  "test_plan": [
    "Owner-authored golden fixtures and negative/canonicalization tests first, then implementation; never derive expected identities from implementation output.",
    "Exercise action/freshness/protection truth tables, tenant and sequence adversaries, serialization round trips, shuffled/replayed attention input, delivery failure, resource ceilings and forbidden-import/field mutations.",
    "Run affected legacy SignalEvent, IR hashing, monitoring-intent and no-live-under-pytest tests after focused proof."
  ],
  "parallel_budget": 0,
  "assignments": [],
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "medium",
    "fork_turns": "none",
    "service_tier": "priority"
  },
  "owner_task": "/root/v0_signal_alert_attention_contract",
  "review": {
    "required": true,
    "assignment_id": "v0_signal_alert_attention_contract_review",
    "agent": "critical-reviewer",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "reason": "A false or mutable alert/attention contract can misstate strategy intent, leak tenant facts or become an execution-authority shortcut.",
    "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c",
    "package": ".agent/runs/strategy-os-v0-signal-alert-attention-contract/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/monitoring/__init__.py",
      "paper-trader/backend/app/monitoring/contracts.py",
      "paper-trader/backend/tests/test_v0_signal_alert_attention_contract.py",
      "paper-trader/docs/agent/tasks/strategy-os-v0-signal-alert-attention-contract.md",
      ".agent/runs/strategy-os-v0-signal-alert-attention-contract"
    ],
    "exclude_paths": [
      "paper-trader/backend/app/db",
      "paper-trader/backend/migrations",
      "paper-trader/backend/app/api",
      "paper-trader/backend/app/engine",
      "paper-trader/backend/app/execution",
      "paper-trader/frontend"
    ],
    "output": ".agent/runs/strategy-os-v0-signal-alert-attention-contract/review/verdict.json",
    "verdicts": ["SPEC", "QUALITY"],
    "max_rechecks": 1
  },
  "owner_gates": [
    "The accepted handoff reconciliation authorizes this exact pure contract owner after monitoring-intent closes; it does not authorize persistence or runtime work.",
    "Stop before any schema, migration, route, worker, frontend, provider, delivery integration, registry publication, order, money or deployment behavior."
  ],
  "stop_conditions": [
    "A shared model, migration, legacy SignalEvent, route, runtime or monitoring-intent byte must change.",
    "A notification-channel, retention, snooze or analytics policy decision is required.",
    "An alert cannot retain exact event/strategy/instrument/time/freshness/reason/protection lineage without introducing execution authority."
  ],
  "deployment_impact": {
    "classification": "compatible unpublished pure domain contract; no schema, service, route, dependency or configuration change",
    "future_owner": "strategy-os-v0-monitoring-persistence consumes the accepted contract without redefining it"
  },
  "nonclaims": [
    "No persistence, migration, API, frontend, notification delivery integration, admin/analytics view, registry publication, provider data, execution, order, position, capital, PnL, deployment or V0 completion.",
    "SL/TP remain authored monitoring evidence and hypothetical display levels, never exchange protection."
  ],
  "implementation_closure": {
    "verdict": "IMPLEMENTATION PASS PENDING INDEPENDENT CRITICAL REVIEW",
    "review_package": ".agent/runs/strategy-os-v0-signal-alert-attention-contract/review-package.json",
    "review_package_sha256": "3e6b7e4bd36791ce7ddc008e09e9c0daa74e7f819dd22e76bf13f6183b84bd5e",
    "report": ".agent/runs/strategy-os-v0-signal-alert-attention-contract/implementation-report.md",
    "review_task": "/root/v0_signal_alert_attention_review",
    "persistence": false,
    "publication": false,
    "deployment": false
  },
  "first_review": {
    "verdict": "SPEC FAIL / QUALITY FAIL",
    "verdict_path": ".agent/runs/strategy-os-v0-signal-alert-attention-contract/review/verdict.json",
    "verdict_sha256": "5f2c061d30479ee7ae03d8fd427f0f91bf730a1c5005f36cc45c6acb91185f08",
    "finding_ids": [
      "F1-OPPOSITE-STATE-TRANSITIONS-REFUSED",
      "F2-INVALID-HOLD-MISCLASSIFIED",
      "F3-ALERT-FRESHNESS-ATTRIBUTION-MISSING",
      "F4-PROTECTED-HASH-PROOF-VACUOUS"
    ],
    "rechecks_used": 0,
    "rechecks_remaining": 1
  },
  "correction_scope": [
    "Admit the exact SHORT-to-LONG BUY and LONG-to-SHORT SELL transitions while continuing to refuse the unsupported REVERSE operation noun.",
    "Validate refusal/missing/invalid/stale truth before the valid HOLD branch so unavailable market truth never becomes HOLD.",
    "Carry the closed freshness fact into SignalAlert serialization and canonical identity.",
    "Replace failed protected-hash logs only with trustworthy pre-slice receipts and attributable current manifests; if no trustworthy full baseline exists, stop and replan without consuming the recheck."
  ],
  "replan": {
    "reason": "No trustworthy full predecessor baseline covered the monitoring-persistence capsule and external frontend root; the only recheck was not consumed.",
    "decision": ".agent/runs/strategy-os-v0-signal-alert-attention-correction-replan/decision.json",
    "successor": "paper-trader/docs/agent/tasks/strategy-os-v0-signal-alert-attention-correction.md"
  }
}
---

# Signal alert and attention contract

Freeze distinct monitoring-event, alert, delivery-attempt and attention facts before any shared persistence owner starts.
