# WS-07 — Infrastructure & Persistence

**Status:** active
**Owner surface:** `backend/app/db/` (`models.py`, `session.py`, `migrate.py`), `backend/migrations/`, `backend/app/core/config.py`, `backend/app/core/runtime_config.py`, `backend/app/engine/retention.py`, `backend/app/ws/manager.py`, `backend/app/market_data/candles.py`, `backend/app/providers/replay.py` (carved out of WS-02's `app/providers/`), `backend/conftest.py`
**Last verified:** 2026-08-03 · commit `cdbe686`

> Everything the trading engine stands on that is not the trading engine: the SQLite database
> and its schema history, how sessions and pooled connections are handed out and given back,
> the two-layer configuration system (static `Settings` plus DB-backed `runtime_config`
> overrides), telemetry retention on a 1 GB box, the WebSocket broadcast hub, validation at
> the market-data seam, replay mode, timezone correctness, and the test harness's isolation
> from production. Most of the load-bearing facts here were learned from outages, and the
> comments in these files are the post-mortems.

---

## 1. Vision

The substrate is boring and provably so. A database whose shape can be interrogated and
migrated rather than guessed at. Connections that cannot leak because the call site is not
given the option. A configuration system where the difference between "what the code ships"
and "what the box runs" is visible in one screen instead of being a trap. A file that does not
grow without bound on a machine with 134 MB free. Candles that are validated once, at the one
seam both the live plane and the backtest plane pass through. A clock that is correct
regardless of what timezone the host is set to. And a test suite that is deterministic and
structurally unable to touch production.

## 2. Scope

**In scope.**

- **Schema and migrations** — `app/db/models.py`, `app/db/migrate.py`, `migrations/versions/`,
  and the frozen legacy `_migrate_schema()` in `session.py`.
- **Sessions and connection hygiene** — `SessionLocal`, the engine's pool settings, SQLite
  PRAGMAs, `init_db(reset=...)`.
- **Configuration** — `Settings` (`core/config.py`) and `runtime_config` DB overrides
  (`core/runtime_config.py`): the `OVERRIDABLE` allowlist, `BOUNDS`, type coercion,
  `refresh_params()`.
- **Retention and DB bloat** — `engine/retention.py`, `scripts/prune_db.py`, `/api/storage`.
- **The WebSocket hub** — `app/ws/manager.py`.
- **Market-data validation at the data seam** — `app/market_data/candles.py`, the single
  converter both `runner._to_df` and `backtest._candles_to_df` alias, and the `FeedQuality`
  report it feeds.
- **Replay mode** — `app/providers/replay.py`, `PT_PROVIDER=replay`.
- **Timezone handling** — `now_ist()`, `ist_epoch`, `market_hours`, and
  `tests/test_timezone_independence.py`.
- **Test-harness isolation** — `backend/conftest.py` (rootdir) and `_env_file_for_this_process`.

**Out of scope.**

- What the parameters *mean* and whether a given override is a good trading decision:
  **WS-02 (Execution)**. WS-07 owns the mechanism by which an override reaches the engine, not
  the number.
- The deploy that carries a schema change to the box, the exclusion list that protects the DB
  files from the rsync, `/api/health`'s verdict logic and build provenance:
  **WS-06 (Deployment & Operations)**. WS-07 supplies two of the probe's inputs (DB
  reachability, feed anomalies); WS-06 owns the verdict.
- `research.db` and the research plane's own config/guards: **WS-03 (Research)**. Its isolation
  is by design — own DB, own settings, no capital-moving imports.
- The Component IR's schema and artefacts: **WS-01**.
- What the cockpit renders from any of this, including the Settings screen's amber
  overridden-value badge: **WS-08 (Cockpit UI)**.

## 3. Interfaces

**Exports**

| Export | Guarantee |
|---|---|
| `app/db/session.py:SessionLocal` | `expire_on_commit=False`. Sessions must be context-managed by the caller. |
| `app/db/session.py:engine` | `pool_pre_ping=True`, `pool_timeout=10`, `check_same_thread=False`; on connect: `journal_mode=WAL`, `synchronous=NORMAL`, `busy_timeout=10000`. |
| `app/db/session.py:init_db(reset=False)` | `reset=True` **raises** unless `provider == "mock"` — the last line of defence against a stray reset wiping the live book. `reset=True` disposes the pool before `drop_all`, and drops `alembic_version` too so a reset returns to the genuinely empty state. |
| `app/db/migrate.py:init_schema(...)` | Converges three DB states (empty / pre-Alembic / managed) onto head, non-destructively. Baseline is revision `0001` (2026-08-02). |
| `app/core/config.py:Settings` | Static config. `env_prefix="PT_"`; `KITE_*` and `TELEGRAM_*` deliberately unprefixed via `validation_alias`. `env_file` is `None` under pytest. |
| `app/core/runtime_config.py:effective()` | The merged, type-coerced parameter dict the engine reads. Only `OVERRIDABLE` keys are accepted; every numeric key is range-checked against `BOUNDS`. |
| `app/engine/retention.py:prune(now, policy)` | Idempotent; returns `{table: rows_removed}`. Touches only `option_data`, `signal_events`, `equity_snapshots`. A window of `0` or negative means **keep forever**, never "delete everything". |
| `app/engine/retention.py:vacuum()` | Rewrites the file and takes an exclusive lock. Caller owns the decision that the market is shut and the book is flat. |
| `app/market_data/candles.py` | **THE** candle→signal-frame converter and validator. No-op on clean data, pinned by a test asserting byte-identity with the old converter. Returns a report; `frame_from` builds the frame from an already-validated result so the hot path does not validate twice. |
| `app/ws/manager.py:manager` | Producers only ever enqueue and never touch client I/O. `state`/`position_ticks` coalesce latest-wins; everything else goes to a bounded per-client deque (`LOG_BUFFER=200`); a client that cannot accept a message within `SEND_TIMEOUT=10s` is evicted. |
| `app/providers/replay.py` | `get_candles` returns history up to and including the cursor and **not one bar further**. `now()` returns the recorded bar's timestamp. `is_authenticated()` is always `False`. |
| `backend/conftest.py` | Forces `PT_PROVIDER=mock`, `PT_EXECUTION=paper`, empty `PT_LIVE_ACK`, and per-run temp paths for **all three** databases before any `app.*` import; a session fixture verifies the *resolved* Settings. |

**Consumes**

| Consumed | From | Why |
|---|---|---|
| Provider candle payloads | WS-02 / providers | The thing validated at the seam. |
| `refresh_params()` call on settings write | WS-02 (engine runner) | How a cleared or changed override reaches the running engine without a restart. |
| `POST /api/settings/reset` route | WS-08 / API | The only sanctioned way to clear an override. |
| The signal lane's daily flat-book window | WS-02 | When retention is allowed to run. |

**Depends on:** nothing internal. WS-07 is a root of the dependency graph — WS-02, WS-03 and
WS-08 consume it, not the reverse. (An earlier draft declared a dependency on WS-02 "the engine
that calls into all of this"; that is a *consumer*, and declaring it as a dependency would put a
cycle in the graph.)
**Blocked by:** nothing inside this workstream. The 1 GB droplet constraint is WS-06 §8 and shapes decisions here but does not block them.
**Currently blocking:** nothing. Retention, session hygiene, feed validation, replay and the migration framework are all landed.

## 4. Completed

- **Versioned migrations — `0001` baseline, 2026-08-02.** Alembic now owns schema change.
  Revisions in `backend/migrations/versions/`: `0001_baseline_schema`,
  `0002_deployment_entity`, `0003_instrument_scoped_params`,
  `0004_strategy_version_provenance`. The old additive `ADD COLUMN` dict in `session.py`
  (`_migrate_schema`) is **frozen** — `tests/test_migrate_schema_frozen.py` fails the build if
  a column is added to it. It still runs, for exactly one job: carrying a pre-Alembic database
  (the owner's live `paper_trader.db`) up to the baseline, after which `init_schema` stamps
  `0001` and upgrades. The invariant that makes the empty-DB path (`create_all` + stamp head)
  and the migrated-up path safe to coexist is that they must produce *identical* schemas — not
  assumed, asserted column by column by `tests/test_schema_migrations.py`.
- **DB session hygiene — DONE + DEPLOYED 2026-08-01 (`4e9f125`), TDD.** Not minor:
  `_upsert_state` handed an **open** session to four callers that each ended with
  `s.commit(); s.close()`, so any raise in between skipped the close and leaked the pooled
  connection. Reproduced before fixing — a failed watchlist write left
  `engine.pool.checkedout()` at 1 instead of 0. It is now a `@contextmanager` that commits
  inside the block and closes structurally, so the four call sites cannot forget; committing
  inside also means a caller's in-memory bookkeeping only runs if the write landed. Added
  `pool_pre_ping=True` (a pooled handle can outlive its file — a predeploy restore, a
  `prune_db.py` VACUUM) and `pool_timeout=10` (from 30: a request that cannot get a connection
  in 10s just holds a worker thread while the pool is already exhausted). Tests:
  `tests/test_db_session_hygiene.py`, 9 including leak accounting, rollback, and "in-memory
  state must not advance past a failed write".
- **Retention / DB-bloat — DECIDED AND BUILT 2026-08-01 (`1e8b64f`).** The file had reached
  **108 MB** (`option_data` 319k, `signal_events` 169k, `equity_snapshots` 133k) growing
  ~5 MB/day, and the 2 GB resize is off the table — which settled the decision as *retention,
  not migration*. `engine/retention.py` ages telemetry out at 90d and **downsamples** the
  equity curve (7d full, then ~1 row/15 min) rather than truncating it, because the curve is
  the only long-run record of how the bot performed. **The money record — `trades`,
  `positions`, `order_journal`, `capital_state` — is never pruned**, with a test that says so:
  it is not regenerable and a missing row is an unrecoverable accounting hole. Runs daily from
  the signal lane with a flat book; `scripts/prune_db.py` does the one-off catch-up and the
  VACUUM; `/api/storage` makes growth visible in-app, which is what was actually missing.
- **Market-data validation at the data seam — DONE + DEPLOYED 2026-08-01 (`eb88d4e`).**
  Candles reached `strat.signals` completely unchecked through **two byte-identical
  converters** — nothing sorted them, de-duplicated them, or rejected a NaN close or an
  inverted high/low. Both are now thin aliases over `app/market_data/candles.py`, so a data fix
  cannot land in one plane and miss the other. **No-op on clean data, pinned by a test**
  asserting byte-identity with the old converter's frame — anything else would be a silent
  re-tuning of a live strategy. Repairs are limited to the unambiguous: sort, de-dupe (last
  copy wins, since Kite revises the newest bar), widen high/low to contain the bar's own
  open/close. Only missing/NaN/infinite or non-positive prices are dropped. The envelope repair
  was argued into existence by this repo's own fixtures — `test_backtest_ratchet_overlay.py`
  builds `(o=100.0, h=100.5, lo=98.5, c=97.9)`, a close below its own low. 31 tests.
- **Feed quality is VISIBLE — DONE + DEPLOYED 2026-08-01 (`2a8fcc8`).** The validator returned
  a report nothing consumed, so a broken feed would have been corrected silently every 2.5s
  forever. The live scan now validates once, builds the frame via `frame_from`, and records
  per-instrument anomalies in `FeedQuality`. They surface as `provider_feed` in `/api/health`
  and mark the probe **degraded, never unready** — the bars were repaired before any strategy
  saw them, so it is a reason to look, not to 503 and fail a deploy. Logging is throttled by
  anomaly **signature**: a repeating problem logs once, a changed one logs again, a recovered
  feed drops out of the report. 13 tests. **Still unmeasured live** — see §5.
- **Timezone audit — DONE 2026-08-01.** Measured: the production droplet is set to **IST**,
  while DigitalOcean droplets default to **UTC**. A rebuild or replacement of that box would
  come up 5.5 hours off and nothing in the codebase would notice — correctness rested partly on
  a machine setting. The core is genuinely host-independent (`market_hours` uses an explicit
  `+05:30` tzinfo, `now_ist()` is tz-aware, `ist_epoch` localises naive candle stamps as IST)
  and `tests/test_timezone_independence.py` runs that logic under `TZ=UTC`, `Asia/Kolkata` and
  `America/New_York` to keep it that way. **One real hazard found and fixed:** `broker.mark()`
  stamped `last_mark_time` from the provider's IST clock but **fell back to naive host-local**.
  On a UTC host those differ by 19,800s, and the mark-staleness guard compares them — a
  just-taken mark would read as stale, and `is_stale` suppresses SL/TP. A stop silently not
  firing on real money, triggered by nothing more than rebuilding the droplet. The fallback is
  now IST.
- **Replay mode — DONE 2026-08-01 (`468a984`).** `app/providers/replay.py` +
  `PT_PROVIDER=replay` re-runs a recorded session bar by bar against the real engine. **The
  property the whole thing rests on is no look-ahead:** `get_candles` returns history up to and
  including the cursor and not one bar further — a replay that leaked future bars would look
  like a perfectly successful replay while making the engine appear to decide things it could
  never have decided live. `now()` returns the recorded bar's timestamp, so market hours, the
  square-off deadline and every staleness check behave as they did on the day. **It
  structurally cannot trade:** `is_authenticated()` is always `False` and `make_broker()`
  refuses a real `LiveBroker` without an authenticated kite provider. It also refuses to price
  futures rather than inventing a basis. Format is deliberately boring JSON. 13 tests.
- **WebSocket hub rewrite — `68c852e`, 2026-07-23, deployed same day.** One of the two leaks
  behind the OOM: the old hub awaited each client's send inline (one slow client stalled the
  engine callbacks) and spawned a coroutine per log line via `run_coroutine_threadsafe`, so a
  stalled dashboard client made full-state snapshots pile up unboundedly (+100 MB/min RSS →
  1 GB VPS OOM → DB-pool collapse). See §7 for the second leak.
- **Test suite made deterministic — `3b2b752` and `c234e70` (2026-08-03).** See §6; this is the
  most recently-learned fact in this workstream.

## 5. Active roadmap

- [ ] **Measure `provider_feed` over a week of live sessions.** The mechanism is built and
      deployed; the question it exists to answer — does real Kite history actually contain
      duplicates, gaps or inverted bars — is unanswered. As of deploy it reported `{}` with the
      markets shut, which is "the scan has not run", not "the feed is clean". Check
      `/api/health` `provider_feed` and grep for `FEED_QUALITY`.
- [ ] **DB session hygiene — the broker's long-lived session (DELIBERATELY DEFERRED).** The
      other half of the 2026-08-01 item, split out rather than silently dropped. `broker.s` is
      long-lived **by design** and it is load-bearing: E0.2's auto-reanchor had exactly one
      correct implementation because the write must go through the broker's own session — an
      Opus review caught a first cut that used a separate session, where `expire_on_commit=False`
      left `broker.capital()` stale at ₹50k and the next `snapshot()` clobbered the re-anchor
      back to the synthetic base. Context-managing it is a real refactor of the ledger's identity
      map, not a hygiene tweak, and it should be done deliberately with the reanchor/snapshot
      regression tests in front of it. Trigger: a measured connection leak attributable to it.
- [ ] **Re-measure DB size after a month of retention** and confirm the daily prune is actually
      firing on the box (it needs a flat book). Evidence: `/api/storage` plus the file size.

## 6. Acceptance criteria

```bash
cd backend
.venv/bin/python -m pytest tests research_tests -q --tb=short > /tmp/pt.log 2>&1; grep -A5 FAILED /tmp/pt.log
.venv/bin/python scripts/dryrun.py 700     # must print LEDGER OK
```

Plus, for a change here:

- A schema change is an **Alembic revision** with the matching model change. Never a new entry
  in `_migrate_schema()` — `tests/test_migrate_schema_frozen.py` fails the build on that. The
  empty-DB and migrated-up schemas must still diff clean
  (`tests/test_schema_migrations.py`).
- A change to `candles.py` must keep the byte-identity pin green, or it is a silent re-tuning
  of a live strategy, not a data fix.
- A new tunable knob goes into `Settings` **and** is wired through `runtime_config` if it
  should be live-editable. A safety-probe budget goes into `Settings` **only** (see WS-06 §3).
- The ledger invariant `cash == initial + realized − Σ(open entry_cost)` stays green.

**Rules that are not negotiable:**

1. **`runtime_config` DB overrides shadow code defaults.** Shipping a new default silently has
   no effect until the corresponding override is cleared. **There are ten currently differing
   from defaults, and they are the owner's deliberate operating decisions — not drift, not a
   defect list. Leave them alone.** When the table and `config.py` disagree, the correct
   response is to **update the doc, never to "reconcile" the box**. `intraday_enabled` is
   `False` in code and true only by DB row — clearing it would silently stop the segment that
   booked 70 of the 72 real trades; it is the single most load-bearing row in the table. Clear
   an override only with `POST /api/settings/reset {"key": ...}`, which also calls
   `refresh_params()` so the running engine picks it up without a restart. **Never hand-edit
   the `runtime_config` table** — the route is what keeps the live process in step with the
   row. Do not clear a key without the owner explicitly asking for that specific key.
2. **`.env` is not read at all during a test run.** `Settings.model_config` sets
   `env_file=None` whenever `pytest` is in `sys.modules`
   (`config.py:_env_file_for_this_process`). This is the primary isolation control and it is an
   **allowlist**: under pytest the only config sources are defaults and what a test sets
   explicitly. Forcing individual vars was a denylist that left `KITE_API_KEY`/`KITE_API_SECRET`
   resolving from `.env` and would silently expose every setting added later.
   `PT_DISABLE_DOTENV=1` gets the same isolation outside pytest. The signal is deliberately
   `"pytest" in sys.modules` rather than a marker our own conftest sets — it holds for any test
   root, including one added later with no conftest of ours, which is exactly the failure mode
   that caused the incident.
3. **Test-env safety lives in the ROOTDIR `backend/conftest.py` and must never move deeper.**
   The shipped `backend/.env` satisfies all three live gates (`PT_EXECUTION=live`,
   `PT_LIVE_ACK=I_UNDERSTAND_REAL_MONEY`, `PT_PROVIDER=kite`) and points at the real ledger, so
   any suite root without the guard resolved to **live execution against production** — on
   2026-07-28 `pytest research_tests` alone did exactly that. `PT_LIVE_ACK` is set **empty, not
   deleted**: pydantic-settings falls back to `.env` when an OS var is absent, so
   `os.environ.pop()` does not unset it. All three DB paths are redirected, not just the
   execution one. `make_broker()` additionally raises if it ever resolves a real `LiveBroker`
   while `PYTEST_CURRENT_TEST` is set. Do not add env forcing to a subdirectory conftest, and
   keep the denylist as backup rather than deleting it.
4. **The suite was intermittent — 2 runs in 5 — until 2026-08-03. Two causes, both fixed; do
   not reintroduce either shape.** `test_init_db_guard.py` called `init_db(reset=True)`, which
   `DROP`s every table, against the **shared** per-run database. `DROP TABLE` needs an
   exclusive lock, and in WAL mode a single session left open anywhere in a ~2,500-test run
   holds a read transaction that outlasts the 10s `busy_timeout`. It always failed there and
   always took `test_health_endpoint.py` with it — those ERRORs were fixture setup against a
   half-dropped database, not defects of their own. Fixes: **(a)** `3b2b752` — that file now
   has its own database, which it should have had from the start; a test that wipes the schema
   out from under every other test was relying on collection order to stay benign. **(b)**
   `c234e70` — `init_db(reset=True)` now calls `engine.dispose()` before `drop_all`, releasing
   every *idle* pooled connection, which fixes the class at the source rather than one leak at
   a time. **A dispose cannot reclaim a connection that is still checked out by a live
   session** — so close your brokers in fixtures, or the lock is still held. (Related known
   hazard: `with TestClient(app)` starts the real engine lanes, so calling `scan_signals()`
   directly races them on the shared session.)
5. **Never dump a full test run into context** — write to a file and read the failures. And a
   backgrounded `cmd | tail` reports the *pipe's* exit code; use `backend/.venv/bin/python`,
   not bare `python`.

## 7. Known technical debt

- **`_migrate_schema()` is dead weight that cannot be deleted.** It is frozen and only serves
  databases written before Alembic existed. Cost: two migration mechanisms in the reader's
  head. Trigger to remove: confirmation that every live database has been stamped past `0001`
  (in practice, one box).
- **`_repair_open_position_lot_sizes()` runs on every `init_db`.** A one-off repair for a
  legacy one-unit-instead-of-one-lot bug, now permanent startup work with subtle guards (H6:
  never inflate a genuine partial fill to a full lot — that debits cash never spent and leaves
  a position the account cannot back). Cost: a mutation path on the money record that runs at
  every boot. Trigger: any change to partial-fill handling.
- **SQLite on a 1 GB box with WAL, one writer, and an API threadpool + a backtest thread.**
  `busy_timeout=10000` papers over contention rather than removing it. Retention keeps the file
  bounded; it does not make the concurrency model better. Trigger: a "database is locked" in
  production, or the file passing ~200 MB again.
- **The broker's long-lived session** — §5, deliberately deferred.
- **`/api/health` reports the commit but not the effective parameters.** A deployed SHA can be
  running materially different numbers because of `runtime_config`. Cost: any reasoning from
  `config.py` about live behaviour is wrong. Mitigated only in the Settings UI (amber badge on
  an overridden value). Owned jointly with WS-06.
- **The equity curve's history is now lossy past 7 days** by design (1 row/15 min). Anything
  that later wants sub-15-minute resolution on old data cannot have it. The trade was made
  knowingly against a 108 MB file on a box with 134 MB free.

## 8. Blockers

Nothing internal. Two external facts shape decisions here and are tracked in **WS-06 §8**:
the droplet is 1 GB and the 2 GB resize is declined for budget (which is *why* retention exists
rather than a data-store migration), and the box has a pending OS reboot.

Note also that **nothing on branch `feat/exec-completeness` is deployed** — the migration
framework, retention, session hygiene and feed validation entries above that are marked
DEPLOYED were deployed on 2026-08-01 as part of `4e9f125` / `1e8b64f` / `eb88d4e` / `2a8fcc8`;
work committed since then (including the Alembic baseline of 2026-08-02) is local. Verify with
`curl localhost:8090/api/health`, never from this line.

## 9. Future work

- **Move telemetry out of the execution database** (archive DB, or off SQLite entirely).
  Deliberately not scheduled — retention was chosen instead. Trigger: retention proving
  insufficient, or a second consumer of the time-series.
- **Record real sessions routinely for replay.** Replay mode exists; there is no capture
  routine. Trigger: the first live day surprising enough to want to re-run.
- **Narrow `OVERRIDABLE`.** It is large, and every key in it is a way for a DB row to change
  live behaviour. Trigger: an incident traced to an override nobody knew was settable.
- **Make the effective-parameter set part of the health payload**, so "what is running" is one
  question rather than two. Trigger: the next time a deployed SHA is misread as describing
  behaviour.
- **Connection-leak accounting in the readiness probe** (`engine.pool.checkedout()` as a
  degraded check). Trigger: a second leak of the `_upsert_state` shape.

---

## Rules for this document

- It is the **only** thing an implementation agent should need to read for this workstream,
  besides `CLAUDE.md` and its declared dependencies.
- Anything in §3 is a contract. Changing an export requires updating every workstream that
  lists it under Consumes, in the same commit.
- Do not restate another workstream's content. Link to it.
- Tick a box only with verified evidence — the command and its output — in the same commit as
  the work.
