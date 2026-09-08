---
{
  "id": "strategy-os-v0-paper-charge-authority-and-legacy-identity-replan",
  "phase": "v0",
  "status": "accepted",
  "kind": "critical_read_only_money_authority_replan",
  "goal": "Replan the rejected NMT-004 Paper charge reconstruction and historical result identity seams so a selected schedule is durable across restart, risk-reducing Paper exits cannot be blocked by rounded schedule collisions, and one historical cache identity cannot accept two answers.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "The two open Critical findings are reproduced from immutable reviewer fixtures; existing Position/Trade, migration, result/cache and receipt authorities are mapped; one smallest safe implementation capsule is sealed with exact schema/no-schema decision, expand-contract migration and rollback obligations if needed, collision/exit/legacy uniqueness tests, path ownership and a fresh independent Critical review route. No product, test, schema, migration, programme or frontend write occurs."
  },
  "risk_tags": ["critical", "money", "paper-trading", "exit-availability", "restart", "schema", "migration", "historical-identity", "cache-identity"],
  "required_docs": [
    {"path": ".agent/runs/strategy-os-v0-charge-schedule-and-segment-fallback-correction/review/recheck-verdict.json", "sections": ["all output"]},
    {"path": "paper-trader/docs/agent/tasks/strategy-os-v0-charge-schedule-and-segment-fallback-correction.md", "sections": ["V0 charge schedule and segment fallback correction"]},
    {"path": "paper-trader/docs/engineering/decisions/0012-execution-state-ownership.md", "sections": ["2.1 Ownership — who owns which fact", "3. The smallest safe paper/shadow deployment architecture"]},
    {"path": "paper-trader/docs/engineering/decisions/0017-sizing-target-position-and-reservation.md", "sections": ["Decision", "Deterministic policy", "Rollout boundary"]},
    {"path": "paper-trader/docs/agent/DEPLOYABILITY.md", "sections": ["Current verdict", "Open obligations", "V1 release gate"]}
  ],
  "dependency_gate": "The original NMT-004 correction has an immutable second Critical rejection, SHA-256 443b4eb6d7012165b8d1af9a1dfda0fd2e3035a1c361907e8c49dff53bb02094; its one recheck is consumed and all product/test paths are frozen for this read-only replan.",
  "allowed_paths": [
    "paper-trader/docs/agent/tasks/strategy-os-v0-paper-charge-authority-and-legacy-identity-replan.md",
    ".agent/runs/strategy-os-v0-paper-charge-authority-and-legacy-identity-replan"
  ],
  "new_paths": [
    "paper-trader/docs/agent/tasks/strategy-os-v0-paper-charge-authority-and-legacy-identity-replan.md",
    ".agent/runs/strategy-os-v0-paper-charge-authority-and-legacy-identity-replan"
  ],
  "protected_paths": [
    "paper-trader/docs/agent/CURRENT.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/backend/app",
    "paper-trader/backend/migrations",
    "paper-trader/backend/tests",
    "paper-trader/backend/research_tests",
    "paper-trader/frontend",
    "/Users/priyanshusaraf/dev/strategy-os-frontend",
    "paper-trader/scripts/deploy.sh"
  ],
  "scope": [
    "Reproduce only V0-CS-001 and V0-CS-003 from the immutable reviewer fixtures; retain V0-CS-002 capability refusals and V0-CS-004 typed Decimal handling unchanged.",
    "Map where schedule id/address, charge components, Position, Trade and result/cache identity are authored, persisted, copied, restored and reconstructed. Do not create a second money ledger, order path, position lifecycle or charge calculator.",
    "Decide explicitly between an additive nullable durable Paper charge-authority fact and pre-effect refusal of every ambiguous open. Prefer the durable fact if it is the smallest design that preserves the supported Paper product; any schema proposal must use expand-contract compatibility and keep historical NULL rows truthful.",
    "Guarantee risk-reducing Paper exits remain available after restart. Missing/legacy attribution may refuse new entries or nonessential analytics but may not make an already-open Paper position impossible to close.",
    "Replace caller-asserted legacy compatibility with authority derived from a frozen historical result envelope, verified manifest or exact legacy-address recomputation. The same legacy identity must deterministically yield one answer or refuse before publication/cache reuse.",
    "Produce exact adversarial RED tests and mutations for rounded v1/v2 collisions, expected-label bypass, restart, partial close, exit availability and same-legacy-address/different-inputs. Name SQLite and disposable PostgreSQL migration/restore evidence if schema changes.",
    "Output one fresh implementation capsule with non-overlapping paths, owner gates, deployment impact and a new Critical review lineage; do not reopen the rejected capsule or grant live/provider/deployment authority."
  ],
  "acceptance": [
    "An authority/state-flow map identifies the sole writer and reader of every Paper charge-selection and historical compatibility fact, including restart, partial close, copy/restore and cache publication.",
    "A decision record returns KEEP, KEEP + HARDEN, REFACTOR, REPLACE or DEFER and explains why rejected alternatives fail the V0 product or invariants.",
    "The schema/no-schema choice is exact. If additive persistence is selected, columns/tables, null semantics, migration head, backfill policy, restore/downgrade plan and historical reconstruction behavior are named without silently relabelling old rows.",
    "The successor acceptance matrix proves no cash/row effect before an unreconstructible open, durable schedule reconstruction after restart, always-available risk-reducing Paper exit, paise conservation and paper/live separation.",
    "Historical compatibility binds a complete authoritative legacy identity to one v1 answer and rejects any second answer, base mismatch, incomplete envelope or caller-only assertion.",
    "Exact implementation/review paths and collision ownership are sealed; zero product/test/schema/control writes are evidenced."
  ],
  "test_plan": [
    "Run reviewer adversarial fixtures read-only and inspect current migration/model/copy/restore/result identity contracts.",
    "Build a failure-hypothesis matrix for durable schedule authority, risk-reducing exit continuity and legacy one-to-one reconstruction.",
    "Validate capsule metadata, protected hashes and zero product/control writes; seal the successor capsule and evidence-indexed report."
  ],
  "parallel_budget": 1,
  "assignments": [
    {
      "id": "nmt004_paper_charge_authority_replan_owner",
      "agent": "default",
      "model": "gpt-5.6-sol",
      "reasoning_effort": "high",
      "fork_turns": "none",
      "mode": "write-evidence-only",
      "depends_on": [],
      "reason": "The second Critical rejection crosses Paper money reconstruction, risk-reducing exit availability, historical cache identity and a possible shared-schema boundary.",
      "read_paths": [
        ".agent/runs/strategy-os-v0-charge-schedule-and-segment-fallback-correction",
        "paper-trader/backend/app/engine/broker.py",
        "paper-trader/backend/app/engine/charges.py",
        "paper-trader/backend/app/backtest/identity.py",
        "paper-trader/backend/app/db/models.py",
        "paper-trader/backend/app/db/copy_contract.py",
        "paper-trader/backend/app/db/restore_contract.py",
        "paper-trader/backend/migrations",
        "paper-trader/backend/tests",
        "paper-trader/docs/engineering/decisions/0012-execution-state-ownership.md",
        "paper-trader/docs/engineering/decisions/0017-sizing-target-position-and-reservation.md"
      ],
      "write_paths": [
        "paper-trader/docs/agent/tasks/strategy-os-v0-paper-charge-authority-and-legacy-identity-replan.md",
        ".agent/runs/strategy-os-v0-paper-charge-authority-and-legacy-identity-replan"
      ],
      "output": ".agent/runs/strategy-os-v0-paper-charge-authority-and-legacy-identity-replan/report.md"
    }
  ],
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "high",
    "fork_turns": "none",
    "service_tier": "priority",
    "routing_note": "Bounded read-only architecture escalation after a second Critical money/authority rejection; high is required to resolve schema and historical identity ownership without product writes."
  },
  "owner_task": "01a04c7c-257a-7210-9dd3-f639c661db00",
  "review": {
    "required": false,
    "assignment_id": "nmt004_paper_charge_authority_replan_owner",
    "agent": "owner",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c",
    "package": ".agent/runs/strategy-os-v0-paper-charge-authority-and-legacy-identity-replan/review-package.json",
    "review_paths": [
      "paper-trader/docs/agent/tasks/strategy-os-v0-paper-charge-authority-and-legacy-identity-replan.md",
      ".agent/runs/strategy-os-v0-paper-charge-authority-and-legacy-identity-replan"
    ],
    "exclude_paths": [
      "paper-trader/docs/agent/CURRENT.md",
      "paper-trader/docs/agent/programme/PROGRAMME.json",
      "paper-trader/backend",
      "paper-trader/frontend",
      "paper-trader/scripts/deploy.sh"
    ],
    "output": ".agent/runs/strategy-os-v0-paper-charge-authority-and-legacy-identity-replan/report.md",
    "verdicts": ["AUTHORITY_MAP", "SCHEMA_DECISION", "SUCCESSOR_CAPSULE"],
    "max_rechecks": 0
  },
  "owner_gates": [
    "This replan is read-only and owns no product, test, schema, migration, control, frontend, provider, live, order, credential or deployment path.",
    "A successor may propose an additive Paper-only schema fact, but implementation waits for root acceptance, exact migration ownership and a fresh Critical review route.",
    "No live charge schedule, provider contract-note assumption, real broker call, production data or customer-money action is authorized."
  ],
  "stop_conditions": [
    "A safe V0 result requires changing live order/routing/sizing/risk authority or adopting a second position/money model.",
    "Historical uniqueness cannot be verified from repository/base artifacts without silently inventing or relabelling old data.",
    "Any planned write overlaps an active NMT-003, monitoring, frontend or other shared-schema owner."
  ],
  "deployment_impact": {
    "classification": "none for replan; successor may be an additive USER/money schema and Paper runtime change requiring migration, restore, rollback, restart and deterministic artifact evidence",
    "required_evidence": "The replan must name exact migration/deployment obligations rather than defer them vaguely. No deployment claim follows."
  },
  "decision": "KEEP + HARDEN",
  "delivery_status": "accepted",
  "output_artifacts": {
    "report": {"path": ".agent/runs/strategy-os-v0-paper-charge-authority-and-legacy-identity-replan/report.md", "sha256": "b72804d0b73b25d8190465f4cc4b1e09bcee0d5e0fb1c0a731358d3adac99ed9"},
    "successor_capsule": {"path": ".agent/runs/strategy-os-v0-paper-charge-authority-and-legacy-identity-replan/successor-capsule.json", "sha256": "1f72cb51d9112790162fd2b6c7cc61160c46d57b353b010636ccdb7047781468", "id": "strategy-os-v0-paper-charge-authority-and-legacy-identity-correction"},
    "review_package": {"path": ".agent/runs/strategy-os-v0-paper-charge-authority-and-legacy-identity-replan/review-package.json", "sha256": "c06b424fdb183d0d910b12ca601cc8fce5fd3f6f4c69a55efdd372ca272c9f2c"},
    "replan_seal": {"path": ".agent/runs/strategy-os-v0-paper-charge-authority-and-legacy-identity-replan/replan-seal.json", "sha256": "e37f6bbeb6eaedb2d0c101a76e022f6b817f1d3871e43265c1fe553218a72793"}
  },
  "nonclaims": [
    "No NMT-004 acceptance, Paper exit fix, historical cache fix, schema change, public Paper runtime, live execution, deployment, production readiness or V0 completion follows from this replan."
  ]
}
---

# V0 Paper charge authority and legacy identity replan

The original NMT-004 capsule exhausted its only focused recheck with two P0
findings still open. This read-only capsule decides the smallest safe successor
for durable Paper charge authority and one-to-one historical result identity.
It cannot edit product, tests, schema, migrations, frontend or programme state.

## Terminal replan receipt

Verdict: `AUTHORITY MAP PASS / SCHEMA DECISION KEEP + HARDEN / SUCCESSOR CAPSULE SEALED`.

The immutable V0-CS-001 and V0-CS-003 fixtures reproduce on the exact frozen
source bytes. The smallest safe successor uses additive nullable, leg-specific
Paper schedule authority on the existing Position and Trade rows. Historical
NULL stays unknown and is never backfilled. A valid legacy Paper Position can
still take a risk-reducing exit: the entry remains unknown while the new exit
leg records its exact selected schedule. The caller-asserted legacy result helper
is replaced by a duplicate-refusing frozen manifest whose exact preimage
recomputes one old identity and one v1 answer; it cannot alias current cache or
publication identity.

The successor is sealed but blocked from dispatch until monitoring persistence
passes its focused recheck and releases shared model/copy/restore/schema paths.
It must then query one exact execution head of `0044` before creating `0045`; a
different head or owner stops and replans the path. No implementation or review
was launched.

- Report: `.agent/runs/strategy-os-v0-paper-charge-authority-and-legacy-identity-replan/report.md`
  (`b72804d0b73b25d8190465f4cc4b1e09bcee0d5e0fb1c0a731358d3adac99ed9`)
- Successor capsule: `.agent/runs/strategy-os-v0-paper-charge-authority-and-legacy-identity-replan/successor-capsule.json`
  (`1f72cb51d9112790162fd2b6c7cc61160c46d57b353b010636ccdb7047781468`)
- Evidence manifest: `.agent/runs/strategy-os-v0-paper-charge-authority-and-legacy-identity-replan/evidence-manifest.json`
  (`a72634cbbeb0427d51c49b3543e223be79c777bc248641b97fdeaad3a8161626`)

Product, test, schema, migration, frontend, control and deployment writes: zero.
