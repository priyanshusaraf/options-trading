# Purple SL/TP · Trade Journal · shadcn UI · Residual Fixes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship (1) the manual/physical trade journal (owner's most urgent ask —
**execute Group A/B first**), (2) purple-flagged intraday names getting wider
SL/TP than normal names, (3) three small residual fixes from the 2026-07-15 VPS
autopsy, (4) the H13 persisted order journal, and (5) a shadcn/ui foundation +
per-view re-skins — as five independently-shippable groups on
`feat/exits-journal`.

**Architecture:** Journal is a fully isolated subsystem (own `journal.db`, own
SQLAlchemy `Base`, own router) that never touches the engine's tables or
broker — mirrors the existing `research.db` isolation pattern exactly. Purple
SL/TP and the residual fixes are small, surgical edits inside
`app/engine/`. shadcn is additive on top of the existing Tailwind 3.4 stack
(new component/token files; existing view files are edited in place per-view,
not rewritten wholesale).

**Tech Stack:** Backend: Python 3, FastAPI, SQLAlchemy 2.0, SQLite, pytest.
Frontend: React 18, TypeScript 5.5, Vite 5, Tailwind 3.4.7, shadcn/ui (CLI-
generated components, Radix primitives, `class-variance-authority`, `clsx`,
`tailwind-merge`, `lucide-react`).

## Global Constraints

- Run backend commands from `paper-trader/backend/`, frontend from
  `paper-trader/frontend/` — never the repo root.
- TDD: write the failing test, watch it fail, write minimal code, watch it
  pass, commit. One commit per task (or per step group inside a task where
  noted), message style matching `git log` (e.g. `feat(journal): …`,
  `fix(live): …`).
- After every backend task: `.venv/bin/python -m pytest` (full suite must
  stay green) and, for any task touching `app/engine/` or `app/db/`,
  `.venv/bin/python scripts/dryrun.py 700` (ledger invariant
  `cash == initial + realized − Σ(open entry_cost)` must hold to the paisa).
  The journal group touches neither, so its own pytest run is sufficient, but
  run the full suite anyway to catch import-time surprises.
- After every frontend task: `npm run typecheck` (no test suite exists on the
  frontend per `CLAUDE.md`).
- New engine tunables go in `Settings` (`app/core/config.py`) **and**
  `runtime_config.py` (`OVERRIDABLE` + `BOUNDS`) when they should be
  live-editable — per repo convention.
- New DB **columns** on existing tables need `app/db/session.py:_migrate_schema`
  (additive `ALTER TABLE`, idempotent) — mirror `tests/test_migration.py`. New
  **tables** in the journal's own DB need no migration (fresh `create_all`);
  the journal DB has no legacy data to preserve.
- Every engine-behavior fix must emit a grep-able log marker (VPS deploy
  verification is marker-based — there is no git on the VPS, deploys are a
  whole-tree rsync + systemd restart, verified by `journalctl` grep).
- The options trading path's behavior must not change except where a task
  explicitly says so.
- Never touch `LiveContext.tsx` or `lib/api.ts`'s existing exports — only add
  to them.
- Source spec: `docs/superpowers/specs/2026-07-17-purple-journal-shadcn-design.md`.

---

## Execution order

**Group A (journal backend) and Group B (journal frontend) run FIRST** — the
owner flagged the journal as the most important deliverable this session.
Groups C–F follow in any order after A/B land (C and D are independent of
each other and of E/F; F's foundation task, F1, must land before F2+ and
before B3 the Journal re-skin pass, but B1/B2 do **not** wait for F — they ship
on the existing Tailwind utility classes already used across every other view,
and get re-skinned later in F's Journal pass per the design doc's priority
list).

```
A1 → A2 → A3 → A4 → A5   (journal backend: db → models → pnl → service → routes)
                    └──► B1 → B2 → B3   (journal frontend: api client → view → tab wiring)
C1 → C2                              (purple SL/TP: entry-time binding → lockstep wiring)
D1, D2, D3                           (residual fixes — independent of each other)
E1 → E2 → E3 → E4                    (H13 persisted order journal)
F1 → F2 (template) → F3 (checklist)  (shadcn foundation → re-skins, incl. Journal re-skin)
```

---

# Group A — Trade journal backend

### Task A1: Journal DB isolation layer

**Files:**
- Create: `backend/app/journal/__init__.py`
- Create: `backend/app/journal/config.py`
- Create: `backend/app/journal/db.py`
- Test: `backend/tests/journal/__init__.py`
- Test: `backend/tests/journal/test_db.py`

**Interfaces:**
- Produces: `JournalBase` (SQLAlchemy `DeclarativeBase`), `journal_db_path(env=None) -> str`,
  `make_engine(path: str) -> Engine`, `make_sessionmaker(engine) -> sessionmaker`,
  `init_journal_db(engine) -> None`.

This mirrors `backend/research/config.py` + `backend/research/domain/base.py`
exactly (same isolation pattern already proven in this codebase) so the
journal can never entangle with `paper_trader.db`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/journal/test_db.py
"""journal.db must be fully isolated: its own Base, its own engine, never the
execution engine's metadata."""
import os

from app.journal.config import journal_db_path, DEFAULT_JOURNAL_DB
from app.journal.db import JournalBase, make_engine, make_sessionmaker, init_journal_db


def test_journal_db_path_defaults_and_env_override(monkeypatch):
    assert journal_db_path({}) == DEFAULT_JOURNAL_DB
    assert journal_db_path({"PT_JOURNAL_DB_PATH": "/tmp/x.db"}) == "/tmp/x.db"


def test_journal_base_is_not_the_execution_base():
    from app.db.models import Base as ExecBase
    assert JournalBase is not ExecBase
    assert JournalBase.metadata is not ExecBase.metadata


def test_init_journal_db_creates_tables(tmp_path):
    path = str(tmp_path / "journal_test.db")
    engine = make_engine(path)
    init_journal_db(engine)
    from sqlalchemy import inspect
    tables = set(inspect(engine).get_table_names())
    assert {"journal_instruments", "journal_views", "journal_trades",
            "journal_missed", "journal_tags"} <= tables
    Session = make_sessionmaker(engine)
    with Session() as s:
        assert s is not None  # session factory is usable
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/journal/test_db.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'app.journal'`)

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/journal/__init__.py
```
(empty — marks the package)

```python
# backend/app/journal/config.py
"""Journal configuration — deliberately independent of app.core.config so the
journal never implicitly binds the execution DB engine. Mirrors
research/config.py's isolation pattern.
"""
from __future__ import annotations

import os
from collections.abc import Mapping

DEFAULT_JOURNAL_DB = "journal.db"


def journal_db_path(env: Mapping | None = None) -> str:
    """Path to journal.db (``PT_JOURNAL_DB_PATH``; default ``journal.db``)."""
    e = os.environ if env is None else env
    return e.get("PT_JOURNAL_DB_PATH", DEFAULT_JOURNAL_DB)
```

```python
# backend/app/journal/db.py
"""Dedicated SQLAlchemy base + engine factory for journal.db — the owner's
manual/physical trade log. `JournalBase` is a separate `DeclarativeBase` from
`app.db.models.Base` (the execution ledger) so the two can never entangle via
`metadata.create_all`/`drop_all`, and the journal package never imports the
engine, broker, or runner. Mirrors `research/domain/base.py`.
"""
from __future__ import annotations

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class JournalBase(DeclarativeBase):
    """Declarative base for every journal table. Never shared with the
    execution ledger's Base or the research plane's ResearchBase."""


def make_engine(path: str) -> Engine:
    engine = create_engine(f"sqlite:///{path}", future=True)

    @event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_conn, _record):  # noqa: ANN001
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=10000")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    return engine


def make_sessionmaker(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


def init_journal_db(engine: Engine) -> None:
    """Create all journal tables. Imports the models module so every mapped
    class is registered on JournalBase.metadata before create_all."""
    from app.journal import models  # noqa: F401  (registers tables)
    JournalBase.metadata.create_all(engine)
```

Also create an empty `models.py` stub so the import above resolves for this
task's test run (Task A2 fills it in):

```python
# backend/app/journal/models.py
"""Journal tables — filled in by Task A2."""
from __future__ import annotations

from app.journal.db import JournalBase  # noqa: F401
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/journal/test_db.py -v`
Expected: PASS (4 tests) — `test_init_journal_db_creates_tables` will still
fail at this step since no tables are defined yet; that's expected — proceed
to Task A2 before re-running. If you want a green checkpoint here, temporarily
skip that one assertion; otherwise fold Steps 1-4 of A1 and A2 into one
commit. **Recommended: do exactly that** — implement A1 and A2 together, run
the full A1 test file only after A2's models exist, then commit once. The
step numbering below in A2 continues from here.

---

### Task A2: Journal models

**Files:**
- Modify: `backend/app/journal/models.py`
- Test: `backend/tests/journal/test_models.py`

**Interfaces:**
- Consumes: `JournalBase` from `app.journal.db`.
- Produces: `JournalInstrument`, `JournalView`, `JournalTrade`, `JournalMissed`,
  `JournalTag` ORM classes (exact columns below — later tasks depend on these
  names).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/journal/test_models.py
import datetime as dt

from app.journal.db import make_engine, make_sessionmaker, init_journal_db
from app.journal.models import (
    JournalInstrument, JournalView, JournalTrade, JournalMissed, JournalTag)


def _session(tmp_path):
    engine = make_engine(str(tmp_path / "j.db"))
    init_journal_db(engine)
    return make_sessionmaker(engine)()


def test_instrument_roundtrip(tmp_path):
    s = _session(tmp_path)
    s.add(JournalInstrument(symbol="GOLDM", exchange="MCX", lot_size=10,
                             tick_size=1.0, multiplier=1.0, active=True))
    s.commit()
    row = s.get(JournalInstrument, "GOLDM")
    assert row.lot_size == 10 and row.active is True


def test_view_roundtrip_and_retire(tmp_path):
    s = _session(tmp_path)
    v = JournalView(name="current", thesis="swing minis", created_at=dt.datetime.now())
    s.add(v)
    s.commit()
    assert v.id is not None
    assert v.retired_at is None
    v.retired_at = dt.datetime.now()
    s.commit()
    assert s.get(JournalView, v.id).retired_at is not None


def test_trade_roundtrip_open_and_closed(tmp_path):
    s = _session(tmp_path)
    inst = JournalInstrument(symbol="GOLDM", exchange="MCX", lot_size=10,
                              tick_size=1.0, multiplier=1.0, active=True)
    view = JournalView(name="current", created_at=dt.datetime.now())
    s.add_all([inst, view])
    s.commit()
    t = JournalTrade(
        instrument_symbol="GOLDM", direction="LONG", lots=1,
        entry_price=72000.0, entry_time=dt.datetime.now(), view_id=view.id,
        setup_tag="breakout", notes="test entry")
    s.add(t)
    s.commit()
    assert t.id is not None
    assert t.exit_price is None and t.exit_time is None
    assert t.manual_net_pnl is None
    t.exit_price, t.exit_time = 72500.0, dt.datetime.now()
    s.commit()
    assert s.get(JournalTrade, t.id).exit_price == 72500.0


def test_missed_roundtrip(tmp_path):
    s = _session(tmp_path)
    inst = JournalInstrument(symbol="SILVERM", exchange="MCX", lot_size=5,
                              tick_size=1.0, multiplier=1.0, active=True)
    s.add(inst)
    s.commit()
    m = JournalMissed(
        instrument_symbol="SILVERM", direction="SHORT", seen_at=dt.datetime.now(),
        setup_tag="reversal", skip_reason="was away from desk",
        hypothetical_entry=90000.0, hypothetical_exit=89500.0)
    s.add(m)
    s.commit()
    assert m.id is not None


def test_tag_curation_unique(tmp_path):
    s = _session(tmp_path)
    s.add(JournalTag(name="breakout"))
    s.commit()
    assert s.get(JournalTag, "breakout") is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/journal/test_models.py -v`
Expected: FAIL (`ImportError: cannot import name 'JournalInstrument'`)

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/journal/models.py
"""Journal tables — the owner's manual/physical trade log. Fully isolated from
the execution ledger (own JournalBase, own journal.db); the engine never
imports this package.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.journal.db import JournalBase


class JournalInstrument(JournalBase):
    """The journal's own instrument list — separate from the bot's universe
    because the bot trades full-size CRUDEOIL/NATURALGAS while the owner
    manually trades the MINI contracts (different lot size/multiplier)."""
    __tablename__ = "journal_instruments"
    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    exchange: Mapped[str] = mapped_column(String(8), default="MCX")
    lot_size: Mapped[int] = mapped_column(Integer)
    tick_size: Mapped[float] = mapped_column(Float, default=1.0)
    # contract value multiplier — 1.0 unless the contract's point value differs
    # from lot_size×price (verify against the exchange contract spec per symbol
    # before trusting a non-default value).
    multiplier: Mapped[float] = mapped_column(Float, default=1.0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class JournalView(JournalBase):
    """An append-only horizon (e.g. 'long-term', 'current-week'). Trades bind
    to whichever view is live (retired_at IS NULL) at entry time; retiring a
    view never rewrites the trades already bound to it."""
    __tablename__ = "journal_views"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    thesis: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime)
    retired_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)


class JournalTrade(JournalBase):
    """An executed manual/physical trade. `manual_net_pnl`, when set, IS the
    net P&L (charges are never separately subtracted on top of it) — set it
    when the owner enters the broker-reported net directly; leave it NULL to
    have net computed from entry/exit price + app.engine.charges."""
    __tablename__ = "journal_trades"
    id: Mapped[int] = mapped_column(primary_key=True)
    instrument_symbol: Mapped[str] = mapped_column(
        String(32), ForeignKey("journal_instruments.symbol"))
    direction: Mapped[str] = mapped_column(String(8))  # LONG | SHORT
    lots: Mapped[int] = mapped_column(Integer)
    entry_price: Mapped[float] = mapped_column(Float)
    entry_time: Mapped[dt.datetime] = mapped_column(DateTime)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit_time: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    view_id: Mapped[int] = mapped_column(Integer, ForeignKey("journal_views.id"))
    setup_tag: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    manual_net_pnl: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now)


class JournalMissed(JournalBase):
    """A setup the owner saw but did not take, with an optional hypothetical
    entry/exit so missed-opportunity P&L can be estimated (never counted as
    real P&L)."""
    __tablename__ = "journal_missed"
    id: Mapped[int] = mapped_column(primary_key=True)
    instrument_symbol: Mapped[str] = mapped_column(
        String(32), ForeignKey("journal_instruments.symbol"))
    direction: Mapped[str] = mapped_column(String(8))
    seen_at: Mapped[dt.datetime] = mapped_column(DateTime)
    setup_tag: Mapped[str | None] = mapped_column(String(64), nullable=True)
    skip_reason: Mapped[str] = mapped_column(Text)
    hypothetical_entry: Mapped[float | None] = mapped_column(Float, nullable=True)
    hypothetical_exit: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class JournalTag(JournalBase):
    """Curated setup-tag suggestion list. Tags are still free-text on trades/
    missed rows; this table is auto-upserted on first use so the UI can offer
    a picker instead of re-typing tags from memory."""
    __tablename__ = "journal_tags"
    name: Mapped[str] = mapped_column(String(64), primary_key=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/journal/ -v`
Expected: PASS (all of A1 + A2's tests, ~9 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/journal/__init__.py backend/app/journal/config.py \
        backend/app/journal/db.py backend/app/journal/models.py \
        backend/tests/journal/__init__.py backend/tests/journal/test_db.py \
        backend/tests/journal/test_models.py
git commit -m "feat(journal): isolated journal.db + schema (instruments/views/trades/missed/tags)"
```

---

### Task A3: Pure P&L functions

**Files:**
- Create: `backend/app/journal/pnl.py`
- Test: `backend/tests/journal/test_pnl.py`

**Interfaces:**
- Consumes: `app.engine.charges.compute_charges(segment: str, side: str, premium: float, qty: int) -> dict`
  (existing, `dict["total"]` is the per-leg charge). `MCX_FUT` is the schedule key
  for commodity futures (`app/engine/charges.py`).
- Produces: `gross_pnl(direction, entry_price, exit_price, lots, lot_size, multiplier) -> float`,
  `round_trip_charges(entry_price, exit_price, lots, lot_size) -> float`,
  `net_pnl(direction, entry_price, exit_price, lots, lot_size, multiplier, manual_net_pnl=None) -> float`,
  `unrealized_pnl(direction, entry_price, last_price, lots, lot_size, multiplier) -> float`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/journal/test_pnl.py
"""Pure P&L math — no DB, no engine, no provider. GOLDM lot_size=10, multiplier=1.0
throughout (mirrors app/core/instruments.py's GOLDM seed)."""
from app.journal.pnl import gross_pnl, round_trip_charges, net_pnl, unrealized_pnl


def test_gross_pnl_long_and_short():
    assert gross_pnl("LONG", 72000, 72500, lots=1, lot_size=10, multiplier=1.0) == 5000.0
    assert gross_pnl("SHORT", 72000, 71500, lots=1, lot_size=10, multiplier=1.0) == 5000.0
    assert gross_pnl("LONG", 72000, 71500, lots=2, lot_size=10, multiplier=1.0) == -10000.0


def test_round_trip_charges_uses_mcx_fut_schedule_and_is_positive():
    c = round_trip_charges(72000, 72500, lots=1, lot_size=10)
    assert c > 0
    # a bigger round-trip notional charges more
    assert round_trip_charges(72000, 72500, lots=2, lot_size=10) > c


def test_net_pnl_computed_when_manual_is_none():
    gross = gross_pnl("LONG", 72000, 72500, lots=1, lot_size=10, multiplier=1.0)
    charges = round_trip_charges(72000, 72500, lots=1, lot_size=10)
    net = net_pnl("LONG", 72000, 72500, lots=1, lot_size=10, multiplier=1.0)
    assert abs(net - (gross - charges)) < 1e-6


def test_net_pnl_manual_overrides_and_never_double_subtracts_charges():
    # owner enters the broker's own net figure directly — must be returned verbatim,
    # NOT further reduced by computed charges.
    assert net_pnl("LONG", 72000, 72500, lots=1, lot_size=10, multiplier=1.0,
                    manual_net_pnl=4321.0) == 4321.0


def test_unrealized_pnl_is_gross_only_no_exit_charges_yet():
    # only the entry leg's charges are real so far; unrealized is pre-exit-charge gross
    # minus the entry leg only, not a full round trip.
    u = unrealized_pnl("LONG", 72000, 72500, lots=1, lot_size=10, multiplier=1.0)
    gross = gross_pnl("LONG", 72000, 72500, lots=1, lot_size=10, multiplier=1.0)
    assert u < gross  # entry-leg charges reduce it
    assert u > gross - round_trip_charges(72000, 72500, lots=1, lot_size=10)  # but not a full RT
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/journal/test_pnl.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'app.journal.pnl'`)

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/journal/pnl.py
"""Pure P&L math for manual/physical journal trades. Reuses the engine's real
charge schedule (app.engine.charges) so journal figures are net-of-cost on the
same basis as the live/backtest ledgers — no separate cost model to drift.
"""
from __future__ import annotations

from app.engine.charges import compute_charges

SEGMENT = "MCX_FUT"


def gross_pnl(direction: str, entry_price: float, exit_price: float, *,
              lots: int, lot_size: int, multiplier: float = 1.0) -> float:
    qty = lots * lot_size
    move = (exit_price - entry_price) if direction == "LONG" else (entry_price - exit_price)
    return move * qty * multiplier


def round_trip_charges(entry_price: float, exit_price: float, *,
                        lots: int, lot_size: int) -> float:
    qty = lots * lot_size
    entry_leg = compute_charges(SEGMENT, "BUY", entry_price, qty)["total"]
    exit_leg = compute_charges(SEGMENT, "SELL", exit_price, qty)["total"]
    return entry_leg + exit_leg


def net_pnl(direction: str, entry_price: float, exit_price: float, *,
            lots: int, lot_size: int, multiplier: float = 1.0,
            manual_net_pnl: float | None = None) -> float:
    if manual_net_pnl is not None:
        return manual_net_pnl
    gross = gross_pnl(direction, entry_price, exit_price,
                       lots=lots, lot_size=lot_size, multiplier=multiplier)
    charges = round_trip_charges(entry_price, exit_price, lots=lots, lot_size=lot_size)
    return gross - charges


def unrealized_pnl(direction: str, entry_price: float, last_price: float, *,
                    lots: int, lot_size: int, multiplier: float = 1.0) -> float:
    """Mark-to-market on an OPEN trade: gross minus the entry leg's charges only
    (the exit leg hasn't happened yet, so it isn't deducted)."""
    qty = lots * lot_size
    gross = gross_pnl(direction, entry_price, last_price,
                       lots=lots, lot_size=lot_size, multiplier=multiplier)
    entry_leg = compute_charges(SEGMENT, "BUY", entry_price, qty)["total"]
    return gross - entry_leg
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/journal/test_pnl.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/journal/pnl.py backend/tests/journal/test_pnl.py
git commit -m "feat(journal): pure net-of-charges P&L math (gross/net/unrealized)"
```

---

### Task A4: Journal service layer (CRUD + stats + live MTM)

**Files:**
- Create: `backend/app/journal/service.py`
- Test: `backend/tests/journal/test_service.py`

**Interfaces:**
- Consumes: `JournalBase`/`make_engine`/`make_sessionmaker`/`init_journal_db`
  (A1); `JournalInstrument`/`JournalView`/`JournalTrade`/`JournalMissed`/
  `JournalTag` (A2); `gross_pnl`/`round_trip_charges`/`net_pnl`/
  `unrealized_pnl` (A3); `app.core.instruments.Instrument` (existing dataclass,
  read-only, for building a throwaway quote-lookup object);
  `app.providers.base.MarketDataProvider.get_ltp(inst) -> float | None`
  (existing interface — the live provider is passed in by the caller, never
  imported globally, so the service stays testable with a fake).
- Produces (all take a `Session` as first arg — no global session state):
  - `ensure_current_view(s) -> JournalView` (auto-creates a "current" view if
    none is live)
  - `add_trade(s, *, symbol, direction, lots, entry_price, entry_time,
    setup_tag=None, notes=None, view_id=None) -> JournalTrade`
  - `close_trade(s, trade_id, *, exit_price, exit_time, manual_net_pnl=None) -> JournalTrade`
  - `add_missed(s, *, symbol, direction, seen_at, skip_reason, setup_tag=None,
    hypothetical_entry=None, hypothetical_exit=None, notes=None) -> JournalMissed`
  - `list_trades(s, *, open_only=False) -> list[JournalTrade]`
  - `list_missed(s) -> list[JournalMissed]`
  - `trade_unrealized(trade: JournalTrade, inst: JournalInstrument, last_price: float) -> float`
  - `stats(s) -> dict` — `{by_tag: {tag: {trades, wins, net_pnl}}, by_view:
    {view_name: {trades, net_pnl}}, missed_summary: {count, hypothetical_net_pnl}}`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/journal/test_service.py
import datetime as dt

from app.journal.db import make_engine, make_sessionmaker, init_journal_db
from app.journal.models import JournalInstrument
from app.journal import service


def _session(tmp_path):
    engine = make_engine(str(tmp_path / "j.db"))
    init_journal_db(engine)
    s = make_sessionmaker(engine)()
    s.add(JournalInstrument(symbol="GOLDM", exchange="MCX", lot_size=10,
                             tick_size=1.0, multiplier=1.0, active=True))
    s.commit()
    return s


def test_ensure_current_view_creates_once(tmp_path):
    s = _session(tmp_path)
    v1 = service.ensure_current_view(s)
    v2 = service.ensure_current_view(s)
    assert v1.id == v2.id  # idempotent — doesn't create a second live view


def test_add_trade_binds_to_current_view_when_unspecified(tmp_path):
    s = _session(tmp_path)
    t = service.add_trade(s, symbol="GOLDM", direction="LONG", lots=1,
                           entry_price=72000.0, entry_time=dt.datetime.now())
    assert t.id is not None
    assert t.view_id == service.ensure_current_view(s).id
    assert t.exit_price is None


def test_close_trade_sets_exit_fields(tmp_path):
    s = _session(tmp_path)
    t = service.add_trade(s, symbol="GOLDM", direction="LONG", lots=1,
                           entry_price=72000.0, entry_time=dt.datetime.now())
    closed = service.close_trade(s, t.id, exit_price=72500.0, exit_time=dt.datetime.now())
    assert closed.exit_price == 72500.0


def test_add_trade_upserts_tag_into_curation_list(tmp_path):
    s = _session(tmp_path)
    service.add_trade(s, symbol="GOLDM", direction="LONG", lots=1,
                       entry_price=72000.0, entry_time=dt.datetime.now(),
                       setup_tag="breakout")
    from app.journal.models import JournalTag
    assert s.get(JournalTag, "breakout") is not None


def test_add_missed_persists(tmp_path):
    s = _session(tmp_path)
    m = service.add_missed(s, symbol="GOLDM", direction="SHORT",
                            seen_at=dt.datetime.now(), skip_reason="lunch",
                            hypothetical_entry=72000.0, hypothetical_exit=71800.0)
    assert m.id is not None


def test_list_trades_open_only_filter(tmp_path):
    s = _session(tmp_path)
    open_t = service.add_trade(s, symbol="GOLDM", direction="LONG", lots=1,
                                entry_price=72000.0, entry_time=dt.datetime.now())
    closed_t = service.add_trade(s, symbol="GOLDM", direction="LONG", lots=1,
                                  entry_price=71000.0, entry_time=dt.datetime.now())
    service.close_trade(s, closed_t.id, exit_price=71200.0, exit_time=dt.datetime.now())
    ids = {t.id for t in service.list_trades(s, open_only=True)}
    assert ids == {open_t.id}


def test_trade_unrealized_uses_pnl_module(tmp_path):
    s = _session(tmp_path)
    t = service.add_trade(s, symbol="GOLDM", direction="LONG", lots=1,
                           entry_price=72000.0, entry_time=dt.datetime.now())
    inst = s.get(JournalInstrument, "GOLDM")
    from app.journal.pnl import unrealized_pnl
    expected = unrealized_pnl("LONG", 72000.0, 72200.0, lots=1, lot_size=10, multiplier=1.0)
    assert service.trade_unrealized(t, inst, 72200.0) == expected


def test_stats_by_tag_and_missed_summary(tmp_path):
    s = _session(tmp_path)
    t = service.add_trade(s, symbol="GOLDM", direction="LONG", lots=1,
                           entry_price=72000.0, entry_time=dt.datetime.now(),
                           setup_tag="breakout")
    service.close_trade(s, t.id, exit_price=72500.0, exit_time=dt.datetime.now())
    service.add_missed(s, symbol="GOLDM", direction="LONG", seen_at=dt.datetime.now(),
                        skip_reason="away", hypothetical_entry=72000.0,
                        hypothetical_exit=72400.0)
    out = service.stats(s)
    assert out["by_tag"]["breakout"]["trades"] == 1
    assert out["by_tag"]["breakout"]["wins"] == 1
    assert out["by_tag"]["breakout"]["net_pnl"] > 0
    assert out["missed_summary"]["count"] == 1
    assert out["missed_summary"]["hypothetical_net_pnl"] > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/journal/test_service.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'app.journal.service'`)

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/journal/service.py
"""Journal service layer — CRUD + stats over journal.db. Every function takes
an explicit Session (no module-level session state) so it's testable against
a throwaway DB and safely callable from FastAPI's request-scoped session.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from app.journal.models import JournalInstrument, JournalMissed, JournalTag, JournalTrade, JournalView
from app.journal.pnl import net_pnl, unrealized_pnl

CURRENT_VIEW_NAME = "current"


def ensure_current_view(s) -> JournalView:
    """The live (non-retired) view trades bind to when the caller doesn't pick
    one explicitly. Auto-creates a 'current' view on first use; idempotent."""
    row = s.execute(
        select(JournalView).where(JournalView.retired_at.is_(None))
        .order_by(JournalView.created_at.desc())
    ).scalars().first()
    if row is not None:
        return row
    row = JournalView(name=CURRENT_VIEW_NAME, created_at=dt.datetime.now())
    s.add(row)
    s.commit()
    return row


def _upsert_tag(s, tag: str | None) -> None:
    if not tag:
        return
    if s.get(JournalTag, tag) is None:
        s.add(JournalTag(name=tag))
        s.commit()


def add_trade(s, *, symbol: str, direction: str, lots: int, entry_price: float,
              entry_time: dt.datetime, setup_tag: str | None = None,
              notes: str | None = None, view_id: int | None = None) -> JournalTrade:
    vid = view_id if view_id is not None else ensure_current_view(s).id
    t = JournalTrade(instrument_symbol=symbol, direction=direction, lots=lots,
                      entry_price=entry_price, entry_time=entry_time, view_id=vid,
                      setup_tag=setup_tag, notes=notes)
    s.add(t)
    _upsert_tag(s, setup_tag)
    s.commit()
    return t


def close_trade(s, trade_id: int, *, exit_price: float, exit_time: dt.datetime,
                 manual_net_pnl: float | None = None) -> JournalTrade:
    t = s.get(JournalTrade, trade_id)
    t.exit_price, t.exit_time = exit_price, exit_time
    t.manual_net_pnl = manual_net_pnl
    s.commit()
    return t


def add_missed(s, *, symbol: str, direction: str, seen_at: dt.datetime,
               skip_reason: str, setup_tag: str | None = None,
               hypothetical_entry: float | None = None,
               hypothetical_exit: float | None = None,
               notes: str | None = None) -> JournalMissed:
    m = JournalMissed(instrument_symbol=symbol, direction=direction, seen_at=seen_at,
                       skip_reason=skip_reason, setup_tag=setup_tag,
                       hypothetical_entry=hypothetical_entry,
                       hypothetical_exit=hypothetical_exit, notes=notes)
    s.add(m)
    _upsert_tag(s, setup_tag)
    s.commit()
    return m


def list_trades(s, *, open_only: bool = False) -> list[JournalTrade]:
    q = select(JournalTrade).order_by(JournalTrade.entry_time.desc())
    if open_only:
        q = q.where(JournalTrade.exit_time.is_(None))
    return list(s.execute(q).scalars().all())


def list_missed(s) -> list[JournalMissed]:
    return list(s.execute(select(JournalMissed).order_by(JournalMissed.seen_at.desc())).scalars().all())


def trade_unrealized(trade: JournalTrade, inst: JournalInstrument, last_price: float) -> float:
    return unrealized_pnl(trade.direction, trade.entry_price, last_price,
                           lots=trade.lots, lot_size=inst.lot_size, multiplier=inst.multiplier)


def _trade_net(t: JournalTrade, inst: JournalInstrument) -> float | None:
    if t.exit_price is None:
        return None
    return net_pnl(t.direction, t.entry_price, t.exit_price, lots=t.lots,
                    lot_size=inst.lot_size, multiplier=inst.multiplier,
                    manual_net_pnl=t.manual_net_pnl)


def stats(s) -> dict:
    trades = list_trades(s)
    insts = {r.symbol: r for r in s.execute(select(JournalInstrument)).scalars().all()}
    views = {r.id: r.name for r in s.execute(select(JournalView)).scalars().all()}

    by_tag: dict[str, dict] = {}
    by_view: dict[str, dict] = {}
    for t in trades:
        inst = insts.get(t.instrument_symbol)
        net = _trade_net(t, inst) if inst else None
        if net is None:
            continue  # still open — excluded from realized stats
        tag = t.setup_tag or "untagged"
        row = by_tag.setdefault(tag, {"trades": 0, "wins": 0, "net_pnl": 0.0})
        row["trades"] += 1
        row["wins"] += 1 if net > 0 else 0
        row["net_pnl"] += net
        vname = views.get(t.view_id, "unknown")
        vrow = by_view.setdefault(vname, {"trades": 0, "net_pnl": 0.0})
        vrow["trades"] += 1
        vrow["net_pnl"] += net

    missed = list_missed(s)
    hyp_total = 0.0
    for m in missed:
        if m.hypothetical_entry is None or m.hypothetical_exit is None:
            continue
        inst = insts.get(m.instrument_symbol)
        if inst is None:
            continue
        hyp_total += net_pnl(m.direction, m.hypothetical_entry, m.hypothetical_exit,
                              lots=1, lot_size=inst.lot_size, multiplier=inst.multiplier)

    return {
        "by_tag": by_tag,
        "by_view": by_view,
        "missed_summary": {"count": len(missed), "hypothetical_net_pnl": round(hyp_total, 2)},
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/journal/test_service.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/journal/service.py backend/tests/journal/test_service.py
git commit -m "feat(journal): service layer — CRUD, view binding, stats, unrealized MTM"
```

---

### Task A5: Journal REST API + startup wiring + instrument seeding

**Files:**
- Create: `backend/app/journal/schemas.py`
- Create: `backend/app/journal/routes.py`
- Modify: `backend/app/main.py` (add journal DB init to `lifespan`, mount router)
- Test: `backend/tests/journal/test_routes.py`

**Interfaces:**
- Consumes: everything from A1-A4; `app.providers.factory.get_provider() ->
  MarketDataProvider` (existing, for live quotes — imported lazily inside the
  route handler only, never at module scope, so importing `app.journal.routes`
  never touches the engine's provider singleton at collection time);
  `app.core.instruments.Instrument` (dataclass, for a throwaway quote-lookup
  object — journal instruments are NOT registered into the bot's universe).
- Produces: `router` (FastAPI `APIRouter`, prefix `/api/journal`), mounted in
  `main.py` via `app.include_router(journal_routes.router)`.

Seed instruments (GOLDM/SILVERM already have correct MINI specs in the bot's
own seed registry per `app/core/instruments.py`; CRUDEOILM/NATGASM are new —
the bot only carries full-size CRUDEOIL/NATURALGAS):

| symbol | exchange | lot_size | tick_size |
|---|---|---|---|
| GOLDM | MCX | 10 | 1.0 |
| SILVERM | MCX | 5 | 1.0 |
| CRUDEOILM | MCX | 10 | 1.0 |
| NATGASM | MCX | 250 | 0.1 |

(`multiplier` defaults to 1.0 for all four — flag in the route docstring that
the owner should verify lot sizes against the current Kite instrument dump
before relying on P&L figures, since these are entered by hand rather than
resolved live.)

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/journal/test_routes.py
"""Journal REST surface. Uses a TestClient with PT_JOURNAL_DB_PATH pointed at a
temp file (isolation — never touches the owner's real journal.db)."""
import os
import tempfile

os.environ["PT_JOURNAL_DB_PATH"] = os.path.join(tempfile.gettempdir(), "journal_pytest.db")

from fastapi.testclient import TestClient

from app.main import app


def _client():
    # fresh DB per test run
    path = os.environ["PT_JOURNAL_DB_PATH"]
    if os.path.exists(path):
        os.remove(path)
    return TestClient(app)


def test_instruments_seeded_on_first_call():
    c = _client()
    res = c.get("/api/journal/instruments").json()
    symbols = {r["symbol"] for r in res["instruments"]}
    assert {"GOLDM", "SILVERM", "CRUDEOILM", "NATGASM"} <= symbols


def test_add_and_list_trade_roundtrip():
    c = _client()
    r = c.post("/api/journal/trades", json={
        "symbol": "GOLDM", "direction": "LONG", "lots": 1,
        "entry_price": 72000.0, "setup_tag": "breakout",
    })
    assert r.status_code == 200
    trade_id = r.json()["id"]
    rows = c.get("/api/journal/trades").json()["trades"]
    assert any(t["id"] == trade_id for t in rows)


def test_close_trade_route():
    c = _client()
    trade_id = c.post("/api/journal/trades", json={
        "symbol": "GOLDM", "direction": "LONG", "lots": 1, "entry_price": 72000.0,
    }).json()["id"]
    r = c.post(f"/api/journal/trades/{trade_id}/close", json={"exit_price": 72500.0})
    assert r.status_code == 200
    assert r.json()["exit_price"] == 72500.0


def test_add_missed_route():
    c = _client()
    r = c.post("/api/journal/missed", json={
        "symbol": "SILVERM", "direction": "SHORT", "skip_reason": "away from desk",
    })
    assert r.status_code == 200
    assert r.json()["id"] is not None


def test_stats_route():
    c = _client()
    trade_id = c.post("/api/journal/trades", json={
        "symbol": "GOLDM", "direction": "LONG", "lots": 1, "entry_price": 72000.0,
        "setup_tag": "breakout",
    }).json()["id"]
    c.post(f"/api/journal/trades/{trade_id}/close", json={"exit_price": 72500.0})
    r = c.get("/api/journal/stats")
    assert r.status_code == 200
    assert "breakout" in r.json()["by_tag"]


def test_views_route_create_and_list():
    c = _client()
    r = c.post("/api/journal/views", json={"name": "swing-2026", "thesis": "test"})
    assert r.status_code == 200
    rows = c.get("/api/journal/views").json()["views"]
    assert any(v["name"] == "swing-2026" for v in rows)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/journal/test_routes.py -v`
Expected: FAIL (404s — router not mounted yet)

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/journal/schemas.py
"""Request/response models for the journal REST API."""
from __future__ import annotations

import datetime as dt

from pydantic import BaseModel


class AddTradeRequest(BaseModel):
    symbol: str
    direction: str          # LONG | SHORT
    lots: int
    entry_price: float
    entry_time: dt.datetime | None = None
    setup_tag: str | None = None
    notes: str | None = None
    view_id: int | None = None


class CloseTradeRequest(BaseModel):
    exit_price: float
    exit_time: dt.datetime | None = None
    manual_net_pnl: float | None = None


class AddMissedRequest(BaseModel):
    symbol: str
    direction: str
    seen_at: dt.datetime | None = None
    setup_tag: str | None = None
    skip_reason: str
    hypothetical_entry: float | None = None
    hypothetical_exit: float | None = None
    notes: str | None = None


class AddViewRequest(BaseModel):
    name: str
    thesis: str | None = None
```

```python
# backend/app/journal/routes.py
"""REST surface for the trade journal — fully isolated from the execution
engine's routes/DB. Every handler opens its own journal.db session and closes
it; there is no shared session with app.db.session.
"""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, HTTPException

from app.journal import service
from app.journal.config import journal_db_path
from app.journal.db import init_journal_db, make_engine, make_sessionmaker
from app.journal.models import JournalInstrument, JournalTrade, JournalView
from app.journal.schemas import AddMissedRequest, AddTradeRequest, AddViewRequest, CloseTradeRequest

router = APIRouter(prefix="/api/journal", tags=["journal"])

# Own MINI-contract specs — deliberately separate from app.core.instruments
# (the bot's universe carries full-size CRUDEOIL/NATURALGAS, wrong multipliers
# for the owner's manual minis). Verify lot sizes against the current Kite
# instrument dump before trusting P&L on a newly-added symbol.
SEED_INSTRUMENTS = [
    dict(symbol="GOLDM", exchange="MCX", lot_size=10, tick_size=1.0, multiplier=1.0),
    dict(symbol="SILVERM", exchange="MCX", lot_size=5, tick_size=1.0, multiplier=1.0),
    dict(symbol="CRUDEOILM", exchange="MCX", lot_size=10, tick_size=1.0, multiplier=1.0),
    dict(symbol="NATGASM", exchange="MCX", lot_size=250, tick_size=0.1, multiplier=1.0),
]

_engine = None
_SessionLocal = None


def _get_sessionmaker():
    """Lazy singleton so importing this module (e.g. at FastAPI startup
    collection time) never opens the DB file before the app actually runs —
    matters for tests, which set PT_JOURNAL_DB_PATH before import."""
    global _engine, _SessionLocal
    if _SessionLocal is None:
        _engine = make_engine(journal_db_path())
        init_journal_db(_engine)
        _seed_instruments(_engine)
        _SessionLocal = make_sessionmaker(_engine)
    return _SessionLocal


def _seed_instruments(engine) -> None:
    Session = make_sessionmaker(engine)
    with Session() as s:
        for row in SEED_INSTRUMENTS:
            if s.get(JournalInstrument, row["symbol"]) is None:
                s.add(JournalInstrument(active=True, **row))
        s.commit()


def _session():
    return _get_sessionmaker()()


def _trade_dict(t: JournalTrade) -> dict:
    return {
        "id": t.id, "instrument_symbol": t.instrument_symbol, "direction": t.direction,
        "lots": t.lots, "entry_price": t.entry_price,
        "entry_time": t.entry_time.isoformat(), "exit_price": t.exit_price,
        "exit_time": t.exit_time.isoformat() if t.exit_time else None,
        "view_id": t.view_id, "setup_tag": t.setup_tag, "notes": t.notes,
        "manual_net_pnl": t.manual_net_pnl,
    }


@router.get("/instruments")
def list_instruments():
    with _session() as s:
        from sqlalchemy import select
        rows = s.execute(select(JournalInstrument)).scalars().all()
        return {"instruments": [
            {"symbol": r.symbol, "exchange": r.exchange, "lot_size": r.lot_size,
             "tick_size": r.tick_size, "multiplier": r.multiplier, "active": r.active}
            for r in rows]}


@router.post("/trades")
def add_trade(req: AddTradeRequest):
    with _session() as s:
        if s.get(JournalInstrument, req.symbol) is None:
            raise HTTPException(400, f"unknown journal instrument {req.symbol}")
        t = service.add_trade(
            s, symbol=req.symbol, direction=req.direction, lots=req.lots,
            entry_price=req.entry_price, entry_time=req.entry_time or dt.datetime.now(),
            setup_tag=req.setup_tag, notes=req.notes, view_id=req.view_id)
        return _trade_dict(t)


@router.get("/trades")
def list_trades(open_only: bool = False):
    with _session() as s:
        return {"trades": [_trade_dict(t) for t in service.list_trades(s, open_only=open_only)]}


@router.post("/trades/{trade_id}/close")
def close_trade(trade_id: int, req: CloseTradeRequest):
    with _session() as s:
        if s.get(JournalTrade, trade_id) is None:
            raise HTTPException(404, "trade not found")
        t = service.close_trade(
            s, trade_id, exit_price=req.exit_price,
            exit_time=req.exit_time or dt.datetime.now(), manual_net_pnl=req.manual_net_pnl)
        return _trade_dict(t)


@router.get("/trades/open-mtm")
def open_trades_with_mtm():
    """Open trades with live unrealized P&L via the shared market-data provider
    (read-only quote lookup). A quote failure degrades that row's `unrealized`
    to null rather than failing the whole list."""
    from app.core.instruments import Instrument
    from app.providers.factory import get_provider
    provider = get_provider()
    with _session() as s:
        from sqlalchemy import select
        insts = {r.symbol: r for r in s.execute(select(JournalInstrument)).scalars().all()}
        out = []
        for t in service.list_trades(s, open_only=True):
            inst = insts.get(t.instrument_symbol)
            row = _trade_dict(t)
            row["unrealized"] = None
            if inst is not None:
                probe = Instrument(
                    key=inst.symbol, name=inst.symbol, segment=inst.exchange,
                    spot_exchange=inst.exchange, spot_symbol=inst.symbol,
                    option_name=inst.symbol, lot_size=inst.lot_size, strike_step=0,
                    priority=99, mock_spot=0.0, mock_vol=0.0, has_options=False)
                try:
                    last = provider.get_ltp(probe)
                except Exception:
                    last = None
                if last is not None:
                    row["unrealized"] = service.trade_unrealized(t, inst, last)
            out.append(row)
        return {"trades": out}


@router.post("/missed")
def add_missed(req: AddMissedRequest):
    with _session() as s:
        if s.get(JournalInstrument, req.symbol) is None:
            raise HTTPException(400, f"unknown journal instrument {req.symbol}")
        m = service.add_missed(
            s, symbol=req.symbol, direction=req.direction,
            seen_at=req.seen_at or dt.datetime.now(), skip_reason=req.skip_reason,
            setup_tag=req.setup_tag, hypothetical_entry=req.hypothetical_entry,
            hypothetical_exit=req.hypothetical_exit, notes=req.notes)
        return {"id": m.id}


@router.get("/missed")
def list_missed():
    with _session() as s:
        rows = service.list_missed(s)
        return {"missed": [
            {"id": m.id, "instrument_symbol": m.instrument_symbol, "direction": m.direction,
             "seen_at": m.seen_at.isoformat(), "setup_tag": m.setup_tag,
             "skip_reason": m.skip_reason, "hypothetical_entry": m.hypothetical_entry,
             "hypothetical_exit": m.hypothetical_exit, "notes": m.notes}
            for m in rows]}


@router.get("/stats")
def get_stats():
    with _session() as s:
        return service.stats(s)


@router.post("/views")
def add_view(req: AddViewRequest):
    with _session() as s:
        v = JournalView(name=req.name, thesis=req.thesis, created_at=dt.datetime.now())
        s.add(v)
        s.commit()
        return {"id": v.id, "name": v.name}


@router.get("/views")
def list_views():
    with _session() as s:
        from sqlalchemy import select
        rows = s.execute(select(JournalView)).scalars().all()
        return {"views": [
            {"id": v.id, "name": v.name, "thesis": v.thesis,
             "created_at": v.created_at.isoformat(),
             "retired_at": v.retired_at.isoformat() if v.retired_at else None}
            for v in rows]}
```

Now mount the router in `main.py`. Find the existing router includes:

```python
# backend/app/main.py — near the existing include_router calls (~line 137-139)
app.include_router(routes.router)
app.include_router(backtest_routes.router)
app.include_router(portfolio_routes.router)
```

Add the import near the top with the other route imports, and one more
`include_router` line — the journal router is always mounted (unlike the
research-gated `portfolio_routes`, the journal is not behind a feature flag):

```python
# add near the other `from app.api import ...` imports
from app.journal import routes as journal_routes
```

```python
# add after the existing include_router calls
app.include_router(journal_routes.router)
```

The journal DB itself is lazily initialized on first request (via
`_get_sessionmaker()` in `routes.py`) rather than in `lifespan`, so a journal
bug can never block engine startup — this satisfies the design's "journal API
failures must never affect the trading loops" isolation rule more strongly
than an eager `lifespan` hook would.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/journal/ -v`
Expected: PASS (all journal tests, ~28 total)

Then run the full suite to confirm nothing else broke:

Run: `cd backend && .venv/bin/python -m pytest`
Expected: all prior tests still PASS (the journal package is additive; no
existing file was modified except `main.py`'s router registration, which adds
a line and doesn't touch the `lifespan` function other tests exercise).

- [ ] **Step 5: Commit**

```bash
git add backend/app/journal/schemas.py backend/app/journal/routes.py \
        backend/app/main.py backend/tests/journal/test_routes.py
git commit -m "feat(journal): REST API (trades/missed/views/stats/instruments) + mount router"
```

---

# Group B — Trade journal frontend

Ships on the **existing** Tailwind utility classes (`.card`, `.badge`, the
`text-muted`/`bg-panel`/`border-edge` tokens already used in every view — see
`frontend/src/index.css` and `frontend/src/views/TradesView.tsx` for the
pattern) so it's usable immediately; it gets the shadcn re-skin treatment in
Task F3's priority list, not before.

### Task B1: API client + types

**Files:**
- Modify: `frontend/src/lib/api.ts` (append — do not touch existing exports)
- Modify: `frontend/src/lib/types.ts` (append)

**Interfaces:**
- Produces: `JournalTradeDTO`, `JournalMissedDTO`, `JournalInstrumentDTO`,
  `JournalStatsDTO`, `JournalViewDTO` types; `getJournalInstruments()`,
  `getJournalTrades(openOnly?)`, `getJournalOpenTradesMtm()`, `addJournalTrade(body)`,
  `closeJournalTrade(id, body)`, `addJournalMissed(body)`, `getJournalMissed()`,
  `getJournalStats()`, `getJournalViews()`, `addJournalView(body)` functions.

- [ ] **Step 1: Add types**

Append to `frontend/src/lib/types.ts`:

```typescript
// Trade journal (backend/app/journal) — fully separate from the engine's
// PositionDTO/TradeDTO; never confuse the two.
export interface JournalInstrumentDTO {
  symbol: string
  exchange: string
  lot_size: number
  tick_size: number
  multiplier: number
  active: boolean
}

export interface JournalTradeDTO {
  id: number
  instrument_symbol: string
  direction: 'LONG' | 'SHORT'
  lots: number
  entry_price: number
  entry_time: string
  exit_price: number | null
  exit_time: string | null
  view_id: number
  setup_tag: string | null
  notes: string | null
  manual_net_pnl: number | null
  unrealized?: number | null
}

export interface JournalMissedDTO {
  id: number
  instrument_symbol: string
  direction: 'LONG' | 'SHORT'
  seen_at: string
  setup_tag: string | null
  skip_reason: string
  hypothetical_entry: number | null
  hypothetical_exit: number | null
  notes: string | null
}

export interface JournalViewDTO {
  id: number
  name: string
  thesis: string | null
  created_at: string
  retired_at: string | null
}

export interface JournalStatsDTO {
  by_tag: Record<string, { trades: number; wins: number; net_pnl: number }>
  by_view: Record<string, { trades: number; net_pnl: number }>
  missed_summary: { count: number; hypothetical_net_pnl: number }
}
```

- [ ] **Step 2: Add API functions**

Append to `frontend/src/lib/api.ts` (the file already exports a `j`/`post`
helper used by every other function — reuse them):

```typescript
// ── Trade journal (backend/app/journal — isolated from the engine) ─────────
export const getJournalInstruments = () => j('/api/journal/instruments')
export const getJournalTrades = (openOnly?: boolean) =>
  j(`/api/journal/trades${openOnly ? '?open_only=true' : ''}`)
export const getJournalOpenTradesMtm = () => j('/api/journal/trades/open-mtm')
export const addJournalTrade = (body: {
  symbol: string; direction: 'LONG' | 'SHORT'; lots: number; entry_price: number
  setup_tag?: string; notes?: string; view_id?: number
}) => post('/api/journal/trades', body)
export const closeJournalTrade = (
  id: number,
  body: { exit_price: number; manual_net_pnl?: number },
) => post(`/api/journal/trades/${id}/close`, body)
export const addJournalMissed = (body: {
  symbol: string; direction: 'LONG' | 'SHORT'; skip_reason: string
  setup_tag?: string; hypothetical_entry?: number; hypothetical_exit?: number
}) => post('/api/journal/missed', body)
export const getJournalMissed = () => j('/api/journal/missed')
export const getJournalStats = () => j('/api/journal/stats')
export const getJournalViews = () => j('/api/journal/views')
export const addJournalView = (body: { name: string; thesis?: string }) =>
  post('/api/journal/views', body)
```

- [ ] **Step 3: Verify typecheck passes**

Run: `cd frontend && npm run typecheck`
Expected: PASS (no errors — pure additions, `any`-typed `post`/`j` accept
these shapes without friction)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/lib/types.ts
git commit -m "feat(journal): frontend API client + DTO types"
```

---

### Task B2: JournalView component

**Files:**
- Create: `frontend/src/views/JournalView.tsx`

**Interfaces:**
- Consumes: everything from B1.

- [ ] **Step 1: Write the component**

```tsx
// frontend/src/views/JournalView.tsx
import { useEffect, useMemo, useState } from 'react'
import {
  getJournalInstruments, getJournalOpenTradesMtm, getJournalTrades,
  addJournalTrade, closeJournalTrade, addJournalMissed, getJournalMissed,
  getJournalStats,
} from '../lib/api'
import type {
  JournalInstrumentDTO, JournalTradeDTO, JournalMissedDTO, JournalStatsDTO,
} from '../lib/types'

const n = (v: number | null | undefined) => (v == null ? '—' : v.toFixed(2))
const pnlClass = (v: number | null | undefined) =>
  v == null ? 'text-muted' : v >= 0 ? 'text-emerald-400' : 'text-down'

function QuickAdd({ instruments, onAdded }: {
  instruments: JournalInstrumentDTO[]
  onAdded: () => void
}) {
  const [symbol, setSymbol] = useState(instruments[0]?.symbol ?? '')
  const [direction, setDirection] = useState<'LONG' | 'SHORT'>('LONG')
  const [lots, setLots] = useState('1')
  const [price, setPrice] = useState('')
  const [tag, setTag] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!symbol && instruments[0]) setSymbol(instruments[0].symbol)
  }, [instruments, symbol])

  const submit = async () => {
    if (!symbol || !price) return
    setBusy(true)
    try {
      await addJournalTrade({
        symbol, direction, lots: parseInt(lots, 10) || 1,
        entry_price: parseFloat(price), setup_tag: tag || undefined,
      })
      setPrice(''); setTag('')
      onAdded()
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="card p-3 flex flex-col gap-2">
      <div className="text-xs font-semibold text-muted">Quick add</div>
      <div className="grid grid-cols-2 gap-2">
        <select className="bg-panel2 border border-edge rounded px-2 py-1.5 text-sm"
          value={symbol} onChange={(e) => setSymbol(e.target.value)}>
          {instruments.map((i) => <option key={i.symbol} value={i.symbol}>{i.symbol}</option>)}
        </select>
        <div className="flex gap-1">
          {(['LONG', 'SHORT'] as const).map((d) => (
            <button key={d} onClick={() => setDirection(d)}
              className={`flex-1 rounded px-2 py-1.5 text-xs font-semibold border ${direction === d
                ? (d === 'LONG' ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                                  : 'bg-down/20 text-down border-down/40')
                : 'bg-panel2 text-muted border-edge'}`}>{d}</button>
          ))}
        </div>
        <input className="bg-panel2 border border-edge rounded px-2 py-1.5 text-sm"
          placeholder="lots" inputMode="numeric" value={lots}
          onChange={(e) => setLots(e.target.value)} />
        <input className="bg-panel2 border border-edge rounded px-2 py-1.5 text-sm"
          placeholder="entry price" inputMode="decimal" value={price}
          onChange={(e) => setPrice(e.target.value)} />
        <input className="col-span-2 bg-panel2 border border-edge rounded px-2 py-1.5 text-sm"
          placeholder="setup tag (optional)" value={tag}
          onChange={(e) => setTag(e.target.value)} />
      </div>
      <button onClick={submit} disabled={busy || !symbol || !price}
        className="rounded px-3 py-1.5 text-xs font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 disabled:opacity-40">
        {busy ? 'Adding…' : 'Log trade'}
      </button>
    </div>
  )
}

function OpenTrades({ trades, onClosed }: {
  trades: JournalTradeDTO[]
  onClosed: () => void
}) {
  const [closingId, setClosingId] = useState<number | null>(null)
  const [exitPrice, setExitPrice] = useState('')

  const submitClose = async (id: number) => {
    if (!exitPrice) return
    await closeJournalTrade(id, { exit_price: parseFloat(exitPrice) })
    setClosingId(null); setExitPrice('')
    onClosed()
  }

  if (!trades.length) {
    return <div className="card p-3 text-xs text-muted">No open journal trades.</div>
  }
  return (
    <div className="card p-3 flex flex-col gap-2">
      <div className="text-xs font-semibold text-muted">Open ({trades.length})</div>
      {trades.map((t) => (
        <div key={t.id} className="flex items-center gap-2 text-sm border-b border-edge/60 pb-2 last:border-0 last:pb-0">
          <span className="badge bg-panel2 text-muted">{t.instrument_symbol}</span>
          <span className={`text-xs font-semibold ${t.direction === 'LONG' ? 'text-emerald-400' : 'text-down'}`}>
            {t.direction}
          </span>
          <span className="text-xs text-muted">{t.lots} lot @ {n(t.entry_price)}</span>
          <span className={`ml-auto text-xs font-semibold ${pnlClass(t.unrealized)}`}>
            {t.unrealized == null ? 'MTM —' : `₹${n(t.unrealized)}`}
          </span>
          {closingId === t.id ? (
            <div className="flex gap-1">
              <input className="w-20 bg-panel2 border border-edge rounded px-1.5 py-1 text-xs"
                placeholder="exit" inputMode="decimal" value={exitPrice}
                onChange={(e) => setExitPrice(e.target.value)} />
              <button onClick={() => submitClose(t.id)}
                className="text-xs px-2 py-1 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
                ✓
              </button>
            </div>
          ) : (
            <button onClick={() => setClosingId(t.id)}
              className="text-xs px-2 py-1 rounded bg-panel2 text-muted border border-edge hover:text-zinc-200">
              Close
            </button>
          )}
        </div>
      ))}
    </div>
  )
}

function MissedQuickAdd({ instruments, onAdded }: {
  instruments: JournalInstrumentDTO[]
  onAdded: () => void
}) {
  const [symbol, setSymbol] = useState('')
  const [direction, setDirection] = useState<'LONG' | 'SHORT'>('LONG')
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async () => {
    if (!symbol || !reason) return
    setBusy(true)
    try {
      await addJournalMissed({ symbol, direction, skip_reason: reason })
      setReason('')
      onAdded()
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="card p-3 flex flex-col gap-2">
      <div className="text-xs font-semibold text-muted">Log a missed setup</div>
      <div className="grid grid-cols-2 gap-2">
        <select className="bg-panel2 border border-edge rounded px-2 py-1.5 text-sm"
          value={symbol} onChange={(e) => setSymbol(e.target.value)}>
          <option value="">instrument…</option>
          {instruments.map((i) => <option key={i.symbol} value={i.symbol}>{i.symbol}</option>)}
        </select>
        <div className="flex gap-1">
          {(['LONG', 'SHORT'] as const).map((d) => (
            <button key={d} onClick={() => setDirection(d)}
              className={`flex-1 rounded px-2 py-1.5 text-xs font-semibold border ${direction === d
                ? 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                : 'bg-panel2 text-muted border-edge'}`}>{d}</button>
          ))}
        </div>
        <input className="col-span-2 bg-panel2 border border-edge rounded px-2 py-1.5 text-sm"
          placeholder="why skipped?" value={reason} onChange={(e) => setReason(e.target.value)} />
      </div>
      <button onClick={submit} disabled={busy || !symbol || !reason}
        className="rounded px-3 py-1.5 text-xs font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/40 disabled:opacity-40">
        {busy ? 'Adding…' : 'Log missed setup'}
      </button>
    </div>
  )
}

export default function JournalView() {
  const [instruments, setInstruments] = useState<JournalInstrumentDTO[]>([])
  const [openTrades, setOpenTrades] = useState<JournalTradeDTO[]>([])
  const [closedTrades, setClosedTrades] = useState<JournalTradeDTO[]>([])
  const [missed, setMissed] = useState<JournalMissedDTO[]>([])
  const [stats, setStats] = useState<JournalStatsDTO | null>(null)

  const reload = () => {
    getJournalInstruments().then((d) => setInstruments(d.instruments || [])).catch(() => {})
    getJournalOpenTradesMtm().then((d) => setOpenTrades(d.trades || [])).catch(() => {})
    getJournalTrades().then((d) =>
      setClosedTrades((d.trades || []).filter((t: JournalTradeDTO) => t.exit_price != null))
    ).catch(() => {})
    getJournalMissed().then((d) => setMissed(d.missed || [])).catch(() => {})
    getJournalStats().then(setStats).catch(() => {})
  }

  useEffect(() => {
    reload()
    const t = setInterval(reload, 15000)
    return () => clearInterval(t)
  }, [])

  const tagRows = useMemo(() => Object.entries(stats?.by_tag ?? {}), [stats])

  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <QuickAdd instruments={instruments} onAdded={reload} />
        <MissedQuickAdd instruments={instruments} onAdded={reload} />
      </div>

      <OpenTrades trades={openTrades} onClosed={reload} />

      {stats && (
        <div className="card p-3 flex flex-col gap-2">
          <div className="text-xs font-semibold text-muted">By tag</div>
          {tagRows.length === 0 && <div className="text-xs text-muted">No closed trades yet.</div>}
          {tagRows.map(([tag, row]) => (
            <div key={tag} className="flex items-center gap-2 text-sm">
              <span className="badge bg-panel2 text-muted">{tag}</span>
              <span className="text-xs text-muted">{row.trades} trades, {row.wins} wins</span>
              <span className={`ml-auto text-xs font-semibold ${pnlClass(row.net_pnl)}`}>
                ₹{n(row.net_pnl)}
              </span>
            </div>
          ))}
          <div className="border-t border-edge/60 pt-2 text-xs text-muted">
            Missed setups: {stats.missed_summary.count}
            {stats.missed_summary.count > 0 && (
              <> — hypothetical net{' '}
                <span className={pnlClass(stats.missed_summary.hypothetical_net_pnl)}>
                  ₹{n(stats.missed_summary.hypothetical_net_pnl)}
                </span>
              </>
            )}
          </div>
        </div>
      )}

      <div className="card p-3 flex flex-col gap-2">
        <div className="text-xs font-semibold text-muted">Closed ({closedTrades.length})</div>
        {closedTrades.slice(0, 30).map((t) => (
          <div key={t.id} className="flex items-center gap-2 text-sm border-b border-edge/60 pb-1.5 last:border-0">
            <span className="badge bg-panel2 text-muted">{t.instrument_symbol}</span>
            <span className={`text-xs font-semibold ${t.direction === 'LONG' ? 'text-emerald-400' : 'text-down'}`}>
              {t.direction}
            </span>
            <span className="text-xs text-muted">{n(t.entry_price)} → {n(t.exit_price)}</span>
            {t.setup_tag && <span className="badge bg-panel2 text-muted">{t.setup_tag}</span>}
          </div>
        ))}
      </div>

      {missed.length > 0 && (
        <div className="card p-3 flex flex-col gap-2">
          <div className="text-xs font-semibold text-muted">Missed setups ({missed.length})</div>
          {missed.slice(0, 20).map((m) => (
            <div key={m.id} className="flex items-center gap-2 text-sm border-b border-edge/60 pb-1.5 last:border-0">
              <span className="badge bg-panel2 text-muted">{m.instrument_symbol}</span>
              <span className={`text-xs font-semibold ${m.direction === 'LONG' ? 'text-emerald-400' : 'text-down'}`}>
                {m.direction}
              </span>
              <span className="text-xs text-muted flex-1">{m.skip_reason}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verify typecheck passes**

Run: `cd frontend && npm run typecheck`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/JournalView.tsx
git commit -m "feat(journal): JournalView — quick-add, open MTM, missed setups, tag stats"
```

---

### Task B3: Wire the Journal tab into App.tsx

**Files:**
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `JournalView` (B2, default export).

- [ ] **Step 1: Add the import and tab entry**

```tsx
// frontend/src/App.tsx — add near the other view imports
import JournalView from './views/JournalView'
```

Add `['journal', 'Journal']` to the `TABS` array, right after `['positions', 'Active Positions']`
(so it's prominent, matching the design doc's priority-3 placement ahead of
Backtests/Trades/Dashboard):

```tsx
const TABS: [string, string][] = [
  ['watchlist', 'Watchlist'],
  ['positions', 'Active Positions'],
  ['journal', 'Journal'],
  ['engine', 'Engine / Logs'],
  ['options', 'Options Calc'],
  ['backtests', 'Backtests'],
  ['portfolio', 'Portfolio'],
  ['trades', 'Trade Log'],
  ['calendar', 'Calendar'],
  ['dashboard', 'Dashboard'],
  ['settings', 'Settings'],
]
```

Add the render branch next to the other `{tab === '...' && <...>}` lines:

```tsx
{tab === 'journal' && <JournalView />}
```

- [ ] **Step 2: Verify typecheck and build pass**

Run: `cd frontend && npm run typecheck && npm run build`
Expected: both PASS

- [ ] **Step 3: Manual smoke check**

Run: `cd frontend && npm run dev` (and, in another terminal, start the backend
per `CLAUDE.md` if not already running) — open the app, click the **Journal**
tab, confirm the instrument dropdown is populated (GOLDM/SILVERM/CRUDEOILM/
NATGASM) and a quick-add trade appears in **Open** immediately after
submitting. Stop the dev server when done (`Ctrl-C`) — do not leave a local
engine running per the "run the bot on the VPS, not the Mac" convention in
memory; if a local backend was started only for this smoke check, stop it too.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat(journal): wire Journal tab into the app shell"
```

---

# Group C — Purple SL/TP tiering

### Task C1: Purple SL/TP config knobs + entry-time binding columns

**Files:**
- Modify: `backend/app/core/config.py` (add two knobs near `intraday_purple_margin`)
- Modify: `backend/app/core/runtime_config.py` (register in `OVERRIDABLE` + `BOUNDS`)
- Modify: `backend/app/db/models.py` (add two nullable columns to `Position`)
- Modify: `backend/app/db/session.py` (`_migrate_schema` — add the two columns)
- Test: `backend/tests/test_migration.py` (extend existing assertions)
- Test: `backend/tests/journal/../test_purple_sltp.py` → actually:
  `backend/tests/test_purple_sltp.py` (new file)

**Interfaces:**
- Produces: `Settings.intraday_purple_stop_loss_pct: float = 0.015`,
  `Settings.intraday_purple_target_pct: float = 0.03`,
  `Position.entry_sl_pct: float | None`, `Position.entry_tp_pct: float | None`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_purple_sltp.py
"""Purple-flagged intraday names get wider SL/TP (owner: 1.5%/3% vs 1%/2%
normal), frozen onto the position at entry so a mid-trade flag toggle can't
reshape an open trade."""
from app.core.config import Settings


def test_purple_sltp_defaults_exist_and_are_wider_than_normal():
    s = Settings()
    assert s.intraday_purple_stop_loss_pct == 0.015
    assert s.intraday_purple_target_pct == 0.03
    assert s.intraday_purple_stop_loss_pct > s.intraday_stop_loss_pct
    assert s.intraday_purple_target_pct > s.intraday_target_pct
```

```python
# append to backend/tests/test_migration.py, inside test_migration_adds_missing_columns,
# right after the existing `pos = {...}` assertion block:
    assert {"entry_sl_pct", "entry_tp_pct"} <= pos
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/python -m pytest tests/test_purple_sltp.py tests/test_migration.py -v`
Expected: FAIL (`AttributeError: 'Settings' object has no attribute
'intraday_purple_stop_loss_pct'`; migration assertion `KeyError`)

- [ ] **Step 3: Write minimal implementation**

In `backend/app/core/config.py`, right after the `intraday_purple_margin` line
(`config.py:175`) and before `intraday_leverage`:

```python
    intraday_purple_margin: float = 8_000.0    # target REAL margin for a purple-flagged priority name
    # purple SL/TP tiering: purple names are higher-conviction and more volatile
    # than the rest of the watchlist (owner, 2026-07-17) — they get wider bands so
    # normal intraday noise doesn't stop them out. Frozen onto Position.entry_sl_pct/
    # entry_tp_pct AT ENTRY (see equity_entry.py/broker.py) so a mid-trade purple-flag
    # toggle never reshapes an already-open position.
    intraday_purple_stop_loss_pct: float = 0.015   # purple equity SL, fraction of entry price
    intraday_purple_target_pct: float = 0.03       # purple equity TP, fraction of entry price
    intraday_leverage: float = 2.5             # FALLBACK leverage estimate only (real margin governs live)
```

In `backend/app/core/runtime_config.py`, add to `OVERRIDABLE` right after
`"intraday_stop_loss_pct", "intraday_target_pct",`:

```python
    "intraday_stop_loss_pct", "intraday_target_pct",
    "intraday_purple_stop_loss_pct", "intraday_purple_target_pct",
```

Find the `BOUNDS` dict (same file) and add matching entries next to the
existing `intraday_stop_loss_pct`/`intraday_target_pct` bounds — locate them
with `grep -n '"intraday_stop_loss_pct":' backend/app/core/runtime_config.py`
and add immediately after in the same style, e.g.:

```python
    "intraday_purple_stop_loss_pct": (0.001, 0.20),
    "intraday_purple_target_pct": (0.001, 0.50),
```

(Use the exact same bound style/values as the existing
`intraday_stop_loss_pct`/`intraday_target_pct` entries — read them first and
mirror the tuple shape; the values above are placeholders only if those two
keys don't already exist with bounds — if they do, copy their exact numbers.)

In `backend/app/db/models.py`, inside the `Position` class, add right after
the existing `target_price` column:

```python
    stop_price: Mapped[float] = mapped_column(Float)        # premium floor (SL)
    target_price: Mapped[float] = mapped_column(Float)      # premium ceiling (TP)
    # purple SL/TP tiering (2026-07-17): the SL/TP *percentages* this equity_intraday
    # position was opened with, frozen at entry. NULL for options positions and for
    # legacy equity rows predating this feature — both fall back to the current global
    # intraday_stop_loss_pct/intraday_target_pct knobs at ratchet time.
    entry_sl_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    entry_tp_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
```

In `backend/app/db/session.py`, inside `_migrate_schema`'s `additions` dict,
find the `"positions": [...]` list and append:

```python
        "positions": [
            ("segment", "VARCHAR(16) DEFAULT 'options'"),
            # ... existing entries stay as-is ...
            ("entry_sl_pct", "FLOAT"),
            ("entry_tp_pct", "FLOAT"),
        ],
```

(Insert the two new tuples at the end of the existing `"positions"` list —
don't reorder or remove any existing entry in that list.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_purple_sltp.py tests/test_migration.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/config.py backend/app/core/runtime_config.py \
        backend/app/db/models.py backend/app/db/session.py \
        backend/tests/test_purple_sltp.py backend/tests/test_migration.py
git commit -m "feat(engine): purple SL/TP knobs + entry-time-frozen Position columns"
```

---

### Task C2: Wire purple SL/TP through entry and the lockstep ratchet

**Files:**
- Modify: `backend/app/engine/broker.py` (`open_equity_position` — accept/persist the pair)
- Modify: `backend/app/engine/runner.py` (intraday entry branch resolves the pair by
  `pick.is_purple`; `_apply_lockstep` reads the frozen pair)
- Test: `backend/tests/test_purple_sltp.py` (extend)

**Interfaces:**
- Consumes: `Position.entry_sl_pct`/`entry_tp_pct` (C1);
  `equity_stop_target(direction, entry, sl_pct, tp_pct) -> (stop, target)`
  (existing, `app/engine/equity_entry.py:48`); `lockstep_band(...)` (existing,
  `app/engine/equity_entry.py:116`, unchanged signature).
- Produces: `PaperBroker.open_equity_position(..., sl_pct: float | None = None,
  tp_pct: float | None = None)` (new optional kwargs, default `None` → current
  params lookup, so every existing call site is unaffected).

- [ ] **Step 1: Write the failing tests**

```python
# append to backend/tests/test_purple_sltp.py
import datetime as dt

from app.core.instruments import get_instrument
from app.engine.broker import PaperBroker
from app.db.session import init_db, SessionLocal


def _broker():
    init_db(reset=True)
    s = SessionLocal()
    return PaperBroker(s), s


def test_purple_entry_gets_wider_band_and_persists_pcts():
    broker, s = _broker()
    inst = get_instrument("GOLDM")  # any seed instrument works; segment irrelevant here
    now = dt.datetime(2026, 7, 17, 10, 0)
    pos = broker.open_equity_position(
        inst, "LONG", price=100.0, qty=10, charge_segment="MCX_INTRADAY",
        reason="test", now=now, sl_pct=0.015, tp_pct=0.03)
    assert pos.entry_sl_pct == 0.015
    assert pos.entry_tp_pct == 0.03
    assert pos.stop_price == pytest_approx(100.0 * 0.985)
    assert pos.target_price == pytest_approx(100.0 * 1.03)


def test_normal_entry_leaves_pcts_none_and_uses_global_defaults():
    broker, s = _broker()
    inst = get_instrument("GOLDM")
    now = dt.datetime(2026, 7, 17, 10, 0)
    pos = broker.open_equity_position(
        inst, "LONG", price=100.0, qty=10, charge_segment="MCX_INTRADAY",
        reason="test", now=now)   # no sl_pct/tp_pct passed — legacy call shape
    assert pos.entry_sl_pct is None
    assert pos.entry_tp_pct is None
    assert pos.stop_price == pytest_approx(100.0 * 0.99)   # default intraday_stop_loss_pct


def pytest_approx(x):
    import pytest
    return pytest.approx(x, rel=1e-6)
```

Also add a lockstep-wiring test:

```python
# append to backend/tests/test_purple_sltp.py
def test_lockstep_uses_frozen_purple_pcts_not_global_defaults():
    """A purple position's ratchet must derive its initial band from the FROZEN
    entry_sl_pct/entry_tp_pct, not whatever the global intraday_stop_loss_pct
    happens to be right now — this is what makes a mid-trade flag toggle inert."""
    from app.engine.equity_entry import lockstep_band
    # purple band: 1.5% SL / 3% TP, frozen; global knobs simulate having since
    # changed to something else entirely (0.01/0.02) to prove the frozen pcts win.
    entry, qty, margin = 100.0, 10, 1000.0
    stop, target = lockstep_band(
        "LONG", entry, qty, margin, entry * 0.985, entry * 1.03, price=entry,
        trigger_pct=0.02, sl_pct=0.015, tp_pct=0.03,   # <- must be the FROZEN pair
        breakeven_price=entry)
    assert stop == pytest_approx(entry * 0.985)
    assert target == pytest_approx(entry * 1.03)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/python -m pytest tests/test_purple_sltp.py -v`
Expected: FAIL (`TypeError: open_equity_position() got an unexpected keyword
argument 'sl_pct'`)

- [ ] **Step 3: Write minimal implementation**

In `backend/app/engine/broker.py`, modify `open_equity_position`'s signature
and body (`broker.py:93-137`):

```python
    def open_equity_position(self, inst: Instrument, direction: str, price: float,
                             qty: int, charge_segment: str, reason: str,
                             now: dt.datetime, params: dict | None = None,
                             strategy_key: str | None = None,
                             margin: float | None = None,
                             sl_pct: float | None = None,
                             tp_pct: float | None = None) -> Position:
        """Open an intraday equity (MIS) position of `qty` shares at `price`.

        MIS is leveraged: only the MARGIN leaves cash, not the full notional — but P&L
        is on the full share move. We store entry_cost = margin + entry charges (the
        actual cash out), so the ledger reconciliation invariant holds exactly. When the
        caller supplies `margin` (fix A: the REAL Zerodha `order_margins` figure the
        position was sized to) we book that; otherwise we fall back to notional/leverage.
        SL/TP are direction-aware (a SHORT's stop is above entry). `sl_pct`/`tp_pct`, when
        given (purple-tiered entries), are frozen onto the row (entry_sl_pct/entry_tp_pct)
        so a later flag toggle can never reshape this position; omitted (the legacy shape)
        falls back to the global intraday_stop_loss_pct/intraday_target_pct and leaves the
        columns NULL. Charges use the intraday charge segment (NSE_INTRADAY/BSE_INTRADAY)."""
        p = params if params is not None else effective(self.settings)
        leverage = p.get("intraday_leverage", 2.5) or 2.5
        eff_sl_pct = sl_pct if sl_pct is not None else p.get("intraday_stop_loss_pct", 0.01)
        eff_tp_pct = tp_pct if tp_pct is not None else p.get("intraday_target_pct", 0.02)
        notional = price * qty
        margin = margin if (margin is not None and margin > 0) else notional / leverage
        charges = compute_charges(charge_segment, "BUY", price, qty)["total"]
        cost = margin + charges
        stop, target = equity_stop_target(direction, price, eff_sl_pct, eff_tp_pct)

        cap = self.capital()
        cap.cash -= cost
        cap.updated_at = now

        pos = Position(
            instrument_key=inst.key, direction=direction, option_type="EQ",
            tradingsymbol=getattr(inst, "spot_symbol", "") or inst.key,
            exchange=charge_segment, segment="equity_intraday", strategy_key=strategy_key,
            strike=0.0, expiry=now.date(), lot_size=qty, qty=qty, entry_premium=price,
            entry_charges=charges, entry_cost=cost, entry_spot=price, entry_time=now,
            entry_reason=reason, stop_price=stop, target_price=target,
            entry_sl_pct=sl_pct, entry_tp_pct=tp_pct,
            last_premium=price, last_spot=price, last_mark_time=now,
            high_water_premium=price, mode=self.MODE)
        self.s.add(pos)
        self.s.commit()
        purple_note = f" — purple band SL {eff_sl_pct:.1%} / TP {eff_tp_pct:.1%}" if sl_pct is not None else ""
        log.trade(
            f"OPEN EQUITY {direction} {pos.tradingsymbol} {qty}@{price:.2f} "
            f"— margin ₹{margin:,.0f} (chg ₹{charges:.0f}); SL {stop:.2f} / TP {target:.2f}"
            f"{purple_note}",
            instrument=inst.key, event="OPEN_EQUITY", tradingsymbol=pos.tradingsymbol,
            premium=price, cost=round(cost, 2))
        return pos
```

Now wire the caller. In `backend/app/engine/runner.py`, inside
`process_entries`'s intraday branch (around `runner.py:950-965`, right after
`inst, direction = eq_meta[pickk.instrument_key]`), resolve the pair and pass
it through:

```python
                for pickk in sel.selected:
                    if not self.armed:   # #8 defense-in-depth: disarm may have landed mid-cycle
                        log.warn("DISARMED mid-cycle — aborting remaining intraday entries",
                                 event="ARM_RECHECK_ABORT")
                        break
                    inst, direction = eq_meta[pickk.instrument_key]
                    seg = _equity_charge_segment(inst)
                    sl_pct = (self.params.get("intraday_purple_stop_loss_pct", 0.015)
                              if pickk.is_purple else None)
                    tp_pct = (self.params.get("intraday_purple_target_pct", 0.03)
                              if pickk.is_purple else None)
                    log.info(f"INTRADAY {pickk.direction} {pickk.instrument_key} "
                             f"{pickk.qty}@{pickk.price:.2f} (margin ₹{pickk.margin:,.0f}"
                             f"{', purple' if pickk.is_purple else ''})",
```

Find the actual `self.broker.open_equity_position(...)` call a few lines below
that (still inside this same loop) and add the two kwargs:

```python
                    pos = self.broker.open_equity_position(
                        inst, pickk.direction, pickk.price, pickk.qty, seg,
                        pick.reason if False else "INTRADAY_ENTRY",  # placeholder — DO NOT use this line
                        now, self.params, strategy_key=self.strategy_keys.get(pickk.instrument_key),
                        margin=pickk.margin, sl_pct=sl_pct, tp_pct=tp_pct)
```

**Important:** the exact existing call to `open_equity_position` in this loop
must be read from the live file first (`grep -n
"open_equity_position" backend/app/engine/runner.py`) and edited **in place**
— do not replace its `reason`/other positional args with the placeholder
above; only **add** `sl_pct=sl_pct, tp_pct=tp_pct` to the existing call's
keyword arguments, preserving every other argument exactly as it is today.

Finally, wire `_apply_lockstep` (`runner.py:504-525`) to prefer the frozen
per-position pcts:

```python
    def _apply_lockstep(self, pos) -> None:
        """Lockstep band: once an equity position is in profit, ratchet its stop AND
        target together (break-even floored). A hand-pinned target is left in place;
        only the stop slides then. `pos.entry_sl_pct`/`entry_tp_pct` (purple tiering,
        2026-07-17), when set, override the global knobs so a purple position's band
        never reshapes if the global intraday_stop_loss_pct/intraday_target_pct or the
        purple flag itself changes after entry."""
        self.broker.ensure_stop_protection(pos, pos.last_premium)  # self-heal a missing backstop every tick
        from app.engine.equity_entry import lockstep_band
        p = self.params
        if not p.get("intraday_lockstep_enabled", True):
            return
        last = pos.last_premium or pos.entry_premium
        margin = pos.entry_cost - pos.entry_charges
        rt = (2.0 * pos.entry_charges / pos.qty) if pos.qty else 0.0   # round-trip cost/share
        be = pos.entry_premium + rt if pos.direction == "LONG" else pos.entry_premium - rt
        sl_pct = pos.entry_sl_pct if pos.entry_sl_pct is not None else p.get("intraday_stop_loss_pct", 0.01)
        tp_pct = pos.entry_tp_pct if pos.entry_tp_pct is not None else p.get("intraday_target_pct", 0.02)
        new_stop, new_target = lockstep_band(
            pos.direction, pos.entry_premium, pos.qty, margin,
            pos.stop_price, pos.target_price, last,
            trigger_pct=p.get("intraday_lockstep_trigger_pct", 0.02),
            sl_pct=sl_pct, tp_pct=tp_pct,
            breakeven_price=be, rt_per_share=rt,
            profit_lock_threshold=p.get("intraday_profit_lock_threshold", 200.0),
            profit_lock_frac=p.get("intraday_profit_lock_frac", 0.5))
```

(The rest of `_apply_lockstep` below this point is unchanged.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_purple_sltp.py tests/test_equity_entry.py tests/test_intraday_controls.py tests/test_intraday_real_margin.py -v`
Expected: PASS (no existing intraday test asserts a specific
`open_equity_position` call signature that would break from adding optional
kwargs — if one does, it's asserting positional args; fix that call site to
keep passing, don't change the test's intent).

Then the full suite + ledger invariant:

Run: `cd backend && .venv/bin/python -m pytest && .venv/bin/python scripts/dryrun.py 700`
Expected: full suite PASS; dry-run prints `LEDGER OK` (diff `0`).

- [ ] **Step 5: Commit**

```bash
git add backend/app/engine/broker.py backend/app/engine/runner.py \
        backend/tests/test_purple_sltp.py
git commit -m "feat(engine): purple intraday entries get 1.5%/3% SL/TP, frozen at entry"
```

---

# Group D — Residual autopsy fixes

### Task D1: Short-circuit the per-instrument token-auth error storm

**Files:**
- Modify: `backend/app/engine/runner.py` (wherever the signal loop iterates
  instruments calling `provider.get_candles`/`get_ltp` — locate with
  `grep -n "def scan_signals" backend/app/engine/runner.py`)
- Test: `backend/tests/test_token_storm_suppression.py`

**Interfaces:**
- Consumes: the provider's existing auth-failure exception shape (Kite raises
  a `TokenException` or a generic exception whose message contains `"Incorrect
  api_key"`/`"access_token"` — confirm the exact exception class via
  `grep -rn "TokenException\|Incorrect \`api_key\`" backend/app/providers/`
  before writing the classifier, since the autopsy evidence quotes the Kite
  SDK's literal error string).
- Produces: `runner._token_bad_until: datetime | None` instance state;
  `runner._is_token_probably_bad(now) -> bool`; the scan loop logs ONE
  suppression line and skips per-instrument fetches while latched, retrying a
  single probe instrument per loop to detect recovery.

- [ ] **Step 1: Investigate the exact exception shape first**

Run: `cd backend && grep -n "class.*Exception\|TokenException" app/providers/kite_provider.py app/providers/*.py 2>/dev/null`
and `grep -n "Incorrect \`api_key\`\|access_token" app/providers/*.py`

Read the surrounding 10-15 lines of whatever `get_candles`/`get_ltp` do on
failure in `app/providers/kite_provider.py` to confirm whether the caller
(`runner.scan_signals`) already catches a broad `Exception` per-instrument (it
must, since the autopsy shows the engine survives the storm and keeps
looping) — find that except block with
`grep -n "except Exception" backend/app/engine/runner.py` near the candle-fetch
call sites. **This step has no code to write** — it is required investigation
before Step 3, since the fix must classify the SAME exception the existing
broad catch already swallows, not invent a new one.

- [ ] **Step 2: Write the failing test**

```python
# backend/tests/test_token_storm_suppression.py
"""Autopsy rank 5: ~3,800 unbacked-off 'Incorrect api_key or access_token'
lines/morning. A known-bad token should short-circuit the per-instrument sweep
to one probe/loop instead of hammering every instrument every cycle."""
import datetime as dt

from app.engine.runner import EngineRunner


def _runner():
    from app.db.session import init_db
    init_db(reset=True)
    return EngineRunner()


def test_token_latch_starts_clear():
    r = _runner()
    assert r._is_token_probably_bad(dt.datetime.now()) is False


def test_token_latch_engages_and_expires():
    r = _runner()
    now = dt.datetime.now()
    r._mark_token_bad(now)
    assert r._is_token_probably_bad(now) is True
    # a fresh success clears the latch immediately (mirrors the proven
    # margins()-suppression pattern's "recovered" behavior)
    r._mark_token_ok()
    assert r._is_token_probably_bad(now) is False
```

(This test targets the two new small helper methods directly — the full
scan-loop integration is exercised indirectly by the existing
`test_intraday_controls.py`/dry-run suite, which must keep passing after the
wiring in Step 3; no new integration test is needed since the classifier
plugs into an existing, already-tested per-instrument except block.)

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_token_storm_suppression.py -v`
Expected: FAIL (`AttributeError: 'EngineRunner' object has no attribute
'_is_token_probably_bad'`)

- [ ] **Step 4: Write minimal implementation**

Add near `EngineRunner.__init__`'s other instance-state initializations
(`grep -n "def __init__" backend/app/engine/runner.py` to find it):

```python
        self._token_bad_until: dt.datetime | None = None
```

Add two small helpers near `_maybe_reconcile_orphans` or another small
private helper method (keep them together, same class):

```python
    def _is_token_probably_bad(self, now: dt.datetime) -> bool:
        return self._token_bad_until is not None and now < self._token_bad_until

    def _mark_token_bad(self, now: dt.datetime, cooldown_seconds: float = 20.0) -> None:
        self._token_bad_until = now + dt.timedelta(seconds=cooldown_seconds)

    def _mark_token_ok(self) -> None:
        self._token_bad_until = None
```

Now wire it into the scan loop. Locate the per-instrument candle-fetch except
block found in Step 1 (inside `scan_signals` or whatever it calls per
instrument) and change it from unconditionally calling the provider for every
instrument to checking the latch first, e.g. (adapt to the ACTUAL loop
structure found in Step 1 — this is the shape, not a literal diff):

```python
        now = self.provider.now()
        if self._is_token_probably_bad(now):
            # one probe instrument per loop to detect recovery, instead of every
            # instrument hammering historical_data/margins with the same dead token
            probe_key = next(iter(self.instruments), None)
            if probe_key is not None:
                try:
                    self.provider.get_ltp(get_instrument(probe_key))
                    self._mark_token_ok()
                    log.info("token recovered — resuming full market-data sweep",
                             event="TOKEN_RECOVERED")
                except Exception:
                    pass  # still bad — stay latched, suppressed until next loop's probe
            if self._is_token_probably_bad(now):
                log.warn("token invalid — pausing market-data sweep until re-auth",
                         event="TOKEN_SUSPEND_SWEEP")
                return  # skip the rest of this scan iteration entirely
```

Insert this check at the TOP of the per-instrument loop body (or the top of
`scan_signals`, whichever the Step 1 investigation shows is the right scope —
it must gate every instrument's `get_candles` call, not just some). Inside the
existing per-instrument `except Exception as e:` block that today just logs
and continues, add the classification that engages the latch:

```python
        except Exception as e:
            msg = str(e)
            if "Incorrect" in msg and ("api_key" in msg or "access_token" in msg):
                self._mark_token_bad(self.provider.now())
            log.error(f"[{key}] historical_data failed: {e}", instrument=key)
            continue
```

(Match this to the real variable names/log call already in that except block
— only add the two-line classification check before the existing log call,
don't restructure anything else in it.)

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_token_storm_suppression.py -v`
Expected: PASS

Then the full suite:

Run: `cd backend && .venv/bin/python -m pytest`
Expected: PASS (the mock provider never raises an auth error, so this path is
inert in every existing test — confirms zero regression risk)

- [ ] **Step 6: Commit**

```bash
git add backend/app/engine/runner.py backend/tests/test_token_storm_suppression.py
git commit -m "fix(logging): latch a bad Kite token — one probe/loop instead of hammering every instrument"
```

---

### Task D2: Enable `max_open_drawdown` (H15) with a sane default

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/frontend/src/views/SettingsView.tsx` → actually
  `frontend/src/views/SettingsView.tsx` (help text)
- Test: `backend/tests/test_max_open_drawdown.py`

**Interfaces:**
- Consumes: existing `max_open_drawdown` knob (already wired into the halt
  logic per `audit-fix-tracker.md`'s H15 entry — this task only changes the
  **default value** from `0.0` (off) to `2500.0`; verify the halt logic itself
  already exists with `grep -rn "max_open_drawdown" backend/app/engine/`).

- [ ] **Step 1: Confirm the halt logic already consumes this knob**

Run: `cd backend && grep -rn "max_open_drawdown" app/engine/*.py`

If a halt check already reads `self.params.get("max_open_drawdown", ...)` or
`p["max_open_drawdown"]` somewhere (e.g. in `_entries_halted`/`halt_status`),
this task is a **pure default-value + docs change** — no new halt logic
needed, matching the design doc ("knob exists... already live-editable").

- [ ] **Step 2: Write the failing test**

```python
# backend/tests/test_max_open_drawdown.py
from app.core.config import Settings


def test_max_open_drawdown_default_is_no_longer_zero():
    """H15 (pre-live audit): the guard existed but shipped disabled (0 = off).
    Owner default: half the ₹5k daily-loss halt, since open MTM bleeds faster
    than realized P&L."""
    s = Settings()
    assert s.max_open_drawdown == 2500.0
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_max_open_drawdown.py -v`
Expected: FAIL (`assert 0.0 == 2500.0`)

- [ ] **Step 4: Write minimal implementation**

In `backend/app/core/config.py` at line 147:

```python
    max_open_drawdown: float = 2_500.0         # halt NEW entries once today's REALIZED + UNREALIZED (open MTM) loss breaches this (0 = off; H15, enabled 2026-07-17 — half the ₹5k daily-loss halt since open MTM bleeds faster than realized)
```

In `frontend/src/views/SettingsView.tsx`, find the label/help entry for
`max_open_drawdown` (`grep -n "max_open_drawdown" frontend/src/views/SettingsView.tsx`)
and update its help text to note the new default and rationale, mirroring the
existing style of neighboring entries (e.g. the `intraday_max_positions` help
string quoted in the design doc's research). If no entry exists yet for this
key, add one next to `max_daily_loss`'s entry using the same object shape.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_max_open_drawdown.py -v`
Expected: PASS

Then: `cd backend && .venv/bin/python -m pytest` (full suite) and
`cd frontend && npm run typecheck`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/config.py frontend/src/views/SettingsView.tsx \
        backend/tests/test_max_open_drawdown.py
git commit -m "fix(engine): enable max_open_drawdown (H15) at a ₹2,500 default"
```

---

### Task D3: Demote polling-route access logs + rate-limit repeated SL-M failures

**Files:**
- Modify: `backend/app/main.py` (uvicorn access-log filter)
- Modify: `backend/app/core/logging.py` (or wherever `log.error` lives —
  `grep -n "^def error\|^class.*Log" backend/app/core/logging.py`)
- Test: `backend/tests/test_log_noise_reduction.py`

**Interfaces:**
- Produces: a `logging.Filter` subclass suppressing uvicorn access-log lines
  for `/api/execution/state`, `/api/status`, `/api/signals` to DEBUG level (or
  drop entirely from the access logger — filter approach keeps them
  retrievable if ever needed); `log.error_ratelimited(message, key, event=...,
  window_seconds=60.0)` — logs at most once per `(key, event)` pair per
  window, suppressing the rest with a single trailing count.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_log_noise_reduction.py
import logging

from app.core.logging import log


def test_polling_route_access_filter_suppresses_known_noisy_paths():
    from app.main import _PollingRouteFilter
    f = _PollingRouteFilter()
    noisy = logging.LogRecord("uvicorn.access", logging.INFO, "", 0,
                               '"GET /api/execution/state HTTP/1.1" 200 OK', (), None)
    real = logging.LogRecord("uvicorn.access", logging.INFO, "", 0,
                              '"POST /api/positions/manual-open HTTP/1.1" 200 OK', (), None)
    assert f.filter(noisy) is False   # suppressed
    assert f.filter(real) is True     # passes through


def test_error_ratelimited_emits_once_per_window(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(log, "_emit_error", lambda *a, **k: calls.append((a, k)))
    for _ in range(5):
        log.error_ratelimited("SL-M stop place failed LT: tick size", key="LT:SLM_FAIL",
                               event="SLM_FAIL")
    assert len(calls) == 1   # only the first of the 5 identical calls actually emits
```

(Adapt `_emit_error`/the exact internal emission function name to whatever
`app/core/logging.py`'s `log.error` actually calls internally — read the file
first with `Read backend/app/core/logging.py` before writing this test, since
the plan cannot know the exact private method name without seeing the file;
if `log.error` is not easily monkeypatchable at an inner layer, test
`error_ratelimited` at the black-box level instead by monkeypatching
`log.error` itself and asserting call count.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_log_noise_reduction.py -v`
Expected: FAIL (`ImportError`/`AttributeError` on both new symbols)

- [ ] **Step 3: Write minimal implementation**

In `backend/app/core/logging.py`, add a rate-limited error method to whatever
the existing `log` object's class is (read the file first to match its exact
class/method structure — the shape below assumes a simple class with an
`error` method; adapt field names to match):

```python
    _ratelimit_seen: dict = {}  # (key, event) -> last-emitted monotonic time, class-level

    def error_ratelimited(self, message: str, *, key: str, event: str,
                           window_seconds: float = 60.0, **kw) -> None:
        """Like .error(), but suppresses repeats of the same (key, event) within
        window_seconds — the fix for the 1,820x/day LT SL-M-failure spam the
        2026-07-15 autopsy found burying the journal. Only the FIRST occurrence
        in a window actually logs."""
        import time
        now = time.monotonic()
        last = self._ratelimit_seen.get((key, event))
        if last is not None and now - last < window_seconds:
            return
        self._ratelimit_seen[(key, event)] = now
        self.error(message, event=event, **kw)
```

In `backend/app/main.py`, add the filter class and install it on the uvicorn
access logger near the top-level module code (after imports, before `app =
FastAPI(...)`):

```python
class _PollingRouteFilter(logging.Filter):
    """Demote high-frequency UI polling GETs out of the access log (autopsy:
    ~34% of the 3-day journal was polling noise). Real mutating/rare routes
    still log normally."""
    _NOISY = ("/api/execution/state", "/api/status", "/api/signals")

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return not any(f"GET {p} " in msg for p in self._NOISY)


logging.getLogger("uvicorn.access").addFilter(_PollingRouteFilter())
```

(Add `import logging` at the top of `main.py` if not already present — check
first with `grep -n "^import logging" backend/app/main.py`.)

Now find the SL-M failure log call site (`grep -rn '"SL-M stop place failed"'
backend/app/engine/`) and switch it from `log.error(...)` to
`log.error_ratelimited(..., key=f"{sym}:SLM_FAIL", event="SLM_PLACE_FAIL")`,
keeping the message text identical.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_log_noise_reduction.py -v`
Expected: PASS

Then the full suite: `cd backend && .venv/bin/python -m pytest`

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py backend/app/core/logging.py backend/app/engine/live_broker.py \
        backend/tests/test_log_noise_reduction.py
git commit -m "fix(logging): demote polling-route access logs; rate-limit SL-M failure spam"
```

---

# Group E — H13: persisted order journal

Build exactly per the existing detailed spec — **do not re-derive it**; both
documents already exist in this repo and were produced by a prior Fable
architecture pass specifically for this feature:

- Design: `docs/audit-deferred-design.md` §"H13 — No persisted order journal"
- Implementation guide: `docs/audit-remaining-impl-guide.md` §"H13 — Persisted
  order journal + startup recovery"

### Task E1: `OrderJournal` model + migration

**Files:**
- Modify: `backend/app/db/models.py` (new `OrderJournal` class)
- Modify: `backend/app/db/session.py` (`create_all` already picks up new
  tables automatically — confirm no `_migrate_schema` entry is needed for a
  brand-new table, only for new columns on existing tables)
- Test: `backend/tests/test_order_journal.py` (start the file — later tasks in
  this group append to it)

**Interfaces:**
- Produces: `OrderJournal` ORM class with exactly the columns from the guide:
  `id, order_id (nullable, indexed), tradingsymbol, instrument_key, side,
  kind ("options"|"equity"), qty, intent ("ENTRY"|"EXIT"), context_json (Text),
  status ("WORKING"|"TERMINAL", indexed), resolution
  (FILLED/REJECTED/CANCELLED/ADOPTED/DEAD/RACED_FILL/NEVER_PLACED/UNKNOWN,
  nullable), filled_qty, avg_price, placed_at, resolved_at (nullable)`.

**Note before starting:** the VPS snapshot DB already has a table named
`order_journal` (seen in the 2026-07-15 autopsy's DB queries). Before writing
the model, run
`sqlite3 /private/tmp/claude-*/*/scratchpad/pt-snap-20260715.db ".schema order_journal"`
(or re-copy the snapshot if the scratchpad was cleared) to check whether that
table's existing columns overlap or conflict with the guide's schema. If it's
a different, smaller ad-hoc table (likely, since H13 was never implemented per
the tracker), name the new SQLAlchemy table exactly `order_journal` only if
the columns are a superset-compatible extension; otherwise name it
`order_journal_v2` and note the discrepancy in the commit message for the
owner to reconcile/drop the old table later. Do not silently overwrite
unknown existing data.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_order_journal.py
"""H13 — persisted order journal (see docs/audit-remaining-impl-guide.md).
This file grows across Tasks E1-E4."""
import datetime as dt

from app.db.models import OrderJournal
from app.db.session import init_db, SessionLocal


def test_order_journal_row_roundtrip():
    init_db(reset=True)
    s = SessionLocal()
    row = OrderJournal(
        order_id=None, tradingsymbol="LT", instrument_key="LT", side="SELL",
        kind="equity", qty=10, intent="ENTRY", context_json="{}",
        status="WORKING", placed_at=dt.datetime.now())
    s.add(row)
    s.commit()
    assert row.id is not None
    assert row.status == "WORKING"
    assert row.resolution is None
    row.order_id = "250715001234"
    row.status = "TERMINAL"
    row.resolution = "FILLED"
    row.filled_qty = 10
    row.avg_price = 3837.4
    row.resolved_at = dt.datetime.now()
    s.commit()
    fresh = s.get(OrderJournal, row.id)
    assert fresh.status == "TERMINAL" and fresh.resolution == "FILLED"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_order_journal.py -v`
Expected: FAIL (`ImportError: cannot import name 'OrderJournal'`)

- [ ] **Step 3: Write minimal implementation**

Add to `backend/app/db/models.py` (place near the other engine-lifecycle
tables, e.g. after `Trade` or near `Position`):

```python
class OrderJournal(Base):
    """H13 — persisted, across-restart record of every REAL order this process
    places (options + equity, entries + exits). Write-through: a WORKING row is
    written BEFORE placement, marked TERMINAL on resolution. On startup,
    recover_journal() reconciles any still-WORKING row against the broker so a
    crash mid-order doesn't leave unrecoverable in-flight state. See
    docs/audit-remaining-impl-guide.md §H13 for the full design."""
    __tablename__ = "order_journal"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    tradingsymbol: Mapped[str] = mapped_column(String(64))
    instrument_key: Mapped[str] = mapped_column(String(32))
    side: Mapped[str] = mapped_column(String(8))          # BUY | SELL
    kind: Mapped[str] = mapped_column(String(16))          # options | equity
    qty: Mapped[int] = mapped_column(Integer)
    intent: Mapped[str] = mapped_column(String(8))         # ENTRY | EXIT
    context_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(12), index=True)  # WORKING | TERMINAL
    resolution: Mapped[str | None] = mapped_column(String(24), nullable=True)
    filled_qty: Mapped[int] = mapped_column(Integer, default=0)
    avg_price: Mapped[float] = mapped_column(Float, default=0.0)
    placed_at: Mapped[dt.datetime] = mapped_column(DateTime)
    resolved_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
```

Since this is a brand-new table, `Base.metadata.create_all` (already called by
`init_db`) creates it automatically for both fresh and existing DBs — no
`_migrate_schema` entry needed (that hook is only for adding *columns* to
tables that already exist). Confirm this by re-running the migration test
unchanged: `.venv/bin/python -m pytest tests/test_migration.py -v` must still
pass with zero edits to that file.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_order_journal.py tests/test_migration.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/db/models.py backend/tests/test_order_journal.py
git commit -m "feat(engine): OrderJournal table (H13 foundation)"
```

---

### Task E2: Write-through journaling in `LiveBroker._execute`

**Files:**
- Modify: `backend/app/engine/live_broker.py`
- Modify: `backend/app/engine/order_executor.py` (`execute_order` gains
  `on_placed` callback per the guide)
- Test: `backend/tests/test_order_journal.py` (append)

**Interfaces:**
- Consumes: `OrderJournal` (E1); the guide's exact contract: "write a WORKING
  row BEFORE placement (order_id NULL), set order_id via on_placed, mark
  TERMINAL on resolution."
- Produces: `LiveBroker._execute(req, *, intent: str, kind: str, context: dict
  | None = None) -> (res, filled, avg)` (absorbs the existing
  `_actual_fill`/`_note_order_outcome` per the guide — read
  `backend/app/engine/live_broker.py` in full first, since this task
  restructures existing private methods rather than adding new standalone
  ones; follow the guide's exact call-site consolidation: "the 4 callers drop
  their own `_actual_fill`/`_note_order_outcome`").
- Produces: `journal_mark_terminal(order_id, resolution, filled=0, avg=0.0)`
  module-level or instance function, called from every terminal branch
  (`_ensure_no_inflight`, `cancel_working_entries`, `adopt_pending_entries`).

This task requires reading `backend/app/engine/live_broker.py`,
`backend/app/engine/order_executor.py`, and
`backend/app/engine/kite_order_client.py` in full before writing code — the
guide (`docs/audit-remaining-impl-guide.md` §H13, steps 2-4) is written
against these files' actual current structure and names exact methods
(`_actual_fill`, `_note_order_outcome`, `_record_inflight`,
`_pending_entries`) that must be located precisely, not guessed. Follow the
guide's steps 2-4 verbatim as the implementation spec for this task; the
guide's own acceptance bar is the test list reproduced below.

- [ ] **Step 1: Write the failing tests**

```python
# append to backend/tests/test_order_journal.py
"""E2: write-through journaling around LiveBroker._execute. Uses the existing
FakeClient test double already proven in test_live_broker.py — read that file
first to reuse its exact FakeClient class/import path rather than duplicating
a second fake broker client."""
# NOTE TO IMPLEMENTER: import FakeClient from wherever test_live_broker.py
# defines/imports it (grep -n "class FakeClient" backend/tests/test_live_broker.py).
# The tests below are the ACCEPTANCE BAR from docs/audit-remaining-impl-guide.md
# §H13's test list — write them against the real FakeClient, adapting fixture
# setup to match test_live_broker.py's existing conventions exactly (same
# LiveBroker construction pattern) so this file's tests run in the same style
# as the rest of the live-broker suite.

def test_working_row_written_before_placement_with_null_order_id():
    ...  # placeholder marker for the implementer — see guide's test list below


def test_filled_order_marks_terminal_filled_no_never_placed_leak():
    ...


def test_rejected_order_marks_terminal_rejected():
    ...


def test_place_raises_marks_terminal_appropriately_no_leak():
    ...


def test_timeout_entry_then_fresh_broker_same_db_recovers_and_adopts():
    ...


def test_exit_working_then_complete_books_ledger_only_no_new_order_placed():
    ...


def test_dead_order_marked_dead():
    ...


def test_tag_sweep_surfaces_unbooked_orders_without_booking_them():
    ...


def test_three_pop_sites_mark_terminal():
    ...


def test_init_db_creates_order_journal_table():
    from app.db.session import init_db
    from sqlalchemy import inspect
    import app.db.session as sess
    init_db(reset=True)
    assert "order_journal" in inspect(sess.engine).get_table_names()
```

**Implementer note:** the nine `...`-bodied tests above are named directly
from the guide's own acceptance list ("Tests (`tests/test_order_journal.py`,
FakeClient): WORKING row w/ order_id; FILLED/REJECTED/place-raises → correct
TERMINAL, no NEVER_PLACED leak; TIMEOUT entry → WORKING+dicts, then a FRESH
LiveBroker on the same DB + COMPLETE status → recover adopts, ADOPTED,
invariant 0; EXIT WORKING → COMPLETE → ledger-only close, `client.placed`
empty during recovery; dead → DEAD; tag sweep surfaces+books nothing; the 3
pop-sites mark terminal; init_db creates the table."). Fill in each body by
mirroring `test_live_broker.py`'s existing FakeClient-based test patterns
(same class construction, same style of asserting on `client.placed`/DB
state) — this is a **placeholder-in-the-plan-document only**; the delivered
test file must have zero `...` bodies or skipped tests before Step 4's green
run. `test_init_db_creates_order_journal_table` is fully written above and
needs no filling in.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/python -m pytest tests/test_order_journal.py -v`
Expected: FAIL / collection error until the `...` bodies are replaced with
real assertions in Step 1's actual delivery (not this plan document).

- [ ] **Step 3: Implement per the guide**

Follow `docs/audit-remaining-impl-guide.md` §H13 steps 2-4 exactly:
2. `order_executor.execute_order` gains `on_placed: Callable[[str], None] |
   None = None`, called right after `order_id = client.place(req)`,
   try/except-wrapped.
3. `live_broker._execute(req, *, intent, kind, context=None) -> (res, filled,
   avg)`: writes a WORKING row before placement (order_id NULL), sets
   order_id via `on_placed`, marks TERMINAL on resolution; the 4 existing
   callers drop their own `_actual_fill`/`_note_order_outcome` in favor of
   this consolidated method. All journal I/O try/except-wrapped — a journal
   failure must NEVER block or fail a real order (wrap every journal write in
   `try/except Exception: log.error(...)`, never let it propagate).
   `context_json` is JSON-safe per the guide's exact shapes (options ENTRY,
   equity ENTRY, EXIT) — never pickle.
4. `journal_mark_terminal(order_id, resolution, filled=0, avg=0.0)` called
   from `_ensure_no_inflight` (every terminal branch), `cancel_working_entries`,
   `adopt_pending_entries` (ADOPTED/DEAD resolutions).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_order_journal.py tests/test_live_broker.py -v`
Expected: PASS, zero regressions in the existing live-broker suite.

Run: `cd backend && .venv/bin/python -m pytest && .venv/bin/python scripts/dryrun.py 700`
Expected: full suite PASS; ledger invariant holds.

- [ ] **Step 5: Commit**

```bash
git add backend/app/engine/live_broker.py backend/app/engine/order_executor.py \
        backend/tests/test_order_journal.py
git commit -m "feat(engine): write-through order journaling around LiveBroker._execute (H13)"
```

---

### Task E3: `recover_journal()` startup recovery

**Files:**
- Modify: `backend/app/engine/live_broker.py` (`recover_journal(now)` method;
  no-op on `PaperBroker`)
- Modify: `backend/app/engine/kite_order_client.py` (add `orders()` for the
  tag sweep)
- Test: `backend/tests/test_order_journal.py` (the recovery-focused tests from
  E2's list are exercised here if not already fully covered)

**Interfaces:** per the guide's step 5 exactly — implement `recover_journal`
with the per-row branching table from `docs/audit-remaining-impl-guide.md`
§H13 step 5 (NULL order_id → tag sweep; status raises → keep WORKING;
ENTRY filled>0 → rebuild `_pending_entries` + `adopt_pending_entries(now)`
ONCE; ENTRY dead → DEAD; ENTRY working → rebuild both dicts; EXIT filled≥qty →
book ledger-only via segment routing like `reconcile_orphans`; EXIT partial →
`book_partial_close`/`book_partial_close_equity`; EXIT working → `_inflight`).

- [ ] **Step 1-4:** follow the TDD cycle against whichever of E2's nine tests
  specifically exercise recovery (`test_timeout_entry_then_fresh_broker...`,
  `test_exit_working_then_complete...`, `test_dead_order_marked_dead`,
  `test_tag_sweep_surfaces_unbooked_orders_without_booking_them`) — if E2 only
  stubbed these, complete them now against the real `recover_journal`
  implementation; if E2 already fully implemented and passed them (plausible,
  since E2 and E3 are tightly coupled per the guide), this task is primarily
  the `orders()` tag-sweep addition to `kite_order_client.py` plus
  confirming all nine tests are genuinely green (not accidentally
  vacuous/tautological).

- [ ] **Step 5: Commit**

```bash
git add backend/app/engine/live_broker.py backend/app/engine/kite_order_client.py \
        backend/tests/test_order_journal.py
git commit -m "feat(engine): recover_journal startup recovery + tag sweep (H13)"
```

---

### Task E4: Wire `recover_journal` into `main.py` lifespan

**Files:**
- Modify: `backend/app/main.py`

**Interfaces:** per the guide's step 6 — call
`await asyncio.to_thread(runner.broker.recover_journal,
runner.provider.now())` in `lifespan`, **after** `EngineRunner()` construction
and **before** the loop tasks start, wrapped in try/except so a recovery bug
never blocks startup.

- [ ] **Step 1: Write the failing test**

```python
# append to backend/tests/test_order_journal.py
def test_lifespan_calls_recover_journal_before_loops(monkeypatch):
    """recover_journal must run once at startup, before the signal/risk loops
    can re-enter an instrument that has a WORKING order-journal row."""
    calls = []
    from app.engine import live_broker as lb
    monkeypatch.setattr(lb.LiveBroker, "recover_journal",
                         lambda self, now: calls.append(now))
    # Exercise via the TestClient's app lifespan (mock provider → PaperBroker,
    # whose recover_journal is a no-op and isn't the one patched above — so
    # this test's real assertion is that a KITE-provider lifespan wires the
    # call at all; use a lightweight monkeypatch of get_provider/broker_factory
    # if a full live TestClient boot is too heavy — mirror however
    # test_main.py or test_app_boot.py (if one exists) already boots the app
    # in-process for a lifespan-level assertion. grep -rn "lifespan" backend/tests/
    # first to find the existing pattern for testing lifespan behavior, if any.
    pass
```

**Implementer note:** grep the existing test suite for how (or whether)
`lifespan` is already exercised in-process
(`grep -rn "lifespan\|TestClient(app)" backend/tests/*.py | head -20`) and
follow that established pattern rather than inventing a new one; if no test
currently boots the full lifespan, the simplest correct test is a narrower
unit check that `main.py`'s `lifespan` function, read as source, contains the
`recover_journal` call in the right position relative to `EngineRunner()` and
the loop-task creation — or, more robustly, refactor the recovery call into a
small `_recover_orders(runner)` module-level function in `main.py` that a
test can import and call directly against a `PaperBroker` (no-op path) and a
monkeypatched `LiveBroker`, without booting the whole ASGI lifespan. Prefer
the extracted-function approach — it's more testable and matches this
codebase's general preference for small, directly-testable units.

- [ ] **Step 2-4:** standard TDD cycle for whichever approach was chosen above.

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py backend/tests/test_order_journal.py
git commit -m "feat(engine): wire recover_journal into startup, before the trading loops (H13)"
```

---

# Group F — shadcn/ui foundation + re-skins

### Task F1: shadcn foundation (tokens, primitives, responsive shell)

**Files:**
- Modify: `frontend/tsconfig.json` (path alias `@/*` → `src/*`)
- Modify: `frontend/vite.config.ts` (matching resolve alias)
- Create: `frontend/components.json` (shadcn CLI config)
- Create: `frontend/src/lib/utils.ts` (`cn()` helper)
- Modify: `frontend/package.json` (new deps)
- Modify: `frontend/src/index.css` (CSS variable tokens, dark theme default)
- Create: `frontend/src/components/ui/*` (shadcn-generated: button, card,
  badge, table, tabs, sheet, dialog, input, select, switch, sonner, skeleton)
- Modify: `frontend/src/App.tsx` (responsive shell: bottom tab bar ≤768px /
  sidebar desktop — the current `TopBar`/`MobileTopBar` split is reused, not
  discarded, per "follow existing patterns")

**Interfaces:**
- Produces: `cn(...)` util used by every shadcn component; CSS variables
  (`--background`, `--foreground`, `--card`, `--border`, `--primary`, etc.)
  layered alongside (not replacing) the existing `.card`/`.badge`/token
  classes in `index.css`, so every un-migrated view keeps rendering correctly
  during the incremental re-skin.

- [ ] **Step 1: Add path aliases**

In `frontend/tsconfig.json`, add under `compilerOptions`:

```json
    "baseUrl": ".",
    "paths": { "@/*": ["./src/*"] }
```

In `frontend/vite.config.ts`, add a matching `resolve.alias` entry (read the
file first — `Read frontend/vite.config.ts` — to insert into its existing
`defineConfig({...})` shape rather than guessing its structure):

```typescript
import path from 'path'
// ...
export default defineConfig({
  // ...existing plugins/config...
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
})
```

- [ ] **Step 2: Install dependencies**

Run: `cd frontend && npm install tailwindcss-animate class-variance-authority clsx tailwind-merge lucide-react @radix-ui/react-slot @radix-ui/react-tabs @radix-ui/react-dialog @radix-ui/react-select @radix-ui/react-switch sonner`

- [ ] **Step 3: Create `cn()` util**

```typescript
// frontend/src/lib/utils.ts
import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
```

- [ ] **Step 4: Create `components.json`**

```json
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "default",
  "rsc": false,
  "tsx": true,
  "tailwind": {
    "config": "tailwind.config.js",
    "css": "src/index.css",
    "baseColor": "zinc",
    "cssVariables": true,
    "prefix": ""
  },
  "aliases": {
    "components": "@/components",
    "utils": "@/lib/utils"
  }
}
```

- [ ] **Step 5: Add design tokens to `index.css`**

Add alongside the existing `@layer components` block (do not remove
`.card`/`.badge` — both systems coexist during the incremental migration):

```css
@layer base {
  :root {
    --background: 240 10% 4%;
    --foreground: 0 0% 95%;
    --card: 240 6% 10%;
    --card-foreground: 0 0% 95%;
    --border: 240 6% 20%;
    --input: 240 6% 20%;
    --primary: 160 84% 39%;
    --primary-foreground: 0 0% 100%;
    --secondary: 240 6% 16%;
    --secondary-foreground: 0 0% 90%;
    --destructive: 0 72% 51%;
    --destructive-foreground: 0 0% 100%;
    --muted: 240 6% 16%;
    --muted-foreground: 240 5% 65%;
    --accent: 240 6% 16%;
    --accent-foreground: 0 0% 95%;
    --ring: 160 84% 39%;
    --radius: 0.5rem;
  }
}
```

Add the CSS variable → Tailwind color mapping in `frontend/tailwind.config.js`
(read the file first to extend, not replace, its existing `theme.extend`):

```javascript
      colors: {
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: { DEFAULT: 'hsl(var(--primary))', foreground: 'hsl(var(--primary-foreground))' },
        secondary: { DEFAULT: 'hsl(var(--secondary))', foreground: 'hsl(var(--secondary-foreground))' },
        destructive: { DEFAULT: 'hsl(var(--destructive))', foreground: 'hsl(var(--destructive-foreground))' },
        muted: { DEFAULT: 'hsl(var(--muted))', foreground: 'hsl(var(--muted-foreground))' },
        accent: { DEFAULT: 'hsl(var(--accent))', foreground: 'hsl(var(--accent-foreground))' },
        card: { DEFAULT: 'hsl(var(--card))', foreground: 'hsl(var(--card-foreground))' },
      },
      borderRadius: {
        lg: 'var(--radius)', md: 'calc(var(--radius) - 2px)', sm: 'calc(var(--radius) - 4px)',
      },
```

Add `require('tailwindcss-animate')` to the config's `plugins` array (append,
don't replace existing plugins).

**Naming collision check:** the existing `index.css` already defines a
`text-muted`/`bg-panel`/`border-edge` utility vocabulary used by every current
view (confirmed via `TradesView.tsx`'s classes). Tailwind's `muted` color key
above is new and distinct from the existing `.text-muted` utility class (a
custom class, not a Tailwind color token) — verify with
`grep -n "muted\|panel\|edge" frontend/tailwind.config.js frontend/src/index.css`
before this step that no name actually collides; if `muted` is ALREADY a
defined Tailwind color in this config, merge into the existing entry instead
of adding a duplicate key.

- [ ] **Step 6: Generate primitives via the shadcn CLI**

Run: `cd frontend && npx shadcn@latest add button card badge table tabs sheet dialog input select switch sonner skeleton`

(This writes into `frontend/src/components/ui/`. If the CLI prompts
interactively, answer with the `components.json` values already configured
above — Tailwind v3-compatible components are the CLI's default when it
detects a v3 `tailwind.config.js`, so no `--tailwind-version` flag should be
needed; if the CLI errors on Tailwind version detection, pin generation with
whatever flag its own error message specifies rather than guessing.)

- [ ] **Step 7: Verify build**

Run: `cd frontend && npm run typecheck && npm run build`
Expected: both PASS. If any generated component fails typecheck due to a
missing peer dependency, install exactly what the error names (shadcn's CLI
output lists the components actually generated — install their real Radix
peers, don't guess ahead).

- [ ] **Step 8: Screenshot checkpoint**

Run the dev server (`npm run dev`) and, using Playwright or the `claude-in-
chrome` skill, capture the existing app shell unchanged (this task doesn't
re-skin any view yet — the checkpoint confirms the foundation didn't break
anything visually) at 390px and 1280px widths. Save under
`docs/superpowers/screenshots/2026-07-17-shadcn-foundation-{390,1280}.png`
(create the directory if it doesn't exist). This is the review artifact for
the owner before Task F2 begins.

- [ ] **Step 9: Commit**

```bash
git add frontend/tsconfig.json frontend/vite.config.ts frontend/components.json \
        frontend/src/lib/utils.ts frontend/package.json frontend/package-lock.json \
        frontend/src/index.css frontend/tailwind.config.js frontend/src/components/ui/ \
        docs/superpowers/screenshots/
git commit -m "feat(ui): shadcn/ui foundation — tokens, primitives, path aliases (Tailwind 3 stack)"
```

**STOP — this is a review checkpoint per the design doc ("foundation first,
one agent, reviewed before fan-out"). Do not proceed to Task F2 until the
owner has reviewed the screenshots and approved.**

---

### Task F2: Re-skin template — Watchlist (worked example)

**Files:**
- Modify: `frontend/src/views/WatchlistView.tsx`

**Interfaces:**
- Consumes: `Button`, `Card`, `Badge`, `Table*`, `Switch` from
  `frontend/src/components/ui/*` (F1).

This task is the **worked template** the checklist in F3 follows for every
remaining view. Read the current `WatchlistView.tsx` in full first — this
plan does not reproduce its ~300 lines; the re-skin is a like-for-like
component swap (`<div className="card">` → `<Card>`, raw `<button>` →
`<Button variant="ghost"/>`, `.badge` spans → `<Badge>`, etc.), preserving
every prop, handler, and piece of business logic exactly. **Do not change
behavior — only markup/styling.**

- [ ] **Step 1: Read the current file**

Run: `Read frontend/src/views/WatchlistView.tsx` (full file).

- [ ] **Step 2: Swap primitives incrementally, verifying typecheck after each
  logical section** (rows table, per-row action buttons, filter controls,
  purple/overtrade badges). Keep the purple-priority toggle's existing
  `title`/tooltip text and the `bg-purple-500/20`-style badge coloring intent
  (swap to `<Badge variant="secondary">` with a purple accent class, or keep
  the raw span if `Badge` doesn't support arbitrary accent colors cleanly —
  judgment call, prioritize not regressing the purple-vs-normal visual
  distinction this whole session is partly about).

- [ ] **Step 3: Typecheck**

Run: `cd frontend && npm run typecheck`
Expected: PASS

- [ ] **Step 4: Screenshot at 390px**

Capture `WatchlistView` at 390px width (Playwright / claude-in-chrome), save
to `docs/superpowers/screenshots/2026-07-17-watchlist-390.png`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/WatchlistView.tsx docs/superpowers/screenshots/2026-07-17-watchlist-390.png
git commit -m "feat(ui): re-skin WatchlistView onto shadcn primitives"
```

---

### Task F3: Re-skin checklist — remaining views (follow F2's pattern)

**Files (one commit each, same pattern as F2):**
- Modify: `frontend/src/views/ActivePositionsView.tsx`
- Modify: `frontend/src/views/JournalView.tsx` (from Group B — re-skin onto
  shadcn now that the foundation exists; preserve every handler/API call from
  B2 exactly)
- Modify: `frontend/src/views/BacktestsView.tsx` (mobile-first per the design
  doc: "launch + monitor a sweep from the phone" — pay particular attention to
  the progress-bar and launch-form controls rendering usably at 390px)
- Modify: `frontend/src/views/TradesView.tsx`
- Modify: `frontend/src/views/DashboardView.tsx`
- Modify: `frontend/src/views/SettingsView.tsx`
- Modify: `frontend/src/views/EngineView.tsx`

For each view, repeat Task F2's five steps exactly (read file → swap
primitives preserving all logic → typecheck → 390px screenshot → commit),
substituting the file name and commit message (`feat(ui): re-skin
<ViewName> onto shadcn primitives`). Work through them in this exact
order — it matches the design doc's approved priority list. Each is
independently committable and independently reviewable; do not batch
multiple views into one commit.

- [ ] **Step 1: ActivePositionsView** — read, swap, typecheck, screenshot, commit.
- [ ] **Step 2: JournalView** — read (from Group B), swap, typecheck, screenshot, commit.
- [ ] **Step 3: BacktestsView** — read, swap (mobile-first care on the launch
  form + progress bar), typecheck, screenshot at 390px AND 1280px (desktop-only
  per `App.tsx:64-66` — confirm both render correctly), commit.
- [ ] **Step 4: TradesView** — read, swap, typecheck, screenshot, commit.
- [ ] **Step 5: DashboardView** — read, swap, typecheck, screenshot, commit.
- [ ] **Step 6: SettingsView** — read, swap (this file is long/knob-heavy per
  `CLAUDE.md`'s "dozens of parameters" — swap in logical sections, typecheck
  after each, don't attempt one giant diff), screenshot, commit.
- [ ] **Step 7: EngineView** — read, swap, typecheck, screenshot, commit.

- [ ] **Final acceptance check for Group F:**

Run: `cd frontend && npm run typecheck && npm run build`
Expected: both PASS after all seven views are re-skinned. Manually click
through every tab at a 390px browser width (or via Playwright) confirming
each is usable one-handed — this is the design doc's explicit acceptance bar
("every view usable one-handed at 390px over the tailnet").

---

## Post-plan: P1 exit-autopsy replay

Not a coding task — a read-only analysis Workflow, per the design doc §7. Run
it separately (not as a plan task) once Groups A-F are stable, using the same
multi-agent replay pattern already proven in this session's VPS log/DB
autopsy: one agent per instrument-day replaying the pure kernels
(`lockstep_band`, `equity_exit` from `app/engine/equity_entry.py`) against
Kite 1-minute candles, Opus synthesizing loss attribution into
`docs/exit-autopsy-2026-07.md`. Requires a valid Kite token for candle
history; degrades to DB+journal-only classification without one.

---

## Deploy reminder (not a plan task — owner-gated)

None of Groups A-F are live until the owner runs the established off-market
deploy routine (rsync whole tree + systemd restart + journalctl marker
check) on the VPS. The design doc's §1 already flags that the VPS is still on
the 2026-07-14 deploy and the tick-size/leverage/reconcile safety fixes from
2026-07-16 are not yet in force live — this plan's work compounds on top of
that same gap. Do not let engineering completeness here be mistaken for
production readiness; only the owner deploys.
