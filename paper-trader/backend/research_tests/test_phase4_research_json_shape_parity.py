"""Closed cross-dialect contracts for research JSON object/array authority."""
from __future__ import annotations

import datetime as dt
import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql, sqlite

from research.domain import migrate
from research.domain.base import ResearchBase
from research.domain import models as _models  # noqa: F401 - register complete metadata


ADDRESS = "sha256:" + "a" * 64
JSON_SITES = (
    ("research_ir_v2_graph_versions", "ck_research_ir_v2_graph_versions_valid_json",
     "artifact_json", "object"),
    ("research_strategy_admission", "ck_research_strategy_admission_valid_json",
     "artifact_json", "object"),
    ("research_dataset_manifests", "ck_research_dataset_manifest_json",
     "manifest_json", "object"),
    ("research_dataset_manifests_v2", "ck_research_dataset_manifest_v2_segments_json",
     "segment_addresses_json", "array"),
    ("research_dataset_manifests_v2", "ck_research_dataset_manifest_v2_instruments_json",
     "instrument_addresses_json", "array"),
    ("research_dataset_manifests_v2", "ck_research_dataset_manifest_v2_fields_json",
     "fields_json", "array"),
    ("research_dataset_manifests_v2", "ck_research_dataset_manifest_v2_gaps_json",
     "gaps_json", "array"),
    ("research_dataset_manifests_v2", "ck_research_dataset_manifest_v2_dependencies_json",
     "dependency_addresses_json", "array"),
)


def _constraint(table_name: str, constraint_name: str):
    return next(
        constraint for constraint in ResearchBase.metadata.tables[table_name].constraints
        if constraint.name == constraint_name
    )


def test_all_eight_json_sites_compile_to_explicit_equal_shape_contracts():
    assert migrate.HEAD_VERSION == migrate.head_version() == "0011"
    assert len(JSON_SITES) == 8
    for table, name, column, shape in JSON_SITES:
        expression = _constraint(table, name).sqltext
        sqlite_sql = str(expression.compile(dialect=sqlite.dialect()))
        postgres_sql = str(expression.compile(dialect=postgresql.dialect()))
        assert f"json_valid({column})" in sqlite_sql
        assert f"json_type({column}) = '{shape}'" in sqlite_sql
        assert sqlite_sql.count(f"json_valid({column})") == 2
        assert "CASE WHEN" in sqlite_sql
        assert postgres_sql == f"jsonb_typeof({column}::jsonb) = '{shape}'"


@pytest.fixture(params=("sqlite", "postgresql"))
def shape_engine(request, tmp_path):
    if request.param == "postgresql":
        # Resolved lazily so the sqlite parameter still runs without a harness.
        import os

        if not os.environ.get("PT_TEST_POSTGRES_URL"):
            pytest.skip("disposable PostgreSQL 16 URL not supplied")
        from tests.postgres_sandbox import PostgresSandbox

        sandbox = PostgresSandbox()
        try:
            engine = sandbox.research_engine
            migrate.migrate_research_db(engine)
            try:
                yield engine
            finally:
                engine.dispose()
        finally:
            sandbox.close()
        return
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'shape.db'}", future=True)
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
    migrate.migrate_research_db(engine)
    try:
        yield engine
    finally:
        engine.dispose()


def _insert_graph(connection, key: str, payload: str) -> None:
    connection.execute(sa.text(
        "INSERT INTO research_ir_v2_graph_versions "
        "(owner_id,graph_identifier,graph_version,artifact_json,format_version,"
        "content_address,graph_address,registry_snapshot_address,created_at) VALUES "
        "(:owner,:key,1,:payload,2,:address,:address,:address,:created)"
    ), {"owner": f"owner-{key}", "key": key, "payload": payload,
        "address": ADDRESS, "created": dt.datetime(2025, 1, 1)})


def _insert_admission(connection, key: str, payload: str) -> None:
    connection.execute(sa.text(
        "INSERT INTO research_strategy_admission "
        "(owner_id,admission_address,graph_identifier,graph_version,graph_address,"
        "artifact_json,scheme,contract_suite,parity_suite,created_at) VALUES "
        "(:owner,:admission,:key,1,:address,:payload,'v1','contract','parity',:created)"
    ), {"owner": f"owner-{key}", "admission": ADDRESS,
        "key": key, "address": ADDRESS, "payload": payload,
        "created": dt.datetime(2025, 1, 1)})


def _insert_legacy_manifest(connection, key: str, payload: str) -> None:
    connection.execute(sa.text(
        "INSERT INTO research_dataset_manifests "
        "(owner_id,digest,provider,dataset_version,market_truth_digest,capability_digest,"
        "manifest_json,created_at) VALUES "
        "(:owner,:digest,'provider','v1',:address,:address,:payload,:created)"
    ), {"owner": f"owner-{key}", "digest": ADDRESS,
        "address": ADDRESS, "payload": payload, "created": dt.datetime(2025, 1, 1)})


def _insert_typed_manifest(connection, key: str, column: str, payload: str) -> None:
    values = {
        "segment_addresses_json": "[]", "instrument_addresses_json": "[]",
        "fields_json": "[]", "gaps_json": "[]", "dependency_addresses_json": "[]",
    }
    values[column] = payload
    connection.execute(sa.text(
        "INSERT INTO research_dataset_manifests_v2 "
        "(owner_id,manifest_address,canonical_bytes,aggregate_byte_digest,"
        "aggregate_byte_length,segment_addresses_json,instrument_addresses_json,fields_json,"
        "gaps_json,dependency_addresses_json,event_start,event_end,availability_start,"
        "availability_end,authority_state) VALUES "
        "(:owner,:manifest,:canonical,:digest,1,:segment_addresses_json,"
        ":instrument_addresses_json,:fields_json,:gaps_json,:dependency_addresses_json,"
        "'2025-01-01T00:00:00Z','2025-01-01T00:00:01Z','2025-01-01T00:00:00Z',"
        "'2025-01-01T00:00:01Z','VERIFIED_V2')"
    ), {**values, "owner": f"owner-{key}", "manifest": ADDRESS,
        "canonical": b"x", "digest": ADDRESS})


OBJECT_CASES = ("{", "null", "1", '"string"', "[]")
ARRAY_CASES = ("[", "null", "1", '"string"', "{}")


def test_real_tables_accept_declared_shapes_and_refuse_every_other_shape(shape_engine):
    valid_objects = (
        (_insert_graph, "graph-valid", '{"strategy_id":"graph-valid","strategy_version":1}'),
        (_insert_admission, "admission-valid",
         '{"owner_id":"owner-admission-valid","graph_identifier":"admission-valid",'
         '"graph_version":1,"graph_address":"' + ADDRESS + '","scheme":"v1",'
         '"contract_suite":"contract","parity_suite":"parity"}'),
        (_insert_legacy_manifest, "legacy-valid",
         '{"owner_id":"owner-legacy-valid","provider":"provider","dataset_version":"v1",'
         '"market_truth_digest":"' + ADDRESS + '","capability_digest":"' + ADDRESS + '",'
         '"schema_version":1}'),
    )
    with shape_engine.begin() as connection:
        for insert, key, payload in valid_objects:
            insert(connection, key, payload)
        _insert_typed_manifest(connection, "typed-valid", "fields_json", "[]")

    object_inserts = (_insert_graph, _insert_admission, _insert_legacy_manifest)
    for site, insert in enumerate(object_inserts):
        for case, payload in enumerate(OBJECT_CASES):
            with pytest.raises(sa.exc.DBAPIError):
                with shape_engine.begin() as connection:
                    insert(connection, f"{chr(98 + site)}{case}", payload)
    for site, (_table, _name, column, _shape) in enumerate(JSON_SITES[3:]):
        for case, payload in enumerate(ARRAY_CASES):
            with pytest.raises(sa.exc.DBAPIError):
                with shape_engine.begin() as connection:
                    _insert_typed_manifest(connection, f"{chr(102 + site)}{case}", column, payload)
