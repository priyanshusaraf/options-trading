"""What a money record says about which strategy traded it must be what actually traded it.

L1.2 canonicalised execution *selection* authority: every strategy the engine runs now comes
from `execution_binding.bind`. This is the other half — execution *attribution*.

The defect it closes: selection went through the binding while the `strategy_key` stamped onto
a position came from `self.strategy_keys.get(key)`, the raw instrument assignment. Those two
disagree in exactly the case the fail-safe fallback exists for. An instrument assigned a key
the registry can no longer resolve keeps trading — deliberately, so one stale config row
cannot stop the book — but it trades the *default*, while the position and every trade row
descending from it claimed the key that failed to resolve. Silent misattribution of executing
logic onto a money record is the failure the fail-closed/fail-safe registry split was written
to prevent, surviving in the one place nothing checked.

The five identities this file keeps apart, because collapsing them is how the defect happened:

| identity | where it lives | what it means |
|---|---|---|
| requested assignment | `instrument_state.strategy_key` | what somebody configured |
| executed strategy | `positions.strategy_key`, `trades.strategy_key` | what actually produced the trade |
| graph content identity | `graph_versions` | the immutable logic, if any |
| deployment identity | `deployments.(strategy_key, strategy_version)` | which book, at which version |
| execution authority | `AUTHORITY_BY_SOURCE` | whether that source may trade at all |

Nothing here changes which strategy executes, the signal, the order, the fill, the sizing, the
routing, the exits, reconciliation, risk, or authority. Only the recorded identity changes,
and only where it was wrong.
"""
from __future__ import annotations

import pytest
from unittest.mock import patch

from app.core import paper_authority
from app.core import execution_binding as binding
from app.core.instruments import all_instruments
from app.db.models import LEGACY_DEPLOYMENT_ID, LEGACY_OWNER_ID, InstrumentState
from app.db.session import SessionLocal, init_db
from app.engine.runner import EngineRunner
from app.providers.mock import MockProvider
from app.strategy.registry import DEFAULT_STRATEGY_KEY
from tests.admitted_entry import persist_admitted_entry

STALE = "a_strategy_that_was_withdrawn"


@pytest.fixture(autouse=True)
def pin_the_shared_provider():
    """Start every test at the mock provider's opening cursor, and put it back afterwards.

    The provider is a **process-wide singleton** and its cursor is global market time.
    Both halves matter, and each was learned from a red run:

    * **Restore**, because these tests tick a runner hundreds of times to reach a fill,
      which drags every later test in the suite to different prices — two unrelated files
      went red that way.
    * **Set**, because by the time this file runs the suite has already advanced the
      cursor, sometimes to within a few bars of the end. `advance()` stops at `n - 1`, so
      no new bar prints, no signal fires, and every test here fails for want of a fill
      while passing perfectly in isolation.

    Restoring alone looks like the whole fix and is only half of it. State the precondition
    rather than inheriting whatever the previous file left behind.
    """
    from app.providers.factory import get_provider

    provider = get_provider()
    was = getattr(provider, "_cursor", None)
    if was is not None:
        provider._cursor = min(160, provider.n - 1)   # MockProvider's own opening cursor
    yield
    if was is not None:
        provider._cursor = was


def _tradable_keys(n: int = 3) -> list[str]:
    """Mock instruments cheap enough that a 5–8k margin buys at least one share, so the
    dust floor does not skip every signal. Copied in spirit from `test_engine_intraday`;
    an attribution test that never opens a position proves nothing."""
    prov = MockProvider()
    out = []
    for inst in all_instruments():
        price = prov._candles[inst.key][prov._cursor].close
        if 100.0 <= price <= 1500.0:
            out.append(inst.key)
        if len(out) >= n:
            break
    return out


def _intraday_runner(assigned: str | None) -> tuple[EngineRunner, list[str]]:
    init_db(reset=True)
    keys = _tradable_keys()
    assert keys, "expected at least one affordably-priced mock instrument"
    with SessionLocal() as session:
        for key in keys:
            row = (session.get(InstrumentState, (LEGACY_OWNER_ID, key))
                   or InstrumentState(owner_id=LEGACY_OWNER_ID, instrument_key=key))
            row.enabled = True
            row.product = "equity_intraday"
            row.strategy_key = assigned          # straight to the table: a stale row is
            session.add(row)                     # exactly what no setter would let you write
        session.commit()

    runner = EngineRunner(owner_id="owner", broker_account_id="account.default")
    runner.armed = True
    runner.params["intraday_enabled"] = True
    runner.params["notify_enabled"] = False
    return runner, keys


def _admit(runner: EngineRunner, keys: list[str]) -> dict[str, str]:
    """Make one immutable graph authoritative for these fixture instruments."""
    admission = persist_admitted_entry(runner.broker.s, owner_id=runner.owner_id)
    with runner._session() as session:
        rows = [paper_authority.stage(
            session, project_id="test.admission.4c1029697ee358715d3a14a2",
            graph_identifier="test.strategy.expanding_z_impulse", graph_version=1,
            deployment_id=LEGACY_DEPLOYMENT_ID, instrument_key=key, interval="30minute",
            owner_id=runner.owner_id, broker_account_id=runner.broker_account_id)
            for key in keys]
        session.commit()
    decision = {
        "project_id": "test.admission.4c1029697ee358715d3a14a2",
        "graph_identifier": "test.strategy.expanding_z_impulse", "graph_version": 1,
        "content_address": admission["graph_address"],
        "admission_address": admission["admission_address"], "decision": "approved",
    }
    with runner._session() as session:
        with patch.object(paper_authority, "verified_decision", return_value=decision):
            for row in rows:
                paper_authority.activate(
                    session, row.id, revision=row.revision, owner_id=runner.owner_id,
                    broker_account_id=runner.broker_account_id)
        session.commit()
    assert runner.refresh_paper_authority() == len(keys)
    return admission


def _admitted_intraday_runner(assigned: str | None = None):
    runner, keys = _intraday_runner(assigned)
    return runner, keys, _admit(runner, keys)


def _run_until_open(runner: EngineRunner, ticks: int = 300):
    """Tick until the intraday segment holds a position, and return it."""
    for _ in range(ticks):
        runner.tick()
        held = [p for p in runner.broker.open_positions()
                if p.segment == "equity_intraday"]
        if held:
            return held[0]
        runner.provider.advance()
    return None


# ── legacy requested facts remain distinct from admitted execution authority ───

@pytest.mark.parametrize("assigned", [None, DEFAULT_STRATEGY_KEY, "expanding_z_v4", STALE])
def test_a_legacy_assignment_is_preserved_but_cannot_open_new_exposure(assigned):
    """A handwritten legacy assignment is requested state, never entry authority."""
    runner, keys = _intraday_runner(assigned)

    assert _run_until_open(runner) is None
    assert runner.broker.open_positions() == []
    with SessionLocal() as session:
        assert session.get(InstrumentState, (LEGACY_OWNER_ID, keys[0])).strategy_key == assigned
    assert runner.strategy_keys.get(keys[0]) == assigned


# ── admitted binding attribution ───────────────────────────────────────────────

def test_an_admitted_binding_stamps_its_exact_identity_and_receipt():
    """The position records the immutable IR binding that produced its signal."""
    runner, _, admission = _admitted_intraday_runner(STALE)
    position = _run_until_open(runner)

    assert position is not None, "no intraday position opened — the test proves nothing"
    executed = runner.executed_binding[position.instrument_key]
    assert position.strategy_key == executed.strategy_key == admission["strategy_key"]
    assert position.strategy_version == executed.strategy_version == admission["strategy_version"]
    assert position.admission_address == executed.admission_address == admission["admission_address"]


def test_the_trade_row_carries_the_same_admitted_identity_as_the_position():
    """Attribution has to survive into the money record. `positions` is working state;
    `trades` is what an audit reads."""
    from sqlalchemy import select

    from app.db.models import Trade

    runner, _, admission = _admitted_intraday_runner(STALE)
    position = _run_until_open(runner)
    assert position is not None

    # A trade row is written at the CLOSE, from `pos.strategy_key`. Closed directly rather
    # than by ticking to an exit: which exit fires and when is not this test's subject, and
    # waiting for one makes the assertion depend on the mock's price path.
    runner.broker.close_equity_position(position, position.entry_premium, "TARGET",
                                        runner.provider.now())
    runner.broker.commit()

    with SessionLocal() as session:
        rows = list(session.scalars(
            select(Trade).where(Trade.segment == "equity_intraday")))
    assert rows, "no trade rows written — the round trip never closed"
    assert {r.strategy_key for r in rows} == {admission["strategy_key"]}
    assert {r.strategy_version for r in rows} == {admission["strategy_version"]}
    assert {r.admission_address for r in rows} == {admission["admission_address"]}


def test_restarting_the_engine_preserves_admitted_attribution():
    """The identity is persisted at the fill, not recomputed on read — a later config
    change must not retroactively rewrite what a past trade claims to have run."""
    runner, keys, admission = _admitted_intraday_runner(STALE)
    position = _run_until_open(runner)
    assert position is not None

    with SessionLocal() as session:
        row = session.get(InstrumentState, (LEGACY_OWNER_ID, keys[0]))
        row.strategy_key = "expanding_z_v4"      # reassign after the fact
        session.commit()

    reborn = EngineRunner(owner_id="owner", broker_account_id="account.default")
    held = [p for p in reborn.broker.open_positions()
            if p.instrument_key == position.instrument_key]
    assert held and held[0].strategy_key == admission["strategy_key"]
    assert held[0].strategy_version == admission["strategy_version"]
    assert held[0].admission_address == admission["admission_address"]


def test_the_executed_identity_comes_from_the_binding_not_a_second_resolution(monkeypatch):
    """Requirement: no second resolver, and no re-resolution at the write site. The
    attribution must be the identity of the strategy whose output produced *this* trade —
    captured when the signal was produced, not looked up again later, because the
    assignment can change between the two and the trade would then name logic that never
    ran."""
    runner, keys, admission = _admitted_intraday_runner("expanding_z_v4")

    resolutions = []
    real = binding.bind
    monkeypatch.setattr(binding, "bind",
                        lambda **kw: (resolutions.append(kw["instrument_key"]), real(**kw))[1])
    position = _run_until_open(runner)

    assert position is not None
    assert position.strategy_key == admission["strategy_key"]
    assert position.strategy_version == admission["strategy_version"]
    assert position.admission_address == admission["admission_address"]
    # The binding is resolved on the signal path and carried; the entry path adds no
    # resolutions of its own beyond the instruments the scan already covered.
    assert set(resolutions) <= set(runner.enabled)


def test_a_refused_binding_produces_no_position_and_no_attribution(monkeypatch):
    """A refusal must not be able to open anything. The scan skips a refused instrument —
    and must also drop its stale state, or the entry path would open on the previous
    tick's signal and stamp an identity nothing authorised."""
    from app.strategy.registry import _REGISTRY, strategy_keys

    from app.engine import ir_shadow

    runner, keys = _intraday_runner(None)
    strategy_keys()
    graph = ir_shadow.pairing_for("expanding_z_v4").adapter()
    monkeypatch.setitem(_REGISTRY, graph.key, graph)

    # Let the scan build state normally, then refuse every instrument.
    runner.scan_signals()
    for key in list(runner.enabled):
        runner.strategy_keys[key] = graph.key
    runner.scan_signals()

    assert runner.state == {}, "a refused instrument kept its previous signal state"
    runner.process_entries()
    assert runner.broker.open_positions() == []


def test_a_shadow_strategy_is_never_stamped_onto_a_money_record(monkeypatch):
    """The shadow lane evaluates a graph on the same frame as the authoritative strategy.
    Its key must never reach a position, whatever the observation said."""
    runner, _, admission = _admitted_intraday_runner("expanding_z_v4")
    monkeypatch.setitem(runner.params, "ir_shadow_enabled", True)
    for key in list(runner.enabled):
        runner.strategy_keys[key] = "expanding_z_v4"

    position = _run_until_open(runner)
    assert position is not None
    assert position.strategy_key == admission["strategy_key"]
    assert position.strategy_version == admission["strategy_version"]
    assert position.admission_address == admission["admission_address"]
    assert runner.shadow_metrics.snapshot()["bars_observed"] > 0


def test_the_executed_identity_is_the_one_that_produced_the_signal_not_the_latest():
    """The reason the binding is *carried* from the scan rather than resolved at the fill.

    Selection and the fill are separate moments, and the assignment can change between
    them — a route call, a watchlist activation, a config reload. Resolving again at the
    fill would attribute the trade to whatever is configured by then, which is not what
    produced the signal. Here the assignment is changed after the scan and before the
    entry, and the position must still name what actually ran.
    """
    runner, keys, admission = _admitted_intraday_runner("expanding_z_v4")

    # The reassignment has to land *between* the scan and the entry. An earlier version of
    # this test flipped the assignment from inside `open_equity_position`, which reads
    # convincingly and proves nothing: the attribution argument is evaluated before the
    # call, so re-resolving at the write site still produced the right answer and the
    # mutation stayed green. The harness caught it. Driving the two halves of the tick
    # separately is what actually exercises the window.
    def reassign(to: str) -> None:
        for key in keys:
            runner.strategy_keys[key] = to

    position = None
    for _ in range(300):
        reassign("expanding_z_v4")          # what is configured when the signal is produced
        runner.scan_signals()
        reassign(DEFAULT_STRATEGY_KEY)      # ...and what is configured when it fills
        runner.process_entries()
        held = [p for p in runner.broker.open_positions()
                if p.segment == "equity_intraday"]
        if held:
            position = held[0]
            break
        runner.provider.advance()

    assert position is not None, "no position opened — the test proves nothing"
    scanned = runner.executed_binding[position.instrument_key]
    assert position.strategy_key == scanned.strategy_key == admission["strategy_key"]
    assert position.strategy_version == scanned.strategy_version == admission["strategy_version"]
    assert position.admission_address == scanned.admission_address == admission["admission_address"]


def test_the_futures_entry_path_attributes_the_admitted_binding(monkeypatch, give_futures_price_feed):
    """The futures write path carries the same exact admitted identity as intraday."""
    init_db(reset=True)
    runner = EngineRunner(owner_id="owner", broker_account_id="account.default")
    runner.armed = True
    cap = runner.broker.capital()
    cap.initial_capital = 1_000_000.0
    cap.cash = 1_000_000.0
    runner.broker.s.commit()
    runner.params = {**runner.params, "index_futures_enabled": True,
                     "index_futures_max_positions": 1,
                     "index_futures_max_margin": 250_000.0,
                     "index_futures_min_margin": 50_000.0,
                     "notify_enabled": False}
    runner.strategy_keys["NIFTY"] = STALE
    admission = _admit(runner, ["NIFTY"])
    give_futures_price_feed(runner.provider,
                           lambda inst, expiry: 24_000.0)
    runner.publish_signal("NIFTY", runner._binding_for("NIFTY"),
                          {"long_entry": True, "short_entry": False, "close": 24_000.0})

    import datetime as dt
    runner._process_futures_entries(dt.datetime(2026, 8, 3, 11, 0))

    held = [p for p in runner.broker.open_positions() if p.segment == "index_futures"]
    assert held, "no futures position opened — the test proves nothing"
    assert held[0].strategy_key == admission["strategy_key"]
    assert held[0].strategy_version == admission["strategy_version"]
    assert held[0].admission_address == admission["admission_address"]
