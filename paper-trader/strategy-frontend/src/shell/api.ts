import { watchlistMonitoringPath, watchlistCommandBody, parseWatchlistMonitoringRows, parseWatchlistMonitoringRow } from '../features/static-scopes/watchlistMonitorClient'
import type { WatchlistMonitorContext, WatchlistStrategySelection } from '../features/static-scopes/watchlistMonitorTypes'
import type { ScopeMember } from '../features/static-scopes/staticScopeContracts'
import { validProviderExchange, validProviderQuery } from '../features/connections/dataConnectionClient'
import { alertsEnabled, attentionBody, monitoringAlertPath, monitoringListPath, parseMonitoringPage, verifyMonitoringDetail, parseAttentionMutation, parseOwnReview, parseReviewMutation, reviewBody, type MonitoringAlert } from '../features/alerts/monitoringContracts'
import type { AttentionAction, SignalReviewDraft } from '../features/alerts/viewModels'
import { parseAccountRiskSettings, parseAccountRiskSave, validateAccountRiskUpdate, type AccountRiskKey } from '../research/accountRiskContracts'
import { parseStaticScope, parseStaticScopePage, type ScopeDraft } from '../features/static-scopes/staticScopeContracts'
import { parsePaperPortfolio } from '../features/portfolio/portfolioContracts'
import { assertResearchSettingsSave, parseWorkspaceResearchSettings, parseStrategyResearchSettings, parseResearchSettingsRevision, type ResearchValues } from './contracts'
import { operationId, parsePreparationReceipt, parsePreparedOperation, parseResearchRecovery, parseRecoveryCancellation, type InputSettingsPreparation, type SettingsPreparation, type SavedResearchContext, type ResearchPreparation, type ResearchSelection } from '../research/preparedResearchContracts'
import { parsePresets, parsePresetCopy } from '../features/presets/presetContracts'
import { ContractError, parseApiErrorEnvelope, parseBrowserSession, parseCatalogue, parseComparison,
  parseEditor, parseEditorValidation, parseExperimentDetail, parseGraphPage, parseManifest,
  staticScopesEnabled, parseProjectPage, parseProjects, parsePublishedGraph, parseResearchRunPage, parseReview, parseVersions, strategiesEnabled,
  parseResearchDatasetPage, parseResearchVisualization, parseMarketContext, assertProviderHistoryRequest, parseProviderHistoryReceipt,
  parseChartAnnotation, parseChartAnnotationPage, parseV2Draft, parseV2Presentation,
  parseV2PresentationReceipt, parseV2PublishReceipt, parseV2SemanticReceipt,
  type ApiErrorEnvelope, type ExperimentRun, type Project, type ReleaseManifest, type ResearchDataset, type ProviderHistoryRequest,
  type ChartAnnotation, type MarketContext, type V2PresentationReceipt, type V2SemanticReceipt } from './contracts'
import type {
  AccountCommerceRequestDescriptor,
  AccountCommerceTransport,
  AccountCommerceTransportResponse,
} from '../features/account/accountCommerceClient'
import type {
  DataConnectionRequestDescriptor,
  DataConnectionTransport,
  DataConnectionTransportResponse,
} from '../features/connections/dataConnectionClient'
import { dailyCsvFilesError, parseDailyCsvImport, parseDailyCsvInspection,
  type DailyCsvMetadata } from '../features/data/dailyCsvContracts'

export type RestMethod = 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'
type JsonBody = Readonly<Record<string, unknown>>
const MAX_REQUEST_BODY_BYTES = 64 * 1024
const MAX_V2_RECEIPT_BODY_BYTES = 1_100_000
const MAX_ERROR_BODY_BYTES = 64 * 1024

function isProviderInstrumentSearch(method: string, path: string): boolean {
  const prefix = '/api/v1/data-connections/instruments?'
  if (method !== 'GET' || !path.startsWith(prefix) || path.includes('#')) return false
  const params = new URLSearchParams(path.slice(prefix.length))
  const keys = [...params.keys()].sort()
  if (keys.join(',') !== 'exchange,limit,query') return false
  return validProviderQuery(params.get('query')) && validProviderExchange(params.get('exchange'))
    && /^(?:[1-9]|[1-4][0-9]|50)$/.test(params.get('limit')!)
}

const DATA_CONNECTION_PATHS = new Set([
  '/api/v1/data-connections/status', '/api/v1/data-connections',
  '/api/v1/data-connections/app-keys', '/api/v1/data-connections/app-keys/rotate',
  '/api/v1/data-connections/oauth/initiate',
])

function validDataConnectionShape(descriptor: DataConnectionRequestDescriptor): boolean {
  const keys = Reflect.ownKeys(descriptor)
  const expected = ['method', 'path', 'signal', 'credentials', 'cache', 'redirect',
    'csrfRequired', 'headers', 'requestBodyLimitBytes', 'responseBodyLimitBytes']
  if (descriptor.method === 'POST') expected.push('body')
  return keys.length === expected.length && expected.every((key) => keys.includes(key))
    && ['GET', 'POST', 'DELETE'].includes(descriptor.method)
    && (DATA_CONNECTION_PATHS.has(descriptor.path)
      || isProviderInstrumentSearch(descriptor.method, descriptor.path)
      || (descriptor.method === 'POST' && ['/api/v1/data-connections/instruments/resolve', '/api/v1/data-connections/instrument-selections'].includes(descriptor.path)))
    && descriptor.signal instanceof AbortSignal
}

function validDataConnectionPolicy(descriptor: DataConnectionRequestDescriptor): boolean {
  return descriptor.credentials === 'same-origin' && descriptor.cache === 'no-store'
    && descriptor.redirect === 'error' && descriptor.requestBodyLimitBytes === 4096
    && descriptor.responseBodyLimitBytes === 65536
    && descriptor.csrfRequired === (descriptor.method !== 'GET')
    && Object.getPrototypeOf(descriptor.headers) === Object.prototype
}

function validDataConnectionHeaders(descriptor: DataConnectionRequestDescriptor): boolean {
  const hasBody = descriptor.method === 'POST'
  const required = hasBody ? ['Accept', 'Content-Type'] : ['Accept']
  const keys = Object.keys(descriptor.headers)
  return keys.length === required.length && required.every((key) => keys.includes(key))
    && descriptor.headers.Accept === 'application/json'
    && (!hasBody || descriptor.headers['Content-Type'] === 'application/json')
}

function validDataConnectionBody(descriptor: DataConnectionRequestDescriptor): boolean {
  if (descriptor.method !== 'POST') return descriptor.body === undefined
  return typeof descriptor.body === 'string'
    && new TextEncoder().encode(descriptor.body).byteLength <= 4096
}

export class ApiError extends Error {
  readonly kind: 'access' | 'input' | 'network' | 'timeout' | 'server' | 'manifest'
  readonly envelope: ApiErrorEnvelope | null
  constructor(kind: ApiError['kind'], message: string, envelope: ApiErrorEnvelope | null = null) {
    super(message); this.name = 'ApiError'; this.kind = kind; this.envelope = envelope
  }
}

/** The sole REST transport. Same-origin routing and authentication belong to the server. */
function validateMonitoringRequest(method: 'GET' | 'POST', path: string, body?: JsonBody) {
    const list = /^monitoring\/alerts\?limit=100(?:&unread_only=true)?(?:&cursor=[A-Za-z0-9_.-]{1,2048})?$/
    const detail = /^monitoring\/assignments\/[A-Za-z0-9](?:[A-Za-z0-9._-]|%3A){0,127}\/alerts\/sha256%3A[0-9a-f]{64}(?:\/(?:attention|review))?$/
    const allowed = method === 'GET' ? list.test(path) || (detail.test(path) && !path.endsWith('/attention')) : detail.test(path) && /\/(?:attention|review)$/.test(path)
    if (!allowed || (method === 'GET' && body !== undefined)) throw new ApiError('input', 'The monitoring request is invalid.')
}

async function readMonitoringResponse(response: Response) {
      if (!response.headers.get('content-type')?.includes('application/json')) throw new ContractError()
      const length = response.headers.get('content-length')
      if (length !== null && (!/^\d+$/.test(length) || Number(length) > 524288)) throw new ContractError()
      const text = await response.text(); if (new TextEncoder().encode(text).length > 524288) throw new ContractError()
      return JSON.parse(text) as unknown
}

function validateRestRequest(method: RestMethod, path: string, body: JsonBody | undefined) {
  if (!/^[A-Za-z0-9][A-Za-z0-9._~!$&'()*+,;=:@%/?-]*$/.test(path) || path.length > 2048 || path.includes('..')) {
    throw new ApiError('input', 'The request path is invalid.')
  }
  if (method === 'GET' && body !== undefined) throw new ApiError('input', 'GET requests cannot include a body.')
}

function serializeRestBody(body: JsonBody | undefined, maximum: number) {
  if (body === undefined) return undefined
  if (body === null || Array.isArray(body) || Object.getPrototypeOf(body) !== Object.prototype) {
    throw new ApiError('input', 'The request body is invalid.')
  }
  let serialized: string
  try { serialized = JSON.stringify(body) } catch { throw new ApiError('input', 'The request body is invalid.') }
  if (new TextEncoder().encode(serialized).byteLength > maximum) throw new ApiError('input', 'The request body is too large.')
  return serialized
}

async function readRestErrorEnvelope(response: Response) {
  if (response.ok || !response.headers.get('content-type')?.includes('application/json')) return null
  const declared = Number(response.headers.get('content-length'))
  if (Number.isFinite(declared) && declared > MAX_ERROR_BODY_BYTES) return null
  try {
    const text = await response.text()
    return new TextEncoder().encode(text).byteLength <= MAX_ERROR_BODY_BYTES ? parseApiErrorEnvelope(JSON.parse(text)) : null
  } catch { return null }
}

function restAccessError(status: number, authRequest: boolean, envelope: ApiErrorEnvelope | null) {
  if (authRequest && (status === 403 || status === 422)) {
    return new ApiError('input', 'This account action could not be completed. Check the supplied details and try again.', envelope)
  }
  if (status === 401 || status === 403) return new ApiError('access', authRequest
    ? 'Sign-in or session verification failed. Check your details and try again.'
    : 'Your session no longer has access. Sign in again or check your workspace membership.', envelope)
  return null
}

function restResponseError(method: RestMethod, response: Response, authRequest: boolean, envelope: ApiErrorEnvelope | null) {
  const access = restAccessError(response.status, authRequest, envelope)
  if (access) return access
  if (response.status === 429 || response.status === 503) return new ApiError('server', 'Authentication or service capacity is temporarily unavailable. Wait a minute and retry.', envelope)
  if (!response.ok) return new ApiError('server', method === 'GET'
    ? 'The server could not load this information. Retry when it is available.' : 'The server could not complete this request.', envelope)
  return null
}

export class StrategyApi {
  private manifest: ReleaseManifest | null = null
  private generation = 0
  private csrf: string | null = null
  private readonly requests = new Set<AbortController>()
  private readonly listeners = new Set<(error: ApiError | null) => void>()

  onAccessInvalidated(listener: (error: ApiError | null) => void) {
    this.listeners.add(listener)
    return () => { this.listeners.delete(listener) }
  }

  private advanceGeneration() {
    this.manifest = null
    this.csrf = null
    this.generation += 1
    for (const request of this.requests) request.abort()
    this.requests.clear()
    return this.generation
  }

  /** Explicit user recheck. No timer or claim of detecting server revocation. */
  recheck() {
    this.advanceGeneration()
    for (const listener of this.listeners) listener(null)
  }

  private assertCurrent(generation: number, signal: AbortSignal) {
    if (signal.aborted || generation !== this.generation) throw new DOMException('Request cancelled', 'AbortError')
  }

  private async send<T>(method: RestMethod, path: string, signal: AbortSignal,
    requestBody: BodyInit | undefined, csrfRequired: boolean,
    consume: (response: Response) => Promise<T>, timeoutMs = 10000): Promise<T> {
    const generation = this.generation
    const controller = new AbortController()
    this.requests.add(controller)
    const abort = () => controller.abort()
    signal.addEventListener('abort', abort, { once: true })
    let timedOut = false
    const timer = setTimeout(() => { timedOut = true; controller.abort() }, timeoutMs)
    try {
      if (signal.aborted) controller.abort()
      const response = await fetch(`/api/v1/${path}`, {
        method,
        headers: {
          Accept: 'application/json',
          ...(typeof requestBody === 'string' ? { 'Content-Type': 'application/json' } : {}),
          ...(csrfRequired && this.csrf ? { 'X-Strategy-CSRF': this.csrf } : {}),
        },
        credentials: 'same-origin',
        ...(requestBody !== undefined ? { body: requestBody } : {}),
        cache: 'no-store', redirect: 'error', signal: controller.signal,
      })
      this.assertCurrent(generation, signal)
      const value = await consume(response)
      this.assertCurrent(generation, signal)
      return value
    } catch (error) {
      if (error instanceof ApiError && error.kind === 'access') throw error
      this.assertCurrent(generation, signal)
      if (timedOut) throw new ApiError('timeout', 'The server did not respond in time. Try again.')
      if (error instanceof ApiError || error instanceof ContractError) throw error
      if (error instanceof SyntaxError) throw new ContractError()
      throw new ApiError('network', 'The server could not be reached. Check the connection and retry.')
    } finally {
      this.requests.delete(controller)
      clearTimeout(timer)
      signal.removeEventListener('abort', abort)
    }
  }

  protected async request(method: RestMethod, path: string, signal: AbortSignal, body?: JsonBody, authRequest = false, maxBodyBytes = MAX_REQUEST_BODY_BYTES, timeoutMs = 10000): Promise<unknown> {
    validateRestRequest(method, path, body)
    const serializedBody = serializeRestBody(body, maxBodyBytes)
    const requestGeneration = this.generation
    return this.send(method, path, signal, serializedBody, method !== 'GET', async (response) => {
      const envelope = await readRestErrorEnvelope(response)
      this.assertCurrent(requestGeneration, signal)
      const error = restResponseError(method, response, authRequest, envelope)
      if (error) {
        if (error.kind === 'access' && !authRequest) {
          this.advanceGeneration()
          for (const listener of this.listeners) listener(error)
        }
        throw error
      }
      if (!response.headers.get('content-type')?.includes('application/json')) throw new ContractError()
      return response.json() as Promise<unknown>
    }, timeoutMs)
  }

  private async dailyCsvRequest(projectId: string, action: 'inspect-csv' | 'import-csv',
    file: File, metadata: DailyCsvMetadata, signal: AbortSignal, sessionMetadata?: File): Promise<unknown> {
    if (!this.csrf) throw new ApiError('access', 'Verify your session before importing research data.')
    const filesError = dailyCsvFilesError(file, sessionMetadata)
    if (filesError) throw new ApiError('input', filesError)
    const serialized = JSON.stringify(metadata)
    if (new TextEncoder().encode(serialized).byteLength > 8192) throw new ApiError('input', 'The CSV mapping is too large.')
    const form = new FormData(); form.append('file', file); form.append('metadata', serialized)
    if (sessionMetadata) form.append('session_metadata', sessionMetadata)
    const path = `ir/projects/${encodeURIComponent(projectId)}/research-datasets/${action}`
    return this.send('POST', path, signal, form, true, async (response) => {
      const declared = Number(response.headers.get('content-length'))
      if (Number.isFinite(declared) && declared > MAX_ERROR_BODY_BYTES) throw new ContractError()
      if (!response.headers.get('content-type')?.includes('application/json')) throw new ContractError()
      const text = await response.text()
      if (new TextEncoder().encode(text).byteLength > MAX_ERROR_BODY_BYTES) throw new ContractError()
      let value: unknown
      try { value = JSON.parse(text) } catch { throw new ContractError() }
      const envelope = response.ok ? null : parseApiErrorEnvelope(value)
      if (response.status === 401 || response.status === 403) {
        const error = new ApiError('access', 'Your session no longer has access. Sign in again or check your workspace membership.', envelope)
        this.advanceGeneration(); for (const listener of this.listeners) listener(error)
        throw error
      }
      if (response.status === 404) throw new ApiError('access', 'This project is not available. Choose a project you can access.', envelope)
      if (response.status === 413) throw new ApiError('input', 'Choose a CSV no larger than 1 MiB.', envelope)
      if (response.status === 422) throw new ApiError('input', 'The CSV or its mapping was not accepted. Check the named columns and date format.', envelope)
      if (!response.ok) throw new ApiError('server', 'The server could not complete this request.', envelope)
      return value
    // The bounded synchronous import publishes attributable observation rows.
    // Its acknowledgement can exceed the ordinary read/inspection deadline.
    }, action === 'import-csv' ? 120000 : 10000)
  }

  readonly accountCommerceTransport: AccountCommerceTransport = async (
    descriptor: AccountCommerceRequestDescriptor,
  ): Promise<AccountCommerceTransportResponse> => {
    const keys = Reflect.ownKeys(descriptor)
    const expected = descriptor.method === 'POST'
      ? ['method', 'path', 'signal', 'credentials', 'cache', 'redirect', 'csrfRequired',
        'headers', 'body', 'requestBodyLimitBytes', 'responseBodyLimitBytes']
      : ['method', 'path', 'signal', 'credentials', 'cache', 'redirect', 'csrfRequired',
        'headers', 'requestBodyLimitBytes', 'responseBodyLimitBytes']
    if (keys.length !== expected.length || !expected.every((key) => keys.includes(key))
      || !['GET', 'POST'].includes(descriptor.method)
      || !descriptor.path.startsWith('/api/v1/account-commerce/')
      || descriptor.path.slice('/api/v1/'.length).includes('..')
      || descriptor.credentials !== 'same-origin' || descriptor.cache !== 'no-store'
      || descriptor.redirect !== 'error' || descriptor.requestBodyLimitBytes !== 4096
      || descriptor.responseBodyLimitBytes !== 65536
      || descriptor.csrfRequired !== (descriptor.method === 'POST')
      || !(descriptor.signal instanceof AbortSignal)
      || Object.getPrototypeOf(descriptor.headers) !== Object.prototype) {
      throw new ApiError('input', 'The account request descriptor is invalid.')
    }
    const headerKeys = Object.keys(descriptor.headers)
    const requiredHeaders = descriptor.method === 'POST'
      ? ['Accept', 'Content-Type'] : ['Accept']
    if (headerKeys.length !== requiredHeaders.length
      || !requiredHeaders.every((key) => headerKeys.includes(key))
      || descriptor.headers.Accept !== 'application/json'
      || (descriptor.method === 'POST'
        && descriptor.headers['Content-Type'] !== 'application/json')
      || (descriptor.method === 'GET' && descriptor.body !== undefined)
      || (descriptor.method === 'POST' && typeof descriptor.body !== 'string')
      || (descriptor.body !== undefined
        && new TextEncoder().encode(descriptor.body).byteLength > 4096)) {
      throw new ApiError('input', 'The account request descriptor is invalid.')
    }
    const path = descriptor.path.slice('/api/v1/'.length)
    const captured = await this.send(
      descriptor.method, path, descriptor.signal, descriptor.body,
      descriptor.csrfRequired, async (response) => {
        const declared = response.headers.get('content-length')
        if (declared !== null && (!/^\d+$/.test(declared) || Number(declared) > 65536)) {
          throw new ContractError()
        }
        const text = await response.text()
        if (new TextEncoder().encode(text).byteLength > 65536) throw new ContractError()
        let body: unknown
        try { body = JSON.parse(text) } catch { throw new ContractError() }
        return Object.freeze({
          status: response.status,
          headers: Object.freeze({
            contentType: response.headers.get('content-type') ?? '',
            cacheControl: response.headers.get('cache-control') ?? '',
          }),
          body,
        })
      },
    )
    if (captured.status === 401 || captured.status === 403) {
      const error = new ApiError('access', 'Your session no longer has access. Sign in again or check your workspace membership.')
      this.advanceGeneration()
      for (const listener of this.listeners) listener(error)
    }
    return captured
  }

  readonly dataConnectionTransport: DataConnectionTransport = async (
    descriptor: DataConnectionRequestDescriptor,
  ): Promise<DataConnectionTransportResponse> => {
    if (!validDataConnectionShape(descriptor) || !validDataConnectionPolicy(descriptor)
      || !validDataConnectionHeaders(descriptor) || !validDataConnectionBody(descriptor)) {
      throw new ApiError('input', 'The provider request descriptor is invalid.')
    }
    const captured = await this.send(
      descriptor.method, descriptor.path.slice('/api/v1/'.length), descriptor.signal,
      descriptor.body, descriptor.csrfRequired, async (response) => {
        const declared = response.headers.get('content-length')
        if (declared !== null && (!/^\d+$/.test(declared) || Number(declared) > 65536)) {
          throw new ContractError()
        }
        const text = await response.text()
        if (new TextEncoder().encode(text).byteLength > 65536) throw new ContractError()
        let body: unknown
        try { body = JSON.parse(text) } catch { throw new ContractError() }
        return Object.freeze({
          status: response.status,
          headers: Object.freeze({
            contentType: response.headers.get('content-type') ?? '',
            cacheControl: response.headers.get('cache-control') ?? '',
          }),
          body,
        })
      },
    )
    if (captured.status === 401 || captured.status === 403) {
      const error = new ApiError('access', 'Your session no longer has access. Sign in again or check your workspace membership.')
      this.advanceGeneration()
      for (const listener of this.listeners) listener(error)
    }
    return captured
  }

  private async monitoringRequest(method: 'GET' | 'POST', path: string, signal: AbortSignal, body?: JsonBody) {
    validateMonitoringRequest(method, path, body)
    if (!this.manifest || !alertsEnabled(this.manifest)) throw new ApiError('manifest', 'Stored alerts are not available in this release.')
    if (method === 'POST' && !this.csrf) throw new ApiError('input', 'Verify your session before updating an alert.', { code: 'MONITORING_SESSION_REQUIRED', message: 'Verify your session before updating an alert.' })
    const serialized = body === undefined ? undefined : JSON.stringify(body)
    if (serialized && new TextEncoder().encode(serialized).length > 16384) throw new ApiError('input', 'The monitoring request is too large.')
    return this.send(method, path, signal, serialized, method === 'POST', async (response) => {
      if (response.status === 401) {
        const error = new ApiError('access', 'Your session has expired. Sign in again.')
        this.advanceGeneration(); for (const listener of this.listeners) listener(error)
        throw error
      }
      const failures: Record<number, [string, string]> = {
        403: ['MONITORING_FORBIDDEN', 'Your current membership cannot complete this action. Your input is retained.'],
        409: ['MONITORING_CONFLICT', 'The alert or your review changed. Refresh the alert before trying again.'],
        404: ['MONITORING_NOT_FOUND', 'This alert is unavailable in your workspace. Refresh the inbox.'],
        400: ['MONITORING_INVALID', 'The alert action was not accepted. Check the displayed values.'],
      }
      const failure = failures[response.status]
      if (failure) throw new ApiError('input', failure[1], { code: failure[0], message: failure[1] })
      if (!response.ok) throw new ApiError('server', 'The monitoring request could not be completed.')
      return readMonitoringResponse(response)
    })
  }

  async monitoringAlerts(cursor: string | null, unreadOnly: boolean, signal: AbortSignal) {
    if (typeof unreadOnly !== 'boolean') throw new ApiError('input', 'Choose an alert filter.')
    return parseMonitoringPage(await this.monitoringRequest('GET', monitoringListPath(cursor, unreadOnly), signal), unreadOnly)
  }
  async monitoringAlert(expected: MonitoringAlert, signal: AbortSignal) {
    return verifyMonitoringDetail(await this.monitoringRequest('GET', monitoringAlertPath(expected.facts.assignmentId, expected.facts.alertAddress), signal), expected)
  }
  async monitoringOwnReview(alert: MonitoringAlert, signal: AbortSignal) {
    return parseOwnReview(await this.monitoringRequest('GET', `${monitoringAlertPath(alert.facts.assignmentId, alert.facts.alertAddress)}/review`, signal), alert)
  }
  async monitoringAttention(alert: MonitoringAlert, action: AttentionAction, expectedSequence: number, signal: AbortSignal) {
    const value = await this.monitoringRequest('POST', `${monitoringAlertPath(alert.facts.assignmentId, alert.facts.alertAddress)}/attention`, signal, attentionBody(action, expectedSequence))
    return parseAttentionMutation(value, alert, action, expectedSequence)
  }
  async monitoringReview(alert: MonitoringAlert, draft: SignalReviewDraft, signal: AbortSignal) {
    const value = await this.monitoringRequest('POST', `${monitoringAlertPath(alert.facts.assignmentId, alert.facts.alertAddress)}/review`, signal, reviewBody(draft))
    return parseReviewMutation(value, alert, draft)
  }

  async bootstrap(signal: AbortSignal): Promise<ReleaseManifest> {
    const generation = this.advanceGeneration()
    const manifest = parseManifest(await this.request('GET', 'release-profile', signal))
    this.assertCurrent(generation, signal)
    this.manifest = manifest
    return manifest
  }

  async session(signal: AbortSignal) {
    const generation = this.generation
    const parsed = parseBrowserSession(await this.request('GET', 'auth/session', signal, undefined, true))
    this.assertCurrent(generation, signal)
    this.csrf = parsed.csrf
    return parsed.identity
  }

  async authenticate(action: 'login' | 'enroll', values: Record<string, string>, signal: AbortSignal) {
    await this.request('POST', `auth/${action}`, signal, values, true)
    return this.session(signal)
  }

  async accountAction(action: 'logout' | 'logout-all' | 'password' | 'organization', values: Record<string, string>, signal: AbortSignal) {
    if (!this.csrf) throw new ApiError('access', 'Verify your session before changing account settings.')
    try {
      await this.request('POST', `auth/${action}`, signal, values, true)
    } catch (error) {
      if (error instanceof ApiError && error.kind === 'access') this.recheck()
      throw error
    }
    this.recheck()
  }

  private requireStrategies() {
    if (!this.manifest || !strategiesEnabled(this.manifest)) {
      throw new ApiError('manifest', 'Strategies are unavailable until the server release is verified.')
    }
  }

  async paperPortfolio(signal: AbortSignal) {
    this.requireStrategies()
    return parsePaperPortfolio(await this.request('GET', 'paper-portfolio', signal))
  }

  async projects(signal: AbortSignal) {
    this.requireStrategies()
    const generation = this.generation
    const collected: Project[] = []
    let after: string | null = null
    for (let pageNumber = 0; pageNumber < 200; pageNumber += 1) {
      const query = new URLSearchParams({ limit: '50' })
      if (after !== null) query.set('after', after)
      const value = await this.request('GET', `ir/projects/research-spine/index?${query}`, signal)
      this.assertCurrent(generation, signal)
      const page = parseProjectPage(value, after, 50)
      collected.push(...page.items)
      if (page.next_cursor === null) return Object.freeze(collected)
      after = page.next_cursor
    }
    throw new ContractError()
  }

  async createProject(name: string, description: string, signal: AbortSignal) {
    this.requireStrategies()
    const generation = this.generation
    const value = await this.request('POST', 'ir/projects', signal, { name, description })
    this.assertCurrent(generation, signal)
    const projects = parseProjects([value])
    return projects[0]
  }

  async graphs(projectId: string, after: string | null, signal: AbortSignal) {
    this.requireStrategies()
    const generation = this.generation
    const query = new URLSearchParams({ limit: '50' })
    if (after !== null) query.set('after', after)
    const value = await this.request('GET', `ir/projects/${encodeURIComponent(projectId)}/graphs?${query}`, signal)
    this.assertCurrent(generation, signal)
    return parseGraphPage(value, projectId, after, 50)
  }


  async createGraph(projectId: string, identifier: string, graph: Readonly<Record<string, unknown>>, signal: AbortSignal) {
    this.requireStrategies()
    const generation = this.generation
    const value = await this.request('POST', `ir/projects/${encodeURIComponent(projectId)}/graphs`, signal, { identifier, graph })
    this.assertCurrent(generation, signal)
    return value
  }

  async presets(signal: AbortSignal) {
    this.requireStrategies()
    const generation = this.generation
    const value = await this.request('GET', 'ir/presets', signal)
    this.assertCurrent(generation, signal)
    return parsePresets(value)
  }

  async copyPreset(projectId: string, presetId: string, identifier: string, name: string, signal: AbortSignal) {
    this.requireStrategies()
    const generation = this.generation
    const value = await this.request('POST', `ir/projects/${encodeURIComponent(projectId)}/presets/${encodeURIComponent(presetId)}/copy`,
      signal, { identifier, ...(name ? { name } : {}) })
    this.assertCurrent(generation, signal)
    return parsePresetCopy(value, projectId, identifier)
  }

  async createV2Graph(projectId: string, identifier: string, name: string, description: string, signal: AbortSignal) {
    this.requireStrategies()
    const generation = this.generation
    const value = await this.request('POST', `ir/projects/${encodeURIComponent(projectId)}/graphs/v2/create`, signal,
      { format_version: 2, identifier, name, description })
    this.assertCurrent(generation, signal)
    return parseV2Draft(value, projectId, identifier)
  }

  async v2Draft(projectId: string, graphId: string, signal: AbortSignal) {
    this.requireStrategies()
    const generation = this.generation
    const value = await this.request('GET', `ir/projects/${encodeURIComponent(projectId)}/graphs/${encodeURIComponent(graphId)}/v2`, signal)
    this.assertCurrent(generation, signal)
    return parseV2Draft(value, projectId, graphId)
  }

  private v2SemanticBody(baseRevision: number, commands: readonly Readonly<Record<string, unknown>>[],
    intent: 'EDIT' | 'UNDO' | 'REDO' | 'REPLAY', sourceReceipt: V2SemanticReceipt | null) {
    return { schema: 'strategy-os-v2-semantic-batch/1', format_version: 2, base_revision: baseRevision, intent,
      use_check: { purpose: 'AUTHORING', capability_receipt_address: null }, source_receipt: sourceReceipt, commands: [...commands] }
  }

  async validateV2(projectId: string, graphId: string, baseRevision: number,
    commands: readonly Readonly<Record<string, unknown>>[], signal: AbortSignal) {
    this.requireStrategies(); const generation = this.generation
    const value = await this.request('POST', `ir/projects/${encodeURIComponent(projectId)}/graphs/${encodeURIComponent(graphId)}/v2/validate`, signal,
      this.v2SemanticBody(baseRevision, commands, 'EDIT', null), false, MAX_V2_RECEIPT_BODY_BYTES)
    this.assertCurrent(generation, signal); return parseV2SemanticReceipt(value)
  }

  async mutateV2(projectId: string, graphId: string, baseRevision: number,
    commands: readonly Readonly<Record<string, unknown>>[], intent: 'EDIT' | 'UNDO' | 'REDO',
    sourceReceipt: V2SemanticReceipt | null, signal: AbortSignal) {
    this.requireStrategies(); const generation = this.generation
    const value = await this.request('POST', `ir/projects/${encodeURIComponent(projectId)}/graphs/${encodeURIComponent(graphId)}/v2/semantic-batches`, signal,
      this.v2SemanticBody(baseRevision, commands, intent, sourceReceipt), false, MAX_V2_RECEIPT_BODY_BYTES)
    this.assertCurrent(generation, signal); return parseV2SemanticReceipt(value)
  }

  async replayV2(projectId: string, graphId: string, baseRevision: number,
    commands: readonly Readonly<Record<string, unknown>>[], sourceReceipt: V2SemanticReceipt, signal: AbortSignal) {
    this.requireStrategies(); const generation = this.generation
    const value = await this.request('POST', `ir/projects/${encodeURIComponent(projectId)}/graphs/${encodeURIComponent(graphId)}/v2/replay`, signal,
      this.v2SemanticBody(baseRevision, commands, 'REPLAY', sourceReceipt), false, MAX_V2_RECEIPT_BODY_BYTES)
    this.assertCurrent(generation, signal); return parseV2SemanticReceipt(value)
  }

  async publishV2(projectId: string, graphId: string, baseRevision: number, expectedCurrentVersion: number | null, signal: AbortSignal, targetRegistrySnapshotAddress?: string) {
    this.requireStrategies(); const generation = this.generation
    if (targetRegistrySnapshotAddress !== undefined && !/^sha256:[0-9a-f]{64}$/.test(targetRegistrySnapshotAddress)) throw new ApiError('input', 'The current component identity is invalid. Reload the component review.')
    const value = await this.request('POST', `ir/projects/${encodeURIComponent(projectId)}/graphs/${encodeURIComponent(graphId)}/v2/publish`, signal,
      { format_version: 2, base_revision: baseRevision, expected_current_version: expectedCurrentVersion,
        ...(targetRegistrySnapshotAddress === undefined ? {} : { target_registry_snapshot_address: targetRegistrySnapshotAddress }) })
    this.assertCurrent(generation, signal); return parseV2PublishReceipt(value, projectId, graphId)
  }

  async v2Version(projectId: string, graphId: string, version: number, signal: AbortSignal) {
    this.requireStrategies(); const generation = this.generation
    const value = await this.request('GET', `ir/projects/${encodeURIComponent(projectId)}/graphs/${encodeURIComponent(graphId)}/v2/versions/${version}`, signal)
    this.assertCurrent(generation, signal); return value
  }

  async v2Presentation(projectId: string, graphId: string, signal: AbortSignal) {
    this.requireStrategies(); const generation = this.generation
    const value = await this.request('GET', `ir/projects/${encodeURIComponent(projectId)}/graphs/${encodeURIComponent(graphId)}/v2/presentation`, signal)
    this.assertCurrent(generation, signal); return parseV2Presentation(value)
  }

  async mutateV2Presentation(projectId: string, graphId: string, semanticRevision: number, presentationRevision: number,
    commands: readonly Readonly<Record<string, unknown>>[], intent: 'EDIT' | 'UNDO' | 'REDO' | 'REPLAY',
    sourceReceipt: V2PresentationReceipt | null, signal: AbortSignal) {
    this.requireStrategies(); const generation = this.generation
    const value = await this.request('POST', `ir/projects/${encodeURIComponent(projectId)}/graphs/${encodeURIComponent(graphId)}/v2/presentation-batches`, signal,
      { schema: 'strategy-os-v2-presentation-batch/1', format_version: 2, base_semantic_revision: semanticRevision,
        base_presentation_revision: presentationRevision, intent, source_receipt: sourceReceipt, commands: [...commands] }, false, MAX_V2_RECEIPT_BODY_BYTES)
    this.assertCurrent(generation, signal); return parseV2PresentationReceipt(value)
  }

  async catalogue(signal: AbortSignal) {
    this.requireStrategies()
    const generation = this.generation
    const value = await this.request('GET', 'ir/catalogue', signal)
    this.assertCurrent(generation, signal)
    return parseCatalogue(value)
  }

  async editor(projectId: string, graphId: string, signal: AbortSignal) {
    this.requireStrategies()
    const generation = this.generation
    const value = await this.request('GET', `ir/projects/${encodeURIComponent(projectId)}/graphs/${encodeURIComponent(graphId)}/editor`, signal)
    this.assertCurrent(generation, signal)
    return parseEditor(value, projectId, graphId)
  }

  async publishGraph(projectId: string, graphId: string, baseRevision: number, signal: AbortSignal) {
    this.requireStrategies()
    const generation = this.generation
    const value = await this.request('POST', `ir/projects/${encodeURIComponent(projectId)}/graphs/${encodeURIComponent(graphId)}/versions`, signal,
      { base_revision: baseRevision })
    this.assertCurrent(generation, signal)
    return parsePublishedGraph(value)
  }

  async editGraph(projectId: string, graphId: string, baseRevision: number, presentationRevision: number,
    edits: readonly Readonly<Record<string, unknown>>[], signal: AbortSignal) {
    this.requireStrategies()
    const generation = this.generation
    const value = await this.request('POST', `ir/projects/${encodeURIComponent(projectId)}/graphs/${encodeURIComponent(graphId)}/edits`, signal,
      { base_revision: baseRevision, base_presentation_revision: presentationRevision, edits: [...edits], presentation_edits: [] })
    this.assertCurrent(generation, signal)
    return parseEditor(value, projectId, graphId)
  }

  async publishEdits(projectId: string, graphId: string, baseRevision: number, presentationRevision: number,
    edits: readonly Readonly<Record<string, unknown>>[], presentationEdits: readonly Readonly<Record<string, unknown>>[], signal: AbortSignal) {
    this.requireStrategies()
    const generation = this.generation
    const value = await this.request('POST', `ir/projects/${encodeURIComponent(projectId)}/graphs/${encodeURIComponent(graphId)}/edits`, signal,
      { base_revision: baseRevision, base_presentation_revision: presentationRevision, edits: [...edits], presentation_edits: [...presentationEdits] })
    this.assertCurrent(generation, signal)
    return parseEditor(value, projectId, graphId)
  }

  async validateEdits(projectId: string, graphId: string, baseRevision: number, presentationRevision: number,
    edits: readonly Readonly<Record<string, unknown>>[], presentationEdits: readonly Readonly<Record<string, unknown>>[], signal: AbortSignal) {
    this.requireStrategies()
    const generation = this.generation
    const value = await this.request('POST', `ir/projects/${encodeURIComponent(projectId)}/graphs/${encodeURIComponent(graphId)}/edits/validate`, signal,
      { base_revision: baseRevision, base_presentation_revision: presentationRevision, edits: [...edits], presentation_edits: [...presentationEdits] })
    this.assertCurrent(generation, signal)
    return parseEditorValidation(value)
  }

  async presentationEdits(projectId: string, graphId: string, baseRevision: number, presentationRevision: number,
    edits: readonly Readonly<Record<string, unknown>>[], signal: AbortSignal) {
    this.requireStrategies()
    const generation = this.generation
    const value = await this.request('POST', `ir/projects/${encodeURIComponent(projectId)}/graphs/${encodeURIComponent(graphId)}/presentation-edits`, signal,
      { base_revision: baseRevision, base_presentation_revision: presentationRevision, edits: [...edits] })
    this.assertCurrent(generation, signal)
    return parseEditor(value, projectId, graphId)
  }

  async versions(projectId: string, graphId: string, signal: AbortSignal) {
    this.requireStrategies()
    const generation = this.generation
    const value = await this.request('GET', `ir/projects/${encodeURIComponent(projectId)}/graphs/${encodeURIComponent(graphId)}/versions`, signal)
    this.assertCurrent(generation, signal)
    return parseVersions(value)
  }

  async experiments(projectId: string, signal: AbortSignal) {
    this.requireStrategies()
    const generation = this.generation
    const runs: ExperimentRun[] = []
    let before: number | null = null
    for (let pageNumber = 0; pageNumber < 400; pageNumber += 1) {
      const query = new URLSearchParams({ limit: '25' })
      if (before !== null) query.set('before', String(before))
      const value = await this.request('GET', `ir/projects/${encodeURIComponent(projectId)}/research-spine/experiments?${query}`, signal)
      this.assertCurrent(generation, signal)
      const page = parseResearchRunPage(value, projectId, 25)
      runs.push(...page.runs)
      if (page.next_cursor === null) return Object.freeze({ runs: Object.freeze(runs) })
      before = page.next_cursor
    }
    throw new ContractError()
  }

  private requireStaticScopes() {
    this.requireStrategies()
    if (!this.manifest || !staticScopesEnabled(this.manifest)) throw new ApiError('manifest', 'Static watchlists are not enabled by this server.')
  }

  async watchlistMonitoringRows(context: WatchlistMonitorContext, signal: AbortSignal) {
    this.requireStaticScopes(); const generation = this.generation
    const value = await this.request('GET', watchlistMonitoringPath(context, true), signal)
    const snapshot = parseWatchlistMonitoringRows(value, context)
    this.assertCurrent(generation, signal); return snapshot
  }

  async writeWatchlistMonitoringRow(context: WatchlistMonitorContext, member: ScopeMember, expectedRevision: number,
    operation: 'CONFIGURE' | 'PIN' | 'MONITOR', selection: WatchlistStrategySelection | null, flag: boolean | null, signal: AbortSignal) {
    this.requireStaticScopes(); const generation = this.generation
    const body = watchlistCommandBody(context, member, expectedRevision, operation, selection, flag)
    const value = await this.request('POST', watchlistMonitoringPath(context), signal, body)
    const row = parseWatchlistMonitoringRow(value, context, member, expectedRevision)
    this.assertCurrent(generation, signal); return row
  }

  async staticScopes(projectId: string, after: string | null, includeArchived: boolean, signal: AbortSignal) {
    this.requireStaticScopes(); const generation = this.generation
    const query = new URLSearchParams({ limit: '50', include_archived: String(includeArchived) }); if (after !== null) query.set('after', after)
    const value = await this.request('GET', `ir/projects/${encodeURIComponent(projectId)}/static-scopes?${query}`, signal)
    const page = await parseStaticScopePage(value, projectId, after)
    this.assertCurrent(generation, signal); return page
  }

  async staticScope(projectId: string, scopeId: string, version: number | null, signal: AbortSignal) {
    this.requireStaticScopes(); const generation = this.generation
    const suffix = version === null ? '' : `/revisions/${version}`
    const value = await this.request('GET', `ir/projects/${encodeURIComponent(projectId)}/static-scopes/${encodeURIComponent(scopeId)}${suffix}`, signal)
    const scope = await parseStaticScope(value, projectId, scopeId, version ?? undefined)
    this.assertCurrent(generation, signal); return scope
  }

  async createStaticScope(projectId: string, scopeId: string, draft: ScopeDraft, signal: AbortSignal) {
    this.requireStaticScopes(); const generation = this.generation
    const value = await this.request('POST', `ir/projects/${encodeURIComponent(projectId)}/static-scopes`, signal, { scope_id: scopeId, name: draft.name, members: draft.members })
    const scope = await parseStaticScope(value, projectId, scopeId)
    this.assertCurrent(generation, signal); return scope
  }

  async reviseStaticScope(projectId: string, scopeId: string, expectedRevision: number, draft: ScopeDraft, signal: AbortSignal) {
    this.requireStaticScopes(); const generation = this.generation
    const value = await this.request('POST', `ir/projects/${encodeURIComponent(projectId)}/static-scopes/${encodeURIComponent(scopeId)}/revisions`, signal,
      { expected_revision: expectedRevision, name: draft.name, members: draft.members })
    const scope = await parseStaticScope(value, projectId, scopeId)
    this.assertCurrent(generation, signal); return scope
  }

  async archiveStaticScope(projectId: string, scopeId: string, expectedRevision: number, signal: AbortSignal) {
    this.requireStaticScopes(); const generation = this.generation
    const value = await this.request('POST', `ir/projects/${encodeURIComponent(projectId)}/static-scopes/${encodeURIComponent(scopeId)}/archive`, signal, { expected_revision: expectedRevision })
    const scope = await parseStaticScope(value, projectId, scopeId)
    this.assertCurrent(generation, signal); return scope
  }

  async researchDatasets(projectId: string, signal: AbortSignal) {
    this.requireStrategies()
    const generation = this.generation
    const collected: ResearchDataset[] = []
    let after: string | null = null
    for (let pageNumber = 0; pageNumber < 200; pageNumber += 1) {
      const query = new URLSearchParams({ limit: '50' }); if (after !== null) query.set('after', after)
      const value = await this.request('GET', `ir/projects/${encodeURIComponent(projectId)}/research-datasets?${query}`, signal)
      this.assertCurrent(generation, signal)
      const page = parseResearchDatasetPage(value, projectId, 50); collected.push(...page.items)
      if (page.next_cursor === null) return Object.freeze(collected)
      after = page.next_cursor
    }
    throw new ContractError()
  }

  async importProviderHistory(projectId: string, input: ProviderHistoryRequest, signal: AbortSignal) {
    this.requireStrategies(); const generation = this.generation
    assertProviderHistoryRequest(input)
    const value = await this.request('POST', `ir/projects/${encodeURIComponent(projectId)}/research-datasets/from-provider`,
      signal, input, false, MAX_REQUEST_BODY_BYTES, 120000)
    this.assertCurrent(generation, signal)
    return parseProviderHistoryReceipt(value, projectId, input)
  }

  async inspectDailyCsv(projectId: string, file: File, metadata: DailyCsvMetadata,
    signal: AbortSignal, sessionMetadata?: File) {
    this.requireStrategies(); const generation = this.generation
    const value = await this.dailyCsvRequest(projectId, 'inspect-csv', file, metadata, signal, sessionMetadata)
    this.assertCurrent(generation, signal)
    return parseDailyCsvInspection(value)
  }

  async importDailyCsv(projectId: string, file: File, metadata: DailyCsvMetadata,
    signal: AbortSignal, sessionMetadata?: File) {
    this.requireStrategies(); const generation = this.generation
    const value = await this.dailyCsvRequest(projectId, 'import-csv', file, metadata, signal, sessionMetadata)
    this.assertCurrent(generation, signal)
    return parseDailyCsvImport(value, projectId)
  }

  async visualization(projectId: string, runId: number, tradeAfter: number, signal: AbortSignal) {
    this.requireStrategies()
    const generation = this.generation
    const query = new URLSearchParams({ trade_after: String(tradeAfter), trade_limit: '100' })
    const value = await this.request('GET', `ir/projects/${encodeURIComponent(projectId)}/experiments/${runId}/visualization?${query}`, signal)
    this.assertCurrent(generation, signal)
    return parseResearchVisualization(value)
  }

  async marketContext(projectId: string, runId: number, replayAt: string | null,
                      signal: AbortSignal): Promise<MarketContext> {
    this.requireStrategies(); const generation = this.generation
    const bars = []; let after = 0; let first: MarketContext | null = null
    for (let pageNumber = 0; pageNumber < 4; pageNumber += 1) {
      const query = new URLSearchParams({ after: String(after), limit: '500' })
      if (replayAt !== null) query.set('replay_at', replayAt)
      const raw = await this.request('GET', `ir/projects/${encodeURIComponent(projectId)}/experiments/${runId}/market-context?${query}`, signal)
      this.assertCurrent(generation, signal)
      const page = parseMarketContext(raw, after, 500); if (first === null) first = page
      else if (page.market_context_address !== first.market_context_address || page.replay_at !== first.replay_at) throw new ContractError()
      bars.push(...page.bars)
      if (page.page.next_cursor === null) { const origin = first ?? page; return Object.freeze({ ...origin, bars: Object.freeze(bars), page: Object.freeze({ ...page.page, after: 0 }) }) }
      after = page.page.next_cursor
    }
    throw new ContractError()
  }

  async chartAnnotations(projectId: string, runId: number, contextAddress: string,
                         signal: AbortSignal): Promise<readonly ChartAnnotation[]> {
    this.requireStrategies(); const generation = this.generation
    const items: ChartAnnotation[] = []; let after: string | null = null
    for (let pageNumber = 0; pageNumber < 6; pageNumber += 1) {
      const query = new URLSearchParams({ limit: '50' }); if (after !== null) query.set('after', after)
      const raw = await this.request('GET', `ir/projects/${encodeURIComponent(projectId)}/experiments/${runId}/market-context/annotations?${query}`, signal)
      this.assertCurrent(generation, signal)
      const page = parseChartAnnotationPage(raw, contextAddress, 50); items.push(...page.items)
      if (items.length > 256) throw new ContractError()
      if (page.next_cursor === null) return Object.freeze(items)
      after = page.next_cursor
    }
    throw new ContractError()
  }

  async createChartAnnotation(projectId: string, runId: number, geometry: Readonly<Record<string, unknown>>,
                              applicability: Readonly<Record<string, unknown>>, signal: AbortSignal) {
    this.requireStrategies(); const generation = this.generation
    const raw = await this.request('POST', `ir/projects/${encodeURIComponent(projectId)}/experiments/${runId}/market-context/annotations`, signal, { geometry, applicability })
    this.assertCurrent(generation, signal); return parseChartAnnotation(raw)
  }

  async updateChartAnnotation(projectId: string, runId: number, annotationId: string, expectedRevision: number,
                              geometry: Readonly<Record<string, unknown>>, applicability: Readonly<Record<string, unknown>>, signal: AbortSignal) {
    this.requireStrategies(); const generation = this.generation
    const raw = await this.request('PUT', `ir/projects/${encodeURIComponent(projectId)}/experiments/${runId}/market-context/annotations/${encodeURIComponent(annotationId)}`, signal,
      { expected_revision: expectedRevision, geometry, applicability })
    this.assertCurrent(generation, signal); return parseChartAnnotation(raw)
  }

  async deleteChartAnnotation(projectId: string, runId: number, annotationId: string,
                              expectedRevision: number, signal: AbortSignal) {
    this.requireStrategies(); const generation = this.generation
    await this.request('DELETE', `ir/projects/${encodeURIComponent(projectId)}/experiments/${runId}/market-context/annotations/${encodeURIComponent(annotationId)}`, signal,
      { expected_revision: expectedRevision })
    this.assertCurrent(generation, signal)
  }

  async experiment(projectId: string, runId: number, signal: AbortSignal) {
    this.requireStrategies()
    const generation = this.generation
    const value = await this.request('GET', `ir/projects/${encodeURIComponent(projectId)}/experiments/${runId}`, signal)
    this.assertCurrent(generation, signal)
    return parseExperimentDetail(value)
  }

  async researchRecovery(context: SavedResearchContext, signal: AbortSignal) {
    this.requireStrategies(); const generation = this.generation
    const value = await this.request('GET', 'research/operations/status', signal)
    this.assertCurrent(generation, signal)
    return parseResearchRecovery(value, context)
  }

  async cancelRecoveryOperation(id: string, signal: AbortSignal) {
    this.requireStrategies(); const generation = this.generation
    const value = await this.request('POST', `research/operations/${operationId(id)}/cancel`, signal)
    this.assertCurrent(generation, signal)
    return parseRecoveryCancellation(value, id)
  }

  private accountRiskRequest(method: 'GET' | 'POST', signal: AbortSignal, body?: { key: AccountRiskKey; value: number }) {
    this.requireStrategies()
    return this.send(method, 'account-risk-settings', signal, body ? JSON.stringify(body) : undefined, method === 'POST', async (response) => {
      if (response.status === 401) { this.recheck(); throw new ApiError('access', 'Sign in again to view account entry limits.') }
      if (response.status === 403) throw new ApiError('input', 'Account entry limit permission refused.', { code: 'ACCOUNT_RISK_FORBIDDEN', message: 'Permission refused.' })
      if (!response.ok) throw new ApiError('server', 'Account entry limits could not be updated or loaded. Retry when the service is available.')
      if (!response.headers.get('content-type')?.includes('application/json')) throw new ContractError()
      const result: unknown = await response.json()
      if (result && typeof result === 'object' && 'error' in result) throw new ApiError('input', 'This account entry limit was not saved. Check the amount and reload the saved limits.')
      return result
    })
  }

  async accountRiskSettings(signal: AbortSignal) {
    return parseAccountRiskSettings(await this.accountRiskRequest('GET', signal))
  }

  async saveAccountRiskSetting(key: AccountRiskKey, value: number, signal: AbortSignal) {
    const body = validateAccountRiskUpdate(key, value)
    return parseAccountRiskSave(await this.accountRiskRequest('POST', signal, body), key, value)
  }

  async workspaceResearchSettings(signal: AbortSignal) {
    this.requireStrategies(); const generation = this.generation
    const value = await this.request('GET', 'research-settings', signal)
    this.assertCurrent(generation, signal)
    return parseWorkspaceResearchSettings(value)
  }

  async strategyResearchSettings(projectId: string, graphId: string, signal: AbortSignal) {
    this.requireStrategies(); const generation = this.generation
    const value = await this.request('GET', `ir/projects/${encodeURIComponent(projectId)}/graphs/${encodeURIComponent(graphId)}/research-settings`, signal)
    this.assertCurrent(generation, signal)
    return parseStrategyResearchSettings(value, graphId)
  }

  async saveResearchSettings(body: { request_id: string; expected_revision: number; values: Partial<ResearchValues> }, signal: AbortSignal, strategy?: { projectId: string; graphId: string; enabled: boolean }) {
    this.requireStrategies(); const generation = this.generation
    const path = strategy ? `ir/projects/${encodeURIComponent(strategy.projectId)}/graphs/${encodeURIComponent(strategy.graphId)}/research-settings` : 'research-settings'
    const value = await this.request('PUT', path, signal, strategy ? { ...body, enabled: strategy.enabled } : body)
    this.assertCurrent(generation, signal)
    const saved = parseResearchSettingsRevision(value, strategy?.graphId ?? null)
    assertResearchSettingsSave(saved, body.expected_revision, body.values, strategy?.enabled ?? true)
    return saved
  }

  async prepareResearch(projectId: string, graphId: string, version: number, body: ResearchPreparation, signal: AbortSignal) {
    this.requireStrategies(); const generation = this.generation
    const value = await this.request('POST', `ir/projects/${encodeURIComponent(projectId)}/graphs/${encodeURIComponent(graphId)}/versions/${version}/research-preparations`, signal, body)
    this.assertCurrent(generation, signal)
    return parsePreparationReceipt(value, body.request_id)
  }

  async prepareResearchFromSettings(projectId: string, graphId: string, version: number, body: SettingsPreparation, signal: AbortSignal) {
    this.requireStrategies(); const generation = this.generation
    const value = await this.request('POST', `ir/projects/${encodeURIComponent(projectId)}/graphs/${encodeURIComponent(graphId)}/versions/${version}/research-preparations/from-settings`, signal, body)
    this.assertCurrent(generation, signal)
    return parsePreparationReceipt(value, body.request_id)
  }

  async prepareResearchFromInputs(projectId: string, graphId: string, version: number, body: InputSettingsPreparation, signal: AbortSignal) {
    this.requireStrategies(); const generation = this.generation
    const value = await this.request('POST', `ir/projects/${encodeURIComponent(projectId)}/graphs/${encodeURIComponent(graphId)}/versions/${version}/research-preparations/from-inputs`, signal, body)
    this.assertCurrent(generation, signal)
    return parsePreparationReceipt(value, body.request_id)
  }

  async researchOperation(id: string, selection: ResearchSelection, signal: AbortSignal) {
    this.requireStrategies(); const generation = this.generation
    const value = await this.request('GET', `research/operations/${operationId(id)}`, signal)
    this.assertCurrent(generation, signal)
    return parsePreparedOperation(value, id, selection)
  }

  async cancelResearchOperation(id: string, selection: ResearchSelection, signal: AbortSignal) {
    this.requireStrategies(); const generation = this.generation
    const value = await this.request('POST', `research/operations/${operationId(id)}/cancel`, signal)
    this.assertCurrent(generation, signal)
    return parsePreparedOperation(value, id, selection)
  }


  async compareVersions(projectId: string, leftVersion: number, rightVersion: number,
    leftRunId: number | null, rightRunId: number | null, graphId: string, signal: AbortSignal) {
    this.requireStrategies()
    const generation = this.generation
    const selection = (graph_version: number, run_id: number | null) => ({ format_version: 2, graph_identifier: graphId, graph_version,
      ...(run_id === null ? {} : { run_id }) })
    const value = await this.request('POST', `ir/projects/${encodeURIComponent(projectId)}/version-comparisons`, signal,
      { left: selection(leftVersion, leftRunId), right: selection(rightVersion, rightRunId) })
    this.assertCurrent(generation, signal)
    return parseComparison(value)
  }

  async review(projectId: string, signal: AbortSignal) {
    this.requireStrategies()
    const generation = this.generation
    const value = await this.request('GET', `ir/projects/${encodeURIComponent(projectId)}/review?limit=50`, signal)
    this.assertCurrent(generation, signal)
    return parseReview(value, projectId)
  }
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return {
    access: 'Your session no longer has access. Sign in again or check your workspace membership.',
    input: 'Check the information you entered and try again.',
    network: 'The server could not be reached. Check the connection and retry.',
    timeout: 'The server did not respond in time. Try again.',
    server: 'The server could not complete this request. Try again.',
    manifest: 'Strategies are unavailable until the server release is verified.',
  }[error.kind]
  return error instanceof ContractError
    ? 'The server response could not be verified. Refresh and try again.'
    : 'This information is unavailable. Try again.'
}
