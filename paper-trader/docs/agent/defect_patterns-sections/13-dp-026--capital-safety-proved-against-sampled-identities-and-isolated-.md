Reference: [section index](../DEFECT_PATTERNS.md). Read with its scope; this is not a new assignment.

## DP-026 — Capital safety proved against sampled identities and isolated transitions

- Severity: Critical for money admission, order binding, recovery and inventory
  lineage.
- Status: STALE/REQUIRES RECHECK. The first independent capital assurance and its
  sole focused recheck both returned SPEC FAIL and QUALITY FAIL. The recheck
  closed eight original findings, left `P5-CAP-004` open because reservation-bound
  command quantity still accepted `2.0`, and added critical `P5-CAP-R001` because
  recovery numeric facts accepted float/bool coercion and lacked exact bounds. The
  exhausted route is immutable history. The owner-authorized successor is the
  serial `phase5-capital-assurance-replan` →
  blocked historical `phase5-capital-assurance-recovery-correction` →
  `phase5-capital-broad-compatibility-provider-leak-correction` →
  `phase5-capital-assurance-final-review` lineage. Phase 5 integration and Phase 6
  remain blocked until the fresh review returns dual PASS. The provider-leak
  correction passed its causal sequence, killed/restored mutation and unchanged
  broad process; this register does not upgrade the integrated capital boundary
  before independent review.
- Incident: separately green sizing, transaction, recovery, lineage, migration and
  compatibility packages omitted cross-boundary members and combinations. The
  pending digest ignored `ExecutionIntent`/`ExecutionOrderEvent`; known pending was
  dropped when uncertainty existed; float score decided rank; reservation command
  side was unbound; `RESOLVED_UNUSED` could release a submitted command; exact batch
  replay failed after TTL; fill allocation could omit intent and over-consume one
  reservation across tranches; campaign/tranche addressed identity fields remained
  mutable; and the broad-suite debt misclassified one current-head fixture failure.
- Violated invariant: enumerate the complete durable state and identity universe at
  every money boundary. Risk reduction must remain reducing after all known pending
  facts. Every reservation command and fill must retain exact signed causal
  attribution. Addressed facts must make every hashed identity immutable. Evidence
  must report actual failures and broad compatibility cannot be called green while
  red.
- Why prior evidence missed it: tests exercised commands, uncertainty, known pending,
  duplicate replay, fill allocation, lineage guards and historical migrations in
  isolation. They did not combine known plus uncertain pending, replay after TTL,
  correct quantity plus wrong side, submitted unused release, cross-intent fills,
  multiple tranches sharing a reservation, or direct mutation of every field hashed
  into campaign/tranche addresses. The inventory counted consumers but did not prove
  the complete pending or causal-member universe.
- False assumption: one representative row per authority class, one transition per
  state, and one allocation per reservation were enough to prove closure. Database
  integer columns were assumed to reject floats before Python ranking or money
  mutation. Later, equality and range checks were assumed to establish integer type,
  even though Python makes integer-valued floats and booleans compare as integers. A
  red legacy test was assumed stale from its name rather than diagnosed from its
  actual stack.
- Prevention invariant: freeze complete sets for pending intents/events/commands,
  reservation-linked tranches/allocations, hashed identity fields and compatibility
  failures. Cross-product tests must combine known and uncertain states, sign and
  side, time expiry and idempotence, command and release state, intent and fill, and
  multiple consumers of one bounded quantity. Independently mutate each omitted
  member or predicate and restore exact bytes.
- Minimal permanent regressions: (1) insert or transition any unresolved
  intent/event/command and require the candidate digest to stale or admission to
  block; (2) combine known opposite pending with uncertainty and prove the exit delta
  cannot flip/increase exposure; (3) reject float/bool rank inputs; (4) reject a
  correct absolute quantity with wrong side; (5) retain capital for submitted
  `RESOLVED_UNUSED`; (6) converge exact post-TTL replay; (7) reject cross-intent,
  cross-instrument and aggregate cross-tranche over-allocation; (8) mutate/delete
  every addressed lineage identity on SQLite/PostgreSQL; (9) rerun the identical
  broad selection green and describe every failure from its stack; (10) require an
  exact positive int excluding bool for reservation-bound command quantity before
  lease authority or reservation mutation while preserving unreserved v1 behavior;
  (11) require exact non-negative int32 recovery head/quantity and exact non-negative
  int64 consumed money before evidence addressing, session binding or locking, and
  prove float, bool, negative and above-bound forms have zero reservation, event,
  head and outbox effects in both database dialects; (12) run the broad process in
  one interpreter and require every test-owned override on a process-wide provider
  to restore through normal pytest teardown before the successor test starts.
- Adversarial generalization: apply the same complete-universe and cross-product
  challenge to risk limits, broker reconciliation, fill attribution, campaign
  ownership, provider evidence, migration restore and deployability gates. Ask which
  independently durable identity or second consumer could bypass a locally complete
  row-level proof.
- Exact inheritors: immutable failed `phase5-capital-admission-assurance`,
  `phase5-capital-assurance-replan`,
  blocked historical `phase5-capital-assurance-recovery-correction`,
  `phase5-capital-broad-compatibility-provider-leak-correction`,
  `phase5-capital-assurance-final-review`, `phase5-implementation`, `phase5-review`,
  Phase 6 preflight and the V1 release review.
- Evidence: `.agent/runs/phase5-capital-admission-assurance/review/verdict.json`
  SHA-256
  `89d05b05650b9775966d4ae263d833794f56f8f17690e9a390502191db9512b8`
  `.agent/runs/phase5-capital-admission-assurance/review/recheck-verdict.json`
  SHA-256
  `78e81a79606b6e70c2ed4d152a5edfab54a56dde30eee03a325cc8bf7762f8a9`,
  `.agent/runs/phase5-capital-admission-assurance/owner-replan-proposal.md`
  SHA-256
  `6c43d1e4855454d5b52fac9973de9bb5fd6298d084f6da8898f03a19f97fe51f`
  and `.agent/runs/phase5-capital-admission-assurance/correction-plan.md`.

## Canonical parameter drift hidden by implementation-derived receipts — 2026-08-28

- Violated invariant: evaluation must preserve the canonical parameter facts emitted
  by the resolver and bound by the data compiler. Numeric equality does not imply
  identical serialized receipt bytes: integer `50` and float `50.0` differ.
- Why earlier evidence missed it: implementation tests built their bound receipts
  through the same candidate parameter helper that coerced integer `q` to float.
  Formula tests therefore saw matching but unrepresentative receipts. Independent
  assurance used the real resolver/compiler and rejected valid PERCENTILE defaults.
- False assumption: validating formulas and a locally constructed receipt proved
  that a valid authored parameter crossed every canonical consumer unchanged.
- Minimal permanent regression:
  `test_percentile_preserves_canonical_parameters_through_real_runtime` in
  `backend/tests/test_indicator_accuracy_core_math.py` covers complete defaults,
  integer, float, endpoint and fractional q through resolve, compile/verify-plan and
  evaluate_v2, comparing complete arrays and masks without the candidate helper
  constructing the expected receipt.
- Adversarial proof: restoring the old coercion in an isolated copy fails five
  real-consumer cases while two float controls pass; exact restoration passes all
  seven. Working product source is never mutated for this experiment.
- Generalization: the missing-consumer equivalent is a parameter/receipt fixture
  derived from the same implementation being tested. Test actual default and
  authored representations at every answer-changing boundary; do not normalize
  parameters again inside a numerical component or weaken replay to admit drift.
- Exact inheritors: `post-phase5-indicator-accuracy-core-parameter-correction`,
  `post-phase5-indicator-accuracy-core-return-stability-correction`,
  `post-phase5-indicator-accuracy-core-correction-assurance`,
  `post-phase5-indicator-accuracy-recursive-state`,
  `post-phase5-indicator-accuracy-recursive-state-assurance`,
  `post-phase5-indicator-accuracy-multi-output`,
  `post-phase5-indicator-accuracy-multi-output-assurance`,
  `post-phase5-indicator-accuracy-session-data`,
  `post-phase5-indicator-accuracy-session-data-assurance`,
  `post-phase5-indicator-accuracy-remaining-oracles`,
  `post-phase5-indicator-accuracy-remaining-oracles-assurance`,
  `post-phase5-indicator-accuracy-registry-lineage-integration`,
  `post-phase5-indicator-accuracy-complete-universe-assurance`,
  `post-phase5-indicator-accuracy-final-review`,
  `strategy-os-v0-verified-language-catalogue` and
  `strategy-os-v0-canonical-research-spine`.
- Evidence: sealed assurance F01 in
  `.agent/runs/post-phase5-indicator-accuracy-core-math-assurance/findings.json`;
  correction evidence in
  `.agent/runs/post-phase5-indicator-accuracy-core-parameter-correction/`.
