# Instrument Intelligence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add three segment-aware live-cockpit features — an advisory overtrading "red" flag on the Watchlist, a per-instrument performance drill-down with a time-period selector on the Dashboard, and a bulk "add top N backtest winners" action on the Backtests view.

**Architecture:** Extend existing endpoints (`/api/signals`, `/api/dashboard`, `/api/portfolio/add`) plus two new endpoints (`GET /api/instrument/{key}`, `POST /api/portfolio/add-bulk`). Backend is built test-first with pytest; schema changes use the existing additive idempotent migration in `app/db/session.py::_migrate_schema` (no Alembic). Runner setters mirror the existing `set_priority_flag` pattern (DB upsert + live in-memory dict so the next tick honors the change). Frontend is React + TypeScript, verified with `tsc --noEmit` + `vite build` (no unit-test runner exists).

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2.x (SQLite/WAL), pytest; React 18, TypeScript, Vite, Tailwind, lightweight-charts.

## Global Constraints

- **Backend dir:** `/Users/priyanshusaraf/Desktop/options-trading/paper-trader/backend`. Run tests with `source .venv/bin/activate && python -m pytest <path> -v`.
- **Frontend dir:** `/Users/priyanshusaraf/Desktop/options-trading/paper-trader/frontend`. Verify with `npm run typecheck && npm run build`.
- **Git repo root** is `/Users/priyanshusaraf/Desktop/options-trading` (one level above `paper-trader`); `git add` paths are repo-relative (e.g. `paper-trader/backend/...`).
- **IST time:** candle/trade/signal timestamps are **naive IST wall-clock**. `market_hours.now_ist()` returns a **tz-aware** datetime — strip tz (`.replace(tzinfo=None)`) before comparing against `Trade.exit_time` / `SignalEvent.time`. Never use `pd.Timestamp().timestamp()`. (See `[[timestamp-ist-convention]]`.)
- **Default strategy key** is `trend_impulse_v3`; V4 is registered as `expanding_z_v4`.
- **Advisory only:** the overtrading flag must NOT change engine behavior (no auto-block, no auto-flag).
- **Back-compat:** every new function param is optional with a default that reproduces today's behavior; legacy trades with NULL `segment`/`strategy_key` normalize to `options`/`trend_impulse_v3` (existing `_seg`/`_strat` helpers in `analytics.py`).
- **Commit message trailer** (every commit):
  ```
  Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01A9kHe6kQTYhPBmw93VFpUe
  ```
- Each commit's `git add` lists only that task's files. Commit subjects follow the repo style: `feat(<area>): …` / `test(<area>): …`.

---

## Phase 1 — Overtrading red flag (advisory)

### Task 1: Per-instrument signal counts (analytics)

**Files:**
- Modify: `paper-trader/backend/app/engine/analytics.py`
- Test: `paper-trader/backend/tests/test_signal_counts.py` (create)

**Interfaces:**
- Produces: `analytics.signal_counts(s: Session, now: datetime, rolling_days: int = 7) -> dict[str, {"today": int, "rolling": int}]`. Keyed only by instruments that fired ≥1 signal within the rolling window; callers default missing keys to zeros. `now` is naive IST.

- [ ] **Step 1: Write the failing test**

Create `paper-trader/backend/tests/test_signal_counts.py`:
```python
"""signal_counts: per-instrument entry-signal tallies (today + rolling window)."""
import datetime as dt

from app.db.models import SignalEvent
from app.db.session import SessionLocal, init_db
from app.engine import analytics


def test_signal_counts_today_and_rolling():
    init_db(reset=True)
    now = dt.datetime(2026, 6, 26, 14, 0)   # naive IST
    with SessionLocal() as s:
        for t in (dt.datetime(2026, 6, 26, 9, 30),   # today
                  dt.datetime(2026, 6, 26, 11, 0),   # today
                  dt.datetime(2026, 6, 23, 10, 0),   # 3 days ago (in 7d window)
                  dt.datetime(2026, 6, 16, 10, 0)):  # 10 days ago (outside 7d)
            s.add(SignalEvent(time=t, instrument_key="GOLDM", signal="LONG_ENTRY"))
        s.commit()
        c = analytics.signal_counts(s, now, rolling_days=7)
    assert c["GOLDM"]["today"] == 2
    assert c["GOLDM"]["rolling"] == 3        # the 10-day-old event is excluded
    assert "SILVERM" not in c                 # no events -> absent (caller defaults to 0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tests/test_signal_counts.py -v`
Expected: FAIL with `AttributeError: module 'app.engine.analytics' has no attribute 'signal_counts'`

- [ ] **Step 3: Implement `signal_counts`**

In `analytics.py`, add `import datetime as dt` near the top if not present, add `SignalEvent` to the `from app.db.models import ...` line, and append:
```python
def signal_counts(s: Session, now: dt.datetime, rolling_days: int = 7) -> dict[str, dict]:
    """Per-instrument entry-signal tallies: `today` (since IST start-of-day) and
    `rolling` (last `rolling_days`). `now` must be naive IST wall-clock so it
    compares correctly against SignalEvent.time. Only instruments that fired in
    the rolling window appear; callers default the rest to zero."""
    if now.tzinfo is not None:
        now = now.replace(tzinfo=None)
    start_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_roll = now - dt.timedelta(days=rolling_days)
    out: dict[str, dict] = {}
    for ev in s.scalars(select(SignalEvent).where(SignalEvent.time >= start_roll)):
        d = out.setdefault(ev.instrument_key, {"today": 0, "rolling": 0})
        d["rolling"] += 1
        if ev.time >= start_today:
            d["today"] += 1
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tests/test_signal_counts.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add paper-trader/backend/app/engine/analytics.py paper-trader/backend/tests/test_signal_counts.py
git commit -m "feat(analytics): per-instrument signal_counts (today + rolling window)"
```

---

### Task 2: `overtrade_flag` model field + migration + runner setter

**Files:**
- Modify: `paper-trader/backend/app/db/models.py` (`InstrumentState`, ~line 34-43)
- Modify: `paper-trader/backend/app/db/session.py` (`_migrate_schema`, `instrument_state` list ~line 101-108)
- Modify: `paper-trader/backend/app/engine/runner.py` (`_load_instr_config` ~line 127, unpack ~line 76, add `set_overtrade_flag`)
- Test: `paper-trader/backend/tests/test_overtrade_flag.py` (create)

**Interfaces:**
- Consumes: `_upsert_state(key)` (existing), `self.overtrade_flags` dict.
- Produces: `InstrumentState.overtrade_flag: bool`; `runner.overtrade_flags: dict[str, bool]`; `runner.set_overtrade_flag(key: str, flag: bool) -> None`; `_load_instr_config` now returns a **4-tuple** `(products, strategies, priority, overtrade)`.

- [ ] **Step 1: Write the failing test**

Create `paper-trader/backend/tests/test_overtrade_flag.py`:
```python
"""overtrade_flag: advisory red flag — set live + persisted, reloaded on restart."""
from app.db.session import init_db
from app.engine.runner import EngineRunner


def _fresh_runner():
    init_db(reset=True)
    return EngineRunner()


def test_set_overtrade_flag_live_and_persisted():
    r = _fresh_runner()
    try:
        r.set_overtrade_flag("GOLDM", True)
        assert r.overtrade_flags.get("GOLDM") is True
    finally:
        r.broker.close()
    # a fresh runner reloads the flag from the DB
    r2 = EngineRunner()
    try:
        assert r2.overtrade_flags.get("GOLDM") is True
        r2.set_overtrade_flag("GOLDM", False)
        assert "GOLDM" not in r2.overtrade_flags
    finally:
        r2.broker.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tests/test_overtrade_flag.py -v`
Expected: FAIL with `AttributeError: 'EngineRunner' object has no attribute 'overtrade_flags'`

- [ ] **Step 3: Add the model field**

In `models.py`, in `InstrumentState` after the `product` line (~line 43) add:
```python
    overtrade_flag: Mapped[bool] = mapped_column(Boolean, default=False)  # "red" overtrading flag (advisory)
```

- [ ] **Step 4: Add the migration**

In `session.py` `_migrate_schema`, in the `"instrument_state"` list (after the `("product", ...)` entry, ~line 107) add:
```python
            ("overtrade_flag", "BOOLEAN DEFAULT 0"),
```

- [ ] **Step 5: Load + set in the runner**

In `runner.py`, change the unpack at ~line 76 from:
```python
        self.products, self.strategy_keys, self.priority_flags = self._load_instr_config()
```
to:
```python
        self.products, self.strategy_keys, self.priority_flags, self.overtrade_flags = self._load_instr_config()
```

In `_load_instr_config` (~line 127), change the signature/return to include overtrade:
```python
    def _load_instr_config(self) -> tuple[dict, dict, dict, dict]:
        """Per-instrument product (options|equity_intraday), assigned strategy, the
        purple priority flag, and the red overtrading flag. Missing/legacy rows
        default to options/v3/not-priority/not-overtraded."""
        products, strategies, priority, overtrade = {}, {}, {}, {}
        with SessionLocal() as s:
            for r in s.scalars(select(InstrumentState)):
                products[r.instrument_key] = r.product or "options"
                if r.strategy_key:
                    strategies[r.instrument_key] = r.strategy_key
                if r.priority_flag:
                    priority[r.instrument_key] = True
                if getattr(r, "overtrade_flag", False):
                    overtrade[r.instrument_key] = True
        return products, strategies, priority, overtrade
```

Add the setter next to `set_priority_flag` (~after line 201):
```python
    def set_overtrade_flag(self, key: str, flag: bool) -> None:
        """Toggle the watchlist 'red' overtrading flag. Advisory only — the engine
        does NOT change behavior based on it."""
        s, r = self._upsert_state(key)
        r.overtrade_flag = bool(flag)
        s.commit(); s.close()
        if flag:
            self.overtrade_flags[key] = True
        else:
            self.overtrade_flags.pop(key, None)
        log.info(f"OVERTRADE {'set' if flag else 'cleared'}", instrument=key)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tests/test_overtrade_flag.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add paper-trader/backend/app/db/models.py paper-trader/backend/app/db/session.py paper-trader/backend/app/engine/runner.py paper-trader/backend/tests/test_overtrade_flag.py
git commit -m "feat(intraday): overtrade_flag on InstrumentState + runner setter (advisory)"
```

---

### Task 3: Overtrading threshold settings

**Files:**
- Modify: `paper-trader/backend/app/core/config.py` (`Settings`, after the intraday block ~line 161)
- Modify: `paper-trader/backend/app/core/runtime_config.py` (`OVERRIDABLE`, `BOUNDS`)
- Test: `paper-trader/backend/tests/test_overtrade_settings.py` (create)

**Interfaces:**
- Produces settings keys (overridable + bounded): `overtrade_today_threshold` (int, default 5), `overtrade_rolling_threshold` (int, default 15), `overtrade_rolling_days` (int, default 7). Reach the engine via `effective()` (only OVERRIDABLE keys surface).

- [ ] **Step 1: Write the failing test**

Create `paper-trader/backend/tests/test_overtrade_settings.py`:
```python
"""Overtrading thresholds are overridable + bounded and reach effective()."""
from fastapi.testclient import TestClient

from app.core import runtime_config
from app.db.session import init_db
from app.engine.runner import EngineRunner
from app.main import app


def _client():
    prev = getattr(app.state, "runner", None)
    if prev is not None:
        try:
            prev.broker.close()
        except Exception:
            pass
    init_db(reset=True)
    app.state.runner = EngineRunner()
    return TestClient(app)


def test_overtrade_thresholds_overridable_and_bounded():
    c = _client()
    keys = {r["key"] for r in c.get("/api/settings").json()["params"]}
    assert {"overtrade_today_threshold", "overtrade_rolling_threshold",
            "overtrade_rolling_days"} <= keys
    c.post("/api/settings", json={"key": "overtrade_today_threshold", "value": "3"})
    assert runtime_config.effective()["overtrade_today_threshold"] == 3
    bad = c.post("/api/settings", json={"key": "overtrade_rolling_days", "value": "999"}).json()
    assert "error" in bad   # rolling_days capped at 90
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tests/test_overtrade_settings.py -v`
Expected: FAIL (keys not in the settings schema)

- [ ] **Step 3: Add the Settings fields**

In `config.py`, after `intraday_target_pct` (~line 161) add:
```python
    # overtrading guard (advisory red-flag suggestion — no engine effect)
    overtrade_today_threshold: int = 5      # suggest red when an instrument fires >= this many signals today
    overtrade_rolling_threshold: int = 15   # ...or >= this many over the rolling window
    overtrade_rolling_days: int = 7         # rolling window length, in days
```

- [ ] **Step 4: Register overridable + bounds**

In `runtime_config.py`, append to the `OVERRIDABLE` tuple (before the closing `)`):
```python
    # overtrading guard (advisory)
    "overtrade_today_threshold", "overtrade_rolling_threshold", "overtrade_rolling_days",
```
And add to `BOUNDS`:
```python
    "overtrade_today_threshold": (0, 200),       # 0 disables the today arm of the suggestion
    "overtrade_rolling_threshold": (0, 1000),    # 0 disables the rolling arm
    "overtrade_rolling_days": (1, 90),
```

- [ ] **Step 5: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tests/test_overtrade_settings.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add paper-trader/backend/app/core/config.py paper-trader/backend/app/core/runtime_config.py paper-trader/backend/tests/test_overtrade_settings.py
git commit -m "feat(settings): overtrading-guard thresholds (overridable + bounded)"
```

---

### Task 4: `/api/signals` enrichment + overtrade endpoint

**Files:**
- Modify: `paper-trader/backend/app/api/routes.py` (`signals` ~line 328-377; add new POST route after `set_priority` ~line 470)
- Test: `paper-trader/backend/tests/test_overtrade_routes.py` (create)

**Interfaces:**
- Consumes: `analytics.signal_counts`, `runtime_config.effective()`, `runner.overtrade_flags`, `runner.set_overtrade_flag`, `runner.provider.now()`.
- Produces: each `/api/signals` row gains `signals_today: int`, `signals_rolling: int`, `overtrade_flag: bool`, `overtrade_suggested: bool`. New `POST /api/instruments/{key}/overtrade {flag: bool}`.

- [ ] **Step 1: Write the failing test**

Create `paper-trader/backend/tests/test_overtrade_routes.py`:
```python
"""/api/signals carries signal counts + overtrade suggestion; flag toggle endpoint."""
from fastapi.testclient import TestClient

from app.db.models import SignalEvent
from app.db.session import SessionLocal, init_db
from app.engine.runner import EngineRunner
from app.main import app


def _client():
    prev = getattr(app.state, "runner", None)
    if prev is not None:
        try:
            prev.broker.close()
        except Exception:
            pass
    init_db(reset=True)
    r = EngineRunner()
    app.state.runner = r
    return TestClient(app), r


def test_signals_carry_counts_and_suggestion_and_flag():
    c, r = _client()
    c.post("/api/settings", json={"key": "overtrade_today_threshold", "value": "2"})
    now = r.provider.now()
    with SessionLocal() as s:
        for _ in range(3):
            s.add(SignalEvent(time=now, instrument_key="GOLDM", signal="LONG_ENTRY"))
        s.commit()
    rows = {x["key"]: x for x in c.get("/api/signals").json()["instruments"]}
    assert rows["GOLDM"]["signals_today"] >= 3
    assert rows["GOLDM"]["overtrade_suggested"] is True
    assert rows["GOLDM"]["overtrade_flag"] is False
    assert c.post("/api/instruments/GOLDM/overtrade", json={"flag": True}).json()["overtrade_flag"] is True
    rows = {x["key"]: x for x in c.get("/api/signals").json()["instruments"]}
    assert rows["GOLDM"]["overtrade_flag"] is True


def test_overtrade_unknown_instrument_rejected():
    c, _ = _client()
    assert "error" in c.post("/api/instruments/NOPE/overtrade", json={"flag": True}).json()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tests/test_overtrade_routes.py -v`
Expected: FAIL (`KeyError: 'signals_today'` and 404/`overtrade` route missing)

- [ ] **Step 3: Enrich the `signals` route**

In `routes.py` `signals()`, after `now = r.provider.now()` (~line 343) add:
```python
    from app.engine import analytics
    from app.core import runtime_config
    eff = runtime_config.effective()
    today_thr = int(eff.get("overtrade_today_threshold", 5))
    roll_thr = int(eff.get("overtrade_rolling_threshold", 15))
    roll_days = int(eff.get("overtrade_rolling_days", 7))
    with SessionLocal() as _s:
        sig_counts = analytics.signal_counts(_s, now, rolling_days=roll_days)
```
Then inside the `out.append({...})` per-instrument dict, before the closing brace, add:
```python
            "signals_today": sig_counts.get(inst.key, {}).get("today", 0),
            "signals_rolling": sig_counts.get(inst.key, {}).get("rolling", 0),
            "overtrade_flag": r.overtrade_flags.get(inst.key, False),
            "overtrade_suggested": (
                (today_thr > 0 and sig_counts.get(inst.key, {}).get("today", 0) >= today_thr)
                or (roll_thr > 0 and sig_counts.get(inst.key, {}).get("rolling", 0) >= roll_thr)),
```

- [ ] **Step 4: Add the overtrade endpoint**

In `routes.py`, after the `set_priority` route (~line 470) add:
```python
class OvertradeBody(BaseModel):
    flag: bool


@router.post("/api/instruments/{key}/overtrade")
def set_overtrade(key: str, body: OvertradeBody, request: Request):
    if key not in {i.key for i in all_instruments()}:
        return {"error": "unknown instrument"}
    _runner(request).set_overtrade_flag(key, body.flag)
    return {"key": key, "overtrade_flag": body.flag}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tests/test_overtrade_routes.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add paper-trader/backend/app/api/routes.py paper-trader/backend/tests/test_overtrade_routes.py
git commit -m "feat(api): signals carry signal-counts + overtrade suggestion; flag toggle endpoint"
```

---

### Task 5: Watchlist red-flag UI

**Files:**
- Modify: `paper-trader/frontend/src/lib/types.ts` (`SignalRow` ~line 70-81)
- Modify: `paper-trader/frontend/src/lib/api.ts` (add helper after `setPriorityFlag` ~line 23)
- Modify: `paper-trader/frontend/src/views/WatchlistView.tsx` (import, handler near `togglePriority` ~line 117, toggle cell ~line 244-263)
- Modify: `paper-trader/frontend/src/views/SettingsView.tsx` (`META` ~line 46, `GROUPS` ~line 56-67)

**Interfaces:**
- Consumes: `/api/signals` new fields; `POST /api/instruments/{key}/overtrade`.
- Produces: `setOvertradeFlag(key, flag)` api helper; red-dot toggle + count badges in the Watchlist row; an "Overtrading guard" group in Settings.

- [ ] **Step 1: Extend the type**

In `types.ts`, inside `SignalRow` (after `strategy_key?` ~line 80) add:
```typescript
  signals_today?: number
  signals_rolling?: number
  overtrade_flag?: boolean       // red "overtrading" flag (advisory)
  overtrade_suggested?: boolean  // count crossed a threshold -> suggest red
```

- [ ] **Step 2: Add the api helper**

In `api.ts`, after `setPriorityFlag` (~line 23) add:
```typescript
export const setOvertradeFlag = (key: string, flag: boolean) =>
  post(`/api/instruments/${key}/overtrade`, { flag })
```

- [ ] **Step 3: Add the handler + UI**

In `WatchlistView.tsx`:
- Add `setOvertradeFlag` to the api import line (`import { ..., setPriorityFlag, setOvertradeFlag, ... }`).
- After `togglePriority` (~line 117-121) add:
```typescript
  const toggleOvertrade = (r: SignalRow) => {
    const next = !r.overtrade_flag
    patchRow(r.key, { overtrade_flag: next })
    setOvertradeFlag(r.key, next).catch(() => patchRow(r.key, { overtrade_flag: r.overtrade_flag }))
  }
```
- In the priority/product cell, immediately after the `togglePriority` button (after line 250, before the product button) add:
```tsx
                    <button onClick={() => toggleOvertrade(r)}
                      title={r.overtrade_flag
                        ? 'red overtrading flag ON — advisory only; consider removing this name'
                        : (r.overtrade_suggested
                            ? `high signal count (today ${r.signals_today ?? 0} · 7d ${r.signals_rolling ?? 0}) — consider flagging red`
                            : 'flag as red (overtrading)')}
                      className={`text-sm leading-none ${r.overtrade_flag ? 'text-red-400'
                        : r.overtrade_suggested ? 'text-red-400/70 hover:text-red-400 animate-pulse'
                        : 'text-zinc-600 hover:text-red-400'}`}>
                      {r.overtrade_flag ? '🔴' : '○'}
                    </button>
                    <span className={`badge text-[10px] ${r.overtrade_suggested ? 'bg-red-500/20 text-red-300' : 'bg-zinc-700/40 text-muted'}`}
                      title="entry signals: today · last 7 days">
                      {r.signals_today ?? 0}·{r.signals_rolling ?? 0}
                    </span>
```

- [ ] **Step 4: Add the Settings group for the overtrade thresholds**

In `SettingsView.tsx`, add the help text to `META` (~line 46, alongside the other entries):
```typescript
  overtrade_today_threshold: { label: 'Overtrade suggest — today (signals)', help: 'Suggest the red overtrading flag when an instrument fires at least this many entry signals today. 0 disables. Advisory only — never blocks trading.' },
  overtrade_rolling_threshold: { label: 'Overtrade suggest — rolling (signals)', help: 'Suggest red when signals over the rolling window reach this many. 0 disables.' },
  overtrade_rolling_days: { label: 'Overtrade rolling window (days)', help: 'Length of the rolling window for the signal-count suggestion.' },
```
And add a group to the `GROUPS` array (~line 56-67):
```typescript
  ['Overtrading guard', (k) => k.startsWith('overtrade_')],
```

- [ ] **Step 5: Verify typecheck + build**

Run (from `frontend/`): `npm run typecheck && npm run build`
Expected: both succeed, exit 0.

- [ ] **Step 6: Commit**

```bash
git add paper-trader/frontend/src/lib/types.ts paper-trader/frontend/src/lib/api.ts paper-trader/frontend/src/views/WatchlistView.tsx paper-trader/frontend/src/views/SettingsView.tsx
git commit -m "feat(watchlist): red overtrading flag + signal-count badges + Settings group (advisory)"
```

---

## Phase 2 — Per-instrument breakdown + drill-down

### Task 6: Period filter + richer per-instrument stats (analytics)

**Files:**
- Modify: `paper-trader/backend/app/engine/analytics.py`
- Test: `paper-trader/backend/tests/test_analytics_period.py` (create)

**Interfaces:**
- Produces:
  - `_apply(trades, segment, strategy, since=None)` — gains a `since: datetime | None` cutoff (`exit_time >= since`).
  - `_stat_block(trades) -> dict` — full per-group stat block: `trades, wins, win_rate, net, gross, charges, avg_pnl, avg_win, avg_loss, expectancy, avg_holding_minutes, best, worst` (best/worst are net P&L of the best/worst single trade).
  - `since` param added to `summary`, `per_instrument_curves`, `realized_curve`, `recent_trades`, `equity_curve`, `segment_curves`, `strategy_curves`.
  - `instrument_stats(s, key, segment=None, strategy=None, since=None) -> dict` (a `_stat_block` over one instrument).
  - `instrument_trades(s, key, segment=None, strategy=None, since=None, limit=500) -> list[dict]`.

- [ ] **Step 1: Write the failing test**

Create `paper-trader/backend/tests/test_analytics_period.py`:
```python
"""Period (`since`) filtering + richer per-instrument stat block."""
import datetime as dt

from app.db.models import Trade
from app.db.session import SessionLocal, init_db
from app.engine import analytics


def _trade(s, *, key="GOLDM", net, hold=60.0, exit_time):
    s.add(Trade(instrument_key=key, direction="LONG", option_type="CE",
                tradingsymbol=key, exchange="NFO", segment="options",
                strategy_key="trend_impulse_v3", strike=0.0,
                expiry=dt.date(2026, 7, 31), qty=10,
                entry_premium=100.0, entry_cost=1000.0, entry_spot=100.0,
                entry_time=exit_time - dt.timedelta(hours=1),
                exit_premium=100.0 + net / 10, exit_charges=2.0, exit_spot=100.0,
                exit_time=exit_time, exit_reason="TARGET",
                gross_pnl=net + 2, charges_total=2.0, net_pnl=net, return_pct=0.0,
                holding_minutes=hold, win=net > 0))


def test_since_filters_and_stat_block():
    init_db(reset=True)
    now = dt.datetime(2026, 6, 26, 14, 0)
    with SessionLocal() as s:
        _trade(s, net=100.0, hold=60.0, exit_time=now)                       # today
        _trade(s, net=-40.0, hold=30.0, exit_time=now)                       # today
        _trade(s, net=50.0, hold=20.0, exit_time=now - dt.timedelta(days=10))  # old
        s.commit()
        all_summary = analytics.summary(s)
        today = analytics.summary(s, since=now.replace(hour=0, minute=0, second=0, microsecond=0))
    assert all_summary["trades"] == 3
    assert today["trades"] == 2 and today["net_pnl"] == 60.0
    block = today["per_instrument"]["GOLDM"]
    assert block["trades"] == 2
    assert block["net"] == 60.0
    assert block["avg_win"] == 100.0
    assert block["avg_loss"] == -40.0
    assert block["avg_holding_minutes"] == 45.0
    assert block["best"] == 100.0 and block["worst"] == -40.0


def test_instrument_stats_and_trades_helpers():
    init_db(reset=True)
    now = dt.datetime(2026, 6, 26, 14, 0)
    with SessionLocal() as s:
        _trade(s, key="GOLDM", net=100.0, exit_time=now)
        _trade(s, key="SILVERM", net=20.0, exit_time=now)
        s.commit()
        stats = analytics.instrument_stats(s, "GOLDM")
        trades = analytics.instrument_trades(s, "GOLDM")
    assert stats["trades"] == 1 and stats["net"] == 100.0
    assert len(trades) == 1 and trades[0]["instrument_key"] == "GOLDM"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tests/test_analytics_period.py -v`
Expected: FAIL (`summary()` has no `since` kwarg; `instrument_stats` missing)

- [ ] **Step 3: Extend `_apply` and add `_stat_block`**

In `analytics.py`, replace `_apply` with:
```python
def _apply(trades: list[Trade], segment: str | None, strategy: str | None,
           since: "dt.datetime | None" = None) -> list[Trade]:
    if since is not None:
        cut = since.replace(tzinfo=None) if since.tzinfo else since
        trades = [t for t in trades if t.exit_time >= cut]
    if segment:
        trades = [t for t in trades if _seg(t) == segment]
    if strategy:
        trades = [t for t in trades if _strat(t) == strategy]
    return trades
```
Add (near the other helpers):
```python
def _stat_block(trades: list[Trade]) -> dict:
    """Full per-group performance block (used for per-instrument + instrument detail)."""
    n = len(trades)
    wins = [t for t in trades if t.win]
    nw = len(wins)
    nl = n - nw
    net = sum(t.net_pnl for t in trades)
    return {
        "trades": n,
        "wins": nw,
        "win_rate": round(100 * nw / n, 1) if n else 0.0,
        "net": round(net, 2),
        "gross": round(sum(t.gross_pnl for t in trades), 2),
        "charges": round(sum(t.charges_total for t in trades), 2),
        "avg_pnl": round(net / n, 2) if n else 0.0,
        "avg_win": round(sum(t.net_pnl for t in wins) / nw, 2) if nw else 0.0,
        "avg_loss": round(sum(t.net_pnl for t in trades if not t.win) / nl, 2) if nl else 0.0,
        "expectancy": round(net / n, 2) if n else 0.0,
        "avg_holding_minutes": round(sum(t.holding_minutes for t in trades) / n, 1) if n else 0.0,
        "best": round(max((t.net_pnl for t in trades), default=0.0), 2),
        "worst": round(min((t.net_pnl for t in trades), default=0.0), 2),
    }
```

- [ ] **Step 4: Thread `since` through the public functions**

Update these signatures + bodies in `analytics.py`:

`equity_curve` — add `since` and filter snaps:
```python
def equity_curve(s: Session, limit: int = 2000, since: "dt.datetime | None" = None) -> list[dict]:
    snaps = list(s.scalars(select(EquitySnapshot).order_by(EquitySnapshot.time)))
    if since is not None:
        cut = since.replace(tzinfo=None) if since.tzinfo else since
        snaps = [sn for sn in snaps if sn.time >= cut]
    return [sn.to_dict() for sn in snaps[-limit:]]
```
(Keep the existing body shape; only the query/filter line and signature change.)

`per_instrument_curves(s, segment=None, strategy=None, since=None)` — pass `since` into `_apply`.

`realized_curve(s, segment=None, strategy=None, since=None)` — pass `since` into `_apply`.

`segment_curves(s, since=None)` and `strategy_curves(s, segment=None, since=None)` — after loading `trades = list(s.scalars(select(Trade)))`, add:
```python
    if since is not None:
        cut = since.replace(tzinfo=None) if since.tzinfo else since
        trades = [t for t in trades if t.exit_time >= cut]
```

`summary(s, segment=None, strategy=None, since=None)` — change the first line to `_apply(..., since)`, then replace the per-instrument loop/finalize block with a `_stat_block` grouping:
```python
    groups: dict[str, list[Trade]] = {}
    for t in trades:
        groups.setdefault(t.instrument_key, []).append(t)
    per = {k: _stat_block(v) for k, v in groups.items()}
    ranked = sorted(per.items(), key=lambda x: x[1]["net"], reverse=True)
```
(Leave the top-level summary fields — `expectancy`, `avg_win`, `avg_loss`, `gross_pnl`, `charges`, `net_pnl`, `best`, `worst` — exactly as they are. `best`/`worst` at the top level stay instrument *keys*; inside `per_instrument[key]` they are trade P&L values.)

`recent_trades(s, limit=50, mode=None, segment=None, strategy=None, since=None)` — pass `since` into `_apply`.

- [ ] **Step 5: Add the instrument helpers**

Append to `analytics.py`:
```python
def instrument_stats(s: Session, key: str, segment: str | None = None,
                     strategy: str | None = None, since: "dt.datetime | None" = None) -> dict:
    """Full stat block for one instrument (segment/strategy/period aware)."""
    trades = _apply(list(s.scalars(select(Trade).where(Trade.instrument_key == key))),
                    segment, strategy, since)
    return _stat_block(trades)


def instrument_trades(s: Session, key: str, segment: str | None = None,
                      strategy: str | None = None, since: "dt.datetime | None" = None,
                      limit: int = 500) -> list[dict]:
    """That instrument's trades, newest first (segment/strategy/period aware)."""
    q = select(Trade).where(Trade.instrument_key == key).order_by(Trade.exit_time.desc())
    trades = _apply(list(s.scalars(q)), segment, strategy, since)
    return [t.to_dict() for t in trades[:limit]]
```

- [ ] **Step 6: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tests/test_analytics_period.py tests/test_dashboard_segments.py -v`
Expected: PASS (both the new test and the existing Phase-4 segment tests still green — back-compat).

- [ ] **Step 7: Commit**

```bash
git add paper-trader/backend/app/engine/analytics.py paper-trader/backend/tests/test_analytics_period.py
git commit -m "feat(analytics): period (since) filter + richer per-instrument stat block + instrument helpers"
```

---

### Task 7: Dashboard period param + instrument-detail endpoint

**Files:**
- Modify: `paper-trader/backend/app/api/routes.py` (`dashboard` ~line 284-308; add `_period_since` helper + new GET route)
- Test: `paper-trader/backend/tests/test_instrument_detail.py` (create)

**Interfaces:**
- Consumes: the analytics `since`/`instrument_stats`/`instrument_trades` from Task 6; `runner.provider.now()`; `get_instrument`.
- Produces: `_period_since(period, now) -> datetime | None`; `/api/dashboard?period=all|today|7d|30d`; `GET /api/instrument/{key}?segment=&strategy=&period=` → `{key, name, segment, stats, trades, period}`.

- [ ] **Step 1: Write the failing test**

Create `paper-trader/backend/tests/test_instrument_detail.py`:
```python
"""Dashboard period filter + per-instrument detail endpoint."""
import datetime as dt

from app.db.models import Trade
from app.db.session import SessionLocal, init_db
from app.engine.runner import EngineRunner
from app.main import app
from fastapi.testclient import TestClient


def _client():
    prev = getattr(app.state, "runner", None)
    if prev is not None:
        try:
            prev.broker.close()
        except Exception:
            pass
    init_db(reset=True)
    r = EngineRunner()
    app.state.runner = r
    return TestClient(app), r


def _trade(s, *, key, net, hold, exit_time):
    s.add(Trade(instrument_key=key, direction="LONG", option_type="CE",
                tradingsymbol=key, exchange="NFO", segment="options",
                strategy_key="trend_impulse_v3", strike=0.0,
                expiry=dt.date(2026, 7, 31), qty=10,
                entry_premium=100.0, entry_cost=1000.0, entry_spot=100.0,
                entry_time=exit_time - dt.timedelta(hours=1),
                exit_premium=100.0 + net / 10, exit_charges=2.0, exit_spot=100.0,
                exit_time=exit_time, exit_reason="TARGET",
                gross_pnl=net + 2, charges_total=2.0, net_pnl=net, return_pct=0.0,
                holding_minutes=hold, win=net > 0))


def test_dashboard_period_filters_to_today():
    c, r = _client()
    now = r.provider.now()
    if now.tzinfo is not None:
        now = now.replace(tzinfo=None)
    with SessionLocal() as s:
        _trade(s, key="GOLDM", net=100.0, hold=60, exit_time=now)
        _trade(s, key="GOLDM", net=50.0, hold=60, exit_time=now - dt.timedelta(days=10))
        s.commit()
    assert c.get("/api/dashboard").json()["summary"]["trades"] == 2
    today = c.get("/api/dashboard?period=today").json()["summary"]
    assert today["trades"] == 1 and today["net_pnl"] == 100.0


def test_instrument_detail_stats_and_trade_list():
    c, r = _client()
    now = r.provider.now()
    if now.tzinfo is not None:
        now = now.replace(tzinfo=None)
    with SessionLocal() as s:
        _trade(s, key="GOLDM", net=100.0, hold=60, exit_time=now)
        _trade(s, key="GOLDM", net=-40.0, hold=30, exit_time=now)
        _trade(s, key="SILVERM", net=20.0, hold=10, exit_time=now)
        s.commit()
    d = c.get("/api/instrument/GOLDM").json()
    assert d["key"] == "GOLDM"
    assert d["stats"]["trades"] == 2 and d["stats"]["net"] == 60.0
    assert d["stats"]["avg_holding_minutes"] == 45.0
    assert len(d["trades"]) == 2
    assert all(t["instrument_key"] == "GOLDM" for t in d["trades"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tests/test_instrument_detail.py -v`
Expected: FAIL (period ignored → today returns 2; `/api/instrument/GOLDM` 404)

- [ ] **Step 3: Add the `_period_since` helper**

In `routes.py`, near the top of the module (after imports) add (`_dt` alias avoids clashing with any existing `datetime` import; `now` is passed in, so no time helper import is needed):
```python
import datetime as _dt


def _period_since(period: str | None, now):
    """Map a period token to a naive-IST cutoff (exit_time >= cutoff). None = all-time.
    `now` comes from provider.now(); strip tz so it compares to naive exit_time."""
    if not period or period == "all":
        return None
    if getattr(now, "tzinfo", None) is not None:
        now = now.replace(tzinfo=None)
    if period == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "7d":
        return now - _dt.timedelta(days=7)
    if period == "30d":
        return now - _dt.timedelta(days=30)
    return None
```
(If `routes.py` already imports `datetime`/`market_hours`, skip the duplicate import.)

- [ ] **Step 4: Add `period` to the dashboard route**

Replace the `dashboard` function body (~line 284-308) so it computes `since` and threads it through:
```python
@router.get("/api/dashboard")
def dashboard(request: Request, segment: str | None = None, strategy: str | None = None,
              period: str | None = None):
    """Portfolio dashboard. Optional ?segment=, ?strategy=, and ?period=all|today|7d|30d
    slice the summary / curves / trades. The headline `equity_curve` is the global
    mark-to-market series when unfiltered; for a slice it's the realized-P&L curve."""
    seg = segment or None
    strat = strategy or None
    since = _period_since(period, _runner(request).provider.now())
    with SessionLocal() as s:
        equity = (analytics.equity_curve(s, since=since) if not (seg or strat)
                  else analytics.realized_curve(s, seg, strat, since))
        return {
            "capital": analytics.capital_dict(s),
            "summary": analytics.summary(s, seg, strat, since),
            "equity_curve": equity,
            "instrument_curves": analytics.per_instrument_curves(s, seg, strat, since),
            "segment_curves": analytics.segment_curves(s, since),
            "strategy_curves": analytics.strategy_curves(s, seg, since),
            "recent_trades": analytics.recent_trades(s, 50, segment=seg, strategy=strat, since=since),
            "open_positions": [p.to_dict() for p in analytics.open_positions(s)],
            "segment": seg, "strategy": strat, "period": period or "all",
        }
```

- [ ] **Step 5: Add the instrument-detail route**

In `routes.py`, after the dashboard route add:
```python
@router.get("/api/instrument/{key}")
def instrument_detail(key: str, request: Request, segment: str | None = None,
                      strategy: str | None = None, period: str | None = None):
    """Full per-instrument stat block + that instrument's trades, honoring
    ?segment=, ?strategy=, ?period=."""
    inst = get_instrument(key)
    since = _period_since(period, _runner(request).provider.now())
    with SessionLocal() as s:
        stats = analytics.instrument_stats(s, key, segment or None, strategy or None, since)
        trades = analytics.instrument_trades(s, key, segment or None, strategy or None, since)
    return {"key": key, "name": inst.name if inst else key,
            "segment": inst.segment if inst else None,
            "stats": stats, "trades": trades, "period": period or "all"}
```
(`get_instrument` is already imported at the top of `routes.py`.)

- [ ] **Step 6: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tests/test_instrument_detail.py tests/test_dashboard_segments.py -v`
Expected: PASS (new + existing dashboard tests green).

- [ ] **Step 7: Commit**

```bash
git add paper-trader/backend/app/api/routes.py paper-trader/backend/tests/test_instrument_detail.py
git commit -m "feat(api): dashboard ?period= filter + per-instrument detail endpoint"
```

---

### Task 8: Dashboard period selector + instrument-detail modal (frontend)

**Files:**
- Modify: `paper-trader/frontend/src/lib/api.ts` (`getDashboard` ~line 44; add `getInstrumentDetail`)
- Modify: `paper-trader/frontend/src/lib/types.ts` (add `InstrumentDetailDTO`)
- Create: `paper-trader/frontend/src/views/InstrumentDetailModal.tsx`
- Modify: `paper-trader/frontend/src/views/DashboardView.tsx` (period state + selector; per-instrument rows open the modal)

**Interfaces:**
- Consumes: `/api/dashboard?period=`, `GET /api/instrument/{key}`.
- Produces: `getDashboard(segment?, strategy?, period?)`, `getInstrumentDetail(key, segment?, strategy?, period?)`, `<InstrumentDetailModal>`.

- [ ] **Step 1: Extend the api helpers**

In `api.ts`, replace `getDashboard` with:
```typescript
export const getDashboard = (segment?: string, strategy?: string, period?: string) => {
  const q = new URLSearchParams()
  if (segment) q.set('segment', segment)
  if (strategy) q.set('strategy', strategy)
  if (period && period !== 'all') q.set('period', period)
  const qs = q.toString()
  return j(`/api/dashboard${qs ? `?${qs}` : ''}`)
}
export const getInstrumentDetail = (key: string, segment?: string, strategy?: string, period?: string) => {
  const q = new URLSearchParams()
  if (segment) q.set('segment', segment)
  if (strategy) q.set('strategy', strategy)
  if (period && period !== 'all') q.set('period', period)
  const qs = q.toString()
  return j(`/api/instrument/${key}${qs ? `?${qs}` : ''}`)
}
```

- [ ] **Step 2: Add the detail type**

In `types.ts`, after `TradeDTO` add:
```typescript
export interface InstrumentStatBlock {
  trades: number; wins: number; win_rate: number; net: number; gross: number
  charges: number; avg_pnl: number; avg_win: number; avg_loss: number
  expectancy: number; avg_holding_minutes: number; best: number; worst: number
}
export interface InstrumentDetailDTO {
  key: string; name: string; segment: string | null
  stats: InstrumentStatBlock; trades: TradeDTO[]; period: string
}
```

- [ ] **Step 3: Create the modal component**

Create `paper-trader/frontend/src/views/InstrumentDetailModal.tsx`:
```tsx
import { useEffect, useState } from 'react'
import { getInstrumentDetail } from '../lib/api'
import { inr, signedInr, pnlColor, num, dt } from '../lib/format'
import type { InstrumentDetailDTO } from '../lib/types'

export default function InstrumentDetailModal(
  { instrumentKey, segment, strategy, period, onClose }:
  { instrumentKey: string; segment?: string; strategy?: string; period?: string; onClose: () => void }) {
  const [d, setD] = useState<InstrumentDetailDTO | null>(null)
  useEffect(() => {
    getInstrumentDetail(instrumentKey, segment, strategy, period).then(setD).catch(() => setD(null))
  }, [instrumentKey, segment, strategy, period])

  const Stat = ({ label, v, cls = '' }: { label: string; v: string; cls?: string }) => (
    <div className="bg-panel2 rounded p-2">
      <div className="stat-label">{label}</div>
      <div className={`tabular-nums font-semibold ${cls}`}>{v}</div>
    </div>
  )

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="card w-full max-w-4xl p-4 flex flex-col gap-3 max-h-[92vh] overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between shrink-0">
          <span className="text-lg font-semibold text-zinc-100">{d?.name || instrumentKey}</span>
          <button onClick={onClose} className="btn">✕ close</button>
        </div>
        {!d ? <div className="text-muted text-xs py-10 text-center">loading…</div> : (
          <>
            <div className="grid gap-2 shrink-0" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(110px,1fr))' }}>
              <Stat label="Trades" v={String(d.stats.trades)} />
              <Stat label="Win rate" v={`${d.stats.win_rate}%`} />
              <Stat label="Net P&L" v={signedInr(d.stats.net)} cls={pnlColor(d.stats.net)} />
              <Stat label="Gross" v={signedInr(d.stats.gross)} />
              <Stat label="Charges" v={inr(d.stats.charges)} cls="text-down" />
              <Stat label="Avg P&L / trade" v={signedInr(d.stats.avg_pnl)} cls={pnlColor(d.stats.avg_pnl)} />
              <Stat label="Avg win" v={signedInr(d.stats.avg_win)} cls="text-up" />
              <Stat label="Avg loss" v={signedInr(d.stats.avg_loss)} cls="text-down" />
              <Stat label="Best" v={signedInr(d.stats.best)} cls="text-up" />
              <Stat label="Worst" v={signedInr(d.stats.worst)} cls="text-down" />
              <Stat label="Avg hold (min)" v={num(d.stats.avg_holding_minutes, 0)} />
            </div>
            <div className="card p-2 overflow-auto">
              <table className="w-full text-xs">
                <thead className="text-muted text-left"><tr className="[&>th]:py-1 [&>th]:pr-3">
                  <th>Exit</th><th>Dir</th><th>Contract</th><th>Reason</th><th>Ret%</th><th>Net</th></tr></thead>
                <tbody>
                  {d.trades.length === 0 && <tr><td colSpan={6} className="py-4 text-center text-muted">no trades for this view</td></tr>}
                  {d.trades.map((t) => (
                    <tr key={t.id} className="border-t border-edge [&>td]:py-1 [&>td]:pr-3 tabular-nums">
                      <td>{dt(t.exit_time)}</td>
                      <td>{t.direction}</td>
                      <td className="text-muted">{t.tradingsymbol}</td>
                      <td className="text-muted">{t.exit_reason}</td>
                      <td className={pnlColor(t.return_pct)}>{num(t.return_pct, 1)}</td>
                      <td className={pnlColor(t.net_pnl)}>{signedInr(t.net_pnl)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
```
(Verify `inr, signedInr, pnlColor, num, dt` exist in `../lib/format` — they are already imported by `DashboardView.tsx`.)

- [ ] **Step 4: Wire period selector + modal into the dashboard**

In `DashboardView.tsx`:
- Add to the imports: `import InstrumentDetailModal from './InstrumentDetailModal'`.
- Add state near `const [seg, setSeg]`:
```typescript
  const [period, setPeriod] = useState<'all' | 'today' | '7d' | '30d'>('all')
  const [detailKey, setDetailKey] = useState<string | null>(null)
```
- Change the loader effect to pass period and re-run on it:
```typescript
  useEffect(() => {
    const load = () => getDashboard(seg === 'all' ? undefined : seg, strat || undefined, period).then(setD)
    load()
    const t = setInterval(load, 5000)
    return () => clearInterval(t)
  }, [seg, strat, period])
```
- In the segment/strategy selector card, after the strategy `<select>`, add a period toggle group:
```tsx
        <span className="stat-label mx-1">Period</span>
        {(['all', 'today', '7d', '30d'] as const).map((p) => (
          <button key={p} onClick={() => setPeriod(p)}
            className={`badge ${period === p ? 'bg-purple-500/25 text-purple-200 border border-purple-400/40' : 'bg-zinc-700/40 text-muted hover:text-zinc-200'}`}>
            {p === 'all' ? 'All-time' : p}
          </button>
        ))}
```
- Make the per-instrument table rows clickable. In the `perInst.map(...)` row (~line 206-212), change the `<tr>` to:
```tsx
                <tr key={k} onClick={() => setDetailKey(k)}
                  className="border-t border-edge [&>td]:py-1 [&>td]:pr-3 tabular-nums cursor-pointer hover:bg-panel2/50">
```
- Just before the final closing `</div>` of the component's returned tree, add the modal:
```tsx
      {detailKey && (
        <InstrumentDetailModal instrumentKey={detailKey}
          segment={seg === 'all' ? undefined : seg} strategy={strat || undefined} period={period}
          onClose={() => setDetailKey(null)} />
      )}
```

- [ ] **Step 5: Verify typecheck + build**

Run (from `frontend/`): `npm run typecheck && npm run build`
Expected: both succeed, exit 0.

- [ ] **Step 6: Commit**

```bash
git add paper-trader/frontend/src/lib/api.ts paper-trader/frontend/src/lib/types.ts paper-trader/frontend/src/views/InstrumentDetailModal.tsx paper-trader/frontend/src/views/DashboardView.tsx
git commit -m "feat(dashboard): period selector + click-to-drilldown per-instrument modal"
```

---

## Phase 3 — Bulk-add backtest winners

### Task 9: Carry strategy + product through the add path

**Files:**
- Modify: `paper-trader/backend/app/core/universe_resolver.py` (`add_instrument`)
- Modify: `paper-trader/backend/app/api/routes.py` (`AddInstrument` model ~line 172-176; `portfolio_add` ~line 178-188)
- Test: `paper-trader/backend/tests/test_portfolio_add_config.py` (create)

**Interfaces:**
- Produces: `add_instrument(key, provider, on_home=True, interval=None, strategy_key=None, product=None)` — sets `InstrumentState.product`/`.strategy_key` when valid and echoes the applied values in the result dict (`out["product"]`, `out["strategy_key"]`). `/api/portfolio/add` body gains optional `strategy_key`, `product`; the route syncs `runner.products`/`runner.strategy_keys` from the result.

- [ ] **Step 1: Write the failing test**

Create `paper-trader/backend/tests/test_portfolio_add_config.py`:
```python
"""Single add carries strategy_key + product into InstrumentState + live runner dicts."""
from app.db.session import init_db
from app.engine.runner import EngineRunner
from app.main import app
from fastapi.testclient import TestClient


def _client():
    prev = getattr(app.state, "runner", None)
    if prev is not None:
        try:
            prev.broker.close()
        except Exception:
            pass
    init_db(reset=True)
    r = EngineRunner()
    app.state.runner = r
    return TestClient(app), r


def test_single_add_carries_strategy_and_product():
    c, r = _client()
    res = c.post("/api/portfolio/add", json={
        "key": "CRUDEOIL", "product": "equity_intraday",
        "strategy_key": "expanding_z_v4", "interval": "15minute"}).json()
    assert "error" not in res
    assert res.get("product") == "equity_intraday"
    assert res.get("strategy_key") == "expanding_z_v4"
    assert r.products.get("CRUDEOIL") == "equity_intraday"
    assert r.strategy_keys.get("CRUDEOIL") == "expanding_z_v4"
    assert "CRUDEOIL" in r.enabled
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tests/test_portfolio_add_config.py -v`
Expected: FAIL (`res.get("product")` is None — not carried)

- [ ] **Step 3: Extend `add_instrument`**

In `universe_resolver.py`, change the signature to:
```python
def add_instrument(key: str, provider, on_home: bool = True,
                   interval: str | None = None, strategy_key: str | None = None,
                   product: str | None = None) -> dict:
```
After the `if iv: st.live_interval = iv` line (inside the `with SessionLocal() as s:` block, before `s.commit()`) add:
```python
        applied_product = applied_strategy = None
        if product in ("options", "equity_intraday"):
            st.product = product
            applied_product = product
        if strategy_key:
            from app.strategy.registry import strategy_keys as _skeys
            if strategy_key in _skeys():
                st.strategy_key = strategy_key
                applied_strategy = strategy_key
```
Then, after the `out = {...}` dict is built (and after the `if iv:` / `if warning:` blocks), **before `return out`**, echo ONLY the values that were actually applied — never default them, so a plain re-add can't clobber an existing product/strategy:
```python
    if applied_product:
        out["product"] = applied_product
    if applied_strategy:
        out["strategy_key"] = applied_strategy
```

- [ ] **Step 4: Extend the single-add route**

In `routes.py`, extend the `AddInstrument` model (~line 172):
```python
class AddInstrument(BaseModel):
    key: str
    on_home: bool = True
    interval: str | None = None   # carry a backtest winner's timeframe into live
    strategy_key: str | None = None  # carry the winner's best strategy
    product: str | None = None       # options | equity_intraday
```
In `portfolio_add` (~line 178), pass the new args and sync the live dicts:
```python
@router.post("/api/portfolio/add")
def portfolio_add(body: AddInstrument, request: Request):
    from app.core import universe_resolver
    r = _runner(request)
    res = universe_resolver.add_instrument(body.key, r.provider, on_home=body.on_home,
                                           interval=body.interval,
                                           strategy_key=body.strategy_key, product=body.product)
    if "error" not in res:
        r.enabled.add(body.key)   # the live engine picks it up next tick
        if res.get("interval"):
            r.intervals[body.key] = res["interval"]
        if res.get("product"):
            r.products[body.key] = res["product"]
        if res.get("strategy_key"):
            r.strategy_keys[body.key] = res["strategy_key"]
    return res
```

- [ ] **Step 5: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tests/test_portfolio_add_config.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add paper-trader/backend/app/core/universe_resolver.py paper-trader/backend/app/api/routes.py paper-trader/backend/tests/test_portfolio_add_config.py
git commit -m "feat(portfolio): single-add carries strategy_key + product into InstrumentState + runner"
```

---

### Task 10: `POST /api/portfolio/add-bulk`

**Files:**
- Modify: `paper-trader/backend/app/api/routes.py` (add models + route after `portfolio_remove` ~line 197)
- Test: `paper-trader/backend/tests/test_portfolio_add_bulk.py` (create)

**Interfaces:**
- Consumes: extended `universe_resolver.add_instrument` from Task 9.
- Produces: `POST /api/portfolio/add-bulk {items: [{key, interval?, strategy_key?, product?, on_home?}]}` → `{added: [...], skipped: [{key, reason}]}`; every added item is enabled.

- [ ] **Step 1: Write the failing test**

Create `paper-trader/backend/tests/test_portfolio_add_bulk.py`:
```python
"""Bulk add: carries config, enables each item, reports skipped."""
from app.db.session import init_db
from app.engine.runner import EngineRunner
from app.main import app
from fastapi.testclient import TestClient


def _client():
    prev = getattr(app.state, "runner", None)
    if prev is not None:
        try:
            prev.broker.close()
        except Exception:
            pass
    init_db(reset=True)
    r = EngineRunner()
    app.state.runner = r
    return TestClient(app), r


def test_add_bulk_carries_config_and_enables():
    c, r = _client()
    body = {"items": [
        {"key": "CRUDEOIL", "interval": "15minute",
         "strategy_key": "expanding_z_v4", "product": "equity_intraday"},
        {"key": "SILVERM", "interval": "30minute", "product": "options"},
        {"key": "NOPE_NOT_REAL", "product": "options"}]}
    res = c.post("/api/portfolio/add-bulk", json=body).json()
    added = {a["key"] for a in res["added"]}
    skipped = {s["key"] for s in res["skipped"]}
    assert {"CRUDEOIL", "SILVERM"} <= added
    assert "NOPE_NOT_REAL" in skipped
    assert "CRUDEOIL" in r.enabled and "SILVERM" in r.enabled
    assert r.products.get("CRUDEOIL") == "equity_intraday"
    assert r.strategy_keys.get("CRUDEOIL") == "expanding_z_v4"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tests/test_portfolio_add_bulk.py -v`
Expected: FAIL (404 — route does not exist)

- [ ] **Step 3: Add the bulk route**

In `routes.py`, after `portfolio_remove` (~line 197) add:
```python
class BulkItem(BaseModel):
    key: str
    interval: str | None = None
    strategy_key: str | None = None
    product: str | None = None
    on_home: bool = True


class BulkAdd(BaseModel):
    items: list[BulkItem]


@router.post("/api/portfolio/add-bulk")
def portfolio_add_bulk(body: BulkAdd, request: Request):
    """Add several instruments at once (backtest winners). Each carries its best
    interval / strategy / product; every successfully added item is enabled for
    live trading. Over-budget names are excluded client-side before posting."""
    from app.core import universe_resolver
    r = _runner(request)
    added, skipped = [], []
    for it in body.items:
        res = universe_resolver.add_instrument(
            it.key, r.provider, on_home=it.on_home, interval=it.interval,
            strategy_key=it.strategy_key, product=it.product)
        if "error" in res:
            skipped.append({"key": it.key, "reason": res["error"]})
            continue
        r.enabled.add(it.key)
        if res.get("interval"):
            r.intervals[it.key] = res["interval"]
        if res.get("product"):
            r.products[it.key] = res["product"]
        if res.get("strategy_key"):
            r.strategy_keys[it.key] = res["strategy_key"]
        added.append(res)
    return {"added": added, "skipped": skipped}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tests/test_portfolio_add_bulk.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add paper-trader/backend/app/api/routes.py paper-trader/backend/tests/test_portfolio_add_bulk.py
git commit -m "feat(portfolio): POST /api/portfolio/add-bulk for backtest winners"
```

---

### Task 11: Expose `has_options` on backtest result rows

**Files:**
- Modify: `paper-trader/backend/app/api/backtest_routes.py` (`results` loop ~line 198-201)
- Test: `paper-trader/backend/tests/test_backtest_has_options.py` (create)

**Interfaces:**
- Produces: each `/api/backtest/results` row gains `has_options: bool` (from the instrument registry), so the bulk-add preview can infer product.

- [ ] **Step 1: Write the failing test**

Create `paper-trader/backend/tests/test_backtest_has_options.py`:
```python
"""Backtest result rows expose has_options for product inference."""
from app.db.models import BacktestResult, BacktestRun
from app.db.session import SessionLocal, init_db
from app.engine.runner import EngineRunner
from app.main import app
from fastapi.testclient import TestClient


def _client():
    prev = getattr(app.state, "runner", None)
    if prev is not None:
        try:
            prev.broker.close()
        except Exception:
            pass
    init_db(reset=True)
    app.state.runner = EngineRunner()
    return TestClient(app)


def test_results_carry_has_options():
    c = _client()
    with SessionLocal() as s:
        s.add(BacktestRun(id=1, status="done", scope="liquid"))
        s.add(BacktestResult(run_id=1, instrument_key="NIFTY", interval="15minute",
                             trades=5, win_rate=60.0, return_pct=10.0, net_pnl=500.0))
        s.commit()
    rows = c.get("/api/backtest/results?run_id=1&min_trades=1").json()["results"]
    assert rows and "has_options" in rows[0]
    assert isinstance(rows[0]["has_options"], bool)
```
(`BacktestRun` only requires sensible defaults; pass `id`, `status`, `scope`. If `BacktestRun` requires more non-null fields, add them with simple values — inspect `app/db/models.py::BacktestRun`.)

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tests/test_backtest_has_options.py -v`
Expected: FAIL (`has_options` not in the row)

- [ ] **Step 3: Attach `has_options` in the results payload**

In `backtest_routes.py`, ensure `from app.core.instruments import get_instrument` is imported at the top. In the `results` loop, right after `d = _with_affordability(r.summary(), budget)` (~line 198) add:
```python
        _inst = get_instrument(r.instrument_key)
        d["has_options"] = bool(_inst.has_options) if _inst else True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tests/test_backtest_has_options.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add paper-trader/backend/app/api/backtest_routes.py paper-trader/backend/tests/test_backtest_has_options.py
git commit -m "feat(backtest): expose has_options on result rows for product inference"
```

---

### Task 12: "Add top N" bulk control + preview modal (frontend)

**Files:**
- Modify: `paper-trader/frontend/src/lib/api.ts` (add `addBulkToPortfolio`)
- Modify: `paper-trader/frontend/src/lib/types.ts` (`BTResult` add `has_options?`)
- Create: `paper-trader/frontend/src/views/BulkAddModal.tsx`
- Modify: `paper-trader/frontend/src/views/BacktestsView.tsx` (control near sort UI; best-per-instrument derivation; render modal)

**Interfaces:**
- Consumes: `view` (filtered+sorted `BTResult[]`), `sort` key, `ASC` set, `stratLabel` (already in BacktestsView).
- Produces: `addBulkToPortfolio(items)`; `<BulkAddModal>`; "Add top N" button.

- [ ] **Step 1: Add the api helper**

In `api.ts`, after `addToPortfolio` (~line 61) add:
```typescript
export const addBulkToPortfolio = (items: Array<{
  key: string; interval?: string; strategy_key?: string | null; product?: string; on_home?: boolean
}>) => post('/api/portfolio/add-bulk', { items })
```

- [ ] **Step 2: Extend the BTResult type**

In `types.ts`, inside `BTResult` (after `affordable_options?` ~line 146) add:
```typescript
  has_options?: boolean
```

- [ ] **Step 3: Create the preview modal**

Create `paper-trader/frontend/src/views/BulkAddModal.tsx`:
```tsx
import { useState } from 'react'
import { addBulkToPortfolio } from '../lib/api'
import { inr, num, pnlColor } from '../lib/format'
import type { BTResult } from '../lib/types'

type Row = {
  r: BTResult
  product: 'options' | 'equity_intraday'
  include: boolean
}

export default function BulkAddModal(
  { winners, stratLabel, onClose, onDone }:
  { winners: BTResult[]; stratLabel: (k: string) => string; onClose: () => void; onDone: () => void }) {
  // over-budget for an options name = ATM option cost over budget; intraday names are
  // effectively always sizeable, so they default to included.
  const [rows, setRows] = useState<Row[]>(() => winners.map((r) => {
    const product: Row['product'] = r.has_options === false ? 'equity_intraday' : 'options'
    const overBudget = product === 'options' && r.affordable_options === false
    return { r, product, include: !overBudget }
  }))
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<{ added: any[]; skipped: any[] } | null>(null)

  const setRow = (i: number, patch: Partial<Row>) =>
    setRows((rs) => rs.map((row, j) => (j === i ? { ...row, ...patch } : row)))

  const confirm = async () => {
    setBusy(true)
    const items = rows.filter((x) => x.include).map((x) => ({
      key: x.r.instrument_key, interval: x.r.interval,
      strategy_key: x.r.strategy_key, product: x.product, on_home: true,
    }))
    const res = await addBulkToPortfolio(items)
    setResult(res); setBusy(false); onDone()
  }

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="card w-full max-w-4xl p-4 flex flex-col gap-3 max-h-[92vh] overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between shrink-0">
          <span className="text-lg font-semibold text-zinc-100">Add top {rows.length} to portfolio</span>
          <button onClick={onClose} className="btn">✕ close</button>
        </div>
        {result ? (
          <div className="text-sm">
            <div className="text-up mb-1">Added {result.added.length}.</div>
            {result.skipped.length > 0 && (
              <div className="text-amber-400">Skipped {result.skipped.length}: {result.skipped.map((s) => `${s.key} (${s.reason})`).join(', ')}</div>
            )}
            <button onClick={onClose} className="btn mt-3">done</button>
          </div>
        ) : (
          <>
            <div className="text-[11px] text-muted shrink-0">
              Each name is preset to its best strategy + timeframe. Over-budget options names are unticked by default; tick to include. Included names are added AND enabled for live trading.
            </div>
            <div className="card p-2 overflow-auto">
              <table className="w-full text-xs">
                <thead className="text-muted text-left"><tr className="[&>th]:py-1 [&>th]:pr-3">
                  <th>Add</th><th>Instrument</th><th>Strategy</th><th>TF</th><th>Product</th><th>Return%</th><th>Affordable</th></tr></thead>
                <tbody>
                  {rows.map((row, i) => (
                    <tr key={row.r.instrument_key} className="border-t border-edge [&>td]:py-1 [&>td]:pr-3 tabular-nums">
                      <td><input type="checkbox" checked={row.include} onChange={(e) => setRow(i, { include: e.target.checked })} /></td>
                      <td className="font-semibold text-zinc-100">{row.r.name || row.r.instrument_key}</td>
                      <td className="text-muted">{stratLabel(row.r.strategy_key)}</td>
                      <td className="text-muted">{row.r.interval}</td>
                      <td>
                        <select value={row.product} onChange={(e) => setRow(i, { product: e.target.value as Row['product'] })}
                          className="bg-panel2 border border-edge rounded px-1 py-0.5 text-[11px]">
                          <option value="options">Options</option>
                          <option value="equity_intraday">Intraday-equity</option>
                        </select>
                      </td>
                      <td className={pnlColor(row.r.return_pct)}>{num(row.r.return_pct, 1)}</td>
                      <td className={row.product === 'options' && row.r.affordable_options === false ? 'text-amber-400' : 'text-up/80'}>
                        {row.product === 'equity_intraday' ? 'MIS' : (row.r.affordable_options === false ? `over (${row.r.option_cost ? inr(row.r.option_cost) : '—'})` : 'yes')}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex justify-end shrink-0">
              <button onClick={confirm} disabled={busy || !rows.some((x) => x.include)} className="btn border-up/50 text-up">
                {busy ? 'adding…' : `add ${rows.filter((x) => x.include).length} enabled`}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
```
(Verify `inr, num, pnlColor` exist in `../lib/format` — `BacktestsView` already imports `num`/`inr`.)

- [ ] **Step 4: Wire the control + best-per-instrument into BacktestsView**

In `BacktestsView.tsx`:
- Add to imports: `import BulkAddModal from './BulkAddModal'` and add `addBulkToPortfolio` is not needed here (modal owns it).
- Add state near the other `useState`s (~line 52):
```typescript
  const [topN, setTopN] = useState(5)
  const [bulkWinners, setBulkWinners] = useState<BTResult[] | null>(null)
```
- After the `view` array is computed (~line 171), add the best-per-instrument derivation:
```typescript
  // best row per instrument (across intervals × strategies) by the CURRENT sort,
  // honoring lower-is-better metrics. Used by the "Add top N" bulk action.
  const bestPerInstrument = (() => {
    const best = new Map<string, BTResult>()
    for (const r of view) {            // `view` is already sorted best-first
      if (!best.has(r.instrument_key)) best.set(r.instrument_key, r)
    }
    return [...best.values()]          // preserves `view` order = sorted best-first
  })()
  const openBulk = () => setBulkWinners(bestPerInstrument.slice(0, Math.max(1, topN)))
```
- Near the sort/filter controls (find the row that renders the `sort` selector), add:
```tsx
        <span className="stat-label ml-2">Add top</span>
        <input type="number" min={1} max={50} value={topN}
          onChange={(e) => setTopN(parseInt(e.target.value) || 1)}
          className="bg-panel2 border border-edge rounded px-1 py-0.5 text-xs w-14" />
        <button onClick={openBulk} disabled={bestPerInstrument.length === 0}
          className="btn border-up/50 text-up text-xs" title="add the top N best instruments (each at its best strategy + timeframe) to the watchlist">
          + add top {topN} to portfolio
        </button>
```
- Before the component's closing tag, render the modal:
```tsx
      {bulkWinners && (
        <BulkAddModal winners={bulkWinners} stratLabel={stratLabel}
          onClose={() => setBulkWinners(null)}
          onDone={() => setAdded((s) => { const n = new Set(s); bulkWinners.forEach((w) => n.add(w.instrument_key)); return n })} />
      )}
```
(`stratLabel` already exists in `BacktestsView`; if it is named differently, reuse the existing strategy-label helper. If no `stratLabel` exists, pass `(k) => availStrategies.find((x) => x.key === k)?.display_name || k`.)

- [ ] **Step 5: Verify typecheck + build**

Run (from `frontend/`): `npm run typecheck && npm run build`
Expected: both succeed, exit 0.

- [ ] **Step 6: Commit**

```bash
git add paper-trader/frontend/src/lib/api.ts paper-trader/frontend/src/lib/types.ts paper-trader/frontend/src/views/BulkAddModal.tsx paper-trader/frontend/src/views/BacktestsView.tsx
git commit -m "feat(backtests): add-top-N bulk control + preview modal (best strategy + timeframe)"
```

---

## Final verification (after all tasks)

- [ ] Backend full suite: `cd paper-trader/backend && source .venv/bin/activate && python -m pytest -q` → all pass.
- [ ] Frontend: `cd paper-trader/frontend && npm run typecheck && npm run build` → both clean.
- [ ] Manual smoke (optional, via the `run` skill): start the app, confirm the Watchlist red dot + counts render, the Dashboard period toggle + per-instrument modal work, and "Add top N" on Backtests adds names to the Watchlist with the right strategy/timeframe/product.

> Note: the overtrade-threshold Settings group is built in Task 5 (Step 4). Without it the keys still work via the API but won't appear grouped in the Settings UI.
