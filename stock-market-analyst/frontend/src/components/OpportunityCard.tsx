import { Opportunity } from "../lib/api";
import { actionBadgeClass, fmt, signClass } from "../lib/utils";
import { ScoreBar } from "./ScoreBar";
import { AlertTriangle, TrendingUp } from "lucide-react";

export function OpportunityCard({ opp }: { opp: Opportunity }) {
  const badgeClass = actionBadgeClass(opp.action);

  return (
    <div className="card hover:border-slate-500 transition-colors cursor-default">
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div>
          <h3 className="font-semibold text-white text-lg">{opp.symbol}</h3>
          <span
            className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium mt-1 ${badgeClass}`}
          >
            {opp.action}
          </span>
        </div>
        <div className="text-right">
          <div className="text-xs text-slate-500 mb-1">Confidence</div>
          <div className="text-lg font-mono font-semibold text-accent-gold">
            {fmt(opp.confidence * 100, "number", 0)}%
          </div>
        </div>
      </div>

      {/* Score bars */}
      <div className="space-y-1.5 mb-3">
        <ScoreBar score={opp.score} label="Overall" />
        <ScoreBar score={opp.quant_score} label="Quant" />
        <ScoreBar score={opp.technical_score} label="Technical" />
      </div>

      {/* Suggested weight */}
      {opp.suggested_weight_pct > 0 && (
        <div className="flex items-center gap-2 mb-3 text-sm">
          <TrendingUp size={14} className="text-accent-blue" />
          <span className="text-slate-400">Suggested weight:</span>
          <span className="num text-accent-blue font-medium">{opp.suggested_weight_pct}%</span>
        </div>
      )}

      {/* Reasons */}
      {opp.reasons.length > 0 && (
        <ul className="space-y-1 mb-2">
          {opp.reasons.slice(0, 3).map((r, i) => (
            <li key={i} className="text-xs text-slate-300 flex gap-1.5">
              <span className="text-accent-green mt-0.5 shrink-0">✓</span>
              {r}
            </li>
          ))}
        </ul>
      )}

      {/* Warnings */}
      {opp.warnings.length > 0 && (
        <ul className="space-y-1">
          {opp.warnings.slice(0, 2).map((w, i) => (
            <li key={i} className="text-xs text-accent-gold/80 flex gap-1.5">
              <AlertTriangle size={12} className="shrink-0 mt-0.5" />
              {w}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
