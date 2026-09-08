"""HTTP route classification using the existing closed capability names.

Order is deliberate: exact routes and registered project shapes precede legacy
substring families. Resource ownership and permission policy remain elsewhere.
"""
from __future__ import annotations

import re


_EXACT_ACTIONS = {
    "/api/paper-portfolio": {"GET": "read:portfolio"},
    "/api/account-commerce/access": {"GET": "read:account-commerce"},
    "/api/account-commerce/status": {"GET": "read:account-commerce"},
    "/api/account-commerce/billing/subscription": {"GET": "read:account-commerce"},
    "/api/account-commerce/profile-evidence": {"POST": "write:account-commerce"},
    "/api/account-commerce/trials/beta": {"POST": "write:account-commerce"},
    "/api/account-commerce/trials/coupon": {"POST": "write:account-commerce"},
    "/api/account-commerce/billing/checkout": {"POST": "write:account-commerce"},
    "/api/account-commerce/billing/payment": {"POST": "write:account-commerce"},
    "/api/account-commerce/billing/refund": {"POST": "write:account-commerce"},
    "/api/ir/catalogue": {"GET": "read:project"},
    "/api/ir/presets": {"GET": "read:project"},
    "/api/brokers": {"GET": "read:brokers"},
    "/api/data-connections/status": {"GET": "read:connections"},
    "/api/data-connections/instruments": {"GET": "read:connections"},
    "/api/data-connections/instrument-selections": {"POST": "create:connection"},
    "/api/data-connections/instruments/resolve": {"POST": "create:connection"},
    "/api/account-risk-settings": {"GET": "read:runtime-config", "POST": "write:runtime-config"},
    "/api/data-connections": {"POST": "create:connection", "DELETE": "revoke:connection"},
    "/api/data-connections/app-keys": {"POST": "write:credential"},
    "/api/data-connections/app-keys/rotate": {"POST": "write:credential"},
    "/api/data-connections/oauth/initiate": {"POST": "write:credential"},
    "/api/data-connections/oauth/callback": {},
    "/api/connections": {"GET": "read:connections", "POST": "create:connection"},
    "/api/settings": {"GET": "read:runtime-config", "*": "write:runtime-config"},
    "/api/settings/reset": {"*": "write:runtime-config"},
}
_EXECUTION_EXACT = frozenset({
    "/api/status", "/api/calendar", "/api/login", "/api/session", "/api/instruments",
    "/api/trades", "/api/signals", "/api/account-pnl", "/api/dashboard",
    "/api/positions", "/api/provider-health", "/api/execution/state",
    "/api/execution/arm", "/api/execution/kill", "/api/execution/events",
    "/api/execution/cockpit", "/api/execution/cockpit/deployments",
    "/api/ir-shadow/deployments", "/api/ir-paper/deployments",
})
_EXECUTION_PREFIXES = (
    "/api/ledger/", "/api/positions/", "/api/instruments/",
    "/api/ir-shadow/deployments/", "/api/ir-paper/deployments/",
)
_PORTFOLIO_EXACT = frozenset({
    "/api/portfolio/promotions", "/api/portfolio/deploy",
    "/api/portfolio/watchlists", "/api/portfolio/archive",
})
_PORTFOLIO_PREFIXES = (
    "/api/portfolio/promotions/", "/api/portfolio/watchlists/", "/api/portfolio/archive/",
)
_STATIC_READ = re.compile(r"/api/ir/projects/[^/]+/static-scopes(?:/[^/]+(?:/revisions/[^/]+|/monitoring-rows)?)?$")
_STATIC_WRITE = re.compile(r"/api/ir/projects/[^/]+/static-scopes(?:/[^/]+/(?:revisions|archive|monitoring-rows))?$")
_RESEARCH_POST = re.compile(
    r"/api/ir/projects/[^/]+/graphs/[^/]+/versions/[^/]+/research-(?:preparations(?:/from-settings|/from-inputs)?|operations)$"
)
_MONITORING_READ = re.compile(r"/api/monitoring/(?:alerts|assignments/[^/]+/alerts/[^/]+(?:/review)?)$")
_MONITORING_WRITE = re.compile(r"/api/monitoring/assignments/[^/]+/alerts/[^/]+/(?:attention|review)$")


def classify_request(method: str, path: str) -> str | None:
    method = method.upper()
    if path.startswith("/api/monitoring/"):
        return _monitoring_action(method, path)
    if path in _EXACT_ACTIONS:
        actions = _EXACT_ACTIONS[path]
        return actions.get(method, actions.get("*"))
    if path.startswith("/api/connections/"):
        return _connection_action(method, path)
    if path in _EXECUTION_EXACT or path.startswith(_EXECUTION_PREFIXES):
        return _execution_action(method, path)
    return _user_action(method, path)


def _monitoring_action(method, path):
    if method == "GET" and _MONITORING_READ.fullmatch(path):
        return "read:review"
    if method == "POST" and _MONITORING_WRITE.fullmatch(path):
        return "write:review"
    return None


def _connection_action(method: str, path: str) -> str | None:
    if path.endswith(("/credential", "/oauth/initiate")):
        return "write:credential" if method == "POST" else None
    if path.endswith("/login"):
        return "read:connection" if method == "GET" else None
    return {"GET": "read:connection", "DELETE": "revoke:connection"}.get(method)


def _execution_action(method: str, path: str) -> str:
    if method == "GET" and path not in {"/api/login", "/api/session"}:
        return "read:execution"
    return "authoritative:execution"


def _user_action(method: str, path: str) -> str | None:
    if path.startswith("/api/backtest"):
        return "read:backtest" if method == "GET" else "write:backtest"
    if path.startswith("/api/research/operations"):
        return "read:research" if method == "GET" else "start:research"
    if path.startswith("/api/ir/graphs/") and "/layout" in path:
        return "read:layout" if method == "GET" else "write:layout"
    if path.startswith("/api/portfolio"):
        return _portfolio_action(method, path)
    return _project_action(method, path)


def _portfolio_action(method: str, path: str) -> str | None:
    if path not in _PORTFOLIO_EXACT and not path.startswith(_PORTFOLIO_PREFIXES):
        # Unconverted runner endpoints remain denied to durable users.
        return None
    if method == "GET":
        return "read:portfolio"
    if "/watchlists/" in path:
        return "write:watchlist"
    if "/archive/" in path:
        return "archive:strategy"
    return "write:watchlist"


def _research_settings_path(path: str) -> bool:
    return path == "/api/research-settings" or (
        path.startswith("/api/ir/projects/") and path.endswith("/research-settings"))


def _project_action(method: str, path: str) -> str | None:
    if _research_settings_path(path):
        return {"GET": "read:research", "PUT": "start:research"}.get(method)
    if not path.startswith("/api/ir/projects/") and path != "/api/ir/projects":
        return None
    shape_action = _project_shape_action(method, path)
    if shape_action is not None:
        return shape_action
    return _project_resource_action(method, path)


def _project_shape_action(method: str, path: str) -> str | None:
    # Keep the registered routes' $ anchor, including terminal-newline behavior.
    if method == "GET" and _STATIC_READ.match(path):
        return "read:project"
    if method == "POST" and _STATIC_WRITE.match(path):
        return "write:project"
    if method == "POST" and _RESEARCH_POST.match(path):
        return "start:research"
    return None


def _project_resource_action(method: str, path: str) -> str:
    if "/review" in path:
        return "read:review" if method == "GET" else "write:review"
    if "/candidates/" in path and path.endswith("/decisions"):
        return "decision:research"
    if any(part in path for part in ("/experiments", "/findings", "/version-comparisons")):
        return _research_action(method, path)
    return _graph_or_project_action(method, path)


def _research_action(method: str, path: str) -> str:
    if method == "GET":
        return "read:research"
    return "compare:research" if "compar" in path else "start:research"


def _graph_or_project_action(method: str, path: str) -> str:
    if "/layouts" in path or "/presentation-edits" in path:
        return "read:layout" if method == "GET" else "write:layout"
    if "/graphs" in path:
        return _graph_action(method, path)
    if path.endswith("/status"):
        return "archive:project"
    return "read:project" if method == "GET" else "write:project"


def _graph_action(method: str, path: str) -> str:
    if method == "GET":
        return "read:graph"
    return "publish:graph" if path.endswith("/versions") else "write:graph"
