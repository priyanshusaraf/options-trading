"""Durable Component IR v2 graph facts and persisted Phase 4 verification.

These records are evidence only.  They neither adapt v2 into the legacy runtime
nor grant provider, deployment, or money authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from app.ir.hashing import canonical_json, content_address
from app.ir.resolve import resolve_v2
from app.ir.schema import is_content_address
from app.market_data.requirements import compile_data_requirement_plan


PHASE4_SCHEME = "strategy-admission/phase4-data/1"
PHASE4_BOUND_SCHEME = "strategy-admission/phase4-data/2"
PHASE4_SCHEMES = frozenset({PHASE4_SCHEME, PHASE4_BOUND_SCHEME})
V2_RUNTIME_UNAVAILABLE = "V2_RUNTIME_UNAVAILABLE"

_SATISFIED_REASON = "one declared offer covers the complete requirement"


def _bound_check(condition, reason):
    if not condition:
        raise V2GraphVerificationError(reason)


def require_bound_phase4_receipt(document):
    """Validate closed stored bytes; this does not reconstruct source authority."""
    from app.market_data.capability import require_bound_capability_assessment_envelope
    receipt = _plain(document)
    required = {"scheme", "contract_suite", "parity_suite", "format_version", "owner_id",
        "graph_identifier", "graph_version", "graph_address", "content_address", "base_v2_admission",
        "base_v2_admission_address", "phase4_data_binding", "capability_assessment", "dataset_selection"}
    _bound_check(isinstance(receipt, dict) and set(receipt) == required, "bound receipt is not closed")
    _bound_check((receipt["scheme"], receipt["contract_suite"], receipt["parity_suite"], receipt["format_version"])
        == (PHASE4_BOUND_SCHEME, "closed-component-ir/2", "prefix-vector-parity/1", 2), "bound receipt contract differs")
    base, binding = receipt["base_v2_admission"], receipt["phase4_data_binding"]
    _require_bound_base(receipt, base)
    _require_bound_binding(binding, base)
    envelope, address = require_bound_capability_assessment_envelope(receipt["capability_assessment"])
    fact = envelope["fact"]
    repeated = ("owner_id", "mode", "plan_address", "registry_snapshot_address", "dataset_set_address",
                "input_binding_context_address", "evaluation_policy_address")
    _bound_check(address == binding["capability_assessment_address"]
        and all(fact[key] == binding[key] for key in repeated)
        and all(row["result"] == "SATISFIED" for row in fact["requirement_results"]), "bound assessment differs")
    _require_bound_selection(receipt["dataset_selection"], binding, fact)
    return receipt


def _require_bound_base(receipt, base):
    from app.strategy.admission import is_closed_phase4_registry_snapshot
    keys = {"content_address", "contract_suite", "document", "evidence", "format_version", "graph_address",
        "graph_identifier", "graph_version", "owner_id", "parity_suite", "registry_snapshot", "resolved_topology", "scheme"}
    _bound_check(isinstance(base, dict) and set(base) == keys, "bound base is not closed")
    _bound_check((base["scheme"], base["format_version"], base["contract_suite"], base["parity_suite"])
        == ("strategy-admission/2", 2, "closed-component-ir/2", "prefix-vector-parity/1"), "bound base contract differs")
    repeated = ("owner_id", "graph_identifier", "graph_version", "graph_address", "content_address", "format_version")
    _bound_check(all(receipt[key] == base[key] for key in repeated)
        and receipt["base_v2_admission_address"] == content_address(base), "bound base identity differs")
    facts = V2GraphFacts(base["owner_id"], base["graph_identifier"], base["graph_version"],
        canonical_json(base["document"]), 2, base["content_address"], base["graph_address"],
        base["registry_snapshot"]["address"])
    _verify_graph_facts(facts, document=base["document"])
    _bound_check(is_closed_phase4_registry_snapshot(base["registry_snapshot"],
        expected_address=facts.registry_snapshot_address), "bound registry snapshot differs")


def _require_bound_binding(binding, base):
    keys = {"owner_id", "mode", "authored_ir_address", "registry_snapshot_address", "resolved_graph_address",
        "implementation_closure_address", "declaration_addresses", "plan_address", "capability_assessment_address",
        "dataset_manifest_address", "dataset_set_address", "primary_input", "input_binding_context_address",
        "truth_snapshot_addresses", "evaluation_policy_address"}
    _bound_check(isinstance(binding, dict) and set(binding) == keys, "bound data binding is not closed")
    _bound_check(binding["mode"] == "RESEARCH" and binding["owner_id"] == base["owner_id"]
        and binding["authored_ir_address"] == base["content_address"]
        and binding["registry_snapshot_address"] == base["registry_snapshot"]["address"], "bound graph identity differs")
    for name in keys - {"owner_id", "mode", "primary_input", "declaration_addresses", "truth_snapshot_addresses"}:
        _bound_check(is_content_address(binding[name]), "bound address is invalid")
    for name in ("declaration_addresses", "truth_snapshot_addresses"):
        _require_sorted_addresses(binding[name], "bound address list is invalid")


def _require_bound_selection(selection, binding, fact):
    keys = {"schema", "owner_id", "primary_input", "as_of", "alignment", "inputs"}
    _bound_check(isinstance(selection, dict) and set(selection) == keys, "bound dataset selection is not closed")
    _require_bound_selection_identity(selection, binding, fact)
    inputs = selection["inputs"]
    _bound_check(isinstance(inputs, dict) and 2 <= len(inputs) <= 8
        and binding["primary_input"] in inputs, "bound dataset inputs are invalid")
    _bound_check(set(inputs) == {row["graph_input_id"] for row in fact["sources"]}, "bound source coverage differs")
    for source in fact["sources"]:
        _require_bound_selection_source(inputs[source["graph_input_id"]], source)
    _bound_check(inputs[binding["primary_input"]]["dataset_manifest_address"] == binding["dataset_manifest_address"],
        "bound primary manifest differs")
    _bound_check(binding["truth_snapshot_addresses"] == sorted({row["market_truth_snapshot_address"] for row in fact["sources"]}),
        "bound truth snapshots differ")


def _require_bound_selection_identity(selection, binding, fact):
    _bound_check(selection["schema"] == "canonical-research-input-selection/1"
        and selection["owner_id"] == binding["owner_id"] and selection["primary_input"] == binding["primary_input"]
        and selection["alignment"] == {"kind": "EXACT", "maximum_skew_seconds": 0}
        and content_address(selection) == binding["dataset_set_address"], "bound dataset selection differs")
    _require_bound_cutoff(selection["as_of"], fact["assessed_at"])


def _require_bound_cutoff(value, assessed_at):
    import datetime as dt
    cutoff = dt.datetime.fromisoformat(value)
    _bound_check(cutoff.utcoffset() == dt.timedelta(0) and not cutoff.microsecond
        and cutoff.isoformat() == value and cutoff.timestamp() == assessed_at, "bound cutoff differs")


def _require_bound_selection_source(value, source):
    keys = {"source_input_id", "dataset_manifest_address", "source_input_digest", "source_binding_address",
            "source_codec", "source_provenance_address"}
    _bound_check(isinstance(value, dict) and set(value) == keys, "bound selection source is not closed")
    for name in ("source_input_id", "dataset_manifest_address", "source_binding_address"):
        _bound_check(value[name] == source[name], "bound selection source differs")
    for name in keys - {"source_input_id", "source_codec"}:
        _bound_check(is_content_address(value[name]), "bound selection source address is invalid")
    _bound_check(isinstance(value["source_codec"], str) and bool(value["source_codec"]), "bound source codec is invalid")


def canonical_admission_values(artifact):
    """Common pure receipt checks for the two immutable persistence planes."""
    document = _admission_document(artifact)
    if document.get("scheme") == PHASE4_SCHEME:
        require_singular_phase4_receipt(document)
    elif document.get("scheme") == PHASE4_BOUND_SCHEME:
        require_bound_phase4_receipt(document)
    address = content_address(document)
    _bound_check(is_content_address(address) and artifact.admission_address == address,
                 "admission artifact address does not match canonical bytes")
    values = _admission_identity(artifact, document)
    version, semantic_content = _admission_semantics(artifact, document)
    return {**values, "admission_address": address, "artifact_json": canonical_json(document),
            "format_version": version, "content_address": semantic_content}


def _admission_document(artifact):
    try:
        document = artifact.to_dict()
    except Exception as exc:
        raise V2GraphVerificationError("admission artifact cannot produce receipt bytes") from exc
    _bound_check(isinstance(document, Mapping), "admission artifact must produce a mapping")
    try:
        canonical_json(document)
    except (TypeError, ValueError) as exc:
        raise V2GraphVerificationError("admission artifact is not canonical JSON") from exc
    return document


def _admission_identity(artifact, document):
    fields = ("owner_id", "graph_identifier", "graph_version", "graph_address", "scheme", "contract_suite", "parity_suite")
    values = {name: document.get(name) for name in fields}
    for name, value in values.items():
        _bound_check(value == getattr(artifact, name, object()), f"admission artifact {name} does not match canonical bytes")
    _bound_check(isinstance(values["graph_identifier"], str) and isinstance(values["graph_version"], int)
        and not isinstance(values["graph_version"], bool) and values["graph_version"] >= 1
        and is_content_address(values["graph_address"]), "admission artifact identity is invalid")
    _bound_check(all(isinstance(values[name], str) and values[name]
        for name in ("owner_id", "scheme", "contract_suite", "parity_suite")), "admission artifact identity is invalid")
    return values


def _admission_semantics(artifact, document):
    if document.get("format_version") == 2:
        address = document.get("content_address")
        _bound_check(is_content_address(address) and address == getattr(artifact, "content_address", None),
                     "v2 content address does not match canonical receipt")
        return 2, address
    _bound_check(getattr(artifact, "format_version", None) is None and getattr(artifact, "content_address", None) is None,
                 "legacy admission semantic identity must remain null")
    return None, None


def require_singular_phase4_receipt(document):
    """Preserve /1's exact closed shape and repeated identity checks."""
    required = {"scheme", "contract_suite", "parity_suite", "format_version", "owner_id", "graph_identifier",
        "graph_version", "graph_address", "content_address", "base_v2_admission", "base_v2_admission_address",
        "phase4_data_binding", "capability_assessment"}
    binding_keys = {"owner_id", "mode", "authored_ir_address", "registry_snapshot_address", "resolved_graph_address",
        "implementation_closure_address", "declaration_addresses", "plan_address", "capability_assessment_address",
        "dataset_manifest_address", "market_truth_snapshot_address", "evaluation_policy_address"}
    binding, base = document.get("phase4_data_binding"), document.get("base_v2_admission")
    _bound_check(set(document) == required and isinstance(binding, Mapping) and set(binding) == binding_keys,
                 "Phase 4 admission wrapper is partial or base-mismatched")
    _singular_base_shape(document, base)
    _singular_binding_identity(document, base, binding, binding_keys)
    _singular_graph_identity(base, binding)
    require_singular_phase4_assessment(document, binding)


def _singular_base_shape(document, base):
    keys = {"content_address", "contract_suite", "document", "evidence", "format_version", "graph_address",
        "graph_identifier", "graph_version", "owner_id", "parity_suite", "registry_snapshot", "resolved_topology", "scheme"}
    _bound_check(isinstance(base, Mapping) and set(base) == keys, "Phase 4 admission wrapper is partial or base-mismatched")
    _bound_check((base.get("scheme"), base.get("format_version"), base.get("contract_suite"), base.get("parity_suite"))
        == ("strategy-admission/2", 2, "closed-component-ir/2", "prefix-vector-parity/1")
        and is_content_address(document["base_v2_admission_address"])
        and content_address(base) == document["base_v2_admission_address"], "Phase 4 admission wrapper is partial or base-mismatched")


def _singular_binding_identity(document, base, binding, binding_keys):
    _bound_check(binding["mode"] in {"RESEARCH", "PAPER", "LIVE"}
        and all(is_content_address(binding[key]) for key in binding_keys - {"owner_id", "mode", "declaration_addresses"}),
        "Phase 4 admission wrapper is internally inconsistent")
    _require_sorted_addresses(binding["declaration_addresses"], "Phase 4 admission wrapper is internally inconsistent")
    fields = ("owner_id", "graph_identifier", "graph_version", "graph_address", "content_address")
    _bound_check(all(document[key] == base.get(key) for key in fields)
        and binding["owner_id"] == base.get("owner_id") and binding["authored_ir_address"] == base.get("content_address"),
        "Phase 4 admission wrapper is internally inconsistent")


def _singular_graph_identity(base, binding):
    from app.strategy.admission import is_closed_phase4_registry_snapshot
    graph = base.get("document")
    _bound_check(isinstance(graph, Mapping) and isinstance(base.get("evidence"), Mapping)
        and isinstance(base.get("resolved_topology"), Mapping), "Phase 4 admission wrapper is internally inconsistent")
    try:
        address = content_address({"identity_scheme_version": 1, "graph": {key: graph[key]
            for key in ("format_version", "graph_inputs", "graph_outputs", "nodes", "edges")}})
    except KeyError:
        address = None
    _bound_check(base.get("content_address") == content_address(graph)
        and base.get("graph_identifier") == graph.get("strategy_id") and base.get("graph_version") == graph.get("strategy_version")
        and base.get("graph_address") == address, "Phase 4 admission wrapper is internally inconsistent")
    _bound_check(is_closed_phase4_registry_snapshot(base.get("registry_snapshot"),
        expected_address=binding["registry_snapshot_address"]), "Phase 4 admission wrapper is internally inconsistent")


def _require_sorted_addresses(values, reason):
    _bound_check(isinstance(values, list) and values == sorted(set(values))
        and all(is_content_address(value) for value in values), reason)


def require_singular_phase4_assessment(document, binding):
    from app.market_data.capability import require_capability_assessment_authority_envelope
    envelope, address = require_capability_assessment_authority_envelope(document.get("capability_assessment"))
    fact = envelope["fact"]
    repeated = ("owner_id", "mode", "plan_address", "registry_snapshot_address", "dataset_manifest_address",
                "market_truth_snapshot_address", "evaluation_policy_address")
    _bound_check(address == binding["capability_assessment_address"] and all(fact[name] == binding[name] for name in repeated)
        and all(row["result"] == "SATISFIED" for row in fact["requirement_results"]),
        "Phase 4 capability assessment binding is stale")


class V2GraphVerificationError(ValueError):
    """A persisted v2 graph, receipt, or assessment fact is incomplete or stale."""


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _plain(value[key]) for key in sorted(value)}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    raise V2GraphVerificationError("v2 persistence facts must be closed JSON")


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(value[key]) for key in sorted(value)})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


@dataclass(frozen=True)
class V2GraphFacts:
    owner_id: str
    graph_identifier: str
    graph_version: int
    artifact_json: str
    format_version: int
    content_address: str
    graph_address: str
    registry_snapshot_address: str

    @property
    def document(self) -> Mapping[str, Any]:
        import json

        return _freeze(json.loads(self.artifact_json))


@dataclass(frozen=True)
class PersistedPhase4Artifact:
    """A verified persisted receipt without in-memory write authority."""

    document: Mapping[str, Any]
    base_v2_admission: Any
    assessment_document: Mapping[str, Any]
    plan: Any

    def to_dict(self) -> dict[str, Any]:
        return _plain(self.document)

    @property
    def admission_address(self) -> str:
        return content_address(_plain(self.document))

    @property
    def assessment(self) -> Mapping[str, Any]:
        return _plain(self.assessment_document)

    def __getattr__(self, name: str) -> Any:
        try:
            return self.document[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


def facts_from_row(row: Any) -> V2GraphFacts:
    """Read and validate either plane's structurally equivalent v2 graph row."""
    import json

    try:
        facts = V2GraphFacts(**{
            name: getattr(row, name)
            for name in V2GraphFacts.__dataclass_fields__
        })
        document = json.loads(facts.artifact_json)
    except (AttributeError, TypeError, ValueError) as exc:
        raise V2GraphVerificationError("v2 graph row is incomplete") from exc
    if not isinstance(document, Mapping):
        raise V2GraphVerificationError("v2 graph row does not contain a document")
    _verify_graph_facts(facts, document=document)
    return facts


def require_row_matches(row: Any, expected: V2GraphFacts) -> Any:
    actual = facts_from_row(row)
    if actual != expected:
        raise V2GraphVerificationError("conflicting bytes for immutable v2 graph version")
    return row


def _verify_graph_facts(facts: V2GraphFacts, *, document: Mapping[str, Any]) -> None:
    try:
        projection = {
            "identity_scheme_version": 1,
            "graph": {
                key: document[key]
                for key in (
                    "format_version", "graph_inputs", "graph_outputs", "nodes", "edges"
                )
            },
        }
    except (KeyError, TypeError) as exc:
        raise V2GraphVerificationError("v2 graph document is incomplete") from exc
    if (
        facts.format_version != 2
        or document.get("format_version") != 2
        or facts.graph_identifier != document.get("strategy_id")
        or facts.graph_version != document.get("strategy_version")
        or canonical_json(document) != facts.artifact_json
        or content_address(document) != facts.content_address
        or content_address(projection) != facts.graph_address
        or not is_content_address(facts.registry_snapshot_address)
    ):
        raise V2GraphVerificationError("v2 graph identity does not match canonical bytes")
