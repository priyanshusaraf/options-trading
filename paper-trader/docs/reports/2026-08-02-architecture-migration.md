> **SUPERSEDED / CONTAINS STALE CLAIMS.** *(header added 2026-08-03)*
> The opening line **"Nothing in this migration is committed"** — and everything that follows
> from it, including "none of it is deployed because `deploy.sh` refuses a dirty tree" — is
> **false**. Phases A–H were committed as `cc53bba` on 2026-08-02. The migration is committed
> and verified; what is still true is that it is **not deployed** (blocked on owner
> acknowledgement, not on a dirty tree). Current truth:
> [`docs/engineering/workstreams/WS-02-execution.md`](../engineering/workstreams/WS-02-execution.md)
> §4 (phase-by-phase, with the SHA) and §8 (why it is undeployed).

# Enterprise Architecture Migration — status

Working record for the migration that must complete before Phases 3 / 5 / 6 / 9 / 13.
Source of the findings: [`2026-08-02-production-architecture-audit.md`](2026-08-02-production-architecture-audit.md).

**Nothing in this migration is committed.** `CLAUDE.md` says commit only when asked, so
the whole thing is in the working tree. `deploy.sh` refuses a dirty tree, so **none of
it is deployed** and the VPS is unaffected.

**Engineering rule applied throughout:** additive migrations over rewrites. Every phase
must leave existing behaviour byte-identical, and each one carries a test that asserts
that equivalence rather than claiming it.

---

## Phase A — Migration infrastructure ✅

Alembic replaces the hand-maintained `ADD COLUMN` dict as the mechanism for schema change.

| | |
|---|---|
| Added | `alembic.ini`, `migrations/env.py`, `migrations/versions/`, `app/db/migrate.py`, `migrations/baseline_schema.ddl` |
| Baseline | revision `0001` — a deliberate no-op naming the pre-Alembic floor |
| Frozen | `session.py:_migrate_schema()` — kept (it is the only thing that can carry a pre-Alembic DB to the baseline) but may never be extended |
| Schema version | `GET /api/health` → `schema: {current, head, up_to_date}` |
| CLI | `python -m app.db.migrate {current,head,upgrade,history}` |

**Three database states, all converging on head:** empty → `create_all` + stamp head ·
pre-Alembic → frozen ALTERs + baseline tables + stamp `0001` + upgrade · managed → upgrade.

**The guard that makes it self-verifying:** `tests/test_schema_migrations.py` builds a
database from the ORM models *and* a database migrated up from the checked-in baseline
DDL, then diffs them column by column. Models and revisions cannot drift apart silently.
Proven red by adding a model column with no revision — it failed with the exact column
named. `tests/test_migrate_schema_frozen.py` fails the build if a line is added to the
legacy dict.

**Two real problems this phase surfaced and fixed:**

1. **`deploy.sh` would have killed the engine.** It excludes `.venv` and never installed
   dependencies remotely, so the first new dependency would have hit the VPS as an
   `ImportError` *after* `systemctl restart` — engine down, positions unmanaged. The
   script now installs requirements and proves the app imports **before** restarting, and
   fails while the old process is still healthy.
2. **`baseline_schema.ddl`, not `.sql`** — `deploy.sh` excludes `*.sql` (that is how
   ledger backups stay off the box) and its Guard 0 asserts the exclude list is strictly
   `--exclude PATTERN` pairs. Renaming the file was cheaper than widening a guard whose
   real job is protecting the production `.env`.

---

## Phase B — Deployment entity ✅

`Deployment` is now the primary execution object; revision `0002`.

Owns: strategy, strategy version, parameter set, account, universe, allocation, runtime
state (`armed`, `halted_on`), lifecycle (`draft|active|paused|archived`).

`deployment_id` added to the five tables that record an *execution* — `positions`,
`trades`, `equity_snapshots`, `signal_events`, `order_journal`. Reference tables
(`universe_instruments`, `runtime_config`, `instrument_state`) deliberately excluded:
they describe the platform, not a book.

**How this changes nothing.** The legacy deployment (`id=1`) is seeded with
`universe_mode='legacy'`, `strategy_key=NULL`, `allocation=NULL`, `params_json='{}'` —
which together mean "resolve exactly as before". `deployment_id` lands NOT NULL with
`server_default='1'`, so an insert path that knows nothing about deployments still
succeeds and is still attributed. Verified by raw SQL insert, not just through the ORM.

**Reads stay unscoped; writes are stamped.** `open_positions()` and `position_for()`
take an *optional* deployment filter that nothing in the exit path passes. This is
deliberate: a misattributed write is a reporting error, a missed read is a position
nobody exits — and hard invariant 2 says the risk lane manages every persisted position.

**Verified against a real ledger:** a copy of `paper_trader.db` went `unmanaged → 0003`
with every row preserved, `positions.deployment_id = 1`, and the legacy deployment seeded.

---

## Phase C — Scoped configuration ✅

`app/core/scoped_config.py` — one resolution path, narrowest wins:

    Platform    Settings defaults, then runtime_config rows
    Deployment  deployments.params_json
    Instrument  instrument_state.params_json          (revision 0003)

The owner's ten live `runtime_config` overrides become **platform scope** with no data
migration and no change in meaning. `EngineRunner._effective_params()` now resolves
through this path.

**The assertion that matters:** `resolve()` with no scope arguments returns exactly what
`effective()` returned — same keys, same values, same types — and there is a test that
says so, including with platform overrides present.

Narrower scopes are validated through the *same* `OVERRIDABLE` + `BOUNDS` gate the
platform uses, so a deployment cannot set a key or a value the platform would refuse.
Invalid values are skipped-and-logged on the read path (it runs inside the signal loop;
one bad row must not stop the engine managing open positions) and *raised* on the write
path (a human is watching). `explain()` gives per-key provenance, because "why is this
stop 0.8%?" gets asked during an incident.

---

## Phase G — Execution parity ✅

`app/engine/decision_kernel.py` — one pure exit decision for live, replay and backtest.

Three implementations existed and were never compared: live options
(`evaluate_exit`), live equity (`equity_exit`), and the backtester — which evaluated
**ratchet and strategy flag only, no stop or target at all**. The backtester's own
docstring admitted it; the numbers did not.

Both live functions are now thin wrappers with unchanged signatures and return types
(their existing tests pass untouched — that is the proof the kernel was extracted, not
redesigned). The backtester routes through the same kernel.

**The divergence is now declared, not absent.** `ExitPolicy.no_protective_band(note=...)`
requires an explanation, `divergences()` reports it alongside results, and a test fails
if someone tries to declare one without a reason.

**A real bug the parity test caught in this phase's own code:** the first kernel used
`NO_STOP = -inf`, which on the directional SHORT path (`price >= stop`) means *stopped at
any price* — every short would have exited instantly with reason `STOP_LOSS`. Levels are
now `None`-means-unset; a sentinel whose meaning flips with direction is not a sentinel.

---

## Phase H — API foundation ✅

Versioning, principal, authorization boundary, stable DTOs — seams only, no multi-user
features.

`/api/v1/*` serves every existing route by re-registering the **same endpoint callables**
under rewritten paths at mount time; `routes.py` was not edited, and the unprefixed paths
are served by literally the same route objects as before. `Principal` (owner /
anonymous-owner, never `None` when auth is disabled) is resolved once at the middleware
boundary; `require(principal, action, resource)` is the single authorization seam and
currently allows everything. DTOs describe the health and deployment-summary shapes;
routes were **not** given `response_model=` because that silently drops undeclared keys —
a behaviour change on a live surface.

Auth exemptions match on the *unversioned* path, so `/api/v1/health` will not 401 the day
`deploy.sh` moves. The internal-state-leak inventory (`runner.state` publishing
`_ratchet_atr` to every browser; `/api/status` as ad-hoc runner attributes) is recorded in
`dto.py` for the phase that migrates those routes.

---

## Phase D — Strategy identity ✅

Strategies are now immutable, content-addressed artifacts.

`app/strategy/identity.py` computes a sha256 over the things that decide behaviour —
key, code (or, for a generated strategy, its **composition**, since all generated
strategies share one wrapper class), default params, risk model. `display_name` is
deliberately excluded: a rename must not mint a new artifact. The scheme id is inside
the hashed payload so a future scheme change is visible rather than a silent collision.
Determinism is verified across processes under differing `PYTHONHASHSEED`.

**Fail-closed resolution.** `resolve_strategy(key)` raises `StrategyNotFound`.
`get_strategy()` keeps its fail-open fallback — correct for the legacy per-instrument
path, where a stale assignment must not crash a tick — but now logs (rate-limited) when
it actually substitutes. `None` is not logged: it is the explicit "give me the default"
idiom the chart and backtest paths use on every request, and logging it would bury the
real substitutions.

**The deployment path is fail-closed** (`resolve_deployment_strategy`). This is the C4
defect: a deployment *names* which strategy trades, so an unresolvable key must halt it,
never hand the customer's capital to the platform default while the trade rows claim
otherwise. `None` (the legacy deployment pins nothing) stays distinguishable from
"not found".

**Provenance on the money record** — revision `0004` adds `positions.strategy_version`,
`trades.strategy_version`, `generated_strategies.version`. Nullable, no default,
following `build_sha`'s three-value rule: a hash means identified, `'unknown'` means
running-but-unidentifiable, NULL means predates the column. The 72 real trades stay NULL
— backfilling them would assert a provenance they do not have.

**Still open:** `generated_strategies.key` remains the primary key, so redeploying an
edited strategy still overwrites in place. Recording the version makes that overwrite
*detectable*; making identity `(key, version)` needs the deploy bridge and the registry
to both carry it, and is left as named work rather than half-done.

## Phase E — Strategy specification ✅ (contract compiled, adoption deferred)

`app/strategy/spec.py` — `StrategySpec` = metadata + typed parameter schema + signal
generation + entry policy + exit policy + sizing policy. `compile_spec()` turns any
existing `Strategy` into one, and **every registered strategy compiles** (asserted by a
test parametrised over the registry, so a strategy added later is covered automatically).

Parameters carry a **kind**, not just a type — `LENGTH`, `THRESHOLD`, `PERCENT`,
`MULTIPLIER`, `CHOICE`, `MINUTE`, `BOOLEAN` — because "it's a float" does not tell an
editor whether `0.8` means 80% or 0.8 ATR, and Phases 5 and 6 render from the kind.
Bounds are contractual, not advisory. `resolve_params()` falls back on the read path
(the engine, mid-loop) and `ParamSpec.validate()` raises on the write path.

`ExitPolicy` is the decision kernel's, not a second one — a spec with its own exit
vocabulary would need a translation layer, and the translation is what would drift.

Consumed by `strategy_meta()` → `/api/strategies`, **added** alongside `default_params`
rather than replacing it, so existing consumers are untouched.

**Deliberately not done:** the engine does not read specs yet. Swapping the runner onto
them changes real-money entry and exit paths and needs its own parity evidence — the
same compile-first / adopt-second order Phase G used.

## Phase F — Broker architecture ✅ (interfaces + boundary + guard; no re-parenting)

`Broker` Protocol (domain verbs) and `ExecutionVenue` Protocol (11 wire verbs, failure
semantics declared rather than inherited). `app/engine/kite_venue.py` is now the only
place `MIS`/`NRML`/GTT/SL-M are spelled; `product_for_segment`/`exchange_for_segment`
delegate to it, so there is one implementation of each mapping.

`Position.gtt_trigger_id` is reached only through neutral accessors
(`protective_order_id` / `set_` / `clear_`), enforced by a test that greps for direct
column access. The column itself is **not** renamed — that is a rename migration plus
call sites, and landing it together with the broker refactor would have made both
un-bisectable.

**The H7 guard, which is the point of the phase:** venue-facing methods are enumerated,
and the build fails if `LiveBroker` *inherits* one from the paper simulator instead of
defining it. Proven red by renaming `ensure_stop_protection`.

**What that guard immediately found — a real latent defect.** `LiveBroker` inherits
`open_futures_position` / `close_futures_position` from the **simulator**, and
`runner.py:1398` calls them. In live mode that books a futures position into the ledger
with **no order behind it and no exchange stop**. It is unreachable today only because
`index_futures_enabled` defaults to `False` with no production override. Both facts are
now pinned: the gap is declared in `KNOWN_UNIMPLEMENTED_VENUE_METHODS` (bidirectional —
drift either way fails), and a test fails the build if that flag is ever flipped while
the gap is open.

**Deliberately not done:** no `BrokerCore` extraction — `class LiveBroker(PaperBroker)`
is unchanged. Re-parenting the real-money class and moving ~650 lines of ledger
arithmetic is not verifiable in one pass; the safety-critical half (every venue method
explicitly defined) is now enforced by a test rather than by hope. `KiteVenue` is a
checked translation table, **not wired into the live path**, and says so in its own
docstring — rewiring every protective-stop call site sits behind three July incidents
and wants its own phase.

## Phase I — Engine decomposition ⏳ not started (lowest priority: "only refactor where boundaries become clearer")

---

## Test-infrastructure fix (not a phase, but it made verification trustworthy)

The rootdir `conftest.py` isolated `PT_DB_PATH` per run but **not** `ledger.db` or
`research.db`, whose defaults are fixed paths. Two concurrent pytest runs shared them —
the same clobbering bug that once cost a session chasing 27 phantom failures, in two
tables nobody had looked at. It also meant a bare `pytest` read and wrote the developer's
real journal. All three are now redirected to the per-run temp directory.

This was found the honest way: a full-suite run reported seven health-endpoint errors and
several failures that all passed in isolation.

---

## Named remaining work

Recorded rather than half-done. Each is a decision someone should make deliberately.

1. **`generated_strategies` identity is still `key`, not `(key, version)`.** Redeploying
   an edited strategy overwrites in place. The version column makes that *detectable*;
   making it impossible needs the deploy bridge and the registry to both carry a version.
2. **The engine does not read `StrategySpec` yet.** Compiling is done; adoption changes
   real-money entry and exit paths and needs its own parity evidence.
3. **The backtester still does not model the protective band.** Now declared
   (`ExitPolicy.no_protective_band`) and reported, but the gap is real on the spot path,
   where the live SL/TP applies to the same series the backtest trades.
4. **`Position.gtt_trigger_id` is still a Zerodha concept in the ORM.** Renaming it to
   `protective_order_id` is a rename migration (batch mode, now available) plus call
   sites; it was kept out of this pass so the broker refactor and the schema change
   would not land together.
5. **The frontend still calls the unprefixed API.** Moving it to `/api/v1` is a
   one-constant change and step 2 of the deprecation path in `api/versioning.py`.
6. **`require()` has no call sites.** By design — it is the seam, not the rules — but
   that is one step from this codebase's known unconsumed-mechanism failure mode. The
   first phase to add an authorization rule should wire it rather than adding checks
   inline.
7. **Reads are not deployment-scoped.** Deliberate (see Phase B), and it is the change
   that must land before a second deployment can trade the same instrument.
8. **Phase I (engine decomposition) not started.** `EngineRunner` is still ~2,450 lines.
   The goal says refactor only where boundaries become clearer; the boundaries that
   became clearest during this migration are the entry-gate chain and the risk governor,
   and both sit in the middle of the live entry path.

## Verification status

All commands run from `backend/`, after every phase had landed.

| Check | Command | Result |
|---|---|---|
| Backend suite | `pytest tests research_tests -q` | **exit 0**, 2,303 marks, zero F/E |
| Ledger reconciliation | `scripts/dryrun.py 700` | **exit 0 · LEDGER OK ✓** |
| Backtest invariants | `scripts/backtest_smoke.py` | **exit 0 · SWEEP OK ✓** |
| Real-ledger migration | copy of `paper_trader.db` | `unmanaged → 0004`, **all rows preserved**, idempotent on re-run |
| Models ⇄ migrations parity | in-suite | asserted every run; **proven able to fail** |
| Venue-inheritance guard | in-suite | **proven able to fail** |
| Deploy | — | **not deployed** — tree is dirty by design |

> This project's pytest config swallows the trailing `N passed` line, so the count above
> is progress marks. Exit code is the claim; the count is context.

### One failure worth recording, because it was mine

The first full-suite run after Phase E came back **red** — `database is locked`, six
health-endpoint errors and two `init_db` guard failures, all of which passed in
isolation. Cause: `init_schema` runs on every `init_db`, and `command.upgrade` opens a
write transaction **even when there are no pending revisions**. Boot was taking a write
lock it did not need, contending with any already-open session.

Fixed by returning early when the database is already at head. That is not a test-only
fix: on the box, every `systemctl restart` was about to start competing for the lock
with the engine's own long-lived session.
