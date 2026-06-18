"""
Commodity Linking Engine.

For each stock in the watchlist, determines:
  1. Which commodities are correlated (contemporaneous + lagged)
  2. The direction and strength of the relationship
  3. The lag at which the relationship is strongest
  4. Whether it's a cost driver (inverse) or revenue driver (positive)

Commodity data sources:
  - FRED series (oil: DCOILWTICO, gold: GOLDAMGBD228NLBM, etc.)
  - yfinance: commodity ETFs / futures (GC=F, CL=F, HG=F, etc.)

Analysis:
  - Rolling correlation (30d, 90d, 252d)
  - Granger causality test (does commodity Granger-cause stock?)
  - Lagged cross-correlation (find optimal lag 0–20 days)
  - Regime-conditional correlation (bull vs bear commodity regime)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.tsa.stattools import grangercausalitytests

from backend.app.core.cache import cached
from backend.app.core.logging import logger
from backend.app.data.ingestion import DataIngestionManager

# ── Commodity universe ────────────────────────────────────────────────────────

COMMODITY_TICKERS: dict[str, str] = {
    # Name → yfinance symbol
    "Crude Oil (WTI)": "CL=F",
    "Crude Oil (Brent)": "BZ=F",
    "Natural Gas": "NG=F",
    "Gold": "GC=F",
    "Silver": "SI=F",
    "Copper": "HG=F",
    "Aluminum": "ALI=F",
    "Steel": "HRC=F",
    "Iron Ore": "TIO=F",
    "Corn": "ZC=F",
    "Wheat": "ZW=F",
    "Soybeans": "ZS=F",
    "Sugar": "SB=F",
    "Cotton": "CT=F",
    "Palm Oil": "FPOL.KL",
    "Coal": "MTF=F",
    "Rubber": "TOCOM.RSP",
}

# Sector → commodities most likely to affect it
SECTOR_COMMODITY_PRIORS: dict[str, list[str]] = {
    "energy":        ["Crude Oil (WTI)", "Crude Oil (Brent)", "Natural Gas"],
    "chemicals":     ["Crude Oil (WTI)", "Natural Gas"],
    "airlines":      ["Crude Oil (Brent)"],
    "auto":          ["Steel", "Aluminum", "Copper"],
    "fmcg":          ["Palm Oil", "Sugar", "Wheat", "Cotton"],
    "metals":        ["Iron Ore", "Steel", "Coal", "Copper"],
    "agriculture":   ["Corn", "Wheat", "Soybeans", "Sugar"],
    "infrastructure":["Steel", "Copper", "Aluminum"],
    "logistics":     ["Crude Oil (WTI)"],
    "technology":    ["Copper"],
    "textile":       ["Cotton"],
    "pharma":        ["Crude Oil (WTI)"],
}


@dataclass
class CommodityLink:
    commodity_name: str
    commodity_ticker: str
    stock_symbol: str

    # Correlations at different windows
    corr_30d: float = 0.0
    corr_90d: float = 0.0
    corr_252d: float = 0.0

    # Best lag analysis
    best_lag_days: int = 0           # 0 = contemporaneous, >0 = commodity leads
    best_lag_corr: float = 0.0
    lag_direction: str = "unknown"   # "commodity_leads" / "stock_leads" / "contemporaneous"

    # Granger test
    granger_pvalue: Optional[float] = None   # H0: commodity does NOT cause stock
    granger_significant: bool = False

    # Relationship type
    relationship_type: str = "unknown"  # "cost_driver" / "revenue_driver" / "macro_proxy" / "none"
    is_significant: bool = False


@dataclass
class CommodityLinkageResult:
    symbol: str
    sector: Optional[str]
    links: list[CommodityLink]
    top_commodity: Optional[str] = None
    top_correlation: float = 0.0
    risk_exposure: str = "low"           # low / medium / high


class CommodityLinker:
    """
    For each stock, find which commodities drive its price.
    """

    MAX_LAG = 20  # Days

    def __init__(self):
        self.ingestion = DataIngestionManager()

    @cached(ttl=86400, prefix="commodity:linkage")
    def analyze(
        self,
        symbol: str,
        sector: Optional[str] = None,
        days: int = 756,
    ) -> CommodityLinkageResult:
        """
        Compute commodity linkages for a stock.
        If sector is provided, only test sector-relevant commodities.
        """
        logger.info(f"[CommodityLinker] Analyzing {symbol} (sector={sector})")
        end = date.today()
        start = end - timedelta(days=days)

        # ── Fetch stock returns ───────────────────────────────────────────────
        yf_sym = f"{symbol}.NS" if not symbol.endswith((".NS", ".BO")) else symbol
        stock_df = self.ingestion.get_ohlcv(yf_sym, start, end)
        if stock_df.empty:
            return CommodityLinkageResult(symbol=symbol, sector=sector, links=[])

        stock_returns = stock_df["close"].pct_change().dropna()

        # ── Select commodities to test ────────────────────────────────────────
        if sector and sector.lower() in SECTOR_COMMODITY_PRIORS:
            candidates = SECTOR_COMMODITY_PRIORS[sector.lower()]
        else:
            # Test top 5 most universal commodities
            candidates = ["Crude Oil (WTI)", "Gold", "Copper", "Wheat", "Iron Ore"]

        links: list[CommodityLink] = []
        for comm_name in candidates:
            ticker = COMMODITY_TICKERS.get(comm_name)
            if not ticker:
                continue
            link = self._compute_link(
                symbol, stock_returns, comm_name, ticker, start, end
            )
            if link:
                links.append(link)

        # Sort by absolute correlation strength
        links.sort(key=lambda x: abs(x.corr_252d), reverse=True)

        top_link = links[0] if links else None
        risk = self._risk_level(links)

        return CommodityLinkageResult(
            symbol=symbol,
            sector=sector,
            links=links,
            top_commodity=top_link.commodity_name if top_link else None,
            top_correlation=top_link.corr_252d if top_link else 0.0,
            risk_exposure=risk,
        )

    def _compute_link(
        self,
        stock_sym: str,
        stock_returns: pd.Series,
        comm_name: str,
        comm_ticker: str,
        start: date,
        end: date,
    ) -> Optional[CommodityLink]:
        try:
            comm_df = self.ingestion.get_ohlcv(comm_ticker, start, end)
            if comm_df.empty:
                return None
            comm_returns = comm_df["close"].pct_change().dropna()
        except Exception as e:
            logger.debug(f"[CommodityLinker] Failed to fetch {comm_ticker}: {e}")
            return None

        # Align
        aligned = pd.DataFrame({"stock": stock_returns, "commodity": comm_returns}).dropna()
        if len(aligned) < 60:
            return None

        link = CommodityLink(
            commodity_name=comm_name,
            commodity_ticker=comm_ticker,
            stock_symbol=stock_sym,
        )

        # Correlations at different windows
        link.corr_252d = self._safe_corr(aligned["stock"], aligned["commodity"])
        link.corr_90d = self._safe_corr(aligned["stock"].tail(90), aligned["commodity"].tail(90))
        link.corr_30d = self._safe_corr(aligned["stock"].tail(30), aligned["commodity"].tail(30))

        # Lagged cross-correlation
        best_lag, best_corr = self._best_lag(aligned["commodity"], aligned["stock"])
        link.best_lag_days = best_lag
        link.best_lag_corr = best_corr
        if best_lag > 2:
            link.lag_direction = "commodity_leads"
        elif best_lag < -2:
            link.lag_direction = "stock_leads"
        else:
            link.lag_direction = "contemporaneous"

        # Granger causality (does commodity Granger-cause stock?)
        if len(aligned) >= 60:
            link.granger_pvalue, link.granger_significant = self._granger_test(
                aligned[["stock", "commodity"]].dropna()
            )

        # Classify relationship type
        link.relationship_type = self._classify_relationship(
            stock_sym, comm_name, link.corr_252d
        )

        link.is_significant = (
            abs(link.corr_252d) > 0.3 or link.granger_significant
        )

        return link

    def _best_lag(
        self, leading: pd.Series, lagged: pd.Series, max_lag: int = 20
    ) -> tuple[int, float]:
        """Find the lag (–max_lag to +max_lag) with the highest absolute cross-correlation."""
        best_lag = 0
        best_corr = 0.0
        for lag in range(-max_lag, max_lag + 1):
            if lag == 0:
                corr = self._safe_corr(leading, lagged)
            elif lag > 0:
                corr = self._safe_corr(leading.iloc[:-lag], lagged.iloc[lag:])
            else:
                corr = self._safe_corr(leading.iloc[-lag:], lagged.iloc[:lag])
            if abs(corr) > abs(best_corr):
                best_corr = corr
                best_lag = lag
        return best_lag, round(best_corr, 4)

    def _granger_test(self, df: pd.DataFrame, maxlag: int = 5) -> tuple[Optional[float], bool]:
        """
        Test if commodity Granger-causes stock price.
        Returns (min_pvalue, is_significant_at_5pct).
        df columns: ['stock', 'commodity']
        """
        try:
            results = grangercausalitytests(df[["stock", "commodity"]], maxlag=maxlag, verbose=False)
            min_pval = min(
                results[lag][0]["ssr_chi2test"][1]
                for lag in range(1, maxlag + 1)
            )
            return round(min_pval, 4), min_pval < 0.05
        except Exception:
            return None, False

    def _classify_relationship(
        self, stock_sym: str, comm_name: str, corr: float
    ) -> str:
        """
        Classify whether the commodity is a cost driver or revenue driver.
        Cost drivers: inverse correlation expected (oil for airlines, etc.)
        Revenue drivers: positive correlation (oil for energy companies)
        """
        cost_pairs = {
            ("airlines", "Crude Oil"): "cost_driver",
            ("auto", "Steel"): "cost_driver",
            ("fmcg", "Palm Oil"): "cost_driver",
            ("cement", "Coal"): "cost_driver",
        }
        # Heuristic: strong negative → cost driver, strong positive → revenue driver
        if corr < -0.3:
            return "cost_driver"
        elif corr > 0.3:
            return "revenue_driver"
        elif abs(corr) > 0.15:
            return "macro_proxy"
        return "none"

    @staticmethod
    def _safe_corr(a: pd.Series, b: pd.Series) -> float:
        try:
            c = pd.concat([a, b], axis=1).dropna().corr().iloc[0, 1]
            return float(c) if not np.isnan(c) else 0.0
        except Exception:
            return 0.0

    @staticmethod
    def _risk_level(links: list[CommodityLink]) -> str:
        significant = [l for l in links if l.is_significant]
        if len(significant) >= 3 or any(abs(l.corr_252d) > 0.6 for l in links):
            return "high"
        if len(significant) >= 1:
            return "medium"
        return "low"
