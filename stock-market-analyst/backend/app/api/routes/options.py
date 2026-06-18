"""
Options & Derivatives endpoints.
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from backend.app.analytics.options.engine import OptionsEngine, implied_vol, _bs_greeks
from backend.app.data.ingestion import DataIngestionManager
from backend.app.core.logging import logger

router = APIRouter(prefix="/options", tags=["Options"])

_options = OptionsEngine()
_ingestion = DataIngestionManager()


@router.get("/chain/{symbol}")
def options_chain(
    symbol: str,
    spot: Optional[float] = Query(None, description="Spot price override"),
    exchange: str = Query("NSE"),
):
    """
    Fetch and analyze the options chain for a symbol.
    Returns IV skew, PCR, max pain, smart money signal.
    """
    # Fetch spot price if not provided
    if spot is None:
        try:
            yf_sym = f"{symbol.upper()}.NS" if exchange == "NSE" else symbol.upper()
            df = _ingestion.get_ohlcv(yf_sym)
            spot = float(df["close"].iloc[-1]) if not df.empty else 0.0
        except Exception:
            spot = 0.0

    if spot <= 0:
        raise HTTPException(status_code=400, detail="Could not determine spot price. Pass ?spot=<price>")

    try:
        result = _options.analyze(symbol.upper(), spot_price=spot)
        return {
            "symbol": symbol.upper(),
            "spot_price": result.spot_price,
            "expiry": str(result.expiry),
            "analytics": {
                "pcr_volume": round(result.pcr_volume, 3),
                "pcr_oi": round(result.pcr_oi, 3),
                "max_pain": round(result.max_pain, 2),
                "atm_iv": round(result.atm_iv, 4),
                "iv_skew": round(result.iv_skew, 4),
                "vol_breakout_prob": round(result.vol_breakout_prob, 3),
            },
            "smart_money": {
                "signal": result.smart_money_signal,
                "reasons": result.signal_reasons,
            },
            "chain_summary": {
                "total_strikes": len(set(r.strike for r in result.chain)),
                "call_count": sum(1 for r in result.chain if r.option_type == "CE"),
                "put_count": sum(1 for r in result.chain if r.option_type == "PE"),
            },
        }
    except Exception as e:
        logger.error(f"Options chain failed for {symbol}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/iv-surface/{symbol}")
def iv_surface(symbol: str, spot: Optional[float] = Query(None)):
    """Return the implied volatility surface (strike × expiry grid)."""
    if spot is None:
        try:
            yf_sym = f"{symbol.upper()}.NS"
            df = _ingestion.get_ohlcv(yf_sym)
            spot = float(df["close"].iloc[-1]) if not df.empty else 0.0
        except Exception:
            spot = 0.0
    if spot <= 0:
        raise HTTPException(status_code=400, detail="Cannot determine spot price")

    result = _options.analyze(symbol.upper(), spot_price=spot)
    surface = _options.compute_iv_surface(symbol.upper(), spot, result.chain)

    if surface.empty:
        return {"symbol": symbol, "surface": {}}

    return {
        "symbol": symbol.upper(),
        "spot": spot,
        "strikes": list(surface.index),
        "expiries": list(surface.columns),
        "iv_matrix": surface.where(surface.notna(), None).to_dict(),
    }


@router.get("/greeks")
def compute_greeks(
    spot: float = Query(...),
    strike: float = Query(...),
    expiry_days: int = Query(..., ge=1),
    iv: float = Query(..., ge=0.01),
    option_type: str = Query("CE", pattern="^(CE|PE)$"),
    risk_free_rate: float = Query(0.065),
):
    """Compute Black-Scholes Greeks for given parameters."""
    T = expiry_days / 365.0
    flag = "c" if option_type == "CE" else "p"
    from backend.app.analytics.options.engine import _bs_price
    price = _bs_price(spot, strike, T, risk_free_rate, iv, flag)
    greeks = _bs_greeks(spot, strike, T, risk_free_rate, iv, flag)
    return {
        "price": round(price, 4),
        "greeks": {k: round(v, 6) for k, v in greeks.items()},
        "inputs": {"spot": spot, "strike": strike, "T_years": T, "iv": iv, "flag": flag},
    }


@router.get("/implied-vol")
def compute_iv(
    market_price: float = Query(...),
    spot: float = Query(...),
    strike: float = Query(...),
    expiry_days: int = Query(..., ge=1),
    option_type: str = Query("CE", pattern="^(CE|PE)$"),
    risk_free_rate: float = Query(0.065),
):
    """Back-compute implied volatility from market price."""
    T = expiry_days / 365.0
    flag = "c" if option_type == "CE" else "p"
    iv = implied_vol(market_price, spot, strike, T, risk_free_rate, flag)
    if iv is None:
        raise HTTPException(status_code=422, detail="Could not compute IV (check inputs)")
    return {"implied_vol": round(iv, 6), "implied_vol_pct": round(iv * 100, 3)}
