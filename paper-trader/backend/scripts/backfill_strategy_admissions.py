"""Exact-only, dry-run-first causal-admission backfill.

The migration intentionally left every new ``admission_address`` nullable.  This
command is the only upgrade path: it re-admits immutable graph bytes against the
*current* registry, stores the resulting immutable receipt, and fills a dependent
row only when its own durable fields prove that exact receipt.  In particular it
does not use a deployment's present state to explain a historical money row.
"""
from __future__ import annotations

import argparse
import json
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from sqlalchemy import select


@dataclass(frozen=True)
class BackfillDecision:
    status: str                    # exact | quarantined | already_admitted
    admission_address: str | None
    reason: str


@dataclass(frozen=True)
class BackfillRow:
    consumer: str
    identity: str
    decision: BackfillDecision


def handwritten_adapter(strategy_key: object, strategy_version: object) -> str:
    """Classify the only historical handwritten execution identities explicitly.

    This is a disposition table, not a key/version inference mechanism.  The
    expanding-z adapter can only proceed once the row supplies the exact admitted IR
    graph bytes; trend impulse has no equivalent and remains legacy-unadmitted.
    """
    if strategy_key == "expanding_z_v4":
        return "EXPANDING_Z_EQUIVALENT_IR_REQUIRED"
    if strategy_key == "trend_impulse_v3":
        return "LEGACY_UNADMITTED"
    return "NO_EQUIVALENT_IR"


def expanding_z_adapter_input(*, strategy_key: object, strategy_version: object,
                              graph: Mapping[str, Any]):
    """Return the one reviewed handwritten-to-IR mapping, or no mapping at all."""
    if strategy_key != "expanding_z_v4":
        return None
    import numpy as np
    import pandas as pd

    from app.ir.hashing import content_address
    from app.ir.registry import DependencyBoundary
    from app.ir.strategies.expanding_z import GRAPH
    from app.strategy.admission import HandwrittenAdapterInput, IRGraphAdmissionInput
    from app.strategy.registry.expanding_z_v4 import ExpandingZImpulseV4

    adapter = ExpandingZImpulseV4()
    # The historical identity and bytes must both name the shipped parity graph.
    if (strategy_version != adapter.version
            or content_address(graph) != content_address(GRAPH)
            or graph.get("identifier") != GRAPH.get("identifier")
            or graph.get("version") != GRAPH.get("version")):
        return None
    return HandwrittenAdapterInput(
        strategy_key=adapter.key, strategy_version=adapter.version,
        adapter_implementation=ExpandingZImpulseV4,
        adapter_dependencies=DependencyBoundary("defining_module", (np, pd)),
        equivalent_ir=IRGraphAdmissionInput(graph=graph, parameters={}, risk_model=None),
    )


def _json_object(value: object) -> dict[str, Any] | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        decoded = json.loads(value)
    except (TypeError, ValueError):
        return None
    return decoded if isinstance(decoded, dict) else None


def _canonical_json_object(value: object) -> dict[str, Any] | None:
    document = _json_object(value)
    if document is None:
        return None
    from app.ir.hashing import canonical_json
    try:
        return document if canonical_json(document) == value else None
    except (TypeError, ValueError):
        return None


def _row_graph_address(row: Any) -> str | None:
    """Read the three real schema spellings; do not invent a fourth one."""
    value = getattr(row, "graph_content_address", None)
    if isinstance(value, str) and value:
        return value
    value = getattr(row, "content_address", None)
    if isinstance(value, str) and value:
        return value
    return getattr(row, "graph_address", None)


def classify(row: Any, *, owner_id: str, graph: Mapping[str, Any],
             parameters: Mapping[str, Any], risk_model: Mapping[str, Any] | None,
             registry: Any, admit: Callable[..., Any] | None = None) -> BackfillDecision:
    """Recompute a receipt from exact graph bytes, never from a label/version."""
    from app.strategy.admission import IRGraphAdmissionInput, admit_strategy

    decision = (admit or admit_strategy)(
        owner_id=owner_id,
        source_input=IRGraphAdmissionInput(
            graph=graph, parameters=parameters, risk_model=risk_model),
        registry=registry,
    )
    artifact = getattr(decision, "artifact", None)
    if artifact is None:
        refusal = getattr(decision, "refusal_code", None)
        return BackfillDecision("quarantined", None, getattr(refusal, "value", "RECEIPT_STALE"))
    if _row_graph_address(row) != artifact.graph_address:
        return BackfillDecision("quarantined", None, "ARTEFACT_MISMATCH")
    if (getattr(row, "owner_id", None) != owner_id
            or getattr(graph, "get", lambda _k, _d=None: None)("identifier")
            != artifact.graph_identifier
            or getattr(graph, "get", lambda _k, _d=None: None)("version")
            != artifact.graph_version):
        return BackfillDecision("quarantined", None, "ARTEFACT_MISMATCH")
    return BackfillDecision("exact", artifact.admission_address, "")


def _artifact_identity(artifact: Any) -> tuple[str, int, str, str, str]:
    """The execution identity supplied by the admitted IR runtime."""
    return (
        artifact.graph_identifier,
        artifact.graph_version,
        artifact.graph_address,
        f"ir.{artifact.graph_identifier}",
        artifact.graph_address,
    )


def _executed_identity(artifact: Any) -> tuple[str, str]:
    if getattr(artifact, "source", None) == "ir_graph":
        return f"ir.{artifact.graph_identifier}", str(artifact.graph_version)
    source = getattr(artifact, "source_evidence", None)
    if source is None:
        return f"ir.{artifact.graph_identifier}", artifact.graph_address
    return source.strategy_key, source.strategy_version


def _same_identity(row: Any, artifact: Any, *, key: object | None = None,
                   version: object | None = None) -> bool:
    identifier, graph_version, graph_address, expected_key, expected_version = _artifact_identity(artifact)
    return (
        getattr(row, "owner_id", None) == artifact.owner_id
        and _row_graph_address(row) == graph_address
        and (getattr(row, "graph_identifier", identifier) == identifier)
        and (getattr(row, "graph_version", graph_version) == graph_version)
        and (key is None or key == expected_key)
        and (version is None or version == expected_version)
    )


def _parameters_match(encoded: object, artifact: Any) -> bool:
    from app.ir.hashing import canonical_json
    parsed = _canonical_json_object(encoded)
    if parsed is None:
        return False
    try:
        return canonical_json(parsed) == canonical_json(dict(artifact.bound_parameters))
    except (TypeError, ValueError):
        return False


def predicate_for(consumer: str, row: Any, *, artifact: Any,
                  exact_intents: Mapping[str, Any] | None = None,
                  exact_runs: Mapping[int, Any] | None = None) -> BackfillDecision:
    """Return the precise durable proof verdict for one current-schema row.

    A positive verdict is deliberately stricter than an address comparison.  The
    caller can use this function in dry-run mode because it has no side effects.
    """
    address = artifact.admission_address
    if getattr(row, "admission_address", None):
        return BackfillDecision("already_admitted", getattr(row, "admission_address"), "")
    if consumer == "GraphVersion":
        canonical = _canonical_json_object(getattr(row, "artifact_json", None))
        if canonical is None:
            return BackfillDecision("quarantined", None, "NONCANONICAL_GRAPH")
        if not _same_identity(row, artifact):
            return BackfillDecision("quarantined", None, "ARTEFACT_MISMATCH")
        return BackfillDecision("exact", address, "")

    if consumer == "BacktestRun":
        # The current persisted descriptor contains a strategy descriptor and an
        # admission address, but no historical engine manifest or bound graph/parameter
        # proof.  Arbitrary JSON keys would be claims added after the fact, so all legacy
        # rows remain quarantined until a future schema records those facts at enqueue.
        return BackfillDecision("quarantined", None, "MISSING_ENGINE_MANIFEST")

    if consumer == "BacktestResult":
        # A result is exact only after an exact run and a persisted execution-result
        # manifest.  Neither was written by the pre-Phase-3 producer.
        return BackfillDecision("quarantined", None, "PARENT_RUN_UNPROVEN")

    if consumer == "Deployment":
        if (getattr(row, "owner_id", None) != artifact.owner_id
                or (getattr(row, "strategy_key", None), getattr(row, "strategy_version", None))
                != _executed_identity(artifact)):
            return BackfillDecision("quarantined", None, "ARTEFACT_MISMATCH")
        if not isinstance(getattr(row, "broker_account_id", None), str) or not _parameters_match(
                getattr(row, "params_json", None), artifact):
            return BackfillDecision("quarantined", None, "MISSING_HISTORICAL_PROVENANCE")
        return BackfillDecision("exact", address, "")

    if consumer in {"IrShadowDeployment", "IrPaperDeployment"}:
        # Current execution schema records the research decision envelope address,
        # but not that decision's research receipt.  It is therefore unprovable in
        # this bounded command; do not turn `admission_ok` into a receipt claim.
        # In particular an appended receipt for a null legacy GraphVersion is not a
        # substitute for the paper/shadow activation proof, whose existing boundary
        # deliberately requires the row-local address and verified research evidence.
        if not _same_identity(row, artifact, key=getattr(row, "strategy_key", None)):
            return BackfillDecision("quarantined", None, "ARTEFACT_MISMATCH")
        return BackfillDecision("quarantined", None, "MISSING_RESEARCH_RECEIPT")

    if consumer == "ExecutionIntent":
        context = _canonical_json_object(getattr(row, "context_json", None))
        if context is None:
            return BackfillDecision("quarantined", None, "MISSING_INTENT_SNAPSHOT")
        snapshot = context.get("deployment_receipt_snapshot")
        if snapshot != address:
            return BackfillDecision("quarantined", None, "MISSING_INTENT_SNAPSHOT")
        if (context.get("graph_address") != artifact.graph_address
                or context.get("parameters") != dict(artifact.bound_parameters)
                or getattr(row, "owner_id", None) != artifact.owner_id
                or (getattr(row, "strategy_key", None), getattr(row, "strategy_version", None))
                != _executed_identity(artifact)):
            return BackfillDecision("quarantined", None, "ARTEFACT_MISMATCH")
        if not isinstance(getattr(row, "broker_account_id", None), str):
            return BackfillDecision("quarantined", None, "MISSING_HISTORICAL_PROVENANCE")
        return BackfillDecision("exact", address, "")

    if consumer == "Position":
        intent = (exact_intents or {}).get(getattr(row, "entry_intent_id", None))
        if intent is None:
            return BackfillDecision("quarantined", None, "ENTRY_SOURCE_UNPROVEN")
        if (getattr(row, "owner_id", None) != getattr(intent, "owner_id", None)
                or getattr(row, "broker_account_id", None) != getattr(intent, "broker_account_id", None)
                or getattr(row, "strategy_key", None) != getattr(intent, "strategy_key", None)
                or getattr(row, "strategy_version", None) != getattr(intent, "strategy_version", None)
                or getattr(intent, "admission_address", None) != address):
            return BackfillDecision("quarantined", None, "ENTRY_SOURCE_MISMATCH")
        return BackfillDecision("exact", address, "")

    if consumer == "Trade":
        intent = (exact_intents or {}).get(getattr(row, "entry_intent_id", None))
        if intent is None:
            return BackfillDecision("quarantined", None, "ENTRY_SOURCE_UNPROVEN")
        if (getattr(row, "owner_id", None) != getattr(intent, "owner_id", None)
                or getattr(row, "broker_account_id", None) != getattr(intent, "broker_account_id", None)
                or getattr(row, "strategy_key", None) != getattr(intent, "strategy_key", None)
                or getattr(row, "strategy_version", None) != getattr(intent, "strategy_version", None)
                or getattr(intent, "admission_address", None) != address):
            return BackfillDecision("quarantined", None, "ENTRY_SOURCE_MISMATCH")
        return BackfillDecision("exact", address, "")
    raise ValueError(f"unsupported consumer {consumer!r}")


def _identity(consumer: str, row: Any) -> str:
    if consumer == "GraphVersion":
        return f"{row.owner_id}:{row.graph_identifier}:{row.version}"
    return f"{getattr(row, 'owner_id', '')}:{getattr(row, 'id', getattr(row, 'client_intent_id', ''))}"


def _all_rows(session: Any) -> Iterable[tuple[str, Any]]:
    """Enumerate actual current-schema consumers in deterministic dependency order."""
    from app.db.models import (BacktestResult, BacktestRun, Deployment, ExecutionIntent,
                               GraphVersion, IrPaperDeployment, IrShadowDeployment,
                               Position, Trade)
    for consumer, model in (
        ("GraphVersion", GraphVersion), ("BacktestRun", BacktestRun),
        ("BacktestResult", BacktestResult), ("Deployment", Deployment),
        ("IrShadowDeployment", IrShadowDeployment), ("IrPaperDeployment", IrPaperDeployment),
        ("ExecutionIntent", ExecutionIntent), ("Position", Position), ("Trade", Trade),
    ):
        for row in session.scalars(select(model).where(model.admission_address.is_(None))).all():
            yield consumer, row


def _graph_artifact(session: Any, row: Any, registry: Any, admit: Callable[..., Any] | None):
    document = _canonical_json_object(row.artifact_json)
    if document is None:
        return None, BackfillDecision("quarantined", None, "NONCANONICAL_GRAPH")
    # The shipped expanding-z bytes have one reviewed source runtime.  Persist that
    # adapter receipt on GraphVersion itself so execution's canonical loader sees the
    # same address an attributed historical intent will carry; two competing receipts
    # for one GraphVersion would make a later load fail closed.
    source_input = expanding_z_adapter_input(
        strategy_key="expanding_z_v4",
        strategy_version=__import__("app.strategy.registry.expanding_z_v4", fromlist=["ExpandingZImpulseV4"])
        .ExpandingZImpulseV4().version,
        graph=document)
    from app.strategy.admission import IRGraphAdmissionInput, admit_strategy
    if source_input is None:
        source_input = IRGraphAdmissionInput(
            graph=document, parameters={}, risk_model=document.get("risk_model"))
    full = (admit or admit_strategy)(owner_id=row.owner_id, source_input=source_input,
                                     registry=registry)
    artifact = getattr(full, "artifact", None)
    if artifact is None:
        refusal = getattr(full, "refusal_code", None)
        return None, BackfillDecision("quarantined", None, getattr(refusal, "value", "RECEIPT_STALE"))
    if artifact.graph_address != row.content_address:
        return None, BackfillDecision("quarantined", None, "ARTEFACT_MISMATCH")
    decision = BackfillDecision("exact", artifact.admission_address, "")
    # classify returns public data; recompute only after it accepted exact bytes.
    if decision.status != "exact":
        return None, decision
    return full.artifact, decision


def _durable_graph_address(consumer: str, row: Any) -> str | None:
    """Extract a graph address only from that row's immutable historical record."""
    if getattr(row, "attribution_state", None) == "LEGACY_UNVERIFIED":
        return None
    direct = _row_graph_address(row)
    if isinstance(direct, str) and direct:
        return direct
    if consumer == "BacktestRun":
        request = _canonical_json_object(getattr(row, "request_json", None))
        return request.get("graph_address") if request else None
    if consumer == "ExecutionIntent":
        context = _canonical_json_object(getattr(row, "context_json", None))
        return context.get("graph_address") if context else None
    return None


def run_backfill(session: Any, *, registry: Any, apply: bool,
                 admit: Callable[..., Any] | None = None) -> dict[str, Any]:
    """Inspect every consumer; apply only exact proofs in the caller transaction."""
    from app.core import strategy_admissions

    report: list[BackfillRow] = []
    artifacts: dict[tuple[str, str], Any] = {}
    intent_artifacts: dict[str, Any] = {}
    graph_documents: dict[tuple[str, str], Mapping[str, Any]] = {}
    exact_runs: dict[int, Any] = {}
    exact_intents: dict[str, Any] = {}

    # Graph versions are the sole re-admission source.  Nothing below consults a
    # mutable deployment to invent a historical graph.
    rows = list(_all_rows(session))
    for consumer, row in rows:
        if consumer != "GraphVersion":
            continue
        artifact, decision = _graph_artifact(session, row, registry, admit)
        if artifact is not None:
            artifacts[(artifact.owner_id, artifact.graph_address)] = artifact
            graph_documents[(artifact.owner_id, artifact.graph_address)] = _canonical_json_object(
                row.artifact_json) or {}
            if apply:
                # GraphVersion itself is append-only.  Receipt storage is additive;
                # load_verified_admission permits null only when this exact persisted
                # graph still independently matches the requested receipt.
                strategy_admissions.put(session, artifact)
        report.append(BackfillRow(consumer, _identity(consumer, row), decision))

    for consumer, row in rows:
        if consumer == "GraphVersion":
            continue
        if getattr(row, "attribution_state", None) == "LEGACY_UNVERIFIED":
            report.append(BackfillRow(
                consumer, _identity(consumer, row),
                BackfillDecision("quarantined", None, "LEGACY_UNVERIFIED")))
            continue
        artifact = None
        # These are immutable row identities, not deployment joins.  Consumers with
        # no graph address can only be accepted through their durable source below.
        address = _durable_graph_address(consumer, row)
        if isinstance(address, str):
            artifact = artifacts.get((getattr(row, "owner_id", None), address))
            document = graph_documents.get((getattr(row, "owner_id", None), address))
            adapter_input = (expanding_z_adapter_input(
                strategy_key=getattr(row, "strategy_key", None),
                strategy_version=getattr(row, "strategy_version", None), graph=document)
                if document is not None else None)
            if adapter_input is not None:
                from app.strategy.admission import admit_strategy
                adapter_decision = (admit or admit_strategy)(
                    owner_id=row.owner_id, source_input=adapter_input, registry=registry)
                if adapter_decision.artifact is not None:
                    artifact = adapter_decision.artifact
                    if apply:
                        strategy_admissions.put(session, artifact)
        if artifact is None and consumer in {"Position", "Trade"}:
            source = exact_intents.get(getattr(row, "entry_intent_id", None))
            if source is None and getattr(row, "entry_intent_id", None):
                from app.db.models import ExecutionIntent
                source = session.get(ExecutionIntent, row.entry_intent_id)
                if source is not None:
                    source_artifact = next((candidate for candidate in artifacts.values()
                                            if candidate.owner_id == source.owner_id
                                            and candidate.admission_address
                                            == source.admission_address), None)
                    if source_artifact is not None:
                        exact_intents[source.client_intent_id] = source
                        intent_artifacts[source.client_intent_id] = source_artifact
            if source is not None:
                artifact = intent_artifacts.get(getattr(row, "entry_intent_id", None))
        if artifact is None:
            disposition = handwritten_adapter(
                getattr(row, "strategy_key", None), getattr(row, "strategy_version", None))
            decision = BackfillDecision(
                "quarantined", None,
                ("LEGACY_UNADMITTED" if disposition == "LEGACY_UNADMITTED"
                 else "NO_EXACT_GRAPH_PROOF"))
        else:
            decision = predicate_for(consumer, row, artifact=artifact,
                                     exact_intents=exact_intents, exact_runs=exact_runs)
        if decision.status == "exact":
            if apply:
                row.admission_address = decision.admission_address
            if consumer == "BacktestRun":
                exact_runs[row.id] = row
            elif consumer == "ExecutionIntent":
                # Dry-run must propagate prospective proof without mutating ORM state;
                # apply mode has already stamped the row above.
                exact_intents[row.client_intent_id] = SimpleNamespace(
                    owner_id=row.owner_id, broker_account_id=row.broker_account_id,
                    strategy_key=row.strategy_key, strategy_version=row.strategy_version,
                    admission_address=decision.admission_address)
                intent_artifacts[row.client_intent_id] = artifact
        report.append(BackfillRow(consumer, _identity(consumer, row), decision))

    return {
        "exact": sum(item.decision.status == "exact" for item in report),
        "already_admitted": sum(item.decision.status == "already_admitted" for item in report),
        "quarantined": sum(item.decision.status == "quarantined" for item in report),
        "rows": [{"consumer": item.consumer, "identity": item.identity,
                  "status": item.decision.status, "admission_address": item.decision.admission_address,
                  "reason": item.decision.reason} for item in report],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--dry-run-json", type=Path, metavar="PATH")
    modes.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)

    from app.db.session import SessionLocal
    from app.ir.library import REGISTRY
    with SessionLocal.begin() as session:
        result = run_backfill(session, registry=REGISTRY, apply=args.apply)
    encoded = json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n"
    if args.dry_run_json:
        args.dry_run_json.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
