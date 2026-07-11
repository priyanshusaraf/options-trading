"""Research dev-blacklist: an instrument committed to a live watchlist is off-limits
for strategy development — EXCEPT the always-allowed commodity sandbox (GOLDM, SILVERM,
CRUDEOIL, NATURALGAS, COPPERM), which stays open to research even when deployed.

The research plane learns watchlist membership only from a read-only SNAPSHOT file — it
never opens the execution DB (fail-closed isolation). A missing snapshot means 'no
watchlists known' → nothing blacklisted.
"""
import json

from research.universe import (
    ALWAYS_ALLOWED,
    eligible_for_research,
    read_watchlist_snapshot,
)


def test_committed_instrument_is_blacklisted():
    allk = {"NIFTY", "BANKNIFTY", "GOLDM", "RELIANCE"}
    in_watchlists = {"NIFTY", "RELIANCE"}
    elig = eligible_for_research(allk, in_watchlists)
    assert "NIFTY" not in elig and "RELIANCE" not in elig
    assert "BANKNIFTY" in elig                     # uncommitted → eligible


def test_always_allowed_commodities_stay_eligible_even_when_committed():
    allk = {"GOLDM", "SILVERM", "CRUDEOIL", "NATURALGAS", "COPPERM", "NIFTY"}
    in_watchlists = set(allk)                       # everything committed
    elig = eligible_for_research(allk, in_watchlists)
    assert ALWAYS_ALLOWED <= elig                   # the 5 sandbox names survive
    assert "NIFTY" not in elig                      # a committed non-sandbox name does not


def test_nothing_committed_means_everything_eligible():
    allk = {"NIFTY", "GOLDM", "TCS"}
    assert eligible_for_research(allk, set()) == allk


def test_read_snapshot_reads_membership(tmp_path):
    p = tmp_path / "snap.json"
    p.write_text(json.dumps({"in_watchlists": ["NIFTY", "RELIANCE"]}))
    assert read_watchlist_snapshot(str(p)) == {"NIFTY", "RELIANCE"}


def test_missing_snapshot_is_empty_not_an_error():
    assert read_watchlist_snapshot("/no/such/snapshot.json") == set()
