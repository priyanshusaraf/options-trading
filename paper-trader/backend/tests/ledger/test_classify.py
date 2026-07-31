"""The classifier is pure: dicts in, a verdict out. Every ambiguity must land in
NEEDS_REVIEW rather than being guessed either way."""
from app.ledger.classify import BOT, BOT_TAG, MANUAL, NEEDS_REVIEW, classify_order


def order(**kw):
    base = {"order_id": "o1", "tag": None, "tradingsymbol": "NIFTY25000CE",
            "status": "COMPLETE", "transaction_type": "BUY", "filled_quantity": 65,
            "average_price": 120.5, "product": "NRML"}
    base.update(kw)
    return base


def test_bot_tag_alone_is_enough():
    assert classify_order(order(tag=BOT_TAG), set(), set()) == BOT


def test_order_id_in_the_local_journal_is_enough():
    assert classify_order(order(order_id="o9"), {"o9"}, set()) == BOT


def test_untagged_and_unknown_on_a_symbol_the_bot_never_touched_is_manual():
    assert classify_order(order(), set(), set()) == MANUAL


def test_untagged_on_a_symbol_the_bot_held_today_is_needs_review():
    # A GTT-fired stop carries no tag and is created server-side by Zerodha, so
    # it is indistinguishable from a manual order except by symbol.
    assert classify_order(order(tradingsymbol="RELIANCE"), set(),
                          {"RELIANCE"}) == NEEDS_REVIEW


def test_a_missing_tag_key_is_treated_as_untagged_not_as_an_error():
    o = order()
    del o["tag"]
    assert classify_order(o, set(), set()) == MANUAL


def test_empty_string_tag_is_untagged():
    assert classify_order(order(tag=""), set(), set()) == MANUAL


def test_tag_comparison_is_exact_not_prefix():
    assert classify_order(order(tag="pt-bot-v2"), set(), set()) == MANUAL


def test_cnc_product_is_manual_even_on_a_bot_symbol():
    # The bot uses MIS or NRML only; it cannot place a delivery order, so the
    # symbol overlap that normally forces NEEDS_REVIEW does not apply.
    assert classify_order(order(product="CNC", tradingsymbol="RELIANCE"),
                          set(), {"RELIANCE"}) == MANUAL


def test_a_none_order_id_cannot_match_the_journal():
    # A crash between _journal_open and the placement ack leaves order_id NULL.
    # It must not accidentally match a set that contains None.
    assert classify_order(order(order_id=None), set(), set()) == MANUAL


def test_order_ids_compare_as_strings():
    assert classify_order(order(order_id="250731000123"), {"250731000123"},
                          set()) == BOT


def test_symbol_match_is_case_insensitive():
    assert classify_order(order(tradingsymbol="reliance"), set(),
                          {"RELIANCE"}) == NEEDS_REVIEW


def test_the_tag_wins_over_a_symbol_overlap():
    assert classify_order(order(tag=BOT_TAG, tradingsymbol="RELIANCE"), set(),
                          {"RELIANCE"}) == BOT


def test_a_manual_option_trade_on_an_untouched_symbol_is_manual():
    # The everyday case: owner buys a Nifty option by hand from the Zerodha app
    # while the bot is trading equities.
    assert classify_order(order(tradingsymbol="NIFTY25000PE", product="NRML"),
                          {"other1", "other2"}, {"RELIANCE", "TCS"}) == MANUAL
