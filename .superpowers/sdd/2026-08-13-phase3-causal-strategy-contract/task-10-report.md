# Task 10 report: promotion, shadow, paper, and deployment authority

## Scope

Task 10 binds causal-admission receipts through promotion decisions and shadow/paper
authority boundaries. Causal admission remains an additional guard only; it does not
claim complete Strategy Preflight or weaken account, capital, history, paper/live,
execution, or protection gates.

## Observed evidence

Initial RED:

```text
cd paper-trader/backend && .venv/bin/pytest -q \
  tests/test_shadow_deployments.py::test_shadow_activation_refuses_a_missing_local_causal_receipt \
  tests/test_paper_authority_runtime.py::test_paper_activation_refuses_a_missing_local_causal_receipt
# 2 failed: both activation paths accepted a forged address with no local receipt.
```

Focused GREEN after adding the local receipt check:

```text
cd paper-trader/backend && .venv/bin/pytest -q \
  tests/test_shadow_deployments.py::test_shadow_activation_refuses_a_missing_local_causal_receipt \
  tests/test_paper_authority_runtime.py::test_paper_activation_refuses_a_missing_local_causal_receipt
# 2 passed
```

Deployment zero-write RED/GREEN:

```text
cd paper-trader/backend && .venv/bin/pytest -q \
  tests/test_deployments.py::test_new_explicit_deployment_without_admission_refuses_before_insert
# RED: Failed: DID NOT RAISE ValueError
# GREEN: 1 passed; EXIT=0
```

Individual verification at the current freeze:

```text
tests/test_paper_authority_runtime.py::test_paper_activation_refuses_a_missing_local_causal_receipt
# 1 passed; EXIT=0

tests/test_shadow_deployments.py
# stopped after exceeding the required 60-second single-file cap; no result claimed.
```

Narrow mutation evidence:

```text
tests/test_deploy_bridge.py::test_deploy_bridge_receipt_check_bypass_mutant_is_killed
# 1 passed; EXIT=0

tests/test_deployments.py::test_deployment_strategy_write_bypass_mutant_is_killed
# 1 passed; EXIT=0

tests/test_shadow_deployments.py::test_shadow_activate_receipt_bypass_mutant_is_killed
# process finished after the harness relay window; no result claimed.
```

## Mutation closure update

The original shadow and paper mutation probes had two setup defects: their local-receipt
monkeypatches targeted the `LegacyMoneyScope` wrapper rather than the service call site,
and the full structural admission fixture could consume the 60-second probe budget before
the named receipt guard ran. The probes now construct a valid staged graph/version with a
syntactically valid but absent local receipt, return matching research evidence, and stub
only the unrelated history-admission decision. Each mutates the underlying service's
`_require_local_receipt` call. The resume cases enter the paused state directly, so they
exercise only the resume transition and do not spend time proving the already-covered
activation path.

Fresh individual mutation results, each with a 60-second subprocess cap:

```text
tests/test_shadow_deployments.py::test_shadow_activate_receipt_bypass_mutant_is_killed
# 1 passed; EXIT=0; 28.35s

tests/test_shadow_deployments.py::test_shadow_resume_receipt_bypass_mutant_is_killed
# 1 passed; EXIT=0; 30.00s

tests/test_paper_authority_runtime.py::test_paper_activate_receipt_bypass_mutant_is_killed
# 1 passed; EXIT=0; 24.45s

tests/test_paper_authority_runtime.py::test_paper_resume_receipt_bypass_mutant_is_killed
# 1 passed; EXIT=0; 26.81s

tests/test_strategy_admission_authority.py::test_promotion_approval_receipt_bypass_mutant_is_killed
# 1 passed; EXIT=0; 29.33s
```

The promotion mutation persists a real owner-local candidate, run, graph provenance, and
research receipt. It presents substituted published graph bytes that falsely claim the
approved content address. Removing only fresh `verify_admission` allows approval; with the
real check present, the nested mutation harness observes the required refusal. This keeps
candidate/run/receipt binding checks intact while proving the fresh-verification guard.

The bridge happy-path fixture initially reproduced the graph-version JSON CHECK failure,
then an artefact/receipt version mismatch. The fixture now stamps the graph's stored JSON
version before admitting and persisting it. Its final bounded test result was not received
before this freeze and is not claimed.

Compatibility-fix round two retained the production nonlegacy IR-only rule. Positive
deployment lifecycle tests now build one real owner-local admitted graph/version/receipt;
tests that formerly created handwritten, generated, unknown, or strategy-less new books
now assert the intended `ADMISSION_REQUIRED` write-time refusal. The explicit legacy
deployment remains supplied only by `ensure_legacy_deployment`.

```text
tests/test_deployments.py
# stopped at 52 seconds under the single-file cap; no result claimed.

tests/test_execution_binding.py::test_a_deployment_that_pins_a_strategy_wins_over_the_instrument_row \
  tests/test_execution_binding.py::test_an_unresolvable_deployment_pin_fails_closed
# 2 passed; EXIT=0

tests/test_deploy_bridge.py::test_deploy_creates_watchlist_assigns_and_archives_running \
  tests/test_deploy_bridge.py::test_deploy_bridge_refuses_a_forged_receipt_before_writes \
  tests/test_deploy_bridge.py::test_deploy_bridge_refuses_a_foreign_account_before_writes
# stopped at 56 seconds under the cap; no result claimed.
```

Test-infrastructure optimization: deployment and deploy-bridge fixtures now cache only the
immutable admission artifact calculation per module. Each fresh database still receives the
canonical artifact through `strategy_admissions.put` and a matching immutable `GraphVersion`,
then exercises the normal current-receipt verifier. The first cached positive deployment test
process exited before the 60-second cap but its final pytest relay was unavailable, so no result
is claimed. The full file and bridge trio were not rerun because this timing did not predict a
reliable under-cap completion.

Compilation and whitespace verification:

```text
cd paper-trader/backend && .venv/bin/python -m py_compile \
  app/core/research_read.py app/core/shadow_deployments.py \
  app/core/paper_authority.py app/core/deploy_bridge.py \
  app/api/portfolio_routes.py app/core/execution_binding.py
git diff --check
# exit 0
```

The combined shadow/paper suites were launched during development but overlap with
other in-progress database-reset test processes in the shared worktree. Their final
result is not claimed here. No broad suite ran.

Deployment wiring now rejects a missing or non-current owner-local IR receipt before
the bridge creates a watchlist, deployment, archive record, or membership. A successful
bridge writes a canonical watchlist-bound `Deployment` with the same graph strategy
version and admission address. `create_deployment` independently repeats that exact
receipt check for non-legacy IR deployment writes. The legacy deployment remains a
read-compatible quarantine path because this worktree has no deterministically persisted
admitted expanding-z record to pin; no address was inferred or invented.

The non-legacy bridge request also requires an explicit broker account identifier.
It verifies that exact active account under the owner before any write and never picks
an arbitrary account from a multi-account owner.

## Final compatibility verification and review

Root retained the focused results after the immutable-artifact fixture optimization:

```text
tests/test_deployments.py::test_new_deployments_start_as_draft_not_active
# 1 passed; exit 0

tests/test_deployments.py::test_duplicate_name_is_refused \
  tests/test_deployments.py::test_cannot_arm_a_non_active_deployment \
  tests/test_deployments.py::test_a_deployment_pinning_a_real_strategy_reports_its_content_hash
# 3 passed; exit 0

tests/test_deploy_bridge.py::test_deploy_creates_watchlist_assigns_and_archives_running \
  tests/test_deploy_bridge.py::test_deploy_bridge_refuses_a_forged_receipt_before_writes \
  tests/test_deploy_bridge.py::test_deploy_bridge_refuses_a_foreign_account_before_writes
# 3 passed; exit 0
```

The final independent review returned **SPEC PASS / QUALITY PASS**. It confirmed that the
compatibility fixtures persist a real immutable owner-local receipt and matching graph version,
while production continues to verify the receipt and account. All seven named authority mutants
are killed. The inherited broker/venue protected files remain outside this task.
