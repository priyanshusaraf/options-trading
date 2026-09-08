# Interaction audit

Status: static source inspection

This audit did not start either frontend. It records source-visible behavior and gaps. Runtime usability, timing, confidence, console, network, and screen-reader results remain unmeasured.

## Visual direction

Keep the accepted standalone prototype direction.

Its strongest structural decisions are:

- clear global navigation;
- strategy-local navigation only inside a Strategy context;
- one dominant working surface;
- optional context drawer;
- visible version and lifecycle facts;
- calm overview and denser research or operations;
- separate presentation from executable identity;
- desktop for material graph changes;
- mobile for Today, Live, Activity, and safe controls.

No new palette, typography, or styling system is proposed here.

## Current production strengths

- one React application and one WebSocket;
- shared API client;
- dedicated mobile top bar;
- horizontal table containment checks;
- separate semantic graph and layout revisions;
- canonical server batch-edit seam;
- visible validation, transport, and conflict states;
- undo and redo based on server command receipts;
- graph layout persists outside executable identity;
- backend-owned provider health;
- explicit research feature gate.

## Current production gaps

- the global shell presents a long flat tab list rather than the accepted global and Strategy-local hierarchy;
- Strategy context does not organize all research and operation surfaces;
- Backtests are disabled on mobile without a companion summary;
- browser realtime state reduces transport to connected true or false;
- the graph renderer is custom and lacks the prototype's palette, connection, resize, insertion, inspector, focus, and search behavior;
- the current app does not expose Dynamic Universe, Workflow, candidate lineage, portfolio admission, or reservation facts;
- progressive disclosure is inconsistent across older operational surfaces;
- static tests cannot prove keyboard completion, screen reader output, focus recovery, or pointer alternatives.

## Benchmark-task readiness

| Task | Source-visible readiness | Main gap |
| --- | --- | --- |
| Create or clone first Strategy | PARTIAL | no accepted onboarding shell in production |
| Change one parameter | IMPLEMENTED | runtime usability unmeasured |
| Run backtest | IMPLEMENTED desktop | mobile summary absent; assumptions view incomplete |
| Discover exact result assumptions | PARTIAL | identities exist across receipts but no unified reconstruction view |
| Compare baseline and candidate | PARTIAL | research feature-gated and behavior unmeasured |
| Understand OOS, walk-forward, Monte Carlo | PARTIAL | backend evidence exists; guided UX not proven |
| Identify missing or stale data | PARTIAL | provider health exists; per-input causal explanation incomplete |
| Understand invalid node | IMPLEMENTED in graph edit errors | exact large-graph localization unmeasured |
| Publish immutable revision | IMPLEMENTED | workflow clarity unmeasured |
| Paper deploy | PARTIAL | current routes exist; accepted V1 shell not integrated |
| Understand preflight refusal | PARTIAL | composite preflight and UI are later work |
| Suspend and recover deployment | PARTIAL | backend lifecycle exists; user flow unmeasured |
| Explain why a trade fired | PARTIAL | facts exist in several views |
| Explain why candidate rejected | ABSENT as durable portfolio receipt | needs DecisionBatch view |
| Resolve simultaneous capital contention | ABSENT | needs admission and reservation UI |
| Inspect degraded provider or stream | PARTIAL | backend health exists; client state is too coarse |
| Navigate and edit large graph | PARTIAL | prototype behavior exists, production adoption absent |
| Recover accidental edit without changing live version | IMPLEMENTED in draft semantics | end-to-end user proof absent |

## High-priority interaction recommendations

1. Adopt the prototype's global and Strategy-local navigation structure.
2. Show one provenance line on every Strategy surface:
   Strategy version, data or Universe binding, evidence state, deployment state.
3. Keep draft, published, admitted, deployment, and money facts visually distinct.
4. Add a reason panel for every refusal.
5. Add why-trade and why-not-trade views from durable batch receipts.
6. Split realtime status into transport, authorization, subscription, first event, freshness, and provider health.
7. Use xyflow only as the canvas view layer. Keep backend edit and identity contracts.
8. Add pointer alternatives for drag and resize.
9. Test the full graph editor without a mouse.
10. Virtualize or paginate long node, candidate, event, and evidence lists.

## Progressive disclosure

Use one consistent depth:

    conclusion
      → reason
      → evidence
      → raw receipt

Examples:

- Deployment refused.
- Provider cannot supply historical OI at the required range.
- Show exact requirement and capability result.
- Open the immutable assessment receipt.

Do not hide a critical refusal behind a generic warning count.

## Realtime language

Use:

- Connected to Strategy OS.
- Broker session authenticated.
- Market subscription acknowledged.
- Waiting for first event.
- Data stale since 10:31:42.
- Resync required.

Do not use:

- Live, when only the browser transport is connected.
- Healthy, when the provider has no current event.
- Ready, when preflight is incomplete.

## Accessibility

Future acceptance must prove:

- skip to main content;
- logical heading order;
- visible focus;
- no keyboard trap;
- graph actions available without drag;
- 44 by 44 pixel touch targets where practical;
- status never uses color alone;
- meaningful live-region updates;
- reduced-motion behavior;
- error associated with the exact control;
- focus returns after dialog close;
- graph nodes and edges have navigable accessible descriptions.

## Mobile

Keep mobile focused on:

- current risk;
- position and protection state;
- provider and broker health;
- paper state;
- activity and reasons;
- pause, disarm, and kill actions under existing authority.

Do not make the 390-pixel surface the primary place for:

- graph topology edits;
- Workflow authoring;
- dense Universe ranking design;
- live authority migration.

## Performance

The future frontend capsule should profile:

- 100, 300, and 1,000 node graphs;
- 2,000 and 10,000 Universe candidates;
- 1,000 evidence records;
- realtime updates under slow browser conditions;
- 390 by 844 layout;
- current reference desktop.

No optimization is accepted without the same before and after workload and output-equivalence proof.

## Verdict

KEEP the accepted styling. REFACTOR the product information hierarchy through a future frontend owner gate. KEEP the current semantic edit and layout separation.
