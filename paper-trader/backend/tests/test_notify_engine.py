"""Phase 2: the engine emits notifications on auto-open, on close, and when a
position nears its SL/TP (the owner's 'tell me when I'm near an exit' ask)."""
from app.core.instruments import get_instrument
from app.core import paper_authority
from app.db.models import LEGACY_DEPLOYMENT_ID
from app.db.session import init_db
from app.engine.runner import EngineRunner
from tests.admitted_entry import persist_admitted_entry
from app.notify.notifier import Notifier


def _runner_with_capture():
    init_db(reset=True)
    r = EngineRunner(owner_id="owner", broker_account_id="account.default")
    r.params["entry_min_days_to_expiry"] = 0   # mock NIFTY chain is ~1-DTE; these tests aren't the DTE guard
    admission = persist_admitted_entry(r.broker.s)
    with r._session() as session:
        row = paper_authority.stage(
            session, project_id="test.admission.4c1029697ee358715d3a14a2",
            graph_identifier="test.strategy.expanding_z_impulse", graph_version=1,
            deployment_id=LEGACY_DEPLOYMENT_ID, instrument_key="NIFTY", interval="30minute",
            owner_id=r.owner_id, broker_account_id=r.broker_account_id)
        session.commit()
    with r._session() as session:
        from unittest.mock import patch
        decision = {"project_id": "test.admission.4c1029697ee358715d3a14a2",
                    "graph_identifier": "test.strategy.expanding_z_impulse",
                    "graph_version": 1, "content_address": admission["graph_address"],
                    "admission_address": admission["admission_address"], "decision": "approved"}
        with patch.object(paper_authority, "verified_decision", return_value=decision):
            paper_authority.activate(session, row.id, revision=row.revision,
                                     owner_id=r.owner_id, broker_account_id=r.broker_account_id)
        session.commit()
    r.refresh_paper_authority()
    sent: list[str] = []
    r.notifier = Notifier(sender=lambda t: sent.append(t))
    return r, sent


def _nearest_ce(r):
    inst = get_instrument("NIFTY")
    chain = r.provider.get_option_chain(inst)
    q = min((x for x in chain.quotes if x.option_type == "CE"),
            key=lambda x: abs(x.strike - chain.spot))
    return inst, chain, q


def _stub_snapshot(r, premium):
    def fake(insts, positions):
        return {p.instrument_key: {"time": "t", "spot": 100.0,
                                   "option_premium": premium,
                                   "tradingsymbol": p.tradingsymbol}
                for p in positions}
    r.provider.live_snapshot = fake


def test_notifies_on_auto_open():
    r, sent = _runner_with_capture()
    r.armed = True                       # must be armed to auto-execute
    r.publish_signal(
        "NIFTY", r._binding_for("NIFTY"), {"signal": "LONG_ENTRY", "z": 1.5, "slope": 1.0,
                                           "close": 100.0, "long_exit": False, "short_exit": False})
    r.process_entries()
    assert r.broker.position_for("NIFTY") is not None
    assert any("OPEN" in m for m in sent)


def test_notifies_when_nearing_stop_without_closing():
    r, sent = _runner_with_capture()
    inst, chain, q = _nearest_ce(r)
    admission = persist_admitted_entry(r.broker.s)
    pos = r.broker.open_position(inst, "LONG", q, "t", r.provider.now(), chain.spot,
                                  r.params, **admission)
    r.publish_signal(
        "NIFTY", r._binding_for("NIFTY"), {"long_exit": False, "short_exit": False})
    # premium just above the stop (within the proximity zone) -> warn, don't close
    _stub_snapshot(r, premium=pos.stop_price * 1.05)
    r.mark_and_exit_positions()
    assert r.broker.position_for("NIFTY") is not None       # not closed
    assert any("STOP" in m for m in sent)                   # but warned


def test_notifies_on_stop_loss_close():
    r, sent = _runner_with_capture()
    inst, chain, q = _nearest_ce(r)
    admission = persist_admitted_entry(r.broker.s)
    pos = r.broker.open_position(inst, "LONG", q, "t", r.provider.now(), chain.spot,
                                  r.params, **admission)
    r.publish_signal(
        "NIFTY", r._binding_for("NIFTY"), {"long_exit": False, "short_exit": False})
    _stub_snapshot(r, premium=pos.stop_price * 0.9)         # below the stop -> exit
    r.mark_and_exit_positions()
    assert r.broker.position_for("NIFTY") is None
    assert any("CLOSE" in m and "STOP_LOSS" in m for m in sent)
