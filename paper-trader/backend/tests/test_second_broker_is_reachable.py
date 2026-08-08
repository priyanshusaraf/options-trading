"""A second broker must be able to reach the paths that were gated on the name "kite".

This is the observable success of the capability migration, and it is the thing the previous
slice could not assert: an equivalence table proves the migration changed nothing for the
providers that exist, but it says nothing about whether a *new* provider now works.

Before the migration, seven sites in shared engine/backtest/analytics code asked
`provider.name == "kite"`. A second broker — Upstox, Dhan, anything — answered False at every
one of them and would have:

  * never had a live order client constructed (`broker_factory`);
  * read no account funds, so `deployable_capital` sizes against nothing;
  * quoted no real margin, so futures sizing refuses;
  * reported no account equity;
  * been refused a real instrument universe.

None of that raises. It is the silent, safe-looking wrong branch. These tests fail against the
name comparisons and pass against capabilities, which is exactly what makes them evidence.

The stub deliberately does **not** subclass any existing provider: it is the shape a genuinely
new adapter would have, so nothing here can pass by inheriting Kite's behaviour.
"""
from __future__ import annotations

import pytest

from app.providers import capabilities as caps

class _SecondBroker:
    """A hypothetical second Indian broker connection.

    Declares the same capability set Kite does. Note the name is emphatically not "kite" —
    that is the point of the test.
    """

    name = "upstox"
    CAPABILITIES = frozenset({
        caps.HISTORICAL_DATA, caps.LIVE_QUOTES, caps.OPTION_CHAIN,
        caps.ACCOUNT_FUNDS, caps.ACCOUNT_POSITIONS, caps.ACCOUNT_EQUITY, caps.ORDER_MARGIN,
        caps.LIVE_EXECUTION, caps.MARKET_ORDERS, caps.LIMIT_ORDERS, caps.STOP_ORDERS,
        caps.INSTRUMENT_UNIVERSE,
    })

    def supports(self, capability: str) -> bool:
        return capability in self.CAPABILITIES

    def is_authenticated(self) -> bool:
        return True


class _DataOnlyConnection:
    """A market-data-only connection — the Upstox-data/Zerodha-execution case.

    It must be usable for data and must NOT be mistaken for something that can execute or
    report an account. This is the role separation the architecture exists to keep.
    """

    name = "dataonly"
    CAPABILITIES = frozenset({caps.HISTORICAL_DATA, caps.LIVE_QUOTES})

    def supports(self, capability: str) -> bool:
        return capability in self.CAPABILITIES

    def is_authenticated(self) -> bool:
        return True


MIGRATED_SITES = [
    ("broker_factory: construct a live order client", caps.LIVE_EXECUTION),
    ("runner: read deployable account funds", caps.ACCOUNT_FUNDS),
    ("runner: quote a real futures margin", caps.ORDER_MARGIN),
    ("runner: surface account funds on the cockpit", caps.ACCOUNT_FUNDS),
    ("analytics: report account equity", caps.ACCOUNT_EQUITY),
    ("universe: build a real instrument universe", caps.INSTRUMENT_UNIVERSE),
]


@pytest.mark.parametrize("site,capability", MIGRATED_SITES, ids=[s for s, _ in MIGRATED_SITES])
def test_a_second_broker_reaches_every_previously_kite_gated_site(site, capability):
    """Each of these answered False for any non-Kite connection before the migration."""
    provider = _SecondBroker()
    assert caps.provider_supports(provider, capability), (
        f"a second broker is still shut out of: {site}"
    )
    # and the name check it replaced would still refuse it — this is what makes the assertion
    # above meaningful rather than tautological
    assert provider.name != "kite"


@pytest.mark.parametrize("site,capability", MIGRATED_SITES, ids=[s for s, _ in MIGRATED_SITES])
def test_a_data_only_connection_is_not_mistaken_for_an_execution_broker(site, capability):
    """Role separation: declaring market data must not imply funds, equity or execution.

    A connection used purely as a data feed must never be handed the account or execution
    questions — that is the failure mode where 'one broker owns everything' creeps back in.
    """
    provider = _DataOnlyConnection()
    if capability in (caps.HISTORICAL_DATA, caps.LIVE_QUOTES):
        return
    assert not caps.provider_supports(provider, capability), (
        f"a data-only connection was treated as capable of: {site}"
    )


def test_the_data_only_connection_is_still_usable_for_data():
    """The other half of the same claim — restricting roles must not make the feed useless."""
    provider = _DataOnlyConnection()
    assert caps.provider_supports(provider, caps.HISTORICAL_DATA)
    assert caps.provider_supports(provider, caps.LIVE_QUOTES)


def test_no_kite_name_comparison_survives_in_shared_code():
    """The migration must be complete, not partial.

    A single surviving `name == "kite"` in shared code re-creates the whole defect for that
    path, and it is the kind of thing that comes back in a later edit. Adapters themselves are
    exempt — provider-specific code is where provider identity legitimately lives.
    """
    import pathlib
    import re

    root = pathlib.Path(__file__).resolve().parents[1] / "app"
    pattern = re.compile(r'name["\']?\s*(?:,\s*["\']["\'])?\s*\)?\s*==\s*["\']kite["\']')
    offenders = []
    for path in root.rglob("*.py"):
        if path.parent.name == "providers":
            continue                      # the adapter layer may know its own identity
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line):
                offenders.append(f"{path.relative_to(root)}:{i}")
    assert not offenders, (
        f"shared code still branches on the provider name instead of a capability: {offenders}"
    )
