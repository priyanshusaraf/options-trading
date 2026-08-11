"""E1 — a position whose instrument key is no longer in the registry ("poisoned"
key) must NOT abort risk management for the whole book.

Reproduces the shipped failure: the owner removes an instrument from the portfolio
(`POST /api/portfolio/remove`) while the bot holds a position on it. `load_universe`
pops a deactivated user instrument, so `get_instrument(key)` raises KeyError, and the
unguarded list comprehension in `mark_and_exit_positions` took down marking, trailing
stops and SL/TP for EVERY open position — silently, every ~1s, forever.
"""
from app.core.instruments import get_instrument
from app.db.session import init_db
from app.engine.runner import EngineRunner

GHOST = "GHOST_DELISTED"


def _runner():
    init_db(reset=True)
    return EngineRunner()


def _open_option(r, key):
    inst = get_instrument(key)
    chain = r.provider.get_option_chain(inst)
    return r.broker.open_position(inst, "LONG", chain.quotes[0], "t",
                                  r.provider.now(), chain.spot)


def _poison(r, pos):
    """Make this position's key unresolvable, exactly as a removed instrument does."""
    pos.instrument_key = GHOST
    r.broker.commit()


def test_poisoned_key_does_not_stop_the_rest_of_the_book_being_marked():
    r = _runner()
    bad = _open_option(r, "GOLDM")
    good = _open_option(r, "NIFTY")
    _poison(r, bad)
    # neutralise the healthy position's exits so this test isolates "was it marked?"
    # and can't be perturbed by whatever the mock premium happens to do.
    good.stop_price = 0.0
    good.no_take_profit = True
    r.broker.commit()

    r.mark_and_exit_positions()          # must not raise

    # the per-position marks feed is only reached at the END of a position's pass, so
    # an entry here proves the healthy position was fully processed despite the ghost.
    assert "NIFTY" in r.position_ticks, (
        "the healthy position was never processed — the poisoned key aborted the batch")
    assert GHOST not in r.position_ticks


def test_poisoned_key_does_not_stop_the_mis_close_flatten():
    """`square_off_intraday` is the sole authority that keeps MIS legal by close.
    A poisoned key must not leave other MIS positions carrying overnight."""
    r = _runner()
    inst = get_instrument("NIFTY")
    bad = r.broker.open_equity_position(inst, "LONG", 100.0, 10, "equity_intraday",
                                        "t", r.provider.now())
    good = r.broker.open_equity_position(get_instrument("GOLDM"), "LONG", 200.0, 5,
                                         "equity_intraday", "t", r.provider.now())
    _poison(r, bad)

    # force "at the close" for every segment so the flatten is due
    r.params["intraday_square_off_buffer_minutes"] = 10 ** 6
    r.square_off_intraday(r.provider.now())     # must not raise

    still_open = {p.id for p in r.broker.open_positions()}
    assert good.id not in still_open, (
        "healthy MIS position was left open — the poisoned key aborted the flatten")
    assert bad.id not in still_open, (
        "the poisoned MIS position itself was left to carry overnight, which MIS "
        "cannot legally do — it must be flattened on the NSE fallback clock")


def test_removing_an_instrument_with_an_open_position_is_refused():
    """Don't let the cockpit create a poisoned key in the first place."""
    from app.core import universe_resolver

    r = _runner()
    _open_option(r, "GOLDM")

    res = universe_resolver.remove_instrument("GOLDM", owner_id="owner")

    assert "error" in res, f"removal should have been refused, got {res}"
    assert get_instrument("GOLDM") is not None      # still resolvable
