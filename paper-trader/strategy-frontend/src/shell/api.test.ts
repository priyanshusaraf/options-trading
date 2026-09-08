import { createWatchlistMonitorClient, parseWatchlistMonitoringRows, parseWatchlistMonitoringRow, watchlistContextBody } from '../features/static-scopes/watchlistMonitorClient'
import optimizationFixture from '../test/canonicalOptimization.json'
import { parseCanonicalOptimizationEvidence, parseOptimizationSettings, disabledOptimization, compareOptimizationAxes } from './contracts'
import { optimizationInputProblem } from '../research/OptimizationSettingsFields'
import { accountRiskFields, canEditAccountRisk, parseAccountRiskSettings, parseAccountRiskSave } from '../research/accountRiskContracts'
import { parseResearchSettingsRevision, parseWorkspaceResearchSettings } from './contracts'
import { createHash, webcrypto } from 'node:crypto'
import { parseStaticScope, parseStaticScopePage } from '../features/static-scopes/staticScopeContracts'
import { parsePaperPortfolio } from '../features/portfolio/portfolioContracts'
import { inputSettingsPreparation, settingsPreparation, parsePreparedOperation, parsePreparationReceipt, parseSavedResearchPolicy, parseResearchRecovery, type ResearchSelection } from '../research/preparedResearchContracts'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, StrategyApi, errorMessage } from './api'
import { createAccountCommerceClient } from '../features/account/accountCommerceClient'
import { createDataConnectionClient } from '../features/connections/dataConnectionClient'
import type { DailyCsvMetadata } from '../features/data/dailyCsvContracts'
import release from '../test/releaseManifest.json'

function response(body: unknown, status = 200, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store', ...headers },
  })
}

const statusBody = {
  schema: 'account-commerce-status/1', profile_state: 'INCOMPLETE',
  satisfied_field_codes: [], profile_attested_at: null, trial_state: 'AVAILABLE',
  trial_source: null, trial_expires_at: null, access_state: 'INACTIVE',
  access_expires_at: null, evaluated_at: '2026-09-02T06:00:00Z',
}
const providerStatusBody = {
  schema: 'strategy-os-data-connection-status/1', state: 'APP_KEYS_REQUIRED',
  provider: 'ZERODHA', role: 'DATA', ready: false,
  credential_expiry: 'UNVERIFIED', rate_quota: 'UNVERIFIED',
  actions: { create: false, write_app_keys: true, rotate_app_keys: false, reauthenticate: false, revoke: true },
}
const browserSession = {
  user: { id: 'user.alpha', display_name: 'Alpha' }, organization_id: 'owner.alpha',
  memberships: [{ organization_id: 'owner.alpha', name: 'Alpha', role: 'owner' }],
  csrf: 'c'.repeat(64), expires_at: '2026-09-03T06:00:00Z',
}
const dailyMetadata: DailyCsvMetadata = {
  instrument: 'NIFTY 50', venue_code: 'XNSE', asset_class: 'INDEX',
  columns: { instrument: 'Index Name', date: 'Date', open: 'Open', high: 'High', low: 'Low', close: 'Close', volume: null },
  date_format: '%d %b %Y', date_timezone: 'Asia/Kolkata', interval: 'day', contract_kind: 'SPOT', currency: 'INR',
}
const dailyInspection = {
  schema: 'strategy-os-user-csv-inspection/1', source_type: 'USER_SUPPLIED',
  source_sha256: 'd'.repeat(64), byte_count: 120, row_count: 2,
  source_order: 'DESCENDING', fields: ['OPEN', 'HIGH', 'LOW', 'CLOSE'], interval: 'day',
  event_start: '2026-09-03T00:00:00+05:30', event_end: '2026-09-04T00:00:00+05:30',
  historical_source_availability: 'NOT_SUPPLIED', calendar_coverage: 'NOT_ASSERTED',
  rights_scope: 'PERSONAL_RESEARCH_ONLY',
}

afterEach(() => vi.restoreAllMocks())

describe('StrategyApi account-commerce transport', () => {
  it('owns the fixed same-origin no-store redirect-error fetch seam', async () => {
    const fetch = vi.spyOn(globalThis, 'fetch').mockResolvedValue(response(statusBody))
    const api = new StrategyApi()
    await createAccountCommerceClient(api.accountCommerceTransport)
      .load(new AbortController().signal)
    expect(fetch).toHaveBeenCalledTimes(1)
    expect(fetch).toHaveBeenCalledWith('/api/v1/account-commerce/status', expect.objectContaining({
      method: 'GET', credentials: 'same-origin', cache: 'no-store', redirect: 'error',
      headers: { Accept: 'application/json' },
    }))
  })

  it('injects only the in-memory session CSRF value for a mutation', async () => {
    const fetch = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(response({
        user: { id: 'user.alpha', display_name: 'Alpha' },
        organization_id: 'owner.alpha',
        memberships: [{ organization_id: 'owner.alpha', name: 'Alpha', role: 'owner' }],
        csrf: 'a'.repeat(64), expires_at: '2026-09-03T06:00:00Z',
      }))
      .mockResolvedValueOnce(response({
        schema: 'account-commerce-profile-evidence/1', profile_state: 'COMPLETE',
        satisfied_field_codes: ['profile.country', 'profile.full_name'],
        attested_at: '2026-09-02T06:00:00Z', replayed: false,
      }))
    const api = new StrategyApi()
    await api.session(new AbortController().signal)
    await createAccountCommerceClient(api.accountCommerceTransport).attestRequiredDetails(
      { full_name: 'Alpha User', country: 'IN' }, new AbortController().signal,
    )
    expect(fetch.mock.calls[1][1]).toMatchObject({
      method: 'POST', body: '{"full_name":"Alpha User","country":"IN"}',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json',
        'X-Strategy-CSRF': 'a'.repeat(64) },
    })
  })

  it('captures fixed authentication responses before invalidating access', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(response(
      { error: 'authentication refused' }, 401,
    ))
    const api = new StrategyApi()
    const invalidated = vi.fn()
    api.onAccessInvalidated(invalidated)
    await expect(createAccountCommerceClient(api.accountCommerceTransport)
      .load(new AbortController().signal)).rejects.toMatchObject({
        status: 401, code: 'AUTHENTICATION_REFUSED',
      })
    expect(invalidated).toHaveBeenCalledOnce()
  })

  it('refuses declared and measured responses beyond 65536 bytes', async () => {
    const api = new StrategyApi()
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(response(statusBody, 200, {
      'Content-Length': '65537',
    }))
    await expect(createAccountCommerceClient(api.accountCommerceTransport)
      .load(new AbortController().signal)).rejects.toBeTruthy()
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(response({ raw: 'x'.repeat(66000) }))
    await expect(createAccountCommerceClient(api.accountCommerceTransport)
      .load(new AbortController().signal)).rejects.toBeTruthy()
  })

  it('refuses a forged descriptor before fetch', async () => {
    const fetch = vi.spyOn(globalThis, 'fetch')
    const api = new StrategyApi()
    await expect(api.accountCommerceTransport({
      method: 'GET', path: '/api/v1/account-commerce/status',
      signal: new AbortController().signal, credentials: 'same-origin', cache: 'no-store',
      redirect: 'error', csrfRequired: true, headers: { Accept: 'application/json' },
      requestBodyLimitBytes: 4096, responseBodyLimitBytes: 65536,
    })).rejects.toMatchObject({ kind: 'input' })
    expect(fetch).not.toHaveBeenCalled()
  })
})

describe('StrategyApi data-connection transport', () => {
  it.each([401, 403])('invalidates access on provider response %i', async (status) => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(response({}, status))
    const api = new StrategyApi()
    const listener = vi.fn()
    api.onAccessInvalidated(listener)
    await api.dataConnectionTransport({
      method: 'GET', path: '/api/v1/data-connections/status',
      signal: new AbortController().signal, credentials: 'same-origin', cache: 'no-store',
      redirect: 'error', csrfRequired: false, headers: { Accept: 'application/json' },
      requestBodyLimitBytes: 4096, responseBodyLimitBytes: 65536,
    })
    expect(listener).toHaveBeenCalledWith(expect.objectContaining({ kind: 'access' }))
  })

  it.each([
    ['declared size', '{}', '65537'],
    ['invalid size', '{}', 'invalid'],
    ['actual size', JSON.stringify({ value: 'x'.repeat(65536) }), null],
    ['malformed JSON', 'not-json', null],
  ])('refuses an invalid provider response: %s', async (_label, body, length) => {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    if (length !== null) headers['Content-Length'] = length
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(new Response(body, { headers }))
    await expect(new StrategyApi().dataConnectionTransport({
      method: 'GET', path: '/api/v1/data-connections/status',
      signal: new AbortController().signal, credentials: 'same-origin', cache: 'no-store',
      redirect: 'error', csrfRequired: false, headers: { Accept: 'application/json' },
      requestBodyLimitBytes: 4096, responseBodyLimitBytes: 65536,
    })).rejects.toBeTruthy()
  })

  it.each([
    { extra: true }, { method: 'PUT' }, { signal: {} },
    { credentials: 'include' }, { cache: 'default' }, { redirect: 'follow' },
    { requestBodyLimitBytes: 8192 }, { responseBodyLimitBytes: 100000 },
    { csrfRequired: false }, { headers: Object.create(null) },
    { headers: { Accept: 'application/json', 'Content-Type': 'application/json', Extra: 'x' } },
    { headers: { Accept: 'text/html', 'Content-Type': 'application/json' } },
    { headers: { Accept: 'application/json', 'Content-Type': 'text/plain' } },
    { headers: { Accept: 'application/json', Different: 'application/json' } },
    { body: undefined }, { body: 'x'.repeat(4097) },
  ])('preserves closed provider descriptor validation: %j', async (override) => {
    const fetch = vi.spyOn(globalThis, 'fetch')
    const descriptor = {
      method: 'POST', path: '/api/v1/data-connections/app-keys',
      signal: new AbortController().signal, credentials: 'same-origin', cache: 'no-store',
      redirect: 'error', csrfRequired: true,
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' }, body: '{}',
      requestBodyLimitBytes: 4096, responseBodyLimitBytes: 65536, ...override,
    } as Parameters<StrategyApi['dataConnectionTransport']>[0]
    await expect(new StrategyApi().dataConnectionTransport(descriptor)).rejects.toMatchObject({ kind: 'input' })
    expect(fetch).not.toHaveBeenCalled()
  })

  it.each([
    'query=NIFTY+50&exchange=NSE&limit=20',
    'exchange=BSE&limit=1&query=ab',
    'query=SMALL&exchange=ALL&limit=20',
    'query=FUT&exchange=MCX&limit=20',
    'query=OPTION&exchange=NFO&limit=20',
    `limit=50&query=${'a'.repeat(64)}&exchange=NSE`,
  ])('allows bounded provider instrument reads: %s', async (query) => {
    const fetch = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(response({ rows: [] }))
    const path = `/api/v1/data-connections/instruments?${query}` as const
    await new StrategyApi().dataConnectionTransport({
      method: 'GET', path,
      signal: new AbortController().signal, credentials: 'same-origin', cache: 'no-store',
      redirect: 'error', csrfRequired: false, headers: { Accept: 'application/json' },
      requestBodyLimitBytes: 4096, responseBodyLimitBytes: 65536,
    })
    expect(fetch).toHaveBeenCalledExactlyOnceWith(path, expect.objectContaining({
      method: 'GET', credentials: 'same-origin', cache: 'no-store', redirect: 'error',
      headers: { Accept: 'application/json' },
    }))
  })

  it.each([
    'query=NIFTY&exchange=NSE&limit=20#fragment',
    'exchange=NSE&limit=20&query=NIFTY#fragment',
    'query=NIFTY&exchange=NSE&limit=20&extra=true',
    'query=NIFTY&exchange=NSE&limit=20&query=BANK',
    'query=NIFTY&exchange=NSE',
    'query=a&exchange=NSE&limit=20',
    `query=${'a'.repeat(65)}&exchange=NSE&limit=20`,
    'query=++&exchange=NSE&limit=20',
    'query=NIFTY&exchange=NFO%2Fother&limit=20',
    'query=NIFTY&exchange=NSE&limit=0',
    'query=NIFTY&exchange=NSE&limit=51',
    'query=NIFTY&exchange=NSE&limit=1.5',
  ])('refuses invalid instrument descriptors before fetch: %s', async (query) => {
    const fetch = vi.spyOn(globalThis, 'fetch')
    await expect(new StrategyApi().dataConnectionTransport({
      method: 'GET', path: `/api/v1/data-connections/instruments?${query}`,
      signal: new AbortController().signal, credentials: 'same-origin', cache: 'no-store',
      redirect: 'error', csrfRequired: false, headers: { Accept: 'application/json' },
      requestBodyLimitBytes: 4096, responseBodyLimitBytes: 65536,
    })).rejects.toMatchObject({ kind: 'input' })
    expect(fetch).not.toHaveBeenCalled()
  })

  it('refuses a mutation through the provider instrument search route', async () => {
    const fetch = vi.spyOn(globalThis, 'fetch')
    await expect(new StrategyApi().dataConnectionTransport({
      method: 'POST', path: '/api/v1/data-connections/instruments?query=NIFTY&exchange=NSE&limit=20',
      signal: new AbortController().signal, credentials: 'same-origin', cache: 'no-store',
      redirect: 'error', csrfRequired: true,
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' }, body: '{}',
      requestBodyLimitBytes: 4096, responseBodyLimitBytes: 65536,
    })).rejects.toMatchObject({ kind: 'input' })
    expect(fetch).not.toHaveBeenCalled()
  })

  it('uses the sole fetch seam and injects the in-memory CSRF token for app keys', async () => {
    const fetch = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(response({
        user: { id: 'user.alpha', display_name: 'Alpha' }, organization_id: 'owner.alpha',
        memberships: [{ organization_id: 'owner.alpha', name: 'Alpha', role: 'owner' }],
        csrf: 'b'.repeat(64), expires_at: '2026-09-03T06:00:00Z',
      }))
      .mockResolvedValueOnce(response({ ...providerStatusBody, state: 'REAUTH_REQUIRED', actions: {
        create: false, write_app_keys: false, rotate_app_keys: true, reauthenticate: true, revoke: true,
      } }))
    const api = new StrategyApi()
    await api.session(new AbortController().signal)
    await createDataConnectionClient(api.dataConnectionTransport).storeAppKeys({
      api_key: 'KEY-SENTINEL', api_secret: 'SECRET-SENTINEL',
    }, new AbortController().signal)
    expect(fetch.mock.calls[1][0]).toBe('/api/v1/data-connections/app-keys')
    expect(fetch.mock.calls[1][1]).toMatchObject({
      method: 'POST', credentials: 'same-origin', cache: 'no-store', redirect: 'error',
      body: '{"api_key":"KEY-SENTINEL","api_secret":"SECRET-SENTINEL"}',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json',
        'X-Strategy-CSRF': 'b'.repeat(64) },
    })
  })

  it('sends generic selection through the sole CSRF-protected transport', async () => {
    const fetch = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(response({ user: { id: 'user.alpha', display_name: 'Alpha' }, organization_id: 'owner.alpha',
        memberships: [{ organization_id: 'owner.alpha', name: 'Alpha', role: 'owner' }], csrf: 'b'.repeat(64), expires_at: '2026-09-03T06:00:00Z' }))
      .mockResolvedValueOnce(response({ saved: true }))
    const api = new StrategyApi(), signal = new AbortController().signal
    await api.session(signal)
    const body = JSON.stringify({ reference: { token: 77, symbol: 'SMALLCAP', name: 'Unknown smallcap', exchange: 'NSE', segment: 'NSE',
      instrument_type: 'EQ', expiry: null, strike: '0', lot_size: '1', tick_size: '0.05' } })
    await api.dataConnectionTransport({ method: 'POST', path: '/api/v1/data-connections/instrument-selections', signal,
      credentials: 'same-origin', cache: 'no-store', redirect: 'error', csrfRequired: true,
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' }, body, requestBodyLimitBytes: 4096, responseBodyLimitBytes: 65536 })
    expect(fetch.mock.calls[1][0]).toBe('/api/v1/data-connections/instrument-selections')
    expect(fetch.mock.calls[1][1]).toMatchObject({ method: 'POST', headers: { 'X-Strategy-CSRF': 'b'.repeat(64) }, body })
  })

  it('sends instrument resolution through the CSRF-protected provider transport', async () => {
    const fetch = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(response({ user: { id: 'user.alpha', display_name: 'Alpha' }, organization_id: 'owner.alpha',
        memberships: [{ organization_id: 'owner.alpha', name: 'Alpha', role: 'owner' }], csrf: 'b'.repeat(64), expires_at: '2026-09-03T06:00:00Z' }))
      .mockResolvedValueOnce(response({ selection: 'synthetic' }))
    const api = new StrategyApi(), signal = new AbortController().signal
    await api.session(signal)
    await api.dataConnectionTransport({ method: 'POST', path: '/api/v1/data-connections/instruments/resolve', signal,
      credentials: 'same-origin', cache: 'no-store', redirect: 'error', csrfRequired: true,
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' }, body: JSON.stringify({ token: 256265, symbol: 'NIFTY 50', exchange: 'NSE' }),
      requestBodyLimitBytes: 4096, responseBodyLimitBytes: 65536 })
    expect(fetch.mock.calls[1][0]).toBe('/api/v1/data-connections/instruments/resolve')
    expect(fetch.mock.calls[1][1]).toMatchObject({ method: 'POST', headers: { 'X-Strategy-CSRF': 'b'.repeat(64) },
      body: JSON.stringify({ token: 256265, symbol: 'NIFTY 50', exchange: 'NSE' }) })
  })
  it.each(['GET', 'DELETE'] as const)('refuses a %s on instrument resolution before fetch', async (method) => {
    const fetch = vi.spyOn(globalThis, 'fetch')
    await expect(new StrategyApi().dataConnectionTransport({ method, path: '/api/v1/data-connections/instruments/resolve',
      signal: new AbortController().signal, credentials: 'same-origin', cache: 'no-store', redirect: 'error', csrfRequired: method !== 'GET',
      headers: { Accept: 'application/json' }, requestBodyLimitBytes: 4096, responseBodyLimitBytes: 65536 })).rejects.toMatchObject({ kind: 'input' })
    expect(fetch).not.toHaveBeenCalled()
  })

  it('refuses arbitrary provider paths before fetch', async () => {
    const fetch = vi.spyOn(globalThis, 'fetch')
    const api = new StrategyApi()
    await expect(api.dataConnectionTransport({
      method: 'GET', path: '/api/v1/data-connections/../orders',
      signal: new AbortController().signal, credentials: 'same-origin', cache: 'no-store',
      redirect: 'error', csrfRequired: false, headers: { Accept: 'application/json' },
      requestBodyLimitBytes: 4096, responseBodyLimitBytes: 65536,
    })).rejects.toMatchObject({ kind: 'input' })
    expect(fetch).not.toHaveBeenCalled()
  })
})

describe('StrategyApi daily CSV transport', () => {
  it('uses multipart through the sole transport with cookies and the in-memory CSRF token', async () => {
    const imported = { ...dailyInspection, schema: 'strategy-os-user-csv-import/1',
      project_id: 'project.a', manifest_address: `sha256:${'a'.repeat(64)}`,
      instrument_address: `sha256:${'b'.repeat(64)}`, imported_at: '2026-09-05T00:00:00Z',
      ready_as_of: '2026-09-04T18:30:00Z' }
    const fetch = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(response(release))
      .mockResolvedValueOnce(response(browserSession)).mockResolvedValueOnce(response(dailyInspection))
      .mockResolvedValueOnce(response(imported))
    const api = new StrategyApi(); const signal = new AbortController().signal
    await api.bootstrap(signal); await api.session(signal)
    const file = new File(['Index Name,Date,Open,High,Low,Close\n'], 'nifty.csv', { type: 'text/csv' })
    await api.inspectDailyCsv('project.a', file, dailyMetadata, signal)
    await api.importDailyCsv('project.a', file, dailyMetadata, signal)

    for (const call of fetch.mock.calls.slice(2)) {
      expect(call[0]).toMatch(/^\/api\/v1\/ir\/projects\/project\.a\/research-datasets\/(inspect|import)-csv$/)
      expect(call[1]).toMatchObject({ method: 'POST', credentials: 'same-origin', cache: 'no-store',
        redirect: 'error', headers: { Accept: 'application/json', 'X-Strategy-CSRF': 'c'.repeat(64) } })
      expect((call[1]!.headers as Record<string, string>)['Content-Type']).toBeUndefined()
      const body = call[1]!.body as FormData
      expect(body.get('file')).toBe(file)
      expect(body.get('session_metadata')).toBeNull()
      expect(JSON.parse(String(body.get('metadata')))).toEqual(dailyMetadata)
    }
  })

  it('keeps structured CSV refusals typed and refuses oversized files before fetch', async () => {
    const fetch = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(response(release))
      .mockResolvedValueOnce(response(browserSession)).mockResolvedValueOnce(response({
        detail: { code: 'CSV_HEADER_MISMATCH', message: 'private parser detail' },
      }, 422))
    const api = new StrategyApi(); const signal = new AbortController().signal
    await api.bootstrap(signal); await api.session(signal)
    await expect(api.inspectDailyCsv('project.a', new File(['bad'], 'bad.csv'), dailyMetadata, signal))
      .rejects.toMatchObject({ kind: 'input', envelope: { code: 'CSV_HEADER_MISMATCH' } })
    await expect(api.inspectDailyCsv('project.a', new File([new Uint8Array(1024 * 1024 + 1)], 'large.csv'), dailyMetadata, signal))
      .rejects.toMatchObject({ kind: 'input' })
    expect(fetch).toHaveBeenCalledTimes(3)
  })

  it('aborts an in-flight CSV request when the API generation changes', async () => {
    const fetch = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(response(release))
      .mockResolvedValueOnce(response(browserSession)).mockImplementationOnce((_url, init) => new Promise((_resolve, reject) => {
        init?.signal?.addEventListener('abort', () => reject(new DOMException('cancelled', 'AbortError')))
      }))
    const api = new StrategyApi(); const signal = new AbortController().signal
    await api.bootstrap(signal); await api.session(signal)
    const pending = api.inspectDailyCsv('project.a', new File(['csv'], 'daily.csv'), dailyMetadata, signal)
    api.recheck()
    await expect(pending).rejects.toMatchObject({ name: 'AbortError' })
    expect((fetch.mock.calls[2][1]!.signal as AbortSignal).aborted).toBe(true)
  })

  it.each([
    [413, { detail: { code: 'CSV_SIZE_INVALID', message: 'CSV file exceeds 1 MiB' } }, 'input'],
    [404, { detail: 'project not found' }, 'access'],
    [403, { detail: { code: 'CSRF_INVALID', message: 'CSRF token invalid' } }, 'access'],
  ] as const)('maps CSV HTTP %s to a typed error', async (status, body, kind) => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(response(release))
      .mockResolvedValueOnce(response(browserSession)).mockResolvedValueOnce(response(body, status))
    const api = new StrategyApi(); const signal = new AbortController().signal
    await api.bootstrap(signal); await api.session(signal)
    await expect(api.inspectDailyCsv('project.a', new File(['csv'], 'daily.csv'), dailyMetadata, signal))
      .rejects.toMatchObject({ kind })
  })
})

describe('human error copy', () => {
  it('never renders backend envelope codes or messages', () => {
    const rendered = errorMessage(new ApiError('server', 'raw internal detail', {
      code: 'CANONICAL_PROVIDER_SECRET_FAILURE',
      message: 'CANONICAL provider failure with token detail',
    }))
    expect(rendered).toBe('The server could not complete this request. Try again.')
    expect(rendered).not.toMatch(/CANONICAL|PROVIDER_SECRET|raw internal|token detail/i)
  })

  it.each([
    ['access', 'Your session no longer has access. Sign in again or check your workspace membership.'],
    ['input', 'Check the information you entered and try again.'],
    ['network', 'The server could not be reached. Check the connection and retry.'],
    ['timeout', 'The server did not respond in time. Try again.'],
    ['manifest', 'Strategies are unavailable until the server release is verified.'],
  ] as const)('maps %s errors to bounded copy', (kind, expected) => {
    expect(errorMessage(new ApiError(kind, 'hidden'))).toBe(expected)
  })
})

describe('StrategyApi Market context', () => {
  it('uses the sole bounded no-store transport and parses a completed-candle page', async () => {
    const address = (digit: string) => `sha256:${digit.repeat(64)}`
    const page = { schema: 'strategy-os-market-context/1', state: 'AVAILABLE',
      market_context_address: address('a'), projection_address: address('b'),
      source: { kind: 'VERIFIED_SAVED_RUN', address: address('c') }, graph: {},
      dataset_manifest_address: address('d'), canonical_instrument_address: address('e'),
      instrument_label: 'XNSE · EQUITY · SPOT', timeframe_seconds: 60,
      source_as_of: '2026-01-01T10:01:00Z', replay_at: '2026-01-01T10:01:00Z',
      bars: [{ cursor: 1, event_time: '2026-01-01T10:00:00Z', completed_at: '2026-01-01T10:01:00Z',
        open: 100, high: 102, low: 99, close: 101, volume: 10 }],
      page: { after: 0, limit: 500, next_cursor: null, visible_count: 1 } }
    const fetch = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(response(release)).mockResolvedValueOnce(response(page))
    const api = new StrategyApi(); await api.bootstrap(new AbortController().signal)
    const context = await api.marketContext('project.a', 7, null, new AbortController().signal)
    expect(context.bars).toHaveLength(1)
    expect(fetch.mock.calls[1][0]).toBe('/api/v1/ir/projects/project.a/experiments/7/market-context?after=0&limit=500')
    expect(fetch.mock.calls[1][1]).toMatchObject({ method: 'GET', cache: 'no-store', credentials: 'same-origin' })
  })

  it('refuses annotation aggregation above the exact 256-row ceiling', async () => {
    const address = (digit: string) => `sha256:${digit.repeat(64)}`
    const annotation = (index: number) => ({
      annotation_id: `00000000-0000-0000-0000-${String(index).padStart(12, '0')}`,
      revision: 1, geometry: { kind: 'LEVEL', price: '100' }, geometry_address: address('a'),
      applicability: { known_at: '2026-01-01T10:00:00Z' }, applicability_address: address('b'),
      created_at: '2026-01-01T10:00:00Z', updated_at: '2026-01-01T10:00:00Z',
    })
    const pages = Array.from({ length: 6 }, (_, pageIndex) => {
      const start = pageIndex * 50 + 1; const count = pageIndex < 5 ? 50 : 7
      const items = Array.from({ length: count }, (_unused, offset) => annotation(start + offset))
      return { schema: 'strategy-os-chart-annotation-presentation/1',
        market_context_address: address('c'), items,
        next_cursor: pageIndex < 5 ? items.at(-1)!.annotation_id : null }
    })
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(response(release))
    for (const page of pages) vi.mocked(globalThis.fetch).mockResolvedValueOnce(response(page))
    const api = new StrategyApi(); await api.bootstrap(new AbortController().signal)
    await expect(api.chartAnnotations('project.a', 7, address('c'),
      new AbortController().signal)).rejects.toBeTruthy()
    expect(globalThis.fetch).toHaveBeenCalledTimes(7)
  })
})

describe('StrategyApi presets', () => {
  const preset = { preset_id: 'trend_impulse_v3', name: 'Original V3', description: 'EMA slope and z-score',
    parameters: { length: 50 }, provenance: { semantic_version: 1, source: 'signals.py', source_sha256: 'a'.repeat(64) }, available: true }
  const copy = { project_id: 'project.a', identifier: 'my.v3', display_name: 'My V3', revision: 0,
    current_version: null, graph: { format_version: 2, strategy_id: 'my.v3', strategy_version: 1 } }
  it('lists server templates and copies a draft with only closed request fields', async () => {
    const fetch = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(response(release))
      .mockResolvedValueOnce(response({ presets: [preset] })).mockResolvedValueOnce(response(copy, 201))
    const api = new StrategyApi(); const signal = new AbortController().signal
    await api.bootstrap(signal)
    expect(await api.presets(signal)).toHaveLength(1)
    expect(await api.copyPreset('project.a', 'trend_impulse_v3', 'my.v3', 'My V3', signal)).toMatchObject({ identifier: 'my.v3' })
    expect(fetch.mock.calls[1][0]).toBe('/api/v1/ir/presets')
    expect(fetch.mock.calls[2]).toEqual(['/api/v1/ir/projects/project.a/presets/trend_impulse_v3/copy', expect.objectContaining({
      method: 'POST', credentials: 'same-origin', cache: 'no-store', body: JSON.stringify({ identifier: 'my.v3', name: 'My V3' }),
    })])
  })
  it.each([{ ...copy, project_id: 'another-owner-project' }, { ...copy, identifier: 'wrong' }, { ...copy, current_version: 1 },
    { ...copy, graph: { ...copy.graph, strategy_id: 'wrong' } }])('rejects mismatched copy identity or published state', async (body) => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(response(release)).mockResolvedValueOnce(response(body))
    const api = new StrategyApi(); const signal = new AbortController().signal; await api.bootstrap(signal)
    await expect(api.copyPreset('project.a', 'trend_impulse_v3', 'my.v3', '', signal)).rejects.toThrow()
  })
  it.each([{ presets: [preset, preset] }, { presets: [{ ...preset, available: 'yes' }] },
    { presets: [{ ...preset, parameters: { length: '50' } }] }, { presets: [preset], extra: true }])('rejects an invalid template catalogue', async (body) => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(response(release)).mockResolvedValueOnce(response(body))
    const api = new StrategyApi(); const signal = new AbortController().signal; await api.bootstrap(signal)
    await expect(api.presets(signal)).rejects.toThrow()
  })
})


describe('saved V2 research preparations', () => {
  const request = { request_id: '12345678-1234-4234-8234-123456789abc', dataset_manifest_address: `sha256:${'a'.repeat(64)}`,
    dataset_as_of: '2026-09-05T00:00:00Z', hypothesis: 'Completed prices support the trend rule.', research_capital: 100000,
    seed: 0, min_trades: 10, n_folds: 4, min_positive_fold_frac: .6, risk_policy: 'none' as const }
  const id = 'b'.repeat(64)
  const selection: ResearchSelection = { projectId: 'project.a', graphId: 'strategy.a', version: 1, contentAddress: `sha256:${'c'.repeat(64)}`, request }
  const receipt = { request_id: request.request_id, operation_id: id, status: 'pending',
    status_url: `/api/research/operations/${id}`, cancel_url: `/api/research/operations/${id}/cancel` }
  const experiment = { hypothesis: request.hypothesis, research_capital: request.research_capital, seed: 0, min_trades: 10, n_folds: 4, min_positive_fold_frac: .6 }
  const descriptor = { project_id: selection.projectId, graph_identifier: selection.graphId, graph_version: 1,
    content_address: selection.contentAddress, request_id: request.request_id, dataset_manifest_address: request.dataset_manifest_address,
    dataset_as_of: request.dataset_as_of, experiment, execution_policy: { risk: { risk_policy: 'none', capital: 100000 } } }
  const status = { operation_id: id, trigger: 'v2_graph', status: 'completed', stage: 'completed', error: null,
    cancel_requested_at: null, completed_run_ids: [9], plan: { schema: 'v2-graph-research-operation/2', experiment_count: 1, v2_graphs: [descriptor] } }

  it('uses the same CSRF transport for POST202, versioned status and cancellation', async () => {
    const fetch = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(response(release)).mockResolvedValueOnce(response(browserSession))
      .mockResolvedValueOnce(response(receipt, 202)).mockResolvedValueOnce(response(status))
      .mockResolvedValueOnce(response({ ...status, status: 'cancelled', completed_run_ids: [] }))
    const api = new StrategyApi(); const signal = new AbortController().signal
    await api.bootstrap(signal); await api.session(signal)
    expect(await api.prepareResearch('project.a', 'strategy.a', 1, request, signal)).toMatchObject({ operation_id: id, status: 'pending' })
    expect(await api.researchOperation(id, selection, signal)).toMatchObject({ completed_run_ids: [9] })
    expect(await api.cancelResearchOperation(id, selection, signal)).toMatchObject({ status: 'cancelled' })
    expect(fetch.mock.calls[2][0]).toBe('/api/v1/ir/projects/project.a/graphs/strategy.a/versions/1/research-preparations')
    expect(JSON.parse(String(fetch.mock.calls[2][1]?.body))).toEqual(request)
    expect(fetch.mock.calls[3][0]).toBe(`/api/v1/research/operations/${id}`)
    expect(fetch.mock.calls[4][0]).toBe(`/api/v1/research/operations/${id}/cancel`)
    for (const index of [2, 4]) expect(fetch.mock.calls[index][1]).toMatchObject({ method: 'POST', credentials: 'same-origin', headers: { 'X-Strategy-CSRF': 'c'.repeat(64) }, redirect: 'error' })
  })

  it.each([
    { request_id: 'other' }, { operation_id: '../outside' }, { status_url: 'https://other.invalid/status' },
    { cancel_url: '/api/research/operations/other/cancel' }, { status: 'unknown' },
  ])('rejects an unbound preparation receipt', (change) => {
    expect(() => parsePreparationReceipt({ ...receipt, ...change }, request.request_id)).toThrow()
  })

  it.each([
    { project_id: 'project.other' }, { graph_identifier: 'strategy.other' }, { graph_version: 2 },
    { request_id: 'different' }, { content_address: `sha256:${'d'.repeat(64)}` },
    { dataset_manifest_address: `sha256:${'e'.repeat(64)}` }, { dataset_as_of: '2025-09-05T00:00:00Z' },
    { experiment: { ...experiment, seed: 1 } }, { experiment: { ...experiment, optimize_search: true } },
    { execution_policy: { risk: { risk_policy: 'pine-v4-ratchet/1', capital: 100000 } } },
  ])('rejects another selection before exposing completed run IDs', (change) => {
    expect(() => parsePreparedOperation({ ...status, plan: { ...status.plan, v2_graphs: [{ ...descriptor, ...change }] } }, id, selection)).toThrow()
  })

  it.each([{ completed_run_ids: [] }, { completed_run_ids: [0] }, { completed_run_ids: ['9'] }, { completed_run_ids: [9, 9] },
    { operation_id: 'f'.repeat(64) }, { status: 'success' }, { trigger: 'other' }, { cancel_requested_at: 'invalid' }])('refuses an unverifiable completion', (change) => {
    expect(() => parsePreparedOperation({ ...status, ...change }, id, selection)).toThrow()
  })

  it('verifies saved-version metadata before choosing a policy and retains typed failure reasons', () => {
    const version = { format_version: 2, graph_identifier: 'strategy.a', graph_version: 1, content_address: selection.contentAddress,
      document: { format_version: 2, strategy_id: 'strategy.a', metadata: { tags: ['expanding-z-v4'] }, graph_inputs: [{ port_id: 'frame', direction: 'input', semantic_role: 'market_frame' }] } }
    expect(parseSavedResearchPolicy(version, 'strategy.a', 1).riskPolicy).toBe('pine-v4-ratchet/1')
    expect(() => parseSavedResearchPolicy(version, 'strategy.a', 2)).toThrow()
    expect(() => parseSavedResearchPolicy({ ...version, document: { ...version.document, metadata: { tags: 'expanding-z-v4' } } }, 'strategy.a', 1)).toThrow()
    expect(parsePreparedOperation({ ...status, status: 'failed', completed_run_ids: [], error: { code: 'V2_PREPARATION_INVALID', message: 'The saved graph requires unavailable data.' } }, id, selection).error?.message).toBe('The saved graph requires unavailable data.')
  })
  it('reads the bounded owner list and cancels an unsupported matching request through the same transport', async () => {
    const active = { ...status, status: 'running', completed_run_ids: [] }
    const fetch = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(response(release)).mockResolvedValueOnce(response(browserSession))
      .mockResolvedValueOnce(response({ state: 'available', active_operations: [active], active_complete: true }))
      .mockResolvedValueOnce(response({ ...active, status: 'cancelled' }))
    const api = new StrategyApi(), signal = new AbortController().signal
    await api.bootstrap(signal); await api.session(signal)
    const recovered = await api.researchRecovery(selection, signal)
    expect(recovered.requests[0].selection?.request).toEqual(request)
    expect(await api.cancelRecoveryOperation(id, signal)).toEqual({ status: 'cancelled' })
    expect(fetch.mock.calls[2][0]).toBe('/api/v1/research/operations/status')
    expect(fetch.mock.calls[3]).toEqual([`/api/v1/research/operations/${id}/cancel`, expect.objectContaining({ method: 'POST', credentials: 'same-origin', headers: expect.objectContaining({ 'X-Strategy-CSRF': 'c'.repeat(64) }) })])
  })

  it('restores only matching identity and leaves another graph request untouched', () => {
    const active = { ...status, status: 'running', completed_run_ids: [] }
    const other = { ...active, operation_id: 'e'.repeat(64), plan: { ...status.plan, v2_graphs: [{ ...descriptor, graph_identifier: 'another.graph', experiment: { unsupported: true } }] } }
    const result = parseResearchRecovery({ active_operations: [other, active], active_complete: true }, selection)
    expect(result.complete).toBe(true); expect(result.requests).toHaveLength(1)
    expect(result.requests[0].operationId).toBe(id); expect(result.requests[0].selection?.request).toEqual(request)
  })

  it.each([
    { content_address: `sha256:${'e'.repeat(64)}` }, { request_id: 'invalid' },
    { dataset_as_of: '2026-02-31T00:00:00Z' }, { dataset_as_of: '2026-09-05T00:00:00.123Z' },
    { experiment: { ...experiment, seed: 1.5 } }, { experiment: { ...experiment, n_folds: 33 } },
    { experiment: { ...experiment, research_capital: 0 } }, { experiment: { ...experiment, hypothesis: '  ' } },
    { execution_policy: { risk: { risk_policy: ['none'], capital: 100000 } } },
  ])('keeps an unsupported matching active request visible instead of inventing absence', (change) => {
    const active = { ...status, status: 'running', completed_run_ids: [], plan: { ...status.plan, v2_graphs: [{ ...descriptor, ...change }] } }
    const recovered = parseResearchRecovery({ active_operations: [active], active_complete: true }, selection)
    expect(recovered.requests).toHaveLength(1)
    expect(recovered.requests[0]).toMatchObject({ operationId: id, selection: null, operation: null })
    expect(recovered.requests[0].reason).toMatch(/cannot be verified/)
  })

  it('refuses missing completeness, duplicate IDs and overflow marked complete', () => {
    const active = { ...status, status: 'pending', completed_run_ids: [] }
    expect(() => parseResearchRecovery({ active_operations: [] }, selection)).toThrow()
    expect(() => parseResearchRecovery({ active_operations: [active, active], active_complete: true }, selection)).toThrow()
    const overflow = Array.from({ length: 21 }, (_, index) => ({ ...active, operation_id: index.toString(16).padStart(64, '0') }))
    expect(() => parseResearchRecovery({ active_operations: overflow, active_complete: true }, selection)).toThrow()
    expect(parseResearchRecovery({ active_operations: overflow, active_complete: false }, selection).complete).toBe(false)
    expect(() => parseResearchRecovery({ active_operations: [...overflow, active], active_complete: false }, selection)).toThrow()
    expect(() => parseResearchRecovery({ active_operations: [{ ...active, status: ['pending'] }], active_complete: true }, selection)).toThrow()
  })

})


it('reads only valid saved graph input metadata before offering dataset bindings', () => {
  const base = { format_version: 2, graph_identifier: 'strategy.a', graph_version: 1, content_address: `sha256:${'b'.repeat(64)}`,
    document: { format_version: 2, strategy_id: 'strategy.a', metadata: { tags: [] }, graph_inputs: [
      { port_id: 'frame', direction: 'input', semantic_role: 'market_frame' }, { port_id: 'benchmark', direction: 'input', semantic_role: 'market_frame' },
    ] } }
  expect(parseSavedResearchPolicy(base, 'strategy.a', 1).inputs.map((input) => input.id)).toEqual(['benchmark', 'frame'])
  expect(parseSavedResearchPolicy({ ...base, document: { ...base.document, graph_inputs: [] } }, 'strategy.a', 1).inputs).toEqual([])
  for (const graph_inputs of [undefined, [base.document.graph_inputs[0], base.document.graph_inputs[0]], [{ ...base.document.graph_inputs[0], direction: 'output' }]]) {
    expect(() => parseSavedResearchPolicy({ ...base, document: { ...base.document, graph_inputs } }, 'strategy.a', 1)).toThrow()
  }
})

describe('settings-backed preparation and immutable recovery', () => {
  const values = { research_capital: 120000, seed: 3, min_trades: 12, n_folds: 5, min_positive_fold_frac: .6, risk_policy: 'none' as const }
  const uuid = '00000000-0000-4000-8000-000000000003'
  const workspace = { schema: 'research-settings-revision/1' as const, owner_id: 'owner.a', graph_identifier: null,
    revision: 1, expected_revision: 0, request_id: uuid, enabled: true, values, content_address: `sha256:${'1'.repeat(64)}` }
  const strategy = { ...workspace, graph_identifier: 'strategy.a', revision: 0, expected_revision: 0, request_id: null, values: {}, content_address: `sha256:${'2'.repeat(64)}` }
  const request = { ...values, research_capital: 130000, request_id: uuid, hypothesis: 'Settings-backed test', dataset_manifest_address: `sha256:${'a'.repeat(64)}`, dataset_as_of: '2026-09-05T00:00:00Z' }
  const selection = { projectId: 'project.a', graphId: 'strategy.a', version: 1, contentAddress: `sha256:${'b'.repeat(64)}`, request,
    settings: { workspace, strategy, runOverrides: { research_capital: 130000 } } }
  const snapshot = { schema: 'research-settings-snapshot/1', owner_id: 'owner.a', graph_identifier: 'strategy.a', workspace, strategy,
    run_overrides: selection.settings.runOverrides, values: { ...values, research_capital: 130000 },
    sources: { research_capital: 'run', seed: 'workspace', min_trades: 'workspace', n_folds: 'workspace', min_positive_fold_frac: 'workspace', risk_policy: 'workspace' }, content_address: `sha256:${'c'.repeat(64)}` }
  const id = 'd'.repeat(64)
  const { request_id, dataset_manifest_address, dataset_as_of, risk_policy, ...experiment } = request
  const descriptor = { owner_id: 'owner.a', project_id: 'project.a', graph_identifier: 'strategy.a', graph_version: 1,
    content_address: selection.contentAddress, request_id, dataset_manifest_address, dataset_as_of, experiment,
    execution_policy: { schema: 'v2-research-execution-policy/1', risk: { risk_policy, capital: request.research_capital, sizing_model: 'one_lot_or_cash_budget_v1', fill: 'existing-next-bar-open', overlay: { schema: 'v2-research-risk-policy/1', policy_id: 'none' } } }, settings_snapshot: snapshot }
  const active = { operation_id: id, trigger: 'v2_graph', status: 'running', stage: 'planning', error: null, cancel_requested_at: null, completed_run_ids: [],
    plan: { schema: 'v2-graph-research-operation/3', experiment_count: 1, v2_graphs: [descriptor] } }

  it('verifies percentage policy and restores a version 2 snapshot without changing legacy bytes', () => {
    const bands = { stop_loss_pct: .01, take_profit_pct: .02 }
    const workspace2 = { ...workspace, schema: 'research-settings-revision/2' as const, values: { ...values, ...bands } }
    const snapshot2 = { ...snapshot, schema: 'research-settings-snapshot/2', workspace: workspace2, values: { ...snapshot.values, ...bands }, sources: { ...snapshot.sources, stop_loss_pct: 'workspace', take_profit_pct: 'workspace' } }
    const selection2 = { ...selection, request: { ...request, ...bands }, settings: { ...selection.settings, workspace: workspace2 } }
    const protective_band = { schema: 'research-percentage-exit-policy/1', ...bands, basis: 'slipped-entry-fill', trigger: 'completed-close-after-entry-bar', fill: 'next-bar-open-adverse-slippage', intrabar: 'not-evaluated', precedence: 'stop-target-ratchet-strategy' }
    const descriptor2 = { ...descriptor, settings_snapshot: snapshot2, execution_policy: { ...descriptor.execution_policy, schema: 'v2-research-execution-policy/2', risk: { ...descriptor.execution_policy.risk, schema: 'research-risk-assumption/2', protective_band } } }
    const operation2 = { ...active, plan: { ...active.plan, v2_graphs: [descriptor2] } }
    expect(parsePreparedOperation(operation2, id, selection2).settingsSnapshotAddress).toBe(snapshot2.content_address)
    const recovered2 = parseResearchRecovery({ active_operations: [operation2], active_complete: true }, selection2).requests[0]
    expect(recovered2.selection?.request).toMatchObject(bands)
    for (const invalid of [1, -.01]) {
      const broken = { ...operation2, plan: { ...operation2.plan, v2_graphs: [{ ...descriptor2, settings_snapshot: { ...snapshot2, values: { ...snapshot2.values, stop_loss_pct: invalid } } }] } }
      expect(parseResearchRecovery({ active_operations: [broken], active_complete: true }, selection2).requests[0].selection).toBeNull()
    }
    for (const change of [{ stop_loss_pct: .02 }, { trigger: 'intrabar' }, { extra: true }]) {
      const malformed = { ...operation2, plan: { ...operation2.plan, v2_graphs: [{ ...descriptor2, execution_policy: { ...descriptor2.execution_policy, risk: { ...descriptor2.execution_policy.risk, protective_band: { ...protective_band, ...change } } } }] } }
      expect(() => parsePreparedOperation(malformed, id, selection2)).toThrow()
    }
    const malformed = { ...operation2, plan: { ...operation2.plan, v2_graphs: [{ ...descriptor2, settings_snapshot: { ...snapshot2, values: { ...snapshot2.values, unknown: 1 } } }] } }
    expect(() => parsePreparedOperation(malformed, id, selection2)).toThrow()
    expect(parsePreparedOperation(active, id, selection).settingsSnapshotAddress).toBe(snapshot.content_address)
  })

  it('preserves /3 search snapshots and rejects downgrade or altered slippage', () => {
    const optimization = {schema:'canonical-local-development-search/1' as const,enabled:true,axes:[{node_id:'rising',parameter_id:'window',step:'1',minimum:'1',maximum:'3'}]}
    const bands={stop_loss_pct:.01,take_profit_pct:0}
    const workspace3={...workspace,schema:'research-settings-revision/3' as const,values:{...values,...bands,optimization:disabledOptimization()}}
    const strategy3={...workspace,graph_identifier:'strategy.a',schema:'research-settings-revision/3' as const,values:{optimization}}
    const snapshot3={...snapshot,schema:'research-settings-snapshot/3',workspace:workspace3,strategy:strategy3,values:{...snapshot.values,...bands,optimization},sources:{...snapshot.sources,stop_loss_pct:'workspace',take_profit_pct:'workspace',optimization:'strategy'}}
    const selection3={...selection,request:{...request,...bands,optimization},settings:{...selection.settings,workspace:workspace3,strategy:strategy3}}
    const protective_band={schema:'research-percentage-exit-policy/1',...bands,basis:'slipped-entry-fill',trigger:'completed-close-after-entry-bar',fill:'next-bar-open-adverse-slippage',intrabar:'not-evaluated',precedence:'stop-target-ratchet-strategy'}
    const descriptor3={...descriptor,settings_snapshot:snapshot3,execution_policy:{...descriptor.execution_policy,slippage:{schema:'research-slippage-assumption/1',basis_points:5,challenge_multiplier:2,application:'existing-research-kernel'},schema:'v2-research-execution-policy/2',risk:{...descriptor.execution_policy.risk,schema:'research-risk-assumption/2',protective_band}}}
    const operation3={...active,plan:{...active.plan,v2_graphs:[descriptor3]}}
    Object.freeze(snapshot3.run_overrides)
    expect(parsePreparedOperation(operation3,id,selection3).settingsSnapshotAddress).toBe(snapshot3.content_address)
    expect(parseResearchRecovery({active_operations:[operation3],active_complete:true},selection3).requests[0].selection?.request.optimization).toEqual(optimization)
    for(const change of [{schema:'research-settings-snapshot/2'},{values:{...snapshot3.values,optimization:disabledOptimization()}}]) {
      expect(()=>parsePreparedOperation({...operation3,plan:{...operation3.plan,v2_graphs:[{...descriptor3,settings_snapshot:{...snapshot3,...change}}]}},id,selection3)).toThrow()
    }
    expect(()=>parsePreparedOperation({...operation3,plan:{...operation3.plan,v2_graphs:[{...descriptor3,execution_policy:{...descriptor3.execution_policy,slippage:{...descriptor3.execution_policy.slippage,basis_points:0}}}]}},id,selection3)).toThrow()
    expect(parseWorkspaceResearchSettings({workspace,fixed_assumptions:{},supported_values_schema:'research-values/3'}).values).toEqual(values)
    expect(()=>parseResearchSettingsRevision({...workspace3,values:{...workspace3.values,optimization}},null)).toThrow()
  })

  it('advertises new percentage controls without rewriting a legacy revision and rejects invalid fractions', () => {
    const result = parseWorkspaceResearchSettings({ workspace, fixed_assumptions: {}, supported_values_schema: 'research-values/2' })
    expect(result.supportedValuesSchema).toBe('research-values/2')
    expect(result.values).toEqual(values)
    expect(() => parseWorkspaceResearchSettings({ workspace, fixed_assumptions: {}, supported_values_schema: 'other' })).toThrow()
    for (const stop_loss_pct of [-.01, 1, Infinity, null, '1']) {
      expect(() => parseResearchSettingsRevision({ ...workspace, schema: 'research-settings-revision/2', values: { ...values, stop_loss_pct, take_profit_pct: .02 } }, null)).toThrow()
    }
    expect(() => parseResearchSettingsRevision({ ...workspace, values: { ...values, stop_loss_pct: 0 } }, null)).toThrow()
    expect(() => parseResearchSettingsRevision({ ...workspace, schema: 'research-settings-revision/2', values: { ...values, stop_loss_pct: 0, take_profit_pct: 0, unknown: 1 } }, null)).toThrow()
  })

  it('requires settings identity for a new preparation request', () => {
    expect(() => settingsPreparation({ ...selection, settings: undefined })).toThrow()
  })

  it('posts selected revisions and sparse overrides through CSRF without a /2 fallback', async () => {
    const receipt = { operation_id: id, request_id: uuid, status: 'pending', status_url: `/api/research/operations/${id}`, cancel_url: `/api/research/operations/${id}/cancel` }
    const fetch = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(response(release)).mockResolvedValueOnce(response(browserSession))
      .mockResolvedValueOnce(response(receipt, 202))
    const api = new StrategyApi(), signal = new AbortController().signal
    await api.bootstrap(signal); await api.session(signal)
    const body = { request_id, dataset_manifest_address, dataset_as_of, hypothesis: request.hypothesis,
      expected_workspace_revision: 1, expected_strategy_revision: 0, run_overrides: { research_capital: 130000 } }
    await api.prepareResearchFromSettings('project.a', 'strategy.a', 1, body, signal)
    expect(fetch.mock.calls[2][0]).toBe('/api/v1/ir/projects/project.a/graphs/strategy.a/versions/1/research-preparations/from-settings')
    expect(JSON.parse(String(fetch.mock.calls[2][1]?.body))).toEqual(body)
    expect(fetch.mock.calls[2][1]).toMatchObject({ method: 'POST', credentials: 'same-origin', headers: { 'X-Strategy-CSRF': 'c'.repeat(64) } })
  })

  it('restores /3 from its snapshot and pins its address during subsequent polling', () => {
    expect(parsePreparedOperation(active, id, selection).status).toBe('running')
    const recovered = parseResearchRecovery({ active_operations: [active], active_complete: true }, selection).requests[0]
    expect(recovered.selection?.request).toEqual(request)
    expect(recovered.selection?.settings?.snapshotAddress).toBe(snapshot.content_address)
    const changed = { ...active, plan: { ...active.plan, v2_graphs: [{ ...descriptor, settings_snapshot: { ...snapshot, content_address: `sha256:${'f'.repeat(64)}` } }] } }
    expect(() => parsePreparedOperation(changed, id, recovered.selection!)).toThrow()
  })

  it.each([
    { owner_id: 'foreign' }, { graph_identifier: 'other' }, { extra: true },
    { workspace: { ...workspace, content_address: `sha256:${'f'.repeat(64)}` } },
    { strategy: { ...strategy, enabled: false } },
    { run_overrides: { research_capital: 140000 } },
    { values: { ...snapshot.values, research_capital: 140000 } },
    { sources: { ...snapshot.sources, research_capital: 'workspace' } },
    { sources: { ...snapshot.sources, extra: 'run' } },
    { content_address: 'invalid' },
  ])('rejects mismatched settings snapshot before exposing a run', (change) => {
    const changed = { ...active, plan: { ...active.plan, v2_graphs: [{ ...descriptor, settings_snapshot: { ...snapshot, ...change } }] } }
    expect(() => parsePreparedOperation(changed, id, selection)).toThrow()
  })

  it('keeps a malformed /3 active request visible and refuses schema downgrade', () => {
    const changed = { ...active, plan: { ...active.plan, v2_graphs: [{ ...descriptor, settings_snapshot: { ...snapshot, run_overrides: { unknown: true } } }] } }
    expect(parseResearchRecovery({ active_operations: [changed], active_complete: true }, selection).requests[0].selection).toBeNull()
    expect(() => parsePreparedOperation({ ...active, plan: { ...active.plan, schema: 'v2-graph-research-operation/2' } }, id, selection)).toThrow()
  })

  it.each([true, false])('verifies strategy inheritance when overrides enabled=%s', (enabled) => {
    const nextStrategy = { ...strategy, revision: 1, request_id: uuid, enabled, values: { seed: 8 } }
    const seed = enabled ? 8 : values.seed
    const nextSelection = { ...selection, request: { ...request, seed }, settings: { ...selection.settings, strategy: nextStrategy } }
    const nextSnapshot = { ...snapshot, strategy: nextStrategy, values: { ...snapshot.values, seed }, sources: { ...snapshot.sources, seed: enabled ? 'strategy' : 'workspace' } }
    const next = { ...active, plan: { ...active.plan, v2_graphs: [{ ...descriptor, experiment: { ...experiment, seed }, settings_snapshot: nextSnapshot }] } }
    expect(parsePreparedOperation(next, id, nextSelection).settingsSnapshotAddress).toBe(snapshot.content_address)
  })


  it.each([
    { sizing_model: 'fixed_unit_v1' }, { fill: 'next-bar-open-reversal/1' },
    { overlay: { schema: 'v2-research-risk-policy/1', policy_id: 'none', replay_policy: 'pine-reversal-fixed-unit/1' } },
    { overlay: { schema: 'v2-research-risk-policy/2', policy_id: 'none' } },
  ])('rejects a changed execution policy on the recorded /3 setup', (change) => {
    const next = { ...active, plan: { ...active.plan, v2_graphs: [{ ...descriptor,
      execution_policy: { ...descriptor.execution_policy, risk: { ...descriptor.execution_policy.risk, ...change } } }] } }
    expect(() => parsePreparedOperation(next, id, selection)).toThrow()
  })


  it('verifies the explicit fixed-unit reversal snapshot and refuses it under legacy /2', () => {
    const riskPolicy = 'pine-v4-reversal/1' as const
    const runOverrides = { ...selection.settings.runOverrides, risk_policy: riskPolicy }
    const nextSelection = { ...selection, request: { ...request, risk_policy: riskPolicy }, settings: { ...selection.settings, runOverrides } }
    const nextSnapshot = { ...snapshot, run_overrides: runOverrides, values: { ...snapshot.values, risk_policy: riskPolicy }, sources: { ...snapshot.sources, risk_policy: 'run' } }
    const policy = { ...descriptor.execution_policy, risk: { ...descriptor.execution_policy.risk, risk_policy: riskPolicy,
      sizing_model: 'fixed_unit_v1', fill: 'next-bar-open-reversal/1', overlay: { schema: 'v2-research-risk-policy/2', policy_id: riskPolicy, replay_policy: 'pine-reversal-fixed-unit/1' } } }
    const nextDescriptor = { ...descriptor, execution_policy: policy, settings_snapshot: nextSnapshot }
    const next = { ...active, plan: { ...active.plan, v2_graphs: [nextDescriptor] } }
    expect(parsePreparedOperation(next, id, nextSelection).status).toBe('running')
    expect(parseResearchRecovery({ active_operations: [next], active_complete: true }, selection).requests[0].selection?.request.risk_policy).toBe(riskPolicy)
    for (const change of [{ sizing_model: 'one_lot_or_cash_budget_v1' }, { fill: 'existing-next-bar-open' },
      { overlay: { ...policy.risk.overlay, replay_policy: 'unknown' } }]) {
      const wrong = { ...next, plan: { ...next.plan, v2_graphs: [{ ...nextDescriptor, execution_policy: { ...policy, risk: { ...policy.risk, ...change } } }] } }
      expect(() => parsePreparedOperation(wrong, id, nextSelection)).toThrow()
    }
    const legacy = { ...next, plan: { ...next.plan, schema: 'v2-graph-research-operation/2' } }
    expect(() => parsePreparedOperation(legacy, id, { ...nextSelection, settings: undefined })).toThrow()
  })

  const inputDatasets = [
    { graph_input_id: 'benchmark', dataset_manifest_address: `sha256:${'e'.repeat(64)}` },
    { graph_input_id: 'frame', dataset_manifest_address: request.dataset_manifest_address },
  ]
  const { dataset_manifest_address: _scalarRequest, ...inputRequestValues } = request
  const inputRequest = { ...inputRequestValues, input_datasets: inputDatasets, primary_input: 'frame' }
  const inputSelection = { ...selection, request: inputRequest, inputIds: ['benchmark', 'frame'] }
  const { dataset_manifest_address: _scalarDescriptor, ...inputDescriptorValues } = descriptor
  const inputDescriptor = { ...inputDescriptorValues, input_datasets: inputDatasets, primary_input: 'frame' }
  const inputActive = { ...active, plan: { ...active.plan, schema: 'v2-graph-research-operation/4', v2_graphs: [inputDescriptor] } }

  it('posts /4 exact input bindings and revisions, then recovers all bindings without a scalar fallback', async () => {
    const nextReceipt = { operation_id: id, request_id: uuid, status: 'pending', status_url: `/api/research/operations/${id}`, cancel_url: `/api/research/operations/${id}/cancel` }
    const fetch = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(response(release)).mockResolvedValueOnce(response(browserSession))
      .mockResolvedValueOnce(response(nextReceipt, 202)).mockResolvedValueOnce(response(inputActive))
    const api = new StrategyApi(), signal = new AbortController().signal
    await api.bootstrap(signal); await api.session(signal)
    const body = inputSettingsPreparation(inputSelection)
    await api.prepareResearchFromInputs('project.a', 'strategy.a', 1, body, signal)
    expect(fetch.mock.calls[2][0]).toBe('/api/v1/ir/projects/project.a/graphs/strategy.a/versions/1/research-preparations/from-inputs')
    expect(JSON.parse(String(fetch.mock.calls[2][1]?.body))).toEqual({ request_id: uuid, input_datasets: inputDatasets, primary_input: 'frame', dataset_as_of,
      hypothesis: request.hypothesis, expected_workspace_revision: 1, expected_strategy_revision: 0, run_overrides: { research_capital: 130000 } })
    expect(fetch.mock.calls[2][1]).toMatchObject({ method: 'POST', credentials: 'same-origin', headers: { 'X-Strategy-CSRF': 'c'.repeat(64) } })
    expect(await api.researchOperation(id, inputSelection, signal)).toMatchObject({ status: 'running', settingsSnapshotAddress: snapshot.content_address })
    const recovered = parseResearchRecovery({ active_operations: [inputActive], active_complete: true }, inputSelection).requests[0]
    expect(recovered.selection?.request).toEqual(inputRequest)
    expect(recovered.selection?.settings?.snapshotAddress).toBe(snapshot.content_address)
    expect(() => settingsPreparation(inputSelection)).toThrow()
    expect(() => inputSettingsPreparation(selection)).toThrow()
    expect(() => inputSettingsPreparation({ ...inputSelection, settings: undefined })).toThrow()
    expect(() => parsePreparedOperation(inputActive, id, { ...inputSelection, settings: undefined })).toThrow()
  })

  it.each([
    { input_datasets: [...inputDatasets].reverse() },
    { input_datasets: inputDatasets.slice(0, 1) },
    { input_datasets: [inputDatasets[0], inputDatasets[0]] },
    { input_datasets: inputDatasets.map((item) => ({ ...item, dataset_manifest_address: request.dataset_manifest_address })) },
    { input_datasets: [{ ...inputDatasets[0], dataset_manifest_address: `sha256:${'f'.repeat(64)}` }, inputDatasets[1]] },
    { input_datasets: [{ ...inputDatasets[0], extra: true }, inputDatasets[1]] },
    { primary_input: 'benchmark' }, { primary_input: 'missing' },
    { dataset_as_of: '2026-09-04T00:00:00Z' }, { dataset_as_of: '2026-09-05T00:00:00.1Z' },
    { dataset_manifest_address: request.dataset_manifest_address },
    { settings_snapshot: { ...snapshot, owner_id: 'other-owner' } },
    { execution_policy: { ...descriptor.execution_policy, risk: { ...descriptor.execution_policy.risk, capital: 42 } } },
  ])('refuses /4 input or snapshot substitution before exposing results %j', (change) => {
    const changed = { ...inputActive, plan: { ...inputActive.plan, v2_graphs: [{ ...inputDescriptor, ...change }] } }
    expect(() => parsePreparedOperation(changed, id, inputSelection)).toThrow()
  })

  it.each([
    { input_datasets: [...inputDatasets].reverse() },
    { input_datasets: [inputDatasets[0], inputDatasets[0]] },
    { input_datasets: inputDatasets.map((item) => ({ ...item, dataset_manifest_address: request.dataset_manifest_address })) },
    { primary_input: 'missing' }, { dataset_as_of: '2026-02-30T00:00:00Z' },
    { dataset_as_of: '2026-09-05T00:00:00.1Z' }, { dataset_as_of: '2026-09-05T00:00:00+05:30' },
  ])('rejects invalid /4 request identities before transport %j', (change) => {
    expect(() => inputSettingsPreparation({ ...inputSelection, request: { ...inputRequest, ...change } })).toThrow()
  })

  it('keeps unsupported /4 recovery visible and refuses /3 downgrade or different saved ports', () => {
    expect(() => parsePreparedOperation({ ...inputActive, plan: { ...inputActive.plan, schema: 'v2-graph-research-operation/3' } }, id, inputSelection)).toThrow()
    expect(parseResearchRecovery({ active_operations: [inputActive], active_complete: true }, { ...inputSelection, inputIds: ['other', 'frame'] }).requests[0].selection).toBeNull()
    expect(parseResearchRecovery({ active_operations: [inputActive], active_complete: true }, selection).requests[0].selection).toBeNull()
    const wrong = { ...inputActive, plan: { ...inputActive.plan, v2_graphs: [{ ...inputDescriptor, input_datasets: inputDatasets.slice(0, 1) }] } }
    expect(parseResearchRecovery({ active_operations: [wrong], active_complete: true }, inputSelection).requests[0].selection).toBeNull()
  })

})


describe('research settings transport and save receipts', () => {
  const values = { research_capital: 100000, seed: 0, min_trades: 10, n_folds: 4, min_positive_fold_frac: .6, risk_policy: 'none' as const }
  const requestId = '00000000-0000-4000-8000-000000000001'
  const workspaceRequestId = '00000000-0000-4000-8000-000000000002'
  const disableRequestId = '00000000-0000-4000-8000-000000000003'
  const workspace = { schema: 'research-settings-revision/1' as const, owner_id: 'owner.a', graph_identifier: null, revision: 0, expected_revision: 0,
    request_id: null, enabled: true, values, content_address: `sha256:${'1'.repeat(64)}` }
  const strategy = { ...workspace, graph_identifier: 'strategy.a', values: {} }

  it('reads both scopes and saves through the existing CSRF transport', async () => {
    const saved = { ...strategy, revision: 1, request_id: requestId, values: { n_folds: 8 } }
    const fetch = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(response(release)).mockResolvedValueOnce(response(browserSession))
      .mockResolvedValueOnce(response({ workspace, fixed_assumptions: {} }))
      .mockResolvedValueOnce(response({ workspace, strategy, values, sources: Object.fromEntries(Object.keys(values).map((key) => [key, 'workspace'])), fixed_assumptions: {} }))
      .mockResolvedValueOnce(response(saved)).mockResolvedValueOnce(response({ ...workspace, revision: 1, request_id: workspaceRequestId }))
      .mockResolvedValueOnce(response({ ...saved, revision: 2, expected_revision: 1, request_id: disableRequestId, enabled: false }))
    const api = new StrategyApi(), signal = new AbortController().signal
    await api.bootstrap(signal); await api.session(signal)
    expect((await api.workspaceResearchSettings(signal)).revision).toBe(0)
    expect((await api.strategyResearchSettings('project.a', 'strategy.a', signal)).strategy.values).toEqual({})
    await api.saveResearchSettings({ request_id: requestId, expected_revision: 0, values: { n_folds: 8 } }, signal, { projectId: 'project.a', graphId: 'strategy.a', enabled: true })
    await api.saveResearchSettings({ request_id: workspaceRequestId, expected_revision: 0, values }, signal)
    expect(fetch.mock.calls[2][0]).toBe('/api/v1/research-settings')
    expect(fetch.mock.calls[3][0]).toBe('/api/v1/ir/projects/project.a/graphs/strategy.a/research-settings')
    expect(fetch.mock.calls[4][1]).toMatchObject({ method: 'PUT', credentials: 'same-origin', headers: { 'X-Strategy-CSRF': 'c'.repeat(64) } })
    expect(JSON.parse(String(fetch.mock.calls[4][1]?.body))).toEqual({ request_id: requestId, expected_revision: 0, values: { n_folds: 8 }, enabled: true })
    expect(JSON.parse(String(fetch.mock.calls[5][1]?.body))).not.toHaveProperty('enabled')
    await api.saveResearchSettings({ request_id: disableRequestId, expected_revision: 1, values: { n_folds: 8 } }, signal, { projectId: 'project.a', graphId: 'strategy.a', enabled: false })
    expect(JSON.parse(String(fetch.mock.calls[6][1]?.body))).toMatchObject({ expected_revision: 1, values: { n_folds: 8 }, enabled: false })
  })

  it.each([
    { revision: 2, expected_revision: 1 }, { enabled: false }, { values: {} }, { values: { n_folds: 7 } }, { values: { n_folds: 8, seed: 0 } },
  ])('refuses a saved revision that does not match the requested change', async (change) => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(response(release)).mockResolvedValueOnce(response(browserSession))
      .mockResolvedValueOnce(response({ ...strategy, revision: 1, request_id: requestId, values: { n_folds: 8 }, ...change }))
    const api = new StrategyApi(), signal = new AbortController().signal
    await api.bootstrap(signal); await api.session(signal)
    await expect(api.saveResearchSettings({ request_id: requestId, expected_revision: 0, values: { n_folds: 8 } }, signal, { projectId: 'project.a', graphId: 'strategy.a', enabled: true })).rejects.toThrow()
  })
})


it.each([undefined, `sha256:${'a'.repeat(64)}`])('sends a registry target only for an explicit publication request: %s', async (target) => {
  const fetch = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(response(release)).mockResolvedValueOnce(response(browserSession))
    .mockResolvedValueOnce(response({ detail: { code: 'STRATEGY_LIBRARY_CHANGED', message: 'Review current components.' } }, 409))
  const api = new StrategyApi(), signal = new AbortController().signal
  await api.bootstrap(signal); await api.session(signal)
  await expect(api.publishV2('project.a', 'graph.a', 3, 1, signal, target)).rejects.toMatchObject({ kind: 'server', envelope: { code: 'STRATEGY_LIBRARY_CHANGED' } })
  expect(JSON.parse(fetch.mock.calls[2][1]!.body as string)).toEqual({ format_version: 2, base_revision: 3, expected_current_version: 1,
    ...(target === undefined ? {} : { target_registry_snapshot_address: target }) })
  expect(fetch.mock.calls[2][0]).toBe('/api/v1/ir/projects/project.a/graphs/graph.a/v2/publish')
})

it('rejects an invalid component target before sending a publication', async () => {
  const fetch = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(response(release)).mockResolvedValueOnce(response(browserSession))
  const api = new StrategyApi(), signal = new AbortController().signal
  await api.bootstrap(signal); await api.session(signal)
  await expect(api.publishV2('project.a', 'graph.a', 3, 1, signal, 'not-an-address')).rejects.toMatchObject({ kind: 'input' })
  expect(fetch).toHaveBeenCalledTimes(2)
})

describe('paper portfolio contract', () => {
  const portfolio = { schema: 'paper-portfolio/1', untraded_strategies: [], currency: 'INR', as_of: '2026-09-05T12:00:00Z',
    realized_pnl: -30, closed_trades: 1, points: [{ timestamp: '2026-09-04', realized_pnl: -30 }],
    strategies: [{ strategy_key: null, strategy_version: null, display_name: 'Unattributed strategy', realized_pnl: -30, closed_trades: 1 }] }
  it('loads owner paper history through the authenticated transport', async () => {
    const fetch = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(response(release)).mockResolvedValueOnce(response(portfolio))
    const api = new StrategyApi()
    await api.bootstrap(new AbortController().signal)
    expect(await api.paperPortfolio(new AbortController().signal)).toMatchObject({ realized_pnl: -30, strategies: [{ strategy_key: null }] })
    expect(fetch).toHaveBeenLastCalledWith('/api/v1/paper-portfolio', expect.objectContaining({ credentials: 'same-origin', cache: 'no-store' }))
  })
  it.each([
    { currency: 'USD' }, { realized_pnl: '30' }, { closed_trades: -1 }, { as_of: 'bad date' },
    { as_of: '2026-09-05T12:00:00' }, { as_of: '2026-02-30T12:00:00Z' },
    { as_of: '2026-09-05T24:00:00Z' },
    { points: [{ timestamp: '2026-02-30', realized_pnl: -30 }] },
    { points: [{ timestamp: '2026-09-04T00:00:00Z', realized_pnl: -30 }] },
    { realized_pnl: 200 }, { closed_trades: 2 },
    { points: [] },
    { strategies: [{ strategy_key: null, strategy_version: null, display_name: 'Unknown', realized_pnl: -20, closed_trades: 1 }] },
    { points: [{ timestamp: 'invalid', realized_pnl: 0 }] },
    { points: [{ timestamp: '2026-09-03', realized_pnl: 'not a number' }, { timestamp: '2026-09-04', realized_pnl: -30 }] },
    { points: [{ timestamp: '2026-09-04', realized_pnl: 0 }, { timestamp: '2026-09-03', realized_pnl: -30 }] },
    { strategies: [{ strategy_key: '', strategy_version: null, display_name: 'Unknown', realized_pnl: 0, closed_trades: 0 }] },
  ])('refuses malformed portfolio records %j', async (change) => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(response(release)).mockResolvedValueOnce(response({ ...portfolio, ...change }))
    const api = new StrategyApi()
    await api.bootstrap(new AbortController().signal)
    await expect(api.paperPortfolio(new AbortController().signal)).rejects.toThrow()
  })
})


it('preserves real leap days, explicit update offsets and separately rounded strategy totals', () => {
  const portfolio = { schema: 'paper-portfolio/1', untraded_strategies: [], currency: 'INR', as_of: '2024-03-01T00:30:00.123456+05:30',
    realized_pnl: 0.01, closed_trades: 2, points: [{ timestamp: '2024-02-29', realized_pnl: 0.01 }],
    strategies: ['A', 'B'].map((strategy_key) => ({ strategy_key, strategy_version: '1', display_name: strategy_key, realized_pnl: 0.01, closed_trades: 1 })) }
  expect(parsePaperPortfolio(portfolio)).toMatchObject({ realized_pnl: 0.01, points: [{ timestamp: '2024-02-29' }] })
  expect(() => parsePaperPortfolio({ ...portfolio, strategies: portfolio.strategies.map((row) => ({ ...row, realized_pnl: 0.02 })) })).toThrow()
})

it('rejects duplicate or overlapping untraded portfolio strategies', () => {
  const row = { strategy_key: 'ir.test', strategy_version: '1', display_name: 'Test' }
  const base = { schema: 'paper-portfolio/1', currency: 'INR', as_of: '2026-09-05T12:00:00Z', points: [], strategies: [], untraded_strategies: [row], realized_pnl: 0, closed_trades: 0 }
  expect(parsePaperPortfolio(base).untraded_strategies).toEqual([row])
  expect(() => parsePaperPortfolio({ ...base, untraded_strategies: [row, row] })).toThrow()
  const traded = { ...row, realized_pnl: 0, closed_trades: 1 }
  expect(() => parsePaperPortfolio({ ...base, strategies: [traded], closed_trades: 1 })).toThrow()
  expect(() => parsePaperPortfolio({ ...base, strategies: [traded, traded], untraded_strategies: [], closed_trades: 2 })).toThrow()
})

describe('static watchlist API and revision identity', () => {
  const projectId = 'project.static', id = 'scope.api', member = `sha256:${'1'.repeat(64)}`
  const digest = (value: Record<string, unknown>) => `sha256:${createHash('sha256').update(JSON.stringify(Object.fromEntries(Object.entries(value).sort(([a], [b]) => a < b ? -1 : 1)))).digest('hex')}`
  function record(version = 1, predecessor: string | null = null) {
    const snapshot = { schema: 'static-instrument-scope/1', owner_id: browserSession.organization_id, project_id: projectId, scope_id: id, revision: version, predecessor, members: [member] }
    return { scope_id: id, name: '研究 list', status: 'active', current_revision: version, address: digest(snapshot), membership_address: digest({ schema: 'static-instrument-membership/1', members: [member] }), snapshot, member_labels: [{ instrument_address: member, display_name: null }] }
  }
  const first = record(), second = record(2, first.address)
  const enabled = structuredClone(release)
  Object.assign(enabled.capabilities.static_watchlists, { state: 'ENABLED_WITH_LIMIT', ui_navigation: true })
  beforeEach(() => vi.stubGlobal('crypto', webcrypto))
  afterEach(() => vi.unstubAllGlobals())

  it('uses owned versioned endpoints and CSRF for create, revise and archive without execution fields', async () => {
    const fetch = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(response(enabled)).mockResolvedValueOnce(response(browserSession))
      .mockResolvedValueOnce(response(first, 201)).mockResolvedValueOnce(response(first))
      .mockResolvedValueOnce(response(second, 201)).mockResolvedValueOnce(response({ ...second, status: 'archived' }))
      .mockResolvedValueOnce(response({ items: [{ ...second, status: 'archived' }], next_cursor: null }))
    const api = new StrategyApi(), signal = new AbortController().signal
    await api.bootstrap(signal); await api.session(signal)
    const draft = { name: first.name, members: [member] }
    expect(await api.createStaticScope(projectId, id, draft, signal)).toMatchObject({ address: first.address })
    expect(await api.staticScope(projectId, id, 1, signal)).toMatchObject({ snapshot: { revision: 1 } })
    expect(await api.reviseStaticScope(projectId, id, 1, draft, signal)).toMatchObject({ address: second.address })
    expect(await api.archiveStaticScope(projectId, id, 2, signal)).toMatchObject({ status: 'archived' })
    expect((await api.staticScopes(projectId, null, true, signal)).items).toHaveLength(1)
    expect(fetch.mock.calls.slice(2).map((call) => call[0])).toEqual([
      `/api/v1/ir/projects/${projectId}/static-scopes`, `/api/v1/ir/projects/${projectId}/static-scopes/${id}/revisions/1`,
      `/api/v1/ir/projects/${projectId}/static-scopes/${id}/revisions`, `/api/v1/ir/projects/${projectId}/static-scopes/${id}/archive`,
      `/api/v1/ir/projects/${projectId}/static-scopes?limit=50&include_archived=true`,
    ])
    expect(JSON.parse(String(fetch.mock.calls[2][1]?.body))).toEqual({ scope_id: id, ...draft })
    expect(JSON.parse(String(fetch.mock.calls[4][1]?.body))).toEqual({ expected_revision: 1, ...draft })
    expect(JSON.parse(String(fetch.mock.calls[5][1]?.body))).toEqual({ expected_revision: 2 })
    for (const index of [2, 4, 5]) expect(fetch.mock.calls[index][1]).toMatchObject({ method: 'POST', credentials: 'same-origin', headers: { 'X-Strategy-CSRF': 'c'.repeat(64) } })
  })
  it('refuses blocked static access before a scope request is sent', async () => {
    const fetch = vi.spyOn(globalThis, 'fetch').mockResolvedValue(response(release))
    const api = new StrategyApi(), signal = new AbortController().signal
    await api.bootstrap(signal)
    await expect(api.staticScopes(projectId, null, false, signal)).rejects.toMatchObject({ kind: 'manifest' })
    await expect(api.createStaticScope(projectId, id, { name: 'x', members: [member] }, signal)).rejects.toMatchObject({ kind: 'manifest' })
    expect(fetch).toHaveBeenCalledOnce()
  })
  it.each([
    { address: `sha256:${'f'.repeat(64)}` }, { membership_address: `sha256:${'f'.repeat(64)}` },
    { scope_id: 'scope.other' }, { status: 'deleted' }, { current_revision: 0 }, { extra: true },
    { snapshot: { ...first.snapshot, project_id: 'project.foreign' } },
    { snapshot: { ...first.snapshot, schema: 'unknown' } },
    { snapshot: { ...first.snapshot, predecessor: first.address } },
    { snapshot: { ...first.snapshot, members: [member, member] } },
    { snapshot: { ...first.snapshot, members: [] } },
    { snapshot: { ...first.snapshot, members: [`sha256:${'2'.repeat(64)}`, member] } },
  ])('rejects malformed or substituted static revision identity %j', async (change) => {
    await expect(parseStaticScope({ ...first, ...change }, projectId, id)).rejects.toThrow()
  })
  it('checks valid-but-different scope IDs and rejects oversized canonical membership', async () => {
    expect(first.address).toBe('sha256:c4ea75cd3160b6f1ad6962bcc22e4663b6cb21c7f0616d94776370b8dbda750f')
    const foreignSnapshot = { ...first.snapshot, scope_id: 'scope.other' }
    await expect(parseStaticScope({ ...first, scope_id: 'scope.other', snapshot: foreignSnapshot, address: digest(foreignSnapshot) }, projectId, id)).rejects.toThrow()
    const wideMembers = Array.from({ length: 33 }, (_, index) => `sha256:${index.toString(16).padStart(64, '0')}`)
    const wide = { ...first.snapshot, members: wideMembers }
    await expect(parseStaticScope({ ...first, snapshot: wide, address: digest(wide), membership_address: digest({ schema: 'static-instrument-membership/1', members: wideMembers }) }, projectId, id)).rejects.toThrow()
  })
  it('reads an exact historical revision without mistaking the current head for it', async () => {
    const history = { ...first, name: 'Current display name', current_revision: 2 }
    expect(await parseStaticScope(history, projectId, id, 1)).toMatchObject({ current_revision: 2, snapshot: { revision: 1 }, address: first.address })
    await expect(parseStaticScope(history, projectId, id)).rejects.toThrow()
    await expect(parseStaticScope(first, projectId, id, 2)).rejects.toThrow()
    await expect(parseStaticScopePage({ items: [first, first], next_cursor: null }, projectId, null)).rejects.toThrow()
    await expect(parseStaticScopePage({ items: [first], next_cursor: id }, projectId, null)).rejects.toThrow()
    await expect(parseStaticScopePage({ items: [first], next_cursor: null }, projectId, id)).rejects.toThrow()
    expect(await parseStaticScopePage({ items: [], next_cursor: null }, projectId, null)).toEqual({ items: [], next_cursor: null })
  })
  it('retains structured scope conflicts for explicit readback recovery', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(response(enabled)).mockResolvedValueOnce(response(browserSession))
      .mockResolvedValueOnce(response({ detail: { code: 'STATIC_SCOPE_CONFLICT', message: 'Expected revision conflict' } }, 409))
    const api = new StrategyApi(), signal = new AbortController().signal
    await api.bootstrap(signal); await api.session(signal)
    await expect(api.reviseStaticScope(projectId, id, 1, { name: 'x', members: [member] }, signal)).rejects.toMatchObject({ envelope: { code: 'STATIC_SCOPE_CONFLICT' } })
  })
  it('does not release a parsed static record after session generation changes during hashing', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(response(enabled)).mockResolvedValueOnce(response(first))
    const api = new StrategyApi(), signal = new AbortController().signal
    await api.bootstrap(signal)
    let finish!: () => void
    const gate = new Promise<void>((resolve) => { finish = resolve })
    const original = webcrypto.subtle.digest.bind(webcrypto.subtle)
    const digestSpy = vi.spyOn(webcrypto.subtle, 'digest').mockImplementation(async (...args) => { const value = await original(...args); await gate; return value })
    const loading = api.staticScope(projectId, id, null, signal)
    await vi.waitFor(() => expect(digestSpy).toHaveBeenCalledTimes(2))
    api.recheck(); finish()
    await expect(loading).rejects.toMatchObject({ name: 'AbortError' })
  })
})

it.each([undefined, null, 'RELIANCE · XNSE · EQUITY SPOT'])('accepts the backward-compatible dataset display name %s', async (displayName) => {
  const row = { manifest_address: `sha256:${'a'.repeat(64)}`, instrument_address: `sha256:${'1'.repeat(64)}`, canonical_instrument_label: 'XNSE · EQUITY SPOT · 111111111111',
    asset_class: 'EQUITY', contract_kind: 'SPOT', interval: '1d', event_start: '2025-01-01T00:00:00Z', event_end: '2025-12-31T00:00:00Z', availability_end: '2026-01-01T00:00:00Z', as_of: '2026-01-02T00:00:00Z', bar_count: 248,
    fields: ['OPEN', 'HIGH', 'LOW', 'CLOSE'], provider_evidence_state: 'VERIFIED_REFERENCES_PRESENT', market_truth_state: 'VERIFIED_REFERENCES_PRESENT', gaps: [], backtest_eligibility: 'ELIGIBLE_Q03', refusal_code: null,
    ...(displayName === undefined ? {} : { instrument_display_name: displayName }) }
  vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(response(release)).mockResolvedValueOnce(response({ schema: 'strategy-os-canonical-dataset-index/1', project_id: 'project.a', items: [row], next_cursor: null }))
  const api = new StrategyApi(), signal = new AbortController().signal
  await api.bootstrap(signal)
  expect((await api.researchDatasets('project.a', signal))[0].instrument_display_name).toBe(displayName)
})


describe('account entry limit boundary', () => {
  const rows = accountRiskFields.map(({ key }) => ({ key, type: 'float', default: 0, value: 1000, overridden: true, choices: null }))
  it('decodes only the three account limits and rejects missing, duplicate or invalid values', () => {
    expect(parseAccountRiskSettings({ params: [...rows, { key: 'stop_loss_pct', value: .1 }] }).map((row) => row.key)).toEqual(accountRiskFields.map(({ key }) => key))
    for (const params of [rows.slice(1), [...rows, rows[0]], [null], [...rows.slice(1), { ...rows[0], value: Infinity }], [...rows.slice(1), { ...rows[0], value: -1 }], [...rows.slice(1), { ...rows[0], value: 100000001 }], [...rows.slice(1), { ...rows[0], type: 'str' }], [...rows.slice(1), { ...rows[0], overridden: 'true' }]]) {
      expect(() => parseAccountRiskSettings({ params })).toThrow()
    }
    expect(() => parseAccountRiskSettings(null)).toThrow()
    expect(() => parseAccountRiskSettings({ params: {} })).toThrow()
    expect(() => parseAccountRiskSettings({ params: Array(301).fill(rows[0]) })).toThrow()
    for (const receipt of [{ key: 'max_daily_loss', value: '' }, { key: 'max_daily_profit', value: '1000' }, { key: 'max_daily_loss', value: '2000' }, { key: 'max_daily_loss', value: 1000 }, { key: 'max_daily_loss', value: '1000', extra: true }]) {
      expect(() => parseAccountRiskSave(receipt, 'max_daily_loss', 1000)).toThrow()
    }
  })
  it('allows only the selected owner/admin membership to edit', () => {
    expect(canEditAccountRisk(null)).toBe(false)
    for (const role of ['owner', 'admin', 'member', 'viewer']) {
      expect(canEditAccountRisk({ ...browserSession, memberships: [{ organization_id: browserSession.organization_id, name: 'Workspace', role }] })).toBe(['owner', 'admin'].includes(role))
    }
    expect(canEditAccountRisk({ ...browserSession, organization_id: 'different' })).toBe(false)
  })
  it('sends one whitelisted entry limit with CSRF and keeps permission refusal local', async () => {
    const fetch = vi.fn().mockResolvedValueOnce(response(release)).mockResolvedValueOnce(response(browserSession))
      .mockResolvedValueOnce(response({ params: rows })).mockResolvedValueOnce(response({ key: 'max_daily_loss', value: '1500.0' }))
      .mockResolvedValueOnce(response({ error: 'forbidden' }, 403)).mockResolvedValueOnce(response({ key: 'max_daily_loss', value: '0.0' }))
    vi.stubGlobal('fetch', fetch)
    const api = new StrategyApi(), signal = new AbortController().signal, invalidated = vi.fn()
    await api.bootstrap(signal); await api.session(signal); api.onAccessInvalidated(invalidated)
    expect(await api.accountRiskSettings(signal)).toHaveLength(3)
    expect(await api.saveAccountRiskSetting('max_daily_loss', 1500, signal)).toBe(1500)
    expect(fetch.mock.calls[3][0]).toBe('/api/v1/account-risk-settings')
    expect(fetch.mock.calls[3][1]).toMatchObject({ method: 'POST', credentials: 'same-origin', headers: { 'X-Strategy-CSRF': browserSession.csrf }, body: JSON.stringify({ key: 'max_daily_loss', value: 1500 }) })
    await expect(api.saveAccountRiskSetting('max_daily_loss', 0, signal)).rejects.toMatchObject({ envelope: { code: 'ACCOUNT_RISK_FORBIDDEN' } })
    expect(invalidated).not.toHaveBeenCalled()
    expect(await api.saveAccountRiskSetting('max_daily_loss', 0, signal)).toBe(0)
    const count = fetch.mock.calls.length
    await expect(api.saveAccountRiskSetting('stop_loss_pct' as never, 1, signal)).rejects.toThrow()
    await expect(api.saveAccountRiskSetting('max_daily_loss', NaN, signal)).rejects.toThrow()
    expect(fetch).toHaveBeenCalledTimes(count)
  })
  it.each([401, 500, 200])('refuses session/server/error receipts for account limits (%i)', async (status) => {
    const fetch = vi.fn().mockResolvedValueOnce(response(release)).mockResolvedValueOnce(response({ error: 'refused' }, status))
    vi.stubGlobal('fetch', fetch)
    const api = new StrategyApi(), signal = new AbortController().signal, invalidated = vi.fn()
    await api.bootstrap(signal); api.onAccessInvalidated(invalidated)
    await expect(api.accountRiskSettings(signal)).rejects.toThrow()
    expect(invalidated).toHaveBeenCalledTimes(status === 401 ? 1 : 0)
  })
})

// Monitoring transport uses its own fixed endpoint and 403-preservation policy.
import { monitoringAlertData, monitoringAttentionData, monitoringReviewData, alertAddress } from '../features/alerts/testData'
import { alertView, monitoringAlertPath, parseMonitoringAlert, parseMonitoringPage, parseAttentionMutation, parseOwnReview, parseReviewMutation } from '../features/alerts/monitoringContracts'

async function monitoringClient() {
  const manifest = structuredClone(release)
  Object.assign(manifest.capabilities.signals, { state: 'ENABLED_WITH_LIMIT', ui_navigation: true })
  const fetcher = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(response(manifest)).mockResolvedValueOnce(response(browserSession))
  const client = new StrategyApi(), signal = new AbortController().signal
  await client.bootstrap(signal); await client.session(signal); fetcher.mockClear()
  return { client, fetcher, signal }
}

it('monitoring sends fixed same-origin authenticated requests and omits false unread filtering', async () => {
  const { client, fetcher, signal } = await monitoringClient()
  fetcher.mockImplementation(async () => response({ schema: 'monitoring-alert-page/2', items: [monitoringAlertData()], next_cursor: null }))
  await client.monitoringAlerts(null, false, signal)
  expect(fetcher.mock.calls[0][0]).toBe('/api/v1/monitoring/alerts?limit=100')
  await client.monitoringAlerts('signed.cursor', true, signal)
  expect(fetcher.mock.calls[1][0]).toBe('/api/v1/monitoring/alerts?limit=100&unread_only=true&cursor=signed.cursor')
  const selected = parseMonitoringAlert(monitoringAlertData({ last_sequence: 7, is_unread: false, read_at: '2026-09-06T05:59:30Z' }))
  fetcher.mockResolvedValue(response(monitoringAttentionData({ sequence: 8, last_sequence: 8, read_at: '2026-09-06T05:59:30Z' })))
  const result = await client.monitoringAttention(selected, 'ACKNOWLEDGE', 7, signal)
  expect(result.lastSequence).toBe(8)
  const request = fetcher.mock.calls.at(-1)!
  expect(request[0]).toBe(`/api/v1/monitoring/assignments/assignment.alpha/alerts/${encodeURIComponent(alertAddress('a'))}/attention`)
  expect(request[1]).toMatchObject({ credentials: 'same-origin', cache: 'no-store', redirect: 'error', method: 'POST', headers: { 'X-Strategy-CSRF': browserSession.csrf } })
  expect(JSON.parse(String(request[1]?.body))).toEqual({ action: 'ACKNOWLEDGE', expected_sequence: 7 })
})

it('monitoring preserves a 403 session but invalidates it on 401', async () => {
  const { client, fetcher, signal } = await monitoringClient(), listener = vi.fn()
  client.onAccessInvalidated(listener)
  const selected = parseMonitoringAlert(monitoringAlertData())
  fetcher.mockResolvedValueOnce(response({ detail: 'forbidden' }, 403)).mockResolvedValueOnce(response({ schema: 'monitoring-review-read/1', review: null }))
  await expect(client.monitoringReview(selected, { disposition: 'CONFIRMED', reasonCode: 'MATCHED_EXPECTATION', note: 'Keep this note' }, signal)).rejects.toMatchObject({ kind: 'input', envelope: { code: 'MONITORING_FORBIDDEN' } })
  expect(listener).not.toHaveBeenCalled()
  await expect(client.monitoringOwnReview(selected, signal)).resolves.toBeNull()
  fetcher.mockResolvedValue(response({ detail: 'unauthorized' }, 401))
  await expect(client.monitoringAlerts(null, false, signal)).rejects.toMatchObject({ kind: 'access' })
  expect(listener).toHaveBeenCalledOnce()
})

it('monitoring rejects arbitrary endpoints, invalid identifiers and invalid local notes before fetch', async () => {
  const { client, fetcher, signal } = await monitoringClient()
  const privateRequest = client as unknown as { monitoringRequest: (method: string, path: string, signal: AbortSignal) => Promise<unknown> }
  for (const path of ['orders', 'monitoring/activate', 'monitoring/alerts?limit=100&unread_only=false', `monitoring/assignments/a%2Fb/alerts/sha256%3A${'a'.repeat(64)}`]) await expect(privateRequest.monitoringRequest('GET', path, signal)).rejects.toBeInstanceOf(ApiError)
  expect(() => monitoringAlertPath('../other', alertAddress('a'))).toThrow()
  await expect(client.monitoringReview(parseMonitoringAlert(monitoringAlertData()), { disposition: 'CONFIRMED', reasonCode: 'MATCHED_EXPECTATION', note: 'two\nlines' }, signal)).rejects.toThrow()
  expect(fetcher).not.toHaveBeenCalled()
})

it('monitoring accepts only attributed complete alert rows and consistent attention replies', () => {
  for (const field of ['monitoring_event_address', 'strategy_id', 'graph_version_address', 'last_sequence']) {
    const value = monitoringAlertData(); delete value[field as keyof typeof value]
    expect(() => parseMonitoringAlert(value)).toThrow()
  }
  expect(() => parseMonitoringAlert(monitoringAlertData({ schema: 'monitoring-alert-read/1' }))).toThrow()
  expect(() => parseMonitoringAlert(monitoringAlertData({ last_sequence: false }))).toThrow()
  const selected = parseMonitoringAlert(monitoringAlertData())
  for (const change of [{ alert_address: alertAddress('0') }, { assignment_id: 'other' }, { sequence: 0 }, { last_sequence: 0 }, { action: 'READ' }, { is_unread: true }, { acknowledged_at: null }]) expect(() => parseAttentionMutation(monitoringAttentionData(change), selected, 'ACKNOWLEDGE', 0)).toThrow()
  const read = monitoringReviewData()
  expect(parseOwnReview({ schema: 'monitoring-review-read/1', review: read }, selected)?.note).toBe(read.note)
  expect(() => parseOwnReview({ schema: 'monitoring-review-read/1', review: { ...read, monitoring_event_address: alertAddress('0') } }, selected)).toThrow()
  expect(() => parseReviewMutation({ schema: 'monitoring-review-mutation-read/1', ...read, note: 'Different', replayed: false }, selected, { disposition: 'CONFIRMED', reasonCode: 'MATCHED_EXPECTATION', note: read.note })).toThrow()
})

it('monitoring derives expiry from the clock and rejects false unread or duplicate pages', () => {
  const selected = parseMonitoringAlert(monitoringAlertData())
  expect(alertView(selected, Date.parse('2026-09-06T07:00:00Z')).evidenceState).toBe('EXPIRED')
  expect(alertView(selected, Date.parse('2026-09-06T05:58:00Z')).evidenceState).toBe('UNKNOWN')
  expect(() => parseMonitoringPage({ schema: 'monitoring-alert-page/2', items: [monitoringAlertData(), monitoringAlertData()], next_cursor: null }, false)).toThrow()
  expect(() => parseMonitoringPage({ schema: 'monitoring-alert-page/2', items: [monitoringAlertData({ is_unread: false, last_sequence: 1, read_at: '2026-09-06T06:00:00Z' })], next_cursor: null }, true)).toThrow()
})

it('monitoring rejects oversized, malformed and non JSON successful responses', async () => {
  const { client, fetcher, signal } = await monitoringClient()
  for (const response of [
    new Response('{}', { headers: { 'content-type': 'text/html' } }),
    new Response('{}', { headers: { 'content-type': 'application/json', 'content-length': 'invalid' } }),
    new Response('{}', { headers: { 'content-type': 'application/json', 'content-length': '524289' } }),
    new Response(' '.repeat(524289), { headers: { 'content-type': 'application/json' } }),
    new Response('{', { headers: { 'content-type': 'application/json' } }),
  ]) {
    fetcher.mockResolvedValueOnce(response)
    await expect(client.monitoringAlerts(null, false, signal)).rejects.toThrow()
  }
})

it('monitoring verifies detail identity and successful saved review echo through the transport', async () => {
  const { client, fetcher, signal } = await monitoringClient(), selected = parseMonitoringAlert(monitoringAlertData())
  fetcher.mockResolvedValueOnce(response(monitoringAlertData()))
  await expect(client.monitoringAlert(selected, signal)).resolves.toEqual(selected)
  fetcher.mockResolvedValueOnce(response(monitoringAlertData({ strategy_id: 'strategy.other' })))
  await expect(client.monitoringAlert(selected, signal)).rejects.toThrow()
  const draft = { disposition: 'CONFIRMED' as const, reasonCode: 'MATCHED_EXPECTATION', note: 'Matches the written rules' }
  fetcher.mockResolvedValueOnce(response({ schema: 'monitoring-review-mutation-read/1', ...monitoringReviewData(), replayed: false }))
  await expect(client.monitoringReview(selected, draft, signal)).resolves.toMatchObject(draft)
})

it('daily CSV session metadata keeps multipart optional, rejects combined oversize and preserves typed session errors', async () => {
  const fetch = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(response(release)).mockResolvedValueOnce(response(browserSession))
  const api = new StrategyApi(), signal = new AbortController().signal
  await api.bootstrap(signal); await api.session(signal)
  const file = new File(['data'], 'daily.csv'), sessions = new File(['sessions'], 'sessions.csv')
  for (const operation of ['inspectDailyCsv', 'importDailyCsv'] as const) {
    fetch.mockResolvedValueOnce(response({ detail: { code: 'SESSION_CSV_HEADER_INVALID', message: 'private parser detail' } }, 422))
    await expect(api[operation]('project.a', file, dailyMetadata, signal, sessions)).rejects.toMatchObject({ kind: 'input', envelope: { code: 'SESSION_CSV_HEADER_INVALID' } })
    const body = fetch.mock.calls.at(-1)![1]!.body as FormData
    expect(body.get('session_metadata')).toBe(sessions)
    expect(body.get('file')).toBe(file)
  }
  const calls = fetch.mock.calls.length
  await expect(api.inspectDailyCsv('project.a', file, dailyMetadata, signal, new File([new Uint8Array(1048576)], 'large.csv'))).rejects.toMatchObject({ kind: 'input' })
  expect(fetch).toHaveBeenCalledTimes(calls)
})


describe('canonical development search contracts', () => {
  const axis = { node_id: 'rising', parameter_id: 'window', step: '1', minimum: '1', maximum: '3' }
  const enabled = { schema: 'canonical-local-development-search/1' as const, enabled: true, axes: [axis] }
  it('keeps immutable normalized axes and codepoint order', () => {
    const result = parseOptimizationSettings(enabled)
    expect(result).toEqual(enabled); expect(Object.isFrozen(result.axes[0])).toBe(true)
    expect(parseOptimizationSettings(disabledOptimization()).axes).toEqual([])
    expect(compareOptimizationAxes({node_id:'\uE000',parameter_id:'a'}, {node_id:'😀',parameter_id:'a'})).toBeLessThan(0)
    for (const step of ['1.0', '1e1', '+1', '-0', '', '0'.repeat(129)]) expect(() => parseOptimizationSettings({...enabled, axes:[{...axis,step}]})).toThrow()
    for (const axes of [[], [axis,axis], Array.from({length:5},(_,i)=>({...axis,node_id:String(i)}))]) expect(() => parseOptimizationSettings({...enabled,axes})).toThrow()
    expect(() => parseOptimizationSettings({...enabled,enabled:false})).toThrow()
    expect(optimizationInputProblem(enabled)).toBeNull()
    expect(optimizationInputProblem({...enabled,axes:[{...axis,step:'0'}]})).toMatch(/greater than zero/)
    expect(optimizationInputProblem({...enabled,axes:[{...axis,minimum:'3.1',maximum:'3'}]})).toMatch(/minimum/)
    expect(optimizationInputProblem({...enabled,axes:[{...axis,step:'1e1'}]})).toMatch(/plain decimals/)
  })
  it('parses the synthetic worker selection and refuses inconsistent retained results', () => {
    const graphId = optimizationFixture.selected.canonical_document.strategy_id
    const result = parseCanonicalOptimizationEvidence(optimizationFixture,graphId)
    expect(result.state).toBe('selected'); expect(result.candidates).toHaveLength(3); expect(result.nested_trials).toHaveLength(6)
    expect(result.selected?.parameters[0].normalized_value).toBe('1')
    const mutate = (change: (value: typeof optimizationFixture)=>void) => {const value=structuredClone(optimizationFixture);change(value);expect(()=>parseCanonicalOptimizationEvidence(value,graphId)).toThrow()}
    mutate(value=>{value.candidates[0].parameters[0].value=99})
    mutate(value=>{value.candidates[0].coordinates.axis_000='2.0'})
    mutate(value=>{value.candidates[0].lineage.graph_address=value.candidates[1].graph_address})
    mutate(value=>{value.nested_trials[0].fold_index=9})
    mutate(value=>{value.nested_trials[0].params.candidate_graph_address=value.candidates[1].graph_address})
    mutate(value=>{value.final_development_trials.forEach(row=>{row.selected=false})})
    mutate(value=>{value.n_trials=8})
    mutate(value=>{value.nested_trials.pop()})
    mutate(value=>{value.partition.validation_start_ts=value.partition.development_end_ts})
    mutate(value=>{value.performance_matrix=[[1,2,3]]})
    mutate(value=>{value.selected.parameters[0].value=99})
    const cancelled={...optimizationFixture,state:'cancelled',selected:null,nested_trials:[],final_development_trials:[],n_trials:0,performance_matrix:[]}
    expect(parseCanonicalOptimizationEvidence(cancelled,graphId).state).toBe('cancelled')
    expect(()=>parseCanonicalOptimizationEvidence({...cancelled,selected:optimizationFixture.selected},graphId)).toThrow()
  })
})

it.each(['inspect', 'import'] as const)('keeps the %s CSV request within its own bounded deadline', async (action) => {
  vi.useFakeTimers()
  let requestSignal: AbortSignal | null | undefined
  vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(response(release)).mockResolvedValueOnce(response(browserSession))
    .mockImplementationOnce((_url, init) => new Promise((_resolve, reject) => {
      requestSignal = init?.signal
      requestSignal?.addEventListener('abort', () => reject(new DOMException('cancelled', 'AbortError')))
    }))
  const api = new StrategyApi(), signal = new AbortController().signal
  await api.bootstrap(signal); await api.session(signal)
  const file = new File(['Date,Open,High,Low,Close'], 'bounded.csv')
  const request = action === 'import' ? api.importDailyCsv('project.a', file, dailyMetadata, signal) : api.inspectDailyCsv('project.a', file, dailyMetadata, signal)
  const rejected = expect(request).rejects.toMatchObject({ kind: 'timeout' })
  await vi.advanceTimersByTimeAsync(10001)
  expect(requestSignal?.aborted).toBe(action === 'inspect')
  if (action === 'import') await vi.advanceTimersByTimeAsync(110000)
  await rejected
  vi.useRealTimers()
})

describe('provider history request and receipt boundary', () => {
  const selection = `sha256:${'d'.repeat(64)}`
  const input = { selection_address: selection, start_date: '2025-01-01', end_date: '2025-12-31', interval: 'day' as const }
  const item = { manifest_address: `sha256:${'a'.repeat(64)}`, instrument_address: `sha256:${'1'.repeat(64)}`,
    canonical_instrument_label: 'INFY', instrument_display_name: 'Infosys', provider_selection_address: selection,
    asset_class: 'EQUITY', contract_kind: 'SPOT', interval: 'day', event_start: '2025-01-01T18:30:00Z', event_end: '2025-12-31T18:30:00Z',
    availability_end: '2026-09-06T12:00:01Z', as_of: '2026-09-06T12:00:01Z', bar_count: 248, fields: ['OPEN', 'HIGH', 'LOW', 'CLOSE', 'VOLUME'],
    provider_evidence_state: 'VERIFIED_REFERENCES_PRESENT', market_truth_state: 'RECONSTRUCTED_WITH_GAPS', source_type: 'PROVIDER_AUTHORITY',
    historical_source_availability: 'NOT_SUPPLIED', calendar_coverage: 'NOT_ASSERTED', rights_scope: 'PROVIDER_CONTRACT',
    research_compatibility: 'PRIMARY_BACKTEST', gaps: [], backtest_eligibility: 'ELIGIBLE_Q03', refusal_code: null }
  const receipt = { schema: 'strategy-os-provider-history-import/1', reused: false, project_id: 'project.a', selection_address: selection,
    requested_start: '2024-12-31T18:30:00Z', requested_end: '2025-12-31T18:29:59Z', returned_start: item.event_start,
    returned_end: '2025-12-30T18:30:00Z', request_count: 1, empty_request_count: 0, request_window_days: 1900,
    application_bar_limit: 2000, provider_retention: 'UNKNOWN', item }
  it('sends only the saved selection and daily dates through the authenticated REST transport', async () => {
    const fetch = vi.spyOn(globalThis, 'fetch').mockClear().mockResolvedValueOnce(response(release)).mockResolvedValueOnce(response(browserSession))
      .mockResolvedValueOnce(response(receipt))
    const api = new StrategyApi(), signal = new AbortController().signal
    await api.bootstrap(signal); await api.session(signal)
    expect(await api.importProviderHistory('project.a', input, signal)).toEqual(receipt)
    expect(fetch.mock.calls[2]).toEqual(['/api/v1/ir/projects/project.a/research-datasets/from-provider', expect.objectContaining({
      method: 'POST', credentials: 'same-origin', headers: expect.objectContaining({ 'X-Strategy-CSRF': 'c'.repeat(64) }), body: JSON.stringify(input) })])
  })
  it('refuses invalid dates without sending provider requests', async () => {
    const fetch = vi.spyOn(globalThis, 'fetch').mockClear().mockResolvedValueOnce(response(release)).mockResolvedValueOnce(response(browserSession))
    const api = new StrategyApi(), signal = new AbortController().signal
    await api.bootstrap(signal); await api.session(signal)
    await expect(api.importProviderHistory('project.a', { ...input, start_date: '2025-02-30' }, signal)).rejects.toThrow()
    expect(fetch).toHaveBeenCalledTimes(2)
  })
  it('retains the typed server refusal and rejects a substituted saved selection', async () => {
    const error = { code: 'HISTORICAL_FETCH_GRANT_UNAVAILABLE', message: 'No active historical research grant is recorded.' }
    vi.spyOn(globalThis, 'fetch').mockClear().mockResolvedValueOnce(response(release)).mockResolvedValueOnce(response(browserSession))
      .mockResolvedValueOnce(response({ detail: error }, 409)).mockResolvedValueOnce(response({ ...receipt, selection_address: `sha256:${'f'.repeat(64)}` }))
    const api = new StrategyApi(), signal = new AbortController().signal
    await api.bootstrap(signal); await api.session(signal)
    await expect(api.importProviderHistory('project.a', input, signal)).rejects.toMatchObject({ envelope: error })
    await expect(api.importProviderHistory('project.a', input, signal)).rejects.toThrow('could not be verified')
  })
  it('allows bounded synchronous publication time and cancels at its own deadline', async () => {
    vi.useFakeTimers()
    try {
      let requestSignal: AbortSignal | null | undefined
      vi.spyOn(globalThis, 'fetch').mockClear().mockResolvedValueOnce(response(release)).mockResolvedValueOnce(response(browserSession))
        .mockImplementationOnce((_url, init) => new Promise((_resolve, reject) => {
          requestSignal = init?.signal
          requestSignal?.addEventListener('abort', () => reject(new DOMException('cancelled', 'AbortError')))
        }))
      const api = new StrategyApi(), signal = new AbortController().signal
      await api.bootstrap(signal); await api.session(signal)
      const rejected = expect(api.importProviderHistory('project.a', input, signal)).rejects.toMatchObject({ kind: 'timeout' })
      await vi.advanceTimersByTimeAsync(10001); expect(requestSignal?.aborted).toBe(false)
      await vi.advanceTimersByTimeAsync(110000); await rejected; expect(requestSignal?.aborted).toBe(true)
    } finally { vi.useRealTimers() }
  })
  it('does not expose late receipt bytes after access invalidation', async () => {
    let finish!: (value: Response) => void
    vi.spyOn(globalThis, 'fetch').mockClear().mockResolvedValueOnce(response(release)).mockResolvedValueOnce(response(browserSession))
      .mockImplementationOnce(() => new Promise((resolve) => { finish = resolve }))
    const api = new StrategyApi(), signal = new AbortController().signal
    await api.bootstrap(signal); await api.session(signal)
    const loading = api.importProviderHistory('project.a', input, signal)
    api.recheck(); finish(response(receipt))
    await expect(loading).rejects.toMatchObject({ name: 'AbortError' })
  })
})

it.each(['caller abort', 'network loss'] as const)('does not report a successful history save after %s', async (failure) => {
  let fail!: (reason: unknown) => void
  vi.spyOn(globalThis, 'fetch').mockClear().mockResolvedValueOnce(response(release)).mockResolvedValueOnce(response(browserSession))
    .mockImplementationOnce((_url, init) => new Promise((_resolve, reject) => {
      fail = reject
      init?.signal?.addEventListener('abort', () => reject(new DOMException('cancelled', 'AbortError')))
    }))
  const api = new StrategyApi(), controller = new AbortController()
  await api.bootstrap(controller.signal); await api.session(controller.signal)
  const loading = api.importProviderHistory('project.a', { selection_address: `sha256:${'d'.repeat(64)}`,
    start_date: '2025-01-01', end_date: '2025-12-31', interval: 'day' }, controller.signal)
  if (failure === 'caller abort') controller.abort()
  else fail(new TypeError('network disconnected'))
  await expect(loading).rejects.toMatchObject(failure === 'caller abort' ? { name: 'AbortError' } : { kind: 'network' })
})

describe('watchlist monitoring API adapter', () => {
  const hash = `sha256:${'1'.repeat(64)}`
  const context = { projectId: 'project.static', scopeId: 'scope.api', scopeRevision: 1, scopeAddress: hash, membershipAddress: hash }
  const member = { kind: 'CANONICAL' as const, instrument_address: hash }
  const row = { member_key: `CANONICAL:${hash}`, configuration_revision: 0, pinned: false, graph: null, timeframe: '15minute',
    supported_timeframes: [{ value: '15minute', label: '15 min' }], assignment_id: null, monitoring: 'OFF', can_configure: true,
    can_pin: true, can_set_monitoring: false, reason: 'Choose a strategy.', result: { kind: 'NOT_EVALUATED', label: 'Not evaluated',
      evaluated_at: null, assignment_id: null, graph_version_address: null, reason: null, warmup: null } }
  const snapshot = { schema: 'watchlist-monitoring-rows/1', context: watchlistContextBody(context), rows: [row] }
  const receipt = { schema: 'watchlist-monitoring-row/1', context: snapshot.context, row: { ...row, configuration_revision: 1, pinned: true } }
  beforeEach(() => vi.stubGlobal('crypto', webcrypto))
  afterEach(() => vi.unstubAllGlobals())

  it('uses exact context, member and revision through the authenticated transport', async () => {
    const enabled = structuredClone(release)
    Object.assign(enabled.capabilities.static_watchlists, { state: 'ENABLED_WITH_LIMIT', ui_navigation: true })
    const fetch = vi.spyOn(globalThis, 'fetch').mockReset().mockResolvedValueOnce(response(enabled)).mockResolvedValueOnce(response(browserSession))
      .mockResolvedValueOnce(response(snapshot)).mockResolvedValueOnce(response(receipt)).mockResolvedValueOnce(response(receipt)).mockResolvedValueOnce(response(receipt))
    const api = new StrategyApi(), signal = new AbortController().signal
    await api.bootstrap(signal); await api.session(signal)
    const client = createWatchlistMonitorClient(api)
    expect((await client.list(context, signal)).rows[0]).toMatchObject({ memberKey: row.member_key, monitoring: 'OFF' })
    expect(await client.pin(context, member, 0, true, signal)).toMatchObject({ pinned: true, configurationRevision: 1 })
    await client.configure(context, member, 0, { graphId: 'graph.test', graphVersion: 2, timeframe: 'day' }, signal)
    await client.setMonitoring(context, member, 0, true, signal)
    expect(fetch.mock.calls[2][0]).toBe(`/api/v1/ir/projects/project.static/static-scopes/scope.api/monitoring-rows?${new URLSearchParams({ scope_revision: '1', scope_address: hash, membership_address: hash })}`)
    const bodies = fetch.mock.calls.slice(3).map((call) => JSON.parse(String(call[1]?.body)))
    expect(bodies.map((body) => body.command)).toEqual([
      { operation: 'PIN', expected_revision: 0, selection: null, flag: true },
      { operation: 'CONFIGURE', expected_revision: 0, selection: { graph_id: 'graph.test', graph_version: 2, timeframe: 'day' }, flag: null },
      { operation: 'MONITOR', expected_revision: 0, selection: null, flag: true },
    ])
    for (const body of bodies) expect(body).toMatchObject({ context: snapshot.context, member, request_id: expect.stringMatching(/^[0-9a-f-]{14}4[0-9a-f-]{21}$/) })
    for (const call of fetch.mock.calls.slice(3)) expect(call[1]).toMatchObject({ method: 'POST', credentials: 'same-origin', cache: 'no-store', redirect: 'error', headers: { 'X-Strategy-CSRF': browserSession.csrf } })
  })
  it('blocks disabled capability and cancels an obsolete response after session recheck', async () => {
    const fetch = vi.spyOn(globalThis, 'fetch').mockReset().mockResolvedValueOnce(response(release))
    const api = new StrategyApi(), signal = new AbortController().signal
    await api.bootstrap(signal)
    const client = createWatchlistMonitorClient(api)
    await expect(client.list(context, signal)).rejects.toMatchObject({ kind: 'manifest' })
    expect(fetch).toHaveBeenCalledOnce()
    const enabled = structuredClone(release)
    Object.assign(enabled.capabilities.static_watchlists, { state: 'ENABLED_WITH_LIMIT', ui_navigation: true })
    fetch.mockResolvedValueOnce(response(enabled))
    await api.bootstrap(signal)
    let resolve!: (value: Response) => void
    fetch.mockReturnValueOnce(new Promise<Response>((done) => { resolve = done }))
    const pending = client.list(context, signal)
    api.recheck(); resolve(response(snapshot))
    await expect(pending).rejects.toMatchObject({ name: 'AbortError' })
  })
  it.each([
    { member_key: hash }, { configuration_revision: -1 }, { pinned: 1 }, { monitoring: 'LIVE' }, { extra: true },
    { supported_timeframes: [{ value: 'tick', label: 'Tick' }] }, { reason: 'bad\u0000text' },
    { graph: { graph_id: 'x', graph_version: 1, graph_version_address: 'bad', label: 'Strategy' } },
    { result: { ...row.result, kind: 'SIGNAL' } }, { result: { ...row.result, evaluated_at: '2026-02-30T00:00:00Z' } },
    { result: { ...row.result, warmup: { available: -1, required: 2 } } },
    { result: { ...row.result, assignment_id: 'foreign' } },
    { result: { ...row.result, graph_version_address: hash } },
  ])('rejects unsafe or unattributable row fields %j', (patch) => {
    expect(() => parseWatchlistMonitoringRows({ ...snapshot, rows: [{ ...row, ...patch }] }, context)).toThrow()
  })
  it('rejects foreign context, duplicate members and wrong write revisions', () => {
    expect(() => parseWatchlistMonitoringRows({ ...snapshot, context: { ...snapshot.context, scope_revision: 2 } }, context)).toThrow()
    expect(() => parseWatchlistMonitoringRows({ ...snapshot, rows: [row, row] }, context)).toThrow()
    expect(() => parseWatchlistMonitoringRows({ ...snapshot, extra: true }, context)).toThrow()
    expect(() => parseWatchlistMonitoringRow(receipt, context, member, 1)).toThrow()
    expect(() => parseWatchlistMonitoringRow(receipt, context, { kind: 'PROVIDER_REFERENCE', selection_address: hash }, 0)).toThrow()
  })
})
