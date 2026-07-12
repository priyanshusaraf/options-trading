"""Portfolio API — watchlists, the strategy archive, and the approve→deploy bridge.

These endpoints expose the portfolio-management layer to the cockpit. Deploy WRITES
DECLARATIVE CONFIG ONLY (a watchlist + memberships + an archive transition) and is STAGED:
it takes effect on the next engine restart, after which the owner re-ARMs. Nothing here
places an order or touches capital. Kept in its own router (like backtest_routes) so the
new subsystem's surface stays cohesive.
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.core import research_read
from app.core import strategy_archive as arch
from app.core import watchlists as wl
from app.core.deploy_bridge import DeployRequest, deploy, preview_deploy
from app.db.session import SessionLocal

router = APIRouter()


class ProposalIn(BaseModel):
    instrument_key: str
    score: float = 0.0


class DeployIn(BaseModel):
    watchlist_name: str
    strategy_key: str
    proposals: list[ProposalIn]
    source: str = "builtin"
    interval: str | None = None
    dry_run: bool = False


class StatusIn(BaseModel):
    status: str


class PromotionDeployIn(BaseModel):
    watchlist_name: str | None = None
    dry_run: bool = False


@router.get("/api/portfolio/promotions")
def get_promotions():
    """Pending research promotions awaiting a human decision — read from research.db
    read-only, each carrying its validated universe + a plain-language explanation."""
    return {"promotions": research_read.list_pending_promotions()}


@router.post("/api/portfolio/promotions/{candidate_id}/deploy")
def deploy_promotion(candidate_id: int, body: PromotionDeployIn):
    """Approve a research candidate and STAGE its validated universe into a watchlist.
    The instruments and their DSR (the conflict-resolution score) come straight from
    the candidate; nothing here places an order. On commit the candidate is recorded
    approved. `dry_run` previews the assignment/conflicts without writing."""
    cand = research_read.get_promotion(candidate_id)
    if cand is None:
        return {"error": f"no pending promotion #{candidate_id}"}
    name = body.watchlist_name or cand["strategy_key"]
    req = DeployRequest(
        watchlist_name=name, strategy_key=cand["strategy_key"],
        proposals=[(v["instrument"], v.get("dsr", 0.0)) for v in cand["validated_universe"]],
        source="research", interval=cand.get("interval"))
    with SessionLocal() as s:
        if body.dry_run:
            prev = preview_deploy(s, req)
            return {"dry_run": True, "candidate_id": candidate_id,
                    "watchlist": prev.watchlist_name, "strategy_key": prev.strategy_key,
                    "accepted": prev.accepted, "rejected": prev.rejected}
        res = deploy(s, req)
        s.commit()
    research_read.approve_candidate(candidate_id, git_sha="")
    return {"dry_run": False, "candidate_id": candidate_id, "watchlist_id": res.watchlist_id,
            "assigned": res.assigned, "rejected": res.rejected,
            "note": "staged — effective on next engine restart, then ARM"}


@router.get("/api/portfolio/watchlists")
def get_watchlists():
    with SessionLocal() as s:
        return {"watchlists": wl.list_watchlists(s)}


@router.get("/api/portfolio/archive")
def get_archive():
    with SessionLocal() as s:
        return {"strategies": arch.list_archive(s)}


@router.post("/api/portfolio/deploy")
def portfolio_deploy(body: DeployIn):
    """Preview (dry_run) or commit a deploy. On commit the assignment is STAGED — it
    loads on the next engine restart, then the owner ARMs."""
    req = DeployRequest(
        watchlist_name=body.watchlist_name, strategy_key=body.strategy_key,
        proposals=[(p.instrument_key, p.score) for p in body.proposals],
        source=body.source, interval=body.interval)
    with SessionLocal() as s:
        if body.dry_run:
            prev = preview_deploy(s, req)
            return {"dry_run": True, "watchlist": prev.watchlist_name,
                    "strategy_key": prev.strategy_key, "accepted": prev.accepted,
                    "rejected": prev.rejected}
        res = deploy(s, req)
        s.commit()
        return {"dry_run": False, "watchlist_id": res.watchlist_id,
                "assigned": res.assigned, "rejected": res.rejected,
                "note": "staged — effective on next engine restart, then ARM"}


@router.post("/api/portfolio/watchlists/{name}/status")
def set_watchlist_status(name: str, body: StatusIn):
    if body.status not in ("active", "paused", "archived"):
        return {"error": f"bad status {body.status!r}"}
    with SessionLocal() as s:
        w = wl.get_watchlist(s, name)
        if w is None:
            return {"error": f"no watchlist named {name!r}"}
        w.status = body.status
        s.commit()
        return {"name": name, "status": w.status}


@router.post("/api/portfolio/archive/{strategy_key}/status")
def set_archive_status(strategy_key: str, body: StatusIn):
    """Move a strategy through its lifecycle (probation / on_hold / retired / revive)."""
    with SessionLocal() as s:
        try:
            rec = arch.set_status(s, strategy_key, body.status)
            s.commit()
            return rec.to_dict()
        except ValueError as e:
            return {"error": str(e)}
