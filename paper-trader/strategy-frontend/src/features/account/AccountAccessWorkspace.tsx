import { AccountSecurityControls } from '../../auth/AuthGate'
import { useCallback, useEffect, useRef, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import {
  AccountCommerceContractError,
  AccountCommerceRequestError,
  validateProfileRefresh,
  validateTrialRefresh,
} from './accountCommerceClient'
import type {
  AccountCommerceClient,
  AccountCommerceStatus,
  ProfileEvidence,
  TrialGrant,
} from './accountCommerceClient'
import './account-access.css'

type ViewState =
  | { readonly kind: 'LOADING' }
  | { readonly kind: 'ERROR' }
  | { readonly kind: 'READY'; readonly status: AccountCommerceStatus }

type Action = 'profile' | 'beta' | 'coupon'
type FieldErrors = Readonly<{ fullName?: string; country?: string }>

const EMPTY_PENDING: Readonly<Record<Action, boolean>> = Object.freeze({
  profile: false, beta: false, coupon: false,
})

function formatUtc(value: string): string {
  return new Intl.DateTimeFormat('en-GB', {
    day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
    hourCycle: 'h23', timeZone: 'UTC', timeZoneName: 'short',
  }).format(new Date(value))
}

function sourceLabel(source: AccountCommerceStatus['trial_source']): string {
  if (source === 'BETA_TRIAL') return '15-day beta'
  if (source === 'COUPON_REDEMPTION') return 'Coupon access'
  return 'Not started'
}

function accessStage(status: AccountCommerceStatus): string {
  if (status.access_state === 'ACTIVE') return 'Active'
  if (status.access_state === 'EXPIRED') return 'Expired'
  return 'Not active'
}

function primaryTask(status: AccountCommerceStatus): string {
  if (status.profile_state === 'INCOMPLETE') return 'profile'
  if (status.trial_state === 'AVAILABLE') return 'trial'
  return status.access_state.toLowerCase()
}

function errorMessage(error: unknown): string {
  if (error instanceof AccountCommerceRequestError) {
    if (error.status === 409) return 'Account access changed. Refresh before trying again.'
    if (error.status === 503) return 'Account access is temporarily unavailable. Retry.'
    if (error.status === 401 || error.status === 403) {
      return 'Refresh or sign in again to check your account.'
    }
    return 'Check the required details and try again.'
  }
  if (error instanceof AccountCommerceContractError) {
    return 'Could not confirm your account status. Refresh before trying again.'
  }
  return 'Account access is temporarily unavailable. Retry.'
}

function validateFullName(value: string): string | undefined {
  const normalized = value.trim().normalize('NFC')
  if (normalized.length < 1) return 'Enter your full name.'
  if ([...normalized].length > 128) return 'Full name must be 128 characters or fewer.'
  if (/\p{Cc}/u.test(normalized)) return 'Full name cannot contain control characters.'
  return undefined
}

function validateCountry(value: string): string | undefined {
  return /^[A-Z]{2}$/.test(value) ? undefined : 'Enter a two-letter country code, such as IN.'
}

function StatusTime({ value }: { readonly value: string }): ReactNode {
  return <time dateTime={value}>{formatUtc(value)}</time>
}

function PlanSummary({ status, mutationPending }: {
  readonly status: AccountCommerceStatus
  readonly mutationPending: boolean
}) {
  return <section className="account-access__plan" aria-labelledby="account-plan-title"
    aria-busy={mutationPending} data-access-state={status.access_state}>
    <div className="account-access__section-heading">
      <h2 id="account-plan-title">Your plan</h2>
      <span aria-live="polite">{mutationPending ? 'Updating account…' : ''}</span>
    </div>
    <dl>
      <div><dt>Plan</dt><dd>{sourceLabel(status.trial_source)}</dd></div>
      <div><dt>Status</dt><dd>{accessStage(status)}</dd></div>
      {status.access_expires_at && <div>
        <dt>{status.access_state === 'EXPIRED' ? 'Ended' : 'Expires'}</dt>
        <dd><StatusTime value={status.access_expires_at} /></dd>
      </div>}
    </dl>
  </section>
}

export function AccountAccessWorkspace({ client }: { readonly client: AccountCommerceClient }) {
  const [view, setView] = useState<ViewState>({ kind: 'LOADING' })
  const [fullName, setFullName] = useState('')
  const [country, setCountry] = useState('')
  const [coupon, setCoupon] = useState('')
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({})
  const [showSummary, setShowSummary] = useState(false)
  const [pending, setPending] = useState(EMPTY_PENDING)
  const [actionMessages, setActionMessages] = useState<Partial<Record<Action, string>>>({})
  const mounted = useRef(false)
  const generation = useRef(0)
  const controllers = useRef(new Set<AbortController>())
  const currentLoad = useRef<AbortController | null>(null)
  const headingRef = useRef<HTMLHeadingElement>(null)
  const summaryRef = useRef<HTMLDivElement>(null)
  const fullNameRef = useRef<HTMLInputElement>(null)
  const countryRef = useRef<HTMLInputElement>(null)
  const couponRef = useRef<HTMLInputElement>(null)
  const previousTask = useRef<string | null>(null)

  const clearVolatileInputs = useCallback(() => {
    if (fullNameRef.current) fullNameRef.current.value = ''
    if (countryRef.current) countryRef.current.value = ''
    if (couponRef.current) couponRef.current.value = ''
  }, [])

  const ownController = useCallback(() => {
    const controller = new AbortController()
    controllers.current.add(controller)
    return controller
  }, [])

  const releaseController = useCallback((controller: AbortController) => {
    controllers.current.delete(controller)
    if (currentLoad.current === controller) currentLoad.current = null
  }, [])

  const projectStatus = useCallback((status: AccountCommerceStatus) => {
    const nextTask = primaryTask(status)
    const shouldFocus = previousTask.current !== null && previousTask.current !== nextTask
    previousTask.current = nextTask
    setView({ kind: 'READY', status })
    if (shouldFocus) queueMicrotask(() => headingRef.current?.focus())
  }, [])

  const load = useCallback(async () => {
    currentLoad.current?.abort()
    const controller = ownController()
    currentLoad.current = controller
    const ownedGeneration = ++generation.current
    setView({ kind: 'LOADING' })
    try {
      const result = await client.load(controller.signal)
      if (!mounted.current || controller.signal.aborted || ownedGeneration !== generation.current) return
      projectStatus(result.status)
    } catch {
      if (!mounted.current || controller.signal.aborted || ownedGeneration !== generation.current) return
      previousTask.current = null
      setView({ kind: 'ERROR' })
    } finally {
      releaseController(controller)
    }
  }, [client, ownController, projectStatus, releaseController])

  useEffect(() => {
    const ownedControllers = controllers.current
    mounted.current = true
    queueMicrotask(() => {
      if (mounted.current) void load()
    })
    return () => {
      mounted.current = false
      generation.current += 1
      ownedControllers.forEach((controller) => controller.abort())
      ownedControllers.clear()
      clearVolatileInputs()
    }
  }, [clearVolatileInputs, load])

  const mutate = useCallback(async (
    action: Action,
    request: (signal: AbortSignal) => Promise<ProfileEvidence | TrialGrant>,
  ) => {
    const controller = ownController()
    const ownedGeneration = ++generation.current
    currentLoad.current?.abort()
    setPending((current) => ({ ...current, [action]: true }))
    setActionMessages((current) => ({ ...current, [action]: undefined }))
    try {
      const receipt = await request(controller.signal)
      if (!mounted.current || controller.signal.aborted || ownedGeneration !== generation.current) return
      if (action === 'profile') {
        setFullName('')
        setCountry('')
        if (fullNameRef.current) fullNameRef.current.value = ''
        if (countryRef.current) countryRef.current.value = ''
      }
      setView({ kind: 'LOADING' })
      const refreshed = await client.load(controller.signal)
      if (!mounted.current || controller.signal.aborted || ownedGeneration !== generation.current) return
      if (action === 'profile') validateProfileRefresh(receipt as ProfileEvidence, refreshed.status)
      else validateTrialRefresh(receipt as TrialGrant, refreshed.status)
      setActionMessages((current) => ({ ...current, [action]: 'Account updated.' }))
      projectStatus(refreshed.status)
    } catch (error) {
      if (!mounted.current || controller.signal.aborted || ownedGeneration !== generation.current) return
      setActionMessages((current) => ({ ...current, [action]: errorMessage(error) }))
      setView((current) => current.kind === 'LOADING' ? { kind: 'ERROR' } : current)
    } finally {
      if (mounted.current) setPending((current) => ({ ...current, [action]: false }))
      releaseController(controller)
    }
  }, [client, ownController, projectStatus, releaseController])

  function validateProfileForm(): FieldErrors {
    return {
      fullName: validateFullName(fullName),
      country: validateCountry(country),
    }
  }

  function submitProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const errors = validateProfileForm()
    setFieldErrors(errors)
    if (errors.fullName || errors.country) {
      setShowSummary(true)
      queueMicrotask(() => summaryRef.current?.focus())
      return
    }
    setShowSummary(false)
    const details = { full_name: fullName.trim().normalize('NFC'), country }
    void mutate('profile', (signal) => client.attestRequiredDetails(details, signal))
  }

  function submitCoupon(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const submittedCoupon = coupon
    const invalid = submittedCoupon.length < 1 || new TextEncoder().encode(submittedCoupon).byteLength > 256
    if (invalid) {
      setActionMessages((current) => ({ ...current, coupon: 'Enter a valid coupon code.' }))
      return
    }
    setCoupon('')
    if (couponRef.current) couponRef.current.value = ''
    void mutate('coupon', (signal) => client.redeemCoupon(submittedCoupon, signal))
  }

  function renderRequiredDetails() {
    return <section className="account-access__panel" aria-labelledby="required-details-title">
          <h2 id="required-details-title">Finish setting up your account</h2>
          <p>Add your name and country to continue.</p>
          <form noValidate onSubmit={submitProfile}>
            {showSummary && <div className="account-access__summary" role="alert" tabIndex={-1} ref={summaryRef}>
              <h3>Check your details</h3><ul>
                {fieldErrors.fullName && <li><a href="#account-full-name" onClick={() => fullNameRef.current?.focus()}>{fieldErrors.fullName}</a></li>}
                {fieldErrors.country && <li><a href="#account-country" onClick={() => countryRef.current?.focus()}>{fieldErrors.country}</a></li>}
              </ul>
            </div>}
            <label htmlFor="account-full-name">Full name</label>
            <input id="account-full-name" ref={fullNameRef} value={fullName} autoComplete="name"
              aria-invalid={Boolean(fieldErrors.fullName)} aria-describedby={fieldErrors.fullName ? 'account-full-name-error' : undefined}
              onChange={(event) => setFullName(event.target.value)}
              onBlur={() => setFieldErrors((current) => ({ ...current, fullName: validateFullName(fullName) }))} />
            {fieldErrors.fullName && <p id="account-full-name-error" className="account-access__field-error">{fieldErrors.fullName}</p>}
            <label htmlFor="account-country">Country</label>
            <input id="account-country" ref={countryRef} value={country} autoComplete="country" maxLength={2}
              aria-invalid={Boolean(fieldErrors.country)} aria-describedby={fieldErrors.country ? 'account-country-error' : 'account-country-hint'}
              onChange={(event) => setCountry(event.target.value.toUpperCase())}
              onBlur={() => setFieldErrors((current) => ({ ...current, country: validateCountry(country) }))} />
            <p id="account-country-hint" className="account-access__hint">Use a two-letter code, such as IN for India.</p>
            {fieldErrors.country && <p id="account-country-error" className="account-access__field-error">{fieldErrors.country}</p>}
            <button type="submit" disabled={pending.profile}>{pending.profile ? 'Saving details…' : 'Save details'}</button>
            <p className="account-access__action-message" aria-live="polite">
              {pending.profile ? 'Saving details…' : actionMessages.profile}
            </p>
          </form>
        </section>
  }

  const status = view.kind === 'READY' ? view.status : null
  const mutationPending = pending.profile || pending.beta || pending.coupon

  return <section className="account-access" aria-labelledby="account-access-title">
    <header className="account-access__header">
      <div>
        <h1 id="account-access-title" ref={headingRef} tabIndex={-1}>Account</h1>
      </div>
      {status && <button type="button" onClick={() => void load()}>Refresh</button>}
    </header>

    {view.kind === 'LOADING' && <section className="account-access__loading" role="status" aria-live="polite">
      <span>Loading your account…</span>
    </section>}
    {view.kind === 'ERROR' && <section className="account-access__error" role="alert">
      <h2>Could not load your account</h2>
      <p>Try again to see your plan and account settings.</p>
      <button type="button" onClick={() => void load()}>Retry</button>
    </section>}
    {status && <>
      <PlanSummary status={status} mutationPending={mutationPending} />
      <div className="account-access__work">
        {status.profile_state === 'INCOMPLETE' && renderRequiredDetails()}

        {status.profile_state === 'COMPLETE' && status.trial_state === 'AVAILABLE' && <section className="account-access__panel" aria-labelledby="access-source-title">
          <h2 id="access-source-title">Start your trial</h2>
          <p>Choose the 15-day beta or use a coupon.</p>
          <div className="account-access__beta">
            <button type="button" disabled={pending.beta} onClick={() => void mutate('beta', (signal) => client.activateBeta(signal))}>
              {pending.beta ? 'Starting 15-day beta…' : 'Start 15-day beta'}
            </button>
            <p className="account-access__action-message" aria-live="polite">
              {pending.beta ? 'Starting 15-day beta…' : actionMessages.beta}
            </p>
          </div>
          <form noValidate onSubmit={submitCoupon}>
            <label htmlFor="account-coupon">Coupon</label>
            <input id="account-coupon" ref={couponRef} value={coupon} autoComplete="off"
              aria-describedby="account-coupon-hint" onChange={(event) => setCoupon(event.target.value)} />
            <p id="account-coupon-hint" className="account-access__hint">Enter your coupon code to activate it.</p>
            <button type="submit" disabled={pending.coupon}>{pending.coupon ? 'Redeeming coupon…' : 'Redeem coupon'}</button>
            <p className="account-access__action-message" aria-live="polite">
              {pending.coupon ? 'Redeeming coupon…' : actionMessages.coupon}
            </p>
          </form>
        </section>}


      </div>
    </>}
    <AccountSecurityControls />
  </section>
}
