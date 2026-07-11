"""Shared fixtures for the research-plane test suite (run: `pytest research_tests`).

Each test gets a throwaway file-backed research.db (WAL needs a real file), with
the full research schema created — including the immutability triggers.
"""
import pytest

from research.domain.base import init_research_db, make_engine, make_sessionmaker


@pytest.fixture
def research_session(tmp_path):
    engine = make_engine(str(tmp_path / "research.db"))
    init_research_db(engine)
    Session = make_sessionmaker(engine)
    with Session() as s:
        yield s
