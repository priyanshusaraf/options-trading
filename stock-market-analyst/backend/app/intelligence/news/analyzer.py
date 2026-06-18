"""
News Analyzer — top-level orchestrator.

For each symbol (or globally):
  1. Fetch news from Finnhub (or cache)
  2. Run sentiment analysis (FinBERT or lexicon)
  3. Extract events
  4. Score aggregate impact
  5. Return structured NewsAnalysis
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

from backend.app.core.cache import cached
from backend.app.core.logging import logger
from backend.app.data.sources.finnhub_source import FinnhubSource
from .event_extractor import EventExtractor, ExtractedEvent
from .sentiment import SentimentAnalyzer, SentimentResult


@dataclass
class NewsAnalysis:
    symbol: Optional[str]
    period_start: date
    period_end: date

    # Articles analyzed
    article_count: int = 0
    articles: list[dict] = field(default_factory=list)

    # Aggregate sentiment
    sentiment_score: float = 0.0      # –1 to +1
    sentiment_label: str = "neutral"
    sentiment_confidence: float = 0.0

    # Events
    events: list[ExtractedEvent] = field(default_factory=list)
    event_types: list[str] = field(default_factory=list)
    sector_impact: dict[str, float] = field(default_factory=dict)

    # Summary
    top_positive: list[str] = field(default_factory=list)
    top_negative: list[str] = field(default_factory=list)
    high_impact_events: list[str] = field(default_factory=list)


class NewsAnalyzer:
    """
    Orchestrates news fetching, sentiment, and event extraction.
    Designed to be called on a schedule (daily batch) with results cached.
    """

    def __init__(self):
        self.finnhub = FinnhubSource()
        self.sentiment = SentimentAnalyzer()
        self.extractor = EventExtractor()

    @cached(ttl=3600, prefix="news:analysis")
    def analyze_symbol(
        self,
        symbol: str,
        days: int = 7,
    ) -> NewsAnalysis:
        end = date.today()
        start = end - timedelta(days=days)

        logger.info(f"[NewsAnalyzer] Analyzing {symbol} | {start} → {end}")

        # ── Fetch news ────────────────────────────────────────────────────────
        raw_articles: list[dict] = []
        if self.finnhub.is_available():
            try:
                raw_articles = self.finnhub.fetch_company_news(symbol, start, end)
            except Exception as e:
                logger.warning(f"[NewsAnalyzer] Finnhub failed for {symbol}: {e}")

        analysis = NewsAnalysis(symbol=symbol, period_start=start, period_end=end)
        if not raw_articles:
            return analysis

        analysis.article_count = len(raw_articles)

        # ── Sentiment analysis ────────────────────────────────────────────────
        headlines = [a.get("headline", "") for a in raw_articles if a.get("headline")]
        sentiment_results = self.sentiment.analyze_batch(headlines)
        agg = self.sentiment.aggregate(sentiment_results)

        analysis.sentiment_score = agg["score"]
        analysis.sentiment_label = agg["sentiment"]
        analysis.sentiment_confidence = agg["confidence"]

        # ── Event extraction ──────────────────────────────────────────────────
        events = self.extractor.extract_batch(headlines)
        analysis.events = events
        analysis.event_types = list({e.event_type for e in events if e.event_type != "GENERAL"})
        analysis.sector_impact = self.extractor.aggregate_sector_impact(events)

        # ── Enrich articles with per-item scores ─────────────────────────────
        enriched = []
        for article, sent, event in zip(raw_articles, sentiment_results, events):
            enriched.append({
                "headline": article.get("headline", ""),
                "url": article.get("url", ""),
                "published": article.get("datetime", ""),
                "source": article.get("source", ""),
                "sentiment_score": sent.score,
                "sentiment_label": sent.sentiment,
                "event_type": event.event_type,
                "impact_magnitude": event.impact_magnitude,
                "is_positive": event.is_positive,
            })
        analysis.articles = enriched

        # ── Top headlines ─────────────────────────────────────────────────────
        sorted_by_score = sorted(enriched, key=lambda x: x["sentiment_score"], reverse=True)
        analysis.top_positive = [a["headline"] for a in sorted_by_score[:3] if a["sentiment_score"] > 0.1]
        analysis.top_negative = [a["headline"] for a in sorted_by_score[-3:] if a["sentiment_score"] < -0.1]

        # ── High-impact events ────────────────────────────────────────────────
        analysis.high_impact_events = [
            a["headline"]
            for a in enriched
            if a["impact_magnitude"] >= 0.7
        ][:5]

        return analysis

    @cached(ttl=3600, prefix="news:market")
    def analyze_market(self, days: int = 3) -> NewsAnalysis:
        """Analyze broad market news (no specific symbol)."""
        end = date.today()
        start = end - timedelta(days=days)
        logger.info("[NewsAnalyzer] Analyzing market-wide news")

        raw = []
        if self.finnhub.is_available():
            try:
                raw = self.finnhub.fetch_market_news("general")
            except Exception as e:
                logger.warning(f"[NewsAnalyzer] Market news fetch failed: {e}")

        analysis = NewsAnalysis(symbol=None, period_start=start, period_end=end)
        if not raw:
            return analysis

        analysis.article_count = len(raw)
        headlines = [a.get("headline", "") for a in raw if a.get("headline")]
        results = self.sentiment.analyze_batch(headlines)
        agg = self.sentiment.aggregate(results)

        analysis.sentiment_score = agg["score"]
        analysis.sentiment_label = agg["sentiment"]
        analysis.sentiment_confidence = agg["confidence"]

        events = self.extractor.extract_batch(headlines)
        analysis.events = events
        analysis.event_types = list({e.event_type for e in events if e.event_type != "GENERAL"})
        analysis.sector_impact = self.extractor.aggregate_sector_impact(events)
        analysis.high_impact_events = [
            e.headline for e in sorted(events, key=lambda x: x.impact_magnitude, reverse=True)
            if e.impact_magnitude >= 0.7
        ][:10]

        return analysis
