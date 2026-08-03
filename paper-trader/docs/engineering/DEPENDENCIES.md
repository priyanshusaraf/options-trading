# DEPENDENCIES

The inter-workstream graph, derived from what each workstream declares in its §3. If an edge
here is not declared in both documents, one of the three is wrong.

Maintained by the executive layer. See [`EXECUTIVE.md`](EXECUTIVE.md) §9 for the checks.

---

## 1. The graph

```mermaid
graph TD
  WS01["WS-01<br/>Component IR"]
  WS02["WS-02<br/>Execution & Brokers"]
  WS03["WS-03<br/>Research Plane"]
  WS04["WS-04<br/>Editor"]
  WS05["WS-05<br/>Marketplace"]
  WS06["WS-06<br/>Deployment & Ops"]
  WS07["WS-07<br/>Infrastructure"]
  WS08["WS-08<br/>Cockpit UI"]

  WS01 --> WS03
  WS01 --> WS04
  WS01 --> WS05
  WS01 -.pending owner.-> WS02
  WS02 --> WS03
  WS02 --> WS08
  WS07 --> WS02
  WS07 --> WS03
  WS07 --> WS08
  WS02 --> WS06
  WS07 --> WS06
  WS08 --> WS06
  WS08 --> WS04
  WS02 --> WS01
  WS07 --> WS04
  WS07 -.when it starts.-> WS05
  WS03 -.when it starts.-> WS05

  classDef blocked stroke-dasharray: 5 5
```

An arrow means *the target consumes from the source* — see
[`EXECUTIVE.md`](EXECUTIVE.md) §7 for why that is the definition. Dashed edges are declared but
not yet live.

**Acyclic today**, and one edge away from not being. WS-01 consumes from WS-02 (its reference
artefact composes the seven pure functions extracted out of `expanding_z_v4`), while the pending
adoption edge points WS-01 → WS-02. Both at once is a cycle. Decide which direction survives
before adoption starts.

## 2. Edges, and what actually crosses them

| From | To | What crosses |
|---|---|---|
| WS-01 | WS-03 | `resolve`, `evaluate`, `edit`, `authoring`, `experiment`, `kernels` — the whole language |
| WS-01 | WS-04 | `graph_view`, `to_svg`, `Layout`, the edit functions |
| WS-01 | WS-05 | the component/kernel registry shape; C13 |
| WS-01 | WS-02 | **not yet** — RFC Appendix C(d), owner-blocked |
| WS-02 | WS-03 | strategy registry contract, `candles.py`, charges, the backtester |
| WS-02 | WS-08 | the REST + WS API, the money record |
| WS-07 | WS-02, WS-03, WS-08 | DB, sessions, `Settings`/`runtime_config`, the WS hub, test isolation |
| WS-02, WS-07, WS-08 | WS-06 | what gets deployed, and what `/api/health` reports |
| WS-08 | WS-04 | the app shell, `lib/api.ts` and shadcn primitives used by the live read-only viewer |
| WS-02 | WS-01 | the seven pure `expanding_z_v4` steps the reference artefact's kernels compose. Live today, and the edge that makes adoption a cycle risk |
| WS-07 | WS-04 | current — FastAPI plus the SQLite/Alembic `0005` sparse layout store |
| WS-07 | WS-05 | future — persistence for a package store |
| WS-03 | WS-05 | future — the AST allow-list as prior art, *not* an import (WS-05 §3) |

## 3. Roots and sinks

**Roots** (depend on nothing internal): WS-07 only. WS-01 was a root until its reference
artefact began composing WS-02's extracted functions; that is the edge above.
Changing an export in either is the most expensive kind of change here — check both before
touching them.

**Sink**: WS-06. Nothing depends on Deployment, which is why deployment being owner-blocked
stops shipping without stopping development.

## 4. Blocking, right now

| Blocked | By | On what |
|---|---|---|
| WS-06 | **owner** | Deploying the eight-phase architecture migration (WS-02). Committed, verified, off the box for several sessions |
| WS-02 | **owner** | Adopting the IR runtime in a live path (RFC Appendix C(d)). Parity evidence exists |
| WS-06 | **owner** | VPS OS reboot (5 ESM security updates); droplet resize 1 GB → 2 GB |
| WS-05 | trigger | Third-party component distribution. Deliberately not started |

Nothing is blocked on another workstream's unfinished code. Every current blocker is an owner
decision or an unmet trigger — which means every workstream except WS-05 can progress today.

## 5. Changing an interface

1. Update the exporting workstream's §3 Exports.
2. Update every consumer's §3 Consumes.
3. Update this file if the edge itself changed.
4. All of it in one commit. A half-updated interface is worse than the old one, because the
   documents stop being trustworthy and then stop being read.
