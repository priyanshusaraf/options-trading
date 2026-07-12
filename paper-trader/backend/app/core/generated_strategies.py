"""Execution-side store for deployed generated strategies.

When the owner approves a generated PromotionCandidate, the deploy bridge persists the
strategy's composition here (execution DB), so the engine can run it WITHOUT reaching
back into research.db at runtime — the composition is copied across the plane boundary
once, at the human-gated deploy. At startup `register_all` reconstructs each row through
the sandboxed builder and registers it in the strategy registry.

`register_all` is resilient: a row that fails to rebuild (corrupt JSON, a block removed
from the grammar) is logged and skipped, never crashing engine startup. That row's
`gen_*` key then simply falls back to the default strategy — fail-safe, not fail-open.
"""
from __future__ import annotations

import json

from app.core.logging import log
from app.db.models import GeneratedStrategyRow


def save_generated(session, key: str, composition_json: str, source: str = ""):
    """Upsert a generated strategy's composition. Idempotent on re-deploy."""
    row = session.get(GeneratedStrategyRow, key)
    if row is None:
        row = GeneratedStrategyRow(key=key, composition_json=composition_json, source=source)
        session.add(row)
    else:
        row.composition_json = composition_json
        row.source = source
    return row


def list_generated(session) -> list:
    return session.query(GeneratedStrategyRow).all()


def register_all(session) -> int:
    """Rebuild + register every persisted generated strategy. Returns the count
    registered. Never raises: a bad row is logged and skipped."""
    # imported lazily so the execution import graph doesn't pull the builder unless a
    # generated strategy actually exists to load.
    from research.strategy.builder.grammar import Composition
    from research.strategy.builder.load import build_strategy
    from app.strategy import registry

    count = 0
    for row in list_generated(session):
        try:
            comp = Composition.from_dict(json.loads(row.composition_json))
            registry.register(build_strategy(comp))
            count += 1
        except Exception as e:  # corrupt/incompatible row — skip, don't crash startup
            log.warn(f"generated strategy {row.key!r} failed to load, skipping: {e}")
    if count:
        log.info(f"registered {count} deployed generated strateg"
                 f"{'y' if count == 1 else 'ies'}")
    return count
