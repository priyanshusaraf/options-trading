# Live Trading, Configurable SL/TP & Telegram Alerts — Design Spec

**Date:** 2026-06-20
**Status:** Draft for owner review
**Context:** The platform currently runs the EMA50+z-score strategy on **live Kite
market data** but **simulates every fill** (`PaperBroker`) and structurally
forbids real orders (`SafePaperKite`). The owner wants: (1) real-money automated
execution, (2) configurable stop-loss/take-profit (global + per-position),
(3) cheap notifications when a position nears its SL/TP.

Six correctness/safety bugs found in pre-work review are **already fixed**
(commit `6023e04`): SL/TP overrides reaching entries (C1), airtight order lock
(C2), cross-thread DB race (C3), zero-premium stop suppression (C4), multi-day
overnight re-evaluation (H1), runtime override validation (H2).

This spec covers three phases. **Phases 1–2 ship value immediately and run in the
current paper mode.** Phase 3 (real money) is the large, gated build and is
sequenced last.

---

## Phase 1 — Configurable SL/TP (global default + per-position)

### Goal
The owner sets a global default stop/target in Settings (done) AND can adjust the
stop and target on any individual open position from the Active Positions cockpit.

### What already works (Phase 0)
- `stop_loss_pct` / `target_pct` overrides now reach new entries (C1) and are
  bounds-validated (H2). Changing them in Settings applies to the next entry.

### New work
**Backend**
- New endpoint `POST /api/positions/{key}/sltp` (async, under the engine lock —
  same single-threaded-session guarantee as the close route). Body accepts either
  absolute prices or percentages of entry:
  `{ "stop_price"?: float, "target_price"?: float, "stop_pct"?: float, "target_pct"?: float }`.
- Validation: `0 < stop_price < target_price`; reject a stop above the current
  premium that would fire instantly *unless* the owner confirms; percentages
  bounded like the global ones.
- Interaction with the trailing stop: a manual stop sets a new **baseline**. The
  trailing ratchet only ever raises the stop, so `effective_stop = max(manual_stop,
  trailed_stop)`. A manual stop *below* the current trailed level is recorded but
  the ratchet keeps the higher protective level (document this clearly; owner can
  disable trailing per-position if they truly want a looser stop).
- Persist `manual_stop` / `manual_target` flags on the position so the engine
  doesn't let the next reinforcement silently override an owner-set target.

**Frontend (`ActivePositionsView.tsx`)**
- Each position row gets editable stop and target fields (number inputs) with a
  save button and inline validation feedback; the existing dist-to-stop/target
  badges stay.

### Tests
- Endpoint sets stop/target; rejects `target <= stop`; trailing still ratchets
  above a manual stop; a manual target survives a subsequent reinforcement.

### Effort: small (~½ day).

---

## Phase 2 — Telegram alerts (free)

### Goal
Push a phone notification when a position **nears** its SL or TP, plus on fill /
exit, so the owner doesn't have to watch the screen.

### Architecture
- New package `app/notify/`:
  - `telegram.py` — `send(text: str)` posting to the Telegram Bot API
    (`https://api.telegram.org/bot<token>/sendMessage`) via `httpx` (already a
    dependency). Reads `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` from env/`.env`.
    If unset → no-op (feature simply off). Network failures are caught + logged,
    never crash the engine.
  - `notifier.py` — a thin `Notifier` the engine holds; formats events into
    messages and dedupes/throttles. Injectable sender so tests use a fake (no
    network).
- **Events emitted:**
  - `OPEN` (fill), `CLOSE` (exit reason + net P&L), `STOP_LOSS` / `TARGET` hit.
  - **Approaching SL/TP** — evaluated in the fast risk loop
    (`mark_and_exit_positions`): when the live premium enters within
    `alert_proximity_pct` of the distance to the stop or target, send **once** on
    entering the near-zone; re-arm when it leaves. Per-position alert state is kept
    in-memory on the runner (`{key: {"near_stop": bool, "near_target": bool}}`) so
    a 1-second loop doesn't spam.
  - `SIGNAL` fired — optional, behind a toggle (can be noisy).
- **Settings:** add to `runtime_config.OVERRIDABLE` + `BOUNDS`:
  `notify_enabled` (bool), `notify_on_signal` (bool), `alert_proximity_pct`
  (float, default 0.15, bounds 0.01–0.90). Surfaced in the Settings UI with a new
  "Notifications" group.
- **Setup doc:** README section — create a bot via @BotFather, get the token, get
  your chat id (message the bot, read `getUpdates`), put both in `.env`.

### Tests
- Message formatting for each event; proximity detection fires once on entering
  the near-zone and re-arms on leaving; `send` is a no-op (and never raises) when
  no token is configured; a fake sender records calls.

### Cost: ₹0. Effort: small (~½–1 day).

---

## Phase 3 — Real-money automated execution (gated, incremental)

> **This is the high-risk build.** It introduces the first code path that can move
> real capital. It ships behind explicit flags, defaults OFF, and is rolled out in
> stages with a kill switch and tiny size. Nothing here weakens the paper default.

### 3.0 Safety model (non-negotiable invariants)
- `SafePaperKite` remains the **default** client. A real-order client is only
  constructed when BOTH `PT_EXECUTION=live` and an explicit acknowledgement flag
  (e.g. `PT_LIVE_ACK=I_UNDERSTAND_REAL_MONEY`) are set. Absent either → paper.
- The live client has its **own narrow allowlist** that adds exactly
  `order.place`, `order.modify`, `order.cancel` (and `gtt.place`/`gtt.modify`/
  `gtt.delete` if the GTT option is chosen) on top of the read-only routes —
  nothing else.
- A **kill switch** (UI button + `POST /api/execution/kill` + a sentinel file
  the engine checks each loop) that: blocks new entries, optionally squares off
  all open positions at market, and flips execution back to paper.
- **Guardrails enforced in code, not discipline:** 1 lot only (initially), a
  configurable max open positions, a **max daily realized loss** that halts new
  entries for the day, and a per-order margin pre-check.

### 3.1 Components
- **`LiveKite`** (new): KiteConnect subclass with the narrow order allowlist; used
  for both data and orders when live.
- **`LiveBroker`** (new): same interface as `PaperBroker`
  (`open_position`/`close_position`/`mark`/`reconcile`) so the runner is unchanged.
  - `open_position` → place a real **BUY**, poll order status to COMPLETE /
    REJECTED / partial, record the **actual** average fill price and filled qty,
    then mirror into the local ledger (for analytics + reconciliation).
  - `close_position` → place a real **SELL**, poll, record actuals.
  - Order lifecycle: handle REJECTED (insufficient margin, circuit limit,
    illiquidity), partial fills, and timeouts; never double-place (idempotency via
    a client order tag + status check before retry).
- **Reconciler**: on startup and on a cadence, fetch real Kite positions/holdings/
  funds and compare to the local ledger; on mismatch → alert (Telegram) + halt
  entries.
- **Margin pre-check**: use the already-allowlisted `order.margins` calculator
  before placing.

### 3.2 SL/TP on the exchange — **KEY DECISION (D1)**
Three options:
- **(a) Bot-managed** (reuses today's logic): the risk loop fires a market SELL on
  SL/TP. Pro: trailing + target work exactly as in paper. Con: if the bot
  crashes/disconnects, the position is unprotected.
- **(b) Exchange GTT**: place a Good-Till-Triggered stop at entry; modify as the
  trail ratchets. Pro: protection survives bot downtime. Con: GTT triggers on LTP
  (not guaranteed fill), single/OCO limits, frequent modifies for trailing.
- **(c) Hybrid (recommended)**: a GTT stop as a **safety net** at entry (survives
  downtime) + bot-managed exits for trailing/target precision, reconciled so we
  never double-exit. Most robust, most work.

### 3.3 Order type — **KEY DECISION (D2)**
- **Market** (recommended for liquid ATM options the picker already filters to:
  OI ≥ 500, spread ≤ 3%) — fills reliably; small slippage. Mitigation: a
  marketable-limit (cap slippage) variant.
- **Limit** — price control but may not fill; risks missing the move.

### 3.4 Rollout (each stage gated on the prior proving clean)
1. **Shadow mode**: live path computes the exact order it *would* place + runs the
   margin check, logs/alerts it, but still paper-fills. Validates order
   construction with zero money at risk.
2. **Pilot**: ONE instrument (e.g. NIFTY weekly ATM), **1 lot**, kill switch armed,
   max-daily-loss set, owner supervising a live session.
3. **Expand**: more instruments / size only after N sessions of clean
   reconciliation.

### 3.5 Guardrails — **KEY DECISION (D3)**
Confirm: 1-lot pilot, one-instrument start, max-daily-loss halt value, max open
positions, kill switch behavior (square-off-all on kill: yes/no).

### 3.6 Real-world constraints (designed around, not hidden)
- Kite Connect is a **paid** subscription; live orders need the daily OAuth token
  (the owner initiates auth each morning — headless auto-login violates Kite ToS,
  per the existing README).
- Automated personal-API order placement carries **SEBI / broker ToS**
  responsibility that rests with the owner; the kill switch + supervision are part
  of operating it responsibly.

### Tests (never touch the real exchange)
- Order-payload construction; status-poll state machine (complete/reject/partial/
  timeout); idempotent retry; reconciliation mismatch → halt; kill switch blocks
  entries and (optionally) squares off; margin-reject path. All against a **fake
  Kite order API**.

### Effort: large (multi-day, staged). Phase 3 gets its **own** implementation
plan after this spec is approved; Phases 1–2 can start immediately.

---

## Sequencing
1. **Phase 1** (per-position SL/TP) — small, paper-safe, immediately useful.
2. **Phase 2** (Telegram alerts) — small, paper-safe, the owner's "tell me when
   I'm near SL/TP" ask.
3. **Phase 3** (live execution) — gated, shadow-first, 1-lot pilot, kill switch.

## Open decisions for owner sign-off
- **D1** — SL/TP-on-exchange mechanism: bot-managed / GTT / **hybrid (rec.)**.
- **D2** — order type: **market (rec.)** / limit / marketable-limit.
- **D3** — guardrails: confirm 1-lot pilot, one instrument, max-daily-loss value,
  kill-switch square-off-all yes/no.
