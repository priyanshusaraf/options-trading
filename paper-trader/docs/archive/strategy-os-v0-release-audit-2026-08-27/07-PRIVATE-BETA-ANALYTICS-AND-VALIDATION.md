# Private-beta analytics and validation

## Validation thesis

V0 tests whether users can express a strategy, produce research they trust, reject
fragile ideas, monitor the accepted version and learn from signals. It does not test
whether Strategy OS can place orders.

## Founding cohort

- 5–15 invited Indian-market users after Gate B.
- Founder-assisted onboarding and recorded consent for observation/telemetry.
- Separate retail/research users from eventual professional/B2B requirements.
- Weekly cohort review; no public performance marketing.
- ₹500/month is a willingness-to-pay experiment only after Gate C, not a readiness
  substitute.

## Minimum event model

| Event | Required dimensions | Prohibited content |
| --- | --- | --- |
| signup/session | pseudonymous owner, stage, outcome, duration | password/token/PII beyond approved IDs |
| Zerodha connect | connection role, attempt/outcome/reason, expiry/reconnect | API key, secret, access token, raw response |
| watchlist create | count, source type, outcome | proprietary full list in general analytics |
| annotation create/lock | type, count, workflow stage, outcome | raw chart/vendor blob |
| builder open/edit/validate | graph size band, operation type, refusal code, duration | full strategy graph/parameters |
| backtest job | bounded workload dimensions, queue/run duration, outcome | full proprietary strategy/data |
| robustness method | method, workload band, conclusion class, outcome | trial payloads outside research ledger |
| monitoring activate | strategy version reference, capability result | provider credential |
| signal emit/view/review | transition class, latency band, review state | sensitive position/account data |
| return/retention | day 1/7/30 pseudonymous cohort | cross-product tracking identifiers |
| frontend/backend failure | build, route/component, typed error | request bodies, tokens, strategies |

The canonical research/evidence ledger stores detailed strategy facts. Product
analytics stores bounded usage facts and references, never a competing truth.

## Funnel metrics

1. Invitation → signup completion.
2. Signup → Zerodha connection completion.
3. Connection → first static watchlist.
4. Watchlist → first locked annotation.
5. Annotation/builder → first valid strategy version.
6. Strategy → first completed reproducible backtest.
7. Backtest → first robustness method.
8. Research → monitoring activation.
9. Activation → first signal viewed/reviewed.
10. Day 1/7/30 return and willingness to pay.

Primary product metrics:

- median time to first valid backtest;
- percentage reproducing a saved result;
- percentage reaching a robustness conclusion;
- percentage activating monitoring;
- signal review rate and useful/noisy/late/data-issue distribution;
- seven-day retained research users;
- failed jobs and support minutes per active user;
- compute/provider cost per active user;
- number of strategies rejected before monitoring.

Do not optimize for signals emitted or strategies promoted. A product that helps a
user reject a bad strategy is working.

## Signal review vocabulary

- acted;
- ignored;
- useful;
- late;
- noisy;
- invalid context;
- wrong regime;
- data issue;
- note.

A review is user-authored and append-only. It never changes the historical signal or
becomes execution truth.

## Founder-assisted workflow

1. Pre-screen user goals, instruments, data rights and strategy horizon.
2. Create account and verify V0 terms/privacy consent.
3. Observe connection and first watchlist.
4. Screen-share one strategy creation and one backtest.
5. Require a robustness conclusion, including “reject.”
6. Activate one monitored strategy only after exact evidence.
7. Review the first signals together.
8. Capture structured friction, bugs and requests.
9. Review telemetry/support/data cost weekly.
10. Promote features only when repeated cohort evidence supports them.

## Success criteria for the founding cohort

- At least half of activated users complete the golden research loop with support.
- The majority of completed results can be reopened and reproduced without founder
  intervention.
- Users can explain why a strategy was accepted or rejected from the product evidence.
- Signal context is understood without implying platform advice.
- Support and compute demands fit the declared beta quotas.
- A meaningful subset returns in week two and voluntarily asks to continue/pay.

These are proposed validation metrics, not statistical proof or commercial promises.
Exact numeric thresholds are an owner decision after the first observed sessions.

## Failure criteria

- Users admire the canvas but do not complete a backtest.
- Results cannot be reproduced or trusted.
- Users bypass robustness work and treat signals as advice.
- Provider/data friction dominates the workflow.
- Support or compute cost makes ₹500 economically incoherent.
- Users need execution more than the research product.
- Users do not return after the founder session.

## Privacy controls

- Explicit event catalogue and retention period.
- Pseudonymous analytics IDs separated from credentials.
- No raw broker payload, secret, strategy graph, chart artifact, portfolio or signal
  context in general analytics.
- User export/delete process.
- Role-bounded internal analytics access and audit trail.
- No analytics agent as canonical truth; no customer-facing AI.
