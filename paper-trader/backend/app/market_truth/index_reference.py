"""One source-reviewed index definition, separate from provider token mappings.

The retained excerpts below are transformed text from official references, not
original PDF bytes. Their address identifies this representation only. This
definition supplies no history, calendar, constituents, data rights or trading
authority. A new source snapshot need not change the instrument definition.
"""
from __future__ import annotations

from app.ir.hashing import content_address
from app.market_truth.identity import CanonicalPhysicalInstrument


def nifty_50_price_return_reference() -> tuple[CanonicalPhysicalInstrument, dict]:
    """Return the app-owned INR price-return definition and retained provenance."""
    instrument = CanonicalPhysicalInstrument(
        authority_namespace="strategy-os:index:nifty-50:inr:price-return",
        authority_version="1", venue_code="XNSE", asset_class="INDEX",
        contract_kind="SPOT", currency="INR", economic_underlier_address=None,
    )
    evidence = {
        "schema": "strategy-os-index-definition-reference/1",
        "representation": "TRANSFORMED_REFERENCE",
        "extraction_method": "Official web/PDF text extraction; selected excerpts retained verbatim",
        "retrieved_on": "2026-09-06",
        "instrument_address": instrument.address,
        "interpretation": {"name": "Nifty 50", "currency": "INR", "return_type": "PRICE_RETURN"},
        "sources": [
            {"url": "https://www.niftyindices.com/Factsheet/ind_nifty50.pdf",
             "document_date": "2026-08-31", "location": "page 1, statistics footnote",
             "excerpt": "Based on Price Return Index."},
            {"url": "https://www.niftyindices.com/indices/equity/broad-based-indices/nifty--50",
             "document_date": None, "location": "NIFTY 50 page, price display",
             "excerpt": "All Prices are in INR"},
            {"url": "https://www.niftyindices.com/BenchmarkCodes/nifty_indices_benchmark_codes.pdf",
             "document_date": "2026-08-31", "location": "page 1, row 5",
             "excerpt": "NSE_E_60 Nifty 50"},
        ],
    }
    return instrument, {"address": content_address(evidence), "document": evidence}
