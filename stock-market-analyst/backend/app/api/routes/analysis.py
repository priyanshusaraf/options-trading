"""
Analysis endpoints — run quant, technical, and regime analysis on demand.
"""
from datetime import date, timedelta
from typing import Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.app.analytics.quant.engine import QuantEngine
from backend.app.analytics.technical.engine import TechnicalEngine
from backend.app.data.ingestion import DataIngestionManager
from backend.app.data.sources.yfinance_source import YFinanceSource
from backend.app.data.sources.watchlist_service import WatchlistService
from backend.app.decision.engine import DecisionEngine
from backend.app.decision.position_sizer import PositionSizer, SizingConfig
from backend.app.intelligence.regime.detector import RegimeDetector
from backend.app.core.config import get_settings
from backend.app.core.logging import logger

router = APIRouter(prefix="/analysis", tags=["Analysis"])

_ingestion = DataIngestionManager()
_quant = QuantEngine()
_technical = TechnicalEngine()
_regime = RegimeDetector()
_decision = DecisionEngine()
_watchlist = WatchlistService()
_yf = YFinanceSource()


def _yf_sym(symbol: str, exchange: str = "NSE") -> str:
    if exchange == "NSE" and not symbol.endswith((".NS", ".BO")):
        return f"{symbol}.NS"
    return symbol


# ── Quant Analysis ────────────────────────────────────────────────────────────

@router.get("/quant/{symbol}")
def quant_analysis(
    symbol: str,
    days: int = Query(756, ge=60, le=3650),
    exchange: str = Query("NSE"),
):
    """Run full quantitative analysis for a symbol."""
    end = date.today()
    start = end - timedelta(days=days)
    yf_sym = _yf_sym(symbol, exchange)
    benchmark_sym = get_settings().benchmark_symbol

    try:
        price_df = _ingestion.get_ohlcv(yf_sym, start, end)
        if price_df.empty:
            raise HTTPException(status_code=404, detail=f"No price data for {symbol}")

        benchmark_df = _ingestion.get_ohlcv(benchmark_sym, start, end)
        fundamentals = _yf.fetch_fundamentals(yf_sym)

        metrics = _quant.compute(
            symbol=symbol,
            price_df=price_df,
            benchmark_df=benchmark_df if not benchmark_df.empty else None,
            market_cap=fundamentals.market_cap if fundamentals else None,
            pe_ratio=fundamentals.pe_ratio if fundamentals else None,
        )

        return {
            "symbol": symbol,
            "observations": metrics.observations,
            "returns": {
                "total": round(metrics.total_return, 4),
                "annualized": round(metrics.annualized_return, 4),
            },
            "risk": {
                "annualized_vol": round(metrics.annualized_vol, 4),
                "rolling_vol_30d": round(metrics.rolling_vol_30d, 4),
                "rolling_vol_90d": round(metrics.rolling_vol_90d, 4),
                "beta": round(metrics.beta, 3),
                "alpha_annualized": round(metrics.alpha, 4),
                "r_squared": round(metrics.r_squared, 3),
            },
            "ratios": {
                "sharpe": round(metrics.sharpe_ratio, 3),
                "sortino": round(metrics.sortino_ratio, 3),
                "calmar": round(metrics.calmar_ratio, 3),
            },
            "var": {
                "hist_95": round(metrics.var_95_hist, 4),
                "hist_99": round(metrics.var_99_hist, 4),
                "param_95": round(metrics.var_95_param, 4),
                "cvar_95": round(metrics.cvar_95, 4),
            },
            "drawdown": {
                "max": round(metrics.max_drawdown, 4),
                "current": round(metrics.current_drawdown, 4),
                "duration_days": metrics.drawdown_duration_days,
            },
            "factors": {
                "momentum": round(metrics.momentum_score, 3),
                "volatility": round(metrics.volatility_score, 3),
                "value": round(metrics.value_score, 3),
                "size": round(metrics.size_score, 3),
            },
            "composite_score": round(metrics.composite_score, 3),
            "distribution": {
                "skewness": round(metrics.skewness, 3),
                "kurtosis": round(metrics.kurtosis, 3),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Quant analysis failed for {symbol}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ── Technical Analysis ────────────────────────────────────────────────────────

@router.get("/technical/{symbol}")
def technical_analysis(
    symbol: str,
    days: int = Query(365, ge=60, le=1095),
    exchange: str = Query("NSE"),
):
    """Run technical analysis and return probabilistic signals."""
    end = date.today()
    start = end - timedelta(days=days)
    yf_sym = _yf_sym(symbol, exchange)

    try:
        df = _ingestion.get_ohlcv(yf_sym, start, end)
        if df.empty:
            raise HTTPException(status_code=404, detail=f"No data for {symbol}")

        signals = _technical.compute(symbol=symbol, df=df)

        return {
            "symbol": symbol,
            "signal": signals.signal,
            "confidence": signals.confidence,
            "probabilities": {
                "bullish": signals.bullish_prob,
                "bearish": signals.bearish_prob,
                "breakout": signals.breakout_prob,
                "reversal": signals.reversal_prob,
            },
            "indicators": {
                "rsi_14": round(signals.rsi_14, 2),
                "macd": {
                    "line": round(signals.macd_line, 4),
                    "signal": round(signals.macd_signal, 4),
                    "histogram": round(signals.macd_hist, 4),
                    "crossover": signals.macd_crossover,
                },
                "bollinger": {
                    "upper": round(signals.bb_upper, 2),
                    "middle": round(signals.bb_middle, 2),
                    "lower": round(signals.bb_lower, 2),
                    "pct_b": round(signals.bb_pct, 3),
                    "bandwidth": round(signals.bb_width, 4),
                },
                "moving_averages": {
                    "ma_20": round(signals.ma_20, 2),
                    "ma_50": round(signals.ma_50, 2),
                    "ma_200": round(signals.ma_200, 2),
                    "cross": signals.ma_cross,
                },
                "atr_14": round(signals.atr_14, 2),
                "adx_14": round(signals.adx_14, 2),
                "trend_strength": round(signals.trend_strength, 3),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Technical analysis failed for {symbol}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ── Correlation Matrix ────────────────────────────────────────────────────────

@router.get("/correlation")
def correlation_matrix(
    symbols: Optional[str] = Query(None, description="Comma-separated symbols; if omitted uses watchlist"),
    days: int = Query(252, ge=30, le=1095),
    exchange: str = Query("NSE"),
):
    """Return pairwise correlation matrix for a list of symbols (defaults to watchlist)."""
    if symbols:
        sym_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    else:
        sym_list = _watchlist.symbols()

    if len(sym_list) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 symbols")

    end = date.today()
    start = end - timedelta(days=days)
    yf_syms = [_yf_sym(s, exchange) for s in sym_list]

    prices = _ingestion.get_multi_ohlcv(yf_syms, start, end)
    if prices.empty:
        raise HTTPException(status_code=404, detail="No price data returned")

    # Map yfinance symbols back to clean names
    prices.columns = [c.replace(".NS", "").replace(".BO", "") for c in prices.columns]
    corr = _quant.correlation_matrix(prices)

    return {
        "symbols": list(corr.columns),
        "matrix": corr.round(4).to_dict(),
        "period_days": days,
    }


# ── Rolling Correlation ───────────────────────────────────────────────────────

@router.get("/rolling-correlation")
def rolling_correlation_pair(
    symbol1: str = Query(...),
    symbol2: str = Query(...),
    window: int = Query(30, ge=10, le=90),
    days: int = Query(504, ge=120, le=1095),
    exchange: str = Query("NSE"),
):
    """Compute rolling pairwise correlation between two symbols."""
    end = date.today()
    start = end - timedelta(days=days)
    yf1 = _yf_sym(symbol1, exchange)
    yf2 = _yf_sym(symbol2, exchange)

    df1 = _ingestion.get_ohlcv(yf1, start, end)
    df2 = _ingestion.get_ohlcv(yf2, start, end)

    if df1.empty or df2.empty:
        raise HTTPException(status_code=404, detail="No price data for one or both symbols")

    close1 = df1["close"] if "close" in df1.columns else df1.iloc[:, 3]
    close2 = df2["close"] if "close" in df2.columns else df2.iloc[:, 3]

    combined = pd.DataFrame({symbol1: close1, symbol2: close2}).dropna()
    returns = combined.pct_change().dropna()
    rolling = returns[symbol1].rolling(window).corr(returns[symbol2]).dropna()

    return {
        "symbol1": symbol1,
        "symbol2": symbol2,
        "window": window,
        "rolling_correlation": {
            str(k.date()): round(v, 4)
            for k, v in rolling.items()
            if not pd.isna(v)
        },
        "latest": round(float(rolling.iloc[-1]), 4) if len(rolling) else None,
        "mean": round(float(rolling.mean()), 4) if len(rolling) else None,
        "min": round(float(rolling.min()), 4) if len(rolling) else None,
        "max": round(float(rolling.max()), 4) if len(rolling) else None,
    }


# ── Market Regime ─────────────────────────────────────────────────────────────

@router.get("/regime")
def market_regime(days: int = Query(365, ge=90, le=1095)):
    """Detect the current market regime using the benchmark index."""
    benchmark_sym = get_settings().benchmark_symbol
    end = date.today()
    start = end - timedelta(days=days)

    try:
        df = _ingestion.get_ohlcv(benchmark_sym, start, end)
        if df.empty:
            raise HTTPException(status_code=404, detail="No benchmark data available")

        result = _regime.detect(df)
        return {
            "regime": result.regime.value,
            "confidence": result.confidence,
            "vol_regime": result.vol_regime,
            "trend_strength": result.trend_strength,
            "is_trending": result.is_trending,
            "is_mean_reverting": result.is_mean_reverting,
            "realized_vol_30d": round(result.realized_vol_30d, 4),
            "realized_vol_90d": round(result.realized_vol_90d, 4),
            "description": result.description,
            "signal_adjustments": {
                "momentum_weight": result.momentum_weight_adj,
                "mean_reversion_weight": result.mean_reversion_weight_adj,
                "vol_risk_discount": result.vol_risk_discount,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Regime detection failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ── Full Decision Engine ──────────────────────────────────────────────────────

@router.get("/opportunities")
def get_opportunities(
    days: int = Query(756, ge=60),
    exchange: str = Query("NSE"),
    limit: int = Query(20, ge=1, le=100),
):
    """
    Run the full decision engine across the entire watchlist.
    Returns ranked buy/sell opportunities with reasoning.
    """
    symbols = _watchlist.symbols(exchange=exchange)
    if not symbols:
        return {"opportunities": [], "regime": None, "message": "Watchlist is empty"}

    end = date.today()
    start = end - timedelta(days=days)
    benchmark_sym = get_settings().benchmark_symbol

    # Get benchmark for regime detection
    bmark_df = _ingestion.get_ohlcv(benchmark_sym, start, end)
    regime_result = _regime.detect(bmark_df) if not bmark_df.empty else None

    opportunities = []
    for sym in symbols[:limit]:
        try:
            yf_sym = _yf_sym(sym, exchange)
            price_df = _ingestion.get_ohlcv(yf_sym, start, end)
            if price_df.empty:
                continue

            fundamentals = _yf.fetch_fundamentals(yf_sym)
            quant_m = _quant.compute(
                symbol=sym,
                price_df=price_df,
                benchmark_df=bmark_df if not bmark_df.empty else None,
                market_cap=fundamentals.market_cap if fundamentals else None,
                pe_ratio=fundamentals.pe_ratio if fundamentals else None,
            )
            tech_s = _technical.compute(symbol=sym, df=price_df)

            opp = _decision.evaluate(
                symbol=sym,
                quant=quant_m,
                technical=tech_s,
                regime=regime_result,
            )
            opportunities.append(opp)
        except Exception as e:
            logger.warning(f"Skipping {sym} due to error: {e}")
            continue

    ranked = _decision.rank(opportunities)

    # ── Position sizing ────────────────────────────────────────────────────────
    sizer = PositionSizer()
    sizing_inputs = []
    for opp in ranked:
        quant_data = opp.metrics_summary.get("quant", {})
        sizing_inputs.append({
            "symbol": opp.symbol,
            "score": opp.score,
            "confidence": opp.confidence,
            "annual_vol": quant_data.get("annualized_vol", 0.25),
            "sector": "unknown",
        })

    # Fetch returns matrix for correlation adjustment
    prices = _ingestion.get_multi_ohlcv(
        [f"{s}.NS" for s in symbols[:limit]], start, end
    ) if symbols else None

    allocation = sizer.allocate(sizing_inputs, returns_matrix=prices)

    # Map allocations back to opportunities
    alloc_map = {s.symbol: s.final_pct for s in allocation.suggestions}

    return {
        "regime": regime_result.regime.value if regime_result else None,
        "portfolio_sizing": {
            "total_allocated_pct": allocation.total_allocated_pct,
            "cash_pct": allocation.cash_pct,
            "expected_portfolio_vol": allocation.expected_portfolio_vol,
            "diversification_ratio": allocation.diversification_ratio,
            "sector_breakdown": allocation.sector_breakdown,
            "warnings": allocation.warnings,
        },
        "opportunities": [
            {
                "symbol": o.symbol,
                "action": o.action,
                "score": o.score,
                "confidence": o.confidence,
                "suggested_weight_pct": alloc_map.get(o.symbol, o.suggested_weight),
                "quant_score": round(o.quant_score, 3),
                "technical_score": round(o.technical_score, 3),
                "reasons": o.reasons,
                "warnings": o.warnings,
                "metrics": o.metrics_summary,
            }
            for o in ranked
        ],
    }


# ── Dedicated position-sizing endpoint ────────────────────────────────────────

class SizingRequest(BaseModel):
    symbols: list[str]
    kelly_fraction: float = 0.5
    max_position_pct: float = 10.0
    max_sector_pct: float = 35.0
    method: str = "combined"


@router.post("/position-sizing", summary="Compute optimal position sizes for a list of symbols")
def compute_position_sizing(req: SizingRequest):
    """
    Given a list of symbols, run quant + technical analysis, then apply
    the Kelly / vol-parity position sizing engine to output suggested allocation.
    """
    start = date.today() - timedelta(days=756)
    end = date.today()
    settings = get_settings()

    bmark = _ingestion.get_ohlcv(settings.benchmark_symbol, start, end)

    inputs = []
    prices_dict = {}
    for sym in req.symbols:
        try:
            yf_sym = f"{sym}.NS"
            df = _ingestion.get_ohlcv(yf_sym, start, end)
            if df.empty:
                continue
            fundamentals = _yf.fetch_fundamentals(yf_sym)
            qm = _quant.compute(
                symbol=sym, price_df=df,
                benchmark_df=bmark if not bmark.empty else None,
                market_cap=fundamentals.market_cap if fundamentals else None,
                pe_ratio=fundamentals.pe_ratio if fundamentals else None,
            )
            ts = _technical.compute(symbol=sym, df=df)
            score = round((qm.composite_score + ts.breakout_prob - ts.reversal_prob) / 3, 3)
            inputs.append({
                "symbol": sym,
                "score": score,
                "confidence": min(abs(score) * 1.5, 1.0),
                "annual_vol": qm.annualized_vol,
                "sector": "unknown",
            })
            prices_dict[sym] = df["close"] if "close" in df.columns else df.iloc[:, 3]
        except Exception as e:
            logger.warning(f"Position sizing skipping {sym}: {e}")

    if not inputs:
        raise HTTPException(status_code=400, detail="No valid symbols with data found")

    returns_df = pd.DataFrame(prices_dict) if prices_dict else None
    config = SizingConfig(
        kelly_fraction=req.kelly_fraction,
        max_position_pct=req.max_position_pct,
        max_sector_pct=req.max_sector_pct,
        method=req.method,
    )
    sizer = PositionSizer(config)
    result = sizer.allocate(inputs, returns_matrix=returns_df)

    return {
        "total_allocated_pct": result.total_allocated_pct,
        "cash_pct": result.cash_pct,
        "expected_portfolio_vol": result.expected_portfolio_vol,
        "diversification_ratio": result.diversification_ratio,
        "sector_breakdown": result.sector_breakdown,
        "warnings": result.warnings,
        "positions": [
            {
                "symbol": s.symbol,
                "final_pct": s.final_pct,
                "raw_kelly_pct": s.raw_kelly_pct,
                "vol_parity_pct": s.vol_parity_pct,
                "score": s.score,
                "confidence": s.confidence,
                "annual_vol_pct": round(s.annual_vol * 100, 1),
                "capped": s.capped,
                "reason": s.reason,
            }
            for s in result.suggestions
        ],
    }
