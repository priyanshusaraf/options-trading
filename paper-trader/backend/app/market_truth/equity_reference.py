"""One sourced Indian cash equity, distinct from provider and historical aliases.

Excerpts are transformed official text, not retained original PDF bytes. The
reference identifies the NSE equity class; it grants no historical coverage,
corporate-action completeness, data rights, or execution authority.
"""
from __future__ import annotations

from app.ir.hashing import content_address
from app.market_truth.identity import CanonicalPhysicalInstrument


def infosys_equity_reference() -> tuple[CanonicalPhysicalInstrument, dict]:
    """Return the ISIN-based NSE equity root and its current source interpretation."""
    instrument = CanonicalPhysicalInstrument(
        authority_namespace="strategy-os:security:isin:INE009A01021", authority_version="1",
        venue_code="XNSE", asset_class="EQUITY", contract_kind="SPOT",
        currency="INR", economic_underlier_address=None,
    )
    document = {
        "schema": "strategy-os-equity-definition-reference/1",
        "representation": "TRANSFORMED_REFERENCE",
        "extraction_method": "Official issuer HTML and exchange PDF text extraction; selected excerpts retained verbatim",
        "retrieved_on": "2026-09-06",
        "instrument_address": instrument.address,
        "interpretation": {
            "name": "Infosys Limited", "symbol": "INFY", "isin": "INE009A01021",
            "security_class": "INDIAN_EQUITY", "exchange": "NSE", "series": "EQ",
            "currency": "INR",
        },
        "sources": [
            {"url": "https://nsearchives.nseindia.com/content/circulars/CML74479.pdf",
             "document_date": "2026-05-29", "effective_from": "2026-06-01",
             "location": "page 8, item 11; page 1 identifies NSE Capital Market admission",
             "excerpts": ["Symbol INFY", "Series EQ", "ISIN* INE009A01021",
                          "Equity shares of Rs. 5/- each allotted under ESOP.",
                          "Pari Passu Yes", "Name of the Company Infosys Limited"]},
            {"url": "https://www.infosys.com/investors/shareholder-services/faqs.html",
             "document_date": None, "location": "Corporate information, questions 12 and 13",
             "excerpts": ["The equity shares of Infosys are listed on BSE and NSE in India",
                          "The ISIN number of Infosys is - INE009A01021."]},
            {"url": "https://www.infosys.com/investors/shares/share-details.html",
             "document_date": None, "data_as_of": "2026-06-30",
             "location": "Share details / INR heading; Basic Data table",
             "excerpts": ["INR", "NSE Symbol", "INFY", "Equity share of par value", "Rs 5"]},
        ],
    }
    return instrument, {"address": content_address(document), "document": document}
