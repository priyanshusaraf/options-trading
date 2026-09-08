Reference: [section index](../ARCHITECTURE.md). Read with its scope; this is not a new assignment.

## 11. Risk register

**Technical:** import-time DB-engine binding in `app.db.session` (mitigate: research never imports
it; guardrail asserts DB paths differ); SQLite single-writer under a process pool (mitigate: shards
+ single-writer funnel); `fork` inheriting the SQLite fd (mitigate: worker-initializer disposes
engine, pass keys/hashes not objects); cross-process Kite 429/quota (mitigate: token bucket + strict
post-close window); promotion silently falling back to default strategy (mitigate: verify importable
in the running process + alert on fallback).

**Statistical:** N_eff ≈ 2–4 makes breadth weak evidence; multiple-comparisons overfitting;
intraday sample too thin to be confirmatory; survivorship + look-ahead in a *today's-dump* universe;
unmodeled slippage flattering high-turnover edges. Mitigations are the §5 gate stack — and honest
labeling of intraday as hypothesis-generating and daily as survivorship-biased.

**Architectural:** the semantic-primitive layer deferred to M5 means the builder's hardest problem
(the combination grammar) is validated by nothing built earlier — accepted deliberately, designed
when its consumer exists; long-lived-branch drift (mitigate: rebase cadence + structural isolation);
scope creep toward a general research platform (mitigate: "knowledge per unit compute", ruthless YAGNI).

---

*This document will evolve on `feat/research-plane`. Changes to the reuse line (§6) or the capital
guardrails (§0.2) require re-review — they are the load-bearing safety boundaries.*
