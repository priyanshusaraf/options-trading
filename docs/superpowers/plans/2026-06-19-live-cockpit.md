# Live Trading Cockpit — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (chosen cadence: write full plan, then execute straight through with a checkpoint after every Phase). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the paper-trader from a "show charts for every instrument" app into a signal-first, position-first live trading cockpit: a fast backend position-risk loop split from a slower signal-scan loop, per-instrument live timeframes, outage/stale-data safety, a lightweight signal list with click-to-detail charts, a new Active Positions cockpit with manual paper controls, and a reusable backtest cache.

**Architecture:** Backend keeps the existing `MarketDataProvider` seam and the `SafePaperKite` barrier untouched. `EngineRunner.tick()` is decomposed into three pure methods (`scan_signals`, `mark_and_exit_positions`, `process_entries`) that the combined `tick()` (mock/dryrun) still calls in order, while live mode runs two cooperative asyncio loops at different cadences (fast risk loop ~1s, slow signal loop gated by next-candle time). All position/capital DB mutation is serialized by one `asyncio.Lock`; no threads/executors are introduced, so the single SQLAlchemy session stays single-threaded. New per-instrument state (`live_interval`, `entries_blocked`), per-position freshness (`last_mark_time`), and backtest-cache columns are added via additive `ALTER TABLE` migrations (no Alembic). Frontend converts the chart-per-row tile grid into a signal-first table + a new Active Positions page; charts load only inside the click-to-open detail modal.

**Tech Stack:** Python 3.10+, FastAPI, SQLAlchemy 2.x (SQLite + WAL), pandas/numpy, pytest. React 18 + TypeScript + Vite + Tailwind, lightweight-charts v4, native WebSocket.

## Global Constraints

These apply to **every** task. Copied verbatim from the spec / repo invariants:

- **Paper-only, no real orders, ever.** `SafePaperKite` stays the hard barrier; no order/GTT/modify endpoint may be called. No manual or automatic path may reach a real Kite order. `tests/test_safety.py` must keep passing unchanged.
- **No pyramiding.** Exactly one open position per instrument. A new position only opens on a fresh signal (or explicit manual open) when no position is held for that instrument.
- **Always 1 lot** per trade (F&O lot size); manual entries are also 1 lot.
- **Capital ledger invariant holds to the paisa:** `cash == initial_capital + realized_pnl - Σ(open entry_cost)` (checked by `PaperBroker.reconcile()` and `scripts/dryrun.py`).
- **Do not break existing views/analytics.** Dashboard, Engine/Logs, Options Calc, Backtests keep working.
- **Mock determinism preserved.** `scripts/dryrun.py` and `scripts/backtest_smoke.py` force the mock provider and must keep their invariants. `tick()` semantics for mock/dryrun must not change.
- **All 83 existing backend tests must stay green** at every phase boundary; new tests are added, none deleted.
- **Strategy math is frozen.** `app/strategy/signals.py` is the single source of truth and is **not** modified.
- **Migrations are additive and idempotent.** Never drop/rewrite the live `paper_trader.db`; only `ALTER TABLE ... ADD COLUMN`.

## Feature → Task coverage (codex's 8 items)

| # | Codex item | Tasks |
|---|------------|-------|
| F1 | Signal-first list view | T15, T16 |
| F2 | Click-to-inspect details | T14, T16 |
| F3 | Active Positions page | T17 |
| F4 | Split backend update lanes | T6, T7, T8 |
| F5 | Outage & stale-data handling | T4, T5, T7, T13, T15 |
| F6 | Per-instrument live timeframes | T1, T3, T12, T18 |
| F7 | Backtest cache upgrade | T10, T11 |
| F8 | Manual override mode | T2, T9, T13, T17 |

---

## File Structure

**New backend files**
- `paper-trader/backend/app/engine/health.py` — `HealthTracker` + pure freshness helpers (`is_stale`, `provider_health_dict`).
- `paper-trader/backend/app/backtest/cache.py` — `params_signature()`, `find_reusable()`, `SCHEMA_VERSION`.
- `paper-trader/backend/tests/test_migration.py`, `test_intervals.py`, `test_health.py`, `test_engine_loops.py`, `test_routes_manual.py`, `test_backtest_cache.py`, `test_manual_broker.py`.

**Modified backend files**
- `app/db/models.py` — new columns on `InstrumentState`, `Position`, `BacktestResult`.
- `app/db/session.py` — `_migrate_schema()` called from `init_db`.
- `app/core/config.py` — `LIVE_INTERVALS`, `DEFAULT_LIVE_INTERVAL`, `normalize_live_interval`, cadence settings, `max_stale_seconds`.
- `app/engine/runner.py` — decompose `tick()`; add `risk`/`signal` loops, interval map, health, next-candle gating, manual ops.
- `app/engine/broker.py` — `manual_open()` (validation) + set `last_mark_time` in `mark()`.
- `app/engine/exit_monitor.py` — unchanged logic; staleness handled in runner (documented).
- `app/main.py` — launch `risk_loop` + `signal_loop` (drop separate `live_quotes`).
- `app/api/routes.py` — list/positions/health endpoints, interval set, manual close/open/disable, per-instrument candle interval.
- `app/api/backtest_routes.py` — surface `from_cache`.
- `app/backtest/sweep.py` — cache lookup in `_one`.
- `app/core/universe_resolver.py` — `add_instrument(..., interval=None)` carry-over.

**Modified frontend files**
- `package.json` — add `"typecheck": "tsc --noEmit"`.
- `src/lib/types.ts` — new DTO fields (`live_interval`, health, stale, `entries_blocked`, `from_cache`, etc.).
- `src/lib/api.ts` — new endpoints.
- `src/state/LiveContext.tsx` — handle `position_ticks`, expose `health`.
- `src/components/InstrumentTile.tsx` — remove always-on chart (chartless tile).
- `src/views/Monitor.tsx` — replace tile grid with signal-first table + filters; keep `Expanded` detail modal (charts lazy-load).
- `src/views/HomeView.tsx` — chartless tiles (uses updated InstrumentTile).
- `src/views/BacktestsView.tsx` — pass interval on promote; show cache badge.
- `src/App.tsx` + `src/components/TopBar.tsx` — add "Active Positions" tab.
- **New:** `src/views/ActivePositionsView.tsx` — cockpit + manual controls; `src/views/components` reused.

---

# PHASE 1 — Schema, intervals, config (codex item 1 + parts of F5/F6/F8)

### Task T1: Add new columns to models

**Files:**
- Modify: `paper-trader/backend/app/db/models.py`
- Test: `paper-trader/backend/tests/test_intervals.py` (created here, expanded in T3)

**Interfaces — Produces:**
- `InstrumentState.live_interval: str` (default `"15minute"`), `InstrumentState.entries_blocked: bool` (default `False`)
- `Position.last_mark_time: datetime | None`
- `BacktestResult.params_hash: str`, `.last_candle_ts: int`, `.schema_version: int`, `.from_cache: bool`, `.computed_at: datetime | None`

- [ ] **Step 1: Write the failing test**
```python
# tests/test_intervals.py
from app.db.models import InstrumentState, Position, BacktestResult

def test_instrument_state_has_interval_defaults():
    cols = InstrumentState.__table__.columns
    assert "live_interval" in cols
    assert "entries_blocked" in cols

def test_position_has_last_mark_time():
    assert "last_mark_time" in Position.__table__.columns

def test_backtest_result_has_cache_columns():
    cols = BacktestResult.__table__.columns
    for c in ("params_hash", "last_candle_ts", "schema_version", "from_cache", "computed_at"):
        assert c in cols
```

- [ ] **Step 2: Run to verify it fails**
Run: `cd paper-trader/backend && .venv/bin/python -m pytest tests/test_intervals.py -q`
Expected: FAIL (`KeyError`/`assert` on missing columns).

- [ ] **Step 3: Add columns**
In `InstrumentState`:
```python
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    live_interval: Mapped[str] = mapped_column(String(12), default="15minute")
    entries_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
```
In `Position` (after `last_spot`):
```python
    last_mark_time: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
```
In `BacktestResult` (after `error`):
```python
    params_hash: Mapped[str] = mapped_column(String(64), default="")
    last_candle_ts: Mapped[int] = mapped_column(Integer, default=0)
    schema_version: Mapped[int] = mapped_column(Integer, default=1)
    from_cache: Mapped[bool] = mapped_column(Boolean, default=False)
    computed_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
```
Add `from_cache` to `BacktestResult.summary()`:
```python
            "bars": self.bars,
            "from_cache": self.from_cache,
            "error": self.error,
```

- [ ] **Step 4: Run to verify it passes**
Run: `cd paper-trader/backend && .venv/bin/python -m pytest tests/test_intervals.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add paper-trader/backend/app/db/models.py paper-trader/backend/tests/test_intervals.py
git commit -m "feat(db): add live_interval/entries_blocked/last_mark_time and backtest cache columns"
```

---

### Task T2: Additive ALTER-based schema migration

**Files:**
- Modify: `paper-trader/backend/app/db/session.py`
- Test: `paper-trader/backend/tests/test_migration.py`

**Interfaces — Produces:** `app.db.session._migrate_schema()` (idempotent), invoked by `init_db()`.

- [ ] **Step 1: Write the failing test** — simulate an old DB missing the new columns, then assert migration adds them.
```python
# tests/test_migration.py
from sqlalchemy import create_engine, text

def test_migration_adds_missing_columns(tmp_path, monkeypatch):
    db = tmp_path / "old.db"
    eng = create_engine(f"sqlite:///{db}", future=True)
    # an "old" instrument_state table missing the new columns
    with eng.begin() as c:
        c.execute(text("CREATE TABLE instrument_state (instrument_key VARCHAR(32) PRIMARY KEY, enabled BOOLEAN)"))
        c.execute(text("INSERT INTO instrument_state VALUES ('NIFTY', 1)"))

    import app.db.session as sess
    monkeypatch.setattr(sess, "engine", eng)
    sess._migrate_schema()

    with eng.begin() as c:
        cols = {r[1] for r in c.execute(text("PRAGMA table_info(instrument_state)"))}
    assert {"live_interval", "entries_blocked"} <= cols
    # idempotent: a second run must not raise
    sess._migrate_schema()
```

- [ ] **Step 2: Run to verify it fails**
Run: `.venv/bin/python -m pytest tests/test_migration.py -q`
Expected: FAIL (`_migrate_schema` not defined / table missing columns).

- [ ] **Step 3: Implement `_migrate_schema` and call it from `init_db`**
Add to `app/db/session.py` (before `init_db`):
```python
def _migrate_schema() -> None:
    """Additive, idempotent SQLite migrations (no Alembic in this project).
    For a fresh DB, create_all already made these columns, so every ALTER is
    skipped; for an existing live DB, the new columns are appended in place."""
    from sqlalchemy import text
    additions = {
        "instrument_state": [
            ("live_interval", "VARCHAR(12) DEFAULT '15minute'"),
            ("entries_blocked", "BOOLEAN DEFAULT 0"),
        ],
        "positions": [
            ("last_mark_time", "DATETIME"),
        ],
        "backtest_results": [
            ("params_hash", "VARCHAR(64) DEFAULT ''"),
            ("last_candle_ts", "INTEGER DEFAULT 0"),
            ("schema_version", "INTEGER DEFAULT 1"),
            ("from_cache", "BOOLEAN DEFAULT 0"),
            ("computed_at", "DATETIME"),
        ],
    }
    with engine.begin() as conn:
        for table, cols in additions.items():
            existing = {r[1] for r in conn.execute(text(f"PRAGMA table_info({table})"))}
            if not existing:
                continue  # table not created yet; create_all handles fresh schema
            for name, ddl in cols:
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
```
In `init_db`, right after `Base.metadata.create_all(engine)`:
```python
    Base.metadata.create_all(engine)
    _migrate_schema()
```

- [ ] **Step 4: Run to verify it passes**
Run: `.venv/bin/python -m pytest tests/test_migration.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add paper-trader/backend/app/db/session.py paper-trader/backend/tests/test_migration.py
git commit -m "feat(db): additive ALTER-based schema migration for live-cockpit columns"
```

---

### Task T3: Live-interval config helpers

**Files:**
- Modify: `paper-trader/backend/app/core/config.py`
- Test: `paper-trader/backend/tests/test_intervals.py` (append)

**Interfaces — Produces:** `config.LIVE_INTERVALS: tuple[str,...]`, `config.DEFAULT_LIVE_INTERVAL: str`, `config.normalize_live_interval(iv: str) -> str`; new `Settings` fields `position_loop_seconds: float = 1.0`, `signal_loop_seconds: float = 2.5`, `max_stale_seconds: float = 30.0`.

- [ ] **Step 1: Write the failing test** (append to `tests/test_intervals.py`)
```python
from app.core import config

def test_live_intervals_and_normalize():
    assert config.LIVE_INTERVALS == ("5minute", "15minute", "30minute", "60minute")
    assert config.DEFAULT_LIVE_INTERVAL == "15minute"
    assert config.normalize_live_interval("60minute") == "60minute"
    assert config.normalize_live_interval("1minute") == "15minute"   # unsupported -> default
    assert config.normalize_live_interval("") == "15minute"

def test_cadence_settings_present():
    s = config.get_settings()
    assert s.position_loop_seconds > 0 and s.signal_loop_seconds > 0
    assert s.max_stale_seconds >= 1
```

- [ ] **Step 2: Run to verify it fails**
Run: `.venv/bin/python -m pytest tests/test_intervals.py -q`
Expected: FAIL (`AttributeError`).

- [ ] **Step 3: Implement** — in `app/core/config.py`, after `ALLOWED_INTERVALS`:
```python
ALLOWED_INTERVALS = ("15minute", "30minute")
LIVE_INTERVALS = ("5minute", "15minute", "30minute", "60minute")
DEFAULT_LIVE_INTERVAL = "15minute"

def normalize_live_interval(iv: str) -> str:
    """Clamp an arbitrary interval to a supported live timeframe (default 15m)."""
    return iv if iv in LIVE_INTERVALS else DEFAULT_LIVE_INTERVAL
```
Add to `Settings` (in the "mock demo clock" / misc area):
```python
    # split-loop cadences (live)
    position_loop_seconds: float = 1.0   # fast risk lane target (Kite throttle bounds it ~2s)
    signal_loop_seconds: float = 2.5     # signal scan scheduler tick
    max_stale_seconds: float = 30.0      # mark older than this => treat as stale; no SL/TP
```

- [ ] **Step 4: Run to verify it passes**
Run: `.venv/bin/python -m pytest tests/test_intervals.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add paper-trader/backend/app/core/config.py paper-trader/backend/tests/test_intervals.py
git commit -m "feat(config): live intervals, normalize helper, split-loop cadences"
```

**PHASE 1 GATE:** `.venv/bin/python -m pytest -q` → all green (86+ tests). Checkpoint with user.

---

# PHASE 2 — Health / stale tracking (F5)

### Task T4: `HealthTracker` + freshness helpers (pure)

**Files:**
- Create: `paper-trader/backend/app/engine/health.py`
- Test: `paper-trader/backend/tests/test_health.py`

**Interfaces — Produces:**
- `is_stale(last_ok: datetime | None, now: datetime, max_stale_seconds: float) -> bool`
- `class HealthTracker` with `record_ok(category: str, now: datetime)`, `record_fail(category: str, msg: str, now: datetime)`, `quote_health() -> dict`, `candle_health() -> dict`, `as_dict() -> dict`. Categories used: `"quote"`, `"candle"`.

- [ ] **Step 1: Write the failing test**
```python
# tests/test_health.py
import datetime as dt
from app.engine.health import is_stale, HealthTracker

NOW = dt.datetime(2026, 6, 19, 12, 0, 0)

def test_is_stale():
    assert is_stale(None, NOW, 30) is True
    assert is_stale(NOW - dt.timedelta(seconds=5), NOW, 30) is False
    assert is_stale(NOW - dt.timedelta(seconds=45), NOW, 30) is True

def test_tracker_counts_and_resets():
    h = HealthTracker()
    h.record_fail("quote", "429 too many requests", NOW)
    h.record_fail("quote", "429 too many requests", NOW)
    assert h.quote_health()["consecutive_failures"] == 2
    assert "429" in h.quote_health()["last_error"]
    h.record_ok("quote", NOW)
    assert h.quote_health()["consecutive_failures"] == 0
    assert h.quote_health()["last_ok"] == NOW.isoformat()

def test_as_dict_shape():
    h = HealthTracker()
    h.record_ok("candle", NOW)
    d = h.as_dict()
    assert set(d) >= {"quote", "candle"}
    assert d["candle"]["last_ok"] == NOW.isoformat()
```

- [ ] **Step 2: Run to verify it fails**
Run: `.venv/bin/python -m pytest tests/test_health.py -q`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement `app/engine/health.py`**
```python
"""
Provider/data health + freshness. The engine must not crash on a Kite/internet
outage, must never fire SL/TP on a stale or missing price, and must show the UI
that data is stale rather than pretending it is live. This module is pure (no DB,
no network) so it is trivially testable; the runner owns one HealthTracker.
"""
from __future__ import annotations

import datetime as dt


def is_stale(last_ok: dt.datetime | None, now: dt.datetime, max_stale_seconds: float) -> bool:
    """True if the last good update is missing or older than the budget."""
    if last_ok is None:
        return True
    return (now - last_ok).total_seconds() > max_stale_seconds


class _Cat:
    def __init__(self) -> None:
        self.last_ok: dt.datetime | None = None
        self.consecutive_failures: int = 0
        self.last_error: str = ""

    def to_dict(self) -> dict:
        return {
            "last_ok": self.last_ok.isoformat() if self.last_ok else None,
            "consecutive_failures": self.consecutive_failures,
            "last_error": self.last_error,
        }


class HealthTracker:
    """Per-category (quote/candle) success/failure tracking. In-memory; resets on
    restart, which is fine — it only reports current live health."""

    def __init__(self) -> None:
        self._cats: dict[str, _Cat] = {"quote": _Cat(), "candle": _Cat()}

    def _cat(self, category: str) -> _Cat:
        return self._cats.setdefault(category, _Cat())

    def record_ok(self, category: str, now: dt.datetime) -> None:
        c = self._cat(category)
        c.last_ok = now
        c.consecutive_failures = 0

    def record_fail(self, category: str, msg: str, now: dt.datetime) -> None:
        c = self._cat(category)
        c.consecutive_failures += 1
        c.last_error = (msg or "")[:200]

    def quote_health(self) -> dict:
        return self._cat("quote").to_dict()

    def candle_health(self) -> dict:
        return self._cat("candle").to_dict()

    def as_dict(self) -> dict:
        return {k: v.to_dict() for k, v in self._cats.items()}
```

- [ ] **Step 4: Run to verify it passes**
Run: `.venv/bin/python -m pytest tests/test_health.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add paper-trader/backend/app/engine/health.py paper-trader/backend/tests/test_health.py
git commit -m "feat(engine): pure HealthTracker + is_stale freshness helper"
```

---

### Task T5: Broker stamps `last_mark_time`

**Files:**
- Modify: `paper-trader/backend/app/engine/broker.py`
- Test: `paper-trader/backend/tests/test_manual_broker.py` (created here, expanded in T9)

**Interfaces — Consumes:** `Position.last_mark_time` (T1). **Produces:** `mark()` sets `last_mark_time` when a premium is applied; `open_position()` sets it at fill.

- [ ] **Step 1: Write the failing test**
```python
# tests/test_manual_broker.py
import datetime as dt
from app.db.session import init_db, SessionLocal
from app.providers.mock import MockProvider
from app.engine.broker import PaperBroker
from app.core.instruments import get_instrument

def _broker():
    init_db(reset=True)
    return PaperBroker(MockProvider())

def test_mark_sets_last_mark_time():
    b = _broker()
    inst = get_instrument("NIFTY")
    chain = b.provider.get_option_chain(inst)
    q = chain.quotes[0]
    pos = b.open_position(inst, "LONG", q, "test", b.provider.now(), chain.spot)
    assert pos.last_mark_time is not None
    pos.last_mark_time = None
    b.mark(pos, premium=q.ltp * 1.1, spot=chain.spot)
    assert pos.last_mark_time is not None
```

- [ ] **Step 2: Run to verify it fails**
Run: `.venv/bin/python -m pytest tests/test_manual_broker.py -q`
Expected: FAIL (`mark` does not set `last_mark_time`).

- [ ] **Step 3: Implement** — in `broker.py`:
In `mark()`, accept an optional `now` and stamp it:
```python
    def mark(self, pos: Position, premium: float | None, spot: float | None,
             now: dt.datetime | None = None) -> None:
        if premium:
            pos.last_premium = premium
            pos.last_mark_time = now or dt.datetime.now()
        if spot:
            pos.last_spot = spot
```
In `open_position()`, set the field on the new `Position(...)` (add to the constructor kwargs):
```python
            last_premium=premium, last_spot=spot, last_mark_time=now,
```

- [ ] **Step 4: Run to verify it passes**
Run: `.venv/bin/python -m pytest tests/test_manual_broker.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add paper-trader/backend/app/engine/broker.py paper-trader/backend/tests/test_manual_broker.py
git commit -m "feat(broker): stamp last_mark_time on fill and mark"
```

**PHASE 2 GATE:** full `pytest -q` green. Checkpoint.

---

# PHASE 3 — Split engine loops + per-instrument intervals (F4, F6)

> This phase decomposes `tick()` into reusable methods, then runs them on two cadences. `tick()` keeps its exact mock/dryrun behavior (it calls the three methods in order).

### Task T6: Decompose `tick()` into `scan_signals` / `mark_and_exit_positions` / `process_entries`

**Files:**
- Modify: `paper-trader/backend/app/engine/runner.py`
- Test: `paper-trader/backend/tests/test_engine_loops.py`

**Interfaces — Produces (on `EngineRunner`):**
- `scan_signals() -> None` — recompute strategy state for enabled instruments (per-instrument interval), update `self.state`, record candle health.
- `mark_and_exit_positions() -> None` — batched marks of open positions, staleness guard, SL/TP/strategy exits, record quote health.
- `process_entries() -> None` — fresh-crossover entries (existing entry logic, now skipping `entries_blocked`).
- `self.intervals: dict[str, str]`, `self.health: HealthTracker`, `self.position_ticks: dict`, `_interval_for(key) -> str`, `set_interval(key, iv)`.
- `tick()` calls the three in order + snapshot (unchanged externally).

- [ ] **Step 1: Write the failing test** (behavioral parity + interval wiring + entries_blocked)
```python
# tests/test_engine_loops.py
from app.db.session import init_db, SessionLocal
from app.db.models import InstrumentState
from app.engine.runner import EngineRunner
from app.core import config

def _runner():
    init_db(reset=True)
    return EngineRunner()

def test_runner_has_split_methods_and_state():
    r = _runner()
    for m in ("scan_signals", "mark_and_exit_positions", "process_entries", "set_interval"):
        assert hasattr(r, m)
    assert isinstance(r.intervals, dict)
    assert r.health is not None

def test_tick_still_advances_and_marks():
    r = _runner()
    for _ in range(120):
        r.tick(); r.provider.advance()
    # the combined tick must still produce engine state and a valid ledger
    assert r.broker.reconcile()["diff"] == 0.0
    assert r.tick_count == 120

def test_interval_default_and_set():
    r = _runner()
    assert r._interval_for("NIFTY") == config.DEFAULT_LIVE_INTERVAL
    r.set_interval("NIFTY", "60minute")
    assert r._interval_for("NIFTY") == "60minute"
    with SessionLocal() as s:
        assert s.get(InstrumentState, "NIFTY").live_interval == "60minute"
    r.set_interval("NIFTY", "1minute")   # unsupported -> clamped
    assert r._interval_for("NIFTY") == config.DEFAULT_LIVE_INTERVAL

def test_entries_blocked_prevents_open():
    r = _runner()
    with SessionLocal() as s:
        for st in s.scalars(__import__("sqlalchemy").select(InstrumentState)):
            st.entries_blocked = True
        s.commit()
    r._load_enabled(); r._load_intervals(); r._load_entry_blocks()
    for _ in range(200):
        r.tick(); r.provider.advance()
    assert len(r.broker.open_positions()) == 0
```

- [ ] **Step 2: Run to verify it fails**
Run: `.venv/bin/python -m pytest tests/test_engine_loops.py -q`
Expected: FAIL (methods/attrs missing).

- [ ] **Step 3: Implement the decomposition** — edit `runner.py`:

In `__init__`, add after `self.enabled`:
```python
        self.intervals: dict[str, str] = self._load_intervals()
        self.entry_blocks: set[str] = self._load_entry_blocks()
        from app.engine.health import HealthTracker
        self.health = HealthTracker()
        self.position_ticks: dict[str, dict] = {}   # latest marks for open positions (UI feed)
        self._next_scan: dict[str, float] = {}      # key -> earliest epoch we should refetch candles
```

Add loaders + accessors:
```python
    def _load_intervals(self) -> dict[str, str]:
        from app.core.config import normalize_live_interval
        with SessionLocal() as s:
            rows = list(s.scalars(select(InstrumentState)))
            return {r.instrument_key: normalize_live_interval(r.live_interval or "")
                    for r in rows}

    def _load_entry_blocks(self) -> set[str]:
        with SessionLocal() as s:
            return {r.instrument_key for r in s.scalars(select(InstrumentState)) if r.entries_blocked}

    def _interval_for(self, key: str) -> str:
        from app.core.config import normalize_live_interval, DEFAULT_LIVE_INTERVAL
        return normalize_live_interval(self.intervals.get(key, DEFAULT_LIVE_INTERVAL))

    def set_interval(self, key: str, interval: str) -> str:
        from app.core.config import normalize_live_interval
        iv = normalize_live_interval(interval)
        with SessionLocal() as s:
            r = s.get(InstrumentState, key)
            if r:
                r.live_interval = iv
                s.commit()
        self.intervals[key] = iv
        self._next_scan.pop(key, None)   # force a re-scan at the new interval
        log.info(f"live interval set to {iv}", instrument=key)
        return iv

    def set_entries_blocked(self, key: str, blocked: bool) -> None:
        with SessionLocal() as s:
            r = s.get(InstrumentState, key)
            if r:
                r.entries_blocked = blocked
                s.commit()
        self.entry_blocks.add(key) if blocked else self.entry_blocks.discard(key)
        log.info(f"{'BLOCKED' if blocked else 'UNBLOCKED'} new entries", instrument=key)
```

Now split the body of the current `tick()`. Replace the existing `tick()` with three methods + a thin `tick()`:
```python
    # 1) strategy recompute (per-instrument interval)
    def scan_signals(self) -> None:
        s, prov = self.settings, self.provider
        opens = {p.instrument_key: p for p in self.broker.open_positions()}
        for key in list(self.enabled):
            inst = get_instrument(key)
            if not prov.is_tradable_now(inst):
                continue
            try:
                candles = prov.get_candles(inst, self._interval_for(key), s.history_days)
                self.health.record_ok("candle", prov.now())
            except Exception as e:
                self.health.record_fail("candle", str(e), prov.now())
                log.error(f"candles failed: {e}", instrument=key)
                continue
            if len(candles) < s.ema_length + 5:
                continue
            sig = compute_signals(_to_df(candles), ema_length=s.ema_length,
                                  z_length=s.z_length, entry_z=s.entry_z,
                                  slope_lookback=s.slope_lookback)
            latest = to_payload(sig, entry_z=s.entry_z)["latest"]
            if not latest:
                continue
            held = opens.get(key)
            self.state[key] = {
                "instrument": key, "name": inst.name, "segment": inst.segment,
                "interval": self._interval_for(key),
                "time": latest["time"], "close": latest["close"], "ema": latest["ema"],
                "z": latest["z"], "z_prev": latest["z_prev"], "slope": latest["slope"],
                "std": latest["std"], "trend": latest["trend"], "signal": latest["signal"],
                "long_exit": latest["long_exit"], "short_exit": latest["short_exit"],
                "position": held.to_dict() if held else None,
                "has_options": inst.has_options,
                "entries_blocked": key in self.entry_blocks,
            }

    # 2) fast lane: mark open positions, staleness guard, exits
    def mark_and_exit_positions(self) -> None:
        prov = self.provider
        now = prov.now()
        opens = {p.instrument_key: p for p in self.broker.open_positions()}
        if not opens:
            self.position_ticks = {}
            return
        insts = [get_instrument(k) for k in opens]
        try:
            snap = prov.live_snapshot(insts, list(opens.values()))
            self.health.record_ok("quote", now)
        except Exception as e:
            self.health.record_fail("quote", str(e), now)
            log.error(f"position snapshot failed: {e}")
            snap = {}
        from app.engine.health import is_stale
        ticks: dict[str, dict] = {}
        for key, pos in list(opens.items()):
            data = snap.get(key) or {}
            premium = data.get("option_premium")
            spot = data.get("spot")
            stale = premium is None
            if premium is not None:
                self.broker.mark(pos, premium, spot, now=now)
            pos_stale = stale or is_stale(pos.last_mark_time, now, self.settings.max_stale_seconds)
            st = self.state.get(key, {})
            if not pos_stale:
                should, reason = evaluate_exit(
                    pos.direction, pos.stop_price, pos.target_price, premium,
                    st.get("long_exit", False), st.get("short_exit", False))
                if should:
                    self.broker.close_position(pos, premium, reason, now, spot)
                    opens.pop(key, None)
                    if key in self.state:
                        self.state[key]["position"] = None
                    continue
            ticks[key] = {
                "instrument": key, "tradingsymbol": pos.tradingsymbol,
                "option_premium": round(premium, 2) if premium is not None else None,
                "spot": round(spot, 2) if spot else None,
                "unrealized_pnl": pos.to_dict()["unrealized_pnl"],
                "stop_price": round(pos.stop_price, 2), "target_price": round(pos.target_price, 2),
                "stale": pos_stale,
                "stale_age": None if pos.last_mark_time is None
                             else round((now - pos.last_mark_time).total_seconds(), 1),
                "last_mark_time": pos.last_mark_time.isoformat() if pos.last_mark_time else None,
            }
        self.broker.commit()
        self.position_ticks = ticks

    # 3) entries (fresh crossovers, not blocked, not held)
    def process_entries(self) -> None:
        s, prov = self.settings, self.provider
        now = prov.now()
        opens = {p.instrument_key for p in self.broker.open_positions()}
        cands: list[Candidate] = []
        meta: dict[str, tuple] = {}
        for key in list(self.enabled):
            if key in opens or key in self.entry_blocks:
                continue
            st = self.state.get(key)
            if not st or st["signal"] not in ("LONG_ENTRY", "SHORT_ENTRY"):
                continue
            direction = "LONG" if st["signal"] == "LONG_ENTRY" else "SHORT"
            inst = get_instrument(key)
            self._record_signal(now, key, st)
            if not inst.has_options:
                continue
            chain = prov.get_option_chain(inst)
            if not chain:
                log.warn("signal fired but no option chain — skipped", instrument=key)
                continue
            pick = pick_option(chain, direction, s, now)
            self.last_pick[key] = {
                "time": now.isoformat(), "direction": direction, "reason": pick.reason,
                "spot": round(chain.spot, 2), "expiry": chain.expiry.isoformat(),
                "chosen": pick.chosen.to_dict() if pick.chosen else None,
                "candidates": pick.candidates,
            }
            if not pick.chosen:
                log.warn(f"signal fired but {pick.reason}", instrument=key)
                continue
            qty = pick.chosen.lot_size
            charges = compute_charges(inst.segment, "BUY", pick.chosen.ltp, qty)["total"]
            cost = pick.chosen.ltp * qty + charges
            cands.append(Candidate(key, direction, cost))
            meta[key] = (inst, direction, pick, chain)
        if cands:
            alloc = allocate(cands, self.broker.cash())
            if len(alloc.funded) < len(cands):
                log.info(f"capital shortfall — {len(alloc.funded)}/{len(cands)} signals funded by priority")
            for c in alloc.funded:
                inst, direction, pick, chain = meta[c.instrument_key]
                self.broker.open_position(inst, direction, pick.chosen, pick.reason, now, chain.spot)
                if c.instrument_key in self.state:
                    p = self.broker.position_for(c.instrument_key)
                    self.state[c.instrument_key]["position"] = p.to_dict() if p else None
            for c, reason in alloc.skipped:
                log.warn(f"signal dropped — {reason}", instrument=c.instrument_key)

    # combined step — used by mock dry-run and tests (unchanged semantics)
    def tick(self) -> None:
        self.scan_signals()
        self.mark_and_exit_positions()
        self.process_entries()
        self.broker.snapshot(self.provider.now())
        self.tick_count += 1
```
> Note: the old `tick()` marked positions inside the exit pass via per-position `option_ltp`; the new `mark_and_exit_positions()` uses the batched `live_snapshot` (works for both mock and Kite). Mock's `live_snapshot` default returns the same option price `option_ltp` would, so dry-run P&L is unchanged. Keep the imports already at the top of the file (`Candidate`, `allocate`, `compute_charges`, `pick_option`, `evaluate_exit`, `compute_signals`, `to_payload`, `_to_df`).

Also enrich `snapshot_state()` to publish health + position_ticks + intervals:
```python
    def snapshot_state(self) -> dict:
        return {"tick": self.tick_count, "provider": self.provider.name,
                "time": self.provider.now().isoformat(),
                "enabled": sorted(self.enabled), "states": self.state,
                "intervals": {k: self._interval_for(k) for k in self.enabled},
                "health": self.health.as_dict(),
                "position_ticks": self.position_ticks,
                "capital": self.capital_dict()}
```

- [ ] **Step 4: Run to verify it passes**
Run: `.venv/bin/python -m pytest tests/test_engine_loops.py -q`
Expected: PASS.

- [ ] **Step 5: Run the FULL suite + dryrun (parity guard)**
Run: `.venv/bin/python -m pytest -q && .venv/bin/python scripts/dryrun.py 700`
Expected: all tests PASS; dryrun ledger diff `0.0`.

- [ ] **Step 6: Commit**
```bash
git add paper-trader/backend/app/engine/runner.py paper-trader/backend/tests/test_engine_loops.py
git commit -m "feat(engine): decompose tick into scan/mark-exit/entries; per-instrument intervals + health"
```

---

### Task T7: Two async loops in the runner (risk lane vs signal lane)

**Files:**
- Modify: `paper-trader/backend/app/engine/runner.py`
- Test: `paper-trader/backend/tests/test_engine_loops.py` (append, async)

**Interfaces — Produces:** `async run_risk_loop()`, `async run_signal_loop()`, shared `self._lock: asyncio.Lock`, `self.on_position_ticks` callback. `run()` is kept as an alias that runs the signal loop (back-compat for any caller). Next-candle gating via `_due_for_scan(key, now) -> bool`.

- [ ] **Step 1: Write the failing test** (drive one iteration of each loop with the mock; assert marks + state produced, lock present)
```python
import asyncio

def test_async_loops_one_iteration(monkeypatch):
    from app.db.session import init_db
    from app.engine.runner import EngineRunner
    init_db(reset=True)
    r = EngineRunner()
    assert hasattr(r, "run_risk_loop") and hasattr(r, "run_signal_loop")
    assert r._lock is not None
    # prime some signals, open at least one position deterministically
    for _ in range(160):
        r.tick(); r.provider.advance()
    async def drive():
        await r._risk_iteration()    # one fast-lane pass
        await r._signal_iteration()  # one slow-lane pass
    asyncio.run(drive())
    # position ticks dict exists (possibly empty) and ledger stays valid
    assert isinstance(r.position_ticks, dict)
    assert r.broker.reconcile()["diff"] == 0.0
```

- [ ] **Step 2: Run to verify it fails**
Run: `.venv/bin/python -m pytest tests/test_engine_loops.py -q`
Expected: FAIL (`_risk_iteration`/loops missing).

- [ ] **Step 3: Implement the loops** — in `runner.py`:
In `__init__` add:
```python
        self._lock = asyncio.Lock()
        self.on_update = None          # async cb(state) for signal-lane snapshots
        self.on_position_ticks = None  # async cb(ticks) for fast-lane marks
        self._scan_cursor = 0
```
Add gating + single-iteration helpers + loops:
```python
    def _due_for_scan(self, key: str, now) -> bool:
        """Refetch candles only when a new completed candle could exist."""
        import datetime as _dt
        nxt = self._next_scan.get(key)
        epoch = now.timestamp() if isinstance(now, _dt.datetime) else float(now)
        if nxt is None or epoch >= nxt:
            minutes = {"5minute": 5, "15minute": 15, "30minute": 30, "60minute": 60}.get(
                self._interval_for(key), 15)
            self._next_scan[key] = epoch + minutes * 60
            return True
        return False

    async def _risk_iteration(self) -> None:
        async with self._lock:
            self.mark_and_exit_positions()
        if self.on_position_ticks:
            try:
                await self.on_position_ticks(self.position_ticks)
            except Exception:
                pass

    async def _signal_iteration(self) -> None:
        async with self._lock:
            self.scan_signals()
            self.process_entries()
            self.broker.snapshot(self.provider.now())
            self.tick_count += 1
        if self.on_update:
            try:
                await self.on_update(self.snapshot_state())
            except Exception:
                pass

    async def run_risk_loop(self) -> None:
        self.running = True
        while self.running:
            try:
                await self._risk_iteration()
            except Exception as e:
                log.error(f"risk loop error: {e}")
            await asyncio.sleep(self.settings.position_loop_seconds)

    async def run_signal_loop(self) -> None:
        log.info(f"engine started — provider={self.provider.name}, "
                 f"intervals(default={get_settings().__class__ and self._interval_for('') if False else 'per-instrument'}), "
                 f"enabled={sorted(self.enabled)}")
        while self.running:
            try:
                if self.provider.name == "mock":
                    await self._signal_iteration()
                    if not self.provider.advance():
                        await asyncio.sleep(5); continue
                    await asyncio.sleep(self.settings.mock_tick_seconds)
                else:
                    any_open = any(self.provider.is_tradable_now(get_instrument(k))
                                   for k in self.enabled)
                    if not any_open:
                        if not self._idle_logged:
                            log.info("all enabled markets closed — engine idling until next session")
                            self._idle_logged = True
                        await asyncio.sleep(60)
                    else:
                        self._idle_logged = False
                        await self._signal_iteration()
                        await asyncio.sleep(self.settings.signal_loop_seconds)
            except Exception as e:
                log.error(f"signal loop error: {e}")
                await asyncio.sleep(self.settings.signal_loop_seconds)

    async def run(self) -> None:   # back-compat alias
        self.running = True
        await self.run_signal_loop()
```
> Simplify the log line in `run_signal_loop` to: `log.info(f"engine started — provider={self.provider.name}, enabled={sorted(self.enabled)}")` (the conditional above is illustrative; use the simple form).

- [ ] **Step 4: Run to verify it passes**
Run: `.venv/bin/python -m pytest tests/test_engine_loops.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add paper-trader/backend/app/engine/runner.py paper-trader/backend/tests/test_engine_loops.py
git commit -m "feat(engine): split risk/signal async loops with lock + next-candle gating"
```

---

### Task T8: Wire the split loops into `main.py`

**Files:**
- Modify: `paper-trader/backend/app/main.py`
- Test: manual (covered by route tests in Phase 4 + final app run).

- [ ] **Step 1: Implement** — replace the body of `lifespan` after `runner.on_update = on_update`:
```python
    async def on_update(state: dict) -> None:
        await manager.broadcast({"type": "state", "data": state})

    async def on_position_ticks(ticks: dict) -> None:
        await manager.broadcast({"type": "position_ticks", "data": ticks})

    runner.on_update = on_update
    runner.on_position_ticks = on_position_ticks
    log.subscribe(lambda entry: manager.push({"type": "log", "data": entry}))

    runner.running = True
    signal_task = asyncio.create_task(runner.run_signal_loop())
    risk_task = asyncio.create_task(runner.run_risk_loop())
    log.info("backend ready — open the dashboard")
    try:
        yield
    finally:
        runner.stop()
        signal_task.cancel()
        risk_task.cancel()
```
Remove the old `live_quotes` task + its `live_task` references entirely (the risk loop now feeds position ticks).

- [ ] **Step 2: Smoke-run the backend** (mock provider; no Kite needed)
Run: `cd paper-trader/backend && PT_PROVIDER=mock .venv/bin/uvicorn app.main:app --port 8091 &` then `sleep 4 && curl -s localhost:8091/api/health && curl -s localhost:8091/api/status | head -c 400; kill %1`
Expected: `{"ok":true}` and a status JSON containing `"provider":"mock"`.

- [ ] **Step 3: Commit**
```bash
git add paper-trader/backend/app/main.py
git commit -m "feat(engine): run split risk + signal loops; drop separate live_quotes task"
```

**PHASE 3 GATE:** full `pytest -q` green; `dryrun.py 700` diff 0.0; backend boots on mock. Checkpoint.

---

# PHASE 4 — APIs + WS payloads (F1–F3, F5, F6, F8 backend surface)

### Task T9: Manual paper open in the broker (validated)

**Files:**
- Modify: `paper-trader/backend/app/engine/broker.py`
- Test: `paper-trader/backend/tests/test_manual_broker.py` (append)

**Interfaces — Produces:** `PaperBroker.manual_open(inst, direction, chain, settings, now) -> tuple[Position | None, str]` returning `(position, reason)`. Rejects: insufficient cash, no priceable contract, already holding.

- [ ] **Step 1: Write the failing test**
```python
def test_manual_open_respects_capital_and_one_position():
    from app.core.config import get_settings
    b = _broker()
    inst = get_instrument("NIFTY")
    chain = b.provider.get_option_chain(inst)
    pos, reason = b.manual_open(inst, "LONG", chain, get_settings(), b.provider.now())
    assert pos is not None, reason
    # second manual open on same instrument is rejected (no pyramiding)
    pos2, reason2 = b.manual_open(inst, "LONG", chain, get_settings(), b.provider.now())
    assert pos2 is None and "already" in reason2.lower()

def test_manual_open_rejects_when_no_cash():
    from app.core.config import get_settings
    b = _broker()
    cap = b.capital(); cap.cash = 1.0; b.commit()
    inst = get_instrument("NIFTY")
    chain = b.provider.get_option_chain(inst)
    pos, reason = b.manual_open(inst, "LONG", chain, get_settings(), b.provider.now())
    assert pos is None and "cash" in reason.lower()
```

- [ ] **Step 2: Run to verify it fails**
Run: `.venv/bin/python -m pytest tests/test_manual_broker.py -q`
Expected: FAIL (`manual_open` missing).

- [ ] **Step 3: Implement** — add to `broker.py` (reuse the existing picker for contract choice):
```python
    def manual_open(self, inst, direction: str, chain, settings, now):
        """Owner-initiated paper entry. Same safety as the engine: 1 lot, one
        position per instrument, capital-checked, paper-only. Returns (pos, reason)."""
        from app.options.picker import pick_option
        if self.position_for(inst.key) is not None:
            return None, "already holding a position for this instrument"
        if chain is None:
            return None, "no option chain available to price a contract"
        pick = pick_option(chain, direction, settings, now)
        if not pick.chosen:
            return None, f"no priceable contract: {pick.reason}"
        qty = pick.chosen.lot_size
        from app.engine.charges import compute_charges
        charges = compute_charges(inst.segment, "BUY", pick.chosen.ltp, qty)["total"]
        cost = pick.chosen.ltp * qty + charges
        if cost > self.cash():
            return None, f"insufficient cash: need ₹{cost:,.0f}, have ₹{self.cash():,.0f}"
        pos = self.open_position(inst, direction, pick.chosen,
                                 f"MANUAL {direction}", now, chain.spot)
        log.info(f"MANUAL OPEN {direction} {pos.tradingsymbol}", instrument=inst.key,
                 event="MANUAL_OPEN", manual=True)
        return pos, "ok"
```

- [ ] **Step 4: Run to verify it passes**
Run: `.venv/bin/python -m pytest tests/test_manual_broker.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add paper-trader/backend/app/engine/broker.py paper-trader/backend/tests/test_manual_broker.py
git commit -m "feat(broker): validated manual paper open (1 lot, capital + one-position checks)"
```

---

### Task T10: New REST + enriched WS endpoints

**Files:**
- Modify: `paper-trader/backend/app/api/routes.py`
- Test: `paper-trader/backend/tests/test_routes_manual.py`

**Interfaces — Produces** (all under existing `router`):
- `GET /api/signals` — lightweight list rows from `runner.state` + health (no candle fetch).
- `GET /api/positions` — rich open-position cockpit rows (+ stale/health).
- `GET /api/health` already exists; add `GET /api/provider-health` → `runner.health.as_dict()`.
- `POST /api/instruments/{key}/interval` body `{interval}` → `runner.set_interval`.
- `POST /api/instruments/{key}/block-entries` body `{blocked}` → `runner.set_entries_blocked`.
- `POST /api/positions/{key}/close` → paper-close now at latest LTP (`MANUAL_CLOSE`).
- `POST /api/positions/manual-open` body `{key, direction}` → `runner.broker.manual_open`.
- `GET /api/candles/{key}?interval=` — default to the instrument's live interval.

> Tests use FastAPI `TestClient`. The app lifespan starts the engine; to keep tests fast and deterministic we construct the runner directly and attach it to `app.state` without the background loops.

- [ ] **Step 1: Write the failing test**
```python
# tests/test_routes_manual.py
from fastapi.testclient import TestClient
from app.db.session import init_db
from app.engine.runner import EngineRunner
from app.main import app

def _client():
    init_db(reset=True)
    r = EngineRunner()
    # warm a little state so /api/signals has rows
    for _ in range(160):
        r.tick(); r.provider.advance()
    app.state.runner = r
    return TestClient(app), r

def test_signals_list_is_lightweight():
    c, _ = _client()
    res = c.get("/api/signals").json()
    assert "instruments" in res and isinstance(res["instruments"], list)
    if res["instruments"]:
        row = res["instruments"][0]
        for k in ("key", "signal", "interval", "has_position", "has_options", "stale"):
            assert k in row

def test_set_interval_route():
    c, r = _client()
    res = c.post("/api/instruments/NIFTY/interval", json={"interval": "60minute"}).json()
    assert res["interval"] == "60minute"
    assert r._interval_for("NIFTY") == "60minute"

def test_block_entries_route():
    c, r = _client()
    c.post("/api/instruments/NIFTY/block-entries", json={"blocked": True})
    assert "NIFTY" in r.entry_blocks

def test_manual_open_then_close():
    c, r = _client()
    op = c.post("/api/positions/manual-open", json={"key": "NIFTY", "direction": "LONG"}).json()
    assert op.get("opened") is True, op
    cl = c.post("/api/positions/NIFTY/close").json()
    assert cl.get("closed") is True, cl
    assert r.broker.position_for("NIFTY") is None

def test_provider_health_route():
    c, _ = _client()
    h = c.get("/api/provider-health").json()
    assert "quote" in h and "candle" in h
```

- [ ] **Step 2: Run to verify it fails**
Run: `.venv/bin/python -m pytest tests/test_routes_manual.py -q`
Expected: FAIL (routes missing).

- [ ] **Step 3: Implement the routes** — append to `routes.py`:
```python
@router.get("/api/signals")
def signals(request: Request):
    """Lightweight signal-first list. Pure read of in-memory engine state +
    health — NEVER fetches candles (rows must stay cheap)."""
    r = _runner(request)
    h = r.health.as_dict()
    now = r.provider.now()
    from app.engine.health import is_stale
    out = []
    for inst in all_instruments():
        st = r.state.get(inst.key, {})
        pos = st.get("position")
        out.append({
            "key": inst.key, "name": inst.name, "segment": inst.segment,
            "enabled": inst.key in r.enabled,
            "interval": r._interval_for(inst.key),
            "signal": st.get("signal", "NONE"), "trend": st.get("trend"),
            "z": st.get("z"), "close": st.get("close"),
            "last_candle_time": st.get("time"),
            "has_position": pos is not None,
            "has_options": inst.has_options,
            "entries_blocked": inst.key in r.entry_blocks,
            "stale": is_stale(None, now, 0) if not st else False,
            "quote_health": h.get("quote"), "candle_health": h.get("candle"),
        })
    return {"instruments": out, "health": h}


@router.get("/api/positions")
def positions(request: Request):
    r = _runner(request)
    ticks = r.position_ticks
    out = []
    for p in r.broker.open_positions():
        d = p.to_dict()
        t = ticks.get(p.instrument_key, {})
        d["live_premium"] = t.get("option_premium")
        d["live_spot"] = t.get("spot")
        d["stale"] = t.get("stale", True)
        d["stale_age"] = t.get("stale_age")
        d["dist_to_stop"] = round((d["last_premium"] - d["stop_price"]), 2)
        d["dist_to_target"] = round((d["target_price"] - d["last_premium"]), 2)
        out.append(d)
    return {"positions": out, "capital": r.capital_dict()}


@router.get("/api/provider-health")
def provider_health(request: Request):
    return _runner(request).health.as_dict()


class IntervalBody(BaseModel):
    interval: str

@router.post("/api/instruments/{key}/interval")
def set_interval(key: str, body: IntervalBody, request: Request):
    iv = _runner(request).set_interval(key, body.interval)
    return {"key": key, "interval": iv}


class BlockBody(BaseModel):
    blocked: bool

@router.post("/api/instruments/{key}/block-entries")
def block_entries(key: str, body: BlockBody, request: Request):
    _runner(request).set_entries_blocked(key, body.blocked)
    return {"key": key, "entries_blocked": body.blocked}


@router.post("/api/positions/{key}/close")
def close_position(key: str, request: Request):
    r = _runner(request)
    pos = r.broker.position_for(key)
    if not pos:
        return {"error": "no open position for this instrument"}
    inst = get_instrument(key)
    premium = r.provider.option_ltp(inst, pos.tradingsymbol, pos.strike, pos.expiry, pos.option_type)
    if premium is None:
        premium = pos.last_premium or pos.entry_premium
    now = r.provider.now()
    r.broker.close_position(pos, premium, "MANUAL_CLOSE", now, r.provider.get_ltp(inst) or pos.last_spot)
    from app.core.logging import log
    log.info(f"MANUAL CLOSE {pos.tradingsymbol} @ {premium:.2f}", instrument=key,
             event="MANUAL_CLOSE", manual=True)
    if key in r.state:
        r.state[key]["position"] = None
    return {"closed": True, "key": key, "exit_premium": round(premium, 2)}


class ManualOpenBody(BaseModel):
    key: str
    direction: str   # "LONG" | "SHORT"

@router.post("/api/positions/manual-open")
def manual_open(body: ManualOpenBody, request: Request):
    r = _runner(request)
    if body.direction not in ("LONG", "SHORT"):
        return {"error": "direction must be LONG or SHORT"}
    inst = get_instrument(body.key)
    if not inst.has_options:
        return {"error": "instrument has no listed options (tracking only)"}
    chain = r.provider.get_option_chain(inst)
    pos, reason = r.broker.manual_open(inst, body.direction, chain, settings, r.provider.now())
    if pos is None:
        return {"error": reason}
    if body.key in r.state:
        r.state[body.key]["position"] = pos.to_dict()
    return {"opened": True, "key": body.key, "tradingsymbol": pos.tradingsymbol}
```
Update the existing `candles` route to use the per-instrument interval (optional override):
```python
@router.get("/api/candles/{key}")
def candles(key: str, request: Request, interval: str | None = None):
    r = _runner(request)
    inst = get_instrument(key)
    iv = interval or r._interval_for(key)
    try:
        cs = r.provider.get_candles(inst, iv, settings.history_days)
    except Exception:
        cs = []
    ...
```
(keep the rest of `candles` unchanged; pass `iv` into `get_candles`).

- [ ] **Step 4: Run to verify it passes**
Run: `.venv/bin/python -m pytest tests/test_routes_manual.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add paper-trader/backend/app/api/routes.py paper-trader/backend/tests/test_routes_manual.py
git commit -m "feat(api): signals list, positions cockpit, health, interval/block, manual open/close"
```

**PHASE 4 GATE:** full `pytest -q` green. Checkpoint.

---

# PHASE 5 — Backtest cache + interval promotion (F7, F6)

### Task T11: Backtest cache module + reuse in sweep

**Files:**
- Create: `paper-trader/backend/app/backtest/cache.py`
- Modify: `paper-trader/backend/app/backtest/sweep.py`
- Test: `paper-trader/backend/tests/test_backtest_cache.py`

**Interfaces — Produces:**
- `cache.SCHEMA_VERSION: int = 1`
- `cache.params_signature(capital: float, *, ema_length=50, z_length=50, entry_z=1.0, slope_lookback=5) -> str`
- `cache.find_reusable(session, key, interval, params_hash, last_candle_ts) -> BacktestResult | None`

- [ ] **Step 1: Write the failing test**
```python
# tests/test_backtest_cache.py
from app.db.session import init_db, SessionLocal
from app.backtest import cache, sweep
from app.db.models import BacktestResult, BacktestRun
from app.providers.mock import MockProvider
from app.core.instruments import get_instrument

def test_params_signature_stable_and_sensitive():
    a = cache.params_signature(50000)
    b = cache.params_signature(50000)
    c = cache.params_signature(60000)
    assert a == b and a != c

def test_second_sweep_reuses_cache():
    init_db(reset=True)
    prov = MockProvider()
    # run 1
    rid1 = sweep.start_sweep(scope="liquid", intervals=["15minute"], capital=50000, provider=prov)
    sweep._join()  # test helper: block until the worker thread finishes
    # run 2 (same data, same params) should mark results from_cache
    rid2 = sweep.start_sweep(scope="liquid", intervals=["15minute"], capital=50000, provider=prov)
    sweep._join()
    with SessionLocal() as s:
        from sqlalchemy import select
        rows2 = list(s.scalars(select(BacktestResult).where(BacktestResult.run_id == rid2)))
    assert rows2 and any(r.from_cache for r in rows2 if not r.error)
```

- [ ] **Step 2: Run to verify it fails**
Run: `.venv/bin/python -m pytest tests/test_backtest_cache.py -q`
Expected: FAIL (`cache` module / `_join` missing).

- [ ] **Step 3: Implement `cache.py`**
```python
"""
Reusable backtest cache. A sweep result is reusable when the *content* it would
recompute is identical: same instrument, interval, strategy/params signature,
schema version, and the same last completed candle. Then we copy the stored
metrics into the new run instead of recomputing. SQLite is the source of truth.
"""
from __future__ import annotations

import hashlib

from sqlalchemy import select

from app.db.models import BacktestResult

SCHEMA_VERSION = 1


def params_signature(capital: float, *, ema_length: int = 50, z_length: int = 50,
                     entry_z: float = 1.0, slope_lookback: int = 5) -> str:
    raw = f"v{SCHEMA_VERSION}|cap={capital}|ema={ema_length}|z={z_length}|ez={entry_z}|sl={slope_lookback}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def find_reusable(session, key: str, interval: str, params_hash: str,
                  last_candle_ts: int) -> BacktestResult | None:
    """Most recent successful result with identical content key, if any."""
    if last_candle_ts <= 0:
        return None
    q = (select(BacktestResult)
         .where(BacktestResult.instrument_key == key,
                BacktestResult.interval == interval,
                BacktestResult.params_hash == params_hash,
                BacktestResult.last_candle_ts == last_candle_ts,
                BacktestResult.schema_version == SCHEMA_VERSION,
                BacktestResult.error == "")
         .order_by(BacktestResult.id.desc()))
    return session.scalars(q).first()
```

- [ ] **Step 4: Wire cache into `sweep._one` / `_store`** — edit `sweep.py`:
Add a test-friendly join handle. At module scope:
```python
_worker: "threading.Thread | None" = None

def _join() -> None:
    """Test helper: block until the running sweep thread completes."""
    t = _worker
    if t is not None:
        t.join()
```
In `start_sweep`, capture the thread:
```python
        global _worker
        t = threading.Thread(target=_run, args=(run_id, provider, specs, intervals, capital), daemon=True)
        _worker = t
        t.start()
        return run_id
```
Rewrite `_one` to use the cache:
```python
def _one(run_id, provider, inst, interval, capital) -> None:
    from app.backtest import cache
    days = MAX_DAYS.get(interval, 200)
    try:
        candles = provider.get_candles(inst, interval, days)
    except Exception as e:
        return _store(run_id, inst, interval, None, [], 0, error=f"candles: {e}")
    if len(candles) < MIN_BARS:
        return _store(run_id, inst, interval, None, [], len(candles), error="insufficient history")
    last_ts = int(candles[-1].ts.timestamp())
    phash = cache.params_signature(capital)
    with SessionLocal() as s:
        hit = cache.find_reusable(s, inst.key, interval, phash, last_ts)
        if hit is not None:
            _copy_from_cache(s, run_id, hit)
            return
    trades, m = simulate(candles, inst, interval, capital=capital)
    _store(run_id, inst, interval, m, trades, len(candles),
           params_hash=phash, last_candle_ts=last_ts)
```
Add `_copy_from_cache` and extend `_store` signature:
```python
def _copy_from_cache(session, run_id, src) -> None:
    import datetime as dt
    session.add(BacktestResult(
        run_id=run_id, instrument_key=src.instrument_key, name=src.name,
        segment=src.segment, interval=src.interval, trades=src.trades, wins=src.wins,
        win_rate=src.win_rate, profit_factor=src.profit_factor,
        max_drawdown_pct=src.max_drawdown_pct, return_pct=src.return_pct,
        net_pnl=src.net_pnl, gross_pnl=src.gross_pnl, charges=src.charges,
        expectancy=src.expectancy, cagr=src.cagr, bars=src.bars,
        curve_json=src.curve_json, trades_json=src.trades_json,
        params_hash=src.params_hash, last_candle_ts=src.last_candle_ts,
        schema_version=src.schema_version, from_cache=True, computed_at=dt.datetime.now()))
    session.commit()
```
Update `_store` to persist the cache metadata (add params/last_ts kwargs, set `from_cache=False`, `computed_at=now`, `schema_version=cache.SCHEMA_VERSION`):
```python
def _store(run_id, inst, interval, m, trades, bars, error="",
           params_hash="", last_candle_ts=0) -> None:
    import datetime as dt
    from app.backtest import cache
    seg = backtest_charge_segment(inst)
    with SessionLocal() as s:
        common = dict(run_id=run_id, instrument_key=inst.key, name=inst.name,
                      segment=seg, interval=interval, bars=bars,
                      params_hash=params_hash, last_candle_ts=last_candle_ts,
                      schema_version=cache.SCHEMA_VERSION, from_cache=False,
                      computed_at=dt.datetime.now())
        if m is None:
            s.add(BacktestResult(error=error, **common))
        else:
            s.add(BacktestResult(
                trades=m.trades, wins=m.wins, win_rate=m.win_rate,
                profit_factor=m.profit_factor, max_drawdown_pct=m.max_drawdown_pct,
                return_pct=m.return_pct, net_pnl=m.net_pnl, gross_pnl=m.gross_pnl,
                charges=m.charges, expectancy=m.expectancy, cagr=m.cagr,
                curve_json=json.dumps(m.equity_curve),
                trades_json=json.dumps([t.to_dict() for t in trades]), **common))
        s.commit()
```

- [ ] **Step 5: Run to verify it passes**
Run: `.venv/bin/python -m pytest tests/test_backtest_cache.py tests/test_backtest.py -q`
Expected: PASS (new cache test + existing backtest test).

- [ ] **Step 6: Commit**
```bash
git add paper-trader/backend/app/backtest/cache.py paper-trader/backend/app/backtest/sweep.py paper-trader/backend/tests/test_backtest_cache.py
git commit -m "feat(backtest): content-addressed result cache (reuse compute when unchanged)"
```

---

### Task T12: Carry backtest interval into live on promotion

**Files:**
- Modify: `paper-trader/backend/app/core/universe_resolver.py`, `paper-trader/backend/app/api/routes.py`
- Test: `paper-trader/backend/tests/test_routes_manual.py` (append)

**Interfaces — Produces:** `add_instrument(key, provider, on_home=True, interval=None) -> dict` — when `interval` is a supported live interval, store it on `InstrumentState.live_interval`; else fall back to default and include `"interval_warning"` in the result. `POST /api/portfolio/add` accepts optional `interval`.

- [ ] **Step 1: Write the failing test** (append)
```python
def test_promote_carries_supported_interval():
    c, r = _client()
    res = c.post("/api/portfolio/add", json={"key": "NIFTY", "interval": "30minute"}).json()
    assert "error" not in res
    assert r._interval_for("NIFTY") == "30minute" or \
           __import__("app.db.session", fromlist=["SessionLocal"])  # interval persisted

def test_promote_unsupported_interval_falls_back_with_warning():
    c, r = _client()
    res = c.post("/api/portfolio/add", json={"key": "NIFTY", "interval": "minute"}).json()
    assert res.get("interval_warning")
```

- [ ] **Step 2: Run to verify it fails**
Run: `.venv/bin/python -m pytest tests/test_routes_manual.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement** — `universe_resolver.add_instrument`:
```python
def add_instrument(key: str, provider, on_home: bool = True, interval: str | None = None) -> dict:
    spec = resolve_spec(key, provider)
    if spec is None:
        return {"error": f"could not resolve instrument '{key}'"}
    from app.core.config import LIVE_INTERVALS, normalize_live_interval
    warning = None
    iv = None
    if interval:
        iv = normalize_live_interval(interval)
        if interval not in LIVE_INTERVALS:
            warning = f"{interval} is not a live timeframe; using {iv}"
    with SessionLocal() as s:
        row = s.get(UniverseInstrument, key)
        if row is None:
            s.add(UniverseInstrument(... unchanged ...))
        else:
            row.active = True; row.on_home = on_home
        st = s.get(InstrumentState, key)
        if st is None:
            st = InstrumentState(instrument_key=key, enabled=True)
            s.add(st)
        else:
            st.enabled = True
        if iv:
            st.live_interval = iv
        s.commit()
    reg.load_universe()
    out = {"key": key, "added": True, "has_options": spec.has_options,
           "name": spec.name, "segment": spec.segment}
    if iv:
        out["interval"] = iv
    if warning:
        out["interval_warning"] = warning
    return out
```
In `routes.py`, extend the add model + route + sync the runner's interval cache:
```python
class AddInstrument(BaseModel):
    key: str
    on_home: bool = True
    interval: str | None = None

@router.post("/api/portfolio/add")
def portfolio_add(body: AddInstrument, request: Request):
    from app.core import universe_resolver
    r = _runner(request)
    res = universe_resolver.add_instrument(body.key, r.provider, on_home=body.on_home,
                                           interval=body.interval)
    if "error" not in res:
        r.enabled.add(body.key)
        r.intervals[body.key] = res.get("interval", r.intervals.get(body.key, "15minute"))
    return res
```

- [ ] **Step 4: Run to verify it passes**
Run: `.venv/bin/python -m pytest tests/test_routes_manual.py -q`
Expected: PASS.

- [ ] **Step 5: Surface `from_cache` in backtest results UI feed** — verify `BacktestResult.summary()` already includes `from_cache` (added in T1); no `backtest_routes.py` change needed beyond confirming it flows through `results()`/`result_detail()`. Add a quick assertion test if desired.

- [ ] **Step 6: Commit**
```bash
git add paper-trader/backend/app/core/universe_resolver.py paper-trader/backend/app/api/routes.py paper-trader/backend/tests/test_routes_manual.py
git commit -m "feat(api): carry backtest interval into live on promote (safe fallback + warning)"
```

**PHASE 5 GATE:** full `pytest -q` green; `scripts/backtest_smoke.py` passes. Checkpoint.

---

# PHASE 6 — Frontend (F1, F2, F3, F5, F6, F8 UI)

> No frontend test runner exists; verification per task is `npm run typecheck` (added below) + `npm run build`. A final manual pass runs in Phase 7.

### Task T13: Add typecheck script + types + API client + LiveContext

**Files:**
- Modify: `paper-trader/frontend/package.json`, `src/lib/types.ts`, `src/lib/api.ts`, `src/state/LiveContext.tsx`

- [ ] **Step 1:** Add to `package.json` scripts:
```json
    "build": "vite build",
    "typecheck": "tsc --noEmit",
    "preview": "vite preview --port 5173"
```

- [ ] **Step 2:** Extend `src/lib/types.ts`:
```typescript
export interface SignalRow {
  key: string; name: string; segment: string; enabled: boolean
  interval: string; signal: string; trend: string | null; z: number | null
  close: number | null; last_candle_time: number | null
  has_position: boolean; has_options: boolean; entries_blocked: boolean; stale: boolean
}
export interface PositionRow extends PositionDTO {
  live_premium: number | null; live_spot: number | null
  stale: boolean; stale_age: number | null; dist_to_stop: number; dist_to_target: number
}
export interface CatHealth { last_ok: string | null; consecutive_failures: number; last_error: string }
export interface ProviderHealth { quote: CatHealth; candle: CatHealth }
export interface PositionTick {
  instrument: string; tradingsymbol: string; option_premium: number | null; spot: number | null
  unrealized_pnl: number; stop_price: number; target_price: number
  stale: boolean; stale_age: number | null; last_mark_time: string | null
}
```
Add to `LiveState`: `intervals?: Record<string, string>; health?: ProviderHealth; position_ticks?: Record<string, PositionTick>`.

- [ ] **Step 3:** Extend `src/lib/api.ts`:
```typescript
export const getSignals = () => j('/api/signals')
export const getPositions = () => j('/api/positions')
export const getProviderHealth = () => j('/api/provider-health')
export const setInterval_ = (key: string, interval: string) =>
  post(`/api/instruments/${key}/interval`, { interval })
export const blockEntries = (key: string, blocked: boolean) =>
  post(`/api/instruments/${key}/block-entries`, { blocked })
export const closePosition = (key: string) => post(`/api/positions/${key}/close`, {})
export const manualOpen = (key: string, direction: string) =>
  post('/api/positions/manual-open', { key, direction })
```
Update `addToPortfolio` to accept interval:
```typescript
export const addToPortfolio = (key: string, on_home = true, interval?: string) =>
  post('/api/portfolio/add', { key, on_home, interval })
```

- [ ] **Step 4:** `src/state/LiveContext.tsx` — handle `position_ticks` and expose health. Add state `positionTicks` + `health`; in `onmessage`:
```typescript
        else if (m.type === 'position_ticks') setPositionTicks(m.data || {})
```
Pull `health`/`intervals`/`position_ticks` off the `state` message too (they ride inside the snapshot). Add `positionTicks`, `health` to the context value + `Ctx` interface, default `{}`/`null`. Keep `liveTicks` for back-compat but it is no longer broadcast.

- [ ] **Step 5: Verify**
Run: `cd paper-trader/frontend && npm install && npm run typecheck`
Expected: no type errors.

- [ ] **Step 6: Commit**
```bash
git add paper-trader/frontend/package.json paper-trader/frontend/src/lib/types.ts paper-trader/frontend/src/lib/api.ts paper-trader/frontend/src/state/LiveContext.tsx
git commit -m "feat(fe): typecheck script, cockpit DTOs, new API client calls, position_ticks in LiveContext"
```

---

### Task T14: Chartless InstrumentTile (remove always-on chart)

**Files:** Modify `src/components/InstrumentTile.tsx`

- [ ] **Step 1:** Remove the chart + its data-fetching `useEffect`s and the SPOT/OPT toggle. The tile becomes a click-to-expand summary card: name + segment, signal badge, position/invested/unrealized, tradingsymbol line, and the z/slope/px stats row. Keep the `onExpand(key)` button so clicking opens the detail modal (which still has the chart). Drop imports of `PriceChart`, `getCandles`, `getOptionCandles`, `liveSeries`. Keep `liveTick` prop optional but only use it to refresh the numeric `unrealized`/price text if present (no chart).

- [ ] **Step 2: Verify**
Run: `cd paper-trader/frontend && npm run typecheck`
Expected: no type errors (remove now-unused vars to satisfy `noUnusedLocals` if enabled in tsconfig).

- [ ] **Step 3: Commit**
```bash
git add paper-trader/frontend/src/components/InstrumentTile.tsx
git commit -m "feat(fe): chartless instrument tile — charts only in detail view"
```

---

### Task T15: Signal-first list view (replace Monitor tile grid)

**Files:** Modify `src/views/Monitor.tsx` (keep its `Expanded` detail modal export — HomeView imports it)

- [ ] **Step 1:** Rebuild the `Monitor` default export as a **table** driven by `useLive().state` (no per-row fetch). Columns: Instrument (name+segment), Interval (selector — see T18), Enabled, Signal, Trend/z, Last candle (time), Position?, Options?, Stale/health, Error. Add a filter bar (client-side `useState`): Active positions · Signals now · No signal · Stale/error · Options-tradable · Enabled/disabled. Build rows from `state.states` merged with `getSignals()` (polled every 4s for health/stale + instruments not yet in `states`). Each row is a `<tr onClick={() => setExpanded(key)}>`; keep `{expanded && <Expanded .../>}` at the bottom (charts lazy-load there). Do **not** call `getCandles` per row.
Representative row skeleton:
```tsx
const rows = useMemo(() => buildRows(state?.states, signals, health), [state, signals, health])
// filter chips toggle booleans; apply before render
<table className="w-full text-xs"> … <tbody>{view.map(row => (
  <tr key={row.key} onClick={() => setExpanded(row.key)} className="cursor-pointer hover:bg-panel2/50">
    <td>{row.name} <span className="badge">{row.segment}</span></td>
    <td><IntervalSelect k={row.key} value={row.interval} /></td>
    <td><span className={signalStyle(row.signal)}>{row.signal}</span></td>
    <td className="tabular-nums">{num(row.z)}</td>
    <td>{row.has_position ? '●' : '—'}</td>
    <td>{row.has_options ? 'yes' : 'track'}</td>
    <td>{row.stale ? <span className="text-amber-400">stale</span> : 'live'}</td>
  </tr>))}</tbody></table>
```
Keep the enable/disable control (a toggle in the Enabled column, calling `toggleInstrument`).

- [ ] **Step 2: Verify**
Run: `cd paper-trader/frontend && npm run typecheck && npm run build`
Expected: builds clean.

- [ ] **Step 3: Commit**
```bash
git add paper-trader/frontend/src/views/Monitor.tsx
git commit -m "feat(fe): signal-first list view with filters; rows never fetch charts"
```

---

### Task T16: Detail modal uses per-instrument interval

**Files:** Modify `src/views/Monitor.tsx` (`Expanded` component)

- [ ] **Step 1:** `Expanded` already lazy-loads `getCandles(k)` + opens `/ws/instrument/{k}`. Pass the instrument interval through: `getCandles(k)` now defaults server-side to the instrument's live interval (T10), so no change is required for correctness, but add the interval label to the modal header (`st?.interval`) and ensure the option chart only renders when `pos` exists (already the case). Confirm "recent instrument logs" panel: add a small `<LogStream>`-filtered list for the instrument key if cheap, else defer (note it as deferred in the final summary).

- [ ] **Step 2: Verify** `npm run typecheck`.

- [ ] **Step 3: Commit**
```bash
git add paper-trader/frontend/src/views/Monitor.tsx
git commit -m "feat(fe): detail modal labels per-instrument interval"
```

---

### Task T17: Active Positions page (cockpit + manual controls)

**Files:** Create `src/views/ActivePositionsView.tsx`; modify `src/App.tsx`, `src/components/TopBar.tsx`

- [ ] **Step 1:** Add the tab. In `App.tsx` `TABS`, insert after `home`:
```tsx
  ['positions', 'Active Positions'],
```
and render `{tab === 'positions' && <ActivePositionsView />}` (import it). TopBar needs no change (it maps `tabs`).

- [ ] **Step 2:** Implement `ActivePositionsView.tsx`: poll `getPositions()` every 2s and overlay `useLive().positionTicks` for sub-second freshness. Render one card/row per open position with: instrument, direction + option type, tradingsymbol, qty/lot, entry premium, current option LTP (`live_premium`), spot (`live_spot`), unrealized P&L, entry cost, stop, target, dist-to-stop, dist-to-target, holding time (now − entry_time), last update (`last_mark_time`), stale badge (`stale`/`stale_age`). Controls per row: **Close now** (`closePosition(key)`), **Disable entries** (`blockEntries(key, true)`). A top "Manual paper entry" form: instrument `<select>` (from `getSignals` options-tradable list) + LONG/SHORT + submit → `manualOpen(key, dir)`; show success/error. Empty state: "No open positions." All actions show a toast/inline result and re-poll.
```tsx
export default function ActivePositionsView() {
  const { positionTicks } = useLive()
  const [rows, setRows] = useState<PositionRow[]>([])
  const load = () => getPositions().then(d => setRows(d.positions || []))
  useEffect(() => { load(); const t = setInterval(load, 2000); return () => clearInterval(t) }, [])
  // merge live ticks over polled rows for premium/pnl/stale
  …
}
```

- [ ] **Step 3: Verify** `npm run typecheck && npm run build`.

- [ ] **Step 4: Commit**
```bash
git add paper-trader/frontend/src/views/ActivePositionsView.tsx paper-trader/frontend/src/App.tsx
git commit -m "feat(fe): Active Positions cockpit with manual close/disable/open"
```

---

### Task T18: Interval selector + backtest cache badge + promote-with-interval

**Files:** Modify `src/views/Monitor.tsx` (IntervalSelect helper), `src/views/BacktestsView.tsx`

- [ ] **Step 1:** Add a small `IntervalSelect` (used in the list + detail): a `<select>` over `['5minute','15minute','30minute','60minute']` calling `setInterval_(key, iv)` then optimistic local update.
```tsx
function IntervalSelect({ k, value }: { k: string; value: string }) {
  const [v, setV] = useState(value)
  return (
    <select value={v} className="bg-panel2 border border-edge rounded px-1 py-0.5 text-[11px]"
      onClick={(e) => e.stopPropagation()}
      onChange={(e) => { setV(e.target.value); setInterval_(k, e.target.value) }}>
      {['5minute','15minute','30minute','60minute'].map(iv =>
        <option key={iv} value={iv}>{iv.replace('minute','m')}</option>)}
    </select>
  )
}
```

- [ ] **Step 2:** In `BacktestsView.tsx`: on promote (`add`), pass the row interval — `addToPortfolio(r.instrument_key, true, r.interval)`; if the response has `interval_warning`, `alert` it. Add a "cached" badge in the results table when `r.from_cache` (add `from_cache?: boolean` to `BTResult` type).

- [ ] **Step 3: Verify** `npm run typecheck && npm run build`.

- [ ] **Step 4: Commit**
```bash
git add paper-trader/frontend/src/views/Monitor.tsx paper-trader/frontend/src/views/BacktestsView.tsx paper-trader/frontend/src/lib/types.ts
git commit -m "feat(fe): per-instrument interval selector + promote-with-interval + cache badge"
```

**PHASE 6 GATE:** `npm run typecheck && npm run build` clean. Checkpoint.

---

# PHASE 7 — Full verification (codex acceptance + testing expectations)

### Task T19: Backend full verification

- [ ] **Step 1:** `cd paper-trader/backend && .venv/bin/python -m pytest -q` → all green (target ≥ 100 tests).
- [ ] **Step 2:** `.venv/bin/python scripts/dryrun.py 700` → ledger diff `0.0`.
- [ ] **Step 3:** `.venv/bin/python scripts/backtest_smoke.py` → net-of-charges invariant holds.
- [ ] **Step 4:** `.venv/bin/python -m pytest tests/test_safety.py -q` → SafePaperKite barrier intact.

### Task T20: Frontend + app run verification

- [ ] **Step 1:** `cd paper-trader/frontend && npm run typecheck && npm run build` → clean.
- [ ] **Step 2:** Run app on mock: backend `PT_PROVIDER=mock .venv/bin/uvicorn app.main:app --port 8090` + `npm run dev`; open `http://localhost:5173`. Manually verify the acceptance list:
  - [ ] No always-on mini charts in Home / Monitor / list rows.
  - [ ] Clicking an instrument opens detail and only then fetches chart data (Network tab shows `/api/candles` only on open).
  - [ ] Active Positions tab exists and reachable; renders empty + non-empty states.
  - [ ] Stale state is visible (kill the backend briefly → rows show stale; restart → recovers).
  - [ ] Interval selector changes an instrument's live interval (persists across reload).
  - [ ] Manual close / disable-entries / manual-open work and log; no console errors.
  - [ ] Backend logs do not spam repeated identical outage errors.

### Task T21: Finalize

- [ ] **Step 1:** Update `paper-trader/README.md` — document the new Active Positions view, the seven tabs, split loops, per-instrument intervals, stale handling, backtest cache, manual controls; reaffirm paper-only/no-pyramiding.
- [ ] **Step 2:** `git commit` the README.
- [ ] **Step 3:** Use `superpowers:finishing-a-development-branch` to merge `feat/live-cockpit` → `main` once the user confirms everything works, then push.

---

## Self-Review

**Spec coverage:** Every codex item F1–F8 maps to ≥1 task (see coverage table); each acceptance bullet maps to a T19/T20 check. Testing expectations: interval persistence (T6/T10), risk-vs-signal separation (T6/T7), no-SL/TP-on-stale (T6 `mark_and_exit_positions` + T4 `is_stale`), manual close/open/disable APIs (T9/T10), backtest cache hit/miss (T11) — all covered. Existing tests preserved (no deletions).

**Placeholder scan:** No "TBD"/"add error handling"/"similar to". Frontend tasks T15/T17 give skeletons not full files because there is no FE test harness and the components are layout-heavy; each lists exact data sources, props, columns, and controls, with representative code — executable without further design.

**Type consistency:** `mark(pos, premium, spot, now=None)` used consistently (T5 def, T6 call). `manual_open(inst, direction, chain, settings, now)` def (T9) = call (T10). `add_instrument(..., interval=None)` def (T12) = call (T12 route). `set_interval`/`set_entries_blocked`/`_interval_for` names consistent across runner (T6/T7) and routes (T10). `from_cache` added to model+summary (T1) and consumed in FE (T18). `params_signature`/`find_reusable`/`SCHEMA_VERSION` consistent (T11).

**Known scoped deferrals (called out, not silent):** per-instrument log panel in detail (T16) is best-effort; the fast risk lane is bounded by Kite's quote throttle (~2s for a batched snapshot) — documented as "fastest safe throttled cadence," not literally 1s under Kite.
