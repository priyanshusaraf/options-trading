"""Execution-plane authority for typed market-truth snapshots."""
from __future__ import annotations

from app.market_truth.identity import MarketTruthError, load_canonical_instrument
from app.market_truth.rulebook import MarketTruthSnapshot
from app.market_truth.temporal import require_sql_utc_naive, to_sql_utc_naive


def persist_market_truth_snapshot(session, snapshot: MarketTruthSnapshot) -> None:
    from app.db.models import AuthorityMarketTruthSnapshot
    if not isinstance(snapshot, MarketTruthSnapshot):
        raise MarketTruthError("only market-truth-snapshot/3 can enter authority storage")
    if snapshot.schema != MarketTruthSnapshot.SCHEMA:
        raise MarketTruthError("legacy market truth is reconstruction-only")
    snapshot.require_authority_complete()
    for address in snapshot.instrument_addresses:
        load_canonical_instrument(session, address)
    existing = session.get(AuthorityMarketTruthSnapshot, snapshot.address)
    if existing is not None:
        if load_market_truth_snapshot(session, snapshot.address).canonical_bytes != snapshot.canonical_bytes:
            raise MarketTruthError("market truth address collision")
        return
    session.add(AuthorityMarketTruthSnapshot(
        address=snapshot.address, schema=snapshot.SCHEMA,
        canonical_json=snapshot.canonical_bytes.decode("utf-8"),
        authority_scope=snapshot.authority_scope, quality=snapshot.quality.value,
        knowledge_cutoff=to_sql_utc_naive(snapshot.knowledge_cutoff, "knowledge_cutoff"),
        effective_from=to_sql_utc_naive(snapshot.effective_from, "effective_from"),
        effective_to=to_sql_utc_naive(snapshot.effective_to, "effective_to", nullable=True),
        authority_state="VERIFIED_V2"))
    session.flush()


def load_market_truth_snapshot(session, address: str) -> MarketTruthSnapshot:
    from app.db.models import AuthorityMarketTruthSnapshot
    row = session.get(AuthorityMarketTruthSnapshot, address)
    if (row is None or row.authority_state != "VERIFIED_V2"
            or row.schema not in MarketTruthSnapshot.SUPPORTED_SCHEMAS):
        raise MarketTruthError("market truth authority is absent")
    try:
        snapshot = MarketTruthSnapshot.from_bytes(row.canonical_json.encode("utf-8"))
    except (AttributeError, UnicodeError) as exc:
        raise MarketTruthError("market truth stored bytes are malformed") from exc
    checks = ((snapshot.address, row.address), (snapshot.schema, row.schema),
        (snapshot.authority_scope, row.authority_scope),
        (snapshot.quality.value, row.quality),
        (to_sql_utc_naive(snapshot.knowledge_cutoff, "knowledge_cutoff"),
         require_sql_utc_naive(row.knowledge_cutoff, "knowledge_cutoff")),
        (to_sql_utc_naive(snapshot.effective_from, "effective_from"),
         require_sql_utc_naive(row.effective_from, "effective_from")),
        (to_sql_utc_naive(snapshot.effective_to, "effective_to", nullable=True),
         require_sql_utc_naive(row.effective_to, "effective_to", nullable=True)))
    if any(left != right for left, right in checks):
        raise MarketTruthError("market truth copied columns do not match bytes")
    snapshot.require_loadable_authority()
    for instrument_address in snapshot.instrument_addresses:
        load_canonical_instrument(session, instrument_address)
    return snapshot


__all__ = ["load_market_truth_snapshot", "persist_market_truth_snapshot"]
