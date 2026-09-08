"""How a connection acquires a credential — one contract, several broker-shaped answers.

The connection API can store a credential and the engine can use one. Nothing could **obtain**
one per-connection: `/api/login` and `/api/session` drive the process-global `KiteProvider` and
write `access_token.json`, a single file for a single account. That is the single-owner design
showing through, and it is the half that keeps "a connection row exists" from meaning "a user
connected their broker".

`BrokerSpec.auth` already says which shape each broker needs, and the shapes are genuinely
different rather than cosmetic:

  * `DAILY_OAUTH` — a redirect to the broker, a `request_token` back, exchanged for an access
    token that dies each morning. Two round trips, and the second one must be authenticated as
    the same owner who started the first.
  * `LONG_LIVED_KEY` — no interactive flow at all. The user pastes a token from the broker's
    dashboard, which `POST /api/connections/{id}/credential` already does. Such a broker gets
    `NoInteractiveLogin`, which **refuses with an explanation** rather than returning a login
    URL that would 404 at the broker.
  * `TOTP_SESSION` — programmatic login from a stored seed. None built; the planned brokers that
    need it have no adapter either, so nothing here pretends to have one.

**The credential bundle is per-connection, and so are the app keys.** `api_key`/`api_secret`
come from the connection's own stored secrets, never from `Settings`. Falling back to the
process-wide `KITE_API_KEY` would mean every owner's login ran through the owner's Zerodha
app registration — which is a cross-tenant credential path dressed as a convenience default.
A connection with no app keys is refused and told to store them first.

**No adapter may be written from memory of an API** (see `brokers.py`). Upstox is `DAILY_OAUTH`
and has a data adapter, but no authenticator is registered for it here, because writing its token
exchange without reading its current documentation is how you get a flow that looks right and
fails at 06:00. It refuses by absence, which is the honest state.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable


class BrokerAuthError(RuntimeError):
    """The login flow could not be completed. Carries a message safe to show a caller —
    implementations must not interpolate a secret, a seed or a token into it."""


class NoInteractiveLogin(BrokerAuthError):
    """This broker has no redirect flow, by design rather than by omission.

    Separate from `BrokerAuthError` so a route can answer 400-with-instructions ("paste the
    token from your broker dashboard") instead of 502-something-broke. A long-lived-key broker
    is not a degraded OAuth broker.
    """


@runtime_checkable
class BrokerAuthenticator(Protocol):
    """Two steps, and the second must be able to run in a different request than the first."""

    def login_url(self, secrets: dict) -> str:
        """Where to send the user's browser. Raises `NoInteractiveLogin` if there is none."""
        ...

    def exchange(self, secrets: dict, request_token: str) -> dict:
        """Trade the broker's one-time token for a credential bundle to seal.

        Returns the WHOLE bundle to store, not just the access token: `secrets` goes in and a
        superset comes out, so the app keys survive the exchange. Dropping them would work
        until tomorrow morning, when the re-login has nothing to authenticate with — a failure
        that appears exactly once a day and looks like an expired token.
        """
        ...


def _required(secrets: dict, *names: str) -> tuple[str, ...]:
    """Fetch required fields or refuse, naming what is missing and never what was found."""
    missing = [n for n in names if not (secrets or {}).get(n)]
    if missing:
        raise BrokerAuthError(
            f"this connection has no {', '.join(missing)} stored. POST them to "
            f"/api/connections/{{id}}/credential first — the app keys are per-connection, so "
            f"each owner authenticates through their own broker app registration.")
    return tuple(str(secrets[n]) for n in names)


class KiteAuthenticator:
    """Zerodha Kite Connect v3 — https://kite.trade/docs/connect/v3/user/#login-flow.

    Deliberately does NOT write `access_token.json`. That file is the process-global
    single-account credential and `KiteProvider` owns it; a per-connection login writing to it
    would have two owners' logins overwriting each other in one file, which is the exact
    single-account assumption this seam exists to remove. The bundle goes to the vault instead,
    keyed by connection.
    """

    def _client(self, api_key: str):
        """Use the dedicated DATA transport, never a broad provider client.

        The login URL is local string construction. The one-time exchange may use
        only ``api.token``. Every account, portfolio, order, GTT, margin,
        mutation and unknown route is refused at the transport chokepoint.
        """
        from app.providers.zerodha_data_runtime import ZerodhaDataKite
        return ZerodhaDataKite(api_key=api_key)

    def login_url(self, secrets: dict) -> str:
        (api_key,) = _required(secrets, "api_key")
        return self._client(api_key).login_url()

    def exchange(self, secrets: dict, request_token: str) -> dict:
        api_key, api_secret = _required(secrets, "api_key", "api_secret")
        if not request_token:
            raise BrokerAuthError("no request_token supplied")
        try:
            data = self._client(api_key).generate_session(
                request_token, api_secret=api_secret)
        except Exception as e:                              # noqa: BLE001
            # The type name only. Kite's exception messages have been observed to echo request
            # parameters, and this message reaches an API response and the log ring buffer that
            # `/api/logs` serves.
            raise BrokerAuthError(
                f"Kite refused the session exchange ({type(e).__name__}). A request_token is "
                f"single-use and expires within minutes — start the login again.") from e
        token = (data or {}).get("access_token")
        if not token:
            raise BrokerAuthError("Kite returned no access_token")
        # The app keys are carried through, not replaced. See `exchange`'s docstring.
        return {**{k: v for k, v in (secrets or {}).items() if isinstance(v, str)},
                "access_token": str(token),
                **({"public_token": str(data["public_token"])}
                   if data.get("public_token") else {}),
                **({"user_id": str(data["user_id"])} if data.get("user_id") else {})}


class PastedTokenAuthenticator:
    """For brokers whose credential is issued in a dashboard, not through a redirect.

    Dhan's token is long-lived and copied by hand. There is nothing to redirect to, and
    inventing a URL would send the user to a 404 with no way to tell that from a broker outage.
    """

    def __init__(self, display_name: str, docs_url: str) -> None:
        self.display_name, self.docs_url = display_name, docs_url

    def login_url(self, secrets: dict) -> str:
        raise NoInteractiveLogin(
            f"{self.display_name} has no redirect login. Generate the token from its dashboard "
            f"({self.docs_url}) and POST it to /api/connections/{{id}}/credential.")

    def exchange(self, secrets: dict, request_token: str) -> dict:
        raise NoInteractiveLogin(
            f"{self.display_name} issues its credential directly; there is no token to "
            f"exchange. POST it to /api/connections/{{id}}/credential.")


def kite_authenticator() -> KiteAuthenticator:
    return KiteAuthenticator()


def dhan_authenticator() -> PastedTokenAuthenticator:
    return PastedTokenAuthenticator("Dhan", "https://dhanhq.co/docs/v2/")


__all__ = ["BrokerAuthenticator", "BrokerAuthError", "NoInteractiveLogin",
           "KiteAuthenticator", "PastedTokenAuthenticator",
           "kite_authenticator", "dhan_authenticator"]
