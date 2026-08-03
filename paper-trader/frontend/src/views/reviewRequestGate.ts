/**
 * Sequencing for review requests whose responses may arrive out of order.
 *
 * A historical capture read is slow enough that a project switch, a reload, or a
 * second capture can overtake it. Without a gate the late response wins and the
 * surface shows another project's frozen review as if it were the current one.
 * Every adopt-the-response site checks `isCurrent` first; `invalidate` retires all
 * in-flight work when the surface resets.
 */
export interface RequestGate {
  current: number
}

export const createRequestGate = (): RequestGate => ({ current: 0 })

export const beginRequest = (gate: RequestGate): number => (gate.current += 1)

export const isCurrent = (gate: RequestGate, requestId: number): boolean =>
  gate.current === requestId

export const invalidate = (gate: RequestGate): void => {
  gate.current += 1
}
