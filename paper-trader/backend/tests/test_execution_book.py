"""The canonical execution book — which ledger a piece of money state belongs to.

The book is the execution mode. These tests pin the two properties that make it safe
to build isolation on top of: it fails closed to `live`, and it never invents `paper`
out of missing or malformed input.
"""
from __future__ import annotations

import pytest

from app.core import execution_book as eb


class TestResolvingABook:
    def test_paper_resolves_to_paper(self):
        assert eb.resolve_book("paper") == eb.PAPER

    def test_live_resolves_to_live(self):
        assert eb.resolve_book("live") == eb.LIVE

    def test_case_and_whitespace_do_not_change_the_book(self):
        assert eb.resolve_book("  PAPER \n") == eb.PAPER
        assert eb.resolve_book("Live") == eb.LIVE

    @pytest.mark.parametrize("raw", [None, "", "   ", "papr", "simulated", "LIVE!",
                                     0, 1, True, object()])
    def test_unknown_missing_or_malformed_input_fails_closed_to_live(self, raw):
        """The safe direction is the one with the strictest rules. Defaulting to paper
        would let a misconfigured process inherit paper's permissions."""
        assert eb.resolve_book(raw) == eb.LIVE

    def test_paper_is_never_invented(self):
        """Stated separately from the parametrised case because it is the property that
        matters: no input other than the literal word yields the permissive book."""
        for raw in (None, "", "unknown", "live", "PAPERWORK", " pape r "):
            assert eb.resolve_book(raw) != eb.PAPER or raw == "paper"


class TestTheBookOfABroker:
    def test_a_paper_broker_is_the_paper_book(self):
        class B:
            MODE = "paper"
        assert eb.book_of(B()) == eb.PAPER

    def test_a_live_broker_is_the_live_book(self):
        class B:
            MODE = "live"
        assert eb.book_of(B()) == eb.LIVE

    def test_a_broker_with_no_mode_is_the_live_book(self):
        """`getattr(broker, 'MODE', 'paper')` was the shape used before this slice. An
        object that cannot say which book it writes to must not be assumed harmless."""
        class B:
            pass
        assert eb.book_of(B()) == eb.LIVE

    def test_a_broker_whose_mode_is_junk_is_the_live_book(self):
        class B:
            MODE = "??"
        assert eb.book_of(B()) == eb.LIVE


class TestTheConfiguredMode:
    def test_the_test_environment_is_paper(self):
        """conftest forces PT_EXECUTION=paper, so this pins the wiring to Settings
        rather than to a constant."""
        assert eb.configured_execution_mode() == eb.PAPER

    def test_an_unset_execution_setting_is_live(self, monkeypatch):
        from app.core import config

        class S:
            execution = ""
        monkeypatch.setattr(config, "get_settings", lambda: S())
        assert eb.configured_execution_mode() == eb.LIVE


class TestTheBookVocabulary:
    def test_there_are_exactly_two_books(self):
        """A third book would need its own capital row, its own reconciliation and its
        own authority grants. Adding one should fail this test first."""
        assert eb.BOOKS == (eb.PAPER, eb.LIVE)
