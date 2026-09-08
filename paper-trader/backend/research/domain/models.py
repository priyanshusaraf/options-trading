"""Research-plane domain model (the ledger of research).

The spine: `ResearchProgram` (long-lived initiative) -> `Hypothesis` (an explicit
thesis carrying the re-test priority) -> `ExperimentSpec` (an IMMUTABLE, content-
hashed recipe) -> `ExperimentRun` (its mutable execution). `Finding` is the
revisable-knowledge layer (negative evidence is first-class, confidence is
monotone-in-evidence and never decays). `PromotionCandidate` is the human-gated
bridge toward production.

Immutability of `ExperimentSpec` is enforced at the DB layer via SQLite triggers
(`RAISE(ABORT)` on UPDATE/DELETE) so it holds even against a stray CLI write, not
just in-process ORM discipline. Later stages (OptimizationTrial, EvaluationResult,
ValidationResult) will reuse `_make_immutable`.
"""
from __future__ import annotations

import datetime as dt
import json

from sqlalchemy import (
    DDL,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKeyConstraint,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    event,
    insert,
    select,
    text,
)
from sqlalchemy import Index
from sqlalchemy.engine import Engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.dml import Insert
from sqlalchemy.schema import Table

from research.domain.base import ResearchBase


class _ContentAddress(ColumnElement):
    """Portable strict ``sha256:<64 lowercase hex>`` validation."""

    type = Boolean()
    inherit_cache = True

    def __init__(self, column_name: str):
        self.column_name = column_name


@compiles(_ContentAddress, "sqlite")
def _compile_content_address_sqlite(element, _compiler, **_kw):
    name = element.column_name
    return (f"length({name}) = 71 AND substr({name}, 1, 7) = 'sha256:' AND "
            f"substr({name}, 8) = lower(substr({name}, 8)) AND "
            f"substr({name}, 8) NOT GLOB '*[^0-9a-f]*'")


@compiles(_ContentAddress, "postgresql")
def _compile_content_address_postgresql(element, _compiler, **_kw):
    return f"{element.column_name} ~ '^sha256:[0-9a-f]{{64}}$'"


class _NullableContentAddress(_ContentAddress):
    """Allow a legacy NULL but reject malformed receipt keys."""


@compiles(_NullableContentAddress, "sqlite")
def _compile_nullable_content_address_sqlite(element, _compiler, **_kw):
    return (f"{element.column_name} IS NULL OR "
            f"({_compile_content_address_sqlite(element, _compiler, **_kw)})")


@compiles(_NullableContentAddress, "postgresql")
def _compile_nullable_content_address_postgresql(element, _compiler, **_kw):
    return (f"{element.column_name} IS NULL OR "
            f"({_compile_content_address_postgresql(element, _compiler, **_kw)})")


class _JsonObject(ColumnElement):
    """Portable strict top-level JSON object validation."""

    type = Boolean()
    inherit_cache = True

    def __init__(self, column_name: str):
        self.column_name = column_name


@compiles(_JsonObject, "sqlite")
def _compile_json_object_sqlite(element, _compiler, **_kw):
    name = element.column_name
    return (f"json_valid({name}) AND CASE WHEN json_valid({name}) "
            f"THEN json_type({name}) = 'object' ELSE 0 END")


@compiles(_JsonObject, "postgresql")
def _compile_json_object_postgresql(element, _compiler, **_kw):
    return f"jsonb_typeof({element.column_name}::jsonb) = 'object'"


class _JsonArray(ColumnElement):
    """Portable strict top-level JSON array validation."""

    type = Boolean()
    inherit_cache = True

    def __init__(self, column_name: str):
        self.column_name = column_name


@compiles(_JsonArray, "sqlite")
def _compile_json_array_sqlite(element, _compiler, **_kw):
    name = element.column_name
    return (f"json_valid({name}) AND CASE WHEN json_valid({name}) "
            f"THEN json_type({name}) = 'array' ELSE 0 END")


@compiles(_JsonArray, "postgresql")
def _compile_json_array_postgresql(element, _compiler, **_kw):
    return f"jsonb_typeof({element.column_name}::jsonb) = 'array'"


class _SecretFreeJson(ColumnElement):
    """Reject credential-bearing keys from persisted dataset provenance."""

    type = Boolean()
    inherit_cache = True

    def __init__(self, column_name: str):
        self.column_name = column_name


@compiles(_SecretFreeJson, "sqlite")
def _compile_secret_free_json_sqlite(element, _compiler, **_kw):
    return " AND ".join(
        f"instr(lower({element.column_name}), '{term}') = 0"
        for term in ("token", "secret", "password", "api_key", "credential", "authorization")
    )


@compiles(_SecretFreeJson, "postgresql")
def _compile_secret_free_json_postgresql(element, _compiler, **_kw):
    return f"NOT phase4_json_has_secret_key({element.column_name}::jsonb)"


_SECRET_KEY_PARTS = ("token", "secret", "password", "api_key", "credential", "authorization")


def _canonical_secret_free_document(value: str, *, label: str) -> dict:
    """Decode persisted JSON once so escaped credential keys cannot evade policy."""
    from app.ir.hashing import canonical_json

    try:
        document = json.loads(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be valid canonical JSON") from exc
    if not isinstance(document, dict) or canonical_json(document) != value:
        raise ValueError(f"{label} must be canonical JSON object bytes")

    def visit(node: object) -> None:
        if isinstance(node, dict):
            for key, child in node.items():
                if any(part in key.lower() for part in _SECRET_KEY_PARTS):
                    raise ValueError(f"{label} must not contain credential-bearing keys")
                visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)

    visit(document)
    return document


def _manifest_document_matches_columns(document: dict, values: dict) -> None:
    required = ("owner_id", "provider", "dataset_version", "market_truth_digest", "capability_digest")
    if document.get("schema_version") != 1:
        raise ValueError("dataset manifest_json schema_version must be 1")
    for name in required:
        if document.get(name) != values[name]:
            raise ValueError(f"dataset manifest_json {name} does not match column")


def _dataset_manifest_core_identity_guard(values: dict) -> None:
    """Apply the manifest identity contract to controlled SQLAlchemy Core writes."""
    from app.ir.hashing import content_address

    document = _canonical_secret_free_document(values["manifest_json"], label="dataset manifest_json")
    _manifest_document_matches_columns(document, values)
    if content_address(document) != values["digest"]:
        raise ValueError("dataset manifest digest does not match manifest_json")


def _insert_rows_with_inline_values(clauseelement, multiparams, params) -> list[dict]:
    normalize = lambda values: {
        getattr(column, "key", column): getattr(value, "value", value)
        for column, value in values.items()
    }
    multi_values = [
        normalize(row)
        for group in (getattr(clauseelement, "_multi_values", None) or ())
        for row in group
    ]
    inline = {
        getattr(column, "key", column): getattr(value, "value", value)
        for column, value in (getattr(clauseelement, "_values", None) or {}).items()
    }
    supplied = multiparams or ([params] if params else [])
    if multi_values:
        return multi_values
    if supplied:
        return [{**inline, **dict(row)} for row in supplied]
    return [inline] if inline else []


class _JsonTextMatchesColumn(ColumnElement):
    type = Boolean()
    inherit_cache = True

    def __init__(self, json_column: str, json_key: str, column_name: str):
        self.json_column = json_column
        self.json_key = json_key
        self.column_name = column_name


@compiles(_JsonTextMatchesColumn, "sqlite")
def _compile_json_text_matches_column_sqlite(element, _compiler, **_kw):
    return (f"json_extract({element.json_column}, '$.{element.json_key}') "
            f"IS {element.column_name}")


@compiles(_JsonTextMatchesColumn, "postgresql")
def _compile_json_text_matches_column_postgresql(element, _compiler, **_kw):
    field = f"({element.json_column}::jsonb -> '{element.json_key}')"
    return (f"{field} IS NOT NULL AND jsonb_typeof({element.json_column}::jsonb "
            f"-> '{element.json_key}') = 'string' AND "
            f"({element.json_column}::jsonb ->> '{element.json_key}') = {element.column_name}")


class _JsonNumberEquals(ColumnElement):
    type = Boolean()
    inherit_cache = True

    def __init__(self, json_column: str, json_key: str, column_name: str):
        self.json_column = json_column
        self.json_key = json_key
        self.column_name = column_name


@compiles(_JsonNumberEquals, "sqlite")
def _compile_json_number_equals_sqlite(element, _compiler, **_kw):
    return (f"json_extract({element.json_column}, '$.{element.json_key}') "
            f"IS {element.column_name}")


@compiles(_JsonNumberEquals, "postgresql")
def _compile_json_number_equals_postgresql(element, _compiler, **_kw):
    field = f"({element.json_column}::jsonb -> '{element.json_key}')"
    return (f"{field} IS NOT NULL AND jsonb_typeof({element.json_column}::jsonb "
            f"-> '{element.json_key}') = 'number' AND "
            f"(({field} #>> '{{}}')::numeric) = {element.column_name}::numeric")


def _make_immutable(table: Table, *, sqlstate: str | None = None) -> None:
    """Attach BEFORE UPDATE/DELETE triggers that abort any mutation of `table`,
    created alongside the table itself. DB-enforced, client-agnostic."""
    for op in ("UPDATE", "DELETE"):
        trg = f"trg_{table.name}_no_{op.lower()}"
        event.listen(
            table, "after_create",
            DDL(f"CREATE TRIGGER IF NOT EXISTS {trg} BEFORE {op} ON {table.name} "
                f"BEGIN SELECT RAISE(ABORT, '{table.name} is immutable'); END")
            .execute_if(dialect="sqlite"))
    function = f"{table.name}_refuse_mutation"
    event.listen(
        table, "after_create",
        DDL(
            f"CREATE OR REPLACE FUNCTION {function}() RETURNS trigger AS $$ "
            f"BEGIN RAISE EXCEPTION '{table.name} is immutable'"
            f"{f' USING ERRCODE = {sqlstate!r}' if sqlstate else ''}; END; "
            "$$ LANGUAGE plpgsql"
        ).execute_if(dialect="postgresql"),
    )
    event.listen(
        table, "after_create",
        DDL(
            f"CREATE TRIGGER {function} BEFORE UPDATE OR DELETE ON {table.name} "
            f"FOR EACH ROW EXECUTE FUNCTION {function}()"
        ).execute_if(dialect="postgresql"),
    )


class ResearchProgram(ResearchBase):
    """A long-lived research initiative (e.g. Trend Following, Mean Reversion)."""
    __tablename__ = "research_program"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(80))
    thesis: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(12), default="active")  # active|paused|archived
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now)
    __table_args__ = (
        UniqueConstraint("owner_id", "id", name="uq_research_program_owner_id"),
        UniqueConstraint("owner_id", "name", name="uq_research_program_owner_name"),
        Index("ix_research_program_owner_name", "owner_id", "name"),
    )


class ResearchOperation(ResearchBase):
    """Durable, tenant-local authority for a bounded research workload."""
    __tablename__ = "research_operation"
    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    operation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    trigger: Mapped[str] = mapped_column(String(24), nullable=False)
    plan_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    preparation_evidence_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    stage: Mapped[str] = mapped_column(String(24), nullable=False, default="startup")
    error_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    build: Mapped[str] = mapped_column(String(40), nullable=False, default="unknown")
    provider_mode: Mapped[str] = mapped_column(String(80), nullable=False, default="unknown")
    completed_run_ids_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, default=dt.datetime.now)
    queued_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, default=dt.datetime.now)
    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    heartbeat_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    claim_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    claimed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    claim_expires_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cancel_requested_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    __table_args__ = (
        Index("ix_research_operation_owner_latest", "owner_id", "created_at", "operation_id"),
        Index("ix_research_operation_owner_status", "owner_id", "status", "queued_at"),
        Index("ix_research_operation_claim_expiry", "claim_expires_at"),
    )


class ResearchOperationItem(ResearchBase):
    """One replay boundary in a durable research operation.

    Experiment execution is not assumed to be interruptible mid-call.  A worker
    checkpoints only *between* items, under the operation's lease fence, so a
    reclaimed operation can skip an already recorded run without inventing a
    second completion receipt.
    """
    __tablename__ = "research_operation_item"
    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    operation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    item_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    __table_args__ = (
        ForeignKeyConstraint(
            ("owner_id", "operation_id"),
            ("research_operation.owner_id", "research_operation.operation_id"),
        ),
        # A durable receipt may only name an ExperimentRun owned by the same
        # tenant.  The unique pair makes a run belong to exactly one operation
        # item; a replay can therefore resume/refuse the already-bound run
        # without inventing a second run for the same work item.
        ForeignKeyConstraint(
            ("owner_id", "run_id"),
            ("research_experiment_run.owner_id", "research_experiment_run.id"),
        ),
        UniqueConstraint("owner_id", "operation_id", "ordinal",
                         name="uq_research_operation_item_ordinal"),
        UniqueConstraint("owner_id", "run_id",
                         name="uq_research_operation_item_run"),
        CheckConstraint(
            "status IN ('pending', 'running', 'completed')",
            name="ck_research_operation_item_status",
        ),
        CheckConstraint(
            "(status = 'pending' AND run_id IS NULL AND completed_at IS NULL) OR "
            "(status = 'running' AND run_id IS NOT NULL AND completed_at IS NULL) OR "
            "(status = 'completed' AND run_id IS NOT NULL AND completed_at IS NOT NULL)",
            name="ck_research_operation_item_receipt_state",
        ),
        Index("ix_research_operation_item_cursor", "owner_id", "operation_id", "ordinal"),
    )


class ResearchOperationEvent(ResearchBase):
    """Bounded, owner-local evidence of scheduler authority and progress."""
    __tablename__ = "research_operation_event"
    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    operation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    sequence: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    stage: Mapped[str | None] = mapped_column(String(24), nullable=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, default=dt.datetime.now)
    __table_args__ = (
        ForeignKeyConstraint(
            ("owner_id", "operation_id"),
            ("research_operation.owner_id", "research_operation.operation_id"),
        ),
        CheckConstraint(
            "event_type IN ('claimed', 'heartbeat', 'stage', 'item_completed', "
            "'takeover', 'completed', 'failed', 'cancelled')",
            name="ck_research_operation_event_type",
        ),
        CheckConstraint(
            "stage IS NULL OR stage IN ('startup', 'planning', 'collection', "
            "'experiments', 'reports', 'generation', 'completed')",
            name="ck_research_operation_event_stage",
        ),
        Index("ix_research_operation_event_owner_operation_latest",
              "owner_id", "operation_id", "sequence"),
    )


class Hypothesis(ResearchBase):
    """An explicit thesis under a Program. Research always begins here. Carries the
    re-test priority — the quantity that *decays upward* over time so a killed idea
    is eventually revisited (floor > 0: never permanently banned; cap: never thrash)."""
    __tablename__ = "research_hypothesis"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False)
    program_id: Mapped[int] = mapped_column(Integer)
    statement: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(12), default="open")  # open|supported|rejected|dormant
    retest_priority: Mapped[float] = mapped_column(Float, default=1.0)
    last_tested_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now)
    __table_args__ = (
        UniqueConstraint("owner_id", "id", name="uq_research_hypothesis_owner_id"),
        ForeignKeyConstraint(
            ("owner_id", "program_id"),
            ("research_program.owner_id", "research_program.id"),
        ),
        Index("ix_research_hypothesis_owner_program", "owner_id", "program_id"),
        Index("ix_research_hypothesis_owner_program_statement", "owner_id", "program_id", "statement"),
    )


class ExperimentSpec(ResearchBase):
    """IMMUTABLE, content-hashed recipe for one reproducible experiment. `id` is the
    content hash; the same idea re-run under new code is a new *Run* against this
    same Spec. Provenance (git_commit + rule-set versions + seed) makes any result
    interpretable and reproducible."""
    __tablename__ = "research_experiment_spec"
    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # content hash
    hypothesis_id: Mapped[int] = mapped_column(Integer)
    parent_spec_id: Mapped[str | None] = mapped_column(String(64), nullable=True)  # lineage
    recipe_json: Mapped[str] = mapped_column(Text, default="{}")  # definitions, datasets, budgets
    git_commit: Mapped[str] = mapped_column(String(40), default="")
    qualifier_version: Mapped[str] = mapped_column(String(24), default="")
    optimizer_version: Mapped[str] = mapped_column(String(24), default="")
    validator_version: Mapped[str] = mapped_column(String(24), default="")
    scoring_version: Mapped[str] = mapped_column(String(24), default="")
    rng_seed: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now)
    __table_args__ = (
        ForeignKeyConstraint(
            ("owner_id", "hypothesis_id"),
            ("research_hypothesis.owner_id", "research_hypothesis.id"),
        ),
        ForeignKeyConstraint(
            ("owner_id", "parent_spec_id"),
            ("research_experiment_spec.owner_id", "research_experiment_spec.id"),
        ),
        Index("ix_research_experiment_spec_owner_hypothesis", "owner_id", "hypothesis_id"),
        Index("ix_research_experiment_spec_owner_parent", "owner_id", "parent_spec_id"),
    )


_make_immutable(ExperimentSpec.__table__)


class ResearchIrV2GraphVersion(ResearchBase):
    """Research-plane immutable evidence for one canonical Component IR v2 graph."""

    __tablename__ = "research_ir_v2_graph_versions"
    __table_args__ = (
        CheckConstraint("graph_version >= 1",
                        name="ck_research_ir_v2_graph_versions_version"),
        CheckConstraint("format_version = 2",
                        name="ck_research_ir_v2_graph_versions_format"),
        CheckConstraint(_JsonObject("artifact_json"),
                        name="ck_research_ir_v2_graph_versions_valid_json"),
        CheckConstraint(_JsonTextMatchesColumn(
            "artifact_json", "strategy_id", "graph_identifier"),
            name="ck_research_ir_v2_graph_versions_identifier_matches_json"),
        CheckConstraint(_JsonNumberEquals(
            "artifact_json", "strategy_version", "graph_version"),
            name="ck_research_ir_v2_graph_versions_version_matches_json"),
        CheckConstraint(_ContentAddress("content_address"),
                        name="ck_research_ir_v2_graph_versions_content_address"),
        CheckConstraint(_ContentAddress("graph_address"),
                        name="ck_research_ir_v2_graph_versions_graph_address"),
        CheckConstraint(_ContentAddress("registry_snapshot_address"),
                        name="ck_research_ir_v2_graph_versions_registry_address"),
        Index("ix_research_ir_v2_graph_versions_content_address", "content_address"),
        Index("ix_research_ir_v2_graph_versions_graph_address", "graph_address"),
    )

    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    graph_identifier: Mapped[str] = mapped_column(String(128), primary_key=True)
    graph_version: Mapped[int] = mapped_column(Integer, primary_key=True)
    artifact_json: Mapped[str] = mapped_column(Text, nullable=False)
    format_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=2, server_default=text("2"))
    content_address: Mapped[str] = mapped_column(String(71), nullable=False)
    graph_address: Mapped[str] = mapped_column(String(71), nullable=False)
    registry_snapshot_address: Mapped[str] = mapped_column(String(71), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, nullable=False, default=dt.datetime.now)


@event.listens_for(ResearchIrV2GraphVersion, "before_insert")
def _research_ir_v2_graph_before_insert(_mapper, _connection, target) -> None:
    from app.ir.v2_graph_versions import facts_from_row

    facts_from_row(target)


@event.listens_for(ResearchIrV2GraphVersion, "before_update")
@event.listens_for(ResearchIrV2GraphVersion, "before_delete")
def _research_ir_v2_graph_mutation_refused(_mapper, _connection, _target) -> None:
    raise ValueError("research IR v2 graph versions are immutable")


_make_immutable(ResearchIrV2GraphVersion.__table__, sqlstate="55000")


class ResearchStrategyAdmission(ResearchBase):
    """One immutable owner-scoped Phase 3 causal-admission receipt.

    The research plane records evidence only. An address here is never execution
    authority and cannot share a session, model, or foreign key with execution
    persistence.
    """

    __tablename__ = "research_strategy_admission"
    __table_args__ = (
        CheckConstraint(_ContentAddress("admission_address"),
                        name="ck_research_strategy_admission_address_format"),
        CheckConstraint(_ContentAddress("graph_address"),
                        name="ck_research_strategy_admission_graph_address_format"),
        CheckConstraint("graph_version >= 1",
                        name="ck_research_strategy_admission_graph_version"),
        CheckConstraint(_JsonObject("artifact_json"),
                        name="ck_research_strategy_admission_valid_json"),
        CheckConstraint(_JsonTextMatchesColumn("artifact_json", "owner_id", "owner_id"),
                        name="ck_research_strategy_admission_owner_matches_json"),
        CheckConstraint(_JsonTextMatchesColumn(
            "artifact_json", "graph_identifier", "graph_identifier"),
            name="ck_research_strategy_admission_graph_identifier_matches_json"),
        CheckConstraint(_JsonNumberEquals("artifact_json", "graph_version", "graph_version"),
                        name="ck_research_strategy_admission_graph_version_matches_json"),
        CheckConstraint(_JsonTextMatchesColumn("artifact_json", "graph_address", "graph_address"),
                        name="ck_research_strategy_admission_graph_address_matches_json"),
        CheckConstraint(_JsonTextMatchesColumn("artifact_json", "scheme", "scheme"),
                        name="ck_research_strategy_admission_scheme_matches_json"),
        CheckConstraint(_JsonTextMatchesColumn("artifact_json", "contract_suite", "contract_suite"),
                        name="ck_research_strategy_admission_contract_suite_matches_json"),
        CheckConstraint(_JsonTextMatchesColumn("artifact_json", "parity_suite", "parity_suite"),
                        name="ck_research_strategy_admission_parity_suite_matches_json"),
        UniqueConstraint("owner_id", "graph_identifier", "graph_version", "admission_address",
                         name="uq_research_strategy_admission_owner_graph_address"),
    )

    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    admission_address: Mapped[str] = mapped_column(String(71), primary_key=True)
    graph_identifier: Mapped[str] = mapped_column(String(128), nullable=False)
    graph_version: Mapped[int] = mapped_column(Integer, nullable=False)
    graph_address: Mapped[str] = mapped_column(String(71), nullable=False)
    artifact_json: Mapped[str] = mapped_column(Text, nullable=False)
    scheme: Mapped[str] = mapped_column(String(32), nullable=False)
    contract_suite: Mapped[str] = mapped_column(String(32), nullable=False)
    parity_suite: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, nullable=False, default=dt.datetime.now)
    # NULL preserves historical v1 receipts without claiming v2 semantics.
    # Keep additive columns last for exact fresh/migrated SQLite parity.
    format_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_address: Mapped[str | None] = mapped_column(String(71), nullable=True)


def _research_admission_identity_matches_json(target: ResearchStrategyAdmission) -> None:
    """Reject ORM rows whose receipt bytes and copied identity diverge."""
    from app.ir.hashing import canonical_json, content_address

    try:
        document = json.loads(target.artifact_json)
    except (TypeError, ValueError) as exc:
        raise ValueError("research admission artifact_json must be valid canonical JSON") from exc
    if canonical_json(document) != target.artifact_json:
        raise ValueError("research admission artifact_json must be canonical JSON")
    if content_address(document) != target.admission_address:
        raise ValueError("research admission address does not match artifact_json")
    for name in ("owner_id", "graph_identifier", "graph_version", "graph_address", "scheme",
                 "contract_suite", "parity_suite"):
        if document.get(name) != getattr(target, name):
            raise ValueError(f"research admission {name} does not match artifact_json")
    if document.get("format_version") == 2:
        if target.format_version != 2 or document.get("content_address") != target.content_address:
            raise ValueError("research v2 semantic identity does not match artifact_json")
    elif target.format_version is not None or target.content_address is not None:
        raise ValueError("legacy research admission semantic identity must remain null")


@event.listens_for(ResearchStrategyAdmission, "before_insert")
def _research_admission_before_insert(_mapper, _connection, target) -> None:
    _research_admission_identity_matches_json(target)


@event.listens_for(ResearchStrategyAdmission, "before_update")
@event.listens_for(ResearchStrategyAdmission, "before_delete")
def _research_admission_orm_mutation_refused(_mapper, _connection, _target) -> None:
    raise ValueError("research strategy admissions are immutable")


_make_immutable(ResearchStrategyAdmission.__table__, sqlstate="55000")


class ExperimentRun(ResearchBase):
    """The mutable execution of an ExperimentSpec: lifecycle status, checkpoint
    pointer, spent compute, and the final decision. Resuming advances the Run; a
    re-run after a code change is a new Run against the same (immutable) Spec."""
    __tablename__ = "research_experiment_run"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False)
    spec_id: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(12), default="pending")  # pending|running|failed|completed
    decision: Mapped[str | None] = mapped_column(String(16), nullable=True)  # propose|archive|needs_review
    spent_bar_seconds: Mapped[float] = mapped_column(Float, default=0.0)  # compute budget spent
    checkpoint_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str] = mapped_column(String(400), default="")
    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now)
    admission_address: Mapped[str | None] = mapped_column(String(71), nullable=True)
    __table_args__ = (
        CheckConstraint(_NullableContentAddress("admission_address"),
                        name="ck_research_experiment_run_admission_address"),
        UniqueConstraint("owner_id", "id", name="uq_research_experiment_run_owner_id"),
        ForeignKeyConstraint(
            ("owner_id", "spec_id"),
            ("research_experiment_spec.owner_id", "research_experiment_spec.id"),
        ),
        Index("ix_research_experiment_run_owner_spec", "owner_id", "spec_id"),
    )


class Finding(ResearchBase):
    """Distilled, revisable knowledge derived from experiments. Negative evidence is
    first-class (`polarity`). `confidence` is monotone in evidence and is NOT decayed
    by time — a well-powered negative stays a fact; it is only revised by a
    superseding Finding (`superseded_by`). Time-decay lives on Hypothesis.retest_priority."""
    __tablename__ = "research_finding"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False)
    hypothesis_id: Mapped[int] = mapped_column(Integer)
    statement: Mapped[str] = mapped_column(Text)
    polarity: Mapped[str] = mapped_column(String(8))  # positive|negative
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    evidence_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    superseded_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now)
    __table_args__ = (
        UniqueConstraint("owner_id", "id", name="uq_research_finding_owner_id"),
        ForeignKeyConstraint(("owner_id", "hypothesis_id"), ("research_hypothesis.owner_id", "research_hypothesis.id")),
        ForeignKeyConstraint(("owner_id", "evidence_run_id"), ("research_experiment_run.owner_id", "research_experiment_run.id")),
        ForeignKeyConstraint(("owner_id", "superseded_by"), ("research_finding.owner_id", "research_finding.id")),
        Index("ix_research_finding_owner_hypothesis", "owner_id", "hypothesis_id"),
        Index("ix_research_finding_owner_evidence_run", "owner_id", "evidence_run_id"),
        Index("ix_research_finding_owner_superseded", "owner_id", "superseded_by"),
    )


class OptimizationTrial(ResearchBase):
    """One parameterization evaluated on one walk-forward fold's in-sample window.
    Immutable and append-only: this is the trial ledger the Deflated Sharpe deflation
    counts over, so it must be a faithful, tamper-proof record of the search."""
    __tablename__ = "research_optimization_trial"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False)
    run_id: Mapped[int] = mapped_column(Integer)
    instrument_key: Mapped[str] = mapped_column(String(48), index=True)
    fold_index: Mapped[int] = mapped_column(Integer)
    params_json: Mapped[str] = mapped_column(Text, default="{}")
    is_objective: Mapped[float] = mapped_column(Float, default=0.0)  # in-sample objective
    is_trades: Mapped[int] = mapped_column(Integer, default=0)
    oos_trades: Mapped[int] = mapped_column(Integer, default=0)
    selected: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now)
    __table_args__ = (
        ForeignKeyConstraint(("owner_id", "run_id"), ("research_experiment_run.owner_id", "research_experiment_run.id")),
        Index("ix_research_optimization_trial_owner_run", "owner_id", "run_id"),
    )


_make_immutable(OptimizationTrial.__table__)


class GeneratedStrategyRecord(ResearchBase):
    """A bot-composed strategy the builder generated and evaluated. Stores the
    composition (the declarative block spec) + the emitted source keyed by strategy key,
    so a PromotionCandidate for a generated strategy can carry its exact composition to
    the human review and, on approval, into the execution engine. Mutable/upsert on
    re-generation (unlike the immutable experiment ledger)."""
    __tablename__ = "research_generated_strategy"
    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    composition_json: Mapped[str] = mapped_column(Text, default="{}")
    source: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now)


class PromotionCandidate(ResearchBase):
    """An experiment's human-gated proposal toward production. Emitting one is
    autonomous; approval is a human act recorded as a git SHA. The execution plane
    is never written to from here — approval flows through a reviewed git commit."""
    __tablename__ = "research_promotion_candidate"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False)
    run_id: Mapped[int] = mapped_column(Integer)
    parameterization_hash: Mapped[str] = mapped_column(String(64))
    qualifying_universe_json: Mapped[str] = mapped_column(Text, default="[]")
    scorecard_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(12), default="pending")  # pending|approved|rejected
    approved_git_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now)
    admission_address: Mapped[str | None] = mapped_column(String(71), nullable=True)
    __table_args__ = (
        CheckConstraint(_NullableContentAddress("admission_address"),
                        name="ck_research_promotion_candidate_admission_address"),
        UniqueConstraint("owner_id", "id", name="uq_research_promotion_candidate_owner_id"),
        ForeignKeyConstraint(("owner_id", "run_id"), ("research_experiment_run.owner_id", "research_experiment_run.id")),
        Index("ix_research_promotion_candidate_owner_run", "owner_id", "run_id"),
    )


class BlockEdge(ResearchBase):
    """"Which idea works where" — the block-family x instrument edge map.

    The reinforcement loop's memory. Findings are free-text and cannot be queried
    by block, so a night's generation had no way to learn that (say) `roc_gt`
    keeps dying on bullion while `zscore_cross_up` survives there. This table is
    that knowledge in structured form: one row per (block, instrument), counting
    how often a composition containing that block validated versus was rejected.

    Deliberately counts BLOCKS, not whole compositions. A composition is a
    one-off; a block is a reusable family, and the family is the level at which a
    lesson generalises to the next night's draw.
    """
    __tablename__ = "research_block_edge"
    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    block_name: Mapped[str] = mapped_column(String(48), primary_key=True)
    instrument_key: Mapped[str] = mapped_column(String(32), primary_key=True)
    positive: Mapped[int] = mapped_column(Integer, default=0)
    negative: Mapped[int] = mapped_column(Integer, default=0)
    last_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now)


class ShadowSession(ResearchBase):
    """One session of a candidate traded on the RESEARCH-side paper book.

    The stage between "validated" and "pending approval". A backtest is a promise;
    this is the record of whether reality matched it, session by session, against
    live candles the strategy has never seen.

    It never touches the execution plane: no order, no position, no row in
    paper_trader.db. The research plane owning its own paper book is the whole
    point — a shadow trade must be incapable of becoming a real one by accident.
    """
    __tablename__ = "research_shadow_session"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False)
    candidate_id: Mapped[int] = mapped_column(Integer)
    session_date: Mapped[dt.date] = mapped_column(Date)
    instrument_key: Mapped[str] = mapped_column(String(32))
    trades: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    net_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now)
    __table_args__ = (
        ForeignKeyConstraint(("owner_id", "candidate_id"), ("research_promotion_candidate.owner_id", "research_promotion_candidate.id")),
        Index("ix_research_shadow_session_owner_candidate", "owner_id", "candidate_id"),
    )


class DatasetManifest(ResearchBase):
    """Immutable owner-scoped provenance; cross-plane facts are digest references."""
    __tablename__ = "research_dataset_manifests"
    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    digest: Mapped[str] = mapped_column(String(71), primary_key=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    dataset_version: Mapped[str] = mapped_column(String(128), nullable=False)
    market_truth_digest: Mapped[str] = mapped_column(String(71), nullable=False)
    capability_digest: Mapped[str] = mapped_column(String(71), nullable=False)
    manifest_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, default=dt.datetime.now)
    __table_args__ = (
        CheckConstraint(_ContentAddress("digest"), name="ck_research_dataset_manifest_digest"),
        CheckConstraint(_ContentAddress("market_truth_digest"), name="ck_research_dataset_manifest_truth_digest"),
        CheckConstraint(_ContentAddress("capability_digest"), name="ck_research_dataset_manifest_capability_digest"),
        CheckConstraint(_JsonObject("manifest_json"), name="ck_research_dataset_manifest_json"),
        CheckConstraint(_SecretFreeJson("manifest_json"), name="ck_research_dataset_manifest_no_secret"),
        CheckConstraint(_JsonTextMatchesColumn("manifest_json", "owner_id", "owner_id"), name="ck_research_dataset_manifest_owner_matches_json"),
        CheckConstraint(_JsonTextMatchesColumn("manifest_json", "provider", "provider"), name="ck_research_dataset_manifest_provider_matches_json"),
        CheckConstraint(_JsonTextMatchesColumn("manifest_json", "dataset_version", "dataset_version"), name="ck_research_dataset_manifest_version_matches_json"),
        CheckConstraint(_JsonTextMatchesColumn("manifest_json", "market_truth_digest", "market_truth_digest"), name="ck_research_dataset_manifest_truth_matches_json"),
        CheckConstraint(_JsonTextMatchesColumn("manifest_json", "capability_digest", "capability_digest"), name="ck_research_dataset_manifest_capability_matches_json"),
        CheckConstraint(_JsonNumberEquals("manifest_json", "schema_version", "1"), name="ck_research_dataset_manifest_schema_version"),
        Index("ix_research_dataset_manifest_owner_created", "owner_id", "created_at"),
    )


_make_immutable(DatasetManifest.__table__)


class ResearchDatasetSegmentV2(ResearchBase):
    """Immutable typed segment fact plus the exact locally verified bytes."""

    __tablename__ = "research_dataset_segments_v2"
    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    segment_address: Mapped[str] = mapped_column(String(71), primary_key=True)
    canonical_bytes: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    object_bytes: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    object_address: Mapped[str] = mapped_column(String(71), nullable=False)
    byte_digest: Mapped[str] = mapped_column(String(71), nullable=False)
    byte_length: Mapped[int] = mapped_column(Integer, nullable=False)
    event_start: Mapped[str] = mapped_column(String(40), nullable=False)
    event_end: Mapped[str] = mapped_column(String(40), nullable=False)
    availability_start: Mapped[str] = mapped_column(String(40), nullable=False)
    availability_end: Mapped[str] = mapped_column(String(40), nullable=False)
    authority_state: Mapped[str] = mapped_column(
        String(24), nullable=False, default="VERIFIED_V2", server_default=text("'VERIFIED_V2'"))
    __table_args__ = (
        CheckConstraint(_ContentAddress("segment_address"), name="ck_research_dataset_segment_v2_address"),
        CheckConstraint(_ContentAddress("object_address"), name="ck_research_dataset_segment_v2_object"),
        CheckConstraint(_ContentAddress("byte_digest"), name="ck_research_dataset_segment_v2_digest"),
        CheckConstraint("byte_length > 0", name="ck_research_dataset_segment_v2_length"),
        CheckConstraint("authority_state = 'VERIFIED_V2'", name="ck_research_dataset_segment_v2_state"),
    )


class ResearchDatasetManifestV2(ResearchBase):
    """Sole typed research dataset authority; legacy rows remain audit-only."""

    __tablename__ = "research_dataset_manifests_v2"
    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    manifest_address: Mapped[str] = mapped_column(String(71), primary_key=True)
    canonical_bytes: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    aggregate_byte_digest: Mapped[str] = mapped_column(String(71), nullable=False)
    aggregate_byte_length: Mapped[int] = mapped_column(Integer, nullable=False)
    segment_addresses_json: Mapped[str] = mapped_column(Text, nullable=False)
    instrument_addresses_json: Mapped[str] = mapped_column(Text, nullable=False)
    fields_json: Mapped[str] = mapped_column(Text, nullable=False)
    gaps_json: Mapped[str] = mapped_column(Text, nullable=False)
    dependency_addresses_json: Mapped[str] = mapped_column(Text, nullable=False)
    event_start: Mapped[str] = mapped_column(String(40), nullable=False)
    event_end: Mapped[str] = mapped_column(String(40), nullable=False)
    availability_start: Mapped[str] = mapped_column(String(40), nullable=False)
    availability_end: Mapped[str] = mapped_column(String(40), nullable=False)
    authority_state: Mapped[str] = mapped_column(
        String(24), nullable=False, default="VERIFIED_V2", server_default=text("'VERIFIED_V2'"))
    __table_args__ = (
        CheckConstraint(_ContentAddress("manifest_address"), name="ck_research_dataset_manifest_v2_address"),
        CheckConstraint(_ContentAddress("aggregate_byte_digest"), name="ck_research_dataset_manifest_v2_digest"),
        CheckConstraint("aggregate_byte_length > 0", name="ck_research_dataset_manifest_v2_length"),
        CheckConstraint(_JsonArray("segment_addresses_json"), name="ck_research_dataset_manifest_v2_segments_json"),
        CheckConstraint(_JsonArray("instrument_addresses_json"), name="ck_research_dataset_manifest_v2_instruments_json"),
        CheckConstraint(_JsonArray("fields_json"), name="ck_research_dataset_manifest_v2_fields_json"),
        CheckConstraint(_JsonArray("gaps_json"), name="ck_research_dataset_manifest_v2_gaps_json"),
        CheckConstraint(_JsonArray("dependency_addresses_json"), name="ck_research_dataset_manifest_v2_dependencies_json"),
        CheckConstraint("authority_state = 'VERIFIED_V2'", name="ck_research_dataset_manifest_v2_state"),
    )


class ResearchDatasetManifestSegmentV2(ResearchBase):
    """Ordered owner-scoped link; prevents a manifest from naming an alien segment."""

    __tablename__ = "research_dataset_manifest_segments_v2"
    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    manifest_address: Mapped[str] = mapped_column(String(71), primary_key=True)
    ordinal: Mapped[int] = mapped_column(Integer, primary_key=True)
    segment_address: Mapped[str] = mapped_column(String(71), nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(
            ("owner_id", "manifest_address"),
            ("research_dataset_manifests_v2.owner_id", "research_dataset_manifests_v2.manifest_address"),
        ),
        ForeignKeyConstraint(
            ("owner_id", "segment_address"),
            ("research_dataset_segments_v2.owner_id", "research_dataset_segments_v2.segment_address"),
        ),
        UniqueConstraint("owner_id", "manifest_address", "segment_address",
                         name="uq_research_dataset_manifest_segment_v2_address"),
        CheckConstraint("ordinal >= 0", name="ck_research_dataset_manifest_segment_v2_ordinal"),
    )


def _verify_typed_dataset_segment_row(target: ResearchDatasetSegmentV2) -> None:
    from app.backtest.dataset_store import DatasetSegment, verify_dataset_segment

    segment = DatasetSegment.from_bytes(bytes(target.canonical_bytes))
    if (segment.owner_id != target.owner_id or segment.segment_address != target.segment_address
            or segment.object_address != target.object_address
            or segment.byte_digest != target.byte_digest or segment.byte_length != target.byte_length
            or segment.event_start != target.event_start or segment.event_end != target.event_end
            or segment.availability_start != target.availability_start
            or segment.availability_end != target.availability_end
            or target.authority_state != "VERIFIED_V2"):
        raise ValueError("typed dataset segment copied columns do not reconstruct")
    verify_dataset_segment(segment, bytes(target.object_bytes))


def _verify_typed_dataset_manifest_row(target: ResearchDatasetManifestV2) -> None:
    from app.backtest.dataset_store import DatasetManifest
    from app.ir.hashing import canonical_json

    manifest = DatasetManifest.from_bytes(bytes(target.canonical_bytes))
    dependencies = sorted({
        *manifest.correction_addresses, *manifest.provider_entity_addresses,
        *manifest.provider_product_addresses, *manifest.provider_contract_addresses,
        *manifest.provider_observation_addresses, *manifest.normalized_observation_addresses,
        *manifest.raw_schema_addresses, *manifest.normalization_transform_addresses,
        *manifest.creation_evidence_addresses,
        *manifest.truth_snapshot_addresses, manifest.capability_profile_address,
        manifest.alignment_policy_address,
        manifest.missing_data_policy_address, manifest.adjustment_policy_address,
        manifest.roll_policy_address, *manifest.algorithm_addresses,
    })
    copied = {
        "segment_addresses_json": list(manifest.segment_addresses),
        "instrument_addresses_json": list(manifest.instrument_addresses),
        "fields_json": list(manifest.fields),
        "gaps_json": list(manifest.gaps),
        "dependency_addresses_json": dependencies,
    }
    if (manifest.owner_id != target.owner_id or manifest.manifest_address != target.manifest_address
            or manifest.aggregate_byte_digest != target.aggregate_byte_digest
            or manifest.aggregate_byte_length != target.aggregate_byte_length
            or manifest.event_start != target.event_start or manifest.event_end != target.event_end
            or manifest.availability_start != target.availability_start
            or manifest.availability_end != target.availability_end
            or target.authority_state != "VERIFIED_V2"
            or any(canonical_json(value) != getattr(target, name)
                   for name, value in copied.items())):
        raise ValueError("typed dataset manifest copied columns do not reconstruct")


for _typed_dataset_model, _verifier in (
    (ResearchDatasetSegmentV2, _verify_typed_dataset_segment_row),
    (ResearchDatasetManifestV2, _verify_typed_dataset_manifest_row),
):
    event.listen(_typed_dataset_model, "before_insert",
                 lambda _mapper, _connection, target, verifier=_verifier: verifier(target))
    event.listen(_typed_dataset_model, "before_update",
                 lambda _mapper, _connection, _target: (_ for _ in ()).throw(
                     ValueError("typed dataset authority is immutable")))
    event.listen(_typed_dataset_model, "before_delete",
                 lambda _mapper, _connection, _target: (_ for _ in ()).throw(
                     ValueError("typed dataset authority is immutable")))


for _typed_dataset_table in (
    ResearchDatasetSegmentV2.__table__, ResearchDatasetManifestV2.__table__,
    ResearchDatasetManifestSegmentV2.__table__,
):
    _make_immutable(_typed_dataset_table, sqlstate="55000")


@event.listens_for(Engine, "before_execute", retval=True)
def _dataset_manifest_core_guard(connection, clauseelement, multiparams, params, execution_options):
    """Guard controlled SQLAlchemy Core INSERT values, including inline ``.values``.

    Raw driver SQL is deliberately outside this application persistence boundary.
    """
    if not isinstance(clauseelement, Insert) or clauseelement.table.name != DatasetManifest.__tablename__:
        return clauseelement, multiparams, params
    for row in _insert_rows_with_inline_values(clauseelement, multiparams, params):
        _dataset_manifest_core_identity_guard(row)
    return clauseelement, multiparams, params


@event.listens_for(DatasetManifest, "before_insert")
def _dataset_manifest_identity_matches_json(_mapper, _connection, target) -> None:
    _dataset_manifest_core_identity_guard(target.__dict__)


def persist_dataset_manifest(execution_connection, research_connection, *, owner_id: str, values: dict) -> None:
    """Persist only for the server-authorized owner after both facts resolve."""
    from app.db.models import MarketDataCapabilityProfile, MarketTruthSnapshotRecord
    from app.ir.hashing import content_address

    record = dict(values)
    if record.get("owner_id") != owner_id:
        raise ValueError("dataset manifest owner does not match authoritative owner")
    document = _canonical_secret_free_document(record["manifest_json"], label="dataset manifest_json")
    _manifest_document_matches_columns(document, record)
    if content_address(document) != record["digest"]:
        raise ValueError("dataset manifest digest does not match manifest_json")
    truth = execution_connection.execute(select(MarketTruthSnapshotRecord.digest).where(
        MarketTruthSnapshotRecord.digest == record["market_truth_digest"]
    )).scalar_one_or_none()
    if truth is None:
        raise ValueError("dataset manifest market-truth digest is not persisted")
    capability = execution_connection.execute(select(MarketDataCapabilityProfile.provider).where(
        MarketDataCapabilityProfile.owner_id == record["owner_id"],
        MarketDataCapabilityProfile.digest == record["capability_digest"],
    )).scalar_one_or_none()
    if capability != record["provider"]:
        raise ValueError("dataset manifest capability digest is not owned by its owner")
    research_connection.execute(insert(DatasetManifest), record)


_PHASE4_SECRET_FUNCTION = """
CREATE OR REPLACE FUNCTION phase4_json_has_secret_key(payload jsonb) RETURNS boolean
LANGUAGE sql IMMUTABLE AS $$
    WITH RECURSIVE nodes(value) AS (
        SELECT payload
        UNION ALL
        SELECT child.value FROM nodes CROSS JOIN LATERAL (
            SELECT value FROM jsonb_each(CASE WHEN jsonb_typeof(nodes.value) = 'object' THEN nodes.value ELSE '{}'::jsonb END)
            UNION ALL
            SELECT value FROM jsonb_array_elements(CASE WHEN jsonb_typeof(nodes.value) = 'array' THEN nodes.value ELSE '[]'::jsonb END)
        ) AS child
    )
    SELECT EXISTS (
        SELECT 1 FROM nodes CROSS JOIN LATERAL jsonb_object_keys(CASE WHEN jsonb_typeof(nodes.value) = 'object' THEN nodes.value ELSE '{}'::jsonb END) AS key
        WHERE (
            lower(key) LIKE '%%token%%' OR lower(key) LIKE '%%secret%%' OR
            lower(key) LIKE '%%password%%' OR lower(key) LIKE '%%api_key%%' OR
            lower(key) LIKE '%%credential%%' OR lower(key) LIKE '%%authorization%%'
        )
    )
$$
"""

event.listen(DatasetManifest.__table__, "before_create", DDL(_PHASE4_SECRET_FUNCTION).execute_if(dialect="postgresql"))
event.listen(DatasetManifest.__table__, "after_create", DDL("""
    CREATE TRIGGER research_dataset_manifests_refuse_secret_key
    BEFORE INSERT ON research_dataset_manifests
    WHEN EXISTS (SELECT 1 FROM json_tree(NEW.manifest_json) WHERE key IS NOT NULL AND (
        lower(key) LIKE '%%token%%' OR lower(key) LIKE '%%secret%%' OR lower(key) LIKE '%%password%%' OR
        lower(key) LIKE '%%api_key%%' OR lower(key) LIKE '%%credential%%' OR lower(key) LIKE '%%authorization%%'
    ))
    BEGIN SELECT RAISE(ABORT, 'research_dataset_manifests contains credential-bearing key'); END
""").execute_if(dialect="sqlite"))


from app.events.outbox import define_outbox_models as _define_outbox_models

RESEARCH_OUTBOX_MODELS = _define_outbox_models(ResearchBase, "research")
