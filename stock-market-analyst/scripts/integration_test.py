#!/usr/bin/env python3
"""
Full System Integration Test.

Runs an end-to-end smoke test across all core modules:
  1. Database init
  2. Data ingestion (yfinance)
  3. Quant engine
  4. Technical analysis
  5. Regime detection
  6. Decision engine + position sizing
  7. News intelligence (lexicon, no API required)
  8. Event calendar
  9. Alerts engine
  10. Commodity linker
  11. Supply chain graph

Usage:
    python scripts/integration_test.py

Pass --verbose for detailed output.
"""
import sys
import os
import traceback
import time
import argparse
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.app.core.logging import configure_logging

configure_logging()

PASSED = "  ✓"
FAILED = "  ✗"


def run_test(name: str, fn, verbose: bool = False):
    start = time.time()
    try:
        result = fn()
        elapsed = time.time() - start
        print(f"{PASSED}  {name} ({elapsed:.2f}s)")
        if verbose and result:
            print(f"      → {result}")
        return True
    except Exception as e:
        elapsed = time.time() - start
        print(f"{FAILED}  {name} ({elapsed:.2f}s)")
        print(f"      ERROR: {e}")
        if verbose:
            traceback.print_exc()
        return False


def main(verbose=False):
    print("=" * 60)
    print("  Stock Market Intelligence Platform — Integration Test")
    print("=" * 60)

    results = []
    SYMBOL = "TCS"
    YF_SYMBOL = f"{SYMBOL}.NS"
    BENCHMARK = "^NSEI"

    # ── 1. Database ───────────────────────────────────────────────────────────
    def test_db():
        from backend.app.data.models.database import init_db, get_engine
        init_db()
        engine = get_engine()
        return f"DB at {engine.url}"

    results.append(run_test("Database initialization", test_db, verbose))

    # ── 2. Data Ingestion ─────────────────────────────────────────────────────
    def test_ingestion():
        from backend.app.data.ingestion import DataIngestionManager
        mgr = DataIngestionManager()
        end = date.today()
        start = end - timedelta(days=90)
        df = mgr.get_ohlcv(YF_SYMBOL, start, end)
        assert not df.empty, "Empty OHLCV returned"
        return f"{len(df)} rows for {SYMBOL}"

    results.append(run_test("Data ingestion (yfinance)", test_ingestion, verbose))

    # ── 3. Quant Engine ───────────────────────────────────────────────────────
    def test_quant():
        from backend.app.data.ingestion import DataIngestionManager
        from backend.app.analytics.quant.engine import QuantEngine
        mgr = DataIngestionManager()
        end = date.today()
        start = end - timedelta(days=504)
        df = mgr.get_ohlcv(YF_SYMBOL, start, end)
        bmark = mgr.get_ohlcv(BENCHMARK, start, end)
        engine = QuantEngine()
        metrics = engine.compute(SYMBOL, df, benchmark_df=bmark if not bmark.empty else None)
        assert -2 <= metrics.composite_score <= 2
        return f"composite_score={metrics.composite_score:.3f}, beta={metrics.beta:.3f}"

    results.append(run_test("Quant engine", test_quant, verbose))

    # ── 4. Technical Analysis ─────────────────────────────────────────────────
    def test_technical():
        from backend.app.data.ingestion import DataIngestionManager
        from backend.app.analytics.technical.engine import TechnicalEngine
        mgr = DataIngestionManager()
        end = date.today()
        start = end - timedelta(days=300)
        df = mgr.get_ohlcv(YF_SYMBOL, start, end)
        engine = TechnicalEngine()
        signals = engine.compute(SYMBOL, df)
        assert 0 <= signals.rsi_14 <= 100
        return f"RSI={signals.rsi_14:.1f}, signal={signals.signal}, conf={signals.confidence:.2f}"

    results.append(run_test("Technical analysis", test_technical, verbose))

    # ── 5. Regime Detection ───────────────────────────────────────────────────
    def test_regime():
        from backend.app.data.ingestion import DataIngestionManager
        from backend.app.intelligence.regime.detector import RegimeDetector
        mgr = DataIngestionManager()
        end = date.today()
        start = end - timedelta(days=365)
        df = mgr.get_ohlcv(BENCHMARK, start, end)
        detector = RegimeDetector()
        result = detector.detect(df)
        assert result.regime is not None
        return f"regime={result.regime.value}, conf={result.confidence:.2f}"

    results.append(run_test("Regime detection", test_regime, verbose))

    # ── 6. Decision Engine ────────────────────────────────────────────────────
    def test_decision():
        from backend.app.data.ingestion import DataIngestionManager
        from backend.app.analytics.quant.engine import QuantEngine
        from backend.app.analytics.technical.engine import TechnicalEngine
        from backend.app.decision.engine import DecisionEngine
        from backend.app.intelligence.regime.detector import RegimeDetector

        mgr = DataIngestionManager()
        end = date.today()
        start = end - timedelta(days=504)
        df = mgr.get_ohlcv(YF_SYMBOL, start, end)
        bmark = mgr.get_ohlcv(BENCHMARK, start, end)

        qm = QuantEngine().compute(SYMBOL, df, benchmark_df=bmark if not bmark.empty else None)
        ts = TechnicalEngine().compute(SYMBOL, df)
        regime = RegimeDetector().detect(bmark if not bmark.empty else df)

        dec = DecisionEngine()
        opp = dec.evaluate(symbol=SYMBOL, quant=qm, technical=ts, regime=regime)
        assert opp.action in ("STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL")
        return f"action={opp.action}, score={opp.score:.3f}, conf={opp.confidence:.2f}"

    results.append(run_test("Decision engine", test_decision, verbose))

    # ── 7. Position Sizer ─────────────────────────────────────────────────────
    def test_sizer():
        from backend.app.decision.position_sizer import PositionSizer

        opps = [
            {"symbol": "TCS", "score": 0.5, "confidence": 0.7, "annual_vol": 0.22, "sector": "Technology"},
            {"symbol": "RELIANCE", "score": 0.4, "confidence": 0.65, "annual_vol": 0.25, "sector": "Energy"},
            {"symbol": "HDFCBANK", "score": 0.3, "confidence": 0.6, "annual_vol": 0.20, "sector": "Financials"},
        ]
        sizer = PositionSizer()
        result = sizer.allocate(opps)
        assert result.total_allocated_pct > 0
        assert result.total_allocated_pct <= 100
        return (
            f"total={result.total_allocated_pct:.1f}%, "
            f"cash={result.cash_pct:.1f}%, "
            f"dr={result.diversification_ratio:.2f}"
        )

    results.append(run_test("Position sizer", test_sizer, verbose))

    # ── 8. News Intelligence ──────────────────────────────────────────────────
    def test_news_sentiment():
        from backend.app.intelligence.news.sentiment import SentimentAnalyzer, lexicon_sentiment
        from backend.app.intelligence.news.event_extractor import EventExtractor

        result = lexicon_sentiment("Record profits and strong revenue growth beat expectations")
        assert result.score > 0, "Positive text should have positive score"

        extractor = EventExtractor()
        events = extractor.extract("Federal Reserve raises interest rates by 25bps")
        # Just ensure it doesn't crash; events may or may not be detected
        assert isinstance(events, list)
        return f"sentiment={result.label} ({result.score:.2f}), events={len(events)}"

    results.append(run_test("News intelligence (offline)", test_news_sentiment, verbose))

    # ── 9. Event Calendar ─────────────────────────────────────────────────────
    def test_calendar():
        from backend.app.intelligence.events.calendar import EventCalendar
        cal = EventCalendar()
        events = cal.upcoming(days_ahead=60)
        assert isinstance(events, list)
        return f"{len(events)} events in next 60 days"

    results.append(run_test("Event calendar", test_calendar, verbose))

    # ── 10. Alerts Engine ─────────────────────────────────────────────────────
    def test_alerts():
        from backend.app.intelligence.alerts.engine import AlertsEngine, AlertRequest, AlertType
        engine = AlertsEngine()
        req = AlertRequest("TESTSTOCK", AlertType.RSI_OVERSOLD, 30.0, notes="integration test")
        created = engine.create(req)
        assert created.id is not None
        engine.delete(created.id)
        return f"Created and deleted alert id={created.id}"

    results.append(run_test("Alerts engine", test_alerts, verbose))

    # ── 11. Commodity Linker ──────────────────────────────────────────────────
    def test_commodities():
        from backend.app.data.ingestion import DataIngestionManager
        from backend.app.analytics.macro.commodity_linker import CommodityLinker
        mgr = DataIngestionManager()
        end = date.today()
        start = end - timedelta(days=365)
        df = mgr.get_ohlcv(YF_SYMBOL, start, end)
        linker = CommodityLinker()
        result = linker.analyze(SYMBOL, df, sector="Technology")
        assert isinstance(result.links, list)
        return f"{len(result.links)} commodity links found for {SYMBOL}"

    results.append(run_test("Commodity linker", test_commodities, verbose))

    # ── 12. Supply Chain Graph ────────────────────────────────────────────────
    def test_graph():
        from backend.app.graph.supply_chain import SupplyChainGraph
        graph = SupplyChainGraph()
        graph.add_company("TCS", sector="Technology", market_cap=1e13)
        graph.add_company("RELIANCE", sector="Energy", market_cap=2e13)
        graph.add_supplier_edge("TCS", "RELIANCE", weight=0.3)
        nodes, edges = graph.to_json()
        assert len(nodes) >= 2
        return f"{len(nodes)} nodes, {len(edges)} edges"

    results.append(run_test("Supply chain graph", test_graph, verbose))

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    status = "PASS" if passed == total else f"PARTIAL ({passed}/{total})"
    print(f"  Result: {status}")
    print("=" * 60)

    if passed < total:
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Integration smoke test")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()
    main(verbose=args.verbose)
