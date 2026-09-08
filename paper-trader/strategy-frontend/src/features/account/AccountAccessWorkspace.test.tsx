import { readFileSync } from 'node:fs'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AccountAccessWorkspace } from './AccountAccessWorkspace'
import {
  BILLING_UNAVAILABLE,
  AccountCommerceRequestError,
  parseAccountCommerceStatus,
  parseProfileEvidence,
  parseTrialGrant,
} from './accountCommerceClient'
import type {
  AccountCommerceClient,
  AccountCommerceStatus,
  ProfileEvidence,
  TrialGrant,
} from './accountCommerceClient'

afterEach(cleanup)

const evaluated = '2026-09-02T06:00:00Z'
const expires = '2026-09-17T06:00:00.000000Z'

function status(overrides: Record<string, unknown> = {}): AccountCommerceStatus {
  return parseAccountCommerceStatus({
    schema: 'account-commerce-status/1', profile_state: 'INCOMPLETE',
    satisfied_field_codes: [], profile_attested_at: null, trial_state: 'AVAILABLE',
    trial_source: null, trial_expires_at: null, access_state: 'INACTIVE',
    access_expires_at: null, evaluated_at: evaluated, ...overrides,
  })
}

function completeAvailable(): AccountCommerceStatus {
  return status({
    profile_state: 'COMPLETE', satisfied_field_codes: ['profile.country', 'profile.full_name'],
    profile_attested_at: evaluated,
  })
}

function active(source: 'BETA_TRIAL' | 'COUPON_REDEMPTION' = 'BETA_TRIAL'): AccountCommerceStatus {
  return status({
    profile_state: 'COMPLETE', satisfied_field_codes: ['profile.country', 'profile.full_name'],
    profile_attested_at: evaluated, trial_state: 'USED_ACTIVE', trial_source: source,
    trial_expires_at: expires, access_state: 'ACTIVE', access_expires_at: expires,
  })
}

function expired(): AccountCommerceStatus {
  return status({
    profile_state: 'COMPLETE', satisfied_field_codes: ['profile.country', 'profile.full_name'],
    profile_attested_at: '2026-08-01T06:00:00Z', trial_state: 'USED_EXPIRED',
    trial_source: 'BETA_TRIAL', trial_expires_at: '2026-08-16T06:00:00Z',
    access_state: 'EXPIRED', access_expires_at: '2026-08-16T06:00:00Z',
  })
}

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((ok, no) => { resolve = ok; reject = no })
  return { promise, resolve, reject }
}

function client(initial: AccountCommerceStatus): AccountCommerceClient & {
  load: ReturnType<typeof vi.fn<AccountCommerceClient['load']>>
  attestRequiredDetails: ReturnType<typeof vi.fn<AccountCommerceClient['attestRequiredDetails']>>
  activateBeta: ReturnType<typeof vi.fn<AccountCommerceClient['activateBeta']>>
  redeemCoupon: ReturnType<typeof vi.fn<AccountCommerceClient['redeemCoupon']>>
} {
  return {
    load: vi.fn<AccountCommerceClient['load']>().mockResolvedValue({ status: initial, billing: BILLING_UNAVAILABLE }),
    loadAccess: vi.fn<AccountCommerceClient['loadAccess']>(),
    attestRequiredDetails: vi.fn<AccountCommerceClient['attestRequiredDetails']>(),
    activateBeta: vi.fn<AccountCommerceClient['activateBeta']>(),
    redeemCoupon: vi.fn<AccountCommerceClient['redeemCoupon']>(),
  }
}

describe('account plan states', () => {
  it('reserves the plan footprint while loading without unavailable-feature panels', () => {
    const loading = deferred<{ status: AccountCommerceStatus; billing: typeof BILLING_UNAVAILABLE }>()
    const api = client(status()); api.load.mockReturnValue(loading.promise)
    render(<AccountAccessWorkspace client={api} />)
    expect(screen.getByRole('status')).toHaveTextContent('Loading your account…')
    expect(screen.queryByRole('heading', { name: 'Billing' })).not.toBeInTheDocument()
    expect(screen.queryByText('Required')).not.toBeInTheDocument()
  })

  it('removes all facts on load error and retries', async () => {
    const api = client(status())
    api.load.mockRejectedValueOnce(new Error('private transport details')).mockResolvedValueOnce({ status: status(), billing: BILLING_UNAVAILABLE })
    render(<AccountAccessWorkspace client={api} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load your account')
    expect(screen.queryByText('Server evaluated')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(await screen.findByRole('heading', { name: 'Your plan' })).toBeInTheDocument()
    expect(api.load).toHaveBeenCalledTimes(2)
  })

  it('shows the needed setup form without profile codes or attestation details', async () => {
    const emptyApi = client(status())
    const { unmount } = render(<AccountAccessWorkspace client={emptyApi} />)
    expect(await screen.findByRole('heading', { name: 'Finish setting up your account' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Save details' })).toBeInTheDocument()
    unmount()
    const partialApi = client(status({
      satisfied_field_codes: ['profile.country'], profile_attested_at: evaluated,
    }))
    render(<AccountAccessWorkspace client={partialApi} />)
    expect(await screen.findByRole('heading', { name: 'Finish setting up your account' })).toBeInTheDocument()
    expect(screen.queryByText('profile.country')).not.toBeInTheDocument()
    expect(screen.queryByText(/Attested|Server evaluated|Access lifecycle/)).not.toBeInTheDocument()
    expect(screen.getByLabelText('Full name')).toHaveValue('')
  })

  it('shows the plan status and expiry once, without unavailable actions', async () => {
    const availableApi = client(completeAvailable())
    const first = render(<AccountAccessWorkspace client={availableApi} />)
    expect(await screen.findByRole('button', { name: 'Start 15-day beta' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Redeem coupon' })).toBeInTheDocument()
    for (const absent of ['Checkout', 'Subscribe', 'Refund', 'Contact support', 'Sign in with Google', 'Admin']) {
      expect(screen.queryByRole('button', { name: new RegExp(absent, 'i') })).not.toBeInTheDocument()
    }
    first.unmount()
    const activeView = render(<AccountAccessWorkspace client={client(active())} />)
    expect((await screen.findAllByText('15-day beta')).length).toBeGreaterThan(0)
    expect(screen.getAllByText('Active')).toHaveLength(1)
    expect(screen.getAllByText('Expires')).toHaveLength(1)
    expect(screen.getByText('Expires').nextElementSibling?.querySelector('time')).toHaveAttribute('datetime', expires)
    expect(screen.queryByRole('heading', { name: 'Product access' })).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Access lifecycle' })).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Your plan', level: 2 })).toBeInTheDocument()
    activeView.unmount()
    render(<AccountAccessWorkspace client={client(expired())} />)
    expect(await screen.findAllByText('Expired')).not.toHaveLength(0)
    expect(screen.queryByRole('button', { name: 'Start 15-day beta' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Redeem coupon' })).not.toBeInTheDocument()
  })
})

describe('forms, privacy and mutation semantics', () => {
  it('validates on blur and focuses a linked submit error summary', async () => {
    const api = client(status())
    render(<AccountAccessWorkspace client={api} />)
    const name = await screen.findByLabelText('Full name')
    fireEvent.blur(name)
    expect(screen.getByText('Enter your full name.')).toBeInTheDocument()
    expect(name).toHaveAttribute('aria-invalid', 'true')
    expect(name).toHaveAttribute('aria-describedby', 'account-full-name-error')
    fireEvent.submit(screen.getByRole('button', { name: 'Save details' }).closest('form')!)
    const summary = screen.getByRole('alert')
    await waitFor(() => expect(summary).toHaveFocus())
    const link = screen.getByRole('link', { name: 'Enter your full name.' })
    fireEvent.click(link)
    expect(name).toHaveFocus()
    expect(api.attestRequiredDetails).not.toHaveBeenCalled()
  })

  it('clears successful profile values before refresh and validates the receipt', async () => {
    const api = client(status())
    const receipt: ProfileEvidence = parseProfileEvidence({
      schema: 'account-commerce-profile-evidence/1', profile_state: 'COMPLETE',
      satisfied_field_codes: ['profile.country', 'profile.full_name'],
      attested_at: evaluated, replayed: false,
    })
    const revalidation = deferred<{ status: AccountCommerceStatus; billing: typeof BILLING_UNAVAILABLE }>()
    api.attestRequiredDetails.mockResolvedValue(receipt)
    api.load.mockResolvedValueOnce({ status: status(), billing: BILLING_UNAVAILABLE }).mockReturnValueOnce(revalidation.promise)
    render(<AccountAccessWorkspace client={api} />)
    fireEvent.change(await screen.findByLabelText('Full name'), { target: { value: 'Ada Lovelace' } })
    fireEvent.change(screen.getByLabelText('Country'), { target: { value: 'in' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save details' }))
    await waitFor(() => expect(api.attestRequiredDetails).toHaveBeenCalledWith({ full_name: 'Ada Lovelace', country: 'IN' }, expect.any(AbortSignal)))
    await waitFor(() => expect(screen.queryByDisplayValue('Ada Lovelace')).not.toBeInTheDocument())
    act(() => revalidation.resolve({ status: completeAvailable(), billing: BILLING_UNAVAILABLE }))
    expect(await screen.findByRole('button', { name: 'Start 15-day beta' })).toBeInTheDocument()
  })

  it('retains volatile profile values after a safe fixed failure', async () => {
    const api = client(status())
    api.attestRequiredDetails.mockRejectedValue(new AccountCommerceRequestError(400, 'ACCOUNT_COMMERCE_REQUEST_INVALID'))
    render(<AccountAccessWorkspace client={api} />)
    fireEvent.change(await screen.findByLabelText('Full name'), { target: { value: 'Ada Lovelace' } })
    fireEvent.change(screen.getByLabelText('Country'), { target: { value: 'IN' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save details' }))
    expect(await screen.findByText('Check the required details and try again.')).toBeInTheDocument()
    expect(screen.getByLabelText('Full name')).toHaveValue('Ada Lovelace')
    expect(screen.getByLabelText('Country')).toHaveValue('IN')
  })

  it('sends beta as a client-owned exact empty request and refreshes against its receipt', async () => {
    const api = client(completeAvailable())
    const grant: TrialGrant = parseTrialGrant({
      schema: 'account-commerce-trial-grant/1', source: 'BETA_TRIAL', state: 'ACTIVE',
      expires_at: expires, replayed: false,
    })
    api.activateBeta.mockResolvedValue(grant)
    api.load.mockResolvedValueOnce({ status: completeAvailable(), billing: BILLING_UNAVAILABLE })
      .mockResolvedValueOnce({ status: active(), billing: BILLING_UNAVAILABLE })
    render(<AccountAccessWorkspace client={api} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Start 15-day beta' }))
    await waitFor(() => expect(api.activateBeta).toHaveBeenCalledWith(expect.any(AbortSignal)))
    expect(await screen.findByText('Active')).toBeInTheDocument()
  })

  it('announces each pending action while retaining the last confirmed plan', async () => {
    const profilePending = deferred<ProfileEvidence>()
    const profileApi = client(status())
    profileApi.attestRequiredDetails.mockReturnValue(profilePending.promise)
    const profileView = render(<AccountAccessWorkspace client={profileApi} />)
    fireEvent.change(await screen.findByLabelText('Full name'), { target: { value: 'Ada Lovelace' } })
    fireEvent.change(screen.getByLabelText('Country'), { target: { value: 'IN' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save details' }))
    await waitFor(() => expect(screen.getAllByText('Saving details…')).toHaveLength(2))
    expect(screen.getByText('Updating account…')).toBeInTheDocument()
    profileView.unmount()

    const betaPending = deferred<TrialGrant>()
    const betaApi = client(completeAvailable())
    betaApi.activateBeta.mockReturnValue(betaPending.promise)
    const betaView = render(<AccountAccessWorkspace client={betaApi} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Start 15-day beta' }))
    await waitFor(() => expect(screen.getAllByText('Starting 15-day beta…')).toHaveLength(2))
    expect(screen.getByText('Updating account…')).toBeInTheDocument()
    betaView.unmount()

    const couponPending = deferred<TrialGrant>()
    const couponApi = client(completeAvailable())
    couponApi.redeemCoupon.mockReturnValue(couponPending.promise)
    const couponView = render(<AccountAccessWorkspace client={couponApi} />)
    fireEvent.change(await screen.findByLabelText('Coupon'), { target: { value: 'ONE-TIME-SECRET' } })
    fireEvent.click(screen.getByRole('button', { name: 'Redeem coupon' }))
    await waitFor(() => expect(screen.getAllByText('Redeeming coupon…')).toHaveLength(2))
    expect(screen.getByText('Updating account…')).toBeInTheDocument()
    expect(document.body.textContent).not.toContain('ONE-TIME-SECRET')
    couponView.unmount()
  })

  it('clears coupon state and the DOM before success, error, abort or network promises settle', async () => {
    const outcomes = [
      { kind: 'success' as const },
      { kind: 'error' as const },
      { kind: 'abort' as const },
      { kind: 'network' as const },
    ]
    for (const outcome of outcomes) {
      const pending = deferred<TrialGrant>()
      const api = client(completeAvailable())
      api.redeemCoupon.mockReturnValue(pending.promise)
      const view = render(<AccountAccessWorkspace client={api} />)
      const input = await screen.findByLabelText('Coupon')
      fireEvent.change(input, { target: { value: 'ONE-TIME-SECRET' } })
      fireEvent.click(screen.getByRole('button', { name: 'Redeem coupon' }))
      expect(input).toHaveValue('')
      expect(document.body.textContent).not.toContain('ONE-TIME-SECRET')
      expect(api.redeemCoupon).toHaveBeenCalledWith('ONE-TIME-SECRET', expect.any(AbortSignal))
      if (outcome.kind === 'success') {
        api.load.mockResolvedValueOnce({ status: active('COUPON_REDEMPTION'), billing: BILLING_UNAVAILABLE })
        act(() => pending.resolve(parseTrialGrant({
          schema: 'account-commerce-trial-grant/1', source: 'COUPON_REDEMPTION', state: 'ACTIVE',
          expires_at: expires, replayed: false,
        })))
        expect(await screen.findByText('Active')).toBeInTheDocument()
        expect(screen.getByText('Coupon access')).toBeInTheDocument()
      } else if (outcome.kind === 'error') {
        act(() => pending.reject(new AccountCommerceRequestError(409, 'ACCOUNT_COMMERCE_CONFLICT')))
        expect(await screen.findByText(/Refresh before trying again/)).toBeInTheDocument()
      } else if (outcome.kind === 'network') {
        act(() => pending.reject(new TypeError('network secret')))
        expect(await screen.findByText(/temporarily unavailable/)).toBeInTheDocument()
      } else {
        view.unmount()
        act(() => pending.reject(new DOMException('Aborted', 'AbortError')))
      }
      expect(document.body.textContent).not.toContain('ONE-TIME-SECRET')
      view.unmount()
    }
  })

  it('aborts every in-flight call and ignores late completion after unmount', async () => {
    const pending = deferred<{ status: AccountCommerceStatus; billing: typeof BILLING_UNAVAILABLE }>()
    let signal: AbortSignal | undefined
    const api = client(status())
    api.load.mockImplementation((ownedSignal) => { signal = ownedSignal; return pending.promise })
    const view = render(<AccountAccessWorkspace client={api} />)
    expect(screen.getByRole('status')).toBeInTheDocument()
    await waitFor(() => expect(signal).toBeDefined())
    view.unmount()
    expect(signal?.aborted).toBe(true)
    await act(async () => pending.resolve({ status: active(), billing: BILLING_UNAVAILABLE }))
    expect(screen.queryByRole('heading', { name: 'Your plan', level: 2 })).not.toBeInTheDocument()
  })
})

it('keeps feature sources free of second transports, persistence, analytics and excluded actions', () => {
  const sources = ['AccountAccessWorkspace.tsx', 'accountCommerceClient.ts']
    .map((name) => readFileSync(new URL(name, import.meta.url), 'utf8')).join('\n')
  for (const forbidden of [
    'fetch' + '(', 'XMLHttpRequest', 'EventSource', 'WebSocket', 'localStorage', 'sessionStorage',
    'Strategy' + 'Api', 'analytics.', 'track' + '(', '/billing/checkout', '/billing/payment',
    '/billing/refund', '/auth/google', '/auth/email', '/support/', '/admin/',
  ]) expect(sources).not.toContain(forbidden)
  expect(sources).not.toMatch(/console\.(log|warn|error)/)
})
