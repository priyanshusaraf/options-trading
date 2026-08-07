"""A paper-authoritative deployment: the record, its lifecycle, and its rollback.

L1.3A made a graph *observable* with lineage. This makes one **authoritative in the paper
book** — the first record through which IR output may create execution state — and it must
be structurally unable to say the same thing about the live book.

Same discipline as the shadow record, because the failure modes are the same and the stakes
are higher: identities stay in separate columns, lineage is verified rather than declared,
and the reviewed `(ir_graph, paper, authoritative)` triple is the only one the service can
write. What is new is that authority must be **revocable to a named target** — retiring a
binding restores a strategy somebody wrote down, or nothing at all, and never a value
inferred at runtime.
"""
from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from app.core import paper_authority as pa
from app.db.models import (
    LEGACY_DEPLOYMENT_ID,
    GraphArtifact,
    GraphVersion,
    IrPaperDeployment,
    Project,
)
from app.db.session import SessionLocal, init_db
from app.ir.hashing import canonical_json, content_address

PROJECT = "proj-paper"
GRAPH = "strategy.expanding_z_impulse"
#: MCX 09:00–23:30, so a 302-bar warmup is admissible at 30 minutes — the same deliberate
#: choice `test_shadow_deployments.py` documents. An NSE name cannot settle here, and a
#: test that used one would be asserting the admission contract's refusal by accident.
INSTRUMENT = "SILVERM"
INTERVAL = "30minute"


def _graph_document(version: int = 1) -> dict:
    from app.ir.strategies.expanding_z import GRAPH as DOCUMENT

    return {**DOCUMENT, "version": version}


def seed_graph(session, version: int = 1) -> GraphVersion:
    if session.get(Project, PROJECT) is None:
        session.add(Project(project_id=PROJECT, name="paper"))
    if session.get(GraphArtifact, GRAPH) is None:
        session.add(GraphArtifact(identifier=GRAPH, project_id=PROJECT,
                                  display_name="mirror", draft_json="{}",
                                  draft_revision=0))
    session.flush()
    document = _graph_document(version)
    row = GraphVersion(graph_identifier=GRAPH, version=version,
                       artifact_json=canonical_json(document),
                       content_address=content_address(document))
    session.add(row)
    session.flush()
    return row


def approved_evidence(**overrides):
    return {"run_id": 7, "candidate_id": 3, "project_id": PROJECT,
            "graph_identifier": GRAPH, "graph_version": 1,
            # Content, not name. The admission binding requires the address research
            # approved to be the address receiving authority, so a stub that invents an
            # address would be asserting a contract the service no longer offers.
            "content_address": content_address(_graph_document(1)),
            "decision": "approved",
            **overrides}


@pytest.fixture(autouse=True)
def evidence_bridge(monkeypatch):
    """Stub the read-only research bridge — the approval lineage lives in the research
    plane's own database (hard invariant 5), so these tests state the verdict."""
    verdicts = {"value": "approve-what-is-asked"}

    def bridge(**asked):
        if verdicts["value"] != "approve-what-is-asked":
            return verdicts["value"]
        return approved_evidence(graph_version=asked["graph_version"])

    monkeypatch.setattr(pa, "verified_decision", bridge)
    return verdicts


@pytest.fixture(autouse=True)
def a_fresh_database():
    """An autouse fixture, not `setup_function`: the xunit hook applies only to
    module-level test functions, and every test here is a method on a class — it would
    have run for none of them, silently, leaving each test to inherit whatever database
    the previous file left behind."""
    init_db(reset=True)
    yield


def stage(session, **overrides):
    return pa.stage(
        session, project_id=overrides.pop("project_id", PROJECT),
        graph_identifier=overrides.pop("graph_identifier", GRAPH),
        graph_version=overrides.pop("graph_version", 1),
        deployment_id=overrides.pop("deployment_id", LEGACY_DEPLOYMENT_ID),
        instrument_key=overrides.pop("instrument_key", INSTRUMENT),
        interval=overrides.pop("interval", INTERVAL), **overrides)


def staged(session, **overrides):
    seed_graph(session, overrides.get("graph_version", 1))
    return stage(session, **overrides)


# ── the record says what it is ──────────────────────────────────────────────────

class TestTheRecord:
    def test_it_carries_every_identity_separately(self):
        """Eleven facts, eleven columns. The recorded defect class in this codebase is one
        layer asserting another's fact, and the cheapest way to commit it is to encode
        several of them in the strategy key and parse them back out."""
        with SessionLocal() as s:
            row = staged(s)
            assert row.project_id == PROJECT
            assert row.graph_identifier == GRAPH
            assert row.graph_version == 1
            assert row.graph_content_address.startswith("sha256:")
            assert row.deployment_id == LEGACY_DEPLOYMENT_ID
            assert row.instrument_key == INSTRUMENT
            assert row.interval == INTERVAL
            assert row.strategy_key == f"ir.{GRAPH}"
            assert row.runtime_source == "ir_graph"
            assert row.execution_mode == "paper"
            assert row.authority == "authoritative"
            assert row.state == pa.STAGED
            assert row.revision == 0

    def test_the_stable_key_is_not_the_content_address(self):
        """They answer different questions. The key survives an edit so persisted rows
        keep resolving; the address identifies the build that actually ran."""
        with SessionLocal() as s:
            row = staged(s)
            assert row.strategy_key != row.graph_content_address
            assert str(row.graph_version) not in row.strategy_key

    def test_the_database_refuses_a_live_deployment(self):
        """The lock beside the gate. `GRANTS` refuses live IR authority in code; this
        refuses it in the schema, and neither depends on the other."""
        with SessionLocal() as s:
            row = staged(s)
            s.commit()
            row.execution_mode = "live"
            with pytest.raises(IntegrityError):
                s.commit()

    def test_the_database_refuses_a_non_authoritative_paper_row(self):
        """The complement: this table means authority. A shadow-shaped row here would be
        a second way to express observation, and one of anything is the rule."""
        with SessionLocal() as s:
            row = staged(s)
            s.commit()
            row.authority = "non_authoritative"
            with pytest.raises(IntegrityError):
                s.commit()

    def test_the_service_has_no_mode_or_authority_parameter(self):
        """The third refusal. A service that cannot say the word cannot be talked into it
        by a caller, a route, or a future edit that adds a keyword argument."""
        import inspect

        params = set(inspect.signature(pa.stage).parameters)
        assert not {"execution_mode", "authority", "mode", "runtime_source"} & params


# ── activation verifies rather than declares ────────────────────────────────────

class TestActivation:
    def test_a_staged_deployment_activates_for_paper(self):
        with SessionLocal() as s:
            row = staged(s)
            s.commit()
            activated = pa.activate(s, row.id, revision=row.revision)
            assert activated.state == pa.PAPER_ACTIVE
            assert activated.evidence_verified_at is not None
            assert activated.revision == 1

    def test_a_content_address_that_moved_fails_closed(self):
        """Safety proof 5. The row claims to name specific bytes; if the artefact no
        longer hashes to them, the claim is false and activation must say so rather than
        rebind to whatever is there now."""
        with SessionLocal() as s:
            row = staged(s)
            row.graph_content_address = "sha256:" + "0" * 64
            s.commit()
            with pytest.raises(pa.BindingUnverifiable):
                pa.activate(s, row.id, revision=row.revision)

    def test_a_graph_version_that_does_not_exist_fails_closed(self):
        """Staging is where this is caught, and it has to be: the foreign key means a row
        naming a non-existent version cannot be written in the first place. Deleting the
        version out from under an existing row is refused by RESTRICT, which is the
        schema making the same guarantee from the other side."""
        with SessionLocal() as s:
            seed_graph(s, 1)
            with pytest.raises(pa.BindingUnverifiable):
                stage(s, graph_version=2)

    def test_missing_evidence_fails_closed(self, evidence_bridge):
        """Safety proof 6. Paper money is still a record somebody will reason from."""
        evidence_bridge["value"] = None
        with SessionLocal() as s:
            row = staged(s)
            s.commit()
            with pytest.raises(pa.EvidenceUnverified):
                pa.activate(s, row.id, revision=row.revision)
            assert s.get(IrPaperDeployment, row.id).state == pa.STAGED

    def test_rejected_evidence_fails_closed(self, evidence_bridge):
        evidence_bridge["value"] = approved_evidence(decision="rejected")
        with SessionLocal() as s:
            row = staged(s)
            s.commit()
            with pytest.raises(pa.EvidenceUnverified):
                pa.activate(s, row.id, revision=row.revision)

    def test_evidence_for_a_different_version_fails_closed(self, evidence_bridge):
        """An approval is for an artefact, not for a name."""
        evidence_bridge["value"] = approved_evidence(graph_version=99)
        with SessionLocal() as s:
            row = staged(s)
            s.commit()
            with pytest.raises(pa.EvidenceUnverified):
                pa.activate(s, row.id, revision=row.revision)

    def test_a_stale_revision_is_refused(self):
        with SessionLocal() as s:
            row = staged(s)
            s.commit()
            pa.activate(s, row.id, revision=0)
            with pytest.raises(pa.RevisionConflict):
                pa.pause(s, row.id, revision=0)


# ── lifecycle ───────────────────────────────────────────────────────────────────

class TestLifecycle:
    def test_pause_and_resume(self):
        with SessionLocal() as s:
            row = staged(s)
            s.commit()
            pa.activate(s, row.id, revision=0)
            paused = pa.pause(s, row.id, revision=1)
            assert paused.state == pa.PAUSED
            resumed = pa.resume(s, row.id, revision=2)
            assert resumed.state == pa.PAPER_ACTIVE

    def test_resuming_re_verifies_rather_than_trusting_the_pause(self):
        """A pause is a gap in which the world can move. Resuming on trust would make it
        the one window where a graph could change unnoticed."""
        with SessionLocal() as s:
            row = staged(s)
            s.commit()
            pa.activate(s, row.id, revision=0)
            pa.pause(s, row.id, revision=1)
            row.graph_content_address = "sha256:" + "0" * 64
            s.commit()
            with pytest.raises(pa.BindingUnverifiable):
                pa.resume(s, row.id, revision=row.revision)

    def test_retirement_is_terminal(self):
        """A retired binding that could be revived would let a graph nobody re-approved
        come back — quietly, and most likely across a restart."""
        with SessionLocal() as s:
            row = staged(s)
            s.commit()
            pa.activate(s, row.id, revision=0)
            pa.retire(s, row.id, revision=1, restore_strategy_key=None)
            with pytest.raises(pa.IllegalTransition):
                pa.activate(s, row.id, revision=row.revision)

    def test_only_one_live_binding_per_instrument_and_interval(self):
        with SessionLocal() as s:
            staged(s)
            s.commit()
            with pytest.raises(IntegrityError):
                stage(s)
                s.commit()

    def test_retiring_frees_the_slot_without_deleting_the_history(self):
        with SessionLocal() as s:
            first = staged(s)
            s.commit()
            pa.retire(s, first.id, revision=0, restore_strategy_key=None)
            s.commit()
            second = stage(s)
            s.commit()
            assert second.id != first.id
            assert s.get(IrPaperDeployment, first.id).state == pa.RETIRED


# ── rollback is explicit ────────────────────────────────────────────────────────

class TestRollback:
    def test_retiring_restores_the_named_previous_authority(self):
        """The rollback target is written down at retirement, not inferred. "Whatever the
        instrument row said before" is a runtime guess, and this project has closed that
        failure twice."""
        from app.db.models import InstrumentState

        with SessionLocal() as s:
            row = staged(s)
            s.commit()
            pa.activate(s, row.id, revision=0)
            s.commit()

            pa.retire(s, row.id, revision=1, restore_strategy_key="expanding_z_v4")
            s.commit()

            assert s.get(IrPaperDeployment, row.id).rollback_strategy_key == "expanding_z_v4"
            assert s.get(InstrumentState, INSTRUMENT).strategy_key == "expanding_z_v4"

    def test_retiring_with_no_previous_authority_leaves_the_instrument_unassigned(self):
        from app.db.models import InstrumentState

        with SessionLocal() as s:
            row = staged(s)
            s.commit()
            pa.activate(s, row.id, revision=0)
            pa.retire(s, row.id, revision=1, restore_strategy_key=None)
            s.commit()
            state = s.get(InstrumentState, INSTRUMENT)
            assert state is None or state.strategy_key is None

    def test_a_rollback_target_that_cannot_execute_is_refused(self):
        """Rolling back onto a graph key would revoke authority and immediately re-grant
        it through the door this slice deliberately left shut."""
        with SessionLocal() as s:
            row = staged(s)
            s.commit()
            pa.activate(s, row.id, revision=0)
            with pytest.raises(pa.RollbackTargetInvalid):
                pa.retire(s, row.id, revision=1, restore_strategy_key=f"ir.{GRAPH}")

    def test_a_rollback_target_that_does_not_exist_is_refused(self):
        with SessionLocal() as s:
            row = staged(s)
            s.commit()
            pa.activate(s, row.id, revision=0)
            with pytest.raises(pa.RollbackTargetInvalid):
                pa.retire(s, row.id, revision=1, restore_strategy_key="no_such_strategy")

    def test_money_records_are_never_rewritten_by_a_rollback(self):
        """Rollback changes what runs next. It says nothing about what already traded."""
        import datetime as dt

        from app.db.models import Trade

        with SessionLocal() as s:
            row = staged(s)
            s.commit()
            pa.activate(s, row.id, revision=0)
            s.add(Trade(
                instrument_key=INSTRUMENT, direction="LONG", option_type="CE",
                tradingsymbol="X", exchange="MCX", segment="equity_intraday",
                strike=0.0, expiry=dt.date(2030, 1, 1), qty=1,
                entry_premium=100.0, exit_premium=101.0, entry_cost=100.0,
                exit_charges=0.0, entry_time=dt.datetime(2026, 1, 1, 10, 0),
                exit_time=dt.datetime(2026, 1, 1, 11, 0), entry_spot=100.0,
                exit_spot=101.0, gross_pnl=1.0, charges_total=0.0, net_pnl=1.0,
                return_pct=1.0, holding_minutes=60, win=True, exit_reason="TARGET",
                mode="paper", strategy_key=f"ir.{GRAPH}",
                strategy_version=row.graph_content_address))
            s.commit()

            pa.retire(s, row.id, revision=1, restore_strategy_key="expanding_z_v4")
            s.commit()

            trade = s.scalars(__import__("sqlalchemy").select(Trade)).one()
            assert trade.strategy_key == f"ir.{GRAPH}"
            assert trade.strategy_version == row.graph_content_address


# ── what the engine is handed ───────────────────────────────────────────────────

class TestActiveBindings:
    def test_only_active_bindings_are_returned(self):
        with SessionLocal() as s:
            row = staged(s)
            s.commit()
            assert pa.active_bindings(s) == []
            pa.activate(s, row.id, revision=0)
            s.commit()
            assert [b.instrument_key for b in pa.active_bindings(s)] == [INSTRUMENT]

    def test_paused_and_retired_bindings_do_not_come_back(self):
        """Safety proof 14, at the seam a restart actually uses."""
        with SessionLocal() as s:
            row = staged(s)
            s.commit()
            pa.activate(s, row.id, revision=0)
            pa.pause(s, row.id, revision=1)
            s.commit()
            assert pa.active_bindings(s) == []
            pa.retire(s, row.id, revision=2, restore_strategy_key=None)
            s.commit()
            assert pa.active_bindings(s) == []

    def test_the_bytes_behind_an_approved_version_cannot_move_at_all(self):
        """The first line of defence, and it is the database's. A trigger makes published
        graph versions immutable, so "the artefact was edited under an active deployment"
        is not a state this platform can reach. Asserted rather than assumed, because the
        reload check below is only *defence in depth* if this is what it is depending on."""
        with SessionLocal() as s:
            staged(s)
            s.commit()
            edited = {**_graph_document(1), "notes": "edited after approval"}
            with pytest.raises(IntegrityError, match="immutable"):
                s.query(GraphVersion).filter_by(graph_identifier=GRAPH, version=1).update(
                    {"artifact_json": canonical_json(edited)})
                s.commit()

    def test_reload_drops_a_binding_whose_recorded_address_disagrees(self):
        """Safety proof 5 at the reload boundary, from the side that *is* reachable.

        Graph bytes are immutable (above), so the disagreement this catches comes from the
        other direction: a deployment row whose recorded address is not what the artefact
        hashes to — a bad restore, a hand-edited row, a future writer with a bug. Either
        way the row claims to name bytes it does not name, and rebinding it to whatever is
        actually there is the silent substitution this project keeps closing."""
        problems: list[str] = []
        with SessionLocal() as s:
            row = staged(s)
            s.commit()
            pa.activate(s, row.id, revision=0)
            s.commit()
            assert len(pa.active_bindings(s)) == 1

            s.query(IrPaperDeployment).filter_by(id=row.id).update(
                {"graph_content_address": "sha256:" + "0" * 64})
            s.commit()

            assert pa.active_bindings(s, on_problem=problems.append) == []
            assert problems and "content address" in problems[0]

    def test_a_binding_carries_identities_and_nothing_invocable(self):
        """The engine holds these. If one carried a strategy object or a callable, the
        authority gate would be advisory — anything holding it could just call it."""
        import dataclasses

        with SessionLocal() as s:
            row = staged(s)
            s.commit()
            pa.activate(s, row.id, revision=0)
            s.commit()
            b = pa.active_bindings(s)[0]
            assert dataclasses.is_dataclass(b)
            for value in dataclasses.asdict(b).values():
                assert not callable(value)
            assert b.execution_mode == "paper"
            assert b.authority == "authoritative"


# ── admission binds CONTENT, not a name ─────────────────────────────────────────

class TestAdmissionBindsTheExactGraphContent:
    """The 2026-08-08 provenance correction.

    Evidence is looked up by `(project, identifier, version)` — a **name**. Until this
    check existed, every comparison was also on the name, so a research decision that
    approved one artefact could admit a *different* artefact carrying the same identifier
    and version. That is reachable across an independently restored `research.db`, and it
    was proven reachable through this service before the fix: research approved graph A,
    graph B took authority, activation succeeded, and the row recorded both addresses
    without ever comparing them.

    The invariant now enforced:

        the immutable graph content receiving deployment authority must be the same
        immutable graph content bound into the research evidence used to admit it.

    It is an **admission** check (ADR 0013) — activation and resume, never runtime reload.
    """

    def test_exact_matching_lineage_still_activates(self):
        """The success case, kept first so a regression that refuses everything is not
        mistaken for the guard working."""
        with SessionLocal() as s:
            row = staged(s)
            s.commit()
            pa.activate(s, row.id, revision=row.revision)
            s.commit()
            assert row.state == pa.PAPER_ACTIVE
            assert row.evidence_content_address == row.graph_content_address

    def test_another_graphs_approval_cannot_admit_this_one(self, monkeypatch):
        """**The adversarial case.** Graph A has a valid approval. Graph B is independently
        valid — it is a real, published, immutable version. An attempt is made to activate
        B on A's research lineage: same project, same identifier, same version number,
        genuine `approved` decision, different bytes."""
        graph_a = _graph_document(1)
        graph_b = _graph_document(2)
        address_a, address_b = content_address(graph_a), content_address(graph_b)
        assert address_a != address_b, "the two artefacts must genuinely differ"

        # Research approves A's content, under the name B is deployed as.
        monkeypatch.setattr(pa, "verified_decision", lambda **asked: approved_evidence(
            graph_version=asked["graph_version"], content_address=address_a))

        with SessionLocal() as s:
            row = staged(s, graph_version=2)          # B is what is being deployed
            s.commit()
            assert row.graph_content_address == address_b
            with pytest.raises(pa.EvidenceUnverified, match="two different artefacts"):
                pa.activate(s, row.id, revision=row.revision)

    def test_the_refusal_leaves_no_authority_behind(self, monkeypatch):
        """A refused admission must not half-happen: no active state, no recorded evidence
        lineage, nothing for a reload to pick up."""
        monkeypatch.setattr(pa, "verified_decision", lambda **asked: approved_evidence(
            graph_version=asked["graph_version"],
            content_address=content_address(_graph_document(1))))
        with SessionLocal() as s:
            row = staged(s, graph_version=2)
            s.commit()
            with pytest.raises(pa.EvidenceUnverified):
                pa.activate(s, row.id, revision=row.revision)
            s.rollback()
            current = s.get(IrPaperDeployment, row.id)
            assert current.state == pa.STAGED
            assert current.evidence_content_address == ""
            assert pa.active_bindings(s) == []

    def test_resume_re_checks_the_content_binding(self, monkeypatch):
        """Resume re-establishes admission, so it must apply the same test. A pause is a
        window in which the research plane can be restored from somewhere else."""
        with SessionLocal() as s:
            row = staged(s)
            s.commit()
            pa.activate(s, row.id, revision=row.revision)
            s.commit()
            pa.pause(s, row.id, revision=row.revision)
            s.commit()

            monkeypatch.setattr(pa, "verified_decision", lambda **asked: approved_evidence(
                graph_version=asked["graph_version"],
                content_address=content_address(_graph_document(2))))
            current = s.get(IrPaperDeployment, row.id)
            with pytest.raises(pa.EvidenceUnverified, match="two different artefacts"):
                pa.resume(s, current.id, revision=current.revision)

    def test_a_decision_naming_no_content_is_refused(self, monkeypatch):
        """An approval that cannot say which bytes it approved has admitted nothing."""
        monkeypatch.setattr(pa, "verified_decision", lambda **asked: approved_evidence(
            graph_version=asked["graph_version"], content_address=""))
        with SessionLocal() as s:
            row = staged(s)
            s.commit()
            with pytest.raises(pa.EvidenceUnverified, match="names no graph content"):
                pa.activate(s, row.id, revision=row.revision)

    def test_reload_does_not_apply_the_admission_check(self, monkeypatch):
        """ADMISSION-ONLY, preserved. The binding check belongs where authority is granted;
        putting it on reload would make every restart depend on the research plane."""
        with SessionLocal() as s:
            row = staged(s)
            s.commit()
            pa.activate(s, row.id, revision=row.revision)
            s.commit()

        def trap(**asked):
            raise AssertionError("reload consulted the research plane")

        monkeypatch.setattr(pa, "verified_decision", trap)
        with SessionLocal() as s:
            assert len(pa.active_bindings(s)) == 1


# ── lifecycle capability, as a description of the guards below it ────────────────

class TestPermittedTransitions:
    """`TRANSITIONS` is capability metadata an operational surface renders from. It is only
    worth anything if it agrees with the guards it describes, so this drives the **real
    services** from every state and compares.

    That agreement is what makes it a description rather than a second state machine.
    """

    #: `activate` is legal from `paused` — `resume` calls it — but the table names the
    #: transition once, so an operator is not offered two buttons for one action. This is
    #: the only permitted divergence between the table and the guards, and it is listed
    #: here so it stays deliberate rather than becoming drift nobody notices.
    SYNONYMS = {(pa.PAUSED, "activate")}

    def _row_in(self, session, state: str):
        row = staged(session)
        session.commit()
        if state == pa.STAGED:
            return row
        pa.activate(session, row.id, revision=row.revision)
        session.commit()
        if state == pa.PAPER_ACTIVE:
            return row
        pa.pause(session, row.id, revision=row.revision)
        session.commit()
        if state == pa.PAUSED:
            return row
        pa.retire(session, row.id, revision=row.revision, restore_strategy_key=None)
        session.commit()
        return row

    def _attempt(self, session, row, action: str):
        if action == "retire":
            return pa.retire(session, row.id, revision=row.revision,
                             restore_strategy_key=None)
        return getattr(pa, action)(session, row.id, revision=row.revision)

    @pytest.mark.parametrize("state", pa.STATES)
    @pytest.mark.parametrize("action", ("activate", "pause", "resume", "retire"))
    def test_the_table_agrees_with_the_guards(self, state, action):
        with SessionLocal() as s:
            row = self._row_in(s, state)
            permitted = action in pa.permitted_transitions(state)
            try:
                self._attempt(s, row, action)
                refused = False
            except pa.IllegalTransition:
                refused = True
            s.rollback()

        if (state, action) in self.SYNONYMS:
            assert not refused and not permitted, (
                f"{action!r} from {state!r} is a documented synonym: legal, deliberately "
                f"not offered")
            return
        assert refused == (not permitted), (
            f"{action!r} from {state!r}: the table says permitted={permitted} but the "
            f"service {'refused' if refused else 'accepted'} it")

    def test_the_matrix_is_what_an_operator_is_offered(self):
        assert pa.permitted_transitions(pa.STAGED) == ("activate", "retire")
        assert pa.permitted_transitions(pa.PAPER_ACTIVE) == ("pause", "retire")
        assert pa.permitted_transitions(pa.PAUSED) == ("resume", "retire")
        assert pa.permitted_transitions(pa.RETIRED) == ()
        assert pa.permitted_transitions("nonsense") == ()

    def test_retirement_is_terminal_and_offers_no_resurrection(self):
        assert pa.permitted_transitions(pa.RETIRED) == ()
        for action in ("activate", "resume", "pause", "retire"):
            assert action not in pa.permitted_transitions(pa.RETIRED)

    def test_paper_retirement_declares_its_rollback_argument(self):
        """Retiring paper authority must name where authority returns. A contract that
        presented it as a bare button would be lying to whoever pressed it."""
        assert pa.transition_requirements("retire") == ("restore_strategy_key",)
        for action in ("activate", "pause", "resume"):
            assert pa.transition_requirements(action) == ()

    def test_the_two_planes_are_not_conflated(self):
        """Paper and shadow look alike and are not: shadow retirement hands nothing back."""
        from app.core import shadow_deployments as sd

        assert sd.transition_requirements("retire") == ()
        assert pa.transition_requirements("retire") == ("restore_strategy_key",)
        assert pa.PAPER_ACTIVE not in sd.TRANSITIONS
        assert sd.SHADOW_ACTIVE not in pa.TRANSITIONS
