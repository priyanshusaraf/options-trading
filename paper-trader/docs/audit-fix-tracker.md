# Pre-Live Audit — Fix Tracker

Source: `docs/pre-live-audit-2026-07-09-recovered.md` (26 CONFIRMED + 3 PLAUSIBLE).
Base commit: `301c628` (#21 tick-size fix). Branch: `feat/backtest-arbiter`.
Convention: TDD (test-first, watch fail, minimal impl, targeted tests green), one atomic commit per batch.
**Deploy is user-gated** — the live backend (PID running) is NOT restarted by this work.

Status key: ⬜ todo · 🔨 in progress · ✅ code-complete (tests green, committed) · 📐 design-staged (spec written, impl deferred)

## Batch 0 — Incident prevention (2026-07-09)
- ✅ `init_db(reset=True)` fails closed on non-mock providers — commit `060b152`. (Root cause of the live-DB reset incident; full pre-drop snapshot preserved at `backend/paper_trader.db.PREDROP-recovery-20260709-1230.db`; live restore pending user `kill 10256`.)

## Batch 1 — Security (API surface) — commit `deb67c8`
- ✅ C2 no auth on any REST/WS endpoint → token auth middleware + WS token
- ✅ H5 CORS `allow_origins=["*"]` → settings-driven origin allowlist
- ✅ C1 `manual_open` bypasses ARM gate → require armed

## Batch 2 — Reconcile safety
- ✅ C4 [commit 145f57a] `account_positions()` failure reads as flat → distinguish error from empty; skip orphan-close on failed/unauth read
- ✅ H14 (`4faf0bc`) startup reconcile → surface (not adopt) untracked real positions

## Batch 3 — Async / concurrency
- ✅ C5 (commit `d187a1c`) signal-loop entry runs sync on event loop → `asyncio.to_thread`
- ✅ H1 (`16e5034`) `/ws/instrument/{key}` sync Kite calls → asyncio.to_thread
- ✅ H11 (`b44058b`) config-mutating routes → ordered (enable-last/disable-first), lock-free

## Batch 4 — Order lifecycle
- ✅ C3 (commit `15ea775`) options late-fill never adopted → extend pending-adoption to options path
- ✅ H4 (commit `95da329`) stale `gtt_trigger_id` wedge → persist cancel before close order
- ✅ H8 (`7b2ed61`) KILL cancels working/timed-out entry orders
- 📐 H16 partial equity (MIS) close → see below (order-lifecycle; partial-close booking for equity)

## Batch 5 — Picker liquidity
- ✅ C8 (commit `37c9eb3`) zero bid/ask collapses `spread_pct` to 0 → reject empty-depth quotes

## Batch 6 — Durability / DB
- ✅ C7 (commit `ddb96bf`) two backends on one account → startup pidfile/flock guard
- ✅ H3 (`a38bf2e`) no rollback on exception → rollback both iterations
- ✅ H6 (`06a73e0`) startup lot-size repair corrupts partial fills → guard real partials
- ✅ H10 (`b2b1c61`) periodic ledger-drift alarm in the signal loop
- 📐 H13 persisted order journal → design in `audit-deferred-design.md`
- ✅ P1 substantially resolved by H3 (rollback) + P2 (busy_timeout); see `audit-deferred-design.md`
- ✅ P2 (commit `6ea0cc4`) SQLite `busy_timeout` → explicit 10s PRAGMA

## Batch 7 — Risk / config / robustness
- ✅ H7 (commit `6ea0cc4`) `get_candles()` uses server-local `now()` not IST → use `self.now()`
- ✅ H12 (`7325316`) position sizing fails closed when margins() unreadable
- ⬜ H15 `max_open_drawdown` ships disabled + disabled in live runtime → enable
- ✅ M1 (`e3f504f`) infra alerting on loop failure / stall → Telegram + log
- ✅ P3 (`e3f504f`) per-lane heartbeats + risk-lane staleness watchdog

## Batch 8 — Strategy / backtest validity (design-scope)
- 📐 C6 backtest models underlying → synthetic-premium design in `audit-deferred-design.md`
- 📐 H2 live trailing ≠ backtest ratchet → unify plan in `audit-deferred-design.md`
- 📐 H9 walk-forward / OOS gate → design in `audit-deferred-design.md`
