"""Add closed Phase 4 authority facts without promoting opaque legacy rows.

Revision ID: 0038
Revises: 0037
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None


# Frozen /1 alias storage: replaying0038 must never create a successor schema.
ALIAS_DDL = {'sqlite': ["\nCREATE TABLE authority_provider_aliases (\n\taddress VARCHAR(71) NOT NULL, \n\tschema VARCHAR(64) NOT NULL, \n\tcanonical_json TEXT NOT NULL, \n\tproduct_address VARCHAR(71) NOT NULL, \n\tinstrument_address VARCHAR(71) NOT NULL, \n\tprovider_token VARCHAR(256) NOT NULL, \n\tprovider_symbol VARCHAR(256) NOT NULL, \n\tobservation_namespace VARCHAR(128) NOT NULL, \n\teffective_from DATETIME NOT NULL, \n\teffective_to DATETIME, \n\tauthority_state VARCHAR(24) DEFAULT 'VERIFIED_V2' NOT NULL, \n\tcreated_at DATETIME NOT NULL, \n\tPRIMARY KEY (address), \n\tFOREIGN KEY(product_address) REFERENCES authority_provider_products (address), \n\tFOREIGN KEY(instrument_address) REFERENCES authority_canonical_instruments (address), \n\tCONSTRAINT ck_authority_provider_alias_interval CHECK (effective_to IS NULL OR effective_to > effective_from), \n\tCONSTRAINT uq_authority_provider_alias_token UNIQUE (product_address, observation_namespace, provider_token, effective_from),\n\tCONSTRAINT ck_authority_provider_aliases_address CHECK (length(address) = 71 AND substr(address, 1, 7) = 'sha256:' AND substr(address, 8) = lower(substr(address, 8)) AND substr(address, 8) NOT GLOB '*[^0-9a-f]*'), \n\tCONSTRAINT ck_authority_provider_aliases_json CHECK (json_valid(canonical_json)), \n\tCONSTRAINT ck_authority_provider_aliases_verified CHECK (authority_state = 'VERIFIED_V2')\n)\n\n\n", "CREATE TRIGGER authority_provider_aliases_refuse_update BEFORE UPDATE ON authority_provider_aliases BEGIN SELECT RAISE(ABORT, 'authority_provider_aliases is immutable'); END", "CREATE TRIGGER authority_provider_aliases_refuse_delete BEFORE DELETE ON authority_provider_aliases BEGIN SELECT RAISE(ABORT, 'authority_provider_aliases is immutable'); END", "CREATE TRIGGER authority_provider_aliases_refuse_overlap BEFORE INSERT ON authority_provider_aliases BEGIN SELECT CASE WHEN EXISTS (SELECT 1 FROM authority_provider_aliases AS existing WHERE existing.product_address = NEW.product_address AND existing.observation_namespace = NEW.observation_namespace AND (existing.provider_token = NEW.provider_token OR existing.provider_symbol = NEW.provider_symbol OR existing.instrument_address = NEW.instrument_address) AND (existing.effective_to IS NULL OR NEW.effective_from < existing.effective_to) AND (NEW.effective_to IS NULL OR existing.effective_from < NEW.effective_to)) THEN RAISE(ABORT, 'authority provider alias overlaps') END; END"], 'postgresql': ["\nCREATE TABLE authority_provider_aliases (\n\taddress VARCHAR(71) NOT NULL, \n\tschema VARCHAR(64) NOT NULL, \n\tcanonical_json TEXT NOT NULL, \n\tproduct_address VARCHAR(71) NOT NULL, \n\tinstrument_address VARCHAR(71) NOT NULL, \n\tprovider_token VARCHAR(256) NOT NULL, \n\tprovider_symbol VARCHAR(256) NOT NULL, \n\tobservation_namespace VARCHAR(128) NOT NULL, \n\teffective_from TIMESTAMP WITHOUT TIME ZONE NOT NULL, \n\teffective_to TIMESTAMP WITHOUT TIME ZONE, \n\tauthority_state VARCHAR(24) DEFAULT 'VERIFIED_V2' NOT NULL, \n\tcreated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, \n\tPRIMARY KEY (address), \n\tFOREIGN KEY(product_address) REFERENCES authority_provider_products (address), \n\tFOREIGN KEY(instrument_address) REFERENCES authority_canonical_instruments (address), \n\tCONSTRAINT ck_authority_provider_alias_interval CHECK (effective_to IS NULL OR effective_to > effective_from), \n\tCONSTRAINT uq_authority_provider_alias_token UNIQUE (product_address, observation_namespace, provider_token, effective_from),\n\tCONSTRAINT ck_authority_provider_aliases_address CHECK (address ~ '^sha256:[0-9a-f]{64}$'), \n\tCONSTRAINT ck_authority_provider_aliases_json CHECK (CAST(canonical_json AS JSONB) IS NOT NULL), \n\tCONSTRAINT ck_authority_provider_aliases_verified CHECK (authority_state = 'VERIFIED_V2')\n)\n\n\n", "CREATE OR REPLACE FUNCTION authority_provider_aliases_refuse_mutation() RETURNS trigger AS $$ BEGIN RAISE EXCEPTION 'authority_provider_aliases is immutable'; END; $$ LANGUAGE plpgsql", 'CREATE TRIGGER authority_provider_aliases_refuse_mutation BEFORE UPDATE OR DELETE ON authority_provider_aliases FOR EACH ROW EXECUTE FUNCTION authority_provider_aliases_refuse_mutation()', "CREATE OR REPLACE FUNCTION authority_provider_aliases_refuse_overlap() RETURNS trigger AS $$ BEGIN IF EXISTS (SELECT 1 FROM authority_provider_aliases AS existing WHERE existing.product_address = NEW.product_address AND existing.observation_namespace = NEW.observation_namespace AND (existing.provider_token = NEW.provider_token OR existing.provider_symbol = NEW.provider_symbol OR existing.instrument_address = NEW.instrument_address) AND (existing.effective_to IS NULL OR NEW.effective_from < existing.effective_to) AND (NEW.effective_to IS NULL OR existing.effective_from < NEW.effective_to)) THEN RAISE EXCEPTION 'authority provider alias overlaps'; END IF; RETURN NEW; END; $$ LANGUAGE plpgsql", 'CREATE TRIGGER authority_provider_aliases_refuse_overlap BEFORE INSERT ON authority_provider_aliases FOR EACH ROW EXECUTE FUNCTION authority_provider_aliases_refuse_overlap()']}

def upgrade() -> None:
    from app.db.models import (
        AuthorityCanonicalInstrument, AuthorityProviderEntity, AuthorityProviderProduct,
        AuthorityProviderContract, AuthorityProviderAlias, AuthorityRawSegment,
        AuthorityProviderObservation, AuthorityNormalizedObservation,
        AuthorityNormalizedObservationInput, AuthorityMarketTruthSnapshot,
        AuthorityProviderConformance, AuthorityCapabilityProfile,
        AuthorityCapabilityAssessment,
    )

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table_name in (
        "market_truth_instruments", "market_truth_provider_mappings",
        "market_truth_snapshots", "market_data_capability_profiles",
    ):
        if "authority_state" not in {item["name"] for item in inspector.get_columns(table_name)}:
            with op.batch_alter_table(table_name) as batch:
                batch.add_column(sa.Column(
                    "authority_state", sa.String(length=24), nullable=False,
                    server_default=sa.text("'LEGACY_UNVERIFIED'")))

    for model in (
        AuthorityCanonicalInstrument, AuthorityProviderEntity, AuthorityProviderProduct,
        AuthorityProviderContract, AuthorityProviderAlias, AuthorityRawSegment,
        AuthorityProviderObservation, AuthorityNormalizedObservation,
        AuthorityNormalizedObservationInput, AuthorityMarketTruthSnapshot,
        AuthorityProviderConformance, AuthorityCapabilityProfile,
        AuthorityCapabilityAssessment,
    ):
        if model is AuthorityProviderAlias:
            if model.__tablename__ not in sa.inspect(bind).get_table_names():
                for statement in ALIAS_DDL[bind.dialect.name]:
                    bind.exec_driver_sql(statement)
        else:
            model.__table__.create(bind, checkfirst=True)


def downgrade() -> None:
    raise RuntimeError("0038 refuses destructive removal of authority and observation facts")
