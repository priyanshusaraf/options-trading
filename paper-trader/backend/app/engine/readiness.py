"""Readiness verdict for /api/health — the part that is allowed to say NO.

`/api/health` was a liveness stub: `{"ok": True}` plus a build stamp. It returned
200 throughout BOTH 2026-07 outages (the `.env` clobber that 404'd every `GET /`,
and the memory-leak/DB-pool collapse), which is why `scripts/deploy.sh` has to
curl `GET /` separately to notice a broken deploy. A probe that cannot fail
tells you nothing.

This module is pure — no DB, no network, no clock of its own — for the same
reason `engine/health.py` is: the caller measures, this decides, and every state
below is a unit test rather than an integration setup.

Two rules shape everything here:

**Only the fast (risk) lane is fatal.** It marks open positions and fires SL/TP,
so a stall there means real money is sitting unmanaged — that is worth taking the
box out of rotation and failing a deploy for. The signal lane only opens new
entries; a stall there is bad but not an emergency, and it *legitimately* stops
beating overnight (`runner.run_signal_loop` takes the `any_open`-false branch and
never reaches `_beat_now`). Since `deploy.sh` refuses to run during market hours,
a fatal signal lane would 503 on every legitimate deploy.

**Ages must be measured on a wall clock.** `_beat_now` stamps `provider.now()`,
which under the mock provider is *simulated* time that jumps a whole candle per
tick — measuring staleness against that reports a healthy dev engine as stale.
The runner keeps a parallel monotonic beat (`_beat_wall`) purely for this.
"""
from __future__ import annotations

from dataclasses import dataclass

# Lane names, matching the runner's `_beat_now` keys.
LANE_RISK = "risk"
LANE_SIGNAL = "signal"

# Lane states. `idle` and `stale` are deliberately different words for the same
# silence: one is the market being shut, the other is a loop that should be
# running and is not.
STATE_OK = "ok"
STATE_STARTING = "starting"   # process is young and this lane has not beaten yet
STATE_IDLE = "idle"           # silent, but expected to be (markets closed)
STATE_STALE = "stale"         # beat once, then went quiet past its budget
STATE_DEAD = "dead"           # never beat at all, and the grace period is over

_BAD_STATES = (STATE_STALE, STATE_DEAD)

# Overall verdict. Only `unready` is not ready — see `evaluate`.
STATUS_OK = "ok"
STATUS_STARTING = "starting"
STATUS_DEGRADED = "degraded"
STATUS_UNREADY = "unready"


@dataclass(frozen=True)
class Thresholds:
    """Staleness budgets, in seconds.

    Deliberately NOT `runtime_config`-overridable: these gate a safety probe, and
    a DB override that silences it is a footgun with no upside. They are static
    `Settings` fields instead.

    `risk_stale_seconds` is intentionally much larger than the runner's own
    `watchdog_stale_seconds` (30s, which fires a Telegram alert). One risk
    iteration can legitimately block for the live order-poll window, so the
    alert should be twitchy and the HTTP verdict should not: a probe that flaps
    during a normal exit poll would be turned off within a week.
    """
    risk_stale_seconds: float = 90.0
    signal_stale_seconds: float = 600.0
    startup_grace_seconds: float = 45.0


def lane_state(
    age_seconds: float | None,
    *,
    uptime_seconds: float,
    budget_seconds: float,
    grace_seconds: float,
    silence_expected: bool,
) -> str:
    """Classify one loop lane from the age of its last heartbeat.

    `age_seconds is None` means the lane has never beaten: during boot that is
    `starting`, and after the grace period it is `dead` — a task that died on
    startup never produces a beat to go stale, so age alone cannot see it.
    """
    if age_seconds is None:
        if uptime_seconds < grace_seconds:
            return STATE_STARTING
        return STATE_IDLE if silence_expected else STATE_DEAD
    if age_seconds <= budget_seconds:
        return STATE_OK
    return STATE_IDLE if silence_expected else STATE_STALE


def evaluate(
    *,
    uptime_seconds: float,
    db_ok: bool,
    db_error: str = "",
    engine_running: bool,
    lane_ages: dict[str, float | None],
    markets_open: bool | None,
    provider_auth_error: bool = False,
    feed_anomalies: int = 0,
    thresholds: Thresholds,
) -> dict:
    """Decide whether this process is fit to be managing real money right now.

    `markets_open=None` means we could not resolve the session (a provider read
    threw). That is treated as "silence is expected" rather than guessed either
    way: the alternative is a nightly false alarm, and an alarm that cries wolf
    every night is one nobody reads on the morning it matters.

    Returns the whole payload, including the checks that PASSED — a probe body
    that only lists failures cannot be used to prove something was verified.
    """
    checks: list[dict] = []

    def check(name: str, ok: bool, fatal: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": ok, "fatal": fatal, "detail": detail})

    check("database", db_ok, fatal=True,
          detail="" if db_ok else f"database unreachable: {db_error or 'unknown error'}")
    check("engine_running", engine_running, fatal=True,
          detail="" if engine_running else
                 "engine loops are not running — the process is up and serving HTTP "
                 "but nothing is managing positions")

    # The risk lane never idles: it has no market-hours branch and beats every
    # tick, all night. The signal lane goes quiet whenever no enabled market is
    # open — and, being the lane that also drives the mock's clock, whenever the
    # mock history is exhausted.
    lane_specs = (
        (LANE_RISK, thresholds.risk_stale_seconds, False, True,
         "open positions are NOT being marked — no SL/TP is firing"),
        (LANE_SIGNAL, thresholds.signal_stale_seconds, markets_open is not True, False,
         "no new entries are being scanned"),
    )

    loops: dict[str, dict] = {}
    for lane, budget, silence_expected, fatal, why in lane_specs:
        state = lane_state(
            lane_ages.get(lane),
            uptime_seconds=uptime_seconds,
            budget_seconds=budget,
            grace_seconds=thresholds.startup_grace_seconds,
            silence_expected=silence_expected,
        )
        loops[lane] = {
            "age_seconds": lane_ages.get(lane),
            "state": state,
            "budget_seconds": budget,
            "fatal": fatal,
        }
        bad = state in _BAD_STATES
        check(f"{lane}_lane", not bad, fatal=fatal,
              detail="" if not bad else f"{lane} loop is {state} — {why}")

    check("provider_auth", not provider_auth_error, fatal=False,
          detail="" if not provider_auth_error else
                 "broker session/token rejected — re-authenticate (Connect Kite)")

    # Deliberately NOT fatal: these bars were successfully de-duplicated, sorted
    # or repaired before any strategy saw them. The engine handled it; a human
    # should still know the feed is misbehaving.
    check("feed_quality", not feed_anomalies, fatal=False,
          detail="" if not feed_anomalies else
                 f"{feed_anomalies} instrument(s) returning anomalous candles "
                 f"(duplicated, out-of-order or self-inconsistent bars) — repaired "
                 f"before use; see provider_feed in this payload")

    failed = [c["name"] for c in checks if not c["ok"] and c["fatal"]]
    degraded = [c["name"] for c in checks if not c["ok"] and not c["fatal"]]

    if failed:
        status = STATUS_UNREADY
    elif any(v["state"] == STATE_STARTING for v in loops.values()):
        # Reported separately from `ok` so a deploy can WAIT for the lanes to
        # come up instead of accepting the first 200 and verifying nothing.
        status = STATUS_STARTING
    elif degraded:
        status = STATUS_DEGRADED
    else:
        status = STATUS_OK

    return {
        "ready": not failed,
        "status": status,
        "uptime_seconds": round(uptime_seconds, 1),
        "db": {"ok": db_ok, "error": db_error},
        "loops": loops,
        "markets_open": markets_open,
        "checks": checks,
        "failed_checks": failed,
        "degraded_checks": degraded,
    }
