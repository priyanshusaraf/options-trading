"""
Data endpoints — OHLCV, fundamentals, macro, cache management.
"""
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.app.data.ingestion import DataIngestionManager
from backend.app.data.sources.yfinance_source import YFinanceSource
from backend.app.data.sources.fred_source import FREDSource, COMMON_SERIES
from backend.app.data.cache.parquet_store import list_cached_symbols
from backend.app.core.cache import cache_stats, invalidate
from backend.app.core.logging import logger

router = APIRouter(prefix="/data", tags=["Data"])

_ingestion = DataIngestionManager()
_yf = YFinanceSource()
_fred = FREDSource()


@router.get("/ohlcv/{symbol}")
def get_ohlcv(
    symbol: str,
    days: int = Query(365, ge=1, le=3650),
    interval: str = Query("1d", pattern="^(1d|1wk|1mo)$"),
    exchange: str = Query("NSE"),
    force_refresh: bool = Query(False),
):
    """Fetch OHLCV data for a symbol."""
    end = date.today()
    start = end - timedelta(days=days)
    yf_sym = f"{symbol.upper()}.NS" if exchange == "NSE" and not symbol.endswith((".NS", ".BO")) else symbol.upper()

    try:
        df = _ingestion.get_ohlcv(yf_sym, start, end, interval=interval, force_refresh=force_refresh)
        if df.empty:
            raise HTTPException(status_code=404, detail=f"No data for {symbol}")

        records = []
        for ts, row in df.iterrows():
            records.append({
                "date": ts.date().isoformat(),
                "open": round(float(row["open"]), 2),
                "high": round(float(row["high"]), 2),
                "low": round(float(row["low"]), 2),
                "close": round(float(row["close"]), 2),
                "volume": int(row.get("volume", 0)),
            })

        return {
            "symbol": symbol,
            "exchange": exchange,
            "interval": interval,
            "count": len(records),
            "data": records,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/fundamentals/{symbol}")
def get_fundamentals(symbol: str, exchange: str = Query("NSE")):
    """Fetch fundamental data (P/E, P/B, market cap, etc.)."""
    yf_sym = f"{symbol.upper()}.NS" if exchange == "NSE" and not symbol.endswith((".NS", ".BO")) else symbol.upper()
    fundamentals = _yf.fetch_fundamentals(yf_sym)
    if not fundamentals:
        raise HTTPException(status_code=404, detail=f"No fundamentals for {symbol}")
    return {
        "symbol": symbol,
        "pe_ratio": fundamentals.pe_ratio,
        "pb_ratio": fundamentals.pb_ratio,
        "market_cap": fundamentals.market_cap,
        "eps": fundamentals.eps,
        "dividend_yield": fundamentals.dividend_yield,
        "revenue": fundamentals.revenue,
        "net_income": fundamentals.net_income,
        "debt_to_equity": fundamentals.debt_to_equity,
        "roe": fundamentals.roe,
    }


@router.get("/macro")
def get_macro_data(series: Optional[str] = Query(None, description="Specific FRED series ID")):
    """Fetch macro time series from FRED. Returns common series if none specified."""
    if not _fred.is_available():
        raise HTTPException(status_code=503, detail="FRED API key not configured")

    if series:
        try:
            s = _fred.fetch_series(series)
            return {
                "series_id": series,
                "data": {str(k.date()): v for k, v in s.items()},
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    result = {}
    for label, series_id in COMMON_SERIES.items():
        try:
            s = _fred.fetch_series(series_id)
            latest = float(s.iloc[-1]) if len(s) > 0 else None
            prev = float(s.iloc[-2]) if len(s) > 1 else None
            result[label] = {
                "series_id": series_id,
                "latest": latest,
                "previous": prev,
                "change": round(latest - prev, 4) if latest and prev else None,
                "latest_date": str(s.index[-1].date()) if len(s) > 0 else None,
            }
        except Exception as e:
            logger.warning(f"FRED {label} failed: {e}")

    return {"macro": result}


@router.get("/cache/stats")
def get_cache_stats():
    """Return cache usage stats."""
    return {
        "disk_cache": cache_stats(),
        "cached_symbols": list_cached_symbols("1d"),
        "symbol_count": len(list_cached_symbols("1d")),
    }


@router.delete("/cache/{prefix}")
def clear_cache(prefix: str):
    """Clear cache entries matching a prefix (e.g. 'yf', 'av', 'fred')."""
    removed = invalidate(prefix)
    return {"removed": removed, "prefix": prefix}
