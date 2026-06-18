"""
Global Event Calendar Engine.

Sources:
  1. Finnhub economic calendar (free)
  2. Finnhub earnings calendar (free)
  3. FRED release calendar (free)
  4. Static NSE/BSE events (hardcoded key dates: budget, RBI MPC, etc.)
  5. Manual user-added events (stored in SQLite)

Each event is tagged with:
  - region / country
  - event category
  - affected sectors
  - expected impact level (low / medium / high)
  - prior + forecast values (for macro releases)

The calendar powers the Decision Engine's event_risk_level input.
"""
from __future__ import annotations

import json
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy.orm import sessionmaker, Session

from backend.app.core.cache import cached
from backend.app.core.logging import logger
from backend.app.data.models.database import MarketEvent, get_engine
from backend.app.data.sources.finnhub_source import FinnhubSource

SessionLocal = sessionmaker(bind=get_engine(), autocommit=False, autoflush=False)


@contextmanager
def _db():
    s: Session = SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


@dataclass
class CalendarEvent:
    id: Optional[int]
    title: str
    event_type: str        # CENTRAL_BANK / MACRO_RELEASE / EARNINGS / ELECTION / GEOPOLITICAL / USER
    region: str            # US / IN / EU / CN / GLOBAL
    country: Optional[str]
    scheduled_at: Optional[datetime]
    affected_sectors: list[str]
    impact_level: str      # low / medium / high
    actual: Optional[str] = None
    forecast: Optional[str] = None
    previous: Optional[str] = None
    source: str = "unknown"
    days_away: int = 0     # Computed field: days from today


# ── Impact classification ─────────────────────────────────────────────────────

HIGH_IMPACT_TYPES = {
    "FED_DECISION", "RBI_DECISION", "ECB_DECISION", "BOJ_DECISION",
    "US_CPI", "US_GDP", "US_NFP", "INDIA_BUDGET", "INDIA_RBI_MPC",
    "INDIA_ELECTION", "GEOPOLITICAL",
}

SECTOR_MAP: dict[str, list[str]] = {
    "FED_DECISION": ["banking", "real_estate", "bonds", "all"],
    "RBI_DECISION": ["banking", "real_estate", "nbfc", "all"],
    "US_CPI": ["consumer_staples", "real_estate", "bonds"],
    "US_GDP": ["industrials", "consumer_discretionary", "all"],
    "US_NFP": ["consumer_discretionary", "financials"],
    "INDIA_BUDGET": ["infrastructure", "defense", "banking", "all"],
    "INDIA_RBI_MPC": ["banking", "real_estate", "nbfc"],
    "EARNINGS": [],   # Symbol-specific
    "GEOPOLITICAL": ["energy", "defense", "commodities"],
    "OIL_REPORT": ["energy", "chemicals", "airlines"],
    "ELECTION": ["infrastructure", "defense", "banking"],
}


def _classify_impact(event_type: str, title: str) -> str:
    if event_type in HIGH_IMPACT_TYPES:
        return "high"
    title_lower = title.lower()
    high_kws = ["fed", "rbi", "ecb", "war", "budget", "election", "rate", "inflation", "gdp"]
    if any(k in title_lower for k in high_kws):
        return "high"
    medium_kws = ["earnings", "pmi", "iip", "unemployment", "trade", "retail sales"]
    if any(k in title_lower for k in medium_kws):
        return "medium"
    return "low"


class EventCalendar:
    """
    Aggregates events from all sources into a unified, sortable calendar.
    """

    def __init__(self):
        self.finnhub = FinnhubSource()

    # ── Main query ────────────────────────────────────────────────────────────

    def upcoming(
        self,
        days_ahead: int = 30,
        region: Optional[str] = None,
        impact_level: Optional[str] = None,
        include_earnings: bool = True,
    ) -> list[CalendarEvent]:
        """
        Return all upcoming events within `days_ahead`, sorted by date.
        Merges Finnhub + stored events.
        """
        today = date.today()
        end = today + timedelta(days=days_ahead)
        events: list[CalendarEvent] = []

        # ── Stored events (SQLite) ────────────────────────────────────────────
        events += self._load_stored_events(today, end)

        # ── Finnhub economic calendar ─────────────────────────────────────────
        if self.finnhub.is_available():
            events += self._fetch_finnhub_economic()
            if include_earnings:
                events += self._fetch_finnhub_earnings(today, end)

        # ── Static Indian market calendar ─────────────────────────────────────
        events += self._static_india_calendar(today, end)

        # ── Deduplicate + filter ──────────────────────────────────────────────
        seen = set()
        unique = []
        for e in events:
            key = (e.title[:40], str(e.scheduled_at)[:10] if e.scheduled_at else "")
            if key not in seen:
                seen.add(key)
                unique.append(e)

        # ── Compute days_away + filter ────────────────────────────────────────
        result = []
        for e in unique:
            if e.scheduled_at:
                e.days_away = (e.scheduled_at.date() - today).days
                if not (0 <= e.days_away <= days_ahead):
                    continue
            if region and e.region.upper() != region.upper():
                continue
            if impact_level and e.impact_level != impact_level:
                continue
            result.append(e)

        return sorted(result, key=lambda e: e.scheduled_at or datetime.max)

    def event_risk_for_symbol(
        self, symbol: str, sectors: list[str], days_ahead: int = 7
    ) -> str:
        """
        Determine event risk level for a symbol based on upcoming events
        that affect its sectors. Used by the Decision Engine.
        Returns: "low" / "medium" / "high"
        """
        events = self.upcoming(days_ahead=days_ahead)
        max_impact = "low"
        impact_order = {"low": 0, "medium": 1, "high": 2}

        for event in events:
            # Check sector overlap
            event_sectors = set(event.affected_sectors)
            symbol_sectors = set(s.lower() for s in sectors)
            has_overlap = bool(event_sectors & symbol_sectors) or "all" in event_sectors

            if has_overlap or event.impact_level == "high":
                if impact_order[event.impact_level] > impact_order[max_impact]:
                    max_impact = event.impact_level

        return max_impact

    # ── CRUD for manual events ────────────────────────────────────────────────

    def add_event(
        self,
        title: str,
        event_type: str,
        scheduled_at: datetime,
        region: str = "IN",
        country: Optional[str] = "India",
        affected_sectors: Optional[list[str]] = None,
        impact_level: Optional[str] = None,
        forecast: Optional[str] = None,
    ) -> MarketEvent:
        sectors = affected_sectors or SECTOR_MAP.get(event_type, [])
        impact = impact_level or _classify_impact(event_type, title)
        with _db() as db:
            evt = MarketEvent(
                title=title,
                event_type=event_type,
                region=region,
                country=country,
                scheduled_at=scheduled_at,
                affected_sectors=json.dumps(sectors),
                impact_level=impact,
                forecast_value=forecast,
                source="manual",
            )
            db.add(evt)
        logger.info(f"[Calendar] Added event: {title} on {scheduled_at.date()}")
        return evt

    def delete_event(self, event_id: int) -> bool:
        with _db() as db:
            evt = db.query(MarketEvent).filter_by(id=event_id).first()
            if not evt:
                return False
            db.delete(evt)
        return True

    # ── Private loaders ────────────────────────────────────────────────────────

    def _load_stored_events(self, start: date, end: date) -> list[CalendarEvent]:
        with _db() as db:
            rows = (
                db.query(MarketEvent)
                .filter(MarketEvent.scheduled_at >= datetime.combine(start, datetime.min.time()))
                .filter(MarketEvent.scheduled_at <= datetime.combine(end, datetime.max.time()))
                .all()
            )
        result = []
        for r in rows:
            try:
                sectors = json.loads(r.affected_sectors) if r.affected_sectors else []
            except (json.JSONDecodeError, TypeError):
                sectors = []
            result.append(CalendarEvent(
                id=r.id,
                title=r.title,
                event_type=r.event_type or "GENERAL",
                region=r.region or "IN",
                country=r.country,
                scheduled_at=r.scheduled_at,
                affected_sectors=sectors,
                impact_level=r.impact_level or "medium",
                actual=r.actual_value,
                forecast=r.forecast_value,
                previous=r.previous_value,
                source=r.source or "manual",
            ))
        return result

    @cached(ttl=7200, prefix="calendar:finnhub:econ")
    def _fetch_finnhub_economic(self) -> list[CalendarEvent]:
        events = []
        try:
            raw = self.finnhub.fetch_economic_calendar()
        except Exception as e:
            logger.warning(f"[Calendar] Finnhub economic calendar failed: {e}")
            return []

        for item in raw:
            try:
                dt_str = item.get("time") or item.get("date", "")
                if not dt_str:
                    continue
                dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00")).replace(tzinfo=None)
                title = item.get("event", "Economic Event")
                country = item.get("country", "")
                region = "US" if country == "US" else "EU" if country in ("EU", "GB", "DE") else "IN" if country == "IN" else "GLOBAL"
                impact_raw = str(item.get("impact", "")).lower()
                impact = "high" if impact_raw == "high" else "medium" if impact_raw == "medium" else "low"
                event_type = self._classify_economic_type(title)
                events.append(CalendarEvent(
                    id=None,
                    title=title,
                    event_type=event_type,
                    region=region,
                    country=country,
                    scheduled_at=dt,
                    affected_sectors=SECTOR_MAP.get(event_type, []),
                    impact_level=impact,
                    actual=str(item.get("actual", "")),
                    forecast=str(item.get("estimate", "")),
                    previous=str(item.get("prev", "")),
                    source="finnhub",
                ))
            except Exception:
                continue
        return events

    @cached(ttl=7200, prefix="calendar:finnhub:earnings")
    def _fetch_finnhub_earnings(self, start: date, end: date) -> list[CalendarEvent]:
        events = []
        try:
            raw = self.finnhub.fetch_earnings_calendar(start, end)
        except Exception as e:
            logger.warning(f"[Calendar] Finnhub earnings calendar failed: {e}")
            return []

        for item in raw:
            try:
                dt_str = item.get("date", "")
                if not dt_str:
                    continue
                dt = datetime.strptime(dt_str, "%Y-%m-%d")
                symbol = item.get("symbol", "")
                events.append(CalendarEvent(
                    id=None,
                    title=f"{symbol} Earnings",
                    event_type="EARNINGS",
                    region="US",
                    country="US",
                    scheduled_at=dt,
                    affected_sectors=[],
                    impact_level="medium",
                    forecast=str(item.get("epsEstimate", "")),
                    previous=str(item.get("epsPrior", "")),
                    source="finnhub",
                ))
            except Exception:
                continue
        return events

    def _static_india_calendar(self, start: date, end: date) -> list[CalendarEvent]:
        """
        Hardcoded recurring Indian market events.
        These are seeded at startup if not already present.
        """
        today = date.today()
        year = today.year
        events = [
            # RBI MPC — typically Feb, Apr, Jun, Aug, Oct, Dec (first week)
            ("RBI MPC Policy Decision", "RBI_DECISION", date(year, 2, 8), "IN", "India", ["banking", "real_estate", "nbfc"], "high"),
            ("RBI MPC Policy Decision", "RBI_DECISION", date(year, 4, 5), "IN", "India", ["banking", "real_estate", "nbfc"], "high"),
            ("RBI MPC Policy Decision", "RBI_DECISION", date(year, 6, 7), "IN", "India", ["banking", "real_estate", "nbfc"], "high"),
            ("RBI MPC Policy Decision", "RBI_DECISION", date(year, 8, 8), "IN", "India", ["banking", "real_estate", "nbfc"], "high"),
            ("RBI MPC Policy Decision", "RBI_DECISION", date(year, 10, 9), "IN", "India", ["banking", "real_estate", "nbfc"], "high"),
            ("RBI MPC Policy Decision", "RBI_DECISION", date(year, 12, 6), "IN", "India", ["banking", "real_estate", "nbfc"], "high"),
            # Union Budget
            ("India Union Budget", "INDIA_BUDGET", date(year, 2, 1), "IN", "India", ["infrastructure", "defense", "banking", "all"], "high"),
            # F&O Expiry — last Thursday of every month
            *[("NSE F&O Monthly Expiry", "FNO_EXPIRY", self._last_thursday(year, m), "IN", "India", ["all"], "medium") for m in range(1, 13)],
        ]

        result = []
        for title, etype, event_date, region, country, sectors, impact in events:
            if start <= event_date <= end:
                result.append(CalendarEvent(
                    id=None,
                    title=title,
                    event_type=etype,
                    region=region,
                    country=country,
                    scheduled_at=datetime.combine(event_date, datetime.min.time()),
                    affected_sectors=sectors,
                    impact_level=impact,
                    source="static",
                ))
        return result

    @staticmethod
    def _last_thursday(year: int, month: int) -> date:
        """Return the last Thursday of a given month."""
        if month == 12:
            d = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            d = date(year, month + 1, 1) - timedelta(days=1)
        while d.weekday() != 3:  # 3 = Thursday
            d -= timedelta(days=1)
        return d

    @staticmethod
    def _classify_economic_type(title: str) -> str:
        t = title.lower()
        if any(k in t for k in ["fed", "fomc", "federal funds"]):
            return "FED_DECISION"
        if any(k in t for k in ["rbi", "repo rate", "monetary policy"]):
            return "RBI_DECISION"
        if any(k in t for k in ["ecb", "european central"]):
            return "ECB_DECISION"
        if any(k in t for k in ["cpi", "consumer price"]):
            return "US_CPI"
        if "gdp" in t:
            return "US_GDP"
        if any(k in t for k in ["nonfarm", "payroll", "unemployment"]):
            return "US_NFP"
        if "pmi" in t:
            return "PMI"
        return "MACRO_RELEASE"
