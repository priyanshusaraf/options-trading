import { describe, expect, it } from 'vitest'

import { buildSeed } from './seed'

describe('the seed', () => {
  const db = buildSeed()

  it('ships no fabricated history', () => {
    // The source seeded ~173 generated trades to demo the evidence thresholds.
    // In a real journal those would make every statistic describe fiction.
    expect(db.trades).toHaveLength(0)
    expect(db.sessions).toHaveLength(0)
    expect(db.events).toHaveLength(0)
    expect(db.artifacts).toHaveLength(0)
  })

  it('ships the instruments the owner actually trades', () => {
    const codes = db.instruments.map((i) => i.code)
    expect(codes).toContain('NIFTY')
    expect(codes).toContain('BNF')
  })

  it('carries the owner-confirmed lot sizes', () => {
    // Confirmed 2026-07-31. A wrong lot size silently mis-scales every R figure
    // without ever erroring, so it is pinned by a test rather than a comment.
    const by = Object.fromEntries(db.instruments.map((i) => [i.id, i.lotSize]))
    expect(by.nifty).toBe(65)
    expect(by.bnf).toBe(30)
  })

  it('gives every instrument an R basis, because riskPerR returns null without one', () => {
    for (const i of db.instruments) expect(i.rBasis).toBeTruthy()
  })

  it('keeps the route target resolvable, or eight surfaces render null', async () => {
    // uiState hard-codes the landing instrument. If the seed ever stops
    // shipping it, Cockpit/Blotter/Stats/Playbook/Notebook/Timeline/Vault/Review
    // all `return null` and there is no UI anywhere to create an instrument.
    const { getUI } = await import('../app/uiState')
    const ids = db.instruments.map((i) => i.id)
    expect(ids).toContain(getUI().route.instrumentId)
  })

  it('ships a playbook, because setup attribution is mandatory', () => {
    expect(db.playbook.length).toBeGreaterThan(0)
  })

  it('keeps the evidence threshold at 20', () => {
    expect(db.settings.evidenceThreshold).toBe(20)
  })

  it('ships the mistake and emotion taxonomies', () => {
    expect(db.settings.mistakes.length).toBeGreaterThan(0)
    expect(db.settings.emotions.length).toBeGreaterThan(0)
  })
})
