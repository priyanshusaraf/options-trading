import { createWatchlistMonitorClient } from '../features/static-scopes/watchlistMonitorClient'
import { AlertsWorkspace } from '../features/alerts/AlertsWorkspace'
import { alertsEnabled } from '../features/alerts/monitoringContracts'
import { StaticWatchlistWorkspace } from '../features/static-scopes/StaticWatchlistWorkspace'
import { parseScopeMemberContext } from '../features/static-scopes/staticScopeContracts'
import { SettingsWorkspace } from '../research/SettingsWorkspace'
import { PortfolioWorkspace } from '../features/portfolio/PortfolioWorkspace'
import { HomeWorkspace } from '../features/home/HomeWorkspace'
import { useEffect, useMemo, useRef } from 'react'
import { createBrowserRouter, Link, Outlet, RouterProvider, useLocation, useNavigate, useParams, useRouteError, type RouteObject } from 'react-router-dom'
import type { StrategyApi } from '../shell/api'
import { providerOnboardingEnabled, staticScopesEnabled, strategiesEnabled, type ReleaseManifest } from '../shell/contracts'
import { PrecisionFrame, PrecisionShell, type GlobalPath } from '../shell/PrecisionShell'
import { PresetLibrary } from '../features/presets/PresetLibrary'
import { AccountAccessGate } from '../auth/AccountAccessGate'
import { AccountAccessWorkspace } from '../features/account/AccountAccessWorkspace'
import { createAccountCommerceClient, type AccountCommerceClient } from '../features/account/accountCommerceClient'
import { createDataConnectionClient, type DataConnectionClient } from '../features/connections/dataConnectionClient'
import { DataConnectionWorkspace } from '../features/connections/DataConnectionWorkspace'

export { NeutralRouteTransition } from '../auth/AccountAccessGate'

export type ProductRouteDefinition = Readonly<{
  id: 'alerts' | 'settings' | 'home' | 'watchlists' | 'portfolio' | 'strategies' | 'presets' | 'account' | 'provider'
  path: '/alerts' | '/settings' | '/' | '/watchlists/:projectId?' | '/portfolio' | '/strategies/:projectId?/:graphId?' | '/presets' | '/account' | '/account/provider'
  capability: 'signals' | 'static_watchlists' | 'strategy_graph' | 'account_access' | 'data_provider_onboarding'
}>

const registry: readonly ProductRouteDefinition[] = Object.freeze([
  Object.freeze({ id: 'strategies', path: '/strategies/:projectId?/:graphId?', capability: 'strategy_graph' }),
  Object.freeze({ id: 'account', path: '/account', capability: 'account_access' }),
  Object.freeze({ id: 'provider', path: '/account/provider', capability: 'data_provider_onboarding' }),
  Object.freeze({ id: 'presets', path: '/presets', capability: 'strategy_graph' }),
  Object.freeze({ id: 'portfolio', path: '/portfolio', capability: 'strategy_graph' }),
  Object.freeze({ id: 'watchlists', path: '/watchlists/:projectId?', capability: 'static_watchlists' }),
  Object.freeze({ id: 'settings', path: '/settings', capability: 'strategy_graph' }),
  Object.freeze({ id: 'alerts', path: '/alerts', capability: 'signals' }),
  Object.freeze({ id: 'home', path: '/', capability: 'strategy_graph' }),
])

function activeProductSection(path: string) {
  if (path === '/alerts') return 'alerts'
  if (path === '/settings') return 'settings'
  if (path.startsWith('/watchlists')) return 'watchlists'
  if (path === '/') return 'home'
  if (path === '/portfolio') return 'portfolio'
  if (path.startsWith('/presets')) return 'presets'
  if (path === '/account/provider') return 'provider'
  return path.startsWith('/account') ? 'account' : 'strategies'
}

function ProductFrame({ api, manifest }: { api: StrategyApi; manifest: ReleaseManifest }) {
  const location = useLocation()
  const navigate = useNavigate()
  const path = location.pathname
  const projectId = path.startsWith('/strategies/') || path.startsWith('/watchlists/') ? decodeURIComponent(path.split('/')[2])
    : typeof location.state?.projectId === 'string' ? location.state.projectId : undefined
  const active = activeProductSection(path)
  return <PrecisionFrame api={api} active={active} alerts={alertsEnabled(manifest)} staticWatchlists={staticScopesEnabled(manifest)} providerOnboarding={providerOnboardingEnabled(manifest)}
    onNavigate={(target) => { void navigate((target === '/strategies' || target === '/watchlists') && projectId ? `${target}/${encodeURIComponent(projectId)}` : target, { flushSync: true, state: { projectId } }) }}><Outlet /></PrecisionFrame>
}

export function enabledProductRoutes(manifest: ReleaseManifest): readonly ProductRouteDefinition[] {
  return Object.freeze(registry.filter((route) => (
    route.capability === 'signals' ? alertsEnabled(manifest) : route.capability === 'static_watchlists' ? staticScopesEnabled(manifest) : route.capability === 'strategy_graph' ? strategiesEnabled(manifest)
      : route.id === 'provider' ? providerOnboardingEnabled(manifest)
        : true
  )))
}

function ErrorFrame({ title, message }: { title: string; message: string }) {
  const heading = useRef<HTMLHeadingElement>(null)
  useEffect(() => { heading.current?.focus() }, [])
  return <main className="slate-gate slate-route-error">
    <span className="slate-eyebrow">Strategy OS · Verified workspace</span>
    <h1 ref={heading} tabIndex={-1}>{title}</h1>
    <p role="alert">{message}</p>
    <Link className="slate-route-link" to="/strategies">Return to Strategies</Link>
  </main>
}

export function RouteErrorBoundary() {
  useRouteError()
  return <ErrorFrame title="Strategies could not be shown" message="The route stopped before it could show verified strategy records. Return to Strategies and try again." />
}

export function AccountRouteErrorBoundary() {
  useRouteError()
  return <ErrorFrame title="Account could not be shown" message="The route stopped before it could show verified account access. Return to Strategies and open Account again." />
}

function RouteNotFound() {
  return <ErrorFrame title="Page unavailable" message="This page does not exist or is not enabled for the verified server release." />
}

function StrategiesFeature({ api, manifest, restoreFocus }: { api: StrategyApi; manifest: ReleaseManifest; restoreFocus: boolean }) {
  const { projectId, graphId } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const requested = new URLSearchParams(location.search).get('view')
  const view = requested === 'build' || requested === 'backtest' ? requested : undefined
  const scopeContext = useMemo(() => location.state?.watchlistMember === undefined ? undefined : parseScopeMemberContext(location.state.watchlistMember, projectId ?? '', graphId ?? ''), [location.state, projectId, graphId])
  const globalNavigate = (path: GlobalPath) => {
    void navigate(path, { flushSync: true, state: { projectId } })
  }
  return <PrecisionShell api={api} manifest={manifest} restoreFocus={restoreFocus} scopeContext={scopeContext}
    onGlobalNavigate={globalNavigate}
    selection={{ projectId, graphId, view }}
    onNavigate={(nextProjectId, nextGraphId) => {
      const path = nextProjectId === undefined ? '/strategies'
        : nextGraphId === undefined ? `/strategies/${encodeURIComponent(nextProjectId)}`
          : `/strategies/${encodeURIComponent(nextProjectId)}/${encodeURIComponent(nextGraphId)}`
        void navigate(path, { flushSync: true })
    }} />
}

function PresetsFeature({ api, manifest }: { api: StrategyApi; manifest: ReleaseManifest }) {
  const navigate = useNavigate()
  const location = useLocation()
  const projectId = typeof location.state?.projectId === 'string' ? location.state.projectId : undefined
  const go = (path: string) => {
    void navigate(path, { flushSync: true, state: { projectId } })
  }
  return <PrecisionFrame api={api} active="presets" providerOnboarding={providerOnboardingEnabled(manifest)} onNavigate={(path) => go(path === '/strategies' && projectId ? `/strategies/${encodeURIComponent(projectId)}` : path)}>
    <PresetLibrary api={api} projectId={projectId} onCreated={(project, identifier) => go(`/strategies/${encodeURIComponent(project)}/${encodeURIComponent(identifier)}`)} />
  </PrecisionFrame>
}

function WatchlistsFeature({ api, manifest, client }: { api: StrategyApi; manifest: ReleaseManifest; client: DataConnectionClient | null }) {
  const { projectId } = useParams()
  const navigate = useNavigate()
  const monitorClient = useMemo(() => createWatchlistMonitorClient(api), [api])
  return <StaticWatchlistWorkspace monitorClient={monitorClient} api={api} providerClient={client} enabled={staticScopesEnabled(manifest)} backtestEnabled={['ENABLED', 'ENABLED_WITH_LIMIT'].includes(manifest.capabilities.backtesting.state)} projectId={projectId}
    onProject={(project) => { void navigate(`/watchlists/${encodeURIComponent(project)}`, { flushSync: true }) }}
    onBacktest={(context) => { void navigate(`/strategies/${encodeURIComponent(context.project_id)}/${encodeURIComponent(context.graph_id)}`, { flushSync: true, state: { projectId: context.project_id, watchlistMember: context } }) }} />
}

function AccountFeature({ api, client, showProvider }: {
  api: StrategyApi; client: AccountCommerceClient; showProvider: boolean
}) {
  const navigate = useNavigate()
  const globalNavigate = (path: GlobalPath) => {
    if (path === '/account') return
    void navigate(path, { flushSync: true })
  }
  return <PrecisionFrame api={api} active="account" onNavigate={globalNavigate}
    providerOnboarding={showProvider}>
    {showProvider && <nav className="slate-local-nav" aria-label="Account sections">
      <span>Access</span><Link to="/account/provider">Data provider</Link>
    </nav>}
    <AccountAccessWorkspace client={client} />

  </PrecisionFrame>
}

function ProviderFeature({ api, client }: { api: StrategyApi; client: DataConnectionClient }) {
  const navigate = useNavigate()
  const globalNavigate = (path: GlobalPath) => {
    void navigate(path, { flushSync: true })
  }
  return <PrecisionFrame api={api} active="provider" onNavigate={globalNavigate}
    providerOnboarding>
    <DataConnectionWorkspace client={client} />
  </PrecisionFrame>
}

function AccountGateRoute({ client }: { client: AccountCommerceClient }) {
  return <AccountAccessGate client={client}><Outlet /></AccountAccessGate>
}

export function productRouteObjects({ api, manifest, restoreFocus }: {
  api: StrategyApi; manifest: ReleaseManifest; restoreFocus: boolean
}): RouteObject[] {
  const client = createAccountCommerceClient(api.accountCommerceTransport)
  const providerEnabled = providerOnboardingEnabled(manifest)
  const providerClient = providerEnabled ? createDataConnectionClient(api.dataConnectionTransport) : null
  const privateChildren: RouteObject[] = []
  const strategiesRoute: RouteObject = {
    id: 'strategies', path: registry[0].path.slice(1),
    element: <StrategiesFeature api={api} manifest={manifest} restoreFocus={restoreFocus} />,
    errorElement: <RouteErrorBoundary />,
  }
  if (enabledProductRoutes(manifest).some((route) => route.id === 'strategies')) {
    privateChildren.push({ id: 'settings', path: 'settings', element: <SettingsWorkspace api={api} />, errorElement: <RouteErrorBoundary /> }, { id: 'portfolio', path: 'portfolio', element: <PortfolioWorkspace api={api} />, errorElement: <RouteErrorBoundary /> }, strategiesRoute, {
      id: 'presets', path: 'presets', element: <PresetsFeature api={api} manifest={manifest} />,
      errorElement: <RouteErrorBoundary />,
    })
  }
  privateChildren.push({
    id: 'account', path: registry[1].path.slice(1),
    element: <AccountFeature api={api} client={client}
      showProvider={providerEnabled} />,
    errorElement: <AccountRouteErrorBoundary />,
  })
  if (providerClient !== null) privateChildren.push({
    id: 'provider', path: registry[2].path.slice(1),
    element: <ProviderFeature api={api} client={providerClient} />,
    errorElement: <AccountRouteErrorBoundary />,
  })
  privateChildren.push({ id: 'alerts', path: 'alerts', element: <AlertsWorkspace api={api} enabled={alertsEnabled(manifest)} />, errorElement: <RouteErrorBoundary /> })
  privateChildren.push({ id: 'watchlists', path: 'watchlists/:projectId?', element: <WatchlistsFeature api={api} manifest={manifest} client={providerClient} />, errorElement: <RouteErrorBoundary /> })
  privateChildren.push({ index: true, element: strategiesEnabled(manifest) ? <HomeWorkspace api={api} /> : <RouteNotFound /> })
  privateChildren.push({ path: '*', element: <RouteNotFound />, errorElement: <RouteErrorBoundary /> })
  return [{ path: '/', element: <ProductFrame api={api} manifest={manifest} />, errorElement: <RouteErrorBoundary />, children: [
    { element: <AccountGateRoute client={client} />, children: privateChildren },
  ] }]
}

export function ProductRouteHost({ router }: { router: ReturnType<typeof createBrowserRouter> }) {
  return <RouterProvider router={router} />
}

export function ProductRouter({ api, manifest, restoreFocus = false }: {
  api: StrategyApi; manifest: ReleaseManifest; restoreFocus?: boolean
}) {
  const router = useMemo(() => createBrowserRouter(productRouteObjects({ api, manifest, restoreFocus })), [api, manifest, restoreFocus])
  useEffect(() => () => router.dispose(), [router])
  return <ProductRouteHost router={router} />
}
