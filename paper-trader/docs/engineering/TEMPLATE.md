# WS-NN — <Name>

**Status:** active | paused | not started | complete
**Owner surface:** `<the paths this workstream owns>`
**Last verified:** YYYY-MM-DD · commit `<sha>`

> One paragraph. What this workstream is for, in terms a reader who knows nothing
> about the repository can follow.

---

## 1. Vision

What "done" looks like. Not a task list — the end state, and why it is worth reaching.

## 2. Scope

**In scope.** The things this workstream decides and builds.

**Out of scope.** The things a reader might reasonably expect here and will not find,
with a pointer to the workstream that owns them. This section prevents duplicated work
more than any other.

## 3. Interfaces

**Exports** — what other workstreams may depend on. Each entry: the symbol or file, and
the guarantee it carries. If it is not listed here, it is internal and may change.

| Export | Guarantee |
|---|---|

**Consumes** — what this workstream depends on, and from where.

| Consumed | From | Why |
|---|---|---|

**Depends on:** WS-NN, WS-NN
**Blocked by:** — (name the workstream *and* the specific item, or "nothing")
**Currently blocking:** — (which workstreams are waiting on this one, and for what)

## 4. Completed

Verified and committed work, newest first. Each line: what, when, the commit, and the
evidence that made it tickable. Keep the rationale that would be expensive to re-derive;
delete narration.

## 5. Active roadmap

- [ ] The next item, with enough detail to start without reading anything else.
- [ ] …

Ordered. The topmost unchecked item is what an implementation agent picks up.

## 6. Acceptance criteria

What must be true for a change in this workstream to be considered done. The commands,
not the intent.

## 7. Known technical debt

Things that work and are wrong. Each with the cost of leaving it and the trigger that
would force it.

## 8. Blockers

Anything that stops progress and cannot be resolved inside this workstream — owner
decisions, external information, another workstream's unfinished work.

## 9. Future work

Named, deliberately not scheduled. Each with the trigger that would schedule it.

---

## Rules for this document

- It is the **only** thing an implementation agent should need to read for this
  workstream, besides the constitutional documents and its declared dependencies.
- Anything in §3 is a contract. Changing an export requires updating every workstream
  that lists it under Consumes, in the same commit.
- Do not restate another workstream's content. Link to it.
- Tick a box only with verified evidence, in the same commit as the work.
