# Ground-truth audit — 2026-07-28

Read-only audit. Every claim in `CLAUDE.md` and `docs/product-overview.md` was treated as
suspect until confirmed against code or a database. No source file was modified.

**Scope of evidence**
- Working tree: `paper-trader/`, branch `feat/exec-completeness`, HEAD `2b3356d`.
- `origin/main` = `d9903cd` (2026-07-14). **HEAD is 101 commits ahead of `origin/main`.**
- Databases queried (copied to a scratch dir first; originals untouched):
  - `paper-trader/vps-snapshots/paper_trader-offload-20260723-094218.db` — production, 45MB, newest available.
  - `vps-snapshots/2026-07-15/pt-snap-20260715.db` — production, older.
- **Caveat that limits every "is it deployed" question:** the newest production snapshot is
  from **2026-07-23 09:41**. Sixteen commits on this branch are dated 2026-07-24 or later.
  No snapshot, log, or artifact in this repo reflects the currently-running VPS process, and
  this audit did not contact the VPS. Deployment state is therefore marked
  **NOT ESTABLISHED** wherever it depends on that.

**Severity legend** — `DOC BUG` = code is right, prose is wrong. `CODE BUG` = prose describes
the intended behaviour and the code fails to deliver it. `PREMISE ERROR` = the claim as quoted
in the audit request does not exist in the named file.

---

## Summary table

| # | Item | Verdict |
|---|---|---|
| 1 | Equity intraday sizing | **DOC BUG** (CLAUDE.md) + **PREMISE ERROR** (product-overview) + latent code inconsistency |
| 2 | Equity anchoring to ₹50k | **CODE BUG** — auto-reanchor exists but can never fire on the live ledger; not on `main` |
| 3 | "Live path has never placed a real order" | **DOC BUG, severe** — 50 real orders, 34 live trades |
| 4 | Test counts | **DOC BUG** — "~67 files" vs 141 files / 933 tests |
| 5 | Options −35% / +60% | **DOC BUG** — stop is **−30%**, not −35%; ratchet claim is accurate |
| 6 | `scripts/deploy.sh` / `--exclude .env` | **Neither exists.** Guard is prose only; one doc falsely says it is enforced |
| 7 | Other contradictions | 11 further items, listed in §7 |

---

## 1. Equity intraday position sizing

**Claim A — `CLAUDE.md:200`:** "**equity_intraday** (MIS, opt-in via `intraday_enabled`) —
margin-sized at 5x leverage, hard cap of 3 concurrent".

**Claim B — as quoted in the audit request,** attributed to `docs/product-overview.md`:
"sized against full real broker margin (the 2.5× leverage cap was deliberately removed)".

### Reality

**Claim B does not exist in `docs/product-overview.md`.** `grep -n -i "leverage\|2\.5\|real
broker margin" docs/product-overview.md` returns only three unrelated hits — `:137`
("over-leverage trap", reinforcement), `:165` ("without leverage", the *backtester*), and
`:451` ("high-leverage developments", roadmap prose). The only thing the overview says about
equity-intraday sizing is `docs/product-overview.md:191-193`: "trades the underlying on margin
with its own concurrency cap" — vague, but not false. **Recorded as a PREMISE ERROR**: the
sentence is not in that file. Its substance *is* stated in code, at
`backend/app/core/config.py:175-178`.

**The rule actually implemented (live, Kite-authenticated):** size to **real Zerodha margin**,
with **no leverage cap**.

1. Deployable cash — `backend/app/engine/runner.py:1031` → `capital.py:18-31`. In live mode
   headroom is clamped by the real account: `min(cap_headroom, account_available -
   capital_reserve)`, where `account_available` is Kite `margins()["equity"]["available"]
   ["live_balance"]` (`backend/app/providers/kite.py:139-153`). If funds cannot be read it
   returns `0.0` — **fails closed** (`capital.py:23-27`).
2. Slot cap — `runner.py:1017`, `max(0, intraday_max_positions - open equity positions)`.
3. Target margin per name — `intraday_max_margin = 7,000.0`
   (`config.py:188`, used `equity_entry.py:285`); purple names get
   `intraday_purple_margin = 10,000.0` (`config.py:189`, used `equity_entry.py:283`).
4. Self-funding clamp — `effective_target = min(target_margin, cash)`
   (`equity_entry.py:260`).
5. **Quantity** — `runner.py:668-716` `_intraday_margin_sizer`: one real
   `kite.order_margins()` MARKET/MIS quote per (symbol, side), cached
   (`runner.py:701-708`; provider call at `backend/app/providers/kite.py:159-172`), then
   `per_share = total / probe_qty` (`runner.py:709`) and
   `qty = int(target_margin // per_share)` (`equity_entry.py:32-40`, called `runner.py:714`).
6. Floors — skip if `qty < 1` (`equity_entry.py:262-265`) or if real margin is below the
   `intraday_min_margin = 2,500.0` dust floor (`config.py:187`,
   `equity_entry.py:270-273`).
7. Leftover cash **is** deployed: each accepted pick does `cash -= margin`
   (`equity_entry.py:280`) and the next name sizes against what remains
   (`equity_entry.py:256-260`), bounded below by the dust floor.

### Is there a leverage cap?

**No binding cap in the live path.** `intraday_leverage` survives in exactly two roles:
the seed for the probe quantity, and the fallback sizing model when live margin is
unavailable.

- **Definition:** `backend/app/core/config.py:201` — `intraday_leverage: float = 5.0`.
  The comment above it (`config.py:175-178`) is explicit and is the authoritative in-code
  statement: *"The earlier artificial `intraday_leverage` notional cap (Task 2, R2
  2026-07-16) is REMOVED — it was throttling real margin to ~4.5k. `intraday_leverage` now
  serves ONLY as the pure fallback estimate for paper/mock or a failed margin quote."*
- **Runtime override:** registered overridable at
  `backend/app/core/runtime_config.py:42`, bounded `(1.0, 20.0)` at `runtime_config.py:107`.
  **The production `runtime_config` table does not contain `intraday_leverage`** (query in
  §Appendix A), so production uses the Settings default `5.0` — in its fallback-only role.
- **Use sites:** `runner.py:689` (probe/fallback), `runner.py:1032` (passed to the selector),
  `equity_entry.py:24-29` (`equity_qty`), `:232-234` (fallback sizer), `:241` (ordering key
  only), `broker.py:114,118` (booking fallback when `margin` is not supplied).
- **History:** `cefa966` (2026-07-16) *"make intraday_leverage a binding notional cap"* →
  `0f93f9a` (2026-07-22) *"size by full real margin (7k/10k) + widen exits"* removed it.
  Earlier, `f53c07a` (2026-07-14) *"size intraday MIS to real Zerodha margin, not assumed 5x"*.
  All three are ancestors of HEAD; none are on `origin/main`.

**Verdict on Claim A: DOC BUG.** "Margin-sized at 5x leverage" describes behaviour that was
removed on 2026-07-22. In live mode sizing is real-margin-driven; 5x is only the paper/mock
fallback. Separately, "hard cap of 3 concurrent" matches the code default
(`config.py:186`) but **not production** — the production `runtime_config` row sets
`intraday_max_positions = 4` (§Appendix A).

### Latent code inconsistency (not a doc issue)

`runner.py:689`, `runner.py:1032`, and `broker.py:114` each read the knob as
`.get("intraday_leverage", 2.5)` — a hardcoded **2.5** fallback that contradicts the
documented 5.0 default. It is currently unreachable because `effective()` always populates the
key, but any future code path that builds `params` without it would silently size at 2.5x.
Worth fixing.

---

## 2. Starting capital / equity anchoring

**Claim — `CLAUDE.md:54`:** "Starting capital is ₹50,000, persisted across restarts."
Also `CLAUDE.md:84` describes as an *open E0 bug*: "equity curve stuck on the ₹50k base".

### Reality on this branch

The ledger is still **seeded** at the synthetic ₹50,000, and on live mode there is now a
**one-shot auto-reanchor** to real broker equity — but its guards mean it can never fire on the
actual production ledger.

- Synthetic base: `backend/app/core/config.py:49` `initial_capital: float = 50_000.0`;
  `backend/.env:17` `PT_INITIAL_CAPITAL=50000`.
- Seeded into the ledger: `backend/app/db/session.py:236-237`.
- The curve is `cash + open MTM`, i.e. anchored to `capital_state`:
  `backend/app/engine/broker.py:448-461` writes `EquitySnapshot(equity=cap.cash + mtm)`.
  Dashboard reads `analytics.py:110-124` (`"initial": cap.initial_capital`) and
  `analytics.py:133-141`. The chart's baseline line is drawn from `cap.initial` —
  `frontend/src/views/DashboardView.tsx:164`.
- **Auto-reanchor (E0.2):** `backend/app/engine/runner.py:1500-1547`
  `_maybe_auto_reanchor` → `backend/app/engine/ledger_reconcile.py:16-41` `plan_reanchor`,
  which sets `initial_capital = cash = account_baseline = margins()["equity"]["net"]` and
  `realized_pnl = 0`. Fires once per process (`runner.py:121` `_reanchored`).

### The guards make it inert in production

`_maybe_auto_reanchor` no-ops unless **all** hold (`runner.py:1500-1547`): provider is kite;
`net > 0`; the book is flat; `cap.initial_capital == settings.initial_capital` **and**
`realized_pnl == 0`; and there are **zero `Trade` rows**.

Production violates the last two. From the 2026-07-23 snapshot:

```
sqlite> SELECT initial_capital, cash, realized_pnl, account_baseline FROM capital_state;
50000.0 | 50744.12 | 744.120000000006 | 17948.15
sqlite> SELECT COUNT(*) FROM trades;
34
```

So the live ledger is **permanently pinned to the ₹50,000 synthetic base** unless the manual
`backend/scripts/reconcile_ledger.py` path is run. The scale of the misreport is measurable —
the platform reported ₹50,744 equity while the real Zerodha account net was between ₹14,236
and ₹27,441 over the same period:

```
sqlite> SELECT day, account_net FROM daily_account_snapshot ORDER BY day;
2026-07-10  17948.15     2026-07-16  23887.02
2026-07-11  17922.2      2026-07-17  14235.65
2026-07-12  17922.2      2026-07-18  14235.65
2026-07-13  27441.45     2026-07-20  22133.35
2026-07-14  27387.3
2026-07-15  26366.01
sqlite> SELECT equity, cash, realized_pnl FROM equity_snapshots ORDER BY time DESC LIMIT 1;
50744.12 | 50744.12 | 744.120000000006
```

Real account equity is fetched (`backend/app/providers/kite.py:139-157`) and persisted
(`daily_account_snapshot`), and `runner.py:1810-1832` attaches `account_available`/
`account_net` to the state payload — but **additively**; it does not change `equity` or
`initial`.

### Has it shipped?

- Commit **`8abca46`** (2026-07-24) *"fix(pnl): E0.2 auto-anchor the live equity curve to real
  broker equity, not ₹50k"*.
- `git merge-base --is-ancestor 8abca46 HEAD` → **0 (yes, on this branch)**.
- `git merge-base --is-ancestor 8abca46 origin/main` → **1 (no, not on main)**.
- Branches containing it: `feat/exec-completeness`, `wip/e2-index-futures`. `origin/main`
  (`d9903cd`, 2026-07-14) predates all of Workstream E.
- Whether the running VPS process carries it: **NOT ESTABLISHED** (see scope caveat). The
  newest snapshot predates the commit by one day.

**Verdict: CODE BUG.** `CLAUDE.md:54` is accurate about the seed. But `CLAUDE.md:84` lists the
₹50k anchoring as an E0 bug to fix, and the fix that landed cannot fire on any ledger that has
ever traded — which is every real one. This is a correctness gap, not a documentation gap.

---

## 3. Live order path — has a real order ever been placed?

**Claims:**
- `CLAUDE.md:164-166`: "**Live execution has never placed a real order.** The whole live path
  (`LiveBroker`, `KiteOrderClient`, `LiveExecutionKite`) is exercised only against a mock order
  client in tests. The first real order is its own first real-world test."
- `docs/product-overview.md:42-43`: "its live order-placement path has never executed a real order".
- `docs/product-overview.md:334-336` and `:365-367`: same, in "Requires validation" and
  "Known Limitations".

### Reality: **false.** 50 real orders and 34 booked live trades.

`mode` is stamped by the broker class, so `mode='live'` is dispositive:
`backend/app/engine/broker.py:27` `MODE = "paper"` on `PaperBroker`, and
`backend/app/engine/live_broker.py:36` `MODE = "live"   # every fill this broker books is a
REAL trade`. It is written to every `Trade` at `broker.py:81,141,187,298,352,406`.

Query against `paper-trader/vps-snapshots/paper_trader-offload-20260723-094218.db`:

```
sqlite> SELECT mode, segment, COUNT(*) n, MIN(entry_time), MAX(exit_time)
   ...> FROM trades GROUP BY mode, segment;
live | equity_intraday | 33 | 2026-07-13 09:30:10.182947 | 2026-07-22 15:07:15.526417
live | options         |  1 | 2026-07-20 09:30:13.451745 | 2026-07-20 09:39:42.724026
```

**Every trade in the production database is `mode='live'`. There are zero paper rows.**
Date range **2026-07-13 → 2026-07-22**.

The order journal carries real Zerodha order IDs (19-digit exchange IDs, which the paper path
does not generate):

```
sqlite> SELECT COUNT(*), COUNT(order_id) FROM order_journal;   -- 58 rows, 50 with a broker id
sqlite> SELECT status, resolution, kind, intent, COUNT(*) FROM order_journal
   ...> GROUP BY status,resolution,kind,intent;
TERMINAL | FILLED       | equity  | ENTRY | 33
TERMINAL | FILLED       | equity  | EXIT  | 16
TERMINAL | NEVER_PLACED | equity  | ENTRY |  8
TERMINAL | FILLED       | options | ENTRY |  1
sqlite> SELECT order_id, tradingsymbol, side, filled_qty, avg_price, placed_at
   ...> FROM order_journal ORDER BY id LIMIT 3;
2076517013647302657 | SUZLON | SELL | 940 | 53.12    | 2026-07-13 09:30:10.289012
2076549247112617984 | SUZLON | BUY  | 940 | 53.076.. | 2026-07-13 11:38:15.551910
2077253096622301184 | LT     | SELL |  10 | 3837.4   | 2026-07-15 10:15:06.241181
```

Corroborating, from the older snapshot (`vps-snapshots/2026-07-15/pt-snap-20260715.db`):
9 live `equity_intraday` trades, 17 order-journal rows, 14 with broker IDs — so the first
real order dates to **2026-07-13 09:30 IST**, and the count grew between snapshots.

Config confirms live is armed at the file level: `backend/.env:50-51`
`PT_EXECUTION=live` and `PT_LIVE_ACK=I_UNDERSTAND_REAL_MONEY`.

Internal consistency check (independent of `mode`): realized P&L sums to the ledger.

```
sqlite> SELECT segment, COUNT(*), ROUND(SUM(net_pnl),2), SUM(win) FROM trades GROUP BY segment;
equity_intraday | 33 | 417.40 | 13
options         |  1 | 326.72 |  1
-- 417.40 + 326.72 = 744.12 == capital_state.realized_pnl (744.120000000006)
```

**Verdict: DOC BUG, severe (4 locations).** This is the most consequential drift found. Both
documents lead with "never fired a live order" as a headline safety and maturity claim —
`product-overview.md` builds its "Production readiness = 3" score (`:494`) and two Known
Limitations (`:365`) on it, and `CLAUDE.md:164-166` presents it as a fact an agent should rely
on when touching execution code. The system has been trading real money for **at least 10
calendar days** across **34 positions**.

---

## 4. Test counts

**Claim — `CLAUDE.md:111`:** `.venv/bin/python -m pytest   # full suite (~67 files, all offline/mock)`.

### Reality

File counts (`find`, excluding `__pycache__`):

| Location | Test files |
|---|---|
| `backend/tests/` (top level) | 133 |
| `backend/tests/` (recursive, incl. `tests/journal/`) | **141** |
| `backend/research_tests/` | **24** |
| **Total** | **165** |

Collected test counts (`pytest --collect-only -q`, summed per file):

| Suite | Files | Tests collected |
|---|---|---|
| `backend/tests` | 141 | **933** |
| `backend/research_tests` | 24 | **167** |
| **Total** | **165** | **1,100** |

Run results — `.venv/bin/python -m pytest <suite> -q -p no:randomly`, both suites run
sequentially in one shell so they could not clobber each other's SQLite files:

| Suite | Passed | Failed | Errors | Skipped | Exit code |
|---|---|---|---|---|---|
| `backend/tests` | **933** | 0 | 0 | 0 | **0** |
| `backend/research_tests` | **167** | 0 | 0 | 0 | **0** |

**Both suites are fully green.** Passed counts equal the collected counts exactly, so nothing
was silently deselected.

Note on how those numbers were read: `pytest.ini` already sets `addopts = -q`, so passing
`-q` again produced `-qq`, which **suppresses the "N passed" summary line**. The counts above
were derived by counting outcome characters in the progress output
(`sed -n 's/ *\[ *[0-9]*%\]$//p' | tr -cd '.'` etc.), and corroborated by the process exit
code of `0` for each suite. The only warning emitted was an unrelated
`StarletteDeprecationWarning` from `fastapi/testclient.py`.

Note also that `backend/pytest.ini` sets `testpaths = tests`, so the bare
`pytest` command documented at `CLAUDE.md:111` **does not run `research_tests` at all** —
24 files / 167 tests are excluded from "the full suite".

**Verdict: DOC BUG.** "~67 files" understates the suite by more than half. The claim
"all offline/mock" was not contradicted by the run.

---

## 5. Options stop / target and the ratcheting trail

**Claims:** `CLAUDE.md:198` — "−35%/+60% premium stop/target with a ratcheting trailing stop".
`docs/product-overview.md:131` — "Fixed premium stop and target on every entry (default −35% /
+60%)". Also `:239` and `:251`, where the "−35% / +60% asymmetry" is load-bearing for the whole
edge argument.

### Reality: the stop is **−30%**, not −35%. The target and the ratchet claims are correct.

- `backend/app/core/config.py:50` — `stop_loss_pct: float = 0.30`
- `backend/app/core/config.py:51` — `target_pct: float = 0.60`
- Applied at entry, options path only: `backend/app/engine/broker.py:63-64` resolves
  `p.get("stop_loss_pct", self.settings.stop_loss_pct)`; `:76-77`
  `stop_price = premium * (1 - stop_loss_pct)`, `target_price = premium * (1 + target_pct)`.
  Nothing is hardcoded on this path.
- Both are live-overridable: `backend/app/core/runtime_config.py:22-25` (allowlist),
  `:67-76` (bounds — `stop_loss_pct` clamped 0.001–0.99). The production `runtime_config`
  table contains **no** `stop_loss_pct` or `target_pct` row (§Appendix A), so production runs
  the **−30% / +60%** defaults.
- Provenance of the drift: commit `922be06` *"feat(exits): aggressive trailing stop (trail 10%
  behind, no ceiling) + 30% initial stop"*. `git merge-base --is-ancestor 922be06 origin/main`
  → **0**; `... HEAD` → **0**. It is on **both** branches, so `−35%` is stale everywhere,
  including on `main`. `0.35` survives only in prose: `config.py:8` (module docstring),
  `CLAUDE.md:197`, `docs/product-overview.md:131`, and
  `docs/2026-07-28-platform-status-report.md:101`.
- Percentage basis confirmed: every options stop/target/trail number is a fraction of
  `entry_premium` (`broker.py:76-77`, `exit_monitor.py:64,97`). There is no absolute-rupee
  exit knob on the options lane.

### The ratchet — claim is accurate

`backend/app/engine/exit_monitor.py:38-65` `trailing_stop`, called each risk-loop tick via
`runner.py:567` → `_apply_trailing` (`runner.py:567-593`):

- Arms once high-water premium clears entry by one `trail_trigger_pct` step
  (`config.py:93-96`: `trail_enabled=True`, `trigger=0.10`, `first_step_lock=0.025`,
  `step_lock=0.10`); `steps = int(profit_frac / trigger_pct)`, returns unchanged if
  `steps <= 0` (`exit_monitor.py:59-62`).
- Lock schedule (`:63`): step 1 locks +2.5%; step N≥2 locks `(N-1) * 10%` — one full step
  behind high-water. New stop `= entry * (1 + lock_frac)` (`:64`).
- **Never loosens:** `max(current_stop, ...)` at `:65`, and `runner.py:585` only applies when
  `new_stop > pos.stop_price`. Confirms "ratcheting … never loosens"
  (`product-overview.md:132-133`).
- The exchange-side stop is re-priced when the trail moves (`runner.py:589-590`
  `broker.update_stop_protection`), with `ensure_stop_protection` self-healing each tick
  (`runner.py:569`).
- Exit priority: STOP_LOSS → TARGET (skipped if `pos.no_take_profit`) → RATCHET_STOP →
  STRATEGY_EXIT (`exit_monitor.py:17-34`).

**One undocumented branch:** if `pos.entry_atr is not None` the premium trail is **skipped
entirely** (`runner.py:576`) and the position is governed by an ATR ratchet on the
*underlying spot* (`runner.py:402-425` → `backend/app/backtest/ratchet.py:29-70`: initial stop
`fill − 1.25·ATR`, trail arms at 1.75R trailing 3.0·ATR, MFE floor at 1.25R locking 35% of peak).
This only applies to `expanding_z_v4` positions (`strategy/registry/expanding_z_v4.py:78-84`);
the default `trend_impulse_v3` declares no `risk_model` (`registry/__init__.py:18`), so the
default options position does use the premium trail. Neither document mentions the
two-mode split.

**Verdict: DOC BUG (stop number, 4 locations).** Material because
`product-overview.md:251` rests its central edge argument on the specific
"−35% / +60% asymmetry"; the real asymmetry is more favourable (−30% / +60%), so the
document *understates* the platform while still being wrong.

---

## 6. Deploy reality

### Does `scripts/deploy.sh` exist? **No.**

There is no `scripts/` directory at the repo root and **no `.sh` file anywhere under
`paper-trader/`**. The only shell scripts in the repository belong to the unrelated
`stock-market-analyst/` sub-project (`scripts/setup.sh`, `start.sh`, `test.sh`), plus stale
duplicates under `.claude/worktrees/`.

Also absent: no `Makefile` (only `node_modules/delayed-stream/Makefile`), no `justfile`, **no
`.github/` directory at all** (zero CI workflows), and no `*.service`/`*.timer` unit files
checked in. `backend/scripts/` holds only Python utilities (`dryrun.py`,
`reconcile_ledger.py`, `refresh_earnings.py`, `research_run.py`, `backtest_smoke.py`,
`fetch_mis_blocklist.py`) — none deploy.

`backend/app/core/deploy_bridge.py:1` is a false positive: "deploy" there means promoting a
research strategy to a watchlist, not shipping code.

### Is there an `--exclude .env` guard anywhere? **No — prose only.**

Every `--exclude` and `rsync` occurrence in the repository is inside a `.md` or `.html`
file. **There is not one executable rsync invocation anywhere.** Full inventory:

| Location | Nature |
|---|---|
| `CLAUDE.md:249` | The canonical rule, as prose: "Never rsync to the VPS without `--exclude '.env' --exclude 'node_modules' --exclude '*.db'`." |
| `docs/superpowers/plans/2026-07-10-vps-deployment.md:308` | The **only** full rsync command line in the repo, in a fenced bash block. Flags: `rsync -av --exclude .venv --exclude node_modules --exclude '*.db*' --exclude 'access_token.json'`. **Does not exclude `.env`.** |
| `docs/ROADMAP.md:173` | Unchecked TODO: "rsync with `--exclude .env --exclude '*.db'`" |
| `docs/ROADMAP.md:387` | **Falsely asserts as settled fact** that ".env, DBs, and access_token.json are excluded by the rsync filter" — no such filter exists |
| `docs/STATUS.html:205`, `:364` | "Add `--exclude .env` to the deploy rsync. This has taken the VPS down twice." |
| `docs/2026-07-28-platform-status-report.md:171` | Correctly: "The `--exclude .env` guard is still a documented TODO." |

**Verdict: the rule exists only as prose, and is unenforceable as written** because no deploy
automation exists to enforce it in. Two further problems:

1. `docs/ROADMAP.md:387` **contradicts** `docs/STATUS.html:205` and
   `docs/2026-07-28-platform-status-report.md:171`. One says the filter is in place; the others
   say it is an open TODO that has caused two outages. The TODO version is correct.
2. The single concrete recipe an operator would copy
   (`plans/2026-07-10-vps-deployment.md:308`) **omits `.env`** — copy-pasting the documented
   command reproduces the documented outage exactly.

### How deploys actually happen

All prose, no enforced code. `CLAUDE.md:43-46`: SSH is
`ssh -i ~/.ssh/paper-trader-vps root@64.227.191.162`; "Deploy = rsync whole tree from Mac +
`systemctl restart paper-trader` (VPS has NO git)." Restated at `docs/STATUS.html:355`.
Restart/verify step at `plans/2026-07-10-vps-deployment.md:466`. Post-deploy verification is
also prose only (`CLAUDE.md:250-251`, refined at `docs/STATUS.html:364` — "the post-deploy
check must curl `/`, not just health" — and `docs/ROADMAP.md:174`). `CLAUDE.md:251` notes macOS
ships an old rsync, so flags like `--info=progress2` must be avoided.

**Verdict: DOC BUG** at `docs/ROADMAP.md:387` (asserts a guard that does not exist).
Everything else here is an accurate description of an unautomated, unguarded process.

---

## 7. Other claims contradicted by the code

### 7.1 "localhost" / "single local process" — the bot runs on a VPS
`CLAUDE.md:50` — "A single-user, **localhost** autonomous options paper-trading platform".
`docs/product-overview.md:379-381` — "It runs as **one local process against a local
database** for one account." `docs/product-overview.md:384-386` repeats it.
Contradicted **inside the same file** by `CLAUDE.md:43-46`: the engine runs on a DigitalOcean
droplet at `64.227.191.162`, deployed by rsync, supervised by systemd
(`systemctl restart paper-trader`). **DOC BUG.**

### 7.2 "No real capital ever moves by default"
`CLAUDE.md:53-54` — "**No real capital ever moves by default**". `backend/.env:50-51` sets
`PT_EXECUTION=live` **and** `PT_LIVE_ACK=I_UNDERSTAND_REAL_MONEY`, which is exactly the pair
`engine/broker_factory.py` requires to select `LiveBroker` (per `CLAUDE.md:152-154`). The
committed default configuration is live. Combined with §3, this is **DOC BUG** — the sentence
is true of the code's *fallback* posture and false of the shipped configuration.

### 7.3 "options paper-trading platform" — the book is 97% equity
`CLAUDE.md:50` and `docs/product-overview.md:1,9` frame the product as an **options** platform.
Of 34 real trades, **33 are `equity_intraday`** and 1 is options (§3 query). `CLAUDE.md:59-67`
does document the 2026-07 pivot to equity/index, so the two halves of `CLAUDE.md` disagree with
each other, and `product-overview.md` — which has no equivalent note — misrepresents what the
system actually trades. **DOC BUG.**

### 7.4 Persisted order journal is described as "deferred" but is built and in use
`docs/product-overview.md:493` docks the Maintainability score for "some deferred designs
(**e.g. a persisted order journal**)". The table exists at
`backend/app/db/models.py:610` (`__tablename__ = "order_journal"`), and production holds
**58 rows** including 50 real broker order IDs (§3). `docs/audit-deferred-design.md:10-19`
describes it as H13/deferred — also stale. **DOC BUG.**

### 7.5 "One risk toggle ships disabled" — it was enabled 11 days ago
`docs/product-overview.md:396` — "A maximum-open-drawdown guard exists but is **shipped off**".
`backend/app/core/config.py:148` — `max_open_drawdown: float = 2_500.0`, with the inline
comment "(0 = off; H15, **enabled 2026-07-17**)". Enabled by commit `0778f4d` (2026-07-17)
*"fix(engine): enable max_open_drawdown (H15) at a ₹2,500 default"*. Live at
`runner.py:1299,1345` and `risk_controls.py:183`. The Risk-management score justification at
`:490` also docks for "one guard shipped disabled". **DOC BUG.**

### 7.6 Documented defaults ≠ production behaviour (runtime_config overrides)
Neither document mentions that production overrides several documented defaults. From the
2026-07-23 snapshot (§Appendix A):

| Knob | Documented default | Production value |
|---|---|---|
| `intraday_max_positions` | 3 (`config.py:186`; "hard cap of 3", `CLAUDE.md:200`) | **4** |
| `intraday_entry_cutoff_minutes` | 25.0 (`config.py:208`) | **60** |
| `max_daily_loss` | 5000.0 (`config.py:146`) | **2000** |

`CLAUDE.md:183-187` does explain the layering mechanism, but any reader taking the stated
numbers as production truth would be wrong on all three. **DOC BUG** (documentation of
production state, not of the mechanism).

### 7.7 Stale line references in the ARM-gate note
`CLAUDE.md:161-163` — "gate is in `process_entries` at **`runner.py:506,532`**".
`process_entries` is defined at `runner.py:750`; the arm checks are at `runner.py:885, 911,
979, 1039`. The *substance* (ARM gates entries only, not exits) is correct and confirmed.
**DOC BUG** (stale citations only).

### 7.8 Incomplete key-tables list
`CLAUDE.md:216-219` lists the "key tables" but omits six that exist in
`backend/app/db/models.py`: `watchlists` (`:313`), `watchlist_membership` (`:331`),
`strategy_lifecycle` (`:343`), `generated_strategies` (`:369`), `order_journal` (`:610`),
`earnings_events` (`:633`). All six are present in the production DB. **DOC BUG.**

### 7.9 "the hardened code is not yet deployed" — unverifiable as written
`docs/product-overview.md:340-342`, `:491`, `:494`, `:523` all assert that current code is
committed but not deployed. The statement has no stable referent — it was written 2026-07-22
(commit `144dfdd`) and the branch has moved 20+ commits since. What *is* establishable:
`origin/main` is `d9903cd` (2026-07-14) and HEAD is **101 commits ahead**. Whether the running
process matches either is **NOT ESTABLISHED** by this audit. **Flagged as an unmaintainable
claim** rather than a bug — a doc should not assert deployment state it cannot pin to a commit.

### 7.10 `pytest` as documented does not run the research suite
`CLAUDE.md:109-111` presents `pytest` as running "the full suite". `backend/pytest.ini`
sets `testpaths = tests`, excluding `research_tests/` (24 files / 167 tests). **DOC BUG.**

### 7.11 Options "1 lot" — confirmed accurate
`CLAUDE.md:53` and `docs/product-overview.md:126` claim a fixed one-lot options position.
Confirmed: `backend/app/engine/broker.py:56` `qty, premium = q.lot_size, q.ltp`, and
`:212` `qty = pick.chosen.lot_size`. **No bug** — recorded because it was checked.

---

## Could not be established

- **Whether the running VPS process carries this branch.** No artifact in the repo reports the
  deployed commit, and the audit did not contact the VPS. Affects §2 ("has it shipped"),
  §7.9, and any claim about production code state. The newest production snapshot
  (2026-07-23 09:41) predates 16 commits on this branch.
- **Whether production `runtime_config` has changed since 2026-07-23.** §7.6 and the
  "no leverage/stop override in production" statements in §1 and §5 are true **as of the
  snapshot**, not necessarily as of today.
- **Whether the single live options trade (2026-07-20) used the −30% stop.** The trade exited
  in 9 minutes with `+₹326.72`; reconstructing which exit rule fired would need the
  `exit_reason` cross-checked against the then-current params, which the snapshot does not
  pin down.
- **Charge-rate accuracy** (`CLAUDE.md:239`, `docs/product-overview.md:388`). Both flag the
  rates as needing verification against contract notes; this audit did not verify them.
- **Claims about edge / statistical validity** (`product-overview.md` §6, §7, §11). These are
  judgements, not code facts, and were out of scope — though §3 invalidates the specific
  premises they rest on.

---

## Appendix A — production `runtime_config` (2026-07-23 snapshot)

```
sqlite> SELECT key, value, updated_at FROM runtime_config;
intraday_enabled               True   2026-07-11 00:21:11.928240
intraday_max_positions         4      2026-07-16 05:19:32.096024
max_daily_loss                 2000   2026-07-11 00:24:25.828256
intraday_block_weekday         0      2026-07-21 11:12:10.254665
intraday_override_date         ''     2026-07-16 05:17:13.890430
intraday_entry_cutoff_minutes  60     2026-07-22 01:58:29.870360
```

Six rows only. No `intraday_leverage`, `stop_loss_pct`, or `target_pct` override — those run
at their `config.py` defaults in production.

## Appendix B — commands used

```bash
# DBs were copied to a scratch dir before querying; originals never opened for write.
cp vps-snapshots/2026-07-15/pt-snap-20260715.db* "$SCRATCH/"
cp paper-trader/vps-snapshots/paper_trader-offload-20260723-094218.db "$SCRATCH/"
sqlite3 "$SCRATCH/paper_trader-offload-20260723-094218.db" "<queries quoted inline above>"

# Ancestry
git merge-base --is-ancestor 8abca46 HEAD;        echo $?   # 0
git merge-base --is-ancestor 8abca46 origin/main; echo $?   # 1
git merge-base --is-ancestor 922be06 origin/main; echo $?   # 0
git rev-list --count origin/main..HEAD                      # 101

# Tests
cd backend
./.venv/bin/python -m pytest tests          --collect-only -q
./.venv/bin/python -m pytest research_tests --collect-only -q
./.venv/bin/python -m pytest tests          -q -p no:randomly
./.venv/bin/python -m pytest research_tests -q -p no:randomly
```

---

## Recommended follow-ups (not performed — this was read-only)

1. **Correct the "never placed a real order" claim** in `CLAUDE.md:164-166` and
   `docs/product-overview.md:42-43, 334-336, 365-367`, and re-derive the
   Production-readiness/Risk scores that depend on it. Highest priority: an agent reading
   `CLAUDE.md` before touching execution code is being told real money is not at stake.
2. **Fix the equity anchor (real code fix).** `_maybe_auto_reanchor`'s "zero trades" guard
   means it can never fire on a live ledger; the production curve overstates equity by
   roughly 2×. Either relax the guard or make the manual reconcile path part of go-live.
3. **Update the stop to −30%** in `CLAUDE.md:197`, `docs/product-overview.md:131, 239, 251`,
   `config.py:8`, `docs/2026-07-28-platform-status-report.md:101`.
4. **Rewrite `CLAUDE.md:200`** — real-margin sizing (7k/10k targets, 2.5k dust floor), no
   leverage cap, concurrency 3 by default / 4 in production.
5. **Delete the false assertion at `docs/ROADMAP.md:387`** and add `--exclude .env` to the
   recipe at `plans/2026-07-10-vps-deployment.md:308`. Better: write the deploy script that
   `CLAUDE.md:249` already assumes exists, so the guard is mechanical.
6. **Remove the hardcoded `2.5` fallbacks** at `runner.py:689,1032` and `broker.py:114`.
7. **Fix "localhost"/"local process"** framing in `CLAUDE.md:50` and
   `docs/product-overview.md:379-381`.
8. **Update the test-count and `pytest`-scope claims** at `CLAUDE.md:109-111`.
9. **Drop the "deferred order journal"** dock at `docs/product-overview.md:493` and the
   "guard ships disabled" claims at `:396, :490`.
10. **Stop asserting deployment state in prose** (§7.9) — pin it to a commit or a
    health-endpoint check instead.
