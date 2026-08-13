"""Phase B — Deployment as the primary execution object.

Two things are being asserted, and the second matters more than the first:

  1. The deployment lifecycle behaves (create, status, arm, disarm, params).
  2. **Nothing changed.** Introducing deployments must be invisible: the legacy
     book still resolves the same way, every executed row still lands somewhere
     attributable, and no existing call site had to be modified for the database to
     stay consistent. An architectural migration that quietly re-points the money
     record is not a migration, it is an incident.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core import deployments as dep
from app.db.models import (
    LEGACY_BROKER_ACCOUNT_ID,
    LEGACY_DEPLOYMENT_ID,
    LEGACY_OWNER_ID,
    Deployment,
    EquitySnapshot,
    Position,
    GraphArtifact,
    GraphVersion,
    Project,
    SignalEvent,
    Trade,
)
from app.db.session import SessionLocal, init_db
from app.core import strategy_admissions
from app.ir.hashing import canonical_json, content_address
from app.ir.library import REGISTRY
from app.strategy.admission import IRGraphAdmissionInput, admit_strategy
from tests.legacy_money_scope import LegacyMoneyScope

_CACHED_ADMISSION = None

dep = LegacyMoneyScope(
    dep, "ensure_legacy_deployment", "create_deployment", "active_deployments",
    "get_deployment", "get_by_name", "all_deployments", "set_status", "set_armed",
    "disarm_all", "resolve_deployment_strategy", "deployment_strategy_version",
    "deployment_params")


@pytest.fixture(autouse=True)
def _db():
    init_db(reset=True)
    yield


def test_legacy_deployment_exists_after_init():
    with SessionLocal() as s:
        row = s.get(Deployment, LEGACY_DEPLOYMENT_ID)
        assert row is not None, "init_db must seed the legacy deployment"
        assert row.name == dep.LEGACY_NAME
        assert row.status == dep.ACTIVE


def test_legacy_deployment_resolves_exactly_as_before():
    """The legacy row's whole job is to mean "no change". Each NULL/'legacy' here
    is load-bearing: a strategy_key would pin the book to one strategy, an
    allocation would cap capital that is currently uncapped, and universe_mode
    anything but 'legacy' would stop using per-instrument config."""
    with SessionLocal() as s:
        row = s.get(Deployment, LEGACY_DEPLOYMENT_ID)
        assert row.strategy_key is None, "must resolve strategy PER INSTRUMENT"
        assert row.strategy_version is None
        assert row.universe_mode == "legacy"
        assert row.allocation is None, "must mean 'the whole account'"
        assert row.params_json == "{}", "must inherit every platform default"
        assert row.armed is False, "must start disarmed, like the global flag"


def test_ensure_legacy_is_idempotent():
    with SessionLocal() as s:
        dep.ensure_legacy_deployment(s)
        dep.ensure_legacy_deployment(s)
        s.commit()
        assert len(s.scalars(select(Deployment)).all()) == 1


def _create_admitted_deployment(session, name: str, *, status=dep.DRAFT):
    """The one current owner-local IR receipt used by positive new-book tests."""
    from app.ir.strategies.expanding_z import GRAPH as source_document

    project_id = "deployment-tests"
    graph_identifier = "strategy.expanding_z_impulse"
    document = {**source_document, "version": 1}
    if session.get(Project, project_id) is None:
        session.add(Project(project_id=project_id, owner_id=LEGACY_OWNER_ID,
                            name="deployment tests"))
    if session.get(GraphArtifact, (LEGACY_OWNER_ID, graph_identifier)) is None:
        session.add(GraphArtifact(
            owner_id=LEGACY_OWNER_ID, identifier=graph_identifier,
            project_id=project_id, display_name="admitted deployment graph",
            draft_json="{}", draft_revision=0))
    session.flush()
    global _CACHED_ADMISSION
    if _CACHED_ADMISSION is None:
        decision = admit_strategy(
            owner_id=LEGACY_OWNER_ID,
            source_input=IRGraphAdmissionInput(graph=document, parameters={}, risk_model=None),
            registry=REGISTRY)
        assert decision.artifact is not None
        _CACHED_ADMISSION = decision.artifact
    strategy_admissions.put(session, _CACHED_ADMISSION)
    if session.get(GraphVersion, (LEGACY_OWNER_ID, graph_identifier, 1)) is None:
        session.add(GraphVersion(
            owner_id=LEGACY_OWNER_ID, graph_identifier=graph_identifier, version=1,
            artifact_json=canonical_json(document), content_address=content_address(document),
            admission_address=_CACHED_ADMISSION.admission_address))
    session.flush()
    return dep.create_deployment(
        session, name, strategy_key=f"ir.{graph_identifier}",
        admission_address=_CACHED_ADMISSION.admission_address, status=status)


def test_new_deployments_start_as_draft_not_active():
    """A book must be switched on deliberately. Describing one must never start it."""
    with SessionLocal() as s:
        d = _create_admitted_deployment(s, "momentum-2")
        s.commit()
        assert d.status == dep.DRAFT
        assert d.armed is False
        assert [x.id for x in dep.active_deployments(s)] == [LEGACY_DEPLOYMENT_ID]


def test_new_explicit_deployment_without_admission_refuses_before_insert():
    """Hypothesis: omitting a strategy lets a new deployment bypass causal admission."""
    with SessionLocal() as s:
        with pytest.raises(ValueError, match="ADMISSION_REQUIRED"):
            dep.create_deployment(s, "unbound")
        assert dep.get_by_name(s, "unbound") is None


def test_deployment_strategy_write_bypass_mutant_is_killed(monkeypatch):
    """Removing only the deployment receipt check accepts a forged strategy write."""
    with SessionLocal() as s:
        forged = "sha256:" + "f" * 64
        monkeypatch.setattr(
            "app.core.deployments._require_current_deployment_admission",
            lambda *_args, **_kwargs: __import__("types").SimpleNamespace(
                admission_address=forged,
                strategy=__import__("types").SimpleNamespace(version="mutant")))
        with pytest.raises(pytest.fail.Exception):
            with pytest.raises(ValueError, match="RECEIPT_STALE"):
                dep.create_deployment(
                    s, "mutant", strategy_key="ir.strategy.expanding_z_impulse",
                    admission_address=forged)


def test_duplicate_name_is_refused():
    with SessionLocal() as s:
        _create_admitted_deployment(s, "dupe")
        s.commit()
        with pytest.raises(ValueError, match="already exists"):
            _create_admitted_deployment(s, "dupe")


def test_cannot_arm_a_non_active_deployment():
    """'Armed but not running' reads as live on a dashboard and takes nothing."""
    with SessionLocal() as s:
        d = _create_admitted_deployment(s, "draft-book")
        s.commit()
        with pytest.raises(ValueError, match="not 'active'"):
            dep.set_armed(s, d.id, True)


def test_pausing_a_deployment_disarms_it():
    with SessionLocal() as s:
        d = _create_admitted_deployment(s, "live-book", status=dep.ACTIVE)
        dep.set_armed(s, d.id, True)
        s.commit()
        assert d.armed is True
        dep.set_status(s, d.id, dep.PAUSED)
        s.commit()
        assert d.armed is False, "a paused deployment must not stay armed"


def test_legacy_deployment_cannot_be_archived():
    """Every historical row points at it and deployment_id is NOT NULL — archiving
    it would make the entire money record unattributable."""
    with SessionLocal() as s:
        with pytest.raises(ValueError, match="cannot be archived"):
            dep.set_status(s, LEGACY_DEPLOYMENT_ID, dep.ARCHIVED)
        # ...but pausing it, which is what someone actually wants, is allowed.
        dep.set_status(s, LEGACY_DEPLOYMENT_ID, dep.PAUSED)
        s.commit()
        assert s.get(Deployment, LEGACY_DEPLOYMENT_ID).status == dep.PAUSED


def test_disarm_all_matches_the_boot_invariant():
    with SessionLocal() as s:
        d = _create_admitted_deployment(s, "b", status=dep.ACTIVE)
        dep.set_armed(s, d.id, True)
        dep.set_status(s, LEGACY_DEPLOYMENT_ID, dep.ACTIVE)
        dep.set_armed(s, LEGACY_DEPLOYMENT_ID, True)
        s.commit()
        assert dep.disarm_all(s) == 2
        s.commit()
        assert all(not x.armed for x in dep.all_deployments(s))


def test_malformed_params_degrade_to_inherit_everything():
    """A bad row must never take the engine down; it must mean 'no overrides'."""
    with SessionLocal() as s:
        d = _create_admitted_deployment(s, "bad-params")
        d.params_json = "{not json"
        s.commit()
        assert dep.deployment_params(s, d.id) == {}


def test_params_round_trip():
    with SessionLocal() as s:
        d = _create_admitted_deployment(s, "tuned")
        d.params_json = '{"max_daily_loss": 1500.0}'
        s.commit()
        assert dep.deployment_params(s, d.id) == {"max_daily_loss": 1500.0}


# ── the behaviour-preservation half ──────────────────────────────────────────

def test_inserts_that_omit_deployment_id_land_in_the_legacy_book():
    """The server_default is the additive-migration guarantee: a write path that
    knows nothing about deployments still succeeds and is still attributed, rather
    than failing on a NOT NULL. Verified through raw SQL because that is the case
    that would break — the ORM would otherwise supply the Python-side default."""
    from sqlalchemy import text
    from app.db.session import engine
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO signal_events (owner_id, broker_account_id, time, instrument_key, "
            "signal, z, slope, close, acted, note) VALUES "
            f"('{LEGACY_OWNER_ID}', '{LEGACY_BROKER_ACCOUNT_ID}', "
            "'2026-08-02 10:00:00', 'NIFTY', 'LONG_ENTRY', 1.2, 0.3, 100.0, 1, '')"))
        got = conn.execute(text(
            "SELECT deployment_id FROM signal_events")).scalar_one()
    assert got == LEGACY_DEPLOYMENT_ID


@pytest.mark.parametrize("model", [Position, Trade, EquitySnapshot, SignalEvent])
def test_executed_row_tables_carry_a_deployment(model):
    """Every table that records something the system DID must be attributable.
    Reference tables (universe, runtime_config, instrument_state) deliberately are
    not — they describe the platform, not a book."""
    assert hasattr(model, "deployment_id"), \
        f"{model.__name__} records an execution and must carry deployment_id"


# ── Phase D: a deployment's strategy resolves FAIL-CLOSED ────────────────────

def test_a_deployment_with_an_unknown_strategy_raises_rather_than_substituting():
    """Audit finding C4. `get_strategy()` fails OPEN by design — a stale
    per-instrument assignment must not crash a tick. A DEPLOYMENT is a different
    promise: it names which strategy is trading, so an unresolvable key must stop
    it, never quietly hand the customer's capital to the platform default while the
    trade rows claim otherwise."""
    with SessionLocal() as s:
        with pytest.raises(ValueError, match="ADMISSION_REQUIRED"):
            dep.create_deployment(s, "ghost", strategy_key="gen_does_not_exist")
        assert dep.get_by_name(s, "ghost") is None


def test_the_legacy_deployment_pins_no_strategy_and_that_is_not_an_error():
    """None means "not applicable" (resolve per instrument, as before), which must
    stay distinguishable from "not found"."""
    with SessionLocal() as s:
        assert dep.resolve_deployment_strategy(s, LEGACY_DEPLOYMENT_ID) is None
        assert dep.deployment_strategy_version(s, LEGACY_DEPLOYMENT_ID) is None


def test_a_deployment_pinning_a_real_strategy_reports_its_content_hash():
    with SessionLocal() as s:
        d = _create_admitted_deployment(s, "real")
        s.commit()
        assert d.strategy_key == "ir.strategy.expanding_z_impulse"
        assert d.strategy_version
        assert d.admission_address


def test_money_record_tables_can_carry_a_strategy_version():
    """Historical trades must reference the exact strategy version executed."""
    assert hasattr(Position, "strategy_version")
    assert hasattr(Trade, "strategy_version")


def test_engine_arm_mirrors_onto_the_deployment_row():
    """Phase B runtime state. The in-memory flag stays the master switch — the row
    is a durable record of what it says, never a second gate that could disagree."""
    from app.engine.runner import EngineRunner
    r = EngineRunner(owner_id="owner", broker_account_id="account.default")
    with SessionLocal() as s:
        assert s.get(Deployment, LEGACY_DEPLOYMENT_ID).armed is False, \
            "a fresh process must start disarmed, persisted state included"
    r.arm(True)
    with SessionLocal() as s:
        assert s.get(Deployment, LEGACY_DEPLOYMENT_ID).armed is True
    r.arm(False)
    with SessionLocal() as s:
        assert s.get(Deployment, LEGACY_DEPLOYMENT_ID).armed is False
    r.broker.close()


def test_a_disarm_still_succeeds_when_the_row_cannot_be_written(monkeypatch):
    """Disarming must NEVER be blocked by a database problem. Not being able to
    stop taking new entries is the failure mode that matters here."""
    from app.core import deployments as dep_mod
    from app.engine.runner import EngineRunner
    r = EngineRunner(owner_id="owner", broker_account_id="account.default")
    r.arm(True)
    monkeypatch.setattr(dep_mod, "set_armed",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("db down")))
    assert r.arm(False) is False, "the engine's own flag must be disarmed regardless"
    assert r.armed is False
    r.broker.close()
