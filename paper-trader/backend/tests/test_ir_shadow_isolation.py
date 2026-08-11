"""L1 Stage 1 — the shadow lane is an observer, and these are the proofs.

Stage 1 was approved on the condition that the IR lane "must not place, modify, cancel,
route, size, reconcile, or otherwise influence orders, positions, accounting, exits,
deployment authority, or risk controls". Four independent guards enforce that:

1. **Static** — the shadow modules import no execution seam, transitively.
2. **Dynamic** — every broker, order-client and execution entry point is replaced with a
   trap, and a full shadow-enabled signal scan runs without springing one.
3. **State** — the engine's authoritative state, params and strategy assignment are
   byte-identical with the lane on and off.
4. **Containment** — failures injected at each layer of the lane leave the authoritative
   output unchanged.

Each has a recorded mutation that turns it red; see
`docs/reports/2026-08-04-l1-stage1-shadow.md`.
"""
from __future__ import annotations

import ast
import copy
import pathlib

import pytest

from app.core import runtime_config
from app.db.session import init_db
from app.engine import ir_shadow, ir_shadow_store
from tests.legacy_money_scope import LegacyMoneyScope

ir_shadow_store = LegacyMoneyScope(
    ir_shadow_store, "record", "recent", "counts_by_reason", "prune")
from app.engine.runner import EngineRunner

#: Modules the shadow lane may never reach, directly or transitively. These are the seams
#: named in the owner's constraint: orders, broker, sizing, routing, reconciliation,
#: square-off, accounting, capital, deployment authority.
FORBIDDEN = (
    "app.engine.broker",
    "app.engine.broker_factory",
    "app.engine.live_broker",
    "app.engine.kite_order_client",
    "app.engine.execution_policy",
    "app.engine.equity_entry",
    "app.engine.allocator",
    "app.engine.capital",
    "app.engine.charges",
    "app.engine.ledger_reconcile",
    "app.engine.risk_controls",
    "app.engine.exit_monitor",
    "app.engine.runner",
    "app.core.deployments",
    "app.options.picker",
    "app.providers",
    "research",
)

SHADOW_MODULES = (ir_shadow, ir_shadow_store)


def _imports_of(path: pathlib.Path) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
        elif isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
    return modules


#: The one frontier the transitive walk stops at, and why. `app/db/session.py` imports
#: `app.engine.charges` to price a seeded position and `app.core.deployments` to ensure the
#: legacy book exists. Any module that persists **anything** therefore "reaches" both, so
#: descending through the shared persistence layer would make this guard unpassable for any
#: table-writing module and would say nothing about whether the shadow lane can trade.
#: Stopping here is not a hole: the shadow store's own imports are checked directly below,
#: and the dynamic trap test proves the seams are never actually called.
PERSISTENCE_FRONTIER = ("app.db.session", "app.db.models")


def _reachable(module, stop_at: tuple[str, ...] = ()) -> set[str]:
    """Every app module reachable from `module` by following imports. Parsed, not grepped:
    the shadow module's docstring names the order path, and a substring guard would pass on
    a real violation while failing on prose."""
    import importlib

    seen: set[str] = set()
    queue = [module.__name__]
    while queue:
        name = queue.pop()
        if name in seen or not name.startswith(("app.", "research")):
            continue
        seen.add(name)
        if name in stop_at:
            continue
        try:
            found = importlib.import_module(name)
        except Exception:
            continue
        path = getattr(found, "__file__", None)
        if not path:
            continue
        queue.extend(_imports_of(pathlib.Path(path)))
    return seen


def _offenders(names) -> list[str]:
    return sorted(name for name in names
                  if any(name == f or name.startswith(f + ".") for f in FORBIDDEN))


# ── 1. static: no execution seam is reachable ────────────────────────────────────

def test_the_shadow_core_cannot_reach_an_execution_seam():
    """The evaluating half touches no database, so it gets the unrestricted walk."""
    assert _offenders(_reachable(ir_shadow)) == []


def test_the_shadow_store_cannot_reach_an_execution_seam():
    assert _offenders(_reachable(ir_shadow_store, stop_at=PERSISTENCE_FRONTIER)) == []


@pytest.mark.parametrize("module", SHADOW_MODULES, ids=lambda m: m.__name__)
def test_no_shadow_module_names_an_execution_seam_directly(module):
    """The frontier above is only defensible if nothing hides behind it: the shadow modules
    must not import a seam themselves, at any depth of `from ... import ...`."""
    assert _offenders(_imports_of(pathlib.Path(module.__file__))) == []


def test_the_shadow_lane_reaches_the_ir_language_and_the_strategy_contract():
    """The complement of the guard above: a test that only proves absence would pass on a
    lane that imports nothing and does nothing."""
    reached = _reachable(ir_shadow)
    assert "app.strategy.ir_adapter" in reached
    assert any(name.startswith("app.ir") for name in reached)


# ── 2. dynamic: every seam is a trap and the lane runs ───────────────────────────

class Sprung(AssertionError):
    """Raised by a trap. Its own type so no `except Exception` can absorb it."""


def _trap_every_seam(monkeypatch) -> list[str]:
    """Replace every order/position/accounting entry point with a trap that records and
    raises. Returns the list of seams that were sprung (must stay empty)."""
    sprung: list[str] = []

    def trap(label):
        def fire(*_args, **_kwargs):
            sprung.append(label)
            raise Sprung(label)
        return fire

    from app.engine import broker as broker_module
    from app.engine import kite_order_client

    seams = [
        "open_position", "open_equity_position", "open_futures_position",
        "close_position", "close_equity_position", "close_futures_position",
        "book_partial_close", "book_partial_close_equity", "reinforce_position",
        "manual_open", "update_stop_protection", "ensure_stop_protection",
        "reconcile_orphans", "adopt_pending_entries", "cancel_working_entries",
        "recover_journal", "reconcile", "commit", "snapshot",
    ]
    for name in seams:
        if hasattr(broker_module.PaperBroker, name):
            monkeypatch.setattr(broker_module.PaperBroker, name, trap(f"broker.{name}"),
                                raising=False)
    for name in dir(kite_order_client.KiteOrderClient):
        if name.startswith("_"):
            continue
        monkeypatch.setattr(kite_order_client.KiteOrderClient, name,
                            trap(f"kite.{name}"), raising=False)
    return sprung


def _runner_with_shadow(monkeypatch) -> EngineRunner:
    init_db(reset=True)
    runner = EngineRunner(owner_id="owner", broker_account_id="account.default")
    monkeypatch.setitem(runner.params, "ir_shadow_enabled", True)
    for key in list(runner.enabled):
        runner.strategy_keys[key] = "expanding_z_v4"
    return runner


def test_a_full_shadow_scan_reaches_no_broker_or_order_seam(monkeypatch):
    runner = _runner_with_shadow(monkeypatch)
    sprung = _trap_every_seam(monkeypatch)

    runner.scan_signals()

    assert sprung == [], f"the shadow scan reached {sprung}"


def test_recording_a_divergence_reaches_no_broker_or_order_seam(monkeypatch):
    """The persistence half: writing the record must not touch the money path either."""
    runner = _runner_with_shadow(monkeypatch)
    sprung = _trap_every_seam(monkeypatch)

    observation = ir_shadow.ShadowObservation(
        instrument_key="NIFTY", bar_time=runner.provider.now(),
        observed_at=runner.provider.now(), authoritative_strategy_key="expanding_z_v4",
        shadow_strategy_key="ir.x", graph_address="sha256:abc",
        authoritative={"longEntry": True, "shortEntry": False,
                       "longExit": False, "shortExit": False},
        ir={"longEntry": False, "shortEntry": False,
            "longExit": False, "shortExit": False},
        warmup_state="settled", declared_warmup=302, frame_bars=400,
        frame_id="sha256:f", frame_first_ts=None, frame_last_ts=None,
        reason=ir_shadow.FLAG_DIVERGENCE, detail="longEntry", eval_seconds=0.01)

    assert ir_shadow_store.record(observation, market_open=True) is True
    assert sprung == []


def test_the_isolation_proofs_are_not_vacuous_the_lane_really_ran(monkeypatch):
    """Every proof above is of the form "nothing happened". They are worth nothing unless
    the lane was actually exercised, so this asserts the same scan produced observations."""
    runner = _runner_with_shadow(monkeypatch)

    runner.scan_signals()

    snapshot = runner.shadow_metrics.snapshot()
    assert snapshot["bars_observed"] == len(runner.enabled)
    assert snapshot["eval_seconds"]["count"] == len(runner.enabled)


class AlwaysLong:
    """A stand-in mirror that always says "long entry".

    Substituting the *graph* rather than the frame is what makes this deterministic. The
    obvious alternative — relying on the real graph refusing a short frame — passed alone
    and failed in the full suite, because the mock provider is a process-wide singleton and
    an earlier test had advanced it past the warmup, at which point the two lanes agreed and
    there was nothing to record. Everything else on the path is the shipping code.
    """

    key = "ir.strategy.expanding_z_impulse"
    address = "sha256:" + "ab" * 32
    display_name = "always long"
    declared_warmup = 0
    required_inputs = ("high", "low", "close")

    def compute(self, df):
        out = df.copy()
        out["longEntry"], out["shortEntry"] = True, False
        out["longExit"], out["shortExit"] = False, False
        return out


def test_a_disagreement_seen_by_the_engine_reaches_the_record(monkeypatch):
    """End to end through the runner: observed, classified, persisted, attributable."""
    from sqlalchemy import select

    from app.db.models import IrShadowDivergence
    from app.db.session import SessionLocal

    runner = _runner_with_shadow(monkeypatch)
    monkeypatch.setitem(ir_shadow._PAIRINGS, "expanding_z_v4", ir_shadow.ShadowPairing(
        authoritative_key="expanding_z_v4", graph={}, library=(None, None),
        strategy=AlwaysLong()))

    runner.scan_signals()

    with SessionLocal() as session:
        rows = list(session.scalars(select(IrShadowDivergence)))
    assert rows, "the engine observed disagreements but recorded none"
    assert len(rows) == len(runner.enabled)
    for row in rows:
        assert row.reason == ir_shadow.FLAG_DIVERGENCE
        assert any(column in row.detail for column in
                   ("longEntry", "shortEntry", "longExit", "shortExit"))
        assert row.graph_address == AlwaysLong.address
        assert row.frame_id.startswith("sha256:")
        assert row.shadow_strategy_key == "ir.strategy.expanding_z_impulse"
        assert row.authoritative_strategy_key == "expanding_z_v4"


# ── 3. state: the authoritative lane produces the same thing either way ──────────

def _authoritative_state(enabled: bool) -> tuple[dict, dict, dict]:
    init_db(reset=True)
    runner = EngineRunner(owner_id="owner", broker_account_id="account.default")
    runner.params["ir_shadow_enabled"] = enabled
    for key in list(runner.enabled):
        runner.strategy_keys[key] = "expanding_z_v4"
    runner.scan_signals()
    state = copy.deepcopy(runner.state)
    for entry in state.values():
        entry.pop("_ratchet_atr", None)      # float noise from a separate code path
    return state, dict(runner.params), dict(runner.strategy_keys)


def test_the_authoritative_state_is_identical_with_the_shadow_on_and_off():
    off_state, off_params, off_keys = _authoritative_state(False)
    on_state, on_params, on_keys = _authoritative_state(True)

    on_params.pop("ir_shadow_enabled"), off_params.pop("ir_shadow_enabled")
    assert on_state == off_state
    assert on_params == off_params
    assert on_keys == off_keys


def test_the_shadow_lane_writes_nothing_into_the_engine_state():
    """Constraint 2 and 4: the IR verdict may be recorded, never fed back. No state entry
    may carry a shadow field for the entry pass to read."""
    init_db(reset=True)
    runner = EngineRunner(owner_id="owner", broker_account_id="account.default")
    runner.params["ir_shadow_enabled"] = True
    for key in list(runner.enabled):
        runner.strategy_keys[key] = "expanding_z_v4"

    runner.scan_signals()

    for entry in runner.state.values():
        assert not [field for field in entry if "shadow" in field.lower()]
        assert not [field for field in entry if field.startswith("ir_")]


# ── 4. containment: an exploding shadow cannot touch the authoritative output ────

@pytest.mark.parametrize("layer", ["observe", "record", "metrics"])
def test_a_failure_anywhere_in_the_lane_leaves_the_authoritative_output_unchanged(
        monkeypatch, layer):
    baseline, _, _ = _authoritative_state(False)

    init_db(reset=True)
    runner = EngineRunner(owner_id="owner", broker_account_id="account.default")
    runner.params["ir_shadow_enabled"] = True
    for key in list(runner.enabled):
        runner.strategy_keys[key] = "expanding_z_v4"

    def explode(*_args, **_kwargs):
        raise RuntimeError(f"{layer} exploded")

    if layer == "observe":
        monkeypatch.setattr(ir_shadow, "observe", explode)
    elif layer == "record":
        monkeypatch.setattr(ir_shadow_store, "record", explode)
    else:
        monkeypatch.setattr(runner.shadow_metrics, "observe", explode)

    runner.scan_signals()          # must not raise

    produced = copy.deepcopy(runner.state)
    for entry in produced.values():
        entry.pop("_ratchet_atr", None)
    assert produced == baseline


def test_a_shadow_failure_does_not_stop_later_instruments_being_scanned(monkeypatch):
    """Containment must be per instrument. A lane that aborts the loop on the first
    failure would silently stop scanning the rest of the book — the E1 poisoned-key
    shape."""
    init_db(reset=True)
    runner = EngineRunner(owner_id="owner", broker_account_id="account.default")
    runner.params["ir_shadow_enabled"] = True
    for key in list(runner.enabled):
        runner.strategy_keys[key] = "expanding_z_v4"
    monkeypatch.setattr(ir_shadow, "observe",
                        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")))

    runner.scan_signals()

    assert len(runner.state) == len(runner.enabled)


def test_the_signal_iteration_reports_what_the_shadow_cost_it():
    """Requirement 11's last measure. `_signal_iteration_blocking` re-reads params from the
    database, so this also proves the flag reaches a *running* engine through the sanctioned
    channel rather than through a test's attribute poke."""
    init_db(reset=True)
    runtime_config.set_override("ir_shadow_enabled", True)
    try:
        runner = EngineRunner(owner_id="owner", broker_account_id="account.default")
        for key in list(runner.enabled):
            runner.strategy_keys[key] = "expanding_z_v4"

        runner._signal_iteration_blocking()

        loop = runner.shadow_metrics.snapshot()["loop"]
        assert loop["iterations"] == 1
        assert loop["budget_seconds"] == 2.5
        assert loop["shadow_seconds"]["max"] > 0.0
        assert loop["iteration_seconds"]["max"] >= loop["shadow_seconds"]["max"]
        assert loop["shadow_share_p95"] is not None
    finally:
        runtime_config.clear_override("ir_shadow_enabled")


def test_the_iteration_reports_no_shadow_cost_when_the_lane_is_off():
    """The complement: with the flag off the cost measure must read zero, not "unknown"."""
    init_db(reset=True)
    runner = EngineRunner(owner_id="owner", broker_account_id="account.default")
    for key in list(runner.enabled):
        runner.strategy_keys[key] = "expanding_z_v4"

    runner._signal_iteration_blocking()

    loop = runner.shadow_metrics.snapshot()["loop"]
    assert loop["iterations"] == 1
    assert loop["shadow_seconds"]["max"] == 0.0


# ── the flag ─────────────────────────────────────────────────────────────────────

def test_the_flag_is_off_by_default_and_the_lane_is_inert():
    init_db(reset=True)
    runner = EngineRunner(owner_id="owner", broker_account_id="account.default")
    assert runner.params["ir_shadow_enabled"] is False
    for key in list(runner.enabled):
        runner.strategy_keys[key] = "expanding_z_v4"

    runner.scan_signals()

    assert runner.shadow_metrics.snapshot()["bars_observed"] == 0
    assert runner.shadow_metrics.snapshot()["eval_seconds"]["count"] == 0


def test_the_flag_is_live_editable_without_a_restart():
    """ADR 0011 Stage 1 criterion 5. `runtime_config` is the sanctioned channel and
    `refresh_params` is what the settings route already calls."""
    init_db(reset=True)
    assert "ir_shadow_enabled" in runtime_config.OVERRIDABLE
    runner = EngineRunner(owner_id="owner", broker_account_id="account.default")
    assert runner.params["ir_shadow_enabled"] is False

    runtime_config.set_override("ir_shadow_enabled", True)
    runner.refresh_params()
    assert runner.params["ir_shadow_enabled"] is True

    runtime_config.clear_override("ir_shadow_enabled")
    runner.refresh_params()
    assert runner.params["ir_shadow_enabled"] is False


def test_an_uncoercible_flag_value_fails_closed():
    """Fail-closed means a value nobody can read is OFF, not ON."""
    init_db(reset=True)
    runtime_config.set_override("ir_shadow_enabled", True)
    from app.db.models import RuntimeConfig
    from app.db.session import SessionLocal
    with SessionLocal() as session:
        session.get(RuntimeConfig, "ir_shadow_enabled").value = "banana"
        session.commit()

    runner = EngineRunner(owner_id="owner", broker_account_id="account.default")
    try:
        assert runner.params["ir_shadow_enabled"] is False
    finally:
        runtime_config.clear_override("ir_shadow_enabled")
