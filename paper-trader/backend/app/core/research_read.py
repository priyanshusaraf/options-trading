"""Read side of the approve→deploy bridge: the execution/API plane reading the
research plane's PromotionCandidate ledger.

This is the ONE intended coupling between the two planes, and it runs in this
direction only — the API surfaces research output for a human to approve. The
research process never reaches back the other way (its guards forbid importing any
execution / order / broker / runner code). Nothing here touches capital: the only
write is `decide_project_candidate`, which appends canonical research decision evidence.
It does not write application configuration, deployment state or orders.

research.db lives at `PT_RESEARCH_DB_PATH` (default `research.db`); if it does not
exist yet (no nightly has run) every read degrades to empty and deploy reports the
candidate as missing — the cockpit simply shows no promotions.
"""
from __future__ import annotations

import contextlib
import dataclasses
import datetime as dt
import json
import os

from sqlalchemy import update

from app.ir.hashing import canonical_json, content_address

from research.config import research_db_path
from research.domain.base import make_engine, make_sessionmaker
from research.domain.models import (
    ExperimentRun,
    ExperimentSpec,
    GeneratedStrategyRecord,
    PromotionCandidate,
)
from research.evidence import (
    EvidenceMissing,
    EvidenceRejected,
    decode_terminal_evidence,
)
from research.strategy.explain import explain


@contextlib.contextmanager
def _research_session():
    """Yield a session on research.db, or None if it doesn't exist. Disposes the
    engine on exit so repeated API calls don't accumulate SQLite connections."""
    path = research_db_path()
    if not os.path.exists(path):
        yield None
        return
    engine = make_engine(path)
    session = make_sessionmaker(engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _recipe_for(session, run_id: int) -> dict:
    run = session.get(ExperimentRun, run_id)
    spec = session.get(ExperimentSpec, run.spec_id) if run else None
    if spec is None:
        return {}
    try:
        return json.loads(spec.recipe_json)
    except (ValueError, TypeError):
        return {}


class StoredEvidenceCorrupt(Exception):
    pass


class CandidateDecisionConflict(Exception):
    pass


def _graph_for_recipe(recipe: dict) -> dict | None:
    provenance = recipe.get("graph_provenance")
    graph = provenance.get("graph") if isinstance(provenance, dict) else None
    return graph if isinstance(graph, dict) else None


def _candidate_for_run(session, run_id: int) -> dict | None:
    candidate = (
        session.query(PromotionCandidate)
        .filter_by(run_id=run_id)
        .order_by(PromotionCandidate.id.desc())
        .first()
    )
    if candidate is None:
        return None
    try:
        scorecard = json.loads(candidate.scorecard_json)
    except (TypeError, ValueError):
        scorecard = {}
    decision = scorecard.get("decision") if isinstance(scorecard, dict) else None
    return {
        "candidate_id": candidate.id,
        "status": candidate.status,
        "decision": decision if isinstance(decision, dict) else None,
    }


def _graph_run_view(session, run: ExperimentRun, *, include_evidence: bool) -> dict | None:
    recipe = _recipe_for(session, run.id)
    graph = _graph_for_recipe(recipe)
    if graph is None:
        return None
    evidence = None
    try:
        evidence = decode_terminal_evidence(run.checkpoint_json)
        evidence_state = "verified"
    except EvidenceMissing:
        if run.status in {"pending", "running"}:
            evidence_state = run.status
        elif run.status == "failed":
            if include_evidence:
                raise StoredEvidenceCorrupt(run.id)
            evidence_state = "corrupt"
        else:
            evidence_state = "legacy_unbound"
    except EvidenceRejected as exc:
        if include_evidence:
            raise StoredEvidenceCorrupt(run.id) from exc
        evidence_state = "corrupt"
    view = {
        "run_id": run.id,
        "spec_id": run.spec_id,
        "status": run.status,
        "decision": run.decision,
        "evidence_state": evidence_state,
        "graph": graph,
        "candidate": _candidate_for_run(session, run.id),
    }
    if include_evidence:
        view["evidence"] = evidence
    return view


def list_graph_runs(project_id: str) -> list[dict]:
    """Graph-bound runs owned by one copied immutable project provenance."""
    with _research_session() as session:
        if session is None:
            return []
        runs = session.query(ExperimentRun).order_by(ExperimentRun.id.desc()).all()
        views = []
        for run in runs:
            view = _graph_run_view(session, run, include_evidence=False)
            if view is not None and view["graph"].get("project_id") == project_id:
                views.append(view)
        return views


def get_graph_run(project_id: str, run_id: int) -> dict | None:
    """One graph-bound run, hidden unless its immutable recipe owns the project."""
    with _research_session() as session:
        if session is None:
            return None
        run = session.get(ExperimentRun, run_id)
        if run is None:
            return None
        view = _graph_run_view(session, run, include_evidence=True)
        if view is None or view["graph"].get("project_id") != project_id:
            return None
        return view


def _view(session, c: PromotionCandidate) -> dict:
    """Flatten a candidate + its spec into a JSON-safe dict for the API. Carries the
    validated universe (what deploy assigns) and a plain-language explanation so the
    human reviews the strategy's actual logic, not just a score."""
    recipe = _recipe_for(session, c.run_id)
    strategy_key = recipe.get("strategy", "unknown")
    params = recipe.get("params", {})
    interval = recipe.get("interval", "day")

    def _load(raw, default):
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            return default

    payload = _load(c.scorecard_json, {})
    # If this is a bot-generated strategy, carry its exact composition + source so the
    # human reviews the real logic and deploy can hand the composition to the engine.
    gen = session.get(GeneratedStrategyRecord, strategy_key)
    composition = _load(gen.composition_json, None) if gen is not None else None
    explanation = _explain(strategy_key, params, composition)
    return {
        "id": c.id,
        "run_id": c.run_id,
        "status": c.status,
        "strategy_key": strategy_key,
        "params": params,
        "interval": interval,
        "parameterization_hash": c.parameterization_hash,
        "qualified_universe": _load(c.qualifying_universe_json, []),
        "validated_universe": payload.get("validated", []),
        "best": payload.get("best"),
        "generated": gen is not None,
        "composition": composition,
        "generated_source": gen.source if gen is not None else None,
        "explanation": explanation,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


def _explain(strategy_key: str, params: dict, composition) -> dict:
    """Composition-exact explanation for a generated strategy; the authored/curated one
    otherwise."""
    if composition:
        try:
            from research.strategy.builder.describe import explain_composition
            from research.strategy.builder.grammar import Composition
            return dataclasses.asdict(explain_composition(Composition.from_dict(composition)))
        except Exception:
            pass
    return dataclasses.asdict(explain(strategy_key, params))


def list_pending_promotions() -> list[dict]:
    """Every candidate still awaiting a human decision, newest first."""
    with _research_session() as session:
        if session is None:
            return []
        try:
            cands = (session.query(PromotionCandidate)
                     .filter_by(status="pending")
                     .order_by(PromotionCandidate.created_at.desc()).all())
            return [_view(session, c) for c in cands]
        except Exception:
            return []


def get_promotion(candidate_id: int) -> dict | None:
    """One pending candidate, or None for absent and every non-pending state."""
    with _research_session() as session:
        if session is None:
            return None
        try:
            c = (session.query(PromotionCandidate)
                 .filter_by(id=candidate_id, status="pending")
                 .one_or_none())
            return _view(session, c) if c is not None else None
        except Exception:
            return None


def decide_project_candidate(
    project_id: str,
    candidate_id: int,
    *,
    expected_status: str,
    decision: str,
    reason: str,
) -> dict | None:
    """Record one canonical human decision without touching application state.

    None hides absent and cross-project ids. CandidateDecisionConflict covers every
    stale, shadow or terminal state without revealing which one to a caller.
    """
    with _research_session() as session:
        if session is None:
            return None
        if (
            expected_status != "pending"
            or decision not in {"approved", "rejected"}
            or not isinstance(reason, str)
            or not reason.strip()
            or len(reason) > 400
        ):
            raise CandidateDecisionConflict(candidate_id)
        candidate = session.get(PromotionCandidate, candidate_id)
        if candidate is None:
            return None
        recipe = _recipe_for(session, candidate.run_id)
        graph = _graph_for_recipe(recipe)
        if graph is None or graph.get("project_id") != project_id:
            return None
        if candidate.status != expected_status:
            raise CandidateDecisionConflict(candidate_id)
        try:
            scorecard = json.loads(candidate.scorecard_json)
        except (TypeError, ValueError) as exc:
            raise CandidateDecisionConflict(candidate_id) from exc
        if not isinstance(scorecard, dict) or "decision" in scorecard:
            raise CandidateDecisionConflict(candidate_id)
        decided_at = dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z")
        evidence = {
            "actor": "owner",
            "candidate_id": candidate.id,
            "decision": decision,
            "decided_at": decided_at,
            "expected_status": expected_status,
            "reason": reason,
            "run_id": candidate.run_id,
        }
        envelope = {
            "schema_version": 1,
            "content_address": content_address(evidence),
            "evidence": evidence,
        }
        updated_scorecard = {**scorecard, "decision": envelope}
        claimed = session.execute(
            update(PromotionCandidate)
            .where(
                PromotionCandidate.id == candidate_id,
                PromotionCandidate.status == expected_status,
                PromotionCandidate.scorecard_json == candidate.scorecard_json,
            )
            .values(
                status=decision,
                scorecard_json=canonical_json(updated_scorecard),
            )
        )
        if claimed.rowcount != 1:
            session.rollback()
            raise CandidateDecisionConflict(candidate_id)
        session.commit()
        return {
            "candidate_id": candidate_id,
            "status": decision,
            "decision": envelope,
        }
