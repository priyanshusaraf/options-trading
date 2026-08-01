import { describe, expect, it } from 'vitest'
import { META } from './settingsMeta'
import { DANGER_KEYS } from '../lib/settingFormat'

import { OVERRIDABLE } from './overridable'

describe('settings coverage', () => {
  it('documents every overridable knob', () => {
    const missing = OVERRIDABLE.filter((k) => !META[k])
    expect(missing, `undocumented keys: ${missing.join(', ')}`).toEqual([])
  })

  it('does not document keys the backend does not expose', () => {
    const stale = Object.keys(META).filter((k) => !OVERRIDABLE.includes(k))
    expect(stale, `stale META keys: ${stale.join(', ')}`).toEqual([])
  })

  it('every danger key is a real overridable knob', () => {
    const bogus = [...DANGER_KEYS].filter((k) => !OVERRIDABLE.includes(k))
    expect(bogus, `DANGER_KEYS not in OVERRIDABLE: ${bogus.join(', ')}`).toEqual([])
  })
})

describe('settings are explained, not merely named', () => {
  // A definition without a consequence still leaves you guessing, and these knobs move
  // real money. Every knob must say what happens when you change it, in the direction
  // you would change it.
  it('every knob explains what changes if you move it', () => {
    const noDetail = OVERRIDABLE.filter((k) => !META[k]?.detail)
    expect(noDetail, `knobs with no consequence note: ${noDetail.join(', ')}`).toEqual([])
  })

  it('help and detail say different things', () => {
    const lazy = OVERRIDABLE.filter((k) => {
      const m = META[k]
      return m?.detail && m.detail.trim() === m.help.trim()
    })
    expect(lazy, `detail merely repeats help: ${lazy.join(', ')}`).toEqual([])
  })

  it('descriptions are substantive', () => {
    const thin = OVERRIDABLE.filter((k) => (META[k]?.detail ?? '').length < 40)
    expect(thin, `too thin to be useful: ${thin.join(', ')}`).toEqual([])
  })

  it('a label never falls back to the raw key', () => {
    const raw = OVERRIDABLE.filter((k) => META[k]?.label === k)
    expect(raw, `label is just the key: ${raw.join(', ')}`).toEqual([])
  })
})
