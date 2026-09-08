"""Phase C — one configuration resolution path, three scopes.

The load-bearing test in this file is the FIRST one. Everything else describes new
capability; that one asserts the new capability changed nothing. Configuration
resolution feeds the stop loss, the daily-loss halt and the position sizer of a
system trading real money, so "the new resolver agrees with the old one exactly"
is the claim that has to hold before any of the rest matters.
"""
from __future__ import annotations

import json

import pytest

from app.core import scoped_config as sc
from app.core.config import get_settings
from app.core import deployments as _deployments
from app.core.runtime_config import effective, set_override
from app.db.models import LEGACY_DEPLOYMENT_ID, InstrumentState
from app.db.session import SessionLocal, init_db
from tests.legacy_money_scope import LEGACY_SCOPE, LegacyMoneyScope
from tests.admitted_entry import persist_admitted_entry

create_deployment = LegacyMoneyScope(_deployments, "create_deployment").create_deployment
sc = LegacyMoneyScope(sc, "resolve", "explain")
_effective, _set_override = effective, set_override
def effective(*args, **kwargs):
    kwargs.setdefault("owner_id", "owner")
    return _effective(*args, **kwargs)
def set_override(*args, **kwargs):
    kwargs.setdefault("owner_id", "owner")
    return _set_override(*args, **kwargs)


def _create_deployment(session, name, *, params=None, **kwargs):
    admission = persist_admitted_entry(session)
    row = create_deployment(
        session, name, strategy_key=admission["strategy_key"],
        strategy_version=admission["strategy_version"],
        graph_address=admission["graph_address"],
        attribution_state=admission["attribution_state"],
        admission_address=admission["admission_address"], **kwargs)
    if params is not None:
        # The receipt binds the graph identity, while this test exercises the
        # separately persisted deployment-scope overlay.
        row.params_json = json.dumps(params)
    return row


@pytest.fixture(autouse=True)
def _db():
    init_db(reset=True)
    yield


def test_resolve_with_no_scopes_is_identical_to_effective():
    """THE behaviour-preservation assertion. Every engine call site that switches
    from effective() to resolve() must see the same dict — same keys, same values,
    same types."""
    assert sc.resolve() == effective()


def test_resolve_still_matches_effective_when_platform_overrides_exist():
    """The owner's ten live runtime_config rows are platform scope. They must keep
    winning over code defaults exactly as before — CLAUDE.md is explicit that these
    are deliberate operating decisions, not drift to be reconciled away."""
    set_override("max_daily_loss", 2000.0)
    set_override("intraday_max_positions", 4)
    assert sc.resolve() == effective()
    assert sc.resolve()["max_daily_loss"] == 2000.0
    assert sc.resolve()["intraday_max_positions"] == 4


def test_legacy_deployment_scope_changes_nothing():
    """The legacy deployment carries `{}` params, so resolving *through* it must be
    indistinguishable from not resolving through anything."""
    set_override("max_daily_loss", 2000.0)
    with SessionLocal() as s:
        assert sc.resolve(s, deployment_id=LEGACY_DEPLOYMENT_ID,
                          **LEGACY_SCOPE) == effective()


def test_deployment_cannot_override_account_loss():
    with SessionLocal() as s:
        d = _create_deployment(s, "tight-risk", params={"max_daily_loss": 500.0})
        s.commit()
        set_override("max_daily_loss", 2000.0)      # platform says 2000
        assert effective()["max_daily_loss"] == 2000.0
        got = sc.resolve(s, deployment_id=d.id)
        assert got["max_daily_loss"] == 2000.0, "account constraint must remain platform-owned"
        # ...and only that key moves.
        assert got["intraday_stop_loss_pct"] == effective()["intraday_stop_loss_pct"]


def test_instrument_scope_overrides_deployment():
    with SessionLocal() as s:
        d = _create_deployment(s, "d", params={"intraday_stop_loss_pct": 0.02})
        # init_db seeds instrument_state from the universe, so NIFTY already exists —
        # update it rather than inserting a duplicate.
        row = s.get(InstrumentState, ("owner", "NIFTY"))
        assert row is not None, "expected the seeded universe to contain NIFTY"
        row.params_json = json.dumps({"intraday_stop_loss_pct": 0.005})
        s.commit()
        got = sc.resolve(s, deployment_id=d.id, instrument_key="NIFTY", owner_id="owner")
        assert got["intraday_stop_loss_pct"] == 0.005, "instrument is narrowest"


def test_scopes_compose_rather_than_replace():
    """A narrower scope overrides the KEYS IT SETS, not the whole dict. Getting
    this wrong would silently reset every unmentioned risk parameter to its code
    default — which is the failure mode that looks like it works."""
    with SessionLocal() as s:
        set_override("max_daily_loss", 2000.0)
        d = _create_deployment(s, "partial", params={"intraday_target_pct": 0.02})
        s.commit()
        got = sc.resolve(s, deployment_id=d.id)
        assert got["intraday_target_pct"] == 0.02      # from the deployment
        assert got["max_daily_loss"] == 2000.0         # still from the platform


# ── validation: a narrower scope cannot escape the platform's own gate ────────

def test_deployment_cannot_set_a_non_overridable_key():
    with pytest.raises(sc.ScopeRejection, match="not an overridable parameter"):
        sc.validate_override("kite_api_secret", "hunter2")


def test_deployment_cannot_set_an_out_of_bounds_value():
    """Same bounds the platform enforces. An inverted stop is not more acceptable
    because a deployment asked for it."""
    with pytest.raises(sc.ScopeRejection, match="outside the permitted range"):
        sc.validate_override("intraday_stop_loss_pct", 5.0)     # bound is 0.50


def test_scoped_order_mode_normalizes_known_values_and_rejects_unknown_values():
    assert sc.validate_override("entry_order_mode", "market") == "MARKET"
    with pytest.raises(sc.ScopeRejection, match="AUTO, MARKET, LIMIT"):
        sc.validate_override("entry_order_mode", "iceberg")


def test_invalid_scoped_value_is_skipped_not_fatal():
    """This resolution runs inside the signal loop's refresh_params(). One bad row
    must never stop the engine from managing open positions."""
    with SessionLocal() as s:
        d = _create_deployment(s, "bad")
        d.params_json = json.dumps({"intraday_stop_loss_pct": 99.0,   # out of bounds
                                    "intraday_target_pct": 0.02})     # fine
        s.commit()
        got = sc.resolve(s, deployment_id=d.id)
        assert got["intraday_stop_loss_pct"] == effective()["intraday_stop_loss_pct"], \
            "the invalid value must be ignored, falling back to platform scope"
        assert got["intraday_target_pct"] == 0.02, \
            "a valid sibling key must still apply"


def test_corrupt_params_json_degrades_to_inherit_everything():
    with SessionLocal() as s:
        d = _create_deployment(s, "corrupt")
        d.params_json = "{{{not json"
        s.commit()
        assert sc.resolve(s, deployment_id=d.id) == effective()


def test_explain_reports_which_scope_decided_each_value():
    """Three scopes means "why is this stop 0.8%?" stops being obvious, and that
    question gets asked during an incident."""
    with SessionLocal() as s:
        set_override("max_daily_loss", 2000.0)
        d = _create_deployment(s, "x", params={"intraday_target_pct": 0.02})
        s.commit()
        report = sc.explain(s, deployment_id=d.id)
        assert report["intraday_target_pct"]["scope"] == sc.DEPLOYMENT
        assert report["intraday_target_pct"]["value"] == 0.02
        assert report["max_daily_loss"]["scope"] == sc.PLATFORM
        assert report["max_daily_loss"]["value"] == 2000.0
        assert report["intraday_target_pct"]["platform_default"] == \
            getattr(get_settings(), "intraday_target_pct")


@pytest.mark.parametrize("key,value,platform_value", [
    ("max_daily_loss", 0, 2000), ("max_open_drawdown", 1000000, 1000),
    ("max_daily_profit", 0, 1000), ("daily_profit_lock_pct", 0, 0.02),
    ("daily_profit_giveback_frac", 0.01, 0.7),
])
def test_account_constraints_reject_narrow_writes_and_keep_platform_provenance(key, value, platform_value):
    with pytest.raises(sc.ScopeRejection, match="account-wide risk constraint"):
        sc.validate_override(key, value)
    set_override(key, platform_value)
    with SessionLocal() as session:
        deployment = _create_deployment(session, "account-bound", params={key: value})
        row = session.get(InstrumentState, ("owner", "NIFTY"))
        row.params_json = json.dumps({key: value})
        session.commit()
        expected = effective()[key]
        report = sc.explain(session, deployment_id=deployment.id, instrument_key="NIFTY")
        assert report[key]["value"] == expected
        assert report[key]["scope"] == sc.PLATFORM
