"""
Base class for all data sources.
Every source must implement fetch_ohlcv and optionally fetch_fundamentals.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import Optional
import pandas as pd


@dataclass
class OHLCVData:
    symbol: str
    df: pd.DataFrame               # columns: open, high, low, close, volume
    source: str = "unknown"
    currency: str = "USD"
    interval: str = "1d"


@dataclass
class FundamentalData:
    symbol: str
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    market_cap: Optional[float] = None
    eps: Optional[float] = None
    dividend_yield: Optional[float] = None
    revenue: Optional[float] = None
    net_income: Optional[float] = None
    debt_to_equity: Optional[float] = None
    roe: Optional[float] = None
    extra: dict = field(default_factory=dict)


class BaseDataSource(ABC):
    name: str = "base"

    @abstractmethod
    def fetch_ohlcv(
        self,
        symbol: str,
        start: date,
        end: date,
        interval: str = "1d",
    ) -> OHLCVData:
        ...

    def fetch_fundamentals(self, symbol: str) -> Optional[FundamentalData]:
        return None

    def is_available(self) -> bool:
        return True
