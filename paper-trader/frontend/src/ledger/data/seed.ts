/* Seed data.
 *
 * The numbers here are chosen to reproduce the sample figures in the design
 * document — the playbook in §5.6 (ORB n=38, VWAP-rev n=61, Failed-breakout
 * fade n=14, Event fade n=9) and the Bank Nifty session of 29 Jul 2026 shown
 * in §5.1 — so the app opens on the screen the document describes.
 *
 * The n=14 and n=9 setups exist specifically to exercise the `insufficient`
 * evidence state. A journal that only ever shows healthy sample sizes teaches
 * nothing about the discipline the product is built around.
 */

import type {
  Artifact,
  DB,
  Instrument,
  Level,
  MacroEvent,
  NotebookDoc,
  PlaybookEntry,
  RegimeChange,
  SavedQuery,
  Session,
  StreamEvent,
  Trade,
} from '../domain/types'
import { SEED_DOCS, SEED_EMOTIONS, SEED_MISTAKES } from '../domain/taxonomy'
import { addDays, toDateStr, fromDateStr } from '../domain/dates'
import { uid } from '../domain/ids'

/* Deterministic PRNG so the seeded journal is identical on every machine —
   a reproducible demo is worth more than a varied one. */
function rng(seed: number) {
  let s = seed >>> 0
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0
    return s / 4294967296
  }
}

const ANCHOR = '2026-07-29' // the session shown in §5.1

function at(date: string, hh: number, mm: number, ss = 0): number {
  const d = fromDateStr(date)
  d.setHours(hh, mm, ss, 0)
  return d.getTime()
}

// ── Instruments ───────────────────────────────────────────────────────────
// §11.6 Nifty/Bank Nifty/MCX clearly deserve their own workspace; 40 equities
// probably do not — so equities are one workspace with a symbol dimension.

const INSTRUMENTS: Instrument[] = [
  // Lot sizes confirmed by the owner 2026-07-31: NIFTY 65, BANKNIFTY 30.
  // These change by exchange circular and a wrong one silently mis-scales every
  // R figure without erroring — do not "correct" them from memory.
  {
    id: 'nifty', code: 'NIFTY', name: 'Nifty 50', kind: 'index-fno',
    lotSize: 65, tick: 0.05, hours: { open: '09:15', close: '15:30' },
    order: 0, rBasis: 'initial-stop',
  },
  {
    id: 'bnf', code: 'BNF', name: 'Bank Nifty', kind: 'index-fno',
    lotSize: 30, tick: 0.05, hours: { open: '09:15', close: '15:30' },
    order: 1, rBasis: 'initial-stop',
  },
  // The MCX MINI contracts — the bot trades the full-size versions, the owner
  // trades these by hand. All on a fixed-rupee R basis, which means lot size
  // does not enter their R computation; that is deliberate, because the MINI
  // lot sizes here are NOT owner-confirmed.
  {
    id: 'goldm', code: 'GOLDM', name: 'Gold Mini', kind: 'commodity',
    lotSize: 10, tick: 1, hours: { open: '09:00', close: '23:55' },
    order: 2, rBasis: 'fixed-rupee', fixedRisk: 2500,
  },
  {
    id: 'silverm', code: 'SILVERM', name: 'Silver Mini', kind: 'commodity',
    lotSize: 5, tick: 1, hours: { open: '09:00', close: '23:55' },
    order: 3, rBasis: 'fixed-rupee', fixedRisk: 2500,
  },
  {
    id: 'crudem', code: 'CRUDEM', name: 'Crude Oil Mini', kind: 'commodity',
    lotSize: 10, tick: 1, hours: { open: '09:00', close: '23:30' },
    order: 4, rBasis: 'fixed-rupee', fixedRisk: 2500,
  },
  {
    id: 'stocks', code: 'EQ', name: 'Stocks', kind: 'equity',
    lotSize: 1, tick: 0.05, hours: { open: '09:15', close: '15:30' },
    order: 5, rBasis: 'account-pct', accountEquity: 2_500_000, accountRiskPct: 0.5,
  },
]

// ── Playbook ──────────────────────────────────────────────────────────────

const PLAYBOOK: PlaybookEntry[] = [
  {
    id: 'pb_orb', shortcut: 1, code: 'orb', name: 'ORB continuation',
    instrumentIds: ['bnf', 'nifty'],
    definition:
      'Opening range breaks and holds on retest, with the broader index confirming. Continuation, not reversal.',
    entryTrigger: 'Break of 15m opening range high, then acceptance on retest with volume.',
    invalidation: 'Close back inside the opening range.',
    typicalR: 1.8, regimes: ['expansion', 'trending'],
    createdAt: at('2026-01-04', 9, 0), revisions: [
      {
        at: at('2026-04-12', 18, 0), field: 'entryTrigger',
        from: 'Break of 15m opening range high.',
        to: 'Break of 15m opening range high, then acceptance on retest with volume.',
        why: 'Taking the break without the retest was the single biggest source of early-entry tags in Q1.',
      },
    ],
    archived: false,
  },
  {
    id: 'pb_vwap', shortcut: 2, code: 'vwap', name: 'VWAP reversion',
    instrumentIds: ['bnf', 'nifty'],
    definition: 'Extended move away from VWAP in a range regime, faded back toward it.',
    entryTrigger: 'Two standard deviations from VWAP with momentum divergence.',
    invalidation: 'Acceptance beyond the band for more than two 5m bars.',
    typicalR: 1.0, regimes: ['range', 'compression'],
    createdAt: at('2026-01-04', 9, 0), revisions: [], archived: false,
  },
  {
    id: 'pb_fbo', shortcut: 3, code: 'fbo', name: 'Failed breakout fade',
    instrumentIds: ['bnf'],
    definition: 'Break of a well-watched level that fails to find acceptance, faded back into the range.',
    entryTrigger: 'Rejection candle back inside the level within three bars of the break.',
    invalidation: 'Reclaim and hold above the broken level.',
    typicalR: 1.5, regimes: ['range'],
    createdAt: at('2026-05-02', 9, 0), revisions: [], archived: false,
  },
  {
    id: 'pb_event', shortcut: 4, code: 'ev', name: 'Event fade',
    instrumentIds: ['bnf', 'nifty', 'crude'],
    definition: 'The first move after a scheduled event is usually wrong. Fade it once the initial spike stalls.',
    entryTrigger: 'Spike stalls and reverses through the pre-event price.',
    invalidation: 'Continuation beyond the spike extreme.',
    typicalR: 2.2, regimes: ['event-driven'],
    createdAt: at('2026-06-01', 9, 0), revisions: [], archived: false,
  },
  {
    id: 'pb_trend', shortcut: 5, code: 'tp', name: 'Trend pullback',
    instrumentIds: ['crude', 'gold', 'stocks'],
    definition: 'In an established trend, buy the first pullback to a rising average that holds.',
    entryTrigger: 'Pullback holds the 20-period average and reclaims the prior swing.',
    invalidation: 'Close below the pullback low.',
    typicalR: 1.6, regimes: ['trending'],
    createdAt: at('2026-02-10', 9, 0), revisions: [], archived: false,
  },
]

// ── Levels ────────────────────────────────────────────────────────────────
// The ladder from §5.1, with the respect counters the design calls for.

const LEVELS: Level[] = [
  {
    id: 'lv1', instrumentId: 'bnf', price: 52240, type: 'supply',
    source: 'weekly VAH', createdAt: at(addDays(ANCHOR, -3), 15, 30),
    held: 2, broken: 0, active: true,
  },
  {
    id: 'lv2', instrumentId: 'bnf', price: 52180, type: 'supply',
    source: 'prev day high', createdAt: at(addDays(ANCHOR, -1), 15, 30),
    held: 0, broken: 0, active: true,
  },
  {
    id: 'lv3', instrumentId: 'bnf', price: 51960, type: 'demand',
    source: 'gap fill', createdAt: at(addDays(ANCHOR, -6), 15, 30),
    held: 3, broken: 0, active: true,
  },
  {
    id: 'lv4', instrumentId: 'bnf', price: 51700, type: 'demand',
    source: 'monthly pivot', createdAt: at(addDays(ANCHOR, -12), 15, 30),
    held: 1, broken: 1, brokenAt: at(addDays(ANCHOR, -5), 11, 20), active: true,
  },
  {
    id: 'lv5', instrumentId: 'nifty', price: 24580, type: 'supply',
    source: 'prev day high', createdAt: at(addDays(ANCHOR, -2), 15, 30),
    held: 1, broken: 0, active: true,
  },
  {
    id: 'lv6', instrumentId: 'nifty', price: 24380, type: 'demand',
    source: 'weekly VAL', createdAt: at(addDays(ANCHOR, -8), 15, 30),
    held: 2, broken: 0, active: true,
  },
  {
    id: 'lv7', instrumentId: 'crude', price: 6420, type: 'supply',
    source: 'overnight high', createdAt: at(addDays(ANCHOR, -1), 23, 0),
    held: 1, broken: 0, active: true,
  },
]

// ── Regime log ────────────────────────────────────────────────────────────

const REGIME_LOG: RegimeChange[] = [
  {
    id: 'rg1', instrumentId: 'bnf', state: 'range', at: at('2026-03-02', 9, 15),
    note: 'Two weeks of overlapping value. Treating extremes as fades until proven otherwise.',
  },
  {
    id: 'rg2', instrumentId: 'bnf', state: 'compression', at: at('2026-05-18', 9, 15),
    note: 'Daily ranges contracting into the policy meeting. Size down.',
  },
  {
    id: 'rg3', instrumentId: 'bnf', state: 'expansion', at: at('2026-07-24', 9, 15),
    note: 'Range resolved upward on volume. Continuation setups back on, fades off.',
  },
  {
    id: 'rg4', instrumentId: 'nifty', state: 'trending', at: at('2026-06-15', 9, 15),
    note: 'Higher highs and higher lows on the daily for four weeks.',
  },
  {
    id: 'rg5', instrumentId: 'crude', state: 'event-driven', at: at('2026-07-20', 9, 0),
    note: 'Supply headlines dominating. Technicals subordinate to the tape.',
  },
  {
    id: 'rg6', instrumentId: 'gold', state: 'trending', at: at('2026-05-05', 9, 0),
    note: 'Steady bid on real-rate expectations.',
  },
  {
    id: 'rg7', instrumentId: 'stocks', state: 'range', at: at('2026-06-01', 9, 15),
    note: 'Breadth flat. Stock-specific only.',
  },
]

// ── Trade history ─────────────────────────────────────────────────────────
// Generated to land on the sample sizes in §5.6, with the shape of a real
// discretionary record: a strong setup, a marginal one, and two that have not
// earned an opinion yet.

interface Spec {
  setupId: string | null
  offBook: boolean
  instrumentId: string
  n: number
  winRate: number
  avgWin: number
  avgLoss: number
  /** How often the trader actually followed the plan. */
  adherenceQuality: number
}

const SPECS: Spec[] = [
  { setupId: 'pb_orb', offBook: false, instrumentId: 'bnf', n: 26, winRate: 0.47, avgWin: 2.35, avgLoss: -0.92, adherenceQuality: 0.84 },
  { setupId: 'pb_orb', offBook: false, instrumentId: 'nifty', n: 12, winRate: 0.46, avgWin: 2.1, avgLoss: -0.95, adherenceQuality: 0.8 },
  { setupId: 'pb_vwap', offBook: false, instrumentId: 'bnf', n: 38, winRate: 0.58, avgWin: 0.92, avgLoss: -1.02, adherenceQuality: 0.71 },
  { setupId: 'pb_vwap', offBook: false, instrumentId: 'nifty', n: 23, winRate: 0.57, avgWin: 0.88, avgLoss: -1.0, adherenceQuality: 0.7 },
  { setupId: 'pb_fbo', offBook: false, instrumentId: 'bnf', n: 14, winRate: 0.36, avgWin: 1.4, avgLoss: -1.05, adherenceQuality: 0.62 },
  { setupId: 'pb_event', offBook: false, instrumentId: 'bnf', n: 9, winRate: 0.55, avgWin: 2.9, avgLoss: -1.0, adherenceQuality: 0.9 },
  { setupId: 'pb_trend', offBook: false, instrumentId: 'crude', n: 17, winRate: 0.52, avgWin: 1.7, avgLoss: -0.98, adherenceQuality: 0.76 },
  { setupId: 'pb_trend', offBook: false, instrumentId: 'gold', n: 11, winRate: 0.5, avgWin: 1.5, avgLoss: -1.0, adherenceQuality: 0.78 },
  // §5.7 Adherence: the expectancy of off-book trades is a real question.
  // Here they are worse, but not catastrophically — which is the honest shape.
  { setupId: null, offBook: true, instrumentId: 'bnf', n: 16, winRate: 0.38, avgWin: 1.3, avgLoss: -1.15, adherenceQuality: 0.2 },
  { setupId: null, offBook: true, instrumentId: 'nifty', n: 7, winRate: 0.4, avgWin: 1.2, avgLoss: -1.2, adherenceQuality: 0.2 },
]

const MISTAKE_POOL = [
  'early-exit', 'early-entry', 'late-entry', 'moved-stop', 'chased',
  'oversized', 'held-past-invalidation', 'revenge', 'ignored-event',
]

function buildTrades(): { trades: Trade[]; sessions: Map<string, Session> } {
  const rand = rng(20260729)
  const trades: Trade[] = []
  const sessionDates = new Set<string>()

  // Trading days walking back from the anchor, skipping weekends.
  const days: string[] = []
  let cursor = addDays(ANCHOR, -1)
  while (days.length < 130) {
    const dow = fromDateStr(cursor).getDay()
    if (dow !== 0 && dow !== 6) days.push(cursor)
    cursor = addDays(cursor, -1)
  }

  for (const spec of SPECS) {
    for (let i = 0; i < spec.n; i++) {
      // Bias recent trades slightly toward the front of the window so the
      // timeline looks lived-in rather than uniformly sampled.
      const dayIdx = Math.floor(Math.pow(rand(), 1.4) * days.length)
      const date = days[Math.min(dayIdx, days.length - 1)]
      sessionDates.add(`${spec.instrumentId}|${date}`)

      const win = rand() < spec.winRate
      const magnitude = win
        ? spec.avgWin * (0.45 + rand() * 1.35)
        : spec.avgLoss * (0.5 + rand() * 0.9)
      const r = Number(magnitude.toFixed(2))

      const inst = INSTRUMENTS.find((x) => x.id === spec.instrumentId)!
      const hour = 9 + Math.floor(rand() * 6)
      const minute = Math.floor(rand() * 60)
      const openedAt = at(date, Math.min(hour, 15), minute, Math.floor(rand() * 60))
      const holdMin = 8 + Math.floor(rand() * 110)
      const closedAt = openedAt + holdMin * 60000

      const isOption = inst.kind === 'index-fno' && rand() < 0.7
      const base = inst.id === 'bnf' ? 52000 : inst.id === 'nifty' ? 24400
        : inst.id === 'crude' ? 6400 : inst.id === 'gold' ? 72000 : 1450
      const strike = isOption
        ? Math.round((base + (rand() - 0.5) * 600) / 100) * 100
        : undefined
      const direction = rand() < 0.55 ? 'long' : 'short'
      const optionType = isOption
        ? (direction === 'long' ? 'CE' : 'PE') as 'CE' | 'PE'
        : undefined

      // Prices are constructed backwards from the intended R, so the FACT
      // layer is internally consistent: R is always derivable from the fills.
      const entry = isOption
        ? Number((120 + rand() * 220).toFixed(2))
        : Number((base + (rand() - 0.5) * 200).toFixed(2))
      const stopDistance = isOption
        ? Number((entry * (0.18 + rand() * 0.12)).toFixed(2))
        : Number((base * 0.002 * (0.8 + rand() * 0.6)).toFixed(2))
      const qty = inst.lotSize * (1 + Math.floor(rand() * 3))
      const risk = stopDistance * qty
      const feeAmount = Math.round(qty * 0.8)
      const move = (r * risk + feeAmount) / qty
      const sign = direction === 'long' ? 1 : -1
      const exit = Number((entry + sign * move).toFixed(2))
      const stop = Number((entry - sign * stopDistance).toFixed(2))

      const followed = rand() < spec.adherenceQuality
      const grade = followed
        ? (rand() < 0.6 ? 'A' : 'B')
        : (rand() < 0.45 ? 'C' : rand() < 0.8 ? 'D' : 'F')

      const mistakes: string[] = []
      if (!followed) {
        const count = 1 + (rand() < 0.35 ? 1 : 0)
        for (let k = 0; k < count; k++) {
          const pick = MISTAKE_POOL[Math.floor(rand() * MISTAKE_POOL.length)]
          if (!mistakes.includes(pick)) mistakes.push(pick)
        }
      } else if (win && rand() < 0.28) {
        // The most common leak in the product's own thesis: exiting winners
        // early even when the decision was otherwise sound. §5.4
        mistakes.push('early-exit')
      }

      // MFE always dominates realised R for winners; MAE is the heat taken.
      const mfeR = Number(
        (Math.max(r, 0) + (win ? 0.2 + rand() * 1.1 : rand() * 0.7)).toFixed(2),
      )
      const maeR = Number((-(rand() * 0.75)).toFixed(2))

      const emotionAtEntry = followed
        ? (rand() < 0.7 ? 'calm' : 'confident')
        : ['fomo', 'impatient', 'tilt', 'bored'][Math.floor(rand() * 4)]

      trades.push({
        id: uid('tr'),
        instrumentId: spec.instrumentId,
        sessionId: `${spec.instrumentId}|${date}`,
        date,
        direction,
        contract: isOption ? 'OPT' : 'FUT',
        strike,
        optionType,
        qty,
        legs: [
          { id: uid('lg'), at: openedAt, side: 'entry', price: entry, qty, fees: Math.round(feeAmount / 2) },
          { id: uid('lg'), at: closedAt, side: 'exit', price: exit, qty, fees: Math.round(feeAmount / 2) },
        ],
        openedAt,
        closedAt,
        entryNote: followed
          ? 'Setup presented cleanly. Taking it as written in the playbook.'
          : 'Took this without waiting for the trigger. Wanted to be in.',
        entryNoteLockedAt: openedAt,
        confidence: followed
          ? 3 + Math.floor(rand() * 3)
          : 1 + Math.floor(rand() * 4),
        plannedStop: stop,
        plannedTarget: Number((entry + sign * stopDistance * 2).toFixed(2)),
        emotionAtEntry,
        setupId: spec.setupId,
        offBook: spec.offBook,
        regime: null, // resolved against the regime log below
        grade: grade as Trade['grade'],
        takeAgain: followed ? rand() > 0.12 : rand() > 0.72,
        executionScore: followed ? 6 + Math.floor(rand() * 5) : 2 + Math.floor(rand() * 5),
        exitNote: win
          ? 'Closed into strength.'
          : 'Stopped out at the planned level.',
        lesson: mistakes.includes('early-exit')
          ? 'Left R on the table by exiting on a stall rather than the plan.'
          : '',
        mistakes,
        emotions: [emotionAtEntry],
        emotionAtExit: win ? 'calm' : rand() < 0.4 ? 'tilt' : 'calm',
        mfeR,
        maeR,
        mfeSource: 'manual',
        tags: [],
        artifactIds: [],
        autoTags: spec.offBook ? ['off-book'] : [],
        createdAt: openedAt,
        updatedAt: closedAt,
        deletedAt: null,
      })
    }
  }

  // §3.3 Every trade inherits the regime active at its timestamp.
  for (const t of trades) {
    const log = REGIME_LOG.filter((r) => r.instrumentId === t.instrumentId)
      .sort((a, b) => a.at - b.at)
    let state: Trade['regime'] = null
    for (const entry of log) if (entry.at <= t.openedAt) state = entry.state
    t.regime = state
  }

  trades.sort((a, b) => b.openedAt - a.openedAt)
  return { trades, sessions: buildSessions(sessionDates, trades) }
}

const ONE_LINERS = [
  'Wait for the retest. Every single time.',
  'Do not trade the first fifteen minutes on event days.',
  'Size was right today. Keep it there.',
  'Stopped reading the tape and started reacting to it after 13:00.',
  'Two good decisions that lost money. That is fine.',
  'The plan was right and I did not follow it.',
  'Flat is a position.',
]

function buildSessions(keys: Set<string>, trades: Trade[]): Map<string, Session> {
  const rand = rng(4711)
  const map = new Map<string, Session>()
  for (const key of keys) {
    const [instrumentId, date] = key.split('|')
    const dayTrades = trades.filter((t) => t.sessionId === key)
    const hitA = rand() < 0.45
    map.set(key, {
      id: key,
      instrumentId,
      date,
      thesis:
        'Range held overnight. Watching the prior day extremes for acceptance; ' +
        'no trade until one of them is tested and answered.',
      scenarios: [
        {
          id: uid('sc'), letter: 'A', name: 'Break and hold above prior high',
          trigger: 'Acceptance above the prior day high on volume',
          invalidation: 'Close back inside the prior range',
          target: 'Measured move of the overnight range', probability: 0.45,
          status: hitA ? 'hit' : 'invalidated',
          resolvedAt: at(date, 14, 0), paid: hitA && dayTrades.length > 0,
        },
        {
          id: uid('sc'), letter: 'B', name: 'Fade the extremes',
          trigger: 'Rejection at either extreme', invalidation: 'Acceptance beyond it',
          target: 'Back to value', probability: 0.35,
          status: hitA ? 'missed' : 'hit', resolvedAt: at(date, 14, 0),
          paid: !hitA,
        },
        {
          id: uid('sc'), letter: 'C', name: 'Chop, no trade',
          trigger: '', invalidation: '', target: '', probability: 0.2,
          status: dayTrades.length ? 'missed' : 'hit',
          resolvedAt: at(date, 15, 30),
        },
      ],
      risk: { maxTrades: 3, maxLossR: -2, maxConcurrent: 1 },
      lockedAt: at(date, 9, 7, 41),
      appends: [],
      review: {
        reconciled: true,
        oneLineForTomorrow: ONE_LINERS[Math.floor(rand() * ONE_LINERS.length)],
        notes: '',
        completedAt: at(date, 16, 5),
        step: 5,
      },
      createdAt: at(date, 8, 40),
      updatedAt: at(date, 16, 5),
    })
  }
  return map
}

// ── Today's session, exactly as §5.1 renders it ───────────────────────────

function anchorSession(): Session {
  return {
    id: `bnf|${ANCHOR}`,
    instrumentId: 'bnf',
    date: ANCHOR,
    thesis:
      'Gap-up into 52,180 supply. Expecting a failed breakout unless banks carry it. ' +
      'Regime: expansion (set 24 Jul). Yesterday’s high untested.',
    scenarios: [
      {
        id: 'sc_a', letter: 'A', name: 'Failed breakout',
        trigger: '52,180 rejection', invalidation: '52,240 close',
        target: '51,960', probability: 0.45, status: 'pending',
      },
      {
        id: 'sc_b', letter: 'B', name: 'Continuation',
        trigger: '52,180 accept', invalidation: '51,960',
        target: '52,420', probability: 0.35, status: 'pending',
      },
      {
        id: 'sc_c', letter: 'C', name: 'Chop, no trade',
        trigger: 'No acceptance either way by 11:00', invalidation: 'A clean break holds',
        target: '', probability: 0.2, status: 'pending',
      },
    ],
    risk: { maxTrades: 3, maxLossR: -2, maxConcurrent: 1 },
    lockedAt: at(ANCHOR, 9, 7, 41),
    appends: [],
    review: null,
    createdAt: at(ANCHOR, 8, 42),
    updatedAt: at(ANCHOR, 9, 7, 41),
  }
}

function anchorEvents(sessionId: string): StreamEvent[] {
  return [
    {
      id: uid('ev'), sessionId, instrumentId: 'bnf', at: at(ANCHOR, 9, 15, 0),
      kind: 'session-open', text: 'session open', tags: [],
    },
    {
      id: uid('ev'), sessionId, instrumentId: 'bnf', at: at(ANCHOR, 9, 7, 41),
      kind: 'thesis-lock', text: 'thesis locked', tags: [],
    },
    {
      id: uid('ev'), sessionId, instrumentId: 'bnf', at: at(ANCHOR, 9, 18, 2),
      kind: 'screenshot', text: 'screenshot · 5m opening range', tags: [],
    },
    {
      id: uid('ev'), sessionId, instrumentId: 'bnf', at: at(ANCHOR, 9, 21, 14),
      kind: 'observation', text: 'Banks leading, HDFC unusually strong', tags: [],
    },
  ]
}

// §4.4 Quick-captured items land in an Inbox count, and Prep mode's first
// block is "triage inbox".
function inboxEvents(): StreamEvent[] {
  return [
    {
      id: uid('ev'), sessionId: `bnf|${ANCHOR}`, instrumentId: 'bnf',
      at: at(ANCHOR, 8, 12, 0), kind: 'question',
      text: 'Does the ORB setup actually need the index confirming, or is that superstition?',
      tags: [], inbox: true, capturedFrom: 'chart',
    },
    {
      id: uid('ev'), sessionId: `bnf|${ANCHOR}`, instrumentId: 'bnf',
      at: at(ANCHOR, 7, 55, 0), kind: 'observation',
      text: 'US close was strong; Asia following. Gap likely.',
      tags: [], inbox: true, capturedFrom: 'quick-capture',
    },
  ]
}

function buildDocs(): NotebookDoc[] {
  const docs: NotebookDoc[] = []
  for (const inst of INSTRUMENTS) {
    SEED_DOCS.forEach((d, i) => {
      docs.push({
        id: `doc_${inst.id}_${i}`,
        instrumentId: inst.id,
        title: d.title,
        parentId: null,
        order: i,
        body:
          inst.id === 'bnf' && d.title === 'Market opinion'
            ? 'Expansion regime since 24 Jul. The range that defined May and June has resolved upward, ' +
              'and the fades that worked all through compression have stopped working. Until daily ranges ' +
              'contract again, continuation setups get full size and reversion setups get half.\n\n' +
              'What would change my mind: two consecutive closes back inside 51,700–52,240 on falling volume.'
            : inst.id === 'bnf' && d.title === 'Mistakes I keep making'
              ? 'Exiting winners on a momentum stall rather than at the planned level. ' +
                'It has cost more than every other error combined, and it is the only one that ' +
                'does not feel like a mistake at the time.'
              : d.body,
        updatedAt:
          inst.id === 'bnf' && d.title === 'Market opinion'
            ? at('2026-07-24', 18, 0)
            : at('2026-06-01', 9, 0),
        createdAt: at('2026-01-04', 9, 0),
        versions: [],
        backlinks: [],
        seeded: true,
      })
    })
  }
  return docs
}

function buildMacroEvents(): MacroEvent[] {
  return [
    { id: 'me1', date: ANCHOR, time: '11:00', title: 'RBI speak', instrumentIds: ['bnf', 'nifty'], importance: 'high' },
    { id: 'me2', date: ANCHOR, time: '15:30', title: 'US initial claims', instrumentIds: ['bnf', 'nifty'], importance: 'medium' },
    { id: 'me3', date: ANCHOR, time: '20:00', title: 'EIA crude inventories', instrumentIds: ['crude'], importance: 'high' },
    { id: 'me4', date: addDays(ANCHOR, 1), time: '17:30', title: 'US GDP advance', instrumentIds: ['nifty', 'gold'], importance: 'high' },
    { id: 'me5', date: addDays(ANCHOR, 2), time: '11:30', title: 'Monthly F&O expiry', instrumentIds: ['bnf', 'nifty'], importance: 'high' },
  ]
}

function buildSavedQueries(): SavedQuery[] {
  return [
    { id: 'sq1', name: 'Off-book losers', query: 'offbook:yes r:<0', pinned: true, createdAt: Date.now() },
    { id: 'sq2', name: 'Good decision, lost money', query: 'grade:A or grade:B r:<0', pinned: true, createdAt: Date.now() },
    { id: 'sq3', name: 'Early exits this quarter', query: 'mistake:early-exit date:2026-q3', pinned: true, createdAt: Date.now() },
    { id: 'sq4', name: 'Would not take again', query: 'again:no', pinned: false, createdAt: Date.now() },
  ]
}

export function buildSeed(): DB {
  // NOTE: buildTrades() / anchorSession() / inboxEvents() and friends are the
  // demo generators. They are deliberately NOT called — they fabricate ~173
  // trades against instrument ids ('crude', 'gold') this seed no longer ships,
  // so calling them would also throw. They are left in the file rather than
  // deleted because buildDocs() and buildSavedQueries() share helpers with
  // them; nothing else reaches them.

  // A REAL journal, not the demo.
  //
  // The source seeded ~173 generated trades tuned to reproduce the design
  // document's figures — which is right for a demo and poison for a live
  // journal: every statistic would describe fiction. So history ships empty.
  //
  // What must NOT ship empty is `instruments`: uiState's initial route names an
  // instrument, and eight surfaces `return null` when it does not resolve, with
  // no UI anywhere to create one. Same for the playbook (setup attribution is
  // mandatory, so an empty playbook makes every trade off-book) and the mistake
  // and emotion taxonomies.
  //
  // The Research Bench will show `░░░ n=0` everywhere until real trades land.
  // That is the design working, not a bug — no metric renders below the
  // evidence threshold.
  return {
    instruments: INSTRUMENTS,
    sessions: [],
    trades: [],
    events: [],
    levels: [],
    playbook: PLAYBOOK,
    docs: buildDocs(),
    artifacts: [],
    macroEvents: [],
    regimeLog: [],
    savedQueries: buildSavedQueries(),
    periodReviews: [],
    settings: {
      schemaVersion: 1,
      density: 'compact',
      theme: 'dark',
      cvdSafe: false,
      sound: false,
      evidenceThreshold: 20,
      defaultRisk: { maxTrades: 3, maxLossR: -2, maxConcurrent: 1 },
      mistakes: SEED_MISTAKES,
      emotions: SEED_EMOTIONS,
      pnlVisible: true,
    },
  }
}

export const SEED_ANCHOR_DATE = ANCHOR
export { toDateStr }
