# V0 scope and golden path

## Public V0 scope

Every owner-requested feature remains in the V0 programme. “Required” means it must
reach its release gate before public V0; it does not mean current bytes already pass.

### Public V0 — required

- User account, owner tenancy and one Zerodha data connection per user.
- Static user watchlists and manual canonical instrument selection.
- Responsive chart workspace.
- Versioned horizontal levels, zones, trendlines, channels, Fibonacci retracement
  and extension; exact executable subset identified explicitly.
- Draft/locked/superseded/archived annotation identity.
- Temporally honest historical replay for annotation-backed research.
- General node canvas over the canonical Component IR.
- Verified first-party node allowlist and safe Level 1/2 custom composition.
- Deterministic backtesting with realistic charges, slippage, sessions, expiry and
  evidence lineage.
- Locked OOS, walk-forward, bounded optimisation, parameter neighbourhood,
  sensitivity/parameter surfaces and seeded Monte Carlo.
- Supported NSE cash/index/futures/options research across declared timeframes.
- India VIX as an exact canonical input.
- Bounded live and captured-historical options/OI/five-level depth/order-flow facts.
- Canonical forward monitoring and deterministic signal-state transitions.
- Simple BUY/SELL/EXIT/HOLD presentation with exact explanation/context.
- User signal review and research journal.
- Privacy-conscious product analytics, quotas and diagnosable failures.
- V0-specific security, deployment, backup/restore, observability and rollback.

### Public V0 — include with limits

- Only accuracy-accepted node semantic versions are selectable.
- Only static watchlists; Dynamic Watchlists remain V0.1/V1.
- Level 1 reusable-group/fork and Level 2 formula custom nodes; no arbitrary Python,
  packages, filesystem or network.
- Options/depth history only for exact captured periods. Missing history is visible.
- Bounded watchlist size, active strategies, jobs, combinations, windows,
  Monte Carlo iterations, data range, option contracts and daily compute.
- Annotation execution only for normalized, tested semantics. Other drawings may be
  visual-only and must be labelled as such.
- Heavy authoring may remain desktop-first; signal/review/status must work at 390px.

### Internal / feature-flagged

- Existing paper execution, target sizing, capital admission and position lineage.
- Existing live broker/order/protection/reconciliation code.
- Multi-provider adapters beyond Zerodha.
- Level 3/4 custom-node contracts.
- Generated-strategy and research automation not exposed by the golden path.

The V0 server denies these surfaces even when the code exists.

### Deferred

- Dynamic Watchlists and Benchmark C: V0.1/V1.
- Portfolio-level backtesting and cross-strategy allocation: V1/V2.
- Certified options execution: V1.5.
- Broad annotation replay, fundamentals, workflows and diagnostics: V2 extensions.
- AI, ML, marketplace, managed models and institutional breadth: V3.

## Canonical V0 objects

V0 reuses the long-term facts:

```text
User/Organization
ProviderConnection
CanonicalInstrument
StaticInstrumentScope
ChartWorkspace + VendorArtifact
NormalizedAnnotationRevision
Strategy graph/version/admission
Dataset/market-truth/provider evidence
ExperimentSpec / jobs / trials / results
MonitoringAssignment (no execution authority)
SignalStateTransition
SignalReview
```

`MonitoringAssignment` is not a Deployment and cannot acquire an account execution
lease, capital, a broker route or order authority.

## V0 signal semantics

The visible vocabulary may be simple while the backend remains exact.

| Visible state | Backend transition |
| --- | --- |
| `BUY` | exact strategy state changes from non-long to target-long |
| `SELL` | exact strategy state changes from non-short to target-short |
| `EXIT` | exact target changes from long/short to flat |
| `HOLD` | no target-state transition at this completed evaluation event |

Every transition binds:

- owner and monitoring assignment;
- strategy and exact semantic version;
- canonical instrument roles and bindings;
- previous/target state and transition type;
- evaluation event/timestamp and latest consumed data timestamp;
- dataset/provider/truth/capability addresses;
- annotation revision addresses where used;
- state snapshot/reset lineage;
- deduplication identity and explanation;
- validity/freshness state.

No signal record owns capital or implies an order.

## Golden path

| Step | Current evidence | V0 blocker/fallback | Acceptance criterion |
| ---: | --- | --- | --- |
| 1. Sign up | Backend users/sessions/tenancy exist; integrated onboarding absent. | Founder-created accounts for owner demo only. | User creates/revokes own session; tenant isolation and privacy tests pass. |
| 2. Connect Zerodha | OAuth/vault backend tested; legacy UI route exists. | Demo uses mock; no real credential in audit. | V0 connection UX, backend-only secret, expiry/reconnect and vendor approval pass. |
| 3. Create static watchlist | Backend/frontend tested; currently tied to execution assignment. | Use research scope only. | Exact owner-scoped static scope, no execution authority, bounded members. |
| 4. Open chart | Lightweight chart works; professional workspace absent. | Controlled demo may use current chart. | Approved chart licence/datafeed, persistence, instrument/timeframe truth and responsive surface. |
| 5. Create/lock annotations | Absent. | No executable annotation fallback; visual-only labels allowed. | Exact geometry/version/lifecycle, owner isolation, immutable lock and restore. |
| 6. Build strategy | IR/editor tested; UI fixed to repository graph. Precision Slate mock. | Founder can use repository graph in demo. | Create/select/edit/publish arbitrary V0 draft from verified palette through batch edit. |
| 7. Validate | Canonical validator/admission tested. | None; rejection is visible. | Same graph bytes produce exact validation/admission receipt and errors map to nodes. |
| 8. Backtest | Backend and old UI tested; graph journey partly connected. | Controlled admitted fixture. | Current draft → exact admission → data → job → result → UI, deterministic reopen. |
| 9. Robustness | OOS/WF/optimisation/DSR/PBO exist; neighbourhood/Monte Carlo absent. | Demo only implemented methods and labels missing ones. | All required methods persist exact seeds/trials/folds and compare baseline honestly. |
| 10. Review result | Research evidence/review APIs/UI exist. | Current dense expert panel. | Precision Slate conclusion/evidence/rejection UI over real records. |
| 11. Activate monitoring | Old runner exists; no monitoring-only canonical assignment. | Mock owner demo only. | Monitoring service reloads same graph/snapshot without broker/execution cell. |
| 12. Generate signal | SignalEvent exists for old strategy. | No public V0 claim yet. | Exact transition semantics, restart/dedup/cooldown/staleness and explanation pass. |
| 13. Inspect context | Old signal list exposes z/slope; canonical context absent. | Show Unknown, never invented context. | UI links signal to graph/data/annotation/validity evidence. |
| 14. Review signal | Dedicated flow absent. | Research note is not substituted silently. | Append-only review state/note with owner privacy and analytics redaction. |
| 15. Reproduce later | Strong backend lineage, incomplete V0 journey. | None. | Clean process reconstructs strategy, data, research result, state and signal; first divergence reported. |

## Instrument-capability matrix

| Instrument/input | Historical backtest | Robustness | Live monitoring/signal | V0 decision |
| --- | --- | --- | --- | --- |
| NSE cash equities | Existing candle/backtest foundation; point-in-time corporate-action breadth needs audit. | Supported by generic pipeline after graph integration. | Zerodha read-only data. | Required. |
| NSE/BSE indices | Existing canonical instruments and candles for current seeds. | Supported once exact mappings/history pass. | Zerodha read-only data. | Required. |
| Futures | Backtest/lifecycle code exists; exact historical contract mapping remains gate. | Supported for captured/verified history. | Read-only quotes/context. | Required with declared contracts. |
| Options | Underlying/synthetic-premium and snapshot evidence exist; complete chain history absent. | Only exact captured chain datasets. | Chain/OI/IV/top-depth context. | Required with date/capability limits. |
| India VIX | No exact current integration found. | Unsupported until implemented. | Unsupported until provider mapping passes. | Required build item. |
| Five-level depth/order flow | No deep historical source; node math exists. | Captured-snapshot periods only. | Kite offers five levels, subject to terms/capability. | Required with prospective/captured labels. |
| Cross-market roles | Phase 5 scenario proves identities/resources, not real providers. | Fixture research only today. | Unproven. | Required for Benchmark F after exact mappings/data. |

## V0 golden five

The V0 set uses canonical A, B, D, E and F. Benchmark C remains V0.1/V1 because it
requires Dynamic Watchlists.

| Benchmark | Current maturity | V0 completion requirement |
| --- | --- | --- |
| A — reusable static equity | Phase 5 scenario proves one graph/roles/resources; backend backtest exists. | Accuracy-verified EMA/RSI/ATR versions, static bindings, graph-to-backtest/robustness/monitoring/review journey. |
| B — NIFTY cross-expiry IV/order flow | Architecture scenario and options/depth node contracts; picker/cache exist. | Exact current/next contracts, real/captured data capabilities, temporal routing, no fabricated history, research/signal only. |
| D — pre-open repricing recorder | No complete vertical found. | Licensed inputs, clock/session/availability truth, bounded warm recorder, restart, latency/gap receipt, no execution. |
| E — chart thesis confirmation | Product contracts absent; prototype visual only. | Chart licence, normalized annotations, lock/version, activation, explanation, signal and review; approval/order steps omitted from V0. |
| F — cross-market signal | Phase 5 scenario proves roles/resources only. | Real supported mappings/data/freshness/alignment and signal context; execution instrument becomes a separately observed target, not an order route. |

Additional owner strategies enter a `V0 Strategy Validation Pack` only after their
exact thesis, roles, data, parameters, costs, timeframes and expected refusal cases
are written. They use the same harness; no one-off evaluator is allowed.
