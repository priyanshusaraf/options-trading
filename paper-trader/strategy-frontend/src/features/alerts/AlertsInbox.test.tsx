import { readFileSync } from 'node:fs'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { AlertsInbox } from './AlertsInbox'
import type { SignalAlertViewModel } from './viewModels'

afterEach(cleanup)

const address = (value: string) => `sha256:${value.repeat(64).slice(0, 64)}`
function alert(overrides: Partial<SignalAlertViewModel> = {}): SignalAlertViewModel {
  return {
    alertAddress: address('a'), assignmentId: 'assignment.alpha', monitoringEventAddress: address('b'),
    action: 'BUY', displaySymbol: 'NIFTY 50', previousState: 'FLAT', targetState: 'LONG',
    eventLabel: '29 Aug · 09:16', validUntilLabel: '29 Aug · 09:21', evidenceState: 'FRESH',
    entryReferenceKind: 'BAR_CLOSE', entryReferenceValue: '₹22,481.35', entryReferenceCurrency: 'INR',
    stopLoss: { basis: 'RATE', authoredValue: '5', units: 'PERCENT', resolvedValue: '₹21,357.28' },
    takeProfit: { basis: 'RATE', authoredValue: '15', units: 'PERCENT', resolvedValue: '₹25,853.55' },
    attention: { lastSequence: 0, isUnread: true, readAt: null, acknowledgedAt: null, dismissedAt: null },
    ...overrides,
  }
}

it('renders a dense verified queue with exact signal and safety language', () => {
  render(<AlertsInbox items={[
    alert(),
    alert({ alertAddress: address('c'), action: 'SELL', previousState: 'LONG', targetState: 'SHORT', displaySymbol: 'RELIANCE', evidenceState: 'STALE' }),
    alert({ alertAddress: address('d'), action: 'EXIT', previousState: 'SHORT', targetState: 'FLAT', displaySymbol: 'BANKNIFTY', attention: { lastSequence: 1, isUnread: false, readAt: 'now', acknowledgedAt: null, dismissedAt: null } }),
  ]} selectedAlertAddress={address('a')} filter="ALL" state={{ kind: 'READY' }} onSelect={() => undefined} onFilterChange={() => undefined} />)
  expect(screen.getByRole('heading', { name: 'Alerts Inbox' })).toBeInTheDocument()
  expect(screen.getByText('BUY NIFTY 50 · target state LONG')).toBeInTheDocument()
  expect(screen.getByText('SELL RELIANCE · target state SHORT')).toBeInTheDocument()
  expect(screen.getByText('EXIT BANKNIFTY · target state FLAT')).toBeInTheDocument()
  expect(screen.getAllByText(/Entry ₹22,481.35 · SL ₹21,357.28 · TP ₹25,853.55/)).toHaveLength(3)
  expect(screen.getByText(/Entry reference is not a fill/)).toBeInTheDocument()
  expect(document.querySelectorAll('.alerts-unread')).toHaveLength(2)
  expect(screen.getByRole('button', { name: /BUY NIFTY 50/ })).toHaveAttribute('aria-pressed', 'true')
})

it('uses native selected/filter actions and stable server alert identities', () => {
  const onSelect = vi.fn(); const onFilterChange = vi.fn()
  render(<AlertsInbox items={[alert()]} selectedAlertAddress={null} filter="UNREAD" state={{ kind: 'READY' }} onSelect={onSelect} onFilterChange={onFilterChange} />)
  fireEvent.click(screen.getByRole('button', { name: /BUY NIFTY 50/ }))
  expect(onSelect).toHaveBeenCalledWith(address('a'))
  fireEvent.click(screen.getByRole('button', { name: 'Active evidence' }))
  expect(onFilterChange).toHaveBeenCalledWith('ACTIVE')
  expect(screen.getByRole('button', { name: 'Unread' })).toHaveAttribute('aria-pressed', 'true')
})

it('gives loading, empty, offline and retry states explicit direction', () => {
  const props = { items: [], selectedAlertAddress: null, filter: 'ALL' as const, onSelect: () => undefined, onFilterChange: () => undefined }
  const { rerender } = render(<AlertsInbox {...props} state={{ kind: 'LOADING' }} />)
  expect(screen.getByRole('status')).toHaveTextContent('Loading verified alerts')
  rerender(<AlertsInbox {...props} state={{ kind: 'READY' }} />)
  expect(screen.getByRole('heading', { name: 'No alerts in this view' })).toBeInTheDocument()
  const onRetry = vi.fn()
  rerender(<AlertsInbox {...props} state={{ kind: 'OFFLINE', message: 'Verified alert facts are unavailable.' }} onRetry={onRetry} />)
  expect(screen.getByRole('alert')).toHaveTextContent('Alerts are offline')
  fireEvent.click(screen.getByRole('button', { name: 'Retry' })); expect(onRetry).toHaveBeenCalledOnce()
})

it('keeps feature sources transport, storage, prototype and execution free', () => {
  const sources = ['AlertsInbox.tsx', 'AlertDetail.tsx', 'viewModels.ts'].map((name) => readFileSync(new URL(name, import.meta.url), 'utf8')).join('\n')
  for (const forbidden of ['fetch(', 'XMLHttpRequest', 'EventSource', 'WebSocket', 'localStorage', 'sessionStorage', 'StrategyApi', 'PrototypeApp', '/api/orders', '/api/positions', 'session replay']) expect(sources).not.toContain(forbidden)
  expect(sources).toContain('key={alert.alertAddress}')
})

// Connected desk checks use parsed server facts and a controlled transport.
import { act, waitFor } from '@testing-library/react'
import { AlertsWorkspace } from './AlertsWorkspace'
import { parseMonitoringAlert } from './monitoringContracts'
import { ALERT_NOW, monitoringAlertData } from './testData'
import { ApiError, type StrategyApi } from '../../shell/api'

function desk(role = 'member') {
  let invalidate = () => {}
  const record = parseMonitoringAlert(monitoringAlertData({ last_sequence: 7, is_unread: false, read_at: '2026-09-06T05:59:30Z' }))
  const api = {
    session: vi.fn().mockResolvedValue({ user: { id: 'person' }, organization_id: 'workspace', memberships: [{ organization_id: 'workspace', role }] }),
    onAccessInvalidated: vi.fn((callback: () => void) => { invalidate = callback; return () => {} }),
    monitoringAlerts: vi.fn().mockResolvedValue({ items: [record], nextCursor: null }),
    monitoringAlert: vi.fn().mockResolvedValue(record), monitoringOwnReview: vi.fn().mockResolvedValue(null),
    monitoringAttention: vi.fn().mockResolvedValue({ ...record.facts.attention, lastSequence: 8, acknowledgedAt: '2026-09-06T06:00:00Z' }),
    monitoringReview: vi.fn(),
  }
  return { api, record, invalidate: () => invalidate(), component: <AlertsWorkspace api={api as unknown as StrategyApi} enabled /> }
}
async function selectDesk(context: ReturnType<typeof desk>) {
  render(context.component)
  fireEvent.click(await screen.findByRole('button', { name: /BUY RELIANCE/ }))
  await screen.findByRole('heading', { name: 'Handle this alert' })
}
afterEach(() => vi.restoreAllMocks())
it('loads server detail and personal review before sending its actual attention sequence', async () => {
  vi.spyOn(Date, 'now').mockReturnValue(ALERT_NOW)
  const context = desk(); await selectDesk(context)
  expect(context.api.monitoringAlert).toHaveBeenCalledWith(context.record, expect.any(AbortSignal))
  expect(context.api.monitoringOwnReview).toHaveBeenCalledWith(context.record, expect.any(AbortSignal))
  fireEvent.click(screen.getByRole('button', { name: 'Acknowledge' }))
  await waitFor(() => expect(context.api.monitoringAttention).toHaveBeenCalledWith(context.record, 'ACKNOWLEDGE', 7, expect.any(AbortSignal)))
  await waitFor(() => expect(screen.getByRole('button', { name: 'Acknowledge' })).toBeDisabled())
  expect(screen.getByText('Read · Acknowledged')).toBeInTheDocument()
})
it('retains review input on forbidden responses and requires readback after uncertain mutations', async () => {
  const context = desk(); context.api.monitoringReview.mockRejectedValueOnce(new ApiError('input', 'Forbidden', { schema: 'api-error/1', code: 'MONITORING_FORBIDDEN', message: 'Your role cannot submit this review.', request_id: null, details: null } as never))
  await selectDesk(context)
  fireEvent.change(screen.getByLabelText('Optional note'), { target: { value: 'Keep my observation' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save review' }))
  await screen.findByText('Your role cannot submit this review.')
  expect(screen.getByLabelText('Optional note')).toHaveValue('Keep my observation')
  expect(screen.getByRole('button', { name: 'Save review' })).toBeEnabled()
  context.api.monitoringReview.mockRejectedValueOnce(new Error('Connection interrupted'))
  fireEvent.click(screen.getByRole('button', { name: 'Save review' }))
  await screen.findByText(/Refresh the alert to check its saved state/)
  expect(screen.getByLabelText('Optional note')).toHaveValue('Keep my observation')
  expect(screen.getByRole('button', { name: /Saving review/ })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: 'Refresh alert' }))
  await waitFor(() => expect(screen.getByRole('button', { name: 'Save review' })).toBeEnabled())
  expect(screen.getByLabelText('Optional note')).toHaveValue('Keep my observation')
})
it('shows viewer facts read only and removes private desk state when access expires', async () => {
  const context = desk('viewer'); await selectDesk(context)
  expect(screen.getByRole('button', { name: 'Acknowledge' })).toBeDisabled()
  expect(screen.queryByLabelText('Optional note')).not.toBeInTheDocument()
  act(context.invalidate)
  expect(screen.getByRole('alert')).toHaveTextContent('Verify your session again')
  expect(screen.queryByText(/BUY RELIANCE/)).not.toBeInTheDocument()
})
it('pages explicitly and refilters active evidence against the current clock', async () => {
  const clock = vi.spyOn(Date, 'now').mockReturnValue(ALERT_NOW), context = desk()
  context.api.monitoringAlerts.mockResolvedValue({ items: [context.record], nextCursor: 'signed.cursor' })
  render(context.component)
  await screen.findByRole('button', { name: /BUY RELIANCE/ })
  fireEvent.click(screen.getByRole('button', { name: 'Older alerts' }))
  await waitFor(() => expect(context.api.monitoringAlerts).toHaveBeenLastCalledWith('signed.cursor', false, expect.any(AbortSignal)))
  expect(screen.getByRole('button', { name: 'Previous page' })).toBeEnabled()
  fireEvent.click(screen.getByRole('button', { name: 'Active evidence' }))
  await waitFor(() => expect(context.api.monitoringAlerts).toHaveBeenLastCalledWith(null, false, expect.any(AbortSignal)))
  await screen.findByRole('button', { name: /BUY RELIANCE/ })
  clock.mockReturnValue(ALERT_NOW + 3600000); fireEvent.focus(window)
  expect(screen.queryByRole('button', { name: /BUY RELIANCE/ })).not.toBeInTheDocument()
  expect(screen.getByText(/matching of 1 alerts on this page/)).toHaveTextContent('0 matching')
  fireEvent.click(screen.getByRole('button', { name: 'Unread' }))
  await waitFor(() => expect(context.api.monitoringAlerts).toHaveBeenLastCalledWith(null, true, expect.any(AbortSignal)))
})
it('does not open session or transport when the alert capability is disabled', () => {
  const context = desk(); render(<AlertsWorkspace api={context.api as unknown as StrategyApi} enabled={false} />)
  expect(screen.getByRole('status')).toHaveTextContent('not available')
  expect(context.api.session).not.toHaveBeenCalled()
})
