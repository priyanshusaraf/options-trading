"""Bounded local resource and cancellation recovery matrix rows."""
from tests.phase4_adversarial_support import run_current_nodes, run_disposable_postgres_nodes


def test_adv_026_full() -> None:
    run_current_nodes((
        "tests/test_phase4_canonical_market_identity.py::test_adv_026_database_write_exhaustion_rolls_back_and_retry_reloads",
        "tests/test_phase4_typed_market_authority.py::test_adv_026_database_failure_never_returns_authority_and_retry_reconstructs",
        "tests/test_phase4_authority_transaction_boundary.py::test_complete_claim_is_a_real_caller_owned_terminal_outbox_boundary[sqlite-rollback]",
        "tests/test_phase4_authority_transaction_boundary.py::test_complete_claim_is_a_real_caller_owned_terminal_outbox_boundary[sqlite-commit-refusal]",
        "tests/test_phase4_authority_transaction_boundary.py::test_complete_claim_is_a_real_caller_owned_terminal_outbox_boundary[sqlite-commit-replay]",
        "tests/test_phase4_authority_transaction_boundary.py::test_ledger_snapshot_real_seam_commits_snapshot_and_outbox_together[sqlite-commit]",
        "tests/test_phase4_authority_transaction_boundary.py::test_ledger_snapshot_real_seam_commits_snapshot_and_outbox_together[sqlite-commit-refusal]",
        "tests/test_instance_lock.py::test_lock_released_on_close_allows_restart",
        "tests/test_ir_shadow_metrics.py::test_memory_stays_bounded_over_a_long_session",
    ))
    run_disposable_postgres_nodes((
        "tests/test_phase4_authority_transaction_boundary.py::test_complete_claim_is_a_real_caller_owned_terminal_outbox_boundary[postgresql-rollback]",
        "tests/test_phase4_authority_transaction_boundary.py::test_complete_claim_is_a_real_caller_owned_terminal_outbox_boundary[postgresql-commit-refusal]",
        "tests/test_phase4_authority_transaction_boundary.py::test_complete_claim_is_a_real_caller_owned_terminal_outbox_boundary[postgresql-commit-replay]",
        "tests/test_phase4_authority_transaction_boundary.py::test_ledger_snapshot_real_seam_commits_snapshot_and_outbox_together[postgresql-commit]",
        "tests/test_phase4_authority_transaction_boundary.py::test_ledger_snapshot_real_seam_commits_snapshot_and_outbox_together[postgresql-commit-refusal]",
    ))


def test_adv_027_full() -> None:
    run_current_nodes((
        "tests/test_phase4_canonical_market_identity.py::test_adv_027_cancellation_unwinds_and_restart_has_no_partial_chain",
        "tests/test_phase4_typed_market_authority.py::test_adv_027_rollback_at_cancellation_boundary_leaves_no_authoritative_prefix",
        "tests/test_phase4_authority_transaction_boundary.py::test_append_claimed_result_batch_is_a_real_caller_owned_boundary[sqlite-rollback]",
        "tests/test_phase4_authority_transaction_boundary.py::test_append_claimed_result_batch_is_a_real_caller_owned_boundary[sqlite-commit-refusal]",
        "tests/test_phase4_authority_transaction_boundary.py::test_append_claimed_result_batch_is_a_real_caller_owned_boundary[sqlite-commit-replay]",
        "tests/test_phase4_authority_transaction_boundary.py::test_complete_claim_is_a_real_caller_owned_terminal_outbox_boundary[sqlite-rollback]",
        "tests/test_phase4_authority_transaction_boundary.py::test_complete_claim_is_a_real_caller_owned_terminal_outbox_boundary[sqlite-commit-refusal]",
        "tests/test_phase4_authority_transaction_boundary.py::test_complete_claim_is_a_real_caller_owned_terminal_outbox_boundary[sqlite-commit-replay]",
        "tests/test_portable_concurrency_integration.py::test_takeover_fences_old_token_and_cancellation_fences_new_token[sqlite]",
        "tests/test_portable_concurrency_integration.py::test_research_claim_has_one_winner_and_cancellation_fences_it[sqlite]",
    ))
    run_disposable_postgres_nodes((
        "tests/test_phase4_authority_transaction_boundary.py::test_append_claimed_result_batch_is_a_real_caller_owned_boundary[postgresql-rollback]",
        "tests/test_phase4_authority_transaction_boundary.py::test_append_claimed_result_batch_is_a_real_caller_owned_boundary[postgresql-commit-refusal]",
        "tests/test_phase4_authority_transaction_boundary.py::test_append_claimed_result_batch_is_a_real_caller_owned_boundary[postgresql-commit-replay]",
        "tests/test_phase4_authority_transaction_boundary.py::test_complete_claim_is_a_real_caller_owned_terminal_outbox_boundary[postgresql-rollback]",
        "tests/test_phase4_authority_transaction_boundary.py::test_complete_claim_is_a_real_caller_owned_terminal_outbox_boundary[postgresql-commit-refusal]",
        "tests/test_phase4_authority_transaction_boundary.py::test_complete_claim_is_a_real_caller_owned_terminal_outbox_boundary[postgresql-commit-replay]",
        "tests/test_portable_concurrency_integration.py::test_takeover_fences_old_token_and_cancellation_fences_new_token[postgresql]",
        "tests/test_portable_concurrency_integration.py::test_research_claim_has_one_winner_and_cancellation_fences_it[postgresql]",
    ))
