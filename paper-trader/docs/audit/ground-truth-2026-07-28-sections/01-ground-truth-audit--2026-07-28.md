Reference: [section index](../ground-truth-2026-07-28.md). Read with its scope; this is not a new assignment.

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
