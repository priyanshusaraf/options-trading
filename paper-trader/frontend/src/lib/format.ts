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

export const time = (iso: string): string => {
  try { return new Date(iso).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) }
  catch { return iso }
}

export const dt = (iso: string): string => {
  try { return new Date(iso).toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) }
  catch { return iso }
}
