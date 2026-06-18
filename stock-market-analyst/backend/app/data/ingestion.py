"""
DataIngestionManager — single entry point for all data fetching.
Handles source fallback, incremental Parquet caching, and symbol normalization.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

import pandas as pd

from backend.app.core.logging import logger
from backend.app.data.cache.parquet_store import load, missing_range, save
from backend.app.data.sources.alpha_vantage_source import AlphaVantageSource
from backend.app.data.sources.yfinance_source import YFinanceSource


DEFAULT_LOOKBACK_DAYS = 365 * 3  # 3 years of history by default


class DataIngestionManager:
    """
    Fetches OHLCV data using the following source priority:
      1. Parquet cache (instant, no API call)
      2. yfinance (free, reliable)
      3. Alpha Vantage (fallback, limited calls)
    """

    def __init__(self):
        self.yf = YFinanceSource()
        self.av = AlphaVantageSource()

    def get_ohlcv(
        self,
        symbol: str,
        start: Optional[date] = None,
        end: Optional[date] = None,
        interval: str = "1d",
        force_refresh: bool = False,
    ) -> pd.DataFrame:
        """
        Main entry point. Returns a DataFrame with columns:
        [open, high, low, close, volume] indexed by date.
        """
        end = end or date.today()
        start = start or (end - timedelta(days=DEFAULT_LOOKBACK_DAYS))

        # ── Step 1: Load from Parquet cache ──────────────────────────────────
        if not force_refresh:
            gap = missing_range(symbol, start, end, interval)
            if gap is None:
                logger.debug(f"[Ingestion] Fully cached | {symbol}")
                df = load(symbol, interval)
                return self._slice(df, start, end)

            fetch_start, fetch_end = gap
        else:
            fetch_start, fetch_end = start, end

        # ── Step 2: Fetch missing data ────────────────────────────────────────
        fresh_df = self._fetch_with_fallback(symbol, fetch_start, fetch_end, interval)

        if fresh_df is not None and not fresh_df.empty:
            save(symbol, fresh_df, interval)

        # ── Step 3: Merge cache + fresh ───────────────────────────────────────
        cached_df = load(symbol, interval)
        if cached_df is None:
            return fresh_df if fresh_df is not None else pd.DataFrame()
        return self._slice(cached_df, start, end)

    def get_multi_ohlcv(
        self,
        symbols: list[str],
        start: Optional[date] = None,
        end: Optional[date] = None,
        column: str = "close",
    ) -> pd.DataFrame:
        """Return a multi-symbol close price DataFrame (wide format)."""
        dfs = {}
        for sym in symbols:
            try:
                df = self.get_ohlcv(sym, start, end)
                if not df.empty:
                    dfs[sym] = df[column]
            except Exception as e:
                logger.warning(f"[Ingestion] Failed to fetch {sym}: {e}")
        if not dfs:
            return pd.DataFrame()
        result = pd.DataFrame(dfs)
        result.index = pd.to_datetime(result.index)
        return result.sort_index()

    def _fetch_with_fallback(
        self,
        symbol: str,
        start: date,
        end: date,
        interval: str,
    ) -> Optional[pd.DataFrame]:
        # Try yfinance first
        try:
            data = self.yf.fetch_ohlcv(symbol, start, end, interval)
            logger.info(f"[Ingestion] yfinance OK | {symbol} | {len(data.df)} rows")
            return data.df
        except Exception as e:
            logger.warning(f"[Ingestion] yfinance failed for {symbol}: {e}")

        # Try Alpha Vantage as fallback
        if self.av.is_available():
            try:
                data = self.av.fetch_ohlcv(symbol, start, end, interval)
                logger.info(f"[Ingestion] Alpha Vantage OK | {symbol} | {len(data.df)} rows")
                return data.df
            except Exception as e:
                logger.warning(f"[Ingestion] Alpha Vantage failed for {symbol}: {e}")

        logger.error(f"[Ingestion] All sources failed for {symbol}")
        return None

    @staticmethod
    def _slice(df: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()
        return df.loc[str(start) : str(end)]
