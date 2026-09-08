Reference: [section index](../architecture-extension-review-2026-08-07.md). Read with its scope; this is not a new assignment.

# Architecture extension review — 2026-08-07

**Scope.** A bounded architecture and reuse audit taken at `75809a3` (L1.3C, migration head `0013`),
before L1.4 begins. It stress-tests the built architecture against twelve candidate product
directions (A–L) that the owner is exploring, and asks one question of each: *does today's code
provide a clean extension point, or would it create expensive coupling later?*

**Status.** Inspection and documentation only. **Zero production files changed.** Every claim below
is followed by the command that produced it or the file and line that shows it. Where a probe was
needed, it was run from a scratchpad, never added to the tree.

**What this review is not.** It is not a proposal to redesign anything. The candidate directions are
hypotheses, not requirements. The default answer here is *defer*, and it is the answer for most of
them.

**Headline.** The architecture is healthy for the expanded direction. The language (RFC 0001)
already carries the vocabulary for the two capabilities that looked most threatening —
cross-domain *typing* and subgraph packaging — and both were verified by execution, not by reading.
There are **no** CHANGE NOW findings and **three** at CREATE SEAM NOW (G-1, G-2, G-3). Everything
else defers.

---

## Amendments — 2026-08-07, after owner review

This review was accepted, with its central conclusion intact: **no foundational contradiction
exists, and the current IR/research/execution spine should be preserved.** Four readings were
tightened because they were carrying more weight than the evidence supports. The findings and their
urgency classifications are unchanged.

| # | What was too strong | The precise claim |
|---|---|---|
| **A-1** | That F7 makes cross-instrument work "already supported" | Instrument/domain identity **participates in the type system**, and *accidental* cross-domain wiring **fails closed**. Multi-instrument strategy *composition* is not implemented. See §C Drill 2 and the principle below |
| **A-2** | That the ten-bar drill shows "stateful nodes are supported" | **Data-derived** state is expressible in the pure kernel model. It does not follow that all stateful strategy behaviour is. See §D G-8 |
| **A-3** | That the headline's finding counts were right | Corrected above: zero CHANGE NOW, three CREATE SEAM NOW |
| **A-4** | That "no external code should be adopted" is a rule | It is a conclusion **about G-1 and G-2 only**. Project reuse policy is unchanged. See §E |

**A-1 — the cross-domain principle, recorded (no runtime change, no design).**

> Arbitrary domain mismatch remains illegal. Future cross-instrument behaviour is to be introduced
> through **explicitly typed cross-domain operations** — nodes whose declared interface is permitted
> to consume distinct domains while preserving their identities — rather than by weakening F7
> globally.

RFC 0001 A.5 already states the mechanism for the timeframe axis ("an explicit resampling component
whose declared interface changes the timeframe domain"); this generalises the same shape to the
instrument axis. Conceptually such nodes might one day cover comparison, synchronisation,
normalisation or cross-domain predicates. **None of them is designed here, and none should be
designed until a real strategy needs one.** The principle exists so the first person who needs one
does not reach for the shortcut of relaxing F7, which would silently re-admit the accidental
mismatches the axis exists to catch.

---

## A. Current architecture map

The full path, from what a user draws to what a money record says. Each arrow is a real call, with
the file that makes it.

```
   authored graph (React canvas)
        │   frontend/src/views/GraphView.tsx — server-driven; no node vocabulary in the client
        ▼
   persisted draft                       graph_artifacts.draft_json      (optimistic revision)
        │   app/editor/graph_artifacts.py · app/api/ir_edit_routes.py
        │   every edit goes through app/ir/edit.py:apply_batch, never around it
        ▼
   immutable graph version               graph_versions.artifact_json    (append-only)
        │   canonical JSON + content address; CHECK constraints pin identifier/version to the bytes
        │   presentation state lives apart: ir_graph_layouts / _positions / _groups  (F13)
        ▼
   IR resolution                         app/ir/resolve.py:resolve(spec, library)
        │   pure: no plane, no mode, no clock, no counter (C12, C7)
        │   → 18 nodes, 35 edges, warmup 302 for the reference artefact  [measured]
        ▼
   runtime strategy                      app/strategy/ir_adapter.py:IRGraphStrategy
        │   presents a ResolvedGraph behind the Strategy contract
        │   key   = ir.<identifier>          — stable across edits, so persisted rows keep resolving
        │   version = graph content address  — so an edit still changes (key, version)
        ▼
   deployment                            ir_paper_deployments            (migration 0013)
        │   app/core/paper_authority.py — staged / paper_active / paused / retired
        │   verified: content address re-derived from bytes at activation AND at every reload
        │   verified: research lineage approves this exact artefact (core/research_read.py)
        │   verified: warmup admission against instrument+interval (engine/ir_shadow.py:admit)
        ▼
   canonical execution binding           app/core/execution_binding.py
        │   ONE decision: bind(deployment_pin, assigned_key, paper_authority)
        │   precedence: paper-authority record > deployment pin > instrument row > platform default
        │   gate: strategy_for_execution() recomputes source AND mode, then checks GRANTS
        │   GRANTS (measured) = {handwritten,generated}×{paper,live} + (ir_graph, paper)
        │                       (ir_graph, live) is ABSENT — the standing owner gate
        ▼
   signal publication                    app/engine/runner.py:scan_signals → publish_signal
        │   signal and its binding written through one door; a signal with no binding cannot open
        ▼
   execution                             process_entries → execution_policy.plan_order
        │                                → broker (PaperBroker | LiveBroker)
        │                                → ExecutionVenue → KiteVenue     (broker_protocol.py)
        ▼
   fill                                  positions row: strategy_key + strategy_version + mode
        ▼
   position / trade / accounting         app/core/execution_book.py decides whose money it is
                                         book = execution mode; fails closed to `live`
                                         capital_state and equity_snapshots are book-scoped (0012)
```

Three properties of this map are worth stating because they are what make the rest of this review
short:

1. **There is one resolver, one validator, one hash, one registry, one deployment authority and one
   research ledger.** The project's standing "one of anything" rule holds today. `execution_binding.
   BINDING_MECHANISMS` even enumerates the six legacy things that claim to answer "what runs here",
   so adding a seventh is a visible edit rather than a new table appearing.
2. **Authority is checked where it is used, not where it is produced.** `strategy_for_execution`
   recomputes the source from the key and the mode from settings, and refuses anything outside
   `GRANTS`. A binding is a plain dataclass, so a field is treated as a claim. This is why granting
   a new capability execution rights is a reviewed code edit and cannot become a config row.
3. **Execution is provenance-blind (C13).** No path under `app/engine/` branches on where a
   component came from. The one place that inspects a source lives in `app/core/`, outside the
   executor perimeter.

---
