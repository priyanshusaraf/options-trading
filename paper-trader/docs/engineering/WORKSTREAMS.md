# WORKSTREAMS

Eight engineering streams. Each is independently maintainable; together they are one system.

**If you are here to implement something, read exactly three things:** `../ARCHITECTURE.md`,
your workstream's document, and the documents of anything it lists under *Depends on*. Not the
roadmap, not the other seven.

---

## The streams

| # | Workstream | Status | Owns | Document |
|---|---|---|---|---|
| WS-01 | **Component IR** | active | `backend/app/ir/` | [WS-01](workstreams/WS-01-component-ir.md) |
| WS-02 | **Execution & Brokers** | active · live money | `backend/app/engine/`, `providers/`, `options/`, `strategy/`, `backtest/` | [WS-02](workstreams/WS-02-execution.md) |
| WS-03 | **Research Plane** | active | `backend/research/` | [WS-03](workstreams/WS-03-research-plane.md) |
| WS-04 | **Editor** | active | read-only IR graph API/viewer; layout and editing next | [WS-04](workstreams/WS-04-editor.md) |
| WS-05 | **Marketplace** | not started | — | [WS-05](workstreams/WS-05-marketplace.md) |
| WS-06 | **Deployment & Operations** | active · owner-blocked | `scripts/deploy.sh`, the VPS, `/api/health` | [WS-06](workstreams/WS-06-deployment.md) |
| WS-07 | **Infrastructure & Persistence** | active | `backend/app/db/`, `core/`, `ws/`, test harness | [WS-07](workstreams/WS-07-infrastructure.md) |
| WS-08 | **Cockpit UI** | active | `frontend/` | [WS-08](workstreams/WS-08-cockpit-ui.md) |

## Coordination

| Document | Purpose |
|---|---|
| [`EXECUTIVE.md`](EXECUTIVE.md) | the coordination layer — invariants, sequencing, interface changes, drift |
| [`DEPENDENCIES.md`](DEPENDENCIES.md) | the dependency graph and what crosses each edge |
| [`EXECUTION_PLAN.md`](EXECUTION_PLAN.md) | sequential full-product slices, gates and checkpoints |
| [`TEMPLATE.md`](TEMPLATE.md) | the required shape of a workstream document |
| [`reference/`](reference/) | long-form reference that no single workstream owns |

## How a workstream document is meant to be used

Every one has the same nine sections, so you can find what you need without reading the whole
thing:

- **§2 Scope** — the fastest way to discover you are in the wrong document.
- **§3 Interfaces** — what you may depend on, and what depends on you. This is a contract:
  changing an export means updating every consumer in the same commit.
- **§5 Active roadmap** — the topmost unchecked item is what to pick up.
- **§6 Acceptance criteria** — the commands that decide whether you are done.

## Adding a workstream

Rare, and an executive decision. A new stream is justified when a body of work has its own
vision, its own acceptance criteria, and an interface other streams consume — not when it is
merely large. Copy `TEMPLATE.md`, add a row above, add the edges to `DEPENDENCIES.md`, and
state in every neighbour's §2 what has moved out of it.
