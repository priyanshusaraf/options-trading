import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { alertsApi, AlertItem } from "../lib/api";
import { Bell, BellOff, Plus, Trash2, RefreshCw, CheckCircle } from "lucide-react";

const ALERT_TYPES = [
  { value: "price_above", label: "Price rises above" },
  { value: "price_below", label: "Price falls below" },
  { value: "rsi_oversold", label: "RSI ≤ (oversold)" },
  { value: "rsi_overbought", label: "RSI ≥ (overbought)" },
  { value: "breakout", label: "Breakout probability ≥" },
  { value: "reversal", label: "Reversal probability ≥" },
  { value: "quant_score", label: "Quant score ≥" },
  { value: "quant_score_below", label: "Quant score ≤" },
  { value: "max_drawdown", label: "Drawdown exceeds (negative)" },
  { value: "macd_bullish_cross", label: "MACD bullish crossover" },
  { value: "macd_bearish_cross", label: "MACD bearish crossover" },
];

const alertTypeColor = (type: string): string => {
  if (type.includes("price")) return "text-blue-400";
  if (type.includes("rsi")) return "text-purple-400";
  if (type.includes("breakout") || type.includes("reversal")) return "text-amber-400";
  if (type.includes("quant")) return "text-indigo-400";
  if (type.includes("drawdown")) return "text-red-400";
  if (type.includes("macd")) return "text-cyan-400";
  return "text-gray-400";
};

// ── Alert Card ────────────────────────────────────────────────────────────────

function AlertCard({ alert, onDelete, onReset }: {
  alert: AlertItem;
  onDelete: (id: number) => void;
  onReset: (id: number) => void;
}) {
  return (
    <div
      className={`bg-gray-900 border rounded-xl p-4 ${
        alert.triggered ? "border-green-600/50 bg-green-950/20" : "border-gray-700"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-bold text-white font-mono">{alert.symbol}</span>
            <span className={`text-xs font-medium ${alertTypeColor(alert.alert_type)}`}>
              {ALERT_TYPES.find((t) => t.value === alert.alert_type)?.label ?? alert.alert_type}
            </span>
            {alert.triggered && (
              <span className="text-xs bg-green-500/20 text-green-400 px-2 py-0.5 rounded-full font-medium flex items-center gap-1">
                <CheckCircle size={10} /> Triggered
              </span>
            )}
          </div>
          <p className="text-gray-300 text-sm mt-1">{alert.condition}</p>
          {alert.notes && <p className="text-gray-500 text-xs mt-1 italic">{alert.notes}</p>}
          <div className="flex gap-3 mt-2 text-xs text-gray-500">
            <span>Threshold: <span className="text-gray-300 font-mono">{alert.threshold}</span></span>
            {alert.triggered_at && (
              <span>
                Triggered: {new Date(alert.triggered_at).toLocaleString()}
              </span>
            )}
          </div>
        </div>
        <div className="flex gap-2 shrink-0">
          {alert.triggered && (
            <button
              onClick={() => onReset(alert.id)}
              className="p-1.5 text-gray-400 hover:text-amber-400 transition-colors rounded"
              title="Re-arm alert"
            >
              <RefreshCw size={14} />
            </button>
          )}
          <button
            onClick={() => onDelete(alert.id)}
            className="p-1.5 text-gray-400 hover:text-red-400 transition-colors rounded"
            title="Delete alert"
          >
            <Trash2 size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Create Alert Form ─────────────────────────────────────────────────────────

function CreateAlertForm({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    symbol: "",
    alert_type: "price_above",
    threshold: "",
    notes: "",
  });

  const mutation = useMutation({
    mutationFn: () =>
      alertsApi.create({
        symbol: form.symbol.toUpperCase(),
        alert_type: form.alert_type,
        threshold: parseFloat(form.threshold) || 0,
        notes: form.notes,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
      onClose();
    },
  });

  return (
    <div className="bg-gray-900 border border-gray-700 rounded-xl p-5">
      <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
        <Plus size={16} /> New Alert
      </h3>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-gray-400 mb-1 block">Symbol</label>
          <input
            value={form.symbol}
            onChange={(e) => setForm({ ...form, symbol: e.target.value.toUpperCase() })}
            placeholder="RELIANCE"
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm"
          />
        </div>
        <div>
          <label className="text-xs text-gray-400 mb-1 block">Alert Type</label>
          <select
            value={form.alert_type}
            onChange={(e) => setForm({ ...form, alert_type: e.target.value })}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm"
          >
            {ALERT_TYPES.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-xs text-gray-400 mb-1 block">Threshold</label>
          <input
            type="number"
            value={form.threshold}
            onChange={(e) => setForm({ ...form, threshold: e.target.value })}
            placeholder="e.g. 2500 or 30"
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm"
          />
        </div>
        <div>
          <label className="text-xs text-gray-400 mb-1 block">Notes (optional)</label>
          <input
            value={form.notes}
            onChange={(e) => setForm({ ...form, notes: e.target.value })}
            placeholder="Why you set this alert"
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm"
          />
        </div>
      </div>
      <div className="flex gap-2 mt-4">
        <button
          onClick={() => mutation.mutate()}
          disabled={!form.symbol || !form.threshold || mutation.isPending}
          className="flex-1 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white py-2 rounded-lg text-sm font-medium transition-colors"
        >
          {mutation.isPending ? "Creating..." : "Create Alert"}
        </button>
        <button
          onClick={onClose}
          className="px-4 bg-gray-800 hover:bg-gray-700 text-gray-300 py-2 rounded-lg text-sm transition-colors"
        >
          Cancel
        </button>
      </div>
      {mutation.isError && (
        <p className="text-red-400 text-xs mt-2">Failed to create alert. Check symbol and threshold.</p>
      )}
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function AlertsPage() {
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [filter, setFilter] = useState<"all" | "active" | "triggered">("all");

  const { data: alerts = [], isLoading } = useQuery<AlertItem[]>({
    queryKey: ["alerts"],
    queryFn: () => alertsApi.list(),
    refetchInterval: 60 * 1000,
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => alertsApi.delete(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["alerts"] }),
  });

  const resetMutation = useMutation({
    mutationFn: (id: number) => alertsApi.reset(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["alerts"] }),
  });

  const evaluateMutation = useMutation({
    mutationFn: () => alertsApi.evaluateAll(),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
      alert(`Evaluation complete — ${result.newly_triggered} alert(s) triggered`);
    },
  });

  const filteredAlerts = alerts.filter((a) => {
    if (filter === "active") return !a.triggered;
    if (filter === "triggered") return a.triggered;
    return true;
  });

  const activeCount = alerts.filter((a) => !a.triggered).length;
  const triggeredCount = alerts.filter((a) => a.triggered).length;

  return (
    <div className="space-y-6">
      {/* ── Header ── */}
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Bell size={22} className="text-amber-400" />
            Alerts
          </h1>
          <p className="text-gray-400 text-sm mt-1">
            Automated alerts for price, technical, quant signals, and MACD crossovers
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => evaluateMutation.mutate()}
            disabled={evaluateMutation.isPending}
            className="flex items-center gap-2 px-3 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg text-sm transition-colors"
          >
            <RefreshCw size={14} className={evaluateMutation.isPending ? "animate-spin" : ""} />
            Evaluate Now
          </button>
          <button
            onClick={() => setShowCreate(!showCreate)}
            className="flex items-center gap-2 px-3 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-medium transition-colors"
          >
            <Plus size={14} /> New Alert
          </button>
        </div>
      </div>

      {/* ── Stats ── */}
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-gray-900 border border-gray-700 rounded-xl p-4 text-center">
          <div className="text-2xl font-bold text-white">{alerts.length}</div>
          <div className="text-xs text-gray-400 mt-1">Total Alerts</div>
        </div>
        <div className="bg-gray-900 border border-gray-700 rounded-xl p-4 text-center">
          <div className="text-2xl font-bold text-amber-400">{activeCount}</div>
          <div className="text-xs text-gray-400 mt-1">Active</div>
        </div>
        <div className="bg-gray-900 border border-gray-700 rounded-xl p-4 text-center">
          <div className="text-2xl font-bold text-green-400">{triggeredCount}</div>
          <div className="text-xs text-gray-400 mt-1">Triggered</div>
        </div>
      </div>

      {/* ── Create Form ── */}
      {showCreate && <CreateAlertForm onClose={() => setShowCreate(false)} />}

      {/* ── Filter Tabs ── */}
      <div className="flex gap-2">
        {(["all", "active", "triggered"] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium capitalize transition-colors ${
              filter === f
                ? "bg-indigo-600 text-white"
                : "bg-gray-800 text-gray-400 hover:text-white hover:bg-gray-700"
            }`}
          >
            {f}
          </button>
        ))}
      </div>

      {/* ── Alert List ── */}
      {isLoading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="animate-pulse h-24 bg-gray-800 rounded-xl" />
          ))}
        </div>
      ) : filteredAlerts.length === 0 ? (
        <div className="text-center py-16">
          <BellOff size={36} className="text-gray-600 mx-auto mb-3" />
          <p className="text-gray-400 font-medium">No alerts</p>
          <p className="text-gray-600 text-sm mt-1">Create an alert to get notified when conditions are met</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredAlerts.map((a) => (
            <AlertCard
              key={a.id}
              alert={a}
              onDelete={(id) => deleteMutation.mutate(id)}
              onReset={(id) => resetMutation.mutate(id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
