# Proposed CEO prior-art gate

Status: proposed only

This recommendation does not edit the canonical agent instructions. The user's recommendations-only boundary forbids installing the rule during this slice.

## Canonical control decision

The authoritative repository control is the root AGENTS.md, with paper-trader/AGENTS.md adding product-local rules. The root file defines task startup, model routing, programme discipline, invariants, owner gates, and deployability. The product file already directs phase design to the architecture skill and says that work outside a capsule needs an owner decision.

Recommendation: add one compact prior-art gate to the root AGENTS.md and one reference sentence to paper-trader/AGENTS.md. Do not create another competing instruction file.

## Proposed rule

Before delegating a nontrivial feature, architecture change, defect correction, or subsystem redesign, the root owner must:

1. State the user problem and affected Strategy OS invariants.
2. Search the repository-intelligence index for the affected contracts.
3. Inspect the marked local sources and at least two materially different approaches when credible alternatives exist.
4. Read source, tests, failure handling, persistence, migrations, concurrency, current issues, release history, security notices, and licence terms in proportion to risk.
5. Record a Prior-Art Decision with exact commits, observed facts, inferences, rejected alternatives, licence limits, failure modes, required tests, migration impact, rollback posture, and open questions.
6. Attach that decision to the capsule or assignment before implementation starts.
7. Keep Strategy OS's settled IR, authority, tenancy, causality, provider, and money invariants binding unless new evidence supports a formal architecture correction.

Trivial copy or harmless styling work may record:

    Prior-art review: not materially relevant.

A production emergency may record a waiver only when delay increases user, capital, data, or security risk. The waiver must name the temporary mitigation, regression test, owner, and deadline for the missed review.

## Proposed delegation template

### Task

### User problem

### Observable outcome

### Affected objects and invariants

### Relevant repositories reviewed

| Repository | Commit | Licence | Why relevant |
| --- | --- | --- | --- |

### Alternative approaches

### Selected approach

### Rejected approaches

### Known production failures

### Strategy OS files and runtime paths

### Required tests

### Migration and rollback

### Deployability impact

### Owner gates

### Open questions

## Enforcement recommendation

- Extend the task-capsule schema with one prior_art_decision path for nontrivial slices.
- Make the capsule validator reject a nontrivial implementation assignment when the path is absent.
- Let the root explicitly mark trivial work.
- Do not make a repository clone count or a star count an acceptance condition.
- Do not let prior art authorize code copying. The licence ledger still controls reuse.
- Keep one decision log. Do not create per-agent competing architecture records.

Proposed future capsule: agent-prior-art-gate-integration

Deployment impact: none for the documentation proposal; compatible agent-governance change when implemented.
