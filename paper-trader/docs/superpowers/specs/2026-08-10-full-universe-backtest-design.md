# Full-universe backtesting: targets, determinism, and the language question

Owner direction, 2026-08-10. Supersedes the 10,000 × 5 figure in
[`2026-08-09-scale-and-cost-corrections-design.md`](2026-08-09-scale-and-cost-corrections-design.md)
with something more precise, and settles the rewrite question with measurements.

## 1. What was asked

1. Take the **maximum instruments NSE/BSE provide**, **every interval**, **maximum duration**,
   and measure how long the whole thing takes.
2. **Subsequent iterations of a slightly modified strategy: ~90% faster.**
3. **The initial run must also be dramatically faster** — the wait is a developer-experience
   and customer-retention problem.
4. **Every iteration must produce identical results when no parameter changed.** This is a
   validity requirement for the claims the product makes, not a nicety.
5. A different language is acceptable if the gain justifies the overhead and deployment stays
   sane.
6. The backtesting engine matters more than it has been credited.

## 2. The size of the job, measured

Interval ceilings are the repo's own `sweep.MAX_DAYS`. Bars/day use the NSE 375-minute session.
Per-bar cost is the **measured** 84.7 ms / 5,000 bars from hardening record §10 (post-`5ba1233`),
i.e. 16.94 µs/bar including the synthetic-premium replay.

| | NSE cash (~2,000) | NSE+BSE (~6,000) |
|---|---:|---:|
| Cells (instruments × 8 intervals) | 16,000 | 48,000 |
| Total bars | **78.1 M** | **234.2 M** |
| Provider requests | 16,000 | 48,000 |
| Compute, serial, 1 strategy | 1,323 s (0.37 h) | 3,968 s (1.10 h) |
| Provider I/O @ 0.40 s | 6,400 s (**1.78 h**) | 19,200 s (**5.33 h**) |
| **Cold total, serial** | **2.15 h** | **6.44 h** |
| Warm/pinned (no I/O), serial | 22 min | 66 min |
| Dataset store @ 38 B/bar | 3.0 GB | 8.9 GB |

**The single most important number: 83% of a cold run is provider I/O**, and that is Kite's
documented rate limit, not our code. No language, algorithm or data structure touches it.

## 3. Target 2 — the 90% warm iteration — is already reachable in Python

"A slightly modified strategy" changes the strategy, not the data. With the dataset store
(`e985d77`) and the pinned path (`0bd1147`), that iteration makes **zero provider calls**, so it
costs only compute. Serial that is 22 min for NSE; the 90% target is 2.2 min.

| Cores | NSE warm | vs. 22 min serial |
|---:|---:|---:|
| 8 | 2.8 min | 87% faster |
| 16 | **1.4 min** | **94% faster** |
| 32 | 0.7 min | 97% faster |

Cells are independent — no cross-cell reduction — so fan-out is near-linear and, importantly,
**does not change any number** (§5). 16 cores clears the target with margin. This is Task 6 of
the sweep plan and needs no rewrite.

Iterating one strategy over a **subset** — the actual developer loop — is far below this again.

## 4. Target 3 — the cold run — is an I/O problem, and has three real attacks

None of them is a language.

1. **The store is shared infrastructure, so only the first run of a
   `(provider, instrument, interval, window)` ever pays.** With 500 users this is the dominant
   effect: user #2 onward starts warm. A background warmer that populates the store outside
   market hours turns "2.15 h" into "already done" for everything a customer is likely to ask
   for. This is the highest-value item and it is scheduling, not engineering.
2. **Parallel data connections cut the floor linearly.** The throttle is per connection, so a
   second data provider halves it — **the first hard commercial argument for Upstox beyond
   redundancy**, and it depends on the connection-role composition of phase 6. Two connections
   take NSE cold from 1.78 h to 0.89 h.
3. **Bulk endpoints for what supports them.** Daily bars for the whole universe are a bhavcopy
   download, not 2,000 throttled requests. Worth confirming per interval before assuming.

## 5. Target 4 — determinism — has one real hazard, and it is not floating point

Reproducibility is largely already structural: cells are independent, the content-addressed
cache keys on exact ordered bytes plus a closed execution manifest, and a pinned rerun is proven
to reproduce every stored result column (`tests/test_backtest_pinned.py`). Parallel fan-out does
not threaten this, because no result is a reduction across cells — each cell's arithmetic is
performed in the same order regardless of which worker runs it. That must still be *proven*
byte-identical (Task 6's gate), not assumed.

**The real hazard is that a window is resolved against `date.today()`.** `sweep._fetch_days`
computes the fetch span from the current date, and `"max"` means "whatever exists now". So the
same request, with no parameter changed, resolves to a **different dataset tomorrow** — more
bars, a different address, different results. That is precisely the case the owner named, and
today it is unguarded:

- a pin resolved yesterday for a custom-window run mismatches today and fails closed, so the
  "pinned rerun" silently becomes a run of all-error cells;
- an unpinned rerun quietly produces different numbers and looks like strategy drift.

**Required:** a run must record the window it actually resolved to, and be re-runnable against
that resolution rather than against "today". A result should be reproducible from
`(dataset addresses, execution manifest)` alone, with wall-clock date participating nowhere.
This is a correctness gate on any reproducibility claim and it outranks the performance work.

Two related gaps already recorded against the store, both of which weaken a reproducibility
claim and neither of which is closed:

- **The store proves self-consistency, not provenance.** A blob+manifest edited *together* and
  re-addressed is served as authentic. Closing it needs the manifest sealed against the fetch
  that produced it.
- **A pinned result is not structurally marked as pinned** — `BacktestResult` has no dataset-
  address column, so nothing downstream can tell a pinned result from a live-fetched one. This
  sits awkwardly against the standing invariant that results bind to the versions that produced
  them.

## 6. The language question, answered with the profile

The repo's rule is that a rewrite needs a profile showing the *runtime* is the dominant cost.
Here is that profile, and it does not support one.

Cold NSE run, 2.15 h. A hypothetical rewrite making **all** compute infinitely fast:

```
2.15 h  ->  1.78 h      saves 22 min of 129, or 17%
```

Warm iteration, where compute *is* everything — but where fan-out already wins:

```
22 min serial  ->  1.4 min on 16 cores (Python, no rewrite)
```

A rewrite of the simulator might reach ~0.2 min on 16 cores. The remaining prize is ~1 minute per
warm iteration, bought with a second language in the money path, a second toolchain in the
deploy, a second set of numerical semantics to keep bit-identical against §5, and an FFI seam.
**That trade is not worth taking now**, and the honest reason is that the cheap wins have not
been taken yet — the store landed today and fan-out is not built.

Where a rewrite *would* become arguable, stated so it can be revisited on evidence rather than
feeling: if, **after** fan-out and the shared store are in place, the warm full-universe
iteration is still the bottleneck in a real user's loop, the target is the two hot inner loops —
`simulate` (25.5 ms/cell) and `simulate_premium` (36.7 ms/cell), 73% of a cell between them. The
first escalations are cheaper than a language and should be exhausted in order:

1. **Share the per-bar conversions across the two simulators.** *(Corrected 2026-08-10 — see
   below; this replaced "vectorise the premium replay", which the profile does not support.)*
2. **Numba on the two loops.** Keeps one language, one deploy, one dependency.
3. **A compiled kernel behind the existing seam**, only for the hot loop, only with bit-identity
   proven against the Python reference on a frozen dataset.

### Correction: `bs_price` is no longer the bottleneck

An earlier draft of this section said to vectorise the premium replay, reasoning that the
`ndtr` win came from removing per-call overhead so more of the same was probably available.
**Re-profiling after `5ba1233` shows that is wrong.** `bs_price` is now ~5% of the premium
replay (0.014 s of 0.285 s over five iterations); the fix already took what was there.

What remains, in both `simulate` and `simulate_premium`, has the same shape and no dominant
term:

| cost | share | note |
|---|---:|---|
| `to_dict` (signal frame → dicts) | ~15% | paid **once per simulator**, on the same frame |
| `ist_epoch` | ~17% | ~one call per bar, **in both simulators**, same timestamps |
| `round`, `compute_charges`, `normalize_key`, … | the rest | thin, spread across per-bar Python |

Two consequences, and they point in opposite directions from what the earlier draft implied:

- **There is a concrete ~30% win available, and it is the same pattern as Tasks 1–2** — hoist
  the frame-to-dict conversion and the epoch conversion to once per (dataset, strategy) instead
  of once per simulator. Both simulators consume the identical signal frame and the identical
  timestamps. This is cheap, stays in Python, and must be proven bit-identical.
- **The residual after that is thin-spread interpreter overhead**, which is precisely the cost a
  compiled language removes and which neither vectorisation nor a better algorithm will touch.
  So if the escalation ladder is ever exhausted, the honest argument for a compiled kernel is
  *stronger* than the earlier draft implied — but it is still an argument about the last
  ~60% of a 22-minute warm pass that fan-out already reduces to ~1.4 minutes, which is why it
  still sits behind fan-out and behind the shared-conversion win.

Only if all three are exhausted does a rewrite deserve a design. It would also have to answer
how it preserves §5 — a compiled reimplementation of the same arithmetic is *not* automatically
bit-identical, and "faster but subtly different numbers" is the one outcome the owner explicitly
cannot accept.

## 7. Order of work

Ahead of the remaining sweep tasks, because it is a correctness gate:

0. **Pin window resolution.** Kill `date.today()` from result identity; record the resolved
   window; make a rerun reproducible from addresses plus manifest.

Then, unchanged in intent:

1. Task 5 — batch persistence (measure whether one SQLite writer survives 16,000+ rows).
2. Task 6 — multiprocess fan-out, gated on **byte-identical** output versus serial.
3. Task 7 — tiered benchmark, now reported at real universe sizes rather than a synthetic tier.
4. Background store warming, and parallel connections once phase 6 lands.

Revisit the language question at the end of that list, against measurements taken after it.
