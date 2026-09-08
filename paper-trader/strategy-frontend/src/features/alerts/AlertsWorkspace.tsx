import { useEffect, useRef, useState } from 'react'
import { ApiError, errorMessage, type StrategyApi } from '../../shell/api'
import type { BrowserIdentity } from '../../shell/contracts'
import { AlertDetail } from './AlertDetail'
import { AlertsInbox } from './AlertsInbox'
import { alertView, canReviewAlerts, matchesAlertFilter, type MonitoringAlert, type MonitoringPage } from './monitoringContracts'
import type { AlertFilter, AttentionAction, SignalReviewDraft, SignalReviewViewModel } from './viewModels'

type Load<T> = { kind: 'loading' } | { kind: 'error'; message: string } | { kind: 'ready'; value: T }
const reasons = [{ code: 'MATCHED_EXPECTATION', label: 'Matched the written rules' }, { code: 'UNEXPECTED_TRANSITION', label: 'Unexpected state change' }, { code: 'INSUFFICIENT_EVIDENCE', label: 'Insufficient evidence' }]
function monitoringMessage(error: unknown) { return error instanceof ApiError && error.envelope?.code.startsWith('MONITORING_') ? error.envelope.message : errorMessage(error) }
function requiresReadback(error: unknown) { return !(error instanceof ApiError && error.kind === 'input' && ['MONITORING_FORBIDDEN', 'MONITORING_INVALID', 'MONITORING_SESSION_REQUIRED'].includes(error.envelope?.code ?? '')) }
function useClock() {
  const [now, setNow] = useState(Date.now)
  useEffect(() => { const update = () => setNow(Date.now()); const timer = window.setInterval(update, 1000); window.addEventListener('focus', update); document.addEventListener('visibilitychange', update); return () => { window.clearInterval(timer); window.removeEventListener('focus', update); document.removeEventListener('visibilitychange', update) } }, [])
  return now
}
function useAlertPage(api: StrategyApi, filter: AlertFilter, cursor: string | null, attempt: number) {
  const key = `${filter}/${cursor ?? ''}/${attempt}`
  const [stored, setStored] = useState<{ api: StrategyApi; key: string; state: Load<MonitoringPage> }>({ api, key: '', state: { kind: 'loading' } })
  useEffect(() => {
    const controller = new AbortController(); setStored({ api, key, state: { kind: 'loading' } })
    api.monitoringAlerts(cursor, filter === 'UNREAD', controller.signal).then((value) => { if (!controller.signal.aborted) setStored({ api, key, state: { kind: 'ready', value } }) })
      .catch((error: unknown) => { if (!controller.signal.aborted) setStored({ api, key, state: { kind: 'error', message: monitoringMessage(error) } }) })
    return () => controller.abort()
  }, [api, cursor, filter, key])
  const state: Load<MonitoringPage> = stored.api === api && stored.key === key ? stored.state : { kind: 'loading' }
  function update(alert: MonitoringAlert) { setStored((current) => current.api === api && current.key === key && current.state.kind === 'ready' ? { ...current, state: { kind: 'ready', value: { ...current.state.value, items: current.state.value.items.map((item) => item.facts.alertAddress === alert.facts.alertAddress ? alert : item) } } } : current) }
  return { state, update }
}

type DetailState = { record: MonitoringAlert | null; review: SignalReviewViewModel | null; loading: boolean; error: string | null; blocked: boolean }
function mutationAvailable(canWrite: boolean, state: DetailState, request: AbortController | null) { return canWrite && !state.loading && request === null }
function AlertSelection({ api, initial, canWrite, now, onBusy, onUpdated }: { api: StrategyApi; initial: MonitoringAlert; canWrite: boolean; now: number; onBusy: (busy: boolean) => void; onUpdated: (alert: MonitoringAlert) => void }) {
  const [state, setState] = useState<DetailState>({ record: null, review: null, loading: true, error: null, blocked: false })
  const [attempt, setAttempt] = useState(0), [pending, setPending] = useState<AttentionAction | 'REVIEW' | null>(null)
  const request = useRef<AbortController | null>(null), current = useRef(initial); current.current = state.record ?? initial
  useEffect(() => {
    const controller = new AbortController(); setState((value) => ({ ...value, loading: true, error: null }))
    async function load() {
      const record = await api.monitoringAlert(current.current, controller.signal)
      const review = await api.monitoringOwnReview(record, controller.signal)
      if (!controller.signal.aborted) setState({ record, review, loading: false, error: null, blocked: false })
    }
    void load().catch((error) => { if (!controller.signal.aborted) setState((value) => ({ ...value, loading: false, error: monitoringMessage(error), blocked: true })) })
    return () => controller.abort()
  }, [api, initial.facts.alertAddress, attempt])
  useEffect(() => () => request.current?.abort(), [api])
  async function mutate(action: AttentionAction | 'REVIEW', value: number | SignalReviewDraft) {
    const record = state.record
    if (!record || !mutationAvailable(canWrite, state, request.current)) return
    const controller = new AbortController(); request.current = controller; setPending(action); onBusy(true)
    try {
      if (action === 'REVIEW') {
        const review = await api.monitoringReview(record, value as SignalReviewDraft, controller.signal)
        if (!controller.signal.aborted) setState((current) => ({ ...current, review, error: null }))
      } else {
        const attention = await api.monitoringAttention(record, action, value as number, controller.signal)
        if (!controller.signal.aborted) { const updated = { ...record, facts: { ...record.facts, attention } }; setState((current) => ({ ...current, record: updated, error: null })); onUpdated(updated) }
      }
    } catch (error) { if (!controller.signal.aborted) setState((current) => ({ ...current, error: monitoringMessage(error), blocked: requiresReadback(error) })) }
    finally { if (request.current === controller) { request.current = null; setPending(null); onBusy(false) } }
  }
  return <section className="alerts-selection"><div className="alerts-detail-tools"><button disabled={pending !== null || state.loading} onClick={() => setAttempt((value) => value + 1)}>Refresh alert</button>{state.loading && <p role="status">Loading this alert and your review…</p>}</div>
    {state.record === null && state.error && <p role="alert">{state.error}</p>}
    {state.blocked && <p>Refresh the alert to check its saved state before another action. Your note is retained.</p>}
    <AlertDetail alert={state.record ? alertView(state.record, now) : null} existingReview={state.review} reviewReasons={reasons} readOnly={!canWrite} disabled={state.loading || state.blocked} pendingAction={pending} errorMessage={state.error} onAttention={(action, sequence) => void mutate(action, sequence)} onReview={(draft) => void mutate('REVIEW', draft)} />
  </section>
}

function AlertsDesk({ api, identity }: { api: StrategyApi; identity: BrowserIdentity }) {
  const [filter, setFilter] = useState<AlertFilter>('ALL'), [cursors, setCursors] = useState<(string | null)[]>([null]), [attempt, setAttempt] = useState(0)
  const [selected, setSelected] = useState<MonitoringAlert | null>(null), [busy, setBusy] = useState(false); const busyRef = useRef(false)
  const now = useClock(), { state, update } = useAlertPage(api, filter, cursors.at(-1) ?? null, attempt)
  const items = state.kind === 'ready' ? state.value.items : [], visible = items.filter((item) => matchesAlertFilter(item, filter, now))
  function changeFilter(next: AlertFilter) { if (busyRef.current) return; setFilter(next); setCursors([null]); setSelected(null) }
  function page(next: (string | null)[]) { if (busyRef.current) return; setCursors(next); setSelected(null) }
  return <div className="alerts-workspace"><div className="alerts-workspace-tools"><button disabled={busy} onClick={() => { setCursors([null]); setAttempt((value) => value + 1) }}>Refresh inbox</button><span>Stored monitoring alerts and personal reviews</span></div><div className="alerts-workspace-grid"><div>
    <AlertsInbox items={visible.map((item) => alertView(item, now))} selectedAlertAddress={selected?.facts.alertAddress ?? null} filter={filter} navigationDisabled={busy} state={state.kind === 'loading' ? { kind: 'LOADING' } : state.kind === 'error' ? { kind: 'ERROR', message: state.message } : { kind: 'READY' }}
      pageLabel={`Page ${cursors.length} · ${visible.length} matching of ${items.length} alerts on this page`} hasOlder={state.kind === 'ready' && state.value.nextCursor !== null} onRetry={() => setAttempt((value) => value + 1)} onFilterChange={changeFilter}
      onSelect={(address) => { if (!busyRef.current) setSelected(items.find((item) => item.facts.alertAddress === address) ?? null) }} />
    <nav className="alerts-pagination" aria-label="Alert pages"><button disabled={busy || cursors.length === 1} onClick={() => page(cursors.slice(0, -1))}>Previous page</button><button disabled={busy || state.kind !== 'ready' || state.value.nextCursor === null} onClick={() => { if (state.kind === 'ready') page([...cursors, state.value.nextCursor]) }}>Older alerts</button></nav>
  </div>{selected ? <AlertSelection key={selected.facts.alertAddress} api={api} initial={selected} canWrite={canReviewAlerts(identity)} now={now} onUpdated={update} onBusy={(next) => { busyRef.current = next; setBusy(next) }} /> : <AlertDetail alert={null} reviewReasons={reasons} onAttention={() => {}} onReview={() => {}} />}</div></div>
}
function SessionAlerts({ api }: { api: StrategyApi }) {
  const [attempt, setAttempt] = useState(0), [stored, setStored] = useState<{ api: StrategyApi; state: Load<BrowserIdentity> }>({ api, state: { kind: 'loading' } })
  useEffect(() => { const controller = new AbortController(); setStored({ api, state: { kind: 'loading' } }); api.session(controller.signal).then((value) => { if (!controller.signal.aborted) setStored({ api, state: { kind: 'ready', value } }) }).catch((error) => { if (!controller.signal.aborted) setStored({ api, state: { kind: 'error', message: errorMessage(error) } }) }); return () => controller.abort() }, [api, attempt])
  useEffect(() => api.onAccessInvalidated(() => setStored({ api, state: { kind: 'error', message: 'Verify your session again before viewing alerts.' } })), [api])
  const state: Load<BrowserIdentity> = stored.api === api ? stored.state : { kind: 'loading' }
  if (state.kind === 'ready') return <AlertsDesk key={`${state.value.organization_id}/${state.value.user.id}`} api={api} identity={state.value} />
  return <section><h1>Alerts</h1>{state.kind === 'loading' ? <p role="status">Checking your alert access…</p> : <><p role="alert">{state.message}</p><button onClick={() => setAttempt((value) => value + 1)}>Retry alert access</button></>}</section>
}
export function AlertsWorkspace({ api, enabled }: { api: StrategyApi; enabled: boolean }) { return enabled ? <SessionAlerts api={api} /> : <section><h1>Alerts</h1><p role="status">Stored alerts are not available in this server release.</p></section> }
