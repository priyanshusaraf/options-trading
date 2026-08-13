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
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy import Index
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.elements import ColumnElement
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


class _JsonIsValid(ColumnElement):
    type = Boolean()
    inherit_cache = True

    def __init__(self, column_name: str):
        self.column_name = column_name


@compiles(_JsonIsValid, "sqlite")
def _compile_json_is_valid_sqlite(element, _compiler, **_kw):
    return f"json_valid({element.column_name})"


@compiles(_JsonIsValid, "postgresql")
def _compile_json_is_valid_postgresql(_element, _compiler, **_kw):
    return "jsonb_typeof(artifact_json::jsonb) = 'object'"


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
        CheckConstraint(_JsonIsValid("artifact_json"),
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


from app.events.outbox import define_outbox_models as _define_outbox_models

RESEARCH_OUTBOX_MODELS = _define_outbox_models(ResearchBase, "research")
