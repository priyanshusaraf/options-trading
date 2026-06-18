"""
News Sentiment Engine — FinBERT-based financial sentiment analysis.

Architecture:
  - Primary: FinBERT (ProsusAI/finbert) — fine-tuned on financial text
  - Fallback: Lexicon-based (VADER + financial word lists) when GPU/model unavailable
  - All inference results are cached to disk to avoid repeated API calls
  - Batch processing preferred over real-time

Output per news item:
  - sentiment: "positive" / "negative" / "neutral"
  - score: float (-1 to +1)
  - confidence: float (0 to 1)
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

import numpy as np

from backend.app.core.cache import cached
from backend.app.core.logging import logger


@dataclass
class SentimentResult:
    text: str
    sentiment: str        # "positive" / "negative" / "neutral"
    score: float          # –1 to +1
    confidence: float     # 0 to 1
    method: str           # "finbert" or "lexicon"


# ── Lexicon (offline fallback) ────────────────────────────────────────────────

POSITIVE_WORDS = {
    "surge", "rally", "gain", "profit", "growth", "beat", "exceed", "outperform",
    "strong", "record", "upgrade", "buy", "bullish", "optimistic", "expand",
    "increase", "rise", "jump", "soar", "boost", "robust", "recovery", "positive",
    "upside", "opportunity", "momentum", "breakthrough", "approval", "dividend",
    "acquisition", "merger", "partnership", "contract", "win", "award", "launch",
}

NEGATIVE_WORDS = {
    "fall", "drop", "decline", "loss", "miss", "below", "underperform", "weak",
    "cut", "downgrade", "sell", "bearish", "pessimistic", "shrink", "decrease",
    "slump", "crash", "collapse", "warning", "risk", "concern", "threat", "fraud",
    "scandal", "lawsuit", "fine", "penalty", "recall", "shortage", "supply chain",
    "inflation", "recession", "default", "bankruptcy", "downside", "headwind",
    "disappointing", "miss", "writedown", "impairment", "layoff", "restructure",
}

INTENSIFIERS = {"very", "extremely", "significantly", "sharply", "massively", "deeply"}
NEGATORS = {"not", "no", "never", "without", "despite", "fail", "unable"}


def lexicon_sentiment(text: str) -> SentimentResult:
    """
    Rule-based lexicon sentiment as fallback when FinBERT is unavailable.
    Handles negation and intensification.
    """
    words = re.findall(r"\b\w+\b", text.lower())
    score = 0.0
    intensifier_active = False
    negation_active = False
    window = 4  # Negation window

    for i, word in enumerate(words):
        if word in INTENSIFIERS:
            intensifier_active = True
            continue
        if word in NEGATORS:
            negation_active = True
            negation_end = i + window
            continue

        weight = 1.5 if intensifier_active else 1.0
        intensifier_active = False

        if i > negation_end if negation_active else False:
            negation_active = False

        if word in POSITIVE_WORDS:
            score += (-weight if negation_active else weight)
        elif word in NEGATIVE_WORDS:
            score += (weight if negation_active else -weight)

    n = len(words) or 1
    normalized = float(np.tanh(score / (n ** 0.5) * 3))
    sentiment = "positive" if normalized > 0.1 else "negative" if normalized < -0.1 else "neutral"
    confidence = min(abs(normalized) + 0.3, 1.0)

    return SentimentResult(
        text=text[:100],
        sentiment=sentiment,
        score=normalized,
        confidence=confidence,
        method="lexicon",
    )


# ── FinBERT ────────────────────────────────────────────────────────────────────

_finbert_pipeline = None
_finbert_available = None


def _get_finbert():
    """Lazy-load FinBERT pipeline. Returns None if unavailable."""
    global _finbert_pipeline, _finbert_available
    if _finbert_available is False:
        return None
    if _finbert_pipeline is not None:
        return _finbert_pipeline
    try:
        from transformers import pipeline
        logger.info("[Sentiment] Loading FinBERT model (ProsusAI/finbert)...")
        _finbert_pipeline = pipeline(
            "text-classification",
            model="ProsusAI/finbert",
            device=-1,         # CPU; set to 0 for GPU
            top_k=None,
            truncation=True,
            max_length=512,
        )
        _finbert_available = True
        logger.info("[Sentiment] FinBERT loaded successfully.")
    except Exception as e:
        logger.warning(f"[Sentiment] FinBERT unavailable: {e}. Using lexicon fallback.")
        _finbert_available = False
        _finbert_pipeline = None
    return _finbert_pipeline


def finbert_sentiment(text: str) -> SentimentResult:
    """Run FinBERT on a single text. Falls back to lexicon if model unavailable."""
    pipe = _get_finbert()
    if pipe is None:
        return lexicon_sentiment(text)

    try:
        truncated = text[:512]
        outputs = pipe(truncated)[0]  # list of {label, score}
        label_map = {"positive": 1.0, "negative": -1.0, "neutral": 0.0}
        best = max(outputs, key=lambda x: x["score"])
        score = label_map.get(best["label"].lower(), 0.0) * best["score"]
        return SentimentResult(
            text=truncated[:100],
            sentiment=best["label"].lower(),
            score=float(score),
            confidence=float(best["score"]),
            method="finbert",
        )
    except Exception as e:
        logger.warning(f"[Sentiment] FinBERT inference failed: {e}")
        return lexicon_sentiment(text)


# ── Batch Analyzer ────────────────────────────────────────────────────────────

class SentimentAnalyzer:
    """
    Analyzes lists of news headlines/articles.
    Caches results to avoid re-inference.
    """

    @cached(ttl=86400, prefix="sentiment:item")
    def analyze_text(self, text: str) -> SentimentResult:
        """Analyze a single text. Result is cached per unique text."""
        return finbert_sentiment(text)

    def analyze_batch(self, texts: list[str]) -> list[SentimentResult]:
        """Analyze multiple texts. Each result independently cached."""
        return [self.analyze_text(t) for t in texts]

    def aggregate(self, results: list[SentimentResult], weights: Optional[list[float]] = None) -> dict:
        """
        Aggregate multiple sentiment results into a composite score.
        Returns: {score, sentiment, confidence, count, breakdown}
        """
        if not results:
            return {"score": 0.0, "sentiment": "neutral", "confidence": 0.0, "count": 0}

        weights = weights or [1.0] * len(results)
        total_w = sum(weights)
        if total_w == 0:
            return {"score": 0.0, "sentiment": "neutral", "confidence": 0.0, "count": 0}

        w_score = sum(r.score * w for r, w in zip(results, weights)) / total_w
        w_conf = sum(r.confidence * w for r, w in zip(results, weights)) / total_w

        sentiment = "positive" if w_score > 0.1 else "negative" if w_score < -0.1 else "neutral"
        breakdown = {
            "positive": sum(1 for r in results if r.sentiment == "positive"),
            "negative": sum(1 for r in results if r.sentiment == "negative"),
            "neutral": sum(1 for r in results if r.sentiment == "neutral"),
        }

        return {
            "score": round(float(w_score), 4),
            "sentiment": sentiment,
            "confidence": round(float(w_conf), 4),
            "count": len(results),
            "breakdown": breakdown,
        }
