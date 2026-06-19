"""Test isolation — NEVER touch the live paper_trader.db.

Tests that call init_db(reset=True) (broker/engine/route tests) drop & recreate
all tables. Point the DB at a throwaway temp file BEFORE any app module — and
thus the module-level SQLAlchemy engine in app.db.session — is imported, so the
owner's real database is untouchable from the suite. A real OS env var overrides
the .env value in pydantic-settings.
"""
import os
import tempfile

os.environ["PT_DB_PATH"] = os.path.join(tempfile.gettempdir(), "paper_trader_pytest.db")
os.environ["PT_PROVIDER"] = "mock"
