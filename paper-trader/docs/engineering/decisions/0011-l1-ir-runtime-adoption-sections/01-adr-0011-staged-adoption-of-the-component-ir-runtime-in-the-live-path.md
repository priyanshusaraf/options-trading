Reference: [section index](../0011-l1-ir-runtime-adoption.md). Read with its scope; this is not a new assignment.

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
