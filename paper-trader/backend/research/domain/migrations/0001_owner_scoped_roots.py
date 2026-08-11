"""Make research roots owner-scoped without coupling to application Alembic."""

VERSION = "0001"

# Migration 0001 is intentionally bound to this pre-Task 1B.1 table/column
# contract.  The runner hashes names, types, nullability, defaults, PKs, unique
# constraints, foreign keys, indexes and immutable triggers before it calls this
# migration. Future metadata changes need a new migration rather than silently
# changing the historical rebuild's meaning.
TABLE_SIGNATURE = {
    "research_block_edge": (
        "owner_id", "block_name", "instrument_key", "positive", "negative", "last_run_id", "updated_at",
    ),
    "research_generated_strategy": (
        "owner_id", "key", "composition_json", "source", "created_at",
    ),
    "research_program": ("id", "owner_id", "name", "thesis", "status", "created_at"),
    "research_hypothesis": (
        "id", "owner_id", "program_id", "statement", "status", "retest_priority",
        "last_tested_at", "created_at",
    ),
    "research_experiment_spec": (
        "owner_id", "id", "hypothesis_id", "parent_spec_id", "recipe_json", "git_commit",
        "qualifier_version", "optimizer_version", "validator_version", "scoring_version",
        "rng_seed", "created_at",
    ),
    "research_experiment_run": (
        "id", "owner_id", "spec_id", "status", "decision", "spent_bar_seconds",
        "checkpoint_json", "error", "started_at", "completed_at", "created_at",
    ),
    "research_finding": (
        "id", "owner_id", "hypothesis_id", "statement", "polarity", "confidence",
        "evidence_run_id", "superseded_by", "created_at",
    ),
    "research_promotion_candidate": (
        "id", "owner_id", "run_id", "parameterization_hash", "qualifying_universe_json",
        "scorecard_json", "status", "approved_git_sha", "created_at",
    ),
    "research_optimization_trial": (
        "id", "owner_id", "run_id", "instrument_key", "fold_index", "params_json", "is_objective",
        "is_trades", "oos_trades", "selected", "created_at",
    ),
    "research_shadow_session": (
        "id", "owner_id", "candidate_id", "session_date", "instrument_key", "trades", "wins",
        "net_pnl", "created_at",
    ),
}

# Filled from the deterministic complete contract represented by TABLE_SIGNATURE
# and the frozen model metadata at the time 0001 was introduced.  Kept separate
# from the explanatory table map so a reviewer can inspect the covered shape.
SCHEMA_DIGEST = "105bb87242135b9ebb404910242470c53598290f2d36a9415d3e2f2ec0f05830"


def upgrade(connection, rebuild, *, schema_digest) -> None:
    """Run the durable owner-scoping rebuild supplied by the migration runner."""
    if schema_digest != SCHEMA_DIGEST:
        raise RuntimeError("0001 owner-scoping contract does not match live metadata")
    rebuild(connection)
