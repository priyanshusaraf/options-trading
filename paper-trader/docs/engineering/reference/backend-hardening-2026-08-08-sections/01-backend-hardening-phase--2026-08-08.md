Reference: [section index](../backend-hardening-2026-08-08.md). Read with its scope; this is not a new assignment.

# Backend hardening phase — 2026-08-08

**Scope.** Repo-wide backend security, data-integrity, quant-leakage, performance and
provider-architecture review, with fixes rather than a report. Started from exact head
`b47e8f5` (migration head `0013`), branch `feat/exec-completeness`.

**Status:** in progress. Eight commits landed (2026-08-08 → 09). This document is the
continuity record — what was inspected, what was found, what changed, and what is next.

**Standing state after the commits below:** full backend + research suite **EXIT 0, no
failures** (it was not, at `b47e8f5` — see §3.1), `dryrun.py 700` **LEDGER OK**,
`backtest_smoke.py` **SWEEP OK**, migration head unchanged at `0013`. No schema change, no
migration, no execution-path change, nothing deployed.

---

## 1. Commits

| Commit | What |
|---|---|
| `e01bdcc` | docs: the V1 guidance review (previous phase's deliverable, not adopted) |
| `837febe` | fix: bound reporting reads at the query and at the request |
| `e6b9bbf` | fix: restore the shared market cursor, not just the pinned clock |
| `ce72249` | test: prove the hand-written strategies cannot read the future |
| `d383326` | docs: this record |
| `4a09c02` | chore: rebuild the Claude Code engineering harness (§6b) |
| `553d871` | feat: declare provider capabilities; fail closed on futures with no price feed |
| `7442e69` | refactor: ask capabilities, not the provider's name |
| `323c865` | docs: record the provider slices and the instrument-identity finding |
| `ef513fa` | docs: correct the record's own commit table |
| `0a55b3a` | feat: give instrument identity a seam, and put Kite behind it |
| `a23157a` | feat: price dated futures contracts (commodities only, as §9 records) |
| `ca6f231` | docs: record the resolver seam and the futures feed as done |
| *(pending)* | feat: a semantic provider conformance contract, and the four defects it found |

---

## 2. Security

### 2.1 Auth posture — accurate, deliberate, and untenable for V1 (no fix; owner gate)

`app/api/auth.py` is **one shared bearer token** (`PT_API_TOKEN`); empty disables auth
entirely, and empty is the shipped default and the production posture on a tailnet-only
box. `app/api/principal.py` resolves an explicit `ANONYMOUS_OWNER` rather than `None`, and
`is_allowed()` is honestly "the owner may do everything".

The middleware itself is well reasoned and was **not** found defective: exemptions are
matched on the unversioned path (so `/api/v1/health` is exempt for the same reason
`/api/health` is), `resolve_http_principal` returns `None` for exactly one condition (a
credential presented and refused), the fallback in `get_principal` re-checks rather than
defaulting to anonymous, and CORS is registered outermost on purpose so a 401 still
carries its headers.

**What is genuinely missing for multi-user V1**, and is a slice rather than a patch:

- No object ownership. `Project` has no owner column; `graph_artifacts.identifier` is a
  **global primary key** (gap G-5). Only `research_review_routes.py` references `principal`
  at all — the other ten route modules do not.
- Cross-project isolation *is* enforced and tested; cross-**principal** isolation does not
  exist because there is only one principal.

**Not a defect today. It is the V1 blocker**, and it is sequenced in the V1 proposal
(`docs/agent-guidance-review/v1-proposal-2026-08/02-v1-classification.md` §1.5). The free
hedge — namespacing identifiers per owner — remains untaken and still costs nothing.

### 2.2 Generated-strategy sandbox — audited, found sound (no change)

`research/strategy/builder/` is the only `exec()` in the tree. It was audited as a
potential arbitrary-code-execution path and is **tight**:

- `validate.py` runs a global AST **node-type allow-list** that excludes `Import`,
  `Attribute`, `Subscript`, `Lambda`, comprehensions, control flow and f-strings, plus a
  ban on any identifier or string containing `__`;
- then a structural pass requiring exactly one `def compute(df, **params)` whose body is
  block-call assignments and a canonical dict return;
- `load.py` execs in a namespace containing only whitelisted block callables and an
  **empty `__builtins__`**.

The only reachable calls are whitelisted block functions with `df` or numeric-literal
arguments. `validate_source` is called on the single exec path. No bypass found.

### 2.3 Injection and unsafe-primitive sweep — clean

`eval` / `exec` / `pickle` / `marshal` / `yaml.load`: one hit, the sandbox above.
Raw-SQL interpolation: three hits (`app/ledger/db.py:37`, `app/db/session.py:243,248`), all
interpolating **internal table/column constants**, never request data. `subprocess`: one
hit (`research/nightly.py`, a `git` invocation with a fixed argv, no shell).

### 2.4 Unbounded reads — REAL, FIXED (`837febe`)

See §4.1. Classified here too because it is a denial-of-service surface, not only a
performance defect: on a tailnet box any device, and after V1 any user, could turn a
reporting endpoint into a full-table dump.

---

## 3. Data integrity and test-evidence integrity

### 3.1 The suite was order-dependent — FIXED (`e6b9bbf`)

At `b47e8f5` the full suite was **not green**: `test_notifies_on_auto_open` failed under
`pytest tests research_tests`, passed under `pytest tests`, and passed in isolation. It was
neither flaky nor about notifications.

`MockProvider.now()` is `self._times[self._cursor]`, and `advance()` mutates that cursor on
the **process-wide singleton**. The rootdir conftest already restored a pinned `now`
attribute (ADR 0012 §4.1a) but not the cursor. Measured:

```
cursor=1149 -> now = 2025-03-05 15:15   (after the 09:30 gate — entry taken, test passes)
cursor=1150 -> now = 2025-03-06 09:15   (before it — "ENTRY WINDOW closed", test fails)
```

The cursor sat exactly on a session boundary, so **one extra `advance()` anywhere earlier
in the run** rolled the clock into the next morning. Suite greenness was a function of test
order, which an exact-head CI contract cannot tolerate.

Fixed at the same seam. `advance()` remains observable within a test and stops being
observable between them. `tests/test_shared_provider_isolation.py` pins both halves as
ordered pairs; both proven able to go red.

### 3.2 A vacuous test caught in my own work — worth recording

The first draft of the analytics equivalence test was **vacuous**, and the mutation sweep is
what found it. `Trade(segment=None)` does **not** store NULL: the column carries a
Python-side default, so the ORM substitutes `"options"` and the legacy shape is never
created. A mutation deleting the segment normalisation stayed green.

Two consequences, both now in the test file:

- unset shapes must be written by **direct SQL**, bypassing the ORM default;
- `trades.segment` is `NOT NULL`, so NULL is unreachable there and the **empty string** is
  the only reachable unset segment.

That second point exposed a **real bug in the fix itself**: `_seg`/`_strat` used Python's
`or`, which is falsy for `""` as well as `None`, while a plain `COALESCE` matches only
NULL. `NULLIF(col, '')` inside the COALESCE is load-bearing, not decoration.

Also: the oracle must not be written in the implementation's own SQL, or it agrees with a
wrong implementation. It computes the expected count in Python from raw column bytes.

---
