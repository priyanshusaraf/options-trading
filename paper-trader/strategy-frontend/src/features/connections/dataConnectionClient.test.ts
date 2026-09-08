import { canonicalJson, contentAddress } from '../../shell/contentAddress'
import { createHash, webcrypto } from 'node:crypto'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
beforeEach(() => vi.stubGlobal('crypto', webcrypto))
afterEach(() => vi.unstubAllGlobals())
import {
  DataConnectionContractError,
  DataConnectionRequestError,
  createDataConnectionClient,
  parseDataConnectionStatus,
  parseProviderInstrumentSearch,
  parseProviderInstrumentSelection,
  type ProviderInstrumentReference,
  type ProviderResearchReference,
  parseProviderReference,
  parseSavedProviderSelection,
  type DataConnectionState,
  type DataConnectionTransport,
} from './dataConnectionClient'

const allowed: Readonly<Record<DataConnectionState, readonly string[]>> = {
  CONNECTION_REQUIRED: ['create'],
  APP_KEYS_REQUIRED: ['write_app_keys', 'revoke'],
  REAUTH_REQUIRED: ['rotate_app_keys', 'reauthenticate', 'revoke'],
  SESSION_PRESENT_UNVERIFIED: ['rotate_app_keys', 'reauthenticate', 'revoke'],
  REVOKED: ['create'],
  UNAVAILABLE: [],
}

function status(state: DataConnectionState = 'REAUTH_REQUIRED') {
  return {
    schema: 'strategy-os-data-connection-status/1', state, provider: 'ZERODHA', role: 'DATA',
    ready: false, credential_expiry: 'UNVERIFIED', rate_quota: 'UNVERIFIED',
    actions: Object.fromEntries(['create', 'write_app_keys', 'rotate_app_keys', 'reauthenticate', 'revoke']
      .map((action) => [action, allowed[state].includes(action)])),
  }
}

function transport(body: unknown = status(), responseStatus = 200) {
  return vi.fn<DataConnectionTransport>().mockResolvedValue({
    status: responseStatus,
    headers: { contentType: 'application/json; charset=utf-8', cacheControl: 'no-store' },
    body,
  })
}

function providerReference(changes: Partial<ProviderInstrumentReference> = {}): ProviderInstrumentReference {
  return { token: 256265, symbol: 'NIFTY 50', name: 'NIFTY 50', exchange: 'NSE', segment: 'INDICES', instrument_type: 'EQ',
    expiry: null, strike: '0', lot_size: '1', tick_size: '0.05', ...changes }
}
function instrumentResult(query = 'NIFTY', exchange = 'NSE') {
  const selectedExchange = exchange === 'ALL' ? 'NSE' : exchange
  return { schema: 'strategy-os-provider-instrument-search/2', provider: 'ZERODHA', reference_type: 'CURRENT_PROVIDER_REFERENCE',
    query, exchange, available_exchanges: [...new Set(['NSE', 'BSE', 'NFO', 'MCX', selectedExchange])], has_more: false,
    items: [providerReference({ exchange: selectedExchange })] }
}

describe('data connection client', () => {
  it('encodes a read-only search with no-store policy and binds the result to the submitted query', async () => {
    const send = transport(instrumentResult('M&M', 'BSE'))
    const signal = new AbortController().signal
    const result = await createDataConnectionClient(send).searchInstruments(' M&M ', 'BSE', signal)
    expect(send.mock.calls[0][0]).toEqual({ method: 'GET',
      path: '/api/v1/data-connections/instruments?query=M%26M&exchange=BSE&limit=20', signal,
      credentials: 'same-origin', cache: 'no-store', redirect: 'error', csrfRequired: false,
      headers: { Accept: 'application/json' }, requestBodyLimitBytes: 4096, responseBodyLimitBytes: 65536 })
    expect(result.reference_type).toBe('CURRENT_PROVIDER_REFERENCE')
    expect(result).not.toHaveProperty('canonical_mapping')
    expect(result).not.toHaveProperty('historical_mapping')
    expect(Object.isFrozen(result)).toBe(true)
    expect(Object.isFrozen(result.items)).toBe(true)
    expect(Object.isFrozen(result.items[0])).toBe(true)
  })

  it.each(['', 'a', 'x'.repeat(65), 'e\u0301quity', 'nifty\n50'])('refuses invalid search input before transport: %s', async (query) => {
    const send = transport(instrumentResult())
    await expect(createDataConnectionClient(send).searchInstruments(query, 'NSE', new AbortController().signal)).rejects.toMatchObject({ status: 422 })
    expect(send).not.toHaveBeenCalled()
  })

  it.each([
    { canonical_mapping: 'VERIFIED' }, { historical_mapping: 'VERIFIED' }, { reference_type: 'CANONICAL' },
    { provider: 'OTHER' }, { schema: 'other/1' }, { query: 'OTHER' }, { exchange: 'BSE' },
    { owner_id: 'foreign' }, { has_more: 'false' }, { has_more: true }, { items: {} },
  ])('rejects forged or misattributed instrument envelopes: %j', (changes) => {
    expect(() => parseProviderInstrumentSearch({ ...instrumentResult(), ...changes }, 'nifty', 'NSE')).toThrow(DataConnectionContractError)
  })

  it.each([
    { token: true }, { token: '256265' }, { token: 0 }, { token: 4_294_967_296 }, { token: 1.5 },
    { symbol: '' }, { symbol: ' ' }, { symbol: ' NIFTY' }, { symbol: 'NIFTY\u007f' }, { symbol: 'x'.repeat(65) },
    { name: null }, { name: 'e\u0301quity' }, { name: 'x'.repeat(129) }, { exchange: 'BSE' }, { instrument_type: '' }, { expiry: '2026-02-30' }, { strike: '1.0' }, { lot_size: '-1' }, { tick_size: '0.0000000000000000000000001' }, { kind: 'FUT' },
    { canonical_id: 'fabricated' },
  ])('rejects malformed provider reference fields: %j', (changes) => {
    const body = instrumentResult()
    expect(() => parseProviderInstrumentSearch({ ...body, items: [{ ...body.items[0], ...changes }] }, 'nifty', 'NSE')).toThrow(DataConnectionContractError)
  })

  it('enforces response count, duplicates and exact full-page has_more semantics', () => {
    const body = instrumentResult()
    const items = Array.from({ length: 20 }, (_, index) => ({ ...body.items[0], token: index + 1 }))
    expect(parseProviderInstrumentSearch({ ...body, items, has_more: true }, 'nifty', 'NSE').items).toHaveLength(20)
    expect(() => parseProviderInstrumentSearch({ ...body, items: [...items, { ...items[0], token: 21 }] }, 'nifty', 'NSE')).toThrow(DataConnectionContractError)
    expect(() => parseProviderInstrumentSearch({ ...body, items: [items[0], items[0]] }, 'nifty', 'NSE')).toThrow(DataConnectionContractError)
    expect(parseProviderInstrumentSearch({ ...body, items: [] }, 'nifty', 'NSE').items).toHaveLength(0)
    expect(parseProviderInstrumentSearch({ ...body, items: [{ ...body.items[0], token: 4_294_967_295, name: '' }] }, 'nifty', 'NSE').items[0].name).toBe('')
  })

  it('keeps only recognized refusal codes and never projects provider error text', async () => {
    const signal = new AbortController().signal
    const known = transport({ detail: { code: 'DATA_REAUTH_REQUIRED', message: 'PRIVATE-PAYLOAD' } }, 409)
    await expect(createDataConnectionClient(known).searchInstruments('nifty', 'NSE', signal)).rejects.toMatchObject({ status: 409, code: 'DATA_REAUTH_REQUIRED', message: 'Provider connection request was not accepted.' })
    const unknown = transport({ detail: { code: 'PRIVATE-PAYLOAD', message: 'PRIVATE-PAYLOAD' } }, 502)
    await expect(createDataConnectionClient(unknown).searchInstruments('nifty', 'NSE', signal)).rejects.toMatchObject({ status: 502, code: null })
    const extra = transport({ detail: { code: 'DATA_REAUTH_REQUIRED', message: '', token: 'PRIVATE-PAYLOAD' } }, 409)
    await expect(createDataConnectionClient(extra).searchInstruments('nifty', 'NSE', signal)).rejects.toMatchObject({ code: null })
  })

  it.each([
    { contentType: 'text/html', cacheControl: 'no-store' },
    { contentType: 'application/json', cacheControl: 'public' },
  ])('rejects unverified response metadata for search', async (headers) => {
    const send = transport(instrumentResult())
    send.mockResolvedValue({ status: 200, headers, body: instrumentResult() })
    await expect(createDataConnectionClient(send).searchInstruments('nifty', 'NSE', new AbortController().signal)).rejects.toBeInstanceOf(DataConnectionContractError)
  })

  it.each(Object.keys(allowed) as DataConnectionState[])('accepts exact closed %s state', (state) => {
    const parsed = parseDataConnectionStatus(status(state))
    expect(parsed.state).toBe(state)
    expect(parsed.ready).toBe(false)
    expect(Object.isFrozen(parsed.actions)).toBe(true)
  })

  it('rejects a readiness lie, action lie and extra field', () => {
    expect(() => parseDataConnectionStatus({ ...status(), ready: true })).toThrow(DataConnectionContractError)
    expect(() => parseDataConnectionStatus({ ...status(), actions: { ...status().actions, create: true } })).toThrow(DataConnectionContractError)
    expect(() => parseDataConnectionStatus({ ...status(), owner_id: 'other' })).toThrow(DataConnectionContractError)
  })

  it('sends exact direct V1 descriptors and keeps secrets only in the request body', async () => {
    const send = transport()
    const client = createDataConnectionClient(send)
    const signal = new AbortController().signal
    await client.storeAppKeys({ api_key: 'KEY-SENTINEL', api_secret: 'SECRET-SENTINEL' }, signal)
    expect(send).toHaveBeenCalledOnce()
    const descriptor = send.mock.calls[0][0]
    expect(descriptor).toMatchObject({
      method: 'POST', path: '/api/v1/data-connections/app-keys',
      credentials: 'same-origin', cache: 'no-store', redirect: 'error', csrfRequired: true,
      requestBodyLimitBytes: 4096, responseBodyLimitBytes: 65536,
    })
    expect(JSON.parse(descriptor.body ?? '')).toEqual({ api_key: 'KEY-SENTINEL', api_secret: 'SECRET-SENTINEL' })
    expect(JSON.stringify(await client.status(signal))).not.toContain('SENTINEL')
  })

  it('accepts only a bounded http login URL and converts non-success into a closed error', async () => {
    const good = transport({ login_url: 'https://fake-provider.invalid/login?state=synthetic' })
    await expect(createDataConnectionClient(good).initiate(new AbortController().signal)).resolves.toEqual({
      login_url: 'https://fake-provider.invalid/login?state=synthetic',
    })
    const bad = transport({ login_url: 'javascript:alert(1)' })
    await expect(createDataConnectionClient(bad).initiate(new AbortController().signal)).rejects.toBeInstanceOf(DataConnectionContractError)
    const refused = transport({}, 409)
    await expect(createDataConnectionClient(refused).create(new AbortController().signal)).rejects.toBeInstanceOf(DataConnectionRequestError)
  })
})


const selectedReference: ProviderResearchReference = { token: 256265, symbol: 'NIFTY 50', name: 'NIFTY 50', exchange: 'NSE', kind: 'INDEX' }
function selectionHash(value: unknown): string {
  const json = JSON.stringify(value, (_key, item) => item && typeof item === 'object' && !Array.isArray(item)
    ? Object.fromEntries(Object.entries(item).sort(([a], [b]) => a < b ? -1 : 1)) : item)
  return `sha256:${createHash('sha256').update(json).digest('hex')}`
}
function selectionBody() {
  const definition = { authority_namespace: 'synthetic:index', authority_version: '1',
    venue_code: 'XNSE', asset_class: 'INDEX', contract_kind: 'SPOT', currency: 'INR', economic_underlier_address: null,
    expiry: null, strike: null, option_right: null, multiplier: null, series_terms: [] }
  const address = selectionHash({ schema: 'canonical-instrument/1', fact: definition })
  const document = { schema: 'strategy-os-index-definition-reference/1', representation: 'TRANSFORMED_REFERENCE',
    extraction_method: 'Synthetic test reference', retrieved_on: '2026-09-06', instrument_address: address,
    interpretation: { name: 'Nifty 50', currency: 'INR', return_type: 'PRICE_RETURN' },
    sources: [{ url: 'https://example.invalid/reference', document_date: null, location: 'Test', excerpt: 'Synthetic reference' }] }
  return { schema: 'strategy-os-provider-instrument-selection/1', reference_type: 'CURRENT_PROVIDER_REFERENCE', historical_mapping: 'UNVERIFIED',
    selection: { ...selectedReference }, instrument: { address, definition }, definition_evidence: { address: selectionHash(document), document } }
}
it('resolves the exact selected reference with CSRF policy and returns only a labelled canonical address', async () => {
  const send = transport(selectionBody()), signal = new AbortController().signal
  const result = await createDataConnectionClient(send).resolveInstrument(selectedReference, signal)
  expect(send.mock.calls[0][0]).toMatchObject({ method: 'POST', path: '/api/v1/data-connections/instruments/resolve', signal,
    csrfRequired: true, credentials: 'same-origin', cache: 'no-store', redirect: 'error',
    body: JSON.stringify({ token: 256265, symbol: 'NIFTY 50', exchange: 'NSE' }) })
  expect(result).toEqual({ instrument_address: selectionBody().instrument.address, display_name: 'Nifty 50 · INR · Price return', historical_mapping: 'UNVERIFIED' })
  expect(Object.isFrozen(result)).toBe(true)
  expect(result).not.toHaveProperty('token')
})
it.each([
  { schema: 'wrong' }, { historical_mapping: 'VERIFIED' }, { reference_type: 'HISTORICAL' },
  { selection: { ...selectedReference, token: 42 } }, { selection: { ...selectedReference, symbol: 'OTHER' } },
  { selection: { ...selectedReference, name: 'OTHER' } }, { selection: { ...selectedReference, exchange: 'BSE' } },
  { selection: { ...selectedReference, kind: 'EQUITY' } }, { secret: 'forbidden' },
])('rejects a substituted selection response %j', async (changes) => {
  await expect(parseProviderInstrumentSelection({ ...selectionBody(), ...changes }, selectedReference)).rejects.toThrow(DataConnectionContractError)
})
it.each([
  { asset_class: 'EQUITY' }, { contract_kind: 'FUTURE' }, { currency: 'USD' }, { venue_code: 'XBOM' },
  { authority_namespace: '' }, { authority_version: 'x\n' }, { expiry: '2026-09-30' }, { multiplier: '1' }, { series_terms: [['x', 'y']] },
])('rejects a malformed index definition %j', async (changes) => {
  const body = selectionBody()
  await expect(parseProviderInstrumentSelection({ ...body, instrument: { ...body.instrument, definition: { ...body.instrument.definition, ...changes } } }, selectedReference)).rejects.toThrow(DataConnectionContractError)
})
it.each([
  { schema: 'wrong' }, { representation: 'ORIGINAL_BYTES' }, { instrument_address: `sha256:${'3'.repeat(64)}` },
  { interpretation: { name: 'Nifty 50', currency: 'USD', return_type: 'PRICE_RETURN' } },
  { interpretation: { name: 'Nifty 50', currency: 'INR', return_type: 'TOTAL_RETURN' } },
  { interpretation: { name: '', currency: 'INR', return_type: 'PRICE_RETURN' } },
])('rejects a mismatched definition label %j', async (changes) => {
  const body = selectionBody()
  await expect(parseProviderInstrumentSelection({ ...body, definition_evidence: { ...body.definition_evidence, document: { ...body.definition_evidence.document, ...changes } } }, selectedReference)).rejects.toThrow(DataConnectionContractError)
})
it('refuses invalid addresses and preserves typed selection failures', async () => {
  const body = selectionBody()
  await expect(parseProviderInstrumentSelection({ ...body, instrument: { ...body.instrument, address: 'provider:256265' } }, selectedReference)).rejects.toThrow(DataConnectionContractError)
  await expect(parseProviderInstrumentSelection({ ...body, definition_evidence: { ...body.definition_evidence, address: 'wrong' } }, selectedReference)).rejects.toThrow(DataConnectionContractError)
  const send = transport({ detail: { code: 'INSTRUMENT_SELECTION_UNAVAILABLE', message: 'Unsupported selection' } }, 409)
  await expect(createDataConnectionClient(send).resolveInstrument(selectedReference, new AbortController().signal)).rejects.toMatchObject({ code: 'INSTRUMENT_SELECTION_UNAVAILABLE' })
})
it('rejects an invalid selected token before transport', async () => {
  const send = transport(selectionBody())
  await expect(createDataConnectionClient(send).resolveInstrument({ ...selectedReference, token: 0 }, new AbortController().signal)).rejects.toThrow(DataConnectionContractError)
  expect(send).not.toHaveBeenCalled()
})

it.each(['authority_namespace', 'authority_version'] as const)('rejects changed %s bytes paired with the original root digest', async (field) => {
  const body = selectionBody()
  body.instrument.definition[field] = 'changed'
  await expect(parseProviderInstrumentSelection(body, selectedReference)).rejects.toThrow(DataConnectionContractError)
})
it('rejects a substituted root address even when the evidence points to it', async () => {
  const body = selectionBody()
  body.instrument.address = `sha256:${'f'.repeat(64)}`
  body.definition_evidence.document.instrument_address = body.instrument.address
  body.definition_evidence.address = selectionHash(body.definition_evidence.document)
  await expect(parseProviderInstrumentSelection(body, selectedReference)).rejects.toThrow(DataConnectionContractError)
})
it('rejects source evidence tampering and a self-consistent wrong label or return variant', async () => {
  const tampered = selectionBody()
  tampered.definition_evidence.document.sources[0].excerpt = 'Changed source text'
  await expect(parseProviderInstrumentSelection(tampered, selectedReference)).rejects.toThrow(DataConnectionContractError)
  for (const changes of [{ name: 'Other index' }, { return_type: 'TOTAL_RETURN' }]) {
    const body = selectionBody()
    Object.assign(body.definition_evidence.document.interpretation, changes)
    body.definition_evidence.address = selectionHash(body.definition_evidence.document)
    await expect(parseProviderInstrumentSelection(body, selectedReference)).rejects.toThrow(DataConnectionContractError)
  }
})
it('preserves caller cancellation while checking selection digests', async () => {
  const signal = new AbortController()
  const send = transport(selectionBody())
  signal.abort()
  await expect(createDataConnectionClient(send).resolveInstrument(selectedReference, signal.signal)).rejects.toMatchObject({ name: 'AbortError' })
})

it('accepts a valid digest-bound authority without a client root allowlist', async () => {
  const body = selectionBody()
  body.instrument.definition.authority_namespace = 'synthetic:other-source-reviewed-root'
  body.instrument.definition.authority_version = '2'
  body.instrument.address = selectionHash({ schema: 'canonical-instrument/1', fact: body.instrument.definition })
  body.definition_evidence.document.instrument_address = body.instrument.address
  body.definition_evidence.address = selectionHash(body.definition_evidence.document)
  await expect(parseProviderInstrumentSelection(body, selectedReference)).resolves.toMatchObject({ instrument_address: body.instrument.address })
})


const selectedEquity: ProviderResearchReference = { token: 77, symbol: 'INFY', name: 'INFOSYS', exchange: 'NSE', kind: 'EQUITY' }
function equitySelectionBody() {
  const base = selectionBody()
  const definition = { ...base.instrument.definition, authority_namespace: 'strategy-os:security:isin:INE009A01021', asset_class: 'EQUITY' }
  const address = selectionHash({ schema: 'canonical-instrument/1', fact: definition })
  const document = { ...base.definition_evidence.document, schema: 'strategy-os-equity-definition-reference/1', instrument_address: address,
    interpretation: { name: 'Infosys Limited', symbol: 'INFY', isin: 'INE009A01021', security_class: 'INDIAN_EQUITY', exchange: 'NSE', series: 'EQ', currency: 'INR' } }
  return { ...base, selection: { ...selectedEquity }, instrument: { address, definition }, definition_evidence: { address: selectionHash(document), document } }
}
it('resolves an equity symbol with its legal label while preserving the different provider display name', async () => {
  const body = equitySelectionBody(), send = transport(body)
  const result = await createDataConnectionClient(send).resolveInstrument(selectedEquity, new AbortController().signal)
  expect(result).toEqual({ instrument_address: body.instrument.address, display_name: 'Infosys Limited · NSE · Equity · INR', historical_mapping: 'UNVERIFIED' })
  expect(JSON.parse(send.mock.calls[0][0].body!)).toEqual({ token: 77, symbol: 'INFY', exchange: 'NSE' })
  expect(body.selection.name).not.toBe(body.definition_evidence.document.interpretation.name)
})
it.each([
  { symbol: 'OTHER' }, { isin: 'US4567881085' }, { isin: 'invalid' }, { security_class: 'ADS' },
  { exchange: 'BSE' }, { series: 'BE' }, { currency: 'USD' }, { name: '' }, { name: ' Infosys Limited' },
])('rejects a digest-valid but mismatched equity interpretation %j', async (changes) => {
  const body = equitySelectionBody()
  Object.assign(body.definition_evidence.document.interpretation, changes)
  body.definition_evidence.address = selectionHash(body.definition_evidence.document)
  await expect(parseProviderInstrumentSelection(body, selectedEquity)).rejects.toThrow(DataConnectionContractError)
})
it('rejects an equity evidence ISIN that is not the root namespace even when both digests are valid', async () => {
  const body = equitySelectionBody()
  body.instrument.definition.authority_namespace = 'strategy-os:security:isin:INE000A01010'
  body.instrument.address = selectionHash({ schema: 'canonical-instrument/1', fact: body.instrument.definition })
  body.definition_evidence.document.instrument_address = body.instrument.address
  body.definition_evidence.address = selectionHash(body.definition_evidence.document)
  await expect(parseProviderInstrumentSelection(body, selectedEquity)).rejects.toThrow(DataConnectionContractError)
})
it('keeps equity and index evidence schemas separate', async () => {
  const body = equitySelectionBody()
  body.definition_evidence.document.schema = 'strategy-os-index-definition-reference/1'
  body.definition_evidence.address = selectionHash(body.definition_evidence.document)
  await expect(parseProviderInstrumentSelection(body, selectedEquity)).rejects.toThrow(DataConnectionContractError)
})
it('rejects a BSE equity selection rather than merging its ISIN into the NSE root', async () => {
  const body = equitySelectionBody(), selected = { ...selectedEquity, exchange: 'BSE' as const }
  body.selection = selected
  body.definition_evidence.document.interpretation.exchange = 'BSE'
  body.definition_evidence.address = selectionHash(body.definition_evidence.document)
  await expect(parseProviderInstrumentSelection(body, selected)).rejects.toThrow(DataConnectionContractError)
})

it('rejects a rehashed index root presented for an equity selection', async () => {
  const body = equitySelectionBody()
  body.instrument.definition.asset_class = 'INDEX'
  body.instrument.address = selectionHash({ schema: 'canonical-instrument/1', fact: body.instrument.definition })
  body.definition_evidence.document.instrument_address = body.instrument.address
  body.definition_evidence.address = selectionHash(body.definition_evidence.document)
  await expect(parseProviderInstrumentSelection(body, selectedEquity)).rejects.toThrow(DataConnectionContractError)
})


function savedSelection(reference = providerReference()) {
  const selection = { schema: 'owner-provider-instrument-selection/1', owner_id: 'owner.a', data_account_id: 'data.a', connection_id: 7,
    provider: 'ZERODHA', reference, observed_at: '2026-09-06T06:00:00.123456+00:00' }
  return { schema: 'strategy-os-provider-selection/1', selection_address: selectionHash(selection), selection, research_resolution: 'UNRESOLVED' }
}
it.each([
  providerReference({ token: 77, symbol: 'SMALLCAP', name: 'छोटी कंपनी', segment: 'NSE' }),
  providerReference({ token: 88, symbol: 'SYNTHETIC_FUT', exchange: 'MCX', segment: 'MCX-FUT', instrument_type: 'FUT', expiry: '2026-10-30', lot_size: '100' }),
  providerReference({ token: 99, symbol: 'SYNTHETIC_CE', exchange: 'NFO', segment: 'NFO-OPT', instrument_type: 'CE', expiry: '2026-09-24', strike: '100.25' }),
  providerReference({ token: 100, symbol: '<UNKNOWN & TYPE>', exchange: 'NEW_EX', segment: 'OTHER', instrument_type: 'PROVIDER_NEW', strike: null, lot_size: null, tick_size: null }),
])('saves any well-formed provider instrument without creating a canonical root: $symbol', async (reference) => {
  const body = savedSelection(reference), send = transport(body), signal = new AbortController().signal
  const result = await createDataConnectionClient(send).selectInstrument(reference, signal)
  expect(send.mock.calls[0][0]).toMatchObject({ method: 'POST', path: '/api/v1/data-connections/instrument-selections', csrfRequired: true,
    body: JSON.stringify({ reference }), signal, credentials: 'same-origin', cache: 'no-store', redirect: 'error' })
  expect(result.selection.reference).toEqual(reference)
  expect(result.selection.observed_at).toBe('2026-09-06T06:00:00.123456+00:00')
  expect(result.research_resolution).toBe('UNRESOLVED')
  expect(result).not.toHaveProperty('instrument_address')
  expect(Object.isFrozen(result.selection.reference)).toBe(true)
})
it('searches Unicode and punctuation across a dynamic provider exchange catalogue', async () => {
  const query = 'कंपनी & <shares>', body = { ...instrumentResult(query.toUpperCase(), 'ALL'), available_exchanges: ['NEW_EX'],
    items: [providerReference({ symbol: 'SMALL', exchange: 'NEW_EX', instrument_type: 'NEW_TYPE' })] }
  const send = transport(body)
  const result = await createDataConnectionClient(send).searchInstruments(query, 'ALL', new AbortController().signal)
  expect(result.available_exchanges).toEqual(['NEW_EX'])
  expect(new URLSearchParams(send.mock.calls[0][0].path.split('?')[1]).get('query')).toBe(query)
})
it.each([
  { exchange: '../NSE' }, { exchange: 'x'.repeat(17) }, { segment: 'x'.repeat(33) }, { instrument_type: 'x'.repeat(33) },
  { strike: '10000000000000000000000000' }, { strike: '00' }, { strike: '1e2' }, { strike: 'NaN' }, { lot_size: '0.0' },
  { tick_size: 0.05 }, { expiry: '2026-09-31' }, { expiry: '2026-09-01T00:00:00Z' },
])('refuses malformed generic provider terms %j', (changes) => {
  expect(() => parseProviderReference({ ...providerReference(), ...changes })).toThrow(DataConnectionContractError)
})
it.each([
  { research_resolution: 'READY' }, { selection_address: `sha256:${'f'.repeat(64)}` }, { instrument_address: `sha256:${'e'.repeat(64)}` },
])('rejects forged provider-selection envelopes %j', async (changes) => {
  await expect(parseSavedProviderSelection({ ...savedSelection(), ...changes }, providerReference())).rejects.toThrow(DataConnectionContractError)
})
it.each([
  { owner_id: 'different-owner' }, { data_account_id: 'different-account' }, { connection_id: 8 },
  { observed_at: '2026-09-06T06:00:00.123457+00:00' }, { provider: 'OTHER' }, { connection_id: 0 },
  { observed_at: '2026-09-06T06:00:00+05:30' }, { observed_at: '2026-02-30T06:00:00Z' },
])('rejects changed attribution bytes or invalid observation terms %j', async (changes) => {
  const body = savedSelection()
  await expect(parseSavedProviderSelection({ ...body, selection: { ...body.selection, ...changes } }, providerReference())).rejects.toThrow(DataConnectionContractError)
})
it.each([{ token: 77 }, { exchange: 'MCX' }, { expiry: '2026-12-01' }, { strike: '100' }, { name: 'Different' }])('binds the exact selected provider descriptor even when a substituted record digest is valid %j', async (changes) => {
  await expect(parseSavedProviderSelection(savedSelection(providerReference(changes)), providerReference())).rejects.toThrow(DataConnectionContractError)
})
it('preserves provider-selection cancellation and typed invalid-reference errors', async () => {
  const controller = new AbortController(); controller.abort()
  await expect(createDataConnectionClient(transport(savedSelection())).selectInstrument(providerReference(), controller.signal)).rejects.toMatchObject({ name: 'AbortError' })
  await expect(createDataConnectionClient(transport({ detail: { code: 'INVALID_PROVIDER_REFERENCE', message: 'private details' } }, 422)).selectInstrument(providerReference(), new AbortController().signal)).rejects.toMatchObject({ code: 'INVALID_PROVIDER_REFERENCE' })
})


it('matches the backend canonical JSON and digest vector for Unicode and safe integers', async () => {
  // Generated independently with app.ir.hashing.canonical_json/content_address.
  const value = { z: { b: 'text', a: -2 }, a: [null, true, false, 'é', 3] }
  expect(canonicalJson(value)).toBe('{"a":[null,true,false,"é",3],"z":{"a":-2,"b":"text"}}')
  await expect(contentAddress(value)).resolves.toBe('sha256:e05b9041ba3f8cdc923119a6bf063f1e43beaf279c65710dde3f4224d4f27bd7')
  expect(canonicalJson({ maximum: Number.MAX_SAFE_INTEGER, minimum: Number.MIN_SAFE_INTEGER })).toBe('{"maximum":9007199254740991,"minimum":-9007199254740991}')
})
it('keeps the inclusive canonical nesting bound for containers and scalar leaves', () => {
  let value: unknown = 'edge'
  for (let level = 0; level < 8; level += 1) value = [value]
  expect(canonicalJson(value)).toBe('[[[[[[[["edge"]]]]]]]]')
  expect(() => canonicalJson([value])).toThrow(TypeError)
  expect(() => canonicalJson(null, 9)).toThrow(TypeError)
})
it.each([NaN, Infinity, -Infinity, 1.5, Number.MAX_SAFE_INTEGER + 1, Number.MIN_SAFE_INTEGER - 1,
  undefined, Symbol('unsupported'), 1n, () => undefined, new Date('2026-01-01'), Object.create(null)]
  .map((value) => ({ value })))('rejects unsupported canonical scalar or object values: $value', ({ value }) => {
  expect(() => canonicalJson(value)).toThrow(TypeError)
})
