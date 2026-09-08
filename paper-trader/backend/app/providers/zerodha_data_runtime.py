"""Closed Zerodha DATA transport and offline-verifiable runtime policy.

The wire object is private to one call. Credentials are late-read from the
owner-scoped vault. This module has no process credential or token-file path.
"""
from __future__ import annotations

import hashlib
import datetime as dt
import hmac
import json
import math
import re
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Mapping

from kiteconnect import KiteConnect
from kiteconnect.exceptions import TokenException


QUOTE_MIN_INTERVAL_SECONDS = 1.0
HISTORICAL_MIN_INTERVAL_SECONDS = 1 / 3
MAX_EVIDENCE_BYTES = 1_000_000
MAX_EVIDENCE_DEPTH = 8
MAX_EVIDENCE_KEYS = 512
MAX_EVIDENCE_ROWS = 500
MAX_EVIDENCE_SHAPE_ENTRIES = 400
RATE_COORDINATION_SCOPE = "SINGLE_PROCESS_PER_OWNER_CONNECTION"
MULTIPROCESS_RATE_COORDINATION = "UNAVAILABLE"
# Request windows, not total historical retention. Daily chunks leave headroom
# below Kite's documented 2000-day request bound (sandbox guidance uses 1900).
HISTORICAL_REQUEST_DAYS = {"minute": 60, "3minute": 100, "5minute": 100,
    "10minute": 100, "15minute": 200, "30minute": 200, "60minute": 400, "day": 1900}
MAX_HISTORY_REQUESTS = 64
MAX_HISTORY_CANDLES = 100_000
MAX_HISTORY_RESPONSE_BYTES = 4 * 1024 * 1024
MAX_INSTRUMENT_RESPONSE_BYTES = 32 * 1024 * 1024


class DataRouteBlocked(RuntimeError):
    """The dedicated DATA transport refused a route before network access."""


class ZerodhaDataUnavailable(RuntimeError):
    """The owner-scoped data operation has no safe result."""


class ZerodhaReauthRequired(ZerodhaDataUnavailable):
    """The failed token was invalidated and a new provider login is required."""


class ZerodhaTransientError(ZerodhaDataUnavailable):
    """A bounded transient failure occurred without invalidating credentials."""


class EvidenceRefused(ValueError):
    """A response cannot be reduced to the durable, privacy-safe evidence shape."""


def _history_time(value):
    if type(value) is str:
        try:
            value = dt.datetime.fromisoformat(value)
        except ValueError:
            raise ZerodhaDataUnavailable("Historical dates must use ISO format") from None
    if type(value) is dt.date:
        value = dt.datetime.combine(value, dt.time())
    if type(value) is not dt.datetime or value.microsecond:
        raise ZerodhaDataUnavailable("Historical dates must have whole-second precision")
    # Kite formats datetime arguments without their offset; normalize aware
    # values to exchange time before that formatting can discard the timezone.
    return value.astimezone(dt.timezone(dt.timedelta(hours=5, minutes=30))) if value.utcoffset() is not None else value


def _history_windows(from_date, to_date, interval):
    if interval not in HISTORICAL_REQUEST_DAYS:
        raise ZerodhaDataUnavailable("Historical candle interval is unsupported")
    start, end = _history_time(from_date), _history_time(to_date)
    if (start.utcoffset() is None) != (end.utcoffset() is None):
        raise ZerodhaDataUnavailable("Historical date timezones must agree")
    span = dt.timedelta(days=HISTORICAL_REQUEST_DAYS[interval])
    if end < start or end - start >= span * MAX_HISTORY_REQUESTS:
        raise ZerodhaDataUnavailable("Historical range exceeds the request budget; choose a shorter range")
    windows = []
    while start <= end:
        last = min(start + span - dt.timedelta(seconds=1), end)
        windows.append((start, last))
        start = last + dt.timedelta(seconds=1)
    return windows


class TypedUnavailable(str, Enum):
    CURRENT_OPTION_CHAIN = "CURRENT_OPTION_CHAIN_UNPROVEN"
    HISTORICAL_OPTIONS_DEPTH = "HISTORICAL_OPTIONS_DEPTH_UNPROVEN"
    EXPIRED_OPTION_TOKEN_RECOVERY = "EXPIRED_OPTION_TOKEN_RECOVERY_UNPROVEN"
    OPTIONS_ORDER_FLOW = "OPTIONS_ORDER_FLOW_UNPROVEN"
    OPTIONS_BACKTESTS = "OPTIONS_BACKTESTS_UNPROVEN"
    FUTURES_LTP = "CURRENT_FUTURES_LTP_UNPROVEN"
    PROVIDER_SUBSTITUTION = "AUTOMATIC_PROVIDER_SUBSTITUTION_FORBIDDEN"


# Route plus method is the authority. Authentication permits only the one-time
# session exchange. Token renewal/invalidation and every account route stay shut.
DATA_ROUTE_METHODS = frozenset({
    ("api.token", "POST"),
    ("market.instruments", "GET"),
    ("market.instruments.all", "GET"),
    ("market.quote", "GET"),
    ("market.quote.ohlc", "GET"),
    ("market.quote.ltp", "GET"),
    ("market.historical", "GET"),
})


class ZerodhaDataKite(KiteConnect):
    """Kite SDK transport with no account, portfolio, order or unknown route."""

    def _request(self, route, method, url_args=None, params=None,
                 is_json=False, query_params=None):
        key = (str(route), str(method).upper())
        if key not in DATA_ROUTE_METHODS:
            raise DataRouteBlocked(
                "Zerodha DATA transport refused a non-data route before network access"
            )
        return KiteConnect._request(
            self, route, method, url_args=url_args, params=params,
            is_json=is_json, query_params=query_params,
        )

    def historical_data(self, instrument_token, from_date, to_date, interval,
                        continuous=False, oi=False, *, capture_response=None):
        """Optionally retain the actual successful response before SDK projection."""
        if capture_response is None:
            return super().historical_data(instrument_token, from_date, to_date,
                interval, continuous=continuous, oi=oi)
        with self._response_capture(MAX_HISTORY_RESPONSE_BYTES, "Historical") as captured:
            rows = super().historical_data(instrument_token, from_date, to_date,
                interval, continuous=continuous, oi=oi)
            body, received_at = _successful_capture(captured, "Historical")
            capture_response(body, received_at, from_date, to_date, interval)
            return rows

    def instruments(self, exchange=None, *, capture_response=None):
        """Retain exact current-reference bytes and UTC receipt when requested."""
        if capture_response is None:
            return super().instruments(exchange)
        with self._response_capture(MAX_INSTRUMENT_RESPONSE_BYTES, "Instrument") as captured:
            rows = super().instruments(exchange)
            body, received_at = _successful_capture(captured, "Instrument")
            capture_response(body, received_at, exchange)
            return rows

    @contextmanager
    def _response_capture(self, max_bytes, label):
        captured = []
        def observe(response, **_kwargs):
            body = response.content
            if not 0 < len(body) <= max_bytes:
                raise ZerodhaDataUnavailable(f"{label} response exceeds the capture size limit")
            captured.append((body, dt.datetime.now(dt.timezone.utc), response.status_code))
        hooks = self.reqsession.hooks.setdefault("response", [])
        hooks.append(observe)
        try:
            yield captured
        finally:
            hooks.remove(observe)


def _successful_capture(captured, label):
    if len(captured) != 1 or captured[0][2] != 200:
        raise ZerodhaDataUnavailable(f"{label} response capture is ambiguous")
    body, received_at, _status = captured[0]
    return body, received_at


@dataclass(frozen=True)
class RuntimePolicy:
    """Bounded retry policy. Unknown provider limits remain outside this claim."""

    max_attempts: int = 3
    backoff_base_seconds: float = 0.25
    backoff_max_seconds: float = 1.0

    def __post_init__(self) -> None:
        if (type(self.max_attempts) is not int or not 1 <= self.max_attempts <= 3
                or isinstance(self.backoff_base_seconds, bool)
                or not 0 <= self.backoff_base_seconds <= 1
                or isinstance(self.backoff_max_seconds, bool)
                or not self.backoff_base_seconds <= self.backoff_max_seconds <= 2):
            raise ValueError("Zerodha DATA runtime policy is outside its safe bounds")


class _RateGate:
    def __init__(self, monotonic: Callable[[], float], sleep: Callable[[float], None]) -> None:
        self._monotonic = monotonic
        self._sleep = sleep
        self._lock = threading.Lock()
        self._last: dict[str, float] = {}

    def wait(self, category: str) -> None:
        interval = {
            "quote": QUOTE_MIN_INTERVAL_SECONDS,
            "historical": HISTORICAL_MIN_INTERVAL_SECONDS,
        }.get(category)
        if interval is None:
            return
        with self._lock:
            now = self._monotonic()
            if category in self._last:
                delay = interval - (now - self._last[category])
                if delay > 0:
                    self._sleep(delay)
            self._last[category] = self._monotonic()


_SHARED_RATE_GATES: dict[str, _RateGate] = {}
_SHARED_RATE_GATES_LOCK = threading.Lock()
_MAX_SHARED_RATE_SCOPES = 4096


def _rate_gate(scope: str | None, monotonic: Callable[[], float],
               sleep: Callable[[float], None]) -> _RateGate:
    if scope is None:
        return _RateGate(monotonic, sleep)
    if not isinstance(scope, str) or not scope or len(scope) > 128:
        raise ZerodhaDataUnavailable("data rate scope is unavailable")
    digest = hashlib.sha256(scope.encode("utf-8")).hexdigest()
    with _SHARED_RATE_GATES_LOCK:
        gate = _SHARED_RATE_GATES.get(digest)
        if gate is not None:
            return gate
        if len(_SHARED_RATE_GATES) >= _MAX_SHARED_RATE_SCOPES:
            raise ZerodhaDataUnavailable("data rate capacity is unavailable")
        gate = _RateGate(monotonic, sleep)
        _SHARED_RATE_GATES[digest] = gate
        return gate


def _status_code(exc: Exception) -> int | None:
    for candidate in (
        getattr(exc, "status_code", None),
        getattr(exc, "code", None),
        getattr(getattr(exc, "response", None), "status_code", None),
    ):
        if type(candidate) is int:
            return candidate
    return None


def _is_auth_failure(exc: Exception) -> bool:
    return isinstance(exc, TokenException) or _status_code(exc) == 403


def _is_transient_failure(exc: Exception) -> bool:
    status = _status_code(exc)
    return (status in {429, 502, 503, 504}
            or isinstance(exc, TimeoutError)
            or "timeout" in type(exc).__name__.lower())


def failed_token_is_current(current_token: object, failed_token: object) -> bool:
    """Fence delayed expiry handling from a newer callback or rotation."""
    return (isinstance(current_token, str) and isinstance(failed_token, str)
            and bool(current_token) and bool(failed_token)
            and hmac.compare_digest(current_token, failed_token))


class ZerodhaDataRuntime:
    """Owner-scoped, data-only calls with typed failure and bounded recovery."""

    __slots__ = (
        "_credential_source", "_invalidate_access_token", "_client_factory",
        "_policy", "_rate_gate", "_sleep",
    )

    def __init__(
        self,
        credential_source: Callable[[], dict],
        invalidate_access_token: Callable[[str], bool],
        *,
        client_factory: Callable[..., object] = ZerodhaDataKite,
        policy: RuntimePolicy = RuntimePolicy(),
        rate_scope: str | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._credential_source = credential_source
        self._invalidate_access_token = invalidate_access_token
        self._client_factory = client_factory
        self._policy = policy
        self._rate_gate = _rate_gate(rate_scope, monotonic, sleep)
        self._sleep = sleep

    def _credentials(self) -> tuple[str, str]:
        bundle = self._credential_source()
        if not isinstance(bundle, dict) or not set(bundle).issubset({
            "api_key", "api_secret", "access_token",
        }):
            raise ZerodhaDataUnavailable("owner data credential is unavailable")
        api_key = bundle.get("api_key")
        access_token = bundle.get("access_token")
        if (not isinstance(api_key, str) or not api_key
                or not isinstance(access_token, str) or not access_token):
            raise ZerodhaDataUnavailable("owner data credential is unavailable")
        return api_key, access_token

    def _call(self, category: str, method: str, *args, _capture_responses=None, **kwargs):
        for attempt in range(self._policy.max_attempts):
            if _capture_responses is not None:
                _capture_responses.clear()
            api_key, access_token = self._credentials()
            self._rate_gate.wait(category)
            client = self._client_factory(api_key=api_key, access_token=access_token)
            try:
                return getattr(client, method)(*args, **kwargs)
            except Exception as exc:  # SDK types are normalized at this boundary.
                if _is_auth_failure(exc):
                    self._invalidate_access_token(access_token)
                    raise ZerodhaReauthRequired(
                        "Zerodha data authentication must be renewed"
                    ) from None
                if not _is_transient_failure(exc):
                    raise ZerodhaDataUnavailable(
                        f"Zerodha data request failed ({type(exc).__name__})"
                    ) from None
                if attempt + 1 == self._policy.max_attempts:
                    raise ZerodhaTransientError(
                        f"Zerodha data request is temporarily unavailable ({type(exc).__name__})"
                    ) from None
                delay = min(
                    self._policy.backoff_base_seconds * (2 ** attempt),
                    self._policy.backoff_max_seconds,
                )
                if delay:
                    self._sleep(delay)

    def instruments(self, exchange: str | None = None, *, capture_response=None):
        if capture_response is None:
            return self._call("instrument", "instruments", exchange)
        captured = []
        rows = self._call("instrument", "instruments", exchange,
            _capture_responses=captured,
            capture_response=lambda *response: captured.append(response))
        if type(rows) is not list or len(captured) != 1:
            raise ZerodhaDataUnavailable("Instrument response capture is unavailable")
        capture_response(*captured[0])
        return rows

    def quote(self, *keys: str):
        return self._call("quote", "quote", *keys)

    def ltp(self, *keys: str):
        return self._call("quote", "ltp", *keys)

    def ohlc(self, *keys: str):
        return self._call("quote", "ohlc", *keys)

    def historical_data(self, instrument_token, from_date, to_date, interval,
                        *, continuous: bool = False, oi: bool = False,
                        capture_response=None):
        """Fetch every chunk before exposing results or raw captures.

        Capture consumers still own their publication transaction: a consumer
        failure cannot roll back side effects from its earlier callbacks.
        """
        result = []
        responses = []
        for start, end in _history_windows(from_date, to_date, interval):
            captured = []
            options = {"continuous": continuous, "oi": oi}
            if capture_response is not None:
                options["capture_response"] = lambda *response: captured.append(response)
            rows = self._call("historical", "historical_data", instrument_token,
                start, end, interval, **options)
            if type(rows) is not list:
                raise ZerodhaDataUnavailable("Historical candle response is unavailable")
            if len(result) + len(rows) > MAX_HISTORY_CANDLES:
                raise ZerodhaDataUnavailable("History exceeds the 100000-candle application limit; choose a shorter range")
            if capture_response is not None:
                if len(captured) != 1:
                    raise ZerodhaDataUnavailable("Historical response capture is unavailable")
                responses.append(captured[0])
            result.extend(rows)
        for response in responses:
            capture_response(*response)
        return result


_EVIDENCE_ENDPOINTS = frozenset({"AUTH", "INSTRUMENT", "QUOTE", "LTP", "OHLC", "HISTORICAL"})
_SENSITIVE_KEYS = frozenset({
    "access_token", "api_key", "api_secret", "authorization", "credential",
    "password", "private_key", "public_token", "refresh_token", "secret",
    "totp", "user_id", "email", "user_name", "user_shortname", "avatar_url",
    "exchanges", "products", "order_types", "broker", "login_time", "meta",
    "enctoken", "silo", "demat_consent", "account", "account_id", "strategy",
    "graph", "alert", "paper_position", "position", "trade", "pnl", "review_note",
})


def _canonical_evidence_key(key: str) -> str:
    """Normalize case, camel case, and separators before sensitive-key checks."""
    separated = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", key.strip())
    separated = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", separated)
    return re.sub(r"[^A-Za-z0-9]+", "_", separated).strip("_").casefold()


def _reject_sensitive_evidence_key(key: str) -> None:
    if _canonical_evidence_key(key) in _SENSITIVE_KEYS:
        raise EvidenceRefused("sensitive response field refused before evidence capture")


def _preflight_evidence(payload: object) -> None:
    stack: list[tuple[object, int]] = [(payload, 0)]
    keys = rows = shape_entries = 0
    while stack:
        value, depth = stack.pop()
        if depth > MAX_EVIDENCE_DEPTH:
            raise EvidenceRefused("evidence response nesting bound exceeded")
        shape_entries += 1
        if shape_entries > MAX_EVIDENCE_SHAPE_ENTRIES:
            raise EvidenceRefused("evidence response shape bound exceeded")
        if isinstance(value, Mapping):
            keys += len(value)
            if keys > MAX_EVIDENCE_KEYS:
                raise EvidenceRefused("evidence response key bound exceeded")
            for key, item in value.items():
                if not isinstance(key, str):
                    raise EvidenceRefused("evidence response keys must be strings")
                _reject_sensitive_evidence_key(key)
                stack.append((item, depth + 1))
        elif isinstance(value, (tuple, list)):
            rows += len(value)
            if rows > MAX_EVIDENCE_ROWS:
                raise EvidenceRefused("evidence response row bound exceeded")
            stack.extend((item, depth + 1) for item in value)
        elif type(value) is float:
            if not math.isfinite(value):
                raise EvidenceRefused("evidence response contains a non-finite number")
        elif value is None or type(value) in {bool, int}:
            continue
        elif isinstance(value, str):
            if len(value.encode("utf-8")) > MAX_EVIDENCE_BYTES:
                raise EvidenceRefused("evidence response byte bound exceeded")
        else:
            raise EvidenceRefused("evidence response contains an unsupported type")


def _closed_shape(value: object, path: str = "$") -> tuple[str, ...]:
    if isinstance(value, Mapping):
        rows: list[str] = []
        for key in sorted(value, key=str):
            if not isinstance(key, str):
                raise EvidenceRefused("evidence response keys must be strings")
            _reject_sensitive_evidence_key(key)
            rows.extend(_closed_shape(value[key], f"{path}.{key}"))
        return tuple(rows or (f"{path}:object",))
    if isinstance(value, (tuple, list)):
        rows = [f"{path}:array"]
        for item in value:
            rows.extend(_closed_shape(item, f"{path}[]"))
        return tuple(dict.fromkeys(rows))
    if value is None:
        kind = "null"
    elif type(value) is bool:
        kind = "boolean"
    elif type(value) in {int, float}:
        kind = "number"
    elif isinstance(value, str):
        kind = "string"
    else:
        raise EvidenceRefused("evidence response contains an unsupported type")
    return (f"{path}:{kind}",)


def _row_count(payload: object) -> int:
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, Mapping):
        data = payload.get("data")
        if isinstance(data, (list, Mapping)):
            return len(data)
        return len(payload)
    return 1


def summarize_response(
        endpoint_class: str, payload: object, *, elapsed_seconds: float,
        http_status: int = 200) -> dict:
    """Return the only durable response-evidence shape allowed by this slice."""
    if endpoint_class not in _EVIDENCE_ENDPOINTS:
        raise EvidenceRefused("unknown endpoint class")
    if (isinstance(elapsed_seconds, bool) or not isinstance(elapsed_seconds, (int, float))
            or not math.isfinite(float(elapsed_seconds)) or elapsed_seconds < 0
            or type(http_status) is not int
            or not 100 <= http_status <= 599):
        raise EvidenceRefused("evidence timing or HTTP class is invalid")
    _preflight_evidence(payload)
    shape = _closed_shape(payload)
    try:
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise EvidenceRefused("response is not safely addressable") from exc
    if len(raw) > MAX_EVIDENCE_BYTES:
        raise EvidenceRefused("evidence response byte bound exceeded")
    return {
        "schema": "strategy-os-zerodha-private-response-summary/1",
        "endpoint_class": endpoint_class,
        "http_class": f"{http_status // 100}XX",
        "elapsed_milliseconds": round(float(elapsed_seconds) * 1000, 3),
        "byte_count": len(raw),
        "row_count": _row_count(payload),
        "closed_shape": shape,
        "content_address": f"sha256:{hashlib.sha256(raw).hexdigest()}",
    }


__all__ = [
    "DATA_ROUTE_METHODS", "HISTORICAL_MIN_INTERVAL_SECONDS",
    "MAX_EVIDENCE_BYTES", "MAX_EVIDENCE_DEPTH", "MAX_EVIDENCE_KEYS",
    "MAX_EVIDENCE_ROWS", "MAX_EVIDENCE_SHAPE_ENTRIES",
    "MULTIPROCESS_RATE_COORDINATION", "QUOTE_MIN_INTERVAL_SECONDS",
    "RATE_COORDINATION_SCOPE", "DataRouteBlocked", "EvidenceRefused",
    "RuntimePolicy", "TypedUnavailable", "ZerodhaDataKite",
    "ZerodhaDataRuntime", "ZerodhaDataUnavailable", "ZerodhaReauthRequired",
    "ZerodhaTransientError", "failed_token_is_current", "summarize_response",
]
