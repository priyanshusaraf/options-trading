"""`/api/health` reports the schema revision.

Phase A requires the schema version to be *exposed*, not merely tracked. The whole
lesson of 2026-07-28 was that deployment state must be measurable from outside the
box; a migrated schema is part of that state. `build.commit` says which code is
running — `schema.current` says which shape the database under it is in, and those
two can disagree (restored backup, boot that skipped init_db).
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.db import migrate
from app.main import app


def test_health_reports_schema_revision():
    # No `with` — a bare TestClient skips lifespan, so the engine lanes never
    # start. This test only wants the HTTP handler. (See the test-hazard note in
    # tests/conftest.py: `with TestClient(app)` runs the real engine.)
    client = TestClient(app)
    body = client.get("/api/health").json()

    assert "schema" in body, "health must expose the schema revision"
    schema = body["schema"]
    assert set(schema) >= {"current", "head", "up_to_date"}
    assert schema["head"] == migrate.head_revision()
    assert schema["up_to_date"] is (schema["current"] == schema["head"])


def test_schema_info_never_raises(monkeypatch):
    """The probe must not 500 on its own bug — same contract as every other read
    in _readiness_payload."""
    from app import main

    monkeypatch.setattr(migrate, "schema_state",
                        lambda _e: (_ for _ in ()).throw(RuntimeError("boom")))
    info = main._schema_info()
    assert info["up_to_date"] is None
    assert "boom" in info["error"]
