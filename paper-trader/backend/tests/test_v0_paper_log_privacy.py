"""PaperBroker operational logs expose bounded status, never tenant trade facts."""
from __future__ import annotations

import ast
import datetime as dt
from pathlib import Path

from sqlalchemy import select

from app.core.logging import log
from app.db.models import Position
from app.engine.broker import PaperBroker
from app.monitoring.contracts import SignalAction
from app.paper_runtime.contracts import EffectPreference
from app.paper_runtime.service import PaperRuntimeService
from tests.test_v0_paper_runtime import _event, _facts, _runtime


SOURCE = Path(__file__).resolve().parents[1] / "app/engine/broker.py"
EXPECTED_EVENTS = {
    "PAPER_EXIT_LIFECYCLE_UNKNOWN", "OPEN", "OPEN_EQUITY", "CLOSE_EQUITY",
    "MANUAL_OPEN", "REINFORCE", "OPEN_FUTURES", "CLOSE_FUTURES", "CLOSE",
    "PARTIAL_CLOSE", "PARTIAL_CLOSE_EQUITY", "PARTIAL_CLOSE_FUTURES",
}
ALLOWED_LEVELS = {"trade", "info", "warn", "error"}
ALLOWED_OUTCOMES = {"APPLIED", "DEGRADED"}
FORBIDDEN_FIELDS = {
    "owner", "user", "request", "assignment", "strategy", "graph", "address",
    "instrument", "symbol", "tradingsymbol", "direction", "quantity", "qty",
    "price", "premium", "margin", "charge", "stop", "sl", "target", "tp",
    "reason", "position", "trade", "cash", "pnl", "cost", "count", "manual",
}


def _paper_broker_class() -> ast.ClassDef:
    tree = ast.parse(SOURCE.read_text())
    return next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "PaperBroker")


def test_every_paper_broker_logger_site_uses_the_closed_private_helper():
    broker = _paper_broker_class()
    log_calls = []
    for function in (
            node for node in broker.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))):
        for node in ast.walk(function):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "log"):
                log_calls.append((function.name, node))
    assert len(log_calls) == 1
    helper_name, helper_call = log_calls[0]
    assert helper_name == "_operational_log"
    assert helper_call.func.attr == "emit"
    assert len(helper_call.args) == 2
    assert isinstance(helper_call.args[0], ast.Name)
    assert helper_call.args[0].id == "emitted_level"
    assert ast.literal_eval(helper_call.args[1]) == "Paper broker event"
    assert {keyword.arg for keyword in helper_call.keywords} == {
        "event", "mode", "outcome",
    }
    keyword_values = {keyword.arg: keyword.value for keyword in helper_call.keywords}
    assert isinstance(keyword_values["event"], ast.Name)
    assert keyword_values["event"].id == "event"
    assert isinstance(keyword_values["mode"], ast.Attribute)
    assert isinstance(keyword_values["mode"].value, ast.Name)
    assert keyword_values["mode"].value.id == "self"
    assert keyword_values["mode"].attr == "MODE"
    assert isinstance(keyword_values["outcome"], ast.Name)
    assert keyword_values["outcome"].id == "outcome"
    calls = [
        node for node in ast.walk(broker)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name) and node.func.value.id == "self"
        and node.func.attr == "_operational_log"
    ]
    observed = set()
    for call in calls:
        assert len(call.args) == 3 and not call.keywords
        level, event, outcome = (ast.literal_eval(arg) for arg in call.args)
        assert level in ALLOWED_LEVELS and event in EXPECTED_EVENTS
        assert outcome in ALLOWED_OUTCOMES
        observed.add(event)
    assert observed == EXPECTED_EVENTS


def test_private_helper_emits_only_generic_message_and_closed_fields(monkeypatch):
    captured = []

    def capture(level, message, **fields):
        captured.append((level, message, fields))

    monkeypatch.setattr(log, "emit", capture)
    broker = object.__new__(PaperBroker)
    for event in EXPECTED_EVENTS:
        broker._operational_log(
            "error" if event == "PAPER_EXIT_LIFECYCLE_UNKNOWN" else "trade",
            event,
            "DEGRADED" if event == "PAPER_EXIT_LIFECYCLE_UNKNOWN" else "APPLIED",
        )
    assert captured
    for level, message, fields in captured:
        assert level in {"trade", "error"}
        assert message == "Paper broker event"
        assert set(fields) == {"event", "mode", "outcome"}
        assert not FORBIDDEN_FIELDS & set(fields)
        assert fields["event"] in EXPECTED_EVENTS
        assert fields["mode"] == "paper"
        assert fields["outcome"] in ALLOWED_OUTCOMES


def test_runtime_entry_and_risk_reducing_exit_do_not_log_private_sentinels(
        admitted_entry_identity, monkeypatch):
    captured = []

    def capture(level, message, **fields):
        captured.append((level, message, fields))

    monkeypatch.setattr(log, "emit", capture)
    broker, identity, event, assignment, authority, sink = _runtime(
        admitted_entry_identity, preference=EffectPreference.PAPER,
        price="98765.43", stop="87654.32", target="99876.54")
    service = PaperRuntimeService(broker, alert_sink=sink)
    service.process(assignment, authority, event, now=event.event_at + dt.timedelta(minutes=1))
    assert broker.s.scalar(select(Position)) is not None
    exit_event = _event(
        identity, action=SignalAction.EXIT, event_minute=3,
        base_time=event.event_at, price="97654.21", stop="87654.32", target="99876.54")
    exit_assignment, exit_authority = _facts(
        identity, exit_event, preference=EffectPreference.PAPER, authority=authority)
    service.process(exit_assignment, exit_authority, exit_event,
                    now=exit_event.event_at + dt.timedelta(minutes=1))
    paper_events = [item for item in captured if item[2].get("event") in EXPECTED_EVENTS]
    serialized = repr(paper_events).lower()
    assert paper_events and any(fields.get("event") == "OPEN_EQUITY" for _, _, fields in paper_events)
    assert any(fields.get("event") == "CLOSE_EQUITY" for _, _, fields in paper_events)
    for sentinel in ("nifty", "long", "98765.43", "87654.32", "99876.54", "97654.21"):
        assert sentinel not in serialized
    broker.close()
