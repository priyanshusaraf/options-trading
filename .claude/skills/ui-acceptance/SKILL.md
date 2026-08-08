---
name: ui-acceptance
description: Required before declaring any meaningful Strategy OS frontend change done. Vitest, tsc and build passing are necessary and insufficient — this skill demands the app actually run and the operator flow actually work in a browser.
---

# UI acceptance

Green tests cannot see a blank page, a mis-wired value, an overflowing table, or a console error.

## 1. Understand the operator workflow

Who is looking at this screen, and what are they trying to answer? The cockpit exists to answer
**is it working right now**, **what is it holding**, **what is it about to do**. If the change
does not serve one of those, question it before building it.

## 2. Design intent before code

Dense, monospace, chip-and-table, dark. Information per square inch. Every number is true or
visibly **Unknown** — never a stale value wearing a green badge. Works one-handed at **390px**.
Use the `frontend-design` plugin skill for craft; avoid generic AI-dashboard output.

## 3. Implement

Constraints in `.claude/rules/frontend-ui.md`: one WebSocket, all REST through `lib/api.ts`, no
second opinion on backend truth.

## 4. Static gates (necessary, not sufficient)

```bash
npm test && npm run typecheck && npm run build     # from frontend/
```

## 5. Run the real application

`.claude/skills/run-strategy-os`. It starts a **mock-provider, paper-mode, temp-database**
instance — never the live ledger and never a real broker session.

## 6. Drive the actual flow in a browser

Use the `claude-in-chrome` tools. Perform the intended user journey end to end — not just load the
route. Then inspect:

- **layout and interaction** at desktop **and** 390×844; no page-level horizontal overflow
  (wide content scrolls inside its own container);
- **console** — `read_console_messages`, filtered; zero errors;
- **network** — `read_network_requests`; no failed or unexpected calls, no polling storm;
- **loading, error and empty states** — force each one, do not assume it renders;
- **screenshot** the result and actually look at it.

## 7. Independent verification

Dispatch **`ui-verifier`**. The agent that built the UI must not be the only one deciding it looks
right.

## 8. Fix what you saw, then re-verify

Re-run the flow after fixing. A fix you did not re-observe is unverified.
