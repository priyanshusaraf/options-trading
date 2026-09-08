# Component IR v2 implementation integration

Date: 2026-08-16\
Capsule: `phase3-4-ir-v2-integration-gate`\
Snapshot: `de6faae3e97cf5537338bee2143350e53f70da1c`

## Result

The serial integration gate is accepted for bounded local verification. It makes
`phase3-4-ir-v2-implementation-review` ready. This is not an independent review verdict and
does not make Phase 4 ready.

The accepted predecessor reports are reconciled in
`.agent/runs/phase3-4-ir-v2-integration-gate/owner/preflight_snapshot.log`:

- dispatch compatibility;
- schema and topology;
- resolution and runtime;
- admission and persistence; and
- API contract.

They bind the same HEAD and inherited dirty-tree input. The integration owner did not change
frontend source, live authority, provider or broker behavior, deployment state, credentials,
production data, or migration history.

## Integrated evidence

`owner/integrated_v1_v2_gate.log` records the one bounded v1/v2 suite. It covers frozen v1
dispatch, runtime, admission, and API compatibility; closed v2 metadata and canonical bytes;
topology, exact types, cardinality and edge order; compound binding and provenance; vector and
prefix parity; owner-isolated admission; execution/research SQLite migrations; API atomicity;
editor descriptors; and compatibility refusal.

`owner/disposable_postgresql_execution.log` and
`owner/disposable_postgresql_research.log` each record a passing disposable PostgreSQL 16
upgrade in its own fresh database plane. Execution head is `0035`, parented to `0034`; research
head is `0006`. The focused migration tests cover populated and empty upgrades, restart and
recovery behavior, concurrency/refusal cases, and preservation of v1 facts.

One earlier combined execution-and-research command is retained at
`owner/disposable_postgresql_gate.log` as rejected diagnostic output, not acceptance evidence.
It attempted to share a database plane that the documented topology keeps separate; the research
migrator correctly refused the populated unmanaged database. No bypass was added. The two
separate fresh-plane commands above are the declared PostgreSQL gate.

`owner/killed_mutation_gate.log` records passing killed probes for format dispatch, exact type
compatibility, edge binding/order, compound parameter propagation, content versus graph
identity, prefix parity, receipt immutability, and execution/research migration safety. The
probes are test-scoped reversible mutations and the final integrity audit confirms the source
boundary after they completed.

## Integrity and deployment boundary

`owner/final_integrity_audit_corrected.log` records a clean diff check, unchanged protected
hashes, no frontend path in the working diff, and current migration heads. The predecessor
snapshot and evidence hashes are recorded in `owner/preflight_snapshot.log`.

The local deployment-impact matrix is limited to application and HTTP behavior, execution and
research schemas/migrations, disposable PostgreSQL, and local CPU/memory behavior. The
repository deployability matrix remains authoritative at
`paper-trader/docs/agent/DEPLOYABILITY.md`: release deployability, production capacity,
recovery, security, cost, and live authorization remain rejected or open under their named
future gates.

## Closure correction

The first implementation review's three bounded defects are corrected for local integration evidence: recursive compound bodies lower their public and nested edges to executable leaves with retained provenance; the immutable registry owns exact leaf implementation identities for both evaluators and admission; and duplicate canonical semantic edge tuples refuse before cardinality assembly. The focused affected-v2 plus v1 compatibility evidence is `.agent/runs/phase3-4-ir-v2-implementation-closure-correction/owner_integration/focused-final.log`.

This correction changes no migration or persistence schema. Its deployment impact is limited to local Application, CPU, Memory, Research runtime, and Admission identity behavior; release deployment remains rejected by the deployability ledger.

## Next gate and nonclaims

The current official package is `.agent/review-package.json`. The next task performs one
read-only critical review and must return separate SPEC and QUALITY verdicts. No reviewer was
started by this integration gate.

This report does not claim production readiness, deployment readiness, frontend v2 authoring,
provider capability, Phase 4 implementation, authoritative live IR, or permission to trade.

## Recovery correction (2026-08-17)

The owner-authorized recovery hardens the existing v2 validator, registry, and
resolver only. Compound bodies now use the ordinary graph validator; registry
construction closes direct and transitive component references and rejects
compound-reference cycles; and lowered members retain deterministic authored
edge paths, including each edge binding, while preserving direct
`provenance["edge_id"]` compatibility.

The focused compound/registry integration and the affected v2 compatibility
suite passed at `.agent/runs/phase3-4-ir-v2-implementation-recovery-correction/owner_integration/compound_resolution_after_output_compatibility.log`
and `.agent/runs/phase3-4-ir-v2-implementation-recovery-correction/owner_integration/affected_ir_v2_suite.log`.
The reversible-mutation evidence is
`.agent/runs/phase3-4-ir-v2-implementation-recovery-correction/recovery_mutation_evidence/phase3-4-ir-v2-implementation-recovery-correction/recovery_mutation_evidence/mutation_runner_v5.log`.

This remains compatible runtime hardening with no schema or service change.
Migration head, protected-hash, and frontend read-only evidence is retained
under `.agent/runs/phase3-4-ir-v2-implementation-recovery-correction/owner_final_audit/`.
The final scoped-hash and attributed-command manifest is
`.agent/runs/phase3-4-ir-v2-implementation-recovery-correction/owner_final_audit/final_evidence_manifest.json`.
It prepares a fresh independent final review only; it does not accept Phase 4
or change the existing nonclaims.

## Final-review correction iteration 2 (2026-08-17)

The immutable first final review at
`.agent/runs/phase3-4-ir-v2-implementation-final-review/verdict.json` returned
separate SPEC and QUALITY failures for one bounded validator exception and its
missing reproducibility evidence. The correction keeps the single ordinary v2
graph validator. Its cycle traversal now skips non-mapping edges and endpoints
after structural validation records ordered `V2_OBJECT` violations. Validly
shaped ordinary graph cycles continue to return `V2_CYCLE`.

Named top-level malformed-edge, compound-body malformed-edge, and ordinary
cycle regressions are retained in the existing edge and compound test modules.
The owner integration records 60 passing affected IR v2 tests and 34 passing
edge-contract tests at
`.agent/runs/phase3-4-ir-v2-implementation-recovery-correction/owner_correction_2/`.
The exact guard mutation fails with the original raw exception and passes after
restoration; its baseline, mutation, restoration, and pre/post product hashes
are under
`.agent/runs/phase3-4-ir-v2-implementation-recovery-correction/recovery_edge_mutation_evidence_v2/`.

Every retained correction command has its own timestamp, absolute working
directory, exact arguments, HEAD/base, complete dirty-tree fingerprint, exit
status, assumptions, evidence class, and complete output. Execution and
research migration heads remain `0035` and `0006`; protected hashes, scoped
diff checks, and the frontend read-only boundary match. The official package
is regenerated after this programme transition so the focused reviewer sees
the exact final tree.

This correction makes only the one focused independent final-review recheck
ready. It does not accept Component IR v2, open Phase 4, change the frontend,
authorize live IR or trading, or claim deployment or production readiness.
