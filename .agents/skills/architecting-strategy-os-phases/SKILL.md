---
name: architecting-strategy-os-phases
description: "Assess Strategy OS architecture, phase boundaries, and proposed technology or subsystem changes. Use before accepting a new abstraction, dependency, schema, authority model, provider model, runtime model, or rewrite."
---

# Architect Strategy OS phases

Start from the current task capsule or workstream and the governing RFC or ADR. Do not use `docs/CONTINUE.md` as a startup document.

1. State the decision, expected operator outcome, constraints, and evidence needed to accept it.
2. Inspect the established architecture and dependency direction before proposing code. Treat a settled ADR as binding unless new evidence justifies changing it.
3. Reject a proposal that creates a second IR, validator, resolver, hash, component library, research ledger, deployment model, or execution authority.
4. Test the need: distinguish a present seam need from an imagined feature; keep complexity proportionate to the operating scale.
5. For commodity/provider work, inspect Strategy OS first, then permitted external references. Classify reuse and read the licence. Stop for an owner/legal gate before licence-sensitive code adoption.
6. Route any accepted change to execution binding, money, authority, shared schema, or live behavior through one integrated critical-risk review after implementation and evidence exist.
7. Return `KEEP`, `KEEP + HARDEN`, `REFACTOR`, `REPLACE`, or `DEFER`, with evidence, the smallest safe next slice, invariants that must survive, and an explicit deferred home where applicable.

Read the relevant reference only for the decision at hand:

- [IR and authority invariants](references/ir-and-authority.md) for language, deployment, or money boundaries.
- [Providers and tenancy](references/providers-and-tenancy.md) for brokers, connections, credentials, owners, or API changes.
- [Research and performance](references/research-and-performance.md) for backtests, data, runtime, or rewrite proposals.
