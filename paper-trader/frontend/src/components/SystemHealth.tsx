import { useEffect, useState } from 'react'
import { getHealth } from '../lib/api'
import {
  feedProblems, headlineProblem, laneAge, laneTone, uptimeLabel,
  verdictLabel, verdictTone, type Health,
} from '../lib/health'
import { Card } from '@/components/ui/card'
import { cn } from '@/lib/utils'

/**
 * System health, from the /api/health readiness probe.
 *
 * The backend has reported DB reachability, both loop heartbeat ages, provider
 * auth and candle-feed anomalies since 2026-08-01, and none of it was visible
 * in the app — you had to ssh to the box and curl. This is the panel that makes
 * the answer to "is it actually working right now?" a glance instead of an
 * investigation.
 *
 * Polls on its own timer rather than riding the WS state, because the whole
 * point is to be informative when the engine is NOT well: a probe that only
 * updates while the thing it monitors is healthy tells you nothing on the day
 * it matters.
 */
const TONE = {
  good: 'text-emerald-400',
  warn: 'text-amber-400',
  bad: 'text-rose-400',
} as const

function Dot({ tone }: { tone: 'good' | 'warn' | 'bad' }) {
  return <span className={cn('mr-1', TONE[tone])} aria-hidden>●</span>
}

export default function SystemHealth() {
  const [health, setHealth] = useState<Health | null>(null)
  const [read, setRead] = useState(false)

  useEffect(() => {
    let alive = true
    const load = () =>
      getHealth().then((h) => {
        if (!alive) return
        setHealth(h)
        setRead(true)
      })
    load()
    const t = setInterval(load, 10_000)
    return () => {
      alive = false
      clearInterval(t)
    }
  }, [])

  const verdict = read && health ? (health.status ?? 'unknown') : 'unknown'
  const tone = verdictTone(verdict as any)
  const problem = read ? headlineProblem(health) : ''
  const feed = feedProblems(health)
  const loops = health?.loops ?? {}

  return (
    <Card className="p-3 space-y-2">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <span className="stat-label">System health</span>
          <span className={cn('text-sm font-semibold', TONE[tone])}>
            <Dot tone={tone} />
            {verdictLabel(verdict as any)}
          </span>
        </div>
        <div className="text-[11px] text-muted">
          up {uptimeLabel(health?.uptime_seconds)}
          {health?.build?.commit ? ` · ${health.build.commit}` : ''}
          {health?.engine?.provider ? ` · ${health.engine.provider}` : ''}
        </div>
      </div>

      {/* The two engine lanes. The risk lane is the one that matters for money:
          if it is stale, stops are not firing. */}
      <div className="flex gap-6 flex-wrap text-[11px]">
        {(['risk', 'signal'] as const).map((lane) => (
          <div key={lane}>
            <div className="stat-label">{lane} lane</div>
            <div className={cn('font-semibold', TONE[laneTone(loops[lane])])}>
              <Dot tone={laneTone(loops[lane])} />
              {laneAge(loops[lane])}
              {loops[lane]?.state ? ` · ${loops[lane].state}` : ''}
            </div>
          </div>
        ))}
        <div>
          <div className="stat-label">database</div>
          <div className={cn('font-semibold', health?.db?.ok ? TONE.good : TONE.bad)}>
            <Dot tone={health?.db?.ok ? 'good' : 'bad'} />
            {health?.db?.ok ? 'reachable' : 'unreachable'}
          </div>
        </div>
        {health?.markets_open !== undefined && health?.markets_open !== null && (
          <div>
            <div className="stat-label">markets</div>
            <div className="font-semibold">{health.markets_open ? 'open' : 'closed'}</div>
          </div>
        )}
      </div>

      {problem && (
        <div className={cn('text-[11px] leading-relaxed', TONE[tone])}>{problem}</div>
      )}

      {feed.length > 0 && (
        <div className="text-[11px] text-amber-400 leading-relaxed">
          <span className="font-semibold">Candle feed anomalies</span> — repaired before use,
          but worth knowing:
          <ul className="list-disc ml-4">
            {feed.map((f) => (
              <li key={f.key}>
                <span className="font-semibold">{f.key}</span>: {f.detail}
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  )
}
