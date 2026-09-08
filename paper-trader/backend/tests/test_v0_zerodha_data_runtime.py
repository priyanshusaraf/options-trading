"""Offline checks for the closed Zerodha DATA authentication and runtime boundary."""
from __future__ import annotations

import datetime as dt
import inspect
import json
from urllib.parse import parse_qs, urlsplit

import pytest
from kiteconnect.exceptions import DataException, TokenException

from app.providers.broker_auth import KiteAuthenticator
from app.providers.zerodha_data_runtime import (
    HISTORICAL_MIN_INTERVAL_SECONDS,
    MULTIPROCESS_RATE_COORDINATION,
    QUOTE_MIN_INTERVAL_SECONDS,
    RATE_COORDINATION_SCOPE,
    DataRouteBlocked,
    EvidenceRefused,
    RuntimePolicy,
    TypedUnavailable,
    ZerodhaDataKite,
    ZerodhaDataRuntime,
    ZerodhaReauthRequired,
    ZerodhaTransientError,
    failed_token_is_current,
    summarize_response,
)


class _Clock:
    def __init__(self) -> None:
        self.value = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.value += seconds


class _Wire:
    def __init__(self, api_key: str, access_token: str | None = None) -> None:
        self.api_key = api_key
        self.access_token = access_token
        self.calls: list[tuple] = []
        self.failures: list[Exception] = []

    def set_access_token(self, token: str) -> None:
        self.access_token = token

    def ltp(self, *keys):
        self.calls.append(("ltp", keys, self.access_token))
        if self.failures:
            raise self.failures.pop(0)
        return {key: {"instrument_token": 1, "last_price": 100.0} for key in keys}

    def quote(self, *keys):
        self.calls.append(("quote", keys, self.access_token))
        return {key: {"instrument_token": 1, "last_price": 100.0} for key in keys}

    def ohlc(self, *keys):
        self.calls.append(("ohlc", keys, self.access_token))
        return {key: {"instrument_token": 1, "last_price": 100.0} for key in keys}

    def historical_data(self, *args, **kwargs):
        self.calls.append(("historical", args, kwargs, self.access_token))
        return [{"date": dt.datetime(2026, 9, 4, 9, 15), "close": 100.0}]

    def instruments(self, exchange=None):
        self.calls.append(("instruments", exchange, self.access_token))
        return [{"instrument_token": 1, "tradingsymbol": "INFY"}]


def test_production_authenticator_constructs_the_closed_data_transport_without_network(monkeypatch):
    touched = []
    monkeypatch.setattr(
        ZerodhaDataKite,
        "_request",
        lambda *_args, **_kwargs: touched.append(True),
    )
    authenticator = KiteAuthenticator()
    client = authenticator._client("owner-app-key")
    assert isinstance(client, ZerodhaDataKite)
    assert client.login_url().startswith(
        "https://kite.zerodha.com/connect/login?api_key=owner-app-key"
    )
    assert touched == []


def test_zerodha_callback_state_uses_url_encoded_redirect_params():
    from app.providers.data_connection_service import _with_state

    login_url = _with_state(
        "https://kite.zerodha.com/connect/login?api_key=synthetic&v=3",
        "synthetic-state",
        zerodha_redirect_params=True,
    )
    query = parse_qs(urlsplit(login_url).query)
    assert "state" not in query
    assert parse_qs(query["redirect_params"][0]) == {"state": ["synthetic-state"]}


@pytest.mark.parametrize(("route", "method"), [
    ("user.profile", "GET"),
    ("user.margins", "GET"),
    ("portfolio.positions", "GET"),
    ("portfolio.holdings", "GET"),
    ("orders", "GET"),
    ("trades", "GET"),
    ("gtt", "GET"),
    ("order.place", "POST"),
    ("market.margins", "GET"),
    ("market.unknown", "GET"),
])
def test_closed_transport_denies_account_portfolio_order_and_unknown_before_network(
        monkeypatch, route, method):
    touched = []
    monkeypatch.setattr(
        "kiteconnect.KiteConnect._request",
        lambda *_args, **_kwargs: touched.append(True),
    )
    client = ZerodhaDataKite(api_key="synthetic")
    with pytest.raises(DataRouteBlocked):
        client._request(route, method)
    assert touched == []


@pytest.mark.parametrize(("route", "method"), [
    ("api.token", "GET"),
    ("market.quote", "POST"),
    ("market.historical", "DELETE"),
])
def test_closed_transport_rejects_the_wrong_method_before_network(monkeypatch, route, method):
    touched = []
    monkeypatch.setattr(
        "kiteconnect.KiteConnect._request",
        lambda *_args, **_kwargs: touched.append(True),
    )
    client = ZerodhaDataKite(api_key="synthetic")
    with pytest.raises(DataRouteBlocked):
        client._request(route, method)
    assert touched == []


def test_runtime_late_reads_each_owner_token_and_never_uses_process_fallback():
    bundles = iter([
        {"api_key": "owner-key", "access_token": "token-one"},
        {"api_key": "owner-key", "access_token": "token-two"},
    ])
    wires: list[_Wire] = []

    def factory(api_key: str, access_token: str | None = None):
        wire = _Wire(api_key, access_token)
        wires.append(wire)
        return wire

    runtime = ZerodhaDataRuntime(lambda: next(bundles), lambda _token: False,
                                 client_factory=factory)
    runtime.ltp("NSE:INFY")
    runtime.ltp("NSE:INFY")
    assert [wire.calls[0][2] for wire in wires] == ["token-one", "token-two"]
    source = inspect.getsource(type(runtime))
    for forbidden in ("TOKEN_FILE", "access_token.json", "get_settings", "os.environ"):
        assert forbidden not in source


def test_quote_and_historical_limits_are_minimums_and_are_enforced():
    assert QUOTE_MIN_INTERVAL_SECONDS >= 1.0
    assert HISTORICAL_MIN_INTERVAL_SECONDS >= 1 / 3
    clock = _Clock()
    wire = _Wire("owner-key", "token")
    runtime = ZerodhaDataRuntime(
        lambda: {"api_key": "owner-key", "access_token": "token"},
        lambda _token: False,
        client_factory=lambda *_args, **_kwargs: wire,
        policy=RuntimePolicy(max_attempts=1),
        monotonic=clock.monotonic,
        sleep=clock.sleep,
    )
    runtime.ltp("NSE:INFY")
    runtime.ltp("NSE:INFY")
    runtime.historical_data(1, "2026-09-01", "2026-09-02", "minute")
    runtime.historical_data(1, "2026-09-01", "2026-09-02", "minute")
    assert clock.sleeps == pytest.approx([
        QUOTE_MIN_INTERVAL_SECONDS,
        HISTORICAL_MIN_INTERVAL_SECONDS,
    ])


def test_reconstructing_the_same_owner_runtime_cannot_bypass_the_quote_gate():
    clock = _Clock()
    wire = _Wire("owner-key", "token")
    kwargs = {
        "client_factory": lambda *_args, **_kwargs: wire,
        "policy": RuntimePolicy(max_attempts=1),
        "rate_scope": "synthetic-owner-connection-rate-test",
        "monotonic": clock.monotonic,
        "sleep": clock.sleep,
    }
    first = ZerodhaDataRuntime(
        lambda: {"api_key": "owner-key", "access_token": "token"},
        lambda _token: False, **kwargs,
    )
    second = ZerodhaDataRuntime(
        lambda: {"api_key": "owner-key", "access_token": "token"},
        lambda _token: False, **kwargs,
    )
    first.ltp("NSE:INFY")
    second.ltp("NSE:INFY")
    assert clock.sleeps == pytest.approx([QUOTE_MIN_INTERVAL_SECONDS])


def test_rate_claim_is_single_process_only_and_shared_scope_capacity_fails_closed(monkeypatch):
    import app.providers.zerodha_data_runtime as module

    assert RATE_COORDINATION_SCOPE == "SINGLE_PROCESS_PER_OWNER_CONNECTION"
    assert MULTIPROCESS_RATE_COORDINATION == "UNAVAILABLE"
    monkeypatch.setattr(module, "_SHARED_RATE_GATES", {})
    monkeypatch.setattr(module, "_MAX_SHARED_RATE_SCOPES", 1)
    ZerodhaDataRuntime(
        lambda: {"api_key": "key", "access_token": "token"},
        lambda _token: False, rate_scope="first-owner-connection",
    )
    with pytest.raises(module.ZerodhaDataUnavailable, match="rate capacity"):
        ZerodhaDataRuntime(
            lambda: {"api_key": "key", "access_token": "token"},
            lambda _token: False, rate_scope="second-owner-connection",
        )


@pytest.mark.parametrize("failure", [
    TokenException("synthetic"),
    type("Provider403", (RuntimeError,), {"status_code": 403})("synthetic"),
])
def test_auth_failure_invalidates_only_the_failed_token_and_requests_reauthentication(failure):
    wire = _Wire("owner-key", "failed-token")
    wire.failures.append(failure)
    invalidated = []
    runtime = ZerodhaDataRuntime(
        lambda: {"api_key": "owner-key", "access_token": "failed-token"},
        lambda token: invalidated.append(token) or True,
        client_factory=lambda *_args, **_kwargs: wire,
    )
    with pytest.raises(ZerodhaReauthRequired):
        runtime.ltp("NSE:INFY")
    assert invalidated == ["failed-token"]


def test_concurrent_token_fence_accepts_only_the_exact_failed_token():
    assert failed_token_is_current("failed-token", "failed-token") is True
    assert failed_token_is_current("newer-token", "failed-token") is False
    assert failed_token_is_current("", "") is False


@pytest.mark.parametrize("status_code", [429, 502, 503, 504])
def test_transient_provider_failures_retry_with_a_bound_and_preserve_token(status_code):
    class ProviderFailure(RuntimeError):
        pass

    failure = ProviderFailure("synthetic provider failure")
    failure.status_code = status_code
    wire = _Wire("owner-key", "valid-token")
    wire.failures = [failure, failure, failure]
    invalidated = []
    clock = _Clock()
    runtime = ZerodhaDataRuntime(
        lambda: {"api_key": "owner-key", "access_token": "valid-token"},
        lambda token: invalidated.append(token) or True,
        client_factory=lambda *_args, **_kwargs: wire,
        policy=RuntimePolicy(max_attempts=2, backoff_base_seconds=0.25,
                             backoff_max_seconds=0.25),
        monotonic=clock.monotonic,
        sleep=clock.sleep,
    )
    with pytest.raises(ZerodhaTransientError):
        runtime.ltp("NSE:INFY")
    assert len(wire.calls) == 2
    assert invalidated == []
    assert 0.25 in clock.sleeps


def test_evidence_summary_is_closed_and_refuses_sensitive_fields_before_digesting():
    summary = summarize_response(
        "LTP",
        {"data": {"NSE:INFY": {"instrument_token": 408065, "last_price": 100.0}}},
        elapsed_seconds=0.125,
    )
    assert set(summary) == {
        "schema", "endpoint_class", "http_class", "elapsed_milliseconds",
        "byte_count", "row_count", "closed_shape", "content_address",
    }
    assert "100.0" not in repr(summary) and "408065" not in repr(summary)
    with pytest.raises(EvidenceRefused, match="sensitive"):
        summarize_response("LTP", {"access_token": "must-not-survive"},
                           elapsed_seconds=0.1)


@pytest.mark.parametrize("field", [
    "access_token", "api_key", "api_secret", "public_token", "refresh_token",
    "email", "user_id", "user_name", "user_shortname", "avatar_url",
    "exchanges", "products", "order_types", "broker", "login_time", "meta",
    "enctoken", "silo", "demat_consent", "account_id", "strategy", "graph",
    "alert", "paper_position", "position", "trade", "pnl", "review-note",
    "accessToken", "apiSecret", "userId", "accountId", "reviewNote",
    "access token", "api.secret", "user/id", "account:id", "review note",
])
def test_evidence_summary_refuses_every_secret_account_and_product_field(field):
    with pytest.raises(EvidenceRefused, match="sensitive"):
        summarize_response("AUTH", {"data": {field: "synthetic"}},
                           elapsed_seconds=0.01)


@pytest.mark.parametrize("payload,match", [
    ({"data": [0] * 501}, "row bound"),
    ({"data": {str(index): index for index in range(513)}}, "key bound"),
    ({"data": "x" * 1_000_001}, "byte bound"),
])
def test_evidence_summary_refuses_resource_bounds_before_hashing(payload, match):
    with pytest.raises(EvidenceRefused, match=match):
        summarize_response("QUOTE", payload, elapsed_seconds=0.01)


def test_evidence_summary_refuses_excessive_nesting_and_shape():
    nested: object = 1
    for _ in range(9):
        nested = {"data": nested}
    with pytest.raises(EvidenceRefused, match="nesting bound"):
        summarize_response("QUOTE", nested, elapsed_seconds=0.01)
    with pytest.raises(EvidenceRefused, match="shape bound"):
        summarize_response("QUOTE", {"data": list(range(401))},
                           elapsed_seconds=0.01)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_evidence_summary_refuses_non_finite_market_numbers(value):
    with pytest.raises(EvidenceRefused, match="non-finite"):
        summarize_response("LTP", {"data": {"last_price": value}},
                           elapsed_seconds=0.01)


@pytest.mark.parametrize("elapsed", [float("nan"), float("inf"), float("-inf")])
def test_evidence_summary_refuses_non_finite_elapsed_timing_before_summary_work(elapsed):
    class MustNotWalk(dict):
        def items(self):
            raise AssertionError("payload walked before timing refusal")

    with pytest.raises(EvidenceRefused, match="timing"):
        summarize_response("LTP", MustNotWalk(data={}), elapsed_seconds=elapsed)


def test_evidence_summary_is_strict_json_serializable():
    summary = summarize_response(
        "LTP", {"data": {"NSE:INFY": {"last_price": 100.0}}},
        elapsed_seconds=0.01,
    )
    encoded = json.dumps(summary, allow_nan=False, sort_keys=True)
    assert json.loads(encoded) == {**summary, "closed_shape": list(summary["closed_shape"])}


def test_v0_unavailable_claims_remain_typed_and_no_provider_substitution_exists():
    assert {item.value for item in TypedUnavailable} == {
        "CURRENT_OPTION_CHAIN_UNPROVEN",
        "HISTORICAL_OPTIONS_DEPTH_UNPROVEN",
        "EXPIRED_OPTION_TOKEN_RECOVERY_UNPROVEN",
        "OPTIONS_ORDER_FLOW_UNPROVEN",
        "OPTIONS_BACKTESTS_UNPROVEN",
        "CURRENT_FUTURES_LTP_UNPROVEN",
        "AUTOMATIC_PROVIDER_SUBSTITUTION_FORBIDDEN",
    }
    source = inspect.getsource(ZerodhaDataRuntime)
    assert "fallback" not in source.lower()


def _history_runtime(wire):
    clock = _Clock()
    return ZerodhaDataRuntime(lambda: {"api_key": "dummy", "access_token": "dummy"},
        lambda _token: False, client_factory=lambda **_kwargs: wire,
        policy=RuntimePolicy(max_attempts=1), monotonic=clock.monotonic, sleep=clock.sleep)


def test_history_chunks_cover_long_daily_range_without_a_retention_cutoff():
    wire = _Wire("dummy")
    start, end = dt.datetime(2010, 1, 1), dt.datetime(2026, 9, 1)
    result = _history_runtime(wire).historical_data(1, start, end, "day")
    calls = [row[1] for row in wire.calls]
    assert len(calls) == 4 and len(result) == 4
    assert calls[0][1] == start and calls[-1][2] == end
    for previous, following in zip(calls, calls[1:]):
        assert following[1] == previous[2] + dt.timedelta(seconds=1)
    assert all(row[2] - row[1] < dt.timedelta(days=1900) for row in calls)


@pytest.mark.parametrize("interval,days", [("minute",60),("3minute",100),("5minute",100),
    ("10minute",100),("15minute",200),("30minute",200),("60minute",400),("day",1900)])
def test_history_interval_request_limits_do_not_truncate_the_requested_end(interval, days):
    wire = _Wire("dummy")
    start = dt.datetime(2020, 1, 1)
    end = start + dt.timedelta(days=days)
    _history_runtime(wire).historical_data(1, start, end, interval, oi=True)
    assert len(wire.calls) == 2
    assert wire.calls[0][1][2] == end - dt.timedelta(seconds=1)
    assert wire.calls[1][1][1:3] == (end, end)
    assert all(row[2] == {"continuous": False, "oi": True} for row in wire.calls)


@pytest.mark.parametrize("start,end,interval", [
    ("2026-09-02", "2026-09-01", "day"), ("not-a-date", "2026-09-01", "day"),
    (True, "2026-09-01", "day"), ("2026-09-01T00:00:00.000001", "2026-09-02", "day"),
    ("2026-09-01T00:00:00+05:30", "2026-09-02", "day"),
    ("2000-01-01", "2026-09-01", "minute"), ("2026-09-01", "2026-09-02", "week"),
])
def test_invalid_history_range_refuses_before_any_provider_call(start, end, interval):
    from app.providers.zerodha_data_runtime import ZerodhaDataUnavailable
    wire = _Wire("dummy")
    with pytest.raises(ZerodhaDataUnavailable):
        _history_runtime(wire).historical_data(1, start, end, interval)
    assert not wire.calls


def test_later_history_chunk_failure_never_returns_partial_success():
    from app.providers.zerodha_data_runtime import ZerodhaDataUnavailable
    wire = _Wire("dummy")
    calls = []
    def historical(*args, **kwargs):
        calls.append(args)
        if len(calls) == 2:
            raise ValueError("private provider details")
        return [{"close": 100}]
    wire.historical_data = historical
    with pytest.raises(ZerodhaDataUnavailable, match="ValueError") as refused:
        _history_runtime(wire).historical_data(1, "2020-01-01", "2020-04-01", "minute")
    assert len(calls) == 2
    assert "private provider details" not in str(refused.value)


def test_history_refuses_unbounded_or_malformed_response(monkeypatch):
    from app.providers import zerodha_data_runtime as module
    wire = _Wire("dummy")
    monkeypatch.setattr(module, "MAX_HISTORY_CANDLES", 1)
    with pytest.raises(module.ZerodhaDataUnavailable, match="application limit"):
        _history_runtime(wire).historical_data(1, "2020-01-01", "2020-04-01", "minute")
    wire.historical_data = lambda *args, **kwargs: {"candles": []}
    with pytest.raises(module.ZerodhaDataUnavailable, match="response"):
        _history_runtime(wire).historical_data(1, dt.date(2020,1,1), dt.date(2020,1,1), "day")


def test_history_normalizes_aware_dates_before_sdk_discards_the_offset():
    wire = _Wire("dummy")
    _history_runtime(wire).historical_data(1, "2026-09-01T00:00:00+00:00", "2026-09-01T01:00:00+00:00", "minute")
    start, end = wire.calls[0][1][1:3]
    assert start.strftime('%Y-%m-%d %H:%M:%S') == '2026-09-01 05:30:00'
    assert end.strftime('%Y-%m-%d %H:%M:%S') == '2026-09-01 06:30:00'
    assert start.utcoffset() == dt.timedelta(hours=5,minutes=30)


def _captured_history_client(monkeypatch, payload, status=200, content_type="application/json"):
    from requests import Response
    from types import SimpleNamespace
    client = ZerodhaDataKite(api_key='dummy', access_token='dummy')
    def send(request, **kwargs):
        response = Response()
        response.status_code = status
        response._content = payload
        response.headers['content-type'] = content_type
        response.request = request
        response.url = request.url
        return response
    monkeypatch.setattr(client.reqsession, 'get_adapter', lambda url: SimpleNamespace(send=send))
    return client


def test_historical_capture_retains_original_wire_bytes_and_request_window(monkeypatch):
    raw = b'{ "status": "success", "data": {"candles": [["2026-09-01T09:15:00+0530",100,102,99,101,10]]}}\n'
    client = _captured_history_client(monkeypatch, raw)
    captures = []
    before = dt.datetime.now(dt.timezone.utc)
    rows = client.historical_data(1, '2026-09-01', '2026-09-02', 'minute', capture_response=lambda *args: captures.append(args))
    assert rows[0]['close'] == 101
    assert len(captures) == 1
    body, received_at, start, end, interval = captures[0]
    assert body == raw and before <= received_at <= dt.datetime.now(dt.timezone.utc)
    assert (start,end,interval) == ('2026-09-01','2026-09-02','minute')
    assert client.reqsession.hooks['response'] == []
    assert client.historical_data(1, '2026-09-01', '2026-09-02', 'minute') == rows


@pytest.mark.parametrize('payload,status,expected', [(b'{"status":"error","error_type":"TokenException","message":"dummy expired"}',403,TokenException), (b'not-json',200,DataException)])
def test_failed_historical_response_never_emits_capture_and_removes_hook(monkeypatch,payload,status,expected):
    client = _captured_history_client(monkeypatch,payload,status)
    existing = lambda response, **kwargs: response
    client.reqsession.hooks['response'].append(existing)
    captures = []
    with pytest.raises(expected):
        client.historical_data(1,'2026-09-01','2026-09-02','minute',capture_response=lambda *args: captures.append(args))
    assert not captures
    assert client.reqsession.hooks['response'] == [existing]


def test_historical_capture_size_failure_cleans_up_without_emitting(monkeypatch):
    from app.providers import zerodha_data_runtime as module
    client = _captured_history_client(monkeypatch,b'{"status":"success","data":{"candles":[]}}')
    monkeypatch.setattr(module,'MAX_HISTORY_RESPONSE_BYTES',8)
    captures=[]
    with pytest.raises(module.ZerodhaDataUnavailable,match='size limit'):
        client.historical_data(1,'2026-09-01','2026-09-02','minute',capture_response=lambda *args: captures.append(args))
    assert captures == [] and client.reqsession.hooks['response'] == []


def test_capture_consumer_failure_is_not_retried_as_a_provider_failure():
    wire=_Wire('dummy'); calls=[]
    def historical(token,start,end,interval,**kwargs):
        calls.append((start,end))
        kwargs['capture_response'](b'dummy',dt.datetime.now(dt.timezone.utc),start,end,interval)
        return []
    wire.historical_data=historical
    clock=_Clock()
    runtime=ZerodhaDataRuntime(lambda:{'api_key':'dummy','access_token':'dummy'},lambda _token:False,
        client_factory=lambda **kwargs:wire,monotonic=clock.monotonic,sleep=clock.sleep)
    def consume(*args):
        raise TimeoutError('local publication timed out')
    with pytest.raises(TimeoutError,match='local publication'):
        runtime.historical_data(1,'2026-09-01','2026-09-02','minute',capture_response=consume)
    assert len(calls)==1


def test_runtime_refuses_a_capture_transport_that_returns_no_source():
    from app.providers.zerodha_data_runtime import ZerodhaDataUnavailable
    wire = _Wire('dummy')
    captures = []
    with pytest.raises(ZerodhaDataUnavailable,match='capture is unavailable'):
        _history_runtime(wire).historical_data(1,'2026-09-01','2026-09-02','minute',capture_response=lambda *args: captures.append(args))
    assert not captures


@pytest.mark.parametrize("failure", ["provider", "missing_capture", "malformed", "row_limit", None])
def test_range_capture_waits_for_every_chunk(monkeypatch, failure):
    from app.providers import zerodha_data_runtime as module
    wire = _Wire("dummy")
    calls, captures = [], []
    received_at = dt.datetime(2026, 9, 1, tzinfo=dt.timezone.utc)

    def historical(token, start, end, interval, **kwargs):
        calls.append((start, end))
        assert captures == []
        if len(calls) == 2 and failure == "provider":
            raise ValueError("dummy failure")
        if len(calls) != 2 or failure != "missing_capture":
            kwargs["capture_response"](str(len(calls)).encode(), received_at, start, end, interval)
        return {} if len(calls) == 2 and failure == "malformed" else [{"close": 100}]

    wire.historical_data = historical
    if failure == "row_limit":
        monkeypatch.setattr(module, "MAX_HISTORY_CANDLES", 1)
    runtime = _history_runtime(wire)
    arguments = (1, "2020-01-01", "2020-04-01", "minute")
    if failure is not None:
        with pytest.raises(module.ZerodhaDataUnavailable):
            runtime.historical_data(*arguments, capture_response=lambda *args: captures.append(args))
        assert captures == []
    else:
        assert len(runtime.historical_data(*arguments, capture_response=lambda *args: captures.append(args))) == 2
        assert [capture[0] for capture in captures] == [b"1", b"2"]
        assert [capture[2:4] for capture in captures] == calls
    assert len(calls) == 2


def test_ambiguous_historical_capture_never_emits_a_source(monkeypatch):
    from app.providers.zerodha_data_runtime import ZerodhaDataUnavailable
    client = _captured_history_client(monkeypatch,b'{"status":"success","data":{"candles":[]}}')
    def repeat(response, **kwargs):
        client.reqsession.hooks['response'][-1](response)
        return response
    client.reqsession.hooks['response'].append(repeat)
    captures=[]
    with pytest.raises(ZerodhaDataUnavailable,match='ambiguous'):
        client.historical_data(1,'2026-09-01','2026-09-02','minute',capture_response=lambda *args: captures.append(args))
    assert not captures and client.reqsession.hooks['response'] == [repeat]


@pytest.mark.parametrize("exchange", [None, "NSE"])
def test_instruments_capture_preserves_csv_and_receipt(monkeypatch, exchange):
    raw = b"instrument_token,exchange_token,tradingsymbol,last_price,tick_size,lot_size,expiry,strike\n123,12,ABC,100,0.05,1,,0\n"
    client = _captured_history_client(monkeypatch, raw, content_type="text/csv")
    from app.providers import zerodha_data_runtime as module
    monkeypatch.setattr(module, "MAX_INSTRUMENT_RESPONSE_BYTES", len(raw))
    captures = []
    before = dt.datetime.now(dt.timezone.utc)
    rows = client.instruments(exchange, capture_response=lambda *args: captures.append(args))
    assert rows[0]["instrument_token"] == 123
    assert rows == client.instruments(exchange)
    assert len(captures) == 1
    body, received_at, selected_exchange = captures[0]
    assert body == raw and selected_exchange == exchange
    assert received_at.tzinfo is dt.timezone.utc
    assert before <= received_at <= dt.datetime.now(dt.timezone.utc)
    assert client.reqsession.hooks["response"] == []


@pytest.mark.parametrize("failure", ["empty", "oversize", "ambiguous", "status", "parse", "consumer", "missing"])
def test_instruments_capture_failures_clean_hooks(monkeypatch, failure):
    from app.providers import zerodha_data_runtime as module
    raw = b"instrument_token,exchange_token,tradingsymbol,last_price,tick_size,lot_size,expiry,strike\n123,12,ABC,100,0.05,1,,0\n"
    if failure == "empty":
        raw = b""
    if failure == "parse":
        raw = b"instrument_token\ninvalid\n"
    client = _captured_history_client(monkeypatch, raw,
        status=201 if failure == "status" else 200, content_type="text/csv")
    if failure == "oversize":
        monkeypatch.setattr(module, "MAX_INSTRUMENT_RESPONSE_BYTES", len(raw) - 1)
    def existing(response, **kwargs):
        if failure == "ambiguous":
            client.reqsession.hooks["response"][-1](response)
        return response
    client.reqsession.hooks["response"].append(existing)
    if failure == "missing":
        monkeypatch.setattr(module.KiteConnect, "instruments", lambda *args: [])
    captures = []
    def consume(*args):
        if failure == "consumer":
            raise TimeoutError("consumer failed")
        captures.append(args)
    with pytest.raises((module.ZerodhaDataUnavailable, ValueError, TimeoutError)):
        client.instruments("NSE", capture_response=consume)
    assert captures == []
    assert client.reqsession.hooks["response"] == [existing]


@pytest.mark.parametrize("failure", [None, "missing", "multiple", "malformed", "consumer", "provider"])
def test_runtime_instruments_capture_uses_successful_attempt(failure):
    from app.providers import zerodha_data_runtime as module
    wire = _Wire("dummy")
    calls, captures, credentials = [], [], []
    received_at = dt.datetime(2026, 9, 1, 1, 2, 3, 456789, tzinfo=dt.timezone.utc)
    def instruments(exchange, **kwargs):
        calls.append(exchange)
        callback = kwargs["capture_response"]
        if len(calls) == 1:
            callback(b"failed-attempt", received_at, exchange)
            raise TimeoutError("provider timeout")
        if failure == "provider":
            raise ValueError("provider failed")
        if failure != "missing":
            callback(b"successful-attempt", received_at, exchange)
        if failure == "multiple":
            callback(b"extra", received_at, exchange)
        return {} if failure == "malformed" else [{"instrument_token": 123}]
    wire.instruments = instruments
    def source():
        credentials.append(True)
        return {"api_key": "dummy", "access_token": "dummy"}
    runtime = module.ZerodhaDataRuntime(source, lambda token: False,
        client_factory=lambda **kwargs: wire, sleep=lambda delay: None,
        policy=module.RuntimePolicy(backoff_base_seconds=0))
    def consume(*args):
        if failure == "consumer":
            raise TimeoutError("consumer timeout")
        captures.append(args)
    if failure is None:
        assert runtime.instruments("NSE", capture_response=consume) == [{"instrument_token": 123}]
        assert captures == [(b"successful-attempt", received_at, "NSE")]
    else:
        with pytest.raises(TimeoutError if failure == "consumer" else module.ZerodhaDataUnavailable):
            runtime.instruments("NSE", capture_response=consume)
        assert captures == []
    assert calls == ["NSE", "NSE"]
    assert len(credentials) == 2


def test_runtime_default_instruments_preserves_wire_signature():
    wire = _Wire("dummy")
    _history_runtime(wire).instruments("NSE")
    assert wire.calls == [("instruments", "NSE", None)]
