Reference: [section index](../ground-truth-2026-07-28.md). Read with its scope; this is not a new assignment.

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
| `docs/reports/STATUS.html:205`, `:364` | "Add `--exclude .env` to the deploy rsync. This has taken the VPS down twice." |
| `docs/reports/2026-07-28-platform-status-report.md:171` | Correctly: "The `--exclude .env` guard is still a documented TODO." |

**Verdict: the rule exists only as prose, and is unenforceable as written** because no deploy
automation exists to enforce it in. Two further problems:

1. `docs/ROADMAP.md:387` **contradicts** `docs/reports/STATUS.html:205` and
   `docs/reports/2026-07-28-platform-status-report.md:171`. One says the filter is in place; the others
   say it is an open TODO that has caused two outages. The TODO version is correct.
2. The single concrete recipe an operator would copy
   (`plans/2026-07-10-vps-deployment.md:308`) **omits `.env`** — copy-pasting the documented
   command reproduces the documented outage exactly.

### How deploys actually happen

All prose, no enforced code. `CLAUDE.md:43-46`: SSH is
`ssh -i ~/.ssh/paper-trader-vps root@64.227.191.162`; "Deploy = rsync whole tree from Mac +
`systemctl restart paper-trader` (VPS has NO git)." Restated at `docs/reports/STATUS.html:355`.
Restart/verify step at `plans/2026-07-10-vps-deployment.md:466`. Post-deploy verification is
also prose only (`CLAUDE.md:250-251`, refined at `docs/reports/STATUS.html:364` — "the post-deploy
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
**58 rows** including 50 real broker order IDs (§3). `docs/reports/audit-deferred-design.md:10-19`
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
