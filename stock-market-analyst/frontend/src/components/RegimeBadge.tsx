import { regimeColor } from "../lib/utils";

const REGIME_ICONS: Record<string, string> = {
  BULL_TREND: "↑",
  BEAR_TREND: "↓",
  HIGH_VOL: "⚡",
  MEAN_REVERTING: "↔",
  UNKNOWN: "?",
};

export function RegimeBadge({ regime, confidence }: { regime: string; confidence?: number }) {
  return (
    <span className={`inline-flex items-center gap-1 text-sm font-medium ${regimeColor(regime)}`}>
      <span>{REGIME_ICONS[regime] ?? "•"}</span>
      <span>{regime.replace("_", " ")}</span>
      {confidence !== undefined && (
        <span className="text-slate-500 text-xs">({(confidence * 100).toFixed(0)}%)</span>
      )}
    </span>
  );
}
