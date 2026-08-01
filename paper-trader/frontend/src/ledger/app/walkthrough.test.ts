import { beforeEach, describe, expect, it } from 'vitest'
import {
  WALKTHROUGH,
  loadProgress,
  resetProgress,
  saveProgress,
} from './walkthrough'

// The surfaces the router can actually render (App.tsx SurfaceFor). A walkthrough step
// pointing at a surface that no longer exists sends the reader to a blank screen, which
// is worse than having no walkthrough at all.
const SURFACES = new Set([
  'cockpit', 'notebook', 'blotter', 'trade', 'timeline', 'playbook', 'stats',
  'review', 'vault', 'search', 'inbox', 'weekly', 'settings', 'guide',
])

describe('walkthrough content', () => {
  it('is short enough to finish before the market opens', () => {
    expect(WALKTHROUGH.length).toBeGreaterThanOrEqual(4)
    expect(WALKTHROUGH.length).toBeLessThanOrEqual(8)
  })

  it('every step points at a surface that exists', () => {
    const broken = WALKTHROUGH
      .filter((s) => s.surface && !SURFACES.has(s.surface))
      .map((s) => `${s.id} → ${s.surface}`)
    expect(broken, `steps pointing nowhere: ${broken.join(', ')}`).toEqual([])
  })

  it('every step says WHY, not just what', () => {
    // The complaint that produced this was not "I cannot find the buttons", it was
    // "I do not know what this is for".
    for (const s of WALKTHROUGH) {
      expect(s.why.length, `${s.id} has no real rationale`).toBeGreaterThan(60)
      expect(s.action.length, `${s.id} has no concrete action`).toBeGreaterThan(20)
    }
  })

  it('has unique step ids', () => {
    expect(new Set(WALKTHROUGH.map((s) => s.id)).size).toBe(WALKTHROUGH.length)
  })

  it('opens by explaining the point and ends by saying the rest is optional', () => {
    expect(WALKTHROUGH[0].id).toBe('what')
    expect(WALKTHROUGH[WALKTHROUGH.length - 1].id).toBe('rest')
  })
})

// The suite runs in the node environment (no DOM), so stub the one browser API the
// progress store touches rather than pulling in jsdom for six assertions.
class MemoryStorage {
  private m = new Map<string, string>()
  getItem(k: string) { return this.m.has(k) ? this.m.get(k)! : null }
  setItem(k: string, v: string) { this.m.set(k, String(v)) }
  removeItem(k: string) { this.m.delete(k) }
  clear() { this.m.clear() }
}

describe('walkthrough progress', () => {
  beforeEach(() => {
    ;(globalThis as any).localStorage = new MemoryStorage()
  })

  it('starts at the beginning and unfinished', () => {
    expect(loadProgress()).toEqual({ step: 0, done: false })
  })

  it('resumes where you stopped', () => {
    saveProgress({ step: 2, done: false })
    expect(loadProgress()).toEqual({ step: 2, done: false })
  })

  it('remembers that you finished, so it never reopens itself', () => {
    saveProgress({ step: 0, done: true })
    expect(loadProgress().done).toBe(true)
  })

  it('clamps a stale index from a longer previous walkthrough', () => {
    // Otherwise a shipped change to the step list leaves the user on a blank screen.
    saveProgress({ step: 99, done: false })
    expect(loadProgress().step).toBe(WALKTHROUGH.length - 1)
  })

  it('survives corrupt storage rather than throwing on boot', () => {
    localStorage.setItem('pt.ledger.walkthrough', 'not json')
    expect(loadProgress()).toEqual({ step: 0, done: false })
  })

  it('can be reset so it is re-openable, not one-shot', () => {
    saveProgress({ step: 4, done: true })
    resetProgress()
    expect(loadProgress()).toEqual({ step: 0, done: false })
  })
})
