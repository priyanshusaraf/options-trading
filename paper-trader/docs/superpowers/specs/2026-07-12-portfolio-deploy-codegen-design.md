# Design: Approve→Deploy Bridge + Constrained Primitive Builder

**Status:** DRAFT for owner approval — *no code until approved.*
**Date:** 2026-07-12
**Author:** research/portfolio thread
**Depends on:** watchlists + conflict resolver + dev-blacklist + strategy archive (all landed).

These are the two capital-touching subsystems the owner deliberately gated behind a
design pass. Everything else in the multi-watchlist plan (watchlists, incumbency rules,
dev-blacklist, lifecycle archive) is already built and behaviour-preserving. This doc
covers only:

- **A — Approve→Deploy Bridge:** turning an approved research candidate into a live watchlist.
- **B — Constrained Primitive Builder:** the bot generating *runnable* new strategies.

## 0. Non-negotiable safety spine (applies to both)

1. **Capital allocation is never autonomous.** Every deployment is an explicit human
   approval. Nothing here auto-arms; the ARM-to-trade gate, kill switch, and daily-loss
   halt remain the final authority and are untouched.
2. **Disarmed on every restart.** Deployment is *staged* (owner's choice): an approval
   writes config that takes effect on the next controlled restart, after which the owner
   re-ARMs. This matches how the strategy registry caches per-process today.
3. **Generated code can never do arbitrary I/O.** It is composed from a vetted primitive
   library, statically validated (AST allow-list), executed in a restricted namespace,
   and must clear the full research gauntlet before it is even *eligible* for approval.
4. **The book must be clean before live.** Deploying a strategy never places orders to
   flatten phantom rows (existing ARM-note constraint). The bridge writes assignments
   only; it does not touch positions.

---

## A. Approve→Deploy Bridge

### A.1 The flow

```
research run ─▶ PromotionCandidate (status=pending, scorecard, qualifying_universe)
                     │
             owner reviews in cockpit  ── sees the "How this strategy works" report
                     │  (approve)
                     ▼
   resolve_conflicts(current_watchlist_membership, proposals)   ← incumbency + score
                     │
                     ▼
   create/update Watchlist(strategy_key)  +  assign winning instruments (membership)
                     │
                     ▼
   strategy_archive: candidate ─▶ running   (deployed_watchlist_id, last_dsr recorded)
                     │
                     ▼
   PromotionCandidate.status = approved  (+ approved_git_sha / approver + timestamp)
                     │
             ── STAGED: takes effect on next controlled restart ──
                     ▼
   owner restarts backend  ▶  _load_instr_config overlays the new watchlist  ▶  owner ARMs
```

### A.2 What it writes (and never writes)

- **Writes:** a `Watchlist` row (strategy_key), `WatchlistMembership` rows for the
  instruments that won conflict resolution, a `StrategyLifecycle` transition
  (candidate→running), and stamps the `PromotionCandidate` approved.
- **Never writes:** positions, capital_state, orders. It cannot move money — it only
  declares "when the engine next starts, run strategy S on instruments I."

### A.3 Conflict resolution at approval

The proposals are `(watchlist_id, instrument_key, score=DSR)` from the candidate's
qualifying universe. `resolve_conflicts` (already built) applies:
incumbents are untouched; disputes go to the higher DSR. The owner sees the resolution
(what was accepted, what lost, what was blocked by an incumbent) *before* confirming.

### A.4 Why staged, not hot-load

The registry discovers strategies per-process; a running engine won't see a newly
registered generated strategy without a restart. Staging also gives a clean, reversible
checkpoint: the approval is durable config, applied deterministically at the next start,
with the engine disarmed until the owner ARMs. Reversal = pause/archive the watchlist (or
KILL), then restart.

### A.5 Surfaces

- `POST /api/portfolio/promotions/{id}/approve` — runs conflict resolution, returns the
  *preview* (accepted/rejected/blocked) without committing.
- `POST /api/portfolio/promotions/{id}/deploy` — commits the resolved assignments +
  archive transition (idempotent; safe to replay).
- Cockpit: a "Promotions" panel listing pending candidates with their explanation report,
  scorecard, and the resolution preview; an Approve & Deploy button; a Watchlists panel.

### A.6 Open questions (A)

1. **Approval identity.** `PromotionCandidate.approved_git_sha` exists — do we require the
   owner to point at a committed SHA (traceable), or is a cockpit approval + timestamp
   enough for staged deploys? (Recommend: cockpit approval for staged; SHA optional.)
2. **Multi-instrument partial deploy.** If 3 of 5 qualifying instruments are blocked by
   incumbents, deploy the other 2 automatically or ask? (Recommend: show preview, deploy
   the winners, list the blocked ones.)

---

## B. Constrained Primitive Builder (code-gen)

The owner chose the **constrained primitive** approach over free-form LLM Python: new
strategies are *composed*, not hand-written, so every generated strategy is auditable and
structurally incapable of arbitrary I/O.

### B.1 The primitive grammar

A fixed vocabulary of parameterized, pure predicates over the candle frame, grouped by
research primitive:

| Primitive | Example building blocks (params) |
|---|---|
| **Trend** | `ema_slope_up(len, lookback)`, `ema_slope_down(...)`, `price_above_ema(len)` |
| **Momentum** | `zscore_cross_up(len, thr)`, `zscore_cross_down(...)`, `roc_gt(len, thr)` |
| **Volatility** | `atr_pct_lt(len, max)`, `range_atr_lt(len, mult)` (quality/quiet-bar gates) |
| **MeanReversion** | `zscore_lt(len, thr)`, `pct_from_ema_gt(len, pct)` |
| **Confirmation** | `still_expanding(series)`, `nth_bar_since(cond, n)` |

Each block is a hand-written, unit-tested pure function `df -> bool Series`. The builder
never writes these — it only *references* them by name with bounded params.

### B.2 Composition → a strategy

A generated strategy is a **declarative spec**: boolean AND/OR combinations of blocks
mapped to the four canonical columns.

```json
{
  "key": "gen_trend_z_v1",
  "longEntry":  {"all": ["ema_slope_up(50,5)", "zscore_cross_up(50,1.0)"]},
  "shortEntry": {"all": ["ema_slope_down(50,5)", "zscore_cross_down(50,1.0)"]},
  "longExit":   {"any": ["zscore_lt(50,0)", "ema_slope_down(50,5)"]},
  "shortExit":  {"any": ["zscore_gt(50,0)", "ema_slope_up(50,5)"]}
}
```

This is what the builder *emits*. Two ways to run it — **decision needed** (B.6 Q1):

- **B.i — Interpreter (recommended):** a single vetted `GeneratedStrategy(spec)` class
  interprets the spec at runtime. No code generation at all → nothing to sandbox, the
  attack surface is the (small, tested) interpreter. Registry key + spec stored in DB.
- **B.ii — Emit Python:** template the spec into a readable `compute(df, **params)` source
  string that references only whitelisted blocks, AST-validate it (allow-list: no
  `import`, no `eval`/`exec`, no dunder/attribute escapes, no calls outside the block
  whitelist), then load it in a restricted namespace. More "real code" but needs the
  sandbox + AST validator.

Both satisfy "can't do arbitrary I/O"; **B.i is strictly safer and simpler** — recommend it,
with the emitted-Python view offered read-only for the owner's inspection.

### B.3 Search over compositions

The builder enumerates a **bounded** space of compositions (small max depth, capped
block count, only economically-sensible pairings — e.g. a Trend block gates a Momentum
entry). Each composition runs the existing gauntlet: `qualify → optimize → validate
(hard gates) → score`. The trial count (compositions × param grid × folds) feeds the
Deflated Sharpe deflation, so a wider search *raises* the significance bar — the anti-
overfitting math already in place directly guards the generator.

### B.4 From generated → deployable

1. A composition that clears every validation gate is registered (`source="generated"`)
   and entered in the archive as **candidate** with its spec + provenance (research run,
   spec_hash, git commit).
2. It appears as a `PromotionCandidate` like any tuned strategy, with a generated
   "How this strategy works" report (the primitive grammar makes this explanation exact).
3. It reaches capital **only** through the same human Approve→Deploy bridge (A). No
   generated strategy is ever auto-deployed.

### B.5 Static + runtime safety (for B.ii, if chosen)

- **AST allow-list:** module may contain only a single `compute` def; nodes restricted to
  arithmetic/boolean/comparison/subscript + calls to whitelisted block names; **reject**
  `Import`, `ImportFrom`, `Attribute` on non-`df`, `Call` to non-whitelisted names,
  dunders, comprehension-with-calls-out.
- **Restricted exec namespace:** only `df` + the block library injected; no builtins.
- **Resource guard:** wall-clock + row-count caps per evaluation.
- (B.i sidesteps most of this — the interpreter only ever calls vetted blocks.)

### B.6 Open questions (B)

1. **Interpreter (B.i) vs emitted Python (B.ii)?** Recommend **B.i** — same power for this
   grammar, far smaller attack surface, and the emitted-Python view can still be shown
   for auditability.
2. **Initial primitive library scope.** Start with the ~12 blocks above (covering the two
   existing strategies + obvious neighbours), expand later? (Recommend: yes, start small.)
3. **Composition search budget.** Cap generated compositions per nightly run (e.g. ≤ N)
   and log what was skipped, tying into the compute-budget work? (Recommend: yes.)

---

## C. Phasing (once approved)

1. **A first** (deploy bridge over *existing* tuned strategies) — immediately useful, no
   code-gen risk. Cockpit Promotions/Watchlists panels + the two endpoints + archive wiring.
2. **B.i** (interpreter + primitive library + composition search) — behind the same gate.
3. **B.ii** (emitted-Python view + AST validator) — only if the owner wants literal code
   artifacts; otherwise skip.

## D. What this does NOT change

The live engine's signal/risk lanes, the ARM/kill/halt safety stack, the charges model,
and the paisa-exact ledger invariant are all untouched. The bridge writes declarative
config; the builder produces strategies that flow through the *same* validation and the
*same* human gate as everything else.
```
