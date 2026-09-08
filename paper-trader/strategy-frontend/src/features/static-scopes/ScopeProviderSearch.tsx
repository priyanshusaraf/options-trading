import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { DataConnectionRequestError, providerExchangeOptions, providerReferenceLabel, type DataConnectionClient, type ProviderExchange,
  type ProviderInstrumentReference, type ProviderInstrumentSearchResult, type SavedProviderSelection } from '../connections/dataConnectionClient'

interface SearchState {
  client: DataConnectionClient
  busy: boolean
  result?: ProviderInstrumentSearchResult
  error?: string
  message?: string
}
function selectionError(error: unknown): string {
  if (error instanceof DataConnectionRequestError) {
    if (error.status === 401 || error.status === 403) return 'Sign in again to use your data provider. Your watchlist draft is retained.'
    if (error.code === 'INSTRUMENT_SELECTION_UNAVAILABLE') return 'The instrument details changed or are unavailable. Search again and choose a current result. Your draft is retained.'
    if (error.code === 'DATA_REAUTH_REQUIRED') return 'Reconnect your data provider in Account, then retry. Your draft is retained.'
    if (error.code === 'DATA_CONNECTION_UNAVAILABLE') return 'Your data connection is unavailable. Open Data provider in Account to complete or reconnect it, then retry. Your draft is retained.'
    if (error.code === 'INVALID_PROVIDER_REFERENCE') return 'The instrument details are incomplete. Search again and select a current result. Your draft is retained.'
    if (error.status === 422) return 'Enter 2–64 search characters and choose a provider exchange or All exchanges.'
  }
  return 'The provider response could not be verified. Check your data connection and retry. Your draft is retained.'
}
function useProviderSelection(client: DataConnectionClient, enabled: boolean, onSelected: (value: SavedProviderSelection) => void) {
  const [storedInput, setInput] = useState({ client, query: '', exchange: 'ALL' as ProviderExchange })
  const [exchanges, setExchanges] = useState<{ client: DataConnectionClient; values: readonly string[] }>({ client, values: [] })
  const [stored, setStored] = useState<SearchState>({ client, busy: false })
  const latest = useRef({ client, enabled, onSelected })
  latest.current = { client, enabled, onSelected }
  const request = useRef<AbortController | null>(null)
  const input = storedInput.client === client ? storedInput : { client, query: '', exchange: 'ALL' as ProviderExchange }
  const state = stored.client === client ? stored : { client, busy: false }
  useEffect(() => () => request.current?.abort(), [client])
  useEffect(() => { if (!enabled) { request.current?.abort(); setStored((value) => ({ ...value, busy: false })) } }, [enabled])
  function current(controller: AbortController) {
    return !controller.signal.aborted && request.current === controller && latest.current.client === client && latest.current.enabled
  }
  function change(query: string, exchange: ProviderExchange) {
    request.current?.abort()
    setInput({ client, query, exchange }); setStored({ client, busy: false })
  }
  async function search() {
    if (!enabled) return
    request.current?.abort(); const controller = new AbortController(); request.current = controller
    setStored({ client, busy: true })
    try {
      const result = await client.searchInstruments(input.query, input.exchange, controller.signal)
      if (current(controller)) { setExchanges({ client, values: result.available_exchanges }); setStored({ client, busy: false, result }) }
    } catch (error) { if (current(controller)) setStored({ client, busy: false, error: selectionError(error) }) }
  }
  async function select(item: ProviderInstrumentReference) {
    if (!enabled || state.busy) return
    request.current?.abort(); const controller = new AbortController(); request.current = controller
    setStored({ ...state, client, busy: true, error: undefined, message: undefined })
    try {
      const selected = await client.selectInstrument(item, controller.signal)
      if (!current(controller)) return
      latest.current.onSelected(selected)
      setStored({ ...state, client, busy: false, message: `${providerReferenceLabel(selected.selection.reference)} is in the draft. Save the watchlist to keep it.` })
    } catch (error) { if (current(controller)) setStored({ ...state, client, busy: false, error: selectionError(error) }) }
  }
  return { input, state, exchangeOptions: providerExchangeOptions(exchanges.client === client ? exchanges.values : [], input.exchange), change, search, select }
}
function SearchResults({ result, disabled, onSelect }: { result: ProviderInstrumentSearchResult; disabled: boolean; onSelect: (item: ProviderInstrumentReference) => void }) {
  if (!result.items.length) return <p role="status">No instruments matched. Try another symbol or name.</p>
  return <><ul className="scope-provider-results">{result.items.map((item) => <li key={JSON.stringify(item)}>
    <span>{providerReferenceLabel(item)}</span>
    <button type="button" aria-label={`Add ${providerReferenceLabel(item)}`} disabled={disabled} onClick={() => onSelect(item)}>Add {item.symbol}</button>
  </li>)}</ul>{result.has_more && <p>Showing the first 20 matches. Refine your search to see a smaller list.</p>}</>
}
export function ScopeProviderSearch({ client, disabled, onSelected }: { client: DataConnectionClient; disabled: boolean; onSelected: (value: SavedProviderSelection) => void }) {
  const search = useProviderSelection(client, !disabled, onSelected)
  const { input, state } = search
  function searchOnEnter(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key !== 'Enter') return
    event.preventDefault(); void search.search()
  }
  return <section className="scope-provider-search" aria-label="Add from data provider"><h3>Add from your data provider</h3>
    <p>You can save any instrument from your provider. Backtests need verified instrument details and compatible historical data.</p>
    <div className="scope-provider-query"><label>Provider symbol or name<input type="search" maxLength={64} value={input.query} disabled={disabled}
      onKeyDown={searchOnEnter} onChange={(event) => search.change(event.target.value, input.exchange)} /></label>
      <label>Provider exchange<select value={input.exchange} disabled={disabled} onChange={(event) => search.change(input.query, event.target.value as ProviderExchange)}>{search.exchangeOptions.map((exchange) => <option key={exchange} value={exchange}>{exchange === 'ALL' ? 'All exchanges' : exchange}</option>)}</select></label>
      <button type="button" disabled={disabled || state.busy} onClick={() => void search.search()}>Search provider</button></div>
    {state.busy && <p role="status">Checking the current provider reference…</p>}{state.error && <p role="alert">{state.error}</p>}{state.message && <p role="status">{state.message}</p>}
    {state.result && <SearchResults result={state.result} disabled={disabled || state.busy} onSelect={(item) => void search.select(item)} />}
  </section>
}
