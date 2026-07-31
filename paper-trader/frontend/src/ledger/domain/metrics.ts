/* The statistics engine — §5.7, §0.5
 *
 * The governing rule of this file: **statistics carry their own error bars.**
 * No metric is ever returned as a bare number. Everything returns a `Stat`,
 * which carries `n`, an interval, and an evidence state. Below the evidence
 * threshold (default n=20) the value is still computed but flagged
 * `insufficient`, and the UI renders `░░░ n=9` with no number at all.
 *
 * This will occasionally annoy the user. It is protecting them from the most
 * expensive mistake in discretionary trading: revising a strategy on nine
 * observations.
 */

import type {
  Grade,
  Instrument,
  RegimeState,
  Trade,
} from './types'

export const EVIDENCE_N = 20

export type EvidenceState = 'evidence' | 'provisional' | 'insufficient'

export interface Stat {
  value: number
  n: number
  /** Half-width of the 95% interval. Zero when n < 2. */
  ci: number
  state: EvidenceState
  unit?: string
}

export function evidenceState(n: number, threshold = EVIDENCE_N): EvidenceState {
  if (n >= threshold * 2) return 'evidence'
  if (n >= threshold) return 'provisional'
  return 'insufficient'
}

export function stat(
  values: number[],
  unit?: string,
  threshold = EVIDENCE_N,
): Stat {
  const n = values.length
  if (n === 0) return { value: 0, n: 0, ci: 0, state: 'insufficient', unit }
  const mean = values.reduce((a, b) => a + b, 0) / n
  let ci = 0
  if (n > 1) {
    const variance =
      values.reduce((a, b) => a + (b - mean) ** 2, 0) / (n - 1)
    // 1.96 · SEM. Normal approximation is honest enough at the sample sizes
    // this product deals with, and the threshold guard does the real work.
    ci = 1.96 * Math.sqrt(variance / n)
  }
  return { value: mean, n, ci, state: evidenceState(n, threshold), unit }
}

/** Wilson score interval — correct for proportions at small n, where the
 *  normal approximation embarrasses itself. */
export function proportion(
  hits: number,
  n: number,
  threshold = EVIDENCE_N,
): Stat {
  if (n === 0) return { value: 0, n: 0, ci: 0, state: 'insufficient', unit: '%' }
  const p = hits / n
  const z = 1.96
  const denom = 1 + (z * z) / n
  const centre = (p + (z * z) / (2 * n)) / denom
  const half =
    (z * Math.sqrt((p * (1 - p)) / n + (z * z) / (4 * n * n))) / denom
  return {
    value: p,
    n,
    ci: Math.abs(centre - p) + half,
    state: evidenceState(n, threshold),
    unit: '%',
  }
}

// ── R ─────────────────────────────────────────────────────────────────────
// §11.2 R is defined by exactly one thing per instrument. Every statistic
// below depends on this, so it is computed in one place and nowhere else.

/** The rupee risk that defines 1R for a trade. */
export function riskPerR(trade: Trade, inst: Instrument): number | null {
  switch (inst.rBasis) {
    case 'initial-stop': {
      const entry = entryPrice(trade)
      if (entry == null || trade.plannedStop == null) return null
      const perUnit = Math.abs(entry - trade.plannedStop)
      if (perUnit <= 0) return null
      return perUnit * trade.qty
    }
    case 'fixed-rupee':
      return inst.fixedRisk && inst.fixedRisk > 0 ? inst.fixedRisk : null
    case 'account-pct': {
      const eq = inst.accountEquity ?? 0
      const pct = inst.accountRiskPct ?? 0
      const risk = (eq * pct) / 100
      return risk > 0 ? risk : null
    }
  }
}

export function entryPrice(trade: Trade): number | null {
  const entries = trade.legs.filter((l) => l.side === 'entry')
  if (!entries.length) return null
  const qty = entries.reduce((a, l) => a + l.qty, 0)
  if (qty === 0) return null
  return entries.reduce((a, l) => a + l.price * l.qty, 0) / qty
}

export function exitPrice(trade: Trade): number | null {
  const exits = trade.legs.filter((l) => l.side === 'exit')
  if (!exits.length) return null
  const qty = exits.reduce((a, l) => a + l.qty, 0)
  if (qty === 0) return null
  return exits.reduce((a, l) => a + l.price * l.qty, 0) / qty
}

export function fees(trade: Trade): number {
  return trade.legs.reduce((a, l) => a + l.fees, 0)
}

/** Gross P&L in rupees. FACT layer — derived only from fills. */
export function grossPnl(trade: Trade): number | null {
  const entry = entryPrice(trade)
  const exit = exitPrice(trade)
  if (entry == null || exit == null) return null
  const closedQty = trade.legs
    .filter((l) => l.side === 'exit')
    .reduce((a, l) => a + l.qty, 0)
  const sign = trade.direction === 'long' ? 1 : -1
  return sign * (exit - entry) * closedQty
}

export function netPnl(trade: Trade): number | null {
  const gross = grossPnl(trade)
  return gross == null ? null : gross - fees(trade)
}

/** Realised R. Null when the trade is open or R is undefined for it. */
export function realisedR(trade: Trade, inst: Instrument): number | null {
  const net = netPnl(trade)
  const risk = riskPerR(trade, inst)
  if (net == null || risk == null || risk === 0) return null
  return net / risk
}

export function isOpen(trade: Trade): boolean {
  return trade.closedAt == null
}

export function holdMs(trade: Trade): number | null {
  if (trade.closedAt == null) return null
  return trade.closedAt - trade.openedAt
}

/** §5.4 capture % = realised R ÷ MFE R. The most under-used metric in
 *  discretionary trading, which is why it sits in the fact column by default.
 *
 *  Defined for a single trade at any outcome — a trade that ran +2R and then
 *  stopped out has a capture of −0.5, and that is exactly the fact the metric
 *  exists to expose. Aggregates must not average this raw (see below). */
export function captureRatio(trade: Trade, inst: Instrument): number | null {
  const r = realisedR(trade, inst)
  if (r == null || trade.mfeR == null || trade.mfeR <= 0) return null
  return r / trade.mfeR
}

/** The aggregate form. Averaging raw capture across losers is meaningless: a
 *  loser whose MFE was +0.05R produces a capture of −20, and two of those
 *  swamp a hundred honest observations. So the *rate* is computed over winners
 *  — the standard reading of "how much of the available move did you take" —
 *  and everything given back, by winners and losers alike, is reported
 *  separately by `exitQuality().gaveBack`, where it cannot be averaged away. */
export function captureForAggregate(
  trade: Trade,
  inst: Instrument,
): number | null {
  const r = realisedR(trade, inst)
  if (r == null || r <= 0) return null
  return captureRatio(trade, inst)
}

// ── Aggregates ────────────────────────────────────────────────────────────

export interface Ledger {
  /** §0.2 The money ledger. */
  expectancy: Stat
  totalR: number
  netRupees: number
  winRate: Stat
  avgWin: Stat
  avgLoss: Stat
  profitFactor: number | null
  maxDrawdownR: number
  /** §0.2 The process ledger. Displayed side by side, never averaged in. */
  adherence: Stat
  takeAgainRate: Stat
  goodGradeRate: Stat
  captureRate: Stat
  count: number
}

const closedR = (trades: Trade[], inst: Instrument): number[] =>
  trades
    .map((t) => realisedR(t, inst))
    .filter((r): r is number => r != null)

export function ledger(
  trades: Trade[],
  inst: Instrument,
  threshold = EVIDENCE_N,
): Ledger {
  const live = trades.filter((t) => !t.deletedAt)
  const rs = closedR(live, inst)
  const wins = rs.filter((r) => r > 0)
  const losses = rs.filter((r) => r < 0)

  const grossWin = wins.reduce((a, b) => a + b, 0)
  const grossLoss = Math.abs(losses.reduce((a, b) => a + b, 0))

  const graded = live.filter((t) => t.grade != null)
  const answered = live.filter((t) => t.takeAgain != null)
  const captures = live
    .map((t) => captureForAggregate(t, inst))
    .filter((c): c is number => c != null)

  return {
    expectancy: stat(rs, 'R', threshold),
    totalR: rs.reduce((a, b) => a + b, 0),
    netRupees: live.reduce((a, t) => a + (netPnl(t) ?? 0), 0),
    winRate: proportion(wins.length, rs.length, threshold),
    avgWin: stat(wins, 'R', threshold),
    avgLoss: stat(losses, 'R', threshold),
    profitFactor: grossLoss > 0 ? grossWin / grossLoss : null,
    maxDrawdownR: maxDrawdown(rs),
    // §5.7 Adherence: in-playbook %. Whether your discipline is actually
    // costing you is a separate question, answered by offBookLedger below.
    adherence: proportion(
      live.filter((t) => !t.offBook).length,
      live.length,
      threshold,
    ),
    takeAgainRate: proportion(
      answered.filter((t) => t.takeAgain).length,
      answered.length,
      threshold,
    ),
    goodGradeRate: proportion(
      graded.filter((t) => t.grade === 'A' || t.grade === 'B').length,
      graded.length,
      threshold,
    ),
    captureRate: stat(captures, '%', threshold),
    count: live.length,
  }
}

/** Cumulative R track, in trade order. §6.2 EquityTrack */
export function equityCurve(trades: Trade[], inst: Instrument): number[] {
  const out: number[] = []
  let cum = 0
  for (const t of [...trades].sort((a, b) => a.openedAt - b.openedAt)) {
    const r = realisedR(t, inst)
    if (r == null) continue
    cum += r
    out.push(cum)
  }
  return out
}

export function maxDrawdown(rs: number[]): number {
  let cum = 0
  let peak = 0
  let dd = 0
  for (const r of rs) {
    cum += r
    peak = Math.max(peak, cum)
    dd = Math.min(dd, cum - peak)
  }
  return dd
}

// ── The named analyses of §5.7 ────────────────────────────────────────────

/** R distribution, bucketed. §5.7 "changes position sizing, stop placement" */
export function rHistogram(
  rs: number[],
  bucket = 0.5,
): { from: number; to: number; count: number }[] {
  if (!rs.length) return []
  const lo = Math.floor(Math.min(...rs) / bucket) * bucket
  const hi = Math.ceil(Math.max(...rs) / bucket) * bucket
  const bins: { from: number; to: number; count: number }[] = []
  for (let x = lo; x < hi; x += bucket) {
    bins.push({ from: x, to: x + bucket, count: 0 })
  }
  if (!bins.length) bins.push({ from: lo, to: lo + bucket, count: 0 })
  for (const r of rs) {
    const i = Math.min(bins.length - 1, Math.floor((r - lo) / bucket))
    bins[i].count++
  }
  return bins
}

/** §5.7 Expectancy grid: setup × regime, cells greyed below n=20. */
export interface GridCell {
  rowKey: string
  colKey: string
  stat: Stat
}

export function expectancyGrid(
  trades: Trade[],
  inst: Instrument,
  rowOf: (t: Trade) => string,
  colOf: (t: Trade) => string,
  threshold = EVIDENCE_N,
): GridCell[] {
  const buckets = new Map<string, number[]>()
  for (const t of trades) {
    const r = realisedR(t, inst)
    if (r == null) continue
    const key = `${rowOf(t)} ${colOf(t)}`
    const arr = buckets.get(key) ?? []
    arr.push(r)
    buckets.set(key, arr)
  }
  return [...buckets.entries()].map(([key, rs]) => {
    const [rowKey, colKey] = key.split(' ')
    return { rowKey, colKey, stat: stat(rs, 'R', threshold) }
  })
}

/** §5.7 Calibration: stated confidence vs realised win rate and avg R.
 *  Answers "whether your conviction means anything". */
export interface CalibrationPoint {
  confidence: number
  winRate: Stat
  avgR: Stat
}

export function calibration(
  trades: Trade[],
  inst: Instrument,
  threshold = EVIDENCE_N,
): CalibrationPoint[] {
  const out: CalibrationPoint[] = []
  for (let c = 1; c <= 5; c++) {
    const group = trades.filter((t) => t.confidence === c)
    const rs = closedR(group, inst)
    out.push({
      confidence: c,
      winRate: proportion(rs.filter((r) => r > 0).length, rs.length, threshold),
      avgR: stat(rs, 'R', threshold),
    })
  }
  return out
}

/** §5.7 Decision × outcome 2×2 — separates skill from luck.
 *  The two off-diagonal cells are the ones that teach. §2.5 */
export interface Quadrants {
  goodWin: Trade[]
  goodLoss: Trade[]
  badWin: Trade[]
  badLoss: Trade[]
  ungraded: Trade[]
}

export function decisionOutcome(trades: Trade[], inst: Instrument): Quadrants {
  const q: Quadrants = {
    goodWin: [], goodLoss: [], badWin: [], badLoss: [], ungraded: [],
  }
  for (const t of trades) {
    const r = realisedR(t, inst)
    if (t.grade == null || r == null) {
      q.ungraded.push(t)
      continue
    }
    const good = t.grade === 'A' || t.grade === 'B'
    const win = r > 0
    if (good && win) q.goodWin.push(t)
    else if (good && !win) q.goodLoss.push(t)
    else if (!good && win) q.badWin.push(t)
    else q.badLoss.push(t)
  }
  return q
}

/** §5.7 Mistake ledger: frequency × avg cost, ranked. "What to work on this
 *  month, in rupees." */
export interface MistakeCost {
  mistake: string
  count: number
  totalRupees: number
  avgRupees: number
  totalR: number
  /** Trend: count in the most recent third vs the earliest third. */
  trend: 'rising' | 'falling' | 'flat'
}

export function mistakeLedger(
  trades: Trade[],
  inst: Instrument,
): MistakeCost[] {
  const byMistake = new Map<string, Trade[]>()
  for (const t of trades) {
    for (const m of [...t.mistakes, ...t.autoTags]) {
      const arr = byMistake.get(m) ?? []
      arr.push(t)
      byMistake.set(m, arr)
    }
  }
  const sorted = [...trades].sort((a, b) => a.openedAt - b.openedAt)
  const third = Math.floor(sorted.length / 3)
  const early = new Set(sorted.slice(0, third).map((t) => t.id))
  const late = new Set(sorted.slice(-third || sorted.length).map((t) => t.id))

  return [...byMistake.entries()]
    .map(([mistake, ts]) => {
      // Attributable cost: only losing trades carry a rupee cost. A mistake
      // that happened to make money is still a mistake, but the ledger must
      // not pretend it cost anything — that is how journals lie.
      const costs = ts
        .map((t) => netPnl(t) ?? 0)
        .filter((p) => p < 0)
        .map((p) => Math.abs(p))
      const totalRupees = costs.reduce((a, b) => a + b, 0)
      const earlyN = ts.filter((t) => early.has(t.id)).length
      const lateN = ts.filter((t) => late.has(t.id)).length
      return {
        mistake,
        count: ts.length,
        totalRupees,
        avgRupees: costs.length ? totalRupees / costs.length : 0,
        totalR: ts.reduce((a, t) => a + Math.min(0, realisedR(t, inst) ?? 0), 0),
        trend:
          third < 2 || earlyN === lateN
            ? ('flat' as const)
            : lateN > earlyN
              ? ('rising' as const)
              : ('falling' as const),
      }
    })
    .sort((a, b) => b.totalRupees - a.totalRupees)
}

/** §5.7 Behavioural sequences — revenge and overtrading, made visible. */
export interface SequenceRead {
  /** Avg size multiple of the trade taken immediately after a loss. */
  sizeAfterLoss: Stat
  /** Minutes to the next trade after a loss. */
  minutesAfterLoss: Stat
  /** Expectancy of trade #4 and beyond within a single day. */
  lateTradeExpectancy: Stat
  /** Expectancy of the first three trades of a day, for comparison. */
  earlyTradeExpectancy: Stat
}

export function behaviouralSequences(
  trades: Trade[],
  inst: Instrument,
  threshold = EVIDENCE_N,
): SequenceRead {
  const sorted = [...trades].sort((a, b) => a.openedAt - b.openedAt)
  const sizeMultiples: number[] = []
  const gaps: number[] = []

  const avgQty =
    sorted.length > 0
      ? sorted.reduce((a, t) => a + t.qty, 0) / sorted.length
      : 0

  for (let i = 0; i < sorted.length - 1; i++) {
    const r = realisedR(sorted[i], inst)
    if (r == null || r >= 0) continue
    const next = sorted[i + 1]
    if (next.date !== sorted[i].date) continue
    if (avgQty > 0) sizeMultiples.push(next.qty / avgQty)
    gaps.push((next.openedAt - (sorted[i].closedAt ?? sorted[i].openedAt)) / 60000)
  }

  const byDay = new Map<string, Trade[]>()
  for (const t of sorted) {
    const arr = byDay.get(t.date) ?? []
    arr.push(t)
    byDay.set(t.date, arr)
  }
  const early: number[] = []
  const late: number[] = []
  for (const day of byDay.values()) {
    day.forEach((t, i) => {
      const r = realisedR(t, inst)
      if (r == null) return
      ;(i < 3 ? early : late).push(r)
    })
  }

  return {
    sizeAfterLoss: stat(sizeMultiples, '×', threshold),
    minutesAfterLoss: stat(gaps, 'm', threshold),
    lateTradeExpectancy: stat(late, 'R', threshold),
    earlyTradeExpectancy: stat(early, 'R', threshold),
  }
}

/** §5.7 Exit quality — capture % distribution, MAE before winners. */
export interface ExitQuality {
  /** Over winners only — see captureForAggregate. */
  capture: Stat
  /** How much heat winners took before working. */
  maeBeforeWinners: Stat
  /** R left on the table: MFE − realised, for winners only. */
  leftOnTable: Stat
  /** MFE − realised across *every* trade that ever went green, losers
   *  included. This is where "ran +2R then stopped out" shows up, and it is
   *  deliberately kept out of the capture average so it cannot be diluted. */
  gaveBack: Stat
  /** Raw per-trade captures, for the distribution plot. */
  captureSamples: number[]
}

export function exitQuality(
  trades: Trade[],
  inst: Instrument,
  threshold = EVIDENCE_N,
): ExitQuality {
  const captures: number[] = []
  const samples: number[] = []
  const maes: number[] = []
  const left: number[] = []
  const gaveBack: number[] = []
  for (const t of trades) {
    const r = realisedR(t, inst)
    const agg = captureForAggregate(t, inst)
    if (agg != null) captures.push(agg)
    const raw = captureRatio(t, inst)
    if (raw != null) samples.push(Math.max(-1, Math.min(1.5, raw)))
    if (r != null && t.mfeR != null && t.mfeR > 0) {
      gaveBack.push(Math.max(0, t.mfeR - r))
    }
    if (r != null && r > 0) {
      if (t.maeR != null) maes.push(Math.abs(t.maeR))
      if (t.mfeR != null) left.push(Math.max(0, t.mfeR - r))
    }
  }
  return {
    capture: stat(captures, '%', threshold),
    maeBeforeWinners: stat(maes, 'R', threshold),
    leftOnTable: stat(left, 'R', threshold),
    gaveBack: stat(gaveBack, 'R', threshold),
    captureSamples: samples,
  }
}

/** §5.7 Adherence: expectancy of off-book trades vs in-playbook.
 *  Answers "whether your discipline is actually costing you" — which is a
 *  real question, not a rhetorical one. */
export function adherenceSplit(
  trades: Trade[],
  inst: Instrument,
  threshold = EVIDENCE_N,
): { inBook: Stat; offBook: Stat; rate: Stat } {
  const inBook = closedR(trades.filter((t) => !t.offBook), inst)
  const off = closedR(trades.filter((t) => t.offBook), inst)
  return {
    inBook: stat(inBook, 'R', threshold),
    offBook: stat(off, 'R', threshold),
    rate: proportion(
      trades.filter((t) => !t.offBook).length,
      trades.length,
      threshold,
    ),
  }
}

/** §5.7 Weekday / time-of-day — "when to be flat". */
export function byBucket(
  trades: Trade[],
  inst: Instrument,
  keyOf: (t: Trade) => string,
  threshold = EVIDENCE_N,
): { key: string; stat: Stat }[] {
  const map = new Map<string, number[]>()
  for (const t of trades) {
    const r = realisedR(t, inst)
    if (r == null) continue
    const k = keyOf(t)
    const arr = map.get(k) ?? []
    arr.push(r)
    map.set(k, arr)
  }
  return [...map.entries()].map(([key, rs]) => ({
    key,
    stat: stat(rs, 'R', threshold),
  }))
}

/** §2.4.1 Market read score — thesis accuracy, independent of money. */
export function marketReadScore(
  scenarios: { status: string }[],
): { resolved: number; total: number; score: number } {
  const total = scenarios.length
  const resolved = scenarios.filter((s) => s.status !== 'pending').length
  const hit = scenarios.filter((s) => s.status === 'hit').length
  return { resolved, total, score: resolved ? hit / resolved : 0 }
}

/** §2.5 The week's worst-graded winner and best-graded loser — these two
 *  trades teach more than any other. */
const GRADE_ORDER: Record<Grade, number> = { A: 5, B: 4, C: 3, D: 2, F: 1 }

export function teachingTrades(
  trades: Trade[],
  inst: Instrument,
): { worstGradedWinner: Trade | null; bestGradedLoser: Trade | null } {
  let worstGradedWinner: Trade | null = null
  let bestGradedLoser: Trade | null = null
  for (const t of trades) {
    const r = realisedR(t, inst)
    if (r == null || t.grade == null) continue
    const g = GRADE_ORDER[t.grade]
    if (r > 0) {
      if (!worstGradedWinner || g < GRADE_ORDER[worstGradedWinner.grade!]) {
        worstGradedWinner = t
      }
    } else if (r < 0) {
      if (!bestGradedLoser || g > GRADE_ORDER[bestGradedLoser.grade!]) {
        bestGradedLoser = t
      }
    }
  }
  return { worstGradedWinner, bestGradedLoser }
}

/** §5.7 Mistake-class extinction — which errors you have actually stopped
 *  making. Reported as last-seen, not as a score. */
export function mistakeExtinction(
  trades: Trade[],
): { mistake: string; lastSeen: number | null; count: number }[] {
  const map = new Map<string, { lastSeen: number | null; count: number }>()
  for (const t of trades) {
    for (const m of [...t.mistakes, ...t.autoTags]) {
      const cur = map.get(m) ?? { lastSeen: null, count: 0 }
      cur.count++
      cur.lastSeen = Math.max(cur.lastSeen ?? 0, t.openedAt)
      map.set(m, cur)
    }
  }
  return [...map.entries()]
    .map(([mistake, v]) => ({ mistake, ...v }))
    .sort((a, b) => (b.lastSeen ?? 0) - (a.lastSeen ?? 0))
}

export function regimeAt(
  log: { at: number; state: RegimeState }[],
  at: number,
): RegimeState | null {
  let cur: RegimeState | null = null
  for (const entry of [...log].sort((a, b) => a.at - b.at)) {
    if (entry.at <= at) cur = entry.state
  }
  return cur
}
