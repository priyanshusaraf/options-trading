"""Read side of the approve→deploy bridge: the execution/API plane reading the
research plane's PromotionCandidate ledger.

This is the ONE intended coupling between the two planes, and it runs in this
direction only — the API surfaces research output for a human to approve. The
research process never reaches back the other way (its guards forbid importing any
execution / order / broker / runner code). Nothing here touches capital: the only
write is `approve_candidate`, which stamps the human's approval onto the candidate
row (research bookkeeping), and the deploy that follows writes declarative config to
the execution ledger, never an order.

research.db lives at `PT_RESEARCH_DB_PATH` (default `research.db`); if it does not
exist yet (no nightly has run) every read degrades to empty and deploy reports the
candidate as missing — the cockpit simply shows no promotions.
"""
from __future__ import annotations

import contextlib
import dataclasses
import json
import os

from research.config import research_db_path
from research.domain.base import make_engine, make_sessionmaker
from research.domain.models import (
    ExperimentRun,
    ExperimentSpec,
    GeneratedStrategyRecord,
    PromotionCandidate,
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
    """One candidate's full view, or None if research.db or the row is absent."""
    with _research_session() as session:
        if session is None:
            return None
        try:
            c = session.get(PromotionCandidate, candidate_id)
            return _view(session, c) if c is not None else None
        except Exception:
            return None


def approve_candidate(candidate_id: int, git_sha: str = "") -> bool:
    """Stamp a human approval onto the candidate (status → approved, + git sha). The
    sole write to research.db from the execution plane; touches research bookkeeping
    only — never capital. Returns False if the candidate (or research.db) is absent."""
    with _research_session() as session:
        if session is None:
            return False
        try:
            c = session.get(PromotionCandidate, candidate_id)
            if c is None:
                return False
            c.status = "approved"
            c.approved_git_sha = git_sha or None
            session.commit()
            return True
        except Exception:
            session.rollback()
            return False
