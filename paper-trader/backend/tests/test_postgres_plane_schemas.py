"""Live PostgreSQL current-schema contracts for research and ledger planes."""
from __future__ import annotations

import os
import datetime as dt
import threading
import uuid

import pytest
import sqlalchemy as sa

from app.ledger.db import LedgerBase, init_ledger_db, make_engine as make_ledger_engine
from app.ledger import db as ledger_db
from app.ledger import service as ledger_service
from app.ledger.models import LedgerManualFill
from research.domain.base import ResearchBase, init_research_db, make_engine as make_research_engine
from research.domain import migrate as research_migrate
from research.domain.models import (ExperimentRun, ExperimentSpec, Hypothesis,
                                    OptimizationTrial, ResearchProgram)
from research.domain.operations import ResearchOperationRepository

# Register both independent metadata collections.
from app.ledger import models as _ledger_models  # noqa: F401,E402
from research.domain import models as _research_models  # noqa: F401,E402


def _schema_url(base_url: str, schema: str) -> str:
    return str(sa.engine.make_url(base_url).update_query_dict(
        {"options": f"-csearch_path={schema}"}
    ))


@pytest.fixture(params=("research", "ledger"))
def postgres_plane(request):
    base_url = os.environ.get("PT_TEST_POSTGRES_URL")
    if not base_url:
        pytest.skip("PT_TEST_POSTGRES_URL is not configured")
    schema = f"task3_{request.param}_{uuid.uuid4().hex}"
    admin = sa.create_engine(base_url, future=True)
    with admin.begin() as connection:
        connection.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    url = _schema_url(base_url, schema)
    engine = (make_research_engine(url) if request.param == "research"
              else make_ledger_engine(url))
    try:
        yield request.param, schema, engine
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def test_postgresql_research_metadata_installs_native_immutable_triggers():
    statements = []
    engine = sa.create_mock_engine(
        "postgresql+psycopg://app@db/research",
        lambda statement, *_args, **_kwargs: statements.append(
            str(statement.compile(dialect=engine.dialect))),
    )

    ResearchBase.metadata.create_all(engine)
    ddl = "\n".join(statements)

    for table in ("research_experiment_spec", "research_optimization_trial"):
        assert f"CREATE OR REPLACE FUNCTION {table}_refuse_mutation()" in ddl
        assert f"BEFORE UPDATE OR DELETE ON {table}" in ddl
    assert "RAISE(ABORT" not in ddl


def test_fresh_postgresql_plane_creates_validates_stamps_and_restarts(postgres_plane):
    plane, _schema, engine = postgres_plane
    init = init_research_db if plane == "research" else init_ledger_db
    metadata = ResearchBase.metadata if plane == "research" else LedgerBase.metadata
    marker = (research_migrate.VERSION_TABLE if plane == "research"
              else ledger_db.VERSION_TABLE)
    head = research_migrate.HEAD_VERSION if plane == "research" else ledger_db.HEAD_VERSION

    init(engine)
    assert set(sa.inspect(engine).get_table_names()) == set(metadata.tables) | {marker}
    with engine.connect() as connection:
        assert connection.execute(sa.text(
            f'SELECT version FROM "{marker}"'
        )).scalar_one() == head
    init(engine)


def test_populated_unmanaged_postgresql_plane_refuses_without_mutation(postgres_plane):
    plane, _schema, engine = postgres_plane
    init = init_research_db if plane == "research" else init_ledger_db
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE foreign_payload (id INTEGER PRIMARY KEY, value TEXT)"))
        connection.execute(sa.text("INSERT INTO foreign_payload VALUES (1, 'preserve-me')"))

    with pytest.raises(RuntimeError, match="populated unmanaged PostgreSQL"):
        init(engine)

    with engine.connect() as connection:
        assert connection.execute(sa.text(
            "SELECT value FROM foreign_payload WHERE id=1"
        )).scalar_one() == "preserve-me"
    assert set(sa.inspect(engine).get_table_names()) == {"foreign_payload"}


def test_wrong_version_postgresql_plane_refuses_without_row_loss(postgres_plane):
    plane, _schema, engine = postgres_plane
    init = init_research_db if plane == "research" else init_ledger_db
    marker = (research_migrate.VERSION_TABLE if plane == "research"
              else ledger_db.VERSION_TABLE)
    init(engine)
    with engine.begin() as connection:
        connection.execute(sa.text(f'UPDATE "{marker}" SET version=\'wrong\''))

    with pytest.raises(RuntimeError, match="wrong|unsupported|head"):
        init(engine)

    with engine.connect() as connection:
        assert connection.execute(sa.text(
            f'SELECT version FROM "{marker}"'
        )).scalar_one() == "wrong"


def test_same_name_relaxed_check_is_refused(postgres_plane):
    plane, _schema, engine = postgres_plane
    init = init_research_db if plane == "research" else init_ledger_db
    init(engine)
    if plane == "research":
        table = "research_operation_item"
        constraint = "ck_research_operation_item_status"
    else:
        table = "ledger_snapshot"
        constraint = "ck_ledger_snapshot_single_row"
    with engine.begin() as connection:
        connection.execute(sa.text(
            f'ALTER TABLE "{table}" DROP CONSTRAINT "{constraint}"'
        ))
        connection.execute(sa.text(
            f'ALTER TABLE "{table}" ADD CONSTRAINT "{constraint}" CHECK (TRUE)'
        ))

    with pytest.raises(RuntimeError, match="check|schema|drift"):
        init(engine)


@pytest.mark.parametrize("relaxed_expression", (
    "id = 1 OR TRUE",
    "CASE WHEN id = 1 THEN TRUE ELSE TRUE END",
))
def test_ledger_snapshot_check_cannot_be_semantically_weakened(
    postgres_plane, relaxed_expression,
):
    plane, _schema, engine = postgres_plane
    if plane != "ledger":
        pytest.skip("ledger plane only")
    init_ledger_db(engine)
    with engine.begin() as connection:
        connection.execute(sa.text(
            'ALTER TABLE ledger_snapshot '
            'DROP CONSTRAINT ck_ledger_snapshot_single_row'
        ))
        connection.execute(sa.text(
            'ALTER TABLE ledger_snapshot ADD CONSTRAINT '
            f'ck_ledger_snapshot_single_row CHECK ({relaxed_expression})'
        ))

    with pytest.raises(RuntimeError, match="check|schema|drift"):
        init_ledger_db(engine)


def test_research_state_check_cannot_be_replaced_by_case_passthrough(postgres_plane):
    plane, _schema, engine = postgres_plane
    if plane != "research":
        pytest.skip("research plane only")
    init_research_db(engine)
    with engine.begin() as connection:
        connection.execute(sa.text(
            'ALTER TABLE research_operation_item '
            'DROP CONSTRAINT ck_research_operation_item_status'
        ))
        connection.execute(sa.text(
            'ALTER TABLE research_operation_item ADD CONSTRAINT '
            'ck_research_operation_item_status CHECK '
            "(CASE WHEN status IN ('pending', 'running', 'completed') "
            'THEN TRUE ELSE TRUE END)'
        ))

    with pytest.raises(RuntimeError, match="check|schema|drift"):
        init_research_db(engine)


def test_missing_research_immutable_trigger_is_refused(postgres_plane):
    plane, _schema, engine = postgres_plane
    if plane != "research":
        pytest.skip("research plane only")
    init_research_db(engine)
    with engine.begin() as connection:
        connection.execute(sa.text(
            "DROP TRIGGER research_experiment_spec_refuse_mutation "
            "ON research_experiment_spec"
        ))

    with pytest.raises(RuntimeError, match="immutable-trigger"):
        init_research_db(engine)


@pytest.mark.parametrize("tamper", ("pass_through", "disabled", "mislinked"))
def test_research_immutable_trigger_catalog_contract_is_validated(postgres_plane, tamper):
    plane, _schema, engine = postgres_plane
    if plane != "research":
        pytest.skip("research plane only")
    init_research_db(engine)
    function = "research_experiment_spec_refuse_mutation"
    with engine.begin() as connection:
        if tamper == "pass_through":
            connection.execute(sa.text(
                f"CREATE OR REPLACE FUNCTION {function}() RETURNS trigger AS $$ "
                "BEGIN RETURN NEW; END; $$ LANGUAGE plpgsql"
            ))
        elif tamper == "disabled":
            connection.execute(sa.text(
                f"ALTER TABLE research_experiment_spec DISABLE TRIGGER {function}"
            ))
        else:
            connection.execute(sa.text(
                "CREATE FUNCTION research_experiment_spec_passthrough() "
                "RETURNS trigger AS $$ BEGIN RETURN NEW; END; $$ LANGUAGE plpgsql"
            ))
            connection.execute(sa.text(
                f"DROP TRIGGER {function} ON research_experiment_spec"
            ))
            connection.execute(sa.text(
                f"CREATE TRIGGER {function} BEFORE UPDATE OR DELETE "
                "ON research_experiment_spec FOR EACH ROW "
                "EXECUTE FUNCTION research_experiment_spec_passthrough()"
            ))

    with pytest.raises(RuntimeError, match="immutable-trigger"):
        init_research_db(engine)


def test_research_immutable_trigger_when_false_is_refused(postgres_plane):
    plane, _schema, engine = postgres_plane
    if plane != "research":
        pytest.skip("research plane only")
    init_research_db(engine)
    function = "research_experiment_spec_refuse_mutation"
    with engine.begin() as connection:
        connection.execute(sa.text(
            f"DROP TRIGGER {function} ON research_experiment_spec"
        ))
        connection.execute(sa.text(
            f"CREATE TRIGGER {function} BEFORE UPDATE OR DELETE "
            "ON research_experiment_spec FOR EACH ROW WHEN (FALSE) "
            f"EXECUTE FUNCTION {function}()"
        ))

    sessions = sa.orm.sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with sessions() as session, session.begin():
        program = ResearchProgram(owner_id="when-owner", name="when-program", thesis="test")
        session.add(program)
        session.flush()
        hypothesis = Hypothesis(
            owner_id="when-owner", program_id=program.id, statement="when-hypothesis",
        )
        session.add(hypothesis)
        session.flush()
        session.add(ExperimentSpec(
            owner_id="when-owner", id="when-spec", hypothesis_id=hypothesis.id,
        ))

    with engine.begin() as connection:
        changed = connection.execute(sa.text(
            "UPDATE research_experiment_spec SET recipe_json='tampered' "
            "WHERE owner_id='when-owner' AND id='when-spec'"
        ))
        assert changed.rowcount == 1

    with pytest.raises(RuntimeError, match="immutable-trigger"):
        init_research_db(engine)


def test_research_immutable_facts_refuse_update_and_delete(postgres_plane):
    plane, _schema, engine = postgres_plane
    if plane != "research":
        pytest.skip("research plane only")
    init_research_db(engine)
    sessions = sa.orm.sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with sessions() as session, session.begin():
        program = ResearchProgram(owner_id="owner-a", name="program", thesis="test")
        session.add(program)
        session.flush()
        hypothesis = Hypothesis(
            owner_id="owner-a", program_id=program.id, statement="hypothesis",
        )
        session.add(hypothesis)
        session.flush()
        spec = ExperimentSpec(
            owner_id="owner-a", id="same-local-id", hypothesis_id=hypothesis.id,
        )
        session.add(spec)
        session.flush()
        run = ExperimentRun(owner_id="owner-a", spec_id=spec.id)
        session.add(run)
        session.flush()
        trial = OptimizationTrial(
            owner_id="owner-a", run_id=run.id, instrument_key="NSE:TEST",
            fold_index=0,
        )
        session.add(trial)
        session.flush()
        trial_id = trial.id

    mutations = (
        "UPDATE research_experiment_spec SET recipe_json='{}' "
        "WHERE owner_id='owner-a' AND id='same-local-id'",
        f"DELETE FROM research_optimization_trial WHERE id={trial_id}",
    )
    for statement in mutations:
        with pytest.raises(sa.exc.DBAPIError, match="immutable"):
            with engine.begin() as connection:
                connection.execute(sa.text(statement))


def _race(call):
    barrier = threading.Barrier(2)
    outcomes = []

    def invoke(label):
        try:
            barrier.wait(timeout=5)
            outcomes.append(("ok", call(label)))
        except Exception as exc:  # outcome is the concurrency contract
            outcomes.append(("error", exc))

    threads = [threading.Thread(target=invoke, args=(label,)) for label in ("a", "b")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)
    assert all(not thread.is_alive() for thread in threads)
    return outcomes


def test_research_owner_isolation_and_claim_race_on_plane_url(postgres_plane):
    plane, _schema, engine = postgres_plane
    if plane != "research":
        pytest.skip("research plane only")
    init_research_db(engine)
    sessions = sa.orm.sessionmaker(bind=engine, expire_on_commit=False, future=True)
    now = dt.datetime(2026, 8, 12, 12)
    for owner, trigger in (("owner-a", "manual"), ("owner-b", "nightly")):
        with sessions() as session:
            ResearchOperationRepository(session).enqueue(
                owner_id=owner, trigger=trigger, plan={}, build="test",
                provider_mode="mock", operation_id="same-local-id", now=now,
            )
    with sessions() as session:
        repository = ResearchOperationRepository(session)
        assert repository.get("same-local-id", owner_id="owner-a").trigger == "manual"
        assert repository.get("same-local-id", owner_id="owner-b").trigger == "nightly"
        assert repository.get("same-local-id", owner_id="foreign") is None
        assert repository.get("absent", owner_id="owner-a") is None

    def claim(label):
        with sessions() as session:
            row = ResearchOperationRepository(session).claim_operation(
                "same-local-id", owner_id="owner-a", worker_id=label,
                now=now, lease_seconds=30,
            )
            return None if row is None else row.claim_token

    outcomes = _race(claim)
    tokens = [value for kind, value in outcomes if kind == "ok" and value is not None]
    assert len(tokens) == 1
    assert not [value for kind, value in outcomes if kind == "error"]
    with sessions() as session:
        assert ResearchOperationRepository(session).request_cancel(
            "same-local-id", owner_id="owner-a", now=now + dt.timedelta(seconds=1),
        )
    with sessions() as session:
        assert not ResearchOperationRepository(session).transition(
            "same-local-id", owner_id="owner-a", token=tokens[0],
            stage="planning", now=now + dt.timedelta(seconds=2),
        )

    with sessions() as session:
        repository = ResearchOperationRepository(session)
        repository.enqueue(
            owner_id="owner-a", trigger="manual", plan={}, build="test",
            provider_mode="mock", operation_id="takeover", now=now,
        )
        old = repository.claim_operation(
            "takeover", owner_id="owner-a", worker_id="old", now=now,
            lease_seconds=1,
        )
    assert old is not None

    def takeover(label):
        with sessions() as session:
            row = ResearchOperationRepository(session).claim_operation(
                "takeover", owner_id="owner-a", worker_id=label,
                now=now + dt.timedelta(seconds=2), lease_seconds=30,
            )
            return None if row is None else row.claim_token

    takeover_outcomes = _race(takeover)
    takeover_tokens = [
        value for kind, value in takeover_outcomes if kind == "ok" and value is not None
    ]
    assert len(takeover_tokens) == 1 and takeover_tokens[0] != old.claim_token
    with sessions() as session:
        assert not ResearchOperationRepository(session).transition(
            "takeover", owner_id="owner-a", token=old.claim_token,
            stage="planning", now=now + dt.timedelta(seconds=3),
        )


def test_ledger_owner_account_isolation_and_snapshot_race_on_plane_url(postgres_plane):
    plane, _schema, engine = postgres_plane
    if plane != "ledger":
        pytest.skip("ledger plane only")
    init_ledger_db(engine)
    sessions = sa.orm.sessionmaker(bind=engine, expire_on_commit=False, future=True)
    assert ledger_service.write_snapshot(
        sessions, "owner-a-payload", None,
        owner_id="owner-a", broker_account_id="account",
    ) == 1
    assert ledger_service.write_snapshot(
        sessions, "owner-b-payload", None,
        owner_id="owner-b", broker_account_id="account",
    ) == 1
    assert ledger_service.read_snapshot(
        sessions, owner_id="owner-a", broker_account_id="account",
    ) == (1, "owner-a-payload")
    assert ledger_service.read_snapshot(
        sessions, owner_id="owner-a", broker_account_id="foreign",
    ) is None
    assert ledger_service.read_snapshot(
        sessions, owner_id="foreign", broker_account_id="account",
    ) is None

    def first_write(label):
        return ledger_service.write_snapshot(
            sessions, label, None, owner_id="race-owner", broker_account_id="race-account",
        )

    outcomes = _race(first_write)
    assert sum(kind == "ok" and value == 1 for kind, value in outcomes) == 1
    errors = [value for kind, value in outcomes if kind == "error"]
    assert len(errors) == 1 and isinstance(errors[0], ledger_service.VersionConflict)

    def update_snapshot(label):
        return ledger_service.write_snapshot(
            sessions, f"updated-{label}", 1,
            owner_id="owner-a", broker_account_id="account",
        )

    update_outcomes = _race(update_snapshot)
    assert sum(kind == "ok" and value == 2 for kind, value in update_outcomes) == 1
    update_errors = [value for kind, value in update_outcomes if kind == "error"]
    assert len(update_errors) == 1
    assert isinstance(update_errors[0], ledger_service.VersionConflict)


def test_ledger_manual_fill_claim_race_on_plane_url(postgres_plane):
    plane, _schema, engine = postgres_plane
    if plane != "ledger":
        pytest.skip("ledger plane only")
    init_ledger_db(engine)
    sessions = sa.orm.sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with sessions() as session, session.begin():
        session.add(LedgerManualFill(
            owner_id="owner-a", broker_account_id="account-a", order_id="order-1",
            tradingsymbol="TEST", exchange="NSE", product="CNC", side="BUY",
            qty=1, avg_price=10.0, verdict="manual", raw="{}", seen_at=dt.datetime.now(),
        ))

    def claim(label):
        return ledger_service.claim_manual_fill(
            sessions, "order-1", f"trade-{label}", owner_id="owner-a",
            broker_account_id="account-a", trade_exists=lambda *_args: True,
        )

    outcomes = _race(claim)
    assert sum(kind == "ok" and value is True for kind, value in outcomes) == 1
    errors = [value for kind, value in outcomes if kind == "error"]
    assert len(errors) == 1 and isinstance(errors[0], ledger_service.AlreadyClaimed)
