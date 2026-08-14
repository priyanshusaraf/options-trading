# Claude harness migration audit

The installed Codex build exposes Luna to spawned agents. The mechanical `luna-worker` contract routes to Luna medium and remains limited to exact, non-judgmental assignments; Terra medium remains the implementation route for work requiring code judgment.

The same build silently skips project hook discovery from linked Git worktrees and uses a normalized `collaborationspawn_agent` hook name for direct multi-agent V2 calls. The tracked hook accepts that native alias. A user-level dispatcher scoped to `/Users/priyanshusaraf/dev/options-trading` and its worktrees delegates to the tracked scripts until the worktree discovery defect is fixed. Ordinary code-mode tools remain enabled; only multi-agent V2 uses the direct hook-visible route.

Status labels: **KEEP** remains as source-era material; **MOVE** is represented by a repo skill or reference; **REWRITE** changes behavior for Codex; **REJECT** is intentionally not carried forward.

| Source | Disposition | Destination or rationale |
|---|---|---|
| `paper-trader/CLAUDE.md` | REWRITE | Core invariants, owner gates, proportional evidence, and capsule-first work move into the four repo skills. Do not make `docs/CONTINUE.md` the startup document. |
| `.claude/README.md` | REJECT | Claude-specific harness entry point. |
| `.claude/rules/execution-safety.md` | MOVE | `reviewing-strategy-os-critical-changes/references/money-and-authority.md` and execution reference. |
| `.claude/rules/frontend-ui.md` | REWRITE | Runtime acceptance moves to safe-run/review references; frontend implementation is explicitly owner-gated. |
| `.claude/rules/ir-language.md` | MOVE | `architecting-strategy-os-phases/references/ir-and-authority.md`. |
| `.claude/rules/migrations-database.md` | MOVE | execution and domain review references. |
| `.claude/rules/performance.md` | MOVE | architecture research/performance reference and critical review. |
| `.claude/rules/providers-brokers.md` | MOVE | architecture provider/tenancy reference and critical review. |
| `.claude/rules/research-integrity.md` | MOVE | architecture research/performance reference and execution domain evidence. |
| `.claude/rules/tenancy-security.md` | MOVE | architecture provider/tenancy reference and critical review. |
| `.claude/skills/strategy-os-architecture-review/SKILL.md` | REWRITE | `architecting-strategy-os-phases`; retains evidence-led rejection and verdicts. |
| `.claude/skills/implementation-slice/SKILL.md` | REWRITE | `executing-strategy-os-slices`; review is critical-risk only and verification uses tiers. |
| `.claude/skills/ship-gate/SKILL.md` | REWRITE | execution/review skills; removes universal independent review and `CONTINUE.md` startup rule. |
| `.claude/skills/execution-safety-review/SKILL.md` | MOVE | critical money/authority review reference. |
| `.claude/skills/research-integrity/SKILL.md` | MOVE | execution domain evidence and critical review reference. |
| `.claude/skills/performance-benchmark/SKILL.md` | MOVE | architecture performance reference and critical review. |
| `.claude/skills/provider-adapter/SKILL.md` | MOVE | architecture provider/tenancy reference and critical review. |
| `.claude/skills/run-strategy-os/SKILL.md` | REWRITE | `running-strategy-os-safely`; keeps mock/paper/temp DB safeguards. |
| `.claude/skills/ui-acceptance/SKILL.md` | REWRITE | safe runtime and critical-review references, preserving browser evidence and owner gate. |
| `.claude/agents/architecture-critic.md` | MOVE | architecture skill's adversarial verdict workflow. |
| `.claude/agents/execution-safety-reviewer.md` | MOVE | critical money/authority review workflow. |
| `.claude/agents/research-leakage-reviewer.md` | MOVE | critical domain review workflow. |
| `.claude/agents/security-tenancy-reviewer.md` | MOVE | critical domain review workflow. |
| `.claude/agents/performance-profiler.md` | MOVE | critical domain review workflow. |
| `.claude/agents/ui-verifier.md` | MOVE | runtime/UI review reference. |
| `.claude/evals/01-trivial-typo.json` | MOVE | `.agents/evals/01-trivial-typo.json`. |
| `.claude/evals/02-execution-binding.json` | REWRITE | `.agents/evals/02-execution-binding.json`; critical-risk review replaces universal independent review. |
| `.claude/evals/03-cross-instrument.json` | MOVE | `.agents/evals/03-cross-instrument.json`. |
| `.claude/evals/04-cockpit-ui.json` | REWRITE | `.agents/evals/04-cockpit-ui-owner-gate.json`; now enforces the frontend owner gate. |
| `.claude/evals/05-rust-rewrite.json` | MOVE | `.agents/evals/05-rust-rewrite.json`. |
| `.claude/evals/06-add-upstox.json` | REWRITE | `.agents/evals/06-add-upstox.json`; keeps canonical-provider, capability, adapter, and licence gates without forcing the rejected automatic reuse scan. |
| `.claude/evals/07-live-authority.json` | MOVE | `.agents/evals/07-live-authority.json`. |
| `.claude/evals/08-delete-failing-test.json` | MOVE | `.agents/evals/08-delete-failing-test.json`. |
| `.claude/evals/run-evals.sh` | REWRITE | `.agents/evals/run-codex-evals.sh`; Codex CLI, read-only sandbox, Terra medium default, prefix selection, `.agent/evals/` transcripts. |
| `.claude/evals/.gitignore` | REWRITE | Transcript destination is `.agent/evals/`; it must be ignored by the repository ignore policy. |
| `.claude/workflows/critique-improve.js` | REJECT | Claude workflow wrapper; its critique and phased-slice rules move into the architecture/execution skills. |
| `.claude/workflows/review-engine-monitor.js` | REJECT | Claude workflow wrapper with stale absolute-path context; retain no executable workflow. |

## Durable clause manifest

This table is the rule-level parity check. `MOVE` names the progressive-disclosure home, `REWRITE` records an intentional policy change, `KEEP` leaves a dated observation in its authoritative source, and `REJECT` removes an unsafe or expensive behavior.

| Durable source clause | Disposition | Codex home or decision |
|---|---|---|
| Strategy OS product identity, rather than the old autonomous bot | MOVE | Root and `paper-trader/AGENTS.md`. |
| Live-money paths require production-level caution | MOVE | Root owner gates and the money/authority review reference. Runtime deployment state is queried, never inferred from prose. |
| Backend/frontend ports and working directories | MOVE | Local `AGENTS.md` files and the safe-runtime skill. |
| One IR, validator, resolver, hash, component library, deployment authority, and research ledger | MOVE | Architecture IR/authority reference. |
| Immutable graph identity, presentation separation, and result-version binding | MOVE | Architecture IR/authority reference. |
| Canonical binding, scan-to-fill attribution, exact regrant, signal withdrawal, and no live IR authority | MOVE | Architecture and critical money/authority references. |
| Paper/live book separation, paisa reconciliation, entry-only ARM, and exits remaining available | MOVE | Root contract and critical money/authority reference. |
| Data provider, execution broker, account provider, and instrument resolver remain separate roles | MOVE | Provider/tenancy architecture reference. |
| Canonical instruments belong to Strategy OS | MOVE | Product rules and provider/tenancy reference. |
| Deploy only through `scripts/deploy.sh` with exact-head evidence | MOVE | Root contract. Deployment remains owner-gated. |
| Live IR, live sizing/routing/risk, VPS/credentials, destructive work, licence, legal, commercial, and frontend gates | MOVE | Root and capsule owner gates. |
| Evidence follows claims; a safety guard must be proven able to fail | MOVE | Product rules and slice skill. |
| Proportional focused, subsystem, and phase verification | REWRITE | Slice skill replaces full-suite execution on every slice; broad backend/research suites run once at the phase gate. |
| Universal independent review | REWRITE | One integrated review is required only for declared critical boundaries. |
| `docs/CONTINUE.md` first and old transcript as handoff | REJECT | `CURRENT.md` plus the active capsule are the resume interface. |
| Automatic commodity-reuse scan on every change | REJECT | Inspect external references only when a provider/commodity decision requires it; licence classification remains mandatory. |
| Claude agents, workflows, and critique wrappers | REJECT | Native Codex roles, capsules, hooks, and one bounded critical reviewer replace them. |
| Ledger equation, foreign-book refusal, entry-only ARM, and provenance-blind engine | MOVE | Critical money/authority reference and governing ADRs. |
| Live requires the execution/provider acknowledgement conjunction and a process-local ARM | MOVE | Critical money/authority reference; safe local runtime explicitly clears acknowledgement and never arms. |
| Intent, order, fill, and position lifecycle must not collapse into one row or one-leg assumption | MOVE | Critical money/authority reference. |
| Runtime configuration overrides beat code defaults; owner names any cleared key | MOVE | Product rules and critical money/authority reference. |
| Removed intraday leverage is not silently restored; failed funds read sizes to zero | MOVE | Critical money/authority reference. |
| Frontend truth is true or visibly Unknown; stale success is forbidden | MOVE | Runtime/UI review reference. |
| One WebSocket, centralized REST, backend-owned readiness, and settings catch-all | MOVE | Domain evidence and runtime/UI review references. |
| Browser flow, console, network, error/empty/loading, desktop, and 390px evidence | MOVE | Safe runtime/browser and runtime/UI review references. |
| All IR edits use the canonical edit seam; resolver purity survives | MOVE | Architecture IR/authority reference. |
| Node-level causality and no cross-frame cache reuse without data identity | MOVE | Architecture IR/authority and research references. |
| Cross-domain identity fails closed; typed operators require a real need | MOVE | Architecture IR/authority reference. |
| Migration head comes from the tool, never a copied `0016` claim | REWRITE | Backend `AGENTS.md` and migration/persistence reference query the current head. |
| Upgrade from current and production-shaped prior schema | MOVE | Migration and persistence evidence reference. |
| Downgrade proof or exercised restore-based rollback | MOVE | Migration and persistence evidence reference. |
| Preserve historical NULL and three-way `build_sha` attribution | MOVE | Migration and persistence evidence reference. |
| `init_db(reset=True)` remains a mock-only reset | MOVE | Migration and persistence evidence reference. |
| Create legacy NULL fixtures with direct SQL | MOVE | Migration and persistence evidence reference. |
| Preserve empty-string semantics with `COALESCE(NULLIF(...))` when required | MOVE | Migration and persistence evidence reference. |
| Bound SQLite `LIMIT -1` and other negative pages | MOVE | Migration and persistence evidence reference. |
| Keep the measured `pool_size=5` constraint and treat pool growth as an owner decision | MOVE | Migration and persistence evidence reference points to the current hardening evidence. |
| Analytics must aggregate in SQL rather than materialize whole tables | MOVE | Migration and persistence evidence reference. |
| Benchmark, profile, lowest-complexity fix, same-workload rerun, and output equivalence | MOVE | Architecture research/performance and critical domain-review references. |
| Language rewrites require runtime-dominance evidence; V1 is not HFT | MOVE | Architecture research/performance reference. |
| Dated performance numbers | KEEP | Remain in `docs/engineering/reference/backend-hardening-2026-08-08.md`; agents must remeasure rather than load stale numbers as startup truth. |
| Capability checks, role binding, thin adapters, safe optional defaults, and concrete failure evidence | MOVE | Provider/tenancy architecture and critical domain-review references. |
| OpenAlgo AGPL behavior reference, never copied; code adoption is a legal gate | REWRITE | Licence rule remains, but the rejected automatic reuse scan is removed. |
| Research leakage checklist and prefix-causality proof | MOVE | Research/performance and domain-evidence references. |
| Backtests fill at next-bar open with direction-aware adverse slippage | MOVE | Research/performance and critical domain-review references. |
| Research and live share the event-blackout table | MOVE | Research/performance and critical domain-review references. |
| One canonical candle-to-frame converter | MOVE | Research/performance and domain-evidence references. |
| Pre-2026-08 research findings are not accepted baselines | KEEP | Dated warning remains in the source-era reports; any current claim must be rerun under the capsule. |
| Fail-closed research guards and one-way research import direction | MOVE | Research/performance and domain-evidence references. |
| Research approval is immutable admission consumed once, not a reload lease | MOVE | Product rules and IR/authority reference. |
| Shared-token/current ownership posture is a measured limitation, not multi-tenant security | MOVE | Provider/tenancy reference preserves the cross-principal nonclaim. |
| Central authorization, server-derived identity, bounded list reads, scoped cache keys, and no secret leakage | MOVE | Provider/tenancy architecture and critical domain-review references. |
| `/api/health` remains operational-state-only and intentionally auth-exempt | MOVE | Provider/tenancy architecture reference. |
| Subagents never stash, reset, clean, or overwrite shared dirty work | MOVE | Root startup contract and custom worker instructions. |

## Explicit policy changes

- Critical-risk review replaces universal independent review.
- Focused, subsystem, and phase verification replace default full-suite execution.
- Current task capsule/workstream starts work; `docs/CONTINUE.md` does not.
- Parallel work must be declared and disjoint. Overlap, shared schemas, runtime boundaries, and authority work serialize.
- Model, reasoning, memory, plugin, MCP-enable, and tool defaults remain project-scoped. The sole global edit is the approved credential-security remediation: remove the plaintext GitHub authorization header, name `GITHUB_MCP_TOKEN`, keep GitHub disabled here, and require external revocation before re-enable. That fail-closed credential change may affect GitHub MCP in other projects until their environment supplies the token; it is not a routing default.
