#!/usr/bin/env python3
"""Create a deterministic review package from Git's complete dirty state."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Iterable


def git(repo: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=repo)


def normalized_relative(value: str, *, label: str) -> str:
    path = Path(value)
    if not value or path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"{label} must be a repository-relative path without traversal: {value}")
    return path.as_posix().strip("/")


def contained_file(repo: Path, value: str, *, label: str) -> tuple[str, Path]:
    relative = normalized_relative(value, label=label)
    resolved = (repo / relative).resolve()
    if repo not in resolved.parents or not resolved.is_file():
        raise ValueError(f"{label} must name a file inside the repository: {value}")
    return relative, resolved


def path_matches(path: str, prefix: str) -> bool:
    return path == prefix or path.startswith(prefix + "/")


def changed_paths(repo: Path, excluded_output: str) -> list[str]:
    path_sets = (
        git(repo, "diff", "--name-only", "-z"),
        git(repo, "diff", "--cached", "--name-only", "-z"),
        git(repo, "ls-files", "--others", "--exclude-standard", "-z"),
    )
    return sorted(
        {
            entry.decode("utf-8", "replace")
            for paths in path_sets
            for entry in paths.split(b"\0")
            if entry
            and entry.decode("utf-8", "replace") != excluded_output
            and not entry.startswith(b".agent/")
        }
    )


def commit_changed_paths(repo: Path, base_sha: str, head_sha: str) -> list[str]:
    output = git(
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


def commit_diff(repo: Path, base_sha: str, head_sha: str) -> bytes:
    return git(repo, "diff", "--binary", "--no-ext-diff", f"{base_sha}..{head_sha}")


def tracked_tree_is_clean(repo: Path) -> bool:
    return not git(repo, "status", "--porcelain=v1", "--untracked-files=no")


def scoped_paths(paths: Iterable[str], includes: list[str], excludes: list[str]) -> list[str]:
    return [
        path
        for path in paths
        if (not includes or any(path_matches(path, prefix) for prefix in includes))
        and not any(path_matches(path, prefix) for prefix in excludes)
    ]


def fingerprint(repo: Path, excluded: Path) -> str:
    relative = excluded.resolve().relative_to(repo).as_posix().encode()
    digest = hashlib.sha256()
    for label, args in ((b"worktree", ("diff", "--binary", "--no-ext-diff")), (b"index", ("diff", "--cached", "--binary", "--no-ext-diff"))):
        digest.update(label + b"\0" + git(repo, *args) + b"\0")
    for entry in sorted(item for item in git(repo, "ls-files", "--others", "--exclude-standard", "-z").split(b"\0") if item and item != relative):
        digest.update(b"untracked\0" + entry + b"\0" + (repo / entry.decode()).read_bytes() + b"\0")
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head")
    parser.add_argument("--acceptance-status", required=True)
    parser.add_argument("--evidence", action="append", default=[])
    parser.add_argument("--owner-gate", action="append", default=[])
    parser.add_argument("--open-finding", action="append", default=[])
    parser.add_argument("--include", action="append", default=[])
    parser.add_argument("--exclude", action="append", default=[])
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    output_arg = Path(args.output)
    output = output_arg.resolve()
    try:
        output_relative = output.relative_to(repo).as_posix()
    except ValueError:
        parser.error("output must be inside the repository")
    try:
        includes = sorted({normalized_relative(item, label="include") for item in args.include})
        excludes = sorted({normalized_relative(item, label="exclude") for item in args.exclude})
        evidence_items = [contained_file(repo, item, label="evidence") for item in args.evidence]
    except ValueError as exc:
        parser.error(str(exc))
    try:
        base_sha = git(repo, "rev-parse", "--verify", f"{args.base}^{{commit}}").decode().strip()
    except subprocess.CalledProcessError:
        parser.error(f"base is not a commit: {args.base}")
    head_sha = None
    if args.head is not None:
        try:
            head_sha = git(repo, "rev-parse", "--verify", f"{args.head}^{{commit}}").decode().strip()
        except subprocess.CalledProcessError:
            parser.error(f"head is not a commit: {args.head}")
        if not tracked_tree_is_clean(repo):
            parser.error("--head requires a clean tracked/index state; repository is dirty")

    complete = (
        commit_changed_paths(repo, base_sha, head_sha)
        if head_sha is not None
        else changed_paths(repo, output_relative)
    )
    changed = scoped_paths(complete, includes, excludes)
    evidence_logs = [relative for relative, _ in evidence_items]
    evidence_sha256 = {
        relative: hashlib.sha256(path.read_bytes()).hexdigest()
        for relative, path in evidence_items
    }
    package = {
        "task_id": args.task_id,
        "base_sha": base_sha,
        "dirty_tree_fingerprint": fingerprint(repo, output),
        "scope_prefixes": includes,
        "excluded_paths": excludes,
        "changed_paths": changed,
        "acceptance_status": args.acceptance_status,
        "evidence_logs": evidence_logs,
        "evidence_sha256": evidence_sha256,
        "open_findings": args.open_finding,
        "owner_gates": args.owner_gate,
        "review_state": "commit" if head_sha is not None else "dirty_tree",
        "complete_changed_paths": complete,
    }
    if head_sha is not None:
        package["head_sha"] = head_sha
        package["commit_diff_sha256"] = hashlib.sha256(
            commit_diff(repo, base_sha, head_sha)
        ).hexdigest()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(package, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "changed_paths": len(changed)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
