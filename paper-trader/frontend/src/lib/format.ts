export const inr = (n: number | null | undefined, d = 0): string =>
  n == null ? '—' : '₹' + n.toLocaleString('en-IN', { maximumFractionDigits: d, minimumFractionDigits: d })

export const signedInr = (n: number | null | undefined, d = 0): string =>
  n == null ? '—' : (n >= 0 ? '+' : '') + inr(n, d)

export const pct = (n: number | null | undefined, d = 1): string =>
  n == null ? '—' : (n >= 0 ? '+' : '') + n.toFixed(d) + '%'

export const num = (n: number | null | undefined, d = 2): string =>
  n == null ? '—' : n.toFixed(d)

export const pnlColor = (n: number | null | undefined): string =>
  n == null ? 'text-muted' : n > 0 ? 'text-up' : n < 0 ? 'text-down' : 'text-zinc-300'

export const signalStyle = (sig: string | undefined): string => {
  if (sig === 'LONG_ENTRY') return 'bg-up/15 text-up'
  if (sig === 'SHORT_ENTRY') return 'bg-down/15 text-down'
  return 'bg-zinc-700/30 text-muted'
}

// Always render in IST — this is an Indian-market app; a viewer in another
// timezone must still see the real session time, not their local clock. Backend
// timestamps that arrive WITHOUT an offset are IST wall-clock, so anchor them to
// +05:30 before formatting (a naive string would otherwise be parsed as the
// viewer's local time).
const IST = 'Asia/Kolkata'
const anchorIst = (iso: string): string =>
  /([zZ]|[+-]\d{2}:?\d{2})$/.test(iso) ? iso : iso + '+05:30'

export const time = (iso: string): string => {
  try { return new Date(anchorIst(iso)).toLocaleTimeString('en-IN', { timeZone: IST, hour: '2-digit', minute: '2-digit', second: '2-digit' }) }
  catch { return iso }
}

export const dt = (iso: string): string => {
  try { return new Date(anchorIst(iso)).toLocaleString('en-IN', { timeZone: IST, day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) }
  catch { return iso }
}

// Candle/scan times on the snapshot are IST epoch SECONDS (market_hours.ist_epoch).
// Render them as IST wall-clock — never the viewer's local clock.
export const epochTime = (epoch: number | null | undefined): string => {
  if (!epoch) return '—'
  try { return new Date(epoch * 1000).toLocaleTimeString('en-IN', { timeZone: IST, hour: '2-digit', minute: '2-digit', second: '2-digit' }) }
  catch { return '—' }
}
