"""
Commodity Linkage endpoints.
"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from backend.app.analytics.macro.commodity_linker import CommodityLinker, COMMODITY_TICKERS
from backend.app.core.logging import logger

router = APIRouter(prefix="/commodities", tags=["Commodities"])
_linker = CommodityLinker()


@router.get("/")
def list_commodities():
    """List all tracked commodities and their tickers."""
    return {
        "commodities": [
            {"name": name, "ticker": ticker}
            for name, ticker in COMMODITY_TICKERS.items()
        ]
    }


@router.get("/linkage/{symbol}")
def commodity_linkage(
    symbol: str,
    sector: Optional[str] = Query(None),
    days: int = Query(756, ge=60, le=1825),
):
    """
    Analyze which commodities drive a stock's price.
    Returns correlations, lag analysis, Granger causality, and relationship type.
    """
    try:
        result = _linker.analyze(symbol=symbol.upper(), sector=sector, days=days)
        return {
            "symbol": result.symbol,
            "sector": result.sector,
            "risk_exposure": result.risk_exposure,
            "top_commodity": result.top_commodity,
            "top_correlation": result.top_correlation,
            "links": [
                {
                    "commodity": l.commodity_name,
                    "ticker": l.commodity_ticker,
                    "corr_30d": l.corr_30d,
                    "corr_90d": l.corr_90d,
                    "corr_252d": l.corr_252d,
                    "best_lag_days": l.best_lag_days,
                    "best_lag_corr": l.best_lag_corr,
                    "lag_direction": l.lag_direction,
                    "granger_pvalue": l.granger_pvalue,
                    "granger_significant": l.granger_significant,
                    "relationship_type": l.relationship_type,
                    "is_significant": l.is_significant,
                }
                for l in result.links
            ],
        }
    except Exception as e:
        logger.error(f"Commodity linkage failed for {symbol}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/market-overview")
def commodity_market_overview(days: int = Query(30, ge=7, le=365)):
    """
    Return recent returns for all tracked commodities.
    Useful for spotting commodity regime changes.
    """
    from datetime import date, timedelta
    from backend.app.data.ingestion import DataIngestionManager
    ingestion = DataIngestionManager()
    end = date.today()
    start = end - timedelta(days=days)

    results = []
    for name, ticker in COMMODITY_TICKERS.items():
        try:
            df = ingestion.get_ohlcv(ticker, start, end)
            if df.empty:
                continue
            ret = float((df["close"].iloc[-1] / df["close"].iloc[0]) - 1)
            vol = float(df["close"].pct_change().dropna().std() * (252 ** 0.5))
            results.append({
                "name": name,
                "ticker": ticker,
                "period_return": round(ret, 4),
                "annualized_vol": round(vol, 4),
                "last_price": round(float(df["close"].iloc[-1]), 4),
            })
        except Exception:
            continue

    results.sort(key=lambda x: x["period_return"], reverse=True)
    return {"days": days, "commodities": results}
