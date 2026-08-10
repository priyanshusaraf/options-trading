"""The HTTP edge of a Dhan connection. Nothing above this file speaks HTTP.

Same split as `upstox_transport.py`, for the same reason: the adapter's *semantics* — the
columnar candle layout, the interval refusal, the non-inclusive end date — must be testable
without a network, and the transport must be replaceable by a fixture returning real recorded
payloads.

Read from https://dhanhq.co/docs/v2/ on 2026-08-10. Four facts from that reading shape this file
and none of them is a guess:

  * **Base URL is `https://api.dhan.co/v2`** and every data call is a **POST**, including the
    reads. A GET-shaped transport would be wrong for every endpoint.
  * **Two credentials, not one.** `access-token` carries the JWT and `client-id` carries the
    account. Kite and Upstox need one header; Dhan needs both, and omitting the second fails in
    a way that reads like an auth problem with the token.
  * **Rate limit is 1 request per second** on the market-quote endpoints, documented. It is
    enforced here rather than hoped for, because a 429 mid-scan is a lane that returns nothing.
  * **Errors arrive inside a 200 envelope** as well as by status code, the same shape Upstox
    uses, so the check cannot be `status_code == 200` alone.

The token appears in no log line and no exception message built here.
"""
from __future__ import annotations

import dataclasses
import threading
import time
from typing import Any

import httpx

from app.providers.base import ProviderReadError

BASE_URL = "https://api.dhan.co/v2"

CONNECT_TIMEOUT = 5.0
READ_TIMEOUT = 10.0

#: Documented as 1 request/second. Kept slightly above the boundary because the limit is applied
#: at the server's clock, not ours, and a burst that is exactly at the limit is the one that gets
#: rejected.
MIN_REQUEST_INTERVAL = 1.05


@dataclasses.dataclass(frozen=True)
class DhanResponse:
    """A successful, parsed Dhan payload. `data` is whatever the endpoint returned."""

    endpoint: str
    data: dict


class _Throttle:
    """One request per second, process-wide per transport.

    A lock rather than a bare timestamp: the engine's scan lane and the risk loop can both reach
    a provider, and two threads reading a stale timestamp is exactly how a documented limit gets
    breached by a factor of two.
    """

    def __init__(self, min_interval: float = MIN_REQUEST_INTERVAL) -> None:
        self._min = min_interval
        self._lock = threading.Lock()
        self._last = 0.0

    def wait(self) -> None:
        with self._lock:
            gap = time.monotonic() - self._last
            if gap < self._min:
                time.sleep(self._min - gap)
            self._last = time.monotonic()


class DhanTransport:
    """Signed, timed, throttled HTTP against the DhanHQ v2 API.

    `token_source` and `client_id_source` are callables rather than strings so a
    re-authenticated connection is picked up without rebuilding the transport — the same shape
    `KiteOrderClient` uses to stay in lock-step with a refreshed token.
    """

    def __init__(self, token_source, client_id_source, *, base_url: str = BASE_URL,
                 client=None, throttle=None) -> None:
        self._token_source = token_source
        self._client_id_source = client_id_source
        self._base_url = base_url.rstrip("/")
        self._throttle = throttle if throttle is not None else _Throttle()
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(READ_TIMEOUT, connect=CONNECT_TIMEOUT))

    def _headers(self) -> dict[str, str]:
        token = self._token_source() if callable(self._token_source) else self._token_source
        cid = (self._client_id_source() if callable(self._client_id_source)
               else self._client_id_source)
        if not token:
            raise ProviderReadError("dhan: no access token on this connection")
        if not cid:
            # Named separately from the token because the failure looks identical from the
            # outside and the fix is different — this one is a configuration gap, not an expiry.
            raise ProviderReadError("dhan: no client id on this connection")
        return {"access-token": str(token), "client-id": str(cid),
                "Content-Type": "application/json", "Accept": "application/json"}

    def _send(self, method: str, path: str, body: dict[str, Any] | None,
              *, allow_list: bool) -> DhanResponse:
        """One request, one place. `allow_list` is the only thing that differs between the
        market-data reads (always an object) and the order endpoints (`GET /orders` is a JSON
        array). Keeping the difference to a flag is what stops the two growing separate error
        handling — which is how one of them ends up treating an HTTP 500 as no data.
        """
        # Credentials FIRST, before the throttle and before the client is touched. Building them
        # inside the request call let a missing client-id surface as "transport failed:
        # AttributeError", which sends the operator to look at the network for a configuration
        # gap. It also made us sleep out the rate limit before discovering we could not have
        # sent anything.
        headers = self._headers()
        self._throttle.wait()
        url = f"{self._base_url}{path}"
        try:
            resp = self._client.request(method, url, headers=headers,
                                        **({"json": body} if body is not None else {}))
        except ProviderReadError:
            raise
        except Exception as e:                    # noqa: BLE001 — timeouts, DNS, TLS, refused
            raise ProviderReadError(
                f"dhan {method} {path}: transport failed: {type(e).__name__}: {e}") from e

        if resp.status_code != 200:
            raise ProviderReadError(
                f"dhan {method} {path}: HTTP {resp.status_code}: {_error_detail(resp)}")
        try:
            body_json = resp.json()
        except Exception as e:                    # noqa: BLE001 — a 200 that is not JSON
            raise ProviderReadError(f"dhan {method} {path}: malformed response body") from e

        if isinstance(body_json, list):
            if not allow_list:
                raise ProviderReadError(
                    f"dhan {method} {path}: expected a JSON object, got a list")
            # A bare array carries no envelope, so there is no status to check and no `data`
            # key to unwrap. Returned as-is; the caller knows the shape it asked for.
            return DhanResponse(endpoint=path, data=body_json)
        if not isinstance(body_json, dict):
            raise ProviderReadError(
                f"dhan {method} {path}: expected a JSON object, got {type(body_json).__name__}")
        status = body_json.get("status")
        if status is not None and str(status).lower() not in ("success", "ok"):
            raise ProviderReadError(f"dhan {method} {path}: {status}: {_errors(body_json)}")
        # The charts endpoints return the OHLC arrays at the TOP level; marketfeed nests them
        # under "data". Both are legitimate, so an absent "data" key is not an error here.
        data = body_json.get("data", body_json)
        if isinstance(data, list):
            if not allow_list:
                raise ProviderReadError(
                    f"dhan {method} {path}: expected a data object, got a list")
            return DhanResponse(endpoint=path, data=data)
        if not isinstance(data, dict):
            raise ProviderReadError(
                f"dhan {method} {path}: expected a data object, got {type(data).__name__}")
        return DhanResponse(endpoint=path, data=data)

    def post(self, path: str, body: dict[str, Any], *,
             allow_list: bool = False) -> DhanResponse:
        """POST `path`, or raise `ProviderReadError` with the context that failed.

        `allow_list` defaults to **False**, which is the market-data contract: `_columns_to_candles`
        and `get_ltp` index `data` as a mapping, so a list must fail here with a message naming
        the shape rather than three frames later as an `AttributeError` on `.get`. The order
        endpoints pass `True` — Dhan answers some of them with a single-element array.
        """
        return self._send("POST", path, body, allow_list=allow_list)

    def get(self, path: str) -> DhanResponse:
        """`GET /orders` returns a JSON ARRAY; `GET /fundlimit` returns an object. Both are
        documented and both are legitimate, which is why the list case is permitted here and
        refused nowhere else."""
        return self._send("GET", path, None, allow_list=True)

    def put(self, path: str, body: dict[str, Any]) -> DhanResponse:
        """Modify. Dhan uses PUT where Kite POSTs to an action path — assuming Kite's shape here
        returns 404 or 405, and a failed protective-stop modify leaves the exchange stop stale
        at the old trigger while the internal one ratchets (the 2026-07-13 SUZLON class)."""
        return self._send("PUT", path, body, allow_list=True)

    def delete(self, path: str) -> DhanResponse:
        """Cancel. Raises if Dhan refused — a refused cancel means the old order may still fire,
        so the caller must NOT then place a second one or mark the position closed."""
        return self._send("DELETE", path, None, allow_list=True)

    def close(self) -> None:
        try:
            self._client.close()
        except Exception:                          # noqa: BLE001 — closing must never raise
            pass


def _error_detail(resp) -> str:
    try:
        body = resp.json()
    except Exception:                              # noqa: BLE001
        return "<unparseable body>"
    return _errors(body) if isinstance(body, dict) else "<unexpected body>"


def _errors(body: dict) -> str:
    """Dhan's own error code where it sent one. `errorType`/`errorCode`/`errorMessage` are the
    documented fields; the fallbacks exist because an error envelope is the payload least likely
    to match its own documentation."""
    for key in ("errorMessage", "message", "remarks"):
        value = body.get(key)
        if isinstance(value, str) and value:
            code = body.get("errorCode") or body.get("errorType")
            return f"{code}: {value}" if code else value
    return "<no error detail>"
