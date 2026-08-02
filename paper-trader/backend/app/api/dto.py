"""H3 (Phase H) — explicit response contracts for the API surface.

The audit's complaint is not that responses are wrong, it is that they are
*implicit*: routes return bare dicts assembled inline, so the wire format is
whatever the code happened to build that day, and internal engine fields ride
along by accident. A DTO here is a written-down promise about a payload —
something a client, an SDK generator, or a future `/api/v2` can be diffed against.

Scope of THIS phase: define the contracts and prove they match what production
actually serves (see `tests/test_api_versioning.py`, which validates the live
`/api/health` body against `HealthResponse` — a DTO nothing validates is a
docstring with extra syntax). Routes are NOT rewritten to declare
`response_model=` here, deliberately: `routes.py` is owned by other phases right
now, and swapping a hand-built dict for a response model silently drops any
undeclared key, which is a behaviour change on a live surface.

`extra="allow"` throughout for the same reason: these DTOs describe the keys that
are PROMISED, and a payload with extra keys must validate rather than fail. That
is what makes them safe to tighten later — flip to `extra="forbid"` in the phase
that actually migrates the route, and the test tells you what leaked.

────────────────────────────────────────────────────────────────────────────
INTERNAL STATE ON THE PUBLIC SURFACE — inventory for the phase that fixes it
────────────────────────────────────────────────────────────────────────────
Documented here, NOT fixed here (fixing it means editing `routes.py` and
`runner.py`, both owned elsewhere this phase). Each of these serialises engine
internals straight to any client:

* `GET /api/status` (`routes.py`) — returns `capital` from
  `analytics.capital_dict()` plus runner attributes (`tick`, `running`, `armed`)
  chosen ad hoc. No declared shape; the cockpit reads it by key.
* The `state` WebSocket message (`main.py` `on_update` → `runner.state`) — this
  is the worst one. `runner.state[key]` is the runner's own scratch dict and it
  carries `_ratchet_atr` (`runner.py:454`), an underscore-prefixed
  implementation detail of the ATR trailing stop, out to every connected
  browser. Anything a future refactor puts in `runner.state` is published the
  same way, with no review step.
* `GET /api/instrument/{key}` — same `runner.state` slice, same leak.
* `GET /api/positions` — ORM-shaped rows; resource identity is the instrument
  key, which C1 is going to re-key.
* `POST /api/portfolio/deploy` — returns two DIFFERENT shapes depending on
  `dry_run` (`watchlist` vs `watchlist_id`), which is why `DeploymentSummary`
  below exists as one shape with an adapter.

The migration for each is the same three steps: define the DTO here, build it
explicitly in the route, then flip to `extra="forbid"` and let the test find
whatever was riding along.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class _Dto(BaseModel):
    # See module docstring: additive keys must not break validation while both
    # the old dicts and these contracts coexist.
    model_config = ConfigDict(extra="allow")


# ── /api/health ────────────────────────────────────────────────────────────
# The one payload with an existing external contract worth freezing NOW:
# `scripts/deploy.sh` parses `build.commit`, and the readiness verdict decides
# whether a box stays in rotation. Both are load-bearing outside this codebase,
# so their shape is a promise, not an implementation detail.

class BuildInfo(_Dto):
    """`app/core/version.py:get_build_info`. `commit` is 'unknown' — never null —
    when a process could not read its VERSION file; the distinction is
    load-bearing (see CLAUDE.md on `build_sha`)."""
    commit: str
    branch: str | None = None
    deployed_at: str | None = None
    deployed_by: str | None = None


class SchemaInfo(_Dto):
    """`app/db/migrate.py:schema_state`. All three fields go null when the probe
    itself failed, which is why none of them are required."""
    current: str | None = None
    head: str | None = None
    up_to_date: bool | None = None
    error: str | None = None


class HealthCheck(_Dto):
    """One readiness check. Passing checks are included on purpose: a probe body
    that lists only failures cannot be used to prove something was verified."""
    name: str
    ok: bool
    fatal: bool
    detail: str = ""


class LoopHealth(_Dto):
    """A runner lane. `age_seconds` is null when the lane has never beaten —
    distinct from 0, and the reason `state` exists as a separate word."""
    age_seconds: float | None = None
    state: str
    budget_seconds: float | None = None
    fatal: bool | None = None


class DbHealth(_Dto):
    ok: bool
    error: str = ""


class EngineHealth(_Dto):
    present: bool
    armed: bool | None = None
    provider: str | None = None


class HealthResponse(_Dto):
    """The full `/api/health` body.

    Every field below `status` is optional because the endpoint has a documented
    degenerate branch: when the readiness probe itself raises, `main.py` answers
    a reduced payload rather than a 500. A DTO that could not describe that
    branch would be describing a payload the endpoint does not always emit.
    """
    ok: bool
    ready: bool
    status: Literal["ok", "starting", "degraded", "unready"]
    build: BuildInfo | None = None
    schema_: SchemaInfo | None = Field(default=None, alias="schema")
    uptime_seconds: float | None = None
    db: DbHealth | None = None
    loops: dict[str, LoopHealth] = Field(default_factory=dict)
    markets_open: bool | None = None
    checks: list[HealthCheck] = Field(default_factory=list)
    failed_checks: list[str] = Field(default_factory=list)
    degraded_checks: list[str] = Field(default_factory=list)
    engine: EngineHealth | None = None
    provider_health: dict[str, Any] = Field(default_factory=dict)
    provider_feed: dict[str, Any] = Field(default_factory=dict)

    # `schema` shadows BaseModel.schema on pydantic v1-era APIs, hence the
    # aliased field name. Population by alias so both the JSON key and the
    # python attribute work.
    model_config = ConfigDict(extra="allow", populate_by_name=True)


# ── deployments ────────────────────────────────────────────────────────────

class DeploymentSummary(_Dto):
    """One deployed strategy assignment, as ONE shape.

    Why this DTO and not just "whatever /api/portfolio/deploy returns": that
    route returns `{"dry_run": True, "watchlist": ...}` on preview and
    `{"dry_run": False, "watchlist_id": ...}` on commit — two payloads from one
    endpoint, differing in the identity field. A client has to branch on
    `dry_run` to learn what it is even looking at. Phase 13 ("per-deployment
    dashboards", thousands of deployments) needs a deployment to be one
    addressable thing with one shape; this is that shape, stated before the
    volume arrives.

    CONCURRENT WORK, read before extending: a `Deployment` DB entity is landing
    in `app/core/deployments.py` (C1) in a parallel phase. This DTO is the WIRE
    shape and is deliberately built from the CURRENT route payload — it is not a
    serializer for that entity, and it must not become one by accident. When C1
    settles, the right move is to add the entity's identity field here
    (`deployment_id`) and delete `from_legacy_payload`, not to mirror the ORM.

    `staged` is not decoration: a committed deploy writes declarative config that
    takes effect on the NEXT ENGINE RESTART, after which the owner re-ARMs.
    Nothing here places an order. A summary that omitted that would read as
    "live" and it is not.
    """
    watchlist: str
    strategy_key: str
    watchlist_id: int | None = None
    dry_run: bool = False
    staged: bool = True
    accepted: list[Any] = Field(default_factory=list)
    rejected: list[Any] = Field(default_factory=list)
    note: str | None = None

    @classmethod
    def from_legacy_payload(cls, payload: dict[str, Any]) -> "DeploymentSummary":
        """Adapter over today's two-shaped `/api/portfolio/deploy` response.

        Lives here rather than in the route so the route stays untouched this
        phase. When the route is migrated it should BUILD this DTO directly and
        this adapter should be deleted — an adapter that outlives its migration
        becomes a second source of truth for the shape.
        """
        return cls(
            watchlist=payload.get("watchlist") or payload.get("watchlist_name") or "",
            strategy_key=payload.get("strategy_key") or "",
            watchlist_id=payload.get("watchlist_id"),
            dry_run=bool(payload.get("dry_run")),
            # A preview reports `accepted`; a commit reports `assigned`. Same
            # thing under two names — another symptom of the missing contract.
            accepted=list(payload.get("accepted") or payload.get("assigned") or []),
            rejected=list(payload.get("rejected") or []),
            note=payload.get("note"),
        )
