"""Allocation rule (owner-specified): if capital covers every simultaneous signal,
fund them all. Only under a shortfall does the liquidity priority order decide who
gets funded — strictly greedy by priority, no max-fill optimisation. Anything
unfunded this tick is dropped (never queued)."""
from app.engine.allocator import Candidate, allocate


def test_empty_candidates():
    res = allocate([], available_cash=50_000)
    assert res.funded == []
    assert res.skipped == []


def test_all_funded_when_capital_is_sufficient():
    cands = [
        Candidate("DHANIYA", "LONG", 10_000),
        Candidate("NIFTY", "LONG", 12_000),
        Candidate("GOLDM", "SHORT", 6_000),
    ]
    res = allocate(cands, available_cash=50_000)
    assert {c.instrument_key for c in res.funded} == {"NIFTY", "GOLDM", "DHANIYA"}
    assert res.skipped == []


def test_funded_in_priority_order():
    cands = [
        Candidate("DHANIYA", "LONG", 10_000),   # priority 11
        Candidate("GOLDM", "SHORT", 6_000),     # priority 2
        Candidate("NIFTY", "LONG", 12_000),     # priority 1
    ]
    res = allocate(cands, available_cash=50_000)
    assert [c.instrument_key for c in res.funded] == ["NIFTY", "GOLDM", "DHANIYA"]


def test_priority_decides_under_shortfall():
    # NIFTY (prio 1) and DHANIYA (prio 11) each cost 30k; only 50k available.
    # NIFTY funds first (20k left), DHANIYA's 30k no longer fits -> dropped.
    cands = [
        Candidate("DHANIYA", "LONG", 30_000),
        Candidate("NIFTY", "LONG", 30_000),
    ]
    res = allocate(cands, available_cash=50_000)
    assert [c.instrument_key for c in res.funded] == ["NIFTY"]
    assert [c.instrument_key for c, _ in res.skipped] == ["DHANIYA"]


def test_greedy_not_maxfill():
    # NIFTY 40k then GOLDM 15k with 50k: strict greedy funds NIFTY, then GOLDM
    # (15k) does not fit in the remaining 10k and is skipped — even though
    # skipping NIFTY could have fit more rupees of lower-priority orders.
    cands = [
        Candidate("GOLDM", "LONG", 15_000),
        Candidate("NIFTY", "LONG", 40_000),
    ]
    res = allocate(cands, available_cash=50_000)
    assert [c.instrument_key for c in res.funded] == ["NIFTY"]
    assert [c.instrument_key for c, _ in res.skipped] == ["GOLDM"]


def test_skipped_carries_a_reason():
    cands = [Candidate("NIFTY", "LONG", 80_000)]
    res = allocate(cands, available_cash=50_000)
    assert res.funded == []
    assert len(res.skipped) == 1
    assert res.skipped[0][1]  # non-empty reason string
