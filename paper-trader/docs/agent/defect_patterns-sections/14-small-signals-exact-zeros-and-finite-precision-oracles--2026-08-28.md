Reference: [section index](../DEFECT_PATTERNS.md). Read with its scope; this is not a new assignment.

## Small signals, exact zeros and finite-precision oracles — 2026-08-28

- Violated invariant: a small nonzero expected value still needs the accepted
  relative accuracy; positive variance and exact zero variance have distinct masks.
  Large finite coordinates do not excuse a false residual on an exact fitted line.
- Missed assumptions: `b/a-1` loses small returns; subtracting a large fitted price
  loses a small residual. Increasing Decimal precision alone does not make a
  repeating constant ratio's rounded mean exact or guarantee a zero residual at
  extreme coordinates. A high-precision oracle also needs independent identities.
- Reproductions: original assurance F02; the 13 failing near-flat cases recorded
  as F03; 12 constant-window failures in an intermediate correction; four exact
  large-linearity failures in that intermediate correction. These are preserved,
  not replaced by later passing output.
- Correction: stable return/log-return algebra; explicitly isolated Decimal
  context with centering on an observed value; exact rational level-regression
  moments. Keep the same formulas, parameters, float64 state and validity policies.
  Temporary precision work must be included in measured resource declarations.
- Permanent regressions live in `backend/tests/test_indicator_accuracy_core_math.py`:
  complete small-signal arrays through the actual resolver/compiler/runtime,
  hostile arithmetic context, extreme endpoints, constant fractional peer returns,
  constant finite extreme windows, and exact binary-scaled linear levels.
- Seven isolated numerical mutations are detected and exactly restored. The
  immutable original oracle also fails the newly added constant-ratio identity;
  fresh different-owner assurance must independently author that extension rather
  than modify the old package or use it as infallible expected output.
- Exact inheritors: `post-phase5-indicator-accuracy-core-correction-assurance`,
  `post-phase5-indicator-accuracy-recursive-state-assurance`,
  `post-phase5-indicator-accuracy-multi-output-assurance`,
  `post-phase5-indicator-accuracy-session-data-assurance`,
  `post-phase5-indicator-accuracy-remaining-oracles-assurance`,
  `post-phase5-indicator-accuracy-complete-universe-assurance`, and
  `post-phase5-indicator-accuracy-final-review`.
- Evidence: `.agent/runs/post-phase5-indicator-accuracy-core-return-stability-correction/`.

## Shared level moments: rounded means and premature underflow — 2026-08-28

- Violated invariant: positive exact variance must not become undefined because
  intermediate squared float deviations underflow; adjacent representable prices
  must retain the specified covariance, correlation and OLS values.
- Independent F04 reproduction: two increasing adjacent-float pairs produce
  correlation 0.7071 instead of one. Exact binary-scaled y=2x gives false undefined
  masks for correlation, R-squared, hedge slope and adjusted spread.
- Required shared-consumer inspection expanded the proven scope to covariance and
  both time-index regressions. It retained 144 complete-array cases: 76 failed before
  correction, including covariance bias and constant-large finite mean overflow.
  Ownership was amended before those additional formulas changed.
- Minimal correction: exact rational n-scaled level moments, shared with the already
  exact level-regression path; only correlation's final irrational root uses the
  fixed Decimal context. Remove the unused defective float helper after all seven
  consumers are audited. Keep zero-variance masks, covariance ddof, intercept origin,
  correlation sign and all accepted semantics unchanged.
- Permanent actual-consumer tests cover scale-invariant closed forms, adjacent-float
  correlation, covariance mean-error multiplication, time-intercept rounding and
  constant-large validity. Existing numerical/causal/restart and compatibility tests
  remain in force. Four isolated mutants restore rounded moments, remove correlation
  sign, ignore ddof and substitute mean for intercept; each is detected and restored.
- Exact inheritors: `post-phase5-indicator-accuracy-core-level-moment-assurance`,
  `post-phase5-indicator-accuracy-recursive-state-assurance`,
  `post-phase5-indicator-accuracy-multi-output-assurance`,
  `post-phase5-indicator-accuracy-complete-universe-assurance`, and
  `post-phase5-indicator-accuracy-final-review`.
- Evidence: immutable F04 REJECT in
  `.agent/runs/post-phase5-indicator-accuracy-core-correction-assurance/`; correction
  and complete before/after arrays in
  `.agent/runs/post-phase5-indicator-accuracy-core-level-moment-correction/`.
