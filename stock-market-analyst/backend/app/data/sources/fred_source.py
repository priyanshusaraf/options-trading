"""
FRED (Federal Reserve Economic Data) — macro time series.
Key series: DGS10, FEDFUNDS, CPIAUCSL, GDP, UNRATE, etc.
"""
from datetime import date
from typing import Optional

import pandas as pd
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.app.core.cache import cached
from backend.app.core.config import get_settings
from backend.app.core.logging import logger

FRED_BASE = "https://api.stlouisfed.org/fred"

COMMON_SERIES = {
    "10Y_YIELD": "DGS10",
    "2Y_YIELD": "DGS2",
    "FED_FUNDS": "FEDFUNDS",
    "CPI": "CPIAUCSL",
    "CORE_CPI": "CPILFESL",
    "GDP": "GDP",
    "UNEMPLOYMENT": "UNRATE",
    "INDUSTRIAL_PROD": "INDPRO",
    "VIX": "VIXCLS",
    "YIELD_CURVE_10_2": "T10Y2Y",
    "RETAIL_SALES": "RSAFS",
    "HOUSING_STARTS": "HOUST",
    "OIL_PRICE_WTI": "DCOILWTICO",
}


class FREDSource:
    name = "fred"

    def __init__(self):
        self.api_key = get_settings().fred_key

    def is_available(self) -> bool:
        return bool(self.api_key)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=3, max=20))
    def _get(self, endpoint: str, params: dict) -> dict:
        params["api_key"] = self.api_key
        params["file_type"] = "json"
        resp = requests.get(f"{FRED_BASE}/{endpoint}", params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    @cached(ttl=86400, prefix="fred:series")
    def fetch_series(
        self,
        series_id: str,
        start: Optional[date] = None,
        end: Optional[date] = None,
    ) -> pd.Series:
        logger.info(f"[FRED] Fetching series | {series_id}")
        params: dict = {"series_id": series_id}
        if start:
            params["observation_start"] = start.isoformat()
        if end:
            params["observation_end"] = end.isoformat()
        raw = self._get("series/observations", params)
        observations = raw.get("observations", [])
        records = {}
        for obs in observations:
            if obs["value"] != ".":
                try:
                    records[pd.Timestamp(obs["date"])] = float(obs["value"])
                except ValueError:
                    pass
        return pd.Series(records, name=series_id).sort_index()

    def fetch_common_series(self) -> dict[str, pd.Series]:
        """Batch-fetch all common macro series. Uses cache for each individually."""
        result = {}
        for label, series_id in COMMON_SERIES.items():
            try:
                result[label] = self.fetch_series(series_id)
            except Exception as e:
                logger.warning(f"[FRED] Failed to fetch {label} ({series_id}): {e}")
        return result

    @cached(ttl=86400, prefix="fred:info")
    def series_info(self, series_id: str) -> dict:
        raw = self._get("series", {"series_id": series_id})
        return raw.get("seriess", [{}])[0]
