"""Approve→Deploy bridge — the human-gated path from a research candidate to a live
watchlist.

Deploying a candidate is the ONLY way research output reaches capital, and it is always
an explicit human action. The bridge writes *declarative config* — a watchlist, its
memberships, and a strategy-archive transition — and nothing else. It never places an
order, never touches positions or capital_state, and never bypasses the ARM / kill /
daily-loss-halt stack. Deployment is STAGED: the assignment takes effect the next time
the engine starts (it reloads per-instrument config), after which the owner re-ARMs.

Conflict resolution runs at deploy time: an instrument already committed to another
watchlist is an incumbent and is left running its existing strategy; the new watchlist
simply doesn't take it. `preview_deploy` reports exactly this without writing, so the
owner confirms with full sight of what will and won't be assigned.
"""
from __future__ import annotations

import dataclasses

from sqlalchemy import select

from app.core import deployments
from app.core import strategy_archive as archive
from app.core import watchlists as wl
from app.db.models import BrokerAccount


@dataclasses.dataclass
class DeployRequest:
    watchlist_name: str
    strategy_key: str
    proposals: list                 # [(instrument_key, score), ...]
    admission_address: str
    broker_account_id: str
    source: str = "builtin"         # builtin | generated
    interval: str | None = None


@dataclasses.dataclass
class DeployPreview:
    watchlist_name: str
    strategy_key: str
    accepted: list                  # instrument_keys that would be assigned
    rejected: list                  # [{instrument, watchlist_id, reason}]


@dataclasses.dataclass
class DeployResult:
    watchlist_id: int
    deployment_id: int
    assigned: list
    rejected: list


def _resolve(session, target_id: int, req: DeployRequest, *, owner_id: str):
    """Run conflict resolution for `req` against the current incumbents, treating any
    instrument already in a DIFFERENT watchlist as an untouchable incumbent."""
    incumbents = {k: wid for k, wid in wl.membership_map(session, owner_id=owner_id).items() if wid != target_id}
    proposals = [wl.Proposal(watchlist_id=target_id, instrument_key=k, score=score)
                 for k, score in req.proposals]
    return wl.resolve_conflicts(incumbents, proposals)


def preview_deploy(session, req: DeployRequest, *, owner_id: str) -> DeployPreview:
    """What deploying `req` would do — no writes. Uses the target watchlist's id if it
    already exists, else a sentinel (0); the id only affects dispute tie-breaks, which do
    not arise within a single watchlist's deploy."""
    existing = wl.get_watchlist(session, req.watchlist_name, owner_id=owner_id)
    target_id = existing.id if existing else 0
    res = _resolve(session, target_id, req, owner_id=owner_id)
    return DeployPreview(req.watchlist_name, req.strategy_key,
                         accepted=sorted(res.assign.keys()), rejected=res.rejected)


def deploy(session, req: DeployRequest, *, owner_id: str) -> DeployResult:
    """Commit the deploy: create/reuse the target watchlist, assign the instruments that
    clear conflict resolution, and record the strategy as `running` in the archive.
    Idempotent — re-deploying the same request reuses the watchlist and reassigns the same
    winners in place."""
    admitted = deployments._require_current_deployment_admission(
        session, owner_id=owner_id, strategy_key=req.strategy_key,
        admission_address=req.admission_address, params={})
    account = session.scalar(select(BrokerAccount).where(
        BrokerAccount.owner_id == owner_id,
        BrokerAccount.broker_account_id == req.broker_account_id,
        BrokerAccount.status == "active",
    ))
    if account is None:
        raise ValueError("ADMISSION_REQUIRED")
    # Checked here as well as in `create_watchlist`: the reuse branch below reassigns an
    # existing watchlist's strategy in place and never passes through the constructor, so
    # a gate on creation alone would let a redeploy install what a first deploy refused.
    from app.core.execution_binding import assert_may_execute
    assert_may_execute(req.strategy_key, owner_id=owner_id)
    target = wl.get_watchlist(session, req.watchlist_name, owner_id=owner_id)
    if target is None:
        target = wl.create_watchlist(session, req.watchlist_name, req.strategy_key, owner_id=owner_id,
                                     interval=req.interval)
    session.flush()

    deployment = deployments.get_by_name(
        session, f"watchlist:{target.id}", owner_id=owner_id,
        broker_account_id=account.broker_account_id)
    if deployment is None:
        deployment = deployments.create_deployment(
            session, f"watchlist:{target.id}", strategy_key=req.strategy_key,
            strategy_version=admitted.strategy.version,
            admission_address=admitted.admission_address,
            owner_id=owner_id, broker_account_id=account.broker_account_id,
            universe_mode="watchlist", watchlist_id=target.id, params={})
    elif (deployment.strategy_key != req.strategy_key
          or deployment.admission_address != admitted.admission_address):
        raise ValueError("ARTEFACT_MISMATCH")
    target.strategy_key = req.strategy_key
    session.flush()

    res = _resolve(session, target.id, req, owner_id=owner_id)
    wl.apply_resolution(session, res, owner_id=owner_id)

    archive.record_strategy(session, req.strategy_key, owner_id=owner_id, source=req.source)
    archive.set_status(session, req.strategy_key, "running", owner_id=owner_id,
                       deployed_watchlist_id=target.id)
    return DeployResult(watchlist_id=target.id, deployment_id=deployment.id,
                        assigned=sorted(res.assign.keys()),
                        rejected=res.rejected)
