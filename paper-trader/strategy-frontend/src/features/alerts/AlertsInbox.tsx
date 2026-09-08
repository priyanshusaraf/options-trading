import { BellRing, ChevronRight, CircleAlert, RefreshCw } from 'lucide-react'
import type { AlertFilter, InboxState, SignalAlertViewModel } from './viewModels'
import { alertTitle, evidenceLabel, levelValue, protectionValue, SAFETY_COPY } from './viewModels'
import './alerts.css'

export type AlertsInboxProps = Readonly<{
  items: readonly SignalAlertViewModel[]
  selectedAlertAddress: string | null
  filter: AlertFilter
  state: InboxState
  onSelect: (alertAddress: string) => void
  onFilterChange: (filter: AlertFilter) => void
  onRetry?: () => void
  navigationDisabled?: boolean
  pageLabel?: string
  hasOlder?: boolean
}>

const filters: readonly Readonly<{ value: AlertFilter; label: string }>[] = [
  { value: 'ALL', label: 'All alerts' },
  { value: 'UNREAD', label: 'Unread' },
  { value: 'ACTIVE', label: 'Active evidence' },
]

export function AlertsInbox({
  items, selectedAlertAddress, filter, state, onSelect, onFilterChange, onRetry, navigationDisabled = false, pageLabel, hasOlder = false,
}: AlertsInboxProps) {
  return <section className="alerts-inbox" aria-labelledby="alerts-inbox-title">
    <header className="alerts-inbox__header">
      <div>
        <span className="alerts-eyebrow">Monitoring ledger</span>
        <h1 id="alerts-inbox-title">Alerts Inbox</h1>
        <p>Strategy state changes that need review. Nothing here places an order.</p>
      </div>
      <BellRing aria-hidden="true" size={20} />
    </header>

    <div className="alerts-filter" aria-label="Filter alerts">
      {filters.map((item) => <button key={item.value} type="button"
        disabled={navigationDisabled} aria-pressed={filter === item.value}
        onClick={() => onFilterChange(item.value)}>{item.label}</button>)}
    </div>

    {pageLabel && <p className="alerts-page-label">{pageLabel}</p>}
    {state.kind === 'LOADING' && <div className="alerts-state" role="status" aria-live="polite">
      <BellRing aria-hidden="true" size={18} /><span>Loading verified alerts…</span>
    </div>}
    {(state.kind === 'ERROR' || state.kind === 'OFFLINE') && <div className="alerts-state alerts-state--error" role="alert">
      <CircleAlert aria-hidden="true" size={18} />
      <div><strong>{state.kind === 'OFFLINE' ? 'Alerts are offline' : 'Alerts could not be loaded'}</strong><span>{state.message}</span></div>
      {onRetry && <button type="button" onClick={onRetry}><RefreshCw aria-hidden="true" size={15} />Retry</button>}
    </div>}
    {state.kind === 'READY' && items.length === 0 && <div className="alerts-state">
      <BellRing aria-hidden="true" size={18} />
      <div><h2>{pageLabel ? 'No matching alerts on this page' : 'No alerts in this view'}</h2><span>{hasOlder ? 'Older pages may contain matching alerts. Continue to the next page.' : 'Only stored alerts from this workspace appear here.'}</span></div>
    </div>}
    {state.kind === 'READY' && items.length > 0 && <ul className="alerts-list">
      {items.map((alert) => <li key={alert.alertAddress}>
        <button type="button" className={`alerts-row alerts-row--${alert.action.toLowerCase()}`}
          disabled={navigationDisabled} aria-pressed={selectedAlertAddress === alert.alertAddress}
          onClick={() => onSelect(alert.alertAddress)}>
          <span className="alerts-row__signal" aria-hidden="true">{alert.action}</span>
          <span className="alerts-row__body">
            <strong>{alertTitle(alert)}</strong>
            <span className="alerts-row__levels">
              Entry {levelValue(alert.entryReferenceValue)} · SL {protectionValue(alert.stopLoss)} · TP {protectionValue(alert.takeProfit)}
            </span>
            <span className={`alerts-evidence alerts-evidence--${alert.evidenceState.toLowerCase()}`}>
              {evidenceLabel(alert.evidenceState)} · {alert.eventLabel}
            </span>
          </span>
          {alert.attention.isUnread && <span className="alerts-unread">Unread</span>}
          <ChevronRight aria-hidden="true" size={16} />
        </button>
      </li>)}
    </ul>}
    <p className="alerts-safety">{SAFETY_COPY}</p>
  </section>
}
