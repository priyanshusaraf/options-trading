"""Transaction, retry, cache, worker, and concurrency adversarial rows."""
from __future__ import annotations

import sqlite3

import pytest
import sqlalchemy as sa
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.strategy_admissions import put
from app.db.models import Base, IrV2GraphVersion, StrategyAdmission
from research.domain.admissions import store_admission
from research.domain.base import ResearchBase
from research.domain.models import ResearchIrV2GraphVersion, ResearchStrategyAdmission
from tests.phase4_adversarial_support import run_current_nodes
from tests.test_phase4_v2_graph_persistence import _phase4_fixture


def test_adv_002_every_named_transaction_boundary_is_atomic() -> None:
    """Facts, dependency links, datasets, assessments, and outbox roll back."""
    transcript = run_current_nodes((
        "tests/test_phase4_canonical_market_identity.py::"
        "test_authority_chain_atomic_failure_rolls_back_all_facts",
        "tests/test_phase4_dataset_assessment_authority.py::"
        "test_atomic_failure_exposes_no_manifest",
        "tests/test_phase4_v2_graph_persistence.py::"
        "test_execution_graph_and_receipt_have_no_partial_write_on_receipt_failure",
        "tests/test_outbox_contract.py::"
        "test_state_and_event_commit_or_rollback_together",
    ))
    assert transcript.count(" PASSED") >= 4


@pytest.mark.parametrize("plane", ("execution", "research"))
def test_adv_003_commit_failure_leaves_no_graph_or_receipt_orphan(plane: str) -> None:
    """A driver-level commit refusal exposes neither half of a plane-local pair."""
    _registry, wrapper = _phase4_fixture()
    fail_commit = {"armed": False}

    class CommitRefusingConnection:
        def __init__(self) -> None:
            self._connection = sqlite3.connect(":memory:")

        def __getattr__(self, name: str):
            return getattr(self._connection, name)

        def commit(self) -> None:
            if fail_commit["armed"]:
                raise sqlite3.OperationalError(f"injected {plane} commit failure")
            self._connection.commit()

    engine = sa.create_engine(
        "sqlite://", creator=CommitRefusingConnection, poolclass=StaticPool, future=True)
    model_base = Base if plane == "execution" else ResearchBase
    graph_model = IrV2GraphVersion if plane == "execution" else ResearchIrV2GraphVersion
    receipt_model = StrategyAdmission if plane == "execution" else ResearchStrategyAdmission
    persist = put if plane == "execution" else store_admission
    model_base.metadata.create_all(engine)

    with Session(engine) as writer:
        persist(writer, wrapper)
        fail_commit["armed"] = True
        with pytest.raises(sa.exc.OperationalError, match=f"injected {plane} commit failure"):
            writer.commit()
        fail_commit["armed"] = False
        writer.rollback()

    with Session(engine) as reader:
        residual = (
            reader.scalar(select(func.count()).select_from(graph_model)),
            reader.scalar(select(func.count()).select_from(receipt_model)),
        )
        assert residual == (0, 0), f"{plane} graph/receipt residual after failed commit: {residual}"
    engine.dispose()
