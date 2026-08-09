#!/usr/bin/env python
"""Tiered sweep benchmark — Task 7 of the scalable-backtest-sweep plan.

Deterministic and offline. Drives the REAL `sweep.start_sweep` against a synthetic
provider, so what it measures is the shipped code path rather than a model of it.

Three things this reports that a wall-clock number alone cannot:

  * **stage separation** — acquisition, identity, simulation and persistence are timed
    apart, because they are bounded by different things and only one of them is ours to
    optimise. Provider I/O is Kite's rate limit; persistence is SQLite; simulation is
    Python.
  * **operation counts** — provider reads, store reads/writes and write transactions.
    A speed claim with an unbounded operation count underneath it is not a speed claim.
  * **cold / refresh-warm / pinned-warm**, measured separately. Those are three different
    promises (see the "Truthful warm modes" section of the sweep design) and collapsing
    them is exactly how a "zero provider reads" claim stops being true.

Usage, from `backend/`:

    PT_PROVIDER=mock PT_EXECUTION=paper PT_DISABLE_DOTENV=1 \\
        .venv/bin/python scripts/sweep_benchmark.py --tier 100x5
    ... --tier 1000x5 --workers 4
    ... --tier all --bars 5000 --json out.json

Tiers are named by the plan's shape (instruments x intervals). Real universe sizing —
NSE cash is 16,000 cells / 78.1M bars — is in
`docs/superpowers/specs/2026-08-10-full-universe-backtest-design.md` §2; this harness
measures the per-cell cost that projection multiplies.

NOTE: multiprocess workers require this module to be import-safe, hence the
`if __name__ == "__main__"` guard at the bottom. A spawn pool re-imports the entry
module in every child; without the guard you get a recursive process explosion.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TIERS = {
    "100x5": (100, 5),
    "1000x5": (1_000, 5),
    "10000x5": (10_000, 5),
}


class _Recorder:
    """Counts the operations a speed number has to be honest about."""

    def __init__(self) -> None:
        self.provider_reads: list[tuple] = []
        self.store_reads = 0
        self.store_writes = 0
        self.write_txns = 0


def _synthetic_candles(n_bars: int, seed: int):
    """A deterministic OHLCV series that is NOT representable in two decimals.

    The mock provider rounds to 2dp, which once made a bit-identity gate vacuous —
    a worker doing `round(x, 2)` produced identical numbers and nothing failed. Any
    benchmark that also feeds numerical comparisons must use full-mantissa prices.
    """
    from app.providers.base import Candle

    base = dt.datetime(2026, 1, 1, 9, 15)
    out, px = [], 100.0 + seed * 0.0000173
    for i in range(n_bars):
        px = px * (1.0 + ((i * 7919 + seed * 104729) % 1000 - 500) / 1_000_000.0)
        hi, lo = px * 1.0021734, px * 0.9979112
        out.append(Candle(ts=base + dt.timedelta(minutes=15 * i), open=px, high=hi,
                          low=lo, close=px * 1.0003119, volume=1000.0 + i))
    return out


def _timed(fn):
    t0 = time.perf_counter()
    out = fn()
    return out, (time.perf_counter() - t0)


def _percentiles(samples: list[float]) -> dict:
    if not samples:
        return {}
    s = sorted(samples)
    def pct(p):
        k = max(0, min(len(s) - 1, int(round((p / 100.0) * (len(s) - 1)))))
        return s[k]
    return {"p50": pct(50), "p95": pct(95), "p99": pct(99),
            "min": s[0], "max": s[-1], "mean": statistics.fmean(s)}


def measure_stages(n_bars: int, repeats: int) -> dict:
    """Per-cell stage costs, measured directly rather than inferred from a total."""
    from app.backtest.engine import compute_signals, prepare_signal_frame, simulate
    from app.backtest.identity import ordered_dataset_address
    from app.backtest.premium import simulate_premium
    from app.core.instruments import get_instrument
    from app.core.market_hours import ist_epoch
    from app.providers.mock import MockProvider
    from app.strategy.registry import get_strategy

    inst, strat, provider = get_instrument("NIFTY"), get_strategy("trend_impulse_v3"), MockProvider()
    candles = tuple(_synthetic_candles(n_bars, seed=1))
    first_ts, last_ts = ist_epoch(candles[0].ts), ist_epoch(candles[-1].ts)
    params = dict(strat.default_params)

    stages: dict[str, list[float]] = {k: [] for k in
                                      ("identity", "frame", "signals", "simulate", "premium")}
    for _ in range(repeats):
        _, t = _timed(lambda: ordered_dataset_address(
            candles, provider=provider, instrument=inst, interval="15minute",
            requested_window={"lookback_days": None, "start": None, "end": None},
            effective_window={"first_ts": first_ts, "last_ts": last_ts,
                              "bars": len(candles), "clamped": False}))
        stages["identity"].append(t * 1000)

        frame, t = _timed(lambda: prepare_signal_frame(candles))
        stages["frame"].append(t * 1000)

        sig, t = _timed(lambda: compute_signals(candles, strat, params, frame=frame))
        stages["signals"].append(t * 1000)

        _, t = _timed(lambda: simulate(candles, inst, "15minute", capital=50_000.0,
                                       strategy=strat, params=params, signals=sig))
        stages["simulate"].append(t * 1000)

        try:
            _, t = _timed(lambda: simulate_premium(candles, inst, "15minute", strategy=strat,
                                                   params=params, capital=50_000.0, signals=sig))
            stages["premium"].append(t * 1000)
        except Exception as exc:                                    # noqa: BLE001
            stages["premium"].append(float("nan"))
            print(f"  (premium replay unavailable on this series: {exc})")

    return {k: _percentiles([v for v in vals if v == v]) for k, vals in stages.items()}


def project(stage_stats: dict, cells: int, bars: int) -> dict:
    """Multiply the measured per-cell cost out to a tier. Stated as a PROJECTION,
    never as a measurement — the distinction is why the earlier 16-core estimate was
    wrong (see the design note: the parent thread, not the cells, was the ceiling)."""
    per_cell_ms = sum(s.get("p50", 0.0) for s in stage_stats.values())
    compute_s = per_cell_ms * cells / 1000.0
    io_s = cells * 0.40                       # Kite historical throttle, per connection
    return {
        "cells": cells, "bars_per_cell": bars, "total_bars": cells * bars,
        "per_cell_ms_p50": round(per_cell_ms, 3),
        "compute_serial_s": round(compute_s, 1),
        "provider_io_floor_s": round(io_s, 1),
        "cold_serial_s": round(compute_s + io_s, 1),
        "warm_pinned_serial_s": round(compute_s, 1),
        "store_bytes_est": cells * bars * 38,
    }


def measure_sweep(n_instruments: int, intervals: list[str], workers: int) -> dict:
    """Drive a REAL sweep and count the operations underneath the wall time.

    A projection says how long the arithmetic takes. This says how many provider reads
    and write transactions it took to get there — the two numbers that decide whether a
    tier is bounded or merely fast on a small sample.
    """
    from sqlalchemy import event
    from app.backtest import sweep as sweep_mod
    from app.db.session import SessionLocal, engine, init_db
    from app.db.models import BacktestResult
    from sqlalchemy import select

    class _CountingProvider:
        """Wraps the mock and counts candle reads."""

        def __init__(self):
            from app.providers.mock import MockProvider
            self._inner = MockProvider()
            self.candle_reads = []

        def __getattr__(self, name):
            return getattr(self._inner, name)

        def get_candles(self, inst, interval, days, end=None):
            self.candle_reads.append((inst.key, interval))
            return self._inner.get_candles(inst, interval, days, end=end)

    init_db(reset=True)
    provider = _CountingProvider()
    txns = {"n": 0}

    @event.listens_for(engine, "commit")
    def _count_commit(_conn):
        txns["n"] += 1

    from app.backtest.universe import liquid_universe
    universe = [i.key for i in liquid_universe(provider)][:n_instruments]

    t0 = time.perf_counter()
    run_id = sweep_mod.start_sweep(scope="liquid", intervals=intervals,
                                   instruments=universe, provider=provider,
                                   workers=workers)
    sweep_mod._join()
    wall = time.perf_counter() - t0
    event.remove(engine, "commit", _count_commit)

    with SessionLocal() as session:
        rows = list(session.scalars(
            select(BacktestResult).where(BacktestResult.run_id == run_id)))
    cells = len(rows)
    return {
        "cells": cells, "wall_s": round(wall, 3),
        "ms_per_cell": round(wall * 1000 / max(1, cells), 2),
        "provider_reads": len(provider.candle_reads),
        "unique_datasets": len(set(provider.candle_reads)),
        "write_transactions": txns["n"],
        "txn_budget": -(-cells // 10) + 1,
        "workers": workers,
        "errors": sum(1 for r in rows if r.error),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tier", default="100x5",
                    choices=[*TIERS, "all"], help="which tier to project")
    ap.add_argument("--bars", type=int, default=5000,
                    help="bars per cell; 5,000 is a real 15-minute/200-day window")
    ap.add_argument("--repeats", type=int, default=12)
    ap.add_argument("--json", default="", help="also write results to this path")
    ap.add_argument("--sweep", type=int, default=0,
                    help="also drive a REAL sweep over N instruments and count operations")
    ap.add_argument("--workers", type=int, default=1)
    args = ap.parse_args()

    print(f"stage measurement: {args.bars:,} bars/cell, {args.repeats} repeats\n")
    stages = measure_stages(args.bars, args.repeats)

    print(f"{'stage':<12}{'p50 ms':>10}{'p95 ms':>10}{'p99 ms':>10}{'min ms':>10}")
    print("-" * 52)
    for name, s in stages.items():
        if not s:
            continue
        print(f"{name:<12}{s['p50']:>10.3f}{s['p95']:>10.3f}{s['p99']:>10.3f}{s['min']:>10.3f}")
    total = sum(s.get("p50", 0.0) for s in stages.values())
    print("-" * 52)
    print(f"{'TOTAL':<12}{total:>10.3f}\n")

    tiers = list(TIERS) if args.tier == "all" else [args.tier]
    results = {"bars_per_cell": args.bars, "stages": stages, "tiers": {}}
    for name in tiers:
        insts, intervals = TIERS[name]
        p = project(stages, insts * intervals, args.bars)
        results["tiers"][name] = p
        print(f"{name:>10}: {p['cells']:>7,} cells  {p['total_bars']:>14,} bars  "
              f"compute {p['compute_serial_s']:>9,.0f}s  "
              f"I/O floor {p['provider_io_floor_s']:>9,.0f}s  "
              f"cold {p['cold_serial_s']/3600:>6.2f}h  "
              f"store {p['store_bytes_est']/1e9:>6.1f}GB")

    print("\nProjections multiply a measured per-cell cost. They are NOT a measured "
          "end-to-end tier:\nthe parent thread's own work, not the cells, set the ceiling "
          "when fan-out was measured.\nSee the design note before quoting these as capacity.")

    if args.sweep:
        print(f"\nend-to-end sweep: {args.sweep} instruments, workers={args.workers}")
        m = measure_sweep(args.sweep, ["15minute", "day"], args.workers)
        results["sweep"] = m
        print(f"  cells               {m['cells']:>8,}   errors {m['errors']}")
        print(f"  wall                {m['wall_s']:>8.3f}s  ({m['ms_per_cell']} ms/cell)")
        print(f"  provider reads      {m['provider_reads']:>8,}   "
              f"unique datasets {m['unique_datasets']:,}")
        print(f"  write transactions  {m['write_transactions']:>8,}   "
              f"budget {m['txn_budget']:,}")
        ok = m["write_transactions"] <= m["txn_budget"]
        print(f"  transaction budget  {'OK' if ok else 'EXCEEDED'}")

    if args.json:
        with open(args.json, "w") as fh:
            json.dump(results, fh, indent=2, default=float)
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":       # required: a spawn pool re-imports this module
    raise SystemExit(main())
