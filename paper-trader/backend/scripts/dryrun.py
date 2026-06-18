"""
Headless end-to-end proof of the engine — no server, no Kite, no browser.

Runs the real EngineRunner.tick() against the MockProvider for N steps, then
prints what happened and (critically) reconciles the capital ledger:

    cash == initial_capital + realized_pnl − Σ(open position entry_cost)

If that invariant holds to the paisa, the money math is sound. Run:

    .venv/bin/python scripts/dryrun.py [ticks]
"""
import os
import sys

# make `app` importable when this file is run directly as a script
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# isolate the dry-run in its own DB, configured before app import
os.environ.setdefault("PT_DB_PATH", "dryrun.db")
os.environ.setdefault("PT_MOCK_TICK_SECONDS", "0")

from sqlalchemy import func, select  # noqa: E402

from app.db.models import EquitySnapshot, SignalEvent, Trade  # noqa: E402
from app.db.session import SessionLocal, init_db  # noqa: E402
from app.engine.runner import EngineRunner  # noqa: E402


def main() -> int:
    ticks = int(sys.argv[1]) if len(sys.argv) > 1 else 600
    init_db(reset=True)
    eng = EngineRunner()

    for _ in range(ticks):
        eng.tick()
        if not eng.provider.advance():
            break

    with SessionLocal() as s:
        trades = list(s.scalars(select(Trade)))
        n_signals = s.scalar(select(func.count()).select_from(SignalEvent))
        n_snaps = s.scalar(select(func.count()).select_from(EquitySnapshot))

    wins = [t for t in trades if t.win]
    losses = [t for t in trades if not t.win]
    net = sum(t.net_pnl for t in trades)
    charges = sum(t.charges_total for t in trades)
    gross = sum(t.gross_pnl for t in trades)

    cap = eng.capital_dict()
    rec = eng.broker.reconcile()

    print("\n" + "=" * 64)
    print(f"  DRY RUN — {eng.tick_count} ticks, provider={eng.provider.name}")
    print("=" * 64)
    print(f"  entry signals recorded : {n_signals}")
    print(f"  equity snapshots       : {n_snaps}")
    print(f"  trades closed          : {len(trades)}")
    if trades:
        wr = 100 * len(wins) / len(trades)
        avg_w = sum(t.net_pnl for t in wins) / len(wins) if wins else 0
        avg_l = sum(t.net_pnl for t in losses) / len(losses) if losses else 0
        expectancy = net / len(trades)
        print(f"  win rate               : {wr:.1f}%  ({len(wins)}W / {len(losses)}L)")
        print(f"  avg win / avg loss     : ₹{avg_w:,.0f} / ₹{avg_l:,.0f}")
        print(f"  expectancy / trade     : ₹{expectancy:,.0f}")
        print(f"  gross P&L              : ₹{gross:,.0f}")
        print(f"  charges paid           : ₹{charges:,.0f}")
        print(f"  net P&L                : ₹{net:,.0f}")
        # exit-reason + per-instrument breakdown
        reasons: dict[str, int] = {}
        per_inst: dict[str, float] = {}
        for t in trades:
            reasons[t.exit_reason] = reasons.get(t.exit_reason, 0) + 1
            per_inst[t.instrument_key] = per_inst.get(t.instrument_key, 0) + t.net_pnl
        print(f"  exit reasons           : {reasons}")
        print("  per-instrument net P&L :")
        for k, v in sorted(per_inst.items(), key=lambda x: -x[1]):
            print(f"      {k:11s} ₹{v:>10,.0f}")
    print("-" * 64)
    print(f"  initial capital        : ₹{cap['initial']:,.2f}")
    print(f"  cash                   : ₹{cap['cash']:,.2f}")
    print(f"  invested (open cost)   : ₹{cap['invested']:,.2f}")
    print(f"  realized P&L           : ₹{cap['realized_pnl']:,.2f}")
    print(f"  equity (MTM)           : ₹{cap['equity']:,.2f}")
    print(f"  open positions         : {cap['open_count']}")
    print("-" * 64)
    print(f"  RECONCILE cash vs expected: {rec['cash']:,.2f} vs "
          f"{rec['expected_cash']:,.2f}  (diff {rec['diff']:+.4f})")
    ok = abs(rec["diff"]) < 0.01
    print(f"  LEDGER {'OK ✓' if ok else 'MISMATCH ✗'}")
    print("=" * 64 + "\n")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
