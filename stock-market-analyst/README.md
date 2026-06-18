# Stock Market Intelligence Platform

A personal-use, research-grade stock market intelligence system combining quantitative finance, technical analysis, macro data, NLP, and graph-based dependency modeling.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        DECISION ENGINE                          │
│     (Quant × Technical × Regime × Sentiment × Event Risk)      │
└───────────────────┬────────────────────────────────────────────┘
                    │
    ┌───────────────┼───────────────────┐
    ▼               ▼                   ▼
┌──────────┐  ┌──────────────┐  ┌──────────────┐
│  QUANT   │  │  TECHNICAL   │  │    REGIME    │
│  ENGINE  │  │   ENGINE     │  │  DETECTOR    │
│          │  │              │  │              │
│ Beta,VaR │  │RSI,MACD,BB   │  │Bull/Bear/Vol │
│ Sharpe   │  │Breakout prob │  │Mean-Rev      │
│ Factors  │  │Reversal prob │  │Hurst exp     │
└────┬─────┘  └──────┬───────┘  └──────┬───────┘
     │               │                  │
     └───────────────┴──────────────────┘
                    │
    ┌───────────────▼────────────────────┐
    │           DATA LAYER               │
    │  yfinance → Parquet cache →        │
    │  Alpha Vantage → SQLite metadata   │
    │  FRED (macro) → Finnhub (news)     │
    │  FMP (fundamentals) → Kite API     │
    └────────────────────────────────────┘
```

## Features Implemented

| Module | Status | Description |
|--------|--------|-------------|
| Data Ingestion | ✅ | yfinance + Alpha Vantage with Parquet cache |
| Watchlist | ✅ | CRUD, SQLite, auto pre-fetch |
| Quant Engine | ✅ | Beta, VaR, CVaR, Sharpe, Sortino, Calmar, factors |
| Technical Engine | ✅ | RSI, MACD, BB, MA, ATR, ADX, probabilistic signals |
| Regime Detector | ✅ | Bull/Bear/HighVol/MeanRev + Hurst exponent |
| Decision Engine | ✅ | Ranked opportunities with transparency |
| FRED Integration | ✅ | 14 macro series |
| Finnhub | ✅ | News, sentiment, calendars |
| FMP | ✅ | Fundamentals, income, balance sheet |
| Caching | ✅ | Parquet (OHLCV) + diskcache (API) |
| FastAPI Backend | ✅ | Full REST API with docs |
| React Frontend | ✅ | Dashboard, Watchlist, Analysis pages |
| Tests | ✅ | Quant, Technical, Regime engine tests |

## Planned Modules (Next Steps)

| Module | Description |
|--------|-------------|
| NLP Engine | Parse annual reports, extract supply chain graph |
| Options Engine | IV surface, PCR, OI analysis via Zerodha/NSE |
| Portfolio Tracker | Kite API integration, live PnL, rebalancing |
| News Intelligence | FinBERT sentiment, event extraction |
| Event Calendar | Global macro calendar (Finnhub + manual) |
| Commodity Linker | Correlation of commodities to stocks |
| Supply Chain Graph | NetworkX graph: company → suppliers → commodities |
| Position Sizer | Kelly-based allocation with correlation adjustment |

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+

### Setup

```bash
# Clone / open this folder
cd stock-market-analyst

# Run setup (creates .venv, installs deps, creates .env)
./scripts/setup.sh

# Edit .env with your API keys (all optional — yfinance works without keys)
vim .env

# Start both servers
./scripts/start.sh
```

Access:
- Frontend: http://localhost:5173
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Run Tests

```bash
./scripts/test.sh
```

## API Keys

| Source | Free Tier | Used For |
|--------|-----------|----------|
| yfinance | No key | Primary OHLCV (NSE, BSE, global) |
| Alpha Vantage | 25 calls/day | Fallback OHLCV, macro |
| Finnhub | 60 calls/min | News, sentiment, calendars |
| FMP | 250 calls/day | Fundamentals, financials |
| FRED | Free | Macro data (CPI, GDP, yields) |
| Zerodha Kite | OAuth | Live portfolio, options chain |

**System works with zero API keys** — yfinance provides OHLCV data for free.

## Folder Structure

```
stock-market-analyst/
├── backend/
│   ├── app/
│   │   ├── api/routes/          # FastAPI endpoints
│   │   ├── analytics/
│   │   │   ├── quant/           # Beta, VaR, factors, Sharpe
│   │   │   ├── technical/       # RSI, MACD, BB, probabilistic signals
│   │   │   ├── options/         # IV surface, PCR (planned)
│   │   │   ├── nlp/             # Document intelligence (planned)
│   │   │   └── macro/           # Macro factor modeling (planned)
│   │   ├── core/                # Config, logging, caching
│   │   ├── data/
│   │   │   ├── sources/         # yfinance, AV, Finnhub, FRED, FMP, Kite
│   │   │   ├── cache/           # Parquet store
│   │   │   ├── models/          # SQLAlchemy models
│   │   │   └── ingestion.py     # Unified data manager
│   │   ├── decision/            # Decision engine + opportunity ranking
│   │   ├── graph/               # Supply chain graph (planned)
│   │   ├── intelligence/
│   │   │   ├── regime/          # Market regime detection
│   │   │   ├── news/            # News intelligence (planned)
│   │   │   └── events/          # Event calendar (planned)
│   │   └── portfolio/           # Portfolio tracking (planned)
│   ├── tests/                   # pytest test suite
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── components/          # ScoreBar, MetricCard, OpportunityCard, etc.
│       ├── pages/               # Dashboard, Watchlist, Analysis
│       └── lib/                 # API client, utilities
├── data/                        # Local data storage
│   ├── parquet/                 # Cached OHLCV (per-symbol .parquet files)
│   ├── sqlite/                  # Metadata DB
│   ├── reports/                 # Annual report PDFs
│   └── cache/                   # diskcache API response cache
├── scripts/
│   ├── setup.sh
│   ├── start.sh
│   └── test.sh
└── .env.example
```

## Design Principles

1. **Causal, not correlational** — Every signal has an economic justification
2. **Transparency** — Every opportunity includes reasoning breakdown
3. **No black boxes** — All scores are decomposable to their inputs
4. **Modular** — Each engine is independently testable
5. **Cache-first** — Aggressive caching minimizes API calls and cost
6. **Probabilistic** — Signals are probabilities (0–1), not binary
7. **Regime-aware** — Signal weights adjust based on detected market regime

## Signal Flow

```
Price Data
    │
    ├─→ Quant Engine ──────────────────────┐
    │   (Beta, VaR, Sharpe, Factors)       │
    │                                       ▼
    ├─→ Technical Engine ──────────→ Decision Engine
    │   (RSI, MACD, BB, MA)         (Weighted combination)
    │                                       │
    ├─→ Regime Detector ───────────────────→│ Regime multiplier
    │   (Bull/Bear/HighVol)                 │
    │                                       │
    └─→ [News Sentiment] ──────────────────→│ (coming soon)
        [Event Risk]                        │
                                            ▼
                                    Ranked Opportunities
                                    + Reasoning
                                    + Position Sizing
```

## Extending the System

### Add a new data source
1. Create `backend/app/data/sources/your_source.py` extending `BaseDataSource`
2. Register in `DataIngestionManager._fetch_with_fallback()`

### Add a new signal
1. Implement your signal in `backend/app/analytics/`
2. Add a weight in `DecisionEngine.WEIGHTS`
3. Wire it in `DecisionEngine.evaluate()`

### Add a new API endpoint
1. Create a new route file in `backend/app/api/routes/`
2. Register the router in `backend/app/main.py`
