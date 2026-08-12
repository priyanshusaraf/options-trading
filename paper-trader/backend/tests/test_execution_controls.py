from types import SimpleNamespace

import pytest

from app.execution.controls import apply_control
from app.engine.live_broker import LiveBroker


class _Repo:
    def __init__(self):
        self.transitions = []

    def bind_money_session(self, session, token):
        session.bound = token

    def transition_command(self, token, command_id, **transition):
        self.transitions.append((command_id, transition))

    def complete_control(self, token, command_id, *, success):
        self.transitions.append((command_id, {"to_state": "resolved" if success else "failed"}))

    def complete_control_with_projection(self, token, command_id, *, deployment_id, armed,
                                         success=True):
        self.complete_control(token, command_id, success=success)


class _Session:
    def __enter__(self): return self
    def __exit__(self, *_): pass
    def commit(self): self.committed = True
    def scalar(self, *_): return 0


class _UnresolvedSession(_Session):
    def scalar(self, *_): return 1


def _runner(*, remaining=(), inflight=None, pending=None):
    return SimpleNamespace(
        deployment_id=1, owner_id="owner", broker_account_id="account", armed=False,
        kill=lambda: [],
        broker=SimpleNamespace(open_positions=lambda: list(remaining), _inflight=inflight or {},
                               _pending_entries=pending or {}))


def _token():
    return SimpleNamespace(owner_id="owner", broker_account_id="account")


def test_holder_arm_resolves_only_after_durable_projection(monkeypatch):
    repo, runner = _Repo(), _runner()
    assert apply_control(repo, _token(), runner,
                         SimpleNamespace(kind="control_arm", command_id="arm"), _Session) == "resolved"
    assert runner.armed is True
    assert repo.transitions[-1][1] == {"to_state": "resolved"}


def test_holder_arm_persistence_failure_never_changes_local_flag(monkeypatch):
    repo, runner = _Repo(), _runner()
    repo.complete_control_with_projection = lambda *a, **k: (_ for _ in ()).throw(
        RuntimeError("projection unavailable"))
    with pytest.raises(RuntimeError, match="projection"):
        apply_control(repo, _token(), runner,
                      SimpleNamespace(kind="control_arm", command_id="arm"), _Session)
    assert runner.armed is False
    assert repo.transitions[-1][1]["to_state"] == "failed"


def test_holder_arm_completion_failure_never_changes_local_flag(monkeypatch):
    repo, runner = _Repo(), _runner()
    repo.complete_control_with_projection = lambda *a, **k: (_ for _ in ()).throw(
        RuntimeError("stale completion"))
    with pytest.raises(RuntimeError, match="stale completion"):
        apply_control(repo, _token(), runner,
                      SimpleNamespace(kind="control_arm", command_id="arm"), _Session)
    assert runner.armed is False


def test_partial_kill_is_failed_not_resolved(monkeypatch):
    repo, runner = _Repo(), _runner(remaining=[object()])
    with pytest.raises(RuntimeError, match="partial"):
        apply_control(repo, _token(), runner,
                      SimpleNamespace(kind="control_kill", command_id="kill"), _Session)
    assert repo.transitions[-1][1]["to_state"] == "failed"


def test_tag_only_pending_entry_prevents_kill_success(monkeypatch):
    repo, runner = _Repo(), _runner(pending={"NIFTY": {"broker_tag": "pti-late"}})
    with pytest.raises(RuntimeError, match="partial"):
        apply_control(repo, _token(), runner,
                      SimpleNamespace(kind="control_kill", command_id="kill"), _Session)


def test_live_kill_cannot_clear_tag_only_pending_entry_without_broker_identity():
    broker = SimpleNamespace(
        _inflight={}, _pending_entries={"NIFTY": {"broker_tag": "pti-late"}},
        client=SimpleNamespace(cancel=lambda _: None), journal_mark_terminal=lambda *_: None,
        _notify=lambda *_: None)
    assert LiveBroker.cancel_working_entries(broker) == []
    assert broker._pending_entries == {"NIFTY": {"broker_tag": "pti-late"}}


def test_clean_kill_resolves(monkeypatch):
    repo, runner = _Repo(), _runner()
    assert apply_control(repo, _token(), runner,
                         SimpleNamespace(kind="control_kill", command_id="kill"), _Session) == "resolved"
    assert repo.transitions[-1][1]["to_state"] == "resolved"


def test_durable_working_evidence_prevents_kill_resolution():
    repo, runner = _Repo(), _runner()
    runner.armed = True
    with pytest.raises(RuntimeError, match="partial"):
        apply_control(repo, _token(), runner,
                      SimpleNamespace(kind="control_kill", command_id="kill"),
                      _UnresolvedSession)
    assert runner.armed is False
    assert repo.transitions[-1][1]["to_state"] == "failed"


def test_stale_holder_cannot_resolve_control(monkeypatch):
    repo, runner = _Repo(), _runner()

    def stale(*args, **kwargs):
        if kwargs.get("to_state") == "resolved":
            raise RuntimeError("stale token")
        repo.transitions.append((args[1], kwargs))

    repo.complete_control_with_projection = lambda *a, **k: (_ for _ in ()).throw(
        RuntimeError("stale token"))
    with pytest.raises(RuntimeError, match="stale"):
        apply_control(repo, _token(), runner,
                      SimpleNamespace(kind="control_kill", command_id="kill"), _Session)
    assert not any(transition.get("to_state") == "resolved"
                   for _, transition in repo.transitions)
