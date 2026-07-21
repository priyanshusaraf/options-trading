"""Fix A (2026-07-14): size intraday-equity orders to the REAL Zerodha MIS margin
instead of an assumed 5x leverage.

Root cause (2026-07-13 live): the sizer assumed 5x, but Zerodha's real MIS margin on
those names was ~2.5x, so a bot-intended ~₹10k-margin order actually needed ~₹20k →
"Insufficient funds" rejections → the order circuit breaker DISARMED the bot for the day.

The pure selector now accepts an injected `sizer(cand, target_margin) -> (qty, margin)`
so the runner can size against a real per-share margin quote. With no sizer it keeps the
exact legacy leverage math (pinned by test_equity_entry.py).

2026-07-21 (owner): the artificial notional cap (Task 2, R2 2026-07-16) is REMOVED — it
throttled deployed real margin to ~4.5k. qty is now sized purely to the real margin quote
(deploy the FULL target margin) and Zerodha's own MIS multiplier decides the notional.
`intraday_leverage` only sizes the probe / fallback estimate now.
"""
import pytest

from app.engine.equity_entry import (
    IntradayCandidate, equity_qty, qty_for_margin, select_intraday_entries)


def _c(key, price, purple=False, direction="LONG"):
    return IntradayCandidate(key, direction, price, purple)


SEL = dict(max_positions=3, min_margin=5_000.0, max_margin=8_000.0,
           purple_margin=8_000.0, leverage=2.5, available_cash=1_000_000.0)


# ── qty_for_margin: the real-margin sizing primitive ──────────────────────────

def test_qty_for_margin_floors_to_target():
    # ₹228.75/share real margin, ₹8,000 target → 34 shares (₹7,777 margin)
    assert qty_for_margin(228.75, 8_000.0) == 34
    assert qty_for_margin(0.0, 8_000.0) == 0        # no quote → 0 (caller falls back/skips)
    assert qty_for_margin(9_000.0, 8_000.0) == 0    # 1 share exceeds target → 0


# ── select_intraday_entries with an injected real-margin sizer ────────────────

def test_injected_sizer_governs_qty_and_reported_margin():
    # A real per-share margin of ₹250 (regardless of price) → qty = floor(8000/250) = 32.
    def sizer(cand, target_margin):
        per_share = 250.0
        qty = qty_for_margin(per_share, target_margin)
        return qty, qty * per_share
    res = select_intraday_entries([_c("HEG", 555.65)], sizer=sizer, **SEL)
    assert len(res.selected) == 1
    p = res.selected[0]
    assert p.qty == 32
    assert p.margin == pytest.approx(8_000.0)       # 32 × 250, NOT price×qty/leverage


def test_injected_sizer_below_floor_is_skipped():
    # A name whose real margin can't reach the ₹5k floor at the target is dropped.
    def sizer(cand, target_margin):
        return 1, 1_000.0        # only ₹1,000 of margin fits → below the 5k floor
    res = select_intraday_entries([_c("X", 100)], sizer=sizer, **SEL)
    assert not res.selected
    assert any("floor" in reason.lower() for _, reason in res.skipped)


def test_injected_sizer_respects_available_cash():
    # Two names each needing ₹8k real margin but only ₹8k available → exactly one funds
    # fully; the second sizes against the ₹0 leftover → <1 share → skipped.
    def sizer(cand, target_margin):
        qty = equity_qty(target_margin, 2.5, cand.price)
        return qty, target_margin
    res = select_intraday_entries([_c("A", 100), _c("B", 200)], sizer=sizer,
                                  **{**SEL, "available_cash": 8_000.0})
    assert len(res.selected) == 1
    assert sum(p.margin for p in res.selected) <= 8_000.0 + 1e-6


def test_no_sizer_keeps_legacy_leverage_math():
    # Backward compatibility: without a sizer, qty/margin come from the leverage model.
    from app.engine.equity_entry import equity_qty
    res = select_intraday_entries([_c("A", 100)], **{**SEL, "leverage": 5.0})
    p = res.selected[0]
    assert p.qty == equity_qty(8_000.0, 5.0, 100)
    assert p.margin == pytest.approx(p.qty * 100 / 5.0)


# ── runner glue: builds a real-margin sizer from a Kite order_margins quote ────

class _KiteStub:
    """Minimal live-provider stand-in: quotes ₹`per_share`/share of real MIS margin."""
    name = "kite"

    def __init__(self, per_share=50.0):
        self.per_share = per_share
        self.calls = 0

    def is_authenticated(self):
        return True

    def order_margin(self, orders):
        self.calls += 1
        if self.per_share is None:
            return None
        return self.per_share * sum(o["quantity"] for o in orders)


def _runner_with_provider(provider):
    from app.db.session import init_db
    from app.engine.runner import EngineRunner
    init_db(reset=True)
    r = EngineRunner()
    r.provider = provider
    return r


def test_runner_sizer_sizes_to_real_margin_and_caches():
    from app.core.instruments import all_instruments
    r = _runner_with_provider(_KiteStub(per_share=50.0))   # ₹50/share real margin
    key = all_instruments()[0].key
    sizer = r._intraday_margin_sizer()
    assert sizer is not None
    qty, margin = sizer(_c(key, 100.0), 8_000.0)
    assert qty == 160 and margin == pytest.approx(8_000.0)   # floor(8000/50)=160
    # a second call for the same (symbol, side) reuses the cached quote — no re-hit
    sizer(_c(key, 100.0), 8_000.0)
    assert r.provider.calls == 1


def test_runner_sizer_falls_back_when_quote_unavailable():
    from app.engine.equity_entry import equity_qty
    from app.core.instruments import all_instruments
    r = _runner_with_provider(_KiteStub(per_share=None))    # quote fails → leverage fallback
    r.params["intraday_leverage"] = 2.5
    key = all_instruments()[0].key
    qty, margin = r._intraday_margin_sizer()(_c(key, 100.0), 8_000.0)
    assert qty == equity_qty(8_000.0, 2.5, 100.0)   # leverage model, not a crash


def test_runner_sizer_none_on_mock_provider():
    from app.db.session import init_db
    from app.engine.runner import EngineRunner
    init_db(reset=True)
    r = EngineRunner()                              # default mock provider
    assert r._intraday_margin_sizer() is None       # → select uses the leverage model


def test_fallback_path_scales_with_leverage():
    # When the quote fails, the pure leverage model is unchanged and scales with
    # whatever intraday_leverage is currently set to.
    from app.engine.equity_entry import equity_qty
    from app.core.instruments import all_instruments
    r = _runner_with_provider(_KiteStub(per_share=None))
    r.params["intraday_leverage"] = 4.0
    key = all_instruments()[0].key
    qty, margin = r._intraday_margin_sizer()(_c(key, 100.0), 8_000.0)
    assert qty == equity_qty(8_000.0, 4.0, 100.0)               # 320, not the default


# ── 2026-07-21 (owner): the artificial notional cap is REMOVED — qty is sized purely
# to the real Zerodha margin (deploy the full target), letting the broker's own MIS
# multiplier decide notional. `intraday_leverage` only sizes the probe / fallback. ──

def test_sizer_deploys_full_real_margin_regardless_of_leverage_estimate():
    from app.core.instruments import all_instruments
    # ₹20/share real margin on a ₹100 share ≈ 5x. Even with a conservative 2.5x
    # leverage estimate, qty is NOT capped — the full ₹8,000 of real margin deploys
    # (pre-2026-07-21 this capped to floor(8000×2.5/100)=200).
    r = _runner_with_provider(_KiteStub(per_share=20.0))
    r.params["intraday_leverage"] = 2.5
    key = all_instruments()[0].key
    qty, margin = r._intraday_margin_sizer()(_c(key, 100.0), 8_000.0)
    assert qty == qty_for_margin(20.0, 8_000.0)                 # 400 — full real margin
    assert qty == 400
    assert margin == pytest.approx(8_000.0)


def test_sizer_tiny_leverage_estimate_does_not_cap_when_quote_exists():
    from app.core.instruments import all_instruments
    # A tiny leverage estimate used to collapse qty via the cap; with the cap gone a
    # live quote sizes to the real margin regardless (and never crashes the cycle).
    r = _runner_with_provider(_KiteStub(per_share=20.0))
    r.params["intraday_leverage"] = 0.01
    key = all_instruments()[0].key
    qty, margin = r._intraday_margin_sizer()(_c(key, 100.0), 8_000.0)
    assert qty == 400 and margin == pytest.approx(8_000.0)


def test_sizer_share_too_expensive_for_target_returns_zero():
    from app.core.instruments import all_instruments
    # Real per-share margin exceeds the whole target → 0 shares (selector then skips).
    r = _runner_with_provider(_KiteStub(per_share=9_000.0))
    key = all_instruments()[0].key
    qty, margin = r._intraday_margin_sizer()(_c(key, 100.0), 8_000.0)
    assert qty == 0 and margin == 0.0


def test_expensive_real_margin_skipped_by_selector():
    from app.core.instruments import all_instruments
    r = _runner_with_provider(_KiteStub(per_share=9_000.0))
    key = all_instruments()[0].key
    sizer = r._intraday_margin_sizer()
    res = select_intraday_entries([_c(key, 100.0)], sizer=sizer, **SEL)
    assert not res.selected
    assert any("buys <1 share" in reason for _, reason in res.skipped)
