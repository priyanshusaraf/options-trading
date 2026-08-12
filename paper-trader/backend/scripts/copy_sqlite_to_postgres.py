#!/usr/bin/env python3
"""Offline SQLite-to-PostgreSQL copy. URLs and paths are always explicit."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from app.db.copy_contract import (CopyRefusal, canonical_report, configured_planes,
                                  copy_planes)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    for plane in ("execution", "research", "ledger"):
        result.add_argument(f"--{plane}-source", required=True, type=Path)
        result.add_argument(f"--{plane}-destination", required=True)
    result.add_argument("--report", required=True, type=Path)
    result.add_argument("--batch-size", type=int, default=500)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.report.exists():
        print("refusing to overwrite an existing report", file=sys.stderr)
        return 2
    try:
        planes = configured_planes(
            execution_source=args.execution_source,
            execution_destination=args.execution_destination,
            research_source=args.research_source,
            research_destination=args.research_destination,
            ledger_source=args.ledger_source,
            ledger_destination=args.ledger_destination,
        )
        report = copy_planes(planes, batch_size=args.batch_size)
        temporary = args.report.with_name(f".{args.report.name}.{os.getpid()}.tmp")
        try:
            temporary.write_text(canonical_report(report), encoding="utf-8")
            with temporary.open("rb") as handle:
                os.fsync(handle.fileno())
            os.replace(temporary, args.report)
        finally:
            temporary.unlink(missing_ok=True)
    except CopyRefusal as exc:
        print(f"copy refused: {exc}", file=sys.stderr)
        return 2
    except Exception:
        # Database-driver errors often embed credential-bearing URLs. Preserve the
        # nonzero refusal contract without echoing those details to logs.
        print("copy refused: unexpected database or filesystem failure", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
