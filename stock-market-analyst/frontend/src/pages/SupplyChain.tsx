import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { intelligenceApi, commodityApi } from "../lib/api";
import { cn } from "../lib/utils";
import { GitBranch, Zap, BarChart2 } from "lucide-react";

export function SupplyChain() {
  const [disruptionNode, setDisruptionNode] = useState("crude_oil");
  const [magnitude, setMagnitude] = useState(0.5);
  const [linkageSymbol, setLinkageSymbol] = useState("RELIANCE");
  const [linkageInput, setLinkageInput] = useState("RELIANCE");

  const { data: graphData } = useQuery({
    queryKey: ["supply-graph"],
    queryFn: () => intelligenceApi.graph(),
    staleTime: 10 * 60 * 1000,
  });

  const { data: disruption, refetch: runDisruption, isFetching: disruptionLoading } = useQuery({
    queryKey: ["disruption", disruptionNode, magnitude],
    queryFn: () => intelligenceApi.disruption(disruptionNode, magnitude),
    enabled: false,
    staleTime: 0,
  });

  const { data: linkage, refetch: runLinkage, isFetching: linkageLoading } = useQuery({
    queryKey: ["commodity-linkage", linkageSymbol],
    queryFn: () => commodityApi.linkage(linkageSymbol),
    enabled: false,
    staleTime: 0,
  });

  const { data: commodityOverview } = useQuery({
    queryKey: ["commodity-overview"],
    queryFn: () => commodityApi.overview(30),
    staleTime: 60 * 60 * 1000,
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Supply Chain & Commodities</h1>
        <p className="text-slate-500 text-sm mt-1">
          Graph-based dependency modeling + commodity linkage analysis
        </p>
      </div>

      {/* Graph stats */}
      {graphData && (
        <div className="grid grid-cols-4 gap-4">
          {[
            { label: "Companies", value: graphData.stats?.companies ?? 0 },
            { label: "Commodities", value: graphData.stats?.commodities ?? 0 },
            { label: "Regions", value: graphData.stats?.regions ?? 0 },
            { label: "Total Edges", value: graphData.stats?.total_edges ?? 0 },
          ].map(({ label, value }) => (
            <div key={label} className="card text-center">
              <div className="text-xl font-bold text-white">{value}</div>
              <div className="text-xs text-slate-500 mt-1">{label}</div>
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Disruption Simulator */}
        <div className="card space-y-4">
          <h2 className="font-semibold text-white flex items-center gap-2">
            <Zap size={16} className="text-accent-gold" />
            Disruption Simulator
          </h2>
          <p className="text-xs text-slate-500">
            Simulate a shock at any commodity or region and see which companies are affected.
          </p>
          <div className="flex gap-3 flex-wrap">
            <input
              value={disruptionNode}
              onChange={(e) => setDisruptionNode(e.target.value.toLowerCase().replace(/ /g, "_"))}
              placeholder="Node (e.g. crude_oil, Middle East)"
              className="flex-1 bg-surface-2 border border-surface-3 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-accent-blue"
            />
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-500">Magnitude</span>
              <input
                type="range" min="0.1" max="1.0" step="0.1"
                value={magnitude} onChange={(e) => setMagnitude(parseFloat(e.target.value))}
                className="w-20"
              />
              <span className="text-xs text-accent-gold w-8">{(magnitude * 100).toFixed(0)}%</span>
            </div>
            <button
              onClick={() => runDisruption()}
              disabled={disruptionLoading}
              className="px-4 py-2 bg-accent-gold/20 hover:bg-accent-gold/30 border border-accent-gold/40 text-accent-gold rounded-lg text-sm transition-colors disabled:opacity-50"
            >
              {disruptionLoading ? "Simulating…" : "Run"}
            </button>
          </div>

          {disruption && (
            <div className="space-y-3">
              <div className="text-sm text-slate-300">{disruption.description}</div>
              {Object.entries(disruption.affected_companies || {}).length > 0 ? (
                <div className="space-y-1.5">
                  <div className="text-xs text-slate-500 uppercase tracking-wide">Affected Companies</div>
                  {Object.entries(disruption.affected_companies || {}).slice(0, 8).map(([sym, impact]: [string, any]) => (
                    <div key={sym} className="flex items-center gap-3">
                      <span className="text-sm text-white w-24 shrink-0">{sym}</span>
                      <div className="flex-1 h-1.5 bg-surface-3 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-accent-red rounded-full"
                          style={{ width: `${Math.min(impact * 100, 100)}%` }}
                        />
                      </div>
                      <span className="text-xs text-accent-red num w-12 text-right">
                        {(impact * 100).toFixed(0)}%
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-500">No companies affected (node not in graph).</p>
              )}
            </div>
          )}
        </div>

        {/* Commodity Linkage */}
        <div className="card space-y-4">
          <h2 className="font-semibold text-white flex items-center gap-2">
            <GitBranch size={16} className="text-accent-purple" />
            Commodity Linkage Analysis
          </h2>
          <div className="flex gap-3">
            <input
              value={linkageInput}
              onChange={(e) => setLinkageInput(e.target.value.toUpperCase())}
              placeholder="Symbol (e.g. RELIANCE)"
              className="flex-1 bg-surface-2 border border-surface-3 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-accent-blue"
            />
            <button
              onClick={() => { setLinkageSymbol(linkageInput); setTimeout(() => runLinkage(), 0); }}
              disabled={linkageLoading}
              className="px-4 py-2 bg-accent-purple/20 hover:bg-accent-purple/30 border border-accent-purple/40 text-accent-purple rounded-lg text-sm transition-colors disabled:opacity-50"
            >
              {linkageLoading ? "Analyzing…" : "Analyze"}
            </button>
          </div>

          {linkage && (
            <div className="space-y-3">
              <div className="flex items-center gap-3 text-sm">
                <span className="text-slate-400">Top commodity:</span>
                <span className="text-white font-medium">{linkage.top_commodity || "None"}</span>
                <span className={cn(
                  "px-2 py-0.5 rounded text-xs",
                  linkage.risk_exposure === "high" ? "bg-accent-red/20 text-accent-red" :
                  linkage.risk_exposure === "medium" ? "bg-accent-gold/20 text-accent-gold" :
                  "bg-slate-700/50 text-slate-400"
                )}>
                  {linkage.risk_exposure} risk
                </span>
              </div>
              <div className="space-y-2">
                {(linkage.links || []).map((l: any) => (
                  <div key={l.commodity} className="bg-surface-2 rounded-lg p-3">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm font-medium text-white">{l.commodity}</span>
                      <span className={cn(
                        "text-xs px-1.5 py-0.5 rounded",
                        l.relationship_type === "cost_driver" ? "bg-accent-red/20 text-accent-red" :
                        l.relationship_type === "revenue_driver" ? "bg-accent-green/20 text-accent-green" :
                        "bg-slate-600/50 text-slate-400"
                      )}>
                        {l.relationship_type?.replace(/_/g, " ")}
                      </span>
                    </div>
                    <div className="grid grid-cols-3 gap-2 text-xs text-slate-400">
                      <span>30d: <span className="num text-white">{l.corr_30d?.toFixed(3)}</span></span>
                      <span>90d: <span className="num text-white">{l.corr_90d?.toFixed(3)}</span></span>
                      <span>252d: <span className="num text-white">{l.corr_252d?.toFixed(3)}</span></span>
                    </div>
                    {l.granger_significant && (
                      <p className="text-xs text-accent-gold mt-1">
                        ⚡ Granger-causal (p={l.granger_pvalue?.toFixed(3)}) — commodity leads by {l.best_lag_days}d
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Commodity Market Overview */}
      <div className="card">
        <h2 className="font-semibold text-white flex items-center gap-2 mb-4">
          <BarChart2 size={16} className="text-accent-blue" />
          Commodity Market (30d)
        </h2>
        {commodityOverview && (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
            {commodityOverview.commodities?.map((c: any) => (
              <div key={c.name} className="bg-surface-2 rounded-lg p-3">
                <div className="text-xs text-slate-500 truncate mb-1">{c.name}</div>
                <div className="num text-sm text-white">{c.last_price?.toFixed(2)}</div>
                <div className={cn("num text-xs mt-0.5",
                  c.period_return >= 0 ? "text-accent-green" : "text-accent-red")}>
                  {c.period_return >= 0 ? "+" : ""}{(c.period_return * 100).toFixed(1)}%
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
