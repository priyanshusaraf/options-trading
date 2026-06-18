import { useQuery } from "@tanstack/react-query";
import { analysisApi, dataApi } from "../lib/api";
import { OpportunityCard } from "../components/OpportunityCard";
import { RegimeBadge } from "../components/RegimeBadge";
import { MetricCard } from "../components/MetricCard";
import { fmt } from "../lib/utils";
import { Activity, RefreshCw } from "lucide-react";

export function Dashboard() {
  const { data: opps, isLoading, refetch, isFetching } = useQuery({
    queryKey: ["opportunities"],
    queryFn: () => analysisApi.opportunities(756, 20),
    staleTime: 5 * 60 * 1000,
  });

  const { data: regime } = useQuery({
    queryKey: ["regime"],
    queryFn: () => analysisApi.regime(),
    staleTime: 10 * 60 * 1000,
  });

  const { data: health } = useQuery({
    queryKey: ["health"],
    queryFn: dataApi.health,
    staleTime: 30 * 1000,
  });

  const buyList = opps?.opportunities.filter((o) => o.score > 0.1) ?? [];
  const sellList = opps?.opportunities.filter((o) => o.score < -0.1) ?? [];
  const holdList = opps?.opportunities.filter((o) => Math.abs(o.score) <= 0.1) ?? [];

  return (
    <div className="space-y-6">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Market Intelligence</h1>
          <p className="text-slate-500 text-sm mt-1">Ranked opportunities across your watchlist</p>
        </div>
        <div className="flex items-center gap-4">
          {regime && (
            <div className="card py-2 px-4">
              <span className="text-xs text-slate-500 mr-2">Regime</span>
              <RegimeBadge regime={regime.regime} confidence={regime.confidence} />
            </div>
          )}
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="flex items-center gap-2 px-4 py-2 bg-surface-2 hover:bg-surface-3 border border-surface-3 rounded-lg text-sm text-slate-300 transition-colors disabled:opacity-50"
          >
            <RefreshCw size={14} className={isFetching ? "animate-spin" : ""} />
            Refresh
          </button>
        </div>
      </div>

      {/* Regime summary */}
      {regime && (
        <div className="card">
          <p className="text-sm text-slate-300">{regime.description}</p>
          <div className="grid grid-cols-3 gap-4 mt-3">
            <div className="text-center">
              <div className="text-xs text-slate-500">30d Realized Vol</div>
              <div className="num text-lg text-white">{fmt(regime.realized_vol_30d * 100, "number", 1)}%</div>
            </div>
            <div className="text-center">
              <div className="text-xs text-slate-500">Vol Regime</div>
              <div className="text-sm font-medium text-accent-gold capitalize">{regime.vol_regime}</div>
            </div>
            <div className="text-center">
              <div className="text-xs text-slate-500">Trend Strength</div>
              <div className="num text-lg text-white">{fmt(regime.trend_strength * 100, "number", 0)}%</div>
            </div>
          </div>
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        <MetricCard
          label="Buy Signals"
          value={buyList.length}
          sub={`of ${opps?.opportunities.length ?? 0} symbols`}
          colorize
          size="lg"
        />
        <MetricCard label="Hold" value={holdList.length} size="lg" />
        <MetricCard
          label="Sell Signals"
          value={sellList.length}
          sub="reduce or exit"
          colorize
          size="lg"
        />
      </div>

      {/* Loading state */}
      {isLoading && (
        <div className="flex items-center justify-center py-16 gap-3 text-slate-400">
          <Activity size={20} className="animate-pulse" />
          <span>Running analysis across watchlist…</span>
        </div>
      )}

      {/* Opportunities grid */}
      {!isLoading && opps && (
        <>
          {buyList.length > 0 && (
            <section>
              <h2 className="text-sm font-semibold text-accent-green uppercase tracking-wider mb-3">
                Buy Opportunities ({buyList.length})
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {buyList.map((o) => (
                  <OpportunityCard key={o.symbol} opp={o} />
                ))}
              </div>
            </section>
          )}

          {holdList.length > 0 && (
            <section>
              <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-3">
                Hold ({holdList.length})
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {holdList.map((o) => (
                  <OpportunityCard key={o.symbol} opp={o} />
                ))}
              </div>
            </section>
          )}

          {sellList.length > 0 && (
            <section>
              <h2 className="text-sm font-semibold text-accent-red uppercase tracking-wider mb-3">
                Sell / Reduce ({sellList.length})
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {sellList.map((o) => (
                  <OpportunityCard key={o.symbol} opp={o} />
                ))}
              </div>
            </section>
          )}

          {opps.opportunities.length === 0 && (
            <div className="card text-center py-12 text-slate-500">
              <p>No opportunities found. Add symbols to your watchlist to begin.</p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
