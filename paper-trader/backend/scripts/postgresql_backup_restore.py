#!/usr/bin/env python3
"""Bounded local three-plane pg_dump/pg_restore automation."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import tempfile
from pathlib import Path
from sqlalchemy.engine import make_url

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.version import get_build_sha
from app.db.restore_contract import (
    canonical_manifest,
    capture_manifest,
    configured_restore_planes,
    verify_manifest_signature,
    verify_restore,
)
from app.operations.postgresql_backup import (
    assert_fresh_restore_target,
    postgres_process_spec,
    run_process_spec,
    sha256_file,
)

PLANE_ENV = {
    "execution": "PT_DATABASE_URL",
    "research": "PT_RESEARCH_DATABASE_URL",
    "ledger": "PT_LEDGER_DATABASE_URL",
}


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _urls(prefix: str = "") -> dict[str, str]:
    values = {plane: os.environ.get(prefix + name, "") for plane, name in PLANE_ENV.items()}
    if not all(values.values()):
        raise SystemExit(f"all three {prefix or 'source ' }plane URL environment variables are required")
    return values


def _physical_key(url: str) -> tuple[str, str, int, str]:
    parsed = make_url(url)
    return (parsed.get_backend_name(), (parsed.host or "").lower(),
            int(parsed.port or 5432), parsed.database or "")


def backup(args) -> dict:
    source = _urls()
    maintenance = json.loads(args.maintenance_evidence.read_text(encoding="utf-8"))
    started = dt.datetime.now(dt.timezone.utc)
    artifacts = {}
    for plane in ("execution", "research", "ledger"):
        path = args.directory / args.generation / f"{plane}.dump"
        path.parent.mkdir(parents=True, exist_ok=True)
        spec = postgres_process_spec(source[plane], executable=args.pg_dump,
                                     action="dump", artifact=path)
        run_process_spec(spec, timeout_seconds=args.timeout)
        artifacts[plane] = {"identifier": path.name, "sha256": sha256_file(path)}
    completed = dt.datetime.now(dt.timezone.utc)
    raw_key = os.environ.get(args.signing_key_env)
    manifest = capture_manifest(
        configured_restore_planes(execution_url=source["execution"],
                                  research_url=source["research"],
                                  ledger_url=source["ledger"]),
        generation_id=args.generation, source_build=get_build_sha(), artifacts=artifacts,
        maintenance_evidence=maintenance, backup_started_at=started,
        backup_completed_at=completed,
        signing_key=raw_key.encode() if raw_key else None)
    _atomic_text(args.directory / args.generation / "manifest.json", canonical_manifest(manifest))
    return {"generation_id": args.generation, "manifest": "manifest.json",
            "managed_pitr": "UNPROVEN"}


def restore(args) -> dict:
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    raw_key = os.environ.get(args.signing_key_env)
    # Complete the closed manifest/signature preflight before resolving or
    # opening any target authority and before executing pg_restore.
    verify_manifest_signature(
        manifest, signing_key=raw_key.encode() if raw_key else None,
        require_signed=args.require_signed)
    target = _urls("RESTORE_")
    expected = {item["plane"]: item for item in manifest["planes"]}
    # Complete every freshness/activity check before the first restore mutates a
    # shared target database. Rechecking after one plane restores would mistake
    # our own earlier tables for pre-existing application activity.
    checked = set()
    for plane in ("execution", "research", "ledger"):
        physical = _physical_key(target[plane])
        if physical not in checked:
            assert_fresh_restore_target(target[plane], expected_schemas=set(target))
            checked.add(physical)
    for plane in ("execution", "research", "ledger"):
        artifact = args.manifest.parent / expected[plane]["artifact"]["identifier"]
        if sha256_file(artifact) != expected[plane]["artifact"]["sha256"]:
            raise SystemExit(f"{plane} backup artifact digest differs from manifest")
        spec = postgres_process_spec(target[plane], executable=args.pg_restore,
                                     action="restore", artifact=artifact)
        run_process_spec(spec, timeout_seconds=args.timeout)
    report = verify_restore(
        configured_restore_planes(execution_url=target["execution"],
                                  research_url=target["research"], ledger_url=target["ledger"]),
        manifest, signing_key=raw_key.encode() if raw_key else None,
        require_signed=args.require_signed)
    _atomic_text(args.output, json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n")
    return {"generation_id": report["generation_id"],
            "cutover_ready": report["cutover_ready"], "output": str(args.output)}


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--timeout", type=int, default=900)
    common.add_argument("--signing-key-env", default="PT_RESTORE_SIGNING_KEY")
    make = sub.add_parser("backup", parents=[common])
    make.add_argument("--generation", required=True)
    make.add_argument("--directory", type=Path, required=True)
    make.add_argument("--maintenance-evidence", type=Path, required=True)
    make.add_argument("--pg-dump", type=Path, default=Path("pg_dump"))
    load = sub.add_parser("restore", parents=[common])
    load.add_argument("--manifest", type=Path, required=True)
    load.add_argument("--output", type=Path, required=True)
    load.add_argument("--pg-restore", type=Path, default=Path("pg_restore"))
    load.add_argument("--require-signed", action="store_true")
    args = parser.parse_args()
    result = backup(args) if args.action == "backup" else restore(args)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
