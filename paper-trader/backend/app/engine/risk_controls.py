"""
Pure, additive trader risk-control guards for the entry path.

These ONLY ever prevent or limit *new* entries — they never change strategy
direction, sizing of an accepted trade, or order mechanics — so they are safe to
layer on and trivially unit-testable. The engine consults them in
`process_entries`; open-position management is untouched.
"""
from __future__ import annotations

import datetime as dt


def slots_available(open_count: int, max_open_positions: int) -> int | None:
    """How many *new* positions may still be opened. None = unlimited (cap off).

    `max_open_positions <= 0` disables the cap (back-compat default)."""
    if not max_open_positions or max_open_positions <= 0:
        return None
    return max(0, max_open_positions - open_count)


def in_reentry_cooldown(last_stop_time: dt.datetime | None, now: dt.datetime,
                        cooldown_minutes: float) -> bool:
    """True if `now` is still within the post-stop-out cooldown for an instrument.

    Prevents the classic chop trap: stop out at −X%, the next candle re-crosses,
    re-enter, stop out again. `cooldown_minutes <= 0` disables it."""
    if not cooldown_minutes or cooldown_minutes <= 0 or last_stop_time is None:
        return False
    return (now - last_stop_time).total_seconds() < cooldown_minutes * 60.0


def over_per_trade_cap(cost: float, cap: float) -> bool:
    """True if a single trade's all-in cost exceeds the per-trade capital cap.

    `cap <= 0` disables it. Guards against one fat contract (e.g. a pricey index
    option) consuming a disproportionate slice of capital on a single signal."""
    return bool(cap and cap > 0 and cost > cap)


def expiry_too_close(expiry: dt.date | None, today: dt.date, min_days: int) -> bool:
    """True if an option is too close to expiry to OPEN (theta-cliff guard).

    Blocks an entry when days-to-expiry < `min_days`. With `min_days = 3` this
    refuses 0/1/2-DTE options (the owner's "no options with 2 DTE or less" rule) —
    where a small adverse move can vaporise the premium (a 0-DTE NIFTY put went
    ₹56 → ₹9 intraday). `min_days <= 0` disables the guard; a missing expiry never
    blocks here (handled upstream)."""
    if expiry is None or min_days <= 0:
        return False
    return (expiry - today).days < min_days


def signal_already_evaluated(bar: int | None, last_bar: int | None) -> bool:
    """True if this candle's entry signal was already evaluated for the instrument,
    so it must NOT be acted on again.

    A signal is a candle-level STATE, not a one-shot event — it stays set for the
    whole candle. Without this guard a signal that fired but couldn't enter (no
    capital, or the concurrency cap was full) is re-attempted every tick and FILLED
    the instant a slot frees up — at a stale price the original crossover never
    intended. Gate on the candle time so each crossover is evaluated once; a new
    entry then needs the NEXT fresh candle. `bar`/`last_bar` are candle epoch
    seconds; a missing `bar` never blocks (tests / warm-up)."""
    return bar is not None and last_bar is not None and bar <= last_bar


def signal_too_old(bar: int | None, now_epoch: float, interval_minutes: float,
                   max_age_minutes: float) -> bool:
    """True if an entry signal's candle is too old to act on — the crossover is
    HISTORY, not a live signal.

    `bar` is the candle-OPEN epoch (seconds); the candle completes at
    `bar + interval`, and a live engine acts within seconds of that. After a
    (re)start, though, the "latest completed candle" can be hours old — pre-open it
    is the PREVIOUS session's last bar — and entering on it chases a move that
    already left (LODHA 2026-07-03: a prior-session crossover fired at 09:00 and
    was ~5% past its origin by noon). Blocks when the signal is older than
    `max_age_minutes` past its candle's completion. `max_age_minutes <= 0` disables
    the guard; a missing `bar` never blocks (tests / warm-up), matching
    `signal_already_evaluated`."""
    if bar is None or not max_age_minutes or max_age_minutes <= 0:
        return False
    completed = bar + interval_minutes * 60.0
    return (now_epoch - completed) > max_age_minutes * 60.0


def before_entry_window(now: dt.datetime, start_hhmm: str) -> bool:
    """True if `now` is before the owner's start-of-day entry gate (e.g. "09:30").

    Stricter than the session gate: the cash session opens 09:15 but the first
    minutes are erratic (uncross drift, opening range), so NO new entry is taken
    before the window opens. Gates ENTRIES only. A blank/garbage `start_hhmm`
    disables the gate (the session guard still applies)."""
    try:
        h, m = (start_hhmm or "").strip().split(":")
        start = dt.time(int(h), int(m))
    except (ValueError, AttributeError):
        return False
    return now.time() < start


def gap_halt_active(now: dt.datetime, index_open: float | None,
                    prev_close: float | None, *, gap_pct: float,
                    resume_hhmm: str) -> bool:
    """True if NEW entries should be blocked because the index gapped ≥ `gap_pct`
    percent at the open and it's still before `resume_hhmm` (IST wall-clock).

    Gates ENTRIES only — a big overnight gap makes the first hour's price action
    erratic/unreliable, so the owner sits out until (default) 11:00. Fails OPEN: a
    disabled guard (gap_pct ≤ 0), a bad resume time, or a missing index read never
    blocks — a data hiccup must not halt the whole book."""
    if not gap_pct or gap_pct <= 0:
        return False
    if index_open is None or not prev_close or prev_close <= 0:
        return False
    gap = abs(index_open - prev_close) / prev_close * 100.0
    if gap < gap_pct:
        return False
    try:
        h, m = (resume_hhmm or "").strip().split(":")
        resume = dt.time(int(h), int(m))
    except (ValueError, AttributeError):
        return False
    return now.time() < resume


def intraday_blocked_for_expiry_day(today: dt.date, override_iso: str | None,
                                    block_weekday: int = 1,
                                    key: str | None = None,
                                    block_keys: str = "*") -> bool:
    """True if a NEW entry in `key` is blocked today (the owner's "no trades on Tuesday").

    By default this sits out **Tuesdays** — NIFTY-50 weekly expiry day, whose erratic
    moves the owner wants to avoid. Originally intraday(MIS)-only; since 2026-07-04 it
    gates ALL entries (options too) — the keys keep the `intraday_` prefix for
    runtime-override back-compat. The block is lifted ONLY when the owner opted in
    for this exact date: `override_iso` is a 'YYYY-MM-DD' string that lifts the block
    when it equals `today` — a per-day, self-expiring switch (last Tuesday's opt-in
    never carries forward). `block_weekday`: Mon=0 … Sun=6 (1 = Tuesday);
    `block_weekday < 0` disables the guard.

    `block_keys` scopes WHICH instruments sit out on that weekday (owner, 2026-07-28 —
    a NIFTY expiry says nothing about SUZLON, so the equity-intraday book kept trading
    for no reason). "*" blocks the whole book (the pre-2026-07-28 behaviour); otherwise
    it is a comma-separated list of instrument keys and only those sit out. A blank
    list fails SAFE (treated as "*") so clearing the field can never silently remove a
    safety guard, and an unresolved `key` is blocked for the same reason."""
    if block_weekday < 0 or today.weekday() != block_weekday:
        return False
    try:
        override = dt.date.fromisoformat((override_iso or "").strip())
    except ValueError:
        override = None
    if override == today:               # the owner opted in for this exact date
        return False
    scope = (block_keys or "").strip()
    if scope in ("", "*"):              # whole book (blank = fail safe)
        return True
    if key is None:                     # unresolved key — never sneak past the guard
        return True
    wanted = {k.strip().upper() for k in scope.split(",") if k.strip()}
    return key.strip().upper() in wanted


def outside_trading_session(segment: str, now: dt.datetime) -> bool:
    """True if `now` is OUTSIDE `segment`'s continuous trading session — the pre-open
    auction (before 09:15) or after the close.

    A NEW entry must never be placed then. Orders the bot sends are protected-market
    (a marketable LIMIT at LTP ± the protection band); placed in the pre-open window it
    simply rests until the 09:15 uncross and, if the open prints beyond the band, never
    fills — the LODHA 09:01:25 order that dangled and missed the move (2026-07-03 live
    incident). Intraday charge-segments ('NSE_INTRADAY'/'BSE_INTRADAY') resolve to the
    09:15-15:30 cash-session window. Gates ENTRIES only; open positions are still
    marked, stopped and exited regardless — like the other guards here."""
    from app.core import market_hours
    return not market_hours.is_open(segment, now)


def daily_loss_halt(realized_today: float, unrealized_open: float,
                    max_daily_loss: float, max_open_drawdown: float) -> tuple[bool, str]:
    """Decide whether to HALT new entries for the day. Two independent circuit
    breakers — either one trips the halt; both are off by default (cap <= 0):

      • max_daily_loss    — today's REALIZED net loss (closed trades only). The
        original breaker; blind to a position bleeding while still open.
      • max_open_drawdown — today's REALIZED + UNREALIZED (open mark-to-market)
        loss, so a deep *open* drawdown halts new entries even before anything is
        booked. This is the realized+unrealized halt the owner asked for.

    Returns (halted, reason) with reason in {"", "realized", "open_drawdown"};
    the realized breaker wins the reason when both would trip. Open positions are
    ALWAYS still managed (SL/TP/trailing) — this only blocks opening new ones, and
    the open-drawdown breaker un-trips if the open MTM recovers."""
    if max_daily_loss and max_daily_loss > 0 and realized_today <= -max_daily_loss:
        return True, "realized"
    if (max_open_drawdown and max_open_drawdown > 0
            and (realized_today + unrealized_open) <= -max_open_drawdown):
        return True, "open_drawdown"
    return False, ""


def round_trip_cap_reached(round_trips_today: int, cap: int) -> bool:
    """True if today's completed round-trip count has hit the daily cap — a HARD halt
    on NEW entries (the functional counterpart to the advisory overtrade flag). Open
    positions are still managed throughout. `cap <= 0` disables it."""
    return bool(cap and cap > 0 and round_trips_today >= cap)


def daily_profit_lock(day_pnl: float, high_water: float, deployed_capital: float,
                      lock_pct: float, giveback_frac: float) -> tuple[bool, float | None]:
    """Give-back circuit breaker — the symmetric twin of `daily_loss_halt`, but on
    the UPSIDE: once the day's P&L clears a profit threshold, ARM a floor under it
    and if the day retraces back down to that floor, the caller must SQUARE OFF ALL
    open positions and HALT new entries for the rest of the session (protects a good
    day from round-tripping to flat or red).

      • lock_pct        — arm threshold as a FRACTION of `deployed_capital` (e.g.
        0.02 = 2%). Armed once `high_water >= lock_pct * deployed_capital`.
        `lock_pct <= 0` disables the guard entirely.
      • giveback_frac    — once armed, the floor is `giveback_frac * high_water`
        (e.g. 0.5 = give back at most half the peak gain).
      • high_water       — the running intraday PEAK of `day_pnl`; the caller
        maintains this, trailing it up tick by tick — it never loosens.
      • deployed_capital — the day's deployed capital (the denominator for
        `lock_pct`), typically the day's peak concurrent open exposure.
        `deployed_capital <= 0` disables the guard (no capital, no ratio).

    Returns (breached, floor). Not yet armed (high_water below threshold, or the
    guard is off) -> (False, None). Once armed, breached = day_pnl <= floor.
    Pure — no state, no I/O; the caller owns high_water/armed persistence."""
    if lock_pct <= 0 or deployed_capital <= 0 or high_water <= 0:
        return False, None
    armed = high_water >= lock_pct * deployed_capital
    if not armed:
        return False, None
    floor = giveback_frac * high_water
    return day_pnl <= floor, floor


def account_halt_reason(realized: float, unrealized: float, round_trips: int,
                        profit_lock_halted: bool, limits: dict) -> str:
    """Account entry-only caps, followed by the existing profit-giveback latch."""
    halted, reason = daily_loss_halt(realized, unrealized, limits["max_daily_loss"],
                                     limits["max_open_drawdown"])
    if halted:
        return reason
    if round_trip_cap_reached(round_trips, limits["max_round_trips_per_day"]):
        return "round_trips"
    if limits["max_daily_profit"] > 0 and realized >= limits["max_daily_profit"]:
        return "realized_profit"
    return "profit_lock" if profit_lock_halted else ""
