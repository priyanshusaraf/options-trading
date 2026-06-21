"""
Backtest performance metrics — pure functions over a list of closed trades.

Every metric is computed on **net** P&L (after the full Zerodha charge stack), so
the equity curve and the headline numbers reflect what the strategy would really
have kept, not a charge-free fantasy. This is the whole point of the sweep: find
edges that survive commissions, not smooth curves that don't.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BTTrade:
    """One closed backtest trade on the underlying."""
    direction: str          # "LONG" | "SHORT"
    entry_time: int         # epoch seconds
    entry_price: float
    exit_time: int
    exit_price: float
    qty: int
    gross_pnl: float
    charges: float
    net_pnl: float
    reason: str             # "STRATEGY_EXIT" | "OPEN_AT_END" (still open at last candle)
    bars_held: int

    @property
    def win(self) -> bool:
        return self.net_pnl > 0

    @property
    def return_pct(self) -> float:
        notional = self.entry_price * self.qty
        return (self.net_pnl / notional) if notional else 0.0

    def to_dict(self) -> dict:
        return {
            "direction": self.direction,
            "entry_time": self.entry_time,
            "entry_price": round(self.entry_price, 2),
            "exit_time": self.exit_time,
            "exit_price": round(self.exit_price, 2),
            "qty": self.qty,
            "gross_pnl": round(self.gross_pnl, 2),
            "charges": round(self.charges, 2),
            "net_pnl": round(self.net_pnl, 2),
            "return_pct": round(self.return_pct, 4),
            "reason": self.reason,
            "bars_held": self.bars_held,
            "win": self.win,
        }


@dataclass
class BTMetrics:
    trades: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0          # %
    net_pnl: float = 0.0
    gross_pnl: float = 0.0
    charges: float = 0.0
    return_pct: float = 0.0        # compounding return on capital DEPLOYED (no leverage), %
    profit_factor: float | None = None   # Σwin / Σ|loss|; None if undefined
    expectancy: float = 0.0        # net per trade
    avg_win: float = 0.0
    avg_loss: float = 0.0
    max_drawdown_pct: float = 0.0  # worst peak-to-trough on the equity curve, %
    max_drawdown_abs: float = 0.0
    cagr: float | None = None      # %, None if duration too short
    # ── smoothness / quality (the owner ranks curves on these, not raw return) ──
    calmar: float | None = None         # CAGR ÷ maxDD% — annualised return per unit of pain
    consistency: float | None = None    # mean ÷ std of per-trade returns (Sharpe-like)
    max_consec_losses: int = 0          # longest losing streak (tail-pain proxy)
    time_underwater_pct: float = 0.0    # % of the curve spent below its prior peak
    equity_curve: list[dict] = field(default_factory=list)  # [{time, value}]

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        for k in ("net_pnl", "gross_pnl", "charges", "expectancy", "avg_win",
                  "avg_loss", "max_drawdown_abs"):
            d[k] = round(d[k], 2)
        for k in ("win_rate", "return_pct", "max_drawdown_pct"):
            d[k] = round(d[k], 2)
        d["time_underwater_pct"] = round(self.time_underwater_pct, 1)
        if self.profit_factor is not None:
            d["profit_factor"] = round(self.profit_factor, 3)
        if self.cagr is not None:
            d["cagr"] = round(self.cagr, 2)
        if self.calmar is not None:
            d["calmar"] = round(self.calmar, 3)
        if self.consistency is not None:
            d["consistency"] = round(self.consistency, 3)
        return d


def _max_drawdown(curve: list[float]) -> tuple[float, float]:
    """Worst peak-to-trough decline on an equity series. Returns (abs, pct)."""
    peak = curve[0] if curve else 0.0
    mdd_abs = 0.0
    mdd_pct = 0.0
    for v in curve:
        peak = max(peak, v)
        dd = peak - v
        if dd > mdd_abs:
            mdd_abs = dd
            mdd_pct = (dd / peak * 100) if peak > 0 else 0.0
    return mdd_abs, mdd_pct


def compute_metrics(trades: list[BTTrade], initial_capital: float) -> BTMetrics:
    m = BTMetrics()
    m.trades = len(trades)
    if not trades:
        return m

    wins = [t for t in trades if t.win]
    losses = [t for t in trades if not t.win]
    m.wins, m.losses = len(wins), len(losses)
    m.win_rate = 100.0 * m.wins / m.trades
    m.net_pnl = sum(t.net_pnl for t in trades)        # absolute rupees (raw P&L still matters)
    m.gross_pnl = sum(t.gross_pnl for t in trades)
    m.charges = sum(t.charges for t in trades)
    m.expectancy = m.net_pnl / m.trades
    m.avg_win = sum(t.net_pnl for t in wins) / len(wins) if wins else 0.0
    m.avg_loss = sum(t.net_pnl for t in losses) / len(losses) if losses else 0.0

    gross_profit = sum(t.net_pnl for t in wins)
    gross_loss = -sum(t.net_pnl for t in losses)
    m.profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else None

    # Equity curve — leverage-free, COMPOUNDING the per-trade return on the
    # position's own NOTIONAL (net P&L / (entry_price × qty)), NOT a flat ₹50k base.
    # This is the honest curve: capital deployed == the position you actually take
    # (the owner buys the underlying outright, no futures leverage), so one F&O lot
    # can never imply a >100% account swing and curves are directly comparable
    # across instruments regardless of price/lot size. return_pct/maxDD%/CAGR are
    # therefore anchor-independent; `initial_capital` is only the curve's index base.
    base = initial_capital if initial_capital else 100_000.0
    equity = base
    curve_vals = [equity]
    m.equity_curve = [{"time": trades[0].entry_time, "value": round(equity, 2)}]
    for t in trades:
        r = max(t.return_pct, -1.0)   # a fully-funded (un-leveraged) position can't lose >100%
        equity = max(0.0, equity * (1.0 + r))
        curve_vals.append(equity)
        m.equity_curve.append({"time": t.exit_time, "value": round(equity, 2)})
    m.return_pct = (curve_vals[-1] / base - 1.0) * 100.0
    m.max_drawdown_abs, m.max_drawdown_pct = _max_drawdown(curve_vals)

    # CAGR over the spanned period (on the same compounding basis)
    span_secs = trades[-1].exit_time - trades[0].entry_time
    years = span_secs / (365.25 * 86400)
    final = curve_vals[-1]
    if years >= 0.05 and final > 0 and base > 0:
        m.cagr = ((final / base) ** (1 / years) - 1) * 100.0

    # ── smoothness / quality metrics ──
    # Longest losing streak — a run of small losses is exactly what kills an
    # option buyer (each is a near-total premium loss), so it's worth surfacing.
    streak = m.max_consec_losses = 0
    for t in trades:
        streak = streak + 1 if not t.win else 0
        m.max_consec_losses = max(m.max_consec_losses, streak)
    # Time underwater: share of curve points sitting below the running peak —
    # a low number means the curve spends little time in drawdown (smooth).
    peak = curve_vals[0]
    under = 0
    for v in curve_vals[1:]:
        peak = max(peak, v)
        if v < peak:
            under += 1
    m.time_underwater_pct = (100.0 * under / (len(curve_vals) - 1)) if len(curve_vals) > 1 else 0.0
    # Consistency: mean ÷ std of per-trade returns (Sharpe-like). Higher = more
    # uniform trade outcomes = smoother curve, independent of raw magnitude.
    rets = [t.return_pct for t in trades]
    if len(rets) >= 2:
        mean = sum(rets) / len(rets)
        sd = (sum((r - mean) ** 2 for r in rets) / len(rets)) ** 0.5
        m.consistency = (mean / sd) if sd > 0 else None
    # Calmar: annualised return per unit of max drawdown — the single ratio that
    # best captures "return earned per unit of pain", which is what to optimise.
    if m.cagr is not None and m.max_drawdown_pct > 0:
        m.calmar = m.cagr / m.max_drawdown_pct
    return m
