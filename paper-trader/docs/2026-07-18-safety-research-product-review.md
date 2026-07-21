# Full Safety Review · Research-Plane Assessment · Product Ideation

**Date:** 2026-07-18 · **Branch reviewed:** `feat/exits-journal` (61 commits ahead of `main`, deployed live on the VPS) · **Scope:** whole branch, `git merge-base main HEAD`..HEAD.

Method: 7 parallel subsystem auditors (Sonnet) traced the actual code; every money-touching
finding was then adversarially re-verified against the source at file:line (Opus). Only
confirmed findings appear below. Blast-radius rank, not discovery order.

---

## 0. Verdict on the four past failure classes ("actually dead, or patched once?")

| Class | Verdict | Evidence |
|---|---|---|
| **5×-vs-2.5× leverage/margin** | **DEAD** | `runner.py:678` `qty = min(margin_qty, lev_qty)` — real `order_margins` qty *and* the owner leverage cap both bind; fallback on quote failure uses owner-configured leverage (`runner.py:671-673`), never a hardcoded 5×; dust floor is `max(real, lev-equiv)` (`equity_entry.py:276-281`) so cap×floor can't zero out entries. |
| **Tick-size naked stops** | **DEAD on the stop/GTT path** — surviving cousin on the entry-LIMIT path (E9) | SL-M/GTT triggers round to the real per-instrument tick from the Kite dump (`kite.py:214-242`, cache-poison-guarded → `kite_order_client._tick` → `round_to_tick`). But the *options-entry LIMIT price* still uses hardcoded `0.05` (`execution_policy.py:23`) and `kite_order_client.place()` never re-rounds it. |
| **Exits cutting winners** | **STILL LIVE — as a tuning problem, not a code bug** (E5) | `lockstep_band` mechanics are correct and the break-even floor is *cost-adjusted* (`runner.py:570` `be = entry + rt`), so a scratch nets ~₹0 not a loss. The bleed is parameter aggressiveness (`trigger_pct` 0.02 default / **0.01 on the VPS** arms BE at ₹80 gross; `profit_lock_frac` 0.5). Owned by the exit-tuning roadmap (P2 sweep), not yet done. |
| **SL-M ↔ internal-stop sync** | **DEAD for equity SL-M — ALIVE for options GTT** (E3) | Equity path resyncs (cancel+replace) on modify-reject with an oversell guard (`live_broker.py:764-814`). The options **GTT** path only logs on modify-reject (`live_broker.py:788-790`) — no resync, no alert, self-heal never retries. Options is the default segment. |

Two classes fully dead; two have surviving cousins on the **options** path; one (exits) is a live
tuning bleed. The equity/MIS path — the product's current focus — is materially hardened; the
options path carries the residue.

---

## 1. ESSENTIAL flaws (verified), ranked

### TIER 0 — verify on the VPS today

**E2 · API mutation surface is fail-open if `PT_API_TOKEN` is unset.**
`auth.py:24-28` — `token_ok()` returns `True` when `Settings.api_token` is empty; the field
defaults to `""` (`config.py:256`). The global `auth_gate` middleware (`main.py:121-142`) then
lets *every* `/api/*` mutation through unauthenticated: `POST /api/execution/arm`,
`/api/execution/kill`, `/api/positions/manual-open`, `/api/portfolio/*/deploy`. Today the only
protection is that the UI is Tailscale-only — the API itself doesn't enforce that boundary.
- **Why it matters:** if the token isn't set in the VPS `.env`, anything that can reach
  `127.0.0.1:8090` on the box (any process, a future misconfigured bind/firewall rule) can arm,
  kill, open, or deploy with zero credentials. Could not verify prod `.env` from this checkout
  (deploys are rsync'd and exclude `.env`).
- **Next action:** SSH the VPS and `grep PT_API_TOKEN backend/.env`. If absent → set it now.
  Then harden the code: in `main.py` lifespan, refuse-to-arm (or hard-fail startup) when
  `provider == "kite"` and `api_token == ""`, so a misconfigured live deploy can't run wide open.

### TIER 1 — new silent safety-net failures (fix before next arm)

**E1 · A poisoned open-position key aborts risk-loop management AND overnight force-flatten for the WHOLE book.**
`runner.py:465` builds `insts = [get_instrument(k) for k in opens]` **outside** the `try` at
466. `get_instrument` raises `KeyError` for an unknown key (`instruments.py:129`), and
`load_universe` *pops* any instrument whose `UniverseInstrument.active=False`
(`instruments.py:112`). `universe_resolver.remove_instrument` sets `active=False` with **no
open-position guard** (`universe_resolver.py:123`).
- **Failure scenario:** the bot holds an `equity_intraday` position on a user-added instrument;
  the owner later hits `POST /api/portfolio/remove` on it (pruning a watchlist — a shipped
  feature). Next risk-loop tick, the comprehension raises → `mark_and_exit_positions` aborts for
  *every* open position (no marking, no trailing-stop, no SL/TP) — and repeats every ~1s
  forever. `handle_overnight` calls `get_instrument` the same way (`runner.py:1092`), so the MIS
  force-flatten-before-close never runs either. Symptom: one repeating log line while the whole
  book sits unmanaged.
- **Fix:** wrap each per-position lookup in its own try/except (drop+alert the one bad position,
  don't abort the batch) in both `mark_and_exit_positions` and `handle_overnight`; and guard
  `remove_instrument` to refuse (or force-close first) an instrument with an open bot position.

**E3 · Options GTT modify-reject → silent, unalerted stop divergence** (see Tier-0 table, class 4).
`live_broker.py:788-790` only logs on a rejected `modify_stop_gtt`; `pos.gtt_trigger_id` stays
non-None so `ensure_stop_protection`'s self-heal never retries. The exchange GTT is stuck at the
old (looser) trigger while the internal stop has ratcheted higher — exactly the SUZLON class,
fixed for equity, alive for the default options segment, and it bites precisely when the GTT is
supposed to matter (bot down / risk loop stalled).
- **Fix:** mirror `_resync_equity_stop` — on a GTT modify exception, `_cancel_gtt` + `_place_gtt`
  fresh at `pos.stop_price`, plus a `_notify` so repeated resync failure is visible.

**E4 · A failed live close is reported to the cockpit as success ("phantom close").**
`routes.py:603-614` discards `broker.close_position`'s return, then unconditionally logs
`MANUAL CLOSE`, sets `entries_blocked=True`, nulls the WS display state, and returns
`{"closed": true}`. But `LiveBroker.close_position` returns `None` on real failure paths (ownership
guard; SL-M-cancel-abort at `live_broker.py:489`; account re-check). Frontend `act()`
(`ActivePositionsView.tsx:80`) doesn't inspect the response either.
- **Nuance (lowers blast radius vs. the raw finding):** the DB `Position` row survives — only the
  *display* state is nulled — so the risk loop keeps managing/protecting the position. Harm is a
  **lying cockpit** + silent failure + an unwarranted same-day re-entry block, not a naked
  unmanaged position. Still essential: it misreports real-money state and can induce a wrong
  manual action.
- **Fix:** have the route check the broker return; only null state / report `closed` when a real
  trade comes back, else surface "close failed — still open". Frontend: check `res?.error` in
  `act()` (the pattern `SLTPEditor` already uses two components away).

### TIER 2 — the known money bleed (the reason this branch exists)

**E5 · Intraday exit ratchet arms the break-even floor on a trivial first step, scratching winners.**
`equity_entry.py:145-161` + config (`intraday_lockstep_trigger_pct` 0.02 default, **0.01 live on
VPS**; `profit_lock_frac` 0.5). Worked example: ₹8k margin, entry ₹500, qty 40 → the first
lockstep step needs only ₹160 (VPS: ₹80) of profit = a 0.8% move; `max(init_stop+slide,
breakeven_price)` then snaps the stop to break-even, and a routine ~0.8% pullback scratches the
trade at ~costs long before the 3% target. This is the documented net-negative (gross +₹134,
charges ₹359, **net −₹225**).
- **Not a code defect** — the mechanics are correct and break-even is cost-covering. It's a
  parameter problem already scoped by the exit-tuning roadmap (P1 replay → P2 offline sweep →
  new BE-arming-threshold knob) and simply **not implemented yet**.
- **Next action:** run the P2 offline exit-param sweep on the real VPS trades; interim, set on
  the VPS (live-editable, no restart): `sl_pct 0.008`, `target_pct 0.03`, `lockstep_trigger 0.03`,
  `lock_threshold 600`, `lock_frac 0.3`; consider decoupling the BE floor to arm from step 2+.

### TIER 3 — correctness / analytics (money-adjacent, lower magnitude)

**E6 · Options orphan reconciliation mislabels the bot's own GTT stop-fill as `RECONCILED_EXTERNAL_EXIT` at a stale price.**
`live_broker.py:900-904` — the options branch books external-exit unconditionally at
`last_premium or entry_premium`, without the GTT-status check the equity branch has
(`:878-895`, which books `STOP_LOSS` at the real fill). Corrupts exit-reason analytics
(backtest-vs-live comparison) and can trigger a false same-day re-entry auto-block on options.
**Fix:** query the GTT status (`kite.get_gtt`, not `client.status` — a trigger_id isn't an
order_id) and, if triggered, book `STOP_LOSS` at the real fill, excluded from the auto-block.

**E9 · Options-entry LIMIT price rounds to hardcoded 0.05, not the real tick** (Tier-0 table, class 2).
`execution_policy.py:23` `TICK=0.05` feeds `plan_order`'s LIMIT price; `kite_order_client.place()`
forwards it with no `round_to_tick` (unlike the stop/GTT placers). A commodity-option contract on
a coarser grid, quoted in the LIMIT-routing spread band, gets its entry rejected → missed entry.
Options-only and deprioritized, but latent. **Fix:** round `req.limit_price` through
`round_to_tick(price, self._tick(sym, exch))` in `place()`.

**E10 · `square_off_for_overnight` runs the options overnight-hold decision on MIS positions.**
`runner.py:1037-1067` loops all open positions with no `segment == equity_intraday` filter, so an
MIS position can be tagged `held_overnight` (meaningless + illegal to carry). Incidentally rescued
by `square_off_intraday` moments later at the default buffers — but corrupts the journal and turns
fragile if the two buffers are ever set apart or the call throws (compounds with E1).
**Fix:** `if pos.segment == "equity_intraday": continue` — let `square_off_intraday` be the sole
segment-correct authority.

**E7 · Equity charge legs ignore direction for SHORTs.**
`broker.py:118,153,354` hardcode `"BUY"` open / `"SELL"` close regardless of `direction`, so an
equity-intraday SHORT gets STT on the exit leg and stamp on the entry leg (real order sequence is
SELL-to-open/BUY-to-cover — `live_broker.py` and `journal/pnl.py:22` get it right). Magnitude is
pennies/trade and self-consistent (so `reconcile` won't flag it), but `Trade.net_pnl` won't match
the contract note on shorts. **Fix:** direction-aware sides, mirroring `journal/pnl.py`.

**E8 · `account_pnl` uses a LONG-only unrealized formula.**
`analytics.py:103-104` computes `bot_unrealized` as `(last-entry)*qty` for every position,
ignoring direction — inverting the sign for an open equity SHORT in the bot-vs-you dashboard
split. Display-only (cash/realized stay correct via `Position.mtm_value()`), but misleads a live
who's-making-money read. **Fix:** `sum(p.unrealized_pnl() for p in opens)`.

### Confirmed DEAD / clean (traced, no issue)
Paper↔live mixup impossible (`broker_factory.py:35-61` requires `PT_EXECUTION=live` +
`PT_LIVE_ACK` + `provider==kite`, built once at startup; market-data Kite is always
`SafePaperKite`). Order circuit breaker works (`runner.py:742-752`, 3 consecutive fails →
disarm). Never double-places an order (`_ensure_no_inflight`). `register_all` is fail-safe not
fail-open (`generated_strategies.py:47-53`). Deploy endpoints write declarative config only, never
an order (`deploy_bridge.py:68-88`). `runtime_config` bounds-checks every knob. All three
frontend API helpers now attach the bearer token (the DELETE-only bug is fixed). journal.db is
fully isolated from the live ledger.

---

## 2. Research plane — honest maturity assessment + roadmap

**One-line read:** the *safety perimeter* is close to production-grade; the *autonomous discovery*
is barely wired; the *statistical-validation* layer is one promise unbuilt and one silently broken.

### What's genuinely strong (verified adversarially)
- **Capital isolation is structural, not conventional.** An import-graph BFS over everything
  `research/` touches reaches none of `guards.FORBIDDEN_MODULES` and never `app.db.session`;
  `guards.enforce()` (called first in `nightly.main`) fail-closes on distinct-DB, no-broker-import,
  not-live. Real, callable checks.
- **The code-gen sandbox is escape-resistant.** `validate.py` AST allow-list excludes
  `Import/Attribute/Subscript/Lambda`/comprehensions/control-flow (18-node whitelist), bans `__`
  in names/args/string-literals, and structurally constrains the module to one
  `compute(df,**params)` of block-calls combined with `& | ~`. `load.py` execs in
  `{"__builtins__": {}}` + only the vetted blocks. It's the only `exec` in the tree; no `eval`.
- **The execution side re-validates.** `generated_strategies.register_all` reconstructs from the
  *declarative composition* (`Composition.from_dict`) and re-emits + re-validates source through
  the same gauntlet — it does **not** trust the stored `source` string. A tampered
  `composition_json` can at worst raise → logged + skipped → default-strategy fallback.
- **The validation pipeline is real:** qualify → hard-gate battery (min-OOS-trades, temporal
  stability, bootstrap confident-edge, 2× slippage-stress) → DSR score → Pareto → PromotionCandidate,
  with ± Findings and immutable content-hashed specs. A candidate can't reach promotion on vibes.

### What's missing or broken
- **[ESSENTIAL to research trust] DSR deflation is inert.** `score.py:21-28` hardcodes
  `var_sr=0.0`; `run.py:172` passes no `var_sr`; `dsr.py:29-32` then returns `expected_max_sharpe=0`
  regardless of `n_trials`. So a strategy picked out of a 100-point grid scores identically to one
  tested once — the documented anti-overfit mechanism doesn't fire. **Fix:** compute `var_sr` from
  the per-fold trial objective distribution (already captured in the `OptimizationTrial` ledger) and
  thread it through.
- **[ESSENTIAL to research trust] PBO/CSCV does not exist.** `stats/__init__.py` claims it as a
  "hard gate"; there is no `pbo.py`/`cscv.py` anywhere. Combined with the DSR no-op, there is
  currently **no functioning multiple-comparisons control**. **Fix:** implement CSCV/PBO over the
  persisted trial ledger and gate on it — or stop the docstring claiming it and flag it in the
  report so a human reviewer doesn't over-trust the scorecard.
- **N_eff is computed but unwired** (`stats/neff.py` has zero callers) — 15 correlated large-caps
  read as 15 independent bets on the scorecard.
- **`register_all` fallback is silent** — a generated strategy that fails to rebuild after a
  restart falls back to `trend_impulse_v3` with no cockpit marker (ARCHITECTURE §11's own
  unmitigated risk). **Fix:** return failed keys, surface a per-watchlist "fallback" flag.

### The autonomy gap (the honest part)
`nightly._load_plan()` returns a hardcoded `[]`. The nightly cron is a guardrail+schema-proof
**no-op**: there is no hypothesis generator, no universe resolver feeding it, nothing consuming
`Hypothesis.retest_priority` to schedule work, and the whole plane is flag-gated **off**
(`PT_RESEARCH_ENABLED=0`) and dormant on the VPS. "Generation" exists (`run_generated` +
`enumerate_compositions`) but is bounded deterministic enumeration invoked only by the offline
`research_run.py` driver, never by the nightly loop. So today this is a rigorous **validation
harness you hand a plan to** — not a discovery loop.

### Fastest credible path to "a real selling point" (milestones)
The safety rails to run this unattended already exist; the remaining work is integration + honesty,
not new safety architecture.
1. **Fix the stats integrity first (1-2 days).** Wire `var_sr` into DSR; either build CSCV/PBO or
   stop claiming it and label it in reports; wire N_eff into the scorecard. *Until this ships, do
   not trust DSR numbers or run `optimize_search=True` with large grids.*
2. **Turn the nightly loop on in shadow mode (2-3 days).** Implement `_load_plan()` to resolve the
   research-eligible universe from the read-only watchlist snapshot + a small hypothesis backlog
   ordered by `retest_priority`; run known strategies + `run_generated`; write the morning report.
   Flag stays gated to research.db only — zero capital path. This is the single highest-leverage
   move: it converts scaffolding into a machine that manufactures candidates nightly.
3. **Close the feedback loop (1 week).** Have tonight's Findings (esp. negatives) *condition*
   tomorrow's generation, so the loop stops re-discovering that crude-oil intraday is dead.
4. **Sim-to-real calibration (see §3 Avenue 2).** Feed live-measured slippage/premium into the 2×
   slippage-stress gate so it stresses against reality, not a guess. This is what makes a promoted
   strategy trustworthy with capital.
5. **Capital-aware SizingModel + per-segment numeraire** (ARCHITECTURE W6) before any options/futures
   candidate is scored — the 1-lot additive model understates index-futures return-on-margin ~7-10×.

---

## 3. New directions (ranked by upside)

1. **Wire the self-driving researcher.** Finish §2's loop: hypothesis generator → code-gen builder
   → gauntlet → Findings condition the next night. Converts "validates what I thought of" into a
   machine that manufactures explainable-Python edge while you sleep. Builds on: research plane +
   sandbox + backtest cache + lifecycle archive. Effort **M** (pipeline exists; the hard part is a
   Findings-steered proposal policy). Upside: a compounding asset + the crown-jewel product claim.
2. **Sim-to-real fidelity program.** Instrument every live order (quote@signal, quote@fill, spread,
   latency, SL-M trigger-vs-fill) into telemetry; calibrate a synthetic-premium model from *your own
   fills* (sidesteps the "pointless without a vol surface" objection); feed measured costs back into
   the slippage-stress gate. Builds on: live engine + journal charge math + research gate. Effort
   **M**. Upside: turns "believes it has edge" into "knows" — de-risks every other avenue. (Your own
   deep-research verdict already ranked this gap #1.)
3. **"The Anti-Streak" — gauntlet-as-a-service.** Productize the validation gauntlet as a brutal
   second opinion for the Indian retail-algo market (Streak/Tradetron/AlgoTest users trading
   in-sample, gross-of-charges fiction): upload a strategy → walk-forward, net of the Zerodha charge
   model, DSR/PBO, slippage-stressed verdict. Builds on: full gate suite + charge model + sandbox
   (safely running outsiders' definitions is exactly what the AST sandbox was built for). Effort
   **L** (multi-tenancy + data licensing + running a product). Upside: a moated business riding
   SEBI's 2025 retail-algo accountability wave.
4. **Regime-aware meta-allocator (the fund-of-one layer).** Size each watchlist-strategy's capital
   share from live-vs-backtest health (Avenue 2), the sector edge-map regime signal, and
   cross-strategy correlation; probation becomes a dimmer, not a switch. Builds on: multi-strategy
   engine + conflict resolver + lifecycle + sector edge map. Effort **M**. Upside: portfolio-level
   Sharpe — where a solo trader's staying power actually comes from.
5. **Glass-box provenance — a dossier per live rupee.** hypothesis → gate scores → Finding ID →
   deploy commit → every live trade annotated with which rule fired + the backtest distribution it
   expected → live-vs-expected drift. Builds on: Findings + journal attribution + deploy bridge.
   Effort **S/M**. Upside: kills 2 a.m. doubt, makes probation mechanical, best demo asset in Indian
   retail algo.
6. **"Seatbelt for Kite" — open-core the fail-closed execution harness** (real-margin sizing,
   tick-aware SL-M/internal-stop sync, gap guards, circuit breakers, fail-closed paper/live). Effort
   **M/L** (clean extraction + supporting others' bugs). Upside: reputation/distribution beachhead
   into the exact community Avenue 3 sells to.
7. **India Edge Observatory.** Publish the backtest cache as a living, negative-result-honest map of
   where edge lives and how fast it decays (sector × timeframe heatmaps, charge-drag), without
   revealing entry logic. Effort **S**. Upside: cheap flywheel — audience/credibility/inbound for 3
   and 6.

Sequencing note: 1→2→5→4 is one arc (discover → verify → trust → allocate) that turns this into a
complete autonomous fund-of-one; 3/6/7 monetize its exhaust. Do the internal arc first — it makes
the product arc's claims true.

---

## 4. Worthwhile cleanup (non-essential)
- Per-share margin quote is cached in a per-call closure, re-quoted every ~2.5s tick and unthrottled
  (`runner.py:655`) — hoist to a day-keyed cache; `order.margins` isn't rate-limited.
- `_today_net_realized`/`_today_round_trips` full-scan the `trades` table in Python every ~2.5s
  (`runner.py:1144-1156`) — filter by date at the SQL layer before the table grows.
- No cross-field validation of `intraday_min/max/purple_margin` (`runtime_config.py`) — an inverted
  min>max silently disables all non-purple entries.
- Duplicated hardcoded `0.05` tick constant in `execution_policy.py` and `gtt.py` — import one.
- `set_interval`/`block-entries` don't validate the instrument key exists; two read-only candle
  routes 500 on a bad key instead of returning `{"error"}`.
- `plan_order`'s thin-depth LIMIT branch is dead (`top_qty` always None).
- WS token travels in the query string (unavoidable in-browser; ensure the proxy doesn't log URLs).
- Frontend: add `window.confirm` on "Close now" and "open REAL position" (only KILL has it); make
  `api.ts` `j/post/put` throw on `!r.ok` like `del` does; compute EngineView freshness from client
  `Date.now()` not the server-echoed `state.time` (freezes "fresh" on WS drop); surface `res?.error`
  in the Watchlist/Archive toggles.

---

*Prepared from a 7-subsystem parallel trace + adversarial re-verification. Every ESSENTIAL item
above was confirmed against the source at the cited file:line.*
