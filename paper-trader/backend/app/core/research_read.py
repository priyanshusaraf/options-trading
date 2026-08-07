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

from app.core.research_review import ReviewQueryRejected, make_review_event
from app.ir.hashing import canonical_json, content_address

from research.config import research_db_path
from research.domain.base import make_engine, make_sessionmaker
from research.domain.models import (
    ExperimentRun,
    ExperimentSpec,
    Finding,
    GeneratedStrategyRecord,
    PromotionCandidate,
)
from research.evidence import (
    EvidenceMissing,
    EvidenceRejected,
    confidence_from_trades,
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


class FindingEvidenceUnavailable(Exception):
    pass


class FindingRevisionConflict(Exception):
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


def _review_graph_reference(graph: dict) -> dict:
    return {
        "identifier": graph["identifier"],
        "version": graph["version"],
        "content_address": graph["content_address"],
    }


def _verified_candidate_decision(candidate: PromotionCandidate) -> dict | None:
    """Return a verified decision envelope, or None for a valid undecided row."""
    try:
        scorecard = json.loads(candidate.scorecard_json)
    except (TypeError, ValueError) as exc:
        raise StoredEvidenceCorrupt(candidate.id) from exc
    if not isinstance(scorecard, dict):
        raise StoredEvidenceCorrupt(candidate.id)
    envelope = scorecard.get("decision")
    if envelope is None:
        if candidate.status not in {"pending", "shadow"}:
            raise StoredEvidenceCorrupt(candidate.id)
        return None
    if not isinstance(envelope, dict) or set(envelope) != {
        "schema_version", "content_address", "evidence"
    } or envelope.get("schema_version") != 1:
        raise StoredEvidenceCorrupt(candidate.id)
    evidence = envelope.get("evidence")
    if not isinstance(evidence, dict) or set(evidence) != {
        "actor", "candidate_id", "decision", "decided_at", "expected_status",
        "reason", "run_id",
    }:
        raise StoredEvidenceCorrupt(candidate.id)
    try:
        verified_address = content_address(evidence)
    except (TypeError, ValueError) as exc:
        raise StoredEvidenceCorrupt(candidate.id) from exc
    if (
        envelope.get("content_address") != verified_address
        or evidence.get("actor") != "owner"
        or evidence.get("candidate_id") != candidate.id
        or evidence.get("run_id") != candidate.run_id
        or evidence.get("expected_status") != "pending"
        or evidence.get("decision") not in {"approved", "rejected"}
        or candidate.status != evidence.get("decision")
        or not isinstance(evidence.get("reason"), str)
        or not evidence["reason"].strip()
        or len(evidence["reason"]) > 400
    ):
        raise StoredEvidenceCorrupt(candidate.id)
    try:
        dt.datetime.fromisoformat(evidence["decided_at"].replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError) as exc:
        raise StoredEvidenceCorrupt(candidate.id) from exc
    return envelope


#: The orchestrator's decision vocabulary (`research/orchestrator/run.py`). Review
#: summaries are frozen verbatim into immutable, content-addressed review snapshots,
#: so only known tokens may reach them — an unrecognised value is reported as its
#: run status rather than copied out of the research database unvalidated.
RUN_DECISIONS = frozenset({"propose", "archive", "needs_review"})


def _run_outcome(run: ExperimentRun) -> str:
    return run.decision if run.decision in RUN_DECISIONS else run.status


def _empty_project_review_source() -> dict:
    return {
        "events": [],
        "queues": {
            "review_needed_runs": [],
            "pending_candidates": [],
            "active_findings": [],
        },
        "source_errors": [],
    }


def project_review_source(project_id: str) -> dict:
    """Derive one project's review facts and queues in one research snapshot.

    Corrupt rows are contained and identified without copying untrusted source text
    into the response. This function never invokes research execution services.
    """
    result = _empty_project_review_source()
    with _research_session() as session:
        if session is None:
            return result

        run_contexts: dict[int, dict] = {}
        for run in session.query(ExperimentRun).order_by(ExperimentRun.id.asc()).all():
            view = _graph_run_view(session, run, include_evidence=False)
            graph = view.get("graph") if view is not None else None
            if not isinstance(graph, dict) or graph.get("project_id") != project_id:
                continue
            try:
                graph_ref = _review_graph_reference(graph)
                status = "needs_review" if run.decision == "needs_review" else run.status
                result["events"].append(make_review_event(
                    event_id=f"run:{run.id}",
                    event_type="experiment_run",
                    occurred_at=run.completed_at or run.started_at or run.created_at,
                    status=status,
                    summary=f"Experiment run {run.id}: {_run_outcome(run)}",
                    references={
                        "graph": graph_ref, "run_id": run.id,
                        "finding_id": None, "candidate_id": None,
                    },
                ))
            except (KeyError, TypeError, ValueError, ReviewQueryRejected):
                result["source_errors"].append({
                    "source": "run", "source_id": str(run.id),
                    "code": "RUN_BINDING_CORRUPT",
                })
                continue
            run_contexts[run.id] = {"run": run, "view": view, "graph": graph_ref}
            if (
                run.decision == "needs_review" or run.status == "failed"
                or view["evidence_state"] == "corrupt"
            ):
                result["queues"]["review_needed_runs"].append({
                    "run_id": run.id,
                    "status": status,
                    "evidence_state": view["evidence_state"],
                    "graph": graph_ref,
                })

        for finding in session.query(Finding).order_by(Finding.id.asc()).all():
            if finding.evidence_run_id not in run_contexts:
                continue
            try:
                context = _verified_finding_run(
                    session, project_id, finding.evidence_run_id
                )
            except FindingEvidenceUnavailable:
                result["source_errors"].append({
                    "source": "finding", "source_id": str(finding.id),
                    "code": "FINDING_EVIDENCE_UNAVAILABLE",
                })
                continue
            except StoredEvidenceCorrupt:
                result["source_errors"].append({
                    "source": "finding", "source_id": str(finding.id),
                    "code": "FINDING_EVIDENCE_CORRUPT",
                })
                continue
            if context is None:
                continue
            graph_ref = run_contexts[finding.evidence_run_id]["graph"]
            status = "superseded" if finding.superseded_by is not None else "active"
            try:
                result["events"].append(make_review_event(
                    event_id=f"finding:{finding.id}",
                    event_type="finding_created",
                    occurred_at=finding.created_at,
                    status=status,
                    summary=f"Finding {finding.id}: {finding.polarity}",
                    references={
                        "graph": graph_ref, "run_id": finding.evidence_run_id,
                        "finding_id": finding.id, "candidate_id": None,
                    },
                ))
            except ReviewQueryRejected:
                result["source_errors"].append({
                    "source": "finding", "source_id": str(finding.id),
                    "code": "FINDING_ROW_CORRUPT",
                })
                continue
            if status == "active":
                result["queues"]["active_findings"].append({
                    "finding_id": finding.id,
                    "evidence_run_id": finding.evidence_run_id,
                    "polarity": finding.polarity,
                    "confidence": finding.confidence,
                    "graph": graph_ref,
                })

        candidates = (
            session.query(PromotionCandidate)
            .order_by(PromotionCandidate.id.asc()).all()
        )
        for candidate in candidates:
            context = run_contexts.get(candidate.run_id)
            if context is None:
                continue
            graph_ref = context["graph"]
            try:
                result["events"].append(make_review_event(
                    event_id=f"candidate:{candidate.id}",
                    event_type="candidate_created",
                    occurred_at=candidate.created_at,
                    status="created",
                    summary=f"Candidate {candidate.id}: created",
                    references={
                        "graph": graph_ref, "run_id": candidate.run_id,
                        "finding_id": None, "candidate_id": candidate.id,
                    },
                ))
            except ReviewQueryRejected:
                result["source_errors"].append({
                    "source": "candidate", "source_id": str(candidate.id),
                    "code": "CANDIDATE_ROW_CORRUPT",
                })
                continue
            try:
                decision = _verified_candidate_decision(candidate)
            except StoredEvidenceCorrupt:
                result["source_errors"].append({
                    "source": "candidate", "source_id": str(candidate.id),
                    "code": "CANDIDATE_DECISION_CORRUPT",
                })
                continue
            if decision is None:
                if candidate.status == "pending":
                    result["queues"]["pending_candidates"].append({
                        "candidate_id": candidate.id,
                        "run_id": candidate.run_id,
                        "status": candidate.status,
                        "graph": graph_ref,
                    })
                continue
            evidence = decision["evidence"]
            try:
                result["events"].append(make_review_event(
                    event_id=f"candidate:{candidate.id}:decision",
                    event_type="candidate_decided",
                    occurred_at=evidence["decided_at"],
                    status=evidence["decision"],
                    summary=f"Candidate {candidate.id}: {evidence['decision']}",
                    references={
                        "graph": graph_ref, "run_id": candidate.run_id,
                        "finding_id": None, "candidate_id": candidate.id,
                    },
                ))
            except ReviewQueryRejected:
                result["source_errors"].append({
                    "source": "candidate", "source_id": str(candidate.id),
                    "code": "CANDIDATE_DECISION_CORRUPT",
                })
    return result


def _verified_finding_run(session, project_id: str, run_id: int) -> dict | None:
    run = session.get(ExperimentRun, run_id)
    spec = session.get(ExperimentSpec, run.spec_id) if run is not None else None
    if run is None or spec is None:
        return None
    recipe = _recipe_for(session, run_id)
    graph = _graph_for_recipe(recipe)
    if graph is None or graph.get("project_id") != project_id:
        return None
    if run.status != "completed":
        raise FindingEvidenceUnavailable(run_id)
    try:
        evidence = decode_terminal_evidence(run.checkpoint_json)
    except EvidenceMissing as exc:
        raise FindingEvidenceUnavailable(run_id) from exc
    except EvidenceRejected as exc:
        raise StoredEvidenceCorrupt(run_id) from exc
    evidence_run = evidence.get("run")
    evidence_provenance = evidence.get("provenance")
    evidence_graph = (
        evidence_provenance.get("graph_provenance", {}).get("graph")
        if isinstance(evidence_provenance, dict) else None
    )
    if (
        evidence.get("spec_id") != spec.id
        or not isinstance(evidence_run, dict)
        or evidence_run.get("id") != run.id
        or evidence_run.get("status") != "completed"
        or evidence_graph != graph
    ):
        raise StoredEvidenceCorrupt(run_id)
    return {
        "run": run,
        "spec": spec,
        "recipe": recipe,
        "evidence": evidence,
        "binding": {
            "run_id": run.id,
            "spec_id": spec.id,
            "evidence_content_address": content_address(evidence),
            "graph": graph,
        },
    }


def _finding_view(finding: Finding, context: dict) -> dict:
    return {
        "finding_id": finding.id,
        "statement": finding.statement,
        "polarity": finding.polarity,
        "confidence": finding.confidence,
        "evidence_run_id": finding.evidence_run_id,
        "superseded_by": finding.superseded_by,
        "status": "superseded" if finding.superseded_by is not None else "active",
        "created_at": finding.created_at.isoformat() if finding.created_at else None,
        "binding": context["binding"],
    }


def list_project_findings(project_id: str) -> list[dict]:
    with _research_session() as session:
        if session is None:
            return []
        views = []
        for finding in session.query(Finding).order_by(Finding.id.asc()).all():
            if finding.evidence_run_id is None:
                continue
            context = _verified_finding_run(
                session, project_id, finding.evidence_run_id
            )
            if context is not None:
                views.append(_finding_view(finding, context))
        return views


def get_project_finding(project_id: str, finding_id: int) -> dict | None:
    with _research_session() as session:
        if session is None:
            return None
        finding = session.get(Finding, finding_id)
        if finding is None or finding.evidence_run_id is None:
            return None
        context = _verified_finding_run(
            session, project_id, finding.evidence_run_id
        )
        return _finding_view(finding, context) if context is not None else None


def _finding_confidence(evidence: dict) -> float:
    results = evidence.get("results")
    instruments = results.get("instruments", []) if isinstance(results, dict) else []
    trades = 0
    if isinstance(instruments, list):
        for item in instruments:
            qualification = item.get("qualification") if isinstance(item, dict) else None
            value = qualification.get("trades") if isinstance(qualification, dict) else None
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                trades += value
    return confidence_from_trades(trades)


def create_project_finding(
    project_id: str, run_id: int, *, statement: str, polarity: str
) -> dict | None:
    with _research_session() as session:
        if session is None:
            return None
        context = _verified_finding_run(session, project_id, run_id)
        if context is None:
            return None
        finding = Finding(
            hypothesis_id=context["spec"].hypothesis_id,
            statement=statement,
            polarity=polarity,
            confidence=_finding_confidence(context["evidence"]),
            evidence_run_id=run_id,
        )
        session.add(finding)
        session.commit()
        return _finding_view(finding, context)


def _after_finding_successor_insert(_session, _successor) -> None:
    """Failure-injection seam proving successor/CAS transaction atomicity."""


def revise_project_finding(
    project_id: str, finding_id: int, *, statement: str, polarity: str
) -> dict | None:
    with _research_session() as session:
        if session is None:
            return None
        original = session.get(Finding, finding_id)
        if original is None or original.evidence_run_id is None:
            return None
        context = _verified_finding_run(
            session, project_id, original.evidence_run_id
        )
        if context is None:
            return None
        if original.superseded_by is not None:
            raise FindingRevisionConflict(finding_id)
        successor = Finding(
            hypothesis_id=original.hypothesis_id,
            statement=statement,
            polarity=polarity,
            confidence=_finding_confidence(context["evidence"]),
            evidence_run_id=original.evidence_run_id,
        )
        session.add(successor)
        session.flush()
        _after_finding_successor_insert(session, successor)
        claimed = session.execute(
            update(Finding)
            .where(Finding.id == finding_id, Finding.superseded_by.is_(None))
            .values(superseded_by=successor.id)
            .execution_options(synchronize_session=False)
        )
        if claimed.rowcount != 1:
            session.rollback()
            raise FindingRevisionConflict(finding_id)
        session.commit()
        session.refresh(original)
        return {
            "superseded": _finding_view(original, context),
            "successor": _finding_view(successor, context),
        }


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


def verified_graph_decision(*, project_id: str, graph_identifier: str,
                            graph_version: int) -> dict | None:
    """The verified approval for one exact graph version, or None.

    The single cross-plane read a managed shadow deployment makes, and it makes it once —
    at activation — never on a control-loop boundary. Read-only, through the same session
    seam as every other bridge here (hard invariant 5: the research plane is isolated and
    only read-only bridges cross it).

    "Verified" is load-bearing. A run's terminal evidence and a candidate's decision are
    both content-addressed envelopes; `_graph_run_view` and `_verified_candidate_decision`
    re-derive those addresses rather than trusting the stored fields, and anything that
    fails to verify raises rather than being reported as an approval. So a caller that
    receives a dict here has been told something checked, not something claimed.

    Returns None — rather than raising — when nothing approves the artefact, because "no
    approval exists" is an ordinary answer for a graph nobody has decided on yet. The
    caller decides what to do about it; `shadow_deployments.activate` refuses.
    """
    for view in list_graph_runs(project_id):
        graph = view.get("graph") or {}
        if (graph.get("identifier") != graph_identifier
                or graph.get("version") != graph_version):
            continue
        candidate = view.get("candidate") or {}
        decision = candidate.get("decision") or {}
        if decision.get("decision") != "approved":
            continue
        return {
            "run_id": view.get("run_id"),
            "candidate_id": candidate.get("candidate_id") or candidate.get("id"),
            "project_id": graph.get("project_id"),
            "graph_identifier": graph.get("identifier"),
            "graph_version": graph.get("version"),
            "content_address": graph.get("content_address"),
            "decision": "approved",
        }
    return None


#: The candidate decision vocabulary, as `decide_project_candidate` writes it. Named here
#: so an observability caller reuses it instead of inventing a parallel status model.
CANDIDATE_DECISIONS = frozenset({"approved", "rejected"})


def graph_decision_history(*, project_id: str, graph_identifier: str,
                           graph_version: int) -> list[dict] | None:
    """Every verified decision recorded about one exact graph version, newest run first.

    The narrow read the execution cockpit needs to tell an operator "the research view has
    moved since this was admitted". It is deliberately raw: it reports what research says
    and classifies nothing. Comparing a decision against the one that admitted a deployment
    is an execution-plane question and is answered there (`app/engine/cockpit.py`), because
    this bridge must not learn what a deployment is.

    **Read-only, and observability only.** ADR 0013: research approval is an admission
    prerequisite consumed at activation. Nothing derived from this function may pause,
    retire, refuse or downgrade an active deployment.

    Returns `None` — not `[]` — when the research plane cannot be read, so a caller can say
    *unavailable* rather than inferring "nothing contradicts this". The two are different
    facts and collapsing them is exactly the inference an operator must not be handed.
    A candidate whose stored decision fails verification is skipped rather than reported: an
    unverifiable envelope is not evidence of anything, in either direction.
    """
    if not os.path.exists(research_db_path()):
        return None
    try:
        views = list_graph_runs(project_id)
    except Exception:
        return None

    out: list[dict] = []
    for view in views:
        graph = view.get("graph") or {}
        if (graph.get("identifier") != graph_identifier
                or graph.get("version") != graph_version):
            continue
        candidate = view.get("candidate") or {}
        envelope = candidate.get("decision") or {}
        evidence = envelope.get("evidence") if isinstance(envelope, dict) else None
        verdict = envelope.get("decision") if isinstance(envelope, dict) else None
        if verdict is None and isinstance(evidence, dict):
            verdict = evidence.get("decision")
        if verdict not in CANDIDATE_DECISIONS:
            continue
        out.append({
            "run_id": view.get("run_id"),
            "candidate_id": candidate.get("candidate_id") or candidate.get("id"),
            "decision": verdict,
            "decided_at": (evidence or {}).get("decided_at"),
            "reason": (evidence or {}).get("reason"),
            "graph_content_address": graph.get("content_address"),
        })
    return out
