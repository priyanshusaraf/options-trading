"""A managed shadow deployment may name an exact graph. It may never execute one.

L1.2 canonicalised execution selection authority; L1.2b canonicalised execution
attribution; L1.3A makes the IR shadow pairing a **server-owned record** instead of runtime
machinery. At the end of it the platform can state, durably and with lineage:

    this approved immutable graph version is deployed to this instrument at this interval
    in shadow mode, with this evidence and this admission state

and it remains structurally unable to state that the graph may influence an order.

Two properties carry the slice, and both are asserted here rather than described:

* **Lineage is verified, not declared.** Activation re-derives the graph's content address
  from its stored bytes and re-checks the research decision through the read-only bridge.
  A row that merely *claims* a content address is a row that stops being true the moment
  anything moves underneath it.
* **Authority is refused at three independent layers.** `AUTHORITY_BY_SOURCE` (ADR 0012),
  a CHECK constraint the database will not widen, and the service's own refusal to write
  any mode but `shadow`. Any one of them alone would be a convention.
"""
from __future__ import annotations

import datetime as dt
import json

import pytest
from sqlalchemy.exc import IntegrityError

from app.core import shadow_deployments as sd
from app.db.models import (
    LEGACY_DEPLOYMENT_ID,
    GraphArtifact,
    GraphVersion,
    IrShadowDeployment,
    Project,
)
from app.db.session import SessionLocal, init_db
from app.ir.hashing import canonical_json, content_address
from tests.legacy_money_scope import LegacyMoneyScope

sd = LegacyMoneyScope(
    sd, "stage", "activate", "pause", "resume", "retire", "active_bindings",
    "listing")

PROJECT = "proj-shadow"
#: The real mirror artefact, not a stub. Admission resolves the graph to read its declared
#: warmup, so a hand-rolled placeholder would fail resolution — and a test that worked
#: around that with a fake warmup would be asserting a number it invented.
GRAPH = "strategy.expanding_z_impulse"
#: MCX: a 09:00–23:30 session, so a 302-bar warmup is admissible at 30 minutes. Chosen
#: deliberately — an NSE name on the same interval cannot settle, and a test that silently
#: used one would be asserting the admission contract's *refusal* while claiming to test
#: activation.
INSTRUMENT = "SILVERM"
INTERVAL = "30minute"


def _graph_document(version: int = 1) -> dict:
    """The shipped `expanding_z` mirror, restamped to the version under test."""
    from app.ir.strategies.expanding_z import GRAPH as DOCUMENT

    return {**DOCUMENT, "version": version}


def seed_graph(session, version: int = 1) -> GraphVersion:
    from app.core import strategy_admissions
    from app.ir.library import REGISTRY
    from app.strategy.admission import IRGraphAdmissionInput, admit_strategy

    if session.get(Project, PROJECT) is None:
        session.add(Project(project_id=PROJECT, owner_id="owner", name="shadow"))
    if session.get(GraphArtifact, ("owner", GRAPH)) is None:
        session.add(GraphArtifact(owner_id="owner", identifier=GRAPH, project_id=PROJECT,
                                  display_name="mirror", draft_json="{}",
                                  draft_revision=0))
    session.flush()
    document = _graph_document(version)
    decision = admit_strategy(
        owner_id="owner",
        source_input=IRGraphAdmissionInput(graph=document, parameters={}, risk_model=None),
        registry=REGISTRY,
    )
    assert decision.artifact is not None
    strategy_admissions.put(session, decision.artifact)
    row = GraphVersion(owner_id="owner", graph_identifier=GRAPH, version=version,
                       artifact_json=canonical_json(document),
                       content_address=content_address(document),
                       admission_address=decision.artifact.admission_address)
    session.add(row)
    session.flush()
    return row


def approved_evidence(**overrides):
    """A verified research decision, as the read-only bridge would report it."""
    version = overrides.get("graph_version", 1)
    return {"run_id": 7, "candidate_id": 3, "project_id": PROJECT,
            "graph_identifier": GRAPH, "graph_version": version,
            "content_address": content_address(_graph_document(version)),
            "admission_address": _admission_address(version), "decision": "approved",
            **overrides}


def _admission_address(version: int) -> str:
    from tests.admitted_entry import admitted_artifact

    return admitted_artifact(
        graph=_graph_document(version), owner_id="owner").admission_address


@pytest.fixture(autouse=True)
def evidence_bridge(monkeypatch):
    """Stub the read-only research bridge.

    The approval lineage lives in the research plane's own database — isolated by hard
    invariant 5 — so these tests state what the bridge returns rather than reaching across
    to write it. What is under test here is what the service *does* with a verdict, and
    that is exactly what a stub can express honestly.
    """
    #: Sentinel rather than None, so a test can state "there is no approval" and be
    #: distinguishable from "nobody set an expectation".
    verdicts = {"value": "approve-what-is-asked"}

    def bridge(**asked):
        if verdicts["value"] != "approve-what-is-asked":
            return verdicts["value"]
        return approved_evidence(graph_version=asked["graph_version"])

    monkeypatch.setattr(sd, "verified_decision", bridge)
    return verdicts


def setup_function() -> None:
    init_db(reset=True)


def stage(session, **overrides):
    return sd.stage(
        session, project_id=overrides.pop("project_id", PROJECT),
        graph_identifier=overrides.pop("graph_identifier", GRAPH),
        graph_version=overrides.pop("graph_version", 1),
        deployment_id=overrides.pop("deployment_id", LEGACY_DEPLOYMENT_ID),
        instrument_key=overrides.pop("instrument_key", INSTRUMENT),
        interval=overrides.pop("interval", INTERVAL), **overrides)


def staged(session, **overrides):
    seed_graph(session, overrides.get("graph_version", 1))
    return stage(session, **overrides)


def staged_without_local_receipt(session):
    """A valid staged binding whose only missing authority is its local receipt."""
    if session.get(Project, PROJECT) is None:
        session.add(Project(project_id=PROJECT, owner_id="owner", name="shadow"))
    if session.get(GraphArtifact, ("owner", GRAPH)) is None:
        session.add(GraphArtifact(owner_id="owner", identifier=GRAPH, project_id=PROJECT,
                                  display_name="mirror", draft_json="{}",
                                  draft_revision=0))
    document = _graph_document()
    session.add(GraphVersion(
        owner_id="owner", graph_identifier=GRAPH, version=1,
        artifact_json=canonical_json(document), content_address=content_address(document),
        admission_address="sha256:" + "b" * 64))
    session.flush()
    row = stage(session)
    session.commit()
    return row


# ── the record says what it is ──────────────────────────────────────────────────

def test_a_staged_deployment_carries_every_identity_separately():
    """Nine facts, nine columns. Collapsing any of them into the strategy key is how one
    layer ends up asserting another's fact — the defect class this project keeps hitting."""
    with SessionLocal() as session:
        row = staged(session)
        session.commit()

        assert row.project_id == PROJECT
        assert (row.graph_identifier, row.graph_version) == (GRAPH, 1)
        assert row.graph_content_address == content_address(_graph_document(1))
        assert row.deployment_id == LEGACY_DEPLOYMENT_ID
        assert row.instrument_key == INSTRUMENT
        assert row.interval == INTERVAL
        assert row.strategy_key == f"ir.{GRAPH}"
        assert row.runtime_source == "ir_graph"
        assert row.execution_mode == "shadow"
        assert row.authority == "non_authoritative"
        assert row.state == sd.STAGED
        # The stable key cannot identify the build: it survives an edit, which is the
        # whole reason the version and the address are separate columns.
        assert str(row.graph_version) not in row.strategy_key


def test_shadow_activation_refuses_a_missing_local_causal_receipt(evidence_bridge):
    """Hypothesis: a graph address alone can grant new shadow evaluation authority."""
    with SessionLocal() as session:
        row = staged_without_local_receipt(session)
        evidence_bridge["value"] = approved_evidence(admission_address=row.admission_address)
        with pytest.raises(sd.NotAdmissible, match="RECEIPT_STALE"):
            sd.activate(session, row.id, revision=row.revision)


def test_shadow_activate_receipt_bypass_mutant_is_killed(monkeypatch, evidence_bridge):
    """Removing only activation's local receipt check admits forged evidence."""
    with SessionLocal() as session:
        row = staged_without_local_receipt(session)
        row.admission_address = "sha256:" + "a" * 64
        evidence_bridge["value"] = approved_evidence(admission_address=row.admission_address)
        # History admission is already proven elsewhere. Keep this mutation focused on
        # the receipt guard instead of letting a test-environment history shortfall
        # mask the forged receipt.
        service = __import__("app.core.shadow_deployments", fromlist=["*"])
        monkeypatch.setattr(
            service, "_admission_for",
            lambda *_args, **_kwargs: __import__("types").SimpleNamespace(ok=True, reason=""))
        monkeypatch.setattr(service, "_require_local_receipt", lambda *_args, **_kwargs: None)
        with pytest.raises(pytest.fail.Exception):
            with pytest.raises(sd.NotAdmissible, match="RECEIPT_STALE"):
                sd.activate(session, row.id, revision=row.revision)


def test_shadow_resume_receipt_bypass_mutant_is_killed(monkeypatch, evidence_bridge):
    """Removing only resume's shared activation receipt check admits stale state."""
    with SessionLocal() as session:
        row = staged_without_local_receipt(session)
        row.state = sd.PAUSED
        session.commit()
        evidence_bridge["value"] = approved_evidence(admission_address=row.admission_address)
        service = __import__("app.core.shadow_deployments", fromlist=["*"])
        monkeypatch.setattr(
            service, "_admission_for",
            lambda *_args, **_kwargs: __import__("types").SimpleNamespace(ok=True, reason=""))
        monkeypatch.setattr(service, "_require_local_receipt", lambda *_args, **_kwargs: None)
        with pytest.raises(pytest.fail.Exception):
            with pytest.raises(sd.NotAdmissible, match="RECEIPT_STALE"):
                sd.resume(session, row.id, revision=row.revision)


def test_the_strategy_key_is_never_the_graph_identity():
    with SessionLocal() as session:
        first = staged(session)
        session.commit()
        seed_graph(session, 2)
        second = sd.stage(session, project_id=PROJECT, graph_identifier=GRAPH,
                          graph_version=2, deployment_id=LEGACY_DEPLOYMENT_ID,
                          instrument_key="GOLDM", interval=INTERVAL)
        session.commit()
        assert first.strategy_key == second.strategy_key
        assert first.graph_content_address != second.graph_content_address


# ── lifecycle ───────────────────────────────────────────────────────────────────

def test_staged_activates_to_shadow_active():
    with SessionLocal() as session:
        row = staged(session)
        session.commit()
        activated = sd.activate(session, row.id, revision=row.revision)
        session.commit()
        assert activated.state == sd.SHADOW_ACTIVE
        assert activated.revision == 1
        assert activated.admission_ok is True
        assert activated.evidence_verified_at is not None


def test_an_active_deployment_pauses_and_resumes():
    with SessionLocal() as session:
        row = staged(session)
        session.commit()
        row = sd.activate(session, row.id, revision=row.revision)
        row = sd.pause(session, row.id, revision=row.revision)
        assert row.state == sd.PAUSED
        row = sd.resume(session, row.id, revision=row.revision)
        assert row.state == sd.SHADOW_ACTIVE


def test_retirement_is_terminal():
    """Reversible where appropriate — and retirement is where it is not. A retired binding
    that could be revived would let a graph nobody re-approved come back after a restart."""
    with SessionLocal() as session:
        row = staged(session)
        session.commit()
        row = sd.activate(session, row.id, revision=row.revision)
        row = sd.retire(session, row.id, revision=row.revision)
        assert row.state == sd.RETIRED
        with pytest.raises(sd.IllegalTransition):
            sd.resume(session, row.id, revision=row.revision)
        with pytest.raises(sd.IllegalTransition):
            sd.activate(session, row.id, revision=row.revision)


def test_a_stale_revision_is_rejected():
    """Two operators, one binding. Without this the second silently overwrites the first."""
    with SessionLocal() as session:
        row = staged(session)
        session.commit()
        sd.activate(session, row.id, revision=row.revision)
        with pytest.raises(sd.RevisionConflict):
            sd.pause(session, row.id, revision=0)


def test_activating_twice_is_refused_rather_than_duplicated():
    with SessionLocal() as session:
        row = staged(session)
        session.commit()
        active = sd.activate(session, row.id, revision=row.revision)
        with pytest.raises(sd.IllegalTransition):
            sd.activate(session, active.id, revision=active.revision)


def test_two_live_bindings_for_one_instrument_and_interval_are_refused():
    """One evaluator per (deployment, instrument, interval). Two would double-count every
    observation and make the agreement rate meaningless."""
    with SessionLocal() as session:
        staged(session)
        session.commit()
        seed_graph(session, 2)
        with pytest.raises(IntegrityError):
            stage(session, graph_version=2)
            session.commit()


def test_retiring_frees_the_slot_without_deleting_the_history():
    with SessionLocal() as session:
        first = staged(session)
        session.commit()
        sd.retire(session, first.id, revision=first.revision)
        session.commit()
        seed_graph(session, 2)
        second = stage(session, graph_version=2)
        session.commit()
        assert second.id != first.id
        assert session.get(IrShadowDeployment, first.id).state == sd.RETIRED


# ── verification: lineage is checked, not believed ──────────────────────────────

def test_activation_reverifies_the_graph_content_address():
    """The row records an address; activation re-derives it from the stored bytes. A
    binding that only ever believed its own column would keep claiming a graph it no
    longer names."""
    with SessionLocal() as session:
        row = staged(session)
        row.graph_content_address = "sha256:" + "0" * 64
        session.flush()
        with pytest.raises(sd.BindingUnverifiable) as raised:
            sd.activate(session, row.id, revision=row.revision)
    assert "content address" in str(raised.value).lower()


def test_naming_a_graph_version_that_does_not_exist_fails_closed():
    """Staging cannot reference an artefact nobody minted. Deleting one out from under a
    live binding is a different question and the database already answers it: the foreign
    key is RESTRICT and `graph_versions` is immutable by trigger."""
    with SessionLocal() as session:
        seed_graph(session, 1)
        with pytest.raises(sd.BindingUnverifiable) as raised:
            stage(session, graph_version=99)
    assert "99" in str(raised.value)


def test_activation_without_evidence_is_refused(evidence_bridge):
    evidence_bridge["value"] = None
    with SessionLocal() as session:
        row = staged(session)
        session.commit()
        with pytest.raises(sd.EvidenceUnverified):
            sd.activate(session, row.id, revision=row.revision)


def test_evidence_for_a_different_graph_version_is_refused(evidence_bridge):
    """The lineage has to be about *this* artefact. Approval of version 1 is not approval
    of version 2, and an edit is always a new version."""
    evidence_bridge["value"] = approved_evidence(graph_version=2)
    with SessionLocal() as session:
        row = staged(session)
        session.commit()
        with pytest.raises(sd.EvidenceUnverified):
            sd.activate(session, row.id, revision=row.revision)


def test_evidence_from_a_different_project_is_refused(evidence_bridge):
    evidence_bridge["value"] = approved_evidence(project_id="someone-elses-project")
    with SessionLocal() as session:
        row = staged(session)
        session.commit()
        with pytest.raises(sd.EvidenceUnverified):
            sd.activate(session, row.id, revision=row.revision)


def test_a_rejected_decision_is_not_an_approval(evidence_bridge):
    evidence_bridge["value"] = approved_evidence(decision="rejected")
    with SessionLocal() as session:
        row = staged(session)
        session.commit()
        with pytest.raises(sd.EvidenceUnverified):
            sd.activate(session, row.id, revision=row.revision)


def test_an_unknown_instrument_is_refused():
    with SessionLocal() as session:
        seed_graph(session)
        with pytest.raises(sd.BindingUnverifiable):
            stage(session, instrument_key="NOT_A_REAL_INSTRUMENT")


def test_an_interval_that_can_never_settle_the_warmup_is_refused_at_activation():
    """The Stage 1 admission contract, consulted before activation rather than discovered
    once per scan. NIFTY at 30 minutes cannot reach a 302-bar warmup on the configured
    history, and that is knowable from configuration alone."""
    with SessionLocal() as session:
        row = staged(session, instrument_key="NIFTY")
        session.commit()
        with pytest.raises(sd.NotAdmissible) as raised:
            sd.activate(session, row.id, revision=row.revision)
        assert row.admission_ok is False
        assert "warmup" in str(raised.value).lower() or "bars" in str(raised.value).lower()


def test_a_graph_edit_does_not_mutate_an_existing_deployment():
    """Requirement 9. A new version is a new artefact; the live binding keeps naming the
    one that was approved, and adopting the new one is a deliberate act."""
    with SessionLocal() as session:
        row = staged(session)
        session.commit()
        row = sd.activate(session, row.id, revision=row.revision)
        session.commit()
        before = (row.graph_version, row.graph_content_address, row.revision)

        seed_graph(session, 2)          # the edit
        session.commit()

        reloaded = session.get(IrShadowDeployment, row.id)
        assert (reloaded.graph_version, reloaded.graph_content_address,
                reloaded.revision) == before


# ── authority is refused by the schema, not only by the service ─────────────────

def test_the_database_refuses_any_mode_but_shadow():
    """ADR 0012 §3.2 reserves paper authority to the owner. This is the lock on that door:
    a route, a data fix or a mistaken service call cannot widen a CHECK constraint — only
    a reviewed schema change can."""
    with SessionLocal() as session:
        row = staged(session)
        session.commit()
        row.execution_mode = "paper"
        with pytest.raises(IntegrityError):
            session.commit()


def test_the_database_refuses_any_authority_but_non_authoritative():
    with SessionLocal() as session:
        row = staged(session)
        session.commit()
        row.authority = "authoritative"
        with pytest.raises(IntegrityError):
            session.commit()


def test_the_service_writes_exactly_one_source_and_mode_pair():
    """`ir_graph + shadow` is the only permitted pair, and the service has no parameter
    that could express another. A mode argument is how the next slice's owner decision
    gets made accidentally."""
    import inspect

    for name in ("stage", "activate", "resume"):
        parameters = set(inspect.signature(getattr(sd, name)).parameters)
        assert not parameters & {"mode", "execution_mode", "authority", "source"}, name


# ── restart ─────────────────────────────────────────────────────────────────────

def test_only_active_bindings_are_reloaded():
    with SessionLocal() as session:
        active = staged(session)
        session.commit()
        sd.activate(session, active.id, revision=active.revision)

        seed_graph(session, 2)
        second = stage(session, graph_version=2, instrument_key="GOLDM")
        session.commit()
        second = sd.activate(session, second.id, revision=second.revision)
        sd.pause(session, second.id, revision=second.revision)

        seed_graph(session, 3)
        third = stage(session, graph_version=3, instrument_key="COPPERM")
        session.commit()
        third = sd.activate(session, third.id, revision=third.revision)
        sd.retire(session, third.id, revision=third.revision)
        session.commit()

        loaded = sd.active_bindings(session)
        assert [b.instrument_key for b in loaded] == [INSTRUMENT]


def test_reload_reverifies_and_drops_a_binding_whose_graph_moved():
    """Requirement: missing graph state disables the deployment *visibly*. Verification at
    activation alone would be a claim about the past."""
    with SessionLocal() as session:
        row = staged(session)
        session.commit()
        sd.activate(session, row.id, revision=row.revision)
        session.commit()
        assert len(sd.active_bindings(session)) == 1

        session.get(IrShadowDeployment, row.id).graph_content_address = (
            "sha256:" + "1" * 64)
        session.flush()

        problems: list = []
        assert sd.active_bindings(session, on_problem=problems.append) == []
        assert problems and "content address" in problems[0].lower()


def test_reload_drops_a_binding_with_a_missing_local_receipt():
    """Hypothesis: a previous activation lets a deleted receipt survive reload."""
    with SessionLocal() as session:
        row = staged(session)
        session.commit()
        sd.activate(session, row.id, revision=row.revision)
        session.commit()
        row = session.get(IrShadowDeployment, row.id)
        row.admission_address = "sha256:" + "b" * 64
        session.flush()

        problems: list[str] = []
        assert sd.active_bindings(session, on_problem=problems.append) == []
        assert problems and "RECEIPT_STALE" in problems[0]


def test_shadow_refuses_evidence_without_an_admission_address(evidence_bridge):
    """Hypothesis: a research approval can omit the exact causal receipt."""
    with SessionLocal() as session:
        row = staged(session)
        session.commit()
        evidence_bridge["value"] = approved_evidence(admission_address=None)
        with pytest.raises(sd.EvidenceUnverified, match="admission"):
            sd.activate(session, row.id, revision=row.revision)


def test_a_reloaded_binding_carries_its_verified_identity():
    with SessionLocal() as session:
        row = staged(session)
        session.commit()
        sd.activate(session, row.id, revision=row.revision)
        session.commit()

        binding = sd.active_bindings(session)[0]
        assert binding.graph_identifier == GRAPH
        assert binding.graph_version == 1
        assert binding.content_address == content_address(_graph_document(1))
        assert binding.strategy_key == f"ir.{GRAPH}"
        assert binding.execution_mode == "shadow"
        assert binding.authority == "non_authoritative"
        assert binding.interval == INTERVAL


def test_the_reloaded_binding_type_exposes_no_way_to_execute():
    """A dataclass the engine holds every tick. If it carried a Strategy the entry paths
    could reach, "non-authoritative" would be a naming convention."""
    import dataclasses

    with SessionLocal() as session:
        row = staged(session)
        session.commit()
        sd.activate(session, row.id, revision=row.revision)
        session.commit()
        binding = sd.active_bindings(session)[0]

    fields = {f.name for f in dataclasses.fields(binding)}
    assert not fields & {"strategy", "broker", "adapter", "signals", "order"}
    assert dataclasses.is_dataclass(binding) and binding.__dataclass_params__.frozen


def test_a_verified_evidence_envelope_is_recorded_not_recomputed_on_every_reload():
    """Reload re-verifies the *graph*, which is local and cheap. It does not re-open the
    research database on a control-loop boundary; the verified lineage was recorded at
    activation and the row states when."""
    with SessionLocal() as session:
        row = staged(session)
        session.commit()
        sd.activate(session, row.id, revision=row.revision)
        session.commit()

        calls = []
        original = sd.verified_decision
        try:
            sd.verified_decision = lambda **kw: calls.append(kw) or approved_evidence()
            sd.active_bindings(session)
        finally:
            sd.verified_decision = original
        assert calls == []
        assert session.get(IrShadowDeployment, row.id).evidence_run_id == 7


class TestPermittedTransitions:
    """The shadow plane's capability table, proven against its own guards.

    Deliberately a separate table from `paper_authority`'s, and this is where that pays:
    the states differ (`shadow_active`, not `paper_active`) and retirement here hands
    nothing back, so a shared table would have to over-promise on one plane.
    """

    SYNONYMS = {(sd.PAUSED, "activate")}      # `resume` names the same transition

    def setup_method(self) -> None:
        # `setup_function` above applies to module-level tests only, not to methods.
        init_db(reset=True)

    def _row_in(self, session, state: str):
        row = staged(session)
        session.commit()
        if state == sd.STAGED:
            return row
        sd.activate(session, row.id, revision=row.revision)
        session.commit()
        if state == sd.SHADOW_ACTIVE:
            return row
        sd.pause(session, row.id, revision=row.revision)
        session.commit()
        if state == sd.PAUSED:
            return row
        sd.retire(session, row.id, revision=row.revision)
        session.commit()
        return row

    @pytest.mark.parametrize("state", sd.STATES)
    @pytest.mark.parametrize("action", ("activate", "pause", "resume", "retire"))
    def test_the_table_agrees_with_the_guards(self, state, action):
        with SessionLocal() as s:
            row = self._row_in(s, state)
            permitted = action in sd.permitted_transitions(state)
            try:
                getattr(sd, action)(s, row.id, revision=row.revision)
                refused = False
            except sd.IllegalTransition:
                refused = True
            s.rollback()

        if (state, action) in self.SYNONYMS:
            assert not refused and not permitted
            return
        assert refused == (not permitted), (
            f"{action!r} from {state!r}: table says permitted={permitted}, service "
            f"{'refused' if refused else 'accepted'}")

    def test_the_matrix(self):
        assert sd.permitted_transitions(sd.STAGED) == ("activate", "retire")
        assert sd.permitted_transitions(sd.SHADOW_ACTIVE) == ("pause", "retire")
        assert sd.permitted_transitions(sd.PAUSED) == ("resume", "retire")
        assert sd.permitted_transitions(sd.RETIRED) == ()

    def test_shadow_retirement_needs_no_rollback_target(self):
        assert sd.transition_requirements("retire") == ()
