"""PostgreSQL-to-PostgreSQL logical restore evidence.

This module deliberately does not call the SQLite copy verifier.  It reuses its
pure typed-digest and semantic primitives while keeping source and restored
PostgreSQL authorities read-only.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from typing import Callable, Iterable, Mapping

import sqlalchemy as sa
from sqlalchemy import Engine, MetaData, inspect, select, text
from sqlalchemy.engine import make_url

from app.db.copy_contract import (
    stream_table_summary,
    streamed_identity_set,
    validate_content_addresses,
    validate_postgresql_constraints,
    validate_semantic_ownership,
    validate_sequence_safety,
)
from research.guards import _search_path, assert_pairwise_database_authorities

MANIFEST_SCHEMA_VERSION = 1
_DIGEST = re.compile(r"^(?:sha256:)?[0-9a-f]{64}$")
_GENERATION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{7,127}$")
_SECRET_KEYS = frozenset({
    "password", "token", "secret", "credential", "ciphertext", "api_key",
    "access_token", "refresh_token", "connection_url", "database_url",
})
_MANIFEST_KEYS = frozenset({
    "schema_version", "generation_id", "created_at", "backup_started_at",
    "backup_completed_at", "source_build", "postgresql_major", "coherence",
    "planes", "cross_plane", "capabilities", "content_address", "signature",
})
_PLANE_KEYS = frozenset({
    "plane", "generation_id", "source_authority", "source_physical_authority",
    "schema", "marker_table", "schema_head", "table_inventory", "tables",
    "sequences", "state_counts", "content_addresses", "artifact",
})


class RestoreRefusal(RuntimeError):
    """The evidence cannot prove this restore safe to start."""


@dataclass(frozen=True)
class PostgreSQLRestorePlane:
    name: str
    url: str
    metadata: MetaData
    marker_table: str
    expected_head: str
    validate_current: Callable[[Engine], None]


def _without_envelope(manifest: Mapping[str, object]) -> dict[str, object]:
    body = dict(manifest)
    body.pop("content_address", None)
    body.pop("signature", None)
    return body


def _canonical_body(manifest: Mapping[str, object]) -> bytes:
    return json.dumps(_without_envelope(manifest), sort_keys=True,
                      separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def canonical_manifest(manifest: Mapping[str, object]) -> str:
    return json.dumps(dict(manifest), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False) + "\n"


def _reject_secret_shape(value: object, path: str = "manifest") -> None:
    if isinstance(value, Mapping):
        for raw_key, child in value.items():
            key = str(raw_key).lower()
            if key in _SECRET_KEYS or any(part in _SECRET_KEYS for part in re.split(r"[^a-z0-9]+", key)):
                raise RestoreRefusal(f"secret-bearing manifest field at {path}.{raw_key}")
            _reject_secret_shape(child, f"{path}.{raw_key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _reject_secret_shape(child, f"{path}[{index}]")
    elif isinstance(value, str) and "://" in value:
        raise RestoreRefusal(f"full authority URL is forbidden at {path}")


def validate_manifest(manifest: Mapping[str, object]) -> None:
    _reject_secret_shape(manifest)
    unknown = set(manifest) - _MANIFEST_KEYS
    if unknown:
        raise RestoreRefusal(f"unknown restore manifest fields: {sorted(unknown)}")
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise RestoreRefusal("unsupported restore manifest schema version")
    generation = manifest.get("generation_id")
    if not isinstance(generation, str) or not _GENERATION.fullmatch(generation):
        raise RestoreRefusal("invalid backup generation identity")
    coherence = manifest.get("coherence")
    if not isinstance(coherence, Mapping) or coherence.get("maintenance_quiesced") is not True:
        raise RestoreRefusal("three-plane backup generation was not quiesced")
    if not _DIGEST.fullmatch(str(coherence.get("evidence_address", ""))):
        raise RestoreRefusal("quiesced generation requires durable maintenance evidence")
    try:
        started = dt.datetime.fromisoformat(str(manifest["backup_started_at"]))
        completed = dt.datetime.fromisoformat(str(manifest["backup_completed_at"]))
        created = dt.datetime.fromisoformat(str(manifest["created_at"]))
    except Exception as exc:
        raise RestoreRefusal("manifest timestamps are invalid") from exc
    if completed < started or created < completed:
        raise RestoreRefusal("manifest backup timestamp ordering is invalid")
    planes = manifest.get("planes")
    if not isinstance(planes, list) or len(planes) != 3:
        raise RestoreRefusal("manifest must contain exactly three planes")
    names = [item.get("plane") for item in planes if isinstance(item, Mapping)]
    if set(names) != {"execution", "research", "ledger"} or len(names) != 3:
        raise RestoreRefusal("manifest contains an absent or duplicate plane")
    for plane in planes:
        if not isinstance(plane, Mapping):
            raise RestoreRefusal("invalid plane manifest")
        unknown_plane = set(plane) - _PLANE_KEYS
        if unknown_plane:
            raise RestoreRefusal(f"unknown plane manifest fields: {sorted(unknown_plane)}")
        if plane.get("generation_id") != generation:
            raise RestoreRefusal("mixed generation restore manifest")
        if not _DIGEST.fullmatch(str(plane.get("source_authority", ""))):
            raise RestoreRefusal("plane source authority is not redacted")
        if not _DIGEST.fullmatch(str(plane.get("source_physical_authority", ""))):
            raise RestoreRefusal("plane source physical authority is not redacted")
        inventory = plane.get("table_inventory")
        tables = plane.get("tables")
        if not isinstance(inventory, list) or not isinstance(tables, Mapping):
            raise RestoreRefusal("plane table evidence is absent")
        marker = plane.get("marker_table")
        payload_inventory = set(inventory) - ({str(marker)} if marker else set())
        if payload_inventory != set(tables):
            raise RestoreRefusal("plane table inventory does not bind table digests")
        artifact = plane.get("artifact")
        if not isinstance(artifact, Mapping) or not _DIGEST.fullmatch(str(artifact.get("sha256", ""))):
            raise RestoreRefusal("backup artifact digest is absent")


def finalize_manifest(manifest: Mapping[str, object], *,
                      signing_key: bytes | None = None) -> dict[str, object]:
    body = _without_envelope(manifest)
    validate_manifest(body)
    encoded = _canonical_body(body)
    address = "sha256:" + hashlib.sha256(encoded).hexdigest()
    if signing_key is None:
        signature = {"algorithm": "none", "status": "unsigned-development"}
    else:
        if len(signing_key) < 24:
            raise RestoreRefusal("operator signing key is too short")
        signature = {
            "algorithm": "hmac-sha256",
            "status": "signed",
            "key_id": hashlib.sha256(signing_key).hexdigest()[:16],
            "value": hmac.new(signing_key, encoded, hashlib.sha256).hexdigest(),
        }
    return {**body, "content_address": address, "signature": signature}


def verify_manifest_signature(manifest: Mapping[str, object], *, signing_key: bytes | None,
                              require_signed: bool) -> None:
    validate_manifest(manifest)
    encoded = _canonical_body(manifest)
    expected_address = "sha256:" + hashlib.sha256(encoded).hexdigest()
    if not hmac.compare_digest(str(manifest.get("content_address", "")), expected_address):
        raise RestoreRefusal("manifest content address is invalid")
    signature = manifest.get("signature")
    if not isinstance(signature, Mapping):
        raise RestoreRefusal("manifest signature envelope is absent")
    if signature.get("status") != "signed":
        if require_signed:
            raise RestoreRefusal("production restore approval requires a signed manifest")
        return
    if signing_key is None:
        raise RestoreRefusal("signed manifest requires the operator verification key")
    expected = hmac.new(signing_key, encoded, hashlib.sha256).hexdigest()
    if (signature.get("algorithm") != "hmac-sha256"
            or not hmac.compare_digest(str(signature.get("value", "")), expected)):
        raise RestoreRefusal("manifest signature is invalid")


def _safe_authority(url: str) -> tuple[str, str, str]:
    parsed = make_url(url)
    if parsed.get_backend_name() != "postgresql":
        raise RestoreRefusal("restore authority must be PostgreSQL")
    schema = _search_path(url)
    if not schema:
        raise RestoreRefusal("restore authority needs one explicit private search_path")
    physical = f"{parsed.host or 'local'}:{parsed.port or 5432}/{parsed.database or ''}"
    logical = f"{physical}/{schema[0]}"
    return (schema[0], "sha256:" + hashlib.sha256(logical.encode()).hexdigest(),
            "sha256:" + hashlib.sha256(physical.encode()).hexdigest())


def _group_counts(connection, table, column: str) -> dict[str, int]:
    if table is None or column not in table.c:
        return {}
    return {str(value): int(count) for value, count in connection.execute(
        select(table.c[column], sa.func.count()).group_by(table.c[column]))}


def _state_counts(connection, metadata: MetaData) -> dict[str, object]:
    tables = metadata.tables
    result: dict[str, object] = {}
    if "user_sessions" in tables:
        table = tables["user_sessions"]
        result["sessions"] = {
            "active": int(connection.scalar(select(sa.func.count()).select_from(table).where(
                table.c.revoked_at.is_(None))) or 0),
            "revoked": int(connection.scalar(select(sa.func.count()).select_from(table).where(
                table.c.revoked_at.is_not(None))) or 0),
        }
    for name, column in (
        ("account_execution_leases", "state"),
        ("account_execution_commands", "state"),
        ("backtest_runs", "status"),
        ("research_experiment_run", "status"),
        ("monitoring_assignments", "lifecycle_state"),
        ("monitoring_signal_reviews", "disposition"),
        ("monitoring_alert_delivery_attempts", "outcome"),
        ("platform_coupon_redemptions", "status"),
        ("platform_billing_event_receipts", "event_state"),
        ("platform_entitlement_events", "transition"),
        ("platform_current_entitlements", "state"),
        ("platform_complimentary_entitlement_grants", "action"),
        ("platform_support_requests", "status"),
        ("platform_operator_audit_events", "outcome"),
    ):
        if name in tables:
            result[name] = _group_counts(connection, tables[name], column)
    if "ir_v2_editor_presentations" in tables:
        table = tables["ir_v2_editor_presentations"]
        result["ir_v2_editor_presentations"] = {
            "rows": int(connection.scalar(select(sa.func.count()).select_from(table)) or 0),
            "max_revision": int(connection.scalar(select(sa.func.max(table.c.revision))) or 0),
        }
    if "chart_context_annotations" in tables:
        table = tables["chart_context_annotations"]
        result["chart_context_annotations"] = {
            "rows": int(connection.scalar(select(sa.func.count()).select_from(table)) or 0),
            "max_revision": int(connection.scalar(select(sa.func.max(table.c.revision))) or 0),
        }
    for name in sorted(tables):
        if any(part in name for part in ("outbox_event", "outbox_consumer_cursor",
                                         "outbox_consumer_receipt")):
            result[name] = int(connection.scalar(
                select(sa.func.count()).select_from(tables[name])) or 0)
    return result


def _content_summary(connection, metadata: MetaData) -> list[dict[str, object]]:
    evidence = []
    for table_name, column_name in (
        ("graph_versions", "content_address"),
        ("project_review_snapshots", "content_address"),
        ("research_experiment_spec", "id"),
        ("backtest_computations", "payload_digest"),
        ("monitoring_state_snapshots", "snapshot_address"),
        ("monitoring_signal_events", "content_address"),
        ("monitoring_signal_alerts", "alert_address"),
        ("monitoring_alert_delivery_attempts", "attempt_address"),
        ("monitoring_alert_attention_events", "attention_event_address"),
        ("monitoring_alert_attention_state", "projection_address"),
        ("monitoring_signal_reviews", "review_address"),
        ("platform_plan_versions", "entitlement_set_address"),
        ("platform_coupon_definitions", "policy_address"),
        ("platform_billing_event_receipts", "raw_body_digest"),
        ("platform_entitlement_events", "policy_address"),
        ("platform_complimentary_entitlement_grants", "policy_address"),
        ("platform_analytics_subjects", "pseudonym_digest"),
        ("platform_operator_bindings", "bootstrap_evidence_address"),
    ):
        table = metadata.tables.get(table_name)
        if table is None or column_name not in table.c:
            continue
        values = sorted(str(value) for value in connection.scalars(select(table.c[column_name])))
        evidence.append({
            "table": table_name, "count": len(values),
            "set_digest": hashlib.sha256("\n".join(values).encode()).hexdigest(),
        })
    presentation = metadata.tables.get("ir_v2_editor_presentations")
    if presentation is not None:
        values = sorted(str(value) for value in connection.scalars(
            select(presentation.c.presentation_json)))
        evidence.append({
            "table": "ir_v2_editor_presentations", "count": len(values),
            "set_digest": hashlib.sha256("\n".join(values).encode()).hexdigest(),
        })
    annotations = metadata.tables.get("chart_context_annotations")
    if annotations is not None:
        values = sorted("\x1f".join(str(item) for item in row) for row in connection.execute(
            select(annotations.c.owner_id, annotations.c.market_context_address,
                   annotations.c.annotation_id, annotations.c.revision,
                   annotations.c.geometry_address, annotations.c.geometry_json,
                   annotations.c.applicability_address, annotations.c.applicability_json)))
        evidence.append({
            "table": "chart_context_annotations", "count": len(values),
            "set_digest": hashlib.sha256("\n".join(values).encode()).hexdigest(),
        })
    return evidence


def _marker_head(connection, plane: PostgreSQLRestorePlane) -> str:
    marker = sa.Table(plane.marker_table, sa.MetaData(), autoload_with=connection)
    column = marker.c.get("version_num")
    if column is None:
        column = marker.c.get("version")
    if column is None:
        raise RestoreRefusal(f"{plane.name} marker has no version column")
    rows = connection.execute(select(column)).scalars().all()
    if rows != [plane.expected_head]:
        raise RestoreRefusal(f"{plane.name} schema head is not current")
    return str(rows[0])


def _plane_evidence(plane: PostgreSQLRestorePlane, *, generation_id: str,
                    artifact: Mapping[str, object], batch_size: int) -> dict[str, object]:
    schema, authority, physical_authority = _safe_authority(plane.url)
    engine = sa.create_engine(plane.url, future=True, pool_pre_ping=True)
    try:
        plane.validate_current(engine)
        with engine.connect() as connection:
            expected_inventory = set(plane.metadata.tables) | {plane.marker_table}
            actual_inventory = set(inspect(connection).get_table_names())
            if actual_inventory != expected_inventory:
                raise RestoreRefusal(f"{plane.name} contains an unexpected table inventory")
            validate_semantic_ownership(connection, plane.metadata)
            validate_content_addresses(connection, plane.metadata)
            validate_postgresql_constraints(connection)
            tables = {table.name: stream_table_summary(connection, table, batch_size=batch_size)
                      for table in plane.metadata.sorted_tables}
            return {
                "plane": plane.name, "generation_id": generation_id,
                "source_authority": authority,
                "source_physical_authority": physical_authority, "schema": schema,
                "marker_table": plane.marker_table,
                "schema_head": _marker_head(connection, plane),
                "table_inventory": sorted(actual_inventory), "tables": tables,
                "sequences": validate_sequence_safety(connection, plane.metadata),
                "state_counts": _state_counts(connection, plane.metadata),
                "content_addresses": _content_summary(connection, plane.metadata),
                "artifact": {"identifier": str(artifact["identifier"]),
                             "sha256": str(artifact["sha256"])},
            }
    except RestoreRefusal:
        raise
    except Exception as exc:
        raise RestoreRefusal(f"{plane.name} current PostgreSQL validation failed") from exc
    finally:
        engine.dispose()


def _identity_digest(values: set[bytes]) -> str:
    return hashlib.sha256(b"".join(sorted(values))).hexdigest()


def _cross_plane(planes: Mapping[str, PostgreSQLRestorePlane]) -> dict[str, str]:
    engines = {name: sa.create_engine(plane.url, future=True, pool_pre_ping=True)
               for name, plane in planes.items()}
    try:
        with (engines["execution"].connect() as execution,
              engines["research"].connect() as research,
              engines["ledger"].connect() as ledger):
            execution_meta = planes["execution"].metadata
            research_meta = planes["research"].metadata
            ledger_meta = planes["ledger"].metadata
            organizations = streamed_identity_set(
                execution, execution_meta.tables["organizations"], ("organization_id",))
            accounts = streamed_identity_set(
                execution, execution_meta.tables["broker_accounts"],
                ("owner_id", "broker_account_id"))
            research_owners: set[bytes] = set()
            for table in research_meta.sorted_tables:
                if "owner_id" in table.c:
                    research_owners |= streamed_identity_set(research, table, ("owner_id",))
            ledger_pairs: set[bytes] = set()
            for table in ledger_meta.sorted_tables:
                if {"owner_id", "broker_account_id"} <= set(table.c):
                    ledger_pairs |= streamed_identity_set(
                        ledger, table, ("owner_id", "broker_account_id"))
            if not research_owners <= organizations:
                raise RestoreRefusal("research owner has no execution organization")
            if not ledger_pairs <= accounts:
                raise RestoreRefusal("ledger owner/account has no execution broker account")
            return {
                "execution_organizations": _identity_digest(organizations),
                "execution_owner_accounts": _identity_digest(accounts),
                "research_owners": _identity_digest(research_owners),
                "ledger_owner_accounts": _identity_digest(ledger_pairs),
            }
    finally:
        for engine in engines.values():
            engine.dispose()


def capture_manifest(planes: Iterable[PostgreSQLRestorePlane], *, generation_id: str,
                     source_build: str, artifacts: Mapping[str, Mapping[str, object]],
                     maintenance_evidence: Mapping[str, object],
                     backup_started_at: dt.datetime, backup_completed_at: dt.datetime,
                     signing_key: bytes | None = None, batch_size: int = 500) -> dict[str, object]:
    by_name = {plane.name: plane for plane in planes}
    if set(by_name) != {"execution", "research", "ledger"}:
        raise RestoreRefusal("capture requires execution, research and ledger planes")
    assert_pairwise_database_authorities(*(by_name[name].url for name in
                                           ("execution", "research", "ledger")))
    if maintenance_evidence.get("quiesced") is not True:
        raise RestoreRefusal("backup capture requires explicit quiesced maintenance evidence")
    evidence_address = str(maintenance_evidence.get("evidence_address", ""))
    if not _DIGEST.fullmatch(evidence_address):
        raise RestoreRefusal("backup capture requires durable maintenance evidence address")
    evidence = [_plane_evidence(by_name[name], generation_id=generation_id,
                                artifact=artifacts[name], batch_size=batch_size)
                for name in ("execution", "research", "ledger")]
    major = 0
    engine = sa.create_engine(by_name["execution"].url, future=True)
    try:
        with engine.connect() as connection:
            major = int(str(connection.scalar(text("SHOW server_version_num")))[:2])
    finally:
        engine.dispose()
    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "generation_id": generation_id,
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "backup_started_at": backup_started_at.isoformat(),
        "backup_completed_at": backup_completed_at.isoformat(),
        "source_build": source_build,
        "postgresql_major": major,
        "coherence": {"maintenance_quiesced": True,
                      "mode": "three-plane-maintenance",
                      "evidence_address": evidence_address},
        "planes": evidence,
        "cross_plane": _cross_plane(by_name),
        "capabilities": {"logical_restore": "PROVEN", "managed_pitr": "UNPROVEN",
                         "geographic_failover": "UNPROVEN", "production_rpo_rto": "UNMEASURED"},
    }
    return finalize_manifest(manifest, signing_key=signing_key)


def verify_restore(planes: Iterable[PostgreSQLRestorePlane], manifest: Mapping[str, object], *,
                   signing_key: bytes | None = None, require_signed: bool = False,
                   batch_size: int = 500) -> dict[str, object]:
    verify_manifest_signature(manifest, signing_key=signing_key, require_signed=require_signed)
    by_name = {plane.name: plane for plane in planes}
    if set(by_name) != {"execution", "research", "ledger"}:
        raise RestoreRefusal("restore verification requires three targets")
    assert_pairwise_database_authorities(*(by_name[name].url for name in
                                           ("execution", "research", "ledger")))
    expected = {item["plane"]: item for item in manifest["planes"]}
    actual = []
    generation = str(manifest["generation_id"])
    for name in ("execution", "research", "ledger"):
        _schema, authority, physical_authority = _safe_authority(by_name[name].url)
        if (authority == expected[name]["source_authority"]
                or physical_authority == expected[name]["source_physical_authority"]):
            raise RestoreRefusal("source and target authority overlap")
        observed = _plane_evidence(by_name[name], generation_id=generation,
                                   artifact=expected[name]["artifact"], batch_size=batch_size)
        comparable = dict(observed)
        comparable["source_authority"] = expected[name]["source_authority"]
        comparable["source_physical_authority"] = expected[name]["source_physical_authority"]
        if comparable != expected[name]:
            raise RestoreRefusal(f"{name} restored digest or sequence evidence differs")
        actual.append({"plane": name, "target_authority": authority,
                       "verified": True})
    cross = _cross_plane(by_name)
    if cross != manifest.get("cross_plane"):
        raise RestoreRefusal("cross-plane restored identity evidence differs")
    completed = dt.datetime.now(dt.timezone.utc).isoformat()
    report = {
        "schema_version": 1, "generation_id": generation,
        "manifest_content_address": manifest["content_address"],
        "completed_at": completed, "planes": actual,
        "cross_plane_verified": True,
        "execution_recovery_required": True,
        "cutover_ready": True,
    }
    encoded = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    report["content_address"] = "sha256:" + hashlib.sha256(encoded).hexdigest()
    return report


def configured_restore_planes(*, execution_url: str, research_url: str,
                              ledger_url: str) -> list[PostgreSQLRestorePlane]:
    from app.db import migrate
    from app.db.models import Base
    from app.ledger import models as _ledger_models  # noqa: F401
    from app.ledger.db import HEAD_VERSION as LEDGER_HEAD, LedgerBase, VERSION_TABLE as LEDGER_MARKER
    from app.db.plane_schema import validate_postgresql_plane
    from research.domain import models as _research_models  # noqa: F401
    from research.domain.base import ResearchBase
    from research.domain.migrate import (HEAD_VERSION as RESEARCH_HEAD,
                                         VERSION_TABLE as RESEARCH_MARKER,
                                         _validate_postgresql as validate_research)

    def validate_execution(engine: Engine) -> None:
        if migrate.schema_version(engine) != migrate.head_revision():
            raise RestoreRefusal("execution PostgreSQL target is not at head")
        migrate._validate_current_schema(engine, Base.metadata.tables)
        migrate._validate_postgresql_immutable_triggers(engine)

    def validate_research_engine(engine: Engine) -> None:
        with engine.connect() as connection:
            validate_research(connection)

    def validate_ledger_engine(engine: Engine) -> None:
        with engine.connect() as connection:
            validate_postgresql_plane(connection, LedgerBase.metadata,
                                      marker_table=LEDGER_MARKER, plane="ledger")

    return [
        PostgreSQLRestorePlane("execution", execution_url, Base.metadata,
                               "alembic_version", migrate.head_revision(), validate_execution),
        PostgreSQLRestorePlane("research", research_url, ResearchBase.metadata,
                               RESEARCH_MARKER, RESEARCH_HEAD, validate_research_engine),
        PostgreSQLRestorePlane("ledger", ledger_url, LedgerBase.metadata,
                               LEDGER_MARKER, LEDGER_HEAD, validate_ledger_engine),
    ]
