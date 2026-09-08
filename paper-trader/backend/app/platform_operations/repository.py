"""Transactional repository for the closed platform OPERATIONS plane."""
from __future__ import annotations

import datetime as dt
import hashlib
import secrets
from collections.abc import Iterable

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import (
    AccountTrialUseRow,
    PlatformAnalyticsEventRow, PlatformAnalyticsSubjectRow,
    PlatformBillingBindingRow, PlatformBillingEventReceiptRow,
    PlatformComplimentaryEntitlementGrantRow, PlatformCouponDefinitionRow,
    PlatformCouponRedemptionRow, PlatformCurrentEntitlementRow,
    PlatformEntitlementEventRow, PlatformOperatorAuditEventRow,
    PlatformOperatorBindingRow, PlatformPlanVersionRow,
    PlatformSupportReplyRow, PlatformSupportRequestRow,
)
from app.platform_operations.contracts import (
    AnalyticsEventType, AnalyticsOutcome, AnalyticsSubject, AnalyticsSurface,
    BillingEventState, BillingEventType, BillingInterval, BillingMode, BillingReceipt,
    BillingVerifierAuthority,
    BindingState, CouponRedemption, CouponState, CurrentEntitlement,
    EntitlementEffectTiming, EntitlementSource, EntitlementState, EntitlementTransition,
    GrantAction,
    MembershipState, OperationsConflict, OperationsNotFound, OperationsRefused,
    OperatorAction, OperatorAuthority, OperatorBindingState, OperatorOutcome,
    OperatorPermission, OperatorTarget, Page, PlanVersion, PolicyState,
    SupportCategory, SupportRequest, SupportStatus, TenantAuthority,
    address, analytics_dimension_code, code, currency, digest, page_limit,
    redacted_id, reference, support_detail_code, support_response_code, utc,
    validate_persisted_text,
)


OPERATIONS_TABLES = frozenset({
    "platform_plan_versions", "platform_coupon_definitions", "platform_coupon_redemptions",
    "platform_billing_bindings", "platform_billing_event_receipts",
    "platform_entitlement_events", "platform_current_entitlements",
    "platform_complimentary_entitlement_grants", "platform_analytics_subjects",
    "platform_analytics_events", "platform_support_requests", "platform_support_replies",
    "platform_operator_bindings", "platform_operator_audit_events",
})


def _db_time(value: dt.datetime) -> dt.datetime:
    return utc(value, "time").replace(tzinfo=None)


def _api_time(value: dt.datetime | None) -> dt.datetime | None:
    return None if value is None else value.replace(tzinfo=dt.timezone.utc)


def _enum(value, enum_type, label: str):
    try:
        return enum_type(value)
    except (TypeError, ValueError) as exc:
        raise OperationsRefused(f"unsupported {label}") from exc


class PlatformOperationsRepository:
    """One short-transaction repository bound to server-derived authorities."""

    def __init__(self, session: Session, *, tenant: TenantAuthority | None = None,
                 operator: OperatorAuthority | None = None,
                 verifier: BillingVerifierAuthority | None = None):
        self.session = session
        self.tenant = tenant
        self.operator = operator
        self.verifier = verifier

    def _owner(self) -> str:
        if self.tenant is None or self.tenant.membership_state is not MembershipState.ACTIVE:
            raise OperationsRefused("active server-derived tenant membership required")
        return self.tenant.owner_ref

    def _operator_row(self) -> PlatformOperatorBindingRow:
        if self.operator is None:
            raise OperationsRefused("platform operator authority required")
        row = self.session.scalar(sa.select(PlatformOperatorBindingRow).where(
            PlatformOperatorBindingRow.binding_id == self.operator.binding_id,
            PlatformOperatorBindingRow.principal_ref == self.operator.principal_ref,
            PlatformOperatorBindingRow.operator_slot == "FOUNDER",
            PlatformOperatorBindingRow.status == OperatorBindingState.ACTIVE.value,
        ))
        if row is None:
            raise OperationsRefused("active founder operator binding required")
        return row

    def _billing_verifier(self) -> BillingVerifierAuthority:
        if self.verifier is None:
            raise OperationsRefused("internal billing verifier authority required")
        return self.verifier

    def bind_founder(self, *, binding_id: str, principal_ref: str,
                     permission_profile_address: str, bootstrap_evidence_address: str,
                     created_at: dt.datetime) -> None:
        """Materialise an explicit bootstrap decision; no tenant role is accepted."""
        reference(binding_id, "binding")
        reference(principal_ref, "principal")
        address(permission_profile_address, "permission profile")
        address(bootstrap_evidence_address, "bootstrap evidence")
        existing = self.session.get(PlatformOperatorBindingRow, "FOUNDER")
        if existing is not None:
            if existing.binding_id == binding_id and existing.principal_ref == principal_ref:
                return
            raise OperationsConflict("founder operator slot is already bound")
        self.session.add(PlatformOperatorBindingRow(
            operator_slot="FOUNDER", binding_id=binding_id, principal_ref=principal_ref,
            permission_profile_address=permission_profile_address,
            bootstrap_evidence_address=bootstrap_evidence_address,
            status=OperatorBindingState.ACTIVE.value, created_at=_db_time(created_at), revoked_at=None,
        ))
        self.session.flush()

    def create_plan_version(self, *, plan_version_id: str, plan_code: str, version: int,
                            amount_minor: int, currency_code: str,
                            billing_interval: BillingInterval,
                            entitlement_set_address: str, policy_state: PolicyState,
                            created_at: dt.datetime,
                            test_provider_plan_address: str | None = None,
                            live_provider_plan_address: str | None = None) -> PlanVersion:
        self._operator_row()
        reference(plan_version_id, "plan version")
        code(plan_code, "plan code")
        if isinstance(version, bool) or not isinstance(version, int) or version < 1:
            raise OperationsRefused("plan version must be positive")
        if isinstance(amount_minor, bool) or not isinstance(amount_minor, int) or amount_minor < 0:
            raise OperationsRefused("trusted amount must be non-negative integer minor units")
        interval = _enum(billing_interval, BillingInterval, "billing interval")
        state = _enum(policy_state, PolicyState, "policy state")
        address(entitlement_set_address, "entitlement set")
        for value in (test_provider_plan_address, live_provider_plan_address):
            if value is not None:
                address(value, "provider plan")
        row = PlatformPlanVersionRow(
            plan_version_id=plan_version_id, plan_code=plan_code, version=version,
            amount_minor=amount_minor, currency=currency(currency_code),
            billing_interval=interval.value, entitlement_set_address=entitlement_set_address,
            policy_state=state.value, test_provider_plan_address=test_provider_plan_address,
            live_provider_plan_address=live_provider_plan_address, created_at=_db_time(created_at),
        )
        self.session.add(row)
        try:
            self.session.flush()
        except IntegrityError as exc:
            raise OperationsConflict("plan version identity already exists") from exc
        return PlanVersion(plan_version_id, plan_code, version, amount_minor, currency_code,
                           interval, entitlement_set_address, state, utc(created_at, "created at"))

    def define_coupon(self, *, coupon_id: str, coupon_digest: str, plan_version_id: str,
                      policy_address: str, valid_from: dt.datetime,
                      valid_until: dt.datetime | None, max_redemptions: int | None,
                      per_owner_limit: int, status: CouponState, created_at: dt.datetime,
                      entitlement_code: str,
                      entitlement_transition: EntitlementTransition,
                      entitlement_valid_from: dt.datetime | None,
                      entitlement_valid_until: dt.datetime | None,
                      trial_policy_address: str | None = None,
                      discount_policy_address: str | None = None,
                      entitlement_effect_timing: EntitlementEffectTiming =
                      EntitlementEffectTiming.FIXED_ABSOLUTE,
                      entitlement_duration_seconds: int | None = None) -> None:
        self._operator_row()
        reference(coupon_id, "coupon")
        digest(coupon_digest, "coupon digest")
        reference(plan_version_id, "plan version")
        address(policy_address, "coupon policy")
        for value in (trial_policy_address, discount_policy_address):
            if value is not None:
                address(value, "coupon sub-policy")
        code(entitlement_code, "coupon entitlement code")
        transition = _enum(
            entitlement_transition, EntitlementTransition, "coupon entitlement transition")
        timing = _enum(
            entitlement_effect_timing, EntitlementEffectTiming,
            "coupon entitlement effect timing")
        if max_redemptions is not None and (isinstance(max_redemptions, bool) or max_redemptions < 1):
            raise OperationsRefused("coupon maximum must be positive or unknown")
        if isinstance(per_owner_limit, bool) or not 1 <= per_owner_limit <= 100:
            raise OperationsRefused("coupon owner limit is out of bounds")
        start = _db_time(valid_from)
        end = None if valid_until is None else _db_time(valid_until)
        if end is not None and end <= start:
            raise OperationsRefused("coupon validity must be increasing")
        entitlement_start = (None if entitlement_valid_from is None
                             else _db_time(entitlement_valid_from))
        entitlement_end = (None if entitlement_valid_until is None
                           else _db_time(entitlement_valid_until))
        if timing is EntitlementEffectTiming.FIXED_ABSOLUTE:
            if (entitlement_start is None or entitlement_duration_seconds is not None
                    or (entitlement_end is not None
                        and entitlement_end <= entitlement_start)):
                raise OperationsRefused("fixed coupon entitlement shape is invalid")
        elif (
            entitlement_start is not None
            or entitlement_end is not None
            or entitlement_duration_seconds != 1_296_000
            or isinstance(entitlement_duration_seconds, bool)
            or trial_policy_address is None
            or discount_policy_address is not None
            or transition is not EntitlementTransition.GRANT
        ):
            raise OperationsRefused("dynamic coupon entitlement shape is invalid")
        self.session.add(PlatformCouponDefinitionRow(
            coupon_id=coupon_id, coupon_digest=coupon_digest, plan_version_id=plan_version_id,
            policy_address=policy_address, trial_policy_address=trial_policy_address,
            discount_policy_address=discount_policy_address, valid_from=start, valid_until=end,
            entitlement_code=entitlement_code,
            entitlement_transition=transition.value,
            entitlement_effect_timing=timing.value,
            entitlement_duration_seconds=entitlement_duration_seconds,
            entitlement_valid_from=entitlement_start,
            entitlement_valid_until=entitlement_end,
            max_redemptions=max_redemptions, per_owner_limit=per_owner_limit,
            status=_enum(status, CouponState, "coupon state").value,
            created_at=_db_time(created_at),
        ))
        self.session.flush()

    def redeem_coupon(self, *, coupon_digest: str, redemption_id: str,
                      policy_address: str, redeemed_at: dt.datetime) -> CouponRedemption:
        owner = self._owner()
        digest(coupon_digest, "coupon digest")
        reference(redemption_id, "redemption")
        address(policy_address, "redemption policy")
        moment = _db_time(redeemed_at)
        query = sa.select(PlatformCouponDefinitionRow).where(
            PlatformCouponDefinitionRow.coupon_digest == coupon_digest).with_for_update()
        coupon = self.session.scalar(query)
        if (coupon is None or coupon.status != CouponState.ACTIVE.value
                or moment < coupon.valid_from
                or (coupon.valid_until is not None and moment >= coupon.valid_until)
                or coupon.policy_address != policy_address):
            raise OperationsRefused("coupon is not currently admissible")
        total = self.session.scalar(sa.select(sa.func.count()).select_from(
            PlatformCouponRedemptionRow).where(
                PlatformCouponRedemptionRow.coupon_id == coupon.coupon_id,
                PlatformCouponRedemptionRow.status == "ACCEPTED")) or 0
        owner_count = self.session.scalar(sa.select(sa.func.count()).select_from(
            PlatformCouponRedemptionRow).where(
                PlatformCouponRedemptionRow.coupon_id == coupon.coupon_id,
                PlatformCouponRedemptionRow.owner_ref == owner,
                PlatformCouponRedemptionRow.status == "ACCEPTED")) or 0
        if coupon.max_redemptions is not None and total >= coupon.max_redemptions:
            raise OperationsRefused("coupon redemption capacity exhausted")
        if owner_count >= coupon.per_owner_limit:
            raise OperationsRefused("coupon owner redemption capacity exhausted")
        try:
            timing = EntitlementEffectTiming(coupon.entitlement_effect_timing)
        except ValueError as exc:
            raise OperationsRefused("coupon entitlement effect timing is invalid") from exc
        if timing is EntitlementEffectTiming.DYNAMIC_DURATION:
            if (
                coupon.entitlement_valid_from is not None
                or coupon.entitlement_valid_until is not None
                or coupon.entitlement_duration_seconds != 1_296_000
                or coupon.trial_policy_address is None
                or coupon.discount_policy_address is not None
                or coupon.entitlement_transition != EntitlementTransition.GRANT.value
            ):
                raise OperationsRefused("dynamic coupon entitlement shape is invalid")
            entitlement_start = moment
            entitlement_end = moment + dt.timedelta(
                seconds=coupon.entitlement_duration_seconds)
        else:
            if (coupon.entitlement_valid_from is None
                    or coupon.entitlement_duration_seconds is not None
                    or (coupon.entitlement_valid_until is not None
                        and coupon.entitlement_valid_until <= coupon.entitlement_valid_from)):
                raise OperationsRefused("fixed coupon entitlement shape is invalid")
            entitlement_start = coupon.entitlement_valid_from
            entitlement_end = coupon.entitlement_valid_until
        redemption_row = PlatformCouponRedemptionRow(
            redemption_id=redemption_id, coupon_id=coupon.coupon_id, owner_ref=owner,
            policy_address=policy_address, status="ACCEPTED",
            entitlement_code=coupon.entitlement_code,
            entitlement_transition=coupon.entitlement_transition,
            entitlement_valid_from=entitlement_start,
            entitlement_valid_until=entitlement_end,
            redeemed_at=moment)
        self.session.add(redemption_row)
        try:
            self.session.flush()
        except IntegrityError as exc:
            raise OperationsConflict("coupon redemption already exists") from exc
        return CouponRedemption(
            redemption_id, coupon.coupon_id, owner, policy_address,
            _api_time(redemption_row.redeemed_at),
            _api_time(redemption_row.entitlement_valid_from),
            _api_time(redemption_row.entitlement_valid_until),
        )

    def create_billing_binding(self, *, binding_id: str, mode: BillingMode,
                               merchant_address: str, integration_address: str,
                               status: BindingState, created_at: dt.datetime,
                               provider_customer_ref: str,
                               provider_subscription_ref: str) -> None:
        owner = self._owner()
        reference(binding_id, "billing binding")
        billing_mode = _enum(mode, BillingMode, "billing mode")
        if billing_mode is BillingMode.INTERNAL:
            raise OperationsRefused("billing bindings cannot use internal mode")
        address(merchant_address, "merchant")
        address(integration_address, "integration")
        for value in (provider_customer_ref, provider_subscription_ref):
            reference(value, "provider reference")
        moment = _db_time(created_at)
        self.session.add(PlatformBillingBindingRow(
            binding_id=binding_id, owner_ref=owner, mode=billing_mode.value,
            merchant_address=merchant_address, integration_address=integration_address,
            provider_customer_ref=provider_customer_ref,
            provider_subscription_ref=provider_subscription_ref,
            status=_enum(status, BindingState, "binding state").value,
            created_at=moment, updated_at=moment))
        self.session.flush()

    def receive_billing_event(self, *, receipt_id: str, binding_id: str,
                              provider_event_ref: str, event_type: BillingEventType,
                              event_state: BillingEventState, raw_body_digest: str,
                              occurred_at: dt.datetime, received_at: dt.datetime,
                              amount_minor: int | None = None, currency_code: str | None = None,
                              provider_customer_ref: str,
                              provider_payment_ref: str | None = None,
                              provider_subscription_ref: str,
                              provider_invoice_ref: str | None = None,
                              entitlement_code: str | None = None,
                              entitlement_transition: EntitlementTransition | None = None,
                              entitlement_policy_address: str | None = None,
                              entitlement_valid_from: dt.datetime | None = None,
                              entitlement_valid_until: dt.datetime | None = None) -> BillingReceipt:
        for value, label in ((receipt_id, "receipt"), (binding_id, "binding"),
                             (provider_event_ref, "provider event")):
            reference(value, label)
        body_digest = digest(raw_body_digest, "raw body digest")
        state = _enum(event_state, BillingEventState, "event state")
        if state is BillingEventState.VERIFIED:
            verifier = self._billing_verifier()
            binding = self.session.scalar(sa.select(PlatformBillingBindingRow).where(
                PlatformBillingBindingRow.binding_id == binding_id,
                PlatformBillingBindingRow.mode == verifier.mode.value,
                PlatformBillingBindingRow.merchant_address == verifier.merchant_address,
                PlatformBillingBindingRow.integration_address == verifier.integration_address))
        else:
            owner = self._owner()
            binding = self.session.scalar(sa.select(PlatformBillingBindingRow).where(
                PlatformBillingBindingRow.binding_id == binding_id,
                PlatformBillingBindingRow.owner_ref == owner))
        if binding is None:
            raise OperationsNotFound("billing binding not found")
        owner = binding.owner_ref
        if (provider_customer_ref != binding.provider_customer_ref
                or provider_subscription_ref != binding.provider_subscription_ref):
            raise OperationsRefused("provider customer/subscription attribution mismatch")
        reference(provider_customer_ref, "provider customer")
        reference(provider_subscription_ref, "provider subscription")
        existing = self.session.scalar(sa.select(PlatformBillingEventReceiptRow).where(
            PlatformBillingEventReceiptRow.mode == binding.mode,
            PlatformBillingEventReceiptRow.merchant_address == binding.merchant_address,
            PlatformBillingEventReceiptRow.integration_address == binding.integration_address,
            PlatformBillingEventReceiptRow.provider_event_ref == provider_event_ref))
        if existing is not None:
            if existing.raw_body_digest != body_digest or existing.receipt_id != receipt_id:
                raise OperationsConflict("provider event identity conflicts with durable receipt")
            return self._receipt(existing)
        if amount_minor is not None and (isinstance(amount_minor, bool) or amount_minor < 0):
            raise OperationsRefused("event amount must be non-negative integer minor units")
        if currency_code is not None:
            currency(currency_code)
        for value in (provider_payment_ref, provider_invoice_ref):
            if value is not None:
                reference(value, "provider fact")
        entitlement_values = (
            entitlement_code, entitlement_transition, entitlement_policy_address,
            entitlement_valid_from, entitlement_valid_until,
        )
        if any(value is not None for value in entitlement_values):
            if any(value is None for value in entitlement_values[:4]):
                raise OperationsRefused("billing entitlement facts must form one closed envelope")
            code(entitlement_code, "billing entitlement code")
            entitlement_transition = _enum(
                entitlement_transition, EntitlementTransition, "billing entitlement transition")
            address(entitlement_policy_address, "billing entitlement policy")
            entitlement_start = _db_time(entitlement_valid_from)
            entitlement_end = (None if entitlement_valid_until is None
                               else _db_time(entitlement_valid_until))
            if entitlement_end is not None and entitlement_end <= entitlement_start:
                raise OperationsRefused("billing entitlement validity must be increasing")
        else:
            entitlement_start = entitlement_end = None
        row = PlatformBillingEventReceiptRow(
            receipt_id=receipt_id, binding_id=binding_id, owner_ref=owner, mode=binding.mode,
            merchant_address=binding.merchant_address,
            integration_address=binding.integration_address,
            provider_customer_ref=binding.provider_customer_ref,
            provider_event_ref=provider_event_ref,
            event_type=_enum(event_type, BillingEventType, "event type").value,
            event_state=state.value,
            raw_body_digest=body_digest, facts_schema_version=1, amount_minor=amount_minor,
            currency=currency_code, provider_payment_ref=provider_payment_ref,
            provider_subscription_ref=provider_subscription_ref,
            provider_invoice_ref=provider_invoice_ref,
            entitlement_code=entitlement_code,
            entitlement_transition=(None if entitlement_transition is None
                                    else entitlement_transition.value),
            entitlement_policy_address=entitlement_policy_address,
            entitlement_valid_from=entitlement_start,
            entitlement_valid_until=entitlement_end,
            occurred_at=_db_time(occurred_at),
            received_at=_db_time(received_at))
        self.session.add(row)
        self.session.flush()
        return self._receipt(row)

    @staticmethod
    def _receipt(row: PlatformBillingEventReceiptRow) -> BillingReceipt:
        return BillingReceipt(
            row.receipt_id, row.binding_id, row.owner_ref, BillingMode(row.mode),
            row.provider_event_ref, BillingEventType(row.event_type),
            BillingEventState(row.event_state), row.raw_body_digest,
            _api_time(row.received_at),
        )

    def add_complimentary_grant(self, *, grant_id: str, owner_ref: str,
                                entitlement_code: str, action: GrantAction,
                                policy_address: str, valid_from: dt.datetime,
                                valid_until: dt.datetime | None,
                                created_at: dt.datetime) -> None:
        operator = self._operator_row()
        reference(grant_id, "complimentary grant")
        reference(owner_ref, "grant owner")
        code(entitlement_code, "entitlement code")
        address(policy_address, "grant policy")
        start = _db_time(valid_from)
        end = None if valid_until is None else _db_time(valid_until)
        if end is not None and end <= start:
            raise OperationsRefused("grant validity must be increasing")
        self.session.add(PlatformComplimentaryEntitlementGrantRow(
            grant_id=grant_id, owner_ref=owner_ref, entitlement_code=entitlement_code,
            action=_enum(action, GrantAction, "grant action").value,
            policy_address=policy_address, valid_from=start, valid_until=end,
            operator_binding_id=operator.binding_id, created_at=_db_time(created_at)))
        self.session.flush()

    def append_entitlement_event(self, *, event_id: str, entitlement_code: str,
                                 mode: BillingMode, source_kind: EntitlementSource,
                                 source_ref: str, transition: EntitlementTransition,
                                 policy_address: str, valid_from: dt.datetime,
                                 valid_until: dt.datetime | None, effective_at: dt.datetime,
                                 recorded_at: dt.datetime) -> CurrentEntitlement:
        owner = self._owner()
        reference(event_id, "entitlement event")
        code(entitlement_code, "entitlement code")
        reference(source_ref, "entitlement source")
        address(policy_address, "entitlement policy")
        billing_mode = _enum(mode, BillingMode, "entitlement mode")
        source = _enum(source_kind, EntitlementSource, "entitlement source kind")
        start = _db_time(valid_from)
        end = None if valid_until is None else _db_time(valid_until)
        effective = _db_time(effective_at)
        transition_value = _enum(
            transition, EntitlementTransition, "entitlement transition").value
        if end is not None and end <= start:
            raise OperationsRefused("entitlement validity must be increasing")
        self._validate_entitlement_source(
            owner, billing_mode, source, source_ref, event_id=event_id,
            entitlement_code=entitlement_code, transition=transition_value,
            policy_address=policy_address, valid_from=start, valid_until=end)
        row = PlatformEntitlementEventRow(
            event_id=event_id, owner_ref=owner, entitlement_code=entitlement_code,
            mode=billing_mode.value, source_kind=source.value, source_ref=source_ref,
            transition=transition_value,
            policy_address=policy_address, valid_from=start, valid_until=end,
            effective_at=effective, recorded_at=_db_time(recorded_at))
        self.session.add(row)
        try:
            self.session.flush()
        except IntegrityError as exc:
            raise OperationsConflict("entitlement source was already reduced") from exc
        self._project(row, _db_time(recorded_at))
        return self.current_entitlement(entitlement_code, billing_mode)

    def _validate_entitlement_source(
        self, owner: str, mode: BillingMode, source: EntitlementSource, source_ref: str,
        *, event_id: str,
        entitlement_code: str, transition: str, policy_address: str,
        valid_from: dt.datetime, valid_until: dt.datetime | None,
    ) -> None:
        if source is EntitlementSource.BILLING_RECEIPT:
            found = self.session.scalar(sa.select(PlatformBillingEventReceiptRow).where(
                PlatformBillingEventReceiptRow.receipt_id == source_ref,
                PlatformBillingEventReceiptRow.owner_ref == owner,
                PlatformBillingEventReceiptRow.mode == mode.value,
                PlatformBillingEventReceiptRow.event_state == BillingEventState.VERIFIED.value))
            if found is None or mode is BillingMode.INTERNAL:
                raise OperationsRefused("verified owner/mode billing receipt required")
            expected = (
                found.entitlement_code, found.entitlement_transition,
                found.entitlement_policy_address, found.entitlement_valid_from,
                found.entitlement_valid_until,
            )
        elif source is EntitlementSource.COUPON_REDEMPTION:
            found = self.session.scalar(sa.select(PlatformCouponRedemptionRow).where(
                PlatformCouponRedemptionRow.redemption_id == source_ref,
                PlatformCouponRedemptionRow.owner_ref == owner,
                PlatformCouponRedemptionRow.status == "ACCEPTED"))
            if found is None or mode is not BillingMode.INTERNAL:
                raise OperationsRefused("accepted owner coupon redemption requires internal mode")
            expected = (
                found.entitlement_code, found.entitlement_transition,
                found.policy_address, found.entitlement_valid_from,
                found.entitlement_valid_until,
            )
        elif source is EntitlementSource.COMPLIMENTARY_GRANT:
            found = self.session.scalar(sa.select(PlatformComplimentaryEntitlementGrantRow).where(
                PlatformComplimentaryEntitlementGrantRow.grant_id == source_ref,
                PlatformComplimentaryEntitlementGrantRow.owner_ref == owner))
            if found is None or mode is not BillingMode.INTERNAL:
                raise OperationsRefused("explicit owner complimentary grant requires internal mode")
            expected = (
                found.entitlement_code, found.action, found.policy_address,
                found.valid_from, found.valid_until,
            )
        else:
            found = self.session.scalar(sa.select(AccountTrialUseRow).where(
                AccountTrialUseRow.trial_use_id == source_ref,
                AccountTrialUseRow.owner_ref == owner,
                AccountTrialUseRow.source_kind == EntitlementSource.BETA_TRIAL.value,
                AccountTrialUseRow.entitlement_event_id == event_id,
            ))
            if found is None or mode is not BillingMode.INTERNAL:
                raise OperationsRefused("exact owner beta trial source requires internal mode")
            expected = (
                found.entitlement_code, found.entitlement_transition,
                found.policy_address, found.valid_from, found.valid_until,
            )
        actual = (entitlement_code, transition, policy_address, valid_from, valid_until)
        if expected != actual:
            raise OperationsRefused("entitlement event does not exactly match its source fact")

    def _project(self, event: PlatformEntitlementEventRow, rebuilt_at: dt.datetime) -> None:
        key = (event.owner_ref, event.entitlement_code, event.mode)
        current = self.session.get(PlatformCurrentEntitlementRow, key)
        if current is not None and (current.effective_at, current.source_event_id) >= (
                event.effective_at, event.event_id):
            return
        state = (EntitlementState.ACTIVE.value if event.transition in
                 {EntitlementTransition.GRANT.value, EntitlementTransition.RENEW.value}
                 else EntitlementState.INACTIVE.value)
        if current is None:
            current = PlatformCurrentEntitlementRow(
                owner_ref=event.owner_ref, entitlement_code=event.entitlement_code,
                mode=event.mode, projection_version=1, state=state,
                source_event_id=event.event_id, effective_at=event.effective_at,
                valid_until=event.valid_until, rebuilt_at=rebuilt_at)
            self.session.add(current)
        else:
            current.state = state
            current.source_event_id = event.event_id
            current.effective_at = event.effective_at
            current.valid_until = event.valid_until
            current.projection_version += 1
            current.rebuilt_at = rebuilt_at
        self.session.flush()

    def rebuild_entitlements(self, *, rebuilt_at: dt.datetime) -> tuple[CurrentEntitlement, ...]:
        owner = self._owner()
        self.session.execute(sa.delete(PlatformCurrentEntitlementRow).where(
            PlatformCurrentEntitlementRow.owner_ref == owner))
        events = self.session.scalars(sa.select(PlatformEntitlementEventRow).where(
            PlatformEntitlementEventRow.owner_ref == owner).order_by(
                PlatformEntitlementEventRow.effective_at,
                PlatformEntitlementEventRow.event_id)).all()
        stamp = _db_time(rebuilt_at)
        for event in events:
            self._project(event, stamp)
        rows = self.session.scalars(sa.select(PlatformCurrentEntitlementRow).where(
            PlatformCurrentEntitlementRow.owner_ref == owner).order_by(
                PlatformCurrentEntitlementRow.entitlement_code,
                PlatformCurrentEntitlementRow.mode)).all()
        return tuple(self._current(row) for row in rows)

    def current_entitlement(self, entitlement_code: str, mode: BillingMode) -> CurrentEntitlement:
        owner = self._owner()
        code(entitlement_code, "entitlement code")
        row = self.session.get(PlatformCurrentEntitlementRow,
                               (owner, entitlement_code, _enum(mode, BillingMode, "mode").value))
        if row is None:
            return CurrentEntitlement(owner, entitlement_code, mode, EntitlementState.UNKNOWN,
                                      None, None, None)
        return self._current(row)

    @staticmethod
    def _current(row: PlatformCurrentEntitlementRow) -> CurrentEntitlement:
        return CurrentEntitlement(row.owner_ref, row.entitlement_code, BillingMode(row.mode),
                                  EntitlementState(row.state), row.source_event_id,
                                  _api_time(row.effective_at), _api_time(row.valid_until))

    def create_analytics_subject(self, *, created_at: dt.datetime) -> AnalyticsSubject:
        owner = self._owner()
        subject_id = "subject." + secrets.token_hex(16)
        pseudonym = hashlib.sha256(secrets.token_bytes(32)).hexdigest()
        row = PlatformAnalyticsSubjectRow(owner_ref=owner, subject_id=subject_id,
            pseudonym_digest=pseudonym, created_at=_db_time(created_at),
            deleted_at=None, exported_at=None)
        self.session.add(row)
        self.session.flush()
        return AnalyticsSubject(owner, subject_id, utc(created_at, "created at"), None, None)

    def record_analytics_event(self, *, event_id: str, subject_id: str,
                               event_type: AnalyticsEventType, surface: AnalyticsSurface,
                               outcome: AnalyticsOutcome, occurred_at: dt.datetime,
                               dimension_a: str | None = None,
                               dimension_b: str | None = None) -> None:
        owner = self._owner()
        reference(event_id, "analytics event")
        reference(subject_id, "analytics subject")
        for value in (dimension_a, dimension_b):
            if value is not None:
                analytics_dimension_code(value)
        subject = self.session.get(PlatformAnalyticsSubjectRow, (owner, subject_id))
        if subject is None or subject.deleted_at is not None:
            raise OperationsNotFound("active analytics subject not found")
        self.session.add(PlatformAnalyticsEventRow(
            event_id=event_id, owner_ref=owner, subject_id=subject_id, schema_version=1,
            event_type=_enum(event_type, AnalyticsEventType, "analytics event").value,
            surface=_enum(surface, AnalyticsSurface, "analytics surface").value,
            outcome=_enum(outcome, AnalyticsOutcome, "analytics outcome").value,
            dimension_a=dimension_a, dimension_b=dimension_b,
            occurred_at=_db_time(occurred_at)))
        self.session.flush()

    def mark_analytics_exported(self, *, subject_id: str, at: dt.datetime) -> None:
        owner = self._owner()
        row = self.session.get(PlatformAnalyticsSubjectRow, (owner, reference(subject_id, "subject")))
        if row is None:
            raise OperationsNotFound("analytics subject not found")
        row.exported_at = _db_time(at)
        self.session.flush()

    def mark_analytics_deleted(self, *, subject_id: str, at: dt.datetime) -> None:
        owner = self._owner()
        row = self.session.get(PlatformAnalyticsSubjectRow, (owner, reference(subject_id, "subject")))
        if row is None:
            raise OperationsNotFound("analytics subject not found")
        row.deleted_at = _db_time(at)
        self.session.flush()

    def create_support_request(self, *, request_id: str, category: SupportCategory,
                               detail_code: str, created_at: dt.datetime) -> SupportRequest:
        owner = self._owner()
        reference(request_id, "support request")
        support_detail_code(detail_code)
        moment = _db_time(created_at)
        row = PlatformSupportRequestRow(
            request_id=request_id, owner_ref=owner,
            schema_version=1,
            category=_enum(category, SupportCategory, "support category").value,
            detail_code=detail_code, status=SupportStatus.OPEN.value,
            created_at=moment, updated_at=moment, deleted_at=None, exported_at=None)
        self.session.add(row)
        self.session.flush()
        return self._support(row)

    def list_support_requests(self, *, limit: int = 50,
                              after_request_id: str | None = None) -> Page:
        owner = self._owner()
        count = page_limit(limit)
        query = sa.select(PlatformSupportRequestRow).where(
            PlatformSupportRequestRow.owner_ref == owner)
        if after_request_id is not None:
            query = query.where(PlatformSupportRequestRow.request_id > reference(
                after_request_id, "support cursor"))
        rows = self.session.scalars(query.order_by(
            PlatformSupportRequestRow.request_id).limit(count + 1)).all()
        return Page(tuple(self._support(row) for row in rows[:count]),
                    rows[count - 1].request_id if len(rows) > count else None)

    @staticmethod
    def _support(row: PlatformSupportRequestRow) -> SupportRequest:
        return SupportRequest(row.request_id, row.owner_ref, SupportCategory(row.category),
                              row.detail_code, SupportStatus(row.status),
                              _api_time(row.created_at), _api_time(row.updated_at),
                              _api_time(row.deleted_at), _api_time(row.exported_at))

    def reply_support(self, *, reply_id: str, request_id: str, owner_ref: str,
                      response_code: str, created_at: dt.datetime) -> None:
        operator = self._operator_row()
        for value, label in ((reply_id, "reply"), (request_id, "request"),
                             (owner_ref, "owner")):
            reference(value, label)
        support_response_code(response_code)
        request = self.session.scalar(sa.select(PlatformSupportRequestRow).where(
            PlatformSupportRequestRow.request_id == request_id,
            PlatformSupportRequestRow.owner_ref == owner_ref))
        if request is None:
            raise OperationsNotFound("support request not found")
        self.session.add(PlatformSupportReplyRow(
            reply_id=reply_id, request_id=request_id, owner_ref=owner_ref,
            schema_version=1, operator_binding_id=operator.binding_id,
            response_code=response_code,
            created_at=_db_time(created_at)))
        self.session.flush()

    def append_operator_audit(self, *, audit_event_id: str,
                              permission: OperatorPermission, action: OperatorAction,
                              target: OperatorTarget, target_redacted_id: str,
                              outcome: OperatorOutcome, occurred_at: dt.datetime) -> None:
        operator = self._operator_row()
        reference(audit_event_id, "audit event")
        redacted_id(target_redacted_id)
        self.session.add(PlatformOperatorAuditEventRow(
            audit_event_id=audit_event_id, operator_binding_id=operator.binding_id,
            permission_class=_enum(permission, OperatorPermission, "permission").value,
            action_class=_enum(action, OperatorAction, "action").value,
            target_class=_enum(target, OperatorTarget, "target").value,
            target_redacted_id=target_redacted_id,
            outcome=_enum(outcome, OperatorOutcome, "outcome").value,
            occurred_at=_db_time(occurred_at)))
        self.session.flush()


def validate_persisted_operations(connection) -> None:
    """Recompute source/projection separation after copy or restore."""
    if not OPERATIONS_TABLES <= set(sa.inspect(connection).get_table_names()):
        raise OperationsRefused("platform operations table inventory is incomplete")
    definitions = {
        row["coupon_id"]: row
        for row in connection.execute(sa.select(
            PlatformCouponDefinitionRow.__table__)).mappings()
    }
    for definition in definitions.values():
        try:
            timing = EntitlementEffectTiming(definition["entitlement_effect_timing"])
        except ValueError as exc:
            raise OperationsRefused("coupon definition timing is invalid") from exc
        fixed = (
            definition["entitlement_valid_from"] is not None
            and definition["entitlement_duration_seconds"] is None
            and (
                definition["entitlement_valid_until"] is None
                or definition["entitlement_valid_until"]
                > definition["entitlement_valid_from"]
            )
        )
        dynamic = (
            definition["entitlement_valid_from"] is None
            and definition["entitlement_valid_until"] is None
            and definition["entitlement_duration_seconds"] == 1_296_000
            and definition["trial_policy_address"] is not None
            and definition["discount_policy_address"] is None
            and definition["entitlement_transition"]
            == EntitlementTransition.GRANT.value
        )
        if (
            timing is EntitlementEffectTiming.FIXED_ABSOLUTE and not fixed
            or timing is EntitlementEffectTiming.DYNAMIC_DURATION and not dynamic
        ):
            raise OperationsRefused("coupon definition entitlement shape is invalid")
    for redemption in connection.execute(sa.select(
            PlatformCouponRedemptionRow.__table__)).mappings():
        definition = definitions.get(redemption["coupon_id"])
        if (
            definition is None
            or redemption["policy_address"] != definition["policy_address"]
            or redemption["entitlement_code"] != definition["entitlement_code"]
            or redemption["entitlement_transition"]
            != definition["entitlement_transition"]
        ):
            raise OperationsRefused("coupon redemption definition attribution is invalid")
        if definition["entitlement_effect_timing"] == EntitlementEffectTiming.FIXED_ABSOLUTE.value:
            expected = (
                definition["entitlement_valid_from"],
                definition["entitlement_valid_until"],
            )
        else:
            expected = (
                redemption["redeemed_at"],
                redemption["redeemed_at"] + dt.timedelta(
                    seconds=definition["entitlement_duration_seconds"]),
            )
        if expected != (
            redemption["entitlement_valid_from"],
            redemption["entitlement_valid_until"],
        ):
            raise OperationsRefused("coupon redemption resolved envelope is invalid")
    events = connection.execute(sa.select(PlatformEntitlementEventRow.__table__).order_by(
        PlatformEntitlementEventRow.owner_ref, PlatformEntitlementEventRow.entitlement_code,
        PlatformEntitlementEventRow.mode, PlatformEntitlementEventRow.effective_at,
        PlatformEntitlementEventRow.event_id)).mappings().all()
    expected: dict[tuple[str, str, str], object] = {}
    for event in events:
        key = (event["owner_ref"], event["entitlement_code"], event["mode"])
        expected[key] = event
        source_table, required_mode = {
            EntitlementSource.BILLING_RECEIPT.value:
                (PlatformBillingEventReceiptRow.__table__, event["mode"]),
            EntitlementSource.COUPON_REDEMPTION.value:
                (PlatformCouponRedemptionRow.__table__, BillingMode.INTERNAL.value),
            EntitlementSource.COMPLIMENTARY_GRANT.value:
                (PlatformComplimentaryEntitlementGrantRow.__table__, BillingMode.INTERNAL.value),
            EntitlementSource.BETA_TRIAL.value:
                (AccountTrialUseRow.__table__, BillingMode.INTERNAL.value),
        }[event["source_kind"]]
        if event["mode"] != required_mode:
            raise OperationsRefused("entitlement source mode is invalid")
        source_id = {
            "platform_billing_event_receipts": "receipt_id",
            "platform_coupon_redemptions": "redemption_id",
            "platform_complimentary_entitlement_grants": "grant_id",
            "account_trial_uses": "trial_use_id",
        }[source_table.name]
        source = connection.execute(sa.select(source_table).where(
            source_table.c[source_id] == event["source_ref"],
            source_table.c.owner_ref == event["owner_ref"])).mappings().one_or_none()
        if source is None:
            raise OperationsRefused("entitlement source is absent or cross-owner")
        if source_table.name == "platform_billing_event_receipts" and (
                source["event_state"] != BillingEventState.VERIFIED.value
                or source["mode"] != event["mode"]):
            raise OperationsRefused("billing entitlement lacks verified same-mode receipt")
        if source_table.name == "platform_billing_event_receipts":
            source_fact = (
                source["entitlement_code"], source["entitlement_transition"],
                source["entitlement_policy_address"], source["entitlement_valid_from"],
                source["entitlement_valid_until"],
            )
        elif source_table.name == "platform_coupon_redemptions":
            source_fact = (
                source["entitlement_code"], source["entitlement_transition"],
                source["policy_address"], source["entitlement_valid_from"],
                source["entitlement_valid_until"],
            )
        elif source_table.name == "platform_complimentary_entitlement_grants":
            source_fact = (
                source["entitlement_code"], source["action"], source["policy_address"],
                source["valid_from"], source["valid_until"],
            )
        else:
            if (source["source_kind"] != EntitlementSource.BETA_TRIAL.value
                    or source["entitlement_event_id"] != event["event_id"]):
                raise OperationsRefused("beta trial source attribution is invalid")
            source_fact = (
                source["entitlement_code"], source["entitlement_transition"],
                source["policy_address"], source["valid_from"], source["valid_until"],
            )
        event_fact = (
            event["entitlement_code"], event["transition"], event["policy_address"],
            event["valid_from"], event["valid_until"],
        )
        if source_fact != event_fact:
            raise OperationsRefused("persisted entitlement event does not match its source")
    projections = {
        (row["owner_ref"], row["entitlement_code"], row["mode"]): row
        for row in connection.execute(sa.select(
            PlatformCurrentEntitlementRow.__table__)).mappings()
    }
    if set(projections) != set(expected):
        raise OperationsRefused("current entitlement projection key set is stale")
    for key, event in expected.items():
        projection = projections[key]
        state = (EntitlementState.ACTIVE.value if event["transition"] in
                 {EntitlementTransition.GRANT.value, EntitlementTransition.RENEW.value}
                 else EntitlementState.INACTIVE.value)
        if (projection["source_event_id"] != event["event_id"]
                or projection["effective_at"] != event["effective_at"]
                or projection["valid_until"] != event["valid_until"]
                or projection["state"] != state):
            raise OperationsRefused("current entitlement projection does not rebuild")
    bindings = connection.execute(sa.select(PlatformOperatorBindingRow.__table__)).mappings().all()
    if len(bindings) > 1 or any(row["operator_slot"] != "FOUNDER" for row in bindings):
        raise OperationsRefused("founder operator binding is not singleton")
    operator_ids = {row["binding_id"] for row in bindings}
    requests = {
        (row["request_id"], row["owner_ref"]): row
        for row in connection.execute(sa.select(PlatformSupportRequestRow.__table__)).mappings()
    }
    for request in requests.values():
        if request["schema_version"] != 1:
            raise OperationsRefused("unsupported support vocabulary version")
        try:
            SupportCategory(request["category"])
            SupportStatus(request["status"])
        except ValueError as exc:
            raise OperationsRefused("unsupported support vocabulary") from exc
        support_detail_code(request["detail_code"])
    for reply in connection.execute(sa.select(PlatformSupportReplyRow.__table__)).mappings():
        if (reply["schema_version"] != 1
                or (reply["request_id"], reply["owner_ref"]) not in requests
                or reply["operator_binding_id"] not in operator_ids):
            raise OperationsRefused("support reply attribution is invalid")
        support_response_code(reply["response_code"])
    for grant in connection.execute(sa.select(
            PlatformComplimentaryEntitlementGrantRow.__table__)).mappings():
        if grant["operator_binding_id"] not in operator_ids:
            raise OperationsRefused("complimentary grant operator attribution is invalid")
    for event in connection.execute(sa.select(PlatformAnalyticsEventRow.__table__)).mappings():
        if event["schema_version"] != 1:
            raise OperationsRefused("unsupported analytics vocabulary version")
        try:
            AnalyticsEventType(event["event_type"])
            AnalyticsSurface(event["surface"])
            AnalyticsOutcome(event["outcome"])
        except ValueError as exc:
            raise OperationsRefused("unsupported analytics vocabulary") from exc
        for dimension in (event["dimension_a"], event["dimension_b"]):
            if dimension is not None:
                analytics_dimension_code(dimension)
    for table_name in sorted(OPERATIONS_TABLES):
        table = sa.Table(table_name, sa.MetaData(), autoload_with=connection)
        text_columns = [column for column in table.columns
                        if isinstance(column.type, sa.String)]
        if not text_columns:
            continue
        for row in connection.execute(sa.select(*text_columns)):
            for column, value in zip(text_columns, row, strict=True):
                validate_persisted_text(value, f"{table_name}.{column.name}")
