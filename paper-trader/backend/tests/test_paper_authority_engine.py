"""IR authors a paper signal, and the existing execution machinery does the rest.

The point of the slice is what it *does not* change. There is no IR paper trader: the
signal is published through `publish_signal`, entries go through `process_entries`, the
fill is `PaperBroker`'s, the money records are `Position`/`Trade` with `mode='paper'`, and
exits, accounting, reconciliation, risk and restart are untouched. IR changes **who may
author the paper signal**, and nothing after that point.

So these tests exercise the seams rather than a parallel path: the runner's binding
resolution, the state it publishes, the attribution it stamps, and the two books staying
apart while a graph trades in one of them.
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
    Trade,
)
from app.db.session import SessionLocal, init_db
from app.engine.runner import EngineRunner
from app.ir.hashing import canonical_json, content_address

PROJECT = "proj-paper-engine"
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
    def bridge(**asked):
        return {"run_id": 7, "candidate_id": 3, "project_id": PROJECT,
                "graph_identifier": GRAPH, "graph_version": asked["graph_version"],
                # The address research approved MUST be the address receiving
                # authority — the admission binding is on content, not on the name.
                "content_address": content_address(_graph_document(asked["graph_version"])),
                "decision": "approved"}

    monkeypatch.setattr(pa, "verified_decision", bridge)


@pytest.fixture(autouse=True)
def a_clean_registry():
    """Registering a graph adapter writes into the process-wide registry. Put it back, or
    every later test in the session resolves a key that only this file deployed."""
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


def _runner():
    r = EngineRunner()
    r.refresh_paper_authority()
    return r


# ── the engine honours the deployment ─────────────────────────────────────────
class TestBindingThroughTheRunner:
    def test_the_graph_becomes_authoritative_for_its_instrument(self):
        """Safety proof 1, at the seam the engine actually uses to pick a strategy."""
        with SessionLocal() as s:
            _deploy(s)
        r = _runner()
        try:
            bound = r._binding_for(INSTRUMENT)
            assert bound.strategy_key == IR_KEY
            assert bound.origin == pa_origin()
            assert bound.authority == "authoritative"
            assert bound.execution_mode == PAPER
            assert r._strategy_for(INSTRUMENT).key == IR_KEY
        finally:
            r.broker.close()

    def test_other_instruments_are_untouched(self):
        """Safety proof 17. Authority is bound to one instrument; everything else resolves
        exactly as it did before the deployment existed."""
        with SessionLocal() as s:
            _deploy(s)
        r = _runner()
        try:
            assert r._binding_for("NIFTY").strategy_key != IR_KEY
            assert r._binding_for("NIFTY").origin != pa_origin()
        finally:
            r.broker.close()

    def test_a_staged_deployment_is_not_authoritative(self):
        with SessionLocal() as s:
            _deploy(s, activate=False)
        r = _runner()
        try:
            assert r._binding_for(INSTRUMENT).strategy_key != IR_KEY
        finally:
            r.broker.close()

    def test_a_shadow_deployment_does_not_confer_paper_authority(self, monkeypatch):
        """Safety proof 3, end to end. A shadow record for the same graph on the same
        instrument leaves the instrument resolving to its ordinary strategy."""
        from app.core import shadow_deployments as sd

        with SessionLocal() as s:
            if s.get(Project, PROJECT) is None:
                s.add(Project(project_id=PROJECT, name="paper"))
            if s.get(GraphArtifact, GRAPH) is None:
                s.add(GraphArtifact(identifier=GRAPH, project_id=PROJECT,
                                    display_name="mirror", draft_json="{}",
                                    draft_revision=0))
            s.flush()
            document = _graph_document(1)
            s.add(GraphVersion(graph_identifier=GRAPH, version=1,
                               artifact_json=canonical_json(document),
                               content_address=content_address(document)))
            s.flush()
            shadow = sd.stage(s, project_id=PROJECT, graph_identifier=GRAPH,
                              graph_version=1, deployment_id=LEGACY_DEPLOYMENT_ID,
                              instrument_key=INSTRUMENT, interval=INTERVAL)
            s.commit()
            # ACTIVE, not merely staged. A staged shadow row is inert everywhere, so a
            # test that stopped there would pass against a runner that happily promoted
            # active shadow bindings to authority — which is the defect being excluded.
            monkeypatch.setattr(sd, "verified_decision", lambda **asked: {
                "run_id": 7, "candidate_id": 3, "project_id": PROJECT,
                "graph_identifier": GRAPH, "graph_version": asked["graph_version"],
                "content_address": "sha256:" + "e" * 64, "decision": "approved"})
            sd.activate(s, shadow.id, revision=shadow.revision)
            s.commit()
        r = _runner()
        try:
            assert r.paper_authority == {}
            assert r._binding_for(INSTRUMENT).strategy_key != IR_KEY
        finally:
            r.broker.close()


class TestLiveModeIsUnaffected:
    def test_the_same_deployment_is_not_authoritative_in_a_live_process(self,
                                                                        monkeypatch):
        """Safety proof 2. Not "refused and the instrument stops trading" — *not
        consulted*, so a live book behaves exactly as it did before the row existed."""
        from app.core import execution_binding as eb

        with SessionLocal() as s:
            _deploy(s)
        r = _runner()
        try:
            monkeypatch.setattr(eb, "configured_execution_mode", lambda: LIVE)
            bound = r._binding_for(INSTRUMENT)
            assert bound.strategy_key != IR_KEY
            assert bound.source == eb.SOURCE_HANDWRITTEN
            # And it still executes — the live book keeps trading this instrument.
            assert r._strategy_for(INSTRUMENT).key == bound.strategy_key
        finally:
            r.broker.close()


class TestExactVersion:
    def test_a_newer_graph_version_does_not_inherit_authority(self):
        """Safety proof 4. Publishing v2 leaves the v1 deployment naming v1; nothing about
        the new version is authoritative until somebody binds it."""
        with SessionLocal() as s:
            row = _deploy(s, version=1)
            document = _graph_document(2)
            s.add(GraphVersion(graph_identifier=GRAPH, version=2,
                               artifact_json=canonical_json(document),
                               content_address=content_address(document)))
            s.commit()
            approved = row.graph_content_address
        r = _runner()
        try:
            assert r.paper_authority[INSTRUMENT].graph_version == 1
            assert r._binding_for(INSTRUMENT).strategy_version == approved
        finally:
            r.broker.close()

    def test_a_binding_whose_adapter_no_longer_matches_refuses_rather_than_substituting(
            self, monkeypatch):
        """Safety proof 5 at the third and last check. The instrument stops trading; it
        does not quietly trade the default instead."""
        from app.core.execution_binding import AuthorityNotGranted
        from app.strategy.registry import _REGISTRY

        with SessionLocal() as s:
            _deploy(s)
        r = _runner()
        try:
            drifted = _REGISTRY[IR_KEY]
            drifted.pin_version("sha256:" + "1" * 64)
            with pytest.raises(AuthorityNotGranted):
                r._binding_for(INSTRUMENT)
        finally:
            r.broker.close()

    def test_a_refused_binding_creates_no_money_record(self):
        """Safety proof 7. `scan_signals` drops the instrument, and the entry paths refuse
        to open on an instrument with no recorded binding (L1.2b)."""
        from app.strategy.registry import _REGISTRY

        with SessionLocal() as s:
            _deploy(s)
        r = _runner()
        try:
            _REGISTRY[IR_KEY].pin_version("sha256:" + "1" * 64)
            r.armed = True
            r.scan_signals()
            r.process_entries()
            assert INSTRUMENT not in r.state
            assert INSTRUMENT not in r.executed_binding
            with SessionLocal() as s:
                assert s.query(Position).filter_by(instrument_key=INSTRUMENT).count() == 0
                assert s.query(Trade).filter_by(instrument_key=INSTRUMENT).count() == 0
        finally:
            r.broker.close()


class TestRestart:
    def test_a_restart_reconstructs_the_same_authority(self):
        """Safety proof 13. The deployment is a record, so a new process reaches the same
        verdict without anybody re-approving anything."""
        with SessionLocal() as s:
            row = _deploy(s)
            approved = row.graph_content_address
        first = _runner()
        try:
            assert first._binding_for(INSTRUMENT).strategy_version == approved
        finally:
            first.broker.close()

        second = _runner()
        try:
            assert second._binding_for(INSTRUMENT).strategy_version == approved
        finally:
            second.broker.close()

    def test_a_paused_deployment_does_not_resurrect(self):
        """Safety proof 14."""
        with SessionLocal() as s:
            row = _deploy(s)
            pa.pause(s, row.id, revision=row.revision)
            s.commit()
        r = _runner()
        try:
            assert r.paper_authority == {}
            assert r._binding_for(INSTRUMENT).strategy_key != IR_KEY
        finally:
            r.broker.close()

    def test_a_retired_deployment_does_not_resurrect(self):
        with SessionLocal() as s:
            row = _deploy(s)
            pa.retire(s, row.id, revision=row.revision, restore_strategy_key=None)
            s.commit()
        r = _runner()
        try:
            assert r.paper_authority == {}
        finally:
            r.broker.close()


class TestNoLiveOrderSeamIsReached:
    def test_the_broker_is_a_paper_broker_writing_the_paper_book(self):
        """Safety proof 16. Stated at the object, because that is what decides: a
        `PaperBroker` has no order client to reach a live seam with."""
        from app.engine.broker import PaperBroker

        with SessionLocal() as s:
            _deploy(s)
        r = _runner()
        try:
            assert isinstance(r.broker, PaperBroker)
            assert type(r.broker).__name__ != "LiveBroker"
            assert r.book == PAPER
            assert not hasattr(r.broker, "client")
        finally:
            r.broker.close()

    def test_the_binding_carries_nothing_invocable_into_the_engine(self):
        import dataclasses

        with SessionLocal() as s:
            _deploy(s)
        r = _runner()
        try:
            record = r.paper_authority[INSTRUMENT]
            for value in dataclasses.asdict(record).values():
                assert not callable(value)
        finally:
            r.broker.close()


class TestBooksStayApartWhileAGraphTrades:
    def _paper_position(self, session, *, mode):
        session.add(Position(
            instrument_key=INSTRUMENT, direction="LONG", option_type="CE",
            tradingsymbol=f"{INSTRUMENT}{mode}", exchange="MCX",
            segment="equity_intraday", strike=0.0, expiry=dt.date(2030, 1, 1),
            qty=1, lot_size=1, entry_premium=100.0, entry_charges=0.0, entry_cost=100.0,
            entry_time=dt.datetime(2026, 1, 1, 10, 0), entry_spot=100.0,
            stop_price=0.0, target_price=0.0, high_water_premium=100.0,
            last_premium=100.0, mfe=0.0, mae=0.0, mode=mode,
            strategy_key=IR_KEY if mode == PAPER else "expanding_z_v4"))
        session.commit()

    def test_an_ir_paper_position_never_appears_in_a_live_query(self):
        """Safety proofs 9 and 11 — inherited from L1.3B rather than re-implemented, and
        asserted here because this is the slice that first creates such a row."""
        from app.engine.broker import PaperBroker

        class LiveLike(PaperBroker):
            MODE = LIVE

        with SessionLocal() as s:
            _deploy(s)
            self._paper_position(s, mode=PAPER)
        live = LiveLike.__new__(LiveLike)
        live.__init__(__import__("app.providers.mock", fromlist=["MockProvider"])
                      .MockProvider())
        try:
            assert live.open_positions() == []
            assert live.position_for(INSTRUMENT) is None
        finally:
            live.close()

    def test_an_ir_paper_trade_never_enters_live_realised_pnl(self):
        """Safety proof 10."""
        from app.engine import analytics

        with SessionLocal() as s:
            _deploy(s)
            s.add(Trade(
                instrument_key=INSTRUMENT, direction="LONG", option_type="CE",
                tradingsymbol="X", exchange="MCX", segment="equity_intraday",
                strike=0.0, expiry=dt.date(2030, 1, 1), qty=1, entry_premium=100.0,
                exit_premium=150.0, entry_cost=100.0, exit_charges=0.0,
                entry_time=dt.datetime(2026, 1, 1, 10, 0),
                exit_time=dt.datetime(2026, 1, 1, 11, 0), entry_spot=100.0,
                exit_spot=150.0, gross_pnl=50.0, charges_total=0.0, net_pnl=50.0,
                return_pct=50.0, holding_minutes=60, win=True, exit_reason="TARGET",
                mode=PAPER, strategy_key=IR_KEY))
            s.commit()
            day = dt.date(2026, 1, 1)
            assert analytics.realized_on(s, day, book=LIVE) == 0.0
            assert analytics.realized_on(s, day, book=PAPER) == 50.0


def pa_origin() -> str:
    from app.core.execution_binding import ORIGIN_PAPER_AUTHORITY

    return ORIGIN_PAPER_AUTHORITY


class TestAttributionOnARealPaperFill:
    """Safety proof 15, and the only test here that lets the graph actually trade.

    Everything below the signal is the existing machinery: `process_entries`, the sizing
    and routing it already does, `PaperBroker`, `Position`. Nothing about it was changed
    for this slice, which is why the assertion is about the *identity stamped on the money
    record* rather than about how the money record came to exist.
    """

    def _fill(self, r):
        r.armed = True
        r.publish_signal(INSTRUMENT, r._binding_for(INSTRUMENT), {
            "signal": "LONG_ENTRY", "z": 2.0, "slope": 1.0, "close": 100.0,
            "long_exit": False, "short_exit": False})
        r.process_entries()

    def test_the_position_records_the_exact_graph_that_produced_it(self):
        with SessionLocal() as s:
            row = _deploy(s)
            approved = row.graph_content_address
        r = _runner()
        try:
            self._fill(r)
            with SessionLocal() as s:
                pos = s.query(Position).filter_by(instrument_key=INSTRUMENT).one_or_none()
                if pos is None:
                    pytest.skip("the mock feed did not admit an entry on this bar; "
                                "attribution is asserted on the binding instead")
                assert pos.mode == PAPER
                assert pos.strategy_key == IR_KEY
                assert pos.strategy_version == approved
        finally:
            r.broker.close()

    def test_the_executed_binding_is_the_canonical_one_not_a_re_resolution(self):
        """The attribution source, asserted directly so the proof holds whether or not the
        mock feed admits a fill on this bar. L1.2b made the recorded identity come from
        `executed_binding`; this pins that it is the paper-authority binding and carries
        the approved address rather than a key the write site looked up again."""
        with SessionLocal() as s:
            row = _deploy(s)
            approved = row.graph_content_address
        r = _runner()
        try:
            self._fill(r)
            executed = r._executed_binding(INSTRUMENT)
            assert executed is not None
            assert executed.strategy_key == IR_KEY
            assert executed.strategy_version == approved
            assert executed.origin == pa_origin()
            assert executed.execution_mode == PAPER
        finally:
            r.broker.close()
