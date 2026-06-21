export const meta = {
  name: 'review-engine-monitor',
  description: 'Critique→plan→execute→review of the Engine/Logs + Monitor views (purpose, redundancy vs Home, usefulness)',
  phases: [
    { title: 'Critique' },
    { title: 'Plan' },
    { title: 'Execute' },
    { title: 'Review' },
  ],
}

// Context BAKED IN (a prior run misfired when args didn't propagate), so this
// script always targets the right area regardless of how it's invoked.
const REPO = '/Users/priyanshusaraf/Desktop/options-trading'
const AREA = 'Engine/Logs view + Monitor view (operational screens), and their overlap with the Home page'
const FILES = [
  'paper-trader/frontend/src/views/EngineView.tsx',
  'paper-trader/frontend/src/views/Monitor.tsx',
  'paper-trader/frontend/src/views/HomeView.tsx',
  'paper-trader/frontend/src/components/LogStream.tsx',
  'paper-trader/frontend/src/components/InstrumentTile.tsx',
  'paper-trader/frontend/src/components/TopBar.tsx',
  'paper-trader/frontend/src/state/LiveContext.tsx',
  'paper-trader/backend/app/api/routes.py',
  'paper-trader/backend/app/engine/health.py',
  'paper-trader/backend/app/engine/runner.py',
].join('\n  - ')
const CONCERNS = `1) PURPOSE GAP (most important): the owner does NOT understand what the Engine/Logs
view or the Monitor view are FOR — from a utility standpoint they feel pointless.
For EACH of Engine/Logs and Monitor, determine and state plainly its single distinct
job, whether it is actually useful, and what is confusing or redundant.
2) MERGE QUESTION: the owner thinks the Home page and the Monitor page overlap
heavily and could be MERGED into one screen. Find the genuine distinct use-case for
Home vs Monitor. If there isn't a real one, RECOMMEND a merge and specify exactly
what the single combined screen should contain and which page becomes redundant.
This is high-impact: deliver it as a recommendation for owner approval; do NOT
merge/remove a whole screen in code.
3) Make Engine/Logs genuinely useful: what should a trader actually see about engine
health, the two loops (fast risk lane + slow signal lane), arm/disarm state, the
daily-loss + realized+unrealized drawdown halt status, per-instrument last-scan
times, and recent errors? Right now it feels useless.
4) Surface KITE SESSION health: when the Kite access token expires mid-session,
get_candles/historical_data fails repeatedly with 'Incorrect api_key or
access_token' and the engine only logs per-instrument errors with no clear signal to
the owner. The Engine/Logs view (or a status banner) should clearly show 'Kite
session expired — re-authenticate' instead of burying it. View/health/status layer
ONLY — do NOT touch auth secrets or the live-execution path.
5) PAPER vs REAL clarity: a global broker_mode ('paper'|'live') now exists on the
live snapshot; ensure these operational screens make the active mode obvious where
it matters.`
const TEST_CMD = `cd ${REPO}/paper-trader/backend && .venv/bin/python -m pytest -q`
const TYPECHECK = `cd ${REPO}/paper-trader/frontend && npx tsc --noEmit`
const FORBIDDEN = 'app/strategy/signals.py (frozen strategy math); the live-execution path: live_broker.py, order_executor.py, kite_order_client.py, live_kite.py, gtt.py; the SafePaperKite barrier (providers/safe_kite.py); Kite auth-secret handling; and do NOT merge, remove, or delete any whole screen/view file — structural screen changes must be left as an owner recommendation only'

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
- This is money-adjacent research tooling; correctness and honest UI matter more than features.
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
software yet. Read the ACTUAL code + UI for this area and enumerate everything that
would make a trader confused, mistrustful, or unable to get value from it. Be
concrete and evidence-backed (file:line). For EACH screen/panel in scope, ask:
- PURPOSE: what is the ONE job it does that nothing else does? State it plainly.
- Does it do that job well, or is it cluttered / confusing / misleading?
- REDUNDANCY: does it overlap another screen (same data the owner could see
  elsewhere)? If two screens substantially overlap, say so and which should win.
- MISSING: what essential thing does a trader operating this live actually need here?
Treat the owner's stated concerns above as ground truth to INVESTIGATE (not assume).
Read the repo; don't speculate. Return findings.`,
    { label: 'trader-critic', phase: 'Critique', schema: FINDINGS_SCHEMA }),

  () => agent(`${CONTEXT}

ROLE: a DATA-VALIDITY / correctness engineer. Determine whether what "${AREA}"
shows can be TRUSTED, especially anything sourced from Zerodha Kite. Investigate
with evidence:
(1) Does the displayed data match reality, or can it silently go stale/wrong
    (timezone, last-mark age, dropped/forming bars, websocket vs poll cadence)?
(2) Silent failure paths: are errors (token/session expiry, missing instrument
    tokens, empty responses) hidden from the user or surfaced clearly? Trace any
    anomaly the owner reports to its root cause.
(3) Is engine / health / log / status state reported ACCURATELY — does the screen
    claim match what the engine is actually doing?
Read the relevant code in app/api/, app/engine/, and providers/. Return findings
with concrete evidence and the fix each needs.`,
    { label: 'data-validity', phase: 'Critique', schema: FINDINGS_SCHEMA }),
])

const findings = [traderCrit, dataCrit].filter(Boolean).flatMap((c) => c.findings || [])
log(`critique: ${findings.length} findings (${findings.filter((f) => ['critical', 'high'].includes(f.severity)).length} critical/high)`)

// ── phase 2: plan ───────────────────────────────────────────────────────────
phase('Plan')
const plan = await agent(`${CONTEXT}

ROLE: a trader-minded tech lead. Turn the findings below into a CONCRETE, ordered
implementation plan for "${AREA}", addressing EVERY owner concern explicitly.

HIGH-IMPACT structural changes (merging, removing, or fundamentally redesigning a
whole screen) must NOT be implemented blind — put each as a clear RECOMMENDATION in
methodology_decisions or out_of_scope, stating the genuine distinct use-case (or
lack of one) for each screen so the OWNER can decide. For the safe, clearly
beneficial improvements, list discrete code changes (file + what + why + the test
that proves it). Keep changes minimal, correct, and tested; nothing outside
"${AREA}". Mark anything you deliberately defer as out_of_scope.

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
if you touched the frontend. Do NOT commit or push. Honest UI over flashy.

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
Verify: the implemented changes actually do what was planned; the data shown is
honest and accurate; no regression elsewhere; no forbidden files were touched; NO
high-impact structural change (merging/removing a whole screen) was made without it
being an explicitly-deferred owner recommendation; new behaviour is tested. Give a
verdict (pass only if tests pass AND no critical/high issue remains).

What the executor reported:
${JSON.stringify(lastExec, null, 2)}`,
    { label: `review-r${round}`, phase: 'Review', schema: REVIEW_SCHEMA })

  const recrit = await agent(`${CONTEXT}

ROLE: the skeptical TRADER again, re-examining "${AREA}" AFTER round ${round}'s
changes. Has anything you'd distrust survived, or did the changes introduce new
problems? Only report genuinely actionable issues (no nitpicks). If it's now
trustworthy and clear for a trader, return an empty findings list.`,
    { label: `recritique-r${round}`, phase: 'Critique', schema: FINDINGS_SCHEMA })

  const fresh = (recrit?.findings || []).filter(
    (f) => ['critical', 'high'].includes(f.severity) && !seen.has(f.problem))
  fresh.forEach((f) => seen.add(f.problem))

  const reviewIssues = (lastReview?.issues || []).filter(
    (i) => ['critical', 'high'].includes((i.severity || '').toLowerCase()))
  const blocking = lastReview?.verdict === 'fail' || !lastReview?.tests_pass || reviewIssues.length > 0

  history.push({ round, exec: lastExec, review: lastReview, fresh_critiques: fresh, review_issues: reviewIssues })
  log(`round ${round}: verdict=${lastReview?.verdict} tests=${lastReview?.tests_pass} blocking=${blocking} fresh=${fresh.length}`)

  if (!blocking && fresh.length === 0) break

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
