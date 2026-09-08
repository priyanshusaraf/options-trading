Reference: [section index](../0013-research-approval-is-admission-not-a-lease.md). Read with its scope; this is not a new assignment.

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
