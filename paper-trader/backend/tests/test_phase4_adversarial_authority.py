"""Authority, identity, cache, tenancy, time, and bound matrix rows."""
from tests.phase4_adversarial_support import run_current_nodes, run_disposable_postgres_nodes


ROWS = {
    "001": (
        "tests/test_phase4_authority_integration.py::test_real_two_plane_process_death_reconstruction_and_terminal_refusal",
        "tests/test_phase4_canonical_market_identity.py::test_adv_001_fresh_interpreter_reloads_exact_dependency_bytes",
        "tests/test_phase4_typed_market_authority.py::test_adv_001_fresh_process_reconstructs_exact_bytes_addresses_and_copied_columns",
    ),
    "004": (
        "tests/test_ir_v2_admission_receipt.py::test_v2_persistence_is_deterministic_idempotent_and_owner_scoped",
        "tests/test_strategy_admission_repository.py::test_owner_scope_and_exact_duplicate_are_safe",
        "tests/test_strategy_admission_repository.py::test_same_owner_address_with_different_bytes_refuses",
        "research_tests/test_phase4_v2_graph_persistence.py::test_research_exact_retries_owner_isolation_and_identity_collision_refuse",
        "tests/test_phase4_authority_integration.py::test_current_research_retry_collision_and_owner_local_loader_isolation",
    ),
    "005": (
        "tests/test_backtest_pinned_worker_reads.py::test_phase4_worker_refuses_before_provider_pinned_store_cache_or_strategy",
        "tests/test_backtest_pinned_worker_reads.py::test_missing_dataset_fails_closed_in_a_worker",
        "tests/test_backtest_pinned_worker_reads.py::test_revised_content_fails_closed_in_a_worker",
        "research_tests/test_phase4_v2_receipt_authority.py::test_research_process_reload_refuses_tampered_receipt_identity",
    ),
    "006": (
        "tests/test_phase4_reclaim_authority_context.py::test_real_persisted_two_plane_public_reclaim_refuses_before_claim",
        "tests/test_phase4_reclaim_authority_context.py::test_fresh_interpreter_reconstructs_context_for_real_public_v2_refusal",
        "tests/test_phase4_reclaim_authority_context.py::test_unknown_frozen_receipt_refuses_before_the_first_legacy_claim",
        "tests/test_phase4_reclaim_authority_context.py::test_mixed_v2_and_unknown_refuse_before_v2_loader_or_mutation",
    ),
    "007": (
        "tests/test_phase4_dataset_assessment_authority.py::test_writer_death_fresh_interpreter_reconstructs_admission_and_cold_warm_cache",
        "tests/test_backtest_cache.py::test_phase4_sweep_is_cold_then_warm_but_never_cross_owner",
        "tests/test_phase4_cache_identity.py::test_cache_identity_binds_every_answer_changing_phase4_digest",
    ),
    "008": (
        "tests/test_phase4_cache_identity.py::test_result_binding_validator_matches_cache_identity_contract",
        "tests/test_phase4_cache_identity.py::test_execution_result_address_binds_phase4_facts_and_refuses_bad_bindings",
        "tests/test_backtest_pinned_worker_reads.py::test_a_refused_dataset_beats_a_reusable_result_row",
    ),
    "009": (
        "tests/test_phase4_canonical_market_identity.py::test_adv_009_malformed_serialized_state_is_closed_before_authority",
        "tests/test_phase4_typed_market_authority.py::test_adv_009_malformed_and_noncanonical_stored_evidence_refuses",
        "research_tests/test_phase4_research_json_shape_parity.py::test_real_tables_accept_declared_shapes_and_refuse_every_other_shape[sqlite]",
        "tests/test_phase4_capability_admission.py::test_both_writers_refuse_invalid_typed_assessment_envelopes",
    ),
    "010": (
        "tests/test_phase4_canonical_market_identity.py::test_adv_010_hostile_values_refuse_or_have_distinct_bounded_identity",
        "tests/test_phase4_typed_market_authority.py::test_adv_010_hostile_temporal_and_cardinality_bounds_refuse",
    ),
    "016": (
        "tests/test_phase4_canonical_market_identity.py::test_adv_016_missing_catalogue_and_provider_dependencies_refuse",
        "tests/test_phase4_typed_market_authority.py::test_adv_016_missing_or_unverified_authority_dependency_refuses",
        "tests/test_phase4_typed_market_authority.py::test_adv_016_missing_authority_addresses_refuse",
        "tests/test_phase4_loader_authority_consumers.py::test_enqueue_consumer_refuses_before_durable_job",
        "tests/test_phase4_loader_authority_consumers.py::test_broker_consumer_refuses_before_money_side_effect",
    ),
    "017": (
        "tests/test_phase4_canonical_market_identity.py::test_adv_017_identical_facts_converge_and_alias_collision_refuses",
        "tests/test_phase4_resolved_topology_identity.py::test_adv_017_canonical_bytes_converge_and_distinct_topology_bytes_diverge",
        "tests/test_phase4_data_requirement_registry.py::test_structured_attribution_avoids_slash_and_colon_collisions",
        "tests/test_phase4_data_requirement_registry.py::test_forged_structured_attribution_and_joined_slash_path_collision_refuse",
    ),
    "018": (
        "tests/test_phase4_canonical_market_identity.py::test_adv_018_forged_address_and_copied_columns_refuse",
        "tests/test_phase4_typed_market_authority.py::test_adv_018_forged_address_or_copied_column_refuses",
        "tests/test_phase4_resolved_topology_identity.py::test_adv_018_forged_topology_document_and_outer_address_refuse",
        "tests/test_phase4_capability_admission.py::test_both_persistence_seams_refuse_self_consistent_phase4_lookalike_with_forged_assessment_address",
    ),
    "019": (
        "tests/test_phase4_resolved_topology_identity.py::test_adv_019_real_writer_exit_fresh_loader_stale_refusal_then_runtime_boundary",
        "tests/test_phase4_dataset_assessment_authority.py::test_manifest_transitive_authority_changes_identity",
        "tests/test_phase4_capability_admission.py::test_reconstruction_refuses_self_consistent_noncanonical_assessment",
        "tests/test_phase4_authority_integration.py::test_current_reusable_equity_scenario_keeps_identity_truth_manifest_and_cache_separate",
    ),
    "020": (
        "tests/test_phase4_canonical_market_identity.py::test_adv_020_deleted_dependency_refuses_and_replacement_mints_address",
        "tests/test_phase4_typed_market_authority.py::test_adv_020_wrong_provider_dependency_bytes_under_requested_address_refuse",
        "tests/test_phase4_resolved_topology_identity.py::test_adv_020_missing_current_implementation_refuses_before_runtime",
        "tests/test_backtest_pinned_worker_reads.py::test_revised_content_fails_closed_in_a_worker",
    ),
    "021": (
        "tests/test_phase4_canonical_market_identity.py::test_adv_021_independent_sessions_alias_race_has_one_winner",
        "tests/test_portable_concurrency_integration.py::test_two_sessions_have_one_claim_winner[sqlite]",
        "tests/test_portable_concurrency_integration.py::test_takeover_fences_old_token_and_cancellation_fences_new_token[sqlite]",
        "tests/test_portable_concurrency_integration.py::test_research_claim_has_one_winner_and_cancellation_fences_it[sqlite]",
    ),
    "022": (
        "tests/test_phase4_canonical_market_identity.py::test_adv_022_owner_product_contract_underlier_substitutions_refuse",
        "tests/test_phase4_typed_market_authority.py::test_adv_022_wrong_owner_mode_product_or_contract_substitution_refuses",
        "tests/test_backtest_cache.py::test_phase4_sweep_is_cold_then_warm_but_never_cross_owner",
        "tests/test_phase4_authority_integration.py::test_current_research_retry_collision_and_owner_local_loader_isolation",
    ),
    "023": (
        "tests/test_phase4_canonical_market_identity.py::test_adv_023_timezone_conversion_is_stable_and_causality_refuses",
        "tests/test_phase4_typed_market_authority.py::test_adv_023_future_recorded_truth_and_stale_or_future_profile_refuse",
        "tests/test_phase4_alignment_causality.py::test_alignment_refuses_forming_future_stale_and_skewed_observations",
        "tests/test_phase4_alignment_causality.py::test_future_append_does_not_change_prior_alignment",
        "tests/test_phase4_authority_timestamp_normalization.py::test_database_neutral_authority_timestamp_lifecycle",
    ),
    "024": (
        "tests/test_phase4_resolved_topology_identity.py::test_adv_024_empty_graph_has_typed_complete_identity",
        "tests/test_phase4_typed_market_authority.py::test_adv_024_explicit_empty_capability_is_unknown_and_absent_conformance_refuses",
        "tests/test_phase4_data_requirement_registry.py::test_explicit_no_data_compiles_while_absent_declaration_only_resolves",
    ),
    "025": (
        "tests/test_phase4_resolved_topology_identity.py::test_adv_025_huge_graph_refuses_at_preflight_limit",
        "tests/test_phase4_resolved_topology_identity.py::test_adv_025_huge_boundary_refuses_at_preflight_limit",
        "tests/test_phase4_resolved_topology_identity.py::test_adv_025_deep_compound_chain_refuses_without_recursion_error",
        "tests/test_phase4_resolved_topology_identity.py::test_adv_025_compound_depth_acceptance_boundary_is_safe_and_next_refuses",
        "tests/test_phase4_canonical_market_identity.py::test_adv_025_oversized_documents_segments_and_inputs_refuse",
        "tests/test_phase4_typed_market_authority.py::test_adv_025_ten_thousand_offer_limit_is_closed",
    ),
}


def _run(row: str) -> None:
    run_current_nodes(ROWS[row])


def test_adv_001_full(): _run("001")
def test_adv_004_full(): _run("004")
def test_adv_005_full(): _run("005")
def test_adv_006_full_containment_only_p5_adv_006_runtime_unproved(): _run("006")
def test_adv_007_full(): _run("007")
def test_adv_008_full(): _run("008")
def test_adv_009_full(): _run("009")
def test_adv_010_full(): _run("010")
def test_adv_016_full(): _run("016")
def test_adv_017_full(): _run("017")
def test_adv_018_full(): _run("018")
def test_adv_019_full(): _run("019")
def test_adv_020_full(): _run("020")
def test_adv_021_full():
    _run("021")
    run_disposable_postgres_nodes((
        "tests/test_portable_concurrency_integration.py::test_two_sessions_have_one_claim_winner[postgresql]",
        "tests/test_portable_concurrency_integration.py::test_takeover_fences_old_token_and_cancellation_fences_new_token[postgresql]",
        "tests/test_portable_concurrency_integration.py::test_research_claim_has_one_winner_and_cancellation_fences_it[postgresql]",
    ))
def test_adv_022_full(): _run("022")
def test_adv_023_full(): _run("023")
def test_adv_024_full(): _run("024")
def test_adv_025_full(): _run("025")
