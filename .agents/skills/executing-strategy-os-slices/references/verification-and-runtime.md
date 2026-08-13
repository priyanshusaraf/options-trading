# Verification tiers and runtime

Use the smallest tier that covers the change:

- **Focused:** the changed contract and a regression test; suitable for a local behavior.
- **Subsystem:** focused evidence plus the affected workstream's regression; suitable when consumers in that subsystem can break.
- **Phase:** subsystem evidence plus relevant safety, migration, runtime, or research checks; use when a shared schema, runtime, or safety boundary moves.

Tests are not the only evidence. Drive UI flows, exercise real adapter response shapes, compare repeatable research numbers, or benchmark the same workload as applicable. Start local runtime only with mock provider, paper mode, disabled dotenv, empty live acknowledgement, and a temporary database. Never use the shipped environment or arm the instance.
