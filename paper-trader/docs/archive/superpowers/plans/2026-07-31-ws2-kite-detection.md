# WS-2: Kite Manual-Trade Detection + Reason Capture — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Detect the owner's discretionary Kite trades, exclude the bot's, auto-create journal entries carrying real broker fills, and prompt for entry/exit reasoning — including from a phone.

**Architecture:** A read-only polling lane reads today's Kite orderbook, a pure classifier assigns each order `BOT | MANUAL | NEEDS_REVIEW` from two independent sources (the `pt-bot` order tag and the local `order_journal`), and manual fills are persisted to a `ledger_manual_fill` table on first sight. The journal's Inbox surface materialises them into real `Trade` records through the existing `addTrade()`, so every attribution rule still fires. A separate mobile capture shell makes the reasoning prompt answerable from a phone.

**Tech Stack:** FastAPI, SQLAlchemy 2, SQLite, kiteconnect 5.2.0 (read endpoints only), React 18 + TypeScript, vitest.

## Global Constraints

- **This feature is READ-AND-RECORD ONLY.** It must never write `positions` or `trades`, never influence `can_bot_close()`, and nothing under `app/engine/` may import `app/ledger/`. Task 10 greps to prove this. A detector bug must never be able to become a real-money bug.
- Depends on WS-1 (`docs/superpowers/plans/2026-07-31-ws1-ledger-port.md`). Reuse its names exactly: `LedgerBase`, `make_engine`, `init_ledger_db`, `migrate_ledger_db`, `get_sessionmaker`, `app/ledger/`, `frontend/src/ledger/`, `frontend/src/views/LedgerView.tsx`. Do not create parallel names.
- **Kite's orderbook is same-day only.** No historical order/trade API. Anything not captured before ~midnight is gone forever. Persist raw detections on first sight; run at least once near session close.
- **Never take `runner._lock` in the new lane.** The 2026-07-13 `risk_loop_stalled` incident was a sweep holding that lock 30s. This lane touches a different database and genuinely does not need it.
- **A failed read returns `None`, never `[]`.** This is a load-bearing repo convention (`providers/kite.py:174-187`: *"read failed — NOT a flat account (audit C4). Callers fail closed."*). "Failed to look" must never read as "found nothing".
- The read routes (`orders`, `trades`, `order.trades`, `portfolio.positions`) are **already** on the SafePaperKite allowlist (`app/providers/safe_kite.py:57-58`). **Do not widen the allowlist.** No safety-perimeter change is needed or permitted.
- `MockProvider` has no orders. The lane must no-op cleanly so `pytest` and `scripts/dryrun.py 700` stay green.
- Owner decisions: reasons may be written after the fact. **Do not build capture-latency tracking or a post-hoc badge** — the owner explicitly declined both.
- Schema changes go through `migrate_ledger_db()`, never `create_all` (which silently skips existing tables). `*.db` is excluded from rsync, so migrations must self-apply on boot.
- **Commit only when the owner asks** (`paper-trader/CLAUDE.md`). Each task shows a commit command; stage and hold unless told otherwise.
- Never run `git stash` / `git checkout -- .` / `git reset`.
- Deploy only via `scripts/deploy.sh`. Build the SPA on the Mac, never on the VPS.

---

## The GTT hole — decision, made here

Bot orders carry `tag="pt-bot"` (`live_broker.py:28`), applied at 5 placement sites. But **GTT-triggered stops carry no tag**: Zerodha creates the resulting order server-side and the GTT API has no tag field (`kite_order_client.py:89-103`). Worse, `Position.gtt_trigger_id` is set to `None` on every exit path (`live_broker.py:504`, `:614`, `:850`, `:877`), so a GTT that fired and closed its position leaves nothing behind to attribute against.

The spec offered two fixes. **We take option (b): any untagged order on a symbol the bot held that day is `NEEDS_REVIEW`, never `MANUAL`.**

Rationale: option (a) — a durable append-only GTT-id table — requires editing `live_broker.py`, which is the live order path. Touching it is a real-money change for a journalling feature, which is a bad trade. Option (b) is fail-closed, costs only an occasional review prompt on a symbol the owner also trades manually, and touches nothing in the execution path.

---

## File Structure

### Backend — created

| File | Responsibility |
|---|---|
| `backend/app/ledger/classify.py` | `classify_order()` — a pure function over dicts. No DB, no Kite, no I/O. The heart of the feature. |
| `backend/app/ledger/detect.py` | `detect_manual_fills()` — orchestration: read, classify, persist. |
| `backend/app/ledger/roundtrip.py` | `pair_round_trips()` — group fills by `order_id`, pair BUY/SELL into round trips. |
| `backend/app/ledger/lane.py` | The async polling lane. Owns cadence and the session-close run. |

### Backend — modified

| File | Change |
|---|---|
| `backend/app/ledger/models.py` | Add `LedgerManualFill`. |
| `backend/app/ledger/db.py` | Add the `ledger_manual_fill` migration step to `migrate_ledger_db()`. |
| `backend/app/ledger/service.py` | Add `upsert_manual_fills`, `list_manual_fills`, `claim_manual_fill`. |
| `backend/app/ledger/routes.py` | Add `GET /api/ledger/manual-fills`, `POST /api/ledger/manual-fills/{order_id}/claim`. |
| `backend/app/providers/kite.py` | Add `account_orders()` and `account_trades()`; add an `"orders"` throttle category. |
| `backend/app/providers/base.py` (or the Protocol) | Declare the two new optional reads. |
| `backend/app/engine/runner.py` | Start/stop the lane. **This is the only engine file touched, and only to schedule a task.** |
| `backend/app/core/config.py` | `manual_detect_enabled`, `manual_detect_seconds`. |

### Frontend — modified

| File | Change |
|---|---|
| `frontend/src/ledger/data/manualFills.ts` (new) | Client for the two new endpoints. |
| `frontend/src/ledger/surfaces/Misc.tsx` | Inbox gains a "needs a reason" queue. |
| `frontend/src/ledger/mobile/` (new) | The 4-screen capture shell. |
| `frontend/src/views/LedgerView.tsx` | Render the mobile shell below 768px. |
| `frontend/src/ledger/surfaces/Stats.tsx` | Relabel the two belief-dependent panels (spec §8). |

---

### Task 1: The classifier

**Files:**
- Create: `backend/app/ledger/classify.py`
- Test: `backend/tests/ledger/test_classify.py`
- Verify: `.venv/bin/python -m pytest tests/ledger/test_classify.py -q`

**Interfaces:**
- Consumes: nothing. Deliberately pure — no DB, no Kite, no imports from `app.engine`.
- Produces:
  - `BOT = "BOT"`, `MANUAL = "MANUAL"`, `NEEDS_REVIEW = "NEEDS_REVIEW"`
  - `BOT_TAG = "pt-bot"`
  - `classify_order(order: dict, bot_order_ids: set[str], bot_symbols_today: set[str]) -> str`

**Why three verdicts, not a boolean.** A bot trade mislabelled manual costs a confusing prompt. A manual trade mislabelled bot silently corrupts the bot's P&L attribution and is invisible. The asymmetry means every ambiguous case must land in a third bucket a human reads. This mirrors `reconcile.py`'s "flag, don't act" convention.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/ledger/test_classify.py`:

```python
"""The classifier is pure: dicts in, a verdict out. Every ambiguity must land in
NEEDS_REVIEW rather than being guessed either way."""
from app.ledger.classify import BOT, MANUAL, NEEDS_REVIEW, BOT_TAG, classify_order


def order(**kw):
    base = {"order_id": "o1", "tag": None, "tradingsymbol": "NIFTY25000CE",
            "status": "COMPLETE", "transaction_type": "BUY", "filled_quantity": 75,
            "average_price": 120.5, "product": "NRML"}
    base.update(kw)
    return base


def test_bot_tag_alone_is_enough():
    assert classify_order(order(tag=BOT_TAG), set(), set()) == BOT


def test_order_id_in_the_local_journal_is_enough():
    assert classify_order(order(order_id="o9"), {"o9"}, set()) == BOT


def test_untagged_and_unknown_on_a_symbol_the_bot_never_touched_is_manual():
    assert classify_order(order(), set(), set()) == MANUAL


def test_untagged_on_a_symbol_the_bot_held_today_is_needs_review():
    # A GTT-fired stop carries no tag and is created server-side by Zerodha, so
    # it is indistinguishable from a manual order except by symbol.
    assert classify_order(order(tradingsymbol="RELIANCE"), set(),
                          {"RELIANCE"}) == NEEDS_REVIEW


def test_a_missing_tag_key_is_treated_as_untagged_not_as_an_error():
    o = order()
    del o["tag"]
    assert classify_order(o, set(), set()) == MANUAL


def test_empty_string_tag_is_untagged():
    assert classify_order(order(tag=""), set(), set()) == MANUAL


def test_tag_comparison_is_exact_not_prefix():
    assert classify_order(order(tag="pt-bot-v2"), set(), set()) == MANUAL


def test_cnc_product_is_manual_even_on_a_bot_symbol():
    # The bot only ever uses MIS (equity intraday) or NRML (options). CNC is a
    # delivery trade and the bot cannot place one, so the symbol overlap that
    # normally forces NEEDS_REVIEW does not apply.
    assert classify_order(order(product="CNC", tradingsymbol="RELIANCE"),
                          set(), {"RELIANCE"}) == MANUAL


def test_a_none_order_id_cannot_match_the_journal():
    # A crash between _journal_open and the placement ack leaves order_id NULL.
    # It must not accidentally match a set containing None.
    assert classify_order(order(order_id=None), {None}, set()) == MANUAL


def test_order_ids_compare_as_strings():
    # Kite returns order_id as a string; order_journal may hold either.
    assert classify_order(order(order_id="250731000123"), {"250731000123"}, set()) == BOT


def test_symbol_match_is_case_insensitive():
    assert classify_order(order(tradingsymbol="reliance"), set(),
                          {"RELIANCE"}) == NEEDS_REVIEW


def test_the_tag_wins_over_a_symbol_overlap():
    assert classify_order(order(tag=BOT_TAG, tradingsymbol="RELIANCE"), set(),
                          {"RELIANCE"}) == BOT
```

- [ ] **Step 2: Run it and watch it fail**

```bash
cd backend && .venv/bin/python -m pytest tests/ledger/test_classify.py -q
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.ledger.classify'`.

- [ ] **Step 3: Implement**

```python
"""Bot-vs-manual attribution for orders read off the live Kite account.

Pure by construction: dicts in, a verdict out. No DB, no Kite, no engine import.
That is what makes it exhaustively testable, and this repo's strongest existing
convention (see app/engine/reconcile.py).

Two independent sources say "the bot placed this":

  1. tag == "pt-bot"   — broker-side truth. Survives a restart and a local DB
                         loss. Set at all 5 placement sites in live_broker.py.
  2. order_id in the local order_journal — local truth. Survives a broker read
                         that omits the tag.

Either alone is sufficient. Neither is necessary, which is why the untagged case
is not automatically manual:

  A GTT-triggered stop carries NO tag. Zerodha creates the order server-side and
  the GTT API has no tag field. Position.gtt_trigger_id is cleared on every exit
  path, so a fired-and-closed GTT leaves nothing to attribute against either.
  Rather than edit the live order path to record GTT ids — a real-money change
  for a journalling feature — we fail closed on symbol overlap.

The asymmetry that drives the whole design: a bot trade mislabelled MANUAL costs
a confusing prompt; a manual trade mislabelled BOT silently corrupts the bot's
P&L attribution and nobody ever sees it. So ambiguity goes to NEEDS_REVIEW.
"""
from __future__ import annotations

BOT = "BOT"
MANUAL = "MANUAL"
NEEDS_REVIEW = "NEEDS_REVIEW"

# Must stay identical to live_broker.TAG. Deliberately NOT imported from there:
# app/ledger/ must never import app/engine/. Task 10 asserts the two agree.
BOT_TAG = "pt-bot"

# The bot only ever places MIS (equity intraday) or NRML (options). It cannot
# place a delivery order, so CNC is proof of a human regardless of symbol.
_BOT_PRODUCTS = {"MIS", "NRML"}


def classify_order(
    order: dict,
    bot_order_ids: set[str],
    bot_symbols_today: set[str],
) -> str:
    """Return BOT, MANUAL or NEEDS_REVIEW for one Kite order dict.

    `bot_order_ids` — order_id values from the local order_journal.
    `bot_symbols_today` — tradingsymbols the bot placed or held today.
    """
    tag = (order.get("tag") or "").strip()
    if tag == BOT_TAG:
        return BOT

    oid = order.get("order_id")
    if oid is not None and str(oid) in bot_order_ids:
        return BOT

    product = (order.get("product") or "").strip().upper()
    if product and product not in _BOT_PRODUCTS:
        return MANUAL

    symbol = (order.get("tradingsymbol") or "").strip().upper()
    if symbol and symbol in {s.strip().upper() for s in bot_symbols_today}:
        # Untagged, unknown locally, on a symbol the bot touched today. This is
        # exactly the shape of a GTT-fired stop. Refuse to guess.
        return NEEDS_REVIEW

    return MANUAL
```

Note `bot_order_ids` must be built as a set of **strings** by the caller, and `None` must be filtered out — the test `test_a_none_order_id_cannot_match_the_journal` pins that.

- [ ] **Step 4: Run and confirm green**

```bash
.venv/bin/python -m pytest tests/ledger/test_classify.py -q
```

Expected: 12 passed.

- [ ] **Step 5: Commit** *(hold unless asked)*

```bash
git add backend/app/ledger/classify.py backend/tests/ledger/test_classify.py
git commit -m "feat(ledger): pure bot-vs-manual order classifier, fail-closed on the GTT hole"
```

---

### Task 2: The `ledger_manual_fill` table

**Files:**
- Modify: `backend/app/ledger/models.py`, `backend/app/ledger/db.py`
- Test: `backend/tests/ledger/test_manual_fill_model.py`
- Verify: `.venv/bin/python -m pytest tests/ledger -q`

**Interfaces:**
- Consumes: `LedgerBase`, `migrate_ledger_db` from WS-1 Task 2.
- Produces: `class LedgerManualFill` with columns `order_id` (PK), `tradingsymbol`, `exchange`, `product`, `side`, `qty`, `avg_price`, `order_ts`, `fill_ts`, `verdict`, `raw`, `claimed_trade`, `seen_at`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/ledger/test_manual_fill_model.py`:

```python
from datetime import datetime

from sqlalchemy import text

from app.ledger.db import init_ledger_db, make_engine, migrate_ledger_db
from app.ledger.models import LedgerManualFill


def test_table_is_created(tmp_path):
    engine = make_engine(str(tmp_path / "l.db"))
    init_ledger_db(engine)
    with engine.connect() as conn:
        names = {r[0] for r in conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'"))}
    assert "ledger_manual_fill" in names


def test_order_id_is_the_primary_key_so_repolling_is_idempotent(tmp_path):
    engine = make_engine(str(tmp_path / "l.db"))
    init_ledger_db(engine)
    with engine.connect() as conn:
        pk = [r[1] for r in conn.execute(
            text("PRAGMA table_info(ledger_manual_fill)")) if r[5]]
    assert pk == ["order_id"]


def test_migration_adds_the_table_to_a_pre_existing_file(tmp_path):
    """*.db is excluded from the deploy rsync, so a schema change ships as code
    and must apply itself to the file already on the VPS."""
    path = str(tmp_path / "l.db")
    engine = make_engine(path)
    # Simulate a WS-1-era file that predates this table.
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE ledger_snapshot (id INTEGER PRIMARY KEY, version INTEGER,"
            " payload TEXT, updated_at DATETIME)"))
    init_ledger_db(engine)
    with engine.connect() as conn:
        names = {r[0] for r in conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'"))}
    assert "ledger_manual_fill" in names


def test_claimed_trade_starts_null(tmp_path):
    engine = make_engine(str(tmp_path / "l.db"))
    init_ledger_db(engine)
    from sqlalchemy.orm import sessionmaker
    sm = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with sm() as s, s.begin():
        s.add(LedgerManualFill(
            order_id="o1", tradingsymbol="NIFTY25000CE", exchange="NFO",
            product="NRML", side="BUY", qty=75, avg_price=120.5,
            order_ts=datetime(2026, 7, 31, 9, 30), fill_ts=None,
            verdict="MANUAL", raw="{}", seen_at=datetime(2026, 7, 31, 9, 31)))
    with sm() as s:
        assert s.get(LedgerManualFill, "o1").claimed_trade is None
```

- [ ] **Step 2: Run it and watch it fail**

```bash
.venv/bin/python -m pytest tests/ledger/test_manual_fill_model.py -q
```

Expected: FAIL — `ImportError: cannot import name 'LedgerManualFill'`.

- [ ] **Step 3: Add the model**

Append to `backend/app/ledger/models.py`:

```python
class LedgerManualFill(LedgerBase):
    """A Kite order attributed to the owner rather than the bot.

    Persisted on FIRST SIGHT, because Kite's orderbook is same-day only: there is
    no historical order/trade API, so anything not captured before midnight is
    gone from the broker forever. `raw` keeps the whole Kite dict for forensics
    precisely because we cannot go back and ask again.

    order_id is the PK so re-polling the same order is idempotent."""

    __tablename__ = "ledger_manual_fill"

    order_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    tradingsymbol: Mapped[str] = mapped_column(String(64), nullable=False)
    exchange: Mapped[str | None] = mapped_column(String(16), nullable=True)
    product: Mapped[str | None] = mapped_column(String(16), nullable=True)
    side: Mapped[str] = mapped_column(String(8), nullable=False)      # BUY | SELL
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    order_ts: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fill_ts: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    verdict: Mapped[str] = mapped_column(String(16), nullable=False)  # MANUAL | NEEDS_REVIEW
    raw: Mapped[str] = mapped_column(Text, nullable=False)
    claimed_trade: Mapped[str | None] = mapped_column(String(64), nullable=True)
    seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
```

Add `Float` to the `sqlalchemy` import line at the top of the file.

- [ ] **Step 4: Make the migration create it on a pre-existing file**

In `backend/app/ledger/db.py`, replace the body of `migrate_ledger_db` with:

```python
def migrate_ledger_db(engine: Engine) -> None:
    """Self-applying migrations. scripts/deploy.sh excludes *.db from rsync, so a
    schema change ships as code and must apply itself on the next boot.

    create_all handles NEW tables. Anything that changes an EXISTING table needs
    an explicit ADD COLUMN here, guarded by a PRAGMA table_info check."""
    from app.ledger import models  # noqa: F401  (registers the mapped classes)

    # create_all is safe to re-run: it creates missing tables and skips present
    # ones. That is exactly what a file written by an older build needs.
    LedgerBase.metadata.create_all(engine)

    with engine.begin() as conn:
        _ = _columns(conn, "ledger_manual_fill")
```

Because `init_ledger_db` already calls `create_all` then `migrate_ledger_db`, the second `create_all` is redundant on a fresh file but is what makes `test_migration_adds_the_table_to_a_pre_existing_file` pass when `migrate_ledger_db` is called on its own.

- [ ] **Step 5: Run**

```bash
.venv/bin/python -m pytest tests/ledger -q
```

Expected: all green, including WS-1's tests.

- [ ] **Step 6: Commit** *(hold unless asked)*

```bash
git add backend/app/ledger/models.py backend/app/ledger/db.py backend/tests/ledger/test_manual_fill_model.py
git commit -m "feat(ledger): ledger_manual_fill table, idempotent on order_id"
```

---

### Task 3: Broker reads that fail closed

**Files:**
- Modify: `backend/app/providers/kite.py`
- Test: `backend/tests/ledger/test_account_orders.py`
- Verify: `.venv/bin/python -m pytest tests/ledger/test_account_orders.py -q`

**Interfaces:**
- Consumes: the existing `_Throttle` and `self.kite` on `KiteProvider`.
- Produces:
  - `KiteProvider.account_orders() -> list[dict] | None`
  - `KiteProvider.account_trades() -> list[dict] | None`
  - a new `"orders"` throttle category.

**Critical convention:** both return `None` on a read failure and never `[]`. `account_positions()` states why at `providers/kite.py:180`: *"read failed — NOT a flat account (audit C4). Callers fail closed."* An empty list here would mean "you placed no manual trades today", which is the exact false statement this feature must never make.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/ledger/test_account_orders.py`:

```python
import pytest

from app.providers.kite import KiteProvider


class _FakeKite:
    def __init__(self, orders=None, trades=None, raise_on=None):
        self._orders, self._trades, self._raise_on = orders, trades, raise_on

    def orders(self):
        if self._raise_on == "orders":
            raise RuntimeError("network")
        return self._orders

    def trades(self):
        if self._raise_on == "trades":
            raise RuntimeError("network")
        return self._trades


@pytest.fixture
def provider(monkeypatch):
    p = KiteProvider.__new__(KiteProvider)   # bypass __init__ and its network setup
    from app.providers.kite import _Throttle
    p._throttle = _Throttle()
    import app.providers.kite as mod
    p._warn = mod._WarnOnce() if hasattr(mod, "_WarnOnce") else _NullWarn()
    return p


class _NullWarn:
    def fail(self, *a, **k): pass
    def ok(self, *a, **k): pass


def test_orders_returns_the_rows(provider):
    provider.kite = _FakeKite(orders=[{"order_id": "o1", "tag": "pt-bot"}])
    got = provider.account_orders()
    assert got is not None and got[0]["order_id"] == "o1"


def test_a_failed_read_is_None_not_an_empty_list(provider):
    provider.kite = _FakeKite(raise_on="orders")
    assert provider.account_orders() is None


def test_a_genuinely_empty_orderbook_is_an_empty_list(provider):
    provider.kite = _FakeKite(orders=[])
    assert provider.account_orders() == []


def test_a_None_response_is_treated_as_a_failed_read(provider):
    provider.kite = _FakeKite(orders=None)
    assert provider.account_orders() is None


def test_trades_failure_is_also_None(provider):
    provider.kite = _FakeKite(raise_on="trades")
    assert provider.account_trades() is None
```

The `provider` fixture reaches into `KiteProvider` internals. **Read `providers/kite.py` and adapt it to the real attribute names** (`_warn`, `_throttle`) before running — the names above are from recon, and the fixture must construct whatever `account_positions()` actually touches.

- [ ] **Step 2: Run it and watch it fail**

```bash
.venv/bin/python -m pytest tests/ledger/test_account_orders.py -q
```

Expected: FAIL — `AttributeError: 'KiteProvider' object has no attribute 'account_orders'`.

- [ ] **Step 3: Add the throttle category**

In `backend/app/providers/kite.py`, extend `_MIN_INTERVAL`:

```python
# Kite documented rate limits: quote/ltp/ohlc = 1 req/s, historical = 3 req/s.
# We keep a small safety margin under each. Order/portfolio reads have no limit
# documented in this repo; 1.05s matches the default and is far under the 30s
# cadence the detection lane actually polls at.
_MIN_INTERVAL = {"quote": 1.05, "historical": 0.40, "orders": 1.05}
```

- [ ] **Step 4: Add the two reads**

Immediately after `account_positions()` in `KiteProvider`:

```python
    def account_orders(self) -> list[dict] | None:
        """Today's full orderbook, unnormalised.

        Returns None on a read failure — NOT an empty list. An empty list here
        would assert "you placed no manual trades today", which is exactly the
        false statement the manual-trade detector must never make. Same reasoning
        as account_positions (audit C4)."""
        try:
            self._throttle.wait("orders")
            rows = self.kite.orders()
        except Exception as e:
            self._warn.fail("account_orders", f"orders() failed: {e} — suppressing "
                                              f"repeats until it recovers")
            return None
        if rows is None:
            return None
        self._warn.ok("account_orders")
        return list(rows)

    def account_trades(self) -> list[dict] | None:
        """Today's fill-level tradebook. A single order can fill in tranches and
        this is the only place tranche detail lives (fill_timestamp, per-tranche
        average_price). Returns None on a read failure, never []."""
        try:
            self._throttle.wait("orders")
            rows = self.kite.trades()
        except Exception as e:
            self._warn.fail("account_trades", f"trades() failed: {e} — suppressing "
                                              f"repeats until it recovers")
            return None
        if rows is None:
            return None
        self._warn.ok("account_trades")
        return list(rows)
```

`trades` is already on the SafePaperKite route allowlist (`safe_kite.py:57-58`). **Do not modify that allowlist.**

- [ ] **Step 5: Run**

```bash
.venv/bin/python -m pytest tests/ledger/test_account_orders.py -q
```

Expected: 5 passed.

- [ ] **Step 6: Commit** *(hold unless asked)*

```bash
git add backend/app/providers/kite.py backend/tests/ledger/test_account_orders.py
git commit -m "feat(ledger): account_orders/account_trades reads that fail closed to None"
```

---

### Task 4: LIVE VERIFICATION — two unknowns, owner-run

**Files:**
- Create: `backend/scripts/probe_kite_order_fields.py`
- Verify: the owner runs it once, after connecting Kite

**Blocks:** Task 5 (fill aggregation) depends on the answer to Q1. Nothing else is blocked.

Two facts cannot be settled from the installed SDK, because `kiteconnect/connect.py` is a thin JSON pass-through that declares no response fields (`connect.py:465-499`). Both change the design if they come back the wrong way.

**Q1 — does `kite.trades()` echo the `tag` field?** `orders()` demonstrably does; production code reads it at `kite_order_client.py:206`. If `trades()` does not, tag classification must run on `orders()` and join to `trades()` by `order_id` (which is the design Task 5 assumes anyway — this only confirms it).

**Q2 — do `placed_by` / `guid` exist, and does `placed_by` differ between an API order and one placed in the Zerodha app?** If it differs, that is a **third independent signal** and would close the GTT hole properly, letting us downgrade many `NEEDS_REVIEW` verdicts to `BOT`. Worth knowing even though we do not depend on it.

- [ ] **Step 1: Write the probe**

Create `backend/scripts/probe_kite_order_fields.py`:

```python
"""Read-only probe: what fields do orders() and trades() actually return?

Prints FIELD NAMES ONLY plus a coarse type. It never prints prices, quantities,
order ids or symbols, so the output is safe to paste into a chat or a log.

Run after connecting Kite in the morning:
    cd backend && .venv/bin/python scripts/probe_kite_order_fields.py
"""
from __future__ import annotations

import sys

from app.providers.factory import get_provider


def describe(rows, label):
    if rows is None:
        print(f"{label}: READ FAILED (None) — reconnect Kite and retry")
        return
    if not rows:
        print(f"{label}: 0 rows today — retry after you have placed or seen an order")
        return
    keys = sorted({k for r in rows for k in r.keys()})
    print(f"\n{label}: {len(rows)} rows, {len(keys)} distinct fields")
    for k in keys:
        sample = next((r.get(k) for r in rows if r.get(k) is not None), None)
        print(f"   {k:<24} {type(sample).__name__}")
    for probe in ("tag", "placed_by", "guid", "meta"):
        print(f"   -> {probe!r} present: {probe in keys}")


def main() -> int:
    provider = get_provider()
    if getattr(provider, "name", None) != "kite":
        print("Not the Kite provider — nothing to probe.")
        return 1
    describe(provider.account_orders(), "orders()")
    describe(provider.account_trades(), "trades()")
    print("\nIf placed_by is present, compare its value between an order the bot")
    print("placed and one you placed in the Zerodha app. A difference would give")
    print("us a third independent bot-vs-manual signal and close the GTT hole.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Confirm it is read-only**

```bash
cd backend && grep -nE "place_order|modify|cancel|delete|POST|PUT" scripts/probe_kite_order_fields.py
```

Expected: no output. The script only calls the two read methods from Task 3.

- [ ] **Step 3: Hand it to the owner**

Tell them: connect Kite as usual, then run the command in the docstring, and paste the output. It prints no prices, no symbols and no order ids.

- [ ] **Step 4: Record the answer**

Write the result into this plan file under this task as `**ANSWERED <date>:**` so later tasks do not have to re-ask. If `trades()` does **not** echo `tag`, note that Task 5 must join on `order_id` — which it already does, so no redesign follows.

- [ ] **Step 5: Commit** *(hold unless asked)*

```bash
git add backend/scripts/probe_kite_order_fields.py
git commit -m "chore(ledger): read-only probe for Kite order/trade response fields"
```

---

### Task 5: Round-trip pairing

**Files:**
- Create: `backend/app/ledger/roundtrip.py`
- Test: `backend/tests/ledger/test_roundtrip.py`
- Verify: `.venv/bin/python -m pytest tests/ledger/test_roundtrip.py -q`

**Interfaces:**
- Consumes: raw `trades()` rows (dicts).
- Produces:
  - `aggregate_fills(trade_rows: list[dict]) -> dict[str, dict]` — keyed by `order_id`, each with `qty`, `avg_price`, `first_fill_ts`, `last_fill_ts`.
  - `pair_round_trips(orders: list[dict]) -> list[dict]` — each with `symbol`, `entry`, `exit` (exit may be `None`), `qty`.

**This is the largest risk in WS-2.** A single manual order can fill in tranches, and a position can be opened and closed by separate orders. Getting this wrong produces journal entries with wrong prices, which is worse than no entry at all.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/ledger/test_roundtrip.py`:

```python
from datetime import datetime

from app.ledger.roundtrip import aggregate_fills, pair_round_trips


def t(order_id, qty, price, ts, symbol="NIFTY25000CE"):
    return {"order_id": order_id, "tradingsymbol": symbol, "quantity": qty,
            "average_price": price, "fill_timestamp": ts}


def o(order_id, side, qty, price, ts, symbol="NIFTY25000CE"):
    return {"order_id": order_id, "tradingsymbol": symbol, "transaction_type": side,
            "qty": qty, "avg_price": price, "order_ts": ts}


class TestAggregateFills:
    def test_a_single_fill_passes_through(self):
        got = aggregate_fills([t("o1", 75, 120.0, datetime(2026, 7, 31, 9, 30))])
        assert got["o1"]["qty"] == 75
        assert got["o1"]["avg_price"] == 120.0

    def test_tranches_are_quantity_weighted_not_arithmetic(self):
        # 50 @ 100 and 25 @ 130 is 110.0 weighted, but 115.0 if you average the
        # prices. Getting this wrong misprices every partially-filled order.
        got = aggregate_fills([
            t("o1", 50, 100.0, datetime(2026, 7, 31, 9, 30)),
            t("o1", 25, 130.0, datetime(2026, 7, 31, 9, 31)),
        ])
        assert got["o1"]["qty"] == 75
        assert got["o1"]["avg_price"] == 110.0

    def test_first_and_last_fill_timestamps_are_kept(self):
        a, b = datetime(2026, 7, 31, 9, 30), datetime(2026, 7, 31, 9, 35)
        got = aggregate_fills([t("o1", 50, 100.0, b), t("o1", 25, 100.0, a)])
        assert got["o1"]["first_fill_ts"] == a
        assert got["o1"]["last_fill_ts"] == b

    def test_separate_orders_stay_separate(self):
        got = aggregate_fills([
            t("o1", 75, 100.0, datetime(2026, 7, 31, 9, 30)),
            t("o2", 75, 200.0, datetime(2026, 7, 31, 9, 40)),
        ])
        assert set(got) == {"o1", "o2"}

    def test_zero_quantity_rows_do_not_divide_by_zero(self):
        got = aggregate_fills([t("o1", 0, 0.0, datetime(2026, 7, 31, 9, 30))])
        assert got["o1"]["avg_price"] is None


class TestPairRoundTrips:
    def test_buy_then_sell_is_one_closed_round_trip(self):
        rt = pair_round_trips([
            o("o1", "BUY", 75, 100.0, datetime(2026, 7, 31, 9, 30)),
            o("o2", "SELL", 75, 130.0, datetime(2026, 7, 31, 10, 0)),
        ])
        assert len(rt) == 1
        assert rt[0]["entry"]["order_id"] == "o1"
        assert rt[0]["exit"]["order_id"] == "o2"
        assert rt[0]["qty"] == 75

    def test_an_unclosed_buy_is_an_open_round_trip(self):
        rt = pair_round_trips([o("o1", "BUY", 75, 100.0, datetime(2026, 7, 31, 9, 30))])
        assert len(rt) == 1 and rt[0]["exit"] is None

    def test_a_sell_first_short_is_an_entry_not_an_orphan_exit(self):
        rt = pair_round_trips([
            o("o1", "SELL", 75, 130.0, datetime(2026, 7, 31, 9, 30)),
            o("o2", "BUY", 75, 100.0, datetime(2026, 7, 31, 10, 0)),
        ])
        assert len(rt) == 1
        assert rt[0]["entry"]["order_id"] == "o1"
        assert rt[0]["exit"]["order_id"] == "o2"

    def test_a_partial_exit_leaves_the_remainder_open(self):
        rt = pair_round_trips([
            o("o1", "BUY", 75, 100.0, datetime(2026, 7, 31, 9, 30)),
            o("o2", "SELL", 50, 130.0, datetime(2026, 7, 31, 10, 0)),
        ])
        closed = [r for r in rt if r["exit"] is not None]
        open_ = [r for r in rt if r["exit"] is None]
        assert len(closed) == 1 and closed[0]["qty"] == 50
        assert len(open_) == 1 and open_[0]["qty"] == 25

    def test_different_symbols_never_pair_with_each_other(self):
        rt = pair_round_trips([
            o("o1", "BUY", 75, 100.0, datetime(2026, 7, 31, 9, 30), symbol="A"),
            o("o2", "SELL", 75, 130.0, datetime(2026, 7, 31, 10, 0), symbol="B"),
        ])
        assert all(r["exit"] is None for r in rt)
        assert len(rt) == 2

    def test_pairing_is_fifo_in_time_order(self):
        rt = pair_round_trips([
            o("o1", "BUY", 75, 100.0, datetime(2026, 7, 31, 9, 30)),
            o("o2", "BUY", 75, 110.0, datetime(2026, 7, 31, 9, 45)),
            o("o3", "SELL", 75, 130.0, datetime(2026, 7, 31, 10, 0)),
        ])
        closed = [r for r in rt if r["exit"] is not None]
        assert len(closed) == 1
        assert closed[0]["entry"]["order_id"] == "o1"   # oldest closes first

    def test_input_order_does_not_matter(self):
        rows = [
            o("o3", "SELL", 75, 130.0, datetime(2026, 7, 31, 10, 0)),
            o("o1", "BUY", 75, 100.0, datetime(2026, 7, 31, 9, 30)),
        ]
        rt = pair_round_trips(rows)
        assert len(rt) == 1 and rt[0]["entry"]["order_id"] == "o1"
```

- [ ] **Step 2: Run it and watch it fail**

```bash
.venv/bin/python -m pytest tests/ledger/test_roundtrip.py -q
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

```python
"""Turning a Kite orderbook into journal-shaped round trips.

Two separate problems, deliberately separate functions:

  1. One ORDER can fill in several TRANCHES. kite.trades() is the only place
     tranche detail lives. Aggregating them needs a QUANTITY-WEIGHTED mean —
     averaging the prices misprices every partial fill.

  2. One POSITION is opened by one order and closed by another. Pairing them is
     FIFO within a symbol, which matches how a discretionary trader thinks about
     "the trade I took at 09:30".

A short is a SELL that opens, so direction is decided by which side comes FIRST
for a symbol, never by the side itself.
"""
from __future__ import annotations

from collections import defaultdict


def aggregate_fills(trade_rows: list[dict]) -> dict[str, dict]:
    """Group fill-level rows by order_id into one weighted average each."""
    by_order: dict[str, list[dict]] = defaultdict(list)
    for r in trade_rows or []:
        oid = r.get("order_id")
        if oid is not None:
            by_order[str(oid)].append(r)

    out: dict[str, dict] = {}
    for oid, rows in by_order.items():
        qty = sum(int(r.get("quantity", 0) or 0) for r in rows)
        notional = sum(
            int(r.get("quantity", 0) or 0) * float(r.get("average_price", 0.0) or 0.0)
            for r in rows
        )
        stamps = [r.get("fill_timestamp") for r in rows if r.get("fill_timestamp")]
        out[oid] = {
            "order_id": oid,
            "tradingsymbol": rows[0].get("tradingsymbol"),
            "qty": qty,
            # A zero-quantity order has no meaningful price. Say None rather
            # than 0.0, which would look like a real fill at zero.
            "avg_price": (notional / qty) if qty else None,
            "first_fill_ts": min(stamps) if stamps else None,
            "last_fill_ts": max(stamps) if stamps else None,
        }
    return out


def pair_round_trips(orders: list[dict]) -> list[dict]:
    """Pair opening and closing orders per symbol, FIFO by time.

    Each order dict needs: order_id, tradingsymbol, transaction_type, qty,
    avg_price, order_ts. Returns round trips with `exit` None while still open.
    """
    by_symbol: dict[str, list[dict]] = defaultdict(list)
    for o in orders or []:
        sym = (o.get("tradingsymbol") or "").strip().upper()
        if sym:
            by_symbol[sym].append(o)

    result: list[dict] = []
    for sym, rows in by_symbol.items():
        rows = sorted(rows, key=lambda r: (r.get("order_ts") or 0))
        # Open lots waiting to be closed, oldest first. `side` is the side that
        # OPENED them, so the closing side is its opposite.
        open_lots: list[dict] = []
        for o in rows:
            side = (o.get("transaction_type") or "").strip().upper()
            qty = int(o.get("qty", 0) or 0)
            if qty <= 0:
                continue
            closing = [l for l in open_lots if l["side"] != side]
            if not closing:
                open_lots.append({"side": side, "qty": qty, "order": o})
                continue
            remaining = qty
            while remaining > 0 and closing:
                lot = closing[0]
                take = min(remaining, lot["qty"])
                result.append({"symbol": sym, "entry": lot["order"], "exit": o,
                               "qty": take})
                lot["qty"] -= take
                remaining -= take
                if lot["qty"] == 0:
                    open_lots.remove(lot)
                    closing.pop(0)
            if remaining > 0:
                # Closed more than was open — this order flips the position.
                open_lots.append({"side": side, "qty": remaining, "order": o})

        for lot in open_lots:
            result.append({"symbol": sym, "entry": lot["order"], "exit": None,
                           "qty": lot["qty"]})
    return result
```

- [ ] **Step 4: Run and iterate until green**

```bash
.venv/bin/python -m pytest tests/ledger/test_roundtrip.py -q
```

Expected: 13 passed. If `test_pairing_is_fifo_in_time_order` fails, the sort key is wrong — check that `order_ts` is a `datetime` and not a string.

- [ ] **Step 5: Commit** *(hold unless asked)*

```bash
git add backend/app/ledger/roundtrip.py backend/tests/ledger/test_roundtrip.py
git commit -m "feat(ledger): tranche aggregation (qty-weighted) and FIFO round-trip pairing"
```

---

### Task 6: Detection orchestration

**Files:**
- Create: `backend/app/ledger/detect.py`
- Modify: `backend/app/ledger/service.py`
- Test: `backend/tests/ledger/test_detect.py`
- Verify: `.venv/bin/python -m pytest tests/ledger -q`

**Interfaces:**
- Consumes: `classify_order` (Task 1), `LedgerManualFill` (Task 2), `account_orders`/`account_trades` (Task 3), `aggregate_fills` (Task 5).
- Produces:
  - `bot_order_ids(exec_session) -> set[str]`
  - `bot_symbols_today(exec_session, today) -> set[str]`
  - `detect_manual_fills(provider, exec_session, ledger_sm, now) -> int` (rows persisted)
  - `service.upsert_manual_fills(sm, rows) -> int`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/ledger/test_detect.py`:

```python
from datetime import datetime

from sqlalchemy.orm import sessionmaker

from app.ledger.db import init_ledger_db, make_engine
from app.ledger.detect import detect_manual_fills
from app.ledger.models import LedgerManualFill


class _Provider:
    name = "kite"
    def __init__(self, orders, trades=None):
        self._o, self._t = orders, trades or []
    def account_orders(self): return self._o
    def account_trades(self): return self._t


def _sm(tmp_path):
    engine = make_engine(str(tmp_path / "l.db"))
    init_ledger_db(engine)
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


def order(**kw):
    base = {"order_id": "o1", "tag": None, "tradingsymbol": "NIFTY25000CE",
            "status": "COMPLETE", "transaction_type": "BUY", "filled_quantity": 75,
            "average_price": 120.5, "product": "NRML", "exchange": "NFO",
            "order_timestamp": datetime(2026, 7, 31, 9, 30)}
    base.update(kw)
    return base


NOW = datetime(2026, 7, 31, 9, 31)


def test_a_manual_order_is_persisted(tmp_path):
    sm = _sm(tmp_path)
    n = detect_manual_fills(_Provider([order()]), None, sm, NOW,
                            bot_ids=set(), bot_symbols=set())
    assert n == 1
    with sm() as s:
        assert s.get(LedgerManualFill, "o1").verdict == "MANUAL"


def test_a_bot_order_is_not_persisted(tmp_path):
    sm = _sm(tmp_path)
    n = detect_manual_fills(_Provider([order(tag="pt-bot")]), None, sm, NOW,
                            bot_ids=set(), bot_symbols=set())
    assert n == 0
    with sm() as s:
        assert s.get(LedgerManualFill, "o1") is None


def test_needs_review_is_persisted_and_labelled(tmp_path):
    sm = _sm(tmp_path)
    detect_manual_fills(_Provider([order(tradingsymbol="RELIANCE")]), None, sm, NOW,
                        bot_ids=set(), bot_symbols={"RELIANCE"})
    with sm() as s:
        assert s.get(LedgerManualFill, "o1").verdict == "NEEDS_REVIEW"


def test_repolling_the_same_order_does_not_duplicate(tmp_path):
    sm = _sm(tmp_path)
    p = _Provider([order()])
    detect_manual_fills(p, None, sm, NOW, bot_ids=set(), bot_symbols=set())
    detect_manual_fills(p, None, sm, NOW, bot_ids=set(), bot_symbols=set())
    with sm() as s:
        assert s.query(LedgerManualFill).count() == 1


def test_a_claimed_row_is_never_overwritten_by_a_repoll(tmp_path):
    sm = _sm(tmp_path)
    p = _Provider([order()])
    detect_manual_fills(p, None, sm, NOW, bot_ids=set(), bot_symbols=set())
    with sm() as s, s.begin():
        s.get(LedgerManualFill, "o1").claimed_trade = "tr_1"
    detect_manual_fills(p, None, sm, NOW, bot_ids=set(), bot_symbols=set())
    with sm() as s:
        assert s.get(LedgerManualFill, "o1").claimed_trade == "tr_1"


def test_a_failed_read_persists_nothing_and_does_not_raise(tmp_path):
    sm = _sm(tmp_path)
    assert detect_manual_fills(_Provider(None), None, sm, NOW,
                               bot_ids=set(), bot_symbols=set()) == 0
    with sm() as s:
        assert s.query(LedgerManualFill).count() == 0


def test_unfilled_orders_are_ignored(tmp_path):
    sm = _sm(tmp_path)
    n = detect_manual_fills(
        _Provider([order(status="CANCELLED", filled_quantity=0)]), None, sm, NOW,
        bot_ids=set(), bot_symbols=set())
    assert n == 0


def test_the_whole_kite_dict_is_kept_for_forensics(tmp_path):
    sm = _sm(tmp_path)
    detect_manual_fills(_Provider([order()]), None, sm, NOW,
                        bot_ids=set(), bot_symbols=set())
    with sm() as s:
        assert "NIFTY25000CE" in s.get(LedgerManualFill, "o1").raw
```

- [ ] **Step 2: Run it and watch it fail**

```bash
.venv/bin/python -m pytest tests/ledger/test_detect.py -q
```

- [ ] **Step 3: Implement `detect.py`**

```python
"""Read the live orderbook, attribute each order, persist the owner's.

READ-AND-RECORD ONLY. This module must never write `positions` or `trades`, and
must never influence can_bot_close(). It reads the execution DB only to learn
which order_ids and symbols belong to the bot.

Kite's orderbook is same-day only, so anything seen here must be persisted
immediately — there is no way to ask again tomorrow.
"""
from __future__ import annotations

import json
from datetime import date, datetime

from sqlalchemy import select

from app.ledger.classify import BOT, classify_order
from app.ledger.models import LedgerManualFill

_FILLED = {"COMPLETE"}


def bot_order_ids(exec_session) -> set[str]:
    """order_ids the bot placed, from the local order_journal. NULLs are dropped:
    a crash between _journal_open and the placement ack leaves order_id NULL, and
    a None in this set must never match a real order."""
    from app.db.models import OrderJournal
    rows = exec_session.scalars(select(OrderJournal.order_id)).all()
    return {str(r) for r in rows if r is not None}


def bot_symbols_today(exec_session, today: date) -> set[str]:
    """Symbols the bot placed or held today. Used only to force NEEDS_REVIEW on
    untagged orders — the GTT hole. See classify.py for why."""
    from app.db.models import OrderJournal, Position
    syms: set[str] = set()
    for r in exec_session.scalars(select(OrderJournal.tradingsymbol)).all():
        if r:
            syms.add(str(r).strip().upper())
    for r in exec_session.scalars(select(Position.tradingsymbol)).all():
        if r:
            syms.add(str(r).strip().upper())
    return syms


def _is_filled(o: dict) -> bool:
    return (str(o.get("status", "")).upper() in _FILLED
            and int(o.get("filled_quantity", 0) or 0) > 0)


def detect_manual_fills(provider, exec_session, ledger_sm, now: datetime,
                        bot_ids: set[str] | None = None,
                        bot_symbols: set[str] | None = None) -> int:
    """Poll once. Returns the number of rows written. Never raises."""
    orders = provider.account_orders()
    if orders is None:
        # A failed read is NOT an empty orderbook. Persist nothing and say so by
        # writing nothing, rather than recording "no manual trades today".
        return 0

    if bot_ids is None:
        bot_ids = bot_order_ids(exec_session) if exec_session is not None else set()
    if bot_symbols is None:
        bot_symbols = (bot_symbols_today(exec_session, now.date())
                       if exec_session is not None else set())

    keep: list[dict] = []
    for o in orders:
        if not _is_filled(o):
            continue
        verdict = classify_order(o, bot_ids, bot_symbols)
        if verdict == BOT:
            continue
        keep.append({"order": o, "verdict": verdict})

    if not keep:
        return 0
    return _upsert(ledger_sm, keep, now)


def _upsert(sm, rows: list[dict], now: datetime) -> int:
    written = 0
    with sm() as s, s.begin():
        for item in rows:
            o, verdict = item["order"], item["verdict"]
            oid = str(o.get("order_id"))
            existing = s.get(LedgerManualFill, oid)
            if existing is not None:
                # Never clobber a row the owner has already reasoned about.
                if existing.claimed_trade:
                    continue
                existing.verdict = verdict
                existing.avg_price = float(o.get("average_price") or 0.0) or None
                existing.qty = int(o.get("filled_quantity", 0) or 0)
                continue
            s.add(LedgerManualFill(
                order_id=oid,
                tradingsymbol=str(o.get("tradingsymbol") or ""),
                exchange=o.get("exchange"),
                product=o.get("product"),
                side=str(o.get("transaction_type") or "").upper(),
                qty=int(o.get("filled_quantity", 0) or 0),
                avg_price=float(o.get("average_price") or 0.0) or None,
                order_ts=o.get("order_timestamp"),
                fill_ts=o.get("exchange_timestamp"),
                verdict=verdict,
                raw=json.dumps(o, default=str),
                seen_at=now,
            ))
            written += 1
    return written
```

- [ ] **Step 4: Run and iterate**

```bash
.venv/bin/python -m pytest tests/ledger/test_detect.py -q
```

Expected: 8 passed.

- [ ] **Step 5: Commit** *(hold unless asked)*

```bash
git add backend/app/ledger/detect.py backend/tests/ledger/test_detect.py
git commit -m "feat(ledger): detection orchestration — read, classify, persist on first sight"
```

---

### Task 7: The polling lane

**Files:**
- Create: `backend/app/ledger/lane.py`
- Modify: `backend/app/engine/runner.py`, `backend/app/core/config.py`
- Test: `backend/tests/ledger/test_lane.py`
- Verify: `.venv/bin/python -m pytest tests/ledger -q` and `scripts/dryrun.py 700`

**Interfaces:**
- Consumes: `detect_manual_fills` (Task 6).
- Produces: `async def run_manual_detect_loop(provider, exec_sessionmaker, ledger_sm, settings, clock) -> None`.

**Two rules this task exists to honour:**
1. **Never take `runner._lock`.** The 2026-07-13 `risk_loop_stalled` incident was a sweep holding it 30s. This lane touches a different database.
2. **Run near session close.** Kite's orderbook is same-day only; a lane that dies at 14:00 loses the whole afternoon permanently.

- [ ] **Step 1: Add the settings knobs**

In `backend/app/core/config.py`, add to `Settings`:

```python
    manual_detect_enabled: bool = True
    manual_detect_seconds: float = 30.0
```

Register both in `runtime_config.OVERRIDABLE` **and** add `META` entries in `SettingsView.tsx`, or they join the twelve knobs that already render nowhere. Labels:

- `manual_detect_enabled` — "Detect my manual Kite trades" — *"Poll the Kite orderbook and journal any trade you placed yourself. Read-only: it never places or cancels an order."*
- `manual_detect_seconds` — "Manual-trade poll (sec)" — *"How often to check for your own trades. Recommended 30 — matches the proven positions() cadence."*

- [ ] **Step 2: Write the failing test**

Create `backend/tests/ledger/test_lane.py`:

```python
import asyncio
from datetime import datetime

import pytest

from app.ledger.lane import should_run_now


def test_runs_on_the_normal_cadence():
    last = datetime(2026, 7, 31, 10, 0, 0)
    assert should_run_now(datetime(2026, 7, 31, 10, 0, 31), last, 30.0) is True


def test_does_not_run_before_the_interval_elapses():
    last = datetime(2026, 7, 31, 10, 0, 0)
    assert should_run_now(datetime(2026, 7, 31, 10, 0, 10), last, 30.0) is False


def test_runs_when_it_has_never_run():
    assert should_run_now(datetime(2026, 7, 31, 10, 0, 0), None, 30.0) is True


@pytest.mark.asyncio
async def test_the_loop_survives_a_detector_exception():
    """A throw inside the detector must never kill the lane — Kite's orderbook is
    same-day only, so a dead lane loses the rest of the day permanently."""
    from app.ledger.lane import _tick_guarded
    calls = []

    def boom():
        calls.append(1)
        raise RuntimeError("kite down")

    await _tick_guarded(boom)
    assert calls == [1]   # returned normally despite the raise
```

If `pytest-asyncio` is not installed, drop the `@pytest.mark.asyncio` test and call `asyncio.run(_tick_guarded(boom))` from a sync test instead. Check `backend/requirements.txt` first.

- [ ] **Step 3: Implement the lane**

```python
"""The manual-trade detection lane.

Deliberately NOT part of the engine's two cooperative loops, and it never takes
runner._lock. The 2026-07-13 risk_loop_stalled incident was a sweep holding that
lock for 30s; this lane touches an entirely different database and genuinely does
not need it.

It also forces a run near session close, because Kite's orderbook is same-day
only: whatever this lane has not seen by midnight is gone from the broker
forever."""
from __future__ import annotations

import asyncio
from datetime import datetime, time

from app.core.logging import log

# Force a sweep in this window regardless of cadence, so a late start or a
# restart at 15:20 still captures the day.
_CLOSE_SWEEP_START = time(15, 25)
_CLOSE_SWEEP_END = time(15, 45)


def should_run_now(now: datetime, last_run: datetime | None, interval: float) -> bool:
    if last_run is None:
        return True
    if _CLOSE_SWEEP_START <= now.time() <= _CLOSE_SWEEP_END:
        # Within the close window, run at least once a minute.
        return (now - last_run).total_seconds() >= 60
    return (now - last_run).total_seconds() >= interval


async def _tick_guarded(fn) -> None:
    """Run one detection tick, swallowing everything. A raise here must never
    kill the lane."""
    try:
        await asyncio.to_thread(fn)
    except Exception as e:
        log.warning(f"manual-detect tick failed: {e}")


async def run_manual_detect_loop(provider, exec_sessionmaker, ledger_sm,
                                 settings, clock) -> None:
    if getattr(provider, "name", None) != "kite":
        log.info("manual-detect: provider is not kite — lane disabled")
        return
    if not getattr(settings, "manual_detect_enabled", True):
        log.info("manual-detect: disabled by settings")
        return

    from app.ledger.detect import detect_manual_fills

    last: datetime | None = None
    log.info("manual-detect: lane started")
    while True:
        now = clock()
        interval = float(getattr(settings, "manual_detect_seconds", 30.0))
        if should_run_now(now, last, interval):
            last = now

            def tick():
                with exec_sessionmaker() as exec_s:
                    n = detect_manual_fills(provider, exec_s, ledger_sm, now)
                if n:
                    log.info(f"manual-detect: {n} new manual fill(s) awaiting a reason")

            await _tick_guarded(tick)
        await asyncio.sleep(5)
```

- [ ] **Step 4: Start it from the runner**

In `backend/app/engine/runner.py`, wherever the two existing loops are launched as tasks, add the lane as a third — **without** acquiring `self._lock` anywhere in its path:

```python
        # Manual-trade detection. A separate lane on purpose: it reads the Kite
        # orderbook and writes only to the ledger DB, never to positions/trades,
        # and it never takes self._lock (see the 2026-07-13 risk_loop_stalled
        # incident). If it dies, trading is unaffected.
        from app.ledger.db import get_sessionmaker as _ledger_sm
        from app.ledger.lane import run_manual_detect_loop
        from app.db.session import SessionLocal
        tasks.append(asyncio.create_task(run_manual_detect_loop(
            self.provider, SessionLocal, _ledger_sm(), get_settings(),
            lambda: self.provider.now())))
```

Match the real local names in `runner.py` for the task list and settings accessor. **This is the only edit to an engine file in WS-2, and it only schedules a task.**

- [ ] **Step 5: Verify the mock provider path no-ops**

```bash
.venv/bin/python -m pytest -q --tb=short > /tmp/ws2-t7.log 2>&1; tail -3 /tmp/ws2-t7.log
.venv/bin/python scripts/dryrun.py 700
```

Expected: suite green, `LEDGER OK ✓`. The lane returns immediately under the mock provider, so neither is affected.

- [ ] **Step 6: Commit** *(hold unless asked)*

```bash
git add backend/app/ledger/lane.py backend/tests/ledger/test_lane.py backend/app/engine/runner.py backend/app/core/config.py
git commit -m "feat(ledger): manual-detect polling lane with a forced session-close sweep"
```

---

### Task 8: REST + Inbox reason capture

**Files:**
- Modify: `backend/app/ledger/service.py`, `backend/app/ledger/routes.py`
- Create: `frontend/src/ledger/data/manualFills.ts`
- Modify: `frontend/src/ledger/surfaces/Misc.tsx` (the Inbox surface)
- Test: `backend/tests/ledger/test_manual_fill_routes.py`
- Verify: `pytest tests/ledger -q`, `npm run typecheck`

**Interfaces:**
- Produces:
  - `GET /api/ledger/manual-fills?unclaimed=true` → `{ fills: [...] }`
  - `POST /api/ledger/manual-fills/{order_id}/claim` body `{ trade_id }` → `{ ok, order_id, trade_id }`
  - `listManualFills(unclaimed?: boolean): Promise<ManualFill[]>`
  - `claimManualFill(orderId: string, tradeId: string): Promise<void>`

**The materialisation rule:** claiming a fill creates the journal trade through the **existing `addTrade()`**, not by writing a `Trade` directly. That is what keeps every rule firing — off-book attribution, no-thesis auto-tagging, regime inheritance, risk-envelope breach. Bypassing `addTrade` would produce records the rest of the journal cannot reason about.

- [ ] **Step 1: Write the failing backend test**

Create `backend/tests/ledger/test_manual_fill_routes.py` using the same `client` fixture as WS-1's `test_routes.py` (copy it), then:

```python
def _seed(client, order_id="o1", verdict="MANUAL"):
    from datetime import datetime
    from app.ledger.db import get_sessionmaker
    from app.ledger.models import LedgerManualFill
    sm = get_sessionmaker()
    with sm() as s, s.begin():
        s.add(LedgerManualFill(
            order_id=order_id, tradingsymbol="NIFTY25000CE", exchange="NFO",
            product="NRML", side="BUY", qty=65, avg_price=120.5,
            order_ts=datetime(2026, 7, 31, 9, 30), fill_ts=None,
            verdict=verdict, raw="{}", seen_at=datetime(2026, 7, 31, 9, 31)))


def test_lists_unclaimed_fills(client):
    _seed(client)
    r = client.get("/api/ledger/manual-fills?unclaimed=true")
    assert r.status_code == 200
    assert [f["order_id"] for f in r.json()["fills"]] == ["o1"]


def test_claiming_records_the_trade_id(client):
    _seed(client)
    r = client.post("/api/ledger/manual-fills/o1/claim", json={"trade_id": "tr_1"})
    assert r.status_code == 200
    assert client.get("/api/ledger/manual-fills?unclaimed=true").json()["fills"] == []


def test_claiming_twice_is_a_conflict_not_a_silent_overwrite(client):
    _seed(client)
    client.post("/api/ledger/manual-fills/o1/claim", json={"trade_id": "tr_1"})
    r = client.post("/api/ledger/manual-fills/o1/claim", json={"trade_id": "tr_2"})
    assert r.status_code == 409


def test_claiming_an_unknown_order_is_404(client):
    r = client.post("/api/ledger/manual-fills/nope/claim", json={"trade_id": "t"})
    assert r.status_code == 404


def test_needs_review_rows_are_listed_and_flagged(client):
    _seed(client, verdict="NEEDS_REVIEW")
    f = client.get("/api/ledger/manual-fills?unclaimed=true").json()["fills"][0]
    assert f["verdict"] == "NEEDS_REVIEW"
```

- [ ] **Step 2: Run it, watch it fail, then implement the service functions**

Append to `backend/app/ledger/service.py`:

```python
def list_manual_fills(sm, unclaimed: bool = True) -> list[dict]:
    from app.ledger.models import LedgerManualFill
    with sm() as s:
        q = select(LedgerManualFill)
        if unclaimed:
            q = q.where(LedgerManualFill.claimed_trade.is_(None))
        return [{
            "order_id": r.order_id, "tradingsymbol": r.tradingsymbol,
            "exchange": r.exchange, "product": r.product, "side": r.side,
            "qty": r.qty, "avg_price": r.avg_price,
            "order_ts": r.order_ts.isoformat() if r.order_ts else None,
            "verdict": r.verdict, "claimed_trade": r.claimed_trade,
        } for r in s.scalars(q.order_by(LedgerManualFill.order_ts))]


class AlreadyClaimed(Exception):
    pass


def claim_manual_fill(sm, order_id: str, trade_id: str) -> bool:
    """Returns False if there is no such fill. Raises AlreadyClaimed if it has
    already been reasoned about — never silently reassign."""
    from app.ledger.models import LedgerManualFill
    with sm() as s, s.begin():
        row = s.get(LedgerManualFill, order_id)
        if row is None:
            return False
        if row.claimed_trade:
            raise AlreadyClaimed(row.claimed_trade)
        row.claimed_trade = trade_id
        return True
```

And the routes:

```python
class ClaimRequest(BaseModel):
    trade_id: str


@router.get("/manual-fills")
def get_manual_fills(unclaimed: bool = True):
    return {"fills": service.list_manual_fills(get_sessionmaker(), unclaimed)}


@router.post("/manual-fills/{order_id}/claim")
def claim(order_id: str, req: ClaimRequest):
    try:
        found = service.claim_manual_fill(get_sessionmaker(), order_id, req.trade_id)
    except service.AlreadyClaimed as exc:
        return JSONResponse(status_code=409,
                            content={"detail": "already claimed",
                                     "trade_id": str(exc.args[0])})
    if not found:
        raise HTTPException(status_code=404, detail="no such fill")
    return {"ok": True, "order_id": order_id, "trade_id": req.trade_id}
```

- [ ] **Step 3: Add the frontend client**

Create `frontend/src/ledger/data/manualFills.ts`:

```ts
/** Kite fills attributed to the owner rather than the bot, awaiting a reason. */
export interface ManualFill {
  order_id: string
  tradingsymbol: string
  exchange: string | null
  product: string | null
  side: 'BUY' | 'SELL'
  qty: number
  avg_price: number | null
  order_ts: string | null
  verdict: 'MANUAL' | 'NEEDS_REVIEW'
  claimed_trade: string | null
}

function authHeaders(): Record<string, string> {
  const token = import.meta.env.VITE_PT_TOKEN
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export async function listManualFills(unclaimed = true): Promise<ManualFill[]> {
  const res = await fetch(`/api/ledger/manual-fills?unclaimed=${unclaimed}`,
                          { headers: authHeaders() })
  if (!res.ok) return []
  return (await res.json()).fills as ManualFill[]
}

export async function claimManualFill(orderId: string, tradeId: string): Promise<void> {
  const res = await fetch(`/api/ledger/manual-fills/${encodeURIComponent(orderId)}/claim`, {
    method: 'POST',
    headers: { 'content-type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ trade_id: tradeId }),
  })
  if (!res.ok) throw new Error(`claim failed: ${res.status}`)
}
```

- [ ] **Step 4: Extend the Inbox surface**

In `frontend/src/ledger/surfaces/Misc.tsx`, the `Inbox` surface currently triages stream events. Add a section above it, "Trades awaiting a reason", that:

1. calls `listManualFills()` on mount and every 60s;
2. renders one row per fill: symbol, side glyph (▲ BUY / ▼ SELL), qty, price, time — **all Fact-layer, all read-only, never editable**;
3. shows a `NEEDS_REVIEW` row with an amber marker and the honest label *"might be a bot stop — confirm this was yours"* (amber already means exactly "unresolved / breached / invalidated" in this design system);
4. on "This was mine", calls the existing `addTrade()` with the broker's price/qty/time pre-filled and the owner's setup and reason, then calls `claimManualFill(order_id, newTradeId)`;
5. on "Not mine", calls `claimManualFill(order_id, 'not-mine')` so it stops appearing.

Read `actions.ts` for `addTrade`'s real signature before writing the call.

- [ ] **Step 5: Verify**

```bash
cd backend && .venv/bin/python -m pytest tests/ledger -q
cd ../frontend && npm run typecheck && npx vitest run
```

- [ ] **Step 6: Commit** *(hold unless asked)*

```bash
git add backend/app/ledger frontend/src/ledger backend/tests/ledger
git commit -m "feat(ledger): manual-fill REST + Inbox reason capture through addTrade()"
```

---

### Task 9: The mobile capture shell

**Files:**
- Create: `frontend/src/ledger/mobile/MobileLedger.tsx`, `Pending.tsx`, `Capture.tsx`, `Today.tsx`, `TimelineRO.tsx`, `mobile.css`
- Modify: `frontend/src/views/LedgerView.tsx`
- Verify: `npm run typecheck`, `npm run build`, device check

**Interfaces:**
- Consumes: `listManualFills`/`claimManualFill` (Task 8), `addTrade`/`observe`/`appendToSession` from `actions.ts`, `useStore` from `hooks.ts`.
- Produces: `<MobileLedger />`, rendered below 768px.

**Why a separate shell, not responsive surfaces.** THE LEDGER has one `@media` rule in 19,000 lines and it is `prefers-reduced-motion`. Its shell consumes 264px of chrome before content; its data grid has a 676px minimum with mouse-drag column resize. Making all 12 surfaces mobile is 5–7 weeks and yields a second design. The owner chose capture-first, which is also §10.4 of the source design doc.

- [ ] **Step 1: Build the shell**

Create `frontend/src/ledger/mobile/MobileLedger.tsx`:

```tsx
import { useState } from 'react'
import Pending from './Pending'
import Capture from './Capture'
import Today from './Today'
import TimelineRO from './TimelineRO'
import './mobile.css'

type Screen = 'pending' | 'capture' | 'today' | 'timeline'

/**
 * The phone journal: capture only.
 *
 * You place discretionary trades from the Zerodha app, so the reason prompt has
 * to be answerable with a thumb. Analysis does not — the blotter, the research
 * bench and the year heatmap are desktop surfaces and say so rather than
 * degrading into something unreadable.
 */
export default function MobileLedger() {
  const [screen, setScreen] = useState<Screen>('pending')
  return (
    <div className="ml">
      <div className="ml__body">
        {screen === 'pending' && <Pending />}
        {screen === 'capture' && <Capture />}
        {screen === 'today' && <Today />}
        {screen === 'timeline' && <TimelineRO />}
      </div>
      <nav className="ml__tabs">
        {(['pending', 'capture', 'today', 'timeline'] as Screen[]).map((s) => (
          <button key={s} className={s === screen ? 'is-active' : ''}
                  onClick={() => setScreen(s)}>{s}</button>
        ))}
      </nav>
    </div>
  )
}
```

Create `mobile.css` with a bottom tab bar, 44px minimum tap targets, and `env(safe-area-inset-bottom)` padding:

```css
.ml { display: flex; flex-direction: column; height: 100%; }
.ml__body { flex: 1; overflow-y: auto; -webkit-overflow-scrolling: touch; padding: var(--s-4); }
.ml__tabs {
  display: grid; grid-template-columns: repeat(4, 1fr);
  border-top: 1px solid var(--border);
  padding-bottom: env(safe-area-inset-bottom, 0);
}
.ml__tabs button {
  min-height: 44px; background: none; border: 0; color: var(--text-faint);
  font: inherit; text-transform: capitalize;
}
.ml__tabs button.is-active { color: var(--interactive); }
```

- [ ] **Step 2: `Pending` — the screen that matters**

One card per unclaimed fill. Broker facts read-only at the top; below them, a single text field "Why did you take this?" and a setup picker; a primary "Save" button at least 44px tall. On save: `addTrade(...)` then `claimManualFill(...)`. A `NEEDS_REVIEW` fill gets the amber marker and a "Not mine" secondary action.

- [ ] **Step 3: `Capture`, `Today`, `TimelineRO`**

`Capture` — one large textarea plus the four sigils QuickCapture already infers (`!` mistake, `?` question, plain = observation), calling `observe()`.
`Today` — the locked thesis read-only, plus an append field calling `appendToSession()`. **Never allow editing a locked thesis here**; that rule is the product.
`TimelineRO` — the month list at 34px rows, read-only, no zoom controls.

- [ ] **Step 4: Route by width in `LedgerView.tsx`**

```tsx
import MobileLedger from '../ledger/mobile/MobileLedger'

// Same 768px breakpoint the rest of the app uses (App.tsx:32-44), so the phone
// header and the phone journal agree about what "mobile" means.
const isDesktop = useIsDesktop()
...
{booted ? (isDesktop ? <LedgerApp /> : <MobileLedger />) : null}
```

Export `useIsDesktop` from `App.tsx` (or lift it to `src/lib/useIsDesktop.ts` and import it in both) rather than duplicating the `matchMedia` logic — two copies would drift.

- [ ] **Step 5: Kill the `window.prompt()` flows reachable from mobile**

```bash
grep -rn "window.prompt" frontend/src/ledger/
```

Any prompt reachable from the four mobile screens becomes an inline field. Prompts only reachable from desktop surfaces may stay for now; note which in a comment.

- [ ] **Step 6: Verify on a real device**

```bash
npm run build
```

Open the tailnet URL on your phone, go to the journal, and confirm: the bottom tab bar sits above the home indicator, tap targets are comfortable, the page does not scroll horizontally, and a pending fill can be answered entirely with a thumb.

- [ ] **Step 7: Commit** *(hold unless asked)*

```bash
git add frontend/src/ledger/mobile frontend/src/views/LedgerView.tsx
git commit -m "feat(ledger): phone capture shell — pending reasons, capture, today, timeline"
```

---

### Task 10: Prove the boundary, and relabel the two belief panels

**Files:**
- Test: `backend/tests/ledger/test_isolation.py`
- Modify: `frontend/src/ledger/surfaces/Stats.tsx`
- Verify: `pytest tests research_tests -q`, `scripts/dryrun.py 700`

- [ ] **Step 1: Write the isolation test**

Create `backend/tests/ledger/test_isolation.py`:

```python
"""The ledger is read-and-record only. These assertions are the guardrail: a
detector bug must never be able to become a real-money bug."""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]   # backend/


def _py(pkg):
    return list((ROOT / "app" / pkg).rglob("*.py"))


def test_the_engine_never_imports_the_ledger():
    offenders = [p for p in _py("engine") + _py("api") + _py("db")
                 if re.search(r"^\s*(from|import)\s+app\.ledger",
                              p.read_text(), re.M)]
    # runner.py schedules the lane and is the single permitted exception.
    offenders = [p for p in offenders if p.name != "runner.py"]
    assert offenders == [], f"engine code importing app.ledger: {offenders}"


def test_the_ledger_never_writes_the_execution_tables():
    banned = re.compile(r"\b(Position|Trade|CapitalState|EquitySnapshot)\s*\(")
    offenders = [p for p in _py("ledger") if banned.search(p.read_text())]
    assert offenders == [], f"ledger code constructing execution ORM rows: {offenders}"


def test_the_bot_tag_constant_agrees_with_the_live_broker():
    """classify.py deliberately does not import live_broker (that would breach the
    boundary), so the two constants must be checked to agree."""
    from app.ledger.classify import BOT_TAG
    src = (ROOT / "app" / "engine" / "live_broker.py").read_text()
    m = re.search(r'^TAG\s*=\s*["\']([^"\']+)["\']', src, re.M)
    assert m, "could not find TAG in live_broker.py"
    assert m.group(1) == BOT_TAG


def test_the_safe_kite_allowlist_was_not_widened():
    src = (ROOT / "app" / "providers" / "safe_kite.py").read_text()
    for mutating in ("order.place", "order.modify", "order.cancel"):
        assert f'"{mutating}"' not in src.split("ALLOWED_ROUTES")[1][:2000], \
            f"{mutating} appeared in the SafePaperKite allowlist"
```

Adapt the last test to the real shape of `ALLOWED_ROUTES` in `safe_kite.py` — read it first.

- [ ] **Step 2: Run it**

```bash
.venv/bin/python -m pytest tests/ledger/test_isolation.py -q
```

Expected: 4 passed. **If `test_the_engine_never_imports_the_ledger` fails on a file other than `runner.py`, that is a real architectural breach — fix the import, do not widen the exception.**

- [ ] **Step 3: Relabel the two belief-dependent panels (spec §8)**

The owner accepted post-hoc reasoning. `metrics.ts`'s `calibration` and thesis-accuracy analyses measure *belief stated before the outcome was known*; fed reasons written afterwards they still render numbers, but the numbers mean something different.

In `frontend/src/ledger/surfaces/Stats.tsx`, find those two panels and change their "what this would change" hint lines to say so plainly. For example:

```tsx
<Panel
  title="Calibration"
  hint="Confidence vs outcome. Reasons written after the position closed are
        included, so read this as how well you rationalise, not how well you
        forecast — those are different skills and only one of them is calibration."
/>
```

Do **not** delete the panels, and do **not** add a post-hoc badge or latency tracking — the owner declined both. Everything else in the engine (R distribution, expectancy grid, exit quality, mistake ledger, adherence, behavioural sequences, the two ledgers) is unaffected, because none of it depends on when the note was written.

- [ ] **Step 4: Full green**

```bash
cd backend && .venv/bin/python -m pytest tests research_tests -q --tb=short > /tmp/ws2-final.log 2>&1; tail -3 /tmp/ws2-final.log
.venv/bin/python scripts/dryrun.py 700
cd ../frontend && npm run typecheck && npx vitest run && npm run build
```

Expected: both suites green, `LEDGER OK ✓`, typecheck and build clean.

- [ ] **Step 5: Commit** *(hold unless asked)*

```bash
git add backend/tests/ledger/test_isolation.py frontend/src/ledger/surfaces/Stats.tsx
git commit -m "test(ledger): assert the read-only boundary; relabel the belief-dependent panels"
```

---

## Deployment checklist for WS-2

- [ ] `PT_LEDGER_DB_PATH` already pinned by WS-1. Confirm it is still absolute in the VPS `.env`.
- [ ] No new env var is required — `manual_detect_enabled` / `manual_detect_seconds` go through `runtime_config`, which is DB-backed. **If you add one anyway, it must be written into the VPS `.env` by hand**; `.env` is excluded from the rsync and this is the single most-repeated deploy failure in this repo.
- [ ] Confirm the `ledger_manual_fill` migration self-applies: `*.db` is excluded from the rsync, so the table must be created by `migrate_ledger_db()` on boot, not shipped.
- [ ] Confirm `runtime_config` has no stale override shadowing the new defaults — a shipped default silently has no effect if an override exists.
- [ ] `npm run build` on the Mac. Never on the VPS (1GB droplet, has OOM'd twice with the engine running).
- [ ] Deploy via `scripts/deploy.sh` only. It refuses during market hours and on a dirty tree.
- [ ] After deploy, curl **`/`** as well as `/api/health` — the latter is a liveness stub that returned 200 through both 2026-07 outages.
- [ ] Watch the first live session: `journalctl -u paper-trader -f | grep manual-detect`. Expect `lane started`, then either silence or `N new manual fill(s) awaiting a reason`.
- [ ] **On the first live day, verify no bot order was misclassified.** Compare `SELECT order_id FROM ledger_manual_fill` against `SELECT order_id FROM order_journal` — the intersection must be empty. A non-empty intersection means the classifier is wrong and the lane should be disabled via `manual_detect_enabled` until it is fixed.

---

## Self-review

**Spec coverage.** §3.4 classification → Tasks 1, 6; persistence → Task 2; broker reads → Task 3; the two live unknowns → Task 4; fill aggregation and round trips → Task 5; the polling lane, cadence and session-close sweep → Task 7; REST and Inbox capture → Task 8. §3.5 mobile capture shell → Task 9. §8 relabelling → Task 10. The read-only boundary is asserted mechanically in Task 10 rather than left as a convention.

**The GTT decision** (§spec offered two options) is made explicitly above and implemented in Task 1: symbol overlap forces `NEEDS_REVIEW`. It costs an occasional extra prompt and touches nothing in the live order path.

**Known soft spots, stated rather than hidden:**
- Task 3's test fixture reaches into `KiteProvider` internals (`_warn`, `_throttle`) from recon rather than from having the file open; the step says to adapt it first.
- Task 7's runner edit depends on the real local names in `runner.py` for the task list and settings accessor.
- Task 5's `pair_round_trips` FIFO model assumes the owner does not run two independent positions in the same symbol simultaneously and expect them tracked separately. For a discretionary book that is right; if it ever stops being right, the pairing needs a lot-id, not a patch.
- `test_the_safe_kite_allowlist_was_not_widened` parses source text and will need adjusting to the real `ALLOWED_ROUTES` shape.
- Task 4 is genuinely blocking for nothing except confirmation — Task 5 already joins on `order_id`, which is the design that holds whichever way Q1 resolves.
