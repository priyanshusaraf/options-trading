"""Privacy-minimised account evidence and single-use trial persistence."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.accounts.browser_auth import ABSOLUTE, IDLE
from app.api.principal import Principal
from app.db.models import (
    AccountProfileEvidenceRow,
    AccountTrialUseRow,
    BrowserSession,
    Membership,
    Organization,
    User,
    UserSession,
    PlatformCouponRedemptionRow,
    PlatformEntitlementEventRow,
)
from app.platform_operations.contracts import (
    EntitlementSource, address, code, reference, validate_persisted_text,
)


class AccountCommerceRefused(ValueError):
    """The local account-commerce boundary failed closed before an effect."""


class AccountCommerceAuthenticationRefused(AccountCommerceRefused):
    """The supplied request principal is not the current browser authority."""


class AccountCommerceConflict(RuntimeError):
    """An immutable account-commerce identity conflicts with durable state."""


def _db_time(value: dt.datetime) -> dt.datetime:
    if not isinstance(value, dt.datetime) or value.tzinfo is None:
        raise AccountCommerceRefused("server time must be timezone-aware")
    return value.astimezone(dt.timezone.utc).replace(tzinfo=None)


def _api_time(value: dt.datetime) -> dt.datetime:
    return value.replace(tzinfo=dt.timezone.utc)


def _stable_ref(prefix: str, *parts: str) -> str:
    material = json.dumps(parts, ensure_ascii=True, separators=(",", ":"))
    return f"{prefix}." + hashlib.sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class AccountAuthority:
    owner_ref: str
    user_ref: str
    principal_ref: str
    session_ref: str


@dataclass(frozen=True, slots=True)
class StoredProfileEvidence:
    profile_evidence_id: str
    owner_ref: str
    user_ref: str
    policy_address: str
    evidence_address: str
    satisfied_fields: tuple[str, ...]
    attested_at: dt.datetime


@dataclass(frozen=True, slots=True)
class StoredTrialUse:
    trial_use_id: str
    owner_ref: str
    user_ref: str
    policy_address: str
    profile_evidence_id: str
    source_kind: str
    source_ref: str
    entitlement_event_id: str
    valid_from: dt.datetime
    valid_until: dt.datetime


class AccountCommerceRepository:
    """One account-plane repository; owner and user never come from command data."""

    def __init__(self, session: Session):
        self.session = session

    @staticmethod
    def trial_id_for(authority: AccountAuthority, policy_address: str) -> str:
        return _stable_ref("trial", authority.owner_ref, authority.user_ref, policy_address)

    def resolve_authority(
        self, principal: Principal | None, *, server_time: dt.datetime
    ) -> AccountAuthority:
        if (
            not isinstance(principal, Principal)
            or principal.kind != "user"
            or not principal.authenticated
        ):
            raise AccountCommerceAuthenticationRefused("active browser principal required")
        if not principal.user_id or not principal.organization_id or not principal.session_id:
            raise AccountCommerceAuthenticationRefused("complete browser principal required")
        if principal.id != principal.user_id:
            raise AccountCommerceAuthenticationRefused("active browser principal required")
        moment = _db_time(server_time)
        row = self.session.execute(
            sa.select(UserSession, BrowserSession, Membership, User, Organization)
            .join(BrowserSession, BrowserSession.session_id == UserSession.session_id)
            .join(
                Membership,
                sa.and_(
                    Membership.organization_id == UserSession.organization_id,
                    Membership.user_id == UserSession.user_id,
                ),
            )
            .join(User, User.user_id == UserSession.user_id)
            .join(Organization, Organization.organization_id == UserSession.organization_id)
            .where(
                UserSession.session_id == principal.session_id,
                UserSession.user_id == principal.user_id,
                UserSession.organization_id == principal.organization_id,
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > moment,
                UserSession.issued_at > moment - ABSOLUTE,
                BrowserSession.last_seen_at > moment - IDLE,
                Membership.status == "active",
                User.status == "active",
                Organization.status == "active",
            )
        ).one_or_none()
        if row is None:
            raise AccountCommerceAuthenticationRefused("active browser principal required")
        owner = reference(principal.organization_id, "owner")
        user = reference(principal.user_id, "user", maximum=64)
        session_ref = reference(principal.session_id, "browser session", maximum=64)
        return AccountAuthority(owner, user, user, session_ref)

    @staticmethod
    def canonical_fields(
        satisfied_fields: tuple[str, ...], *, required_fields: tuple[str, ...]
    ) -> tuple[tuple[str, ...], str]:
        if not isinstance(satisfied_fields, tuple) or not isinstance(required_fields, tuple):
            raise AccountCommerceRefused("profile fields must be exact tuples")
        if len(set(satisfied_fields)) != len(satisfied_fields):
            raise AccountCommerceRefused("profile fields must be unique")
        required = frozenset(required_fields)
        if any(not isinstance(item, str) or item not in required for item in satisfied_fields):
            raise AccountCommerceRefused("unknown profile field code")
        ordered = tuple(sorted(satisfied_fields))
        raw = json.dumps(ordered, ensure_ascii=True, separators=(",", ":"))
        if len(raw.encode("utf-8")) > 2048:
            raise AccountCommerceRefused("profile evidence is too large")
        return ordered, raw

    def record_profile_evidence(
        self,
        *,
        authority: AccountAuthority,
        policy_address: str,
        evidence_address: str,
        satisfied_fields: tuple[str, ...],
        required_fields: tuple[str, ...],
        attested_at: dt.datetime,
    ) -> StoredProfileEvidence:
        address(policy_address, "profile policy")
        address(evidence_address, "profile evidence")
        ordered, raw = self.canonical_fields(
            satisfied_fields, required_fields=required_fields
        )
        evidence_id = _stable_ref(
            "profile", authority.owner_ref, authority.user_ref,
            policy_address, evidence_address, raw,
        )
        existing = self.session.get(AccountProfileEvidenceRow, evidence_id)
        expected = (
            authority.owner_ref, authority.user_ref, policy_address,
            evidence_address, raw,
        )
        if existing is not None:
            actual = (
                existing.owner_ref, existing.user_ref, existing.policy_address,
                existing.evidence_address, existing.satisfied_fields_json,
            )
            if actual != expected:
                raise AccountCommerceConflict("profile evidence identity conflicts")
            return self._profile(existing)
        row = AccountProfileEvidenceRow(
            profile_evidence_id=evidence_id,
            owner_ref=authority.owner_ref,
            user_ref=authority.user_ref,
            policy_address=policy_address,
            evidence_address=evidence_address,
            satisfied_fields_json=raw,
            attested_at=_db_time(attested_at),
        )
        self.session.add(row)
        try:
            self.session.flush()
        except IntegrityError as exc:
            raise AccountCommerceConflict("profile evidence admission conflicted") from exc
        return self._profile(row)

    def profile_evidence(
        self, *, authority: AccountAuthority, policy_address: str,
        evidence_address: str | None = None,
    ) -> StoredProfileEvidence | None:
        """Return only an owner-scoped attestation, never its transient inputs."""
        query = sa.select(AccountProfileEvidenceRow).where(
            AccountProfileEvidenceRow.owner_ref == authority.owner_ref,
            AccountProfileEvidenceRow.user_ref == authority.user_ref,
            AccountProfileEvidenceRow.policy_address == policy_address,
        )
        if evidence_address is not None:
            query = query.where(
                AccountProfileEvidenceRow.evidence_address == evidence_address
            )
        query = query.order_by(
            AccountProfileEvidenceRow.attested_at.desc(),
            AccountProfileEvidenceRow.profile_evidence_id.desc(),
        )
        row = self.session.scalar(query.limit(1))
        return None if row is None else self._profile(row)

    def trial_use(
        self, *, authority: AccountAuthority, policy_address: str
    ) -> StoredTrialUse | None:
        row = self.session.scalar(sa.select(AccountTrialUseRow).where(
            AccountTrialUseRow.owner_ref == authority.owner_ref,
            AccountTrialUseRow.user_ref == authority.user_ref,
            AccountTrialUseRow.policy_address == policy_address,
        ))
        return None if row is None else self._trial(row)

    def record_trial_use(
        self,
        *,
        authority: AccountAuthority,
        profile: StoredProfileEvidence,
        policy_address: str,
        source_kind: str,
        source_ref: str,
        eligibility_authority_address: str,
        prior_use_authority_address: str,
        decision_basis_address: str,
        entitlement_code: str,
        entitlement_event_id: str,
        valid_from: dt.datetime,
        valid_until: dt.datetime,
        used_at: dt.datetime,
    ) -> StoredTrialUse:
        if (profile.owner_ref, profile.user_ref, profile.policy_address) != (
            authority.owner_ref, authority.user_ref, policy_address
        ):
            raise AccountCommerceRefused("profile evidence attribution mismatch")
        if source_kind not in {"BETA_TRIAL", "COUPON_REDEMPTION"}:
            raise AccountCommerceRefused("unsupported trial source")
        for value, label in (
            (policy_address, "trial policy"),
            (eligibility_authority_address, "eligibility authority"),
            (prior_use_authority_address, "prior-use authority"),
            (decision_basis_address, "decision basis"),
        ):
            address(value, label)
        reference(source_ref, "trial source")
        reference(entitlement_event_id, "entitlement event")
        code(entitlement_code, "entitlement code")
        start = _db_time(valid_from)
        end = _db_time(valid_until)
        if end <= start:
            raise AccountCommerceRefused("trial validity must be increasing")
        trial_id = self.trial_id_for(authority, policy_address)
        existing = self.trial_use(authority=authority, policy_address=policy_address)
        expected = (
            profile.profile_evidence_id, source_kind, source_ref,
            eligibility_authority_address, prior_use_authority_address,
            decision_basis_address, entitlement_code, "GRANT", entitlement_event_id,
            start, end,
        )
        if existing is not None:
            row = self.session.get(AccountTrialUseRow, existing.trial_use_id)
            actual = (
                row.profile_evidence_id, row.source_kind, row.source_ref,
                row.eligibility_authority_address, row.prior_use_authority_address,
                row.decision_basis_address, row.entitlement_code,
                row.entitlement_transition, row.entitlement_event_id,
                row.valid_from, row.valid_until,
            )
            if actual != expected:
                raise AccountCommerceConflict("trial was already used under this policy")
            return existing
        row = AccountTrialUseRow(
            trial_use_id=trial_id,
            owner_ref=authority.owner_ref,
            user_ref=authority.user_ref,
            policy_address=policy_address,
            profile_evidence_id=profile.profile_evidence_id,
            source_kind=source_kind,
            source_ref=source_ref,
            eligibility_authority_address=eligibility_authority_address,
            prior_use_authority_address=prior_use_authority_address,
            decision_basis_address=decision_basis_address,
            entitlement_code=entitlement_code,
            entitlement_transition="GRANT",
            entitlement_event_id=entitlement_event_id,
            valid_from=start,
            valid_until=end,
            used_at=_db_time(used_at),
        )
        self.session.add(row)
        try:
            self.session.flush()
        except IntegrityError as exc:
            raise AccountCommerceConflict("trial admission conflicted") from exc
        return self._trial(row)

    @staticmethod
    def _profile(row: AccountProfileEvidenceRow) -> StoredProfileEvidence:
        try:
            fields = json.loads(row.satisfied_fields_json)
        except (TypeError, json.JSONDecodeError) as exc:
            raise AccountCommerceConflict("stored profile evidence is invalid") from exc
        if not isinstance(fields, list) or any(not isinstance(item, str) for item in fields):
            raise AccountCommerceConflict("stored profile evidence is invalid")
        canonical = json.dumps(tuple(fields), ensure_ascii=True, separators=(",", ":"))
        if canonical != row.satisfied_fields_json or tuple(fields) != tuple(sorted(set(fields))):
            raise AccountCommerceConflict("stored profile evidence is noncanonical")
        return StoredProfileEvidence(
            row.profile_evidence_id, row.owner_ref, row.user_ref,
            row.policy_address, row.evidence_address, tuple(fields),
            _api_time(row.attested_at),
        )

    @staticmethod
    def _trial(row: AccountTrialUseRow) -> StoredTrialUse:
        return StoredTrialUse(
            row.trial_use_id, row.owner_ref, row.user_ref, row.policy_address,
            row.profile_evidence_id, row.source_kind, row.source_ref,
            row.entitlement_event_id, _api_time(row.valid_from),
            _api_time(row.valid_until),
        )


def validate_persisted_account_commerce(connection) -> None:
    """Recompute privacy and trial/source attribution after copy or restore."""
    names = set(sa.inspect(connection).get_table_names())
    required = {"account_profile_evidence", "account_trial_uses"}
    if not required <= names:
        raise AccountCommerceRefused("account-commerce table inventory is incomplete")
    profiles = {
        row["profile_evidence_id"]: row
        for row in connection.execute(
            sa.select(AccountProfileEvidenceRow.__table__)
        ).mappings()
    }
    for row in profiles.values():
        try:
            fields = json.loads(row["satisfied_fields_json"])
        except (TypeError, json.JSONDecodeError) as exc:
            raise AccountCommerceRefused("stored profile evidence is invalid") from exc
        if (not isinstance(fields, list)
                or any(not isinstance(item, str) for item in fields)
                or fields != sorted(set(fields))
                or json.dumps(tuple(fields), ensure_ascii=True, separators=(",", ":"))
                != row["satisfied_fields_json"]):
            raise AccountCommerceRefused("stored profile evidence is noncanonical")
    for row in connection.execute(sa.select(AccountTrialUseRow.__table__)).mappings():
        profile = profiles.get(row["profile_evidence_id"])
        if profile is None or (
            profile["owner_ref"], profile["user_ref"], profile["policy_address"]
        ) != (row["owner_ref"], row["user_ref"], row["policy_address"]):
            raise AccountCommerceRefused("trial profile attribution is invalid")
        event = connection.execute(sa.select(PlatformEntitlementEventRow.__table__).where(
            PlatformEntitlementEventRow.event_id == row["entitlement_event_id"],
            PlatformEntitlementEventRow.owner_ref == row["owner_ref"],
            PlatformEntitlementEventRow.entitlement_code == row["entitlement_code"],
            PlatformEntitlementEventRow.valid_from == row["valid_from"],
            PlatformEntitlementEventRow.valid_until == row["valid_until"],
        )).mappings().one_or_none()
        if event is None or event["transition"] != "GRANT" or event["mode"] != "INTERNAL":
            raise AccountCommerceRefused("trial entitlement attribution is invalid")
        if row["source_kind"] == EntitlementSource.BETA_TRIAL.value:
            exact = (
                row["source_ref"] == row["trial_use_id"]
                and event["source_kind"] == EntitlementSource.BETA_TRIAL.value
                and event["source_ref"] == row["trial_use_id"]
                and event["policy_address"] == row["policy_address"]
            )
        elif row["source_kind"] == EntitlementSource.COUPON_REDEMPTION.value:
            redemption = connection.execute(sa.select(
                PlatformCouponRedemptionRow.__table__
            ).where(
                PlatformCouponRedemptionRow.redemption_id == row["source_ref"],
                PlatformCouponRedemptionRow.owner_ref == row["owner_ref"],
                PlatformCouponRedemptionRow.status == "ACCEPTED",
            )).mappings().one_or_none()
            exact = (
                redemption is not None
                and event["source_kind"] == EntitlementSource.COUPON_REDEMPTION.value
                and event["source_ref"] == row["source_ref"]
            )
        else:
            exact = False
        if not exact:
            raise AccountCommerceRefused("trial source attribution is invalid")
    for table in (AccountProfileEvidenceRow.__table__, AccountTrialUseRow.__table__):
        text_columns = [column for column in table.columns if isinstance(column.type, sa.String)]
        for row in connection.execute(sa.select(*text_columns)):
            for column, value in zip(text_columns, row, strict=True):
                validate_persisted_text(value, f"{table.name}.{column.name}")


__all__ = [
    "AccountAuthority", "AccountCommerceConflict", "AccountCommerceRefused",
    "AccountCommerceRepository", "StoredProfileEvidence", "StoredTrialUse",
    "validate_persisted_account_commerce",
]
