"""The execution connection seam — data provider ≠ execution broker.

Until this slice, `make_broker` read the order credential off the *data provider*
(`broker_factory.py:84`, `token = getattr(provider, "access_token", None)`), so "where do I
read prices" and "whose account do I trade" were the same object. Two consequences, both
proven here: a second broker could not be used for execution at all, and a connection that
serves data but cannot place orders fell back to `PaperBroker` **silently** — the operator
believes they are trading while nothing reaches an exchange.

These tests hold the seam open. They do not build a real `LiveBroker`: the pytest guard in
`broker_factory._refuse_live_broker_under_pytest` makes that impossible on purpose, so the
live class is stubbed exactly as `tests/test_broker_factory.py` does.
"""
from __future__ import annotations

import types

import pytest

from app.core.config import get_settings
from app.db.session import init_db
from app.engine.broker import PaperBroker
from app.engine.broker_factory import make_broker
from app.providers import capabilities as caps
from app.providers.connection import (
    KITE_LEGACY_CONNECTION_SCOPE,
    Connection,
    ConnectionCannotExecute,
    configured_execution_connection,
    connection_for,
)
from app.providers.factory import UnknownProvider
from app.providers.mock import MockProvider


def _open_the_live_gate(monkeypatch):
    """Open the gate at the SETTINGS layer — the repo convention, and the only safe one.

    `get_settings` is `lru_cache`d, so `cache_clear()` inside a test leaves the *next*
    caller to rebuild a Settings from an environment that still says live, and that
    instance outlives the test. The first draft of this file did exactly that and
    poisoned 17 tests across paper authority, the shadow lane and the research-root
    live guard — the 2026-07-28 test-env leak, rediscovered. `setattr` on the shared
    instance is reverted by monkeypatch at teardown; `cache_clear()` is not.
    """
    s = get_settings()
    monkeypatch.setattr(s, "execution", "live")
    monkeypatch.setattr(s, "live_ack", "I_UNDERSTAND_REAL_MONEY")
    monkeypatch.setenv("PT_EXECUTION", "live")
    monkeypatch.setenv("PT_LIVE_ACK", "I_UNDERSTAND_REAL_MONEY")


def _kite_shaped_provider(token: str):
    prov = MockProvider()
    prov.name = "kite"
    prov.CAPABILITIES = frozenset({
        caps.HISTORICAL_DATA, caps.LIVE_QUOTES, caps.LIVE_EXECUTION, caps.MARKET_ORDERS,
    })
    prov.access_token = token
    return prov


def _stub_the_live_wiring(monkeypatch, captured: dict):
    """Stub every real-order class; capture what the order client was given."""
    monkeypatch.setattr(
        "app.providers.live_kite.LiveExecutionKite",
        lambda **k: types.SimpleNamespace(set_access_token=lambda t: captured.setdefault("seeded", t)))

    def fake_client(kite, **kw):
        captured.update(kw)
        return object()

    monkeypatch.setattr("app.engine.kite_order_client.KiteOrderClient", fake_client)

    def fake_lb(provider, client, **kw):
        captured["connection"] = kw.get("connection")
        return "LB"

    monkeypatch.setattr("app.engine.live_broker.LiveBroker", fake_lb)


def test_the_order_credential_comes_from_the_execution_connection_not_the_data_provider(monkeypatch):
    """The defect this slice exists to fix.

    Read prices from one connection, trade through another. Before the seam the order client
    was seeded with the DATA provider's token, which means orders authenticated as the wrong
    account — the failure is silent and it is money.
    """
    _open_the_live_gate(monkeypatch)
    init_db(reset=True)
    captured: dict = {}
    _stub_the_live_wiring(monkeypatch, captured)

    data = _kite_shaped_provider("DATA_TOKEN")
    execution = Connection(
        broker="kite",
        scope="kite:trading-account",
        capabilities=frozenset({caps.LIVE_EXECUTION, caps.MARKET_ORDERS}),
        token_source=lambda: "EXEC_TOKEN",
    )

    assert make_broker(data, execution_connection=execution, broker_account_id="account.default") == "LB"
    assert captured["token_source"]() == "EXEC_TOKEN"


def test_the_credential_stays_late_bound_so_a_daily_relogin_still_propagates(monkeypatch):
    """Kite tokens expire ~06:00 IST. The order client must hold a *source*, not a value,
    or every re-login would need a backend restart."""
    _open_the_live_gate(monkeypatch)
    init_db(reset=True)
    captured: dict = {}
    _stub_the_live_wiring(monkeypatch, captured)

    tokens = ["MONDAY"]
    execution = Connection(
        broker="kite", scope="kite:legacy",
        capabilities=frozenset({caps.LIVE_EXECUTION}),
        token_source=lambda: tokens[-1],
    )
    make_broker(_kite_shaped_provider("ignored"), execution_connection=execution, broker_account_id="account.default")

    assert captured["token_source"]() == "MONDAY"
    tokens.append("TUESDAY")
    assert captured["token_source"]() == "TUESDAY", "the order client froze the token"


def test_a_named_data_only_connection_refuses_instead_of_silently_paper_trading(monkeypatch):
    """The reason the Upstox adapter is parked.

    Upstox serves candles and quotes and places no orders through this seam. Selecting it for
    execution used to build a PaperBroker and say nothing.
    """
    _open_the_live_gate(monkeypatch)
    init_db(reset=True)

    data_only = Connection(
        broker="upstox", scope="upstox:acct-1",
        capabilities=frozenset({caps.HISTORICAL_DATA, caps.LIVE_QUOTES}),
        token_source=lambda: "UPSTOX_TOKEN",
    )

    with pytest.raises(ConnectionCannotExecute) as err:
        make_broker(_kite_shaped_provider("tok"), execution_connection=data_only, broker_account_id="account.default")

    message = str(err.value)
    assert "upstox:acct-1" in message, "the refusal must name the connection"
    assert caps.LIVE_EXECUTION in message, "the refusal must name what is missing"


def test_an_unnamed_execution_connection_keeps_the_legacy_paper_fallback(monkeypatch):
    """Deliberate asymmetry, and the reason it is safe.

    Mock and replay are not brokers; they declare no LIVE_EXECUTION and `PT_EXECUTION=live`
    against them has always meant "paper", which is a dev configuration rather than a mistake.
    Only a caller that *names* an execution connection is asserting an intent that can be wrong.
    """
    _open_the_live_gate(monkeypatch)
    init_db(reset=True)

    assert isinstance(make_broker(MockProvider(), broker_account_id="account.default"), PaperBroker)


def test_the_legacy_kite_connection_is_derived_unchanged_from_the_provider():
    """Byte-identical for the one connection that exists in production today."""
    prov = _kite_shaped_provider("LIVE_TOKEN")
    conn = connection_for(prov)

    assert conn.broker == "kite"
    assert conn.scope == KITE_LEGACY_CONNECTION_SCOPE
    assert conn.token_source() == "LIVE_TOKEN"
    assert conn.supports(caps.LIVE_EXECUTION)


def test_the_derived_connection_tracks_the_providers_token_rather_than_copying_it():
    """`connection_for` must not snapshot the token — same re-login reason as above."""
    prov = _kite_shaped_provider("BEFORE")
    conn = connection_for(prov)
    prov.access_token = "AFTER"

    assert conn.token_source() == "AFTER"


# ── the composition-root binding ─────────────────────────────────────────────
# A seam with no caller is this codebase's defining defect (three shapes, all shipped
# once). These hold the resolver that gives it one.


def test_the_single_connection_config_resolves_to_none_and_stays_the_legacy_path(monkeypatch):
    """Production's config. None means unnamed, which is the pre-seam behaviour exactly —
    including the `kite:legacy` scope every existing money record already carries."""
    s = get_settings()
    monkeypatch.setattr(s, "provider", "kite")
    monkeypatch.setattr(s, "execution_provider", "")

    assert configured_execution_connection(MockProvider()) is None


def test_naming_the_same_provider_for_both_roles_is_still_the_legacy_path(monkeypatch):
    """`PT_EXECUTION_PROVIDER=kite` with `PT_PROVIDER=kite` is one connection spelled twice.
    It must NOT mint a second scope, or a restart would recover live entries under a book
    the orders were never written to."""
    s = get_settings()
    monkeypatch.setattr(s, "provider", "kite")
    monkeypatch.setattr(s, "execution_provider", "KITE")   # case and spacing are noise

    assert configured_execution_connection(MockProvider()) is None


def test_split_roles_resolve_to_the_execution_provider_under_its_own_scope(monkeypatch):
    """The target case from `.claude/rules/providers-brokers.md`: prices from one connection,
    orders through another. Proven by resolution, not by prose."""
    s = get_settings()
    monkeypatch.setattr(s, "provider", "mock")
    monkeypatch.setattr(s, "execution_provider", "kite")
    executor = _kite_shaped_provider("EXEC_TOKEN")
    monkeypatch.setattr("app.providers.factory.provider_named", lambda name: executor)

    data = MockProvider()
    conn = configured_execution_connection(data)

    assert conn is not None
    assert conn.broker == "kite"
    assert conn.token_source() == "EXEC_TOKEN", "the data provider's credential leaked in"
    assert conn.scope == "kite:execution"
    assert conn.scope != KITE_LEGACY_CONNECTION_SCOPE, (
        "a second connection sharing the legacy scope would have its live entries "
        "recovered under the first connection's book"
    )


def test_an_unknown_execution_provider_refuses_instead_of_defaulting_to_the_mock(monkeypatch):
    """A typo in this setting must not route real orders at a synthetic market."""
    s = get_settings()
    monkeypatch.setattr(s, "provider", "kite")
    monkeypatch.setattr(s, "execution_provider", "zeroda")   # the typo that matters

    with pytest.raises(UnknownProvider) as err:
        configured_execution_connection(MockProvider())
    assert "zeroda" in str(err.value)


@pytest.mark.parametrize("broker", ["upstox", "angelone", "zeroda"])
def test_a_broker_with_no_order_client_refuses_even_when_it_declares_execution(broker,
                                                                              monkeypatch):
    """Over-declaration is a documented adapter lie (`tests/provider_conformance.py`). If one
    reaches the live branch, the credential must not be handed to another broker's endpoint.

    Three shapes, because they fail at different points and all three must refuse:
      * `upstox` — a SUPPORTED broker with a data adapter and no venue builder;
      * `angelone` — a PLANNED broker with no adapter at all;
      * `zeroda`  — not a broker; the typo that matters.

    **This test used to name `dhan`.** Dhan acquired a real `ExecutionVenue` and builder, so it
    is no longer an example of a broker that cannot execute — and the pytest live-broker guard
    caught that by refusing to hand back a real `LiveBroker`, which is the guard working rather
    than a test to loosen.
    """
    _open_the_live_gate(monkeypatch)
    init_db(reset=True)

    conn = Connection(
        broker=broker, scope=f"{broker}:execution",
        capabilities=frozenset({caps.LIVE_EXECUTION, caps.MARKET_ORDERS}),
        token_source=lambda: "SOME_TOKEN",
    )

    with pytest.raises(ConnectionCannotExecute) as err:
        make_broker(_kite_shaped_provider("tok"), execution_connection=conn, broker_account_id="account.default")
    assert broker in str(err.value)


# ── F4 from the execution-safety review, 2026-08-10 ───────────────────────

def test_a_split_execution_connection_picks_up_a_fresh_token_without_a_restart(tmp_path,
                                                                              monkeypatch):
    """The defect: a SECOND `KiteProvider` built for the execution role never saw a re-login.

    `complete_session` writes the new token to `TOKEN_FILE` **and to the instance it was called
    on**, and the API's re-auth route reaches the *data* provider — which in a split config is
    not the execution one. So the execution instance kept the token it read at construction, and
    after the ~06:00 IST expiry every order and **every exit** was rejected until a restart.

    The connection's token must therefore be late-bound to the authoritative source, not to an
    attribute on an object nothing can reach.
    """
    import datetime as dt
    import json

    from app.providers import kite as kite_mod
    from app.providers.connection import connection_for

    token_file = tmp_path / "access_token.json"
    monkeypatch.setattr(kite_mod, "TOKEN_FILE", str(token_file))

    execution = kite_mod.KiteProvider.__new__(kite_mod.KiteProvider)
    execution.kite = types.SimpleNamespace(set_access_token=lambda t: None)
    execution.access_token = "YESTERDAYS-TOKEN"

    conn = connection_for(execution, scope="kite:execution")
    assert conn.token_source() == "YESTERDAYS-TOKEN", "no file yet — keep what we have"

    # A re-login elsewhere in the process writes today's token to the shared file.
    token_file.write_text(json.dumps(
        {"date": str(dt.date.today()), "access_token": "TODAYS-TOKEN"}))

    assert conn.token_source() == "TODAYS-TOKEN", (
        "the execution connection served a token from before the daily re-login; every order "
        "and every exit would be rejected until the process restarted")


def test_a_stale_dated_token_is_not_served_as_current(tmp_path, monkeypatch):
    """A token cached yesterday is not merely old — Kite rejects it. Reporting it as usable is
    what turns a re-auth into a restart."""
    import datetime as dt
    import json

    from app.providers import kite as kite_mod
    from app.providers.connection import connection_for

    token_file = tmp_path / "access_token.json"
    monkeypatch.setattr(kite_mod, "TOKEN_FILE", str(token_file))
    token_file.write_text(json.dumps(
        {"date": str(dt.date.today() - dt.timedelta(days=1)),
         "access_token": "YESTERDAYS-TOKEN"}))

    p = kite_mod.KiteProvider.__new__(kite_mod.KiteProvider)
    p.kite = types.SimpleNamespace(set_access_token=lambda t: None)
    p.access_token = "YESTERDAYS-TOKEN"

    # `_load_saved_token` refuses a token whose date is not today, so the cached value is not
    # refreshed from a stale file and the connection reports what it has rather than pretending.
    # `_load_saved_token` refuses a token whose date is not today, so a stale file cannot
    # overwrite what we hold — and, critically, cannot present itself as current.
    assert connection_for(p, scope="kite:execution").token_source() == "YESTERDAYS-TOKEN"

    # And when today's token lands, it is adopted on the next read.
    token_file.write_text(json.dumps(
        {"date": str(dt.date.today()), "access_token": "TODAYS-TOKEN"}))
    assert connection_for(p, scope="kite:execution").token_source() == "TODAYS-TOKEN"
