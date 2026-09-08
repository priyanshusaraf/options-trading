// Synthetic contract fixtures, imported only by tests.
export const ALERT_NOW = Date.parse('2026-09-06T06:00:00Z')
export const alertAddress = (digit: string) => `sha256:${digit.repeat(64)}`
export function monitoringAlertData(overrides: Record<string, unknown> = {}) {
  return { schema: 'monitoring-alert-read/2', alert_address: alertAddress('a'), assignment_id: 'assignment.alpha', monitoring_event_address: alertAddress('b'), strategy_id: 'strategy.alpha', graph_version_address: alertAddress('c'),
    action: 'BUY', display_symbol: 'RELIANCE', previous_state: 'FLAT', target_state: 'LONG', event_at: '2026-09-06T05:59:00Z', valid_until: '2026-09-06T07:00:00Z', freshness: 'FRESH',
    entry_reference_kind: 'COMPLETED_EVENT_CLOSE', entry_reference_value: '100', entry_reference_currency: 'INR', stop_loss_basis: 'PERCENT_FROM_ENTRY_REFERENCE', stop_loss_authored_value: '0.01', stop_loss_units: 'RATE', stop_loss_resolved_value: '99', take_profit_basis: 'PERCENT_FROM_ENTRY_REFERENCE', take_profit_authored_value: '0.02', take_profit_units: 'RATE', take_profit_resolved_value: '102',
    last_sequence: 0, is_unread: true, read_at: null, acknowledged_at: null, dismissed_at: null, ...overrides }
}
export function researchMonitoringAlertData(overrides: Record<string, unknown> = {}) {
  const common = Object.fromEntries(Object.entries(monitoringAlertData()).filter(([key]) => !key.startsWith('stop_loss_') && !key.startsWith('take_profit_')))
  return { ...common, schema: 'monitoring-research-alert-read/1', consumer_address: alertAddress('d'),
    previous_state: 'LONG', simulated_position_state: 'FLAT', decision_kind: 'ENTER',
    stop_loss: { status: 'UNRESOLVED', rules: [
      { basis: 'FRACTION_FROM_SIMULATED_ENTRY', fraction: 0.01, resolved_value: null, definition_address: alertAddress('e') },
      { basis: 'ATR_RATCHET_STOP', fraction: null, resolved_value: null, definition_address: alertAddress('f') }] },
    take_profit: { status: 'DISABLED', rules: [] }, ...overrides }
}
export function monitoringAttentionData(overrides: Record<string, unknown> = {}) {
  return { schema: 'monitoring-attention-mutation-read/1', attention_event_address: alertAddress('d'), request_id: alertAddress('e'), assignment_id: 'assignment.alpha', alert_address: alertAddress('a'), sequence: 1, action: 'ACKNOWLEDGE', occurred_at: '2026-09-06T06:00:00Z', replayed: false,
    last_sequence: 1, is_unread: false, read_at: null, acknowledged_at: '2026-09-06T06:00:00Z', dismissed_at: null, ...overrides }
}
export function monitoringReviewData(overrides: Record<string, unknown> = {}) {
  return { review_address: alertAddress('f'), assignment_id: 'assignment.alpha', monitoring_event_address: alertAddress('b'), disposition: 'CONFIRMED', reason_code: 'MATCHED_EXPECTATION', note: 'Matches the written rules', created_at: '2026-09-06T06:00:00Z', ...overrides }
}
