/* Kite orders attributed to the owner rather than the bot, awaiting reasoning.
 *
 * The Fact layer of these trades is broker-sourced: price, quantity, side and
 * timestamp come off the account, so the owner never types a number. All they
 * supply is the part only they can — why. */

export interface ManualFill {
  order_id: string
  tradingsymbol: string
  exchange: string | null
  product: string | null
  side: 'BUY' | 'SELL'
  qty: number
  avg_price: number | null
  order_ts: string | null
  /** NEEDS_REVIEW means it might be a bot GTT stop — the classifier refused to
   *  guess rather than risk misattributing it. */
  verdict: 'MANUAL' | 'NEEDS_REVIEW'
  claimed_trade: string | null
}

function authHeaders(): Record<string, string> {
  const token = import.meta.env.VITE_PT_TOKEN
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export async function listManualFills(unclaimed = true): Promise<ManualFill[]> {
  try {
    const res = await fetch(`/api/ledger/manual-fills?unclaimed=${unclaimed}`,
                            { headers: authHeaders() })
    if (!res.ok) return []
    return (await res.json()).fills as ManualFill[]
  } catch {
    return []
  }
}

export async function claimManualFill(orderId: string, tradeId: string): Promise<void> {
  const res = await fetch(
    `/api/ledger/manual-fills/${encodeURIComponent(orderId)}/claim`,
    {
      method: 'POST',
      headers: { 'content-type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ trade_id: tradeId }),
    },
  )
  if (!res.ok) throw new Error(`claim failed: ${res.status}`)
}

/** The journal instrument a Kite tradingsymbol belongs to.
 *
 *  Kite symbols are like NIFTY25JAN25000CE / BANKNIFTY... / GOLDM25FEBFUT, so a
 *  prefix match against the instrument code is enough and stays correct as
 *  expiries roll. Returns null when nothing matches, and the caller asks rather
 *  than filing the trade under a guess. */
export function instrumentForSymbol(
  symbol: string,
  instruments: { id: string; code: string }[],
): string | null {
  const s = (symbol || '').toUpperCase()
  // Longest code first so BANKNIFTY wins over NIFTY.
  const sorted = [...instruments].sort((a, b) => b.code.length - a.code.length)
  for (const i of sorted) if (s.startsWith(i.code.toUpperCase())) return i.id
  return null
}

/** Kite option symbols end in a STRIKE followed by CE or PE; futures end FUT.
 *
 *  The strike digit is load-bearing: plenty of equity symbols end in those two
 *  letters — RELIANCE is the obvious one — and a bare endsWith('CE') files every
 *  one of them as an option. */
const OPTION_SUFFIX = /\d(CE|PE)$/

export function contractFromSymbol(symbol: string): 'OPT' | 'FUT' | 'EQ' {
  const s = (symbol || '').toUpperCase()
  if (OPTION_SUFFIX.test(s)) return 'OPT'
  if (s.endsWith('FUT')) return 'FUT'
  return 'EQ'
}

export function optionTypeFromSymbol(symbol: string): 'CE' | 'PE' | undefined {
  const m = OPTION_SUFFIX.exec((symbol || '').toUpperCase())
  return m ? (m[1] as 'CE' | 'PE') : undefined
}

/** The open journal trade this fill CLOSES, if any.
 *
 *  A fill is an exit when it is the opposite side of a position already open on
 *  the same instrument: a SELL closes a long, a BUY closes a short. That is the
 *  difference between "why did you take this?" and "why did you get out?" —
 *  two different questions, and the second is the one most journals never ask.
 *
 *  FIFO: the oldest open trade closes first, which is how a discretionary
 *  trader thinks about "the position I've been holding".
 */
export function findClosableTrade<
  T extends { id: string; instrumentId: string; direction: string; closedAt: number | null; openedAt: number },
>(fill: { side: 'BUY' | 'SELL' }, instrumentId: string, trades: T[]): T | null {
  const closes = fill.side === 'SELL' ? 'long' : 'short'
  const open = trades
    .filter((t) => t.instrumentId === instrumentId
      && t.closedAt === null
      && t.direction === closes)
    .sort((a, b) => a.openedAt - b.openedAt)
  return open[0] ?? null
}
