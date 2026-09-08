import { canonicalJson, contentAddress } from '../../shell/contentAddress'

export const DATA_CONNECTION_REQUEST_BODY_LIMIT = 4_096
export const DATA_CONNECTION_RESPONSE_BODY_LIMIT = 65_536

export type DataConnectionState =
  | 'CONNECTION_REQUIRED'
  | 'APP_KEYS_REQUIRED'
  | 'REAUTH_REQUIRED'
  | 'SESSION_PRESENT_UNVERIFIED'
  | 'REVOKED'
  | 'UNAVAILABLE'

export interface DataConnectionStatus {
  readonly schema: 'strategy-os-data-connection-status/1'
  readonly state: DataConnectionState
  readonly provider: 'ZERODHA'
  readonly role: 'DATA'
  readonly ready: false
  readonly credential_expiry: 'UNVERIFIED'
  readonly rate_quota: 'UNVERIFIED'
  readonly actions: Readonly<{
    create: boolean
    write_app_keys: boolean
    rotate_app_keys: boolean
    reauthenticate: boolean
    revoke: boolean
  }>
}

export interface DataConnectionRequestDescriptor {
  readonly method: 'GET' | 'POST' | 'DELETE'
  readonly path: `/api/v1/data-connections${string}`
  readonly signal: AbortSignal
  readonly credentials: 'same-origin'
  readonly cache: 'no-store'
  readonly redirect: 'error'
  readonly csrfRequired: boolean
  readonly headers: Readonly<Record<string, string>>
  readonly body?: string
  readonly requestBodyLimitBytes: 4096
  readonly responseBodyLimitBytes: 65536
}

export interface DataConnectionTransportResponse {
  readonly status: number
  readonly headers: { readonly contentType: string; readonly cacheControl: string }
  readonly body: unknown
}

export type DataConnectionTransport = (
  descriptor: DataConnectionRequestDescriptor,
) => Promise<DataConnectionTransportResponse>

export interface DataConnectionClient {
  status(signal: AbortSignal): Promise<DataConnectionStatus>
  create(signal: AbortSignal): Promise<DataConnectionStatus>
  storeAppKeys(keys: Readonly<{ api_key: string; api_secret: string }>, signal: AbortSignal): Promise<DataConnectionStatus>
  rotateAppKeys(keys: Readonly<{ api_key: string; api_secret: string }>, signal: AbortSignal): Promise<DataConnectionStatus>
  initiate(signal: AbortSignal): Promise<{ readonly login_url: string }>
  revoke(signal: AbortSignal): Promise<DataConnectionStatus>
  searchInstruments(query: string, exchange: ProviderExchange, signal: AbortSignal): Promise<ProviderInstrumentSearchResult>
  resolveInstrument(selection: ProviderResearchReference, signal: AbortSignal): Promise<ProviderInstrumentSelection>
  selectInstrument(reference: ProviderInstrumentReference, signal: AbortSignal): Promise<SavedProviderSelection>
}

export type ProviderExchange = string
export interface ProviderInstrumentReference {
  readonly token: number
  readonly symbol: string
  readonly name: string
  readonly exchange: string
  readonly segment: string
  readonly instrument_type: string
  readonly expiry: string | null
  readonly strike: string | null
  readonly lot_size: string | null
  readonly tick_size: string | null
}
/** Optional research resolver input; never the watchlist selection contract. */
export interface ProviderResearchReference {
  readonly token: number
  readonly symbol: string
  readonly name: string
  readonly exchange: string
  readonly kind: 'INDEX' | 'EQUITY'
}
export interface ProviderInstrumentSearchResult {
  readonly schema: 'strategy-os-provider-instrument-search/2'
  readonly provider: 'ZERODHA'
  readonly reference_type: 'CURRENT_PROVIDER_REFERENCE'
  readonly query: string
  readonly exchange: string
  readonly available_exchanges: readonly string[]
  readonly has_more: boolean
  readonly items: readonly ProviderInstrumentReference[]
}
export interface SavedProviderSelection {
  readonly schema: 'strategy-os-provider-selection/1'
  readonly selection_address: string
  readonly selection: Readonly<{
    schema: 'owner-provider-instrument-selection/1'; owner_id: string; data_account_id: string
    connection_id: number; provider: 'ZERODHA'; reference: ProviderInstrumentReference; observed_at: string
  }>
  readonly research_resolution: 'UNRESOLVED'
}

export interface ProviderInstrumentSelection {
  readonly instrument_address: string
  readonly display_name: string
  readonly historical_mapping: 'UNVERIFIED'
}

const SEARCH_FAILURE_CODES = ['INVALID_PROVIDER_REFERENCE', 'INSTRUMENT_SELECTION_UNAVAILABLE', 'INVALID_INSTRUMENT_SEARCH', 'DATA_REAUTH_REQUIRED', 'DATA_PROVIDER_BUSY',
  'DATA_VAULT_UNAVAILABLE', 'INSTRUMENT_SEARCH_UNAVAILABLE', 'DATA_CONNECTION_UNAVAILABLE'] as const
type SearchFailureCode = typeof SEARCH_FAILURE_CODES[number]

export class DataConnectionContractError extends Error {
  constructor() { super('Provider connection response could not be verified.'); this.name = 'DataConnectionContractError' }
}

export class DataConnectionRequestError extends Error {
  readonly status: number
  readonly code: SearchFailureCode | null
  constructor(status: number, code: SearchFailureCode | null = null) {
    super('Provider connection request was not accepted.')
    this.name = 'DataConnectionRequestError'
    this.status = status
    this.code = code
  }
}

function contract(condition: boolean): asserts condition {
  if (!condition) throw new DataConnectionContractError()
}

function exactObject(value: unknown, keys: readonly string[]): Record<string, unknown> {
  contract(value !== null && typeof value === 'object' && Object.getPrototypeOf(value) === Object.prototype)
  const object = value as Record<string, unknown>
  const ownKeys = Reflect.ownKeys(object)
  contract(ownKeys.length === keys.length)
  contract(ownKeys.every((key) => typeof key === 'string' && keys.includes(key)))
  contract(keys.every((key) => Object.prototype.hasOwnProperty.call(object, key)))
  return object
}

function searchFailureCode(value: unknown): SearchFailureCode | null {
  try {
    const body = exactObject(value, ['detail'])
    const detail = exactObject(body.detail, ['code', 'message'])
    return SEARCH_FAILURE_CODES.includes(detail.code as SearchFailureCode) ? detail.code as SearchFailureCode : null
  } catch { return null }
}

function instrumentText(value: unknown, maximum: number, empty = false): value is string {
  return typeof value === 'string' && value.length >= Number(!empty) && value.length <= maximum
    && /^[A-Za-z0-9 .&()'/_+%-]*$/.test(value)
}

function parseResearchReference(value: unknown, exchange: string): ProviderResearchReference {
  const item = exactObject(value, ['token', 'symbol', 'name', 'exchange', 'kind'])
  contract(typeof item.token === 'number' && Number.isInteger(item.token) && item.token > 0 && item.token <= 4_294_967_295)
  contract(instrumentText(item.symbol, 64) && item.symbol.trim() === item.symbol && item.symbol.trim().length > 0)
  contract(instrumentText(item.name, 128, true))
  contract(item.exchange === exchange)
  contract(item.kind === 'INDEX' || item.kind === 'EQUITY')
  return Object.freeze({ token: item.token, symbol: item.symbol, name: item.name, exchange, kind: item.kind })
}

function providerText(value: unknown, maximum: number, empty = false): string {
  contract(typeof value === 'string' && value.length >= Number(!empty) && value.length <= maximum)
  contract(value === value.trim() && value.normalize('NFC') === value && !/[\u0000-\u001f\u007f]/.test(value))
  return value
}
export function validProviderExchange(value: unknown): value is string {
  return typeof value === 'string' && /^[A-Za-z0-9_-]{1,16}$/.test(value)
}
function providerExchange(value: unknown): string {
  contract(validProviderExchange(value))
  return value
}
export function validProviderQuery(value: unknown): value is string {
  if (typeof value !== 'string') return false
  const normalized = value.trim()
  return normalized.length >= 2 && normalized.length <= 64 && normalized.normalize('NFC') === normalized
    && !/[\u0000-\u001f\u007f]/.test(value)
}
function providerDecimal(value: unknown): string | null {
  if (value === null) return null
  contract(typeof value === 'string' && value.length <= 64 && /^(?:0|[1-9]\d*)(?:\.\d*[1-9])?$/.test(value))
  const exponent = decimalExponent(value)
  contract(exponent >= -24 && exponent <= 24)
  return value
}
function decimalExponent(value: string): number {
  const [whole, fraction = ''] = value.split('.')
  if (whole !== '0') return whole.length - 1
  const first = fraction.search(/[1-9]/)
  return first < 0 ? 0 : -first - 1
}
function providerDate(value: unknown): string | null {
  if (value === null) return null
  contract(typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value))
  const date = new Date(`${value}T00:00:00Z`)
  contract(Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === value)
  return value
}
export function providerObservedAt(value: unknown): string {
  contract(typeof value === 'string' && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)$/.test(value))
  const date = new Date(value)
  contract(Number.isFinite(date.getTime()) && date.toISOString().slice(0, 19) === value.slice(0, 19))
  return value
}
export function parseProviderReference(value: unknown): ProviderInstrumentReference {
  const item = exactObject(value, ['token', 'symbol', 'name', 'exchange', 'segment', 'instrument_type', 'expiry', 'strike', 'lot_size', 'tick_size'])
  contract(typeof item.token === 'number' && Number.isInteger(item.token) && item.token > 0 && item.token <= 4_294_967_295)
  return Object.freeze({ token: item.token, symbol: providerText(item.symbol, 64), name: providerText(item.name, 128, true),
    exchange: providerExchange(item.exchange), segment: providerText(item.segment, 32), instrument_type: providerText(item.instrument_type, 32),
    expiry: providerDate(item.expiry), strike: providerDecimal(item.strike), lot_size: providerDecimal(item.lot_size), tick_size: providerDecimal(item.tick_size) })
}
export function providerReferenceLabel(reference: ProviderInstrumentReference): string {
  const terms = [reference.symbol, reference.exchange, reference.segment, reference.instrument_type]
  if (reference.expiry !== null) terms.push(reference.expiry)
  if (reference.strike !== null && reference.strike !== '0') terms.push(reference.strike)
  return terms.join(' · ')
}
export function providerExchangeOptions(available: readonly string[], selected: string): readonly string[] {
  return ['ALL', ...new Set([...available, selected].filter((value) => value !== 'ALL'))]
}
export function parseProviderInstrumentSearch(value: unknown, query: string, exchange: string): ProviderInstrumentSearchResult {
  const body = exactObject(value, ['schema', 'provider', 'reference_type', 'query', 'exchange', 'available_exchanges', 'has_more', 'items'])
  contract(body.schema === 'strategy-os-provider-instrument-search/2' && body.provider === 'ZERODHA')
  contract(body.reference_type === 'CURRENT_PROVIDER_REFERENCE' && body.query === query.trim().toUpperCase() && body.exchange === exchange)
  contract(typeof body.has_more === 'boolean' && Array.isArray(body.items) && body.items.length <= 20)
  contract(Array.isArray(body.available_exchanges) && body.available_exchanges.length <= 128)
  const exchanges = body.available_exchanges.map(providerExchange)
  contract(new Set(exchanges).size === exchanges.length && !exchanges.includes('ALL'))
  const items = body.items.map(parseProviderReference)
  contract(!body.has_more || items.length === 20)
  contract(items.every((item) => exchanges.includes(item.exchange) && (exchange === 'ALL' || item.exchange === exchange)))
  contract(new Set(items.map((item) => canonicalJson(item))).size === items.length)
  return Object.freeze({ schema: 'strategy-os-provider-instrument-search/2', provider: 'ZERODHA', reference_type: 'CURRENT_PROVIDER_REFERENCE',
    query: body.query, exchange, available_exchanges: Object.freeze(exchanges), has_more: body.has_more, items: Object.freeze(items) })
}
export async function parseSavedProviderSelection(value: unknown, expected: ProviderInstrumentReference): Promise<SavedProviderSelection> {
  const body = exactObject(value, ['schema', 'selection_address', 'selection', 'research_resolution'])
  contract(body.schema === 'strategy-os-provider-selection/1' && body.research_resolution === 'UNRESOLVED')
  const record = exactObject(body.selection, ['schema', 'owner_id', 'data_account_id', 'connection_id', 'provider', 'reference', 'observed_at'])
  contract(record.schema === 'owner-provider-instrument-selection/1' && record.provider === 'ZERODHA')
  contract(typeof record.connection_id === 'number' && Number.isSafeInteger(record.connection_id) && record.connection_id > 0)
  const reference = parseProviderReference(record.reference)
  contract(canonicalJson(reference) === canonicalJson(parseProviderReference(expected)))
  const selection = Object.freeze({ schema: 'owner-provider-instrument-selection/1' as const,
    owner_id: providerText(record.owner_id, 64), data_account_id: providerText(record.data_account_id, 64),
    connection_id: record.connection_id, provider: 'ZERODHA' as const, reference, observed_at: providerObservedAt(record.observed_at) })
  const selection_address = canonicalAddress(body.selection_address)
  await verifySelectionDigest(selection_address, selection)
  return Object.freeze({ schema: 'strategy-os-provider-selection/1', selection_address, selection, research_resolution: 'UNRESOLVED' })
}

function canonicalAddress(value: unknown): string {
  contract(typeof value === 'string' && /^sha256:[a-f0-9]{64}$/.test(value))
  return value
}

async function verifySelectionDigest(address: string, value: unknown) {
  try { contract(await contentAddress(value) === address) }
  catch { throw new DataConnectionContractError() }
}

function indexReferenceLabel(document: Record<string, unknown>, definition: Record<string, unknown>, selected: ProviderResearchReference): string {
  contract(document.schema === 'strategy-os-index-definition-reference/1')
  contract(selected.symbol === 'NIFTY 50' && selected.name === 'NIFTY 50')
  const interpretation = exactObject(document.interpretation, ['name', 'currency', 'return_type'])
  contract(instrumentText(interpretation.name, 128) && interpretation.name.trim() === interpretation.name)
  contract(interpretation.currency === definition.currency && interpretation.return_type === 'PRICE_RETURN')
  contract(interpretation.name.toUpperCase() === selected.name)
  return `${interpretation.name} · ${interpretation.currency} · Price return`
}

function equityReferenceLabel(document: Record<string, unknown>, definition: Record<string, unknown>, selected: ProviderResearchReference): string {
  contract(document.schema === 'strategy-os-equity-definition-reference/1')
  const interpretation = exactObject(document.interpretation, ['name', 'symbol', 'isin', 'security_class', 'exchange', 'series', 'currency'])
  contract(instrumentText(interpretation.name, 128) && interpretation.name.trim() === interpretation.name)
  contract(interpretation.symbol === selected.symbol && interpretation.exchange === selected.exchange)
  contract(interpretation.security_class === 'INDIAN_EQUITY' && interpretation.series === 'EQ')
  contract(interpretation.currency === definition.currency)
  contract(typeof interpretation.isin === 'string' && /^[A-Z]{2}[A-Z0-9]{9}[0-9]$/.test(interpretation.isin))
  contract(definition.authority_namespace === `strategy-os:security:isin:${interpretation.isin}`)
  return `${interpretation.name} · ${interpretation.exchange} · Equity · ${interpretation.currency}`
}

async function definitionLabel(value: unknown, instrumentAddress: string, definition: Record<string, unknown>, selected: ProviderResearchReference): Promise<string> {
  const evidence = exactObject(value, ['address', 'document'])
  const evidenceAddress = canonicalAddress(evidence.address)
  const document = exactObject(evidence.document, ['schema', 'representation', 'extraction_method',
    'retrieved_on', 'instrument_address', 'interpretation', 'sources'])
  contract(document.representation === 'TRANSFORMED_REFERENCE' && document.instrument_address === instrumentAddress)
  await verifySelectionDigest(evidenceAddress, document)
  return selected.kind === 'INDEX' ? indexReferenceLabel(document, definition, selected) : equityReferenceLabel(document, definition, selected)
}

function cashDefinition(value: unknown, selected: ProviderResearchReference): Record<string, unknown> {
  const definition = exactObject(value, ['authority_namespace', 'authority_version', 'venue_code',
    'asset_class', 'contract_kind', 'currency', 'economic_underlier_address', 'expiry', 'strike',
    'option_right', 'multiplier', 'series_terms'])
  contract(definition.asset_class === selected.kind && definition.contract_kind === 'SPOT')
  contract(definition.venue_code === 'XNSE' && definition.currency === 'INR' && selected.exchange === 'NSE')
  for (const key of ['authority_namespace', 'authority_version']) {
    const text = definition[key]
    contract(typeof text === 'string' && text.length > 0 && text.length <= 256 && !/[\u0000-\u001f]/.test(text))
  }
  contract(['economic_underlier_address', 'expiry', 'strike', 'option_right', 'multiplier'].every((key) => definition[key] === null))
  contract(Array.isArray(definition.series_terms) && definition.series_terms.length === 0)
  return definition
}

export async function parseProviderInstrumentSelection(value: unknown, expected: ProviderResearchReference): Promise<ProviderInstrumentSelection> {
  const body = exactObject(value, ['schema', 'reference_type', 'instrument', 'definition_evidence', 'selection', 'historical_mapping'])
  contract(body.schema === 'strategy-os-provider-instrument-selection/1' && body.reference_type === 'CURRENT_PROVIDER_REFERENCE')
  contract(body.historical_mapping === 'UNVERIFIED')
  const selected = parseResearchReference(body.selection, expected.exchange)
  contract(['token', 'symbol', 'name', 'kind'].every((key) => selected[key as keyof ProviderResearchReference] === expected[key as keyof ProviderResearchReference]))
  const instrument = exactObject(body.instrument, ['address', 'definition'])
  const instrument_address = canonicalAddress(instrument.address)
  const definition = cashDefinition(instrument.definition, selected)
  await verifySelectionDigest(instrument_address, { schema: 'canonical-instrument/1', fact: definition })
  const display_name = await definitionLabel(body.definition_evidence, instrument_address, definition, selected)
  return Object.freeze({ instrument_address, display_name, historical_mapping: 'UNVERIFIED' })
}

function instrumentSearchPath(query: string, exchange: string): DataConnectionRequestDescriptor['path'] {
  if (!validProviderQuery(query) || !validProviderExchange(exchange)) throw new DataConnectionRequestError(422, 'INVALID_INSTRUMENT_SEARCH')
  const params = new URLSearchParams({ query: query.trim(), exchange, limit: '20' })
  return `/api/v1/data-connections/instruments?${params}`
}

const STATE_ACTIONS: Readonly<Record<DataConnectionState, readonly string[]>> = Object.freeze({
  CONNECTION_REQUIRED: Object.freeze(['create']),
  APP_KEYS_REQUIRED: Object.freeze(['write_app_keys', 'revoke']),
  REAUTH_REQUIRED: Object.freeze(['rotate_app_keys', 'reauthenticate', 'revoke']),
  SESSION_PRESENT_UNVERIFIED: Object.freeze(['rotate_app_keys', 'reauthenticate', 'revoke']),
  REVOKED: Object.freeze(['create']),
  UNAVAILABLE: Object.freeze([]),
})
const ACTION_KEYS = ['create', 'write_app_keys', 'rotate_app_keys', 'reauthenticate', 'revoke'] as const
const STATES = Object.keys(STATE_ACTIONS) as DataConnectionState[]

export function parseDataConnectionStatus(value: unknown): DataConnectionStatus {
  const object = exactObject(value, [
    'schema', 'state', 'provider', 'role', 'ready', 'credential_expiry', 'rate_quota', 'actions',
  ])
  contract(object.schema === 'strategy-os-data-connection-status/1')
  contract(typeof object.state === 'string' && STATES.includes(object.state as DataConnectionState))
  const state = object.state as DataConnectionState
  contract(object.provider === 'ZERODHA' && object.role === 'DATA' && object.ready === false)
  contract(object.credential_expiry === 'UNVERIFIED' && object.rate_quota === 'UNVERIFIED')
  const actions = exactObject(object.actions, ACTION_KEYS)
  const expected = STATE_ACTIONS[state]
  for (const action of ACTION_KEYS) contract(actions[action] === expected.includes(action))
  return Object.freeze({
    schema: 'strategy-os-data-connection-status/1', state, provider: 'ZERODHA', role: 'DATA',
    ready: false, credential_expiry: 'UNVERIFIED', rate_quota: 'UNVERIFIED',
    actions: Object.freeze({
      create: actions.create as boolean,
      write_app_keys: actions.write_app_keys as boolean,
      rotate_app_keys: actions.rotate_app_keys as boolean,
      reauthenticate: actions.reauthenticate as boolean,
      revoke: actions.revoke as boolean,
    }),
  })
}

function parseLogin(value: unknown): { readonly login_url: string } {
  const object = exactObject(value, ['login_url'])
  contract(typeof object.login_url === 'string' && object.login_url.length <= 2048)
  let url: URL
  try { url = new URL(object.login_url) } catch { throw new DataConnectionContractError() }
  contract(['http:', 'https:'].includes(url.protocol) && Boolean(url.hostname) && url.hash === '')
  return Object.freeze({ login_url: object.login_url })
}

function descriptor(
  method: DataConnectionRequestDescriptor['method'],
  path: DataConnectionRequestDescriptor['path'],
  signal: AbortSignal,
  body?: Readonly<Record<string, unknown>>,
): DataConnectionRequestDescriptor {
  const serialized = body === undefined ? undefined : JSON.stringify(body)
  return Object.freeze({
    method, path, signal, credentials: 'same-origin', cache: 'no-store', redirect: 'error',
    csrfRequired: method !== 'GET',
    headers: Object.freeze({
      Accept: 'application/json',
      ...(serialized === undefined ? {} : { 'Content-Type': 'application/json' }),
    }),
    ...(serialized === undefined ? {} : { body: serialized }),
    requestBodyLimitBytes: DATA_CONNECTION_REQUEST_BODY_LIMIT,
    responseBodyLimitBytes: DATA_CONNECTION_RESPONSE_BODY_LIMIT,
  })
}

function accepted(response: DataConnectionTransportResponse): void {
  if (response.status < 200 || response.status >= 300) throw new DataConnectionRequestError(response.status, searchFailureCode(response.body))
  contract(response.headers.contentType.includes('application/json'))
  contract(response.headers.cacheControl.split(',').map((value) => value.trim().toLowerCase()).includes('no-store'))
}

export function createDataConnectionClient(transport: DataConnectionTransport): DataConnectionClient {
  async function mutateStatus(
    method: 'POST' | 'DELETE', path: DataConnectionRequestDescriptor['path'],
    signal: AbortSignal, body?: Readonly<Record<string, string>>,
  ) {
    const response = await transport(descriptor(method, path, signal, body))
    accepted(response)
    return parseDataConnectionStatus(response.body)
  }
  const client: DataConnectionClient = {
    async status(signal) {
      const response = await transport(descriptor('GET', '/api/v1/data-connections/status', signal))
      accepted(response)
      return parseDataConnectionStatus(response.body)
    },
    create: (signal) => mutateStatus('POST', '/api/v1/data-connections', signal, {}),
    storeAppKeys: (keys, signal) => mutateStatus('POST', '/api/v1/data-connections/app-keys', signal, keys),
    rotateAppKeys: (keys, signal) => mutateStatus('POST', '/api/v1/data-connections/app-keys/rotate', signal, keys),
    async initiate(signal) {
      const response = await transport(descriptor('POST', '/api/v1/data-connections/oauth/initiate', signal, {}))
      accepted(response)
      return parseLogin(response.body)
    },
    revoke: (signal) => mutateStatus('DELETE', '/api/v1/data-connections', signal),
    async selectInstrument(reference, signal) {
      const selected = parseProviderReference(reference)
      const response = await transport(descriptor('POST', '/api/v1/data-connections/instrument-selections', signal, { reference: selected }))
      accepted(response)
      const result = await parseSavedProviderSelection(response.body, selected)
      signal.throwIfAborted()
      return result
    },
    async resolveInstrument(selection, signal) {
      contract(['NSE', 'BSE'].includes(selection.exchange))
      const item = parseResearchReference(selection, selection.exchange)
      const response = await transport(descriptor('POST', '/api/v1/data-connections/instruments/resolve', signal,
        { token: item.token, symbol: item.symbol, exchange: item.exchange }))
      accepted(response)
      const resolved = await parseProviderInstrumentSelection(response.body, item)
      signal.throwIfAborted()
      return resolved
    },
    async searchInstruments(query, exchange, signal) {
      const response = await transport(descriptor('GET', instrumentSearchPath(query, exchange), signal))
      accepted(response)
      return parseProviderInstrumentSearch(response.body, query, exchange)
    },
  }
  return Object.freeze(client)
}
