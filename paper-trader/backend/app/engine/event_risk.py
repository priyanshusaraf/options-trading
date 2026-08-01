"""Event-risk blackouts — the one place that answers "is there a scheduled event that
makes this instrument too dangerous to enter right now?".

Owner's rule (2026-08-01): whenever an instrument has known event-specific risk, the bot
does not take a new position in it. A systematic edge measured across ordinary sessions
does not survive a scheduled release; the distribution on those bars is a different
distribution, and sitting out is free.

Design notes that matter:

**One table, every consumer.** The live engine, the backtester and the cockpit all read
these same rules. A blackout the backtest ignores would make every backtest optimistic
about exactly the bars that hurt most, and a blackout the UI can't see is a bot that looks
broken ("why didn't it take the signal?"). `blackouts_for_day` exists for that second
reason.

**US releases move with American daylight saving.** The EIA gas (Thu) and petroleum (Wed)
reports are 10:30 US/Eastern. That is 20:00 IST in US summer and 21:00 IST in US winter.
Hardcoding the owner's stated 19:30–20:01 IST window would leave the bot trading straight
through the release for roughly four months a year, which is the opposite of the intent.
The window is therefore always derived from the Eastern clock via zoneinfo.

**Entries only.** Nothing here may ever gate an exit (hard invariant #2). A blackout that
trapped a position inside a release would invert its own purpose.

**Fail loud, not silent.** Every block carries a human-readable label that is logged and
shown in the UI, so "the bot didn't trade" is always explainable.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

_ET = ZoneInfo("America/New_York")
_IST = ZoneInfo("Asia/Kolkata")

MON, TUE, WED, THU, FRI = 0, 1, 2, 3, 4


@dataclass(frozen=True)
class EventRule:
    """One scheduled-risk rule. `keys` are instrument keys (case-insensitive, any
    `EXCHANGE:` prefix is stripped before matching); an empty `keys` means the rule
    applies to every instrument (used by the earnings rule, which is per-symbol data
    rather than a fixed list)."""
    kind: str                          # us_report | weekday | pre_expiry | earnings
    label: str                         # shown in logs and the cockpit
    keys: tuple[str, ...] = ()
    products: tuple[str, ...] = ("options", "equity_intraday", "futures")
    weekday: int | None = None         # Mon=0 … Sun=6
    et_time: str | None = None         # "HH:MM" US/Eastern for us_report rules
    before_minutes: int = 30
    after_minutes: int = 1
    days_before_expiry: int | None = None
    flatten_before: bool = False       # square off an open position before the window opens


@dataclass(frozen=True)
class Blackout:
    """An active or scheduled blackout. `window` is None for whole-day rules."""
    rule: EventRule
    label: str
    window: tuple[dt.datetime, dt.datetime] | None = None
    detail: str = ""

    @property
    def kind(self) -> str:
        return self.rule.kind

    def as_dict(self) -> dict:
        return {
            "kind": self.rule.kind, "label": self.label, "detail": self.detail,
            "from": self.window[0].isoformat() if self.window else None,
            "to": self.window[1].isoformat() if self.window else None,
            "all_day": self.window is None,
            "flatten_before": self.rule.flatten_before,
        }


# The owner's stated rules. Times for the two US reports are Eastern, converted per-date.
DEFAULT_RULES: tuple[EventRule, ...] = (
    EventRule(
        kind="us_report",
        label="EIA natural-gas storage report",
        keys=("NATURALGAS", "NATGAS"),
        weekday=THU, et_time="10:30", before_minutes=30, after_minutes=1,
        flatten_before=True,
    ),
    EventRule(
        kind="us_report",
        label="EIA weekly petroleum status report (crude inventories)",
        keys=("CRUDEOIL", "CRUDEOILM"),
        weekday=WED, et_time="10:30", before_minutes=30, after_minutes=1,
        flatten_before=True,
    ),
    EventRule(
        kind="weekday",
        label="NIFTY weekly-expiry Tuesday",
        keys=("NIFTY",),
        products=("options",),
        weekday=TUE,
    ),
    EventRule(
        kind="weekday",
        label="SENSEX expiry-day Thursday",
        keys=("SENSEX",),
        weekday=THU,
    ),
    EventRule(
        kind="weekday",
        label="BANKNIFTY expiry-day Wednesday",
        keys=("BANKNIFTY",),
        weekday=WED,
    ),
    EventRule(
        kind="pre_expiry",
        label="bullion options into expiry",
        keys=("GOLDM", "SILVERM"),
        products=("options",),
        days_before_expiry=2,
    ),
    EventRule(
        kind="earnings",
        label="company earnings / results day",
        keys=(),                       # any symbol — driven by the earnings calendar
    ),
)


def normalize_key(key: str | None) -> str:
    """'NSE:INFY' → 'INFY', 'naturalgas' → 'NATURALGAS'. Keys arrive prefixed or bare
    depending on the code path; a rule that silently stops matching on a prefix would be
    a safety hole that looks like a working guard."""
    k = (key or "").strip().upper()
    return k.split(":")[-1]


def event_window_ist(day: dt.date, et_time: str, before_minutes: int,
                     after_minutes: int) -> tuple[dt.datetime, dt.datetime]:
    """The IST blackout window for a US release at `et_time` Eastern on `day`.

    Returns NAIVE IST datetimes because the whole engine runs on naive IST clocks.
    Because the conversion goes through the Eastern zone for that specific date, the
    window automatically lands at 20:00 IST under EDT and 21:00 IST under EST."""
    hh, mm = (int(x) for x in et_time.split(":"))
    et_dt = dt.datetime(day.year, day.month, day.day, hh, mm, tzinfo=_ET)
    ist_dt = et_dt.astimezone(_IST).replace(tzinfo=None)
    return (ist_dt - dt.timedelta(minutes=before_minutes),
            ist_dt + dt.timedelta(minutes=after_minutes))


def _rule_applies_to(rule: EventRule, key: str, product: str) -> bool:
    if product not in rule.products:
        return False
    if not rule.keys:                  # keyless rules (earnings) match any instrument
        return True
    return normalize_key(key) in {normalize_key(k) for k in rule.keys}


def blackouts_for_day(key: str, product: str, day: dt.date, *,
                      expiry: dt.date | None = None,
                      earnings_date: dt.date | None = None,
                      rules: tuple[EventRule, ...] = DEFAULT_RULES,
                      enabled: bool = True) -> list[Blackout]:
    """Every blackout that applies to `key`/`product` on `day` — whether or not it is
    active at this instant. This is what the cockpit renders so the owner can see the
    day's sit-outs BEFORE the bot silently skips a signal."""
    if not enabled:
        return []
    out: list[Blackout] = []
    for rule in rules:
        if not _rule_applies_to(rule, key, product):
            continue
        if rule.kind == "us_report":
            if day.weekday() != rule.weekday:
                continue
            win = event_window_ist(day, rule.et_time or "10:30",
                                   rule.before_minutes, rule.after_minutes)
            out.append(Blackout(rule, rule.label, win,
                                detail=f"{win[0]:%H:%M}–{win[1]:%H:%M} IST "
                                       f"(10:30 US/Eastern, shifts with US DST)"))
        elif rule.kind == "weekday":
            if day.weekday() != rule.weekday:
                continue
            out.append(Blackout(rule, rule.label, None,
                                detail=f"all of {day:%A}"))
        elif rule.kind == "pre_expiry":
            if expiry is None or rule.days_before_expiry is None:
                continue
            days = (expiry - day).days
            if 0 <= days <= rule.days_before_expiry:
                out.append(Blackout(rule, rule.label, None,
                                    detail=f"expiry {expiry:%d %b} is {days} day(s) away"))
        elif rule.kind == "earnings":
            if earnings_date is None or earnings_date != day:
                continue
            out.append(Blackout(rule, rule.label, None,
                                detail=f"results announced {earnings_date:%d %b}"))
    return out


def active_blackout(key: str, product: str, now: dt.datetime, *,
                    expiry: dt.date | None = None,
                    earnings_date: dt.date | None = None,
                    rules: tuple[EventRule, ...] = DEFAULT_RULES,
                    enabled: bool = True) -> Blackout | None:
    """The blackout blocking a NEW entry in `key` right now, or None.

    NEVER call this on an exit path. Whole-day rules block the entire session; windowed
    rules block only inside the window, so the instrument trades normally either side of
    the release."""
    for b in blackouts_for_day(key, product, now.date(), expiry=expiry,
                               earnings_date=earnings_date, rules=rules, enabled=enabled):
        if b.window is None:
            return b
        if b.window[0] <= now <= b.window[1]:
            return b
    return None


def pending_flatten(key: str, product: str, now: dt.datetime, *,
                    lead_minutes: float = 2.0,
                    rules: tuple[EventRule, ...] = DEFAULT_RULES,
                    enabled: bool = True) -> Blackout | None:
    """A windowed blackout whose window opens within `lead_minutes` and that is marked
    `flatten_before` — i.e. an open position in this instrument should be squared off
    BEFORE the release rather than carried through it.

    Holding into the print is the actual risk the owner is avoiding; blocking entries
    alone would leave a position that was opened an hour earlier exposed to the whole
    move. This is an exit, so it is never itself gated by a blackout."""
    if not enabled:
        return None
    for b in blackouts_for_day(key, product, now.date(), rules=rules, enabled=enabled):
        if b.window is None or not b.rule.flatten_before:
            continue
        opens = b.window[0]
        if opens - dt.timedelta(minutes=lead_minutes) <= now <= b.window[1]:
            return b
    return None
