# CLAUDE.md

Guidance for Claude Code working in this repository.

## What this is

A single-user autonomous trading platform for Indian markets on live Zerodha Kite Connect data.
It runs the EMA50 + displacement (z-score) strategy across a portfolio of underlyings and, on
every qualifying signal, autonomously picks the contract, sizes the position, routes the order,
manages it to exit, and books P&L net of the full Indian charge stack.

**This trades real money.** Live execution was enabled 2026-06-29 and the **first real order was
placed 2026-07-13 09:30 IST**; running 24/7 on a Bangalore VPS since 2026-07-10; **50 real orders
and 34 real trades** booked as of the 2026-07-23 snapshot, every one of them `mode='live'` —
there are zero paper rows in production. The live order path (`LiveBroker`, `KiteOrderClient`,
`LiveExecutionKite`) is in production use — it is **not** untested and the next order is **not**
its first. Treat any change touching execution, sizing, or exits as a production change.

Two processes: FastAPI backend on **:8090**, Vite/React frontend on **:5173**. `:8000` is
deliberately left free for an unrelated analyst app in the parent repo.

**Product direction (2026-07):** near-term focus is equity + index on the **underlying**, not
stock-specific options. Options stay fully supported but drop to lowest priority and are treated
as index-only. This means the mature spot backtester now tests the actually-traded instrument
for the equity/index universe. Borne out by the book: 33 of 34 real trades are `equity_intraday`.

## Production divergence — read before assuming

**Corrected 2026-07-28.** This section previously claimed Workstream B (10 safety fixes) and
E0/E1 (P&L integrity + daily profit-lock) were *not* running in production. That was **false**
and it drove a week of decisions. Verified by md5 against the VPS: `runner.py`,
`risk_controls.py`, `charges.py`, `broker.py`, `equity_entry.py` and `analytics.py` are
byte-identical to the branch, and the live process (up since 07:00:28 IST) is running them.

What genuinely is **not** deployed is the build-provenance + test-isolation work of 2026-07-25→28:
`main.py`, `core/config.py`, `core/version.py`, `db/models.py`, `db/session.py`,
`engine/broker_factory.py`, `conftest.py`. So **`/api/health` does NOT yet report a commit** — it
returns bare `{"ok":true}`, there is no `VERSION` on the box, and `build_sha` is not being
stamped. Until that ships, deployment state must be established by checksum or symbol grep
against the VPS. **Never assert deployment state from prose in this file or any doc** — that is
exactly how this error persisted. Verify, then write down what you verified.

Do not date a deploy from remote file mtimes: the deploy rsyncs with `-t`, so VPS timestamps are
the *Mac's* edit times, identical to the second. They say nothing about when a file landed.

**Known live-state gap:** the equity curve is anchored to the synthetic ₹50,000 seed and the E0.2
auto-reanchor cannot fire on a ledger that has ever traded (its guards require zero `Trade` rows).
Production reported ₹50,744 while the real Zerodha account net was ₹14,236–₹27,441 — roughly a 2×
overstatement. Treat reported equity as untrustworthy until that is fixed.

## Hard invariants

These must hold. Do not weaken any of them without an explicit instruction naming the invariant.

1. **The ledger reconciles to the paisa:** `cash == initial + realized − Σ(open entry_cost)`.
   `scripts/dryrun.py 700` asserts it. Keep it green.
2. **ARM gates entries only — never exits.** `mark_and_exit_positions` (risk loop) marks every
   open position and fires SL/TP/square-off regardless of arm state; the gate lives in
   `process_entries`. Not getting out is worse than any other failure. Consequence: the persisted
   book must contain only positions the real account actually holds, or the engine will place
   real orders to flatten phantom rows.
3. **Paper-by-default is structural, not procedural.** `SafePaperKite` hard-disables every
   order/GTT/MF/convert endpoint and enforces a fail-closed route allowlist in `_request`. Live
   requires `PT_EXECUTION=live` ∧ `PT_LIVE_ACK=I_UNDERSTAND_REAL_MONEY` ∧ `PT_PROVIDER=kite`,
   then a per-session ARM that resets to disarmed on every process start.
   **Note the shipped `backend/.env` satisfies all three** — the fallback is paper, the
   configuration is live. `SafePaperKite` is the *data* client; it does not gate
   `LiveExecutionKite`, which is what actually places orders.
4. **Live/backtest parity.** The trailing-stop ratchet and strategy math are shared and
   parity-tested between simulator and live engine. A change to one must land in both.
5. **The research plane stays isolated.** `research/guards.py` stays fail-closed; read-only
   bridges only; `PT_RESEARCH_ENABLED=0` until Workstream A opens.
6. **Deploys go through `scripts/deploy.sh`.** Never bare-rsync to the VPS. A bare rsync has
   already clobbered the production `.env` and caused an outage, and `rsync -a` as root caused
   a second one by stamping uid 501 onto remote directories.

## Commands

Run from `backend/` or `frontend/` — never the repo root.

**Backend** (`backend/`)
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env                          # set PT_PROVIDER, KITE_API_KEY, KITE_API_SECRET
.venv/bin/uvicorn app.main:app --port 8090    # --reload for dev
```

**Frontend** (`frontend/`)
```bash
npm install
npm run dev          # :5173, proxies /api + /ws to :8090
npm run typecheck    # tsc --noEmit — there is NO test suite or linter on the frontend
npm run build
```

**Tests & headless proofs** (`backend/`) — pytest configured with `pythonpath=.`, `testpaths=tests`.
Never dump a full run into context; write to a file and read the failures.
```bash
.venv/bin/python -m pytest -q --tb=short > /tmp/pt.log 2>&1; grep -A5 FAILED /tmp/pt.log
.venv/bin/python -m pytest tests research_tests     # BOTH suites — see note
.venv/bin/python -m pytest tests/test_picker.py     # one file
.venv/bin/python -m pytest -k allocator             # by name
.venv/bin/python scripts/dryrun.py 700              # engine + ledger reconciliation
.venv/bin/python scripts/backtest_smoke.py          # sweep + net-of-charges invariant
```
`testpaths = tests` means **bare `pytest` does NOT run `research_tests/`** — name both suites
explicitly when you need full coverage. `scripts/deploy.sh` runs both.
Both headless scripts force the mock provider — no Kite, no network.

**`.env` is not read at all during a test run.** `Settings.model_config` sets `env_file=None`
whenever `pytest` is in `sys.modules` (`config.py:_env_file_for_this_process`). This is the
primary isolation control and it is an *allowlist*: under pytest the only config sources are
defaults and what a test sets explicitly. Forcing individual vars was a denylist that left
`KITE_API_KEY`/`KITE_API_SECRET` resolving from `.env`, and would have silently exposed every
setting added later. `PT_DISABLE_DOTENV=1` gets the same isolation outside pytest.

**Test-env safety otherwise lives in `backend/conftest.py` (the rootdir conftest), never
deeper.** It forces `PT_PROVIDER=mock`, `PT_EXECUTION=paper`, empty `PT_LIVE_ACK` and a
per-run temp `PT_DB_PATH` before any `app.*` import; a session fixture verifies the *resolved*
Settings. It has to be at the root: the shipped `.env` satisfies all three live gates and
points at the real ledger, so any suite root without the guard resolved to live execution
against production. `PT_LIVE_ACK` is set **empty, not deleted** — pydantic-settings falls back
to `.env` when an OS var is absent. `make_broker()` additionally raises if it ever resolves a
real `LiveBroker` while `PYTEST_CURRENT_TEST` is set. Do not add env forcing to a subdirectory
conftest, and keep the denylist as backup rather than deleting it.

**Deploy** (from `paper-trader/`) — see `docs/operations.md`
```bash
scripts/deploy.sh                       # normal deploy
scripts/deploy.sh --dry-run             # show what would transfer, change nothing
scripts/deploy.sh --force-market-hours  # deploy inside the trading session
scripts/deploy.sh --prune               # also delete remote-only files (asks first)
```
It refuses during market hours and on a dirty tree. There is deliberately **no** dirty-tree
override: a `-dirty` SHA in `trades.build_sha` is untraceable, which defeats the column.
It also **builds the SPA locally** (`npm run build`) and ships `frontend/dist/` in a separate
targeted rsync. Never build on the VPS — it is a 1GB droplet that has OOM'd twice with the
engine running, and a Vite build there can take live positions down with it.

## Repo map

| Path | What lives there |
|---|---|
| `scripts/deploy.sh` | the only sanctioned deploy path; writes `backend/VERSION` |
| `backend/app/engine/runner.py` | `EngineRunner` — the two cooperative async loops (signal ~2.5s, risk ~1s) |
| `backend/app/engine/equity_entry.py` | equity_intraday entry + `_mark_exit_equity`, deliberately separate from options |
| `backend/app/engine/charges.py` | Zerodha segment-aware charge model — rates indicative, verify vs contract notes |
| `backend/app/engine/analytics.py` | equity curve, signal counts — must aggregate in SQL, never load full tables |
| `backend/app/providers/` | `MarketDataProvider` seam; `safe_kite.py`, `factory.py` (process-wide singleton) |
| `backend/app/options/` | `picker.py` (OI ≥ 500, spread ≤ 3%, delta ≈ 0.50), `pricing.py` (local Black-Scholes) |
| `backend/app/strategy/registry/` | drop-in strategies; auto-discovered by module-level `STRATEGY`; default `trend_impulse_v3` |
| `backend/app/backtest/` | underlying sweep, background thread, per-`(instrument, interval)` cache |
| `backend/app/core/` | `config.py` (static `Settings`) + `runtime_config.py` (DB-backed live overrides) + `version.py` (build stamp) |
| `backend/app/db/` | SQLAlchemy models; `init_db(reset=...)` resets **only** in mock mode |
| `backend/app/api/` | `routes.py` (REST + both WebSockets), `backtest_routes.py` |
| `backend/app/ws/manager.py` | broadcast hub — coalescing, bounded deques, per-client sender tasks |
| `frontend/src/` | React + TS + Tailwind; `state/LiveContext.tsx` holds `/ws`; all REST via `lib/api.ts` |
| `research/` | isolated research plane, own DB, fail-closed import guards. Dormant. |

Deeper detail: `docs/architecture.md`. Operations, deploy, and going-live: `docs/operations.md`.
Incident post-mortems: `docs/incidents/`.

## Sizing rules (get these right — they moved recently)

- **equity_intraday: sized against real Zerodha margin, with NO leverage cap.** The
  `intraday_leverage` notional cap was **removed** on 2026-07-22 (`0f93f9a`); it survives only
  as the probe seed and as the paper/mock fallback when a live margin quote is unavailable.
  Do not reintroduce it as a binding cap. Chain: deployable cash is clamped by real
  `margins()["equity"]["available"]["live_balance"]` and **fails closed to ₹0** if funds can't
  be read → target margin per name `intraday_max_margin = 7,000` (purple names
  `intraday_purple_margin = 10,000`) → quantity from a real `kite.order_margins()` MARKET/MIS
  probe → skip below the `intraday_min_margin = 2,500` dust floor → leftover cash flows to the
  next name. Concurrency cap is **3 by default but 4 in production** (`runtime_config`).
- **options: 1 lot, −30% / +60%** premium stop/target with a ratcheting stop that never
  loosens. The widely-copied "−35%" is stale everywhere it appears — `config.py:50` is
  `stop_loss_pct = 0.30`. Exception: positions with `entry_atr` set (i.e. `expanding_z_v4`)
  skip the premium trail entirely and use an ATR ratchet on the underlying spot.

## The agenda

**`docs/ROADMAP.md` is the canonical, always-current agenda.** Read it at the start of every
session and work the topmost unchecked item of the highest active workstream. Tick boxes only
with verified evidence (tests green + the phase's stated acceptance), and update the tracker in
the same commit as the work.

Do not restate roadmap contents here — duplicating it into CLAUDE.md is how this file drifted
out of sync with reality before.

## Conventions & gotchas

- **Kite access tokens expire ~06:00 IST daily.** Re-auth via the **Connect Kite** button each
  morning; headless auto-login violates Kite ToS, so this is permanent, not a gap. The token
  lives in `backend/access_token.json` and is read live via `token_source` — no restart needed.
- Signals fire only on **completed candles** during market hours. Strategy is valid on 15m/30m
  only; per-instrument *live* interval may be 5/15/30/60m.
- **`runtime_config` DB overrides shadow code defaults.** Shipping a new default requires
  clearing the corresponding VPS override, or it silently has no effect. Production currently
  overrides `intraday_max_positions` (4), `intraday_entry_cutoff_minutes` (60), and
  `max_daily_loss` (2000).
- **`backend/VERSION` is generated per-deploy and gitignored.** It is read once at boot
  (`app/core/version.py`), logged, exposed on `/api/health`, and stamped onto every `trades`
  row as `build_sha`. Absent in dev/test — that's normal. `build_sha` has **three**
  distinguishable values and the distinction is load-bearing: a SHA (identified build),
  `'unknown'` (a live process that could not read its `VERSION` — i.e. something deployed
  outside `deploy.sh`, worth chasing), and NULL (row predates the column, booked before
  2026-07-28, genuinely unattributable). Never collapse the last two. The ORM cannot write a
  NULL — passing `build_sha=None` still stamps `'unknown'` — so NULLs only ever come from the
  migration.
- **`/api/health` is a liveness stub, not a readiness probe.** It returned 200 through both
  2026-07 outages. Never treat it as proof a deploy worked — check `GET /` too.
- `KITE_*` and `TELEGRAM_*` are deliberately **not** `PT_`-prefixed (`validation_alias`).
- When adding a tunable knob: add it to `Settings` *and* wire it through `runtime_config` if it
  should be live-editable.
- All P&L / equity / backtest figures are **net** of the full charge stack.
- Telegram is optional; blank creds = silently off.
- Commit and push only when asked. Working branch is a feature branch off `main`.

## Subagent rules

- Subagents must never run `git stash`, `git checkout -- .`, `git reset`, or anything else that
  mutates the shared working tree. Commit or explicitly hand off before dispatching.
- If a subagent produces no file writes after ~10 minutes, kill it and do the work directly.
- Prefer dispatching read-only subagents for codebase exploration; have them write findings to a
  file rather than returning long prose.
