---
{
  "id": "strategy-os-future-object-boundary-proposal",
  "phase": "v0-v6",
  "status": "accepted",
  "kind": "bounded_documentation_only_architecture_proposal",
  "goal": "Define additive future representational boundaries for EconomicPosition, ProposedPortfolioRevision, Strategy Asset versus Managed Model, and EconomicExposure without changing current objects, history, authority, runtime behavior or release scope.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "The capsule, report, object-boundary matrix and owner decision questions define exact later homes, ownership and authority limits, freeze ADR 0018 PositionCampaign as single-instrument, reject historical inference and real-time-admission bypass, record migration and capability nonclaims, and prove all protected bytes unchanged."
  },
  "risk_tags": [
    "architecture",
    "object-identity",
    "authority-separation",
    "position-lineage",
    "portfolio-admission",
    "historical-integrity",
    "future-scope"
  ],
  "required_docs": [
    {
      "path": "paper-trader/docs/agent/CURRENT.md",
      "sections": [
        "active_stage",
        "active_capsule",
        "next_gate",
        "nonclaims"
      ]
    },
    {
      "path": "paper-trader/docs/agent/tasks/strategy-os-v0-verified-language-catalogue.md",
      "sections": [
        "goal_contract",
        "allowed_paths",
        "protected_paths",
        "owner_gates",
        "nonclaims"
      ]
    },
    {
      "path": "paper-trader/docs/engineering/decisions/0001-product-object-contract.md",
      "sections": [
        "Accepted model",
        "Object identities and ownership",
        "Transactions, migration and rollback",
        "API and workstream ownership"
      ]
    },
    {
      "path": "paper-trader/docs/engineering/decisions/0012-execution-state-ownership.md",
      "sections": [
        "Ownership — who owns which fact",
        "The authority gate"
      ]
    },
    {
      "path": "paper-trader/docs/engineering/decisions/0016-execution-product-policy.md",
      "sections": [
        "Decision",
        "Authority and dependency direction",
        "Implementation and review gate"
      ]
    },
    {
      "path": "paper-trader/docs/engineering/decisions/0017-sizing-target-position-and-reservation.md",
      "sections": [
        "Decision",
        "Closed batch admission",
        "Rollout boundary"
      ]
    },
    {
      "path": "paper-trader/docs/engineering/decisions/0018-position-campaign-tranche-lineage.md",
      "sections": [
        "Decision",
        "Invariants",
        "Legacy rows and migration",
        "Required evidence"
      ]
    },
    {
      "path": "paper-trader/docs/strategy-os-v1-v2-v3/CANONICAL-DOCUMENT-RECONCILIATION.md",
      "sections": [
        "Authority and precedence",
        "Contradictions introduced by the latest owner direction",
        "Final canonical reading order for product/programme work",
        "Nonclaims"
      ]
    },
    {
      "path": "paper-trader/docs/strategy-os-v1-v2-v3/STRATEGY_OS_V0_V6_OWNER_DIRECTION_RECONCILIATION_2026-08-29.md",
      "sections": [
        "Precedence",
        "Future architecture reconciliation",
        "Running-task and collision decision",
        "External and owner decision queue",
        "Nonclaims"
      ]
    },
    {
      "path": "paper-trader/docs/strategy-os-v1-v2-v3/V0-V1-V1.5-V2-V3-V4-V5-V6-SCOPE-DECISION-MATRIX.md",
      "sections": [
        "Matrix",
        "Maturity gates",
        "Release-claim rule"
      ]
    },
    {
      "path": "paper-trader/docs/program/owner-directions/2026-08-29/03-ARCHITECTURE-EVOLUTION-AND-NO-DEAD-END-INVARIANTS.md",
      "sections": [
        "Strategy, economic intent, and execution structure",
        "Position Campaign / Economic Position",
        "Portfolio as an active control plane",
        "Strategic allocation versus real-time admission",
        "Marketplace object boundary",
        "Ownership and authority matrix",
        "Enterprise exposure and treasury seam",
        "Required bounded ADRs"
      ]
    },
    {
      "path": "paper-trader/docs/program/owner-directions/2026-08-29/08-MATURITY-GATED-PRODUCT-SEQUENCE.md",
      "sections": [
        "V2 — Active Portfolio and Hedge Intelligence",
        "V3 — Strategy Ecosystem and Managed Allocation",
        "V4 — Multi-Leg and Institutional Capital Infrastructure",
        "V5/V6 — Corporate Treasury and Enterprise Market-Risk OS"
      ]
    },
    {
      "path": ".agent/runs/strategy-os-v0-v6-handoff-reconciliation/agents/future-seams/report.md",
      "sections": [
        "Outcome",
        "Release concept classification",
        "Architecture invariant matrix",
        "Narrowest safe next slice",
        "Nonclaims"
      ]
    },
    {
      "path": "paper-trader/docs/engineering-references/00-README.md",
      "sections": [
        "How to apply the instructions",
        "Authority and release labels",
        "Refresh and evidence"
      ]
    }
  ],
  "dependency_gate": "Accepted 29 August V0-V6 owner-direction reconciliation and frozen ADR 0018. No active programme-stage dependency or replacement is created.",
  "allowed_paths": [
    "paper-trader/docs/agent/tasks/strategy-os-future-object-boundary-proposal.md",
    ".agent/runs/strategy-os-future-object-boundary-proposal"
  ],
  "new_paths": [
    "paper-trader/docs/agent/tasks/strategy-os-future-object-boundary-proposal.md",
    ".agent/runs/strategy-os-future-object-boundary-proposal/report.md",
    ".agent/runs/strategy-os-future-object-boundary-proposal/object-boundary-matrix.md",
    ".agent/runs/strategy-os-future-object-boundary-proposal/owner-decision-questions.md"
  ],
  "protected_paths": [
    "paper-trader/docs/engineering/decisions",
    "paper-trader/backend",
    "paper-trader/frontend",
    "/Users/priyanshusaraf/dev/strategy-os-frontend",
    "paper-trader/docs/strategy-os-v1-v2-v3",
    "paper-trader/docs/program/owner-directions",
    "paper-trader/docs/agent/CURRENT.md",
    "paper-trader/docs/agent/ROUTER.md",
    "paper-trader/docs/agent/programme",
    ".agent/runs/strategy-os-v0-launch-convergence/capsule-queue.json",
    ".agent/runs/strategy-os-v0-local-release-operations-materialization/queue-confirmation.json",
    ".agent/runs/strategy-os-v0-monitoring-persistence-materialization/queue-path-overlap-receipt.json",
    ".agent/runs/strategy-os-v0-parallel-workstream-replan/queue.json",
    ".agent/runs/strategy-os-v1-parallelization-audit/blocked-queue.json",
    ".agent/runs/strategy-os-v1-parallelization-audit/safe-now-capsule-queue.json",
    "paper-trader/scripts/deploy.sh",
    "AGENTS.md",
    "paper-trader/AGENTS.md",
    ".agents",
    ".codex"
  ],
  "read_only_scope": [
    "Inspect current accepted architecture, product-object ownership, execution foundation and reconciled future release directions only to define representational boundaries.",
    "Do not inspect or contact live providers, brokers, payment systems, credentials, VPS hosts or production infrastructure."
  ],
  "proposal_contract": {
    "position_campaign": "ADR 0018 remains the only meaning: one owner/account/book/deployment/strategy-attributed, single-instrument, single-product, single-direction execution lineage aggregate. It is not a multi-leg economic parent.",
    "economic_position": "Reserve an additive V4 economic parent over one or more exact child PositionCampaign lineages. It owns economic grouping and aggregate lifecycle evidence, not held inventory, fill allocation, order lifecycle, capital admission or broker authority.",
    "proposed_portfolio_revision": "Reserve an immutable V2 recommendation fact. It is never a PortfolioAdmissionDecision, deployment, reservation, order, current-position or money authority, and approval never bypasses transaction-time admission.",
    "strategy_asset_managed_model": "Keep two V3 product roots. A Strategy Asset conveys a versioned package and bounded rights for buyer-operated import; a Managed Model conveys exposure under separate operator, mandate, custody, capacity and legal authority. A shared AllocatableProduct may be a read-only profile, not a generic authority root.",
    "economic_exposure": "Reserve a V5/V6 enterprise operating-exposure fact outside canonical traded-instrument identity. It owns source-revision and forecast context, not market identity, strategy logic, positions, hedge approval or execution authority."
  },
  "later_homes": [
    {
      "release": "post-V0-freeze cross-release architecture",
      "capsule_id": "strategy-os-future-object-boundary-adr-materialization",
      "scope": "Materialize one next-sequential non-implementation ADR only after explicit owner acceptance and an exact V0_FREEZE_SHA."
    },
    {
      "release": "V1",
      "capsule_id": "strategy-os-v1-economic-intent-correlation-contract",
      "scope": "Define strategy-result to zero-or-many economic-intent correlation only when a current V1 producer and consumer exist."
    },
    {
      "release": "V2",
      "capsule_id": "strategy-os-v2-proposed-portfolio-revision-contract",
      "scope": "Own portfolio snapshots, risk snapshots, mandates, proposals, approval and revalidation without replacing real-time admission."
    },
    {
      "release": "V3",
      "capsule_id": "strategy-os-v3-strategy-asset-contract",
      "scope": "Own importable package identity, rights, provenance and buyer-operated preflight."
    },
    {
      "release": "V3",
      "capsule_id": "strategy-os-v3-managed-model-contract",
      "scope": "Own operator, mandate, disclosure, capacity, custody and regulated allocation boundaries."
    },
    {
      "release": "V4",
      "capsule_id": "strategy-os-v4-economic-position-contract",
      "scope": "Own the additive multi-leg parent and exact child-campaign correlation before any schema or execution behavior."
    },
    {
      "release": "V5/V6",
      "capsule_id": "strategy-os-v5-v6-economic-exposure-contract",
      "scope": "Own enterprise exposure provenance, mandate separation and hedge-proposal boundaries before any treasury integration."
    }
  ],
  "acceptance": [
    "ADR 0018 PositionCampaign remains single-instrument and every historical row retains its original meaning and bytes.",
    "Each proposed object has one later release home, an explicit owning domain, a canonical identity boundary, owned facts, forbidden authority and predecessor/successor relation.",
    "ProposedPortfolioRevision approval cannot create a reservation, order or admission verdict and all execution-producing paths retain transaction-time PortfolioAdmissionDecision and reservation gates.",
    "Strategy Asset and Managed Model remain separate product roots despite any shared read-only allocation profile.",
    "EconomicExposure remains outside canonical traded-instrument identity and cannot create a strategy, position or hedge order.",
    "No historical link, backfill, relabel, migration, schema, service, solver, marketplace, portfolio, treasury, frontend, programme, queue or ADR byte is created or changed.",
    "The report states KEEP + HARDEN for the current foundation and DEFER for all feature implementation, with unresolved owner decisions and no completion or readiness claim.",
    "Scoped validation passes and protected manifests match byte for byte."
  ],
  "test_plan": [
    "Parse this capsule's JSON frontmatter and run the repository architecture validator, separating inherited failures from any new failure.",
    "Check the three proposal artifacts for every named object, release home, ownership/authority distinction, no-historical-inference rule, migration nonclaims, V0_FREEZE_SHA gate and real-time-admission guard.",
    "Run git diff --check and a path-scope audit that permits only this capsule and its ignored evidence directory.",
    "Recreate the exact protected manifest and compare it byte for byte with the orientation baseline."
  ],
  "parallel_budget": 0,
  "assignments": [],
  "model_route": {
    "owner": "root user-selected model",
    "child_model": "gpt-5.6-sol",
    "child_reasoning_effort": "medium",
    "fork_turns": "none",
    "service_tier": "priority"
  },
  "owner_gates": [
    "Do not materialize or merge an ADR until the owner explicitly accepts the proposal and supplies the exact V0_FREEZE_SHA.",
    "Do not add any future noun, table, migration, service, solver, marketplace, portfolio, treasury or frontend surface until its named maturity-gated capsule is authorized.",
    "Managed Model, outside-capital, custody, marketplace rights, treasury accounting, OTC, counterparty and jurisdiction decisions remain legal/commercial/owner gates.",
    "No live IR, sizing, routing, risk, execution, VPS, credential, order, money or deployment authority follows."
  ],
  "stop_conditions": [
    "Any proposal reinterprets PositionCampaign or infers campaign, economic-position, portfolio, marketplace or exposure history.",
    "A current schema, service, solver, marketplace, portfolio, treasury, programme, queue, frontend or ADR edit is required.",
    "A future recommendation, asset purchase, managed allocation, EconomicPosition or EconomicExposure can bypass execution binding, real-time admission, reservation or order authority.",
    "The V0_FREEZE_SHA is absent or owner acceptance is not explicit when mergeable ADR work is proposed.",
    "Any protected byte differs from the orientation baseline because of this task."
  ],
  "deployment_impact": {
    "classification": "none; documentation-only ignored evidence plus one task capsule",
    "highest_evidenced_level": "architecture proposal only",
    "future_obligation": "Each named implementation capsule must separately declare schema, migration, service, provider, security, capacity, recovery, rollback and deployment impact."
  },
  "review": {
    "required": false,
    "assignment_id": "strategy_os_future_object_boundary_proposal_owner",
    "agent": "owner",
    "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c",
    "package": ".agent/runs/strategy-os-future-object-boundary-proposal/report.md",
    "output": ".agent/runs/strategy-os-future-object-boundary-proposal/report.md",
    "review_paths": [
      "paper-trader/docs/agent/tasks/strategy-os-future-object-boundary-proposal.md",
      ".agent/runs/strategy-os-future-object-boundary-proposal"
    ],
    "exclude_paths": [
      "paper-trader/docs/engineering/decisions",
      "paper-trader/backend",
      "paper-trader/frontend",
      "paper-trader/docs/agent/CURRENT.md",
      "paper-trader/docs/agent/programme",
      "paper-trader/scripts/deploy.sh"
    ],
    "verdicts": [
      "ARCHITECTURE_PROPOSAL"
    ],
    "max_rechecks": 0
  },
  "completion": {
    "verdict": "ARCHITECTURE_PROPOSAL PASS",
    "disposition": "KEEP + HARDEN current foundations; DEFER future feature implementation",
    "report": ".agent/runs/strategy-os-future-object-boundary-proposal/report.md",
    "report_sha256": "c9e0912bad7ebc960eb551de3645c248d6133261710250fb7bc70ed95c34d7f8",
    "object_boundary_matrix": ".agent/runs/strategy-os-future-object-boundary-proposal/object-boundary-matrix.md",
    "object_boundary_matrix_sha256": "068f282906cdc39a0be487470b82c17ce1bf8592b30e20064f6ed10a695990d3",
    "owner_decision_questions": ".agent/runs/strategy-os-future-object-boundary-proposal/owner-decision-questions.md",
    "owner_decision_questions_sha256": "cfc1a15f764d19380238c1f909b064d87dbab5713a36814afdc06a25cd41242c",
    "protected_files": 26546,
    "protected_manifest_sha256": "9eb01a46eca7c78daf3e9bfe161e46e7b5fdb6f5b2739fc640e54250f155f8b5",
    "protected_match": true,
    "focused_capsule_validation": "PASS",
    "content_assertions": "PASS",
    "scoped_diff_check": "PASS",
    "repository_architecture_validator": "13 inherited failures; zero proposal failures",
    "v0_freeze_sha_supplied": false,
    "adr_materialization_authorized": false,
    "product_writes": 0,
    "deployment": false
  },
  "nonclaims": [
    "No ADR is created, amended, accepted or made mergeable. No V0_FREEZE_SHA exists in this task's authority.",
    "No product, schema, migration, service, dependency, solver, marketplace, portfolio, treasury, provider, queue, programme, CURRENT, frontend, deployment, live, order or money byte changes.",
    "No V1, V1.5, V2, V3, V4, V5/V6 feature, release, provider, capacity, legal, regulatory, accounting, commercial or production-readiness claim is made.",
    "The proposal reserves vocabulary and authority boundaries only. It does not require current framework code or persistence."
  ]
}
---

# Future object-boundary proposal

This capsule records a documentation-only architecture proposal. It keeps ADR 0018
`PositionCampaign` single-instrument, preserves history, assigns exact later homes to the
future objects, and blocks every path that could turn a future proposal or aggregate into
execution authority.

The only deliverables are:

- `.agent/runs/strategy-os-future-object-boundary-proposal/report.md`
- `.agent/runs/strategy-os-future-object-boundary-proposal/object-boundary-matrix.md`
- `.agent/runs/strategy-os-future-object-boundary-proposal/owner-decision-questions.md`

Required command receipts remain in the same ignored run directory. They do not form a
product, ADR, programme or queue change.
