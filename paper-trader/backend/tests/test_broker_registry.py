"""The registry must not be able to lie about what this build supports.

A broker registry is the most attractive possible home for this codebase's defining defect — a
mechanism that looks wired and is not. A row saying `SUPPORTED` is read by a human as "I can
trade there"; nothing about writing that row makes it true. These tests are what makes the
difference between a claim and a fact, in both directions:

  * a `SUPPORTED` broker whose adapter is missing, unimportable, or absent from the conformance
    suite fails the build;
  * a `PLANNED` broker that has quietly grown a working adapter also fails, because a broker
    that works while the registry calls it unbuilt is a capability nobody can select and nobody
    knows exists — the same unconsumed-mechanism shape, arriving from the other side.
"""
from __future__ import annotations

import pytest

from app.providers import brokers
from app.providers.base import MarketDataProvider
from app.providers.brokers import BROKERS, BrokerNotSupported, Status, spec


def test_every_key_is_unique_and_lowercase():
    """`key` is written into every `ExecutionIntent` and matched by restart recovery, so it is an
    identifier rather than a label. Two rows sharing one, or one differing only in case, makes
    recovery ambiguous about which connection's live orders it may adopt."""
    keys = [b.key for b in BROKERS]
    assert len(keys) == len(set(keys)), f"duplicate broker keys: {keys}"
    assert all(k == k.strip().lower() and k for k in keys), keys


def test_every_broker_names_its_documentation():
    """Load-bearing, not decorative. No adapter in this tree may be written from memory of an
    API — an endpoint guessed from a similar broker's shape returns valid-looking prices for the
    wrong instrument, and nothing raises."""
    missing = [b.key for b in BROKERS if not b.docs_url.startswith("https://")]
    assert not missing, f"these brokers name no API documentation: {missing}"


@pytest.mark.parametrize("b", [b for b in BROKERS if b.status is Status.SUPPORTED],
                         ids=lambda b: b.key)
def test_a_supported_broker_really_has_an_importable_adapter(b):
    """`SUPPORTED` with a broken or absent module is the registry lying about itself."""
    assert b.data or b.venue, (
        f"{b.key} is SUPPORTED but declares neither a data adapter nor a venue — supported at "
        f"nothing is not a status, it is a typo")
    if b.data:
        cls = b.load_data()
        assert isinstance(cls, type) and issubclass(cls, MarketDataProvider), cls
    if b.venue:
        assert isinstance(b.load_venue(), type)


@pytest.mark.parametrize("b", [b for b in BROKERS if b.status is Status.PLANNED],
                         ids=lambda b: b.key)
def test_a_planned_broker_is_refused_rather_than_half_wired(b):
    """The failure this prevents is silent: a half-registered broker that falls through to the
    configured provider trades the WRONG ACCOUNT, and one that falls through to the mock routes
    real orders at a synthetic market."""
    assert b.data is None and b.venue is None, (
        f"{b.key} is PLANNED but points at an adapter — if it works, mark it SUPPORTED and give "
        f"it a conformance case; if it does not, remove the pointer")
    with pytest.raises(BrokerNotSupported) as e:
        brokers.data_adapter(b.key)
    assert b.key in str(e.value) and "planned" in str(e.value)
    with pytest.raises(BrokerNotSupported):
        brokers.venue_adapter(b.key)


def test_a_supported_data_adapter_is_covered_by_the_conformance_contract():
    """"Supported" means held to the contract, not merely importable.

    Without this, adding a broker to the registry would be enough to make the claim, and the
    adapter's semantics — bar ordering, refusal vocabulary, capability honesty — would never run.
    """
    from tests.test_provider_conformance import CASE_FIXTURES
    covered = {cls for cls in CASE_FIXTURES}
    missing = []
    for b in BROKERS:
        if b.status is not Status.SUPPORTED or not b.data:
            continue
        if b.load_data() not in covered:
            missing.append(b.key)
    assert not missing, (
        f"these brokers are SUPPORTED but have no conformance case: {missing}. A broker that "
        f"has not been run through the contract has not passed it.")


def test_an_unknown_broker_is_refused_with_the_list_of_real_ones():
    with pytest.raises(BrokerNotSupported) as e:
        spec("zeroda")           # the typo that matters
    assert "kite" in str(e.value), "the refusal must say what IS available"


def test_the_selectable_set_is_exactly_the_supported_set():
    assert {b.key for b in brokers.supported()} == {
        b.key for b in BROKERS if b.status is Status.SUPPORTED}


def test_execution_is_narrower_than_data_and_that_is_the_point():
    """Data and execution are separate roles. Upstox serving prices while placing no orders is
    not an incomplete adapter — it is the configuration the connection seam exists for, and the
    registry has to be able to express it."""
    assert brokers.data_adapter("upstox") is not None
    with pytest.raises(BrokerNotSupported) as e:
        brokers.venue_adapter("upstox")
    assert "cannot place orders" in str(e.value)
    assert brokers.venue_adapter("kite") is not None


def test_the_registry_and_the_provider_factory_agree_on_what_exists():
    """Two places name adapters — the registry and `provider_named`. If they disagree, one of
    them is wrong and the operator cannot tell which. `mock` and `replay` are deliberately
    absent from the registry: they are not brokers, and listing them would make "supported
    brokers" a set the user could see a synthetic market in."""
    from app.providers.factory import provider_named
    for b in brokers.supported():
        if not b.data:
            continue
        assert isinstance(provider_named(b.key), b.load_data()), (
            f"provider_named({b.key!r}) did not build the adapter the registry names")


@pytest.mark.parametrize("b", BROKERS, ids=lambda b: b.key)
def test_a_venue_and_its_builder_are_declared_together(b):
    """`venue` and `venue_builder` must both be present or both absent.

    They answer the same question to two different audiences and nothing kept them in step:

      * `venue` is what a READER is told — `venue_adapter()` refuses without it, and
        `GET /api/brokers` derives `roles.execution` from it;
      * `venue_builder` is what `broker_factory` actually CALLS through
        `registry.build_live_venue` to construct a live order path.

    A row with a builder and no venue tells every reader "this broker cannot place orders"
    while the one place that decides will happily build one for it. A row with a venue and no
    builder is the reverse: it advertises execution and refuses at 09:15. Both are the registry
    disagreeing with itself, which is the single failure this module exists to make impossible —
    its own docstring says a row here is a claim and this file is what makes it a fact.
    """
    assert (b.venue is None) == (b.venue_builder is None), (
        f"broker {b.key!r} declares venue={b.venue!r} and venue_builder={b.venue_builder!r}. "
        f"Declare both or neither: readers ask `venue` and broker_factory calls "
        f"`venue_builder`, so one without the other is the registry contradicting itself.")


def test_dhan_execution_really_refuses_a_server_trigger():
    """The registry's most consequential capability claim, checked against the venue itself.

    Dhan has no GTT equivalent. Options positions take a SERVER_TRIGGER, so an options
    deployment cannot run on Dhan execution — and the failure mode that matters is not a refusal
    but a SUBSTITUTION: a venue that quietly rested a stop order instead would leave the caller
    believing it holds exchange-side protection it does not have.

    Asserted against `DhanVenue` rather than the note, because a note is prose and this is the
    difference between a protected position and an unprotected one. The registry's Dhan notes
    previously claimed the opposite of the row they annotated, which is why capability claims
    belong in machine-checked fields.
    """
    from app.engine.broker_protocol import ProtectiveStopKind
    from app.providers.brokers import venue_adapter

    venue_cls = venue_adapter("dhan")
    assert ProtectiveStopKind.SERVER_TRIGGER not in venue_cls.PROTECTIVE_KINDS
    assert ProtectiveStopKind.RESTING_STOP in venue_cls.PROTECTIVE_KINDS


def test_kite_execution_still_accepts_both_protective_shapes():
    """The contrast that makes the test above meaningful: a venue CAN declare both, so Dhan's
    narrower set is a real property of Dhan and not an artefact of how the field is read."""
    from app.engine.broker_protocol import ProtectiveStopKind
    from app.providers.brokers import venue_adapter

    kinds = venue_adapter("kite").PROTECTIVE_KINDS
    assert {ProtectiveStopKind.SERVER_TRIGGER, ProtectiveStopKind.RESTING_STOP} <= set(kinds)


@pytest.mark.parametrize("b", [b for b in BROKERS if b.venue], ids=lambda b: b.key)
def test_every_execution_venue_can_be_asked_what_it_protects(b):
    """`PROTECTIVE_KINDS` is on the `ExecutionVenue` protocol, so every venue answers it.

    A venue that cannot be asked forces the caller to already know — which means branching on
    the broker's name, the one branch `.claude/rules/providers-brokers.md` forbids under
    `app/engine/`. This is the conformance half of that rule: adding a third venue without the
    declaration fails here rather than at the first stop placement.
    """
    from app.engine.broker_protocol import ProtectiveStopKind
    from app.providers.brokers import venue_adapter

    kinds = getattr(venue_adapter(b.key), "PROTECTIVE_KINDS", None)
    assert isinstance(kinds, frozenset) and kinds, (
        f"{b.key} declares a venue but not PROTECTIVE_KINDS, so no caller can ask it which "
        f"protective shapes it supports without knowing which broker it is")
    assert kinds <= set(ProtectiveStopKind), f"{b.key} declares a protective kind that is not one"
