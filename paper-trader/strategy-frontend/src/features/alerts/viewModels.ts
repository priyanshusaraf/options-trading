export type AlertAction = 'BUY' | 'SELL' | 'EXIT'
export type TargetState = 'LONG' | 'SHORT' | 'FLAT'
export type AlertEvidenceState = 'FRESH' | 'STALE' | 'EXPIRED' | 'UNKNOWN'
export type AttentionAction = 'READ' | 'ACKNOWLEDGE' | 'DISMISS'

export type ResearchProtection = Readonly<{
  status: 'DISABLED' | 'UNRESOLVED' | 'RESOLVED'
  rules: readonly Readonly<{ basis: 'FRACTION_FROM_SIMULATED_ENTRY' | 'ATR_RATCHET_STOP'; fraction: number | null; resolvedValue: string | null; definitionAddress: string }>[]
}>
export type ProtectionLevel = ResearchProtection | Readonly<{
  basis: string
  authoredValue: string
  units: string
  resolvedValue: string | null
}>

export type AlertAttention = Readonly<{
  lastSequence: number
  isUnread: boolean
  readAt: string | null
  acknowledgedAt: string | null
  dismissedAt: string | null
}>

export type SignalAlertViewModel = Readonly<{
  alertAddress: string
  strategyReference?: string
  graphVersionAddress?: string
  assignmentId: string
  monitoringEventAddress: string
  action: AlertAction
  displaySymbol: string
  previousState: TargetState
  targetState: TargetState
  eventLabel: string
  validUntilLabel: string
  evidenceState: AlertEvidenceState
  entryReferenceKind: string
  entryReferenceValue: string | null
  entryReferenceCurrency: string
  stopLoss: ProtectionLevel
  takeProfit: ProtectionLevel
  attention: AlertAttention
  researchDecision?: Readonly<{ consumerAddress: string; kind: 'ENTER' | 'REVERSE' | 'EXIT'; simulatedPosition: TargetState }>
}>

export type AlertFilter = 'ALL' | 'UNREAD' | 'ACTIVE'
export type InboxState =
  | Readonly<{ kind: 'READY' }>
  | Readonly<{ kind: 'LOADING' }>
  | Readonly<{ kind: 'ERROR' | 'OFFLINE'; message: string }>

export type ReviewReason = Readonly<{ code: string; label: string }>
export type SignalReviewDraft = Readonly<{
  disposition: 'CONFIRMED' | 'REJECTED'
  reasonCode: string
  note: string
}>

export type SignalReviewViewModel = Readonly<SignalReviewDraft & {
  reviewAddress: string
  createdLabel: string
}>

export const SAFETY_COPY = 'Monitoring alert only. Entry reference is not a fill. SL and TP are strategy levels, not placed orders or exchange protection.'

export function alertTitle(alert: SignalAlertViewModel): string {
  return `${alert.action} ${alert.displaySymbol} · target state ${alert.targetState}`
}

export function levelValue(value: string | null): string {
  return value ?? 'Level unavailable — no value inferred'
}

export function protectionValue(value: ProtectionLevel): string {
  if (!('status' in value)) return levelValue(value.resolvedValue)
  if (value.status === 'DISABLED') return 'Not configured'
  if (value.status === 'UNRESOLVED') return 'After simulated entry'
  return value.rules.map((rule) => levelValue(rule.resolvedValue)).join(' · ')
}

export function evidenceLabel(state: AlertEvidenceState): string {
  if (state === 'STALE') return 'Stale monitoring evidence'
  if (state === 'EXPIRED') return 'Alert expired'
  if (state === 'UNKNOWN') return 'Monitoring evidence unavailable'
  return 'Fresh monitoring evidence'
}

export function reviewNoteError(note: string): string | null {
  if (new TextEncoder().encode(note).length > 4096) return 'Shorten the note to 4096 UTF-8 bytes.'
  if (/[\u0000-\u001f\u007f]/u.test(note)) return 'Use one paragraph without line breaks, tabs or control characters.'
  if (note !== note.trim() || /^\u0085|\u0085$/u.test(note)) return 'Remove whitespace at the beginning or end of the note.'
  if (Array.from(note).some((character) => { const point = character.codePointAt(0)!; return point >= 0xd800 && point <= 0xdfff })) return 'Remove incomplete Unicode characters from the note.'
  return null
}
