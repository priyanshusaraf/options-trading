import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import type { AccountCommerceClient, AccountCommerceStatus } from '../features/account/accountCommerceClient'

type GateState =
  | { readonly kind: 'LOADING'; readonly path: string }
  | { readonly kind: 'ERROR'; readonly path: string }
  | { readonly kind: 'READY'; readonly path: string; readonly status: AccountCommerceStatus }

export function NeutralRouteTransition() {
  return <section className="slate-route-pending" aria-busy="true" aria-label="Loading page">
    <p className="slate-visually-hidden" role="status" aria-live="polite">Loading page…</p>
  </section>
}

export function AccountAccessGate({ client, children }: {
  client: AccountCommerceClient
  children: ReactNode
}) {
  const location = useLocation()
  const navigate = useNavigate()
  const [attempt, setAttempt] = useState(0)
  const [state, setState] = useState<GateState>({ kind: 'LOADING', path: location.pathname })
  const errorHeading = useRef<HTMLHeadingElement>(null)
  const path = location.pathname

  useEffect(() => {
    const controller = new AbortController()
    setState({ kind: 'LOADING', path })
    client.load(controller.signal).then(({ status }) => {
      if (controller.signal.aborted) return
      const target = status.access_state === 'ACTIVE'
        ? null
        : path === '/account' ? null : '/account'
      if (target !== null) {
        void navigate(target, { replace: true, flushSync: true })
        return
      }
      setState({ kind: 'READY', path, status })
    }).catch(() => {
      if (!controller.signal.aborted) setState({ kind: 'ERROR', path })
    })
    return () => controller.abort()
  }, [attempt, client, navigate, path])

  useEffect(() => {
    if (state.kind === 'ERROR' && state.path === path) errorHeading.current?.focus()
  }, [path, state])

  if (state.path !== path || state.kind === 'LOADING') return <NeutralRouteTransition />
  if (state.kind === 'ERROR') return <main className="slate-gate slate-route-error">

    <h1 ref={errorHeading} tabIndex={-1}>Account access could not be verified</h1>
    <p role="alert">No account or strategy details are shown. Retry with the current verified session.</p>
    <button onClick={() => {
      setState({ kind: 'LOADING', path })
      setAttempt((value) => value + 1)
    }}>Retry account access</button>
  </main>
  return children
}
