import { ContractError, type BrowserIdentity, type ReleaseManifest } from '../../shell/contracts'
import type { AlertAttention, AlertFilter, AttentionAction, ProtectionLevel, ResearchProtection, SignalAlertViewModel, SignalReviewDraft, SignalReviewViewModel } from './viewModels'
import { reviewNoteError } from './viewModels'

const ADDRESS = /^sha256:[0-9a-f]{64}$/
const IDENTIFIER = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/
const DECIMAL = /^(?:0|[1-9][0-9]*)(?:\.[0-9]*[1-9])?$/
const ALERT_FIELDS = ['schema', 'alert_address', 'assignment_id', 'monitoring_event_address', 'strategy_id', 'graph_version_address', 'last_sequence', 'action', 'display_symbol', 'previous_state', 'target_state', 'event_at', 'valid_until', 'freshness', 'entry_reference_kind', 'entry_reference_value', 'entry_reference_currency', 'stop_loss_basis', 'stop_loss_authored_value', 'stop_loss_units', 'stop_loss_resolved_value', 'take_profit_basis', 'take_profit_authored_value', 'take_profit_units', 'take_profit_resolved_value', 'is_unread', 'read_at', 'acknowledged_at', 'dismissed_at']
const RESEARCH_ALERT_FIELDS = [...ALERT_FIELDS.filter((key) => !key.startsWith('stop_loss_') && !key.startsWith('take_profit_')), 'consumer_address', 'simulated_position_state', 'decision_kind', 'stop_loss', 'take_profit']
const REVIEW_FIELDS = ['review_address', 'assignment_id', 'monitoring_event_address', 'disposition', 'reason_code', 'note', 'created_at']
function requireValue(value: unknown): asserts value { if (!value) throw new ContractError() }
function closed(input: unknown, names: readonly string[]) {
  requireValue(input !== null && typeof input === 'object' && !Array.isArray(input))
  const value = input as Record<string, unknown>
  requireValue(Object.keys(value).length === names.length && names.every((name) => Object.hasOwn(value, name)))
  return value
}
function text(value: unknown, max = 128) { requireValue(typeof value === 'string' && value.length > 0 && value.length <= max && value === value.trim() && !/[\u0000-\u001f\u007f]/u.test(value)); return value }
export function monitoringAddress(value: unknown) { const result = text(value, 71); requireValue(ADDRESS.test(result)); return result }
export function monitoringIdentifier(value: unknown) { const result = text(value); requireValue(IDENTIFIER.test(result)); return result }
export function monitoringCursor(value: unknown): string | null { if (value === null) return null; const result = text(value, 2048); requireValue(/^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$/.test(result)); return result }
function choice<T extends string>(value: unknown, options: readonly T[]): T { requireValue(typeof value === 'string' && options.includes(value as T)); return value as T }
function sequence(value: unknown) { requireValue(typeof value === 'number' && Number.isSafeInteger(value) && value >= 0); return value }
function boolean(value: unknown) { requireValue(typeof value === 'boolean'); return value }
function time(value: unknown) {
  const result = text(value, 40), match = /^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(?:\.(\d{1,6}))?(?:Z|\+00:00)$/.exec(result)
  requireValue(match && Number.isFinite(Date.parse(result)) && new Date(result).toISOString().slice(0, 19) === match[1])
  return `${match[1]}.${(match[2] ?? '').padEnd(6, '0')}Z`
}
function optionalTime(value: unknown) { return value === null ? null : time(value) }
function decimal(value: unknown) { const result = text(value, 128); requireValue(DECIMAL.test(result)); return result }
function attention(value: Record<string, unknown>): AlertAttention {
  const result = Object.freeze({ lastSequence: sequence(value.last_sequence), isUnread: boolean(value.is_unread), readAt: optionalTime(value.read_at), acknowledgedAt: optionalTime(value.acknowledged_at), dismissedAt: optionalTime(value.dismissed_at) })
  requireValue(result.isUnread === (result.lastSequence === 0))
  const stamps = [result.readAt, result.acknowledgedAt, result.dismissedAt]
  requireValue(result.lastSequence === 0 ? stamps.every((stamp) => stamp === null) : stamps.some((stamp) => stamp !== null))
  return result
}
function protection(value: Record<string, unknown>, prefix: 'stop_loss' | 'take_profit') {
  return Object.freeze({ basis: choice(value[`${prefix}_basis`], ['ABSOLUTE_PRICE', 'PERCENT_FROM_ENTRY_REFERENCE', 'DISTANCE_FROM_ENTRY_REFERENCE', 'VERIFIED_INDICATOR_DISTANCE']), authoredValue: decimal(value[`${prefix}_authored_value`]), units: choice(value[`${prefix}_units`], ['PRICE', 'RATE', 'PRICE_POINTS']), resolvedValue: decimal(value[`${prefix}_resolved_value`]) })
}
function researchRule(input: unknown) {
  const value = closed(input, ['basis', 'fraction', 'resolved_value', 'definition_address'])
  const basis = choice(value.basis, ['FRACTION_FROM_SIMULATED_ENTRY', 'ATR_RATCHET_STOP'])
  const fraction = value.fraction
  requireValue(basis === 'ATR_RATCHET_STOP' ? fraction === null : typeof fraction === 'number' && Number.isFinite(fraction) && fraction > 0 && fraction < 1)
  const resolved = value.resolved_value
  requireValue(resolved === null || typeof resolved === 'number' && Number.isFinite(resolved))
  return Object.freeze({ basis, fraction: fraction as number | null, resolvedValue: resolved === null ? null : String(resolved), definitionAddress: monitoringAddress(value.definition_address) })
}
function researchProtection(input: unknown, stop: boolean, unresolved: boolean): ResearchProtection {
  const value = closed(input, ['status', 'rules'])
  const status = choice(value.status, ['DISABLED', 'UNRESOLVED', 'RESOLVED'])
  requireValue(Array.isArray(value.rules) && value.rules.length <= (stop ? 2 : 1))
  const rules = value.rules.map(researchRule), bases = rules.map((rule) => rule.basis).join(',')
  requireValue(['', 'FRACTION_FROM_SIMULATED_ENTRY', ...(stop ? ['ATR_RATCHET_STOP', 'FRACTION_FROM_SIMULATED_ENTRY,ATR_RATCHET_STOP'] : [])].includes(bases))
  requireValue(status === (rules.length === 0 ? 'DISABLED' : unresolved ? 'UNRESOLVED' : 'RESOLVED'))
  requireValue(rules.every((rule) => (rule.resolvedValue === null) === unresolved))
  return Object.freeze({ status, rules: Object.freeze(rules) })
}
function researchDecision(value: Record<string, unknown>, target: string) {
  const kind = choice(value.decision_kind, ['ENTER', 'REVERSE', 'EXIT'])
  const simulatedPosition = choice(value.simulated_position_state, ['FLAT', 'LONG', 'SHORT'])
  requireValue(kind === 'EXIT' ? target === 'FLAT' && simulatedPosition !== 'FLAT'
    : target !== 'FLAT' && target !== simulatedPosition && (simulatedPosition === 'FLAT') === (kind === 'ENTER'))
  return Object.freeze({ kind, simulatedPosition, consumerAddress: monitoringAddress(value.consumer_address) })
}
export type MonitoringAlert = Readonly<{
  facts: Omit<SignalAlertViewModel, 'evidenceState' | 'eventLabel' | 'validUntilLabel'>
  eventAt: string; validUntil: string; freshness: 'FRESH' | 'STALE'; strategyId: string; graphVersionAddress: string
}>
function alertVariant(input: unknown) {
  const research = input !== null && typeof input === 'object' && 'schema' in input && input.schema === 'monitoring-research-alert-read/1'
  const value = closed(input, research ? RESEARCH_ALERT_FIELDS : ALERT_FIELDS); requireValue(research || value.schema === 'monitoring-alert-read/2')
  return { research, value }
}
function decisionFacts(value: Record<string, unknown>, research: boolean) {
  const action = choice(value.action, ['BUY', 'SELL', 'EXIT']), targetState = choice(value.target_state, ['FLAT', 'LONG', 'SHORT']), previousState = choice(value.previous_state, ['FLAT', 'LONG', 'SHORT'])
  requireValue(targetState === ({ BUY: 'LONG', SELL: 'SHORT', EXIT: 'FLAT' } as const)[action] && (research || previousState !== targetState))
  if (!research) return { action, targetState, previousState, stopLoss: protection(value, 'stop_loss'), takeProfit: protection(value, 'take_profit') }
  const decision = researchDecision(value, targetState)
  const unresolved = decision.simulatedPosition === 'FLAT' || decision.kind === 'ENTER' || decision.kind === 'REVERSE'
  return { action, targetState, previousState, researchDecision: decision,
    stopLoss: researchProtection(value.stop_loss, true, unresolved), takeProfit: researchProtection(value.take_profit, false, unresolved) }
}
export function parseMonitoringAlert(input: unknown): MonitoringAlert {
  const { research, value } = alertVariant(input), decision = decisionFacts(value, research)
  const eventAt = time(value.event_at), validUntil = time(value.valid_until), seen = attention(value)
  requireValue(validUntil >= eventAt && [seen.readAt, seen.acknowledgedAt, seen.dismissedAt].every((stamp) => stamp === null || stamp >= eventAt))
  const currency = text(value.entry_reference_currency, 3); requireValue(/^[A-Z]{3}$/.test(currency))
  return Object.freeze({ eventAt, validUntil, freshness: choice(value.freshness, ['FRESH', 'STALE']), strategyId: monitoringIdentifier(value.strategy_id), graphVersionAddress: monitoringAddress(value.graph_version_address),
    facts: Object.freeze({ alertAddress: monitoringAddress(value.alert_address), assignmentId: monitoringIdentifier(value.assignment_id), monitoringEventAddress: monitoringAddress(value.monitoring_event_address), ...decision, displaySymbol: text(value.display_symbol, 64),
      entryReferenceKind: choice(value.entry_reference_kind, ['COMPLETED_EVENT_CLOSE']), entryReferenceValue: decimal(value.entry_reference_value), entryReferenceCurrency: currency,
      attention: seen }) })
}
function requireAttentionProgress(before: AlertAttention, after: AlertAttention) {
  requireValue(after.lastSequence >= before.lastSequence)
  if (after.lastSequence === before.lastSequence) requireValue(JSON.stringify(after) === JSON.stringify(before))
  for (const key of ['readAt', 'acknowledgedAt', 'dismissedAt'] as const) requireValue(before[key] === null || after[key] === before[key])
}
export function verifyMonitoringDetail(input: unknown, expected: MonitoringAlert) {
  const actual = parseMonitoringAlert(input)
  const immutable = (item: MonitoringAlert) => JSON.stringify({ ...item, facts: { ...item.facts, attention: null } })
  requireValue(immutable(actual) === immutable(expected)); requireAttentionProgress(expected.facts.attention, actual.facts.attention)
  return actual
}
export function parseMonitoringPage(input: unknown, unreadOnly: boolean) {
  const value = closed(input, ['schema', 'items', 'next_cursor']); requireValue(value.schema === 'monitoring-alert-page/2' && Array.isArray(value.items) && value.items.length <= 100)
  const items = value.items.map(parseMonitoringAlert), nextCursor = monitoringCursor(value.next_cursor)
  requireValue(nextCursor === null || items.length === 100)
  requireValue(!unreadOnly || items.every((item) => item.facts.attention.isUnread))
  const identities = items.map((item) => item.facts.alertAddress); requireValue(new Set(identities).size === identities.length)
  requireValue(items.every((item, index) => index === 0 || item.eventAt < items[index - 1].eventAt || (item.eventAt === items[index - 1].eventAt && item.facts.alertAddress < items[index - 1].facts.alertAddress)))
  return Object.freeze({ items: Object.freeze(items), nextCursor })
}
export type MonitoringPage = ReturnType<typeof parseMonitoringPage>
export function alertView(item: MonitoringAlert, now: number): SignalAlertViewModel {
  const evidenceState = Date.parse(item.validUntil) <= now ? 'EXPIRED' : Date.parse(item.eventAt) > now ? 'UNKNOWN' : item.freshness
  const label = (stamp: string) => new Date(stamp).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })
  const readable = (value: string) => value.toLowerCase().replaceAll('_', ' ')
  const level = (value: ProtectionLevel): ProtectionLevel => 'status' in value ? value : ({ ...value, basis: readable(value.basis), units: value.units === 'RATE' ? 'fraction' : readable(value.units) })
  return { ...item.facts, entryReferenceKind: 'Completed candle close', stopLoss: level(item.facts.stopLoss), takeProfit: level(item.facts.takeProfit), evidenceState, eventLabel: label(item.eventAt), validUntilLabel: label(item.validUntil), strategyReference: item.strategyId, graphVersionAddress: item.graphVersionAddress }
}
export function matchesAlertFilter(item: MonitoringAlert, filter: AlertFilter, now: number) {
  if (filter === 'UNREAD') return item.facts.attention.isUnread
  if (filter === 'ACTIVE') return alertView(item, now).evidenceState === 'FRESH' && item.facts.attention.dismissedAt === null
  return true
}
export function alertsEnabled(manifest: ReleaseManifest) { const value = manifest.capabilities.signals; return Boolean(value?.ui_navigation && ['ENABLED', 'ENABLED_WITH_LIMIT'].includes(value.state)) }
export function canReviewAlerts(identity: BrowserIdentity) { return identity.memberships.some((item) => item.organization_id === identity.organization_id && ['owner', 'admin', 'member'].includes(item.role)) }
export function monitoringAlertPath(assignmentId: string, alertAddress: string) { return `monitoring/assignments/${encodeURIComponent(monitoringIdentifier(assignmentId))}/alerts/${encodeURIComponent(monitoringAddress(alertAddress))}` }
export function monitoringListPath(cursor: string | null, unreadOnly: boolean) {
  const query = new URLSearchParams({ limit: '100' }); if (unreadOnly) query.set('unread_only', 'true'); const checked = monitoringCursor(cursor); if (checked) query.set('cursor', checked)
  return `monitoring/alerts?${query}`
}
export function attentionBody(action: AttentionAction, expectedSequence: number) { requireValue(sequence(expectedSequence) <= 2_147_483_647); return { action: choice(action, ['READ', 'ACKNOWLEDGE', 'DISMISS']), expected_sequence: expectedSequence } }
export function reviewBody(draft: SignalReviewDraft) {
  requireValue(typeof draft.reasonCode === 'string' && typeof draft.note === 'string')
  requireValue(/^[A-Z][A-Z0-9_]{0,63}$/.test(draft.reasonCode) && reviewNoteError(draft.note) === null)
  return { disposition: choice(draft.disposition, ['CONFIRMED', 'REJECTED']), reason_code: draft.reasonCode, note: draft.note }
}
function requireMutationSequence(occurred: string, eventAt: string, actual: number, expected: number, replayed: boolean) {
  requireValue(occurred >= eventAt && actual >= expected + 1 && (replayed || actual === expected + 1))
}
export function parseAttentionMutation(input: unknown, alert: MonitoringAlert, action: AttentionAction, expectedSequence: number): AlertAttention {
  requireValue(expectedSequence === alert.facts.attention.lastSequence && expectedSequence <= 2_147_483_647)
  const value = closed(input, ['schema', 'attention_event_address', 'request_id', 'assignment_id', 'alert_address', 'sequence', 'action', 'occurred_at', 'replayed', 'last_sequence', 'is_unread', 'read_at', 'acknowledged_at', 'dismissed_at'])
  requireValue(value.schema === 'monitoring-attention-mutation-read/1' && value.assignment_id === alert.facts.assignmentId && value.alert_address === alert.facts.alertAddress && choice(value.action, ['READ', 'ACKNOWLEDGE', 'DISMISS']) === action && sequence(value.sequence) === expectedSequence + 1)
  monitoringAddress(value.attention_event_address); monitoringAddress(value.request_id); const occurred = time(value.occurred_at), replayed = boolean(value.replayed), result = attention(value)
  requireMutationSequence(occurred, alert.eventAt, result.lastSequence, expectedSequence, replayed)
  const field = ({ READ: 'readAt', ACKNOWLEDGE: 'acknowledgedAt', DISMISS: 'dismissedAt' } as const)[action]
  requireValue(result[field] !== null)
  requireAttentionProgress(alert.facts.attention, result)
  if (alert.facts.attention[field] === null) requireValue(result[field] === occurred)
  requireValue([result.readAt, result.acknowledgedAt, result.dismissedAt].every((stamp) => stamp === null || stamp >= alert.eventAt))
  return result
}
function review(value: Record<string, unknown>, alert: MonitoringAlert): SignalReviewViewModel {
  requireValue(value.assignment_id === alert.facts.assignmentId && value.monitoring_event_address === alert.facts.monitoringEventAddress)
  const draft = { disposition: choice(value.disposition, ['CONFIRMED', 'REJECTED']), reasonCode: text(value.reason_code, 64), note: value.note }
  requireValue(typeof draft.note === 'string'); reviewBody(draft as SignalReviewDraft)
  return Object.freeze({ ...draft as SignalReviewDraft, reviewAddress: monitoringAddress(value.review_address), createdLabel: time(value.created_at) })
}
export function parseOwnReview(input: unknown, alert: MonitoringAlert) {
  const value = closed(input, ['schema', 'review']); requireValue(value.schema === 'monitoring-review-read/1')
  return value.review === null ? null : review(closed(value.review, REVIEW_FIELDS), alert)
}
export function parseReviewMutation(input: unknown, alert: MonitoringAlert, draft: SignalReviewDraft) {
  const value = closed(input, ['schema', ...REVIEW_FIELDS, 'replayed']); requireValue(value.schema === 'monitoring-review-mutation-read/1'); boolean(value.replayed)
  const actual = review(value, alert)
  requireValue(actual.disposition === draft.disposition && actual.reasonCode === draft.reasonCode && actual.note === draft.note)
  return actual
}
