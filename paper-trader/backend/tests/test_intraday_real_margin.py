"""Fix A (2026-07-14): size intraday-equity orders to the REAL Zerodha MIS margin
instead of an assumed 5x leverage.

Root cause (2026-07-13 live): the sizer assumed 5x, but Zerodha's real MIS margin on
those names was ~2.5x, so a bot-intended ~₹10k-margin order actually needed ~₹20k →
"Insufficient funds" rejections → the order circuit breaker DISARMED the bot for the day.

The pure selector now accepts an injected `sizer(cand, target_margin) -> (qty, margin)`
so the runner can size against a real per-share margin quote. With no sizer it keeps the
exact legacy leverage math (pinned by test_equity_entry.py).
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
    # Two names each needing ₹8k real margin but only ₹8k available → exactly one funds.
    # (Fix, R2 review: qty must be leverage-consistent with SEL's leverage=2.5 — a flat
    # qty=10 regardless of price implied an unrealistic <1x real leverage that the
    # size-vs-min_margin floor now correctly treats as dust, which isn't what this test
    # is exercising. Sizing qty at the configured leverage keeps this test isolated to
    # the cash-affordability behavior it's named for.)
    def sizer(cand, target_margin):
        qty = equity_qty(target_margin, 2.5, cand.price)
        return qty, 8_000.0
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


def test_runner_sizer_sizes_to_real_margin_and_caches():
    from app.db.session import init_db
    from app.engine.runner import EngineRunner
    from app.core.instruments import all_instruments
    init_db(reset=True)
    r = EngineRunner()
    r.provider = _KiteStub(per_share=50.0)          # ₹50/share real margin
    key = all_instruments()[0].key
    sizer = r._intraday_margin_sizer()
    assert sizer is not None
    qty, margin = sizer(_c(key, 100.0), 8_000.0)
    assert qty == 160 and margin == pytest.approx(8_000.0)   # floor(8000/50)=160
    # a second call for the same (symbol, side) reuses the cached quote — no re-hit
    sizer(_c(key, 100.0), 8_000.0)
    assert r.provider.calls == 1


def test_runner_sizer_falls_back_when_quote_unavailable():
    from app.db.session import init_db
    from app.engine.runner import EngineRunner
    from app.engine.equity_entry import equity_qty
    from app.core.instruments import all_instruments
    init_db(reset=True)
    r = EngineRunner()
    r.provider = _KiteStub(per_share=None)          # quote fails → leverage fallback
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


# ── Task 2 (R2): intraday_leverage becomes a BINDING notional cap ────────────
# 2026-07-15 autopsy: all 7 instruments sized at margin/notional = 5.0 (Zerodha's
# real MIS multiplier) while intraday_leverage=2.5 was set to HALVE risk. The real
# margin quote only floors qty against broker rejection; it never capped notional
# to the owner's intended leverage. Fix: qty = min(real-margin qty, leverage-cap qty).

def test_leverage_cap_binds_when_real_margin_is_permissive():
    # Real per-share margin implies 5x (₹100 share needs ₹20 margin) but the owner
    # set intraday_leverage=2.5 to halve risk. The cap must bind: qty comes from the
    # leverage model, not the generous real-margin quote, and notional stays inside
    # target_margin × leverage.
    from app.db.session import init_db
    from app.engine.runner import EngineRunner
    from app.core.instruments import all_instruments
    init_db(reset=True)
    r = EngineRunner()
    r.provider = _KiteStub(per_share=20.0)          # ₹20/share margin on a ₹100 share = 5x
    r.params["intraday_leverage"] = 2.5
    key = all_instruments()[0].key
    target_margin = 8_000.0
    qty, margin = r._intraday_margin_sizer()(_c(key, 100.0), target_margin)
    real_margin_qty = qty_for_margin(20.0, target_margin)     # 400 — what 5x real margin allows
    assert real_margin_qty == 400
    assert qty == 200                                          # capped: floor(8000*2.5/100)
    assert qty < real_margin_qty                                # cap actually bound
    notional = qty * 100.0
    assert notional <= target_margin * 2.5 + 1e-6
    assert margin == pytest.approx(qty * 20.0)                  # real margin actually blocked


def test_real_margin_qty_binds_when_leverage_cap_is_generous():
    # Same 5x-permissive real margin, but a generous owner leverage (10x) — the real
    # broker margin is the tighter constraint and must win (never over-size beyond
    # what Zerodha will actually grant).
    from app.db.session import init_db
    from app.engine.runner import EngineRunner
    from app.core.instruments import all_instruments
    init_db(reset=True)
    r = EngineRunner()
    r.provider = _KiteStub(per_share=20.0)
    r.params["intraday_leverage"] = 10.0
    key = all_instruments()[0].key
    target_margin = 8_000.0
    qty, margin = r._intraday_margin_sizer()(_c(key, 100.0), target_margin)
    assert qty == 400                                           # real-margin qty binds
    assert margin == pytest.approx(8_000.0)                     # 400 × 20


def test_fallback_path_scales_with_leverage():
    # When the quote fails, the pure leverage model is unchanged and scales with
    # whatever intraday_leverage is currently set to (not hardcoded to 2.5).
    from app.db.session import init_db
    from app.engine.runner import EngineRunner
    from app.engine.equity_entry import equity_qty
    from app.core.instruments import all_instruments
    init_db(reset=True)
    r = EngineRunner()
    r.provider = _KiteStub(per_share=None)
    r.params["intraday_leverage"] = 4.0
    key = all_instruments()[0].key
    qty, margin = r._intraday_margin_sizer()(_c(key, 100.0), 8_000.0)
    assert qty == equity_qty(8_000.0, 4.0, 100.0)               # 320, not the 2.5x default


def test_leverage_cap_zero_qty_does_not_crash_entry_cycle():
    # A leverage cap smaller than one share (tiny intraday_leverage) must degrade to
    # qty=0 and be skipped by the selector — never raise/crash the entry cycle.
    from app.db.session import init_db
    from app.engine.runner import EngineRunner
    from app.core.instruments import all_instruments
    init_db(reset=True)
    r = EngineRunner()
    r.provider = _KiteStub(per_share=20.0)
    r.params["intraday_leverage"] = 0.01                        # cap collapses to <1 share
    key = all_instruments()[0].key
    sizer = r._intraday_margin_sizer()
    qty, margin = sizer(_c(key, 100.0), 8_000.0)
    assert qty == 0 and margin == 0.0

    res = select_intraday_entries([_c(key, 100.0)], max_positions=3, min_margin=5_000.0,
                                  max_margin=8_000.0, purple_margin=8_000.0, leverage=0.01,
                                  available_cash=1_000_000.0, sizer=sizer)
    assert not res.selected
    assert any("target margin buys <1 share" in reason for _, reason in res.skipped)


def test_leverage_cap_bind_logs_marker():
    # A log marker must fire when the leverage cap actually reduces qty below the
    # real-margin qty, naming both quantities so the owner can see the cap working.
    from app.db.session import init_db
    from app.engine.runner import EngineRunner
    from app.core.instruments import all_instruments
    from app.core.logging import log
    init_db(reset=True)
    r = EngineRunner()
    r.provider = _KiteStub(per_share=20.0)
    r.params["intraday_leverage"] = 2.5
    key = all_instruments()[0].key
    before = len(log.recent(1))
    r._intraday_margin_sizer()(_c(key, 100.0), 8_000.0)
    entries = log.recent(10)
    assert any("leverage cap" in e["msg"].lower() for e in entries), entries


# ── Task 2 follow-up (R2 review, 2026-07-16): the min_margin floor must measure
# economic position size, NOT the post-cap real margin — otherwise the leverage cap
# and the margin floor combine to zero out the whole intraday segment. Production
# repro: target_margin=8000, min_margin=5000, intraday_leverage=2.5, real broker
# leverage 5x → cap binds, real margin consumed shrinks to ~4000 (<5000) even though
# the position is a legitimate ~8000-deployment/~20000-notional trade. The floor must
# instead compare qty*price/leverage (the deployment the position represents under
# the configured leverage model) against min_margin. ─────────────────────────────

def test_cap_bound_entry_clears_floor_on_size_not_real_margin():
    # Real per-share margin implies 5x (₹20/share on a ₹100 share); intraday_leverage
    # caps qty to the 2.5x model. The consumed real margin (~4000) is BELOW the 5000
    # floor, but the position's economic size (qty*price/leverage ≈ 8000) is not — the
    # entry must NOT be skipped, and the recorded margin is the real, capped ~4000.
    def sizer(cand, target_margin):
        margin_qty = qty_for_margin(20.0, target_margin)          # 400 — real 5x margin
        lev_qty = equity_qty(target_margin, 2.5, cand.price)      # 200 — owner's cap
        qty = min(margin_qty, lev_qty)
        return qty, qty * 20.0

    res = select_intraday_entries(
        [_c("HEG", 100.0)], max_positions=3, min_margin=5_000.0, max_margin=8_000.0,
        purple_margin=8_000.0, leverage=2.5, available_cash=1_000_000.0, sizer=sizer)
    assert res.selected, res.skipped
    p = res.selected[0]
    assert p.qty == 200
    assert p.margin == pytest.approx(4_000.0)           # real margin actually blocked
    assert p.qty * p.price / 2.5 == pytest.approx(8_000.0)   # size_equiv clears the floor


def test_dust_candidate_still_skipped_by_floor():
    # A genuinely tiny target margin (e.g. a small leftover slot) — even after the
    # leverage-model-size calculation, this is real dust and must still be skipped.
    def sizer(cand, target_margin):
        margin_qty = qty_for_margin(20.0, target_margin)
        lev_qty = equity_qty(target_margin, 2.5, cand.price)
        qty = min(margin_qty, lev_qty)
        return qty, qty * 20.0

    res = select_intraday_entries(
        [_c("DUST", 100.0)], max_positions=3, min_margin=5_000.0, max_margin=2_000.0,
        purple_margin=2_000.0, leverage=2.5, available_cash=1_000_000.0, sizer=sizer)
    assert not res.selected
    assert any("floor" in reason.lower() for _, reason in res.skipped)


def test_real_margin_binding_regime_floor_unaffected():
    # Pre-cap behavior preserved: when the owner's leverage cap is generous enough
    # relative to the real broker leverage that the REAL margin quote is the binding
    # constraint (not the cap), a legitimately-sized, well-funded position still
    # clears the floor. (Real per-share margin implies 6x on a ₹120 share; the owner's
    # cap of 8x doesn't bind since it's above the real 6x, so qty comes from the real
    # margin quote — 400 shares, ₹8,000 real margin — exactly as before this fix.)
    def sizer(cand, target_margin):
        margin_qty = qty_for_margin(20.0, target_margin)          # 400, real 6x margin
        lev_qty = equity_qty(target_margin, 8.0, cand.price)      # generous 8x cap → 533
        qty = min(margin_qty, lev_qty)
        return qty, qty * 20.0

    res = select_intraday_entries(
        [_c("HEG", 120.0)], max_positions=3, min_margin=5_000.0, max_margin=8_000.0,
        purple_margin=8_000.0, leverage=8.0, available_cash=1_000_000.0, sizer=sizer)
    assert res.selected, res.skipped
    p = res.selected[0]
    assert p.qty == 400                                  # real-margin qty binds
    assert p.margin == pytest.approx(8_000.0)
