# ADR 0016: Execution Product Policy resolves signal intent before sizing

- **Status:** FROZEN FOR PHASE 5 IMPLEMENTATION; NOT WIRED
- **Date:** 2026-08-25
- **Depends on:** ADR 0012, canonical instruments, execution binding, broker-account isolation

## Context

Strategy logic, execution placement, sizing and tradable-product selection are
different facts. Current options, equity and futures entry paths select products
inside their own engine branches. A target-position contract cannot safely depend
on those distributed choices, and moving selection into the strategy would make
the graph own broker/product authority.

## Decision

Add one asset-neutral `ExecutionProductPolicy` seam after canonical execution
binding and before sizing. It maps one bound signal intent plus explicit market
and account facts to either one immutable `ResolvedExecutionProduct` or one typed
refusal. It does not submit an order, size a position, read a provider, select a
strategy, or grant authority.

The existing options, equity and futures selection behavior remains the
compatibility implementation. Phase 5 may prove a new policy result equivalent in
paper/shadow evidence, but may not switch authoritative live behavior.

## Contract

`ExecutionProductPolicy` carries:

- policy identifier, version and content address;
- owner/deployment scope and permitted execution modes;
- asset/product family and canonical instrument-role rules;
- selector version and explicit liquidity, expiry, session and order constraints;
- rounding/lot metadata source rules;
- refusal policy and evidence schema version.

`ProductResolutionRequest` carries:

- exact `ExecutionBinding` identity and admission/graph attribution;
- canonical signal instrument and direction;
- decision time and completed-bar/source evidence;
- owner, broker account, paper/live book and deployment;
- explicit market snapshot and capability addresses;
- requested target-position or entry purpose.

`ResolvedExecutionProduct` carries:

- policy address and request digest;
- canonical execution instrument plus provider-neutral product identity;
- tradingsymbol/exchange/product/order capability facts only after an adapter has
  supplied a typed mapping;
- lot size, quantity step and price/tick constraints with source addresses;
- selected-contract evidence and typed refusals;
- content digest.

## Authority and dependency direction

- `execution_binding.bind` remains the only strategy-selection decision.
- Strategy OS canonical instruments remain authoritative; provider aliases are
  evidence, never product identity.
- Provider and execution broker remain separate roles.
- Product policy consumes a binding verdict and cannot widen graph/live authority.
- Sizing consumes a resolved product; product policy never consumes a sizing
  result.
- Broker margin remains external final authority after reservation and before
  submission.

No second deployment, instrument, provider, order or money model is created.

## Failure posture

Missing, stale, conflicting, non-finite or unsupported product facts produce a
typed refusal before sizing or reservation. There is no default-product fallback
for an explicit policy. Risk-reducing exits continue through their current held-
instrument path and never require a new entry product resolution.

## Implementation and review gate

The first implementation is pure contracts and compatibility adapters with no
runner wiring. Tests must cover exact options/equity/futures parity, canonical
instrument and provider-alias mismatch, stale capability, unsupported product,
paper/live separation, and exit independence. Any behavior switch, provider
networking, broker action, or live eligibility requires a separate owner gate.
