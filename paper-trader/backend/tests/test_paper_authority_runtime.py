"""L1.4 — paper-authority runtime hardening.

L1.3C proved a graph *may* author a paper signal and that the identity stamped on the money
record is the approved one. This slice asks the next question, and it is an operational one:

> does exact-version IR paper authority stay deterministic, isolated, attributable and
> recoverable **through failure and recovery**, not just on the happy path?

The conditions covered here are the ones an operator actually creates — a restart, a
retirement mid-session, a pause with a position still open, a disarm, a refused entry, a
broker that raises. Every test is deterministic: positions are constructed directly rather
than waited for, and no test depends on the mock feed admitting a fill on a particular bar.

**Two invariants dominate and are worth stating before the tests.**

*Hard invariant 2 — ARM gates entries, never exits.* A position a graph opened must keep
being marked and exited after the deployment that authored it is paused, retired or refused.
Authority is about who may *open*; nothing may make a position unexitable, and
`paper_authority.pause`'s docstring already claims this. A claim in a docstring is not a
proof, so it is proven here.

*Authority is a property of the current tick.* Withdrawing authority must also withdraw the
signal it already produced. `scan_signals` learned this in L1.2b for `AuthorityNotGranted`;
`refresh_paper_authority` is the other door into the same hazard and did not, which is the
defect this slice found (see `TestStaleBindingWithdrawal`).
"""
from __future__ import annotations

import datetime as dt

import pytest

from app.core import paper_authority as pa
from app.core.execution_book import LIVE, PAPER
from app.db.models import (
    LEGACY_DEPLOYMENT_ID,
    GraphArtifact,
    GraphVersion,
    IrPaperDeployment,
    Position,
    Project,
)
from app.db.session import SessionLocal, init_db
from app.engine.runner import EngineRunner
from app.ir.hashing import canonical_json, content_address

PROJECT = "proj-paper-runtime"
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
    """The research read, stated as a verdict. `verified_decision` is the single door
    through the isolation boundary (hard invariant 5), so stating it here is what keeps
    these tests from reaching across the plane."""
    state = {"decision": "approved"}

    def bridge(**asked):
        return {"run_id": 7, "candidate_id": 3, "project_id": PROJECT,
                "graph_identifier": GRAPH, "graph_version": asked["graph_version"],
                # Content, not name: the admission binding requires the approved
                # address to be the address receiving authority.
                "content_address": content_address(_graph_document(asked["graph_version"])),
                "decision": state["decision"]}

    monkeypatch.setattr(pa, "verified_decision", bridge)
    return state


@pytest.fixture(autouse=True)
def a_clean_registry():
    from app.strategy.registry import _REGISTRY

    before = dict(_REGISTRY)
    yield
    _REGISTRY.clear()
    _REGISTRY.update(before)


def _deploy(session, *, version: int = 1, activate: bool = True) -> IrPaperDeployment:
    if session.get(Project, PROJECT) is None:
        session.add(Project(project_id=PROJECT, name="paper"))
    if session.get(GraphArtifact, GRAPH) is None:
        session.add(GraphArtifact(identifier=GRAPH, project_id=PROJECT,
                                  display_name="mirror", draft_json="{}",
                                  draft_revision=0))
    session.flush()
    document = _graph_document(version)
    session.add(GraphVersion(graph_identifier=GRAPH, version=version,
                             artifact_json=canonical_json(document),
                             content_address=content_address(document)))
    session.flush()
    row = pa.stage(session, project_id=PROJECT, graph_identifier=GRAPH,
                   graph_version=version, deployment_id=LEGACY_DEPLOYMENT_ID,
                   instrument_key=INSTRUMENT, interval=INTERVAL)
    session.commit()
    if activate:
        pa.activate(session, row.id, revision=row.revision)
        session.commit()
    return row


def _runner() -> EngineRunner:
    r = EngineRunner()
    r.refresh_paper_authority()
    return r


def _open_paper_position(session, *, strategy_version: str, key: str = IR_KEY) -> int:
    """A position exactly as a paper fill leaves it. Constructed rather than traded, so no
    test here depends on the mock feed admitting an entry on a particular bar."""
    row = Position(
        instrument_key=INSTRUMENT, direction="LONG", option_type="EQ",
        tradingsymbol=f"{INSTRUMENT}-EQ", exchange="MCX", segment="equity_intraday",
        strike=0.0, expiry=dt.date(2030, 1, 1), qty=1, lot_size=1,
        entry_premium=100.0, entry_charges=0.0, entry_cost=100.0, entry_spot=100.0,
        entry_time=dt.datetime(2026, 1, 1, 10, 0), stop_price=99.0, target_price=101.0,
        high_water_premium=100.0, last_premium=100.0, mfe=0.0, mae=0.0,
        mode=PAPER, deployment_id=LEGACY_DEPLOYMENT_ID,
        strategy_key=key, strategy_version=strategy_version)
    session.add(row)
    session.commit()
    return row.id


def _publish(r, binding=None):
    """One authored entry signal, through the door the engine actually uses."""
    r.publish_signal(INSTRUMENT, binding or r._binding_for(INSTRUMENT), {
        "signal": "LONG_ENTRY", "z": 2.0, "slope": 1.0, "close": 100.0,
        "long_exit": False, "short_exit": False})


# ── recovery ────────────────────────────────────────────────────────────────────

class TestRestartAndReload:
    """A restart is the boundary where a deployment is reconstructed from the database
    alone. Nothing may be inherited from the dead process."""

    def test_restart_reloads_the_exact_content_address_not_merely_the_graph_name(self):
        with SessionLocal() as s:
            row = _deploy(s)
            approved = row.graph_content_address
        r = _runner()
        try:
            binding = r.paper_authority[INSTRUMENT]
            assert binding.content_address == approved
            assert binding.graph_identifier == GRAPH
            assert binding.graph_version == 1
            assert binding.execution_mode == PAPER
            assert binding.authority == "authoritative"
        finally:
            r.broker.close()

    def test_the_reloaded_adapter_resolves_to_the_approved_bytes(self):
        """The address is re-derived from the stored artefact at reload — the second of the
        three checks. A registry entry that resolved to different bytes would make
        attribution a lie while every identity column still looked right."""
        from app.strategy.registry import resolve_strategy

        with SessionLocal() as s:
            row = _deploy(s)
            approved = row.graph_content_address
        r = _runner()
        try:
            assert resolve_strategy(IR_KEY).version == approved
        finally:
            r.broker.close()

    def test_the_graph_bytes_cannot_move_under_an_active_deployment(self):
        """The first line of defence is the database's, and it must be confirmed before the
        reload check below can be called defence in depth rather than the only defence."""
        from sqlalchemy.exc import IntegrityError

        with SessionLocal() as s:
            _deploy(s)
            with pytest.raises(IntegrityError, match="immutable"):
                s.query(GraphVersion).filter_by(graph_identifier=GRAPH, version=1).update(
                    {"artifact_json": canonical_json(
                        {**_graph_document(1), "notes": "edited"})})
                s.commit()

    def test_a_deployment_whose_recorded_address_disagrees_is_dropped_and_reported(self):
        """Graph bytes are immutable, so the reachable disagreement comes from the other
        side: a row whose recorded address is not what the artefact hashes to — a bad
        restore, a hand-edited row, a future writer with a bug."""
        with SessionLocal() as s:
            _deploy(s)
        with SessionLocal() as s:
            s.query(IrPaperDeployment).update(
                {"graph_content_address": "sha256:" + "0" * 64})
            s.commit()
        r = _runner()
        try:
            assert INSTRUMENT not in r.paper_authority
            assert r.paper_authority_problems, \
                "a dropped binding must be reported; a silent drop is a silent substitution"
        finally:
            r.broker.close()

    def test_attribution_survives_a_restart_unchanged(self):
        """Safety proof: the identity on a money record written before the restart still
        names the artefact the reloaded deployment approves."""
        with SessionLocal() as s:
            row = _deploy(s)
            approved = row.graph_content_address
            _open_paper_position(s, strategy_version=approved)
        r = _runner()
        try:
            with SessionLocal() as s:
                pos = s.query(Position).filter_by(instrument_key=INSTRUMENT).one()
                assert pos.strategy_key == IR_KEY
                assert pos.strategy_version == approved
                assert pos.strategy_version == r.paper_authority[INSTRUMENT].content_address
        finally:
            r.broker.close()

    def test_a_deployment_cannot_name_a_graph_version_that_does_not_exist(self):
        """The other database-level guarantee this slice depends on. A dangling deployment
        is not a state a partial restore can reach, because the foreign key refuses it —
        so "the row survived and the artefact did not" needs no runtime handling."""
        from sqlalchemy.exc import IntegrityError

        with SessionLocal() as s:
            _deploy(s)
            with pytest.raises(IntegrityError, match="FOREIGN KEY"):
                s.query(IrPaperDeployment).update({"graph_version": 99})
                s.commit()

    def test_one_unbuildable_binding_does_not_take_the_others_down(self):
        """Partial recovery, in the shape that *is* reachable: one deployment cannot be
        rebuilt and the rest must still load, with the failure reported rather than
        swallowed."""
        problems: list[str] = []
        with SessionLocal() as s:
            _deploy(s)
        with SessionLocal() as s:
            loaded = pa.register_active_adapters(s, on_problem=problems.append)
            assert len(loaded) == 1 and not problems

        def refuse(session, binding):
            raise pa.BindingUnverifiable("cannot rebuild")

        with SessionLocal() as s:
            import app.core.paper_authority as module
            original, module.adapter_for = module.adapter_for, refuse
            try:
                loaded = module.register_active_adapters(s, on_problem=problems.append)
            finally:
                module.adapter_for = original
        assert loaded == []
        assert problems and "cannot rebuild" in problems[0]

    def test_a_failed_refresh_does_not_silently_widen_authority(self):
        """If the reload itself throws, the engine keeps the map it had and says so. It
        must never end up with authority it did not verify this pass."""
        with SessionLocal() as s:
            _deploy(s)
        r = _runner()
        try:
            before = dict(r.paper_authority)
            import app.core.paper_authority as module
            original = module.register_active_adapters
            module.register_active_adapters = lambda *a, **k: (_ for _ in ()).throw(
                RuntimeError("database gone"))
            try:
                assert r.refresh_paper_authority() == 0
            finally:
                module.register_active_adapters = original
            assert r.paper_authority == before, (
                "a failed refresh may keep what it verified last, but must not invent more")
        finally:
            r.broker.close()


# ── withdrawal ──────────────────────────────────────────────────────────────────

class TestStaleBindingWithdrawal:
    """**The defect this slice found.**

    `refresh_paper_authority` replaces the binding map, but the signal a *previous* scan
    published survives in `self.state`, and `self.executed_binding` still holds the binding
    that produced it. `process_entries` opens from `self.state` and attributes from
    `self.executed_binding` — so between an operator retiring a deployment and the next
    scan, an entry could open on a withdrawn graph's signal and stamp the withdrawn graph's
    identity on the money record.

    This is exactly the hazard L1.2b closed in `scan_signals`, arriving through the other
    door. The fix is the same one: withdrawing authority withdraws the signal it produced.
    """

    def test_retiring_a_deployment_withdraws_the_signal_it_already_authored(self):
        with SessionLocal() as s:
            row = _deploy(s)
        r = _runner()
        try:
            _publish(r)
            assert r._executed_binding(INSTRUMENT).strategy_key == IR_KEY

            with SessionLocal() as s:
                current = s.get(IrPaperDeployment, row.id)
                pa.retire(s, current.id, revision=current.revision,
                          restore_strategy_key=None)
                s.commit()
            r.refresh_paper_authority()

            assert INSTRUMENT not in r.paper_authority
            assert r.state.get(INSTRUMENT) is None, (
                "a retired deployment's signal must not survive into process_entries")
            assert r._executed_binding(INSTRUMENT) is None, (
                "a withdrawn binding must not still be available to attribute a fill")
        finally:
            r.broker.close()

    def test_pausing_a_deployment_withdraws_its_pending_signal_too(self):
        with SessionLocal() as s:
            row = _deploy(s)
        r = _runner()
        try:
            _publish(r)
            with SessionLocal() as s:
                current = s.get(IrPaperDeployment, row.id)
                pa.pause(s, current.id, revision=current.revision)
                s.commit()
            r.refresh_paper_authority()

            assert INSTRUMENT not in r.paper_authority
            assert r.state.get(INSTRUMENT) is None
            assert r._executed_binding(INSTRUMENT) is None
        finally:
            r.broker.close()

    def test_a_withdrawn_deployment_opens_no_position(self):
        """The consequence, end to end: after withdrawal an entry pass must produce no
        money record attributed to the graph."""
        with SessionLocal() as s:
            row = _deploy(s)
        r = _runner()
        try:
            r.armed = True
            _publish(r)
            with SessionLocal() as s:
                current = s.get(IrPaperDeployment, row.id)
                pa.retire(s, current.id, revision=current.revision,
                          restore_strategy_key=None)
                s.commit()
            r.refresh_paper_authority()
            r.process_entries()

            with SessionLocal() as s:
                assert s.query(Position).filter_by(strategy_key=IR_KEY).count() == 0
        finally:
            r.broker.close()

    def test_an_unaffected_instrument_keeps_its_signal(self):
        """Withdrawal is per instrument. Dropping the whole state map would be a different
        defect wearing the fix's clothes."""
        with SessionLocal() as s:
            row = _deploy(s)
        r = _runner()
        try:
            other = "GOLDM"
            _publish(r)
            r.publish_signal(other, r._binding_for(other), {
                "signal": "LONG_ENTRY", "z": 2.0, "slope": 1.0, "close": 100.0,
                "long_exit": False, "short_exit": False})
            with SessionLocal() as s:
                current = s.get(IrPaperDeployment, row.id)
                pa.retire(s, current.id, revision=current.revision,
                          restore_strategy_key=None)
                s.commit()
            r.refresh_paper_authority()

            assert r.state.get(INSTRUMENT) is None
            assert r.state.get(other) is not None
            assert r._executed_binding(other) is not None
        finally:
            r.broker.close()


# ── exit ownership: hard invariant 2 ────────────────────────────────────────────

class TestExitOwnershipSurvivesWithdrawal:
    """Not getting out is worse than any other failure. A position a graph opened must
    remain markable and exitable after its deployment stops being authoritative."""

    def _positions_seen_by_the_risk_lane(self, r):
        return [p.instrument_key for p in r.broker.open_positions()]

    def test_a_paused_deployments_position_is_still_managed(self):
        with SessionLocal() as s:
            row = _deploy(s)
            approved = row.graph_content_address
            _open_paper_position(s, strategy_version=approved)
        r = _runner()
        try:
            with SessionLocal() as s:
                current = s.get(IrPaperDeployment, row.id)
                pa.pause(s, current.id, revision=current.revision)
                s.commit()
            r.refresh_paper_authority()

            assert INSTRUMENT not in r.paper_authority, "authority must be gone"
            assert INSTRUMENT in self._positions_seen_by_the_risk_lane(r), (
                "hard invariant 2: the exit lane must still see a position whose author "
                "is no longer authoritative")
            r.mark_and_exit_positions()      # must not raise
        finally:
            r.broker.close()

    def test_a_retired_deployments_position_is_still_managed(self):
        with SessionLocal() as s:
            row = _deploy(s)
            approved = row.graph_content_address
            _open_paper_position(s, strategy_version=approved)
        r = _runner()
        try:
            with SessionLocal() as s:
                current = s.get(IrPaperDeployment, row.id)
                pa.retire(s, current.id, revision=current.revision,
                          restore_strategy_key=None)
                s.commit()
            r.refresh_paper_authority()

            assert INSTRUMENT in self._positions_seen_by_the_risk_lane(r)
            r.mark_and_exit_positions()
        finally:
            r.broker.close()

    def test_a_position_under_an_unverifiable_deployment_is_still_managed(self):
        """The worst case: the deployment can no longer be verified, so nothing may open —
        and the position it already opened must still be exitable."""
        with SessionLocal() as s:
            row = _deploy(s)
            _open_paper_position(s, strategy_version=row.graph_content_address)
        with SessionLocal() as s:
            s.query(IrPaperDeployment).update(
                {"graph_content_address": "sha256:" + "0" * 64})
            s.commit()
        r = _runner()
        try:
            assert INSTRUMENT not in r.paper_authority
            assert INSTRUMENT in self._positions_seen_by_the_risk_lane(r)
            r.mark_and_exit_positions()
        finally:
            r.broker.close()

    def test_square_off_reaches_a_graph_opened_position(self):
        with SessionLocal() as s:
            row = _deploy(s)
            _open_paper_position(s, strategy_version=row.graph_content_address)
        r = _runner()
        try:
            closed = r._square_off_all("TEST_SQUAREOFF", r.provider.now())
            assert INSTRUMENT in closed
            with SessionLocal() as s:
                assert s.query(Position).filter_by(instrument_key=INSTRUMENT).count() == 0
        finally:
            r.broker.close()


# ── the kill switch ─────────────────────────────────────────────────────────────

class TestKillSwitchInteraction:
    def test_disarmed_means_no_entry_even_with_authority(self):
        with SessionLocal() as s:
            _deploy(s)
        r = _runner()
        try:
            r.armed = False
            _publish(r)
            r.process_entries()
            with SessionLocal() as s:
                assert s.query(Position).count() == 0
        finally:
            r.broker.close()

    def test_disarming_does_not_remove_authority(self):
        """Arm state and authority are different questions. Conflating them would make
        re-arming silently fail to restore the deployment."""
        with SessionLocal() as s:
            _deploy(s)
        r = _runner()
        try:
            r.armed = False
            assert INSTRUMENT in r.paper_authority
            assert r._binding_for(INSTRUMENT).origin == pa_origin()
        finally:
            r.broker.close()

    def test_disarmed_still_marks_and_exits(self):
        with SessionLocal() as s:
            row = _deploy(s)
            _open_paper_position(s, strategy_version=row.graph_content_address)
        r = _runner()
        try:
            r.armed = False
            r.mark_and_exit_positions()
            assert [p.instrument_key for p in r.broker.open_positions()] == [INSTRUMENT]
        finally:
            r.broker.close()


# ── refused and failed entries ──────────────────────────────────────────────────

class TestRefusedAndFailedEntries:
    def test_a_duplicate_signal_on_one_bar_cannot_open_twice(self):
        """`signal_already_evaluated` is keyed on the signal's bar. An IR-authored signal
        is subject to it exactly as a hand-written one is — the dedupe lives in
        `process_entries`, below the point where authorship stops mattering."""
        from app.engine.risk_controls import signal_already_evaluated

        with SessionLocal() as s:
            _deploy(s)
        r = _runner()
        try:
            r.armed = True
            bar = 1_800_000_000
            r.publish_signal(INSTRUMENT, r._binding_for(INSTRUMENT), {
                "signal": "LONG_ENTRY", "z": 2.0, "slope": 1.0, "close": 100.0,
                "time": bar, "long_exit": False, "short_exit": False})
            r.process_entries()
            first = r.last_entry_bar.get(INSTRUMENT)
            r.process_entries()
            assert r.last_entry_bar.get(INSTRUMENT) == first
            assert signal_already_evaluated(bar, first) or first is None
            with SessionLocal() as s:
                assert s.query(Position).filter_by(instrument_key=INSTRUMENT).count() <= 1
        finally:
            r.broker.close()

    def test_an_entry_that_raises_leaves_no_half_written_money_record(self):
        with SessionLocal() as s:
            _deploy(s)
        r = _runner()
        try:
            r.armed = True

            def explode(*a, **k):
                raise RuntimeError("venue refused")

            r.broker.open_equity_position = explode
            r.broker.open_position = explode
            _publish(r)
            try:
                r.process_entries()
            except RuntimeError:
                pass
            with SessionLocal() as s:
                assert s.query(Position).count() == 0
        finally:
            r.broker.close()

    def test_a_signal_with_no_binding_opens_nothing(self):
        """`publish_signal` is the only door precisely so this state is unreachable; the
        entry paths refuse it anyway, because a fill whose author is unknown is worse than
        a fill that never happened."""
        with SessionLocal() as s:
            _deploy(s)
        r = _runner()
        try:
            r.armed = True
            r.state[INSTRUMENT] = {"signal": "LONG_ENTRY", "z": 2.0, "slope": 1.0,
                                   "close": 100.0, "long_exit": False,
                                   "short_exit": False}
            r.executed_binding.pop(INSTRUMENT, None)
            r.process_entries()
            with SessionLocal() as s:
                assert s.query(Position).filter_by(instrument_key=INSTRUMENT).count() == 0
        finally:
            r.broker.close()


# ── isolation ───────────────────────────────────────────────────────────────────

class TestNoLiveSeamIsReached:
    def test_the_whole_paper_authority_cycle_touches_no_live_order_client(self, monkeypatch):
        """A dynamic trap, not an import scan: every live order entry point is replaced
        with something that raises, and a full stage/activate/reload/signal/entry/exit
        cycle runs without springing one."""
        import app.engine.kite_order_client as koc
        import app.engine.live_broker as lb

        def trap(*a, **k):
            raise AssertionError("a live order seam was reached from the paper lane")

        for module, names in ((koc, ("KiteOrderClient",)), (lb, ("LiveBroker",))):
            for name in names:
                monkeypatch.setattr(module, name, trap, raising=True)

        with SessionLocal() as s:
            row = _deploy(s)
            _open_paper_position(s, strategy_version=row.graph_content_address)
        r = _runner()
        try:
            r.armed = True
            _publish(r)
            r.process_entries()
            r.mark_and_exit_positions()
            r._square_off_all("TEST", r.provider.now())
        finally:
            r.broker.close()

    def test_the_broker_writing_these_records_is_a_paper_broker(self):
        from app.engine.broker import PaperBroker

        with SessionLocal() as s:
            _deploy(s)
        r = _runner()
        try:
            assert isinstance(r.broker, PaperBroker)
            assert type(r.broker) is PaperBroker
            assert r.book == PAPER
        finally:
            r.broker.close()

    def test_a_graph_opened_position_never_enters_the_live_book(self):
        from app.core.execution_book import foreign_book_positions

        with SessionLocal() as s:
            row = _deploy(s)
            _open_paper_position(s, strategy_version=row.graph_content_address)
        with SessionLocal() as s:
            assert [p.instrument_key for p in foreign_book_positions(s, LIVE)] == [INSTRUMENT]
            assert foreign_book_positions(s, PAPER) == []


# ── shadow and paper stay different things ──────────────────────────────────────

class TestShadowAndPaperAuthorityRemainSeparate:
    def test_a_shadow_deployment_confers_no_paper_authority(self, monkeypatch):
        from app.core import shadow_deployments as sd

        # The shadow service reads the research plane through its own door; state the
        # verdict there too, rather than reaching across the isolation boundary.
        monkeypatch.setattr(sd, "verified_decision", lambda **asked: {
            "run_id": 7, "candidate_id": 3, "project_id": PROJECT,
            "graph_identifier": GRAPH, "graph_version": asked["graph_version"],
            "content_address": "sha256:" + "e" * 64, "decision": "approved"})

        with SessionLocal() as s:
            if s.get(Project, PROJECT) is None:
                s.add(Project(project_id=PROJECT, name="paper"))
            if s.get(GraphArtifact, GRAPH) is None:
                s.add(GraphArtifact(identifier=GRAPH, project_id=PROJECT,
                                    display_name="m", draft_json="{}", draft_revision=0))
            s.flush()
            document = _graph_document(1)
            if s.get(GraphVersion, (GRAPH, 1)) is None:
                s.add(GraphVersion(graph_identifier=GRAPH, version=1,
                                   artifact_json=canonical_json(document),
                                   content_address=content_address(document)))
            s.commit()
            row = sd.stage(s, project_id=PROJECT, graph_identifier=GRAPH,
                           graph_version=1, deployment_id=LEGACY_DEPLOYMENT_ID,
                           instrument_key=INSTRUMENT, interval=INTERVAL)
            sd.activate(s, row.id, revision=row.revision)
            s.commit()
        r = _runner()
        try:
            assert r.paper_authority == {}
            assert r._binding_for(INSTRUMENT).origin != pa_origin()
        finally:
            r.broker.close()

    def test_the_two_services_share_no_table(self):
        from app.core import shadow_deployments as sd

        assert pa.IrPaperDeployment.__tablename__ != \
            sd.IrShadowDeployment.__tablename__


# ── evidence ────────────────────────────────────────────────────────────────────

class TestEvidence:
    def test_activation_refuses_an_unapproved_artefact(self, evidence_bridge):
        with SessionLocal() as s:
            row = _deploy(s, activate=False)
            evidence_bridge["decision"] = "rejected"
            with pytest.raises(pa.EvidenceUnverified):
                pa.activate(s, row.id, revision=row.revision)

    def test_resume_re_verifies_evidence_rather_than_trusting_the_pause(
            self, evidence_bridge):
        """A pause is a window in which the world can move. Resuming on trust would make it
        the one gap where a withdrawn approval could come back."""
        with SessionLocal() as s:
            row = _deploy(s)
            pa.pause(s, row.id, revision=row.revision)
            s.commit()
            evidence_bridge["decision"] = "rejected"
            current = s.get(IrPaperDeployment, row.id)
            with pytest.raises(pa.EvidenceUnverified):
                pa.resume(s, current.id, revision=current.revision)


def pa_origin() -> str:
    from app.core.execution_binding import ORIGIN_PAPER_AUTHORITY

    return ORIGIN_PAPER_AUTHORITY


class TestWithdrawalIdentityScope:
    """§7 — withdrawal must remove what the withdrawn binding authored, and only that."""

    def test_it_does_not_withdraw_a_signal_another_binding_authored(self):
        """A paper deployment can be retired in a window where the instrument's pending
        signal was authored by the *previous* authority, not by the graph. Dropping that
        is over-withdrawal: it is safe (a dropped signal never opens a wrong position) but
        it discards a valid signal the graph never touched."""
        with SessionLocal() as s:
            row = _deploy(s)
        r = _runner()
        try:
            # A signal authored by a hand-written strategy, not by the graph.
            handwritten = r._binding_for("GOLDM")
            r.publish_signal(INSTRUMENT, handwritten, {
                "signal": "LONG_ENTRY", "z": 2.0, "slope": 1.0, "close": 100.0,
                "long_exit": False, "short_exit": False})
            assert r._executed_binding(INSTRUMENT).strategy_key != IR_KEY

            with SessionLocal() as s:
                current = s.get(IrPaperDeployment, row.id)
                pa.retire(s, current.id, revision=current.revision,
                          restore_strategy_key=None)
                s.commit()
            r.refresh_paper_authority()

            assert r.state.get(INSTRUMENT) is not None, (
                "the graph did not author this signal; withdrawing the graph's authority "
                "must not discard another binding's valid state")
            assert r._executed_binding(INSTRUMENT) is not None
        finally:
            r.broker.close()
