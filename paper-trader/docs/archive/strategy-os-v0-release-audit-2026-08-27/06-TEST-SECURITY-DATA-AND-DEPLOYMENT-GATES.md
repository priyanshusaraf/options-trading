# Tests, security, data and deployment gates

## Current verification evidence

| Command/scope | Directory | Result | Meaning |
| --- | --- | --- | --- |
| IR/editor selected pytest gate | `paper-trader/backend` | 851 pass, 1 skip | Current IR, editor, catalogue and Phase 5 scenarios remain green; does not prove indicator accuracy or UX. |
| Research/backtest selected pytest gate | `paper-trader/backend` | 325 pass | Backtest/OOS/WF/optimisation/PBO/DSR/cache/job foundations green. |
| Provider/signal/safety selected pytest gate | `paper-trader/backend` | 245 pass | Connection/vault/provider/watchlist/signal/options/tenancy/no-live test foundations green. |
| `npm test -- --run` | integrated frontend | 223 pass | Current UI unit contracts green. |
| `npm run typecheck` / `npm run build` | integrated frontend | pass/pass | Build succeeds; 800.94 kB minified JS warning. |
| Node 24 typecheck/build | Precision Slate | pass/pass | Static prototype compiles. |
| Node 24 root tests | Precision Slate | 954 tests pass; 4 files fail collection | Root Vitest config collects Playwright specs from nested worktrees; prototype not clean-gated. |
| Safe browser, mock/paper/temp DB | local ports 8090/15173 | graph/backtests/portfolio load; 34 successful API responses; no browser errors | Current app is locally usable but execution-centric, fixed-graph and not V0 profile. |
| Phase 5 full process | reviewed evidence | 7,290 pass, 166 skip | Broad current product regression at reviewed hashes. |
| Indicator accuracy | post-Phase-5 audit | 25 strict, 60 reject, 40 unverified; 2,500 prefix passes | Causal catalogue, insufficient numerical/semantic accuracy. |

Logs and screenshots are under `.agent/runs/strategy-os-v0-release-audit/`.

## V0 test matrix

### Strategy, graph and nodes

- Parse/validate/resolve/hash exact graph versions.
- Batch-edit only; no mutation of admitted versions.
- Complete verified-node allowlist and external mathematical oracles.
- Parameter/output/warmup/missing/undefined semantics.
- Prefix causality, batch/incremental parity, reset/restart snapshots.
- Safe custom Level 1/2 lineage; Level 3/4 unavailable.
- Graph layout/presentation changes never change strategy identity.

### Chart, annotations and replay

- Vendor artifact and normalized semantics remain distinct.
- Annotation serialization, owner scope and revision lifecycle.
- Fibonacci anchors/direction/ratios/derived values.
- Trendline/channel time-dependent equations.
- Locked-revision substitution and successor tests.
- Historical `as_of` hides future data; annotation affects subsequent events only.
- Save/load/tombstone/restore, chart-provider upgrade/rollback and structured keyboard
  alternative.

### Backtest and robustness

- Dataset/provider/truth/instrument/timeframe identity.
- Completed bars, warmup, sessions/timezones/resampling and missing/stale data.
- Next-bar fill timing, intrabar assumptions, charges/slippage and expiry identity.
- Deterministic result/cache reproduction.
- Locked OOS isolation and chronological walk-forward.
- Bounded optimisation, exact trials/seeds and PBO/DSR trial population.
- Parameter-neighbourhood stable-region and sensitivity evidence.
- Monte Carlo method, seed and reproducibility.
- Job admission/queue/cancel/retry/process-death/reclaim/finalization and quotas.

### Data and instruments

- Canonical mapping, token reuse, contract expiry, lot/tick/session truth.
- India VIX history/live alignment and gaps.
- Options chain window, IV/Greeks source, OI/volume/spread/freshness and captured range.
- Five-level depth shape, timestamps, duplicate/update behavior and storage bounds.
- No invented aggressor flow, historical depth or current-contract backfill.
- Provider disconnect, token expiry, reconnect, rate limits and partial capability.

### Monitoring and signals

- Same graph/version/data semantics as research.
- Monitoring-only assignment has no lease/capital/broker/order authority.
- Exact previous/target/transition, evaluation/data timestamps and dedup identity.
- Completed-bar, cooldown, stale, repeated-state and restart behavior.
- State snapshot/recovery and annotation/options/VIX/order-flow dependency gaps.
- Signal review ownership, append-only revisions and context links.

### Security and tenancy

- Signup/session/membership and cross-tenant IDOR for every V0 object.
- WebSocket owner scope and revoked-session behavior.
- Credential vault, tamper, rotation, revoke, error redaction and no browser secret.
- CSRF/CORS/CSP, request bounds, file/upload absence and log/analytics redaction.
- V0 route inventory proves every execution mutation absent/unreachable.
- Dependency/SBOM/licence and static secret scans.

### Frontend and operations

- Desktop golden path and 390×844 monitoring/review path.
- Keyboard, focus, screen-reader labels, zoom and reduced motion.
- Loading/error/empty/Unknown states; no false LIVE/healthy state.
- API/network/console evidence and bundle/interaction budgets.
- Product analytics redaction and event-schema tests.
- Clean build/install/config/migrations/health/backup/restore/restart/rollback.

## Explicitly deferred execution tests

Partial fills, live margin reservation, order rejection, broker reconciliation,
multi-broker failover, execution kill switches and portfolio-admission contention do
not gate public V0 behavior. Their existing suites remain regression protection.
V0 adds negative proofs that public users cannot invoke those paths.

## Security findings

1. Current startup defaults to an execution worker on local SQLite and public routers
   include execution mutations. V0 must use a distinct service/profile, not DISARM.
2. Current integrated frontend displays LIVE/ARM/KILL and real-account language.
3. Provider vault/tenancy tests are strong, but production key injection/rotation,
   beta administration, CSRF/CSP and incident response remain unproven.
4. Precision Slate accepts no credentials, but it also has no backend; its security
   posture cannot be transferred by visual adoption.
5. Strategy IP, chart artifacts, datasets and signal reviews need explicit retention,
   export/deletion and access policy.

## Data and licensing gates

### Zerodha

Official Kite Connect terms state that platform use is subject to exchange/SEBI
requirements, live market data cannot be displayed to the public at large, API/live
data redistribution is restricted, end-user platforms may require approvals, and
fully automated trading requires exchange approvals. The V0 questions are:

- Is per-user, authenticated, private display in a paid research product approved?
- May the product persist option/depth snapshots and for how long?
- Which app/API plan and written platform approvals are required for 5–15 users?
- Which audit logs and retention periods apply?
- Can V0 request only read-only market-data capability?

Source: <https://kite.trade/terms/> and <https://kite.trade/docs/connect/v3/>.

### Charting

Current Lightweight Charts is Apache-2.0 and lacks built-in drawings/indicators.
TradingView Advanced Charts requires approved private-repository access, is not
redistributable, and its free availability is described for public implementations
with attribution, not private/paywalled use. Obtain written commercial clarification
before using it for paid V0. Proprietary bytes stay outside the public repository.

Source: <https://www.tradingview.com/charting-library-docs/latest/getting_started/quick-start/>
and <https://www.tradingview.com/charting-library-docs/latest/introduction/>.

### Product positioning and counsel checklist

No legal conclusion is made. Counsel must assess:

- whether user-defined BUY/SELL/EXIT/HOLD computation and paid monitoring cross
  Research Analyst or Investment Adviser boundaries;
- whether platform templates, presets, house strategies or performance rankings
  change that analysis;
- registration/disclosure rules for public recommendations or appearances;
- backtest/performance presentation, derivatives risk and ₹500 paid access;
- DPDP/privacy, credential handling, retention/export/deletion and breach response;
- Zerodha/exchange platform and data terms;
- chart-provider commercial licence and attribution.

Source anchor: SEBI Research Analysts Regulations, last amended 16 December 2024,
<https://www.sebi.gov.in/legal/regulations/dec-2024/securities-and-exchange-board-of-india-research-analysts-regulations-2014-last-amended-on-december-16-2024-_90153.html>.

## V0 deployment topology to prove

```text
TLS edge
  → V0 API (no execution worker)
  → PostgreSQL execution-schema read/legacy preservation
  → PostgreSQL research schema
  → PostgreSQL ledger/journal schema where used
  → research workers
  → monitoring workers (no broker/order imports)
  → scheduler/outbox delivery
  → artifact storage
```

Redis is not required until measurement shows a hot-state need. Durable truth stays in
PostgreSQL/object storage.

## Deployability gates

| Dimension | Required V0 evidence | Current state |
| --- | --- | --- |
| Build | Reproducible backend/frontend artifacts, pinned dependencies, SBOM and build ID. | Partial; local builds/CI, no V0 artifact. |
| Configuration | V0 profile, secret-backed vars, production refuses mock/SQLite/execution ambiguity. | Missing V0 profile. |
| PostgreSQL | Supported PG16, least-privilege V0 roles, pools/TLS and exact heads. | Local contracts only. |
| Migrations | Clean install and upgrade from accepted 0041/0011, restart and stale refusal. | Existing contracts, new V0 migrations unknown. |
| Backup/restore | Encrypted retained plan, clean restore, row/PK/digest/sequence and measured RPO/RTO. | Local tools; no V0 production evidence. |
| Services | API/research/monitor/scheduler roles, ordering, restart/graceful shutdown. | Packaging foundation only. |
| Health | Build, heads, DBs, workers, provider, queues, frontend; no false green. | Current health is too narrow. |
| Security | TLS, exposure, roles, rotation, audit, CSRF/CSP and incident controls. | Open. |
| Observability | Logs/metrics/alerts/retention, provider/jobs/db/backup failures. | Logs/health only. |
| Capacity | 5–15 user quotas for data, jobs, subscriptions, cache, disk and connections. | Unmeasured. |
| Rollout/rollback | Preflight, maintenance, previous build, forward repair and smoke. | Legacy deploy script only. |

Current highest claim remains `locally_runnable`.
