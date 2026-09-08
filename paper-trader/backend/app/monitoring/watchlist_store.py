"""Owner-scoped watchlist preferences with exact retries and caller transactions."""
from __future__ import annotations

import json

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core import static_scopes
from app.db.concurrency import begin_reservation, caller_owned_savepoint
from app.db.models import GraphArtifact, IrV2GraphVersion, WatchlistMonitoringRevision as Row
from app.ir.hashing import canonical_json
from app.ir.v2_graph_versions import V2GraphVerificationError, facts_from_row
from app.monitoring.repository import MonitoringRepository, _db_time, _domain_time
from app.monitoring.state_contracts import _time, _utc
from app.monitoring.watchlist_config import (
    WatchlistCommand, WatchlistConfiguration, WatchlistContext, WatchlistStrategy, WatchlistValues,
)


class WatchlistMonitoringConflict(ValueError):
    pass


class WatchlistMonitoringUnavailable(ValueError):
    pass


def member_key(member):
    value = static_scopes._typed_member(member)
    kind, address = static_scopes._typed_member_key(value)
    return f"{kind}:{address}"


def scope_members(scope):
    members = scope["snapshot"]["members"]
    return {member_key(value): value for value in (
        {"kind": "CANONICAL", "instrument_address": item} if type(item) is str else item
        for item in members)}


def verified_scope(session, owner_id, context, *, write=False):
    if type(context) is not WatchlistContext:
        raise ValueError("closed watchlist context required")
    scope = static_scopes.get_scope(session, owner_id=owner_id,
        project_id=context.project_id, scope_id=context.scope_id)
    actual = (scope["snapshot"]["revision"], scope["address"], scope["membership_address"])
    expected = (context.scope_revision, context.scope_address, context.membership_address)
    if actual != expected:
        raise WatchlistMonitoringConflict("This watchlist changed. Open its current version and try again.")
    if write:
        static_scopes._project(session, owner_id, context.project_id, write=True)
        if scope["status"] != "active":
            raise WatchlistMonitoringConflict("This watchlist is archived. Open an active watchlist to change monitoring.")
    return scope


def _where(owner_id, context):
    return (Row.owner_id == owner_id, Row.project_id == context.project_id,
        Row.scope_id == context.scope_id)


def decode_configuration(row):
    try:
        stored = json.loads(row.canonical_json)
        document = {key: value for key, value in stored.items() if key != "address"}
        configuration = WatchlistConfiguration.model_validate(document)
        fields = ("owner_id", "project_id", "scope_id", "member_key", "revision", "address",
            "predecessor_address", "request_id", "created_by", "monitoring_intent", "assignment_id")
        if (canonical_json(configuration.stored_payload()) != row.canonical_json
                or tuple(getattr(configuration, key) for key in fields)
                    != tuple(getattr(row, key) for key in fields)
                or configuration.created_at != _time(_domain_time(row.created_at))):
            raise ValueError("configuration columns or bytes differ")
        return configuration
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        raise WatchlistMonitoringUnavailable("Saved watchlist settings could not be verified. Refresh before changing this row.") from exc


def latest_configurations(session, owner_id, context, keys):
    latest = (select(Row.member_key, func.max(Row.revision).label("revision"))
        .where(*_where(owner_id, context), Row.member_key.in_(keys)).group_by(Row.member_key).subquery())
    rows = session.scalars(select(Row).join(latest,
        (Row.member_key == latest.c.member_key) & (Row.revision == latest.c.revision))
        .where(*_where(owner_id, context))).all()
    return {row.member_key: _verified_latest(session, row) for row in rows}


def _verified_latest(session, row):
    configuration = decode_configuration(row)
    if configuration.revision == 1:
        return configuration
    predecessor = session.scalar(select(Row).where(
        *_where(configuration.owner_id, configuration.context),
        Row.member_key == configuration.member_key,
        Row.address == configuration.predecessor_address))
    if predecessor is None or predecessor.revision != configuration.revision - 1:
        raise WatchlistMonitoringUnavailable(
            "Saved watchlist history could not be verified. Refresh before changing this row.")
    decode_configuration(predecessor)
    return configuration


def read_watchlist_configurations(session, *, owner_id, context):
    scope = verified_scope(session, owner_id, context)
    members = scope_members(scope)
    return scope, members, latest_configurations(session, owner_id, context, tuple(members))


def _replayed(session, owner_id, context, key, command, request_id):
    row = session.scalar(select(Row).where(Row.owner_id == owner_id, Row.request_id == request_id))
    if row is None:
        return None
    configuration = decode_configuration(row)
    if (configuration.context, configuration.member_key, configuration.command) != (context, key, command):
        raise WatchlistMonitoringConflict("This save request already identifies a different change. Refresh this row.")
    return configuration


def _selected_graph(session, owner_id, context, selection):
    row = session.execute(select(IrV2GraphVersion, GraphArtifact.display_name).join(GraphArtifact,
        (IrV2GraphVersion.owner_id == GraphArtifact.owner_id)
        & (IrV2GraphVersion.graph_identifier == GraphArtifact.identifier)).where(
            IrV2GraphVersion.owner_id == owner_id, GraphArtifact.project_id == context.project_id,
            IrV2GraphVersion.graph_identifier == selection.graph_id,
            IrV2GraphVersion.graph_version == selection.graph_version)).one_or_none()
    if row is None:
        raise WatchlistMonitoringUnavailable("Choose a saved Build strategy from this project. Older bot strategies cannot use this monitoring path.")
    version, label = row
    try:
        facts = facts_from_row(version)
    except V2GraphVerificationError as exc:
        raise WatchlistMonitoringUnavailable(
            "The saved strategy could not be verified. Open Build and save a verified version.") from exc
    return WatchlistStrategy(graph_id=facts.graph_identifier, graph_version=facts.graph_version,
        graph_version_address=facts.content_address, label=label)


def _assignment_for_configuration(repository, configuration):
    assignment = repository.get_assignment(configuration.assignment_id)
    policy = configuration.evaluation_policy
    actual = (assignment.spec.project_id, assignment.spec.graph_version_address,
        assignment.spec.evaluation_trigger_address, assignment.spec.resource_plan_address)
    expected = (configuration.project_id, configuration.graph.graph_version_address,
        policy["address"], policy["initial_resource_plan_address"])
    if actual != expected:
        raise WatchlistMonitoringUnavailable("The row's monitoring assignment no longer matches its settings.")
    return assignment


def _set_assignment_state(session, current, enabled, now):
    if current is None or current.assignment_id is None:
        return
    repository = MonitoringRepository(session, owner_id=current.owner_id)
    assignment = _assignment_for_configuration(repository, current)
    wanted = "ACTIVE" if enabled else "PAUSED"
    if assignment.lifecycle_state != wanted:
        repository.update_assignment(assignment.spec.assignment_id,
            expected_revision=assignment.optimistic_revision, lifecycle_state=wanted, now=now)


def _configured_values(session, owner_id, context, current, values, selection, now):
    graph = _selected_graph(session, owner_id, context, selection)
    if (values.graph, values.timeframe) == (graph, selection.timeframe):
        return values
    _set_assignment_state(session, current, False, now)
    return WatchlistValues(graph=graph, timeframe=selection.timeframe, pinned=values.pinned)


def _changed_values(session, owner_id, context, current, command, now):
    values = current.row_values() if current is not None else WatchlistValues()
    if command.operation == "CONFIGURE":
        return _configured_values(session, owner_id, context, current, values, command.selection, now)
    if command.operation == "PIN":
        return WatchlistValues(**{**values.model_dump(), "pinned": command.flag})
    changed = WatchlistValues(**{**values.model_dump(),
        "monitoring_intent": "MONITOR" if command.flag else "PAUSE"})
    _set_assignment_state(session, current, command.flag, now)
    return changed


def _append(session, owner_id, created_by, context, key, current, command, request_id, values, now):
    configuration = WatchlistConfiguration(owner_id=owner_id, project_id=context.project_id,
        scope_id=context.scope_id, member_key=key, revision=command.expected_revision + 1,
        predecessor_address=current.address if current is not None else None,
        request_id=request_id, created_by=created_by, created_at=_time(now),
        context=context, command=command, **values.model_dump())
    fields = ("owner_id", "project_id", "scope_id", "member_key", "revision", "request_id",
        "address", "predecessor_address", "created_by", "monitoring_intent", "assignment_id")
    row = Row(**{key: getattr(configuration, key) for key in fields}, created_at=_db_time(now),
        canonical_json=canonical_json(configuration.stored_payload()))
    session.add(row)
    session.flush()
    return decode_configuration(row)


def write_watchlist_configuration(session, *, owner_id, created_by, context, member,
        command, request_id, now):
    """Record requested preferences; starting intent alone is not an active worker."""
    if type(command) is not WatchlistCommand:
        raise ValueError("closed watchlist command required")
    now = _utc(now, "watchlist change time")
    key = member_key(member)
    begin_reservation(session, scope=f"static-scope:{owner_id}:{context.project_id}")
    scope = verified_scope(session, owner_id, context, write=True)
    if key not in scope_members(scope):
        raise WatchlistMonitoringUnavailable("This instrument is no longer in the watchlist. Refresh the list.")
    replay = _replayed(session, owner_id, context, key, command, request_id)
    if replay is not None:
        return replay
    current = latest_configurations(session, owner_id, context, (key,)).get(key)
    revision = 0 if current is None else current.revision
    if revision != command.expected_revision:
        raise WatchlistMonitoringConflict("This row changed elsewhere. Refresh it before saving your choice.")
    try:
        with caller_owned_savepoint(session, scope="watchlist-monitoring-configuration"):
            values = _changed_values(session, owner_id, context, current, command, now)
            return _append(session, owner_id, created_by, context, key, current, command, request_id, values, now)
    except IntegrityError as exc:
        raise WatchlistMonitoringConflict("This row changed while saving. Refresh it before retrying.") from exc


def _binding_require(condition, message):
    if not condition:
        raise WatchlistMonitoringConflict(message)


def _binding_request(session, owner_id, requested):
    _binding_require(type(requested) is WatchlistConfiguration,
        "Binding requires a verified requested configuration.")
    _binding_require(requested.owner_id == owner_id,
        "The requested row belongs to a different owner.")
    scope = verified_scope(session, owner_id, requested.context, write=True)
    _binding_require(requested.member_key in scope_members(scope),
        "The requested member is no longer in the watchlist.")
    _binding_require(requested.monitoring_intent == "MONITOR" and requested.graph is not None,
        "The row no longer requests monitoring of a saved strategy.")
    _binding_require(requested.assignment_id is None,
        "A requested row cannot replace an existing monitoring binding.")
    return latest_configurations(session, owner_id, requested.context,
        (requested.member_key,)).get(requested.member_key)


def _binding_assignment(repository, requested, assignment_spec, policy):
    from app.monitoring.repository import MonitoringAssignmentSpec, MonitoringNotFound
    _binding_require(type(assignment_spec) is MonitoringAssignmentSpec,
        "An admitted assignment specification is required.")
    try:
        repository._assignment_row(assignment_spec.assignment_id, write=True)
        assignment = repository.get_assignment(assignment_spec.assignment_id)
    except MonitoringNotFound as exc:
        raise WatchlistMonitoringConflict("The owner has no admitted assignment for this binding.") from exc
    _binding_require(assignment.spec == assignment_spec and assignment.lifecycle_state == "ACTIVE",
        "The admitted assignment changed or is no longer active.")
    actual = (assignment.owner_id, assignment.spec.project_id, assignment.spec.strategy_id,
        assignment.spec.graph_version_address, assignment.spec.static_scope_revision_address,
        assignment.spec.evaluation_trigger_address, assignment.spec.resource_plan_address)
    expected = (requested.owner_id, requested.project_id, requested.graph.graph_id,
        requested.graph.graph_version_address, requested.context.scope_address,
        policy["address"], policy["initial_resource_plan_address"])
    _binding_require(actual == expected, "The admitted assignment differs from the requested row or policy.")
    _binding_require((policy["owner_id"], policy["assignment_id"])
        == (requested.owner_id, assignment.spec.assignment_id), "The evaluation policy identifies another binding.")
    return assignment


def _binding_instrument(session, research_session, requested, spec, policy, manifest_address, now):
    if requested.member_key.startswith('CANONICAL:'):
        return requested.member_key[len('CANONICAL:'):]
    _binding_require(research_session is not None and manifest_address is not None,
        'Provider-reference binding requires verified mapping provenance.')
    from app.monitoring.provider_watchlist_binding import resolve_provider_watchlist_instrument
    return resolve_provider_watchlist_instrument(session, research_session, requested=requested,
        assignment_spec=spec, policy=policy, manifest_address=manifest_address, now=now)


def _binding_initial(requested, assignment, snapshot, now, instrument_address):
    from app.monitoring.contracts import StrategyState
    from app.monitoring.repository import MonitoringStateSnapshot
    from app.monitoring.research_state_contracts import ResearchMonitoringStateSnapshot
    _binding_require(type(snapshot) in (MonitoringStateSnapshot, ResearchMonitoringStateSnapshot),
        "An honest initial snapshot is required.")
    snapshot.__post_init__()
    actual = (snapshot.owner_id, snapshot.assignment_id, f"CANONICAL:{snapshot.canonical_instrument_address}",
        snapshot.snapshot_sequence, snapshot.predecessor_snapshot_address, snapshot.strategy_state)
    expected = (requested.owner_id, assignment.spec.assignment_id, f'CANONICAL:{instrument_address}',
        0, None, StrategyState.FLAT)
    _binding_require(actual == expected, "Initial state must be sequence-zero FLAT for this exact instrument.")
    _binding_require(snapshot.entry_reference.observed_at <= snapshot.effective_at <= now,
        "Initial state contains an unavailable or future clock.")


def _binding_values(requested, assignment, policy, snapshot):
    return WatchlistValues(**{**requested.row_values().model_dump(),
        "assignment_id": assignment.spec.assignment_id, "evaluation_policy": policy,
        "canonical_instrument_address": snapshot.canonical_instrument_address})


def _binding_replay(replay, current, requested, values, created_by):
    if replay is None:
        _binding_require(current is not None and current.address == requested.address,
            "The requested row changed before its monitoring binding was ready.")
        return False
    _binding_require(current is not None and current.address == replay.address,
        "The bound row changed after this request; refresh before continuing.")
    _binding_require((replay.predecessor_address, replay.row_values(), replay.created_by)
        == (requested.address, values, created_by), "This binding request already identifies different evidence.")
    return True


def _persist_binding_initial(repository, assignment, snapshot, *, replayed, now):
    from app.db.models import MonitoringStateSnapshotRow
    foreign = repository.session.scalar(select(MonitoringStateSnapshotRow.snapshot_address).where(
        MonitoringStateSnapshotRow.owner_id == repository.owner_id,
        MonitoringStateSnapshotRow.assignment_id == assignment.spec.assignment_id,
        MonitoringStateSnapshotRow.canonical_instrument_address != snapshot.canonical_instrument_address).limit(1))
    _binding_require(foreign is None, "The admitted assignment already carries another instrument's state.")
    if not replayed:
        _binding_require(assignment.current_state_snapshot_address in (None, snapshot.address),
            "The admitted assignment already carries a different initial state.")
    if replayed:
        existing = repository.session.scalar(select(MonitoringStateSnapshotRow.snapshot_address).where(
            MonitoringStateSnapshotRow.owner_id == repository.owner_id,
            MonitoringStateSnapshotRow.assignment_id == assignment.spec.assignment_id,
            MonitoringStateSnapshotRow.canonical_instrument_address == snapshot.canonical_instrument_address,
            MonitoringStateSnapshotRow.snapshot_sequence == 0))
        _binding_require(existing == snapshot.address, "The retry identifies a different initial snapshot.")
    repository.append_state_snapshot(snapshot, created_at=now)
    latest = repository.get_latest_state(assignment.spec.assignment_id, snapshot.canonical_instrument_address)
    persisted = repository.get_assignment(assignment.spec.assignment_id)
    _binding_require(persisted.current_state_snapshot_address == latest.address,
        "The assignment state pointer differs from its verified latest snapshot.")
    if not replayed:
        _binding_require(latest == snapshot, "The assignment's initial state is no longer current.")


def bind_watchlist_monitoring(session, *, owner_id, created_by, requested,
        assignment_spec, evaluation_policy, initial_snapshot, request_id, now,
        research_session=None, input_manifest_address=None):
    """Internal worker seam: bind admitted facts, never create public command authority.

    The caller owns admission, authored evidence and the outer transaction. This
    function creates neither an assignment nor fabricated protection, and never
    changes lifecycle state. Provider-reference rows require a fully replayed input.
    """
    from app.monitoring.evaluation_policy import monitoring_policy_payload
    from app.monitoring.repository import MonitoringConflict
    now = _utc(now, "watchlist binding time")
    _binding_require(type(requested) is WatchlistConfiguration,
        "Binding requires a verified requested configuration.")
    begin_reservation(session, scope=f"static-scope:{owner_id}:{requested.project_id}")
    current = _binding_request(session, owner_id, requested)
    policy = monitoring_policy_payload(evaluation_policy)
    repository = MonitoringRepository(session, owner_id=owner_id)
    assignment = _binding_assignment(repository, requested, assignment_spec, policy)
    instrument = _binding_instrument(session, research_session, requested, assignment_spec,
        policy, input_manifest_address, now)
    _binding_initial(requested, assignment, initial_snapshot, now, instrument)
    values = _binding_values(requested, assignment, policy, initial_snapshot)
    command = WatchlistCommand(operation="MONITOR", expected_revision=requested.revision, flag=True)
    replay = _replayed(session, owner_id, requested.context, requested.member_key, command, request_id)
    replayed = _binding_replay(replay, current, requested, values, created_by)
    try:
        with caller_owned_savepoint(session, scope="bind-watchlist-monitoring"):
            _persist_binding_initial(repository, assignment, initial_snapshot, replayed=replayed, now=now)
            if replayed:
                return replay
            return _append(session, owner_id, created_by, requested.context, requested.member_key,
                requested, command, request_id, values, now)
    except (IntegrityError, MonitoringConflict) as exc:
        raise WatchlistMonitoringConflict("The monitoring binding changed while saving; refresh this row.") from exc
