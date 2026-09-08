#!/usr/bin/env python3
"""Select one safe Strategy OS programme action without mutating tracked state."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RUNNABLE = {"ready", "correction", "review"}
VALID_STATUSES = RUNNABLE | {"active", "blocked", "accepted", "paused_owner_gate"}
FORBIDDEN_EFFORTS = {"xhigh", "ultra", "max"}
LEASE_MAX_SECONDS = 6 * 60 * 60
STAGE_ROUTES = {
    "correction": ("gpt-5.6-sol", "medium"),
    "implementation_sequence": ("gpt-5.6-sol", "medium"),
    "phase_architecture": ("gpt-5.6-sol", "medium"),
    "interphase_architecture": ("gpt-5.6-sol", "medium"),
    "critical_runtime_lifecycle": ("gpt-5.6-sol", "medium"),
    "independent_assurance": ("gpt-5.6-sol", "medium"),
    "critical_architecture": ("gpt-5.6-sol", "medium"),
    "phase_review": ("gpt-5.6-sol", "high"),
    "release_review": ("gpt-5.6-sol", "high"),
}


class InvalidProgramme(ValueError):
    pass


def contained(root: Path, value: object, label: str, *, must_exist: bool = True) -> Path:
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise InvalidProgramme(f"{label} must be one repository-relative path")
    path = (root / value).resolve()
    if root != path and root not in path.parents:
        raise InvalidProgramme(f"{label} escapes the repository")
    if must_exist and not path.is_file():
        raise InvalidProgramme(f"{label} does not exist: {value}")
    return path


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InvalidProgramme(f"invalid {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise InvalidProgramme(f"{label} must be a JSON object")
    return value


def load_capsule(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
        parts = text.split("---", 2)
        if len(parts) != 3:
            raise InvalidProgramme("active capsule lacks JSON/YAML-compatible frontmatter")
        value = json.loads(parts[1])
    except (OSError, json.JSONDecodeError) as exc:
        raise InvalidProgramme(f"invalid active capsule: {exc}") from exc
    if not isinstance(value, dict):
        raise InvalidProgramme("active capsule frontmatter must be an object")
    return value


def markdown_headings(path: Path) -> list[tuple[int, str]]:
    headings = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^(#{1,4})\s+(.+?)\s*$", line)
        if match:
            headings.append((len(match.group(1)), match.group(2)))
    return headings


def validate_source_map(root: Path, source_map: dict[str, Any]) -> None:
    if source_map.get("schema_version") != 1:
        raise InvalidProgramme("source map schema is invalid")
    sources = source_map.get("sources")
    views = source_map.get("phase_views")
    if not isinstance(sources, list) or not isinstance(views, dict):
        raise InvalidProgramme("source map lacks sources or phase views")
    routed: dict[tuple[str, str], set[str]] = {}
    source_sections: dict[tuple[str, str], set[str]] = {}
    source_ids: set[str] = set()
    for source in sources:
        if not isinstance(source, dict) or not isinstance(source.get("id"), str):
            raise InvalidProgramme("source map contains an invalid source")
        source_id = source["id"]
        if source_id in source_ids:
            raise InvalidProgramme(f"source map duplicates source: {source_id}")
        source_ids.add(source_id)
        source_path = contained(root, source.get("path"), f"source {source_id}")
        if source.get("sha256") != hashlib.sha256(source_path.read_bytes()).hexdigest():
            raise InvalidProgramme(f"source hash is stale: {source_id}")
        sections = source.get("sections")
        if not isinstance(sections, list):
            raise InvalidProgramme(f"source sections are invalid: {source_id}")
        declared: list[tuple[int, str]] = []
        for section in sections:
            if not isinstance(section, dict):
                raise InvalidProgramme(f"source section is invalid: {source_id}")
            level, heading, consumers = section.get("level"), section.get("heading"), section.get("consumers")
            if (
                not isinstance(level, int)
                or not isinstance(heading, str)
                or not heading
                or not isinstance(consumers, list)
                or not consumers
                or not all(isinstance(item, str) and item for item in consumers)
            ):
                raise InvalidProgramme(f"source section is invalid: {source_id}")
            declared.append((level, heading))
            source_sections[(source_id, heading)] = set(consumers)
        if declared != markdown_headings(source_path):
            raise InvalidProgramme(f"source heading coverage is stale: {source_id}")
    for phase, entries in views.items():
        if not isinstance(phase, str) or not isinstance(entries, list) or not entries:
            raise InvalidProgramme(f"source map phase view is invalid: {phase}")
        for entry in entries:
            if not isinstance(entry, dict):
                raise InvalidProgramme(f"source map phase entry is invalid: {phase}")
            key = (entry.get("source_id"), entry.get("heading"))
            if key not in source_sections or phase not in source_sections[key]:
                raise InvalidProgramme(f"source map phase entry is not routed: {phase}")
            routed.setdefault(key, set()).add(phase)
    if any(routed.get(key, set()) != consumers for key, consumers in source_sections.items()):
        raise InvalidProgramme("source map phase coverage is incomplete")


def parse_time(value: object) -> datetime:
    if not isinstance(value, str):
        raise InvalidProgramme("controller lease has no timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InvalidProgramme("controller lease timestamp is invalid") from exc
    if parsed.tzinfo is None:
        raise InvalidProgramme("controller lease timestamp lacks timezone")
    return parsed.astimezone(timezone.utc)


def phase_view(root: Path, source_map: dict[str, Any], phase: str) -> dict[str, Any]:
    views = source_map.get("phase_views")
    sources = source_map.get("sources")
    if not isinstance(views, dict) or not isinstance(sources, list):
        raise InvalidProgramme("source map lacks phase_views or sources")
    entries = views.get(phase)
    if not isinstance(entries, list) or not entries:
        raise InvalidProgramme(f"source map has no phase view: {phase}")
    source_paths = {
        item.get("id"): item.get("path")
        for item in sources
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    grouped: dict[str, list[str]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise InvalidProgramme(f"invalid source-map entry for {phase}")
        source_id, heading = entry.get("source_id"), entry.get("heading")
        path = source_paths.get(source_id)
        if not isinstance(path, str) or not isinstance(heading, str) or not heading:
            raise InvalidProgramme(f"invalid source-map entry for {phase}")
        contained(root, path, f"source {source_id}", must_exist=False)
        grouped.setdefault(path, []).append(heading)
    return {
        "phase": phase,
        "required_docs": [
            {"path": path, "sections": headings}
            for path, headings in grouped.items()
        ],
    }


def validate_programme(root: Path, programme: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if programme.get("schema_version") != 1:
        raise InvalidProgramme("unsupported programme schema_version")
    stages = programme.get("stages")
    if not isinstance(stages, list) or not stages:
        raise InvalidProgramme("programme has no stages")
    if [item.get("order") for item in stages if isinstance(item, dict)] != list(range(1, len(stages) + 1)):
        raise InvalidProgramme("programme stage order is not contiguous")
    ids = [item.get("id") for item in stages if isinstance(item, dict)]
    if len(ids) != len(stages) or len(set(ids)) != len(ids) or not all(isinstance(item, str) and item for item in ids):
        raise InvalidProgramme("programme stage IDs are invalid or duplicated")
    indexed = {stage["id"]: stage for stage in stages}
    current_id = programme.get("current_stage_id")
    if current_id not in indexed:
        raise InvalidProgramme("current_stage_id does not exist")
    seen: set[str] = set()
    for index, stage in enumerate(stages):
        status = stage.get("status")
        if status not in VALID_STATUSES:
            raise InvalidProgramme(f"invalid status for {stage['id']}: {status}")
        dependencies = stage.get("depends_on")
        if not isinstance(dependencies, list) or not all(isinstance(item, str) for item in dependencies):
            raise InvalidProgramme(f"invalid dependencies for {stage['id']}")
        if not set(dependencies) <= seen:
            raise InvalidProgramme(f"dependency ordering is invalid for {stage['id']}")
        expected = [] if index == 0 else [stages[index - 1]["id"]]
        if dependencies != expected:
            raise InvalidProgramme(
                f"exact predecessor is invalid for {stage['id']}: expected {expected}"
            )
        seen.add(stage["id"])
    current = indexed[current_id]
    for dependency in current["depends_on"]:
        if indexed[dependency].get("status") != "accepted":
            raise InvalidProgramme(f"dependency is not accepted: {dependency}")
    first_unfinished = next((stage for stage in stages if stage.get("status") != "accepted"), None)
    if first_unfinished is not None and first_unfinished["id"] != current_id:
        raise InvalidProgramme(f"current stage is not the first unfinished dependency: {first_unfinished['id']}")
    return stages, current


def action_for(
    root: Path,
    programme: dict[str, Any],
    current: dict[str, Any],
    source_map: dict[str, Any],
    *,
    active_goal_count: int | None,
    controller_path: Path,
    now: datetime,
) -> tuple[int, dict[str, Any]]:
    if active_goal_count is not None and active_goal_count < 0:
        raise InvalidProgramme("active goal count cannot be negative")
    if active_goal_count is not None and active_goal_count > 1:
        return 2, {"action": "pause", "stage_id": current["id"], "reason": "more than one active goal owns the programme"}
    if active_goal_count == 1:
        return 0, {"action": "monitor", "stage_id": current["id"], "reason": "one active goal already owns the programme"}

    if controller_path.exists():
        controller = load_json(controller_path, "controller state")
        lease = controller.get("active_goal")
        if lease is not None:
            if not isinstance(lease, dict):
                raise InvalidProgramme("controller active_goal must be an object")
            status = lease.get("status")
            if status in {"reserved", "running", "needs_input"}:
                updated = parse_time(lease.get("updated_at"))
                age = (now - updated).total_seconds()
                if age > LEASE_MAX_SECONDS:
                    return 2, {"action": "pause", "stage_id": current["id"], "reason": "active goal lease is stale; inspect before dispatching a duplicate"}
                if lease.get("stage_id") != current["id"]:
                    return 2, {"action": "pause", "stage_id": current["id"], "reason": "active goal lease belongs to a different stage"}
                return 0, {"action": "monitor", "stage_id": current["id"], "thread_id": lease.get("thread_id"), "reason": "controller lease is active"}
            if lease.get("stage_id") == current["id"] and status in {"completed", "failed"}:
                return 2, {
                    "action": "pause",
                    "stage_id": current["id"],
                    "reason": f"goal lease is {status} but the tracked programme has not advanced",
                }

    status = current.get("status")
    if status == "paused_owner_gate":
        return 2, {"action": "pause", "stage_id": current["id"], "reason": "current stage is paused at an owner gate"}
    if status == "blocked":
        return 2, {"action": "pause", "stage_id": current["id"], "reason": "current stage remains blocked"}
    if status == "active":
        return 2, {"action": "pause", "stage_id": current["id"], "reason": "stage is active without a valid controller lease"}
    if status not in RUNNABLE:
        return 2, {"action": "pause", "stage_id": current["id"], "reason": f"current stage is not dispatchable: {status}"}
    if active_goal_count is None:
        return 2, {
            "action": "pause",
            "stage_id": current["id"],
            "reason": "active goal state is unknown; use an authoritative query or atomic claim",
        }

    capsule_value = current.get("capsule")
    capsule_path = contained(root, capsule_value, "active capsule")
    capsule = load_capsule(capsule_path)
    if capsule.get("id") != current["id"]:
        raise InvalidProgramme("active capsule ID does not match current stage")
    source_view = current.get("source_view")
    if source_view != current.get("phase"):
        raise InvalidProgramme("current stage source view does not match its phase")
    phase_view(root, source_map, str(source_view))
    goal_contract = capsule.get("goal_contract")
    if not isinstance(goal_contract, dict) or goal_contract.get("create_before_work") is not True:
        raise InvalidProgramme("active capsule lacks create-before-work goal contract")
    goal, stop = capsule.get("goal"), goal_contract.get("stopping_condition")
    if not isinstance(goal, str) or not goal or not isinstance(stop, str) or not stop:
        raise InvalidProgramme("active capsule lacks goal or stopping condition")
    model, effort = current.get("model"), current.get("reasoning_effort")
    if not isinstance(model, str) or not isinstance(effort, str) or effort in FORBIDDEN_EFFORTS:
        raise InvalidProgramme("active stage route is invalid or forbidden")
    expected_route = STAGE_ROUTES.get(str(current.get("kind")))
    if expected_route is None or (model, effort) != expected_route:
        raise InvalidProgramme("active stage route does not match its kind")
    model_route = capsule.get("model_route")
    if (
        not isinstance(model_route, dict)
        or model_route.get("owner") != model
        or model_route.get("owner_reasoning_effort") != effort
    ):
        raise InvalidProgramme("active capsule route does not match current stage")
    return 0, {
        "action": "dispatch",
        "stage_id": current["id"],
        "phase": current.get("phase"),
        "kind": current.get("kind"),
        "title": f"Strategy OS {current['id']}",
        "capsule": capsule_value,
        "model": model,
        "reasoning_effort": effort,
        "goal_objective": f"{goal} {stop}",
        "reason": "current stage is ready and has no active goal",
    }


def write_controller(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.{os.getpid()}.tmp"
    temporary.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)


def write_claim(path: Path, stage_id: str, now: datetime) -> str:
    claim_id = uuid.uuid4().hex
    write_controller(path, {
        "schema_version": 1,
        "active_goal": {
            "claim_id": claim_id,
            "thread_id": None,
            "stage_id": stage_id,
            "status": "reserved",
            "updated_at": now.isoformat(),
        },
    })
    return claim_id


def update_claim(
    path: Path,
    *,
    claim_id: str,
    stage_id: str,
    now: datetime,
    thread_id: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    if not path.is_file():
        raise InvalidProgramme("controller claim does not exist")
    state = load_json(path, "controller state")
    lease = state.get("active_goal")
    if not isinstance(lease, dict) or lease.get("claim_id") != claim_id:
        raise InvalidProgramme("controller claim ID does not match the active lease")
    if lease.get("stage_id") != stage_id:
        raise InvalidProgramme("controller claim belongs to a different stage")
    if thread_id is not None:
        if not thread_id.strip():
            raise InvalidProgramme("thread ID cannot be empty")
        if lease.get("status") not in {"reserved", "running"}:
            raise InvalidProgramme("only a reserved or running claim can be bound")
        lease["thread_id"] = thread_id
        lease["status"] = "running"
    if status is not None:
        allowed = {"running", "needs_input", "completed", "failed"}
        if status not in allowed:
            raise InvalidProgramme(f"invalid lease status: {status}")
        if not lease.get("thread_id") and status != "failed":
            raise InvalidProgramme("an unbound claim cannot enter that status")
        lease["status"] = status
    lease["updated_at"] = now.isoformat()
    write_controller(path, state)
    return lease


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--active-goal-count", type=int)
    parser.add_argument("--controller-state", type=Path)
    parser.add_argument("--claim", action="store_true")
    parser.add_argument("--bind-thread", nargs=2, metavar=("CLAIM_ID", "THREAD_ID"))
    parser.add_argument(
        "--update-lease",
        nargs=2,
        metavar=("CLAIM_ID", "STATUS"),
    )
    parser.add_argument("--phase-view")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    output: dict[str, Any]
    code = 0
    try:
        programme_path = root / "paper-trader" / "docs" / "agent" / "programme" / "PROGRAMME.json"
        programme = load_json(programme_path, "programme")
        source_path = contained(root, programme.get("source_map"), "source map")
        source_map = load_json(source_path, "source map")
        validate_source_map(root, source_map)
        if args.phase_view:
            output = phase_view(root, source_map, args.phase_view)
        else:
            stages, current = validate_programme(root, programme)
            if programme.get("status") == "complete":
                if (
                    any(stage.get("status") != "accepted" for stage in stages)
                    or current["id"] != stages[-1]["id"]
                    or stages[-1].get("kind") != "release_review"
                ):
                    raise InvalidProgramme(
                        "programme status complete requires every stage and the final release review to be accepted"
                    )
                output = {"action": "complete", "stage_id": current["id"], "reason": "all stages and the final release review are accepted"}
                print(json.dumps(output, sort_keys=True))
                return 0
            controller = args.controller_state or (root / ".agent" / "programme" / "controller.json")
            controller = controller.resolve()
            allowed = (root / ".agent" / "programme").resolve()
            if allowed != controller and allowed not in controller.parents:
                raise InvalidProgramme("controller state must stay under .agent/programme")
            now = datetime.now(timezone.utc)
            mutations = sum(bool(value) for value in (args.claim, args.bind_thread, args.update_lease))
            if mutations > 1:
                raise InvalidProgramme("claim, bind-thread, and update-lease are mutually exclusive")
            if args.bind_thread or args.update_lease:
                controller.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                lock_path = controller.parent / "controller.lock"
                with lock_path.open("a+", encoding="utf-8") as lock:
                    fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
                    if args.bind_thread:
                        claim_id, thread_id = args.bind_thread
                        lease = update_claim(
                            controller,
                            claim_id=claim_id,
                            stage_id=current["id"],
                            now=now,
                            thread_id=thread_id,
                        )
                    else:
                        claim_id, status = args.update_lease
                        lease = update_claim(
                            controller,
                            claim_id=claim_id,
                            stage_id=current["id"],
                            now=now,
                            status=status,
                        )
                    output = {
                        "action": "monitor" if lease["status"] in {"reserved", "running", "needs_input"} else "recorded",
                        "stage_id": current["id"],
                        "thread_id": lease.get("thread_id"),
                        "status": lease["status"],
                    }
            elif args.claim:
                if args.active_goal_count is None:
                    raise InvalidProgramme(
                        "atomic claim requires an authoritative active goal count"
                    )
                controller.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                lock_path = controller.parent / "controller.lock"
                with lock_path.open("a+", encoding="utf-8") as lock:
                    fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
                    code, output = action_for(
                        root,
                        programme,
                        current,
                        source_map,
                        active_goal_count=args.active_goal_count,
                        controller_path=controller,
                        now=now,
                    )
                    if output.get("action") == "dispatch":
                        output["claim_id"] = write_claim(controller, current["id"], now)
            else:
                code, output = action_for(
                    root,
                    programme,
                    current,
                    source_map,
                    active_goal_count=args.active_goal_count,
                    controller_path=controller,
                    now=now,
                )
    except InvalidProgramme as exc:
        code = 2
        output = {"action": "pause", "stage_id": None, "reason": str(exc)}
    print(json.dumps(output, sort_keys=True))
    return code


if __name__ == "__main__":
    sys.exit(main())
