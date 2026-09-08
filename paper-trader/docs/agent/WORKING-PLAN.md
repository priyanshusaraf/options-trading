# V0 working plan

Updated 8 September 2026. V0 remains unfinished. The latest explicit assignment controls the current task; this plan supplies product context, not a second permission process.

## Product outcome

Complete the invited-user journey:

**Sign in → open a preset or create a strategy → understand and modify it → check data compatibility → backtest → challenge the result → compare revisions → save evidence → monitor supported conditions → inspect attributable alerts.**

Provider API data is the primary watchlist and backtest journey. CSV is optional. Support connected-provider instrument selection, historical fetching and attributable dataset reuse. Explain requested versus returned dates, missing coverage, freshness and the effective test window. Distinguish request-size limits from total available history. Historical research data does not establish current monitoring freshness.

V0 verification uses OHLCV, including cross-instrument inputs. Broad options history, order flow, dynamic discovery and all-30-strategy coverage are deferred. Keep their designs for the [later releases](../strategy-os-v1-v2-v3/V0-V1-V1.5-V2-V3-V4-V5-V6-SCOPE-DECISION-MATRIX.md). Paper accounting remains a correctness concern; trading is not a required step in this journey. Public live execution stays closed.

## Priorities

First finish automatic alerts: fresh provider data → completed-bar evaluation under saved rules → persisted, attributable alert → inbox and detail. Verify trigger timing, deduplication on retry/restart, stale-data and warmup handling, and recovery through the real local interface and backend. Complete this before hierarchy and explicit moves.

1. Finish the provider-driven data and canonical research path, including causal inputs, identity, isolation, costs, development/holdout separation and robustness.
2. Make Watchlists the instrument-and-results screen: add instruments, choose each row’s saved strategy and timeframe, inspect current results and data health, pin/filter rows, and start or pause monitoring. Keep the current app palette; the old bot is a functional reference, not a visual template. Put history acquisition and saved-data details in secondary controls. Complete the monitoring-to-alert lifecycle alongside revisions, comparison and saved research evidence; preserve inputs on rejection.
3. Use the desktop research studio palette, an on-demand component explorer and a conditional inspector. Home follows actual drafts/research activity. Phone work is deferred. Keep one IR and separate prototype variants.
4. Verify separate original Trend Impulse V3 and Expanding Z V4 presets with independent arithmetic and representative cross-instrument/history cases. No fixture-specific production logic.
5. Finish clean-account journeys, failure/recovery/isolation checks, release build and migration/restore evidence. Prepare a concrete candidate for deployment approval; after approval, verify the deployed journey.

## Current work and evidence

### Watchlist acceptance requirements

- Provide independent Global membership, strategy-specific watchlists and a derived Master view. Master reads existing memberships and monitoring results; it must not create assignments, evaluations or alerts.
- Within an owner/workspace, each instrument may belong to only one strategy-specific watchlist. Enforce this on backend writes, imports and concurrent requests. Reject conflicts with a useful explanation and offer an explicit move; never silently reassign.
- Adding an instrument to an active strategy starts eligible monitoring after compatibility, freshness and warmup checks. Show the reason when monitoring cannot start.
- Verify explicit moves, removal, pause/resume, process restart, strategy attribution and owner isolation through the real backend and interface. Preserve historical evidence and existing position-management obligations through membership changes.

These are completion requirements, not claims of implemented or verified behavior.

### Build transparency acceptance requirements

- Provide persistent root and nested-instance editor tabs. Expose internal nodes, connections, parameters and input/output bindings so strategy behavior can be inspected directly.
- Preserve drafts, undo/redo and navigation state across tab switches and navigation; verify the promised persistence across reload and restart.
- Opening or inspecting internals must not change executable identity. Editing published or shared internals requires an explicit local copy or new version, with instance isolation and clear provenance.
- Verify the real editor journey as well as identity and persistence tests. This work may proceed in parallel with the primary monitoring/alerts work.

[Status](STATUS.md) owns open defects, integration results and handoff links. Update that page rather than appending another continuation paragraph here. Do not replay historical capsule restrictions or duplicate another task's writers.

Work in this checkout with exclusive write ownership. Finish monitoring/results/alerts first, then the assessed presets, watchlist hierarchy and Build tabs. Use Astra medium as main and Astra low for delegated children; serialize heavy runs and preserve explicit model choices.

The owner pursues commercial API approvals separately. Continue authorized software and personal-research work without treating future commercial decisions as a blanket blocker. The supplied 248-session NIFTY file is approved for current daily checks; optional Telegram options data remains outside this OHLCV cohort. No live credentials, orders or deployment authority follows.

## Completion rule

Follow source → repository check → reproduction → justified change → verification. Reuse focused evidence unless behavior or unresolved risk changes. Administrative gaps do not invalidate working behavior; technical evidence gaps stay open.

Use root AGENTS.md for code-quality requirements and external-action gates. Distinguish implementation, local integration and deployment. Do not declare V0 complete from phase records.
