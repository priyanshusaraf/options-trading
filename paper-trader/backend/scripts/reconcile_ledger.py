"""#19 — re-anchor capital_state to the real Kite account. Run FLAT (no open positions),
post-close, before re-arming — the internal ledger/baseline drift from the real account
over a live session (2026-07-03: internal cash ₹47,159 / baseline ₹23,706 vs a real
₹22,757 account) and should be reset to reality.

  .venv/bin/python scripts/reconcile_ledger.py                    # DRY-RUN: show the plan
  .venv/bin/python scripts/reconcile_ledger.py --equity 22757.30  # use a manual equity
  .venv/bin/python scripts/reconcile_ledger.py --commit           # back up + write

Refuses unless the book is flat. --commit writes a rollback .sql backup first.
"""
import argparse
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.db.models import CapitalState, Position
from app.db.session import SessionLocal
from app.engine.ledger_reconcile import plan_reanchor

HERE = os.path.dirname(os.path.abspath(__file__))


def _real_equity_from_kite():
    try:
        from kiteconnect import KiteConnect

        from app.core.config import get_settings
        s = get_settings()
        tok = json.load(open(os.path.join(HERE, "..", "access_token.json")))
        k = KiteConnect(api_key=s.kite_api_key or os.environ.get("KITE_API_KEY", ""))
        k.set_access_token(tok["access_token"])
        return float(k.margins(segment="equity")["net"])
    except Exception as e:
        print(f"  (could not read live Kite equity: {e})")
        return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--equity", type=float, default=None,
                    help="real account equity to anchor to (else fetched from Kite margins)")
    ap.add_argument("--commit", action="store_true", help="apply the change (default: dry-run)")
    args = ap.parse_args()

    with SessionLocal() as sess:
        cap = sess.get(CapitalState, 1)
        if cap is None:
            print("no capital_state row — nothing to reconcile")
            return
        open_positions = list(sess.scalars(select(Position)))
        open_cost = sum(p.entry_cost for p in open_positions)
        equity = args.equity if args.equity is not None else _real_equity_from_kite()
        if equity is None:
            print("no equity available — pass --equity <value> (the real account net funds)")
            return

        try:
            new, notes = plan_reanchor(
                real_equity=equity, cash=cap.cash, initial_capital=cap.initial_capital,
                realized_pnl=cap.realized_pnl, account_baseline=cap.account_baseline,
                open_entry_cost=open_cost)
        except ValueError as e:
            print(f"REFUSED: {e}")
            if open_positions:
                print(f"  book still holds {len(open_positions)} position(s): "
                      f"{', '.join(p.instrument_key for p in open_positions)}")
            return

        print(f"Real account equity: ₹{equity:,.2f}   (book is flat)\n")
        print("Re-anchor plan (capital_state id=1):")
        for n in notes:
            print("  " + n)

        if not args.commit:
            print("\nDRY-RUN — re-run with --commit to apply.")
            return

        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = os.path.join(HERE, "..", f"ledger-backup-pre-reanchor-{stamp}.sql")
        with open(backup, "w") as f:
            f.write("-- rollback capital_state to its pre-re-anchor values\n"
                    f"UPDATE capital_state SET initial_capital={cap.initial_capital}, "
                    f"cash={cap.cash}, realized_pnl={cap.realized_pnl}, "
                    f"account_baseline={cap.account_baseline if cap.account_baseline is not None else 'NULL'} "
                    "WHERE id=1;\n")
        cap.initial_capital = new["initial_capital"]
        cap.cash = new["cash"]
        cap.realized_pnl = new["realized_pnl"]
        cap.account_baseline = new["account_baseline"]
        sess.commit()
        print(f"\n✓ committed. Rollback backup: {os.path.abspath(backup)}")
        print("  Restart the backend so the runner reloads the reconciled ledger before re-arming.")


if __name__ == "__main__":
    main()
