# Strategy admission operations record

## Phase 3 and IR v2 status — 2026-08-16

Phase 3 is `ACCEPTED / CLOSED`; its accepted verdict remains
`.agent/runs/phase3-task12-review-2/verdict.json`. The bounded IR v2 integration gate is also
`ACCEPTED` for local verification. Its report is
`paper-trader/docs/reports/2026-08-14-strategy-os-ir-v2-implementation.md`, with direct logs
under `.agent/runs/phase3-4-ir-v2-integration-gate/`.

Neither status authorises deployment, activation, live authority, or authoritative live IR. The
next task is the independent read-only IR v2 implementation review; Phase 4 remains blocked
unless that review returns separate SPEC and QUALITY passes.

## What admission establishes

For the exact admitted graph artefact, causal admission establishes closed implementation
identity, completed-bar causality, and vector/streaming parity. It binds only the admitted
content and its recorded evidence. A consumer must still enforce the existing ownership,
authority, execution-book, and deployment boundaries.

Admission is necessary, never sufficient. An `admission_address` alone does not permit
activation or live trading.

## IR v2 receipt persistence

IR v2 adds an immutable receipt that binds canonical document content, executable graph,
closed registry snapshot, resolved topology, and exact input, dataset, fee, slippage,
risk, parity, and causal-evidence identities. Compound parameter target paths come from
resolver output, never caller assertion.

Execution revision `0035` and research revision `0006` add nullable semantic identity
fields only. Existing v1 receipts retain original bytes and have no invented v2 content
or format value. Downgrade refuses to remove historical receipt identity. Consumers use
`admission_address` as their sole receipt authority; content and graph addresses remain
receipt facts and never substitute authority.

## Evidence

- Phase 3 accepted verdict: `.agent/runs/phase3-task12-review-2/verdict.json`.
- IR v2 predecessor reports: `.agent/runs/phase3-4-ir-v2-*/owner_integration/report.md`.
- IR v2 integration logs: `.agent/runs/phase3-4-ir-v2-integration-gate/owner/` for the bounded
  integrated suite, separate execution/research PostgreSQL 16 upgrades, killed mutations,
  snapshot reconciliation, and final integrity audit.

## Authority and rollback boundary

The accepted local checks bind only the recorded evidence and receipt facts. They do not make
v2 an authoritative live IR or replace the existing admission lifecycle. A later independent
review must verify the package before any Phase 4 architecture task can become ready.

If an existing paper-authority record must be withdrawn, use its controlled lifecycle to pause or
retire it and use the record's named rollback target. Do not substitute a graph, bypass the
authority check, or create live authority. Risk-reducing exits remain available under their
existing execution controls.

## Nonclaims

This record does not claim complete market-data truth, numeric-validity semantics,
point-in-time rulebooks, provider capability, dynamic derivative selection, resource capacity,
or Strategy Preflight. It does not enable authoritative live IR or change live sizing, routing,
risk, protection, or execution semantics. Local and PostgreSQL test evidence is not deployment
or managed-production readiness evidence. Component IR v2 remains excluded from this Phase 3
closure.
