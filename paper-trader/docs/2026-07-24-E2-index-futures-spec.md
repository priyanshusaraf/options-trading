# E2 spec — index-futures segment

Status: DRAFT for owner + Fable review. No code written against this spec.
Scope: `backend/`. Roadmap source: `docs/ROADMAP.md:280-303` (Phase E2).

## Scope & non-goals

**In scope:** a new `index_futures` segment for **cash-settled index futures**
(NIFTY, BANKNIFTY, SENSEX on NFO/BFO) — intraday-only entry/mark/exit,
force-flat before close, no rollover ever, direction-aware SL/TP with
lockstep reuse, NFO_FUT/BFO_FUT charges, paper margin estimate vs live
real-margin path.

**Out of scope:** stock futures (index ranks first per CLAUDE.md's
index-first direction; same segment machinery, later); MCX/NCDEX commodity
futures (deliverable — the guard is a no-op here, a real consumer later);
any multi-day/carry position (Phase E3 MTF, `docs/ROADMAP.md:305-311`);
overnight holding of any kind; any change to the options or equity_intraday
paths (isolation is the first constraint, below).

## Segment isolation design

Precedent: `equity_intraday`, already fully isolated from options. E2 adds
a **third** `Position.segment` value, `"index_futures"`
(`backend/app/db/models.py:65`, plain `String` column, no enum — additive by
construction; also on `Trade.segment`, `models.py:180`). New sibling
functions parallel the equity ones; only two shared functions need their
segment-check widened:

- `Position.unrealized_pnl()` (`models.py:118-124`) — currently `if
  self.segment == "equity_intraday" and self.direction == "SHORT"`. A short
  futures position is a real short (unlike long-only options) → widen to
  `self.segment in ("equity_intraday", "index_futures")`.
- `Position.mtm_value()` (`models.py:126-134`) — equity_intraday returns
  `entry_cost + unrealized_pnl()` (margin left cash, not full notional);
  futures margining works the same way (SPAN+exposure leaves cash) → same
  widening.

Everything else is a new sibling, keyed off `segment == "index_futures"`,
that never touches the options/equity branches:

- **Entry**: `PaperBroker.open_equity_position` (`backend/app/engine/
  broker.py:94-148`) is the template for `open_futures_position` — same
  shape, `segment="index_futures"`, `option_type="FUT"`, charges via
  `compute_charges("NFO_FUT"/"BFO_FUT", "BUY", price, qty)`. Reuses
  `equity_stop_target` (`equity_entry.py`) unchanged for direction-aware
  stop/target.
- **Exit**: `PaperBroker.close_equity_position` (`broker.py:150-194`) is the
  template for `close_futures_position` — same margin-release/net-P&L math.
- **`LiveBroker` overrides**: `broker.py:420` (`open_equity_position`) and
  `:472` (`close_equity_position`) override the paper versions
  (`LiveBroker(PaperBroker)`, `broker.py:35`). Matching futures overrides
  are **not built in E2 v1** — recommend paper-only first (see Open Items #5).
- **Mark + exit dispatch**: `mark_and_exit_positions` (`runner.py:466-539`)
  branches on `pos.segment == "equity_intraday"` at `runner.py:491-493` to
  `_mark_exit_equity`. E2 adds `elif pos.segment == "index_futures":
  self._mark_exit_futures(...)`. **Mark-price wrinkle:** equity_intraday
  marks to underlying SPOT (`runner.py:609`) because the position *is* the
  spot instrument; a futures contract trades at a basis to spot
  (cost-of-carry) so marking to spot would silently misprice P&L. This
  requires a **new provider surface** (futures LTP fetch) — `live_snapshot`
  today returns only spot + option premium. Real new work, not a config
  knob (Open Items #4).
- **Lockstep reuse**: `_apply_lockstep` (`runner.py:565-602`) and
  `lockstep_band`/`equity_stop_target`/`equity_exit`
  (`equity_entry.py:48-167`) are pure and segment-agnostic already (plain
  floats in, no segment string) — `_mark_exit_futures` calls the same
  `_apply_lockstep` unmodified; only new config-knob fallbacks are needed.
- **Selection/sizing**: `select_intraday_entries` (`equity_entry.py:210-286`)
  is also segment-agnostic — reused via a second call in `process_entries`
  (mirroring the existing block at `runner.py:985-1009`), against futures
  candidates, `index_futures_*` knobs, and `self._futures_margin_sizer()`.
- **Force-flat**: reuses `square_off_intraday` (`runner.py:1108-1124`)
  verbatim by widening its segment filter — see below.

Net: options and equity_intraday are touched in exactly two lines
(`unrealized_pnl`/`mtm_value` segment-set widening); everything
futures-specific is new sibling code.

## Margin model

**LIVE: real number, no estimate.** `KiteProvider.order_margin(orders)`
(`backend/app/providers/kite.py:159-169`) calls `self.kite.order_margins
(orders)` and sums `total` — the same mechanism `_intraday_margin_sizer`
(`runner.py:641-690`) already uses for real MIS margin. A
`_futures_margin_sizer()` is the direct sibling (same per-(tradingsymbol,
side) caching, same `order_margin([...])` shape, futures tradingsymbol
instead of equity spot). When live and authenticated, sizing uses this real
SPAN+exposure number — no estimate needed once wired.

**PAPER/backtest: an estimate is required** (no Kite margin API available
offline). Proposed, ⚠️ **FLAGGED, unverified**:

> `paper_margin_estimate = notional × index_futures_margin_pct_estimate`,
> `notional = futures_price × lot_size × lots`,
> `index_futures_margin_pct_estimate` defaults to **0.12 (12%)**.

Rationale: published NRML SPAN+exposure margin for NIFTY/BANKNIFTY/SENSEX
futures has historically run ~10–15% of notional. 12% is a reasoned
single-point estimate, **not verified against a real margin call** — must be
checked against Zerodha's live margin calculator or a real `order_margins()`
response before it's trusted for sizing with real stakes.

**Worked example — 1 NIFTY lot** (lot_size 75, `backend/app/core/
instruments.py:51`), futures price ≈ spot ≈ ₹24,000:

| Quantity | Value |
|---|---|
| Lot size | 75 |
| Futures price | ₹24,000 |
| Notional (price × lot_size) | ₹18,00,000 |
| Paper margin estimate (12%) | ₹2,16,000 |
| Live margin | not estimated — read from Kite at order time |

₹2.16L/lot is the right order of magnitude for NIFTY futures margin
historically — sanity-check against a real contract note before trusting it.

## Charge legs (NFO_FUT)

`CHARGE_SCHEDULE["NFO_FUT"]` (`backend/app/engine/charges.py:57-60`) already
exists and needs no code change — `compute_charges` dispatches on the
`segment` string (`charges.py:84-89`):

```
"NFO_FUT": {"brokerage_pct": 0.0003, "brokerage_cap": 20.0, "txn_pct": 0.0000173,
            "tax_sell_pct": 0.0002, "stamp_buy_pct": 0.00002, "sebi_pct": 1e-6,
            "gst_pct": 0.18}
```

| Leg | Rate | vs public Zerodha F&O schedule |
|---|---|---|
| Brokerage (both legs) | min(₹20, 0.03%) | Matches flat/pct-cap F&O brokerage — CONFIRMED shape |
| STT (sell leg only) | 0.02% | Matches post-Oct-2024 futures STT hike (was 0.0125%), per file comment `charges.py:24-25` — CONFIRMED |
| Exchange txn (both legs) | 0.00173% | Matches published NSE F&O rate — ⚠️ NSE revises periodically, reverify |
| SEBI fee (both legs) | ₹10/crore | Flat across segments — CONFIRMED |
| Stamp duty (buy leg) | 0.002% | Government-fixed, not exchange-fixed — CONFIRMED |
| GST | 18% of (brokerage+txn+sebi) | Standard rate — CONFIRMED |
| DP charge | n/a | Correctly absent (no demat debit) — CONFIRMED by omission |

**Gap:** only `NFO_FUT`/`MCX_FUT`/`NCDEX_FUT` exist today — **no `BFO_FUT`**
for SENSEX futures. Must be authored from scratch during the build (Open
Items #2), not copied from `BFO` options.

**Worked round trip — 1 NIFTY lot, entry ₹24,000 → exit ₹24,000, qty 75**,
via `compute_charges("NFO_FUT", ...)` exactly as coded:

| | Buy leg | Sell leg |
|---|---|---|
| Turnover | ₹18,00,000 | ₹18,00,000 |
| Brokerage | ₹20.00 (0.03% would be ₹540, capped) | ₹20.00 |
| STT | ₹0 | ₹360.00 |
| Exchange txn | ₹31.14 | ₹31.14 |
| SEBI | ₹1.80 | ₹1.80 |
| Stamp | ₹36.00 | ₹0 |
| GST | ₹9.53 | ₹9.53 |
| **Leg total** | **₹98.47** | **₹422.47** |

**Round trip ≈ ₹520.94** (≈0.029% of ₹18L notional) via
`round_trip_charges("NFO_FUT", 24000, 24000, 75)` (`charges.py:126-131`),
unchanged function.

## Direction-aware SL/TP + lockstep reuse

No new geometry code — all pure and direction-generic, reused verbatim:
`equity_stop_target` (`equity_entry.py:48-54`, stop-above/target-below for a
SHORT), `equity_exit` (`equity_entry.py:89-113`), `lockstep_band` via
`_apply_lockstep` (`runner.py:565-602`, `equity_entry.py:116-167`) with new
`index_futures_lockstep_*` knobs read in place of `intraday_lockstep_*`,
and `resolve_sltp` (`equity_entry.py:57-86`) for owner cockpit edits.

## Force-flat / no-rollover / delivery-window guard

**Force-flat:** `square_off_intraday` (`runner.py:1108-1124`) filters `if
pos.segment != "equity_intraday": continue` — widen to `not in
("equity_intraday", "index_futures")`. Own buffer knob
(`index_futures_square_off_buffer_minutes`, default 15) since futures
close-auction dynamics may differ from cash equity.

**No rollover — hard invariant, not a knob.** No roll/rollover code exists
anywhere in `engine/` today; the risk is *adding* one by mistake. The only
lifecycle exits for a futures position are (a) SL/TP/lockstep, (b)
force-flat, (c) manual close — never a roll to the next series, even on
expiry day. Acceptance test: force-flat fires on the expiry-day session too
(no "it's expiry day, let it expire" carve-out).

**Delivery-window guard.** Index futures are cash-settled — no physical
delivery — so the guard is a documented no-op for E2's instruments. It
exists so a later commodity extension (MCX gold/silver staggered-delivery)
can't trade through delivery risk (`docs/ROADMAP.md:290-296`).

```python
# app/engine/delivery_calendar.py (new, pure)

@dataclass(frozen=True)
class DeliveryWindow:
    starts: date   # first delivery/tender-locked date
    ends: date     # expiry / settlement date

class DeliveryCalendar(Protocol):
    def window_for(self, instrument_key: str, expiry: date) -> DeliveryWindow | None:
        """None => cash-settled / no delivery risk. A real MCX/NCDEX
        calendar would return the staggered-delivery start here."""

class CashSettledCalendar:
    """E2's calendar: always None. Correct AND permanent for index futures
    (all NFO/BFO index contracts are cash-settled) — but a deliberately
    inert stub for the future commodity extension point."""
    def window_for(self, instrument_key, expiry):
        return None

def no_delivery_window(instrument_key: str, today: date, expiry: date,
                       calendar: DeliveryCalendar) -> bool:
    """True => safe to hold/open today. False => refuse new entries and
    force-close any open position immediately (higher priority than the
    normal end-of-day force-flat)."""
    w = calendar.window_for(instrument_key, expiry)
    return True if w is None else not (w.starts <= today <= w.ends)
```

`process_entries`'s futures block calls this before adding a candidate;
`mark_and_exit_positions`'s futures branch checks it too and force-closes on
`False` (unreachable for E2's cash-settled instruments — tested with an
adversarial fake calendar that DOES return a window, to prove the block
fires). E2 ships `CashSettledCalendar` only; a real MCX calendar is future
work (Non-goals, Open Items #7).

## Config knobs

New knobs under `Settings` (`backend/app/core/config.py`), mirroring
`intraday_*` (`config.py:184-221`) 1:1 by name, **all default OFF/inert**:

| Knob | Mirrors | Default |
|---|---|---|
| `index_futures_enabled` | `intraday_enabled` | `False` |
| `index_futures_max_positions` | `intraday_max_positions` | `2` (starting guess, owner to confirm) |
| `index_futures_min_margin` | `intraday_min_margin` | `50_000.0` |
| `index_futures_max_margin` | `intraday_max_margin` | `200_000.0` (≈1 NIFTY lot at 12%) |
| `index_futures_purple_margin` | `intraday_purple_margin` | `250_000.0` |
| `index_futures_margin_pct_estimate` | *(new — futures is SPAN-based, not leverage-based)* | `0.12` ⚠️ unverified |
| `index_futures_square_off_buffer_minutes` | `intraday_square_off_buffer_minutes` | `15.0` |
| `index_futures_entry_cutoff_minutes` | `intraday_entry_cutoff_minutes` | `25.0` |
| `index_futures_stop_loss_pct` | `intraday_stop_loss_pct` | `0.008` |
| `index_futures_target_pct` | `intraday_target_pct` | `0.03` |
| `index_futures_lockstep_enabled` | `intraday_lockstep_enabled` | `True` |
| `index_futures_lockstep_trigger_pct` | `intraday_lockstep_trigger_pct` | `0.03` |
| `index_futures_profit_lock_threshold` | `intraday_profit_lock_threshold` | `600.0` |
| `index_futures_profit_lock_frac` | `intraday_profit_lock_frac` | `0.3` |
| `index_futures_live_enabled` | *(new — gates real orders separately; no LiveBroker override exists yet)* | `False`, stays off until built + reviewed |

All wired through `runtime_config.effective()` and read via
`self.params.get(...)` exactly like `intraday_*`.

## Acceptance mapping

| ROADMAP bullet | Test | Verifiable now / needs contract note? |
|---|---|---|
| New segment, isolated entry/mark/exit | `test_futures_entry.py`: options/equity_intraday unchanged before/after opening a futures pos | Verifiable NOW — pure isolation |
| Lot sizes + SPAN+exposure sizing | `test_futures_margin.py`: paper sizer = `notional×0.12`; live sizer uses mocked `order_margin` | Mechanism verifiable now; **12% number NOT verifiable** without a real contract note/live call |
| NFO_FUT charge legs | `test_charges.py` per-leg assertions vs the table above | Formula verifiable now; rates need periodic reverification |
| MTM on futures LTP | `test_futures_mark.py`: fake futures LTP distinct from spot, assert P&L tracks it | Verifiable with a mock quote; needs new provider surface first |
| Direction-aware SL/TP + lockstep | `test_futures_sltp.py`, reusing `test_lockstep_band.py` fixtures | Verifiable now — pure functions |
| Spec gate first | This document | This step |
| Intraday-only, no rollover | `test_futures_no_rollover.py`: force-flat fires on expiry-day session; static grep for roll logic | Verifiable now |
| Delivery-window guard | `test_delivery_guard.py` with `CashSettledCalendar` + an adversarial fake calendar | Verifiable now with a stub — E2 has no deliverable instrument to test against for real |
| Accurate P&L, net of full charge stack | Headless run + `PaperBroker.reconcile()` (`broker.py:458-465`) paisa-exact | Ledger-invariant mechanism verifiable now; matching a REAL trade needs a contract note |
| SPAN+exposure margin "verify against a real contract note" | — | **CANNOT be verified in this repo** without external data — biggest open item |
| Deliverable contract refused/force-closed (stubbed calendar) | Same delivery-guard test | Verifiable now — roadmap itself specifies a stub suffices |

## ⚠️ OPEN ITEMS / RATES TO VERIFY AGAINST A REAL CONTRACT NOTE

1. **Paper margin estimate (12% of notional) is UNVERIFIED** — a reasoned
   estimate from general knowledge of NIFTY/BANKNIFTY/SENSEX NRML
   SPAN+exposure ranges (~10-15%), not from a live Zerodha margin call or
   real contract note. Must be cross-checked (Zerodha margin calculator, or
   a live `order_margins()` call) before it drives any real sizing decision.
2. **No `BFO_FUT` charge schedule exists** — SENSEX futures have no rate
   entry in `charges.py` today (only `NFO_FUT`/`MCX_FUT`/`NCDEX_FUT`). Must
   be authored from scratch, not copied from `BFO` options.
3. **`NFO_FUT`'s bps figures (esp. the 0.00173% exchange txn charge) can be
   revised by NSE/SEBI without a code change surfacing it** — standing
   reverification to-do, same caveat as the existing options schedule
   header (`charges.py:23-25`).
4. **Futures LTP is not fetchable from the provider layer today.**
   `live_snapshot` returns spot + option premium only; marking a futures
   position to spot (equity_intraday's pattern) would silently misprice P&L
   by the futures basis. A new provider method (mock + Kite) must be built
   as part of this segment — the largest real deviation from "just mirror
   equity_intraday."
5. **`LiveBroker` futures overrides are NOT built in E2 v1.** Recommend
   shipping paper-only first: `index_futures_enabled` gates paper entries;
   a separate `index_futures_live_enabled` (default `False`) gates real
   orders and stays off until the overrides exist and are reviewed — avoids
   repeating the "live path only ever exercised against a mock order
   client" gap the options/equity live paths already carry.
6. **`index_futures_max_positions`/margin-tier defaults (₹50k/₹200k/₹250k)
   are starting guesses** scaled off the unverified 12% — not owner-approved.
7. **No commodity delivery calendar is built** — `CashSettledCalendar` is
   permanently correct for index futures but an inert stub for the eventual
   MCX/NCDEX extension; whoever wires commodities onto this segment MUST
   replace it with a real calendar first, or the guard silently no-ops for
   a deliverable contract.

## Build plan (ordered TDD steps)

1. `delivery_calendar.py` + `no_delivery_window` — pure, test-first,
   including the adversarial fake-calendar case.
2. `BFO_FUT` charge schedule entry + `test_charges.py` extension
   (`NFO_FUT` per-leg assertions + new `BFO_FUT`).
3. Provider futures-LTP fetch — mock first (fake basis over spot), then
   `KiteProvider`, behind the existing `MarketDataProvider` interface.
4. `index_futures_*` config knobs in `Settings` + `runtime_config`; test
   every knob defaults inert.
5. `PaperBroker.open_futures_position`/`close_futures_position` — TDD
   modeled on `test_equity_broker.py`.
6. `Position.unrealized_pnl()`/`mtm_value()` segment-set widening +
   regression test proving options/equity_intraday unchanged.
7. `EngineRunner._mark_exit_futures` + dispatch branch, reusing
   `_apply_lockstep` unchanged.
8. `EngineRunner._futures_margin_sizer` (paper estimate + live
   `order_margin` branches), mocking `order_margin` in tests.
9. `process_entries` futures block: candidates + `no_delivery_window` gate
   + `select_intraday_entries` call, mirroring `runner.py:985-1009`.
10. `square_off_intraday` widening + expiry-day-session force-flat test.
11. Ledger-invariant proof: headless open→mark→close, `reconcile()`
    paisa-exact.
12. Full suite green + `dryrun.py 700` paisa-exact both with
    `index_futures_enabled=False` (no-op) and flipped on in a test scenario.
13. Owner + Fable review before `index_futures_enabled` ever flips true
    outside tests, and before `index_futures_live_enabled` is discussed.
