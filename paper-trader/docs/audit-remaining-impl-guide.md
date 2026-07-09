# Remaining audit fixes — implementation guide (Fable-advisor spec)

Airtight, code-cited plan for the 4 items still open after 22 findings were fixed. Produced by a
Fable-tier architecture advisor; resolves the two open design forks. **Build order: H16 → H13 →
H2 → C6 → H9** (H16 is already done, commit `bb8777e`). Ground rules for every implementer:

- Ledger invariant is sacred: `cash == initial_capital + realized_pnl − Σ(open entry_cost)` to
  the paisa (`app/engine/broker.py:reconcile`, asserted by `scripts/dryrun.py`). Any booking
  change must keep `reconcile()["diff"] == 0`.
- New **tables** need only a model in `app/db/models.py` (`create_all` in `init_db`). New
  **columns** additionally need `app/db/session.py:_migrate_schema`. Mirror `tests/test_migration.py`.
- `app/backtest/cache.py:SCHEMA_VERSION` (v6): a bump invalidates the whole result cache → full
  recompute. **C6 and H9 share ONE bump to v7.**
- TDD; run `scripts/dryrun.py 700` + full suite after each item. Sandbox: pytest only, never bare
  python that imports the app (it reads the live `.env`/DB), never touch `paper_trader.db`.

---

## H13 — Persisted order journal + startup recovery (LARGE; sonnet + review on `_execute`/`recover_journal`)

**Invariant (comment on the model):** the journal's WORKING set always equals
`_inflight ∪ _pending_entries`; every site that pops those dicts marks the row terminal.

1. **`OrderJournal` model** (new table, no `_migrate_schema`): id PK; order_id String(32) nullable+indexed;
   tradingsymbol; instrument_key; side; kind ("options"|"equity"); qty Int; intent ("ENTRY"|"EXIT");
   context_json Text; status String(12) indexed ("WORKING"|"TERMINAL"); resolution String(24)
   (FILLED/REJECTED/CANCELLED/ADOPTED/DEAD/RACED_FILL/NEVER_PLACED/UNKNOWN); filled_qty Int; avg_price
   Float; placed_at DateTime; resolved_at DateTime nullable.
2. **`order_executor.execute_order`**: add `on_placed: Callable[[str],None]|None=None`, called right
   after `order_id = client.place(req)`, try/except-wrapped so a callback error can't disturb the order.
3. **`live_broker._execute`**: write a WORKING row BEFORE placement (order_id NULL), set order_id via
   `on_placed`, mark TERMINAL on resolution. Absorb `_actual_fill`+`_note_order_outcome`:
   `_execute(req, *, intent, kind, context=None) -> (res, filled, avg)`; the 4 callers drop their own
   `_actual_fill`/`_note_order_outcome`. Terminality mirrors the exact `_record_inflight`/`_pending_entries`
   conditions. **ALL journal I/O try/except-wrapped — a journal failure must NEVER block/fail a real
   order.** Use `self.s`. context_json is JSON-safe (rebuild OptionQuote(**…)+get_instrument on recovery,
   never pickle): options ENTRY `{inst_key,direction,reason,spot,params,q:{…}}`; equity ENTRY
   `{inst_key,direction,charge_segment,reason,params,strategy_key}`; EXIT `{inst_key,position_id,segment}`.
4. **`journal_mark_terminal(order_id, resolution, filled=0, avg=0.0)`** — call from `_ensure_no_inflight`
   (every terminal branch), `cancel_working_entries`, `adopt_pending_entries` (ADOPTED/DEAD).
5. **`recover_journal(now)`** on LiveBroker (no-op on PaperBroker). Per WORKING row: NULL order_id → tag
   sweep, else UNKNOWN+notify; status raises → keep WORKING (fail open); ENTRY filled>0 → rebuild
   `_pending_entries` then call `adopt_pending_entries(now)` ONCE (reuse, no 2nd adoption path); ENTRY dead
   → DEAD; ENTRY working → rebuild both dicts; EXIT filled≥qty → book LEDGER-ONLY at real avg via
   segment routing like `reconcile_orphans` (beats the reconciler's stale mark); EXIT partial →
   `book_partial_close`/`book_partial_close_equity`; EXIT working → `_inflight`. Tag sweep: add
   `orders()` to `kite_order_client.py`; today's tag=="pt-bot" orders absent from the journal → log+notify
   ONLY, never auto-book.
6. **Wire** in `main.py` lifespan after `EngineRunner()` and BEFORE the loop tasks:
   `await asyncio.to_thread(runner.broker.recover_journal, runner.provider.now())` (try/except; never blocks
   startup). Ordering matters — recovery before the signal loop can re-enter an instrument.

Tests (`tests/test_order_journal.py`, FakeClient): WORKING row w/ order_id; FILLED/REJECTED/place-raises →
correct TERMINAL, no NEVER_PLACED leak; TIMEOUT entry → WORKING+dicts, then a FRESH LiveBroker on the same
DB + COMPLETE status → recover adopts, ADOPTED, invariant 0; EXIT WORKING → COMPLETE → ledger-only close,
`client.placed` empty during recovery; dead → DEAD; tag sweep surfaces+books nothing; the 3 pop-sites mark
terminal; init_db creates the table.

**Risk:** journal failure must be non-fatal on the order path (the #1 dangerous inversion); recovery must
run before the loops; don't skip old WORKING rows.

---

## H2 — Unify live trailing onto the validated ratchet (Option A) (MEDIUM-LARGE; strongest implementer / adversarial review)

**Decision: Option A.** Port `RatchetState` (`app/backtest/ratchet.py`) into the live path for strategies
that declare `risk_model` (today only `expanding_z_v4`). (B) — validating the live percent-trail in the
backtester — is impossible without a premium series and inherits every BS error; (A) validates against real
bars, which schema-v6 already did. Live exit stack for rm strategies: (1) premium hard stop/target (GTT
trigger, unchanged); (2) ratchet SPOT stop (bar-cadence, close-confirmed, PRIMARY); (3) strategy exit. The
legacy `exit_monitor.trailing_stop` is DISABLED for ratchet-managed positions, kept verbatim for no-rm
strategies (default v3 → byte-identical behavior). **Parity contract (docstring):** stops evaluate only on
completed candles of the live interval, close-confirmed, entry ATR frozen at fill from the signal bar,
high-water from completed-bar extremes, no management on the fill bar.

Steps: (1) Position cols `entry_atr, ratchet_hw, spot_stop, ratchet_last_bar_ts` (+ `_migrate_schema`,
nullable = not ratchet-managed). (2) `RatchetState.restore(direction, fill_price, entry_atr, rm, *, hw,
stop)` classmethod (no re-derive). (3) `broker.open_position` accept/persist `strategy_key` for options
(equity already does). (4) `scan_signals` compute Wilder ATR for rm strategies + stash last completed bar
atr/high/low/close. (5) Seed at entry in `process_entries` after a successful rm options open:
`entry_atr, ratchet_hw=spot, spot_stop=spot − d·initial_risk_atr·atr, ratchet_last_bar_ts`. (6) Bar-cadence
update in `scan_signals` for held rm positions: bars with `ts > ratchet_last_bar_ts` (and > entry bar),
`RatchetState.restore(...).update(...)` per bar, persist, set `state[key]["ratchet_exit"]` on `stop_hit`.
(7) `exit_monitor.evaluate_exit(..., ratchet_exit=False)` returns `(True,"RATCHET_STOP")` after the premium
guards, before strategy flags; `mark_and_exit_positions` passes `st.get("ratchet_exit")`. (8) In
`_apply_trailing`, after the `ensure_stop_protection` self-heal, `return` early for rm-managed positions
(GTT stays parked at the initial premium stop; no BS-inversion re-pricing in v1).

Tests: **parity test** (backtest simulate vs a live-style drive → identical stop series + exit bar);
restart persistence (restore from cols → same stop); no-rm regression (v3 untouched); priority (premium
STOP_LOSS wins over RATCHET_STOP); never-loosen; bar-idempotence via `ratchet_last_bar_ts`.

**Risk:** don't feed the fill/signal bar into `update()`; don't double-consume bars; rm lookup uses frozen
`pos.strategy_key`; ship behind the risk_model declaration (per-strategy opt-in).

---

## C6 — Synthetic-premium backtest path (LARGE but pure/offline; sonnet, police scope)

**IV model: realized-vol proxy × vol-risk-premium.** `sigma(t)=clamp(RV_20d, 0.10, 2.0)×iv_rv_multiplier`
(default 1.15), flat across strikes, per-bar from trailing DAILY closes ffill'd onto intraday. Leave a
`sigma_source` hook for a fitted surface later.

New `app/backtest/premium.py`: `simulate_premium(candles, inst, interval, *, strategy, params, capital) ->
(list[BTTrade], BTMetrics)`. Entry (same pending→next-bar-open as engine.py): ATM strike
`K=round(S0/strike_step)·strike_step`, CE long / PE short, `T0=entry_dte_days/365` (default 14),
`entry_fill=bs_price(S0,K,T0,r,σ)·(1+half_spread)`, qty=lot_size, skip if premium<₹0.50 or σ unavailable
(warmup). Per bar: `T_i=T0−(ts_i−ts_fill)/365` calendar seconds (theta free), premiums from `bs_price` at
close + direction-adverse/favorable spot extremes. Exit stack imports the SAME live code
(`evaluate_exit`, `trailing_stop`, `RatchetState`) — trail skipped for rm strategies (H2), stop beats target
on a tie-bar, ratchet on the underlying like engine.py, expiry forced at T≤1/365. Charges via
`compute_charges(inst.segment, side, premium, qty)` (options schedule), `premium_spread_pct` default 0.02.
Skip cash-segment / no-options cells (`premium_error`). Reuse `BTTrade`+`compute_metrics`.

Wire: `sweep._one` runs it in try/except after the spot simulate (a premium bug must not kill the spot cell);
`BacktestResult` gains `premium_*` columns (+`_migrate_schema`, `summary`, `_copy_from_cache`, `/export`);
`cache.SCHEMA_VERSION → 7` (shared w/ H9) + add `iv_rv_multiplier, premium_spread_pct, entry_dte_days` to
`params_signature`; surface premium cols in `/results` + the Backtest view (report BOTH edges).

Tests: theta decay on flat spot; convexity (uptrend CE return > spot); stop arithmetic to the paisa;
trail parity vs a direct `trailing_stop` call; expiry cutoff (never T≤0 into bs_price); charges; no-options
cell; v6→v7 cache invalidation; determinism snapshot.

**Risk:** σ warmup (skip pre-warmup entries, never price at intrinsic≈0); calendar-time tz hygiene; keep
signature construction solely in `cache.params_signature`; label as a MODEL (promotion needs spot AND
non-catastrophic premium edge; IV crush unmodelled — say so).

---

## H9 — Out-of-sample gate (SMALL-MEDIUM; sonnet)

The sweep fits no parameters, so the hazard is grid-level selection bias (600 cells sorted by return), not
per-cell overfit. Minimal correct gate: ONE chronological IS/OOS split from the existing single simulate
run — partition trades by `entry_time` against `split_ts` = candle at ⌈70%⌉ of the clipped series. No 2nd
simulate.

Steps: `metrics.split_metrics(trades, capital, split_ts)` (partition + two `compute_metrics`); `sweep._one`
computes `split_ts`, partitions both spot AND premium (C6) trade lists; `BacktestResult` gains
`split_ts, is_*, oos_*` cols (+ `_migrate_schema`, `summary`, `_copy_from_cache`, `/export`); shares the v7
bump with C6; `/results` default `min_trades 1→10`, new `min_oos_trades`, per-row
`oos_pass = oos_trades>=20 and oos_expectancy>0 and (oos_profit_factor or 0)>=1.0`, `oos` sub-dict for a UI
badge, count OOS-failed rows in the disclosure. Don't hard-block `/portfolio/add`; the promote flow consumes
`oos_pass`. Add a static `grid_note` when >100 cells.

Tests: partition correctness incl. a straddling trade (IS by entry time); all-IS edge (oos_trades==0, no
crash); `/results` 3-trade cell now in `skipped_low_trades`; `oos_pass` truth table; CSV carries new cols;
v6→v7 invalidation.

**Risk:** a 1-trade cell must be impossible to mistake for promotable (the default raise + badge is the
fix); don't double-count the open-at-end trade; coordinate the v7 bump with C6.
