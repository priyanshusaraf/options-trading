# Backend hardening phase — 2026-08-08

**Scope.** Repo-wide backend security, data-integrity, quant-leakage, performance and
provider-architecture review, with fixes rather than a report. Started from exact head
`b47e8f5` (migration head `0013`), branch `feat/exec-completeness`.

**Status:** in progress. Eight commits landed (2026-08-08 → 09). This document is the
continuity record — what was inspected, what was found, what changed, and what is next.

**Standing state after the commits below:** full backend + research suite **EXIT 0, no
failures** (it was not, at `b47e8f5` — see §3.1), `dryrun.py 700` **LEDGER OK**,
`backtest_smoke.py` **SWEEP OK**, migration head unchanged at `0013`. No schema change, no
migration, no execution-path change, nothing deployed.

---

## 1. Commits

| Commit | What |
|---|---|
| `e01bdcc` | docs: the V1 guidance review (previous phase's deliverable, not adopted) |
| `837febe` | fix: bound reporting reads at the query and at the request |
| `e6b9bbf` | fix: restore the shared market cursor, not just the pinned clock |
| `ce72249` | test: prove the hand-written strategies cannot read the future |
| `d383326` | docs: this record |
| `4a09c02` | chore: rebuild the Claude Code engineering harness (§6b) |
| `553d871` | feat: declare provider capabilities; fail closed on futures with no price feed |
| `7442e69` | refactor: ask capabilities, not the provider's name |
| `323c865` | docs: record the provider slices and the instrument-identity finding |
| `ef513fa` | docs: correct the record's own commit table |
| `0a55b3a` | feat: give instrument identity a seam, and put Kite behind it |
| `a23157a` | feat: price dated futures contracts (commodities only, as §9 records) |
| `ca6f231` | docs: record the resolver seam and the futures feed as done |
| *(pending)* | feat: a semantic provider conformance contract, and the four defects it found |

---

## 2. Security

### 2.1 Auth posture — accurate, deliberate, and untenable for V1 (no fix; owner gate)

`app/api/auth.py` is **one shared bearer token** (`PT_API_TOKEN`); empty disables auth
entirely, and empty is the shipped default and the production posture on a tailnet-only
box. `app/api/principal.py` resolves an explicit `ANONYMOUS_OWNER` rather than `None`, and
`is_allowed()` is honestly "the owner may do everything".

The middleware itself is well reasoned and was **not** found defective: exemptions are
matched on the unversioned path (so `/api/v1/health` is exempt for the same reason
`/api/health` is), `resolve_http_principal` returns `None` for exactly one condition (a
credential presented and refused), the fallback in `get_principal` re-checks rather than
defaulting to anonymous, and CORS is registered outermost on purpose so a 401 still
carries its headers.

**What is genuinely missing for multi-user V1**, and is a slice rather than a patch:

- No object ownership. `Project` has no owner column; `graph_artifacts.identifier` is a
  **global primary key** (gap G-5). Only `research_review_routes.py` references `principal`
  at all — the other ten route modules do not.
- Cross-project isolation *is* enforced and tested; cross-**principal** isolation does not
  exist because there is only one principal.

**Not a defect today. It is the V1 blocker**, and it is sequenced in the V1 proposal
(`docs/agent-guidance-review/v1-proposal-2026-08/02-v1-classification.md` §1.5). The free
hedge — namespacing identifiers per owner — remains untaken and still costs nothing.

### 2.2 Generated-strategy sandbox — audited, found sound (no change)

`research/strategy/builder/` is the only `exec()` in the tree. It was audited as a
potential arbitrary-code-execution path and is **tight**:

- `validate.py` runs a global AST **node-type allow-list** that excludes `Import`,
  `Attribute`, `Subscript`, `Lambda`, comprehensions, control flow and f-strings, plus a
  ban on any identifier or string containing `__`;
- then a structural pass requiring exactly one `def compute(df, **params)` whose body is
  block-call assignments and a canonical dict return;
- `load.py` execs in a namespace containing only whitelisted block callables and an
  **empty `__builtins__`**.

The only reachable calls are whitelisted block functions with `df` or numeric-literal
arguments. `validate_source` is called on the single exec path. No bypass found.

### 2.3 Injection and unsafe-primitive sweep — clean

`eval` / `exec` / `pickle` / `marshal` / `yaml.load`: one hit, the sandbox above.
Raw-SQL interpolation: three hits (`app/ledger/db.py:37`, `app/db/session.py:243,248`), all
interpolating **internal table/column constants**, never request data. `subprocess`: one
hit (`research/nightly.py`, a `git` invocation with a fixed argv, no shell).

### 2.4 Unbounded reads — REAL, FIXED (`837febe`)

See §4.1. Classified here too because it is a denial-of-service surface, not only a
performance defect: on a tailnet box any device, and after V1 any user, could turn a
reporting endpoint into a full-table dump.

---

## 3. Data integrity and test-evidence integrity

### 3.1 The suite was order-dependent — FIXED (`e6b9bbf`)

At `b47e8f5` the full suite was **not green**: `test_notifies_on_auto_open` failed under
`pytest tests research_tests`, passed under `pytest tests`, and passed in isolation. It was
neither flaky nor about notifications.

`MockProvider.now()` is `self._times[self._cursor]`, and `advance()` mutates that cursor on
the **process-wide singleton**. The rootdir conftest already restored a pinned `now`
attribute (ADR 0012 §4.1a) but not the cursor. Measured:

```
cursor=1149 -> now = 2025-03-05 15:15   (after the 09:30 gate — entry taken, test passes)
cursor=1150 -> now = 2025-03-06 09:15   (before it — "ENTRY WINDOW closed", test fails)
```

The cursor sat exactly on a session boundary, so **one extra `advance()` anywhere earlier
in the run** rolled the clock into the next morning. Suite greenness was a function of test
order, which an exact-head CI contract cannot tolerate.

Fixed at the same seam. `advance()` remains observable within a test and stops being
observable between them. `tests/test_shared_provider_isolation.py` pins both halves as
ordered pairs; both proven able to go red.

### 3.2 A vacuous test caught in my own work — worth recording

The first draft of the analytics equivalence test was **vacuous**, and the mutation sweep is
what found it. `Trade(segment=None)` does **not** store NULL: the column carries a
Python-side default, so the ORM substitutes `"options"` and the legacy shape is never
created. A mutation deleting the segment normalisation stayed green.

Two consequences, both now in the test file:

- unset shapes must be written by **direct SQL**, bypassing the ORM default;
- `trades.segment` is `NOT NULL`, so NULL is unreachable there and the **empty string** is
  the only reachable unset segment.

That second point exposed a **real bug in the fix itself**: `_seg`/`_strat` used Python's
`or`, which is falsy for `""` as well as `None`, while a plain `COALESCE` matches only
NULL. `NULLIF(col, '')` inside the COALESCE is load-bearing, not decoration.

Also: the oracle must not be written in the implementation's own SQL, or it agrees with a
wrong implementation. It computes the expected count in Python from raw column bytes.

---

## 4. Performance — measured

All numbers from this machine, mock provider, temp databases. Scripts lived in the session
scratchpad and are not in the tree.

### 4.1 `recent_trades` — the 2026-07-23 outage shape, in a second place (FIXED)

The outage post-mortem fixed `equity_curve` and `signal_counts`. `recent_trades` sat 100
lines below `equity_curve` with the identical shape and was not fixed: it selected **every**
`Trade` row, filtered in Python, and applied `limit` with a list slice — so `limit` bounded
the response and never the read.

At **72,000 trades** (the row count the outage note cites for the live VPS):

| Call | Before | After | Speedup | Peak alloc before → after |
|---|---|---|---|---|
| `/api/trades?limit=100` | 1398.4 ms | 2.1 ms | **658×** | 310.7 MB → **0.5 MB** |
| dashboard, filtered, limit=50 | 1296.3 ms | 1.3 ms | **980×** | 310.7 MB → **0.3 MB** |

Output byte-identical at scale, filtered and unfiltered. 310 MB of allocation per call, on
a 1 GB droplet, under a 5-second dashboard poll, is the outage mechanism precisely.

Two independent bounds now, because either alone leaves a path back: the query is bounded
(`analytics._narrow` pushes filters and `LIMIT` into SQL) and the request is bounded
(`app/api/paging.py::MAX_PAGE`). Negative limits mattered: SQLite reads `LIMIT -1` as no
limit at all.

`instrument_stats` stays deliberately unlimited — a statistic over a subset of its own
population is wrong rather than partial — and is bounded by its indexed key instead.

### 4.2 The connection pool has a measured cliff (NOT yet changed — see §6)

`create_engine` sets `pool_pre_ping` and `pool_timeout=10` but **leaves pool sizing at the
SQLAlchemy default**: `pool_size=5`, `max_overflow=10` → **15 connections**. FastAPI runs
every `def` route (which is nearly all of them) in anyio's worker threadpool — **40 threads**
by default. The pool is the binding constraint, not SQLite.

Measured, 40 concurrent DB-touching workers:

| Per-request connection hold | Result |
|---|---|
| 50 ms | 40/40 ok, p95 181 ms |
| 1 s | 40/40 ok, 3.0 s wall |
| 3 s | 40/40 ok, 9.0 s wall — at the `pool_timeout` edge |
| **5 s** | **30/40 ok, 10 failed** with `QueuePool limit ... TimeoutError`, p95 10 s |

So any query holding a connection **≳4 s** under full threadpool concurrency starts
**failing requests**. Before §4.1, `recent_trades` held one for **1.4 s** at production row
counts — within reach, and the 2026-07-23 outage's terminal symptom was DB-pool collapse.

`/api/health` does genuinely touch the pool (`_probe_db`), so total exhaustion surfaces as
503 rather than a lying 200. What is missing is a **leading** indicator: saturation is only
visible once it is total.

---

## 5. Quant / research leakage

### 5.1 Causality of the hand-written strategies — audited, no defect, now guarded (`ce72249`)

The IR proves causality for graphs (C11). Nothing did for the hand-written strategies,
which are what the live engine executes and what every backtest number is measured on.
`trend_impulse_v3` — the default — had no causality proof at all.

This matters because of a deliberate design choice: `compute_signals` computes the signal
frame over the **full** candle series and only then cuts walk-forward folds, so
path-dependent EMA/ATR seeds stay consistent. Correct **iff** every indicator is causal;
otherwise each out-of-sample fold is scored using information from its own future and the
leak is invisible — the equity curve simply looks better.

**Result: both `expanding_z_v4` and `trend_impulse_v3` are causal**, on real recorded
series across four prefix lengths, asserted over every column they emit rather than only
the four canonical ones. The comparison is proven able to fail by injecting a one-bar
look-ahead.

### 5.2 Look-ahead discipline elsewhere — inspected, healthy

`backtest/engine.py` fills at **next bar open**, applies **adverse** slippage on both legs
direction-aware, shares the **same** event-blackout table as the live engine (so backtests
are not flattered by bars the live bot refuses), and trims warmup by declared count for
graph strategies so the two planes agree on which bars exist.

### 5.3 Not yet audited

Cache key dimensionality (does the `(instrument, interval)` backtest cache carry data and
parameter identity?); DSR/PBO deflation correctness — memory records `var_sr` computed
nowhere and the benchmark pinned at 0, making pre-2026-08 findings unusable as baselines,
and that has **not** been re-verified in this phase; survivorship in the sweep's visible
set (there is a disclosure mechanism — `skipped_breakdown` — but its completeness is
unverified); cross-instrument timestamp alignment (does not exist yet).

---

## 6. Architecture conclusions so far

| Decision | Verdict | Evidence |
|---|---|---|
| Python + FastAPI for the API | **Stay** | No measured bottleneck is language-shaped. The two real ones found so far were a query shape and a pool size; both are Python-agnostic. Do not revisit without a measurement that indicts the runtime |
| SQLite + WAL | **Stay with hardening** | Not the binding constraint at the concurrency measured; the 15-connection pool is. Migration trigger remains a measured lock-wait, not a headcount |
| Sync `def` routes on the anyio threadpool | **Stay, but size the pool to it** | §4.2 — 40 workers against 15 connections is an accidental default, not a decision |
| Process-wide provider singleton | **Refactor for V1** | Already a correctness hazard in tests (§3.1) and the concrete blocker for multiple connections per account |
| Process-global backtest sweep | **Unchanged, seam only** | G-3. Second concurrent user is refused outright; do not build queues now |
| The authority / execution-binding spine | **Preserve** | Nothing found in this phase argues against it. Not touched |

**Deliberately NOT changed: the connection pool.** Raising it is the obvious move and it is
not obviously safe. Each additional SQLite connection carries its own page cache, and the
target box is the 1 GB droplet that has OOM'd twice with the engine running — trading a
request-timeout ceiling for a memory ceiling on the machine that holds real positions is
not a change to make unilaterally. It is written up here as an owner-visible decision with
its measurement attached.

---

## 6a. Provider architecture — 2026-08-09

### Done: capabilities replace provider-name branching (`553d871`, `7442e69`)

**The finding.** Ten sites in shared engine/backtest/analytics code branched on
`provider.name == "kite"` or `== "mock"`. Each is really a capability question, and each would
have answered False for a second broker — silently, on the safe-looking branch:

| Site | Consequence for a non-Kite connection |
|---|---|
| `broker_factory.py` | no live order client is ever constructed |
| `runner.py` deployable capital | no account funds read → sizing fails closed to ₹0 |
| `runner.py` futures margin | no real margin quote → sizing refuses |
| `runner.py` cockpit payload | account funds never surfaced |
| `analytics.py` | account equity reported as unavailable |
| `universe.py` (×2) | refuses to build a real instrument universe |

None of them raises. `app/providers/capabilities.py` now carries a role-separated vocabulary
(market data / account / execution / instrument identity / determinism), every provider declares
its set, and all seven kite-gated sites ask the capability instead.

Migration safety was proven **before** the migration: an equivalence table asserts the capability
answer is identical to the name answer, for every provider that exists, at every migrated site —
and a deliberately wrong mapping is shown to fail it. `test_second_broker_is_reachable.py` then
proves what equivalence cannot: a connection named `"upstox"` declaring Kite's capabilities now
passes every gate, while a **data-only** connection is still refused the account and execution
questions. That is the Upstox-data/Zerodha-execution split, asserted.

Deliberately **not** migrated: the three `name == "mock"` sites. `SIMULATED_CLOCK` is broader —
`ReplayProvider` also has an advanceable clock — so migrating them is a behaviour change for
replay, not a refactor. Guarded rather than done quietly.

### Found AND fixed: the index-futures segment had no price feed (latent P1)

The capability honesty check rejected Kite's `FUTURES_QUOTES` declaration on its first run:
**no provider implements `get_futures_ltp`** — not Kite, not mock, not replay. Meanwhile
`runner.py` calls it at three sites to mark futures positions, decide staleness, and price the
delivery-window force close. With the feed unimplemented, `fut` is always `None`, so a position
would never mark on a real price, would read permanently stale, and would be force-closed at
`pos.last_premium` — the **entry** price.

`index_futures_enabled` defaults False and the segment is documented as "fully built and switched
OFF", so this was latent. It stops being latent the moment that flag is flipped, and nothing
would have raised.

Two-part fix. `_process_futures_entries` refuses to open without the capability (`553d871`), and
`KiteProvider.get_futures_ltp` is now implemented (`a23157a`), so Kite declares the capability
honestly and the guard opens for it. The load-bearing behaviour is **exact expiry matching**:
`_near_future` returns the front month, and marking a September position against the August
contract prices a different instrument at a different basis — silently, and flatteringly. Mock and
replay still cannot price futures, so the guard still has something to protect against; a test
asserts it would be dead code if it ever did not.

`index_futures_enabled` remains False. **Live verification against a real Kite session is
outstanding** — the tests stub the dump and the quote call, so they prove the mapping and the
refusals, not the feed.

### Done: instrument identity has a seam, and Kite is behind it (`0a55b3a`)

**Strategy OS does not own instrument identity today; the canonical `Instrument` carries one
provider's symbology inline.** Measured:

- `app/core/instruments.py` — `spot_symbol` is a Kite tradingsymbol; `option_name` is documented
  as "`name` used to find option contracts in **the instruments dump**", a Kite concept;
  `lot_size`/`strike_step` are "re-resolved from the instruments dump each day".
- `app/providers/kite.py:352` builds a Kite quote key directly out of canonical fields:
  `f"{inst.spot_exchange}:{inst.spot_symbol}"`.
- `kite.py:310` tries `(inst.option_name, inst.spot_symbol, inst.key)` as Kite dump lookups.
- `kite.py:297` matches the dump on `row["tradingsymbol"] == inst.spot_symbol`.

So a second provider with different symbology has **nowhere to put its mapping**. It would either
reuse Kite's strings (wrong instrument) or fork the `Instrument` model (breaks "one of anything").
This blocks provider switching, data/execution separation and cross-instrument strategies at once.

`app/providers/instrument_resolver.py` is that somewhere. `ResolvedInstrument` carries the
canonical key as the **only** cross-provider identifier, plus provider-scoped symbol, exchange and
token, plus the connection that produced them — provenance, because a mapping applied against the
wrong broker resolves to a different contract while looking entirely valid.

It shipped with a consumer rather than as a mechanism wired to nothing: `KiteProvider` implements
`resolve_underlying`, and **both** `_underlying_token` and `_underlying_quote_key` now derive from
it. They previously duplicated the index-vs-future branch, which is the `candles.py` shape (two
hand-written implementations of one idea) this project has already paid for once.

Observable success: a fake Upstox resolver maps the same canonical instrument to a different
symbol, exchange and token space — reading only `inst.key` — with no change to `Instrument`.
Proven non-tautological by poisoning the Kite-specific fields; a resolver that read them would
surface the poison.

**What is still outstanding, stated plainly.** `spot_symbol` and `option_name` still live on
`Instrument`. Relocating them is a schema and seed change on the live symbol-resolution path, and
it needs a second real mapping to hold plus a way to prove Kite's resolution is preserved exactly.
Until then `KiteInstrumentResolver` is the only thing permitted to read those fields as symbology,
and a test enforces that a non-Kite resolver does not. **That relocation lands with adapter #2.**

## 7. What is next

1. **Adapter #2 (recommend Upstox).** The abstraction is now testable rather than theoretical:
   capabilities, an instrument-resolver seam, and a second-broker reachability suite exist. The
   adapter is what proves them, and it carries the `spot_symbol`/`option_name` relocation with it.
2. **A conformance suite both adapters pass** — and that fails an adapter which lies about a
   capability. Today's tests prove the seam; they do not yet hold two adapters to one contract.
3. **Pool sizing + saturation telemetry.** Make the pool explicitly configured rather than
   an accidental default, and report utilisation on `/api/health` so saturation is visible
   before it is total. The sizing value itself is the owner decision above.
4. **Connection objects.** Capabilities now exist per provider; the remaining piece is a
   `Connection` record (a user's credentialed link) so one account can hold several, and a
   deployment can validate its required capabilities before activation.
5. **Finish the leakage audit** — §5.3, starting with cache key dimensionality and the DSR
   deflation claim, which is the one with a known prior defect.
6. **Ownership columns and identifier namespacing** — §2.1.

## 8. Method notes worth keeping

- **Mutation-prove every guard, including the ones that pass before and after.** A test
  that is green on both sides of a change proves nothing until a wrong change is shown to
  redden it. That is what caught the vacuous seed in §3.2.
- **Settle "did I break this" with a worktree at HEAD.** Used here to separate a
  pre-existing red from a new one; both the isolated run and the full-suite run at HEAD
  were needed, because the failure only existed in the second.
- **An oracle written in the implementation's own idiom agrees with a wrong
  implementation.** Compute expected values by a different route.


---

## 9. The provider conformance contract, and what it found (2026-08-09)

`b47e8f5..ca6f231` is published and its **exact-head CI run `31303084479` is green** across
backend, frontend and deterministic smoke. That closes the verification gap this phase carried.

### 9.1 Why a second contract was needed

`test_provider_capabilities.py` checks that a declared capability has a method behind it which
is not the base class's default. That is structural, and three adapters written to lie in the
three ways that cost money pass it clean — measured, not assumed:

```
liar-stub        honesty-check offenders: NONE — the guard passes it
liar-candles     honesty-check offenders: NONE — the guard passes it
liar-futures     honesty-check offenders: NONE — the guard passes it
```

`tests/provider_conformance.py` is the semantic contract; `tests/test_provider_conformance.py`
runs every adapter through it and proves it can fail one. It lives under `tests/` deliberately:
its only consumer is CI, `conform()` places live reads, and `break_transport` is destructive to
the connection — so an activation-time capability precondition is a *different* mechanism, not a
relocation of this one. Shipping it under `app/` would have been a mechanism wired to nothing.

### 9.2 Four defects, all found by the contract on its first runs

1. **`ReplayProvider.option_ltp` took one argument; `MarketDataProvider.live_snapshot` calls it
   with five.** Any open option position in a replayed session raised `TypeError` inside the
   provider; `mark_and_exit_positions` caught it, recorded a `quote` health failure and marked
   nothing. The position stayed unmarked for the whole run — no trail, no staleness, no exit.
   A forensic tool had quietly stopped reproducing the day it was replaying.
2. **`MockProvider` implemented futures pricing and never declared `FUTURES_QUOTES`.** The
   capability gate then fenced the index-futures segment off from the only connection on which
   it could be exercised before going live. Under-declaration is the quiet mirror of a lie.
3. **`KiteProvider` searched `spot_exchange` for `FUT` rows.** NSE index futures live in the
   **NFO** dump, so `get_futures_ltp` resolved to nothing for every index future. Invisible on
   MCX, where `segment == spot_exchange` — which is why the commodity tests passed. `a23157a`
   therefore closed the dated-futures feed **for commodities only**; the earlier wording in this
   record overstated it and is corrected here.
4. **`_process_futures_entries` invented the contract expiry** — found by independent review,
   not by the contract, and the most serious of the four. It read
   `getattr(inst, "expiry", None) or now.date()`; `Instrument` is a frozen dataclass describing
   the economic *underlying* and has no `expiry`, so the entry expiry was always **today**.
   With (2) fixed, the gate opened and a NIFTY futures position booked at **exactly spot**
   (24101.45), because at zero days to run the mock's basis has converged — the underlying
   substituted for the contract, arriving through a working provider. From the next simulated
   day the held expiry no longer priced, `_mark_exit_futures` marked nothing, and
   `handle_overnight` no-ops on the mock, so the position could never exit.

Fix for (4): `MarketDataProvider.front_month_expiry` — concrete, defaulting to `None`, the same
pattern `get_futures_ltp` established. The connection is the only thing that knows its own
listed series. Kite answers from the near-future row (and `_near_future` now reads `inst.segment`
too, so the two sibling lookups no longer disagree); the mock answers from the expiries its own
option chain uses; replay inherits the refusal. The runner honours `None` with
`FUTURES_NO_CONTRACT` and opens nothing.

### 9.3 Evidence

```
$ .venv/bin/python -m pytest tests/test_provider_conformance.py
30 passed

$ .venv/bin/python scripts/provider_conformance_mutations.py
8/8 mutations reddened their own guard and were restored · suite green · EXIT 0
```

The contract's first draft was hardened after two independent reviews demonstrated it did not
hold a *data-only* adapter to anything: a deliberately wrong Upstox stub — daily bars for a
15-minute request, three bars for thirty days, the still-forming bar included, tz-aware stamps,
and a dead transport serving cache — produced **zero** violations. It now produces five. Added:
bar completeness against a real clock, modal interval spacing, the requested window, naive-IST
timestamps, front-month resolution priced at a real basis, instrument-identity provenance, and
market-data behaviour under a broken transport. Two of the contract's own checks could not fail
at all (the broken-transport clause allowed every success type; a permanently stuck clock passed)
and were fixed.

### 9.4 Still open — named, not solved

1. ~~**`get_candles` has no failure channel**~~ — **DONE 2026-08-09.** `ProviderReadError` is
   the typed refusal; `KiteProvider.get_candles` raises it (carrying the SDK's message, which
   `_is_auth_error` reads) instead of returning `[]`, and `[]` now means only "no bars". The
   engine's `candle` health failure and `_mark_token_bad` auth latch are reachable for the first
   time — pinned by `tests/test_provider_read_failures.py`, which drives `scan_signals` against a
   failing transport and asserts the latch engages and `last_scan_ok` is *not* refreshed. Two
   mutations prove it: swallowing the failure again, and dropping the message from the wrapper.
   The conformance contract now requires the typed refusal, so Upstox inherits the obligation.
   **This is a live-path change**, in the safe direction: the live candle read now raises where
   it returned `[]`. It alters no order routing, sizing or exit logic, but describing the phase
   as "no live-money path changed" was wrong and is corrected here.
   The three other call sites improve without change — `sweep.py` already records the error on
   the run, `research/data/store.py` no longer content-hashes a Dataset built from an API error,
   and the one unguarded chart route now degrades to an empty panel rather than a 500.

   The original entry is kept below because the *reasoning* is the reusable part.

   **`get_candles` had no failure channel — and the engine's own failure handling was
   consequently unreachable for Kite.**

   `kite.py` catches every exception around `_historical` and returns `[]`, so "the API 500'd",
   "the token expired" and "this instrument has no history" are one answer. But
   `runner.py:725` is written on the opposite assumption — it wraps the call in `try/except`
   and, on an exception, records a `candle` health failure, latches `_mark_token_bad` for an
   auth error so the remaining instruments are skipped rather than re-failing, and breaks the
   scan.

   None of that can fire. The adapter never raises, so on a live token expiry the engine calls
   `health.record_ok("candle")` and refreshes `last_scan_ok[key]` on every tick, then falls to
   `if len(candles) < ema_length + 5: continue` and skips the instrument silently. The operator's
   health surface reports a healthy feed while the connection is returning nothing, and the
   token-bad latch built for exactly this case never engages.

   It degrades toward *no new entries*, which is the safe direction, so this is not an
   emergency — but it means the data-health signal is not measuring what it claims. Settle it
   before Upstox: a second provider doubles the ways a read can fail, and the conformance
   contract's `check_market_data_under_failure` currently has to accept `[]` as a refusal
   because that is the only vocabulary available.
2. **A stale futures position skips its exit check entirely.** `_mark_exit_futures` sets
   `pos_stale` and returns without evaluating the exit, so a position that cannot be marked
   cannot leave. Unreachable today — no futures entry can open — but it is the "nothing may
   block an exit" invariant and it should not stay latent.
3. **The under-declaration check reaches only the capabilities in `_ANSWERED`.** Behavioural
   judgement needs a way to ask "did it answer"; capabilities without one are listed, not
   silently skipped.
4. **The Kite double bypasses `SafePaperKite`**, the wrapper that actually ships between the
   adapter and `KiteConnect`, so the order-endpoint allowlist is not exercised by this suite.
5. **Rate limiting is stubbed out** (`_NoThrottle`), so the suite cannot observe throttling.
   Upstox's limits are not Kite's per-category ones.

## 10. Sweep cost, per stage, and the premium-pricing bottleneck (2026-08-09)

Taken to size the owner's 10,000 x 5 target ("a few minutes" = 50,000 cells). Machine: this
Mac, mock provider, `trend_impulse_v3`, median of 20 repeats, benchmark in the session
scratchpad.

### The 6.61 ms/cell figure was measured on the wrong workload

The supervisor review's 500-cell benchmark reported 6.61 ms/cell on 600 synthetic bars. Two
things make that number inapplicable to the tier maths:

1. A real 15-minute / 200-day window is **~5,000 bars**, not 600.
2. **The synthetic-premium replay produced zero trades** at 161 and 1,000 bars, so any premium
   timing at those sizes is measuring an empty loop. It only books trades once the series is
   long enough to contain expiry cycles — 300 premium trades at 5,000 bars.

Per-stage cost at 5,000 bars, one strategy (median ms):

| Stage | Before | After | Shared across strategies? |
|---|---:|---:|---|
| acquire (in-process, excludes throttle) | 0.11 | 0.11 | yes |
| address (`ordered_dataset_address`) | 11.01 | 11.75 | yes |
| frame (`prepare_signal_frame`) | 7.94 | 8.58 | yes |
| signals | 1.96 | 2.12 | no |
| simulate (spot) | 24.27 | 25.46 | no |
| **premium (synthetic)** | **140.43** | **36.71** | no |
| **TOTAL** | **185.71** | **84.72** | |

### The dominant cost was a scipy wrapper, not arithmetic

`cProfile` over the premium replay at 5,000 bars: of 0.731 s total, **0.539 s (74%) was
`scipy.stats.norm.cdf`** — 15,264 calls, two per `bs_price`. The time is in
`rv_continuous` generic machinery (`argsreduce`, `broadcast_arrays`, `_open_support_mask`),
not in the normal CDF.

`norm.cdf` computes its answer *by calling* `scipy.special.ndtr`. Calling `ndtr` directly is
the same function without the wrapper:

- **bit-identical** over 600,010 samples — uniform tails, standard-normal body, denormals,
  signed zeros, both infinities. Verified by `struct.pack` comparison, not `approx`.
- **232x faster** on scalars: 24.5 us -> 0.106 us per call.

Result: premium replay **140.4 -> 36.7 ms (3.8x)**, whole cell **185.7 -> 84.7 ms (2.19x)**.
`SWEEP OK` and 561 research/backtest tests unchanged.

`tests/test_options_pricing_identity.py` pins this. The guard was proven non-vacuous by
substituting the `math.erf` formulation — the obvious "equivalent" rewrite — which reddens both
the bit-identity test and a golden price. It differs in the **last mantissa byte**
(`b'@E;%ZoS@'` vs `b'\x80E;%ZoS@'`), which is exactly why an approximation here is more
dangerous than an outright bug: every backtested option price would move and nothing would
fail loudly.

### What the tier maths now says

Serial, one strategy, 5,000-bar datasets:

| Tier | Cells | Compute (serial) | Live-fetch I/O floor @ 0.40 s |
|---|---:|---:|---:|
| 100 x 5 | 500 | 42 s | 200 s |
| 1,000 x 5 | 5,000 | 424 s | 2,000 s (0.56 h) |
| 10,000 x 5 | 50,000 | **4,236 s (1.18 h)** | **20,000 s (5.56 h)** |

Two conclusions, both already in the plan:

- **The provider floor dominates and cannot be optimised in our process** — it is Kite's
  documented rate limit. The local content-addressed dataset store is the only path to the
  target, which is why it was promoted ahead of batching.
- **Compute still misses "a few minutes" by ~20x even after this fix**, so measured
  multiprocess fan-out is required and is now justified by measurement rather than preference.
  The next-largest remaining costs are `simulate` (25.5 ms) and `address` + `frame`
  (20.3 ms, paid once per dataset rather than per strategy).

Peak allocation is 2.10 MB per dataset for frame + signals, so 50,000 datasets held at once
would be ~105 GB. The sweep must stream datasets, never accumulate them — this constrains the
fan-out design.

## 11. WebSocket fan-out cost at 500 users (2026-08-09)

The owner named hosting cost at 500 users as a blocker and WebSockets as the part they have
been stuck on before. This is the first measurement rather than an opinion.

**Method and its limit.** Payload sizes are computed from the state entry shape built at
`runner.py:817-831` plus the ratchet keys at 839/841 and a held `Position.to_dict()`,
serialised compactly. This is a **reconstructed** payload, not a capture from a running
server — treat it as the right order of magnitude, and re-measure against a live process
before it becomes a deployment gate.

`main.py` `on_update` broadcasts `{"type": "state", "data": runner.state}` — the **whole**
state dict, every instrument, to every client, on every update.

| Instruments | Bytes/push | MB/user/hour @ 2.5 s tick |
|---:|---:|---:|
| 20 | 11,025 (10.8 KiB) | 15.9 |
| 50 | 26,545 (25.9 KiB) | 38.2 |
| 100 | 49,145 (48.0 KiB) | 70.8 |

At 50 instruments, 6.5 h/day, 22 days: **5.5 GB/user/month**, so **2,733 GB/month at 500
users**. Dashboards left open around the clock take that to ~13.8 TB.

### The bandwidth is not the problem. The serialisation is.

DigitalOcean bundles 1–2 TB per droplet and charges ~$0.01/GB beyond, so 2.7 TB/month is
roughly **$17/month** of overage — real but not the thing to fear. Even the always-on case
is ~$130.

The cliff is CPU. `manager.py:102` sends with `ws.send_json(msg)` **per client**, so the
same dict is JSON-encoded once per connected browser:

```
500 clients x 49 KB every 2.5 s = ~24 MB/s of JSON encoding, to send ~10 MB/s
```

That is the 2026-07-23 outage shape exactly — an application-level fan-out cost that grows
with users while looking like a bandwidth question. The manager is otherwise well built: it
already coalesces per client (`_COALESCE`, `client.latest` keeps only the newest message of
each type), so a slow consumer cannot accumulate a backlog. That part of the July rewrite
holds.

### Two corrections, neither of them "use polling"

1. **Serialise once, send bytes to many. — DONE, `0d6ac14`.** Each enqueued message is now one
   `_Frame` shared by every client, encoded at most once, lazily, inside `_sender`'s existing
   `try/except`. Measured on a 100-instrument payload to 500 clients over 20 pushes:

   | | `json.dumps` calls/push | wall/push |
   |---|---:|---:|
   | before | 500 | 148.94 ms |
   | after | **1** | **0.33 ms** |

   ~450x on the encode step. 149 ms of CPU every 2.5 s tick becomes 0.33 ms.

   Two guards, both proven able to fail. The encoding is byte-identical to starlette's
   `send_json`, pinned by diffing raw ASGI frames from a *genuine* starlette `WebSocket`
   against `send_json`'s own output for the same message, unicode included. And the encode
   stays **lazy** — moving it into `_enqueue` raises `TypeError` straight out of
   `broadcast()`, into the engine tick, instead of evicting the one client that cannot take
   the payload.

   One behaviour change, in our favour: `on_update` broadcasts the *live* `runner.state`, so
   each client's copy used to be serialised at that client's own send moment — clients could
   observe different states and the engine could mutate the dict mid-serialisation, once per
   client per tick. All clients now get one identical snapshot and that window shrinks 500x.
   A late-draining client reads text captured at first send: at most one tick stale, and
   coalescing replaces the frame next tick.
2. **Push deltas, not full state.** A 2.5 s tick changes a handful of fields on a handful of
   instruments, yet every push carries all of them, including `_ratchet_atr` — an
   underscore-prefixed engine internal already flagged in `api/dto.py`'s docstring as
   leaking to browsers. A delta protocol shrinks the payload by roughly the ratio of changed
   to total fields and closes that leak on the way.

Polling is strictly worse on both axes and is not proposed.

**Not yet measured, and still required before this is a gate:** bytes/user/hour captured
from a live process, accounts-per-core under a real session, resident memory per active
account, peak concurrent live accounts versus connected, and DB write throughput at peak
entries.

## 12. Sweep persistence and fan-out, measured (2026-08-10)

Tasks 5 and 6 of the scalable-sweep plan. Machine: this Mac (M1 Pro, 4 performance + 4
efficiency cores), mock/synthetic provider, 5,000-bar 15-minute datasets, `trend_impulse_v3`,
benchmarks in the session scratchpad.

### One SQLite writer sustains both tiers

Persistence moved from two transactions per cell (`_store` + `_bump`) to one transaction per
batch of ten, with `run.done` **derived** from the durable result count inside that same
transaction. Compute stubbed; realistic row payloads.

| rows | transactions | seconds | rows/s | ms/txn | one row per txn |
|---:|---:|---:|---:|---:|---:|
| 500 | 51 | 0.09 | 5,880 | 1.67 | — |
| 5,000 | 501 | 0.76 | 6,582 | 1.52 | — |
| 16,000 | 1,601 | 2.64 | 6,056 | 1.65 | 11.99 s |
| 50,000 | 5,001 | 9.69 | 5,158 | 1.94 | 54.02 s |

2.64 s of persistence against 22 min of compute for the NSE-cash universe. It is not the
bottleneck at either tier and does not need a second writer.

### Fan-out gives 2x, and the reason is measured

Pinned (warm) run, 500 cells, one strategy:

| workers | seconds | ms/cell | speedup | efficiency |
|---:|---:|---:|---:|---:|
| 1 | 48.65 | 97.3 | 1.00x | 100% |
| 2 | 24.50 | 49.0 | 1.99x | 99% |
| 4 | 23.35 | 46.7 | 2.08x | 52% |
| 8 | 26.76 | 53.5 | 1.82x | 23% |

The same box reaches **3.78x at 4 workers on a pure-CPU fan-out**, so 8x was never available
here — but 2.08x is below even that ceiling, and the cause is the parent, not the machine.
Parent-thread wall time during a 4-worker pinned run:

| stage | ms/cell | share |
|---|---:|---:|
| `_prepare_dataset` (store read: decompress + re-address + manifest check) | 37.94 | 73.4% |
| `_plan_dataset` (execution address + result-cache lookup + pickle) | 2.70 | 5.2% |
| `submit` | 0.08 | 0.2% |
| waiting on workers | 7.86 | 15.2% |

Uncontended, the pinned `_prepare_dataset` is 22.5 ms/cell; a cold run adds
`dataset_store.put` at 23.9 ms/cell. **The owner's 16-core / 1.4-minute warm target is not
reached by fan-out alone.** The next lever is sized: send workers the dataset *address* rather
than its candles, so the store read happens in parallel — parent cost ~41 -> ~3.5 ms/cell. It
requires reproducing the five fail-closed refusals of `_pinned_dataset` worker-side, so it is a
`dataset_store` design decision, not a mechanical change.

Parent RSS over a 400-cell 4-worker run: 193.9 -> 196.5 MB (6.3 KB/cell). Datasets are
streamed, at most `workers x 2` in flight; accumulating would have been 2.10 MB/cell.

### A method note that cost a suppression

The bit-identity gate between serial and parallel output was **vacuous against float drift on
the mock provider**: `MockProvider` rounds every OHLC value to two decimals, so a worker that
"normalised" prices with `round(x, 2)` produced identical numbers and the gate stayed green.
It only reddens against a provider that fills the mantissa
(`test_backtest_parallel.FullPrecisionMockProvider`), where it fails on `curve_json` first.
Any numerical guard built on mock candles needs the same witness.

## 13. Tiered sweep benchmark (Task 7, 2026-08-10)

`backend/scripts/sweep_benchmark.py`. Deterministic, offline, drives the shipped
`sweep.start_sweep` rather than a model of it. `tests/test_sweep_benchmark_harness.py` keeps it
from rotting into a script nobody runs.

### Per-cell stage cost, 5,000-bar datasets, 12 repeats

| stage | p50 ms | p95 ms | p99 ms |
|---|---:|---:|---:|
| identity (`ordered_dataset_address`) | 11.46 | 12.01 | 12.01 |
| frame (`prepare_signal_frame`) | 8.25 | 10.19 | 10.19 |
| signals | 2.39 | 2.81 | 8.09 |
| simulate (spot) | 25.17 | 25.46 | 30.38 |
| premium (synthetic) | 33.18 | 35.30 | 63.27 |
| **TOTAL** | **80.32** | | |

Independently reproduces §10's 84.7 ms on a different synthetic series, which is the point of
measuring it twice.

### Projected tiers — projections, not capacity

| tier | cells | bars | compute serial | I/O floor | cold | store |
|---|---:|---:|---:|---:|---:|---:|
| 100 × 5 | 500 | 2.5 M | 40 s | 200 s | 0.07 h | 0.1 GB |
| 1,000 × 5 | 5,000 | 25 M | 402 s | 2,000 s | 0.67 h | 0.9 GB |
| 10,000 × 5 | 50,000 | 250 M | 4,016 s | 20,000 s | **6.67 h** | 9.5 GB |

**These multiply a measured per-cell cost; they are not measured end-to-end runs.** That
distinction is not pedantry — it is exactly where the earlier 16-core projection went wrong
(§12: the parent thread, not the cells, set the ceiling). Real NSE/BSE universe sizing is in
`superpowers/specs/2026-08-10-full-universe-backtest-design.md` §2.

### Operation counts, end-to-end

A speed number with an unbounded operation count underneath it is not a speed claim, so the
harness drives a real sweep and counts:

```
12 instruments x 2 intervals -> 16 cells, 0 errors
provider reads       16   (= unique datasets; no cell refetches another's data)
write transactions    3   budget 3  (ceil(cells/10) + 1)   OK
```

### Two harness guards, both proven able to fail

- **Full-mantissa inputs.** The harness generates its own series rather than using
  `MockProvider`, whose 2-decimal rounding already hid a worker-side `round(x, 2)` from a
  bit-identity gate once (§12). Rounding the harness's own candles to 2 dp reddens that test.
- **The I/O floor is tied to the adapter it models.** The 0.40 s constant is asserted against
  `KiteProvider._MIN_INTERVAL["historical"]`, so a throttle change reddens the guard instead of
  silently invalidating every cold-run projection in the design notes. Changing the constant to
  0.25 reddens it.
