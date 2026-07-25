"""E10 — the overnight HOLD decision must never be applied to an MIS position.

`square_off_for_overnight` looped every open position with no segment filter, so an
intraday-equity (MIS) position could be tagged `held_overnight` — meaningless, and
illegal to actually carry. It was incidentally rescued by `square_off_intraday` moments
later only because both buffers default to the same value; set them apart (or let that
call throw) and an MIS position gets carried. `square_off_intraday` is the sole
segment-correct authority for MIS.
"""
from app.core.instruments import get_instrument
from app.db.session import init_db
from app.engine.runner import EngineRunner


def _runner_with_mis():
    init_db(reset=True)
    r = EngineRunner()
    pos = r.broker.open_equity_position(get_instrument("NIFTY"), "LONG", 100.0, 10,
                                        "NSE_INTRADAY", "t", r.provider.now(), params={})
    return r, pos


def test_mis_position_is_not_given_an_overnight_decision():
    r, pos = _runner_with_mis()

    decisions = r.square_off_for_overnight(r.provider.now())

    assert all(d["key"] != "NIFTY" for d in decisions), (
        f"MIS position was given an overnight decision: {decisions}")
    assert pos.held_overnight is False, "MIS position was tagged to carry overnight"
    assert r.broker.position_for("NIFTY") is not None, (
        "MIS position must be left for square_off_intraday, not closed on this path")


def test_an_options_position_still_gets_its_decision():
    """Guard against filtering out the segment this function actually exists for."""
    init_db(reset=True)
    r = EngineRunner()
    inst = get_instrument("NIFTY")
    chain = r.provider.get_option_chain(inst)
    r.broker.open_position(inst, "LONG", chain.quotes[0], "t", r.provider.now(), chain.spot)

    decisions = r.square_off_for_overnight(r.provider.now())

    assert any(d["key"] == "NIFTY" for d in decisions), decisions
