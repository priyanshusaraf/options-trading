import { describe, expect, it, vi } from 'vitest'
import {
  AccountCommerceContractError,
  createAccountCommerceClient,
  parseAccountCommerceAccess,
  parseAccountCommerceStatus,
  parseProfileEvidence,
  parseTrialGrant,
  validateProfileRefresh,
  validateTrialRefresh,
} from './accountCommerceClient'
import type {
  AccountCommerceTransport,
  AccountCommerceTransportResponse,
} from './accountCommerceClient'

const evaluated = '2026-09-02T06:00:00Z'
const expires = '2026-09-17T06:00:00.000000Z'

function response(body: unknown, status = 200): AccountCommerceTransportResponse {
  return { status, headers: { contentType: 'application/json', cacheControl: 'no-store' }, body }
}

function status(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    schema: 'account-commerce-status/1',
    profile_state: 'INCOMPLETE',
    satisfied_field_codes: [],
    profile_attested_at: null,
    trial_state: 'AVAILABLE',
    trial_source: null,
    trial_expires_at: null,
    access_state: 'INACTIVE',
    access_expires_at: null,
    evaluated_at: evaluated,
    ...overrides,
  }
}

function activeStatus(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return status({
    profile_state: 'COMPLETE',
    satisfied_field_codes: ['profile.country', 'profile.full_name'],
    profile_attested_at: evaluated,
    trial_state: 'USED_ACTIVE',
    trial_source: 'BETA_TRIAL',
    trial_expires_at: expires,
    access_state: 'ACTIVE',
    access_expires_at: expires,
    ...overrides,
  })
}

describe('strict parsers', () => {
  it('accepts immutable canonical status, access, profile and trial projections', () => {
    const parsed = parseAccountCommerceStatus(activeStatus())
    expect(Object.isFrozen(parsed)).toBe(true)
    expect(Object.isFrozen(parsed.satisfied_field_codes)).toBe(true)
    expect(parseAccountCommerceAccess({
      schema: 'account-commerce-access/1', state: 'ACTIVE', expires_at: expires,
      evaluated_at: evaluated,
    }).state).toBe('ACTIVE')
    expect(parseProfileEvidence({
      schema: 'account-commerce-profile-evidence/1', profile_state: 'COMPLETE',
      satisfied_field_codes: ['profile.country', 'profile.full_name'],
      attested_at: evaluated, replayed: false,
    }).profile_state).toBe('COMPLETE')
    expect(parseTrialGrant({
      schema: 'account-commerce-trial-grant/1', source: 'BETA_TRIAL', state: 'ACTIVE',
      expires_at: expires, replayed: false,
    }).source).toBe('BETA_TRIAL')
  })

  it.each([
    ['unknown key', activeStatus({ raw_profile: 'private' })],
    ['missing key', (() => { const value = activeStatus(); delete value.evaluated_at; return value })()],
    ['wrong enum', activeStatus({ access_state: 'ENABLED' })],
    ['wrong nullability', activeStatus({ evaluated_at: null })],
    ['offset timestamp', activeStatus({ evaluated_at: '2026-09-02T11:30:00+05:30' })],
    ['invalid calendar', activeStatus({ evaluated_at: '2026-02-30T06:00:00Z' })],
    ['fraction drift', activeStatus({ evaluated_at: '2026-09-02T06:00:00.1Z' })],
    ['duplicate code', activeStatus({ satisfied_field_codes: ['profile.country', 'profile.country'] })],
    ['unknown code', activeStatus({ satisfied_field_codes: ['profile.country', 'profile.raw'] })],
    ['code order drift', activeStatus({ satisfied_field_codes: ['profile.full_name', 'profile.country'] })],
    ['profile drift', activeStatus({ profile_state: 'INCOMPLETE' })],
    ['active trial already expired', activeStatus({ trial_expires_at: '2026-08-18T06:00:00Z' })],
    ['state drift', activeStatus({ trial_state: 'AVAILABLE' })],
  ])('rejects adversarial status: %s', (_name, value) => {
    expect(() => parseAccountCommerceStatus(value)).toThrow(AccountCommerceContractError)
  })

  it('rejects exotic object and array prototypes', () => {
    class StatusRecord {}
    const exotic = Object.assign(new StatusRecord(), status())
    expect(() => parseAccountCommerceStatus(exotic)).toThrow(AccountCommerceContractError)
    const exoticCodes = Object.setPrototypeOf(['profile.country'], null)
    expect(() => parseAccountCommerceStatus(status({
      satisfied_field_codes: exoticCodes, profile_attested_at: evaluated,
    }))).toThrow(AccountCommerceContractError)
  })

  it('accepts retained INACTIVE expiry and independently authoritative trial/access facts', () => {
    expect(parseAccountCommerceAccess({
      schema: 'account-commerce-access/1', state: 'INACTIVE',
      expires_at: '2026-08-16T06:00:00Z', evaluated_at: evaluated,
    })).toMatchObject({ state: 'INACTIVE', expires_at: '2026-08-16T06:00:00Z' })
    expect(parseAccountCommerceStatus(activeStatus({
      access_state: 'INACTIVE', access_expires_at: '2026-08-16T06:00:00Z',
    }))).toMatchObject({ trial_state: 'USED_ACTIVE', access_state: 'INACTIVE' })
  })

  it('accepts an empty profile-code list with a retained canonical attestation time', () => {
    expect(parseAccountCommerceStatus(status({ profile_attested_at: evaluated })))
      .toMatchObject({ satisfied_field_codes: [], profile_attested_at: evaluated })
  })

  it.each(['symbol', 'hidden'] as const)('rejects %s extra own keys without sentinel retention', (kind) => {
    const value = status() as Record<PropertyKey, unknown>
    if (kind === 'symbol') value[Symbol('private')] = 'PRIVATE-SENTINEL'
    else Object.defineProperty(value, 'private', { value: 'PRIVATE-SENTINEL' })
    let thrown: unknown
    try { parseAccountCommerceStatus(value) } catch (error) { thrown = error }
    expect(thrown).toBeInstanceOf(AccountCommerceContractError)
    expect(String(thrown)).not.toContain('PRIVATE-SENTINEL')
  })

  it('rejects mutation-to-refresh drift', () => {
    const trial = parseTrialGrant({
      schema: 'account-commerce-trial-grant/1', source: 'BETA_TRIAL', state: 'ACTIVE',
      expires_at: expires, replayed: false,
    })
    expect(() => validateTrialRefresh(trial, parseAccountCommerceStatus(activeStatus({
      trial_source: 'COUPON_REDEMPTION',
    })))).toThrow(AccountCommerceContractError)
    const profile = parseProfileEvidence({
      schema: 'account-commerce-profile-evidence/1', profile_state: 'COMPLETE',
      satisfied_field_codes: ['profile.country', 'profile.full_name'],
      attested_at: evaluated, replayed: false,
    })
    expect(() => validateProfileRefresh(profile, parseAccountCommerceStatus(activeStatus({
      profile_attested_at: '2026-09-02T06:01:00Z',
    })))).toThrow(AccountCommerceContractError)
  })
})

describe('injected request descriptor client', () => {
  it('uses one strict relative credentialed bounded GET descriptor', async () => {
    const transport = vi.fn<AccountCommerceTransport>().mockResolvedValue(response(status()))
    const controller = new AbortController()
    const result = await createAccountCommerceClient(transport).load(controller.signal)
    expect(result.billing).toEqual({ kind: 'UNAVAILABLE', code: 'BILLING_PROVIDER_UNAVAILABLE' })
    expect(transport).toHaveBeenCalledWith({
      method: 'GET', path: '/api/v1/account-commerce/status', signal: controller.signal,
      credentials: 'same-origin', cache: 'no-store', redirect: 'error', csrfRequired: false,
      headers: { Accept: 'application/json' }, requestBodyLimitBytes: 4096,
      responseBodyLimitBytes: 65536,
    })
  })

  it('marks every POST CSRF-required and sends beta as exact empty JSON', async () => {
    const transport = vi.fn<AccountCommerceTransport>().mockResolvedValue(response({
      schema: 'account-commerce-trial-grant/1', source: 'BETA_TRIAL', state: 'ACTIVE',
      expires_at: expires, replayed: false,
    }))
    await createAccountCommerceClient(transport).activateBeta(new AbortController().signal)
    expect(transport.mock.calls[0][0]).toMatchObject({
      method: 'POST', path: '/api/v1/account-commerce/trials/beta', csrfRequired: true,
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' }, body: '{}',
      credentials: 'same-origin', cache: 'no-store', redirect: 'error',
      requestBodyLimitBytes: 4096, responseBodyLimitBytes: 65536,
    })
  })

  it('keeps coupon plaintext only in the single request body', async () => {
    const transport = vi.fn<AccountCommerceTransport>().mockResolvedValue(response({
      schema: 'account-commerce-trial-grant/1', source: 'COUPON_REDEMPTION', state: 'ACTIVE',
      expires_at: expires, replayed: false,
    }))
    await createAccountCommerceClient(transport).redeemCoupon('ONE-TIME-SECRET', new AbortController().signal)
    const descriptor = transport.mock.calls[0][0]
    expect(descriptor.path).not.toContain('ONE-TIME-SECRET')
    expect(descriptor.body).toBe('{"coupon":"ONE-TIME-SECRET"}')
    expect(JSON.stringify({ ...descriptor, body: undefined })).not.toContain('ONE-TIME-SECRET')
  })

  it.each([
    [{ contentType: 'text/html', cacheControl: 'no-store' }, 'wrong content type'],
    [{ contentType: 'application/json', cacheControl: 'private' }, 'wrong cache policy'],
  ])('fails closed on response headers: %s', async (headers) => {
    const transport: AccountCommerceTransport = async () => ({ status: 200, headers, body: status() })
    await expect(createAccountCommerceClient(transport).load(new AbortController().signal))
      .rejects.toBeInstanceOf(AccountCommerceContractError)
  })

  it('accepts only fixed privacy-safe errors', async () => {
    const fixed: AccountCommerceTransport = async () => response({
      code: 'ACCOUNT_COMMERCE_CONFLICT', message: 'Account request conflicts with existing state',
    }, 409)
    await expect(createAccountCommerceClient(fixed).load(new AbortController().signal))
      .rejects.toMatchObject({
        name: 'AccountCommerceRequestError', status: 409, code: 'ACCOUNT_COMMERCE_CONFLICT',
      })
    const leaking: AccountCommerceTransport = async () => response({
      code: 'ACCOUNT_COMMERCE_CONFLICT', message: 'coupon SECRET failed',
    }, 409)
    await expect(createAccountCommerceClient(leaking).load(new AbortController().signal))
      .rejects.toBeInstanceOf(AccountCommerceContractError)
  })

  it('does not parse or project a late completion after abort', async () => {
    let resolve!: (value: AccountCommerceTransportResponse) => void
    const transport: AccountCommerceTransport = () => new Promise((done) => { resolve = done })
    const controller = new AbortController()
    const pending = createAccountCommerceClient(transport).load(controller.signal)
    controller.abort()
    resolve(response(activeStatus({ raw_profile: 'must-never-parse' })))
    await expect(pending).rejects.toMatchObject({ name: 'AbortError' })
  })

  it('does not retain a projection when strict parsing fails', async () => {
    let payload: Record<string, unknown> | null = activeStatus({ raw_profile: 'private' })
    const transport: AccountCommerceTransport = async () => response(payload)
    const client = createAccountCommerceClient(transport)
    await expect(client.load(new AbortController().signal)).rejects.toBeInstanceOf(AccountCommerceContractError)
    payload = status()
    await expect(client.load(new AbortController().signal)).resolves.toMatchObject({
      status: { access_state: 'INACTIVE' },
    })
  })
})
