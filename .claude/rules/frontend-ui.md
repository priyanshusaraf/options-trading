---
description: Cockpit UI, React, operator surfaces, runtime verification
paths:
  - "paper-trader/frontend/**"
---

# Frontend and UI

**Claude does not own frontend implementation by default** — that normally belongs to
ChatGPT/Codex. What Claude owns is the backend contract the UI consumes, and the *verification*
that a UI change actually works. When you do change frontend code, invoke
`.claude/skills/ui-acceptance`.

## The standard this cockpit is held to

The cockpit answers three questions without an ssh session: **is it working right now**, **what
is it holding**, **what is it about to do**. A pane that cannot answer one of those does not earn
its place.

Every number on screen is either true or visibly marked **Unknown** — there is no third state. A
stale reading must never render as the last good value wearing a green badge; that is the failure
mode that hid both 2026-07 outages, where a liveness stub returned 200 through the whole
incident.

Dense, monospace, chip-and-table, dark. Information per square inch is the metric. The layout
must work one-handed at **390px**, because the moment it matters most is closing a position from
a phone.

## Architecture constraints

- **One WebSocket.** `state/LiveContext.tsx` holds the single `/ws` connection. A second
  WebSocket anywhere in the app is a defect.
- **All REST goes through `lib/api.ts`.** A `fetch` outside it is a defect.
- The frontend does not compute a second opinion on backend truth — `readiness.py` decides
  ok/degraded/down, `lib/health.ts` renders that verdict.
- A new backend knob needs a `settingsMeta` entry or it is invisible in the UI. An unclaimed key
  is an invisible key; keep the `['Other', () => true]` catch-all.

## Tests are not acceptance

Vitest green, `tsc` green and `npm run build` green are **necessary and insufficient**. They
cannot see a blank page, a mis-wired value, an overflowing table or a console error.

Acceptance means: run the app → open the browser → perform the intended operator flow → inspect
layout and interactions → inspect console and network → check loading, error and empty states →
screenshot → fix what you see. Use `.claude/skills/run-strategy-os` to start it and the
`ui-verifier` agent to judge it — **the agent that built the UI must not be the only one deciding
it looks right**.

Avoid generic AI-dashboard output. This is an operator instrument, not a landing page.
