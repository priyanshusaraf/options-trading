# Task 8 report: editor publication and research admission enforcement

Risk: **Critical**. This task protects the boundary where a graph becomes an immutable
published artefact or consumes research data.

## Delivered

- Publication now admits after semantic validation, stores the exact execution-plane receipt,
  and writes its address with `GraphVersion` in one transaction.
- A typed admission refusal commits the valid edited draft through the existing revision CAS,
  but leaves `published_revision`, `current_version`, immutable version rows, and receipts
  unchanged. The editor returns stable HTTP 422 codes without diagnostic detail.
- Both graph publication endpoints return the stable refusal code. Published-graph experiments
  copy a freshly verified owner-local research receipt before any
  provider materialization. The worker reloads it, checks exact graph bytes/address and owner,
  and calls `verify_admission` again.
- Generated descriptors store the research receipt at enqueue. Their replay worker reloads and
  re-verifies it before source materialization.
- Durable scheduler failure events and their projection payload retain a validated stable refusal
  code instead of replacing it with generic exception text.

## Focused RED/GREEN evidence

- `test_publish_persists_the_exact_owner_scoped_admission_receipt` was RED because
  `GraphVersion.admission_address` was null; it is GREEN after transactional receipt storage.
- `test_admission_refusal_returns_a_stable_422_and_preserves_the_draft` was RED because no
  admission boundary existed; it is GREEN and proves draft-only persistence on refusal.
- `test_missing_graph_receipt_refuses_before_the_experiment_can_touch_data` proves the graph
  worker refuses before its data/provenance seam.
- `test_graph_worker_freshly_verifies_the_persisted_receipt` proves row existence is not enough.
- `test_failure_projection_records_the_stable_refusal_code` proves `RECEIPT_STALE` reaches the
  durable operation event payload.

## Commands observed

```text
.venv/bin/python -m py_compile app/editor/graph_artifacts.py app/api/ir_edit_routes.py \
  app/strategy/admission.py research/orchestrator/graph_experiment.py \
  research/orchestrator/generate.py research/domain/operations.py research/nightly.py \
  scripts/research_run.py

.venv/bin/pytest -q tests/test_graph_artifacts.py::test_publish_persists_the_exact_owner_scoped_admission_receipt
.venv/bin/pytest -q tests/test_ir_edit_routes.py::test_admission_refusal_returns_a_stable_422_and_preserves_the_draft
.venv/bin/pytest -q research_tests/test_graph_experiment.py::test_missing_graph_receipt_refuses_before_the_experiment_can_touch_data
.venv/bin/pytest -q research_tests/test_graph_experiment.py::test_graph_worker_freshly_verifies_the_persisted_receipt
.venv/bin/pytest -q research_tests/test_operation_repository.py::test_failure_projection_records_the_stable_refusal_code
```

No broad or Phase 3 suite was run. Task 12 owns that boundary. This worktree is left unstaged
for independent review.

## Review fix round 1

- Moved the typed admission-refusal handler from graph draft creation to the direct
  `POST /versions` publication route, before its broad `GraphRejected` handler.
- Added `test_version_publication_returns_stable_admission_refusal_without_advancing_state`.
  Its observed output was `1 passed` (with the existing TestClient deprecation warning).
- Re-ran the named focused set:

```text
.venv/bin/pytest -q \
  tests/test_graph_artifacts.py::test_publish_persists_the_exact_owner_scoped_admission_receipt \
  tests/test_ir_edit_routes.py::test_admission_refusal_returns_a_stable_422_and_preserves_the_draft \
  research_tests/test_graph_experiment.py::test_missing_graph_receipt_refuses_before_the_experiment_can_touch_data \
  research_tests/test_graph_experiment.py::test_graph_worker_freshly_verifies_the_persisted_receipt \
  research_tests/test_operation_repository.py::test_failure_projection_records_the_stable_refusal_code \
  research_tests/test_builder_generate.py::test_generated_enqueue_persists_owner_scoped_receipts_before_worker_io \
  research_tests/test_builder_generate.py::test_durable_generated_authority_mismatch_refuses_before_provider_io -x
```

The targeted process completed successfully. `git diff --check` is clean. The protected-file
hashes still match their approved baseline.
