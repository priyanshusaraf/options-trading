"""One page bound for every list-returning read on the API surface.

The reason this constant exists rather than a literal per route: an unbounded `limit`
lets any caller turn a reporting endpoint into a table dump. That is not a hypothetical
failure mode here — the 2026-07-23 outage was exactly this shape from the inside
(full-table ORM scans under a 5-second dashboard poll, ~100 MB/min growth, a 1 GB droplet
OOM, and the DB pool collapsing with real positions open). The lesson recorded then was
about the *query*; the query is now bounded, but a caller could still ask for
`?limit=10000000` and be served every row the table holds.

Two independent controls, deliberately:

  * the query bounds the read (`analytics._narrow(...).limit(...)`), so the database is
    never asked for more than a page;
  * this bounds what a caller may *request*, so the page itself cannot be unbounded.

Removing either one leaves a path back to the outage. Hard invariant 2 is why the bar is
this low: a reporting endpoint that exhausts memory takes the fast risk lane with it, and
not getting out is worse than any other failure.

The value is generous on purpose — well above every default and every page the shipped
frontend asks for (100 trades, 300 log lines, 500 backtest cells), so this cannot break a
client. It is a ceiling on abuse, not a pagination policy. FastAPI answers 422 above it,
which is a refusal a caller can read, not a silent truncation.
"""
from __future__ import annotations

MAX_PAGE = 5_000
