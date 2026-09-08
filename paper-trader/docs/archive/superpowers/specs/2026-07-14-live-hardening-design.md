# Live hardening — 2026-07-14

Fixes for four owner-reported issues + one latent safety gap, all traced to the
**2026-07-13** live session on the Bangalore VPS (`/opt/paper-trader/backend`,
`paper-trader.service`). Root causes were confirmed against the systemd journal and
the `trades` table — not guessed.

## What the logs actually showed (2026-07-13)

- Box never went down (`uptime` 3d+), process never crashed, auth was valid intraday.
- **09:30** SUZLON SHORT 940 @ 53.12 filled (the account's only completed trade).
- **09:45 / 10:00 / 10:15** SBIN, HEG, NBCC orders **rejected — "Insufficient funds"**.
  HEG sized `margin ₹9,891` but Zerodha demanded **₹20,359** (2.06×); NBCC `₹9,989` →
  **₹20,320** (2.03×). The sizer assumes a fixed **5× MIS leverage**; real MIS margin
  on these names was ~2.5×, so every order needed ~2× the account's free margin.
- **10:15:24 ORDER CIRCUIT BREAKER** — 3 consecutive order failures → engine **DISARMED**.
  That, not downtime, is why "the bot stopped after ~10:30".
- **11:26 SUZLON stop-modify FAILED** — "difference between limit and trigger price …
  beyond the exchange's permissible range Rs. 1.59". The exchange SL-M stayed at the old
  53.65 while the bot's internal stop ratcheted to 53.08. They diverged.
- **11:38** internal stop (53.08) fired on the bounce → exit 53.0768, net **−₹12** (charges).
  The −₹12 exit was a *correct* trailed-to-breakeven stop, not a mispriced fill.
- **`risk_loop_stalled` fired 24×** — every 15 min the options-chain research sweep
  (`option research cache +~650 rows`) blocks the event loop **>30 s**, during which open
  positions are unmanaged (no marking / SL / TP).
- Disk is fine: 26 % of 24 GB, DB 4.5 MB, journald 11.7 MB. `margins() failed` logged
  3,156× (pre-market token-expired spam). Trade *history* persists in `trades`; only the
  in-memory 800-entry live-log ring buffer rolls over.

## Fixes

### A — Size intraday orders to real Zerodha margin (Issues 2 + 4)
Stop assuming leverage. Before an intraday MIS entry, query Kite `order_margins()`
(already in the safe-Kite allowlist) for the real per-share MIS margin, then choose qty so
each trade consumes **₹5–8k of real margin** (₹5k floor, ₹8k target), ≤ available margin,
max 3 concurrent. Paper/mock falls back to a conservative **2.5×** estimate so paper ≈ live.
Config: `intraday_min_margin 7000→5000`, `intraday_max_margin 10000→8000`,
`intraday_purple_margin 10000→8000`, `intraday_leverage 5.0→2.5` (fallback only). Real
margin now governs, so orders can't exceed free margin → no rejection cascade → no
circuit-breaker disarm.

### C — Exchange SL-M tracks the ratchet (Issue 3 divergence)
When trailing the SL-M trigger, clamp it within Zerodha's permissible band relative to LTP.
If a modify is still rejected, **cancel + replace** the resting SL-M rather than leaving a
stale one; if replacement also fails, alert loudly (Telegram + ERROR) and flag the position
as exchange-unprotected. The internal software stop already fires correctly; this keeps the
exchange backstop from silently diverging.

### D — Nifty-50 gap guard (Issue 1)
At the first entry attempt each day, read one Nifty-50 quote (its OHLC gives today's open +
prior close). If `|open − prev_close| / prev_close ≥ gap_guard_pct` (default **0.6 %**),
block **all** new entries until **11:00 IST** (`gap_guard_resume`). Exits/management
unaffected. New config: `gap_guard_enabled`, `gap_guard_pct`, `gap_guard_resume`,
`gap_guard_index` ("NIFTY"). Pure, tested helper `nifty_gap_halt(...)`.

### E — Quiet the spam, make logs durable
- `account_funds()` returns `None` without calling `margins()` when unauthenticated; the
  warning is deduped (log once per state change / N min).
- `deployable_cash()` reuses the 20 s-cached `_account_funds` instead of a fresh
  `margins()` call on every entry attempt.
- Add a size-capped `RotatingFileHandler` so no log line is lost (inspectable on disk);
  bump the live ring buffer `800→5000`. Trade history stays in the DB `trades` table (the
  durable Trade Log).

### F — Decouple the sweep from the risk loop (latent safety gap)
Owner chose to leave the options sweep as-is (freq + data). Change only its concurrency:
run its blocking Kite work **without holding the shared engine lock** (and off the event
loop) so it can no longer starve the risk loop. Same sweep, no more `risk_loop_stalled`,
positions stay managed continuously.

## Testing
Each fix is TDD (failing test first). Gate before commit: full `pytest` suite +
`scripts/dryrun.py` cash-invariant to the paisa. Commit each fix separately on
`feat/research-plane`. **No deploy/push without explicit ask.**

## Out of scope
Options sweep frequency/behavior (owner: leave as-is), the local 1.5 GB dev DB bloat
(dev-only; VPS DB is 4.5 MB), and any change to the live/paper safety gates.
