import { describe, expect, it } from 'vitest'
import { createRequestGate, beginRequest, isCurrent, invalidate } from './reviewRequestGate'

describe('reviewRequestGate', () => {
  it('adopts only the newest response when requests resolve out of order', () => {
    const gate = createRequestGate()

    const first = beginRequest(gate)
    const second = beginRequest(gate)

    // The slower first request resolves last and must be discarded.
    expect(isCurrent(gate, second)).toBe(true)
    expect(isCurrent(gate, first)).toBe(false)
  })

  it('discards every in-flight response after an explicit invalidation', () => {
    const gate = createRequestGate()
    const inFlight = beginRequest(gate)

    // A project switch invalidates work belonging to the previous project.
    invalidate(gate)

    expect(isCurrent(gate, inFlight)).toBe(false)
    const reissued = beginRequest(gate)
    expect(isCurrent(gate, reissued)).toBe(true)
  })

  it('keeps a single request current across repeated checks', () => {
    const gate = createRequestGate()
    const only = beginRequest(gate)

    expect(isCurrent(gate, only)).toBe(true)
    expect(isCurrent(gate, only)).toBe(true)
  })
})
