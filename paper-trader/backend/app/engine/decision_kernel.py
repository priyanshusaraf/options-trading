"""The shared exit-decision kernel — one implementation for live, replay and backtest.

Why this exists
---------------
Before Phase G there were three exit implementations that were never compared:

  * `exit_monitor.evaluate_exit`  — live options: premium stop, target, ratchet, flag
  * `equity_entry.equity_exit`    — live equity: direction-aware stop, target, flag
  * `backtest/engine.run_trades`  — backtest: ratchet and flag ONLY

The third is the problem, and it is the one that gets published. `backtest/engine.py`
says so in its own docstring — "the option-premium stop/target of the LIVE engine is
not modelled here" — so the simulator and the executor were different programs, and
the difference was invisible in the output. In a marketplace the backtest number IS
the product; a divergence nobody can see is a divergence customers discover with
their own capital.

This module is the single decision function all three now route through. It is
PURE: no I/O, no clock, no broker, no session. Broker interaction deliberately stays
outside — the kernel decides *what should happen*, the caller decides *how to make it
happen*, and only the second part differs between live and simulation.

Behaviour preservation
----------------------
This kernel was extracted, not designed. It reproduces the existing precedence
exactly — STOP_LOSS, then TARGET, then RATCHET_STOP, then STRATEGY_EXIT — and the
two live functions are now thin wrappers over it that keep their old signatures and
return types. Their existing tests pass unchanged, which is the proof.

Declared divergence
-------------------
The default backtest path uses `ExitPolicy.no_protective_band()` because historical
option premiums are unavailable for most instruments. An explicit percentage policy
can instead manage the underlying with completed-close triggers and next-open fills.
Neither policy claims to reproduce historical option-premium stops.
"""
from __future__ import annotations

import dataclasses
import math

# Exit reasons, in the order they are evaluated. The ORDER IS THE POLICY: a
# protective stop must win any tie against a target or a strategy flag, because the
# stop is the thing that bounds loss.
STOP_LOSS = "STOP_LOSS"
TARGET = "TARGET"
RATCHET_STOP = "RATCHET_STOP"
STRATEGY_EXIT = "STRATEGY_EXIT"
PRECEDENCE = (STOP_LOSS, TARGET, RATCHET_STOP, STRATEGY_EXIT)

# How the protective band relates to price.
#
#   PREMIUM      — a bought option. The position is LONG THE PREMIUM whichever way
#                  the underlying trade is directional, so the stop is always below
#                  and the target always above. This is why the options path is not
#                  direction-aware and the equity path is: they are different facts,
#                  not an inconsistency.
#   DIRECTIONAL  — spot/futures. A SHORT's stop is ABOVE entry.
PREMIUM = "premium"
DIRECTIONAL = "directional"


@dataclasses.dataclass(frozen=True)
class ExitPolicy:
    """Which exit mechanisms are in force. Explicit so that "this is not modelled"
    is a decision on the record rather than a missing branch."""
    band: str = DIRECTIONAL          # PREMIUM | DIRECTIONAL
    protective_band: bool = True     # False => stop/target not modelled at all
    target_enabled: bool = True      # per-position "let it run" (no_take_profit)
    ratchet: bool = True
    strategy_flags: bool = True
    # Free-text note explaining any False above. Required by `divergences()` so a
    # disabled mechanism can never be silently disabled.
    note: str = ""

    @staticmethod
    def live_options(*, target_enabled: bool = True) -> "ExitPolicy":
        return ExitPolicy(band=PREMIUM, target_enabled=target_enabled)

    @staticmethod
    def live_directional(*, target_enabled: bool = True) -> "ExitPolicy":
        return ExitPolicy(band=DIRECTIONAL, target_enabled=target_enabled)

    @staticmethod
    def no_protective_band(note: str) -> "ExitPolicy":
        """The backtest policy. Stop and target are NOT evaluated.

        `note` is mandatory: an unmodelled protective band is the single largest
        way a simulated result can flatter a live one, so the reason travels with
        the policy and surfaces in `divergences()`.
        """
        if not note:
            raise ValueError(
                "no_protective_band() requires a note explaining WHY the stop and "
                "target are not modelled — an undocumented divergence between the "
                "backtester and the executor is what this kernel exists to prevent")
        return ExitPolicy(protective_band=False, target_enabled=False, note=note)

    def divergences(self) -> list[str]:
        """Every mechanism this policy does not evaluate, for reporting alongside
        results. An empty list means the caller ran full live semantics."""
        out = []
        if not self.protective_band:
            out.append(f"protective band (stop/target) not evaluated: {self.note}")
        elif not self.target_enabled:
            out.append("target disabled for this position (let-it-run)")
        if not self.ratchet:
            out.append(f"ratchet not evaluated: {self.note}")
        if not self.strategy_flags:
            out.append(f"strategy exit flags not evaluated: {self.note}")
        return out


@dataclasses.dataclass(frozen=True)
class ExitDecision:
    """`should_exit` plus WHY. The reason is not decoration — it drives the
    re-entry cooldown (STOP_LOSS only) and every P&L attribution downstream."""
    should_exit: bool
    reason: str | None = None

    def as_tuple(self) -> tuple[bool, str | None]:
        return self.should_exit, self.reason


def _band_hit(band: str, direction: str, price: float,
              stop: float | None, target: float | None,
              target_enabled: bool) -> str | None:
    """`None` for a level means it is not set, and is skipped.

    There is no numeric sentinel for "no stop", deliberately. The obvious ones are
    both wrong for one direction: 0 and -inf mean "stopped at any price" on the
    DIRECTIONAL short path (`price >= stop`), and +inf is wrong for a long. A level
    that means different numbers depending on direction is a level that will be
    passed the wrong way round eventually, so it is not a number at all.
    """
    if band == PREMIUM:
        # L13 — a non-positive premium is a missing/bad tick, not a tradeable price
        # (an option cannot trade at <= 0), so it must NOT fire a real market STOP
        # exit. A genuine floor is a small POSITIVE tick and still trips the stop on
        # the next mark. Removing this guard means a feed gap sells the position.
        if stop is not None and price > 0 and price <= stop:
            return STOP_LOSS
        if target is not None and target_enabled and price >= target:
            return TARGET
        return None
    # DIRECTIONAL: a SHORT is stopped when price rises and targeted when it falls.
    if direction == "LONG":
        if stop is not None and price <= stop:
            return STOP_LOSS
        if target is not None and target_enabled and price >= target:
            return TARGET
    else:
        if stop is not None and price >= stop:
            return STOP_LOSS
        if target is not None and target_enabled and price <= target:
            return TARGET
    return None


def decide_exit(*, direction: str, price: float,
                stop: float | None = None, target: float | None = None,
                long_exit: bool = False, short_exit: bool = False,
                ratchet_exit: bool = False,
                policy: ExitPolicy | None = None) -> ExitDecision:
    """Should this position close on this mark, and why.

    Pure. Same inputs always give the same answer — which is what makes it
    replayable, and what makes a live-vs-backtest parity assertion possible at all.
    """
    policy = policy or ExitPolicy()

    if policy.protective_band:
        hit = _band_hit(policy.band, direction, price, stop, target,
                        policy.target_enabled)
        if hit:
            return ExitDecision(True, hit)

    # The backtest-validated ratchet on the underlying (bar cadence, close-confirmed).
    # Sits after the protective floor and before the strategy's own exit, matching
    # the backtest's own precedence — the two agreed on this already and the order
    # is preserved rather than re-litigated.
    if policy.ratchet and ratchet_exit:
        return ExitDecision(True, RATCHET_STOP)

    if policy.strategy_flags:
        if direction == "LONG" and long_exit:
            return ExitDecision(True, STRATEGY_EXIT)
        if direction == "SHORT" and short_exit:
            return ExitDecision(True, STRATEGY_EXIT)

    return ExitDecision(False, None)

def protective_band_document(stop_loss_pct=0.0, take_profit_pct=0.0):
    """Bind optional directional fractions to the close-confirmed replay policy."""
    values = {}
    for name, value in (("stop_loss_pct", stop_loss_pct), ("take_profit_pct", take_profit_pct)):
        if value is None:
            value = 0.0
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value < 1:
            raise ValueError(f"{name} must be a finite fraction from 0 (disabled) to less than 1")
        values[name] = float(value)
    if not any(values.values()):
        return None
    return {"schema": "research-percentage-exit-policy/1", **values,
            "basis": "slipped-entry-fill", "trigger": "completed-close-after-entry-bar",
            "fill": "next-bar-open-adverse-slippage", "intrabar": "not-evaluated",
            "precedence": "stop-target-ratchet-strategy"}
