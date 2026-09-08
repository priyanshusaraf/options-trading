---
{
  "id": "strategy-os-operations-skills",
  "phase": "tooling",
  "status": "accepted",
  "kind": "owner_requested_skill_authoring",
  "goal": "Add the eight requested billing, observability, incident, dependency, resource, privacy, email and support skills after reviewing use cases and related skills.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "Eight skills and their discovery metadata validate, all local references resolve, representative scenarios are reviewed, repository architecture and harness checks pass, and all inherited files and product/programme authority remain unchanged."},
  "risk_tags": ["important", "agent-tooling", "documentation"],
  "required_docs": [
    {"path": "paper-trader/docs/program/owner-steers/04-RUNTIME-ECONOMICS-PROVIDER-CAPABILITIES.md", "sections": ["1. Compile a resource plan with every strategy", "9. Resource QoS priorities", "10. Per-deployment resource ceilings", "12. Provider fallback", "13. Cost telemetry"]},
    {"path": "paper-trader/docs/strategy-os-v0-release-audit-2026-08-27/06-TEST-SECURITY-DATA-AND-DEPLOYMENT-GATES.md", "sections": ["Security findings", "V0 test matrix", "Deployability gates"]}
  ],
  "allowed_paths": [
    ".agents/skills/razorpay-billing-review",
    ".agents/skills/observability-instrumentation",
    ".agents/skills/incident-response-and-postmortem",
    ".agents/skills/dependency-license-sbom",
    ".agents/skills/resource-plan-and-cost-audit",
    ".agents/skills/privacy-data-flow-review",
    ".agents/skills/transactional-email-review",
    ".agents/skills/support-diagnostics-runbook",
    "paper-trader/docs/agent/tasks/strategy-os-operations-skills.md",
    ".agent/runs/strategyos-operations-skills"
  ],
  "protected_paths": ["AGENTS.md", ".codex", "paper-trader/backend", "paper-trader/frontend", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/programme", "paper-trader/docs/agent/DEPLOYABILITY.md"],
  "nonclaims": ["No payment/email/telemetry vendor adoption or product implementation.", "No charges, refunds, DNS mutation, production access, external messages, legal conclusions, pricing or retention decisions.", "No production audit, security certification, compliance verdict or release sign-off."],
  "owner_gates": ["The owner requested these eight skills as a continuation of the prior skill-authoring work.", "Future use preserves existing commercial, privacy, live-money, infrastructure and deployment gates."],
  "stop_conditions": ["The addition requires changing inherited code, skills, dependencies or programme pointers.", "A source gap would require inventing vendor behavior, legal obligations or product policy."],
  "deployment_impact": {"classification": "none", "reason": "Instructions, discovery metadata and a diagnostic output reference only; no running service, schema, dependency or infrastructure changes."},
  "model_route": {"owner": "user-selected", "delegation": "none"},
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": ["All eight requested names exist as discoverable repository skills.", "Each has a concrete trigger, evidence output, applicable owner gates and links to related workflows.", "Vendor/standards claims use primary sources; current product support is not inferred from a requested skill.", "No second IR, resource plan, entitlement authority or financial ledger is introduced by the guidance."],
  "test_plan": ["Bundled skill validator, discovery metadata checks and local reference resolution.", "Repository architecture validator before/after and existing .codex harness tests.", "Manual scenario walkthroughs, explicitly not independent model or product evaluations.", "Full pre-existing file/hash/status preservation check."],
  "review": {"required": false, "assignment_id": "operations_skills_self_review", "base_sha": "HEAD", "review_paths": [".agents/skills", "paper-trader/docs/agent/tasks/strategy-os-operations-skills.md"], "exclude_paths": ["paper-trader/backend", "paper-trader/frontend"], "reason": "Important instruction-only authoring with local review; no critical product implementation."}
}
---

# Strategy OS operational skill authoring

This tooling capsule does not replace CURRENT.md's active V0-A product capsule.
No child agents or programme transitions are part of the work.

## Use cases and related skills reviewed before authoring

| Skill | Concrete use case | Existing responsibility retained |
| --- | --- | --- |
| razorpay-billing-review | Forged checkout amount, duplicate/out-of-order webhook, ambiguous refund or test payment granting live access. | Tenant/auth audits own identity; risk-weighted verification and critical review own proof burden; commercial policy remains with the owner. |
| observability-instrumentation | A stale worker looks healthy, an exporter fails, labels explode or traces leak strategy parameters. | Deployability owns operational gates; existing telemetry/resource contracts remain canonical. |
| incident-response-and-postmortem | A suspected leak, corrupt research output or outage needs bounded containment, evidence and recovery. | Existing execution, privacy, release and deployment gates stay in force during incidents. |
| dependency-license-sbom | A release bundles a transitive package, vendored code, container or proprietary chart asset absent from the manifest review. | prior-art-review-gate owns pre-adoption inspection; legal/commercial decisions stay owner-gated. |
| resource-plan-and-cost-audit | Instrument fan-out, concurrent jobs or provider subscriptions exceed a declared ceiling or distort unit costs. | Canonical ResourcePlan, separate policy/calibration identities and provider conformance remain authoritative. |
| privacy-data-flow-review | An export/deletion request or new processor exposes strategy IP, credentials, analytics or LLM context. | Tenant isolation, auth and ASVS reviews remain separate from privacy/legal conclusions. |
| transactional-email-review | Reset links leak to tracking, DMARC alignment fails or complaint events are ignored. | Auth owns token lifecycle; deployment/DNS and processor adoption still need authorization. |
| support-diagnostics-runbook | Support requests a full strategy export or HAR to investigate a failed job. | Tenant/privacy controls limit access; engineering receives only scoped evidence, not automatic impersonation. |

Repository inspection found relevant resource-plan and execution telemetry contracts
in `app/ir/resource_plan.py`, `test_phase5_language_resource_contracts.py`,
`test_engine_observability.py` and `test_execution_telemetry.py`. These were inspected,
not executed as product evidence. A scoped search did not establish a Razorpay or
transactional-email implementation; the new skills must inspect actual support
before proposing changes rather than treating their installation as feature delivery.

## Primary sources

- Razorpay [webhook validation](https://razorpay.com/docs/webhooks/validate-test/),
  [checkout integration](https://razorpay.com/docs/payments/payment-gateway/web-integration/standard/integration-steps/)
  and [refunds](https://razorpay.com/docs/payments/refunds/).
- OpenTelemetry [resource conventions](https://opentelemetry.io/docs/specs/semconv/resource/)
  and [sensitive data handling](https://opentelemetry.io/docs/security/handling-sensitive-data/).
- NIST [incident-response guidance](https://www.nist.gov/publications/incident-response-recommendations-and-considerations-cybersecurity-risk-management-csf)
  and [privacy framework use](https://www.nist.gov/privacy-framework/getting-started-0).
- [CycloneDX specification](https://cyclonedx.org/specification/overview/) and
  [SLSA provenance](https://slsa.dev/spec/v1.2/provenance).
- Amazon SES [DMARC guidance](https://docs.aws.amazon.com/ses/latest/dg/send-email-authentication-dmarc.html)
  and [bounce/complaint notifications](https://docs.aws.amazon.com/ses/latest/dg/monitor-sending-activity-using-notifications.html),
  used as concrete provider examples, not an SES adoption decision.

The web reader rejected Razorpay's negotiated content type. A direct read-only
public-document fetch succeeded; source bytes, URLs and hashes are retained under
`.agent/runs/strategyos-operations-skills/root/sources/`. No vendor account or API
credential was used.

## Evidence

Evidence root: `.agent/runs/strategyos-operations-skills/root/`.

| Check | Observed result | Evidence |
| --- | --- | --- |
| Bundled skill validator and metadata | Eight skills pass; implicit invocation remains enabled by default. | `skill-validation.log`, `skill-validation.json`, `discovery-metadata.log` |
| Local references | 23 links resolve. | `skill-validation.json` |
| Repository architecture validator | PASS before and after; no failures. | `architecture-baseline.log`, `architecture-final.log` |
| Existing agent harness | 74 tests pass. | `harness-tests.log` |
| Manual scenario review | Eight scenarios inspected against written instructions; not independent model evaluations. | `scenario-review.md` |
| Preservation | All 1,792 pre-existing paths unchanged; all 590 inherited status entries preserved; HEAD/branch unchanged. | `baseline.json`, `preservation.json`, `preservation-check.log` |

Added 18 files: eight entrypoints, eight discovery metadata files, one diagnostic
receipt reference and this capsule. Existing skills, product files, dependencies,
configuration and programme pointers remain unchanged. No payment/refund, provider
account, email, DNS, production service, data deletion or external disclosure occurred.

These checks establish instruction packaging, reference integrity, harness
compatibility and preservation. They do not establish future agent compliance,
billing/security/privacy correctness, deliverability, incident readiness or release
approval. Product and independent model evaluations were not run.
