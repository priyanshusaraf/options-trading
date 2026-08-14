#!/usr/bin/env python3
"""Validate the repository's Codex agent architecture with no third-party code."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.9/3.10 can still run non-TOML checks.
    tomllib = None


MAX_CHAIN_BYTES = 12_288
STATIC_SECRET = re.compile(
    r"(?i)(authorization\s*[:=]\s*[\"']?(?:bearer\s+)?[a-z0-9._-]{16,}"
    r"|(?:api[_-]?key|token|secret)\s*[:=]\s*[\"']?[a-z0-9._-]{16,})"
)
MARKDOWN_REFERENCE = re.compile(r"\]\((references/[^)#\s]+)")
REQUIRED_CAPSULE_FIELDS = {
    "id",
    "phase",
    "status",
    "goal",
    "risk_tags",
    "required_docs",
    "allowed_paths",
    "nonclaims",
    "owner_gates",
    "stop_conditions",
    "model_route",
    "parallel_budget",
    "assignments",
    "acceptance",
    "test_plan",
    "review",
}
PROGRAMME_STATUSES = {
    "blocked",
    "ready",
    "active",
    "correction",
    "review",
    "accepted",
    "paused_owner_gate",
}


def relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def frontmatter_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError("missing frontmatter")
    parts = text.split("---", 2)
    if len(parts) != 3 or not parts[1].strip():
        raise ValueError("empty or unterminated frontmatter")
    return parts[1].strip()


def json_frontmatter(path: Path) -> Dict[str, Any]:
    value = json.loads(frontmatter_text(path))
    if not isinstance(value, dict):
        raise ValueError("frontmatter is not an object")
    return value


def instruction_chains(root: Path) -> Dict[str, int]:
    root_agents = root / "AGENTS.md"
    paper_agents = root / "paper-trader" / "AGENTS.md"
    chains = {
        ".": [root_agents],
        ".agents/evals": [root_agents, root / ".agents" / "evals" / "AGENTS.md"],
        "paper-trader": [root_agents, paper_agents],
        "paper-trader/backend": [
            root_agents,
            paper_agents,
            root / "paper-trader" / "backend" / "AGENTS.md",
        ],
        "paper-trader/frontend": [
            root_agents,
            paper_agents,
            root / "paper-trader" / "frontend" / "AGENTS.md",
        ],
    }
    return {
        name: sum(path.stat().st_size for path in paths if path.is_file())
        for name, paths in chains.items()
    }


def retired_files(root: Path) -> List[Path]:
    candidates = [root / "CLAUDE.md", root / "paper-trader" / "CLAUDE.md"]
    claude = root / ".claude"
    if claude.exists():
        candidates.extend(path for path in claude.rglob("*") if path.is_file())
    return sorted({path.resolve() for path in candidates if path.is_file()})


def validate_review_package(path: Path, failures: List[str], root: Path) -> None:
    try:
        package = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        failures.append(f"invalid review package: {exc}")
        return
    required = {
        "task_id",
        "base_sha",
        "dirty_tree_fingerprint",
        "changed_paths",
        "acceptance_status",
        "evidence_logs",
        "evidence_sha256",
        "scope_prefixes",
        "excluded_paths",
        "open_findings",
        "owner_gates",
    }
    if not isinstance(package, dict) or required - set(package):
        failures.append("review package lacks required fields")
        return
    evidence_logs = package.get("evidence_logs", [])
    evidence_sha256 = package.get("evidence_sha256", {})
    if (
        not isinstance(evidence_logs, list)
        or not all(isinstance(item, str) for item in evidence_logs)
        or not isinstance(evidence_sha256, dict)
        or set(evidence_logs) != set(evidence_sha256)
    ):
        failures.append("review package evidence manifest is invalid")
        return
    for item in evidence_logs:
        resolved = (root / item).resolve() if isinstance(item, str) else root
        if not isinstance(item, str) or root not in resolved.parents or not resolved.is_file():
            failures.append(f"review package evidence does not exist: {item}")
        elif evidence_sha256.get(item) != hashlib.sha256(resolved.read_bytes()).hexdigest():
            failures.append(f"review package evidence digest is stale: {item}")


def repository_file(root: Path, value: object) -> Optional[Path]:
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        return None
    resolved = (root / value).resolve()
    if root not in resolved.parents or not resolved.is_file():
        return None
    return resolved


def markdown_headings(path: Path) -> List[tuple[int, str]]:
    result = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^(#{1,4})\s+(.+?)\s*$", line)
        if match:
            result.append((len(match.group(1)), match.group(2)))
    return result


def validate_source_map(path: Path, failures: List[str], root: Path) -> Optional[Dict[str, Any]]:
    try:
        source_map = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        failures.append(f"invalid source map: {exc}")
        return None
    if not isinstance(source_map, dict) or source_map.get("schema_version") != 1:
        failures.append("source map schema is invalid")
        return None
    sources = source_map.get("sources")
    phase_views = source_map.get("phase_views")
    if not isinstance(sources, list) or not isinstance(phase_views, dict):
        failures.append("source map lacks sources or phase_views")
        return source_map
    indexed: Dict[str, Dict[str, Any]] = {}
    section_consumers: Dict[tuple[str, str], set[str]] = {}
    for source in sources:
        if not isinstance(source, dict) or not isinstance(source.get("id"), str):
            failures.append("source map contains an invalid source record")
            continue
        source_id = source["id"]
        if source_id in indexed:
            failures.append(f"source map contains duplicate source ID: {source_id}")
            continue
        indexed[source_id] = source
        source_path = repository_file(root, source.get("path"))
        if source_path is None:
            failures.append(f"owner source does not exist: {source.get('path')}")
            continue
        actual_digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
        if source.get("sha256") != actual_digest:
            failures.append(f"owner source hash mismatch: {source_id}")
        sections = source.get("sections")
        if not isinstance(sections, list):
            failures.append(f"source map sections are invalid: {source_id}")
            continue
        mapped = []
        for section in sections:
            if not isinstance(section, dict):
                failures.append(f"source map section is invalid: {source_id}")
                continue
            level, heading, consumers = section.get("level"), section.get("heading"), section.get("consumers")
            if (
                not isinstance(level, int)
                or not isinstance(heading, str)
                or not heading
                or not isinstance(consumers, list)
                or not consumers
                or not all(isinstance(item, str) and item for item in consumers)
            ):
                failures.append(f"source map section is invalid: {source_id}")
                continue
            mapped.append((level, heading))
            section_consumers[(source_id, heading)] = set(consumers)
        if mapped != markdown_headings(source_path):
            failures.append(f"owner source heading coverage mismatch: {source_id}")
    view_entries: Dict[tuple[str, str], set[str]] = {}
    for phase, entries in phase_views.items():
        if not isinstance(phase, str) or not isinstance(entries, list) or not entries:
            failures.append(f"source map phase view is invalid: {phase}")
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                failures.append(f"source map phase entry is invalid: {phase}")
                continue
            key = (entry.get("source_id"), entry.get("heading"))
            if key not in section_consumers or phase not in section_consumers[key]:
                failures.append(f"source map phase entry is not routed: {phase} -> {key}")
                continue
            view_entries.setdefault(key, set()).add(phase)
    for key, consumers in section_consumers.items():
        if view_entries.get(key, set()) != consumers:
            failures.append(f"source map phase coverage mismatch: {key[0]} -> {key[1]}")
    return source_map


def validate_programme(path: Path, failures: List[str], root: Path) -> Optional[Dict[str, Any]]:
    try:
        programme = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        failures.append(f"invalid programme: {exc}")
        return None
    if not isinstance(programme, dict) or programme.get("schema_version") != 1:
        failures.append("programme schema is invalid")
        return None
    stages = programme.get("stages")
    if not isinstance(stages, list) or not stages:
        failures.append("programme has no stages")
        return programme
    orders = [item.get("order") for item in stages if isinstance(item, dict)]
    if len(orders) != len(stages) or orders != list(range(1, len(stages) + 1)):
        failures.append("programme stage order is invalid")
    ids = [item.get("id") for item in stages if isinstance(item, dict)]
    if len(ids) != len(stages) or len(set(ids)) != len(ids) or not all(isinstance(item, str) for item in ids):
        failures.append("programme stage IDs are invalid")
        return programme
    indexed = {item["id"]: item for item in stages}
    current_id = programme.get("current_stage_id")
    if current_id not in indexed:
        failures.append("programme current stage does not exist")
    seen: set[str] = set()
    for stage in stages:
        stage_id = stage["id"]
        status = stage.get("status")
        dependencies = stage.get("depends_on")
        if status not in PROGRAMME_STATUSES:
            failures.append(f"programme stage status is invalid: {stage_id}")
        if not isinstance(dependencies, list) or not all(isinstance(item, str) for item in dependencies):
            failures.append(f"programme dependencies are invalid: {stage_id}")
        elif not set(dependencies) <= seen:
            failures.append(f"programme dependency order is invalid: {stage_id}")
        seen.add(stage_id)
        capsule_value = stage.get("capsule")
        if capsule_value is None and stage.get("dynamic") is True:
            continue
        capsule_path = repository_file(root, capsule_value)
        if capsule_path is None:
            failures.append(f"programme capsule does not exist: {stage_id} -> {capsule_value}")
            continue
        try:
            capsule = json_frontmatter(capsule_path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if capsule.get("id") != stage_id:
            failures.append(f"programme capsule ID mismatch: {stage_id}")
        goal_contract = capsule.get("goal_contract")
        if (
            not isinstance(goal_contract, dict)
            or goal_contract.get("create_before_work") is not True
            or not isinstance(goal_contract.get("stopping_condition"), str)
            or not goal_contract.get("stopping_condition")
        ):
            failures.append(f"programme capsule lacks goal contract: {stage_id}")
    for phase in range(4, 11):
        architecture = indexed.get(f"phase{phase}-architecture")
        review = indexed.get(f"phase{phase}-review")
        implementation = f"phase{phase}-implementation"
        if not architecture or (architecture.get("model"), architecture.get("reasoning_effort")) != ("gpt-5.6-sol", "medium"):
            failures.append(f"programme phase architecture route is invalid: phase{phase}")
        if (
            not review
            or review.get("kind") != "phase_review"
            or (review.get("model"), review.get("reasoning_effort")) != ("gpt-5.6-sol", "high")
            or implementation not in review.get("depends_on", [])
        ):
            failures.append(f"programme phase review gate is invalid: phase{phase}")
    return programme


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    args = parser.parse_args()
    root = Path(args.root).resolve()
    failures: List[str] = []

    required_artifacts = [
        "AGENTS.md",
        "paper-trader/AGENTS.md",
        "paper-trader/backend/AGENTS.md",
        "paper-trader/frontend/AGENTS.md",
        ".codex/config.toml",
        ".codex/hooks.json",
        ".codex/hooks/agent_guard.py",
        ".codex/hooks/compaction_guard.py",
        ".codex/scripts/run_logged.py",
        ".codex/scripts/make_review_package.py",
        ".codex/scripts/session_audit.py",
        ".codex/scripts/prompt_input_audit.py",
        ".codex/scripts/programme_dispatcher.py",
        "paper-trader/docs/agent/CURRENT.md",
        "paper-trader/docs/agent/ROUTER.md",
        "paper-trader/docs/agent/programme/SOURCE_MAP.json",
        "paper-trader/docs/agent/programme/PROGRAMME.json",
        "paper-trader/docs/agent/programme/GOAL_TEMPLATES.md",
    ]
    for item in required_artifacts:
        if not (root / item).is_file():
            failures.append(f"missing required artifact: {item}")

    scan_roots = [
        root / ".agents",
        root / ".codex",
        root / "paper-trader" / "docs" / "agent",
        root / "paper-trader" / "docs" / "program" / "owner-steers",
    ]
    files = sorted(
        {
            path.resolve()
            for base in scan_roots
            if base.exists()
            for path in base.rglob("*")
            if path.is_file() and "__pycache__" not in path.parts
        }
        | {
            (root / item).resolve()
            for item in required_artifacts
            if (root / item).is_file()
        }
    )
    retired = retired_files(root)
    files_for_secret_scan = sorted(set(files + retired))

    toml_files = [path for path in files if path.suffix == ".toml"]
    if tomllib is None and toml_files:
        failures.append("TOML parser unavailable; run with Python 3.11 or newer")
    for path in toml_files:
        if tomllib is None:
            break
        try:
            tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
            failures.append(f"invalid TOML: {relative(path, root)} ({exc})")

    for path in (item for item in files if item.suffix == ".json"):
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            failures.append(f"invalid JSON: {relative(path, root)} ({exc})")

    for path in files_for_secret_scan:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if STATIC_SECRET.search(text):
            failures.append(f"likely static credential: {relative(path, root)}")

    source_map_path = root / "paper-trader" / "docs" / "agent" / "programme" / "SOURCE_MAP.json"
    if source_map_path.is_file():
        validate_source_map(source_map_path, failures, root)
    programme_path = root / "paper-trader" / "docs" / "agent" / "programme" / "PROGRAMME.json"
    programme = validate_programme(programme_path, failures, root) if programme_path.is_file() else None

    skills = root / ".agents" / "skills"
    skill_files = sorted(skills.glob("*/SKILL.md")) if skills.exists() else []
    if not skill_files:
        failures.append("no repository skills found")
    for skill in skill_files:
        try:
            header = frontmatter_text(skill)
        except ValueError as exc:
            failures.append(f"invalid skill frontmatter: {relative(skill, root)} ({exc})")
            continue
        if not re.search(r"(?m)^name:\s*\S+", header) or not re.search(
            r"(?m)^description:\s*.+", header
        ):
            failures.append(f"skill lacks name or description: {relative(skill, root)}")
        text = skill.read_text(encoding="utf-8")
        for reference in MARKDOWN_REFERENCE.findall(text):
            if not (skill.parent / reference).is_file():
                failures.append(
                    f"missing skill reference: {relative(skill, root)} -> {reference}"
                )

    current_path = root / "paper-trader" / "docs" / "agent" / "CURRENT.md"
    if current_path.is_file():
        try:
            current = json_frontmatter(current_path)
            active = current.get("active_capsule")
            active_path = (root / active).resolve() if isinstance(active, str) else None
            if active_path is None or root not in active_path.parents or not active_path.is_file():
                failures.append("active capsule does not exist")
            if isinstance(programme, dict):
                if current.get("active_stage") != programme.get("current_stage_id"):
                    failures.append("CURRENT.md active stage differs from programme")
                indexed = {
                    item.get("id"): item
                    for item in programme.get("stages", [])
                    if isinstance(item, dict)
                }
                stage = indexed.get(programme.get("current_stage_id"))
                if isinstance(stage, dict) and stage.get("capsule") != active:
                    failures.append("CURRENT.md active capsule differs from programme")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            failures.append(f"invalid CURRENT.md frontmatter: {exc}")

    capsule_root = root / "paper-trader" / "docs" / "agent" / "tasks"
    capsule_files = sorted(capsule_root.glob("*.md")) if capsule_root.exists() else []
    if not capsule_files:
        failures.append("no tracked task capsule found")
    for capsule_path in capsule_files:
        try:
            capsule = json_frontmatter(capsule_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            failures.append(f"invalid capsule: {relative(capsule_path, root)} ({exc})")
            continue
        missing = REQUIRED_CAPSULE_FIELDS - set(capsule)
        if missing:
            failures.append(
                f"capsule missing fields: {relative(capsule_path, root)} ({sorted(missing)})"
            )
        budget = capsule.get("parallel_budget")
        assignments = capsule.get("assignments")
        if not isinstance(budget, int) or not 0 <= budget <= 5:
            failures.append(f"invalid capsule parallel budget: {relative(capsule_path, root)}")
        if not isinstance(assignments, list) or (isinstance(budget, int) and len(assignments) > budget):
            failures.append(f"invalid capsule assignments: {relative(capsule_path, root)}")
        for document in capsule.get("required_docs", []):
            doc_path = document.get("path") if isinstance(document, dict) else None
            if not isinstance(doc_path, str) or not (root / doc_path).is_file():
                failures.append(
                    f"capsule required document does not exist: {relative(capsule_path, root)} -> {doc_path}"
                )
        identifiers = [item.get("id") for item in assignments if isinstance(item, dict)] if isinstance(assignments, list) else []
        if len(identifiers) != len(set(identifiers)) or any(
            not isinstance(identifier, str) or not re.fullmatch(r"[a-z0-9_]+", identifier)
            for identifier in identifiers
        ):
            failures.append(f"invalid capsule assignment IDs: {relative(capsule_path, root)}")
        review = capsule.get("review")
        if not isinstance(review, dict) or not isinstance(review.get("base_sha"), str):
            failures.append(f"capsule review lacks base_sha: {relative(capsule_path, root)}")
        elif not re.fullmatch(r"[a-z0-9_]+", str(review.get("assignment_id", ""))):
            failures.append(f"invalid review assignment ID: {relative(capsule_path, root)}")
        for field in ("review_paths", "exclude_paths"):
            values = review.get(field) if isinstance(review, dict) else None
            if not isinstance(values, list) or not all(
                isinstance(item, str) and item and not Path(item).is_absolute() and ".." not in Path(item).parts
                for item in values
            ):
                failures.append(f"invalid review {field}: {relative(capsule_path, root)}")

    chains = instruction_chains(root)
    max_chain = max(chains.values(), default=0)
    if max_chain > MAX_CHAIN_BYTES:
        failures.append(f"instruction chain exceeds {MAX_CHAIN_BYTES} bytes")

    if retired:
        failures.append("retired Claude harness still exists")

    package = root / ".agent" / "review-package.json"
    if package.exists():
        validate_review_package(package, failures, root)

    report = {
        "status": "pass" if not failures else "fail",
        "max_agents_chain_bytes": max_chain,
        "instruction_chain_bytes": chains,
        "checked_files": len(files),
        "toml_parsed": bool(tomllib is not None and toml_files),
        "retired_claude_harness": [relative(path, root) for path in retired],
        "failures": failures,
    }
    print(json.dumps(report, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
