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
} from "recharts";
import { analysisApi } from "../lib/api";
import { Grid } from "lucide-react";

// ── Color scale for correlation values ───────────────────────────────────────

function corrColor(value: number): string {
  // -1 → red, 0 → neutral gray, +1 → green
  const v = Math.max(-1, Math.min(1, value));
  if (v >= 0) {
    const intensity = Math.round(v * 255);
    return `rgb(0, ${intensity}, ${Math.round(intensity * 0.4)})`;
  }
  const intensity = Math.round(-v * 255);
  return `rgb(${intensity}, 0, 0)`;
}

function corrTextColor(value: number): string {
  return Math.abs(value) > 0.5 ? "text-white" : "text-gray-300";
}

// ── Correlation Heatmap ───────────────────────────────────────────────────────

function CorrelationHeatmap({ matrix }: { matrix: Record<string, Record<string, number>> }) {
  const symbols = Object.keys(matrix);

  if (symbols.length === 0) {
    return <p className="text-gray-500 text-sm text-center py-8">No correlation data</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs border-collapse">
        <thead>
          <tr>
            <th className="p-2 text-gray-500 font-normal text-right border border-gray-800 bg-gray-950 sticky left-0 z-10">
              &nbsp;
            </th>
            {symbols.map((sym) => (
              <th
                key={sym}
                className="p-2 text-gray-300 font-mono font-semibold border border-gray-800 bg-gray-950 min-w-[70px]"
              >
                {sym}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {symbols.map((row) => (
            <tr key={row}>
              <td className="p-2 text-gray-300 font-mono font-semibold border border-gray-800 bg-gray-950 text-right sticky left-0 z-10">
                {row}
              </td>
              {symbols.map((col) => {
                const val = matrix[row]?.[col] ?? matrix[col]?.[row] ?? 0;
                const isDiag = row === col;
                return (
                  <td
                    key={col}
                    className={`p-2 text-center border border-gray-800 font-mono ${corrTextColor(val)}`}
                    style={{
                      backgroundColor: isDiag ? "#1f2937" : corrColor(val),
                      opacity: isDiag ? 1 : 0.85,
                    }}
                    title={`${row} × ${col} = ${val.toFixed(3)}`}
                  >
                    {isDiag ? "1.00" : val.toFixed(2)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Legend ────────────────────────────────────────────────────────────────────

function HeatmapLegend() {
  const steps = [-1, -0.75, -0.5, -0.25, 0, 0.25, 0.5, 0.75, 1];
  return (
    <div className="flex items-center gap-1 mt-3">
      <span className="text-xs text-gray-500 mr-2">Correlation:</span>
      {steps.map((v) => (
        <div
          key={v}
          className="w-6 h-4 rounded-sm text-center flex items-center justify-center"
          style={{ backgroundColor: corrColor(v) }}
          title={v.toFixed(2)}
        />
      ))}
      <div className="flex justify-between w-32 ml-2">
        <span className="text-xs text-red-400">−1</span>
        <span className="text-xs text-gray-500">0</span>
        <span className="text-xs text-green-400">+1</span>
      </div>
    </div>
  );
}

// ── Rolling Correlation Chart ─────────────────────────────────────────────────

function RollingCorrelationChart({
  symbol1,
  symbol2,
}: {
  symbol1: string;
  symbol2: string;
}) {
  const { data, isLoading } = useQuery({
    queryKey: ["rolling-corr", symbol1, symbol2],
    queryFn: () => analysisApi.rollingCorrelation(symbol1, symbol2, 30),
    staleTime: 30 * 60 * 1000,
    enabled: Boolean(symbol1 && symbol2 && symbol1 !== symbol2),
  });

  if (!symbol1 || !symbol2 || symbol1 === symbol2) {
    return (
      <div className="bg-gray-900 border border-gray-700 rounded-xl p-5 text-center py-12">
        <p className="text-gray-500 text-sm">Select two different symbols to view rolling correlation</p>
      </div>
    );
  }

  if (isLoading) return <div className="animate-pulse h-48 bg-gray-800 rounded-xl" />;
  if (!data?.rolling_correlation) {
    return (
      <div className="bg-gray-900 border border-gray-700 rounded-xl p-5 text-center py-8">
        <p className="text-gray-500 text-sm">No rolling correlation data available</p>
      </div>
    );
  }

  const chartData = Object.entries(data.rolling_correlation as Record<string, number>)
    .sort(([a], [b]) => a.localeCompare(b))
    .slice(-120)
    .map(([date, value]) => ({ date, correlation: parseFloat(value?.toFixed(3) ?? "0") }));

  const latest = chartData[chartData.length - 1]?.correlation ?? 0;

  return (
    <div className="bg-gray-900 border border-gray-700 rounded-xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-white font-semibold">
          {symbol1} × {symbol2} — 30-Day Rolling Correlation
        </h3>
        <span
          className={`text-sm font-mono font-bold ${
            latest > 0.5
              ? "text-green-400"
              : latest < -0.5
              ? "text-red-400"
              : "text-gray-300"
          }`}
        >
          Current: {latest.toFixed(3)}
        </span>
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis
            dataKey="date"
            stroke="#9ca3af"
            tick={{ fontSize: 10 }}
            tickFormatter={(v) => v.slice(5)}
            interval="preserveStartEnd"
          />
          <YAxis
            stroke="#9ca3af"
            tick={{ fontSize: 10 }}
            domain={[-1, 1]}
            tickFormatter={(v) => v.toFixed(1)}
          />
          <Tooltip
            contentStyle={{ backgroundColor: "#1f2937", border: "1px solid #374151" }}
            formatter={(v: number) => [v.toFixed(3), "Correlation"]}
          />
          <ReferenceLine y={0} stroke="#4b5563" strokeDasharray="4 2" />
          <ReferenceLine y={0.7} stroke="#10b981" strokeDasharray="4 2" strokeOpacity={0.4} />
          <ReferenceLine y={-0.7} stroke="#ef4444" strokeDasharray="4 2" strokeOpacity={0.4} />
          <Line
            type="monotone"
            dataKey="correlation"
            stroke="#6366f1"
            strokeWidth={1.5}
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
      <p className="text-gray-500 text-xs mt-2">
        Dashed lines at ±0.7 indicate strong correlation/anti-correlation
      </p>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function Correlations() {
  const [window, setWindow] = useState<number>(90);
  const [selectedA, setSelectedA] = useState<string>("");
  const [selectedB, setSelectedB] = useState<string>("");

  const { data, isLoading, error } = useQuery({
    queryKey: ["correlation-matrix", window],
    queryFn: () => analysisApi.correlationMatrix(window),
    staleTime: 30 * 60 * 1000,
  });

  const symbols: string[] = data?.symbols ?? [];
  const matrix: Record<string, Record<string, number>> = data?.matrix ?? {};

  // Find most correlated pairs
  const pairs: { a: string; b: string; corr: number }[] = [];
  symbols.forEach((a, i) => {
    symbols.slice(i + 1).forEach((b) => {
      const corr = matrix[a]?.[b] ?? matrix[b]?.[a] ?? 0;
      pairs.push({ a, b, corr });
    });
  });
  pairs.sort((x, y) => Math.abs(y.corr) - Math.abs(x.corr));
  const topPairs = pairs.slice(0, 5);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <Grid size={22} className="text-indigo-400" />
          Correlation Analysis
        </h1>
        <p className="text-gray-400 text-sm mt-1">
          Pairwise return correlations and rolling correlation dynamics for watchlist
        </p>
      </div>

      {/* ── Controls ── */}
      <div className="flex items-center gap-3 flex-wrap">
        <span className="text-sm text-gray-400">Rolling window:</span>
        {[30, 60, 90, 180, 252].map((w) => (
          <button
            key={w}
            onClick={() => setWindow(w)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              window === w
                ? "bg-indigo-600 text-white"
                : "bg-gray-800 text-gray-400 hover:text-white hover:bg-gray-700"
            }`}
          >
            {w}D
          </button>
        ))}
      </div>

      {/* ── Heatmap ── */}
      <div className="bg-gray-900 border border-gray-700 rounded-xl p-5">
        <h3 className="text-white font-semibold mb-4">
          Correlation Matrix — {window}-Day Rolling Window
        </h3>
        {isLoading ? (
          <div className="animate-pulse h-48 bg-gray-800 rounded-lg" />
        ) : error ? (
          <p className="text-red-400 text-sm">Failed to load correlation matrix</p>
        ) : (
          <>
            <CorrelationHeatmap matrix={matrix} />
            <HeatmapLegend />
          </>
        )}
      </div>

      {/* ── Top correlated pairs ── */}
      {topPairs.length > 0 && (
        <div className="bg-gray-900 border border-gray-700 rounded-xl p-5">
          <h3 className="text-white font-semibold mb-3">Strongest Correlations</h3>
          <div className="space-y-2">
            {topPairs.map(({ a, b, corr }) => (
              <div
                key={`${a}-${b}`}
                className="flex items-center justify-between p-3 bg-gray-800/50 rounded-lg cursor-pointer hover:bg-gray-800 transition-colors"
                onClick={() => {
                  setSelectedA(a);
                  setSelectedB(b);
                }}
              >
                <div className="flex items-center gap-3">
                  <span className="font-mono font-semibold text-white text-sm">{a}</span>
                  <span className="text-gray-500">↔</span>
                  <span className="font-mono font-semibold text-white text-sm">{b}</span>
                </div>
                <div className="flex items-center gap-3">
                  <div
                    className="w-16 h-1.5 rounded-full"
                    style={{ backgroundColor: corrColor(corr) }}
                  />
                  <span
                    className="font-mono text-sm font-bold"
                    style={{ color: corr > 0 ? "#10b981" : "#ef4444" }}
                  >
                    {corr.toFixed(3)}
                  </span>
                </div>
              </div>
            ))}
          </div>
          <p className="text-gray-500 text-xs mt-2">Click a pair to view rolling correlation chart</p>
        </div>
      )}

      {/* ── Rolling Correlation ── */}
      <div className="space-y-3">
        <h3 className="text-white font-semibold">Rolling Correlation Chart</h3>
        <div className="flex gap-3 flex-wrap">
          <select
            value={selectedA}
            onChange={(e) => setSelectedA(e.target.value)}
            className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm"
          >
            <option value="">Select Symbol A</option>
            {symbols.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <select
            value={selectedB}
            onChange={(e) => setSelectedB(e.target.value)}
            className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm"
          >
            <option value="">Select Symbol B</option>
            {symbols.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <RollingCorrelationChart symbol1={selectedA} symbol2={selectedB} />
      </div>
    </div>
  );
}

