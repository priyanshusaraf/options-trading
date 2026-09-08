import { chooseSelect } from '../../test/select'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { AlertDetail } from './AlertDetail'
import type { SignalAlertViewModel } from './viewModels'
import { alertView, parseMonitoringAlert } from './monitoringContracts'
import { ALERT_NOW, researchMonitoringAlertData } from './testData'

afterEach(cleanup)

it('shows a new pending entry after catch-up without inventing levels or hiding multiple stop rules', () => {
  const record = parseMonitoringAlert(researchMonitoringAlertData())
  render(<AlertDetail alert={alertView(record, ALERT_NOW)} reviewReasons={[]} onAttention={() => undefined} onReview={() => undefined} />)
  expect(screen.getByText('Pending enter · Simulated position flat')).toBeInTheDocument()
  expect(screen.getByText(/LONG → LONG/)).toBeInTheDocument()
  expect(screen.getByText('1% from simulated entry')).toBeInTheDocument()
  expect(screen.getByText('ATR trailing stop')).toBeInTheDocument()
  expect(screen.getAllByText('Not configured')).toHaveLength(2)
  expect(screen.getAllByText('Price available after simulated entry')).toHaveLength(2)
  expect(screen.queryByRole('list', { name: /monitoring price geometry/ })).not.toBeInTheDocument()
  expect(screen.getByText('Completed candle close · not a simulated fill')).toBeInTheDocument()
})

it.each([
  { decision_kind: 'NONE' }, { simulated_position_state: 'LONG' }, { consumer_address: 'invalid' },
  { stop_loss: { status: 'RESOLVED', rules: [] } },
  { stop_loss: { status: 'UNRESOLVED', rules: [{ basis: 'FRACTION_FROM_SIMULATED_ENTRY', fraction: 0.01, resolved_value: 99, definition_address: `sha256:${'e'.repeat(64)}` }] } },
  { take_profit: { status: 'UNRESOLVED', rules: [{ basis: 'ATR_RATCHET_STOP', fraction: null, resolved_value: null, definition_address: `sha256:${'e'.repeat(64)}` }] } },
])('refuses inconsistent research alert data %j', (changes) => {
  expect(() => parseMonitoringAlert(researchMonitoringAlertData(changes))).toThrow()
})

const address = (value: string) => `sha256:${value.repeat(64).slice(0, 64)}`
const reasons = [{ code: 'MATCHED_EXPECTATION', label: 'Matched expectation' }, { code: 'UNEXPECTED_TRANSITION', label: 'Unexpected transition' }] as const
function alert(overrides: Partial<SignalAlertViewModel> = {}): SignalAlertViewModel {
  return {
    alertAddress: address('a'), assignmentId: 'assignment.alpha', monitoringEventAddress: address('b'),
    action: 'BUY', displaySymbol: 'NIFTY 50', previousState: 'FLAT', targetState: 'LONG',
    eventLabel: '29 Aug · 09:16', validUntilLabel: '29 Aug · 09:21', evidenceState: 'FRESH',
    entryReferenceKind: 'BAR_CLOSE', entryReferenceValue: '₹22,481.35', entryReferenceCurrency: 'INR',
    stopLoss: { basis: 'RATE', authoredValue: '5', units: 'PERCENT', resolvedValue: '₹21,357.28' },
    takeProfit: { basis: 'RATE', authoredValue: '15', units: 'PERCENT', resolvedValue: '₹25,853.55' },
    attention: { lastSequence: 3, isUnread: true, readAt: null, acknowledgedAt: null, dismissedAt: null },
    ...overrides,
  }
}

it('shows BUY geometry, authored and resolved protection, time and safety truth', () => {
  render(<AlertDetail alert={alert()} reviewReasons={reasons} onAttention={() => undefined} onReview={() => undefined} />)
  const heading = screen.getByRole('heading', { name: 'BUY NIFTY 50 · target state LONG' })
  expect(heading).toHaveFocus()
  const rail = screen.getByRole('list', { name: 'BUY monitoring price geometry' })
  expect(within(rail).getAllByRole('listitem').map((item) => item.textContent)).toEqual([
    'Take profit₹25,853.55', 'Entry reference₹22,481.35', 'Stop loss₹21,357.28',
  ])
  expect(screen.getByText(/RATE · 5 PERCENT/)).toBeInTheDocument()
  expect(screen.getByText(/RATE · 15 PERCENT/)).toBeInTheDocument()
  expect(screen.getByText(/Candle closed 29 Aug · 09:16/)).toBeInTheDocument()
  expect(screen.getByText(/not placed orders or exchange protection/)).toBeInTheDocument()
})

it('makes SELL short geometry explicit without relying on color', () => {
  render(<AlertDetail alert={alert({ action: 'SELL', previousState: 'LONG', targetState: 'SHORT', stopLoss: { basis: 'RATE', authoredValue: '5', units: 'PERCENT', resolvedValue: '₹23,605.42' }, takeProfit: { basis: 'RATE', authoredValue: '15', units: 'PERCENT', resolvedValue: '₹19,109.15' } })} reviewReasons={reasons} onAttention={() => undefined} onReview={() => undefined} />)
  const rail = screen.getByRole('list', { name: 'SELL monitoring price geometry' })
  expect(rail).toHaveAttribute('data-geometry', 'SHORT')
  expect(within(rail).getAllByRole('listitem').map((item) => item.textContent)).toEqual([
    'Stop loss₹23,605.42', 'Entry reference₹22,481.35', 'Take profit₹19,109.15',
  ])
})

it('labels stale, expired and unavailable evidence without inferring levels', () => {
  const { rerender } = render(<AlertDetail alert={alert({ evidenceState: 'STALE', entryReferenceValue: null, stopLoss: { basis: 'RATE', authoredValue: '5', units: 'PERCENT', resolvedValue: null }, takeProfit: { basis: 'RATE', authoredValue: '15', units: 'PERCENT', resolvedValue: null } })} reviewReasons={reasons} onAttention={() => undefined} onReview={() => undefined} />)
  expect(screen.getByText(/Stale monitoring evidence/)).toBeInTheDocument()
  expect(screen.getAllByText('Level unavailable — no value inferred').length).toBeGreaterThan(2)
  rerender(<AlertDetail alert={alert({ evidenceState: 'EXPIRED' })} reviewReasons={reasons} onAttention={() => undefined} onReview={() => undefined} />)
  expect(screen.getByText(/Alert expired/)).toBeInTheDocument()
  rerender(<AlertDetail alert={alert({ evidenceState: 'UNKNOWN' })} reviewReasons={reasons} onAttention={() => undefined} onReview={() => undefined} />)
  expect(screen.getByText(/Monitoring evidence unavailable/)).toBeInTheDocument()
})

it('sends exact optimistic sequence callbacks and waits for confirmed props', () => {
  const onAttention = vi.fn()
  const { rerender } = render(<AlertDetail alert={alert()} reviewReasons={reasons} onAttention={onAttention} onReview={() => undefined} />)
  fireEvent.click(screen.getByRole('button', { name: 'Mark read' }))
  fireEvent.click(screen.getByRole('button', { name: 'Acknowledge' }))
  fireEvent.click(screen.getByRole('button', { name: 'Dismiss' }))
  expect(onAttention.mock.calls).toEqual([['READ', 3], ['ACKNOWLEDGE', 3], ['DISMISS', 3]])
  expect(screen.getByRole('status')).toHaveTextContent('Unread')
  rerender(<AlertDetail alert={alert()} reviewReasons={reasons} pendingAction="READ" onAttention={onAttention} onReview={() => undefined} />)
  expect(screen.getByRole('button', { name: 'Marking read…' })).toBeDisabled()
  expect(screen.getByRole('status')).toHaveTextContent('Unread')
})

it('submits a bounded review draft and renders immutable confirmed review', async () => {
  const onReview = vi.fn()
  const { rerender } = render(<AlertDetail alert={alert()} reviewReasons={reasons} onAttention={() => undefined} onReview={onReview} />)
  await chooseSelect('Decision', 'REJECTED')
  await chooseSelect('Reason', 'UNEXPECTED_TRANSITION')
  fireEvent.change(screen.getByLabelText('Optional note'), { target: { value: 'Price context differed' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save review' }))
  expect(onReview).toHaveBeenCalledWith({ disposition: 'REJECTED', reasonCode: 'UNEXPECTED_TRANSITION', note: 'Price context differed' })
  rerender(<AlertDetail alert={alert()} reviewReasons={reasons} existingReview={{ reviewAddress: address('r'), disposition: 'REJECTED', reasonCode: 'UNEXPECTED_TRANSITION', note: 'Price context differed', createdLabel: '29 Aug · 09:18' }} onAttention={() => undefined} onReview={onReview} />)
  expect(screen.getByText('Rejected')).toBeInTheDocument();
  expect(screen.getByText(/Unexpected transition · 29 Aug/)).toBeInTheDocument();
  expect(screen.queryByText('UNEXPECTED_TRANSITION')).not.toBeInTheDocument(); expect(screen.queryByRole('button', { name: 'Save review' })).not.toBeInTheDocument()
})

it('counts private notes in UTF-8 bytes and blocks an oversized local draft', () => {
  render(<AlertDetail alert={alert()} reviewReasons={reasons} onAttention={() => undefined} onReview={() => undefined} />)
  fireEvent.change(screen.getByLabelText('Optional note'), { target: { value: '₹'.repeat(1366) } })
  expect(screen.getByRole('alert')).toHaveTextContent('4098 / 4096 bytes')
  expect(screen.getByLabelText('Optional note')).toHaveAttribute('aria-invalid', 'true')
  expect(screen.getByRole('button', { name: 'Save review' })).toBeDisabled()
})

it('provides an explicit empty detail state', () => {
  render(<AlertDetail alert={null} reviewReasons={reasons} onAttention={() => undefined} onReview={() => undefined} />)
  expect(screen.getByRole('heading', { name: 'Select an alert' })).toBeInTheDocument()
})

it.each([' leading', 'trailing ', 'two\nlines', 'a\tb', '\u0085note', 'broken\ud800'])('explains an invalid note without silently rewriting it: %j', (note) => {
  const onReview = vi.fn()
  render(<AlertDetail alert={alert()} reviewReasons={reasons} onAttention={vi.fn()} onReview={onReview} />)
  fireEvent.change(screen.getByLabelText('Optional note'), { target: { value: note } })
  expect(screen.getByLabelText('Optional note')).toHaveValue(note)
  expect(screen.getByLabelText('Optional note')).toHaveAttribute('aria-invalid', 'true')
  expect(screen.getByRole('button', { name: 'Save review' })).toBeDisabled()
  expect(onReview).not.toHaveBeenCalled()
})

it('keeps viewer attention read-only and labels the review as personal', () => {
  render(<AlertDetail alert={alert()} reviewReasons={reasons} readOnly onAttention={vi.fn()} onReview={vi.fn()} />)
  expect(screen.getByRole('button', { name: 'Acknowledge' })).toBeDisabled()
  expect(screen.getByRole('heading', { name: 'Your review' })).toBeInTheDocument()
  expect(screen.queryByLabelText('Optional note')).not.toBeInTheDocument()
  expect(screen.getByText(/Your role can view alerts/)).toBeInTheDocument()
})

it('keeps EXIT from SHORT geometry ordered with the high stop above entry', () => {
  render(<AlertDetail alert={alert({ action: 'EXIT', previousState: 'SHORT', targetState: 'FLAT', stopLoss: { basis: 'RATE', authoredValue: '5', units: 'PERCENT', resolvedValue: '₹23,605.42' }, takeProfit: { basis: 'RATE', authoredValue: '15', units: 'PERCENT', resolvedValue: '₹19,109.15' } })} reviewReasons={reasons} onAttention={() => undefined} onReview={() => undefined} />)
  const rail = screen.getByRole('list', { name: 'EXIT monitoring price geometry' })
  expect(rail).toHaveAttribute('data-geometry', 'EXIT_EVIDENCE')
  expect(within(rail).getAllByRole('listitem').map((item) => item.textContent)).toEqual(['Stop loss₹23,605.42', 'Entry reference₹22,481.35', 'Take profit₹19,109.15'])
})


it('keeps internal alert identities out of the view and explains unavailable reasons', () => {
  const onReview = vi.fn()
  render(<AlertDetail alert={alert({ strategyReference: 'strategy.internal', graphVersionAddress: address('c') })}
    reviewReasons={[]} onAttention={vi.fn()} onReview={onReview} />)
  expect(document.body.textContent).not.toMatch(/sha256:|assignment\.alpha|strategy\.internal/)
  expect(screen.getByText('No review reasons are available. Refresh alerts to try again.')).toBeInTheDocument()
  expect(screen.getByRole('combobox', { name: 'Reason' })).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Save review' })).toBeDisabled()
})
