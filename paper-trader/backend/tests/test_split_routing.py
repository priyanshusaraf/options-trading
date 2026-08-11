"""Split routing — prices from one broker, orders through another, selected by config.

`.claude/rules/providers-brokers.md` sets the bar and it is deliberately high:

    "A second data adapter does not prove split routing until a test selects market data
     from one connection and execution from another."

`tests/test_execution_connection.py` holds the seam open with hand-built `Connection`
objects. That proves the seam accepts a split; it does not prove the *runtime* produces
one. These tests set `PT_PROVIDER` and `PT_EXECUTION_PROVIDER` and let the composition
root resolve both roles itself, with the concrete `UpstoxProvider` serving prices and
Kite placing the order — the exact pairing the rules file names as the target example.

The live classes are stubbed, as in `test_broker_factory.py`: `_refuse_live_broker_under_pytest`
makes constructing a real one impossible on purpose, and no test in this repo may reach a
real exchange.
"""
from __future__ import annotations

import types

import pytest

from app.core.config import get_settings
from app.db.models import LEGACY_OWNER_ID
from app.db.session import init_db
from app.engine.broker import PaperBroker
from app.engine.broker_factory import ConnectionCannotExecute, make_broker
from app.providers import capabilities as caps
from app.providers.connection import configured_execution_connection
from app.providers.factory import provider_named
from app.providers.upstox import UpstoxProvider


def _open_the_live_gate(monkeypatch):
    """Settings-layer only. `get_settings` is `lru_cache`d, so a `cache_clear()` here would
    leave the next caller rebuilding a live Settings that outlives the test — the 2026-07-28
    test-env leak. `setattr` is reverted at teardown; `cache_clear()` is not."""
    s = get_settings()
    monkeypatch.setattr(s, "execution", "live")
    monkeypatch.setattr(s, "live_ack", "I_UNDERSTAND_REAL_MONEY")
    monkeypatch.setenv("PT_EXECUTION", "live")
    monkeypatch.setenv("PT_LIVE_ACK", "I_UNDERSTAND_REAL_MONEY")


def _split_the_roles(monkeypatch, *, data: str, execution: str):
    s = get_settings()
    monkeypatch.setattr(s, "provider", data)
    monkeypatch.setattr(s, "execution_provider", execution)
    return s


def _stub_the_live_wiring(monkeypatch, captured: dict):
    monkeypatch.setattr(
        "app.providers.live_kite.LiveExecutionKite",
        lambda **k: types.SimpleNamespace(
            set_access_token=lambda t: captured.setdefault("seeded", t)))

    def fake_client(kite, **kw):
        captured.update(kw)
        return object()

    monkeypatch.setattr("app.engine.kite_order_client.KiteOrderClient", fake_client)

    def fake_lb(provider, client, **kw):
        captured["data_provider"] = provider
        captured["connection"] = kw.get("connection")
        captured["venue"] = kw.get("venue")
        return "LB"

    monkeypatch.setattr("app.engine.live_broker.LiveBroker", fake_lb)


@pytest.fixture()
def upstox_data_kite_execution(monkeypatch):
    """The target configuration, resolved by the runtime rather than hand-built."""
    # init_db BEFORE the split: a destructive reset is refused unless `provider` is
    # still "mock", which is the guard that stops a stray reset wiping a live book.
    init_db(reset=True)
    _open_the_live_gate(monkeypatch)
    _split_the_roles(monkeypatch, data="upstox", execution="kite")
    data = UpstoxProvider()
    # The execution side must carry ITS OWN credential. Naming Kite resolves a real
    # `KiteProvider`, which in a test holds no token, so seed the resolved object rather
    # than the connection — the point is that the token travels from the execution
    # connection, and a hand-made token_source would beg that question.
    kite = provider_named("kite")
    kite.access_token = "ZERODHA_TOKEN"
    monkeypatch.setattr("app.providers.factory.provider_named",
                        lambda name: kite if name == "kite" else data)
    captured: dict = {}
    _stub_the_live_wiring(monkeypatch, captured)
    return data, kite, captured


# ── the resolution itself ─────────────────────────────────────────────────

def test_the_runtime_resolves_two_different_connections_from_config(upstox_data_kite_execution):
    data, kite, _ = upstox_data_kite_execution
    conn = configured_execution_connection(data)
    assert conn is not None, (
        "with PT_PROVIDER=upstox and PT_EXECUTION_PROVIDER=kite the runtime must produce a "
        "SEPARATE execution connection; None means it collapsed the roles back to one")
    assert conn.broker == "kite"
    assert conn.scope == "kite:execution"
    assert data.name == "upstox"


def test_the_execution_connection_gets_its_own_scope_not_the_data_connections(
        upstox_data_kite_execution):
    """Restart recovery matches unresolved entries by `connection_scope`. If a split
    execution connection reused the legacy scope, a second connection's live entries would
    be recovered under the first connection's book — one account adopting another's
    working orders."""
    data, _, _ = upstox_data_kite_execution
    from app.providers.connection import KITE_LEGACY_CONNECTION_SCOPE, connection_for
    assert configured_execution_connection(data).scope != KITE_LEGACY_CONNECTION_SCOPE
    assert connection_for(data).scope == KITE_LEGACY_CONNECTION_SCOPE


# ── the whole composition root ────────────────────────────────────────────

def test_prices_come_from_upstox_while_the_order_credential_is_zerodhas(
        upstox_data_kite_execution):
    """The end-to-end claim, and the one that is money if it is wrong. An order client
    seeded with the DATA connection's token authenticates as the wrong account — or, with
    Upstox, as nothing at all, and every order is rejected unauthenticated."""
    data, _, captured = upstox_data_kite_execution
    broker = make_broker(data, execution_connection=configured_execution_connection(data), broker_account_id="account.default", owner_id=LEGACY_OWNER_ID)

    assert broker == "LB"
    assert captured["data_provider"] is data, "prices must still come from Upstox"
    assert captured["data_provider"].name == "upstox"
    assert captured["token_source"]() == "ZERODHA_TOKEN", (
        "the order credential must be the EXECUTION connection's")
    assert data.access_token is None, "the Upstox adapter holds no order credential at all"
    assert captured["connection"].scope == "kite:execution"


def test_the_tick_source_follows_execution_not_data(upstox_data_kite_execution):
    """Every trigger price must land on the venue's real grid — the 2026-07-15 incident was
    2,437 rejections for assuming 0.05. The grid belongs to the exchange the ORDER goes to,
    so a split configuration must read it through the execution connection. Upstox has no
    `tick_size` at all, so a tick_source pointing at the data side would be None and the
    client would silently fall back to the 0.05 grid that caused the incident."""
    data, kite, captured = upstox_data_kite_execution
    make_broker(data, execution_connection=configured_execution_connection(data), broker_account_id="account.default", owner_id=LEGACY_OWNER_ID)
    tick_source = captured.get("tick_source")
    assert tick_source is not None
    assert tick_source == getattr(kite, "tick_size"), (
        "tick_source must be the execution connection's reader")
    assert getattr(data, "tick_size", None) is None


# ── the misconfigurations, which must be loud ─────────────────────────────

def test_naming_a_data_only_connection_for_execution_refuses_rather_than_paper_trading(
        monkeypatch):
    """The silent-failure shape this whole seam exists to prevent: the operator configures
    live, sees a green engine, and nothing ever reaches an exchange."""
    init_db(reset=True)
    _open_the_live_gate(monkeypatch)
    _split_the_roles(monkeypatch, data="kite", execution="upstox")
    data = UpstoxProvider()
    upstox = UpstoxProvider()
    monkeypatch.setattr("app.providers.factory.provider_named", lambda name: upstox)

    conn = configured_execution_connection(data)
    assert conn is not None and conn.broker == "upstox"
    with pytest.raises(ConnectionCannotExecute) as e:
        make_broker(data, execution_connection=conn, broker_account_id="account.default", owner_id=LEGACY_OWNER_ID)
    assert caps.LIVE_EXECUTION in str(e.value)


def test_upstox_declares_no_execution_capability_at_all():
    """The refusal above must rest on a declaration, not on a name check. If this adapter
    ever declares LIVE_EXECUTION it will be refused one layer later — by `make_broker`'s
    broker guard — because no order client exists for it in this build."""
    assert caps.LIVE_EXECUTION not in UpstoxProvider.CAPABILITIES
    assert UpstoxProvider.CAPABILITIES == frozenset({caps.HISTORICAL_DATA, caps.LIVE_QUOTES})


def test_a_split_config_under_paper_still_produces_a_paper_broker(monkeypatch):
    """Splitting the roles must not become a back door into live. The execution gate is
    unchanged and still governs."""
    init_db(reset=True)
    _split_the_roles(monkeypatch, data="upstox", execution="kite")
    monkeypatch.setattr(get_settings(), "execution", "paper")
    monkeypatch.delenv("PT_EXECUTION", raising=False)
    data = UpstoxProvider()
    assert isinstance(make_broker(data, broker_account_id="account.default", owner_id=LEGACY_OWNER_ID), PaperBroker)


# ── a stored connection outranks the environment, and a missing one refuses ──
# Both gaps were found by scripts/tenancy_mutations.py rather than by reading the code.

def _vault_key(monkeypatch):
    import base64
    from app.core import credential_vault as vault
    monkeypatch.setenv(vault.ENV_KEY, base64.b64encode(b"k" * 32).decode())


def test_a_stored_connection_is_preferred_over_the_environment_variable(monkeypatch):
    """A stored connection is an explicit act by an owner; `PT_EXECUTION_PROVIDER` is a
    deployment default. When both are present the owner's choice must win, or "I selected this
    account" quietly means nothing."""
    from app.db.session import SessionLocal
    from app.providers.connection_store import OwnedConnectionStore

    init_db(reset=True)
    _vault_key(monkeypatch)
    with SessionLocal() as s:
        OwnedConnectionStore(s, "owner").create(
            broker="kite", scope="kite:stored", label="the owner's own")
        s.commit()

    _open_the_live_gate(monkeypatch)
    _split_the_roles(monkeypatch, data="upstox", execution="kite")
    monkeypatch.setattr(get_settings(), "execution_connection", "kite:stored")

    with SessionLocal() as s:
        conn = configured_execution_connection(UpstoxProvider(), session=s)
    assert conn is not None and conn.scope == "kite:stored", (
        "the environment's connection was used instead of the stored one")


def test_naming_a_stored_connection_that_does_not_exist_refuses(monkeypatch):
    """The refusal that must not become a fallback. Falling through to
    `PT_EXECUTION_PROVIDER` would place real orders through a credential the operator did not
    choose — and every health check would stay green while it happened."""
    from app.db.session import SessionLocal
    from app.providers.connection import UnknownConnection

    init_db(reset=True)
    _open_the_live_gate(monkeypatch)
    _split_the_roles(monkeypatch, data="upstox", execution="kite")
    monkeypatch.setattr(get_settings(), "execution_connection", "kite:typo")

    with SessionLocal() as s:
        with pytest.raises(UnknownConnection) as e:
            configured_execution_connection(UpstoxProvider(), session=s)
    assert "kite:typo" in str(e.value)


def test_a_revoked_stored_connection_refuses_rather_than_falling_back(monkeypatch):
    """Revocation must not silently hand the engine the environment's connection instead."""
    from app.db.session import SessionLocal
    from app.providers.connection import UnknownConnection
    from app.providers.connection_store import OwnedConnectionStore

    init_db(reset=True)
    _vault_key(monkeypatch)
    with SessionLocal() as s:
        store = OwnedConnectionStore(s, "owner")
        row = store.create(broker="kite", scope="kite:stored")
        s.commit()
        store.revoke(row.id)
        s.commit()

    _open_the_live_gate(monkeypatch)
    _split_the_roles(monkeypatch, data="upstox", execution="kite")
    monkeypatch.setattr(get_settings(), "execution_connection", "kite:stored")

    with SessionLocal() as s:
        with pytest.raises(UnknownConnection):
            configured_execution_connection(UpstoxProvider(), session=s)


def test_constructing_a_runner_takes_no_database_connection_by_default(monkeypatch):
    """A regression with no visible symptom except slowness.

    Resolving the execution connection was written to open a session unconditionally at
    `Runner()` construction. The backtest sweep spawns a worker per core and each constructs
    one, against the same SQLite file — so a parallel sweep turned into `busy_timeout`
    contention and the suite appeared to hang rather than fail. Nothing was wrong with any
    result; it just stopped finishing.

    The default configuration reads no connection row at all, so it must touch no session.
    """
    from app.db import session as session_module

    init_db(reset=True)
    monkeypatch.setattr(get_settings(), "execution_connection", "")
    opened = []
    real = session_module.SessionLocal
    monkeypatch.setattr(session_module, "SessionLocal",
                        lambda *a, **k: (opened.append(1), real(*a, **k))[1])

    configured_execution_connection(UpstoxProvider())
    assert opened == [], (
        "resolving the execution connection opened a database session with no stored "
        "connection configured")
