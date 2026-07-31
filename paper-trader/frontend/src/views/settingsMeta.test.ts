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
