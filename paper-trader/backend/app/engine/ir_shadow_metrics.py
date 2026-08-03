"""What the L1 Stage 1 shadow lane costs and how often it agrees.

Stage 1's close criteria are numbers, so the denominators matter more than the code:

- **agreement is per bar, not per scan.** The signal lane re-reads the same completed bar
  every 2.5 s until the next one prints, so counting scans would let one agreeing bar,
  re-read three hundred times, bury a real disagreement under a 99.7% "agreement rate".
- **an unmeasured rate is `None`, never 1.0.** A dashboard cannot be allowed to show
  "perfect agreement" for a lane that has observed nothing — which is the ordinary state
  in production, where the default strategy has no mirror.
- **instruments with no mirror are counted.** Zero coverage and perfect agreement are
  otherwise indistinguishable.
- **cost is recorded even when the evaluation failed.** A refusal that took a second still
  took a second from the loop.

Everything is in memory and bounded: the box is 1 GB and has OOM'd twice. Nothing here
raises — this runs inside the signal lane, and a metric that throws is a metric that stops
the engine.
"""
from __future__ import annotations

import datetime as dt
from collections import Counter, deque

from app.engine.ir_shadow import AGREEMENT, INSUFFICIENT_HISTORY

#: Samples kept for the percentile estimates. ~2 hours of one-per-2.5 s scans per
#: instrument; enough for a stable p95, small enough to be free.
DEFAULT_SAMPLE_LIMIT = 2000


def percentile(samples: list[float], fraction: float) -> float | None:
    """Nearest-rank percentile. No interpolation: with a handful of samples an
    interpolated p95 invents a value that was never measured."""
    if not samples:
        return None
    ordered = sorted(samples)
    rank = max(1, min(len(ordered), int(-(-fraction * len(ordered) // 1))))
    return ordered[rank - 1]


def _summary(samples: deque) -> dict:
    values = list(samples)
    return {
        "count": len(values),
        "p50": percentile(values, 0.50),
        "p95": percentile(values, 0.95),
        "max": max(values) if values else None,
    }


class ShadowMetrics:
    """Rolling counters for one process's shadow lane."""

    def __init__(self, sample_limit: int = DEFAULT_SAMPLE_LIMIT) -> None:
        self.bars_observed = 0
        self.agreements = 0
        self.disagreements = 0
        self.skipped_no_pairing = 0
        self.insufficient_history_in_hours = 0
        self.insufficient_history_out_of_hours = 0
        self.by_reason: Counter[str] = Counter()
        self.last_observed_at: dt.datetime | None = None
        self.instruments: set[str] = set()
        self._eval_samples: deque[float] = deque(maxlen=sample_limit)
        #: The newest bar seen per instrument — an O(instruments) way to tell a new bar
        #: from a re-scan without keeping every bar ever seen.
        self._last_bar: dict[str, dt.datetime | None] = {}
        # loop impact
        self.loop_iterations = 0
        self.loop_overruns = 0
        self.loop_budget_seconds: float | None = None
        self.max_iteration_seconds: float | None = None
        self._iteration_samples: deque[float] = deque(maxlen=sample_limit)
        self._shadow_samples: deque[float] = deque(maxlen=sample_limit)

    # ── recording ────────────────────────────────────────────────────────────────
    def observe(self, observation, *, market_open: bool) -> None:
        """Count one observation. A repeat of an instrument's newest bar is cost-only."""
        try:
            if observation is None:
                return
            self._eval_samples.append(float(observation.eval_seconds))
            self.last_observed_at = observation.observed_at
            self.instruments.add(observation.instrument_key)

            bar = observation.bar_time
            if bar is None:
                return                      # cost counted; a bar with no time is not a bar
            if self._last_bar.get(observation.instrument_key) == bar:
                return                      # the same completed bar, re-scanned
            self._last_bar[observation.instrument_key] = bar

            self.bars_observed += 1
            if observation.reason == AGREEMENT:
                self.agreements += 1
                return
            self.disagreements += 1
            self.by_reason[observation.reason] += 1
            if observation.reason == INSUFFICIENT_HISTORY:
                if market_open:
                    self.insufficient_history_in_hours += 1
                else:
                    self.insufficient_history_out_of_hours += 1
        except Exception:                                 # noqa: BLE001 — see module docs
            pass

    def skipped(self, instrument_key: str) -> None:
        """An instrument whose authoritative strategy has no IR mirror."""
        self.skipped_no_pairing += 1

    def loop(self, *, iteration_seconds: float, shadow_seconds: float,
             budget_seconds: float) -> None:
        """One signal-loop iteration: what it took, and what the shadow took of it."""
        try:
            self.loop_iterations += 1
            self.loop_budget_seconds = float(budget_seconds)
            self._iteration_samples.append(float(iteration_seconds))
            self._shadow_samples.append(float(shadow_seconds))
            if self.max_iteration_seconds is None or iteration_seconds > self.max_iteration_seconds:
                self.max_iteration_seconds = float(iteration_seconds)
            if budget_seconds > 0 and iteration_seconds > budget_seconds:
                # The lane sleeps a fixed tick between iterations, so an iteration longer
                # than the tick is a cycle the scheduler could not start on time.
                self.loop_overruns += 1
        except Exception:                                 # noqa: BLE001
            pass

    # ── reporting ────────────────────────────────────────────────────────────────
    def snapshot(self) -> dict:
        shadow_p95 = percentile(list(self._shadow_samples), 0.95)
        budget = self.loop_budget_seconds
        return {
            "bars_observed": self.bars_observed,
            "agreements": self.agreements,
            "disagreements": self.disagreements,
            "agreement_rate": (None if self.bars_observed == 0
                               else self.agreements / self.bars_observed),
            "by_reason": dict(self.by_reason),
            "insufficient_history_in_hours": self.insufficient_history_in_hours,
            "insufficient_history_out_of_hours": self.insufficient_history_out_of_hours,
            "skipped_no_pairing": self.skipped_no_pairing,
            "instruments": sorted(self.instruments),
            "last_observed_at": (self.last_observed_at.isoformat()
                                 if self.last_observed_at else None),
            "eval_seconds": _summary(self._eval_samples),
            "loop": {
                "iterations": self.loop_iterations,
                "budget_seconds": budget,
                "overruns": self.loop_overruns,
                "max_iteration_seconds": self.max_iteration_seconds,
                "iteration_seconds": _summary(self._iteration_samples),
                "shadow_seconds": _summary(self._shadow_samples),
                "shadow_share_p95": (None if not budget or shadow_p95 is None
                                     else shadow_p95 / budget),
            },
        }


__all__ = ["DEFAULT_SAMPLE_LIMIT", "ShadowMetrics", "percentile"]
