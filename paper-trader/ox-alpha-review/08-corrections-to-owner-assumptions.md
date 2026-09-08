# 08 — Corrections to Owner Assumptions

You asked me to point out where you're wrong. Three adjustments, one confirmation, one partial
confirmation.

## 1. "The two-lineage thing is not a problem — only codex works on this now" — MOSTLY AGREE, with three caveats

The plan (codex is the line; merge to main later) is sound. But:

- **Commit the 374 dirty entries first.** A merge of a branch whose state lives mostly in the
  working tree merges almost nothing. The uncommitted surface is ~4 days of programme state
  including migrations 0035–0039 and the market_truth/market_data modules. Until it's committed,
  "the codex branch" is not what you think it is.
- **One commit is stranded on the old line:** `58436bb` (parked Upstox data adapter + its design
  docs) is on `feat/exec-completeness` and NOT in the codex line (merge-base is `072eb8f`). At
  merge time either cherry-pick it or consciously drop it as superseded — but decide, don't let it
  silently vanish.
- **Mark the old line's docs superseded** when you merge (`feat/exec-completeness`'s CONTINUE.md /
  PROGRESS.md still present themselves as the resume point). One banner line each prevents any
  future agent or human from resuming against stale state.

## 2. "AWS scale-up, no conflict, droplet not a constraint" — CONFIRMED, with two consequences

No conflict found; nothing in the governance contradicts it. Two consequences people miss:

- The **pool-sizing deferral explicitly dies** with this decision — that decision was deferred only
  because of droplet OOM history. Re-open it now (doc 05 D2), because it is also your biggest
  user-facing performance risk.
- **Cutover is still an owner-gated production change** under the existing rules — AWS doesn't
  lower that bar, it raises it (client money on new infra). Plan cutover as its own slice with
  reconciliation evidence, and note the currently-live droplet bot runs code from neither branch.

## 3. "Phase 5 and 6 look much cleaner after the foundation" — PARTIALLY AGREE

Agreed for Phase 5: it decomposes into parallelizable node-library breadth on a stable IR.
Two adjustments:

- **Pull the capacity/rate contract forward** from Phase 6 preflight into a Phase 5 slice (doc 04
  §4). Your no-silent-timeout requirement depends on it, and it's cheap at Phase 5 scale.
- **Phase 6's hard part is capital reservation and position ownership semantics**, not plumbing —
  the preflight receipts are the easy half. Budget review rigor there accordingly (it touches
  sizing = owner gate).

## 4. "We must speed up" — AGREE, and here is where the time is actually going

From the stage ledger: Phases 3–4 consumed roughly 50 stages over ~5 days, and the majority of
*stage count* (not value) went into evidence-harness repair cycles for one migration fixture
question — while two real product defects wait fully specified. The speedup is not "review less":
it is (a) stop generating self-referential meta-evidence (doc 03), (b) commit-per-capsule so
reviews stop re-fighting packaging shape, (c) parallel capsules for breadth work, (d) reference
settled guards instead of re-proving them. Conservatively this halves stage count to Phase 5 open,
without touching review rigor on authority/money surfaces.

## 5. One thing you did NOT ask about but should know

The current tree fails test collection (two errors, documented in doc 02). Whatever else is true,
until that's fixed nobody — including Codex — can verify claims about current bytes. It should be
treated as a P0 alongside the commit sweep, because Recovery 9's repair is being built atop it.
