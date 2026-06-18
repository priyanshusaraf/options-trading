"""
Alerts API — CRUD + evaluation endpoints.
"""
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.app.intelligence.alerts.engine import AlertsEngine, AlertRequest, AlertType

router = APIRouter(prefix="/alerts", tags=["Alerts"])

_engine = AlertsEngine()


# ── Request / Response models ─────────────────────────────────────────────────

class CreateAlertBody(BaseModel):
    symbol: str
    alert_type: AlertType
    threshold: float
    condition: str = ""
    notes: str = ""


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/", summary="List all alerts")
def list_alerts(
    symbol: Optional[str] = None,
    triggered: Optional[bool] = None,
):
    alerts = _engine.list_alerts(symbol=symbol, triggered=triggered)
    return [vars(a) for a in alerts]


@router.post("/", summary="Create a new alert", status_code=201)
def create_alert(body: CreateAlertBody):
    req = AlertRequest(
        symbol=body.symbol,
        alert_type=body.alert_type,
        threshold=body.threshold,
        condition=body.condition,
        notes=body.notes,
    )
    result = _engine.create(req)
    return vars(result)


@router.get("/{alert_id}", summary="Get a specific alert")
def get_alert(alert_id: int):
    a = _engine.get(alert_id)
    if not a:
        raise HTTPException(status_code=404, detail="Alert not found")
    return vars(a)


@router.delete("/{alert_id}", summary="Delete an alert")
def delete_alert(alert_id: int):
    if not _engine.delete(alert_id):
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"message": "Alert deleted"}


@router.post("/{alert_id}/reset", summary="Re-arm a triggered alert")
def reset_alert(alert_id: int):
    result = _engine.reset(alert_id)
    if not result:
        raise HTTPException(status_code=404, detail="Alert not found")
    return vars(result)


@router.post("/evaluate/all", summary="Manually trigger evaluation of all pending alerts")
def evaluate_all():
    triggered = _engine.evaluate_all()
    return {
        "evaluated": True,
        "newly_triggered": len(triggered),
        "alerts": [vars(a) for a in triggered],
    }


@router.post("/evaluate/{symbol}", summary="Evaluate alerts for a specific symbol")
def evaluate_symbol(symbol: str):
    triggered = _engine.evaluate_symbol(symbol)
    return {
        "symbol": symbol.upper(),
        "newly_triggered": len(triggered),
        "alerts": [vars(a) for a in triggered],
    }


@router.get("/triggered/recent", summary="Get recently triggered alerts")
def recent_triggered(limit: int = 20):
    alerts = _engine.list_alerts(triggered=True)
    alerts_sorted = sorted(
        alerts,
        key=lambda a: a.triggered_at or "",
        reverse=True,
    )
    return [vars(a) for a in alerts_sorted[:limit]]
