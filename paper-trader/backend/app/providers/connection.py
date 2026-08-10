"""A credentialed link to a broker, separate from the data feed it may also serve.

`capabilities.py` states the roles doctrine — market data, account/portfolio, execution and
instrument resolution are distinct jobs, and one user may hold several connections serving
different ones. This module is the first object that makes the *execution* role addressable
independently of the object prices are read from.

## Why this exists

`make_broker` used to read the order credential straight off the data provider:

    token = getattr(provider, "access_token", None)      # broker_factory.py, before this slice

so "where do I read prices" and "whose account do I trade" were necessarily the same
connection. Three things followed, and all three were blocking:

  * a second broker could not execute at all — the schema (`ExecutionIntent.broker`,
    `.account_scope`, `.connection_scope`, migration 0014) and the recovery query
    (`ExecutionLifecycleStore.unresolved_entries`) both name the connection, but every writer
    passed one hardcoded constant, so the mechanism was correct and never given real data;
  * a connection that serves candles and quotes but places no orders — which is exactly what
    the parked Upstox adapter is — fell back to `PaperBroker` **silently**;
  * market data could not be fanned in once per instrument set while orders stayed per-account,
    which is what the 500-user correction requires.

## What a connection is not

It is not an authority. `AUTHORITY_BY_SOURCE` grants the right to execute by
`(source, execution_mode)` and this object does not participate in that decision — it answers
"through which credential and under whose scope", after authority has already been granted.
It is not a book either: `execution_book.py` decides whose money a position is by execution
mode, and paper/live separation is untouched by anything here.

## The credential is a source, not a value

Kite access tokens expire ~06:00 IST daily and are refreshed by the operator through Connect
Kite. `token_source` is called at order time so a re-login propagates without a backend
restart — the behaviour the pre-seam `token_source=lambda: getattr(provider, "access_token")`
already had, preserved deliberately rather than rediscovered later.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Callable

from app.providers import capabilities as caps

# The one connection that exists in production. Every `ExecutionIntent` row written before
# this slice carries this scope, so it is the documented value for pre-existing rows and must
# not be renamed — `unresolved_entries` matches on it to recover live entries after a restart.
KITE_LEGACY_CONNECTION_SCOPE: str = "kite:legacy"


class ConnectionCannotExecute(RuntimeError):
    """A connection was named for execution and cannot place orders.

    Loud on purpose. The silent version of this — returning a `PaperBroker` — is
    indistinguishable from working: the engine arms, scans, "fills" and books positions, and
    the operator has no signal that nothing reached an exchange. Refusing at construction
    means the failure surfaces at startup, before a signal exists.
    """


class UnknownConnection(LookupError):
    """A configured connection that does not exist, or is revoked.

    Raised rather than answered with a fallback, because every available fallback places real
    orders through a credential the operator did not choose.
    """


@dataclass(frozen=True)
class Connection:
    """One credentialed link to one broker.

    `capabilities` is the same vocabulary adapters declare (`capabilities.ALL`); a connection
    carries its own set because a credential may be entitled to less than the adapter can do —
    a data-only API key at a broker that also offers execution, for instance.
    """

    broker: str
    scope: str
    capabilities: frozenset[str] = field(default_factory=frozenset)
    token_source: Callable[[], str | None] = lambda: None
    tick_source: Callable[..., float] | None = None

    def __post_init__(self) -> None:
        caps.validate(frozenset(self.capabilities))
        if not self.scope:
            raise ValueError("a connection must carry a scope; it is written into money records")

    def supports(self, capability: str) -> bool:
        return capability in self.capabilities


def connection_for(provider, scope: str | None = None) -> Connection:
    """The legacy single-connection view: the data provider *is* the execution connection.

    This is what production runs today — one Kite login serving data, account and execution —
    and deriving it here rather than at the call site keeps that path byte-identical while the
    seam exists for the second connection. `getattr` throughout because callers may hand this a
    duck-typed stub, the same tolerance `capabilities.provider_supports` preserves.

    `scope` defaults to the legacy constant precisely because that default is load-bearing:
    it is the value already written into every pre-seam `ExecutionIntent`, and the recovery
    query matches on it. A caller that is building a *second* connection must pass its own.
    """
    declared = getattr(provider, "CAPABILITIES", frozenset())
    return Connection(
        broker=str(getattr(provider, "name", "") or ""),
        scope=scope or KITE_LEGACY_CONNECTION_SCOPE,
        capabilities=caps.validate(frozenset(declared)),
        # Prefer a provider's own "what should I use right now" reader over its cached
        # attribute. `KiteProvider.current_access_token` re-reads the dated token file, which is
        # what keeps a SECOND (execution-role) instance from serving a token that expired at
        # 06:00 while the data instance was re-authenticated — F4 from the 2026-08-10 execution
        # review. `getattr` fallback keeps every duck-typed stub and older adapter working.
        token_source=(getattr(provider, "current_access_token", None)
                      or (lambda: getattr(provider, "access_token", None))),
        tick_source=getattr(provider, "tick_size", None),
    )


def _tick_source_for(broker: str):
    """The real per-instrument tick reader for `broker`, or a refusal.

    Deliberately not defaulting to `None` (which becomes 0.05 downstream). The whole point of a
    tick source is that the standard grid is WRONG for a minority of instruments, and that
    minority is where the money is lost — silently, because an off-grid trigger is rejected and
    the position simply runs unprotected.
    """
    from app.providers.factory import provider_named
    adapter = provider_named(broker)
    reader = getattr(adapter, "tick_size", None)
    if not callable(reader):
        raise UnknownConnection(
            f"broker {broker!r} has no tick_size reader, so a protective stop placed through "
            f"this connection would be rounded to the standard 0.05 grid — off-grid triggers "
            f"are rejected outright and the position would run with no exchange-side stop.")
    return reader


def configured_execution_connection(data_provider, session=None) -> Connection | None:
    """Resolve the connection that will place orders.

    Two sources, checked in this order:

      1. **A stored connection** (`PT_EXECUTION_CONNECTION`, a scope owned by
         `PT_OWNER_ID`), when a `session` is available. This is the durable form: the
         credential lives encrypted in `broker_connections`, survives a restart, and can be
         revoked without touching configuration. It wins because a stored connection is an
         explicit act by an owner, where the env var is a deployment default.
      2. **`PT_EXECUTION_PROVIDER`**, the environment-named provider below.

    Returns **None** when the setting is unset or names the data provider itself. None is not
    an error and not a fallback: it means "unnamed", which `make_broker` treats as the legacy
    single-connection path — same credential, same `kite:legacy` scope, same silent paper
    fall-back for the non-broker adapters. Production takes this branch, so binding this at
    the composition root changes nothing about what runs today. That is the point: the seam
    now has a consumer without the live path moving.

    When the names differ the roles genuinely split, and two things follow.

    **A distinct scope.** `connection_scope` is written into money records and is what
    `unresolved_entries` matches on to recover live entries after a restart. A second
    connection reusing `kite:legacy` would have its orders recovered under the first
    connection's book, which is a silent cross-account mix — the worst available failure. So
    a split-role connection carries `"<broker>:execution"` and recovers only its own.

    **No capability check here.** Whether the named connection may execute is `make_broker`'s
    decision and it already refuses loudly (`ConnectionCannotExecute`). Answering it twice
    would let the two answers drift, and this is the one that would be wrong quietly.
    """
    from app.core.config import get_settings
    from app.providers.factory import provider_named

    s = get_settings()

    stored_scope = (getattr(s, "execution_connection", "") or "").strip()
    if stored_scope and session is not None:
        from app.providers.connection_store import OwnedConnectionStore
        # The owner is passed only when configured. An empty `PT_OWNER_ID` must NOT be coerced
        # to the default here — that was a second copy of the fallback the store itself now
        # refuses, and two copies of a security default is one too many.
        configured_owner = (getattr(s, "owner_id", "") or "").strip()
        store = (OwnedConnectionStore(session, configured_owner) if configured_owner
                 else OwnedConnectionStore(session))
        row = store.by_scope(stored_scope)
        if row is None or row.status != "active":
            # Loud, and specifically not a fall-through to the env var. An operator who named a
            # stored connection and got the environment's one instead would be trading through
            # a credential they did not choose — and every health check would stay green.
            raise UnknownConnection(
                f"PT_EXECUTION_CONNECTION names {stored_scope!r}, which is not an active "
                f"connection for owner {store.owner_id!r}. Refusing to fall back to "
                f"PT_EXECUTION_PROVIDER: that would place orders through a credential the "
                f"operator did not select.")
        conn = store.live_connection(row.id)
        # A stored connection has no provider OBJECT behind it — just a row — so it cannot carry
        # a tick reader on its own, and `Connection.tick_source` defaults to None. That default
        # is not neutral: `KiteOrderClient._tick` then returns the hardcoded 0.05 grid for every
        # instrument, so an intraday LT (tick 0.10) or MARUTI (1.00) protective stop is rounded
        # off-grid, rejected by Zerodha, and the position runs the session with NO exchange-side
        # backstop. That is the 2026-07-15 incident — 2,437 rejected SL-M placements —
        # reintroduced through the path this design nominates as preferred. Found by an
        # independent execution-safety review, 2026-08-10.
        #
        # The reader comes from the adapter for the connection's OWN broker, exactly as the
        # environment path below does. Failing to resolve one is a refusal rather than a silent
        # 0.05: a connection that cannot read its venue's price grid must not place protective
        # stops on it.
        return replace(conn, tick_source=_tick_source_for(conn.broker))

    chosen = (s.execution_provider or "").strip().lower()
    if not chosen or chosen == (s.provider or "").strip().lower():
        return None
    executor = provider_named(chosen)
    if executor is data_provider:
        return None
    return connection_for(executor, scope=f"{chosen}:execution")
