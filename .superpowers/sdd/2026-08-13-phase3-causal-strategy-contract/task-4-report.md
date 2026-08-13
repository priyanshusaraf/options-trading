# Phase 3 Task 4 implementation report

## Outcome

Task 4 adds the independent completed-prefix admission lane. The reference evaluator owns its topological walk, input wiring, prefix construction, recursive state replay, timestamp transport, and output assembly. It does not import the vector evaluator, cache, or its private helpers. Admission loads only the app-owned immutable fixture suite, compares recursive streams before final decisions, binds fixture and decision addresses into the receipt, and re-derives that receipt before returning an `IRGraphStrategy` for new exposure. A handwritten strategy remains evidence, not runtime authority.

The suite is intentionally narrow. It covers the 23 admitted generated manifest entries, every RSI source × smoothing choice, a two-session opening-range reset, and an expanding-regime median transition. It does not claim the future first-party node catalogue, numeric-validity model, market truth, provider capability, role binding, resource plan, or live-deployment preflight.

## Critical failure hypotheses and evidence

- **Independent evaluator:** the initial missing reference-module test was observed RED. The focused reference suite reports `7 passed`; it blocks calls/imports to vector runtime helpers, limits bounded history, checks recursive replay determinism, and normalizes fixture timestamps.
- **Manifest parity:** `research_tests/test_block_causal_parity.py` derives its set from `CAUSAL_MANIFEST`. Grouped runs reached `[100%]` for 23 manifest cases, 16 RSI `rsi_gt` choices plus its manifest case, 16 `rsi_lt` choices plus its manifest case, and the two session/regime cases. The reviewer found no causal bypass in this bounded suite. The manifest currently has no quarantined entries; a future quarantine must add its deterministic lowering refusal.
- **Fresh and stale causal contamination:** the post-registration helper mutation dies with `IMPLEMENTATION_STALE`; five independently registered future-reading kernels die with `STREAMING_DIVERGENCE`. After the final admission adjustment the command returned `{"causal_killed":5,"identity_killed":1,"survived":0}` with exit 0.
- **Handwritten adapter/runtime authority:** the new focused test first reproduced a genuine `STREAMING_DIVERGENCE` on the monotonic fixture. Diagnosis showed raw graph and handwritten streams were identical, including 23 `shortExit` rows; admission alone had applied the graph's 302-bar warmup to vector/reference bytes while canonicalizing raw handwritten bytes. The first mismatch was `shortExit` at `2026-08-10 09:30:00+05:30`, vector `False`, adapter `True`. Admission now compares the raw causal decisions. The declared warmup remains part of the structural receipt and `IRGraphStrategy.compute` remains the authority that masks unsettled new-exposure bars. The test asserts byte-address equality and that `runtime_for_admitted` returns `IRGraphStrategy` only after re-verification.

## Scoped freeze checks

- Changed Python files compile with `python -m py_compile`: PASS.
- `git diff --check`: PASS.
- Protected inherited hashes match the approved baseline.
- Staged files: none.
- No broad backend or migration suite was run; Task 12 owns that phase-level boundary.

## Independent final review

The final read-only review returned **SPEC PASS / QUALITY PASS**. Its exact scoped Task 4 command
and the full `tests/test_strategy_admission.py` file exited 0. The reviewer directly admitted the
shipped graph, obtained the verified `IRGraphStrategy`, and confirmed that all four canonical
signals remain false through the 302 pre-warmup bars. Forged receipts, deterministic state replay,
manifest parity, causal mutations, handwritten parity, protected hashes, compilation, and diff
checks passed. No load-bearing finding remains.

Task 4 makes causal admission a necessary guard only. The explicit Strategy Preflight nonclaims
remain owned by later phases. Research remained reference-only: no VectorBT or XState source,
dependency, or runtime was added.
