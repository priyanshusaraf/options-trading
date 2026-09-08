"""Unpublished account-to-INTERNAL-access service with no provider or API seam."""
from __future__ import annotations

import datetime as dt
import hashlib
from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.api.principal import Principal
from app.billing.policy_contracts import (
    CouponEffect,
    CouponPolicy,
    CouponProof,
    EntitlementPolicy,
    ProfileEvidence,
    TrialEligibilityEvidence,
    V0_EXAMPLE_BETA_TRIAL_SECONDS,
    evaluate_coupon,
    evaluate_founder_complimentary,
    evaluate_trial,
)
from app.db.models import (
    PlatformComplimentaryEntitlementGrantRow,
    PlatformCouponDefinitionRow,
    PlatformCouponRedemptionRow,
    PlatformEntitlementEventRow,
)
from app.platform_operations.contracts import (
    BillingMode,
    EntitlementEffectTiming,
    EntitlementSource,
    EntitlementState,
    EntitlementTransition,
    GrantAction,
    OperatorAuthority,
    TenantAuthority,
    MembershipState,
    address,
)
from app.platform_operations.repository import PlatformOperationsRepository

from .repository import (
    AccountAuthority,
    AccountCommerceConflict,
    AccountCommerceRefused,
    AccountCommerceRepository,
    StoredProfileEvidence,
)


PRODUCT_ACCESS = "PRODUCT_ACCESS"
POLICY_PRODUCT_ACCESS = "product.access"


def _stable_ref(prefix: str, *parts: str) -> str:
    material = "\x1f".join(parts).encode("utf-8")
    return f"{prefix}." + hashlib.sha256(material).hexdigest()


@dataclass(frozen=True, slots=True)
class ServerProfileAttestation:
    """Injected server result; raw profile values are intentionally unrepresentable."""

    evidence_address: str
    satisfied_field_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AccessStatus:
    owner_ref: str
    state: str
    source_event_id: str | None
    valid_until: dt.datetime | None


@dataclass(frozen=True, slots=True)
class AccessGrant:
    owner_ref: str
    source_kind: str
    source_ref: str
    entitlement_event_id: str
    valid_until: dt.datetime | None
    access_active: bool


@dataclass(frozen=True, slots=True)
class ProfileStatus:
    satisfied_field_codes: tuple[str, ...]
    attested_at: dt.datetime | None
    replayed: bool = False


@dataclass(frozen=True, slots=True)
class AccountStatus:
    profile: ProfileStatus
    trial_source: str | None
    trial_valid_until: dt.datetime | None
    access: AccessStatus


class AccountCommerceService:
    """Derive ordinary product access from exact account and source facts."""

    def __init__(self, session: Session, *, principal: Principal | None,
                 policy: EntitlementPolicy):
        self.session = session
        self.principal = principal
        if not isinstance(policy, EntitlementPolicy):
            raise AccountCommerceRefused("current entitlement policy required")
        if policy.trial_duration_seconds != V0_EXAMPLE_BETA_TRIAL_SECONDS:
            raise AccountCommerceRefused("V0 trial policy must be exactly 15 days")
        if POLICY_PRODUCT_ACCESS not in policy.entitlements:
            raise AccountCommerceRefused("policy does not contain PRODUCT_ACCESS")
        address(policy.policy_address, "entitlement policy")
        self.policy = policy

    def _begin(self):
        if self.session.in_transaction():
            raise AccountCommerceRefused("account-commerce service requires a clean transaction")
        return self.session.begin()

    def _authority(self, repository: AccountCommerceRepository,
                   server_time: dt.datetime) -> AccountAuthority:
        return repository.resolve_authority(self.principal, server_time=server_time)

    @staticmethod
    def _tenant(authority: AccountAuthority) -> TenantAuthority:
        return TenantAuthority(
            authority.owner_ref, authority.principal_ref, MembershipState.ACTIVE
        )

    @staticmethod
    def _access_active_at(current, server_time: dt.datetime) -> bool:
        return (
            current.state is EntitlementState.ACTIVE
            and (current.valid_until is None or server_time < current.valid_until)
        )

    def _profile(
        self,
        repository: AccountCommerceRepository,
        authority: AccountAuthority,
        attestation: ServerProfileAttestation,
        server_time: dt.datetime,
    ) -> StoredProfileEvidence:
        if not isinstance(attestation, ServerProfileAttestation):
            raise AccountCommerceRefused("server profile attestation required")
        return repository.record_profile_evidence(
            authority=authority,
            policy_address=self.policy.policy_address,
            evidence_address=attestation.evidence_address,
            satisfied_fields=attestation.satisfied_field_codes,
            required_fields=self.policy.required_profile_fields,
            attested_at=server_time,
        )

    def _profile_contract(self, profile: StoredProfileEvidence) -> ProfileEvidence:
        return ProfileEvidence(
            policy_address=self.policy.policy_address,
            owner_id=profile.owner_ref,
            user_id=profile.user_ref,
            evidence_address=profile.evidence_address,
            satisfied_fields=profile.satisfied_fields,
        )

    def validate_browser(self, *, server_time: dt.datetime) -> None:
        """Prove current durable browser authority before transient resolvers run."""
        with self._begin():
            self._authority(AccountCommerceRepository(self.session), server_time)

    def record_profile(
        self, *, attestation: ServerProfileAttestation,
        server_time: dt.datetime,
    ) -> ProfileStatus:
        with self._begin():
            repository = AccountCommerceRepository(self.session)
            authority = self._authority(repository, server_time)
            existing = repository.profile_evidence(
                authority=authority,
                policy_address=self.policy.policy_address,
                evidence_address=attestation.evidence_address,
            )
            profile = self._profile(repository, authority, attestation, server_time)
            return ProfileStatus(
                profile.satisfied_fields, profile.attested_at, existing is not None
            )

    def current_status(self, *, server_time: dt.datetime) -> AccountStatus:
        with self._begin():
            repository = AccountCommerceRepository(self.session)
            authority = self._authority(repository, server_time)
            profile = repository.profile_evidence(
                authority=authority, policy_address=self.policy.policy_address
            )
            trial = repository.trial_use(
                authority=authority, policy_address=self.policy.policy_address
            )
            current = PlatformOperationsRepository(
                self.session, tenant=self._tenant(authority)
            ).current_entitlement(PRODUCT_ACCESS, BillingMode.INTERNAL)
            state = current.state.value
            if current.state is EntitlementState.ACTIVE and not self._access_active_at(
                current, server_time
            ):
                state = "EXPIRED"
            return AccountStatus(
                ProfileStatus(
                    () if profile is None else profile.satisfied_fields,
                    None if profile is None else profile.attested_at,
                ),
                None if trial is None else trial.source_kind,
                None if trial is None else trial.valid_until,
                AccessStatus(
                    authority.owner_ref, state, current.source_event_id,
                    current.valid_until,
                ),
            )

    def _eligibility(
        self,
        *,
        authority: AccountAuthority,
        eligibility_authority_address: str,
        prior_use_authority_address: str,
        eligible: bool,
        prior_used: bool,
    ) -> TrialEligibilityEvidence:
        address(eligibility_authority_address, "eligibility authority")
        address(prior_use_authority_address, "prior-use authority")
        return TrialEligibilityEvidence(
            policy_address=self.policy.policy_address,
            owner_id=authority.owner_ref,
            user_id=authority.user_ref,
            eligibility_authority_address=eligibility_authority_address,
            eligible=eligible,
            prior_use_authority_address=prior_use_authority_address,
            prior_used=prior_used,
        )

    def grant_beta_trial(
        self,
        *,
        attestation: ServerProfileAttestation,
        eligibility_authority_address: str,
        prior_use_authority_address: str,
        revocation_authority_address: str,
        eligible: bool,
        server_time: dt.datetime,
    ) -> AccessGrant:
        with self._begin():
            repository = AccountCommerceRepository(self.session)
            authority = self._authority(repository, server_time)
            prior = repository.trial_use(
                authority=authority, policy_address=self.policy.policy_address
            )
            if prior is not None:
                if prior.source_kind != EntitlementSource.BETA_TRIAL.value:
                    raise AccountCommerceConflict("trial already used by another source")
                return self._existing_trial_grant(
                    authority, prior, server_time=server_time
                )
            profile = self._profile(repository, authority, attestation, server_time)
            eligibility = self._eligibility(
                authority=authority,
                eligibility_authority_address=eligibility_authority_address,
                prior_use_authority_address=prior_use_authority_address,
                eligible=eligible,
                prior_used=False,
            )
            result = evaluate_trial(
                policy=self.policy,
                profile_evidence=self._profile_contract(profile),
                eligibility_evidence=eligibility,
                server_time=server_time,
                revocation_authority_address=revocation_authority_address,
            )
            if result.candidate is None:
                raise AccountCommerceRefused(result.refusal.code.value)
            candidate = result.candidate
            trial_id = repository.trial_id_for(authority, self.policy.policy_address)
            event_id = _stable_ref("entitlement", EntitlementSource.BETA_TRIAL.value, trial_id)
            trial = repository.record_trial_use(
                authority=authority,
                profile=profile,
                policy_address=self.policy.policy_address,
                source_kind=EntitlementSource.BETA_TRIAL.value,
                source_ref=trial_id,
                eligibility_authority_address=eligibility_authority_address,
                prior_use_authority_address=prior_use_authority_address,
                decision_basis_address=candidate.decision_basis_address,
                entitlement_code=PRODUCT_ACCESS,
                entitlement_event_id=event_id,
                valid_from=candidate.starts_at,
                valid_until=candidate.expires_at,
                used_at=server_time,
            )
            current = PlatformOperationsRepository(
                self.session, tenant=self._tenant(authority)
            ).append_entitlement_event(
                event_id=event_id,
                entitlement_code=PRODUCT_ACCESS,
                mode=BillingMode.INTERNAL,
                source_kind=EntitlementSource.BETA_TRIAL,
                source_ref=trial.trial_use_id,
                transition=EntitlementTransition.GRANT,
                policy_address=self.policy.policy_address,
                valid_from=candidate.starts_at,
                valid_until=candidate.expires_at,
                effective_at=candidate.starts_at,
                recorded_at=server_time,
            )
            return AccessGrant(
                authority.owner_ref, EntitlementSource.BETA_TRIAL.value,
                trial.trial_use_id, event_id, candidate.expires_at,
                current.state is EntitlementState.ACTIVE,
            )

    def grant_coupon_trial(
        self,
        *,
        coupon_plaintext: str,
        coupon_policy: CouponPolicy,
        coupon_proof_address: str,
        attestation: ServerProfileAttestation,
        eligibility_authority_address: str,
        prior_use_authority_address: str,
        revocation_authority_address: str,
        eligible: bool,
        server_time: dt.datetime,
    ) -> AccessGrant:
        if (not isinstance(coupon_plaintext, str)
                or not 1 <= len(coupon_plaintext.encode("utf-8")) <= 256):
            raise AccountCommerceRefused("coupon secret required")
        if not isinstance(coupon_policy, CouponPolicy):
            raise AccountCommerceRefused("current coupon policy required")
        coupon_digest = hashlib.sha256(coupon_plaintext.encode("utf-8")).hexdigest()
        with self._begin():
            repository = AccountCommerceRepository(self.session)
            authority = self._authority(repository, server_time)
            prior = repository.trial_use(
                authority=authority, policy_address=self.policy.policy_address
            )
            if prior is not None:
                if prior.source_kind != EntitlementSource.COUPON_REDEMPTION.value:
                    raise AccountCommerceConflict("trial already used by another source")
                redemption = self.session.get(PlatformCouponRedemptionRow, prior.source_ref)
                definition = None if redemption is None else self.session.get(
                    PlatformCouponDefinitionRow, redemption.coupon_id
                )
                if definition is None or definition.coupon_digest != coupon_digest:
                    raise AccountCommerceConflict("trial already used by another coupon")
                return self._existing_trial_grant(
                    authority, prior, server_time=server_time
                )
            profile = self._profile(repository, authority, attestation, server_time)
            eligibility = self._eligibility(
                authority=authority,
                eligibility_authority_address=eligibility_authority_address,
                prior_use_authority_address=prior_use_authority_address,
                eligible=eligible,
                prior_used=False,
            )
            proof = CouponProof(
                coupon_policy_address=coupon_policy.policy_address,
                verifier_address=coupon_policy.verifier_address,
                proof_address=coupon_proof_address,
                owner_id=authority.owner_ref,
                user_id=authority.user_ref,
            )
            result = evaluate_coupon(
                policy=self.policy,
                coupon_policy=coupon_policy,
                coupon_proof=proof,
                profile_evidence=self._profile_contract(profile),
                eligibility_evidence=eligibility,
                server_time=server_time,
                revocation_authority_address=revocation_authority_address,
            )
            if result.candidate is None:
                raise AccountCommerceRefused(result.refusal.code.value)
            candidate = result.candidate
            definition = self.session.scalar(sa.select(PlatformCouponDefinitionRow).where(
                PlatformCouponDefinitionRow.coupon_digest == coupon_digest
            ))
            if (
                definition is None
                or coupon_policy.effect is not CouponEffect.TRIAL_ACCESS
                or definition.policy_address != coupon_policy.policy_address
                or definition.trial_policy_address != self.policy.policy_address
                or definition.discount_policy_address is not None
                or definition.entitlement_code != PRODUCT_ACCESS
                or definition.entitlement_transition != EntitlementTransition.GRANT.value
                or definition.entitlement_effect_timing
                != EntitlementEffectTiming.DYNAMIC_DURATION.value
                or definition.entitlement_duration_seconds
                != V0_EXAMPLE_BETA_TRIAL_SECONDS
                or definition.entitlement_valid_from is not None
                or definition.entitlement_valid_until is not None
            ):
                raise AccountCommerceRefused("coupon policy does not exactly match trial access")
            redemption_id = _stable_ref(
                "redemption", definition.coupon_id, authority.owner_ref,
                self.policy.policy_address,
            )
            event_id = _stable_ref(
                "entitlement", EntitlementSource.COUPON_REDEMPTION.value, redemption_id
            )
            operations = PlatformOperationsRepository(
                self.session, tenant=self._tenant(authority)
            )
            redemption = operations.redeem_coupon(
                coupon_digest=coupon_digest,
                redemption_id=redemption_id,
                policy_address=coupon_policy.policy_address,
                redeemed_at=server_time,
            )
            trial = repository.record_trial_use(
                authority=authority,
                profile=profile,
                policy_address=self.policy.policy_address,
                source_kind=EntitlementSource.COUPON_REDEMPTION.value,
                source_ref=redemption.redemption_id,
                eligibility_authority_address=eligibility_authority_address,
                prior_use_authority_address=prior_use_authority_address,
                decision_basis_address=candidate.decision_basis_address,
                entitlement_code=PRODUCT_ACCESS,
                entitlement_event_id=event_id,
                valid_from=redemption.entitlement_valid_from,
                valid_until=redemption.entitlement_valid_until,
                used_at=server_time,
            )
            current = operations.append_entitlement_event(
                event_id=event_id,
                entitlement_code=PRODUCT_ACCESS,
                mode=BillingMode.INTERNAL,
                source_kind=EntitlementSource.COUPON_REDEMPTION,
                source_ref=redemption.redemption_id,
                transition=EntitlementTransition.GRANT,
                policy_address=coupon_policy.policy_address,
                valid_from=redemption.entitlement_valid_from,
                valid_until=redemption.entitlement_valid_until,
                effective_at=redemption.entitlement_valid_from,
                recorded_at=server_time,
            )
            return AccessGrant(
                authority.owner_ref, EntitlementSource.COUPON_REDEMPTION.value,
                trial.source_ref, event_id, redemption.entitlement_valid_until,
                current.state is EntitlementState.ACTIVE,
            )

    def grant_founder_access(
        self,
        *,
        operator: OperatorAuthority,
        revocation_authority_address: str,
        server_time: dt.datetime,
    ) -> AccessGrant:
        if not isinstance(operator, OperatorAuthority):
            raise AccountCommerceRefused("current operator authority required")
        with self._begin():
            repository = AccountCommerceRepository(self.session)
            authority = self._authority(repository, server_time)
            operations = PlatformOperationsRepository(
                self.session, tenant=self._tenant(authority), operator=operator
            )
            operations._operator_row()
            result = evaluate_founder_complimentary(
                policy=self.policy,
                owner_id=authority.owner_ref,
                user_id=authority.user_ref,
                server_time=server_time,
                binding_address=operator.binding_id,
                revocation_authority_address=revocation_authority_address,
            )
            if result.candidate is None:
                raise AccountCommerceRefused(result.refusal.code.value)
            candidate = result.candidate
            grant_id = _stable_ref(
                "grant", "founder", authority.owner_ref, self.policy.policy_address
            )
            event_id = _stable_ref(
                "entitlement", EntitlementSource.COMPLIMENTARY_GRANT.value, grant_id
            )
            existing = self.session.get(PlatformComplimentaryEntitlementGrantRow, grant_id)
            if existing is None:
                operations.add_complimentary_grant(
                    grant_id=grant_id,
                    owner_ref=authority.owner_ref,
                    entitlement_code=PRODUCT_ACCESS,
                    action=GrantAction.GRANT,
                    policy_address=self.policy.policy_address,
                    valid_from=candidate.starts_at,
                    valid_until=None,
                    created_at=server_time,
                )
            else:
                expected = (
                    authority.owner_ref, PRODUCT_ACCESS, GrantAction.GRANT.value,
                    self.policy.policy_address, None, operator.binding_id,
                )
                actual = (
                    existing.owner_ref, existing.entitlement_code, existing.action,
                    existing.policy_address, existing.valid_until, existing.operator_binding_id,
                )
                if actual != expected:
                    raise AccountCommerceConflict("founder complimentary grant conflicts")
            event = self.session.get(PlatformEntitlementEventRow, event_id)
            if event is None:
                current = operations.append_entitlement_event(
                    event_id=event_id,
                    entitlement_code=PRODUCT_ACCESS,
                    mode=BillingMode.INTERNAL,
                    source_kind=EntitlementSource.COMPLIMENTARY_GRANT,
                    source_ref=grant_id,
                    transition=EntitlementTransition.GRANT,
                    policy_address=self.policy.policy_address,
                    valid_from=candidate.starts_at,
                    valid_until=None,
                    effective_at=candidate.starts_at,
                    recorded_at=server_time,
                )
            else:
                if (
                    event.owner_ref != authority.owner_ref
                    or event.entitlement_code != PRODUCT_ACCESS
                    or event.mode != BillingMode.INTERNAL.value
                    or event.source_kind != EntitlementSource.COMPLIMENTARY_GRANT.value
                    or event.source_ref != grant_id
                    or event.transition != EntitlementTransition.GRANT.value
                    or event.policy_address != self.policy.policy_address
                    or event.valid_until is not None
                ):
                    raise AccountCommerceConflict("founder entitlement event conflicts")
                current = operations.current_entitlement(PRODUCT_ACCESS, BillingMode.INTERNAL)
            return AccessGrant(
                authority.owner_ref, EntitlementSource.COMPLIMENTARY_GRANT.value,
                grant_id, event_id, None,
                current.state is EntitlementState.ACTIVE,
            )

    def revoke_founder_access(
        self,
        *,
        operator: OperatorAuthority,
        revocation_authority_address: str,
        server_time: dt.datetime,
    ) -> AccessGrant:
        if not isinstance(operator, OperatorAuthority):
            raise AccountCommerceRefused("current operator authority required")
        address(revocation_authority_address, "revocation authority")
        with self._begin():
            repository = AccountCommerceRepository(self.session)
            authority = self._authority(repository, server_time)
            operations = PlatformOperationsRepository(
                self.session, tenant=self._tenant(authority), operator=operator
            )
            operations._operator_row()
            grant_id = _stable_ref(
                "grant", "founder-revoke", authority.owner_ref,
                self.policy.policy_address, revocation_authority_address,
            )
            event_id = _stable_ref(
                "entitlement", EntitlementSource.COMPLIMENTARY_GRANT.value, grant_id
            )
            existing = self.session.get(PlatformComplimentaryEntitlementGrantRow, grant_id)
            if existing is None:
                operations.add_complimentary_grant(
                    grant_id=grant_id,
                    owner_ref=authority.owner_ref,
                    entitlement_code=PRODUCT_ACCESS,
                    action=GrantAction.REVOKE,
                    policy_address=self.policy.policy_address,
                    valid_from=server_time,
                    valid_until=None,
                    created_at=server_time,
                )
            else:
                expected = (
                    authority.owner_ref, PRODUCT_ACCESS, GrantAction.REVOKE.value,
                    self.policy.policy_address, None, operator.binding_id,
                )
                actual = (
                    existing.owner_ref, existing.entitlement_code, existing.action,
                    existing.policy_address, existing.valid_until,
                    existing.operator_binding_id,
                )
                if actual != expected:
                    raise AccountCommerceConflict("founder revocation grant conflicts")
            event = self.session.get(PlatformEntitlementEventRow, event_id)
            if event is None:
                current = operations.append_entitlement_event(
                    event_id=event_id,
                    entitlement_code=PRODUCT_ACCESS,
                    mode=BillingMode.INTERNAL,
                    source_kind=EntitlementSource.COMPLIMENTARY_GRANT,
                    source_ref=grant_id,
                    transition=EntitlementTransition.REVOKE,
                    policy_address=self.policy.policy_address,
                    valid_from=server_time,
                    valid_until=None,
                    effective_at=server_time,
                    recorded_at=server_time,
                )
            else:
                if (
                    event.owner_ref != authority.owner_ref
                    or event.entitlement_code != PRODUCT_ACCESS
                    or event.mode != BillingMode.INTERNAL.value
                    or event.source_kind != EntitlementSource.COMPLIMENTARY_GRANT.value
                    or event.source_ref != grant_id
                    or event.transition != EntitlementTransition.REVOKE.value
                    or event.policy_address != self.policy.policy_address
                    or event.valid_until is not None
                ):
                    raise AccountCommerceConflict("founder revocation event conflicts")
                current = operations.current_entitlement(PRODUCT_ACCESS, BillingMode.INTERNAL)
            return AccessGrant(
                authority.owner_ref, EntitlementSource.COMPLIMENTARY_GRANT.value,
                grant_id, event_id, None,
                current.state is EntitlementState.ACTIVE,
            )

    def current_access(self, *, server_time: dt.datetime) -> AccessStatus:
        with self._begin():
            repository = AccountCommerceRepository(self.session)
            authority = self._authority(repository, server_time)
            current = PlatformOperationsRepository(
                self.session, tenant=self._tenant(authority)
            ).current_entitlement(PRODUCT_ACCESS, BillingMode.INTERNAL)
            state = current.state.value
            if current.state is EntitlementState.ACTIVE and not self._access_active_at(
                current, server_time
            ):
                state = "EXPIRED"
            return AccessStatus(
                authority.owner_ref, state, current.source_event_id, current.valid_until
            )

    def rebuild_access(self, *, server_time: dt.datetime) -> AccessStatus:
        with self._begin():
            repository = AccountCommerceRepository(self.session)
            authority = self._authority(repository, server_time)
            operations = PlatformOperationsRepository(
                self.session, tenant=self._tenant(authority)
            )
            operations.rebuild_entitlements(rebuilt_at=server_time)
            current = operations.current_entitlement(PRODUCT_ACCESS, BillingMode.INTERNAL)
            state = current.state.value
            if current.state is EntitlementState.ACTIVE and not self._access_active_at(
                current, server_time
            ):
                state = "EXPIRED"
            return AccessStatus(
                authority.owner_ref, state, current.source_event_id, current.valid_until
            )

    def _existing_trial_grant(
        self, authority: AccountAuthority, prior, *, server_time: dt.datetime
    ) -> AccessGrant:
        event = self.session.get(PlatformEntitlementEventRow, prior.entitlement_event_id)
        beta_policy_mismatch = (
            prior.source_kind == EntitlementSource.BETA_TRIAL.value
            and event is not None
            and event.policy_address != self.policy.policy_address
        )
        if (event is None or event.owner_ref != authority.owner_ref
                or event.source_kind != prior.source_kind
                or event.source_ref != prior.source_ref
                or event.entitlement_code != PRODUCT_ACCESS
                or event.mode != BillingMode.INTERNAL.value
                or event.transition != EntitlementTransition.GRANT.value
                or event.event_id != prior.entitlement_event_id
                or event.valid_from != prior.valid_from.replace(tzinfo=None)
                or event.valid_until != prior.valid_until.replace(tzinfo=None)
                or beta_policy_mismatch):
            raise AccountCommerceConflict("trial source-to-event projection is incomplete")
        current = PlatformOperationsRepository(
            self.session, tenant=self._tenant(authority)
        ).current_entitlement(PRODUCT_ACCESS, BillingMode.INTERNAL)
        return AccessGrant(
            authority.owner_ref, prior.source_kind, prior.source_ref,
            prior.entitlement_event_id, prior.valid_until,
            self._access_active_at(current, server_time),
        )


__all__ = [
    "AccessGrant", "AccessStatus", "AccountCommerceService", "AccountStatus",
    "PRODUCT_ACCESS", "ProfileStatus", "ServerProfileAttestation",
]
