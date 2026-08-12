"""Execution-side store for deployed generated strategies.

When the owner approves a generated PromotionCandidate, the deploy bridge persists the
strategy's composition here (execution DB), so the engine can run it WITHOUT reaching
back into research.db at runtime — the composition is copied across the plane boundary
once, at the human-gated deploy. At startup `register_all` reconstructs each row through
the sandboxed builder and registers it in the strategy registry.

`register_all` is resilient: a row that fails to rebuild (corrupt JSON, a block removed
from the grammar) is logged and skipped, never crashing engine startup. That row's
`gen_*` key then simply falls back to the default strategy — fail-safe, not fail-open.

**That last sentence is the C4 defect, and it is only tolerable while there is one
owner.** Under a marketplace a skipped row means the customer's capital trades the
platform default under the customer's strategy name. The fail-closed half of the fix
lives in `app.strategy.registry.resolve_strategy`; any deployment-bound caller must use
it rather than `get_strategy`, so a row that failed to load here becomes a halted
deployment instead of a silent substitution.

Each rebuilt strategy is pinned to a content hash of its PERSISTED composition
(`app/strategy/identity.py`), so `(key, version)` identifies the artifact. `key` alone
cannot: the row is keyed by `key` and re-deploying an edited strategy overwrites it in
place, which would otherwise re-attribute every past trade to logic that never ran.
"""
from __future__ import annotations

import json

from app.core.logging import log
from app.db.models import GeneratedStrategyRow
from app.strategy.identity import composition_code, content_hash


def save_generated(session, key: str, composition_json: str, *, owner_id: str, source: str = ""):
    """Upsert a generated strategy's composition. Idempotent on re-deploy.

    The content `version` is recorded on every write (Phase D). `key` is still the
    primary key, so re-deploying an EDITED strategy still overwrites in place — that
    is the C4 defect and it is not fixed here. What the version does fix is
    detectability: after this, an overwrite that changes behaviour changes the stored
    version, so trades attributed to the old version can be told apart from trades
    attributed to the new one instead of both silently pointing at whatever the row
    happens to contain today. Making identity `(key, version)` is tracked as
    remaining work in docs/reports/2026-08-02-architecture-migration.md.
    """
    try:
        version = generated_version(json.loads(composition_json))
    except Exception:
        # A composition that will not parse cannot register either; record it as
        # unidentifiable rather than failing the write, matching build_sha's
        # 'unknown' sentinel (distinct from NULL, which means "predates the column").
        version = "unknown"
    row = session.get(GeneratedStrategyRow, (owner_id, key))
    if row is None:
        row = GeneratedStrategyRow(owner_id=owner_id, key=key, composition_json=composition_json,
                                   source=source, version=version)
        session.add(row)
    else:
        row.composition_json = composition_json
        row.source = source
        row.version = version
    return row


def generated_version(composition, default_params=None, risk_model=None) -> str:
    """Content version of a generated strategy, computed from its COMPOSITION.

    The composition is the artifact — the `GeneratedStrategy` wrapper class is shared by
    every generated strategy, so hashing class source would give them all one version.
    Accepts a `Composition` or a raw parsed dict (e.g. straight off
    `row.composition_json`) and hashes both to the SAME value: a raw dict is first
    round-tripped through the grammar, because `Composition.to_dict` re-renders each
    clause into its canonical text ("zscore_lt(50,0.0)" spelling, argument formatting).
    Without that normalisation the version of a stored row would differ from the version
    of the strategy actually rebuilt from it — two identities for one artifact, which is
    worse than none. A dict the grammar rejects is hashed as-is: such a row can never
    register anyway, so its version is only ever used to report the bad row.
    """
    to_dict = getattr(composition, "to_dict", None)
    if callable(to_dict):
        comp_dict = to_dict()
    else:
        comp_dict = composition
        try:
            from research.strategy.builder.grammar import Composition
            comp_dict = Composition.from_dict(comp_dict).to_dict()
        except Exception:
            pass
    key = comp_dict.get("key", "") if isinstance(comp_dict, dict) else ""
    return content_hash(key=str(key or ""),
                        code=composition_code(comp_dict),
                        default_params=default_params,
                        risk_model=risk_model)


def list_generated(session, *, owner_id: str) -> list:
    return session.query(GeneratedStrategyRow).filter_by(owner_id=owner_id).all()


def register_all(session, *, owner_id: str) -> int:
    """Rebuild + register every persisted generated strategy. Returns the count
    registered. Never raises: a bad row is logged and skipped."""
    # imported lazily so the execution import graph doesn't pull the builder unless a
    # generated strategy actually exists to load.
    from research.strategy.builder.grammar import Composition
    from research.strategy.builder.load import build_strategy
    from app.strategy import registry

    count = 0
    for row in list_generated(session, owner_id=owner_id):
        try:
            comp = Composition.from_dict(json.loads(row.composition_json))
            strat = build_strategy(comp)
            # Pin BEFORE registering: a registered strategy must never be observable
            # without its version, or a caller can read `(key, <lazily-derived>)` and
            # attribute a fill to an identity nothing persisted.
            strat.pin_version(generated_version(
                comp, default_params=getattr(strat, "default_params", None),
                risk_model=getattr(strat, "risk_model", None)))
            registry.register(strat, owner_id=owner_id)
            count += 1
        except Exception as e:  # corrupt/incompatible row — skip, don't crash startup
            log.warn(f"generated strategy {row.key!r} failed to load, skipping: {e}")
    if count:
        log.info(f"registered {count} deployed generated strateg"
                 f"{'y' if count == 1 else 'ies'}")
    return count
