"""
Portfolio endpoints — holdings, PnL, risk, rebalancing, and Kite OAuth flow.
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from backend.app.portfolio.tracker import PortfolioTracker
from backend.app.core.config import get_settings
from backend.app.core.logging import logger

router = APIRouter(prefix="/portfolio", tags=["Portfolio"])
_tracker = PortfolioTracker()


# ── Holdings CRUD ─────────────────────────────────────────────────────────────

class HoldingRequest(BaseModel):
    symbol: str
    quantity: float
    avg_cost: float
    exchange: str = "NSE"


@router.get("/")
def get_portfolio():
    """Get full portfolio view with PnL, sector exposure, and risk metrics."""
    try:
        view = _tracker.get_portfolio_view()
        return {
            "data_source": view.data_source,
            "summary": {
                "total_invested": view.total_invested,
                "total_market_value": view.total_market_value,
                "total_unrealized_pnl": view.total_unrealized_pnl,
                "total_unrealized_pnl_pct": round(view.total_unrealized_pnl_pct * 100, 2),
                "portfolio_var_95": view.portfolio_var_95,
                "portfolio_beta": view.portfolio_beta,
            },
            "positions": [
                {
                    "symbol": p.symbol,
                    "quantity": p.quantity,
                    "avg_cost": p.avg_cost,
                    "current_price": p.current_price,
                    "market_value": round(p.market_value, 2),
                    "unrealized_pnl": round(p.unrealized_pnl, 2),
                    "unrealized_pnl_pct": round(p.unrealized_pnl_pct * 100, 2),
                    "weight_pct": p.weight_pct,
                    "sector": p.sector,
                }
                for p in view.positions
            ],
            "sector_exposure": view.sector_exposure,
            "top_positions": view.top_positions,
            "rebalancing_suggestions": view.rebalancing_suggestions,
        }
    except Exception as e:
        logger.error(f"Portfolio view failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/holdings", status_code=201)
def add_holding(body: HoldingRequest):
    """Add or update a holding in the manual portfolio."""
    holding = _tracker.add_holding(
        symbol=body.symbol.upper(),
        quantity=body.quantity,
        avg_cost=body.avg_cost,
        exchange=body.exchange,
    )
    return {
        "symbol": holding.symbol,
        "quantity": holding.quantity,
        "avg_cost": holding.avg_cost,
        "exchange": holding.exchange,
    }


@router.delete("/holdings/{symbol}", status_code=204)
def remove_holding(symbol: str):
    """Remove a holding from the manual portfolio."""
    if not _tracker.remove_holding(symbol.upper()):
        raise HTTPException(status_code=404, detail=f"No holding for {symbol}")


@router.get("/holdings")
def list_holdings():
    """List all manual portfolio holdings."""
    rows = _tracker.list_holdings()
    return {
        "count": len(rows),
        "holdings": [
            {
                "symbol": r.symbol,
                "exchange": r.exchange,
                "quantity": r.quantity,
                "avg_cost": r.avg_cost,
                "instrument_type": r.instrument_type,
            }
            for r in rows
        ],
    }


# ── Kite OAuth ────────────────────────────────────────────────────────────────

@router.get("/kite/login-url")
def kite_login_url():
    """Generate Kite OAuth login URL."""
    settings = get_settings()
    if not settings.kite_api_key:
        raise HTTPException(status_code=503, detail="Kite API key not configured in .env")
    try:
        from kiteconnect import KiteConnect
        kite = KiteConnect(api_key=settings.kite_api_key)
        return {"login_url": kite.login_url()}
    except ImportError:
        raise HTTPException(status_code=503, detail="kiteconnect not installed")


@router.post("/kite/session")
def kite_create_session(request_token: str = Query(...)):
    """
    Exchange request_token for access_token after OAuth redirect.
    Store access_token in settings / env for subsequent calls.
    """
    settings = get_settings()
    try:
        from kiteconnect import KiteConnect
        kite = KiteConnect(api_key=settings.kite_api_key)
        session = kite.generate_session(request_token, api_secret=settings.kite_api_secret)
        access_token = session["access_token"]
        # Persist to .env
        env_path = settings.data_dir.parent / ".env"
        if env_path.exists():
            content = env_path.read_text()
            if "KITE_ACCESS_TOKEN=" in content:
                import re
                content = re.sub(r"KITE_ACCESS_TOKEN=.*", f"KITE_ACCESS_TOKEN={access_token}", content)
            else:
                content += f"\nKITE_ACCESS_TOKEN={access_token}\n"
            env_path.write_text(content)
        return {"access_token": access_token, "message": "Session created. Restart the server to apply."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/kite/status")
def kite_status():
    """Check if Kite API is connected."""
    return {
        "connected": _tracker.kite.is_connected(),
        "has_api_key": bool(get_settings().kite_api_key),
        "has_access_token": bool(get_settings().kite_access_token),
    }
