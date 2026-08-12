"""Tenant boundaries for ledger evidence that predates the main money database."""
from __future__ import annotations

from datetime import datetime

from app.ledger import service
from app.ledger.db import init_ledger_db, make_engine
from app.ledger.models import LedgerManualFill


OWNER_A, OWNER_B = "ledger.a", "ledger.b"
ACCOUNT_A, ACCOUNT_B = "ledger-account.a", "ledger-account.b"


def _sm(tmp_path):
    from sqlalchemy.orm import sessionmaker

    engine = make_engine(str(tmp_path / "ledger.db"))
    init_ledger_db(engine)
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


def test_snapshot_and_artifact_ids_are_reusable_across_accounts_without_visibility(tmp_path):
    """Dropping either owner/account predicate would return A's evidence to B."""
    sm = _sm(tmp_path)
    assert service.write_snapshot(sm, "{\"tenant\":\"a\"}", None, owner_id=OWNER_A,
                                  broker_account_id=ACCOUNT_A) == 1
    assert service.write_snapshot(sm, "{\"tenant\":\"b\"}", None, owner_id=OWNER_B,
                                  broker_account_id=ACCOUNT_B) == 1
    service.put_artifact(sm, "same", "text/plain", b"A", owner_id=OWNER_A,
                         broker_account_id=ACCOUNT_A)
    service.put_artifact(sm, "same", "text/plain", b"B", owner_id=OWNER_B,
                         broker_account_id=ACCOUNT_B)
    assert service.read_snapshot(sm, owner_id=OWNER_A, broker_account_id=ACCOUNT_A) == (1, "{\"tenant\":\"a\"}")
    assert service.get_artifact(sm, "same", owner_id=OWNER_B,
                                broker_account_id=ACCOUNT_B) == ("text/plain", b"B")
    assert service.delete_artifact(sm, "same", owner_id=OWNER_B,
                                   broker_account_id=ACCOUNT_B) is True
    assert service.get_artifact(sm, "same", owner_id=OWNER_A,
                                broker_account_id=ACCOUNT_A) == ("text/plain", b"A")


def test_snapshot_keeps_id_one_invariant_inside_each_owner_account_scope(tmp_path):
    """Removing the id check would admit a second mutable snapshot per account."""
    from sqlalchemy import text
    sm = _sm(tmp_path)
    with sm() as session, session.begin():
        with __import__("pytest").raises(Exception):
            session.execute(text(
                "INSERT INTO ledger_snapshot "
                "(owner_id, broker_account_id, id, version, payload, updated_at) "
                "VALUES ('ledger.a', 'ledger-account.a', 2, 1, '{}', CURRENT_TIMESTAMP)"))


def test_cross_scope_fill_claim_refuses_without_mutating_the_fill(tmp_path):
    """Changing the trade scope validation to an id-only check would claim A's fill for B."""
    sm = _sm(tmp_path)
    with sm() as session, session.begin():
        session.add(LedgerManualFill(
            owner_id=OWNER_A, broker_account_id=ACCOUNT_A, order_id="same-order",
            tradingsymbol="A", exchange="NFO", product="NRML", side="BUY", qty=1,
            avg_price=1.0, order_ts=datetime(2026, 8, 12), fill_ts=None, verdict="MANUAL",
            raw="{}", seen_at=datetime(2026, 8, 12)))
    assert service.claim_manual_fill(sm, "same-order", "foreign-trade", owner_id=OWNER_B,
                                     broker_account_id=ACCOUNT_B,
                                     trade_exists=lambda *_: False) is False
    with sm() as session:
        row = session.get(LedgerManualFill, (OWNER_A, ACCOUNT_A, "same-order"))
        assert row.claimed_trade is None


def test_restart_after_legacy_rename_preserves_financial_evidence(tmp_path):
    """A restart after rename but before copy must not strand global ledger evidence."""
    from sqlalchemy import text

    path = tmp_path / "legacy-restart.db"
    engine = make_engine(str(path))
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE ledger_snapshot (id INTEGER PRIMARY KEY, version INTEGER NOT NULL, payload TEXT NOT NULL, updated_at DATETIME NOT NULL)"))
        conn.execute(text("INSERT INTO ledger_snapshot VALUES (1, 4, :payload, '2026-08-12 09:00:00')"),
                     {"payload": '{"preserve":true}'})
        conn.execute(text("ALTER TABLE ledger_snapshot RENAME TO ledger_snapshot_legacy_scope"))
    init_ledger_db(engine)
    sm = __import__("sqlalchemy").orm.sessionmaker(bind=engine, future=True)
    assert service.read_snapshot(sm, owner_id="owner", broker_account_id="account.default") == (
        4, '{"preserve":true}')
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM sqlite_master WHERE name = 'ledger_snapshot_legacy_scope'")) .scalar() == 0
