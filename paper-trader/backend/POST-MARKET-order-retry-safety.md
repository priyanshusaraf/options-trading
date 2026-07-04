# POST-MARKET FIX — Live order-retry safety

**Raised:** 2026-07-01 live session · **Apply:** after market close, TDD, one at a time, user sign-off.
**Do NOT hot-patch during market hours.** Keep the full pytest suite green + dry-run ledger invariant + `tsc` clean.

Related backlog: `~/.claude/.../memory/post-market-fixes-backlog.md` (this is items **#14** + **#15**).
Root memory: `live-execution-enabled.md`.

---

## The incident (what we observed)

- Live cockpit was armed + Kite authenticated (data feed healthy), 0 open positions.
- Nothing was entering. Root operational cause: **the machine's public IP `103.77.47.13` is not whitelisted in the Kite developer app**, so every *order placement* is rejected by Kite:
  ```
  [ERROR] LIVE EQUITY OPEN not filled [ERROR] NBCC — place failed:
  IP (103.77.47.13) is not allowed to place orders for this app. Update all[owed IPs]
  ```
  (Market **data** has no IP gate, which is why `authenticated: true` and candles flowed — only order routes reject.)
- The engine **re-fired the same entry every ~16s for ~3 hours** (≈150 rejected orders in a 35-min buffer window alone: LODHA 51, NBCC 44, NSE:HEG 27, ANGELONE 26). NBCC logged **~30 order attempts inside a single 15-minute candle** (12:30→12:42).
- Mitigation applied 2026-07-01 15:22: **disarmed** via `POST /api/execution/arm {"armed": false}`. Flood stopped immediately (next scan logged `DISARMED — not taking …`). No positions were ever opened; no capital moved.

**Why this matters even though no money moved:** (a) Zerodha/Kite can suspend an app that floods rejected orders — a config error cascading into an account-level block; (b) if Telegram is on, `live_broker.py:182` fires an alert per failure (~150 alerts); (c) it exposed a real *late-entry* risk on broker recovery (see Defect B).

**Operational (not code):** whitelist `103.77.47.13` at developers.kite.trade → app → allowed IPs. `103.77.47.13` looks like a **dynamic residential IP** — if the ISP rotates it this breaks again; a **static IP** (VPS / fixed-IP tunnel or exit node) is the durable fix.

---

## Defect A (#14) — No circuit-breaker / back-pressure on order-placement failure

**Severity: HIGH** (operational — risks Kite app suspension; alert spam).

### Mechanism (verified)
- Placement is fire-and-forget, once per attempt: `order_executor.py:60-64` — *"Place exactly once. A failure here means nothing reached the exchange"* → returns `OrderResult("ERROR", order_id=None, …)`. Nothing is queued (`allocator.py:12`, `runner.py:11`), orders are `variety="regular"` (not AMO, `kite_order_client.py:41`).
- On non-fill the broker returns `None`:
  - options: `live_broker.py:143` logs `LIVE OPEN not filled` + `_notify` (145) → `return None`.
  - equity: `live_broker.py:180` logs `LIVE EQUITY OPEN not filled` + `_notify` (182) → `return None`.
- The runner just skips and moves on, **with no failure memory**:
  - options: `runner.py:647-648` → `if pos is None: continue  # live order not filled — nothing recorded`.
  - equity: `runner.py:689-690` → `if pos is None: continue`.
- No per-instrument failure counter, no cooldown, no breaker. `grep` confirms the only halts are the **daily-loss** breaker (`risk_controls.py:90`) and **post-stop-out re-entry cooldown** (`risk_controls.py:23`) — neither covers "the broker keeps rejecting orders."
- **No transient-vs-permanent distinction.** A timeout (retry sensible) and `IP not allowed` / invalid token / no-permission (retry is **futile — can never succeed**) are treated identically → a permanent config error becomes an *infinite* retry loop at scan cadence.

### Why it exists
The whole live-order path (`LiveBroker`/`KiteOrderClient`/`LiveExecutionKite`) was only ever exercised against a **mock order client that always fills** (per `live-execution-enabled.md`: the live path had never placed a real order). The "broker says **no**, repeatedly" branch had never run.

### Fix
1. **Classify the failure.** Add a small classifier for Kite `place_order` errors:
   - **PERMANENT** → substrings like `is not allowed to place orders`, `Incorrect \`api_key\` or \`access_token\``, `permission`, `Insufficient permission`. Retrying can never succeed this session.
   - **TRANSIENT** → network/timeout/throttle/`Too many requests`/5xx.
2. **On a PERMANENT placement error → immediate global halt + auto-disarm + ONE alert.** Turn today's ~150-order storm into ≤1–2 orders + a single clear "not whitelisted / bad token — halting entries" message. Surface as a halt reason in `EngineView` (mirror the daily-loss halt UX).
3. **On repeated TRANSIENT failures for one instrument → per-instrument entry block + cooldown** (e.g. N=3 consecutive place-failures → block that key for M minutes, one alert). Reset the counter on any successful fill.
4. Keep counters on the runner (like `last_entry_bar` / `_stopped_at`); reset at session start.

### Acceptance tests (TDD — write first, in `tests/`)
- Mock `OrderClient.place` raising a **permanent** IP error: engine attempts **≤1** placement, then `armed` flips **False** and a halt reason is set; assert `place` call-count ≤ 1 across many ticks; assert exactly one alert.
- Mock `place` raising a **transient** error: after N consecutive failures the instrument is entry-blocked for M minutes; a *different* instrument still trades; a later success resets the counter.
- Regression: a normal fill still opens the position and does **not** trip the breaker.

---

## Defect B (#15) — Fresh-signal guard (#12) does NOT hold on the live intraday-equity path

**Severity: HIGH** (correctness — the exact "chase a gone move" / loss-minting risk). **This contradicts backlog #12's "DONE & offline-verified" status — it passes offline tests but fails live.**

### The intended protection
`risk_controls.py:55-66` `signal_already_evaluated(bar, last_bar)` → `bar <= last_bar`, wired at `runner.py:505-513`. Docstring: *"a signal that fired but couldn't enter is re-attempted every tick and FILLED the instant a slot frees up — at a stale price the original crossover never intended. Gate on the candle time so each crossover is evaluated once; a new entry then needs the NEXT fresh candle."* This is **exactly** the guard against filling a stale/aged signal late.

### The contradiction (observed live 2026-07-01)
If the guard held, an instrument would attempt **at most one** entry per candle. Instead **NBCC fired ~30 attempts inside the single 12:30 candle**. So on the **intraday-equity path the guard is not effectively throttling.** Consequence: the moment the broker recovers (IP whitelisted), whatever signal is active fires immediately — a **late entry after the edge is gone**. (Note: it fires at the *current* live price — `runner.py:550-551` — so it's not a stale-*price* fill; it's a stale-*signal* late entry.)

### Reassurance that IS solid (state clearly to user)
Failed orders do **not** replay — place-once, no queue, `regular` (not AMO). The residual risk is purely the late fresh entry above, not resurrection of old orders.

### Debugging task (root-cause first — do NOT guess-patch)
Primary hypothesis: **`bar = st.get("time")` is not stable within a candle for the intraday / generic-strategy path**, so `signal_already_evaluated` never trips. Investigate:
1. Compare the two state-building paths: default v3 `runner.py:276` (`"time": latest["time"]`) vs generic `runner.py:307` (`"time": _epoch(last["date"])`). The spamming names (NBCC, LODHA, HEG, ANGELONE) are all `expanding_z_v4` → generic path. Is `last["date"]` the completed-candle open (stable, on the 15-min grid) or a forming/`now` timestamp (churns)?
2. Instrument it: log `bar` and `last_entry_bar[key]` at `runner.py:510` on each equity entry evaluation and confirm whether `bar` advances intra-candle.
3. Confirm `last_entry_bar[key]` is actually written (`:513`) on the equity path and never reset elsewhere (`grep` shows only init `:86`, read `:510`, write `:513` — verify no clear).
4. Check whether the equity branch reaches the guard at all before appending to `eq_cands` (it should — guard is `:510`, equity branch `:517`).

### Fix
- Make the bar key a **stable completed-candle epoch** for *all* strategy paths (align generic `:307` with the v3 `:276` semantics), so `signal_already_evaluated` trips within a candle.
- Ensure a **non-fill drops the signal for that candle** (both options + equity): `last_entry_bar[key]` is set once the signal is *evaluated*, regardless of fill outcome — so broker recovery cannot trigger a backlog of late entries.

### Acceptance tests (TDD)
- Signal active + broker failing every tick → **exactly one** entry attempt per candle for that instrument (drive multiple sub-candle ticks; assert one attempt).
- Broker recovers mid-candle-N whose crossover was already evaluated → **no** entry fires for candle N; a fresh crossover on candle N+1 **does** fire.
- Use a **live-representative** bar-time fixture (the churning timestamp the live generic path produced) so the regression can't pass with a stable-time stub the way #12's original test did.

### Nice-to-have (same area)
- The `INTRADAY {dir} {key} …` INFO at `runner.py:681` (and the options `ROUTE` log `:642`) is emitted **before** placement, so logs read like a fill that didn't happen. Log it as an *attempt* or only on confirmed fill.

---

## Shared root cause & sequencing
Both defects trace to one gap: **the live-order failure/retry path was never validated against a broker that rejects.** Fix order:
1. **A (#14) circuit-breaker first** — stops the storm class of bug outright (highest operational risk).
2. **B (#15) guard-#12 live regression** — root-cause, then fix + a live-representative test.
3. Re-run: full pytest suite, `scripts/dryrun.py` ledger invariant, frontend `tsc`. User reviews; adopt on next backend restart.
