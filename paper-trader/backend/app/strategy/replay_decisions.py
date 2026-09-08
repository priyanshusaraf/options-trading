"""Shared completed-bar decisions for research and simulated monitoring.

Callers own verified input rows, declared policies, state persistence and fills.
Returned tuples describe a pending simulation decision for the next observed bar;
this module neither fills a trade nor grants execution authority.
"""
from __future__ import annotations

from app.engine.decision_kernel import ExitPolicy, decide_exit
from app.engine.equity_entry import equity_stop_target


def next_fill_index(signal_index: int) -> int:
    """The earliest fill for a completed-bar decision is the next observed bar."""
    return signal_index + 1


def protection_band(position, document):
    if document is None:
        return None, None
    sl, tp = document["stop_loss_pct"], document["take_profit_pct"]
    stop, target = equity_stop_target(position["direction"], position["entry_price"], sl, tp)
    return (stop if sl else None), (target if tp else None)


def held_exit(position, ratchet, row, index, *, protective_band, unprotected_exit_policy):
    # Original Pine management starts strictly after the simulated fill bar.
    if index <= position["entry_idx"]:
        return None
    close = float(row["close"])
    ratchet_hit = False
    if ratchet is not None:
        ratchet.update(float(row["high"]), float(row["low"]), close,
                       float(row["_ratchet_atr"]))
        ratchet_hit = ratchet.stop_hit(close)
    stop, target = protection_band(position, protective_band)
    policy = ExitPolicy() if protective_band else unprotected_exit_policy
    decision = decide_exit(direction=position["direction"], price=close,
        stop=stop, target=target, long_exit=bool(row["longExit"]),
        short_exit=bool(row["shortExit"]), ratchet_exit=ratchet_hit, policy=policy)
    return ("EXIT", decision.reason, index + 1) if decision.should_exit else None


def entry_direction(row, refuse_conflicts):
    long_entry, short_entry = bool(row["longEntry"]), bool(row["shortEntry"])
    if refuse_conflicts and long_entry and short_entry:
        raise ValueError("PINE_REPLAY_CONFLICTING_ENTRIES")
    if long_entry:
        return "LONG"
    return "SHORT" if short_entry else None


def next_decision(position, ratchet, row, index, direction, *, allow_reversal,
                  protective_band, unprotected_exit_policy):
    """Apply the declared reversal policy without fabricating a next-bar fill."""
    if position is None:
        return ("ENTER", direction, next_fill_index(index)) if direction else None
    if allow_reversal and direction and direction != position["direction"]:
        if protective_band is not None:
            decision = held_exit(position, ratchet, row, index,
                protective_band=protective_band, unprotected_exit_policy=unprotected_exit_policy)
            if decision and decision[1] in {"STOP_LOSS", "TARGET"}:
                return decision
        return ("REVERSE", direction, next_fill_index(index))
    return held_exit(position, ratchet, row, index,
        protective_band=protective_band, unprotected_exit_policy=unprotected_exit_policy)
