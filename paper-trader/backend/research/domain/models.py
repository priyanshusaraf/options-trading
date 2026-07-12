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

from sqlalchemy import (
    DDL,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import Table

from research.domain.base import ResearchBase


def _make_immutable(table: Table) -> None:
    """Attach BEFORE UPDATE/DELETE triggers that abort any mutation of `table`,
    created alongside the table itself. DB-enforced, client-agnostic."""
    for op in ("UPDATE", "DELETE"):
        trg = f"trg_{table.name}_no_{op.lower()}"
        event.listen(
            table, "after_create",
            DDL(f"CREATE TRIGGER IF NOT EXISTS {trg} BEFORE {op} ON {table.name} "
                f"BEGIN SELECT RAISE(ABORT, '{table.name} is immutable'); END"))


class ResearchProgram(ResearchBase):
    """A long-lived research initiative (e.g. Trend Following, Mean Reversion)."""
    __tablename__ = "research_program"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    thesis: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(12), default="active")  # active|paused|archived
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now)


class Hypothesis(ResearchBase):
    """An explicit thesis under a Program. Research always begins here. Carries the
    re-test priority — the quantity that *decays upward* over time so a killed idea
    is eventually revisited (floor > 0: never permanently banned; cap: never thrash)."""
    __tablename__ = "research_hypothesis"
    id: Mapped[int] = mapped_column(primary_key=True)
    program_id: Mapped[int] = mapped_column(ForeignKey("research_program.id"), index=True)
    statement: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(12), default="open")  # open|supported|rejected|dormant
    retest_priority: Mapped[float] = mapped_column(Float, default=1.0)
    last_tested_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now)


class ExperimentSpec(ResearchBase):
    """IMMUTABLE, content-hashed recipe for one reproducible experiment. `id` is the
    content hash; the same idea re-run under new code is a new *Run* against this
    same Spec. Provenance (git_commit + rule-set versions + seed) makes any result
    interpretable and reproducible."""
    __tablename__ = "research_experiment_spec"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # content hash
    hypothesis_id: Mapped[int] = mapped_column(ForeignKey("research_hypothesis.id"), index=True)
    parent_spec_id: Mapped[str | None] = mapped_column(
        ForeignKey("research_experiment_spec.id"), nullable=True)  # lineage
    recipe_json: Mapped[str] = mapped_column(Text, default="{}")  # definitions, datasets, budgets
    git_commit: Mapped[str] = mapped_column(String(40), default="")
    qualifier_version: Mapped[str] = mapped_column(String(24), default="")
    optimizer_version: Mapped[str] = mapped_column(String(24), default="")
    validator_version: Mapped[str] = mapped_column(String(24), default="")
    scoring_version: Mapped[str] = mapped_column(String(24), default="")
    rng_seed: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now)


_make_immutable(ExperimentSpec.__table__)


class ExperimentRun(ResearchBase):
    """The mutable execution of an ExperimentSpec: lifecycle status, checkpoint
    pointer, spent compute, and the final decision. Resuming advances the Run; a
    re-run after a code change is a new Run against the same (immutable) Spec."""
    __tablename__ = "research_experiment_run"
    id: Mapped[int] = mapped_column(primary_key=True)
    spec_id: Mapped[str] = mapped_column(ForeignKey("research_experiment_spec.id"), index=True)
    status: Mapped[str] = mapped_column(String(12), default="pending")  # pending|running|failed|completed
    decision: Mapped[str | None] = mapped_column(String(16), nullable=True)  # propose|archive|needs_review
    spent_bar_seconds: Mapped[float] = mapped_column(Float, default=0.0)  # compute budget spent
    checkpoint_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str] = mapped_column(String(400), default="")
    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now)


class Finding(ResearchBase):
    """Distilled, revisable knowledge derived from experiments. Negative evidence is
    first-class (`polarity`). `confidence` is monotone in evidence and is NOT decayed
    by time — a well-powered negative stays a fact; it is only revised by a
    superseding Finding (`superseded_by`). Time-decay lives on Hypothesis.retest_priority."""
    __tablename__ = "research_finding"
    id: Mapped[int] = mapped_column(primary_key=True)
    hypothesis_id: Mapped[int] = mapped_column(ForeignKey("research_hypothesis.id"), index=True)
    statement: Mapped[str] = mapped_column(Text)
    polarity: Mapped[str] = mapped_column(String(8))  # positive|negative
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    evidence_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("research_experiment_run.id"), nullable=True)
    superseded_by: Mapped[int | None] = mapped_column(
        ForeignKey("research_finding.id"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now)


class OptimizationTrial(ResearchBase):
    """One parameterization evaluated on one walk-forward fold's in-sample window.
    Immutable and append-only: this is the trial ledger the Deflated Sharpe deflation
    counts over, so it must be a faithful, tamper-proof record of the search."""
    __tablename__ = "research_optimization_trial"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("research_experiment_run.id"), index=True)
    instrument_key: Mapped[str] = mapped_column(String(48), index=True)
    fold_index: Mapped[int] = mapped_column(Integer)
    params_json: Mapped[str] = mapped_column(Text, default="{}")
    is_objective: Mapped[float] = mapped_column(Float, default=0.0)  # in-sample objective
    is_trades: Mapped[int] = mapped_column(Integer, default=0)
    oos_trades: Mapped[int] = mapped_column(Integer, default=0)
    selected: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now)


_make_immutable(OptimizationTrial.__table__)


class GeneratedStrategyRecord(ResearchBase):
    """A bot-composed strategy the builder generated and evaluated. Stores the
    composition (the declarative block spec) + the emitted source keyed by strategy key,
    so a PromotionCandidate for a generated strategy can carry its exact composition to
    the human review and, on approval, into the execution engine. Mutable/upsert on
    re-generation (unlike the immutable experiment ledger)."""
    __tablename__ = "research_generated_strategy"
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
    run_id: Mapped[int] = mapped_column(ForeignKey("research_experiment_run.id"), index=True)
    parameterization_hash: Mapped[str] = mapped_column(String(64))
    qualifying_universe_json: Mapped[str] = mapped_column(Text, default="[]")
    scorecard_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(12), default="pending")  # pending|approved|rejected
    approved_git_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now)
