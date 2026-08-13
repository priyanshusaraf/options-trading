# Task 8 brief: enforce admission at publication and research use

Implement Task 8 from
`paper-trader/docs/superpowers/plans/2026-08-13-phase3-causal-strategy-contract.md` against
starting commit `f2fdcd9`.

Read the complete accepted Phase 3 design, full plan, progress ledger, V1 product-steer
reconciliation, and this brief. Preserve the four inherited protected files and hashes.

Risk classification: **Critical**. Publication or research execution that omits, trusts, or delays
receipt verification can grant authority to strategy bytes different from those admitted.

Required outcome:

- Editor `publish_draft` and `apply_and_publish` admit after semantic validation and before the
  immutable version/current pointer advances. Store the execution-plane receipt and
  `admission_address` in the same transaction.
- Admission refusal keeps the edited draft but does not advance published revision/current version.
  API maps stable refusal codes into the existing structured 422 response without leaking internals.
- Graph experiments and durable research-operation descriptors bind exact canonical graph bytes,
  graph content address, owner-scoped research receipt, and admission address at enqueue.
- Claimed workers load the owner-local receipt, recompute/verify admission against current app
  registry, and refuse stale/missing/foreign evidence before provider construction or data I/O.
- Durable refusal records a stable code on the item/event path. It never substitutes exception text
  as authority.
- This task proves causal admission only, not complete Strategy Preflight.

Concrete failure hypotheses:

1. Editor advances a published version/current pointer when admission refuses.
2. Receipt insert and GraphVersion publication are not atomic under an injected commit/flush failure.
3. A forged/stale/foreign receipt reaches provider construction or data access.
4. Enqueue stores graph bytes/address but omits the owner-scoped receipt, or stores a receipt for
   different bytes.
5. Worker checks row existence only and skips fresh `verify_admission` against current registry.
6. API returns an unstable/unstructured refusal or mutates the draft incorrectly.

Verification workflow:

1. Observe focused publication/worker REDs first.
2. Add only tests tied to the six hypotheses, including one rollback injection and one poison
   provider/factory proof.
3. Run affected editor/research tests during implementation and the named subsystem boundary at
   freeze. Use live PostgreSQL only if the touched transaction behavior differs materially.
4. Do not run broad backend or Phase 3 suites; Task 12 owns them.
5. Write `task-8-report.md`, update the ledger, and freeze uncommitted/unstaged for independent
   review.
