"""Conflict/incumbency resolution when a new watchlist proposes instruments.

Rules:
  * INCUMBENCY — an instrument already in a watchlist is untouched; a new proposal for
    it is rejected outright, even if the newcomer performs better. Incumbency > score.
  * DISPUTE — if two *new* proposals want the same (non-incumbent) instrument, the
    higher performance score wins; ties break to the lower watchlist id (determinism).
"""
from app.core import watchlists as wl
from app.core.watchlists import Proposal, apply_resolution, resolve_conflicts
from app.db.session import SessionLocal, init_db


def _fresh():
    init_db(reset=True)


def test_incumbent_is_untouched_even_by_a_better_performer():
    current = {"SILVERM": 1}                                   # already in watchlist 1
    props = [Proposal(watchlist_id=2, instrument_key="SILVERM", score=99.0)]
    res = resolve_conflicts(current, props)
    assert "SILVERM" not in res.assign
    assert res.rejected == [{"instrument": "SILVERM", "watchlist_id": 2, "reason": "incumbent"}]


def test_better_performer_wins_a_dispute():
    props = [Proposal(2, "SILVERM", 0.4), Proposal(3, "SILVERM", 0.9)]
    res = resolve_conflicts({}, props)
    assert res.assign["SILVERM"] == 3
    assert {"instrument": "SILVERM", "watchlist_id": 2, "reason": "lost dispute"} in res.rejected


def test_uncontested_proposal_is_accepted():
    res = resolve_conflicts({}, [Proposal(5, "GOLDM", 0.5)])
    assert res.assign == {"GOLDM": 5}
    assert res.rejected == []


def test_tie_breaks_to_lower_watchlist_id():
    res = resolve_conflicts({}, [Proposal(7, "CRUDEOIL", 0.5), Proposal(4, "CRUDEOIL", 0.5)])
    assert res.assign["CRUDEOIL"] == 4


def test_apply_resolution_writes_winners_and_leaves_incumbents_alone():
    _fresh()
    with SessionLocal() as s:
        a = wl.create_watchlist(s, "A", "trend_impulse_v3")
        b = wl.create_watchlist(s, "B", "expanding_z_v4")
        s.commit()
        wl.assign_instrument(s, "SILVERM", a.id)               # SILVERM is A's incumbent
        s.commit()
        current = {"SILVERM": a.id}
        props = [Proposal(b.id, "SILVERM", 0.9), Proposal(b.id, "GOLDM", 0.5)]
        res = resolve_conflicts(current, props)
        apply_resolution(s, res)
        s.commit()
        assert wl.watchlist_of(s, "SILVERM").id == a.id        # incumbent kept
        assert wl.watchlist_of(s, "GOLDM").id == b.id          # winner assigned
