Reference: [section index](../ground-truth-2026-07-28.md). Read with its scope; this is not a new assignment.

<a id="reality-1"></a>
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
  `docs/reports/2026-07-28-platform-status-report.md:101`.
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
