Reference: [section index](../0001-component-ir.md). Read with its scope; this is not a new assignment.

**F5 — Parameters.** A parameter MUST carry an identifier, a display name, a kind drawn from the
closed vocabulary in the grammar, optional bounds, and a default. The kind is required and is not
redundant with the value's type: "it is a float" does not tell a consumer whether `0.8` means 80%
or 0.8 ATR. Bounds are part of the contract rather than advice, because a published component's
parameters are edited by someone who did not write it.

**F6 — Secrets.** `secret` is a parameter kind whose value is a **reference**. A secret value
MUST NOT appear in any artefact, under any circumstances. This makes the safe path the only
representable one (P12).

**F7 — Wire types.** A wire type MUST be the product of three axes: a **value type**, a
**structure type**, and a **domain**. The structure axis MUST carry at least `scalar` and `series`,
plus `auto` for inference. The domain MUST carry an instrument and a timeframe.

The set of value types MUST be **closed, versioned, and exact-matched**. There MUST NOT be a
wildcard type, overlap matching, or coercion by string comparison. This is the strictest and least
extensible part of the IR, deliberately: ComfyUI's validator accepts comma-separated strings and
`*` as Any, matches by overlap, and carries three compatibility shims — one of which depends on
third-party code subclassing `str` to override `__ne__`. Their ecosystem froze their core. Blender
makes a similar stringly-typed choice and survives it only because socket types are added by one
closed team, which is a mitigation an open ecosystem does not get.

The *inference rules* for the structure axis are a layer above this format and are not frozen
here. The two-axis **shape** is what this clause fixes. See Appendix C(b).

**F8 — Default input sources.** An input MAY declare a default **source**, not merely a default
value. A graph whose unwired inputs all declare sources MUST be valid. This makes graph mutation a
local edit rather than a constraint-satisfaction problem, and is an explicit Generation-2 enabler
(P14).

**F9 — Graph.** A graph MUST consist of nodes and edges. A node MUST carry an instance identifier,
a component reference, and its overrides.

**F10 — Overrides.** An override MUST carry a **value only**. It MUST NOT carry a kind, bounds, or
a display name. The author's constraints are the only thing protecting a user of a component they
did not write (P11). This also matches this platform's operating reality: deployment-level
configuration overrides are deliberate value decisions, not redefinitions of what a knob means.

**F11 — Nesting by reference.** A graph MUST reference a nested subgraph by `(identifier,
version)`. A subgraph MUST NOT be inlined into a referencing graph. Inlining makes sharing,
deduplication and fork-expression impossible — Langflow inlines full source per node, with the
result that every graph is already a fork and the concept loses meaning (P2).

**F12 — Visual grouping.** Visual grouping MUST be a construct distinct from semantic reuse. A
group MUST NOT be versionable or publishable. If grouping-for-tidiness were also the reuse unit,
every cosmetic box would become a versionable artefact and the version history would fill with
noise (P9).

**Format-v1 erratum.** The grammar above incorrectly placed the visual `group` production inside
`graph-def`, while this clause and F13 require presentation state to live beside executable
content. Existing format-v1 graph bytes and content addresses are retained: `groups` is a reserved
compatibility field whose only conforming value is `[]`. Visual group records, labels, membership,
frames and collapse state belong to revisioned presentation storage and MUST NOT be written to,
published with, or hashed as executable graph JSON. The old `app.ir.edit.group()` entry point is
therefore an explicit F12 refusal, not a semantic editing primitive.

**F13 — Presentation state.** Semantic content MUST be hashed. Presentation state MUST persist
**beside** the graph, keyed by stable identifier, and is not part of the artefact grammar.
Ephemeral state MUST NOT be persisted. Without this separation, dragging a node changes its hash
and silently defeats cache identity (C8).

**F14 — Result binding.** Every experiment and every finding MUST record the exact graph version
and every resolved component version that produced it.

F14 carries the heaviest evidential weight in this document. Airflow needed `DagVersion` bound to
**task instances** — execution history, not merely definitions — and reached it only after roughly
a decade, by retrofit. Versioning's value is retrospective, so adding it late leaves every prior
run permanently unattributable. **This platform has already paid that exact price**: every
research finding recorded before 2026-08 is unusable as a baseline for this reason. The clause
exists so it is not paid twice.

> **Where F14 lives.** An experiment is not a component or a graph, so it has no artefact in the
> §3 grammar and did not get one: widening §3 would have bought a migration liability forever for
> a guarantee that does not need serialising into a *graph*. The experiment system defines the
> record, and `app/ir/experiment.py` enforces the clause against it. The binding is **derived
> from the `ResolvedGraph`** — `record()` has no parameter for the versions — because a record
> that can be told its versions can be told last week's, and stale-not-missing is the failure
> that has actually happened here. The record therefore reaches versions that appear nowhere in
> the specification's node list, such as a `smoothing.wilder` reached only through the ATR's body.

---
