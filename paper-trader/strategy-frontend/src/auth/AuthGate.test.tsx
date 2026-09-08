import { chooseSelect } from '../test/select'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import App from '../App'
import release from '../test/releaseManifest.json'
import { StrategyApi } from '../shell/api'
import { parseBrowserSession } from '../shell/contracts'
import { AccountSecurityControls, AuthGate } from './AuthGate'

const session = { user: { id: 'synthetic.user', display_name: 'Synthetic Alice' }, organization_id: 'synthetic.org',
  memberships: [{ organization_id: 'synthetic.org', name: 'Synthetic workspace', role: 'owner' }], expires_at: '2026-08-30T00:00:00Z', csrf: 'b'.repeat(64) }
const accountStatus = { schema: 'account-commerce-status/1', profile_state: 'COMPLETE',
  satisfied_field_codes: ['profile.country', 'profile.full_name'], profile_attested_at: '2026-08-29T00:00:00Z',
  trial_state: 'USED_ACTIVE', trial_source: 'BETA_TRIAL', trial_expires_at: '2026-09-13T00:00:00Z',
  access_state: 'ACTIVE', access_expires_at: '2026-09-13T00:00:00Z', evaluated_at: '2026-08-29T00:00:00Z' }
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'content-type': 'application/json', 'cache-control': 'no-store' } })
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

it('reveals only the requested login password without changing its input contract or submitting', async () => {
  const authenticate = vi.fn(async () => session)
  const api = {
    session: vi.fn(async () => { throw new (await import('../shell/api')).ApiError('access', 'signed out') }),
    authenticate,
    accountAction: vi.fn(),
  } as unknown as StrategyApi
  render(<AuthGate api={api}><div>Private product</div></AuthGate>)

  const password = await screen.findByLabelText('Password')
  const show = screen.getByRole('button', { name: 'Show password' })
  expect(password).toHaveAttribute('type', 'password')
  expect(password).toHaveAttribute('name', 'password')
  expect(password).toHaveAttribute('id', 'auth-password')
  expect(password).toHaveAttribute('autocomplete', 'current-password')
  expect(password).toHaveAttribute('maxlength', '512')
  expect(password).toBeRequired()
  expect(password).toHaveAttribute('aria-describedby', 'auth-password-help')
  expect(show).toHaveAttribute('type', 'button')
  expect(show).toHaveAttribute('aria-controls', 'auth-password')
  expect(show).toHaveAttribute('aria-pressed', 'false')

  const submittedValue = 'x'.repeat(18)
  fireEvent.change(password, { target: { value: submittedValue } })
  password.focus()
  ;(password as HTMLInputElement).setSelectionRange(3, 9)
  fireEvent.click(show)
  expect(authenticate).not.toHaveBeenCalled()
  expect(password).toHaveAttribute('type', 'text')
  expect(password).toHaveValue(submittedValue)
  expect(password).toHaveFocus()
  expect((password as HTMLInputElement).selectionStart).toBe(3)
  expect((password as HTMLInputElement).selectionEnd).toBe(9)
  expect(show).toHaveAccessibleName('Hide password')
  expect(show).toHaveAttribute('aria-pressed', 'true')

  show.focus()
  fireEvent.click(show)
  expect(show).toHaveFocus()
  expect(password).toHaveAttribute('type', 'password')
  fireEvent.submit(password.closest('form') as HTMLFormElement)
  expect(authenticate).toHaveBeenCalledWith('login', { email: '', password: submittedValue }, expect.any(AbortSignal))
  expect(localStorage.length).toBe(0)
  expect(sessionStorage.length).toBe(0)
})

it('keeps account password visibility independent and preserves action payloads', async () => {
  const accountAction = vi.fn(async () => undefined)
  const api = {
    session: vi.fn(async () => session),
    authenticate: vi.fn(),
    accountAction,
  } as unknown as StrategyApi
  render(<AuthGate api={api}><AccountSecurityControls /></AuthGate>)
  await screen.findByRole('heading', { name: 'Security' })
  const signOut = screen.getByRole('button', { name: 'Sign out' })
  expect(signOut.closest('header')).toContainElement(screen.getByRole('heading', { name: 'Security' }))
  expect(screen.queryByText(/Signed in as/)).not.toBeInTheDocument()
  expect(screen.queryByLabelText('Workspace')).not.toBeInTheDocument()
  expect(screen.getByText('Change password').closest('details')).not.toHaveAttribute('open')
  fireEvent.click(screen.getByText('Change password'))
  fireEvent.click(screen.getByText('Sign out on all devices', { selector: 'summary' }))

  const current = screen.getByLabelText('Current password')
  const next = screen.getByLabelText('New password')
  const revoke = screen.getByLabelText('Confirm your password')
  expect(screen.getByText(/including this one/)).toBeInTheDocument()
  expect([current, next, revoke].every((input) => input.getAttribute('type') === 'password')).toBe(true)
  expect(next).toHaveAttribute('autocomplete', 'new-password')
  expect(current).toHaveAttribute('autocomplete', 'current-password')
  expect(revoke).toHaveAttribute('autocomplete', 'current-password')

  fireEvent.change(current, { target: { value: 'c'.repeat(18) } })
  fireEvent.change(next, { target: { value: 'n'.repeat(18) } })
  fireEvent.change(revoke, { target: { value: 'r'.repeat(18) } })
  fireEvent.click(screen.getByRole('button', { name: 'Show current password' }))
  expect(current).toHaveAttribute('type', 'text')
  expect(next).toHaveAttribute('type', 'password')
  expect(revoke).toHaveAttribute('type', 'password')
  expect(screen.getByRole('button', { name: 'Hide current password' })).toHaveAttribute('aria-pressed', 'true')

  fireEvent.submit(next.closest('form') as HTMLFormElement)
  expect(accountAction).toHaveBeenCalledWith('password', { password: 'c'.repeat(18), new_password: 'n'.repeat(18) }, expect.any(AbortSignal))
  await act(async () => undefined)
  fireEvent.submit(revoke.closest('form') as HTMLFormElement)
  expect(accountAction).toHaveBeenLastCalledWith('logout-all', { password: 'r'.repeat(18) }, expect.any(AbortSignal))
  await act(async () => undefined)
  fireEvent.click(signOut)
  expect(accountAction).toHaveBeenLastCalledWith('logout', {}, expect.any(AbortSignal))
})

it('keeps product content closed during identity bootstrap and refused sessions', async () => {
  let finish!: (response: Response) => void
  const pending = new Promise<Response>((resolve) => { finish = resolve })
  const fetch = vi.fn((url: string) => url.endsWith('release-profile') ? Promise.resolve(json(release)) : pending)
  vi.stubGlobal('fetch', fetch); render(<App />)
  expect(await screen.findByRole('heading', { name: 'Verifying your session' })).toBeInTheDocument()
  expect(screen.queryByLabelText('Project')).not.toBeInTheDocument()
  await act(async () => finish(json({}, 401)))
  expect(await screen.findByRole('heading', { name: 'Sign in to your workspace' })).toHaveFocus()
  expect(fetch.mock.calls.map(call => call[0])).toEqual(['/api/v1/release-profile', '/api/v1/auth/session'])
})

it('submits invitation in a password form and mounts product only after safe bootstrap', async () => {
  let authenticated = false
  const fetch = vi.fn(async (url: string) => {
    if (url.endsWith('release-profile')) return json(release)
    if (url.endsWith('auth/session')) return authenticated ? json(session) : json({}, 401)
    if (url.endsWith('auth/enroll')) { authenticated = true; return json({ ok: true }) }
    if (url.endsWith('account-commerce/status')) return json(accountStatus)
    if (url.includes('ir/projects/research-spine/index?')) return json({ schema: 'strategy-os-research-project-page/1', items: [], next_cursor: null })
    throw new Error('unexpected URL')
  })
  vi.stubGlobal('fetch', fetch); render(<App />)
  fireEvent.click(await screen.findByRole('button', { name: 'I have an invitation' }))
  const invitation = screen.getByLabelText('Invitation')
  expect(invitation).toHaveAttribute('type', 'password')
  expect(screen.queryByRole('button', { name: /invitation/i })).not.toBeInTheDocument()
  expect(screen.getByLabelText('Password')).toHaveAttribute('autocomplete', 'new-password')
  expect(screen.getByRole('button', { name: 'Show password' })).toHaveAttribute('aria-controls', 'auth-password')
  fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'alice@example.test' } })
  fireEvent.change(screen.getByLabelText('Display name'), { target: { value: 'Synthetic Alice' } })
  fireEvent.change(invitation, { target: { value: 'synthetic-invitation-value' } })
  fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'a synthetic password phrase' } })
  fireEvent.click(screen.getByRole('button', { name: 'Create invited account' }))
  expect(await screen.findByRole('heading', { name: 'Your workspace' })).toBeInTheDocument()
  expect(localStorage.length).toBe(0); expect(sessionStorage.length).toBe(0)
  expect(fetch.mock.calls.every(call => !call[0].includes('synthetic-invitation-value'))).toBe(true)
})

it('uses in-memory CSRF only and invalidates cached access after logout', async () => {
  const fetch = vi.fn(async (url: string) => url.endsWith('release-profile') ? json(release) : url.endsWith('auth/session') ? json(session) : json({ ok: true }))
  vi.stubGlobal('fetch', fetch)
  const api = new StrategyApi(); const signal = new AbortController().signal
  await api.bootstrap(signal); await api.session(signal)
  const invalidated = vi.fn(); api.onAccessInvalidated(invalidated)
  await api.accountAction('logout', {}, signal)
  expect(invalidated).toHaveBeenCalledOnce()
  const options = (fetch.mock.calls.at(-1) as unknown as [string, RequestInit])[1]
  expect(options.credentials).toBe('same-origin')
  expect(options.headers).toMatchObject({ 'X-Strategy-CSRF': session.csrf, 'Content-Type': 'application/json' })
  expect(options.headers).not.toHaveProperty('Authorization')
  await expect(api.projects(signal)).rejects.toMatchObject({ kind: 'manifest' })
})

it('rejects extra secret fields, missing membership and malformed CSRF', () => {
  expect(() => parseBrowserSession({ ...session, bearer: 'must not exist' })).toThrow()
  expect(() => parseBrowserSession({ ...session, organization_id: 'foreign' })).toThrow()
  expect(() => parseBrowserSession({ ...session, csrf: 'bad' })).toThrow()
})

it.each([403, 422])('retains in-page access state for valid-session action refusal %s', async (status) => {
  const fetch = vi.fn(async (url: string) => url.endsWith('release-profile') ? json(release) : url.endsWith('auth/session') ? json(session) : url.includes('ir/projects/research-spine/index?') ? json({ schema: 'strategy-os-research-project-page/1', items: [], next_cursor: null }) : json({ error: 'authentication refused' }, status))
  vi.stubGlobal('fetch', fetch)
  const api = new StrategyApi(); const signal = new AbortController().signal
  await api.bootstrap(signal); await api.session(signal)
  const invalidated = vi.fn(); api.onAccessInvalidated(invalidated)
  await expect(api.accountAction('organization', { organization_id: 'foreign' }, signal)).rejects.toMatchObject({ kind: 'input' })
  expect(invalidated).not.toHaveBeenCalled()
  await expect(api.projects(new AbortController().signal)).resolves.toEqual([])
})


it('offers workspace switching only for multiple verified memberships', async () => {
  const identity = { ...session, memberships: [...session.memberships, { organization_id: 'second.org', name: 'Second workspace', role: 'viewer' }] }
  const accountAction = vi.fn(async () => undefined)
  const api = { session: vi.fn(async () => identity), accountAction } as unknown as StrategyApi
  render(<AuthGate api={api}><AccountSecurityControls /></AuthGate>)
  const workspace = await screen.findByLabelText('Workspace')
  expect(new FormData(workspace.closest('form') as HTMLFormElement).get('organization_id')).toBe('synthetic.org')
  await chooseSelect('Workspace', 'second.org')
  fireEvent.submit(workspace.closest('form') as HTMLFormElement)
  expect(accountAction).toHaveBeenCalledWith('organization', { organization_id: 'second.org' }, expect.any(AbortSignal))
})
