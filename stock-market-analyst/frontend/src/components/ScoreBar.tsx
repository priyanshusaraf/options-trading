/**
 * A –1 to +1 score bar. Negative = red left side, positive = green right side.
 */
export function ScoreBar({ score, label }: { score: number; label?: string }) {
  const clamped = Math.max(-1, Math.min(1, score));
  const isPositive = clamped >= 0;
  const pct = Math.abs(clamped) * 50; // 0–50%

  return (
    <div className="flex items-center gap-2">
      {label && <span className="text-xs text-slate-400 w-20 shrink-0">{label}</span>}
      <div className="flex-1 flex items-center h-2 bg-surface-3 rounded-full overflow-hidden">
        {/* Left half */}
        <div className="w-1/2 flex justify-end">
          {!isPositive && (
            <div
              className="h-2 bg-accent-red rounded-l-full"
              style={{ width: `${pct * 2}%` }}
            />
          )}
        </div>
        {/* Center divider */}
        <div className="w-px h-3 bg-slate-500 shrink-0" />
        {/* Right half */}
        <div className="w-1/2">
          {isPositive && (
            <div
              className="h-2 bg-accent-green rounded-r-full"
              style={{ width: `${pct * 2}%` }}
            />
          )}
        </div>
      </div>
      <span
        className={`text-xs font-mono w-12 text-right ${
          clamped > 0 ? "text-accent-green" : clamped < 0 ? "text-accent-red" : "text-slate-400"
        }`}
      >
        {clamped.toFixed(2)}
      </span>
    </div>
  );
}
