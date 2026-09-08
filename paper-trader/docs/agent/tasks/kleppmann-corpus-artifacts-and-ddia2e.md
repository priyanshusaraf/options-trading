---
{
  "id": "kleppmann-corpus-artifacts-and-ddia2e",
  "phase": "cross-phase-professional-engineering-reference",
  "status": "accepted",
  "kind": "read_only_side_capsule",
  "goal": "Continue the existing 373-item Kleppmann corpus lineage by triaging recorded one-hop artifacts, inspecting the highest-priority PDFs and diagrams page by page, reviewing the public and lawfully available DDIA second-edition delta, and updating the existing professional-engineering evidence system without product implementation.",
  "goal_contract": {
    "create_before_work": true,
    "durable_goal_created": true,
    "stopping_condition": "Close only after the recorded one-hop paper/course/slide/transcript/artifact queue has a reproducible triage disposition; selected highest-priority PDFs and relevant diagrams have page-level inspection receipts; the official/public DDIA 2e delta and exact licensed artifacts have bounded notes; the existing source registry, claim registry, source notes, coverage ledger, inaccessible-source record and rejected-pattern catalogue are updated; every admitted claim records assumptions, a Strategy OS failure hypothesis, repository evidence, the smallest safe response, verification, migration/rollback and release owner; generated artifacts and protected paths pass direct validation."
  },
  "risk_tags": [
    "documentation",
    "research-validity",
    "source-provenance",
    "licence-evidence",
    "programme-collision-control"
  ],
  "authority": {
    "owner_instruction_date": "2026-08-29",
    "controlling_composite": [
      "paper-trader/docs/research/kleppmann/STRATEGY_OS_KLEPPMANN_AND_PROFESSIONAL_ENGINEERING_REVIEW_PROMPT_V2_2026-08-28.md",
      "paper-trader/docs/program/owner-directions/2026-08-29/05-PROFESSIONAL-ENGINEERING-CORPUS-REVIEW-V4.md",
      "paper-trader/docs/engineering-references/STRATEGY_OS_PROFESSIONAL_ENGINEERING_REFERENCE_PROGRAM_2026-08-28.md",
      "paper-trader/docs/strategy-os-v1-v2-v3/STRATEGY_OS_V0_V6_OWNER_DIRECTION_RECONCILIATION_2026-08-29.md"
    ],
    "unavailable_and_not_read": [
      "STRATEGY_OS_KLEPPMANN_AND_PROFESSIONAL_ENGINEERING_REVIEW_PROMPT_V3_SIMPLICITY_GUARDED_2026-08-28.md",
      "STRATEGY_OS_CODEX_SIMPLICITY_AND_ANTI_OVERENGINEERING_DIRECTIVE_2026-08-28.md"
    ],
    "precedence_resolution": "The owner's explicit instruction accepts the named controlling composite for this run and supersedes the prior recovery prerequisite. The unavailable documents are evidence gaps, not implied inputs."
  },
  "required_docs": [
    {
      "path": "paper-trader/docs/research/kleppmann/STRATEGY_OS_KLEPPMANN_AND_PROFESSIONAL_ENGINEERING_REVIEW_PROMPT_V2_2026-08-28.md",
      "sections": [
        "Corpus scope: crawl the website as a graph, not as a homepage",
        "PDF, slide, graph, image, and video handling",
        "Mandatory DDIA second-edition delta review",
        "Source admission rule",
        "Two-source rule for high-risk changes",
        "Anti-cargo-cult constraints"
      ]
    },
    {
      "path": "paper-trader/docs/program/owner-directions/2026-08-29/05-PROFESSIONAL-ENGINEERING-CORPUS-REVIEW-V4.md",
      "sections": [
        "Highest-precedence simplicity guard",
        "Bounded recursive policy",
        "PDF/visual requirements",
        "DDIA second-edition delta",
        "Source-to-repository method",
        "Parallel-lane restriction",
        "Definition of done"
      ]
    },
    {
      "path": "paper-trader/docs/engineering-references/STRATEGY_OS_PROFESSIONAL_ENGINEERING_REFERENCE_PROGRAM_2026-08-28.md",
      "sections": [
        "Core principle",
        "Source families and their assigned jobs",
        "Review gates",
        "Anti-cargo-cult rule"
      ]
    },
    {
      "path": "paper-trader/docs/strategy-os-v1-v2-v3/STRATEGY_OS_V0_V6_OWNER_DIRECTION_RECONCILIATION_2026-08-29.md",
      "sections": [
        "Precedence",
        "Scale and professional-engineering reconciliation",
        "Running-task and collision decision",
        "Nonclaims"
      ]
    },
    {
      "path": "paper-trader/docs/research/kleppmann/INTAKE-CAPSULE.md",
      "sections": [
        "Outcome and stopping condition",
        "Ownership and boundaries",
        "Required evidence"
      ]
    },
    {
      "path": "paper-trader/docs/research/kleppmann/07-IMPLEMENTATION-AND-MIGRATION-PLAN.md",
      "sections": [
        "Next coherent review slice",
        "Output coverage ledger",
        "Changes deliberately not made"
      ]
    }
  ],
  "allowed_paths": [
    "paper-trader/docs/agent/tasks/kleppmann-corpus-artifacts-and-ddia2e.md",
    "paper-trader/docs/research/kleppmann",
    "paper-trader/docs/engineering-references",
    ".agent/runs/kleppmann-corpus-artifacts-and-ddia2e"
  ],
  "protected_paths": [
    "paper-trader/docs/agent/tasks/post-phase5-indicator-accuracy-registry-lineage-integration.md",
    "paper-trader/docs/agent/CURRENT.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/backend",
    "paper-trader/frontend",
    "paper-trader/scripts/deploy.sh"
  ],
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": [
    "The 373-record first-party manifest lineage and completed HTML frontier are preserved; no duplicate crawl or competing corpus is created.",
    "Every recorded one-hop link has a reproducible triage disposition, and admitted course, paper, slide, transcript and artifact records preserve source edges, access state, checksum or exact commit where available, licence evidence and review depth.",
    "Selected highest-priority PDFs have per-page inspection receipts and direct visual review for relevant diagrams, tables, state machines, transaction histories, timelines and charts.",
    "The DDIA second-edition delta uses only official/public or lawfully available material and separates verified table-of-contents or licensed-artifact evidence from unavailable book text.",
    "Every admitted claim contains assumptions, a Strategy OS failure hypothesis, current repository evidence, the smallest safe response, verification, migration/rollback, release owner and an explicit implement, defer or reject disposition.",
    "The existing source registry, claim registry, source notes, coverage ledger, inaccessible-source record and rejected-pattern catalogue validate without modifying the active programme or any product path."
  ],
  "test_plan": [
    "Run the repository architecture validator after materialization and at closure.",
    "Validate JSON, JSONL, CSV and source-registry schemas; stable source IDs; counts; checksums; exact artifact commits; licence fields; local links; and generated-file provenance.",
    "Recompute corpus and engineering-reference hashes, compare protected paths against the baseline, and audit git status for writes outside the allowed paths.",
    "Check that every new claim has the complete professional-reference chain and that no inaccessible source is marked read or visually inspected.",
    "Record full retrieval, PDF metadata/rendering and validation output under the capsule evidence root. No product, migration, frontend or deployment tests are implied."
  ],
  "model_route": {
    "owner": "root user-selected model",
    "parallelism": "none",
    "service_tier": "priority"
  },
  "owner_gates": [
    "Stop before product code, schema, dependency, frontend, provider, credential, deployment, live execution, order or money mutation; findings require a separate exact capsule and owner before implementation.",
    "Do not bypass access controls, use pirated book material, vendor third-party artifacts, or infer reuse permission when an exact licence is missing.",
    "Do not update CURRENT.md, PROGRAMME.json or the active indicator capsule; programme integration remains with its existing owner."
  ],
  "stop_conditions": [
    "A requested source is inaccessible, gated or lacks a lawful review path but would be required to support a claim; record the gap and narrow or reject the claim.",
    "A proposed finding lacks exact source location, assumptions, repository evidence, a realistic failure hypothesis or a release owner.",
    "A proposed response introduces infrastructure or future-scope behavior without a measured current need and a separately authorized implementation capsule.",
    "Any write overlaps CURRENT.md, PROGRAMME.json, the active indicator capsule, product code or another owner's evidence path."
  ],
  "review": {
    "required": false,
    "assignment_id": "kleppmann_corpus_artifacts_and_ddia2e_owner",
    "agent": "owner",
    "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c",
    "package": ".agent/runs/kleppmann-corpus-artifacts-and-ddia2e/root/review-package.json",
    "review_paths": [
      "paper-trader/docs/agent/tasks/kleppmann-corpus-artifacts-and-ddia2e.md",
      "paper-trader/docs/research/kleppmann",
      "paper-trader/docs/engineering-references",
      ".agent/runs/kleppmann-corpus-artifacts-and-ddia2e"
    ],
    "exclude_paths": [
      "paper-trader/docs/agent/tasks/post-phase5-indicator-accuracy-registry-lineage-integration.md",
      "paper-trader/docs/agent/CURRENT.md",
      "paper-trader/docs/agent/programme/PROGRAMME.json",
      "paper-trader/backend",
      "paper-trader/frontend",
      "paper-trader/scripts/deploy.sh"
    ],
    "verdicts": [
      "REFERENCE_CONTINUATION"
    ],
    "output": ".agent/runs/kleppmann-corpus-artifacts-and-ddia2e/root/report.md"
  },
  "nonclaims": [
    "No completed full-corpus claim follows from inventory, retrieval, extraction or title screening.",
    "No finding implements itself or grants product, schema, dependency, frontend, provider, credential, deployment, live, order or money authority.",
    "No second HTML crawl, second corpus lineage, new infrastructure or production dependency is authorized.",
    "No inaccessible source is claimed read and no licence conclusion is inferred from availability alone."
  ],
  "deployment_impact": {
    "classification": "documentation and ignored research evidence only",
    "migration": "none",
    "rollback": "remove only this capsule's additive research/registry/evidence changes while preserving inherited corpus bytes and all product work",
    "deployment_authority": false
  },
  "evidence_root": ".agent/runs/kleppmann-corpus-artifacts-and-ddia2e/root",
  "completion": {
    "verdict": "REFERENCE_CONTINUATION PASS",
    "report": "paper-trader/docs/research/kleppmann/21-CORPUS-ARTIFACTS-AND-DDIA2E-REVIEW.md",
    "evidence_report": ".agent/runs/kleppmann-corpus-artifacts-and-ddia2e/root/report.md",
    "first_party_records_before": 373,
    "first_party_records_after": 373,
    "html_crawl_rerun": false,
    "one_hop_records_triaged": 2016,
    "pdfs_directly_inspected": 4,
    "pages_directly_inspected": 320,
    "first_party_records_fully_read": 7,
    "new_claims": 9,
    "new_findings": 5,
    "confirmed_product_defects": 0,
    "confirmed_observability_gaps": 1,
    "product_writes": 0,
    "schema_writes": 0,
    "dependency_writes": 0,
    "frontend_writes": 0,
    "deployment": false,
    "full_corpus_mandate_complete": false,
    "protected_paths_changed_by_this_capsule": false,
    "protected_paths_changed_concurrently": [
      "paper-trader/docs/agent/tasks/post-phase5-indicator-accuracy-registry-lineage-integration.md",
      "paper-trader/docs/agent/CURRENT.md",
      "paper-trader/docs/agent/programme/PROGRAMME.json"
    ]
  }
}
---

# Kleppmann corpus artifacts and DDIA 2e continuation

This capsule continues the existing inventory and registries. It does not restart
the completed first-party HTML crawl and does not replace the active indicator
capsule. Source retrieval, reading, applicability, claim admission and product
implementation remain separate states.

Every admitted source claim must include the complete professional-reference
chain: source and exact location; assumptions/system model; Strategy OS failure
hypothesis; current repository evidence; smallest safe response; verification;
migration and rollback; release owner; and an explicit implement, defer or reject
decision.
