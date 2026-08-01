/**
 * Presentation logic for the /api/health readiness probe.
 *
 * The backend gained a real readiness probe on 2026-08-01 — DB reachability,
 * both engine loop heartbeat ages, provider auth, and candle-feed anomalies —
 * and none of it was visible anywhere in the app. Observability that only
 * exists via `curl` is observability the person who needs it at 09:20 does not
 * have.
 *
 * Pure and separate from the component so the judgement calls below are
 * testable, because they are the parts that can mislead.
 */

export type Verdict = 'ok' | 'starting' | 'degraded' | 'unready' | 'unknown'

export interface HealthLoop {
  age_seconds: number | null
  state: string
  budget_seconds: number
  fatal: boolean
}

export interface Health {
  ok?: boolean
  status?: Verdict
  ready?: boolean
  uptime_seconds?: number
  db?: { ok: boolean; error: string }
  loops?: Record<string, HealthLoop>
  markets_open?: boolean | null
  failed_checks?: string[]
  degraded_checks?: string[]
  checks?: { name: string; ok: boolean; fatal: boolean; detail: string }[]
  engine?: { present: boolean; armed?: boolean; provider?: string }
  provider_feed?: Record<string, { detail: string; at: string }>
  build?: { commit?: string; branch?: string; deployed_at?: string }
}

/** Tone for the headline badge. `unknown` is deliberately NOT treated as fine. */
export function verdictTone(v: Verdict | undefined): 'good' | 'warn' | 'bad' {
  if (v === 'ok') return 'good'
  if (v === 'unready') return 'bad'
  // starting / degraded / unknown all mean "do not assume this is healthy".
  return 'warn'
}

export function verdictLabel(v: Verdict | undefined): string {
  switch (v) {
    case 'ok': return 'Healthy'
    case 'starting': return 'Starting'
    case 'degraded': return 'Degraded'
    case 'unready': return 'NOT READY'
    default: return 'Unknown'
  }
}

/**
 * A lane's heartbeat age, for humans.
 *
 * `null` means the lane has NEVER beaten, which is a different fact from
 * "beat a long time ago" and must not render as a number — "0s" would read as
 * "just now", the exact inversion of the truth.
 */
export function laneAge(loop: HealthLoop | undefined): string {
  if (!loop) return '—'
  if (loop.age_seconds === null || loop.age_seconds === undefined) {
    return loop.state === 'idle' ? 'idle' : 'never'
  }
  const s = loop.age_seconds
  if (s < 1) return '<1s'
  if (s < 90) return `${Math.round(s)}s`
  if (s < 3600) return `${Math.round(s / 60)}m`
  return `${(s / 3600).toFixed(1)}h`
}

export function laneTone(loop: HealthLoop | undefined): 'good' | 'warn' | 'bad' {
  if (!loop) return 'warn'
  if (loop.state === 'ok') return 'good'
  if (loop.state === 'idle' || loop.state === 'starting') return 'warn'
  // stale / dead: bad only when it is the lane that matters for money.
  return loop.fatal ? 'bad' : 'warn'
}

/**
 * The one line to show when something is wrong.
 *
 * Prefers a FATAL check's own detail over a generic summary: the probe already
 * writes a sentence explaining each failure, and re-summarising it would lose
 * the specifics that make it actionable.
 */
export function headlineProblem(h: Health | null | undefined): string {
  if (!h) return 'Health could not be read'
  const checks = h.checks ?? []
  const fatal = checks.find((c) => !c.ok && c.fatal)
  if (fatal) return fatal.detail || fatal.name
  const soft = checks.find((c) => !c.ok && !c.fatal)
  if (soft) return soft.detail || soft.name
  return ''
}

/** Instruments whose candle feed is currently anomalous. */
export function feedProblems(h: Health | null | undefined): { key: string; detail: string }[] {
  const feed = h?.provider_feed ?? {}
  return Object.entries(feed).map(([key, v]) => ({ key, detail: v?.detail ?? '' }))
}

export function uptimeLabel(seconds: number | undefined): string {
  if (seconds === undefined || seconds === null) return '—'
  if (seconds < 60) return `${Math.round(seconds)}s`
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`
  if (seconds < 86400) return `${(seconds / 3600).toFixed(1)}h`
  return `${(seconds / 86400).toFixed(1)}d`
}
