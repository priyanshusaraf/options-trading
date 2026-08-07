# ADR 0013 — Research approval is an admission prerequisite, not an authority lease

**Status:** accepted, 2026-08-07
**Context:** L1.4 closure reported that "evidence is not re-read on reload; an approval withdrawn
while a deployment is active goes unnoticed" and recommended implementing an evidence re-read.
That recommendation is **withdrawn by this ADR.** The question it assumed — that continued
authority depends on continued approval — had never been decided, and deciding it turns out to
matter more than implementing either answer.

**Decision:** research evidence and approval are an **admission prerequisite**, consumed once at
activation. They are not a continuously evaluated lease. An active deployment loses authority
through an execution-plane lifecycle action, never because research state changed elsewhere.

---

## 1. What the code actually does

Traced, not assumed. Every claim below names the file, and the two that decide the outcome were
verified by execution.

### 1.1 Evidence records are immutable, and verified rather than trusted

A run's terminal evidence is a content-addressed envelope in `research_experiment_run.
checkpoint_json`. `research/evidence.py:decode_terminal_evidence` re-derives the address from the
payload and additionally requires the stored text to be canonical JSON — so an evidence record
cannot be edited in place without failing verification, and a caller that receives evidence has
been told something *checked*, not something claimed. `ExperimentSpec` is immutable by design
(`research/domain/models.py:72`); a re-run after a code change is a new `ExperimentRun` against
the same spec, never a mutation of the old one.

`Finding` carries the same shape at the knowledge layer: it is revised only by a superseding
Finding through `superseded_by`, and its docstring is explicit that confidence is *not* decayed by
time — "a well-powered negative stays a fact".

**Answer: evidence cannot be modified, deleted or invalidated in place.** It can only be
superseded by a later record.

### 1.2 Approval decisions are write-once

`app/core/research_read.py:decide_project_candidate` is the **only** writer of a decision, reached
by exactly one route (`POST /projects/{p}/candidates/{c}/decisions`,
`api/ir_experiment_routes.py:526`). It refuses in three independent ways:

- `expected_status != "pending"` → `CandidateDecisionConflict`;
- `"decision" in scorecard` → `CandidateDecisionConflict` — **a candidate that has been decided
  can never be decided again**;
- the write is a compare-and-set on both `status` and the exact prior `scorecard_json`.

There is no route, service or migration that deletes a `PromotionCandidate` or clears a decision.

**Answer to "what happens when somebody withdraws approval": option C, and only C.** The system
has no withdraw operation. A later negative judgement is a *new* decision on a *new* candidate.
The original approval remains, intact and addressable, forever.

### 1.3 What a later negative decision actually changes

`_candidate_for_run` (`research_read.py:93`) selects
`filter_by(run_id=…).order_by(PromotionCandidate.id.desc()).first()` — the newest candidate for a
run. `verified_graph_decision` (`research_read.py:751`) walks the graph-bound runs and returns an
approval only if that newest candidate's decision is `approved`.

So a newer rejecting candidate on the same run *does* flip `verified_graph_decision` to `None`.
That is the mechanism by which research state could become a runtime kill switch — **if anything
on the runtime path read it.** Nothing does.

### 1.4 An activated deployment persists the whole admission fact

`ir_paper_deployments` (`app/db/models.py:1297`) records, at activation:

| Column | Proves |
|---|---|
| `graph_identifier`, `graph_version` | the exact artefact |
| `graph_content_address` | its exact bytes, re-derived from `graph_versions.artifact_json` |
| `evidence_run_id`, `evidence_candidate_id` | the exact approval object |
| `evidence_content_address` | the graph address research recorded — see §5.2 |
| `evidence_verified_at` | when admission was established |
| `admission_ok`, `admission_reason` | the warmup/history verdict |
| `deployment_id`, `instrument_key`, `interval` | the scope of the grant |
| `execution_mode`, `authority`, `runtime_source` | CHECK-constrained to `paper`/`authoritative`/`ir_graph` |
| `state`, `revision` | the lifecycle position and the CAS token |
| `rollback_strategy_key` | where authority returns |

The pointers into research (`run_id`, `candidate_id`) address records that §1.1 and §1.2 establish
cannot change. **A pointer to an immutable record is as good as a copy for proving a fact**, and
better for storage.

### 1.5 Reload is already independent of the research plane — measured

The decisive check. With every research door trapped to raise
(`paper_authority.verified_decision`, `research_read.verified_graph_decision`,
`research_read._research_session`), a reload was run against an active deployment:

```
RELOAD with the research plane trapped: 1 binding(s) loaded
   graph=strategy.expanding_z_impulse v1
   content_address=sha256:8f8896fa2141540c0f1...
   evidence run=17 candidate=8
   mode=paper authority=authoritative
   adapter rebuilt, version=sha256:8f8896fa2141540c0f1...
   adapter matches approved bytes: True
```

`active_bindings` re-derives the content address from the stored artefact and re-checks the
`(source, mode, authority)` triple; `adapter_for` rebuilds the adapter from the approved bytes and
verifies the address a second time; the authority gate verifies it a third time. **None of those
three checks reads research.** Restart recovery already satisfies §3's design goal in full.

---

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

## 5. Consequences

### 5.1 The L1.4 "evidence reload gap" is not a defect

Reclassified: **a deliberate consequence of plane separation**, with an **observability**
requirement attached. The L1.4 documents that called it a gap and named it "the first thing to
revisit before live authority" are corrected. Do not implement an evidence re-read on reload.

### 5.2 Admission must bind the exact graph *content* — closed 2026-08-08

**Superseding the "recorded and not fixed" note that stood here.** The imprecision was
investigated and turned out to be a real provenance defect, so it was fixed.

The evidence lookup is keyed on `(project, identifier, version)` — a **name**. Until
2026-08-08 every comparison in `_require_evidence` was also on the name, so a research
decision approving one artefact could admit a *different* artefact carrying the same
identifier and version. Reachable across an independently restored `research.db`, and
**proven reachable through the real service**, not theorised:

```
graph A address = sha256:9b2ea801986694093b3...
graph B address = sha256:fb2968b78ff4ed552b2...
RESULT: activation SUCCEEDED
  graph_content_address    = sha256:fb2968b78ff4ed552b2...  (B — trades)
  evidence_content_address = sha256:9b2ea801986694093b3...  (A — approved)
  addresses equal          = False
```

The row held both addresses and never compared them. The correction is that comparison, in
`_require_evidence`:

> **The immutable graph content receiving deployment authority must be the same immutable
> graph content bound into the research evidence used to admit it.**

`row.graph_content_address` is re-derived from the stored artefact bytes immediately
before; `decision["content_address"]` is what research recorded when the experiment was
bound, itself re-derived then by `graph_experiment.build_graph_provenance`. Two independent
derivations, now required to agree. A decision naming *no* content address is refused —
an approval that cannot say which bytes it approved has admitted nothing.

**It is an admission check and stays one.** It runs at activation and at resume — the two
moments authority is granted or re-granted — and **never on the runtime reload path**. That
is the model in §2, unchanged: research is required to grant or re-grant authority; ordinary
restart must not require research to be readable.

`evidence_content_address` **keeps its name**, which is imprecise — it holds the *graph*
address research approved, not the address of the decision envelope. Renaming it would be a
migration for naming alone on a table carrying live paper authority. The contract is stated
instead where it is used: the column docstring in `db/models.py`, `_require_evidence`, and
here. It is now load-bearing rather than decorative.

### 5.3 Newer contradicting research is an operator-visible fact — built 2026-08-08

Three facts, never collapsed, each in its own key of the cockpit payload:

| Fact | Where it comes from | Can it change authority? |
|---|---|---|
| **Admission basis** — the lineage that justified authority when it was granted | the deployment row, recorded at activation | it already did, once |
| **Current research view** — what research says *now* about this exact graph version | read on demand through the bridge | **never** |
| **Execution authority** — the lifecycle state | the execution plane | only via pause / retire / supersession |

`app/engine/cockpit.current_research(binding)` computes the middle one. It takes a binding and
returns a dict: no session, no runner, no transition verb — enforced by a test that parses its
body. The statuses reuse the existing candidate vocabulary
(`research_read.CANDIDATE_DECISIONS` = `approved | rejected`) rather than inventing a parallel
model:

- `no_newer_decision`
- `newer_approved_decision` — **a newer decision is not assumed negative**
- `newer_rejected_decision` — the attention case
- `unavailable`
- `admission_decision_not_visible` — the admitting decision cannot be seen at all, most likely a
  replaced `research.db`. Not "rejected": nothing rejected it

"Newer" is by candidate id, the ordering the bridge already uses. The read is served by one narrow
addition to the existing bridge, `research_read.graph_decision_history` — no second research
resolver, no independent database access, no duplicated candidate-selection semantics. It returns
`None`, not `[]`, when research cannot be read, so *unavailable* and *nothing contradicts this*
stay distinguishable.

**This is not a safety interlock and must never be described as one.** A newer rejection sets
`operator_attention: true` and `affects_execution_authority: false`. It does not pause, retire,
withdraw, refuse or downgrade anything. The correct shape is:

```
admission:           VALID HISTORICAL FACT
current research:    NOW NEGATIVE
execution authority: STILL ACTIVE
attention:           REQUIRED
```

not `execution authority: automatically revoked`.

### 5.3a Research availability affects observability, not authority

The cockpit *may* query research, because observability is not execution. If the read fails the
section degrades to `unavailable` with a detail, and the rest of the execution view still
assembles — what is running, why it was admitted, which graph version is authoritative, which
book, what money state exists, whether authority currently exists. Unavailability never infers
"still approved", never infers "rejected", and never removes authority.

### 5.3b Operator response

A newer contradictory decision creates operator *attention*. Acting on it is a human decision
executed through the existing lifecycle controls. Nothing automates it, and nothing should: the
point of the admission-only model is that a research row is not a kill switch.

### 5.4 The withdrawal invariant is strengthened, not weakened

This ADR removes a *research-driven* invalidation path that never existed. It does not touch the
*execution-driven* one L1.4 established, which is now stated in its strongest form:

> **Execution-capable pending state authored under a binding must not survive withdrawal or
> supersession of the authority that authored it.**

Today that state is the published signal plus its `executed_binding`. `_withdraw_superseded_signals`
enforces it, and L1.4's §7 review tightened its identity scope: it withdraws state **this** binding
authored, leaves state another binding authored alone, and withdraws unattributable state
fail-closed. Future richer execution intents inherit the invariant; no intent infrastructure is
built for it now.

---

## 6. Outcome

**A — ADMISSION-ONLY.** Research evidence and approval are an admission prerequisite. Active
deployment authority is self-contained and survives restart without the research plane. No
evidence-on-reload implementation is required, and one must not be added.
