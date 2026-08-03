# ADR 0011: Staged adoption of the Component IR runtime in the live path

- **Status:** **Stage 0 IMPLEMENTED (2026-08-03). Stage 1 ENGINEERING-CLOSED (2026-08-04).
  Stages 2–3 remain PROPOSED and owner-gated.** The live hand-written strategy is still the sole execution authority; no
  order, paper or live path consumes the adapter. Stage 1 added a shadow lane that
  *observes* it — see §5 Stage 1 outcome.
- **Date:** 2026-08-03
- **Owners:** WS-02 execution, WS-01 Component IR, WS-03 research plane
- **Depends on:** RFC 0001 (Appendix C(d)), ADR 0001, the S3.3 equivalence proof, S4.1–S4.6 research binding
- **Reference prior art:** `~/dev/multiverse-of-ideas/reviews/nautilus-trader.md` §9D — "one
  execution path for research and live", recorded verdict *"adopt as the long-term target,
  explicitly staged"*, with the explicit note that it "belongs in its own phase with its own
  parity evidence". This ADR is that phase.

---

## 1. Why this is not a small change

The Component IR is complete, tested to 29 enforced RFC clauses, and **consumed by nothing that
trades**. Verified 2026-08-03: no module under `app/engine/`, `app/api/` (execution routes),
`app/backtest/` or `scripts/` imports `app.ir`. The parity test says so in its own docstring
(`tests/test_ir_strategy_parity.py:20`): *"Nothing here runs in production. The engine still calls
`compute()`."*

This is the codebase's documented defining defect — mechanisms built, correct, wired to nothing —
at the largest scale it has ever occurred. Adoption is how it stops being that. But the target is
a **real-money path that has booked 72 live trades**, so the sequence below is deliberately slower
than the engineering would strictly require.

---

## 2. What the live path actually is

Reconciled by reading the source, not the docs.

**The strategy contract** (`app/strategy/registry/base.py`) is narrow and already sufficient:

```
compute(self, df: pd.DataFrame, **params) -> pd.DataFrame     # base.py:60
CANONICAL_COLUMNS = ("longEntry","shortEntry","longExit","shortExit")   # base.py:21
```

`signals()` (`base.py:63-72`) merges params over `default_params` and **enforces** the four
columns. Input frames are `["date","open","high","low","close","volume"]` on a RangeIndex
(`app/market_data/candles.py:59`).

**Only six call sites exist.** Live: `runner.py:449` (default v3, params from static `Settings`)
and **`runner.py:457` — every other strategy, including `expanding_z_v4`, called with no params at
all**. Backtest: `backtest/engine.py:213`, `premium.py:210`. Chart: `api/routes.py:285`. Plus the
contract itself.

**The money path barely touches strategy output.** The risk lane calls no strategy; it consumes
cached booleans `st["long_exit"|"short_exit"|"ratchet_exit"]` (`runner.py:625-627`). Order
placement, journalling, reconciliation, ledger anchoring and `build_sha` stamping are entirely
shape-agnostic. **Exactly two things read strategy shape:** the four booleans reaching
`self.state[key]`, and the presence of `risk_model`.

That narrowness is what makes staged adoption feasible.

---

## 3. Every place the live path bypasses or conflicts with Strategy OS

| # | Conflict | Evidence | Severity |
|---|---|---|---|
| 1 | **The adapter is on the wrong side of a fail-closed boundary.** `IRGraphStrategy` exists and works, but lives at `research/strategy/builder/ir_strategy.py:70`, and `research/guards.py:24-32` lists `app.engine.runner` among `FORBIDDEN_MODULES`. | source | **blocking** |
| 2 | **Warmup vs the live admission guard.** Live admits a frame at `len(candles) >= settings.ema_length + 5` ≈ **55 bars** (`runner.py:444`); the resolved graph's warmup is **302** (parity `:244-245`), and `_flags` forces the warmup prefix to `False` (`ir_strategy.py:65-67`). A short frame ⇒ **every flag False, forever, silently.** | source | **critical** |
| 3 | **`risk_model` is lost.** `IRGraphStrategy` never sets it, so the base's `None` applies — silently disabling the ATR ratchet at `runner.py:478-487`, `:1258-1263`. | source | **critical** |
| 4 | **Backtest warmup trim disappears.** `compute_signals` trims on indicator columns `("ema","z","slope","atr","absZ")` (`backtest/engine.py:218`); the adapter emits only the four booleans, so `warm_cols` is empty and **nothing is trimmed** — breaking hard invariant 4 (live/backtest parity). | source | **critical** |
| 5 | **Unknown strategy keys silently become v3.** `set_strategy` (`runner.py:362`) and `universe_resolver` (`:95-96`) coerce an unregistered key to the default; `get_strategy` logs `strategy_fallback` only once per 300 s. | source | **critical** |
| 6 | **Content-address keys drift.** `IRGraphStrategy.key` embeds 12 hex of the graph address (`ir_strategy.py:83`), so **editing a graph changes its key** — every persisted `InstrumentState.strategy_key` stops resolving and falls back to v3 per #5. The generated-strategy path chose stable keys + versioned content (`generated_strategies.py:36-46`); the two identity schemes are inconsistent. | source | **critical** |
| 7 | ~~**No memoisation in the adapter.**~~ **WITHDRAWN — this ADR was wrong, and acting on it would have been a correctness bug.** See §4a. | measured | — |
| 8 | **Parameters frozen at resolution.** `compute` **raises** if given any params (`ir_strategy.py:87-94`). Live passes none, so it works — but no `runtime_config` or `Settings` value can ever reach graph parameters without re-resolution. | source | major |
| 9 | **Telemetry goes blank.** `_generic_latest` returns `ema/z/trend = None` when those columns are absent (`runner.py:539-551`); cockpit, `/ws` and `SignalEvent` rows lose their indicator values. Trading is unaffected. | source | minor |
| 10 | **Frame contract mismatch.** The adapter demands all six OHLCV columns (`ir_strategy.py:102-104`) though `GRAPH` declares only `high/low/close` (`expanding_z.py:235`). Live frames carry all six, so this bites only narrower callers. | source | minor |

**What does not exist at all:** any shadow-execution lane, any IR-vs-handwritten divergence
comparator or log, any feature flag selecting a strategy engine, any dry-run mode inside the live
broker. `research/shadow.py` is research-DB bookkeeping for promotion candidates, **not** a live
shadow lane. The closest thing to a rollout switch that exists is the per-instrument
`strategy_key`, which is DB-persisted and applies without restart.

---

## 4. What the current parity evidence is actually worth

`tests/test_ir_strategy_parity.py` proves bar-for-bar equality of the four columns over **400
bars** — but on a **synthetic sine fixture** (`:38-60`), not real candles (its docstring's claim of
"real candle data" is wrong), one instrument, 15-minute only, at default params plus **two** moved
parameters. Eleven of fifteen parameters are never varied, including every length parameter that
changes warmup.

Decisively: **it calls `evaluate()` directly and bypasses `IRGraphStrategy` entirely** (`:74-76`).
The adapter's warmup masking, NaN coercion, frame contract and `Strategy` conformance are
therefore **outside the parity claim**. `IRGraphStrategy` is exercised only in `research_tests/`,
which bare `pytest` does not run (`testpaths = tests`).

**Conclusion: the existing parity evidence is necessary but nowhere near sufficient to authorise
live adoption.** Stage 0 below exists to fix precisely this.

---

## 4a. A correction this ADR must carry: the cache is not an optimisation

The original conflict #7 read "C8 memoisation is entirely off in the adapter" and the Stage 0
plan said to pass a persistent `Cache`. **That was wrong, and implementing it would have
produced silently incorrect signals on live money.**

`Cache` is keyed on `node.cache_id` (`runtime.py:138`), which is computed **at resolution**
from node identity and bound parameters. It carries nothing about the input data. A cache
reused across two different candle frames therefore returns the *first* frame's series for
the second. Measured on the real graph:

```
reused-cache result == FIRST frame's result : True
reused-cache result == CORRECT result       : False
cache hits on 2nd evaluate                  : 18     (every node)
```

Every node reports a hit, the evaluation looks fast and healthy, and every value is stale.
In a signal lane this is the worst available failure: the strategy would keep trading
yesterday's signal shape with today's prices and nothing would log.

The adapter's existing behaviour — a fresh `Cache` per `evaluate()` — is therefore
**correct, not a missed optimisation**. Memoisation still does its intended job *within* one
evaluation (a subgraph appearing twice is computed once). `tests/test_ir_adapter.py` pins the
hazard so that "turn the cache on for performance" cannot be done quietly later.

The performance question is real but separate, and must be answered by measurement against
the 2.5 s signal-loop budget, not by sharing a cache.

## 5. The staged sequence

Each stage is independently reversible and ends at a decision point. **Stages 0–2 touch no
real-money path and need no owner gate beyond approval of this ADR. Stage 3 is a separate,
explicit, owner-gated production decision.**

### Stage 0 — make the adapter production-grade and honestly tested (no live effect)

Move an `IRGraphStrategy` equivalent into `app/ir/` (conflict #1: the engine cannot import from
`research/`). The research plane keeps using it; the module simply moves to the side of the
boundary that both may import — the reverse direction is already permitted and used
(`app/core/generated_strategies.py:105-107`).

Then close the correctness conflicts, each test-first:

- **#3** carry `risk_model` through from a declaration on the graph, so the ATR ratchet survives.
- **#4** emit the indicator columns the backtest warmup trim depends on, or change the trim to
  read a declared warmup. Either way, live and backtest must agree on which bars count.
- **#2** make warmup explicit and *loud*: a frame shorter than the resolved warmup must raise or
  log, never silently return all-False.
- **#6** adopt the generated-strategy identity scheme — stable key, versioned content.
- **#7** pass a persistent `Cache`; measure evaluation cost against the 2.5 s budget.

**Exit criterion:** parity re-proved **through `IRGraphStrategy`** (not `evaluate()`), on real
recorded candles, across multiple instruments and intervals, over a parameter sweep, including
short frames, gaps and session boundaries — plus a measured per-scan cost budget.

**Stage 0 outcome, 2026-08-03.** Implemented at `app/strategy/ir_adapter.py`. Conflicts 1–6
and 8–10 are closed; #7 was withdrawn as wrong (§4a). The `research/` bridge now **subclasses**
the shared adapter rather than duplicating it, inverting exactly two declared policies —
identity (address-embedded keys, because a search must tell hundreds of candidates apart) and
tolerance (short windows are a result, not an error). Attempting a straight de-duplication is
what surfaced that conflict: the two planes need opposite answers, and the difference is now
declared in one place instead of forked into two adapters.

### Stage 1 acceptance criteria (quantitative and structural)

Stage 1 may not be proposed until all of the following hold. **These are entry criteria for
the shadow lane, not for live adoption.**

*Structural:*

1. The shadow evaluation reaches no order, position, ledger or capital seam — proven by a
   test that patches every broker entry point and fails if one is touched.
2. The hand-written strategy remains authoritative for every signal that reaches an order.
3. Divergence is persisted per bar with the graph's content address, so a disagreement can be
   attributed to an exact graph version after the fact.
4. A shadow failure (raise, timeout, missing kernel) cannot degrade the authoritative lane;
   proven by injecting each and asserting the live signal is unchanged.
5. Enabling and disabling the shadow lane requires no deploy and no restart.

*Quantitative, measured on real sessions before Stage 2 is proposed:*

6. ≥ 20 live sessions of recorded divergence on at least 3 instruments. (`research/shadow.py`
   uses `MIN_SHADOW_SESSIONS = 5` for simulated promotion candidates; a live lane against real
   money warrants more.)
7. Per-bar agreement on all four canonical columns ≥ 99.9% over settled bars, with **every**
   disagreement individually explained — an unexplained divergence blocks Stage 2 regardless
   of the rate.
8. Zero `InsufficientHistory` refusals during market hours on any instrument the shadow lane
   is configured for; a refusal means the live admission guard and the graph warmup disagree
   and must be reconciled before proceeding.
9. Added evaluation cost ≤ 20% of the signal-loop budget (`signal_loop_seconds = 2.5`) at the
   95th percentile, and no measurable increase in resident memory across a full session — the
   box is 1 GB and has OOM'd twice.

### Stage 1 — shadow lane, computed but never acted on (no live effect)

Add a shadow evaluation to the signal lane: when an instrument has a shadow graph configured,
evaluate it alongside the authoritative hand-written strategy and **persist the divergence**.
The hand-written strategy remains authoritative for every order. The shadow result reaches no
order, no position, no ledger row — enforced by a test that patches the broker and fails if the
shadow path reaches it.

**Exit criterion:** N sessions of recorded divergence on real market data, with a report of
per-bar agreement. `research/shadow.py`'s `MIN_SHADOW_SESSIONS = 5` is the existing precedent for
what N should be, though live sessions warrant more.

**Stage 1 outcome, 2026-08-04. Implemented; NOT closed.** Evidence and raw numbers:
`docs/reports/2026-08-04-l1-stage1-shadow.md`. Built as `app/engine/ir_shadow.py` (observer),
`ir_shadow_store.py` + `ir_shadow_divergences` + migration `0010` (record),
`ir_shadow_metrics.py` (numbers), `GET /api/ir-shadow` (read surface), and
`Settings.ir_shadow_enabled` (fail-closed, `runtime_config`-overridable, no deploy or
restart). Pairing is by authoritative strategy key, so an instrument whose strategy has no
mirror is skipped and counted rather than compared against a different strategy.

Structural criteria 1–5 are met, each with a mutation watched turning its guard red
(`scripts/ir_shadow_mutations.py`, nine mutations, all reverted). Criterion 9's cost half is
met and comfortably: 36.6 ms p95 per eight-instrument iteration, **1.46% of the 2.5 s
budget** against a 20% limit, zero missed cycles.

**Criterion 8 was closed by an admission contract, not by changing the authoritative lane.**
This ADR predicted the conflict (#2) and the measurement confirmed it: the graph's warmup is
302 bars, and at `history_days = 30` an NSE name on a **30m or 60m** interval yields
~286 / ~154 bars and can never settle. Both obvious remedies — more history, a shorter
warmup — change what the authoritative lane is handed, and the owner ruled both out of
scope. So the lane now decides admissibility from the **resolved IR contract** (the graph's
own declared warmup) against the configured timeframe and history, **before** evaluating:
an impossible pairing is rejected up front with a stable explicit reason, never evaluated,
never able to emit all-False output, and never able to repeat an in-hours refusal. Because
admission reasons from configuration and a feed can contradict it, three consecutive
post-admission refusals demote the pairing, naming both the expected and the observed bar
count. Verdicts are cached per `(instrument, interval)` and re-decided on an interval change,
so criterion 5 still holds.

**Deferred by owner decision (2026-08-04), and explicitly NOT closure criteria:** criterion 6
(≥ 20 live sessions × ≥ 3 instruments), criterion 7's denominator, the resident-memory half
of 9, richer recorded OHLCV and replay fidelity. The stored market data is temporary
validation material; it will be re-exported or re-accumulated when more brokers and APIs are
connected. **These must be revisited before authority promotion, production deployment or
commercial validation.**

**Coverage in production remains zero** — the default `trend_impulse_v3` has no mirror, and
assigning `expanding_z_v4` to an instrument changes what it trades. `GET /api/ir-shadow`
reports `coverage.shadowed`, `coverage.unmirrored` and `coverage.rejected` so absence can
never be misread as agreement.

### Stage 2 — paper-mode adoption (no real money)

Let an IR graph be authoritative **in paper execution only**, gated so it cannot bind while
`PT_EXECUTION=live`. `SafePaperKite` and `PaperBroker` already provide the containment; the gate
is a strategy-engine selector that fails closed to the hand-written path.

**Exit criterion:** a paper session whose ledger reconciles to the paisa, with shadow divergence
from Stage 1 explaining every difference.

### Stage 3 — live adoption **(OWNER-GATED, one instrument, reversible in one command)**

Bind one IR graph to **one** instrument via the existing per-instrument `strategy_key`, which is
DB-persisted and live-applied. Rollback is reassigning that key — no deploy, no restart.

**Preconditions, all required:** Stage 1 divergence at zero on that instrument for the agreed
window; Stage 2 ledger clean; a measured `/api/health` and `/` check; the deployed commit
recorded; and the owner's explicit approval **at this stage specifically**, separate from
approving this ADR.

---

## 6. What stays authoritative at each stage

| Stage | Signals authoritative | Orders | Ledger | Rollback |
|---|---|---|---|---|
| 0 | hand-written | hand-written | untouched | n/a — nothing live changed |
| 1 | **hand-written** (shadow is recorded only) | hand-written | untouched | disable shadow config |
| 2 | IR **in paper only**; hand-written in live | paper broker only | paper | flip the selector |
| 3 | IR on one named instrument | live, that instrument only | live | reassign `strategy_key` |

Hard invariants 1–6 hold unchanged throughout. In particular **invariant 2** (ARM gates entries,
never exits) and **invariant 4** (live/backtest parity) are the two most at risk — #4 above is
already a latent invariant-4 violation, and it is fixed in Stage 0 before anything else proceeds.

---

## 7. Non-vacuous safety proofs required

Each must be proven able to fail, restored, and recorded — the eight-mutation discipline used in
S4.6d:

1. a frame shorter than resolved warmup **cannot** silently produce all-False;
2. an unregistered or drifted `ir.*` key **cannot** silently trade v3 — it must refuse or alarm;
3. an IR strategy without a carried `risk_model` **cannot** silently disable the ATR ratchet;
4. live and backtest agree on the warmup-trimmed bar set for the same graph and frame;
5. the shadow lane **cannot** reach `open_position`, `open_equity_position`, or any order seam
   (patch the broker; the test fails if touched);
6. the paper gate **cannot** bind an IR strategy while `PT_EXECUTION=live`;
7. evaluation cost per scan stays inside the signal-loop budget on a 1 GB box;
8. parity holds through `IRGraphStrategy` on real candles across a parameter sweep, gaps and
   session boundaries — not just through `evaluate()` on a sine wave.

---

## 8. Honest scope and risk

**Scope.** Stage 0 is the largest piece: roughly the size of a full slice band (comparable to
S4.1–S4.3 combined), because it is where six real defects get fixed and where the parity claim is
rebuilt from scratch. Stages 1 and 2 are each about one slice. Stage 3 is hours of work and weeks
of patience.

**Risk, stated plainly.** The severe risks are all *silent-degradation* risks, not crashes:
all-False signals from warmup (#2), a disabled ratchet (#3), and a silent fallback to v3 (#5, #6).
Each fails in the direction of "the bot quietly stops doing what you think it does" — the same
shape as the E0.2 re-anchor bug that reported ₹49,833 against a much smaller real account for
three weeks. That is why Stage 0 fixes them before any shadow data is collected, and why every
proof above is phrased as "cannot silently…".

**The honest counterpoint the owner should weigh.** Adoption makes the research plane pay rent,
but it does not by itself improve trading outcomes. The book says the problem is entry quality:
across 72 trades `TARGET` has fired **zero** times, the largest favourable excursion ever recorded
(1.216%) is below the target it must hit, and the median trade travels further against you
(0.427%) than for you (0.286%). Running the same strategy through a different runtime changes none
of that. **The value of L1 is that it makes the research plane able to change the strategy at
all** — it is the bridge, not the destination.

---

## 9. Boundary

This ADR authorises **design only**. No implementation begins before owner approval. Stage 3 —
live adoption — requires a **second, separate** approval at that stage, and remains subject to the
standing owner gates on the architecture migration and on any sizing, exit, or routing change.
