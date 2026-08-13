#!/usr/bin/env python3
"""Allow one automatic compaction per safely keyed session."""
from __future__ import annotations

import hashlib
import fcntl
import json
import os
import sys
import subprocess
from pathlib import Path


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    if payload.get("trigger") != "auto":
        return 0
    configured = os.environ.get("STRATEGY_OS_AGENT_STATE_DIR")
    if configured:
        state_dir = Path(configured).resolve()
    else:
        root = subprocess.run(["git", "rev-parse", "--show-toplevel"], text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False)
        repo = Path(root.stdout.strip()).resolve() if root.returncode == 0 else Path.cwd().resolve()
        common = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=repo, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False)
        common_path = Path(common.stdout.strip()) if common.returncode == 0 else repo / ".git"
        if not common_path.is_absolute():
            common_path = repo / common_path
        state_dir = common_path.resolve() / "codex-agent-state"
    state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    key = hashlib.sha256(str(payload.get("session_id", "")).encode()).hexdigest()
    path = state_dir / ("compaction-" + key + ".json")
    lock_path = state_dir / ("compaction-" + key + ".lock")
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        count = 0
        if path.exists():
            try:
                state = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(state, dict) or not isinstance(state.get("auto_compactions", 0), int):
                    raise ValueError("invalid state")
                count = state.get("auto_compactions", 0)
            except (OSError, ValueError, json.JSONDecodeError):
                print(json.dumps({"continue": False, "stopReason": "Compaction state is invalid; start a fresh task and inspect the state file."}))
                return 0
        if count:
            print(json.dumps({"continue": False, "stopReason": "Start a fresh task after the first automatic compaction."}))
            return 0
        temporary = state_dir / (".compaction-" + key + f".{os.getpid()}.tmp")
        temporary.write_text(json.dumps({"auto_compactions": 1}), encoding="utf-8")
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
        print(json.dumps({"continue": True, "systemMessage": "First automatic compaction recorded; preserve the capsule and evidence."}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
