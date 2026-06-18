import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
  BarChart,
  Bar,
} from "recharts";
import { macroApi } from "../lib/api";
import { fmt } from "../lib/utils";

// ── Macro series catalogue ────────────────────────────────────────────────────

interface SeriesGroup {
  label: string;
  color: string;
  series: { id: string; label: string }[];
}

const SERIES_GROUPS: SeriesGroup[] = [
  {
    label: "Interest Rates",
    color: "#6366f1",
    series: [
      { id: "FEDFUNDS", label: "Fed Funds Rate" },
      { id: "DGS10", label: "10Y Treasury" },
      { id: "DGS2", label: "2Y Treasury" },
      { id: "DGS30", label: "30Y Treasury" },
    ],
  },
  {
    label: "Inflation",
    color: "#f59e0b",
    series: [
      { id: "CPIAUCSL", label: "CPI (All Items)" },
      { id: "CPILFESL", label: "Core CPI" },
      { id: "PCEPI", label: "PCE Price Index" },
    ],
  },
  {
    label: "Growth",
    color: "#10b981",
    series: [
      { id: "GDP", label: "Real GDP" },
      { id: "UNRATE", label: "Unemployment Rate" },
      { id: "PAYEMS", label: "Nonfarm Payrolls" },
    ],
  },
  {
    label: "Financial Conditions",
    color: "#ef4444",
    series: [
      { id: "VIXCLS", label: "VIX" },
      { id: "DCOILWTICO", label: "WTI Crude Oil" },
      { id: "GOLDAMGBD228NLBM", label: "Gold Price" },
      { id: "DXY", label: "US Dollar Index" },
    ],
  },
];

const YIELD_MATURITIES = [
  { id: "DGS3MO", label: "3M" },
  { id: "DGS2", label: "2Y" },
  { id: "DGS5", label: "5Y" },
  { id: "DGS10", label: "10Y" },
  { id: "DGS30", label: "30Y" },
];

// ── Yield Curve Component ─────────────────────────────────────────────────────

function YieldCurve() {
  const { data, isLoading } = useQuery({
    queryKey: ["yield-curve"],
    queryFn: () => macroApi.yieldCurve(),
    staleTime: 6 * 60 * 60 * 1000,
  });

  const chartData = YIELD_MATURITIES.map(({ id, label }) => {
    const seriesData = data?.[id];
    const latest = seriesData ? Object.values(seriesData).slice(-1)[0] : null;
    return { maturity: label, yield: latest ? parseFloat(String(latest)) : null };
  }).filter((d) => d.yield !== null);

  const isInverted =
    chartData.length >= 2 &&
    chartData[0].yield! > chartData[chartData.length - 1].yield!;

  if (isLoading) return <div className="animate-pulse h-48 bg-gray-800 rounded-lg" />;

  return (
    <div className="bg-gray-900 border border-gray-700 rounded-xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-white font-semibold">Yield Curve</h3>
        {isInverted ? (
          <span className="text-xs bg-red-500/20 text-red-400 px-2 py-1 rounded-full font-medium">
            ⚠ Inverted
          </span>
        ) : (
          <span className="text-xs bg-green-500/20 text-green-400 px-2 py-1 rounded-full font-medium">
            Normal
          </span>
        )}
      </div>
      {chartData.length === 0 ? (
        <p className="text-gray-500 text-sm text-center py-8">
          Configure FRED_API_KEY to fetch yield curve data
        </p>
      ) : (
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis dataKey="maturity" stroke="#9ca3af" tick={{ fontSize: 11 }} />
            <YAxis stroke="#9ca3af" tick={{ fontSize: 11 }} tickFormatter={(v) => `${v}%`} />
            <Tooltip
              contentStyle={{ backgroundColor: "#1f2937", border: "1px solid #374151" }}
              formatter={(v: number) => [`${v?.toFixed(2)}%`, "Yield"]}
            />
            <Line
              type="monotone"
              dataKey="yield"
              stroke={isInverted ? "#ef4444" : "#10b981"}
              strokeWidth={2}
              dot={{ r: 4, fill: isInverted ? "#ef4444" : "#10b981" }}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
      <p className="text-gray-500 text-xs mt-2">
        2Y–10Y spread:{" "}
        {chartData.length >= 4
          ? `${((chartData[3].yield ?? 0) - (chartData[1].yield ?? 0)).toFixed(2)}%`
          : "N/A"}
      </p>
    </div>
  );
}

// ── Time Series Chart ─────────────────────────────────────────────────────────

const COLORS = ["#6366f1", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4"];

function MacroSeriesChart({ seriesIds, title }: { seriesIds: string[]; title: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ["macro-series", ...seriesIds],
    queryFn: () => macroApi.series(seriesIds),
    staleTime: 6 * 60 * 60 * 1000,
    enabled: seriesIds.length > 0,
  });

  if (isLoading) return <div className="animate-pulse h-48 bg-gray-800 rounded-lg" />;
  if (!data) return null;

  // Build unified timeline
  const allDates = new Set<string>();
  seriesIds.forEach((id) => {
    if (data[id]) Object.keys(data[id]).forEach((d) => allDates.add(d));
  });

  const chartData = Array.from(allDates)
    .sort()
    .slice(-252)
    .map((date) => {
      const row: Record<string, string | number> = { date };
      seriesIds.forEach((id) => {
        const val = data[id]?.[date];
        if (val !== undefined && val !== null) row[id] = parseFloat(String(val));
      });
      return row;
    });

  const latestValues: Record<string, number> = {};
  seriesIds.forEach((id) => {
    const vals = Object.values(data[id] || {});
    if (vals.length) latestValues[id] = parseFloat(String(vals[vals.length - 1]));
  });

  const labelMap: Record<string, string> = {};
  SERIES_GROUPS.forEach((g) =>
    g.series.forEach((s) => {
      labelMap[s.id] = s.label;
    })
  );

  if (chartData.length === 0) {
    return (
      <div className="bg-gray-900 border border-gray-700 rounded-xl p-5">
        <h3 className="text-white font-semibold mb-2">{title}</h3>
        <p className="text-gray-500 text-sm text-center py-8">
          No data — configure FRED_API_KEY
        </p>
      </div>
    );
  }

  return (
    <div className="bg-gray-900 border border-gray-700 rounded-xl p-5">
      <div className="flex items-start justify-between mb-4 flex-wrap gap-3">
        <h3 className="text-white font-semibold">{title}</h3>
        <div className="flex flex-wrap gap-3">
          {seriesIds.map((id, i) => (
            <div key={id} className="text-center">
              <div className="text-xs text-gray-400">{labelMap[id] || id}</div>
              <div className="text-sm font-mono font-semibold" style={{ color: COLORS[i % COLORS.length] }}>
                {latestValues[id] !== undefined ? fmt.pct(latestValues[id] / 100) : "—"}
              </div>
            </div>
          ))}
        </div>
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis
            dataKey="date"
            stroke="#9ca3af"
            tick={{ fontSize: 10 }}
            tickFormatter={(v) => v.slice(0, 7)}
            interval="preserveStartEnd"
          />
          <YAxis stroke="#9ca3af" tick={{ fontSize: 10 }} />
          <Tooltip
            contentStyle={{ backgroundColor: "#1f2937", border: "1px solid #374151" }}
            labelStyle={{ color: "#e5e7eb" }}
            formatter={(v: number, name: string) => [
              fmt.number(v, 2),
              labelMap[name] || name,
            ]}
          />
          <Legend formatter={(v) => labelMap[v] || v} wrapperStyle={{ fontSize: 11 }} />
          {seriesIds.map((id, i) => (
            <Line
              key={id}
              type="monotone"
              dataKey={id}
              stroke={COLORS[i % COLORS.length]}
              strokeWidth={1.5}
              dot={false}
              connectNulls
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── Regime Summary Cards ──────────────────────────────────────────────────────

function MacroMetricCard({
  label,
  seriesId,
  format = "pct",
  suffix = "",
}: {
  label: string;
  seriesId: string;
  format?: "pct" | "number" | "large";
  suffix?: string;
}) {
  const { data } = useQuery({
    queryKey: ["macro-series", seriesId],
    queryFn: () => macroApi.series([seriesId]),
    staleTime: 6 * 60 * 60 * 1000,
  });

  const vals = data?.[seriesId] ? Object.values(data[seriesId]) : [];
  const latest = vals.length ? parseFloat(String(vals[vals.length - 1])) : null;
  const prev = vals.length > 1 ? parseFloat(String(vals[vals.length - 2])) : null;
  const change = latest !== null && prev !== null ? latest - prev : null;

  const display =
    latest === null
      ? "—"
      : format === "pct"
      ? `${latest.toFixed(2)}%`
      : format === "large"
      ? fmt.large(latest)
      : fmt.number(latest, 2);

  return (
    <div className="bg-gray-900 border border-gray-700 rounded-xl p-4">
      <div className="text-xs text-gray-400 mb-1">{label}</div>
      <div className="text-2xl font-bold text-white font-mono">
        {display}
        {suffix && <span className="text-sm text-gray-400 ml-1">{suffix}</span>}
      </div>
      {change !== null && (
        <div
          className={`text-xs mt-1 font-medium ${
            change > 0 ? "text-red-400" : change < 0 ? "text-green-400" : "text-gray-400"
          }`}
        >
          {change > 0 ? "▲" : change < 0 ? "▼" : "—"} {Math.abs(change).toFixed(2)} vs prev
        </div>
      )}
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function Macro() {
  const [activeGroup, setActiveGroup] = useState<string>("Interest Rates");

  const activeSeriesGroup = SERIES_GROUPS.find((g) => g.label === activeGroup);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Macro Dashboard</h1>
        <p className="text-gray-400 text-sm mt-1">
          FRED economic indicators — interest rates, inflation, growth, and financial conditions
        </p>
      </div>

      {/* ── Key Metrics ── */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <MacroMetricCard label="Fed Funds Rate" seriesId="FEDFUNDS" />
        <MacroMetricCard label="10Y Treasury" seriesId="DGS10" />
        <MacroMetricCard label="CPI YoY" seriesId="CPIAUCSL" />
        <MacroMetricCard label="Unemployment" seriesId="UNRATE" />
        <MacroMetricCard label="VIX" seriesId="VIXCLS" format="number" />
        <MacroMetricCard label="WTI Crude" seriesId="DCOILWTICO" format="number" suffix="$/bbl" />
      </div>

      {/* ── Yield Curve ── */}
      <YieldCurve />

      {/* ── Time Series Charts ── */}
      <div>
        <div className="flex gap-2 mb-4 flex-wrap">
          {SERIES_GROUPS.map((g) => (
            <button
              key={g.label}
              onClick={() => setActiveGroup(g.label)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                activeGroup === g.label
                  ? "bg-indigo-600 text-white"
                  : "bg-gray-800 text-gray-400 hover:text-white hover:bg-gray-700"
              }`}
            >
              {g.label}
            </button>
          ))}
        </div>

        {activeSeriesGroup && (
          <MacroSeriesChart
            title={activeSeriesGroup.label}
            seriesIds={activeSeriesGroup.series.map((s) => s.id)}
          />
        )}
      </div>

      {/* ── Interpretation panel ── */}
      <MacroInterpretation />
    </div>
  );
}

// ── Macro Regime Interpretation ───────────────────────────────────────────────

function MacroInterpretation() {
  const { data: ratesData } = useQuery({
    queryKey: ["macro-series", "FEDFUNDS", "DGS10", "DGS2"],
    queryFn: () => macroApi.series(["FEDFUNDS", "DGS10", "DGS2"]),
    staleTime: 6 * 60 * 60 * 1000,
  });

  const { data: inflationData } = useQuery({
    queryKey: ["macro-series", "CPIAUCSL"],
    queryFn: () => macroApi.series(["CPIAUCSL"]),
    staleTime: 6 * 60 * 60 * 1000,
  });

  const getLatest = (d: Record<string, Record<string, string>> | undefined, id: string) => {
    const vals = d?.[id] ? Object.values(d[id]) : [];
    return vals.length ? parseFloat(String(vals[vals.length - 1])) : null;
  };

  const fedFunds = getLatest(ratesData, "FEDFUNDS");
  const tenYear = getLatest(ratesData, "DGS10");
  const twoYear = getLatest(ratesData, "DGS2");
  const cpi = getLatest(inflationData, "CPIAUCSL");

  const spread = tenYear !== null && twoYear !== null ? tenYear - twoYear : null;
  const isInverted = spread !== null && spread < 0;
  const isHighInflation = cpi !== null && cpi > 4;
  const isHighRates = fedFunds !== null && fedFunds > 4;

  const signals = [];
  if (isInverted) signals.push({ text: "Yield curve inverted — recession risk elevated", color: "red" });
  if (isHighInflation) signals.push({ text: `CPI at ${cpi?.toFixed(1)}% — inflationary environment`, color: "amber" });
  if (isHighRates) signals.push({ text: `Fed Funds at ${fedFunds?.toFixed(2)}% — tightening cycle`, color: "amber" });
  if (!isInverted && spread !== null) signals.push({ text: `2Y–10Y spread +${spread.toFixed(2)}% — curve normal`, color: "green" });

  if (signals.length === 0) return null;

  return (
    <div className="bg-gray-900 border border-gray-700 rounded-xl p-5">
      <h3 className="text-white font-semibold mb-3">Macro Regime Interpretation</h3>
      <div className="space-y-2">
        {signals.map((s, i) => (
          <div
            key={i}
            className={`flex items-center gap-2 text-sm p-2 rounded-lg ${
              s.color === "red"
                ? "bg-red-500/10 text-red-400"
                : s.color === "amber"
                ? "bg-amber-500/10 text-amber-400"
                : "bg-green-500/10 text-green-400"
            }`}
          >
            <span>{s.color === "red" ? "⚠" : s.color === "amber" ? "◈" : "✓"}</span>
            {s.text}
          </div>
        ))}
      </div>
    </div>
  );
}
