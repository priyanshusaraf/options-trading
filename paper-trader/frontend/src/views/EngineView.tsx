import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { useLive } from '../state/LiveContext'
import { getStatus } from '../lib/api'
import LogStream from '../components/LogStream'
import SessionBanner from '../components/SessionBanner'
import ModeChip from '../components/ModeChip'
import { num, signalStyle, signedInr, pnlColor, inr, epochTime } from '../lib/format'
import { prio } from '../lib/constants'
import type { InstrState } from '../lib/types'
import { Badge, badgeVariants } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { cn } from '@/lib/utils'

// Budget (seconds) after which a row with no fresh candle is flagged. Mirrors the
// backend interval grace (interval minutes + 90s slack).
const INTERVAL_MIN: Record<string, number> = { '5minute': 5, '15minute': 15, '30minute': 30, '60minute': 60 }
const staleBudget = (interval?: string) => (INTERVAL_MIN[interval || '15minute'] || 15) * 60 + 90

function Stat({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <div className="stat-label">{label}</div>
      <div className="text-sm font-semibold">{children}</div>
    </div>
  )
}

export default function EngineView() {
  const { state, logs } = useLive()
  const [authed, setAuthed] = useState<boolean | null>(null)
  const [showMath, setShowMath] = useState(false)

  useEffect(() => {
    const f = () => getStatus().then((s) => setAuthed(!!s.authenticated)).catch(() => {})
    f(); const t = setInterval(f, 5000); return () => clearInterval(t)
  }, [])

  const rows: InstrState[] = useMemo(
    () => Object.values(state?.states || {}).sort((a, b) => prio(a.instrument) - prio(b.instrument)),
    [state?.states])

  // server time as IST epoch seconds, for per-row freshness age
  const nowEpoch = useMemo(() => {
    const iso = state?.time
    if (!iso) return Math.floor(Date.now() / 1000)
    const anchored = /([zZ]|[+-]\d{2}:?\d{2})$/.test(iso) ? iso : iso + '+05:30'
    const ms = Date.parse(anchored)
    return Number.isNaN(ms) ? Math.floor(Date.now() / 1000) : Math.floor(ms / 1000)
  }, [state?.time])

  const recentErrors = useMemo(
    () => logs.filter((l) => l.level === 'ERROR' || l.level === 'WARNING').slice(-8).reverse(),
    [logs])

  const armed = state?.armed
  const running = state?.running
  const halt = state?.halt
  const mode = state?.broker_mode
  // OPS-R2-1: per-segment market session. When a segment is closed, no candle can
  // print, so a "stale" row is benign idle — render it neutral grey, not amber alarm.
  const marketOpen = state?.market_open || {}
  const anyOpen = state?.any_market_open

  return (
    <div className="flex flex-col gap-3">
      <SessionBanner authenticated={authed} />

      {/* Engine status header — is the bot ALIVE, ARMED, PAPER/LIVE, HALTED? */}
      <Card className="p-3 flex items-center gap-6 flex-wrap">
        <div className="flex items-center gap-2">
          <span className="text-zinc-100 font-semibold">Engine</span>
          <Badge variant="chip" className="bg-zinc-700/40 text-muted">{state?.provider?.toUpperCase() || '—'}</Badge>
          <ModeChip mode={mode} />
        </div>
        <Stat label="Running">
          {running == null ? <span className="text-muted">—</span>
            : running
              ? anyOpen === false
                ? <span className="text-muted" title="all enabled markets closed — engine idling until next session (this is healthy, not a fault)">● idle (markets closed)</span>
                : <span className="text-up">● running</span>
              : <span className="text-down">○ stopped</span>}
        </Stat>
        <Stat label="Armed">
          {armed == null ? <span className="text-muted">—</span>
            : armed ? <span className="text-up">● ARMED</span>
              : <span className="text-amber-400">○ DISARMED</span>}
        </Stat>
        <Stat label="Tick"><span className="tabular-nums">{state?.tick ?? '—'}</span></Stat>
        <Stat label="Open positions"><span className="tabular-nums">{state?.capital?.open_count ?? '—'}</span></Stat>
        <div className="ml-auto">
          {halt?.halted ? (
            <div className={cn(badgeVariants({ variant: 'chip' }), 'bg-down/20 text-down border border-down/50 font-semibold')}
              title="New entries are halted by a circuit breaker. Open positions are still managed & protected.">
              ⛔ HALT — {halt.reason === 'open_drawdown' ? 'open drawdown'
                : halt.reason === 'round_trips' ? 'round-trip cap' : 'daily loss'}
              {' · '}
              {halt.reason === 'round_trips'
                ? `${halt.round_trips} / ${halt.max_round_trips} round trips`
                : halt.reason === 'open_drawdown'
                  ? `${signedInr(halt.realized + halt.open_unrealized)} / cap ${inr(-halt.max_open_drawdown)}`
                  : `${signedInr(halt.realized)} / cap ${inr(-halt.max_daily_loss)}`}
            </div>
          ) : (
            <Badge variant="chip" className="bg-up/15 text-up">no halt</Badge>
          )}
        </div>
      </Card>

      {/* What the two loops actually do — honest cadence, not "every tick" */}
      <Card className="p-3 text-[11px] text-muted leading-relaxed">
        <span className="text-zinc-300 font-semibold">How it runs: </span>
        signal math recomputes on each instrument's completed candle (per its live TF); open positions
        are marked &amp; SL/TP-checked continuously on the fast risk lane. A waiting row is not hung —
        it is between candles. The bot only OPENS new trades when armed and not halted.
      </Card>

      <div className="grid gap-3 grid-cols-1 md:grid-cols-[minmax(0,1.7fr)_minmax(0,1fr)]">
        <div className="flex flex-col gap-3 min-w-0">
          {/* Per-instrument freshness / scan + position health */}
          <Card className="p-3 overflow-auto">
            <div className="flex items-center justify-between mb-2">
              <span className="stat-label">Per-instrument health — last completed candle &amp; freshness</span>
              <button onClick={() => setShowMath((v) => !v)}
                className={cn(badgeVariants({ variant: 'chip' }), 'bg-zinc-700/40 text-muted hover:text-zinc-200')}>
                {showMath ? 'hide strategy math' : 'show strategy math'}
              </button>
            </div>
            <table className="w-full text-xs">
              <thead className="text-muted text-left">
                <tr className="[&>th]:py-1 [&>th]:pr-3 [&>th]:font-medium">
                  <th>Instrument</th><th>Live TF</th><th>Last candle</th><th>Freshness</th>
                  <th>Signal</th><th>Position</th>
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 && <tr><td colSpan={6} className="py-6 text-center text-muted">warming up…</td></tr>}
                {rows.map((s) => {
                  const age = s.time ? nowEpoch - s.time : null
                  const stale = age == null || age > staleBudget(s.interval)
                  // closed market -> staleness is expected idle, not a broken feed
                  const closed = marketOpen[s.segment] === false
                  return (
                    <tr key={s.instrument} className="border-t border-edge [&>td]:py-1 [&>td]:pr-3 tabular-nums">
                      <td className="font-semibold text-zinc-100">{s.name}</td>
                      <td className="text-muted">{(s.interval || '').replace('minute', 'm') || '—'}</td>
                      <td className="text-muted">{epochTime(s.time)}</td>
                      <td>{closed
                        ? <span className="text-muted" title="market closed — no new candle prints; engine is idle, not broken">market closed</span>
                        : !s.time
                          ? <span className="text-muted">no scan yet</span>
                          : stale
                            ? <span className="text-amber-400" title={`last candle ${age}s ago`}>stale / waiting</span>
                            : <span className="text-up/80">fresh</span>}</td>
                      <td><span className={cn(badgeVariants({ variant: 'chip' }), signalStyle(s.signal))}>{s.signal === 'NONE' ? '—' : s.signal.replace('_', ' ')}</span></td>
                      <td>{s.position
                        ? <span className={s.position.direction === 'LONG' ? 'text-up' : 'text-down'}>
                            {s.position.direction} {s.position.option_type}{' '}
                            <span className={pnlColor(s.position.unrealized_pnl)}>{signedInr(s.position.unrealized_pnl)}</span>
                          </span>
                        : <span className="text-muted">flat</span>}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </Card>

          {/* Strategy-math table — a subset of Monitor, collapsed by default */}
          {showMath && (
            <Card className="p-3 overflow-auto">
              <div className="stat-label mb-2">Strategy math — EMA50 + displacement z-score per instrument</div>
              <table className="w-full text-xs">
                <thead className="text-muted text-left">
                  <tr className="[&>th]:py-1 [&>th]:pr-3 [&>th]:font-medium">
                    <th>Instrument</th><th>Close</th><th>EMA50</th><th>z</th><th>z[-1]</th>
                    <th>slope</th><th>trend</th><th>signal</th><th>exit</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((s) => (
                    <tr key={s.instrument} className="border-t border-edge [&>td]:py-1 [&>td]:pr-3 tabular-nums">
                      <td className="font-semibold text-zinc-100">{s.name}</td>
                      <td>{num(s.close)}</td>
                      <td>{num(s.ema)}</td>
                      <td className={s.z > 1 ? 'text-up' : s.z < -1 ? 'text-down' : ''}>{num(s.z)}</td>
                      <td className="text-muted">{num(s.z_prev)}</td>
                      <td>{num(s.slope, 1)}</td>
                      <td className={s.trend === 'bull' ? 'text-up' : s.trend === 'bear' ? 'text-down' : 'text-muted'}>{s.trend}</td>
                      <td><span className={cn(badgeVariants({ variant: 'chip' }), signalStyle(s.signal))}>{s.signal === 'NONE' ? '—' : s.signal.replace('_', ' ')}</span></td>
                      <td className="text-muted">{[s.long_exit && 'L', s.short_exit && 'S'].filter(Boolean).join('/') || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          )}
        </div>

        <div className="flex flex-col gap-3 min-w-0">
          {/* Recent errors pinned above the raw log */}
          <Card className="p-3">
            <div className="stat-label mb-2">Recent errors / warnings ({recentErrors.length})</div>
            {recentErrors.length === 0
              ? <div className="text-[11px] text-up/70">none — engine quiet</div>
              : <div className="space-y-0.5 text-[11px]">
                  {recentErrors.map((l, i) => (
                    <div key={l.seq || i} className="flex gap-2">
                      {l.instrument && <span className="text-blue-300 shrink-0">[{l.instrument}]</span>}
                      <span className={l.level === 'ERROR' ? 'text-down' : 'text-yellow-400'}>{l.msg}</span>
                    </div>
                  ))}
                </div>}
          </Card>
          <LogStream />
        </div>
      </div>
    </div>
  )
}
