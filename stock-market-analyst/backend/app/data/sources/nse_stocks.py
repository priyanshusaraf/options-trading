"""
NSE Stock Directory — full list of all NSE-listed equities.

Primary source: NSE EQUITY_L.csv (~2,364 companies)
  https://archives.nseindia.com/content/equities/EQUITY_L.csv

The CSV is bundled at data/nse_equity_list.csv and refreshed on startup if stale.
Sector/index data is layered on top via a curated mapping for the ~300 most
important stocks; the rest get sector "Unknown" which can be set by the user.
"""
from __future__ import annotations

import csv
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from backend.app.core.logging import logger


@dataclass
class StockInfo:
    symbol: str
    name: str
    sector: str = "Unknown"
    industry: str = ""
    index_membership: str = ""
    isin: str = ""
    series: str = "EQ"
    listed_date: str = ""


# ── Sector / index overlay for well-known stocks ──────────────────────────────
# (symbol → (sector, industry, index))
_OVERLAY: dict[str, tuple[str, str, str]] = {
    # Nifty 50
    "RELIANCE":    ("Energy",              "Oil & Gas",              "Nifty 50"),
    "TCS":         ("Technology",          "IT Services",            "Nifty 50"),
    "HDFCBANK":    ("Financials",          "Private Banks",          "Nifty 50"),
    "BHARTIARTL":  ("Communication",       "Telecom",                "Nifty 50"),
    "ICICIBANK":   ("Financials",          "Private Banks",          "Nifty 50"),
    "INFOSYS":     ("Technology",          "IT Services",            "Nifty 50"),
    "INFY":        ("Technology",          "IT Services",            "Nifty 50"),
    "SBIN":        ("Financials",          "Public Banks",           "Nifty 50"),
    "HINDUNILVR":  ("Consumer Staples",    "FMCG",                   "Nifty 50"),
    "ITC":         ("Consumer Staples",    "Cigarettes/FMCG",        "Nifty 50"),
    "LT":          ("Industrials",         "Engineering",            "Nifty 50"),
    "KOTAKBANK":   ("Financials",          "Private Banks",          "Nifty 50"),
    "BAJFINANCE":  ("Financials",          "NBFC",                   "Nifty 50"),
    "HCLTECH":     ("Technology",          "IT Services",            "Nifty 50"),
    "MARUTI":      ("Consumer Discret.",   "Automobiles",            "Nifty 50"),
    "SUNPHARMA":   ("Healthcare",          "Pharma",                 "Nifty 50"),
    "ADANIENT":    ("Industrials",         "Conglomerate",           "Nifty 50"),
    "ADANIPORTS":  ("Industrials",         "Ports",                  "Nifty 50"),
    "TITAN":       ("Consumer Discret.",   "Jewellery",              "Nifty 50"),
    "ULTRACEMCO":  ("Materials",           "Cement",                 "Nifty 50"),
    "ONGC":        ("Energy",              "Oil & Gas",              "Nifty 50"),
    "NTPC":        ("Utilities",           "Power Generation",       "Nifty 50"),
    "POWERGRID":   ("Utilities",           "Transmission",           "Nifty 50"),
    "WIPRO":       ("Technology",          "IT Services",            "Nifty 50"),
    "NESTLEIND":   ("Consumer Staples",    "Food & Beverages",       "Nifty 50"),
    "TMCV":        ("Consumer Discret.",   "Automobiles (CV)",       ""),       # Tata Motors Commercial Vehicles
    "TMPV":        ("Consumer Discret.",   "Automobiles (PV)",       ""),       # Tata Motors Passenger Vehicles
    "TATASTEEL":   ("Materials",           "Steel",                  "Nifty 50"),
    "JSWSTEEL":    ("Materials",           "Steel",                  "Nifty 50"),
    "TECHM":       ("Technology",          "IT Services",            "Nifty 50"),
    "DRREDDY":     ("Healthcare",          "Pharma",                 "Nifty 50"),
    "CIPLA":       ("Healthcare",          "Pharma",                 "Nifty 50"),
    "BAJAJFINSV":  ("Financials",          "Financial Services",     "Nifty 50"),
    "EICHERMOT":   ("Consumer Discret.",   "Automobiles",            "Nifty 50"),
    "HEROMOTOCO":  ("Consumer Discret.",   "Two-wheelers",           "Nifty 50"),
    "APOLLOHOSP":  ("Healthcare",          "Hospitals",              "Nifty 50"),
    "TATACONSUM":  ("Consumer Staples",    "FMCG",                   "Nifty 50"),
    "ASIANPAINT":  ("Materials",           "Paints",                 "Nifty 50"),
    "GRASIM":      ("Materials",           "Diversified",            "Nifty 50"),
    "HINDALCO":    ("Materials",           "Aluminium",              "Nifty 50"),
    "COALINDIA":   ("Energy",              "Coal Mining",            "Nifty 50"),
    "BPCL":        ("Energy",              "Refining",               "Nifty 50"),
    "BRITANNIA":   ("Consumer Staples",    "Food",                   "Nifty 50"),
    "SHREECEM":    ("Materials",           "Cement",                 "Nifty 50"),
    "DIVISLAB":    ("Healthcare",          "Pharma",                 "Nifty 50"),
    "M&M":         ("Consumer Discret.",   "Automobiles",            "Nifty 50"),
    "INDUSINDBK":  ("Financials",          "Private Banks",          "Nifty 50"),
    "SBILIFE":     ("Financials",          "Insurance",              "Nifty 50"),
    "HDFCLIFE":    ("Financials",          "Insurance",              "Nifty 50"),
    "BAJAJ-AUTO":  ("Consumer Discret.",   "Two-wheelers",           "Nifty 50"),
    "ZOMATO":      ("Consumer Discret.",   "Food Delivery",          "Nifty Next 50"),
    # Nifty Next 50
    "ABB":         ("Industrials",         "Electrical Equipment",   "Nifty Next 50"),
    "AMBUJACEM":   ("Materials",           "Cement",                 "Nifty Next 50"),
    "AUROPHARMA":  ("Healthcare",          "Pharma",                 "Nifty Next 50"),
    "BANKBARODA":  ("Financials",          "Public Banks",           "Nifty Next 50"),
    "BEL":         ("Industrials",         "Defense Electronics",    "Nifty Next 50"),
    "BERGEPAINT":  ("Materials",           "Paints",                 "Nifty Next 50"),
    "BOSCHLTD":    ("Consumer Discret.",   "Auto Components",        "Nifty Next 50"),
    "CANBK":       ("Financials",          "Public Banks",           "Nifty Next 50"),
    "CHOLAFIN":    ("Financials",          "NBFC",                   "Nifty Next 50"),
    "COLPAL":      ("Consumer Staples",    "Personal Care",          "Nifty Next 50"),
    "DABUR":       ("Consumer Staples",    "FMCG",                   "Nifty Next 50"),
    "DLF":         ("Real Estate",         "Real Estate",            "Nifty Next 50"),
    "FEDERALBNK":  ("Financials",          "Private Banks",          "Nifty Next 50"),
    "GAIL":        ("Energy",              "Gas Utilities",          "Nifty Next 50"),
    "GODREJCP":    ("Consumer Staples",    "FMCG",                   "Nifty Next 50"),
    "HAVELLS":     ("Consumer Discret.",   "Electrical Equipment",   "Nifty Next 50"),
    "HDFCAMC":     ("Financials",          "Asset Management",       "Nifty Next 50"),
    "ICICIPRULI":  ("Financials",          "Insurance",              "Nifty Next 50"),
    "ICICIGI":     ("Financials",          "Insurance",              "Nifty Next 50"),
    "INDUSTOWER":  ("Communication",       "Telecom Infrastructure", "Nifty Next 50"),
    "IOC":         ("Energy",              "Refining",               "Nifty Next 50"),
    "IRCTC":       ("Consumer Discret.",   "Travel",                 "Nifty Next 50"),
    "LUPIN":       ("Healthcare",          "Pharma",                 "Nifty Next 50"),
    "NAUKRI":      ("Technology",          "Internet",               "Nifty Next 50"),
    "NHPC":        ("Utilities",           "Hydro Power",            "Nifty Next 50"),
    "NMDC":        ("Materials",           "Iron Ore Mining",        "Nifty Next 50"),
    "OFSS":        ("Technology",          "IT Services",            "Nifty Next 50"),
    "PAGEIND":     ("Consumer Discret.",   "Apparel",                "Nifty Next 50"),
    "PERSISTENT":  ("Technology",          "IT Services",            "Nifty Next 50"),
    "PETRONET":    ("Energy",              "LNG",                    "Nifty Next 50"),
    "PIDILITIND":  ("Materials",           "Adhesives",              "Nifty Next 50"),
    "PNB":         ("Financials",          "Public Banks",           "Nifty Next 50"),
    "RECLTD":      ("Financials",          "Power Finance",          "Nifty Next 50"),
    "SAIL":        ("Materials",           "Steel",                  "Nifty Next 50"),
    "SIEMENS":     ("Industrials",         "Electrical Equipment",   "Nifty Next 50"),
    "SRF":         ("Materials",           "Chemicals",              "Nifty Next 50"),
    "TORNTPHARM":  ("Healthcare",          "Pharma",                 "Nifty Next 50"),
    "TRENT":       ("Consumer Discret.",   "Retail",                 "Nifty Next 50"),
    "VEDL":        ("Materials",           "Diversified Metals",     "Nifty Next 50"),
    "VOLTAS":      ("Consumer Discret.",   "Air Conditioning",       "Nifty Next 50"),
    # IT
    "MPHASIS":     ("Technology",          "IT Services",            ""),
    "COFORGE":     ("Technology",          "IT Services",            ""),
    "LTIM":        ("Technology",          "IT Services",            ""),
    "LTTS":        ("Technology",          "IT Services",            ""),
    "KPITTECH":    ("Technology",          "Auto Tech",              ""),
    "TATAELXSI":   ("Technology",          "Design/Embedded",        ""),
    "PERSISTENT":  ("Technology",          "IT Services",            ""),
    # Banks & Finance
    "AUBANK":      ("Financials",          "Small Finance Bank",     ""),
    "IDFCFIRSTB":  ("Financials",          "Private Banks",          ""),
    "RBLBANK":     ("Financials",          "Private Banks",          ""),
    "BANDHANBNK":  ("Financials",          "Microfinance Bank",      ""),
    "MANAPPURAM":  ("Financials",          "Gold Finance",           ""),
    "MUTHOOTFIN":  ("Financials",          "Gold Finance",           ""),
    "SHRIRAMFIN":  ("Financials",          "NBFC",                   ""),
    "SBICARD":     ("Financials",          "Credit Cards",           ""),
    "LICHSGFIN":   ("Financials",          "Housing Finance",        ""),
    "PNBHOUSING":  ("Financials",          "Housing Finance",        ""),
    "ANGELONE":    ("Financials",          "Broking",                ""),
    # Pharma
    "ALKEM":       ("Healthcare",          "Pharma",                 ""),
    "BIOCON":      ("Healthcare",          "Biopharma",              ""),
    "GLENMARK":    ("Healthcare",          "Pharma",                 ""),
    "IPCA":        ("Healthcare",          "Pharma",                 ""),
    "ZYDUSLIFE":   ("Healthcare",          "Pharma",                 ""),
    "FORTIS":      ("Healthcare",          "Hospitals",              ""),
    "MAXHEALTH":   ("Healthcare",          "Hospitals",              ""),
    "METROPOLIS":  ("Healthcare",          "Diagnostics",            ""),
    # Auto
    "ASHOKLEY":    ("Consumer Discret.",   "Commercial Vehicles",    ""),
    "BALKRISIND":  ("Consumer Discret.",   "Tyres",                  ""),
    "BHARATFORG":  ("Consumer Discret.",   "Forgings",               ""),
    "MOTHERSON":   ("Consumer Discret.",   "Auto Components",        ""),
    "MRF":         ("Consumer Discret.",   "Tyres",                  ""),
    "TVSMOTOR":    ("Consumer Discret.",   "Two-wheelers",           ""),
    # Energy
    "ADANIGREEN":  ("Utilities",           "Renewable Energy",       ""),
    "TATAPOWER":   ("Utilities",           "Power",                  ""),
    "TORNTPOWER":  ("Utilities",           "Power",                  ""),
    "IGL":         ("Energy",              "City Gas",               ""),
    "MGL":         ("Energy",              "City Gas",               ""),
    "HPCLLTD":     ("Energy",              "Refining",               ""),
    "OIL":         ("Energy",              "Oil & Gas",              ""),
    # Consumer
    "DMART":       ("Consumer Staples",    "Retail",                 ""),
    "EMAMILTD":    ("Consumer Staples",    "FMCG",                   ""),
    "MARICO":      ("Consumer Staples",    "FMCG",                   ""),
    "VBL":         ("Consumer Staples",    "Beverages",              ""),
    "JUBLFOOD":    ("Consumer Discret.",   "QSR",                    ""),
    "NYKAA":       ("Consumer Discret.",   "Beauty Retail",          ""),
    "TRENT":       ("Consumer Discret.",   "Retail",                 ""),
    # Industrials
    "HAL":         ("Industrials",         "Aerospace/Defense",      ""),
    "POLYCAB":     ("Consumer Discret.",   "Cables & Wires",         ""),
    "ASTRAL":      ("Materials",           "Pipes & Fittings",       ""),
    "APLAPOLLO":   ("Materials",           "Steel Tubes",            ""),
    # Chemicals
    "AARTI":       ("Materials",           "Chemicals",              ""),
    "DEEPAKNTR":   ("Materials",           "Chemicals",              ""),
    "PIIND":       ("Materials",           "Agrochemicals",          ""),
    "UPL":         ("Materials",           "Agrochemicals",          ""),
    "TATACHEM":    ("Materials",           "Chemicals",              ""),
    "VINATI":      ("Materials",           "Specialty Chemicals",    ""),
    # Real Estate
    "GODREJPROP":  ("Real Estate",         "Real Estate",            ""),
    "DLF":         ("Real Estate",         "Real Estate",            ""),
    "OBEROIRLTY":  ("Real Estate",         "Real Estate",            ""),
    "PRESTIGE":    ("Real Estate",         "Real Estate",            ""),
    # New-age
    "PAYTM":       ("Technology",          "Fintech",                ""),
    "POLICYBZR":   ("Technology",          "Fintech",                ""),
    "DELHIVERY":   ("Industrials",         "Logistics",              ""),
    "INDIGO":      ("Industrials",         "Aviation",               ""),
}

# ── Load CSV ──────────────────────────────────────────────────────────────────

def _find_csv() -> Optional[Path]:
    """Locate the EQUITY_L.csv file relative to the project root."""
    candidates = [
        Path(__file__).resolve().parents[3] / "data" / "nse_equity_list.csv",
        Path("data/nse_equity_list.csv"),
        Path("/tmp/nse_equity_list.csv"),
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def _load_all_stocks() -> list[StockInfo]:
    """Load all stocks from the NSE equity CSV, enriched with sector overlay."""
    csv_path = _find_csv()
    stocks: list[StockInfo] = []

    if csv_path is None:
        logger.warning("[NSE] EQUITY_L.csv not found — falling back to curated list only")
        for sym, (sector, industry, index) in _OVERLAY.items():
            stocks.append(StockInfo(symbol=sym, name=sym, sector=sector,
                                    industry=industry, index_membership=index))
        return stocks

    try:
        with open(csv_path, encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                sym = row.get("SYMBOL", "").strip()
                name = row.get("NAME OF COMPANY", "").strip()
                series = row.get(" SERIES", "EQ").strip()
                isin = row.get(" ISIN NUMBER", "").strip()
                listed = row.get(" DATE OF LISTING", "").strip()

                if not sym or not name:
                    continue
                # Only EQ series (skip ETFs, REITs, bonds, etc.)
                if series not in ("EQ", "BE", "BL", ""):
                    continue

                overlay = _OVERLAY.get(sym)
                sector = overlay[0] if overlay else "Unknown"
                industry = overlay[1] if overlay else ""
                index = overlay[2] if overlay else ""

                stocks.append(StockInfo(
                    symbol=sym,
                    name=name,
                    sector=sector,
                    industry=industry,
                    index_membership=index,
                    isin=isin,
                    series=series,
                    listed_date=listed,
                ))

        logger.info(f"[NSE] Loaded {len(stocks)} equities from EQUITY_L.csv")
    except Exception as e:
        logger.error(f"[NSE] Failed to load EQUITY_L.csv: {e}")

    return stocks


# Singleton — loaded once at module import
_ALL_STOCKS: list[StockInfo] = _load_all_stocks()

# Trigram index for fuzzy name matching
_TRIGRAMS: dict[str, list[int]] = {}

def _make_trigrams(text: str) -> set[str]:
    t = text.lower()
    return {t[i:i+3] for i in range(len(t) - 2)}

def _build_index():
    for i, stock in enumerate(_ALL_STOCKS):
        for tg in _make_trigrams(stock.name):
            _TRIGRAMS.setdefault(tg, []).append(i)
        for tg in _make_trigrams(stock.symbol):
            _TRIGRAMS.setdefault(tg, []).append(i)

_build_index()


# ── Search ────────────────────────────────────────────────────────────────────

def search_stocks(query: str, limit: int = 12) -> list[StockInfo]:
    """
    Fast search across all ~2,364 NSE-listed equities.

    Ranking (highest to lowest):
      1. Exact symbol match
      2. Symbol starts with query
      3. Name starts with query (word boundary)
      4. Name contains all query words
      5. Trigram similarity (fuzzy)
    """
    q = query.strip()
    if not q:
        return []

    q_up = q.upper()
    q_low = q.lower()
    q_words = q_low.split()

    tier1, tier2, tier3, tier4, tier5 = [], [], [], [], []
    seen: set[int] = set()

    # Tiers 1-4: exact / prefix / contains
    for i, stock in enumerate(_ALL_STOCKS):
        sym_up = stock.symbol.upper()
        name_low = stock.name.lower()

        if sym_up == q_up:
            tier1.append(i); seen.add(i)
        elif sym_up.startswith(q_up):
            tier2.append(i); seen.add(i)
        elif name_low.startswith(q_low):
            tier3.append(i); seen.add(i)
        elif all(w in name_low for w in q_words):
            tier4.append(i); seen.add(i)

    # Tier 5: trigram fuzzy (only if we need more results)
    if len(tier1) + len(tier2) + len(tier3) + len(tier4) < limit:
        scores: dict[int, int] = {}
        for tg in _make_trigrams(q_low):
            for idx in _TRIGRAMS.get(tg, []):
                if idx not in seen:
                    scores[idx] = scores.get(idx, 0) + 1
        tier5 = sorted(scores, key=lambda x: -scores[x])

    ordered = tier1 + tier2 + tier3 + tier4 + tier5
    # Deduplicate while preserving order
    seen2: set[int] = set()
    result = []
    for idx in ordered:
        if idx not in seen2:
            seen2.add(idx)
            result.append(_ALL_STOCKS[idx])
        if len(result) >= limit:
            break

    return result


# ── Symbol aliases (old/common → current NSE symbol) ─────────────────────────
_ALIASES: dict[str, str] = {
    "TATAMOTORS":  "TMCV",     # Tata Motors restructured
    "TATAMOTORS-DVR": "TMCV",
    "HDFC":        "HDFCBANK", # HDFC Ltd merged into HDFC Bank
    "INFOSYS":     "INFY",
    "ZEEL":        "ZEEL",
    "ADANITRANS":  "ADANIENSOL",
    "MCDOWELL-N":  "UNITDSPR",
    "BAJAJ-AUTO":  "BAJAJ-AUTO",
}


def search_stocks(query: str, limit: int = 12) -> list[StockInfo]:
    """
    Fast search across all NSE-listed equities.
    Ranking: exact symbol → symbol prefix → name prefix → name contains → trigram fuzzy.
    Also resolves common aliases (e.g. TATAMOTORS → TMCV).
    """
    q = query.strip()
    if not q:
        return []

    # Check alias first
    alias_target = _ALIASES.get(q.upper())
    if alias_target:
        aliased = get_stock_info(alias_target)
        if aliased:
            rest = _search_raw(q, limit - 1)
            return [aliased] + [r for r in rest if r.symbol != aliased.symbol]

    return _search_raw(q, limit)


def _search_raw(query: str, limit: int) -> list[StockInfo]:
    q = query.strip()
    q_up = q.upper()
    q_low = q.lower()
    q_words = q_low.split()

    tier1, tier2, tier3, tier4, tier5 = [], [], [], [], []
    seen: set[int] = set()

    for i, stock in enumerate(_ALL_STOCKS):
        sym_up = stock.symbol.upper()
        name_low = stock.name.lower()

        if sym_up == q_up:
            tier1.append(i); seen.add(i)
        elif sym_up.startswith(q_up):
            tier2.append(i); seen.add(i)
        elif name_low.startswith(q_low):
            tier3.append(i); seen.add(i)
        elif all(w in name_low for w in q_words):
            tier4.append(i); seen.add(i)

    if len(tier1) + len(tier2) + len(tier3) + len(tier4) < limit:
        scores: dict[int, int] = {}
        for tg in _make_trigrams(q_low):
            for idx in _TRIGRAMS.get(tg, []):
                if idx not in seen:
                    scores[idx] = scores.get(idx, 0) + 1
        tier5 = sorted(scores, key=lambda x: -scores[x])

    ordered = tier1 + tier2 + tier3 + tier4 + tier5
    seen2: set[int] = set()
    result = []
    for idx in ordered:
        if idx not in seen2:
            seen2.add(idx)
            result.append(_ALL_STOCKS[idx])
        if len(result) >= limit:
            break
    return result


def get_stock_info(symbol: str) -> Optional[StockInfo]:
    sym = symbol.upper().strip()
    # Check alias
    resolved = _ALIASES.get(sym)
    if resolved:
        sym = resolved
    for s in _ALL_STOCKS:
        if s.symbol == sym:
            return s
    return None


def total_count() -> int:
    return len(_ALL_STOCKS)
