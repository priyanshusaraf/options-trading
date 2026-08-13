#!/usr/bin/env python3
"""Measure model-visible startup input without retaining prompt contents."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


DEFAULT_CODEX = "/Applications/ChatGPT.app/Contents/Resources/codex"
RETIRED_MARKERS = ("CLAUDE.md", ".claude/rules", ".claude/skills", ".claude/agents")
DISABLED_SURFACE_MARKERS = (
    "engineering-skills:",
    "superpowers:",
    "browser:control",
    "chrome:control",
    "computer-use:computer-use",
    "documents:documents",
    "pdf:pdf",
    "presentations:Presentations",
    "sites:sites-",
)
REPOSITORY_SKILLS = (
    "architecting-strategy-os-phases",
    "executing-strategy-os-slices",
    "reviewing-strategy-os-critical-changes",
    "running-strategy-os-safely",
)


def visible_text(rows: List[Dict[str, Any]]) -> str:
    values: List[str] = []
    for row in rows:
        content = row.get("content", "")
        values.append(content if isinstance(content, str) else json.dumps(content, ensure_ascii=False))
    return "\n".join(values)


def probes(root: Path) -> List[Tuple[str, Path, Tuple[str, ...]]]:
    return [
        (".", root, ("Strategy OS agent contract",)),
        (
            "paper-trader",
            root / "paper-trader",
            ("Strategy OS agent contract", "Strategy OS product rules"),
        ),
        (
            "paper-trader/backend",
            root / "paper-trader" / "backend",
            ("Strategy OS agent contract", "Strategy OS product rules", "Backend execution rules"),
        ),
        (
            "paper-trader/backend/app/ir",
            root / "paper-trader" / "backend" / "app" / "ir",
            ("Strategy OS agent contract", "Strategy OS product rules", "Backend execution rules"),
        ),
        (
            "paper-trader/backend/app/engine",
            root / "paper-trader" / "backend" / "app" / "engine",
            ("Strategy OS agent contract", "Strategy OS product rules", "Backend execution rules"),
        ),
    ]


def measure_root(
    root: Path,
    codex: str,
    *,
    verify_contract: bool,
    max_bytes: int,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    failures: List[str] = []
    results: List[Dict[str, Any]] = []
    for label, cwd, expected in probes(root):
        if not cwd.is_dir():
            failures.append(f"probe directory is missing: {root}:{label}")
            continue
        completed = subprocess.run(
            [codex, "debug", "prompt-input", "startup audit"],
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if completed.returncode:
            failures.append(f"prompt-input failed in {root}:{label}: exit {completed.returncode}")
            continue
        try:
            rows = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            failures.append(f"prompt-input returned invalid JSON in {root}:{label}: {exc.msg}")
            continue
        if not isinstance(rows, list) or not all(isinstance(item, dict) for item in rows):
            failures.append(f"prompt-input returned an invalid message list in {root}:{label}")
            continue
        text = visible_text(rows)
        size = len(completed.stdout.encode("utf-8"))
        missing = [marker for marker in expected if marker not in text] if verify_contract else []
        missing_skills = [marker for marker in REPOSITORY_SKILLS if marker not in text] if verify_contract else []
        retired = [marker for marker in RETIRED_MARKERS if marker in text] if verify_contract else []
        disabled = [marker for marker in DISABLED_SURFACE_MARKERS if marker in text] if verify_contract else []
        if verify_contract and size > max_bytes:
            failures.append(f"startup input in {label} is {size} bytes (limit {max_bytes})")
        if missing:
            failures.append(f"instruction chain missing in {label}: {missing}")
        if missing_skills:
            failures.append(f"repository skills missing in {label}: {missing_skills}")
        if retired:
            failures.append(f"retired Claude metadata visible in {label}: {retired}")
        if disabled:
            failures.append(f"disabled plugin metadata visible in {label}: {disabled}")
        result: Dict[str, Any] = {
            "cwd": label,
            "serialized_bytes": size,
            "messages": len(rows),
            "stderr_present": bool(completed.stderr.strip()),
        }
        if verify_contract:
            result.update(
                {
                    "missing_instruction_markers": missing,
                    "missing_repository_skills": missing_skills,
                    "retired_markers": retired,
                    "disabled_surface_markers": disabled,
                }
            )
        results.append(result)
    return results, failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--baseline-root")
    parser.add_argument("--codex")
    parser.add_argument("--max-bytes", type=int, default=22_000)
    args = parser.parse_args()
    root = Path(args.root).resolve()
    baseline_root: Optional[Path] = Path(args.baseline_root).resolve() if args.baseline_root else None
    codex = args.codex or (DEFAULT_CODEX if Path(DEFAULT_CODEX).is_file() else shutil.which("codex"))
    if not codex:
        parser.error("Codex CLI not found; pass --codex")
    version = subprocess.run(
        [codex, "--version"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    ).stdout.strip()

    results, failures = measure_root(root, codex, verify_contract=True, max_bytes=args.max_bytes)
    max_current = max((item["serialized_bytes"] for item in results), default=0)
    baseline_report: Optional[Dict[str, Any]] = None
    reduction_percent: Optional[float] = None
    if baseline_root is not None:
        baseline_results, baseline_failures = measure_root(
            baseline_root,
            codex,
            verify_contract=False,
            max_bytes=args.max_bytes,
        )
        failures.extend(baseline_failures)
        max_baseline = max((item["serialized_bytes"] for item in baseline_results), default=0)
        baseline_report = {"root": str(baseline_root), "max_bytes": max_baseline, "probes": baseline_results}
        if max_baseline:
            reduction_percent = round(((max_baseline - max_current) / max_baseline) * 100, 2)
            if max_current >= max_baseline:
                failures.append("startup input did not improve over the same-build baseline")
        else:
            failures.append("same-build baseline produced no measurements")

    report = {
        "status": "pass" if not failures else "fail",
        "codex_binary": str(codex),
        "codex_version": version,
        "max_bytes": max_current,
        "limit_bytes": args.max_bytes,
        "probes": results,
        "baseline": baseline_report,
        "reduction_percent": reduction_percent,
        "failures": failures,
    }
    print(json.dumps(report, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
