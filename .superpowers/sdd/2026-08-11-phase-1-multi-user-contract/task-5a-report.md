# Task 5A report — durable user sessions and principal resolution

## Delivered

- Added digest-only `UserSession` persistence bound by a composite foreign key to an active organization membership.
- Issuance generates a 256-bit bearer, returns it only at issuance, and persists only its lowercase SHA-256 digest. Session identifiers are independently random and non-secret.
- Centralized HTTP and WebSocket resolution in `app.api.principal`: active session, user, organization, and membership are all required; unknown, malformed, expired, and revoked credentials fail closed.
- Replaced runtime plaintext shared-token comparison with the durable resolver. A configured legacy token is narrowly bootstrapped as a seeded legacy session and rejects a foreign digest binding.
- Added explicit development/test disabled-auth mode and production-like boot refusal. A tokenless durable-auth deployment is supported by `auth_disabled=False`.
- WebSocket authentication now quarantines after accept until a strict first `{type: "authenticate", bearer: ...}` frame resolves through the same service. Handshake credentials are rejected. Protocol-frame log records redact inbound text/binary payloads before handlers while retaining metadata.
- Added migration `0028`, including target-bound creation proof/restart recovery, forged-target rejection, populated-0027 preservation, relational parity, and refusal to downgrade populated sessions.

## Verification

- RED behavior tests were written before the durable-session production implementation.
- `tests/test_schema_migrations.py`: 266 passed in independent review.
- Focused auth/config/WS review: 82 passed in seeded order; post-review isolation tests for legacy direct resolution and missing session schema pass.
- Focused local gates passed: `tests/test_schema_migrations.py` (32 in the local focused run), `tests/test_user_sessions.py tests/test_principal.py tests/test_api_auth.py tests/test_boot_config_assert.py` (69 before the final isolation addition), and `tests/test_api_versioning.py tests/test_health_endpoint.py` (41).
- `python -m compileall -q app migrations tests` and `git diff --check` passed.
- The full repository suite remains blocked by existing `tests/test_account_scoped_state.py` fixtures attempting to downgrade through existing migration `0023`, whose intentional downgrade refusal raises before `0028` is reached.

## Deferred boundary

The owner-gated frontend still sends the retired query-token WebSocket handshake and therefore must be migrated in its own frontend task to send the post-accept authentication frame. Task 5A leaves frontend files untouched and rejects that unsafe legacy handshake. No Task 5B route-family IDOR conversion was included.
