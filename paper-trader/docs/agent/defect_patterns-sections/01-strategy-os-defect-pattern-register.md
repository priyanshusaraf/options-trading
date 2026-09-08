Reference: [section index](../DEFECT_PATTERNS.md). Read with its scope; this is not a new assignment.

# Strategy OS defect-pattern register

This register turns serious failures into reusable architecture and review controls. A local fix does not close a pattern. Closure requires a root-cause statement, a prevention invariant, a permanent adversarial regression through the real boundary, a search across every named surface, and revalidation of dependent evidence.

## Status and evidence rules

- `OPEN`: the pattern or its transitive impact has not been fully searched or closed.
- `CONTAINED`: the known instance fails closed, but the pattern search or dependent revalidation remains incomplete.
- `CLOSED`: the known instance and relevant pattern search pass permanent real-path regressions, and every dependent PASS is current or explicitly superseded.
- `DEFERRED`: only non-Critical residual work may use this status. It requires a named owner, rationale, deadline or future capsule, and proof that the deferral cannot cross an authority, tenant, money, persistence, or research-integrity boundary.
- `STALE/REQUIRES RECHECK`: an earlier PASS depended on an invalidated assumption. Historical evidence remains immutable, but it is no longer current acceptance evidence.

Every entry must record:

1. incident and root cause;
2. prevention invariant;
3. searched surfaces and results;
4. permanent adversarial regression;
5. transitive evidence map: changed invariant → affected contracts → affected phases/tests/reviews → required revalidation;
6. severity, status, owner, and evidence paths.

Every material defect, false green, incomplete proof, invalid assumption,
authority error, recovery failure, or evidence weakness must also record the
violated invariant, why the prior evidence missed it, the false assumption, a
minimal regression, an adversarial generalization, and the exact future
capsules that inherit the lesson. A Critical producer, writer, or implementation
owner cannot certify its own authority boundary. Acceptance requires an outside
consumer, recomputation, or independent review where the active capsule names
that gate. Aggregate test or mutation counts describe coverage; they never
supply semantic authority by themselves.

For cross-layer architecture invariants, acceptance evidence must include at least one actual lifecycle:

`create/admit → persist → process death → reload → verify → consume`

Replacing persistence, reconstruction, authority, or consumption with a monkeypatch does not prove that lifecycle.

## DP-001 — Distinct facts collapsed into one representation

- Severity: Critical
- Status: OPEN pending independent Sol-high pattern search and Phase 4 final review
- Incident: the Phase 4 persisted-loader design equated a Component IR v2 full-document `content_address` with its executable-projection `graph_address`. Legacy `GraphVersion` could represent only one stored-document address, so it could not preserve both facts while satisfying its v1 contract.
- Root cause: individually reasonable storage, admission, and runtime components made incompatible assumptions about what one address and one graph row meant. Earlier unit and mocked-loader evidence did not exercise the complete persisted lifecycle.
- Prevention invariant: semantically distinct facts require distinct typed fields or records unless a reviewed proof shows a stable bijection. Storage identity, executable identity, admission evidence, requested authority, resolved authority, tenant ownership, dataset identity, result identity, and cache identity must never be substituted for one another.
- Required search surfaces: Component IR v1/v2 identities; graph, registry, receipt, assessment, dataset, result, and cache addresses; execution and research persistence; requested and resolved authority; organization/user/owner fields; provider versus broker identity; migration/version discriminators; worker/reclaim identity.
- Permanent regression: persist distinct v2 document and executable addresses in both owner-scoped planes, simulate a new process/session, reload the real rows, verify the full receipt/assessment/registry/graph chain, and reach the stable pre-runtime consumer refusal without legacy-v1 dispatch. Add changed-address, duplicate-version, wrong-owner, partial-write, stale-receipt, and mixed-v1/v2 counterexamples.
- Transitive evidence map: v2 identity semantics → IR v2 admission/persistence and Phase 4 capability/cache/runtime contracts → IR v2 implementation review, Phase 4 correction/recheck, durable integration, migration and worker/cache tests → independent Sol-high search plus fresh Phase 4 final review. Any broader dependencies found by the checker become `STALE/REQUIRES RECHECK` until directly revalidated.
- Owner: `phase4-v2-durable-graph-integration` for the known instance; root-dispatched Sol-high checker for the pattern search.
- Evidence: `.agent/runs/phase4-review/recheck-verdict.json`, `.agent/runs/phase4-review-recovery/owner_integration/report.md`, `.agent/runs/phase4-v2-durable-graph-integration/independent_architecture_pattern_check/report.md`.

## DP-002 — Syntactic self-consistency mistaken for authority

- Severity: Critical
- Status: CONTAINED pending full lifecycle and pattern revalidation
- Incident: a caller could construct or recompute a self-consistent capability-assessment lookalike and persist it because consumers checked shape and repeated addresses without proving canonical construction or reconstructing authoritative evidence.
- Root cause: provenance was represented as claims inside an object, while the authority to mint that object was not preserved across persistence and reload.
- Prevention invariant: public structure validation never grants authority. A persisted authoritative fact must be derived through the sole constructor or independently reconstructed from immutable authoritative dependencies, with owner and version checks, before use.
- Required search surfaces: strategy admission, causal proof, capability assessment, deployment binding, account/lease authority, provider credentials, research promotion, paper/live assignment, and any `from_dict`, ORM constructor, receipt, token, or copied status row that can cross a trust boundary.
- Permanent regression: forge a structurally valid object and recompute every outer digest; both write and reload/use paths must reject it. Then prove the canonical object survives the complete process-death lifecycle without retaining an in-memory token.
- Transitive evidence map: assessment authority → Phase 4 data capability/admission/persistence/cache contracts → Phase 4 correction, recheck, durable integration, real-loader and research-persistence tests → independent checker and fresh Phase 4 final review.
- Owner: `phase4-v2-durable-graph-integration` for the known assessment instance; foundation audit for the broader authority pattern.
- Evidence: `.agent/runs/phase4-review/verdict.json`, `.agent/runs/phase4-review/recheck-verdict.json`.
