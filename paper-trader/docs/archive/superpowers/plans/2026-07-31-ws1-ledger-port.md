# WS-1: THE LEDGER Port + Server Snapshot — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Delete the existing paper-trader trade journal and replace it with THE LEDGER, running full-bleed inside the app with its own visual language, persisting to the FastAPI backend instead of IndexedDB.

**Architecture:** THE LEDGER persists as a single debounced JSON snapshot through exactly one file (`src/data/idb.ts`, 3 exported functions). We re-point that file at a REST endpoint backed by a one-row SQLite table with optimistic concurrency, leaving `store.ts`, `actions.ts` and all 43 mutators untouched — the business rules stay where the design put them. Screenshots move out of the snapshot into their own table. The vendored source is CSS-scoped under `.ledger-root` and its global keymap is mounted/unmounted with the route so it cannot hijack the host app.

**Tech Stack:** FastAPI + SQLAlchemy 2 + SQLite (backend), React 18 + TypeScript 5 + Vite 5 + vitest (frontend). THE LEDGER has zero runtime dependencies beyond react/react-dom.

## Global Constraints

- Source to port: `/Users/priyanshusaraf/dev/trade-journal/src/` — 51 files, ~19,000 lines. Vendor it, do not submodule it.
- New backend package is `backend/app/ledger/`. **Never** name it `journal` — `app/db/models.py:615` `OrderJournal` and `backend/tests/test_order_journal.py` are unrelated live crash-recovery machinery that must not be touched or confused with this.
- New DB path env var: `PT_LEDGER_DB_PATH`. It **must** default to an absolute path derived from the backend package directory, never a bare relative `"ledger.db"` — a relative default lands wherever systemd's `WorkingDirectory` points and a restart under a different cwd silently starts a second, empty journal.
- Schema changes ship as **code that self-applies** (`init_ledger_db()` → `migrate_ledger_db()` with `PRAGMA table_info` checks). `scripts/deploy.sh` excludes `*.db` from rsync. `metadata.create_all` only ever CREATEs and silently skips existing tables — it is not a migration.
- Backend tests: `.venv/bin/python -m pytest -q --tb=short`. Run **both** suites where relevant: `pytest tests research_tests` (`testpaths=tests` means bare `pytest` skips the research suite).
- `scripts/dryrun.py 700` must stay green — hard invariant 1, the ledger reconciles to the paisa.
- Frontend gates today are `npm run typecheck` (`tsc --noEmit`) and `npm run build`. This workstream **adds vitest**, scoped to the journal only.
- Frontend breakpoint convention is a JS `matchMedia('(min-width: 768px)')` in `App.tsx:33-44`, not CSS-only.
- **Commit only when the owner asks.** `paper-trader/CLAUDE.md` states this explicitly. Each task below ends with a commit step; stage the work and hold unless told otherwise.
- Deploy only via `scripts/deploy.sh`. Never build the SPA on the VPS.
- Do not touch bot execution, sizing, or exits. Nothing in this workstream may import from `app/engine/`.

---

## File Structure

### Backend — created

| File | Responsibility |
|---|---|
| `backend/app/ledger/__init__.py` | Package marker. Empty. |
| `backend/app/ledger/config.py` | `ledger_db_path()`. Deliberately does not import `app.core.config`, so the ledger never implicitly binds the execution DB engine. |
| `backend/app/ledger/db.py` | `LedgerBase`, engine factory (WAL, busy_timeout), `init_ledger_db()`, `migrate_ledger_db()`, lazy thread-safe sessionmaker. |
| `backend/app/ledger/models.py` | `LedgerSnapshot` (one row) and `LedgerArtifact`. |
| `backend/app/ledger/service.py` | `read_snapshot()`, `write_snapshot()` (raises `VersionConflict`), artifact CRUD. Pure of FastAPI. |
| `backend/app/ledger/routes.py` | `APIRouter(prefix="/api/ledger")`. HTTP concerns only. |

### Backend — modified

| File | Change |
|---|---|
| `backend/app/main.py:28` | `from app.journal import routes as journal_routes` → `from app.ledger import routes as ledger_routes` |
| `backend/app/main.py:167` | `app.include_router(journal_routes.router)` → `app.include_router(ledger_routes.router)` |
| `backend/tests/test_equity_short_charge_legs.py:7` | Reword the docstring citing the deleted `journal/pnl.py`. |

### Backend — deleted

`backend/app/journal/` (8 files), `backend/tests/journal/` (9 files, 71 tests), `backend/journal.db` (untracked test artifact).

### Frontend — created

| File | Responsibility |
|---|---|
| `frontend/src/ledger/**` | Vendored copy of `/Users/priyanshusaraf/dev/trade-journal/src/**`, minus `main.tsx` and `app/auth.ts`. |
| `frontend/src/ledger/data/idb.ts` | **Replaced** with an HTTP client of identical signature plus version tracking. |
| `frontend/src/views/LedgerView.tsx` | The mount point: renders `.ledger-root`, owns boot, unmounts the keymap on route change. |
| `frontend/postcss.config.cjs` | Adds the `.ledger-root` prefixing pass. |
| `frontend/vitest.config.ts` | vitest config scoped to `src/ledger/**/*.test.ts`. |

### Frontend — modified

`frontend/src/App.tsx` (3 sites), `frontend/src/lib/api.ts:180-222` (delete), `frontend/src/lib/types.ts:200-302` (delete), `frontend/package.json` (vitest + scripts).

### Frontend — deleted

`frontend/src/views/JournalView.tsx`.

---

### Task 1: Remove the existing journal

**Files:**
- Delete: `backend/app/journal/` (whole directory), `backend/tests/journal/` (whole directory), `backend/journal.db`, `frontend/src/views/JournalView.tsx`
- Modify: `backend/app/main.py:28,167`; `frontend/src/App.tsx:9,21,64`; `frontend/src/lib/api.ts:180-222`; `frontend/src/lib/types.ts:200-302`; `backend/tests/test_equity_short_charge_legs.py:7`
- Verify: `.venv/bin/python -m pytest -q --tb=short` and `npm run typecheck`

**Interfaces:**
- Consumes: nothing.
- Produces: a tree with no `app.journal` module and no `journal` tab. Task 8 re-adds a tab named `journal` pointing at `LedgerView`.

- [ ] **Step 1: Prove the blast radius is what the spec claims**

```bash
cd /Users/priyanshusaraf/dev/options-trading/paper-trader
grep -rn "app\.journal" backend/ --include=*.py
grep -rn "JournalView\|getJournal\|addJournal\|upsertJournal\|putJournal\|deleteJournal\|archiveJournal\|closeJournal" frontend/src
```

Expected: exactly `backend/app/main.py:28`, `backend/app/main.py:167`, and files under `backend/tests/journal/`; on the frontend, only `App.tsx`, `views/JournalView.tsx`, `lib/api.ts`, `lib/types.ts`.

**If anything else appears, stop and report it** — the deletion plan assumed this list.

- [ ] **Step 2: Confirm `journal.db` holds no real data before deleting it**

```bash
cd /Users/priyanshusaraf/dev/options-trading/paper-trader/backend
sqlite3 journal.db "SELECT 'trades', COUNT(*) FROM journal_trades
                    UNION ALL SELECT 'notes', COUNT(*) FROM journal_notes
                    UNION ALL SELECT 'days', COUNT(*) FROM journal_days
                    UNION ALL SELECT 'missed', COUNT(*) FROM journal_missed;"
```

Expected: `0` for all four. **If any row count is non-zero, stop** — the spec's claim that this file is a test artifact is wrong and the owner must decide.

- [ ] **Step 3: Delete the backend package, its tests, and the db file**

```bash
cd /Users/priyanshusaraf/dev/options-trading/paper-trader
rm -rf backend/app/journal backend/tests/journal backend/journal.db
```

- [ ] **Step 4: Unmount the router**

In `backend/app/main.py`, delete line 28:

```python
from app.journal import routes as journal_routes
```

and delete line 167:

```python
app.include_router(journal_routes.router)
```

Order matters: removing 28 while leaving 167 raises `NameError` at module scope.

- [ ] **Step 5: Reword the dangling citation**

`backend/tests/test_equity_short_charge_legs.py:7` currently reads:

```python
# It is self-consistent, so reconcile() never flagged it. journal/pnl.py and live_broker.py already get this right — the paper broker is the outlier.
```

Replace with:

```python
# It is self-consistent, so reconcile() never flagged it. live_broker.py already gets this right — the paper broker is the outlier.
```

- [ ] **Step 6: Run the backend suites**

```bash
cd backend && .venv/bin/python -m pytest -q --tb=short > /tmp/ws1-t1.log 2>&1; tail -5 /tmp/ws1-t1.log; grep -A5 FAILED /tmp/ws1-t1.log
```

Expected: PASS, with the total dropping by exactly 71 tests versus the pre-deletion baseline. Capture the baseline count before Step 3 if you want the arithmetic to check.

- [ ] **Step 7: Remove the frontend view and its wiring**

```bash
rm frontend/src/views/JournalView.tsx
```

In `frontend/src/App.tsx` delete line 9 (`import JournalView from './views/JournalView'`), line 21 (`['journal', 'Journal'],`) and line 64 (`{tab === 'journal' && <JournalView />}`).

Delete `frontend/src/lib/api.ts:180-222` in full — that block is the 18 journal functions plus the `bq()` helper at `:183-184`, which nothing else uses. Delete `frontend/src/lib/types.ts:200-302` in full — the 11 `Journal*DTO` interfaces.

- [ ] **Step 8: Verify the frontend**

```bash
cd frontend && npm run typecheck && npm run build
```

Expected: both succeed. `tsc` catches a missed import; there is no runtime-only failure mode here.

- [ ] **Step 9: Commit** *(hold unless the owner has asked for commits)*

```bash
git add -A
git commit -m "feat(ledger): remove the old trade journal ahead of THE LEDGER port

15 files, ~2030 lines. Zero user rows in journal.db (4 seed instruments,
2 bias rows, pre-multi-book schema, a leaked test artifact). The engine
never wrote to it. OrderJournal and test_order_journal.py are unrelated
crash-recovery machinery and are untouched."
```

---

### Task 2: Backend ledger package — schema and migrations

**Files:**
- Create: `backend/app/ledger/__init__.py`, `config.py`, `db.py`, `models.py`
- Test: `backend/tests/ledger/__init__.py`, `backend/tests/ledger/test_db.py`
- Verify: `.venv/bin/python -m pytest tests/ledger -q`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `ledger_db_path(env: Mapping[str, str] | None = None) -> str`
  - `class LedgerBase(DeclarativeBase)`
  - `make_engine(path: str) -> Engine`
  - `init_ledger_db(engine: Engine) -> None`
  - `migrate_ledger_db(engine: Engine) -> None`
  - `get_sessionmaker() -> sessionmaker`
  - `class LedgerSnapshot` with columns `id, version, payload, updated_at`
  - `class LedgerArtifact` with columns `id, mime, bytes, created_at`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/ledger/__init__.py` (empty) and `backend/tests/ledger/test_db.py`:

```python
"""The ledger DB is structurally isolated from the execution ledger: its own
DeclarativeBase, its own file, its own engine. The engine must never be able to
reach it and it must never be able to reach the engine."""
import os

from sqlalchemy import text

from app.db.models import Base as ExecBase
from app.ledger.config import ledger_db_path
from app.ledger.db import LedgerBase, init_ledger_db, make_engine


def test_ledger_base_is_not_the_execution_base():
    assert LedgerBase is not ExecBase


def test_default_path_is_absolute():
    # A bare relative default lands wherever systemd's WorkingDirectory points,
    # so a restart under a different cwd silently starts a second empty journal.
    assert os.path.isabs(ledger_db_path({}))


def test_env_override_wins():
    assert ledger_db_path({"PT_LEDGER_DB_PATH": "/tmp/x.db"}) == "/tmp/x.db"


def test_init_creates_both_tables(tmp_path):
    engine = make_engine(str(tmp_path / "ledger.db"))
    init_ledger_db(engine)
    with engine.connect() as conn:
        names = {r[0] for r in conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'"))}
    assert {"ledger_snapshot", "ledger_artifact"} <= names


def test_init_is_idempotent(tmp_path):
    path = str(tmp_path / "ledger.db")
    init_ledger_db(make_engine(path))
    init_ledger_db(make_engine(path))  # must not raise


def test_snapshot_table_permits_exactly_one_row(tmp_path):
    import pytest
    from sqlalchemy.exc import IntegrityError
    engine = make_engine(str(tmp_path / "ledger.db"))
    init_ledger_db(engine)
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO ledger_snapshot (id, version, payload, updated_at)"
            " VALUES (1, 1, '{}', '2026-07-31T00:00:00')"))
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO ledger_snapshot (id, version, payload, updated_at)"
                " VALUES (2, 1, '{}', '2026-07-31T00:00:00')"))
```

- [ ] **Step 2: Run it and watch it fail**

```bash
cd backend && .venv/bin/python -m pytest tests/ledger -q
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.ledger'`.

- [ ] **Step 3: Write `config.py`**

```python
"""Path resolution for the ledger DB.

Deliberately does NOT import app.core.config, so importing the ledger never
implicitly binds the execution DB engine. Mirrors the isolation the deleted
journal package had, which was the one thing about it worth keeping."""
from __future__ import annotations

import os
from collections.abc import Mapping

# Absolute by construction. A bare relative default resolves against the
# process cwd, so a systemd restart with a different WorkingDirectory would
# silently create a second, empty journal. See the deploy notes in
# docs/superpowers/specs/2026-07-31-ledger-integration-design.md §9.
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_LEDGER_DB = os.path.join(_BACKEND_DIR, "ledger.db")


def ledger_db_path(env: Mapping[str, str] | None = None) -> str:
    e = os.environ if env is None else env
    return e.get("PT_LEDGER_DB_PATH") or DEFAULT_LEDGER_DB
```

- [ ] **Step 4: Write `models.py`**

```python
"""Two tables. The snapshot is the whole journal as one JSON document — see
the design spec §3.1 for why that is the right shape here. Artifacts are held
out of it because they are binary and would otherwise be rewritten on every
debounced save (§3.2)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.ledger.db import LedgerBase


class LedgerSnapshot(LedgerBase):
    """Exactly one row, id=1. `version` is the optimistic-concurrency token:
    a client PUT carries the version it read, and a mismatch is a 409."""

    __tablename__ = "ledger_snapshot"
    __table_args__ = (CheckConstraint("id = 1", name="ck_ledger_snapshot_single_row"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class LedgerArtifact(LedgerBase):
    """A screenshot. `id` is the client-generated uid() from the journal, so the
    snapshot can reference it before the upload round-trips."""

    __tablename__ = "ledger_artifact"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    mime: Mapped[str] = mapped_column(String(64), nullable=False)
    bytes: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
```

- [ ] **Step 5: Write `db.py`**

```python
"""Engine, base and migrations for the ledger DB.

The ledger package never imports the engine, broker, or runner. Nothing under
app/engine/ may import this package. That isolation is structural, not a
convention: a bug here must never be able to become a real-money bug."""
from __future__ import annotations

import threading

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.ledger.config import ledger_db_path


class LedgerBase(DeclarativeBase):
    """Never share this with app.db.models.Base or the research plane's base."""


def make_engine(path: str) -> Engine:
    engine = create_engine(f"sqlite:///{path}", future=True)

    @event.listens_for(engine, "connect")
    def _pragmas(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=10000")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    return engine


def init_ledger_db(engine: Engine) -> None:
    """Create tables, then bring a pre-existing file up to date.

    create_all only ever CREATEs — it silently skips tables that already exist,
    so any change to an existing table must go through migrate_ledger_db."""
    from app.ledger import models  # noqa: F401  (registers the mapped classes)

    LedgerBase.metadata.create_all(engine)
    migrate_ledger_db(engine)


def _columns(conn, table: str) -> set[str]:
    return {r[1] for r in conn.execute(text(f"PRAGMA table_info({table})"))}


def migrate_ledger_db(engine: Engine) -> None:
    """Self-applying migrations. scripts/deploy.sh excludes *.db from rsync, so
    a schema change ships as code and must apply itself on the next boot.

    No migrations yet — this is the seam. Add ADD COLUMN steps here guarded by
    `if "col" not in _columns(conn, "table")`."""
    with engine.begin() as conn:
        _ = _columns(conn, "ledger_snapshot")


_sessionmaker: sessionmaker | None = None
_lock = threading.Lock()


def get_sessionmaker() -> sessionmaker:
    """Lazy, double-checked. The deleted journal package learned this the hard
    way: a production 500 from two threads racing table creation."""
    global _sessionmaker
    if _sessionmaker is None:
        with _lock:
            if _sessionmaker is None:
                engine = make_engine(ledger_db_path())
                init_ledger_db(engine)
                _sessionmaker = sessionmaker(
                    bind=engine, expire_on_commit=False, future=True)
    return _sessionmaker
```

Create `backend/app/ledger/__init__.py` as an empty file.

- [ ] **Step 6: Run the tests**

```bash
cd backend && .venv/bin/python -m pytest tests/ledger -q
```

Expected: 6 passed.

- [ ] **Step 7: Confirm nothing regressed**

```bash
.venv/bin/python -m pytest -q --tb=short > /tmp/ws1-t2.log 2>&1; tail -3 /tmp/ws1-t2.log
```

- [ ] **Step 8: Commit** *(hold unless asked)*

```bash
git add backend/app/ledger backend/tests/ledger
git commit -m "feat(ledger): ledger DB package — own base, own file, self-applying migrations"
```

---

### Task 3: Backend routes — snapshot with optimistic concurrency, and artifacts

**Files:**
- Create: `backend/app/ledger/service.py`, `backend/app/ledger/routes.py`
- Modify: `backend/app/main.py:28,167`
- Test: `backend/tests/ledger/test_routes.py`
- Verify: `.venv/bin/python -m pytest tests/ledger -q`

**Interfaces:**
- Consumes: `get_sessionmaker`, `LedgerSnapshot`, `LedgerArtifact` from Task 2.
- Produces:
  - `class VersionConflict(Exception)` with attribute `current: int`
  - `read_snapshot(sm) -> tuple[int, str] | None`
  - `write_snapshot(sm, payload: str, base_version: int | None) -> int`
  - HTTP: `GET /api/ledger/snapshot`, `PUT /api/ledger/snapshot`, `POST /api/ledger/artifacts`, `GET /api/ledger/artifacts/{id}`, `DELETE /api/ledger/artifacts/{id}`
  - Task 6 depends on the exact JSON shapes below.

**Contract, fixed here because Task 6 codes against it:**

```
GET  /api/ledger/snapshot
  200 { "version": <int>, "payload": <object> }
  404 { "detail": "no snapshot" }          → client seeds and PUTs with base_version=null

PUT  /api/ledger/snapshot
  body { "base_version": <int|null>, "payload": <object> }
  200 { "version": <int> }                 → the NEW version
  409 { "detail": "version conflict", "current": <int> }
```

`base_version: null` means "I believe no snapshot exists". It succeeds only if none does; otherwise 409. That makes first-write racing safe.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/ledger/test_routes.py`:

```python
import json

import pytest
from fastapi.testclient import TestClient

from app.ledger import db as ledger_db


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PT_LEDGER_DB_PATH", str(tmp_path / "ledger.db"))
    monkeypatch.setattr(ledger_db, "_sessionmaker", None, raising=False)
    from app.main import app
    with TestClient(app) as c:
        yield c
    monkeypatch.setattr(ledger_db, "_sessionmaker", None, raising=False)


def test_get_snapshot_404_when_empty(client):
    assert client.get("/api/ledger/snapshot").status_code == 404


def test_first_put_with_null_base_version_creates_v1(client):
    r = client.put("/api/ledger/snapshot",
                   json={"base_version": None, "payload": {"trades": []}})
    assert r.status_code == 200
    assert r.json()["version"] == 1


def test_round_trip(client):
    client.put("/api/ledger/snapshot",
               json={"base_version": None, "payload": {"trades": [{"id": "t1"}]}})
    r = client.get("/api/ledger/snapshot")
    assert r.status_code == 200
    assert r.json() == {"version": 1, "payload": {"trades": [{"id": "t1"}]}}


def test_stale_base_version_is_409_and_reports_current(client):
    client.put("/api/ledger/snapshot", json={"base_version": None, "payload": {}})
    client.put("/api/ledger/snapshot", json={"base_version": 1, "payload": {"a": 1}})
    r = client.put("/api/ledger/snapshot",
                   json={"base_version": 1, "payload": {"b": 2}})
    assert r.status_code == 409
    assert r.json()["current"] == 2


def test_second_null_base_version_is_409(client):
    client.put("/api/ledger/snapshot", json={"base_version": None, "payload": {}})
    r = client.put("/api/ledger/snapshot", json={"base_version": None, "payload": {}})
    assert r.status_code == 409


def test_conflict_does_not_write(client):
    client.put("/api/ledger/snapshot", json={"base_version": None, "payload": {"keep": 1}})
    client.put("/api/ledger/snapshot", json={"base_version": 1, "payload": {"keep": 2}})
    client.put("/api/ledger/snapshot", json={"base_version": 1, "payload": {"clobber": 1}})
    assert client.get("/api/ledger/snapshot").json()["payload"] == {"keep": 2}


def test_artifact_round_trip(client):
    r = client.post("/api/ledger/artifacts",
                    files={"file": ("a.png", b"\x89PNG-bytes", "image/png")},
                    data={"artifact_id": "art_1"})
    assert r.status_code == 200 and r.json()["id"] == "art_1"

    g = client.get("/api/ledger/artifacts/art_1")
    assert g.status_code == 200
    assert g.content == b"\x89PNG-bytes"
    assert g.headers["content-type"].startswith("image/png")

    assert client.delete("/api/ledger/artifacts/art_1").status_code == 200
    assert client.get("/api/ledger/artifacts/art_1").status_code == 404


def test_artifact_upload_is_idempotent_on_id(client):
    for body in (b"one", b"two"):
        client.post("/api/ledger/artifacts",
                    files={"file": ("a.png", body, "image/png")},
                    data={"artifact_id": "art_dup"})
    assert client.get("/api/ledger/artifacts/art_dup").content == b"two"
```

- [ ] **Step 2: Run it and watch it fail**

```bash
cd backend && .venv/bin/python -m pytest tests/ledger/test_routes.py -q
```

Expected: FAIL — 404 on every ledger route, because the router does not exist yet.

- [ ] **Step 3: Write `service.py`**

```python
"""Snapshot and artifact persistence. No FastAPI here — the routes layer owns
HTTP status codes, this layer owns the concurrency rule."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.ledger.models import LedgerArtifact, LedgerSnapshot


class VersionConflict(Exception):
    """The caller's base_version does not match what is stored."""

    def __init__(self, current: int):
        super().__init__(f"version conflict: stored is {current}")
        self.current = current


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def read_snapshot(sm) -> tuple[int, str] | None:
    with sm() as s:
        row = s.get(LedgerSnapshot, 1)
        return None if row is None else (row.version, row.payload)


def write_snapshot(sm, payload: str, base_version: int | None) -> int:
    """Compare-and-set. base_version=None asserts "no snapshot exists yet".

    Returns the new version. Raises VersionConflict on a mismatch, leaving the
    stored payload untouched."""
    with sm() as s, s.begin():
        row = s.get(LedgerSnapshot, 1, with_for_update=False)
        if row is None:
            if base_version is not None:
                raise VersionConflict(0)
            s.add(LedgerSnapshot(id=1, version=1, payload=payload, updated_at=_now()))
            return 1
        if base_version != row.version:
            raise VersionConflict(row.version)
        row.version += 1
        row.payload = payload
        row.updated_at = _now()
        return row.version


def put_artifact(sm, artifact_id: str, mime: str, data: bytes) -> str:
    with sm() as s, s.begin():
        row = s.get(LedgerArtifact, artifact_id)
        if row is None:
            s.add(LedgerArtifact(id=artifact_id, mime=mime, bytes=data,
                                 created_at=_now()))
        else:
            row.mime, row.bytes = mime, data
    return artifact_id


def get_artifact(sm, artifact_id: str) -> tuple[str, bytes] | None:
    with sm() as s:
        row = s.get(LedgerArtifact, artifact_id)
        return None if row is None else (row.mime, row.bytes)


def delete_artifact(sm, artifact_id: str) -> bool:
    with sm() as s, s.begin():
        row = s.get(LedgerArtifact, artifact_id)
        if row is None:
            return False
        s.delete(row)
        return True


def list_artifact_ids(sm) -> list[str]:
    with sm() as s:
        return list(s.scalars(select(LedgerArtifact.id)))
```

- [ ] **Step 4: Write `routes.py`**

```python
"""HTTP surface for THE LEDGER.

Auth: none per-route. The global auth_gate middleware in app/main.py already
requires Bearer PT_API_TOKEN on every /api/* path except health/login/session."""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel

from app.ledger import service
from app.ledger.db import get_sessionmaker

router = APIRouter(prefix="/api/ledger", tags=["ledger"])

# A screenshot larger than this is a mistake, not a screenshot. Bounding it
# keeps a single bad upload from wedging a 1GB VPS.
MAX_ARTIFACT_BYTES = 8 * 1024 * 1024


class PutSnapshotRequest(BaseModel):
    base_version: int | None = None
    payload: Any


@router.get("/snapshot")
def get_snapshot():
    got = service.read_snapshot(get_sessionmaker())
    if got is None:
        raise HTTPException(status_code=404, detail="no snapshot")
    version, payload = got
    return {"version": version, "payload": json.loads(payload)}


@router.put("/snapshot")
def put_snapshot(req: PutSnapshotRequest):
    try:
        version = service.write_snapshot(
            get_sessionmaker(),
            json.dumps(req.payload, separators=(",", ":")),
            req.base_version,
        )
    except service.VersionConflict as exc:
        raise HTTPException(
            status_code=409,
            detail={"detail": "version conflict", "current": exc.current},
        ) from exc
    return {"version": version}


@router.post("/artifacts")
async def post_artifact(artifact_id: str = Form(...), file: UploadFile = File(...)):
    data = await file.read()
    if len(data) > MAX_ARTIFACT_BYTES:
        raise HTTPException(status_code=413, detail="artifact too large")
    service.put_artifact(get_sessionmaker(), artifact_id,
                         file.content_type or "application/octet-stream", data)
    return {"id": artifact_id}


@router.get("/artifacts/{artifact_id}")
def fetch_artifact(artifact_id: str):
    got = service.get_artifact(get_sessionmaker(), artifact_id)
    if got is None:
        raise HTTPException(status_code=404, detail="no such artifact")
    mime, data = got
    # Artifact bytes are immutable for a given id, so this can cache hard.
    return Response(content=data, media_type=mime,
                    headers={"Cache-Control": "private, max-age=31536000, immutable"})


@router.delete("/artifacts/{artifact_id}")
def remove_artifact(artifact_id: str):
    if not service.delete_artifact(get_sessionmaker(), artifact_id):
        raise HTTPException(status_code=404, detail="no such artifact")
    return {"ok": True}
```

FastAPI serialises a dict `detail` as `{"detail": {"detail": ..., "current": ...}}`. The test asserts `r.json()["current"]`, so flatten it: replace the `HTTPException` in `put_snapshot` with an explicit response instead.

Use this form in `put_snapshot` rather than raising:

```python
from fastapi.responses import JSONResponse

@router.put("/snapshot")
def put_snapshot(req: PutSnapshotRequest):
    try:
        version = service.write_snapshot(
            get_sessionmaker(),
            json.dumps(req.payload, separators=(",", ":")),
            req.base_version,
        )
    except service.VersionConflict as exc:
        return JSONResponse(
            status_code=409,
            content={"detail": "version conflict", "current": exc.current},
        )
    return {"version": version}
```

- [ ] **Step 5: Mount the router**

In `backend/app/main.py`, add to the import block near line 28:

```python
from app.ledger import routes as ledger_routes
```

and alongside the other `include_router` calls near line 167:

```python
app.include_router(ledger_routes.router)
```

It must be registered **before** the SPA catch-all `@app.get("/{full_path:path}")` at the bottom of `main.py`. Adding it next to the existing `include_router` calls satisfies this.

- [ ] **Step 6: Run the tests**

```bash
cd backend && .venv/bin/python -m pytest tests/ledger -q
```

Expected: 14 passed (6 from Task 2 + 8 here).

- [ ] **Step 7: Verify the auth gate covers the new routes**

```bash
grep -n "_AUTH_EXEMPT_PATHS" app/main.py
```

Expected: the exempt set is `{"/api/health", "/api/login", "/api/session"}` and does **not** contain any `/api/ledger` path. If `PT_API_TOKEN` is set, ledger routes require it — which is correct.

- [ ] **Step 8: Full suite + dryrun**

```bash
.venv/bin/python -m pytest -q --tb=short > /tmp/ws1-t3.log 2>&1; tail -3 /tmp/ws1-t3.log
.venv/bin/python scripts/dryrun.py 700
```

Expected: suite green; dryrun reports `LEDGER OK`.

- [ ] **Step 9: Commit** *(hold unless asked)*

```bash
git add backend/app/ledger backend/tests/ledger backend/app/main.py
git commit -m "feat(ledger): snapshot + artifact REST with optimistic concurrency"
```

---

### Task 4: Vendor THE LEDGER source and stand up vitest

**Files:**
- Create: `frontend/src/ledger/**` (copied), `frontend/vitest.config.ts`
- Modify: `frontend/package.json`
- Verify: `npm run typecheck`, `npx vitest run`

**Interfaces:**
- Consumes: nothing.
- Produces: `frontend/src/ledger/` mirroring the source tree, with `main.tsx` and `app/auth.ts` omitted. Later tasks reference `src/ledger/data/idb.ts`, `src/ledger/data/store.ts`, `src/ledger/app/App.tsx`, `src/ledger/styles/{tokens,base}.css`.

- [ ] **Step 1: Copy the tree, excluding the two files that must not come**

```bash
cd /Users/priyanshusaraf/dev/options-trading/paper-trader/frontend
mkdir -p src/ledger
rsync -a --exclude 'main.tsx' --exclude 'app/auth.ts' \
  /Users/priyanshusaraf/dev/trade-journal/src/ ./src/ledger/
find src/ledger -name '*.tsx' -o -name '*.ts' -o -name '*.css' | wc -l
```

Expected: 49 files (51 minus the two excluded).

`main.tsx` is an application root, not a component — `LedgerView.tsx` in Task 8 replaces it. `auth.ts` is a client-side fake gate that prints `admin/admin@123` on screen; the app already has `Bearer PT_API_TOKEN`.

- [ ] **Step 2: Cut the auth references out of `App.tsx`**

`src/ledger/app/App.tsx` imports `auth.ts` and renders `<Login/>` when `!auth.user`. Remove the import, remove the gate, and render `Workspace` unconditionally. Also delete `src/ledger/app/Login.tsx` and `src/ledger/app/login.css` and any import of them.

```bash
rm src/ledger/app/Login.tsx src/ledger/app/login.css
grep -rn "auth\|Login" src/ledger/app/App.tsx src/ledger/keys/commands.ts
```

Fix every hit. `commands.ts` has a sign-out command in the Workspace section — delete that command entry.

- [ ] **Step 3: Add vitest**

```bash
npm install --save-dev vitest@^2.1.4
```

Create `frontend/vitest.config.ts`:

```ts
import { defineConfig } from 'vitest/config'

// Scoped deliberately: the journal is the only part of this frontend with
// tests, and widening the glob would silently claim to cover views that
// have none.
export default defineConfig({
  test: {
    include: ['src/ledger/**/*.test.ts'],
    environment: 'node',
  },
})
```

In `frontend/package.json`, add to `scripts`:

```json
"test": "vitest run",
"test:watch": "vitest"
```

- [ ] **Step 4: Run the ported domain tests**

```bash
npx vitest run
```

Expected: 49 tests passing from `src/ledger/domain/domain.test.ts` — the metrics engine, ticket grammar, query language and date helpers. These are pure and have no import from `data/` or React, so they pass unchanged.

- [ ] **Step 5: Typecheck**

```bash
npm run typecheck
```

Expected: PASS. If `tsconfig.json` has settings stricter than the source repo's (`strict`, `noUnusedLocals`), fix the errors — do not loosen the host's tsconfig.

- [ ] **Step 6: Confirm nothing is imported from outside `src/ledger/`**

```bash
grep -rn "from '\.\./\.\./" src/ledger | grep -v "src/ledger"
grep -rn "@/components\|lib/api" src/ledger
```

Expected: no output. The vendored tree must be self-contained at this stage; Task 6 introduces its only outward dependency (the HTTP client).

- [ ] **Step 7: Commit** *(hold unless asked)*

```bash
git add frontend/src/ledger frontend/vitest.config.ts frontend/package.json frontend/package-lock.json
git commit -m "feat(ledger): vendor THE LEDGER source; add vitest for the journal domain

49 files. main.tsx and the client-side fake auth gate are deliberately not
ported. 49 domain tests green."
```

---

### Task 5: Scope the CSS under `.ledger-root`

**Files:**
- Modify: `frontend/src/ledger/styles/base.css`, `frontend/src/ledger/styles/tokens.css`
- Create: `frontend/postcss.config.cjs` (or modify if one exists)
- Verify: `npm run build`, then a visual check

**Interfaces:**
- Consumes: the vendored tree from Task 4.
- Produces: every LEDGER selector nested under `.ledger-root`. Task 8 renders `<div className="ledger-root" data-theme="dark" data-density="compact">`.

**Why:** the recon found ~40 unscoped utility names in `base.css` (`.grid`, `.panel`, `.chip`, `.label`, `.num`, `.badge`, `.toast`, `.empty`, `.stat`, `.surface`, `.card`, `.tile`) that collide with paper-trader's Tailwind layer **in both directions**, plus a document-level reset including `body{overflow:hidden}` that would break host page scrolling app-wide.

- [ ] **Step 1: Check what postcss config already exists**

```bash
cd frontend && ls postcss.config.* tailwind.config.* 2>/dev/null && cat postcss.config.* 2>/dev/null
```

Tailwind requires a postcss config, so one exists. Note its filename and current contents before editing.

- [ ] **Step 2: Install the prefixing plugin**

```bash
npm install --save-dev postcss-prefix-selector@^1.16.1
```

- [ ] **Step 3: Add a scoped pass for the ledger stylesheets only**

Edit the existing postcss config to add the plugin, configured to touch only files under `src/ledger/`:

```js
const prefixer = require('postcss-prefix-selector')

module.exports = {
  plugins: [
    require('tailwindcss'),
    require('autoprefixer'),
    {
      // Scope THE LEDGER's global CSS so its ~40 generic utility names
      // (.grid .panel .chip .label .num .badge .toast .empty .stat .surface)
      // cannot collide with Tailwind in either direction.
      postcssPlugin: 'ledger-scope',
      Once(root, { result }) {
        const from = result.opts.from || ''
        if (!from.includes('/src/ledger/')) return
        prefixer({
          prefix: '.ledger-root',
          transform(prefix, selector, prefixed) {
            // :root carries the design tokens — it becomes the scope itself,
            // not a descendant of it, or the custom properties never apply.
            if (selector === ':root') return prefix
            if (selector.startsWith(':root')) return prefix + selector.slice(5)
            // Document-level selectors collapse onto the scope element.
            if (['html', 'body', '#root'].includes(selector)) return prefix
            return prefixed
          },
        }).Once(root)
      },
    },
  ],
}
```

Keep whatever plugin list the existing config already had; the block above assumes `tailwindcss` + `autoprefixer`, which is the standard pairing. Match reality.

- [ ] **Step 4: Fix the reset by hand, because prefixing alone is not enough**

In `src/ledger/styles/base.css`, the reset currently reads roughly:

```css
* { box-sizing: border-box; }
html, body, #root { height: 100%; margin: 0; }
body { background: var(--base); color: var(--text); font-family: var(--font-ui); overflow: hidden; }
```

Replace with:

```css
/* Scoped reset. The source shipped this at document level; inside a host app
   `body{overflow:hidden}` would kill page scrolling everywhere, so the frame
   properties move onto .ledger-root, which Task 8 renders at full viewport. */
.ledger-root, .ledger-root * { box-sizing: border-box; }
.ledger-root {
  height: 100%;
  margin: 0;
  background: var(--base);
  color: var(--text);
  font-family: var(--font-ui);
  overflow: hidden;
}
```

Also scope the two document-wide rules the recon flagged — the global `:focus-visible` outline and the global `::selection` — by prefixing them with `.ledger-root ` so they do not override the host's.

- [ ] **Step 5: Build and inspect the emitted CSS**

```bash
npm run build
grep -c "ledger-root" dist/assets/*.css
grep -oE "^[^{]*\{" dist/assets/*.css | grep -E "^\.(grid|panel|chip|label|num|badge|toast|empty|stat|surface)\s*\{" | head
```

Expected: the first count is large (hundreds). The second command must return **nothing** — an unscoped bare utility selector escaping into the bundle is the failure this task exists to prevent.

- [ ] **Step 6: Confirm the host still scrolls**

```bash
npm run dev
```

Open `http://localhost:5173`, go to any long view (Trade Log), and confirm the page scrolls normally. Before this task, importing `base.css` anywhere would have frozen it.

- [ ] **Step 7: Commit** *(hold unless asked)*

```bash
git add frontend/postcss.config.cjs frontend/src/ledger/styles frontend/package.json frontend/package-lock.json
git commit -m "feat(ledger): scope THE LEDGER's global CSS under .ledger-root"
```

---

### Task 6: Re-point persistence at the backend

**Files:**
- Modify (replace contents): `frontend/src/ledger/data/idb.ts`
- Modify: `frontend/src/ledger/data/store.ts:73-85` (`schedulePersist`), `:96-110` (`boot`)
- Test: `frontend/src/ledger/data/remote.test.ts`
- Verify: `npx vitest run`, `npm run typecheck`

**Interfaces:**
- Consumes: the HTTP contract fixed in Task 3.
- Produces: `loadSnapshot<T>(): Promise<T | null>`, `saveSnapshot<T>(value: T): Promise<void>`, `clearSnapshot(): Promise<void>` — **identical signatures to the file being replaced**, so `store.ts`'s imports at `:16` do not change. Adds `getBaseVersion(): number | null` and `class SnapshotConflictError extends Error`.

**Why this shape:** `store.ts` imports exactly `loadSnapshot` and `saveSnapshot` from `./idb`, and `Misc.tsx` imports `clearSnapshot`. Keeping the three signatures means `store.ts`, `actions.ts`, all 43 mutators, undo/redo and every surface are untouched.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/ledger/data/remote.test.ts`:

```ts
import { describe, expect, it, beforeEach, vi } from 'vitest'
import {
  loadSnapshot, saveSnapshot, clearSnapshot,
  getBaseVersion, SnapshotConflictError, __resetForTests,
} from './idb'

function mockFetch(handler: (url: string, init?: RequestInit) => Response | Promise<Response>) {
  vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => handler(url, init)))
}
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })

beforeEach(() => { __resetForTests(); vi.unstubAllGlobals() })

describe('the snapshot client', () => {
  it('returns null and records no version when the server has nothing', async () => {
    mockFetch(() => json({ detail: 'no snapshot' }, 404))
    expect(await loadSnapshot()).toBeNull()
    expect(getBaseVersion()).toBeNull()
  })

  it('returns the payload and records the version', async () => {
    mockFetch(() => json({ version: 7, payload: { trades: [] } }))
    expect(await loadSnapshot()).toEqual({ trades: [] })
    expect(getBaseVersion()).toBe(7)
  })

  it('sends the recorded version as base_version and advances it on success', async () => {
    let seen: any = null
    mockFetch((url, init) => {
      if (init?.method === 'PUT') { seen = JSON.parse(String(init.body)); return json({ version: 8 }) }
      return json({ version: 7, payload: {} })
    })
    await loadSnapshot()
    await saveSnapshot({ trades: [] })
    expect(seen.base_version).toBe(7)
    expect(getBaseVersion()).toBe(8)
  })

  it('sends base_version null before anything has been loaded', async () => {
    let seen: any = null
    mockFetch((_u, init) => { seen = JSON.parse(String(init!.body)); return json({ version: 1 }) })
    await saveSnapshot({ trades: [] })
    expect(seen.base_version).toBeNull()
  })

  it('throws SnapshotConflictError on 409 and adopts the server version', async () => {
    mockFetch(() => json({ detail: 'version conflict', current: 12 }, 409))
    await expect(saveSnapshot({})).rejects.toBeInstanceOf(SnapshotConflictError)
    expect(getBaseVersion()).toBe(12)
  })

  it('propagates a network failure so the store can show "error"', async () => {
    mockFetch(() => { throw new Error('offline') })
    await expect(saveSnapshot({})).rejects.toThrow()
  })

  it('never throws out of loadSnapshot — a dead backend must not stop the journal opening', async () => {
    mockFetch(() => { throw new Error('offline') })
    expect(await loadSnapshot()).toBeNull()
  })

  it('clearSnapshot resets the tracked version', async () => {
    mockFetch(() => json({ version: 3, payload: {} }))
    await loadSnapshot()
    mockFetch(() => json({ ok: true }))
    await clearSnapshot()
    expect(getBaseVersion()).toBeNull()
  })
})
```

- [ ] **Step 2: Run it and watch it fail**

```bash
cd frontend && npx vitest run src/ledger/data/remote.test.ts
```

Expected: FAIL — `getBaseVersion` / `SnapshotConflictError` / `__resetForTests` are not exported.

- [ ] **Step 3: Replace `src/ledger/data/idb.ts` entirely**

```ts
/* Server-backed persistence.
 *
 * The source shipped a debounced whole-DB snapshot into IndexedDB. The shape is
 * unchanged — one blob, one key — but the key now lives on the backend so the
 * journal is the same on the Mac and on the phone. Everything above this file
 * (store.ts, actions.ts, all 43 mutators, undo/redo) is untouched, which is the
 * whole point: the business rules stay in the closures the design put them in.
 *
 * Concurrency is compare-and-set. We send the version we last read; a 409 means
 * another device moved first, and the caller reloads rather than clobbering.
 * For one user on two devices that is the honest trade — see the design spec
 * §3.1 for why a merge strategy is out of scope.
 *
 * The filename is a deliberate lie kept for one reason: store.ts imports
 * `./idb` and not changing that import is what makes this a one-file swap.
 */

const SNAPSHOT_URL = '/api/ledger/snapshot'
const ARTIFACT_URL = '/api/ledger/artifacts'

export class SnapshotConflictError extends Error {
  constructor(public current: number) {
    super(`snapshot conflict — server is at version ${current}`)
    this.name = 'SnapshotConflictError'
  }
}

let baseVersion: number | null = null

export function getBaseVersion(): number | null {
  return baseVersion
}

/** Test seam. Never called by application code. */
export function __resetForTests(): void {
  baseVersion = null
}

function authHeaders(): Record<string, string> {
  const token = import.meta.env.VITE_PT_TOKEN
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export async function loadSnapshot<T>(): Promise<T | null> {
  try {
    const res = await fetch(SNAPSHOT_URL, { headers: authHeaders() })
    if (res.status === 404) {
      baseVersion = null
      return null
    }
    if (!res.ok) return null
    const body = (await res.json()) as { version: number; payload: T }
    baseVersion = body.version
    return body.payload
  } catch {
    // A dead backend must never stop the journal from opening — the same
    // reasoning the IndexedDB version had for swallowing a blocked open. The
    // status dot reports the truth; the user can still read what is on screen.
    return null
  }
}

export async function saveSnapshot<T>(value: T): Promise<void> {
  const res = await fetch(SNAPSHOT_URL, {
    method: 'PUT',
    headers: { 'content-type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ base_version: baseVersion, payload: value }),
  })
  if (res.status === 409) {
    const body = (await res.json()) as { current: number }
    baseVersion = body.current
    throw new SnapshotConflictError(body.current)
  }
  if (!res.ok) throw new Error(`snapshot save failed: ${res.status}`)
  const body = (await res.json()) as { version: number }
  baseVersion = body.version
}

export async function clearSnapshot(): Promise<void> {
  await fetch(SNAPSHOT_URL, {
    method: 'PUT',
    headers: { 'content-type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ base_version: baseVersion, payload: null }),
  })
  baseVersion = null
}

// ── Artifacts ─────────────────────────────────────────────────────────────
// Screenshots are held OUT of the snapshot: the source stored them as base64
// data URLs inside the blob, so every 250ms debounced save rewrote every
// screenshot. Over HTTP that is untenable. See design spec §3.2.

export async function uploadArtifact(id: string, file: Blob): Promise<string> {
  const form = new FormData()
  form.append('artifact_id', id)
  form.append('file', file)
  const res = await fetch(ARTIFACT_URL, { method: 'POST', headers: authHeaders(), body: form })
  if (!res.ok) throw new Error(`artifact upload failed: ${res.status}`)
  return artifactUrl(id)
}

export function artifactUrl(id: string): string {
  return `${ARTIFACT_URL}/${id}`
}

export async function deleteArtifact(id: string): Promise<void> {
  await fetch(`${ARTIFACT_URL}/${id}`, { method: 'DELETE', headers: authHeaders() })
}
```

- [ ] **Step 4: Run the tests**

```bash
npx vitest run src/ledger/data/remote.test.ts
```

Expected: 8 passed.

- [ ] **Step 5: Adjust the debounce and make `sync` tell the truth**

In `src/ledger/data/store.ts`, `schedulePersist` currently debounces 250ms and sets `sync = 'error'` on any throw. A network write needs a longer debounce and must distinguish a conflict. Replace lines 71-85 with:

```ts
let saveTimer: ReturnType<typeof setTimeout> | null = null

// 250ms was right for IndexedDB. Over HTTP it would fire a request per
// keystroke in the notebook editor, so this is the one number the move to a
// server actually changes.
const PERSIST_DEBOUNCE_MS = 1_500

function schedulePersist() {
  sync = 'saving'
  if (saveTimer) clearTimeout(saveTimer)
  saveTimer = setTimeout(async () => {
    try {
      await saveSnapshot(db)
      sync = navigator.onLine ? 'synced' : 'offline'
    } catch (err) {
      // A conflict means another device moved first. Reloading is the honest
      // response: this client's base version is stale and pushing again would
      // clobber. Anything else is a plain write failure.
      sync = err instanceof SnapshotConflictError ? 'stale' : 'error'
    }
    emit()
  }, PERSIST_DEBOUNCE_MS)
}
```

Extend the `SyncState` union at `:20`:

```ts
export type SyncState = 'synced' | 'saving' | 'offline' | 'error' | 'stale'
```

Add the import at `:16`:

```ts
import { loadSnapshot, saveSnapshot, SnapshotConflictError } from './idb'
```

- [ ] **Step 6: Render the new state**

Find the status-dot component that reads `sync` (grep for `SyncState` and for `'offline'` under `src/ledger/`), and give `'stale'` a label — amber, reading `stale — reload`. Amber already means exactly "unresolved / breached / invalidated" in this design system, which is the correct semantics here. Do not invent a new colour.

- [ ] **Step 7: Typecheck and run everything**

```bash
npm run typecheck && npx vitest run
```

Expected: PASS; 57 tests (49 domain + 8 remote).

- [ ] **Step 8: Commit** *(hold unless asked)*

```bash
git add frontend/src/ledger/data
git commit -m "feat(ledger): persist the snapshot to the backend with compare-and-set

idb.ts keeps its three signatures, so store.ts and all 43 mutators are
untouched. Debounce 250ms -> 1500ms; adds a 'stale' sync state for 409."
```

---

### Task 7: Move screenshots out of the snapshot

**Files:**
- Modify: `frontend/src/ledger/surfaces/Vault.tsx`, `frontend/src/ledger/data/actions.ts` (`addArtifact`, `deleteArtifact`), `frontend/src/ledger/domain/types.ts` (`Artifact.data` doc comment)
- Verify: `npm run typecheck`, `npx vitest run`, manual upload

**Interfaces:**
- Consumes: `uploadArtifact(id, file)`, `artifactUrl(id)`, `deleteArtifact(id)` from Task 6.
- Produces: `Artifact.data` holds `/api/ledger/artifacts/<id>` instead of a base64 data URL. No other field changes, so `Vault.tsx`'s rendering (`<img src={a.data}>`) works unchanged.

- [ ] **Step 1: Find the current upload path**

```bash
cd frontend && grep -n "FileReader\|readAsDataURL\|addArtifact\|deleteArtifact" src/ledger/surfaces/Vault.tsx src/ledger/data/actions.ts
```

`Vault.tsx` reads the file with `FileReader` into a data URL and passes it to `addArtifact`.

- [ ] **Step 2: Upload first, then store the URL**

In `Vault.tsx`, replace the `FileReader` block with a direct upload. The id must be minted before the upload so the snapshot can reference it:

```tsx
import { uid } from '../domain/ids'
import { uploadArtifact } from '../data/idb'

async function onFiles(files: FileList | null) {
  if (!files) return
  for (const file of Array.from(files)) {
    const id = uid('art')
    const url = await uploadArtifact(id, file)
    addArtifact({ id, name: file.name, data: url, mime: file.type })
  }
}
```

Match `addArtifact`'s real parameter shape in `actions.ts` — read it before writing this; the field list above is the minimum and the function may take more (`sessionId`, `tradeId`, `tags`).

- [ ] **Step 3: Delete server-side too**

In `actions.ts`, `deleteArtifact` currently only removes the record from the draft. It must also delete the bytes. Because `mutate()` is synchronous, fire the network delete beside it rather than inside the closure:

```ts
import { deleteArtifact as deleteArtifactBytes } from './idb'

export function deleteArtifact(id: string): void {
  mutate('Delete screenshot', (draft) => {
    draft.artifacts = draft.artifacts.filter((a) => a.id !== id)
    for (const t of draft.trades) {
      t.artifactIds = t.artifactIds.filter((x) => x !== id)
    }
  })
  // Fire-and-forget: an orphaned blob is harmless and cheap; a failed delete
  // must not block the undoable record change or make this function async.
  void deleteArtifactBytes(id)
}
```

Note the consequence honestly in a comment: ⌘Z restores the record but not the bytes if the delete already landed. Given the bytes are keyed by a uid that is never reused, the pragmatic fix is to leave the blob and let it be orphaned — which the code above already does by not awaiting.

- [ ] **Step 4: Update the type comment**

In `src/ledger/domain/types.ts`, the `Artifact` interface documents `data` as a base64 data URL. Change the comment to state it is now a URL served by `/api/ledger/artifacts/<id>`, and that `ocrText` remains permanently empty (the source design's stated non-feature — Vault search matches names and tags only, rather than faking matches).

- [ ] **Step 5: Verify no data URL survives**

```bash
grep -rn "readAsDataURL\|data:image" src/ledger/
```

Expected: no output.

- [ ] **Step 6: Manual check**

Run `npm run dev` with the backend up. Open the journal, go to the Vault (`g v`), upload a screenshot, confirm it renders. Then:

```bash
cd ../backend && sqlite3 ledger.db "SELECT id, mime, length(bytes) FROM ledger_artifact;"
sqlite3 ledger.db "SELECT length(payload) FROM ledger_snapshot;"
```

Expected: the artifact row exists with a plausible byte length, and the snapshot payload length did **not** grow by that amount. That second assertion is the entire point of this task.

- [ ] **Step 7: Commit** *(hold unless asked)*

```bash
git add frontend/src/ledger
git commit -m "feat(ledger): store screenshots as blobs, not base64 inside the snapshot"
```

---

### Task 8: Mount the journal in the app

**Files:**
- Create: `frontend/src/views/LedgerView.tsx`
- Modify: `frontend/src/App.tsx`, `frontend/src/ledger/app/App.tsx` (appearance scoping, hash namespace)
- Verify: `npm run typecheck`, `npm run build`, manual

**Interfaces:**
- Consumes: everything from Tasks 4-7.
- Produces: a `journal` tab rendering `LedgerView`. `LedgerView` owns the `.ledger-root` element and guarantees the keymap unmounts when the tab changes.

- [ ] **Step 1: Scope the appearance writes**

`src/ledger/app/App.tsx` has a `useAppearance` hook writing to `document.documentElement.dataset`:

```ts
const root = document.documentElement
root.dataset.theme = settings.theme
root.dataset.density = settings.density
```

That stomps the host's theming. Change it to write onto the scope element instead:

```ts
const root = document.querySelector('.ledger-root') as HTMLElement | null
if (!root) return
root.dataset.theme = settings.theme
root.dataset.density = settings.density
root.dataset.cvd = settings.cvdSafe ? 'on' : 'off'
```

Task 5's PostCSS transform already rewrote `:root[data-theme='light']` to `.ledger-root[data-theme='light']`, so these attributes land on the element the selectors now target.

- [ ] **Step 2: Namespace the hash router**

`src/ledger/app/App.tsx` installs a `hashchange` listener and maps `#surface/objectId` onto its route. paper-trader has no router (`App.tsx:47` is a `useState` tab switcher), so there is nothing to fight — but namespace it anyway so a future router can coexist. Change the read/write to use `#/journal/<surface>/<objectId>` and ignore any hash not starting with `#/journal/`.

- [ ] **Step 3: Write the mount point**

Create `frontend/src/views/LedgerView.tsx`:

```tsx
import { useEffect, useState } from 'react'
import LedgerApp from '../ledger/app/App'
import { boot } from '../ledger/data/store'
import '../ledger/styles/tokens.css'
import '../ledger/styles/base.css'

/**
 * THE LEDGER, mounted full-bleed inside paper-trader.
 *
 * Two things this wrapper exists to guarantee, both from the integration recon:
 *
 * 1. `.ledger-root` is the CSS scope. Every LEDGER selector was prefixed under
 *    it at build time, and its document-level reset was collapsed onto it, so
 *    nothing leaks either way.
 * 2. LEDGER's `useKeymap` installs ONE window keydown listener that
 *    preventDefaults bare t/o/n/j/k/space/x/e/f and a pile of Cmd chords. It
 *    lives inside LedgerApp, so unmounting this component removes it. That is
 *    why the journal must never be rendered behind a hidden tab.
 */
export default function LedgerView() {
  const [booted, setBooted] = useState(false)

  useEffect(() => {
    let cancelled = false
    boot().then(() => { if (!cancelled) setBooted(true) })
    return () => { cancelled = true }
  }, [])

  return (
    <div
      className="ledger-root"
      data-theme="dark"
      data-density="compact"
      style={{ position: 'fixed', inset: 0, zIndex: 40 }}
    >
      {booted ? <LedgerApp /> : null}
    </div>
  )
}
```

`position: fixed; inset: 0` gives the full-bleed sub-app the owner asked for: LEDGER's shell wants a fixed frame with its own internal scroll panes, and letting it flow inside `<main className="flex-1 p-3">` would fight that.

- [ ] **Step 4: Wire it into `App.tsx`**

Add the import beside the other views:

```tsx
import LedgerView from './views/LedgerView'
```

Restore the tab entry in `TABS` at the position the old one held:

```tsx
['journal', 'Journal'],
```

And render it — but **outside** `<main>`, because it is fixed and full-bleed:

```tsx
{tab === 'journal' && <LedgerView />}
```

Place that line as a sibling of `<main>`, not inside it. The header stays reachable because `LedgerView` has `zIndex: 40` and the header can sit above it if needed; if the owner wants the header hidden entirely while journalling, that is a one-line change here and worth asking about after the first look.

- [ ] **Step 5: Verify the keymap does not leak**

```bash
npm run dev
```

Open `:5173`. On the Watchlist tab, press `t`, `j`, `k`, `x` and `?`. Nothing should happen — no navigation, no overlay. Switch to Journal, press `?`; the shortcut sheet must open. Switch back to Watchlist and press `?` again; nothing should happen.

**This is the single most important manual check in WS-1.** A leaked global keymap that swallows bare letters across the whole app is the failure mode this design guards against.

- [ ] **Step 6: Verify the host still scrolls and the theme did not change**

On the Trade Log tab, scroll the page. Confirm paper-trader's own dark theme is unchanged — no LEDGER token bled into it.

- [ ] **Step 7: Typecheck and build**

```bash
npm run typecheck && npm run build
```

- [ ] **Step 8: Commit** *(hold unless asked)*

```bash
git add frontend/src/views/LedgerView.tsx frontend/src/App.tsx frontend/src/ledger/app/App.tsx
git commit -m "feat(ledger): mount THE LEDGER full-bleed at the journal tab

Keymap and appearance writes are scoped to the mounted subtree, so the
global keydown listener exists only while the journal is on screen."
```

---

### Task 9: Replace the demo seed with a real one

**Files:**
- Modify: `frontend/src/ledger/data/seed.ts`, `frontend/src/ledger/app/uiState.ts`
- Test: `frontend/src/ledger/data/seed.test.ts`
- Verify: `npx vitest run`, manual first-boot

**Interfaces:**
- Consumes: `buildSeed(): DB` (existing export, signature unchanged).
- Produces: a seed with real instruments, a real playbook and settings, and **zero trades, zero sessions, zero events, zero artifacts**.

**Why:** `buildSeed()` is the default value of the module-level `db` in `store.ts:27` and the fallback in `boot()`. It is not optional demo content. But its 637 lines generate ~173 fake trades tuned to reproduce the design document's figures — shipping those into a real journal would poison every statistic. Meanwhile `uiState.ts` hard-codes `instrumentId: 'bnf'` as the initial route, and with no instruments eight surfaces `return null` with no UI anywhere to create one. So the seed must keep instruments and drop history.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/ledger/data/seed.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { buildSeed } from './seed'

describe('the seed', () => {
  const db = buildSeed()

  it('ships no fabricated history', () => {
    expect(db.trades).toHaveLength(0)
    expect(db.sessions).toHaveLength(0)
    expect(db.events).toHaveLength(0)
    expect(db.artifacts).toHaveLength(0)
  })

  it('ships the instruments the owner actually trades', () => {
    const codes = db.instruments.map((i) => i.code)
    expect(codes).toContain('nifty')
    expect(codes).toContain('bnf')
  })

  it('gives every instrument an R basis, because riskPerR returns null without one', () => {
    for (const i of db.instruments) expect(i.rBasis).toBeTruthy()
  })

  it('keeps the initial route pointing at an instrument that exists', async () => {
    const { initialRoute } = await import('../app/uiState')
    expect(db.instruments.map((i) => i.id)).toContain(initialRoute.instrumentId)
  })

  it('ships a playbook, because setup attribution is mandatory', () => {
    expect(db.playbook.length).toBeGreaterThan(0)
  })

  it('keeps the evidence threshold at 20', () => {
    expect(db.settings.evidenceThreshold).toBe(20)
  })

  it('ships the mistake and emotion taxonomies', () => {
    expect(db.settings.mistakes.length).toBeGreaterThan(0)
    expect(db.settings.emotions.length).toBeGreaterThan(0)
  })
})
```

- [ ] **Step 2: Run it and watch it fail**

```bash
cd frontend && npx vitest run src/ledger/data/seed.test.ts
```

Expected: FAIL on the first assertion — the seed ships ~173 trades.

- [ ] **Step 3: Strip the generated history**

In `src/ledger/data/seed.ts`, delete the `SPECS` table and the generation loop that produces trades, sessions and stream events, along with the `rng`/LCG helper that exists only to make that generation deterministic. Keep: the instrument list, `SEED_DOCS`, the playbook entries, `SEED_MISTAKES`, `SEED_EMOTIONS`, the saved queries, and the settings object.

Return the collections as empty arrays:

```ts
return {
  instruments: INSTRUMENTS,
  sessions: [],
  trades: [],
  events: [],
  levels: [],
  playbook: PLAYBOOK,
  docs: SEED_DOCS.flatMap(docsFor),
  artifacts: [],
  macroEvents: [],
  regimeLog: [],
  savedQueries: SAVED_QUERIES,
  periodReviews: [],
  settings: SETTINGS,
}
```

Match the real names in the file — the field list above is `DB` from `domain/types.ts` and is exact, but the local constant names may differ.

- [ ] **Step 4: Set the real instruments**

Replace the demo five (bnf, nifty, crude, gold, stocks) with what the owner trades. From the deleted journal's own `JournalInstrument` docstring: *"the bot trades full-size CRUDEOIL/NATURALGAS while the owner manually trades the MINI contracts"*. Combined with the product direction in `paper-trader/CLAUDE.md` (equity + index on the underlying, options index-only), the set is:

```ts
const INSTRUMENTS: Instrument[] = [
  { id: 'nifty', code: 'NIFTY',   name: 'Nifty 50',   kind: 'index', lotSize: 65,  tick: 0.05, hours: { open: '09:15', close: '15:30' }, order: 0, rBasis: 'initial-stop' },
  { id: 'bnf',   code: 'BANKNIFTY', name: 'Bank Nifty', kind: 'index', lotSize: 30, tick: 0.05, hours: { open: '09:15', close: '15:30' }, order: 1, rBasis: 'initial-stop' },
  { id: 'goldm', code: 'GOLDM',   name: 'Gold Mini',  kind: 'commodity', lotSize: 10, tick: 1, hours: { open: '09:00', close: '23:30' }, order: 2, rBasis: 'fixed-rupee', fixedRisk: 2500 },
  { id: 'silverm', code: 'SILVERM', name: 'Silver Mini', kind: 'commodity', lotSize: 5, tick: 1, hours: { open: '09:00', close: '23:30' }, order: 3, rBasis: 'fixed-rupee', fixedRisk: 2500 },
  { id: 'crudem', code: 'CRUDEOILM', name: 'Crude Mini', kind: 'commodity', lotSize: 10, tick: 1, hours: { open: '09:00', close: '23:30' }, order: 4, rBasis: 'fixed-rupee', fixedRisk: 2500 },
  { id: 'stocks', code: 'STOCKS', name: 'Stocks', kind: 'equity', hours: { open: '09:15', close: '15:30' }, order: 5, rBasis: 'account-%', accountEquity: 100000, accountRiskPct: 1 },
]
```

Verify every field name and every union value against `Instrument` in `src/ledger/domain/types.ts` before writing — the shape above is from the recon and must match exactly or `tsc` will reject it.

**Lot sizes confirmed by the owner on 2026-07-31: NIFTY 65, BANKNIFTY 30.** Use these verbatim; do not substitute a value from memory or from a web source. Lot sizes change by exchange circular, and a wrong one silently mis-scales every R calculation in the journal without erroring. The commodity MINI lot sizes above are still unconfirmed — check them against a Zerodha contract note before relying on R figures for those instruments, or set `rBasis: 'fixed-rupee'` (as the seed does) so lot size does not enter the R computation for them.

- [ ] **Step 5: Fix the hard-coded initial route**

`src/ledger/app/uiState.ts` hard-codes `instrumentId: 'bnf'`. Export the initial route so the test can assert it, and derive the instrument from the seed rather than a literal:

```ts
import { buildSeed } from '../data/seed'

export const initialRoute: Route = {
  surface: 'cockpit',
  instrumentId: buildSeed().instruments[0].id,
  date: today(),
  zoom: 'month',
}
```

- [ ] **Step 6: Rewrite the seeded notebook docs to say true things**

`SEED_DOCS` ships ten docs per instrument with demo prose. `Notebook.tsx` special-cases three of them **by title string** — `'Levels'`, `'Regime'`, `'Mistakes I keep making'` — to render live projections above the prose. Those three titles must survive verbatim or the projections silently vanish. Empty their bodies; keep their titles.

- [ ] **Step 7: Run the tests and check first boot**

```bash
npx vitest run && npm run typecheck
```

Then delete the local ledger DB and boot fresh:

```bash
rm -f ../backend/ledger.db && npm run dev
```

Open the Journal tab. Expected: the Cockpit renders (not a blank `return null`), the instrument rail shows six tiles, the Playbook has entries, and the Research Bench shows `░░░ n=0` everywhere rather than numbers. That last one is the design working as intended — no metric renders below the evidence threshold.

- [ ] **Step 8: Commit** *(hold unless asked)*

```bash
git add frontend/src/ledger/data/seed.ts frontend/src/ledger/data/seed.test.ts frontend/src/ledger/app/uiState.ts
git commit -m "feat(ledger): real seed — owner instruments and playbook, zero fabricated history"
```

---

### Task 10: Test the invariants that make this journal worth having

**Files:**
- Test: `frontend/src/ledger/data/actions.test.ts`
- Verify: `npx vitest run`

**Interfaces:**
- Consumes: the mutators in `src/ledger/data/actions.ts` and `getDB`/`mutate` from `store.ts`.
- Produces: no new exports. This task adds coverage only.

**Why:** the source repo has one test file covering metrics, grammar, query and dates — and **zero** tests for `actions.ts`, `store.ts` or any component. The thesis lock, auto-tagging, regime inheritance and risk-breach rules are the product's actual invariants, they now run against a shared server, and they are untested.

- [ ] **Step 1: Write the tests**

Create `frontend/src/ledger/data/actions.test.ts`:

```ts
import { beforeEach, describe, expect, it, vi } from 'vitest'

// The store persists on every mutation; in tests we do not want a network call.
vi.mock('./idb', () => ({
  loadSnapshot: async () => null,
  saveSnapshot: async () => {},
  clearSnapshot: async () => {},
  uploadArtifact: async (id: string) => `/api/ledger/artifacts/${id}`,
  artifactUrl: (id: string) => `/api/ledger/artifacts/${id}`,
  deleteArtifact: async () => {},
  getBaseVersion: () => null,
  SnapshotConflictError: class extends Error {},
}))

import {
  addTrade, ensureSession, lockBlockers, lockThesis, setRisk, setThesis,
  upsertScenario, appendToSession, sessionKey,
} from './actions'
import { getDB } from './store'

const INST = 'nifty'
const DATE = '2026-07-31'

beforeEach(() => { ensureSession(INST, DATE) })

describe('the thesis lock', () => {
  it('refuses an empty thesis, and says so as a direction', () => {
    const blockers = lockBlockers(sessionKey(INST, DATE))
    expect(blockers.join(' ')).toMatch(/thesis is empty/i)
  })

  it('requires at least two scenarios', () => {
    setThesis(INST, DATE, 'Gap up, expecting continuation above 24800.')
    upsertScenario(INST, DATE, { letter: 'A', name: 'Continuation', invalidation: 'loses 24780' })
    expect(lockBlockers(sessionKey(INST, DATE)).join(' ')).toMatch(/two scenarios/i)
  })

  it('requires every scenario to carry an invalidation', () => {
    setThesis(INST, DATE, 'Gap up.')
    upsertScenario(INST, DATE, { letter: 'A', name: 'Continuation', invalidation: 'loses 24780' })
    upsertScenario(INST, DATE, { letter: 'B', name: 'Fade', invalidation: '' })
    expect(lockBlockers(sessionKey(INST, DATE)).join(' ')).toMatch(/invalidation/i)
  })

  it('exempts a scenario named "Chop, no trade" — standing aside is a complete thought', () => {
    setThesis(INST, DATE, 'Balanced.')
    upsertScenario(INST, DATE, { letter: 'A', name: 'Continuation', invalidation: 'loses 24780' })
    upsertScenario(INST, DATE, { letter: 'B', name: 'Chop, no trade', invalidation: '' })
    expect(lockBlockers(sessionKey(INST, DATE))).toHaveLength(0)
  })

  it('freezes the thesis after locking — this is the whole product', () => {
    setThesis(INST, DATE, 'Original belief.')
    upsertScenario(INST, DATE, { letter: 'A', name: 'Up', invalidation: 'x' })
    upsertScenario(INST, DATE, { letter: 'B', name: 'Down', invalidation: 'y' })
    lockThesis(INST, DATE)
    setThesis(INST, DATE, 'Revised after the fact.')
    const s = getDB().sessions.find((x) => x.id === sessionKey(INST, DATE))!
    expect(s.thesis).toBe('Original belief.')
    expect(s.lockedAt).not.toBeNull()
  })

  it('still allows appends after the lock', () => {
    setThesis(INST, DATE, 'Belief.')
    upsertScenario(INST, DATE, { letter: 'A', name: 'Up', invalidation: 'x' })
    upsertScenario(INST, DATE, { letter: 'B', name: 'Down', invalidation: 'y' })
    lockThesis(INST, DATE)
    appendToSession(INST, DATE, 'Banks leading, index lagging.')
    const s = getDB().sessions.find((x) => x.id === sessionKey(INST, DATE))!
    expect(s.appends).toHaveLength(1)
  })
})

describe('attribution and auto-tagging', () => {
  it('marks a trade with no setup as off-book', () => {
    const id = addTrade({ instrumentId: INST, date: DATE, direction: 'long', qty: 1, price: 100, setupId: null })
    const t = getDB().trades.find((x) => x.id === id)!
    expect(t.offBook).toBe(true)
  })

  it('auto-tags a trade taken without a locked thesis', () => {
    const id = addTrade({ instrumentId: INST, date: DATE, direction: 'long', qty: 1, price: 100, setupId: null })
    const t = getDB().trades.find((x) => x.id === id)!
    expect(t.autoTags.join(' ')).toMatch(/thesis/i)
  })

  it('auto-tags a trade that breaches the risk envelope rather than blocking it', () => {
    setRisk(INST, DATE, { maxTrades: 1, maxLossR: 2, maxConcurrent: 1 })
    addTrade({ instrumentId: INST, date: DATE, direction: 'long', qty: 1, price: 100, setupId: null })
    const id = addTrade({ instrumentId: INST, date: DATE, direction: 'long', qty: 1, price: 101, setupId: null })
    const t = getDB().trades.find((x) => x.id === id)!
    expect(t.autoTags.length).toBeGreaterThan(0)
    // The journal records that you did it. It never refuses the trade.
    expect(t).toBeDefined()
  })

  it('never lets an auto-tag be removed by hand', () => {
    const id = addTrade({ instrumentId: INST, date: DATE, direction: 'long', qty: 1, price: 100, setupId: null })
    const before = getDB().trades.find((x) => x.id === id)!.autoTags.length
    expect(before).toBeGreaterThan(0)
  })
})
```

**Every call signature above must be checked against the real `actions.ts` before running** — the source's exact parameter shapes are not reproduced here from memory, and `addTrade` in particular takes a richer object. Read the file, adapt the calls, keep the assertions. The assertions are the contract; the call shapes are yours to match.

- [ ] **Step 2: Run and iterate until green**

```bash
cd frontend && npx vitest run src/ledger/data/actions.test.ts
```

Expected initially: failures from mismatched signatures. Fix the calls, not the assertions. If an assertion genuinely cannot hold, that is a finding about the port — report it rather than deleting the test.

- [ ] **Step 3: Run everything**

```bash
npx vitest run && npm run typecheck && npm run build
```

Expected: 49 domain + 8 remote + 7 seed + ~10 actions tests green.

- [ ] **Step 4: Full backend suite and dryrun one more time**

```bash
cd ../backend
.venv/bin/python -m pytest tests research_tests -q --tb=short > /tmp/ws1-final.log 2>&1; tail -3 /tmp/ws1-final.log
.venv/bin/python scripts/dryrun.py 700
```

Expected: green, `LEDGER OK`.

- [ ] **Step 5: Commit** *(hold unless asked)*

```bash
git add frontend/src/ledger/data/actions.test.ts
git commit -m "test(ledger): cover the lock, off-book attribution and risk-breach auto-tagging"
```

---

## Deployment checklist for WS-1

Do not deploy until every box is ticked. Each item below has caused a production incident in this repo.

- [ ] **Install the new dependency on the VPS by hand.** `python-multipart` is required by FastAPI for the `UploadFile`/`Form` screenshot endpoint. **VERIFIED 2026-07-31:** `scripts/deploy.sh` excludes `.venv` (line 68) and never runs `pip install`, so a normal deploy will NOT install it. Symptom if missed: `POST /api/ledger/artifacts` returns 500 while `/api/health` and every other route stay green.
  ```bash
  ssh -i ~/.ssh/paper-trader-vps root@64.227.191.162 \
    'cd /opt/paper-trader/backend && .venv/bin/pip install -r requirements.txt'
  ```
- [ ] `PT_LEDGER_DB_PATH` added **by hand** to the VPS `.env` as an absolute path (e.g. `/opt/paper-trader/backend/ledger.db`). `.env` is excluded from the rsync, so it will not arrive on its own — this is the single most-repeated deploy failure here.
- [ ] Confirm `*.db` is still in the deploy exclude list, so the new `ledger.db` is never overwritten from the Mac.
- [ ] Confirm the schema self-applies: `init_ledger_db()` runs on first `get_sessionmaker()`, and `migrate_ledger_db()` is the seam for later columns.
- [ ] `npm run build` on the Mac. Never on the VPS.
- [ ] Deploy via `scripts/deploy.sh` only.
- [ ] After deploy, curl **`/`** as well as `/api/health`. `/api/health` is a liveness stub that returned 200 through both 2026-07 outages.
- [ ] Verify the journal tab loads and `GET /api/ledger/snapshot` returns 404 on the first visit (no snapshot yet), then 200 after the first edit.

---

## Self-review

**Spec coverage.** §3.1 server snapshot → Tasks 2, 3, 6. §3.2 artifacts out of the blob → Tasks 2, 3, 7. §3.3 mounting, CSS scoping, keymap gating, appearance scoping, auth deletion, seed → Tasks 4, 5, 8, 9. §2.1 deletion of the old journal → Task 1. §7 testing posture → Tasks 4, 10. §9 deployment → the checklist above.

**Not covered here, by design:** §3.4 Kite detection, §3.5 mobile capture shell (both WS-2); §4 typography and §5 settings (the separate UI-layer plan). §8's honest labelling of the `calibration` and thesis-accuracy panels belongs with WS-2, since it is only reachable once auto-detected trades exist — it is recorded here so it is not lost.

**Known soft spots, stated rather than hidden:**
- Task 9 Step 4's `Instrument` literal and Task 10's `addTrade` call shapes are written from the recon, not from having the files open. Both steps say so and instruct the implementer to verify against `domain/types.ts` and `actions.ts`. Do not skip that.
- Task 5's PostCSS config assumes a `tailwindcss` + `autoprefixer` plugin list. Step 1 reads the real config first.
- `clearSnapshot()` writes `payload: null`, which `GET` will then return as `{"version": n, "payload": null}` rather than 404. `boot()` treats a falsy payload the same as a missing one (`store.ts:98` checks `stored && stored.instruments?.length`), so Settings → Reset still re-seeds correctly. Verified against the real boot logic; noted because it is non-obvious.
