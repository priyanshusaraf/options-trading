---
name: strategy-os-architecture-review
description: Use before any major architecture, subsystem, or technology decision in Strategy OS — new abstraction, new dependency, schema or authority change, "should we rewrite X", "should we adopt Y". Produces a KEEP / KEEP+HARDEN / REFACTOR / REPLACE / DEFER verdict backed by inspected code, not opinion.
---

# Strategy OS architecture review

The default answer is **DEFER**. Novelty needs evidence; the existing spine does not need to
re-justify itself every session.

## 1. Establish what is actually true

Never reason from prose. Read, in this order, and stop when you have enough:

- `docs/engineering/reference/architecture-extension-review-2026-08-07.md` — **twelve candidate
  directions already stress-tested against real code, with executed drills.** If your question is
  in there, the work is done; cite it rather than redoing it.
- `docs/rfcs/0001-component-ir.md` for anything touching the language.
- `docs/engineering/decisions/` — an ADR settles a question. 0011 adoption gates, 0012
  execution-state ownership, 0013 admission-not-lease.
- The code itself. Use LSP navigation (go-to-definition, find-references) rather than grep
  archaeology.

## 2. Name the invariants in the blast radius

From `CLAUDE.md` "Core invariants" plus the relevant `.claude/rules/` file. State explicitly
which invariants the change touches and how each survives. An invariant you cannot name is one
you are about to break.

## 3. Inspect dependencies both ways

What does this consume, and what consumes it? A `Consumes` entry naming a file another workstream
does not `Export` is either a missing export or a private thing being reached into. Check
`docs/engineering/DEPENDENCIES.md` stays acyclic.

## 4. Reuse before building

Strategy OS itself → OpenAlgo (behaviour only, AGPL-3.0) → `~/dev/multiverse-of-ideas` (only
`reviews/` prose may cross) → other open source. Classify DIRECT REUSE / ADAPT-WRAP /
REFERENCE ONLY / REJECT with the licence you read.

## 5. Challenge it

- What breaks if we do nothing? If the honest answer is "nothing yet", the verdict is DEFER.
- Is this a *seam* need or a *feature* need? Seams are cheap now and expensive later; features
  are the reverse.
- Does it introduce a second graph schema, validator, resolver, hash, ledger, deployment model or
  execution authority? That is disqualifying — say so and stop.
- Is the complexity proportional to ~100 users, or is it infrastructure for an imagined scale?
- What is the cost of being wrong, and does that cost grow with delay?

## 6. Verdict

One of **KEEP** / **KEEP + HARDEN** / **REFACTOR** / **REPLACE** / **DEFER**, each with:
the evidence that produced it, the smallest correction if any, what must not change, and what
test would prove it. If DEFER, name the home it defers to (a workstream §5 item, an L-band, a
gap ID) so it is deferred rather than forgotten.
