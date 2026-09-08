Reference: [section index](../ground-truth-2026-07-28.md). Read with its scope; this is not a new assignment.

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
