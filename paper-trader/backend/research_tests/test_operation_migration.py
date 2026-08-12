from sqlalchemy import inspect

from research.domain.base import init_research_db, make_engine


def test_research_schema_has_owner_scoped_operation_authority(tmp_path):
    engine = make_engine(str(tmp_path / "research.db"))
    init_research_db(engine)
    try:
        inspector = inspect(engine)
        assert "research_operation" in inspector.get_table_names()
        columns = {column["name"] for column in inspector.get_columns("research_operation")}
        assert {"owner_id", "operation_id", "claim_token", "claim_expires_at", "cancel_requested_at"} <= columns
        indexes = {index["name"] for index in inspector.get_indexes("research_operation")}
        assert {"ix_research_operation_owner_latest", "ix_research_operation_owner_status", "ix_research_operation_claim_expiry"} <= indexes
    finally:
        engine.dispose()
