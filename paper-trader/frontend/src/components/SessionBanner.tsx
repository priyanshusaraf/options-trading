import { useLive } from '../state/LiveContext'

// Presentational only. Turns the classified health flags (C1) into an honest,
// prominent strip so a Kite session expiry is a 10-second re-auth instead of a
// buried 1-in-30 log line. Two distinct states:
//   • RED  — Kite SESSION EXPIRED (auth_error on candle/quote, or status says
//            unauthenticated): the access token is dead; re-authenticate.
//   • AMBER — data feed DEGRADED (failures but not auth): a transient outage.
// No banner when the feed is healthy.
//
// `authenticated` is optional: TopBar already polls /api/status and can pass it;
// EngineView relies on the classified auth_error flag alone (which is the
// authoritative, machine-readable signal regardless of the status poll).
export default function SessionBanner({ authenticated }: { authenticated?: boolean | null }) {
  const { health } = useLive()
  const candle = health?.candle
  const quote = health?.quote
  const authExpired = !!candle?.auth_error || !!quote?.auth_error || authenticated === false
  const fails = (candle?.consecutive_failures || 0) + (quote?.consecutive_failures || 0)
  const degraded = fails > 0

  if (!authExpired && !degraded) return null

  if (authExpired) {
    return (
      <div className="flex items-center justify-center gap-3 bg-down/20 border border-down/50 text-down
                      text-xs font-semibold py-2 px-3 rounded">
        <span>🔴 KITE SESSION EXPIRED — re-authenticate to restore the data feed</span>
        <a href="/api/login" className="btn border-down/60 text-down hover:bg-down/20">Connect Kite</a>
      </div>
    )
  }

  // degraded but not an auth failure — a transient outage (429 / timeout)
  const lastErr = candle?.last_error || quote?.last_error || ''
  return (
    <div className="flex items-center justify-center gap-2 bg-amber-400/15 border border-amber-400/40
                    text-amber-400 text-xs font-semibold py-1.5 px-3 rounded"
         title={lastErr}>
      ⚠ DATA FEED DEGRADED — {fails} consecutive failure{fails === 1 ? '' : 's'} (retrying)
    </div>
  )
}
