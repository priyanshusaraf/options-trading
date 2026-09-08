import { useEffect, useRef, useState } from 'react'
import { StrategyApi, errorMessage } from './shell/api'
import { strategiesEnabled, type ReleaseManifest } from './shell/contracts'
import { AuthGate } from './auth/AuthGate'
import { ProductRouter } from './product/routes'

type Bootstrap = { kind: 'loading' } | { kind: 'ready'; manifest: ReleaseManifest } | { kind: 'error'; message: string }

export default function App() {
  const [api] = useState(() => new StrategyApi())
  const [attempt, setAttempt] = useState(0)
  const [state, setState] = useState<Bootstrap>({ kind: 'loading' })
  const restoreFocus = useRef(false)
  const gateHeading = useRef<HTMLHeadingElement>(null)
  const pendingBootstrap = useRef<AbortController | null>(null)
  useEffect(() => api.onAccessInvalidated((error) => {
    pendingBootstrap.current?.abort()
    restoreFocus.current = true
    setState(error ? { kind: 'error', message: error.message } : { kind: 'loading' })
    if (!error) setAttempt((value) => value + 1)
  }), [api])
  useEffect(() => { if (restoreFocus.current) gateHeading.current?.focus() }, [state.kind])
  useEffect(() => {
    const controller = new AbortController()
    pendingBootstrap.current = controller
    api.bootstrap(controller.signal).then((manifest) => {
      if (!controller.signal.aborted) setState({ kind: 'ready', manifest })
    }).catch((error: unknown) => {
      if (!controller.signal.aborted) setState({ kind: 'error', message: errorMessage(error) })
    })
    return () => controller.abort()
  }, [api, attempt])

  // Manifest barrier: product components must not mount before this decision.
  if (state.kind === 'ready' && strategiesEnabled(state.manifest)) {
    return <AuthGate api={api}><ProductRouter api={api} manifest={state.manifest} restoreFocus /></AuthGate>
  }
  return <main className="slate-gate">
    <span className="slate-eyebrow">Connection check</span>
    {state.kind === 'loading' ? <>
      <h1 ref={gateHeading} tabIndex={-1}>Verifying the server release</h1>
      <p role="status">Loading release information. Product access remains closed until it is verified.</p>
    </> : <>
      <h1 ref={gateHeading} tabIndex={-1}>Release unavailable</h1>
      <p role="alert">{state.kind === 'error' ? state.message : state.manifest.capabilities.strategy_graph.reason ?? 'The server has not enabled strategy navigation.'}</p>
      <p>This entrypoint requires the V0 API profile with Strategies enabled.</p>
      <button onClick={() => api.recheck()}>Retry release check</button>
    </>}
  </main>
}
