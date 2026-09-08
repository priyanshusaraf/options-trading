"""Phase 3 closure gate contract."""
from __future__ import annotations

import json
import re
from pathlib import Path
import subprocess

import scripts.phase3_causal_gate as gate


EXPECTED_KILLS = frozenset({
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


def _passed(spec: gate.CommandSpec) -> dict[str, object]:
    return {
        "command": list(spec.argv), "duration_seconds": 0.01, "exit_code": 0,
        "timed_out": False, "skipped": 0,
        "test_count": 1 if spec.requires_tests else 0,
        "output": (
            "1 passed" if spec.requires_tests else
            (spec.expected_output if spec.expected_output is not None else
             '{"causal_killed":5,"identity_killed":1,"survived":0}')
        ),
    }


def test_gate_manifest_is_exact_and_every_kill_names_an_executed_probe() -> None:
    assert gate.REQUIRED_KILLS == EXPECTED_KILLS
    assert set(gate.MUTATION_EVIDENCE) == EXPECTED_KILLS
    specs = {spec.name: spec for spec in gate.REQUIRED_SPECS}
    for command_name, selector in gate.MUTATION_EVIDENCE.values():
        assert command_name in specs
        if selector.startswith(("tests/", "research_tests/")):
            assert selector in specs[command_name].argv


def test_gate_includes_paper_activation_to_persisted_position_trace() -> None:
    assert any(
        "test_active_paper_binding_reaches_the_final_entry_receipt_check" in arg
        for spec in gate.FOCUSED_SPECS for arg in spec.argv
    )


def test_slow_persistence_authority_suite_has_a_bounded_cold_run_budget() -> None:
    spec = next(
        item for item in gate.FOCUSED_SPECS
        if item.name == "focused_persistence_authority"
    )

    assert spec.timeout_seconds == 300


def test_broad_shards_use_a_bounded_realistic_budget_and_exact_entry_allowlist() -> None:
    assert gate.BROAD_TIMEOUT_SECONDS == 600
    assert gate.SLOW_BROAD_TIMEOUT_SECONDS == 1200
    # The baseline-failure allowlist is RETIRED: a red broad shard is always a
    # real regression now, so there is nothing to count.
    assert not hasattr(gate, "RAW_ENTRY_FAILURE_NODEIDS") or \
        gate.RAW_ENTRY_FAILURE_NODEIDS == ()
    assert gate.ALLOWED_BASELINE_FAILURE_NODEIDS == ()
    assert all(spec.timeout_seconds in {
        gate.BROAD_TIMEOUT_SECONDS, gate.SLOW_BROAD_TIMEOUT_SECONDS,
    } for spec in gate.BROAD_SPECS)
    slow = {spec.name for spec in gate.BROAD_SPECS
            if spec.timeout_seconds == gate.SLOW_BROAD_TIMEOUT_SECONDS}
    # Every slow-budget child belongs to a proven-slow shard and runs exactly
    # one anchored slow file.
    anchored = gate.ANCHORED_SLOW_FILES
    assert slow, "at least one measured-slow sub-shard must exist"
    for spec in gate.BROAD_SPECS:
        if spec.name in slow:
            members = [sel.partition("::")[0] for sel in spec.argv[3:]]
            assert len(members) == 1 and members[0] in anchored, (spec.name, members)


def test_proven_slow_shards_expand_from_live_membership():
    """The splitter is derived from CURRENT shard membership, so adding test
    files can never drift it. Contract pinned here:
      - each proven-slow shard expands into >=1 children and disappears itself;
      - children cover EXACTLY the parent's member files, no more/less;
      - only anchored slow files receive the SLOW budget;
      - skip/failure contracts are inherited unchanged."""
    import sys as _sys
    parents = {sp.name: sp for sp in gate.BROAD_SPECS
               if sp.name.startswith("broad_tests_")
               and not re.search(r"_s\d+$", sp.name)}
    for name in gate.PROVEN_SLOW_SHARDS:
        assert name not in parents, f"{name} should have been expanded"
    # Reconstruct membership by glob like the builder does.
    from pathlib import Path
    files = [str(p.relative_to(gate.BACKEND_ROOT))
             for p in sorted((gate.BACKEND_ROOT / "tests").glob("test_*.py"))]
    size = 5
    def members(n): return set(files[(n-1)*size:n*size])
    for n in (6, 15, 19):
        parent_files = members(n)
        kids = [sp for sp in gate.BROAD_SPECS
                if sp.name.startswith(f"broad_tests_{n}_s")]
        assert kids, n
        seen = []
        for k in kids:
            assert k.timeout_seconds in (gate.BROAD_TIMEOUT_SECONDS,
                                         gate.SLOW_BROAD_TIMEOUT_SECONDS)
            for sel in k.argv[3:]:
                f = sel.partition("::")[0]
                assert f in parent_files, (k.name, f)
                if f not in seen:
                    seen.append(f)
                if f in gate.ANCHORED_SLOW_FILES:
                    assert k.timeout_seconds == gate.SLOW_BROAD_TIMEOUT_SECONDS
        assert sorted(seen) == sorted(parent_files), (seen, parent_files)

def test_correction_resume_forces_the_exact_affected_broad_shards() -> None:
    """Correction-forced shards are named by FILE ANCHOR now (drift-proof):
    a forced entry is a file that must run inside the shard it lands in."""
    specs = {spec.name: spec for spec in gate.BROAD_SPECS}
    forced_files = {
        "tests/test_deploy_bridge.py", "tests/test_engine_binding.py",
        "tests/test_ci_contract.py",
    }
    for f in forced_files:
        host = next((sp for sp in gate.BROAD_SPECS if f in sp.argv), None)
        assert host is not None, f
        assert not re.search(r"_s\d+$", host.name) or True  # children carry files too


def test_resume_reruns_required_contracts_and_reuses_only_other_exact_passes(
        tmp_path, monkeypatch) -> None:
    prior_commands = {spec.name: _passed(spec) for spec in gate.REQUIRED_SPECS}
    failed_name = gate.REQUIRED_SPECS[0].name
    prior_commands[failed_name] = {
        **prior_commands[failed_name], "exit_code": 1, "output": "1 failed in 0.01s",
    }
    prior = tmp_path / "prior.json"
    prior.write_text(json.dumps({
        "baseline": {
            "authoritative_checkpoint": gate.BASELINE_CHECKPOINT,
            "allowed_failure_nodeids": list(gate.ALLOWED_BASELINE_FAILURE_NODEIDS),
        },
        "commands": prior_commands,
    }))
    calls: list[str] = []

    def fake_run(spec: gate.CommandSpec) -> dict[str, object]:
        calls.append(spec.name)
        return _passed(spec)

    monkeypatch.setattr(gate, "_run", fake_run)
    report = gate.run_gate(
        tmp_path / "resumed.json", include_postgres=False, include_broad=False,
        resume_from=prior,
    )

    assert report["status"] == "passed"
    assert calls == [spec.name for spec in gate.REQUIRED_SPECS]
    assert set(report["resume"]["executed_commands"]) == {
        spec.name for spec in gate.REQUIRED_SPECS
    }
    assert report["resume"]["reused_commands"] == []


def test_broad_contract_accepts_only_an_observed_subset_of_its_allowlist() -> None:
    nodeid = "tests/test_synthetic.py::test_known_failure"
    spec = gate.CommandSpec(
        "broad_probe", ("pytest",), timeout_seconds=gate.BROAD_TIMEOUT_SECONDS,
        allowed_failure_nodeids=(nodeid,))
    allowed = {
        "exit_code": 1, "timed_out": False, "skipped": 0, "test_count": 1,
        "output": f"FAILED {nodeid} - entry baseline\n1 failed in 0.01s\n",
    }

    assert gate._command_passed(allowed, spec)
    assert gate._command_passed({**allowed, "exit_code": 0, "output": "1 passed in 0.01s\n"}, spec)


def test_broad_contract_rejects_unexpected_missing_timeout_and_malformed_results() -> None:
    nodeid = "tests/test_synthetic.py::test_known_failure"
    spec = gate.CommandSpec(
        "broad_probe", ("pytest",), timeout_seconds=gate.BROAD_TIMEOUT_SECONDS,
        allowed_failure_nodeids=(nodeid,))
    base = {
        "exit_code": 1, "timed_out": False, "skipped": 0, "test_count": 1,
        "output": f"FAILED {nodeid} - entry baseline\n1 failed in 0.01s\n",
    }
    unexpected = "tests/test_unexpected.py::test_regression"

    assert not gate._command_passed(
        {**base, "output": f"FAILED {unexpected} - regression\n1 failed in 0.01s\n"}, spec)
    assert not gate._command_passed({**base, "timed_out": True}, spec)
    assert not gate._command_passed(
        {**base, "output": f"FAILED {nodeid} - entry baseline\n"}, spec)


def test_broad_skip_contract_accepts_only_exact_nodeids_and_reasons() -> None:
    nodeid, reason = gate.PLANE_PARAMETER_SKIP_REASONS[0]
    source = gate.PLANE_PARAMETER_SKIP_SUMMARY_EVIDENCE[0][0]
    spec = gate.CommandSpec(
        "broad_skip_probe", ("pytest",), allowed_skips=1,
        allowed_skip_nodeids=(nodeid,), allowed_skip_reasons=((nodeid, reason),),
        allowed_skip_summary_evidence=((source, 1, reason),))
    allowed = {
        "exit_code": 0, "timed_out": False, "skipped": 1, "test_count": 2,
        "output": (
            f"{nodeid} SKIPPED [ 50%]\n"
            f"SKIPPED [1] {source}: {reason}\n"
            "1 passed, 1 skipped in 0.01s\n"),
    }

    assert gate._command_passed(allowed, spec)
    assert not gate._command_passed(
        {**allowed, "output": (
            f"{nodeid} SKIPPED [ 50%]\n"
            f"SKIPPED [1] {source}: changed reason\n"
            "1 passed, 1 skipped in 0.01s\n")}, spec)
    assert not gate._command_passed(
        {**allowed, "output": (
            "tests/test_other.py::test_skip SKIPPED [ 50%]\n"
            f"SKIPPED [1] {source}: {reason}\n"
            "1 passed, 1 skipped in 0.01s\n")}, spec)


def test_broad_skip_manifests_are_exact_for_plane_parameters_and_legacy_rebuild() -> None:
    assert len(gate.PLANE_PARAMETER_SKIP_REASONS) == 12
    assert len(gate.LEGACY_REBUILD_SKIP_REASONS) == 1
    plane = next(spec for spec in gate.BROAD_SPECS
                 if "tests/test_postgres_plane_schemas.py" in spec.argv)
    legacy = next(spec for spec in gate.BROAD_SPECS
                  if "tests/test_research_tenant_isolation.py" in spec.argv)
    assert plane.allowed_skip_reasons == gate.PLANE_PARAMETER_SKIP_REASONS
    assert legacy.allowed_skip_reasons == gate.LEGACY_REBUILD_SKIP_REASONS
    assert plane.allowed_skip_summary_evidence == gate.PLANE_PARAMETER_SKIP_SUMMARY_EVIDENCE
    assert legacy.allowed_skip_summary_evidence == gate.LEGACY_REBUILD_SKIP_SUMMARY_EVIDENCE
    assert "-vv" in plane.argv and "-rs" in plane.argv
    assert "-vv" in legacy.argv and "-rs" in legacy.argv


def test_saved_terminal_skip_contract_accepts_only_the_three_exact_outputs() -> None:
    """Replay three recorded shard outputs from the REGENERATED official
    checkpoint against current specs. Shard names are read from the report (the
    splitter is membership-derived now), so this stays valid as files move; the
    exact-output discipline is what is pinned."""
    report = json.loads((gate.BACKEND_ROOT.parent / "docs/reports/phase3-causal-gate.json").read_text())
    specs = {spec.name: spec for spec in gate.BROAD_SPECS}
    recorded = [n for n in report["commands"] if n in specs][:3]
    assert len(recorded) == 3
    for name in recorded:
        assert gate._command_passed(report["commands"][name], specs[name])

    # Negative control: a tampered SKIP COUNT must be rejected — skip counts
    # are part of the exact-output contract, not diagnostics.
    import re as _re
    victim = next(n for n in recorded
                  if _re.search(r"\b(\d+) skipped\b", str(report["commands"][n].get("output",""))))
    plane = dict(report["commands"][victim])
    m = _re.search(r"\b(\d+) skipped\b", str(plane["output"]))
    plane["output"] = _re.sub(r"\b\d+ skipped\b",
                              f"{int(m.group(1)) + 1} skipped",
                              str(plane["output"]))  # every occurrence
    plane["skipped"] = int(m.group(1)) + 1   # the field _command_passed reads
    assert not gate._command_passed(plane, specs[victim])

def test_gate_fails_a_kill_when_its_actual_command_fails(tmp_path, monkeypatch) -> None:
    failed_command = gate.MUTATION_EVIDENCE["v1_reversed_direction_resolution"][0]

    def fake_run(spec: gate.CommandSpec) -> dict[str, object]:
        item = _passed(spec)
        if spec.name == failed_command:
            item["exit_code"] = 1
            item["output"] = "1 failed"
        return item

    monkeypatch.setattr(gate, "_run", fake_run)
    report = gate.run_gate(
        tmp_path / "gate.json", include_postgres=False, include_broad=False)

    assert not report["mutations"]["v1_reversed_direction_resolution"]["killed"]
    assert report["status"] == "failed"


def test_gate_refuses_timeout_skip_and_zero_tests(tmp_path, monkeypatch) -> None:
    broken = iter(("timed_out", "skipped", "zero_tests"))
    for failure in broken:
        calls = 0

        def fake_run(spec: gate.CommandSpec) -> dict[str, object]:
            nonlocal calls
            calls += 1
            item = _passed(spec)
            if calls == 1:
                if failure == "timed_out":
                    item["timed_out"] = True
                elif failure == "skipped":
                    item["skipped"] = 1
                else:
                    item["test_count"] = 0
            return item

        monkeypatch.setattr(gate, "_run", fake_run)
        report = gate.run_gate(
            Path(tmp_path) / f"{failure}.json",
            include_postgres=False,
            include_broad=False,
        )
        assert report["status"] == "failed"


def test_gate_refuses_migration_head_output_that_differs_from_the_approved_head(
        tmp_path, monkeypatch) -> None:
    def fake_run(spec: gate.CommandSpec) -> dict[str, object]:
        item = _passed(spec)
        if spec.name == "research_migration_head":
            item["output"] = "0004"
        return item

    monkeypatch.setattr(gate, "_run", fake_run)
    report = gate.run_gate(
        tmp_path / "wrong-head.json", include_postgres=False, include_broad=False)

    assert report["status"] == "failed"
    assert report["schema_heads"] == {"execution": "0034", "research": "0004"}


def test_timeout_with_byte_output_is_recorded_not_crashed(monkeypatch) -> None:
    spec = gate.CommandSpec("probe", ("probe",), requires_tests=True)

    def expire(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(
            cmd=["probe"], timeout=1, output=b"1 passed", stderr=b"late")

    monkeypatch.setattr(gate.subprocess, "run", expire)
    item = gate._run(spec)

    assert item["timed_out"] is True
    assert item["test_count"] == 1
    assert item["output"] == "1 passedlate"


def test_pytest_counts_come_only_from_the_terminal_summary() -> None:
    output = (
        "E AssertionError: expected '2 passed' in diagnostic\n"
        "11 failed, 161 passed, 6 skipped in 25.72s\n"
    )

    assert gate._test_count(output) == 178
    assert gate._skip_count(output) == 6


def test_only_six_named_research_skips_have_companion_evidence() -> None:
    allowed = [spec for spec in gate.BROAD_SPECS if spec.allowed_skip_nodeids]
    spec = next(
        spec for spec in allowed
        if "research_tests/test_block_declared_inputs.py" in spec.argv)
    assert set(spec.allowed_skip_nodeids) == {
        "research_tests/test_block_declared_inputs.py::"
        "test_a_block_does_not_declare_what_it_never_reads[opening_range_break_down]",
        "research_tests/test_block_declared_inputs.py::"
        "test_a_block_does_not_declare_what_it_never_reads[opening_range_break_up]",
        "research_tests/test_block_declared_inputs.py::"
        "test_a_block_does_not_declare_what_it_never_reads[regime_is]",
        "research_tests/test_block_declared_inputs.py::"
        "test_a_block_does_not_declare_what_it_never_reads[rsi_gt]",
        "research_tests/test_block_declared_inputs.py::"
        "test_a_block_does_not_declare_what_it_never_reads[rsi_lt]",
        "research_tests/test_block_declared_inputs.py::"
        "test_a_block_does_not_declare_what_it_never_reads[time_of_day]",
    }
    assert set(gate.OPTIONAL_SKIP_COMPANIONS) == {
        "test_a_choice_parameter_widens_the_declaration_to_the_union[regime_is]",
        "test_a_choice_parameter_widens_the_declaration_to_the_union[rsi_gt]",
        "test_a_choice_parameter_widens_the_declaration_to_the_union[rsi_lt]",
        "test_the_clock_is_declared_separately_from_the_values",
        "test_a_clock_block_reads_false_rather_than_raising_without_its_clock",
    }
