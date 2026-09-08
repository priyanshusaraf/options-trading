Reference: [section index](../0001-component-ir.md). Read with its scope; this is not a new assignment.

# RFC 0001 — The Component IR

**Status:** Accepted — Gates 1, 2 and 3 met
**Version:** 1.0 · **Date:** 2026-08-02
**Supersedes:** nothing · **Amended by:** nothing (one erratum — see §6.3)

> **Gate 3 — acceptance.** Recorded 2026-08-02 on the owner's standing directive that "the
> architectural phase is complete… the RFCs, roadmap, implementation plans and accepted design
> documents define the architecture… do not redesign accepted architecture unless
> implementation produces contradictory evidence that cannot be resolved within the existing
> design." That is acceptance in substance: the document is treated as constitutional and
> implementation, not redesign, is the default activity. Written down here rather than assumed,
> so that if the owner meant something narrower there is one line to correct.

> **§3 and §4 are both enforced.** As of 2026-08-02 the conformance suite is
> `backend/app/ir/` plus
> `backend/tests/test_ir_{conformance,corpus,contract_c13,resolution,runtime}.py`.
> It mechanically validates artefacts against **F1–F13**, executes all five Appendix A
> artefacts as real data rather than sketches, and enforces **all fifteen contract clauses**
> against a real resolver (`app/ir/resolve.py`). Suppressing any single clause turns that suite
> red — swept F1–F13 in the format phase and C1–C15 in the resolver phase — so the checks are
> known to be load-bearing rather than merely present.
>
> **F14 is enforced as of 2026-08-02**, and the note that used to sit here saying it was not is
> gone. It binds experiments and findings to the versions that produced them, and an experiment
> is not a component or a graph — so the answer was never to widen §3. The experiment system
> defines the record (`app/ir/experiment.py`), and the binding is **derived from the resolved
> graph rather than supplied**, because F14's real failure mode is a stale field, not a missing
> one. `format_version` does not move.
>
> One gap remains, recorded rather than glossed and asserted by a test so it cannot be mistaken
> for coverage: **F7's edge type-matching needs a component library** — given one, exact matching
> on all three axes is checked; given none, F7 is reported *unchecked* rather than passing
> silently.
>
> A **component runtime** now consumes the resolved graph (`app/ir/runtime.py`), which is what
> turns C8, C9, C10 and C11 from declarations into measurements — in particular C11, where
> lookahead is caught by evaluating a prefix of the bars and demanding the shared bars match,
> rather than by trusting a component's author.
>
> **Nothing in production executes IR graphs.** `app/ir/` is imported only by its own tests. C12
> is enforced as the *absence* of a second resolver, which is what makes parity structural; the
> question of when the live engine runs IR graphs is Appendix C(d) and stays open.

---

## Preface (informative)

### Why the Component IR exists

Nine systems were read in full before a line of this document was written — ComfyUI, vectorbt,
NautilusTrader, Node-RED, Blender, Langflow, xyflow, Airflow, Prefect — across four domains and
three decades of combined history, plus an earlier teardown of OpenAlgo. The evidence and the
per-system reviews live in `~/dev/multiverse-of-ideas/reviews/`; the distilled conclusions are in
`_FINDINGS-component-ir.md` and `_PATTERNS.md`. This document cites them and does not reproduce
them.

The finding all nine converge on is an absence. **Not one of them has both a durable component
and a real composition model.** Some compose but cannot say durably what they composed; some have
reusable units but no graph. The table in `_FINDINGS-component-ir.md` §1 is the evidence. That
gap is what this language exists to close.

### Why we are introducing a language

The platform is being rebuilt around Components → Graphs → Experiments → Deployments. Today it is
built around strategies, and the cost of that is visible in the code: four sources of strategy —
built-in, generated, visual, Python, marketplace — each reduce to the same four boolean columns
and then run one hard-coded risk model. That is four skins on one strategy, not four strategies.

A language is what lets a strategy say what it is: its parameters, its structure, its
composition, its version. Without one, every subsystem invents its own private answer.

### Why every subsystem speaks it

The runtime, the research plane, the editor and the marketplace are **interfaces over one
language**, not four abstractions that happen to cooperate. Each either produces the IR, consumes
it, or is deterministically derived from it. Where two subsystems need to agree about a strategy,
they agree in this language or they do not agree at all.

### Why this document distinguishes Format clauses from Contract clauses

Blender carries **44,246 lines** of version-migration code across releases 2.50→5.30 — rewrite
passes that carry old files forward, forever, one per concept the format ever admitted. That is
the true price of a language, and it is the reason §3 of this document is kept small.

But that price is paid **only for what is serialised**. A guarantee costs nothing to migrate:
"the executor never branches on a component's provenance" adds no bytes to a stored graph and
will never need a rewrite pass. So this constitution has two kinds of normative clause and marks
them apart:

- **§3 Format clauses** — what is written down and read back. Each is a permanent migration
  liability. Minimised ruthlessly.
- **§4 Contract clauses** — guarantees any conforming implementation must satisfy. Free.
  Completed thoroughly.

The practical rule this yields, and the reason the split is structural rather than stylistic:
*additions to §3 cost migrations forever; additions to §4 cost nothing.* A designer under time
pressure can apply that rule without re-deriving the argument.

---
