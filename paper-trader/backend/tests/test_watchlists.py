"""Watchlists: many named lists, each bound to ONE strategy. An instrument belongs
to at most one watchlist, and an *active* watchlist's strategy is what the engine
runs on its instruments (overriding the per-instrument default). Behaviour-preserving:
with no watchlists, today's per-instrument strategy resolution is unchanged.
"""
from app.core import watchlists as wl
from app.db.models import InstrumentState, WatchlistMembership
from app.db.session import SessionLocal, init_db


def _fresh():
    init_db(reset=True)


def test_create_and_get_watchlist():
    _fresh()
    with SessionLocal() as s:
        w = wl.create_watchlist(s, "Bullion Trend", "trend_impulse_v3")
        s.commit()
        assert w.id is not None
        got = wl.get_watchlist(s, "Bullion Trend")
        assert got.strategy_key == "trend_impulse_v3" and got.status == "active"


def test_instrument_belongs_to_at_most_one_watchlist():
    _fresh()
    with SessionLocal() as s:
        a = wl.create_watchlist(s, "A", "trend_impulse_v3")
        b = wl.create_watchlist(s, "B", "expanding_z_v4")
        s.commit()
        wl.assign_instrument(s, "SILVERM", a.id)
        s.commit()
        assert wl.watchlist_of(s, "SILVERM").name == "A"
        wl.assign_instrument(s, "SILVERM", b.id)   # reassign MOVES it, not duplicates
        s.commit()
        assert wl.watchlist_of(s, "SILVERM").name == "B"
        assert s.query(WatchlistMembership).filter_by(instrument_key="SILVERM").count() == 1


def test_unassign_removes_membership():
    _fresh()
    with SessionLocal() as s:
        a = wl.create_watchlist(s, "A", "trend_impulse_v3")
        s.commit()
        wl.assign_instrument(s, "GOLDM", a.id)
        s.commit()
        assert wl.unassign_instrument(s, "GOLDM") is True
        s.commit()
        assert wl.watchlist_of(s, "GOLDM") is None


def test_effective_strategy_map_uses_active_watchlist_strategy():
    _fresh()
    with SessionLocal() as s:
        a = wl.create_watchlist(s, "A", "expanding_z_v4")
        s.commit()
        wl.assign_instrument(s, "GOLDM", a.id)
        s.commit()
        assert wl.effective_strategy_map(s) == {"GOLDM": "expanding_z_v4"}


def test_paused_or_archived_watchlist_does_not_drive_strategy():
    _fresh()
    with SessionLocal() as s:
        a = wl.create_watchlist(s, "A", "expanding_z_v4", status="paused")
        s.commit()
        wl.assign_instrument(s, "GOLDM", a.id)
        s.commit()
        assert wl.effective_strategy_map(s) == {}


def test_no_watchlists_is_behaviour_preserving():
    _fresh()
    with SessionLocal() as s:
        assert wl.effective_strategy_map(s) == {}


def test_list_watchlists_reports_members_and_strategy():
    _fresh()
    with SessionLocal() as s:
        a = wl.create_watchlist(s, "Bullion", "expanding_z_v4")
        s.commit()
        wl.assign_instrument(s, "GOLDM", a.id)
        wl.assign_instrument(s, "SILVERM", a.id)
        s.commit()
        listed = {w["name"]: w for w in wl.list_watchlists(s)}
        assert listed["Bullion"]["strategy_key"] == "expanding_z_v4"
        assert set(listed["Bullion"]["instruments"]) == {"GOLDM", "SILVERM"}


def test_engine_prefers_active_watchlist_strategy_over_instrument_state():
    _fresh()
    from app.engine.runner import EngineRunner
    with SessionLocal() as s:
        # GOLDM is a seed instrument; pin its per-instrument strategy explicitly so the
        # test proves the watchlist beats even an explicit InstrumentState assignment.
        st = s.get(InstrumentState, "GOLDM") or InstrumentState(instrument_key="GOLDM")
        st.strategy_key = "trend_impulse_v3"
        st.enabled = True
        s.add(st)
        a = wl.create_watchlist(s, "Z", "expanding_z_v4")
        s.commit()
        wl.assign_instrument(s, "GOLDM", a.id)
        s.commit()
    r = EngineRunner()
    assert r.strategy_keys.get("GOLDM") == "expanding_z_v4"   # watchlist wins
