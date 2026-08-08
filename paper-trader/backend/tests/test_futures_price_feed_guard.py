"""The index-futures segment must refuse to open a position it could never mark.

`MarketDataProvider.get_futures_ltp` is the base no-op returning `None`, and **no provider
implements it** — not the mock, not replay, and not Kite. The capability audit surfaced this:
Kite initially declared `FUTURES_QUOTES` and the honesty check rejected the declaration.

Meanwhile `runner.py` calls `get_futures_ltp` at three sites to mark a futures position, to
decide staleness, and to price the delivery-window force close. With the feed unimplemented:

  * `fut` is `None` at every mark, so the position never marks on a real futures price;
  * `pos_stale` is therefore permanently True;
  * the delivery-window close falls back to `pos.last_premium` — the **entry** price — so an
    obligation gets closed at a number that has nothing to do with the market.

`index_futures_enabled` defaults False and the segment is documented as "fully built and
switched OFF", so this is latent today. It stops being latent the moment that flag is flipped,
and nothing would have raised — the segment would simply trade blind. Opening a position that
cannot be marked is worse than not opening it, so the entry path now fails closed.
"""
from __future__ import annotations

import pytest

from app.providers import capabilities as caps
from app.providers.kite import KiteProvider
from app.providers.mock import MockProvider
from app.providers.replay import ReplayProvider


def test_the_guard_still_has_providers_to_protect_against():
    """The guard's premise, re-pinned after Kite gained a real feed on 2026-08-09.

    The earlier version of this test asserted that NO provider could price futures, and said
    that implementing one should make it fail as a reminder to re-evaluate the guard. That is
    exactly what happened: `KiteProvider.get_futures_ltp` is now implemented and the capability
    is honestly declared, so Kite is allowed through.

    The guard is not obsolete. Mock and replay still cannot price a dated contract, and a
    future adapter starts with no capabilities at all — so the segment must still refuse rather
    than open a position it could never mark. If this ever ends up with nothing to protect
    against, the guard has become dead code and should be removed rather than left as decoration.
    """
    assert caps.FUTURES_QUOTES in KiteProvider.CAPABILITIES, (
        "Kite implements get_futures_ltp — it should declare the capability"
    )
    incapable = [cls for cls in (MockProvider, ReplayProvider)
                 if caps.FUTURES_QUOTES not in cls.CAPABILITIES]
    assert incapable, (
        "every provider can now price futures — the guard protects nobody and is dead code"
    )


class _StubProvider:
    """Minimal stand-in: the guard only reads `.supports()` and `.name`."""

    def __init__(self, *, can_price: bool) -> None:
        self.name = "stub"
        self._can = can_price

    def supports(self, capability: str) -> bool:
        return capability == caps.FUTURES_QUOTES and self._can


class _Runner:
    """The guard, isolated from the engine's construction cost.

    Deliberately reproduces the real branch rather than importing it: constructing a full
    `EngineRunner` pulls in the broker, the database and both lanes, none of which this
    behaviour depends on. `test_the_guard_is_wired_into_the_real_entry_path` below is what
    proves the real code contains this branch, so the isolation cannot drift into fiction.
    """

    def __init__(self, provider, enabled: bool) -> None:
        self.provider = provider
        self.enabled = enabled
        self.alerts: list[tuple[str, str]] = []
        self.proceeded = False

    def _alert_infra(self, key: str, msg: str) -> None:
        self.alerts.append((key, msg))

    def process(self) -> None:
        if not self.enabled:
            return
        if not self.provider.supports(caps.FUTURES_QUOTES):
            self._alert_infra("futures_no_price_feed", "cannot price futures")
            return
        self.proceeded = True


def test_the_segment_stays_shut_when_disabled_regardless_of_capability():
    r = _Runner(_StubProvider(can_price=True), enabled=False)
    r.process()
    assert not r.proceeded and not r.alerts, "a disabled segment must not alert or open"


def test_enabling_the_segment_without_a_price_feed_refuses_and_says_why():
    r = _Runner(_StubProvider(can_price=False), enabled=True)
    r.process()
    assert not r.proceeded, "opened a futures position that could never be marked"
    assert r.alerts and r.alerts[0][0] == "futures_no_price_feed", r.alerts


def test_a_provider_that_can_price_futures_is_allowed_through():
    """The guard must gate on the capability, not disable the segment permanently."""
    r = _Runner(_StubProvider(can_price=True), enabled=True)
    r.process()
    assert r.proceeded and not r.alerts


def test_the_guard_is_wired_into_the_real_entry_path():
    """The isolation above is only meaningful if the real code carries the same branch.

    Asserted against the **AST** of `_process_futures_entries`, not its source text. The first
    version of this test grepped `inspect.getsource` for "FUTURES_QUOTES" and was **vacuous**:
    replacing the whole condition with `if False:` left the explanatory comment above it in
    place, the string was still found, and the test stayed green while the guard was gone.
    Comments do not survive parsing, so an AST assertion cannot be satisfied by prose.
    """
    import ast
    import inspect
    import textwrap

    from app.engine.runner import EngineRunner

    tree = ast.parse(textwrap.dedent(inspect.getsource(EngineRunner._process_futures_entries)))

    supports_calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute) and node.func.attr == "supports"
        and any(isinstance(a, ast.Attribute) and a.attr == "FUTURES_QUOTES" for a in node.args)
    ]
    assert supports_calls, (
        "the futures entry path no longer asks whether the connection can price futures — "
        "a position would be opened that can never be marked"
    )

    alert_keys = [
        node.value for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and node.value == "futures_no_price_feed"
    ]
    assert alert_keys, "the refusal no longer raises an operator-visible alert"

    # The guard must run before the entry path inspects or opens anything.
    guard_line = min(c.lineno for c in supports_calls)
    open_lines = [n.lineno for n in ast.walk(tree)
                  if isinstance(n, ast.Name) and n.id == "open_futs"]
    assert open_lines and guard_line < min(open_lines), (
        "the price-feed guard must run before the entry path inspects or opens positions"
    )
