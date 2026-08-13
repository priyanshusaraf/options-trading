# Task 2 brief: immutable registrations and transitive implementation identity

Implement Task 2 from `paper-trader/docs/superpowers/plans/2026-08-13-phase3-causal-strategy-contract.md` against starting commit `ba6ed7c`.

The accepted design and plan are authoritative. Read both completely before editing. Preserve the four inherited protected files and their approved hashes.

Risk classification: **Critical**. A stale, incomplete, or forgeable implementation identity can make research, backtests, admission, and deployment refer to different executable code under one apparent strategy address. Verification must target concrete stale-helper, undeclared dependency, forged-address, split-registry, and contributor-completeness failures. Do not grow matrices for their own sake.

Required outcome:

- Add canonical native implementation identity for callables, classes, recursive state functions, declared objects, and complete defining modules.
- Reject missing and extra dependency declarations, runtime imports, dynamic global/module lookup, unsupported closure values, and every fallback to `repr`, module name, or unknown identity.
- Derive `KernelRegistration`; callers cannot supply its implementation address.
- Add one immutable `PlatformRegistry` that binds components, specs, implementations, bodies, and addresses. Derive compatibility views from it; never compose independent maps as authority.
- Register all app-owned generated blocks, `logic.and`, `logic.or`, and the complete expanding-z contributor.
- Keep Component IR format version 1.
- Derive or reject global/module dependencies independently. Do not trust Task 1's manual `BLOCK_DEPENDENCIES` tuple; specifically account for `bisect`, pandas, numpy, recursive state callables/types/encoders, and imported expanding-z helpers.

Research consultation:

- Blocked capability: immutable semantic callable identity with complete dependency closure.
- Current files: `app/ir/implementation_identity.py`, `app/ir/registry.py`, `app/ir/kernels.py`, `app/ir/authoring.py`, `app/ir/contributors/generated_blocks.py`, `app/ir/strategies/expanding_z.py`, and `app/ir/library.py`.
- Reviewed read-only sources: DVC Data review and `hashfile/obj.py`, `hashfile/db/__init__.py`, `hashfile/cache.py`, `hashfile/status.py`, `hashfile/transfer.py`; Dagster review and its previously inspected definition/dependency/composition modules.
- Adopted patterns: immutable content identity separate from logical names; caches never become authority; validation completes before publication/invocation; partial dependency state is explicit failure.
- Rejected patterns: adopting DVC storage/workspace semantics, treating a file hash as semantic strategy identity, adopting Dagster's DSL/runtime, copying source, or adding either dependency.
- Reuse: reference-only. Both are Apache-2.0; no code reuse is planned.
- Smallest native change: canonical JSON plus SHA-256 over normalized callable/state/dependency identity, closed boundaries, and one app-owned registration transport.

Workflow:

1. Write the plan's behavioral identity tests first and capture the missing-module RED.
2. Implement canonical identity and registration closure in small cycles.
3. Add one concrete real-helper mutation proving the actual expanding-z address changes; a dummy helper is insufficient.
4. Run affected identity tests during development. At freeze run only the Task 2 subsystem boundary command from the plan plus changed-file compilation, `git diff --check`, protected hashes, and staged-set check.
5. Write `task-2-report.md` with exact RED/GREEN evidence and research provenance.
6. Stop uncommitted and unstaged for independent review.

Never edit or stage the four protected inherited files.
