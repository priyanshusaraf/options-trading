import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { createMemoryRouter, RouterProvider, useLocation } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AccountAccessGate } from './AccountAccessGate'
import type { AccountCommerceClient, AccountCommerceStatus } from '../features/account/accountCommerceClient'

const baseStatus: AccountCommerceStatus = {
  schema: 'account-commerce-status/1', profile_state: 'COMPLETE',
  satisfied_field_codes: ['profile.country', 'profile.full_name'],
  profile_attested_at: '2026-09-02T06:00:00Z', trial_state: 'USED_ACTIVE',
  trial_source: 'BETA_TRIAL', trial_expires_at: '2026-09-17T06:00:00Z',
  access_state: 'ACTIVE', access_expires_at: '2026-09-17T06:00:00Z',
  evaluated_at: '2026-09-02T06:00:00Z',
}

afterEach(() => cleanup())

function Content() {
  return <div>private:{useLocation().pathname}</div>
}

function harness(status: AccountCommerceStatus, path: string) {
  const client = { load: vi.fn().mockResolvedValue({ status, billing: { kind: 'UNAVAILABLE', code: 'BILLING_PROVIDER_UNAVAILABLE' } }) } as unknown as AccountCommerceClient
  const router = createMemoryRouter([{
    path: '*', element: <AccountAccessGate client={client}><Content /></AccountAccessGate>,
  }], { initialEntries: [path] })
  render(<RouterProvider router={router} />)
  return { client, router }
}

describe('AccountAccessGate', () => {
  it.each([
    ['INACTIVE', '/strategies'], ['EXPIRED', '/strategies'], ['INACTIVE', '/'],
  ] as const)('replaces an ineligible %s target with Account', async (access_state, path) => {
    const { router } = harness({ ...baseStatus, access_state }, path)
    await waitFor(() => expect(router.state.location.pathname).toBe('/account'))
    expect(await screen.findByText('private:/account')).toBeInTheDocument()
  })

  it('keeps active direct Account and strategy deep links', async () => {
    const account = harness(baseStatus, '/account')
    expect(await screen.findByText('private:/account')).toBeInTheDocument()
    account.router.dispose()
    harness(baseStatus, '/strategies/project/graph')
    expect(await screen.findByText('private:/strategies/project/graph')).toBeInTheDocument()
  })

  it('keeps active root on Home', async () => {
    const { router } = harness(baseStatus, '/')
    expect(await screen.findByText('private:/')).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/')
  })

  it('unmounts prior facts while a new path is pending', async () => {
    let resolveSecond!: (value: unknown) => void
    const client = { load: vi.fn()
      .mockResolvedValueOnce({ status: baseStatus, billing: { kind: 'UNAVAILABLE', code: 'BILLING_PROVIDER_UNAVAILABLE' } })
      .mockImplementationOnce(() => new Promise((resolve) => { resolveSecond = resolve })) } as unknown as AccountCommerceClient
    const router = createMemoryRouter([{ path: '*', element: <AccountAccessGate client={client}><Content /></AccountAccessGate> }], { initialEntries: ['/account'] })
    render(<RouterProvider router={router} />)
    expect(await screen.findByText('private:/account')).toBeInTheDocument()
    await router.navigate('/strategies')
    await waitFor(() => expect(screen.queryByText('private:/account')).not.toBeInTheDocument())
    expect(screen.getByRole('status')).toBeInTheDocument()
    resolveSecond({ status: baseStatus, billing: { kind: 'UNAVAILABLE', code: 'BILLING_PROVIDER_UNAVAILABLE' } })
    expect(await screen.findByText('private:/strategies')).toBeInTheDocument()
  })

  it('shows a focused fact-free closed error', async () => {
    const client = { load: vi.fn().mockRejectedValue(new Error('private sentinel')) } as unknown as AccountCommerceClient
    const router = createMemoryRouter([{ path: '*', element: <AccountAccessGate client={client}><Content /></AccountAccessGate> }], { initialEntries: ['/strategies'] })
    render(<RouterProvider router={router} />)
    const heading = await screen.findByRole('heading', { name: 'Account access could not be verified' })
    await waitFor(() => expect(heading).toHaveFocus())
    expect(document.body.textContent).not.toContain('private sentinel')
    expect(screen.queryByText(/private:/)).not.toBeInTheDocument()
  })
})
