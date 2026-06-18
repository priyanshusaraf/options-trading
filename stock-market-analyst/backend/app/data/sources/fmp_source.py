"""
Financial Modeling Prep — fundamentals, DCF, income/balance/cash-flow statements.
Free tier: 250 calls/day.
"""
from datetime import date
from typing import Optional

import pandas as pd
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.app.core.cache import cached
from backend.app.core.config import get_settings
from backend.app.core.logging import logger

FMP_BASE = "https://financialmodelingprep.com/api/v3"


class FMPSource:
    name = "fmp"

    def __init__(self):
        self.api_key = get_settings().fmp_key

    def is_available(self) -> bool:
        return bool(self.api_key)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=3, max=20))
    def _get(self, endpoint: str, params: Optional[dict] = None) -> list | dict:
        url = f"{FMP_BASE}/{endpoint}"
        p = {"apikey": self.api_key, **(params or {})}
        resp = requests.get(url, params=p, timeout=30)
        resp.raise_for_status()
        return resp.json()

    @cached(ttl=86400, prefix="fmp:income")
    def fetch_income_statement(self, symbol: str, limit: int = 5) -> list[dict]:
        logger.info(f"[FMP] Income statement | {symbol}")
        return self._get(f"income-statement/{symbol}", {"limit": limit})

    @cached(ttl=86400, prefix="fmp:balance")
    def fetch_balance_sheet(self, symbol: str, limit: int = 5) -> list[dict]:
        logger.info(f"[FMP] Balance sheet | {symbol}")
        return self._get(f"balance-sheet-statement/{symbol}", {"limit": limit})

    @cached(ttl=86400, prefix="fmp:cashflow")
    def fetch_cash_flow(self, symbol: str, limit: int = 5) -> list[dict]:
        logger.info(f"[FMP] Cash flow | {symbol}")
        return self._get(f"cash-flow-statement/{symbol}", {"limit": limit})

    @cached(ttl=86400, prefix="fmp:ratios")
    def fetch_ratios(self, symbol: str) -> dict:
        logger.info(f"[FMP] Ratios | {symbol}")
        data = self._get(f"ratios-ttm/{symbol}")
        return data[0] if data else {}

    @cached(ttl=86400, prefix="fmp:profile")
    def fetch_profile(self, symbol: str) -> dict:
        data = self._get(f"profile/{symbol}")
        return data[0] if data else {}

    @cached(ttl=3600, prefix="fmp:sector")
    def fetch_sector_performance(self) -> list[dict]:
        logger.info("[FMP] Sector performance")
        return self._get("sector-performance") or []

    @cached(ttl=7200, prefix="fmp:macro:gdp")
    def fetch_economic_indicator(self, indicator: str) -> pd.DataFrame:
        """
        Available: GDP, realGDP, inflation, CPI, unemploymentRate, federalFunds, etc.
        """
        logger.info(f"[FMP] Economic indicator | {indicator}")
        data = self._get(f"economic/{indicator}")
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data)
        df["date"] = pd.to_datetime(df["date"])
        return df.set_index("date").sort_index()
