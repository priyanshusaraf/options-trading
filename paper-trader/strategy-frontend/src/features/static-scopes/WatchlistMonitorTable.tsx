import { useEffect, useRef, useState } from 'react'
import { TraderSelect } from '../../components/TraderSelect'
import { ApiError, errorMessage, type StrategyApi } from '../../shell/api'
import { ContractError, type GraphSummary } from '../../shell/contracts'
import { formatIndiaTimestamp } from './ProviderHistoryForm'
import { scopeMemberIdentity, type ScopeMember, type WatchlistMemberCandidate } from './staticScopeContracts'
import type { WatchlistMonitorClient, WatchlistMonitorContext, WatchlistMonitorRow, WatchlistMonitorSnapshot, WatchlistStrategySelection } from './watchlistMonitorTypes'
export type { WatchlistMonitorClient, WatchlistMonitorContext, WatchlistMonitorRow } from './watchlistMonitorTypes'

type Filter = 'ALL' | 'PINNED' | 'SIGNALS' | 'ATTENTION'
type Props = { api: StrategyApi; client?: WatchlistMonitorClient | null; context: WatchlistMonitorContext;
  members: readonly WatchlistMemberCandidate[]; graphs: readonly GraphSummary[]; locked: boolean; readOnly?: boolean;
  onDetails: (member: ScopeMember) => void; onRemove: (member: ScopeMember) => void; canRemove: boolean }
function contextKey(value: WatchlistMonitorContext) {
  return [value.projectId, value.scopeId, value.scopeRevision, value.scopeAddress, value.membershipAddress].join('|')
}
function verifyRow(row: WatchlistMonitorRow, memberKey: string) {
  if (row.memberKey !== memberKey || !Number.isSafeInteger(row.configurationRevision) || row.configurationRevision < 0) throw new ContractError()
  verifyResultIdentity(row)
}
function verifyResultIdentity(row: WatchlistMonitorRow) {
  const result = row.result
  if (result.assignmentId !== null && result.assignmentId !== row.assignmentId) throw new ContractError()
  if (result.graphVersionAddress !== null && result.graphVersionAddress !== row.graph?.graphVersionAddress) throw new ContractError()
  if (['HOLD', 'SIGNAL', 'STALE'].includes(result.kind) && (!result.assignmentId || !result.graphVersionAddress)) throw new ContractError()
}
export function verifyWatchlistMonitorSnapshot(snapshot: WatchlistMonitorSnapshot, context: WatchlistMonitorContext, members: readonly WatchlistMemberCandidate[]) {
  if (contextKey(snapshot.context) !== contextKey(context) || snapshot.rows.length !== members.length) throw new ContractError()
  const expected = new Set(members.map((item) => scopeMemberIdentity(item.member))), seen = new Set<string>()
  for (const row of snapshot.rows) {
    if (!expected.has(row.memberKey) || seen.has(row.memberKey)) throw new ContractError()
    verifyRow(row, row.memberKey); seen.add(row.memberKey)
  }
  return snapshot.rows
}
function monitorError(error: unknown) {
  if (error instanceof ApiError && /^(WATCHLIST_|MONITORING_)/.test(error.envelope?.code ?? '')) return error.envelope!.message
  return errorMessage(error)
}
const MONITOR_POLL_MS = 5_000
function needsMonitoringRefresh(rows: readonly WatchlistMonitorRow[] | undefined) {
  return rows?.some((row) => row.assignmentId !== null || row.monitoring === 'STARTING' || row.monitoring === 'ON') === true
}
type State = { api: StrategyApi; client: WatchlistMonitorClient | null | undefined; key: string;
  rows?: readonly WatchlistMonitorRow[]; loading: boolean; busy: boolean; error: string; uncertain: boolean; retryDelay?: number }
function monitorReadFailure(previous: State, error: unknown): State {
  const retryable = error instanceof ApiError && ['network', 'timeout', 'server'].includes(error.kind)
    && !/^(WATCHLIST_|MONITORING_|STATIC_SCOPE_|SCOPE_|PROJECT_)/.test(error.envelope?.code ?? '')
  const retryDelay = retryable ? Math.min((previous.retryDelay ?? MONITOR_POLL_MS / 2) * 2, 30_000) : undefined
  return { ...previous, loading: false, busy: false, uncertain: true, retryDelay,
    error: `${monitorError(error)} ${retryable ? 'Monitoring will retry automatically; saved rows are retained.' : 'Refresh rows to check the latest monitoring state.'}` }
}
function useMonitorRows(props: Props) {
  const { api, client, context, members } = props, key = contextKey(context)
  const [stored, setStored] = useState<State>({ api, client, key, loading: Boolean(client), busy: false, error: '', uncertain: false })
  const [attempt, setAttempt] = useState(0)
  const request = useRef<AbortController | null>(null)
  const active = useRef({ api, client, key }); active.current = { api, client, key }
  const state: State = stored.api === api && stored.client === client && stored.key === key ? stored
    : { api, client, key, loading: Boolean(client), busy: false, error: '', uncertain: false }
  function current(controller: AbortController) {
    return !controller.signal.aborted && request.current === controller && active.current.api === api && active.current.client === client && active.current.key === key
  }
  useEffect(() => {
    const controller = new AbortController(); request.current?.abort(); request.current = controller
    setStored((previous) => ({ api, client, key, loading: Boolean(client), busy: false, error: '', uncertain: false,
      rows: previous.api === api && previous.client === client && previous.key === key ? previous.rows : undefined }))
    if (client) void client.list(context, controller.signal).then((snapshot) => {
      const rows = verifyWatchlistMonitorSnapshot(snapshot, context, members)
      if (current(controller)) setStored({ api, client, key, rows, loading: false, busy: false, error: '', uncertain: false })
    }).catch((error) => { if (current(controller)) setStored((previous) => monitorReadFailure(previous, error)) })
    return () => { controller.abort(); request.current?.abort() }
  }, [api, client, key, attempt])
  useEffect(() => {
    if (!client || state.loading || state.busy) return
    if (state.uncertain ? !state.retryDelay : !needsMonitoringRefresh(state.rows)) return
    const controller = new AbortController()
    const timer = setTimeout(() => {
      if (controller.signal.aborted) return
      request.current?.abort(); request.current = controller
      void client.list(context, controller.signal).then((snapshot) => {
        if (!current(controller)) return
        const rows = verifyWatchlistMonitorSnapshot(snapshot, context, members)
        setStored((previous) => ({ ...previous, rows, error: '', uncertain: false, retryDelay: undefined }))
      }).catch((error) => {
        if (current(controller)) setStored((previous) => monitorReadFailure(previous, error))
      })
    }, state.retryDelay ?? MONITOR_POLL_MS)
    return () => { clearTimeout(timer); controller.abort() }
  }, [api, client, key, attempt, stored])
  async function change(member: ScopeMember, command: (signal: AbortSignal) => Promise<WatchlistMonitorRow>) {
    if (!client || state.busy || state.uncertain) return
    const controller = new AbortController(); request.current?.abort(); request.current = controller
    setStored({ ...state, busy: true, error: '' })
    try {
      const receipt = await command(controller.signal)
      if (!current(controller)) return
      verifyRow(receipt, scopeMemberIdentity(member))
      const snapshot = await client.list(context, controller.signal)
      const rows = verifyWatchlistMonitorSnapshot(snapshot, context, members)
      if (current(controller)) setStored({ api, client, key, rows, loading: false, busy: false, error: '', uncertain: false })
    } catch (error) {
      if (current(controller)) setStored({ ...state, busy: false, uncertain: true,
        error: `${monitorError(error)} Refresh rows to check the saved state before retrying. Your choices are retained.` })
    }
  }
  return { state, change, refresh: () => setAttempt((value) => value + 1) }
}
export function matchesWatchlistFilter(row: WatchlistMonitorRow | undefined, filter: Filter) {
  if (filter === 'ALL') return true
  if (filter === 'PINNED') return row?.pinned === true
  if (filter === 'SIGNALS') return row?.result.kind === 'SIGNAL'
  return !row || row.monitoring === 'BLOCKED' || ['STALE', 'ERROR', 'WARMUP'].includes(row.result.kind)
}
function ResultCell({ row }: { row: WatchlistMonitorRow | undefined }) {
  if (!row) return <td><span className="scope-row-state">Unavailable</span><small>No verified monitoring result is available.</small></td>
  const result = row.result
  const title = { NOT_EVALUATED: 'Not evaluated', HOLD: 'HOLD', SIGNAL: result.label, WARMUP: 'Warming up', STALE: 'Stale result', ERROR: 'Error' }[result.kind]
  return <td><span className={`scope-row-state scope-row-${result.kind.toLowerCase()}`}>{title}</span>
    {result.label !== title && <small>{result.label}</small>}
    {result.kind === 'HOLD' && <small>Evaluated · no new signal</small>}
    {result.warmup && <small>{result.warmup.available} / {result.warmup.required} warmup bars</small>}
    {result.evaluatedAt && <small>{formatIndiaTimestamp(result.evaluatedAt)}</small>}
    {result.reason && <small>{result.reason}</small>}</td>
}
function strategyOptions(graphs: readonly GraphSummary[], row: WatchlistMonitorRow | undefined) {
  const options = graphs.filter((graph) => graph.current_version !== null).map((graph) => ({
    value: JSON.stringify([graph.identifier, graph.current_version]), label: `${graph.display_name} · v${graph.current_version}`,
    graphId: graph.identifier, graphVersion: graph.current_version! }))
  const saved = row?.graph
  if (saved && !options.some((option) => option.graphId === saved.graphId && option.graphVersion === saved.graphVersion)) {
    options.push({ value: JSON.stringify([saved.graphId, saved.graphVersion]), label: `${saved.label} · v${saved.graphVersion}`, graphId: saved.graphId, graphVersion: saved.graphVersion })
  }
  return options
}
function StrategyCells({ row, label, graphs, locked, onConfigure }: { row: WatchlistMonitorRow | undefined; label: string;
  graphs: readonly GraphSummary[]; locked: boolean; onConfigure: (selection: WatchlistStrategySelection) => void }) {
  const options = strategyOptions(graphs, row)
  const initial = row?.graph ? JSON.stringify([row.graph.graphId, row.graph.graphVersion]) : ''
  const [strategy, setStrategy] = useState(initial), [timeframe, setTimeframe] = useState(row?.timeframe ?? '')
  const saved = useRef({ strategy: initial, timeframe: row?.timeframe ?? '' })
  useEffect(() => {
    const previous = saved.current, nextTimeframe = row?.timeframe ?? ''
    setStrategy((value) => !row || value === previous.strategy ? initial : value)
    setTimeframe((value) => !row || value === previous.timeframe ? nextTimeframe : value)
    saved.current = { strategy: initial, timeframe: nextTimeframe }
  }, [initial, row?.timeframe])
  const selected = options.find((option) => option.value === strategy)
  const changed = strategy !== initial || timeframe !== row?.timeframe
  const validTimeframe = row?.supportedTimeframes.some((option) => option.value === timeframe) === true
  const allowed = !locked && row?.canConfigure === true
  return <><td><TraderSelect label={`${label} strategy`} value={strategy} disabled={!allowed} onValueChange={setStrategy}
    options={[{ value: '', label: 'Choose strategy' }, ...options]} /></td>
    <td><TraderSelect label={`${label} timeframe`} value={timeframe} disabled={!allowed} onValueChange={setTimeframe}
      options={[{ value: '', label: 'Choose timeframe' }, ...(row?.supportedTimeframes ?? [])]} />
      <button type="button" className="scope-row-apply" aria-label={`Apply strategy and timeframe for ${label}`}
        disabled={!allowed || !selected || !validTimeframe || !changed}
        onClick={() => { if (selected && validTimeframe) onConfigure({ graphId: selected.graphId, graphVersion: selected.graphVersion, timeframe }) }}>Apply</button></td></>
}
function MonitoringCell({ row, label, locked, onToggle }: { row: WatchlistMonitorRow | undefined; label: string; locked: boolean; onToggle: (enabled: boolean) => void }) {
  const enabled = row?.monitoring === 'ON' || row?.monitoring === 'STARTING'
  return <td><button type="button" role="switch" aria-label={`${label} monitoring`} aria-checked={enabled}
    disabled={locked || !row?.canSetMonitoring} onClick={() => onToggle(!enabled)}>
    {row ? ({ OFF: 'Off', ON: 'On', STARTING: 'Starting…', PAUSED: 'Paused', BLOCKED: 'Unavailable' }[row.monitoring]) : 'Unavailable'}</button>
    {row?.reason && <small>{row.reason}</small>}</td>
}
export function WatchlistMonitorTable(props: Props) {
  const { client, context, members, graphs, onDetails, onRemove, canRemove } = props
  const monitor = useMonitorRows(props), { state } = monitor
  const [filter, setFilter] = useState<Filter>('ALL')
  const locked = props.locked || props.readOnly || state.busy || state.loading || state.uncertain
  const visible = members.filter((item) => matchesWatchlistFilter(state.rows?.find((row) => row.memberKey === scopeMemberIdentity(item.member)), filter))
  return <section className="scope-monitor" aria-label="Watchlist results">
    <div className="scope-monitor-toolbar"><div role="group" aria-label="Filter watchlist">{([
      ['ALL', 'All'], ['PINNED', 'Pinned'], ['SIGNALS', 'Signals'], ['ATTENTION', 'Needs attention']] as const).map(([value, label]) =>
      <button key={value} type="button" aria-pressed={filter === value} onClick={() => setFilter(value)}>{label}</button>)}</div>
      <button type="button" disabled={!client || state.busy} onClick={monitor.refresh}>Refresh rows</button></div>
    {!client && <p className="scope-monitor-note">Monitoring controls are not connected yet. You can add instruments and prepare history; no live results are inferred.</p>}
    {state.loading && <p role="status">Loading saved row settings and results…</p>}
    {state.busy && <p role="status">Saving and checking row settings…</p>}
    {state.error && <p role="alert">{state.error}</p>}
    <div className="scope-table-scroll"><table className="scope-members scope-results-table"><caption>Saved instruments</caption>
      <thead><tr><th scope="col">Pin</th><th scope="col">Instrument</th><th scope="col">Strategy</th><th scope="col">Timeframe</th><th scope="col">Latest result</th><th scope="col">Monitoring</th><th scope="col">Actions</th></tr></thead>
      <tbody>{visible.map((item) => {
        const key = scopeMemberIdentity(item.member), row = state.rows?.find((value) => value.memberKey === key), label = item.label ?? 'Instrument name unavailable'
        const apply = (command: (signal: AbortSignal) => Promise<WatchlistMonitorRow>) => void monitor.change(item.member, command)
        return <tr key={key}><td><button type="button" aria-label={`${row?.pinned ? 'Unpin' : 'Pin'} ${label}`} aria-pressed={row?.pinned === true}
          disabled={locked || !row?.canPin} onClick={() => { if (client && row) apply((signal) => client.pin(context, item.member, row.configurationRevision, !row.pinned, signal)) }}>{row?.pinned ? '★' : '☆'}</button></td>
          <th scope="row"><button type="button" disabled={props.locked || !item.label} onClick={() => onDetails(item.member)}>{label}</button></th>
          <StrategyCells row={row} label={label} graphs={graphs} locked={locked} onConfigure={(selection) => { if (client && row) apply((signal) => client.configure(context, item.member, row.configurationRevision, selection, signal)) }} />
          <ResultCell row={row} /><MonitoringCell row={row} label={label} locked={locked} onToggle={(enabled) => { if (client && row) apply((signal) => client.setMonitoring(context, item.member, row.configurationRevision, enabled, signal)) }} />
          <td><button type="button" disabled={props.locked} onClick={() => onDetails(item.member)}>Details</button>
            <button type="button" aria-label={`Remove ${label}`} disabled={locked || !canRemove} onClick={() => onRemove(item.member)}>Remove</button></td></tr>
      })}</tbody></table></div>
    {!visible.length && <p>No instruments match this filter.</p>}
  </section>
}
