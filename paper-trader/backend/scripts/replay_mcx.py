"""
Paper-trading REPLAY — the real live engine on real MCX futures bars.

Runs `EngineRunner` (PaperBroker, armed) exactly along its live path — candle
fetch with `history_days_for`, stale-signal / session / entry-window / expiry-day
guards, option chain via `get_option_chain(inst, min_dte=)`, the picker (OI,
spread, delta ~0.5), adaptive routing, per-strategy `option_exits`, mark-to-market
+ SL/TP/trail, strategy exits, the overnight square-off/hold rules and the capital
ledger — driven by `app/providers/replay.ReplayProvider` over recorded Moneycontrol
MCX 15m prints. It is the closest thing to paper trading without a Kite login.

Clock: one tick 1 minute after every 15m bar start (the bar before it is then a
completed candle, so a signal is seen ~1 min after its candle closes — inside
`max_signal_age_minutes`). While a position is open three more ticks follow inside
the bar (+5/+10/+14 min) walking the bar's OHLC path, so stops/targets can fire
intra-bar. Per tick the engine does what its two live lanes do:
    first tick of a bar : refresh_params, scan_signals, mark_and_exit_positions,
                          process_entries, handle_overnight, snapshot
    intra-bar ticks     : mark_and_exit_positions, process_entries,
                          handle_overnight, snapshot
(no rescan inside a bar: no new completed candle can exist, so the live signal
lane would recompute the identical state.)

Each cell runs in its own process with its own DB (`replay_<strategy>_<inst>.db`,
mock-style reset), one instrument enabled, ₹50k start. After the replay the same
cell is run through the research backtest (`research/commodity/rlib.run_premium`,
same spread, same window) for a live-engine vs backtest comparison.

    .venv/bin/python scripts/replay_mcx.py                    # the 4 default cells, in parallel
    .venv/bin/python scripts/replay_mcx.py --cells spike_fade:NATGASMINI --spread 0.04
    .venv/bin/python scripts/replay_mcx.py --data /path/to/data_mcxreal   (dir holding mcx/)

APPROXIMATIONS (documented, deliberate):
  * Option prices are synthetic: Black-Scholes on trailing 20-day realised vol ×1.15
    (as `backtest/premium.py`), bid/ask = mid ∓ spread/2, OI 5000. PaperBroker fills
    at the LTP (= mid) — so the replay's raw net excludes the spread; a
    spread-adjusted net (−spread/2 per side) is printed next to it.
  * Expiries: futures expiry = the stitched series' roll date where known, else the
    exchange rule (NG: 4 business days before month end; crude: 1 bd before the
    NYMEX WTI expiry). Option expiry = futures expiry − `--opt-expiry-bdays`
    business days (default 2 — MCX energy options expire before their futures).
  * Roll handling: an option is priced off ITS OWN futures month = stitched price +
    the roll gap(s) still ahead of it (`ReplayProvider.underlying_for`), so a held
    option never jumps on a front-month roll. Before the first known roll the
    stitched series IS one later contract (Moneycontrol serves only recent
    contracts), so early-month options are priced off that contract (calendar
    spread ignored).
  * The NIFTY gap guard cannot fire (no NIFTY prints in the replay -> fails open).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time as _time
from collections import Counter
from datetime import date, datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)
sys.path.insert(0, BACKEND)
RESEARCH = os.path.abspath(os.path.join(BACKEND, "..", "research", "commodity"))

DEFAULT_CELLS = ["spike_fade:NATGASMINI", "vwap_band_reversion:NATGASMINI",
                 "spike_fade:CRUDEOILM", "shock_reversal:CRUDEOILM"]
DEFAULT_DATA = os.environ.get("COMMODITY_DATA", os.path.join(RESEARCH, "data", "mcx_real"))
# instrument specs: real MCX option strike steps; lot = mcx_lot_size (units per lot)
SPECS = {"NATGASMINI": dict(name="NATURAL GAS MINI", strike_step=5.0, mock_spot=300, mock_vol=0.5),
         "CRUDEOILM": dict(name="CRUDE OIL MINI", strike_step=50.0, mock_spot=6000, mock_vol=0.35)}


# ── expiry calendar ──────────────────────────────────────────────────────────
def _predicted_fut_expiry(name: str, y: int, m: int) -> date:
    """MCX energy futures expiry rule (as research/commodity/fetch_mcx_moneycontrol)."""
    import pandas as pd
    bd = pd.offsets.BDay()
    first_next = pd.Timestamp(y, m, 1) + pd.offsets.MonthBegin(1)
    if name.startswith("NAT"):
        return (first_next - 4 * bd).date()
    d25 = pd.Timestamp(y, m, 25)
    nymex = d25 - (3 if d25.weekday() < 5 else 4) * bd
    return (nymex - bd).date()


def build_expiries(name: str, df, rolls, opt_bdays: int) -> list[tuple[date, date]]:
    import pandas as pd
    known = {(r.old_expiry.year, r.old_expiry.month): r.old_expiry for r in rolls}
    first, last = df.index.min(), df.index.max() + pd.DateOffset(months=3)
    out = []
    for per in pd.period_range(first.strftime("%Y-%m"), last.strftime("%Y-%m"), freq="M"):
        fut = known.get((per.year, per.month)) or _predicted_fut_expiry(name, per.year, per.month)
        opt = (pd.Timestamp(fut) - opt_bdays * pd.offsets.BDay()).date()
        out.append((opt, fut))
    return out


def load_market(data_root: str, names: list[str]):
    import pandas as pd
    from app.providers.replay import Roll
    frames, rolls = {}, {}
    for n in names:
        frames[n] = pd.read_pickle(os.path.join(data_root, "mcx", f"{n}_15m.pkl"))
        rf = os.path.join(data_root, "mcx", f"{n}_rolls.csv")
        rl = []
        if os.path.exists(rf):
            r = pd.read_csv(rf, parse_dates=["ist", "last_before"])
            for _, x in r.iterrows():
                at = pd.Timestamp(x["ist"]).to_pydatetime()
                rl.append(Roll(at=at, old_expiry=at.date(), gap_pts=float(x["gap_pts"])))
        rolls[n] = rl
    return frames, rolls


# ── one cell (runs in its own process: the DB engine is bound at import) ─────
def run_cell(strategy_key: str, name: str, args) -> dict:
    os.environ["PT_PROVIDER"] = "mock"          # settings-level only: allows the reset;
    os.environ["PT_DB_PATH"] = os.path.join(args.db_dir, f"replay_{strategy_key}_{name}.db")
    os.environ["PT_EXECUTION"] = ""             # paper, always
    os.environ["PT_LIVE_ACK"] = ""
    os.environ["TELEGRAM_BOT_TOKEN"] = ""
    os.environ["TELEGRAM_CHAT_ID"] = ""
    import logging

    import pandas as pd
    from sqlalchemy import select

    import app.providers.factory as factory
    from app.core import instruments as reg
    from app.core.instruments import mcx_lot_size
    from app.core.logging import log
    from app.db.models import InstrumentState, Trade, UniverseInstrument
    from app.db.session import SessionLocal, init_db
    from app.notify.notifier import Notifier
    from app.providers.replay import ReplayProvider
    logging.getLogger("paper_trader").setLevel(logging.ERROR)

    frames, rolls = load_market(args.data, [name])
    df = frames[name]
    if args.start:
        df = df[df.index >= pd.Timestamp(args.start)]
    if args.end:
        df = df[df.index < pd.Timestamp(args.end)]
    frames[name] = df
    exps = {name: build_expiries(name, df, rolls[name], args.opt_expiry_bdays)}
    prov = ReplayProvider(frames, option_expiries=exps, rolls=rolls,
                          spread_pct=args.spread, iv_rv_multiplier=1.15)
    factory._provider = prov                     # the engine's get_provider() -> replay

    init_db(reset=True)
    spec = SPECS[name]
    with SessionLocal() as s:                    # what universe_resolver.add_instrument writes
        s.add(UniverseInstrument(
            key=name, name=spec["name"], segment="MCX", spot_exchange="MCX",
            spot_symbol=name, option_name=name, lot_size=mcx_lot_size(name),
            strike_step=spec["strike_step"], priority=50, has_options=True,
            source="user", on_home=True, active=True,
            mock_spot=spec["mock_spot"], mock_vol=spec["mock_vol"]))
        s.add(InstrumentState(instrument_key=name, enabled=True))
        s.commit()
    reg.load_universe()
    # counterfactual knobs: runtime overrides exactly as the Settings view writes them
    from app.core import runtime_config
    for kv in args.param or []:
        k, v = kv.split("=", 1)
        res = runtime_config.set_override(k, v)
        if "error" in res:
            raise SystemExit(f"--param {kv}: {res['error']}")
    from app.strategy.registry import get_strategy as _gs
    if args.tenor is not None:      # replay-only experiment: a longer-dated option
        _gs(strategy_key).option_tenor_days = args.tenor or None

    from app.engine.runner import EngineRunner, history_days_for
    eng = EngineRunner()
    eng.notifier = Notifier(sender=lambda _t: None)   # never reach Telegram
    for k in list(eng.enabled):
        if k != name:
            eng.set_enabled(k, False)
    eng.set_enabled(name, True)
    eng.set_product(name, "options")
    eng.set_strategy(name, strategy_key)
    eng.set_interval(name, "15minute")
    eng.arm(True)
    inst = reg.get_instrument(name)
    strat = __import__("app.strategy.registry", fromlist=["get_strategy"]).get_strategy(strategy_key)

    # capture the engine's log bus (event + sim time) for skip-reason attribution
    events: list[dict] = []
    log.subscribe(lambda e: events.append({**e, "sim": prov.now()}))

    seen: dict[int, dict] = {}        # signal bar epoch -> {signal, outcome, ...}
    starts = list(df.index)
    t0 = _time.time()
    n_ticks = 0

    def evaluate(full: bool):
        nonlocal n_ticks
        now = prov.now()
        if full:
            eng.refresh_params()
            eng.scan_signals()
        eng.mark_and_exit_positions()
        held = eng.broker.position_for(name)
        st = eng.state.get(name)
        new_bar = None
        if st and st.get("signal") in ("LONG_ENTRY", "SHORT_ENTRY") and st["time"] not in seen:
            new_bar = st["time"]
            seen[new_bar] = {"bar": _ist_str(new_bar), "signal": st["signal"],
                             "seen_at": now.isoformat(timespec="minutes")}
        mark = len(events)
        eng.process_entries()
        if new_bar is not None:
            rec = seen[new_bar]
            sig_dir = "LONG" if rec["signal"] == "LONG_ENTRY" else "SHORT"
            if held is not None:
                rec["outcome"] = ("HELD_SAME_DIR(reinforce)" if held.direction == sig_dir
                                  else "HELD_OPPOSITE(ignored)")
            else:
                pos = eng.broker.position_for(name)
                if pos is not None:
                    rec["outcome"] = "OPENED"
                    rec["symbol"] = pos.tradingsymbol
                else:
                    rec["outcome"] = _skip_reason(events[mark:], name)
        eng.handle_overnight(now)
        eng.broker.snapshot(now)
        n_ticks += 1

    for s in starts:
        prov.set_now(s.to_pydatetime() + timedelta(minutes=1))
        evaluate(True)
        if eng.broker.position_for(name) is not None:
            for off in (5, 10, 14):
                prov.set_now(s.to_pydatetime() + timedelta(minutes=off))
                evaluate(False)

    # ── results ────────────────────────────────────────────────────────────
    with SessionLocal() as s:
        trades = list(s.scalars(select(Trade).order_by(Trade.entry_time)))
    rec = eng.broker.reconcile()
    cap = eng.capital_dict()
    open_pos = eng.broker.position_for(name)
    half = args.spread / 2.0
    tr_out = []
    for t in trades:
        spread_cost = half * (t.entry_premium + t.exit_premium) * t.qty
        tr_out.append({
            "entry": t.entry_time.isoformat(timespec="minutes"),
            "exit": t.exit_time.isoformat(timespec="minutes"),
            "dir": t.direction, "symbol": t.tradingsymbol, "expiry": t.expiry.isoformat(),
            "qty": t.qty, "prem_in": round(t.entry_premium, 2), "prem_out": round(t.exit_premium, 2),
            "spot_in": round(t.entry_spot, 2), "spot_out": round(t.exit_spot or 0, 2),
            "reason": t.exit_reason, "net": round(t.net_pnl, 2),
            "net_spread_adj": round(t.net_pnl - spread_cost, 2),
            "overnight": bool(t.held_overnight), "reinf": t.reinforcements})
    skip_events = Counter(e.get("event") for e in events
                          if e.get("instrument") == name and str(e.get("event", "")).endswith("SKIP"))
    outcomes = Counter(v.get("outcome", "?") for v in seen.values())

    # ── the backtest path on the same cell / window / spread ──────────────
    bt = backtest_cell(strategy_key, name, args, df)
    sigs_bt = bt.pop("signal_bars")
    live_bars = {v["bar"] for v in seen.values()}
    out = {
        "cell": f"{strategy_key} x {name}",
        "window": [str(df.index.min()), str(df.index.max())],
        "history_days": history_days_for(strat, "15minute", eng.settings.history_days),
        "lot": inst.lot_size, "strike_step": inst.strike_step,
        "overrides": list(args.param or []) + ([f"tenor={args.tenor}"] if args.tenor is not None else []),
        "option_tenor_days": getattr(strat, "option_tenor_days", None),
        "ticks": n_ticks, "runtime_s": round(_time.time() - t0, 1),
        "signals_seen": len(seen), "signal_outcomes": dict(outcomes),
        "skip_events_all_ticks": dict(skip_events),
        "signals": sorted(seen.values(), key=lambda v: v["bar"]),
        "trades": tr_out,
        "n_trades": len(tr_out),
        "net": round(sum(t["net"] for t in tr_out), 2),
        "net_spread_adj": round(sum(t["net_spread_adj"] for t in tr_out), 2),
        "exit_reasons": dict(Counter(t["reason"] for t in tr_out)),
        "open_position": (None if open_pos is None else {
            "symbol": open_pos.tradingsymbol, "entry": open_pos.entry_time.isoformat(),
            "unrealized": round(((open_pos.last_premium or open_pos.entry_premium)
                                 - open_pos.entry_premium) * open_pos.qty, 2)}),
        "capital": {k: round(v, 2) if isinstance(v, float) else v for k, v in cap.items()
                    if k in ("initial", "cash", "invested", "realized_pnl", "equity", "open_count")},
        "reconcile": rec, "ledger_ok": abs(rec["diff"]) < 0.01,
        "backtest": bt,
        "signal_match": {
            "backtest_flag_bars": len(sigs_bt),
            "live_seen_bars": len(live_bars),
            "both": len(live_bars & set(sigs_bt)),
            "live_only": sorted(live_bars - set(sigs_bt))[:20],
            "backtest_only": sorted(set(sigs_bt) - live_bars)[:20],
        },
    }
    return out


def _ist_str(epoch: int) -> str:
    from app.core.market_hours import IST
    return datetime.fromtimestamp(epoch, IST).replace(tzinfo=None).isoformat(timespec="minutes")


_MSG_REASONS = [("no option chain", "NO_CHAIN"), ("signal dropped", "CAPITAL"),
                ("MAX POSITIONS", "MAX_POS"), ("DISARMED", "DISARMED"),
                ("no CE contract", "PICKER"), ("no PE contract", "PICKER"),
                ("routing SKIP", "ROUTE_SKIP"), ("expiry too close", "DTE_SKIP"),
                ("DAILY LOSS HALT", "HALT"), ("GAP GUARD", "GAP_GUARD")]


def _skip_reason(evs: list[dict], key: str) -> str:
    for e in evs:
        if e.get("instrument") not in (key, None):
            continue
        ev = str(e.get("event") or "")
        if ev.endswith("SKIP"):
            return ev
        for pat, tag in _MSG_REASONS:
            if pat in e.get("msg", ""):
                return tag
    return "SILENT(no log: already-evaluated / not tradable)"


# ── backtest path (research harness, same data root) ─────────────────────────
def backtest_cell(strategy_key: str, name: str, args, df) -> dict:
    os.environ["COMMODITY_DATA"] = args.data
    sys.path.insert(0, RESEARCH)
    import rlib
    from app.strategy.registry import get_strategy
    strat = get_strategy(strategy_key)
    start = str(df.index.min()) if args.start else None
    end = args.end or None
    trades, dropped = rlib.run_premium(strat, name, "15m",
                                       premium={"premium_spread_pct": args.spread},
                                       start=start, end=end)
    summ = rlib.summarize(trades)
    # the strategy's entry flags on the full frame (what the backtest acts on)
    cs = rlib.candles(name, "15m", start, end)
    from app.backtest.engine import _candles_to_df
    sig = strat.signals(_candles_to_df(list(cs)))
    flag = sig[(sig["longEntry"]) | (sig["shortEntry"])]
    bars = [d.isoformat(timespec="minutes") if hasattr(d, "isoformat") else str(d)
            for d in pd_to_py(flag["date"])]
    fut, _ = rlib.run(strat, name, "15m", start=start, end=end)
    return {
        "n": summ["n"], "net": summ["net"], "pf": summ["pf"], "wr": summ["wr"],
        "dropped_roll_spanning": dropped,
        "exit_reasons": dict(Counter(t.reason for t in trades)),
        "trades": [{"entry": _ist_str(t.entry_time), "exit": _ist_str(t.exit_time),
                    "dir": t.direction, "prem_in": round(t.entry_price, 2),
                    "prem_out": round(t.exit_price, 2), "reason": t.reason,
                    "net": round(t.net_pnl, 2)} for t in trades],
        "futures_path": {"n": len(fut), "net": round(sum(t.net_pnl for t in fut), 0)},
        "signal_bars": bars,
    }


def pd_to_py(series):
    return [x.to_pydatetime() if hasattr(x, "to_pydatetime") else x for x in series]


# ── reporting ────────────────────────────────────────────────────────────────
def print_cell(r: dict) -> None:
    print("=" * 96)
    print(f"  {r['cell']}   window {r['window'][0]} -> {r['window'][1]}")
    print(f"  lot {r['lot']}, strike step {r['strike_step']}, history_days {r['history_days']}, "
          f"{r['ticks']} ticks in {r['runtime_s']}s")
    print(f"  option_tenor_days {r['option_tenor_days']}, overrides {r['overrides'] or 'none (defaults)'}")
    print("-" * 96)
    print(f"  LIVE ENGINE: signals seen {r['signals_seen']}  outcomes {r['signal_outcomes']}")
    print(f"  skip events (all ticks): {r['skip_events_all_ticks']}")
    for v in r["signals"]:
        print(f"     signal bar {v['bar']}  {v['signal']:11s} seen {v['seen_at'][11:]}  -> "
              f"{v.get('outcome')}{'  ' + v['symbol'] if v.get('symbol') else ''}")
    print(f"  trades {r['n_trades']}  net ₹{r['net']:,.0f}  (spread-adjusted ₹{r['net_spread_adj']:,.0f})"
          f"  exits {r['exit_reasons']}")
    for t in r["trades"]:
        print(f"     {t['entry']} -> {t['exit']}  {t['dir']:5s} {t['symbol']:22s} "
              f"{t['prem_in']:>8.2f} -> {t['prem_out']:>8.2f}  spot {t['spot_in']:.1f}->{t['spot_out']:.1f}"
              f"  {t['reason']:20s} ₹{t['net']:>9,.0f}{'  ON' if t['overnight'] else ''}"
              f"{'  R' + str(t['reinf']) if t['reinf'] else ''}")
    if r["open_position"]:
        print(f"  OPEN at end: {r['open_position']}")
    c, rec = r["capital"], r["reconcile"]
    print(f"  capital: cash ₹{c['cash']:,.2f}  realized ₹{c['realized_pnl']:,.2f}  "
          f"equity ₹{c['equity']:,.2f}  open {c['open_count']}")
    print(f"  RECONCILE cash {rec['cash']:,.2f} vs expected {rec['expected_cash']:,.2f} "
          f"(diff {rec['diff']:+.4f})  LEDGER {'OK' if r['ledger_ok'] else 'MISMATCH'}")
    b = r["backtest"]
    print("-" * 96)
    print(f"  BACKTEST (rlib.run_premium, same spread/window): n={b['n']} net ₹{b['net']:,.0f} "
          f"pf={b['pf']} wr={b['wr']} dropped(roll-spanning)={b['dropped_roll_spanning']} "
          f"exits {b['exit_reasons']}   futures path n={b['futures_path']['n']} "
          f"₹{b['futures_path']['net']:,.0f}")
    for t in b["trades"]:
        print(f"     {t['entry']} -> {t['exit']}  {t['dir']:5s} {t['prem_in']:>8.2f} -> "
              f"{t['prem_out']:>8.2f}  {t['reason']:20s} ₹{t['net']:>9,.0f}")
    m = r["signal_match"]
    print(f"  SIGNALS: backtest flag bars {m['backtest_flag_bars']}, live seen {m['live_seen_bars']}, "
          f"both {m['both']}")
    if m["live_only"]:
        print(f"     live-only: {m['live_only']}")
    if m["backtest_only"]:
        print(f"     backtest-only: {m['backtest_only']}")
    print("=" * 96 + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--cells", nargs="*", default=DEFAULT_CELLS, help="strategy:INSTRUMENT ...")
    ap.add_argument("--data", default=DEFAULT_DATA, help="data root holding mcx/<NAME>_15m.pkl")
    ap.add_argument("--spread", type=float, default=0.02, help="option round-trip spread (fraction)")
    ap.add_argument("--opt-expiry-bdays", type=int, default=2,
                    help="option expiry = futures expiry minus this many business days")
    ap.add_argument("--start", default=None)
    ap.add_argument("--end", default=None)
    ap.add_argument("--db-dir", default=BACKEND)
    ap.add_argument("--json-dir", default=None, help="write <cell>.json results here")
    ap.add_argument("--param", action="append", default=[],
                    help="runtime override key=value (e.g. intraday_block_weekday=-1); repeatable")
    ap.add_argument("--tenor", type=int, default=None,
                    help="experiment: override the strategy's option_tenor_days (0 = nearest)")
    ap.add_argument("--cell", default=None, help=argparse.SUPPRESS)   # internal: run one cell
    ap.add_argument("--serial", action="store_true", help="run cells one after another")
    args = ap.parse_args()

    if args.cell:
        sk, nm = args.cell.split(":")
        res = run_cell(sk, nm, args)
        print("@@RESULT@@" + json.dumps(res, default=str))
        return 0 if res["ledger_ok"] else 1

    # driver: one subprocess per cell (each binds its own DB at import)
    base = [sys.executable, os.path.abspath(__file__), "--data", args.data,
            "--spread", str(args.spread), "--opt-expiry-bdays", str(args.opt_expiry_bdays),
            "--db-dir", args.db_dir]
    for kv in args.param:
        base += ["--param", kv]
    if args.tenor is not None:
        base += ["--tenor", str(args.tenor)]
    if args.start:
        base += ["--start", args.start]
    if args.end:
        base += ["--end", args.end]
    procs = []
    results = []
    for c in args.cells:
        p = subprocess.Popen(base + ["--cell", c], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, cwd=BACKEND)
        procs.append((c, p))
        if args.serial:
            procs[-1] = (c, p, *p.communicate())
    ok = True
    for item in procs:
        c, p = item[0], item[1]
        out, err = (item[2], item[3]) if len(item) > 2 else p.communicate()
        line = next((ln for ln in out.splitlines() if ln.startswith("@@RESULT@@")), None)
        if line is None:
            print(f"cell {c} FAILED (exit {p.returncode}):\n{err[-4000:]}")
            ok = False
            continue
        r = json.loads(line[len("@@RESULT@@"):])
        results.append(r)
        print_cell(r)
        ok &= r["ledger_ok"]
        if args.json_dir:
            os.makedirs(args.json_dir, exist_ok=True)
            with open(os.path.join(args.json_dir, c.replace(":", "_") + ".json"), "w") as f:
                json.dump(r, f, indent=1, default=str)
    print("SUMMARY")
    for r in results:
        b = r["backtest"]
        print(f"  {r['cell']:34s} LIVE n={r['n_trades']:3d} ₹{r['net']:>9,.0f} "
              f"(spread-adj ₹{r['net_spread_adj']:>9,.0f})  ledger {'OK' if r['ledger_ok'] else 'BAD'}"
              f"  | BACKTEST n={b['n']:3d} ₹{b['net']:>9,.0f}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
