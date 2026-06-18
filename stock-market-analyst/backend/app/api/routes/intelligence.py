"""
Intelligence endpoints — news, events calendar, supply chain graph.
"""
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from pydantic import BaseModel

from backend.app.intelligence.news.analyzer import NewsAnalyzer
from backend.app.intelligence.events.calendar import EventCalendar
from backend.app.graph.supply_chain import SupplyChainGraph
from backend.app.analytics.nlp.report_parser import AnnualReportParser
from backend.app.data.sources.watchlist_service import WatchlistService
from backend.app.core.config import get_settings
from backend.app.core.logging import logger
import tempfile
from pathlib import Path

router = APIRouter(prefix="/intelligence", tags=["Intelligence"])

_news = NewsAnalyzer()
_calendar = EventCalendar()
_graph = SupplyChainGraph()
_parser = AnnualReportParser()
_watchlist = WatchlistService()


# ── News ──────────────────────────────────────────────────────────────────────

@router.get("/news/{symbol}")
def news_analysis(symbol: str, days: int = Query(7, ge=1, le=30)):
    """Analyze recent news for a symbol with sentiment and event extraction."""
    try:
        analysis = _news.analyze_symbol(symbol.upper(), days=days)
        return {
            "symbol": symbol.upper(),
            "period_days": days,
            "article_count": analysis.article_count,
            "sentiment": {
                "score": analysis.sentiment_score,
                "label": analysis.sentiment_label,
                "confidence": analysis.sentiment_confidence,
            },
            "event_types": analysis.event_types,
            "sector_impact": analysis.sector_impact,
            "top_positive": analysis.top_positive,
            "top_negative": analysis.top_negative,
            "high_impact_events": analysis.high_impact_events,
            "articles": analysis.articles[:20],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/news/market/overview")
def market_news(days: int = Query(3, ge=1, le=7)):
    """Analyze broad market news and return sector impact scores."""
    try:
        analysis = _news.analyze_market(days=days)
        return {
            "period_days": days,
            "article_count": analysis.article_count,
            "market_sentiment": {
                "score": analysis.sentiment_score,
                "label": analysis.sentiment_label,
                "confidence": analysis.sentiment_confidence,
            },
            "active_event_types": analysis.event_types,
            "sector_impact": analysis.sector_impact,
            "high_impact_events": analysis.high_impact_events,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Event Calendar ─────────────────────────────────────────────────────────────

@router.get("/calendar")
def upcoming_events(
    days_ahead: int = Query(30, ge=1, le=90),
    region: Optional[str] = Query(None),
    impact_level: Optional[str] = Query(None, pattern="^(low|medium|high)$"),
):
    """List all upcoming market events within the next N days."""
    events = _calendar.upcoming(
        days_ahead=days_ahead,
        region=region,
        impact_level=impact_level,
    )
    return {
        "count": len(events),
        "events": [
            {
                "id": e.id,
                "title": e.title,
                "event_type": e.event_type,
                "region": e.region,
                "country": e.country,
                "scheduled_at": e.scheduled_at.isoformat() if e.scheduled_at else None,
                "days_away": e.days_away,
                "affected_sectors": e.affected_sectors,
                "impact_level": e.impact_level,
                "forecast": e.forecast,
                "previous": e.previous,
                "source": e.source,
            }
            for e in events
        ],
    }


class AddEventRequest(BaseModel):
    title: str
    event_type: str
    scheduled_at: datetime
    region: str = "IN"
    country: Optional[str] = "India"
    affected_sectors: Optional[list[str]] = None
    impact_level: Optional[str] = None
    forecast: Optional[str] = None


@router.post("/calendar", status_code=201)
def add_event(body: AddEventRequest):
    """Add a manual event to the calendar."""
    try:
        evt = _calendar.add_event(
            title=body.title,
            event_type=body.event_type,
            scheduled_at=body.scheduled_at,
            region=body.region,
            country=body.country,
            affected_sectors=body.affected_sectors,
            impact_level=body.impact_level,
            forecast=body.forecast,
        )
        return {"id": evt.id, "title": evt.title, "scheduled_at": str(evt.scheduled_at)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/calendar/{event_id}", status_code=204)
def delete_event(event_id: int):
    if not _calendar.delete_event(event_id):
        raise HTTPException(status_code=404, detail="Event not found")


@router.get("/calendar/risk/{symbol}")
def event_risk(
    symbol: str,
    sectors: str = Query("", description="Comma-separated sectors"),
    days_ahead: int = Query(7, ge=1, le=30),
):
    """Get event risk level for a symbol based on upcoming events."""
    sector_list = [s.strip() for s in sectors.split(",") if s.strip()]
    risk = _calendar.event_risk_for_symbol(symbol.upper(), sector_list, days_ahead)
    return {"symbol": symbol.upper(), "event_risk": risk, "days_ahead": days_ahead}


# ── Supply Chain Graph ─────────────────────────────────────────────────────────

@router.get("/graph")
def get_supply_chain_graph(
    node_types: str = Query("company,commodity,region", description="Comma-separated node types"),
):
    """
    Return the supply chain graph populated from the current watchlist.
    Populates graph on-the-fly from watchlist sectors.
    """
    # Build from watchlist
    items = _watchlist.list_all()
    for item in items:
        _graph.add_company(
            __import__("backend.app.graph.supply_chain", fromlist=["CompanyNode"]).CompanyNode(
                symbol=item.symbol,
                name=item.symbol,
                sector=item.sector or "unknown",
                country="India",
            )
        )

    types = [t.strip() for t in node_types.split(",")]
    return _graph.to_json(include_types=types)


@router.get("/graph/disruption/{node}")
def simulate_disruption(
    node: str,
    magnitude: float = Query(0.5, ge=0.0, le=1.0),
    max_hops: int = Query(4, ge=1, le=6),
):
    """Simulate a supply chain disruption from a commodity or region node."""
    result = _graph.simulate_disruption(node, shock_magnitude=magnitude, max_hops=max_hops)
    return {
        "source": result.source_node,
        "shock_magnitude": result.shock_magnitude,
        "affected_companies": result.affected_companies,
        "total_affected": result.total_affected,
        "propagation_path": result.propagation_path,
        "description": result.description,
    }


@router.get("/graph/risk/{symbol}")
def company_supply_risk(symbol: str):
    """Compute supply chain risk score for a company."""
    return _graph.company_risk_score(symbol.upper())


@router.get("/graph/critical-nodes")
def critical_nodes():
    """Find commodity/node bottlenecks with highest betweenness centrality."""
    return {"critical_nodes": _graph.find_critical_nodes()}


# ── Annual Report Parser ───────────────────────────────────────────────────────

@router.post("/reports/parse/{symbol}")
async def parse_annual_report(
    symbol: str,
    file: UploadFile = File(...),
):
    """Upload and parse an annual report PDF for a symbol."""
    if not file.filename or not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    settings = get_settings()
    reports_dir = settings.reports_dir / symbol.upper()
    reports_dir.mkdir(parents=True, exist_ok=True)
    dest = reports_dir / file.filename

    with open(dest, "wb") as f:
        f.write(await file.read())

    insights = _parser.parse(dest, symbol.upper())

    return {
        "symbol": symbol.upper(),
        "filename": insights.filename,
        "year": insights.year,
        "page_count": insights.page_count,
        "extraction_confidence": insights.extraction_confidence,
        "suppliers": insights.suppliers,
        "customers": insights.customers,
        "commodity_dependencies": insights.commodity_dependencies,
        "risk_factors": insights.risk_factors[:5],
        "revenue_segments": insights.revenue_segments,
        "management_tone": insights.management_tone,
        "growth_keywords": insights.growth_keywords,
        "concern_keywords": insights.concern_keywords,
    }


@router.get("/reports/{symbol}")
def list_reports(symbol: str):
    """List parsed annual reports for a symbol."""
    settings = get_settings()
    reports_dir = settings.reports_dir / symbol.upper()
    if not reports_dir.exists():
        return {"symbol": symbol, "reports": []}
    pdfs = list(reports_dir.glob("*.pdf"))
    return {
        "symbol": symbol,
        "reports": [{"filename": p.name, "size_kb": round(p.stat().st_size / 1024, 1)} for p in pdfs],
    }
