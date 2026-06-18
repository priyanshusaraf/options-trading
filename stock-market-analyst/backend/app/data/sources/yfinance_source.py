"""
yfinance data source — primary free source for OHLCV + basic fundamentals.
Supports NSE (append .NS), BSE (.BO), and global symbols.
"""
from datetime import date
from typing import Optional

import pandas as pd
import yfinance as yf
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.app.core.cache import cached
from backend.app.core.logging import logger
from .base import BaseDataSource, FundamentalData, OHLCVData


class YFinanceSource(BaseDataSource):
    name = "yfinance"

    @cached(ttl=3600, prefix="yf:ohlcv")
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def fetch_ohlcv(
        self,
        symbol: str,
        start: date,
        end: date,
        interval: str = "1d",
    ) -> OHLCVData:
        logger.info(f"[yfinance] Fetching OHLCV | {symbol} | {start} → {end}")
        ticker = yf.Ticker(symbol)
        df = ticker.history(
            start=start.isoformat(),
            end=end.isoformat(),
            interval=interval,
            auto_adjust=True,
        )
        if df.empty:
            raise ValueError(f"No data returned for {symbol}")

        df.index = pd.to_datetime(df.index).tz_localize(None)
        df.columns = [c.lower() for c in df.columns]
        df = df[["open", "high", "low", "close", "volume"]].dropna()
        currency = ticker.info.get("currency", "USD")
        return OHLCVData(symbol=symbol, df=df, source=self.name, currency=currency, interval=interval)

    @cached(ttl=86400, prefix="yf:fundamentals")
    def fetch_fundamentals(self, symbol: str) -> Optional[FundamentalData]:
        logger.info(f"[yfinance] Fetching fundamentals | {symbol}")
        try:
            info = yf.Ticker(symbol).info
            return FundamentalData(
                symbol=symbol,
                pe_ratio=info.get("trailingPE"),
                pb_ratio=info.get("priceToBook"),
                market_cap=info.get("marketCap"),
                eps=info.get("trailingEps"),
                dividend_yield=info.get("dividendYield"),
                revenue=info.get("totalRevenue"),
                net_income=info.get("netIncomeToCommon"),
                debt_to_equity=info.get("debtToEquity"),
                roe=info.get("returnOnEquity"),
                extra=info,
            )
        except Exception as e:
            logger.warning(f"[yfinance] Fundamentals failed for {symbol}: {e}")
            return None

    @staticmethod
    def nse_symbol(symbol: str) -> str:
        """Convert plain NSE ticker to yfinance format (e.g. RELIANCE → RELIANCE.NS)."""
        if not symbol.endswith((".NS", ".BO")):
            return f"{symbol}.NS"
        return symbol
