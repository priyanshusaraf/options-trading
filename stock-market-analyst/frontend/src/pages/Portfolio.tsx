import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { portfolioApi } from "../lib/api";
import { cn, fmt, signClass } from "../lib/utils";
import { Plus, Trash2, TrendingUp, TrendingDown, AlertCircle } from "lucide-react";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";

const SECTOR_COLORS = [
  "#4e9eff", "#00d17a", "#ff4f5a", "#f5c842", "#9b6dff",
  "#00c0ff", "#ff8c42", "#c084fc", "#34d399", "#f87171",
];

export function Portfolio() {
  const qc = useQueryClient();
  const [symbol, setSymbol] = useState("");
  const [qty, setQty] = useState("");
  const [avgCost, setAvgCost] = useState("");
  const [exchange, setExchange] = useState("NSE");

  const { data, isLoading } = useQuery({
    queryKey: ["portfolio"],
    queryFn: portfolioApi.get,
    refetchInterval: 60000,
  });

  const { data: kiteStatus } = useQuery({
    queryKey: ["kite-status"],
    queryFn: portfolioApi.kiteStatus,
  });

  const addMutation = useMutation({
    mutationFn: portfolioApi.addHolding,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["portfolio"] });
      setSymbol(""); setQty(""); setAvgCost("");
    },
  });

  const removeMutation = useMutation({
    mutationFn: portfolioApi.removeHolding,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["portfolio"] }),
  });

  const handleAdd = (e: React.FormEvent) => {
    e.preventDefault();
    if (!symbol || !qty || !avgCost) return;
    addMutation.mutate({
      symbol: symbol.toUpperCase(),
      quantity: parseFloat(qty),
      avg_cost: parseFloat(avgCost),
      exchange,
    });
  };

  const sectorData = data
    ? Object.entries(data.sector_exposure || {}).map(([name, pct]) => ({
        name,
        value: pct as number,
      }))
    : [];

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Portfolio</h1>
          <p className="text-slate-500 text-sm mt-1">
            {kiteStatus?.connected
              ? "Live data via Zerodha Kite"
              : "Manual tracking mode — connect Kite for live data"}
          </p>
        </div>
        {kiteStatus && !kiteStatus.connected && (
          <a
            href="http://localhost:8000/api/v1/portfolio/kite/login-url"
            target="_blank"
            rel="noopener noreferrer"
            className="px-4 py-2 bg-accent-blue/20 border border-accent-blue/40 text-accent-blue text-sm rounded-lg hover:bg-accent-blue/30 transition-colors"
          >
            Connect Kite
          </a>
        )}
      </div>

      {/* Summary cards */}
      {data && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="card">
            <div className="text-xs text-slate-500 uppercase tracking-wide">Invested</div>
            <div className="num text-lg font-semibold text-white mt-1">
              ₹{data.summary.total_invested.toLocaleString("en-IN", { maximumFractionDigits: 0 })}
            </div>
          </div>
          <div className="card">
            <div className="text-xs text-slate-500 uppercase tracking-wide">Market Value</div>
            <div className="num text-lg font-semibold text-white mt-1">
              ₹{data.summary.total_market_value.toLocaleString("en-IN", { maximumFractionDigits: 0 })}
            </div>
          </div>
          <div className="card">
            <div className="text-xs text-slate-500 uppercase tracking-wide">Unrealized PnL</div>
            <div className={cn("num text-lg font-semibold mt-1",
              data.summary.total_unrealized_pnl >= 0 ? "text-accent-green" : "text-accent-red")}>
              {data.summary.total_unrealized_pnl >= 0 ? "+" : ""}
              ₹{data.summary.total_unrealized_pnl.toLocaleString("en-IN", { maximumFractionDigits: 0 })}
              <span className="text-sm ml-1">
                ({data.summary.total_unrealized_pnl_pct.toFixed(1)}%)
              </span>
            </div>
          </div>
          <div className="card">
            <div className="text-xs text-slate-500 uppercase tracking-wide">Portfolio VaR (95%)</div>
            <div className="num text-lg font-semibold text-accent-red mt-1">
              {(data.summary.portfolio_var_95 * 100).toFixed(2)}%
            </div>
            <div className="text-xs text-slate-600">1-day</div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Positions table */}
        <div className="lg:col-span-2 space-y-4">
          {/* Add holding form */}
          <form onSubmit={handleAdd} className="card">
            <h2 className="text-sm font-semibold text-slate-300 mb-3">Add Holding</h2>
            <div className="flex gap-2 flex-wrap">
              <input
                value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())}
                placeholder="Symbol" className="w-28 bg-surface-2 border border-surface-3 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-accent-blue"
              />
              <input
                type="number" value={qty} onChange={(e) => setQty(e.target.value)}
                placeholder="Qty" className="w-24 bg-surface-2 border border-surface-3 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-accent-blue"
              />
              <input
                type="number" value={avgCost} onChange={(e) => setAvgCost(e.target.value)}
                placeholder="Avg Cost" className="w-32 bg-surface-2 border border-surface-3 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-accent-blue"
              />
              <select
                value={exchange} onChange={(e) => setExchange(e.target.value)}
                className="bg-surface-2 border border-surface-3 rounded-lg px-3 py-2 text-sm text-white focus:outline-none"
              >
                <option value="NSE">NSE</option>
                <option value="BSE">BSE</option>
              </select>
              <button type="submit" disabled={addMutation.isPending}
                className="flex items-center gap-1.5 px-4 py-2 bg-accent-blue/20 hover:bg-accent-blue/30 border border-accent-blue/40 text-accent-blue rounded-lg text-sm transition-colors disabled:opacity-50">
                <Plus size={14} />Add
              </button>
            </div>
          </form>

          {/* Positions list */}
          {isLoading && <div className="card text-slate-500 text-center py-8">Loading…</div>}
          {data && data.positions.length === 0 && (
            <div className="card text-slate-500 text-center py-8">No positions yet.</div>
          )}
          <div className="space-y-2">
            {(data?.positions ?? []).map((p: any) => (
              <div key={p.symbol} className="card flex items-center gap-4">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-white">{p.symbol}</span>
                    <span className="text-xs text-slate-500 bg-surface-3 px-1.5 py-0.5 rounded">{p.sector || "—"}</span>
                    <span className="text-xs text-slate-500">{p.weight_pct}%</span>
                  </div>
                  <div className="text-xs text-slate-500 mt-0.5 num">
                    {p.quantity} shares @ ₹{p.avg_cost.toFixed(2)} → ₹{p.current_price.toFixed(2)}
                  </div>
                </div>
                <div className="text-right">
                  <div className={cn("num font-medium", p.unrealized_pnl >= 0 ? "text-accent-green" : "text-accent-red")}>
                    {p.unrealized_pnl >= 0 ? <TrendingUp size={12} className="inline mr-1" /> : <TrendingDown size={12} className="inline mr-1" />}
                    {p.unrealized_pnl >= 0 ? "+" : ""}{p.unrealized_pnl_pct.toFixed(1)}%
                  </div>
                  <div className="text-xs text-slate-500 num">
                    ₹{p.market_value.toLocaleString("en-IN", { maximumFractionDigits: 0 })}
                  </div>
                </div>
                <button
                  onClick={() => removeMutation.mutate(p.symbol)}
                  className="text-slate-600 hover:text-accent-red transition-colors"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>

          {/* Rebalancing suggestions */}
          {data?.rebalancing_suggestions?.length > 0 && (
            <div className="card border-accent-gold/20">
              <h3 className="text-sm font-semibold text-accent-gold mb-3 flex items-center gap-2">
                <AlertCircle size={14} />
                Rebalancing Suggestions
              </h3>
              <ul className="space-y-2">
                {data.rebalancing_suggestions.map((s: any, i: number) => (
                  <li key={i} className="text-sm flex items-start gap-2">
                    <span className={cn(
                      "shrink-0 px-1.5 py-0.5 rounded text-xs font-medium",
                      s.action === "TRIM" ? "bg-accent-gold/20 text-accent-gold" : "bg-accent-red/20 text-accent-red"
                    )}>
                      {s.action}
                    </span>
                    <span className="text-slate-400">{s.reason}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Sector pie chart */}
        <div className="card">
          <h2 className="text-sm font-semibold text-slate-300 mb-4">Sector Exposure</h2>
          {sectorData.length > 0 ? (
            <>
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie
                    data={sectorData}
                    cx="50%" cy="50%"
                    outerRadius={80}
                    dataKey="value"
                  >
                    {sectorData.map((_, i) => (
                      <Cell key={i} fill={SECTOR_COLORS[i % SECTOR_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(v: number) => [`${v.toFixed(1)}%`, "Weight"]}
                    contentStyle={{ background: "#1c2230", border: "1px solid #222b3d", borderRadius: "8px" }}
                  />
                </PieChart>
              </ResponsiveContainer>
              <ul className="space-y-1 mt-2">
                {sectorData.map((s, i) => (
                  <li key={s.name} className="flex items-center justify-between text-xs">
                    <span className="flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full" style={{ background: SECTOR_COLORS[i % SECTOR_COLORS.length] }} />
                      <span className="text-slate-300 capitalize">{s.name}</span>
                    </span>
                    <span className="num text-slate-400">{s.value.toFixed(1)}%</span>
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <div className="text-slate-500 text-center py-8 text-sm">Add positions to see sector breakdown</div>
          )}
        </div>
      </div>
    </div>
  );
}
