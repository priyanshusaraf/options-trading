# L1 Stage 1 — shadow-only IR lane: evidence

**Date:** 2026-08-04 · **Status:** **ENGINEERING-CLOSED 2026-08-04.** Implemented,
committed, **not deployed**. Operational validation against long-duration native broker data
is **deferred by owner decision**, not pending — see §0.
**Authority:** owner approval 2026-08-04 for a *shadow-only integration*; ADR 0011 §5.

---

## 0. What "engineering-closed" means here, and what it does not

The owner closed Stage 1 on the **engineering contract**, explicitly declining to gate the
programme on market-data quantity, cleanliness, duration or broker fidelity: the data stored
today is temporary validation material, not the product's data foundation, and it can be
re-exported or re-accumulated when more brokers and APIs are connected.

**Closed:** the shadow lane exists in the live signal path as an observer, isolation and
containment are proven, disagreements are persisted and attributable, cost is inside budget,
and — added at closure — an explicit **warmup/history admission contract** makes an
impossible graph/timeframe/history pairing a visible, up-front rejection instead of a
refusal repeated every 2.5 seconds.

**Deferred, and NOT a closure criterion:** ≥ 20 genuine market sessions, richer recorded
OHLCV, replay fidelity, long-duration production shadow statistics, frontend settings
controls. Recorded here so nobody later reads §2's numbers as more than they are. They must
be revisited before authority promotion, production deployment or commercial validation.

**Unchanged:** the hand-written strategy is the sole execution authority. Nothing in Stage 1
places, modifies, cancels, routes, sizes, reconciles or squares off anything.

---

## 1. What was built

One observer inside `EngineRunner.scan_signals` (`runner.py:_observe_shadow`). For an
instrument whose **authoritative** strategy has a Component IR mirror, the mirror is
evaluated on the *same* frame the authoritative strategy just consumed, the two verdicts
are compared on the newest bar, and disagreements are persisted.

| Piece | Where |
|---|---|
| the observer (pairing, comparison, classification, frame identity) | `app/engine/ir_shadow.py` |
| the record | `app/engine/ir_shadow_store.py`, `ir_shadow_divergences`, migration `0010` |
| the numbers | `app/engine/ir_shadow_metrics.py` |
| the admission contract | `ir_shadow.admit` / `demote`, enforced in `runner._shadow_admitted` |
| the read surface | `GET /api/ir-shadow` |
| the flag | `Settings.ir_shadow_enabled = False`, `runtime_config`-overridable |
| the measurement | `scripts/ir_shadow_replay.py` |
| the guard proofs | `scripts/ir_shadow_mutations.py` |

Pairing is by **authoritative strategy key** (`expanding_z_v4` → the `expanding_z` graph).
Running the graph against an instrument on a different strategy would compare two different
strategies and call the difference a divergence.

---

## 2. Measurements

`backend/.venv/bin/python scripts/ir_shadow_replay.py`

### 2.1 Per-bar agreement — 110/110 settled bars, 100%

Bar-by-bar over real recorded series, through the shipping `ir_shadow.observe` (not around
it), with the frame growing one completed bar at a time exactly as the live lane sees it:

```
BANKNIFTY    settled=   0  agreement=n/a  reasons={'INSUFFICIENT_HISTORY': 134}
CRUDEOIL     settled=   0  agreement=n/a  reasons={'INSUFFICIENT_HISTORY': 208}
GOLDM        settled=  36  agreement=100.0000%  reasons={'INSUFFICIENT_HISTORY': 302}
NATURALGAS   settled=  36  agreement=100.0000%  reasons={'INSUFFICIENT_HISTORY': 302}
NIFTY        settled=   0  agreement=n/a  reasons={'INSUFFICIENT_HISTORY': 135}
SILVERM      settled=  38  agreement=100.0000%  reasons={'INSUFFICIENT_HISTORY': 302}
unexplained disagreements: 0
```

**Read the denominator before the rate.** 110 settled bars on three instruments says the
lane works and the mirror tracks. It is not the ≥ 20 sessions × ≥ 3 instruments the ADR
asked for, and per §0 that measurement is deferred rather than satisfied.

The fixture is real spot closes recorded from Kite (2026-06-22 → 2026-07-08); `open`,
`high`, `low` and `volume` are **reconstructed deterministically** because per-bar OHLCV
was not recoverable offline. For an agreement measurement that is sound — both lanes get
the identical frame, so any divergence would be theirs — but it is not a claim about live
Kite bars.

### 2.2 Disagreement classifications

Every disagreement observed in the replay was `INSUFFICIENT_HISTORY` (1,383), and every one
is explained by §3 below. `FLAG_DIVERGENCE`, `MISSING_GRAPH_INPUT`, `ADAPTER_REFUSAL`,
`EVALUATION_ERROR`, `UNEXPECTED_ERROR` and `AUTHORITATIVE_UNAVAILABLE` did not occur; each
is exercised deliberately in `tests/test_ir_shadow.py`.

### 2.3 Evaluation cost — p95 3.8 ms, max 4.4 ms

```
eval seconds  p50=0.0000  p95=0.0038  max=0.0044  n=1493
```

p50 is ~6 µs because a frame short of warmup is refused before any kernel runs. The p95 and
max are settled evaluations, and those are the numbers that matter: **0.15% of the 2.5 s
signal-loop budget for one instrument.**

### 2.4 Loop impact — p95 +37 ms, 1.46% of budget, zero missed cycles

The real `_signal_iteration_blocking`, lane off then on, over eight instruments:

```
loop_short_frames  as a fresh process sees them (161 bars)   off p95=0.035s  on p95=0.041s  delta=+0.006s  overruns=0  shadow p95 = 0.10% of budget
loop_settled       settled (mock advanced past warmup)       off p95=0.049s  on p95=0.086s  delta=+0.037s  overruns=0  shadow p95 = 1.46% of budget
```

Two rows because a fresh mock hands back 161 bars whatever you ask for, so the shadow
refuses immediately and costs nothing — a truthful measurement of a short frame and a
useless measurement of an evaluation. Advancing the mock past the warmup gives the second
row, with the same engine path.

**Settled: 36.6 ms p95 for eight instruments — 1.46% of the budget, against a limit of
20%.** Zero iterations exceeded the 2.5 s tick in either arm.

---

## 3. The finding: warmup and the live admission guard disagree

Found by the Stage 1 measurement, and **closed by the admission contract in §3a** rather
than by touching the authoritative lane.

The graph's resolved warmup is **302 bars**. The live lane admits a frame at
`len(candles) >= ema_length + 5` ≈ **55 bars** and pulls `history_days = 30`. Whether the
shadow can settle therefore depends entirely on the instrument's live interval:

The table below is **arithmetic from the session length, not a measurement** — it cannot be
measured offline, because the mock provider returns a fixed 161-bar window whatever interval
or `history_days` it is asked for. It is stated as derivation so the owner can check it
against a real Kite pull rather than take it on trust. NSE cash session: 09:15–15:30, 375
minutes. MCX runs 09:00–23:30, so commodity names get roughly three times these counts and
clear the warmup at every interval.

| live interval | bars per NSE session | bars in 30 calendar days (~22 sessions) | settles a 302-bar warmup? |
|---|---|---|---|
| 5 minute | 75 | ~1,650 | yes |
| 15 minute | 25 | ~550 | yes |
| 30 minute | 13 | ~286 | **no** |
| 60 minute | 7 | ~154 | **no** |

An instrument on 30m or 60m would produce a **permanent** in-hours `INSUFFICIENT_HISTORY`
for as long as the lane is on. ADR 0011 criterion 8 requires zero *unexplained* in-hours
refusals; these would be explained, but they would also mean the shadow never observes
anything on those instruments.

**Not fixed by changing the authoritative lane.** The two obvious remedies — raising
`history_days`, or reducing the graph's warmup — both change what the *authoritative* lane
is handed or what the graph computes, and the owner ruled both out of scope. So the finding
is handled where it belongs: **as an admission contract**, §3a.

### 3a. The admission contract (added at closure)

`app/engine/ir_shadow.py` now decides, **before any evaluation**, whether a pairing can ever
work under the current configuration:

1. required settled history comes from the **resolved IR contract** — the graph's own
   `declared_warmup`, never a constant copied into the engine;
2. available history comes from the configured **timeframe and `history_days`**, via the
   segment's session length (`bars_per_session` × `trading_sessions`), floored, so the
   estimate errs low;
3. `expected_bars <= warmup` ⇒ **rejected**, with a stable explicit reason naming both
   numbers, the interval and the segment;
4. a rejected pairing is **never evaluated** — so it cannot emit all-False output and cannot
   produce a repeated in-hours refusal;
5. the verdict is cached per `(instrument, interval)` and **re-decided** when the interval
   changes, so fixing the configuration needs no restart (criterion 5 holds);
6. the rejection is logged **once**, counted, and published at
   `GET /api/ir-shadow` → `coverage.rejected`.

Unknown interval or unknown segment fail **closed**: an unknown interval is refused rather
than sized by guess, and an unknown segment is priced at the *shortest* session, never the
longest.

**Admission is predictive, so observation gets the last word.** A feed can contradict the
arithmetic — the mock provider returns 161 bars whatever it is asked for. Three consecutive
post-admission `INSUFFICIENT_HISTORY` refusals therefore **demote** the pairing to rejected,
with a reason naming *both* what admission expected and what the feed returned, because the
gap between those two numbers is the thing someone has to fix. The contract is not "predict
correctly"; it is "a pairing cannot repeat an in-hours refusal".

`insufficient_history_after_admission` is counted separately from the ordinary case: a
refusal before admission is configuration, one after it is a defect in the validator, and
blending them would make the second invisible.

Related: the shadow lane's coverage in production is currently **zero**. The default
strategy is `trend_impulse_v3`, which has no IR mirror, so unless an instrument is
deliberately assigned `expanding_z_v4` the lane records nothing. Assigning one changes
authoritative trading and was not done. `GET /api/ir-shadow` reports `coverage.shadowed`
and `coverage.unmirrored` precisely so a "no disagreements" reading cannot be mistaken for
agreement when it is really absence.

---

## 4. Isolation and containment

`backend/.venv/bin/python -m pytest tests/test_ir_shadow_isolation.py` — 20 passed.

1. **Static.** `ir_shadow` reaches no execution seam transitively; `ir_shadow_store` reaches
   none either, walking to the shared persistence layer (`app.db.session` imports
   `app.engine.charges` to price a seeded position, so *any* table-writing module "reaches"
   it — the frontier is named and both modules' direct imports are checked separately).
2. **Dynamic.** Every broker, order-client and execution entry point is replaced with a trap
   that raises on call; a full shadow-enabled scan, and a divergence write, spring none.
3. **State.** `runner.state`, `runner.params` and `runner.strategy_keys` are identical with
   the lane on and off. No state entry carries a shadow field.
4. **Containment.** Failures injected at `observe`, `record` and the metrics leave the
   authoritative output byte-identical, and a failure on one instrument does not stop the
   rest of the book being scanned.

## 5. The guards were watched failing

`backend/.venv/bin/python scripts/ir_shadow_mutations.py` — each defect applied, the guard
run, the defect reverted:

```
guard                                                          clean    mutated  verdict
------------------------------------------------------------------------------------------------
the shadow verdict is fed back into the engine's state         PASS     FAIL     guard works
the shadow lane mutates shared execution parameters            PASS     FAIL     guard works
the shadow lane touches a broker seam                          PASS     FAIL     guard works
the shadow store imports the order path                        PASS     FAIL     guard works
a shadow failure escapes into the signal lane                  PASS     FAIL     guard works
the feature flag ships on                                      PASS     FAIL     guard works
agreement is counted per scan instead of per bar               PASS     FAIL     guard works
an unsettleable frame goes back to silent all-False            PASS     FAIL     guard works
the admission contract admits a configuration that cannot settle the warmup PASS  FAIL  guard works
a pairing the feed keeps refusing is never demoted             PASS     FAIL     guard works
a persistent cross-frame evaluation cache is reintroduced      PASS     FAIL     guard works
------------------------------------------------------------------------------------------------
all 11 guards reddened on their own defect and were restored
```

Three things this harness taught, all of them recorded because each was a way to be wrong
while looking right:

- the `self.state` leak mutation was a **no-op** (the observer runs before the state entry
  exists), so the guard was green for the wrong reason until the mutation moved;
- mutating `REFUSALS_BEFORE_DEMOTION` to `10**9` **hangs** — the test loops that many times.
  The call site is mutated instead. The first attempt ran past ten minutes and was killed;
- being killed left the mutation **in the tree**, because `finally` does not survive
  SIGKILL. The harness now parks the original in a sidecar and restores it on next start.

The harness earned its keep on the first run: the obvious version of mutation 1 — writing
into `self.state[key]` from inside `_observe_shadow` — is a **no-op**, because the observer
runs before the state entry is built and the assignment that follows replaces the dict
wholesale. The guard stayed green, the harness reported it **VACUOUS**, and the mutation was
moved to where a real leak would live. A guard nobody has watched go red is a guard nobody
knows works.

## 6. Stage 1 close criteria — where each stands

| # | Criterion | State |
|---|---|---|
| 1 | no order/position/ledger/capital seam reachable | **met** — §4, static + dynamic + mutation |
| 2 | hand-written strategy authoritative for every order | **met** — §4.3, and no caller reads the observation |
| 3 | divergence persisted with graph content address | **met** — `ir_shadow_divergences`, field-completeness test |
| 4 | a shadow failure cannot degrade the authoritative lane | **met** — §4.4, three injection points |
| 5 | enable/disable without deploy or restart | **met** — `runtime_config`, proven through a running engine |
| 6 | ≥ 20 live sessions on ≥ 3 instruments | **OPEN** — needs live sessions and an owner decision on §3 |
| 7 | ≥ 99.9% agreement, every disagreement explained | **provisional** — 100% of 110 settled bars, 0 unexplained; denominator far short |
| 8 | zero in-hours `InsufficientHistory` | **met structurally** — §3a. An impossible pairing is rejected before evaluation; an admitted one that refuses three times is demoted. Neither can repeat in hours |
| 9 | added cost ≤ 20% of budget at p95 | **met** — 1.46% (§2.4); resident-memory over a full session deferred with the other long-duration measurements |

**Stage 1 is engineering-closed. Stage 2 is not proposed and needs separate owner
approval.** Criteria 6 and 7's denominator are deferred operational validation (§0), not
open engineering work.

## 7. Verification run for this slice

Recorded in the commit message with commands and raw output: full backend + research
suites, `scripts/dryrun.py 700` (ledger reconciliation), `scripts/backtest_smoke.py`,
migration head, and the two scripts above.
