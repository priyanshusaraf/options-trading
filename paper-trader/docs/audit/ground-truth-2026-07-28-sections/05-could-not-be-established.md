Reference: [section index](../ground-truth-2026-07-28.md). Read with its scope; this is not a new assignment.

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
   `config.py:8`, `docs/reports/2026-07-28-platform-status-report.md:101`.
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
