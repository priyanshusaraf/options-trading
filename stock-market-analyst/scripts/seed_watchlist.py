#!/usr/bin/env python3
"""
Watchlist Pre-Seeding Script.

Seeds a curated list of Indian large-cap stocks across key sectors.
Run this once after initial setup:

    python scripts/seed_watchlist.py

Optionally pass a custom watchlist file:

    python scripts/seed_watchlist.py --file my_watchlist.csv
"""
import argparse
import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.app.data.models.database import init_db
from backend.app.data.sources.watchlist_service import WatchlistService
from backend.app.core.logging import configure_logging

configure_logging()

# ── Default seed list ─────────────────────────────────────────────────────────
DEFAULT_WATCHLIST = [
    # Financials
    {"symbol": "HDFCBANK",   "sector": "Financials",     "exchange": "NSE", "notes": "India's largest private bank by assets"},
    {"symbol": "ICICIBANK",  "sector": "Financials",     "exchange": "NSE", "notes": "Large-cap private sector bank"},
    {"symbol": "KOTAKBANK",  "sector": "Financials",     "exchange": "NSE", "notes": "Premium retail banking franchise"},
    {"symbol": "SBIN",       "sector": "Financials",     "exchange": "NSE", "notes": "Largest public sector bank"},
    {"symbol": "BAJFINANCE", "sector": "Financials",     "exchange": "NSE", "notes": "Leading NBFC consumer finance"},
    # IT
    {"symbol": "TCS",        "sector": "Technology",     "exchange": "NSE", "notes": "India's largest IT services"},
    {"symbol": "INFY",       "sector": "Technology",     "exchange": "NSE", "notes": "Tier-1 IT services company"},
    {"symbol": "WIPRO",      "sector": "Technology",     "exchange": "NSE", "notes": "Mid-tier IT services"},
    {"symbol": "HCLTECH",    "sector": "Technology",     "exchange": "NSE", "notes": "IT services and products"},
    {"symbol": "TECHM",      "sector": "Technology",     "exchange": "NSE", "notes": "IT services, telecom focus"},
    # Energy
    {"symbol": "RELIANCE",   "sector": "Energy",         "exchange": "NSE", "notes": "Diversified conglomerate — oil, retail, jio"},
    {"symbol": "ONGC",       "sector": "Energy",         "exchange": "NSE", "notes": "State oil & gas exploration"},
    {"symbol": "POWERGRID",  "sector": "Utilities",      "exchange": "NSE", "notes": "Transmission infrastructure"},
    {"symbol": "NTPC",       "sector": "Utilities",      "exchange": "NSE", "notes": "Largest power producer"},
    # Consumer
    {"symbol": "HINDUNILVR", "sector": "Consumer Staples","exchange": "NSE", "notes": "FMCG giant — Hindustan Unilever"},
    {"symbol": "ITC",        "sector": "Consumer Staples","exchange": "NSE", "notes": "Cigarettes + FMCG diversified"},
    {"symbol": "NESTLEIND",  "sector": "Consumer Staples","exchange": "NSE", "notes": "Food & beverages"},
    {"symbol": "MARUTI",     "sector": "Consumer Discretionary","exchange": "NSE", "notes": "Largest auto maker India"},
    {"symbol": "TATAMOTORS", "sector": "Consumer Discretionary","exchange": "NSE", "notes": "Auto + JLR premium cars"},
    # Healthcare
    {"symbol": "SUNPHARMA",  "sector": "Healthcare",     "exchange": "NSE", "notes": "Largest Indian pharma by revenue"},
    {"symbol": "DRREDDY",    "sector": "Healthcare",     "exchange": "NSE", "notes": "Generic drugs, US/India"},
    {"symbol": "CIPLA",      "sector": "Healthcare",     "exchange": "NSE", "notes": "Generic pharma and inhalers"},
    # Industrials
    {"symbol": "LT",         "sector": "Industrials",    "exchange": "NSE", "notes": "Engineering & construction conglomerate"},
    {"symbol": "ADANIPORTS", "sector": "Industrials",    "exchange": "NSE", "notes": "Port infrastructure"},
    {"symbol": "TATASTEEL",  "sector": "Materials",      "exchange": "NSE", "notes": "Steel production, India + UK"},
    {"symbol": "JSWSTEEL",   "sector": "Materials",      "exchange": "NSE", "notes": "Steel manufacturing"},
    # Benchmark
    {"symbol": "NIFTY50",    "sector": "Index",          "exchange": "NSE", "notes": "Benchmark index tracking"},
]


def seed(dry_run: bool = False, custom_file: str = None):
    init_db()
    svc = WatchlistService()

    # Load from file if provided
    if custom_file:
        import csv
        items = []
        with open(custom_file) as f:
            reader = csv.DictReader(f)
            for row in reader:
                items.append(row)
    else:
        items = DEFAULT_WATCHLIST

    existing = set(svc.symbols())
    added = 0
    skipped = 0

    for item in items:
        sym = item["symbol"].upper()
        if sym in existing:
            print(f"  SKIP  {sym} (already in watchlist)")
            skipped += 1
            continue

        if dry_run:
            print(f"  DRY   {sym} — {item.get('sector', '')} — {item.get('notes', '')}")
        else:
            try:
                svc.add(
                    symbol=sym,
                    exchange=item.get("exchange", "NSE"),
                    sector=item.get("sector"),
                    notes=item.get("notes"),
                )
                print(f"  ADD   {sym} — {item.get('sector', '')}")
                added += 1
            except Exception as e:
                print(f"  ERR   {sym} — {e}")

    print(f"\n{'DRY RUN' if dry_run else 'Done'}: added={added}, skipped={skipped}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed default watchlist")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--file", default=None, help="Path to CSV with symbol,sector,exchange,notes")
    args = parser.parse_args()
    seed(dry_run=args.dry_run, custom_file=args.file)
