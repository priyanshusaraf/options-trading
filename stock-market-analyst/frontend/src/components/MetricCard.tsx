import { cn, signClass } from "../lib/utils";

interface MetricCardProps {
  label: string;
  value: string | number;
  sub?: string;
  colorize?: boolean;
  isPercent?: boolean;
  size?: "sm" | "md" | "lg";
}

export function MetricCard({
  label,
  value,
  sub,
  colorize = false,
  size = "md",
}: MetricCardProps) {
  const numVal = typeof value === "number" ? value : parseFloat(String(value));
  const colorClass = colorize && !isNaN(numVal) ? signClass(numVal) : "";

  return (
    <div className="card flex flex-col gap-1">
      <span className="text-xs text-slate-500 uppercase tracking-wide">{label}</span>
      <span
        className={cn(
          "num font-semibold",
          size === "lg" ? "text-2xl" : size === "sm" ? "text-sm" : "text-lg",
          colorClass
        )}
      >
        {typeof value === "number" ? value.toFixed(3) : value}
      </span>
      {sub && <span className="text-xs text-slate-500">{sub}</span>}
    </div>
  );
}
