# CLAUDE.md

Guidance for Claude Code working in this repository.

## What this is

A single-user autonomous trading platform for Indian markets on live Zerodha Kite Connect data.
It runs the EMA50 + displacement (z-score) strategy across a portfolio of underlyings and, on
every qualifying signal, autonomously picks the contract, sizes the position, routes the order,
manages it to exit, and books P&L net of the full Indian charge stack.

**This trades real money.** Live execution was enabled 2026-06-29 and the **first real order was
placed 2026-07-13 09:30 IST**; running 24/7 on a Bangalore VPS since 2026-07-10; **72 real
trades** booked as of 2026-08-01 (net **−₹166.37**), every one of them `mode='live'` —
there are zero paper rows in production. The live order path (`LiveBroker`, `KiteOrderClient`,
`LiveExecutionKite`) is in production use — it is **not** untested and the next order is **not**
its first. Treat any change touching execution, sizing, or exits as a production change.

Two processes: FastAPI backend on **:8090**, Vite/React frontend on **:5173**. `:8000` is
deliberately left free for an unrelated analyst app in the parent repo.

**Product direction (2026-07):** near-term focus is equity + index on the **underlying**, not
stock-specific options. Options stay fully supported but drop to lowest priority and are treated
as index-only. This means the mature spot backtester now tests the actually-traded instrument
for the equity/index universe. Borne out by the book: 70 of 72 real trades are
`equity_intraday`, and production runs `max_open_positions=0`, which disables options entirely.

**Read the book before changing an exit.** Across all 72 trades, `TARGET` has fired **zero**
times: 45 exits were the owner closing manually (`RECONCILED_EXTERNAL_EXIT`, net +₹2,761) and
the bot's own exits net **−₹2,927**. The 2026-08-01 excursion sweep
(`docs/2026-08-01-exit-sweep.md`) shows why — the largest favourable excursion ever recorded
is 1.216% of notional against a 1.5% target. This is an entry-quality problem as much as an
exit one: the median trade travels further against you (0.427%) than for you (0.286%).

## Production divergence — read before assuming

**Corrected 2026-07-28.** This section previously claimed Workstream B (10 safety fixes) and
E0/E1 (P&L integrity + daily profit-lock) were *not* running in production. That was **false**
and it drove a week of decisions. Verified by md5 against the VPS: `runner.py`,
`risk_controls.py`, `charges.py`, `broker.py`, `equity_entry.py` and `analytics.py` are
byte-identical to the branch, and the live process (up since 07:00:28 IST) is running them.

**Updated 2026-08-01.** The build-provenance work of 2026-07-25→28 **is now deployed**, so the
paragraph that used to sit here — "`/api/health` does NOT yet report a commit" — is itself
stale and has been removed. Verified by measurement, not by prose:

```
$ curl -s localhost:8090/api/health
{"ok":true,"build":{"commit":"4e9f125","branch":"feat/exec-completeness",
 "deployed_at":"2026-08-01T06:59:50Z","deployed_by":"priyanshusaraf@…"},
 "status":"ok","loops":{"risk":{"age_seconds":0.41,"state":"ok"},
 "signal":{"age_seconds":null,"state":"idle"}},"markets_open":false}
```
Since `4e9f125` that command answers a second question too — not just *which* build is
running but *whether it is working* (see the readiness note under Conventions).

**So deployment state is now answerable in one command: `curl /api/health` and compare the
commit.** That is the intended workflow; checksum/symbol grepping is the fallback for a box
that predates provenance. **Never assert deployment state from prose in this file or any
doc** — that is exactly how the earlier error persisted for a week. Verify, then write down
what you verified, with the command and its output.

Note what the reported commit does *not* tell you: `runtime_config` overrides in the DB
shadow code defaults, so a deployed commit can be running with materially different
parameters than its source implies. Check the Settings screen — an override whose value
differs from the shipped default is now flagged amber.

Do not date a deploy from remote file mtimes: the deploy rsyncs with `-t`, so VPS timestamps are
the *Mac's* edit times, identical to the second. They say nothing about when a file landed.

**Live-state gap — FIXED `4c91e05`, DEPLOYED 2026-08-01 (`4e9f125`), effect NOT yet
observed.** Read that last clause literally. The fix is on the box, but its output could not
be checked on deploy day: the re-anchor only runs in live mode off cached Kite funds, and the
deploy was a Saturday with no valid token — so `_account_funds` was `None`, `capital_dict`
omitted `ledger_drift` entirely, and `/api/status` still reported the old
`equity = 49,833.63`. That is the expected shape of "could not measure", not evidence the fix
works or that it doesn't. **Verify on the next trading session, after Connect Kite:**
`ledger_drift` should appear in `/api/status` and sit near zero. The equity
curve was anchored to the synthetic ₹50,000 seed because the E0.2 auto-reanchor could only
fire on a ledger that had never traded, which production has done since 2026-07-13 — so the
path was unreachable from the day it shipped and the cockpit reported ₹49,833 against a much
smaller real account for three weeks. It now re-anchors **once a day, before the day's first
entry, with a flat book, only when actually adrift** (`should_reanchor` in
`engine/ledger_reconcile.py`), and `capital_dict` publishes `ledger_drift` so a lying ledger
shows a warning badge instead of being silent. (The verification is the one stated above —
next trading session, token valid.)

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
npm run typecheck    # tsc --noEmit
npm test             # vitest — 116 tests (settings docs, journal walkthrough, ledger domain)
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
| `backend/app/engine/event_risk.py` | scheduled-event blackout table (EIA releases, index weekdays, bullion expiry, earnings) — shared by engine, backtester and `/api/event-risk` |
| `backend/app/engine/retention.py` | telemetry retention; the money record is never pruned |
| `backend/app/backtest/exit_sweep.py` | replays real trades against candidate exit parameters (`scripts/exit_sweep.py`) |
| `backend/app/market_data/candles.py` | **THE** candle→signal-frame converter + validation (sort, de-dupe, envelope repair). `runner._to_df` and `backtest._candles_to_df` are thin aliases over it — they used to be byte-identical copies, so a data fix could land in one plane and miss the other |
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

Deeper detail: `docs/engineering/reference/engine-internals.md`. Operations, deploy, and going-live: `docs/operations.md`.
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
- **exits (equity_intraday), retuned 2026-08-01 from real excursion data:** stop 0.8%,
  target 1.5% — and the target is effectively INERT (see "Read the book" above). The lever
  that works is the give-back lock: `intraday_profit_lock_threshold` **150** (was 600) and
  `intraday_profit_lock_frac` **0.7** (was 0.3). **Both production overrides (450/0.3) were
  CLEARED 2026-08-01 on the owner's instruction, so the retuned lock is now live** — verified
  via `/api/settings`: `value=150.0/0.7, overridden=false`. This was gate (a) in the roadmap.

### Code default vs what production actually runs (measured 2026-08-01)

Do not read the defaults above as what the bot is doing. **Ten `runtime_config` overrides
differ from code defaults** — this file previously named three. Measured from
`/api/settings` on the VPS, not from prose.

**These are the owner's deliberate operating decisions, not drift, and not a defect list.
Leave them alone.** They are hand-set from live trading experience, and the code defaults
are the weaker information — several were chosen precisely because the default was wrong for
this account. When this table and `config.py` disagree, **the correct response is to update
the doc, never to "reconcile" the box.** Do not clear an override to make a shipped default
take effect without the owner explicitly asking for that specific key.

| key | code default | LIVE |
|---|---|---|
| `intraday_enabled` | `False` | **1** |
| `intraday_max_margin` | 7,000 | **10,000** |
| `intraday_purple_margin` | 10,000 | **14,000** |
| `intraday_max_positions` | 3 | **4** |
| `intraday_target_pct` | 0.03 | **0.015** |
| `intraday_purple_stop_loss_pct` | 0.015 | **0.01** |
| `intraday_purple_target_pct` | 0.045 | **0.025** |
| `intraday_lockstep_trigger_pct` | 0.03 | **0.015** |
| `intraday_entry_cutoff_minutes` | 25 | **60** |
| `max_daily_loss` | 5,000 | **2,000** |

Two consequences worth internalising. **`intraday_enabled` is `False` in code and true only
by DB row** — clearing that override would silently stop the segment that booked 70 of the
72 real trades. It is the single most load-bearing row in `runtime_config`. And **the
retuned 1.5% target lives only in the override**; the code default is still 0.03, so the
"retuned defaults" language above describes the stop and the lock, not the target.

Production also sizes ~40% larger than the documented defaults (10k/14k vs 7k/10k) — a
deliberate sizing decision. Any reasoning about position size from `config.py` alone will be
wrong; read the live value.
- **options: 1 lot, −30% / +60%** premium stop/target with a ratcheting stop that never
  loosens. The widely-copied "−35%" is stale everywhere it appears — `config.py:50` is
  `stop_loss_pct = 0.30`. Exception: positions with `entry_atr` set (i.e. `expanding_z_v4`)
  skip the premium trail entirely and use an ATR ratchet on the underlying spot.

## The agenda

**Work is organised into eight workstreams.** Read
[`docs/engineering/WORKSTREAMS.md`](docs/engineering/WORKSTREAMS.md) to find yours.

An implementation session should load **three things only**: `docs/ARCHITECTURE.md`, the
workstream document you are working in, and the documents of anything it lists under *Depends
on*. Not the roadmap, not the other seven workstreams. If your workstream document is missing
something you need, that is a defect in the document — fix it there rather than reading around
it.

| Document | When to read it |
|---|---|
| `docs/PROGRESS.md` | the one-page state: built, running, blocked, next |
| `docs/ARCHITECTURE.md` | always — the invariants that cross every workstream |
| `docs/engineering/WORKSTREAMS.md` | to find the right workstream |
| `docs/engineering/workstreams/WS-NN-*.md` | the whole agenda for one subsystem |
| `docs/ROADMAP.md` | only for cross-workstream sequencing and owner blockers |
| `docs/engineering/EXECUTIVE.md` | when changing an interface or sequencing across streams |
| `docs/rfcs/0001-component-ir.md` | the constitution |

Tick a box only with verified evidence, in the same commit as the work. Do not restate a
workstream's contents here — duplicating them into CLAUDE.md is how this file drifted out of
sync with reality before.

## Conventions & gotchas

- **Kite access tokens expire ~06:00 IST daily.** Re-auth via the **Connect Kite** button each
  morning; headless auto-login violates Kite ToS, so this is permanent, not a gap. The token
  lives in `backend/access_token.json` and is read live via `token_source` — no restart needed.
- Signals fire only on **completed candles** during market hours. Strategy is valid on 15m/30m
  only; per-instrument *live* interval may be 5/15/30/60m.
- **`runtime_config` DB overrides shadow code defaults.** Shipping a new default requires
  clearing the corresponding VPS override, or it silently has no effect. **There are ten of
  them, not the three this line used to name — the full measured table is in "Sizing rules"
  above.** Clear one with `POST /api/settings/reset {"key": ...}`, which also calls
  `refresh_params()` so the running engine picks it up without a restart. Never hand-edit the
  `runtime_config` table: the route is what keeps the live process in step with the row.
- **`backend/VERSION` is generated per-deploy and gitignored.** It is read once at boot
  (`app/core/version.py`), logged, exposed on `/api/health`, and stamped onto every `trades`
  row as `build_sha`. Absent in dev/test — that's normal. `build_sha` has **three**
  distinguishable values and the distinction is load-bearing: a SHA (identified build),
  `'unknown'` (a live process that could not read its `VERSION` — i.e. something deployed
  outside `deploy.sh`, worth chasing), and NULL (row predates the column, booked before
  2026-07-28, genuinely unattributable). Never collapse the last two. The ORM cannot write a
  NULL — passing `build_sha=None` still stamps `'unknown'` — so NULLs only ever come from the
  migration.
- **`/api/health` is a readiness probe as of 2026-08-01** — it used to be a liveness stub
  that returned 200 through both 2026-07 outages. It now answers **503** when the DB is
  unreachable, the engine loops are stopped, or the **fast risk lane** is stale (stops not
  firing = unmanaged real money). The signal lane is reported but never fatal: it
  legitimately stops beating overnight, and deploys run out of hours. Verdict logic is pure
  in `app/engine/readiness.py`; budgets are static `Settings` (`health_*_seconds`),
  deliberately NOT `runtime_config`-overridable, so no DB row can silence the probe.
  **Still check `GET /` too** — a broken SPA mount is invisible from here, which is exactly
  how the `.env` outage hid.
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
