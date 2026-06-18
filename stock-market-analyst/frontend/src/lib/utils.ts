import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export const fmt = {
  pct: (value: number, decimals = 2): string => {
    if (value === null || value === undefined || isNaN(value)) return "—";
    return `${(value * 100).toFixed(decimals)}%`;
  },
  number: (value: number, decimals = 2): string => {
    if (value === null || value === undefined || isNaN(value)) return "—";
    return value.toFixed(decimals);
  },
  large: (value: number): string => {
    if (value === null || value === undefined || isNaN(value)) return "—";
    if (Math.abs(value) >= 1e12) return `${(value / 1e12).toFixed(2)}T`;
    if (Math.abs(value) >= 1e9) return `${(value / 1e9).toFixed(2)}B`;
    if (Math.abs(value) >= 1e6) return `${(value / 1e6).toFixed(2)}M`;
    if (Math.abs(value) >= 1e3) return `${(value / 1e3).toFixed(1)}K`;
    return value.toFixed(2);
  },
  score: (value: number, decimals = 3): string => {
    if (value === null || value === undefined || isNaN(value)) return "—";
    return value.toFixed(decimals);
  },
};

/** @deprecated Use fmt.number / fmt.pct instead */
export function fmtLegacy(value: number, type: "pct" | "number" | "score" = "number", decimals = 2): string {
  if (value === null || value === undefined || isNaN(value)) return "—";
  if (type === "pct") return `${(value * 100).toFixed(decimals)}%`;
  if (type === "score") return value.toFixed(decimals);
  return value.toFixed(decimals);
}

export function signClass(value: number): string {
  if (value > 0.01) return "positive";
  if (value < -0.01) return "negative";
  return "neutral";
}

export function actionBadgeClass(action: string): string {
  const map: Record<string, string> = {
    STRONG_BUY: "badge-strong-buy",
    BUY: "badge-buy",
    HOLD: "badge-hold",
    SELL: "badge-sell",
    STRONG_SELL: "badge-strong-sell",
  };
  return map[action] ?? "badge-hold";
}

export function regimeColor(regime: string): string {
  const map: Record<string, string> = {
    BULL_TREND: "text-accent-green",
    BEAR_TREND: "text-accent-red",
    HIGH_VOL: "text-accent-gold",
    MEAN_REVERTING: "text-accent-blue",
    UNKNOWN: "text-slate-400",
  };
  return map[regime] ?? "text-slate-400";
}
