"""Server-owned Strategy OS release profiles and V0 authority denial.

The profile contracts reachability.  It never creates a second strategy language,
runtime, provider model, or database truth.  V0 reuses the canonical research stack
while making the execution-shaped compatibility surface unavailable.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping


class ReleaseProfile(StrEnum):
    STANDARD = "standard"
    V0_RESEARCH_SIGNAL = "v0_research_signal"


class ReleaseServiceRole(StrEnum):
    API = "api"
    RESEARCH_WORKER = "research_worker"
    MONITOR = "monitor"
    SCHEDULER = "scheduler"


V0_SERVICE_ROLES = tuple(role.value for role in ReleaseServiceRole)

# These closed POST endpoints only validate drafts or inspect uploaded bytes.
# Keep each exception explicit; a later POST cannot escape this inventory by analogy.
V0_NONMUTATING_POST_ROUTES = frozenset({
    "/api/ir/projects/{project_id}/graphs/{identifier}/edits/validate",
    "/api/ir/projects/{project_id}/research-datasets/inspect-csv",
})

# Exact owner-scoped research mutations accepted in the legacy router inventory:
# review drawings and imported research datasets. These grant no execution authority.
# Keep method and full route template explicit so a new IR mutation cannot hide
# behind a prefix exemption.
V0_ALLOWED_RESEARCH_MUTATION_ROUTES = frozenset({
    ("POST", "/api/ir/projects/{project_id}/research-datasets/import-csv"),
    ("POST", "/api/ir/projects/{project_id}/research-datasets/from-provider"),
    ("POST", "/api/ir/projects/{project_id}/experiments/{run_id}/market-context/annotations"),
    ("PUT", "/api/ir/projects/{project_id}/experiments/{run_id}/market-context/annotations/{annotation_id}"),
    ("DELETE", "/api/ir/projects/{project_id}/experiments/{run_id}/market-context/annotations/{annotation_id}"),
})


class CapabilityState(StrEnum):
    ENABLED = "ENABLED"
    ENABLED_WITH_LIMIT = "ENABLED_WITH_LIMIT"
    INTERNAL = "INTERNAL"
    UNAVAILABLE = "UNAVAILABLE"
    BLOCKED = "BLOCKED"


class ReleaseProfileConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class DeniedRoute:
    method: str
    template: str
    capability: str
    reason: str

    @property
    def pattern(self) -> re.Pattern[str]:
        parts: list[str] = []
        position = 0
        for match in re.finditer(r"\{[^}]+\}", self.template):
            parts.append(re.escape(self.template[position:match.start()]))
            parts.append(r"[^/]+")
            position = match.end()
        parts.append(re.escape(self.template[position:]))
        return re.compile("^" + "".join(parts) + "$")

    def matches(self, method: str, path: str) -> bool:
        return (self.method == "*" or self.method == method.upper()) and bool(
            self.pattern.fullmatch(path)
        )


def _deny(method: str, template: str, capability: str, reason: str) -> DeniedRoute:
    return DeniedRoute(method, template, capability, reason)


# Complete current mutation surface of the legacy engine/portfolio/ledger routers.
# Backtest, IR, research and provider-connection mutations are deliberately absent:
# they are V0 research capabilities, not execution authority.
V0_DENIED_MUTATION_ROUTES: tuple[DeniedRoute, ...] = (
    _deny("POST", "/api/instruments/{key}/toggle", "execution_configuration", "legacy engine instrument mutation"),
    _deny("POST", "/api/portfolio/add", "execution_configuration", "legacy engine universe mutation"),
    _deny("POST", "/api/portfolio/remove", "execution_configuration", "legacy engine universe mutation"),
    _deny("POST", "/api/portfolio/add-bulk", "execution_configuration", "legacy engine universe mutation"),
    _deny("POST", "/api/instruments/{key}/interval", "execution_configuration", "legacy engine cadence mutation"),
    _deny("POST", "/api/instruments/{key}/block-entries", "execution_configuration", "entry-authority mutation"),
    _deny("POST", "/api/instruments/{key}/product", "execution_configuration", "execution-product mutation"),
    _deny("POST", "/api/instruments/{key}/priority", "execution_configuration", "execution priority mutation"),
    _deny("POST", "/api/instruments/{key}/overtrade", "execution_configuration", "execution risk mutation"),
    _deny("POST", "/api/instruments/{key}/strategy", "execution_configuration", "execution assignment mutation"),
    _deny("POST", "/api/positions/{key}/close", "positions", "position mutation"),
    _deny("POST", "/api/positions/{key}/sltp", "positions", "position protection mutation"),
    _deny("POST", "/api/positions/{key}/no-take-profit", "positions", "position protection mutation"),
    _deny("POST", "/api/execution/arm", "execution", "execution control"),
    _deny("POST", "/api/execution/kill", "execution", "execution control"),
    _deny("POST", "/api/positions/manual-open", "positions", "position creation"),
    _deny("POST", "/api/settings", "execution_configuration", "legacy runtime setting mutation"),
    _deny("POST", "/api/settings/reset", "execution_configuration", "legacy runtime setting mutation"),
    _deny("POST", "/api/ir-shadow/deployments", "deployment", "shadow deployment mutation"),
    _deny("POST", "/api/ir-shadow/deployments/{row_id}/{action}", "deployment", "shadow deployment mutation"),
    _deny("POST", "/api/ir-paper/deployments", "deployment", "paper deployment mutation"),
    _deny("POST", "/api/ir-paper/deployments/{row_id}/{action}", "deployment", "paper deployment mutation"),
    _deny("POST", "/api/ir-paper/deployments/{row_id}/retire", "deployment", "paper deployment mutation"),
    _deny("POST", "/api/portfolio/promotions/{candidate_id}/deploy", "deployment", "research-to-deployment bridge"),
    _deny("POST", "/api/portfolio/deploy", "deployment", "watchlist deployment mutation"),
    _deny("POST", "/api/portfolio/watchlists/{name}/status", "deployment", "execution watchlist lifecycle mutation"),
    _deny("POST", "/api/portfolio/archive/{strategy_key}/status", "deployment", "execution strategy lifecycle mutation"),
    _deny("PUT", "/api/ledger/snapshot", "execution_journal", "execution ledger mutation"),
    _deny("POST", "/api/ledger/artifacts", "execution_journal", "execution ledger mutation"),
    _deny("DELETE", "/api/ledger/artifacts/{artifact_id}", "execution_journal", "execution ledger mutation"),
    _deny("POST", "/api/ledger/manual-fills/{order_id}/claim", "execution_journal", "broker fill mutation"),
    _deny("POST", "/api/connections", "provider_connections", "mixed-role broker connection creation"),
    _deny("POST", "/api/connections/{connection_id}/credential", "provider_connections", "broker credential mutation"),
    _deny("DELETE", "/api/connections/{connection_id}", "provider_connections", "broker connection mutation"),
    _deny("POST", "/api/connections/{connection_id}/oauth/initiate", "provider_connections", "broker OAuth mutation"),
)


V0_DENIED_READ_ROUTES: tuple[DeniedRoute, ...] = (
    _deny("GET", "/api/status", "execution", "legacy execution-cell status"),
    _deny("GET", "/api/execution/state", "execution", "execution control state"),
    _deny("GET", "/api/positions", "positions", "execution position book"),
    _deny("GET", "/api/signals", "legacy_signals", "legacy runner signal surface"),
    _deny("GET", "/api/trades", "execution_journal", "execution trade book"),
    _deny("GET", "/api/analytics", "execution_journal", "execution analytics"),
    _deny("GET", "/api/connections", "provider_connections", "mixed-role broker connection list"),
    _deny("GET", "/api/connections/{connection_id}", "provider_connections", "mixed-role broker connection detail"),
    _deny("GET", "/api/connections/{connection_id}/login", "provider_connections", "broker login materialization"),
    _deny("GET", "/api/oauth/callback", "provider_connections", "broker OAuth token exchange"),
)

V0_DENIED_CHANNEL_ROUTES: tuple[DeniedRoute, ...] = (
    _deny("WEBSOCKET", "/ws", "execution_stream", "private execution state stream"),
    _deny("WEBSOCKET", "/ws/instrument/{key}", "execution_stream", "position-aware price stream"),
)

V0_DENIED_ROUTES = (
    V0_DENIED_MUTATION_ROUTES + V0_DENIED_READ_ROUTES + V0_DENIED_CHANNEL_ROUTES
)


_V0_CAPABILITIES = MappingProxyType({
    "strategy_graph": MappingProxyType({
        "state": CapabilityState.ENABLED.value,
        "ui_navigation": True,
    }),
    "backtesting": MappingProxyType({
        "state": CapabilityState.ENABLED_WITH_LIMIT.value,
        "ui_navigation": False,
        "reason": "the current cockpit mixes research results with execution-watchlist controls",
    }),
    "research_review": MappingProxyType({
        "state": CapabilityState.ENABLED.value,
        "ui_navigation": False,
        "reason": "available inside the canonical strategy graph surface",
    }),
    "provider_connections": MappingProxyType({
        "state": CapabilityState.BLOCKED.value,
        "ui_navigation": False,
        "reason": "data-only connection separation is owned by V0-D",
    }),
    "data_provider_onboarding": MappingProxyType({
        "state": CapabilityState.ENABLED_WITH_LIMIT.value,
        "ui_navigation": True,
        "reason": (
            "local encrypted onboarding only; provider activation, expiry, quota "
            "and readiness remain unavailable"
        ),
    }),
    "static_watchlists": MappingProxyType({
        "state": CapabilityState.ENABLED_WITH_LIMIT.value, "ui_navigation": True,
        "reason": "Saved research instrument lists, up to 32 members. Research starts for one selected member.",
    }),
    "monitoring": MappingProxyType({"state": CapabilityState.BLOCKED.value,
                                    "reason": "monitoring-only authority is owned by V0-G"}),
    "signals": MappingProxyType({"state": CapabilityState.ENABLED_WITH_LIMIT.value, "ui_navigation": True,
                                 "reason": "Stored monitoring alerts and reviews. No execution authority; new monitoring activation remains separate."}),
    "execution": MappingProxyType({"state": CapabilityState.UNAVAILABLE.value}),
    "orders": MappingProxyType({"state": CapabilityState.UNAVAILABLE.value}),
    "positions": MappingProxyType({"state": CapabilityState.UNAVAILABLE.value}),
    "execution_stream": MappingProxyType({"state": CapabilityState.UNAVAILABLE.value}),
    "capital_admission": MappingProxyType({"state": CapabilityState.INTERNAL.value}),
})

_V0_ROUTE_RULES = tuple(MappingProxyType({
    "method": route.method,
    "template": route.template,
    "state": CapabilityState.UNAVAILABLE.value,
    "capability": route.capability,
    "reason": route.reason,
}) for route in V0_DENIED_ROUTES)


def parse_release_profile(value: str) -> ReleaseProfile:
    try:
        return ReleaseProfile((value or "").strip().lower())
    except ValueError as exc:
        raise ReleaseProfileConfigurationError(
            "PT_RELEASE_PROFILE must be exactly standard or v0_research_signal"
        ) from exc


def is_v0_profile(value: str) -> bool:
    return parse_release_profile(value) is ReleaseProfile.V0_RESEARCH_SIGNAL


def parse_release_service_role(value: str) -> ReleaseServiceRole:
    try:
        return ReleaseServiceRole((value or "").strip().lower())
    except ValueError as exc:
        raise ReleaseProfileConfigurationError(
            "PT_RELEASE_SERVICE_ROLE must be exactly api, research_worker, monitor, or scheduler"
        ) from exc


def required_readiness_planes(role: ReleaseServiceRole) -> tuple[str, ...]:
    if role is ReleaseServiceRole.API:
        return ("execution", "ledger", "research")
    return ("execution", "research")


def validate_boot(settings: Any) -> ReleaseProfile:
    profile = parse_release_profile(settings.release_profile)
    if profile is ReleaseProfile.STANDARD:
        return profile
    role = parse_release_service_role(settings.release_service_role)
    violations: list[str] = []
    if settings.service_role.strip().lower() not in {"development", "test", role.value}:
        violations.append(
            "PT_SERVICE_ROLE must be development/test or match PT_RELEASE_SERVICE_ROLE"
        )
    if settings.execution_worker.strip().lower() != "api":
        violations.append("PT_EXECUTION_WORKER=api")
    if not settings.research_enabled:
        violations.append("PT_RESEARCH_ENABLED=1")
    if settings.execution.strip().lower() != "paper":
        violations.append("PT_EXECUTION=paper")
    if settings.live_ack.strip():
        violations.append("PT_LIVE_ACK must be empty")
    if settings.execution_provider.strip():
        violations.append("PT_EXECUTION_PROVIDER must be empty")
    if settings.execution_connection.strip():
        violations.append("PT_EXECUTION_CONNECTION must be empty")
    identities = (
        settings.execution_owner_id.strip(),
        settings.execution_broker_account_id.strip(),
        settings.execution_cell_id.strip(),
    )
    if any(identities):
        violations.append("execution owner/account/cell assignment must be empty")
    if violations:
        raise ReleaseProfileConfigurationError(
            "V0_RESEARCH_SIGNAL refuses execution authority: " + "; ".join(violations)
        )
    return profile


def denied_route(profile_value: str, method: str, unversioned_path: str) -> DeniedRoute | None:
    if not is_v0_profile(profile_value):
        return None
    return next(
        (route for route in V0_DENIED_ROUTES if route.matches(method, unversioned_path)),
        None,
    )


def refusal_payload(route: DeniedRoute) -> dict[str, str]:
    return {
        "code": "V0_CAPABILITY_UNAVAILABLE",
        "release_profile": ReleaseProfile.V0_RESEARCH_SIGNAL.value,
        "capability": route.capability,
        "message": f"{route.capability} is unavailable in the V0 research/signal profile",
    }


def manifest(
    profile_value: str, *, research_enabled: bool, service_role: str = "api"
) -> Mapping[str, Any]:
    profile = parse_release_profile(profile_value)
    if profile is ReleaseProfile.STANDARD:
        capabilities: Mapping[str, Any] = MappingProxyType({
            "legacy_application": MappingProxyType({"state": CapabilityState.ENABLED.value}),
        })
        current_role = None
        roles = ("api", "execution_worker")
        required_planes: tuple[str, ...] = ()
    else:
        current = parse_release_service_role(service_role)
        capabilities = _V0_CAPABILITIES
        current_role = current.value
        roles = V0_SERVICE_ROLES
        required_planes = required_readiness_planes(current)
    return MappingProxyType({
        "schema": "strategy-os-release-profile/1",
        "release_profile": profile.value,
        "research_enabled": bool(research_enabled),
        "service_role": current_role,
        "allowed_service_roles": roles,
        "required_readiness_planes": required_planes,
        "capabilities": capabilities,
        "route_rules": _V0_ROUTE_RULES if profile is ReleaseProfile.V0_RESEARCH_SIGNAL else (),
        "execution_authority": False if profile is ReleaseProfile.V0_RESEARCH_SIGNAL else None,
    })
