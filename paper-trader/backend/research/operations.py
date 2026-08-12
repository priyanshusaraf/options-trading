"""Canonical current/last status for bounded research entry points."""
from __future__ import annotations

import contextlib
import fcntl
import json
import os
import uuid
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping

from app.ir.hashing import canonical_json, content_address


SCHEMA_VERSION = 1
MAX_OPERATION_BYTES = 256_000
STAGES = {
    "startup", "planning", "collection", "experiments", "generation",
    "reports", "completed",
}
TRIGGERS = {"nightly", "manual_script"}


class OperationStateCorrupt(Exception):
    pass


class OperationAlreadyRunning(Exception):
    pass


def empty_operation_state() -> dict[str, Any]:
    return {"active": None, "last": None}


def _reject_constant(value: str):
    raise ValueError(f"non-finite JSON value {value}")


def _validate_failure(value: Any) -> None:
    if value is None:
        return
    if not isinstance(value, dict) or set(value) != {"stage", "code", "message"}:
        raise OperationStateCorrupt("operation failure has unknown or missing fields")
    if value["stage"] not in STAGES:
        raise OperationStateCorrupt("operation failure stage is unsupported")
    if not all(isinstance(value[key], str) for key in ("code", "message")):
        raise OperationStateCorrupt("operation failure fields must be strings")


def _validate_plan(value: Any) -> None:
    if value is None:
        return
    if not isinstance(value, dict) or set(value) != {
        "content_address", "experiment_count", "items"
    }:
        raise OperationStateCorrupt("operation plan has unknown or missing fields")
    if not isinstance(value["experiment_count"], int) or value["experiment_count"] < 0:
        raise OperationStateCorrupt("operation experiment count is invalid")
    if not isinstance(value["items"], list):
        raise OperationStateCorrupt("operation plan items must be a list")
    if len(value["items"]) > 64:
        raise OperationStateCorrupt("operation plan has too many items")
    item_fields = {
        "program", "hypothesis", "strategy_key", "instrument_keys",
        "interval", "days", "optimize_search",
    }
    for item in value["items"]:
        if not isinstance(item, dict) or set(item) != item_fields:
            raise OperationStateCorrupt("operation plan item has unknown or missing fields")
        for key, limit in (
            ("program", 80), ("hypothesis", 4000),
            ("strategy_key", 80), ("interval", 24),
        ):
            if not isinstance(item[key], str) or len(item[key]) > limit:
                raise OperationStateCorrupt(f"operation plan item {key} is invalid")
        keys = item["instrument_keys"]
        if (
            not isinstance(keys, list) or len(keys) > 64
            or any(not isinstance(key, str) or len(key) > 48 for key in keys)
        ):
            raise OperationStateCorrupt("operation plan instrument keys are invalid")
        if (
            not isinstance(item["days"], int) or isinstance(item["days"], bool)
            or item["days"] < 0 or item["days"] > 100_000
            or not isinstance(item["optimize_search"], bool)
        ):
            raise OperationStateCorrupt("operation plan item options are invalid")
    payload = {
        "experiment_count": value["experiment_count"],
        "items": value["items"],
    }
    if value["content_address"] != content_address(payload):
        raise OperationStateCorrupt("operation plan content address does not match")


def _validate_operation(value: Any, *, active: bool) -> None:
    if value is None:
        return
    fields = {
        "operation_id", "trigger", "state", "stage", "started_at", "completed_at",
        "build", "provider_mode", "plan", "completed_run_ids", "failure",
    }
    if not isinstance(value, dict) or set(value) != fields:
        raise OperationStateCorrupt("operation has unknown or missing fields")
    if value["trigger"] not in TRIGGERS or value["stage"] not in STAGES:
        raise OperationStateCorrupt("operation trigger or stage is unsupported")
    expected_states = {"running"} if active else {"completed", "failed"}
    if value["state"] not in expected_states:
        raise OperationStateCorrupt("operation state is inconsistent with its slot")
    for key in ("operation_id", "started_at", "build", "provider_mode"):
        if not isinstance(value[key], str) or not value[key] or len(value[key]) > 200:
            raise OperationStateCorrupt(f"operation {key} is invalid")
    if value["completed_at"] is not None and not isinstance(value["completed_at"], str):
        raise OperationStateCorrupt("operation completion timestamp is invalid")
    run_ids = value["completed_run_ids"]
    if (
        not isinstance(run_ids, list)
        or any(not isinstance(run_id, int) or isinstance(run_id, bool) or run_id < 1
               for run_id in run_ids)
        or len(run_ids) != len(set(run_ids))
    ):
        raise OperationStateCorrupt("operation run ids are invalid")
    _validate_plan(value["plan"])
    _validate_failure(value["failure"])
    if active and (value["completed_at"] is not None or value["failure"] is not None):
        raise OperationStateCorrupt("active operation has terminal fields")
    if not active and not value["completed_at"]:
        raise OperationStateCorrupt("terminal operation has no completion timestamp")
    if value["state"] == "completed" and (
        value["stage"] != "completed" or value["failure"] is not None
    ):
        raise OperationStateCorrupt("completed operation has inconsistent fields")
    if value["state"] == "failed" and (
        value["stage"] == "completed" or value["failure"] is None
    ):
        raise OperationStateCorrupt("failed operation has inconsistent fields")


def _validate_state(state: Any) -> None:
    if not isinstance(state, dict) or set(state) != {"active", "last"}:
        raise OperationStateCorrupt("operation state has unknown or missing fields")
    _validate_operation(state["active"], active=True)
    _validate_operation(state["last"], active=False)


def encode_operation_state(state: Mapping[str, Any]) -> str:
    canonical_state = json.loads(canonical_json(dict(state)))
    _validate_state(canonical_state)
    raw = canonical_json({
        "schema_version": SCHEMA_VERSION,
        "content_address": content_address(canonical_state),
        "operations": canonical_state,
    })
    if len(raw.encode("utf-8")) > MAX_OPERATION_BYTES:
        raise OperationStateCorrupt("operation state exceeds the size limit")
    return raw


def decode_operation_state(raw: str) -> dict[str, Any]:
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > MAX_OPERATION_BYTES:
        raise OperationStateCorrupt("operation state is missing or exceeds the size limit")
    try:
        envelope = json.loads(raw, parse_constant=_reject_constant)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise OperationStateCorrupt("operation state is invalid JSON") from exc
    if not isinstance(envelope, dict) or set(envelope) != {
        "schema_version", "content_address", "operations"
    }:
        raise OperationStateCorrupt("operation envelope has unknown or missing fields")
    if envelope["schema_version"] != SCHEMA_VERSION:
        raise OperationStateCorrupt("operation schema version is unsupported")
    state = envelope["operations"]
    _validate_state(state)
    if envelope["content_address"] != content_address(state):
        raise OperationStateCorrupt("operation content address does not match")
    if raw != canonical_json(envelope):
        raise OperationStateCorrupt("operation state is not canonical JSON")
    return state


def _write_atomic(path: Path, raw: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    descriptor = None
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        data = raw.encode("utf-8")
        offset = 0
        while offset < len(data):
            offset += os.write(descriptor, data[offset:])
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = None
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temporary.exists():
            temporary.unlink()


@contextlib.contextmanager
def acquire_operation_lock(path: str | os.PathLike) -> Iterator[None]:
    lock_path = Path(path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    os.chmod(lock_path, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise OperationAlreadyRunning(
                "RESEARCH_OPERATION_ALREADY_RUNNING"
            ) from exc
        yield
    finally:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


def _text(value: Any, limit: int) -> str:
    return str(value)[:limit]


def safe_plan_summary(plan: list[dict]) -> dict[str, Any]:
    if not isinstance(plan, list) or len(plan) > 64:
        raise OperationStateCorrupt("operation plan has too many items")
    items = []
    for item in plan:
        if not isinstance(item, dict):
            raise OperationStateCorrupt("operation plan item is invalid")
        instruments = item.get("instruments", [])
        if not isinstance(instruments, list) or len(instruments) > 64:
            raise OperationStateCorrupt("operation plan instruments are invalid")
        for field, limit in (("program", 80), ("hypothesis", 4000),
                             ("strategy_key", 80), ("interval", 24)):
            value = item.get(field, "")
            if not isinstance(value, str) or not value or len(value) > limit:
                raise OperationStateCorrupt(f"operation plan {field} is invalid")
        days = item.get("days", 0)
        if (not isinstance(days, int) or isinstance(days, bool)
                or days < 0 or days > 100_000):
            raise OperationStateCorrupt("operation plan days are invalid")
        optimize_search = item.get("optimize_search", False)
        if not isinstance(optimize_search, bool):
            raise OperationStateCorrupt("operation plan optimize_search is invalid")
        for instrument in instruments:
            key = getattr(instrument, "key", instrument)
            if not isinstance(key, str) or not key or len(key) > 48:
                raise OperationStateCorrupt("operation plan instrument key is invalid")
        keys = [
            _text(getattr(instrument, "key", instrument), 48)
            for instrument in instruments[:64]
        ]
        items.append({
            "program": _text(item.get("program", ""), 80),
            "hypothesis": _text(item.get("hypothesis", ""), 4000),
            "strategy_key": _text(item.get("strategy_key", ""), 80),
            "instrument_keys": keys,
            "interval": _text(item.get("interval", ""), 24),
            "days": days,
            "optimize_search": optimize_search,
        })
    payload = {"experiment_count": len(items), "items": items}
    return {"content_address": content_address(payload), **payload}


def _failure(stage: str, *, interrupted: bool = False) -> dict[str, str]:
    if interrupted:
        return {
            "stage": "startup",
            "code": "RESEARCH_OPERATION_INTERRUPTED",
            "message": "previous research operation ended without a terminal receipt",
        }
    normalized = stage if stage in STAGES - {"completed"} else "startup"
    return {
        "stage": normalized,
        "code": f"RESEARCH_{normalized.upper()}_FAILED",
        "message": f"research {normalized} failed",
    }


class ResearchOperationRecorder:
    def __init__(self, path: Path, state: dict[str, Any]):
        self.path = path
        self.state = state

    @classmethod
    def load(cls, path: str | os.PathLike) -> dict[str, Any]:
        receipt = Path(path)
        if not receipt.exists():
            return empty_operation_state()
        try:
            with receipt.open("r", encoding="utf-8") as stream:
                raw = stream.read(MAX_OPERATION_BYTES + 1)
            return decode_operation_state(raw)
        except OSError as exc:
            raise OperationStateCorrupt("operation state cannot be read") from exc

    @classmethod
    def start(
        cls,
        path: str | os.PathLike,
        *,
        trigger: str,
        build: str,
        provider_mode: str,
        operation_id: str | None = None,
        now: Callable[[], str],
    ) -> "ResearchOperationRecorder":
        if trigger not in TRIGGERS:
            raise ValueError("unsupported research operation trigger")
        receipt = Path(path)
        state = cls.load(receipt)
        started_at = now()
        if state["active"] is not None:
            stale = dict(state["active"])
            stale.update({
                "state": "failed",
                "completed_at": started_at,
                "failure": _failure("startup", interrupted=True),
            })
            state["last"] = stale
        state["active"] = {
            "operation_id": operation_id or uuid.uuid4().hex,
            "trigger": trigger,
            "state": "running",
            "stage": "startup",
            "started_at": started_at,
            "completed_at": None,
            "build": _text(build or "unknown", 40),
            "provider_mode": _text(provider_mode or "unknown", 80),
            "plan": None,
            "completed_run_ids": [],
            "failure": None,
        }
        recorder = cls(receipt, state)
        recorder._persist()
        return recorder

    def _persist(self) -> None:
        _write_atomic(self.path, encode_operation_state(self.state))

    @property
    def active(self) -> dict[str, Any]:
        active = self.state.get("active")
        if active is None:
            raise RuntimeError("research operation is already terminal")
        return active

    def set_plan(self, plan: dict[str, Any]) -> None:
        _validate_plan(plan)
        self.active["plan"] = plan
        self.active["stage"] = "planning"
        self._persist()

    def transition(self, stage: str) -> None:
        if stage not in STAGES - {"completed"}:
            raise ValueError("unsupported research operation stage")
        self.active["stage"] = stage
        self._persist()

    def add_completed_run(self, run_id: int) -> None:
        if not isinstance(run_id, int) or isinstance(run_id, bool) or run_id < 1:
            raise ValueError("completed run id must be a positive integer")
        if run_id not in self.active["completed_run_ids"]:
            self.active["completed_run_ids"].append(run_id)
            self._persist()

    def complete(self, *, now: Callable[[], str]) -> None:
        operation = dict(self.active)
        operation.update({
            "state": "completed",
            "stage": "completed",
            "completed_at": now(),
            "failure": None,
        })
        self.state = {"active": None, "last": operation}
        self._persist()

    def fail(self, *, now: Callable[[], str]) -> None:
        operation = dict(self.active)
        operation.update({
            "state": "failed",
            "completed_at": now(),
            "failure": _failure(operation["stage"]),
        })
        self.state = {"active": None, "last": operation}
        self._persist()


__all__ = [
    "OperationAlreadyRunning",
    "OperationStateCorrupt",
    "ResearchOperationRecorder",
    "acquire_operation_lock",
    "decode_operation_state",
    "empty_operation_state",
    "encode_operation_state",
    "safe_plan_summary",
]
