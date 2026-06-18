"""
Alpha Vantage — technical indicators + macro indicators.
Free tier: 25 calls/day. Use cache aggressively.
"""
from datetime import date
from typing import Optional

import pandas as pd
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.app.core.cache import cached
from backend.app.core.config import get_settings
from backend.app.core.logging import logger
from .base import BaseDataSource, OHLCVData

AV_BASE = "https://www.alphavantage.co/query"


class AlphaVantageSource(BaseDataSource):
    name = "alpha_vantage"

    def __init__(self):
        self.api_key = get_settings().alpha_vantage_key

    def is_available(self) -> bool:
        return bool(self.api_key)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=5, max=30))
    def _get(self, params: dict) -> dict:
        params["apikey"] = self.api_key
        resp = requests.get(AV_BASE, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if "Note" in data:
            raise RuntimeError("Alpha Vantage rate limit hit")
        if "Error Message" in data:
            raise ValueError(f"Alpha Vantage error: {data['Error Message']}")
        return data

    @cached(ttl=3600, prefix="av:ohlcv")
    def fetch_ohlcv(
        self,
        symbol: str,
        start: date,
        end: date,
        interval: str = "1d",
    ) -> OHLCVData:
        func_map = {"1d": "TIME_SERIES_DAILY_ADJUSTED", "1wk": "TIME_SERIES_WEEKLY_ADJUSTED"}
        func = func_map.get(interval, "TIME_SERIES_DAILY_ADJUSTED")
        logger.info(f"[alpha_vantage] Fetching OHLCV | {symbol}")
        raw = self._get({"function": func, "symbol": symbol, "outputsize": "full"})

        ts_key = next((k for k in raw if "Time Series" in k), None)
        if not ts_key:
            raise ValueError(f"Unexpected response structure: {list(raw.keys())}")

        records = []
        for date_str, vals in raw[ts_key].items():
            records.append(
                {
                    "date": pd.Timestamp(date_str),
                    "open": float(vals.get("1. open", vals.get("1a. open (USD)", 0))),
                    "high": float(vals.get("2. high", vals.get("2a. high (USD)", 0))),
                    "low": float(vals.get("3. low", vals.get("3a. low (USD)", 0))),
                    "close": float(vals.get("4. close", vals.get("4a. close (USD)", 0))),
                    "volume": float(vals.get("6. volume", vals.get("5. volume", 0))),
                }
            )
        df = pd.DataFrame(records).set_index("date").sort_index()
        df = df.loc[str(start) : str(end)]
        return OHLCVData(symbol=symbol, df=df, source=self.name, interval=interval)

    @cached(ttl=3600, prefix="av:indicator")
    def fetch_indicator(self, symbol: str, indicator: str, **kwargs) -> pd.Series:
        """Fetch a single technical indicator from Alpha Vantage."""
        params = {"function": indicator, "symbol": symbol, "interval": "daily", **kwargs}
        logger.info(f"[alpha_vantage] Indicator {indicator} | {symbol}")
        raw = self._get(params)
        meta_key = next((k for k in raw if "Technical" in k or "Meta" in k), None)
        data_key = next((k for k in raw if "Technical" not in k and "Meta" not in k), None)
        if not data_key:
            raise ValueError(f"Cannot parse indicator response: {list(raw.keys())}")
        records = {pd.Timestamp(k): float(list(v.values())[0]) for k, v in raw[data_key].items()}
        return pd.Series(records).sort_index()

    @cached(ttl=7200, prefix="av:macro")
    def fetch_macro_series(self, series_id: str) -> pd.Series:
        """
        Fetch a macro time series (e.g. REAL_GDP, INFLATION, FEDERAL_FUNDS_RATE).
        """
        logger.info(f"[alpha_vantage] Macro series | {series_id}")
        raw = self._get({"function": series_id})
        if "data" not in raw:
            raise ValueError(f"No 'data' field for {series_id}")
        records = {pd.Timestamp(d["date"]): float(d["value"]) for d in raw["data"] if d["value"] != "."}
        return pd.Series(records).sort_index()
