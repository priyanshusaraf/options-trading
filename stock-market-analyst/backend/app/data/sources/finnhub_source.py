"""
Finnhub — news, sentiment, earnings calendar, economic calendar.
Free tier: 60 API calls/minute.
"""
from datetime import date, datetime, timezone
from typing import Optional

import pandas as pd
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.app.core.cache import cached
from backend.app.core.config import get_settings
from backend.app.core.logging import logger

FINNHUB_BASE = "https://finnhub.io/api/v1"


class FinnhubSource:
    name = "finnhub"

    def __init__(self):
        self.api_key = get_settings().finnhub_key

    def is_available(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict:
        return {"X-Finnhub-Token": self.api_key}

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=15))
    def _get(self, endpoint: str, params: Optional[dict] = None) -> dict | list:
        url = f"{FINNHUB_BASE}/{endpoint}"
        resp = requests.get(url, headers=self._headers(), params=params or {}, timeout=20)
        resp.raise_for_status()
        return resp.json()

    @cached(ttl=1800, prefix="fh:news")
    def fetch_company_news(self, symbol: str, start: date, end: date) -> list[dict]:
        logger.info(f"[finnhub] Fetching news | {symbol}")
        data = self._get(
            "company-news",
            {
                "symbol": symbol,
                "from": start.isoformat(),
                "to": end.isoformat(),
            },
        )
        return data if isinstance(data, list) else []

    @cached(ttl=1800, prefix="fh:market_news")
    def fetch_market_news(self, category: str = "general") -> list[dict]:
        logger.info(f"[finnhub] Fetching market news | category={category}")
        return self._get("news", {"category": category}) or []

    @cached(ttl=3600, prefix="fh:sentiment")
    def fetch_news_sentiment(self, symbol: str) -> dict:
        logger.info(f"[finnhub] Sentiment | {symbol}")
        return self._get("news-sentiment", {"symbol": symbol})

    @cached(ttl=7200, prefix="fh:calendar:earnings")
    def fetch_earnings_calendar(self, start: date, end: date) -> list[dict]:
        logger.info(f"[finnhub] Earnings calendar | {start} → {end}")
        data = self._get(
            "calendar/earnings",
            {"from": start.isoformat(), "to": end.isoformat()},
        )
        return data.get("earningsCalendar", []) if isinstance(data, dict) else []

    @cached(ttl=7200, prefix="fh:calendar:economic")
    def fetch_economic_calendar(self) -> list[dict]:
        logger.info("[finnhub] Economic calendar")
        data = self._get("calendar/economic")
        return data.get("economicCalendar", []) if isinstance(data, dict) else []

    @cached(ttl=86400, prefix="fh:profile")
    def fetch_company_profile(self, symbol: str) -> dict:
        logger.info(f"[finnhub] Company profile | {symbol}")
        return self._get("stock/profile2", {"symbol": symbol}) or {}

    @cached(ttl=3600, prefix="fh:quote")
    def fetch_quote(self, symbol: str) -> dict:
        return self._get("quote", {"symbol": symbol}) or {}
