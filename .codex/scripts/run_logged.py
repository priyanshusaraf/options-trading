#!/usr/bin/env python3
"""Run a command, retain complete output, and print a compact safe summary."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def safe_part(value: str) -> str:
    if not value or value in {".", ".."} or "/" in value or "\\" in value:
        raise ValueError("task, assignment, and label must use safe path components")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--assignment", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--cwd", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    try:
        parts = [safe_part(value) for value in (args.task, args.assignment, args.label)]
    except ValueError as exc:
        parser.error(str(exc))
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("a command is required after --")
    configured_root = os.environ.get("STRATEGY_OS_RUN_ROOT")
    if configured_root:
        root = Path(configured_root)
    else:
        discovered = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=args.cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        repo = Path(discovered.stdout.strip()).resolve() if discovered.returncode == 0 else Path(args.cwd).resolve()
        root = repo / ".agent" / "runs"
    log = root.joinpath(*parts).with_suffix(".log")
    log.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(command, cwd=args.cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    log.write_text(completed.stdout, encoding="utf-8")
    print(json.dumps({"exit_code": completed.returncode, "log": str(log)}))
    if completed.returncode:
        sys.stderr.write(completed.stdout[-4000:])
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
