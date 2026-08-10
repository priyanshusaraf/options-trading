"""Durable per-owner broker connections — the tenancy dimension, and the credential at rest.

Two properties are worth a test here and they fail in different ways:

  * **Cross-owner isolation.** If it breaks, one customer trades on another's account. There is
    no degraded mode and no partial version of this being wrong.
  * **The credential is never at rest in plaintext, and never leaks into anything renderable.**
    The database file is rsynced by `deploy.sh`, backed up, and copied between environments; a
    plaintext token in it is equivalent to the account.

ADR 0015 places this table in the money plane and states the key is not a row. Both are checked
here rather than trusted to the document.
"""
from __future__ import annotations

import base64
import json
import os

import pytest

from app.core import credential_vault as vault
from app.core.config import get_settings
from app.db.models import LEGACY_OWNER_ID, BrokerConnection
from app.db.session import SessionLocal, init_db
from app.providers import capabilities as caps
from app.providers.brokers import BrokerNotSupported
from app.providers.connection_store import ConnectionNotFound, OwnedConnectionStore

KEY = base64.b64encode(b"k" * 32).decode()
OTHER_KEY = base64.b64encode(b"z" * 32).decode()


@pytest.fixture()
def session():
    init_db(reset=True)
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture()
def vault_key(monkeypatch):
    monkeypatch.setenv(vault.ENV_KEY, KEY)
    return KEY


# ── ownership isolation ───────────────────────────────────────────────────

def test_one_owners_connection_is_invisible_to_another(session):
    """The failure this prevents has no degraded form: it is one customer trading on another
    customer's account."""
    alice = OwnedConnectionStore(session, "alice")
    bob = OwnedConnectionStore(session, "bob")
    row = alice.create(broker="kite", scope="kite:main", label="Alice's Zerodha")
    session.flush()

    assert [c.id for c in alice.list()] == [row.id]
    assert bob.list() == []
    with pytest.raises(ConnectionNotFound):
        bob.get(row.id)
    assert bob.by_scope("kite:main") is None


def test_the_refusal_does_not_reveal_that_the_connection_exists(session):
    """One error for "does not exist" and for "belongs to someone else". Distinguishing them
    confirms the existence of another owner's connection, and an integer id is guessable."""
    alice = OwnedConnectionStore(session, "alice")
    row = alice.create(broker="kite", scope="kite:main")
    session.flush()
    bob = OwnedConnectionStore(session, "bob")

    with pytest.raises(ConnectionNotFound) as real:
        bob.get(row.id)
    with pytest.raises(ConnectionNotFound) as imaginary:
        bob.get(row.id + 9999)
    assert str(real.value) == str(imaginary.value).replace(str(row.id + 9999), str(row.id))


def test_two_owners_may_hold_the_same_scope(session):
    """The uniqueness constraint is per owner, not global. Two owners each holding a
    `kite:legacy` connection is the normal case, not a conflict — a global constraint would mean
    the second customer to connect gets an integrity error."""
    a = OwnedConnectionStore(session, "alice").create(broker="kite", scope="kite:legacy")
    b = OwnedConnectionStore(session, "bob").create(broker="kite", scope="kite:legacy")
    session.flush()
    assert a.id != b.id and a.owner_id != b.owner_id


def test_the_same_owner_cannot_hold_one_scope_twice(session):
    from sqlalchemy.exc import IntegrityError
    store = OwnedConnectionStore(session, "alice")
    store.create(broker="kite", scope="kite:legacy")
    # `create` flushes, so the constraint fires inside the second call rather than at a later
    # commit. That is deliberate: the caller learns about the collision at the operation that
    # caused it, not at whatever unrelated write happens to flush next.
    with pytest.raises(IntegrityError):
        store.create(broker="kite", scope="kite:legacy")


def test_an_unnamed_owner_is_the_legacy_owner_not_null(session):
    """On a table that grants the authority to trade, "belongs to the original owner" and "we do
    not know whose this is" must never be the same value."""
    row = OwnedConnectionStore(session).create(broker="kite", scope="kite:legacy")
    session.flush()
    assert row.owner_id == LEGACY_OWNER_ID
    assert row.owner_id is not None


# ── the broker must actually exist ────────────────────────────────────────

def test_a_connection_to_an_unsupported_broker_is_refused_at_creation(session):
    """Refusing here rather than at first use is the point. A connection naming a broker with no
    adapter is a row that looks configured and can never work — and the operator finds out at
    09:15 instead of at the moment they created it."""
    store = OwnedConnectionStore(session, "alice")
    with pytest.raises(BrokerNotSupported):
        store.create(broker="angelone", scope="angel:main")   # PLANNED, no adapter
    with pytest.raises(BrokerNotSupported):
        store.create(broker="zeroda", scope="typo:main")      # not a broker at all


def test_declared_capabilities_default_to_the_adapters(session):
    store = OwnedConnectionStore(session, "alice")
    row = store.create(broker="upstox", scope="upstox:data")
    session.flush()
    assert set(json.loads(row.capabilities_json)) == {caps.HISTORICAL_DATA, caps.LIVE_QUOTES}
    assert caps.LIVE_EXECUTION not in row.to_dict()["capabilities"]


# ── the credential at rest ────────────────────────────────────────────────

def test_the_stored_credential_is_not_the_token(session, vault_key):
    """The database file is rsynced, backed up and copied between environments. A plaintext
    token in it is the account."""
    store = OwnedConnectionStore(session, "alice")
    row = store.create(broker="kite", scope="kite:main")
    session.flush()
    store.store_credential(row.id, {"access_token": "SUPER-SECRET-TOKEN"})
    session.flush()

    blob = session.get(BrokerConnection, row.id).credential_ciphertext
    assert blob and "SUPER-SECRET-TOKEN" not in blob
    assert "SUPER-SECRET-TOKEN" not in json.dumps(row.to_dict())


def test_the_serialisable_form_carries_no_credential_field_at_all(session, vault_key):
    """`to_dict` reaches the API, the logs and the operator's browser. Absence of the field is
    stronger than a redacted value: there is nothing to accidentally un-redact."""
    store = OwnedConnectionStore(session, "alice")
    row = store.create(broker="kite", scope="kite:main")
    session.flush()
    store.store_credential(row.id, {"access_token": "T"})
    d = row.to_dict()
    assert "credential_ciphertext" not in d and "credential_key_id" not in d
    assert d["has_credential"] is True


def test_a_round_trip_returns_the_bundle_not_just_a_token(session, vault_key):
    """One bundle shape for every broker. Dhan needs a token AND a client id; a TOTP broker
    stores a seed. A per-broker credential shape would put a broker branch in the vault."""
    store = OwnedConnectionStore(session, "alice")
    row = store.create(broker="dhan", scope="dhan:main")
    session.flush()
    store.store_credential(row.id, {"access_token": "T", "client_id": "1000000001"})
    assert vault.unseal(row.credential_ciphertext) == {
        "access_token": "T", "client_id": "1000000001"}


def test_no_key_means_refusal_not_plaintext(session, monkeypatch):
    """Fail closed. Quietly storing plaintext when unconfigured is how a development default
    reaches production, and it is invisible exactly where it matters."""
    monkeypatch.delenv(vault.ENV_KEY, raising=False)
    store = OwnedConnectionStore(session, "alice")
    row = store.create(broker="kite", scope="kite:main")
    session.flush()
    with pytest.raises(vault.CredentialVaultUnavailable):
        store.store_credential(row.id, {"access_token": "T"})
    assert session.get(BrokerConnection, row.id).credential_ciphertext is None


def test_a_tampered_ciphertext_fails_to_authenticate(session, vault_key):
    """AES-GCM is authenticated, and that is why. An attacker who can write to the database but
    not read the key must not be able to flip a stored credential to one they control."""
    store = OwnedConnectionStore(session, "alice")
    row = store.create(broker="kite", scope="kite:main")
    session.flush()
    store.store_credential(row.id, {"access_token": "T"})
    raw = bytearray(base64.b64decode(row.credential_ciphertext))
    raw[-1] ^= 0x01
    row.credential_ciphertext = base64.b64encode(bytes(raw)).decode()
    with pytest.raises(vault.CredentialDecryptionFailed):
        vault.unseal(row.credential_ciphertext)


def test_a_rotated_key_is_a_loud_failure_not_a_silent_absence(session, vault_key, monkeypatch):
    """A credential that silently reads as absent looks exactly like "this owner never
    connected", and the operator would reconnect rather than investigate a key mismatch."""
    store = OwnedConnectionStore(session, "alice")
    row = store.create(broker="kite", scope="kite:main")
    session.flush()
    store.store_credential(row.id, {"access_token": "T"})
    written_with = row.credential_key_id

    monkeypatch.setenv(vault.ENV_KEY, OTHER_KEY)
    assert vault.key_id() != written_with, "the fingerprint must distinguish two keys"
    with pytest.raises(vault.CredentialDecryptionFailed):
        vault.unseal(row.credential_ciphertext)


def test_the_key_is_never_a_row(session, vault_key):
    """ADR 0015's central claim, checked rather than trusted: nothing in the money plane holds
    key material, so a database compromise alone is not a credential compromise."""
    store = OwnedConnectionStore(session, "alice")
    row = store.create(broker="kite", scope="kite:main")
    session.flush()
    store.store_credential(row.id, {"access_token": "T"})
    key_b64 = os.environ[vault.ENV_KEY]
    dumped = json.dumps([
        {c.name: str(getattr(r, c.name)) for c in BrokerConnection.__table__.columns}
        for r in session.query(BrokerConnection).all()])
    assert key_b64 not in dumped
    assert base64.b64decode(key_b64).hex() not in dumped
    # The key id is a hash, and the point of a hash here is that it is not the key.
    assert row.credential_key_id and row.credential_key_id != key_b64


# ── revocation ────────────────────────────────────────────────────────────

def test_revoking_destroys_the_credential_but_keeps_the_row(session, vault_key):
    """"This credential was revoked at 14:02" is a fact someone will need to establish, and a
    deleted row establishes nothing. But keeping the ciphertext would mean a revoked connection
    is still a credential at rest, which is what revocation is supposed to end."""
    store = OwnedConnectionStore(session, "alice")
    row = store.create(broker="kite", scope="kite:main")
    session.flush()
    store.store_credential(row.id, {"access_token": "T"})

    store.revoke(row.id)
    session.flush()
    assert row.status == "revoked" and row.revoked_at is not None
    assert row.credential_ciphertext is None and row.credential_key_id is None
    assert session.get(BrokerConnection, row.id) is not None
    assert store.list() == []                       # active-only by default
    assert [c.id for c in store.list(include_revoked=True)] == [row.id]


# ── the bridge to a running engine ────────────────────────────────────────

def test_the_live_connection_reads_the_credential_late_not_once(session, vault_key):
    """Kite tokens expire ~06:00 IST. `token_source` is a source rather than a value so a daily
    re-login propagates without a backend restart — and so a revoked connection stops producing
    a token at the NEXT ORDER rather than at the next restart."""
    store = OwnedConnectionStore(session, "alice")
    row = store.create(broker="kite", scope="kite:main")
    session.flush()
    store.store_credential(row.id, {"access_token": "MORNING"})
    # COMMIT, not flush: `token_source` deliberately reads through its own short-lived session
    # rather than closing over this one, so an uncommitted row is invisible to it. That is the
    # behaviour under test — the alternative holds a pooled connection for the life of the
    # process, which is the shape behind the 2026-07-23 pool collapse.
    session.commit()

    conn = store.live_connection(row.id)
    assert conn.broker == "kite" and conn.scope == "kite:main"
    assert conn.token_source() == "MORNING"

    store.store_credential(row.id, {"access_token": "AFTERNOON"})
    session.commit()
    assert conn.token_source() == "AFTERNOON", "the connection cached a token it should re-read"

    store.revoke(row.id)
    session.commit()
    assert conn.token_source() is None, "a revoked connection still produced a credential"


def test_a_revoked_connection_cannot_be_bound_at_all(session, vault_key):
    store = OwnedConnectionStore(session, "alice")
    row = store.create(broker="kite", scope="kite:main")
    session.flush()
    store.revoke(row.id)
    with pytest.raises(ConnectionNotFound):
        store.live_connection(row.id)


def test_the_live_connection_carries_the_declared_capabilities(session, vault_key):
    """`make_broker` decides whether to build a live broker from these. A connection whose
    stored capabilities did not survive the round trip would be refused for execution despite
    being a perfectly good Kite login."""
    store = OwnedConnectionStore(session, "alice")
    row = store.create(broker="kite", scope="kite:main",
                       capabilities=frozenset({caps.LIVE_EXECUTION, caps.MARKET_ORDERS}))
    session.flush()
    conn = store.live_connection(row.id)
    assert caps.LIVE_EXECUTION in conn.capabilities


def test_a_missing_vault_key_refuses_the_order_rather_than_sending_it_unauthenticated(
        session, vault_key, monkeypatch):
    """The engine keeps running; this connection simply cannot authenticate. `None` is what the
    order client turns into a rejected-unauthenticated order, which is the safe outcome — the
    unsafe one would be an exception escaping into the risk loop."""
    store = OwnedConnectionStore(session, "alice")
    row = store.create(broker="kite", scope="kite:main")
    session.flush()
    store.store_credential(row.id, {"access_token": "T"})
    session.commit()
    conn = store.live_connection(row.id)

    monkeypatch.delenv(vault.ENV_KEY, raising=False)
    assert conn.token_source() is None


def test_the_engines_owner_id_is_the_api_principals_owner_id():
    """Two independently invented owner identities would resolve the same human to two different
    sets of resources — authenticated requests seeing one book and the engine writing to another
    — and the symptom is missing data, not an error."""
    from app.api.principal import OWNER
    from app.core.config import get_settings
    assert LEGACY_OWNER_ID == OWNER.id
    assert get_settings().owner_id == LEGACY_OWNER_ID


# ── gaps found by scripts/tenancy_mutations.py, not by reading the code ────

def test_an_explicitly_empty_owner_is_refused_rather_than_defaulted(session):
    """**Corrected 2026-08-10 after an independent security review.** The first version of this
    test asserted the opposite — that `""`, `"   "` and `None` all resolve to the legacy owner —
    on availability grounds. That was wrong, and it was wrong in the dangerous direction.

    Omitting the argument is the single-owner default and is fine. *Passing* an empty one is a
    caller bug: a header parsed to `""`, a principal field not populated, a service call with no
    principal. Resolving any of those to `"owner"` — the identity holding the live Zerodha
    credential — is principal substitution enabled by a convenience, and it becomes reachable
    the moment connection routes exist.
    """
    assert OwnedConnectionStore(session).owner_id == LEGACY_OWNER_ID   # omitted: fine
    for empty in ("", "   ", None):
        with pytest.raises(ValueError):
            OwnedConnectionStore(session, empty)


def test_the_late_credential_read_stops_if_the_row_changes_owner(session, vault_key):
    """Defence in depth, and reachable. `live_connection` checks ownership once, at build time,
    but the `Connection` it returns outlives that check — the engine holds it for the life of
    the process. If the row is reassigned to another owner (an ownership transfer, a support
    action, a bad migration), the credential must stop flowing to the old owner's engine at the
    next order rather than at the next restart."""
    store = OwnedConnectionStore(session, "alice")
    row = store.create(broker="kite", scope="kite:main")
    session.commit()
    store.store_credential(row.id, {"access_token": "ALICE-TOKEN"})
    session.commit()

    conn = store.live_connection(row.id)
    assert conn.token_source() == "ALICE-TOKEN"

    row.owner_id = "bob"
    session.commit()
    assert conn.token_source() is None, (
        "a connection reassigned to another owner still handed its credential to the first "
        "owner's engine")


# ── the withdrawal path, end to end ───────────────────────────────────────
# Added after an independent security review found that these tests stopped at the STORE
# boundary: they asserted `token_source()` returns None and called that "the order is refused
# unauthenticated". No such refusal existed — `KiteOrderClient._sync_token` discarded a None and
# kept using the token cached at construction, so a revoked connection kept placing real orders
# for the life of the process. The mechanism was named in three docstrings and implemented in
# none. These tests reach the consumer.

def test_a_withdrawn_credential_refuses_at_the_order_client_not_just_the_store(session, vault_key):
    """The end of the chain the store's `None` was supposed to reach.

    Revoking must stop orders at the NEXT ORDER. Anything weaker means the owner revokes a
    compromised credential, sees `CONNECTION_REVOKED` in the log, and the engine keeps trading
    on that account until someone restarts the backend.
    """
    from app.engine.kite_order_client import CredentialWithdrawn, KiteOrderClient

    store = OwnedConnectionStore(session, "alice")
    row = store.create(broker="kite", scope="kite:main")
    session.commit()
    store.store_credential(row.id, {"access_token": "LIVE-TOKEN"})
    session.commit()
    conn = store.live_connection(row.id)

    seen = []
    kite = type("K", (), {"set_access_token": lambda self, t: seen.append(t)})()
    client = KiteOrderClient(kite, token_source=conn.token_source)

    client._sync_token()
    assert seen == ["LIVE-TOKEN"]

    store.revoke(row.id)
    session.commit()
    with pytest.raises(CredentialWithdrawn):
        client._sync_token()
    assert seen[-1] == "", "the cached token was not cleared from the wire client"


def test_a_connection_that_never_authenticated_is_not_treated_as_withdrawn(vault_key):
    """The distinction that keeps this fix from being a behaviour change for the legacy path.

    "Never had a token" is the ordinary pre-Connect-Kite state and already fails safely at the
    broker's own auth check. Only a credential that WAS working and is now gone is a withdrawal.
    """
    from app.engine.kite_order_client import KiteOrderClient

    kite = type("K", (), {"set_access_token": lambda self, t: None})()
    client = KiteOrderClient(kite, token_source=lambda: None)
    client._sync_token()          # must not raise
    client._sync_token()


def test_a_rotated_vault_key_also_stops_orders(session, vault_key, monkeypatch):
    """Same hole, different cause. A key rotation makes the credential unreadable; the engine
    must stop rather than keep using the token it read this morning."""
    from app.engine.kite_order_client import CredentialWithdrawn, KiteOrderClient

    store = OwnedConnectionStore(session, "alice")
    row = store.create(broker="kite", scope="kite:main")
    session.commit()
    store.store_credential(row.id, {"access_token": "LIVE-TOKEN"})
    session.commit()
    conn = store.live_connection(row.id)

    kite = type("K", (), {"set_access_token": lambda self, t: None})()
    client = KiteOrderClient(kite, token_source=conn.token_source)
    client._sync_token()

    monkeypatch.delenv(vault.ENV_KEY, raising=False)
    monkeypatch.setattr("app.core.credential_vault._configured_key", lambda: "")
    with pytest.raises(CredentialWithdrawn):
        client._sync_token()


def test_the_vault_key_can_be_configured_the_way_env_example_documents(monkeypatch):
    """`.env.example` tells the operator to put `PT_CREDENTIAL_KEY` in `backend/.env`.
    pydantic-settings reads that file itself and does NOT export to `os.environ`, so a vault
    reading only the environment ignored the documented path while reporting "is not set"."""
    monkeypatch.delenv(vault.ENV_KEY, raising=False)
    monkeypatch.setattr(get_settings(), "credential_key", KEY)
    assert vault.available() is True
    assert vault.unseal(vault.seal({"access_token": "T"})[0]) == {"access_token": "T"}


def test_a_real_environment_variable_still_wins_over_the_file(monkeypatch):
    """Precedence matches pydantic-settings' own, so a deployment override is not silently
    ignored by a stale value in a checked-in file."""
    monkeypatch.setenv(vault.ENV_KEY, KEY)
    monkeypatch.setattr(get_settings(), "credential_key", OTHER_KEY)
    import base64
    assert vault.key_material() == base64.b64decode(KEY)


# ── F1/F2/F3 from the execution-safety review, 2026-08-10 ─────────────────
# The withdrawal tests above are not enough and the review said why: they call `_sync_token()`
# first, which seeds the client's state. Production does NOT take that shape — `broker_factory`
# authenticates the wire object itself and then constructs the client. These tests build the
# client the way the composition root does.

class _FakeKite:
    def __init__(self):
        self.token = None

    def set_access_token(self, t):
        self.token = t


def _client_built_like_broker_factory(conn):
    """Reproduce `broker_factory`'s construction order exactly: authenticate the wire object,
    THEN build the client. This is the shape in which the withdrawal guard was inert."""
    from app.engine.kite_order_client import KiteOrderClient

    kite = _FakeKite()
    token = conn.token_source()
    if token:
        kite.set_access_token(token)          # broker_factory.py does this
    return KiteOrderClient(kite, token_source=conn.token_source), kite


def test_revocation_after_startup_refuses_even_though_the_client_never_synced(session, vault_key):
    """**F1 — the defect the withdrawal fix itself had.**

    Engine starts 09:10 holding a valid credential. Owner revokes at 09:12. A signal fires at
    09:20. Before this test, `_sync_token` returned silently — the client held a token it had
    never *recorded*, so the withdrawal branch could not fire — and a REAL order went out on a
    revoked account. For the life of the process.
    """
    from app.engine.kite_order_client import CredentialWithdrawn

    store = OwnedConnectionStore(session, "alice")
    row = store.create(broker="kite", scope="kite:main")
    session.commit()
    store.store_credential(row.id, {"access_token": "LIVE-TOKEN"})
    session.commit()
    conn = store.live_connection(row.id)

    client, kite = _client_built_like_broker_factory(conn)
    assert kite.token == "LIVE-TOKEN"

    store.revoke(row.id)
    session.commit()

    with pytest.raises(CredentialWithdrawn):
        client._sync_token()
    assert kite.token == "", "the revoked token was left on the wire client"


def test_the_refusal_is_latched_and_does_not_fire_only_once(session, vault_key):
    """**F3.** `_sync_token` cleared `_last_token` before raising, so the SECOND withdrawn call
    took the never-authenticated branch and returned normally — the order then reached Kite with
    a blanked token and failed as a generic error that `find_fill` swallows into `None`."""
    from app.engine.kite_order_client import CredentialWithdrawn

    store = OwnedConnectionStore(session, "alice")
    row = store.create(broker="kite", scope="kite:main")
    session.commit()
    store.store_credential(row.id, {"access_token": "LIVE-TOKEN"})
    session.commit()
    conn = store.live_connection(row.id)
    client, _ = _client_built_like_broker_factory(conn)

    store.revoke(row.id)
    session.commit()
    for attempt in range(3):
        with pytest.raises(CredentialWithdrawn):
            client._sync_token()


def test_a_stored_connection_carries_a_real_tick_reader(session, vault_key, monkeypatch):
    """**F2.** `live_connection` built a `Connection` with no `tick_source`, so
    `KiteOrderClient._tick` fell back to the hardcoded 0.05 grid for every instrument. An
    intraday LT (0.10) or MARUTI (1.00) protective stop is then rounded off-grid, rejected by
    Zerodha, and the position runs the session with NO exchange-side backstop — the 2026-07-15
    incident, reintroduced through the path this design calls preferred.
    """
    from app.core.config import get_settings
    from app.db.session import SessionLocal
    from app.providers.connection import configured_execution_connection
    from app.providers.upstox import UpstoxProvider

    store = OwnedConnectionStore(session, "owner")
    store.create(broker="kite", scope="kite:stored")
    session.commit()

    s = get_settings()
    monkeypatch.setattr(s, "provider", "upstox")
    monkeypatch.setattr(s, "execution_provider", "")
    monkeypatch.setattr(s, "execution_connection", "kite:stored")

    with SessionLocal() as lookup:
        conn = configured_execution_connection(UpstoxProvider(), session=lookup)

    assert conn is not None
    assert callable(conn.tick_source), (
        "a stored connection reached the order client with no tick reader; every protective "
        "stop would be rounded to the 0.05 grid")
