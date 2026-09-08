# Feature review — what's here, what's missing, what's dead weight

*2026-08-01 · branch `feat/exec-completeness` · a FEATURE review, not a code review: every
user-facing capability judged on whether it earns its place in a product that must (a) run
itself, (b) be trustworthy, and (c) be recommendable to someone else.*

**Evidence base.** Every "used / unused" verdict below is a row count from the live
production database on 2026-08-01, not an impression:

| | |
|---|---|
| Real trades since 2026-07-13 | **72**, net **−₹166.37** |
| Exits chosen by the bot itself | 27 (net **−₹2,927**) |
| Exits chosen by the owner closing manually | 45 (net **+₹2,761**) |
| `TARGET` exits, all time | **0** |
| Instruments in the universe | 36 (28 equity, 8 options) |
| Backtest runs / results | 11 / 277 |
| Watchlists / watchlist members | **0 / 0** |
| Generated strategies / lifecycle rows | **0 / 0** |
| Journal snapshots / manual fills / artifacts | **1 / 0 / 0** |
| Earnings dates known | **3** of 28 stocks |
| Database | **108 MB** on a 1 GB box, +5 MB/day |
| Top-level tabs / journal surfaces / API routes | 11 / 14 / 56 |

---

## 1. The headline

The engineering is good and the product is not finished — but not in the places the roadmap
assumed. The gap is not missing features. **It is that the software has 25 destinations and
one user, who uses about five of them, and the single most important loop — deciding when
to get out of a trade — is still being run by a human.**

Three sentences that should govern the rest of the week:

1. **The bot enters; the human exits.** 45 of 72 real exits were the owner closing by
   hand, and those manual exits are the only reason the book is not deeply negative. Until
   the bot's own exits are trusted, nothing else about "autonomous" is true.
2. **Roughly a third of the product has never been used once.** Watchlists, the strategy
   codegen/archive, the research plane and the journal all have zero or near-zero rows in
   production after a month.
3. **Nothing was measurable from inside the app.** Ledger drift, database growth, exit
   quality, event blackouts — every one of those had to be discovered by SSH-ing into the
   box. Four of them became app-visible this week; that is the pattern to continue.

---

## 2. Feature-by-feature verdict

### The trading engine — the part that works

| Feature | Verdict | Notes |
|---|---|---|
| Two-lane engine (signal ~2.5s / risk ~1s) | **Keep** | The separation is genuinely good design: a slow broker call cannot delay an exit. |
| Provider seam (mock ↔ Kite) | **Keep** | The reason 1,200 tests can run offline. This is a real asset and a real selling point. |
| Safety gates + ARM | **Keep** | Four independent gates plus per-session ARM. Structurally hard to trade by accident. |
| Paisa-exact ledger + invariant check | **Keep** | Reconciles on every build. Rare in retail software. |
| Charge model (segment-aware) | **Keep, verify** | Rates still flagged "indicative". Blocks futures. One contract note settles it. |
| Adaptive order routing | **Keep** | Correct instinct — for options, execution cost dominates brokerage. |
| Equity-intraday (MIS) segment | **Keep** | 70 of 72 real trades. This IS the product right now. |
| Options segment | **Dormant, keep** | `max_open_positions=0` in production — deliberately off. Fine. But see §4 on the 319k option rows still being written for it. |
| Exit logic (SL / TP / lockstep / profit-lock) | **Fix — the #1 job** | `TARGET` has never fired in 72 trades because the target sits outside the range these trades occupy. Retuned this week from real excursion data; unproven until a no-touch trial runs. |
| Event-risk blackouts | **New this week** | EIA gas/crude windows (DST-correct), index weekdays, bullion into expiry, earnings days. Shared by engine + backtester + UI. |
| Daily loss halt / drawdown halt / round-trip cap | **Keep** | The round-trip cap actually fired on 2026-07-30, so it is load-bearing, not decorative. |
| Daily profit-lock | **Keep, unproven** | Built 2026-07-24, has never fired in production. |
| Ledger re-anchor to broker equity | **New this week** | The reported equity was ₹49,833 against a much smaller real account for three weeks. |

### The cockpit — 11 tabs for one person

| Tab | Verdict | Notes |
|---|---|---|
| **Watchlist** | Keep | The daily driver: what's enabled, which product, purple/red flags. |
| **Active Positions** | Keep | The other daily driver. |
| **Dashboard** | Keep, simplify | Overlapping equity curves by segment AND strategy AND instrument. Three of those are the same question. |
| **Trade Log** | **Merge into Dashboard** | A table of trades and a page of trade analytics are one screen, not two. |
| **Calendar** | Keep | Bot-vs-you per day is genuinely the most honest screen in the app. |
| **Engine / Logs** | Keep, demote | Diagnostics, not a peer of Watchlist. Belongs behind a "system" area with Storage and provider health. |
| **Options Calc** | **Cut or hide** | A standalone Black-Scholes calculator, in a product whose options segment is switched off. It is a tool, not a feature of this system. |
| **Backtests** | Keep | 11 runs, 277 results — actually used, and the honest validation path for the equity book. |
| **Portfolio** | **Cut** | Fronts the research plane (dormant), watchlists (0 rows) and promotions (0 rows). It is already hidden when research is off; that is the right permanent state. |
| **Journal** | Keep, now simplified | Was 14 surfaces and 1 row of data. Given a real walkthrough and a 3-section default this week. |
| **Settings** | Keep | 87 knobs, now all documented with consequences and usable on a phone. |

### The research plane

| Feature | Verdict |
|---|---|
| Isolated research DB, immutable specs, fail-closed guards | **Keep frozen.** The isolation design is genuinely good and cost nothing to leave dormant. |
| Nightly loop, hypothesis planner | **Cut from the roadmap for now.** Never switched on. |
| Sandboxed strategy code generation (AST allow-list, no-builtins exec) | **Cut from the roadmap for now.** 0 generated strategies in a month. Impressive; unused. |
| DSR / PBO / deflated Sharpe statistics | **Broken and dormant** — `var_sr` defaults to 0 so deflation never engages, PBO unimplemented. Do not present these as working. |

Blunt reading: the research plane is a well-built laboratory that has never run an
experiment. It is not harmful — it is isolated and off — but every hour spent on it is an
hour not spent on the exit loop that is losing money today.

### Watchlists, strategy archive, promotions, codegen

**Cut, or finish deliberately.** Built in July, `0` rows of every kind in production a month
later. This is a whole subsystem — multi-watchlist, conflict/incumbency, dev-blacklist,
archive, approve→deploy bridge — with no user. Either delete it from the surface area or
schedule a week to make it the way instruments are actually managed. Leaving it half-present
is the worst option: it is code that must keep compiling, keep passing tests, and keep
confusing anyone reading the product.

---

## 3. What's missing to call this "autonomous"

Ranked by how much each one actually blocks the claim.

1. **A trusted exit.** The bot has never taken a profit by its own decision. Everything else
   is secondary. The parameters are now set from real data; what is missing is the
   *evidence* that they work, which only the no-touch trial produces.
2. **Slippage telemetry.** Charges are modelled to the paisa; realised slippage — the
   dominant cost in options and a real one in MIS equity — is gated at entry and never
   measured afterwards. The system cannot currently tell you what execution costs it.
3. **A "why did nothing happen today?" answer.** A quiet bot and a broken bot look
   identical. The event-risk panel added this week is the first piece of this; it needs to
   extend to every skip reason (halted, stale signal, cutoff, cooldown, no margin) as a
   single daily digest.
4. **Position-level attribution.** Which instruments, which times of day, which entry
   conditions actually make money — the data exists in `trades` but nothing surfaces it.
   With 72 trades this is premature; at 300 it is the most valuable screen in the product.
5. **Unattended recovery.** The engine recovers its order journal on restart, but the daily
   Kite re-auth is manual and permanent (ToS). "Autonomous" therefore has an honest asterisk:
   one human action per morning. Say so plainly rather than letting a buyer discover it.

---

## 4. What's redundant, and what it costs

- **319,068 rows of option-chain data** collected for a segment that is switched off. It is
  a deliberate cost — Kite sells no historical chains — but it is the largest single writer
  to a database that reached 108 MB on a 1 GB box. Retention shipped this week; the decision
  to keep collecting should now be a conscious one, taken on the Storage screen.
- **Two ways to see trades** (Trade Log, Dashboard) and **three overlapping equity curves**.
- **Two journals**: `journal.db` exists and is dead; `ledger.db` is the live one. Delete the
  dead one before anyone else reads this codebase.
- **A 644-line in-app Guide** alongside a 14-surface workspace, for a feature with one row of
  data. The Guide is well written and was not the problem; the surface count was.
- **`intraday_leverage`** survives as "fallback estimate only" after the cap was removed —
  a knob that looks like it governs sizing and does not.
- **`intraday_block_weekday` / `expiry_day_block_keys`** now largely duplicate the event-risk
  weekday rules. Keep one; the old pair has an escape hatch the new engine reuses, so the
  merge is straightforward but should be done deliberately.

---

## 5. What's missing to sell it or recommend it

Be clear-eyed about what "sellable" means here, because the honest answer changes the plan.

**As multi-tenant SaaS: not close, and not a week away.** The system is single-user,
single-account, single-process by design. Every ledger, every setting and every DB row
assumes one owner. There is no tenancy, no per-user isolation, no billing, no signup, no
password (a shared bearer token), no rate-limit isolation, and a 1 GB box that OOMs. Turning
this into SaaS is a rewrite of the persistence and auth layers, not a feature.

**As a licensed single-user product someone else runs: genuinely plausible, with four gaps.**

1. **Install.** There is no path for another person to get this running: no Docker image, no
   `.env` template walkthrough, no "connect your Kite account" flow that assumes nothing.
   Deployment is an rsync script pointed at one specific droplet.
2. **First-run.** A new user lands in a cockpit with 36 instruments seeded from the owner's
   own preferences and 87 settings. The journal got a walkthrough this week; the product did
   not.
3. **Legal.** SEBI's retail-algo framework and Zerodha's algo-registration requirements are
   flagged "to confirm" and have never been confirmed. **Selling software that places
   automated orders on someone else's broker account without settling this is the single
   biggest non-technical risk in the project.** Resolve it before any sale, not after.
4. **A track record you can show.** 72 trades, net −₹166, and no trade ever exited on the
   bot's own target. This is the honest blocker on recommending it to anyone: the engineering
   is demonstrable, the edge is not yet. A month of the no-touch trial changes that
   conversation completely — in whichever direction the data goes.

**What is already sellable-grade:** the safety architecture, the offline determinism, the
paisa-exact accounting, the charge model, and now the event-risk engine. Those are the parts
a knowledgeable buyer would check first, and they hold up.

---

## 6. Design recommendations

1. **Collapse 11 tabs to 6.** Watchlist · Positions · Journal · Analytics (Dashboard + Trade
   Log + Calendar) · Backtests · System (Engine/Logs + Storage + Settings). Cut Options Calc
   and Portfolio from the top level.
2. **Make every screen answer "is this number real?"** The ledger-drift badge added this week
   is the template: when the app cannot vouch for a figure, it should say so on the figure,
   not in a log. Apply the same to backtest results (which now exclude event-blackout bars)
   and to any equity-curve percentage.
3. **One daily digest.** After the close: what fired, what was skipped and why, what the exits
   did versus what they could have done, ledger drift, DB growth. One screen, one Telegram
   message. This replaces four separate places you currently have to look.
4. **Make the exit visible while the trade is open.** Show the profit-lock floor, the current
   peak, and the distance to each on the open position. The reason the owner closes by hand
   is that the bot's intentions are invisible in the moment.
5. **Stop building a second application inside the first.** The journal has its own router,
   keymap, storage layer and design system. It is good work and it is why it went unused.
   Its future should be fewer surfaces, not more.

---

## 7. The rest of this week, in order

1. **Deploy what was built this week** and clear the two `runtime_config` overrides that
   make the new exit defaults inert (`intraday_profit_lock_threshold=450`,
   `intraday_profit_lock_frac=0.3`). Without that step, the most important change of the week
   does nothing.
2. **Run the no-touch trial** — five sessions, armed, no manual closes. This is the only
   experiment that can convert this from an entry engine into an autonomous system, and every
   other claim waits behind it.
3. **Slippage telemetry.** Cheap to build, and it closes the last hole in the cost model.
4. **Collapse the navigation** (§6.1) and delete the dead `journal.db`.
5. **Settle the regulatory question.** One afternoon with Zerodha's algo policy and SEBI's
   retail-algo circular. It gates everything commercial.

Deliberately NOT this week: the research plane, index futures, MTF, and anything in the
watchlist/codegen subsystem.
