"""Deployment service — the lifecycle of the primary execution object.

A Deployment is "this strategy, at this version, with these parameters, on this
account, over this universe, with this allocation, armed or not". Before Phase B
that sentence had no subject: the system had one implicit book whose identity was
scattered across per-instrument config, watchlists, global settings and a boolean
on the runner.

Two rules hold everything together and are enforced here rather than by convention:

  * **The legacy deployment always exists and is never deleted.** Every row written
    before Phase B refers to it, and `deployment_id` is NOT NULL. Removing it would
    orphan the entire money record.

  * **The legacy deployment resolves exactly as the system did before.**
    `universe_mode='legacy'`, `strategy_key=NULL`, `allocation=NULL`. Callers that
    do not know about deployments get this one and see no change.

Every function takes an explicit `session` — same convention as `core/watchlists.py`,
and for the same reason: no module-level engine binding, so nothing here can open a
second connection to the live ledger.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json

from sqlalchemy import select

from app.db.models import BrokerAccount, LEGACY_DEPLOYMENT_ID, Deployment

# A deployment is only scanned for entries in `active`. The others are real states,
# not decoration: `paused` keeps the book and its open positions but stops new
# entries; `archived` is a retired deployment kept for attribution of its history.
ACTIVE = "active"
PAUSED = "paused"
DRAFT = "draft"
ARCHIVED = "archived"
STATUSES = (DRAFT, ACTIVE, PAUSED, ARCHIVED)

LEGACY_NAME = "default"


def _deployment_producer_key(*parts: object) -> str:
    """Keep mutation identities within the outbox's bounded key contract."""
    raw = "|".join(str(part) for part in parts)
    return "deployment:" + hashlib.sha256(raw.encode()).hexdigest()


def _account_belongs_to_owner(session, *, owner_id: str, broker_account_id: str) -> bool:
    return session.scalar(select(BrokerAccount.broker_account_id).where(
        BrokerAccount.broker_account_id == broker_account_id,
        BrokerAccount.owner_id == owner_id,
        BrokerAccount.status == "active",
    )) is not None


def ensure_legacy_deployment(session, *, owner_id: str,
                             broker_account_id: str) -> Deployment:
    """Create the legacy deployment if it is absent. Idempotent.

    Called from `init_db`. Also seeded by migration 0002 — deliberately both, so a
    database can arrive at a valid state whether it was created by `create_all`
    (fresh install, no revision ran) or migrated (existing install). Whichever runs
    first wins; the other is a no-op.
    """
    row = get_deployment(
        session, LEGACY_DEPLOYMENT_ID,
        owner_id=owner_id, broker_account_id=broker_account_id)
    if row is not None:
        return row
    row = Deployment(
        id=LEGACY_DEPLOYMENT_ID,
        owner_id=owner_id,
        name=LEGACY_NAME,
        strategy_key=None,        # resolve per instrument, exactly as before
        strategy_version=None,
        broker_account_id=broker_account_id,
        universe_mode="legacy",   # per-instrument config + active watchlists
        params_json="{}",         # inherit every platform default
        allocation=None,          # the whole account
        status=ACTIVE,
        armed=False,              # disarmed on every start, like the global flag
        notes="The original single book. Every row written before deployments "
              "existed belongs to this one.",
    )
    session.add(row)
    session.flush()
    from app.events.producers import append_execution_change
    append_execution_change(
        session, owner_id=owner_id, broker_account_id=broker_account_id,
        aggregate_type="deployment", aggregate_id=str(row.id),
        event_type="execution.deployment.changed", projection="deployments",
        producer_key=_deployment_producer_key(owner_id, row.id, "created"),
        facts={"state": ACTIVE},
    )
    return row


def get_deployment(session, deployment_id: int, *, owner_id: str,
                   broker_account_id: str) -> Deployment | None:
    return session.scalar(select(Deployment).where(
        Deployment.id == deployment_id,
        Deployment.owner_id == owner_id,
        Deployment.broker_account_id == broker_account_id,
    ))


def get_by_name(session, name: str, *, owner_id: str,
                broker_account_id: str) -> Deployment | None:
    return session.scalars(
        select(Deployment).where(
            Deployment.name == name,
            Deployment.owner_id == owner_id,
            Deployment.broker_account_id == broker_account_id,
        )).one_or_none()


def all_deployments(session, *, owner_id: str, broker_account_id: str,
                    include_archived: bool = False) -> list[Deployment]:
    stmt = select(Deployment).where(
        Deployment.owner_id == owner_id,
        Deployment.broker_account_id == broker_account_id,
    )
    if not include_archived:
        stmt = stmt.where(Deployment.status != ARCHIVED)
    return list(session.scalars(stmt.order_by(Deployment.id)))


def active_deployments(session, *, owner_id: str,
                       broker_account_id: str) -> list[Deployment]:
    """The deployments the engine scans. Today: exactly the legacy one."""
    return list(session.scalars(
        select(Deployment).where(
            Deployment.status == ACTIVE,
            Deployment.owner_id == owner_id,
            Deployment.broker_account_id == broker_account_id,
        ).order_by(Deployment.id)))


def create_deployment(session, name: str, *, strategy_key: str | None = None,
                      strategy_version: str | None = None,
                      owner_id: str, broker_account_id: str,
                      universe_mode: str = "explicit",
                      watchlist_id: int | None = None,
                      params: dict | None = None,
                      allocation: float | None = None,
                      status: str = DRAFT, notes: str = "") -> Deployment:
    """Create a deployment. Defaults to `draft` — a new book must be turned on
    deliberately, never by the act of describing it."""
    if status not in STATUSES:
        raise ValueError(f"unknown status {status!r}; expected one of {STATUSES}")
    if not _account_belongs_to_owner(
            session, owner_id=owner_id, broker_account_id=broker_account_id):
        raise ValueError("broker account is not available to this owner")
    if get_by_name(session, name, owner_id=owner_id,
                   broker_account_id=broker_account_id) is not None:
        raise ValueError(f"a deployment named {name!r} already exists")
    if watchlist_id is not None:
        from app.db.models import Watchlist
        if session.scalar(select(Watchlist.id).where(
                Watchlist.owner_id == owner_id, Watchlist.id == watchlist_id)) is None:
            raise ValueError(f"no watchlist with id {watchlist_id}")
    row = Deployment(
        owner_id=owner_id, broker_account_id=broker_account_id,
        name=name, strategy_key=strategy_key, strategy_version=strategy_version,
        universe_mode=universe_mode, watchlist_id=watchlist_id,
        params_json=json.dumps(params or {}), allocation=allocation,
        status=status, armed=False, notes=notes)
    session.add(row)
    session.flush()
    from app.events.producers import append_execution_change
    append_execution_change(
        session, owner_id=owner_id, broker_account_id=broker_account_id,
        aggregate_type="deployment", aggregate_id=str(row.id),
        event_type="execution.deployment.changed", projection="deployments",
        producer_key=_deployment_producer_key(owner_id, row.id, "created"),
        facts={"state": status},
    )
    return row


def set_status(session, deployment_id: int, status: str, *, owner_id: str,
               broker_account_id: str) -> Deployment:
    """Move a deployment through its lifecycle.

    Archiving the legacy deployment is refused: `deployment_id` is NOT NULL across
    the money record and every historical row points at it, so retiring it would
    make the book unattributable. It can be paused (which stops entries) — that is
    the operation someone reaching for "archive" actually wants.
    """
    if status not in STATUSES:
        raise ValueError(f"unknown status {status!r}; expected one of {STATUSES}")
    row = get_deployment(session, deployment_id, owner_id=owner_id,
                         broker_account_id=broker_account_id)
    if row is None:
        raise ValueError(f"no deployment with id {deployment_id}")
    if deployment_id == LEGACY_DEPLOYMENT_ID and status == ARCHIVED:
        raise ValueError(
            "the legacy deployment cannot be archived — every row written before "
            "deployments existed refers to it. Pause it instead if you want to stop "
            "new entries.")
    row.status = status
    if status != ACTIVE:
        row.armed = False       # a non-active deployment must never stay armed
    row.updated_at = dt.datetime.now()
    session.flush()
    from app.events.producers import append_execution_change
    append_execution_change(
        session, owner_id=owner_id, broker_account_id=broker_account_id,
        aggregate_type="deployment", aggregate_id=str(row.id),
        event_type="execution.deployment.changed", projection="deployments",
        producer_key=_deployment_producer_key(
            owner_id, row.id, "status", row.updated_at.isoformat()),
        facts={"state": status},
    )
    return row


def set_armed(session, deployment_id: int, armed: bool, *, owner_id: str,
              broker_account_id: str) -> Deployment:
    """Arm or disarm one deployment.

    Arming a deployment that is not `active` is refused rather than silently
    ignored: "armed but not running" is precisely the kind of state that reads as
    safe on a dashboard and is not.
    """
    row = get_deployment(session, deployment_id, owner_id=owner_id,
                         broker_account_id=broker_account_id)
    if row is None:
        raise ValueError(f"no deployment with id {deployment_id}")
    if armed and row.status != ACTIVE:
        raise ValueError(
            f"cannot arm deployment {deployment_id} — its status is {row.status!r}, "
            f"not {ACTIVE!r}. An armed non-active deployment would look live and "
            f"take nothing.")
    row.armed = armed
    row.updated_at = dt.datetime.now()
    session.flush()
    from app.events.producers import append_execution_change
    append_execution_change(
        session, owner_id=owner_id, broker_account_id=broker_account_id,
        aggregate_type="deployment", aggregate_id=str(row.id),
        event_type="execution.deployment.changed", projection="deployments",
        producer_key=_deployment_producer_key(
            owner_id, row.id, "armed", row.updated_at.isoformat()),
        facts={"state": "armed" if armed else "disarmed"},
    )
    return row


def disarm_all(session, *, owner_id: str, broker_account_id: str) -> int:
    """Disarm every deployment. Called at process start, mirroring the global
    disarm-on-boot invariant: a restart must never inherit an arm state, because
    nobody was watching when the process went down."""
    n = 0
    for row in session.scalars(select(Deployment).where(
            Deployment.armed.is_(True),
            Deployment.owner_id == owner_id,
            Deployment.broker_account_id == broker_account_id)):
        row.armed = False
        row.updated_at = dt.datetime.now()
        from app.events.producers import append_execution_change
        append_execution_change(
            session, owner_id=owner_id, broker_account_id=broker_account_id,
            aggregate_type="deployment", aggregate_id=str(row.id),
            event_type="execution.deployment.changed", projection="deployments",
            producer_key=_deployment_producer_key(
                owner_id, row.id, "boot-disarm", row.updated_at.isoformat()),
            facts={"state": "disarmed"},
        )
        n += 1
    session.flush()
    return n


def resolve_deployment_strategy(session, deployment_id: int, *, owner_id: str,
                                broker_account_id: str):
    """The Strategy a deployment runs — FAIL-CLOSED (Phase D).

    This is the call site audit finding C4 was about. `get_strategy()` fails OPEN:
    an unknown key silently returns the platform default. That is the right posture
    for the legacy per-instrument path, where a stale assignment must not be able to
    crash a tick — but it is the wrong posture entirely for a deployment, because a
    deployment is a promise about WHICH strategy is trading. Under a marketplace,
    failing open means a strategy that fails to load trades the platform's default
    with the customer's capital, while the trade rows claim it was theirs.

    So a deployment that pins a strategy resolves it strictly and raises
    `StrategyNotFound` if it is not registered. The caller's job is to halt that
    deployment, not to substitute something else.

    Returns None for `strategy_key=None` — that is the legacy deployment, which
    resolves per instrument by design and pins nothing. None here means "not
    applicable", never "not found"; the two are separate outcomes on purpose.
    """
    from app.strategy.registry import resolve_strategy

    row = get_deployment(session, deployment_id, owner_id=owner_id,
                         broker_account_id=broker_account_id)
    if row is None:
        raise ValueError(f"no deployment with id {deployment_id}")
    if row.strategy_key is None:
        return None
    return resolve_strategy(row.strategy_key, owner_id=owner_id)  # raises StrategyNotFound


def deployment_strategy_version(session, deployment_id: int, *, owner_id: str,
                                broker_account_id: str) -> str | None:
    """The content hash of the strategy this deployment runs, or None if it pins
    none. Resolved through the fail-closed path, so an unresolvable strategy raises
    rather than reporting the default's version as if it were the deployment's."""
    strat = resolve_deployment_strategy(
        session, deployment_id, owner_id=owner_id,
        broker_account_id=broker_account_id)
    return None if strat is None else strat.version


def deployment_params(session, deployment_id: int, *, owner_id: str,
                      broker_account_id: str) -> dict:
    """The deployment's own parameter overrides (Phase C resolves these against
    platform defaults). Malformed JSON returns {} rather than raising — a bad row
    must degrade to 'inherit everything', never take the engine down."""
    row = get_deployment(session, deployment_id, owner_id=owner_id,
                         broker_account_id=broker_account_id)
    if row is None:
        return {}
    try:
        parsed = json.loads(row.params_json or "{}")
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}
