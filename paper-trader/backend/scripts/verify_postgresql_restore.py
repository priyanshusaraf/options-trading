#!/usr/bin/env python3
"""Verify three cleanly restored PostgreSQL targets without mutating them."""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.restore_contract import configured_restore_planes, verify_restore


def _write_atomic(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execution-url-env", default="PT_DATABASE_URL")
    parser.add_argument("--research-url-env", default="PT_RESEARCH_DATABASE_URL")
    parser.add_argument("--ledger-url-env", default="PT_LEDGER_DATABASE_URL")
    parser.add_argument("--signing-key-env", default="PT_RESTORE_SIGNING_KEY")
    parser.add_argument("--require-signed", action="store_true")
    args = parser.parse_args()
    urls = [os.environ.get(name, "") for name in (
        args.execution_url_env, args.research_url_env, args.ledger_url_env)]
    if not all(urls):
        parser.error("all three target URL environment variables are required")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    raw_key = os.environ.get(args.signing_key_env)
    report = verify_restore(
        configured_restore_planes(execution_url=urls[0], research_url=urls[1], ledger_url=urls[2]),
        manifest, signing_key=raw_key.encode() if raw_key else None,
        require_signed=args.require_signed)
    _write_atomic(args.output, report)
    print(json.dumps({"cutover_ready": report["cutover_ready"],
                      "generation_id": report["generation_id"],
                      "output": str(args.output)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
