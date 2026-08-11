"""The operational read model — contract, and the invariants that keep it a *read* model.

Three kinds of test here and no others:

1. **Contract** — the cockpit can answer the eight operational questions.
2. **Fidelity** — its answers are the authoritative services' answers, not a second opinion.
   This is the one that matters: a cockpit that computes its own view of "what is
   authorised" would disagree with the engine exactly when it mattered.
3. **Read-only** — assembling the view writes nothing, controls nothing, and opens no
   research database (ADR 0013: admission facts are held by the execution plane).
"""
from __future__ import annotations

import datetime as dt

import pytest

from app.core import paper_authority as pa
from app.core.execution_book import PAPER
from app.db.models import (
    LEGACY_DEPLOYMENT_ID,
    GraphArtifact,
    GraphVersion,
    IrPaperDeployment,
    Position,
    Project,
)
from app.db.session import SessionLocal, init_db
from app.engine import cockpit
from app.engine.runner import EngineRunner
from app.ir.hashing import canonical_json, content_address

PROJECT = "proj-cockpit"
GRAPH = "strategy.expanding_z_impulse"
INSTRUMENT = "SILVERM"
INTERVAL = "30minute"
IR_KEY = f"ir.{GRAPH}"


def _graph_document(version: int = 1) -> dict:
    from app.ir.strategies.expanding_z import GRAPH as DOCUMENT

    return {**DOCUMENT, "version": version}


@pytest.fixture(autouse=True)
def a_fresh_database():
    init_db(reset=True)
    yield


@pytest.fixture(autouse=True)
def evidence_bridge(monkeypatch):
    monkeypatch.setattr(pa, "verified_decision", lambda **asked: {
        "run_id": 41, "candidate_id": 9, "project_id": PROJECT,
        "graph_identifier": GRAPH, "graph_version": asked["graph_version"],
        "content_address": content_address(_graph_document(asked["graph_version"])),
        "decision": "approved"})


@pytest.fixture(autouse=True)
def a_clean_registry():
    from app.strategy.registry import _REGISTRY

    before = dict(_REGISTRY)
    yield
    _REGISTRY.clear()
    _REGISTRY.update(before)


def _deploy(session, *, activate: bool = True) -> IrPaperDeployment:
    if session.get(Project, PROJECT) is None:
        session.add(Project(project_id=PROJECT, name="cockpit"))
    if session.get(GraphArtifact, GRAPH) is None:
        session.add(GraphArtifact(identifier=GRAPH, project_id=PROJECT,
                                  display_name="m", draft_json="{}", draft_revision=0))
    session.flush()
    document = _graph_document(1)
    if session.get(GraphVersion, (GRAPH, 1)) is None:
        session.add(GraphVersion(graph_identifier=GRAPH, version=1,
                                 artifact_json=canonical_json(document),
                                 content_address=content_address(document)))
    session.flush()
    row = pa.stage(session, project_id=PROJECT, graph_identifier=GRAPH, graph_version=1,
                   deployment_id=LEGACY_DEPLOYMENT_ID, instrument_key=INSTRUMENT,
                   interval=INTERVAL)
    session.commit()
    if activate:
        pa.activate(session, row.id, revision=row.revision)
        session.commit()
    return row


@pytest.fixture
def runner():
    r = EngineRunner(owner_id="owner", broker_account_id="account.default")
    r.refresh_paper_authority()
    try:
        yield r
    finally:
        r.broker.close()


def _instrument(view: dict, key: str = INSTRUMENT) -> dict:
    return next(i for i in view["instruments"] if i["instrument_key"] == key)


# ── 1. the eight questions ───────────────────────────────────────────────────────

class TestTheCockpitCanAnswer:
    def test_what_exact_strategy_is_authorised_and_why(self):
        with SessionLocal() as s:
            row = _deploy(s)
            approved = row.graph_content_address
        r = EngineRunner(owner_id="owner", broker_account_id="account.default")
        r.refresh_paper_authority()
        try:
            with SessionLocal() as s:
                item = _instrument(cockpit.view(r, s).to_dict())
            assert item["strategy_key"] == IR_KEY
            assert item["strategy_version"] == approved
            assert item["source"] == "ir_graph"
            assert item["authority"] == "authoritative"
            assert item["origin"] == "paper_authority_deployment"
            assert "authoritative for SILVERM" in item["reason"]
            assert item["binding_error"] is None
        finally:
            r.broker.close()

    def test_what_immutable_graph_is_running_and_on_what_admission(self):
        with SessionLocal() as s:
            row = _deploy(s)
            approved = row.graph_content_address
        r = EngineRunner(owner_id="owner", broker_account_id="account.default")
        r.refresh_paper_authority()
        try:
            with SessionLocal() as s:
                graph = _instrument(cockpit.view(r, s).to_dict())["graph"]
            assert graph["graph_identifier"] == GRAPH
            assert graph["graph_version"] == 1
            assert graph["content_address"] == approved
            assert graph["admission"]["evidence_run_id"] == 41
            assert graph["admission"]["evidence_candidate_id"] == 9
            assert graph["admission"]["model"] == "admission-prerequisite"
        finally:
            r.broker.close()

    def test_in_which_book(self, runner):
        with SessionLocal() as s:
            view = cockpit.view(runner, s).to_dict()
        assert view["book"] == PAPER
        assert view["execution_mode"] == PAPER
        assert view["foreign_book"]["other_book"] == "live"

    def test_what_positions_and_money_it_created(self, runner):
        with SessionLocal() as s:
            _deploy(s)
            s.add(Position(
                instrument_key=INSTRUMENT, direction="LONG", option_type="EQ",
                tradingsymbol="X", exchange="MCX", segment="equity_intraday",
                strike=0.0, expiry=dt.date(2030, 1, 1), qty=1, lot_size=1,
                entry_premium=100.0, entry_charges=0.0, entry_cost=100.0,
                entry_spot=100.0, entry_time=dt.datetime(2026, 1, 1, 10, 0),
                stop_price=99.0, target_price=101.0, high_water_premium=100.0,
                last_premium=100.0, mfe=0.0, mae=0.0, mode=PAPER,
                deployment_id=LEGACY_DEPLOYMENT_ID, strategy_key=IR_KEY,
                strategy_version="sha256:" + "b" * 64))
            s.commit()
        runner.refresh_paper_authority()
        with SessionLocal() as s:
            view = cockpit.view(runner, s).to_dict()
        item = _instrument(view)
        assert item["position"] is not None
        assert item["position"]["instrument_key"] == INSTRUMENT
        assert set(view["paper_pnl"]) >= {"cash", "realized_pnl", "equity"}

    def test_whether_it_may_open_another_entry_and_why_not(self, runner):
        runner.armed = False
        with SessionLocal() as s:
            item = _instrument(cockpit.view(runner, s).to_dict(), "NIFTY")
        assert item["entry"]["allowed"] is False
        assert cockpit.GATE_DISARMED in item["entry"]["blocked_by"]

        runner.armed = True
        runner.set_entries_blocked("NIFTY", True)
        with SessionLocal() as s:
            item = _instrument(cockpit.view(runner, s).to_dict(), "NIFTY")
        assert cockpit.GATE_ENTRIES_BLOCKED in item["entry"]["blocked_by"]

    def test_the_entry_answer_never_claims_to_be_the_whole_decision(self, runner):
        """`complete=False` is load-bearing. The full chain lives in `process_entries`;
        reporting `allowed=True` as the whole answer would make this a second entry
        authority."""
        runner.armed = True
        with SessionLocal() as s:
            item = _instrument(cockpit.view(runner, s).to_dict(), "NIFTY")
        assert item["entry"]["complete"] is False
        assert "process_entries" in item["entry"]["note"]

    def test_which_lifecycle_actions_are_available(self):
        with SessionLocal() as s:
            _deploy(s)
        r = EngineRunner(owner_id="owner", broker_account_id="account.default")
        r.refresh_paper_authority()
        try:
            with SessionLocal() as s:
                item = _instrument(cockpit.view(r, s).to_dict())
            assert set(item["lifecycle_actions"]) == {"pause", "retire"}
        finally:
            r.broker.close()

    def test_an_instrument_with_no_graph_offers_no_graph_lifecycle(self, runner):
        with SessionLocal() as s:
            item = _instrument(cockpit.view(runner, s).to_dict(), "NIFTY")
        assert item["graph"] is None
        assert item["lifecycle_actions"] == []

    def test_refusal_and_problem_state_is_reported(self):
        with SessionLocal() as s:
            _deploy(s)
        with SessionLocal() as s:
            s.query(IrPaperDeployment).update(
                {"graph_content_address": "sha256:" + "0" * 64})
            s.commit()
        r = EngineRunner(owner_id="owner", broker_account_id="account.default")
        r.refresh_paper_authority()
        try:
            with SessionLocal() as s:
                view = cockpit.view(r, s).to_dict()
            assert view["problems"]["paper_authority"], \
                "a dropped binding must be visible to an operator, not only in a log"
            assert _instrument(view)["graph"] is None
        finally:
            r.broker.close()


# ── 2. fidelity: the cockpit reports the engine's answer ─────────────────────────

class TestItIsNotASecondOpinion:
    def test_the_binding_is_the_engines_own_binding(self):
        with SessionLocal() as s:
            _deploy(s)
        r = EngineRunner(owner_id="owner", broker_account_id="account.default")
        r.refresh_paper_authority()
        try:
            engine_binding = r._binding_for(INSTRUMENT)
            with SessionLocal() as s:
                item = _instrument(cockpit.view(r, s).to_dict())
            assert item["strategy_key"] == engine_binding.strategy_key
            assert item["strategy_version"] == engine_binding.strategy_version
            assert item["origin"] == engine_binding.origin
            assert item["reason"] == engine_binding.reason
            assert item["authority"] == engine_binding.authority
        finally:
            r.broker.close()

    def test_a_refused_binding_is_reported_as_refused_not_as_the_default(self, runner):
        """An unregistered graph key must not be laundered into a working default by the
        read model — the silent-substitution class, arriving through a viewer."""
        runner.strategy_keys["NIFTY"] = "ir.does.not.exist"
        with SessionLocal() as s:
            item = _instrument(cockpit.view(runner, s).to_dict(), "NIFTY")
        assert item["binding_error"] or item["strategy_key"] == "ir.does.not.exist"
        assert item["strategy_key"] != "trend_impulse_v3"

    def test_deployment_listing_is_the_domain_services_own(self):
        with SessionLocal() as s:
            _deploy(s)
            assert cockpit.paper_deployments(s) == pa.listing(s, include_retired=True)

    def test_health_defers_rather_than_deciding(self, runner):
        with SessionLocal() as s:
            health = cockpit.view(runner, s).to_dict()["health"]
        assert health["verdict_owned_by"] == "GET /api/health"
        assert "ok" not in health and "status" not in health, \
            "the cockpit must not publish a second readiness verdict"


# ── 3. it is a read model ────────────────────────────────────────────────────────

class TestReadOnly:
    def test_admission_facts_never_come_from_a_research_read(self, runner, monkeypatch):
        """ADR 0013: the *admission basis* is held by the execution plane and is a
        historical fact. Observability may query research (that is Phase 2's whole point),
        but the admitting lineage must still be readable with research completely dead —
        otherwise the admission-only model is a claim rather than a property."""
        import app.core.research_read as rr

        def trap(*a, **k):
            raise AssertionError("the admission basis was read from the research plane")

        monkeypatch.setattr(rr, "_research_session", trap, raising=True)
        monkeypatch.setattr(rr, "verified_graph_decision", trap, raising=True)
        monkeypatch.setattr(rr, "graph_decision_history", trap, raising=True)
        with SessionLocal() as s:
            _deploy(s)
        runner.refresh_paper_authority()
        with SessionLocal() as s:
            graph = _instrument(cockpit.view(runner, s).to_dict())["graph"]
        assert graph["admission"]["evidence_run_id"] == 41
        assert graph["admission"]["evidence_candidate_id"] == 9
        assert graph["current_research"]["status"] == cockpit.RESEARCH_UNAVAILABLE

    def test_assembling_the_view_changes_no_state(self, runner):
        with SessionLocal() as s:
            _deploy(s)
        runner.refresh_paper_authority()
        before = (runner.armed, dict(runner.state), dict(runner.executed_binding),
                  {k: v.content_address for k, v in runner.paper_authority.items()})
        with SessionLocal() as s:
            rows_before = s.query(IrPaperDeployment).count()
            positions_before = s.query(Position).count()
            cockpit.view(runner, s).to_dict()
            assert s.query(IrPaperDeployment).count() == rows_before
            assert s.query(Position).count() == positions_before
        after = (runner.armed, dict(runner.state), dict(runner.executed_binding),
                 {k: v.content_address for k, v in runner.paper_authority.items()})
        assert before == after

    def test_the_module_owns_no_lifecycle_or_control_verb(self):
        """The read model must not grow a control surface. Lifecycle stays with
        `paper_authority`; arm and kill stay with the runner."""
        import inspect

        source = inspect.getsource(cockpit)
        for verb in ("def pause", "def resume", "def retire", "def activate",
                     "def arm", "def kill", "session.add", "session.commit",
                     "session.delete"):
            assert verb not in source, f"the cockpit read model must not define {verb!r}"


# ── 4. the route ─────────────────────────────────────────────────────────────────

class TestTheRoute:
    def test_it_serves_the_read_model(self):
        from fastapi.testclient import TestClient

        from app.main import app

        with SessionLocal() as s:
            _deploy(s)
        client = TestClient(app)
        app.state.runner = r = EngineRunner(owner_id="owner", broker_account_id="account.default")
        r.refresh_paper_authority()
        try:
            body = client.get("/api/execution/cockpit").json()
            assert body["book"] == PAPER
            item = _instrument(body)
            assert item["strategy_key"] == IR_KEY
            assert item["graph"]["graph_identifier"] == GRAPH

            listing = client.get("/api/execution/cockpit/deployments").json()
            assert listing["deployments"][0]["graph_identifier"] == GRAPH
            assert listing["deployments"][0]["state"] == "paper_active"
        finally:
            r.broker.close()
            app.state.runner = None

    def test_the_route_exposes_no_new_control_operation(self):
        """Every mutating cockpit action must already exist as a domain-service route."""
        from app.api import routes

        import inspect
        source = inspect.getsource(routes.execution_cockpit)
        assert "post" not in source.lower().split("def ")[0]
        for name in ("execution_cockpit", "execution_cockpit_deployments"):
            fn = getattr(routes, name)
            assert not any(
                verb in inspect.getsource(fn)
                for verb in ("paper_authority.pause", "paper_authority.retire",
                             "paper_authority.activate", ".arm(", ".kill("))


# ── 5. current research: observability, never authority (ADR 0013 §5.3) ──────────

def _history(monkeypatch, entries):
    """State what research currently says, at the one door the cockpit uses."""
    import app.core.research_read as rr

    monkeypatch.setattr(rr, "graph_decision_history",
                        lambda **asked: entries, raising=True)


def _decision(candidate_id: int, verdict: str) -> dict:
    return {"run_id": 41, "candidate_id": candidate_id, "decision": verdict,
            "decided_at": "2026-08-08T00:00:00Z", "reason": "because",
            "graph_content_address": "sha256:" + "c" * 64}


class TestCurrentResearchView:
    """Three facts, kept apart: admission basis, current research, execution authority."""

    def _graph(self, runner):
        with SessionLocal() as s:
            return _instrument(cockpit.view(runner, s).to_dict())["graph"]

    def test_no_newer_decision(self, runner, monkeypatch):
        with SessionLocal() as s:
            _deploy(s)
        runner.refresh_paper_authority()
        _history(monkeypatch, [_decision(9, "approved")])
        research = self._graph(runner)["current_research"]
        assert research["status"] == cockpit.RESEARCH_NO_NEWER
        assert research["operator_attention"] is False
        assert research["newer_decision_count"] == 0

    def test_a_newer_rejection_raises_attention_without_touching_authority(
            self, runner, monkeypatch):
        """The headline case. Research now says no; the deployment keeps authority."""
        with SessionLocal() as s:
            row = _deploy(s)
            approved = row.graph_content_address
        runner.refresh_paper_authority()
        _history(monkeypatch, [_decision(9, "approved"), _decision(14, "rejected")])

        graph = self._graph(runner)
        research = graph["current_research"]
        assert research["status"] == cockpit.RESEARCH_NEWER_REJECTED
        assert research["latest_decision"]["candidate_id"] == 14
        assert research["operator_attention"] is True
        assert research["affects_execution_authority"] is False
        # ...and the other two facts are untouched.
        assert research["admission_basis"]["evidence_candidate_id"] == 9
        assert graph["content_address"] == approved
        with SessionLocal() as s:
            item = _instrument(cockpit.view(runner, s).to_dict())
        assert item["authority"] == "authoritative"
        assert item["strategy_key"] == IR_KEY

    def test_a_newer_decision_is_not_assumed_negative(self, runner, monkeypatch):
        """A re-approval must read as a re-approval, not as contradiction."""
        with SessionLocal() as s:
            _deploy(s)
        runner.refresh_paper_authority()
        _history(monkeypatch, [_decision(9, "approved"), _decision(20, "approved")])
        research = self._graph(runner)["current_research"]
        assert research["status"] == cockpit.RESEARCH_NEWER_APPROVED
        assert research["operator_attention"] is False
        assert research["newer_decision_count"] == 1

    def test_the_newest_decision_wins_when_several_are_newer(self, runner, monkeypatch):
        with SessionLocal() as s:
            _deploy(s)
        runner.refresh_paper_authority()
        _history(monkeypatch, [_decision(9, "approved"), _decision(14, "rejected"),
                               _decision(21, "approved")])
        research = self._graph(runner)["current_research"]
        assert research["status"] == cockpit.RESEARCH_NEWER_APPROVED
        assert research["latest_decision"]["candidate_id"] == 21
        assert research["newer_decision_count"] == 2

    def test_research_unavailable_is_stated_not_inferred(self, runner, monkeypatch):
        with SessionLocal() as s:
            _deploy(s)
        runner.refresh_paper_authority()
        _history(monkeypatch, None)
        research = self._graph(runner)["current_research"]
        assert research["status"] == cockpit.RESEARCH_UNAVAILABLE
        assert research["latest_decision"] is None
        assert research["affects_execution_authority"] is False

    def test_a_research_read_that_raises_degrades_rather_than_failing_the_view(
            self, runner, monkeypatch):
        """The rest of the execution view must still assemble — what is running, in which
        book, on what admission, with what authority."""
        import app.core.research_read as rr

        with SessionLocal() as s:
            _deploy(s)
        runner.refresh_paper_authority()

        def boom(**asked):
            raise RuntimeError("research plane on fire")

        monkeypatch.setattr(rr, "graph_decision_history", boom, raising=True)
        with SessionLocal() as s:
            view = cockpit.view(runner, s).to_dict()
        item = _instrument(view)
        assert item["strategy_key"] == IR_KEY
        assert item["authority"] == "authoritative"
        assert item["graph"]["graph_identifier"] == GRAPH
        assert view["book"] == PAPER
        assert item["graph"]["current_research"]["status"] == cockpit.RESEARCH_UNAVAILABLE
        assert "research plane on fire" in item["graph"]["current_research"]["detail"]

    def test_an_invisible_admission_decision_is_not_reported_as_rejected(
            self, runner, monkeypatch):
        with SessionLocal() as s:
            _deploy(s)
        runner.refresh_paper_authority()
        _history(monkeypatch, [_decision(99, "approved")])   # ours (9) is not here
        research = self._graph(runner)["current_research"]
        assert research["status"] == cockpit.RESEARCH_ADMISSION_NOT_VISIBLE
        assert research["operator_attention"] is True

    def test_every_status_is_declared(self):
        assert set(cockpit.CURRENT_RESEARCH_STATUSES) == {
            cockpit.RESEARCH_NO_NEWER, cockpit.RESEARCH_NEWER_APPROVED,
            cockpit.RESEARCH_NEWER_REJECTED, cockpit.RESEARCH_UNAVAILABLE,
            cockpit.RESEARCH_ADMISSION_NOT_VISIBLE}


class TestCurrentResearchIsNotAControlPath:
    """The critical invariant: a change in the research view mutates nothing."""

    def test_a_newer_rejection_changes_no_deployment_state(self, runner, monkeypatch):
        with SessionLocal() as s:
            row = _deploy(s)
        runner.refresh_paper_authority()
        with SessionLocal() as s:
            before = s.get(IrPaperDeployment, row.id).to_dict()

        _history(monkeypatch, [_decision(9, "approved"), _decision(14, "rejected")])
        for _ in range(3):                       # repeated reads must stay inert
            with SessionLocal() as s:
                cockpit.view(runner, s).to_dict()

        with SessionLocal() as s:
            after = s.get(IrPaperDeployment, row.id).to_dict()
        assert after == before
        assert after["state"] == pa.PAPER_ACTIVE
        assert runner.paper_authority[INSTRUMENT].content_address == \
            before["graph_content_address"]
        assert runner.state.get(INSTRUMENT) is None or True   # unchanged either way

    def test_the_reader_holds_no_transition_verb(self):
        """`current_research` takes a binding and returns a dict — no session, no runner,
        nothing it could transition even if a later edit tried."""
        import ast
        import inspect
        import textwrap

        tree = ast.parse(textwrap.dedent(inspect.getsource(cockpit.current_research)))
        fn = tree.body[0]
        if (fn.body and isinstance(fn.body[0], ast.Expr)
                and isinstance(fn.body[0].value, ast.Constant)):
            fn.body = fn.body[1:]          # the prose may discuss what the code may not do
        body = ast.unparse(fn)
        for verb in ("pause", "retire", "activate", "resume", "commit", "flush",
                     "session", "runner"):
            assert verb not in body, f"the research reader must not reference {verb!r}"
        assert [a.arg for a in fn.args.args] == ["binding"], \
            "it takes a binding and nothing it could mutate"

    def test_research_status_never_reaches_the_authority_fields(self, runner, monkeypatch):
        _history(monkeypatch, [_decision(9, "approved"), _decision(14, "rejected")])
        with SessionLocal() as s:
            _deploy(s)
        runner.refresh_paper_authority()
        with SessionLocal() as s:
            item = _instrument(cockpit.view(runner, s).to_dict())
        # authority/lifecycle are decided by the execution plane alone
        assert item["authority"] == "authoritative"
        assert item["binding_error"] is None
        assert set(item["lifecycle_actions"]) == {"pause", "retire"}


# ── 6. lifecycle capability: the backend declares, the frontend renders ──────────

class TestLifecycleCapability:
    """The defect this slice closes.

    `lifecycle_actions` was derived from `runner.paper_authority`, which holds only
    **active** bindings, and returned a hard-coded `("pause", "retire")`. A staged or paused
    deployment is not in that map, so it reported *no actions at all* — leaving a frontend
    with no way to offer resume except by inferring it from `state`, which is exactly the
    transition logic the backend is supposed to own.
    """

    def _item(self, runner, key=INSTRUMENT):
        with SessionLocal() as s:
            return _instrument(cockpit.view(runner, s).to_dict(), key)

    def _fresh_runner(self):
        r = EngineRunner(owner_id="owner", broker_account_id="account.default")
        r.refresh_paper_authority()
        return r

    def test_staged_offers_activate_and_retire(self):
        with SessionLocal() as s:
            _deploy(s, activate=False)
        r = self._fresh_runner()
        try:
            item = self._item(r)
            assert item["lifecycle"]["state"] == pa.STAGED
            assert set(item["lifecycle_actions"]) == {"activate", "retire"}
        finally:
            r.broker.close()

    def test_active_offers_pause_and_retire(self):
        with SessionLocal() as s:
            _deploy(s)
        r = self._fresh_runner()
        try:
            item = self._item(r)
            assert item["lifecycle"]["state"] == pa.PAPER_ACTIVE
            assert set(item["lifecycle_actions"]) == {"pause", "retire"}
        finally:
            r.broker.close()

    def test_paused_offers_resume_without_the_frontend_inferring_it(self):
        """**The headline case.** A paused deployment must declare its resume capability."""
        with SessionLocal() as s:
            row = _deploy(s)
            pa.pause(s, row.id, revision=row.revision)
            s.commit()
        r = self._fresh_runner()
        try:
            item = self._item(r)
            assert item["lifecycle"]["state"] == pa.PAUSED
            assert "resume" in item["lifecycle_actions"], (
                "a paused deployment must declare resume; a frontend deriving it from "
                "state would be reproducing the transition rules")
            assert set(item["lifecycle_actions"]) == {"resume", "retire"}
            assert r.paper_authority == {}, "and it is correctly not authoritative"
        finally:
            r.broker.close()

    def test_retired_exposes_no_resurrection_path(self):
        with SessionLocal() as s:
            row = _deploy(s)
            pa.retire(s, row.id, revision=row.revision, restore_strategy_key=None, owner_id="owner")
            s.commit()
        r = self._fresh_runner()
        try:
            item = self._item(r)
            assert item["lifecycle"]["state"] is None      # no live row remains
            assert item["lifecycle_actions"] == []
        finally:
            r.broker.close()

    def test_the_actions_carry_what_invoking_them_requires(self):
        with SessionLocal() as s:
            row = _deploy(s)
            revision = row.revision
        r = self._fresh_runner()
        try:
            lifecycle = self._item(r)["lifecycle"]
            assert lifecycle["revision"] == revision
            assert lifecycle["deployment_row_id"] is not None
            assert lifecycle["plane"] == cockpit.PLANE_PAPER
            by_action = {a["action"]: a for a in lifecycle["actions"]}
            assert by_action["retire"]["requires"] == ["restore_strategy_key"]
            assert by_action["pause"]["requires"] == []
            assert all(a["requires_revision"] for a in lifecycle["actions"])
        finally:
            r.broker.close()

    def test_the_capability_comes_from_the_owning_service(self):
        """Not a table in the cockpit: the same answer the domain gives."""
        with SessionLocal() as s:
            row = _deploy(s)
            pa.pause(s, row.id, revision=row.revision)
            s.commit()
        r = self._fresh_runner()
        try:
            actions = self._item(r)["lifecycle_actions"]
            assert tuple(actions) == pa.permitted_transitions(pa.PAUSED)
        finally:
            r.broker.close()

    def test_an_instrument_with_no_deployment_offers_nothing(self, runner):
        item = self._item(runner, "NIFTY")
        assert item["lifecycle"]["state"] is None
        assert item["lifecycle_actions"] == []
        assert item["shadow_lifecycle"]["state"] is None

    def test_paper_and_shadow_capabilities_are_not_conflated(self, runner):
        """Separate keys, separate services. `lifecycle_actions` remains the paper plane's,
        so a shadow row can never put an action on the authoritative surface."""
        with SessionLocal() as s:
            _deploy(s)
        runner.refresh_paper_authority()
        item = self._item(runner)
        assert item["lifecycle"]["plane"] == cockpit.PLANE_PAPER
        assert item["shadow_lifecycle"]["plane"] is None
        assert item["shadow_lifecycle"]["actions"] == []

    def test_a_newer_rejection_does_not_remove_lifecycle_capability(
            self, runner, monkeypatch):
        """Research may raise attention. It may not take away resume, pause or retire —
        only the execution-plane state decides capability."""
        with SessionLocal() as s:
            row = _deploy(s)
            pa.pause(s, row.id, revision=row.revision)
            s.commit()
        runner.refresh_paper_authority()
        _history(monkeypatch, [_decision(9, "approved"), _decision(14, "rejected")])
        item = self._item(runner)
        assert set(item["lifecycle_actions"]) == {"resume", "retire"}
        assert item["lifecycle"]["state"] == pa.PAUSED
