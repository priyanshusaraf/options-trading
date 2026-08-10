"""The HTTP edge of the Upstox connection. Nothing above this file speaks HTTP.

Kept separate from the provider for one reason that has already cost this repository: the
adapter's *semantics* — interval mapping, the historical/intraday merge, forming-bar removal —
must be testable without a network, and the transport must be replaceable by a fixture that
returns real recorded payloads. `KiteProvider` mixes the two, which is why its tests stub
provider methods rather than the wire.

Three rules this file exists to hold:

  * **Every request has an explicit timeout.** A read with no deadline is an engine lane that
    never returns.
  * **The bearer token is never logged, never persisted, never rendered.** It is read from the
    connection and put in a header; it appears in no log line and no exception message here.
  * **A transport failure raises `ProviderReadError` carrying the API context** — endpoint,
    status and Upstox's own error code where it sent one. `[]` belongs exclusively to a
    successful read that contained no bars, and the whole point of the failure channel is that
    the two are never confused again.
"""
from __future__ import annotations

import dataclasses
from typing import Any

import httpx

from app.core.logging import log
from app.providers.base import ProviderReadError


BASE_URL = "https://api.upstox.com"

# Connect/read deadlines. The read budget is the one that matters: the engine's scan lane calls
# this synchronously, so an unbounded read is a stalled lane, and the risk loop behind it.
CONNECT_TIMEOUT = 5.0
READ_TIMEOUT = 10.0


@dataclasses.dataclass(frozen=True)
class UpstoxResponse:
    """A successful, parsed Upstox envelope. `data` is whatever the endpoint returned."""

    endpoint: str
    data: dict


class UpstoxTransport:
    """Signed, timed, bounded HTTP against the Upstox v3 API.

    `token_source` is a callable rather than a string so a re-authenticated connection is picked
    up without rebuilding the transport — the same shape `KiteOrderClient` uses to stay in
    lock-step with the data provider's token.
    """

    def __init__(self, token_source, *, base_url: str = BASE_URL, client=None) -> None:
        self._token_source = token_source
        self._base_url = base_url.rstrip("/")
        # Injectable so tests drive real recorded payloads through the real request-building
        # and error-mapping code, rather than stubbing the methods that do that work.
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(READ_TIMEOUT, connect=CONNECT_TIMEOUT))

    def _headers(self) -> dict[str, str]:
        token = self._token_source() if callable(self._token_source) else self._token_source
        if not token:
            # Not an outage and not "no data" — the connection simply cannot be used yet.
            raise ProviderReadError("upstox: no access token on this connection")
        return {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    def get(self, path: str, params: dict[str, Any] | None = None) -> UpstoxResponse:
        """GET `path`, or raise `ProviderReadError` with the context that failed.

        The token is deliberately absent from every message built here. An exception string ends
        up in logs, in `/api/health`, and in the operator's terminal.
        """
        url = f"{self._base_url}{path}"
        try:
            resp = self._client.get(url, headers=self._headers(), params=params)
        except ProviderReadError:
            raise
        except Exception as e:                    # noqa: BLE001 — timeouts, DNS, TLS, refused
            raise ProviderReadError(f"upstox GET {path}: transport failed: {type(e).__name__}: {e}") from e

        if resp.status_code != 200:
            raise ProviderReadError(
                f"upstox GET {path}: HTTP {resp.status_code}: {_error_detail(resp)}")
        try:
            body = resp.json()
        except Exception as e:                    # noqa: BLE001 — a 200 that is not JSON
            raise ProviderReadError(f"upstox GET {path}: malformed response body") from e
        if not isinstance(body, dict):
            raise ProviderReadError(
                f"upstox GET {path}: expected a JSON object, got {type(body).__name__}")
        # Upstox reports application errors inside a 200 envelope as well as by status code.
        if body.get("status") not in (None, "success"):
            raise ProviderReadError(
                f"upstox GET {path}: {body.get('status')}: {_envelope_errors(body)}")
        data = body.get("data")
        if data is None:
            raise ProviderReadError(f"upstox GET {path}: envelope carried no data")
        if not isinstance(data, dict):
            raise ProviderReadError(
                f"upstox GET {path}: expected data object, got {type(data).__name__}")
        return UpstoxResponse(endpoint=path, data=data)

    def close(self) -> None:
        try:
            self._client.close()
        except Exception:                          # noqa: BLE001 — closing must never raise
            pass


def _error_detail(resp) -> str:
    """Upstox's own error code when it sent one — `UDAPI1020` distinguishes "you asked for an
    interval we do not serve" from "we are down", and the caller must not retry the first."""
    try:
        body = resp.json()
    except Exception:                              # noqa: BLE001
        return "<unparseable body>"
    return _envelope_errors(body) if isinstance(body, dict) else "<unexpected body>"


def _envelope_errors(body: dict) -> str:
    errors = body.get("errors")
    if isinstance(errors, list) and errors:
        parts = []
        for err in errors:
            if isinstance(err, dict):
                parts.append(f"{err.get('errorCode', '?')}: {err.get('message', '')}".strip())
        if parts:
            return " · ".join(parts)
    return "<no error detail>"
