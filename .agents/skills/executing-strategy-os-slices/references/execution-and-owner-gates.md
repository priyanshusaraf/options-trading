# Execution and owner gates

Preserve ledger reconciliation, separate paper/live books that fail closed to live, entry-only ARM, canonical binding, exact scan-to-fill attribution, withdrawal of authority-authored signals, exact content-address grants, and provenance-blind execution.

Stop for explicit owner acknowledgement before enabling live IR authority; changing live sizing, routing, risk, or execution semantics; accessing the live VPS or credentials; destructive database/infrastructure operations; adopting licence-sensitive code; or deciding regulatory, legal, commercial, or customer-money matters. Local development and safe verification may continue, but deployment may not cross the gate.

For a schema change, use a migration, test the appropriate upgrade path and model alignment, preserve money records, and record the actual migration head. Do not backfill or rewrite historical attribution without explicit authority.
