"""Adaptive order routing. Market orders on a wide book (illiquid commodity
options like the COPPER example) fill deep in the spread — so we only route MARKET
when the book is tight and deep, use a capped marketable-limit when it's moderate,
and SKIP the entry entirely when it's as ugly as COPPER. Protective exits always
go MARKET (getting out beats slippage)."""
from app.engine import execution_policy as policy

plan_order = policy.plan_order

P = {
    "entry_order_mode": "AUTO",
    "exec_market_max_spread_pct": 0.01,   # <=1% spread -> MARKET ok
    "exec_limit_max_spread_pct": 0.05,    # 1%..5% -> capped LIMIT; >5% -> SKIP
    "exec_max_slippage_pct": 0.01,        # cap the limit at 1% off the mid
    "exec_min_top_qty_lots": 1.0,         # need >=1 lot of top-of-book depth for MARKET
}


def test_tight_deep_book_routes_market():
    # NIFTY-like: ~1% spread, plenty of depth -> MARKET (don't miss the move)
    plan = plan_order("ENTRY", "BUY", bid=99.5, ask=100.5, ltp=100.0,
                      top_qty=1000, lot_qty=75, params=P)
    assert plan.action == "MARKET"


def test_moderate_spread_routes_capped_limit():
    # ~3% spread -> marketable LIMIT capped at +1% of mid (<= 101.0)
    plan = plan_order("ENTRY", "BUY", bid=98.5, ask=101.5, ltp=100.0,
                      top_qty=1000, lot_qty=75, params=P)
    assert plan.action == "LIMIT"
    assert 0 < plan.limit_price <= 100.0 * 1.01 + 1e-9


def test_copper_like_wide_spread_skips_entry():
    # COPPER-like: 40% spread -> never send a market order into that -> SKIP
    plan = plan_order("ENTRY", "BUY", bid=80.0, ask=120.0, ltp=100.0,
                      top_qty=1000, lot_qty=75, params=P)
    assert plan.action == "SKIP" and "spread" in plan.reason.lower()


def test_thin_depth_downgrades_market_to_limit():
    # tight spread but <1 lot on top of book -> don't market into a thin book
    plan = plan_order("ENTRY", "BUY", bid=99.5, ask=100.5, ltp=100.0,
                      top_qty=10, lot_qty=75, params=P)
    assert plan.action == "LIMIT"


def test_unknown_depth_allows_market_on_tight_spread():
    # paper/mock has no depth (None) -> spread alone gates; tight -> MARKET
    plan = plan_order("ENTRY", "BUY", bid=99.6, ask=100.4, ltp=100.0,
                      top_qty=None, lot_qty=75, params=P)
    assert plan.action == "MARKET"


def test_missing_quote_treated_as_wide():
    plan = plan_order("ENTRY", "BUY", bid=0.0, ask=0.0, ltp=100.0,
                      top_qty=None, lot_qty=75, params=P)
    assert plan.action == "SKIP"


def test_protective_exit_always_market():
    # even a horrible spread -> exits go MARKET; not exiting is worse than slippage
    plan = plan_order("EXIT", "SELL", bid=80.0, ask=120.0, ltp=100.0,
                      top_qty=1000, lot_qty=75, params={**P, "entry_order_mode": "LIMIT"})
    assert plan.action == "MARKET"


def test_forced_limit_prices_buy_and_short_entry_in_opposite_directions():
    params = {**P, "entry_order_mode": "LIMIT"}
    buy = plan_order("ENTRY", "BUY", 99.0, 101.0, 100.0, 1000, 10, params)
    short = plan_order("ENTRY", "SELL", 99.0, 101.0, 100.0, 1000, 10, params)
    assert buy.action == "LIMIT" and buy.limit_price == 101.0
    assert short.action == "LIMIT" and short.limit_price == 99.0


def test_forced_market_keeps_the_known_thin_book_veto():
    plan = plan_order("ENTRY", "BUY", 99.8, 100.2, 100.0, 5, 10,
                      {**P, "entry_order_mode": "MARKET"})
    assert plan.action == "SKIP"
    assert "thin" in plan.reason.lower()


def test_forced_market_uses_market_on_moderate_but_acceptable_book():
    plan = plan_order("ENTRY", "BUY", 98.5, 101.5, 100.0, 1000, 10,
                      {**P, "entry_order_mode": "MARKET"})
    assert plan.action == "MARKET"


def test_reference_limit_is_side_aware_without_fabricating_a_book():
    params = {**P, "entry_order_mode": "LIMIT"}
    assert policy.plan_reference_entry("BUY", 100.0, params).limit_price == 101.0
    assert policy.plan_reference_entry("SELL", 100.0, params).limit_price == 99.0


def test_reference_auto_preserves_legacy_equity_market_behavior():
    assert policy.plan_reference_entry("SELL", 100.0, P).action == "MARKET"
