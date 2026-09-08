Reference: [section index](../0012-execution-state-ownership.md). Read with its scope; this is not a new assignment.

### 2.4 The registry of mechanisms

`BINDING_MECHANISMS` names all six, as `table.column`, with a test asserting each still
exists. Adding a seventh is a deliberate edit with a test to justify it. This is the "no
second deployment model" rule enforced rather than asserted — and it fails loudly if a
column is renamed, so it cannot pass forever while describing a schema nobody has.

## 3. The smallest safe paper/shadow deployment architecture

Recorded now, gated at each step. **§3.1 is built (L1.3A, 2026-08-07). §3.2 onward is not,
and is the owner's decision.**

1. **A deployment may name a graph version, and still not execute it.** — **BUILT (L1.3A).**
   Implemented as `ir_shadow_deployments` (migration `0011`) plus
   `app/core/shadow_deployments.py`, rather than by overloading `deployments.strategy_key`
   as this ADR originally sketched. The reason for the change is §3.1a below.
### 3.1a Why L1.3A did not overload `deployments.strategy_key`

The original sketch was "set the deployment's key to `ir.<identifier>` and let the gate
refuse it". Building it exposed why that is wrong, and the correction is worth recording:

- **A `Deployment` row cannot hold the lineage.** Project, graph identifier, graph version,
  content address, evidence run, candidate, admission verdict and shadow lifecycle are
  eight facts with nowhere to live. Encoding them in the key is §2.1's forbidden move —
  one layer asserting another's fact — and it is how the whole defect class starts.
- **The two lifecycles are different.** A deployment is draft/active/paused/archived and
  *armed*. A shadow binding is staged/shadow-active/paused/retired and has no arm state,
  because there is nothing to arm. Sharing a state column would have made "armed" mean two
  things.
- **The refusal would have been a runtime one.** With a separate table the mode and
  authority columns are CHECK-constrained, so the database refuses to widen them at all.

This is **not** a second deployment model. `ir_shadow_deployments` has a foreign key to
`deployments` and describes an *observer attached to a book*, not a book. It creates no
orders, holds no capital, has no arm state, and appears in `BINDING_MECHANISMS` as
observation rather than as an answer to "what executes here" — the engine's authoritative
selection does not consult it.

### 3.1b What L1.3A verifies, and when

| checked | at stage | at activate | at every reload |
|---|---|---|---|
| graph version exists | yes | yes | yes |
| content address re-derived from the stored bytes | yes | yes | yes |
| instrument and interval are real | yes | — | — |
| research decision approves *this* project/graph/version | — | yes | no — recorded |
| warmup/history admission | — | yes | — |
| source/mode/authority is the one reviewed triple | — | yes | yes |

Evidence is verified once and **recorded**, not re-read on reload: the approval lineage
lives in the research plane's own database (hard invariant 5), and a control-loop boundary
is the wrong place for a cross-plane read. The graph address *is* re-derived on every
reload, because it is local, cheap, and the thing that can move underneath a live binding.

A binding that fails reload verification is **dropped and reported**
(`runner.shadow_deployment_problems`), never repaired. Silently rebinding to whatever bytes
are present now is the silent-substitution failure this project has closed in the registry,
in selection and in attribution; it does not get to reappear in observation.

2. **Paper authority is a source-and-mode pair, never a source alone.** — **NOT BUILT.
   Owner-gated.** L1.3A deliberately stops here. `shadow_deployments` has no mode
   parameter, no authority parameter, and the columns are CHECK-constrained, so granting
   paper authority requires a reviewed change in three independent places: the schema, the
   service, and `AUTHORITY_BY_SOURCE`. The smallest safe
   grant is not "`ir_graph` is authoritative" but "`ir_graph` is authoritative **when
   `PT_EXECUTION=paper`**" — i.e. the gate consults execution mode, and fails closed when it
   cannot determine it. `SafePaperKite` and `PaperBroker` already provide the containment;
   the gate provides the selection, and it must fail closed rather than open.
3. **One deployment, one instrument, one graph version.** Rollback is reassigning the
   deployment's key — no deploy, no restart, matching the existing per-instrument path.
4. **Every transition is version-bound.** A graph edit mints a new version, so it cannot
   inherit the previous version's authority. That falls out of `(key, version)` identity and
   requires no new mechanism.
5. **Observability before authority.** A deployment running a graph in paper must publish
   the same evidence the shadow lane does — agreement, classifications, cost — under the
   same contract, or the promotion has no basis.

**Not in this design, deliberately:** a second ledger, a second broker, a second candidate
lifecycle, a parallel "IR engine", or any code path that duplicates order lifecycle,
accounting, reconciliation, exits, kill controls or rollback. Every one of those already
exists once and stays that way. The engine remains authoritative until a later,
explicitly-approved authority transition.
