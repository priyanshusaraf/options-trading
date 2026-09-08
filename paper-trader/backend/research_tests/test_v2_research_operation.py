"""Closed durable-operation identity tests for saved V2 research."""
from __future__ import annotations

import copy
import datetime as dt
import hashlib
import inspect
import uuid

import pytest


@pytest.mark.parametrize("preset,fields", [
    ("trend_impulse_v3", ("CLOSE",)),
    ("expanding_z_v4", ("CLOSE", "HIGH", "LOW")),
])
def test_saved_preset_data_requirements_include_resolved_compound_members(preset, fields):
    from app.ir.original_strategy_presets import instantiate_preset
    from tests.test_strategy_registry import _original_preset_registry
    from research.orchestrator.v2_operation import _graph_input_fields
    registry = _original_preset_registry()
    document = instantiate_preset(preset, "compound-data-requirements")
    assert _graph_input_fields(document, registry) == {"frame": fields}
    document["nodes"][0]["parameters"]["ema_length"] = 43
    assert _graph_input_fields(document, registry) == {"frame": fields}

from app.ir.hashing import canonical_json, content_address
from research.orchestrator.v2_operation import (
    DurableClaimCancellationToken,
    V2_PROVIDER_MODE,
    V2_OPERATION_SCHEMA,
    V2OperationRefusal,
    build_v2_operation_plan,
    operation_id_for_request,
    parse_v2_operation_plan,
)
from research_tests.test_operation_repository import repo


def _item() -> dict:
    phase4 = {
        "owner_id": "owner-a", "mode": "RESEARCH",
        "authored_ir_address": "sha256:" + "b" * 64,
        "registry_snapshot_address": "sha256:" + "2" * 64,
        "resolved_graph_address": "sha256:" + "3" * 64,
        "implementation_closure_address": "sha256:" + "4" * 64,
        "declaration_addresses": ["sha256:" + "5" * 64],
        "plan_address": "sha256:" + "6" * 64,
        "capability_assessment_address": "sha256:" + "7" * 64,
        "dataset_manifest_address": "sha256:" + "8" * 64,
        "market_truth_snapshot_address": "sha256:" + "9" * 64,
        "evaluation_policy_address": "sha256:" + "a" * 64,
    }
    return {
        "request_id": "6ba7b810-9dad-4d80-80b4-00c04fd430c8",
        "project_id": "project-a", "graph_identifier": "graph-a",
        "graph_version": 2, "content_address": "sha256:" + "b" * 64,
        "graph_address": "sha256:" + "c" * 64,
        "admission_address": "sha256:" + "d" * 64,
        "dataset_manifest_address": phase4["dataset_manifest_address"],
        "dataset_as_of": "2026-08-30T12:00:00+00:00",
        "phase4_binding": phase4,
        "experiment": {
            "hypothesis": "A saved V2 graph remains causal.",
            "research_capital": 50_000.0, "seed": 17, "min_trades": 2,
            "n_folds": 2, "min_positive_fold_frac": 0.5,
        },
    }


def test_v2_plan_is_closed_canonical_and_deterministic():
    plan = build_v2_operation_plan(_item())
    parsed = parse_v2_operation_plan(copy.deepcopy(plan))
    assert parsed == plan
    assert plan["schema"] == V2_OPERATION_SCHEMA
    assert plan["experiment_count"] == 1
    assert len(plan["v2_graphs"]) == 1
    assert len(canonical_json(plan).encode()) <= 65_536
    item = plan["v2_graphs"][0]
    assert item["descriptor_address"] == content_address({
        key: value for key, value in item.items() if key != "descriptor_address"
    })
    assert plan["content_address"] == content_address({
        "schema": plan["schema"], "experiment_count": 1,
        "v2_graphs": plan["v2_graphs"],
    })


def test_optional_parameter_neighborhood_is_durable_and_identity_bound():
    absent = build_v2_operation_plan(_item())
    frozen = {
        "request": (canonical_json(_item()).encode(), 1768,
                    "bf929faca343b1c27daecd755208ac4331cd7cef74c87c972950d9a97532f037"),
        "descriptor": (canonical_json(absent["v2_graphs"][0]).encode(), 3046,
                       "bd14c07b6c468beb1574d4a51f0a58cfaaaf8f54845d19f795cde5947448e967"),
        "plan": (canonical_json(absent).encode(), 3216,
                 "1c087afa72f2508f9858da8a51270f6517d2bf7c21ca91ad3d9afa9151253c88"),
    }
    for raw, length, digest in frozen.values():
        assert len(raw) == length
        assert hashlib.sha256(raw).hexdigest() == digest
    present_item = _item()
    present_item["robustness"] = {"parameter_neighborhood": {
        "enabled": True,
        "axes": [{
            "node_id": "rising", "parameter_id": "window",
            "step": "1", "minimum": "1", "maximum": "3",
        }],
        "maximum_score_drop_paise": 100,
        "minimum_stable_fraction_ppm": 500_000,
    }}
    present = build_v2_operation_plan(present_item)
    assert "robustness" not in absent["v2_graphs"][0]
    assert parse_v2_operation_plan(copy.deepcopy(present)) == present
    assert present["content_address"] != absent["content_address"]
    changed = copy.deepcopy(present_item)
    changed["robustness"]["parameter_neighborhood"]["maximum_score_drop_paise"] = 101
    assert build_v2_operation_plan(changed)["content_address"] != present["content_address"]
    forged = copy.deepcopy(present)
    forged["v2_graphs"][0]["robustness"]["parameter_neighborhood"]["axes"][0]["step"] = "2"
    with pytest.raises(V2OperationRefusal):
        parse_v2_operation_plan(forged)


def test_candidate_capability_keeps_one_mutation_resolution_and_evaluation_authority():
    import research.orchestrator.v2_operation as operation_module

    source = inspect.getsource(operation_module._execute_admitted_operation)
    assert source.count("apply_semantic_commands(") == 1
    assert "candidate_resolved = resolve_v2(mutation.document, REGISTRY)" in source
    assert "candidate_data_plan = compile_data_requirement_plan(" in source
    assert "candidate_eligibility = _operation_eligibility(" in source
    assert "candidate_resolved, candidate_data_plan, candidate_policy.policy_address" in source
    assert "candidate_resource_plan = accept_research_resource_plan(" in source
    assert "candidate_result = execute_research(" in source
    assert "canonical_json(version[\"document\"]) != baseline_bytes" in source
    assert "v2_editor_store" not in source[source.index("def evaluate_parameter_candidate"):]


def test_request_identity_requires_lowercase_rfc4122_uuid4():
    request_id = "6ba7b810-9dad-4d80-80b4-00c04fd430c8"
    first = operation_id_for_request(owner_id="owner-a", request_id=request_id)
    assert len(first) == 64 and int(first, 16) >= 0
    assert first == operation_id_for_request(owner_id="owner-a", request_id=request_id)
    assert first != operation_id_for_request(owner_id="owner-b", request_id=request_id)
    for invalid in (str(uuid.uuid1()), request_id.upper(), "not-a-uuid"):
        with pytest.raises(V2OperationRefusal, match="request_id"):
            operation_id_for_request(owner_id="owner-a", request_id=invalid)


@pytest.mark.parametrize("mutation", [
    lambda item: item.update(provider_mode="network"),
    lambda item: item.update(dataset_as_of="2026-08-30T12:00:00.1+00:00"),
    lambda item: item["phase4_binding"].update(mode="PAPER"),
    lambda item: item["phase4_binding"].update(dataset_manifest_address="sha256:" + "f" * 64),
    lambda item: item["experiment"].update(optimize=True),
])
def test_v2_plan_parser_refuses_open_or_mismatched_content(mutation):
    item = _item()
    mutation(item)
    with pytest.raises(V2OperationRefusal):
        build_v2_operation_plan(item)


def _owner_plan(owner: str, request_id: str, *, hypothesis: str = "causal"):
    item = _item()
    item["request_id"] = request_id
    item["phase4_binding"]["owner_id"] = owner
    item["experiment"]["hypothesis"] = hypothesis
    return build_v2_operation_plan(item)


def test_v2_enqueue_retry_is_exact_and_changed_request_reuse_refuses(repo):
    from research.domain.operations import ResearchOperationRepository

    request_id = "9c074bb2-19e0-4690-a26e-16590f249888"
    plan = _owner_plan("owner-a", request_id)
    operation_id = operation_id_for_request(owner_id="owner-a", request_id=request_id)
    first = repo.enqueue(
        owner_id="owner-a", trigger="v2_graph", plan=plan, build="build-a",
        provider_mode=V2_PROVIDER_MODE, operation_id=operation_id,
    )
    retry = repo.enqueue(
        owner_id="owner-a", trigger="v2_graph", plan=copy.deepcopy(plan),
        build="build-a", provider_mode=V2_PROVIDER_MODE, operation_id=operation_id,
    )
    assert retry == first
    with pytest.raises(V2OperationRefusal) as refused:
        repo.enqueue(
            owner_id="owner-a", trigger="v2_graph",
            plan=_owner_plan("owner-a", request_id, hypothesis="changed"),
            build="build-a", provider_mode=V2_PROVIDER_MODE,
            operation_id=operation_id,
        )
    assert refused.value.code == "REQUEST_ID_REUSED"
    assert repo.get(operation_id, owner_id="owner-a").plan == plan


def test_one_running_v2_graph_per_owner_preserves_foreign_progress(repo):
    requests = (
        "34676c3c-e14f-4a56-9a59-b91901c955b0",
        "17c5bdcf-62f9-44b6-bbab-fc7f8951fd55",
        "db64fd7e-4ffc-47f5-9138-05d36f00ee37",
    )
    first_id = operation_id_for_request(owner_id="owner-a", request_id=requests[0])
    second_id = operation_id_for_request(owner_id="owner-a", request_id=requests[1])
    foreign_id = operation_id_for_request(owner_id="owner-b", request_id=requests[2])
    for owner, request_id, operation_id in (
        ("owner-a", requests[0], first_id), ("owner-a", requests[1], second_id),
        ("owner-b", requests[2], foreign_id),
    ):
        repo.enqueue(
            owner_id=owner, trigger="v2_graph", plan=_owner_plan(owner, request_id),
            build="build-a", provider_mode=V2_PROVIDER_MODE,
            operation_id=operation_id,
        )
    assert repo.claim_operation(
        first_id, owner_id="owner-a", worker_id="one",
    ) is not None
    assert repo.claim_operation(
        second_id, owner_id="owner-a", worker_id="two",
    ) is None
    assert repo.get(second_id, owner_id="owner-a").status == "pending"
    assert repo.claim_operation(
        foreign_id, owner_id="owner-b", worker_id="foreign",
    ) is not None


def test_blocked_v2_candidate_does_not_starve_legacy_claim_lane(repo):
    first_request = "d786ecdc-981b-4bed-8c3f-3ba863c90d76"
    second_request = "a5535eec-b158-4773-8e29-64f24373a95a"
    first_id = operation_id_for_request(owner_id="owner-a", request_id=first_request)
    second_id = operation_id_for_request(owner_id="owner-a", request_id=second_request)
    for request_id, operation_id in ((first_request, first_id), (second_request, second_id)):
        repo.enqueue(
            owner_id="owner-a", trigger="v2_graph",
            plan=_owner_plan("owner-a", request_id), build="build-a",
            provider_mode=V2_PROVIDER_MODE, operation_id=operation_id,
        )
    assert repo.claim_operation(
        first_id, owner_id="owner-a", worker_id="v2-first",
    ) is not None
    repo.enqueue(
        owner_id="owner-a", trigger="manual", plan={}, build="legacy",
        provider_mode="mock", operation_id="legacy-after-v2",
    )
    claimed = repo.claim_next(
        owner_id="owner-a", worker_id="mixed-lane",
        triggers=("v2_graph", "manual"),
    )
    assert claimed is not None and claimed.operation_id == "legacy-after-v2"
    assert repo.get(second_id, owner_id="owner-a").status == "pending"


def test_durable_cancellation_token_checks_every_event_and_fails_closed():
    checks = []

    def guard():
        checks.append(len(checks))
        if len(checks) == 3:
            raise RuntimeError("claim lost")

    token = DurableClaimCancellationToken(guard)
    assert token.observe()
    assert token.observe()
    assert not token.observe()
    assert token.cancelled and token.observed_events == 2 and len(checks) == 3


def test_bound_v2_takeover_fails_run_and_operation_without_reset(repo):
    from research.domain.models import ExperimentRun, ExperimentSpec, Hypothesis, ResearchProgram
    from research.domain.operations import operation_item_keys

    now = dt.datetime(2026, 8, 30, tzinfo=dt.UTC)
    request_id = "ea4f47ba-6d88-45e1-85ae-efcbd9352d82"
    plan = _owner_plan("owner-a", request_id)
    operation_id = operation_id_for_request(owner_id="owner-a", request_id=request_id)
    repo.enqueue(
        owner_id="owner-a", trigger="v2_graph", plan=plan, build="build-a",
        provider_mode=V2_PROVIDER_MODE, operation_id=operation_id, now=now,
    )
    first = repo.claim_operation(
        operation_id, owner_id="owner-a", worker_id="first", now=now,
        lease_seconds=1,
    )
    program = ResearchProgram(owner_id="owner-a", name="v2-bound", thesis="")
    repo.session.add(program); repo.session.flush()
    hypothesis = Hypothesis(owner_id="owner-a", program_id=program.id, statement="v2")
    repo.session.add(hypothesis); repo.session.flush()
    spec = ExperimentSpec(owner_id="owner-a", id="v2-bound-spec", hypothesis_id=hypothesis.id)
    repo.session.add(spec); repo.session.flush()
    run = ExperimentRun(owner_id="owner-a", spec_id=spec.id, status="running")
    repo.session.add(run); repo.session.commit()
    item_key = operation_item_keys(plan, trigger="v2_graph")[0]
    assert repo.bind_item_run(
        operation_id, owner_id="owner-a", token=first.claim_token,
        item_key=item_key, run_id=run.id, now=now,
    )
    takeover = repo.claim_operation(
        operation_id, owner_id="owner-a", worker_id="replacement",
        now=now + dt.timedelta(seconds=2),
    )
    assert takeover is not None
    assert repo.fail_bound_v2_replay(
        operation_id, owner_id="owner-a", token=takeover.claim_token,
        item_key=item_key, now=now + dt.timedelta(seconds=2),
    ) == run.id
    repo.session.expire_all()
    assert repo.session.get(ExperimentRun, run.id).status == "failed"
    assert repo.get(operation_id, owner_id="owner-a").status == "failed"
    assert repo.bound_item_run(operation_id, owner_id="owner-a", item_key=item_key) == run.id
    assert repo.claim_operation(
        operation_id, owner_id="owner-a", worker_id="third",
        now=now + dt.timedelta(seconds=3),
    ) is None


def test_v2_takeover_before_run_binding_reconstructs_exact_descriptor(repo):
    from research.domain.operations import operation_item_keys

    now = dt.datetime(2026, 8, 30, tzinfo=dt.UTC)
    request_id = "1c4ce81c-b9fa-44f0-bddc-5b8a119e1615"
    plan = _owner_plan("owner-a", request_id)
    operation_id = operation_id_for_request(owner_id="owner-a", request_id=request_id)
    repo.enqueue(
        owner_id="owner-a", trigger="v2_graph", plan=plan, build="build-a",
        provider_mode=V2_PROVIDER_MODE, operation_id=operation_id, now=now,
    )
    first = repo.claim_operation(
        operation_id, owner_id="owner-a", worker_id="first", now=now,
        lease_seconds=1,
    )
    takeover = repo.claim_operation(
        operation_id, owner_id="owner-a", worker_id="replacement",
        now=now + dt.timedelta(seconds=2), lease_seconds=60,
    )
    assert first.claim_token != takeover.claim_token
    assert takeover.attempt_count == 2
    assert parse_v2_operation_plan(takeover.plan) == plan
    item_key = operation_item_keys(plan, trigger="v2_graph")[0]
    assert repo.bound_item_run(operation_id, owner_id="owner-a", item_key=item_key) is None
    assert not repo.claim_active(
        operation_id, owner_id="owner-a", token=first.claim_token,
        now=now + dt.timedelta(seconds=2),
    )
    assert repo.claim_active(
        operation_id, owner_id="owner-a", token=takeover.claim_token,
        now=now + dt.timedelta(seconds=2),
    )


def test_concurrent_identical_v2_enqueue_race_converges(tmp_path):
    import threading
    from research.domain.base import init_research_db, make_engine, make_sessionmaker
    from research.domain.operations import ResearchOperationRepository

    engine = make_engine(str(tmp_path / "v2-enqueue-race.db"))
    init_research_db(engine)
    Session = make_sessionmaker(engine)
    request_id = "4e0d77e2-bf7d-4f63-b4a7-518481809eef"
    operation_id = operation_id_for_request(owner_id="owner-a", request_id=request_id)
    plan = _owner_plan("owner-a", request_id)
    barrier = threading.Barrier(2)
    results, errors = [], []

    def enqueue():
        try:
            with Session() as session:
                barrier.wait()
                result = ResearchOperationRepository(session).enqueue(
                    owner_id="owner-a", trigger="v2_graph", plan=plan,
                    build="build-a", provider_mode=V2_PROVIDER_MODE,
                    operation_id=operation_id,
                )
                results.append((result.operation_id, result.plan))
        except Exception as exc:  # captured for the assertion below
            errors.append(exc)

    threads = [threading.Thread(target=enqueue) for _ in range(2)]
    for thread in threads: thread.start()
    for thread in threads: thread.join(timeout=10)
    try:
        assert not errors
        assert len(results) == 2
        assert results == [(operation_id, plan), (operation_id, plan)]
        with Session() as session:
            assert len(ResearchOperationRepository(session).list(owner_id="owner-a")) == 1
    finally:
        engine.dispose()


def _bound_v2_terminal_fixture(repo, *, suffix: str):
    from research.domain.models import ExperimentRun, ExperimentSpec, Hypothesis, ResearchProgram
    from research.domain.operations import operation_item_keys

    now = dt.datetime(2026, 9, 3, 12, 0, tzinfo=dt.UTC)
    request_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"v2-terminal-{suffix}"))
    # uuid5 is not accepted client identity; retain deterministic test setup while
    # using a literal v4 shape derived from the suffix's digest bytes.
    raw = bytearray(uuid.UUID(request_id).bytes)
    raw[6] = (raw[6] & 0x0F) | 0x40
    raw[8] = (raw[8] & 0x3F) | 0x80
    request_id = str(uuid.UUID(bytes=bytes(raw)))
    plan = _owner_plan("owner-a", request_id)
    operation_id = operation_id_for_request(owner_id="owner-a", request_id=request_id)
    repo.enqueue(
        owner_id="owner-a", trigger="v2_graph", plan=plan, build="build-a",
        provider_mode=V2_PROVIDER_MODE, operation_id=operation_id, now=now,
    )
    claim = repo.claim_operation(
        operation_id, owner_id="owner-a", worker_id="worker", now=now,
        lease_seconds=60,
    )
    program = ResearchProgram(owner_id="owner-a", name=f"terminal-{suffix}", thesis="")
    repo.session.add(program); repo.session.flush()
    hypothesis = Hypothesis(owner_id="owner-a", program_id=program.id,
                            statement=f"terminal-{suffix}")
    repo.session.add(hypothesis); repo.session.flush()
    spec = ExperimentSpec(owner_id="owner-a", id=f"terminal-spec-{suffix}",
                          hypothesis_id=hypothesis.id)
    repo.session.add(spec); repo.session.flush()
    run = ExperimentRun(owner_id="owner-a", spec_id=spec.id, status="running")
    repo.session.add(run); repo.session.commit()
    item_key = operation_item_keys(plan, trigger="v2_graph")[0]
    assert repo.bind_item_run(
        operation_id, owner_id="owner-a", token=claim.claim_token,
        item_key=item_key, run_id=run.id, now=now,
    )
    return now, operation_id, claim.claim_token, item_key, run.id


def test_v2_completion_wins_atomically_and_later_cancel_is_noop(repo):
    from research.domain.models import ExperimentRun, ResearchOperationEvent, ResearchOperationItem
    from sqlalchemy import event

    now, operation_id, token, item_key, run_id = _bound_v2_terminal_fixture(
        repo, suffix="complete-first",
    )
    run = repo.session.get(ExperimentRun, run_id)
    run.status = "completed"
    run.decision = "archive"
    run.completed_at = now
    updates = []
    def record_update(_connection, _cursor, statement, *_args):
        if statement.lstrip().upper().startswith("UPDATE"):
            updates.append(statement.lower())
    event.listen(repo.session.get_bind(), "before_cursor_execute", record_update)
    try:
        assert repo.finalize_v2_operation_in_transaction(
            operation_id, owner_id="owner-a", token=token,
            item_key=item_key, run_id=run_id, now=now,
        )
    finally:
        event.remove(repo.session.get_bind(), "before_cursor_execute", record_update)
    assert "research_operation" in updates[0] and "experiment_run" not in updates[0]
    assert next(index for index, sql in enumerate(updates) if "experiment_run" in sql) > 0
    repo.session.commit()
    assert not repo.request_cancel(operation_id, owner_id="owner-a", now=now)
    repo.session.expire_all()
    operation = repo.get(operation_id, owner_id="owner-a")
    item = repo.session.get(ResearchOperationItem, ("owner-a", operation_id, item_key))
    assert operation.status == operation.stage == "completed"
    assert operation.completed_run_ids == [run_id]
    assert operation.claim_token is None and operation.completed_at == now.replace(tzinfo=None)
    assert item.status == "completed" and item.run_id == run_id
    assert repo.session.get(ExperimentRun, run_id).status == "completed"
    events = repo.session.query(ResearchOperationEvent).filter_by(
        owner_id="owner-a", operation_id=operation_id,
    ).order_by(ResearchOperationEvent.sequence).all()
    assert [event.event_type for event in events] == [
        "claimed", "item_completed", "completed",
    ]


def test_v2_cancel_wins_before_terminalization_and_no_completed_facts_escape(repo):
    from research.domain.models import ExperimentRun, ResearchOperationEvent, ResearchOperationItem

    now, operation_id, token, item_key, run_id = _bound_v2_terminal_fixture(
        repo, suffix="cancel-first",
    )
    assert repo.request_cancel(operation_id, owner_id="owner-a", now=now)
    assert not repo.finalize_v2_operation_in_transaction(
        operation_id, owner_id="owner-a", token=token,
        item_key=item_key, run_id=run_id, now=now,
    )
    repo.session.rollback(); repo.session.expire_all()
    operation = repo.get(operation_id, owner_id="owner-a")
    item = repo.session.get(ResearchOperationItem, ("owner-a", operation_id, item_key))
    assert operation.status == "cancelled" and operation.completed_run_ids == []
    assert item.status == "running"
    assert repo.session.get(ExperimentRun, run_id).status == "failed"
    events = repo.session.query(ResearchOperationEvent.event_type).filter_by(
        owner_id="owner-a", operation_id=operation_id,
    ).order_by(ResearchOperationEvent.sequence).all()
    assert [event[0] for event in events] == ["claimed", "cancelled"]


def _inject_terminal_operation_failure_after_item(repo, monkeypatch):
    original_execute = repo.session.execute
    state = {"item_transitioned": False}

    def execute(statement, *args, **kwargs):
        sql = str(statement).lstrip()
        if state["item_transitioned"] and sql.startswith(
                "UPDATE research_operation SET status"):
            state["item_transitioned"] = False
            raise RuntimeError("injected after item transition")
        result = original_execute(statement, *args, **kwargs)
        if sql.startswith("UPDATE research_operation_item SET"):
            state["item_transitioned"] = True
        return result

    monkeypatch.setattr(repo.session, "execute", execute)


def test_v2_terminal_interruption_rolls_back_item_operation_ids_and_events(
    repo, monkeypatch,
):
    from research.domain.models import ExperimentRun, ResearchOperationEvent, ResearchOperationItem

    now, operation_id, token, item_key, run_id = _bound_v2_terminal_fixture(
        repo, suffix="rollback",
    )
    run = repo.session.get(ExperimentRun, run_id)
    run.status = "completed"; run.decision = "archive"; run.completed_at = now

    _inject_terminal_operation_failure_after_item(repo, monkeypatch)
    with pytest.raises(RuntimeError, match="injected after item"):
        repo.finalize_v2_operation_in_transaction(
            operation_id, owner_id="owner-a", token=token,
            item_key=item_key, run_id=run_id, now=now,
        )
    repo.session.rollback(); repo.session.expire_all()
    operation = repo.get(operation_id, owner_id="owner-a")
    item = repo.session.get(ResearchOperationItem, ("owner-a", operation_id, item_key))
    assert operation.status == "running" and operation.completed_run_ids == []
    assert item.status == "running" and item.run_id == run_id
    assert repo.session.get(ExperimentRun, run_id).status == "running"
    events = repo.session.query(ResearchOperationEvent.event_type).filter_by(
        owner_id="owner-a", operation_id=operation_id,
    ).all()
    assert [event[0] for event in events] == ["claimed"]


def test_v2_restart_after_terminal_rollback_never_re_evaluates_or_opens_second_run(
    repo, monkeypatch,
):
    from research.domain.models import ExperimentRun

    now, operation_id, token, item_key, run_id = _bound_v2_terminal_fixture(
        repo, suffix="restart-no-replay",
    )
    run = repo.session.get(ExperimentRun, run_id)
    run.status = "completed"; run.decision = "archive"; run.completed_at = now
    _inject_terminal_operation_failure_after_item(repo, monkeypatch)
    with pytest.raises(RuntimeError):
        repo.finalize_v2_operation_in_transaction(
            operation_id, owner_id="owner-a", token=token,
            item_key=item_key, run_id=run_id, now=now,
        )
    repo.session.rollback()
    takeover_time = now + dt.timedelta(seconds=61)
    takeover = repo.claim_operation(
        operation_id, owner_id="owner-a", worker_id="replacement",
        now=takeover_time, lease_seconds=60,
    )
    assert takeover is not None
    before_runs = repo.session.query(ExperimentRun).count()
    assert repo.fail_bound_v2_replay(
        operation_id, owner_id="owner-a", token=takeover.claim_token,
        item_key=item_key, now=takeover_time,
    ) == run_id
    assert repo.session.query(ExperimentRun).count() == before_runs == 1
    assert repo.session.get(ExperimentRun, run_id).status == "failed"
    assert repo.get(operation_id, owner_id="owner-a").status == "failed"


def test_v2_terminal_wiring_has_no_reviewer_split_commit_counterexample():
    import ast
    from pathlib import Path

    backend = Path(__file__).parents[1]
    executor = (backend / "research/orchestrator/v2_operation.py").read_text()
    dispatcher = (backend / "scripts/research_run.py").read_text()
    assert "recorder.finalize_v2_operation_in_transaction" in executor
    assert "recorder.finalize_item_in_transaction(item_key, run_id)" not in executor
    tree = ast.parse(dispatcher)
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    v2_branch = next(node for node in ast.walk(functions["_run_enabled_operation"])
        if isinstance(node, ast.If) and ast.unparse(node.test) == "claimed.trigger == 'v2_graph'")
    assert len(v2_branch.body) == 1 and isinstance(v2_branch.body[0], ast.Return)
    assert ast.unparse(v2_branch.body[0].value.func) == "_run_claimed_v2"
    calls = {ast.unparse(node.func) for node in ast.walk(functions["_run_claimed_v2"]) if isinstance(node, ast.Call)}
    assert "recorder.complete" not in calls
    assert "recorder.close_watchdog" in calls


def _preparation_plan():
    from research.orchestrator.v2_preparation import build_preparation_plan, execution_policy
    old = _item()
    return build_preparation_plan({
        "owner_id": "owner-a", "request_id": old["request_id"], "project_id": old["project_id"],
        "graph_identifier": old["graph_identifier"], "graph_version": old["graph_version"],
        "content_address": old["content_address"], "graph_address": old["graph_address"],
        "registry_snapshot_address": old["phase4_binding"]["registry_snapshot_address"],
        "dataset_manifest_address": old["dataset_manifest_address"], "dataset_as_of": old["dataset_as_of"],
        "experiment": old["experiment"], "execution_policy": execution_policy(old["experiment"]["research_capital"]),
    })


def test_public_preparation_keeps_one_real_item_and_no_client_admission():
    from research.orchestrator.v2_preparation import parse_preparation_plan
    from research.domain.operations import operation_item_keys
    plan = _preparation_plan()
    assert parse_preparation_plan(plan) == plan
    assert len(operation_item_keys(plan, trigger="v2_graph")) == 1
    assert "admission_address" not in plan["v2_graphs"][0]
    changed = copy.deepcopy(plan)
    changed["v2_graphs"][0]["execution_policy"]["risk"]["capital"] += 1
    with pytest.raises(V2OperationRefusal):
        parse_preparation_plan(changed)
    changed = copy.deepcopy(plan)
    changed["v2_graphs"][0]["admission_address"] = "sha256:" + "1" * 64
    with pytest.raises(V2OperationRefusal):
        parse_preparation_plan(changed)


def test_preparation_null_evidence_and_owner_cancel_fence(repo):
    plan = _preparation_plan()
    request_id = plan["v2_graphs"][0]["request_id"]
    operation_id = operation_id_for_request(owner_id="owner-a", request_id=request_id)
    repo.enqueue(owner_id="owner-a", trigger="v2_graph", plan=plan, build="b",
                 provider_mode=V2_PROVIDER_MODE, operation_id=operation_id)
    assert repo.preparation_evidence(operation_id, owner_id="owner-a") is None
    with pytest.raises(ValueError, match="unavailable"):
        repo.preparation_evidence(operation_id, owner_id="owner-b")
    claimed = repo.claim_next(owner_id="owner-a", worker_id="worker")
    repo.request_cancel(operation_id, owner_id="owner-a")
    with pytest.raises(RuntimeError, match="claim was lost"):
        repo.lock_preparation(operation_id, owner_id="owner-a", token=claimed.claim_token)
    repo.session.rollback()


@pytest.mark.parametrize("changed", [False, True])
def test_v2_enqueue_reconciles_real_unique_conflict_after_stale_read(repo, monkeypatch, changed):
    from research.domain.models import ResearchOperationItem
    from sqlalchemy import select, func
    request_id = "7ca7b810-9dad-4d80-80b4-00c04fd430c8"
    operation_id = operation_id_for_request(owner_id="owner-a", request_id=request_id)
    original = _owner_plan("owner-a", request_id)
    repo.enqueue(owner_id="owner-a", trigger="v2_graph", plan=original, build="b",
                 provider_mode=V2_PROVIDER_MODE, operation_id=operation_id)
    repo.session.expunge_all()
    # Force the stale-read interleaving; the actual unique constraint must reject the insert.
    monkeypatch.setattr(repo, "_queued_retry", lambda _row: None)
    plan = _owner_plan("owner-a", request_id, hypothesis="changed") if changed else original
    def enqueue():
        return repo.enqueue(owner_id="owner-a", trigger="v2_graph", plan=plan, build="b",
                            provider_mode=V2_PROVIDER_MODE, operation_id=operation_id)
    if changed:
        with pytest.raises(V2OperationRefusal, match="reused"):
            enqueue()
    else:
        assert enqueue().operation_id == operation_id
    assert repo.get(operation_id, owner_id="owner-a").plan == original
    assert repo.session.scalar(select(func.count()).select_from(ResearchOperationItem)) == 1


def test_v2_enqueue_refuses_a_foreign_owner_descriptor(repo):
    request_id = "7ca7b810-9dad-4d80-80b4-00c04fd430c8"
    operation_id = operation_id_for_request(owner_id="owner-a", request_id=request_id)
    with pytest.raises(ValueError, match="identity or mode"):
        repo.enqueue(owner_id="owner-a", trigger="v2_graph", plan=_owner_plan("owner-b", request_id),
                     build="b", provider_mode=V2_PROVIDER_MODE, operation_id=operation_id)
    assert repo.get(operation_id, owner_id="owner-a") is None


@pytest.mark.parametrize("point", [[], (), (None,),
    ({"node_id":"n","parameter_id":"p","value":1}, {"node_id":"n","parameter_id":"p","value":2}),
    ({"node_id":"z","parameter_id":"p","value":1}, {"node_id":"a","parameter_id":"p","value":2}),
])
def test_parameter_candidate_rejects_malformed_or_ambiguous_commands(point):
    from research.orchestrator.v2_operation import _candidate_commands
    with pytest.raises(V2OperationRefusal, match="V2_PARAMETER_CANDIDATE_INVALID"):
        _candidate_commands(point)


@pytest.mark.parametrize("revocation", ["cancel", "expiry", "watchdog"])
def test_admission_publication_fence_observes_actual_lease_and_cancel(repo, revocation):
    from research.domain.models import ResearchOperation
    from research.domain.operations import DurableOperationRecorder
    from research.orchestrator.v2_preparation import _publication_fence
    request_id = "8ca7b810-9dad-4d80-80b4-00c04fd430c8"
    operation_id = operation_id_for_request(owner_id="owner-a", request_id=request_id)
    repo.enqueue(owner_id="owner-a", trigger="v2_graph", plan=_owner_plan("owner-a", request_id),
                 build="b", provider_mode=V2_PROVIDER_MODE, operation_id=operation_id)
    claim = repo.claim_operation(operation_id, owner_id="owner-a", worker_id="publication")
    recorder = DurableOperationRecorder(repo, owner_id="owner-a", operation_id=operation_id, token=claim.claim_token)
    _publication_fence(recorder, repo)
    repo.session.rollback()
    if revocation == "cancel":
        assert repo.request_cancel(operation_id, owner_id="owner-a")
    elif revocation == "watchdog":
        recorder.start_watchdog(lambda *_args: False, interval_seconds=0.001)
        assert recorder._claim_lost.wait(1)
        recorder.close_watchdog()
        assert repo.claim_active(operation_id, owner_id="owner-a", token=claim.claim_token)
    else:
        row = repo.session.get(ResearchOperation, ("owner-a", operation_id))
        row.claim_expires_at = dt.datetime.now(dt.UTC).replace(tzinfo=None) - dt.timedelta(seconds=1)
        repo.session.commit()
    with pytest.raises(RuntimeError, match="claim was lost"):
        _publication_fence(recorder, repo)
    repo.session.rollback()


def test_admission_publication_has_short_fences_at_both_commit_boundaries():
    import ast
    from research.orchestrator.v2_preparation import _publish_admission
    function = ast.parse(inspect.getsource(_publish_admission)).body[0]
    transaction = next(node for node in function.body if isinstance(node, ast.Try))
    def call_name(node):
        call = node.value
        return call.func.id if isinstance(call.func, ast.Name) else f"{call.func.value.id}.{call.func.attr}"
    assert [call_name(node) for node in transaction.body] == [
        "put", "_publication_fence", "execution_session.commit", "research_session.commit",
        "store_admission", "_publication_fence", "research_session.commit",
    ]
    rollback = transaction.handlers[0].body
    assert [call_name(node) for node in rollback[:-1]] == ["execution_session.rollback", "research_session.rollback"]
    assert isinstance(rollback[-1], ast.Raise)


def test_admission_publication_rejects_a_different_research_transaction():
    from types import SimpleNamespace
    from research.orchestrator.v2_preparation import _publish_admission
    with pytest.raises(V2OperationRefusal, match="transaction does not match"):
        _publish_admission(None, None, SimpleNamespace(session=object()), None, object())


def test_preparation_evidence_byte_bound_precedes_json_parsing(monkeypatch):
    import json
    from research.orchestrator.v2_preparation import decode_preparation_evidence, MAX_EVIDENCE_BYTES
    def forbidden_parse(_raw):
        raise AssertionError("oversized evidence reached JSON parsing")
    with monkeypatch.context() as patch:
        patch.setattr(json, "loads", forbidden_parse)
        with pytest.raises(V2OperationRefusal, match="could not be verified"):
            decode_preparation_evidence('"' + 'x' * MAX_EVIDENCE_BYTES + '"', {})


def _settings_preparation_plan(*, risk_policy="none"):
    from research.domain.settings import _document, _view, PLATFORM_DEFAULTS, resolve_snapshot
    from research.orchestrator.v2_preparation import build_settings_preparation_plan, execution_policy
    old = _preparation_plan()["v2_graphs"][0]
    snapshot = resolve_snapshot(owner_id=old["owner_id"], graph_identifier=old["graph_identifier"],
        workspace=_view(_document(old["owner_id"], None, 0, 0, None, PLATFORM_DEFAULTS, True)),
        strategy=_view(_document(old["owner_id"], old["graph_identifier"], 0, 0, None, {}, True)),
        run_overrides={**{key: value for key, value in old["experiment"].items() if key != "hypothesis"}, "risk_policy": risk_policy})
    return build_settings_preparation_plan({**{key: value for key, value in old.items()
        if key not in {"descriptor_address", "resource_policy_address", "runtime_contract_addresses"}},
        "settings_snapshot": snapshot,
        "execution_policy": execution_policy(old["experiment"]["research_capital"], risk_policy)})


def test_settings_preparation_reconstructs_snapshot_and_preserves_prior_schema():
    from research.orchestrator.v2_preparation import parse_preparation_plan, parse_settings_preparation_plan
    from research.domain.operations import operation_item_keys
    plan = _settings_preparation_plan()
    assert parse_settings_preparation_plan(plan) == plan
    assert len(operation_item_keys(plan, trigger="v2_graph")) == 1
    assert parse_preparation_plan(_preparation_plan())["schema"].endswith("/2")
    with pytest.raises(V2OperationRefusal):
        parse_preparation_plan(plan)
    changed = copy.deepcopy(plan)
    item = changed["v2_graphs"][0]
    item["settings_snapshot"]["values"]["seed"] += 1
    item["descriptor_address"] = content_address({key: value for key, value in item.items() if key != "descriptor_address"})
    changed["content_address"] = content_address({key: value for key, value in changed.items() if key != "content_address"})
    with pytest.raises(V2OperationRefusal, match="pinned research settings"):
        parse_settings_preparation_plan(changed)


@pytest.mark.parametrize("risk_policy", ["none", "pine-v4-ratchet/1"])
def test_existing_execution_policy_retains_exact_legacy_risk_document(risk_policy):
    from research.orchestrator.v2_preparation import execution_policy, _plain
    from research.strategy.v2_runtime_strategy import risk_policy_document
    policy = execution_policy(50000.0, risk_policy)
    assert policy["schema"] == "v2-research-execution-policy/1"
    assert policy["risk"] == {"schema": "research-risk-assumption/1", "risk_policy": risk_policy,
        "overlay": _plain(risk_policy_document(risk_policy)), "capital": 50000.0,
        "sizing_model": "one_lot_or_cash_budget_v1", "fill": "existing-next-bar-open"}
    assert "replay_policy" not in policy["risk"]["overlay"]


def test_reversal_settings_pin_actual_fixed_unit_fill_policy():
    from research.orchestrator.v2_preparation import parse_settings_preparation_plan
    plan = _settings_preparation_plan(risk_policy="pine-v4-reversal/1")
    descriptor = parse_settings_preparation_plan(plan)["v2_graphs"][0]
    risk = descriptor["execution_policy"]["risk"]
    from research.domain.settings import fixed_assumptions
    assert fixed_assumptions("pine-v4-reversal/1")["sizing_model"] == "fixed_unit_v1"
    assert fixed_assumptions("pine-v4-reversal/1")["fill"] == "next-bar-open-reversal/1"
    assert risk["sizing_model"] == "fixed_unit_v1"
    assert risk["fill"] == "next-bar-open-reversal/1"
    assert risk["overlay"]["schema"] == "v2-research-risk-policy/2"
    assert risk["overlay"]["replay_policy"] == "pine-reversal-fixed-unit/1"
    assert descriptor["settings_snapshot"]["values"]["risk_policy"] == "pine-v4-reversal/1"
    assert descriptor["settings_snapshot"]["sources"]["risk_policy"] == "run"
    assert plan["content_address"] != _settings_preparation_plan()["content_address"]


def _input_set_preparation_plan():
    from research.orchestrator.v2_preparation import build_input_set_preparation_plan
    old = _settings_preparation_plan()["v2_graphs"][0]
    item = {key: value for key, value in old.items() if key not in {
        "dataset_manifest_address", "resource_policy_address", "runtime_contract_addresses", "descriptor_address"}}
    item.update(primary_input="frame", input_datasets=[
        {"graph_input_id": "benchmark", "dataset_manifest_address": "sha256:" + "7" * 64},
        {"graph_input_id": "frame", "dataset_manifest_address": old["dataset_manifest_address"]}])
    return build_input_set_preparation_plan(item)


def test_input_set_preparation_is_closed_and_preserves_scalar_versions():
    from research.domain.operations import operation_item_keys
    from research.orchestrator.v2_preparation import parse_public_preparation_plan
    from research.evaluation.v2_resource_policy import V0_V2_INPUT_SET_RESOURCE_POLICY_ADDRESS
    plan = _input_set_preparation_plan()
    assert parse_public_preparation_plan(plan) == plan
    assert plan["schema"] == "v2-graph-research-operation/4"
    assert len(operation_item_keys(plan, trigger="v2_graph")) == 1
    item = plan["v2_graphs"][0]
    assert "dataset_manifest_address" not in item and "admission_address" not in item
    assert item["resource_policy_address"] == V0_V2_INPUT_SET_RESOURCE_POLICY_ADDRESS
    assert item["settings_snapshot"] == _settings_preparation_plan()["v2_graphs"][0]["settings_snapshot"]
    assert parse_public_preparation_plan(_preparation_plan())["schema"].endswith("/2")
    assert parse_public_preparation_plan(_settings_preparation_plan())["schema"].endswith("/3")


@pytest.mark.parametrize("fault", ["duplicate_input", "duplicate_manifest", "reordered", "primary", "scalar",
                                    "settings", "as_of", "legacy_policy", "extra"])
def test_input_set_preparation_refuses_rehashed_wrong_selection(fault):
    from research.orchestrator.v2_preparation import parse_public_preparation_plan
    plan = _input_set_preparation_plan(); item = plan["v2_graphs"][0]
    rows = item["input_datasets"]
    if fault == "duplicate_input": rows[1]["graph_input_id"] = rows[0]["graph_input_id"]
    elif fault == "duplicate_manifest": rows[1]["dataset_manifest_address"] = rows[0]["dataset_manifest_address"]
    elif fault == "reordered": rows.reverse()
    elif fault == "primary": item["primary_input"] = "absent"
    elif fault == "scalar": rows.pop()
    elif fault == "settings": item["settings_snapshot"]["values"]["seed"] += 1
    elif fault == "as_of": item["dataset_as_of"] = "2026-09-05T00:00:00"
    elif fault == "legacy_policy": item["resource_policy_address"] = _preparation_plan()["v2_graphs"][0]["resource_policy_address"]
    else: rows[0]["owner_id"] = "owner-b"
    item["descriptor_address"] = content_address({key: value for key, value in item.items() if key != "descriptor_address"})
    plan["content_address"] = content_address({key: value for key, value in plan.items() if key != "content_address"})
    with pytest.raises(V2OperationRefusal):
        parse_public_preparation_plan(plan)


def test_input_set_queue_retry_recovery_and_cancel_preserve_pinned_selection(repo):
    from research.domain.operations import operation_item_keys
    plan = _input_set_preparation_plan()
    request = plan["v2_graphs"][0]["request_id"]
    identity = operation_id_for_request(owner_id="owner-a", request_id=request)
    args = dict(owner_id="owner-a", trigger="v2_graph", plan=plan, build="build",
                provider_mode=V2_PROVIDER_MODE, operation_id=identity)
    first = repo.enqueue(**args)
    repeated = repo.enqueue(**args)
    assert repeated == first and repeated.plan == plan
    now = dt.datetime.now(dt.UTC)
    first_claim = repo.claim_operation(identity, owner_id="owner-a", worker_id="input-set-worker", now=now, lease_seconds=1)
    claim = repo.claim_operation(identity, owner_id="owner-a", worker_id="replacement", now=now + dt.timedelta(seconds=2))
    assert first_claim.claim_token != claim.claim_token and claim.attempt_count == 2
    assert claim.plan["v2_graphs"][0]["input_datasets"] == plan["v2_graphs"][0]["input_datasets"]
    assert len(operation_item_keys(claim.plan, trigger="v2_graph")) == 1
    assert repo.get(identity, owner_id="owner-b") is None
    repo.request_cancel(identity, owner_id="owner-a")
    with pytest.raises(RuntimeError, match="claim was lost"):
        repo.lock_preparation(identity, owner_id="owner-a", token=claim.claim_token)


def test_input_set_resource_budget_counts_every_source():
    from types import SimpleNamespace
    from research.orchestrator.v2_operation import _projection_resource_admission
    from research_tests.test_v2_resource_policy import _plan
    from research.evaluation.v2_resource_policy import V2ResourceAdmissionRefused
    segment = SimpleNamespace(row_start=0, row_end=1000)
    def source(label):
        return SimpleNamespace(manifest=SimpleNamespace(manifest_address=content_address(label),
            aggregate_byte_length=4194304), segments=(segment,))
    projection = SimpleNamespace(input_sources={"frame": source("a"), "benchmark": source("b")},
        manifest=source("a").manifest, availability_index=range(1000))
    repo = SimpleNamespace(running_v2_count=lambda **kwargs: 1)
    admitted = _projection_resource_admission(_plan(), SimpleNamespace(bar_count=1000), projection, {}, repo, "owner-a")
    assert admitted.observed_dimensions["total_rows"] == 2000
    assert admitted.observed_dimensions["total_bytes"] == 8388608
    segment.row_end = 1001
    with pytest.raises(V2ResourceAdmissionRefused, match="total_rows"):
        _projection_resource_admission(_plan(), SimpleNamespace(bar_count=1001), projection, {}, repo, "owner-a")


def _input_set_gate_graph(registry):
    from research_tests.test_v2_graph_experiment_bridge import _saved_v2_boolean_graph
    graph = _saved_v2_boolean_graph(registry)
    graph["graph_inputs"].append({**graph["graph_inputs"][0], "port_id": "benchmark"})
    graph["nodes"].extend([
        {"node_id": "benchmark_rising", "component": {"component_id": "analytical.rising", "component_version": 2}, "parameters": {"window": 2}},
        {"node_id": "allow", "component": {"component_id": "strategy_math.and", "component_version": 1}, "parameters": {}},
    ])
    next(edge for edge in graph["edges"] if edge["edge_id"] == "rising-entry")["source"]["node_id"] = "allow"
    for identity, source, target in [
        ("benchmark-rising", {"scope": "graph_input", "port_id": "benchmark"}, {"scope": "node", "node_id": "benchmark_rising", "port_id": "frame"}),
        ("primary-allow", {"scope": "node", "node_id": "rising", "port_id": "value"}, {"scope": "node", "node_id": "allow", "port_id": "left"}),
        ("benchmark-allow", {"scope": "node", "node_id": "benchmark_rising", "port_id": "value"}, {"scope": "node", "node_id": "allow", "port_id": "right"}),
    ]:
        graph["edges"].append({"edge_id": identity, "source": source, "target": target, "binding": {"kind": "single"}})
    return graph


def _input_set_fixture_prices(count, *, primary, search):
    if not primary:
        return [200 + (index % 8 if index % 8 < 4 else 8 - index % 8) for index in range(count)]
    if not search:
        return [100 + index for index in range(count)]
    result, price = [], 100.0
    for index in range(count):
        price += 3.0 + (index // 10) % 3 * .1 if index % 10 < 8 else -1.5
        result.append(price)
    return result


def _persist_input_set_csv(execution, research, *, search=False):
    from research.data.user_csv_import import CsvColumnMapping, UserCsvSpec, persist_user_csv
    observed = dt.datetime(2026, 4, 1, tzinfo=dt.UTC)
    count = 240 if search else 64
    start = dt.date(2025 if search else 2026, 1, 1)
    days = [start + dt.timedelta(days=index) for index in range(count * 2)]
    days = [day for day in days if day.weekday() < 5][:count]
    imported, closes = {}, {}
    for name, symbol, asset in [("frame", "SELF", "EQUITY"), ("benchmark", "IDX", "INDEX")]:
        volume = asset == "EQUITY"
        prices = _input_set_fixture_prices(count, primary=volume, search=search)
        rows = ["Symbol,Date,Open,High,Low,Close" + (",Volume" if volume else "")]
        for day, price in zip(days, prices, strict=True):
            rows.append(f"{symbol},{day.isoformat()},{price},{price+2},{price-1},{price+1}" + (",1000" if volume else ""))
        imported[name] = persist_user_csv(execution, research, owner_id="owner-a", project_id="project-v2",
            raw=("\n".join(rows) + "\n").encode(), observed_at=observed,
            spec=UserCsvSpec("Synthetic input-set CSV", f"user-csv:XNSE:{asset}:{symbol}", "1", symbol, symbol, "XNSE", asset,
                CsvColumnMapping("Symbol", "Date", "Open", "High", "Low", "Close", "Volume" if volume else None), date_format="%Y-%m-%d"))
        closes[name] = [price + 1 for price in prices]
    execution.commit(); research.commit()
    return imported, closes


def _persist_input_set_graph(execution, registry):
    from app.db.models import GraphArtifact, Organization, Project
    from app.editor import v2_editor_store
    graph = _input_set_gate_graph(registry)
    if execution.get(Organization, "owner-a") is None:
        execution.add(Organization(organization_id="owner-a", name="Synthetic owner"))
    execution.add(Project(owner_id="owner-a", project_id="project-v2", name="Input-set test"))
    execution.add(GraphArtifact(owner_id="owner-a", identifier=graph["strategy_id"], project_id="project-v2",
        display_name="Primary and benchmark gate", draft_json=canonical_json(graph), draft_revision=0))
    execution.commit()
    v2_editor_store.publish("project-v2", graph["strategy_id"], base_revision=0, expected_current_version=None, owner_id="owner-a")
    return v2_editor_store.read_version("project-v2", graph["strategy_id"], 1, owner_id="owner-a")


def _real_input_set_plan(saved, imported):
    from research.domain.settings import _document, _view, PLATFORM_DEFAULTS, resolve_snapshot
    from research.orchestrator.v2_preparation import build_input_set_preparation_plan
    item = _input_set_preparation_plan()["v2_graphs"][0]
    item = {key: value for key, value in item.items() if key not in {
        "descriptor_address", "resource_policy_address", "runtime_contract_addresses"}}
    item.update(project_id="project-v2", graph_identifier=saved["graph_identifier"], graph_version=saved["graph_version"],
        content_address=saved["content_address"], graph_address=saved["graph_address"], registry_snapshot_address=saved["registry_snapshot_address"],
        dataset_as_of=max(row.ready_as_of for row in imported.values()).isoformat(),
        input_datasets=[{"graph_input_id": name, "dataset_manifest_address": row.manifest.manifest_address} for name, row in sorted(imported.items())])
    item["settings_snapshot"] = resolve_snapshot(owner_id="owner-a", graph_identifier=saved["graph_identifier"],
        workspace=_view(_document("owner-a", None, 0, 0, None, PLATFORM_DEFAULTS, True)),
        strategy=_view(_document("owner-a", saved["graph_identifier"], 0, 0, None, {}, True)),
        run_overrides={**{key: value for key, value in item["experiment"].items() if key != "hypothesis"}, "risk_policy": "none"})
    return build_input_set_preparation_plan(item)


@pytest.fixture
def input_set_worker(tmp_path, monkeypatch, request):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.db.models import Base
    from app.editor import v2_editor_store
    from app.ir.library import REGISTRY
    from app.core.config import get_settings
    from research.domain.base import init_research_db
    import app.db.session as execution_db
    import scripts.research_run as research_run
    execution_engine = create_engine(f"sqlite:///{tmp_path / 'execution.db'}")
    research_path = str(tmp_path / "research.db")
    research_engine = create_engine(f"sqlite:///{research_path}")
    Base.metadata.create_all(execution_engine); init_research_db(research_engine)
    Execution = sessionmaker(execution_engine, expire_on_commit=False)
    Research = sessionmaker(research_engine, expire_on_commit=False)
    monkeypatch.setattr(v2_editor_store, "SessionLocal", Execution)
    monkeypatch.setattr(execution_db, "SessionLocal", Execution)
    monkeypatch.setattr(get_settings(), "owner_id", "owner-a")
    monkeypatch.setattr(get_settings(), "research_enabled", True)
    monkeypatch.setenv("PT_RESEARCH_OWNER_ID", "owner-a")
    monkeypatch.setenv("PT_RESEARCH_DB_PATH", research_path)
    monkeypatch.setattr(research_run, "_git_commit", lambda: "test-build")
    try:
        with Execution() as es, Research() as rs:
            imported, closes = _persist_input_set_csv(es, rs, search=getattr(request, "param", False))
            saved = _persist_input_set_graph(es, REGISTRY)
        yield Execution, Research, research_path, _real_input_set_plan(saved, imported), closes
    finally:
        execution_engine.dispose(); research_engine.dispose()


def _assert_input_set_gate(result, closes):
    values = result.batch_outputs["entry"]
    expected = [all(closes[name][index-2] < closes[name][index-1] < closes[name][index] for name in ("frame", "benchmark"))
                for index in range(2, len(closes["frame"]))]
    assert [row.value for row in values.iloc[2:]] == expected
    assert any(expected) and not all(expected)
    assert result.batch_output_document == result.incremental_output_document


@pytest.mark.parametrize("percentage_exits", [False, True])
def test_real_input_set_preparation_worker_recovers_with_source_lineage(input_set_worker, monkeypatch, percentage_exits):
    import json
    from sqlalchemy import func, select
    from research.domain.models import ExperimentRun, ExperimentSpec, ResearchDatasetManifestV2
    from research.domain.operations import ResearchOperationRepository
    from research.domain.settings import ResearchSettingsRepository
    from research_tests.test_v2_graph_experiment_bridge import _interrupt_preparation_after_execution_receipt
    import research.evaluation.phase5_runtime as runtime
    import scripts.research_run as research_run
    Execution, Research, path, plan, closes = input_set_worker
    if percentage_exits:
        from research.domain.settings import resolve_snapshot
        from research.orchestrator.v2_preparation import build_input_set_preparation_plan, execution_policy
        original = plan["v2_graphs"][0]
        snapshot = original["settings_snapshot"]
        updated = resolve_snapshot(owner_id=original["owner_id"], graph_identifier=original["graph_identifier"],
            workspace=snapshot["workspace"], strategy=snapshot["strategy"],
            run_overrides={**snapshot["run_overrides"], "stop_loss_pct": .01, "take_profit_pct": .02})
        fields = {key: value for key, value in original.items() if key not in {
            "descriptor_address", "resource_policy_address", "runtime_contract_addresses"}}
        plan = build_input_set_preparation_plan({**fields, "settings_snapshot": updated,
            "execution_policy": execution_policy(original["experiment"]["research_capital"],
                stop_loss_pct=.01, take_profit_pct=.02)})
    import research.orchestrator.run as experiment_runner
    actual_experiment = experiment_runner.run_experiment
    observed_bands = []
    def observed_experiment(*args, **kwargs):
        band = kwargs["strategy"].protective_band_document
        observed_bands.append(band)
        if percentage_exits:
            assert band["stop_loss_pct"] == .01 and band["take_profit_pct"] == .02
        else:
            assert band is None
        return actual_experiment(*args, **kwargs)
    monkeypatch.setattr(experiment_runner, "run_experiment", observed_experiment)
    item = plan["v2_graphs"][0]
    identifier = operation_id_for_request(owner_id="owner-a", request_id=item["request_id"])
    with Research() as rs:
        ResearchOperationRepository(rs).enqueue(owner_id="owner-a", trigger="v2_graph", plan=plan,
            build="test-build", provider_mode=V2_PROVIDER_MODE, operation_id=identifier)
    results, projections = [], []
    actual_execute = runtime.execute_research
    def observed_execute(*args, **kwargs):
        result = actual_execute(*args, **kwargs)
        _assert_input_set_gate(result, closes)
        results.append(result)
        projections.append(args[3])
        return result
    monkeypatch.setattr(runtime, "execute_research", observed_execute)
    monkeypatch.setattr(ResearchSettingsRepository, "read", lambda *_args, **_kwargs: pytest.fail("worker read mutable settings"))
    _interrupt_preparation_after_execution_receipt(identifier, "owner-a", Execution, Research, monkeypatch)
    reports, mode = research_run._run_enabled_operation(path)
    assert mode == V2_PROVIDER_MODE and len(reports) == 1 and len(results) >= 3
    assert len(observed_bands) == 1
    with Research() as rs:
        repository = ResearchOperationRepository(rs)
        operation = repository.get(identifier, owner_id="owner-a")
        assert operation.status == "completed" and operation.completed_run_ids == [reports[0]["run_id"]]
        assert repository.get(identifier, owner_id="owner-b") is None
        evidence = repository.preparation_evidence(identifier, owner_id="owner-a")
        assert evidence["schema"] == "v2-research-preparation-evidence/2"
        from research.orchestrator.v2_preparation import validate_preparation_evidence
        legacy = copy.deepcopy(evidence); legacy["schema"] = "v2-research-preparation-evidence/1"
        legacy["documents"].pop("dataset_selection")
        legacy["evidence_address"] = content_address({key: value for key, value in legacy.items() if key != "evidence_address"})
        with pytest.raises(V2OperationRefusal, match="Legacy preparation"):
            validate_preparation_evidence(legacy)
        assert evidence["documents"]["parity"]["schema"] == "phase5-research-run-result/2"
        assert evidence["documents"]["dataset_selection"]["primary_input"] == "frame"
        assert rs.scalar(select(func.count()).select_from(ResearchDatasetManifestV2)) == 2
        assert rs.scalar(select(func.count()).select_from(ExperimentRun)) == 1
        spec = rs.get(ExperimentSpec, ("owner-a", reports[0]["spec_id"]))
        lineage = json.loads(spec.recipe_json)["graph_provenance"]
        assert lineage["schema"] == "saved-v2-graph-research-provenance/2"
        assert lineage["execution_policy"] == item["execution_policy"]
        assert lineage["phase4_binding"]["dataset_set_address"] == evidence["addresses"]["dataset_address"]
        assert lineage["position_map_address"] == projections[-1].input_sources["frame"].position_map_address
        assert lineage["input_set_position_map_address"] == projections[-1].position_map_address
        assert lineage["position_map_address"] != lineage["input_set_position_map_address"]
        assert lineage["source_policies"] == evidence["documents"]["evaluation_policy"]["source_policies"]
        assert len({row["dataset_manifest_address"] for row in lineage["source_policies"].values()}) == 2
        bindings = evidence["documents"]["input"]["input_bindings"]["inputs"]
        assert "VOLUME" in bindings["frame"]["binding"]["fields"]
        assert "VOLUME" not in bindings["benchmark"]["binding"]["fields"]


@pytest.mark.parametrize("warmup", [59, 60, 61])
def test_eligibility_interval_explains_exhausted_warmup(warmup):
    from research.orchestrator.v2_operation import _eligibility_interval
    start = dt.datetime(2026, 4, 1, tzinfo=dt.UTC)
    end = start + dt.timedelta(seconds=60)
    if warmup < 60:
        assert _eligibility_interval(start, end, warmup) == (start + dt.timedelta(seconds=warmup), end)
        return
    with pytest.raises(V2OperationRefusal) as refused:
        _eligibility_interval(start, end, warmup)
    assert refused.value.code == "V2_DATASET_INELIGIBLE"
    assert "No evaluation interval remains" in str(refused.value)
    assert "more matching history" in str(refused.value)
    assert "shorten the lookback and save a new strategy version" in str(refused.value)


@pytest.mark.parametrize("invalid", ["naive_time", "early_cutoff"])
def test_eligibility_interval_retains_canonical_request_validation(invalid):
    from research.orchestrator.v2_operation import _eligibility_interval
    from app.market_data.eligibility import EligibilityRequest
    start = dt.datetime(2026, 4, 1, tzinfo=dt.UTC)
    if invalid == "naive_time":
        start = start.replace(tzinfo=None)
    requested_start, requested_end = _eligibility_interval(start, start + dt.timedelta(seconds=60), 30)
    cutoff = requested_end if invalid == "naive_time" else requested_start
    with pytest.raises(ValueError) as refused:
        EligibilityRequest("owner-a", "RESEARCH", requested_start, requested_end, cutoff)
    assert not isinstance(refused.value, V2OperationRefusal)


def test_percentage_settings_bind_preparation_and_adapter_without_changing_experiment():
    from research.domain.settings import resolve_snapshot
    from research.orchestrator.v2_preparation import build_settings_preparation_plan, execution_policy
    from research.orchestrator.v2_operation import _adapter_settings
    original = _settings_preparation_plan()["v2_graphs"][0]
    snapshot = original["settings_snapshot"]
    updated = resolve_snapshot(owner_id=original["owner_id"], graph_identifier=original["graph_identifier"],
        workspace=snapshot["workspace"], strategy=snapshot["strategy"],
        run_overrides={**snapshot["run_overrides"], "stop_loss_pct": .01, "take_profit_pct": .02})
    item = {key: value for key, value in original.items() if key not in {
        "descriptor_address", "resource_policy_address", "runtime_contract_addresses"}}
    policy = execution_policy(original["experiment"]["research_capital"], stop_loss_pct=.01, take_profit_pct=.02)
    plan = build_settings_preparation_plan({**item, "settings_snapshot": updated, "execution_policy": policy})
    from types import SimpleNamespace
    from app.api.ir_experiment_routes import _settings_preparation_plan as api_plan
    body = SimpleNamespace(dataset_as_of=dt.datetime.fromisoformat(original["dataset_as_of"]),
        dataset_manifest_address=original["dataset_manifest_address"], request_id=original["request_id"],
        hypothesis=original["experiment"]["hypothesis"])
    assert api_plan(original, body, updated, owner_id=original["owner_id"],
        project_id=original["project_id"], identifier=original["graph_identifier"], version=original["graph_version"]) == plan
    pinned = plan["v2_graphs"][0]
    assert pinned["experiment"] == original["experiment"]
    assert pinned["execution_policy"]["schema"] == "v2-research-execution-policy/2"
    assert _adapter_settings(pinned)["stop_loss_pct"] == .01
    assert _adapter_settings(pinned)["take_profit_pct"] == .02
    assert pinned["descriptor_address"] != original["descriptor_address"]
    with pytest.raises(V2OperationRefusal, match="pinned settings"):
        build_settings_preparation_plan({**item, "settings_snapshot": updated,
            "execution_policy": execution_policy(original["experiment"]["research_capital"])})


def test_legacy_zero_revision_preparation_retry_uses_exact_frozen_snapshot():
    from types import SimpleNamespace
    from research.domain.settings import LEGACY_DEFAULTS, _document, _view, resolve_snapshot
    from research.orchestrator.v2_preparation import build_settings_preparation_plan
    from app.api.ir_experiment_routes import _preparation_settings_snapshot
    old = _preparation_plan()["v2_graphs"][0]
    overrides = {**old["experiment"], "risk_policy": "none"}
    overrides.pop("hypothesis")
    snapshot = resolve_snapshot(owner_id=old["owner_id"], graph_identifier=old["graph_identifier"],
        workspace=_view(_document(old["owner_id"], None, 0, 0, None, LEGACY_DEFAULTS, True,
            schema="research-settings-revision/1")),
        strategy=_view(_document(old["owner_id"], old["graph_identifier"], 0, 0, None, {}, True,
            schema="research-settings-revision/1")), run_overrides=overrides)
    plan = build_settings_preparation_plan({**{key: value for key, value in old.items()
        if key not in {"descriptor_address", "resource_policy_address", "runtime_contract_addresses"}},
        "settings_snapshot": snapshot})
    repository = SimpleNamespace(snapshot=lambda **_: pytest.fail("retry read mutable settings"))
    body = SimpleNamespace(expected_workspace_revision=0, expected_strategy_revision=0, run_overrides=overrides)
    observed = _preparation_settings_snapshot(repository, SimpleNamespace(plan=plan), body,
        old["owner_id"], old["graph_identifier"])
    assert observed == snapshot and observed["schema"] == "research-settings-snapshot/1"
    body.run_overrides = {**overrides, "seed": overrides["seed"] + 1}
    with pytest.raises(V2OperationRefusal) as refusal:
        _preparation_settings_snapshot(repository, SimpleNamespace(plan=plan), body,
            old["owner_id"], old["graph_identifier"])
    assert refusal.value.code == "REQUEST_ID_REUSED"


def _search_input_set_plan(plan):
    from research.domain.settings import resolve_snapshot
    from research.orchestrator.v2_preparation import build_input_set_preparation_plan
    original = plan["v2_graphs"][0]
    snapshot = original["settings_snapshot"]
    request = {"schema": "canonical-local-development-search/1", "enabled": True,
        "axes": [{"node_id": "rising", "parameter_id": "window", "step": "1", "minimum": "1", "maximum": "3"}]}
    updated = resolve_snapshot(owner_id=original["owner_id"], graph_identifier=original["graph_identifier"],
        workspace=snapshot["workspace"], strategy=snapshot["strategy"],
        run_overrides={**snapshot["run_overrides"], "min_trades": 1, "n_folds": 2, "optimization": request})
    fields = {key: value for key, value in original.items() if key not in {
        "descriptor_address", "resource_policy_address", "runtime_contract_addresses"}}
    experiment = {key: updated["values"][key] for key in original["experiment"] if key != "hypothesis"}
    return build_input_set_preparation_plan({**fields, "request_id": str(uuid.uuid4()),
        "experiment": {**experiment, "hypothesis": "Frozen canonical development search"}, "settings_snapshot": updated})


def _assert_search_gate(result, closes, window):
    start = max(window, 2)
    expected = [all(closes["frame"][point] < closes["frame"][point + 1] for point in range(index - window, index))
                and closes["benchmark"][index - 2] < closes["benchmark"][index - 1] < closes["benchmark"][index]
                for index in range(start, len(closes["frame"]))]
    assert [row.value for row in result.batch_outputs["entry"].iloc[start:]] == expected
    assert any(expected) and not all(expected)
    assert result.batch_output_document == result.incremental_output_document


@pytest.mark.parametrize("input_set_worker", [True], indirect=True)
def test_real_canonical_search_recovers_and_validates_only_frozen_selected_runtime(input_set_worker, monkeypatch):
    from app.editor import v2_editor_store
    from app.ir.library import REGISTRY
    from app.core import research_read
    from research.domain.operations import ResearchOperationRepository
    from research.domain.settings import ResearchSettingsRepository
    from research.pipeline.v2_parameter_search import prepare_canonical_search
    from research_tests.test_v2_graph_experiment_bridge import _interrupt_preparation_after_execution_receipt
    import research.evaluation.phase5_runtime as runtime
    import research.orchestrator.run as runner
    import scripts.research_run as research_run
    Execution, Research, path, original_plan, closes = input_set_worker
    plan = _search_input_set_plan(original_plan)
    item = plan["v2_graphs"][0]
    saved = v2_editor_store.read_version(item["project_id"], item["graph_identifier"], item["graph_version"], owner_id="owner-a")
    prepared = prepare_canonical_search(item["settings_snapshot"]["values"]["optimization"],
                                        document=saved["document"], registry=REGISTRY)
    windows = {row["content_address"]: row["parameters"][0]["value"] for row in prepared.candidates}
    results, heldout = [], []
    actual_execute, actual_validate = runtime.execute_research, runner.validate
    def observe_execute(*args, **kwargs):
        result = actual_execute(*args, **kwargs)
        _assert_search_gate(result, closes, windows[result.document["authored_ir_address"]])
        results.append(result)
        return result
    def observe_validate(candles, instrument, strategy, params, **kwargs):
        assert params == {}
        assert strategy.replay_slippage_pct == .0005
        heldout.append((strategy.adapter_address, kwargs["evaluation_start"]))
        return actual_validate(candles, instrument, strategy, params, **kwargs)
    monkeypatch.setattr(runtime, "execute_research", observe_execute)
    monkeypatch.setattr(runner, "validate", observe_validate)
    monkeypatch.setattr(ResearchSettingsRepository, "read", lambda *_args, **_kwargs: pytest.fail("worker read mutable settings"))
    identifier = operation_id_for_request(owner_id="owner-a", request_id=item["request_id"])
    with Research() as session:
        ResearchOperationRepository(session).enqueue(owner_id="owner-a", trigger="v2_graph", plan=plan,
            build="test-build", provider_mode=V2_PROVIDER_MODE, operation_id=identifier)
    _interrupt_preparation_after_execution_receipt(identifier, "owner-a", Execution, Research, monkeypatch)
    reports, mode = research_run._run_enabled_operation(path)
    assert mode == V2_PROVIDER_MODE and len(reports) == 1
    with Research() as session:
        _assert_search_worker_evidence(session, reports[0], item, original_plan, results, heldout, research_read)


def _assert_search_worker_evidence(session, report, item, original_plan, results, heldout, research_read):
    import json
    from sqlalchemy import func, select
    from research.domain.models import ExperimentRun, ExperimentSpec, OptimizationTrial, ResearchDatasetManifestV2
    from research.evidence import decode_terminal_evidence
    from research.pipeline.v2_parameter_search import verify_canonical_search_evidence
    run = session.get(ExperimentRun, report["run_id"])
    recipe = json.loads(session.get(ExperimentSpec, ("owner-a", report["spec_id"])).recipe_json)
    evidence = decode_terminal_evidence(run.checkpoint_json)
    search = evidence["results"]["canonical_optimization"]
    assert search["state"] == "selected"
    assert len(search["candidates"]) == len(search["final_development_trials"]) == 3
    assert len(search["nested_trials"]) == search["n_trials"] == 6
    assert len(heldout) == 1
    assert heldout[0][0] == search["selected"]["lineage"]["adapter_address"]
    assert int(heldout[0][1].timestamp()) == search["partition"]["validation_start_ts"]
    assert {result.document["authored_ir_address"] for result in results} == {row["content_address"] for row in search["candidates"]}
    assert session.scalar(select(func.count()).select_from(OptimizationTrial)) == 9
    assert session.scalar(select(func.count()).select_from(ExperimentRun)) == 1
    assert session.scalar(select(func.count()).select_from(ResearchDatasetManifestV2)) == 2
    for key in ("input_datasets", "primary_input", "dataset_as_of"):
        assert item[key] == original_plan["v2_graphs"][0][key]
    assert item["request_id"] != original_plan["v2_graphs"][0]["request_id"]
    verify_canonical_search_evidence(recipe, evidence)
    assert research_read._graph_run_view(session, run, include_evidence=True)["evidence_state"] == "verified"


@pytest.mark.parametrize("inputs", [None, [], [{}], ["frame"], [{"port_id": "other"}], [{"port_id": "frame"}, {"port_id": "benchmark"}]])
def test_single_input_projection_never_drops_an_unbound_graph_input(inputs):
    from research.orchestrator.v2_operation import _graph_input_fields, V2OperationRefusal
    with pytest.raises(V2OperationRefusal, match="one frame graph input"):
        _graph_input_fields({"graph_inputs": inputs}, None)


def test_resolved_market_fields_exclude_other_input_names_and_non_fields():
    from types import SimpleNamespace
    from research.orchestrator.v2_operation import _resolved_market_fields
    graph = SimpleNamespace(nodes=[SimpleNamespace(component=("a", 1)), SimpleNamespace(component=("missing", 1))])
    registry = SimpleNamespace(node_contracts={("a", 1): {"required_market_fields": ["close", "CLOSE", "benchmark.close", None]}})
    assert _resolved_market_fields(graph, registry) == ["CLOSE"]
