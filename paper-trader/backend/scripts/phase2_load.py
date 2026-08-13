#!/usr/bin/env python3
"""Run one bounded Phase 2 workload vector and retain canonical JSON evidence."""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.operations.phase2_load import PRESETS, WorkloadVector, run_workload


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preset", choices=sorted(PRESETS), default="ci")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260813)
    for name in ("tenants", "accounts", "api_replicas", "execution_accounts",
                 "job_workers", "request_concurrency", "request_operations", "jobs",
                 "websocket_channels", "events_per_channel", "payload_bytes",
                 "pool_size", "pool_overflow", "pool_timeout_ms", "outbox_batch",
                 "outbox_retention", "queue_bound", "warmup_operations"):
        parser.add_argument("--" + name.replace("_", "-"), dest=name, type=int)
    parser.add_argument("--duration-seconds", type=float)
    parser.add_argument("--environment", default="local")
    parser.add_argument("--database-profile", default="in-process-contract")
    return parser


def main() -> int:
    args = _parser().parse_args()
    overrides = {key: value for key, value in vars(args).items()
                 if key in WorkloadVector.__dataclass_fields__ and value is not None}
    vector = WorkloadVector.from_preset(args.preset, **overrides)
    report = run_workload(
        vector, seed=args.seed, build=os.environ.get("GIT_SHA", "unknown"),
        environment=args.environment, database_profile=args.database_profile)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=args.output.name + ".",
                                              dir=args.output.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(report, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
        os.replace(temporary, args.output)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print(json.dumps({"output": str(args.output),
                      "production_capacity_claim_ready": report["production_capacity_claim_ready"],
                      "outcomes": report["outcomes"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
