"""Typed execution authority for conformance, profiles, and assessments."""
from __future__ import annotations

from datetime import datetime, timezone
import json

from app.ir.hashing import canonical_json
from app.market_data.capability import (CapabilityAssessment, CapabilityProfile,
    CapabilityRefusal, ProviderConformance, assess_capability,
    verify_profile_conformance)
from app.market_truth.authority import load_market_truth_snapshot
from app.market_truth.identity import (MarketTruthError, ProviderEntity, ProviderProduct,
    load_provider_identity)
from app.market_truth.temporal import require_sql_utc_naive, to_sql_utc_naive


def persist_provider_conformance(session, conformance: ProviderConformance) -> None:
    from app.db.models import AuthorityProviderConformance
    _, product, _ = _load_product(session, conformance.product_address)
    if product.address != conformance.product_address:
        raise CapabilityRefusal("conformance product dependency does not match")
    existing = session.get(AuthorityProviderConformance, conformance.address)
    if existing is not None:
        if load_provider_conformance(session, conformance.address).canonical_bytes != conformance.canonical_bytes:
            raise CapabilityRefusal("provider conformance address collision")
        return
    session.add(AuthorityProviderConformance(address=conformance.address,
        schema=conformance.schema, canonical_json=conformance.canonical_bytes.decode(),
        product_address=conformance.product_address,
        observed_from=to_sql_utc_naive(conformance.observed_from, "observed_from"),
        observed_to=to_sql_utc_naive(conformance.observed_to, "observed_to"),
        authority_state="VERIFIED_V2"))
    session.flush()


def _load_product(session, product_address):
    from app.db.models import AuthorityProviderEntity, AuthorityProviderProduct
    row = session.get(AuthorityProviderProduct, product_address)
    if (row is None or row.authority_state != "VERIFIED_V2"
            or row.schema != ProviderProduct.SCHEMA):
        raise CapabilityRefusal("provider product authority is absent")
    try:
        product = ProviderProduct.from_bytes(row.canonical_json.encode())
    except MarketTruthError as exc:
        raise CapabilityRefusal("provider product bytes are malformed") from exc
    entity_row = session.get(AuthorityProviderEntity, product.entity_address)
    if (entity_row is None or entity_row.authority_state != "VERIFIED_V2"
            or entity_row.schema != ProviderEntity.SCHEMA):
        raise CapabilityRefusal("provider entity authority is absent")
    try:
        entity = ProviderEntity.from_bytes(entity_row.canonical_json.encode())
    except MarketTruthError as exc:
        raise CapabilityRefusal("provider entity bytes are malformed") from exc
    checks = ((product.address, row.address), (product.entity_address, row.entity_address),
        (product.product_code, row.product_code),
        (product.observation_namespace, row.observation_namespace),
        (entity.address, entity_row.address), (entity.entity_code, entity_row.entity_code))
    if any(left != right for left, right in checks):
        raise CapabilityRefusal("provider product copied columns do not match bytes")
    return entity, product, None


def load_provider_conformance(session, address: str) -> ProviderConformance:
    from app.db.models import AuthorityProviderConformance
    row = session.get(AuthorityProviderConformance, address)
    if (row is None or row.authority_state != "VERIFIED_V2"
            or row.schema not in ProviderConformance.SUPPORTED_SCHEMAS):
        raise CapabilityRefusal("provider conformance authority is absent")
    conformance = ProviderConformance.from_bytes(row.canonical_json.encode())
    if ((conformance.address, conformance.schema, conformance.product_address,
            to_sql_utc_naive(conformance.observed_from, "observed_from"),
            to_sql_utc_naive(conformance.observed_to, "observed_to"))
            != (row.address, row.schema, row.product_address,
                require_sql_utc_naive(row.observed_from, "observed_from"),
                require_sql_utc_naive(row.observed_to, "observed_to"))):
        raise CapabilityRefusal("provider conformance copied columns do not match bytes")
    _load_product(session, conformance.product_address)
    if conformance.result != "PASS":
        raise CapabilityRefusal("provider conformance did not pass")
    return conformance


def _profile_from_bytes(value: bytes) -> CapabilityProfile:
    try:
        document = json.loads(value.decode())
        if (canonical_json(document).encode() != value
                or set(document) != {"schema", "fact"}
                or document["schema"] not in CapabilityProfile.SUPPORTED_SCHEMAS):
            raise ValueError
        fact = document["fact"]
        required = {"owner_id", "mode", "profile_version", "observed_at", "expires_at",
            "conformance_evidence_address", "offers", "change_level", "provider_entity_address",
            "provider_product_address", "provider_contract_address"}
        if set(fact) != required:
            raise ValueError
        offers = []
        for raw_offer in fact["offers"]:
            offer = dict(raw_offer)
            if document["schema"] == CapabilityProfile.V3_SCHEMA:
                offer["available_from"] = (datetime.fromisoformat(offer["available_from"])
                    if offer["available_from"] is not None else None)
                offer["available_to"] = (datetime.fromisoformat(offer["available_to"])
                    if offer["available_to"] is not None else None)
            offers.append(offer)
        result = CapabilityProfile(**{**fact, "offers": tuple(offers),
            "observed_at": datetime.fromisoformat(fact["observed_at"]),
            "expires_at": datetime.fromisoformat(fact["expires_at"])})
    except (KeyError, TypeError, ValueError, UnicodeError) as exc:
        raise CapabilityRefusal("capability profile bytes are malformed") from exc
    if result.canonical_bytes != value:
        raise CapabilityRefusal("capability profile bytes do not reconstruct exactly")
    return result


def _verify_profile_dependencies(session, profile: CapabilityProfile, at_time: datetime):
    if profile.provider_contract_address is None or not isinstance(profile.observed_at, datetime):
        raise CapabilityRefusal("legacy profile has no typed authority")
    entity, product, contract = load_provider_identity(session, profile.provider_contract_address)
    conformance = load_provider_conformance(session, profile.conformance_evidence_address)
    if (entity.address != profile.provider_entity_address
            or product.address != profile.provider_product_address
            or contract.owner_id != profile.owner_id
            or contract.mode != profile.mode
            or contract.product_address != profile.provider_product_address
            or conformance.product_address != profile.provider_product_address
            or not (contract.effective_from <= at_time
                    and (contract.effective_to is None or at_time < contract.effective_to))
            or not (conformance.observed_from <= profile.observed_at <= conformance.observed_to)):
        raise CapabilityRefusal("profile entitlement or conformance dependency does not match")
    verify_profile_conformance(profile, conformance)
    return conformance, contract


def persist_capability_profile(session, profile: CapabilityProfile) -> None:
    from app.db.models import AuthorityCapabilityProfile
    if not isinstance(profile.observed_at, datetime) or not isinstance(profile.expires_at, datetime):
        raise CapabilityRefusal("legacy profile has no typed authority")
    _verify_profile_dependencies(session, profile, profile.observed_at)
    existing = session.get(AuthorityCapabilityProfile, profile.capability_profile_address)
    if existing is not None:
        if load_capability_profile(session, profile.capability_profile_address,
                at_time=profile.observed_at).canonical_bytes != profile.canonical_bytes:
            raise CapabilityRefusal("capability profile address collision")
        return
    session.add(AuthorityCapabilityProfile(address=profile.capability_profile_address,
        schema=profile.schema, canonical_json=profile.canonical_bytes.decode(), owner_id=profile.owner_id,
        mode=profile.mode, product_address=profile.provider_product_address,
        contract_address=profile.provider_contract_address,
        observed_at=to_sql_utc_naive(profile.observed_at, "observed_at"),
        expires_at=to_sql_utc_naive(profile.expires_at, "expires_at"),
        authority_state="VERIFIED_V2"))
    session.flush()


def _load_capability_profile_with_conformance(
    session,
    address: str,
    *,
    at_time: datetime,
) -> tuple[CapabilityProfile, ProviderConformance, object]:
    from app.db.models import AuthorityCapabilityProfile
    row = session.get(AuthorityCapabilityProfile, address)
    if (row is None or row.authority_state != "VERIFIED_V2"
            or row.schema not in CapabilityProfile.SUPPORTED_SCHEMAS):
        raise CapabilityRefusal("capability profile authority is absent")
    profile = _profile_from_bytes(row.canonical_json.encode())
    checks = ((profile.capability_profile_address, row.address), (profile.schema, row.schema),
        (profile.owner_id, row.owner_id),
        (profile.mode, row.mode), (profile.provider_product_address, row.product_address),
        (profile.provider_contract_address, row.contract_address),
        (to_sql_utc_naive(profile.observed_at, "observed_at"),
         require_sql_utc_naive(row.observed_at, "observed_at")),
        (to_sql_utc_naive(profile.expires_at, "expires_at"),
         require_sql_utc_naive(row.expires_at, "expires_at")))
    if any(left != right for left, right in checks):
        raise CapabilityRefusal("capability profile copied columns do not match bytes")
    at_time = at_time.astimezone(timezone.utc)
    if not profile.observed_at <= at_time <= profile.expires_at:
        raise CapabilityRefusal("capability profile is stale")
    conformance, contract = _verify_profile_dependencies(session, profile, at_time)
    return profile, conformance, contract


def load_capability_profile(session, address: str, *, at_time: datetime) -> CapabilityProfile:
    return _load_capability_profile_with_conformance(
        session, address, at_time=at_time,
    )[0]


def persist_capability_assessment(session, assessment: CapabilityAssessment, *, plan,
        at_time: datetime) -> None:
    from app.db.models import AuthorityCapabilityAssessment
    profile, conformance, contract = _load_capability_profile_with_conformance(
        session, assessment.capability_profile_address, at_time=at_time)
    truth = load_market_truth_snapshot(session, assessment.market_truth_snapshot_address)
    recomputed = assess_capability(plan=plan, profile=profile, owner_id=assessment.owner_id,
        mode=assessment.mode, dataset_manifest_address=assessment.dataset_manifest_address,
        market_truth_snapshot_address=truth.address,
        evaluation_policy_address=assessment.evaluation_policy_address,
        assessment_evidence_address=assessment.assessment_evidence_address,
        at_time=assessment.assessed_at, conformance=conformance,
        provider_contract=contract)
    if recomputed.fact() != assessment.fact():
        raise CapabilityRefusal("assessment results or dependencies were not recomputed exactly")
    existing = session.get(AuthorityCapabilityAssessment, assessment.authority_address)
    if existing is not None:
        if existing.canonical_json.encode() != assessment.canonical_bytes:
            raise CapabilityRefusal("capability assessment address collision")
        return
    session.add(AuthorityCapabilityAssessment(address=assessment.authority_address,
        schema="capability-assessment/2", canonical_json=assessment.canonical_bytes.decode(),
        owner_id=assessment.owner_id, mode=assessment.mode,
        profile_address=assessment.capability_profile_address,
        dataset_address=assessment.dataset_manifest_address,
        truth_address=assessment.market_truth_snapshot_address,
        assessed_at=to_sql_utc_naive(
            datetime.fromtimestamp(assessment.assessed_at, timezone.utc), "assessed_at"),
        authority_state="VERIFIED_V2"))
    session.flush()


def load_capability_assessment(session, address: str, *, plan, at_time: datetime) -> CapabilityAssessment:
    from app.db.models import AuthorityCapabilityAssessment
    row = session.get(AuthorityCapabilityAssessment, address)
    if row is None or row.authority_state != "VERIFIED_V2" or row.schema != "capability-assessment/2":
        raise CapabilityRefusal("capability assessment authority is absent")
    try:
        document = json.loads(row.canonical_json)
        if canonical_json(document) != row.canonical_json or set(document) != {"schema", "fact"} or document["schema"] != "capability-assessment/2":
            raise ValueError
        fact = document["fact"]
        if (not isinstance(fact, dict) or set(fact) != {
                "owner_id", "mode", "plan_address", "registry_snapshot_address",
                "capability_profile_address", "dataset_manifest_address",
                "market_truth_snapshot_address", "evaluation_policy_address",
                "assessment_evidence_address", "requirement_results", "assessed_at",
                "assessment_algorithm", "assessment_algorithm_version"}):
            raise ValueError
    except (KeyError, TypeError, ValueError) as exc:
        raise CapabilityRefusal("capability assessment bytes are malformed") from exc
    profile, conformance, contract = _load_capability_profile_with_conformance(
        session, fact["capability_profile_address"], at_time=at_time)
    truth = load_market_truth_snapshot(session, fact["market_truth_snapshot_address"])
    recomputed = assess_capability(plan=plan, profile=profile, owner_id=fact["owner_id"], mode=fact["mode"],
        dataset_manifest_address=fact["dataset_manifest_address"],
        market_truth_snapshot_address=truth.address,
        evaluation_policy_address=fact["evaluation_policy_address"],
        assessment_evidence_address=fact["assessment_evidence_address"], at_time=fact["assessed_at"],
        conformance=conformance, provider_contract=contract)
    checks = ((recomputed.authority_address, row.address), (recomputed.owner_id, row.owner_id),
        (recomputed.mode, row.mode), (recomputed.capability_profile_address, row.profile_address),
        (recomputed.dataset_manifest_address, row.dataset_address),
        (recomputed.market_truth_snapshot_address, row.truth_address),
        (to_sql_utc_naive(
            datetime.fromtimestamp(recomputed.assessed_at, timezone.utc), "assessed_at"),
         require_sql_utc_naive(row.assessed_at, "assessed_at")))
    if recomputed.canonical_bytes.decode() != row.canonical_json or any(a != b for a, b in checks):
        raise CapabilityRefusal("capability assessment bytes, results, or copied columns do not match")
    if recomputed.plan_address != plan.plan_address or recomputed.registry_snapshot_address != plan.registry_snapshot_address:
        raise CapabilityRefusal("capability assessment plan or registry is stale")
    return recomputed


__all__ = ["load_capability_assessment", "load_capability_profile", "load_provider_conformance",
    "persist_capability_assessment", "persist_capability_profile", "persist_provider_conformance"]
