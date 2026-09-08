"""Supported-head, mixed-version, and cross-dialect matrix rows."""
from tests.phase4_adversarial_support import run_current_nodes, run_disposable_postgres_nodes


def test_adv_011_finite_direct() -> None:
    run_current_nodes((
        "tests/test_phase4_authority_execution_migration.py::test_adv_011_0037_opaque_rows_remain_legacy_unverified",
        "tests/test_phase4_authority_research_migration.py::test_adv_011_012_actual_0008_refuses_and_keeps_legacy_audit_only",
        "research_tests/test_foundation_direct_migration_0011.py::test_exact_populated_sqlite_0010_preserves_all_rows_sequences_and_bytes",
    ))


def test_adv_012_finite_direct() -> None:
    run_current_nodes((
        "tests/test_phase4_authority_execution_migration.py::test_adv_012_mixed_legacy_and_typed_rows_cannot_cross_authority",
        "tests/test_phase4_authority_research_migration.py::test_adv_011_012_actual_0008_refuses_and_keeps_legacy_audit_only",
        "research_tests/test_foundation_direct_migration_0011.py::test_every_unsupported_sqlite_state_refuses_before_write_with_identical_digest",
    ))


def test_adv_013_finite_direct() -> None:
    run_current_nodes((
        "tests/test_phase4_authority_execution_migration.py::test_adv_013_0039_is_exact_single_head_and_refuses_version_skew_downgrade",
        "tests/test_phase4_authority_research_migration.py::test_adv_013_0011_is_exact_head_and_refuses_destructive_downgrade",
    ))


def test_adv_014_finite_direct_separate_postgresql16_databases() -> None:
    run_current_nodes((
        "tests/test_phase4_authority_execution_migration.py::test_adv_014_0039_sqlite_fresh_migration_matches_model_ddl",
        "tests/test_phase4_authority_research_migration.py::test_adv_014_sqlite_fresh_migration_matches_model_ddl",
        "research_tests/test_foundation_direct_migration_0011.py::test_clean_sqlite_reaches_exact_0011_and_is_deterministic",
    ))
    run_disposable_postgres_nodes((
        "tests/test_phase4_authority_execution_migration.py::test_0038_disposable_postgresql16_fresh_upgrade_restart_model_and_trigger_parity",
    ))
    run_disposable_postgres_nodes((
        "tests/test_phase4_authority_research_migration.py::test_adv_016_disposable_postgresql_fresh_0011_restart_and_hybrid_refusal",
        "tests/test_phase4_authority_research_migration.py::test_postgresql_old_json_constraint_hybrid_refuses_transactionally",
        "research_tests/test_foundation_direct_migration_0011.py::test_clean_postgresql16_reaches_exact_0011_and_is_deterministic",
    ))


def test_adv_015_finite_direct() -> None:
    run_current_nodes((
        "tests/test_phase4_authority_execution_migration.py::test_adv_015_actual_0037_upgrade_restart_preserves_audit_rows",
        "tests/test_phase4_authority_execution_migration.py::test_adv_015_interrupted_0039_rolls_back_then_restarts_at_exact_head",
        "tests/test_phase4_authority_research_migration.py::test_adv_015_retained_0009_refuses_without_marker_only_trust",
        "tests/test_phase4_authority_research_migration.py::test_exact_0009_refusal_preserves_typed_rows_and_json_bytes",
        "research_tests/test_foundation_direct_migration_0011.py::test_sqlite_interruption_is_atomic_and_restart_is_deterministic",
    ))
