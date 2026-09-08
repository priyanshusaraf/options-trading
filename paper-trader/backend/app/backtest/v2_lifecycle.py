"""Exclusive P5 v2 claim/reclaim/finalization lifecycle.

This module owns no queue, schema, provider, cache, broker, order, or money path.
It consumes the existing BacktestRun repository and one explicitly supplied
test executor after the sole persisted Phase 4 authority loader succeeds.
"""
from __future__ import annotations

import datetime as dt
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select

from app.backtest import repository
from app.db.models import BacktestResult
from app.db.concurrency import caller_owned_savepoint


FINALIZED = "FINALIZED"
ALREADY_FINALIZED = "ALREADY_FINALIZED"
CANCELLED = "CANCELLED"
MAX_RESULT_BATCH = 10
_RUN_LOCAL_RESULT_FIELDS = frozenset({
    "id", "owner_id", "run_id", "cell_key", "computed_at",
})
_RESULT_PAYLOAD_COLUMNS = tuple(
    column for column in BacktestResult.__table__.columns
    if column.name not in _RUN_LOCAL_RESULT_FIELDS)
_RESULT_PAYLOAD_NAMES = frozenset(
    column.name for column in _RESULT_PAYLOAD_COLUMNS)


class V2LifecycleRefused(RuntimeError):
    """Stable lifecycle refusal before an unauthorized side effect."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class V2LifecycleOutcome:
    run_id: int
    state: str
    durable_results: int


V2LifecycleExecutor = Callable[
    [repository.VerifiedV2LifecycleAdmission, Mapping[str, Any]],
    Sequence[Mapping[str, Any]],
]
V2AuthorityLoader = Callable[[], repository.VerifiedV2LifecycleAdmission]


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _plain(value[key]) for key in sorted(value)}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


def attribution(admission: repository.VerifiedV2LifecycleAdmission) -> dict[str, str]:
    return {
        "strategy_key": admission.strategy_key,
        "strategy_version": admission.strategy_version,
        "graph_address": admission.graph_address,
        "admission_address": admission.admission_address,
        "attribution_state": admission.attribution_state,
    }


def require_descriptor_matches(
        descriptor: Mapping[str, Any],
        admission: repository.VerifiedV2LifecycleAdmission) -> None:
    """Bind durable replay bytes to the exact freshly verified authority."""
    expected_attribution = attribution(admission)
    expected_binding = _plain(admission.phase4_binding)
    strategies = descriptor.get("strategies")
    if (descriptor.get("admission_address") != admission.admission_address
            or descriptor.get("attribution") != expected_attribution
            or descriptor.get("_phase4_binding") != expected_binding
            or not isinstance(strategies, list)
            or len(strategies) != 1
            or not isinstance(strategies[0], dict)
            or strategies[0].get("key") != admission.strategy_key
            or strategies[0].get("version") != admission.strategy_version):
        raise V2LifecycleRefused("ARTEFACT_MISMATCH")


def _normalized_results(
        values: Sequence[Mapping[str, Any]],
        admission: repository.VerifiedV2LifecycleAdmission) -> list[dict[str, Any]]:
    if not isinstance(values, (tuple, list)) or not values:
        raise V2LifecycleRefused("RESULT_REQUIRED")
    if len(values) > MAX_RESULT_BATCH:
        raise V2LifecycleRefused("RESULT_BATCH_TOO_LARGE")
    expected = attribution(admission)
    normalized = []
    for value in values:
        if not isinstance(value, Mapping):
            raise V2LifecycleRefused("RESULT_INVALID")
        row = dict(value)
        if set(row) - (_RESULT_PAYLOAD_NAMES | {"computed_at"}):
            raise V2LifecycleRefused("RESULT_INVALID")
        for key, expected_value in expected.items():
            if key in row and row[key] != expected_value:
                raise V2LifecycleRefused("GRAPH_ATTRIBUTION_MISMATCH")
            row[key] = expected_value
        normalized.append(row)
    return normalized


def _canonical_result_payload(value: Mapping[str, Any]) -> tuple[tuple[str, Any], ...]:
    payload = []
    for column in _RESULT_PAYLOAD_COLUMNS:
        if column.name in value:
            item = value[column.name]
        elif column.default is not None and column.default.is_scalar:
            item = column.default.arg
        elif column.nullable:
            item = None
        else:
            raise V2LifecycleRefused("RESULT_INVALID")
        payload.append((column.name, item))
    return tuple(payload)


def _expected_payloads(
        values: Sequence[Mapping[str, Any]]) -> dict[str, tuple[tuple[str, Any], ...]]:
    expected = {
        repository._cell_key(dict(value)): _canonical_result_payload(value)
        for value in values
    }
    if len(expected) != len(values):
        raise V2LifecycleRefused("RESULT_UNIVERSE_MISMATCH")
    return expected


def _durable_payloads(
        session, *, owner_id: str, run_id: int) -> dict[str, tuple[tuple[str, Any], ...]]:
    rows = list(session.scalars(select(BacktestResult).where(
        BacktestResult.owner_id == owner_id,
        BacktestResult.run_id == run_id)))
    return {
        row.cell_key: tuple(
            (column.name, getattr(row, column.name))
            for column in _RESULT_PAYLOAD_COLUMNS)
        for row in rows
    }


def _require_result_universe(
        run, expected_payloads, *, code: str = "RESULT_UNIVERSE_MISMATCH") -> None:
    if (run.total != len(expected_payloads)
            or isinstance(run.total, bool) or run.total < 1):
        raise V2LifecycleRefused(code)


def _require_durable_payloads(
        session, *, owner_id: str, run_id: int, run,
        expected_payloads: Mapping[str, tuple[tuple[str, Any], ...]]) -> None:
    durable_payloads = _durable_payloads(
        session, owner_id=owner_id, run_id=run_id)
    if (durable_payloads != expected_payloads
            or run.done != run.total
            or len(durable_payloads) != run.total):
        raise V2LifecycleRefused("FINALIZATION_MISMATCH")


def _idempotent_terminal_state(
        session, *, owner_id: str, run_id: int, claim_token: str,
        admission: repository.VerifiedV2LifecycleAdmission,
        expected_payloads: Mapping[str, tuple[tuple[str, Any], ...]]) -> V2LifecycleOutcome | None:
    run = repository.get_run(session, owner_id=owner_id, run_id=run_id)
    if run is None:
        raise V2LifecycleRefused("CLAIM_LOST")
    if run.status == "running":
        return None
    if (run.status != "done" or run.claim_token != claim_token
            or run.admission_address != admission.admission_address):
        raise V2LifecycleRefused("CLAIM_LOST")
    _require_result_universe(
        run, expected_payloads, code="FINALIZATION_MISMATCH")
    _require_durable_payloads(
        session, owner_id=owner_id, run_id=run_id, run=run,
        expected_payloads=expected_payloads)
    return V2LifecycleOutcome(run_id, ALREADY_FINALIZED, run.done)


def finalize_claimed_results(
        session, *, owner_id: str, run_id: int, claim_token: str,
        admission: repository.VerifiedV2LifecycleAdmission,
        values: Sequence[Mapping[str, Any]],
        now: dt.datetime | None = None,
        lease_seconds: int = 30) -> V2LifecycleOutcome:
    """Append exact results and terminalize once under the existing token fence."""
    normalized = _normalized_results(values, admission)
    expected_payloads = _expected_payloads(normalized)
    with caller_owned_savepoint(session, scope="v2_lifecycle_finalize"):
        terminal = _idempotent_terminal_state(
            session, owner_id=owner_id, run_id=run_id, claim_token=claim_token,
            admission=admission, expected_payloads=expected_payloads)
        if terminal is not None:
            return terminal
        run = repository.get_run(session, owner_id=owner_id, run_id=run_id)
        if run is None:
            raise V2LifecycleRefused("CLAIM_LOST")
        _require_result_universe(run, expected_payloads)
        if not repository.append_claimed_result_batch(
                session, owner_id=owner_id, run_id=run_id, claim_token=claim_token,
                values=normalized, now=now, lease_seconds=lease_seconds,
                verified_v2_admission=admission):
            raise V2LifecycleRefused("CLAIM_LOST")
        session.refresh(run)
        _require_durable_payloads(
            session, owner_id=owner_id, run_id=run_id, run=run,
            expected_payloads=expected_payloads)
        if not repository.complete_claim(
                session, owner_id=owner_id, run_id=run_id, claim_token=claim_token,
                status="done", now=now):
            raise V2LifecycleRefused("CLAIM_LOST")
        return V2LifecycleOutcome(run_id, FINALIZED, run.done)


def run_claimed_lifecycle(
        *, sessionmaker, owner_id: str, run_id: int, claim_token: str,
        descriptor_json: str,
        initial_admission: repository.VerifiedV2LifecycleAdmission,
        authority_loader: V2AuthorityLoader,
        executor: V2LifecycleExecutor,
        lease_seconds: int = 30) -> V2LifecycleOutcome:
    """Run one explicitly supplied fixture executor and finalize after fresh reload."""
    if not callable(executor) or not callable(authority_loader):
        raise V2LifecycleRefused("V2_RUNTIME_UNAVAILABLE")
    try:
        descriptor = json.loads(descriptor_json)
    except (TypeError, json.JSONDecodeError) as exc:
        raise V2LifecycleRefused("ARTEFACT_MISMATCH") from exc
    if not isinstance(descriptor, dict):
        raise V2LifecycleRefused("ARTEFACT_MISMATCH")
    require_descriptor_matches(descriptor, initial_admission)
    with sessionmaker() as session:
        run = repository.get_run(session, owner_id=owner_id, run_id=run_id)
        if (run is None or run.status != "running"
                or run.claim_token != claim_token
                or run.admission_address != initial_admission.admission_address):
            raise V2LifecycleRefused("CLAIM_LOST")
        if repository.is_cancel_requested(
                session, owner_id=owner_id, run_id=run_id,
                claim_token=claim_token):
            if not repository.complete_claim(
                    session, owner_id=owner_id, run_id=run_id,
                    claim_token=claim_token, status="cancelled"):
                raise V2LifecycleRefused("CLAIM_LOST")
            session.commit()
            return V2LifecycleOutcome(
                run_id, CANCELLED,
                repository.durable_result_count(
                    session, owner_id=owner_id, run_id=run_id))

    fixture_descriptor = json.loads(json.dumps(descriptor))
    produced = executor(initial_admission, fixture_descriptor)

    # Current authority is a use-time fact. A fresh execution and research
    # session must reconstruct it after computation and immediately before write.
    current_admission = authority_loader()
    require_descriptor_matches(descriptor, current_admission)
    if attribution(current_admission) != attribution(initial_admission):
        raise V2LifecycleRefused("ARTEFACT_MISMATCH")
    with sessionmaker() as session:
        outcome = finalize_claimed_results(
            session, owner_id=owner_id, run_id=run_id,
            claim_token=claim_token, admission=current_admission,
            values=produced, lease_seconds=lease_seconds)
        session.commit()
        return outcome


__all__ = [
    "ALREADY_FINALIZED", "CANCELLED", "FINALIZED", "V2LifecycleExecutor",
    "V2LifecycleOutcome", "V2LifecycleRefused", "attribution",
    "finalize_claimed_results", "require_descriptor_matches",
    "run_claimed_lifecycle",
]
