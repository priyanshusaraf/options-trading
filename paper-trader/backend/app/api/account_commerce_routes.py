"""Direct-V1 unpublished account-commerce routes with no provider authority."""
from __future__ import annotations

import datetime as dt
import json
import unicodedata
from dataclasses import dataclass
from typing import Callable, Protocol

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.account_commerce.repository import (
    AccountCommerceAuthenticationRefused,
    AccountCommerceConflict,
    AccountCommerceRefused,
)
from app.account_commerce.service import (
    AccountCommerceService,
    ServerProfileAttestation,
)
from app.accounts import browser_auth
from app.api.principal import Principal
from app.billing.policy_contracts import CouponPolicy, EntitlementPolicy


_PREFIX = "/api/v1/account-commerce"
_MAX_BODY_BYTES = 4096
_PROFILE_FIELDS = frozenset({"profile.country", "profile.full_name"})
_TRIAL_ATTEMPTS = 3
_COUNTRIES = frozenset("""
AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL BM BN BO BQ BR BS BT BV BW BY BZ CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV CW CX CY CZ DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO FR GA GB GD GE GF GG GH GI GL GM GN GP GQ GR GS GT GU GW GY HK HM HN HR HT HU ID IE IL IM IN IO IQ IR IS IT JE JM JO JP KE KG KH KI KM KN KP KR KW KY KZ LA LB LC LI LK LR LS LT LU LV LY MA MC MD ME MF MG MH MK ML MM MN MO MP MQ MR MS MT MU MV MW MX MY MZ NA NC NE NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL PM PN PR PS PT PW PY QA RE RO RS RU RW SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS ST SV SX SY SZ TC TD TF TG TH TJ TK TL TM TN TO TR TT TV TW TZ UA UG UM US UY UZ VA VC VE VG VI VN VU WF WS YE YT ZA ZM ZW
""".split())


@dataclass(frozen=True, slots=True)
class ProfileInput:
    full_name: str
    country: str


@dataclass(frozen=True, slots=True)
class TrialEligibility:
    eligible: bool
    eligibility_authority_address: str
    prior_use_authority_address: str
    revocation_authority_address: str


class ProfileAttestor(Protocol):
    def __call__(
        self, principal: Principal, profile: ProfileInput | None,
    ) -> ServerProfileAttestation: ...


def _json(body: dict, status: int = 200) -> JSONResponse:
    return JSONResponse(body, status_code=status, headers={"Cache-Control": "no-store"})


def _authentication(status: int) -> JSONResponse:
    return _json({"error": "authentication refused"}, status)


def _request_invalid() -> JSONResponse:
    return _json({
        "code": "ACCOUNT_COMMERCE_REQUEST_INVALID",
        "message": "Account request is invalid",
    }, 400)


def _conflict() -> JSONResponse:
    return _json({
        "code": "ACCOUNT_COMMERCE_CONFLICT",
        "message": "Account request conflicts with existing state",
    }, 409)


def _unavailable() -> JSONResponse:
    return _json({
        "code": "ACCOUNT_COMMERCE_UNAVAILABLE",
        "message": "Account service is unavailable",
    }, 503)


def _billing_unavailable() -> JSONResponse:
    return _json({
        "code": "BILLING_PROVIDER_UNAVAILABLE",
        "message": "Billing provider is unavailable",
    }, 503)


def _utc(value: dt.datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        raise ValueError("server datetime must be timezone-aware")
    return value.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _browser_request(request: Request, *, mutation: bool) -> Principal:
    principal = getattr(request.state, "principal", None)
    if (
        type(principal) is not Principal
        or principal.kind != "user"
        or not principal.authenticated
        or not principal.user_id
        or principal.id != principal.user_id
        or not principal.organization_id
        or not principal.session_id
    ):
        raise browser_auth.AuthRefusal()
    token = browser_auth.cookie_token(request)
    if token is None:
        raise browser_auth.AuthRefusal()
    if mutation:
        browser_auth.check_csrf(request, token)
    else:
        browser_auth.check_origin(request, mutation=False)
    return principal


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON key")
        value[key] = item
    return value


async def _body(request: Request, fields: frozenset[str]) -> dict:
    if request.headers.getlist("content-type") != ["application/json"]:
        raise ValueError("invalid media type")
    raw = bytearray()
    async for chunk in request.stream():
        if len(raw) + len(chunk) > _MAX_BODY_BYTES:
            raise ValueError("request too large")
        raw.extend(chunk)
    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"), object_pairs_hook=_unique_object
        )
    except (UnicodeError, ValueError, RecursionError):
        raise ValueError("invalid JSON") from None
    if type(value) is not dict or frozenset(value) != fields:
        raise ValueError("invalid object")
    return value


async def _no_get_body(request: Request) -> None:
    async for chunk in request.stream():
        if chunk:
            raise ValueError("GET body refused")


def _profile_input(value: dict) -> ProfileInput:
    full_name = value.get("full_name")
    country = value.get("country")
    if type(full_name) is not str or type(country) is not str:
        raise ValueError("profile fields must be strings")
    try:
        normalized_name = unicodedata.normalize("NFC", full_name.strip())
        encoded = normalized_name.encode("utf-8", errors="strict")
    except UnicodeError:
        raise ValueError("invalid profile text") from None
    if (
        not encoded
        or len(normalized_name) > 128
        or any(ord(character) < 32 or 127 <= ord(character) <= 159
               for character in normalized_name)
        or country not in _COUNTRIES
        or len(country) != 2
        or country != country.upper()
    ):
        raise ValueError("invalid profile fields")
    return ProfileInput(normalized_name, country)


def _coupon(value: dict) -> str:
    coupon = value.get("coupon")
    if type(coupon) is not str:
        raise ValueError("coupon must be a string")
    try:
        size = len(coupon.encode("utf-8", errors="strict"))
    except UnicodeError:
        raise ValueError("invalid coupon") from None
    if not 1 <= size <= 256:
        raise ValueError("invalid coupon")
    return coupon


def _retryable_trial_error(exc: Exception) -> bool:
    if isinstance(exc, AccountCommerceConflict):
        return str(exc) in {
            "profile evidence admission conflicted",
            "trial admission conflicted",
        }
    if isinstance(exc, OperationalError):
        message = str(exc.orig).lower()
        return "database is locked" in message or "database table is locked" in message
    return False


def _access_body(access, evaluated_at: dt.datetime) -> dict:
    return {
        "schema": "account-commerce-access/1",
        "state": _public_access_state(access.state),
        "expires_at": _utc(access.valid_until),
        "evaluated_at": _utc(evaluated_at),
    }


def _public_access_state(state: str) -> str:
    """Present a valid no-row authority fact without publishing UNKNOWN."""
    if type(state) is not str:
        raise ValueError("invalid internal access state")
    if state == "UNKNOWN":
        return "INACTIVE"
    if state in {"ACTIVE", "INACTIVE", "EXPIRED"}:
        return state
    raise ValueError("invalid internal access state")


def build_account_commerce_router(
    *,
    sessionmaker: Callable,
    policy: EntitlementPolicy,
    clock: Callable[[], dt.datetime],
    profile_attestor: ProfileAttestor,
    eligibility_resolver: Callable[[Principal], TrialEligibility],
    coupon_policy_resolver: Callable[[Principal, str], CouponPolicy],
    coupon_proof_resolver: Callable[[Principal, str], str],
) -> APIRouter:
    """Build the sealed local router without registering or version mirroring it."""
    dependencies = (
        sessionmaker, clock, profile_attestor, eligibility_resolver,
        coupon_policy_resolver, coupon_proof_resolver,
    )
    if not isinstance(policy, EntitlementPolicy) or any(
        not callable(item) for item in dependencies
    ):
        raise TypeError("exact account-commerce dependencies required")
    router = APIRouter(prefix=_PREFIX, tags=["account-commerce"])

    # These routes deliberately have no auth, body, service or provider dependency.
    @router.post("/billing/checkout")
    async def billing_checkout(_request: Request):
        return _billing_unavailable()

    @router.post("/billing/payment")
    async def billing_payment(_request: Request):
        return _billing_unavailable()

    @router.get("/billing/subscription")
    async def billing_subscription(_request: Request):
        return _billing_unavailable()

    @router.post("/billing/refund")
    async def billing_refund(_request: Request):
        return _billing_unavailable()

    @router.get("/access")
    async def access(request: Request):
        try:
            await _no_get_body(request)
            principal = _browser_request(request, mutation=False)
            now = clock()
            with sessionmaker() as session:
                result = AccountCommerceService(
                    session, principal=principal, policy=policy
                ).current_access(server_time=now)
            return _json(_access_body(result, now))
        except browser_auth.AuthRefusal as exc:
            return _authentication(exc.status)
        except AccountCommerceAuthenticationRefused:
            return _authentication(401)
        except ValueError:
            return _request_invalid()
        except (SQLAlchemyError, MemoryError):
            return _unavailable()
        except Exception:
            return _unavailable()

    @router.get("/status")
    async def status(request: Request):
        try:
            await _no_get_body(request)
            principal = _browser_request(request, mutation=False)
            now = clock()
            with sessionmaker() as session:
                result = AccountCommerceService(
                    session, principal=principal, policy=policy
                ).current_status(server_time=now)
            complete = frozenset(result.profile.satisfied_field_codes) == _PROFILE_FIELDS
            if result.trial_source is None:
                trial_state = "AVAILABLE"
            elif now < result.trial_valid_until:
                trial_state = "USED_ACTIVE"
            else:
                trial_state = "USED_EXPIRED"
            return _json({
                "schema": "account-commerce-status/1",
                "profile_state": "COMPLETE" if complete else "INCOMPLETE",
                "satisfied_field_codes": list(result.profile.satisfied_field_codes),
                "profile_attested_at": _utc(result.profile.attested_at),
                "trial_state": trial_state,
                "trial_source": result.trial_source,
                "trial_expires_at": _utc(result.trial_valid_until),
                "access_state": _public_access_state(result.access.state),
                "access_expires_at": _utc(result.access.valid_until),
                "evaluated_at": _utc(now),
            })
        except browser_auth.AuthRefusal as exc:
            return _authentication(exc.status)
        except AccountCommerceAuthenticationRefused:
            return _authentication(401)
        except ValueError:
            return _request_invalid()
        except (SQLAlchemyError, MemoryError):
            return _unavailable()
        except Exception:
            return _unavailable()

    @router.post("/profile-evidence")
    async def profile_evidence(request: Request):
        try:
            principal = _browser_request(request, mutation=True)
            profile = _profile_input(await _body(request, frozenset({"full_name", "country"})))
            now = clock()
            with sessionmaker() as session:
                AccountCommerceService(
                    session, principal=principal, policy=policy
                ).validate_browser(server_time=now)
            attestation = profile_attestor(principal, profile)
            with sessionmaker() as session:
                result = AccountCommerceService(
                    session, principal=principal, policy=policy
                ).record_profile(attestation=attestation, server_time=now)
            complete = frozenset(result.satisfied_field_codes) == _PROFILE_FIELDS
            return _json({
                "schema": "account-commerce-profile-evidence/1",
                "profile_state": "COMPLETE" if complete else "INCOMPLETE",
                "satisfied_field_codes": list(result.satisfied_field_codes),
                "attested_at": _utc(result.attested_at),
                "replayed": result.replayed,
            })
        except browser_auth.AuthRefusal as exc:
            return _authentication(exc.status)
        except AccountCommerceAuthenticationRefused:
            return _authentication(401)
        except AccountCommerceConflict:
            return _conflict()
        except AccountCommerceRefused:
            return _conflict()
        except ValueError:
            return _request_invalid()
        except (SQLAlchemyError, MemoryError):
            return _unavailable()
        except Exception:
            return _unavailable()

    async def _trial(request: Request, coupon_plaintext: str | None):
        try:
            principal = _browser_request(request, mutation=True)
            if coupon_plaintext is None:
                await _body(request, frozenset())
            else:
                coupon_plaintext = _coupon(
                    await _body(request, frozenset({"coupon"}))
                )
            now = clock()
            with sessionmaker() as session:
                AccountCommerceService(
                    session, principal=principal, policy=policy
                ).validate_browser(server_time=now)
            attestation = profile_attestor(principal, None)
            eligibility = eligibility_resolver(principal)
            if type(eligibility) is not TrialEligibility:
                raise TypeError("invalid server eligibility")
            coupon_policy = None
            proof = None
            if coupon_plaintext is not None:
                coupon_policy = coupon_policy_resolver(principal, coupon_plaintext)
                proof = coupon_proof_resolver(principal, coupon_plaintext)
            identity_race = False
            for attempt in range(_TRIAL_ATTEMPTS):
                try:
                    with sessionmaker() as session:
                        service = AccountCommerceService(
                            session, principal=principal, policy=policy
                        )
                        before = service.current_status(server_time=now).trial_source
                        if coupon_plaintext is None:
                            result = service.grant_beta_trial(
                                attestation=attestation,
                                eligibility_authority_address=(
                                    eligibility.eligibility_authority_address
                                ),
                                prior_use_authority_address=(
                                    eligibility.prior_use_authority_address
                                ),
                                revocation_authority_address=(
                                    eligibility.revocation_authority_address
                                ),
                                eligible=eligibility.eligible,
                                server_time=now,
                            )
                        else:
                            result = service.grant_coupon_trial(
                                coupon_plaintext=coupon_plaintext,
                                coupon_policy=coupon_policy,
                                coupon_proof_address=proof,
                                attestation=attestation,
                                eligibility_authority_address=(
                                    eligibility.eligibility_authority_address
                                ),
                                prior_use_authority_address=(
                                    eligibility.prior_use_authority_address
                                ),
                                revocation_authority_address=(
                                    eligibility.revocation_authority_address
                                ),
                                eligible=eligibility.eligible,
                                server_time=now,
                            )
                    break
                except (AccountCommerceConflict, OperationalError) as exc:
                    if attempt + 1 == _TRIAL_ATTEMPTS or not _retryable_trial_error(exc):
                        raise
                    identity_race = identity_race or isinstance(
                        exc, AccountCommerceConflict
                    )
            return _json({
                "schema": "account-commerce-trial-grant/1",
                "source": result.source_kind,
                "state": "ACTIVE" if now < result.valid_until else "EXPIRED",
                "expires_at": _utc(result.valid_until),
                "replayed": before is not None or identity_race,
            })
        except browser_auth.AuthRefusal as exc:
            return _authentication(exc.status)
        except AccountCommerceAuthenticationRefused:
            return _authentication(401)
        except AccountCommerceConflict:
            return _conflict()
        except AccountCommerceRefused:
            return _conflict()
        except ValueError:
            return _request_invalid()
        except (SQLAlchemyError, MemoryError):
            return _unavailable()
        except Exception:
            return _unavailable()

    @router.post("/trials/beta")
    async def beta_trial(request: Request):
        return await _trial(request, None)

    @router.post("/trials/coupon")
    async def coupon_trial(request: Request):
        return await _trial(request, "unparsed")

    return router


__all__ = [
    "ProfileInput", "TrialEligibility", "build_account_commerce_router",
]
