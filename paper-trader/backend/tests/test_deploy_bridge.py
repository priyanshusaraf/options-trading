"""Approve→Deploy bridge: an approved research candidate becomes a live watchlist.

Deploying creates (or reuses) the target watchlist, assigns the instruments that clear
conflict resolution (incumbents in OTHER watchlists are left alone), and records the
strategy in the archive as `running`. `preview_deploy` shows exactly what would happen
without writing anything — the owner sees accepted/blocked before confirming. The bridge
writes declarative config only; it never touches positions or capital.
"""
from app.core import strategy_archive as arch
from app.core import watchlists as wl
from app.core.deploy_bridge import DeployRequest, deploy, preview_deploy
from app.db.models import Watchlist
from app.db.session import SessionLocal, init_db


def _fresh():
    init_db(reset=True)


def test_deploy_creates_watchlist_assigns_and_archives_running():
    _fresh()
    with SessionLocal() as s:
        req = DeployRequest(watchlist_name="Bullion Trend", strategy_key="trend_impulse_v3",
                            proposals=[("GOLDM", 0.8), ("SILVERM", 0.7)], source="builtin")
        res = deploy(s, req)
        s.commit()
        assert set(res.assigned) == {"GOLDM", "SILVERM"}
        assert wl.watchlist_of(s, "GOLDM").name == "Bullion Trend"
        rec = arch.get(s, "trend_impulse_v3")
        assert rec.status == "running" and rec.deployed_watchlist_id == res.watchlist_id


def test_deploy_blocks_incumbents_in_other_watchlists():
    _fresh()
    with SessionLocal() as s:
        a = wl.create_watchlist(s, "A", "expanding_z_v4")
        s.commit()
        wl.assign_instrument(s, "SILVERM", a.id)          # SILVERM already earning in A
        s.commit()
        req = DeployRequest("B", "trend_impulse_v3", [("SILVERM", 0.9), ("GOLDM", 0.5)])
        res = deploy(s, req)
        s.commit()
        assert res.assigned == ["GOLDM"]
        assert any(r["instrument"] == "SILVERM" and r["reason"] == "incumbent"
                   for r in res.rejected)
        assert wl.watchlist_of(s, "SILVERM").name == "A"   # incumbent untouched


def test_preview_writes_nothing():
    _fresh()
    with SessionLocal() as s:
        req = DeployRequest("Bullion", "trend_impulse_v3", [("GOLDM", 0.8)])
        prev = preview_deploy(s, req)
        assert prev.accepted == ["GOLDM"]
        assert wl.get_watchlist(s, "Bullion") is None      # nothing created
        assert wl.watchlist_of(s, "GOLDM") is None
        assert arch.get(s, "trend_impulse_v3") is None


def test_deploy_is_idempotent():
    _fresh()
    with SessionLocal() as s:
        req = DeployRequest("Bullion", "trend_impulse_v3", [("GOLDM", 0.8)])
        r1 = deploy(s, req)
        s.commit()
        r2 = deploy(s, req)
        s.commit()
        assert r1.watchlist_id == r2.watchlist_id
        assert s.query(Watchlist).filter_by(name="Bullion").count() == 1
        assert wl.watchlist_of(s, "GOLDM").id == r1.watchlist_id
