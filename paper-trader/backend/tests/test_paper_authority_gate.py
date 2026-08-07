"""The authority gate, with `(ir_graph, paper, authoritative)` granted.

The grant is necessary and **deliberately not sufficient**. If membership in `GRANTS` were
the whole test, then registering a graph adapter — which this slice must do, so the
strategy is resolvable — would make `POST /api/instruments/NIFTY/strategy {ir.…}` an
authoritative paper assignment. That is the hazard
`test_binding_a_registered_graph_to_an_instrument_is_refused_not_silently_shadowed` has
pinned since L1.2, and it must survive the grant.

So an IR binding must additionally prove two things at the point of use, both recomputed
rather than read off the binding:

* it was decided by a verified paper-authority deployment (`origin`), not by an
  instrument row, a watchlist, a default or a fallback;
* the strategy the registry resolves *right now* has exactly the content address the
  deployment approved.

The second is what makes a graph edit non-inheriting: the adapter's version IS the graph's
content address, so an edited graph resolves to a different address and the binding that
named the old one stops matching.
"""
from __future__ import annotations

import pytest

from app.core import execution_binding as binding
from app.core.execution_book import LIVE, PAPER, configured_execution_mode
from app.db.models import LEGACY_DEPLOYMENT_ID
from app.db.session import init_db
from app.strategy.registry import DEFAULT_STRATEGY_KEY


def setup_function() -> None:
    init_db(reset=True)


@pytest.fixture
def registered_graph(monkeypatch):
    """The graph adapter, resolvable by its stable key — as an active paper deployment
    makes it. Returned so tests can name its exact content address."""
    from app.engine import ir_shadow
    from app.strategy.registry import _REGISTRY

    strategy = ir_shadow.pairing_for("expanding_z_v4").adapter()
    monkeypatch.setitem(_REGISTRY, strategy.key, strategy)
    return strategy


#: `None` is a value this test needs to pass explicitly, so "not supplied" needs its own.
_UNSET = object()


def _paper_binding(strategy, *, origin=None, version=_UNSET, mode=None):
    return binding.ExecutionBinding(
        deployment_id=LEGACY_DEPLOYMENT_ID, instrument_key="NIFTY",
        strategy_key=strategy.key,
        strategy_version=strategy.version if version is _UNSET else version,
        source=binding.SOURCE_IR_GRAPH, authority=binding.AUTHORITATIVE,
        execution_mode=configured_execution_mode() if mode is None else mode,
        origin=binding.ORIGIN_PAPER_AUTHORITY if origin is None else origin,
        reason="paper authority")


class TestTheGrant:
    def test_ir_graph_is_granted_in_paper_mode(self):
        assert (binding.SOURCE_IR_GRAPH, PAPER, binding.AUTHORITATIVE) in binding.GRANTS

    def test_ir_graph_is_not_granted_in_live_mode(self):
        """The whole point of the pair. Live IR authority is a separate owner decision and
        this slice must not be able to imply it."""
        assert (binding.SOURCE_IR_GRAPH, LIVE, binding.AUTHORITATIVE) not in binding.GRANTS

    def test_the_coarse_source_map_still_refuses_free_assignment(self):
        """`AUTHORITY_BY_SOURCE` answers a different question — "may this source be
        assigned to an instrument by anyone who can call a route" — and the answer for a
        graph is still no. Collapsing the two maps is how the write-side gate would open."""
        assert binding.AUTHORITY_BY_SOURCE[binding.SOURCE_IR_GRAPH] == binding.SHADOW
        with pytest.raises(binding.AuthorityNotGranted):
            binding.assert_may_execute("ir.strategy.expanding_z_impulse")


class TestTheGrantIsNotSufficientOnItsOwn:
    def test_a_paper_authority_binding_executes(self, registered_graph):
        assert binding.strategy_for_execution(
            _paper_binding(registered_graph)).key == registered_graph.key

    def test_an_instrument_assignment_of_the_same_graph_is_still_refused(self,
                                                                        registered_graph):
        """The L1.2 hazard, re-proved under the grant. Same key, same mode, same registry
        — only the deciding layer differs, and that is what decides."""
        for origin in (binding.ORIGIN_INSTRUMENT, binding.ORIGIN_DEFAULT,
                       binding.ORIGIN_FALLBACK, binding.ORIGIN_DEPLOYMENT):
            with pytest.raises(binding.AuthorityNotGranted):
                binding.strategy_for_execution(
                    _paper_binding(registered_graph, origin=origin))

    def test_a_shadow_deployment_does_not_become_authoritative_by_existing(self,
                                                                          registered_graph):
        """Safety proof 3. A shadow binding names the same graph and the same instrument;
        the only thing it lacks is the paper-authority decision, and that must be enough
        to refuse it."""
        shadow = binding.resolve_shadow_binding(registered_graph.key, "NIFTY")
        assert shadow.authority == binding.SHADOW
        with pytest.raises(binding.AuthorityNotGranted):
            binding.strategy_for_execution(shadow)


class TestExactVersionAtTheMomentOfUse:
    def test_a_binding_naming_a_stale_content_address_fails_closed(self, registered_graph):
        """Safety proof 5. The address is recomputed from what the registry resolves now,
        so a deployment that approved different bytes cannot execute these."""
        with pytest.raises(binding.AuthorityNotGranted):
            binding.strategy_for_execution(
                _paper_binding(registered_graph, version="sha256:" + "0" * 64))

    def test_a_binding_with_no_content_address_fails_closed(self, registered_graph):
        for empty in (None, ""):
            with pytest.raises(binding.AuthorityNotGranted):
                binding.strategy_for_execution(
                    _paper_binding(registered_graph, version=empty))

    def test_an_edited_graph_does_not_inherit_authority(self, monkeypatch):
        """Safety proof 4, stated as the platform means it: authority is bound to bytes.
        Re-registering the same *key* with a differently-addressed adapter is exactly what
        publishing a new graph version does to the registry."""
        from app.engine import ir_shadow
        from app.strategy.registry import _REGISTRY

        approved = ir_shadow.pairing_for("expanding_z_v4").adapter()
        monkeypatch.setitem(_REGISTRY, approved.key, approved)
        bound = _paper_binding(approved)
        assert binding.strategy_for_execution(bound).key == approved.key

        edited = ir_shadow.pairing_for("expanding_z_v4").adapter()
        edited.pin_version("sha256:" + "1" * 64)
        monkeypatch.setitem(_REGISTRY, edited.key, edited)

        with pytest.raises(binding.AuthorityNotGranted):
            binding.strategy_for_execution(bound)


class TestModeIsResolvedNotAsserted:
    def test_a_binding_claiming_paper_in_a_live_process_is_refused(self, registered_graph,
                                                                   monkeypatch):
        """Safety proof 2 at the gate. The binding says paper; the process says live; the
        gate believes the process."""
        from app.core import execution_binding as mod

        monkeypatch.setattr(mod, "configured_execution_mode", lambda: LIVE)
        with pytest.raises(binding.AuthorityNotGranted):
            binding.strategy_for_execution(_paper_binding(registered_graph, mode=PAPER))

    def test_a_binding_claiming_live_is_refused_too(self, registered_graph):
        with pytest.raises(binding.AuthorityNotGranted):
            binding.strategy_for_execution(_paper_binding(registered_graph, mode=LIVE))

    def test_a_handwritten_strategy_is_unaffected_by_any_of_this(self):
        """Safety proof 17 at the gate: nothing above may narrow what already executes."""
        plain = binding.bind(deployment_id=LEGACY_DEPLOYMENT_ID, instrument_key="NIFTY",
                             deployment_pin=None, assigned_key=DEFAULT_STRATEGY_KEY)
        assert binding.strategy_for_execution(plain).key == DEFAULT_STRATEGY_KEY
