"""
SQLAlchemy models + engine setup for SQLite metadata store.
Heavy time-series data lives in Parquet; lightweight metadata lives here.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    create_engine,
    String,
    Float,
    Integer,
    Boolean,
    DateTime,
    Text,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from backend.app.core.config import get_settings


class Base(DeclarativeBase):
    pass


# ── Watchlist ──────────────────────────────────────────────────────────────────
class WatchlistItem(Base):
    __tablename__ = "watchlist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    exchange: Mapped[str] = mapped_column(String(10), default="NSE")
    sector: Mapped[Optional[str]] = mapped_column(String(100))
    industry: Mapped[Optional[str]] = mapped_column(String(100))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    quant_scores: Mapped[list["QuantScore"]] = relationship(
        back_populates="watchlist_item", cascade="all, delete-orphan"
    )
    alerts: Mapped[list["Alert"]] = relationship(
        back_populates="watchlist_item", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_watchlist_symbol", "symbol"),)


# ── Portfolio Holdings ──────────────────────────────────────────────────────────
class PortfolioHolding(Base):
    __tablename__ = "portfolio_holdings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    exchange: Mapped[str] = mapped_column(String(10), default="NSE")
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    avg_cost: Mapped[float] = mapped_column(Float, nullable=False)
    instrument_type: Mapped[str] = mapped_column(String(20), default="EQ")
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (Index("ix_portfolio_symbol", "symbol"),)


# ── Quant Scores ───────────────────────────────────────────────────────────────
class QuantScore(Base):
    __tablename__ = "quant_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(
        String(20), ForeignKey("watchlist.symbol"), nullable=False
    )
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Factor scores (–1 to +1)
    momentum_score: Mapped[Optional[float]] = mapped_column(Float)
    value_score: Mapped[Optional[float]] = mapped_column(Float)
    volatility_score: Mapped[Optional[float]] = mapped_column(Float)
    size_score: Mapped[Optional[float]] = mapped_column(Float)
    composite_score: Mapped[Optional[float]] = mapped_column(Float)

    # Risk metrics
    beta: Mapped[Optional[float]] = mapped_column(Float)
    var_95: Mapped[Optional[float]] = mapped_column(Float)
    var_99: Mapped[Optional[float]] = mapped_column(Float)
    max_drawdown: Mapped[Optional[float]] = mapped_column(Float)
    sharpe_ratio: Mapped[Optional[float]] = mapped_column(Float)
    annualized_vol: Mapped[Optional[float]] = mapped_column(Float)

    watchlist_item: Mapped["WatchlistItem"] = relationship(back_populates="quant_scores")

    __table_args__ = (Index("ix_quant_scores_symbol_time", "symbol", "computed_at"),)


# ── Technical Signals ──────────────────────────────────────────────────────────
class TechnicalSignal(Base):
    __tablename__ = "technical_signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    rsi_14: Mapped[Optional[float]] = mapped_column(Float)
    macd_line: Mapped[Optional[float]] = mapped_column(Float)
    macd_signal: Mapped[Optional[float]] = mapped_column(Float)
    macd_hist: Mapped[Optional[float]] = mapped_column(Float)
    bb_upper: Mapped[Optional[float]] = mapped_column(Float)
    bb_lower: Mapped[Optional[float]] = mapped_column(Float)
    bb_pct: Mapped[Optional[float]] = mapped_column(Float)
    ma_20: Mapped[Optional[float]] = mapped_column(Float)
    ma_50: Mapped[Optional[float]] = mapped_column(Float)
    ma_200: Mapped[Optional[float]] = mapped_column(Float)

    # Probabilistic signals (0–1)
    breakout_prob: Mapped[Optional[float]] = mapped_column(Float)
    reversal_prob: Mapped[Optional[float]] = mapped_column(Float)
    trend_strength: Mapped[Optional[float]] = mapped_column(Float)

    __table_args__ = (Index("ix_tech_signals_symbol_time", "symbol", "computed_at"),)


# ── News / Event Summaries ─────────────────────────────────────────────────────
class NewsItem(Base):
    __tablename__ = "news_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(50))
    headline: Mapped[str] = mapped_column(Text)
    url: Mapped[Optional[str]] = mapped_column(Text)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    symbols: Mapped[Optional[str]] = mapped_column(Text)  # JSON list
    sentiment_score: Mapped[Optional[float]] = mapped_column(Float)
    impact_score: Mapped[Optional[float]] = mapped_column(Float)
    event_type: Mapped[Optional[str]] = mapped_column(String(50))

    __table_args__ = (Index("ix_news_published", "published_at"),)


# ── Event Calendar ─────────────────────────────────────────────────────────────
class MarketEvent(Base):
    __tablename__ = "market_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    event_type: Mapped[str] = mapped_column(String(50))
    region: Mapped[Optional[str]] = mapped_column(String(50))
    country: Mapped[Optional[str]] = mapped_column(String(50))
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    affected_sectors: Mapped[Optional[str]] = mapped_column(Text)  # JSON list
    impact_level: Mapped[str] = mapped_column(String(10), default="medium")  # low/medium/high
    actual_value: Mapped[Optional[str]] = mapped_column(String(50))
    forecast_value: Mapped[Optional[str]] = mapped_column(String(50))
    previous_value: Mapped[Optional[str]] = mapped_column(String(50))
    source: Mapped[Optional[str]] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (Index("ix_events_scheduled", "scheduled_at"),)


# ── Alerts ──────────────────────────────────────────────────────────────────────
class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(
        String(20), ForeignKey("watchlist.symbol"), nullable=False
    )
    alert_type: Mapped[str] = mapped_column(String(50))  # price, technical, news, quant
    condition: Mapped[str] = mapped_column(Text)
    threshold: Mapped[Optional[float]] = mapped_column(Float)
    triggered: Mapped[bool] = mapped_column(Boolean, default=False)
    triggered_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    watchlist_item: Mapped["WatchlistItem"] = relationship(back_populates="alerts")


# ── Engine factory ─────────────────────────────────────────────────────────────
def get_engine():
    settings = get_settings()
    url = f"sqlite:///{settings.sqlite_path}"
    return create_engine(url, connect_args={"check_same_thread": False})


def init_db() -> None:
    engine = get_engine()
    Base.metadata.create_all(engine)
