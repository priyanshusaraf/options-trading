# Providers and tenancy

- Separate market data, execution, account/portfolio, and instrument-resolution connections. A singleton provider factory is not split routing.
- Strategy OS owns canonical instrument identity. Provider tokens and symbols map onto it; strategies never persist provider identifiers.
- Keep provider quirks at the adapter edge. Require declared capabilities, conformance tests that catch capability lies, and recovery evidence for rejection, partial fill, idempotency, expiry, reconnect, postbacks, and restart.
- External code is not copied. For broker work inspect Strategy OS first, then OpenAlgo as an AGPL-3.0 behavior reference only, then other permitted sources. Inspect each licence itself; classify `DIRECT REUSE`, `ADAPT-WRAP`, `REFERENCE ONLY`, or `REJECT`. Stop for an owner/legal decision before licence-sensitive adoption.
- Authorize in one seam, derive identity server-side, bound list queries and requests, keep secrets out of outputs, and include each answer-changing dimension (including owner once ownership exists) in cache keys and data access.
- Keep `/api/health` auth-exempt only while it remains operational-state-only; do not let it disclose tenant, credential, strategy, or money state.

Treat cross-principal isolation as incomplete until object ownership exists. Do not claim security from an absence of findings.
