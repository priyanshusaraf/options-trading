"""Task 6 regression proofs for answer-changing public cache keys."""
import datetime as dt

from app.core import universe_resolver
from app.core.instruments import Instrument
from app.options import cache


class CatalogProvider:
    def __init__(self, source_id, key):
        self.name = "market"
        self.source_id = source_id
        self.key = key
        self.calls = 0

    def is_authenticated(self):
        return False


def test_catalog_cache_does_not_share_answers_between_provider_sources(monkeypatch):
    universe_resolver._catalog.clear()
    p1 = CatalogProvider("provider-1", "P1")
    p2 = CatalogProvider("provider-2", "P2")

    def catalog(provider):
        provider.calls += 1
        return [Instrument(provider.key, provider.key, "NSE", "NSE", provider.key,
                           provider.key, 1, 1, 1, 100.0, 0.2)]

    from app.backtest import universe
    monkeypatch.setattr(universe, "liquid_universe", catalog)
    assert universe_resolver._build_catalog(p1)["P1"].key == "P1"
    assert universe_resolver._build_catalog(p2)["P2"].key == "P2"
    assert p1.calls == p2.calls == 1


def test_option_snapshot_throttle_is_provider_scoped(monkeypatch):
    cache._last_snapshot.clear()
    inst = Instrument("NIFTY", "NIFTY", "NFO", "NSE", "NIFTY", "NIFTY", 1, 1, 1, 100.0, 0.2)
    now = dt.datetime(2026, 8, 12, 10, 0)
    chain = type("Chain", (), {"expiry": now.date(), "spot": 100.0, "quotes": []})()
    commits = []

    class Session:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def add(self, _): pass
        def commit(self): commits.append(True)

    monkeypatch.setattr(cache, "SessionLocal", lambda: Session())
    p1 = type("Provider", (), {"name": "market", "source_id": "p1"})()
    p2 = type("Provider", (), {"name": "market", "source_id": "p2"})()
    assert cache.persist_chain(chain, inst, now, 15.0, provider=p1) == 0
    assert cache.persist_chain(chain, inst, now, 15.0, provider=p1) == 0
    assert cache.persist_chain(chain, inst, now, 15.0, provider=p2) == 0
    assert len(commits) == 2
