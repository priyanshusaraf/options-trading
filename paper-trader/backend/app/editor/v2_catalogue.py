"""Immutable public V0 projection of the canonical platform registry.

The projection exposes declarations and identities, never executable callables.
Catalogue presence is global product metadata and makes no provider, data-right,
backtest, deployment, or execution-authority claim.
"""
from __future__ import annotations

import json
import re
from types import MappingProxyType
from typing import Any, Mapping

from app.ir.hashing import canonical_json, content_address
from app.ir.first_party import monitoring_intent_v2, original_strategy_primitives
from app.ir import original_strategy_presets
from app.ir.library import ANALYTICAL_V2_DISPOSITIONS, REGISTRY
from app.ir.schema import is_content_address
from app.editor import v2_catalogue_help


MAX_CATALOGUE_BYTES = 8 * 1024 * 1024
_GROUPS = (
    (1, "TYPE_4", "Price, Instrument & Market Data"),
    (2, "TYPE_2", "Indicators & Derived Features"),
    (3, "TYPE_3", "Market Structure, Derivatives & Cross-Instrument"),
    (4, "TYPE_5", "Logic, Math & State"),
    (5, "TYPE_1", "Execution & Position"),
)
_EXPECTED_COUNTS = {
    "groups": 5,
    "components": 270,
    "original_primitives": 24,
    "original_compounds": 2,
    "analytical_v2": 108,
    "type_3": 64,
    "type_5": 60,
    "monitoring_type_1_v2": 12,
    "analytical_unavailable": 17,
    "legacy_type_1_excluded": 61,
}
_ORIGINAL_PRIMITIVES = frozenset(original_strategy_primitives.V2_COMPONENTS)
_ORIGINAL_COMPOUNDS = frozenset(original_strategy_presets.V2_COMPONENTS)

_PRIVATE_PUBLIC_FIELDS = frozenset({
    "graph_id", "organization_id", "owner_id", "pnl_value", "profit_value",
    "research_result", "strategy_id", "tenant_id",
})
_TYPE_1_AUTHORITY_TOKENS = frozenset({
    "account", "broker", "capital", "deployment", "execution", "fill", "lease",
    "live", "money", "order", "quantity", "reservation", "route",
})
_ALLOWED_TYPE_1_AUTHORITY_KEYS = frozenset({
    "execution_form", "live", "mode_eligibility",
})


class CatalogueProjectionError(ValueError):
    """The registry cannot produce the closed accepted V0 catalogue."""


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _plain(child) for key, child in value.items()}
    if isinstance(value, (tuple, list, frozenset)):
        return [_plain(child) for child in value]
    return value


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(child) for key, child in value.items()})
    if isinstance(value, (tuple, list, frozenset)):
        return tuple(_freeze(child) for child in value)
    return value


def _monitoring_type_1_allowlist():
    identities = {}
    for name in monitoring_intent_v2.NAMES:
        key = monitoring_intent_v2.component_key(name)
        descriptor = monitoring_intent_v2.V2_COMPONENTS[key]
        identities[key] = (
            content_address(_plain(descriptor)),
            monitoring_intent_v2.NODE_CONTRACT_ADDRESSES[key],
            monitoring_intent_v2.V2_IMPLEMENTATIONS[key].implementation_address,
            content_address(_plain(monitoring_intent_v2.DATA_REQUIREMENTS[key])),
        )
    if len(identities) != 12:
        raise CatalogueProjectionError("accepted monitoring Type 1 allowlist changed")
    return MappingProxyType(dict(sorted(identities.items())))


_MONITORING_TYPE_1_ALLOWLIST = _monitoring_type_1_allowlist()


def _tokens(value: str) -> frozenset[str]:
    return frozenset(re.findall(r"[a-z0-9]+", value.lower()))


def _private_fields(value: str) -> frozenset[str]:
    lowered = value.lower()
    return frozenset(
        field for field in _PRIVATE_PUBLIC_FIELDS
        if re.search(rf"(?<![a-z0-9]){re.escape(field)}(?![a-z0-9])", lowered)
    )


def _validate_public_surface(value: Any, *, visible_family: str, path: tuple[str, ...] = ()):
    """Reject private or authority-shaped nested metadata before publication."""
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise CatalogueProjectionError("public catalogue metadata key is not text")
            key_tokens = _tokens(key)
            if _private_fields(key):
                raise CatalogueProjectionError(
                    f"private metadata is forbidden at public path {'.'.join((*path, key))}"
                )
            if visible_family == "TYPE_1" and key not in _ALLOWED_TYPE_1_AUTHORITY_KEYS \
                    and key_tokens & _TYPE_1_AUTHORITY_TOKENS:
                raise CatalogueProjectionError(
                    f"authority metadata is forbidden at public Type 1 path {'.'.join((*path, key))}"
                )
            _validate_public_surface(child, visible_family=visible_family, path=(*path, key))
        return
    if isinstance(value, (tuple, list, frozenset)):
        for index, child in enumerate(value):
            _validate_public_surface(
                child, visible_family=visible_family, path=(*path, str(index)),
            )
        return
    if isinstance(value, str):
        value_tokens = _tokens(value)
        if _private_fields(value):
            raise CatalogueProjectionError(
                f"private metadata value is forbidden at public path {'.'.join(path)}"
            )
        if visible_family == "TYPE_1" and value_tokens & _TYPE_1_AUTHORITY_TOKENS:
            raise CatalogueProjectionError(
                f"authority metadata value is forbidden at public Type 1 path {'.'.join(path)}"
            )


def _display_name(component_id: str) -> str:
    return component_id.rsplit(".", 1)[-1].replace("_", " ").title()


def _accepted_analytical_keys(dispositions: Mapping[str, Mapping[str, str]]):
    if len(dispositions) != 125:
        raise CatalogueProjectionError("analytical dispositions do not close 125 names")
    accepted = set()
    unavailable = set()
    for name, row in dispositions.items():
        if not isinstance(name, str) or not name:
            raise CatalogueProjectionError("analytical disposition name is invalid")
        key = (f"analytical.{name.lower()}", 2)
        status = row.get("status") if isinstance(row, Mapping) else None
        code = row.get("reason_code") if isinstance(row, Mapping) else None
        if not isinstance(code, str) or not code:
            raise CatalogueProjectionError("analytical disposition lacks a reason code")
        if status == "ACCEPTED_V2":
            accepted.add(key)
        elif status == "UNAVAILABLE":
            unavailable.add((key, code))
        else:
            raise CatalogueProjectionError("analytical disposition has an unknown status")
    if len(accepted) != 108 or len(unavailable) != 17:
        raise CatalogueProjectionError("analytical accepted/unavailable counts changed")
    return frozenset(accepted), tuple(sorted(unavailable))


def _binding_facts(registry: Any, key: tuple[str, int]):
    binding = registry.contract_bindings.get(key)
    if binding is None:
        return None, None
    document = _plain(binding.document)
    return document, content_address(document)


def _leaf_facts(registry, key, group):
    try:
        descriptor = registry.v2_components[key]
        contract = registry.node_contracts[key]
        declaration = registry.data_requirement_declarations[key]
        addresses = (content_address(_plain(descriptor)), registry.node_contract_addresses[key],
                     registry.v2_implementation_identities[key],
                     registry.data_requirement_declaration_addresses[key])
    except (KeyError, TypeError, AttributeError) as exc:
        raise CatalogueProjectionError(f"registry row {key!r} is incomplete") from exc
    if key != (descriptor.get("component_id"), descriptor.get("component_version")):
        raise CatalogueProjectionError(f"registry descriptor identity differs for {key!r}")
    if contract.get("visible_family") != group[1]:
        raise CatalogueProjectionError(f"registry family differs for {key!r}")
    if not all(is_content_address(address) for address in addresses):
        raise CatalogueProjectionError(f"registry row {key!r} lacks a content address")
    return descriptor, contract, declaration, addresses


def _leaf_authority(key, group, modes, providers, data, addresses):
    if group[1] != "TYPE_1":
        return "NONE"
    if (key[1] != 2 or modes != {"research": True, "paper": False, "live": False}
            or providers or data.get("classification") != "NO_DATA"):
        raise CatalogueProjectionError("V0 Type 1 row crosses monitoring-only authority")
    if _MONITORING_TYPE_1_ALLOWLIST.get(key) != addresses:
        raise CatalogueProjectionError(f"registry Type 1 identity is not the accepted monitoring component: {key!r}")
    return "MONITORING_ONLY"


def _leaf_row(registry: Any, key: tuple[str, int], group: tuple[int, str, str]):
    descriptor, contract, declaration, addresses = _leaf_facts(registry, key, group)
    component_address, contract_address, implementation_address, declaration_address = addresses
    modes = _plain(contract.get("mode_eligibility"))
    providers = _plain(contract.get("provider_requirements"))
    resources = _plain(contract.get("resource_profile"))
    if set(modes or {}) != {"research", "paper", "live"} or not isinstance(providers, list) or not isinstance(resources, dict):
        raise CatalogueProjectionError(f"registry contract facts are incomplete for {key!r}")
    data = _plain(declaration)
    conditional = bool(providers) or data.get("classification") != "NO_DATA"
    authority = _leaf_authority(key, group, modes, providers, data, addresses)
    binding, binding_address = _binding_facts(registry, key)
    for public_document in (descriptor, contract, declaration, binding or {}):
        _validate_public_surface(public_document, visible_family=group[1])
    return {
        "component_id": key[0],
        "component_version": key[1],
        "component_address": component_address,
        "display_name": _display_name(key[0]),
        "visible_family": group[1],
        "presentation_group_order": group[0],
        "presentation_group_name": group[2],
        "domain_family": descriptor["domain_family"],
        "structural_role": descriptor["structural_role"],
        "descriptor": _plain(descriptor),
        "node_contract": _plain(contract),
        "node_contract_address": contract_address,
        "implementation_address": implementation_address,
        "contract_binding": binding,
        "contract_binding_address": binding_address,
        "data_requirement": data,
        "data_requirement_address": declaration_address,
        "mode_eligibility": modes,
        "provider_requirements": providers,
        "resource_profile": resources,
        "availability": {
            "status": "CONDITIONAL" if conditional else "AVAILABLE",
            "authority": authority,
            "provider_support_verified": False,
            "data_rights_verified": False,
            "backtest_eligible": False,
        },
    }


def _validate_compound_snapshot(registry, key, component_address):
    payload = getattr(registry, "registry_snapshot_payload", None)
    if not isinstance(payload, Mapping) or content_address(_plain(payload)) != registry.registry_snapshot_address:
        raise CatalogueProjectionError("compound registry snapshot is stale")
    matches = [row for row in payload.get("v2_components", ())
               if (row.get("component_id"), row.get("component_version")) == key]
    if len(matches) != 1 or content_address(_plain(matches[0].get("value"))) != component_address:
        raise CatalogueProjectionError("compound descriptor differs from registry snapshot")


def _compound_row(registry: Any, key: tuple[str, int], group: tuple[int, str, str]):
    descriptor = registry.v2_components.get(key)
    if descriptor is None or not isinstance(descriptor.get("compound"), Mapping):
        raise CatalogueProjectionError(f"compound descriptor is absent for {key!r}")
    if key in registry.v2_implementation_identities or key in registry.node_contracts:
        raise CatalogueProjectionError("compound cannot carry a leaf implementation or contract")
    if key != (descriptor.get("component_id"), descriptor.get("component_version")):
        raise CatalogueProjectionError("compound descriptor identity differs")
    component_address = content_address(_plain(descriptor))
    if not is_content_address(registry.registry_snapshot_address):
        raise CatalogueProjectionError("compound registry binding is absent")
    _validate_compound_snapshot(registry, key, component_address)
    _validate_public_surface(descriptor, visible_family=group[1])
    return {
        "component_kind": "COMPOUND", "component_id": key[0], "component_version": key[1],
        "component_address": component_address, "display_name": _display_name(key[0]),
        "visible_family": group[1], "presentation_group_order": group[0],
        "presentation_group_name": group[2], "domain_family": descriptor["domain_family"],
        "structural_role": descriptor["structural_role"], "descriptor": _plain(descriptor),
        "node_contract": None, "node_contract_address": None, "implementation_address": None,
        "contract_binding": None, "contract_binding_address": None,
        "data_requirement": None, "data_requirement_address": None,
        "mode_eligibility": None, "provider_requirements": None, "resource_profile": None,
        "composition_binding": {"component_address": component_address,
                                "registry_identity": registry.registry_snapshot_address},
        "availability": {"status": "CONDITIONAL", "authority": "NONE",
                         "provider_support_verified": False, "data_rights_verified": False,
                         "backtest_eligible": False},
    }


def _component_row(registry: Any, key: tuple[str, int], group: tuple[int, str, str]):
    if key in _ORIGINAL_COMPOUNDS:
        return _compound_row(registry, key, group)
    row = _leaf_row(registry, key, group)
    return {"component_kind": "LEAF", **row, "composition_binding": None}


def _original_group_keys(registry, accepted_analytical, family):
    leaves = accepted_analytical | _ORIGINAL_PRIMITIVES
    keys = {key for key in leaves if registry.node_contracts.get(key, {}).get("visible_family") == family}
    if family == "TYPE_2":
        keys.update(_ORIGINAL_COMPOUNDS)
    return sorted(keys)


def _group_keys(registry, accepted_analytical, family):
    if family in {"TYPE_4", "TYPE_2"}:
        return _original_group_keys(registry, accepted_analytical, family)
    keys = (key for key in registry.v2_components
            if registry.node_contracts.get(key, {}).get("visible_family") == family)
    return sorted(key for key in keys if family != "TYPE_1" or key[1] == 2)


def _analytical_exclusions(registry, unavailable_analytical):
    analytical_exclusions = []
    for key, code in unavailable_analytical:
        legacy = (key[0], 1)
        contract = registry.node_contracts.get(legacy)
        if contract is None or contract.get("visible_family") not in {"TYPE_2", "TYPE_4"}:
            raise CatalogueProjectionError(f"unavailable analytical identity is unowned: {key!r}")
        analytical_exclusions.append({
            "kind": "ANALYTICAL_V2_UNAVAILABLE",
            "component_id": key[0],
            "component_version": key[1],
            "visible_family": contract["visible_family"],
            "reason_code": code,
            "executable": False,
            "authority": "NONE",
        })

    return analytical_exclusions


def _legacy_type1_keys(registry):
    return sorted(key for key in registry.v2_components
                  if key[1] == 1 and registry.node_contracts.get(key, {}).get("visible_family") == "TYPE_1")


def _legacy_exclusions(registry):
    components = registry.v2_components
    monitoring_ids = {
        key[0] for key in components
        if key[1] == 2 and registry.node_contracts.get(key, {}).get("visible_family") == "TYPE_1"
    }
    legacy_type_1 = []
    for key in _legacy_type1_keys(registry):
        replacement = key[0] in monitoring_ids
        legacy_type_1.append({
            "kind": "LEGACY_TYPE_1_EXCLUDED",
            "component_id": key[0],
            "component_version": key[1],
            "visible_family": "TYPE_1",
            "reason_code": (
                "V0_LEGACY_TYPE_1_REPLACED_BY_MONITORING_V2"
                if replacement else "V0_MONITORING_OPERATION_UNAVAILABLE"
            ),
            "replacement_component_version": 2 if replacement else None,
            "executable": False,
            "authority": "NONE",
        })

    return legacy_type_1


def _attach_help(groups, help_records):
    component_rows = [row for group in groups for row in group["components"]]
    try:
        validated_help = v2_catalogue_help.validate_help_projection(
            component_rows,
            v2_catalogue_help.project_help(component_rows)
            if help_records is None else help_records,
        )
    except v2_catalogue_help.CatalogueHelpError as exc:
        raise CatalogueProjectionError(str(exc)) from exc
    help_by_identity = {
        (record["component_id"], record["component_version"]): record
        for record in validated_help
    }
    for row in component_rows:
        row["help"] = help_by_identity[(row["component_id"], row["component_version"])]


def _project(
    registry: Any,
    dispositions: Mapping[str, Mapping[str, str]],
    *,
    help_records: Any = None,
):
    accepted_analytical, unavailable_analytical = _accepted_analytical_keys(dispositions)
    components = registry.v2_components
    missing = sorted((accepted_analytical | _ORIGINAL_PRIMITIVES | _ORIGINAL_COMPOUNDS) - set(components))
    if missing:
        raise CatalogueProjectionError(f"accepted analytical components are missing: {missing!r}")

    grouped = []
    family_counts = {}
    for group in _GROUPS:
        _, family, display_name = group
        keys = _group_keys(registry, accepted_analytical, family)
        family_counts[family] = len(keys)
        grouped.append({
            "order": group[0],
            "visible_family": family,
            "display_name": display_name,
            "components": [_component_row(registry, key, group) for key in keys],
        })

    analytical_exclusions = _analytical_exclusions(registry, unavailable_analytical)
    legacy_type_1 = _legacy_exclusions(registry)

    counts = {
        "groups": len(grouped),
        "components": sum(len(group["components"]) for group in grouped),
        "analytical_v2": len(accepted_analytical),
        "original_primitives": len(_ORIGINAL_PRIMITIVES),
        "original_compounds": len(_ORIGINAL_COMPOUNDS),
        "type_3": family_counts.get("TYPE_3", 0),
        "type_5": family_counts.get("TYPE_5", 0),
        "monitoring_type_1_v2": family_counts.get("TYPE_1", 0),
        "analytical_unavailable": len(analytical_exclusions),
        "legacy_type_1_excluded": len(legacy_type_1),
    }
    if counts != _EXPECTED_COUNTS:
        raise CatalogueProjectionError(f"catalogue closure changed: {counts!r}")

    _attach_help(grouped, help_records)

    return {
        "schema": "strategy-os-verified-language-catalogue/2",
        "registry_identity": registry.registry_snapshot_address,
        "groups": grouped,
        "exclusions": [*analytical_exclusions, *legacy_type_1],
        "counts": counts,
        "nonauthority": {
            "execution_authority": False,
            "provider_conformance": False,
            "data_rights": False,
            "backtest_eligibility": False,
            "monitoring_runtime": False,
            "deployment_authority": False,
        },
    }


def catalogue_bytes(
    registry: Any,
    dispositions: Mapping[str, Mapping[str, str]],
    *,
    help_records: Any = None,
) -> bytes:
    payload = _project(registry, dispositions, help_records=help_records)
    payload["catalogue_identity"] = content_address(payload)
    encoded = canonical_json(payload).encode("utf-8")
    if len(encoded) > MAX_CATALOGUE_BYTES:
        raise CatalogueProjectionError("catalogue exceeds its immutable response bound")
    return encoded


CATALOGUE_BYTES = catalogue_bytes(REGISTRY, ANALYTICAL_V2_DISPOSITIONS)
CATALOGUE_DOCUMENT = _freeze(json.loads(CATALOGUE_BYTES))
CATALOGUE_IDENTITY = CATALOGUE_DOCUMENT["catalogue_identity"]
CATALOGUE_ETAG = f'"{CATALOGUE_IDENTITY}"'


__all__ = [
    "CATALOGUE_BYTES", "CATALOGUE_DOCUMENT", "CATALOGUE_ETAG", "CATALOGUE_IDENTITY",
    "CatalogueProjectionError", "MAX_CATALOGUE_BYTES", "catalogue_bytes",
]
