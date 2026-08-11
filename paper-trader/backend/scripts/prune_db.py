"""Age out telemetry and reclaim the disk. Market-closed, flat-book operation.

    .venv/bin/python scripts/prune_db.py                 # DRY-RUN: show sizes + plan
    .venv/bin/python scripts/prune_db.py --commit        # prune
    .venv/bin/python scripts/prune_db.py --commit --vacuum   # prune + shrink the file

The engine also prunes itself once a day with a flat book; this script exists for the
one-off catch-up on a database that has already grown (production was 108 MB on 2026-08-01)
and for the VACUUM, which rewrites the whole file under an exclusive lock and must never
run while the engine holds positions.

The money record — trades, positions, order journal, capital state — is never touched.
"""
import argparse
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import get_settings
from app.db.models import (
    EquitySnapshot, LEGACY_BROKER_ACCOUNT_ID, LEGACY_OWNER_ID, OptionData, Position,
    SignalEvent, Trade)
from app.db.session import SessionLocal
from app.engine.retention import RetentionPolicy, prune, vacuum


def _sizes():
    with SessionLocal() as s:
        scope = {"owner_id": LEGACY_OWNER_ID,
                 "broker_account_id": LEGACY_BROKER_ACCOUNT_ID}
        return {
            "option_data": s.query(OptionData).count(),
            "signal_events": s.query(SignalEvent).filter_by(**scope).count(),
            "equity_snapshots": s.query(EquitySnapshot).filter_by(**scope).count(),
            "trades (never pruned)": s.query(Trade).filter_by(**scope).count(),
            "open positions": s.query(Position).filter_by(**scope).count(),
        }


def _db_mb() -> float:
    p = get_settings().db_path
    try:
        return sum(os.path.getsize(p + sfx) for sfx in ("", "-wal", "-shm")
                   if os.path.exists(p + sfx)) / 1e6
    except OSError:
        return 0.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--vacuum", action="store_true",
                    help="reclaim freed pages (exclusive lock — flat book only)")
    ap.add_argument("--option-data-days", type=int, default=None)
    ap.add_argument("--signal-events-days", type=int, default=None)
    ap.add_argument("--equity-full-days", type=int, default=None)
    args = ap.parse_args()

    s = get_settings()
    policy = RetentionPolicy(
        option_data_days=args.option_data_days if args.option_data_days is not None
        else s.retention_option_data_days,
        signal_events_days=args.signal_events_days if args.signal_events_days is not None
        else s.retention_signal_events_days,
        equity_full_days=args.equity_full_days if args.equity_full_days is not None
        else s.retention_equity_full_days,
        equity_downsample_minutes=s.retention_equity_downsample_minutes,
    )

    before = _sizes()
    print(f"\nDatabase: {_db_mb():,.1f} MB")
    for k, v in before.items():
        print(f"  {k:<28} {v:>10,}")
    print(f"\nPolicy: option_data {policy.option_data_days}d, signal_events "
          f"{policy.signal_events_days}d, equity full {policy.equity_full_days}d then "
          f"1 row / {policy.equity_downsample_minutes} min")

    open_positions = before["open positions"]
    if open_positions:
        print(f"\nREFUSED: {open_positions} open position(s). Prune with a flat book — a "
              f"large DELETE must never contend with position management.")
        return

    if not args.commit:
        print("\nDRY-RUN — re-run with --commit to apply.")
        return

    report = prune(
        dt.datetime.now(), policy, owner_id=LEGACY_OWNER_ID,
        broker_account_id=LEGACY_BROKER_ACCOUNT_ID)
    print("\nRemoved: " + ", ".join(f"{k} −{v:,}" for k, v in report.items()))
    if args.vacuum:
        print("VACUUM (rewriting the file; this takes a while and locks the DB)…")
        vacuum()
    print(f"Database now: {_db_mb():,.1f} MB")


if __name__ == "__main__":
    main()
