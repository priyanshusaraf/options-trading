---
{
  "id": "strategy-os-v1-programme-rebase-2026-08-24",
  "phase": "interphase-5-programme-rebase",
  "status": "accepted",
  "goal": "Rebase the Strategy OS V1 programme from Phase 5 onward against the 24 August hybrid-product owner addendum and the current repository without enabling product, frontend, provider, deployment, live, order, or money behavior.",
  "goal_contract": {
    "create_before_work": true,
    "owner_authorization": "The user's 2026-08-24 controlling assignment pauses the ready Phase 5 implementation handoff until a repository-grounded progress mapper, scope matrix, gap map, ADR plan, benchmark/test plan, and canonical-document reconciliation package exist. The root task is owner-selected Sol xhigh; this programme stage and all implementation children retain the repository's Sol-medium route, with one independent Sol-high final review after the documentation bytes and evidence freeze.",
    "stopping_condition": "Complete only when the hybrid addendum is present byte-for-byte in the documentation root; repository, Phase 1-4, Phase 5, object-model, frontend, provider, chart, resource, research, security, migration, and deployability claims are tied to exact evidence; the required six-document package, 54-row subphase contract matrix, and canonical index exist; deprecated current-status and ten-phase guidance no longer contradict the new authority; PROGRAMME.json and CURRENT.md point to one dependency-valid next implementation capsule; validation and one independent final review pass; and every external legal, commercial, licensing, data, production, frontend, live, order, and money decision remains explicit and unclaimed."
  },
  "risk_tags": ["architecture", "programme", "market-truth", "capital-concurrency", "execution-correctness", "security", "migrations", "deployability"],
  "required_docs": [
    {"path": "paper-trader/docs/strategy-os-v1-v2-v3/STRATEGY_OS_HYBRID_PRODUCT_DIRECTION_AND_V1_PROGRAMME_REBASE_2026-08-24.md", "sections": ["0. Authority, precedence, and interpretation", "16. Programme rebase requirement", "20. Required programme/documentation outputs"]},
    {"path": "paper-trader/docs/agent/tasks/phase1-4-foundation-critical-closure-accepted.md", "sections": ["Accepted Phase 1-4 foundation closure record"]},
    {"path": "paper-trader/docs/superpowers/specs/phase5-strategy-os-design.md", "sections": ["Architecture decision", "Deployment impact and nonclaims", "Audit assimilation and current blockers"]},
    {"path": "paper-trader/docs/agent/DEPLOYABILITY.md", "sections": ["Open obligations", "Phase 5 ownership", "V1 release gate"]}
  ],
  "dependency_gate": "phase5-architecture",
  "allowed_paths": [
    "paper-trader/docs/strategy-os-v1-v2-v3",
    "paper-trader/docs/agent/CURRENT.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/tasks/strategy-os-v1-programme-rebase-2026-08-24.md",
    "paper-trader/docs/agent/tasks/phase5-capital-admission-architecture.md",
    "paper-trader/docs/strategy-os-v1-v2-v3/V0-V1-V1.5-V2-V3-V4-V5-V6-SCOPE-DECISION-MATRIX.md",
    "paper-trader/docs/agent/STATUS.md",
    "paper-trader/docs/superpowers/plans/2026-08-13-strategy-os-v1-master-sequence.md",
    ".agent/runs/programme-rebase-2026-08-24"
  ],
  "nonclaims": [
    "No product implementation, frontend implementation, schema migration, provider connection, credential access, runtime enablement, deployment, production access, live authority, order, or money behavior.",
    "The package may define future migrations and gates but cannot establish local runnability, release deployability, production rehearsal, deployment, commercial permission, data rights, or TradingView access.",
    "Accepted Phase 1-4 bytes remain preserved unless direct repository evidence demonstrates a core-abstraction defect."
  ],
  "owner_gates": [
    "TradingView or other licence-sensitive adoption and commercial terms",
    "purchase or redistribution of reference, event, depth, options, OI, or fundamentals data",
    "frontend implementation",
    "production credentials, topology, deployment, or destructive migration work",
    "authoritative live IR, material sizing/routing/risk/execution changes, orders, or money",
    "legal, regulatory, launch-cohort, pricing, or paid-release decisions"
  ],
  "stop_conditions": [
    "A proposed rebase creates a second IR, validator, resolver, hash, deployment authority, research ledger, provider identity, or financial authority.",
    "A Phase 1-4 closure claim cannot be tied to current repository bytes and accepted direct evidence.",
    "A required external legal, commercial, licensing, or data-rights choice is silently converted into implementation scope."
  ],
  "deployment_impact": {
    "classification": "architecture-changing",
    "required_evidence": "Every future runtime, schema, migration, configuration, service, provider, infrastructure, backup/restore, capacity, security, observability, rollout, and rollback obligation must be assigned to an exact revised capsule and release gate. This documentation slice itself establishes no deployability level."
  },
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "service_tier": "default", "root_owner_override": "user-selected gpt-5.6-sol xhigh"},
  "parallel_budget": 4,
  "assignments": [
    {
      "id": "phase_foundation_audit",
      "user_problem": "Determine whether Phases 1-4 remain closed and identify only repository-proven follow-ups required by the expanded product direction.",
      "scope": "Read-only commit, migration, capsule, test, report, and evidence audit for Phases 1-4.",
      "required_files": ["paper-trader/docs/agent/programme/PROGRAMME.json", "paper-trader/docs/agent/tasks", "paper-trader/docs/reports", "paper-trader/backend/migrations", "paper-trader/backend/research/domain/migrations", ".agent/runs/phase1-4-foundation-direct-closure"],
      "invariants": ["Preserve accepted foundation bytes", "Reject closure without current-byte evidence", "Distinguish local proof from deployment truth"],
      "output_artifact": ".agent/runs/programme-rebase-2026-08-24/phase_foundation_audit/report.md",
      "stop_condition": "A four-row Phase 1-4 closure table names exact code, migrations, tests, evidence, classification, and bounded follow-up.",
      "do_not_change": "All repository product, test, migration, programme, capsule, and canonical documentation files."
    },
    {
      "id": "object_runtime_gap_audit",
      "user_problem": "Map existing Strategy OS domain objects and runtime/resource/provider seams so the revised programme extends instead of duplicates them.",
      "scope": "Read-only backend and research audit covering Strategy/revision, IR, roles, InstrumentScope/watchlists, deployments, execution policy, admission, positions/tranches, providers, datasets, evidence, resources, state, approvals, events, fundamentals, and chart persistence.",
      "required_files": ["paper-trader/backend/app", "paper-trader/backend/research", "paper-trader/backend/tests", "paper-trader/backend/research_tests", "paper-trader/docs/strategy-os-v1-v2-v3"],
      "invariants": ["One accepted IR and authority chain", "Canonical instruments", "Data provider and execution broker separation", "Exact owner and revision attribution"],
      "output_artifact": ".agent/runs/programme-rebase-2026-08-24/object_runtime_gap_audit/report.md",
      "stop_condition": "Every required object and runtime area has an implementation-state label, exact file reference, extension disposition, failure risk, and proposed revised owner capsule.",
      "do_not_change": "All repository product, test, migration, programme, capsule, and canonical documentation files."
    },
    {
      "id": "frontend_chart_local_audit",
      "user_problem": "Establish the current frontend/chart/workspace/approval/watchlist surface and the smallest truthful API/design boundary for the expanded hybrid product.",
      "scope": "Read-only frontend, design-plan, API-route, and existing UX packet audit; no browser runtime and no frontend edits.",
      "required_files": ["paper-trader/frontend", "paper-trader/docs/strategy-os-v1-v2-v3/ux", "paper-trader/docs/superpowers", "paper-trader/backend/app/api", "paper-trader/backend/app/core"],
      "invariants": ["Frontend does not own readiness truth", "One REST client and WebSocket", "Vendor chart state never becomes executable identity", "Frontend implementation remains owner-gated"],
      "output_artifact": ".agent/runs/programme-rebase-2026-08-24/frontend_chart_local_audit/report.md",
      "stop_condition": "The current UI/code state, missing surfaces, reusable contracts, contract-first frontend sequence, and owner-gated implementation boundary are explicit.",
      "do_not_change": "All frontend, backend, programme, capsule, and canonical documentation files."
    },
    {
      "id": "official_prior_art_audit",
      "user_problem": "Verify current TradingView product/access/API/licensing constraints and only the official provider/reference facts needed for programme decisions.",
      "scope": "Read-only official-source review of TradingView Advanced Charts, Trading Platform, Lightweight Charts, drawings, save/load, datafeed, framework/security integration, access and terms; add narrowly relevant official provider capability evidence only where repository claims require it.",
      "required_files": ["paper-trader/docs/strategy-os-v1-v2-v3/SOURCE-REGISTER.md", "paper-trader/docs/strategy-os-v1-v2-v3/comparison-packets", "paper-trader/backend/app/providers"],
      "invariants": ["No licence-sensitive adoption", "No tradingview.com parity claim", "No vendor blob in IR", "No disclaimer in place of price-coherence controls"],
      "output_artifact": ".agent/runs/programme-rebase-2026-08-24/official_prior_art_audit/report.md",
      "stop_condition": "A dated capability and access matrix records official URLs, inspected APIs, licensing/access uncertainty, selected/rejected V1 uses, and required tests without making a commercial decision.",
      "do_not_change": "All repository product, test, programme, capsule, and canonical documentation files."
    }
  ],
  "acceptance": [
    "The six required programme/reconciliation documents and canonical index exist and answer the controlling assignment without relying on prose-only implementation claims.",
    "All 54 subphases have exact machine linkage or deterministic capsule-generation ownership plus dependency/reuse, contract/schema/API and frontend/backend delta, migration/security/provider/resource impact, realistic failure tests, benchmark, rollout/rollback, exit artifact, route and disjoint-write rules.",
    "Phase 1-4 closure classifications and Phase 5 sequencing cite exact repository evidence.",
    "Every revised phase/subphase has dependencies, reusable code, contract/schema/API work, frontend/backend work, migrations, tenancy/security, provider/data/resource impact, failure modes, risk-class tests, benchmark coverage, rollout, rollback, exit artifacts, model effort, and parallel lanes.",
    "V1.1 is explicitly retired or redefined, Dynamic Watchlists are in V1, broad certified options execution remains V1.5, and all other requested capabilities have exactly one target classification.",
    "Deprecated current-status and old ten-phase guidance point to the revised canonical authority instead of contradicting it.",
    "No protected product/provider/execution or accepted Phase 1-4 implementation byte changes."
  ],
  "test_plan": [
    "JSON and programme orchestration validation",
    "documentation link and required-section validation",
    "canonical contradiction searches for V1.1 Dynamic Watchlists, ten-phase sanctity, 1 September target, chart semantics deferred to V2, and stale Phase 1-4 status",
    "source SHA-256 and protected-hash comparison",
    "independent SPEC and QUALITY review of the frozen documentation package"
  ],
  "review": {
    "required": true,
    "assignment_id": "programme_rebase_reviewer",
    "agent": "critical-reviewer",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "base_sha": "HEAD",
    "package": ".agent/runs/programme-rebase-2026-08-24/root/review-package.md",
    "review_paths": [
      "paper-trader/docs/strategy-os-v1-v2-v3",
      "paper-trader/docs/agent/CURRENT.md",
      "paper-trader/docs/agent/programme/PROGRAMME.json",
      "paper-trader/docs/agent/tasks/strategy-os-v1-programme-rebase-2026-08-24.md",
      "paper-trader/docs/strategy-os-v1-v2-v3/V0-V1-V1.5-V2-V3-V4-V5-V6-SCOPE-DECISION-MATRIX.md",
      "paper-trader/docs/agent/STATUS.md",
      "paper-trader/docs/superpowers/plans/2026-08-13-strategy-os-v1-master-sequence.md"
    ],
    "exclude_paths": [],
    "output": ".agent/runs/programme-rebase-2026-08-24/review/verdict.md",
    "verdicts": ["SPEC", "QUALITY"],
    "max_rechecks": 1
  },
  "review_result": {
    "first_verdict": ".agent/runs/programme-rebase-2026-08-24/review/verdict.md",
    "first_verdict_sha256": "906fa1977c83c2a7e4f09b049aa1b9dc78a73930907eaf804510a10c960624de",
    "recheck_verdict": ".agent/runs/programme-rebase-2026-08-24/review/recheck-verdict.md",
    "recheck_verdict_sha256": "2e1fd1983ec97b777a556c5b2a3d738c4751246d943c43d4233c90ca13373803",
    "spec": "PASS",
    "quality": "PASS",
    "final": "PASS"
  }
}
---

# Strategy OS V1 programme rebase

This owner-directed documentation capsule is accepted. It preserves the accepted `phase5-graph-paper-attribution-schema` capsule unchanged and makes that schema task the dependency-valid next stage. It authorizes no other product implementation.

The root integrates the four declared read-only audits. Shared canonical documents, `CURRENT.md`, `PROGRAMME.json`, and the final package remain root-owned. Agents must write only their declared evidence artifact and must not amend product or canonical documentation.
