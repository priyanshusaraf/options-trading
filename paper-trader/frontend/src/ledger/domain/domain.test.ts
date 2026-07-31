/* Tests for the three pieces of logic the whole product rests on:
 *   · the metrics engine and its sample-size discipline  (§0.5, §5.7)
 *   · the ticket grammar                                  (§9.6)
 *   · the query language                                  (§6.4)
 *
 * These are the parts where a silent error would produce a journal that lies,
 * which §3.2 treats as the failure mode to design against.
 */

import { describe, expect, it } from 'vitest'
import {
  EVIDENCE_N,
  adherenceSplit,
  captureForAggregate,
  captureRatio,
  decisionOutcome,
  evidenceState,
  exitQuality,
  ledger,
  maxDrawdown,
  netPnl,
  proportion,
  realisedR,
  riskPerR,
  stat,
  teachingTrades,
} from './metrics'
import { parseTicket } from './ticketGrammar'
import { parseQuery, runQuery, serialiseQuery, withTerm } from './query'
import { parseDateExpression, suggestedMode, weekStart } from './dates'
import type { Instrument, PlaybookEntry, Trade } from './types'

// ── Fixtures ──────────────────────────────────────────────────────────────

const inst: Instrument = {
  id: 'bnf', code: 'BNF', name: 'Bank Nifty', kind: 'index-fno',
  lotSize: 15, tick: 0.05, hours: { open: '09:15', close: '15:30' },
  order: 0, rBasis: 'initial-stop',
}

const fixedInst: Instrument = {
  ...inst, id: 'cl', code: 'CL', rBasis: 'fixed-rupee', fixedRisk: 5000,
}

let seq = 0
function trade(over: Partial<Trade> = {}): Trade {
  seq += 1
  const entry = over.legs?.[0]?.price ?? 100
  return {
    id: `t${seq}`, instrumentId: 'bnf', sessionId: 'bnf|2026-07-29',
    date: '2026-07-29', direction: 'long', contract: 'FUT',
    qty: 10,
    legs: [
      { id: 'l1', at: 1, side: 'entry', price: entry, qty: 10, fees: 0 },
      { id: 'l2', at: 2, side: 'exit', price: entry + 10, qty: 10, fees: 0 },
    ],
    openedAt: 1, closedAt: 2,
    entryNote: '', entryNoteLockedAt: 1, confidence: 3,
    plannedStop: entry - 10,
    setupId: 'pb_orb', offBook: false, regime: 'expansion',
    grade: 'A', takeAgain: true, executionScore: 8,
    exitNote: '', lesson: '', mistakes: [], emotions: [],
    mfeR: 2, maeR: -0.3, mfeSource: 'manual',
    tags: [], artifactIds: [], autoTags: [],
    createdAt: 1, updatedAt: 2, deletedAt: null,
    ...over,
  }
}

// ── R ─────────────────────────────────────────────────────────────────────

describe('R is defined by exactly one thing per instrument (§11.2)', () => {
  it('derives 1R from the initial stop', () => {
    // entry 100, stop 90 → 10 points × 10 qty = ₹100 of risk.
    expect(riskPerR(trade(), inst)).toBe(100)
  })

  it('returns +1R when the trade makes exactly its risk', () => {
    expect(realisedR(trade(), inst)).toBeCloseTo(1)
  })

  it('is null when the stop is missing, rather than guessing', () => {
    // A trade with no stop has no R under this basis. Inventing one is how a
    // journal starts lying.
    expect(realisedR(trade({ plannedStop: undefined }), inst)).toBeNull()
  })

  it('uses fixed rupee risk when the instrument says so', () => {
    const t = trade({ instrumentId: 'cl', plannedStop: undefined })
    expect(riskPerR(t, fixedInst)).toBe(5000)
    // ₹100 profit against ₹5000 of risk.
    expect(realisedR(t, fixedInst)).toBeCloseTo(0.02)
  })

  it('nets fees out of P&L before computing R', () => {
    const t = trade({
      legs: [
        { id: 'a', at: 1, side: 'entry', price: 100, qty: 10, fees: 20 },
        { id: 'b', at: 2, side: 'exit', price: 110, qty: 10, fees: 30 },
      ],
    })
    expect(netPnl(t)).toBe(50)
    expect(realisedR(t, inst)).toBeCloseTo(0.5)
  })

  it('signs short trades correctly', () => {
    const t = trade({
      direction: 'short',
      plannedStop: 110,
      legs: [
        { id: 'a', at: 1, side: 'entry', price: 100, qty: 10, fees: 0 },
        { id: 'b', at: 2, side: 'exit', price: 90, qty: 10, fees: 0 },
      ],
    })
    expect(realisedR(t, inst)).toBeCloseTo(1)
  })

  it('leaves open trades without an R', () => {
    const t = trade({ closedAt: null, legs: [
      { id: 'a', at: 1, side: 'entry', price: 100, qty: 10, fees: 0 },
    ] })
    expect(realisedR(t, inst)).toBeNull()
  })
})

// ── The sample-size discipline ────────────────────────────────────────────

describe('statistics carry their own error bars (§0.5, §5.7)', () => {
  it('marks anything below the threshold as insufficient', () => {
    expect(evidenceState(19)).toBe('insufficient')
    expect(evidenceState(20)).toBe('provisional')
    expect(evidenceState(40)).toBe('evidence')
    expect(EVIDENCE_N).toBe(20)
  })

  it('still computes the value, so the UI decides what to hide', () => {
    const s = stat([1, 2, 3])
    expect(s.value).toBeCloseTo(2)
    expect(s.n).toBe(3)
    expect(s.state).toBe('insufficient')
  })

  it('gives a zero interval at n=1 rather than a misleading one', () => {
    expect(stat([1.5]).ci).toBe(0)
  })

  it('widens the interval as variance grows', () => {
    const tight = stat(Array.from({ length: 30 }, () => 1))
    const loose = stat(Array.from({ length: 30 }, (_, i) => (i % 2 ? 5 : -3)))
    expect(loose.ci).toBeGreaterThan(tight.ci)
  })

  it('uses a Wilson interval for proportions, which stays inside [0,1]', () => {
    const p = proportion(1, 3)
    expect(p.value).toBeCloseTo(1 / 3)
    expect(p.value - p.ci).toBeGreaterThan(-1)
    expect(p.ci).toBeGreaterThan(0)
  })

  it('reports an empty sample as insufficient, not as zero', () => {
    const s = stat([])
    expect(s.n).toBe(0)
    expect(s.state).toBe('insufficient')
  })
})

// ── Capture and exit quality ──────────────────────────────────────────────

describe('capture % (§5.4) and its aggregate', () => {
  it('reads realised R ÷ MFE R for a single trade', () => {
    expect(captureRatio(trade({ mfeR: 2 }), inst)).toBeCloseTo(0.5)
  })

  it('is negative for a trade that went green and then lost', () => {
    const t = trade({
      mfeR: 2,
      plannedStop: 90,
      legs: [
        { id: 'a', at: 1, side: 'entry', price: 100, qty: 10, fees: 0 },
        { id: 'b', at: 2, side: 'exit', price: 90, qty: 10, fees: 0 },
      ],
    })
    expect(captureRatio(t, inst)).toBeCloseTo(-0.5)
  })

  it('excludes losers from the aggregate so one does not swamp the mean', () => {
    // The bug this guards: a loser with a tiny MFE yields a capture near −20,
    // which drags an otherwise healthy average to nonsense.
    const tinyMfeLoser = trade({
      mfeR: 0.05,
      plannedStop: 90,
      legs: [
        { id: 'a', at: 1, side: 'entry', price: 100, qty: 10, fees: 0 },
        { id: 'b', at: 2, side: 'exit', price: 90, qty: 10, fees: 0 },
      ],
    })
    expect(captureRatio(tinyMfeLoser, inst)).toBeLessThan(-10)
    expect(captureForAggregate(tinyMfeLoser, inst)).toBeNull()

    const q = exitQuality([trade({ mfeR: 2 }), tinyMfeLoser], inst, 1)
    expect(q.capture.value).toBeCloseTo(0.5)
    expect(q.capture.value).toBeGreaterThan(0)
  })

  it('still counts what losers gave back, where it cannot be averaged away', () => {
    const gaveItBack = trade({
      mfeR: 2,
      plannedStop: 90,
      legs: [
        { id: 'a', at: 1, side: 'entry', price: 100, qty: 10, fees: 0 },
        { id: 'b', at: 2, side: 'exit', price: 90, qty: 10, fees: 0 },
      ],
    })
    const q = exitQuality([gaveItBack], inst, 1)
    // MFE +2R, realised −1R → 3R handed back.
    expect(q.gaveBack.value).toBeCloseTo(3)
  })
})

// ── Ledgers ───────────────────────────────────────────────────────────────

describe('the two ledgers stay separate (§0.2)', () => {
  const trades = [
    trade({ grade: 'A', takeAgain: true }),
    trade({ grade: 'F', takeAgain: false, offBook: true, autoTags: ['off-book'] }),
  ]

  it('never folds process metrics into money metrics', () => {
    const l = ledger(trades, inst, 1)
    expect(l.expectancy.value).toBeCloseTo(1)
    expect(l.adherence.value).toBeCloseTo(0.5)
    expect(l.takeAgainRate.value).toBeCloseTo(0.5)
    expect(l.goodGradeRate.value).toBeCloseTo(0.5)
  })

  it('excludes soft-deleted trades from every aggregate', () => {
    const l = ledger([...trades, trade({ deletedAt: 1 })], inst, 1)
    expect(l.count).toBe(2)
  })

  it('computes max drawdown over the cumulative R path', () => {
    expect(maxDrawdown([1, 1, -3, 1])).toBeCloseTo(-3)
    expect(maxDrawdown([1, 1, 1])).toBe(0)
  })

  it('splits adherence so off-book can be judged on its own record', () => {
    const a = adherenceSplit(trades, inst, 1)
    expect(a.inBook.n).toBe(1)
    expect(a.offBook.n).toBe(1)
  })
})

describe('decision × outcome separates skill from luck (§5.7)', () => {
  const loser = (over: Partial<Trade> = {}) =>
    trade({
      plannedStop: 90,
      legs: [
        { id: 'a', at: 1, side: 'entry', price: 100, qty: 10, fees: 0 },
        { id: 'b', at: 2, side: 'exit', price: 90, qty: 10, fees: 0 },
      ],
      ...over,
    })

  it('puts each trade in exactly one quadrant', () => {
    const q = decisionOutcome(
      [trade({ grade: 'A' }), loser({ grade: 'A' }), trade({ grade: 'D' }), loser({ grade: 'F' })],
      inst,
    )
    expect(q.goodWin).toHaveLength(1)
    expect(q.goodLoss).toHaveLength(1)
    expect(q.badWin).toHaveLength(1)
    expect(q.badLoss).toHaveLength(1)
  })

  it('sets ungraded trades aside rather than assuming a grade', () => {
    const q = decisionOutcome([trade({ grade: null })], inst)
    expect(q.ungraded).toHaveLength(1)
    expect(q.goodWin).toHaveLength(0)
  })

  it('finds the worst-graded winner and best-graded loser (§2.5)', () => {
    const t = teachingTrades(
      [trade({ grade: 'D' }), trade({ grade: 'A' }), loser({ grade: 'A' }), loser({ grade: 'F' })],
      inst,
    )
    expect(t.worstGradedWinner?.grade).toBe('D')
    expect(t.bestGradedLoser?.grade).toBe('A')
  })
})

// ── Ticket grammar ────────────────────────────────────────────────────────

const playbook: PlaybookEntry[] = [
  {
    id: 'pb_orb', shortcut: 1, code: 'orb', name: 'ORB', instrumentIds: [],
    definition: '', entryTrigger: '', invalidation: '', typicalR: 1,
    regimes: [], createdAt: 0, revisions: [], archived: false,
  },
]

const ctx = {
  instruments: [inst, fixedInst],
  playbook,
  defaultInstrumentId: 'bnf',
  defaultQty: 15,
  emotions: ['calm', 'fomo'],
}

describe('the ticket grammar (§9.6)', () => {
  it('parses the documented example', () => {
    const p = parseTicket('bnf 52200ce b 60 @248.5 orb c4 fomo', ctx)
    expect(p).toMatchObject({
      instrumentId: 'bnf',
      strike: 52200,
      optionType: 'CE',
      contract: 'OPT',
      direction: 'long',
      qty: 60,
      price: 248.5,
      setupId: 'pb_orb',
      confidence: 4,
      emotion: 'fomo',
    })
    expect(p.missing).toEqual([])
    expect(p.ambiguous).toEqual([])
  })

  it('is order-tolerant, because typing under pressure is not orderly', () => {
    const a = parseTicket('b bnf 60 @248.5 orb c4', ctx)
    const b = parseTicket('bnf b @248.5 60 c4 orb', ctx)
    expect(a.direction).toBe(b.direction)
    expect(a.qty).toBe(b.qty)
    expect(a.price).toBe(b.price)
    expect(a.setupId).toBe(b.setupId)
  })

  it('falls back to workspace defaults for anything omitted', () => {
    const p = parseTicket('b @100 orb c3', ctx)
    expect(p.instrumentId).toBe('bnf')
    expect(p.qty).toBe(15)
    expect(p.contract).toBe('FUT')
  })

  it('reports what is missing instead of inventing it', () => {
    const p = parseTicket('bnf 60', ctx)
    expect(p.missing).toContain('direction')
    expect(p.missing).toContain('price')
    expect(p.missing).toContain('setup')
    expect(p.missing).toContain('confidence')
  })

  it('flags an ambiguous second number rather than guessing a price', () => {
    const p = parseTicket('bnf b 60 248 orb c4', ctx)
    expect(p.ambiguous).toHaveLength(1)
    expect(p.ambiguous[0].text).toBe('248')
    // The span is reported so the UI can highlight that exact token.
    expect(p.ambiguous[0].to).toBeGreaterThan(p.ambiguous[0].from)
  })

  it('treats 0 as off-book, which is itself tracked (§0.4)', () => {
    const p = parseTicket('bnf b 60 @100 0 c3', ctx)
    expect(p.offBook).toBe(true)
    expect(p.setupId).toBeNull()
    expect(p.missing).not.toContain('setup')
  })

  it('addresses the playbook shortlist by position', () => {
    expect(parseTicket('bnf b 60 @100 1 c3', ctx).setupId).toBe('pb_orb')
  })

  it('reads the stop, which is what defines 1R on a stop basis', () => {
    const p = parseTicket('bnf b 60 @248.5 x240 t260 orb c4', ctx)
    expect(p.stop).toBe(240)
    expect(p.target).toBe(260)
  })

  it('parses put strikes', () => {
    const p = parseTicket('bnf 24500pe s 75 @100 orb c2', ctx)
    expect(p.optionType).toBe('PE')
    expect(p.direction).toBe('short')
  })
})

// ── Query language ────────────────────────────────────────────────────────

const qctx = {
  instruments: [inst, fixedInst],
  setupCode: (id: string | null) => (id ? 'orb' : 'off-book'),
  haystack: (t: Trade) => `${t.entryNote} ${t.lesson}`,
}

describe('the query language (§6.4)', () => {
  const rows = [
    trade({ grade: 'A', mistakes: ['early-exit'], confidence: 5 }),
    trade({ grade: 'C', offBook: true, setupId: null, confidence: 2 }),
    trade({
      grade: 'B', date: '2026-05-04', confidence: 4,
      plannedStop: 90,
      legs: [
        { id: 'a', at: 1, side: 'entry', price: 100, qty: 10, fees: 0 },
        { id: 'b', at: 2, side: 'exit', price: 90, qty: 10, fees: 0 },
      ],
    }),
  ]

  it('filters on field:value', () => {
    expect(runQuery('grade:A', rows, qctx)).toHaveLength(1)
  })

  it('supports comparators on R', () => {
    expect(runQuery('r:>0', rows, qctx)).toHaveLength(2)
    expect(runQuery('r:<0', rows, qctx)).toHaveLength(1)
  })

  it('supports ranges', () => {
    expect(runQuery('conf:4..5', rows, qctx)).toHaveLength(2)
  })

  it('negates with a leading dash', () => {
    expect(runQuery('-mistake:early-exit', rows, qctx)).toHaveLength(2)
  })

  it('ORs within a group and ANDs across groups', () => {
    expect(runQuery('grade:A or grade:C', rows, qctx)).toHaveLength(2)
    expect(runQuery('grade:A or grade:C r:>0', rows, qctx)).toHaveLength(2)
    expect(runQuery('grade:B r:>0', rows, qctx)).toHaveLength(0)
  })

  it('filters on a month prefix and a quarter', () => {
    expect(runQuery('date:2026-05', rows, qctx)).toHaveLength(1)
    expect(runQuery('date:2026-q3', rows, qctx)).toHaveLength(2)
  })

  it('treats off-book as a queryable behaviour', () => {
    expect(runQuery('offbook:yes', rows, qctx)).toHaveLength(1)
  })

  it('returns everything for an empty query', () => {
    expect(runQuery('', rows, qctx)).toHaveLength(3)
  })

  it('round-trips through the serialiser, so facet clicks are lossless', () => {
    const q = 'setup:orb r:>1 -mistake:early-exit'
    expect(serialiseQuery(parseQuery(q))).toBe(q)
  })

  it('toggles a facet off when clicked twice', () => {
    const once = withTerm('', 'grade', 'A')
    expect(once).toBe('grade:A')
    expect(withTerm(once, 'grade', 'A')).toBe('')
  })
})

// ── Dates and the mode engine ─────────────────────────────────────────────

describe('the per-instrument mode engine (§2.1)', () => {
  it('suggests Live inside the session and Review after the close', () => {
    const at = (h: number, m = 0) => new Date(2026, 6, 29, h, m)
    expect(suggestedMode(inst, at(8))).toBe('prep')
    expect(suggestedMode(inst, at(11))).toBe('live')
    expect(suggestedMode(inst, at(16))).toBe('review')
  })

  it('lets one instrument be Live while another is in Review', () => {
    const mcx: Instrument = { ...inst, hours: { open: '09:00', close: '23:30' } }
    const at = new Date(2026, 6, 29, 21, 0)
    expect(suggestedMode(inst, at)).toBe('review')
    expect(suggestedMode(mcx, at)).toBe('live')
  })
})

describe('palette date expressions (§4.3)', () => {
  it('understands the documented forms', () => {
    expect(parseDateExpression('yesterday', '2026-07-29')).toBe('2026-07-28')
    expect(parseDateExpression('2026-06', '2026-07-29')).toBe('2026-06-01')
    expect(parseDateExpression('june', '2026-07-29')).toBe('2026-06-01')
    expect(parseDateExpression('2026-07-01', '2026-07-29')).toBe('2026-07-01')
  })

  it('resolves "last thu" to the most recent Thursday', () => {
    // 29 Jul 2026 is a Wednesday, so last Thursday is the 23rd.
    expect(parseDateExpression('last thu', '2026-07-29')).toBe('2026-07-23')
  })

  it('returns null rather than a wrong date', () => {
    expect(parseDateExpression('sometime')).toBeNull()
  })

  it('starts weeks on Monday for the weekly review', () => {
    expect(weekStart('2026-07-29')).toBe('2026-07-27')
  })
})
