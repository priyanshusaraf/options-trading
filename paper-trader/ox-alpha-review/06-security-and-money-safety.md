# 06 — Security and Money Safety: Posture, Ranked Risks, and the No-Silent-Outage Contract

**Your standard:** "under no circumstance can there be security issues… real money… no server
outages or request timeouts which happen without letting users know." This document states the
current posture honestly, ranks what can actually hurt you, and turns the standard into
checkable mechanisms.

## 1. What is already strong (keep, do not weaken)

- **Owner gates** on live IR authority, sizing/routing/risk changes, credentials, destructive ops.
  These are why eight false-green harnesses and a forged-capability-assessment defect never
  reached acceptance. They are the most valuable control in the repo.
- **Fail-closed defaults everywhere it matters:** book resolution fails to `live` (strictest);
  v2 runtime terminally refuses (`V2_RUNTIME_UNAVAILABLE`) before side effects; unknown/stale
  identity, ownership, provenance, capability → refuse; ARM gates entries only, exits never gated.
- **Structural paper/live separation** with `foreign_book_positions` loud-reporting.
- **Protected-file SHA pinning** — verified intact today (doc 02, claim 12).
- **The defect-pattern register + immutable verdicts + independent review** — the meta-control
  that caught the meta-controls' failures.
- **Audited-clean surfaces:** generated-strategy sandbox (AST allowlist + empty builtins),
  injection sweep, provider conformance contract, causality proofs, bounded reads at both layers.

## 2. Ranked risks (what can actually hurt money or users, soonest first)

| # | Risk | Why it matters | Mitigation owner |
|---|---|---|---|
| 1 | **374 uncommitted entries** | All evidence SHA-pins reference unprotected bytes; loss/corruption unrecoverable; agents authorized to mutate trees | You/Codex, this week (doc 04 §1) |
| 2 | **A-02 boolean→1.0 ingress** | Corrupted candles poison dataset identity, research results, sizing, execution inputs | Bounded slice (doc 03 step 3) |
| 3 | **A-01 migration trigger loss** | Old installs could lose immutability/secret-protection triggers silently | Bounded slice + narrowed contract |
| 4 | **Auth revocation semantics undocumented** (FND-01) | Multi-tenant Phase 1 exists; what deletion/revocation means for by-value owner provenance is undefined | Small ADR + tests before Phase 6 |
| 5 | **Rate limiting/backpressure/tenant isolation unproved** (Codex's own table) | One trader's load could affect another's latency or order correctness once multi-tenant | D2/D3 mechanisms + Phase 6 preflight |
| 6 | **npm: 1 critical + 2 high audit findings; backend deps floored, no lockfile** | Supply-chain exposure on a box that touches money | Lockfile + audit-closure slice |
| 7 | **Process-kill coverage at write boundaries incomplete** (FND-07 note) | Split-brain authority rows after crashes | Extend the savepoint/transaction proof to kill-tests |
| 8 | **Pool cliff** | Request failures under load — now AWS-unblocked | D2 |
| 9 | **P5-ADV-006-RUNTIME nonclaim** (successful v2 reclaim/finalization unproved) | Known, deliberately deferred; must stay a nonclaim until its capsule | Keep gated |

## 3. The no-silent-outage contract — made concrete

"Users must know" requires four mechanisms, none of which exist fully yet:

1. **Degraded is a first-class state, not an error state.** Every surface (feed, pool, queue,
   provider) maps its saturation to a visible degraded state with a reason string, exactly like
   the existing `FUTURES_NO_CONTRACT` / `V2_RUNTIME_UNAVAILABLE` refusals. The UI already has
   health banners; extend vocabulary, don't invent new channels.
2. **Deadlines everywhere.** Request budget + provider-call budget; on breach, structured
   degradation. A timeout that surfaces as a generic 500 is a defect by this standard.
3. **Capacity truth before activation** — the capacity receipt (docs 04–05). The preflight
   refuses or degrades loudly when required rates exceed available budgets.
4. **Leading indicators on health** — pool utilization, queue depth, feed staleness, provider
   budget burn. `/api/health` currently tells you when it's dead; it must tell you when it's
   *approaching* dead. (The July watchdog covers loop liveness; extend to these.)

## 4. Security gates to add for the AWS era (small, high-value)

- Secrets: AWS-managed store; no `KITE_*`/`TELEGRAM_*` in images or env files; rotation runbook.
- Per-tenant resource ceilings enforced at the job/worker boundary (Phase 2 gave the seam).
- Audit trail: append-only, content-addressed (the machinery exists — reuse the review-snapshot
  pattern) for authn events, authority grants, deployment activations, order placements.
- Break-glass procedure documented before client onboarding (Phase 10 scope, but design the hook
  now: an audited, owner-gated override path).
- Keep the existing rule: credential-dependent checks are named production verification, never
  green CI.

## 5. The standing money verdict, unchanged by this review

I concur with the Codex assessment: **research and paper only today.** The specific gates between
here and real-money confidence are, in order: A-01/A-02 fixed and re-audited; deployability
(FND-15) proven on the real target infra; tenant isolation + load controls with direct evidence;
order idempotency/reconciliation proof (P5-ADV-006-RUNTIME and friends); and an owner-signed
cutover with reconciliation against the live ledger. None of these are blocked by unknowns —
they are blocked by sequencing, which doc 04 fixes.
