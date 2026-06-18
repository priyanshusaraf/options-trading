"""
Background Scheduler — autonomous periodic intelligence pipeline.

Jobs:
  1. [Every 4h]   Refresh OHLCV for all watchlist symbols
  2. [Every 1h]   Run quant + technical scores, persist to SQLite
  3. [Every 2h]   Fetch and analyze news for all watchlist symbols
  4. [Every 6h]   Refresh macro data from FRED
  5. [Every 12h]  Refresh event calendar
  6. [Every 24h]  Refresh fundamentals for all watchlist symbols
  7. [Market open] Run full opportunity ranking (Decision Engine)

All jobs are idempotent. Failures are logged but do not crash the server.
Results are stored to SQLite (QuantScore, TechnicalSignal tables) so the
API can serve them instantly without re-computing on every request.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from backend.app.core.config import get_settings
from backend.app.core.logging import logger

if TYPE_CHECKING:
    pass

# ── Job functions ─────────────────────────────────────────────────────────────

async def job_refresh_ohlcv():
    """Fetch any missing OHLCV data for all active watchlist symbols."""
    try:
        from backend.app.data.sources.watchlist_service import WatchlistService
        from backend.app.data.ingestion import DataIngestionManager

        svc = WatchlistService()
        ingestion = DataIngestionManager()
        symbols = svc.symbols()

        if not symbols:
            return

        logger.info(f"[Scheduler] OHLCV refresh — {len(symbols)} symbols")
        end = date.today()
        start = end - timedelta(days=756)

        for sym in symbols:
            try:
                yf_sym = f"{sym}.NS"
                ingestion.get_ohlcv(yf_sym, start, end)
            except Exception as e:
                logger.warning(f"[Scheduler] OHLCV failed for {sym}: {e}")

        logger.info("[Scheduler] OHLCV refresh complete")
    except Exception as e:
        logger.error(f"[Scheduler] job_refresh_ohlcv failed: {e}", exc_info=True)


async def job_compute_scores():
    """
    Run quant + technical analysis for all watchlist symbols.
    Persist latest QuantScore and TechnicalSignal to SQLite.
    """
    try:
        from backend.app.data.sources.watchlist_service import WatchlistService
        from backend.app.data.ingestion import DataIngestionManager
        from backend.app.analytics.quant.engine import QuantEngine
        from backend.app.analytics.technical.engine import TechnicalEngine
        from backend.app.data.sources.yfinance_source import YFinanceSource
        from backend.app.data.models.database import QuantScore, TechnicalSignal, get_engine
        from sqlalchemy.orm import sessionmaker

        svc = WatchlistService()
        ingestion = DataIngestionManager()
        quant_eng = QuantEngine()
        tech_eng = TechnicalEngine()
        yf = YFinanceSource()
        settings = get_settings()

        Session = sessionmaker(bind=get_engine())

        symbols = svc.symbols()
        if not symbols:
            return

        end = date.today()
        start = end - timedelta(days=756)
        bmark = ingestion.get_ohlcv(settings.benchmark_symbol, start, end)

        logger.info(f"[Scheduler] Computing scores — {len(symbols)} symbols")

        for sym in symbols:
            try:
                yf_sym = f"{sym}.NS"
                df = ingestion.get_ohlcv(yf_sym, start, end)
                if df.empty:
                    continue

                fundamentals = yf.fetch_fundamentals(yf_sym)
                qm = quant_eng.compute(
                    symbol=sym,
                    price_df=df,
                    benchmark_df=bmark if not bmark.empty else None,
                    market_cap=fundamentals.market_cap if fundamentals else None,
                    pe_ratio=fundamentals.pe_ratio if fundamentals else None,
                )
                ts = tech_eng.compute(symbol=sym, df=df)

                with Session() as session:
                    # Quant score
                    session.add(QuantScore(
                        symbol=sym,
                        composite_score=qm.composite_score,
                        momentum_score=qm.momentum_score,
                        value_score=qm.value_score,
                        volatility_score=qm.volatility_score,
                        size_score=qm.size_score,
                        beta=qm.beta,
                        var_95=qm.var_95_hist,
                        var_99=qm.var_99_hist,
                        max_drawdown=qm.max_drawdown,
                        sharpe_ratio=qm.sharpe_ratio,
                        annualized_vol=qm.annualized_vol,
                    ))
                    # Technical signal
                    session.add(TechnicalSignal(
                        symbol=sym,
                        rsi_14=ts.rsi_14,
                        macd_line=ts.macd_line,
                        macd_signal=ts.macd_signal,
                        macd_hist=ts.macd_hist,
                        bb_upper=ts.bb_upper,
                        bb_lower=ts.bb_lower,
                        bb_pct=ts.bb_pct,
                        ma_20=ts.ma_20,
                        ma_50=ts.ma_50,
                        ma_200=ts.ma_200,
                        breakout_prob=ts.breakout_prob,
                        reversal_prob=ts.reversal_prob,
                        trend_strength=ts.trend_strength,
                    ))
                    session.commit()

            except Exception as e:
                logger.warning(f"[Scheduler] Score computation failed for {sym}: {e}")

        logger.info("[Scheduler] Score computation complete")
    except Exception as e:
        logger.error(f"[Scheduler] job_compute_scores failed: {e}", exc_info=True)


async def job_refresh_news():
    """Analyze news for all watchlist symbols + broad market."""
    try:
        from backend.app.data.sources.watchlist_service import WatchlistService
        from backend.app.intelligence.news.analyzer import NewsAnalyzer

        svc = WatchlistService()
        analyzer = NewsAnalyzer()

        if not analyzer.finnhub.is_available():
            logger.debug("[Scheduler] Finnhub not configured — skipping news refresh")
            return

        symbols = svc.symbols()
        logger.info(f"[Scheduler] News refresh — {len(symbols)} symbols")

        # Market-wide news first
        analyzer.analyze_market(days=2)

        for sym in symbols:
            try:
                analyzer.analyze_symbol(sym, days=3)
            except Exception as e:
                logger.warning(f"[Scheduler] News failed for {sym}: {e}")

        logger.info("[Scheduler] News refresh complete")
    except Exception as e:
        logger.error(f"[Scheduler] job_refresh_news failed: {e}", exc_info=True)


async def job_refresh_macro():
    """Refresh FRED macro series into cache."""
    try:
        from backend.app.data.sources.fred_source import FREDSource
        fred = FREDSource()
        if not fred.is_available():
            return
        logger.info("[Scheduler] Refreshing macro data from FRED")
        fred.fetch_common_series()
        logger.info("[Scheduler] Macro refresh complete")
    except Exception as e:
        logger.error(f"[Scheduler] job_refresh_macro failed: {e}", exc_info=True)


async def job_refresh_calendar():
    """Pre-populate event calendar cache."""
    try:
        from backend.app.intelligence.events.calendar import EventCalendar
        cal = EventCalendar()
        logger.info("[Scheduler] Refreshing event calendar")
        cal.upcoming(days_ahead=45)
        logger.info("[Scheduler] Calendar refresh complete")
    except Exception as e:
        logger.error(f"[Scheduler] job_refresh_calendar failed: {e}", exc_info=True)


async def job_check_alerts():
    """
    Evaluate all active alerts against current scores.
    Marks alerts as triggered and logs them.
    """
    try:
        from backend.app.data.models.database import Alert, QuantScore, TechnicalSignal, get_engine
        from sqlalchemy.orm import sessionmaker
        from datetime import datetime

        Session = sessionmaker(bind=get_engine())

        with Session() as session:
            alerts = session.query(Alert).filter_by(triggered=False).all()
            if not alerts:
                return

            logger.info(f"[Scheduler] Checking {len(alerts)} active alerts")

            for alert in alerts:
                try:
                    latest_quant = (
                        session.query(QuantScore)
                        .filter_by(symbol=alert.symbol)
                        .order_by(QuantScore.computed_at.desc())
                        .first()
                    )
                    latest_tech = (
                        session.query(TechnicalSignal)
                        .filter_by(symbol=alert.symbol)
                        .order_by(TechnicalSignal.computed_at.desc())
                        .first()
                    )

                    triggered = _evaluate_alert(alert, latest_quant, latest_tech)
                    if triggered:
                        alert.triggered = True
                        alert.triggered_at = datetime.utcnow()
                        logger.info(
                            f"[Alerts] TRIGGERED: {alert.symbol} | {alert.alert_type} | {alert.condition}"
                        )
                except Exception as e:
                    logger.warning(f"[Scheduler] Alert check failed for {alert.symbol}: {e}")

            session.commit()
    except Exception as e:
        logger.error(f"[Scheduler] job_check_alerts failed: {e}", exc_info=True)


def _evaluate_alert(alert, quant, technical) -> bool:
    """Return True if alert condition is met."""
    try:
        t = alert.alert_type
        threshold = alert.threshold or 0.0

        if t == "quant_score" and quant:
            return float(quant.composite_score or 0) >= threshold
        if t == "quant_score_below" and quant:
            return float(quant.composite_score or 0) <= threshold
        if t == "rsi_oversold" and technical:
            return float(technical.rsi_14 or 50) <= threshold
        if t == "rsi_overbought" and technical:
            return float(technical.rsi_14 or 50) >= threshold
        if t == "breakout" and technical:
            return float(technical.breakout_prob or 0) >= threshold
        if t == "macd_bullish_cross" and technical:
            return str(technical.macd_hist or 0) > "0" and quant is not None
        if t == "max_drawdown" and quant:
            return float(quant.max_drawdown or 0) <= threshold  # threshold is negative
    except Exception:
        pass
    return False


# ── Scheduler factory ─────────────────────────────────────────────────────────

def create_scheduler() -> AsyncIOScheduler:
    """
    Build and return a configured APScheduler instance.
    Does NOT start it — call scheduler.start() at app startup.
    """
    scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")

    # OHLCV refresh — every 4 hours on weekdays
    scheduler.add_job(
        job_refresh_ohlcv,
        IntervalTrigger(hours=4),
        id="ohlcv_refresh",
        name="OHLCV Refresh",
        replace_existing=True,
        max_instances=1,
    )

    # Score computation — every 2 hours on weekdays (9am–6pm IST)
    scheduler.add_job(
        job_compute_scores,
        CronTrigger(day_of_week="mon-fri", hour="9-18", minute="0", timezone="Asia/Kolkata"),
        id="score_computation",
        name="Quant+Technical Score Computation",
        replace_existing=True,
        max_instances=1,
    )

    # News refresh — every 2 hours
    scheduler.add_job(
        job_refresh_news,
        IntervalTrigger(hours=2),
        id="news_refresh",
        name="News Intelligence Refresh",
        replace_existing=True,
        max_instances=1,
    )

    # Macro data — every 6 hours
    scheduler.add_job(
        job_refresh_macro,
        IntervalTrigger(hours=6),
        id="macro_refresh",
        name="FRED Macro Refresh",
        replace_existing=True,
        max_instances=1,
    )

    # Event calendar — every 12 hours
    scheduler.add_job(
        job_refresh_calendar,
        IntervalTrigger(hours=12),
        id="calendar_refresh",
        name="Event Calendar Refresh",
        replace_existing=True,
        max_instances=1,
    )

    # Alert checker — every 30 minutes
    scheduler.add_job(
        job_check_alerts,
        IntervalTrigger(minutes=30),
        id="alert_checker",
        name="Alert Evaluation",
        replace_existing=True,
        max_instances=1,
    )

    return scheduler


# ── Singleton ─────────────────────────────────────────────────────────────────

_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = create_scheduler()
    return _scheduler
