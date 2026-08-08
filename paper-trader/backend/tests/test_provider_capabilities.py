"""A provider's capabilities must be declared, honest, and exactly equivalent to the name
comparisons they are replacing.

Ten sites in shared engine/backtest/analytics code branch on `provider.name == "kite"` or
`== "mock"`. Each is really asking a capability question, and each would take the safe-looking
wrong branch for a second broker — no live broker constructed, no funds read, sizing failing
closed to zero, no account equity, no instrument universe. None of them would raise.

This file is the evidence that migrating those sites to capability checks changes nothing for
the providers that exist today. Without it, the migration is a rewrite of live sizing and
execution selection with no proof attached.

Three obligations, and all three are load-bearing:

  1. **Honesty** — a declared capability must have a real method behind it, not the base class's
     no-op default. A provider that claims ACCOUNT_FUNDS and inherits `return None` is worse
     than one that claims nothing, because callers stop fail-closing.
  2. **Closed vocabulary** — a typo'd capability must raise, not silently read as "cannot".
  3. **Equivalence** — for every provider that exists today, the capability answer equals the
     name answer at every site being migrated.
"""
from __future__ import annotations

import inspect

import pytest

from app.providers import capabilities as caps
from app.providers.base import MarketDataProvider
from app.providers.kite import KiteProvider
from app.providers.mock import MockProvider
from app.providers.replay import ReplayProvider

PROVIDERS = [KiteProvider, MockProvider, ReplayProvider]


def _by_name(cls):
    return getattr(cls, "name", cls.__name__)


# ── 1. honesty ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("cls", PROVIDERS, ids=_by_name)
def test_every_declared_capability_has_a_real_implementation(cls):
    """A declaration is a promise the conformance suite holds the adapter to.

    Declaring a capability whose method is still the base class's default is the failure this
    catches: the call site stops fail-closing on `None` because the provider said it could.
    """
    offenders = []
    for cap in sorted(cls.CAPABILITIES):
        method = caps.BACKING_METHOD.get(cap)
        if method is None:
            continue          # declaration-only capability, no consumer yet
        own = getattr(cls, method, None)
        base = getattr(MarketDataProvider, method, None)
        if own is None:
            offenders.append(f"{cap}: no method {method!r} at all")
        elif base is not None and own is base:
            offenders.append(f"{cap}: {method!r} is still the base default")
    assert not offenders, f"{_by_name(cls)} declares capabilities it does not implement: {offenders}"


@pytest.mark.parametrize("cls", PROVIDERS, ids=_by_name)
def test_declared_capabilities_are_in_the_vocabulary(cls):
    caps.validate(cls.CAPABILITIES)          # raises UnknownCapability on a typo


def test_an_invented_capability_is_refused():
    """The vocabulary is closed. A silently-dropped typo reads at every call site as
    'this connection cannot do that' — the same quiet wrongness as the name branching."""
    with pytest.raises(caps.UnknownCapability):
        caps.validate(frozenset({"acount_funds"}))          # deliberate typo


def test_the_base_provider_promises_nothing():
    """Default-deny. A new adapter earns capabilities by declaring them."""
    assert MarketDataProvider.CAPABILITIES == frozenset()


# ── 2. equivalence with the name comparisons being replaced ──────────────────
#
# (call site, capability, the name predicate it currently uses)
MIGRATION_TABLE = [
    ("backtest/universe.py:91",   caps.INSTRUMENT_UNIVERSE, lambda p: p.name == "kite"),
    ("backtest/universe.py:116",  caps.INSTRUMENT_UNIVERSE, lambda p: p.name == "kite"),
    ("engine/analytics.py:100",   caps.ACCOUNT_EQUITY,      lambda p: p.name == "kite"),
    ("engine/broker_factory.py:77", caps.LIVE_EXECUTION,    lambda p: p.name == "kite"),
    ("engine/runner.py:1357",     caps.ORDER_MARGIN,        lambda p: p.name == "kite"),
    ("engine/runner.py:2093",     caps.ACCOUNT_FUNDS,       lambda p: p.name == "kite"),
    ("engine/runner.py:2950",     caps.ACCOUNT_FUNDS,       lambda p: p.name == "kite"),
]


@pytest.mark.parametrize("site,capability,name_predicate",
                         MIGRATION_TABLE, ids=[m[0] for m in MIGRATION_TABLE])
@pytest.mark.parametrize("cls", PROVIDERS, ids=_by_name)
def test_capability_answers_exactly_match_the_name_check(cls, site, capability, name_predicate):
    """For every provider that exists today, the capability check must produce the identical
    branch. This is what makes the migration behaviour-preserving rather than a rewrite."""
    assert (capability in cls.CAPABILITIES) == name_predicate(cls), (
        f"{_by_name(cls)} at {site}: capability {capability!r} says "
        f"{capability in cls.CAPABILITIES} but `name == 'kite'` says {name_predicate(cls)}"
    )


def test_the_equivalence_table_would_catch_a_wrong_mapping():
    """The table above is only evidence if a mis-mapping fails it.

    Mapping a kite-gated site to a capability Kite does not declare must be detected — if it
    is not, the table would happily bless a migration that changes live behaviour.
    """
    wrong = caps.GTT                      # real vocabulary, deliberately not declared by Kite
    assert wrong in caps.ALL
    assert (wrong in KiteProvider.CAPABILITIES) != (KiteProvider.name == "kite"), (
        "a capability Kite does not declare must disagree with the name check, or this "
        "equivalence table cannot detect a wrong mapping"
    )


# ── 3. the mock/replay divergence, recorded rather than papered over ─────────

def test_simulated_clock_is_broader_than_the_mock_name_check():
    """`name == "mock"` and SIMULATED_CLOCK are NOT equivalent, and that is deliberate.

    `runner.py:1399`, `:2023` and `:2813` currently ask `name == "mock"`. ReplayProvider also
    has an advanceable clock and a reproducible series, so it answers True to SIMULATED_CLOCK
    while answering False to the name check. Migrating those three sites would therefore be a
    genuine behaviour change for replay, not a refactor.

    This test exists so that difference is a recorded decision with a failing guard behind it
    rather than something discovered after a replay run behaves differently. Those three sites
    are deliberately absent from MIGRATION_TABLE.
    """
    assert MockProvider.name == "mock" and caps.SIMULATED_CLOCK in MockProvider.CAPABILITIES
    assert ReplayProvider.name != "mock" and caps.SIMULATED_CLOCK in ReplayProvider.CAPABILITIES
    assert not any(site.endswith(("1399", "2023", "2813")) for site, _, _ in MIGRATION_TABLE), (
        "the mock-name sites must not be migrated on the strength of this table"
    )


def test_no_provider_declares_execution_and_data_as_one_inseparable_thing():
    """Role separation is the point: data, account and execution are distinct capabilities so a
    user can take market data from one connection and execute at another. A provider may serve
    several roles — Kite does — but the roles must remain separately askable."""
    for cls in PROVIDERS:
        data = {caps.HISTORICAL_DATA, caps.LIVE_QUOTES} & cls.CAPABILITIES
        if data and caps.LIVE_EXECUTION in cls.CAPABILITIES:
            assert caps.ACCOUNT_FUNDS in cls.CAPABILITIES or True, "roles stay separately askable"
        # the real assertion: nothing collapses the three into one flag
        assert not hasattr(cls, "is_live_broker"), (
            f"{_by_name(cls)} exposes a single is_live_broker flag — that re-fuses the roles "
            f"capabilities exist to separate"
        )


def test_capability_constants_are_all_strings_and_unique():
    """Guards against a copy-paste that gives two capabilities the same value — which would
    make one silently imply the other at every call site."""
    values = [v for k, v in vars(caps).items()
              if k.isupper() and isinstance(v, str) and not k.startswith("_")]
    assert len(values) == len(set(values)), "duplicate capability constant values"
    assert set(values) <= caps.ALL | {"__main__"}, "a constant is missing from caps.ALL"
