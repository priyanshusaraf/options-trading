# Browser-session source application, 2026-08-29

## Decision and direct evidence

KEEP + HARDEN existing UserSession/principal; DIRECT REUSE installed cryptography
50.0.0 Argon2id, not a new identity provider or cryptographic implementation.
OWASP Password Storage and Authentication guidance informs bounded password/KDF
inputs; its Session Management and CSRF guidance informs host-only Secure/HttpOnly
cookies, session rotation and separate Origin/CSRF checks. The exact frozen
auth-contract.md defines invited-user scope and public-release nonclaims.

Pinned pyca commit dcb7050b807b00392fa9fe2eac7cb362fcf355cc was inspected in
argon2.py, backend/kdf.rs (constructor/derive/verify/PHC parsing), relevant
test_argon2.py vectors/verification tests, vector file, changelog and licence files.
The Rust wrapper calls OpenSSL and constant-time bytes_eq, releases the GIL and
maps allocation failure to MemoryError. PHC parsing accepts encoded cost parameters;
therefore the application must enforce its fixed profile BEFORE invoking it.
Do not call the library with attacker-selected cost, length or salt bounds.

Direct installed-library probe passes RFC9106 section5.3 exact output, the proposed
19456KiB/t2/p1 profile, wrong-password refusal and differing-salt outputs. Installed
Python wrapper matches captured source bytes. This is a primitive reuse check,
not an independent application security review, benchmark or authentication proof.

## Sources, alternatives and limits

Raw captures and exact digests: .agent/runs/strategy-os-v0-auth-dataset-parallel-materialization/references/receipt.json.
OWASP commit c735a6edc4c645eb975754cd908296686a5b3049; RFC9106 section5.3;
https://cryptography.io/en/50.0.0/hazmat/primitives/key-derivation-functions/;
https://github.com/pyca/cryptography/tree/dcb7050b807b00392fa9fe2eac7cb362fcf355cc.
Source and licence reading is bounded to the listed use; not the whole package.
The existing dual Apache-2.0/BSD-3-Clause notices are captured; redistribution must
retain applicable notices. No new licence-sensitive asset or dependency is adopted.
GitHub's tag verification response says verified=false/bad_cert; this receipt
claims immutable retrieved commit identity, NOT verified signing authenticity.

Rejected alternatives: keep header-only/admin-token onboarding (does not satisfy
Q01); add a new OAuth/JWT/identity service (duplicates current authority and adds
external setup); Scrypt/PBKDF2 fallback (unnecessary because Argon2id is present).
Invite enrollment is not email verification or public self-service onboarding.

Current upstream50.0.1 changes wheel OpenSSL to4.0.2; installed50.0.0 uses4.0.1.
The captured maintainer advisories and changelog are inputs, not a full vulnerability
or supply-chain clearance. Framework/OpenSSL/package update disposition belongs to
strategy-os-v0-security-operations-deployability before deployment. No lock/venv
mutation occurs during numerical assurance. The initial guessed Rust source path
returned404; that raw failed log is preserved, then exact repository tree resolved
backend/kdf.rs. No failed retrieval is labeled reviewed.

## Repository hypothesis, verification and rollback

The frontend sends same-origin credentials while HTTP principal extraction reads
headers only; there is no real browser enrollment/password verifier. Q01 owns the
exact shared-auth/schema/frontend boundary and must prove real HTTPS browser,
SQLite/PG16, tenant, CSRF, concurrent invite consume, revocation, secret redaction
and bounded-cost behavior, then receive independent SPEC/QUALITY PASS. Additive
USER-plane migration only; preserve old identities/money and refuse unsafe downgrade.
This note authorizes no live access, provider calls, deployment or public capability.
