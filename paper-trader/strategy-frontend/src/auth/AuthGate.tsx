import { TraderSelect } from '../components/TraderSelect'
import { Eye, EyeOff } from 'lucide-react'
import { createContext, useContext, useEffect, useLayoutEffect, useRef, useState, type FormEvent, type InputHTMLAttributes, type ReactNode } from 'react'
import { ApiError, errorMessage, type StrategyApi } from '../shell/api'
import type { BrowserIdentity } from '../shell/contracts'

const BrowserAccountContext = createContext<{ identity: BrowserIdentity; controls: ReactNode } | null>(null)

export function useBrowserIdentity() { return useContext(BrowserAccountContext)?.identity ?? null }
export function AccountSecurityControls() { return useContext(BrowserAccountContext)?.controls ?? null }

type State = { kind: 'loading' } | { kind: 'signed-out' } | { kind: 'error'; message: string } | { kind: 'ready'; identity: BrowserIdentity }

type PasswordFieldProps = Omit<InputHTMLAttributes<HTMLInputElement>, 'id' | 'type'> & {
  id: string
  visibilityLabel: string
}

function PasswordField({ id, visibilityLabel, ...inputProps }: PasswordFieldProps) {
  const [visible, setVisible] = useState(false)
  const input = useRef<HTMLInputElement>(null)
  const restore = useRef<{ focus: boolean; start: number | null; end: number | null; direction: 'forward' | 'backward' | 'none' | null } | null>(null)

  useLayoutEffect(() => {
    const selection = restore.current
    restore.current = null
    if (!selection?.focus || !input.current) return
    input.current.focus()
    if (selection.start !== null && selection.end !== null) {
      input.current.setSelectionRange(selection.start, selection.end, selection.direction ?? undefined)
    }
  }, [visible])

  const toggle = () => {
    const field = input.current
    restore.current = field ? {
      focus: document.activeElement === field,
      start: field.selectionStart,
      end: field.selectionEnd,
      direction: field.selectionDirection,
    } : null
    setVisible((value) => !value)
  }

  return <div className="slate-password-field">
    <input {...inputProps} ref={input} id={id} type={visible ? 'text' : 'password'} />
    <button
      className="slate-password-toggle"
      type="button"
      aria-label={`${visible ? 'Hide' : 'Show'} ${visibilityLabel}`}
      aria-pressed={visible}
      aria-controls={id}
      disabled={inputProps.disabled}
      onPointerDown={(event) => { if (document.activeElement === input.current) event.preventDefault() }}
      onClick={toggle}
    >
      {visible ? <EyeOff aria-hidden="true" /> : <Eye aria-hidden="true" />}
    </button>
  </div>
}

export function AuthGate({ api, children }: { api: StrategyApi; children: ReactNode }) {
  const [state, setState] = useState<State>({ kind: 'loading' })
  const [mode, setMode] = useState<'login' | 'enroll'>('login')
  const [pending, setPending] = useState(false)
  const [message, setMessage] = useState('')
  const [attempt, setAttempt] = useState(0)
  const controller = useRef<AbortController | null>(null)
  const heading = useRef<HTMLHeadingElement>(null)
  const error = useRef<HTMLParagraphElement>(null)
  useEffect(() => {
    const request = new AbortController()
    controller.current = request
    api.session(request.signal).then((identity) => {
      if (!request.signal.aborted) setState({ kind: 'ready', identity })
    }).catch((failure: unknown) => {
      if (!request.signal.aborted) setState(failure instanceof ApiError && failure.kind === 'access'
        ? { kind: 'signed-out' } : { kind: 'error', message: errorMessage(failure) })
    })
    return () => request.abort()
  }, [api, attempt])
  useEffect(() => { heading.current?.focus() }, [state.kind, mode])
  useEffect(() => { if (message) error.current?.focus() }, [message])
  useEffect(() => () => controller.current?.abort(), [])

  async function submit(event: FormEvent<HTMLFormElement>, action: 'login' | 'enroll' | 'logout' | 'logout-all' | 'password' | 'organization') {
    event.preventDefault()
    if (pending) return
    const form = event.currentTarget
    const values = Object.fromEntries(new FormData(form).entries()) as Record<string, string>
    const request = new AbortController()
    controller.current?.abort(); controller.current = request
    setPending(true); setMessage('')
    try {
      if (action === 'login' || action === 'enroll') {
        const identity = await api.authenticate(action, values, request.signal)
        if (!request.signal.aborted) { form.reset(); setState({ kind: 'ready', identity }) }
      } else {
        await api.accountAction(action, values, request.signal)
      }
    } catch (failure) {
      if (!request.signal.aborted) setMessage(errorMessage(failure))
    } finally {
      if (!request.signal.aborted) setPending(false)
    }
  }

  const feedback = <>
    {pending && <p role="status">Verifying securely…</p>}
    {message && <p id="auth-error" ref={error} role="alert" tabIndex={-1}>{message}</p>}
  </>

  function renderCredentials() {
    return <form onSubmit={(event) => void submit(event, mode)} aria-describedby={message ? 'auth-error' : undefined}>
        <label htmlFor="auth-email">Email</label>
        <input id="auth-email" name="email" type="email" autoComplete="username" required maxLength={320} disabled={pending} aria-invalid={message ? true : undefined} />
        {mode === 'enroll' && <>
          <label htmlFor="auth-display-name">Display name</label>
          <input id="auth-display-name" name="display_name" autoComplete="name" required maxLength={128} disabled={pending} />
          <label htmlFor="auth-invitation">Invitation</label>
          <input id="auth-invitation" name="invitation" type="password" autoComplete="off" required maxLength={43} spellCheck={false} disabled={pending} />
        </>}
        <label htmlFor="auth-password">Password</label>
        <PasswordField key={mode} id="auth-password" visibilityLabel="password" name="password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} required maxLength={512} disabled={pending} aria-describedby="auth-password-help" aria-invalid={message ? true : undefined} />
        <p id="auth-password-help">15–128 characters. Paste and password managers are welcome. Passwords are not trimmed or normalized.</p>
        {feedback}
        <button disabled={pending}>{mode === 'login' ? 'Sign in' : 'Create invited account'}</button>
      </form>
  }

  function renderSecurity(identity: BrowserIdentity) {
    return <section className="slate-account-security" aria-label="Account security">
        <header className="slate-account-security__heading">
          <h2>Security</h2>
          <form className="slate-account-security__signout" onSubmit={(event) => void submit(event, 'logout')}>
            <button disabled={pending}>Sign out</button>
          </form>
        </header>
        <div className="slate-account-controls">
          {identity.memberships.length > 1 && <form onSubmit={(event) => void submit(event, 'organization')}>
            <label htmlFor="auth-organization">Workspace</label>
            <TraderSelect id="auth-organization" label="Workspace" name="organization_id"
              defaultValue={identity.organization_id} disabled={pending}
              options={identity.memberships.map((membership) => ({ value: membership.organization_id, label: `${membership.name} (${membership.role})` }))} />
            <button disabled={pending}>Switch workspace</button>
          </form>}
          <details><summary>Change password</summary><form onSubmit={(event) => void submit(event, 'password')} aria-describedby={message ? 'auth-error' : undefined}>
            <label htmlFor="auth-current-password">Current password</label>
            <PasswordField id="auth-current-password" visibilityLabel="current password" name="password" autoComplete="current-password" required maxLength={512} disabled={pending} />
            <label htmlFor="auth-new-password">New password</label>
            <PasswordField id="auth-new-password" visibilityLabel="new password" name="new_password" autoComplete="new-password" required maxLength={512} aria-describedby="auth-password-help" disabled={pending} />
            <p id="auth-password-help">Use 15–128 characters. Spaces and Unicode are supported. Common passwords are refused.</p>
            <button disabled={pending}>Change password and sign out other sessions</button>
          </form></details>
          <details><summary>Sign out on all devices</summary><form onSubmit={(event) => void submit(event, 'logout-all')}>
            <p id="auth-signout-help">You’ll need to sign in again on every device, including this one.</p>
            <label htmlFor="auth-revoke-password">Confirm your password</label>
            <PasswordField id="auth-revoke-password" visibilityLabel="password to sign out on all devices" aria-describedby="auth-signout-help" name="password" autoComplete="current-password" required maxLength={512} disabled={pending} />
            <button disabled={pending}>Sign out on all devices</button>
          </form></details>
          {feedback}
        </div>
    </section>
  }

  if (state.kind === 'ready') return <BrowserAccountContext.Provider value={{ identity: state.identity, controls:
    renderSecurity(state.identity) }}>
    {children}
  </BrowserAccountContext.Provider>

  return <main className="slate-gate slate-auth">
    <span className="slate-eyebrow">Strategy OS · Private workspace</span>
    {state.kind === 'loading' ? <>
      <h1 ref={heading} tabIndex={-1}>Verifying your session</h1><p role="status">Private content stays closed until your session is verified.</p>
    </> : state.kind === 'error' ? <>
      <h1 ref={heading} tabIndex={-1}>Session unavailable</h1><p role="alert">{state.message}</p>
      <button onClick={() => { setState({ kind: 'loading' }); setAttempt((value) => value + 1) }}>Retry session check</button>
    </> : <>
      <h1 ref={heading} tabIndex={-1}>{mode === 'login' ? 'Sign in to your workspace' : 'Accept your invitation'}</h1>
      <p>{mode === 'login' ? 'Use the account you created with your invitation.' : 'Your invitation creates a private workspace. It does not verify your email address.'}</p>
      {renderCredentials()}
      <button className="slate-auth-switch" disabled={pending} onClick={() => { setMessage(''); setMode(mode === 'login' ? 'enroll' : 'login') }}>
        {mode === 'login' ? 'I have an invitation' : 'I already have an account'}
      </button>
      <p className="slate-auth-note">Invitation access only. Public signup, email verification and password recovery are not available here.</p>
    </>}
  </main>
}
