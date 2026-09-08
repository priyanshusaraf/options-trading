export const ACCOUNT_COMMERCE_REQUEST_BODY_LIMIT = 4_096
export const ACCOUNT_COMMERCE_RESPONSE_BODY_LIMIT = 65_536

const PROFILE_FIELDS = ['profile.country', 'profile.full_name'] as const
const UTC_PATTERN = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{6}))?Z$/

export type ProfileFieldCode = (typeof PROFILE_FIELDS)[number]
export type ProfileState = 'COMPLETE' | 'INCOMPLETE'
export type TrialState = 'AVAILABLE' | 'USED_ACTIVE' | 'USED_EXPIRED'
export type TrialSource = 'BETA_TRIAL' | 'COUPON_REDEMPTION'
export type AccessState = 'ACTIVE' | 'INACTIVE' | 'EXPIRED'

export interface AccountCommerceStatus {
  readonly schema: 'account-commerce-status/1'
  readonly profile_state: ProfileState
  readonly satisfied_field_codes: readonly ProfileFieldCode[]
  readonly profile_attested_at: string | null
  readonly trial_state: TrialState
  readonly trial_source: TrialSource | null
  readonly trial_expires_at: string | null
  readonly access_state: AccessState
  readonly access_expires_at: string | null
  readonly evaluated_at: string
}

export interface AccountCommerceAccess {
  readonly schema: 'account-commerce-access/1'
  readonly state: AccessState
  readonly expires_at: string | null
  readonly evaluated_at: string
}

export interface ProfileEvidence {
  readonly schema: 'account-commerce-profile-evidence/1'
  readonly profile_state: ProfileState
  readonly satisfied_field_codes: readonly ProfileFieldCode[]
  readonly attested_at: string
  readonly replayed: boolean
}

export interface TrialGrant {
  readonly schema: 'account-commerce-trial-grant/1'
  readonly source: TrialSource
  readonly state: 'ACTIVE' | 'EXPIRED'
  readonly expires_at: string
  readonly replayed: boolean
}

export interface BillingUnavailable {
  readonly kind: 'UNAVAILABLE'
  readonly code: 'BILLING_PROVIDER_UNAVAILABLE'
}

export const BILLING_UNAVAILABLE: BillingUnavailable = Object.freeze({
  kind: 'UNAVAILABLE',
  code: 'BILLING_PROVIDER_UNAVAILABLE',
})

export interface AccountCommerceRequestDescriptor {
  readonly method: 'GET' | 'POST'
  readonly path: `/api/v1/account-commerce/${string}`
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

export interface AccountCommerceTransportResponse {
  readonly status: number
  readonly headers: {
    readonly contentType: string
    readonly cacheControl: string
  }
  readonly body: unknown
}

export type AccountCommerceTransport = (
  descriptor: AccountCommerceRequestDescriptor,
) => Promise<AccountCommerceTransportResponse>

export interface AccountCommerceClient {
  load(signal: AbortSignal): Promise<{
    readonly status: AccountCommerceStatus
    readonly billing: BillingUnavailable
  }>
  loadAccess(signal: AbortSignal): Promise<AccountCommerceAccess>
  attestRequiredDetails(
    details: Readonly<{ full_name: string; country: string }>,
    signal: AbortSignal,
  ): Promise<ProfileEvidence>
  activateBeta(signal: AbortSignal): Promise<TrialGrant>
  redeemCoupon(coupon: string, signal: AbortSignal): Promise<TrialGrant>
}

export class AccountCommerceContractError extends Error {
  constructor() {
    super('Account access response did not match the required contract.')
    this.name = 'AccountCommerceContractError'
  }
}

export class AccountCommerceRequestError extends Error {
  readonly status: number
  readonly code: string

  constructor(status: number, code: string) {
    super('Account access request was not accepted.')
    this.name = 'AccountCommerceRequestError'
    this.status = status
    this.code = code
  }
}

function contract(condition: boolean): asserts condition {
  if (!condition) throw new AccountCommerceContractError()
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return value !== null
    && typeof value === 'object'
    && Object.getPrototypeOf(value) === Object.prototype
}

function exactObject(value: unknown, keys: readonly string[]): Record<string, unknown> {
  contract(isPlainObject(value))
  const ownKeys = Reflect.ownKeys(value)
  contract(ownKeys.length === keys.length)
  contract(ownKeys.every((key) => typeof key === 'string' && keys.includes(key)))
  contract(keys.every((key) => Object.prototype.hasOwnProperty.call(value, key)))
  return value
}

function exactString<T extends string>(value: unknown, allowed: readonly T[]): T {
  contract(typeof value === 'string' && allowed.includes(value as T))
  return value as T
}

function canonicalUtc(value: unknown, nullable: true): string | null
function canonicalUtc(value: unknown, nullable: false): string
function canonicalUtc(value: unknown, nullable: boolean): string | null {
  if (value === null) {
    contract(nullable)
    return null
  }
  contract(typeof value === 'string')
  const match = UTC_PATTERN.exec(value)
  contract(match !== null)
  const [, year, month, day, hour, minute, second, fraction = '000000'] = match
  const parts = [year, month, day, hour, minute, second, fraction]
    .map((part) => Number(part))
  contract(parts.every(Number.isInteger))
  contract(parts[0] >= 1 && parts[0] <= 9999)
  const instant = new Date(Date.UTC(
    parts[0], parts[1] - 1, parts[2], parts[3], parts[4], parts[5],
    Math.floor(parts[6] / 1_000),
  ))
  contract(Number.isFinite(instant.getTime()))
  contract(instant.getUTCFullYear() === parts[0])
  contract(instant.getUTCMonth() === parts[1] - 1)
  contract(instant.getUTCDate() === parts[2])
  contract(instant.getUTCHours() === parts[3])
  contract(instant.getUTCMinutes() === parts[4])
  contract(instant.getUTCSeconds() === parts[5])
  return value
}

function compareUtc(left: string, right: string): number {
  return left < right ? -1 : left > right ? 1 : 0
}

function profileCodes(value: unknown): readonly ProfileFieldCode[] {
  contract(Array.isArray(value) && Object.getPrototypeOf(value) === Array.prototype)
  contract(value.every((item) => typeof item === 'string'))
  contract(value.every((item) => PROFILE_FIELDS.includes(item as ProfileFieldCode)))
  contract(new Set(value).size === value.length)
  contract(value.every((item, index) => item === [...value].sort()[index]))
  return Object.freeze([...value]) as readonly ProfileFieldCode[]
}

function validateProfile(state: ProfileState, codes: readonly ProfileFieldCode[]): void {
  const complete = codes.length === PROFILE_FIELDS.length
    && PROFILE_FIELDS.every((field) => codes.includes(field))
  contract((state === 'COMPLETE') === complete)
}

export function parseAccountCommerceAccess(value: unknown): AccountCommerceAccess {
  const object = exactObject(value, ['schema', 'state', 'expires_at', 'evaluated_at'])
  contract(object.schema === 'account-commerce-access/1')
  const state = exactString(object.state, ['ACTIVE', 'INACTIVE', 'EXPIRED'] as const)
  const expiresAt = canonicalUtc(object.expires_at, true)
  const evaluatedAt = canonicalUtc(object.evaluated_at, false)
  if (state === 'ACTIVE') contract(expiresAt === null || compareUtc(expiresAt, evaluatedAt) > 0)
  if (state === 'EXPIRED') contract(expiresAt !== null && compareUtc(expiresAt, evaluatedAt) <= 0)
  return Object.freeze({
    schema: 'account-commerce-access/1', state, expires_at: expiresAt, evaluated_at: evaluatedAt,
  })
}

export function parseAccountCommerceStatus(value: unknown): AccountCommerceStatus {
  const object = exactObject(value, [
    'schema', 'profile_state', 'satisfied_field_codes', 'profile_attested_at',
    'trial_state', 'trial_source', 'trial_expires_at', 'access_state',
    'access_expires_at', 'evaluated_at',
  ])
  contract(object.schema === 'account-commerce-status/1')
  const profileState = exactString(object.profile_state, ['COMPLETE', 'INCOMPLETE'] as const)
  const codes = profileCodes(object.satisfied_field_codes)
  validateProfile(profileState, codes)
  const profileAttestedAt = canonicalUtc(object.profile_attested_at, true)
  if (codes.length > 0) contract(profileAttestedAt !== null)
  const trialState = exactString(object.trial_state, ['AVAILABLE', 'USED_ACTIVE', 'USED_EXPIRED'] as const)
  const trialSource = object.trial_source === null
    ? null
    : exactString(object.trial_source, ['BETA_TRIAL', 'COUPON_REDEMPTION'] as const)
  const trialExpiresAt = canonicalUtc(object.trial_expires_at, true)
  const accessState = exactString(object.access_state, ['ACTIVE', 'INACTIVE', 'EXPIRED'] as const)
  const accessExpiresAt = canonicalUtc(object.access_expires_at, true)
  const evaluatedAt = canonicalUtc(object.evaluated_at, false)

  if (trialState === 'AVAILABLE') {
    contract(trialSource === null && trialExpiresAt === null)
  } else if (trialState === 'USED_ACTIVE') {
    contract(trialSource !== null && trialExpiresAt !== null)
    contract(compareUtc(trialExpiresAt, evaluatedAt) > 0)
  } else {
    contract(trialSource !== null && trialExpiresAt !== null)
    contract(compareUtc(trialExpiresAt, evaluatedAt) <= 0)
  }
  if (accessState === 'ACTIVE') {
    contract(accessExpiresAt === null || compareUtc(accessExpiresAt, evaluatedAt) > 0)
  }
  if (accessState === 'EXPIRED') {
    contract(accessExpiresAt !== null && compareUtc(accessExpiresAt, evaluatedAt) <= 0)
  }

  return Object.freeze({
    schema: 'account-commerce-status/1',
    profile_state: profileState,
    satisfied_field_codes: codes,
    profile_attested_at: profileAttestedAt,
    trial_state: trialState,
    trial_source: trialSource,
    trial_expires_at: trialExpiresAt,
    access_state: accessState,
    access_expires_at: accessExpiresAt,
    evaluated_at: evaluatedAt,
  })
}

export function parseProfileEvidence(value: unknown): ProfileEvidence {
  const object = exactObject(value, [
    'schema', 'profile_state', 'satisfied_field_codes', 'attested_at', 'replayed',
  ])
  contract(object.schema === 'account-commerce-profile-evidence/1')
  const profileState = exactString(object.profile_state, ['COMPLETE', 'INCOMPLETE'] as const)
  const codes = profileCodes(object.satisfied_field_codes)
  validateProfile(profileState, codes)
  const attestedAt = canonicalUtc(object.attested_at, false)
  contract(typeof object.replayed === 'boolean')
  return Object.freeze({
    schema: 'account-commerce-profile-evidence/1',
    profile_state: profileState,
    satisfied_field_codes: codes,
    attested_at: attestedAt,
    replayed: object.replayed,
  })
}

export function parseTrialGrant(value: unknown): TrialGrant {
  const object = exactObject(value, ['schema', 'source', 'state', 'expires_at', 'replayed'])
  contract(object.schema === 'account-commerce-trial-grant/1')
  const source = exactString(object.source, ['BETA_TRIAL', 'COUPON_REDEMPTION'] as const)
  const state = exactString(object.state, ['ACTIVE', 'EXPIRED'] as const)
  const expiresAt = canonicalUtc(object.expires_at, false)
  contract(typeof object.replayed === 'boolean')
  return Object.freeze({
    schema: 'account-commerce-trial-grant/1', source, state,
    expires_at: expiresAt, replayed: object.replayed,
  })
}

export function validateTrialRefresh(trial: TrialGrant, status: AccountCommerceStatus): void {
  const expectedState = trial.state === 'ACTIVE' ? 'USED_ACTIVE' : 'USED_EXPIRED'
  contract(status.trial_source === trial.source)
  contract(status.trial_state === expectedState)
  contract(status.trial_expires_at === trial.expires_at)
}

export function validateProfileRefresh(
  profile: ProfileEvidence,
  status: AccountCommerceStatus,
): void {
  contract(status.profile_state === profile.profile_state)
  contract(status.profile_attested_at === profile.attested_at)
  contract(status.satisfied_field_codes.length === profile.satisfied_field_codes.length)
  contract(status.satisfied_field_codes.every(
    (field, index) => field === profile.satisfied_field_codes[index],
  ))
}

function parseError(status: number, body: unknown): never {
  if (status === 401 || status === 403) {
    const object = exactObject(body, ['error'])
    contract(object.error === 'authentication refused')
    throw new AccountCommerceRequestError(status, 'AUTHENTICATION_REFUSED')
  }
  const object = exactObject(body, ['code', 'message'])
  const accepted = status === 400
    ? ['ACCOUNT_COMMERCE_REQUEST_INVALID', 'Account request is invalid']
    : status === 409
      ? ['ACCOUNT_COMMERCE_CONFLICT', 'Account request conflicts with existing state']
      : status === 503 && object.code === 'BILLING_PROVIDER_UNAVAILABLE'
        ? ['BILLING_PROVIDER_UNAVAILABLE', 'Billing provider is unavailable']
        : status === 503
          ? ['ACCOUNT_COMMERCE_UNAVAILABLE', 'Account service is unavailable']
          : null
  contract(accepted !== null && object.code === accepted[0] && object.message === accepted[1])
  throw new AccountCommerceRequestError(status, accepted[0])
}

function descriptor(
  method: 'GET' | 'POST',
  path: AccountCommerceRequestDescriptor['path'],
  signal: AbortSignal,
  body?: Readonly<Record<string, unknown>>,
): AccountCommerceRequestDescriptor {
  contract(signal instanceof AbortSignal)
  const headers: Record<string, string> = { Accept: 'application/json' }
  let encoded: string | undefined
  if (method === 'POST') {
    headers['Content-Type'] = 'application/json'
    encoded = JSON.stringify(body)
    contract(typeof encoded === 'string')
    contract(new TextEncoder().encode(encoded).byteLength <= ACCOUNT_COMMERCE_REQUEST_BODY_LIMIT)
  }
  return Object.freeze({
    method, path, signal, credentials: 'same-origin', cache: 'no-store', redirect: 'error',
    csrfRequired: method === 'POST', headers: Object.freeze(headers),
    ...(encoded === undefined ? {} : { body: encoded }),
    requestBodyLimitBytes: ACCOUNT_COMMERCE_REQUEST_BODY_LIMIT,
    responseBodyLimitBytes: ACCOUNT_COMMERCE_RESPONSE_BODY_LIMIT,
  })
}

function responseBody(response: AccountCommerceTransportResponse): unknown {
  const outer = exactObject(response, ['status', 'headers', 'body'])
  contract(typeof outer.status === 'number' && Number.isInteger(outer.status))
  const headers = exactObject(outer.headers, ['contentType', 'cacheControl'])
  contract(headers.contentType === 'application/json')
  contract(headers.cacheControl === 'no-store')
  contract(outer.status >= 200 && outer.status <= 599)
  if (outer.status < 200 || outer.status >= 300) parseError(outer.status, outer.body)
  return outer.body
}

export function createAccountCommerceClient(transport: AccountCommerceTransport): AccountCommerceClient {
  async function request<T>(
    method: 'GET' | 'POST',
    path: AccountCommerceRequestDescriptor['path'],
    signal: AbortSignal,
    parse: (value: unknown) => T,
    body?: Readonly<Record<string, unknown>>,
  ): Promise<T> {
    contract(typeof transport === 'function')
    const response = await transport(descriptor(method, path, signal, body))
    if (signal.aborted) throw signal.reason ?? new DOMException('Aborted', 'AbortError')
    return parse(responseBody(response))
  }

  const client: AccountCommerceClient = {
    async load(signal) {
      const status = await request(
        'GET', '/api/v1/account-commerce/status', signal, parseAccountCommerceStatus,
      )
      return Object.freeze({ status, billing: BILLING_UNAVAILABLE })
    },
    loadAccess(signal) {
      return request('GET', '/api/v1/account-commerce/access', signal, parseAccountCommerceAccess)
    },
    attestRequiredDetails(details, signal) {
      const body = exactObject(details, ['full_name', 'country'])
      contract(typeof body.full_name === 'string' && typeof body.country === 'string')
      return request(
        'POST', '/api/v1/account-commerce/profile-evidence', signal, parseProfileEvidence,
        { full_name: body.full_name, country: body.country },
      )
    },
    activateBeta(signal) {
      return request(
        'POST', '/api/v1/account-commerce/trials/beta', signal, parseTrialGrant, {},
      )
    },
    redeemCoupon(coupon, signal) {
      contract(typeof coupon === 'string')
      return request(
        'POST', '/api/v1/account-commerce/trials/coupon', signal, parseTrialGrant, { coupon },
      )
    },
  }
  return Object.freeze(client)
}
