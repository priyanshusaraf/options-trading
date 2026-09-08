from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, fields, replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import importlib.util
import sys
import time
import tracemalloc

import pytest

from app.billing.policy_contracts import (
    MAX_CANONICAL_BYTES,
    MAX_COLLECTION_ITEMS,
    MAX_IDENTIFIER_LENGTH,
    V0_EXAMPLE_BETA_TRIAL_SECONDS,
    ContractValidationError,
    CouponEffect,
    CouponPolicy,
    CouponProof,
    DecisionCandidate,
    DecisionRefusal,
    DecisionResult,
    EntitlementPolicy,
    GrantSource,
    ProfileEvidence,
    RefusalCode,
    TrialEligibilityEvidence,
    canonical_deserialize,
    evaluate_coupon,
    evaluate_founder_complimentary,
    evaluate_trial,
    v0_example_beta_trial_policy,
)


NOW = datetime(2026, 9, 1, 5, 30, tzinfo=timezone.utc)


def policy(*, duration: int = V0_EXAMPLE_BETA_TRIAL_SECONDS) -> EntitlementPolicy:
    return EntitlementPolicy(
        policy_address="policy:beta:v7",
        entitlement_set_id="set:synthetic-research",
        entitlements=("builder.read", "research.run"),
        required_profile_fields=("profile.country", "profile.full_name"),
        trial_duration_seconds=duration,
    )


def profile(*, fields: tuple[str, ...] | None = None) -> ProfileEvidence:
    return ProfileEvidence(
        policy_address="policy:beta:v7",
        owner_id="owner:synthetic-a",
        user_id="user:synthetic-a",
        evidence_address="profile-proof:7",
        satisfied_fields=fields
        if fields is not None
        else ("profile.country", "profile.full_name"),
    )


def eligibility(*, eligible: bool = True, prior_used: bool = False) -> TrialEligibilityEvidence:
    return TrialEligibilityEvidence(
        policy_address="policy:beta:v7",
        owner_id="owner:synthetic-a",
        user_id="user:synthetic-a",
        eligibility_authority_address="eligibility:server:v3",
        eligible=eligible,
        prior_use_authority_address="prior-use:server:v2",
        prior_used=prior_used,
    )


def coupon_policy(effect: CouponEffect = CouponEffect.TRIAL_ACCESS) -> CouponPolicy:
    return CouponPolicy(
        policy_address="coupon-policy:synthetic:v4",
        entitlement_policy_address="policy:beta:v7",
        verifier_address="coupon-verifier:server:v5",
        effect=effect,
        effect_policy_address="coupon-effect:trial:v4"
        if effect is CouponEffect.TRIAL_ACCESS
        else "coupon-effect:price-unavailable:v1",
    )


def coupon_proof() -> CouponProof:
    return CouponProof(
        coupon_policy_address="coupon-policy:synthetic:v4",
        verifier_address="coupon-verifier:server:v5",
        proof_address="coupon-proof:opaque:42",
        owner_id="owner:synthetic-a",
        user_id="user:synthetic-a",
    )


def all_contract_values() -> tuple[object, ...]:
    accepted = evaluate_coupon(
        policy=policy(),
        coupon_policy=coupon_policy(),
        coupon_proof=coupon_proof(),
        profile_evidence=profile(),
        eligibility_evidence=eligibility(),
        server_time=NOW,
        revocation_authority_address="revocation:server:v2",
    )
    refused = evaluate_trial(
        policy=policy(),
        profile_evidence=profile(),
        eligibility_evidence=eligibility(eligible=False),
        server_time=NOW,
        revocation_authority_address="revocation:server:v2",
    )
    assert accepted.candidate is not None
    assert refused.refusal is not None
    return (
        policy(),
        profile(),
        eligibility(),
        coupon_policy(),
        coupon_proof(),
        accepted.candidate,
        refused.refusal,
        accepted,
        refused,
    )


def test_example_trial_is_exactly_fifteen_days_and_never_activates_access() -> None:
    example = v0_example_beta_trial_policy(
        policy_address="policy:beta:v7",
        entitlement_set_id="set:synthetic-research",
        entitlements=("builder.read", "research.run"),
        required_profile_fields=("profile.country", "profile.full_name"),
    )
    result = evaluate_trial(
        policy=example,
        profile_evidence=profile(),
        eligibility_evidence=eligibility(),
        server_time=NOW,
        revocation_authority_address="revocation:server:v2",
    )

    assert example.trial_duration_seconds == 1_296_000
    assert result.candidate is not None
    assert result.refusal is None
    assert result.candidate.starts_at == NOW
    assert result.candidate.expires_at == NOW + timedelta(seconds=1_296_000)
    assert result.candidate.access_activated is False
    assert result.candidate.source is GrantSource.BETA_TRIAL


@pytest.mark.parametrize(
    ("profile_value", "eligibility_value", "code"),
    [
        (profile(fields=("profile.country",)), eligibility(), RefusalCode.MISSING_PROFILE_EVIDENCE),
        (profile(), eligibility(eligible=False), RefusalCode.TRIAL_INELIGIBLE),
        (profile(), eligibility(prior_used=True), RefusalCode.PRIOR_TRIAL_USED),
    ],
)
def test_trial_failures_are_closed_refusals_without_candidates(
    profile_value: ProfileEvidence,
    eligibility_value: TrialEligibilityEvidence,
    code: RefusalCode,
) -> None:
    result = evaluate_trial(
        policy=policy(),
        profile_evidence=profile_value,
        eligibility_evidence=eligibility_value,
        server_time=NOW,
        revocation_authority_address="revocation:server:v2",
    )
    assert result == replace(result, candidate=None)
    assert result.candidate is None
    assert result.refusal is not None
    assert result.refusal.code is code


def test_founder_complimentary_is_unpriced_unbounded_and_separately_revocable() -> None:
    result = evaluate_founder_complimentary(
        policy=policy(),
        owner_id="owner:synthetic-founder",
        user_id="user:synthetic-founder",
        server_time=NOW,
        binding_address="founder-binding:server:v3",
        revocation_authority_address="founder-revocation:server:v2",
    )
    candidate = result.candidate
    assert candidate is not None
    assert candidate.source is GrantSource.FOUNDER_COMPLIMENTARY
    assert candidate.expires_at is None
    assert candidate.source_authority_address == "founder-binding:server:v3"
    assert candidate.revocation_authority_address == "founder-revocation:server:v2"
    assert candidate.access_activated is False
    payload = candidate.canonical_json()
    for forbidden in ("email", "operator", "payment", "merchant", "provider", "coupon", "price"):
        assert forbidden not in payload.lower()


@pytest.mark.parametrize(
    ("binding", "revocation", "code"),
    [
        (None, "founder-revocation:server:v2", RefusalCode.FOUNDER_BINDING_REQUIRED),
        ("founder-binding:server:v3", None, RefusalCode.REVOCATION_AUTHORITY_REQUIRED),
    ],
)
def test_founder_missing_authorities_fail_closed(
    binding: str | None, revocation: str | None, code: RefusalCode
) -> None:
    result = evaluate_founder_complimentary(
        policy=policy(),
        owner_id="owner:synthetic-founder",
        user_id="user:synthetic-founder",
        server_time=NOW,
        binding_address=binding,
        revocation_authority_address=revocation,
    )
    assert result.candidate is None
    assert result.refusal is not None
    assert result.refusal.code is code


def test_coupon_trial_requires_server_proof_and_matching_addresses() -> None:
    missing = evaluate_coupon(
        policy=policy(),
        coupon_policy=coupon_policy(),
        coupon_proof=None,
        profile_evidence=profile(),
        eligibility_evidence=eligibility(),
        server_time=NOW,
        revocation_authority_address="revocation:server:v2",
    )
    assert missing.candidate is None
    assert missing.refusal is not None
    assert missing.refusal.code is RefusalCode.COUPON_PROOF_REQUIRED

    substituted = evaluate_coupon(
        policy=policy(),
        coupon_policy=coupon_policy(),
        coupon_proof=replace(coupon_proof(), verifier_address="coupon-verifier:other:v1"),
        profile_evidence=profile(),
        eligibility_evidence=eligibility(),
        server_time=NOW,
        revocation_authority_address="revocation:server:v2",
    )
    assert substituted.candidate is None
    assert substituted.refusal is not None
    assert substituted.refusal.code is RefusalCode.COUPON_PROOF_MISMATCH

    accepted = evaluate_coupon(
        policy=policy(),
        coupon_policy=coupon_policy(),
        coupon_proof=coupon_proof(),
        profile_evidence=profile(),
        eligibility_evidence=eligibility(),
        server_time=NOW,
        revocation_authority_address="revocation:server:v2",
    )
    assert accepted.candidate is not None
    assert accepted.candidate.source is GrantSource.COUPON_TRIAL_ACCESS
    assert accepted.candidate.access_activated is False


def test_coupon_price_adjustment_is_explicitly_unavailable_without_money_catalogue() -> None:
    result = evaluate_coupon(
        policy=policy(),
        coupon_policy=coupon_policy(CouponEffect.PRICE_ADJUSTMENT),
        coupon_proof=coupon_proof(),
        profile_evidence=profile(),
        eligibility_evidence=eligibility(),
        server_time=NOW,
        revocation_authority_address="revocation:server:v2",
    )
    assert result.candidate is None
    assert result.refusal is not None
    assert result.refusal.code is RefusalCode.PRICE_ADJUSTMENT_UNAVAILABLE


def test_all_contracts_are_frozen_canonical_and_restart_roundtrip() -> None:
    for value in all_contract_values():
        encoded = value.canonical_json()
        assert type(json.loads(encoded)["contract_version"]) is int
        restored = canonical_deserialize(encoded)
        assert restored == value
        assert restored.content_id == value.content_id
        assert restored.canonical_json() == encoded
        with pytest.raises(FrozenInstanceError):
            setattr(value, fields(value)[0].name, None)


@pytest.mark.parametrize("bad_version", [True, False, 1.0, "1", 0, 2])
def test_root_contract_versions_require_exact_builtin_int_one(bad_version: object) -> None:
    for value in all_contract_values():
        raw = value.canonical_dict()
        raw["contract_version"] = bad_version
        encoded = json.dumps(raw, sort_keys=True, separators=(",", ":"))
        with pytest.raises(ContractValidationError):
            canonical_deserialize(encoded)


@pytest.mark.parametrize("bad_version", [True, False, 1.0, "1", 0, 2])
def test_nested_contract_versions_require_exact_builtin_int_one(bad_version: object) -> None:
    accepted = all_contract_values()[-2]
    accepted_raw = accepted.canonical_dict()
    accepted_raw["candidate"]["contract_version"] = bad_version
    accepted_encoded = json.dumps(accepted_raw, sort_keys=True, separators=(",", ":"))
    with pytest.raises(ContractValidationError):
        canonical_deserialize(accepted_encoded)

    refused = all_contract_values()[-1]
    refused_raw = refused.canonical_dict()
    refused_raw["refusal"]["contract_version"] = bad_version
    refused_encoded = json.dumps(refused_raw, sort_keys=True, separators=(",", ":"))
    with pytest.raises(ContractValidationError):
        canonical_deserialize(refused_encoded)


@pytest.mark.parametrize(
    ("change",),
    [
        (lambda c: replace(c, owner_id="owner:synthetic-b"),),
        (lambda c: replace(c, user_id="user:synthetic-b"),),
        (lambda c: replace(c, policy_address="policy:beta:v8"),),
        (lambda c: replace(c, entitlement_set_id="set:synthetic-other"),),
        (lambda c: replace(c, starts_at=NOW + timedelta(seconds=1)),),
        (lambda c: replace(c, expires_at=NOW + timedelta(seconds=1_296_001)),),
        (lambda c: replace(c, source_authority_address="eligibility:server:v4"),),
        (lambda c: replace(c, revocation_authority_address="revocation:server:v3"),),
        (lambda c: replace(c, decision_basis_address="sha256:" + "1" * 64),),
        (lambda c: replace(c, source=GrantSource.COUPON_TRIAL_ACCESS),),
    ],
)
def test_candidate_identity_changes_for_every_answer_field(change) -> None:
    original = evaluate_trial(
        policy=policy(),
        profile_evidence=profile(),
        eligibility_evidence=eligibility(),
        server_time=NOW,
        revocation_authority_address="revocation:server:v2",
    ).candidate
    assert original is not None
    assert change(original).content_id != original.content_id


def test_policy_and_evidence_identity_changes_for_profile_proof_and_entitlements() -> None:
    pairs = [
        (policy(), replace(policy(), entitlements=("builder.read", "research.export"))),
        (policy(), replace(policy(), required_profile_fields=("profile.country",))),
        (profile(), replace(profile(), evidence_address="profile-proof:8")),
        (coupon_proof(), replace(coupon_proof(), proof_address="coupon-proof:opaque:43")),
        (coupon_policy(), replace(coupon_policy(), effect_policy_address="coupon-effect:trial:v5")),
    ]
    for left, right in pairs:
        assert left.content_id != right.content_id


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "UPPERCASE",
        "with space",
        "../escape",
        "x" * (MAX_IDENTIFIER_LENGTH + 1),
    ],
)
def test_identifiers_are_closed_and_bounded(bad: str) -> None:
    with pytest.raises(ContractValidationError):
        replace(policy(), policy_address=bad)


def test_collections_must_be_sorted_unique_nonempty_and_bounded() -> None:
    for values in [(), ("z", "a"), ("a", "a")]:
        with pytest.raises(ContractValidationError):
            replace(policy(), entitlements=values)
    too_many = tuple(f"entitlement.{index:03d}" for index in range(MAX_COLLECTION_ITEMS + 1))
    with pytest.raises(ContractValidationError):
        replace(policy(), entitlements=too_many)


def test_utc_and_time_overflow_are_rejected() -> None:
    with pytest.raises(ContractValidationError):
        evaluate_trial(
            policy=policy(),
            profile_evidence=profile(),
            eligibility_evidence=eligibility(),
            server_time=datetime(2026, 9, 1),
            revocation_authority_address="revocation:server:v2",
        )
    with pytest.raises(ContractValidationError):
        evaluate_trial(
            policy=policy(duration=315_360_000),
            profile_evidence=profile(),
            eligibility_evidence=eligibility(),
            server_time=datetime(9998, 1, 1, tzinfo=timezone.utc),
            revocation_authority_address="revocation:server:v2",
        )


def test_unknown_extra_open_type_depth_and_size_are_refused() -> None:
    raw = json.loads(policy().canonical_json())
    raw["unexpected"] = True
    with pytest.raises(ContractValidationError):
        canonical_deserialize(json.dumps(raw))
    raw.pop("unexpected")
    raw["contract_type"] = "OpenFuturePolicy"
    with pytest.raises(ContractValidationError):
        canonical_deserialize(json.dumps(raw))
    nested = json.loads(
        evaluate_trial(
            policy=policy(),
            profile_evidence=profile(),
            eligibility_evidence=eligibility(),
            server_time=NOW,
            revocation_authority_address="revocation:server:v2",
        ).canonical_json()
    )
    nested["candidate"]["contract_type"] = "DecisionRefusal"
    with pytest.raises(ContractValidationError):
        canonical_deserialize(json.dumps(nested, sort_keys=True, separators=(",", ":")))
    with pytest.raises(ContractValidationError):
        canonical_deserialize("[" * 20 + "]" * 20)
    with pytest.raises(ContractValidationError):
        canonical_deserialize(" " * (MAX_CANONICAL_BYTES + 1))


def test_cross_policy_owner_and_user_substitution_is_rejected() -> None:
    with pytest.raises(ContractValidationError):
        evaluate_trial(
            policy=policy(),
            profile_evidence=replace(profile(), owner_id="owner:other"),
            eligibility_evidence=eligibility(),
            server_time=NOW,
            revocation_authority_address="revocation:server:v2",
        )
    substituted = evaluate_coupon(
        policy=policy(),
        coupon_policy=coupon_policy(),
        coupon_proof=replace(coupon_proof(), user_id="user:other"),
        profile_evidence=profile(),
        eligibility_evidence=eligibility(),
        server_time=NOW,
        revocation_authority_address="revocation:server:v2",
    )
    assert substituted.candidate is None
    assert substituted.refusal is not None
    assert substituted.refusal.code is RefusalCode.COUPON_PROOF_MISMATCH


def test_source_and_ast_guard_pure_unpublished_boundary() -> None:
    source_path = Path(__file__).parents[1] / "app" / "billing" / "policy_contracts.py"
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add((node.module or "").split(".")[0])
    imports.discard("__future__")
    assert imports <= {"dataclasses", "datetime", "enum", "hashlib", "json", "re", "typing"}
    forbidden = (
        "app.db",
        "app.api",
        "app.providers",
        "app.execution",
        "app.ledger",
        "app.monitoring",
        "os.environ",
        "getenv",
        "email",
        "razorpay",
    )
    lowered = source.lower()
    for token in forbidden:
        assert token not in lowered
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for argument in (*node.args.args, *node.args.kwonlyargs):
                if argument.arg == "trial_duration_seconds":
                    defaults = node.args.defaults + node.args.kw_defaults
                    assert not any(
                        isinstance(default, ast.Constant) and default.value == 1_296_000
                        for default in defaults
                        if default is not None
                    )


def test_100k_deterministic_decisions_with_declared_resource_bounds() -> None:
    fixed_policy = policy()
    fixed_profile = profile()
    fixed_eligibility = eligibility()
    expected = evaluate_trial(
        policy=fixed_policy,
        profile_evidence=fixed_profile,
        eligibility_evidence=fixed_eligibility,
        server_time=NOW,
        revocation_authority_address="revocation:server:v2",
    ).content_id
    tracemalloc.start()
    started = time.perf_counter()
    for _ in range(100_000):
        result = evaluate_trial(
            policy=fixed_policy,
            profile_evidence=fixed_profile,
            eligibility_evidence=fixed_eligibility,
            server_time=NOW,
            revocation_authority_address="revocation:server:v2",
        )
        assert result.content_id == expected
    elapsed = time.perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    print(f"resource_receipt decisions=100000 elapsed_seconds={elapsed:.6f} peak_bytes={peak}")
    assert elapsed < 30.0
    assert peak < 32 * 1024 * 1024


@pytest.mark.parametrize(
    ("old", "new", "oracle"),
    [
        (
            "if binding_address is None:",
            "if False:  # mutation: founder binding bypass",
            "founder_binding",
        ),
        (
            "if not set(policy.required_profile_fields).issubset(profile.satisfied_fields):",
            "if False:  # mutation: missing profile bypass",
            "missing_profile",
        ),
        (
            "if coupon_proof is None:",
            "if False:  # mutation: coupon proof omission",
            "coupon_omission",
        ),
        (
            "if coupon_policy.effect is CouponEffect.PRICE_ADJUSTMENT:",
            "if False:  # mutation: adjustment activation",
            "adjustment_activation",
        ),
        (
            "access_activated=False,",
            "access_activated=True,  # mutation: activation flip",
            "activation_flip",
        ),
        (
            "return type(value) is int and value == CONTRACT_VERSION",
            "return value == CONTRACT_VERSION  # mutation: permissive version equality",
            "version_type",
        ),
    ],
)
def test_isolated_safety_mutations_are_killed(
    tmp_path: Path, old: str, new: str, oracle: str
) -> None:
    source_path = Path(__file__).parents[1] / "app" / "billing" / "policy_contracts.py"
    source = source_path.read_text(encoding="utf-8")
    assert source.count(old) == 1
    mutated = source.replace(old, new, 1)
    module_name = f"policy_contracts_mutant_{oracle}"
    mutant_path = tmp_path / f"{module_name}.py"
    mutant_path.write_text(mutated, encoding="utf-8")
    spec = importlib.util.spec_from_file_location(module_name, mutant_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
        mutant_policy = module.EntitlementPolicy(
            policy_address="policy:beta:v7",
            entitlement_set_id="set:synthetic-research",
            entitlements=("builder.read", "research.run"),
            required_profile_fields=("profile.country", "profile.full_name"),
            trial_duration_seconds=1_296_000,
        )
        mutant_profile = module.ProfileEvidence(
            policy_address="policy:beta:v7",
            owner_id="owner:synthetic-a",
            user_id="user:synthetic-a",
            evidence_address="profile-proof:7",
            satisfied_fields=("profile.country", "profile.full_name"),
        )
        mutant_eligibility = module.TrialEligibilityEvidence(
            policy_address="policy:beta:v7",
            owner_id="owner:synthetic-a",
            user_id="user:synthetic-a",
            eligibility_authority_address="eligibility:server:v3",
            eligible=True,
            prior_use_authority_address="prior-use:server:v2",
            prior_used=False,
        )
        if oracle == "version_type":
            version_payload = mutant_policy.canonical_dict()
            version_payload["contract_version"] = True
            version_raw = json.dumps(
                version_payload, sort_keys=True, separators=(",", ":")
            )
            try:
                module.canonical_deserialize(version_raw)
            except module.ContractValidationError:
                survived = True
            else:
                survived = False
        elif oracle == "founder_binding":
            try:
                outcome = module.evaluate_founder_complimentary(
                    policy=mutant_policy,
                    owner_id="owner:synthetic-founder",
                    user_id="user:synthetic-founder",
                    server_time=NOW,
                    binding_address=None,
                    revocation_authority_address="founder-revocation:server:v2",
                )
            except module.ContractValidationError:
                survived = False
            else:
                survived = (
                    outcome.candidate is None
                    and outcome.refusal.code is module.RefusalCode.FOUNDER_BINDING_REQUIRED
                )
        elif oracle == "missing_profile":
            outcome = module.evaluate_trial(
                policy=mutant_policy,
                profile_evidence=replace(
                    mutant_profile, satisfied_fields=("profile.country",)
                ),
                eligibility_evidence=mutant_eligibility,
                server_time=NOW,
                revocation_authority_address="revocation:server:v2",
            )
            survived = (
                outcome.candidate is None
                and outcome.refusal.code is module.RefusalCode.MISSING_PROFILE_EVIDENCE
            )
        else:
            effect = (
                module.CouponEffect.PRICE_ADJUSTMENT
                if oracle == "adjustment_activation"
                else module.CouponEffect.TRIAL_ACCESS
            )
            mutant_coupon_policy = module.CouponPolicy(
                policy_address="coupon-policy:synthetic:v4",
                entitlement_policy_address="policy:beta:v7",
                verifier_address="coupon-verifier:server:v5",
                effect=effect,
                effect_policy_address="coupon-effect:synthetic:v1",
            )
            mutant_proof = None
            if oracle != "coupon_omission":
                mutant_proof = module.CouponProof(
                    coupon_policy_address="coupon-policy:synthetic:v4",
                    verifier_address="coupon-verifier:server:v5",
                    proof_address="coupon-proof:opaque:42",
                    owner_id="owner:synthetic-a",
                    user_id="user:synthetic-a",
                )
            try:
                outcome = module.evaluate_coupon(
                    policy=mutant_policy,
                    coupon_policy=mutant_coupon_policy,
                    coupon_proof=mutant_proof,
                    profile_evidence=mutant_profile,
                    eligibility_evidence=mutant_eligibility,
                    server_time=NOW,
                    revocation_authority_address="revocation:server:v2",
                )
            except module.ContractValidationError:
                survived = False
            else:
                if oracle == "coupon_omission":
                    survived = (
                        outcome.candidate is None
                        and outcome.refusal.code is module.RefusalCode.COUPON_PROOF_REQUIRED
                    )
                elif oracle == "adjustment_activation":
                    survived = (
                        outcome.candidate is None
                        and outcome.refusal.code
                        is module.RefusalCode.PRICE_ADJUSTMENT_UNAVAILABLE
                    )
                else:
                    survived = outcome.candidate is not None and not outcome.candidate.access_activated
        assert survived is False, f"safety mutation survived: {oracle}"
    finally:
        sys.modules.pop(module_name, None)


def test_decision_result_rejects_candidate_and_refusal_or_neither() -> None:
    accepted = evaluate_trial(
        policy=policy(),
        profile_evidence=profile(),
        eligibility_evidence=eligibility(),
        server_time=NOW,
        revocation_authority_address="revocation:server:v2",
    )
    assert accepted.candidate is not None
    refusal = DecisionRefusal(
        code=RefusalCode.TRIAL_INELIGIBLE,
        source=GrantSource.BETA_TRIAL,
        policy_address="policy:beta:v7",
        owner_id="owner:synthetic-a",
        user_id="user:synthetic-a",
        evaluated_at=NOW,
        decision_basis_address="sha256:" + "2" * 64,
    )
    with pytest.raises(ContractValidationError):
        DecisionResult(candidate=accepted.candidate, refusal=refusal)
    with pytest.raises(ContractValidationError):
        DecisionResult(candidate=None, refusal=None)


def test_access_activation_cannot_be_constructed_true() -> None:
    accepted = evaluate_trial(
        policy=policy(),
        profile_evidence=profile(),
        eligibility_evidence=eligibility(),
        server_time=NOW,
        revocation_authority_address="revocation:server:v2",
    )
    assert accepted.candidate is not None
    with pytest.raises(ContractValidationError):
        replace(accepted.candidate, access_activated=True)
