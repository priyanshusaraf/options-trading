Reference: [section index](../02-KLEPPMANN-PASS-A-DATA-TIME-TRUTH.md). Read with its scope; this is not a new assignment.

## Current authority and identity reconstruction

### Market truth and instruments

- `app/market_truth/identity.py:55-84` defines one domain-separated canonical fact byte/address path.
- `identity.py:198-270` stores physical instrument identity without broker tokens.
- `identity.py:358-453` separates provider contract and temporal provider alias facts.
- `identity.py:456-470` rejects overlapping token, symbol, or physical mappings.
- `identity.py:533-537` preserves the exact held contract against later selector movement.
- `app/market_truth/rulebook.py:22-63` stores effective and recorded revision facts.
- `rulebook.py:65-176` binds current v3 `recorded_at`, `knowledge_cutoff`, instruments, source evidence, quality, and reconstruction.
- `rulebook.py:254-267` resolves the latest known revision at the cutoff and refuses current-rule substitution.

Status: `CLEAN` for the inspected constructors and loaders. Real historical contract-master completeness, sessions, corporate actions, expiry rules, and provider conformance remain unverified.

### Observations and causal alignment

- `app/market_data/observations.py:117-195` binds exact provider bytes, token mapping, field, resolution, four times, validity, correction, and raw byte range.
- `observations.py:214-301` binds normalized input addresses, algorithm, policy, market truth, four times, numeric validity, and correction lineage.
- `observations.py:345-422` permits only exact or backward alignment, completed rows, explicit age/skew, and no fallback.
- `tests/test_phase4_alignment_causality.py:25-180` covers future append, forming bars, missing/invalid states, ambiguity, skew, and next-bar entry.

Status: `AT RISK`. `_aware_ordered` requires completion and availability after event time and recording after availability, but does not require availability at or after completion. This confirms prior NMT-002. The current aligner checks both clocks and the accepted Q03 loader requires equality, so no current Q03 look-ahead result is shown.

The general `DataObservation` projection omits `recorded_at` and correction lineage. If two revisions preserve the original `completed_at`, its tie handling refuses rather than select the latest revision available at a declared cutoff. That is fail-closed, not a wrong number, but the general revision-aware consumer contract remains missing. Only tests construct `DataObservation`; no production consumer was found.

### Dataset and Q03 canonical research binding

- `research/data/canonical_dataset.py:416-450` reloads every typed dependency and verifies it was recorded by `as_of`.
- `canonical_dataset.py:453-608` verifies one physical cash instrument, exact contiguous row references, completed/available equality, correction absence, raw byte ranges, typed transform/algorithm/truth closure, OHLCV coherence, ranges, and no candle repair.
- `canonical_dataset.py:599-608` records full manifest, instrument, segment, object, time interpretation, charge/sizing projection, and adapter identity.
- `canonical_dataset.py:611-629` enforces one common non-future `as_of` and owner-scoped selection.
- `canonical_dataset.py:632-654` refuses graph requirements outside the pure completed-bar subset and records the adapter source address.

Status: `CLEAN WITH NARROW SCOPE`. It proves a synthetic working contract, not historical provider truth or wider instruments.

### Graph identity and causal parity

- `app/ir/runtime.py:367-415` compares every node output on causal prefixes with a fresh cache.
- `app/ir/streaming_reference.py:35-172` independently reconstructs topology and completed-prefix execution.
- `tests/test_ir_v2_prefix_parity.py` covers v2 vector/prefix parity and a killed future-shift mutation.
- `research_tests/test_block_causal_parity.py` maps admitted block manifests to the independent prefix oracle.

Status: `CLEAN` for the tested graph corpus. Prefix parity does not prove numerical formulas or real market-time availability.

### Backtest and research result identity

- `app/backtest/identity.py:136-172` binds ordered OHLCV bytes and provider/instrument/window context for the legacy dataset address.
- `identity.py:265-405` binds dataset, admission, strategy, source bytes, parameters, capital, window, slippage, charges, event rules, exits, and premium assumptions. Phase 4 authority is optional for legacy callers.
- `app/backtest/cache.py:45-106` verifies the Phase 4 chain before minting a complete phase4 cache identity.
- `research/orchestrator/run.py:234-270` records dataset, costs, charge schedule, gates, seed, versions, graph provenance, and build commit in the experiment recipe.
- `research/domain/models.py:448-480` makes `ExperimentSpec` immutable.

Status: `VIOLATED` at experiment-spec collision handling and `AT RISK` for legacy paths without Phase 4 binding.

## Direct findings

### KPV5-A-001: truncated experiment-spec collision silently reuses another recipe

- **Class:** CONFIRMED DEFECT / MISSING INVARIANT.
- **Source principle:** stable canonical bytes and explicit schema identity; source does not prescribe a hash width.
- **Code:** `research/orchestrator/run.py:124-134` truncates SHA-256 to 32 hex characters. Lines 270-293 look up that ID and reuse an existing immutable spec without comparing `recipe_json`.
- **Reproduction:** `characterization/test_experiment_spec_collision.py` forces the collision branch with two different slippage recipes. The current path stores one spec and returns the same ID for both runs.
- **Evidence:** `.agent/runs/kleppmann-reaudit-v5/pass-a/red-experiment-spec-collision.log`, expected exit 1.
- **Consequence:** a run's terminal provenance can disagree with the immutable spec named by `spec_id`; reconstruction and approval can read the wrong recipe.
- **Likelihood:** cryptographic random collision is extremely low at present volume. The invariant still fails closed incorrectly, and the 128-bit truncation is unnecessary.
- **Release:** V0 NON-BLOCKING HARDENING before public evidence claims; V1 FOUNDATION if a migration is needed.
- **Smallest safe response:** compare canonical stored recipe on exact reuse and refuse any mismatch. Introduce full 256-bit identity additively; do not rewrite historical 32-character IDs silently.

### KPV5-A-002: full-history qualification contaminates later OOS evidence

- **Class:** CONFIRMED DEFECT / RESEARCH VALIDITY.
- **Code:** `run.py:346-390` calls `qualify_instrument` on the complete dataset before `validate` or nested optimization sees the same dataset. Qualification itself uses the full backtest and bootstrap gate (`pipeline/qualify.py:32-50`).
- **Reproduction:** `characterization/test_oos_qualification_contamination.py` records 400 rows at qualification and 400 at validation for each instrument.
- **Evidence:** `.agent/runs/kleppmann-reaudit-v5/pass-a/red-oos-qualification-contamination-recheck.log`, expected exit 1.
- **Consequence:** a candidate or instrument reaches “OOS validation” only after the alleged OOS suffix influenced its qualification. The later record is not untouched confirmatory evidence.
- **Release:** V0 BLOCKER for displaying this pipeline as locked or untouched OOS. Otherwise label it exploratory and unavailable until the robustness owner corrects it.
- **Smallest safe response:** seal train/qualification, embargo where required, and OOS boundaries before candidate or instrument selection. Preserve every screened-out candidate and repeated peek. Do not fix this with a higher statistical threshold.

### KPV5-A-003: V0 permits the legacy current-universe sweep route

- **Class:** CONFIRMED DEFECT / MARKET-TRUTH AND RELEASE BOUNDARY.
- **Code:** `app/core/release_profile.py:143-182` marks backtesting `ENABLED_WITH_LIMIT` but omits `POST /api/backtest/sweep` from denied routes. `app/api/backtest_routes.py:61-90` exposes the legacy sweep. `app/backtest/universe.py:40-134` resolves today's provider dump or curated fallback. `app/api/ir_experiment_routes.py:375-392` also retains the legacy provider materializer for noncanonical selections.
- **Reproduction:** the pure policy test proves `denied_route(..., POST, /api/backtest/sweep)` returns `None` under V0.
- **Evidence:** `.agent/runs/kleppmann-reaudit-v5/pass-a/red-v0-legacy-sweep-policy.log`, expected exit 1.
- **Consequence:** an authenticated API caller can bypass the canonical-manifest-only product journey and request research over current symbols, tokens, strike grids, or mock fallback without the accepted point-in-time authority chain.
- **Release:** V0 BLOCKER before any public/API release of the V0 profile. The legacy standard profile may remain compatible under an explicit non-V0 boundary.
- **Smallest safe response:** deny legacy sweep/materialization routes in V0 or require the canonical selection contract at the shared route boundary. UI hiding is not an authority gate.

### KPV5-A-004: completed-observation authority permits availability before completion

- **Class:** MISSING INVARIANT; confirms NMT-002.
- **Code:** `observations.py:28-35`, `143-164`, `237-261`, and `317-334`.
- **Current containment:** alignment requires both timestamps by the evaluation instant; Q03 requires `available_at == completed_at`.
- **Consequence:** future capture/export/consumer code that checks availability only can use a completed value before it exists.
- **Release:** V0 BLOCKER before real provider capture; not a demonstrated current Q03 wrong result.
- **Smallest safe response:** enforce `available_at >= completed_at` for completed-bar observations after inventorying stored facts. Preserve delayed publication and raw evidence.

### KPV5-A-005: IID trade bootstrap lacks a dependency assumption

- **Class:** MISSING TEST / RESEARCH METHOD ASSUMPTION.
- **Code:** `research/stats/evidence.py:14-24` resamples individual trades independently. Qualification and validation label its lower quantile a confident positive edge.
- **Consequence:** clustered, overlapping, or regime-dependent trades can produce an interval that is too narrow and a false pass.
- **Release:** V0 NON-BLOCKING only if the result is labelled exploratory; V0 BLOCKER before a confidence claim.
- **Smallest safe response:** state the independence/exchangeability model, test realistic dependent sequences, and use a dependence-aware method only if the data justifies it. Broader statistical sources belong in Chat 2.

### KPV5-A-006: revision-aware general alignment remains undefined

- **Class:** FUTURE DESTRUCTIVE ASSUMPTION / MISSING INVARIANT.
- **Code:** `DataObservation` omits recording/correction facts and equal event/completion ties refuse.
- **Reachability:** tests only; the accepted Q03 path refuses correction lineage.
- **Release:** SEAM ONLY for broader provider corrections and point-in-time exports.
- **Smallest safe response:** project a revision/cutoff identity explicitly; never change `completed_at` to publication time merely to break a tie.

### KPV5-A-007: optimization search reconstruction is under-proven

- **Class:** RESEARCH EVIDENCE GAP, not a confirmed wrong result.
- **Code:** `run.py:234-267` records method versions, gates, build SHA, seed, and datasets but not the resolved parameter-space document or candidate order. `pipeline/optimize.py:122-174` derives those from current code. `OptimizationTrial` persists params, objective, trade counts, and selection, but not `is_sharpe` or the PBO performance matrix.
- **Positive evidence:** the immutable trial ledger records every fold/candidate parameter row; eligible trial Sharpe can usually be reconstructed from objective and trade count; current focused method tests cover grid membership, one selected row, DSR variance, and PBO behavior.
- **Limit:** tie selection depends on candidate order, and the complete PBO/DSR input vectors are not directly persisted. Reproduction therefore depends on retrieving and running the exact recorded build against the exact dataset.
- **Release:** V0 ROBUSTNESS / RESEARCH-EVIDENCE HARDENING.
- **Smallest safe response:** first write a reconstruction characterization from stored spec and trials at the same build. Add identity fields only for facts that cannot be reconstructed. Do not redesign the research store from inspection alone.
