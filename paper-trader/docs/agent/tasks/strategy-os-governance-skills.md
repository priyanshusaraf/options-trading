---
{
  "id": "strategy-os-governance-skills",
  "phase": "tooling",
  "status": "accepted",
  "kind": "owner_requested_skill_authoring",
  "goal": "Add all sixteen requested Strategy OS governance skills after checking their use cases, existing skills and canonical scope, without changing product or programme authority.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "All sixteen skills and their discovery metadata validate; local references resolve; representative use cases and limitations are recorded; the repository architecture validator and affected harness tests pass; inherited files, protected paths and programme pointers remain unchanged."},
  "risk_tags": ["important", "agent-tooling", "documentation"],
  "required_docs": [
    {"path": "paper-trader/docs/strategy-os-v1-v2-v3/CANONICAL-DOCUMENT-RECONCILIATION.md", "sections": ["Authority and precedence", "Contradictions introduced by the latest owner direction"]},
    {"path": "paper-trader/docs/strategy-os-v1-v2-v3/STRATEGY_OS_HYBRID_PRODUCT_DIRECTION_AND_V1_PROGRAMME_REBASE_2026-08-24.md", "sections": ["0. Authority, precedence, and interpretation"]},
    {"path": "paper-trader/docs/program/owner-steers/05-V1-IMPLEMENTATION-PRIORITIES-VERIFICATION.md", "sections": ["1. Risk-weighted verification", "2. Test rule", "3. Test cadence"]}
  ],
  "allowed_paths": [
    ".agents/skills/strategyos-repo-orientation",
    ".agents/skills/canonical-document-precedence",
    ".agents/skills/v1-release-scope-classifier",
    ".agents/skills/architecture-invariant-audit",
    ".agents/skills/prior-art-review-gate",
    ".agents/skills/risk-weighted-verification",
    ".agents/skills/tenant-isolation-audit",
    ".agents/skills/auth-and-session-hardening",
    ".agents/skills/asvs-security-review",
    ".agents/skills/database-migration-safety",
    ".agents/skills/anti-lookahead-and-market-truth",
    ".agents/skills/research-validity-audit",
    ".agents/skills/provider-adapter-conformance",
    ".agents/skills/execution-safety-and-reconciliation",
    ".agents/skills/deterministic-capital-admission",
    ".agents/skills/release-readiness-review",
    "paper-trader/docs/agent/tasks/strategy-os-governance-skills.md",
    ".agent/runs/strategyos-governance-skills"
  ],
  "protected_paths": ["AGENTS.md", ".codex", "paper-trader/backend", "paper-trader/frontend", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/programme", "paper-trader/docs/agent/DEPLOYABILITY.md"],
  "nonclaims": ["No product implementation, programme transition, deployment, provider access, licence adoption, security certification or release sign-off.", "Instruction validation is not a behavioral guarantee that every future agent will obey a skill."],
  "owner_gates": ["The owner explicitly requested all sixteen skills and investigation of their use cases and related skills.", "This tooling request does not open any product capsule or safety gate."],
  "stop_conditions": ["A change requires inherited product, existing skill, configuration or programme files.", "An unresolved source conflict would require inventing product scope or authority."],
  "deployment_impact": {"classification": "none", "reason": "Repository instructions and discovery metadata only; no runtime, schema, dependency, service or infrastructure change."},
  "model_route": {"owner": "user-selected", "delegation": "none"},
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": ["All requested names exist as discoverable repository skills.", "Each has a concrete trigger, useful workflow, evidence output and relevant boundaries.", "The original nine-document inventory is reconciled with later owner decisions, the hybrid addendum and the active V0 profile.", "Related skills retain their execution, architecture, runtime, critical-review and deployability responsibilities.", "No automatic product audit, new infrastructure, independent reviewer or runtime is started merely by installing the skills."],
  "test_plan": ["Bundled skill quick_validate for all sixteen skills.", "Resolve Markdown references and validate openai.yaml metadata.", "Repository architecture validator before and after; affected .codex harness tests.", "Manual scenario walkthroughs, explicitly distinguished from independent model evaluations.", "Compare all pre-existing file hashes, status and HEAD with the pre-edit baseline."],
  "review": {"required": false, "assignment_id": "governance_skills_self_review", "base_sha": "HEAD", "review_paths": [".agents/skills", "paper-trader/docs/agent/tasks/strategy-os-governance-skills.md"], "exclude_paths": ["paper-trader/backend", "paper-trader/frontend"], "reason": "Important instruction-only authoring; local review and validation, no critical product boundary changes."}
}
---

# Strategy OS governance skill authoring

This owner-requested tooling capsule does not replace the product capsule selected
by CURRENT.md. The product stage remains V0-A. Run no child agents and do not change
programme state for this work.

## Use cases and existing responsibilities

These are intended uses, not claims that the product has passed these audits.

| New skill | Representative use case | Related skill and responsibility retained |
| --- | --- | --- |
| strategyos-repo-orientation | Resume in a dirty or wrong checkout before editing. | executing-strategy-os-slices still owns the bounded implementation. |
| canonical-document-precedence | Reconcile the older nine-document baseline with later scope decisions. | architecting-strategy-os-phases still owns architecture decisions. |
| v1-release-scope-classifier | Classify Dynamic Watchlists, options execution or licensed data without opening implementation. | architecting-strategy-os-phases decides the accepted design. |
| architecture-invariant-audit | Trace a graph revision through dataset, admission, binding and exact held position. | reviewing-strategy-os-critical-changes owns independent final review. |
| prior-art-review-gate | Evaluate a queue, cache, auth component or broker library before building/adopting it. | architecting-strategy-os-phases owns adopt/refactor/defer decisions. |
| risk-weighted-verification | Distinguish a copy edit from a causal, tenancy or order-state defect. | executing-strategy-os-slices owns test execution and slice closure. |
| tenant-isolation-audit | Tenant B guesses A's object ID or receives A's job/event/cache output. | reviewing-strategy-os-critical-changes owns the final critical verdict. |
| auth-and-session-hardening | Reset a password and prove the old session and recovery token cannot be reused. | running-strategy-os-safely owns any isolated runtime evidence. |
| asvs-security-review | Inspect one security boundary or a declared release-level ASVS scope. | Domain audits supply evidence; no duplicate reviewer is implied. |
| database-migration-safety | Upgrade prior-schema data and rehearse a supported restore or forward repair. | auditing-strategy-os-deployability retains rollout/restore obligations. |
| anti-lookahead-and-market-truth | Detect forming-bar leakage or today's instrument list substituted into history. | Existing research review retains the broader result-integrity gate. |
| research-validity-audit | Evaluate a searched winner against locked OOS and the complete trial population. | anti-lookahead-and-market-truth provides causal/data proof. |
| provider-adapter-conformance | An adapter claims a capability but fails on token reuse, partial data or reconnect. | Existing architecture skill retains provider role and licence rules. |
| execution-safety-and-reconciliation | Recover from ambiguous submission, a partial fill or cancel/fill crossing. | Existing critical review and owner gates remain mandatory. |
| deterministic-capital-admission | Replay simultaneous signals around reservation commit and process death. | Execution audit owns downstream orders/fills; no second capital authority. |
| release-readiness-review | Assess actual launch journeys against exact-build evidence and missing approvals. | auditing-strategy-os-deployability owns deployment evidence levels. |

## Source findings that shape the skills

- The nine original documents are six technical steers, two August 11 product
  documents and the August 24 architecture memo. They are not the entire current
  authority set. The hybrid addendum and reconciliation supersede older timing;
  current owner decisions and the active capsule still control implementation.
- V1.1 is retired as a separate bucket in the accepted rebase. Preserve the label
  for historical classification, with an explicit superseded status.
- The active V0 release profile forbids execution authority. Future execution
  reviews must not turn that into permission to start an execution runtime.
- Existing migration guidance includes historical Alembic/downgrade language;
  the active V0 design specifies additive forward-only migrations. Inspect the
  actual migration mechanism and supported recovery contract before selecting
  commands. Never install a new migration framework to satisfy an old example.
- Existing skills remain intact. New domain audits feed their evidence into the
  established execution, critical review and deployability workflows.

Official references checked during authoring: [Codex skills](https://developers.openai.com/codex/skills/),
[OWASP ASVS](https://owasp.org/www-project-application-security-verification-standard/),
[authentication](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
and [session management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html).
Security references are guidance, not certification or legal advice.

## Evidence

Evidence root: `.agent/runs/strategyos-governance-skills/root/`.

| Check | Observed result | Evidence |
| --- | --- | --- |
| Bundled skill validator and discovery metadata | 16 skills pass; implicit invocation remains enabled by default. | `skill-validation.log`, `skill-validation.json` |
| Local Markdown references | 45 links resolve to existing files. | `skill-validation.json` |
| Repository architecture validator | PASS before and after, no failures. | `architecture-baseline.log`, `architecture-final.log` |
| Existing agent harness | 74 tests pass. | `harness-tests.log` |
| Manual scenario walkthrough | 16 scenarios reviewed against the written instructions. Not independent model evaluation. | `scenario-review.md` |
| Inherited work preservation | 1,758 pre-existing paths checked; zero changed; all 573 inherited status entries preserved; HEAD/branch unchanged. | `baseline.json`, `preservation.json`, `preservation-check.log` |

Added 34 files: sixteen entrypoints, sixteen discovery metadata files, one canonical
document map and this capsule. No existing skill, product file, dependency,
configuration or programme pointer changed. The system Python lacked PyYAML for the
metadata generator; the existing backend environment ran it successfully without
installing anything. Both attempts remain in the evidence logs.

The checks validate packaging, references, harness compatibility and preservation.
They do not prove future agent compliance, ASVS conformance, live execution safety
or release readiness. No independent model evaluation or product runtime was run.
