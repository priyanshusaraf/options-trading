import { describe, expect, it } from 'vitest'
import {
  feedProblems, headlineProblem, laneAge, laneTone, uptimeLabel,
  verdictLabel, verdictTone, type Health,
} from './health'

describe('verdict', () => {
  it('treats unknown as NOT healthy', () => {
    // The probe failing to answer is not evidence that things are fine — that
    // conflation is exactly what made the old liveness stub useless.
    expect(verdictTone(undefined)).toBe('warn')
    expect(verdictLabel(undefined)).toBe('Unknown')
  })

  it('only ok is good, only unready is bad', () => {
    expect(verdictTone('ok')).toBe('good')
    expect(verdictTone('unready')).toBe('bad')
    expect(verdictTone('degraded')).toBe('warn')
    expect(verdictTone('starting')).toBe('warn')
  })
})

describe('lane age', () => {
  it('never renders a never-beaten lane as a number', () => {
    // "0s" would read as "beat just now" — the exact inversion of the truth.
    expect(laneAge({ age_seconds: null, state: 'dead', budget_seconds: 90, fatal: true }))
      .toBe('never')
  })

  it('calls an expected silence idle, not never', () => {
    expect(laneAge({ age_seconds: null, state: 'idle', budget_seconds: 600, fatal: false }))
      .toBe('idle')
  })

  it('scales units so a stalled lane is legible at a glance', () => {
    const L = (s: number) => laneAge({ age_seconds: s, state: 'ok', budget_seconds: 90, fatal: true })
    expect(L(0.4)).toBe('<1s')
    expect(L(12)).toBe('12s')
    expect(L(300)).toBe('5m')
    expect(L(7200)).toBe('2.0h')
  })

  it('is bad only when the stalled lane is the one that matters for money', () => {
    const stale = (fatal: boolean) => laneTone({ age_seconds: 999, state: 'stale', budget_seconds: 90, fatal })
    expect(stale(true)).toBe('bad')     // risk lane: stops are not firing
    expect(stale(false)).toBe('warn')   // signal lane: no new entries, not an emergency
  })

  it('does not call an overnight-idle signal lane a failure', () => {
    expect(laneTone({ age_seconds: 9000, state: 'idle', budget_seconds: 600, fatal: false }))
      .toBe('warn')
  })
})

describe('headline problem', () => {
  const h = (checks: Health['checks']): Health => ({ checks })

  it('prefers a fatal check and shows the probe’s own sentence', () => {
    expect(headlineProblem(h([
      { name: 'provider_auth', ok: false, fatal: false, detail: 'token rejected' },
      { name: 'risk_lane', ok: false, fatal: true, detail: 'risk loop is stale — no SL/TP' },
    ]))).toBe('risk loop is stale — no SL/TP')
  })

  it('falls back to a non-fatal complaint', () => {
    expect(headlineProblem(h([
      { name: 'provider_auth', ok: false, fatal: false, detail: 'token rejected' },
    ]))).toBe('token rejected')
  })

  it('says nothing when nothing is wrong', () => {
    expect(headlineProblem(h([{ name: 'database', ok: true, fatal: true, detail: '' }]))).toBe('')
  })

  it('does not claim health when the probe could not be read', () => {
    expect(headlineProblem(null)).toBe('Health could not be read')
  })
})

describe('feed problems', () => {
  it('lists anomalous instruments', () => {
    const out = feedProblems({ provider_feed: { NIFTY: { detail: '2 duplicates', at: 'x' } } })
    expect(out).toEqual([{ key: 'NIFTY', detail: '2 duplicates' }])
  })

  it('is empty when the feed is clean or absent', () => {
    expect(feedProblems({})).toEqual([])
    expect(feedProblems(null)).toEqual([])
  })
})

describe('uptime', () => {
  it('scales', () => {
    expect(uptimeLabel(30)).toBe('30s')
    expect(uptimeLabel(600)).toBe('10m')
    expect(uptimeLabel(7200)).toBe('2.0h')
    expect(uptimeLabel(172800)).toBe('2.0d')
    expect(uptimeLabel(undefined)).toBe('—')
  })
})
