# Multi-user contract design

**Date:** 2026-08-11
**Programme:** revised ten-phase Strategy OS implementation plan
**Phase:** 1 — establish the multi-user contract

## Outcome

Strategy OS must represent more than one customer without relying on a route filter over
single-owner storage. Ownership is an identity dimension in persistence, repository lookups,
cache addresses, exports and WebSocket fan-out. The system remains unavailable to external
customers until the cross-tenant gate at the end of this phase passes.

## Identity model

- `Organization` is the durable customer/tenant and is the value referenced by existing
  `owner_id` fields. Money-plane rows continue to use a by-value owner identifier so the later
  physical database split does not create cross-plane foreign keys.
- `User` is a human identity. Email uniqueness belongs to the identity system, not to a tenant.
- `Membership` relates a user to an organization with one of `owner`, `admin`, `member`, or
  `viewer`. Authorization remains centralized in `app/api/principal.py`.
- `BrokerAccount` is a money-plane account identity owned by an organization. A broker
  connection authenticates access; a broker account identifies whose positions, funds and
  reconciliation state are being addressed. They are not interchangeable.

The legacy single-user installation is represented explicitly:

```text
organization_id = owner
user_id         = owner-user
broker_account  = account.default
```

Existing `owner_id='owner'` rows remain truthful and are not rewritten to a fabricated customer.

## First vertical slice

Revision `0018` adds the four tenancy roots, seeds the legacy identities, and replaces the three
singleton money identities that migration `0017` correctly refused to decorate:

```text
capital_state          (broker_account_id, book)
instrument_state       (owner_id, instrument_key)
daily_account_snapshot (broker_account_id, day)
```

The migration preserves every existing row under the legacy account/owner. On SQLite this is a
table-rebuild migration with explicit copy and validation. A downgrade is allowed only when rows
can collapse back to the legacy singleton identities without collision; otherwise it refuses and
the rollback path is restore-based.

The slice updates every direct repository/service consumer of those keys. It does not claim that
projects, graphs, backtests, routes, caches or WebSockets are tenant-safe yet; those are the
remaining Phase 1 slices.

## Remaining Phase 1 boundaries

1. Scope all money repositories and execution reads by organization/account.
2. Add ownership to user-plane objects and make display names tenant-local.
3. Add ownership to jobs/backtests and tenant-separate reusable result addresses.
4. Resolve real principals and memberships, then pass principal scope into every route/export.
5. Partition WebSocket fan-out and all answer-changing caches by tenant.
6. Run adversarial guessed-ID, wrong-account, cache-poisoning and fan-out isolation tests.

## Invariants

- No client chooses its `owner_id` or `broker_account_id` for an operation; both derive from the
  authenticated principal and deployment/account binding.
- Authorization policy stays in `principal.py::is_allowed`.
- No money row is silently reassigned during migration.
- Existing execution recovery continues matching owner, broker, account and connection.
- The current dirty provider files are outside this phase and must not be edited.
- Live deployment and destructive production migration remain owner-gated.

## Acceptance evidence

- Two organizations can store the same book, instrument key, day, project name and strategy name.
- A repository lookup under organization/account A cannot return B's row even when the remaining
  identifiers are identical.
- Legacy money values survive the `0017 -> 0018` upgrade exactly.
- Fresh model schema and migrated schema remain equivalent.
- `0018 -> 0017` either restores the exact old shape or refuses a lossy collapse.
- Full backend and research suites, `LEDGER OK`, and `SWEEP OK` pass before Phase 1 closes.
