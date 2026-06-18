import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ReferenceLine,
} from "recharts";
import { OHLCVPoint } from "../lib/api";

interface PriceChartProps {
  data: OHLCVPoint[];
  symbol: string;
  ma20?: number;
  ma50?: number;
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload as OHLCVPoint;
  return (
    <div className="bg-surface-2 border border-surface-3 rounded-lg p-3 text-xs">
      <p className="text-slate-400 mb-2">{label}</p>
      <div className="grid grid-cols-2 gap-x-4 gap-y-1">
        <span className="text-slate-500">Open</span>
        <span className="num text-white">{d.open.toFixed(2)}</span>
        <span className="text-slate-500">High</span>
        <span className="num text-accent-green">{d.high.toFixed(2)}</span>
        <span className="text-slate-500">Low</span>
        <span className="num text-accent-red">{d.low.toFixed(2)}</span>
        <span className="text-slate-500">Close</span>
        <span className="num text-white font-medium">{d.close.toFixed(2)}</span>
      </div>
    </div>
  );
};

export function PriceChart({ data, symbol }: PriceChartProps) {
  const displayData = data.slice(-180); // Show last 6 months

  return (
    <div className="card">
      <h3 className="text-sm font-medium text-slate-400 mb-3">{symbol} — Price (180d)</h3>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={displayData} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1c2230" />
          <XAxis
            dataKey="date"
            tickFormatter={(d) => d.slice(5)} // MM-DD
            tick={{ fontSize: 10, fill: "#64748b" }}
            tickLine={false}
            interval={29}
          />
          <YAxis
            domain={["auto", "auto"]}
            tick={{ fontSize: 10, fill: "#64748b" }}
            tickLine={false}
            axisLine={false}
            width={60}
          />
          <Tooltip content={<CustomTooltip />} />
          <Line
            type="monotone"
            dataKey="close"
            stroke="#4e9eff"
            strokeWidth={1.5}
            dot={false}
            activeDot={{ r: 3, fill: "#4e9eff" }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
