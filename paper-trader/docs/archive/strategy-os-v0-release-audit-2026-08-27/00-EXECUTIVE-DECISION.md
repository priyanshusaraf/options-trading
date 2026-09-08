# Executive decision

## Decision

`KEEP + HARDEN: SHIP V0 FROM THE CURRENT ARCHITECTURE THROUGH AN ACCELERATED,
RESEARCH-FIRST PROGRAMME.`

V0 should include the complete requested research product: Zerodha connection,
static watchlists, node canvas, safe custom nodes, professional charting and bounded
annotations, annotation identity, temporally honest replay, deterministic
backtesting, serious robustness tools, supported instruments, options/VIX/order-flow
context, canonical live monitoring, simple signals, signal review, responsive web UX
and privacy-conscious telemetry. The features remain in scope even when current
evidence says they must be built or corrected.

Public execution is excluded. Existing execution, sizing, capital, position and
reconciliation work remains in the repository behind server-enforced V0 denial and
returns later through V1.

## Largest coherent V0

The V0 product loop is:

```text
user-owned Zerodha data connection
→ static instrument watchlist
→ chart and versioned annotations
→ canonical node graph
→ deterministic historical backtest
→ locked OOS / walk-forward / bounded optimisation / neighbourhood / Monte Carlo
→ evidence and comparison
→ canonical forward monitoring
→ BUY / SELL / EXIT / HOLD presentation over exact backend state transitions
→ user review and research journal
```

Options, India VIX and bounded depth/order-flow inputs participate only where exact
provider capability, timestamps, storage and history exist. Absence becomes
`UNSUPPORTED` or prospective recording, never fabricated history.

## What already exists

- One typed/versioned Component IR, registry, resolver, validator and hash.
- Backend graph read/edit/layout APIs and a real integrated graph editor.
- Deterministic backtest sweeps, cache/artifact identity, job claims and persistence.
- Research qualification, nested optimisation, locked OOS/walk-forward, DSR, PBO,
  N-eff, evidence, comparison and review records.
- Static owner-scoped watchlists.
- Owner-scoped encrypted provider connections and Zerodha OAuth/token exchange.
- Canonical instruments, provider capability facts and market-data authority.
- Options chain retrieval, IV/Greeks, liquidity/delta selection and snapshot cache.
- Persistent signal events, paper/live separation, tenancy and current CI.
- Integrated frontend that passes 223 tests, typecheck and production build.
- Precision Slate design/build and visual builder prototype.

## What is not finished

- A server-enforced V0 profile that makes execution unreachable.
- A generally usable strategy-builder journey; the current graph UI is tied to a
  fixed repository graph and is too dense for the golden path.
- A verified public node allowlist. The 125 analytical components fail accuracy
  acceptance.
- Professional drawing persistence, normalized annotation semantics, locking and
  historical replay.
- Canonical public graph-to-backtest-to-live-monitoring integration in one UX.
- Monte Carlo and parameter-neighbourhood implementation; the prototype displays
  fixture results that the backend does not currently produce.
- Exact India VIX capability, broad historical options/depth truth, and live
  order-flow integration through canonical facts.
- User signal-review APIs/UI and product analytics.
- Production-shaped V0 services, configuration, migrations, security,
  observability, quotas, backup/restore and rollback evidence.

## Top blockers

1. `V0-P0-001` — execution routes, runner startup and LIVE/ARM/KILL UI remain public
   surfaces; hiding them is insufficient.
2. `V0-P0-002` — indicator accuracy is rejected for 60 components and unverified for
   40; V0 cannot expose the full catalogue.
3. `V0-P0-003` — the integrated frontend and Precision Slate have not converged;
   one is functional but execution-centric, the other is polished but fixture-only.
4. `V0-P0-004` — chart/annotation/version/replay contracts do not exist in product.
5. `V0-P0-005` — no complete golden benchmark reaches UI → graph → data → backtest
   → robustness → monitoring → signal review.
6. `V0-P0-006` — Zerodha terms, data display/retention, platform approval and SEBI
   research/signal positioning require owner/counsel/vendor decisions.
7. `V0-P0-007` — release deployability remains false; the current sanctioned deploy
   path targets the legacy execution service and requires a clean committed tree.

## September 8 assessment

| Gate | Current assessment | Reason |
| --- | --- | --- |
| Controlled demo | `POSSIBLE WITH CURRENT MOCK/FIXTURE LIMITS` | Current app boots safely and graph/backtest/research screens load, but it is not the V0 UX and does not prove the golden path. |
| Founder-assisted beta | `NO-GO ON CURRENT BYTES` | No V0 execution hard-disable, frontend convergence, annotation system, accuracy closure, deployment package or external legal/data clearance. |
| Paid private beta | `NO-GO` | Founder gate plus billing, support, privacy, terms, retention, backups and counsel approval are missing. |
| Broader public beta | `NO-GO` | No production rehearsal, capacity/abuse controls, provider/data approval, observability or incident operation. |

September 8 should be used for an owner-controlled demonstration and observed
strategy-testing session, not a claim that the requested public V0 is ready.

## Recommended release sequence

1. V0 release profile and execution hard-disable.
2. Verified/versioned node catalogue and indicator correction.
3. Canonical builder → backtest → evidence spine.
4. Zerodha/static-scope/options/VIX/order-flow data spine.
5. Chart, annotation identity and temporally honest replay.
6. Complete robustness lab.
7. Canonical monitoring, signals and user review.
8. Precision Slate convergence and responsive golden path.
9. Security, operations, telemetry and deployability.
10. V0 golden five plus owner strategy pack and final review.

## Go/no-go rule

Begin implementation only after the owner accepts this package and the exact first
capsule. No beta gate advances on a count of implemented files or passing unit tests.
It advances only on the named end-to-end evidence for that gate.
