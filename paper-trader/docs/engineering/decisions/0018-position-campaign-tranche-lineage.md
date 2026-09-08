# ADR 0018: Position remains operational; campaign and tranche lineage are additive

- **Status:** FROZEN FOR PHASE 5 IMPLEMENTATION; NO HISTORICAL INFERENCE
- **Date:** 2026-08-25
- **Depends on:** ADR 0012, ADR 0017, execution intent/event and trade attribution

## Context

The current `Position` is the operational aggregate used for marks, stops, exits
and book isolation. Target-position additions and reductions need lineage across
multiple intents and fills, but putting order lifecycle or reservation state on
`Position` would collapse physical inventory, broker evidence and portfolio
admission into one mutable row.

## Decision

Keep `Position` as the current held-inventory aggregate. Add immutable campaign,
tranche and fill-allocation facts linked to it. They explain how inventory was
formed and reduced; they do not become a second current-position authority.

`PositionCampaign` carries owner/account/book, deployment and exact strategy
attribution, canonical instrument/resolved product, direction, target-policy
identity, opened/closed times, status, legacy classification and digest.

`PositionTranche` carries campaign, target request, candidate, batch, decision,
reservation, execution intent, side/purpose, requested and admitted quantity,
state, creation/terminal times and digest. Entry/addition and reduction tranches
are distinct facts.

`FillAllocation` maps one immutable execution-order event/fill delta to one
tranche and quantity. The sum of allocations must equal the fill delta; one fill
cannot be allocated twice. `Trade` remains realized money evidence and links to
the allocation/campaign where known.

## Invariants

- `Position.qty` equals exact held quantity reconstructed from booked fill
  allocations for current rows after the new boundary is enabled.
- Campaign/tranche lineage never changes owner, account, book, deployment,
  strategy attribution, canonical instrument, resolved product or direction.
- A target reduction consumes held inventory; it never creates a negative entry
  reservation or changes campaign ownership.
- Partial fills allocate monotonically and never over-consume a reservation.
- Opposing strategies on one account keep separate campaigns and physical
  ownership even when they share an instrument.
- Order lifecycle remains in `ExecutionIntent`/`ExecutionOrderEvent` and command
  recovery remains in `AccountExecutionCommand`.
- Risk-reducing exits remain available when entry admission, reservations or
  campaign creation are blocked.

## Legacy rows and migration

Migration is additive. Existing `Position`, `Trade`, intent and event bytes are
preserved. Legacy positions do not receive inferred campaigns, tranches,
reservations or fill allocations. Nullable links or an explicit
`legacy_unattributed` classification make the absence visible. A controlled
forward process may create lineage only from exact pre-existing intent/event/fill
evidence; labels, current slots, quantities or timestamps alone are insufficient.

Downgrade cannot discard new lineage after writes exist. Rollback disables new
campaign/admission writes, preserves immutable facts and uses forward
reconciliation for broker-touched reservations.

## Required evidence

Tests cover multi-fill addition, partial reduction, full close, cancel/fill
crossing, opposing campaigns, restart, exact held-inventory reconstruction,
legacy visibility, cross-owner/account refusal, mutation of fill-allocation
uniqueness, and exit availability during entry blockage. No frontend or live
behavior switch is authorized by this ADR.
