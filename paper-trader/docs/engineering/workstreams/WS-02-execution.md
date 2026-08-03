# WS-02 — Execution & Brokers

**Status:** active
**Owner surface:** `backend/app/engine/` (except `readiness.py` → WS-06),
`backend/app/providers/` (except `replay.py` → WS-07), `backend/app/options/`,
`backend/app/strategy/`, `backend/app/backtest/`,
`backend/scripts/dryrun.py`, `backend/scripts/backtest_smoke.py`, `backend/scripts/exit_sweep.py`

`app/market_data/candles.py` is **consumed, not owned** — WS-07 owns the data seam. It is
described under Consumes because a re-fork of it is the defect worth naming, wherever it lands.
**Last verified:** 2026-08-03 · commit `cdbe686`

> This workstream is the part of the system that spends money. It reads live Zerodha Kite
> candles, decides when the strategy's edge is present, picks the instrument, sizes the
> position against real broker margin, routes a real order, manages that position to an exit,
> and books the P&L net of the full Indian charge stack into a ledger that must reconcile to
> the paisa. **It controls real capital.** Live execution was enabled **2026-06-29**, the
> first real order was placed **2026-07-13 09:30 IST**, and as of 2026-08-01 it has booked
> **72 real trades, net −₹166.37** — every one of them `mode='live'`; there are zero paper
> rows in production. There is no "we'll test it in production later" here: the live order
> path (`LiveBroker`, `KiteOrderClient`, `LiveExecutionKite`) *is* production, and the next
> order is not its first. Treat every change in this workstream as a production change.

---

## 1. Vision

A trading engine whose behaviour on real money is fully determined, fully measured, and
identical to what its own backtester and replay harness say it is.

"Done" for WS-02 means five properties hold simultaneously:

1. **The book is honest.** The ledger reconciles to the paisa, every trade is booked at the
   true broker fill rather than the last mark, the equity curve is anchored to real account
   funds rather than the ₹50,000 synthetic seed, and any drift between them is visible in
   the cockpit rather than silent.
2. **Getting out never depends on anything.** Exits fire regardless of arm state, regardless
   of a failed cancel, regardless of one poisoned position key, regardless of a Telegram
   outage. Not getting out is worse than any other failure mode this system has.
3. **The bot's own exits are worth having.** Today they are not: across 72 real trades
   `TARGET` has fired **zero** times, the bot's own exits net **−₹2,927**, and the owner's
   45 manual closes net **+₹2,761**. Done means the exit policy has been measured over a
   real, uninterrupted sample and earns its keep — or is deliberately replaced.
4. **Live and backtest are the same decision.** One exit kernel, one candle→frame converter,
   one charge model, one strategy contract, one ratchet — with any remaining divergence
   *declared with a reason* and reported alongside results, never merely absent.
5. **Capital can scale without rewriting the engine.** Equity intraday today; index futures
   and MTF as additional segments behind their own flags, each with its own margin model,
   charge schedule and delivery guard, each provably ledger-exact before it is switched on.

The end state is not "more features". It is that a person can read what the engine did on any
given day, reproduce it exactly from recorded bars, and find the numbers agree.

## 2. Scope

**In scope.**

- **Signal generation** — the strategy registry (`app/strategy/registry/`), the canonical
  signal contract, `app/strategy/signals.py`, `app/strategy/spec.py`, `app/strategy/identity.py`.
- **Entry** — `engine/runner.py` (`process_entries`, `scan_signals`), `engine/equity_entry.py`,
  the entry-gate chain in `engine/risk_controls.py`, `engine/event_risk.py` blackouts,
  `engine/allocator.py`.
- **Sizing** — real-margin sizing off `kite.order_margins()`, the dust floor, leftover-cash
  cascade, `engine/capital.py`, `engine/execution_policy.py`.
- **Exits** — `engine/exit_monitor.py`, `engine/decision_kernel.py`, `_mark_exit_equity`,
  the trailing/ratchet logic, profit-lock and daily-loss halts in `engine/risk_controls.py`,
  `engine/overnight.py`, square-off.
- **Order routing and brokers** — `engine/broker.py` (`PaperBroker`), `engine/live_broker.py`,
  `engine/broker_protocol.py`, `engine/broker_factory.py`, `engine/kite_order_client.py`,
  `engine/kite_venue.py`, `engine/venue.py`, `engine/gtt.py`, `engine/order_executor.py`.
- **The ledger and P&L integrity** — `engine/ledger_reconcile.py`, `engine/reconcile.py`,
  `engine/charges.py`, `engine/carry.py`, `engine/analytics.py`, `scripts/dryrun.py`.
- **The backtester** — `app/backtest/` (sweep, engine, ratchet, premium, metrics,
  `live_equivalent.py`, `exit_sweep.py`), `scripts/backtest_smoke.py`.
- **Market data into the engine** — `app/providers/` (the `MarketDataProvider` seam,
  `safe_kite.py`, `live_kite.py`, `mock.py`, `replay.py`, `factory.py`) and
  `app/market_data/candles.py`.
- **Options selection and pricing** — `app/options/picker.py`, `app/options/pricing.py`
  (index-only, lowest priority per the 2026-07 product direction).
- **Readiness of the money path** — `engine/readiness.py`, `engine/health.py` (the *logic*;
  the operational probe run is WS-06).

**Out of scope.**

| Not here | Owned by |
|---|---|
| The Component IR language (`app/ir/`), RFC 0001, the resolver/runtime/editor, IR strategy parity | **WS-01 Strategy OS.** WS-02 owns the *adoption* decision only, and it is blocked (§8). |
| DB models, sessions, Alembic revisions, `runtime_config` storage mechanics, retention | **WS-07 Infrastructure.** WS-02 declares which columns the money record needs; WS-07 owns how they are stored and migrated. |
| `scripts/deploy.sh`, the VPS, systemd, running `curl /api/health` against the box, droplet resize, OS reboot | **WS-06 Deployment.** WS-02 supplies the acceptance commands; WS-06 runs the deploy and measures the box. |
| The research plane (`research/`), DSR/PBO/N_eff, strategy generation, the search loop | **WS-03 Research.** The isolation rule is a WS-02 safety invariant, but the plane itself is not ours. |
| Frontend, cockpit, Settings UI, journal UI | **WS-05 UI.** |

## 3. Interfaces

**Exports** — what other workstreams may depend on. Anything not listed is internal and may
change without notice.

| Export | Guarantee |
|---|---|
| `app/strategy/registry/base.py::Strategy` + `CANONICAL_COLUMNS` | A strategy turns a candle DataFrame into **exactly four mandatory boolean columns** — `longEntry`, `shortEntry`, `longExit`, `shortExit`. Extra indicator columns are permitted and consumed by chart payloads; the four are enforced by `signals()`, which raises if any is missing. Direction/stop/target/sizing are **not** the strategy's job — the engine owns the risk layer. Auto-discovery is by module-level `STRATEGY`; default is `trend_impulse_v3`. |
| `app/strategy/registry/base.py::Strategy.version` / `pin_version` | Immutable content address (sha256 over key, code or composition, default params, risk model) from `app/strategy/identity.py`. Deterministic across processes and `PYTHONHASHSEED`. `display_name` is deliberately excluded — a rename must not mint a new artifact. |
| `app/strategy/identity.py::resolve_strategy(key)` | **Fail-closed** — raises `StrategyNotFound`. `get_strategy()` keeps a fail-open fallback for the legacy per-instrument path but logs (rate-limited) when it substitutes. `resolve_deployment_strategy` is fail-closed by design. |
| *(re-exported, owned by WS-07)* `app/market_data/candles.py` | **THE** candle→signal-frame converter and validator for the whole system. `runner._to_df` and `backtest._candles_to_df` are thin aliases over it. They used to be byte-identical copies, so a data fix could land in one plane and miss the other — do not re-fork it. Owned by WS-07; listed here because this workstream's aliases are the ones that would re-fork it. |
| `app/engine/charges.py::compute_charges` / `round_trip_charges` / `legs_for` | Zerodha segment-aware charge model (`NFO_OPT`, `NFO_FUT`, `BFO_FUT`, equity intraday/delivery). Direction-aware: `legs_for(direction)` charges a SHORT as SELL-to-open / BUY-to-cover. **All P&L, equity and backtest figures anywhere in the system are net of this stack.** Rates are indicative and must be re-verified against contract notes; the model must never *under*-charge (a test pins `BFO >= NFO`). |
| `app/backtest/` (`sweep`, `engine`, `metrics`, `live_equivalent`, `ratchet`, `premium`) | Underlying sweep with per-`(instrument, interval)` cache, background thread. Next-bar-open fills, no look-ahead, full direction-aware charge stack on both legs, execution cost modelled via `Settings.backtest_slippage_pct` (5 bps default; `0.0` reproduces every pre-`c7e5217` number exactly). **Interpretive contract: a backtest `return_pct` is NOT a live account-return prediction** — backtest sizing is one unleveraged full-capital position, live is up to four MIS-margin ones. |
| `app/backtest/exit_sweep.py` | Replays real booked trades against candidate exit parameters off MFE/MAE telemetry. Ambiguous stop-vs-target orderings are reported as a band, never guessed. |
| `app/engine/decision_kernel.py::decide_exit` / `ExitPolicy` / `ExitDecision` | The single pure exit decision shared by live options, live equity and the backtester. Levels are `None`-means-unset — never a `±inf` sentinel whose meaning flips with direction. Any deliberate divergence must be declared via `ExitPolicy.no_protective_band(note=...)` and is reported by `divergences()`. |
| `app/engine/risk_controls.py` (pure predicates) | Side-effect-free gate functions: `slots_available`, `in_reentry_cooldown`, `over_per_trade_cap`, `expiry_too_close`, `signal_already_evaluated`, `signal_too_old`, `before_entry_window`, `gap_halt_active`, `outside_trading_session`, `daily_loss_halt`, `round_trip_cap_reached`, `daily_profit_lock`. Pure in, pure out — testable without an engine. |
| `app/engine/event_risk.py` | The scheduled-event blackout table (EIA gas Thu / crude Wed with US DST, NIFTY Tue, SENSEX Thu, BANKNIFTY Wed, bullion options into expiry, stock earnings). **One rule table shared by engine, backtester and `/api/event-risk`** — do not add a second. |
| `app/engine/readiness.py::evaluate` / `lane_state` / `Thresholds` | Pure readiness verdict logic behind `/api/health`. Budgets are static `Settings` (`health_risk_stale_seconds`, `health_signal_stale_seconds`, `health_startup_grace_seconds`), deliberately **not** `runtime_config`-overridable so no DB row can silence a safety probe. |
| `app/providers/base.py::MarketDataProvider` | The data seam. New optional methods must be **concrete with a safe default** (`get_futures_ltp` returns `None`), never abstract — an accidental abstract method broke provider construction in nine tests at once, and there is now a test pinning that. `None` means "I cannot price this"; the caller must refuse, never fall back to spot. |
| `app/engine/broker_protocol.py::Broker` / `ExecutionVenue` | Domain verbs and 11 wire verbs, failure semantics declared rather than inherited. `kite_venue.py` is the only place `MIS`/`NRML`/GTT/SL-M are spelled. |
| `scripts/dryrun.py`, `scripts/backtest_smoke.py`, `scripts/exit_sweep.py` | The headless acceptance proofs (§6). Both force the mock provider — no Kite, no network. |

**Consumes** — what this workstream depends on, and from where.

| Consumed | From | Why |
|---|---|---|
| ORM models, `init_db`, sessions, Alembic revisions | WS-07 Infrastructure | The ledger, positions, trades, `order_journal`, `equity_snapshots` all persist here. New money-record columns (`mfe`, `mae`, `exit_price_estimated`, `strategy_version`, `build_sha`, `deployment_id`) land as WS-07 revisions. |
| `app/core/config.py::Settings`, `app/core/runtime_config.py`, `app/core/scoped_config.py` | WS-07 Infrastructure | Every knob. `runtime_config` rows shadow code defaults at platform scope — see §7. |
| `app/core/version.py` / `backend/VERSION` | WS-06 Deployment | `build_sha` stamped on every `trades` row. Three distinguishable values — a SHA, `'unknown'`, and NULL — never collapse the last two. |
| `scripts/deploy.sh` and the box | WS-06 Deployment | Nothing in this workstream reaches production any other way. |
| The strategy registry, read-only, via `research/evaluation/kernels.py` | WS-03 Research (reverse direction) | WS-03 consumes *our* exports; `research/guards.py` forbids it importing broker/runner/db.session. Keep that fail-closed. |

**Depends on:** WS-07 (persistence, config), WS-06 (deploy path, build stamp)
**Blocked by:** owner acknowledgement for the architecture migration deploy (WS-06 cannot run
it without that); owner acknowledgement for IR runtime adoption (WS-01 supplies the runtime,
the live-path change is ours); owner time for the five-session no-touch exit trial. See §8.
**Currently blocking:** WS-01 (production adoption of the IR runtime lands in *our* engine
paths); WS-03 (the strategy registry contract and backtest kernels it evaluates against);
WS-05 (cockpit numbers, `ledger_drift`, health payload shapes).

## 4. Completed

Verified and committed work, newest first. Dates and SHAs are from `docs/ROADMAP.md` and
`git log`; where the roadmap records evidence, the evidence is kept.

**Architecture migration, phases A–H — `cc53bba`, 2026-08-02. Committed and verified.
NOT DEPLOYED (§8).** Eight additive phases, every one leaving existing behaviour
byte-identical and carrying a test that *asserts* that equivalence rather than claiming it.
Working record: `docs/2026-08-02-architecture-migration.md` (note: that file's opening line
"Nothing in this migration is committed" is stale — it was written before `cc53bba`).
Phases relevant to this workstream:
- **Phase G — execution parity.** `engine/decision_kernel.py`: one pure exit decision for
  live, replay and backtest. Three implementations existed and had never been compared —
  live options (`evaluate_exit`), live equity (`equity_exit`), and the backtester, which
  evaluated **ratchet and strategy flag only, with no stop or target at all**. Its own
  docstring admitted it; the numbers did not. Both live functions are now thin wrappers with
  unchanged signatures, and their existing tests pass untouched — that is the proof the
  kernel was extracted rather than redesigned. Remaining divergence is *declared*
  (`ExitPolicy.no_protective_band(note=...)`) and reported. **A real bug the parity test
  caught in this phase's own code:** the first kernel used `NO_STOP = -inf`, which on the
  SHORT path (`price >= stop`) means stopped at any price — every short would have exited
  instantly with reason `STOP_LOSS`.
- **Phase F — broker architecture** (interfaces + boundary + guard; **no re-parenting**).
  `Broker` and `ExecutionVenue` protocols; `kite_venue.py` is the sole place `MIS`/`NRML`/
  GTT/SL-M are spelled. `Position.gtt_trigger_id` is reached only through neutral accessors,
  enforced by a test that greps for direct column access. **The H7 guard is the point of the
  phase:** venue-facing methods are enumerated and the build fails if `LiveBroker` *inherits*
  one from the paper simulator. Proven red by renaming `ensure_stop_protection`. **What it
  immediately found — a real latent defect:** `LiveBroker` inherits
  `open_futures_position`/`close_futures_position` from the **simulator**, and
  `runner.py:1398` calls them; in live mode that would book a futures position into the
  ledger with **no order behind it and no exchange stop**. Unreachable today only because
  `index_futures_enabled` defaults to `False` with no production override. Both facts are now
  pinned: declared in `KNOWN_UNIMPLEMENTED_VENUE_METHODS` (bidirectional — drift either way
  fails) and a test fails the build if that flag is ever flipped while the gap is open.
- **Phase D — strategy identity.** Content-addressed, immutable strategy artifacts;
  fail-closed `resolve_strategy`; `strategy_version` provenance on `positions`, `trades`,
  `generated_strategies` (revision `0004`), following `build_sha`'s three-value rule. **The
  72 real trades stay NULL — backfilling would assert a provenance they do not have.**
- **Phase E — strategy specification** (contract compiled, **adoption deferred**).
  `app/strategy/spec.py`; every registered strategy compiles, asserted by a test parametrised
  over the registry. Parameters carry a *kind* (`LENGTH`, `THRESHOLD`, `PERCENT`,
  `MULTIPLIER`, `CHOICE`, `MINUTE`, `BOOLEAN`) because "it's a float" does not tell an editor
  whether `0.8` means 80% or 0.8 ATR. `ExitPolicy` is the decision kernel's, not a second
  one. **The engine does not read specs yet** — that changes real-money entry and exit paths.
- Phases A (Alembic), B (`Deployment` entity), C (scoped config) and H (API foundation) are
  WS-07/WS-04 surface; recorded here because they landed in the same commit and because
  Phase B's rule is a WS-02 safety rule: **reads stay unscoped, writes are stamped** — a
  misattributed write is a reporting error, a missed read is a position nobody exits.

**Kill-switch defect found and fixed — `e273d54`, 2026-08-02.**
`docs/2026-08-02-execution-determinism-audit.md`. `kill()` ran `cancel_working_entries()`
between the disarm and the square-off with no isolation; a throwing broker call at exactly
the moment things are going wrong propagated to the API route and **the square-off never
ran**, leaving the operator believing they had stopped the bot while positions stayed open.
A half-completed kill is worse than an obvious failure because it looks like success. Now:
disarm first and unconditionally, cancel and square-off each isolated, each logging
`KILL_PARTIAL` with what was left undone; a failed Telegram notify can never mask a
successful kill. Three of the six tests were red against the old code. Same audit asserted
duplicate-order prevention (running the entry path five times on one signal opens at most one
position, and the ledger still reconciles afterwards) and arm/disarm asymmetry as
*properties*, both of which held but had no test.

**Backtester audit — `c7e5217`, 2026-08-01, deployed.**
`docs/2026-08-01-backtester-audit.md`, all ten Phase-1 dimensions with verdicts cited to file
and line. Came out well: **no look-ahead** (next-bar-open fills, exit decisions start the bar
after the fill, every strategy shift backward, no `shift(-1)`/`center=True`/backfill
anywhere), full direction-aware charge stack on both legs, statistics that label their own
limits. **One real defect, fixed:** the SPOT backtester filled at the exact bar open with
**zero execution cost** while `premium.py` had modelled a spread since it was written — so
every `equity_intraday` backtest was optimistic. Against a 0.8% stop / 1.5% target and a
largest-ever favourable excursion of 1.216%, an unmodelled round trip is the same order as
the edge. `Settings.backtest_slippage_pct` defaults to 5 bps. 10 tests.
**Documented, not fixed (divergences, not bugs):** backtest sizing has no relationship to
live sizing — the biggest interpretive trap in the system; no intrabar stop (live uses an
exchange SL-M that fires mid-bar); no partial fills; no pyramiding; structural survivorship
in the curated universe.

**Ledger honesty / live-state gap — `4c91e05`, 2026-08-01; deployed 2026-08-01 in `4e9f125`.
Effect NOT yet observed.** The cockpit reported ₹49,833 against a much smaller real account
for three weeks: E0.2's auto-reanchor could only fire on a ledger that had never traded,
which production has done since 2026-07-13, so the path was unreachable from the day it
shipped. It now re-anchors **once a day, before the day's first entry, with a flat book, only
when actually adrift** (`should_reanchor` in `engine/ledger_reconcile.py`), and
`capital_dict` publishes `ledger_drift` so a lying ledger shows a warning badge instead of
being silent. The deploy was a Saturday with no valid Kite token, so `_account_funds` was
`None` and the field was simply absent — **that is the shape of "could not measure", not
evidence either way.** Verification still outstanding: next trading session, after Connect
Kite, `ledger_drift` should appear in `/api/status` and sit near zero.

**Exit sweep and give-back retune — `eafd7bc`, 2026-08-01.**
`docs/2026-08-01-exit-sweep.md`, Workstream C P2. `scripts/exit_sweep.py` replays real trades
against candidate parameters off MFE/MAE telemetry. **The answer: the target was
UNREACHABLE** — the largest favourable excursion ever recorded is 1.216% of notional against
a 1.5% target, so zero `TARGET` exits was *structural, not tuning*. The give-back lock is the
only lever that works: `intraday_profit_lock_threshold` 600→**150**,
`intraday_profit_lock_frac` 0.3→**0.7**, which turns the 22 replayable trades from −₹913 to
+₹268. **Sample is 22 trades: a direction to test, not a proven setting.** Both production
overrides (450/0.3) were **cleared 2026-08-01 on the owner's instruction** via
`POST /api/settings/reset` (which also calls `refresh_params()`, so the running engine took
them without a restart) — verified on the box via `/api/settings`:
`intraday_profit_lock_threshold value=150.0 overridden=false`,
`intraday_profit_lock_frac value=0.7 overridden=false`.

**Event-risk blackouts — `d1011c1`, `c1dd9f1`, 2026-08-01.** The owner's scheduled-event
rules as **one table** shared by engine, backtester and `/api/event-risk`.

**Reconciliation noise — `ea500f0`, 2026-08-01.** Eleven false orphan alarms per restart were
the bot's own SL-M orders and the owner's own positions; a real orphan would have been
invisible in the noise.

**Replay provider — 2026-08-01.** `app/providers/replay.py`, `PT_PROVIDER=replay`. Re-runs a
recorded session bar by bar against the real engine. **The property the whole thing rests on
is no look-ahead:** `get_candles` returns history up to and including the cursor and not one
bar further; `now()` returns the recorded bar's timestamp so market hours, the square-off
deadline and every staleness check behave as they did on the day. **It structurally cannot
trade** — `is_authenticated()` is always False and `make_broker()` refuses a real
`LiveBroker` without an authenticated kite provider — and it refuses to price futures rather
than inventing a basis. 13 tests.

**Timezone audit — 2026-08-01.** Measured, not assumed: the production droplet is set to IST
while DigitalOcean droplets default to UTC, so a rebuild would come up 5.5 hours off and
nothing would notice. **One real hazard found and fixed:** `broker.mark()` stamped
`last_mark_time` from the provider's IST clock but **fell back to naive host-local**; on a
UTC host those differ by 19,800s and the mark-staleness guard compares them — a just-taken
mark would read as stale, and `is_stale` **suppresses SL/TP**. A stop silently not firing on
real money, triggered by nothing more than rebuilding the droplet. The fallback is now IST;
`tests/test_timezone_independence.py` runs the logic under three zones.

**Readiness probe logic — 2026-08-01, deployed (`4e9f125`).** `/api/health` used to be a
liveness stub that returned 200 through both 2026-07 outages. Verdict logic is pure in
`engine/readiness.py` (22 unit tests) + `tests/test_health_endpoint.py` (10). Returns **503**
when the DB is unreachable, the loops are stopped, or the **fast risk lane** is stale (stops
not firing = unmanaged real money). **The signal lane is reported but deliberately never
fatal** — it legitimately stops beating overnight and deploys run out of hours, so a fatal
signal lane would have 503'd every legitimate deploy. `_beat_now` stamps `provider.now()`,
which under the mock is *simulated* time; the runner keeps a parallel monotonic beat
(`_beat_wall`) that readiness reads, so lane ages mean the same thing in every provider mode.
**Still unexercised live: the 503 path** — proven in-process only; confirming it in
production means deliberately stalling the risk lane on a real-money box. Treat the next
genuine incident as the test.

**Candle validation seam + feed-quality reporting — 2026-08-01.**
`app/market_data/candles.py` is now THE converter; `runner._to_df` and
`backtest._candles_to_df` are aliases over it. Repeating problems log once, a changed one
logs again, a recovered feed drops out of the report. **Still open — the actual
measurement.** `provider_feed` was `{}` at deploy with markets shut: that is "the scan has
not run", not "the feed is clean".

**Workstream E — Phase E2 index futures: all twelve build steps DONE 2026-08-01, deployed,
`index_futures_enabled=False`.** Step 13 (owner + Fable review before the flag flips) is the
only thing left and is deliberately not an agent's to do. Step 12's proof runs with the flag
**ON** in test: open → mark → exit with the ledger invariant asserted at every stage, across
profit, loss, SHORT and force-flat round trips. **Two real defects the build surfaced, both
about defaults rather than logic:** `index_futures_max_margin` defaulted to ₹25,000 when one
NIFTY lot blocks ~₹216,000 — enabled, the segment would have silently never traded and looked
*broken* rather than off; and the same arithmetic says plainly that **a ₹50,000 account
cannot trade index futures at all**, which is the concrete reason this was always scoped as a
bigger-capital feature. Step highlights:
- *Step 1 — delivery-window guard* (`engine/delivery_calendar.py`), built **first** because
  the failure it prevents is not a losing trade but an obligation to deliver physical metal.
  A no-op for cash-settled index futures, but tested against a calendar that actually bites.
  **Unknown means UNSAFE**, and the polarity is deliberate: `True` means safe, so a caller
  who forgets to negate gets a refusal rather than an unguarded position. 9 tests.
- *Step 2 — `BFO_FUT` charge schedule.* SENSEX futures had **no** schedule, so a P&L computed
  for one would have booked the trade as free. BSE's derivatives txn charge is unverified
  against a contract note, so it is set equal to NSE's — the model must never **under**-charge
  since an optimistic cost model flatters everything built on it. A test pins `BFO >= NFO`.
- *Step 3 — futures LTP seam.* `get_futures_ltp` concrete, returning `None`. The mock's
  synthetic basis **decays to zero at expiry**, because convergence at settlement is the one
  property a test must rely on.
- *Steps 5 + 11 — broker open/close, ledger paisa-exact.* A near-copy of the equity pair
  rather than a shared generic, so the live equity path is never one refactor away from a
  futures change. **Margin is REQUIRED with no fallback** — SPAN is portfolio-scanned, so a
  guessed figure would be a fabricated number sitting in the ledger. Separately asserted:
  **only the margin leaves cash** — ₹1.2 crore of notional against ₹25k of margin would take
  the account deeply negative on the first contract if it leaked.
- *Step 6 — margin-based P&L.* `MARGIN_SEGMENTS` is a named set, not a repeated literal: one
  method calling futures margined while the other called them fully paid would inflate equity
  by the notional on every tick.
- *Step 4 — config knobs, every one inert.* Concurrency starts at **1**: a new leveraged
  segment earns its width. `index_futures_margin_pct` is a flagged **paper-only** SPAN
  estimate; live sizing must use a broker `order_margins()` quote.

**Workstream E — Phase E1 daily profit-lock: DONE 2026-07-24** (built by Sonnet 5, reviewed
by Opus). Pure `daily_profit_lock` in `risk_controls.py` (twin of `daily_loss_halt`) + runner
state (`_pl_high_water`, `_pl_deployed_peak`, `_pl_halted_date`, reset each session)
maintained every risk tick in `_maybe_profit_lock`; on breach it calls `_square_off_all`
(factored out of `kill()`, now the single flatten implementation) and sets a sticky session
halt that `_entries_halted`/`halt_status` honour. **Denominator = peak *concurrent* deployed
capital today** (max Σ open `entry_cost`; not cumulative, so re-entries don't inflate it).
Knobs `daily_profit_lock_pct` (fraction, `0` = off) + `daily_profit_giveback_frac`, both
live-editable and bounded. **Default off → zero behaviour change**, verified across dryrun
seeds 6/11/17/29. 12 tests. **Design decisions (owner, 2026-07-24):** base is *deployed*
capital not account equity, so the lock respects the chosen risk; action is **flatten all +
halt**; high-water trails up and never loosens. **This is the one exit path where the ARM
gate does not apply** — it works while disarmed. **Owner tuning caveat (Opus):** early-day
peak-concurrent-deployed can be small, so a low `lock_pct` may arm and halt the whole session
on a tiny peak; a future `min_deployed` floor knob is worth considering.

**Workstream E — Phase E0 P&L integrity: DONE 2026-07-24**, three items:
- **Exit booked at the TRUE fill, not the last mark.** `live_broker.reconcile_orphans` asks
  the broker's order book for the real SELL fill before booking an options
  external/reconciled close — new `KiteOrderClient.find_fill(symbol, side)` scans today's
  COMPLETE orders; books at that fill when found, else falls back to the mark **and tags the
  trade `exit_price_estimated=True`**. Equity R3 fallbacks and the manual paper-close override
  are tagged estimates too. Evidence: a mock fill of 123.45 ≠ mark is booked at 123.45 with
  `estimated=False`; the no-fill path books the mark with `estimated=True`. Owner evidence
  that started it: a SENSEX put exited at +₹792 pre-charges and the bot recorded ~₹1,000.
- **Equity curve anchored to real account value.** `_maybe_auto_reanchor` inside the live-only
  `_maybe_refresh_funds`. The write goes **through the broker's own long-lived session** —
  Opus review caught a first cut using a separate session, where `expire_on_commit=False`
  left `broker.capital()` stale at ₹50k so the next `snapshot()` would clobber the reanchor
  back to the synthetic base. (This is the fix that was later found unreachable on a traded
  ledger — see the `4c91e05` entry above.) 6 tests.
- **Peak-excursion telemetry.** `Position.mfe`/`mae` + `Trade.mfe`/`mae` (₹ unrealized-P&L
  excursion, segment/direction-aware), updated at the single `mark()` chokepoint and copied
  onto every Trade at close including both partial-close paths. **Opus review caught a
  hot-path regression:** the mock's `np.float64` premiums leaked into the ORM writes and
  intermittently corrupted SQLAlchemy's unit-of-work bookkeeping → `StaleDataError` on the
  `mark_and_exit_positions` commit (deterministic at `PYTHONHASHSEED=6`, clean on baseline).
  Fixed by casting to Python `float`, guarded by two regression tests. Pure telemetry, ledger
  untouched. 8 tests. This is the prerequisite that made the exit sweep possible.

**Workstream B — safety backlog: all code items CLOSED 2026-07-25 (TDD, each defect
reproduced RED before the fix), DEPLOYED 2026-08-01 06:59:50 UTC (`4e9f125`).** The deploy
was the item gating the whole workstream; `scripts/deploy.sh` exit 0, guards 0–2 passed, both
suites + dryrun green, `.env` verified present post-transfer, `GET /` 200, `/api/health`
reporting the shipped SHA. The engine came up DISARMED, as it does on every start.
- **E1 (the worst; silent; live):** a poisoned open-position key aborted the risk loop's
  mark/exit for the **whole book**. `runner._resolve_or_skip()` now resolves per-position and
  alerts once; `square_off_intraday` falls back to the NSE clock rather than skipping (MIS
  cannot legally carry); `remove_instrument` refuses while a position is open. **The
  operational rule "never remove an instrument with an open position" is retired.**
  `tests/test_poisoned_position_key.py`
- **E2** `PT_API_TOKEN` fail-open — verified CLOSED on the VPS 2026-07-20 (64-char token set).
- **E3** options GTT stop divergence — `_resync_option_gtt` mirrors the equity cancel+replace,
  refuses a second GTT if the cancel fails, leaves the id `None` so the self-heal retries.
- **E4** phantom close — the route checks the broker return; a refused close answers
  `{error, closed:false}` and keeps display state + re-entry intact. *The frontend half is
  test-unverified.*
- **E6** options orphan mislabelled the bot's **own** GTT fill as an external exit (corrupted
  exit-reason analytics + false same-day re-entry block). New `client.gtt_status()` — a
  trigger_id is not an order_id; conservative fallback keeps the block on any failed read.
- **E7** equity SHORT charge legs — `charges.legs_for(direction)` on all three equity paths,
  so `net_pnl` reconciles against the contract note.
- **E8** `account_pnl` LONG-only sign — defers to `Position.unrealized_pnl()`.
- **E9** options entry-LIMIT tick rounding — `place()` snaps `limit_price` to the real
  per-instrument tick.
- **E10** overnight flatten segment filter — `square_off_for_overnight` skips
  `equity_intraday` (it was closing equity for "expiry too close (0d < 2d)");
  `square_off_intraday` is the sole MIS authority.

**Workstream C — exit tuning, earlier items.** P1 exit autopsy on real VPS trades
(2026-07-15). Interim exit params baked in as code **defaults** 2026-07-21 (PAYTM early-exit
complaint): sl 0.008, target 0.03, lockstep_trigger 0.03, lock_threshold 600, lock_frac 0.3;
purple bands widened to stay strictly wider than the new normal band (purple sl 0.015 /
target 0.045).

**Sizing: the intraday leverage cap was REMOVED 2026-07-22 (`0f93f9a`).** It survives only as
the probe seed and as the paper/mock fallback when a live margin quote is unavailable. **Do
not reintroduce it as a binding cap.**

## 5. Active roadmap

Ordered. The topmost unchecked item is what an implementation agent picks up — but read §6's
last clause first: **nothing in this workstream deploys without owner acknowledgement.**

- [ ] **Observe the three unverified 2026-08-01/02 changes on the next live session.** All
      three were built with markets shut, so none has ever been seen working — absence of
      evidence, not evidence of absence. In order, after **Connect Kite**:
      1. `curl /api/status` → `ledger_drift` should **appear** and sit near zero. If the field
         is still absent, `_account_funds` is `None` again and the re-anchor did not run.
      2. `curl /api/health` → `provider_feed`, and grep the log for `FEED_QUALITY`. This is
         the first real answer to "is Kite's candle history actually dirty?" — the validator
         has been repairing silently and nobody has ever seen the report.
      3. The retuned **150 / 0.7** give-back lock takes its first live session. It is running
         on a 22-trade sample. Watch it; do not retune off one day.
- [ ] **Workstream C-P2 proper: walk-forward exit sweep, a BE-arming-threshold knob, finer
      `exit_reason` tags.** The MFE/MAE telemetry that blocked this now exists (E0.3) and the
      first sweep (`eafd7bc`) has been done, but on 22 replayable trades and without
      walk-forward. Opus-tier judgment task. **Owner has parked this** ("exit tuning is fine
      we can get back to it") — do not start it without asking.
- [ ] **Phase E2 step 13 — owner + Fable review of the index-futures segment before
      `index_futures_enabled` is ever flipped true.** Everything else is built and off. Note
      the coupled guard: a test fails the build if that flag is flipped while the
      `LiveBroker` futures-venue gap in `KNOWN_UNIMPLEMENTED_VENUE_METHODS` is still open, so
      the venue work must land with the flag flip, not after it.
- [ ] **Phase E2 remaining build items.** (a) Futures accurate P&L: `(exit−entry)×lot×qty`
      net of the full F&O charge stack, with SPAN+exposure margin sizing modelled correctly —
      the tricky part, and the owner's emphasis ("that's where the money is"). The
      contract-note gate was **lifted 2026-08-01**: source Zerodha's published F&O rate card
      and NSE's SPAN+exposure figures, build the model, and **state the source and date in
      the code**. A personal contract note is confirmation, not a prerequisite. (b) Encode
      the per-instrument delivery/tender rules into `delivery_calendar.py` (MCX staggered
      delivery for commodities; cash-settled index futures have none). **Intraday-only, no
      rollovers, never hold to delivery** (owner, 2026-07-24).
- [ ] **Close the `LiveBroker` futures-venue gap.** `open_futures_position` /
      `close_futures_position` are inherited from the paper simulator and called at
      `runner.py:1398`; in live mode that books a position with no order and no exchange
      stop. Declared and guarded, not fixed.
- [ ] **Wire `KiteVenue` into the live path.** It is a checked translation table today and
      says so in its own docstring. Rewiring every protective-stop call site sits behind
      three July incidents and wants its own phase with its own parity evidence.
- [ ] **Model the protective band in the backtester.** Now *declared*
      (`ExitPolicy.no_protective_band`) and reported, but the gap is real on the spot path,
      where the live SL/TP applies to the same series the backtest trades.
- [ ] **Phase E3 — MTF segment.** Pledge/funded delivery positions, broker interest/carry
      accrual modelled into P&L, multi-day lifecycle, margin/haircut. `engine/carry.py` is
      built and off; **its lifecycle semantics need owner intent, not more code.** Spec gate
      first, built last — interest accrual makes P&L multi-day, which nothing else here is.
- [ ] **Adopt `StrategySpec` in the engine.** Compiling is done (Phase E); adoption changes
      real-money entry and exit paths and needs its own parity evidence — the same
      compile-first / adopt-second order Phase G used.
- [ ] **Phase I — engine decomposition.** `EngineRunner` is ~2,450 lines. Deliberately lowest
      priority ("only refactor where boundaries become clearer"). The boundaries that became
      clearest during the migration are the **entry-gate chain** and the **risk governor**,
      and both sit in the middle of the live entry path — which is exactly why this is last.

## 6. Acceptance criteria

Every change in this workstream must satisfy all of the following. These are the commands,
not the intent. Run from `backend/`; `python` is not on `PATH` — use `.venv/bin/python`.

```bash
# Both suites. testpaths=tests, so bare pytest does NOT run research_tests.
.venv/bin/python -m pytest tests research_tests -q > /tmp/pt.log 2>&1; echo "EXIT $?"
grep -cE '^FAILED|^ERROR' /tmp/pt.log     # must be 0 — count BOTH, a broken fixture reports ERROR

# The ledger invariant. Must print LEDGER OK and exit 0.
.venv/bin/python scripts/dryrun.py 700

# Backtest invariants. Must print SWEEP OK and exit 0.
.venv/bin/python scripts/backtest_smoke.py
```

**The hard invariants, restated because this is the workstream that can break them.**

1. **The ledger reconciles to the paisa:** `cash == initial + realized − Σ(open entry_cost)`.
   `scripts/dryrun.py 700` asserts it and must print `LEDGER OK`. A change that moves cash
   without a matching trade row fails here and nowhere else.
2. **ARM gates entries only — never exits.** `mark_and_exit_positions` (the risk loop) marks
   every open position and fires SL/TP/square-off **regardless of arm state**; the gate lives
   in `process_entries`. Consequence: the persisted book must contain only positions the real
   account actually holds, or the engine will place real orders to flatten phantom rows.
3. **Paper-by-default is structural, not procedural.** `SafePaperKite` hard-disables every
   order/GTT/MF/convert endpoint and enforces a fail-closed route allowlist in `_request`.
   Live requires `PT_EXECUTION=live` ∧ `PT_LIVE_ACK=I_UNDERSTAND_REAL_MONEY` ∧
   `PT_PROVIDER=kite`, then a per-session ARM that resets to **disarmed on every process
   start**. Note the shipped `backend/.env` satisfies all three — the fallback is paper, the
   configuration is live. `SafePaperKite` is the *data* client; it does not gate
   `LiveExecutionKite`, which is what actually places orders.
4. **Live/backtest parity.** The trailing-stop ratchet and the strategy math are shared and
   parity-tested between simulator and live engine. A change to one must land in both, in the
   same commit. Any deliberate divergence goes through `ExitPolicy.no_protective_band(note=…)`
   — a test fails if someone declares one without a reason.
5. **The research plane stays isolated.** `research/guards.py` stays fail-closed; read-only
   bridges only. Work in this workstream must not create an `app/` → `research/` import.
6. **Deploys go through `scripts/deploy.sh`** (WS-06). Never bare-rsync.

**Further conditions specific to WS-02:**

- **Test-env safety lives in `backend/conftest.py`, the rootdir conftest, never deeper.** The
  shipped `.env` satisfies all three live gates and points at the real ledger, so any suite
  root without the guard resolves to live execution against production. Do not add env
  forcing to a subdirectory conftest.
- **A green test can be vacuous.** Before claiming a guard works, suppress its implementation
  and prove its own test goes red — and assert on the *path* of the violation, not just its
  clause. Five distinct vacuous-test shapes have already been caught in this repository this
  way.
- **Fixtures that build a `PaperBroker` must close it**, or the next `init_db(reset=True)`
  fails with "database is locked" — passing in isolation, failing in the suite.
- Never assert deployment state from prose, in this file or any other. **`curl /api/health`
  on the box and compare the commit** is the only answer; a `runtime_config` override can
  still make a correctly-identified build behave differently from its source (§7).
- **`GET /` is a separate check.** A broken SPA mount is invisible to `/api/health` — that is
  exactly how the `.env` outage hid.

**And the condition that overrides all of the above:**

> **Any change in this workstream stops for owner acknowledgement before it is deployed —
> regardless of green tests.** This is a real-money path. Green suites, a paisa-exact ledger
> and a passing smoke test are the *entry* requirement for asking, not a substitute for the
> answer. Two changes are sitting in exactly this state right now (§8).

## 7. Known technical debt

Things that work and are wrong. Each with the cost of leaving it and the trigger that would
force it.

**The architecture migration (phases A–H, `cc53bba`) is committed, verified, and NOT
deployed.** It has been blocked on owner acknowledgement for several sessions. It touches
sizing, exits and order routing, so the live-money rule stops it regardless of the evidence.
*Cost of leaving it:* every subsequent WS-02 change is written against a code shape the box
does not run, and the divergence grows with each session. *Trigger:* owner acknowledgement,
then WS-06 runs `scripts/deploy.sh` in a market-closed window. Note also that
`docs/2026-08-02-architecture-migration.md` still opens with "Nothing in this migration is
committed", which was true when written and is now stale — correct it when the deploy lands.

**The ten `runtime_config` overrides that differ from code defaults are deliberate owner
decisions. They are not drift and they are not a defect list. Do not "reconcile" them.** They
are hand-set from live trading experience, and the code defaults are the weaker information
— several were chosen precisely because the default was wrong for this account. **When this
table and `config.py` disagree, update the doc, never the box.** Do not clear an override to
make a shipped default take effect without the owner explicitly naming that key. Measured
from `/api/settings` on the VPS 2026-08-01:

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
by DB row** — clearing that override would silently stop the segment that booked 70 of the 72
real trades. It is the single most load-bearing row in `runtime_config`. And **the retuned
1.5% target lives only in the override**; the code default is still 0.03, so "retuned
defaults" describes the stop and the lock, not the target. Production also sizes ~40% larger
than the documented defaults (10k/14k vs 7k/10k) — a deliberate sizing decision. Any
reasoning about position size from `config.py` alone will be wrong; read the live value.
Clear an override only with `POST /api/settings/reset {"key": …}`, which also calls
`refresh_params()`; **never hand-edit the `runtime_config` table** — the route is what keeps
the running engine in step with the row.

**The exit policy does not work, and that is the largest open defect in the system.** Across
72 real trades `TARGET` has fired **zero** times. 45 exits were the owner closing manually
(`RECONCILED_EXTERNAL_EXIT`, net **+₹2,761**); the bot's own exits net **−₹2,927**. The
2026-08-01 sweep shows why: the largest favourable excursion ever recorded is 1.216% of
notional against a 1.5% target, so zero target exits was structural, not tuning. **This is an
entry-quality problem as much as an exit one** — the median trade travels further against you
(0.427%) than for you (0.286%). *Cost of leaving it:* "autonomous" is not a claim this
project can currently make. *Trigger:* the five-session no-touch trial (§8) producing a
sample the bot's own exits actually generated.

**`class LiveBroker(PaperBroker)` — no `BrokerCore` extraction.** Re-parenting the real-money
class and moving ~650 lines of ledger arithmetic is not verifiable in one pass. The
safety-critical half (every venue method explicitly defined, never inherited from the
simulator) is now enforced by the H7 guard rather than by hope. *Trigger:* a second live
venue, or the futures venue work.

**`LiveBroker` inherits `open_futures_position`/`close_futures_position` from the
simulator.** In live mode that books a futures position into the ledger with no order behind
it and no exchange stop. Unreachable today only because `index_futures_enabled` is `False`
with no production override. Declared in `KNOWN_UNIMPLEMENTED_VENUE_METHODS`; a test fails
the build if the flag is flipped while the gap is open. *Trigger:* E2 step 13.

**`KiteVenue` is not wired into the live path.** One checked translation table exists and the
call sites still spell their own product/exchange/GTT constants in places. *Trigger:* the
protective-stop rewiring phase; note three July incidents live in that code.

**The backtester does not model the protective band.** Declared and reported, but real on the
spot path where the live SL/TP applies to the same series the backtest trades. Also
documented and unfixed: no intrabar stop (live uses an exchange SL-M that fires mid-bar), no
partial fills, no pyramiding, structural survivorship in the curated universe, and **backtest
sizing has no relationship to live sizing** — one unleveraged full-capital position vs up to
four MIS-margin ones, so a backtest `return_pct` is not a live account-return prediction.
That last one is the biggest interpretive trap in the system.

**The broker's long-lived session (`broker.s`) is deliberately not context-managed.** It is
load-bearing: E0.2's auto-reanchor has exactly one correct implementation because the write
must go through the broker's own session. Context-managing it is a real refactor of the
ledger's identity map, not a hygiene tweak, and it should be done with the reanchor/snapshot
regression tests in front of it. It also leaks into tests — a live session holds a
checked-out connection no `dispose()` can reclaim.

**`generated_strategies` identity is still `key`, not `(key, version)`.** Redeploying an
edited strategy overwrites in place. The `version` column makes that *detectable*; making it
impossible needs the deploy bridge and the registry to both carry a version.

**Reconnect behaviour is untested against a dropped stream** — the live feed is polled, not
streamed, so there is no socket to drop. Token expiry *is* covered (the engine latches and
probes one instrument per loop rather than hammering every name). Recorded so the gap is
known rather than assumed closed.

**Charge rates are indicative.** `charges.py` rates must be re-verified against real contract
notes; `BFO_FUT` is currently set equal to NSE's because BSE's derivatives transaction charge
is unverified. The model must never under-charge — an optimistic cost model flatters
everything built on it.

**`provider_feed` has never produced a real measurement.** It was `{}` at deploy with markets
shut. Until a week of live sessions has run, "is Kite's candle history dirty?" is unanswered,
not answered clean.

**The `/api/health` 503 path is unexercised in production.** Proven in-process only;
confirming it live means deliberately stalling the risk lane on a real-money box. Treat the
next genuine incident as the test and check the probe went red.

## 8. Blockers

Cannot be resolved inside this workstream.

1. **Owner acknowledgement to deploy the architecture migration (phases A–H, `cc53bba`).**
   Committed, verified, and not on the box. **Blocked for several sessions.** It touches
   sizing, exits and order routing, which is precisely why the live-money rule applies. Until
   it lands, WS-02 develops against a shape production does not run.
2. **Owner acknowledgement to adopt the IR runtime in a live path** (RFC 0001 Appendix C(d)).
   The engine still calls `compute()`; `app/ir/` is imported only by its own tests. WS-01 has
   now produced the parity evidence — `expanding_z_v4` expressed as a graph and equal to
   `ExpandingZImpulseV4.compute()` bar for bar over 400 bars — so the technical objection is
   gone and only the acknowledgement is missing. Same rule, same reason.
3. **The five-session no-touch exit trial — owner-only, and no amount of engineering
   substitutes for it.** `TARGET` has fired zero times in 72 trades and 45 of those exits
   were the owner closing by hand. Until the bot's own exits are allowed to run and be
   measured, every exit-tuning result rests on 22 replayable trades and a simulation. It
   costs five sessions of not intervening.
4. **Phase E2 step 13 — owner + Fable review** before `index_futures_enabled` may be flipped.
   Several defaults (margin %, position/margin tiers, paper-only-first) need sign-off. The
   build landing does not change this.
5. **Phase E3 lifecycle semantics need owner intent, not more code.** The carry model is
   built and off.
6. **Owner has parked Workstream C** ("exit tuning is fine we can get back to it"). Do not
   start the walk-forward sweep without asking.
7. **VPS OS reboot** (5 ESM security updates) and the **1 GB → 2 GB droplet resize** are
   owner actions in a market-closed window. WS-06 surface, listed here because an OOM takes
   live positions with it.

## 9. Future work

Named, deliberately not scheduled.

- **Stock-specific options.** Parked by the 2026-07 product direction: equity + index on the
  *underlying* first, options fully supported but index-only and lowest priority. Production
  runs `max_open_positions=0`, which disables options entirely. *Trigger:* the equity/index
  path being demonstrably profitable and a reason to want convexity.
- **A synthetic-premium backtester with a real vol surface.** C6 was left inert deliberately
  (owner: pointless without a vol surface). *Trigger:* options coming off the parking lot.
- **A streaming market-data feed.** Would make a reconnect test meaningful and remove polling
  latency from the risk lane. *Trigger:* the polled feed being measurably the limiting factor
  on exit timing.
- **A `min_deployed` floor knob for the daily profit-lock.** Flagged by Opus at build time:
  early-day peak-concurrent-deployed can be small, so a low `lock_pct` may arm and halt a
  whole session on a tiny peak. *Trigger:* the lock arming on a day the owner did not want it
  to.
- **`Position.gtt_trigger_id` renamed to `protective_order_id`.** A Zerodha concept sitting in
  the ORM. A rename migration (batch mode, now available) plus call sites; kept out of the
  broker pass so the two would not land together. *Trigger:* a second venue.
- **Deployment-scoped reads.** Deliberately not done (Phase B): a missed read is a position
  nobody exits. It is the change that must land before a second deployment can trade the same
  instrument. *Trigger:* a second deployment.
- **Finer `exit_reason` taxonomy and a BE-arming-threshold knob.** *Trigger:* the no-touch
  trial producing a sample worth slicing.

---

*This document follows `docs/engineering/TEMPLATE.md`. §3 is a contract: changing an export
requires updating every workstream that lists it under Consumes, in the same commit. Tick a
box in §5 only with verified evidence, in the same commit as the work.*
