---
{
  "id": "strategy-os-product-quality-skills",
  "phase": "tooling",
  "status": "accepted",
  "kind": "owner_requested_skill_authoring",
  "goal": "Add six requested SEO, accessibility, feedback, documentation, analytics privacy and provider-change skills after reviewing use cases and related guidance.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "All six skills and discovery metadata validate, local references resolve, representative scenarios are reviewed, no new architecture/harness failure is attributable to these additions, and no inherited file is edited by this slice; concurrent external changes and baseline failures are reported separately."},
  "risk_tags": ["important", "agent-tooling", "documentation"],
  "required_docs": [
    {"path": "paper-trader/docs/strategy-os-v1-v2-v3/ux/TASK-BENCHMARK.md", "sections": ["Test population", "Measures", "Accessibility variants", "Benchmark environments", "Evidence package", "Acceptance gates"]},
    {"path": "paper-trader/docs/strategy-os-v1-v2-v3/ux/INTERACTION-AUDIT.md", "sections": ["Accessibility", "Performance"]},
    {"path": "paper-trader/docs/program/owner-steers/04-RUNTIME-ECONOMICS-PROVIDER-CAPABILITIES.md", "sections": ["12. Provider fallback"]}
  ],
  "allowed_paths": [
    ".agents/skills/seo-and-metadata-audit",
    ".agents/skills/accessibility-audit",
    ".agents/skills/customer-feedback-synthesis",
    ".agents/skills/documentation-quality-review",
    ".agents/skills/analytics-privacy-review",
    ".agents/skills/provider-change-impact-review",
    "paper-trader/docs/agent/tasks/strategy-os-product-quality-skills.md",
    ".agent/runs/strategyos-product-quality-skills"
  ],
  "protected_paths": ["AGENTS.md", ".codex", "paper-trader/backend", "paper-trader/frontend", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/programme", "paper-trader/docs/agent/DEPLOYABILITY.md"],
  "nonclaims": ["No frontend/product implementation, public SEO changes, analytics installation, provider switch or roadmap expansion.", "No live/provider/customer access, external data disclosure, deployment or certification.", "Instruction checks are not product, WCAG, privacy or release acceptance evidence."],
  "owner_gates": ["The owner requested these six skills as a continuation of prior skill authoring.", "Existing frontend, provider, commercial, privacy and deployment gates remain in force."],
  "stop_conditions": ["Completing the addition requires edits to inherited product, skills, configuration or programme state.", "A source conflict would require inventing release scope, user evidence or provider semantics."],
  "deployment_impact": {"classification": "none", "reason": "Repository instructions and discovery metadata only; no running service, schema, dependency, frontend or infrastructure change."},
  "model_route": {"owner": "user-selected", "delegation": "none"},
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": ["All six requested names are discoverable and contain concrete triggers, evidence output and scope boundaries.", "Public indexability and private-app protection remain separate; WCAG criteria remain distinct from design heuristics.", "Feedback does not create implementation authority; documentation and analytics claims require actual behavior evidence.", "Provider impact classification preserves canonical identity, data/execution separation and owner revalidation gates."],
  "test_plan": ["Bundled skill validator, discovery metadata checks and local link resolution.", "Repository architecture baseline/final comparison and existing .codex harness tests; report unrelated failures without editing them.", "Manual scenario walkthroughs, explicitly not independent model evaluations.", "Pre-existing file hashes/status and owned-file manifest; record concurrent external work separately."],
  "review": {"required": false, "assignment_id": "product_quality_skills_self_review", "base_sha": "HEAD", "review_paths": [".agents/skills", "paper-trader/docs/agent/tasks/strategy-os-product-quality-skills.md"], "exclude_paths": ["paper-trader/backend", "paper-trader/frontend"], "reason": "Important instruction-only authoring with local review; no critical product change."}
}
---

# Strategy OS product-quality skill authoring

This tooling capsule does not replace the product capsule selected by CURRENT.md
(V0-A at task start). Use zero child agents and make no edits to the programme or
existing skills. Concurrent product work remains owned by its separate task.

## Use cases and related guidance

| Skill | Representative use case | Related responsibility retained |
| --- | --- | --- |
| seo-and-metadata-audit | A private route appears in a sitemap, metadata leaks a strategy name, or robots blocking prevents noindex discovery. | Tenant/privacy controls protect access; release review owns actual public launch claims. |
| accessibility-audit | A graph requires dragging, virtualized research rows lose focus, or a chart communicates only through colour. | Safe runtime owns browser observation; ui-ux-pro-max offers design guidance, not WCAG certification. |
| customer-feedback-synthesis | Repeated tickets from one user are counted as broad demand; a requested feature masks an onboarding failure. | Scope classifier and canonical precedence own release boundaries; privacy controls govern user evidence. |
| documentation-quality-review | An onboarding guide names a stale route or promises a capability absent from the current profile. | Actual product/build evidence outranks stale prose; safe runtime and owner gates constrain commands. |
| analytics-privacy-review | Auto-capture sends graph text, a broker/account ID, a reset URL or payment data to a vendor. | Privacy-data-flow review owns lifecycle/processors; observability owns instrumentation, not disclosure permission. |
| provider-change-impact-review | A same-shaped API changes bar timestamps, contract mapping, quotas or order semantics. | Provider conformance owns direct tests; invariants, research and execution reviews own their affected boundaries. |

Inspected existing frontend metadata/package scripts and the related skill guidance.
The frontend is a private React/Vite package, but that package flag does not prove
HTTP access control or indexability. Searches for analytics also found internal
financial/research surfaces; these are not evidence of a third-party tracking SDK.
No UI was changed or started during authoring.

The older UX packets provide useful task/measurement ideas, but their proposed
targets and historical scope are not current release authority. Use the active
capsule and accepted source precedence. Generic 44px touch-target guidance must not
be presented as the WCAG AA rule; inspect the applicable criterion and exceptions.

## Primary references

- Google Search Central: [robots/noindex](https://developers.google.com/search/docs/crawling-indexing/robots-meta-tag),
  [canonical URLs](https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls),
  [sitemaps](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap)
  and [structured data](https://developers.google.com/search/docs/appearance/structured-data/intro-structured-data).
- W3C: [WCAG 2.2](https://www.w3.org/TR/WCAG22/),
  [grid interaction pattern](https://www.w3.org/WAI/ARIA/apg/patterns/grid/)
  and [complex images/charts](https://www.w3.org/WAI/tutorials/images/complex/).
- [Web Vitals](https://web.dev/articles/vitals) for performance measurement and the
  distinction between field and laboratory evidence.

## Baseline and evidence

Evidence root: `.agent/runs/strategyos-product-quality-skills/root/`.
The initial repository validator reported missing fields in the unrelated
`strategy-os-v0-frontend-convergence.md` capsule. CURRENT.md and PROGRAMME.json changed
concurrently, selecting that product capsule. The other task subsequently completed
the missing fields. None of those changes was made here; the existing validator/test
sources and skills retained their pre-edit hashes. Preserve the earlier failed runs
as historical evidence rather than overwriting them.

| Check | Observed result | Evidence |
| --- | --- | --- |
| Skill validator and discovery metadata | All six pass; implicit invocation remains enabled by default. | `skill-validation.log`, `skill-validation.json`, `discovery-metadata.log` |
| Local references | All 19 resolve. | `skill-validation.json` |
| Repository architecture validator | Initial and first final runs had four external capsule errors; the recheck passes after external correction. No error was introduced by the six skills. | `architecture-baseline.log`, `architecture-final.log`, `architecture-comparison.json`, `architecture-recheck.log` |
| Existing agent harness | Latest run: 74 tests, 73 pass, one external resume-interface failure. Earlier run: 72 pass, two external failures. | `harness-tests.log`, `failure-attribution.json`, `harness-recheck.log` |
| Manual scenario review | Six scenarios reviewed against the instructions; not independent model evaluation. | `scenario-review.md` |
| Preservation | 1,811 pre-existing paths checked. CURRENT.md, PROGRAMME.json and the frontend-convergence capsule changed externally. All previous skills, harness and product source files remain unchanged at the final check. | `baseline.json`, `pre-authoring-baseline.json`, `preservation.json`, `preservation-final.json` |

Added 13 files: six entrypoints, six metadata files and this capsule. No existing
skill, product source, dependency, configuration or programme pointer was edited by
this slice. The remaining test unconditionally expects the active product capsule's
`risk_tags` to include `critical`; the concurrently selected architecture capsule
does not include that tag. This slice neither relabels its risk nor weakens that
test. Report the repository validator as passing at recheck and the full harness
as having one unrelated failure, not as fully passing.

The package is accepted for the requested instruction-only scope with those external
failures disclosed. This does not establish product behavior, indexing, WCAG/privacy
conformance, provider compatibility or release readiness. No product/browser runtime,
real user research, external analytics or provider account was exercised.
