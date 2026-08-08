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
