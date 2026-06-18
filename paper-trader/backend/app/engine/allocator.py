"""
Capital allocator.

Owner's rule, exactly:
  - If there is enough cash to fund every instrument that fired this tick, fund
    them all — order is irrelevant.
  - Under a shortfall, the liquidity priority order (NIFTY > GOLD MINI > ... >
    DHANIYA, see core/instruments.py) decides who gets funded: walk candidates
    in priority order and fund greedily until the cash can't cover the next one.
  - This is strict greedy-by-priority, NOT a max-fill optimisation: a funded
    high-priority order can block cheaper lower-priority ones.
  - Anything not funded this tick is dropped (the runner never queues it). A new
    position only opens on a fresh signal while cash is available.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.core.instruments import INSTRUMENTS


@dataclass
class Candidate:
    instrument_key: str
    direction: str
    cost: float


@dataclass
class Allocation:
    funded: list[Candidate] = field(default_factory=list)
    skipped: list[tuple[Candidate, str]] = field(default_factory=list)


def allocate(candidates: list[Candidate], available_cash: float) -> Allocation:
    res = Allocation()
    ordered = sorted(candidates, key=lambda c: INSTRUMENTS[c.instrument_key].priority)
    cash = available_cash
    for cand in ordered:
        if cand.cost <= cash:
            res.funded.append(cand)
            cash -= cand.cost
        else:
            res.skipped.append(
                (cand, f"insufficient capital: need ₹{cand.cost:,.0f}, "
                       f"have ₹{cash:,.0f}"))
    return res
