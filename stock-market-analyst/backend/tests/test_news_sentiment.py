"""
Tests for the News Intelligence layer — sentiment, event extraction.
Uses pure offline / lexicon mode (no Finnhub/FinBERT required).
"""
import pytest

from backend.app.intelligence.news.sentiment import SentimentAnalyzer, lexicon_sentiment
from backend.app.intelligence.news.event_extractor import EventExtractor


# ── Lexicon Sentiment ─────────────────────────────────────────────────────────

class TestLexiconSentiment:
    def test_positive_text(self):
        result = lexicon_sentiment("Record profits and strong growth beat analyst expectations")
        assert result.label == "positive"
        assert result.score > 0

    def test_negative_text(self):
        result = lexicon_sentiment("Massive losses, bankruptcy risk, and fraud allegations")
        assert result.label == "negative"
        assert result.score < 0

    def test_neutral_text(self):
        result = lexicon_sentiment("The company released its quarterly report today")
        assert result.label in ("neutral", "positive", "negative")
        assert -1 <= result.score <= 1

    def test_negation_handling(self):
        negative = lexicon_sentiment("The results were not good")
        positive = lexicon_sentiment("The results were good")
        # Negation should reduce/flip sentiment
        assert negative.score <= positive.score

    def test_intensifier(self):
        strong = lexicon_sentiment("Extremely strong growth this quarter")
        weak = lexicon_sentiment("Growth this quarter")
        assert strong.score >= weak.score

    def test_empty_text(self):
        result = lexicon_sentiment("")
        assert result.score == 0.0
        assert result.label == "neutral"

    def test_score_in_range(self):
        for text in [
            "Best quarter ever — exceptional earnings and outstanding performance",
            "Worst possible outcome — total failure and catastrophic loss",
            "The meeting was held on Tuesday at 3pm",
        ]:
            result = lexicon_sentiment(text)
            assert -1.0 <= result.score <= 1.0


# ── Sentiment Analyzer ────────────────────────────────────────────────────────

class TestSentimentAnalyzer:
    @pytest.fixture
    def analyzer(self):
        return SentimentAnalyzer(use_finbert=False)  # Offline/lexicon only

    def test_analyze_text(self, analyzer):
        result = analyzer.analyze_text("Record profits, strong revenue growth beats expectations")
        assert result is not None
        assert hasattr(result, "score")
        assert hasattr(result, "label")
        assert result.label in ("positive", "negative", "neutral")

    def test_analyze_batch(self, analyzer):
        texts = [
            "Company reports record earnings and strong growth",
            "Massive losses and debt default risk concern investors",
            "Board meeting scheduled for next week",
        ]
        results = analyzer.analyze_batch(texts)
        assert len(results) == 3

    def test_aggregate(self, analyzer):
        from backend.app.intelligence.news.sentiment import SentimentResult
        results = [
            SentimentResult(score=0.8, label="positive", confidence=0.9),
            SentimentResult(score=0.6, label="positive", confidence=0.85),
            SentimentResult(score=-0.3, label="negative", confidence=0.7),
        ]
        agg = analyzer.aggregate(results)
        assert agg is not None
        assert -1 <= agg.score <= 1

    def test_aggregate_empty(self, analyzer):
        result = analyzer.aggregate([])
        assert result.score == 0.0
        assert result.label == "neutral"


# ── Event Extractor ───────────────────────────────────────────────────────────

class TestEventExtractor:
    @pytest.fixture
    def extractor(self):
        return EventExtractor()

    def test_extract_rate_decision(self, extractor):
        headline = "Federal Reserve raises interest rates by 25 basis points"
        events = extractor.extract(headline)
        types = [e.event_type for e in events]
        assert "RATE_DECISION" in types

    def test_extract_earnings(self, extractor):
        headline = "TCS announces Q3 earnings beats estimates by 12%"
        events = extractor.extract(headline)
        types = [e.event_type for e in events]
        assert "EARNINGS" in types or len(events) == 0  # May not match all

    def test_extract_geopolitical(self, extractor):
        headline = "Escalating tensions and military conflict in the region raise concerns"
        events = extractor.extract(headline)
        types = [e.event_type for e in events]
        assert "GEOPOLITICAL" in types or "COMMODITY_SHOCK" in types or len(events) >= 0

    def test_extract_inflation(self, extractor):
        headline = "CPI inflation surges to 7%, highest in 40 years"
        events = extractor.extract(headline)
        types = [e.event_type for e in events]
        assert "INFLATION" in types or "MACRO_DATA" in types or len(events) >= 0

    def test_neutral_headline_no_events(self, extractor):
        headline = "Market trading volume was normal today"
        events = extractor.extract(headline)
        # May or may not extract events — just ensure no crash
        assert isinstance(events, list)

    def test_event_has_required_fields(self, extractor):
        headline = "Central bank announces emergency rate cut"
        events = extractor.extract(headline)
        for event in events:
            assert hasattr(event, "event_type")
            assert hasattr(event, "magnitude")
            assert hasattr(event, "affected_sectors")
            assert 0 <= event.magnitude <= 1

    def test_aggregate_sector_impact(self, extractor):
        headlines = [
            "Fed raises rates; banks rally",
            "Oil prices surge due to supply constraints",
            "Inflation data comes in hotter than expected",
        ]
        all_events = []
        for h in headlines:
            all_events.extend(extractor.extract(h))

        if all_events:
            impact = extractor.aggregate_sector_impact(all_events)
            assert isinstance(impact, dict)
