# WS-06 — Deployment & Operations

**Status:** active
**Owner surface:** `scripts/deploy.sh`, `backend/app/core/version.py`, `backend/app/engine/readiness.py` (the one file carved out of WS-02's `app/engine/`), `backend/VERSION` (generated), the `/api/health` route contract, `docs/operations.md`, `docs/incidents/`
**Last verified:** 2026-08-03 · commit `cdbe686`

> This workstream owns the act of moving code from the Mac onto the one machine that trades
> real money, and the act of finding out what is on that machine afterwards. The bot does not
> run on localhost: it runs 24/7 on a DigitalOcean droplet in Bangalore (`64.227.191.162`)
> under systemd, with a tailnet-only UI. The VPS has no git, so "what is deployed" is not a
> question git can answer — it is answered by a build stamp the deploy script writes and the
> running process reports. Two production outages came from a human hand-rolling an rsync;
> everything here exists to make that impossible to repeat.

---

## 1. Vision

A deploy is one command that either refuses with a reason or completes with proof. Proof means:
the tests and the ledger invariant ran before anything moved, the guards that protect
production-owned files were checked mechanically rather than remembered, the SPA was built on
a machine that is not holding positions, the previous build's identity was captured so a
rollback is `git checkout <sha> && scripts/deploy.sh`, and the process that came up reported
the SHA that was just shipped through a probe that is *able to say no*.

And after it: deployment state is never inferred. `curl /api/health`, compare the commit, done.
No prose in any document is evidence of what is running.

## 2. Scope

**In scope.**

- `scripts/deploy.sh` — the only sanctioned deploy path, and every guard in it.
- The VPS itself: systemd unit `paper-trader`, SSH access, the exclusion list that describes
  what production owns, droplet capacity.
- Build provenance: `backend/VERSION` (generated, gitignored), `app/core/version.py`, and the
  `build_sha` stamp that lands on every `trades` row.
- `/api/health` as a **readiness probe**: `app/engine/readiness.py` and its verdict contract.
- The morning routine ("run the bot"): Connect Kite, ARM.
- Incident response and post-mortems (`docs/incidents/`).

**Out of scope.**

- What the engine *does* once running — entries, sizing, exits, order routing: **WS-02
  (Execution)**. This workstream ships it and proves it came up; it does not decide it.
- The database schema, migrations, sessions, retention, `runtime_config` semantics:
  **WS-07 (Infrastructure & Persistence)**. WS-06 protects the DB files from the rsync; WS-07
  owns what is inside them.
- The research plane and where its nightly cron runs: **WS-03 (Research)**. The decision that
  it does *not* run on the production droplet is recorded in `docs/operations.md` and is an
  operational consequence of the 1 GB constraint owned here.
- The SPA's content and design: **WS-08 (Cockpit UI)**. WS-06 owns only the fact that it is
  built on the Mac and that `GET /` is a separate post-deploy check.
- The Component IR and Strategy OS: **WS-01**.

## 3. Interfaces

**Exports**

| Export | Guarantee |
|---|---|
| `scripts/deploy.sh` | The only sanctioned path to production. Refuses rather than half-deploys. Never deletes on the remote unless `--prune` is passed and confirmed by typing `delete`. |
| `GET /api/health` | Returns `200` with `status ∈ {ok, starting, degraded}` when the process is fit to manage money, `503` (`status: unready`) when it is not. Body always includes `build.commit`, `loops.{risk,signal}`, `checks[]` (passing checks included), `failed_checks`, `degraded_checks`. |
| `app/core/version.py:get_build_sha()` | Never `None`. Returns the commit, or the literal `"unknown"` when `VERSION` is missing/unparseable. `NULL` in `trades.build_sha` means something different (see §7). |
| `app/core/version.py:get_build_info()` | Same shape always: `commit`, `branch`, `deployed_at`, `deployed_by`. `commit` uses the same `unknown` sentinel as the ledger stamp, so `/api/health` and `trades.build_sha` cannot disagree. |
| `app/engine/readiness.py:evaluate(...)` | Pure. No DB, no network, no clock. Caller measures, this decides. |
| `app/engine/readiness.py:Thresholds` | Budgets are static `Settings` (`health_risk_stale_seconds` 90 / `health_signal_stale_seconds` 600 / `health_startup_grace_seconds` 45), deliberately **not** `runtime_config`-overridable, so no DB row can silence a safety probe. |

**Consumes**

| Consumed | From | Why |
|---|---|---|
| `EngineRunner` lane heartbeats (`_beat_wall`) | WS-02 | Lane ages must be monotonic wall-clock, not `provider.now()` — under the mock, provider time jumps a candle per tick and reports a healthy dev engine as stale. |
| DB reachability + `FeedQuality` report | WS-07 | Two of the probe's checks. DB is fatal; feed anomalies are degraded-only. |
| `pytest tests research_tests` + `scripts/dryrun.py 700` | WS-02 / WS-07 | Deploy gate. Both suites named explicitly — `pytest.ini` sets `testpaths=tests`, so a bare `pytest` silently skips `research_tests/`. |
| `npm run build` → `frontend/dist/` | WS-08 | Built on the Mac, shipped by a separate targeted rsync. |

**Depends on:** WS-02 (heartbeats, the suites that gate a deploy), WS-07 (DB reachability check, feed quality), WS-08 (SPA build)
**Blocked by:** owner actions — VPS OS reboot and the 1 GB → 2 GB resize (§8). Also blocked, for the *next* production deploy, by WS-02's eight-phase architecture migration awaiting owner acknowledgement (§8).
**Currently blocking:** WS-02 and WS-01 — anything they build is local until a deploy is authorised. Nothing on branch `feat/exec-completeness` is on the box.

## 4. Completed

- **`deploy.sh` makes the rsync guards mechanical — `c3e1ac0`**, re-verified 2026-08-01 by
  reading the script rather than trusting the roadmap line. Every guard the item asked for is
  present: `--exclude '.env'` (`:42`), `access_token.json` (`:44`), **both** DB globs
  `*.db` / `*.db-*` / `*.db.*` (`:45-47`), `--no-owner --no-group` inside `RSYNC_FLAGS`
  (`:317`), and the post-deploy `curl /api/health` plus a **separate** `curl /` (`:578-586`).
  Guard 0 additionally checks `EXCLUDES` is non-empty, has an even element count, and is
  pairwise aligned (`--exclude` at even indices, non-empty pattern at odd), because an odd
  count means a pattern lost its flag and rsync would ship the live `.env` while printing an
  empty prune list.
- **`/api/health` is a real readiness probe — DONE + DEPLOYED 2026-08-01, TDD.** It reports DB
  reachability, both lanes' heartbeat age, provider auth, feed quality and armed state, and
  returns **503** when the DB is unreachable, the engine is stopped, or the fast risk lane is
  stale. Verdict logic pure in `app/engine/readiness.py` (22 unit tests); wiring in
  `tests/test_health_endpoint.py` (10 tests). Two findings that must not be re-litigated:
  **(a)** the signal lane is reported but **never fatal** — it legitimately stops beating
  overnight (`run_signal_loop` takes the `any_open`-false branch and never reaches `_beat_now`)
  and `deploy.sh` refuses to run during market hours, so a fatal signal lane would 503 on every
  legitimate deploy; **(b)** lane ages are measured on the runner's parallel monotonic beat.
  `deploy.sh` now waits out a `starting` verdict instead of exiting on the first 200 — a
  process whose risk loop died at startup previously passed the deploy check.
- **Build provenance deployed — `4e9f125` (2026-08-01).** Measured, not claimed:
  ```
  $ curl -s localhost:8090/api/health
  {"ok":true,"build":{"commit":"4e9f125","branch":"feat/exec-completeness",
   "deployed_at":"2026-08-01T06:59:50Z","deployed_by":"priyanshusaraf@…"},
   "status":"ok","loops":{"risk":{"age_seconds":0.41,"state":"ok"},
   "signal":{"age_seconds":null,"state":"idle"}},"markets_open":false}
  ```
- **Rollback capture.** Before anything overwrites the remote `backend/VERSION`, the script
  reads it, prints it, and stashes it under `~/.paper-trader/deploy-history/`
  (`PT_DEPLOY_HISTORY` overrides): `previous-VERSION` plus an append-only
  `<utc-timestamp>-replaced-by-<sha>.VERSION`. Stored **outside** `REPO_ROOT` deliberately —
  anything under it would be rsynced into production and trip the dirty-tree guard next run.
  If the remote `VERSION` cannot be read at all the deploy **aborts**: shipping without a
  rollback point is the thing this prevents.
- **Remote-import proof before restart.** `pip install` succeeding is not the same claim as
  the app being importable; the script asserts
  `PT_DISABLE_DOTENV=1 .venv/bin/python -c 'import alembic, app.db.migrate'` on the box and
  refuses to restart if it fails — leaving the running engine untouched.
- **Removed the copy-pasteable rsync** at `docs/superpowers/plans/2026-07-10-vps-deployment.md`
  that omitted `--exclude .env`; it now points at `scripts/deploy.sh` (2026-07-28).
- **Corrected the week-long false claim (2026-07-28).** `CLAUDE.md` asserted Workstream B and
  E0/E1 were undeployed. They had been on the box for days. Proven by `md5` of `runner.py`,
  `risk_controls.py`, `charges.py`, `broker.py`, `equity_entry.py`, `analytics.py` against the
  VPS. That error drove a week of decisions and is the origin of the rule in §6.

## 5. Active roadmap

- [ ] **Observe the 503 path in production.** The readiness probe's healthy path is confirmed
      live; the unready path is proven in-process only. Deliberately stalling the risk lane on
      a real-money box is not worth doing on purpose — so treat the **next genuine incident as
      the test** and check the probe went red. Until then §4's claim is "unready is unit-tested,
      not production-observed".
- [ ] **Confirm `provider_feed` on a live session.** As of the 2026-08-01 deploy it is `{}`,
      but markets were shut — that is "the scan has not run", not "the feed is clean". Needs a
      week of live sessions. Check `/api/health` `provider_feed` and grep the journal for
      `FEED_QUALITY`. (Mechanism is WS-07's; the measurement is an operational one.)
- [ ] **Deploy the eight-phase architecture migration** once the owner acknowledges it
      (`cc53bba`, and the phases after it). It is committed, verified and undeployed; it touches
      sizing, exits and order routing, so green tests do not authorise it. See §8.
- [ ] **VPS OS reboot** — 5 ESM security updates, market-closed window, owner action.
- [ ] **Droplet resize 1 GB → 2 GB** — owner action, DO console. Note the resize is currently
      *off the table* for budget reasons, which is what forced retention (WS-07) instead.
      Keep the item so the tradeoff stays visible.

## 6. Acceptance criteria

A change in this workstream is done when:

```bash
scripts/deploy.sh --dry-run          # from paper-trader/, shows the transfer, changes nothing
scripts/deploy.sh                    # runs both suites + dryrun.py 700, builds the SPA, ships
```

and, after it:

```bash
curl -s localhost:8090/api/health | python3 -m json.tool   # on the box
curl -sS -o /dev/null -w '%{http_code}' http://localhost:8090/   # must be 200
```

- `build.commit` equals the SHA that was shipped. `"unknown"` **fails** this comparison rather
  than passing silently.
- `status` is `ok` or `degraded`. `degraded` does not fail a deploy — it means an expired Kite
  token or a quiet signal lane, neither of which leaves money unmanaged. `starting` is waited
  out, not accepted.
- `GET /` returns 200. This is a **separate** check and stays separate: a broken SPA mount is
  invisible from `/api/health`, and a green health endpoint coexisted with 404s on every page
  throughout the `.env` outage.
- If a guard was touched, prove it **can go red**. An empty result and a passing result look
  identical from the outside.

**Rules that are not negotiable:**

1. **Deploys go through `scripts/deploy.sh`. Never bare-rsync.** A bare rsync has already
   clobbered the production `.env` — dropping `PT_SERVE_FRONTEND`/`PT_FRONTEND_DIST`, skipping
   the SPA mount, 404ing every `GET /` while the process and `/api/health` stayed green. A
   second outage came from `rsync -a` as root: `-a` implies `-o -g`, which stamped the Mac's
   uid `501:staff` onto `/opt/paper-trader`, after which the `deploy` user could not create
   files. Everything kept working until a WAL had to be recreated — a latent engine-killer with
   no symptom. The script uses `-rlptD --omit-dir-times --no-owner --no-group -v`. Do not
   "simplify" it back to `-a`; macOS ships openrsync, which also rejects long options combined
   with `-a`.
2. **It refuses during market hours** (Mon–Fri 09:00–15:45 IST, buffered around the real
   09:15–15:30). Override: `--force-market-hours`.
3. **It refuses on a dirty tree** — modified *or untracked*. There is deliberately **no**
   dirty-tree override: a `-dirty` SHA in `trades.build_sha` is untraceable by construction,
   which defeats the column. Untracked files count because rsync ships them even though they
   are not in the SHA.
4. **The SPA is built locally, never on the VPS.** 1 GB droplet, OOM'd twice with the engine
   running; a Vite build there competes with a process holding real positions.
5. **Deployment state is answerable in one command** — `curl /api/health`, compare the commit.
   **Never assert deployment state from prose**, in this file or any other; that is exactly how
   the 2026-07 error persisted for a week. And **do not date a deploy from remote mtimes**: the
   sync uses `-t`, so VPS timestamps are the *Mac's* edit times, identical to the second.
   Checksum/symbol grepping is the fallback only for a box that predates provenance.
6. **Run it from `paper-trader/`.** `REPO_ROOT` resolves there on purpose, which is exactly what
   `/opt/paper-trader` mirrors. Moving the script to the outer git root would sync the wrong
   tree and land the real one at `/opt/paper-trader/paper-trader/`.

## 7. Known technical debt

- **The reported commit does not describe the running parameters.** `runtime_config` overrides
  in the DB shadow code defaults, so a deployed commit can be running materially different
  numbers than its source implies. Ten overrides currently differ. Cost: any reasoning from
  `config.py` about live behaviour is wrong. Mitigated in the UI (an override differing from
  the shipped default is flagged amber) but not in the health payload. Owned jointly with WS-07.
- **`build_sha` has three distinguishable values and the distinction is load-bearing:** a SHA
  (identified build), `'unknown'` (a live process that could not read its `VERSION` — i.e.
  something deployed outside `deploy.sh`, worth chasing), and `NULL` (row predates the column,
  booked before 2026-07-28, genuinely unattributable). Never collapse the last two. The ORM
  cannot write a NULL — passing `build_sha=None` still stamps `'unknown'` — so NULLs only ever
  come from the migration. Trigger to revisit: any tooling that groups by `build_sha`.
- **`EXCLUDES` is verified against a `find /opt/paper-trader` taken 2026-07-28.** If a new
  remote-only artifact lands on the box it must be added to `EXCLUDES` in the same change, or
  `--prune` will offer to delete it. Both DB globs are required: `*.db-*` catches only hyphen
  suffixes (`-wal`, `-shm`); `paper_trader.db.lock` and `paper_trader.db.predeploy-*` have a
  **dot**. The consequence is not cosmetic — unlinking the live `.db.lock` while a backend holds
  the `flock` lets the next boot create a fresh inode and acquire a second lock, defeating the
  single-instance guard.
- **The engine is DISARMED on every process start.** Re-arm from the cockpit after every deploy.
  This is correct behaviour, but it is a manual step with no reminder and no alarm.
- **`vps-snapshots/` is the only artifact in the repo reporting production state**, and the
  newest is from 2026-07-23 09:41. It does not reflect the running process and must never be
  read as if it does.
- **No CI.** The suites gate a deploy, not a commit. A branch can accumulate red commits between
  deploys and nothing says so until `deploy.sh` runs.

## 8. Blockers

1. **VPS OS reboot** — 5 ESM security updates pending. Owner action; needs a market-closed
   window.
2. **Droplet resize 1 GB → 2 GB** — owner action, DO console. Recommended since 2026-07-23,
   still not done; currently declined for budget, which is why WS-07 built retention instead.
   The 2026-07-23 OOM was caused by two memory leaks (both fixed and deployed) but 1 GB leaves
   no headroom.
3. **The eight-phase architecture migration is committed, verified, and undeployed, pending
   owner acknowledgement.** The item belongs to **WS-02 (Execution)** — it touches sizing,
   exits and order routing — but it blocks *here*, because it sits between the current branch
   and the next production deploy. Green tests do not authorise it; the live-money rule does.
   Same standing applies to adopting the IR runtime in a live path (**WS-01**, RFC 0001
   Appendix C(d)).
4. **Nothing on `feat/exec-completeness` is deployed.** As of 2026-08-03 the branch is 77
   commits ahead of `main` and not pushed. The VPS build was not measured this session — the
   only answer is `curl localhost:8090/api/health`, never a doc.

## 9. Future work

- **Automate the post-deploy ARM reminder** (or a probe check that flags "deployed and still
  disarmed during market hours"). Trigger: the first session lost to a forgotten ARM.
- **A staging box.** Trigger: the first change that genuinely cannot be validated by
  `dryrun.py` + replay mode and would otherwise be tested in production.
- **CI on push.** Trigger: a second person, or a red commit reaching `deploy.sh` and costing a
  session.
- **Structured deploy log on the box** (append-only, machine-readable) so incident
  reconstruction does not depend on `deploy-history/` on one Mac. Trigger: the next incident
  where "when did this land" costs more than five minutes.

---

## Rules for this document

- It is the **only** thing an implementation agent should need to read for this workstream,
  besides `CLAUDE.md`, `docs/operations.md` and its declared dependencies.
- Anything in §3 is a contract. Changing an export requires updating every workstream that
  lists it under Consumes, in the same commit.
- Do not restate another workstream's content. Link to it.
- Tick a box only with verified evidence — the command and its output — in the same commit as
  the work.
