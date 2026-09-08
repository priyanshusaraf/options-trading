# Strategy OS — Product Overview

*Current product direction and honest delivery state. Updated 2026-08-13.*

## Product

Strategy OS is a broker-agnostic, multi-user platform for taking a strategy from
research through backtest and controlled deployment. It gives an individual, team,
or future customer organization a private workspace for strategy definitions,
research evidence, backtest results, and eventually broker-account-bound execution.

The product separates four concerns:

1. **Research:** create and evaluate strategies, datasets, hypotheses, evidence, and
   decisions without granting an execution right.
2. **Backtest:** run reproducible simulations against identified inputs, retain the
   result and provenance for its owner, and reuse only computation that is safe to
   share.
3. **Deploy:** turn an approved strategy into an explicit paper or authorised-live
   deployment with a named owner and broker account.
4. **Operate:** show the owner what ran, what it decided, what it submitted, and what
   happened afterwards without exposing another owner's private content.

Strategy semantics should not depend on a particular broker. Market-data providers
and execution venues are separate roles with declared capabilities. That is a product
and architecture direction, not a claim that several production broker adapters are
already proven.

## Current delivery state

The visual strategy foundation exists: typed component IR, immutable graph versions,
content addressing, deterministic evaluation, and research evidence tied to the
version that produced it. The legacy paper/live engine and its safety controls remain
separate from broad Strategy OS adoption. A graph-backed paper-authority path exists;
graph-backed live authority remains deliberately unapproved.

Phase 1 is closed. Organization, user, membership, and broker-account roots now anchor
owner-scoped money, strategy, research, review, backtest, API, export, WebSocket, cache,
job, session, and execution boundaries. The adversarial two-tenant gate is part of the
closure evidence.

Phase 2 is implemented on the current branch. The execution, research, and ledger
planes have explicit PostgreSQL profiles and verified SQLite-to-PostgreSQL copy tooling.
Execution accounts use durable leases, monotonically increasing fences, recovery state,
and durable controls. Plane-local transactional outboxes support scoped replica refresh;
PostgreSQL notifications shorten the wait while durable polling remains authoritative.
Local PostgreSQL restore and bounded workload rehearsals exist.

SQLite remains supported for local development, tests, and a single-node profile. The
PostgreSQL implementation and local proofs do not establish a managed production
topology, managed point-in-time recovery, geographic failover, or production capacity.

## Safety and data boundaries

Money safety remains stricter than general product work. An execution identity must
name an owner and broker account; only one fenced actor may submit orders for that
account. Paper mode and live execution stay behind independent, explicit gates. An
approved research result is evidence, not permission to trade.

Private strategy and research material is owner-local by default. A content address
or cache lookup must not reveal that another owner has a private strategy, dataset, or
result. Shared public market computation may be reused only through a neutral,
verified artifact and never by returning another owner's run or parameters.

The platform will keep the existing execution safeguards and accounting discipline as
it evolves. The relevant work includes paper-by-default behavior, explicit arming and
kill controls, fail-closed order paths, lifecycle journalling, reconciliation, and
net-of-cost reporting. These controls require continued review as execution moves
from a local engine to account-isolated workers.

## Capacity and production concurrency

`500 users` is a launch-validation workload and cost checkpoint. It is not a product
limit, a database limit, or a per-process configuration constant. Capacity is measured
as a workload vector: active broker accounts, subscribed instruments, concurrent
research jobs, backtest cells, order submissions, database contention, cache behavior,
and WebSocket bytes.

Phase 2 supplies the local PostgreSQL and concurrency foundations: shared durable
authority, fenced execution ownership, replicated API ownership, scoped event delivery,
recovery tooling, admission controls, and bounded load/failure rehearsals. The intended
growth path adds control-plane replicas, research workers, market-data fan-out, and
bounded execution cells. Further schema and ownership changes may still be required
when production evidence exposes them.

A managed topology, sustained production load, managed recovery targets, and operating
cost are not yet proven. Those claims require deployment-specific load, failure, restore,
and cost evidence. The current implementation does not establish effortless horizontal
scale or a production capacity ceiling.

## Historical engine context

The repository began as a single-user, single-account autonomous Indian-options
engine. That work provides useful execution context, but it is not the current product
definition. The former trend-and-displacement options strategy is one historical
strategy implementation, not the platform's defining strategy or the limit of its
research model.

Useful lessons carried forward from that engine include:

- backtests and live behavior need explicit parity evidence;
- options execution must model liquidity, slippage, fees, taxes, expiry, and theta;
- a slow provider or broker response must not block protective position management;
- a paper/live boundary must fail closed and remain visible to the operator;
- a reported result needs reconciliation and complete cost treatment; and
- a plausible options edge still needs evidence from representative data and fills.

Open questions from the historical engine also remain relevant: the fidelity of
historical option-premium and implied-volatility data, realized slippage across market
conditions, validation of synthetic-premium approximations, regulatory requirements,
and evidence that a strategy remains profitable after full execution cost. Strategy
research must treat these as testable claims, not settled assumptions.

## What comes next

The immediate goal is to close the bounded Phase 2 review findings, then return to the
research product and frontend. Managed PostgreSQL deployment, real PITR rehearsal,
capacity measurement, cost measurement, and production rollout remain separate gates.
Frontend delivery remains deferred until the backend/research closure is accepted.

For detailed current status, see [the verified gap map](superpowers/specs/2026-08-12-strategy-os-v1-verified-gap-map.md), [the Phase 1 plan](superpowers/plans/2026-08-11-phase-1-multi-user-contract.md), and [the roadmap](ROADMAP.md).
