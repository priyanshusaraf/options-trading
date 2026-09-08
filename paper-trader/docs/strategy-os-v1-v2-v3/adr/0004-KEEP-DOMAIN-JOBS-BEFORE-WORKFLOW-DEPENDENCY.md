# ADR 0004: Keep domain jobs before adopting a Workflow dependency

Status: PROPOSED

Date: 22 August 2026

## Context

Strategy OS already has durable research operations, claims, heartbeats, item checkpoints, takeovers, cancellation, and events.

DBOS, Temporal, and Restate offer broader durable execution. Each adds replay rules, migration, deployment, operational, and failure modes.

## Decision

Keep Strategy OS job and domain facts authoritative.

Do not adopt a general Workflow dependency before:

- a concrete current ceiling is measured;
- one non-money scenario compares current operations, DBOS Python, and one server-backed alternative;
- cancellation, wrapper side effects, duplicate delivery, process death, database failure, and migration pass;
- the backend remains replaceable behind a domain port.

Never place a general Workflow engine in the live broker order path.

## Consequences

- V1 progress continues without new infrastructure;
- V2 retains a clean insertion point;
- a future backend may own scheduling while Strategy OS owns every business fact;
- adoption remains evidence-driven.

## Rejected alternatives

- install a Workflow server now;
- use workflow IDs as Strategy, candidate, deployment, or order IDs;
- persist business authority only in workflow metadata;
- retry real-money steps without reconciliation.
