# Operations

*Relocated from `CLAUDE.md` on 2026-07-28. Deploy, VPS access, go-live procedure, and open
operational items. Architecture lives in [`architecture.md`](architecture.md); the agenda lives
in [`ROADMAP.md`](ROADMAP.md).*

## Where the bot actually runs

Not localhost. The engine runs 24/7 on a **DigitalOcean droplet, `64.227.191.162`**, under
systemd (`systemctl restart paper-trader`), with the UI reachable tailnet-only at
`https://paper-trader.taile25969.ts.net`. The Mac is a development machine — keep the local
engine **off**; only one live engine may exist.

## SSH

```bash
ssh -i ~/.ssh/paper-trader-vps root@64.227.191.162
```

Use the public IP and that key. There is no ssh config entry, and tailnet port 22 is
Tailscale-SSH, which hangs non-interactively.

## Deploy

**`scripts/deploy.sh` is the only sanctioned deploy path.** Do not hand-roll an rsync — that
is what caused both production outages. The VPS has no git; the script rsyncs the tree and
restarts the service, with the guards that used to be prose baked in.

```bash
scripts/deploy.sh                       # the normal case
scripts/deploy.sh --dry-run             # show what would transfer, change nothing
scripts/deploy.sh --force-market-hours  # deploy inside the trading session
scripts/deploy.sh --prune               # also delete remote-only files (asks first)
```

Run it from `paper-trader/`. It lives inside the deployed tree on purpose: `REPO_ROOT`
resolves to `paper-trader/`, which is exactly what `/opt/paper-trader` mirrors. **Moving it
to the outer git root would sync the wrong tree** (the parent repo has
`stock-market-analyst/`, `data/`, and screenshots in it) and land the real tree at
`/opt/paper-trader/paper-trader/`.

### What it refuses to do

| Guard | Behaviour |
|---|---|
| Excludes intact | Aborts unless `.env`, `frontend/dist` **and** `*.db.*` are in the exclusion list |
| Market hours | Refuses Mon–Fri 09:00–15:45 IST (buffered around the real 09:15–15:30). Override: `--force-market-hours` |
| Dirty tree | Refuses on any modified **or untracked** file. No override — see below |
| Tests | Runs `tests` **and** `research_tests` plus `dryrun.py 700`; aborts on failure |
| Frontend build | Builds the SPA locally; aborts if `npm` or `node_modules` is missing, or if the build yields no `dist/index.html` |
| Deletion | Never deletes. `--prune` shows the exact list and requires you to type `delete` |

There is deliberately no `--allow-dirty`. Every trade row is stamped with the deploying
commit (`trades.build_sha`); a `-dirty` SHA is untraceable by construction, which defeats
the column. Untracked files count as dirty because rsync ships them even though they are
not in the SHA.

### Rolling back

Before anything overwrites the remote `backend/VERSION`, the script reads it, prints it, and
stashes it in `~/.paper-trader/deploy-history/` (override with `PT_DEPLOY_HISTORY`):

- `previous-VERSION` — the build this deploy replaced
- `<utc-timestamp>-replaced-by-<sha>.VERSION` — append-only history

This exists because **the VPS has no git** and `VERSION` is written per-host: the instant the
new file lands, the identity of what was running is gone. Rolling back then means an
investigation instead of:

```bash
git checkout <sha> && scripts/deploy.sh
```

The script prints that exact command. If the captured SHA is not reachable from your local
repo it says so loudly rather than offering a command that will fail. If the remote `VERSION`
cannot be read at all, the deploy **aborts** — shipping without a rollback point is the thing
this is meant to prevent. A remote with no `VERSION` yet (first deploy through this script)
is not an error, but is called out: that one build is unrecoverable.

Stored outside `REPO_ROOT` deliberately — anything under it would be rsynced into production
and would trip the dirty-tree guard on the next run.

### What it verifies after restarting

1. `backend/.env` is still present and non-empty — **checked before the restart**, so a
   clobber aborts the deploy instead of taking the site down.
2. `frontend/dist/index.html` still exists (see the `dist/` note below).
3. `/api/health` returns 200 **and its readiness verdict is not `starting`**. Since
   2026-08-01 this is a real readiness probe, not a liveness stub: it answers **503**
   when the DB is unreachable, the engine loops are stopped, or the **fast risk lane**
   has gone stale. The deploy loop keeps polling through a 503 or a `starting` verdict
   and reports the last one it saw if it times out — so "the app came up but its risk
   loop died at startup" now fails the deploy instead of passing on the first 200.
4. `GET /` returns 200. Health alone is **still** not sufficient — the SPA mount is
   invisible from the health probe, and a green `/api/health` coexisted with 404s on
   every page during the `.env` outage. Both checks stay.
5. `/api/health` reports the SHA that was just shipped, proving the restart actually took.
   A process that could not read its `VERSION` reports `"unknown"`, which fails this
   comparison rather than passing silently.

A `degraded` verdict does **not** fail the deploy — it is logged as a note. Degraded means
something non-fatal is wrong (an expired Kite token; the signal lane quiet during market
hours). Only the risk lane, the DB, and a stopped engine are fatal, because only they mean
open positions are unmanaged.

### Reading the probe by hand

```bash
curl -s localhost:8090/api/health | python3 -m json.tool
```
`status` is one of `ok` / `starting` / `degraded` / `unready`; `failed_checks` names what is
fatally wrong and `checks[].detail` says why in a sentence. `loops.risk.age_seconds` is the
number to look at first — if it is climbing, stops are not firing. Note the lane ages are
measured on a **monotonic wall clock**, not the provider clock, so they mean the same thing
under the mock provider as in production.

### Why the exclusion list looks the way it does

Verified against a live `find /opt/paper-trader` on 2026-07-28. If you put a new remote-only
artifact on the box, add it to `EXCLUDES` in the same change.

- **`.env`, `.env.*`, `access_token.json`, `*.db`, `*.db-*`, `*.db.*`** — production owns these
  and they are not in git. Overwriting `.env` drops `PT_SERVE_FRONTEND`/`PT_FRONTEND_DIST`, the
  SPA mount is skipped, and every `GET /` 404s while the process and `/api/health` stay green.
  **Both DB globs are required.** `*.db-*` catches only the hyphen suffixes (`-wal`, `-shm`);
  `paper_trader.db.lock` and `paper_trader.db.predeploy-*` have a **dot**, so they need
  `*.db.*`. This doc previously claimed `*.db-*` covered them — it does not, verified with
  `rsync --dry-run`. The consequence was not cosmetic: the live `.db.lock` appeared in
  `--prune`'s delete list, and unlinking that path while a backend holds the `flock` lets the
  next boot create a fresh inode and acquire a second lock, defeating the C7 single-instance
  guard.
- **`frontend/dist`** — the SPA is **built on the Mac** by `deploy.sh` (`npm run build`) and
  shipped by a **separate, targeted rsync** into `$VPS_PATH/frontend/dist/`. It is *still* in
  `EXCLUDES` on purpose: `--delete` honours `--exclude`, so the exclusion is what keeps
  `--prune` from deleting the live SPA, and that protection must not depend on the second
  transfer having worked. It is gitignored, so building does not dirty the tree.
  **Do not build on the VPS.** The droplet is 1 GB and has OOM'd twice with the engine
  running; a Vite build there competes with a process holding real positions.
- **`backups/`, `backup.sh`, `*.sql`, `*.log`** — the nightly backup set (~600 MB), the cron
  script that produces it, and the pre-operation ledger dumps. None are in git.
- **`VERSION`** — generated per-host by the script itself, never copied from the Mac.

### Mechanics worth knowing

- **macOS ships openrsync** ("rsync version 2.6.9 compatible"), which is stricter than GNU
  rsync: it rejects long options when combined with `-a`. `rsync -a --exclude .env` fails
  outright. The script uses `-rlptD` instead, which also avoids the second outage — `-a`
  implies `-o -g`, and as root that stamps the Mac's uid `501:staff` onto
  `/opt/paper-trader`, after which the `deploy` user cannot create files. Everything keeps
  working until a WAL has to be recreated, so it is a latent engine-killer with no symptom.
  Do not "simplify" `-rlptD` back to `-a`, and do not add modern flags like
  `--info=progress2`.
- The engine is **DISARMED on every process start**. Re-arm from the cockpit after a deploy.
- **Verify code-vs-production, not just code-vs-docs.** A week of planning ran on a status doc
  claiming Workstream B and E0/E1 were undeployed when they had been on the box for days,
  because nobody thought to ask the box. Checksum the files (`md5 -r` local vs `md5sum` remote),
  grep the remote for a symbol unique to the fix, and find a log line only the new code can
  emit — on-disk is not the same as loaded. Never date a deploy from remote mtimes: the sync
  preserves source mtimes, so VPS timestamps are the Mac's edit times, identical to the second.

## Daily routine ("run the bot")

Open `https://paper-trader.taile25969.ts.net` → **Connect Kite** (the access token expires
~06:00 IST daily; headless auto-login violates Kite ToS) → **ARM**. The token is stored in
`backend/access_token.json` (`{date, access_token}`) and the order client reads it live via
`token_source`, so a re-login flows through without a backend restart.

## Going live (checklist)

*Historical note: this checklist was written before the platform went live. It first ran on
2026-07-13; the live path has since placed 50 real orders. Read
[`architecture.md`](architecture.md) § Safety model first. Keep this as the procedure for
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

Carried forward from the [2026-07-23 memory-leak post-mortem](incidents/2026-07-23-memory-leak.md);
all three are tracked as work items in [`ROADMAP.md`](ROADMAP.md), Workstream F.

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
