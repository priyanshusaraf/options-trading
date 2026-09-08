Reference: [section index](../0013-research-approval-is-admission-not-a-lease.md). Read with its scope; this is not a new assignment.

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
