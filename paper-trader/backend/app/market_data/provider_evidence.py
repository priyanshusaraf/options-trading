"""Fixture-only mapping into existing Phase 4 provider authority documents."""
from __future__ import annotations

import datetime as dt
import hashlib
from dataclasses import dataclass
from typing import Any, Mapping

from app.ir.validity import ValidityState
from app.market_data.capability import (
    CapabilityProfile,
    CapabilityRefusal,
    ProviderConformance,
    verify_profile_conformance,
)
from app.market_data.observations import ProviderObservation, RawObservationSegment
from app.market_truth.identity import (
    ProviderContract,
    ProviderEntity,
    ProviderInstrumentAlias,
    ProviderProduct,
    validate_provider_aliases,
)


_TOP_FIELDS = {
    "schema", "owner_id", "mode", "at_time", "entity", "product",
    "contract", "aliases", "conformance", "capability_profile", "raw_observation",
}
_SECRET_KEYS = {
    "api_key", "api_secret", "access_token", "authorization", "credential",
    "password", "private_key", "refresh_token", "secret", "totp",
}


class ProviderEvidenceRefusal(ValueError):
    """Unknown, incomplete, stale, conflicting, or secret-bearing evidence."""


@dataclass(frozen=True)
class ProviderEvidenceBundle:
    entity: ProviderEntity
    product: ProviderProduct
    contract: ProviderContract
    aliases: tuple[ProviderInstrumentAlias, ...]
    conformance: ProviderConformance
    capability_profile: CapabilityProfile
    raw_segment: RawObservationSegment
    raw_observation: ProviderObservation


def map_provider_evidence(fixture: Mapping[str, Any]) -> ProviderEvidenceBundle:
    """Construct only existing typed authority facts from one non-secret fixture."""
    if not isinstance(fixture, Mapping) or set(fixture) != _TOP_FIELDS \
            or fixture.get("schema") != "provider-evidence-fixture/1":
        raise ProviderEvidenceRefusal("provider fixture uses an open or incomplete schema")
    _reject_secrets(fixture)
    try:
        at_time = _time(fixture["at_time"])
        owner_id = fixture["owner_id"]
        mode = fixture["mode"]
        entity_fact = _closed(fixture["entity"], {
            "authority_namespace", "entity_code", "legal_name",
        }, "entity")
        entity = ProviderEntity(**entity_fact)
        product_fact = _closed(fixture["product"], {
            "product_code", "observation_namespace", "product_version",
        }, "product")
        product = ProviderProduct(entity.address, **product_fact)
        contract_fact = _closed(fixture["contract"], {
            "permitted_uses", "effective_from", "effective_to", "evidence_address",
        }, "contract")
        contract = ProviderContract(
            owner_id=owner_id,
            product_address=product.address,
            mode=mode,
            permitted_uses=tuple(contract_fact["permitted_uses"]),
            effective_from=_time(contract_fact["effective_from"]),
            effective_to=(
                _time(contract_fact["effective_to"])
                if contract_fact["effective_to"] is not None else None
            ),
            evidence_address=contract_fact["evidence_address"],
        )
        if not _contains(contract.effective_from, contract.effective_to, at_time):
            raise ProviderEvidenceRefusal("provider contract is not effective at fixture time")
        raw_aliases = fixture["aliases"]
        if not isinstance(raw_aliases, (tuple, list)) or not raw_aliases:
            raise ProviderEvidenceRefusal("provider aliases are absent")
        aliases = tuple(_alias(product, item) for item in raw_aliases)
        validate_provider_aliases(aliases)
        conformance_fact = _closed(fixture["conformance"], {
            "tested_fields", "tested_resolutions", "test_method", "test_version",
            "observed_from", "observed_to", "evidence_artifacts", "result", "coverage",
        }, "conformance")
        coverage = tuple(_coverage_row(item) for item in conformance_fact["coverage"])
        conformance = ProviderConformance(
            product.address,
            tuple(conformance_fact["tested_fields"]),
            tuple(conformance_fact["tested_resolutions"]),
            conformance_fact["test_method"],
            conformance_fact["test_version"],
            _time(conformance_fact["observed_from"]),
            _time(conformance_fact["observed_to"]),
            tuple(conformance_fact["evidence_artifacts"]),
            conformance_fact["result"],
            coverage,
        )
        if conformance.result != "PASS" or not (
            conformance.observed_from <= at_time <= conformance.observed_to
        ):
            raise ProviderEvidenceRefusal("provider conformance is failed or stale")
        profile_fact = _closed(fixture["capability_profile"], {
            "profile_version", "observed_at", "expires_at", "offers", "change_level",
        }, "capability profile")
        profile = CapabilityProfile(
            owner_id=owner_id,
            mode=mode,
            profile_version=profile_fact["profile_version"],
            observed_at=_time(profile_fact["observed_at"]),
            expires_at=_time(profile_fact["expires_at"]),
            conformance_evidence_address=conformance.address,
            offers=tuple(_profile_offer(item) for item in profile_fact["offers"]),
            change_level=profile_fact["change_level"],
            provider_entity_address=entity.address,
            provider_product_address=product.address,
            provider_contract_address=contract.address,
        )
        observed = _time(profile.observed_at)
        expires = _time(profile.expires_at)
        if not (observed <= at_time < expires):
            raise ProviderEvidenceRefusal("capability profile is not current")
        _verify_profile_offers(profile, conformance)
        segment, observation = _raw_observation(
            fixture["raw_observation"], owner_id, entity, product, contract,
            aliases, at_time,
        )
        # Exact reconstruction proves these are existing typed facts, not copied claims.
        if (
            ProviderEntity.from_bytes(entity.canonical_bytes) != entity
            or ProviderProduct.from_bytes(product.canonical_bytes) != product
            or ProviderContract.from_bytes(contract.canonical_bytes) != contract
            or ProviderConformance.from_bytes(conformance.canonical_bytes) != conformance
            or ProviderObservation.from_bytes(observation.canonical_bytes) != observation
        ):
            raise ProviderEvidenceRefusal("provider facts do not reconstruct exactly")
        return ProviderEvidenceBundle(
            entity, product, contract, aliases, conformance, profile, segment, observation,
        )
    except ProviderEvidenceRefusal:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise ProviderEvidenceRefusal("provider evidence is invalid or conflicting") from exc


def _alias(product: ProviderProduct, value: Any) -> ProviderInstrumentAlias:
    fact = _closed(value, {
        "provider_token", "provider_symbol", "canonical_instrument_address",
        "adapter_schema_version", "effective_from", "effective_to",
        "observation_namespace", "source_evidence_address",
    }, "alias")
    if fact["observation_namespace"] != product.observation_namespace:
        raise ProviderEvidenceRefusal("alias namespace conflicts with product")
    return ProviderInstrumentAlias(
        product.address,
        fact["provider_token"],
        fact["provider_symbol"],
        fact["canonical_instrument_address"],
        fact["adapter_schema_version"],
        _time(fact["effective_from"]),
        _time(fact["effective_to"]) if fact["effective_to"] is not None else None,
        fact["observation_namespace"],
        fact["source_evidence_address"],
    )


def _raw_observation(
    raw: Any, owner_id: str, entity: ProviderEntity, product: ProviderProduct,
    contract: ProviderContract, aliases: tuple[ProviderInstrumentAlias, ...],
    at_time: dt.datetime,
) -> tuple[RawObservationSegment, ProviderObservation]:
    fact = _closed(raw, {
        "alias_index", "media_type", "raw_schema", "payload_text", "field",
        "resolution_seconds", "event_time", "completed_at", "available_at",
        "recorded_at", "sequence_id", "correction_id",
    }, "raw observation")
    if type(fact["alias_index"]) is not int or not 0 <= fact["alias_index"] < len(aliases):
        raise ProviderEvidenceRefusal("raw observation alias index is invalid")
    alias = aliases[fact["alias_index"]]
    event_time = _time(fact["event_time"])
    if not _contains(alias.effective_from, alias.effective_to, event_time) \
            or not _contains(contract.effective_from, contract.effective_to, event_time):
        raise ProviderEvidenceRefusal("raw observation is outside alias/contract interval")
    payload_text = fact["payload_text"]
    if not isinstance(payload_text, str) or not payload_text:
        raise ProviderEvidenceRefusal("raw fixture payload is absent")
    payload = payload_text.encode("utf-8")
    segment = RawObservationSegment(
        owner_id, product.address, contract.address, fact["media_type"],
        fact["raw_schema"], payload, _time(fact["recorded_at"]),
    )
    observation = ProviderObservation(
        owner_id=owner_id,
        provider_entity_address=entity.address,
        provider_product_address=product.address,
        provider_contract_address=contract.address,
        mapping_address=alias.address,
        provider_token=alias.provider_token,
        raw_schema=fact["raw_schema"],
        field=fact["field"],
        resolution_seconds=fact["resolution_seconds"],
        event_time=event_time,
        completed_at=_time(fact["completed_at"]),
        available_at=_time(fact["available_at"]),
        recorded_at=_time(fact["recorded_at"]),
        sequence_id=fact["sequence_id"],
        correction_id=fact["correction_id"],
        raw_segment_address=segment.address,
        raw_byte_offset=0,
        raw_byte_length=len(payload),
        raw_byte_digest=hashlib.sha256(payload).hexdigest(),
        validity=ValidityState.VALID,
    )
    observation.verify_segment(segment)
    if observation.recorded_at > at_time:
        raise ProviderEvidenceRefusal("fixture observation is not yet knowable")
    return segment, observation


def _verify_profile_offers(profile: CapabilityProfile, conformance: ProviderConformance) -> None:
    try:
        verify_profile_conformance(profile, conformance)
    except CapabilityRefusal as exc:
        raise ProviderEvidenceRefusal("capability offer exceeds conformance evidence") from exc


def _coverage_row(value: Any) -> Mapping[str, Any]:
    row = dict(_closed(value, {
        "instrument", "field", "resolution_seconds", "history",
        "maximum_freshness_seconds", "depth", "session", "alignment",
        "derived_local", "entitlement",
    }, "conformance coverage"))
    history = dict(_closed(row["history"], {"from", "to", "bars"}, "coverage history"))
    history["from"] = _time(history["from"])
    history["to"] = _time(history["to"])
    row["history"] = history
    return row


def _profile_offer(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ProviderEvidenceRefusal("capability profile offer is invalid")
    offer = dict(value)
    if "available_from" in offer or "available_to" in offer:
        if "available_from" not in offer or "available_to" not in offer:
            raise ProviderEvidenceRefusal("capability profile offer range is incomplete")
        offer["available_from"] = (
            _time(offer["available_from"]) if offer["available_from"] is not None else None)
        offer["available_to"] = (
            _time(offer["available_to"]) if offer["available_to"] is not None else None)
    return offer


def _closed(value: Any, fields: set[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise ProviderEvidenceRefusal(f"{label} uses an open or incomplete schema")
    return value


def _contains(start: dt.datetime, end: dt.datetime | None, value: dt.datetime) -> bool:
    return start <= value and (end is None or value < end)


def _time(value: Any) -> dt.datetime:
    if isinstance(value, str):
        value = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if not isinstance(value, dt.datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ProviderEvidenceRefusal("provider evidence time must be timezone-aware")
    return value.astimezone(dt.UTC)


def _reject_secrets(value: Any, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered in _SECRET_KEYS or any(part in lowered for part in (
                "credential", "password", "secret", "private_key", "access_token",
            )):
                raise ProviderEvidenceRefusal(f"secret-bearing fixture field at {path}.{key}")
            _reject_secrets(item, f"{path}.{key}")
    elif isinstance(value, (tuple, list)):
        for index, item in enumerate(value):
            _reject_secrets(item, f"{path}[{index}]")


__all__ = ["ProviderEvidenceBundle", "ProviderEvidenceRefusal", "map_provider_evidence"]
