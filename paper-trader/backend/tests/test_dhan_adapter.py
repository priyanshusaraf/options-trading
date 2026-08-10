"""Dhan adapter semantics the shared conformance contract cannot express.

Every one of these guards a way this adapter can return a **plausible wrong answer** rather than
an error. That is the class of bug a broker fleet multiplies: with seven adapters, the ones that
raise get fixed on the first run, and the ones that quietly answer wrongly do not.

Read from https://dhanhq.co/docs/v2/ on 2026-08-10; each test names the documented fact it
holds the adapter to.
"""
from __future__ import annotations

import datetime as dt

import pytest

from app.core.instruments import get_instrument
from app.providers import dhan_instruments as master
from app.providers.base import ProviderReadError
from app.providers.dhan import (
    INTRADAY_MINUTES,
    DhanInstrumentResolver,
    DhanProvider,
    UnsupportedInterval,
    supported_intervals,
)
from app.providers.dhan_transport import DhanResponse

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
NOW = dt.datetime(2026, 8, 10, 14, 7)


class _Transport:
    def __init__(self, now=NOW, *, rows: int = 8) -> None:
        self.now = now
        self.rows = rows
        self.posts: list[tuple[str, dict]] = []
        self.payload_override: dict | None = None

    def post(self, path: str, body: dict):
        self.posts.append((path, body))
        if self.payload_override is not None:
            return DhanResponse(endpoint=path, data=self.payload_override)
        if path == "/marketfeed/ltp":
            segment, ids = next(iter(body.items()))
            return DhanResponse(endpoint=path,
                                data={segment: {str(ids[0]): {"last_price": 24012.5}}})
        step = dt.timedelta(days=1) if path.endswith("historical") else dt.timedelta(minutes=15)
        end = self.now - step
        stamps, o, h, low, c, vol = [], [], [], [], [], []
        # NEWEST FIRST on the wire, deliberately: Dhan documents no ordering guarantee, and an
        # adapter that trusted the order would pass a tidied fixture and fail against the API.
        for i in range(self.rows):
            ts = end - step * i
            base = 24000.0 + i
            stamps.append(ts.replace(tzinfo=IST).timestamp())
            o.append(base); h.append(base + 6.0); low.append(base - 4.0)
            c.append(base + 2.0); vol.append(15000.0 + i)
        return DhanResponse(endpoint=path, data={
            "timestamp": stamps, "open": o, "high": h, "low": low, "close": c, "volume": vol})


@pytest.fixture(autouse=True)
def _master():
    master.load_master(
        [{"SECURITY_ID": "13", "SEGMENT": "IDX_I", "SYMBOL_NAME": "NIFTY",
          "INSTRUMENT": "INDEX"}],
        canonical_for=lambda symbol, segment: "NIFTY" if symbol == "NIFTY" else None)
    yield
    master.clear_master()


@pytest.fixture()
def nifty():
    return get_instrument("NIFTY")


def _provider(now=NOW):
    p = DhanProvider.__new__(DhanProvider)
    p.access_token = "tok"
    p.client_id = "1000000001"
    p._transport = _Transport(now)
    p._resolver = DhanInstrumentResolver()
    p.now = lambda: now
    return p, p._transport


# ── 1. the columnar layout ────────────────────────────────────────────────

def test_parallel_arrays_become_candles_in_the_right_order(nifty):
    """Documented: the charts endpoints return `open`/`high`/`low`/`close`/`volume`/`timestamp`
    as six parallel arrays. A row-oriented parser does not raise on this — it reads floats out
    of the `open` array as though each were a candle."""
    p, _ = _provider()
    bars = p.get_candles(nifty, "15minute", 5)
    assert bars, "no bars parsed out of a well-formed columnar payload"
    assert [b.ts for b in bars] == sorted(b.ts for b in bars), "not sorted oldest-first"
    first = bars[0]
    assert first.high > first.open > first.low, (first.open, first.high, first.low)
    assert all(b.ts.tzinfo is None for b in bars), "epoch → naive IST, like every other adapter"


def test_ragged_columns_are_refused_not_zipped(nifty):
    """The most dangerous shape available here. Zipping to the shortest array builds a candle
    whose open is from one bar and whose close is from another — not a bad candle, a fabricated
    one, and nothing downstream can detect it."""
    p, transport = _provider()
    transport.payload_override = {
        "timestamp": [1.0, 2.0, 3.0], "open": [1.0, 2.0, 3.0], "high": [1.0, 2.0, 3.0],
        "low": [1.0, 2.0, 3.0], "close": [1.0, 2.0], "volume": [1.0, 2.0, 3.0]}
    with pytest.raises(ProviderReadError) as e:
        p.get_candles(nifty, "15minute", 5)
    assert "ragged" in str(e.value)


def test_an_absent_timestamp_array_is_no_bars_not_an_error(nifty):
    """`[]` means the read SUCCEEDED and there were no bars. That is a different fact from a
    failed read, and the whole failure channel exists to keep them apart."""
    p, transport = _provider()
    transport.payload_override = {}
    assert p.get_candles(nifty, "15minute", 5) == []


def test_a_non_array_payload_is_refused(nifty):
    p, transport = _provider()
    transport.payload_override = {"timestamp": [1.0], "open": "nope", "high": [1.0],
                                  "low": [1.0], "close": [1.0], "volume": [1.0]}
    with pytest.raises(ProviderReadError):
        p.get_candles(nifty, "15minute", 5)


# ── 2. the interval gap is real and must be refused ───────────────────────

@pytest.mark.parametrize("interval", ["3minute", "10minute", "30minute"])
def test_the_intervals_dhan_cannot_serve_are_refused_not_approximated(interval, nifty):
    """Documented intraday intervals are 1/5/15/25/60 minutes. This engine sweeps 3, 10 and 30
    as well. Dhan cannot serve them, and a nearby substitute is available here in a way it was
    not for Upstox — which makes the temptation worse, not better. Answering a 30-minute request
    with 25-minute bars raises nothing and changes every indicator's horizon."""
    assert interval not in supported_intervals()
    p, transport = _provider()
    with pytest.raises(UnsupportedInterval):
        p.get_candles(nifty, interval, 5)
    assert transport.posts == [], "a request was built for an interval Dhan does not serve"


def test_the_engine_vocabulary_gap_is_stated_rather_than_hidden():
    """This adapter is legitimately narrower than the engine. The gap is asserted here so it is
    a known, named coverage fact — if someone later adds a 30-minute mapping, they have to
    delete this test and say why, rather than the constraint quietly evaporating."""
    from app.backtest.sweep import MAX_DAYS
    gap = sorted(set(MAX_DAYS) - supported_intervals())
    assert gap == ["10minute", "30minute", "3minute"], (
        f"Dhan's interval coverage changed: {gap}. Re-read https://dhanhq.co/docs/v2/ and "
        f"update INTRADAY_MINUTES — do not widen the map from another broker's vocabulary.")


def test_every_mapped_interval_is_one_dhan_documents():
    """Guard the guard, in the other direction: a mapping to an interval Dhan does not accept
    fails at the API with an error that does not name the field."""
    assert set(INTRADAY_MINUTES.values()) <= {1, 5, 15, 25, 60}


# ── 3. the non-inclusive end date ─────────────────────────────────────────

def test_the_daily_window_ends_past_today_because_todate_is_non_inclusive(nifty):
    """Documented: `toDate` is non-inclusive on `/charts/historical`. Passing today's date
    returns nothing for today — the entire current session missing, from a response that looks
    completely successful."""
    p, transport = _provider()
    p.get_candles(nifty, "day", 30)
    path, body = transport.posts[-1]
    assert path == "/charts/historical"
    assert body["toDate"] > NOW.date().isoformat(), (
        f"toDate {body['toDate']} does not clear today; a non-inclusive bound drops the newest bar")


def test_the_intraday_window_is_capped_at_the_documented_ninety_days(nifty):
    """Documented: "Only 90 days of data can be polled at once". Asking for more is rejected
    outright, so a 200-day 15-minute sweep would return nothing rather than less."""
    p, transport = _provider()
    p.get_candles(nifty, "15minute", 200)
    _, body = transport.posts[-1]
    span = (dt.datetime.fromisoformat(body["toDate"])
            - dt.datetime.fromisoformat(body["fromDate"])).days
    assert span <= 90, f"requested a {span}-day intraday window; the API caps it at 90"


# ── 4. two credentials, not one ───────────────────────────────────────────

def test_a_token_without_a_client_id_is_not_authenticated():
    """Dhan needs `access-token` AND `client-id`. Reporting a token-only connection as
    authenticated makes every later refusal look like an outage instead of a config gap."""
    p = DhanProvider.__new__(DhanProvider)
    p.access_token, p.client_id = "tok", None
    assert p.is_authenticated() is False
    p.client_id = "1000000001"
    assert p.is_authenticated() is True


def test_the_two_credential_failures_are_named_separately():
    from app.providers.dhan_transport import DhanTransport
    t = DhanTransport(lambda: "tok", lambda: None, client=object())
    with pytest.raises(ProviderReadError) as e:
        t.post("/x", {})
    assert "client id" in str(e.value)
    t2 = DhanTransport(lambda: None, lambda: "cid", client=object())
    with pytest.raises(ProviderReadError) as e2:
        t2.post("/x", {})
    assert "access token" in str(e2.value)


def test_no_credential_appears_in_an_error_message():
    """An exception string reaches logs, /api/health and the operator's terminal."""
    from app.providers.dhan_transport import DhanTransport

    class Boom:
        def post(self, *a, **k):
            raise RuntimeError("connect failed")

    t = DhanTransport(lambda: "SECRET-TOKEN", lambda: "SECRET-CLIENT", client=Boom())
    with pytest.raises(ProviderReadError) as e:
        t.post("/charts/intraday", {})
    assert "SECRET-TOKEN" not in str(e.value) and "SECRET-CLIENT" not in str(e.value)


# ── 5. the instrument master refuses rather than guessing ─────────────────

def test_an_unloaded_master_resolves_nothing_and_the_adapter_refuses(nifty):
    """The deliberate correction to the hand-seeded pattern. A wrong security id does not raise
    — it prices a different real company, forever, with every layer above reporting health. So
    an unverified master resolves nothing, and the connection has no coverage rather than wrong
    coverage."""
    master.clear_master()
    p, transport = _provider()
    assert p.get_candles(nifty, "15minute", 5) == []
    assert p.get_ltp(nifty) is None
    assert p.resolve_underlying(nifty) is None
    assert transport.posts == [], "a request was built for an instrument we cannot address"


def test_a_master_whose_columns_we_cannot_read_raises_rather_than_loading_empty():
    """An empty master and an unreadable one look identical to every caller — both resolve
    nothing. Only one of them is a bug, so the loader separates them."""
    with pytest.raises(ProviderReadError) as e:
        master.load_master([{"nonsense": "1", "other": "2"}],
                           canonical_for=lambda s, seg: "NIFTY")
    assert "column" in str(e.value).lower()


def test_the_master_addresses_the_instrument_dhans_way(nifty):
    """`securityId` + `exchangeSegment`, never a Kite tradingsymbol."""
    p, transport = _provider()
    p.get_ltp(nifty)
    path, body = transport.posts[-1]
    assert path == "/marketfeed/ltp"
    assert body == {"IDX_I": [13]}, body


def test_the_resolver_never_reads_kites_mapping_fields(nifty):
    """`Instrument` still carries Kite's `spot_symbol`/`option_name`. A second resolver reading
    them would resolve Dhan to a Kite string that Dhan has never heard of."""
    resolved = DhanInstrumentResolver().resolve_underlying(nifty)
    assert resolved is not None
    assert resolved.provider == "dhan"
    assert resolved.symbol == "NIFTY" and resolved.exchange == "IDX_I"


# ── the order-path HTTP verbs ─────────────────────────────────────────────
# Added with the execution venue. These are the wire methods that place, modify and cancel REAL
# orders, so each documented difference from Kite gets a test rather than an assumption.

class _RecordingHttp:
    """Stands in for httpx.Client. Records the METHOD, which is the thing most likely to be
    copied wrongly from the Kite adapter."""

    def __init__(self, payload=None, status=200):
        self.seen: list[tuple] = []
        self.payload = {"status": "success", "data": {"orderId": "DH-1"}} if payload is None else payload
        self.status = status

    def request(self, method, url, headers=None, **kw):
        self.seen.append((method, url, kw.get("json")))
        outer = self

        class R:
            status_code = outer.status

            @staticmethod
            def json():
                return outer.payload
        return R()


def _transport(payload=None, status=200):
    from app.providers.dhan_transport import DhanTransport
    http = _RecordingHttp(payload, status)
    t = DhanTransport(lambda: "tok", lambda: "cid", client=http,
                      throttle=type("T", (), {"wait": lambda self: None})())
    return t, http


def test_modify_uses_put_and_cancel_uses_delete():
    """Documented: `PUT /orders/{id}` and `DELETE /orders/{id}`. Kite POSTs to action paths;
    copying that shape here returns 404/405, and a failed protective-stop cancel means the
    caller must not send a closing order — so the position stays open with a stale stop."""
    t, http = _transport()
    t.put("/orders/DH-1", {"x": 1})
    assert http.seen[-1][0] == "PUT"
    t.delete("/orders/DH-1")
    assert http.seen[-1][0] == "DELETE"
    assert http.seen[-1][2] is None, "DELETE must not carry a body"


def test_the_order_book_may_be_a_bare_json_array():
    """`GET /orders` returns an ARRAY, not an envelope. A transport that insisted on an object
    would raise on every order-book read — which `find_fill` and the protective-stop inventory
    both depend on."""
    t, _ = _transport(payload=[{"orderId": "DH-1"}, {"orderId": "DH-2"}])
    assert len(t.get("/orders").data) == 2


def test_market_data_still_refuses_a_list_so_the_error_names_the_shape():
    """`post` defaults to allow_list=False on purpose. `_columns_to_candles` and `get_ltp` index
    `data` as a mapping, so a list must fail here naming the shape rather than three frames
    later as an AttributeError on `.get`."""
    t, _ = _transport(payload=[{"nope": 1}])
    with pytest.raises(ProviderReadError) as e:
        t.post("/v2/charts/intraday", {})
    assert "list" in str(e.value)
    # the order client opts in explicitly
    assert len(t.post("/orders", {}, allow_list=True).data) == 1


def test_an_http_error_is_never_read_as_no_data():
    """A 500 that returned `[]` would be indistinguishable from an empty order book — and an
    empty order book is what `_protection_inventory` reads as "this position has no exchange
    stop", which licenses placing a second one."""
    t, _ = _transport(payload={"errorCode": "X", "errorMessage": "boom"}, status=500)
    with pytest.raises(ProviderReadError) as e:
        t.get("/orders")
    assert "500" in str(e.value)


def test_an_error_inside_a_200_envelope_is_still_an_error():
    """Dhan reports application errors inside a 200 as well as by status code."""
    t, _ = _transport(payload={"status": "failure", "errorMessage": "rejected"})
    with pytest.raises(ProviderReadError) as e:
        t.get("/orders")
    assert "rejected" in str(e.value)


def test_no_credential_reaches_a_transport_error_message():
    """These messages reach logs, /api/health and the operator's terminal."""
    t, http = _transport()

    def boom(*a, **k):
        raise RuntimeError("connect refused")

    http.request = boom
    from app.providers.dhan_transport import DhanTransport
    t2 = DhanTransport(lambda: "SECRET-TOKEN", lambda: "SECRET-CLIENT", client=http,
                       throttle=type("T", (), {"wait": lambda self: None})())
    with pytest.raises(ProviderReadError) as e:
        t2.put("/orders/1", {})
    assert "SECRET-TOKEN" not in str(e.value) and "SECRET-CLIENT" not in str(e.value)
