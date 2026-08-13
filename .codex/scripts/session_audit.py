#!/usr/bin/env python3
"""Aggregate session metadata without retaining prompts or messages."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path


TOKEN_KEYS = ("input_tokens", "cached_input_tokens", "cache_write_input_tokens", "output_tokens", "reasoning_output_tokens", "total_tokens")


def in_window(timestamp: object, since: str | None, until: str | None) -> bool:
    return isinstance(timestamp, str) and (not since or timestamp >= since) and (not until or timestamp <= until)


def parsed_time(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sessions-root", required=True)
    parser.add_argument("--since")
    parser.add_argument("--until")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    tokens = {key: 0 for key in TOKEN_KEYS}
    models: Counter[str] = Counter()
    forks: Counter[str] = Counter()
    compactions = launches = tool_output_bytes = 0
    fork_sizes: Counter[str] = Counter()
    timestamps: list[datetime] = []
    for path in sorted(Path(args.sessions_root).rglob("*.jsonl")):
        session_tokens: dict[str, int] | None = None
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not in_window(row.get("timestamp"), args.since, args.until):
                continue
            timestamp = parsed_time(row.get("timestamp"))
            if timestamp:
                timestamps.append(timestamp)
            payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
            if row.get("type") == "turn_context":
                model, effort = payload.get("model"), payload.get("effort")
                if isinstance(model, str) and isinstance(effort, str):
                    models[f"{model}/{effort}"] += 1
            elif row.get("type") == "compacted":
                compactions += 1
            elif row.get("type") == "event_msg" and payload.get("type") == "token_count":
                info = payload.get("info")
                usage = info.get("total_token_usage", {}) if isinstance(info, dict) else {}
                if isinstance(usage, dict):
                    session_tokens = {key: usage.get(key, 0) if isinstance(usage.get(key, 0), int) else 0 for key in TOKEN_KEYS}
            elif row.get("type") == "response_item" and payload.get("type") in {"custom_tool_call", "function_call"} and payload.get("name") == "spawn_agent":
                launches += 1
                try:
                    launch = json.loads(payload.get("input", payload.get("arguments", "{}")))
                except (TypeError, json.JSONDecodeError):
                    launch = {}
                fork = launch.get("fork_turns")
                if isinstance(fork, str):
                    forks[fork] += 1
                    if fork.isdecimal():
                        fork_sizes[fork] += int(fork)
            elif row.get("type") == "response_item" and str(payload.get("type", "")).endswith("_output"):
                output = payload.get("output", payload.get("content", ""))
                if isinstance(output, str):
                    tool_output_bytes += len(output.encode("utf-8"))
                elif output is not None:
                    tool_output_bytes += len(json.dumps(output, sort_keys=True).encode("utf-8"))
        if session_tokens:
            for key in TOKEN_KEYS:
                tokens[key] += session_tokens[key]
    # Codex reports cached input as a subset of input and reasoning as a subset of
    # output. Subtract the cached subset before applying its discount so neither
    # category is counted twice.
    cached_input = min(tokens["cached_input_tokens"], tokens["input_tokens"])
    uncached_input = max(tokens["input_tokens"] - cached_input, 0)
    weighted = uncached_input + (cached_input * 0.1) + tokens["output_tokens"]
    duration = (max(timestamps) - min(timestamps)).total_seconds() if timestamps else 0
    report = {
        "tokens": tokens,
        "uncached_input_tokens": uncached_input,
        "models": dict(sorted(models.items())),
        "compactions": compactions,
        "child_launches": launches,
        "fork_turns": dict(sorted(forks.items())),
        "fork_sizes": dict(sorted(fork_sizes.items())),
        "duration_seconds": duration,
        "tool_output_bytes": tool_output_bytes,
        "weighted_credits": weighted,
        "weighting": {"uncached_input": 1.0, "cached_input": 0.1, "output_including_reasoning": 1.0},
    }
    print(json.dumps(report, sort_keys=True) if args.json else "\n".join(f"{key}: {value}" for key, value in report.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
