"""Research persistence and fresh-load authority for Phase 4 datasets."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from sqlalchemy import select

from app.db.concurrency import caller_owned_savepoint
from app.backtest.dataset_store import (
    DatasetManifest,
    DatasetSegment,
    verify_dataset_manifest,
)
from app.ir.hashing import canonical_json
from app.market_data.observations import retain_observation_dependencies
from research.domain.models import (
    ResearchDatasetManifestSegmentV2,
    ResearchDatasetManifestV2,
    ResearchDatasetSegmentV2,
)


@dataclass(frozen=True)
class VerifiedDatasetAuthority:
    manifest: DatasetManifest
    segments: tuple[DatasetSegment, ...]
    object_bytes: tuple[bytes, ...]


def _dependency_addresses(manifest: DatasetManifest) -> list[str]:
    return sorted({
        *manifest.correction_addresses, *manifest.provider_entity_addresses,
        *manifest.provider_product_addresses, *manifest.provider_contract_addresses,
        *manifest.provider_observation_addresses, *manifest.normalized_observation_addresses,
        *manifest.raw_schema_addresses, *manifest.normalization_transform_addresses,
        *manifest.creation_evidence_addresses,
        *manifest.truth_snapshot_addresses, manifest.capability_profile_address,
        manifest.alignment_policy_address,
        manifest.missing_data_policy_address, manifest.adjustment_policy_address,
        manifest.roll_policy_address, *manifest.algorithm_addresses,
    })


def _resolved_address(value: object) -> str | None:
    address = getattr(value, "authority_address", None)
    if address is None:
        address = getattr(value, "capability_profile_address", None)
    if address is None:
        address = getattr(value, "address", None)
        address = address() if callable(address) else address
    return address if isinstance(address, str) else None


def _require_address(value: object, expected: str, role: str) -> object:
    if _resolved_address(value) != expected:
        raise ValueError(f"dataset {role} did not reconstruct to its manifest address")
    return value


def _verify_provider_identity_roles(execution_session, manifest):
    from app.market_truth.identity import load_provider_identity
    entities, products = set(), set()
    for address in manifest.provider_contract_addresses:
        entity, product, contract = load_provider_identity(execution_session, address)
        _require_address(contract, address, "provider contract")
        if contract.owner_id != manifest.owner_id:
            raise ValueError("dataset provider contract owner mismatch")
        entities.add(entity.address)
        products.add(product.address)
    if (entities != set(manifest.provider_entity_addresses)
            or products != set(manifest.provider_product_addresses)):
        raise ValueError("dataset provider identity roles do not reconstruct exactly")


def _fixed_role_loaders(manifest):
    from app.market_data.dataset_authority import (
        load_dataset_correction, load_dataset_creation_evidence, load_deterministic_algorithm,
        load_normalization_transform, load_raw_schema,
    )
    from app.market_data.observations import load_normalized_observation, load_provider_observation
    from app.market_truth.authority import load_market_truth_snapshot
    from app.market_truth.identity import load_canonical_instrument
    provider_memo = {}

    def load_provider_with_memo(session, address):
        return load_provider_observation(session, address, _memo=provider_memo)

    def load_normalized_with_memo(session, address):
        return load_normalized_observation(session, address, _provider_memo=provider_memo)

    return (
        (manifest.instrument_addresses, load_canonical_instrument, "instrument"),
        (manifest.provider_observation_addresses, load_provider_with_memo, "provider observation"),
        (manifest.normalized_observation_addresses, load_normalized_with_memo, "normalized observation"),
        (manifest.raw_schema_addresses, load_raw_schema, "raw schema"),
        (manifest.normalization_transform_addresses, load_normalization_transform, "normalization transform"),
        (manifest.truth_snapshot_addresses, load_market_truth_snapshot, "truth snapshot"),
        (manifest.correction_addresses, load_dataset_correction, "dataset correction"),
        (manifest.creation_evidence_addresses, load_dataset_creation_evidence, "dataset creation evidence"),
        (manifest.algorithm_addresses, load_deterministic_algorithm, "deterministic algorithm"),
    )


def _load_fixed_roles(execution_session, manifest):
    resolved_roles = {}
    for addresses, loader, role in _fixed_role_loaders(manifest):
        resolved_roles[role] = []
        for address in addresses:
            resolved = _require_address(loader(execution_session, address), address, role)
            if getattr(resolved, "owner_id", manifest.owner_id) != manifest.owner_id:
                raise ValueError(f"dataset {role} owner mismatch")
            resolved_roles[role].append(resolved)
    return resolved_roles


def _verify_provider_observation_roles(manifest, observations):
    entities = set(manifest.provider_entity_addresses)
    products = set(manifest.provider_product_addresses)
    contracts = set(manifest.provider_contract_addresses)
    for observation in observations:
        if (observation.owner_id != manifest.owner_id
                or observation.provider_entity_address not in entities
                or observation.provider_product_address not in products
                or observation.provider_contract_address not in contracts):
            raise ValueError("dataset provider observation roles do not match manifest")


def _verify_normalized_observation_roles(manifest, observations):
    sources = set(manifest.provider_observation_addresses)
    transforms = set(manifest.normalization_transform_addresses)
    algorithms = set(manifest.algorithm_addresses)
    truths = set(manifest.truth_snapshot_addresses)
    for observation in observations:
        if (not set(observation.provider_observation_addresses).issubset(sources)
                or observation.canonical_instrument_address not in manifest.instrument_addresses
                or observation.transform_address not in transforms
                or observation.policy_address != manifest.alignment_policy_address
                or observation.algorithm_address not in algorithms
                or observation.market_truth_address not in truths):
            raise ValueError("dataset normalized observation roles do not match manifest")


def _verify_raw_schema_roles(manifest, schemas):
    products = set(manifest.provider_product_addresses)
    contracts = set(manifest.provider_contract_addresses)
    for schema in schemas:
        if (schema.provider_product_address not in products
                or schema.provider_contract_address not in contracts):
            raise ValueError("dataset raw-schema roles do not match manifest")


def _verify_transform_roles(manifest, transforms):
    schemas = set(manifest.raw_schema_addresses)
    algorithms = set(manifest.algorithm_addresses)
    for transform in transforms:
        if (not set(transform.input_raw_schema_addresses).issubset(schemas)
                or transform.algorithm_address not in algorithms):
            raise ValueError("dataset transform roles do not match manifest")


def _verify_creation_roles(manifest, creations):
    algorithms = set(manifest.algorithm_addresses)
    sources = set(manifest.provider_observation_addresses) | set(manifest.normalized_observation_addresses)
    for creation in creations:
        if (creation.algorithm_address not in algorithms
                or not set(creation.source_addresses).issubset(sources)):
            raise ValueError("dataset creation-evidence roles do not match manifest")


def _verify_correction_roles(manifest, corrections):
    products = set(manifest.provider_product_addresses)
    contracts = set(manifest.provider_contract_addresses)
    creations = set(manifest.creation_evidence_addresses)
    algorithms = set(manifest.algorithm_addresses)
    for correction in corrections:
        if (correction.provider_product_address not in products
                or correction.provider_contract_address not in contracts
                or correction.creation_evidence_address not in creations
                or correction.algorithm_address not in algorithms):
            raise ValueError("dataset correction roles do not match manifest")


def _verify_policy_scope(manifest, policy, role):
    if policy.owner_id != manifest.owner_id:
        raise ValueError(f"dataset {role} owner mismatch")
    instruments = getattr(policy, "instrument_addresses", ())
    if instruments and not set(instruments).issubset(manifest.instrument_addresses):
        raise ValueError(f"dataset {role} instruments do not match manifest")


def _verify_policy_dependencies(manifest, policy, role):
    if getattr(policy, "algorithm_address", None) not in set(manifest.algorithm_addresses):
        raise ValueError(f"dataset {role} algorithm does not match manifest")
    truths = set(manifest.truth_snapshot_addresses)
    references = getattr(policy, "truth_snapshot_addresses", ())
    if references and not set(references).issubset(truths):
        raise ValueError(f"dataset {role} truth does not match manifest")
    reference = getattr(policy, "truth_snapshot_address", None)
    if reference is not None and reference not in truths:
        raise ValueError(f"dataset {role} truth does not match manifest")


def _verify_policy_roles(execution_session, manifest):
    from app.market_data.dataset_authority import (
        load_adjustment_policy, load_alignment_policy, load_missing_data_policy, load_roll_policy,
    )
    singletons = (
        (manifest.alignment_policy_address, load_alignment_policy, "alignment policy"),
        (manifest.missing_data_policy_address, load_missing_data_policy, "missing-data policy"),
        (manifest.adjustment_policy_address, load_adjustment_policy, "adjustment policy"),
        (manifest.roll_policy_address, load_roll_policy, "roll policy"),
    )
    for address, loader, role in singletons:
        resolved = _require_address(loader(execution_session, address), address, role)
        _verify_policy_scope(manifest, resolved, role)
        _verify_policy_dependencies(manifest, resolved, role)


def _verify_profile_roles(execution_session, manifest, at_time):
    from app.market_data.authority import load_capability_profile
    profile = _require_address(load_capability_profile(
        execution_session, manifest.capability_profile_address, at_time=at_time),
        manifest.capability_profile_address, "capability profile")
    if (profile.owner_id != manifest.owner_id or profile.mode != manifest.mode
            or profile.provider_entity_address not in set(manifest.provider_entity_addresses)
            or profile.provider_product_address not in set(manifest.provider_product_addresses)
            or profile.provider_contract_address not in set(manifest.provider_contract_addresses)):
        raise ValueError("dataset capability-profile roles do not match manifest")


@retain_observation_dependencies
def _verify_execution_dependencies(execution_session, manifest: DatasetManifest, *, at_time) -> None:
    """Reconstruct each authority role with validation memo limited to this pass."""
    _verify_provider_identity_roles(execution_session, manifest)
    resolved = _load_fixed_roles(execution_session, manifest)
    checks = (
        ("provider observation", _verify_provider_observation_roles),
        ("normalized observation", _verify_normalized_observation_roles),
        ("raw schema", _verify_raw_schema_roles),
        ("normalization transform", _verify_transform_roles),
        ("dataset creation evidence", _verify_creation_roles),
        ("dataset correction", _verify_correction_roles),
    )
    for role, verify in checks:
        verify(manifest, resolved[role])
    _verify_policy_roles(execution_session, manifest)
    _verify_profile_roles(execution_session, manifest, at_time)


def _segment_row(segment: DatasetSegment, object_bytes: bytes) -> ResearchDatasetSegmentV2:
    return ResearchDatasetSegmentV2(
        owner_id=segment.owner_id, segment_address=segment.segment_address,
        canonical_bytes=segment.canonical_bytes, object_bytes=object_bytes,
        object_address=segment.object_address, byte_digest=segment.byte_digest,
        byte_length=segment.byte_length, event_start=segment.event_start,
        event_end=segment.event_end, availability_start=segment.availability_start,
        availability_end=segment.availability_end, authority_state="VERIFIED_V2",
    )


def _manifest_row(manifest: DatasetManifest) -> ResearchDatasetManifestV2:
    return ResearchDatasetManifestV2(
        owner_id=manifest.owner_id, manifest_address=manifest.manifest_address,
        canonical_bytes=manifest.canonical_bytes,
        aggregate_byte_digest=manifest.aggregate_byte_digest,
        aggregate_byte_length=manifest.aggregate_byte_length,
        segment_addresses_json=canonical_json(list(manifest.segment_addresses)),
        instrument_addresses_json=canonical_json(list(manifest.instrument_addresses)),
        fields_json=canonical_json(list(manifest.fields)),
        gaps_json=canonical_json(list(manifest.gaps)),
        dependency_addresses_json=canonical_json(_dependency_addresses(manifest)),
        event_start=manifest.event_start, event_end=manifest.event_end,
        availability_start=manifest.availability_start,
        availability_end=manifest.availability_end, authority_state="VERIFIED_V2",
    )


def load_verified_dataset_authority(
    session,
    *,
    owner_id: str,
    manifest_address: str,
    execution_session,
    at_time,
) -> VerifiedDatasetAuthority:
    """Freshly reconstruct exact rows, raw bytes, coverage, and dependencies."""
    row = session.execute(select(ResearchDatasetManifestV2).where(
        ResearchDatasetManifestV2.owner_id == owner_id,
        ResearchDatasetManifestV2.manifest_address == manifest_address,
    )).scalar_one_or_none()
    if row is None:
        raise ValueError("typed dataset manifest is not persisted for owner")
    # The model verifier is deliberately reused on reads: raw SQL or restored
    # backups cannot gain authority from copied columns alone.
    from research.domain.models import _verify_typed_dataset_manifest_row
    _verify_typed_dataset_manifest_row(row)
    manifest = DatasetManifest.from_bytes(bytes(row.canonical_bytes))
    links = session.execute(select(ResearchDatasetManifestSegmentV2).where(
        ResearchDatasetManifestSegmentV2.owner_id == owner_id,
        ResearchDatasetManifestSegmentV2.manifest_address == manifest_address,
    ).order_by(ResearchDatasetManifestSegmentV2.ordinal)).scalars().all()
    if ([link.ordinal for link in links] != list(range(len(manifest.segment_addresses)))
            or tuple(link.segment_address for link in links) != manifest.segment_addresses):
        raise ValueError("dataset manifest segment links are incomplete or reordered")
    segment_map: dict[str, tuple[DatasetSegment, bytes]] = {}
    for link in links:
        segment_row = session.execute(select(ResearchDatasetSegmentV2).where(
            ResearchDatasetSegmentV2.owner_id == owner_id,
            ResearchDatasetSegmentV2.segment_address == link.segment_address,
        )).scalar_one_or_none()
        if segment_row is None:
            raise ValueError("dataset manifest segment row is missing")
        from research.domain.models import _verify_typed_dataset_segment_row
        _verify_typed_dataset_segment_row(segment_row)
        segment = DatasetSegment.from_bytes(bytes(segment_row.canonical_bytes))
        segment_map[link.segment_address] = (segment, bytes(segment_row.object_bytes))
    ordered = verify_dataset_manifest(manifest, segment_map)
    _verify_execution_dependencies(execution_session, manifest, at_time=at_time)
    return VerifiedDatasetAuthority(
        manifest=manifest, segments=ordered,
        object_bytes=tuple(segment_map[address][1] for address in manifest.segment_addresses),
    )


def persist_verified_dataset_authority(
    session,
    *,
    manifest: DatasetManifest,
    segments: Mapping[str, tuple[DatasetSegment, bytes]],
    execution_session,
    at_time,
    failure_hook: Callable[[str], None] | None = None,
) -> VerifiedDatasetAuthority:
    """Atomically persist or converge on one exact typed dataset authority."""
    ordered = verify_dataset_manifest(manifest, segments)
    _verify_execution_dependencies(execution_session, manifest, at_time=at_time)
    existing = session.get(
        ResearchDatasetManifestV2, (manifest.owner_id, manifest.manifest_address))
    if existing is not None:
        loaded = load_verified_dataset_authority(
            session, owner_id=manifest.owner_id,
            manifest_address=manifest.manifest_address, execution_session=execution_session,
            at_time=at_time)
        if (loaded.manifest.canonical_bytes != manifest.canonical_bytes
                or loaded.object_bytes != tuple(segments[address][1]
                                                for address in manifest.segment_addresses)):
            raise ValueError("conflicting dataset authority replay")
        return loaded
    with caller_owned_savepoint(session, scope="research_dataset_authority"):
        for segment in ordered:
            object_bytes = segments[segment.segment_address][1]
            prior = session.get(ResearchDatasetSegmentV2,
                                (manifest.owner_id, segment.segment_address))
            if prior is None:
                session.add(_segment_row(segment, object_bytes))
            else:
                from research.domain.models import _verify_typed_dataset_segment_row
                _verify_typed_dataset_segment_row(prior)
                if (bytes(prior.canonical_bytes) != segment.canonical_bytes
                        or bytes(prior.object_bytes) != object_bytes):
                    raise ValueError("conflicting dataset segment replay")
            session.flush()
            if failure_hook is not None:
                failure_hook("segment")
        session.add(_manifest_row(manifest))
        session.flush()
        if failure_hook is not None:
            failure_hook("manifest")
        for ordinal, address in enumerate(manifest.segment_addresses):
            session.add(ResearchDatasetManifestSegmentV2(
                owner_id=manifest.owner_id, manifest_address=manifest.manifest_address,
                ordinal=ordinal, segment_address=address,
            ))
            session.flush()
            if failure_hook is not None:
                failure_hook("link")
    return load_verified_dataset_authority(
        session, owner_id=manifest.owner_id, manifest_address=manifest.manifest_address,
        execution_session=execution_session, at_time=at_time)
