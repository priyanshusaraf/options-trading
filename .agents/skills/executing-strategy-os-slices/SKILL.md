---
name: executing-strategy-os-slices
description: "Plan and execute a bounded Strategy OS engineering slice with proportional evidence, declared parallelism, and owner gates. Use for changes beyond a trivial, isolated edit."
---

# Execute Strategy OS slices

Read the current task capsule or assigned workstream and its declared dependencies. Do not start from `docs/CONTINUE.md`.

1. State the observable outcome, affected contract, invariants in the blast radius, and smallest coherent slice before editing.
2. Reject future-scope work, an undocumented dependency, or a missing task capsule. Record a discovered second problem; do not bundle it into the slice.
3. Declare parallel work before starting. Parallel assignments must have disjoint files and contracts. Never declare overlapping write ownership: collapse it under one assignment or the slice owner. Serialize shared schemas, shared runtime boundaries, authority changes, and any overlap discovered after dispatch.
4. Implement only the accepted slice. For a defect, reproduce it and add a regression. Prove a critical guard can fail by a reversible mutation.
5. Select evidence by risk: focused checks for a small local contract; subsystem checks for an affected workstream; phase checks for a shared schema, runtime, or safety boundary. Do not default to a full suite for a trivial edit.
6. Run behavioral verification appropriate to the contract, then invoke critical-risk review only when its trigger applies. Do not require universal independent review.
7. Stop at an owner gate. Report what is done, verified, unverified, deferred, and blocked.

Load only the needed reference:

- [Execution and owner gates](references/execution-and-owner-gates.md) for money, authority, deployment, or migrations.
- [Migration and persistence evidence](references/migration-and-persistence.md) for schema, transaction, restore, pool, or database work.
- [Research, providers, tenancy, and UI](references/domain-evidence.md) for those domains.
- [Verification tiers and runtime](references/verification-and-runtime.md) for test selection or local runtime evidence.
