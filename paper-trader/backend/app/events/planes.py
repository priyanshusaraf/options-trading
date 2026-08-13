"""Closed event vocabularies and repository factories for each private plane."""
from app.events.outbox import OutboxRepository

EXECUTION_EVENT_TYPES = frozenset({
    "execution.lease.changed", "execution.control.changed",
    "execution.lifecycle.changed", "execution.position.changed",
    "execution.money.changed",
    "execution.backtest.changed", "execution.deployment.changed",
    "execution.graph.changed", "execution.runtime_config.changed",
    "execution.universe_preference.changed", "execution.connection.changed",
})
RESEARCH_EVENT_TYPES = frozenset({
    "research.operation.changed", "research.finding.changed",
    "research.spec.changed", "research.run.changed", "research.promotion.changed",
})
LEDGER_EVENT_TYPES = frozenset({
    "ledger.snapshot.changed", "ledger.artifact.changed", "ledger.manual_fill.changed",
})


def execution_outbox() -> OutboxRepository:
    from app.db.models import EXECUTION_OUTBOX_MODELS
    return OutboxRepository(EXECUTION_OUTBOX_MODELS, plane="execution",
                            allowed_event_types=EXECUTION_EVENT_TYPES)


def research_outbox() -> OutboxRepository:
    from research.domain.models import RESEARCH_OUTBOX_MODELS
    return OutboxRepository(RESEARCH_OUTBOX_MODELS, plane="research",
                            allowed_event_types=RESEARCH_EVENT_TYPES)


def ledger_outbox() -> OutboxRepository:
    from app.ledger.models import LEDGER_OUTBOX_MODELS
    return OutboxRepository(LEDGER_OUTBOX_MODELS, plane="ledger",
                            allowed_event_types=LEDGER_EVENT_TYPES)
