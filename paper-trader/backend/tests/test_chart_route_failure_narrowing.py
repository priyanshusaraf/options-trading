"""A chart degrades on a *data* failure, not on a bug in our own code.

Both chart routes caught bare `Exception` and rendered an empty panel. That was the only thing
they could do while `get_candles` had no failure channel — "the provider is not ready" arrived
as an arbitrary exception type and had to be caught broadly.

`ProviderReadError` changes that, and leaving the broad catch in place is now actively harmful:
a `TypeError` or `AttributeError` introduced in the signal path renders as a blank chart with a
200, which is indistinguishable from an unauthenticated provider. The operator sees "no data"
and the defect never surfaces. This codebase has paid for that shape repeatedly — a failure that
looks like an absence.

So the catch is narrowed to the contract's own failure channel. A read failure still degrades; a
programming error propagates and is seen.
"""
from __future__ import annotations

import pytest

from app.providers.base import ProviderReadError


def _client_and_runner(monkeypatch):
    from app.api import routes
    return routes


def test_a_read_failure_still_degrades_to_an_empty_chart(monkeypatch):
    """The behaviour that must NOT change. An unauthenticated or failing connection renders an
    empty panel, not a 500 — the operator is looking at a chart, not a stack trace."""
    from app.api import routes

    class _Prov:
        def get_candles(self, inst, interval, days):
            raise ProviderReadError("historical_data failed: Incorrect `api_key`")

        def _noop(self, *a, **k):
            return None

    class _Runner:
        provider = _Prov()

        def _interval_for(self, key):
            return "15minute"

    class _Req:
        pass

    monkeypatch.setattr(routes, "_runner", lambda request: _Runner())
    out = routes.candles("NIFTY", _Req())
    assert out["candles"] == [] and out["ema"] == []


def test_a_programming_error_is_not_rendered_as_an_empty_chart(monkeypatch):
    """The behaviour that changes, and the reason for the change.

    A bug in our own code used to arrive at the operator as a blank panel with a 200 — the same
    thing an expired token looks like. It must now surface.
    """
    from app.api import routes

    class _Prov:
        def get_candles(self, inst, interval, days):
            raise AttributeError("'NoneType' object has no attribute 'tradingsymbol'")

    class _Runner:
        provider = _Prov()

        def _interval_for(self, key):
            return "15minute"

    class _Req:
        pass

    monkeypatch.setattr(routes, "_runner", lambda request: _Runner())
    with pytest.raises(AttributeError):
        routes.candles("NIFTY", _Req())


def test_the_option_chart_route_narrows_the_same_way():
    """Both routes, or the inconsistency becomes the next person's surprise."""
    import inspect

    from app.api import routes

    for fn in (routes.candles, routes.option_candles):
        src = inspect.getsource(fn)
        assert "except ProviderReadError" in src, (
            f"{fn.__name__} must degrade on a read failure specifically")
        assert "except Exception" not in src, (
            f"{fn.__name__} still swallows every exception, so a defect in our own code renders "
            f"as an empty chart with a 200")
