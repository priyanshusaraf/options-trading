Reference: [section index](../STRATEGY_OS_KLEPPMANN_AND_PROFESSIONAL_ENGINEERING_REVIEW_PROMPT_V2_2026-08-28.md). Read with its scope; this is not a new assignment.

V0 may use ordinary cryptographic hashes and signed manifests where operationally cheap. Future versions may evaluate authenticated snapshots, selective disclosure, user-held verification keys, or third-party verification.

Explicitly reject for V0 unless independently justified:

- blockchains;
- zero-knowledge proofs;
- Merkle trees everywhere;
- custom cryptographic protocols;
- claims of cryptographic non-repudiation without a real key-management model.

Minimum tests:

- mutate one artifact and prove verification fails;
- replace a dataset or engine version and prove identity changes;
- verify old evidence after a migration;
- document what the signature proves and what it does not prove.

### 16.7 Credential, device, session, and key lifecycle

Do not stop at "secrets are encrypted." Model lifecycle and compromise.

Audit:

- user sessions and refresh tokens;
- device/session inventory;
- password reset and account recovery;
- 2FA enrollment, recovery, disablement, and support abuse;
- API keys and service accounts;
- broker access and refresh tokens;
- webhook signing secrets;
- database/object-storage/queue credentials;
- encryption keys and rotation;
- CI/CD and deployment credentials;
- privileged break-glass access.

For each define:

```text
issuer
scope
owner
storage
rotation
expiry
revocation
recovery
audit trail
blast radius
behavior during partial rotation
behavior after compromise
```

Required failure tests:

- broker token expires during an active job or future deployment;
- old and new credentials overlap during rotation;
- wrong-environment credential is deployed;
- revoked session continues using a websocket;
- lost device/account recovery does not silently expose strategy IP;
- support cannot bypass ownership without a logged, time-bounded break-glass path.

Future team collaboration may study group-key agreement and decentralized recovery, but must use reviewed protocols and libraries rather than home-grown cryptography.

### 16.8 Semantic conflicts in future collaborative strategy graphs

A visual graph is not ordinary text. Two edits may merge structurally while producing an unsafe or semantically different executable strategy.

V0 requirements:

- immutable revisions;
- optimistic concurrency or an explicit single-writer rule;
- clear stale-revision conflict UI;
- no silent last-write-wins for executable graph semantics;
- graph diff that distinguishes presentation-only from executable changes;
- revalidation after any executable merge.

Future collaboration requirements to preserve:

- operation identity and causal context;
- CRDT/merge use only where its semantics are proven;
- presentation/layout changes may converge independently when safe;
- executable node/edge/parameter conflicts require semantic review;
- authorization and group membership changes are separate from data convergence;
- undo/redo must be intention-aware and versioned.

Do not add Automerge, CRDTs, or multiplayer editing to V0 without product evidence.

### 16.9 Locale, currency, timezone, and input ambiguity

Audit user input and display separately from canonical storage.

Required cases:

- Indian and international digit grouping;
- rupees/paise and later multi-currency values;
- decimal comma versus decimal point;
- ambiguous day/month date formats;
- exchange timezone versus user timezone;
- daylight-saving transitions in imported/global data;
- session calendars and special sessions;
- UTC storage and monotonic runtime durations;
- locale-safe CSV parsing;
- copy/paste and exported reports;
- frontend formatting that never feeds back into canonical calculations.

Canonical strategy and evidence identity must not change because a user changes locale or display timezone.

### 16.10 Recommendation governance and feedback loops

This is mainly a V2/V3 concern, but preserve evidence now.

Before Strategy Diagnostics, AI research, recommendations, rankings, or a marketplace can exist, require:

- exact distinction between source facts, platform inference, and user hypothesis;
- post-hoc recommendation labeling;
- graph diff and fresh validation for every recommended change;
- disclosure of platform-owned versus third-party content;
- no hidden preference for platform-owned strategies;
- telemetry and training-data consent;
- monitoring for recommendation-induced crowding or self-reinforcing behavior;
- a way to decline recommendations without product punishment;
- auditability of ranking and recommendation policy versions.

Do not build the recommendation system in V0. Preserve branch attribution, trade reasons, regime/time/instrument breakdowns, and exact experiment lineage so future recommendations can be evaluated honestly.

### 16.11 Software supply-chain integrity

Audit the path from source to production artifact:

```text
source
→ dependency resolution
→ build
→ tests
→ artifact
→ container/package
→ deployment
→ runtime
```

Required controls should be proportional to V0 risk and include:

- dependency lockfiles and update policy;
- vulnerability and secret scanning;
- SBOM generation;
- artifact provenance;
- signed or attestable releases where practical;
- protected production deployment path;
- separation of dev/test/prod credentials;
- reproducible or at least traceable builds;
- license review for reused code;
- emergency dependency rollback;
- AI/coding-agent changes subject to normal review and verification.

Do not chase the highest possible certification level before launch. Establish a traceable baseline and harden money/execution paths further before they become reachable.

---
