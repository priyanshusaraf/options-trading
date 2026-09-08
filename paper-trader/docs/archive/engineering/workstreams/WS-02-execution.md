# WS-02 — Execution & Brokers

**Status:** active
**Owner surface:** `backend/app/engine/` (except `readiness.py` → WS-06),
`backend/app/providers/` (except `replay.py` → WS-07), `backend/app/options/`,
`backend/app/strategy/`, `backend/app/backtest/`, `backend/app/api/`,
`backend/scripts/dryrun.py`, `backend/scripts/backtest_smoke.py`, `backend/scripts/exit_sweep.py`

`app/market_data/candles.py` is **consumed, not owned** — WS-07 owns the data seam. It is
described under Consumes because a re-fork of it is the defect worth naming, wherever it lands.
**Last verified:** 2026-08-09 · branch `codex/execution-foundation`

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
  `safe_kite.py`, `live_kite.py`, `mock.py`, `factory.py`; `replay.py` is WS-07's) and
  `app/market_data/candles.py`.
- **Options selection and pricing** — `app/options/picker.py`, `app/options/pricing.py`
  (index-only, lowest priority per the 2026-07 product direction).
- **Readiness of the money path** — `engine/readiness.py`, `engine/health.py` (the *logic*;
  the operational probe run is WS-06).

**Out of scope.**

| Not here | Owned by |
|---|---|
| The Component IR language (`app/ir/`), RFC 0001, the resolver/runtime/editor, IR strategy parity | **WS-01 Component IR.** WS-02 owns the *adoption* decision only, and it is blocked (§8). |
| DB models, sessions, Alembic revisions, `runtime_config` storage mechanics, retention | **WS-07 Infrastructure.** WS-02 declares which columns the money record needs; WS-07 owns how they are stored and migrated. |
| `scripts/deploy.sh`, the VPS, systemd, running `curl /api/health` against the box, droplet resize, OS reboot | **WS-06 Deployment.** WS-02 supplies the acceptance commands; WS-06 runs the deploy and measures the box. |
| The research plane (`research/`), DSR/PBO/N_eff, strategy generation, the search loop | **WS-03 Research.** The isolation rule is a WS-02 safety invariant, but the plane itself is not ours. |
| Frontend, cockpit, Settings UI, journal UI | **WS-08 Cockpit UI.** |

## 3. Interfaces

**Exports** — what other workstreams may depend on. Anything not listed is internal and may
change without notice.

| Export | Guarantee |
|---|---|
| `app/strategy/registry/expanding_z_v4.py` — `zscore`, `adaptive_threshold`, `drift_score`, `range_in_atr`, `impulse`, `directional_entry`, `displacement_lost` | The seven pure steps `compute()` is built from, extracted 2026-08-02 so WS-01's IR kernels compose the same implementation rather than a second copy. **Their signatures are stable**: WS-01's bar-for-bar parity test binds to them, and changing one breaks it by design. That is the guarantee, and it is the reason they are exported rather than private. |
| `app/strategy/registry/base.py::Strategy` + `CANONICAL_COLUMNS` | A strategy turns a candle DataFrame into **exactly four mandatory boolean columns** — `longEntry`, `shortEntry`, `longExit`, `shortExit`. Extra indicator columns are permitted and consumed by chart payloads; the four are enforced by `signals()`, which raises if any is missing. Direction/stop/target/sizing are **not** the strategy's job — the engine owns the risk layer. Auto-discovery is by module-level `STRATEGY`; default is `trend_impulse_v3`. |
| `app/strategy/registry/base.py::Strategy.version` / `pin_version` | Immutable content address (sha256 over key, code or composition, default params, risk model) from `app/strategy/identity.py`. Deterministic across processes and `PYTHONHASHSEED`. `display_name` is deliberately excluded — a rename must not mint a new artifact. |
| `app/strategy/identity.py::resolve_strategy(key)` | **Fail-closed** — raises `StrategyNotFound`. `get_strategy()` keeps a fail-open fallback for the legacy per-instrument path but logs (rate-limited) when it substitutes. `resolve_deployment_strategy` is fail-closed by design. |
| *(re-exported, owned by WS-07)* `app/market_data/candles.py` | **THE** candle→signal-frame converter and validator for the whole system. `runner._to_df` and `backtest._candles_to_df` are thin aliases over it. They used to be byte-identical copies, so a data fix could land in one plane and miss the other — do not re-fork it. Owned by WS-07; listed here because this workstream's aliases are the ones that would re-fork it. |
| `app/engine/charges.py::compute_charges` / `round_trip_charges` / `legs_for` | Zerodha segment-aware charge model (`NFO_OPT`, `NFO_FUT`, `BFO_FUT`, equity intraday/delivery). Direction-aware: `legs_for(direction)` charges a SHORT as SELL-to-open / BUY-to-cover. **All P&L, equity and backtest figures anywhere in the system are net of this stack.** Rates are indicative and must be re-verified against contract notes; the model must never *under*-charge (a test pins `BFO >= NFO`). |
| `app/backtest/` (`identity`, `cache`, `sweep`, `engine`, `metrics`, `live_equivalent`, `ratchet`, `premium`) | Underlying sweep with a schema-v8 content-addressed result cache and background thread. Reuse binds exact ordered candles and source context to strategy/transitive source, parameters, instrument economics, slippage, charges, event/exit policy and premium assumptions; an identity failure is cold. Warm rows reproduce every stored result value except row/run identity. Next-bar-open fills, no look-ahead, full direction-aware charge stack on both legs, execution cost modelled via `Settings.backtest_slippage_pct` (5 bps default; `0.0` reproduces every pre-`c7e5217` number exactly). **Interpretive contract: a backtest `return_pct` is NOT a live account-return prediction** — backtest sizing is one unleveraged full-capital position, live is up to four MIS-margin ones. |
| `app/backtest/exit_sweep.py` | Replays real booked trades against candidate exit parameters off MFE/MAE telemetry. Ambiguous stop-vs-target orderings are reported as a band, never guessed. |
| `app/engine/decision_kernel.py::decide_exit` / `ExitPolicy` / `ExitDecision` | The single pure exit decision shared by live options, live equity and the backtester. Levels are `None`-means-unset — never a `±inf` sentinel whose meaning flips with direction. Any deliberate divergence must be declared via `ExitPolicy.no_protective_band(note=...)` and is reported by `divergences()`. |
| `app/engine/risk_controls.py` (pure predicates) | Side-effect-free gate functions: `slots_available`, `in_reentry_cooldown`, `over_per_trade_cap`, `expiry_too_close`, `signal_already_evaluated`, `signal_too_old`, `before_entry_window`, `gap_halt_active`, `outside_trading_session`, `daily_loss_halt`, `round_trip_cap_reached`, `daily_profit_lock`. Pure in, pure out — testable without an engine. |
| `app/engine/event_risk.py` | The scheduled-event blackout table (EIA gas Thu / crude Wed with US DST, NIFTY Tue, SENSEX Thu, BANKNIFTY Wed, bullion options into expiry, stock earnings). **One rule table shared by engine, backtester and `/api/event-risk`** — do not add a second. |
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

**Depends on:** WS-07 (persistence, config). *Not* WS-06 — deployment is downstream of this
workstream, and "depends on" here means "consumes an export", not "cannot ship without".
**Blocked by:** owner acknowledgement for the architecture migration deploy (WS-06 cannot run
it without that); owner acknowledgement for IR runtime adoption (WS-01 supplies the runtime,
the live-path change is ours); owner time for the five-session no-touch exit trial. See §8.
**Currently blocking:** WS-01 (production adoption of the IR runtime lands in *our* engine
paths); WS-03 (the strategy registry contract and backtest kernels it evaluates against);
WS-08 (cockpit numbers, `ledger_drift`, health payload shapes).

### The execution lifecycle boundary — G-2 (2026-08-07)

**Implemented for live entries on 2026-08-09.** Migration `0014` adds immutable
`ExecutionIntent` and `ExecutionOrderEvent` records. Live options and equity entries commit an
intent and `SUBMIT_STARTED` before broker submission. Broker acknowledgement, cumulative fill,
protection acknowledgement, protected quantity and booked quantity are separate append-only
facts. Existing exits remain on the compatibility journal path.

The conceptual lifecycle, in full:

```
strategy evaluation                 a graph or a Strategy over a candle frame
        ↓
strategy decision                   the requested economic action
        ↓
execution planning                  contract selection, sizing, routing, allocation
        ↓
broker order(s)                     what is actually sent
        ↓
fill(s)                             what actually happened
        ↓
position / accounting state         the economic consequence
```

The strategy decision and execution plan remain collapsed for current one-leg strategies. The
broker request and its observations no longer collapse into `Position`: `Position` records the
economic result and links back through `entry_intent_id`.

**Three invariants make the collapse reversible.** These are what must not be eroded:

1. **`Position` is economic state resulting from execution.** It must not become the universal
   container for strategy intent, broker-order lifecycle, execution planning and fills. A row
   in `positions` answers "what do we own and what is it worth", and order-lifecycle state
   (working / acknowledged / partially filled / rejected / cancelled) belongs to the order and
   fill records — `order_journal` already exists for exactly this — not to `Position`.
   `gtt_trigger_id` is the standing counter-example and is already fenced behind
   `broker_protocol.protective_order_id()` for that reason.
2. **Strategy logic does not directly gain broker authority.** A strategy declares; the engine
   owns the arithmetic and the venue. `StrategySpec`'s sizing policy is a *declaration* the
   engine executes, and `PaperBinding`/`ShadowSource` deliberately carry identities only — no
   strategy object, no broker, no callable — so that "non-authoritative" is a property of the
   type rather than a naming convention.
3. **The durable entry intent does not replace canonical execution authority.**
   `execution_binding.strategy_for_execution` stays the one gate; the intent records what flows
   through it and never becomes a second strategy decision source.

**What this forbids in practice.** Not features — assumptions. Reviewers of L1.4 and later
slices should refuse code that hard-codes any of:

| Assumption | Why it must not deepen |
|---|---|
| one signal ≡ one order | a spread is one decision and several orders |
| one strategy action ≡ one `Position` | a two-leg intent produces two rows and one economic result |
| all order-lifecycle state belongs to `Position` | it belongs to the order/fill stage; see invariant 1 |
| an execution intent can only ever hold one leg | ratios, hedges and rolls are leg *sets* |

The implementation preserves this seam: order observations stay in the lifecycle log, while
`Position` carries only the resulting economic state plus the intent link. The current intent is
still one-leg; multi-leg execution remains a later extension.

**Not deferred out of neglect.** Multi-leg intent is a real product direction (2026-08-07
architecture review, direction H / Drill 3) and the venue layer (`broker_protocol.py`) was
already shaped for it. It is deferred because no strategy needs it yet, and building the object
before the second leg exists would be speculative.

### Cockpit lifecycle capability — 2026-08-08 (backend contract frozen)

`lifecycle_actions` was derived from `runner.paper_authority`, which holds only **active**
bindings, and returned a hard-coded `("pause", "retire")`. A staged or paused deployment is not
in that map, so it reported no actions at all — leaving a frontend to infer resume from
`state`, which is precisely the transition logic the backend must own.

Fixed by asking the owning services. `paper_authority.TRANSITIONS` and
`shadow_deployments.TRANSITIONS` are capability tables sitting beside the guards they describe,
with `permitted_transitions()` / `transition_requirements()` as pure accessors. The cockpit now
reads the deployment **row** (via each service's own `listing`) rather than the in-memory active
map, so every state reports truthfully and an instrument with only a staged or paused deployment
still appears in the view.

They are descriptions, not a second state machine, and that is proven rather than asserted: a
parametrised test drives the real services from every state × every action and requires
`IllegalTransition ⟺ not permitted`. The one deliberate divergence — `activate` is legal from
`paused` but is named `resume` there, so an operator is not offered two buttons for one
transition — is listed in the test as a documented synonym.

Two tables, not one, because the planes differ: paper `retire` requires `restore_strategy_key`
(where authority returns), shadow `retire` requires nothing. A shared table would have to
over-promise on one of them. `lifecycle` and `shadow_lifecycle` are separate keys for the same
reason.

`entry.complete` stays **`false`** — unchanged and deliberate. Closing it needs the runner to
record its skip reason, which touches the hot entry path and belongs to its own slice. The
frontend contract for both is in
[WS-08 §3a](WS-08-cockpit-ui.md); research status may raise operator attention and may **not**
alter lifecycle capability.

## 4. Completed

### The second ExecutionVenue — Dhan, and what it proved about the seam — 2026-08-10

`KiteVenue` implementing `ExecutionVenue` proved nothing about the protocol: one adapter cannot
distinguish "a neutral contract" from "Kite's shape with neutral names on it". `DhanVenue`
(`app/engine/dhan_venue.py` + `app/engine/dhan_order_client.py`) is the second, written from
https://dhanhq.co/docs/v2/ read at the time of writing rather than from the first adapter.

**The seam held.** Every protocol verb maps onto something Dhan actually does — with one
exception, and the exception is the most valuable thing in the slice.

**Dhan has no SERVER_TRIGGER, and the venue refuses rather than substituting.** Kite's GTT is a
broker-side conditional that can be attached to a position that already exists; that is what
protects every options position this system holds. Dhan has `STOP_LOSS_MARKET` — a resting order,
i.e. `RESTING_STOP` — and **super orders**, which bundle entry+target+stop into one construct
submitted together and cannot be attached to an open position. So they are not a substitute.

Placing a `RESTING_STOP` when the broker asks for a `SERVER_TRIGGER` would *look* like it worked
— the position does end up protected. It is refused anyway, and the reason is correctness rather
than purity: the two have different ids (an order id vs a trigger id), different margin, and
different reconciliation. `protective_stop_state` would report a fill that never happened, and
the check deciding whether the bot may re-enter a contract reads exactly that. The refusal fires
on **every** verb, not just placement — a stale id from a previous session reaches modify, cancel
and read directly.

**Consequence, stated rather than discovered at 09:15: an options deployment cannot run on Dhan
execution in this build.** Intraday equity can. The venue seam existing is what lets that be a
stated capability fact instead of a surprise.

Other differences that each return a *plausible wrong answer* rather than an error:

* **`TRADED` is the terminal fill, not `COMPLETE`.** A status map copied from Kite reads every
  filled Dhan order as still working, and `execute_order` polls to TIMEOUT on an order that
  filled instantly — which the caller must then treat as possibly-working and refuse to replace.
* **Modify is `PUT` and cancel is `DELETE`**, where Kite POSTs to action paths. Assuming Kite's
  shape returns 404/405, and a failed protective-stop modify leaves the exchange stop stale at
  the old trigger while the internal one ratchets — the 2026-07-13 SUZLON class.
* **`GET /orders` is a bare JSON array.** The transport permits a list only where a list is
  documented; market-data `post` still refuses one so the error names the shape rather than
  surfacing three frames later as an `AttributeError` on `.get`.
* **Dhan answers 200 with a REJECTED order.** Returning that id as a successful placement leaves
  the caller polling an order that will never work — and, for a protective stop, believing the
  position is backstopped when nothing is resting. Raised instead.
* **`correlationId` is 30 chars**; our durable intent tag is 20, so attribution survives the
  second broker. An over-long tag is refused rather than truncated — a truncated tag is an order
  nobody can attribute, silently.

```
pytest tests/test_dhan_venue.py tests/test_dhan_adapter.py → 24 + 24 passed
scripts/dhan_venue_mutations.py → 13/13 reddened · restored byte-identical
```

`test_no_unconsumed_mechanisms` then failed the build on a `dhan_product_for_charge_segment`
helper written "for symmetry" with `kite_venue` that nothing called. **Deleted rather than
exempted** — writing a mirror function because the other adapter has one is precisely how the
defect this workstream keeps paying for gets in.

**Not wired, deliberately.** `brokers.py` keeps `venue=None` for Dhan: `make_broker` can build no
Dhan order client yet, and a registry claiming a venue would disagree with the one place that
decides. It is registered in the same slice that makes it buildable — which needs `make_broker`'s
`conn.broker != "kite"` refusal replaced by `brokers.venue_adapter(...)`, and that file is under
concurrent execution-safety review.

### Independent security review, and the hole it found — 2026-08-10

The first genuinely independent read of this session's work. Its top finding is the reason the
"a reviewer should not be the author" rule exists.

**HIGH — revoking a connection did not stop orders.** `OwnedConnectionStore.live_connection`
returns a `token_source` that yields `None` when the row is revoked, the vault key has rotated,
or the credential cannot be read. **Three docstrings — two of them mine, in
`connection_store.py` — asserted that a `None` meant the order was "refused unauthenticated".
No such mechanism existed.** `KiteOrderClient._sync_token` read

```python
if tok and tok != self._last_token: ...
```

so a `None` was discarded and `self.kite` kept the token set at broker construction. The owner
could revoke a compromised credential, see `CONNECTION_REVOKED` in the log, and the engine would
keep placing **real orders on that account** until someone restarted the backend — with every
health check green.

This is the codebase's defining defect, third shape: a mechanism that *has* a caller, where the
caller discards the value. The mutation sweeps could not see it because they mutate a module and
run that module's own tests; the tests stopped at the store boundary, asserting `None` and
calling that a refusal. `test_a_missing_vault_key_refuses_the_order_rather_than_sending_it_unauthenticated`
was named for a behaviour it never checked.

Fixed: `_sync_token` now distinguishes **never authenticated** (unchanged — fails at Kite's own
auth check, the pre-existing safe path) from **withdrawn** (had a token, now gone), and the
second clears the cached token and raises `CredentialWithdrawn`. Tests reach the wire client now,
not the store.

**MEDIUM — the documented way to configure the vault key did not work.** `credential_vault` read
`os.environ` only, while `.env.example` (added the same day) told the operator to put
`PT_CREDENTIAL_KEY` in `backend/.env` — which pydantic-settings reads *itself* and does not
export. `available()` returned False while the variable was demonstrably set, and the error said
"is not set". Fail-closed, so not a hole, but an operator who cannot make the documented path
work is an operator inventing a workaround around a credential vault. Now read from the
environment first, then settings.

**MEDIUM — an explicitly empty owner id resolved to the real owner.** `""`, `"   "` and `None`
all became `"owner"`, the identity holding the live Zerodha credential — and **a test of mine
pinned that as intended**, on availability grounds. The reviewer was right and I was wrong: the
argument being *omitted* is the single-owner default and is fine; an argument *passed* as empty
is a caller bug (a header parsed to `""`, an unpopulated principal), and defaulting it is
principal substitution the moment routes exist. Now refused, and the duplicate copy of the same
fallback in `connection.py` is gone.

**LOW, fixed:** a `CredentialDecryptionFailed` escaped `token_source` into the order path — where
`order_executor` turned a recoverable auth condition into a durable reconciliation-required
blocker — and carried `key_id()` into `/api/logs` and Telegram. Now caught and turned into the
same withdrawal refusal. `list()` is bounded at the query. A docstring claiming the IDOR log line
"records the distinction" was false and would have been unsafe if made true, since `/api/logs`
serves the buffer to callers; corrected to say the distinction is recorded nowhere reachable.

**MEDIUM, NOT fixed — recorded as a blocker instead (§5).** `broker_connections` is the only
money-plane table with an `owner_id`. `unresolved_entries` recovers on
`(deployment_id, account_scope, connection_scope)` with no owner, while the new
`(owner_id, scope)` uniqueness makes two owners holding `kite:legacy` legitimate. Not reachable
today, but the constraint that permits the collision shipped before the query that must handle
it. Fixing it is an owner column across the money plane plus a recovery-predicate change — its
own reviewed slice, and a prerequisite for a second owner.

**Clean, per the reviewer:** cross-owner reads in the store (no unscoped helper exists, and the
late `token_source` re-filters on owner and status so the check does not go stale); credential
leakage into payloads (`to_dict` emits a bool, nothing in `app/api/` imports the model);
fail-closed totality of the vault; `key_id()` as a fingerprint; IDOR timing and the uniqueness
constraint; migration 0015; and transport-layer credential handling in both new adapters.

```
scripts/tenancy_mutations.py → 17/17 reddened · restored byte-identical
  new: withdrawn-token-silently-discarded · withdrawn-token-not-cleared-from-the-wire-client
       dotenv-key-ignored-again
```

**The execution-safety review did NOT run** — that agent died on a session limit before reading
anything. The venue boundary, the protective-stop re-route and the restart-recovery paths have
still had no independent reader.

### The ADR claimed a durability it never had — 2026-08-10

Recorded as a completed item because the correction is the deliverable, not the bug.

ADR 0015 §3 was written and accepted asserting, under **Enforced now**, that "the money plane
commits with `synchronous=FULL`". It never did — `app/db/session.py:36` sets `NORMAL`. The claim
survived its own review, a 3,996-test suite and four mutation sweeps, because **nothing anywhere
connected the sentence to the pragma.** It was found by the owner asking whether the three-plane
structure was actually being complied with, which is not a control.

This is the codebase's defining defect arriving somewhere the existing guards structurally
cannot look. `test_no_unconsumed_mechanisms` inspects callables; the mutation sweeps inspect
tests. A *durability posture stated in prose* has no callable to have no callers.

It was also **unimplementable as written**, which is the more useful half. `PRAGMA synchronous`
is per connection, and all three planes share one SQLite file and one engine — so `FULL` for
money-plane commits would put an fsync on every bulk backtest write too, the exact coupling the
plane split exists to remove. The sentence described something the topology cannot express.

**What was done:** the ADR is corrected in place (both corrections it now carries are recorded
rather than edited away), F-2 is moved to its real home — fixed by the physical split, or by a
deliberate *global* move to `FULL` with the write benchmark re-taken, which is the ordering the
failure-mode review already gives it — and `tests/test_durability_posture.py` now pins the
posture in both directions. It does not assert the posture is *correct*; it asserts it is what
the ADR says, so the two cannot drift again.

```
scripts/durability_posture_mutations.py → 5/5 reddened · restored byte-identical
  including "the-false-adr-claim-comes-back" — the original defect, replayed
```

**Still open and live:** under `synchronous=NORMAL` with WAL, a committed money transaction
survives a process crash and **not a host failure**. That is F-2, unfixed, and the correction
above makes it visible rather than resolved.

### Durable per-owner connections, and the plane that holds a credential — 2026-08-10

WS-02 §5 blocked this on "the three-plane database ADR". That ADR is now written and accepted —
**ADR 0015** — and this is what it unblocked.

**The decision that mattered** was not the plane split in general but *which plane holds a broker
credential*, and the three honest readings disagree. By recovery cost it is user-plane or lower:
lose it and the user re-authenticates, and Kite tokens expire every morning anyway. By
confidentiality it is in a class of its own. By **blast radius** it is money — a row here is the
authority to place real orders on a real account. Money won, with two practical supports: it
keeps `ExecutionIntent.connection_scope` and its connection inside one plane (attribution stays
a join rather than a hope), and "who changed this credential, and when" is an audit question that
the money plane already answers with append-only history rather than with a backup.

**Writing the plane check immediately falsified the ADR.** Rule 2 said "no foreign key crosses a
plane boundary"; the schema already broke it **seven times**, all one shape — a money-plane
deployment referencing the user-plane artefact it runs. Those relationships are correct; only
their enforcement mechanism is the problem. So the rule became a **ratchet**: the seven are
enumerated in `planes.py::GRANDFATHERED_CROSS_PLANE_FKS`, every new crossing fails the build, and
that set is now the countable price of the physical split rather than something discovered
mid-migration. The ADR records the correction rather than editing it away, because the sequence
is the point — the rule came from reasoning, the check came from the rule, and the code was right
about what exists.

**What shipped.** Migration `0015` (head is now 0015, not the 0013 the rules file still claims)
adds `broker_connections`: owner-scoped, capabilities stored per connection, revocable. No
foreign keys in either direction — deliberately, because an intent must survive the deletion of
the connection that authored it, and a live order whose connection row is gone is still a live
order.

* **`OwnedConnectionStore`** fixes the owner at construction. There is no method on it that can
  return another owner's connection, because the alternative is a helper that "just needs the id"
  and a caller who forgets. "Does not exist" and "belongs to someone else" are the **same error**;
  distinguishing them confirms another owner's connection exists, and an integer id is guessable.
* **`credential_vault`** is AES-256-GCM with the key from the environment, never a row — a
  database file is rsynced by `deploy.sh`, backed up and copied between environments, so a
  plaintext token in it *is* the account. AEAD rather than plain AES so a tampered ciphertext
  fails rather than decrypting to something an attacker chose. No key is a **refusal**, not a
  fallback to plaintext. Every ciphertext records which key wrote it, so a rotation can find its
  unwrapped rows instead of discovering them one failed decrypt at a time at 09:15.
* **`PT_EXECUTION_CONNECTION`** names a stored connection and outranks `PT_EXECUTION_PROVIDER`,
  because a stored connection is an explicit act by an owner where the env var is a deployment
  default. Naming one that does not exist, or that is revoked, **refuses** — falling back would
  place real orders through a credential the operator did not choose, with every health check
  green.
* The credential is read **late, through its own short-lived session**, not from one closed over
  at build time. The pool is 15 connections against a 40-thread worker pool and a `Connection`
  outlives the request that built it — holding a pooled connection for the life of the process is
  the shape behind the 2026-07-23 collapse.

```
pytest tests research_tests   → 3,990 passed · 0 failed · 6 skipped
scripts/tenancy_mutations.py  → 14/14 reddened · restored byte-identical
python -m app.db.migrate head → 0015
```

The sweep initially found **three unguarded behaviours**, none visible by reading the code: the
late credential read's owner filter was unreachable by any test, an explicitly-empty owner id
(`""`/`None` from a settings field or a principal) bypassed the legacy-owner default, and a
missing stored connection silently fell back to the environment. All three are now covered.

**Not done, and it is the honest boundary of "commercial access".** There is still no
authentication: `principal.py` resolves one shared bearer token to one owner, and `owner_id`
defaults to that same identity everywhere. What exists now is *resource ownership and isolation
on the connection table* — the dimension, enforced and tested — not multi-user login, signup,
entitlement tiers or billing. Those need the frontend the owner has gated (#7) and a decision at
owner gate #6.

### The broker fleet: a registry, split routing, and a third adapter — 2026-08-10

The owner's correction reframed this workstream mid-session: **every major Indian broker is in
scope for v1, not one second broker.** That changes what the valuable artefact is. With seven or
more adapters the failure mode is not a bug in one of them — it is seven slightly different
answers to the same question — so the registry and its contract matter more than any single
adapter.

**`app/providers/brokers.py`** is now the single answer to "which brokers does Strategy OS
support", with one rule the rest of the system leans on: *a broker is SUPPORTED only if its
adapter exists and passes the conformance contract.* Everything else is `PLANNED` and is refused
at selection with a message naming what is missing. `tests/test_broker_registry.py` fails the
build in **both** directions — a SUPPORTED broker whose adapter is missing, and a PLANNED broker
that has quietly grown a working one. A registry is the most attractive possible home for this
codebase's defining defect, and a row in it is a claim until a test makes it a fact.

Registered: `kite` and `upstox` and `dhan` SUPPORTED; `angelone`, `fyers`, `fivepaisa`, `icici`,
`kotak`, `groww` PLANNED with their documentation URLs located. `provider_named` now reads the
registry instead of repeating it.

**Split routing is proven, which was the actual gate.** `.claude/rules/providers-brokers.md`:
*"A second data adapter does not prove split routing until a test selects market data from one
connection and execution from another."* `tests/test_split_routing.py` sets `PT_PROVIDER=upstox`
and `PT_EXECUTION_PROVIDER=kite` and lets the composition root resolve both roles itself —
prices from Upstox, the order credential from Zerodha, the tick grid from the execution side
(Upstox has no `tick_size` at all, so a tick source pointing at the data connection would be
`None` and every trigger would fall back to the 0.05 grid that caused the 2026-07-15 incident).

**Upstox** came back from the parked branch `58436bb`. Its docstring had honestly said the
mixed-provider claim was not yet true; that seam now exists, so the docstring was corrected
rather than left to ship as a lie. Restoring it required making `get_option_chain`/`option_ltp`
**concrete with a `None` default** instead of abstract — a data-only adapter was previously
impossible to *construct*, which contradicted this repo's own rule. That opened a hole in the
same movement (a wrong base default is invisible to `check_no_undeclared_working_capability`,
which skips inherited methods), closed by a new tier-1 obligation.

**Dhan** is the third adapter and the one that proves the contract is not Kite-shaped. Written
from https://dhanhq.co/docs/v2/ read at the time of writing, and it differs in four ways that
each return a *plausible wrong answer* rather than an error:

* the response is **columnar** — six parallel arrays, where the other two send rows. A
  row-oriented parser does not raise; it reads floats out of the `open` array as candles.
  Ragged columns are refused rather than zipped, because zipping fabricates candles from mixed
  rows and nothing downstream could detect it;
* intervals are integers and the set is **incomplete** — 1/5/15/25/60 only, so `3minute`,
  `10minute` and `30minute` are genuinely unservable and are refused. A nearby substitute is
  available here in a way it was not for Upstox, which makes the temptation worse;
* `toDate` is **non-inclusive** on the daily endpoint — passing today's date drops the entire
  current session from a completely successful-looking response;
* **two credentials**, `access-token` and `client-id`, named separately in the failure because
  they look identical from outside and have different fixes.

Dhan also gets the instrument-master correction: **no hand-typed security ids.** A wrong id does
not raise — it prices a different real company, forever, with every layer above reporting
health, and the numbers are unverifiable by inspection. The master loads from Dhan's published
scrip CSV, and an unloaded one resolves nothing, so the connection has no coverage rather than
wrong coverage.

```
pytest tests/test_broker_registry.py tests/test_split_routing.py \
       tests/test_provider_conformance.py tests/test_upstox_adapter.py \
       tests/test_dhan_adapter.py                            → 90 passed
conformance now runs SIX cases: mock · replay · kite · kite-MCX · upstox · dhan
scripts/split_routing_mutations.py → 8/8 reddened · restored byte-identical
```

The sweep initially found **three unguarded behaviours** — an unmapped interval silently
rounded, the intraday endpoint never read, and a base `option_ltp` inventing a price. None was
visible by reading the code; all three are now covered.

**Not done:** no second *execution* venue. Upstox and Dhan serve data and declare no execution
capability, and `make_broker` refuses a non-Kite connection outright. That remains the wall, and
it is now a bounded one.

### The venue seam gets its first caller — 2026-08-10

`ExecutionVenue` (`app/engine/venue.py`) and its Kite translation (`app/engine/kite_venue.py`)
were declared in phase F and then **called by nothing**. `kite_venue.py`'s own docstring said so
plainly — "deliberately NOT wired into the live path yet" — which makes it an honest instance of
this codebase's defining defect rather than a hidden one, but an instance nonetheless: a boundary
that no code crosses is a boundary that has never been shown to hold, and a second broker could
not reach the engine through it.

`LiveBroker`'s protective-stop family now goes through the seam. It asks for a
`ProtectiveStopKind.RESTING_STOP` or a `SERVER_TRIGGER`; the venue decides that Kite spells those
`SL-M` and `GTT`. Six Kite-only verbs left the broker: `place_stop_gtt`, `place_stop_order`,
`modify_stop_gtt`, `modify_stop_order`, `delete_gtt`, `gtt_status`.

Two decisions worth keeping:

* **The venue is passed, not defaulted, at the composition root.** `broker_factory` builds
  `KiteVenue(client)` and hands it over, so the one line that will choose between two venues is
  in the place that already chooses between two connections. `LiveBroker` still defaults to
  `KiteVenue` when none is given, which is what keeps several dozen existing tests holding fake
  Kite clients working unchanged — the adapter is a pure delegator, so wrapping a fake changes
  nothing the fake observes.
* **The kind is carried, never inferred at the wire.** A resting SL-M is cancelled through the
  order endpoint and a GTT through the GTT endpoint; sending either to the other's is rejected by
  Kite. `test_each_cancel_carries_the_kind_that_picks_the_endpoint` fails if the two collapse.

**Evidence.** `tests/test_live_broker_speaks_no_kite.py` (7 tests) asserts both directions: the
six verbs are absent from the broker's executable lines (parsed by AST, not grepped — the log
strings the operator reads on their phone still legitimately say "GTT" and "SL-M"), *and* the
broker really dispatches to a recording venue while a client that raises on any Kite verb sits
underneath it. A second test guards the guard: if `KiteOrderClient` renames a verb, the watched
set silently stops watching and the file would pass forever.

```
suppression sweep (scripts/venue_seam_mutations.py) — each verb put back, one at a time:
  RED  gtt-place-back-to-kite · slm-place-back-to-kite · gtt-cancel-back-to-kite
  RED  slm-cancel-back-to-kite · fired-back-to-kite-probe · cancel-kind-collapsed
  6/6 reddened · file RESTORED byte-identical
pytest tests research_tests → 3,895 passed · 0 failed · 6 skipped
scripts/dryrun.py 700       → RECONCILE 187,733.06 vs 187,733.06 · LEDGER OK
scripts/backtest_smoke.py   → net<gross where charged OK · SWEEP OK
```

**Not done, and named so this is not misread as a finished boundary.** The entry pre-flight still
reads raw `orders()` / `gtts()` inventory dumps off the client, and `exchange_for_segment` /
`product_for_segment` still put Kite exchange and product strings straight into `OrderRequest` —
so the broker still decides `MIS` rather than deciding `Tenor.INTRADAY`. That is the next slice
and it is recorded in `kite_venue.py`'s docstring, not only here.

Owner gate #2 — this changes the live protective-stop call path. Committed, **not deployed**.

### The execution role enters the conformance contract — 2026-08-10

`tests/provider_conformance.py` held every adapter to the market-data and account roles and to
nothing about execution. The reason was structural: the execution capabilities are the only ones
mapping to `None` in `capabilities._METHOD_FOR`, because `LIVE_EXECUTION` means "a live order
client can be built from this connection", not "I place orders myself" — so the structural check
could not falsify the declaration at all.

Three obligations now do, and no order is placed to establish any of them (a conformance run
that trades is one nobody dares execute):

  * **declaration coherence, both directions.** Execution without an order type leaves
    `plan_order` to assume Kite's answer at a venue that never agreed to it; an order type
    without `LIVE_EXECUTION` reads as tradable everywhere a human looks and is refused at the
    one place that decides, surfacing as "the bot silently stopped trading";
  * **a credential exists.** A provider declaring `LIVE_EXECUTION` with no `access_token`
    yields a `token_source` returning `None` forever — `make_broker` logs 🔴 LIVE EXECUTION
    ENABLED and every order is rejected unauthenticated;
  * **a real tick.** `ConformanceCase.non_default_tick` names an instrument whose tick is not
    0.05, because only such a symbol distinguishes "reads the venue's tick" from "returns the
    constant". That is the 2026-07-15 incident (2,437 SL-M placements rejected) as an adapter
    obligation. **A case omitting the field is itself a violation** — otherwise a new adapter
    drops the obligation by leaving a field blank.

The `_FakeKite` NSE dump gained an `LT` row at 0.10; a dump of only 0.05 rows made the tick
obligation unfailable. Evidence: four new liars in `_LIARS`, each caught by the clause it broke.
Suppression sweep — unregistering the `LIVE_EXECUTION` obligation reddens exactly
`liar-tokenless-executor` and `liar-blanket-tick`; unwiring the coherence check reddens exactly
`liar-execution-no-order-type` and `liar-order-type-no-execution`; file restored byte-identical.

### The execution connection seam — 2026-08-10 (phase 6, narrow)

`make_broker` read the order credential off the *data provider*
(`token = getattr(provider, "access_token", None)`), so "where do I read prices" and "whose
account do I trade" were necessarily one object. `app/providers/connection.py` makes the
execution role addressable on its own: a `Connection` carries broker, scope, declared
capabilities and a **late-bound** `token_source` (a value would freeze the daily Kite
re-login). `make_broker(provider, execution_connection=…)` accepts the two separately, and
`connection_for(provider)` reproduces the legacy single-connection derivation, so the Kite path
production runs is unchanged.

Two consequences beyond the seam itself. **A named connection that cannot execute now refuses**
(`ConnectionCannotExecute`) instead of returning a `PaperBroker` — the silent fall-back is
indistinguishable from trading and is why the Upstox adapter was parked. An *unnamed* one keeps
the historical fall-back, deliberately: mock and replay are not brokers and `PT_EXECUTION=live`
against them has always meant paper. And **`ExecutionIntent.broker` / `.connection_scope` now
carry the real connection** rather than the `"kite"` / `"kite:legacy"` constants every writer
passed — the schema and the restart-recovery query had named the connection since migration
`0014` while being fed one hardcoded value, the third shape of unconsumed mechanism.

**The binding (same day, second slice).** A seam with no caller is this repo's defining defect,
so the resolver landed with it. `PT_EXECUTION_PROVIDER` names the connection that places orders;
empty — production's value — resolves to `None`, which *means* unnamed and takes the legacy path
byte-for-byte. `configured_execution_connection()` runs at `EngineRunner.__init__`, the only
place that knows both roles. Three decisions worth keeping:

  * **a split connection gets its own scope** (`"<broker>:execution"`, never `kite:legacy`).
    Sharing the legacy scope would have a second connection's live entries recovered under the
    first connection's book after a restart — a silent cross-account mix;
  * **`provider_named` reuses the process singleton** when the two names match. A second
    `KiteProvider` would carry its own throttle (Kite's limits are per client, so two breach
    1 req/s together) and would never hold the token the OAuth callback set on the singleton;
  * **an unrecognised name refuses** (`UnknownProvider`) rather than defaulting to the mock.
    `get_provider`'s fall-through is documented and warned about at startup; a typo in a *new*
    setting silently routing real orders at a synthetic market is not.

`make_broker` also now refuses an execution connection whose broker has no order client — only
`kite` has one — instead of handing a foreign credential to a Kite endpoint. Over-declaring
`LIVE_EXECUTION` is a documented adapter lie that `provider_conformance.py` exists to catch;
this is the fail-closed answer if one gets past it.

Evidence: `tests/test_execution_connection.py` (11), plus recovery and money-record guards in
`tests/test_execution_lifecycle_recovery.py`. `scripts/connection_seam_mutations.py` proves
**11/11** guards go red on their own defect and restores every file by hash.
`pytest tests research_tests` → 3,883 passed, 1 failed (`test_shadow_deployment_engine.py::
test_the_managed_binding_does_not_change_authoritative_selection`, a `QueuePool` exhaustion
reproduced on unmodified HEAD in a clean worktree — not this slice), 6 skipped.
`dryrun.py 700` → LEDGER OK; `backtest_smoke.py` → SWEEP OK.

Explicitly **not** in this slice, with homes: account actors, leases and fencing (phase 7);
`spot_symbol`/`option_name` relocation (R2); market-data fan-in (R3); credential encryption
(phase 10); registering Upstox in the provider factory. Reasoning:
[`../reference/2026-08-10-account-role-seam-review.md`](../../../engineering/reference/2026-08-10-account-role-seam-review.md).

### Configurable live-entry order policy — 2026-08-09

Live **ENTRY** routing now has one closed operator setting: `AUTO`, `MARKET` or
`LIMIT`. The backend publishes those choices through `/api/settings`, and the Settings UI
renders the backend-owned list as a select. `AUTO` preserves the prior behaviour: options use
the book-aware router, while equity entries without a book snapshot remain MARKET. Explicit
`MARKET` retains the hard spread and known-thin-book vetoes; explicit `LIMIT` produces a
side-aware cap for both BUY and SELL entries.

Order purpose and side are separate inputs to the planner. `ENTRY + SELL` is therefore a short
entry, not a risk-reducing exit, while `EXIT` remains market-only. Kite option-chain quotes now
retain best bid and ask quantities, and the options runner passes ask quantity for BUY entries,
so a known thin offer cannot disappear between the provider and the forced-MARKET veto.

The durable request matches the venue request. `OrderRequest` rejects unsupported order types,
MARKET requests carrying a limit, and LIMIT requests without a finite positive limit. For a
valid LIMIT, `LiveBroker` resolves the venue tick and rounds the price **before** creating the
immutable execution intent; the adapter's send-time rounding is only a second, idempotent
guard. Live options and long/short equity pass the selected plan through the broker boundary,
and `ExecutionIntent.order_type` / `limit_price` record that prepared instruction before the
broker call.

Verification evidence: 186 focused backend tests covering configuration, planning, runner
routing, live broker integration, lifecycle persistence, request validation and Kite quote
mapping passed during implementation. The completed branch gate collected 3,712
backend/research tests: 3,706 passed and 6 expected skips. The frontend passed 223/223 tests,
TypeScript checking, and its production build. `dryrun.py 700` ended `LEDGER OK`, and
`backtest_smoke.py` completed 16/16 cells with `SWEEP OK`. This verifies the live-entry slice;
it does not widen the claim to the gaps below.

**Still open:**

- Paper and backtest fill models do not simulate a resting LIMIT; limit-touch parity remains a
  separate versioned fill-model slice.
- LIMIT time-in-force, automatic cancellation and any cancel/reprice policy are not defined.
  A timed-out order is reconciled and never silently changed to MARKET or resubmitted.
- Exits remain market-only on the legacy compatibility lifecycle; this slice changes entries
  only.
- Platform and deployment settings are consumed by the runner. Instrument-scoped
  `entry_order_mode` consumption is not implemented and must not be claimed.

### Durable live-entry lifecycle and protection boundary — 2026-08-09

- Entry intent and `SUBMIT_STARTED` commit before the broker call. Unclassified placement
  failures stay uncertain and block duplicate submission.
- Startup rebuilds unresolved entries from the lifecycle log under deployment, account and
  `kite:legacy` connection scope before replaying legacy journal rows.
- Cumulative partial fills book only the positive delta. Lower and duplicate observations do
  not shrink or double-charge the ledger. Options and equity resize protection to cumulative
  quantity before advancing the booked watermark.
- A filled entry clears reconciliation only after both `POSITION_PROTECTED` and
  `POSITION_BOOKED` cover the broker fill. A broker-returned protection ID is recorded as
  `PROTECTION_ACKNOWLEDGED` before the Position stores it.
- Live entry refuses before intent creation when protection is disabled, invalid, unreadable or
  unsupported. An unknown-ID GTT/SL-M outcome never auto-attaches by shape and never sends a
  replacement; it remains blocked for manual reconciliation.
- `KiteOrderClient.orders()` exposes normalized recovery fields only. `execution_metrics()`
  derives fill state, adverse slippage and four latency legs only from persisted facts.

Evidence: the final checkpoint collected 3,698 backend/research tests and completed with 3,692
passes plus 6 expected skips. The 700-tick mock run reported `LEDGER OK`; the 16-cell backtest
smoke reported `SWEEP OK`; migration head is `0014`. Exact commands are in `docs/CONTINUE.md`.
No live broker or deployment was contacted.

### Execution-state ownership — the binding contract (2026-08-04)

ADR 0012. **Six mechanisms already express "what strategy runs where"**, and nothing
reconciled them: `deployments.strategy_key`, `instrument_state.strategy_key`, watchlist
assignments, `strategy_lifecycle`, `generated_strategies`, and `graph_artifacts`. Adding a
seventh for IR-backed strategies would have been the second deployment model this project
has a standing rule against.

**The finding that organised the slice:** `resolve_deployment_strategy` has tests and **no
production caller** — verified by grep, recorded in the ADR — so the object the architecture
calls "THE primary execution object" does not decide what executes. The engine resolves per
instrument. That is the codebase's defining defect sitting under the deployment model itself.

`app/core/execution_binding.py` answers, for one instrument under one deployment: which
strategy key, at which content version, from which source, decided by which layer, why — and
whether that source may execute at all. It is a **description with a gate attached**, not a
new resolver: the engine's path is untouched, and an equivalence test pins that the
contract's answer and `get_strategy`'s are the same object for every assignment the engine
can hold.

**The gate.** `AUTHORITY_BY_SOURCE` maps source → may-execute; `ir_graph` is `shadow`.
Resolving such a binding raises `AuthorityNotGranted`. This matters because once Stage 2
registers a graph-backed strategy, nothing else would stop `POST
/api/instruments/NIFTY/strategy` from making it authoritative — the registry resolves it and
the engine trades it. Every owner gate in ADR 0011 now begins at one reviewed line, and a
mutation proves it: flipping `SOURCE_IR_GRAPH` to `AUTHORITATIVE` turns the guard red.

Failure posture differs by layer on purpose: a deployment pin that will not resolve raises
(a deployment is a promise about which strategy is trading); a per-instrument assignment
falls back but **reports** the substitution; a graph-backed key never falls back at either
layer.

`BINDING_MECHANISMS` names all six as `table.column`, with a test that each still exists, so
a seventh is a deliberate edit and a rename cannot leave the registry describing a schema
nobody has.

### Managed shadow deployment — L1.3A (2026-08-07, ADR 0012 §3.1)

The IR shadow pairing was runtime machinery: whichever graph happened to mirror an
instrument's authoritative strategy key, decided per scan, recorded nowhere, gone on
restart. Fine for one experiment, useless as a platform statement. It is now a server-owned
record, so the system can say — durably, after a restart, with every identity separately
attributable:

> this approved immutable graph version is deployed to this instrument at this interval in
> shadow mode, with this evidence lineage and this admission state

and it remains structurally unable to say the graph may influence an order.

| piece | where |
|---|---|
| record | `ir_shadow_deployments`, migration `0011` |
| lifecycle | `app/core/shadow_deployments.py` — staged / shadow-active / paused / retired |
| selection boundary | `execution_binding.shadow_source_for` |
| engine | `EngineRunner.shadow_deployments`, `refresh_shadow_deployments()` |
| contract | `GET|POST /api/ir-shadow/deployments`, `POST …/{id}/{activate\|pause\|resume\|retire}` |

**Authority is refused three times over, independently.** `AUTHORITY_BY_SOURCE` maps
`ir_graph → shadow`; the table CHECK-constrains `execution_mode` and `authority` so the
database will not widen them; and the service has no mode or authority parameter at all.
Any one alone is a convention a later edit could relax without anyone noticing. ADR 0012
§3.2 — paper authority — is **not built** and needs three reviewed changes to become
possible.

**Verified, not declared.** Activation re-derives the graph's content address from the
stored artefact bytes and re-checks the research decision through the read-only bridge;
every reload re-derives the address again. A binding whose graph moved is **dropped and
reported**, never repaired — silently rebinding to whatever bytes are there now is the
silent-substitution failure already closed in the registry, in selection and in attribution.
Evidence is verified once and recorded rather than re-read per reload, because the lineage
lives in the research plane's own database and a control-loop boundary is the wrong place
for a cross-plane read.

**One boundary, two sources, stated precedence.** `shadow_source_for` answers "what should
be observed here" from a managed deployment when one exists and the legacy key pairing
otherwise. The legacy pairing is kept and *named*, not silently retained: retiring it before
anything replaced it would take shadow coverage to zero, which is a worse outcome than
having a fallback somebody can see.

**Not a second deployment model.** The table has a foreign key to `deployments` and
describes an observer attached to a book, not a book: no orders, no capital, no arm state,
and the engine's authoritative selection never consults it. ADR 0012 §3.1a records why
overloading `deployments.strategy_key` — the original sketch — was the wrong shape.

Loaded at startup and at explicit refresh boundaries, never per instrument per tick; a test
pins that a full scan performs zero deployment reads.

### Execution attribution (2026-08-04, ADR 0012 §4.1)

**L1.2 canonicalised execution selection authority. This slice canonicalises execution
attribution.**

The defect: a stale assignment traded the default — the deliberate fail-safe — while the
position, and every trade row descending from it, recorded the key that *failed to resolve*.
Selection had been canonicalised; the money record had not. Demonstrated before the fix:

```
assert position.strategy_key == 'trend_impulse_v3'
E  AssertionError: assert 'a_strategy_that_was_withdrawn' == 'trend_impulse_v3'
```

The binding that produced a signal is now carried from the scan to the fill and is what the
position is attributed to, at both the intraday and futures write sites; the options path
already went through the resolved strategy. `Trade.strategy_key` derives from
`pos.strategy_key` at close, so the money record follows without a second change.

Three structural consequences:

- **`publish_signal` is the only door.** A signal state and the binding that produced it are
  written together. `process_entries` opens from `self.state` and attributes from the binding,
  so a state entry with no binding is a signal whose author is unknown — the entry paths refuse
  to open on one rather than guessing. Nineteen test call sites moved to this door; they had
  been constructing a state the engine cannot reach, and only line 597 of `runner.py` creates
  one in production.
- **A refusal withdraws the previous answer.** `self.state` survives a skipped scan, so
  refusing to evaluate without also dropping the last signal would let a refused instrument
  open on one produced while it was still authorised.
- **The identity is captured at the signal, never re-resolved at the fill.** The assignment can
  change in between; re-resolving would name logic that did not produce the trade.

**No schema change, no migration, no repair tool** — measured rather than assumed. All 72
production live trades carry either `NULL` (the documented "the default produced this"
encoding) or a registered key; none carries an unregistered one, so the defect was latent and
never fired. Where a row *could* be wrong the correct identity is not deterministically
derivable, so history is left untouched. Full evidence and the query in ADR 0012 §4.1b.

Evidence: 24/24 mutations reddened and restored (six new: raw-assignment attribution on the
intraday path and on the futures path, re-resolution at the fill, propagation dropped, a
refusal that keeps openable state, and authority inferred from the key's namespace). One of
the six was **vacuous on the first attempt** — it flipped the assignment from inside
`open_equity_position`, but the attribution argument is evaluated *before* that call, so
re-resolving at the write site still produced the right answer. Driving the scan and the
entry as separate halves of the tick is what actually exercises the window.

**A shared-state leak this slice uncovered:** five wiring test files pin a session time with
`r.provider.now = lambda: ...` on the process-wide provider singleton, at sixteen sites, none
restoring — so the last writer froze the clock at 09:20 and every later entry was refused by
the 09:30 window gate. Ten tests failed in the suite and passed alone, pointing at the
innocent test. Fixed once in the rootdir `conftest.py`; the leak is the shape, not the site
(ADR 0012 §4.1a).

### The engine consults the contract (2026-08-04, same ADR)

The slice above shipped a contract with no production caller — the very defect it described.
This closes that. `EngineRunner` now resolves **every** strategy-selection decision through
`execution_binding.bind`, and holds no other path: an AST guard fails the build if
`get_strategy` or `resolve_strategy` is called anywhere in `runner.py`, and a second guard
fails if the call to the contract is deleted. Both are AST checks, not greps — the runner
discusses these functions in prose, and a substring guard would be satisfied by a comment,
which is a vacuous-guard shape recorded twice in this project already.

**Equivalence first, authority second.** For every value `strategy_keys` can hold — unset,
the default, another registered strategy, a stale key — the engine selects the same
`Strategy` object as before. Only then does the gate change anything, and only for a case
that cannot occur today (no `ir.*` key is registered).

Three properties the wiring adds:

- **The decision is split from the lookup.** `bind` decides over values already in memory;
  `resolve_binding` is `bind` plus two DB reads. The engine resolves per instrument on a
  ~2.5 s loop, so consulting the contract costs no round-trip. One decision, two entry
  points, with a test that they agree.
- **The deployment pin has a production caller for the first time.** Read once at boot.
  `NULL` for the legacy deployment, so resolution is unchanged; deliberately not wrapped in
  a `try`, because swallowing an unresolvable pin would settle a contradiction in favour of
  the weaker claim.
- **A refusal skips the instrument and substitutes nothing** — not the default (silent
  substitution) and not an aborted scan (invariant 2). Every writer of an engine assignment
  — the strategy route, universe add, watchlist create, deploy bridge — calls
  `assert_may_execute`, and the API returns **409 with the reason** by catching the gate's
  own exception type rather than testing for a namespace.

**Found here, closed in the next slice:** selection went through the binding, attribution did
not — see below.

**Still not done, deliberately:** the smallest safe paper/shadow deployment architecture is
*designed* in ADR 0012 §3 and unbuilt. It needs owner approval before any of it becomes
authoritative.

Evidence: 18/18 mutations reddened and restored (six new: the runner call site, direct
resolution, silent fallback after a refusal, registry fallback for a graph key, unreviewed
source/authority pairing, the write-side gate). One of them exposed a **vacuous test** — the
obvious "assign a graph key and watch the engine refuse" never reaches the authority
re-check, because `bind` already refuses at resolution; the re-check is now proven against a
*forged* binding from a drifted resolver, which is the only thing it actually defends.

### L1 Stage 1 — the shadow lane (2026-08-04, engineering-closed)

Owner-approved as a **shadow-only integration**. `EngineRunner.scan_signals` now evaluates
the Component IR mirror of an instrument's authoritative strategy on the *same* frame the
authoritative strategy just consumed, compares the newest bar, and persists disagreements.
**The hand-written strategy remains the sole execution authority**, and nothing reads the
observation back.

| Piece | Where |
|---|---|
| observer (pairing, comparison, classification, frame identity) | `app/engine/ir_shadow.py` |
| record | `app/engine/ir_shadow_store.py`, `ir_shadow_divergences`, migration `0010` |
| numbers | `app/engine/ir_shadow_metrics.py` |
| read surface | `GET /api/ir-shadow` (no frontend — deliberately out of scope) |
| flag | `Settings.ir_shadow_enabled = False`, `runtime_config`-overridable, fail-closed |
| measurement / guard proofs | `scripts/ir_shadow_replay.py`, `scripts/ir_shadow_mutations.py` |

Pairing is by **authoritative strategy key** (`expanding_z_v4` → the `expanding_z` graph): a
graph run against an instrument on a different strategy would compare two different
strategies and call the difference a divergence.

Isolation is proven four ways — static transitive imports, every broker/order seam replaced
with a trap during a real scan, engine state identical with the lane on and off, and failures
injected at each layer leaving the authoritative output byte-identical. Nine mutations were
watched turning those guards red (`scripts/ir_shadow_mutations.py`). The harness immediately
earned itself: the obvious "leak into `self.state`" mutation is a no-op, because the observer
runs *before* the state entry is built — a guard that looked green for the wrong reason.

Measured: 110/110 settled bars agree (100%), zero unexplained disagreements, evaluation p95
3.8 ms, and 36.6 ms p95 per eight-instrument iteration = **1.46% of the 2.5 s signal budget**
against a 20% limit, with zero missed cycles.

**The admission contract (added at closure).** The measurement confirmed ADR 0011 conflict
#2: the graph's 302-bar warmup and the live admission guard disagree, and at
`history_days = 30` an NSE name on a **30m or 60m** interval yields ~286 / ~154 bars and can
never settle. Rather than shorten the warmup or widen the authoritative lane's history —
both ruled out of scope — the lane now decides admissibility **before evaluating**:
required history from the resolved IR contract, available history from the configured
timeframe and `history_days` via the segment's session length, rejection with a stable
explicit reason, no evaluation, no all-False output, no repeated in-hours refusal. Verdicts
cache per `(instrument, interval)` and re-decide on an interval change, so no restart is
needed. Admission is predictive, so three consecutive post-admission refusals **demote** the
pairing, naming both the expected and the observed bar count. Unknown interval or segment
fail closed.

**What Stage 1 is NOT.** It is not Stage 2: paper, staged or live adoption needs a separate
owner approval. And engineering-closed is not operationally validated — ≥ 20 live sessions,
richer recorded OHLCV, replay fidelity, long-duration shadow statistics and the
resident-memory measurement are **deferred by owner decision** and must be revisited before
authority promotion, production deployment or commercial validation.

Shadow coverage in production is **zero**: the default `trend_impulse_v3` has no mirror, and
assigning `expanding_z_v4` to an instrument is an authoritative-trading change. `GET
/api/ir-shadow` reports `coverage.shadowed`, `unmirrored` and `rejected` so absence cannot be
misread as agreement.

**Known gap, deliberately deferred.** `ir_shadow_enabled` is in `runtime_config.OVERRIDABLE`
but **not** in the frontend's `overridable.ts` snapshot or `settingsMeta.ts`, so it is a knob
the Settings screen cannot show — the failure mode `settingsMeta.test.ts` exists to prevent.
This is the cost of constraint 10 (no frontend in this slice), not an oversight: closing it
is two data entries in `frontend/src/views/`.

### L1 Stage 0 — the shared IR strategy adapter (2026-08-03)

`app/strategy/ir_adapter.py` presents a resolved Component IR graph behind the `Strategy`
contract. **It changes nothing the engine executes**: no order, paper, shadow or live path
consumes it, and a test asserts `app/engine/*` imports neither the adapter nor `app.ir`.

> **Superseded by Stage 1 (2026-08-04)** on that last clause only. The engine now reaches the
> IR through `app/engine/ir_shadow.py`, and the substring guard that phrase describes would
> have gone on passing while meaning nothing — the shadow module's name contains neither
> string. It was replaced by
> `test_the_engine_reaches_the_ir_only_through_the_shadow_lane`, which asserts the narrower
> thing that is still true: the shadow lane is the engine's only bridge to the IR, and the
> order path has no bridge at all. Everything else in this section stands.

Placement is deliberate. The adapter is *not* in `app/ir/`, because
`app/ir/strategies/expanding_z.py` already imports `app.strategy.registry` — its kernels
delegate to the hand-written implementation so the two planes cannot drift — and putting the
adapter inside `app.ir` would deepen that tangle. The language core (`app/ir/*.py`) imports
neither `app.strategy`, `research` nor `app.engine`, and an AST-based test enforces it.

Six silent-failure defects closed, each proven by a mutation that turns its guard red:

| Defect | Was | Now |
|---|---|---|
| Insufficient history | 134 real bars against a 302-bar warmup returned four all-False columns forever | `InsufficientHistory`, naming bars and warmup |
| `risk_model` | dropped, silently disabling the live ATR ratchet | carried from the graph, strictly validated, partial declarations refused |
| Backtest warmup trim | keyed off indicator columns the adapter never emits, so **nothing** was trimmed — 340 bars returned where 38 were settled (a latent invariant-4 violation) | `trim_warmup` honours a declared warmup; hand-written strategies keep the exact previous behaviour |
| Identity | key embedded the content address, so an edit orphaned every persisted binding | key is stable, version is the content address |
| Registry fallback | an unregistered `ir.*` key silently traded the default strategy | `IR_NAMESPACE` keys never fall back; hand-written keys keep their deliberate fail-safe |
| Frame contract | demanded all six OHLCV fields regardless of the graph | follows the graph's declared inputs |

The parity claim was rebuilt rather than inherited. The previous proof compared `evaluate()`
against the hand-written strategy over 400 bars of a **synthetic sine wave**, one instrument,
two of fifteen parameters moved — and **bypassed the adapter entirely**, so its masking,
frame contract and identity were outside the claim. `tests/test_ir_adapter.py` now exercises
the adapter itself on real recorded series across instruments, asserts the warmup mask
exactly, and covers every closed failure path.

**One correction worth keeping.** ADR 0011 originally called for a persistent `evaluate()`
cache. That was wrong: `Cache` is keyed on `node.cache_id`, fixed at resolution and carrying
nothing about the input data, so reusing one across frames returns the previous frame's
series — measured, all 18 nodes hit, every value stale. In a signal lane that is the worst
available failure, because it looks fast and healthy. A fresh cache per evaluation is
correct; a guard test pins the hazard.

Research now **subclasses** the shared adapter instead of duplicating it, inverting exactly
two declared policies: identity includes the content address (a search must tell hundreds of
candidates apart) and a short window is a result rather than an error. Attempting a straight
de-duplication is what surfaced that conflict.


Verified and committed work, newest first. Dates and SHAs are from `docs/ROADMAP.md` and
`git log`; where the roadmap records evidence, the evidence is kept.

**Architecture migration, phases A–H — `cc53bba`, 2026-08-02. Committed and verified.
NOT DEPLOYED (§8).** Eight additive phases, every one leaving existing behaviour
byte-identical and carrying a test that *asserts* that equivalence rather than claiming it.
Working record: `docs/reports/2026-08-02-architecture-migration.md` — frozen, and carrying a
stale-claim header since 2026-08-03: its opening line "Nothing in this migration is committed"
was written before `cc53bba` and is false.
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
  `runner.py:1411` calls them; in live mode that would book a futures position into the
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
`docs/reports/2026-08-02-execution-determinism-audit.md`. `kill()` ran `cancel_working_entries()`
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
`docs/reports/2026-08-01-backtester-audit.md`, all ten Phase-1 dimensions with verdicts cited to file
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
`docs/reports/2026-08-01-exit-sweep.md`, Workstream C P2. `scripts/exit_sweep.py` replays real trades
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
- [x] **Hold connections durably, per owner. DONE 2026-08-10** — the blocking ADR is written
      (ADR 0015, which places a credential in the money plane on blast radius) and
      `broker_connections` exists behind migration 0015: owner-scoped, AES-256-GCM at rest with
      the key in the environment rather than a row, revocable without a delete.
      `PT_EXECUTION_CONNECTION` names one and it takes precedence over `PT_EXECUTION_PROVIDER`;
      naming one that does not exist **refuses** rather than falling back, because the fallback
      places real orders through a credential the operator did not choose. A second connection
      is now a record.
- [ ] **BLOCKER FOR THE SPLIT CONFIG: there is no way to authenticate a non-data connection.**
      Found while fixing F4 of the 2026-08-10 execution review, and larger than F4 itself.
      `routes.py:147,158` reach `_runner(request).provider` — the **data** provider — for both
      `login_url` and `complete_session`. Under `PT_PROVIDER=upstox, PT_EXECUTION_PROVIDER=kite`
      that is the Upstox object, so "Connect Kite" cannot reach the connection that actually
      places the orders. The token-freshness fix makes the execution instance *adopt* a token
      that something else writes; it does not give the operator a way to write one.
      Closing this needs a per-connection auth route (`POST /api/connections/{id}/login`) and the
      UI to drive it — which is **owner gate #7**, so the backend half can be built and the
      frontend requirement written down, and no further.
      Until then the split config is usable only for a same-day process start, and
      `PT_EXECUTION_CONNECTION`/`PT_EXECUTION_PROVIDER` must not be set on the live box.
- [ ] **BLOCKER FOR A SECOND OWNER: carry `owner_id` across the money plane.** Found by an
      independent security review, 2026-08-10. `broker_connections` is the only money-plane
      table with an owner. `deployments` and `execution_intents` have none, and
      `execution_lifecycle.unresolved_entries` recovers live entries on
      `(deployment_id, account_scope, connection_scope)` with **no owner in the predicate**.
      Because `(owner_id, scope)` is unique rather than `scope` — deliberate and correct — two
      owners may both hold `kite:legacy`, and that collision is exactly the "silent cross-account
      mix" `providers/connection.py` calls the worst available failure. **Not reachable today**
      (one owner, one deployment, no route creates a second) but the constraint that permits it
      shipped before the query that must handle it. This is a prerequisite for onboarding any
      second owner, ahead of authentication.
- [x] **A second execution venue. DONE 2026-08-10.** `make_broker` no longer names a broker:
      `conn.broker != "kite"` became `brokers.build_live_venue(conn, settings)`, so the registry
      answers *which* client a connection gets and the composition root only decides *whether* a
      live path may exist. The refusal is unchanged — a broker with no order client in this build
      is refused rather than having its credential sent to another broker's endpoint — it is a
      lookup rather than a hardcoded string. `Connection` gained `secrets_source` for brokers
      needing more than an access token (Dhan requires `client_id` on every request and in every
      order body); it is deliberately separate from `token_source` so the full bundle is not put
      in front of the many callers that want exactly the token.
      **Dhan cannot serve an options deployment** — no GTT equivalent, so `DhanVenue` declares
      RESTING_STOP only and refuses SERVER_TRIGGER on every verb rather than substituting.
- [ ] **The remaining wall is smaller: the plain-order verbs.** The blocker
      this item used to describe is gone: `live_broker.py` no longer imports Kite product or
      exchange helpers, its protective stops go through `ExecutionVenue`, and
      `tests/test_live_broker_speaks_no_kite.py` fails the build if the vocabulary returns
      (2026-08-10, §4). What remains is genuinely adapter-shaped: implement `ExecutionVenue`
      for one more broker, register it in `app/providers/brokers.py`, and replace
      `make_broker`'s `conn.broker != "kite"` refusal with `brokers.venue_adapter(...)` — the
      function already exists and already refuses correctly.
      **Pick the broker by auth model, not by popularity.** Dhan is the cheapest first
      execution venue in the registry because its token is long-lived: every other candidate
      (`angelone`, `fivepaisa`, `kotak`) is TOTP-session, which makes the credential lifecycle
      a second piece of work stacked on the venue itself.
      Still-Kite-shaped above the seam, and this is now the whole list: `orders()` /
      `find_fill()` / `status()` are neutral by name but go direct to the client, and the entry
      pre-flight's raw dumps are routed but the *plain-order* family is not.
- [ ] **Fill out the broker fleet.** `app/providers/brokers.py` carries six `PLANNED` rows —
      `angelone`, `fyers`, `fivepaisa`, `icici`, `kotak`, `groww` — each with its documentation
      URL located. Each is now a bounded task: a data adapter plus a conformance case, and the
      registry test refuses to let a row claim `SUPPORTED` without both.
      **Read the broker's published API at the time of writing; never write an adapter from
      the shape of the previous one.** Dhan proved why — columnar payloads, an incomplete
      interval set, a non-inclusive end date and two credentials, none of which resembles
      Upstox and every one of which returns a plausible wrong answer rather than an error.
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
      `runner.py:1411`; in live mode that books a position with no order and no exchange
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
`docs/reports/2026-08-02-architecture-migration.md` still opens with "Nothing in this migration is
committed", which was true when written and is now false. That report is frozen; a stale-claim
header was prepended 2026-08-03 rather than editing the body.

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


### Execution-book isolation — L1.3B (2026-08-07, ADR 0012 §6)

**The question this answers:** can paper execution create positions, trades, P&L, journal
records, reconciliation state and recovery state without contaminating live execution or
live accounting? Before this slice the answer was no, and the reason was not subtle — the
`mode` column was stamped on every fill and consulted by **no** position query, and it did
not exist on `capital_state` or `equity_snapshots` at all.

**The book is the execution mode.** No new abstraction was introduced; `app/core/
execution_book.py` gives the existing discriminator a name, a resolver and reach.
`resolve_book` fails closed to `live` — the book with the strictest rules — so an unset,
malformed or missing mode never inherits paper's permissions. `getattr(broker, "MODE",
"paper")`, the shape it replaces, had that backwards.

**Why a migration was needed at all.** `capital_state.cash` and `realized_pnl` are
aggregates mutated in place on a single row, so no `WHERE` clause could stop a paper fill
debiting the live ledger. A predicate cannot partition a number. Migration `0012` adds
`book` to `capital_state` (with a partial unique index) and `equity_snapshots`, and
back-stamps nothing: the one pre-slice ledger is attributed exactly once, from the `mode`
already stamped on the money rows it produced, and left alone when that evidence
contradicts itself.

**The chokepoint.** `broker.open_positions()` / `position_for()` are how all ~35 production
call sites reach a position — every square-off, every stop, every restart reconstruction,
every risk read. Scoping those two methods scoped all of them.

**Isolated vs cross-book, stated rather than assumed.** Isolated: position lookup, open
positions, exits, restart, deployable capital, the daily-loss breaker, the round-trip cap,
`capital_dict`, `account_pnl`, re-anchor, ledger drift. Cross-book on purpose:
`universe_resolver`'s in-use guard, the reporting surfaces, the journal feeds, and
`daily_account_snapshot` (which describes the real account, not a book). The equity curve
stays unscoped by default because pre-slice points carry no book and scoping would drop the
entire history from the cockpit.

**The one deliberate regression, and its compensating control.** Book-scoping the exit lane
means a live position left open while the paper book runs is managed by nobody — and hard
invariant 2 says not getting out is the worst failure there is. It is still correct: a
paper broker cannot close a live contract, only fake the close. So the orphan is made loud
instead — `foreign_book_positions`, reported at the `run_signal_loop` startup boundary and
on `/api/health` as descriptive context, never as part of the verdict.

**Authority became a `(source, execution_mode)` pair, and IR gained nothing.** `GRANTS` now
holds triples; `(ir_graph, paper)` and `(ir_graph, live)` are both absent. The gate
recomputes the process's real mode at the point of use rather than trusting the field the
binding carries. `ir_shadow_deployments` was **not** widened into a paper deployment table
— it stays an observer with no capital, no orders, no arm state and no authority. Paper
authority, if granted, flows through the canonical Deployment/execution-binding path.


### IR paper authority — L1.3C (2026-08-07, ADR 0012 §7)

The owner granted `(ir_graph, paper, authoritative)`. An approved immutable graph version
may now be authoritative for one instrument in the **paper** book; `(ir_graph, live,
authoritative)` remains absent and is the next gate.

**IR changes who may author the paper signal, and nothing after that point.** There is no IR
paper trader: `publish_signal`, `process_entries`, sizing, routing, `PaperBroker`,
`Position`/`Trade`, accounting, exits, reconciliation, risk, kill and restart recovery are
the existing machinery, untouched.

**The grant is necessary and not sufficient.** This slice registers graph adapters so
`ir.<identifier>` resolves; if `GRANTS` membership were the whole test, an instrument
assignment would become authoritative — the L1.2 hazard. A graph-backed binding must also
carry `ORIGIN_PAPER_AUTHORITY` and match the approved content address, both recomputed at
the point of use.

**Exact version, three checks.** Activation, every reload, and the gate. A published edit
does not inherit authority. A mismatch fails closed — the instrument stops trading rather
than silently trading the default.

**Rollback is named.** `restore_strategy_key` is a required argument with no default; `None`
means "no previous authority". A target that cannot hold authority is refused. Retirement is
terminal and rewrites no money record.

**Found while building it:** option fills carried no `strategy_key`, no entry path carried
`strategy_version`, and `LiveBroker` would have raised `TypeError` on every real order once
those parameters were added — the protocol guard only ever compared the paper implementation.
All three are fixed, the last with a guard of its own.

### Paper-authority runtime hardening — L1.4 (2026-08-07)

L1.3C proved a graph *may* author a paper signal and that the money record names the approved
artefact. L1.4 asks the operational question: does that hold **through failure and recovery**?
29 deterministic tests (`tests/test_paper_authority_runtime.py`) cover restart and exact reload,
withdrawal, exit ownership, the kill switch, refused and failed entries, isolation, shadow/paper
separation and evidence. No position is waited for — every one is constructed — so nothing here
depends on the mock feed admitting a fill on a particular bar.

**One real defect found, and it could write a wrong money record.** `refresh_paper_authority`
replaced the binding map but left `self.state` and `self.executed_binding` alone. Those routes
run *between* a scan and an entry pass, so an operator retiring or pausing a deployment could
still have the previous tick's signal opened afterwards — and `process_entries` attributes from
`executed_binding`, so the `positions` row would name a graph that was no longer authorised.
Measured, not theorised: the test opened one before the fix.

`_withdraw_superseded_signals` closes it. **Withdrawing authority withdraws the signal it
produced** — the same rule L1.2b applied in `scan_signals`, arriving through the other door.
Scoped to instruments the deployment actually held and to a genuine change of content address,
so an unaffected instrument keeps its signal and a no-op refresh withdraws nothing.

*A second bug lived inside the first fix for about ten minutes:* `if state.pop(...) is not None
or binding.pop(...) is not None` short-circuits, so the state went and the binding stayed —
still available to attribute a fill. Both pops are now unconditional, and the mutation that
restores the `or` reddens the exact assertion about attribution.

**What the tests establish beyond the fix.** Hard invariant 2 holds against every form of
withdrawal: a position opened by a graph is still marked, exited and squared off after its
deployment is paused, retired, or made unverifiable — and after a disarm. Two database-level
guarantees the runtime depends on are confirmed rather than assumed: published graph versions
are immutable (so bytes cannot move under an active deployment), and the deployment's foreign
key refuses a dangling graph version (so "the row survived and the artefact did not" is not a
reachable partial-restore state). A dynamic trap over `KiteOrderClient` and `LiveBroker` proves
a full stage → activate → reload → signal → entry → exit → square-off cycle reaches no live
order seam.

**The "evidence reload gap" was investigated and is NOT a defect — see
[ADR 0013](../../../engineering/decisions/0013-research-approval-is-admission-not-a-lease.md).** Research approval
is an *admission prerequisite* consumed once at activation, not a continuously evaluated lease.
Authority is created by activation and ends by an execution-plane lifecycle action (pause, retire,
supersession) — never because research state changed elsewhere. Measured: with every research door
trapped to raise, a reload still loads the binding, rebuilds the adapter and verifies the content
address three times, so restart recovery is already independent of the research plane. `resume`
*does* re-verify evidence, which is the only boundary where stale approval was a genuine risk.
**Do not implement an evidence re-read on reload.** What newer contradicting research deserves is
operator *visibility*, which is a read, not a control.

No schema change; migration head stays `0013`. No sizing, routing, risk, live-order or frontend
change. `(ir_graph, live, authoritative)` remains **NOT APPROVED**.
