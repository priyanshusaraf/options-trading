---
description: API surface, auth, principals, ownership, tenant isolation, credentials
paths:
  - "paper-trader/backend/app/api/**"
  - "paper-trader/backend/app/core/config.py"
  - "paper-trader/backend/app/core/runtime_config.py"
  - "paper-trader/backend/app/ws/**"
---

# Tenancy and security

Treat this as software that will hold broker credentials and real-money execution authority for
multiple users. Invoke `.claude/skills/` review agents rather than self-assessing.

## Where the system actually stands (measured 2026-08-08)

- Auth is **one shared bearer token** (`PT_API_TOKEN`); empty disables auth entirely and empty is
  the shipped default and the production posture on a tailnet-only box.
- `app/api/principal.py` is the seam: a `Principal` on every request, `ANONYMOUS_OWNER` rather
  than `None`, scopes modelled and unused. `is_allowed()` is honestly "the owner may do
  everything".
- **There is no object ownership.** `Project` has no owner column; `graph_artifacts.identifier`
  is a global primary key. Only `research_review_routes.py` references `principal`.
- Cross-**project** isolation is enforced and tested. Cross-**principal** isolation does not exist.

This is accurate for a single-user system and is the V1 blocker. When you add ownership, add it
as a dimension on the object, not as a filter in a route.

## Rules

- **Authorization lives in one place** — `principal.py::is_allowed`. A check anywhere else
  destroys the property that makes the seam worth having.
- **Never trust a client-supplied identity.** Graph identity, evidence identity, version and
  content addresses are derived on the server, never accepted from a caller.
- **Every list read is bounded** at the query (SQL `LIMIT`) *and* at the request
  (`app/api/paging.py::MAX_PAGE`). Either alone leaves a memory-exhaustion path into the risk
  lane, and hard invariant 2 says nothing may block an exit.
- **Cache keys must carry every dimension that changes the answer** — including the owner once
  ownership exists. A tenantless cache key is a cross-tenant read.
- **Secrets never reach logs, errors, receipts or API payloads.** Research operation receipts are
  deliberately bounded to server-owned summaries for this reason.
- **`/api/health` is exempt from auth on purpose** and must stay operational-state-only.

## The threat list for this product

Cross-tenant access · IDOR · cross-account execution · broker credential leakage · principal
substitution · tenantless cache keys · tenantless DB access · user-controlled account or provider
identities · paper/live boundary violations · authority escalation · stale authority or signals ·
research/deployment content-address mismatch · execution attribution mismatch · unscoped broker
connections · secrets in logs.

Deterministic rules catch some of these. Do not pretend tooling guarantees security — keep an
independent reviewer (`security-tenancy-reviewer`).
