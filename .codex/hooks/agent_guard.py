#!/usr/bin/env python3
"""Capsule-aware guard for declared Codex agent launches."""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple


def deny(reason: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )


def allow_updated(tool_input: dict) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "updatedInput": tool_input,
                }
            }
        )
    )


def capsule(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError("capsule is missing JSON frontmatter")
    data = json.loads(text.split("---", 2)[1])
    if not isinstance(data, dict):
        raise ValueError("capsule frontmatter must be an object")
    return data


def run_git(repo: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=repo)


def git_root() -> Path:
    if os.environ.get("STRATEGY_OS_REPO_ROOT"):
        return Path(os.environ["STRATEGY_OS_REPO_ROOT"]).resolve()
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return Path(result.stdout.strip()).resolve() if result.returncode == 0 else Path.cwd().resolve()


def active_capsule(repo: Path, task_name: object = None) -> Path:
    if os.environ.get("STRATEGY_OS_CAPSULE_PATH"):
        return Path(os.environ["STRATEGY_OS_CAPSULE_PATH"]).resolve()
    current = capsule(repo / "paper-trader" / "docs" / "agent" / "CURRENT.md")
    review_capsules = current.get("review_capsules", {})
    if not isinstance(review_capsules, dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in review_capsules.items()
    ):
        raise ValueError("CURRENT.md review_capsules is invalid")
    location = review_capsules.get(task_name, current.get("active_capsule"))
    if not isinstance(location, str) or not location:
        raise ValueError("CURRENT.md has no active_capsule")
    resolved = (repo / location).resolve()
    if repo not in resolved.parents:
        raise ValueError("active_capsule escapes repository")
    return resolved


def trace_payload(repo: Path, payload: dict) -> Optional[str]:
    """Optionally retain a prompt-free native hook contract trace for diagnostics."""
    configured = os.environ.get("STRATEGY_OS_HOOK_TRACE")
    if not configured:
        return None
    try:
        path = Path(configured).resolve()
        if repo not in path.parents:
            raise ValueError("trace path must stay inside the repository")
        tool = payload.get("tool_input", {})
        if not isinstance(tool, dict):
            tool = {}
        record = {
            "tool_name": payload.get("tool_name"),
            "tool_input_keys": sorted(str(key) for key in tool),
            "task_name": tool.get("task_name"),
            "agent_type": tool.get("agent_type"),
            "model": tool.get("model"),
            "reasoning_effort": tool.get("reasoning_effort"),
            "fork_turns": tool.get("fork_turns"),
        }
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with path.open("a+", encoding="utf-8") as output:
            fcntl.flock(output.fileno(), fcntl.LOCK_EX)
            output.write(json.dumps(record, sort_keys=True) + "\n")
            output.flush()
        os.chmod(path, 0o600)
        return None
    except (OSError, TypeError, ValueError) as exc:
        return f"agent guard trace is unavailable: {exc}"


def safe_key(value: object) -> str:
    return hashlib.sha256(str(value).encode()).hexdigest()


def overlaps(left: str, right: str) -> bool:
    a, b = (Path(left).as_posix().strip("/"), Path(right).as_posix().strip("/"))
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


def path_matches(path: str, prefix: str) -> bool:
    return path == prefix or path.startswith(prefix + "/")


def normalized_paths(value: object, label: str) -> List[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise ValueError(f"{label} must be a list of repository-relative paths")
    result = []
    for item in value:
        candidate = Path(item)
        if candidate.is_absolute() or any(part in {"", ".", ".."} for part in candidate.parts):
            raise ValueError(f"{label} contains an invalid path: {item}")
        result.append(candidate.as_posix().strip("/"))
    return sorted(set(result))


def contained_file(repo: Path, value: object, label: str) -> Tuple[str, Path]:
    paths = normalized_paths([value] if isinstance(value, str) else value, label)
    if len(paths) != 1:
        raise ValueError(f"{label} must name one repository file")
    relative = paths[0]
    resolved = (repo / relative).resolve()
    if repo not in resolved.parents or not resolved.is_file():
        raise ValueError(f"{label} escapes the repository or does not exist: {relative}")
    return relative, resolved


def fingerprint(repo: Path, excluded: Path) -> str:
    try:
        excluded_name = excluded.resolve().relative_to(repo).as_posix().encode()
        digest = hashlib.sha256()
        for label, command in (
            (b"worktree", ("diff", "--binary", "--no-ext-diff")),
            (b"index", ("diff", "--cached", "--binary", "--no-ext-diff")),
        ):
            digest.update(label + b"\0" + run_git(repo, *command) + b"\0")
        untracked = run_git(repo, "ls-files", "--others", "--exclude-standard", "-z").split(b"\0")
        for entry in sorted(item for item in untracked if item and item != excluded_name):
            digest.update(b"untracked\0" + entry + b"\0" + (repo / entry.decode()).read_bytes() + b"\0")
        return digest.hexdigest()
    except (OSError, ValueError, subprocess.CalledProcessError):
        return ""


def current_changed_paths(repo: Path, excluded: Path) -> List[str]:
    excluded_name = excluded.resolve().relative_to(repo).as_posix()
    path_sets = (
        run_git(repo, "diff", "--name-only", "-z"),
        run_git(repo, "diff", "--cached", "--name-only", "-z"),
        run_git(repo, "ls-files", "--others", "--exclude-standard", "-z"),
    )
    return sorted(
        {
            entry.decode("utf-8", "replace")
            for paths in path_sets
            for entry in paths.split(b"\0")
            if entry
            and entry.decode("utf-8", "replace") != excluded_name
            and not entry.startswith(b".agent/")
        }
    )


def commit_changed_paths(repo: Path, base_sha: str, head_sha: str) -> List[str]:
    output = run_git(
        repo,
        "diff",
        "--name-only",
        "-z",
        "--no-ext-diff",
        f"{base_sha}..{head_sha}",
    )
    return sorted(
        entry.decode("utf-8", "replace")
        for entry in output.split(b"\0")
        if entry
    )


def commit_diff_digest(repo: Path, base_sha: str, head_sha: str) -> str:
    diff = run_git(repo, "diff", "--binary", "--no-ext-diff", f"{base_sha}..{head_sha}")
    return hashlib.sha256(diff).hexdigest()


def state_directory(repo: Path) -> Path:
    configured = os.environ.get("STRATEGY_OS_AGENT_STATE_DIR")
    if configured:
        return Path(configured).resolve()
    common = run_git(repo, "rev-parse", "--git-common-dir").decode().strip()
    common_path = Path(common)
    if not common_path.is_absolute():
        common_path = repo / common_path
    return common_path.resolve() / "codex-agent-state"


def update_state(
    directory: Path,
    key: str,
    updater: Callable[[Dict[str, object]], Optional[str]],
) -> Optional[str]:
    try:
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        lock_path = directory / f"{key}.lock"
        state_path = directory / f"{key}.json"
        with lock_path.open("a+", encoding="utf-8") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            if state_path.exists():
                try:
                    state = json.loads(state_path.read_text(encoding="utf-8"))
                except (OSError, ValueError, json.JSONDecodeError):
                    return "agent guard state is invalid; stop and inspect it"
                if not isinstance(state, dict):
                    return "agent guard state is invalid; stop and inspect it"
            else:
                state = {}
            reason = updater(state)
            if reason:
                return reason
            temporary = directory / f".{key}.{os.getpid()}.tmp"
            temporary.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")
            os.chmod(temporary, 0o600)
            os.replace(temporary, state_path)
            return None
    except (OSError, subprocess.CalledProcessError) as exc:
        return f"agent guard state is unavailable: {exc}"


def validate_route(
    tool: dict,
    expected_agent: str,
    expected_model: str,
    expected_effort: str,
    escalation_reason: str = "",
) -> Tuple[Optional[dict], Optional[str]]:
    if tool.get("fork_turns") != "none":
        return None, "fork_turns must be none"
    actual_agent = tool.get("agent_type")
    updated = None
    if actual_agent is None or actual_agent == "default":
        updated = dict(tool)
        updated["agent_type"] = expected_agent
    elif actual_agent != expected_agent:
        return None, "agent type differs from declared assignment"
    actual_model = tool.get("model")
    if actual_model is None:
        updated = dict(updated or tool)
        updated["model"] = expected_model
    elif actual_model != expected_model:
        return None, "model differs from declared assignment"
    actual_effort = tool.get("reasoning_effort")
    if actual_effort is None:
        updated = dict(updated or tool)
        updated["reasoning_effort"] = expected_effort
        effort = expected_effort
    else:
        effort = str(actual_effort)
    if effort in {"xhigh", "ultra", "max"}:
        return None, f"{effort} reasoning effort is not allowed"
    if effort == "high" and (expected_effort != "high" or not escalation_reason):
        return None, "high reasoning requires a declared escalation"
    if effort != expected_effort:
        return None, "reasoning effort differs from declared assignment"
    return updated, None


def expected_base_sha(repo: Path, review: dict) -> str:
    declared = review.get("base_sha")
    if not isinstance(declared, str) or not declared:
        raise ValueError("review base_sha is missing")
    return run_git(repo, "rev-parse", "--verify", f"{declared}^{{commit}}").decode().strip()


def validate_review_package(repo: Path, data: dict, review: dict) -> Tuple[Optional[dict], Optional[str], Optional[str]]:
    try:
        _, package = contained_file(repo, review.get("package"), "review package")
        package_data = json.loads(package.read_text(encoding="utf-8"))
        if not isinstance(package_data, dict):
            raise ValueError("review package is not an object")
        if package_data.get("task_id") != data.get("id"):
            return None, None, "review package task ID does not match capsule"
        base_sha = expected_base_sha(repo, review)
        if package_data.get("base_sha") != base_sha:
            return None, None, "review package base SHA does not match capsule"
        includes = normalized_paths(review.get("review_paths", []), "review paths")
        excludes = normalized_paths(review.get("exclude_paths", []), "review exclusions")
        if package_data.get("scope_prefixes") != includes or package_data.get("excluded_paths") != excludes:
            return None, None, "review package scope does not match capsule"
        review_state = package_data.get("review_state", "dirty_tree")
        if review_state == "commit":
            declared_head = package_data.get("head_sha")
            if not isinstance(declared_head, str) or not declared_head:
                return None, None, "commit-bound review package head SHA is invalid"
            head_sha = run_git(repo, "rev-parse", "--verify", f"{declared_head}^{{commit}}").decode().strip()
            current_head = run_git(repo, "rev-parse", "HEAD").decode().strip()
            if head_sha != declared_head or current_head != head_sha:
                return None, None, "checkout does not match the reviewed head"
            if run_git(repo, "status", "--porcelain=v1", "--untracked-files=no"):
                return None, None, "commit-bound review requires a clean tracked and index state"
            complete_paths = commit_changed_paths(repo, base_sha, head_sha)
            if package_data.get("complete_changed_paths") != complete_paths:
                return None, None, "commit-bound review package complete paths are stale"
            if package_data.get("commit_diff_sha256") != commit_diff_digest(repo, base_sha, head_sha):
                return None, None, "commit-bound review package diff digest is stale"
        elif review_state == "dirty_tree":
            complete_paths = current_changed_paths(repo, package)
        else:
            return None, None, "review package state is invalid"
        expected_paths = [
            path
            for path in complete_paths
            if (not includes or any(path_matches(path, prefix) for prefix in includes))
            and not any(path_matches(path, prefix) for prefix in excludes)
        ]
        paths = package_data.get("changed_paths")
        if paths != expected_paths or not expected_paths:
            return None, None, "review package changed paths do not match declared review scope"
        evidence = package_data.get("evidence_logs")
        digests = package_data.get("evidence_sha256")
        if not isinstance(evidence, list) or not evidence or not isinstance(digests, dict) or set(digests) != set(evidence):
            return None, None, "review package evidence manifest is invalid"
        for item in evidence:
            relative, evidence_path = contained_file(repo, item, "review evidence")
            actual = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
            if digests.get(relative) != actual:
                return None, None, "review evidence digest is stale"
        if review_state == "dirty_tree" and package_data.get("dirty_tree_fingerprint") != fingerprint(repo, package):
            return None, None, "review package fingerprint is stale"
        for field in ("open_findings", "owner_gates"):
            if not isinstance(package_data.get(field), list) or not all(isinstance(item, str) for item in package_data[field]):
                return None, None, f"review package {field} is invalid"
        if not isinstance(package_data.get("acceptance_status"), str) or not package_data["acceptance_status"]:
            return None, None, "review package acceptance status is invalid"
        return package_data, base_sha, None
    except (OSError, TypeError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        return None, None, f"review package is invalid: {exc}"


def reject(reason: str) -> int:
    deny(reason)
    return 0


def request_context(capsule_override: bool) -> Tuple[dict, Path, Optional[dict]]:
    payload = json.load(sys.stdin)
    repo = git_root()
    tool = payload.get("tool_input", {})
    task = tool.get("task_name") if isinstance(tool, dict) else None
    try:
        data = capsule(active_capsule(repo, task))
    except (KeyError, OSError, ValueError, json.JSONDecodeError):
        if capsule_override:
            raise
        data = None
    return payload, repo, data


def capsule_contract(data: dict) -> Tuple[List[dict], dict, int]:
    assignments, review = data.get("assignments", []), data.get("review", {})
    if not isinstance(assignments, list) or not isinstance(review, dict):
        raise ValueError("capsule assignments or review contract is invalid")
    identifiers = [item.get("id") for item in assignments if isinstance(item, dict)]
    if len(identifiers) != len(assignments) or len(identifiers) != len(set(identifiers)):
        raise ValueError("capsule has duplicate or invalid assignment IDs")
    budget = data.get("parallel_budget")
    if not isinstance(budget, int) or not 0 <= budget <= 5:
        raise ValueError("parallel budget must be between 0 and 5")
    return assignments, review, budget


def record_review(state: Dict[str, object]) -> Optional[str]:
    launches = state.get("critical_review_launches", 0)
    if not isinstance(launches, int) or launches < 0:
        return "agent guard state is invalid; stop and inspect it"
    if launches >= 2:
        return "critical review is limited to initial review plus one recheck"
    state["critical_review_launches"] = launches + 1
    return None


def finish_dispatch(updated: Optional[dict], state_error: Optional[str]) -> int:
    if state_error:
        return reject(state_error)
    if updated is not None:
        allow_updated(updated)
    return 0


def dispatch_review(repo: Path, data: dict, review: dict, tool: dict) -> int:
    updated, route_error = validate_route(
        tool,
        str(review.get("agent", "")),
        str(review.get("model", "")),
        str(review.get("reasoning_effort", "")),
        "declared critical review",
    )
    if route_error:
        return reject(route_error)
    _, base_sha, package_error = validate_review_package(repo, data, review)
    if package_error or base_sha is None:
        return reject(package_error or "review package is invalid")
    key = safe_key(f"review:{data.get('id')}:{base_sha}")
    return finish_dispatch(updated, update_state(state_directory(repo), key, record_review))


def dependency_error(repo: Path, assignment: dict, assignments: List[dict]) -> Optional[str]:
    for dependency_id in assignment.get("depends_on", []):
        dependency = next((item for item in assignments if item.get("id") == dependency_id), None)
        output = dependency.get("output") if isinstance(dependency, dict) else None
        try:
            contained_file(repo, output, f"dependency report {dependency_id}")
        except ValueError:
            return f"dependency report is missing: {dependency_id}"
    return None


def has_overlapping_ownership(assignment: dict, assignments: List[dict]) -> bool:
    paths = [str(path) for path in assignment.get("write_paths", [])]
    return any(
        any(overlaps(path, other_path) for path in paths for other_path in other.get("write_paths", []))
        for other in assignments
        if other is not assignment
    )


def record_assignment(state: Dict[str, object], task: object, budget: int) -> Optional[str]:
    dispatched = state.setdefault("dispatched", [])
    if not isinstance(dispatched, list) or not all(isinstance(item, str) for item in dispatched):
        return "agent guard state is invalid; stop and inspect it"
    if task in dispatched:
        return "assignment was already dispatched"
    if len(dispatched) >= budget:
        return "parallel budget exceeded"
    dispatched.append(task)
    return None


def dispatch_assignment(
    repo: Path,
    data: dict,
    assignment: dict,
    assignments: List[dict],
    budget: int,
    tool: dict,
) -> int:
    if error := dependency_error(repo, assignment, assignments):
        return reject(error)
    declared_model = assignment.get("model", data.get("model_route", {}).get("owner"))
    updated, route_error = validate_route(
        tool,
        str(assignment.get("agent", "")),
        str(declared_model),
        str(assignment.get("reasoning_effort", "medium")),
        str(assignment.get("escalation_reason", "")),
    )
    if route_error:
        return reject(route_error)
    if has_overlapping_ownership(assignment, assignments):
        return reject("overlapping write ownership in capsule; collapse it under one assignment before dispatch")
    task = tool.get("task_name")
    key = safe_key(f"assignments:{data.get('id')}")
    update = lambda state: record_assignment(state, task, budget)
    return finish_dispatch(updated, update_state(state_directory(repo), key, update))


def main() -> int:
    capsule_override = bool(os.environ.get("STRATEGY_OS_CAPSULE_PATH"))
    try:
        payload, repo, data = request_context(capsule_override)
    except (KeyError, OSError, ValueError, json.JSONDecodeError) as exc:
        return reject(f"invalid capsule: {exc}")
    if error := trace_payload(repo, payload):
        return reject(error)
    if payload.get("tool_name") not in {"Agent", "spawn_agent", "collaborationspawn_agent"}:
        return 0
    tool = payload.get("tool_input", {})
    if not isinstance(tool, dict):
        return reject("agent tool input must be an object")
    if data is None:
        return 0
    try:
        assignments, review, budget = capsule_contract(data)
    except ValueError as exc:
        return reject(str(exc))

    task = tool.get("task_name")
    if task == review.get("assignment_id"):
        return dispatch_review(repo, data, review, tool)

    assignment = next((item for item in assignments if item.get("id") == task), None)
    if assignment is None:
        return reject("assignment is not declared in capsule") if capsule_override else 0
    return dispatch_assignment(repo, data, assignment, assignments, budget, tool)


if __name__ == "__main__":
    raise SystemExit(main())
