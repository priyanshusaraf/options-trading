"""Approve→Deploy bridge: an approved research candidate becomes a deployment.

Deploying creates (or reuses) the target watchlist, assigns the instruments that clear
conflict resolution (incumbents in OTHER watchlists are left alone), and records the
strategy in the archive as `running`. `preview_deploy` shows exactly what would happen
without writing anything — the owner sees accepted/blocked before confirming. The bridge
writes declarative config only; it never touches positions or capital.
"""
import pytest

from app.core import strategy_admissions
from app.core import strategy_archive as arch
from app.core import watchlists as wl
from app.core.deploy_bridge import DeployRequest, deploy, preview_deploy
from app.db.models import Deployment, GraphArtifact, GraphVersion, Project, Watchlist
from app.db.session import SessionLocal, init_db
from app.ir.hashing import canonical_json, content_address
from app.ir.library import REGISTRY
from app.strategy.admission import IRGraphAdmissionInput, admit_strategy
from tests.legacy_money_scope import LegacyUserScope

_CACHED_ADMISSION = None

arch = LegacyUserScope(arch, "get", "record_strategy", "set_status", "by_status", "list_archive")
wl = LegacyUserScope(wl, "create_watchlist", "get_watchlist", "assign_instrument",
                     "unassign_instrument", "watchlist_of", "effective_strategy_map",
                     "membership_map", "in_watchlist_keys", "write_research_snapshot",
                     "list_watchlists", "apply_resolution")

_deploy, _preview_deploy = deploy, preview_deploy
def deploy(*args, **kwargs):
    kwargs.setdefault("owner_id", "owner")
    return _deploy(*args, **kwargs)
def preview_deploy(*args, **kwargs):
    kwargs.setdefault("owner_id", "owner")
    return _preview_deploy(*args, **kwargs)


def _fresh():
    init_db(reset=True)


GRAPH = "strategy.expanding_z_impulse"
PROJECT = "deploy-bridge"
ACCOUNT = "account.default"


def _admitted_request(session, name: str, proposals, *, account_id: str = ACCOUNT):
    """Build a real owner-local IR receipt rather than a plausible address string."""
    from app.ir.strategies.expanding_z import GRAPH as source_document

    document = {**source_document, "version": 1}

    if session.get(Project, PROJECT) is None:
        session.add(Project(project_id=PROJECT, owner_id="owner", name="deploy bridge"))
    if session.get(GraphArtifact, ("owner", GRAPH)) is None:
        session.add(GraphArtifact(
            owner_id="owner", identifier=GRAPH, project_id=PROJECT,
            display_name="deploy graph", draft_json="{}", draft_revision=0))
    session.flush()
    global _CACHED_ADMISSION
    if _CACHED_ADMISSION is None:
        decision = admit_strategy(
            owner_id="owner",
            source_input=IRGraphAdmissionInput(graph=document, parameters={}, risk_model=None),
            registry=REGISTRY,
        )
        assert decision.artifact is not None
        _CACHED_ADMISSION = decision.artifact
    strategy_admissions.put(session, _CACHED_ADMISSION)
    if session.get(GraphVersion, ("owner", GRAPH, document["version"])) is None:
        session.add(GraphVersion(
            owner_id="owner", graph_identifier=GRAPH, version=document["version"],
            artifact_json=canonical_json(document), content_address=content_address(document),
            admission_address=_CACHED_ADMISSION.admission_address))
    session.flush()
    return DeployRequest(
        watchlist_name=name, strategy_key=f"ir.{GRAPH}", proposals=proposals,
        admission_address=_CACHED_ADMISSION.admission_address,
        broker_account_id=account_id, source="ir")


def test_deploy_creates_watchlist_assigns_and_archives_running(monkeypatch):
    _fresh()
    with SessionLocal() as s:
        monkeypatch.setattr("app.core.execution_binding.assert_may_execute",
                            lambda *_args, **_kwargs: None)
        req = _admitted_request(
            s, "Bullion Trend", [("GOLDM", 0.8), ("SILVERM", 0.7)])
        res = deploy(s, req)
        s.commit()
        assert set(res.assigned) == {"GOLDM", "SILVERM"}
        assert wl.watchlist_of(s, "GOLDM").name == "Bullion Trend"
        rec = arch.get(s, req.strategy_key)
        assert rec.status == "running" and rec.deployed_watchlist_id == res.watchlist_id
        deployment = s.get(Deployment, res.deployment_id)
        assert deployment is not None
        assert deployment.admission_address == req.admission_address
        assert deployment.strategy_key == req.strategy_key
        assert deployment.broker_account_id == ACCOUNT


def test_deploy_bridge_refuses_a_missing_admission_address():
    """Hypothesis: watchlist selection can grant new strategy authority by itself."""
    _fresh()
    with SessionLocal() as s:
        req = DeployRequest(
            "admissionless", f"ir.{GRAPH}", [("GOLDM", 0.8)],
            admission_address=None, broker_account_id=ACCOUNT)  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="ADMISSION_REQUIRED"):
            deploy(s, req)
        assert wl.get_watchlist(s, "admissionless") is None
        assert list(s.query(Deployment).filter(Deployment.name == "watchlist:1")) == []


def test_deploy_bridge_refuses_a_forged_receipt_before_writes():
    """Hypothesis: a syntactically valid address can create deployment authority."""
    _fresh()
    with SessionLocal() as s:
        req = _admitted_request(s, "forged", [("GOLDM", 0.8)])
        req.admission_address = "sha256:" + "f" * 64
        with pytest.raises(ValueError, match="RECEIPT_STALE"):
            deploy(s, req)
        assert wl.get_watchlist(s, "forged") is None
        assert not list(s.query(Deployment).filter(Deployment.name.like("watchlist:%")))


def test_deploy_bridge_receipt_check_bypass_mutant_is_killed(monkeypatch):
    """Removing only the bridge receipt check lets a forged request reach writes."""
    _fresh()
    with SessionLocal() as s:
        req = _admitted_request(s, "bridge-mutant", [("GOLDM", 0.8)])
        req.admission_address = "sha256:" + "f" * 64
        monkeypatch.setattr("app.core.execution_binding.assert_may_execute",
                            lambda *_args, **_kwargs: None)
        monkeypatch.setattr(
            "app.core.deployments._require_current_deployment_admission",
            lambda *_args, **_kwargs: __import__("types").SimpleNamespace(
                admission_address=req.admission_address,
                strategy=__import__("types").SimpleNamespace(version="mutant")))
        with pytest.raises(pytest.fail.Exception):
            with pytest.raises(ValueError, match="RECEIPT_STALE"):
                deploy(s, req)


def test_deploy_bridge_refuses_a_foreign_account_before_writes():
    """Hypothesis: an owner can silently redirect an admitted deployment to another account."""
    _fresh()
    with SessionLocal() as s:
        req = _admitted_request(s, "wrong-account", [("GOLDM", 0.8)],
                                account_id="account.foreign")
        with pytest.raises(ValueError, match="ADMISSION_REQUIRED"):
            deploy(s, req)
        assert wl.get_watchlist(s, "wrong-account") is None
        assert not list(s.query(Deployment).filter(Deployment.name.like("watchlist:%")))


def test_portfolio_route_forwards_the_composed_principal_owner(monkeypatch):
    from app.api import portfolio_routes
    from app.api.principal import Principal

    seen = []
    monkeypatch.setattr(portfolio_routes, "owner_id_for", lambda _principal: "owner.route")
    monkeypatch.setattr(
        portfolio_routes, "preview_deploy",
        lambda _session, req, *, owner_id: (
            seen.append(owner_id) or __import__("types").SimpleNamespace(
                watchlist_name=req.watchlist_name, strategy_key=req.strategy_key,
                accepted=[], rejected=[])))
    body = portfolio_routes.DeployIn(
        watchlist_name="route", strategy_key=f"ir.{GRAPH}", proposals=[], dry_run=True,
        admission_address="sha256:" + "a" * 64, broker_account_id=ACCOUNT)
    principal = Principal(id="caller", kind="owner", scopes=frozenset({"*"}))

    assert portfolio_routes.portfolio_deploy(body, principal)["dry_run"] is True
    assert seen == ["owner.route"]


def test_deploy_blocks_incumbents_in_other_watchlists():
    _fresh()
    with SessionLocal() as s:
        a = wl.create_watchlist(s, "A", "expanding_z_v4")
        s.commit()
        wl.assign_instrument(s, "SILVERM", a.id)          # SILVERM already earning in A
        s.commit()
        req = _admitted_request(s, "B", [("SILVERM", 0.9), ("GOLDM", 0.5)])
        res = deploy(s, req)
        s.commit()
        assert res.assigned == ["GOLDM"]
        assert any(r["instrument"] == "SILVERM" and r["reason"] == "incumbent"
                   for r in res.rejected)
        assert wl.watchlist_of(s, "SILVERM").name == "A"   # incumbent untouched


def test_preview_writes_nothing():
    _fresh()
    with SessionLocal() as s:
        req = DeployRequest(
            "Bullion", f"ir.{GRAPH}", [("GOLDM", 0.8)],
            admission_address="sha256:" + "a" * 64, broker_account_id=ACCOUNT)
        prev = preview_deploy(s, req)
        assert prev.accepted == ["GOLDM"]
        assert wl.get_watchlist(s, "Bullion") is None      # nothing created
        assert wl.watchlist_of(s, "GOLDM") is None
        assert arch.get(s, "trend_impulse_v3") is None


def test_deploy_is_idempotent():
    _fresh()
    with SessionLocal() as s:
        req = _admitted_request(s, "Bullion", [("GOLDM", 0.8)])
        r1 = deploy(s, req)
        s.commit()
        r2 = deploy(s, req)
        s.commit()
        assert r1.watchlist_id == r2.watchlist_id
        assert s.query(Watchlist).filter_by(name="Bullion").count() == 1
        assert wl.watchlist_of(s, "GOLDM").id == r1.watchlist_id
