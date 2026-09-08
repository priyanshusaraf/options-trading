# Configurable entry order policy

**Date:** 2026-08-09  
**Branch:** `codex/execution-foundation`  
**Status:** approved by the owner in the 2026-08-09 continuation direction

## Outcome

Strategy OS must let the operator choose how new entries are submitted. The supported modes are:

- `AUTO`: retain the existing liquidity-aware option router. Tight, sufficiently deep books use `MARKET`; moderate or thin books use a capped `LIMIT`; unusable or excessively wide books are skipped.
- `MARKET`: submit a market entry when the available liquidity evidence passes the hard entry veto. A known thin top of book or a spread above the configured maximum is skipped rather than overriding the safety boundary.
- `LIMIT`: submit a capped limit entry. Buy limits are capped above the reference midpoint and sell limits below it. The broker adapter remains responsible for snapping the price to the instrument's actual tick grid.

The effective `MARKET` or `LIMIT` choice and limit price are immutable fields on the durable execution intent. Recovery must replay that instruction and must never substitute another order type.

## Current truth

The repository has partial limit-order infrastructure, not user-configurable support:

- `OrderRequest`, `KiteOrderClient`, and the execution lifecycle can carry `MARKET` and `LIMIT`.
- The options runner chooses automatically from spread and depth.
- the live equity entry path hardcodes `MARKET`.
- the Settings UI exposes thresholds but no order-mode choice.
- the backtester models next-bar market fills plus a cost allowance; it does not model resting limit orders.

## Architecture

Order purpose and order side are separate concepts. `ENTRY` versus `EXIT` determines safety policy; `BUY` versus `SELL` determines price direction. A short equity entry is therefore `ENTRY + SELL`, not a protective exit.

The pure planner owns the decision. Callers supply quote evidence, requested mode, and risk thresholds. It returns one `OrderPlan` with `MARKET`, `LIMIT`, or `SKIP`. The runner uses the plan for allocation and logging. `LiveBroker` consumes the same plan and freezes it into `ExecutionIntent` before broker submission.

The current equity candidate path has a reference price but no order-book snapshot. To avoid fabricating liquidity, `AUTO` keeps its existing market behavior for equity. Explicit `LIMIT` derives a side-aware cap from the reference price. A later market-data depth slice will replace this reduced-evidence branch with the same book-aware policy used for options.

## Failure behavior

- Invalid mode values are rejected at the runtime and scoped-configuration write boundaries.
- An invalid quote or a known book beyond the hard spread/depth boundary produces `SKIP`.
- A limit order that does not fill within the polling window is not automatically repriced or resubmitted. It stays durable and unresolved until cancellation/fill reconciliation proves its state.
- Partial and late fills use the existing cumulative-fill recovery path and are protected before booking is finalized.
- Exits remain market orders in this slice. Limit exits require a separate risk-reduction design.

## Backtest contract

This slice does not label the existing next-open fill model as a limit-order simulation. A later fill-model slice must add an explicit model version with:

- market entry at next bar open plus configured adverse cost;
- limit entry evaluated one bar at a time without access to future bars;
- a declared touch/penetration rule, time-in-force, gap improvement rule, and no fabricated partial fills without volume or book data;
- cache identity including order mode and every fill-model parameter;
- parity fixtures that prove the streaming simulator and optimized runtime agree.

## Acceptance

1. Settings and scoped configuration accept only `AUTO`, `MARKET`, or `LIMIT`.
2. The pure planner distinguishes `ENTRY + SELL` from `EXIT + SELL`.
3. Forced market and limit modes retain the hard liquidity veto where book evidence exists.
4. Option and equity live entries submit the selected order type.
5. Durable intents contain the effective order type and limit price.
6. Existing `AUTO` behavior remains unchanged.
7. Focused backend and frontend tests pass before the branch-wide verification suite.
