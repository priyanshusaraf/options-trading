"""Portfolio API — watchlists, the strategy archive, and promotion preview.

These endpoints expose the portfolio-management layer to the cockpit. Deploy WRITES
DECLARATIVE CONFIG ONLY (a watchlist + memberships + an archive transition) and is STAGED:
it takes effect on the next engine restart, after which the owner re-ARMs. Nothing here
places an order or touches capital. Candidate decisions are project-owned research writes;
the old combined approval/deploy commit is closed. Kept in its own router (like
backtest_routes) so the subsystem's surface stays cohesive.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core import research_read
from app.core import strategy_archive as arch
from app.core import watchlists as wl
from app.core.config import get_settings
from app.core.deploy_bridge import DeployRequest, deploy, preview_deploy
from app.db.session import SessionLocal
from app.api.principal import Principal, get_principal, owner_id_for


def _research_gate() -> None:
    """Freeze gate: every endpoint on this router 403s unless the research plane
    is enabled (PT_RESEARCH_ENABLED). A request-time dependency rather than
    conditional mounting, because main.py mounts routers at import time — the
    dependency keeps the flag testable/flippable without a module reload and
    matches how tests monkeypatch the cached Settings instance."""
    if not get_settings().research_enabled:
        raise HTTPException(status_code=403,
                            detail="research plane disabled (set PT_RESEARCH_ENABLED=1)")


router = APIRouter(dependencies=[Depends(_research_gate)])


@router.get("/api/paper-portfolio")
def get_paper_portfolio(principal: Principal = Depends(get_principal)):
    from app.core.paper_portfolio import read_paper_portfolio

    with SessionLocal() as session:
        return read_paper_portfolio(session, owner_id=owner_id_for(principal))


class ProposalIn(BaseModel):
    instrument_key: str
    score: float = 0.0


class DeployIn(BaseModel):
    watchlist_name: str
    strategy_key: str
    proposals: list[ProposalIn]
    source: str = "builtin"
    interval: str | None = None
    admission_address: str
    broker_account_id: str
    dry_run: bool = False


class StatusIn(BaseModel):
    status: str


class PromotionDeployIn(BaseModel):
    watchlist_name: str | None = None
    dry_run: bool = False


@router.get("/api/portfolio/promotions")
def get_promotions(principal: Principal = Depends(get_principal)):
    """Pending research promotions awaiting a human decision — read from research.db
    read-only, each carrying its validated universe + a plain-language explanation."""
    return {"promotions": research_read.list_pending_promotions(
        owner_id=owner_id_for(principal))}


@router.post("/api/portfolio/promotions/{candidate_id}/deploy")
def deploy_promotion(candidate_id: int, body: PromotionDeployIn,
                     principal: Principal = Depends(get_principal)):
    """Preview the legacy candidate-to-watchlist bridge without committing it.

    S4.2 separates the research decision from any application deployment state. The
    committed combined path is therefore closed; a later workflow may consume an
    approved candidate to create a draft, disarmed deployment explicitly.
    """
    cand = research_read.get_promotion(candidate_id, owner_id=owner_id_for(principal))
    if cand is None:
        return JSONResponse(
            status_code=409,
            content={
                "code": "PROMOTION_NOT_PENDING",
                "message": "promotion is not pending human approval",
            },
        )
    name = body.watchlist_name or cand["strategy_key"]
    req = DeployRequest(
        watchlist_name=name, strategy_key=cand["strategy_key"],
        proposals=[(v["instrument"], v.get("dsr", 0.0)) for v in cand["validated_universe"]],
        source="research", interval=cand.get("interval"),
        admission_address=cand.get("admission_address", ""),
        broker_account_id="")
    with SessionLocal() as s:
        if body.dry_run:
            prev = preview_deploy(s, req, owner_id=owner_id_for(principal))
            return {"dry_run": True, "candidate_id": candidate_id,
                    "watchlist": prev.watchlist_name, "strategy_key": prev.strategy_key,
                    "accepted": prev.accepted, "rejected": prev.rejected}
    return JSONResponse(
        status_code=409,
        content={
            "code": "PROMOTION_DECISION_REQUIRED",
            "message": (
                "record a project-owned research decision before entering a "
                "separate deployment workflow"
            ),
        },
    )


@router.get("/api/portfolio/watchlists")
def get_watchlists(principal: Principal = Depends(get_principal)):
    with SessionLocal() as s:
        return {"watchlists": wl.list_watchlists(s, owner_id=owner_id_for(principal))}


@router.get("/api/portfolio/archive")
def get_archive(principal: Principal = Depends(get_principal)):
    with SessionLocal() as s:
        return {"strategies": arch.list_archive(s, owner_id=owner_id_for(principal))}


@router.post("/api/portfolio/deploy")
def portfolio_deploy(body: DeployIn, principal: Principal = Depends(get_principal)):
    """Preview (dry_run) or commit a deploy. On commit the assignment is STAGED — it
    loads on the next engine restart, then the owner ARMs."""
    req = DeployRequest(
        watchlist_name=body.watchlist_name, strategy_key=body.strategy_key,
        proposals=[(p.instrument_key, p.score) for p in body.proposals],
        source=body.source, interval=body.interval,
        admission_address=body.admission_address,
        broker_account_id=body.broker_account_id)
    with SessionLocal() as s:
        if body.dry_run:
            prev = preview_deploy(s, req, owner_id=owner_id_for(principal))
            return {"dry_run": True, "watchlist": prev.watchlist_name,
                    "strategy_key": prev.strategy_key, "accepted": prev.accepted,
                    "rejected": prev.rejected}
        res = deploy(s, req, owner_id=owner_id_for(principal))
        s.commit()
        return {"dry_run": False, "watchlist_id": res.watchlist_id,
                "assigned": res.assigned, "rejected": res.rejected,
                "note": "staged — effective on next engine restart, then ARM"}


@router.post("/api/portfolio/watchlists/{name}/status")
def set_watchlist_status(name: str, body: StatusIn, principal: Principal = Depends(get_principal)):
    if body.status not in ("active", "paused", "archived"):
        return {"error": f"bad status {body.status!r}"}
    with SessionLocal() as s:
        w = wl.get_watchlist(s, name, owner_id=owner_id_for(principal))
        if w is None:
            return {"error": f"no watchlist named {name!r}"}
        w.status = body.status
        s.commit()
        return {"name": name, "status": w.status}


@router.post("/api/portfolio/archive/{strategy_key}/status")
def set_archive_status(strategy_key: str, body: StatusIn, principal: Principal = Depends(get_principal)):
    """Move a strategy through its lifecycle (probation / on_hold / retired / revive)."""
    with SessionLocal() as s:
        try:
            rec = arch.set_status(s, strategy_key, body.status, owner_id=owner_id_for(principal))
            s.commit()
            return rec.to_dict()
        except ValueError as e:
            return {"error": str(e)}
