# ADR 0003: Durable portfolio admission and capital reservation

Status: PROPOSED

Date: 22 August 2026

Risk: critical

## Context

Current Strategy OS collects simultaneous candidates and applies deterministic priority in one process. Account execution leases provide one current holder. The decision and capital commitment are not durable facts.

Dynamic Universes increase candidate count and make recovery, contention, and explanation more important.

## Decision

Add:

- CandidateIntent;
- DecisionBatch;
- PortfolioAdmissionDecision;
- CapitalReservation;
- why-trade and why-not-trade receipt.

Keep:

- account execution lease as single writer;
- priority subset as default;
- no silent resizing;
- atomic baskets whole;
- risk-reducing exits outside entry reservation gates.

Each batch freezes the candidate set, margin snapshot, safety buffer, policy, rank tuple, constraints, and decision.

Each admitted candidate receives one durable reservation before order submission.

## Consequences

- simultaneous decisions replay deterministically;
- recovery can distinguish reserved, submitted, uncertain, consumed, and released capital;
- UI can explain every outcome;
- broker rejection remains possible and explicit;
- implementation changes a money boundary and requires owner approval plus independent critical review.

## Rejected alternatives

- in-process mutex as final authority;
- distributed lock without persisted state and fencing;
- worker-by-worker margin queries;
- first-arrival wins;
- silent proportional resizing;
- deleting expired reservation history.
