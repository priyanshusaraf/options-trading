/* The query language — §6.4 QueryBar
 *
 * Grammar: `field:value`, ranges (`r:>1`, `date:2026-06-01..2026-06-30`),
 * negation (`-mistake:early-exit`), boolean `or`, free text.
 *
 * "Every facet click writes into it, so the UI teaches the language."
 * That is the reason this is a real parser with a serialiser, not a filter
 * object: the query string is the single source of truth, and the facet rail
 * is just another way to type it.
 */

import type { Instrument, Trade } from './types'
import { realisedR } from './metrics'
import { fromDateStr, quarterOf, weekday } from './dates'

export type Comparator = '=' | '>' | '<' | '>=' | '<=' | '..'

export interface Term {
  field: string
  op: Comparator
  value: string
  /** For `..` ranges. */
  value2?: string
  negated: boolean
}

export interface ParsedQuery {
  /** AND across groups; OR within a group. */
  groups: Term[][]
  text: string[]
  raw: string
}

export const QUERY_FIELDS = [
  'instrument',
  'setup',
  'mistake',
  'emotion',
  'tag',
  'grade',
  'regime',
  'r',
  'date',
  'conf',
  'dir',
  'weekday',
  'quarter',
  'again',
  'offbook',
  'open',
  'capture',
] as const

const TERM_RE =
  /^(-)?([a-z]+):(>=|<=|>|<)?([^\s]*?)(?:\.\.([^\s]+))?$/i

export function parseQuery(raw: string): ParsedQuery {
  const out: ParsedQuery = { groups: [], text: [], raw }
  const tokens = raw.match(/\S+/g) ?? []
  let pendingOr = false
  let current: Term[] = []

  const flush = () => {
    if (current.length) out.groups.push(current)
    current = []
  }

  for (const tok of tokens) {
    if (tok.toLowerCase() === 'or') {
      pendingOr = true
      continue
    }
    const m = TERM_RE.exec(tok)
    if (!m) {
      out.text.push(tok.replace(/^"|"$/g, ''))
      pendingOr = false
      continue
    }
    const [, neg, field, cmp, value, value2] = m
    const term: Term = {
      field: field.toLowerCase(),
      op: value2 ? '..' : ((cmp as Comparator) ?? '='),
      value,
      value2,
      negated: Boolean(neg),
    }
    if (pendingOr && (current.length || out.groups.length)) {
      // `or` binds the previous term into the same group.
      if (!current.length && out.groups.length) current = out.groups.pop()!
      current.push(term)
    } else {
      flush()
      current = [term]
    }
    pendingOr = false
  }
  flush()
  return out
}

export function serialiseQuery(q: ParsedQuery): string {
  const groups = q.groups.map((g) =>
    g
      .map((t) => {
        const neg = t.negated ? '-' : ''
        const op = t.op === '=' || t.op === '..' ? '' : t.op
        const val = t.op === '..' ? `${t.value}..${t.value2}` : t.value
        return `${neg}${t.field}:${op}${val}`
      })
      .join(' or '),
  )
  return [...groups, ...q.text].join(' ')
}

/** Add or replace a term — this is what a facet click calls. */
export function withTerm(raw: string, field: string, value: string): string {
  const q = parseQuery(raw)
  const exists = q.groups.some((g) =>
    g.some((t) => t.field === field && t.value === value && !t.negated),
  )
  if (exists) {
    // Clicking an active facet removes it. Toggle, not accumulate.
    q.groups = q.groups
      .map((g) => g.filter((t) => !(t.field === field && t.value === value)))
      .filter((g) => g.length)
    return serialiseQuery(q)
  }
  q.groups.push([{ field, op: '=', value, negated: false }])
  return serialiseQuery(q)
}

export interface EvalContext {
  instruments: Instrument[]
  setupCode: (id: string | null) => string
  /** Free text is matched against this haystack per trade. */
  haystack: (t: Trade) => string
}

function num(v: string): number {
  return Number(v.replace(/[^\d.\-]/g, ''))
}

function compare(actual: number, op: Comparator, v: number, v2?: number): boolean {
  switch (op) {
    case '>': return actual > v
    case '<': return actual < v
    case '>=': return actual >= v
    case '<=': return actual <= v
    case '..': return actual >= v && actual <= (v2 ?? v)
    default: return actual === v
  }
}

function matchStr(actual: string | null | undefined, t: Term): boolean {
  const a = (actual ?? '').toLowerCase()
  const v = t.value.toLowerCase()
  if (t.op === '=') return a === v || a.includes(v)
  return a === v
}

function matchTerm(
  trade: Trade,
  t: Term,
  ctx: EvalContext,
  inst: Instrument | undefined,
): boolean {
  const r = inst ? realisedR(trade, inst) : null
  switch (t.field) {
    case 'instrument': {
      const i = ctx.instruments.find((x) => x.id === trade.instrumentId)
      return matchStr(i?.code, t)
    }
    case 'setup':
      return matchStr(ctx.setupCode(trade.setupId), t)
    case 'mistake':
      return [...trade.mistakes, ...trade.autoTags].some((m) =>
        matchStr(m, t),
      )
    case 'emotion':
      return [
        ...trade.emotions,
        trade.emotionAtEntry ?? '',
        trade.emotionAtExit ?? '',
      ].some((e) => e && matchStr(e, t))
    case 'tag':
      return trade.tags.some((x) => matchStr(x, t))
    case 'grade':
      return matchStr(trade.grade, t)
    case 'regime':
      return matchStr(trade.regime, t)
    case 'dir':
      return matchStr(trade.direction, t)
    case 'r':
      return r != null && compare(r, t.op, num(t.value), t.value2 ? num(t.value2) : undefined)
    case 'conf':
      return compare(trade.confidence, t.op, num(t.value), t.value2 ? num(t.value2) : undefined)
    case 'capture': {
      if (trade.mfeR == null || r == null || trade.mfeR <= 0) return false
      return compare(r / trade.mfeR, t.op, num(t.value), t.value2 ? num(t.value2) : undefined)
    }
    case 'date': {
      // Supports `date:2026-06`, `date:2026-q2`, and full ranges.
      const v = t.value.toLowerCase()
      const q = /^(\d{4})-q([1-4])$/.exec(v)
      if (q) {
        return (
          trade.date.startsWith(q[1]) && quarterOf(trade.date) === Number(q[2])
        )
      }
      if (t.op === '..') {
        return trade.date >= t.value && trade.date <= (t.value2 ?? t.value)
      }
      if (t.op === '>' ) return trade.date > t.value
      if (t.op === '<') return trade.date < t.value
      if (t.op === '>=') return trade.date >= t.value
      if (t.op === '<=') return trade.date <= t.value
      return trade.date.startsWith(t.value)
    }
    case 'weekday':
      return matchStr(weekday(trade.date), t)
    case 'quarter':
      return quarterOf(trade.date) === num(t.value)
    case 'again':
      return trade.takeAgain === (t.value !== 'no' && t.value !== 'false')
    case 'offbook':
      return trade.offBook === (t.value !== 'no' && t.value !== 'false')
    case 'open':
      return (trade.closedAt == null) === (t.value !== 'no' && t.value !== 'false')
    default:
      return false
  }
}

export function runQuery(
  raw: string,
  trades: Trade[],
  ctx: EvalContext,
): Trade[] {
  const q = parseQuery(raw)
  if (!q.groups.length && !q.text.length) return trades

  return trades.filter((trade) => {
    const inst = ctx.instruments.find((i) => i.id === trade.instrumentId)
    for (const group of q.groups) {
      // Within a group: OR. A negated term inside a group still means "must
      // not match", so negation short-circuits the whole group.
      const positives = group.filter((t) => !t.negated)
      const negatives = group.filter((t) => t.negated)
      if (negatives.some((t) => matchTerm(trade, t, ctx, inst))) return false
      if (positives.length && !positives.some((t) => matchTerm(trade, t, ctx, inst))) {
        return false
      }
    }
    if (q.text.length) {
      const hay = ctx.haystack(trade).toLowerCase()
      if (!q.text.every((w) => hay.includes(w.toLowerCase()))) return false
    }
    return true
  })
}

/** Token autocomplete for the query bar. §6.4 */
export function suggestQuery(
  raw: string,
  vocab: Record<string, string[]>,
): string[] {
  const tokens = raw.match(/\S+/g) ?? []
  const last = tokens[tokens.length - 1] ?? ''
  if (!last.includes(':')) {
    const pref = last.replace(/^-/, '').toLowerCase()
    return QUERY_FIELDS.filter((f) => f.startsWith(pref)).map((f) => `${f}:`)
  }
  const [field, partial] = last.replace(/^-/, '').split(':')
  const values = vocab[field] ?? []
  return values
    .filter((v) => v.toLowerCase().startsWith((partial ?? '').toLowerCase()))
    .slice(0, 12)
    .map((v) => `${field}:${v}`)
}

/** Sort trades for the blotter. Dates descend by default — the most recent
 *  session is the one you are thinking about. */
export function sortTrades(
  trades: Trade[],
  key: string,
  dir: 'asc' | 'desc',
  inst: (id: string) => Instrument | undefined,
): Trade[] {
  const sign = dir === 'asc' ? 1 : -1
  const value = (t: Trade): number | string => {
    switch (key) {
      case 'r': {
        const i = inst(t.instrumentId)
        return i ? (realisedR(t, i) ?? -Infinity) : -Infinity
      }
      case 'conf': return t.confidence
      case 'qty': return t.qty
      case 'grade': return t.grade ?? 'Z'
      case 'setup': return t.setupId ?? ''
      case 'date':
      default: return fromDateStr(t.date).getTime() + t.openedAt % 86_400_000
    }
  }
  return [...trades].sort((a, b) => {
    const va = value(a)
    const vb = value(b)
    if (typeof va === 'string' || typeof vb === 'string') {
      return String(va).localeCompare(String(vb)) * sign
    }
    return (va - vb) * sign
  })
}
