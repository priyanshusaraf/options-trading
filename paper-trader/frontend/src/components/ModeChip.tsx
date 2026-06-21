// PAPER / LIVE chip — surfaces the active broker_mode wherever destructive or
// trust-critical controls live (Engine console, Monitor). Reads broker_mode off
// the WS snapshot. LIVE is loud red (real-money orders); PAPER is calm green.
export default function ModeChip({ mode }: { mode?: 'paper' | 'live' }) {
  if (mode === 'live') {
    return (
      <span className="badge bg-down/20 text-down border border-down/40 font-semibold"
        title="REAL-MONEY execution: the bot can place live Kite orders.">
        🔴 LIVE MONEY
      </span>
    )
  }
  return (
    <span className="badge bg-emerald-500/15 text-emerald-300 border border-emerald-500/30"
      title="Paper mode: simulated fills only, no real orders.">
      📝 PAPER
    </span>
  )
}
