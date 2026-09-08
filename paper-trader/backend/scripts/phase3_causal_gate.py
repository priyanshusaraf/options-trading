"""Run the bounded Phase 3 causal-admission closure gate.

This is evidence collection for the admitted causal artefact lane.  It is not
proof of market truth, complete numeric validity, provider capability, role
binding, resource compatibility, protection compatibility, or live readiness.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any, Iterable


BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TIMEOUT_SECONDS = 180
# Broad admitted-path shards contain migration and lifecycle tests that are known
# to run longer than focused probes.  This is a bounded execution budget, never
# an acceptance of a timeout.
BROAD_TIMEOUT_SECONDS = 600
SLOW_BROAD_TIMEOUT_SECONDS = 1200

REQUIRED_KILLS = frozenset({
    "negative_shift", "centered_window", "bfill", "future_join",
    "global_normalize", "missing_declaration", "stale_actual_expanding_z_helper",
    "omit_node_socket", "add_ghost_socket", "bypass_root_provenance",
    "forged_receipt", "cross_owner_receipt", "same_bar_fill",
    "bypass_editor_publish", "bypass_research_enqueue", "bypass_research_worker",
    "bypass_backtest_enqueue", "bypass_backtest_worker", "bypass_promotion_approval",
    "bypass_shadow_activate", "bypass_shadow_resume", "bypass_paper_activate",
    "bypass_paper_resume", "bypass_deploy_bridge", "bypass_deployment_write",
    "complete_affected_watchlist_authority",
    "bypass_execution_binding", "bypass_live_intent", "bypass_paper_position",
    "bypass_late_fill_adoption", "bypass_trade_attribution",
    "v1_reversed_direction_validation", "v1_duplicate_target_validation",
    "v1_reversed_direction_resolution", "v1_reversed_direction_registry",
    "v1_duplicate_target_vector_runtime", "v1_duplicate_target_prefix_runtime",
    "v1_graph_component_interface_mismatch_resolution",
    "v1_graph_component_interface_mismatch_admission",
    "v1_graph_output_missing_producer_validation",
    "v1_graph_output_missing_producer_resolution",
})


@dataclass(frozen=True)
class CommandSpec:
    name: str
    argv: tuple[str, ...]
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    requires_tests: bool = True
    allowed_skips: int = 0
    allowed_skip_nodeids: tuple[str, ...] = ()
    # Some broad shards deliberately skip the opposite storage plane.  The
    # reason is part of that narrow contract, not merely diagnostic text.
    allowed_skip_reasons: tuple[tuple[str, str], ...] = ()
    # Pytest -vv renders node IDs without reasons and -rs renders the reason
    # once for each source line.  Keep that second, exact evidence shape.
    allowed_skip_summary_evidence: tuple[tuple[str, int, str], ...] = ()
    expected_output: str | None = None
    allowed_failure_nodeids: tuple[str, ...] = ()


def _pytest(name: str, *selectors: str, timeout: int = DEFAULT_TIMEOUT_SECONDS,
            allowed_skips: int = 0,
            allowed_skip_nodeids: tuple[str, ...] = ()) -> CommandSpec:
    # pytest.ini already supplies one -q.  A second hides the final count and
    # would make an executed suite indistinguishable from zero collected tests.
    return CommandSpec(
        name, (sys.executable, "-m", "pytest", *selectors), timeout,
        allowed_skips=allowed_skips,
        allowed_skip_nodeids=allowed_skip_nodeids,
    )


FOCUSED_SPECS = (
    _pytest("focused_ir_contract",
            "tests/test_ir_conformance.py", "tests/test_ir_resolution.py",
            "tests/test_ir_platform_library.py", "tests/test_ir_runtime.py"),
    _pytest("focused_causal_identity",
            "tests/test_ir_causal_contract.py", "tests/test_ir_implementation_identity.py",
            "tests/test_strategy_admission.py", "tests/test_ir_streaming_reference.py",
            "tests/test_causal_admission_mutations.py"),
    _pytest("focused_persistence_authority",
            "tests/test_strategy_admission_repository.py", "tests/test_ir_edit_routes.py",
            "tests/test_backtest_admission.py", "tests/test_strategy_admission_authority.py",
            timeout=300),
    _pytest("focused_execution_trace",
            "tests/test_execution_admission_attribution.py",
            "tests/test_strategy_admission_backfill.py",
            "tests/test_paper_authority_runtime.py::test_active_paper_binding_reaches_the_final_entry_receipt_check"),
    _pytest("focused_research",
            "research_tests/test_composition_ir.py",
            "research_tests/test_strategy_admissions.py",
            "research_tests/test_graph_experiment.py"),
)


MUTATION_SELECTORS = (
    "tests/test_ir_causal_contract.py::test_causal_contract_rejects_future_or_hidden_dependencies",
    "tests/test_ir_implementation_identity.py::test_actual_expanding_z_rma_change_makes_registration_stale",
    "tests/test_strategy_admission.py::test_missing_or_extra_contract_socket_refuses",
    "tests/test_strategy_admission.py::test_structural_inspection_derives_nested_provenance_from_real_registry",
    "tests/test_strategy_admission.py::test_runtime_for_admitted_rejects_a_forged_receipt_without_parity",
    "tests/test_strategy_admission_repository.py::test_owner_scope_and_exact_duplicate_are_safe",
    "tests/test_backtest_fill_timing.py::test_same_bar_mutant_is_killed",
    "tests/test_ir_edit_routes.py::test_admission_refusal_returns_a_stable_422_and_preserves_the_draft",
    "research_tests/test_graph_experiment.py::test_missing_graph_receipt_refuses_before_the_experiment_can_touch_data",
    "research_tests/test_graph_experiment.py::test_graph_worker_freshly_verifies_the_persisted_receipt",
    "tests/test_backtest_admission.py::test_enqueue_bypass_mutant_is_killed",
    "tests/test_backtest_admission.py::test_worker_bypass_mutant_is_killed",
    "tests/test_strategy_admission_authority.py::test_promotion_approval_receipt_bypass_mutant_is_killed",
    "tests/test_shadow_deployments.py::test_shadow_activate_receipt_bypass_mutant_is_killed",
    "tests/test_shadow_deployments.py::test_shadow_resume_receipt_bypass_mutant_is_killed",
    "tests/test_paper_authority_runtime.py::test_paper_activate_receipt_bypass_mutant_is_killed",
    "tests/test_paper_authority_runtime.py::test_paper_resume_receipt_bypass_mutant_is_killed",
    "tests/test_deploy_bridge.py::test_deploy_bridge_receipt_check_bypass_mutant_is_killed",
    "tests/test_deployments.py::test_deployment_strategy_write_bypass_mutant_is_killed",
    "tests/test_session_entry_guard.py::test_final_entry_receipt_check_blocks_an_already_published_signal",
    "tests/test_live_entry_durability.py::test_direct_live_entry_rejects_a_valid_looking_forged_receipt_before_submit",
    "tests/test_execution_admission_attribution.py::test_paper_open_seam_refuses_a_hash_shaped_forged_receipt",
    "tests/test_execution_admission_attribution.py::test_persisted_original_intent_books_a_fill_when_receipt_stales_after_submit",
    "tests/test_execution_admission_attribution.py::test_paper_position_and_trade_copy_the_entry_receipt",
    "tests/test_ir_conformance.py::test_f9_edge_ends_obey_declared_socket_directions",
    "tests/test_ir_conformance.py::test_f9_v1_target_socket_accepts_only_one_incoming_edge",
    "tests/test_ir_resolution.py::test_c3_resolution_rejects_leaf_socket_direction_when_validation_is_bypassed",
    "tests/test_ir_platform_library.py::test_platform_registry_enforces_graph_body_socket_contract[input_as_source]",
    "tests/test_ir_runtime.py::test_runtime_refuses_duplicate_target_collapse_in_a_forged_resolved_graph",
    "tests/test_ir_streaming_reference.py::test_reference_refuses_duplicate_target_collapse_in_a_forged_resolved_graph",
    "tests/test_ir_resolution.py::test_c3_graph_component_public_interface_must_equal_its_body_at_resolution",
    "tests/test_strategy_admission.py::test_reached_nested_body_must_validate_against_its_published_interface",
    "tests/test_ir_conformance.py::test_f9_declared_graph_output_has_exactly_one_producer",
    "tests/test_ir_resolution.py::test_c3_resolution_rejects_declared_output_without_a_producer",
    "tests/test_deploy_bridge.py::test_deploy_complete_affected_set_guard_mutant_is_killed",
)


def _shard(prefix: str, values: tuple[str, ...], size: int) -> tuple[CommandSpec, ...]:
    return tuple(
        _pytest(f"{prefix}_{index // size + 1}", *values[index:index + size])
        for index in range(0, len(values), size)
    )


NAMED_MUTATION_SPECS = _shard("named_mutations", MUTATION_SELECTORS, 9)
CAUSAL_MUTATIONS = CommandSpec(
    "causal_mutations",
    (sys.executable, "scripts/causal_admission_mutations.py", "--json"),
    requires_tests=False,
)
MIGRATION_HEAD_SPECS = (
    CommandSpec(
        "execution_migration_head",
        (sys.executable, "-c", "from app.db.migrate import head_revision; print(head_revision())"),
        requires_tests=False,
        expected_output="0034",
    ),
    CommandSpec(
        "research_migration_head",
        (sys.executable, "-c", "from research.domain.migrate import head_version; print(head_version())"),
        requires_tests=False,
        expected_output="0005",
    ),
)
POSTGRES_SPECS = (
    _pytest("postgres_execution",
            "tests/test_postgres_execution_schema.py::test_optional_postgres_fresh_schema_is_complete_and_idempotent",
            "tests/test_strategy_admission_repository.py::test_postgresql_raw_receipt_mutation_is_sqlstate_55000_and_retains_bytes",
            timeout=300),
    _pytest("postgres_research",
            "tests/test_postgres_plane_schemas.py::test_fresh_postgresql_plane_creates_validates_stamps_and_restarts[research]",
            "research_tests/test_strategy_admissions.py::test_postgresql_research_receipt_trigger_has_sqlstate_55000_and_current_contract",
            timeout=300),
)


OPTIONAL_SKIP_NODEIDS = (
    *(f"research_tests/test_block_declared_inputs.py::"
      f"test_a_block_does_not_declare_what_it_never_reads[{name}]"
      for name in (
          "opening_range_break_down", "opening_range_break_up", "regime_is",
          "rsi_gt", "rsi_lt", "time_of_day",
      )),
)
OPTIONAL_SKIP_COMPANIONS = (
    "test_a_choice_parameter_widens_the_declaration_to_the_union[regime_is]",
    "test_a_choice_parameter_widens_the_declaration_to_the_union[rsi_gt]",
    "test_a_choice_parameter_widens_the_declaration_to_the_union[rsi_lt]",
    "test_the_clock_is_declared_separately_from_the_values",
    "test_a_clock_block_reads_false_rather_than_raising_without_its_clock",
)


PLANE_PARAMETER_SKIP_REASONS = (
    ("tests/test_postgres_plane_schemas.py::"
     "test_ledger_snapshot_check_cannot_be_semantically_weakened[research-id = 1 OR TRUE]",
     "ledger plane only"),
    ("tests/test_postgres_plane_schemas.py::"
     "test_ledger_snapshot_check_cannot_be_semantically_weakened[research-CASE WHEN id = 1 THEN TRUE ELSE TRUE END]",
     "ledger plane only"),
    ("tests/test_postgres_plane_schemas.py::"
     "test_research_state_check_cannot_be_replaced_by_case_passthrough[ledger]",
     "research plane only"),
    ("tests/test_postgres_plane_schemas.py::"
     "test_missing_research_immutable_trigger_is_refused[ledger]",
     "research plane only"),
    *(("tests/test_postgres_plane_schemas.py::"
       f"test_research_immutable_trigger_catalog_contract_is_validated[ledger-{tamper}]",
       "research plane only")
      for tamper in ("pass_through", "disabled", "mislinked")),
    ("tests/test_postgres_plane_schemas.py::"
     "test_research_immutable_trigger_when_false_is_refused[ledger]",
     "research plane only"),
    ("tests/test_postgres_plane_schemas.py::"
     "test_research_immutable_facts_refuse_update_and_delete[ledger]",
     "research plane only"),
    ("tests/test_postgres_plane_schemas.py::"
     "test_research_owner_isolation_and_claim_race_on_plane_url[ledger]",
     "research plane only"),
    ("tests/test_postgres_plane_schemas.py::"
     "test_ledger_owner_account_isolation_and_snapshot_race_on_plane_url[research]",
     "ledger plane only"),
    ("tests/test_postgres_plane_schemas.py::"
     "test_ledger_manual_fill_claim_race_on_plane_url[research]",
     "ledger plane only"),
)
LEGACY_REBUILD_SKIP_REASONS = (
    ("tests/test_research_tenant_isolation.py::"
     "test_legacy_rows_upgrade_losslessly_and_two_owners_share_content_addresses",
     "0001 legacy-rebuild proof is pinned to the c8230d9 frozen metadata contract; "
     "the current head deliberately refuses to reinterpret that historical schema"),
)
PLANE_PARAMETER_SKIP_SUMMARY_EVIDENCE = (
    ("tests/test_postgres_plane_schemas.py:154", 2, "ledger plane only"),
    ("tests/test_postgres_plane_schemas.py:173", 1, "research plane only"),
    ("tests/test_postgres_plane_schemas.py:194", 1, "research plane only"),
    ("tests/test_postgres_plane_schemas.py:210", 3, "research plane only"),
    ("tests/test_postgres_plane_schemas.py:244", 1, "research plane only"),
    ("tests/test_postgres_plane_schemas.py:285", 1, "research plane only"),
    ("tests/test_postgres_plane_schemas.py:347", 1, "research plane only"),
    ("tests/test_postgres_plane_schemas.py:421", 1, "ledger plane only"),
    ("tests/test_postgres_plane_schemas.py:468", 1, "ledger plane only"),
)
LEGACY_REBUILD_SKIP_SUMMARY_EVIDENCE = (
    ("tests/test_research_tenant_isolation.py:125", 1,
     LEGACY_REBUILD_SKIP_REASONS[0][1]),
)
NATIVE_STATE_CONTRACT_SKIP_REASONS = (
    # Module-level quarantine owned by
    # phase1-4-foundation-research-migration-native-state-contract-core: the
    # projection consumer targets the superseded native-state producer API.
    # A module-level skip emits no -vv per-node line, so this contract pins
    # the exact skip COUNT plus the -rs summary source/count, while the exact
    # reason bytes are pinned by the module's own pytest.skip call.  When the
    # owning capsule reconciles the two sides it deletes that skip call and
    # retires this contract in the same slice.
    ("tests/test_foundation_research_projection_contracts.py",
     "test_foundation_research_projection_contracts targets a superseded "
     "foundation_native_state_contract producer API (missing "
     "DeclaredNativeAdapter/register_declared_adapter); owned by "
     "phase1-4-foundation-research-migration-native-state-contract-core"),
)
NATIVE_STATE_CONTRACT_SKIP_SUMMARY_EVIDENCE = (
    ("tests/test_foundation_research_projection_contracts.py:42", 1,
     NATIVE_STATE_CONTRACT_SKIP_REASONS[0][1]),
)


def _broad_skip_contract(
        spec: CommandSpec,
) -> tuple[tuple[str, ...], tuple[tuple[str, str], ...], tuple[tuple[str, int, str], ...]]:
    files = set(spec.argv)
    if "tests/test_postgres_plane_schemas.py" in files:
        return (
            tuple(nodeid for nodeid, _reason in PLANE_PARAMETER_SKIP_REASONS),
            PLANE_PARAMETER_SKIP_REASONS,
            PLANE_PARAMETER_SKIP_SUMMARY_EVIDENCE,
        )
    if "tests/test_research_tenant_isolation.py" in files:
        return (
            tuple(nodeid for nodeid, _reason in LEGACY_REBUILD_SKIP_REASONS),
            LEGACY_REBUILD_SKIP_REASONS,
            LEGACY_REBUILD_SKIP_SUMMARY_EVIDENCE,
        )
    if "tests/test_foundation_research_projection_contracts.py" in files:
        return (
            (),
            NATIVE_STATE_CONTRACT_SKIP_REASONS,
            NATIVE_STATE_CONTRACT_SKIP_SUMMARY_EVIDENCE,
        )
    return (), (), ()


# This immutable entry allowlist is attributable to the authoritative Phase 3
# checkpoint.  It deliberately excludes the paper-broker guard, which was a
# category-C predecessor-schema failure and must now be green.  A broad gate
# may observe a subset here, but never a failure outside it.
BASELINE_CHECKPOINT = "9b8b0f7a639b9b687089f7ba7e5a1ec4dde502ba"
CATEGORY_C_FIXED_NODEIDS = (
    "tests/test_no_live_under_pytest.py::"
    "test_the_guard_does_not_fire_on_the_paper_broker",
)
# Baseline-failure allowlist RETIRED 2026-08-22: every nodeid it tolerated has
# been fixed or consciously refreshed against the current head. A red broad
# shard is therefore ALWAYS a real regression now.
ALLOWED_BASELINE_FAILURE_NODEIDS: tuple[str, ...] = ()


def _broad_failure_allowlist(spec: CommandSpec) -> tuple[str, ...]:
    # Retired with the baseline list above; kept so call sites stay stable.
    return ()


# ── proven-slow shards: membership-derived splits (drift-proof) ──────────────
# The hand-written replacement tables drifted three times: every new test file
# shifted alphabetical windows and broke the hard-coded memberships. They are
# replaced by construction from LIVE membership. Only two facts are declared,
# both stable across membership churn:
#   WHICH shards were measured red (their names), and
#   WHICH FILES contain a node whose measured runtime needs the slow budget.
PROVEN_SLOW_SHARDS = frozenset({"broad_tests_6", "broad_tests_15",
                                "broad_tests_19"})
ANCHORED_SLOW_FILES = frozenset({
    "tests/test_engine_intraday.py",      # intraday e2e measured over budget
    "tests/test_backtest_parallel.py",    # parallel worker pool measured slow
    "tests/test_backtest_pinned_worker_reads.py",
})


def _split_slow_shard(spec: CommandSpec) -> tuple[CommandSpec, ...]:
    """Expand one proven-slow shard around its CURRENT member files.

    Files carrying a measured-slow anchor become their own sub-shard with the
    slow budget; everything else batches into one broad-budget sub-shard. All
    child specs inherit the parent's skip/failure contracts, so the expansion
    can never widen what the run tolerates.
    """
    if spec.name not in PROVEN_SLOW_SHARDS:
        return (spec,)
    files = tuple(spec.argv[3:])
    children: list[tuple[tuple[str, ...], int]] = []
    plain: list[str] = []
    for f in files:
        if f in ANCHORED_SLOW_FILES:
            if plain:
                children.append((tuple(plain), BROAD_TIMEOUT_SECONDS))
                plain = []
            children.append(((f,), SLOW_BROAD_TIMEOUT_SECONDS))
        else:
            plain.append(f)
    if plain:
        children.append((tuple(plain), BROAD_TIMEOUT_SECONDS))
    expanded = []
    for index, (selectors, timeout) in enumerate(children, start=1):
        expanded.append(CommandSpec(
            f"{spec.name}_s{index}",
            (*spec.argv[:3], *selectors),
            timeout,
            spec.requires_tests,
            allowed_skips=spec.allowed_skips,
            allowed_skip_nodeids=spec.allowed_skip_nodeids,
            allowed_skip_reasons=spec.allowed_skip_reasons,
            allowed_skip_summary_evidence=spec.allowed_skip_summary_evidence,
            allowed_failure_nodeids=_broad_failure_allowlist(spec),
        ))
    return tuple(expanded)


def _broad_specs() -> tuple[CommandSpec, ...]:
    specs: list[CommandSpec] = []
    for directory, prefix, size in (
        ("tests", "broad_tests", 5),
        ("research_tests", "broad_research", 7),
    ):
        files = tuple(str(path.relative_to(BACKEND_ROOT)) for path in
                      sorted((BACKEND_ROOT / directory).glob("test_*.py")))
        generated = tuple(
            CommandSpec(
                spec.name, spec.argv, BROAD_TIMEOUT_SECONDS, spec.requires_tests,
                allowed_skip_nodeids=_broad_skip_contract(spec)[0],
                allowed_skip_reasons=_broad_skip_contract(spec)[1],
                allowed_skip_summary_evidence=_broad_skip_contract(spec)[2],
                allowed_failure_nodeids=_broad_failure_allowlist(spec),
            )
            for spec in _shard(prefix, files, size)
        )
        if directory == "research_tests":
            generated = tuple(
                CommandSpec(
                    spec.name,
                    ((*spec.argv[:3], "-vv", "-rs", *spec.argv[3:])
                     if ("research_tests/test_block_declared_inputs.py" in spec.argv
                         or spec.allowed_skip_reasons)
                     else spec.argv),
                    spec.timeout_seconds, spec.requires_tests,
                    allowed_skips=(6 if "research_tests/test_block_declared_inputs.py" in spec.argv
                                   else len(spec.allowed_skip_nodeids)),
                    allowed_skip_nodeids=(OPTIONAL_SKIP_NODEIDS
                                          if "research_tests/test_block_declared_inputs.py" in spec.argv
                                          else spec.allowed_skip_nodeids),
                    allowed_skip_reasons=spec.allowed_skip_reasons,
                    allowed_skip_summary_evidence=spec.allowed_skip_summary_evidence,
                    allowed_failure_nodeids=spec.allowed_failure_nodeids,
                )
                for spec in generated
            )
        else:
            generated = tuple(
                replacement
                for spec in generated
                for replacement in _split_slow_shard(spec)
            )
            generated = tuple(
                CommandSpec(
                    spec.name, (*spec.argv[:3], "-vv", "-rs", *spec.argv[3:]),
                    spec.timeout_seconds, spec.requires_tests,
                    allowed_skips=(len(spec.allowed_skip_nodeids)
                                   or sum(item[1] for item
                                          in spec.allowed_skip_summary_evidence)),
                    allowed_skip_nodeids=spec.allowed_skip_nodeids,
                    allowed_skip_reasons=spec.allowed_skip_reasons,
                    allowed_skip_summary_evidence=spec.allowed_skip_summary_evidence,
                    allowed_failure_nodeids=spec.allowed_failure_nodeids,
                ) if spec.allowed_skip_reasons else spec
                for spec in generated
            )
        specs.extend(generated)
    return tuple(specs)


BROAD_SPECS = _broad_specs()
CORRECTION_FORCED_BROAD_SPECS = (
    "broad_tests_13", "broad_tests_15_before_intraday",
    "broad_tests_31", "broad_tests_45", "broad_tests_46",
)
REQUIRED_SPECS = (*FOCUSED_SPECS, CAUSAL_MUTATIONS, *NAMED_MUTATION_SPECS,
                  *MIGRATION_HEAD_SPECS)


def _mutation_command(selector: str) -> str:
    for spec in NAMED_MUTATION_SPECS:
        if selector in spec.argv:
            return spec.name
    raise RuntimeError(f"mutation selector is not executed: {selector}")


MUTATION_EVIDENCE = {
    "negative_shift": ("causal_mutations", "fresh negative-shift registration"),
    "centered_window": ("causal_mutations", "fresh centered-window registration"),
    "bfill": ("causal_mutations", "fresh backward-fill registration"),
    "future_join": ("causal_mutations", "fresh future-join registration"),
    "global_normalize": ("causal_mutations", "fresh global-normalize registration"),
}


def _bind(names: Iterable[str], selector: str) -> None:
    command = _mutation_command(selector)
    for name in names:
        MUTATION_EVIDENCE[name] = (command, selector)


_bind(("missing_declaration",), MUTATION_SELECTORS[0])
_bind(("stale_actual_expanding_z_helper",), MUTATION_SELECTORS[1])
_bind(("omit_node_socket", "add_ghost_socket"), MUTATION_SELECTORS[2])
_bind(("bypass_root_provenance",), MUTATION_SELECTORS[3])
for _name, _selector in zip((
    "forged_receipt", "cross_owner_receipt", "same_bar_fill",
    "bypass_editor_publish", "bypass_research_enqueue", "bypass_research_worker",
    "bypass_backtest_enqueue", "bypass_backtest_worker", "bypass_promotion_approval",
    "bypass_shadow_activate", "bypass_shadow_resume", "bypass_paper_activate",
    "bypass_paper_resume", "bypass_deploy_bridge", "bypass_deployment_write",
    "bypass_execution_binding", "bypass_live_intent", "bypass_paper_position",
    "bypass_late_fill_adoption", "bypass_trade_attribution",
), MUTATION_SELECTORS[4:24]):
    _bind((_name,), _selector)
for _name, _selector in zip((
    "v1_reversed_direction_validation", "v1_duplicate_target_validation",
    "v1_reversed_direction_resolution", "v1_reversed_direction_registry",
    "v1_duplicate_target_vector_runtime", "v1_duplicate_target_prefix_runtime",
    "v1_graph_component_interface_mismatch_resolution",
    "v1_graph_component_interface_mismatch_admission",
    "v1_graph_output_missing_producer_validation",
    "v1_graph_output_missing_producer_resolution",
), MUTATION_SELECTORS[24:]):
    _bind((_name,), _selector)
_bind(("complete_affected_watchlist_authority",), MUTATION_SELECTORS[-1])


_TEST_OUTCOME = re.compile(
    r"(?<!\d)(?P<count>\d+) (?P<outcome>passed|failed|error|errors|skipped|xfailed|xpassed)")
_PYTEST_FAILURE = re.compile(r"^(?:FAILED|ERROR) (?P<nodeid>\S+?)(?:\s+-|\s*$)")
_PYTEST_SKIP = re.compile(
    r"^(?P<nodeid>(?:tests|research_tests)/.+?)\s+SKIPPED"
    r"(?: \[\s*\d+%\])?(?: \((?P<reason>.*)\))?\s*$")
_PYTEST_SKIP_SUMMARY = re.compile(
    r"^SKIPPED \[(?P<count>\d+)\] (?P<source>(?:tests|research_tests)/.+?:\d+): "
    r"(?P<reason>.*)$")


def _summary_matches(output: str) -> list[re.Match[str]]:
    """Read the last pytest outcome line, never numbers quoted by a failure."""
    for line in reversed(output.splitlines()):
        matches = list(_TEST_OUTCOME.finditer(line))
        if matches:
            return matches
    return []


def _test_count(output: str) -> int:
    return sum(int(match.group(1)) for match in _summary_matches(output))


def _skip_count(output: str) -> int:
    return sum(
        int(match.group(1)) for match in _summary_matches(output)
        if match.group("outcome") == "skipped"
    )


def _error_count(output: str) -> int:
    return sum(
        int(match.group("count")) for match in _summary_matches(output)
        if match.group("outcome") in {"error", "errors"}
    )


def _pytest_failure_nodeids(output: str) -> set[str]:
    """Parse pytest's terminal FAILED/ERROR node lines without traceback text."""
    return {
        match.group("nodeid")
        for line in output.splitlines()
        if (match := _PYTEST_FAILURE.match(line))
    }


def _pytest_skips(output: str) -> dict[str, str | None]:
    return {
        match.group("nodeid"): match.group("reason")
        for line in output.splitlines()
        if (match := _PYTEST_SKIP.match(line))
    }


def _pytest_skip_summary_evidence(output: str) -> dict[str, tuple[int, str]]:
    return {
        match.group("source"): (int(match.group("count")), match.group("reason"))
        for line in output.splitlines()
        if (match := _PYTEST_SKIP_SUMMARY.match(line))
    }


def _has_terminal_pytest_summary(output: str) -> bool:
    return bool(_summary_matches(output))


def _run(spec: CommandSpec) -> dict[str, Any]:
    started = time.monotonic()
    try:
        completed = subprocess.run(
            list(spec.argv), cwd=BACKEND_ROOT, text=True, capture_output=True,
            timeout=spec.timeout_seconds, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        def decoded(value: str | bytes | None) -> str:
            return value.decode(errors="replace") if isinstance(value, bytes) else (value or "")
        output = decoded(exc.stdout) + decoded(exc.stderr)
        return {
            "command": list(spec.argv), "duration_seconds": round(time.monotonic() - started, 3),
            "exit_code": None, "timed_out": True, "skipped": 0,
            "test_count": _test_count(output), "output": output,
        }
    output = completed.stdout + completed.stderr
    return {
        "command": list(spec.argv), "duration_seconds": round(time.monotonic() - started, 3),
        "exit_code": completed.returncode, "timed_out": False,
        "skipped": _skip_count(output),
        "test_count": _test_count(output), "output": output,
    }


def _command_passed(item: dict[str, Any], spec: CommandSpec) -> bool:
    output = str(item.get("output", ""))
    if (item.get("timed_out") or item.get("skipped") != spec.allowed_skips):
        return False
    if spec.requires_tests and (
            not _has_terminal_pytest_summary(output)
            or item.get("test_count", 0) <= 0
            or _error_count(output) != 0):
        return False
    if spec.allowed_failure_nodeids:
        failures = _pytest_failure_nodeids(output)
        if not failures.issubset(set(spec.allowed_failure_nodeids)):
            return False
        return item.get("exit_code") in ({0, 1} if failures else {0})
    if item.get("exit_code") != 0:
        return False
    if spec.allowed_skip_nodeids:
        skipped = _pytest_skips(output)
        if set(skipped) != set(spec.allowed_skip_nodeids):
            return False
        # -vv prints each skipped node ID but omits its reason.  -rs prints
        # reason groups keyed by source line.  The two exact evidence streams
        # are deliberately checked independently below.
        if (spec.allowed_skip_summary_evidence
                and _pytest_skip_summary_evidence(output)
                != {source: (count, reason)
                    for source, count, reason in spec.allowed_skip_summary_evidence}):
            return False
        if (set(spec.allowed_skip_nodeids) == set(OPTIONAL_SKIP_NODEIDS)
                and any(f"::{name} PASSED" not in output
                        for name in OPTIONAL_SKIP_COMPANIONS)):
            return False
    if spec.requires_tests:
        return True
    if spec.expected_output is not None:
        return str(item.get("output", "")).strip() == spec.expected_output
    if spec.name == "causal_mutations":
        try:
            payload = json.loads(str(item.get("output", "")).strip().splitlines()[-1])
        except (IndexError, json.JSONDecodeError):
            return False
        return payload == {"causal_killed": 5, "identity_killed": 1, "survived": 0}
    return True


def _broad_observations(
        commands: dict[str, dict[str, Any]]) -> dict[str, dict[str, list[str]]]:
    return {
        spec.name: {
            "observed_allowed_failure_nodeids": sorted(
                _pytest_failure_nodeids(str(commands[spec.name].get("output", "")))),
            "baseline_nodeids_now_green": sorted(
                set(spec.allowed_failure_nodeids)
                - _pytest_failure_nodeids(str(commands[spec.name].get("output", "")))),
        }
        for spec in BROAD_SPECS
    }


def run_gate(
    output_path: Path,
    *,
    include_postgres: bool = True,
    include_broad: bool = True,
    resume_from: Path | None = None,
) -> dict[str, Any]:
    """Run executable evidence and atomically write its deterministic JSON report."""
    if set(MUTATION_EVIDENCE) != REQUIRED_KILLS:
        raise RuntimeError("required mutation evidence map is incomplete")
    specs = list(REQUIRED_SPECS)
    if include_broad:
        specs.extend(BROAD_SPECS)
    postgres_available = bool(os.environ.get("PT_TEST_POSTGRES_URL"))
    if include_postgres and postgres_available:
        specs.extend(POSTGRES_SPECS)
    prior_report: dict[str, Any] | None = None
    resume_sha256: str | None = None
    if resume_from is not None:
        resume_bytes = resume_from.read_bytes()
        prior_report = json.loads(resume_bytes)
        prior_baseline = prior_report.get("baseline", {})
        if (
            prior_baseline.get("authoritative_checkpoint") != BASELINE_CHECKPOINT
            or prior_baseline.get("allowed_failure_nodeids")
            != list(ALLOWED_BASELINE_FAILURE_NODEIDS)
        ):
            raise RuntimeError("resume report does not match the authoritative baseline")
        resume_sha256 = hashlib.sha256(resume_bytes).hexdigest()
    prior_commands = (prior_report or {}).get("commands", {})
    # This shard contains the gate's own contract tests, so a gate scheduling
    # change always re-executes it. Newly split shards have new names and also
    # execute rather than reuse.
    # A resume is only a bounded replacement for rejected broad shards. Product code may
    # have changed to correct their root cause, so none of the named Phase-3 contracts may
    # be inherited across that correction. The broad shards containing the gate contract
    # and corrected runtime/identity/deployment subsystems are likewise fresh evidence.
    forced = {
        *(spec.name for spec in REQUIRED_SPECS),
        *CORRECTION_FORCED_BROAD_SPECS,
    }
    commands: dict[str, dict[str, Any]] = {}
    reused_commands: list[str] = []
    executed_commands: list[str] = []
    for spec in specs:
        prior = prior_commands.get(spec.name)
        if (
            spec.name not in forced
            and isinstance(prior, dict)
            and prior.get("command") == list(spec.argv)
            and _command_passed(prior, spec)
        ):
            commands[spec.name] = {**prior, "reused_from_report": str(resume_from)}
            reused_commands.append(spec.name)
        else:
            commands[spec.name] = _run(spec)
            executed_commands.append(spec.name)
    if include_postgres and not postgres_available:
        for spec in POSTGRES_SPECS:
            commands[spec.name] = {
                "command": list(spec.argv), "duration_seconds": 0.0, "exit_code": None,
                "timed_out": False, "skipped": 0, "test_count": 0,
                "output": "PT_TEST_POSTGRES_URL unavailable; PostgreSQL closure remains open.",
                "not_run": "environment_unavailable",
            }
    by_name = {spec.name: spec for spec in (*REQUIRED_SPECS, *BROAD_SPECS, *POSTGRES_SPECS)}
    mutations = {
        name: {
            "command": command_name,
            "evidence": selector,
            "killed": _command_passed(commands[command_name], by_name[command_name]),
        }
        for name, (command_name, selector) in sorted(MUTATION_EVIDENCE.items())
    }
    required_ok = all(_command_passed(commands[spec.name], spec) for spec in REQUIRED_SPECS)
    broad_ok = not include_broad or all(
        _command_passed(commands[spec.name], spec) for spec in BROAD_SPECS)
    postgres_ok = not include_postgres or (
        postgres_available and all(
            _command_passed(commands[spec.name], spec) for spec in POSTGRES_SPECS))
    all_killed = all(item["killed"] for item in mutations.values())
    schema_heads = {
        "execution": str(commands["execution_migration_head"]["output"]).strip(),
        "research": str(commands["research_migration_head"]["output"]).strip(),
    }
    status = "passed" if required_ok and broad_ok and postgres_ok and all_killed else (
        "partial" if required_ok and broad_ok and all_killed and not postgres_available
        else "failed")
    report = {
        "schema_version": 3,
        "scope": "Phase 3 causal admission only; not Strategy Preflight or live readiness.",
        "status": status,
        "postgres_required": include_postgres,
        "postgres_available": postgres_available,
        "broad_required": include_broad,
        "resume": {
            "source": str(resume_from) if resume_from is not None else None,
            "source_sha256": resume_sha256,
            "reused_commands": reused_commands,
            "executed_commands": executed_commands,
        },
        # Baseline allowlist RETIRED: recorded as empty so historical consumers
        # keep their schema, and so no stale tolerance can be resurrected.
        "baseline": {
            "authoritative_checkpoint": BASELINE_CHECKPOINT,
            "raw_entry_failure_nodeids": [],
            "excluded_category_c_fixed_nodeids": [],
            "allowed_failure_nodeids": [],
            "retired": True,
        },
        "broad_observed_baseline_failures": (
            _broad_observations(commands) if include_broad else {}),
        "schema_heads": schema_heads,
        "commands": commands,
        "mutations": mutations,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    temporary.replace(output_path)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", required=True, type=Path, metavar="PATH")
    parser.add_argument(
        "--resume-json", type=Path, metavar="PATH",
        help="reuse only exact, individually passing commands from a prior gate report",
    )
    parser.add_argument("--no-broad", action="store_true", help="omit release-boundary suites")
    args = parser.parse_args()
    report = run_gate(
        args.json, include_broad=not args.no_broad, resume_from=args.resume_json)
    print(json.dumps({"status": report["status"], "report": str(args.json)}, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
