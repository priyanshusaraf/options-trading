"""C-P2 — sweep exit parameters over REAL closed trades and rank them.

    .venv/bin/python scripts/exit_sweep.py                     # local ledger
    .venv/bin/python scripts/exit_sweep.py --db /path/prod.db  # a production snapshot
    .venv/bin/python scripts/exit_sweep.py --csv trades.csv    # exported rows
    .venv/bin/python scripts/exit_sweep.py --segment equity_intraday --top 15

Reads only; never writes a ledger. See app/backtest/exit_sweep.py for what this can and
cannot infer from MFE/MAE — in particular, trades that would have touched both a candidate
stop and a candidate target are reported as an explicit band, never resolved by guess.
"""
import argparse
import csv
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.backtest.exit_sweep import (
    ExitParams, ReplayTrade, default_grid, excursion_profile, sweep,
)

_SQL = """
SELECT tradingsymbol, direction, entry_premium, qty, mfe, mae, net_pnl, charges_total,
       segment, exit_reason, exit_time
FROM trades
WHERE exit_time IS NOT NULL
"""


def _f(v):
    return None if v is None or v == "" else float(v)


def _rows_from_db(path: str, segment: str | None, since: str | None, *, owner_id: str | None,
                  broker_account_id: str | None):
    if not owner_id or not broker_account_id:
        raise ValueError("owner and broker account scope are required for database sweeps")
    sql, args = _SQL, []
    sql += " AND owner_id = ? AND broker_account_id = ?"
    args.extend((owner_id, broker_account_id))
    if segment:
        sql += " AND segment = ?"
        args.append(segment)
    if since:
        sql += " AND exit_time >= ?"
        args.append(since)
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return con.execute(sql + " ORDER BY exit_time", args).fetchall()
    finally:
        con.close()


def _rows_from_csv(path: str, segment: str | None, since: str | None):
    out = []
    with open(path, newline="") as fh:
        for r in csv.DictReader(fh):
            if segment and r.get("segment") != segment:
                continue
            if since and (r.get("exit_time") or "") < since:
                continue
            out.append((r["tradingsymbol"], r["direction"], r["entry_premium"], r["qty"],
                        r.get("mfe"), r.get("mae"), r["net_pnl"], r.get("charges_total", 0),
                        r.get("segment"), r.get("exit_reason"), r.get("exit_time")))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(os.path.dirname(__file__), "..",
                                                 "paper_trader.db"))
    ap.add_argument("--csv", default=None, help="read trades from a CSV export instead")
    ap.add_argument("--segment", default=None, help="equity_intraday | options")
    ap.add_argument("--since", default=None, help="only trades exited on/after YYYY-MM-DD")
    ap.add_argument("--top", type=int, default=12)
    ap.add_argument("--owner-id")
    ap.add_argument("--broker-account-id")
    args = ap.parse_args()

    raw = (_rows_from_csv(args.csv, args.segment, args.since) if args.csv
           else _rows_from_db(args.db, args.segment, args.since, owner_id=args.owner_id,
                              broker_account_id=args.broker_account_id))
    trades = [ReplayTrade(tradingsymbol=r[0], direction=r[1], entry_price=float(r[2]),
                          qty=int(r[3]), mfe=_f(r[4]), mae=_f(r[5]), net_pnl=float(r[6]),
                          charges=float(r[7] or 0.0)) for r in raw]
    usable = [t for t in trades if t.has_telemetry]

    print(f"\n{len(trades)} closed trades read"
          f"{f' (segment={args.segment})' if args.segment else ''}"
          f"{f' since {args.since}' if args.since else ''}")
    print(f"{len(usable)} carry MFE/MAE telemetry and can be replayed; "
          f"{len(trades) - len(usable)} predate it and are EXCLUDED.")
    if not usable:
        print("\nNothing to sweep. MFE/MAE landed 2026-07-24 — trades booked before that "
              "carry NULLs and cannot be replayed.")
        return

    prof = excursion_profile(trades)
    print("\nHow far these trades actually travelled (as % of entry notional):")
    print(f"  peak in your favour  — median {prof['mfe_pct_median']:.3%}, "
          f"p75 {prof['mfe_pct_p75']:.3%}, max {prof['mfe_pct_max']:.3%} "
          f"(median ₹{prof['mfe_rs_median']:,.0f})")
    print(f"  worst against you    — median {prof['mae_pct_median']:.3%}, "
          f"p75 {prof['mae_pct_p75']:.3%}, max {prof['mae_pct_max']:.3%} "
          f"(median ₹{prof['mae_rs_median']:,.0f})")
    print("  → any target set above the p75 peak can essentially never fire.")

    actual = sum(t.net_pnl for t in trades)
    actual_usable = sum(t.net_pnl for t in usable)
    print(f"\nActual booked P&L: ₹{actual:,.2f} over all trades, "
          f"₹{actual_usable:,.2f} over the replayable ones (the number to beat).\n")

    rows = sweep(usable, default_grid())
    print(f"{'exit policy':<44} {'P&L':>10} {'band (pess…opt)':>22} {'win%':>6} "
          f"{'amb':>4}  trust")
    print("-" * 100)
    for row in rows[:args.top]:
        d = row.as_dict()
        print(f"{d['params']:<44} {d['total_pnl']:>10,.0f} "
              f"{d['band'][0]:>10,.0f}…{d['band'][1]:<10,.0f} "
              f"{d['win_rate'] * 100:>5.0f}% {d['ambiguous']:>4}  "
              f"{'yes' if d['trustworthy'] else 'NO'}")

    trusted = [r for r in rows if r.trustworthy]
    print("\n" + "=" * 100)
    if not trusted:
        print("NO parameter set is trustworthy on this sample: every candidate's ranking "
              "leans on trades whose stop/target ordering is unknowable, or on a band "
              "wider than its own edge. Do NOT retune from this — collect more trades.")
        return
    best = trusted[0]
    print(f"Best TRUSTWORTHY policy: {best.params.label()}")
    print(f"  P&L ₹{best.total_pnl:,.2f} vs ₹{actual_usable:,.2f} actual "
          f"(delta ₹{best.total_pnl - actual_usable:,.2f}) over {best.trades} trades")
    print(f"  win rate {best.win_rate:.0%}, {best.ambiguous_trades} ambiguous, "
          f"exits: {best.reasons}")
    print(f"\n  Sample is {best.trades} trades. That is small. Treat this as a direction "
          f"to test, not a proven setting.")


if __name__ == "__main__":
    main()
