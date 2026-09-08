Reference: [section index](../0011-l1-ir-runtime-adoption.md). Read with its scope; this is not a new assignment.

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
