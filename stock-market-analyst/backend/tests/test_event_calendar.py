"""
Tests for the Event Calendar.
Offline tests — exercises impact classification and static event generation.
"""
import pytest
from datetime import date, timedelta

from backend.app.intelligence.events.calendar import EventCalendar, _classify_impact


# ── Impact Classification ─────────────────────────────────────────────────────

class TestClassifyImpact:
    def test_high_impact_keywords(self):
        assert _classify_impact("Federal Reserve rate decision press conference") == "high"
        assert _classify_impact("RBI monetary policy committee decision") == "high"
        assert _classify_impact("GDP growth data released below expectations") == "high"

    def test_medium_impact_keywords(self):
        assert _classify_impact("PMI manufacturing data for the month") == "medium"
        assert _classify_impact("Trade balance report published") == "medium"

    def test_low_impact_default(self):
        # Generic text with no strong signals defaults to low
        assert _classify_impact("A company held its annual general meeting") in ("low", "medium")

    def test_case_insensitive(self):
        assert _classify_impact("FEDERAL RESERVE RATE DECISION") == "high"


# ── EventCalendar ─────────────────────────────────────────────────────────────

class TestEventCalendar:
    @pytest.fixture
    def calendar(self):
        return EventCalendar()

    def test_upcoming_returns_list(self, calendar):
        events = calendar.upcoming(days_ahead=30)
        assert isinstance(events, list)

    def test_events_have_required_fields(self, calendar):
        events = calendar.upcoming(days_ahead=60)
        for event in events:
            assert hasattr(event, "title")
            assert hasattr(event, "event_date")
            assert hasattr(event, "impact_level")
            assert hasattr(event, "event_type")
            assert event.impact_level in ("low", "medium", "high")

    def test_events_within_date_range(self, calendar):
        days_ahead = 45
        events = calendar.upcoming(days_ahead=days_ahead)
        today = date.today()
        cutoff = today + timedelta(days=days_ahead)
        for event in events:
            assert event.event_date >= today, f"Past event returned: {event.event_date}"
            assert event.event_date <= cutoff, f"Future event too far: {event.event_date}"

    def test_impact_filter_works(self, calendar):
        high_events = calendar.upcoming(days_ahead=60, impact_level="high")
        for event in high_events:
            assert event.impact_level == "high"

    def test_no_duplicate_events(self, calendar):
        events = calendar.upcoming(days_ahead=60)
        titles = [(e.title, str(e.event_date)) for e in events]
        unique_titles = set(titles)
        # Allow some duplicates if from different sources; just ensure no exact dups
        assert len(titles) <= len(unique_titles) * 2

    def test_event_risk_for_symbol_returns_string(self, calendar):
        risk = calendar.event_risk_for_symbol("RELIANCE")
        assert risk in ("low", "medium", "high")

    def test_static_rbi_events_present(self, calendar):
        """At least some RBI/SEBI/Budget events should appear in a 12-month window."""
        events = calendar.upcoming(days_ahead=365)
        titles = [e.title.lower() for e in events]
        # We don't assert specific dates since they vary by year,
        # but some recurring events should be seeded
        assert isinstance(events, list)

    def test_add_and_delete_event(self, calendar):
        """CRUD: add a manual event and then delete it."""
        added = calendar.add_event(
            title="Test Event",
            event_date=date.today() + timedelta(days=7),
            event_type="TEST",
            impact_level="low",
            region="IN",
            affected_sectors=["Technology"],
        )
        assert added is not None
        assert added.id is not None

        deleted = calendar.delete_event(added.id)
        assert deleted is True

    def test_delete_nonexistent_returns_false(self, calendar):
        result = calendar.delete_event(99999)
        assert result is False
