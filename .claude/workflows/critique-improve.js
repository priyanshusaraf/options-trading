export const meta = {
  name: 'critique-improve',
  description: 'Trader-critique → plan → execute → review loop that hardens one app area (reusable across the app)',
  whenToUse: 'Run on any area of the paper-trader to surface trader-perspective flaws + data-trust issues, implement fixes, and verify. Pass args: {repoRoot, area, files, concerns, testCmd, forbidden}.',
  phases: [
    { title: 'Critique' },
    { title: 'Plan' },
    { title: 'Execute' },
    { title: 'Review' },
  ],
}

// ── inputs (parameterised so the same workflow runs anywhere) ───────────────
const A = args || {}
const REPO = A.repoRoot || '/Users/priyanshusaraf/Desktop/options-trading'
const AREA = A.area || 'the targeted area'
const FILES = (A.files || []).join('\n  - ')
const CONCERNS = A.concerns || '(none supplied)'
const TEST_CMD = A.testCmd || `cd ${REPO}/paper-trader/backend && .venv/bin/python -m pytest -q`
const TYPECHECK = A.typecheck || `cd ${REPO}/paper-trader/frontend && npm run typecheck`
const FORBIDDEN = A.forbidden || [
  'app/strategy/signals.py (frozen strategy math)',
  'the live-execution path: live_broker.py, order_executor.py, kite_order_client.py, live_kite.py, gtt.py',
  'the SafePaperKite barrier (providers/safe_kite.py)',
].join('; ')

const CONTEXT = `
REPO ROOT: ${REPO}
AREA UNDER REVIEW: ${AREA}
KEY FILES:
  - ${FILES}
OWNER'S STATED CONCERNS (treat as ground truth to investigate, not assume):
${CONCERNS}

HARD CONSTRAINTS (apply to every agent):
- Paper-only platform. Do NOT touch: ${FORBIDDEN}.
- Keep ALL existing tests green; ADD tests for new/changed behaviour. Never delete tests to make them pass.
- Do NOT git commit or git push — the human reviews the diff and commits.
- Backend tests: \`${TEST_CMD}\`. Frontend typecheck: \`${TYPECHECK}\`.
- This is money-adjacent research tooling; correctness and honest metrics matter more than features.
`

// ── structured-output schemas ───────────────────────────────────────────────
const FINDINGS_SCHEMA = {
  type: 'object', additionalProperties: false,
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false,
        properties: {
          id: { type: 'string' },
          severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low'] },
          problem: { type: 'string' },
          evidence: { type: 'string', description: 'file:line or concrete repro' },
          trader_impact: { type: 'string' },
          suggested_fix: { type: 'string' },
        },
        required: ['id', 'severity', 'problem', 'evidence', 'suggested_fix'],
      },
    },
  },
  required: ['findings'],
}

const PLAN_SCHEMA = {
  type: 'object', additionalProperties: false,
  properties: {
    methodology_decisions: { type: 'array', items: { type: 'string' } },
    changes: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false,
        properties: {
          id: { type: 'string' },
          title: { type: 'string' },
          files: { type: 'array', items: { type: 'string' } },
          what: { type: 'string' },
          why: { type: 'string' },
          risk: { type: 'string', enum: ['low', 'medium', 'high'] },
          test: { type: 'string' },
        },
        required: ['id', 'title', 'what', 'test'],
      },
    },
    out_of_scope: { type: 'array', items: { type: 'string' } },
  },
  required: ['changes'],
}

const EXEC_SCHEMA = {
  type: 'object', additionalProperties: false,
  properties: {
    summary: { type: 'string' },
    files_changed: { type: 'array', items: { type: 'string' } },
    tests_added: { type: 'array', items: { type: 'string' } },
    tests_pass: { type: 'boolean' },
    test_output_tail: { type: 'string' },
    notes: { type: 'string' },
    follow_ups: { type: 'array', items: { type: 'string' } },
  },
  required: ['summary', 'files_changed', 'tests_pass'],
}

const REVIEW_SCHEMA = {
  type: 'object', additionalProperties: false,
  properties: {
    verdict: { type: 'string', enum: ['pass', 'fail'] },
    tests_pass: { type: 'boolean' },
    typecheck_pass: { type: 'boolean' },
    issues: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false,
        properties: { severity: { type: 'string' }, desc: { type: 'string' }, file: { type: 'string' } },
        required: ['severity', 'desc'],
      },
    },
    remaining_critiques: { type: 'array', items: { type: 'string' } },
  },
  required: ['verdict', 'tests_pass'],
}

// ── phase 1: critique (trader) + data validity (dev), in parallel ──────────
phase('Critique')
const [traderCrit, dataCrit] = await parallel([
  () => agent(`${CONTEXT}

ROLE: a sharp, skeptical options TRADER reviewing "${AREA}". You do not trust the
software yet. Read the actual code + UI and enumerate everything that would make a
trader distrust or misread this tool. Be concrete and evidence-backed (file:line).
Cover at least: capital sizing / position notional vs the stated ₹50,000 base;
whether returns/metrics are honest given that sizing; the backtest lookback period
(how far back, and is it consistent across timeframes?); whether results can show
losers at all or only winners (and WHY); missing controls a trader needs (date
ranges, instrument selection, biggest winners/losers); and any place a number could
mislead. Read the repo; don't speculate. Return findings.`,
    { label: 'trader-critic', phase: 'Critique', schema: FINDINGS_SCHEMA }),

  () => agent(`${CONTEXT}

ROLE: a DATA-VALIDITY engineer. Determine whether the data flowing through "${AREA}"
can be trusted, especially data from Zerodha Kite. Investigate with evidence:
(1) the "no losing instruments in the results" anomaly — is it a sizing artifact, a
filter/sort default, cache reuse, silent skipping of errors, or real? Trace it.
(2) candle handling: the drop of the last (still-forming) bar, timezone, gaps,
holidays, and the per-interval lookback (MAX_DAYS) — does each timeframe silently
use a different history length?
(3) whether quantities/notional are computed correctly and consistently.
(4) any silent failure path (instruments that error/insufficient-history get hidden).
Read the code in app/backtest/ and providers/kite.py. Return findings with concrete
evidence and the fix each needs.`,
    { label: 'data-validity', phase: 'Critique', schema: FINDINGS_SCHEMA }),
])

const findings = [traderCrit, dataCrit].filter(Boolean).flatMap((c) => c.findings || [])
log(`critique: ${findings.length} findings (${findings.filter((f) => ['critical', 'high'].includes(f.severity)).length} critical/high)`)

// ── phase 2: plan (trader + dev synthesis) ──────────────────────────────────
phase('Plan')
const plan = await agent(`${CONTEXT}

ROLE: a trader-minded tech lead. Turn the findings below into a CONCRETE, ordered
implementation plan for "${AREA}". Decide the methodology questions explicitly
(especially: how to size positions so results never imply deploying more than the
stated capital, and how to compute honest returns; and how the backtest lookback /
date range should work). Then list discrete code changes (file + what + why + the
test that proves it). Also deliver the owner's requested features for this area:
selectable preset ranges (1w/2w/1m/3m/6m/1y/3y/7y/10y/entire history) AND a custom
date-range panel; the ability to pick specific instruments to backtest (e.g. only
GOLD/SILVER/COPPER); a results view that shows biggest winning & losing trades; and
ensure losers actually appear when real. Keep changes minimal, correct, and tested;
nothing outside ${AREA}. Mark anything you deliberately defer as out_of_scope.

FINDINGS:
${JSON.stringify(findings, null, 2)}`,
  { label: 'planner', phase: 'Plan', schema: PLAN_SCHEMA })

log(`plan: ${plan?.changes?.length || 0} changes; methodology: ${(plan?.methodology_decisions || []).length} decisions`)

// ── phase 3+4: execute → review, re-critique after each round (till dry) ─────
const MAX_ROUNDS = 3
const seen = new Set()
let round = 0
let currentChanges = plan?.changes || []
let lastExec = null
let lastReview = null
const history = []

while (round < MAX_ROUNDS && currentChanges.length) {
  round += 1

  phase('Execute')
  lastExec = await agent(`${CONTEXT}

ROLE: a careful DEVELOPER. Implement EXACTLY the changes below in the repo working
tree — no more, no less. Add/extend tests for every behavioural change and RUN the
test command; if anything fails, fix it before returning. Run the frontend typecheck
if you touched the frontend. Do NOT commit or push. Honest metrics over flashy ones.

CHANGES TO IMPLEMENT (round ${round}):
${JSON.stringify(currentChanges, null, 2)}

METHODOLOGY DECISIONS to honour:
${JSON.stringify(plan?.methodology_decisions || [], null, 2)}`,
    { label: `execute-r${round}`, phase: 'Execute', schema: EXEC_SCHEMA })

  log(`round ${round} execute: ${(lastExec?.files_changed || []).length} files, tests_pass=${lastExec?.tests_pass}`)

  phase('Review')
  lastReview = await agent(`${CONTEXT}

ROLE: a strict CODE REVIEWER. Review the uncommitted changes for "${AREA}"
(\`cd ${REPO} && git diff\` and \`git status\`). Independently RUN the backend test
command and (if the frontend changed) the typecheck, and report their real results.
Verify: the implemented changes actually do what was planned; capital sizing /
returns are now honest and never imply over-deploying capital; losers appear when
real; no regression elsewhere; no forbidden files were touched; new behaviour is
tested. Give a verdict (pass only if tests pass AND no critical/high issue remains).

What the executor reported:
${JSON.stringify(lastExec, null, 2)}`,
    { label: `review-r${round}`, phase: 'Review', schema: REVIEW_SCHEMA })

  // re-critique (trader) on the now-improved code — the "keep criticising till dry" loop
  const recrit = await agent(`${CONTEXT}

ROLE: the skeptical TRADER again, re-examining "${AREA}" AFTER round ${round}'s
changes. Has anything you'd distrust survived, or did the changes introduce new
problems? Only report genuinely actionable issues (no nitpicks). If it's now
trustworthy and complete for a trader, return an empty findings list.`,
    { label: `recritique-r${round}`, phase: 'Critique', schema: FINDINGS_SCHEMA })

  const fresh = (recrit?.findings || []).filter(
    (f) => ['critical', 'high'].includes(f.severity) && !seen.has(f.problem))
  fresh.forEach((f) => seen.add(f.problem))

  const reviewIssues = (lastReview?.issues || []).filter(
    (i) => ['critical', 'high'].includes((i.severity || '').toLowerCase()))
  const blocking = lastReview?.verdict === 'fail' || !lastReview?.tests_pass || reviewIssues.length > 0

  history.push({ round, exec: lastExec, review: lastReview, fresh_critiques: fresh, review_issues: reviewIssues })
  log(`round ${round}: verdict=${lastReview?.verdict} tests=${lastReview?.tests_pass} blocking=${blocking} fresh=${fresh.length}`)

  if (!blocking && fresh.length === 0) break  // dry — can't critique it further

  if (round < MAX_ROUNDS) {
    phase('Plan')
    const rep = await agent(`${CONTEXT}

ROLE: trader-minded tech lead. Produce the NEXT round of concrete changes for
"${AREA}" that resolve the review issues and the fresh trader critiques below.
Only actionable, tested changes; keep scope tight.

REVIEW ISSUES (must fix):
${JSON.stringify(reviewIssues, null, 2)}
FRESH TRADER CRITIQUES:
${JSON.stringify(fresh, null, 2)}`,
      { label: `replan-r${round}`, phase: 'Plan', schema: PLAN_SCHEMA })
    currentChanges = rep?.changes || []
  }
}

return {
  area: AREA,
  critique: { count: findings.length, findings },
  plan,
  rounds: history,
  final_review: lastReview,
  final_exec: lastExec,
}
