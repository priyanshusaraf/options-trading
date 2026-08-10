"""The broker registry — one place that answers "which brokers does Strategy OS support?"

The product target is every major Indian retail broker, not one. That changes what the
valuable artefact is: with seven or more adapters, the *registry and its contract* matter more
than any single adapter, because the way this goes wrong at seven is not a bug in one of them —
it is seven slightly different answers to the same question.

So this module is declarative and total, and it carries one rule that the rest of the system
leans on:

    **A broker is SUPPORTED only if its adapter exists and passes the conformance contract.**

Everything else is `PLANNED`. A `PLANNED` broker is refused at selection with a message naming
what is missing — never half-wired, never silently falling through to a working provider. That
distinction is the whole point of the file: this codebase's defining defect is a mechanism that
looks wired and is not, and a registry is the single most attractive place for that defect to
live. A row here is a claim, and `tests/test_broker_registry.py` is what makes it a fact.

**No adapter may be written from memory of an API.** Every request-building line must come from
that broker's published documentation, read at the time of writing — `docs_url` is on the spec
for exactly that reason, and the Upstox adapter's own history is the precedent (the API was read
in commit `1ccb9d4` *before* the adapter was written in the next one). An endpoint guessed from
a similar broker's shape produces valid-looking prices for the wrong instrument.

**Licence note.** `~/dev/openalgo` (AGPL-3.0) implements 35 Indian brokers and is the reason the
*shape* of this problem is known to be tractable — a per-broker adapter directory with a fixed
contract. It is a behaviour reference and a catalogue of solved problems. **Re-derived here,
never transcribed**, and no file from it is read into this tree. §13's network clause is fatal to
a hosted product, so if actual code reuse ever looks necessary, that is an owner/legal gate.
"""
from __future__ import annotations

import dataclasses
import enum
import importlib


class Status(str, enum.Enum):
    """How far a broker has actually got. Only `SUPPORTED` is selectable."""

    SUPPORTED = "supported"
    """An adapter exists, is registered, and is held to the conformance contract."""

    PLANNED = "planned"
    """Wanted, not built. Selecting it is refused with a message that says so."""


class Auth(str, enum.Enum):
    """How a session is established. This decides what the connection UI and the token
    lifecycle look like, and the differences are not cosmetic — a broker that issues a daily
    token needs a re-login every morning, and one that issues a long-lived key does not."""

    DAILY_OAUTH = "daily_oauth"
    """Interactive login, token expires each morning (Zerodha ~06:00 IST, Upstox similar).
    Headless auto-login violates the broker's ToS. Permanent, not a gap."""

    TOTP_SESSION = "totp_session"
    """Programmatic login with a TOTP seed. Longer-lived, and the seed is a stored secret with
    the same handling requirements as a token."""

    LONG_LIVED_KEY = "long_lived_key"
    """An API key/secret pair that does not expire daily."""


@dataclasses.dataclass(frozen=True)
class BrokerSpec:
    """One broker, and what this system can currently do with it."""

    key: str
    """The canonical broker id. This is the value carried in `Connection.broker` and written
    into every `ExecutionIntent`, so it is an identifier, not a label — renaming one orphans
    historical rows."""

    display_name: str
    status: Status
    auth: Auth
    docs_url: str
    """The broker's own API documentation. Load-bearing: an adapter is written FROM this, and a
    reviewer checks the request mapping AGAINST it."""

    data: str | None = None
    """`"module:ClassName"` for the `MarketDataProvider`, or None if there is no data adapter."""

    venue: str | None = None
    """`"module:ClassName"` for the `ExecutionVenue`, or None if this broker cannot place orders
    in this build. Data and execution are separate roles and a broker may serve either alone —
    that is the whole point of the connection seam."""

    venue_builder: str | None = None
    """`"module:function"` taking `(connection, settings)` and returning `(client, venue)`.

    The registry owns this rather than `broker_factory` because the *construction* of a live
    order path is broker-specific in a way the venue interface deliberately is not: Kite needs a
    `LiveExecutionKite` seeded with an api key, Dhan needs a transport carrying two credentials.
    Leaving that in the composition root is what kept `conn.broker != "kite"` there as a
    hardcoded string, and a hardcoded broker name in the one place that decides whether real
    orders go out is exactly the thing the registry exists to remove.
    """

    notes: str = ""

    def load_builder(self):
        return _load(self.venue_builder, self.key, "venue builder")

    def load_data(self):
        return _load(self.data, self.key, "data")

    def load_venue(self):
        return _load(self.venue, self.key, "venue")


def _load(target: str | None, key: str, role: str):
    if not target:
        return None
    module, _, name = target.partition(":")
    try:
        return getattr(importlib.import_module(module), name)
    except (ImportError, AttributeError) as e:
        # Loud, and specifically not a silent None. A registry row pointing at a module that
        # does not exist is the registry lying about itself, which is the one failure this file
        # is built to make impossible.
        raise BrokerNotSupported(
            f"broker {key!r} declares a {role} adapter at {target!r} which cannot be "
            f"imported: {type(e).__name__}: {e}") from e


class BrokerNotSupported(LookupError):
    """Asked for a broker this build cannot serve in the role requested.

    Raised rather than answered with a default, because every available default is worse:
    falling back to the mock routes real orders at a synthetic market, and falling back to the
    configured provider trades the wrong account.
    """


# ── the registry ──────────────────────────────────────────────────────────
# Ordered by Indian retail recognition. `PLANNED` rows are a work list with the documentation
# already located, NOT a support claim — `Status` is what a caller reads, and
# `tests/test_broker_registry.py` fails the build if a PLANNED row acquires an adapter without
# its status changing, or if a SUPPORTED row loses one.

BROKERS: tuple[BrokerSpec, ...] = (
    BrokerSpec(
        key="kite", display_name="Zerodha Kite", status=Status.SUPPORTED,
        auth=Auth.DAILY_OAUTH, docs_url="https://kite.trade/docs/connect/v3/",
        data="app.providers.kite:KiteProvider",
        venue="app.engine.kite_venue:KiteVenue",
        venue_builder="app.engine.kite_venue:build_live_venue",
        notes="The reference implementation and the only broker this build has ever placed a "
              "real order through. Its vocabulary (MIS/NRML/GTT/SL-M) is confined to kite_venue.",
    ),
    BrokerSpec(
        key="upstox", display_name="Upstox", status=Status.SUPPORTED,
        auth=Auth.DAILY_OAUTH, docs_url="https://upstox.com/developer/api-documentation/",
        data="app.providers.upstox:UpstoxProvider",
        venue=None,
        notes="Data only, deliberately. It serves candles and quotes and declares nothing else; "
              "naming it for execution is refused by make_broker rather than half-working. "
              "Proven end-to-end against Kite execution in tests/test_split_routing.py.",
    ),
    BrokerSpec(
        key="angelone", display_name="Angel One SmartAPI", status=Status.PLANNED,
        auth=Auth.TOTP_SESSION, docs_url="https://smartapi.angelbroking.com/docs",
        notes="Largest of the planned set by active clients. TOTP session login means the seed "
              "is a stored secret — ADR 0015 puts it in the money plane, encrypted.",
    ),
    BrokerSpec(
        key="fyers", display_name="Fyers", status=Status.PLANNED,
        auth=Auth.DAILY_OAUTH, docs_url="https://myapi.fyers.in/docsv3",
        notes="Strong API reputation among algo traders.",
    ),
    BrokerSpec(
        key="dhan", display_name="Dhan", status=Status.SUPPORTED,
        auth=Auth.LONG_LIVED_KEY, docs_url="https://dhanhq.co/docs/v2/",
        data="app.providers.dhan:DhanProvider",
        venue="app.engine.dhan_venue:DhanVenue",
        venue_builder="app.engine.dhan_venue:build_live_venue",
        notes="Data only IN THIS BUILD. Long-lived token, so no daily re-login — the first "
              "broker whose connection lifecycle differs from Kite's, which is why Auth is on "
              "the spec. Two credentials (access-token AND client-id). Its interval coverage is "
              "genuinely NARROWER than this engine's vocabulary: no 3/10/30-minute; it refuses "
              "them. "
              "**`app/engine/dhan_venue.py` exists and is tested** (13 mutations reddened) but "
              "`venue` stays None here on purpose: `make_broker` can build no Dhan order client "
              "yet, so claiming a venue would make the registry disagree with the one place "
              "that decides. It is registered in the same slice that makes it buildable. Note "
              "that Dhan has NO GTT equivalent, so an options deployment cannot run on Dhan "
              "execution — the venue refuses SERVER_TRIGGER rather than substituting.",
    ),
    BrokerSpec(
        key="fivepaisa", display_name="5paisa", status=Status.PLANNED,
        auth=Auth.TOTP_SESSION, docs_url="https://www.5paisa.com/developerapi/overview",
    ),
    BrokerSpec(
        key="icici", display_name="ICICI Direct Breeze", status=Status.PLANNED,
        auth=Auth.LONG_LIVED_KEY, docs_url="https://api.icicidirect.com/apiuser/home",
        notes="Bank-broker. Its session model differs enough from the discount brokers that it "
              "is worth doing before declaring the adapter contract stable.",
    ),
    BrokerSpec(
        key="kotak", display_name="Kotak Neo", status=Status.PLANNED,
        auth=Auth.TOTP_SESSION, docs_url="https://documenter.getpostman.com/view/21532406/UzXKXJXP",
    ),
    BrokerSpec(
        key="groww", display_name="Groww", status=Status.PLANNED,
        auth=Auth.LONG_LIVED_KEY, docs_url="https://groww.in/trade-api/docs",
        notes="Largest retail broker by active clients; its trading API is the newest of this "
              "set, so treat the documentation as the only source and re-read it at build time.",
    ),
)

BY_KEY: dict[str, BrokerSpec] = {b.key: b for b in BROKERS}


def spec(key: str) -> BrokerSpec:
    """The spec for `key`, or `BrokerNotSupported` naming what is available."""
    found = BY_KEY.get((key or "").strip().lower())
    if found is None:
        raise BrokerNotSupported(
            f"no broker named {key!r}. Known: {sorted(BY_KEY)}; "
            f"selectable today: {sorted(b.key for b in supported())}")
    return found


def supported() -> tuple[BrokerSpec, ...]:
    return tuple(b for b in BROKERS if b.status is Status.SUPPORTED)


def data_adapter(key: str):
    """The `MarketDataProvider` CLASS for `key`. Refuses a broker that serves no data."""
    s = spec(key)
    cls = s.load_data()
    if cls is None:
        raise BrokerNotSupported(
            f"broker {s.key!r} ({s.display_name}) has no market-data adapter in this build"
            + (f"; it is {s.status.value} — see {s.docs_url}" if s.status is Status.PLANNED
               else ""))
    return cls


def build_live_venue(connection, settings):
    """Construct the live order client and venue for `connection`'s broker.

    This replaced `make_broker`'s `if conn.broker != "kite": raise`. The refusal it raises is the
    same one, and it is still the thing standing between a foreign credential and a Kite
    endpoint — but it is now a LOOKUP, so adding a broker is a registry row plus a builder
    rather than an edit to the function that decides whether real orders go out.
    """
    s = spec(getattr(connection, "broker", ""))
    builder = s.load_builder()
    if builder is None:
        raise BrokerNotSupported(
            f"broker {s.key!r} ({s.display_name}) declares live execution but has no order "
            f"client in this build. Refusing rather than sending its credential to another "
            f"broker's endpoint.")
    return builder(connection, settings)


def venue_adapter(key: str):
    """The `ExecutionVenue` CLASS for `key`. Refuses a broker that cannot place orders."""
    s = spec(key)
    cls = s.load_venue()
    if cls is None:
        raise BrokerNotSupported(
            f"broker {s.key!r} ({s.display_name}) cannot place orders in this build — it has "
            f"no ExecutionVenue. Refusing rather than routing its credential somewhere else.")
    return cls
