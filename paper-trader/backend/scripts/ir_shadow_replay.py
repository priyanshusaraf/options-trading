#!/usr/bin/env python3
"""Measure the L1 Stage 1 shadow lane: agreement, classifications, cost, loop impact.

    backend/.venv/bin/python scripts/ir_shadow_replay.py

Two measurements, deliberately separate because they answer different questions.

**1. Replay — does the mirror agree, and what does one evaluation cost?**
Walks real recorded series bar by bar, growing the frame the way the live lane sees it
(one more completed bar each scan), and runs the authoritative strategy and the IR mirror
through the *shipping* `ir_shadow.observe`. No shortcuts around the adapter, the frame
contract or the warmup mask — the whole point of ADR 0011 §4 is that a parity claim which
bypasses the adapter is not a claim about what runs.

The series are real closes recorded from Kite (2026-06-22 → 2026-07-08, six instruments);
`open`, `high`, `low` and `volume` are reconstructed deterministically because per-bar
OHLCV was not recoverable offline. Stated rather than hidden: for an agreement measurement
it is sound — both lanes receive the identical frame, so any divergence is theirs — but it
is not a claim about live Kite bars.

**2. Loop A/B — what does the lane cost the 2.5 s signal loop?**
Runs the real `EngineRunner._signal_iteration_blocking` under the mock provider with the
lane off and then on, and reports both distributions. This is the only honest way to get
the counterfactual: a live process can only ever measure one of the two.

Nothing here trades, and nothing here writes the ledger — the mock provider and a temporary
database are forced before any `app.*` import.
"""
from __future__ import annotations

import json
import argparse
import os
import pathlib
import sys
import tempfile
import time

BACKEND = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

os.environ["PT_PROVIDER"] = "mock"
os.environ["PT_EXECUTION"] = "paper"
os.environ["PT_LIVE_ACK"] = ""
os.environ["PT_DISABLE_DOTENV"] = "1"
os.environ.setdefault("PT_DB_PATH", str(pathlib.Path(tempfile.mkdtemp()) / "replay.db"))

import csv                                                            # noqa: E402

import pandas as pd                                                   # noqa: E402

from app.engine import ir_shadow                                      # noqa: E402
from app.engine.ir_shadow_metrics import ShadowMetrics                # noqa: E402
from app.strategy.registry.expanding_z_v4 import STRATEGY as HANDWRITTEN  # noqa: E402

DATA = BACKEND / "tests" / "data" / "real_spot_series.csv"
#: Warmup is 302 bars, so only these instruments have a settled region to measure on.
#: The others are reported as what they are — too short — rather than quietly dropped.
LOOP_ITERATIONS = 12


def real_series() -> dict[str, list[float]]:
    out: dict[str, list[float]] = {}
    with DATA.open() as handle:
        for row in csv.DictReader(handle):
            out.setdefault(row["instrument_key"], []).append(float(row["spot"]))
    return out


def frame(closes: list[float]) -> pd.DataFrame:
    close = pd.Series(closes, dtype=float)
    prev = close.shift(1).fillna(close.iloc[0]) if len(close) else close
    spread = close.abs() * 0.0005
    return pd.DataFrame({
        "date": pd.date_range("2026-06-22 09:15", periods=len(close), freq="15min",
                              tz="Asia/Kolkata"),
        "open": prev,
        "high": pd.concat([close, prev], axis=1).max(axis=1) + spread,
        "low": pd.concat([close, prev], axis=1).min(axis=1) - spread,
        "close": close,
        "volume": pd.Series(1000.0, index=close.index),
    })


def replay() -> dict:
    """Bar-by-bar agreement over every recorded series."""
    metrics = ShadowMetrics(sample_limit=100_000)
    per_instrument: dict[str, dict] = {}
    disagreements: list[dict] = []

    for instrument, closes in sorted(real_series().items()):
        agreed = observed = 0
        reasons: dict[str, int] = {}
        for end in range(1, len(closes) + 1):
            window = frame(closes[:end])
            authoritative = HANDWRITTEN.signals(window)
            observation = ir_shadow.observe(
                instrument_key=instrument, authoritative_key="expanding_z_v4",
                authoritative_frame=authoritative, frame=window,
                now=pd.Timestamp(window.iloc[-1]["date"]).to_pydatetime())
            metrics.observe(observation, market_open=True)
            observed += 1
            if observation.reason == ir_shadow.AGREEMENT:
                agreed += 1
                continue
            reasons[observation.reason] = reasons.get(observation.reason, 0) + 1
            if observation.reason != ir_shadow.INSUFFICIENT_HISTORY:
                disagreements.append({
                    "instrument": instrument, "bar": end,
                    "reason": observation.reason, "detail": observation.detail,
                    "graph_address": observation.graph_address,
                    "frame_id": observation.frame_id,
                    "authoritative": observation.authoritative, "ir": observation.ir,
                })
        settled = observed - reasons.get(ir_shadow.INSUFFICIENT_HISTORY, 0)
        per_instrument[instrument] = {
            "bars": observed,
            "settled_bars": settled,
            "agreed": agreed,
            "agreement_rate": (agreed / settled) if settled else None,
            "reasons": reasons,
        }
    return {"per_instrument": per_instrument, "metrics": metrics.snapshot(),
            "unexplained_disagreements": disagreements}


def loop_ab(*, owner_id: str, settle_first: bool = False) -> dict:
    """The real signal iteration, lane off then on, under the mock provider.

    `settle_first` matters more than it looks. The mock hands back a window bounded by its
    own cursor — 161 bars at first run, whatever the interval or `history_days` — against a
    302-bar warmup, so a fresh mock makes the shadow **refuse immediately** and cost almost
    nothing. That is a truthful measurement of a short frame and a useless measurement of
    what an evaluation costs. Advancing the mock past the warmup first gives the second
    number, with the same engine code path and the same provider.
    """
    from app.core import runtime_config
    from app.core.instruments import get_instrument
    from app.db.session import init_db
    from app.engine.runner import EngineRunner
    from app.providers.factory import get_provider
    from app.db.models import LEGACY_BROKER_ACCOUNT_ID

    if settle_first:
        provider = get_provider()
        probe = get_instrument(next(iter(real_series())))
        while len(provider.get_candles(probe, "15minute", 30)) < 320:
            if not provider.advance():
                break

    def measure(enabled: bool) -> dict:
        init_db(reset=True)
        # Through the sanctioned channel, not by poking `params`: the iteration begins
        # with `refresh_params()`, which would overwrite an attribute set by hand — and
        # silently measure the lane as OFF in both arms.
        runtime_config.set_override("ir_shadow_enabled", enabled, owner_id=owner_id)
        runner = EngineRunner(owner_id=owner_id,
                              broker_account_id=LEGACY_BROKER_ACCOUNT_ID)
        for key in list(runner.enabled):
            runner.strategy_keys[key] = "expanding_z_v4"
        durations = []
        for _ in range(LOOP_ITERATIONS):
            started = time.perf_counter()
            runner._signal_iteration_blocking()
            durations.append(time.perf_counter() - started)
            runner.provider.advance()
        snapshot = runner.shadow_metrics.snapshot()
        runtime_config.clear_override("ir_shadow_enabled", owner_id=owner_id)
        assert runner.params["ir_shadow_enabled"] is enabled, "the arm did not take"
        durations.sort()
        return {
            "iterations": len(durations),
            "p50": durations[len(durations) // 2],
            "p95": durations[max(0, int(0.95 * len(durations)) - 1)],
            "max": durations[-1],
            "shadow_seconds": snapshot["loop"]["shadow_seconds"],
            "overruns": snapshot["loop"]["overruns"],
            "budget_seconds": snapshot["loop"]["budget_seconds"],
            "bars_observed": snapshot["bars_observed"],
        }

    off, on = measure(False), measure(True)
    budget = on["budget_seconds"] or 2.5
    return {
        "frames": "settled (mock advanced past warmup)" if settle_first
                  else "as a fresh process sees them (161 bars)",
        "off": off, "on": on,
        "delta_p50": on["p50"] - off["p50"],
        "delta_p95": on["p95"] - off["p95"],
        "shadow_p95_share_of_budget": (on["shadow_seconds"]["p95"] or 0.0) / budget,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--owner-id", required=True,
                        help="organization whose shadow-lane runtime override is measured")
    args = parser.parse_args()
    result = {
        "replay": replay(),
        # As shipped: 30 days of history, which the graph cannot settle.
        "loop_short_frames": loop_ab(owner_id=args.owner_id),
        # Enough history that the graph settles, so the cost measured is a real
        # evaluation rather than an immediate refusal.
        "loop_settled": loop_ab(owner_id=args.owner_id, settle_first=True),
    }

    print(json.dumps(result, indent=2, default=str))

    replayed = result["replay"]
    print("\n─── summary " + "─" * 60, file=sys.stderr)
    for instrument, stats in replayed["per_instrument"].items():
        rate = stats["agreement_rate"]
        print(f"{instrument:<12} settled={stats['settled_bars']:>4}  "
              f"agreement={'n/a' if rate is None else f'{rate:.4%}'}  "
              f"reasons={stats['reasons'] or '{}'}", file=sys.stderr)
    cost = replayed["metrics"]["eval_seconds"]
    print(f"eval seconds  p50={cost['p50']:.4f}  p95={cost['p95']:.4f}  "
          f"max={cost['max']:.4f}  n={cost['count']}", file=sys.stderr)
    for label in ("loop_short_frames", "loop_settled"):
        loop = result[label]
        print(f"{label:<18} {loop['frames']:<46} "
              f"off p95={loop['off']['p95']:.3f}s  on p95={loop['on']['p95']:.3f}s  "
              f"delta={loop['delta_p95']:+.3f}s  overruns={loop['on']['overruns']}  "
              f"shadow p95 = {loop['shadow_p95_share_of_budget']:.2%} of budget",
              file=sys.stderr)
    unexplained = replayed["unexplained_disagreements"]
    print(f"unexplained disagreements: {len(unexplained)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
