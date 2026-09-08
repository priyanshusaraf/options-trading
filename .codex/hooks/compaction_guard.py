#!/usr/bin/env python3
"""Keep approved work moving across automatic compaction."""
from __future__ import annotations

import json
import sys


ADVISORY = (
    "Continue the approved work after compaction. Preserve the durable goal, "
    "WORKING-PLAN, evidence, completed results, and current actual state."
)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    if not isinstance(payload, dict) or payload.get("trigger") != "auto":
        return 0
    print(json.dumps({"continue": True, "systemMessage": ADVISORY}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
