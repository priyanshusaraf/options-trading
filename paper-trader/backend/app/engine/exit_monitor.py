"""
When to close an open option position. Owner's rule: exit on a premium stop-loss
OR target OR the strategy's own exit flag — whichever comes first. Premium guards
are evaluated before the strategy flag so a protective stop/target wins any tie.
"""
from __future__ import annotations


def evaluate_exit(direction: str, stop_price: float, target_price: float,
                  current_premium: float, long_exit: bool, short_exit: bool,
                  target_disabled: bool = False
                  ) -> tuple[bool, str | None]:
    # protective premium guards first
    if current_premium <= stop_price:
        return True, "STOP_LOSS"
    # `target_disabled` = owner's per-position "let it run / no take-profit": the
    # profit cap is removed (for an overnight winner running on news) but the stop
    # below and the strategy exit are UNAFFECTED — there is always a protective
    # floor (the trailing stop).
    if not target_disabled and current_premium >= target_price:
        return True, "TARGET"
    # then the strategy's own exit on the underlying
    if direction == "LONG" and long_exit:
        return True, "STRATEGY_EXIT"
    if direction == "SHORT" and short_exit:
        return True, "STRATEGY_EXIT"
    return False, None


def trailing_stop(entry: float, high_water: float, current_stop: float,
                  *, trigger_pct: float, lock_pct: float, target_pct: float) -> float:
    """Ratchet the premium stop UP as profit thresholds are crossed; never down.

    Each time the high-water premium clears another `trigger_pct` of profit (as a
    fraction of entry), the stop is raised by `lock_pct` of entry, until the
    `target_pct` final target. Returns the new stop (>= current_stop).

    Owner's example — entry 400, trigger 10%, lock 2.5%, target 60%:
        high-water 440 (+10%) -> 1 step -> stop 410
        high-water 480 (+20%) -> 2 steps -> stop 420
        ...
        high-water 640 (+60%) -> 6 steps -> stop 460  (capped at target)
    """
    if entry <= 0 or high_water <= entry or trigger_pct <= 0:
        return current_stop
    profit_frac = min((high_water - entry) / entry, target_pct)
    steps = int(profit_frac / trigger_pct + 1e-9)
    if steps <= 0:
        return current_stop
    ratchet = entry * (1 + steps * lock_pct)
    return max(current_stop, round(ratchet, 2))


def apply_reinforcement(entry: float, current_stop: float, current_target: float,
                        current_premium: float, count: int,
                        last_reinforce_time, now, params: dict) -> dict:
    """A fresh SAME-DIRECTION crossover on an open winner. We do NOT add quantity
    (no pyramiding); we strengthen management: lock the stop further into profit,
    optionally extend the target, and increment the reinforcement count.

    Returns {applied, stop_price, target_price, count, reason}. The stop never
    loosens and the target never shrinks. Gated by a minimum-profit floor (don't
    tighten on noise), a cooldown, and a max-reinforcement cap (theta limits the
    value of endless confirmations on a bought option).
    """
    keep = {"applied": False, "stop_price": current_stop,
            "target_price": current_target, "count": count}
    if not params.get("reinforce_enabled", True):
        return {**keep, "reason": "reinforcement disabled"}
    if count >= params["max_reinforcements"]:
        return {**keep, "reason": "max reinforcements reached"}
    profit = (current_premium - entry) / entry if entry > 0 else 0.0
    if profit < params["reinforce_min_profit_pct"]:
        return {**keep, "reason": f"not profitable enough ({profit:.0%})"}
    if last_reinforce_time is not None:
        gap_min = (now - last_reinforce_time).total_seconds() / 60.0
        if gap_min < params["reinforce_cooldown_minutes"]:
            return {**keep, "reason": "within reinforcement cooldown"}
    new_count = count + 1
    # lock the stop at entry*(1 + count*lock) — escalates each reinforcement and
    # never loosens. The default 5%/step comfortably clears round-trip option
    # charges, so a reinforced trade cannot end as a net loss.
    new_stop = max(current_stop, round(entry * (1 + new_count * params["reinforce_lock_pct"]), 2))
    new_target = current_target
    if params.get("reinforce_extend_tp", True):
        extended = current_target + entry * params["reinforce_tp_extend_pct"]
        cap = entry * (1 + params["reinforce_tp_max_pct"])
        new_target = max(current_target, min(round(extended, 2), round(cap, 2)))
    return {"applied": True, "stop_price": new_stop, "target_price": new_target,
            "count": new_count,
            "reason": f"reinforced #{new_count}: SL→{new_stop:.2f}, TP→{new_target:.2f}"}
