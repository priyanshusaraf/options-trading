# WS-05 — Marketplace (component distribution)

**Status:** not started
**Owner surface:** none yet. When it starts it will own a package format, a transport, and a
trust/sandboxing policy for the **kernel registry** — not for the graph language.
**Last verified:** 2026-08-03 · commit `cdbe686`

> This workstream is how a component authored somewhere else gets into this platform's registry
> and runs. RFC 0001 §1.2 makes distribution one of the five planes, and gives it exactly one
> verb: it **transports**. It does not extend the language, it does not add a node kind, and it
> does not get its own execution path. Nothing here is built. This document exists so that when
> the trigger fires, nobody re-derives the boundary from scratch — and so that nobody
> accidentally builds half of it under a different name.

---

## 1. Vision

A component authored by someone who is not the owner of this box arrives as a package, is
verified, lands in the same registry a built-in component lands in, and from that moment is
indistinguishable to every executor path. A graph referencing it resolves identically. Its
cache identity, purity and warmup come from the same kernel registry fields as everything else.
Where it came from is display metadata on a card in the editor, and nothing more.

The reason to want this: the IR's value compounds with the size of the component library, and a
single-owner library grows at one person's rate. The reason to be careful about it: the moment
components arrive from outside, executing one is executing someone else's code, and the platform
trades real money on a box with a live broker session.

"Done" is therefore two things at once, and both are required or neither ships. First, a
distribution mechanism. Second, a sandboxing policy that constrains what a **kernel** may do —
its filesystem, its network, its builtins, its imports — enforced at the registry, so the graph
language never learns the word "untrusted". If the second is absent, this workstream must not
start; a transport without a sandbox is the fastest available way to lose the account.

## 2. Scope

**In scope.**

- **A package format** for a component or a set of components: the component-def artefact(s), the
  kernel source, the declared `KernelSpec` fields, an integrity digest, and enough metadata to
  render a card. Content-addressed, because F2 already gives every body a content address.
- **A transport**: how a package moves from wherever it lives to this box, and how it is verified
  on arrival.
- **A sandboxing policy for the kernel registry.** RFC §5(3) excludes this from the *language*
  deliberately, on the grounds that sandboxing constrains what a component **kernel** may do,
  which is a property of the kernel registry rather than of the graph language. That exclusion
  puts the work here, not that it does not exist. Appendix C(f) names the trigger explicitly:
  **third-party component distribution**.
- **A trust model**: what "verified" means, who signs, what happens to a package that fails
  verification, and whether an unverified package can be installed at all.
- **Provenance as display metadata**, and only that — the card in the editor, the origin URL, the
  publisher. C13 makes the "only that" normative.

**Out of scope.**

- **The IR language, its grammar, resolver and validator** — WS-01 Component IR. C15 already
  makes a subgraph and a component the same kind of thing, and says so as a *language* clause
  precisely because distribution is a separate plane. No marketplace need may add a clause to
  §3 or §4.
- **The executor.** WS-02 Execution. A marketplace component must run down the identical path a
  built-in does; if this workstream ever needs an executor change to accommodate a foreign
  component, that is the signal that the design is wrong, not that the executor needs a flag.
- **Local Python component authoring** — WS-01 (`app/ir/authoring.py`). See §7: it deliberately
  does not sandbox, and the reason is not laziness.
- **The research plane's code-gen builder and its AST allow-list** — WS-03 Research
  (`backend/research/strategy/builder/`). The allow-list is prior art this workstream should
  copy; it is not this workstream's code to change.
- **The visual editor's component picker** — WS-04 Editor. Browsing a catalogue is a UI concern
  (RFC §5(4)); what is *in* the catalogue is this workstream's.
- **Network egress rules, firewalling, the VPS** — WS-07 Infrastructure. A sandbox that relies on
  process-level isolation will need WS-07 to enforce it; the policy is here, the enforcement
  primitives may not be.
- **Deploying a component to production** — WS-06 Deployment. Installing a component into a
  registry and promoting one into the live engine are different acts and must stay different.

## 3. Interfaces

**Exports** — nothing yet.

| Export | Guarantee |
|---|---|
| — | nothing yet. When this workstream ships, its export is a **registry population step**, not a runtime hook. Nothing downstream should ever import a marketplace module. |

**Consumes**

| Consumed | From | Why |
|---|---|---|
| `KernelSpec`, `kernel_spec()`, `kernel_registry()` (`app/ir/kernels.py`) | WS-01 | The registry seam a package must populate. `KernelSpec` carries `warmup` (int or a function of bound params), `purity`, `cache_identity`, `cache_key` — and the field set is **closed on purpose**: an open one is C9's forbidden escape hatch waiting to happen. A marketplace package may not introduce a field. |
| `IMPURITY_POLICIES` = `("account_state", "broker_state", "wall_clock")` (`app/ir/kernels.py`) | WS-01 | The closed vocabulary a foreign kernel must declare itself against. A kernel that needs a fourth impurity is a language change (WS-01), not a package. |
| `validate(graph)` and the `Violation` type (`app/ir/validate.py`) | WS-01 | An arriving artefact is validated by the same validator a locally authored one is. No second validator. |
| `content_address()` (`app/ir/hashing.py`) | WS-01 | Integrity of a package body is the content address that F2 already assigns it. Do not invent a second digest scheme. |
| `resolve()` / `Library` (`app/ir/resolve.py`) | WS-01 | A marketplace component is a `Library` entry. That is the entire integration point, by design. |
| The AST allow-list + no-builtins exec pattern (`backend/research/strategy/builder/validate.py`, `load.py`) | WS-03 | Prior art to copy, not to import. `compile_composition` emits source, validates against an allow-list, then `exec`s it in a namespace containing only the vetted block callables and an **empty** `__builtins__` — so generated code cannot import, open files, call `eval`, or reach any name outside the grammar even if validation missed something. RFC Appendix C(f): this is stronger than anything in the nine systems studied, none of which sandbox user code at all. |

**Depends on:** WS-01 (registry seam, validator, hashing, resolver), WS-03 (the sandboxing
prior art), WS-07 (any OS-level isolation primitive the policy ends up needing).

**Blocked by:** **nothing is blocking work — the trigger has not fired.** RFC Appendix C(f)
names it: third-party component distribution. There is no third party, and there are no
components to distribute. Starting before the trigger is speculative work of exactly the kind
RFC §5(2) declines elsewhere.

**Currently blocking:** nothing. No workstream is waiting on distribution.

## 4. Completed

**Nothing yet.** No package format, no transport, no trust model, no sandboxing policy for the
kernel registry. There is no marketplace module, no marketplace test, and no marketplace concept
anywhere in `backend/app/`.

Two things that already exist and must not be mistaken for a start on this workstream:

- **`backend/research/strategy/builder/`** (WS-03) sandboxes *generated* code — AST allow-list,
  empty `__builtins__`, block-callables-only namespace. Same technique, different threat: the
  code being constrained there was produced by this platform's own generator, not received from
  a stranger.
- **`app/ir/kernels.py`** (WS-01) already gives kernels a closed declaration surface. That is a
  precondition for a sandbox, not a sandbox.

The load-bearing verified fact, 2026-08-03 at `cdbe686`: **`tests/test_ir_contract_c13.py`
exists and passes**, and the RFC records that C13 is enforced by a test in the conformance phase
rather than by review, precisely because this codebase has a documented history of mechanisms
that exist and are wired to nothing. That test is the wall this workstream will be built against.

## 5. Active roadmap

Nothing is scheduled. When the trigger fires, this is the order — and the first item is not the
transport.

- [ ] **Write the sandboxing policy before writing any transport.** What may a foreign kernel
      do: which builtins, which imports, which filesystem paths, which network. Enforced at the
      **kernel registry**, because RFC §5(3) locates sandboxing there and not in the graph
      language. Start from `research/strategy/builder/validate.py` + `load.py`: AST allow-list,
      then compile-and-exec in a namespace with only vetted callables and an empty
      `__builtins__`. Prove the policy can go red — a package that tries to `import os` must be
      refused by a test that fails if the guard is removed.
- [ ] **Package format.** Component-def artefact(s) + kernel source + `KernelSpec` fields +
      content-address digest + display metadata. Validated on arrival by `app/ir/validate.py` —
      the same validator, no second implementation.
- [ ] **The C13 conformance test extended to a foreign component.** Install a package, resolve a
      graph that references it, and assert that no executor path observed its origin. The
      existing `tests/test_ir_contract_c13.py` is the model; the addition is that the component
      under test arrived from outside. **This test is the acceptance gate for the whole
      workstream**: if a foreign component needs any branch anywhere, the design failed.
- [ ] **Transport and verification.** Last, deliberately. It is the easiest part and the one most
      likely to be built first for the wrong reasons.

## 6. Acceptance criteria

No marketplace change is done without all of:

```bash
# from backend/
.venv/bin/python -m pytest -q tests/test_ir_contract_c13.py
.venv/bin/python -m pytest -q tests research_tests     # BOTH suites
.venv/bin/python scripts/dryrun.py 700                 # ledger stays paisa-exact
```

Plus, specific to this workstream and non-negotiable:

- **C13: no executor path may branch on where a component came from.** A marketplace component
  lands in the same registry a built-in does. Enforced by test, not by review. A grep for a
  provenance field reaching anything under `app/engine/` or `app/ir/runtime.py` is a failure
  regardless of what the tests say.
- Every sandbox guard added must be demonstrated able to fail — write the escaping package,
  watch the test go red, then fix it. An empty result looks identical to a passing one.
- No clause is added to RFC 0001 §3 or §4 to accommodate distribution. If one seems necessary,
  RFC §1.2 says the clause is misfiled and the presence of one is a defect in the document.

## 7. Known technical debt

- **`app/ir/authoring.py` deliberately does NOT sandbox**, and its module docstring says so:
  *"This does not sandbox — that belongs to the kernel registry."* This is correct and must not
  be "fixed". A locally authored component is a Python function the owner wrote, in a repo the
  owner controls, executed by a process the owner started — sandboxing it would constrain the
  owner against themselves while adding a mechanism with no threat to defend against. The debt
  is only that the *asymmetry* is currently implicit: there is no code path that distinguishes a
  locally authored component from a foreign one because there are no foreign ones. Cost of
  leaving it: zero today. Trigger: the first package that arrives from off this box — at which
  point the sandbox goes in the **registry**, not into `authoring.py`.
- **The AST allow-list lives in `research/`, behind the research plane's fail-closed import
  guards** (`PT_RESEARCH_ENABLED=0`). The strongest sandboxing code in the repo is therefore in
  the dormant half of it. Cost: none while dormant. Trigger: needing the same technique in
  `app/`; resist copy-paste — two hand-written implementations of one idea is the exact shape
  that produced the `candles.py` defect.

## 8. Blockers

- **The trigger has not fired.** RFC Appendix C(f): third-party component distribution. There is
  no third party. This is not "blocked" in the sense of stuck — it is correctly unscheduled.
- **An owner decision precedes any work here**: whether this platform should ever execute code
  it did not author, on a box holding a live broker session and real money. That is a risk
  decision, not an engineering one, and the answer may legitimately be no forever — in which
  case this document's value is the boundary it records, not the software it describes.
- **RFC 0001 has not passed its acceptance gate**, so C13 and C15 — the two clauses this
  workstream is built entirely around — are proposed rather than ratified.

## 9. Future work

- **A private registry rather than a public marketplace** — the same package format and the same
  sandbox, but the only publisher is the owner, across multiple boxes. Trigger: a second machine
  that should run the same component library.
- **Signing and publisher identity.** Trigger: more than one publisher.
- **Reputation, ratings, discovery, payment.** Named here only so nobody mistakes their absence
  for an oversight. Trigger: an actual user base, which does not exist — this is a single-user
  platform.
- **Sandboxing the research plane's generated code by the same registry policy**, collapsing the
  two implementations into one. Trigger: the registry sandbox shipping.
