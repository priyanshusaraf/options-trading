#!/usr/bin/env python3
"""Compare two supplied receipt documents; never opens a database or broker."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.execution.capital_shadow import compare_documents


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("fixture", type=Path)
    args = parser.parse_args()
    document = json.loads(args.fixture.read_text(encoding="utf-8"))
    if set(document) != {"current", "admission"}:
        raise SystemExit("fixture must contain exactly current and admission")
    print(json.dumps(compare_documents(
        document["current"], document["admission"]), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
