# Verification tiers and runtime

Use the smallest tier that covers the change:

- **Focused:** the changed contract and a regression test; suitable for a local behavior.
- **Subsystem:** focused evidence plus the affected workstream's regression; suitable when consumers in that subsystem can break.
- **Phase:** subsystem evidence plus relevant safety, migration, runtime, or research checks; use when a shared schema, runtime, or safety boundary moves.

Tests are not the only evidence. Drive UI flows, exercise real adapter response shapes, compare repeatable research numbers, or benchmark the same workload as applicable. Start local runtime only with mock provider, paper mode, disabled dotenv, empty live acknowledgement, and a temporary database. Never use the shipped environment or arm the instance.

Classify failures against an evidenced entry baseline: introduced behavior, fixtures affected by an intentional contract change, shared-state/order contamination, or proven pre-existing unrelated failures. Do not call a failure pre-existing merely because the tree is dirty. Repair affected fixtures without weakening the product contract.

When tests pass alone but fail together, reproduce the failing test with its contaminating predecessors. Check registries, caches, globals, environment, database/session cleanup and dependency overrides before editing many downstream tests. Fix the shared cause, run the affected subsystem, then run the broad gate once the clusters are resolved.

One owner runs heavy checks at a time. Let logged runs reach completion, failure or a defined timeout. Avoid repeated process/CPU polls and unchanged "still running" messages. Rerun only when changed inputs, code, environment or a diagnosed failure justify it. Never describe a mocked persistence or authority seam as an end-to-end check.
