"""Canonical instrument identity must be provider-independent.

Strategy OS owns the economic instrument; a provider owns its own names for it. Today those two
things are tangled — `Instrument.spot_symbol` is a Kite tradingsymbol, `option_name` is a Kite
instruments-dump concept, and `f"{spot_exchange}:{spot_symbol}"` is a Kite quote key. A second
provider with different symbology would have to reuse Kite's strings (resolving to the wrong
contract, silently) or fork `Instrument` (breaking "one of anything").

`InstrumentResolver` is the seam that makes a second mapping possible. These tests hold the line
the seam exists to hold:

  * the canonical key is the only identifier that crosses providers;
  * two providers may map the same canonical instrument to entirely different symbology;
  * a mapping carries provenance, so it cannot be applied against the wrong connection;
  * a non-Kite resolver never reads Kite's symbology fields off the canonical object.

The last one is the load-bearing constraint while `spot_symbol` still lives on `Instrument`.
Without it, "Strategy OS owns instrument identity" is a comment rather than a property.
"""
from __future__ import annotations

import pytest

from app.core.instruments import Instrument, get_instrument
from app.providers.instrument_resolver import InstrumentResolver, ResolvedInstrument
from app.providers.kite import KiteProvider


@pytest.fixture
def nifty() -> Instrument:
    return get_instrument("NIFTY")


class _UpstoxResolver:
    """A second provider's mapping for the same canonical instruments.

    Symbology is deliberately unlike Kite's — different symbol text, a different exchange code,
    a different token space — because the point of the seam is that none of that leaks into the
    canonical object. It reads ONLY `inst.key`.
    """

    name = "upstox"
    _MAP = {
        "NIFTY": ("Nifty 50", "NSE_INDEX", 26000),
        "GOLDM": ("GOLDM25AUGFUT", "MCX_FO", 428123),
    }

    def resolve_underlying(self, inst: Instrument) -> ResolvedInstrument | None:
        entry = self._MAP.get(inst.key)
        if entry is None:
            return None
        symbol, exchange, token = entry
        return ResolvedInstrument(canonical_key=inst.key, provider=self.name,
                                  symbol=symbol, exchange=exchange, token=token)


def test_a_second_provider_maps_the_same_canonical_instrument_differently(nifty):
    """The whole point: one economic instrument, two symbologies, no change to `Instrument`."""
    upstox = _UpstoxResolver().resolve_underlying(nifty)
    assert upstox is not None
    assert upstox.canonical_key == "NIFTY"          # the only shared identifier
    assert upstox.symbol != nifty.spot_symbol       # ...and nothing else is shared
    assert upstox.exchange != nifty.spot_exchange
    assert upstox.quote_key() == "NSE_INDEX:Nifty 50"


def test_the_canonical_key_is_the_only_identifier_that_crosses_providers(nifty):
    kite_like = ResolvedInstrument(canonical_key=nifty.key, provider="kite",
                                   symbol=nifty.spot_symbol, exchange=nifty.spot_exchange)
    upstox = _UpstoxResolver().resolve_underlying(nifty)
    assert kite_like.canonical_key == upstox.canonical_key
    assert (kite_like.symbol, kite_like.exchange) != (upstox.symbol, upstox.exchange)


def test_a_mapping_carries_the_connection_that_produced_it(nifty):
    """Provenance is not decoration. A mapping applied against the wrong broker resolves to a
    different contract while looking perfectly valid, so the producing connection travels with
    it."""
    upstox = _UpstoxResolver().resolve_underlying(nifty)
    assert upstox.provider == "upstox"
    assert upstox.provider != KiteProvider.name


def test_an_unknown_instrument_resolves_to_none_rather_than_a_guess():
    """`None` means "I do not know this instrument". Falling back to another provider's mapping
    is how a wrong contract gets traded."""
    unknown = Instrument("ZZZZ", "Unknown", "NSE", "NSE", "ZZZZ", "ZZZZ",
                         lot_size=1, strike_step=1, priority=99,
                         mock_spot=100.0, mock_vol=0.1)
    assert _UpstoxResolver().resolve_underlying(unknown) is None


def test_a_non_kite_resolver_does_not_read_kites_symbology_off_the_canonical_object():
    """The constraint that keeps "Strategy OS owns identity" true while `spot_symbol` still
    lives on `Instrument`.

    Asserted by handing the resolver an instrument whose Kite-specific fields are poisoned. A
    resolver that reads them produces the poisoned value; one that maps from `key` is unaffected.
    """
    poisoned = Instrument("NIFTY", "NIFTY 50", "NFO", "WRONG_EXCHANGE", "WRONG_SYMBOL",
                          "WRONG_OPTION_NAME", lot_size=75, strike_step=50, priority=1,
                          mock_spot=24000, mock_vol=0.12)
    resolved = _UpstoxResolver().resolve_underlying(poisoned)
    assert resolved is not None
    assert "WRONG" not in resolved.symbol, "the resolver read Kite's symbology off Instrument"
    assert "WRONG" not in resolved.exchange
    assert resolved.symbol == "Nifty 50"


def test_kite_satisfies_the_resolver_protocol():
    """The seam ships with a real consumer rather than as a mechanism wired to nothing."""
    provider = KiteProvider.__new__(KiteProvider)      # no network, no session
    assert isinstance(provider, InstrumentResolver)


def _bare_kite(monkeypatch, *, token=12345, future=None):
    """A KiteProvider with its dump lookups stubbed — no network, no session."""
    provider = KiteProvider.__new__(KiteProvider)
    monkeypatch.setattr(KiteProvider, "_index_token", lambda self, inst: token)
    monkeypatch.setattr(KiteProvider, "_near_future", lambda self, inst: future)
    return provider


def test_kites_own_mapping_carries_kite_as_its_provenance(monkeypatch, nifty):
    """Asserted against Kite specifically, not only against the fake second resolver.

    An earlier version of this file checked provenance on `_UpstoxResolver` alone, so blanking
    the `provider` field inside `KiteProvider.resolve_underlying` went undetected — a vacuous
    guard over exactly the field that stops a mapping being applied against the wrong broker.
    """
    resolved = _bare_kite(monkeypatch).resolve_underlying(nifty)
    assert resolved is not None
    assert resolved.provider == "kite", "Kite's mapping lost the connection that produced it"
    assert resolved.canonical_key == "NIFTY"
    assert resolved.token == 12345


def test_kite_resolves_a_derivative_underlying_through_the_near_future(monkeypatch):
    """The index/cash branch and the derivative branch are one resolution, and both must carry
    provenance — the second branch is the one the first version of this test never reached."""
    goldm = get_instrument("GOLDM")
    fut = {"tradingsymbol": "GOLDM25AUGFUT", "instrument_token": 999}
    resolved = _bare_kite(monkeypatch, future=fut).resolve_underlying(goldm)
    assert resolved is not None
    assert resolved.provider == "kite"
    assert resolved.symbol == "GOLDM25AUGFUT"
    assert resolved.token == 999


def test_kite_refuses_rather_than_guessing_when_no_future_resolves(monkeypatch):
    goldm = get_instrument("GOLDM")
    assert _bare_kite(monkeypatch, future=None).resolve_underlying(goldm) is None


def test_kites_token_and_quote_key_go_through_one_resolution():
    """`_underlying_token` and `_underlying_quote_key` previously duplicated the index-vs-future
    branch. Two hand-written implementations of one idea is the `candles.py` defect this project
    has already paid for once, so both now derive from `resolve_underlying`.
    """
    import inspect

    for method in (KiteProvider._underlying_token, KiteProvider._underlying_quote_key):
        src = inspect.getsource(method)
        assert "resolve_underlying" in src, f"{method.__name__} no longer uses the one resolution"
        assert "_near_future" not in src, (
            f"{method.__name__} re-implements the index-vs-future branch instead of resolving"
        )


def test_the_resolved_mapping_is_immutable():
    """A mapping that can be edited after production is a mapping whose provenance is a lie."""
    resolved = ResolvedInstrument(canonical_key="NIFTY", provider="kite",
                                  symbol="NIFTY 50", exchange="NSE")
    with pytest.raises(Exception):
        resolved.symbol = "TAMPERED"      # frozen dataclass
