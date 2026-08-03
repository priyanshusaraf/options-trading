# EXECUTIVE

**The coordination layer. It does not implement.**

Eight workstreams now develop independently. Something has to keep them one system, and that
is this document's job — not by reviewing every change, but by owning the small number of
decisions that no single workstream can make correctly on its own.

The failure this layer exists to prevent is not a bug. It is two workstreams solving the same
problem differently, discovering it a year later, and neither being able to change.

---

## 1. Responsibilities

**Architectural consistency.** `../ARCHITECTURE.md` §3 lists eight cross-cutting invariants.
A workstream may not weaken one to make its own item easier. When implementation produces
evidence that an invariant is wrong, that is an RFC amendment (RFC 0001 §6), not a local
exception.

**Sequencing.** Deciding what is worked next *across* workstreams, when several are unblocked.
The rule: prefer the item that unblocks the most other workstreams, then the item whose cost
of being wrong grows fastest with delay. F14 binding was sequenced ahead of a search objective
for exactly the second reason.

**Duplicated work.** Two workstreams reaching for the same abstraction is normal and worth
catching early. The signal is a `Consumes` entry that names a file another workstream does not
list under `Exports` — that is either a missing export or a private thing being reached into.

**Shared abstractions.** Promoting something from one workstream's internals to a declared
export. This is an executive decision because the exporting workstream now owes a guarantee it
did not previously carry.

**Dependency ordering.** Maintaining `DEPENDENCIES.md` so the graph stays acyclic and every
edge is declared rather than inferred.

**Information transfer.** A finding in one workstream that changes another's plan does not
travel by itself. Recent examples, both real: the research proposer found that F8's converse
was unenforced (WS-03 → WS-01); building the block components found that a shared kernel
factory collapses body addresses (WS-03 → WS-01).

**Master documentation.** `PROGRESS.md`, `ROADMAP.md`, `CONTINUE.md`, `ARCHITECTURE.md` are
executive-owned. Workstream documents are not.

**Drift prevention.** Catching the capability that quietly extends the architecture without an
amendment. RFC 0001 §6.2 exists to make that distinguishable from ordinary work.

## 2. What this layer must not become

Another implementation workstream. It writes coordination documents and RFC amendments. If it
starts owning code, the coordination stops happening and nobody notices for months.

It also does not review every change. Workstreams carry their own acceptance criteria; the
executive layer intervenes at interfaces, sequencing and invariants.

## 3. Working rules

**One coherent history.** Every commit belongs to exactly one workstream and says which.
Cross-workstream changes are split, or the interface change lands first with its consumers
updated in the same commit.

**Interfaces are contracts.** Changing an export means updating every workstream that lists it
under `Consumes`, in the same commit. Adding an export is cheap; removing one is a
coordination event.

**A workstream document is self-sufficient.** An implementation agent should need only:
the constitutional documents (`ARCHITECTURE.md`, RFC 0001), its own workstream document, and
the documents of workstreams it declares under `Depends on`. If it needs more, the workstream
document is incomplete — that is a defect to fix, not a reason to read the whole repository.

**The live-money rule is not delegable.** No workstream's acceptance criteria can discharge it.

## 4. Sequencing, as it stands

The dependency graph in `DEPENDENCIES.md` produces this order. It is a consequence of the
declared edges, not a preference:

1. **WS-01 Component IR** — foundation. Complete as a language; every RFC clause enforced.
   Only WS-01 can unblock WS-04 and WS-05, and it already has.
2. **WS-03 Research Plane** — the largest consumer of WS-01, and unblocked. Currently the
   highest-value active stream.
3. **WS-07 Infrastructure** — substrate; work here is triggered by the others' needs.
4. **WS-02 Execution** — blocked on the owner for deployment, not for development.
5. **WS-04 Editor** — unblocked by WS-01 but not started; the first thing that would make the
   IR part of the running application.
6. **WS-08 Cockpit UI** — active, independent, small.
7. **WS-06 Deployment** — reactive; owner-blocked items only.
8. **WS-05 Marketplace** — deliberately last. Its trigger is third-party distribution.

## 5. Standing decisions

Recorded so they are not re-litigated per session.

| Decision | Rationale |
|---|---|
| §3 of RFC 0001 is minimised; §4 is completed thoroughly | Format clauses are a permanent migration liability; contract clauses are free |
| Nothing in production imports `app/ir/` yet | Adoption is RFC Appendix C(d) — a real-money change needing its own parity phase and owner sign-off |
| `runtime_config` overrides are owner decisions, not drift | Ten differ from code defaults deliberately; when docs and box disagree, fix the doc |
| Research is autonomous; capital is not | `research/guards.py` fail-closed, distinct DB, read-only bridges, `research/` imports `app.ir` and never the reverse |
| Sandboxing belongs to the kernel registry, not the language | RFC Appendix C(f); trigger is third-party distribution |

## 6. Ownership decisions

Three files were claimed by two workstreams each when the documents were first written. No two
workstreams may own the same file — otherwise a change lands in one document's history and not
the other's, and the second workstream's agent will not know it happened.

| File | Owner | Why, and who consumes it |
|---|---|---|
| `app/market_data/candles.py` | **WS-07** | It is the data seam, and WS-07 built its validation. WS-02 consumes it — and holds the two thin aliases (`runner._to_df`, `backtest._candles_to_df`) that were once byte-identical copies, so WS-02's document names the re-fork risk even though it does not own the file |
| `app/engine/readiness.py` | **WS-06** | The verdict logic *is* the probe contract `deploy.sh` polls. Carved out of WS-02's `app/engine/` |
| `app/providers/replay.py` | **WS-07** | Deterministic replay is a data-plane capability, not an execution one. Carved out of WS-02's `app/providers/` |

## 7. Open coordination items

| Item | Between | State |
|---|---|---|
| Deploy the eight-phase architecture migration | WS-02 → WS-06 | **Owner.** Committed, verified, off the box for several sessions |
| Adopt the IR runtime in a live path | WS-01 → WS-02 | **Owner.** RFC Appendix C(d); parity evidence now exists |
| Does a display-name change mint a new body address? | WS-01 | Open question, pinned by a test. Resolving it is an RFC amendment |
| Narrow per-block declared inputs | WS-03 → WS-01 | WS-03's derived components declare the whole OHLCV frame |

## 8. Health checks for this layer

Run when the structure feels wrong, and after any interface change:

- Every `Consumes` entry names something another workstream lists under `Exports`.
- Every `Blocked by` names a specific item in a specific workstream, not a vague dependency.
- `DEPENDENCIES.md` is acyclic.
- No two workstreams claim the same file under `Owner surface`.
- `PROGRESS.md` §4 Next agrees with the topmost unchecked item of the workstream it names.
