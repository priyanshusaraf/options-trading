# Monday watch-list — first trading day after a large change window

**Written 2026-08-02, before the market opens.** The 2026-08-01/02 session put 60
commits on the box, 19 of them touching money-path files (`runner.py`,
`broker.py`, `models.py`). This is the operational brief for the first session
that runs on them: what could go wrong, what the symptom looks like, and how to
undo it — separate from the roadmap, which records what was *built*.

**Running: `83be178`.** Flags off: `PT_RESEARCH_ENABLED=0`,
`index_futures_enabled=False`, `mtf_enabled=False`.

---

## Roll back first, diagnose second

```bash
cat ~/.paper-trader/deploy-history/previous-VERSION   # the build this replaced
git checkout <sha> && scripts/deploy.sh
```
`deploy.sh` prints that exact command after every deploy. The VPS has no git, so
this history file is the only record of what was running before — do not clear it.

**If anything below looks wrong during market hours, roll back before
investigating.** A 40-minute debugging session on a live book costs more than a
redeploy, and the branch is not going anywhere.

---

## Three things to CHECK (built, deployed, never observed)

All three were built on a closed Saturday market. None has ever produced real
output, so a blank result on Monday is ambiguous until proven otherwise.

**1. Ledger honesty — after Connect Kite**
```bash
curl -s localhost:8090/api/status | python3 -m json.tool | grep -A2 ledger_drift
```
Expect `ledger_drift` to APPEAR and sit near zero. It reads live Kite funds, so
with no valid token the field is simply absent — which is what has been seen
every time so far. Absent after a successful Connect Kite means the re-anchor
did not fire; that is the one to chase.

**2. Feed quality — first real answer**
```bash
curl -s localhost:8090/api/health | python3 -m json.tool | grep -A5 provider_feed
journalctl -u paper-trader | grep FEED_QUALITY
```
Empty now genuinely means a clean feed: the chain is proven end-to-end
(`tests/test_feed_quality_end_to_end.py`), so it is no longer ambiguous between
"clean" and "unwired". Anomalies here are informational — the bars were repaired
before any strategy saw them.

**3. The retuned give-back lock — first live session**
`intraday_profit_lock_threshold` 450 → **150**, `_frac` 0.3 → **0.7** (overrides
cleared 2026-08-01). This is the first change to how the bot takes profit since
the sweep, and it rests on a **22-trade sample**. Expect exits to fire EARLIER
and more often than they used to. That is intended; whether it is *better* is
what the five-session trial measures.

---

## What could go wrong, by likelihood

**Exits firing earlier than expected** — the profit-lock retune above. Working as
designed, not a fault. If it feels wrong, the answer is data from the trial, not
a same-day revert.

**Candle validation changing a signal** — the new Data seam sorts, de-duplicates
and repairs bars before the strategy sees them. It is a proven no-op on clean
data, so this only bites if Kite's feed is genuinely dirty — in which case
`provider_feed` names the instrument. The old behaviour was to trade on the bad
bar.

**The signal frame grew a `volume` column** (2026-08-02, `83be178`). Additive: no
indicator in either plane reads it, every consumer names the fields it wants
rather than reading columns positionally, and the price columns are asserted
byte-identical to before by test. It was added because the research plane's
`volume_surge` block had been reading False on every real frame for want of the
data. **If a live signal differs on Monday, this is not the likely cause — but it
is the newest thing on the money path, so rule it in or out first.** The check is
cheap: `git diff 71a375f..HEAD -- backend/app/market_data/candles.py` is eleven
lines, all of them additive.

**`/api/health` returning 503** — the probe can now say no. It means DB
unreachable, engine loops stopped, or the **risk lane stale >90s** (stops not
firing). Read `failed_checks` and `checks[].detail` — each carries a sentence.
A 503 is real: do not restart blindly, read it first.

**Watchlist writes failing** — `_upsert_state` is now a context manager. A
failed write no longer leaks a connection, and in-memory state no longer
advances past a failed commit, so a toggle that appears not to stick means the
DB write genuinely failed rather than silently diverging.

**Kill switch** — now best-effort: it always disarms, then attempts cancel and
square-off independently. If either fails you get `KILL_PARTIAL` in the log
saying what was left undone. Previously a failed cancel aborted the square-off
silently. **Read the log after pressing it** rather than assuming a clean stop.

---

## What CANNOT have changed

Futures and MTF are behind flags that are `False`, and their entry paths return
before doing anything. No futures or MTF code can execute. `unrealized_pnl` is
byte-identical for options and equity (`FUNDED_SEGMENTS` is `{"mtf"}` and no live
position carries that segment) — asserted by test, not by inspection.

The research plane is dormant (`PT_RESEARCH_ENABLED=0`) and, by design, cannot
place an order even when enabled.
