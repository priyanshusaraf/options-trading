# GPT-6 Astra instruction and workflow audit

The repository instructions now give clearer authority to direct assignments, load less routine context, and scope verification to the affected work. The common startup documents are 24.0% smaller by UTF-8 bytes. This is a measured reduction in instruction volume, not a measured improvement in model latency, cost or task success.

Audited on 5 September 2026 in `codex/execution-foundation`, starting at `de6faae3e97cf5537338bee2143350e53f70da1c`, with substantial inherited changes. Changes cover instructions, role prompts, evaluation cases and their documentation. Application code, model defaults, executable hooks, CI and product authority were not changed by this audit.

## Official guidance used

The current [GPT-6 Astra model guide](https://developers.openai.com/api/docs/guides/latest-model) recommends auditing skills and instruction files for conflicts, encouraging follow-through, specifying writing and delegation preferences, and calibrating verification. It recommends preserving effective reasoning effort during migration unless the prior setting is unsupported. Applied here through explicit assignment precedence, bounded delegation and proportional checks; no automatic increase to maximum reasoning.

[Codex instruction discovery](https://developers.openai.com/codex/guides/agents-md) explains that local instructions accumulate from root to working directory within a byte budget. Shared rules belong in the root; local files retain subsystem differences. The existing 12,288-byte project limit remains sufficient after the changes.

[Official skill guidance](https://developers.openai.com/codex/skills) recommends focused descriptions and progressive disclosure: skill metadata first, the selected entrypoint next, and supporting material when needed. All 35 repository entrypoints retain their task boundaries and `SKILL.md` filename. No new universal skill or duplicated policy layer was added.

[Official subagent guidance](https://developers.openai.com/codex/multi-agent) establishes that custom role files can override explicit spawn model and effort settings. The instructions now tell the parent to select a compatible role or the default agent with explicit settings and bounded review instructions. This supports an Astra assignment without silently substituting a fixed Sol role. Delegation remains conditional on useful independent work.

The official pages were fetched and read; copies are in the ignored evidence directory. API-only features such as asynchronous function calls are not repository prompt settings and were not added to Codex configuration.

## Findings and changes

| Finding | Repository evidence | Resolution |
| --- | --- | --- |
| Startup status exceeded its existing budget | `WORKING-PLAN.md` was 10,731 bytes; its 6,144-byte contract failed before edits. | Moved its status section intact to `WORKING-STATUS-2026-09-05.md`; the plan is now 4,878 bytes. Continuation ownership and pending product checks remain linked. |
| Shared instructions repeated startup, model and persistence rules | Root agreement, router, orientation and execution skills repeated the same obligations. | Consolidated shared behavior in root `AGENTS.md`; reuse context and existing handoffs. Orientation no longer requires a separate receipt or universal file hashing. Artifact identity and concurrent ownership still justify hashes. |
| Capsule wording could block a concrete assignment | Several domain skills use “active capsule” as shorthand; newer execution guidance accepts direct assignments. | Defined the shorthand once in the root and corrected historical document routing. Explicit capsule contracts still apply when resumed. |
| UI guidance broadened desktop work | Execution and review references required 390px/mobile evidence; the working plan defers phone work. | Check the assignment's supported layouts; require mobile evidence only when mobile is in scope. Preserve browser, failure-state and backend-truth checks. |
| Ordinary frontend work could gain another approval step | Accessibility and release skills repeated a frontend owner gate. | Bounded frontend implementation follows the current assignment. Deployment and live actions retain their separate gates. |
| Legacy frontend guidance pointed to a design checkout | `paper-trader/frontend/AGENTS.md` named the separate design repository as an implementation alternative. | Points to repository-owned `../strategy-frontend` for V0; the legacy package remains distinct. |
| Reviewer role contradicted the integrated review skill | Role required a generated package for every review and allowed only one recheck. | Direct reviews consume the assigned diff and evidence; explicitly resumed package contracts remain enforced. Rechecks follow corrected findings and affected consumers. |
| Worker prompt stopped on routine ambiguity | `terra-worker.toml` ended with a broad ambiguity stop condition. | Resolve routine choices from context; escalate actual ownership/dependency/gate conflicts while continuing independent work. |
| Evaluations rewarded obsolete policy | Cases 04, 12, 13 and 14 required a UI gate/mobile checks, capsule refusal, universal goal creation and Sol high. | Updated scenarios to test desktop scope, direct authority, explicitly requested goals and an explicit Astra low reviewer choice. |

## Instruction surface reviewed

The audit inventoried all five `AGENTS.md` files, 35 skill entrypoints, 15 skill references, three custom roles, project configuration, evaluation runner/cases, native guard behavior and relevant CI/test entrypoints. The skill scan focused on triggers, instruction conflicts, authority, repetition and reference loading; it was not a fresh domain-security, financial or legal audit.

| Skill group | Disposition |
| --- | --- |
| Orientation and execution | Edited `strategyos-repo-orientation` and `executing-strategy-os-slices`; retained `risk-weighted-verification` and `documentation-quality-review`. |
| Product and architecture | Retained `architecting-strategy-os-phases`, `architecture-invariant-audit`, `canonical-document-precedence`, `v1-release-scope-classifier`, `prior-art-review-gate`; corrected the precedence reference. |
| Research and money | Retained `anti-lookahead-and-market-truth`, `research-validity-audit`, `deterministic-capital-admission`, `execution-safety-and-reconciliation`. Their technical safeguards remain task-specific. |
| Providers and runtime | Retained `provider-adapter-conformance`, `provider-change-impact-review`, `resource-plan-and-cost-audit`, `running-strategy-os-safely`, `observability-instrumentation`. |
| Security and privacy | Retained `asvs-security-review`, `auth-and-session-hardening`, `tenant-isolation-audit`, `privacy-data-flow-review`, `analytics-privacy-review`, `support-diagnostics-runbook`. |
| Release and review | Edited `release-readiness-review` and the UI reference of `reviewing-strategy-os-critical-changes`; retained `auditing-strategy-os-deployability`, `database-migration-safety`, `dependency-license-sbom`, `incident-response-and-postmortem`. |
| User experience and services | Edited `accessibility-audit`; retained `customer-feedback-synthesis`, `seo-and-metadata-audit`, `transactional-email-review`, `razorpay-billing-review`. |

Installed personal/system/plugin skills were consulted where applicable, but their files and invocation settings remain outside the repository mutation scope. Their availability alone does not require loading them for every task.

## Verification and limits

- Repository contract suite: 9 checks pass after the change. The initial run had one failure, the working-plan byte budget; the threshold was preserved.
- Native hook suite: 33 checks pass, including direct-assignment handling, explicit capsule enforcement, model routes, review evidence and compaction continuity. These tests exercise the existing harness with fixtures; they do not certify every desktop dispatch path.
- Skill creator validator: all 35 entrypoints pass using the existing backend Python environment and PyYAML 6.0.3. The initial system-Python attempt lacked PyYAML and is recorded as an environment failure, not a validation pass. No dependency was installed.
- All 114 checked local file links resolve; all 15 evaluation cases parse as JSON. The scoped whitespace/diff check passes. These checks establish document integrity, not agent behavior.
- Four read-only scenario evaluations completed with `gpt-6-astra`, medium reasoning. Their responses were manually inspected in addition to regex checks: desktop scope, direct assignment, requested goal continuity and Astra low review routing all matched the intended decisions. Case 14 describes dispatch; it does not execute a reviewer or prove host enforcement.
- The original working-plan status text is preserved byte-for-byte as the suffix of the linked status file. Unedited instruction/configuration files match the saved baseline.
- The combined root agreement, working plan, router, orientation skill and execution skill decreased from 26,081 to 19,821 bytes. This is a comparison of this declared document set, not a tokenizer count or a promise that every task loads all five files.
- No executable functions changed. Complexity, CRAP and mutation scores therefore have no new code scope in this patch; the owner's numerical gates remain unchanged. Product suites and deployment journeys were not run for this instruction change.

Commands and local evidence are under `.agent/runs/astra-instruction-audit-2026-09-05/`; scenario transcripts are under `.agent/evals/`. Useful reproduction commands from the repository root:

```bash
python3 -m unittest discover -s .codex/tests -p test_repository_contract.py
python3 -m unittest discover -s .codex/tests -p test_hooks.py
CODEX_EVAL_MODEL=gpt-6-astra .agents/evals/run-codex-evals.sh 04 12 13 14
```

The scenario runner is a response smoke test: regex matches and hypothetical answers do not prove real implementation follow-through, correct child routing or speed. It also suppresses the CLI exit status, so inspect transcripts and final answers rather than accepting its label alone. No before/after agent-performance benchmark was performed. The next performance measurement should use isolated copies, the same Astra effort and representative fixed tasks; compare task correctness, unnecessary approvals, repeated checks, elapsed time and token usage over repeated runs.

Project context/compaction limits, tool-output limits, disabled connectors and configured Sol fallback roles were preserved because this audit does not establish that changing them improves Astra outcomes. Explicit user model choices take precedence through the documented compatible/default-role route. Historical capsule dispatch remains intentionally stricter; new direct work uses distinct assignment IDs. Nothing in this audit grants deployment, live-money or destructive-action authority.
