import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { intelligenceApi } from "../lib/api";
import { Calendar, AlertTriangle, Globe, TrendingUp } from "lucide-react";
import { cn } from "../lib/utils";

const IMPACT_COLORS = {
  high: "text-accent-red border-accent-red/30 bg-accent-red/10",
  medium: "text-accent-gold border-accent-gold/30 bg-accent-gold/10",
  low: "text-slate-400 border-slate-600 bg-slate-700/20",
};

const REGION_FLAGS: Record<string, string> = {
  US: "🇺🇸", IN: "🇮🇳", EU: "🇪🇺", CN: "🇨🇳",
  GB: "🇬🇧", JP: "🇯🇵", GLOBAL: "🌍",
};

const EVENT_ICONS: Record<string, string> = {
  FED_DECISION: "🏦", RBI_DECISION: "🏦", ECB_DECISION: "🏦",
  EARNINGS: "📊", US_CPI: "📈", US_GDP: "📈",
  US_NFP: "👷", INDIA_BUDGET: "📋", ELECTION: "🗳️",
  FNO_EXPIRY: "⏰", GEOPOLITICAL: "⚔️", MACRO_RELEASE: "📰",
};

export function Events() {
  const [filterImpact, setFilterImpact] = useState<string>("all");
  const [filterRegion, setFilterRegion] = useState<string>("all");
  const [daysAhead, setDaysAhead] = useState(30);

  const { data, isLoading } = useQuery({
    queryKey: ["calendar", daysAhead, filterImpact, filterRegion],
    queryFn: () => intelligenceApi.calendar(
      daysAhead,
      filterImpact !== "all" ? filterImpact : undefined,
    ),
    staleTime: 15 * 60 * 1000,
  });

  const { data: marketNews } = useQuery({
    queryKey: ["market-news"],
    queryFn: () => intelligenceApi.marketNews(3),
    staleTime: 30 * 60 * 1000,
  });

  const events = (data?.events ?? []).filter((e: any) =>
    filterRegion === "all" || e.region === filterRegion
  );

  const highImpact = events.filter((e: any) => e.impact_level === "high");
  const thisWeek = events.filter((e: any) => e.days_away <= 7);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Event Calendar</h1>
        <p className="text-slate-500 text-sm mt-1">
          Macro events, central bank decisions, earnings, and geopolitical risks
        </p>
      </div>

      {/* Market sentiment banner */}
      {marketNews && (
        <div className={cn(
          "card border",
          marketNews.market_sentiment.label === "positive" ? "border-accent-green/30 bg-accent-green/5" :
          marketNews.market_sentiment.label === "negative" ? "border-accent-red/30 bg-accent-red/5" :
          "border-surface-3"
        )}>
          <div className="flex items-center gap-3">
            <div className="text-2xl">
              {marketNews.market_sentiment.label === "positive" ? "📈" :
               marketNews.market_sentiment.label === "negative" ? "📉" : "📊"}
            </div>
            <div>
              <p className="text-xs text-slate-500 uppercase tracking-wide">3-day Market Sentiment</p>
              <p className={cn(
                "text-sm font-medium capitalize",
                marketNews.market_sentiment.label === "positive" ? "text-accent-green" :
                marketNews.market_sentiment.label === "negative" ? "text-accent-red" : "text-slate-300"
              )}>
                {marketNews.market_sentiment.label} (score: {marketNews.market_sentiment.score.toFixed(3)})
              </p>
            </div>
            {marketNews.active_event_types?.length > 0 && (
              <div className="ml-4 flex gap-2 flex-wrap">
                {marketNews.active_event_types.slice(0, 4).map((t: string) => (
                  <span key={t} className="text-xs bg-surface-3 text-slate-400 px-2 py-0.5 rounded">
                    {t.replace(/_/g, " ")}
                  </span>
                ))}
              </div>
            )}
          </div>
          {marketNews.high_impact_events?.length > 0 && (
            <p className="text-xs text-slate-400 mt-2 flex gap-1.5 items-start">
              <AlertTriangle size={12} className="text-accent-gold mt-0.5 shrink-0" />
              {marketNews.high_impact_events[0]}
            </p>
          )}
        </div>
      )}

      {/* Stats row */}
      <div className="grid grid-cols-3 gap-4">
        <div className="card text-center">
          <div className="text-2xl font-bold text-accent-red">{highImpact.length}</div>
          <div className="text-xs text-slate-500 mt-1">High Impact</div>
        </div>
        <div className="card text-center">
          <div className="text-2xl font-bold text-accent-gold">{thisWeek.length}</div>
          <div className="text-xs text-slate-500 mt-1">This Week</div>
        </div>
        <div className="card text-center">
          <div className="text-2xl font-bold text-white">{events.length}</div>
          <div className="text-xs text-slate-500 mt-1">Total Events</div>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3 flex-wrap">
        <div className="flex gap-1">
          {["all", "high", "medium", "low"].map((impact) => (
            <button
              key={impact}
              onClick={() => setFilterImpact(impact)}
              className={cn(
                "px-3 py-1.5 rounded-lg text-xs font-medium transition-colors",
                filterImpact === impact
                  ? "bg-accent-blue/20 text-accent-blue border border-accent-blue/40"
                  : "bg-surface-2 text-slate-400 border border-surface-3 hover:text-white"
              )}
            >
              {impact === "all" ? "All Impact" : impact.charAt(0).toUpperCase() + impact.slice(1)}
            </button>
          ))}
        </div>
        <div className="flex gap-1">
          {["all", "IN", "US", "EU"].map((region) => (
            <button
              key={region}
              onClick={() => setFilterRegion(region)}
              className={cn(
                "px-3 py-1.5 rounded-lg text-xs font-medium transition-colors",
                filterRegion === region
                  ? "bg-accent-purple/20 text-accent-purple border border-accent-purple/40"
                  : "bg-surface-2 text-slate-400 border border-surface-3 hover:text-white"
              )}
            >
              {region === "all" ? "All Regions" : `${REGION_FLAGS[region] || ""} ${region}`}
            </button>
          ))}
        </div>
        <select
          value={daysAhead}
          onChange={(e) => setDaysAhead(Number(e.target.value))}
          className="bg-surface-2 border border-surface-3 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none"
        >
          <option value={7}>Next 7 days</option>
          <option value={14}>Next 14 days</option>
          <option value={30}>Next 30 days</option>
          <option value={60}>Next 60 days</option>
        </select>
      </div>

      {/* Event list */}
      {isLoading && (
        <div className="card text-center text-slate-500 py-8">Loading calendar…</div>
      )}

      <div className="space-y-2">
        {events.map((event: any, i: number) => (
          <div
            key={i}
            className={cn(
              "card flex items-start gap-4 hover:border-slate-500 transition-colors",
              event.days_away <= 3 && event.impact_level === "high" && "border-accent-red/30"
            )}
          >
            {/* Date */}
            <div className="shrink-0 text-center w-14">
              {event.scheduled_at ? (
                <>
                  <div className="text-xs text-slate-500">
                    {new Date(event.scheduled_at).toLocaleDateString("en-IN", { month: "short" })}
                  </div>
                  <div className="text-xl font-bold text-white">
                    {new Date(event.scheduled_at).getDate()}
                  </div>
                  <div className="text-xs text-slate-600">
                    {event.days_away === 0 ? "Today" : event.days_away === 1 ? "Tomorrow" : `${event.days_away}d`}
                  </div>
                </>
              ) : (
                <Calendar size={20} className="text-slate-600 mx-auto mt-2" />
              )}
            </div>

            {/* Content */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-base">{EVENT_ICONS[event.event_type] || "📅"}</span>
                <h3 className="font-medium text-white truncate">{event.title}</h3>
                <span className={cn(
                  "shrink-0 text-xs px-2 py-0.5 rounded border",
                  IMPACT_COLORS[event.impact_level as keyof typeof IMPACT_COLORS] || IMPACT_COLORS.low
                )}>
                  {event.impact_level}
                </span>
              </div>

              <div className="flex items-center gap-3 text-xs text-slate-500">
                <span className="flex items-center gap-1">
                  <Globe size={11} />
                  {REGION_FLAGS[event.region] || ""} {event.country || event.region}
                </span>
                <span>{event.event_type.replace(/_/g, " ")}</span>
                {event.affected_sectors?.length > 0 && (
                  <span className="flex items-center gap-1">
                    <TrendingUp size={11} />
                    {event.affected_sectors.slice(0, 3).join(", ")}
                  </span>
                )}
              </div>

              {/* Forecast / prev */}
              {(event.forecast || event.previous) && (
                <div className="flex gap-4 mt-1.5 text-xs">
                  {event.forecast && event.forecast !== "None" && (
                    <span className="text-slate-400">
                      Forecast: <span className="text-accent-blue font-mono">{event.forecast}</span>
                    </span>
                  )}
                  {event.previous && event.previous !== "None" && (
                    <span className="text-slate-400">
                      Previous: <span className="text-slate-300 font-mono">{event.previous}</span>
                    </span>
                  )}
                </div>
              )}
            </div>
          </div>
        ))}

        {!isLoading && events.length === 0 && (
          <div className="card text-center py-10 text-slate-500">
            No events found for the selected filters.
          </div>
        )}
      </div>
    </div>
  );
}
