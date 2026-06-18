from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel

from backend.app.data.sources.watchlist_service import WatchlistService
from backend.app.core.logging import logger

router = APIRouter(prefix="/watchlist", tags=["Watchlist"])
_svc = WatchlistService()


def _prefetch_ohlcv(symbol: str, exchange: str):
    """Background task: fetch 3 years of OHLCV after adding to watchlist."""
    try:
        from backend.app.data.ingestion import DataIngestionManager
        from datetime import date, timedelta
        mgr = DataIngestionManager()
        yf_sym = f"{symbol}.NS" if exchange == "NSE" else (f"{symbol}.BO" if exchange == "BSE" else symbol)
        end = date.today()
        start = end - timedelta(days=365 * 3)
        df = mgr.get_ohlcv(yf_sym, start, end)
        logger.info(f"[Watchlist] Pre-fetched {len(df)} rows for {symbol}")
    except Exception as e:
        logger.warning(f"[Watchlist] Pre-fetch failed for {symbol}: {e}")


# ── Request / Response models ─────────────────────────────────────────────────

class AddSymbolRequest(BaseModel):
    symbol: str
    exchange: str = "NSE"
    sector: Optional[str] = None
    industry: Optional[str] = None
    notes: Optional[str] = None


class UpdateSymbolRequest(BaseModel):
    sector: Optional[str] = None
    industry: Optional[str] = None
    notes: Optional[str] = None


class WatchlistItemResponse(BaseModel):
    id: int
    symbol: str
    exchange: str
    sector: Optional[str]
    industry: Optional[str]
    notes: Optional[str]
    added_at: str
    is_active: bool

    @classmethod
    def from_orm(cls, item) -> "WatchlistItemResponse":
        return cls(
            id=item.id,
            symbol=item.symbol,
            exchange=item.exchange,
            sector=item.sector,
            industry=item.industry,
            notes=item.notes,
            added_at=item.added_at.isoformat(),
            is_active=item.is_active,
        )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/", response_model=list[WatchlistItemResponse])
def list_watchlist(include_inactive: bool = Query(False)):
    """List all active watchlist symbols."""
    items = _svc.list_all(include_inactive=include_inactive)
    return [WatchlistItemResponse.from_orm(i) for i in items]


@router.post("/", response_model=WatchlistItemResponse, status_code=201)
def add_symbol(body: AddSymbolRequest, background_tasks: BackgroundTasks):
    """Add a symbol to the watchlist. Historical data is pre-fetched in the background."""
    sym = body.symbol.upper().strip()

    # First validate the symbol actually exists on yfinance before saving
    try:
        import yfinance as yf
        yf_sym = f"{sym}.NS" if body.exchange == "NSE" else (f"{sym}.BO" if body.exchange == "BSE" else sym)
        ticker = yf.Ticker(yf_sym)
        info = ticker.fast_info
        # fast_info raises no error for invalid symbols but returns None market cap
        # Check if we can get any real data at all
        if not info or getattr(info, "last_price", None) is None:
            # Try a quick history check as fallback validation
            from datetime import date, timedelta
            hist = ticker.history(period="5d")
            if hist.empty:
                raise HTTPException(
                    status_code=422,
                    detail=f"Symbol '{sym}' not found on {body.exchange}. "
                           f"Check the ticker (e.g. RELIANCE, TCS, INFY). "
                           f"For NSE stocks use the NSE symbol without .NS suffix.",
                )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"[Watchlist] Validation warning for {sym}: {e}")
        # Don't fail hard on validation errors — yfinance can be flaky

    # Save to DB (fast, no blocking)
    item = _svc.add_direct(
        symbol=sym,
        exchange=body.exchange,
        sector=body.sector,
        industry=body.industry,
        notes=body.notes,
    )
    if not item:
        raise HTTPException(status_code=500, detail="Failed to save symbol to database")

    # Schedule OHLCV fetch in the background (non-blocking)
    background_tasks.add_task(_prefetch_ohlcv, sym, body.exchange)

    return WatchlistItemResponse.from_orm(item)


@router.delete("/{symbol}", status_code=204)
def remove_symbol(symbol: str, hard_delete: bool = Query(False)):
    """Remove (soft-delete) a symbol from the watchlist."""
    success = _svc.remove(symbol.upper(), hard_delete=hard_delete)
    if not success:
        raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found")


@router.patch("/{symbol}", response_model=WatchlistItemResponse)
def update_symbol(symbol: str, body: UpdateSymbolRequest):
    """Update metadata for a watchlist symbol."""
    item = _svc.update(symbol.upper(), **body.model_dump(exclude_none=True))
    if not item:
        raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found")
    return WatchlistItemResponse.from_orm(item)


@router.post("/bulk", response_model=list[WatchlistItemResponse], status_code=201)
def add_bulk(items: list[AddSymbolRequest], background_tasks: BackgroundTasks):
    """Add multiple symbols at once (non-blocking)."""
    results = []
    for item in items:
        sym = item.symbol.upper().strip()
        obj = _svc.add_direct(sym, item.exchange, item.sector, item.industry, item.notes)
        if obj:
            results.append(WatchlistItemResponse.from_orm(obj))
            background_tasks.add_task(_prefetch_ohlcv, sym, item.exchange)
    return results


@router.get("/search", summary="Search all NSE-listed stocks by name or symbol")
def search_stocks(q: str = Query(..., min_length=1), limit: int = Query(12, le=50)):
    """
    Search across all ~2,364 NSE-listed equities by name or symbol.
    Uses trigram fuzzy matching for typo tolerance.
    """
    from backend.app.data.sources.nse_stocks import search_stocks as _search, total_count
    results = _search(q, limit=limit)
    return {
        "query": q,
        "total_in_db": total_count(),
        "results": [
            {
                "symbol": s.symbol,
                "name": s.name,
                "sector": s.sector,
                "industry": s.industry,
                "index": s.index_membership,
                "isin": s.isin,
            }
            for s in results
        ],
    }


@router.get("/search/live", summary="Live yfinance ticker search")
def search_live(q: str = Query(..., min_length=2), limit: int = Query(8, le=20)):
    """
    Tries yfinance ticker search for stocks not in local database.
    Slower than /search but covers more symbols.
    """
    try:
        import yfinance as yf
        tickers = yf.Search(q, max_results=limit)
        quotes = getattr(tickers, "quotes", []) or []
        results = []
        for item in quotes:
            if item.get("exchange") in ("NSI", "BSE", "NSE"):
                sym = item.get("symbol", "").replace(".NS", "").replace(".BO", "")
                results.append({
                    "symbol": sym,
                    "name": item.get("longname") or item.get("shortname", ""),
                    "sector": item.get("sector", ""),
                    "industry": item.get("industry", ""),
                    "exchange": item.get("exchange", ""),
                })
        return results
    except Exception as e:
        logger.warning(f"[Watchlist] Live search failed: {e}")
        return []
