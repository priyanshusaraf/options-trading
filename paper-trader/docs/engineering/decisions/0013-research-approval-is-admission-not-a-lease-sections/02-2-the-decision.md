Reference: [section index](../0013-research-approval-is-admission-not-a-lease.md). Read with its scope; this is not a new assignment.

## 2. The decision

```
research evidence
      ↓
approval / admission decision          ← consumed ONCE, at activation
      ↓
explicit deployment activation         ← the moment authority is created
      ↓
persisted execution authority          ← self-contained; survives restart alone
      ↓
runtime
```

Authority is created by an execution-plane act and ends by an execution-plane act: `pause`,
`resume`, `retire` (with a named rollback target), or supersession by a new binding taking the
`(deployment, instrument, interval)` slot. No new `revoke` operation is needed — `pause` and
`retire` already cover immediate withdrawal, and both are already wired to refresh the engine
before the route returns (`api/routes.py:1258`, `:1280`).

**Research approval is not a second runtime kill switch, and must not become one.** The kill
switches are the arm flag, the daily-loss halt, the order circuit breaker and the lifecycle
actions above — all in the execution plane, all operator-visible, all already tested.

### Why this direction and not the other

1. **Plane separation is a standing invariant** (hard invariant 5; ADR 0011; `research/guards.py`).
   Research and editor activity must not silently control active execution. An evidence re-read on
   every reload would make a research-plane row a live execution control with no operator action —
   precisely the coupling the architecture spends effort preventing.
2. **It would make restart depend on research availability.** `research.db` is a separate file that
   may legitimately be absent (`_research_session` yields `None` when it does not exist, and every
   read degrades to empty). Under a lease model, a missing or unreadable `research.db` would
   silently strip authority from a correctly-approved deployment on the next restart — an outage
   caused by a plane that owns no execution state.
3. **The withdrawal semantics would be wrong anyway.** §1.2 shows there is no withdrawal; there is
   only a newer decision, possibly about a different candidate, possibly by a different reviewer,
   possibly about a re-run that says nothing about the deployed artefact. Treating "the newest
   candidate for this run is negative" as "stop trading" reads far more into the research ledger
   than it means.
4. **Nothing is lost.** The approval that mattered is immutable and still addressable. Newer
   negative research is real information — it belongs in front of an operator (§5.3), not in a
   control path.

---

## 3. The A8 / A14 scenario, resolved

> E17 exists → A8 approves → D42 is activated against G17 and A8 → a researcher later records a
> superseding rejection A14 → the runtime restarts.

Four distinct concepts, deliberately not equated:

| Concept | Answer | Why |
|---|---|---|
| **Historical provenance** | Unchanged. D42 still names run/candidate A8, and A8 is immutable | §1.2 |
| **Eligibility for a *new* deployment** | Gone. `verified_graph_decision` now returns `None` for G17, so a fresh `activate` or `resume` refuses with `EvidenceUnverified` | §1.3, `paper_authority.activate` |
| **Continued authority of D42** | **Retained** across the restart. Authority was granted by activation and ends by a lifecycle action | §1.5, §2 |
| **Operator visibility that A14 exists** | **Should be surfaced, and is the real requirement.** Not a control — a read | §5.3 |

This is the documented, intended behaviour. A14 prevents a new deployment and prevents a resume;
D42 continues until somebody pauses or retires it. That is a decision a human makes, with A14 in
front of them.

Note the asymmetry that makes this safe: **`resume` re-verifies evidence.** A paused deployment
cannot come back on stale approval (`paper_authority.resume` → `activate`, proven by
`test_resume_re_verifies_evidence_rather_than_trusting_the_pause`). So the lease model's one real
benefit — "a withdrawn approval should stop it coming back" — is already delivered at the only
boundary where it is a genuine risk.

---

## 4. Failed-refresh semantics

L1.4 established that a failed `refresh_paper_authority` keeps the previously verified map. Under
this ADR that is not merely acceptable, it is correct — but the reasoning must distinguish two
failures that look identical from inside the loop:

| Failure | Meaning | Correct response |
|---|---|---|
| **Execution-authority data is invalid** — the content address disagrees, the triple is not the reviewed one, the artefact will not rebuild | This binding is not what it claims | **Fail closed**: drop the binding, report it. Already the behaviour (`active_bindings`, `register_active_adapters`) |
| **The store is temporarily unreadable** — the database read throws | We do not know | **Keep what was last verified**, return 0, log. Already the behaviour |

The second is right for paper because the alternative — clearing authority on a transient read
error — silently stops a correctly-approved deployment, and the map being kept was itself verified
by all three checks when it was loaded. It never *widens* authority: a failed refresh cannot add a
binding, only retain one (pinned by
`test_a_failed_refresh_does_not_silently_widen_authority`).

**For eventual live authority this becomes a real design question, and is deliberately left open
here:** whether a live binding may survive a refresh that could not be verified at all, or whether
live requires a positive re-verification within some bound and halts otherwise. That belongs to
the live-authority design, which is owner-gated and designed nowhere. Recording the question is
the deliverable; answering it is not.

---
