"""
Annual Report NLP Parser.

Parses PDF annual reports to extract:
  - Key suppliers / customers mentioned
  - Revenue segmentation by geography/product
  - Risk factors (regulatory, commodity, operational)
  - Management commentary on growth / headwinds
  - Related company mentions (to build supply chain edges)

Uses:
  - pdfplumber for PDF text extraction
  - Rule-based NLP patterns (no inference required)
  - Optional: transformers NER for entity extraction
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from backend.app.core.logging import logger


@dataclass
class ReportInsights:
    symbol: str
    filename: str
    year: Optional[int]

    # Extracted entities
    suppliers: list[str] = field(default_factory=list)
    customers: list[str] = field(default_factory=list)
    competitors: list[str] = field(default_factory=list)
    subsidiaries: list[str] = field(default_factory=list)

    # Revenue segmentation
    revenue_segments: list[dict] = field(default_factory=list)   # [{name, pct}]
    geographic_segments: list[dict] = field(default_factory=list)

    # Risks
    risk_factors: list[str] = field(default_factory=list)
    commodity_dependencies: list[str] = field(default_factory=list)
    regulatory_risks: list[str] = field(default_factory=list)

    # Sentiments from management discussion
    management_tone: str = "neutral"          # positive / negative / neutral
    growth_keywords: list[str] = field(default_factory=list)
    concern_keywords: list[str] = field(default_factory=list)

    # Raw text sections
    raw_risk_section: str = ""
    raw_mda_section: str = ""

    page_count: int = 0
    extraction_confidence: float = 0.5


# ── Pattern library ───────────────────────────────────────────────────────────

SUPPLIER_PATTERNS = [
    r"our (?:key |major |primary |principal )?suppliers? (?:include|are|comprise)[:\s]+([^.]+)\.",
    r"raw materials? (?:are |is )?(?:sourced|procured|purchased) from ([^.]+)\.",
    r"we (?:source|procure|purchase) .{0,30} from ([^.]+)\.",
    r"key vendors? include ([^.]+)\.",
]

CUSTOMER_PATTERNS = [
    r"our (?:key |major |principal |top )?customers? (?:include|are|comprise)[:\s]+([^.]+)\.",
    r"(?:sales|revenue) to ([^.]+) (?:account|accounted) for",
    r"(?:largest|key|major) customer[,\s]+([^,\.]+)",
]

REVENUE_SEGMENT_PATTERNS = [
    r"([\w\s&]+) segment (?:contributed|accounted for|represented) ([\d.]+)%",
    r"([\d.]+)% (?:of (?:total )?revenue) from ([\w\s&]+)",
    r"revenue from ([\w\s]+)[\s:]+(?:INR|Rs\.?|₹)?\s*([\d,]+)",
]

RISK_PATTERNS = [
    r"(?:risk|exposure|vulnerable|dependent) (?:to|on) (?:the )?([\w\s]+(?:prices?|supply|shortage|volatility|regulation|competition)[^.]{0,100})\.",
    r"(?:significant|material|key) risk[s]?[\s:]+([^.]{20,200})\.",
    r"(?:could|may|might) (?:adversely|negatively|materially) affect ([^.]{20,150})\.",
]

COMMODITY_PATTERNS = [
    r"(?:dependent|reliance|exposure) on ([\w\s]+) prices?",
    r"(crude oil|natural gas|coal|steel|aluminum|copper|cotton|sugar|palm oil|rubber|"
    r"wheat|semiconductors|rare earth|chemicals|fertilizers)",
    r"raw material[s]? (?:cost|price)[s]?[\s:,]+(?:including |mainly )?([\w\s,]+) (?:increased|decreased|rose|fell)",
]

GROWTH_KEYWORDS = {
    "growth", "expansion", "opportunity", "positive", "strong", "record", "outperform",
    "momentum", "robust", "increase", "improve", "advantage", "margin expansion",
    "market share", "launch", "new product", "diversification",
}

CONCERN_KEYWORDS = {
    "headwind", "challenge", "risk", "pressure", "concern", "uncertainty",
    "slowdown", "decline", "decrease", "competition", "regulatory", "inflation",
    "supply chain disruption", "shortage", "rising costs", "volatility",
}


class AnnualReportParser:
    """Parse annual report PDFs and extract structured insights."""

    def parse(self, pdf_path: Path, symbol: str) -> ReportInsights:
        try:
            import pdfplumber
        except ImportError:
            logger.error("[ReportParser] pdfplumber not installed. Run: pip install pdfplumber")
            return ReportInsights(symbol=symbol, filename=str(pdf_path), year=None)

        if not pdf_path.exists():
            logger.error(f"[ReportParser] File not found: {pdf_path}")
            return ReportInsights(symbol=symbol, filename=str(pdf_path), year=None)

        logger.info(f"[ReportParser] Parsing {pdf_path.name} for {symbol}")

        insights = ReportInsights(symbol=symbol, filename=pdf_path.name, year=None)

        try:
            with pdfplumber.open(pdf_path) as pdf:
                insights.page_count = len(pdf.pages)
                full_text = "\n".join(
                    page.extract_text() or "" for page in pdf.pages
                )

            if not full_text.strip():
                logger.warning(f"[ReportParser] No text extracted from {pdf_path.name}")
                return insights

            # ── Extract year from filename or text ────────────────────────────
            year_match = re.search(r"20(1[5-9]|2[0-9])", pdf_path.name)
            if year_match:
                insights.year = int(year_match.group())

            # ── Segment the document ──────────────────────────────────────────
            insights.raw_risk_section = self._extract_section(
                full_text, ["risk factor", "risk management", "principal risks"]
            )
            insights.raw_mda_section = self._extract_section(
                full_text, ["management discussion", "management's discussion", "md&a",
                            "directors' report", "management analysis"]
            )

            # ── Extract entities ──────────────────────────────────────────────
            insights.suppliers = self._extract_with_patterns(full_text, SUPPLIER_PATTERNS)
            insights.customers = self._extract_with_patterns(full_text, CUSTOMER_PATTERNS)
            insights.commodity_dependencies = self._extract_commodities(full_text)
            insights.risk_factors = self._extract_risks(insights.raw_risk_section or full_text)

            # ── Revenue segments ──────────────────────────────────────────────
            insights.revenue_segments = self._extract_revenue_segments(full_text)

            # ── Management tone ───────────────────────────────────────────────
            mda = insights.raw_mda_section or full_text[:20000]
            insights.management_tone, insights.growth_keywords, insights.concern_keywords = \
                self._analyze_tone(mda)

            insights.extraction_confidence = self._confidence(insights)
            logger.info(f"[ReportParser] Extracted insights for {symbol} (confidence={insights.extraction_confidence:.0%})")

        except Exception as e:
            logger.error(f"[ReportParser] Failed to parse {pdf_path.name}: {e}", exc_info=True)

        return insights

    # ── Section extraction ────────────────────────────────────────────────────

    def _extract_section(self, text: str, headers: list[str], max_chars: int = 8000) -> str:
        """Find and extract a named section from the document."""
        text_lower = text.lower()
        for header in headers:
            idx = text_lower.find(header)
            if idx != -1:
                # Find end of section (next major heading pattern)
                end_match = re.search(
                    r"\n[A-Z][A-Z\s]{5,50}\n",
                    text[idx + len(header) + 100:idx + len(header) + max_chars]
                )
                end = idx + len(header) + (end_match.start() if end_match else max_chars)
                return text[idx:end].strip()
        return ""

    # ── Pattern-based extractors ──────────────────────────────────────────────

    def _extract_with_patterns(self, text: str, patterns: list[str]) -> list[str]:
        results = set()
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE):
                raw = match.group(1).strip()
                # Clean and split on common delimiters
                for item in re.split(r"[,;]|and\s+(?=[A-Z])", raw):
                    item = re.sub(r"\s+", " ", item).strip(" .,;")
                    if 3 < len(item) < 80:
                        results.add(item)
        return list(results)[:20]

    def _extract_commodities(self, text: str) -> list[str]:
        """Extract commodity names using the commodity pattern list."""
        found = set()
        for match in re.finditer(COMMODITY_PATTERNS[1], text, re.IGNORECASE):
            found.add(match.group(0).lower())
        for pattern in [COMMODITY_PATTERNS[0], COMMODITY_PATTERNS[2]]:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                raw = match.group(1).strip()
                for item in re.split(r"[,;]|\sand\s", raw):
                    item = item.strip()
                    if 3 < len(item) < 40:
                        found.add(item.lower())
        return list(found)[:15]

    def _extract_risks(self, text: str) -> list[str]:
        risks = set()
        for pattern in RISK_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE | re.DOTALL):
                risk = re.sub(r"\s+", " ", match.group(1)).strip()
                if 20 < len(risk) < 200:
                    risks.add(risk)
        return list(risks)[:15]

    def _extract_revenue_segments(self, text: str) -> list[dict]:
        segments = []
        seen = set()
        for pattern in REVENUE_SEGMENT_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                try:
                    if "%" in pattern:
                        name = match.group(1).strip()
                        pct = float(match.group(2))
                    else:
                        name = match.group(2).strip()
                        pct = 0.0
                    name_clean = re.sub(r"\s+", " ", name).strip()
                    if name_clean not in seen and len(name_clean) > 2:
                        seen.add(name_clean)
                        segments.append({"name": name_clean, "pct": pct})
                except (IndexError, ValueError):
                    continue
        return segments[:10]

    # ── Tone analysis ─────────────────────────────────────────────────────────

    def _analyze_tone(self, text: str) -> tuple[str, list[str], list[str]]:
        words = set(re.findall(r"\b\w+\b", text.lower()))
        bigrams = set()
        word_list = re.findall(r"\b\w+\b", text.lower())
        for i in range(len(word_list) - 1):
            bigrams.add(f"{word_list[i]} {word_list[i+1]}")
        all_tokens = words | bigrams

        growth_found = list(GROWTH_KEYWORDS & all_tokens)[:8]
        concern_found = list(CONCERN_KEYWORDS & all_tokens)[:8]

        g = len(growth_found)
        c = len(concern_found)
        if g > c * 1.5:
            tone = "positive"
        elif c > g * 1.5:
            tone = "negative"
        else:
            tone = "neutral"

        return tone, growth_found, concern_found

    def _confidence(self, insights: ReportInsights) -> float:
        scores = [
            0.3 if insights.raw_risk_section else 0.0,
            0.2 if insights.raw_mda_section else 0.0,
            0.2 if insights.commodity_dependencies else 0.0,
            0.15 if insights.risk_factors else 0.0,
            0.15 if insights.revenue_segments else 0.0,
        ]
        return min(sum(scores), 1.0)

    # ── Graph integration ─────────────────────────────────────────────────────

    def insights_to_graph_data(self, insights: ReportInsights) -> dict:
        """
        Convert insights to graph edges for SupplyChainGraph.
        Returns: {suppliers, customers, commodities}
        """
        return {
            "symbol": insights.symbol,
            "suppliers": insights.suppliers,
            "customers": insights.customers,
            "commodities": insights.commodity_dependencies,
            "sector": None,  # Inferred from watchlist
        }
