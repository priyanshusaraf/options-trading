"""
Watchlist CRUD service — the primary entry point for managing tracked symbols.
Backed by SQLite via SQLAlchemy.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date, timedelta
from typing import Optional

from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.logging import logger
from backend.app.data.models.database import WatchlistItem, get_engine
from backend.app.data.ingestion import DataIngestionManager


SessionLocal = sessionmaker(
    bind=get_engine(),
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,  # Keep attributes accessible after session.commit()
)


@contextmanager
def db_session():
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


class WatchlistService:
    def __init__(self):
        self.ingestion = DataIngestionManager()

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def add(
        self,
        symbol: str,
        exchange: str = "NSE",
        sector: Optional[str] = None,
        industry: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Optional[WatchlistItem]:
        """Add a symbol + trigger OHLCV pre-fetch (blocking). Use add_direct for async routes."""
        item = self.add_direct(symbol, exchange, sector, industry, notes)
        if item:
            try:
                yf_symbol = f"{symbol}.NS" if exchange == "NSE" else (f"{symbol}.BO" if exchange == "BSE" else symbol)
                end = date.today()
                start = end - timedelta(days=365 * 3)
                self.ingestion.get_ohlcv(yf_symbol, start, end)
                logger.info(f"[Watchlist] Pre-fetched OHLCV for {symbol}")
            except Exception as e:
                logger.warning(f"[Watchlist] Pre-fetch failed for {symbol}: {e}")
        return self.get(symbol)

    def add_direct(
        self,
        symbol: str,
        exchange: str = "NSE",
        sector: Optional[str] = None,
        industry: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Optional[WatchlistItem]:
        """Add symbol to DB only — no blocking OHLCV fetch. Returns a safely detached copy."""
        with db_session() as db:
            existing = db.query(WatchlistItem).filter_by(symbol=symbol).first()
            if existing:
                if not existing.is_active:
                    existing.is_active = True
                    logger.info(f"[Watchlist] Re-activated {symbol}")
                else:
                    logger.info(f"[Watchlist] {symbol} already in watchlist")
                # Flush & expunge so we can safely return the item
                db.flush()
                db.expunge(existing)
                return existing
            else:
                item = WatchlistItem(
                    symbol=symbol,
                    exchange=exchange,
                    sector=sector,
                    industry=industry,
                    notes=notes,
                )
                db.add(item)
                db.flush()  # Assigns the id
                db.expunge(item)
                logger.info(f"[Watchlist] Added {symbol} ({exchange})")
                return item

    def remove(self, symbol: str, hard_delete: bool = False) -> bool:
        """Soft-delete (deactivate) or hard-delete a symbol."""
        with db_session() as db:
            item = db.query(WatchlistItem).filter_by(symbol=symbol).first()
            if not item:
                return False
            if hard_delete:
                db.delete(item)
            else:
                item.is_active = False
            logger.info(f"[Watchlist] Removed {symbol} (hard={hard_delete})")
        return True

    def update(
        self,
        symbol: str,
        sector: Optional[str] = None,
        industry: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Optional[WatchlistItem]:
        with db_session() as db:
            item = db.query(WatchlistItem).filter_by(symbol=symbol, is_active=True).first()
            if not item:
                return None
            if sector is not None:
                item.sector = sector
            if industry is not None:
                item.industry = industry
            if notes is not None:
                item.notes = notes
        return self.get(symbol)

    def get(self, symbol: str) -> Optional[WatchlistItem]:
        with db_session() as db:
            item = db.query(WatchlistItem).filter_by(symbol=symbol, is_active=True).first()
            if item:
                db.expunge(item)  # Detach safely so attributes remain after session close
            return item

    def list_all(self, include_inactive: bool = False) -> list[WatchlistItem]:
        with db_session() as db:
            q = db.query(WatchlistItem)
            if not include_inactive:
                q = q.filter_by(is_active=True)
            items = q.order_by(WatchlistItem.added_at.desc()).all()
            for item in items:
                db.expunge(item)
            return items

    def symbols(self, exchange: Optional[str] = None) -> list[str]:
        """Return just the symbol strings from the active watchlist."""
        with db_session() as db:
            q = db.query(WatchlistItem.symbol).filter_by(is_active=True)
            if exchange:
                q = q.filter_by(exchange=exchange)
            return [row[0] for row in q.all()]

    # ── Bulk operations ───────────────────────────────────────────────────────

    def add_bulk(self, items: list[dict]) -> list[WatchlistItem]:
        """
        items: list of dicts with keys: symbol, exchange, sector, industry, notes
        """
        return [self.add(**item) for item in items]

    def get_ohlcv(
        self,
        symbol: str,
        days: int = 365,
        yf_suffix: str = ".NS",
    ):
        """Convenience: fetch OHLCV for a watchlist symbol."""
        end = date.today()
        start = end - timedelta(days=days)
        yf_symbol = f"{symbol}{yf_suffix}" if not symbol.endswith((".NS", ".BO")) else symbol
        return self.ingestion.get_ohlcv(yf_symbol, start, end)
