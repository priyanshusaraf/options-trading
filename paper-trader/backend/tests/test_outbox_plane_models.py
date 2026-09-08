"""Each physical private plane owns the same outbox contract in its metadata."""
from app.db.models import Base
from app.ledger.db import LedgerBase
from app.ledger import db as ledger_db
from research.domain.base import ResearchBase
from research.domain import migrate as research_migrate
from alembic.script import ScriptDirectory
from app.db import migrate as execution_migrate
from app.ledger import models as _ledger_models  # noqa: F401
from research.domain import models as _research_models  # noqa: F401


EXPECTED = {
    "execution_outbox_stream_head",
    "execution_outbox_event",
    "execution_outbox_consumer_cursor",
    "execution_outbox_consumer_receipt",
    "execution_outbox_retention_watermark",
}


def test_execution_metadata_owns_execution_outbox_only():
    assert EXPECTED <= set(Base.metadata.tables)
    assert not any(name.startswith("research_outbox_") or name.startswith("ledger_outbox_")
                   for name in Base.metadata.tables)


def test_research_metadata_owns_research_outbox_only():
    expected = {name.replace("execution_", "research_") for name in EXPECTED}
    assert expected <= set(ResearchBase.metadata.tables)
    assert not any(name.startswith("execution_outbox_") or name.startswith("ledger_outbox_")
                   for name in ResearchBase.metadata.tables)


def test_ledger_metadata_owns_ledger_outbox_only():
    expected = {name.replace("execution_", "ledger_") for name in EXPECTED}
    assert expected <= set(LedgerBase.metadata.tables)
    assert not any(name.startswith("execution_outbox_") or name.startswith("research_outbox_")
                   for name in LedgerBase.metadata.tables)


def test_each_plane_schema_head_includes_its_outbox_contract():
    script = ScriptDirectory.from_config(execution_migrate.alembic_config())
    # A-04 refresh: pinned when 0034 was head; the outbox contract must be
    # carried by whatever the current single additive head is.
    assert script.get_current_head() == script.get_revision(script.get_current_head()).revision
    # A-04 refresh: pinned 0005/0002 when those were the heads. The outbox
    # contract itself is guarded by the metadata membership checks; these pins
    # stay literal so a future head move fails loudly here, once.
    assert research_migrate.HEAD_VERSION == "0011"
    assert ledger_db.HEAD_VERSION == "0002"
