#!/usr/bin/env python3
"""Prove the L1 Stage 1 shadow-lane guards can fail.

A guard nobody has watched go red is a guard nobody knows works. This applies one
deliberate defect at a time, runs the test that is supposed to catch it, and asserts the
test **fails**. Every mutation is reverted afterwards, including on error and on Ctrl-C.

    backend/.venv/bin/python scripts/ir_shadow_mutations.py

Exit 0 means every guard reddened on its own defect. Exit 1 names the guards that stayed
green while their defect was in place — those are the vacuous ones.

This is deliberately a script and not a test: it edits source files on disk, and a test
that rewrites the tree it is running from is a hazard, not evidence.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

BACKEND = pathlib.Path(__file__).resolve().parent.parent
PYTHON = BACKEND / ".venv" / "bin" / "python"

RUNNER = BACKEND / "app" / "engine" / "runner.py"
SHADOW = BACKEND / "app" / "engine" / "ir_shadow.py"
STORE = BACKEND / "app" / "engine" / "ir_shadow_store.py"
METRICS = BACKEND / "app" / "engine" / "ir_shadow_metrics.py"
CONFIG = BACKEND / "app" / "core" / "config.py"
ADAPTER = BACKEND / "app" / "strategy" / "ir_adapter.py"
BINDING = BACKEND / "app" / "core" / "execution_binding.py"
BOOK = BACKEND / "app" / "core" / "execution_book.py"
PAPER_AUTH = BACKEND / "app" / "core" / "paper_authority.py"
LIVE_BROKER = BACKEND / "app" / "engine" / "live_broker.py"
BROKER = BACKEND / "app" / "engine" / "broker.py"
ANALYTICS = BACKEND / "app" / "engine" / "analytics.py"
SESSION = BACKEND / "app" / "db" / "session.py"

ISOLATION = "tests/test_ir_shadow_isolation.py"
ADMISSION = "tests/test_ir_shadow_admission.py"
CORE = "tests/test_ir_shadow.py"
BINDING_TESTS = "tests/test_execution_binding.py"
ENGINE_BINDING = "tests/test_engine_binding.py"
ATTRIBUTION = "tests/test_execution_attribution.py"
SHADOW_DEPLOY = "tests/test_shadow_deployments.py"
SHADOW_ENGINE = "tests/test_shadow_deployment_engine.py"
DEPLOYMENTS = BACKEND / "app" / "core" / "shadow_deployments.py"
BOOK_TESTS = "tests/test_execution_book.py"
CAPITAL_TESTS = "tests/test_capital_books.py"
ISOLATION_TESTS = "tests/test_book_isolation.py"
PAPER_GATE_TESTS = "tests/test_paper_authority_gate.py"
PAPER_TESTS = "tests/test_paper_authority.py"
PAPER_ENGINE_TESTS = "tests/test_paper_authority_engine.py"
PROTOCOL_TESTS = "tests/test_broker_protocol.py"


#: (name, file, find, replace, the test that must go red)
MUTATIONS: list[tuple[str, pathlib.Path, str, str, str]] = [
    (
        # NB the obvious version of this mutation — writing into `self.state[key]` from
        # inside `_observe_shadow` — is a NO-OP, because the observer is called before the
        # state entry is built and the assignment that follows replaces the dict wholesale.
        # The harness caught that as a vacuous guard, which is what it is for. The leak has
        # to be injected where a real one would live: after the state entry exists.
        "the shadow verdict is fed back into the engine's state",
        RUNNER,
        '                "priority_flag": self.priority_flags.get(key, False),\n'
        "            }",
        '                "priority_flag": self.priority_flags.get(key, False),\n'
        "            }\n"
        '            self.state[key]["shadow_signal"] = True',
        f"{ISOLATION}::test_the_shadow_lane_writes_nothing_into_the_engine_state",
    ),
    (
        "the shadow lane mutates shared execution parameters",
        RUNNER,
        "            pairing = ir_shadow.pairing_for(source.pairing_key)",
        '            self.params["intraday_max_positions"] = 0\n'
        "            pairing = ir_shadow.pairing_for(source.pairing_key)",
        f"{ISOLATION}::test_the_authoritative_state_is_identical_with_the_shadow_on_and_off",
    ),
    (
        "the shadow lane touches a broker seam",
        RUNNER,
        "            pairing = ir_shadow.pairing_for(source.pairing_key)",
        "            self.broker.commit()\n"
        "            pairing = ir_shadow.pairing_for(source.pairing_key)",
        f"{ISOLATION}::test_a_full_shadow_scan_reaches_no_broker_or_order_seam",
    ),
    (
        "the shadow store imports the order path",
        STORE,
        "from app.db.session import SessionLocal",
        "from app.db.session import SessionLocal\n"
        "from app.engine.kite_order_client import KiteOrderClient  # noqa: F401",
        f"{ISOLATION}::test_no_shadow_module_names_an_execution_seam_directly"
        "[app.engine.ir_shadow_store]",
    ),
    (
        "a shadow failure escapes into the signal lane",
        RUNNER,
        "        except Exception as e:\n"
        "            log.error(f\"IR shadow lane error (authoritative lane unaffected): {e}\",\n"
        "                      instrument=key, event=\"IR_SHADOW\")",
        "        except Exception as e:\n"
        "            raise",
        f"{ISOLATION}::test_a_failure_anywhere_in_the_lane_leaves_the_authoritative_output"
        "_unchanged",
    ),
    (
        "the feature flag ships on",
        CONFIG,
        "    ir_shadow_enabled: bool = False",
        "    ir_shadow_enabled: bool = True",
        f"{ISOLATION}::test_the_flag_is_off_by_default_and_the_lane_is_inert",
    ),
    (
        "agreement is counted per scan instead of per bar",
        METRICS,
        "            if self._last_bar.get(observation.instrument_key) == bar:\n"
        "                return                      # the same completed bar, re-scanned",
        "            if False:\n"
        "                return",
        "tests/test_ir_shadow_metrics.py::test_a_rescanned_bar_is_not_counted_twice",
    ),
    (
        "an unsettleable frame goes back to silent all-False",
        ADAPTER,
        "    refuse_insufficient_history: bool = True",
        "    refuse_insufficient_history: bool = False",
        f"{CORE}::test_a_frame_shorter_than_the_graph_warmup_is_classified_not_silent",
    ),
    (
        "the admission contract admits a configuration that cannot settle the warmup",
        SHADOW,
        "    if expected <= warmup:",
        "    if False:",
        f"{ADMISSION}::test_an_inadmissible_pairing_is_never_evaluated",
    ),
    (
        # Mutating the CONSTANT here would hang: the test loops
        # `REFUSALS_BEFORE_DEMOTION + 3` times, so raising it to 10**9 asks for a billion
        # scans. Mutate the call site instead — same defect, bounded runtime. (That version
        # was tried, ran past ten minutes, and had to be killed.)
        "a pairing the feed keeps refusing is never demoted",
        RUNNER,
        "        if refusals < ir_shadow.REFUSALS_BEFORE_DEMOTION:\n            return",
        "        if True:\n            return",
        f"{ADMISSION}::"
        "test_an_admitted_pairing_that_keeps_refusing_is_demoted_rather_than_left_to_repeat",
    ),
    (
        # The single line that separates "observed" from "trading real money". Everything
        # ADR 0012 calls an owner gate begins here.
        "a graph-backed strategy is granted the authority to execute",
        BINDING,
        "    SOURCE_IR_GRAPH: SHADOW,",
        "    SOURCE_IR_GRAPH: AUTHORITATIVE,",
        f"{BINDING_TESTS}::"
        "test_binding_a_registered_graph_to_an_instrument_is_refused_not_silently_shadowed",
    ),
    (
        # The wiring itself. `strategy_for` resolves the same key from the same binding
        # and skips only the authority re-check — which is exactly the edit somebody makes
        # when the gate is inconvenient and the two names look interchangeable.
        "the engine takes a strategy without re-checking that it may execute",
        RUNNER,
        "        return execution, execution_binding.strategy_for_execution(execution)",
        "        return execution, execution_binding.strategy_for(execution)",
        # NB the obvious target — "assign a graph key, watch the engine refuse" — is
        # VACUOUS here: `bind` already refuses at resolution, so the downstream re-check
        # never runs and this mutation stayed green against it. The harness caught that.
        # The re-check only earns its place against a binding that arrives already
        # claiming authority, which is what the named test forges.
        f"{ENGINE_BINDING}::test_the_engine_rejects_a_forged_binding_from_a_drifted_resolver",
    ),
    (
        # A second resolution path reappearing in the engine is the contradiction this
        # slice removed. The guard is an AST check, so a comment mentioning the resolver
        # cannot satisfy it and a real call cannot escape it.
        "the engine resolves a strategy directly again, bypassing the contract",
        RUNNER,
        "                execution, strat = self._execution_for(key)",
        "                from app.strategy.registry import get_strategy\n"
        "                strat = get_strategy(self.strategy_keys.get(key))",
        f"{ENGINE_BINDING}::test_the_engine_never_calls_a_strategy_resolver_directly",
    ),
    (
        # The failure that must never become a substitution: a refused instrument trading
        # the platform default while every config row still names the graph.
        "a refused instrument silently falls back to an executable strategy",
        RUNNER,
        "                self.state.pop(key, None)\n"
        "                self.executed_binding.pop(key, None)\n"
        "                continue",
        "                strat = execution_binding.strategy_for(self._binding_for(key))",
        f"{ENGINE_BINDING}::"
        "test_the_engine_skips_a_refused_instrument_and_substitutes_nothing",
    ),
    (
        # Registry fallback as the real authority decision: a graph key that cannot be
        # resolved quietly becoming the default, which trades one logic and attributes
        # another. The registry refuses this; so must the binding.
        "an unresolvable graph key falls back to the default strategy",
        BINDING,
        "            raise\n        strategy = resolve_strategy(DEFAULT_STRATEGY_KEY)",
        "            pass\n        strategy = resolve_strategy(DEFAULT_STRATEGY_KEY)",
        f"{ENGINE_BINDING}::"
        "test_an_unregistered_graph_assignment_fails_with_a_stable_explicit_error",
    ),
    (
        # Source and authority stop being a reviewed *pair*, so a binding can grant itself
        # execution by setting a field — the reason the check lives at consumption.
        "an unreviewed source and authority pairing is accepted",
        BINDING,
        "            or (actual, mode, binding.authority) not in GRANTS \\",
        "            or False \\",
        f"{BINDING_TESTS}::"
        "test_a_binding_that_claims_an_unreviewed_pairing_is_refused_at_consumption",
    ),
    (
        # The write-side gate opens, so every route that assigns a strategy — instrument,
        # watchlist, universe add, deploy bridge — stops consulting the authority map.
        "the write-side authority check becomes a no-op",
        BINDING,
        "    if strategy_key is None:\n        return",
        "    if True:\n        return",
        f"{ENGINE_BINDING}::test_assigning_a_graph_strategy_through_the_route_is_refused",
    ),
    (
        # The defect this slice closed, restored. Before the fix this was the production
        # line: a stale assignment traded the default and the position claimed the key
        # that failed to resolve. The pre-fix run is recorded in the L1 plan.
        "a position is attributed to the raw assignment instead of what executed",
        RUNNER,
        "                        strategy_key=executed.strategy_key,\n"
        "                        strategy_version=executed.strategy_version,",
        "                        strategy_key=self.strategy_keys.get(pickk.instrument_key),\n"
        "                        strategy_version=None,",
        f"{ATTRIBUTION}::"
        "test_a_stale_assignment_is_attributed_to_the_strategy_that_actually_traded",
    ),
    (
        # The same defect on the futures path, which has its own write site and would not
        # have been covered by the intraday guard.
        "a futures position is attributed to the raw assignment",
        RUNNER,
        "                strategy_key=executed.strategy_key,\n"
        "                strategy_version=executed.strategy_version)",
        "                strategy_key=self.strategy_keys.get(key),\n"
        "                strategy_version=None)",
        f"{ATTRIBUTION}::test_the_futures_entry_path_attributes_what_executed",
    ),
    (
        # Re-resolution at the write site: the identity stops being "the strategy whose
        # output produced this signal" and becomes "whatever the configuration says at the
        # moment of the fill". The two differ whenever the assignment changed in between.
        "the executed identity is re-resolved at the fill instead of carried",
        RUNNER,
        "                        strategy_key=executed.strategy_key,",
        "                        strategy_key=self._binding_for(\n"
        "                            pickk.instrument_key).strategy_key,",
        f"{ATTRIBUTION}::"
        "test_the_executed_identity_is_the_one_that_produced_the_signal_not_the_latest",
    ),
    (
        # Binding propagation dropped: every fill falls back to the None encoding, which
        # reads as "the default produced this" whether or not it did.
        "the binding is never carried from the scan to the fill",
        RUNNER,
        "        return self.executed_binding.get(key)",
        "        return None",
        f"{ATTRIBUTION}::"
        "test_every_assignment_the_engine_can_hold_attributes_what_it_ran",
    ),
    (
        # A refusal that skips evaluation without withdrawing the previous tick's signal
        # lets `process_entries` open on state nothing currently authorises.
        "a refused instrument keeps the signal state that can still open a position",
        RUNNER,
        "                self.state.pop(key, None)\n"
        "                self.executed_binding.pop(key, None)",
        "                pass",
        f"{ATTRIBUTION}::test_a_refused_binding_produces_no_position_and_no_attribution",
    ),
    (
        # Authority inferred from the key's shape at the write site instead of consumed
        # from the binding — the "just check the namespace" edit that puts the decision
        # back in six places.
        "attribution infers authority from the key instead of the binding verdict",
        RUNNER,
        "                    executed = self._executed_binding(pickk.instrument_key)\n"
        "                    if executed is None:",
        "                    executed = self._executed_binding(pickk.instrument_key)\n"
        "                    _raw = self.strategy_keys.get(pickk.instrument_key)\n"
        '                    if executed is not None and _raw and not _raw.startswith("ir."):\n'
        "                        executed = execution_binding.ExecutionBinding(\n"
        '                            **{**executed.__dict__, "strategy_key": _raw})\n'
        "                    if executed is None:",
        f"{ATTRIBUTION}::"
        "test_a_stale_assignment_is_attributed_to_the_strategy_that_actually_traded",
    ),
    (
        # L1.3A. The single edit that would turn a managed *shadow* deployment into
        # something else. ADR 0012 §3.2 reserves that decision to the owner; this proves
        # the service cannot make it quietly.
        "a managed shadow deployment is written in an authoritative mode",
        DEPLOYMENTS,
        'MODE = "shadow"',
        'MODE = "paper"',
        f"{SHADOW_DEPLOY}::test_the_database_refuses_any_mode_but_shadow",
    ),
    (
        "a managed shadow deployment claims execution authority",
        DEPLOYMENTS,
        'AUTHORITY = "non_authoritative"',
        'AUTHORITY = "authoritative"',
        f"{SHADOW_DEPLOY}::test_the_database_refuses_any_authority_but_non_authoritative",
    ),
    (
        # The row records an address; without re-deriving it, the binding believes its own
        # column forever and keeps naming a graph whose bytes moved.
        "activation trusts the recorded content address instead of re-deriving it",
        DEPLOYMENTS,
        "    if address != row.graph_content_address:",
        "    if False:",
        f"{SHADOW_DEPLOY}::test_activation_reverifies_the_graph_content_address",
    ),
    (
        "activation accepts a graph no research decision approves",
        DEPLOYMENTS,
        "    if not decision:",
        "    if False:",
        f"{SHADOW_DEPLOY}::test_activation_without_evidence_is_refused",
    ),
    (
        "evidence for a different artefact is accepted as approval",
        DEPLOYMENTS,
        "    named = [m for m in mismatches if m]",
        "    named = []",
        f"{SHADOW_DEPLOY}::test_evidence_for_a_different_graph_version_is_refused",
    ),
    (
        # A retired binding that can be revived lets a graph nobody re-approved come back,
        # most likely across a restart, which is where nobody is watching.
        "a retired deployment can be activated again",
        DEPLOYMENTS,
        "    if row.state not in (STAGED, PAUSED):",
        "    if False:",
        f"{SHADOW_DEPLOY}::test_retirement_is_terminal",
    ),
    (
        "paused and retired deployments are reloaded and evaluated",
        DEPLOYMENTS,
        "        .where(IrShadowDeployment.state == SHADOW_ACTIVE)",
        "        .where(IrShadowDeployment.state != 'nothing-matches-this')",
        f"{SHADOW_DEPLOY}::test_only_active_bindings_are_reloaded",
    ),
    (
        "a stale revision silently overwrites somebody else's decision",
        DEPLOYMENTS,
        "    if row.revision != revision:",
        "    if False:",
        f"{SHADOW_DEPLOY}::test_a_stale_revision_is_rejected",
    ),
    (
        "warmup admission is skipped before activation",
        DEPLOYMENTS,
        "    if not admission.ok:",
        "    if False:",
        f"{SHADOW_DEPLOY}::"
        "test_an_interval_that_can_never_settle_the_warmup_is_refused_at_activation",
    ),
    (
        # Reload is the second half of verification: checking only at activation is a claim
        # about the past, and a restart is exactly when the past stops being evidence.
        "reload stops re-verifying, so a moved graph is observed silently",
        DEPLOYMENTS,
        "            if address != row.graph_content_address:\n"
        "                raise BindingUnverifiable(",
        "            if False:\n"
        "                raise BindingUnverifiable(",
        f"{SHADOW_ENGINE}::test_a_binding_whose_graph_moved_is_dropped_and_reported",
    ),
    (
        # The observer must consume the boundary's answer, including its refusals.
        #
        # NB the obvious version of this mutation — swapping `source.pairing_key` back to
        # `strat.key` — is VACUOUS today: exactly one graph exists, so both resolve to the
        # same pairing and nothing observable changes. The harness caught that. What *is*
        # observable now is whether a refusal is honoured, so that is what this breaks.
        "the observer ignores the boundary's refusal to name a shadow source",
        RUNNER,
        "            if source is None:\n"
        "                self.shadow_metrics.skipped(key)\n"
        "                return",
        "            if False:\n"
        "                self.shadow_metrics.skipped(key)\n"
        "                return",
        f"{SHADOW_ENGINE}::"
        "test_the_runner_consumes_a_boundary_refusal_rather_than_evaluating",
    ),
    (
        "a persistent cross-frame evaluation cache is reintroduced",
        SHADOW,
        "    def adapter(self) -> Any:",
        "    def build_cache(self):\n"
        "        from app.ir.runtime import Cache\n"
        "        return Cache()\n\n"
        "    def adapter(self) -> Any:",
        f"{CORE}::test_the_lane_never_constructs_a_persistent_evaluation_cache",
    ),
    # ── L1.3B: execution-mode and accounting isolation ───────────────────────────
    (
        "position lookup drops the book predicate",
        BROKER,
        "        stmt = select(Position).where(Position.instrument_key == key,\n"
        "                                      Position.mode == self.book)",
        "        stmt = select(Position).where(Position.instrument_key == key)",
        f"{ISOLATION_TESTS}::TestPositionsCannotCrossBooks"
        "::test_the_same_instrument_can_be_open_in_both_books_at_once",
    ),
    (
        "the open-position scan drops the book predicate",
        BROKER,
        "        stmt = select(Position).where(Position.mode == self.book)",
        "        stmt = select(Position)",
        f"{ISOLATION_TESTS}::TestPositionsCannotCrossBooks"
        "::test_a_live_position_is_never_returned_as_a_paper_position",
    ),
    (
        "paper trades are mixed into the live book's realised P&L",
        ANALYTICS,
        "    return [t for t in s.scalars(select(Trade).where(Trade.mode == book))",
        "    return [t for t in s.scalars(select(Trade))",
        f"{ISOLATION_TESTS}::TestTradeAggregatesDeclareTheirBook"
        "::test_the_daily_loss_breaker_counts_only_its_own_books_trades",
    ),
    (
        "restart rebuilds the wrong book",
        BROKER,
        "        self.book = book_of(self)",
        '        self.book = "paper"',
        f"{ISOLATION_TESTS}::TestRestartAndLegacyBehaviour"
        "::test_restart_rebuilds_only_the_requested_book",
    ),
    (
        "an unknown execution mode defaults to paper",
        BOOK,
        "    if not isinstance(raw, str):\n        return LIVE",
        "    if not isinstance(raw, str):\n        return PAPER",
        f"{BOOK_TESTS}::TestResolvingABook"
        "::test_unknown_missing_or_malformed_input_fails_closed_to_live",
    ),
    (
        "the gate checks the source alone instead of source and mode",
        BINDING,
        "    if claimed != actual or binding.execution_mode != mode \\\n"
        "            or (actual, mode, binding.authority) not in GRANTS \\",
        "    if claimed != actual \\\n"
        "            or (actual, binding.authority) not in "
        "{(s, a) for s, _m, a in GRANTS} \\",
        f"{BINDING_TESTS}::"
        "test_the_mode_recorded_on_a_binding_cannot_launder_it_past_the_gate",
    ),
    (
        # Suppressing the *warning* alone is a no-op — the `elif` still refuses to claim,
        # so a fresh ledger is created either way and the guard stays green. The harness
        # caught that as vacuous, which is what it is for. The defect has to be the one
        # that matters: claiming the row despite contradictory evidence.
        "the legacy ledger is guessed onto a book when the evidence contradicts itself",
        BOOK,
        "        if len(owners) > 1:\n"
        "            log.warn(LEGACY_LEDGER_AMBIGUOUS.format(row_id=legacy.id,\n"
        "                                                    owners=sorted(owners), book=book),\n"
        '                     event="LEDGER_UNATTRIBUTED")\n'
        "        elif not owners or owners == {book}:",
        "        if True:",
        f"{CAPITAL_TESTS}::TestClaimingTheLegacyLedger"
        "::test_a_ledger_with_rows_from_both_books_is_left_unattributed",
    ),
    (
        "the startup repair debits row 1 whichever book owns the position",
        SESSION,
        "        capital_for_book(sess, resolve_book(pos.mode)).cash -= "
        "pos.entry_cost - old_cost",
        "        capital_for_book(sess, 'live').cash -= pos.entry_cost - old_cost",
        f"{ISOLATION_TESTS}::TestOrphansFromTheOtherBookAreLoud"
        "::test_the_repair_path_debits_the_owning_books_ledger",
    ),
    (
        "an orphan in the other book is silently dropped instead of reported",
        BOOK,
        "    return [p for p in session.scalars(select(Position))\n"
        "            if resolve_book(p.mode) != book]",
        "    return []",
        f"{ISOLATION_TESTS}::TestOrphansFromTheOtherBookAreLoud"
        "::test_the_startup_boundary_reports_them",
    ),
    # ── L1.3C: IR paper authority ────────────────────────────────────────────────
    (
        "the (ir_graph, paper) grant is revoked",
        BINDING,
        "    (SOURCE_IR_GRAPH, PAPER, AUTHORITATIVE),\n})",
        "})",
        f"{PAPER_GATE_TESTS}::TestTheGrant::test_ir_graph_is_granted_in_paper_mode",
    ),
    (
        "ir_graph is granted authority in the LIVE book",
        BINDING,
        "    (SOURCE_IR_GRAPH, PAPER, AUTHORITATIVE),\n})",
        "    (SOURCE_IR_GRAPH, PAPER, AUTHORITATIVE),\n"
        "    (SOURCE_IR_GRAPH, LIVE, AUTHORITATIVE),\n})",
        f"{PAPER_GATE_TESTS}::TestTheGrant::test_ir_graph_is_not_granted_in_live_mode",
    ),
    (
        "the gate stops requiring a paper-authority origin",
        BINDING,
        "    if binding.origin != ORIGIN_PAPER_AUTHORITY:",
        "    if False:",
        f"{PAPER_GATE_TESTS}::TestTheGrantIsNotSufficientOnItsOwn"
        "::test_an_instrument_assignment_of_the_same_graph_is_still_refused",
    ),
    (
        "exact content-address verification is bypassed at the gate",
        BINDING,
        "    if not binding.strategy_version or binding.strategy_version != strategy.version:",
        "    if False:",
        f"{PAPER_GATE_TESTS}::TestExactVersionAtTheMomentOfUse"
        "::test_an_edited_graph_does_not_inherit_authority",
    ),
    (
        "a newer graph version inherits authority at bind time",
        BINDING,
        "    if not record.content_address or strategy.version != record.content_address:",
        "    if False:",
        f"{PAPER_ENGINE_TESTS}::TestExactVersion"
        "::test_a_binding_whose_adapter_no_longer_matches_refuses_rather_than_substituting",
    ),
    (
        "a paper deployment is consulted in a live process",
        BINDING,
        "    if paper_authority is not None and configured_execution_mode() == PAPER:",
        "    if paper_authority is not None:",
        f"{PAPER_ENGINE_TESTS}::TestLiveModeIsUnaffected"
        "::test_the_same_deployment_is_not_authoritative_in_a_live_process",
    ),
    (
        "evidence approval is bypassed at activation",
        PAPER_AUTH,
        "    decision = _require_evidence(row)",
        "    decision = verified_decision(project_id=row.project_id,\n"
        "                                 graph_identifier=row.graph_identifier,\n"
        "                                 graph_version=row.graph_version) or {}",
        f"{PAPER_TESTS}::TestActivation::test_rejected_evidence_fails_closed",
    ),
    (
        "the reload stops re-deriving the content address",
        PAPER_AUTH,
        "            if address != row.graph_content_address:\n"
        "                raise BindingUnverifiable(",
        "            if False:\n"
        "                raise BindingUnverifiable(",
        f"{PAPER_TESTS}::TestActiveBindings"
        "::test_reload_drops_a_binding_whose_recorded_address_disagrees",
    ),
    (
        "paused and retired deployments resurrect on restart",
        PAPER_AUTH,
        "        .where(IrPaperDeployment.state == PAPER_ACTIVE)",
        "        .where(IrPaperDeployment.state != RETIRED)",
        f"{PAPER_ENGINE_TESTS}::TestRestart::test_a_paused_deployment_does_not_resurrect",
    ),
    (
        # Importing the shadow module in place of the paper one is a NO-OP defect: it has
        # no `register_active_adapters`, so the call raises, the broad handler catches it
        # and the runner ends up with no bindings — which is what the guard asserts anyway.
        # The harness caught that as vacuous. The defect has to be the plausible one: a
        # fallback that treats an observed graph as an authoritative one when no paper
        # record exists.
        "a shadow deployment is treated as a paper-authority record",
        RUNNER,
        "        self.paper_authority = {b.instrument_key: b for b in bindings}",
        "        from app.core import shadow_deployments as _sd\n"
        "        with SessionLocal() as _s:\n"
        "            bindings = bindings or _sd.active_bindings(_s)\n"
        "        self.paper_authority = {b.instrument_key: b for b in bindings}",
        f"{PAPER_ENGINE_TESTS}::TestBindingThroughTheRunner"
        "::test_a_shadow_deployment_does_not_confer_paper_authority",
    ),
    (
        "the rollback target is inferred instead of named",
        PAPER_AUTH,
        "    _validate_rollback_target(restore_strategy_key)",
        "    restore_strategy_key = restore_strategy_key or 'expanding_z_v4'",
        f"{PAPER_TESTS}::TestRollback"
        "::test_retiring_with_no_previous_authority_leaves_the_instrument_unassigned",
    ),
    (
        "the executed identity is re-resolved at the fill instead of carried",
        RUNNER,
        "                    strategy_key=executed.strategy_key,\n"
        "                    strategy_version=executed.strategy_version)",
        "                    strategy_key=self.strategy_keys.get(c.instrument_key),\n"
        "                    strategy_version=None)",
        f"{PAPER_ENGINE_TESTS}::TestAttributionOnARealPaperFill"
        "::test_the_position_records_the_exact_graph_that_produced_it",
    ),
    (
        "the live broker cannot accept what the runner passes it",
        LIVE_BROKER,
        "                      params=None, plan=None, strategy_key=None,\n"
        "                      strategy_version=None):",
        "                      params=None, plan=None):",
        f"{PROTOCOL_TESTS}::test_the_live_broker_accepts_everything_the_paper_broker_does",
    ),
]


#: Where a mutation's original text is parked while it is applied. `finally` covers an
#: exception; it does NOT cover SIGKILL, and one killed run did leave a mutated constant in
#: the tree. The sidecar makes recovery automatic instead of a thing to remember.
BACKUP = BACKEND / ".ir_shadow_mutation_backup"


def restore_any_orphan() -> None:
    """Undo a mutation left behind by a run that was killed rather than finished."""
    if not BACKUP.exists():
        return
    name, _, content = BACKUP.read_text().partition("\n")
    target = pathlib.Path(name)
    if target.exists() and target.read_text() != content:
        target.write_text(content)
        print(f"restored {target.name} from an interrupted previous run")
    BACKUP.unlink()


def run(test: str) -> bool:
    """True if the test passed."""
    result = subprocess.run(
        [str(PYTHON), "-m", "pytest", test, "-x", "-q", "--no-header", "-p", "no:cacheprovider"],
        cwd=BACKEND, capture_output=True, text=True)
    return result.returncode == 0


def main() -> int:
    restore_any_orphan()
    failures: list[str] = []
    print(f"{'guard':<62} {'clean':<8} {'mutated':<8} verdict")
    print("-" * 96)
    for name, path, find, replace, test in MUTATIONS:
        original = path.read_text()
        if find not in original:
            print(f"{name:<62} {'-':<8} {'-':<8} ANCHOR NOT FOUND in {path.name}")
            failures.append(name)
            continue
        clean = run(test)
        try:
            BACKUP.write_text(f"{path}\n{original}")
            path.write_text(original.replace(find, replace, 1))
            mutated = run(test)
        finally:
            path.write_text(original)
            BACKUP.unlink(missing_ok=True)
        caught = clean and not mutated
        print(f"{name:<62} {'PASS' if clean else 'FAIL':<8} "
              f"{'PASS' if mutated else 'FAIL':<8} "
              f"{'guard works' if caught else 'VACUOUS — guard did not catch it'}")
        if not caught:
            failures.append(name)

    print("-" * 96)
    if failures:
        print(f"{len(failures)} guard(s) did not redden: " + "; ".join(failures))
        return 1
    print(f"all {len(MUTATIONS)} guards reddened on their own defect and were restored")
    return 0


if __name__ == "__main__":
    sys.exit(main())
