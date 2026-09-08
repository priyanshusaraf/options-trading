import { useEffect, useRef, useState, type FormEvent } from 'react'
import { ApiError, errorMessage, type StrategyApi } from '../../shell/api'
import { ContractError, validHistoryDate, type ProviderHistoryReceipt, type ResearchDataset } from '../../shell/contracts'

export function providerHistoryDates(now = new Date()) {
  // India uses UTC+05:30. Subtract one day after finding the local date.
  const yesterday = now.getTime() + 19800000 - 86400000
  return { start: new Date(yesterday - 365 * 86400000).toISOString().slice(0, 10), end: new Date(yesterday).toISOString().slice(0, 10) }
}

function historyError(error: unknown) {
  if (error instanceof ApiError && error.envelope?.code.startsWith('HISTORICAL_')) return error.envelope.message
  return errorMessage(error)
}

function definiteHistoryRefusal(error: unknown) {
  return error instanceof ApiError && (['input', 'access', 'manifest'].includes(error.kind)
    || Boolean(error.envelope?.code.startsWith('HISTORICAL_')))
}

type HistoryState = { api: StrategyApi; context: string; busy: boolean; message: string; error?: boolean; receipt?: ProviderHistoryReceipt; refreshNeeded?: boolean }
type Props = { api: StrategyApi; projectId: string; selectionAddress: string; disabled: boolean;
  onSaved: (receipt: ProviderHistoryReceipt | undefined, datasets: readonly ResearchDataset[]) => void }

function useProviderHistory({ api, projectId, selectionAddress, onSaved }: Props) {
  const context = `${projectId}:${selectionAddress}`
  const [dates, setDates] = useState(providerHistoryDates)
  const [stored, setStored] = useState<HistoryState>({ api, context, busy: false, message: '' })
  const request = useRef<AbortController | null>(null)
  const active = useRef({ api, projectId, selectionAddress }); active.current = { api, projectId, selectionAddress }
  const saved = useRef(onSaved); saved.current = onSaved
  useEffect(() => () => { request.current?.abort(); request.current = null }, [api, projectId, selectionAddress])
  const state: HistoryState = stored.api === api && stored.context === context ? stored : { api, context, busy: false, message: '' }
  function current(controller: AbortController) {
    return !controller.signal.aborted && active.current.api === api
      && active.current.projectId === projectId && active.current.selectionAddress === selectionAddress
  }
  async function refresh(receipt: ProviderHistoryReceipt | undefined, controller: AbortController) {
    const datasets = await api.researchDatasets(projectId, controller.signal)
    if (!current(controller)) return
    if (receipt) verifyRefreshedReceipt(receipt, datasets, selectionAddress)
    setStored({ api, context, busy: false, receipt, refreshNeeded: !receipt, message: receipt ? ''
      : 'Saved history refreshed. Check the list before fetching again; the previous request may still be finishing.' })
    saved.current(receipt, datasets)
  }
  function failed(error: unknown, receipt?: ProviderHistoryReceipt) {
    const uncertain = !definiteHistoryRefusal(error)
    const next = uncertain ? ' The request may still finish. Refresh saved history before fetching again.' : ''
    setStored({ api, context, busy: false, receipt, error: true, refreshNeeded: Boolean(receipt) || uncertain, message: receipt
      ? `History was saved, but the dataset list could not be refreshed. ${errorMessage(error)}`
      : `${historyError(error)} Your dates are retained.${next}` })
  }
  async function fetchHistory() {
    if (request.current) return
    const controller = new AbortController(); request.current = controller
    setStored({ api, context, busy: true, message: 'Fetching and saving daily history…' })
    let receipt: ProviderHistoryReceipt | undefined
    try {
      receipt = await api.importProviderHistory(projectId, { selection_address: selectionAddress,
        start_date: dates.start, end_date: dates.end, interval: 'day' }, controller.signal)
      if (current(controller)) await refresh(receipt, controller)
    } catch (error) { if (current(controller)) failed(error, receipt) }
    finally { if (request.current === controller) request.current = null }
  }
  async function retryRefresh() {
    if (request.current) return
    const controller = new AbortController(); request.current = controller
    setStored({ ...state, busy: true, message: 'Refreshing saved history…' })
    try { await refresh(state.receipt, controller) }
    catch (error) { if (current(controller)) failed(error, state.receipt) }
    finally { if (request.current === controller) request.current = null }
  }
  return { state, dates, setDates, fetchHistory, retryRefresh }
}

function verifyRefreshedReceipt(receipt: ProviderHistoryReceipt, datasets: readonly ResearchDataset[], selectionAddress: string) {
  const item = datasets.find((value) => value.manifest_address === receipt.item.manifest_address)
  if (!item || item.provider_selection_address !== selectionAddress || item.instrument_address !== receipt.item.instrument_address) throw new ContractError()
}

function historyDay(value: string | number) {
  return new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Kolkata', day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(value))
}

export function historyCount(count: number, unit: string) {
  return `${count.toLocaleString('en-GB')} ${unit}${count === 1 ? '' : 's'}`
}

export function formatIndiaTimestamp(value: string) {
  const display = new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Kolkata', day: 'numeric', month: 'long', year: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23' }).format(new Date(value))
  return `${display} IST`
}

export function historyDatasetLabel(dataset: ResearchDataset) {
  const daily = dataset.interval === 'day' || dataset.interval === '1d'
  const period = daily ? `${historyDay(dataset.event_start)} → ${historyDay(Date.parse(dataset.event_end) - 1)}`
    : `${formatIndiaTimestamp(dataset.event_start)} → ${formatIndiaTimestamp(dataset.event_end)} (end exclusive)`
  return `${daily ? 'Daily' : dataset.interval} · ${historyCount(dataset.bar_count, 'bar')} · ${period}`
}

function HistoryReceipt({ receipt }: { receipt: ProviderHistoryReceipt }) {
  return <div className="scope-history-receipt" role="status">
    <p>{receipt.reused ? 'Reused saved history:' : 'Saved'} {historyCount(receipt.item.bar_count, 'daily bar')}.</p>
    <dl><div><dt>Requested dates</dt><dd>{historyDay(receipt.requested_start)} → {historyDay(receipt.requested_end)}</dd></div>
      <div><dt>Returned bar dates</dt><dd>{historyDay(receipt.returned_start)} → {historyDay(receipt.returned_end)}</dd></div></dl>
    <p>{receipt.reused ? 'Original capture: ' : ''}{historyCount(receipt.request_count, 'provider request')}; {receipt.empty_request_count} returned no bars.</p>
    {receipt.item.calendar_coverage === 'NOT_ASSERTED' && <p>Missing trading sessions have not been verified. Returned dates do not prove complete history.</p>}
  </div>
}

export function ProviderHistoryForm(props: Props) {
  const { state, dates, setDates, fetchHistory, retryRefresh } = useProviderHistory(props)
  const valid = validHistoryDate(dates.start) && validHistoryDate(dates.end) && dates.start <= dates.end
  function submit(event: FormEvent) {
    event.preventDefault()
    if (valid && !props.disabled && !state.busy) void fetchHistory()
  }
  return <form className="scope-history" onSubmit={submit} aria-label="Fetch provider history">
    <h3>Get daily history</h3>
    <p>Dates use India time. Fetch history for this saved instrument through your connected data account.</p>
    <fieldset disabled={props.disabled || state.busy}><legend className="scope-sr-only">History dates</legend>
      <label>Start date<input type="date" required value={dates.start} onChange={(event) => setDates({ ...dates, start: event.target.value })} /></label>
      <label>End date<input type="date" required value={dates.end} onChange={(event) => setDates({ ...dates, end: event.target.value })} /></label>
      <button disabled={!valid} type="submit">Fetch daily history</button>
    </fieldset>
    {!valid && <p role="alert">Choose valid dates with the start on or before the end.</p>}
    <p>Requests are split into windows of up to 1,900 days. This app supports up to 2,000 bars per backtest input. The provider’s total history retention is unknown.</p>
    {state.message && <p role={state.error && !state.busy ? 'alert' : 'status'}>{state.message}</p>}
    {state.refreshNeeded && <button type="button" disabled={props.disabled || state.busy} onClick={() => void retryRefresh()}>Refresh saved history</button>}
    {state.receipt && <HistoryReceipt receipt={state.receipt} />}
  </form>
}
