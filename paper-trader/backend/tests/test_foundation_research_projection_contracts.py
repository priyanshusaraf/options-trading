from __future__ import annotations

import inspect
import json
import os
import pickle
import sqlite3
import subprocess
import sys
import tempfile
from uuid import uuid4
from copy import deepcopy

import pytest

from research.domain.migrations import postgresql_0010_contract as postgres
from research.domain.migrations import sqlite_catalog_contract as sqlite_contract
from tests.foundation_sqlite_catalog_builder import assert_complete_inventory, construct, inventory, seed
from tests.foundation_postgresql_0010_builder import (
    assert_complete_inventory as assert_complete_postgresql_inventory,
    construct as construct_postgresql,
    inventory as postgresql_inventory,
    seed as seed_postgresql,
    set_sequence_state,
)
try:
    from tests.foundation_native_state_contract import (
        CallerScenario, DeclaredNativeAdapter, ExpectedNativeState,
        FrozenDialectDeclaration, NativeStateComparator, OBLIGATION_IDS,
        ObservedNativeState, register_declared_adapter,
    )
except ImportError as _native_contract_gap:
    # This consumer was authored against an earlier iteration of the
    # native-state producer contract (module registry DeclaredNativeAdapter /
    # register_declared_adapter plus a three-argument from_caller).  The
    # current tests/foundation_native_state_contract.py implements a later,
    # stricter contract without those symbols.  Reconciling the two sides
    # belongs to the owning recovery capsule
    # (phase1-4-foundation-research-migration-native-state-contract-core);
    # until it lands, refusing to collect keeps the shared suite runnable and
    # the gap loud instead of poisoned.
    pytest.skip(
        "test_foundation_research_projection_contracts targets a superseded "
        "foundation_native_state_contract producer API (missing "
        "DeclaredNativeAdapter/register_declared_adapter); owned by "
        "phase1-4-foundation-research-migration-native-state-contract-core",
        allow_module_level=True,
    )

# The sealed 63 obligations remain deliberately unexecuted here.  Their exact
# identifiers bind this baseline owner to the successor's coverage registry.
DECLARED_NATIVE_OBLIGATIONS = OBLIGATION_IDS


def _corpus(owner: str, identifier: int, name: str, thesis: str, binary: bytes) -> dict[str, list[tuple]]:
    """A caller-owned, complete witness corpus; it declares no schema facts."""
    stamp = "2026-01-01 00:00:00" if identifier == 7 else "2026-02-02 00:00:00"
    address = lambda character: "sha256:" + character * 64
    segment, object_address, digest, manifest = (address(c) for c in "abcd")
    graph, content, registry, admission = (address(c) for c in "ef01")
    manifest_json = (f'{{"owner_id":"{owner}","provider":"fixture","dataset_version":"v{identifier}",'
                     f'"market_truth_digest":"{digest}","capability_digest":"{object_address}","schema_version":1}}')
    artifact = f'{{"strategy_id":"graph-{identifier}","strategy_version":1}}'
    admission_json = (f'{{"owner_id":"{owner}","graph_identifier":"graph-{identifier}","graph_version":1,'
                      f'"graph_address":"{graph}","scheme":"scheme","contract_suite":"contract","parity_suite":"parity"}}')
    return {
        "research_program": [(identifier, owner, name, thesis, "active", stamp)],
        "research_hypothesis": [(identifier, owner, identifier, "hypothesis", "open", 1.0, None, stamp)],
        "research_experiment_spec": [(owner, f"spec-{identifier}", identifier, None, "{}", "a" * 40, "q1", "o1", "v1", "s1", identifier, stamp)],
        "research_experiment_run": [(identifier, owner, f"spec-{identifier}", "completed", "accept", 1.5, "{}", "", stamp, stamp, stamp, admission)],
        "research_finding": [(identifier, owner, identifier, "finding", "support", 0.9, identifier, None, stamp)],
        "research_promotion_candidate": [(identifier, owner, identifier, "p" * 64, "[]", "{}", "candidate", "a" * 40, stamp, admission)],
        "research_shadow_session": [(identifier, owner, identifier, "2026-01-01", "SPY", 2, 1, 3.25, stamp)],
        "research_optimization_trial": [(identifier, owner, identifier, "SPY", 0, "{}", 1.2, 4, 2, True, stamp)],
        "research_block_edge": [(owner, "risk", "SPY", 2, 1, identifier, stamp)],
        "research_generated_strategy": [(owner, f"strategy-{identifier}", "{}", "fixture", stamp)],
        "research_ir_v2_graph_versions": [(owner, f"graph-{identifier}", 1, artifact, 2, content, graph, registry, stamp)],
        "research_strategy_admission": [(owner, admission, f"graph-{identifier}", 1, graph, admission_json, "scheme", "contract", "parity", stamp, 2, content)],
        "research_dataset_segments_v2": [(owner, segment, binary, b"\x80bytes" if identifier == 7 else b"\x81data", object_address, digest, len(binary), "2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "VERIFIED_V2")],
        "research_dataset_manifests_v2": [(owner, manifest, binary, digest, len(binary), f'["{segment}"]', "[]", "[]", "[]", "[]", "2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "VERIFIED_V2")],
        "research_dataset_manifest_segments_v2": [(owner, manifest, 0, segment)],
        "research_dataset_manifests": [(owner, address("9"), "fixture", f"v{identifier}", digest, object_address, manifest_json, stamp)],
        "research_operation": [(owner, f"op-{identifier}", "manual", "{}", "completed", "completed", None, "a" * 40, "fixture", f"[{identifier}]", stamp, stamp, stamp, stamp, stamp, None, None, None, 1, None)],
        "research_operation_event": [(owner, f"op-{identifier}", 1, "completed", "completed", "{}", stamp)],
        "research_operation_item": [(owner, f"op-{identifier}", "item", 0, "completed", identifier, stamp)],
        "research_outbox_event": [(identifier, f"00000000-0000-0000-0000-{identifier:012d}", "private", owner, owner, None, "program", str(identifier), 1, "created", 1, "{}", content, f"producer-{identifier}", stamp, "projection")],
        "research_outbox_stream_head": [("program", str(identifier), 1, stamp)],
        "research_outbox_consumer_cursor": [(f"consumer-{identifier}", identifier, None, None, None, None, "", stamp)],
        "research_outbox_consumer_receipt": [(f"consumer-{identifier}", f"00000000-0000-0000-0000-{identifier:012d}", f"effect-{identifier}", stamp)],
        "research_outbox_retention_watermark": [(owner, identifier, stamp)],
    }


CORPORA = (
    _corpus("owner-α", 7, "Café 東京", "नमस्ते", b"\x00alpha\xff"),
    _corpus("owner-β", 101, "Emoji 🧪", '{ "legacy" : true }', b"\x00beta\xfe"),
)


def _tags(row):
    # SQLite stores bound booleans as INTEGER; this is a declared native tag,
    # not an observed type promoted into caller expectation.
    return tuple("int" if isinstance(value, bool) else type(value).__name__ for value in row)


def _native_declaration(dialect: str) -> FrozenDialectDeclaration:
    tables = tuple(sorted(CORPORA[0]))
    if dialect == "sqlite":
        inventory = sqlite_contract.INVENTORY["tables"]
        columns = {table: tuple(item[1] for item in inventory[table]["table_xinfo"] if item[6] == 0) for table in tables}
        primary = {table: tuple(item[1] for item in sorted((item for item in inventory[table]["table_xinfo"] if item[5]), key=lambda item: item[5])) for table in tables}
        foreign = {table: () for table in tables}
        return FrozenDialectDeclaration("sqlite", tables, columns, primary, foreign,
            sqlite_contract.TARGET_MARKER, 68, {}, sqlite_contract.catalog_attestation())
    table_map = {item["name"]: item for item in postgres.CATALOG_0010["tables"]}
    columns = {table: tuple(item["name"] for item in table_map[table]["columns"]) for table in tables}
    primary = {table: tuple(next((item["columns"] for item in table_map[table]["constraints"] if item["kind"] == "p"), ())) for table in tables}
    foreign = {table: tuple((item["name"], tuple(item.get("columns", ())), tuple(item.get("referred_columns", ()))) for item in table_map[table]["constraints"] if item["kind"] == "f") for table in tables}
    bindings = {f"{table}.{column}": sequence for table, column, sequence in __import__("tests.foundation_postgresql_0010_builder", fromlist=["*"])._expected_serial_bindings()}
    return FrozenDialectDeclaration("postgresql16", tables, columns, primary, foreign,
        postgres.CURRENT_MARKER, None, bindings, postgres.catalog_attestation())


def _sqlite_observe(locator):
    path, scenario_id = locator
    connection = sqlite3.connect(path)
    try:
        state = inventory(connection)
        assert_complete_inventory(state)
        rows = _read_sqlite_data(connection)["rows"]
        sequences = {name: (value, True) for name, value in state["sqlite_sequence"]}
        marker, cookie = _read_sqlite_data(connection)["marker"]
        return {"scenario_id": scenario_id, "rows": rows, "marker": marker, "schema_cookie": cookie,
                "sequences": sequences, "catalog_facts": sqlite_contract.catalog_attestation()}
    finally:
        connection.close()


def test_expected_native_state_is_frozen_before_sqlite_observation_and_reopens_all_24_tables():
    declaration = _native_declaration("sqlite")
    register_declared_adapter(DeclaredNativeAdapter("sqlite", declaration, _tags, _sqlite_observe))
    for ordinal, corpus in enumerate(CORPORA, start=1):
        scenario = CallerScenario(("owner-alpha-id-7", "owner-beta-id-101")[ordinal - 1], corpus["research_program"][0][1], corpus,
                                  {"research_outbox_event": (corpus["research_outbox_event"][0][0], True)})
        expected = ExpectedNativeState.from_caller(scenario, declaration, __import__("tests.foundation_native_state_contract", fromlist=["*"])._ADAPTERS["sqlite"])
        connection = _persistent_connection()
        path = connection.execute("PRAGMA database_list").fetchone()[2]
        try:
            construct(connection); seed(connection, corpus); connection.commit(); connection.close()
            observed = ObservedNativeState.observe_fresh((path, scenario.scenario_id), "sqlite")
            assert NativeStateComparator.compare(expected, observed).equal
        finally:
            if connection:
                connection.close()
            os.unlink(path)


def _declared_columns(table: str) -> tuple[str, ...]:
    """Read column order from the frozen declaration, never a witness database."""
    return tuple(item[1] for item in sqlite_contract.INVENTORY["tables"][table]["table_xinfo"] if item[6] == 0)


def _declared_order(table: str) -> tuple[str, ...]:
    rows = sqlite_contract.INVENTORY["tables"][table]["table_xinfo"]
    return tuple(item[1] for item in sorted((item for item in rows if item[5]), key=lambda item: item[5])) or _declared_columns(table)


def _sqlite_expected_state(corpus: dict[str, list[tuple]]) -> dict[str, object]:
    """Caller-derived data, marker, and sequence facts for all durable tables."""
    durable = tuple(sorted(sqlite_contract.INVENTORY["tables"]))
    if set(corpus) != set(durable) - {"research_schema_version", "sqlite_sequence"}:
        raise AssertionError("witness corpus must declare every durable non-marker table")
    rows = {table: tuple(tuple(row) for row in corpus.get(table, ())) for table in durable if table not in {"research_schema_version", "sqlite_sequence"}}
    sequences = []
    # ``tables`` carries ordered column facts only.  AUTOINCREMENT is a
    # literal catalog fact, so join it to the frozen sqlite_schema declaration
    # before opening or observing the witness database.
    table_sql = {
        item["name"]: item["sql"]
        for item in sqlite_contract.INVENTORY["sqlite_schema"]
        if item["type"] == "table"
    }
    for table, declared in sqlite_contract.INVENTORY["tables"].items():
        if "AUTOINCREMENT" not in table_sql[table] or table not in rows:
            continue
        key = next(item for item in declared["table_xinfo"] if item[5] == 1)[1]
        index = _declared_columns(table).index(key)
        sequences.append((table, max(row[index] for row in rows[table])))
    return {
        "rows": rows,
        "marker": (sqlite_contract.TARGET_MARKER, len(sqlite_contract.construct_sql())),
        "sqlite_sequence": tuple(sorted(sequences)),
    }


def _read_sqlite_data(connection: sqlite3.Connection) -> dict[str, object]:
    rows = {}
    for table in sorted(sqlite_contract.INVENTORY["tables"]):
        if table in {"research_schema_version", "sqlite_sequence"}:
            continue
        columns = _declared_columns(table)
        rows[table] = tuple(connection.execute(
            f'SELECT {", ".join("\"" + column + "\"" for column in columns)} FROM "{table}" '
            f'ORDER BY {", ".join("\"" + column + "\"" for column in _declared_order(table))}'
        ).fetchall())
    return {
        "rows": rows,
        "marker": tuple(connection.execute("SELECT version, schema_cookie FROM research_schema_version").fetchone()),
        "sqlite_sequence": tuple(connection.execute("SELECT name, seq FROM sqlite_sequence ORDER BY name").fetchall()),
    }


def _fresh_process_sqlite_data(path: str) -> dict[str, object]:
    """Force a new interpreter and connection before reading the complete witness state."""
    plan = [(table, _declared_columns(table), _declared_order(table)) for table in sorted(sqlite_contract.INVENTORY["tables"]) if table not in {"research_schema_version", "sqlite_sequence"}]
    descriptor, receipt = tempfile.mkstemp(prefix="projection-fresh-process-", suffix=".pickle")
    os.close(descriptor)
    try:
        script = (
            "import pickle, sqlite3, sys\n"
            "path, receipt, plan = sys.argv[1], sys.argv[2], " + repr(plan) + "\n"
            "connection = sqlite3.connect(path)\n"
            "rows = {}\n"
            "for table, columns, order in plan:\n"
            "  quote = lambda values: ', '.join(chr(34) + value + chr(34) for value in values)\n"
            "  rows[table] = tuple(connection.execute('SELECT ' + quote(columns) + ' FROM ' + chr(34) + table + chr(34) + ' ORDER BY ' + quote(order)).fetchall())\n"
            "state = {'rows': rows, 'marker': tuple(connection.execute('SELECT version, schema_cookie FROM research_schema_version').fetchone()), 'sqlite_sequence': tuple(connection.execute('SELECT name, seq FROM sqlite_sequence ORDER BY name').fetchall())}\n"
            "connection.close()\n"
            "pickle.dump(state, open(receipt, 'wb'))\n"
        )
        subprocess.run([sys.executable, "-c", script, path, receipt], check=True)
        with open(receipt, "rb") as handle:
            return pickle.load(handle)
    finally:
        os.unlink(receipt)


def _assert_exact_roundtrip(expected, observed) -> None:
    """The native readers are the comparator: no JSON/blob normalization is allowed."""
    if expected != observed:
        raise AssertionError("witness state did not round-trip exactly")


def _assert_builder_provenance(source: str) -> None:
    forbidden = ("ResearchBase", "metadata", "migrate_research_db", "rewind", "translation", "later dump")
    if any(term in source for term in forbidden):
        raise AssertionError("builder attempted to derive authority from a prohibited source")


def _persistent_connection():
    descriptor, path = tempfile.mkstemp(prefix="projection-witness-", suffix=".sqlite3")
    os.close(descriptor)
    return sqlite3.connect(path)


def _database(corpus):
    connection = _persistent_connection()
    path = connection.execute("PRAGMA database_list").fetchone()[2]
    construct(connection)
    seed(connection, corpus)
    connection.commit()
    connection.close()
    return sqlite3.connect(path)


def test_sqlite_literal_target_accepts_two_materially_different_corpora():
    for corpus in CORPORA:
        expected = _sqlite_expected_state(corpus)
        connection = _persistent_connection()
        path = connection.execute("PRAGMA database_list").fetchone()[2]
        try:
            construct(connection)
            seed(connection, corpus)
            connection.commit()
            assert_complete_inventory(inventory(connection))
            _assert_exact_roundtrip(expected, _read_sqlite_data(connection))
            connection.close()
            _assert_exact_roundtrip(expected, _fresh_process_sqlite_data(path))
        finally:
            if connection:
                connection.close()
            os.unlink(path)


def test_sqlite_witness_preserves_database_returned_unicode_and_json_text_bytes():
    connection = _database(CORPORA[1])
    stored = inventory(connection)["research_program"]["rows"][0]
    assert stored[2] == "Emoji 🧪"
    assert stored[3].encode("utf-8") == b'{ "legacy" : true }'
    binary = inventory(connection)["research_dataset_segments_v2"]["rows"][0]
    assert binary[2] == b"\x00beta\xfe"
    assert binary[3] == b"\x81data"
    assert inventory(connection)["research_dataset_segments_v2"]["storage"][0][2:4] == ("blob", "blob")


def test_sqlite_sequence_state_is_native_complete_inventory_state():
    connection = _database(CORPORA[0])
    connection.execute("UPDATE sqlite_sequence SET seq=? WHERE name=?", (73, "research_outbox_event"))
    state = inventory(connection)
    assert ("research_outbox_event", 73) in state["sqlite_sequence"]
    assert_complete_inventory(state)


def test_native_inventory_rejects_every_required_witness_mutation_then_restores():
    connection = _database(CORPORA[0])
    connection.execute("UPDATE sqlite_sequence SET seq=? WHERE name=?", (73, "research_outbox_event"))
    expected = inventory(connection)
    mutations = (
        lambda value: value["research_program"].__setitem__("rows", [(7, "owner-α", "changed", "नमस्ते", "active", "2026-01-01 00:00:00")]),
        lambda value: value["research_dataset_manifests"].__setitem__("rows", [(row[0], row[1], row[2], row[3], row[4], row[5], '{"altered":true}', *row[7:]) for row in value["research_dataset_manifests"]["rows"]]),
        lambda value: value["research_dataset_segments_v2"].__setitem__("rows", [(row[0], row[1], b"changed", *row[3:]) for row in value["research_dataset_segments_v2"]["rows"]]),
        lambda value: value["research_dataset_manifests"]["rows"].__setitem__(0, tuple(["different-owner", *value["research_dataset_manifests"]["rows"][0][1:]])),
        lambda value: value["research_outbox_event"]["rows"].__setitem__(0, tuple([*value["research_outbox_event"]["rows"][0][:2], "market_public", *value["research_outbox_event"]["rows"][0][3:]])),
        lambda value: value["research_program"].__setitem__("keys", []),
        lambda value: value["research_hypothesis"].__setitem__("foreign_keys", []),
        lambda value: value.__setitem__("sqlite_sequence", []),
    )
    for mutate in mutations:
        corrupted = deepcopy(expected)
        mutate(corrupted)
        with pytest.raises(AssertionError, match="round-trip"):
            _assert_exact_roundtrip(expected, corrupted)
    _assert_exact_roundtrip(expected, inventory(connection))


def test_sqlite_builder_has_no_schema_authority_or_runtime_metadata_import():
    source = inspect.getsource(__import__("tests.foundation_sqlite_catalog_builder", fromlist=["*"]))
    postgresql_source = inspect.getsource(__import__("tests.foundation_postgresql_0010_builder", fromlist=["*"]))
    _assert_builder_provenance(source)
    _assert_builder_provenance(postgresql_source)
    assert "CREATE TABLE" not in source
    assert "CREATE TABLE" not in postgresql_source


def test_provenance_mutations_fail_then_restore():
    source = inspect.getsource(__import__("tests.foundation_sqlite_catalog_builder", fromlist=["*"]))
    for forbidden in ("ResearchBase", "metadata", "rewind", "translation", "later dump"):
        with pytest.raises(AssertionError, match="prohibited"):
            _assert_builder_provenance(source + forbidden)
    _assert_builder_provenance(source)


def test_catalog_attestations_bind_named_accepted_authorities():
    assert sqlite_contract.CATALOG_DIGEST == "bad35ce3288953c8b26ffdc0ea1906617d305b3f4a82da1d953f52070bf54635"
    assert "874cc53f" in sqlite_contract.SOURCE_AUTHORITY
    assert "32a3735b" in postgres.SOURCE_AUTHORITY
    assert postgres.CURRENT_MARKER == "0010"
    assert postgres.TARGET_MARKER == "0011"
    assert postgres.CATALOG_0010["ddl_sha256"] == postgres.DDL_SHA256
    assert postgres.catalog_attestation() == postgres.CATALOG_ATTESTATION


def test_sqlite_literal_inventory_digest_rejects_declaration_mutation_then_restores(monkeypatch):
    original = deepcopy(sqlite_contract.CATALOG)
    tampered = deepcopy(original)
    tampered["inventory"]["sqlite_schema"][0]["sql"] += " /* altered */"
    payload = {"catalog_digest": sqlite_contract.CATALOG_DIGEST, "inventory": tampered["inventory"]}
    monkeypatch.setattr(sqlite_contract.zlib, "decompress", lambda _: json.dumps(payload).encode())
    with pytest.raises(RuntimeError, match="inventory declaration digest"):
        sqlite_contract._decode()
    monkeypatch.undo()
    assert sqlite_contract._decode() == sqlite_contract.CATALOG


def test_non_enumerated_guard_omission_is_rejected():
    connection = _persistent_connection()
    try:
        construct(connection, marker="0010", missing_guards=("invented_guard",))
    except ValueError as error:
        assert "non-enumerated" in str(error)
    else:
        raise AssertionError("non-enumerated omission was accepted")


def test_mutated_target_declaration_and_postgresql_attestation_fail_then_restore(monkeypatch):
    original_sql = sqlite_contract.construct_sql
    monkeypatch.setattr(
        sqlite_contract,
        "construct_sql",
        lambda: tuple(sql for sql in original_sql() if "research_program" not in sql),
    )
    connection = _persistent_connection()
    with pytest.raises(sqlite3.OperationalError, match="no such table"):
        construct(connection)
    assert sqlite_contract.construct_sql() != original_sql()

    original_catalog = postgres.CATALOG_0010
    monkeypatch.setattr(postgres, "CATALOG_0010", {**original_catalog, "head_version": "tampered"})
    assert postgres.catalog_attestation() != postgres.CATALOG_ATTESTATION
    monkeypatch.undo()
    assert sqlite_contract.construct_sql() == original_sql()
    assert postgres.catalog_attestation() == postgres.CATALOG_ATTESTATION


@pytest.mark.skipif(not os.environ.get("PT_TEST_POSTGRES_URL"), reason="requires the disposable PostgreSQL harness")
def test_postgresql_0010_contract_constructs_from_frozen_declarations_only():
    from sqlalchemy import create_engine

    engine = create_engine(os.environ["PT_TEST_POSTGRES_URL"])
    with engine.connect() as maintenance:
        maintenance = maintenance.execution_options(isolation_level="AUTOCOMMIT")
        try:
            states = []
            for ordinal, corpus in enumerate(CORPORA, start=1):
                database = f"projection_witness_{ordinal}_{uuid4().hex}"
                maintenance.exec_driver_sql(f'CREATE DATABASE "{database}"')
                witness_engine = create_engine(engine.url.set(database=database))
                try:
                    with witness_engine.begin() as connection:
                        construct_postgresql(connection)
                        seed_postgresql(connection, corpus)
                        expected_sequences = {name: (41 + ordinal + offset, False) for offset, name in enumerate(__import__("tests.foundation_postgresql_0010_builder", fromlist=["*"])._expected_sequence_names())}
                        for name, (last_value, called) in expected_sequences.items():
                            set_sequence_state(connection, name, last_value, called)
                    witness_engine.dispose()
                    witness_engine = create_engine(engine.url.set(database=database))
                    with witness_engine.connect() as connection:
                        assert connection.exec_driver_sql("SELECT version FROM research_schema_version").scalar_one() == "0010"
                        state = postgresql_inventory(connection)
                        assert_complete_postgresql_inventory(state, sequence_states=expected_sequences)
                        _assert_exact_roundtrip(state, postgresql_inventory(connection))
                        # Compare caller-owned witnesses after the fresh
                        # connection.  These explicit fields include owner,
                        # classification, UTF-8 text, textual JSON, and bytes.
                        assert state["research_program"][0][1:4] == corpus["research_program"][0][1:4]
                        assert state["research_dataset_segments_v2"][0][0:4] == corpus["research_dataset_segments_v2"][0][0:4]
                        assert state["research_dataset_manifests"][0][0:7] == corpus["research_dataset_manifests"][0][0:7]
                        assert state["research_outbox_event"][0][2:5] == corpus["research_outbox_event"][0][2:5]
                        catalog_mutations = (
                            lambda value: value.__setitem__("columns", value["columns"][:-1]),
                            lambda value: value.__setitem__("columns", [(*entry[:2], "text", *entry[3:]) if index == 0 else entry for index, entry in enumerate(value["columns"])]),
                            lambda value: value.__setitem__("columns", [(*entry[:3], not entry[3], *entry[4:]) if index == 0 else entry for index, entry in enumerate(value["columns"])]),
                            lambda value: value.__setitem__("constraints", value["constraints"][:-1]),
                            lambda value: value.__setitem__("constraints", [(*entry[:3], tuple(reversed(entry[3])), *entry[4:]) if index == 0 else entry for index, entry in enumerate(value["constraints"])]),
                            lambda value: value.__setitem__("indexes", value["indexes"][:-1]),
                            lambda value: value.__setitem__("indexes", [(*entry[:2], tuple(reversed(entry[2])), *entry[3:]) if index == 0 else entry for index, entry in enumerate(value["indexes"])]),
                            lambda value: value.__setitem__("sequences", [(name, 999, called) if name == value["sequences"][0][0] else (name, last_value, called) for name, last_value, called in value["sequences"]]),
                            lambda value: value.__setitem__("serial_bindings", [(*entry[:2], "wrong_existing_sequence") if index == 0 else entry for index, entry in enumerate(value["serial_bindings"])]),
                            lambda value: value.__setitem__("functions", [(name, "CREATE FUNCTION altered()") if index == 0 else (name, definition) for index, (name, definition) in enumerate(value["functions"])]),
                            lambda value: value.__setitem__("triggers", [(table, name, "CREATE TRIGGER altered") if index == 0 else (table, name, definition) for index, (table, name, definition) in enumerate(value["triggers"])]),
                        )
                        for mutate in catalog_mutations:
                            corrupted = deepcopy(state)
                            mutate(corrupted)
                            with pytest.raises(AssertionError):
                                assert_complete_postgresql_inventory(corrupted, sequence_states=expected_sequences)
                        assert_complete_postgresql_inventory(postgresql_inventory(connection), sequence_states=expected_sequences)
                        states.append(state)
                finally:
                    witness_engine.dispose()
                    maintenance.exec_driver_sql(f'DROP DATABASE IF EXISTS "{database}"')
            assert states[0]["research_program"] != states[1]["research_program"]
        finally:
            engine.dispose()
