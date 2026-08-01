import { describe, expect, it } from 'vitest'

/**
 * 390px layout guards.
 *
 * The roadmap carried "mobile 390px one-handed check" as NEVER VERIFIED. Doing
 * it found the app in better shape than that implied — there is a dedicated
 * MobileTopBar with drawer navigation, and the dense tables already sit in
 * horizontal scroll containers. One did not: OptionsCalcView's 6-column option
 * chain, which would have pushed the whole page body sideways on a phone.
 *
 * So the lasting value is the REGRESSION guard rather than the fix. A raw
 * <table> added later without a scroll wrapper breaks silently: it looks fine on
 * the laptop where it was written, and nobody opens the phone until the morning
 * they need to close a position from it.
 *
 * Uses import.meta.glob rather than node:fs so it needs no Node type
 * declarations — the frontend tsconfig does not ship them, and adding a
 * dependency to run a lint-shaped test would be the wrong trade.
 */
const SOURCES = {
  ...import.meta.glob('./*.tsx', { query: '?raw', import: 'default', eager: true }),
  ...import.meta.glob('../components/*.tsx', { query: '?raw', import: 'default', eager: true }),
} as Record<string, string>

const APP = import.meta.glob('../App.tsx', {
  query: '?raw', import: 'default', eager: true,
}) as Record<string, string>

describe('390px: wide content must scroll inside itself', () => {
  it('every raw <table> lives in a horizontal scroll container', () => {
    const offenders = Object.entries(SOURCES)
      .filter(([, body]) => body.includes('<table'))
      .filter(([, body]) => !/overflow-auto|overflow-x-auto/.test(body))
      .map(([path]) => path.split('/').pop())
    expect(offenders, `tables with no scroll wrapper: ${offenders.join(', ')}`).toEqual([])
  })

  it('multi-stat rows wrap rather than overflowing', () => {
    // A flex row of stats at gap-6 with no wrap is the other reliable way to
    // push a phone's body sideways.
    const offenders = Object.entries(SOURCES)
      .filter(([, body]) => /flex items-center gap-6(?![^\n]*flex-wrap)/.test(body))
      .map(([path]) => path.split('/').pop())
    expect(offenders, `unwrapped wide flex rows: ${offenders.join(', ')}`).toEqual([])
  })
})

describe('390px: the phone gets its own header', () => {
  it('a mobile top bar exists and is wired into the shell', () => {
    expect(Object.values(APP)[0]).toContain('MobileTopBar')
  })
})
