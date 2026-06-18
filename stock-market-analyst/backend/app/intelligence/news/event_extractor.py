"""
Event Extractor — classifies news into structured market events with impact scores.

Extracts:
  - Event type (rate hike, war, sanctions, earnings, regulatory, supply shock, etc.)
  - Affected sectors (list)
  - Impact magnitude (0–1)
  - Time horizon (immediate / short / medium / long)
  - Geographical scope (domestic / regional / global)

Uses rule-based pattern matching first (fast, no inference cost),
then optionally enriches with LLM if available.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ExtractedEvent:
    headline: str
    event_type: str              # See EVENT_TAXONOMY below
    affected_sectors: list[str]
    impact_magnitude: float      # 0–1 (higher = larger market impact)
    time_horizon: str            # "immediate" / "short" / "medium" / "long"
    geo_scope: str               # "domestic" / "regional" / "global"
    is_positive: Optional[bool]  # True=tailwind, False=headwind, None=ambiguous
    keywords_matched: list[str] = field(default_factory=list)
    confidence: float = 0.5


# ── Event Taxonomy ─────────────────────────────────────────────────────────────

EVENT_TAXONOMY: dict[str, dict] = {
    "RATE_DECISION": {
        "keywords": [
            "rate hike", "rate cut", "interest rate", "federal reserve", "rbi policy",
            "monetary policy", "fed funds", "repo rate", "basis points", "bps",
        ],
        "sectors": ["banking", "real_estate", "financials", "utilities", "bonds"],
        "magnitude": 0.8,
        "horizon": "medium",
        "geo": "global",
    },
    "INFLATION": {
        "keywords": ["inflation", "cpi", "consumer price", "pce", "wpi", "deflation", "price surge"],
        "sectors": ["consumer_staples", "real_estate", "industrials"],
        "magnitude": 0.6,
        "horizon": "medium",
        "geo": "domestic",
    },
    "GEOPOLITICAL": {
        "keywords": [
            "war", "invasion", "military", "sanction", "tariff", "trade war",
            "conflict", "missile", "airstrike", "geopolitical", "embargo", "blockade",
        ],
        "sectors": ["energy", "defense", "commodities", "airlines", "logistics"],
        "magnitude": 0.9,
        "horizon": "short",
        "geo": "global",
    },
    "SUPPLY_SHOCK": {
        "keywords": [
            "supply chain", "shortage", "disruption", "opec", "production cut",
            "drought", "flood", "port", "semiconductor", "chip shortage",
        ],
        "sectors": ["energy", "technology", "industrials", "auto", "manufacturing"],
        "magnitude": 0.7,
        "horizon": "short",
        "geo": "global",
    },
    "EARNINGS": {
        "keywords": [
            "earnings", "quarterly result", "profit", "revenue", "eps", "guidance",
            "beat estimates", "miss estimates", "full year outlook", "forecast",
        ],
        "sectors": [],           # Symbol-specific
        "magnitude": 0.5,
        "horizon": "immediate",
        "geo": "domestic",
    },
    "REGULATORY": {
        "keywords": [
            "sebi", "rbi circular", "regulation", "fine", "penalty", "ban",
            "compliance", "antitrust", "investigation", "lawsuit", "sec", "doj",
        ],
        "sectors": ["banking", "financials", "technology", "pharma"],
        "magnitude": 0.6,
        "horizon": "short",
        "geo": "domestic",
    },
    "ELECTION": {
        "keywords": [
            "election", "budget", "fiscal", "government", "policy change",
            "new government", "exit poll", "manifesto", "election result",
        ],
        "sectors": ["infrastructure", "banking", "energy", "defense"],
        "magnitude": 0.7,
        "horizon": "medium",
        "geo": "domestic",
    },
    "MACRO_DATA": {
        "keywords": [
            "gdp", "unemployment", "jobs report", "nonfarm payroll", "iip", "pmi",
            "manufacturing", "services sector", "trade deficit", "current account",
        ],
        "sectors": ["industrials", "consumer_discretionary", "financials"],
        "magnitude": 0.5,
        "horizon": "short",
        "geo": "domestic",
    },
    "COMMODITIES": {
        "keywords": [
            "oil price", "crude", "gold", "silver", "copper", "natural gas",
            "commodity", "brent", "wti", "precious metals",
        ],
        "sectors": ["energy", "materials", "chemicals", "fmcg"],
        "magnitude": 0.6,
        "horizon": "short",
        "geo": "global",
    },
    "CORPORATE_ACTION": {
        "keywords": [
            "merger", "acquisition", "takeover", "buyback", "dividend", "rights issue",
            "ipo", "delisting", "spin-off", "joint venture", "strategic stake",
        ],
        "sectors": [],
        "magnitude": 0.5,
        "horizon": "immediate",
        "geo": "domestic",
    },
    "CREDIT_EVENT": {
        "keywords": [
            "default", "downgrade", "upgrade", "credit rating", "moody's", "s&p",
            "fitch", "npa", "bad loan", "write-off", "restructuring",
        ],
        "sectors": ["banking", "financials", "real_estate"],
        "magnitude": 0.7,
        "horizon": "immediate",
        "geo": "domestic",
    },
}

# Sector-specific positive/negative signal words
POSITIVE_SIGNALS = {
    "beat", "exceed", "surge", "rally", "record", "approve", "win", "launch",
    "partnership", "contract", "gain", "recovery", "profit", "growth", "upgrade",
}
NEGATIVE_SIGNALS = {
    "miss", "below", "cut", "warn", "default", "cancel", "delay", "recall",
    "investigation", "fine", "penalty", "shortage", "downgrade", "loss", "fail",
}


class EventExtractor:
    """
    Classifies a news headline into a structured ExtractedEvent.
    Pure rule-based — no inference required, instant, cacheable.
    """

    def extract(self, headline: str) -> ExtractedEvent:
        text = headline.lower()
        words = set(re.findall(r"\b\w+\b", text))

        best_type = "GENERAL"
        best_magnitude = 0.2
        best_sectors: list[str] = []
        best_horizon = "short"
        best_geo = "domestic"
        matched_kws: list[str] = []
        max_matches = 0

        for evt_type, spec in EVENT_TAXONOMY.items():
            matches = [kw for kw in spec["keywords"] if kw in text]
            if len(matches) > max_matches:
                max_matches = len(matches)
                best_type = evt_type
                best_magnitude = spec["magnitude"]
                best_sectors = spec["sectors"].copy()
                best_horizon = spec["horizon"]
                best_geo = spec["geo"]
                matched_kws = matches

        # Polarity detection
        pos_hits = POSITIVE_SIGNALS & words
        neg_hits = NEGATIVE_SIGNALS & words

        if pos_hits and not neg_hits:
            is_positive = True
        elif neg_hits and not pos_hits:
            is_positive = False
        else:
            is_positive = None

        # Adjust magnitude by match confidence
        confidence = min(max_matches / 3, 1.0) if max_matches > 0 else 0.3

        return ExtractedEvent(
            headline=headline,
            event_type=best_type,
            affected_sectors=best_sectors,
            impact_magnitude=best_magnitude * (0.7 + 0.3 * confidence),
            time_horizon=best_horizon,
            geo_scope=best_geo,
            is_positive=is_positive,
            keywords_matched=matched_kws,
            confidence=confidence,
        )

    def extract_batch(self, headlines: list[str]) -> list[ExtractedEvent]:
        return [self.extract(h) for h in headlines]

    def aggregate_sector_impact(
        self, events: list[ExtractedEvent]
    ) -> dict[str, float]:
        """
        Roll up event impacts into a per-sector impact score.
        Positive = tailwind, negative = headwind.
        """
        sector_scores: dict[str, list[float]] = {}
        for event in events:
            sign = 1.0 if event.is_positive else -1.0 if event.is_positive is False else 0.0
            impact = event.impact_magnitude * sign
            for sector in event.affected_sectors:
                sector_scores.setdefault(sector, []).append(impact)

        return {
            sector: round(float(sum(scores) / len(scores)), 4)
            for sector, scores in sector_scores.items()
        }
