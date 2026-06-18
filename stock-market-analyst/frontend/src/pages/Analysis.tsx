import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { analysisApi, dataApi } from "../lib/api";
import { MetricCard } from "../components/MetricCard";
import { PriceChart } from "../components/PriceChart";
import { ScoreBar } from "../components/ScoreBar";
import { fmt } from "../lib/utils";
import { Search } from "lucide-react";

export function Analysis() {
  const [symbol, setSymbol] = useState("RELIANCE");
  const [inputVal, setInputVal] = useState("RELIANCE");

  const { data: quant, isLoading: quantLoading } = useQuery({
    queryKey: ["quant", symbol],
    queryFn: () => analysisApi.quant(symbol),
    enabled: !!symbol,
  });

  const { data: technical, isLoading: techLoading } = useQuery({
    queryKey: ["technical", symbol],
    queryFn: () => analysisApi.technical(symbol),
    enabled: !!symbol,
  });

  const { data: ohlcv } = useQuery({
    queryKey: ["ohlcv", symbol],
    queryFn: () => dataApi.ohlcv(symbol, 365),
    enabled: !!symbol,
  });

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setSymbol(inputVal.trim().toUpperCase());
  };

  const signalColor = (sig: string) =>
    sig.includes("BUY") ? "text-accent-green" : sig.includes("SELL") ? "text-accent-red" : "text-slate-400";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Deep Analysis</h1>
        <p className="text-slate-500 text-sm mt-1">Quant + technical breakdown for any symbol</p>
      </div>

      {/* Symbol search */}
      <form onSubmit={handleSearch} className="flex gap-3">
        <input
          type="text"
          value={inputVal}
          onChange={(e) => setInputVal(e.target.value.toUpperCase())}
          placeholder="Enter symbol (e.g. RELIANCE, TCS, INFY)"
          className="flex-1 bg-surface-1 border border-surface-3 rounded-lg px-4 py-2.5 text-white placeholder-slate-500 focus:outline-none focus:border-accent-blue"
        />
        <button
          type="submit"
          className="flex items-center gap-2 px-5 py-2.5 bg-accent-blue/20 hover:bg-accent-blue/30 border border-accent-blue/40 text-accent-blue rounded-lg font-medium transition-colors"
        >
          <Search size={16} />
          Analyze
        </button>
      </form>

      {/* Price chart */}
      {ohlcv && <PriceChart data={ohlcv.data} symbol={symbol} />}

      {/* Technical signals */}
      {(techLoading || technical) && (
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-white">Technical Signals</h2>
            {technical && (
              <span className={`text-sm font-semibold ${signalColor(technical.signal)}`}>
                {technical.signal} ({(technical.confidence * 100).toFixed(0)}% confidence)
              </span>
            )}
          </div>

          {techLoading && <p className="text-slate-500 text-sm">Computing indicators…</p>}

          {technical && (
            <div className="space-y-4">
              {/* Probability bars */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="text-xs text-slate-500 mb-2">Bullish Probability</div>
                  <div className="h-2 bg-surface-3 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-accent-green rounded-full"
                      style={{ width: `${technical.probabilities.bullish * 100}%` }}
                    />
                  </div>
                  <div className="num text-accent-green text-sm mt-1">
                    {(technical.probabilities.bullish * 100).toFixed(1)}%
                  </div>
                </div>
                <div>
                  <div className="text-xs text-slate-500 mb-2">Breakout Probability</div>
                  <div className="h-2 bg-surface-3 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-accent-gold rounded-full"
                      style={{ width: `${technical.probabilities.breakout * 100}%` }}
                    />
                  </div>
                  <div className="num text-accent-gold text-sm mt-1">
                    {(technical.probabilities.breakout * 100).toFixed(1)}%
                  </div>
                </div>
              </div>

              {/* Indicators grid */}
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
                <MetricCard label="RSI (14)" value={technical.indicators.rsi_14} />
                <MetricCard label="ADX (14)" value={technical.indicators.adx_14} />
                <MetricCard label="ATR (14)" value={technical.indicators.atr_14} />
                <MetricCard label="BB %B" value={technical.indicators.bollinger.pct_b} />
                <MetricCard label="MA 20" value={technical.indicators.moving_averages.ma_20} />
                <MetricCard label="MA 50" value={technical.indicators.moving_averages.ma_50} />
                <MetricCard label="MA 200" value={technical.indicators.moving_averages.ma_200} />
                <div className="card">
                  <span className="text-xs text-slate-500 uppercase tracking-wide">MA Cross</span>
                  <span
                    className={`block mt-1 text-sm font-semibold ${
                      technical.indicators.moving_averages.cross === "golden"
                        ? "text-accent-green"
                        : technical.indicators.moving_averages.cross === "death"
                        ? "text-accent-red"
                        : "text-slate-400"
                    }`}
                  >
                    {technical.indicators.moving_averages.cross === "none"
                      ? "No cross"
                      : `${technical.indicators.moving_averages.cross} cross`}
                  </span>
                </div>
              </div>

              {/* MACD */}
              <div className="card bg-surface-2">
                <h3 className="text-xs text-slate-500 uppercase tracking-wide mb-2">MACD (12/26/9)</h3>
                <div className="flex gap-6 text-sm">
                  <span>
                    Line: <span className="num text-white">{technical.indicators.macd.line.toFixed(3)}</span>
                  </span>
                  <span>
                    Signal: <span className="num text-white">{technical.indicators.macd.signal.toFixed(3)}</span>
                  </span>
                  <span>
                    Hist:{" "}
                    <span
                      className={`num ${technical.indicators.macd.histogram > 0 ? "text-accent-green" : "text-accent-red"}`}
                    >
                      {technical.indicators.macd.histogram.toFixed(3)}
                    </span>
                  </span>
                  {technical.indicators.macd.crossover !== "none" && (
                    <span
                      className={`font-medium ${technical.indicators.macd.crossover === "bullish" ? "text-accent-green" : "text-accent-red"}`}
                    >
                      {technical.indicators.macd.crossover} crossover
                    </span>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Quant metrics */}
      {(quantLoading || quant) && (
        <div className="card">
          <h2 className="font-semibold text-white mb-4">Quantitative Analysis</h2>
          {quantLoading && <p className="text-slate-500 text-sm">Computing metrics…</p>}
          {quant && (
            <div className="space-y-5">
              {/* Factor scores */}
              <div>
                <h3 className="text-xs text-slate-500 uppercase tracking-wide mb-3">Factor Exposures</h3>
                <div className="space-y-2">
                  <ScoreBar score={quant.composite_score} label="Composite" />
                  <ScoreBar score={quant.factors.momentum} label="Momentum" />
                  <ScoreBar score={quant.factors.value} label="Value" />
                  <ScoreBar score={quant.factors.volatility} label="Low Vol" />
                  <ScoreBar score={quant.factors.size} label="Size" />
                </div>
              </div>

              {/* Risk metrics */}
              <div>
                <h3 className="text-xs text-slate-500 uppercase tracking-wide mb-3">Risk Metrics</h3>
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
                  <MetricCard label="Annual Vol" value={`${fmt(quant.risk.annualized_vol * 100, "number", 1)}%`} />
                  <MetricCard label="Beta" value={quant.risk.beta} colorize />
                  <MetricCard label="Sharpe" value={quant.ratios.sharpe} colorize />
                  <MetricCard label="Sortino" value={quant.ratios.sortino} colorize />
                  <MetricCard label="Max Drawdown" value={`${fmt(quant.drawdown.max * 100, "number", 1)}%`} colorize />
                  <MetricCard label="VaR 95%" value={`${fmt(quant.var.hist_95 * 100, "number", 2)}%`} />
                  <MetricCard label="CVaR 95%" value={`${fmt(quant.var.cvar_95 * 100, "number", 2)}%`} />
                  <MetricCard label="Annual Return" value={`${fmt(quant.returns.annualized * 100, "number", 1)}%`} colorize />
                </div>
              </div>

              <p className="text-xs text-slate-600">
                Based on {quant.observations} trading days. Alpha (annualized): {fmt(quant.risk.alpha_annualized * 100, "number", 2)}% | R²: {quant.risk.r_squared.toFixed(3)}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
