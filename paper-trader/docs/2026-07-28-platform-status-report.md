# Autonomous Options & Equity Trading Platform — Status Report

*Generated 2026-07-28 · branch `feat/exec-completeness` · sources: `docs/ROADMAP.md`, `CLAUDE.md`, `docs/product-overview.md`, live VPS DB snapshot (`vps-snapshots/paper_trader-offload-20260723-094218.db`)*

---

## PART I — THE BUSINESS CASE

### 1. What it is, in one paragraph

A fully autonomous trading system for Indian markets. It ingests live Zerodha Kite data, runs a systematic trend-plus-displacement strategy across a curated portfolio of underlyings, and on every qualifying signal it independently picks the contract, sizes the position against real broker margin, routes the order, manages it to a disciplined exit, and books the result **net of the complete Indian charge stack** — brokerage, STT/CTT, exchange fees, SEBI turnover, GST, stamp duty. There is no human in the decision loop. The operator's only daily act is a broker re-auth and pressing **ARM**.

It has been running **24/7 on a Bangalore VPS since 2026-07-10**, and executing **real money since 2026-06-29**.

### 2. The problem it solves

Most semi-professional systematic setups are four disconnected tools: a charting platform signals, a spreadsheet backtests, a broker terminal executes, and a human stitches them together under time pressure. Edge leaks out at every seam — hesitation, slippage, inconsistent sizing, and untracked costs. Retail options traders in particular lose to a cost stack they never measure.

This closes the seam. One system, one strategy definition driving both the backtest and the live engine, one cost model applied everywhere, one paisa-exact ledger recording every decision.

### 3. What's genuinely differentiated

| # | Differentiator | Why a buyer should care |
|---|---|---|
| 1 | **Defense-in-depth safety architecture** | Paper mode isn't a toggle — the default data client *physically disables* every order endpoint and enforces a fail-closed route allowlist. Real trading requires four independent gates to align simultaneously, plus a per-session ARM that resets to disarmed on every restart. The most expensive class of error — an unintended real trade — is structurally hard, not merely discouraged. |
| 2 | **Provable live/backtest parity** | The trailing-stop ratchet and strategy math are shared and parity-tested between simulator and live engine. This attacks the #1 reason systematic results fail to reproduce: silent drift between what was tested and what trades. |
| 3 | **Net-of-everything accounting, reconciled to the paisa** | A headless dry-run asserts `cash == initial + realized − Σ(open entry_cost)` to the paisa on every build. Cost drag is where retail options edges die; this platform refuses to hide it. |
| 4 | **Transparent contract selection** | The system doesn't just signal — it picks the strike, and it *shows its work*: the full evaluated candidate table with OI, spread, IV, delta and per-contract pass/fail reasons. Full automation with full auditability. |
| 5 | **Full offline determinism** | The whole stack — engine, risk loop, exits, accounting — runs with no network and no broker under **1,100 automated tests**. Behaviour claims are demonstrable, not asserted. |
| 6 | **Live-editable operation** | Dozens of risk and strategy parameters change while the engine runs, no restart, effective on the next loop. |

### 4. Verified operating record

Real trades from the production database (snapshot 2026-07-23, covering 2026-07-13 → 07-22):

| Segment | Trades | Net P&L | Avg/trade | Winners |
|---|---|---|---|---|
| equity_intraday | 33 | **+₹417.40** | ₹12.65 | 13 / 33 |
| options | 1 | **+₹326.72** | ₹326.72 | 1 / 1 |

Exit-reason breakdown: `RECONCILED_EXTERNAL_EXIT` 15 (+₹1,522), `INTRADAY_SQUAREOFF` 12 (−₹229), `STOP_LOSS` 6 (−₹367), `STRATEGY_EXIT` 1 (−₹182).

**Read that honestly:** the book is profitable but the sample is ~10 sessions and tiny. More importantly, the distribution is diagnostic — **not one trade closed on `TARGET` or a managed profit-locking stop.** Winners are leaking out through end-of-day square-off rather than being captured by design. That's a known, root-caused tuning defect (Workstream C, below), not a mystery.

### 5. Honest position on edge

This is where the pitch has to stop selling. **The platform has not established a statistically verified, net-of-cost positive edge on options.** The mature backtester sweeps the *underlying*; the options engine trades *premium*. That validation gap is documented in the platform's own research notes as the single biggest hole in the story.

The near-term product direction resolves this pragmatically: **equity and index on the underlying is now the priority**, which means the mature spot backtester validates the actual traded instrument. Stock-specific options are deliberately deprioritized to index-only.

The correct framing for a buyer: **this is a rigorously engineered execution and research platform with a mature safety and accounting backbone. The engineering is proven. The economic thesis is on a defined, well-understood validation runway.**

---

## PART II — THE TECHNICAL ARCHITECTURE

### 6. Stack and scale

| Layer | Technology | Size |
|---|---|---|
| Backend | Python 3.13, FastAPI, SQLAlchemy, pydantic-settings | ~14,100 LOC across 78 modules |
| Research plane | Isolated Python package, own DB | ~2,450 LOC / 38 modules |
| Frontend | React + TypeScript + Tailwind + shadcn/radix, `lightweight-charts` | ~5,400 LOC / 41 files, 13 views |
| Persistence | SQLite (WAL), 18 tables | prod DB ~45 MB |
| Tests | pytest, all offline/mock | **933 backend + 167 research = 1,100** |
| Deployment | systemd on a DigitalOcean Bangalore droplet, Tailscale-only UI | 1 GB (undersized — see risks) |

### 7. The engine — two cooperative loops

`EngineRunner` (`backend/app/engine/runner.py`) is the brain. `main.py`'s lifespan launches two async lanes serialized by one lock over a shared DB session:

- **Signal loop (~2.5 s, slow lane)** — refresh runtime params → refresh real broker funds → reconcile orphaned/external positions → `scan_signals()` on *completed candles only* → `process_entries()` → sweep the option-chain research cache → overnight square-off / gap guard → snapshot equity.
- **Risk loop (~1 s, fast lane)** — `mark_and_exit_positions()`: mark to market, ratchet the trailing stop, fire SL/TP. The blocking live-order poll runs via `asyncio.to_thread` so a slow broker response can never freeze position management or the WebSocket heartbeat.

The separation is the point: **a stalled broker call cannot delay an exit.** A staleness watchdog alarms if the fast lane falls behind.

### 8. Provider abstraction

The engine only ever touches the `MarketDataProvider` interface. `PT_PROVIDER` swaps between a synthetic mock market and live Kite with **zero engine changes** — which is exactly why the entire stack is deterministically testable offline. Kite sells quotes, candles, and the instrument dump; it does **not** sell IV or greeks, so those are computed locally via a self-contained Black-Scholes engine (`options/pricing.py`).

### 9. Safety model — four gates plus ARM

```
SafePaperKite        → subclasses KiteConnect, hard-disables every order/GTT/MF/convert
                       endpoint + fail-closed route allowlist in _request.
                       Any order attempt raises. This is the normal-operation client.
      ↓ requires ALL of:
PT_EXECUTION=live  ∧  PT_LIVE_ACK=I_UNDERSTAND_REAL_MONEY  ∧  PT_PROVIDER=kite
      ↓ then
LiveBroker           → real orders via LiveExecutionKite
      ↓ still gated by
ARM (per session)    → disarmed on EVERY process start; KILL disarms + flattens
      ↓ plus
daily-loss halt · order circuit breaker · ownership guard · adaptive routing
```

**Critical operational subtlety, documented and deliberate:** ARM gates *entries only, never exits*. The risk loop marks and flattens regardless of arm state — because not getting out is worse than any other failure. The consequence is a hard pre-live requirement: the persisted book must contain only positions the real account actually holds, or the engine will place real orders to flatten phantom rows.

### 10. Trading segments

**Options** (`options/picker.py`) — buys CE on long / PE on short. Screens the live chain for OI ≥ 500 and spread ≤ 3%, rejects empty or crossed books, then selects the strike whose delta is closest to 0.50. Fixed −35% / +60% premium stop/target with a ratcheting trailing stop that never loosens. Reinforcement without pyramiding: a fresh same-direction signal on an open winner tightens management rather than adding size.

**equity_intraday** (MIS, opt-in) — sized against **full real broker margin** (the 2.5× leverage cap was deliberately removed by the owner), hard cap of 3 concurrent, direction-aware SL/TP on spot, force-flat before close, never trailed or reinforced. Kept on an entirely separate code path so it can never complicate the options logic.

### 11. Execution intelligence

Order style adapts to live book conditions: tight and deep → market order; moderate or thin → marketable-limit capped at max slippage off mid; pathologically wide → skip the trade entirely. Protective exits always go to market. Limit prices snap to the real per-instrument tick size. This exists because for options, **execution cost — not brokerage — is the dominant friction.**

### 12. Supporting subsystems

- **Backtester** — sweeps the underlying across the liquid universe × six timeframes net of charges, in a background thread with a progress bar, caching each `(instrument, interval)` cell for instant reruns. Out-of-sample gate + minimum-trade threshold. Winners promote directly into the live portfolio. A **synthetic-premium path** (experimental) reconstructs approximate option premium from underlying candles, deliberately never using a bar's own future.
- **Trade journal** — a full multi-workbook journal subsystem (`app/journal/`) with a reverse-chronological day feed, notes, bias tracking, and per-day P&L.
- **Research plane** — a production-grade autonomous quant-research layer with its own DB, immutable experiment specs, and fail-closed import guards enforcing isolation from the trading engine. Includes a sandboxed strategy code generator (AST allow-list, no-builtins exec, gauntlet validation). **Currently dormant** (`PT_RESEARCH_ENABLED=0`) by owner decision.
- **Diagnostics** — per-lane heartbeats, ledger-drift alarm, single-instance lock, provider health, optional Telegram alerts on fills/exits/proximity.

### 13. Config layering

`config.py` (static pydantic `Settings`, every knob documented with a recommended default) → `.env` / `PT_*` env overrides → `runtime_config` DB table (live-editable from the Settings view, merged every signal-loop iteration). **Gotcha worth knowing:** DB overrides *shadow* code defaults, so shipping a new default requires clearing the corresponding VPS override.

---

## PART III — WHERE IT STANDS

### 14. Shipped and live

✅ 24/7 VPS engine, real-money armed daily · ✅ options + equity-intraday segments · ✅ full safety architecture · ✅ paisa-exact ledger · ✅ segment-aware charge model · ✅ backtest sweep + cache + promotion · ✅ shadcn cockpit, 13 views · ✅ trade journal v2 with multi-book support · ✅ three completed audit rounds' fixes · ✅ two production memory leaks root-caused and fixed (2026-07-23)

### 15. Just completed, awaiting deployment

**Workstream B — safety backlog (all 10 code items closed 2026-07-25, TDD, each defect reproduced RED first):**

| ID | Defect | Impact |
|---|---|---|
| E1 | A poisoned position key aborted the risk loop's mark/exit for the **whole book** | Worst of the set — silent, live |
| E3 | Options GTT stop divergence on a rejected trigger modify | Naked stop |
| E4 | A refused close reported as a phantom success | False state |
| E6 | The bot's own GTT fill mislabelled as an external exit | Corrupted analytics + false re-entry block |
| E7/E8 | Equity SHORT charged on wrong legs; `account_pnl` LONG-only sign | Misreported P&L |
| E9/E10 | Entry-LIMIT tick rounding; overnight flatten wrongly closing equity | Rejected orders / premature exits |

**Workstream E Phase 0–1 — P&L integrity (complete):** exits now book at the **true broker fill** rather than the last mark (owner evidence: a SENSEX put exited at +₹792 but recorded ~₹1,000); the equity curve auto-anchors to real broker equity instead of the synthetic ₹50k base; per-trade MFE/MAE telemetry landed; and a **daily profit-lock** now trails a high-water floor against peak deployed capital and flattens-plus-halts on give-back.

> ⚠️ **These fixes are committed but NOT deployed.** The live VPS process runs the old code until an rsync + `systemctl restart`. This is the single highest-value action available right now.

### 16. Queued — the forward roadmap

Priority order is **B (safety) → E (capital scaling) → C (exit tuning) → D (UI) → A (research, explicitly last)**.

**E2 — Index-futures segment.** Spec written and Opus-reviewed (`docs/2026-07-24-E2-index-futures-spec.md`, 13 TDD steps ready to execute). **Gated on owner action:** the paper SPAN margin is a flagged 12%-of-notional estimate and SENSEX `BFO_FUT` charges don't exist yet — a real Zerodha contract note is required to verify. Intraday-only, no rollovers ever, with a hard guard refusing any deliverable contract inside its physical-delivery window.

**E3 — MTF (Margin Trading Facility).** Pledged/funded delivery positions with broker interest accrual modelled into multi-day P&L. Most complex, spec-gated, built last.

**C-P2 — Exit-parameter sweep.** Now unblocked by the MFE/MAE telemetry. Root hypothesis already identified: `intraday_profit_lock_threshold` at ₹600 sits *above* the typical winner, so the tight lock never arms in the ₹0–600 band — which is precisely why zero of 33 trades closed on TARGET.

**D — UI typography and palette pass**, plus a never-performed 390px one-handed mobile check.

**A — Research plane activation (5 phases).** Honest statistics first (DSR deflation currently never engages; PBO unimplemented), then nightly shadow runs, then formula-level idea generation, then a reinforcement loop that learns which block families work on which instrument clusters, then regime conditioning.

### 17. What's missing — the candid list

**Correctness / validation**

1. **No verified net-of-cost edge on options.** The central open commercial question.
2. **Slippage telemetry doesn't exist.** Charges are modelled rigorously; realized slippage — the dominant options cost — is gated at entry but never measured and fed back.
3. **Charge rates are indicative,** flagged as needing verification against real contract notes. Blocks the futures build.
4. **Futures LTP isn't fetchable today** — marking to spot mis-prices by the basis. Needs a new provider method.
5. **Research statistics are broken where it counts:** `var_sr` defaults to 0 so deflation never engages; PBO is unimplemented; the optimizer objective is raw expectancy with no trade-count awareness.

**Engineering / operational**

6. **The deploy pipeline is a whole-tree rsync — the VPS has no git.** This has caused two separate production incidents: overwriting the VPS `.env` (dropping the frontend-serve config → every `GET /` 404 while health checks stayed green), and `rsync -a` as root stamping Mac uid 501 on directories so the deploy user couldn't create files. **RESOLVED 2026-07-28: `scripts/deploy.sh` now enforces the exclusion list, refuses dirty
   trees and market-hours deploys, never deletes without typed confirmation, and verifies
   `.env` + the built SPA + `GET /` + the reported build SHA after restart.** This is the most fragile part of the entire operation.
7. **1 GB droplet.** Two leaks already OOM'd it. A 2 GB resize is an open owner action.
8. **DB bloat, undecided:** `paper_trader.db` grows ~5 MB/day from unbounded append-only `option_data` (154k rows) / `signal_events` (86k) / `equity_snapshots` (72k). Retention, archive split, or moving time-series off SQLite — no decision made.
9. **No frontend test suite or linter at all.** `tsc --noEmit` is the only check. Several UI-side fixes are explicitly test-unverified.
10. **5 pending ESM security updates** require an OS reboot in a market-closed window.
11. **Manual daily broker re-auth** — headless auto-login would violate Kite's terms, so this is permanent, not a gap.
12. **Single-user, single-process, single-account by design.** Not multi-tenant, not horizontally scalable.
13. **Regulatory algo-registration / order tagging** under the Indian retail-algo framework is flagged to-confirm, not completed.

**Documentation drift (worth fixing before any external showing)**

14. ~~`CLAUDE.md` and `docs/product-overview.md` §6 both still state *"the live order path has never placed a real order."*~~ **FIXED 2026-07-28.** It was stale — 34 real trades exist in the production DB — and any buyer reading it got a materially wrong picture of maturity in both directions. Corrected in `docs/product-overview.md` (§1, §6, §7), `README.md`, `docs/STATUS.html`, `docs/architecture.md`, and dated correction banners added to `docs/deep-research-roadmap-2026-07-05.md` and `backend/POST-MARKET-order-retry-safety.md`.

---

## 18. Bottom line

**For the business reader:** you're looking at a system where the hard, unglamorous parts are genuinely done — safety that's structural rather than procedural, accounting reconciled to the paisa, 1,100 tests, and a real production track record on a live VPS. What isn't done is the proof that the strategy makes money at scale. That's a defined runway, not an unknown: slippage telemetry, exit-parameter tuning against real excursion data, and index-futures for capital scale.

**For the technical reader:** the architecture is disciplined — a hard provider seam that makes the whole stack offline-deterministic, two-lane loop separation so broker latency can't block exits, fail-closed guards at every boundary, and a research plane isolated behind enforced import rules. The weakest link is not the code, it's the **deploy mechanism**: whole-tree rsync to a git-less VPS with no `.env` exclusion has already caused two outages, and the safety fixes sitting on this branch are worthless until that rsync runs.

**The single most valuable next action** is deploying the completed B and E0/E1 work — currently 10 verified safety fixes and 3 real-money P&L-correctness fixes are written, tested, and *not in force in production*.
