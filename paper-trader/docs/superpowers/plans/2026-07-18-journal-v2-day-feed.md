# Journal v2 Day-Feed Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize the trade journal into a reverse-chronological day feed with a daily market-view narrative, timestamped quick notes, and persistent 6M/1M bias — and fix the near-white borders on shadcn primitives.

**Architecture:** Additive tables in the isolated `journal.db` (`JournalDay`, `JournalNote`, `JournalBias`) plus a `GET /api/journal/feed` endpoint that groups existing trades/missed/notes by calendar date. `JournalView.tsx` is rewritten from a form-stack into a day feed. No engine coupling — the journal package stays isolated. The white-border fix is a one-line base rule in `index.css`.

**Tech Stack:** FastAPI + SQLAlchemy (backend, pytest), React + TypeScript + Tailwind/shadcn (frontend, no test runner — verified by typecheck + driving the app).

## Global Constraints

- The journal package (`app/journal/*`) MUST NOT import the engine, broker, or runner; it uses its own `journal.db` via `JournalBase`. Never touch `app.db` or `app.engine` from journal code (except the read-only quote provider already used in `open-mtm`).
- All journal timestamps are naive-local (`dt.datetime.now()`), matching existing journal code. A row's day = its timestamp's `.date()`.
- New tables are created by `init_journal_db` via `create_all` (additive, non-destructive). Do NOT drop or rename `journal_views` — `JournalTrade.view_id` FKs to it.
- Bias horizons are exactly two: `'6M'` and `'1M'`. No mood/emoji field anywhere.
- Frontend: no new libraries. Reuse existing shadcn primitives (`Card`, `Input`, `Button`, `Badge`) and `lib/api.ts` / `lib/types.ts` patterns. Verify with `npm run typecheck`.
- Run backend tests from `backend/` with `.venv/bin/python -m pytest`. Commit after each green task.

---

### Task 1: White-border fix

**Files:**
- Modify: `frontend/src/index.css` (the `@layer base` block, around lines 8-40)

**Interfaces:**
- Consumes: nothing.
- Produces: nothing (pure CSS). All bare `border` classes now resolve to `hsl(var(--border))`.

- [ ] **Step 1: Add the shadcn base border rule**

In `frontend/src/index.css`, inside the existing `@layer base { … }` block, add the `*` rule as the FIRST statement (immediately after `@layer base {`):

```css
@layer base {
  * { @apply border-border; }

  body { @apply bg-bg text-zinc-200 font-mono text-sm; }
  /* …existing :root token block stays unchanged… */
```

- [ ] **Step 2: Typecheck + build**

Run (from `frontend/`): `npm run typecheck && npm run build`
Expected: both succeed, no errors.

- [ ] **Step 3: Verify visually**

Run the app (or `npm run dev`) and open the Journal, Dashboard, Settings, and Engine views. Expected: card/dialog/badge/select borders are the dark `#232733` edge, NOT near-white. No view shows a light seam.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/index.css
git commit -m "fix(ui): resolve bare shadcn borders to the dark edge token

Bare \`border\` on Card/Dialog/Select/Badge fell back to Tailwind's
gray-200 default because index.css lacked the canonical \`* { @apply
border-border }\` base rule. Near-white borders gone.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: New journal tables

**Files:**
- Modify: `backend/app/journal/models.py` (add three classes; extend the sqlalchemy import)
- Test: `backend/tests/journal/test_models.py` (append)

**Interfaces:**
- Consumes: `JournalBase` from `app.journal.db`.
- Produces: `JournalDay(entry_date: date PK, market_view: str|None, result: str|None, created_at, updated_at)`; `JournalNote(id: int PK, noted_at: datetime, body: str, instrument_symbol: str|None FK)`; `JournalBias(horizon: str PK, stance: str|None, note: str|None, updated_at)`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/journal/test_models.py` (mirror the existing fixture style in that file — it already builds a throwaway engine via `make_engine`/`init_journal_db`; reuse whatever session fixture is present. If the file has a `session` fixture, use it; otherwise copy the engine-setup pattern from `test_db.py`):

```python
import datetime as dt

from app.journal.models import JournalBias, JournalDay, JournalNote


def test_journal_day_roundtrip(session):
    session.add(JournalDay(entry_date=dt.date(2026, 7, 17),
                           market_view="nifty broke 24200",
                           result="waiting for monday",
                           created_at=dt.datetime(2026, 7, 17, 9),
                           updated_at=dt.datetime(2026, 7, 17, 9)))
    session.commit()
    row = session.get(JournalDay, dt.date(2026, 7, 17))
    assert row.market_view == "nifty broke 24200"
    assert row.result == "waiting for monday"


def test_journal_note_roundtrip(session):
    note = JournalNote(noted_at=dt.datetime(2026, 7, 17, 14, 32),
                       body="exited +900 too early", instrument_symbol=None)
    session.add(note)
    session.commit()
    assert note.id is not None
    assert session.get(JournalNote, note.id).body == "exited +900 too early"


def test_journal_bias_roundtrip(session):
    session.add(JournalBias(horizon="6M", stance="bullish", note="secular uptrend",
                            updated_at=dt.datetime(2026, 7, 17)))
    session.commit()
    assert session.get(JournalBias, "6M").stance == "bullish"
```

If `test_models.py` has no `session` fixture, add this fixture at the top of the file:

```python
import pytest
from app.journal.db import init_journal_db, make_engine, make_sessionmaker


@pytest.fixture
def session(tmp_path):
    engine = make_engine(str(tmp_path / "journal.db"))
    init_journal_db(engine)
    Session = make_sessionmaker(engine)
    with Session() as s:
        yield s
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `backend/`): `.venv/bin/python -m pytest tests/journal/test_models.py -k "roundtrip" -v`
Expected: FAIL with `ImportError: cannot import name 'JournalDay'` (etc.).

- [ ] **Step 3: Add the models**

In `backend/app/journal/models.py`, extend the sqlalchemy import to include `Date`:

```python
from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
```

Append these classes at the end of the file:

```python
class JournalDay(JournalBase):
    """One row per calendar date — the day-feed backbone. `market_view` is the
    free-text 'what I'm feeling' narrative; `result` is the end-of-day summary.
    Upserted by date; a date with only notes/trades needs no row here."""
    __tablename__ = "journal_days"
    entry_date: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    market_view: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now)


class JournalNote(JournalBase):
    """A timestamped free-text note ('ranting'), droppable anytime. Grouped into
    the day feed by `noted_at.date()`. Optional instrument tag; no mood field."""
    __tablename__ = "journal_notes"
    id: Mapped[int] = mapped_column(primary_key=True)
    noted_at: Mapped[dt.datetime] = mapped_column(DateTime)
    body: Mapped[str] = mapped_column(Text)
    instrument_symbol: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("journal_instruments.symbol"), nullable=True)


class JournalBias(JournalBase):
    """Persistent directional bias per horizon ('6M' | '1M') shown in the feed
    header. Seeded once; overwritten in place (not append-only)."""
    __tablename__ = "journal_bias"
    horizon: Mapped[str] = mapped_column(String(8), primary_key=True)
    stance: Mapped[str | None] = mapped_column(String(32), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/journal/test_models.py -v`
Expected: PASS (all, including existing tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/journal/models.py backend/tests/journal/test_models.py
git commit -m "feat(journal): JournalDay/JournalNote/JournalBias tables

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Service layer — day upsert, notes, bias, feed

**Files:**
- Modify: `backend/app/journal/service.py`
- Test: `backend/tests/journal/test_service.py` (append)

**Interfaces:**
- Consumes: `add_trade`, `add_missed`, `list_trades`, `list_missed`, `_trade_net`, existing session pattern.
- Produces:
  - `upsert_day(s, *, entry_date: date, market_view: str|None=None, result: str|None=None) -> JournalDay`
  - `add_note(s, *, body: str, noted_at: datetime, instrument_symbol: str|None=None) -> JournalNote`
  - `delete_note(s, note_id: int) -> bool`
  - `list_notes(s) -> list[JournalNote]`
  - `BIAS_HORIZONS = ("6M", "1M")`; `seed_bias(s) -> None`; `list_bias(s) -> list[JournalBias]`; `upsert_bias(s, *, horizon: str, stance: str|None=None, note: str|None=None) -> JournalBias` (raises `ValueError` on unknown horizon)
  - `feed(s, *, limit: int=60) -> dict` with shape `{"bias":[{horizon,stance,note,updated_at}], "stats":{net_pnl,win_rate,days_journaled,trades}, "days":[{date,market_view,result,net_pnl,notes:[{id,noted_at,body,instrument_symbol}],trades:[…],missed:[…]}]}`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/journal/test_service.py` (reuse its existing `session`/instrument-seeding fixtures; the file already seeds instruments for `add_trade` tests — follow that pattern, symbols like `GOLDM`):

```python
import datetime as dt

from app.journal import service
from app.journal.models import JournalInstrument


def _seed_inst(s, symbol="GOLDM"):
    if s.get(JournalInstrument, symbol) is None:
        s.add(JournalInstrument(symbol=symbol, exchange="MCX", lot_size=10,
                                tick_size=1.0, multiplier=1.0, active=True))
        s.commit()


def test_upsert_day_is_idempotent(session):
    d = dt.date(2026, 7, 17)
    service.upsert_day(session, entry_date=d, market_view="v1")
    service.upsert_day(session, entry_date=d, result="done")
    from app.journal.models import JournalDay
    rows = session.query(JournalDay).all()
    assert len(rows) == 1
    assert rows[0].market_view == "v1"   # preserved
    assert rows[0].result == "done"      # added


def test_add_and_delete_note(session):
    note = service.add_note(session, body="rant", noted_at=dt.datetime(2026, 7, 17, 10))
    assert service.delete_note(session, note.id) is True
    assert service.delete_note(session, note.id) is False


def test_seed_and_upsert_bias(session):
    service.seed_bias(session)
    assert {b.horizon for b in service.list_bias(session)} == {"6M", "1M"}
    service.upsert_bias(session, horizon="6M", stance="bullish", note="uptrend")
    assert next(b for b in service.list_bias(session) if b.horizon == "6M").stance == "bullish"


def test_upsert_bias_unknown_horizon_raises(session):
    service.seed_bias(session)
    import pytest
    with pytest.raises(ValueError):
        service.upsert_bias(session, horizon="3Y", stance="x")


def test_feed_groups_by_date(session):
    _seed_inst(session)
    d = dt.date(2026, 7, 17)
    service.add_note(session, body="morning", noted_at=dt.datetime(2026, 7, 17, 9))
    service.add_trade(session, symbol="GOLDM", direction="LONG", lots=1,
                      entry_price=100.0, entry_time=dt.datetime(2026, 7, 17, 10))
    service.upsert_day(session, entry_date=d, market_view="broke out")
    out = service.feed(session, limit=10)
    day = next(x for x in out["days"] if x["date"] == "2026-07-17")
    assert day["market_view"] == "broke out"
    assert len(day["notes"]) == 1
    assert len(day["trades"]) == 1


def test_feed_day_with_only_notes_appears(session):
    service.add_note(session, body="lone note", noted_at=dt.datetime(2026, 7, 16, 12))
    out = service.feed(session, limit=10)
    assert any(x["date"] == "2026-07-16" for x in out["days"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/journal/test_service.py -k "day or note or bias or feed" -v`
Expected: FAIL with `AttributeError: module 'app.journal.service' has no attribute 'upsert_day'`.

- [ ] **Step 3: Implement the service functions**

In `backend/app/journal/service.py`, extend the models import:

```python
from app.journal.models import (
    JournalBias, JournalDay, JournalInstrument, JournalMissed, JournalNote,
    JournalTag, JournalTrade, JournalView,
)
```

Add near the top (after `CURRENT_VIEW_NAME`):

```python
BIAS_HORIZONS = ("6M", "1M")
```

Append these functions at the end of the file:

```python
def upsert_day(s, *, entry_date, market_view=None, result=None) -> JournalDay:
    """Create or update the day row. Only non-None fields overwrite, so saving
    the narrative never wipes the result and vice versa."""
    now = dt.datetime.now()
    row = s.get(JournalDay, entry_date)
    if row is None:
        row = JournalDay(entry_date=entry_date, market_view=market_view,
                         result=result, created_at=now, updated_at=now)
        s.add(row)
    else:
        if market_view is not None:
            row.market_view = market_view
        if result is not None:
            row.result = result
        row.updated_at = now
    s.commit()
    return row


def add_note(s, *, body, noted_at, instrument_symbol=None) -> JournalNote:
    note = JournalNote(body=body, noted_at=noted_at, instrument_symbol=instrument_symbol)
    s.add(note)
    s.commit()
    return note


def delete_note(s, note_id) -> bool:
    row = s.get(JournalNote, note_id)
    if row is None:
        return False
    s.delete(row)
    s.commit()
    return True


def list_notes(s) -> list[JournalNote]:
    return list(s.execute(
        select(JournalNote).order_by(JournalNote.noted_at.desc())).scalars().all())


def seed_bias(s) -> None:
    changed = False
    for h in BIAS_HORIZONS:
        if s.get(JournalBias, h) is None:
            s.add(JournalBias(horizon=h, stance=None, note=None, updated_at=dt.datetime.now()))
            changed = True
    if changed:
        s.commit()


def list_bias(s) -> list[JournalBias]:
    return list(s.execute(
        select(JournalBias).order_by(JournalBias.horizon.desc())).scalars().all())


def upsert_bias(s, *, horizon, stance=None, note=None) -> JournalBias:
    row = s.get(JournalBias, horizon)
    if row is None:
        raise ValueError(f"unknown bias horizon {horizon}")
    row.stance = stance
    row.note = note
    row.updated_at = dt.datetime.now()
    s.commit()
    return row


def _note_row(nrow: JournalNote) -> dict:
    return {"id": nrow.id, "noted_at": nrow.noted_at.isoformat(),
            "body": nrow.body, "instrument_symbol": nrow.instrument_symbol}


def _trade_row(t: JournalTrade, inst: JournalInstrument | None) -> dict:
    return {"id": t.id, "instrument_symbol": t.instrument_symbol,
            "direction": t.direction, "lots": t.lots, "entry_price": t.entry_price,
            "entry_time": t.entry_time.isoformat(), "exit_price": t.exit_price,
            "exit_time": t.exit_time.isoformat() if t.exit_time else None,
            "setup_tag": t.setup_tag,
            "net_pnl": _trade_net(t, inst) if inst else None}


def _missed_row(m: JournalMissed) -> dict:
    return {"id": m.id, "instrument_symbol": m.instrument_symbol,
            "direction": m.direction, "seen_at": m.seen_at.isoformat(),
            "setup_tag": m.setup_tag, "skip_reason": m.skip_reason}


def feed(s, *, limit: int = 60) -> dict:
    insts = {r.symbol: r for r in s.execute(select(JournalInstrument)).scalars().all()}
    trades = list_trades(s)
    notes = list_notes(s)
    missed = list_missed(s)
    day_rows = {d.entry_date: d for d in s.execute(select(JournalDay)).scalars().all()}

    dates = set(day_rows)
    dates.update(t.entry_time.date() for t in trades)
    dates.update(nrow.noted_at.date() for nrow in notes)
    dates.update(m.seen_at.date() for m in missed)

    out_days = []
    for d in sorted(dates, reverse=True)[:limit]:
        drow = day_rows.get(d)
        d_trades = [t for t in trades if t.entry_time.date() == d]
        net = 0.0
        for t in d_trades:
            tn = _trade_net(t, insts.get(t.instrument_symbol)) if insts.get(t.instrument_symbol) else None
            if tn is not None:
                net += tn
        out_days.append({
            "date": d.isoformat(),
            "market_view": drow.market_view if drow else None,
            "result": drow.result if drow else None,
            "net_pnl": round(net, 2),
            "notes": [_note_row(nr) for nr in notes if nr.noted_at.date() == d],
            "trades": [_trade_row(t, insts.get(t.instrument_symbol)) for t in d_trades],
            "missed": [_missed_row(m) for m in missed if m.seen_at.date() == d],
        })

    closed = [t for t in trades if t.exit_price is not None]
    net_total, wins = 0.0, 0
    for t in closed:
        tn = _trade_net(t, insts.get(t.instrument_symbol)) if insts.get(t.instrument_symbol) else None
        if tn is not None:
            net_total += tn
            wins += 1 if tn > 0 else 0
    stats_row = {
        "net_pnl": round(net_total, 2),
        "win_rate": round(wins / len(closed), 3) if closed else None,
        "days_journaled": len(day_rows),
        "trades": len(closed),
    }

    bias_rows = [{"horizon": b.horizon, "stance": b.stance, "note": b.note,
                  "updated_at": b.updated_at.isoformat()} for b in list_bias(s)]
    return {"bias": bias_rows, "stats": stats_row, "days": out_days}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/journal/test_service.py -v`
Expected: PASS (new + existing).

- [ ] **Step 5: Commit**

```bash
git add backend/app/journal/service.py backend/tests/journal/test_service.py
git commit -m "feat(journal): day/note/bias service + feed assembly grouped by date

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Schemas + routes

**Files:**
- Modify: `backend/app/journal/schemas.py` (add three request models)
- Modify: `backend/app/journal/routes.py` (seed bias in sessionmaker; add endpoints)
- Test: `backend/tests/journal/test_routes.py` (append)

**Interfaces:**
- Consumes: `service.feed/upsert_day/add_note/delete_note/seed_bias/list_bias/upsert_bias`; existing `_session`, `_get_sessionmaker`, `_seed_instruments`.
- Produces endpoints: `GET /api/journal/feed?limit=`, `POST /api/journal/days`, `POST /api/journal/notes`, `DELETE /api/journal/notes/{id}`, `GET /api/journal/bias`, `PUT /api/journal/bias/{horizon}`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/journal/test_routes.py` (reuse its existing `TestClient` fixture — the file already builds the app/client and points `PT_JOURNAL_DB_PATH` at a tmp DB; follow that exact pattern):

```python
def test_feed_endpoint_empty_ok(client):
    r = client.get("/api/journal/feed")
    assert r.status_code == 200
    body = r.json()
    assert {b["horizon"] for b in body["bias"]} == {"6M", "1M"}
    assert body["days"] == []


def test_day_and_note_and_bias_flow(client):
    assert client.post("/api/journal/days", json={
        "entry_date": "2026-07-17", "market_view": "broke 24200"}).status_code == 200
    note = client.post("/api/journal/notes", json={"body": "exited early"})
    assert note.status_code == 200
    nid = note.json()["id"]
    assert client.put("/api/journal/bias/6M",
                      json={"stance": "bullish", "note": "uptrend"}).status_code == 200

    feed = client.get("/api/journal/feed").json()
    day = next(d for d in feed["days"] if d["date"] == "2026-07-17")
    assert day["market_view"] == "broke 24200"
    assert any(n["body"] == "exited early" for n in day["notes"])
    assert next(b for b in feed["bias"] if b["horizon"] == "6M")["stance"] == "bullish"

    assert client.delete(f"/api/journal/notes/{nid}").status_code == 200
    assert client.delete(f"/api/journal/notes/{nid}").status_code == 404


def test_note_unknown_instrument_400(client):
    r = client.post("/api/journal/notes", json={"body": "x", "instrument_symbol": "NOPE"})
    assert r.status_code == 400


def test_bias_unknown_horizon_400(client):
    r = client.put("/api/journal/bias/3Y", json={"stance": "x"})
    assert r.status_code == 400
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/journal/test_routes.py -k "feed or flow or unknown" -v`
Expected: FAIL (404 on `/feed` — route not defined).

- [ ] **Step 3: Add the schemas**

Append to `backend/app/journal/schemas.py`:

```python
class UpsertDayRequest(BaseModel):
    entry_date: dt.date
    market_view: str | None = None
    result: str | None = None


class AddNoteRequest(BaseModel):
    body: str
    noted_at: dt.datetime | None = None
    instrument_symbol: str | None = None


class UpsertBiasRequest(BaseModel):
    stance: str | None = None
    note: str | None = None
```

- [ ] **Step 4: Wire bias seeding + add the routes**

In `backend/app/journal/routes.py`, extend imports:

```python
from app.journal.models import JournalInstrument, JournalTrade, JournalView
from app.journal.schemas import (
    AddMissedRequest, AddNoteRequest, AddTradeRequest, AddViewRequest,
    CloseTradeRequest, UpsertBiasRequest, UpsertDayRequest,
)
```

In `_get_sessionmaker`, seed bias right after `_seed_instruments(_engine)`:

```python
        _seed_instruments(_engine)
        _seed_bias(_engine)
```

Add the `_seed_bias` helper next to `_seed_instruments`:

```python
def _seed_bias(engine) -> None:
    Session = make_sessionmaker(engine)
    with Session() as s:
        service.seed_bias(s)
```

Append these endpoints at the end of the file:

```python
@router.get("/feed")
def get_feed(limit: int = 60):
    with _session() as s:
        return service.feed(s, limit=limit)


@router.post("/days")
def upsert_day(req: UpsertDayRequest):
    with _session() as s:
        d = service.upsert_day(s, entry_date=req.entry_date,
                               market_view=req.market_view, result=req.result)
        return {"entry_date": d.entry_date.isoformat(),
                "market_view": d.market_view, "result": d.result}


@router.post("/notes")
def add_note(req: AddNoteRequest):
    with _session() as s:
        if req.instrument_symbol and s.get(JournalInstrument, req.instrument_symbol) is None:
            raise HTTPException(400, f"unknown journal instrument {req.instrument_symbol}")
        note = service.add_note(s, body=req.body,
                                noted_at=req.noted_at or dt.datetime.now(),
                                instrument_symbol=req.instrument_symbol)
        return {"id": note.id, "noted_at": note.noted_at.isoformat(),
                "body": note.body, "instrument_symbol": note.instrument_symbol}


@router.delete("/notes/{note_id}")
def delete_note(note_id: int):
    with _session() as s:
        if not service.delete_note(s, note_id):
            raise HTTPException(404, "note not found")
        return {"ok": True}


@router.get("/bias")
def get_bias():
    with _session() as s:
        return {"bias": [{"horizon": b.horizon, "stance": b.stance, "note": b.note,
                          "updated_at": b.updated_at.isoformat()} for b in service.list_bias(s)]}


@router.put("/bias/{horizon}")
def put_bias(horizon: str, req: UpsertBiasRequest):
    with _session() as s:
        try:
            b = service.upsert_bias(s, horizon=horizon, stance=req.stance, note=req.note)
        except ValueError as e:
            raise HTTPException(400, str(e))
        return {"horizon": b.horizon, "stance": b.stance, "note": b.note,
                "updated_at": b.updated_at.isoformat()}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/journal/ -v`
Expected: PASS (whole journal suite).

- [ ] **Step 6: Full-suite regression + commit**

Run: `.venv/bin/python -m pytest` (expect the pre-existing green count, journal additions included). Then:

```bash
git add backend/app/journal/schemas.py backend/app/journal/routes.py backend/tests/journal/test_routes.py
git commit -m "feat(journal): feed/days/notes/bias REST endpoints + bias seeding

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Frontend API + types

**Files:**
- Modify: `frontend/src/lib/types.ts` (add DTOs)
- Modify: `frontend/src/lib/api.ts` (add calls)

**Interfaces:**
- Consumes: existing `j()` (GET), `post()` helpers, and a `del()` helper (see Step 2 — add if missing).
- Produces: `JournalNoteDTO`, `JournalBiasDTO`, `JournalFeedTradeDTO`, `JournalFeedMissedDTO`, `JournalFeedDayDTO`, `JournalFeedDTO`; and `getJournalFeed`, `upsertJournalDay`, `addJournalNote`, `deleteJournalNote`, `getJournalBias`, `putJournalBias`.

- [ ] **Step 1: Add the DTOs**

Append to `frontend/src/lib/types.ts`:

```typescript
export interface JournalNoteDTO {
  id: number
  noted_at: string
  body: string
  instrument_symbol: string | null
}

export interface JournalBiasDTO {
  horizon: string
  stance: string | null
  note: string | null
  updated_at: string
}

export interface JournalFeedTradeDTO {
  id: number
  instrument_symbol: string
  direction: 'LONG' | 'SHORT'
  lots: number
  entry_price: number
  entry_time: string
  exit_price: number | null
  exit_time: string | null
  setup_tag: string | null
  net_pnl: number | null
}

export interface JournalFeedMissedDTO {
  id: number
  instrument_symbol: string
  direction: 'LONG' | 'SHORT'
  seen_at: string
  setup_tag: string | null
  skip_reason: string
}

export interface JournalFeedDayDTO {
  date: string
  market_view: string | null
  result: string | null
  net_pnl: number
  notes: JournalNoteDTO[]
  trades: JournalFeedTradeDTO[]
  missed: JournalFeedMissedDTO[]
}

export interface JournalFeedDTO {
  bias: JournalBiasDTO[]
  stats: { net_pnl: number; win_rate: number | null; days_journaled: number; trades: number }
  days: JournalFeedDayDTO[]
}
```

- [ ] **Step 2: Add the API calls**

Check `frontend/src/lib/api.ts` for a `del`/DELETE helper. If none exists, add one next to `post` (match its exact style — read the top of the file to copy the `fetch`/JSON/error-handling shape):

```typescript
export const del = (path: string) =>
  fetch(path, { method: 'DELETE' }).then((r) => {
    if (!r.ok) throw new Error(`${r.status}`)
    return r.json()
  })
```

Append to the journal section of `frontend/src/lib/api.ts`:

```typescript
export const getJournalFeed = (limit = 60): Promise<import('./types').JournalFeedDTO> =>
  j(`/api/journal/feed?limit=${limit}`)
export const upsertJournalDay = (body: { entry_date: string; market_view?: string; result?: string }) =>
  post('/api/journal/days', body)
export const addJournalNote = (body: { body: string; instrument_symbol?: string }) =>
  post('/api/journal/notes', body)
export const deleteJournalNote = (id: number) => del(`/api/journal/notes/${id}`)
export const getJournalBias = () => j('/api/journal/bias')
export const putJournalBias = (horizon: string, body: { stance?: string; note?: string }) =>
  put(`/api/journal/bias/${encodeURIComponent(horizon)}`, body)
```

If no `put` helper exists in `api.ts`, add one mirroring `post` but with `method: 'PUT'`.

- [ ] **Step 3: Typecheck**

Run (from `frontend/`): `npm run typecheck`
Expected: PASS, no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/types.ts frontend/src/lib/api.ts
git commit -m "feat(journal): frontend feed/day/note/bias DTOs + API calls

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Rewrite JournalView.tsx as a day feed

**Files:**
- Replace: `frontend/src/views/JournalView.tsx`

**Interfaces:**
- Consumes: Task 5 API/DTOs, existing `getJournalInstruments`, `addJournalTrade`, `closeJournalTrade`, shadcn `Card`/`Input`/`Button`/`Badge`.
- Produces: the default-exported `JournalView` component (route unchanged in `App.tsx`).

- [ ] **Step 1: Replace the component**

Overwrite `frontend/src/views/JournalView.tsx` with:

```tsx
import { useEffect, useMemo, useRef, useState } from 'react'
import {
  getJournalFeed, getJournalInstruments, upsertJournalDay,
  addJournalNote, deleteJournalNote, putJournalBias, addJournalTrade,
} from '../lib/api'
import type {
  JournalFeedDTO, JournalFeedDayDTO, JournalBiasDTO, JournalInstrumentDTO,
} from '../lib/types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'

const n = (v: number | null | undefined) => (v == null ? '—' : v.toFixed(2))
const pnlClass = (v: number | null | undefined) =>
  v == null ? 'text-muted' : v >= 0 ? 'text-emerald-400' : 'text-down'
const todayISO = () => new Date().toLocaleDateString('en-CA') // YYYY-MM-DD, local
const fmtDay = (iso: string) =>
  new Date(iso + 'T00:00:00').toLocaleDateString('en-IN',
    { weekday: 'short', day: '2-digit', month: 'short' })
const fmtTime = (iso: string) =>
  new Date(iso).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })

// Textarea that autosaves on blur only when its value actually changed.
function AutoText({ value, placeholder, onSave, rows = 3 }: {
  value: string | null; placeholder: string; onSave: (v: string) => void; rows?: number
}) {
  const [v, setV] = useState(value ?? '')
  const initial = useRef(value ?? '')
  useEffect(() => { setV(value ?? ''); initial.current = value ?? '' }, [value])
  return (
    <textarea
      className="w-full resize-y bg-panel2 border border-edge rounded px-2 py-1.5 text-sm text-zinc-200 placeholder:text-muted focus:outline-none focus:border-zinc-500"
      rows={rows} placeholder={placeholder} value={v}
      onChange={(e) => setV(e.target.value)}
      onBlur={() => { if (v !== initial.current) { initial.current = v; onSave(v) } }}
    />
  )
}

function BiasChip({ bias, onSave }: { bias: JournalBiasDTO; onSave: (stance: string, note: string) => void }) {
  const [editing, setEditing] = useState(false)
  const [stance, setStance] = useState(bias.stance ?? '')
  const [note, setNote] = useState(bias.note ?? '')
  useEffect(() => { setStance(bias.stance ?? ''); setNote(bias.note ?? '') }, [bias])
  if (editing) {
    return (
      <div className="flex items-center gap-1">
        <span className="text-xs font-semibold text-muted">{bias.horizon}</span>
        <Input className="w-24 h-auto bg-panel2 border-edge px-1.5 py-1 text-xs"
          placeholder="stance" value={stance} onChange={(e) => setStance(e.target.value)} />
        <Input className="w-40 h-auto bg-panel2 border-edge px-1.5 py-1 text-xs"
          placeholder="note" value={note} onChange={(e) => setNote(e.target.value)} />
        <Button variant="toolbar" size="toolbar"
          className="bg-emerald-500/20 text-emerald-300 border-emerald-500/40"
          onClick={() => { onSave(stance, note); setEditing(false) }}>✓</Button>
      </div>
    )
  }
  return (
    <button onClick={() => setEditing(true)}
      className="flex items-baseline gap-1.5 rounded border border-edge bg-panel2 px-2 py-1 hover:border-zinc-500">
      <span className="text-xs font-semibold text-muted">{bias.horizon}</span>
      <span className="text-sm font-semibold text-zinc-200">{bias.stance || '—'}</span>
      {bias.note && <span className="text-xs text-muted">· {bias.note}</span>}
    </button>
  )
}

function NoteComposer({ instruments, onAdd }: {
  instruments: JournalInstrumentDTO[]; onAdd: (body: string, sym?: string) => void
}) {
  const [body, setBody] = useState('')
  const [sym, setSym] = useState('')
  const submit = () => { if (body.trim()) { onAdd(body.trim(), sym || undefined); setBody(''); setSym('') } }
  return (
    <div className="flex gap-1">
      <Input className="flex-1 h-auto bg-panel2 border-edge px-2 py-1.5 text-sm"
        placeholder="drop a note…" value={body}
        onChange={(e) => setBody(e.target.value)}
        onKeyDown={(e) => { if (e.key === 'Enter') submit() }} />
      <select className="bg-panel2 border border-edge rounded px-1.5 py-1 text-xs text-muted"
        value={sym} onChange={(e) => setSym(e.target.value)}>
        <option value="">—</option>
        {instruments.map((i) => <option key={i.symbol} value={i.symbol}>{i.symbol}</option>)}
      </select>
      <Button variant="toolbar" size="toolbar" onClick={submit}
        className="text-muted hover:text-zinc-200">＋</Button>
    </div>
  )
}

function TradeComposer({ instruments, onAdd }: {
  instruments: JournalInstrumentDTO[]; onAdd: () => void
}) {
  const [open, setOpen] = useState(false)
  const [symbol, setSymbol] = useState(instruments[0]?.symbol ?? '')
  const [direction, setDirection] = useState<'LONG' | 'SHORT'>('LONG')
  const [lots, setLots] = useState('1')
  const [price, setPrice] = useState('')
  const [tag, setTag] = useState('')
  useEffect(() => { if (!symbol && instruments[0]) setSymbol(instruments[0].symbol) }, [instruments, symbol])
  const submit = async () => {
    if (!symbol || !price) return
    await addJournalTrade({ symbol, direction, lots: parseInt(lots, 10) || 1,
      entry_price: parseFloat(price), setup_tag: tag || undefined })
    setPrice(''); setTag(''); setOpen(false); onAdd()
  }
  if (!open) {
    return <Button variant="toolbar" size="toolbar" onClick={() => setOpen(true)}
      className="text-muted hover:text-zinc-200 self-start">＋ trade</Button>
  }
  return (
    <div className="grid grid-cols-2 gap-1.5">
      <select className="bg-panel2 border border-edge rounded px-2 py-1 text-sm"
        value={symbol} onChange={(e) => setSymbol(e.target.value)}>
        {instruments.map((i) => <option key={i.symbol} value={i.symbol}>{i.symbol}</option>)}
      </select>
      <div className="flex gap-1">
        {(['LONG', 'SHORT'] as const).map((d) => (
          <button key={d} onClick={() => setDirection(d)}
            className={`flex-1 rounded px-2 py-1 text-xs font-semibold border ${direction === d
              ? (d === 'LONG' ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                              : 'bg-down/20 text-down border-down/40')
              : 'bg-panel2 text-muted border-edge'}`}>{d}</button>
        ))}
      </div>
      <Input className="h-auto bg-panel2 border-edge px-2 py-1 text-sm" placeholder="lots"
        inputMode="numeric" value={lots} onChange={(e) => setLots(e.target.value)} />
      <Input className="h-auto bg-panel2 border-edge px-2 py-1 text-sm" placeholder="entry price"
        inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value)} />
      <Input className="col-span-2 h-auto bg-panel2 border-edge px-2 py-1 text-sm"
        placeholder="setup tag (optional)" value={tag} onChange={(e) => setTag(e.target.value)} />
      <Button variant="toolbar" size="toolbar" onClick={submit} disabled={!symbol || !price}
        className="bg-emerald-500/20 text-emerald-300 border-emerald-500/40 disabled:opacity-40">
        Log trade
      </Button>
      <Button variant="toolbar" size="toolbar" onClick={() => setOpen(false)}
        className="text-muted">Cancel</Button>
    </div>
  )
}

function DayCard({ day, instruments, isToday, reload }: {
  day: JournalFeedDayDTO; instruments: JournalInstrumentDTO[]; isToday: boolean; reload: () => void
}) {
  return (
    <Card className="p-3 flex flex-col gap-2.5">
      <div className="flex items-center gap-2">
        <span className="text-sm font-semibold text-zinc-200">{fmtDay(day.date)}</span>
        {isToday && <Badge variant="chip" className="bg-emerald-500/15 text-emerald-300">today</Badge>}
        {(day.trades.length > 0) && (
          <span className={`ml-auto text-xs font-semibold ${pnlClass(day.net_pnl)}`}>₹{n(day.net_pnl)}</span>
        )}
      </div>

      <AutoText value={day.market_view} placeholder="what am I feeling about the market today…"
        rows={3} onSave={(v) => upsertJournalDay({ entry_date: day.date, market_view: v }).then(reload)} />

      {day.notes.length > 0 && (
        <div className="flex flex-col gap-1">
          {day.notes.map((nt) => (
            <div key={nt.id} className="group flex items-start gap-2 text-sm">
              <span className="text-[11px] text-muted tabular-nums pt-0.5">{fmtTime(nt.noted_at)}</span>
              {nt.instrument_symbol && <Badge variant="chip" className="bg-panel2 text-muted">{nt.instrument_symbol}</Badge>}
              <span className="flex-1 text-zinc-300">{nt.body}</span>
              <button onClick={() => deleteJournalNote(nt.id).then(reload)}
                className="opacity-0 group-hover:opacity-100 text-muted hover:text-down text-xs">✕</button>
            </div>
          ))}
        </div>
      )}
      {isToday && <NoteComposer instruments={instruments}
        onAdd={(body, sym) => addJournalNote({ body, instrument_symbol: sym }).then(reload)} />}

      {day.trades.length > 0 && (
        <div className="flex flex-col gap-1 border-t border-edge/60 pt-2">
          <div className="text-[11px] uppercase tracking-wide text-muted">Trades taken</div>
          {day.trades.map((t) => (
            <div key={t.id} className="flex items-center gap-2 text-sm">
              <Badge variant="chip" className="bg-panel2 text-muted">{t.instrument_symbol}</Badge>
              <span className={`text-xs font-semibold ${t.direction === 'LONG' ? 'text-emerald-400' : 'text-down'}`}>{t.direction}</span>
              <span className="text-xs text-muted">{t.lots} lot @ {n(t.entry_price)}{t.exit_price != null ? ` → ${n(t.exit_price)}` : ''}</span>
              {t.setup_tag && <Badge variant="chip" className="bg-panel2 text-muted">{t.setup_tag}</Badge>}
              {t.net_pnl != null && <span className={`ml-auto text-xs font-semibold ${pnlClass(t.net_pnl)}`}>₹{n(t.net_pnl)}</span>}
            </div>
          ))}
        </div>
      )}
      {isToday && <TradeComposer instruments={instruments} onAdd={reload} />}

      {day.missed.length > 0 && (
        <div className="flex flex-col gap-1 border-t border-edge/60 pt-2">
          <div className="text-[11px] uppercase tracking-wide text-muted">Missed</div>
          {day.missed.map((m) => (
            <div key={m.id} className="flex items-center gap-2 text-sm">
              <Badge variant="chip" className="bg-amber-500/15 text-amber-300">{m.instrument_symbol}</Badge>
              <span className="text-xs text-muted flex-1">{m.skip_reason}</span>
            </div>
          ))}
        </div>
      )}

      <div className="border-t border-edge/60 pt-2">
        <div className="text-[11px] uppercase tracking-wide text-muted mb-1">Result</div>
        <AutoText value={day.result} placeholder="how did it go…" rows={2}
          onSave={(v) => upsertJournalDay({ entry_date: day.date, result: v }).then(reload)} />
      </div>
    </Card>
  )
}

export default function JournalView() {
  const [feed, setFeed] = useState<JournalFeedDTO | null>(null)
  const [instruments, setInstruments] = useState<JournalInstrumentDTO[]>([])

  const reload = () => {
    getJournalFeed().then(setFeed).catch(() => {})
    getJournalInstruments().then((d) => setInstruments(d.instruments || [])).catch(() => {})
  }
  useEffect(() => { reload(); const t = setInterval(reload, 15000); return () => clearInterval(t) }, [])

  // Pin "today" at the top, creating a synthetic empty day if none exists yet.
  const days = useMemo(() => {
    const list = feed?.days ?? []
    const today = todayISO()
    if (list.some((d) => d.date === today)) return list
    return [{ date: today, market_view: null, result: null, net_pnl: 0, notes: [], trades: [], missed: [] }, ...list]
  }, [feed])

  const stats = feed?.stats
  return (
    <div className="flex flex-col gap-3">
      <Card className="p-3 flex flex-wrap items-center gap-3">
        {(feed?.bias ?? []).map((b) => (
          <BiasChip key={b.horizon} bias={b}
            onSave={(stance, note) => putJournalBias(b.horizon, { stance, note }).then(reload)} />
        ))}
        {stats && (
          <div className="ml-auto flex items-center gap-4 text-xs">
            <span className="text-muted">net <span className={`font-semibold ${pnlClass(stats.net_pnl)}`}>₹{n(stats.net_pnl)}</span></span>
            <span className="text-muted">win {stats.win_rate == null ? '—' : `${Math.round(stats.win_rate * 100)}%`}</span>
            <span className="text-muted">{stats.days_journaled} days</span>
          </div>
        )}
      </Card>

      {days.map((d) => (
        <DayCard key={d.date} day={d} instruments={instruments} isToday={d.date === todayISO()} reload={reload} />
      ))}
    </div>
  )
}
```

- [ ] **Step 2: Typecheck + build**

Run (from `frontend/`): `npm run typecheck && npm run build`
Expected: both PASS.

- [ ] **Step 3: Verify by driving the app**

Start backend + frontend (or use the `run` skill). On the Journal view, confirm:
1. Header shows `6M` and `1M` bias chips; clicking one lets you set a stance + note that persists after refresh.
2. "Today" card is pinned at top. Typing in the market-view box and clicking away persists (reload the page — text remains).
3. `＋ note` adds a timestamped note into today; the ✕ on hover deletes it.
4. `＋ trade` logs a trade that appears under "Trades taken" with net P&L, and updates the header net.
5. No white borders anywhere.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/JournalView.tsx
git commit -m "feat(journal): rewrite JournalView as a reverse-chronological day feed

Daily market-view narrative + timestamped notes + folded-in trades/missed
+ editable 6M/1M bias header. Replaces the form-stack layout.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- White-border fix → Task 1. ✓
- Day feed / market-view narrative / notes thread / bias header / trades+missed folded in / result box → Tasks 3 (feed), 6 (UI). ✓
- New tables `JournalDay`/`JournalNote`/`JournalBias` → Task 2. ✓
- `GET /feed` + `POST /days` + `POST`/`DELETE /notes` + `GET`/`PUT /bias` → Task 4. ✓
- Light lifetime-stats strip, by-tag table dropped → Task 3 (`stats` in feed), Task 6 (header). ✓
- Manual quick-add kept → Task 6 (`TradeComposer`). ✓
- No mood/emoji → confirmed absent in models/schemas/UI. ✓
- Tests red-first for upsert idempotency / note CRUD / bias upsert / feed grouping → Tasks 2-4. ✓

**Placeholder scan:** No TBD/TODO; every code step shows full code. ✓

**Type consistency:** `feed()` returns `{bias,stats,days}` (service Task 3) → matches `JournalFeedDTO` (Task 5) → consumed in Task 6. `net_pnl` per trade is `_trade_row`'s key (Task 3) → `JournalFeedTradeDTO.net_pnl` (Task 5) → `t.net_pnl` (Task 6). Bias horizons `'6M'`/`'1M'` consistent across Tasks 2-4-6. ✓

**Note on `run` verification:** frontend has no test runner (per CLAUDE.md), so Tasks 1/5/6 rely on `npm run typecheck`/`build` + driving the app. That is the intended verification path here.
