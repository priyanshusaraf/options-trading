/* The ticket grammar — §9.6
 *
 *   bnf 52200ce b 60 @248.5 orb c4 fomo
 *   │   │       │ │   │      │   │  └ emotion (optional)
 *   │   │       │ │   │      │   └ confidence 1–5
 *   │   │       │ │   │      └ setup (playbook shortcode)
 *   │   │       │ │   └ price
 *   │   │       │ └ quantity
 *   │   │       └ direction
 *   │   └ strike + type (or FUT / EQ)
 *   └ instrument shortcode
 *
 * "Anything omitted falls back to workspace defaults; anything ambiguous
 * highlights that token and waits. No dialog appears."
 *
 * The parser is order-tolerant: tokens are classified by shape, not position,
 * because typing `b bnf 60 @248.5` under time pressure should still work.
 */

import type {
  ContractKind,
  Direction,
  ID,
  Instrument,
  OptionType,
  PlaybookEntry,
} from './types'

export interface ParsedTicket {
  instrumentId: ID | null
  instrumentToken?: string
  direction: Direction | null
  contract: ContractKind | null
  strike?: number
  optionType?: OptionType
  qty: number | null
  price: number | null
  stop?: number
  target?: number
  setupId: ID | null
  offBook: boolean
  confidence: number | null
  emotion?: string
  /** Tokens the parser could not classify. The UI highlights these and waits. */
  ambiguous: TokenSpan[]
  /** What is still missing before this can commit. */
  missing: string[]
}

export interface TokenSpan {
  text: string
  from: number
  to: number
  reason: string
}

export interface ParseContext {
  instruments: Instrument[]
  playbook: PlaybookEntry[]
  /** Workspace defaults — instrument is pre-filled from the workspace. §2.3 */
  defaultInstrumentId: ID
  defaultQty: number
  emotions: string[]
}

const DIRECTION_TOKENS: Record<string, Direction> = {
  b: 'long',
  buy: 'long',
  long: 'long',
  l: 'long',
  s: 'short',
  sell: 'short',
  short: 'short',
}

/** `52200ce`, `52200 ce`, `24500pe` */
const STRIKE_RE = /^(\d{3,6})(ce|pe|c|p)$/i
/** `@248.5` — price is always sigil-marked so it never collides with qty. */
const PRICE_RE = /^@(\d+(?:\.\d+)?)$/
/** `x51900` stop, `t52320` target — optional extensions to the documented
 *  grammar, needed because R depends on the stop when rBasis is initial-stop. */
const STOP_RE = /^x(\d+(?:\.\d+)?)$/i
const TARGET_RE = /^t(\d+(?:\.\d+)?)$/i
/** `c4` — confidence 1–5. */
const CONF_RE = /^c([1-5])$/i
const QTY_RE = /^\d+$/

export function parseTicket(
  raw: string,
  ctx: ParseContext,
): ParsedTicket {
  const out: ParsedTicket = {
    instrumentId: null,
    direction: null,
    contract: null,
    qty: null,
    price: null,
    setupId: null,
    offBook: false,
    confidence: null,
    ambiguous: [],
    missing: [],
  }

  // Tokenise while retaining source offsets, so the UI can highlight the exact
  // token that is ambiguous rather than the whole line.
  const spans: { text: string; from: number }[] = []
  const re = /\S+/g
  let m: RegExpExecArray | null
  while ((m = re.exec(raw))) spans.push({ text: m[0], from: m.index })

  const qtyCandidates: { text: string; from: number; value: number }[] = []

  for (const span of spans) {
    const t = span.text
    const lower = t.toLowerCase()

    // Price — checked first because the sigil is unambiguous.
    const price = PRICE_RE.exec(t)
    if (price) {
      out.price = Number(price[1])
      continue
    }
    const stop = STOP_RE.exec(t)
    if (stop) {
      out.stop = Number(stop[1])
      continue
    }
    const target = TARGET_RE.exec(t)
    if (target) {
      out.target = Number(target[1])
      continue
    }
    const conf = CONF_RE.exec(t)
    if (conf) {
      out.confidence = Number(conf[1])
      continue
    }

    // Strike + option type.
    const strike = STRIKE_RE.exec(t)
    if (strike) {
      out.strike = Number(strike[1])
      const kind = strike[2].toLowerCase()
      out.optionType = kind.startsWith('c') ? 'CE' : 'PE'
      out.contract = 'OPT'
      continue
    }

    if (lower === 'fut' || lower === 'f') {
      out.contract = 'FUT'
      continue
    }
    if (lower === 'eq') {
      out.contract = 'EQ'
      continue
    }

    // Instrument shortcode — matched before direction, because a one-letter
    // instrument code would otherwise be eaten by `b`/`s`.
    const inst = ctx.instruments.find(
      (i) => i.code.toLowerCase() === lower || i.id.toLowerCase() === lower,
    )
    if (inst && out.instrumentId == null) {
      out.instrumentId = inst.id
      out.instrumentToken = t
      continue
    }

    if (out.direction == null && lower in DIRECTION_TOKENS) {
      out.direction = DIRECTION_TOKENS[lower]
      continue
    }

    // Setup shortcode from the playbook. `0` is off-book. §2.3
    if (lower === '0' || lower === 'offbook' || lower === 'off-book') {
      out.offBook = true
      out.setupId = null
      continue
    }
    const setup = ctx.playbook.find(
      (p) => !p.archived && p.code.toLowerCase() === lower,
    )
    if (setup) {
      out.setupId = setup.id
      continue
    }
    // Single digit 1–9 addresses the playbook shortlist by position. §2.3
    if (/^[1-9]$/.test(lower)) {
      const byShortcut = ctx.playbook.find(
        (p) => !p.archived && p.shortcut === Number(lower),
      )
      if (byShortcut) {
        out.setupId = byShortcut.id
        continue
      }
    }

    if (ctx.emotions.includes(lower)) {
      out.emotion = lower
      continue
    }

    if (QTY_RE.test(t)) {
      qtyCandidates.push({ text: t, from: span.from, value: Number(t) })
      continue
    }

    out.ambiguous.push({
      text: t,
      from: span.from,
      to: span.from + t.length,
      reason: 'unrecognised token',
    })
  }

  // Bare integers: the first is quantity. A second one is genuinely ambiguous
  // — it could be a price the user forgot to sigil — so we say so rather than
  // guessing, per §8 "errors are directions".
  if (qtyCandidates.length) {
    out.qty = qtyCandidates[0].value
    for (const extra of qtyCandidates.slice(1)) {
      out.ambiguous.push({
        text: extra.text,
        from: extra.from,
        to: extra.from + extra.text.length,
        reason: 'quantity already set — prefix a price with @',
      })
    }
  }

  // Fall back to workspace defaults. §9.6
  if (out.instrumentId == null) out.instrumentId = ctx.defaultInstrumentId
  if (out.qty == null) out.qty = ctx.defaultQty
  if (out.contract == null) out.contract = out.strike != null ? 'OPT' : 'FUT'

  if (out.direction == null) out.missing.push('direction')
  if (out.price == null) out.missing.push('price')
  if (out.setupId == null && !out.offBook) out.missing.push('setup')
  if (out.confidence == null) out.missing.push('confidence')

  return out
}

/** Renders a parsed ticket back to canonical form, used by the `?` overlay
 *  and by the palette's preview line. */
export function describeTicket(
  p: ParsedTicket,
  ctx: ParseContext,
): string {
  const inst = ctx.instruments.find((i) => i.id === p.instrumentId)
  const setup = ctx.playbook.find((s) => s.id === p.setupId)
  const contract =
    p.contract === 'OPT' && p.strike
      ? `${p.strike} ${p.optionType}`
      : (p.contract ?? '')
  const dir = p.direction === 'long' ? 'Long' : p.direction === 'short' ? 'Short' : '—'
  const parts = [
    inst?.code ?? '—',
    contract,
    dir,
    p.qty != null ? `×${p.qty}` : '',
    p.price != null ? `@${p.price}` : '',
    setup ? setup.code : p.offBook ? 'off-book' : '',
    p.confidence != null ? `c${p.confidence}` : '',
  ]
  return parts.filter(Boolean).join('  ')
}
