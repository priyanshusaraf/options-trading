Reference: [section index](../STRATEGY_OS_V0_V6_OWNER_DIRECTION_RECONCILIATION_2026-08-29.md). Read with its scope; this is not a new assignment.

# Strategy OS V0–V6 owner-direction reconciliation

Date: 29 August 2026\
Status: accepted documentation and product-scope reconciliation\
Implementation authority: unchanged and capsule-bound

## Outcome

Use `KEEP + HARDEN`.

The verified 29 August handoff adds real product and programme direction. It does
not justify a repository rewrite, a second product model or immediate future-scope
implementation.

The reconciliation makes five controlling changes:

1. V0 is the immediate commercial research, evidence, monitoring and Alerts Inbox
   product, with auth, Test Mode billing, entitlements and privacy-safe admin. It
   has no public real-money execution authority.
2. V0 needs a distinct durable monitoring event, canonical `SignalAlert`, delivery
   attempts and attention state. The legacy execution-bound `SignalEvent` cannot
   serve this contract.
3. Google sign-in is a V0 requirement where compatible, implemented through the
   existing product session/account seam and kept separate from broker OAuth.
4. The future product map becomes V1 controlled execution; V1.5 discovery and
   derivatives depth; V2 active Portfolio and hedge intelligence; V3 two distinct
   marketplace products; V4 multi-leg/institutional/fund infrastructure; V5/V6
   enterprise treasury and market-risk systems.
5. Release progression is maturity-gated. Dates and registered-user counts are
   planning signals, never release authority.

All current product work still requires:

```text
CURRENT.md
→ matching PROGRAMME.json stage
→ exact capsule
→ required evidence and owner gates
```

## Source reconciliation

The source package was found in the frozen Desktop clone and read only. Its
`SHA256SUMS.txt` passed.

The ten direction/orchestration files are preserved exactly under:

```text
paper-trader/docs/program/owner-directions/2026-08-29/
```

All nine `canonical_sources/` copies are byte-for-byte identical to the accepted
development-checkout files. They introduce no technical-invariant changes and are
not duplicated in the imported source directory.

The exact import status and missing-source record is:

```text
paper-trader/docs/program/owner-directions/2026-08-29/REPOSITORY-INTEGRATION.md
```

Two recovered files named by the package were not present in the package, the
development checkout or filesystem search and were not claimed read:

```text
STRATEGY_OS_KLEPPMANN_AND_PROFESSIONAL_ENGINEERING_REVIEW_PROMPT_V3_SIMPLICITY_GUARDED_2026-08-28.md
STRATEGY_OS_CODEX_SIMPLICITY_AND_ANTI_OVERENGINEERING_DIRECTIVE_2026-08-28.md
```

The exact Professional Engineering Reference Programme is present. The repository
also has a V2 Kleppmann prompt, which is not a substitute for the missing V3.

## Precedence

Separate product direction, current permission and proof.

1. A later explicit owner decision controls only the capability it actually names.
2. This reconciliation and the preserved 29 August source sections control product
   scope and maturity timing where they are explicit.
3. `CURRENT.md`, the matching programme stage and active capsule control current
   implementation state and write permission.
4. The accepted hybrid addendum and its revised programme package control where
   the later reconciliation is silent.
5. The 24 August architecture memo controls where not superseded.
6. Accepted technical steers and ADRs retain their invariants unless explicitly
   amended.
7. Older vision, roadmap and inspection documents remain historical evidence.

The source package's master orchestration prompt is preserved intent. Repository
`AGENTS.md`, capsule, routing, dirty-tree and review rules control actual execution.

## Conflict decisions

| Question | Competing claims | Controlling decision | Retained invariant | Resulting scope | Current implementation permission | Unresolved decision |
| --- | --- | --- | --- | --- | --- | --- |
| What is the first commercial product? | Older V1 documents combined research and optional execution; the 27 August audit inserted V0; the 29 August package defines paid research/alerts V0. | Later V0 directive. | Research, signal, deployment and money remain distinct facts. | Commercial V0 is research/evidence/monitoring/alerts/auth/Test Mode billing/admin; no public execution. | Exact V0 capsules only. | Final price/cadence/tax/refund policy and external go-live remain owner/commercial gates. |
| Are the original nine replaced? | New package includes copies beside new direction files. | No. The nine copies are byte-identical. | One IR, market truth, provider separation, causality, exact identity, authority and evidence contracts remain. | New files amend scope and timing, not technical source bytes. | No product permission follows from equality. | None. |
| Is a signal log enough? | Accepted V0 planning had a signal transition/projection; the new directive requires `SignalEvent → SignalAlert → delivery/attention`. | Later Alerts Inbox directive. | Delivery or attention cannot mutate or erase canonical strategy evidence. | Add explicit monitoring event, alert, delivery and attention facts. | Contract/routing only until exact capsules open. | Final retention, snooze, notification-channel and analytics policies. |
| Can the existing `SignalEvent` be reused? | Current table is tied to deployment/broker execution; V0 has no execution authority. | Distinct-facts and V0-denial invariants. | Preserve legacy rows and execution meaning. | Create a distinct monitoring-domain event/table identity. Never alias the two meanings. | Future monitoring persistence owner only. | Exact public code/table noun freezes in the contract capsule. |
| Does Google replace auth? | Package requests Google; current system has invited enrollment, membership and `UserSession`. | Google extends the existing product-auth seam. | Server verification, stable subject identity, explicit linking, revocation, CSRF/origin and tenant ownership. | One Google/OIDC binding and account-linking path; supported non-Google path remains. | Future serialized identity capsule. | Dashboard/client/domain configuration, linking/recovery policy and secret placement. |
| Where do Dynamic Watchlists belong? | Older memo: V1.1; hybrid: V1; V0 audit: V0.1/V1; later package: V1.5. | 29 August maturity map. | Immutable scope/snapshot identity, bounded fan-out, point-in-time truth, churn and recovery. | Static scopes in V0; Dynamic Watchlists in V1.5. | No current dynamic implementation. | A narrower earlier pilot requires a later explicit decision and direct demand/capacity evidence. |
| What does V1 own? | Older V1 was the first research release; later V0 now owns that wedge. | V1 becomes controlled execution. | Sizing, target position, transactional admission, provider preflight, paper/live separation, lifecycle and reconciliation. | V1 consumes accepted V0 facts and adds bounded certified execution paths. | No V1 behavior switch from this document. | Each live asset/provider path remains separately gated. |
| What is V2? | Older V2 focused on workflows/diagnostics/richer data; later package makes active Portfolio the product outcome. | Later owner vision. | Strategic proposals never bypass transaction-time admission or silently mutate state. | V2 owns sleeves, risk snapshots, feasibility, alternative solutions, proposed revisions and hedge intelligence. | Documentation/seam only. | Exact solver/data/sleeve scope waits for demand and evidence. |
| Is there one marketplace? | Older sources used a broad marketplace bucket; later package separates downloadable assets and managed allocation. | Two-product V3 decision. | Source/rights/ownership/custody/execution authority and investor exposure remain distinct. | V3 has Strategy Asset Marketplace and Managed Model Allocation. | Documentation/provenance only. | Rights, disputes, suitability, regulated structure, custody, fees and conflicts. |
| Where do multi-leg/funds belong? | Older matrix placed multi-leg in V2 and institutional work in V3; later package assigns V4. | Later maturity map. | Exact legs, ownership, intermediate margin, partial-fill recovery and aggregate reconciliation; legal wrapper remains separate. | V4 owns structure-certified campaigns and institutional/fund infrastructure. | Future seam documentation only. | Structure order, provider combo capability, operational team and legal form. |
| Is `PositionCampaign` already the multi-leg parent? | ADR 0018/current schema use one instrument/product/direction; handoff uses the noun for several legs/products. | Preserve existing money-lineage meaning. | Historical attribution is never reinterpreted or inferred. | Freeze current single-instrument campaign. Reserve additive `EconomicPosition` as the preferred future V4 parent over one or more current campaigns/legs. | Documentation-only non-implementation ADR next. | Final noun and relationship freeze before V4 schema work. |
| Is enterprise treasury current scope? | Earlier accepted roadmap ends at broad V3; later package adds V5/V6. | Later product-ceiling decision. | Economic exposures are not fake exchange instruments; natural mitigations and policy authority remain first-class. | V5/V6 product ceiling only; Strategy OS integrates with enterprise systems but does not become an ERP. | No schema/service/provider work. | Accounting, OTC, counterparty, jurisdiction, IAM, experts and funding. |
| Do user count or date trigger rearchitecture/release? | Older documents had dates and the new scale brief lists stage envelopes. | Maturity gates and measured workloads. | Direct evidence, recovery, provider rights, security and staffed ownership. | Stage envelopes inform measurement only. | No new infrastructure. | Thresholds require observed baselines and SLOs. |

The full source/section conflict receipt is:

```text
.agent/runs/strategy-os-v0-v6-handoff-reconciliation/agents/scope-precedence/report.md
```
