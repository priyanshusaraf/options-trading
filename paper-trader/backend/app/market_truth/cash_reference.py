"""Closed source lookup for the two admitted current NSE cash references.

A returned definition is not a persisted registration or historical alias.
Callers retain their own owner, registration and acquisition checks.
"""
import datetime as dt
import json

from app.ir.hashing import canonical_json, content_address
from app.market_truth.identity import MarketTruthError
from app.market_truth.equity_reference import infosys_equity_reference
from app.market_truth.index_reference import nifty_50_price_return_reference


_REFERENCES = {
    ("NIFTY 50", "NSE"): nifty_50_price_return_reference,
    ("INFY", "NSE"): infosys_equity_reference,
}


def source_reference_for_symbol(symbol: str, exchange: str):
    factory = _REFERENCES.get((symbol, exchange))
    return None if factory is None else factory()


def source_reference_for_address(address: str):
    for factory in _REFERENCES.values():
        instrument, evidence = factory()
        if instrument.address == address:
            return instrument, evidence
    return None


def source_reference_label(address: str) -> str | None:
    reference = source_reference_for_address(address)
    if reference is None:
        return None
    instrument, evidence = reference
    interpretation = evidence["document"]["interpretation"]
    if instrument.asset_class == "INDEX":
        return f'{interpretation["name"]} · {instrument.currency} · Price return'
    return f'{interpretation["name"]} · {interpretation["exchange"]} · Equity · {instrument.currency}'


def _require_definition(condition):
    if not condition:
        raise MarketTruthError("retained instrument definition does not match its source selection")


def _equity_definition(document, instrument, symbol, exchange):
    interpretation = document["interpretation"]
    _require_definition(set(interpretation) == {
        "name", "symbol", "isin", "security_class", "exchange", "series", "currency"})
    _require_definition((interpretation["symbol"], interpretation["exchange"],
        interpretation["security_class"], interpretation["series"], interpretation["currency"])
        == (symbol, exchange, "INDIAN_EQUITY", "EQ", "INR"))
    _require_definition((instrument.authority_namespace, instrument.authority_version,
        instrument.venue_code, instrument.asset_class, instrument.contract_kind,
        instrument.currency, instrument.economic_underlier_address) == (
        f"strategy-os:security:isin:{interpretation['isin']}", "1",
        {"NSE": "XNSE", "BSE": "XBOM"}.get(exchange), "EQUITY", "SPOT", "INR", None))


def _index_definition(document, instrument, symbol, exchange):
    expected, _ = nifty_50_price_return_reference()
    _require_definition(instrument == expected and (symbol, exchange) == ("NIFTY 50", "NSE")
        and document["interpretation"] == {
            "name": "Nifty 50", "currency": "INR", "return_type": "PRICE_RETURN"})


def verify_retained_definition(payload, instrument, *, symbol, exchange, recorded_at):
    """Verify the retained interpretation, without replacing it with today's source text.

    Publication admits this document against the sourced definition registry.
    Replay checks its stored meaning and bytes; it does not grant a new root.
    """
    value = json.loads(payload)
    _require_definition(type(value) is dict and set(value) == {"address", "document"}
        and canonical_json(value).encode() == payload)
    document = value["document"]
    _require_definition(type(document) is dict and set(document) == {
        "schema", "representation", "extraction_method", "retrieved_on",
        "instrument_address", "interpretation", "sources"})
    _require_definition(content_address(document) == value["address"]
        and document["instrument_address"] == instrument.address
        and document["representation"] == "TRANSFORMED_REFERENCE"
        and dt.date.fromisoformat(document["retrieved_on"]) <= recorded_at.date())
    decoders = {"strategy-os-equity-definition-reference/1": _equity_definition,
        "strategy-os-index-definition-reference/1": _index_definition}
    _require_definition(document["schema"] in decoders)
    decoders[document["schema"]](document, instrument, symbol, exchange)
    return value
