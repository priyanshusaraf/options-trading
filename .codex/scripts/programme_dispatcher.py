#!/usr/bin/env python3
"""Select one safe Strategy OS programme action without mutating tracked state."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RUNNABLE = {"ready", "correction", "review"}
VALID_STATUSES = RUNNABLE | {"active", "blocked", "accepted", "paused_owner_gate"}
FORBIDDEN_EFFORTS = {"xhigh", "ultra", "max"}
LEASE_MAX_SECONDS = 6 * 60 * 60


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
    for stage in stages:
        status = stage.get("status")
        if status not in VALID_STATUSES:
            raise InvalidProgramme(f"invalid status for {stage['id']}: {status}")
        dependencies = stage.get("depends_on")
        if not isinstance(dependencies, list) or not all(isinstance(item, str) for item in dependencies):
            raise InvalidProgramme(f"invalid dependencies for {stage['id']}")
        if not set(dependencies) <= seen:
            raise InvalidProgramme(f"dependency ordering is invalid for {stage['id']}")
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
    *,
    active_goal_count: int,
    controller_path: Path,
    now: datetime,
) -> tuple[int, dict[str, Any]]:
    if active_goal_count < 0:
        raise InvalidProgramme("active goal count cannot be negative")
    if active_goal_count > 1:
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
            if status in {"running", "needs_input"}:
                updated = parse_time(lease.get("updated_at"))
                age = (now - updated).total_seconds()
                if age > LEASE_MAX_SECONDS:
                    return 2, {"action": "pause", "stage_id": current["id"], "reason": "active goal lease is stale; inspect before dispatching a duplicate"}
                if lease.get("stage_id") != current["id"]:
                    return 2, {"action": "pause", "stage_id": current["id"], "reason": "active goal lease belongs to a different stage"}
                return 0, {"action": "monitor", "stage_id": current["id"], "thread_id": lease.get("thread_id"), "reason": "controller lease is active"}

    status = current.get("status")
    if status == "paused_owner_gate":
        return 2, {"action": "pause", "stage_id": current["id"], "reason": "current stage is paused at an owner gate"}
    if status == "blocked":
        return 2, {"action": "pause", "stage_id": current["id"], "reason": "current stage remains blocked"}
    if status == "active":
        return 2, {"action": "pause", "stage_id": current["id"], "reason": "stage is active without a valid controller lease"}
    if status not in RUNNABLE:
        return 2, {"action": "pause", "stage_id": current["id"], "reason": f"current stage is not dispatchable: {status}"}

    capsule_value = current.get("capsule")
    capsule_path = contained(root, capsule_value, "active capsule")
    capsule = load_capsule(capsule_path)
    goal_contract = capsule.get("goal_contract")
    if not isinstance(goal_contract, dict) or goal_contract.get("create_before_work") is not True:
        raise InvalidProgramme("active capsule lacks create-before-work goal contract")
    goal, stop = capsule.get("goal"), goal_contract.get("stopping_condition")
    if not isinstance(goal, str) or not goal or not isinstance(stop, str) or not stop:
        raise InvalidProgramme("active capsule lacks goal or stopping condition")
    model, effort = current.get("model"), current.get("reasoning_effort")
    if not isinstance(model, str) or not isinstance(effort, str) or effort in FORBIDDEN_EFFORTS:
        raise InvalidProgramme("active stage route is invalid or forbidden")
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--active-goal-count", type=int, default=0)
    parser.add_argument("--controller-state", type=Path)
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
        if args.phase_view:
            output = phase_view(root, source_map, args.phase_view)
        elif programme.get("status") == "complete":
            output = {"action": "complete", "stage_id": programme.get("current_stage_id"), "reason": "programme status is complete"}
        else:
            _, current = validate_programme(root, programme)
            controller = args.controller_state or (root / ".agent" / "programme" / "controller.json")
            controller = controller.resolve()
            allowed = (root / ".agent" / "programme").resolve()
            if allowed != controller and allowed not in controller.parents:
                raise InvalidProgramme("controller state must stay under .agent/programme")
            code, output = action_for(
                root,
                programme,
                current,
                active_goal_count=args.active_goal_count,
                controller_path=controller,
                now=datetime.now(timezone.utc),
            )
    except InvalidProgramme as exc:
        code = 2
        output = {"action": "pause", "stage_id": None, "reason": str(exc)}
    print(json.dumps(output, sort_keys=True))
    return code


if __name__ == "__main__":
    sys.exit(main())
