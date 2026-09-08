Reference: [section index](../operations.md). Read with its scope; this is not a new assignment.

## Daily routine ("run the bot")

Open `https://paper-trader.taile25969.ts.net` → **Connect Kite** (the access token expires
~06:00 IST daily; headless auto-login violates Kite ToS) → **ARM**. The token is stored in
`backend/access_token.json` (`{date, access_token}`) and the order client reads it live via
`token_source`, so a re-login flows through without a backend restart.

## Going live (checklist)

*Historical note: this checklist was written before the platform went live. It first ran on
2026-07-13; the live path has since placed 50 real orders. Read
[`engineering/reference/engine-internals.md`](../engineering/reference/engine-internals.md) § Safety model first. Keep this as the procedure for
re-enabling live execution after it has been turned off.*

1. **Whitelist the static IP** in the Kite developer console (order routes reject otherwise).
   Owner-only.
2. **Re-auth Kite** that morning via the **Connect Kite** button.
3. **Clean the book** — the live ledger must hold only positions the real account holds. The
   risk loop exits positions regardless of ARM state, so a phantom row becomes a real order.
   `capital_state` and `positions` carry over across restarts in non-mock mode.
4. **Set `PT_EXECUTION=live`** in `backend/.env` (`PT_LIVE_ACK=I_UNDERSTAND_REAL_MONEY` +
   `PT_PROVIDER=kite` must already be set) and restart the backend. Logs print
   `🔴 LIVE EXECUTION ENABLED` when armed.
5. **ARM** from the cockpit (disarmed on every start). KILL disarms + squares off everything.

## Snapshots

A DB snapshot from the 2026-07-23 outage is offloaded at `paper-trader/vps-snapshots/`; an
older one is at `vps-snapshots/2026-07-15/`. These are the only artifacts in the repo that
report production state, and the newest is from **2026-07-23 09:41** — it does not reflect the
currently-running process.

**Do not assert deployment state in prose.** No artifact in this repo records the deployed
commit. If a document needs to claim what is running, pin it to a commit hash or a
health-endpoint check taken at a stated time.

## Open operational items

Carried forward from the [2026-07-23 memory-leak post-mortem](../incidents/2026-07-23-memory-leak.md);
all three are tracked as work items in [`ROADMAP.md`](../strategy-os-v1-v2-v3/V0-V1-V1.5-V2-V3-V4-V5-V6-SCOPE-DECISION-MATRIX.md), Workstream F.

1. **Droplet headroom — OWNER ACTION.** The 1GB DO droplet is small; a resize to 2GB has been
   recommended since 2026-07-23 and has not been done. Requires the DO console.
2. **DB bloat — decision not made.** `paper_trader.db` is ~45MB and grows ~5MB/day from
   unbounded append-only `option_data` (~154k), `signal_events` (~86k), and `equity_snapshots`
   (~72k). Options on the table: retention/pruning, splitting telemetry into an archive DB, or
   moving the time-series off SQLite. The owner wants a rethink rather than a patch.
3. **DB session hygiene — minor, unscheduled.** Context-manage `_upsert_state` (`runner.py`) and
   the broker's long-lived session; add `pool_pre_ping`; lower `pool_timeout`.
4. **VPS pending OS reboot** (5 ESM security updates) — owner action, market-closed window.

## Nightly research cron — where it runs, and why not the VPS

**Decision (2026-08-01): the nightly research run does NOT go on the production VPS.**

`research/nightly.py` is a cron one-shot (`python -m research.nightly`). The original design
note said "VPS at ~19:00 IST". That is now the wrong answer, and the reason is measured
rather than cautious:

- The droplet is **1 GB and has OOM'd twice** (2026-07-23). The resize to 2 GB is off the
  table (no budget) — which is why DB retention was built instead.
- A **Vite build on that box can take live positions down with it**, which is why
  `deploy.sh` builds the SPA on the Mac. A nightly research sweep is far heavier than a Vite
  build: `optimize()` runs `n_folds × n_candidates` backtests, and since 2026-08-01 it also
  computes the PBO performance matrix, which is another `n_blocks × n_candidates` replays.
- The live engine's risk lane must beat every second. Anything that can starve it is a
  real-money risk, and research has no deadline that justifies that trade.

**So: run it on the Mac (or any box that is not the trading box).** `PT_RESEARCH_ENABLED`
stays `0` on the VPS. The research plane is isolated by design — own DB, own config, no
capital-moving imports — so running it elsewhere costs nothing architecturally.

```bash
# Mac, offline and deterministic (no Kite, no network):
PT_PROVIDER=mock PT_RESEARCH_ENABLED=1 \
PT_RESEARCH_DB_PATH=~/research/research.db \
PT_RESEARCH_REPORT_DIR=~/research/reports \
PT_RESEARCH_WATCHLIST_SNAPSHOT=~/research/watchlist.json \
  .venv/bin/python -m research.nightly
```

**Feed it the watchlist snapshot.** With no snapshot the run treats every instrument as
research-eligible and prints a WARNING saying so. That fallback is safe in the *permissive*
direction — "nothing is committed" and "I could not read what is committed" look identical
downstream, and only one of them is true. Export the snapshot
(`app.core.watchlists.write_research_snapshot`) so the plane genuinely cannot develop
strategies on instruments that are already earning.

**Shadow mode means shadow mode.** The nightly writes `research.db` and a markdown report
per run. It queues `PromotionCandidate` rows with `status="pending"` and deploys nothing —
promotion to the live engine remains a human action.
