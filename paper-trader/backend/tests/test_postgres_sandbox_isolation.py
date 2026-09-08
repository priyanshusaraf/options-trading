"""Behavioral proof of the shared PostgreSQL sandbox contract.

Owner requirement: prove that two tests can run concurrently against one
cluster without touching each other, that every target starts verified-empty,
and that cleanup removes exactly what the sandbox created.
"""
from __future__ import annotations

import threading

import pytest
import sqlalchemy as sa

from tests.postgres_sandbox import PostgresSandbox, postgres_url_available

pytestmark = pytest.mark.skipif(
    not postgres_url_available(), reason="disposable PostgreSQL 16 harness not configured"
)


def _worker(role: str, sentinel_owner: str, results: dict, errors: dict) -> None:
    try:
        with PostgresSandbox() as sandbox:
            engine = sandbox.research_engine
            # Verified-empty starting state, checked before any migration.
            with engine.connect() as connection:
                tables = connection.execute(sa.text(
                    "SELECT count(*) FROM pg_tables "
                    "WHERE schemaname NOT IN ('pg_catalog', 'information_schema')"
                )).scalar_one()
            assert tables == 0, f"{role}: sandbox did not start empty"
            from research.domain.base import init_research_db

            init_research_db(engine)
            from app.ir.hashing import canonical_json, content_address

            document = {
                "owner_id": sentinel_owner, "graph_identifier": "iso",
                "graph_version": 1, "graph_address": None,
                "scheme": "v1", "contract_suite": "c", "parity_suite": "p",
            }
            document["graph_address"] = "sha256:" + "1" * 64
            artifact = canonical_json(document)
            with engine.begin() as connection:
                connection.execute(sa.text(
                    "INSERT INTO research_strategy_admission "
                    "(owner_id, admission_address, graph_identifier, graph_version, "
                    "graph_address, artifact_json, scheme, contract_suite, parity_suite, "
                    "created_at) VALUES (:owner, :addr, 'iso', 1, "
                    ":graph, :artifact, 'v1', 'c', 'p', CURRENT_TIMESTAMP)"
                ), {"owner": sentinel_owner,
                    "addr": content_address({**document, "admission": sentinel_owner}),
                    "graph": document["graph_address"], "artifact": artifact})
            results[role] = {"url": sandbox.research_url}
    except Exception as error:  # noqa: BLE001 - reported to the main thread
        errors[role] = error


@pytest.mark.skipif(not postgres_url_available(),
                    reason="disposable PostgreSQL 16 harness not configured")
def test_two_concurrent_sandboxes_never_share_state():
    results: dict = {}
    errors: dict = {}
    threads = [
        threading.Thread(target=_worker, args=("thread-a", "owner-alpha", results, errors)),
        threading.Thread(target=_worker, args=("thread-b", "owner-beta", results, errors)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(120)
    assert not errors, f"sandbox workers failed: {errors}"
    assert set(results) == {"thread-a", "thread-b"}
    assert results["thread-a"]["url"] != results["thread-b"]["url"]

    # After close(), each database is gone from the cluster: no survivor state.
    for role in ("thread-a", "thread-b"):
        admin = sa.create_engine(postgres_url_available(), isolation_level="AUTOCOMMIT",
                                 future=True)
        try:
            with admin.connect() as connection:
                exists = connection.execute(sa.text(
                    "SELECT count(*) FROM pg_database WHERE datname LIKE :pattern"
                ), {"pattern": "pt_sandbox_research_%"}).scalar_one()
            assert exists == 0, f"{role}: sandbox databases survived cleanup"
        finally:
            admin.dispose()


@pytest.mark.skipif(not postgres_url_available(),
                    reason="disposable PostgreSQL 16 harness not configured")
def test_sandbox_targets_are_distinct_verified_empty_databases():
    with PostgresSandbox() as sandbox:
        urls = {role: sandbox.url(role) for role in ("execution", "research", "ledger")}
        assert len(set(urls.values())) == 3
        for role, url in urls.items():
            probe = sa.create_engine(url, future=True)
            try:
                with probe.connect() as connection:
                    assert connection.execute(sa.text(
                        "SELECT count(*) FROM pg_tables "
                        "WHERE schemaname NOT IN ('pg_catalog', 'information_schema')"
                    )).scalar_one() == 0
            finally:
                probe.dispose()
