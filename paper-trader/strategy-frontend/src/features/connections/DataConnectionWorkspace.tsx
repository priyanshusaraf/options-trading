import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import {
  DataConnectionContractError,
  providerExchangeOptions,
  DataConnectionRequestError,
  type DataConnectionClient,
  type DataConnectionState,
  type DataConnectionStatus,
  type ProviderExchange,
  type ProviderInstrumentSearchResult,
} from './dataConnectionClient'
import './data-connection.css'

type View =
  | { readonly kind: 'LOADING' }
  | { readonly kind: 'ERROR' }
  | { readonly kind: 'READY'; readonly status: DataConnectionStatus }

type Mutation = 'create' | 'keys' | 'rotate' | 'reauthenticate' | 'revoke'

const COPY: Readonly<Record<DataConnectionState, Readonly<{ title: string; detail: string }>>> = Object.freeze({
  CONNECTION_REQUIRED: Object.freeze({
    title: 'No data connection',
    detail: 'Create the encrypted local connection record before adding application keys.',
  }),
  APP_KEYS_REQUIRED: Object.freeze({
    title: 'Application keys required',
    detail: 'Add the application key and secret. Strategy OS encrypts them before storage.',
  }),
  REAUTH_REQUIRED: Object.freeze({
    title: 'Reconnect this browser session',
    detail: 'Your app keys are stored. This browser needs a fresh Zerodha sign-in.',
  }),
  SESSION_PRESENT_UNVERIFIED: Object.freeze({
    title: 'Session stored, provider not verified',
    detail: 'This browser completed sign-in. Expiry, quota, provider access and live data readiness remain unverified.',
  }),
  REVOKED: Object.freeze({
    title: 'Provider disconnected',
    detail: 'The encrypted credential was destroyed. Create a new record to start again.',
  }),
  UNAVAILABLE: Object.freeze({
    title: 'Connection state unavailable',
    detail: 'Strategy OS could not prove the account, session, vault or stored connection state. Retry after the service is restored.',
  }),
})

function message(error: unknown): string {
  if (error instanceof DataConnectionRequestError) {
    if (error.status === 409) return 'The connection changed or this action is not available. Refresh the server state.'
    if (error.status === 503) return 'The credential vault is unavailable. Retry after it is restored.'
    if (error.status === 401 || error.status === 403) return 'Your verified session no longer has access.'
    return 'The provider action was not accepted. Check the current state and try again.'
  }
  if (error instanceof DataConnectionContractError) {
    return 'The server response could not be verified. Refresh before trying again.'
  }
  return 'The provider connection service is unavailable. Retry.'
}

type SearchView = { kind: 'idle' | 'loading' } | { kind: 'error'; message: string; invalid: boolean }
  | { kind: 'ready'; result: ProviderInstrumentSearchResult }

const SEARCH_MESSAGES: Readonly<Record<string, string>> = {
  INVALID_PROVIDER_REFERENCE: 'The instrument details are incomplete. Search again and select a current result.',
  INVALID_INSTRUMENT_SEARCH: 'Enter 2–64 letters, numbers or symbol characters, then search again.',
  DATA_REAUTH_REQUIRED: 'Reconnect to Zerodha above, then retry your search. Your search text is kept.',
  DATA_CONNECTION_UNAVAILABLE: 'Refresh your connection or sign in again, then retry your search.',
  DATA_PROVIDER_BUSY: 'Zerodha is temporarily unavailable. Wait a moment, then search again.',
  DATA_VAULT_UNAVAILABLE: 'Connection credentials are temporarily unavailable. Retry after the service recovers.',
  INSTRUMENT_SEARCH_UNAVAILABLE: 'The current instrument list is unavailable. Reconnect or retry your search.',
}

function instrumentSearchMessage(error: unknown): string {
  if (error instanceof DataConnectionRequestError) {
    if (error.status === 401 || error.status === 403) return 'Sign in again to search your data provider.'
    return SEARCH_MESSAGES[error.code ?? ''] ?? 'The search was not accepted. Check your connection and try again.'
  }
  if (error instanceof DataConnectionContractError) return 'The instrument response could not be verified. Retry the search.'
  return 'The search service could not be reached. Check your connection and retry.'
}

function useInstrumentSearch(client: DataConnectionClient, enabled: boolean) {
  const [storedInput, setInput] = useState({ client, query: '', exchange: 'ALL' as ProviderExchange })
  const [exchanges, setExchanges] = useState<{ client: DataConnectionClient; values: readonly string[] }>({ client, values: [] })
  const [output, setOutput] = useState<{ client: DataConnectionClient; view: SearchView }>({ client, view: { kind: 'idle' } })
  // Bind both rendered inputs and results during render, before passive cleanup.
  const input = storedInput.client === client ? storedInput : { client, query: '', exchange: 'ALL' as ProviderExchange }
  const view: SearchView = output.client === client ? output.view : { kind: 'idle' }
  const request = useRef<AbortController | null>(null)
  const clear = useCallback(() => { request.current?.abort(); setOutput({ client, view: { kind: 'idle' } }) }, [client])
  useEffect(() => {
    clear()
    return () => request.current?.abort()
  }, [clear])
  useEffect(() => { if (!enabled) clear() }, [clear, enabled])
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!enabled) return
    request.current?.abort()
    const owned = new AbortController()
    request.current = owned
    setOutput({ client, view: { kind: 'loading' } })
    try {
      const result = await client.searchInstruments(input.query, input.exchange, owned.signal)
      if (!owned.signal.aborted) { setExchanges({ client, values: result.available_exchanges }); setOutput({ client, view: { kind: 'ready', result } }) }
    } catch (error) {
      if (!owned.signal.aborted) setOutput({ client, view: { kind: 'error', message: instrumentSearchMessage(error),
        invalid: error instanceof DataConnectionRequestError && error.status === 422 } })
    }
  }
  return { query: input.query, exchange: input.exchange, exchangeOptions: providerExchangeOptions(exchanges.client === client ? exchanges.values : [], input.exchange), view, submit,
    changeQuery: (value: string) => { clear(); setInput({ client, query: value, exchange: input.exchange }) },
    changeExchange: (value: ProviderExchange) => { clear(); setInput({ client, query: input.query, exchange: value }) } }
}

function InstrumentResults({ result }: { result: ProviderInstrumentSearchResult }) {
  if (result.items.length === 0) return <p role="status">No current references match “{result.query}” on {result.exchange}. Try another symbol or name.</p>
  return <>
    <div className="data-connection__search-table"><table>
      <caption>Current provider references for “{result.query}” · {result.exchange}</caption>
      <thead><tr><th scope="col">Symbol</th><th scope="col">Name</th><th scope="col">Exchange</th><th scope="col">Segment / type</th><th scope="col">Expiry</th><th scope="col">Strike</th></tr></thead>
      <tbody>{result.items.map((item) => <tr key={`${item.exchange}:${item.symbol}:${item.token}:${item.name}`}>
        <th scope="row">{item.symbol}</th><td>{item.name || '—'}</td><td>{item.exchange}</td><td>{item.segment} / {item.instrument_type}</td><td>{item.expiry ?? '—'}</td><td>{item.strike ?? '—'}</td>
      </tr>)}</tbody>
    </table></div>
    {result.has_more && <p role="status">Showing the first 20 matches. Refine your search to narrow the list.</p>}
  </>
}

function InstrumentSearch({ client, status, busy }: { client: DataConnectionClient; status: DataConnectionStatus; busy: boolean }) {
  const enabled = status.state === 'SESSION_PRESENT_UNVERIFIED' && !busy
  const search = useInstrumentSearch(client, enabled)
  const error = useRef<HTMLParagraphElement>(null)
  useEffect(() => { if (search.view.kind === 'error') error.current?.focus() }, [search.view])
  return <section className="data-connection__instrument-search" aria-labelledby="provider-search-title">
    <h2 id="provider-search-title">Find an instrument</h2>
    <p id="provider-search-help">Search any instrument from your connected provider. Backtests need verified instrument details and compatible historical data.</p>
    <form className="data-connection__search-form" onSubmit={(event) => void search.submit(event)} aria-describedby="provider-search-help">
      <label>Symbol or name<input type="search" required minLength={2} maxLength={64} value={search.query}
        onChange={(event) => search.changeQuery(event.target.value)} disabled={!enabled}
        aria-invalid={search.view.kind === 'error' && search.view.invalid} /></label>
      <label>Exchange<select value={search.exchange} disabled={!enabled}
        onChange={(event) => search.changeExchange(event.target.value as ProviderExchange)}>{search.exchangeOptions.map((exchange) => <option key={exchange} value={exchange}>{exchange === 'ALL' ? 'All exchanges' : exchange}</option>)}</select></label>
      <button disabled={!enabled || search.view.kind === 'loading'}>Search instruments</button>
    </form>
    {!enabled && <p>Complete the data connection above before searching.</p>}
    {search.view.kind === 'loading' && <p role="status">Searching current instruments…</p>}
    {search.view.kind === 'error' && <p ref={error} className="data-connection__form-error" role="alert" tabIndex={-1}>{search.view.message}</p>}
    {enabled && search.view.kind === 'ready' && <InstrumentResults result={search.view.result} />}
  </section>
}

function DisconnectProvider({ busy, pending, confirmed, onAsk, onConfirm, onCancel }: {
  busy: boolean; pending: Mutation | null; confirmed: boolean; onAsk: () => void; onConfirm: () => void; onCancel: () => void
}) {
  return <div className="data-connection__danger">{!confirmed
    ? <button disabled={busy} onClick={onAsk}>Disconnect provider</button>
    : <><p><strong>Disconnect and destroy the stored credential?</strong> The audit record remains.</p>
      <div className="data-connection__button-row">
        <button disabled={busy} onClick={onConfirm}>{pending === 'revoke' ? 'Disconnecting…' : 'Confirm disconnect'}</button>
        <button disabled={busy} onClick={onCancel}>Cancel</button>
      </div></>}
  </div>
}

export function DataConnectionWorkspace({
  client,
  navigateExternal = (url) => window.location.assign(url),
}: {
  readonly client: DataConnectionClient
  readonly navigateExternal?: (url: string) => void
}) {
  const [view, setView] = useState<View>({ kind: 'LOADING' })
  const [pending, setPending] = useState<Mutation | null>(null)
  const [actionMessage, setActionMessage] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [apiSecret, setApiSecret] = useState('')
  const [showRotate, setShowRotate] = useState(false)
  const [confirmRevoke, setConfirmRevoke] = useState(false)
  const [formError, setFormError] = useState('')
  const mounted = useRef(false)
  const generation = useRef(0)
  const controller = useRef<AbortController | null>(null)
  const heading = useRef<HTMLHeadingElement>(null)
  const errorSummary = useRef<HTMLDivElement>(null)
  const previousState = useRef<DataConnectionState | null>(null)

  const clearSecrets = useCallback(() => {
    setApiKey('')
    setApiSecret('')
  }, [])

  const project = useCallback((status: DataConnectionStatus) => {
    const changed = previousState.current !== null && previousState.current !== status.state
    previousState.current = status.state
    setView({ kind: 'READY', status })
    setShowRotate(false)
    setConfirmRevoke(false)
    if (changed) queueMicrotask(() => heading.current?.focus())
  }, [])

  const load = useCallback(async () => {
    controller.current?.abort()
    const owned = new AbortController()
    controller.current = owned
    const ownedGeneration = ++generation.current
    setView({ kind: 'LOADING' })
    setActionMessage('')
    try {
      const status = await client.status(owned.signal)
      if (mounted.current && !owned.signal.aborted && generation.current === ownedGeneration) project(status)
    } catch {
      if (mounted.current && !owned.signal.aborted && generation.current === ownedGeneration) setView({ kind: 'ERROR' })
    }
  }, [client, project])

  useEffect(() => {
    mounted.current = true
    queueMicrotask(() => { if (mounted.current) void load() })
    return () => {
      mounted.current = false
      generation.current += 1
      controller.current?.abort()
      clearSecrets()
    }
  }, [clearSecrets, load])

  const mutate = useCallback(async (
    action: Mutation,
    run: (signal: AbortSignal) => Promise<DataConnectionStatus>,
  ) => {
    controller.current?.abort()
    const owned = new AbortController()
    controller.current = owned
    const ownedGeneration = ++generation.current
    setPending(action)
    setActionMessage('')
    try {
      const status = await run(owned.signal)
      if (mounted.current && !owned.signal.aborted && generation.current === ownedGeneration) {
        project(status)
        setActionMessage(action === 'revoke' ? 'Provider disconnected.' : 'Connection state refreshed.')
      }
    } catch (error) {
      if (mounted.current && !owned.signal.aborted && generation.current === ownedGeneration) {
        setActionMessage(message(error))
      }
    } finally {
      clearSecrets()
      if (mounted.current && generation.current === ownedGeneration) setPending(null)
    }
  }, [clearSecrets, project])

  function submitKeys(event: FormEvent<HTMLFormElement>, rotate: boolean) {
    event.preventDefault()
    if (!apiKey || !apiSecret) {
      clearSecrets()
      setFormError('Enter both the application key and application secret.')
      queueMicrotask(() => errorSummary.current?.focus())
      return
    }
    if (new TextEncoder().encode(apiKey).byteLength > 4096
      || new TextEncoder().encode(apiSecret).byteLength > 4096) {
      clearSecrets()
      setFormError('Each value must be 4,096 bytes or fewer.')
      queueMicrotask(() => errorSummary.current?.focus())
      return
    }
    setFormError('')
    const keys = { api_key: apiKey, api_secret: apiSecret }
    void mutate(rotate ? 'rotate' : 'keys', (signal) => rotate
      ? client.rotateAppKeys(keys, signal)
      : client.storeAppKeys(keys, signal))
  }

  async function reconnect() {
    controller.current?.abort()
    const owned = new AbortController()
    controller.current = owned
    const ownedGeneration = ++generation.current
    setPending('reauthenticate')
    setActionMessage('')
    try {
      const { login_url } = await client.initiate(owned.signal)
      if (mounted.current && !owned.signal.aborted && generation.current === ownedGeneration) {
        clearSecrets()
        navigateExternal(login_url)
      }
    } catch (error) {
      if (mounted.current && !owned.signal.aborted && generation.current === ownedGeneration) {
        setActionMessage(message(error))
        setPending(null)
      }
    }
  }

  if (view.kind === 'LOADING') return <section className="data-connection" aria-busy="true">
    <span className="data-connection__eyebrow">Account / Data provider</span>
    <h1>Loading provider state</h1>
    <div className="data-connection__loading" role="status">Checking the server-owned connection record…</div>
  </section>

  if (view.kind === 'ERROR') return <section className="data-connection">
    <span className="data-connection__eyebrow">Account / Data provider</span>
    <h1 tabIndex={-1}>Provider state could not be loaded</h1>
    <p role="alert">No cached state is shown. Retry the server check.</p>
    <button onClick={() => void load()}>Retry</button>
  </section>

  const { status } = view
  const copy = COPY[status.state]
  const showKeyForm = status.state === 'APP_KEYS_REQUIRED' || showRotate
  const busy = pending !== null
  return <section className="data-connection">
    <header className="data-connection__header">
      <div>
        <span className="data-connection__eyebrow">Account / Data provider</span>
        <h1 ref={heading} tabIndex={-1}>Zerodha data connection</h1>
        <p>Store your Zerodha app keys securely and reconnect this browser session. Provider readiness stays closed.</p>
      </div>
      <Link to="/account">Back to account</Link>
    </header>

    <div className="data-connection__notice" role="status" aria-atomic="true">
      <div><strong>{copy.title}</strong><p>{copy.detail}</p></div>
    </div>

    <div className="data-connection__grid">
      <section className="data-connection__ledger" aria-labelledby="provider-truth-title">
        <div className="data-connection__section-head">
          <h2 id="provider-truth-title">Connection details</h2>
        </div>
        <dl>
          <div><dt>Provider</dt><dd>Zerodha</dd></div>
          <div><dt>Role</dt><dd>Market data only</dd></div>
          <div><dt>Readiness</dt><dd>Not ready</dd></div>
          <div><dt>Credential expiry</dt><dd>Unverified</dd></div>
          <div><dt>Rate quota</dt><dd>Unverified</dd></div>
        </dl>
      </section>

      <section className="data-connection__actions" aria-labelledby="provider-actions-title">
        <div className="data-connection__section-head">
          <h2 id="provider-actions-title">Available action</h2>
        </div>
        {status.actions.create && <div className="data-connection__action-block">
          <h3>Create the local record</h3><p>This creates one owner-scoped data connection with no credential.</p>
          <button disabled={busy} onClick={() => void mutate('create', client.create)}>
            {pending === 'create' ? 'Creating…' : 'Create connection'}
          </button>
        </div>}

        {showKeyForm && <form className="data-connection__key-form" onSubmit={(event) => submitKeys(event, showRotate)}>
          <h3>{showRotate ? 'Rotate application keys' : 'Add application keys'}</h3>
          <p>{showRotate
            ? 'Rotation removes the stored session token. Reconnect after saving.'
            : 'The values go to the encrypted server vault and are never shown again.'}</p>
          {formError && <div ref={errorSummary} className="data-connection__form-error" role="alert" tabIndex={-1}>{formError}</div>}
          <label htmlFor="provider-api-key">Application key</label>
          <input id="provider-api-key" type="password" autoComplete="off" spellCheck={false}
            value={apiKey} onChange={(event) => setApiKey(event.target.value)}
            aria-invalid={Boolean(formError)} />
          <label htmlFor="provider-api-secret">Application secret</label>
          <input id="provider-api-secret" type="password" autoComplete="off" spellCheck={false}
            value={apiSecret} onChange={(event) => setApiSecret(event.target.value)}
            aria-invalid={Boolean(formError)} />
          <div className="data-connection__button-row">
            <button disabled={busy} type="submit">{pending === (showRotate ? 'rotate' : 'keys') ? 'Saving…' : showRotate ? 'Rotate keys' : 'Save keys'}</button>
            {showRotate && <button type="button" disabled={busy} onClick={() => { clearSecrets(); setShowRotate(false); setFormError('') }}>Cancel</button>}
          </div>
        </form>}

        {status.actions.reauthenticate && !showRotate && <div className="data-connection__action-block">
          <h3>Reconnect</h3><p>Sign in with Zerodha for this browser. Provider access and live data readiness remain unverified.</p>
          <div className="data-connection__button-row">
            <button disabled={busy} onClick={() => void reconnect()}>{pending === 'reauthenticate' ? 'Starting…' : 'Reconnect'}</button>
            {status.actions.rotate_app_keys && <button disabled={busy} onClick={() => setShowRotate(true)}>Rotate keys</button>}
          </div>
        </div>}

        {status.actions.revoke && <DisconnectProvider busy={busy} pending={pending} confirmed={confirmRevoke}
          onAsk={() => setConfirmRevoke(true)} onConfirm={() => void mutate('revoke', client.revoke)} onCancel={() => setConfirmRevoke(false)} />}

        {status.state === 'UNAVAILABLE' && <div className="data-connection__action-block">
          <h3>Restore server truth</h3><p>Mutations stay closed while the state is unavailable.</p>
          <button disabled={busy} onClick={() => void load()}>Retry status</button>
        </div>}
        <p className="data-connection__action-message" role="status" aria-atomic="true">{actionMessage}</p>
      </section>
    </div>
    <InstrumentSearch client={client} status={status} busy={busy} />
  </section>
}
