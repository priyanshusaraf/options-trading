"""
Headless smoke test of the backtest sweep — no Kite, no server.

Forces the mock provider + an isolated DB, runs a small sweep (the seed universe
× a couple of intervals), waits for it to finish, and asserts that results were
stored, metrics are net of charges, and the run reports complete. Run:

    .venv/bin/python scripts/backtest_smoke.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("PT_PROVIDER", "mock")          # force synthetic market
os.environ.setdefault("PT_DB_PATH", "backtest_smoke.db")

from sqlalchemy import select  # noqa: E402

from app.backtest.sweep import start_sweep  # noqa: E402
from app.db.models import BacktestResult, BacktestRun  # noqa: E402
from app.db.session import SessionLocal, init_db  # noqa: E402


def main() -> int:
    init_db(reset=True)
    run_id = start_sweep(scope="liquid", intervals=["15minute", "day"], capital=50_000)

    # poll until the background thread finishes
    for _ in range(120):
        with SessionLocal() as s:
            run = s.get(BacktestRun, run_id)
            if run and run.status != "running":
                break
        time.sleep(0.25)

    with SessionLocal() as s:
        run = s.get(BacktestRun, run_id)
        results = list(s.scalars(select(BacktestResult).where(BacktestResult.run_id == run_id)))

    ok = run.status == "done" and run.done == run.total and len(results) == run.total
    print("=" * 60)
    print(f"  BACKTEST SMOKE — run #{run_id}")
    print(f"  status   : {run.status}   ({run.done}/{run.total} cells)")
    print(f"  universe : {run.note}")
    print(f"  results  : {len(results)}")
    print("-" * 60)
    scored = [r for r in results if not r.error and r.trades > 0]
    for r in sorted(scored, key=lambda r: r.return_pct, reverse=True)[:10]:
        pf = f"{r.profit_factor:.2f}" if r.profit_factor is not None else "  ∞"
        print(f"  {r.instrument_key:11s} {r.interval:9s} "
              f"trades={r.trades:3d} win%={r.win_rate:5.1f} PF={pf:>5s} "
              f"ret={r.return_pct:7.1f}% DD={r.max_drawdown_pct:5.1f}% "
              f"net=₹{r.net_pnl:>10,.0f} chg=₹{r.charges:>7,.0f}")
    # invariant: net must be below gross wherever charges were paid
    bad = [r for r in scored if r.charges > 0 and r.net_pnl >= r.gross_pnl]
    print("-" * 60)
    print(f"  net<gross where charged : {'OK ✓' if not bad else f'VIOLATED ✗ ({len(bad)})'}")
    print(f"  SWEEP {'OK ✓' if ok and not bad else 'FAIL ✗'}")
    print("=" * 60)
    return 0 if (ok and not bad) else 1


if __name__ == "__main__":
    raise SystemExit(main())
