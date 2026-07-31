import { describe, expect, it } from 'vitest'

import {
  contractFromSymbol, instrumentForSymbol, optionTypeFromSymbol,
} from './manualFills'

const INSTRUMENTS = [
  { id: 'nifty', code: 'NIFTY' },
  { id: 'bnf', code: 'BANKNIFTY' },
  { id: 'goldm', code: 'GOLDM' },
  { id: 'stocks', code: 'EQ' },
]

describe('mapping a Kite symbol to a journal instrument', () => {
  it('matches a Nifty option', () => {
    expect(instrumentForSymbol('NIFTY25JAN25000CE', INSTRUMENTS)).toBe('nifty')
  })

  it('prefers BANKNIFTY over NIFTY — longest code wins', () => {
    // 'BANKNIFTY...' does not start with 'NIFTY', but this guards the ordering
    // in case a code is ever a prefix of another.
    expect(instrumentForSymbol('BANKNIFTY25JAN52000PE', INSTRUMENTS)).toBe('bnf')
  })

  it('matches an MCX mini future', () => {
    expect(instrumentForSymbol('GOLDM25FEBFUT', INSTRUMENTS)).toBe('goldm')
  })

  it('returns null rather than guessing on an unknown symbol', () => {
    expect(instrumentForSymbol('RELIANCE', INSTRUMENTS)).toBeNull()
  })

  it('is case insensitive', () => {
    expect(instrumentForSymbol('nifty25jan25000ce', INSTRUMENTS)).toBe('nifty')
  })
})

describe('reading the contract kind off the symbol', () => {
  it('detects calls and puts', () => {
    expect(contractFromSymbol('NIFTY25JAN25000CE')).toBe('OPT')
    expect(contractFromSymbol('NIFTY25JAN25000PE')).toBe('OPT')
    expect(optionTypeFromSymbol('NIFTY25JAN25000CE')).toBe('CE')
    expect(optionTypeFromSymbol('NIFTY25JAN25000PE')).toBe('PE')
  })

  it('detects futures', () => {
    expect(contractFromSymbol('GOLDM25FEBFUT')).toBe('FUT')
    expect(optionTypeFromSymbol('GOLDM25FEBFUT')).toBeUndefined()
  })

  it('falls back to equity', () => {
    expect(contractFromSymbol('TCS')).toBe('EQ')
  })

  it('does not mistake an equity symbol ENDING in CE for an option', () => {
    // RELIANCE ends in "CE". A bare endsWith check files every such stock as
    // an option; the strike digit is what actually distinguishes them.
    expect(contractFromSymbol('RELIANCE')).toBe('EQ')
    expect(optionTypeFromSymbol('RELIANCE')).toBeUndefined()
  })
})
