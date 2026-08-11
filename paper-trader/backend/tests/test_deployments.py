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
    SignalEvent,
    Trade,
)
from app.db.session import SessionLocal, init_db
from tests.legacy_money_scope import LegacyMoneyScope

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


def test_new_deployments_start_as_draft_not_active():
    """A book must be switched on deliberately. Describing one must never start it."""
    with SessionLocal() as s:
        d = dep.create_deployment(s, "momentum-2", strategy_key="expanding_z_v4")
        s.commit()
        assert d.status == dep.DRAFT
        assert d.armed is False
        assert [x.id for x in dep.active_deployments(s)] == [LEGACY_DEPLOYMENT_ID]


def test_duplicate_name_is_refused():
    with SessionLocal() as s:
        dep.create_deployment(s, "dupe")
        s.commit()
        with pytest.raises(ValueError, match="already exists"):
            dep.create_deployment(s, "dupe")


def test_cannot_arm_a_non_active_deployment():
    """'Armed but not running' reads as live on a dashboard and takes nothing."""
    with SessionLocal() as s:
        d = dep.create_deployment(s, "draft-book")
        s.commit()
        with pytest.raises(ValueError, match="not 'active'"):
            dep.set_armed(s, d.id, True)


def test_pausing_a_deployment_disarms_it():
    with SessionLocal() as s:
        d = dep.create_deployment(s, "live-book", status=dep.ACTIVE)
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
        d = dep.create_deployment(s, "b", status=dep.ACTIVE)
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
        d = dep.create_deployment(s, "bad-params")
        d.params_json = "{not json"
        s.commit()
        assert dep.deployment_params(s, d.id) == {}


def test_params_round_trip():
    with SessionLocal() as s:
        d = dep.create_deployment(s, "tuned", params={"max_daily_loss": 1500.0})
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
    from app.strategy.registry import StrategyNotFound
    with SessionLocal() as s:
        d = dep.create_deployment(s, "ghost", strategy_key="gen_does_not_exist")
        s.commit()
        with pytest.raises(StrategyNotFound):
            dep.resolve_deployment_strategy(s, d.id)
        with pytest.raises(StrategyNotFound):
            dep.deployment_strategy_version(s, d.id)


def test_the_legacy_deployment_pins_no_strategy_and_that_is_not_an_error():
    """None means "not applicable" (resolve per instrument, as before), which must
    stay distinguishable from "not found"."""
    with SessionLocal() as s:
        assert dep.resolve_deployment_strategy(s, LEGACY_DEPLOYMENT_ID) is None
        assert dep.deployment_strategy_version(s, LEGACY_DEPLOYMENT_ID) is None


def test_a_deployment_pinning_a_real_strategy_reports_its_content_hash():
    with SessionLocal() as s:
        d = dep.create_deployment(s, "real", strategy_key="trend_impulse_v3")
        s.commit()
        strat = dep.resolve_deployment_strategy(s, d.id)
        assert strat is not None and strat.key == "trend_impulse_v3"
        version = dep.deployment_strategy_version(s, d.id)
        assert version and version == strat.version


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
