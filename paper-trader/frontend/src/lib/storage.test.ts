import { describe, expect, it } from 'vitest'
import { growthLeaders, sizeLabel, sizeTone, storageWarning, type Storage } from './storage'

describe('size', () => {
  it('treats unknown as not-fine', () => {
    // The DB hit 108 MB unnoticed because nothing reported it. "I don't know how
    // big it is" must not render the same as "it's small".
    expect(sizeTone(undefined)).toBe('warn')
    expect(sizeLabel(undefined)).toBe('—')
  })

  it('escalates on a 1 GB box', () => {
    expect(sizeTone(50)).toBe('good')
    expect(sizeTone(350)).toBe('warn')
    expect(sizeTone(700)).toBe('bad')
  })

  it('switches units so a big number is legible', () => {
    expect(sizeLabel(108)).toBe('108.0 MB')
    expect(sizeLabel(2048)).toBe('2.00 GB')
  })
})

describe('growth leaders', () => {
  const s: Storage = {
    tables: [
      { name: 'huge_but_static', rows: 900000, rows_last_24h: 0, pruned: true },
      { name: 'small_but_exploding', rows: 500, rows_last_24h: 40000, pruned: false },
      { name: 'moderate', rows: 20000, rows_last_24h: 300, pruned: false },
    ],
  }

  it('ranks by DAILY growth, not total size', () => {
    // Total rows say what happened; daily growth says what is about to. A huge
    // table that stopped growing is a solved problem.
    expect(growthLeaders(s).map((t) => t.name)).toEqual(['small_but_exploding', 'moderate'])
  })

  it('omits tables that are not growing at all', () => {
    expect(growthLeaders(s).some((t) => t.name === 'huge_but_static')).toBe(false)
  })

  it('is empty and safe when there is no data', () => {
    expect(growthLeaders(null)).toEqual([])
    expect(growthLeaders({})).toEqual([])
  })
})

describe('warning', () => {
  it('names the incident at critical size', () => {
    expect(storageWarning({ size_mb: 700 })).toContain('OOM')
  })

  it('flags retention being off even when the DB is small', () => {
    // Small today is not the point — unbounded growth on a box with no resize is.
    expect(storageWarning({ size_mb: 10, retention: { enabled: false } })).toContain('Retention is OFF')
  })

  it('says nothing when there is nothing to say', () => {
    expect(storageWarning({ size_mb: 20, retention: { enabled: true } })).toBe('')
  })

  it('does not invent a warning from no data', () => {
    expect(storageWarning(null)).toBe('')
  })
})
