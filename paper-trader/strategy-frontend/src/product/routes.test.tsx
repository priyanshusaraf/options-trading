import { ResearchSettings } from '../research/ResearchSettings'
import { chooseSelect } from '../test/select'
import { useLayoutEffect, useState } from 'react'
import { OptimizationSettingsFields } from '../research/OptimizationSettingsFields'
import { CanonicalOptimizationResults } from '../research/CanonicalOptimizationResults'
import { developmentNeighborhood, OptimizationNeighborhood } from '../research/OptimizationNeighborhood'
import { proposalParameterEdits, type ParameterProposal } from '../research/optimizationProposal'
import { disabledOptimization, parseCanonicalOptimizationEvidence } from '../shell/contracts'
import optimizationFixture from '../test/canonicalOptimization.json'
import { prepareParameterEdits, signalParameters } from '../research/signalParameterContracts'
import { SignalParameterSettings } from '../research/SignalParameterSettings'
import type { GraphSummary, V2Draft, VerifiedCatalogue, OptimizationSelection } from '../shell/contracts'
import * as browserAuth from '../auth/AuthGate'
import { AccountRiskSettings } from '../research/AccountRiskSettings'
import { accountRiskFields } from '../research/accountRiskContracts'
import { SettingsWorkspace } from '../research/SettingsWorkspace'
import { PortfolioPanel } from '../features/portfolio/PortfolioWorkspace'
import { HomeWorkspace } from '../features/home/HomeWorkspace'
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { createMemoryRouter, RouterProvider, MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import release from '../test/releaseManifest.json'
import { ApiError, StrategyApi } from '../shell/api'
import { parseManifest } from '../shell/contracts'
import { enabledProductRoutes, NeutralRouteTransition, ProductRouteHost, productRouteObjects, RouteErrorBoundary } from './routes'

const emptyPortfolio = { schema: 'paper-portfolio/1', untraded_strategies: [], currency: 'INR', as_of: '2026-09-05T06:00:00Z', points: [], strategies: [], realized_pnl: 0, closed_trades: 0 }
const project = { project_id: 'project.test-a', name: 'Research desk', description: 'Server description', status: 'active' }
const graph = { identifier: 'graph.canonical-a', display_name: 'Canonical graph', draft_revision: 3, current_version: null }
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'content-type': 'application/json', 'cache-control': 'no-store' } })
const projectPage = (items: unknown) => ({ schema: 'strategy-os-research-project-page/1', items, next_cursor: null })
const runPage = (projectId: string) => ({ schema: 'strategy-os-research-run-page/1', project_id: projectId, runs: [], next_cursor: null })
const activeAccount = { schema: 'account-commerce-status/1', profile_state: 'COMPLETE',
  satisfied_field_codes: ['profile.country', 'profile.full_name'], profile_attested_at: '2026-09-02T06:00:00Z',
  trial_state: 'USED_ACTIVE', trial_source: 'BETA_TRIAL', trial_expires_at: '2026-09-17T06:00:00Z',
  access_state: 'ACTIVE', access_expires_at: '2026-09-17T06:00:00Z', evaluated_at: '2026-09-02T06:00:00Z' }
const providerStatus = { schema: 'strategy-os-data-connection-status/1', state: 'REAUTH_REQUIRED',
  provider: 'ZERODHA', role: 'DATA', ready: false, credential_expiry: 'UNVERIFIED', rate_quota: 'UNVERIFIED',
  actions: { create: false, write_app_keys: false, rotate_app_keys: true, reauthenticate: true, revoke: true } }

function providerManifest() {
  const enabled = structuredClone(release)
  ;(enabled.capabilities as Record<string, unknown>).data_provider_onboarding = {
    state: 'ENABLED_WITH_LIMIT', ui_navigation: true,
    reason: 'Local encrypted onboarding only.',
  }
  return parseManifest(enabled)
}

function transport(graphValue: GraphSummary = graph) {
  const fetch = vi.fn(async (url: string) => {
    if (url === '/api/v1/paper-portfolio') return json(emptyPortfolio)
    if (url === '/api/v1/release-profile') return json(release)
    if (url === '/api/v1/account-commerce/status') return json(activeAccount)
    if (url === '/api/v1/ir/presets') return json({ presets: [] })
    if (url === '/api/v1/ir/projects/research-spine/index?limit=50') return json(projectPage([project]))
    if (url === `/api/v1/ir/projects/${project.project_id}/graphs?limit=50`) {
      return json({ schema: 'strategy-os-graph-index/1', project_id: project.project_id, items: [graphValue], next_cursor: null })
    }
    if (url === `/api/v1/ir/projects/${project.project_id}/graphs/${graph.identifier}/versions`) return json([])
    if (url === `/api/v1/ir/projects/${project.project_id}/research-spine/experiments?limit=25`) return json(runPage(project.project_id))
    throw new Error(`Unexpected request: ${url}`)
  })
  vi.stubGlobal('fetch', fetch)
  return fetch
}

async function routed(initialEntry: string, graphValue: GraphSummary = graph) {
  transport(graphValue)
  const api = new StrategyApi()
  const manifest = await api.bootstrap(new AbortController().signal)
  const router = createMemoryRouter(productRouteObjects({ api, manifest, restoreFocus: true }), { initialEntries: [initialEntry] })
  render(<ProductRouteHost router={router} />)
  return router
}

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('closed production route registry', () => {
  it('announces a fact-free neutral navigation state', () => {
    render(<NeutralRouteTransition />)
    expect(screen.getByRole('status')).toHaveTextContent('Loading page…')
    expect(screen.getByRole('region', { name: 'Loading page' })).toHaveAttribute('aria-busy', 'true')
    expect(screen.getByRole('region', { name: 'Loading page' }).textContent?.toLowerCase()).not.toMatch(/project|graph|strategy|identifier|version|project\.test|graph\./)
  })
  it('enables the accepted Strategies and Account feature modules', () => {
    const manifest = parseManifest(release)
    expect(enabledProductRoutes(manifest).map(({ id, path, capability }) => ({ id, path, capability }))).toEqual([
      { id: 'strategies', path: '/strategies/:projectId?/:graphId?', capability: 'strategy_graph' },
      { id: 'account', path: '/account', capability: 'account_access' },
      { id: 'presets', path: '/presets', capability: 'strategy_graph' },
      { id: 'portfolio', path: '/portfolio', capability: 'strategy_graph' },
      { id: 'settings', path: '/settings', capability: 'strategy_graph' },
      { id: 'home', path: '/', capability: 'strategy_graph' },
    ])
    const blocked = structuredClone(release)
    Object.assign(blocked.capabilities.strategy_graph, { state: 'BLOCKED', ui_navigation: false, reason: 'Paused.' })
    expect(enabledProductRoutes(parseManifest(blocked))).toEqual([
      { id: 'account', path: '/account', capability: 'account_access' },
    ])
  })

  it('resolves direct project and graph loads from owner-scoped server records', async () => {
    const router = await routed(`/strategies/${project.project_id}/${graph.identifier}`)
    expect(await screen.findByRole('heading', { name: graph.display_name })).toHaveFocus()
    expect(screen.getByLabelText('Project')).toHaveTextContent(project.name)
    expect(router.state.location.pathname).toBe(`/strategies/${project.project_id}/${graph.identifier}`)
  })

  it('explains an unavailable strategy record and returns to its project', async () => {
    const router = await routed(`/strategies/${project.project_id}/missing-draft`)
    expect(await screen.findByRole('alert')).toHaveTextContent('This graph is unavailable in the selected project')
    fireEvent.click(screen.getByRole('button', { name: 'Return to project strategies' }))
    expect(await screen.findByRole('heading', { name: 'Project strategies' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe(`/strategies/${project.project_id}`)
  })

  it('opens the separate preset library and preserves the selected project without creating anything', async () => {
    const router = await routed(`/strategies/${project.project_id}`)
    await screen.findByRole('heading', { name: 'Project strategies' })
    fireEvent.click(within(screen.getByRole('navigation', { name: 'Global navigation' })).getByRole('button', { name: 'Presets' }))
    expect(await screen.findByRole('heading', { name: 'Presets' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/presets')
    expect(router.state.location.state).toEqual({ projectId: project.project_id })
    expect(await screen.findByRole('heading', { name: 'No presets yet' })).toBeInTheDocument()
    const fetch = vi.mocked(globalThis.fetch)
    expect(fetch.mock.calls.some(([, options]) => options?.method === 'POST')).toBe(false)
    fireEvent.click(within(screen.getByRole('navigation', { name: 'Global navigation' })).getByRole('button', { name: 'Strategies' }))
    await screen.findByRole('heading', { name: 'Project strategies' })
    expect(router.state.location.pathname).toBe(`/strategies/${project.project_id}`)
  })

  it('publishes Account inside the same frame with exact current navigation', async () => {
    const router = await routed('/account')
    expect(await screen.findByRole('heading', { name: 'Account' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/account')
    for (const navigation of screen.getAllByRole('navigation')) {
      expect(within(navigation).getByRole('button', { name: 'Account' }))
        .toHaveAttribute('aria-current', 'page')
      expect(within(navigation).getByRole('button', { name: 'Strategies' }))
        .not.toHaveAttribute('aria-current')
    }
    expect(await screen.findByRole('heading', { name: 'Your plan' })).toBeInTheDocument()
    expect(screen.getByText('Active')).toBeInTheDocument()
    expect(screen.getByText('Expires').nextElementSibling?.querySelector('time')).toHaveAttribute('datetime', activeAccount.access_expires_at)
    expect(screen.queryByRole('heading', { name: 'Billing' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /checkout|subscribe|refund/i })).not.toBeInTheDocument()
    expect(screen.queryByText(/provider|google|admin|support/i)).not.toBeInTheDocument()
  })

  it('publishes the direct provider workspace only when the server enables the limited capability', async () => {
    const parsed = providerManifest()
    expect(enabledProductRoutes(parsed).map((route) => route.id)).toEqual([
      'strategies', 'account', 'provider', 'presets', 'portfolio', 'settings', 'home',
    ])
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      if (url === '/api/v1/account-commerce/status') return json(activeAccount)
      if (url === '/api/v1/data-connections/status') return json(providerStatus)
      throw new Error(`Unexpected request: ${url}`)
    }))
    const api = new StrategyApi()
    const router = createMemoryRouter(
      productRouteObjects({ api, manifest: parsed, restoreFocus: true }),
      { initialEntries: ['/account/provider'] },
    )
    render(<ProductRouteHost router={router} />)
    expect(await screen.findByRole('heading', { name: 'Zerodha data connection' })).toBeInTheDocument()
    expect(screen.queryByText('Provider reconnect required')).not.toBeInTheDocument()
    expect(screen.getByText('Not ready')).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/account/provider')
  })

  it.each([
    ['a first visit without a connection', {
      ...providerStatus, state: 'CONNECTION_REQUIRED',
      actions: { create: true, write_app_keys: false, rotate_app_keys: false, reauthenticate: false, revoke: false },
    }],
    ['an expired provider session', providerStatus],
  ])('lets an entitled account research imported data on %s', async (_label, status) => {
    const fetch = vi.fn(async (url: string) => {
      if (url === '/api/v1/account-commerce/status') return json(activeAccount)
      if (url === '/api/v1/data-connections/status') return json(status)
      if (url === '/api/v1/release-profile') return json(release)
      if (url === '/api/v1/ir/projects/research-spine/index?limit=50') return json(projectPage([project]))
      throw new Error(`Unexpected request: ${url}`)
    })
    vi.stubGlobal('fetch', fetch)
    const api = new StrategyApi()
    await api.bootstrap(new AbortController().signal)
    const router = createMemoryRouter(
      productRouteObjects({ api, manifest: providerManifest(), restoreFocus: true }),
      { initialEntries: ['/strategies'] },
    )
    render(<ProductRouteHost router={router} />)
    expect(await screen.findByLabelText('Project')).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/strategies')
    expect(fetch.mock.calls.some(([url]) => String(url).startsWith('/api/v1/ir/'))).toBe(true)
  })

  it('keeps app keys out of the repeat sign-in path while a Zerodha session is stored', async () => {
    const storedSession = {
      ...providerStatus, state: 'SESSION_PRESENT_UNVERIFIED',
      actions: { create: false, write_app_keys: false, rotate_app_keys: true, reauthenticate: true, revoke: true },
    }
    const fetch = vi.fn(async (url: string) => {
      if (url === '/api/v1/release-profile') return json(release)
      if (url === '/api/v1/account-commerce/status') return json(activeAccount)
      if (url === '/api/v1/data-connections/status') return json(storedSession)
      if (url === '/api/v1/ir/projects/research-spine/index?limit=50') return json(projectPage([project]))
      throw new Error(`Unexpected request: ${url}`)
    })
    vi.stubGlobal('fetch', fetch)
    const api = new StrategyApi()
    await api.bootstrap(new AbortController().signal)
    const router = createMemoryRouter(
      productRouteObjects({ api, manifest: providerManifest(), restoreFocus: true }),
      { initialEntries: ['/strategies'] },
    )
    render(<ProductRouteHost router={router} />)
    expect(await screen.findByLabelText('Project')).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/strategies')
    expect(screen.queryByLabelText('Application key')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Application secret')).not.toBeInTheDocument()
  })

  it('keeps project and graph state aligned with back and forward navigation', async () => {
    const router = await routed('/strategies')
    await screen.findByLabelText('Project')
    await chooseSelect('Project', project.project_id)
    expect(router.state.location.pathname).toBe(`/strategies/${project.project_id}`)
    fireEvent.click(await screen.findByRole('button', { name: `Open ${graph.display_name}` }))
    expect(router.state.location.pathname).toBe(`/strategies/${project.project_id}/${graph.identifier}`)
    await router.navigate(-1)
    expect(await screen.findByLabelText('Project')).toHaveTextContent(project.name)
    await router.navigate(1)
    expect(await screen.findByRole('heading', { name: graph.display_name })).toBeInTheDocument()
  })

  it('never commits graph facts under a different project during picker or history transitions', async () => {
    const projectB = { ...project, project_id: 'project.test-b', name: 'Second desk' }
    const graphA = { ...graph, identifier: 'graph.review-a', display_name: 'Graph Alpha' }
    const graphB = { ...graph, identifier: 'graph.review-b', display_name: 'Graph Beta' }
    const fetch = vi.fn(async (url: string) => {
      if (url === '/api/v1/release-profile') return json(release)
      if (url === '/api/v1/account-commerce/status') return json(activeAccount)
      if (url === '/api/v1/ir/projects/research-spine/index?limit=50') return json(projectPage([project, projectB]))
      if (url === `/api/v1/ir/projects/${project.project_id}/graphs?limit=50`) {
        return json({ schema: 'strategy-os-graph-index/1', project_id: project.project_id, items: [graphA], next_cursor: null })
      }
      if (url === `/api/v1/ir/projects/${projectB.project_id}/graphs?limit=50`) {
        return json({ schema: 'strategy-os-graph-index/1', project_id: projectB.project_id, items: [graphB], next_cursor: null })
      }
      throw new Error(`Unexpected request: ${url}`)
    })
    vi.stubGlobal('fetch', fetch)
    const api = new StrategyApi(); const manifest = await api.bootstrap(new AbortController().signal)
    const router = createMemoryRouter(productRouteObjects({ api, manifest, restoreFocus: true }), {
      initialEntries: [`/strategies/${project.project_id}/${graphA.identifier}`],
    })
    render(<ProductRouteHost router={router} />)
    await screen.findByRole('heading', { name: graphA.display_name })

    await chooseSelect('Project', projectB.project_id)
    await waitFor(() => expect(router.state.location.pathname).toBe(`/strategies/${projectB.project_id}`))
    expect(await screen.findByLabelText('Project')).toHaveTextContent(projectB.name)
    expect(screen.queryByText(graphA.identifier)).not.toBeInTheDocument()
    fireEvent.click(await screen.findByRole('button', { name: `Open ${graphB.display_name}` }))
    expect(await screen.findByRole('heading', { name: graphB.display_name })).toBeInTheDocument()
    expect(screen.getByLabelText('Project')).toHaveTextContent(projectB.name)
    await router.navigate(-1)
    await waitFor(() => expect(screen.getByLabelText('Project')).toHaveTextContent(projectB.name))
    await waitFor(() => expect(screen.queryByRole('navigation', { name: 'Selected strategy sections' })).not.toBeInTheDocument())
    expect(screen.queryAllByText(graphB.identifier)).toHaveLength(0)
    await router.navigate(-1)
    expect(await screen.findByRole('heading', { name: graphA.display_name })).toBeInTheDocument()
    expect(screen.getByLabelText('Project')).toHaveTextContent(project.name)
    await router.navigate(1)
    await waitFor(() => expect(screen.getByLabelText('Project')).toHaveTextContent(projectB.name))
    expect(screen.queryByText(graphA.identifier)).not.toBeInTheDocument()
    await router.navigate(1)
    expect(await screen.findByRole('heading', { name: graphB.display_name })).toBeInTheDocument()
    expect(screen.getByLabelText('Project')).toHaveTextContent(projectB.name)
  })

  it('focuses and announces an unknown route without leaving the release boundary', async () => {
    await routed('/unaccepted-surface')
    const heading = await screen.findByRole('heading', { name: 'Page unavailable' })
    await waitFor(() => expect(heading).toHaveFocus())
    expect(screen.getByRole('alert')).toHaveTextContent('does not exist or is not enabled')
    expect(screen.getByRole('link', { name: 'Return to Strategies' })).toHaveAttribute('href', '/strategies')
  })

  it('uses a focused, announced recovery boundary for route render failures', async () => {
    function BrokenRoute(): never { throw new Error('sensitive render detail') }
    const router = createMemoryRouter([{ path: '/strategies', element: <BrokenRoute />, errorElement: <RouteErrorBoundary /> }], { initialEntries: ['/strategies'] })
    render(<RouterProvider router={router} />)
    const heading = await screen.findByRole('heading', { name: 'Strategies could not be shown' })
    await waitFor(() => expect(heading).toHaveFocus())
    expect(screen.getByRole('alert')).not.toHaveTextContent('sensitive render detail')
    expect(screen.getByRole('link', { name: 'Return to Strategies' })).toBeInTheDocument()
  })
})


it('shows actual Home records and keeps the shell mounted across navigation', async () => {
  const router = await routed('/')
  await screen.findByRole('heading', { name: 'Your workspace' })
  expect(screen.queryByRole('region', { name: 'Portfolio' })).not.toBeInTheDocument()
  expect(await screen.findByRole('link', { name: /Canonical graph/ })).toBeInTheDocument()
  expect(screen.getByRole('navigation', { name: 'Quick actions' })).toBeInTheDocument()
  const sidebar = document.getElementById('global-sidebar')
  fireEvent.click(screen.getByRole('button', { name: 'Collapse navigation' }))
  fireEvent.click(within(screen.getByRole('navigation', { name: 'Global navigation' })).getByRole('button', { name: 'Account' }))
  expect(await screen.findByRole('heading', { name: 'Account' })).toBeInTheDocument()
  expect(document.getElementById('global-sidebar')).toBe(sidebar)
  expect(screen.getByRole('button', { name: 'Expand navigation' })).toBeInTheDocument()
  expect(screen.queryByText('Canonical graph')).not.toBeInTheDocument()
  expect(router.state.location.pathname).toBe('/account')
  expect(screen.queryByText(/Server profile|Research only|Signed in as/)).not.toBeInTheDocument()
})


it('explains a Home load failure and retries without inventing records', async () => {
  const projects = vi.fn().mockRejectedValueOnce(new Error('Temporary load failure')).mockResolvedValue([])
  const api = { paperPortfolio: vi.fn(async () => emptyPortfolio), projects, presets: vi.fn(async () => []), graphs: vi.fn() } as unknown as StrategyApi
  const router = createMemoryRouter([{ path: '/', element: <HomeWorkspace api={api} /> }])
  render(<RouterProvider router={router} />)
  await screen.findByRole('alert')
  expect(screen.queryByText('No saved strategies yet. Open Strategies to create your first one.')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Retry workspace' }))
  expect(await screen.findByText('No saved strategies yet. Open Strategies to create your first one.')).toBeInTheDocument()
  expect(api.graphs).not.toHaveBeenCalled()
})

it('opens Portfolio from the sidebar and shows actual strategy revision results', async () => {
  const router = await routed('/')
  await screen.findByRole('heading', { name: 'Your workspace' })
  const portfolio = { ...emptyPortfolio, realized_pnl: 125, closed_trades: 3,
    points: [{ timestamp: '2026-09-03', realized_pnl: -25 }, { timestamp: '2026-09-04', realized_pnl: 125 }],
    strategies: [
      { strategy_key: 'private-key', strategy_version: '2', display_name: 'Momentum', realized_pnl: 150, closed_trades: 2 },
      { strategy_key: null, strategy_version: null, display_name: 'Unattributed strategy', realized_pnl: -25, closed_trades: 1 },
    ] }
  const previous = globalThis.fetch
  vi.stubGlobal('fetch', vi.fn((url: string, options?: RequestInit) => url === '/api/v1/paper-portfolio' ? Promise.resolve(json(portfolio)) : previous(url, options)))
  fireEvent.click(within(screen.getByRole('navigation', { name: 'Global navigation' })).getByRole('button', { name: 'Portfolio' }))
  expect(await screen.findByRole('table', { name: 'By strategy' })).toBeInTheDocument()
  expect(router.state.location.pathname).toBe('/portfolio')
  expect(screen.getByRole('img', { name: /Realized paper P&L: ₹125.00 across 3 closed trades/ })).toBeInTheDocument()
  expect(screen.getByText('Momentum').closest('tr')).toHaveTextContent('₹150.00')
  expect(screen.getByText('Version 2')).toBeInTheDocument()
  expect(document.querySelector('.portfolio-line')).toHaveAttribute('points', '24,220 776,24')
  expect(screen.getByText('Unattributed strategy')).toBeInTheDocument()
  expect(screen.queryByText('private-key')).not.toBeInTheDocument()
})

it('retries portfolio errors and renders a single real point without inventing history', async () => {
  const api = new StrategyApi()
  vi.spyOn(api, 'projects').mockResolvedValue([])
  const load = vi.spyOn(api, 'paperPortfolio').mockRejectedValueOnce(new Error('Paper history unavailable')).mockResolvedValue({
    currency: 'INR', untraded_strategies: [], as_of: emptyPortfolio.as_of, realized_pnl: 0, closed_trades: 1,
    points: [{ timestamp: '2026-09-04', realized_pnl: 0 }], strategies: [],
  })
  const router = createMemoryRouter([{ path: '/', element: <PortfolioPanel api={api} /> }])
  const { container } = render(<RouterProvider router={router} />)
  expect(await screen.findByRole('alert')).toHaveTextContent('This information is unavailable. Try again.')
  expect(screen.queryByRole('img')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Retry portfolio' }))
  expect(await screen.findByRole('img', { name: /₹0.00 across 1 closed trades/ })).toBeInTheDocument()
  expect(container.querySelector('polyline')?.getAttribute('points')).toBe('24,220')
  expect(container.querySelectorAll('.portfolio-dot')).toHaveLength(1)
  expect(load).toHaveBeenCalledTimes(2)
})

it('lists saved strategies with no paper trades without presenting a zero return', async () => {
  const router = await routed('/portfolio')
  const portfolio = { ...emptyPortfolio, untraded_strategies: [{ strategy_key: 'ir.private', strategy_version: 'sha256:private', display_name: 'Unrun strategy' }] }
  const previous = globalThis.fetch
  vi.stubGlobal('fetch', vi.fn((url: string, options?: RequestInit) => url === '/api/v1/paper-portfolio' ? Promise.resolve(json(portfolio)) : previous(url, options)))
  await router.navigate('/')
  await router.navigate('/portfolio')
  const name = await screen.findByText('Unrun strategy')
  expect(name.closest('tr')).toHaveTextContent('No closed paper trades')
  expect(screen.getByRole('cell', { name: 'No realized result' })).toHaveTextContent('—')
  expect(screen.queryByRole('img')).not.toBeInTheDocument()
  expect(screen.getByText('Saved version')).toBeInTheDocument()
  expect(screen.queryByText('sha256:private')).not.toBeInTheDocument()
})

it('shows a truthful direct Watchlists refusal and no sidebar action when the capability is blocked', async () => {
  await routed('/watchlists')
  expect(await screen.findByText('Static watchlists are not available in this server release.')).toHaveAttribute('role', 'status')
  expect(screen.queryByRole('button', { name: 'Watchlists' })).not.toBeInTheDocument()
  expect(vi.mocked(globalThis.fetch).mock.calls.some(([url]) => String(url).includes('static-scopes'))).toBe(false)
})

it('opens one saved watchlist member directly in Backtest and preserves project navigation', async () => {
  transport()
  const api = new StrategyApi(); await api.bootstrap(new AbortController().signal)
  const profile = structuredClone(release)
  Object.assign(profile.capabilities.static_watchlists, { state: 'ENABLED_WITH_LIMIT', ui_navigation: true })
  Object.assign(profile.capabilities.backtesting, { state: 'ENABLED_WITH_LIMIT' })
  const manifest = parseManifest(profile), savedGraph = { ...graph, current_version: 1 }
  const address = (digit: string) => `sha256:${digit.repeat(64)}`
  const dataset = { manifest_address: address('a'), instrument_address: address('1'), canonical_instrument_label: 'RELIANCE', instrument_display_name: 'RELIANCE · XNSE · EQUITY SPOT',
    asset_class: 'EQUITY', contract_kind: 'SPOT', interval: '1d', event_start: '2025-01-01T00:00:00Z', event_end: '2025-12-31T00:00:00Z', availability_end: '2026-01-01T00:00:00Z', as_of: '2026-01-02T00:00:00Z', bar_count: 248,
    fields: ['OPEN', 'HIGH', 'LOW', 'CLOSE'], provider_evidence_state: 'VERIFIED_REFERENCES_PRESENT' as const, market_truth_state: 'VERIFIED_REFERENCES_PRESENT' as const, gaps: [], backtest_eligibility: 'ELIGIBLE_Q03' as const, refusal_code: null }
  const scope = { scope_id: 'scope.route', name: 'Growth', status: 'active' as const, current_revision: 1, address: address('5'), membership_address: address('6'),
    member_labels: [{ instrument_address: dataset.instrument_address, display_name: null }],
    snapshot: { schema: 'static-instrument-scope/1' as const, owner_id: 'owner.a', project_id: project.project_id, scope_id: 'scope.route', revision: 1, predecessor: null, members: [dataset.instrument_address] } }
  vi.spyOn(api, 'staticScopes').mockResolvedValue({ items: [scope], next_cursor: null })
  vi.spyOn(api, 'staticScope').mockResolvedValue(scope)
  vi.spyOn(api, 'researchDatasets').mockResolvedValue([dataset])
  vi.spyOn(api, 'graphs').mockResolvedValue({ schema: 'strategy-os-graph-index/1', project_id: project.project_id, items: [savedGraph], next_cursor: null })
  vi.spyOn(api, 'v2Version').mockResolvedValue({ format_version: 2, graph_identifier: graph.identifier, graph_version: 1, content_address: address('b'),
    document: { format_version: 2, strategy_id: graph.identifier, metadata: { tags: [] }, graph_inputs: [{ port_id: 'frame', direction: 'input', semantic_role: 'market_frame' }] } })
  vi.spyOn(api, 'researchRecovery').mockResolvedValue({ complete: true, requests: [] })
  const values = { research_capital: 100000, seed: 0, min_trades: 10, n_folds: 4, min_positive_fold_frac: .6, risk_policy: 'none' as const }
  vi.spyOn(api, 'strategyResearchSettings').mockResolvedValue({ values, sources: {}, workspace: { owner_id: 'owner.a', graph_identifier: null, revision: 1, enabled: true, values, content_address: address('c') },
    strategy: { owner_id: 'owner.a', graph_identifier: graph.identifier, revision: 0, enabled: true, values: {}, content_address: address('d') } })
  const router = createMemoryRouter(productRouteObjects({ api, manifest, restoreFocus: true }), { initialEntries: [`/watchlists/${project.project_id}`] })
  render(<ProductRouteHost router={router} />)
  fireEvent.click(await screen.findByRole('button', { name: 'Open Growth' }))
  fireEvent.click(await screen.findByRole('button', { name: dataset.instrument_display_name }))
  await chooseSelect('Historical dataset', dataset.manifest_address)
  await chooseSelect('Saved strategy', graph.identifier)
  fireEvent.click(screen.getByRole('button', { name: 'Open Backtest' }))
  await screen.findByRole('heading', { name: 'Backtest' })
  await waitFor(() => expect(screen.getByRole('combobox', { name: 'Historical dataset' })).toHaveTextContent(dataset.canonical_instrument_label))
  expect(router.state.location.pathname).toBe(`/strategies/${project.project_id}/${graph.identifier}`)
  expect(router.state.location.state.watchlistMember).toMatchObject({ revision: 1, address: scope.address, dataset_manifest_address: dataset.manifest_address })
  expect(within(screen.getByRole('navigation', { name: 'Selected strategy sections' })).getByRole('button', { name: 'Backtest' })).toHaveAttribute('aria-current', 'page')
  fireEvent.click(within(screen.getByRole('navigation', { name: 'Global navigation' })).getByRole('button', { name: 'Watchlists' }))
  expect(await screen.findByRole('heading', { name: 'Watchlists' })).toBeInTheDocument()
  expect(router.state.location.pathname).toBe(`/watchlists/${project.project_id}`)
  expect(router.state.location.state.watchlistMember).toBeUndefined()
})


it('opens dedicated settings and saves workspace defaults with revision protection', async () => {
  transport()
  const api = new StrategyApi()
  const values = { research_capital: 100000, seed: 0, min_trades: 20, n_folds: 5, min_positive_fold_frac: .6, risk_policy: 'none' as const }
  const revision = { supportedValuesSchema: 'research-values/2' as const, owner_id: 'owner.a', graph_identifier: null, revision: 1, enabled: true, values, content_address: `sha256:${'a'.repeat(64)}` }
  vi.spyOn(api, 'workspaceResearchSettings').mockResolvedValue(revision)
  const save = vi.spyOn(api, 'saveResearchSettings').mockResolvedValue({ ...revision, revision: 2, values: { ...values, n_folds: 8, stop_loss_pct: .01, take_profit_pct: 0 } })
  const router = createMemoryRouter(productRouteObjects({ api, manifest: parseManifest(release), restoreFocus: false }), { initialEntries: ['/settings'] })
  render(<ProductRouteHost router={router} />)
  expect(await screen.findByRole('heading', { name: 'Settings', level: 1 })).toBeVisible()
  const folds = await screen.findByRole('spinbutton', { name: /Walk-forward folds/ })
  await waitFor(() => expect(folds).toHaveValue(5))
  fireEvent.change(folds, { target: { value: '8' } })
  expect(screen.getByRole('spinbutton', { name: 'Stop loss (%)' })).toHaveValue(0)
  fireEvent.change(screen.getByRole('spinbutton', { name: 'Stop loss (%)' }), { target: { value: '1' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save settings' }))
  await waitFor(() => expect(save).toHaveBeenCalledWith(expect.objectContaining({ expected_revision: 1, values: { ...values, n_folds: 8, stop_loss_pct: .01, take_profit_pct: 0 } }), expect.any(AbortSignal), undefined))
  expect(await screen.findByText(/Settings saved/)).toBeVisible()
  router.dispose()
})


it('keeps equal strategy overrides explicit and clears percentage fields to inherited values', async () => {
  const values = { research_capital: 100000, seed: 0, min_trades: 20, n_folds: 5, min_positive_fold_frac: .6, risk_policy: 'none' as const, stop_loss_pct: .01, take_profit_pct: .02 }
  const workspace = { schema: 'research-settings-revision/2' as const, owner_id: 'owner.a', graph_identifier: null, revision: 1, enabled: true, values, content_address: `sha256:${'a'.repeat(64)}` }
  const strategy = { ...workspace, graph_identifier: graph.identifier, values: { stop_loss_pct: .01 } }
  const api = { strategyResearchSettings: vi.fn().mockResolvedValue({ workspace, strategy }), saveResearchSettings: vi.fn().mockResolvedValue({ ...strategy, revision: 2, values: {} }) } as unknown as StrategyApi
  const onEditSignals = vi.fn()
  render(<SettingsWorkspace api={api} strategy={{ projectId: project.project_id, graphId: graph.identifier }} onEditSignals={onEditSignals} />)
  const stop = await screen.findByRole('spinbutton', { name: 'Stop loss (%)' })
  await waitFor(() => expect(stop).toHaveValue(1))
  expect(screen.getByRole('spinbutton', { name: 'Take profit (%)' })).toHaveValue(2)
  expect(screen.getByText('Strategy override')).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: 'Use workspace value' }))
  expect(stop).toHaveValue(1)
  fireEvent.click(screen.getByRole('button', { name: 'Save settings' }))
  await waitFor(() => expect(api.saveResearchSettings).toHaveBeenCalledWith(expect.objectContaining({ values: {} }), expect.any(AbortSignal), expect.objectContaining({ enabled: true })))
  fireEvent.click(screen.getByRole('button', { name: 'Open full builder' }))
  expect(onEditSignals).toHaveBeenCalledOnce()
})


it('saves one account entry limit and retains the amount after permission refusal', async () => {
  const identity = vi.spyOn(browserAuth, 'useBrowserIdentity').mockReturnValue({ user: { id: 'user.a', display_name: 'Owner' }, organization_id: 'owner.a', memberships: [{ organization_id: 'owner.a', name: 'Desk', role: 'owner' }], expires_at: '2027-01-01T00:00:00Z' })
  const rows = accountRiskFields.map(({ key }) => ({ key, value: 0, default: 0, overridden: false }))
  const saveAccountRiskSetting = vi.fn().mockRejectedValueOnce(new ApiError('input', 'Permission refused.', { code: 'ACCOUNT_RISK_FORBIDDEN', message: 'Permission refused.' })).mockResolvedValue(1500)
  const api = { accountRiskSettings: vi.fn().mockResolvedValue(rows), saveAccountRiskSetting } as unknown as StrategyApi
  try {
    render(<AccountRiskSettings api={api} />)
    const input = screen.getByLabelText('Daily net realized loss limit (INR)')
    await waitFor(() => expect(input).toBeEnabled())
    expect(screen.getAllByRole('spinbutton')).toHaveLength(3)
    expect(screen.getByText(/Strategy overrides cannot change/)).toBeVisible()
    fireEvent.change(input, { target: { value: '' } })
    fireEvent.submit(input.closest('form')!)
    expect(screen.getByText('Enter an amount. Use 0 to disable this limit.')).toBeVisible()
    expect(saveAccountRiskSetting).not.toHaveBeenCalled()
    fireEvent.change(input, { target: { value: '1500' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save daily net realized loss limit (inr)' }))
    expect(await screen.findByText(/Your workspace role cannot change/)).toBeVisible()
    expect(input).toHaveValue(1500)
    fireEvent.click(screen.getByRole('button', { name: 'Save daily net realized loss limit (inr)' }))
    expect(await screen.findByText(/Entry limit saved/)).toBeVisible()
    expect(saveAccountRiskSetting).toHaveBeenLastCalledWith('max_daily_loss', 1500, expect.any(AbortSignal))
    expect(screen.getByText(/Workspace override · Saved value ₹1,500/)).toBeVisible()
    fireEvent.click(screen.getByRole('button', { name: 'Reload account entry limits' }))
    await waitFor(() => expect(input).toHaveValue(0))
  } finally { identity.mockRestore() }
})

it('keeps account entry limits read-only for a viewer and retries failed reads', async () => {
  const identity = vi.spyOn(browserAuth, 'useBrowserIdentity').mockReturnValue({ user: { id: 'user.a', display_name: 'Viewer' }, organization_id: 'owner.a', memberships: [{ organization_id: 'owner.a', name: 'Desk', role: 'viewer' }], expires_at: '2027-01-01T00:00:00Z' })
  const rows = accountRiskFields.map(({ key }) => ({ key, value: 0, default: 0, overridden: false }))
  const api = { accountRiskSettings: vi.fn().mockRejectedValueOnce(new Error('Unavailable')).mockResolvedValue(rows), saveAccountRiskSetting: vi.fn() } as unknown as StrategyApi
  try {
    render(<AccountRiskSettings api={api} />)
    expect(await screen.findByText('This information is unavailable. Try again.')).toBeVisible()
    fireEvent.click(screen.getByRole('button', { name: 'Reload account entry limits' }))
    await waitFor(() => expect(screen.getByLabelText('Daily net realized loss limit (INR)')).toHaveValue(0))
    expect(screen.getByText(/Only workspace owners and administrators/)).toBeVisible()
    for (const input of screen.getAllByRole('spinbutton')) expect(input).toBeDisabled()
    fireEvent.submit(screen.getByLabelText('Daily net realized loss limit (INR)').closest('form')!)
    expect(api.saveAccountRiskSetting).not.toHaveBeenCalled()
  } finally { identity.mockRestore() }
})


function signalSettingsFixture() {
  const definitions = [
    { name: 'length', type: 'int', required: false, default: 20, enum: null, domain: { minimum: 1, maximum: 100 }, units: 'bars', serialization: 'canonical-json' },
    { name: 'enabled', type: 'bool', required: false, default: false, enum: null, domain: null, units: 'boolean', serialization: 'canonical-json' },
    { name: 'label', type: 'str', required: false, default: 'trend', enum: null, domain: null, units: 'text', serialization: 'canonical-json' },
  ]
  const catalogue = { groups: [{ components: [{ component_id: 'indicators.ema', component_version: 1, display_name: 'Moving average', help: { customisation: { parameters: definitions } } }] }] } as unknown as VerifiedCatalogue
  const initial: V2Draft = { project_id: project.project_id, graph_identifier: graph.identifier, semantic_revision: 5, current_version: 2, published_revision: 5,
    content_address: `sha256:${'a'.repeat(64)}`, graph_address: `sha256:${'b'.repeat(64)}`,
    document: { format_version: 2, strategy_id: graph.identifier, strategy_version: 3, metadata: { name: 'Trend', description: '', tags: [], metadata_version: 1 }, graph_inputs: [], graph_outputs: [], edges: [],
      nodes: [{ node_id: 'ema', component: { component_id: 'indicators.ema', component_version: 1 }, parameters: { length: 20 } }] } }
  const commands = [{ command: 'set_parameter', node_id: 'ema', parameter_id: 'length', value: 30 }]
  const saved: V2Draft = { ...initial, semantic_revision: 6, content_address: `sha256:${'c'.repeat(64)}`, graph_address: `sha256:${'d'.repeat(64)}`,
    document: { ...initial.document, nodes: [{ ...initial.document.nodes[0], parameters: { length: 30 } }] } }
  const current: V2Draft = { ...saved, current_version: 3, published_revision: 6, content_address: `sha256:${'e'.repeat(64)}`, document: { ...saved.document, strategy_version: 4 } }
  const receipt = { schema: 'strategy-os-v2-semantic-receipt/2', commit_state: 'DRAFT_COMMITTED', intent: 'EDIT', base_semantic_revision: 5, result_semantic_revision: 6,
    base_content_address: initial.content_address, result_content_address: saved.content_address, base_graph_address: initial.graph_address, result_graph_address: saved.graph_address,
    forward_commands: commands, inverse_commands: [], receipt_address: `sha256:${'f'.repeat(64)}` }
  const publication = { schema: 'strategy-os-v2-publish-receipt/1', project_id: project.project_id, graph_identifier: graph.identifier, graph_version: 3, semantic_revision: 6,
    content_address: saved.content_address, graph_address: saved.graph_address, canonical_document: saved.document, receipt_address: `sha256:${'f'.repeat(64)}` }
  const version = { format_version: 2, graph_identifier: graph.identifier, graph_version: 3, graph_address: saved.graph_address, content_address: saved.content_address, document: saved.document }
  const client = { catalogue: vi.fn().mockResolvedValue(catalogue), v2Draft: vi.fn().mockResolvedValueOnce(initial).mockResolvedValueOnce(saved).mockResolvedValue(current),
    validateV2: vi.fn().mockResolvedValue({ ...receipt, commit_state: 'DRY_RUN_ROLLED_BACK' }), mutateV2: vi.fn().mockResolvedValue(receipt),
    publishV2: vi.fn().mockResolvedValue(publication), v2Version: vi.fn().mockResolvedValue(version), mutateV2Presentation: vi.fn(), saveResearchSettings: vi.fn() }
  return { client, catalogue, initial, saved, current, receipt, publication, version, commands, api: client as unknown as StrategyApi }
}
function renderSignalSettings(fixture: ReturnType<typeof signalSettingsFixture>, onPublished = vi.fn()) {
  render(<SignalParameterSettings api={fixture.api} projectId={project.project_id} graphId={graph.identifier} currentVersion={2} onPublished={onPublished} />)
  return onPublished
}
const signalLengthLabel = 'Moving average · 1: Length (bars)'

it('edits signal parameters in Settings through validated draft CAS and a verified saved version', async () => {
  const fixture = signalSettingsFixture(), onPublished = renderSignalSettings(fixture)
  const length = await screen.findByRole('spinbutton', { name: signalLengthLabel })
  expect(length).toHaveValue(20)
  fireEvent.change(length, { target: { value: '1.5' } })
  expect(screen.getByRole('alert')).toHaveTextContent('Enter a whole number.')
  expect(fixture.client.validateV2).not.toHaveBeenCalled()
  fireEvent.change(length, { target: { value: '30' } })
  expect(screen.getByText(/1 pending parameter changes/)).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: 'Save parameters and version' }))
  expect(await screen.findByText(/Saved strategy version 3/)).toBeVisible()
  expect(fixture.client.validateV2).toHaveBeenCalledWith(project.project_id, graph.identifier, 5, fixture.commands, expect.any(AbortSignal))
  expect(fixture.client.mutateV2).toHaveBeenCalledWith(project.project_id, graph.identifier, 5, fixture.commands, 'EDIT', null, expect.any(AbortSignal))
  expect(fixture.client.publishV2).toHaveBeenCalledWith(project.project_id, graph.identifier, 6, 2, expect.any(AbortSignal))
  expect(onPublished).toHaveBeenCalledWith({ project_id: project.project_id, identifier: graph.identifier, version: 3, content_address: fixture.saved.content_address })
  expect(length).toHaveValue(30)
  expect(fixture.client.mutateV2Presentation).not.toHaveBeenCalled()
  expect(fixture.client.saveResearchSettings).not.toHaveBeenCalled()
})

it('keeps rejected signal inputs and sends typed boolean/string values only as IR commands', async () => {
  const fixture = signalSettingsFixture(); renderSignalSettings(fixture)
  await screen.findByRole('spinbutton', { name: signalLengthLabel })
  fixture.client.validateV2.mockRejectedValue(new ApiError('input', 'Parameter combination refused.'))
  await chooseSelect('Moving average · 1: Enabled (boolean)', 'true')
  fireEvent.change(screen.getByRole('textbox', { name: 'Moving average · 1: Label (text)' }), { target: { value: 'swing trend' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save parameters and version' }))
  expect(await screen.findByText(/Your parameter edits are retained/)).toBeVisible()
  expect(screen.getByRole('combobox', { name: 'Moving average · 1: Enabled (boolean)' })).toHaveTextContent('Yes')
  expect(screen.getByRole('textbox', { name: 'Moving average · 1: Label (text)' })).toHaveValue('swing trend')
  expect(fixture.client.validateV2.mock.calls[0][3]).toEqual([{ command: 'set_parameter', node_id: 'ema', parameter_id: 'enabled', value: true }, { command: 'set_parameter', node_id: 'ema', parameter_id: 'label', value: 'swing trend' }])
  expect(fixture.client.mutateV2).not.toHaveBeenCalled()
})

it('clears an explicit-equal signal parameter and publishes its declared default', async () => {
  const fixture = signalSettingsFixture(), onPublished = renderSignalSettings(fixture)
  await screen.findByRole('spinbutton', { name: signalLengthLabel })
  const commands = [{ command: 'clear_parameter', node_id: 'ema', parameter_id: 'length' }]
  const saved = { ...fixture.saved, graph_address: fixture.initial.graph_address, document: { ...fixture.saved.document, nodes: [{ ...fixture.saved.document.nodes[0], parameters: {} }] } }
  const current = { ...saved, current_version: 3, published_revision: 6, document: { ...saved.document, strategy_version: 4 } }
  const receipt = { ...fixture.receipt, forward_commands: commands, result_graph_address: saved.graph_address }
  fixture.client.validateV2.mockResolvedValue({ ...receipt, commit_state: 'DRY_RUN_ROLLED_BACK' })
  fixture.client.mutateV2.mockResolvedValue(receipt)
  fixture.client.v2Draft.mockReset().mockResolvedValueOnce(saved).mockResolvedValue(current)
  fixture.client.publishV2.mockResolvedValue({ ...fixture.publication, graph_address: saved.graph_address, canonical_document: saved.document })
  fixture.client.v2Version.mockResolvedValue({ ...fixture.version, graph_address: saved.graph_address, document: saved.document })
  fireEvent.click(screen.getByRole('button', { name: 'Use component default for Length (bars)' }))
  expect(screen.getByRole('spinbutton', { name: signalLengthLabel })).toHaveValue(20)
  fireEvent.click(screen.getByRole('button', { name: 'Save parameters and version' }))
  expect(await screen.findByText(/Saved strategy version 3/)).toBeVisible()
  expect(fixture.client.validateV2).toHaveBeenCalledWith(project.project_id, graph.identifier, 5, commands, expect.any(AbortSignal))
  expect(screen.getByText('Saved: 20 · Component default')).toBeVisible()
  expect(onPublished).toHaveBeenCalledOnce()
  expect(fixture.client.saveResearchSettings).not.toHaveBeenCalled()
})


it('recovers an uncertain parameter write without repeating the already-applied mutation', async () => {
  const fixture = signalSettingsFixture(), onPublished = renderSignalSettings(fixture)
  const length = await screen.findByRole('spinbutton', { name: signalLengthLabel })
  fixture.client.mutateV2.mockRejectedValue(new ApiError('network', 'Response lost.'))
  fireEvent.change(length, { target: { value: '30' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save parameters and version' }))
  expect(await screen.findByText(/Your parameter edits are retained/)).toBeVisible()
  expect(length).toHaveValue(30)
  expect(screen.getByRole('button', { name: 'Save parameters and version' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: 'Reload latest draft' }))
  await waitFor(() => expect(screen.getByRole('button', { name: 'Save new version' })).toBeEnabled())
  fireEvent.click(screen.getByRole('button', { name: 'Save new version' }))
  expect(await screen.findByText(/Saved strategy version 3/)).toBeVisible()
  expect(fixture.client.mutateV2).toHaveBeenCalledOnce()
  expect(fixture.client.validateV2).toHaveBeenCalledOnce()
  expect(onPublished).toHaveBeenCalledOnce()
})

it('refuses substituted draft values before publishing and retains the edited signal parameter', async () => {
  const fixture = signalSettingsFixture(); renderSignalSettings(fixture)
  const length = await screen.findByRole('spinbutton', { name: signalLengthLabel })
  fixture.client.v2Draft.mockReset().mockResolvedValue({ ...fixture.saved, document: { ...fixture.saved.document, nodes: [{ ...fixture.saved.document.nodes[0], parameters: { length: 31 } }] } })
  fireEvent.change(length, { target: { value: '30' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save parameters and version' }))
  expect(await screen.findByText(/saved parameters do not match your edits/)).toBeVisible()
  expect(length).toHaveValue(30)
  expect(fixture.client.publishV2).not.toHaveBeenCalled()
})

it('rejects a mismatched published signal version before notifying the workspace', async () => {
  const fixture = signalSettingsFixture(), onPublished = renderSignalSettings(fixture)
  const length = await screen.findByRole('spinbutton', { name: signalLengthLabel })
  fixture.client.v2Version.mockResolvedValue({ ...fixture.version, document: { ...fixture.saved.document, nodes: fixture.initial.document.nodes } })
  fireEvent.change(length, { target: { value: '30' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save parameters and version' }))
  expect(await screen.findByText(/saved version could not be matched to your parameters/)).toBeVisible()
  expect(length).toHaveValue(30)
  expect(onPublished).not.toHaveBeenCalled()
})


it('recovers a published signal version after a lost publication response without publishing twice', async () => {
  const fixture = signalSettingsFixture(), onPublished = renderSignalSettings(fixture)
  const length = await screen.findByRole('spinbutton', { name: signalLengthLabel })
  fixture.client.publishV2.mockRejectedValue(new ApiError('network', 'Publication reply lost.'))
  fireEvent.change(length, { target: { value: '30' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save parameters and version' }))
  expect(await screen.findByText(/Parameters are saved in the draft; the new version is not yet verified/)).toBeVisible()
  expect(onPublished).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Reload latest draft' }))
  await waitFor(() => expect(onPublished).toHaveBeenCalledWith(expect.objectContaining({ version: 3, content_address: fixture.saved.content_address })))
  expect(length).toHaveValue(30)
  expect(fixture.client.publishV2).toHaveBeenCalledOnce()
  expect(screen.getByRole('button', { name: 'Save new version' })).toBeDisabled()
})

it('retains signal input when a concurrent edit removes its node until explicit discard', async () => {
  const fixture = signalSettingsFixture(); renderSignalSettings(fixture)
  const length = await screen.findByRole('spinbutton', { name: signalLengthLabel })
  fixture.client.v2Draft.mockReset().mockResolvedValue({ ...fixture.initial, document: { ...fixture.initial.document, nodes: [] } })
  fireEvent.change(length, { target: { value: '30' } })
  fireEvent.click(screen.getByRole('button', { name: 'Reload latest draft' }))
  expect(await screen.findByText(/An edited parameter was removed/)).toBeVisible()
  expect(length).toHaveValue(30)
  expect(screen.getByRole('button', { name: 'Save parameters and version' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: 'Discard pending edits and reload' }))
  expect(await screen.findByText(/No editable parameters in this draft/)).toBeVisible()
})

it('cancels signal validation and clears private edit state when the API context changes', async () => {
  const fixture = signalSettingsFixture(), next = signalSettingsFixture(), onPublished = vi.fn()
  let resolveValidation!: (value: unknown) => void
  fixture.client.validateV2.mockImplementation(() => new Promise((resolve) => { resolveValidation = resolve }))
  const view = render(<SignalParameterSettings api={fixture.api} projectId={project.project_id} graphId={graph.identifier} currentVersion={2} onPublished={onPublished} />)
  const length = await screen.findByRole('spinbutton', { name: signalLengthLabel })
  fireEvent.change(length, { target: { value: '30' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save parameters and version' }))
  view.rerender(<SignalParameterSettings api={next.api} projectId={project.project_id} graphId={graph.identifier} currentVersion={2} onPublished={onPublished} />)
  await act(async () => resolveValidation({ ...fixture.receipt, commit_state: 'DRY_RUN_ROLLED_BACK' }))
  await waitFor(() => expect(screen.getByRole('spinbutton', { name: signalLengthLabel })).toHaveValue(20))
  expect(fixture.client.mutateV2).not.toHaveBeenCalled()
  expect(onPublished).not.toHaveBeenCalled()
})

it('checks signal parameter numeric domains and preserves invalid structured input', () => {
  const fixture = signalSettingsFixture(), rows = signalParameters(fixture.initial, fixture.catalogue), row = rows[0]
  for (const raw of ['', '0', '101', '1.5', 'null']) expect(prepareParameterEdits(rows, { [row.key]: { mode: 'set', raw } }).errors[row.key]).toBeTruthy()
  for (const raw of ['1', '100']) expect(prepareParameterEdits(rows, { [row.key]: { mode: 'set', raw } }).errors).toEqual({})
  const float = { ...row, definition: { ...row.definition, type: 'float' } }
  expect(prepareParameterEdits([float], { [row.key]: { mode: 'set', raw: '1e999' } }).errors[row.key]).toBe('Enter a finite number.')
  expect(prepareParameterEdits(rows, { missing: { mode: 'set', raw: '30' } }).errors.missing).toMatch(/no longer exists/)
})


it('renders declared enum and structured signal parameters without losing rejected text', async () => {
  const fixture = signalSettingsFixture(), component = fixture.catalogue.groups[0].components[0]
  const extra = [
    { name: 'mode', type: 'str', required: false, default: 'fast', enum: ['fast', 'slow'], domain: null, units: 'choice', serialization: 'canonical-json' },
    { name: 'weights', type: 'list', required: false, default: [1, 2], enum: null, domain: null, units: 'ratios', serialization: 'canonical-json' },
  ]
  fixture.client.catalogue.mockResolvedValue({ groups: [{ components: [{ ...component, help: { ...component.help, customisation: { ...component.help.customisation, parameters: [...component.help.customisation.parameters, ...extra] } } }] }] })
  fixture.client.validateV2.mockRejectedValue(new ApiError('input', 'Parameter combination refused.'))
  renderSignalSettings(fixture)
  await screen.findByRole('combobox', { name: 'Moving average · 1: Mode (choice)' })
  const weights = screen.getByRole('textbox', { name: 'Moving average · 1: Weights (ratios)' })
  await chooseSelect('Moving average · 1: Mode (choice)', '"slow"')
  fireEvent.change(weights, { target: { value: '{bad' } })
  expect(screen.getByRole('alert')).toHaveTextContent('Enter a valid value before saving.')
  expect(weights).toHaveValue('{bad')
  fireEvent.change(weights, { target: { value: '[2,3]' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save parameters and version' }))
  await waitFor(() => expect(fixture.client.validateV2).toHaveBeenCalled())
  expect(fixture.client.validateV2.mock.calls[0][3]).toEqual([{ command: 'set_parameter', node_id: 'ema', parameter_id: 'mode', value: 'slow' }, { command: 'set_parameter', node_id: 'ema', parameter_id: 'weights', value: [2, 3] }])
  expect(weights).toHaveValue('[2,3]')
})


it('does not treat a committed receipt as signal dry-run validation or duplicate a rapid save', async () => {
  const fixture = signalSettingsFixture(); renderSignalSettings(fixture)
  const length = await screen.findByRole('spinbutton', { name: signalLengthLabel })
  fixture.client.validateV2.mockResolvedValue(fixture.receipt)
  fireEvent.change(length, { target: { value: '30' } })
  const save = screen.getByRole('button', { name: 'Save parameters and version' })
  act(() => { save.click(); save.click() })
  expect(await screen.findByText(/Parameter validation could not be verified/)).toBeVisible()
  expect(fixture.client.validateV2).toHaveBeenCalledOnce()
  expect(fixture.client.mutateV2).not.toHaveBeenCalled()
  expect(length).toHaveValue(30)
})


it('keeps an independently verified signal version after the following draft refresh fails', async () => {
  const fixture = signalSettingsFixture(), onPublished = renderSignalSettings(fixture)
  const length = await screen.findByRole('spinbutton', { name: signalLengthLabel })
  fixture.client.v2Draft.mockReset().mockResolvedValueOnce(fixture.saved).mockResolvedValue({ ...fixture.current, semantic_revision: 7 })
  fireEvent.change(length, { target: { value: '30' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save parameters and version' }))
  expect(await screen.findByText(/Saved strategy version 3. Reload the latest draft before editing again/)).toBeVisible()
  expect(onPublished).toHaveBeenCalledWith(expect.objectContaining({ version: 3, content_address: fixture.saved.content_address }))
  expect(fixture.client.publishV2).toHaveBeenCalledOnce()
  expect(screen.getByRole('button', { name: 'Save new version' })).toBeDisabled()
  expect(length).toHaveValue(30)
})

it('rejects substituted signal mutation commands before reading or publishing the draft', async () => {
  const fixture = signalSettingsFixture(); renderSignalSettings(fixture)
  const length = await screen.findByRole('spinbutton', { name: signalLengthLabel })
  fixture.client.mutateV2.mockResolvedValue({ ...fixture.receipt, forward_commands: [{ ...fixture.commands[0], value: 31 }] })
  fireEvent.change(length, { target: { value: '30' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save parameters and version' }))
  expect(await screen.findByText(/saved parameter commands do not match your edits/)).toBeVisible()
  expect(fixture.client.v2Draft).toHaveBeenCalledOnce()
  expect(fixture.client.publishV2).not.toHaveBeenCalled()
  expect(length).toHaveValue(30)
})

it('gates the stored alert route independently from monitoring activation', async () => {
  const profile = structuredClone(release)
  Object.assign(profile.capabilities.signals, { state: 'ENABLED_WITH_LIMIT', ui_navigation: true })
  const manifest = parseManifest(profile)
  expect(enabledProductRoutes(manifest)).toContainEqual({ id: 'alerts', path: '/alerts', capability: 'signals' })
  expect(manifest.capabilities.monitoring?.state).toBe('BLOCKED')
  transport()
  const api = new StrategyApi()
  await api.bootstrap(new AbortController().signal)
  vi.spyOn(api, 'session').mockResolvedValue({ user: { id: 'person', email: 'test@example.com', display_name: 'Test' }, organization_id: 'workspace', memberships: [{ organization_id: 'workspace', name: 'Workspace', role: 'member' }], expires_at: '2026-09-07T00:00:00Z' } as never)
  const load = vi.spyOn(api, 'monitoringAlerts').mockResolvedValue({ items: [], nextCursor: null })
  const router = createMemoryRouter(productRouteObjects({ api, manifest, restoreFocus: true }), { initialEntries: ['/alerts'] })
  render(<ProductRouteHost router={router} />)
  expect(await screen.findByRole('heading', { name: 'Alerts Inbox' })).toBeVisible()
  await waitFor(() => expect(load).toHaveBeenCalledOnce())
})


it('configures only explicit saved numeric search axes without editing the strategy', async () => {
  const fixture=signalSettingsFixture()
  function Harness(){const [value,setValue]=useState(disabledOptimization());return <><OptimizationSettingsFields api={fixture.api} strategy={{projectId:project.project_id,graphId:graph.identifier}} currentVersion={3} value={value} disabled={false} onChange={setValue}/><output>{JSON.stringify(value)}</output></>}
  render(<Harness />)
  const enable=await screen.findByRole('checkbox',{name:'Enable bounded development search'})
  await waitFor(()=>expect(enable).toBeEnabled());fireEvent.click(enable)
  expect(screen.getByRole('alert')).toHaveTextContent('Choose 1–4 parameters')
  await chooseSelect('Add optimization parameter',JSON.stringify(['ema','length']))
  expect(screen.getByText('Baseline in version 3: 30')).toBeInTheDocument()
  for(const [field,value] of [['step','1'],['minimum','20'],['maximum','40']]) fireEvent.change(screen.getByRole('textbox',{name:new RegExp(` ${field}$`)}),{target:{value}})
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  fireEvent.change(screen.getByRole('textbox',{name:/ step$/}),{target:{value:'0'}})
  expect(screen.getByRole('alert')).toHaveTextContent('greater than zero')
  fireEvent.click(screen.getByRole('button',{name:'Remove search parameter 1'}))
  expect(screen.getByRole('alert')).toHaveTextContent('Choose 1–4 parameters')
  fireEvent.click(enable);expect(screen.queryByLabelText('Add optimization parameter')).not.toBeInTheDocument()
  expect(fixture.client.mutateV2).not.toHaveBeenCalled();expect(fixture.client.publishV2).not.toHaveBeenCalled()
})
it('keeps global search disabled without loading a strategy', () => {
  const fixture=signalSettingsFixture();render(<OptimizationSettingsFields api={fixture.api} value={disabledOptimization()} disabled={false} onChange={vi.fn()}/>)
  expect(screen.getByText(/Search is off in workspace defaults/)).toBeInTheDocument();expect(fixture.client.v2Version).not.toHaveBeenCalled()
})
it('shows unpublished development selection separately from failed later gates and refuses wrong run identity', async () => {
  const search=parseCanonicalOptimizationEvidence(optimizationFixture,optimizationFixture.selected.canonical_document.strategy_id)
  const run={run_id:7,graph:{project_id:project.project_id},status:'completed',decision:'archive',evidence_state:'verified',canonical_optimization:search,optimization_research_gates:[{instrument:'SYNTHETIC',passed:false,gates:{pbo:{passed:false,value:1}}}]}
  const experiment=vi.fn().mockResolvedValue(run),api={experiment} as unknown as StrategyApi
  const view=render(<CanonicalOptimizationResults api={api} projectId={project.project_id} runId={7}/>)
  expect(await screen.findByText('Candidate selected on development data')).toBeInTheDocument()
  expect(screen.getByText('Selected parameters — not published')).toBeInTheDocument();expect(screen.getByText('SYNTHETIC: Did not pass')).toBeInTheDocument()
  expect(screen.getByText(/PBO gate uses development trials/)).toBeInTheDocument()
  expect(document.body.textContent).not.toMatch(/sha256:|recipe:|content:|graph:|research_result_address|format_version|canonical_document|axis_000/i)
  expect(document.querySelector('pre, code')).toBeNull()
  expect(screen.queryByText('Selected strategy document and lineage')).not.toBeInTheDocument()
  expect(screen.getByText('Candidate population (3)')).toBeInTheDocument()
  expect(screen.getAllByText('Window: 1').length).toBeGreaterThan(0)
  const finalTrials = screen.getByText('Final development trials (3)').closest('details')!
  fireEvent.click(screen.getByText('Final development trials (3)'))
  expect(within(finalTrials).getAllByRole('row')[1]).toHaveTextContent('Window: 2')
  expect(within(finalTrials).getAllByRole('row')[2]).toHaveTextContent('Window: 1')
  expect(screen.getByText('Development data through')).toBeInTheDocument()
  expect(screen.getByText('Later test window')).toBeInTheDocument()
  expect(screen.getByText('2025-08-21 18:30:00 UTC')).toBeInTheDocument()
  view.rerender(<CanonicalOptimizationResults api={api} projectId={project.project_id} runId={8}/>)
  expect(screen.queryByText('Selected parameters — not published')).not.toBeInTheDocument()
  expect(await screen.findByRole('status')).toHaveTextContent('returned run does not match')
  experiment.mockResolvedValue({...run,run_id:8,evidence_state:'failed'})
  fireEvent.click(screen.getByRole('button',{name:'Retry search details'}))
  expect(await screen.findByRole('status')).toHaveTextContent('Search evidence has not been verified')
})


function homeFixture() {
  const saved = { ...graph, current_version: 2 }
  const draft: V2Draft = { project_id: project.project_id, graph_identifier: graph.identifier, semantic_revision: 4, published_revision: 3, current_version: 2,
    document: { format_version: 2, strategy_id: graph.identifier, strategy_version: 3, metadata: { name: graph.display_name, description: null, metadata_version: 1, tags: [] }, nodes: [], edges: [], graph_inputs: [], graph_outputs: [] }, content_address: `sha256:${'a'.repeat(64)}`, graph_address: `sha256:${'b'.repeat(64)}` }
  const client = { projects: vi.fn().mockResolvedValue([project]), graphs: vi.fn().mockResolvedValue({project_id:project.project_id,items:[saved],next_cursor:null}), v2Draft:vi.fn().mockResolvedValue(draft), experiments:vi.fn().mockResolvedValue({runs:[]}), researchDatasets:vi.fn().mockResolvedValue([]), paperPortfolio:vi.fn() }
  return {api:client as unknown as StrategyApi,client,draft,saved}
}
function homeRun(run_id: number, status='completed', version=2) {
  return {run_id,status,evidence_state:'verified',decision:'archive',spec_id:'a'.repeat(32),graph:{project_id:project.project_id,identifier:graph.identifier,version,content_address:`sha256:${'a'.repeat(64)}`},dataset_bindings:[],contract:null}
}
function homeRender(api:StrategyApi){return render(<MemoryRouter><HomeWorkspace api={api}/></MemoryRouter>)}
it.each([null, 2])('Home resumes a verified saved draft and does not duplicate portfolio or invent recency (version %s)', async(currentVersion)=>{
  const fixture=homeFixture()
  fixture.client.graphs.mockResolvedValue({project_id:project.project_id,items:[{...fixture.saved,current_version:currentVersion}],next_cursor:null})
  fixture.client.v2Draft.mockResolvedValue({...fixture.draft,current_version:currentVersion})
  homeRender(fixture.api)
  expect(await screen.findByText('Continue your draft')).toBeInTheDocument()
  expect(screen.getByRole('heading',{name:graph.display_name})).toBeInTheDocument()
  const resume=screen.getAllByRole('link',{name:'Resume draft'})
  expect(resume[0]).toHaveAttribute('href',`/strategies/${project.project_id}/${graph.identifier}?view=build`)
  expect(screen.queryByRole('region',{name:'Portfolio'})).not.toBeInTheDocument();expect(fixture.client.paperPortfolio).not.toHaveBeenCalled()
  expect(document.body.textContent).not.toMatch(/most recent draft|yesterday|weekend|return|profit|Draft revision|Latest run records/i)
  expect(document.querySelector('.home-work-context')).toHaveTextContent(project.name + ' · ' + (currentVersion === null ? 'Draft' : `Saved version ${currentVersion}`))
})
it.each([
  ['no_history','Add backtest history','Add history'],
  ['eligible','Backtest your saved version','Set up backtest'],
  ['history_unavailable','Check your backtest setup','Open Backtest'],
  ['index_only','Add backtest history','Add history'],
  ['unavailable_equity','Add backtest history','Add history'],
])('Home derives the saved-version next step from actual data: %s',async(kind,title,action)=>{
  const fixture=homeFixture();fixture.client.v2Draft.mockResolvedValue({...fixture.draft,published_revision:4})
  if(kind==='eligible')fixture.client.researchDatasets.mockResolvedValue([{asset_class:'EQUITY',backtest_eligibility:'ELIGIBLE_Q03',research_compatibility:'PRIMARY_BACKTEST'}])
  if(kind==='index_only')fixture.client.researchDatasets.mockResolvedValue([{asset_class:'INDEX',backtest_eligibility:'ELIGIBLE_Q03',research_compatibility:'BENCHMARK_INPUT_ONLY'}])
  if(kind==='unavailable_equity')fixture.client.researchDatasets.mockResolvedValue([{asset_class:'EQUITY',backtest_eligibility:'ELIGIBLE_Q03',research_compatibility:'UNAVAILABLE'}])
  if(kind==='history_unavailable')fixture.client.researchDatasets.mockRejectedValue(new Error('private failure payload'))
  homeRender(fixture.api)
  expect(await screen.findByText(title)).toBeInTheDocument()
  expect(screen.getAllByRole('link',{name:action})[0]).toHaveAttribute('href',`/strategies/${project.project_id}/${graph.identifier}?view=backtest`)
  expect(document.body.textContent).not.toContain('private failure payload')
})
it.each([
  ['pending','Check your research'],['running','Check your research'],['failed','Review an unfinished run'],['completed','Review your research'],
])('Home derives the current-version next step from a %s run',async(status,title)=>{
  const fixture=homeFixture();fixture.client.v2Draft.mockResolvedValue({...fixture.draft,published_revision:4});fixture.client.experiments.mockResolvedValue({runs:[homeRun(10,status)]})
  homeRender(fixture.api);expect(await screen.findByText(title)).toBeInTheDocument()
  expect(screen.getByText('Run 10 · Version 2 · Research desk')).toBeInTheDocument()
  expect(screen.getByRole('img')).toHaveAccessibleName(new RegExp(status==='failed'?'1 needs a look':status==='completed'?'1 completed':'1 in progress'))
})
it('Home does not treat an older-version result as a backtest of the new saved version',async()=>{
  const fixture=homeFixture();fixture.client.v2Draft.mockResolvedValue({...fixture.draft,published_revision:4});fixture.client.experiments.mockResolvedValue({runs:[homeRun(10,'completed',1)]});fixture.client.researchDatasets.mockResolvedValue([{asset_class:'EQUITY',backtest_eligibility:'ELIGIBLE_Q03'}])
  homeRender(fixture.api);expect(await screen.findByText('Backtest your saved version')).toBeInTheDocument();expect(screen.getByText('Run 10 · Version 1 · Research desk')).toBeInTheDocument()
})
it('Home orders recent run records by persisted ID and distinguishes corrupt evidence',async()=>{
  const fixture=homeFixture();fixture.client.v2Draft.mockResolvedValue({...fixture.draft,published_revision:4});fixture.client.experiments.mockResolvedValue({runs:[homeRun(2),{...homeRun(9),evidence_state:'corrupt'},homeRun(5,'running')]})
  homeRender(fixture.api);expect(await screen.findByText('Review a result issue')).toBeInTheDocument()
  const list=screen.getByRole('heading',{name:'Recent backtests'}).closest('section')!
  const rows=within(list).getAllByRole('listitem');expect(rows[0]).toHaveTextContent('Run 9');expect(rows[1]).toHaveTextContent('Run 5');expect(rows[2]).toHaveTextContent('Run 2')
  expect(rows[0]).toHaveTextContent('Evidence unavailable')
})
it('Home refuses mismatched draft and run context without rendering private returned names',async()=>{
  const fixture=homeFixture();fixture.client.v2Draft.mockResolvedValue({...fixture.draft,graph_identifier:'other',document:{...fixture.draft.document,metadata:{...fixture.draft.document.metadata,name:'PRIVATE OTHER DRAFT'}}});fixture.client.experiments.mockResolvedValue({runs:[{...homeRun(999),graph:{...homeRun(999).graph,project_id:'other'}}]})
  homeRender(fixture.api);expect(await screen.findByText('Open your strategy')).toBeInTheDocument();expect(document.body.textContent).not.toMatch(/PRIVATE OTHER DRAFT|999/)
  expect(screen.getByRole('status')).toHaveTextContent('Backtests, Draft details')
})
it('Home shows loading and clears old account work immediately when API context changes',async()=>{
  const snapshots:string[]=[]
  function Observe({api}:{api:StrategyApi}){useLayoutEffect(()=>{snapshots.push(document.body.textContent ?? '')});return <HomeWorkspace api={api}/>}
  const fixture=homeFixture();const view=render(<MemoryRouter><Observe api={fixture.api}/></MemoryRouter>);await screen.findByText('Continue your draft')
  let resolve!:(value:unknown[])=>void
  const next={projects:vi.fn().mockReturnValue(new Promise<unknown[]>(done=>{resolve=done}))} as unknown as StrategyApi
  snapshots.length=0;view.rerender(<MemoryRouter><Observe api={next}/></MemoryRouter>)
  expect(snapshots.every(text=>!text.includes(graph.display_name))).toBe(true)
  expect(screen.queryByText(graph.display_name)).not.toBeInTheDocument();expect(screen.getByRole('status')).toHaveTextContent('Loading your workspace')
  expect(screen.queryByText('Start a strategy')).not.toBeInTheDocument()
  await act(async()=>resolve([]));expect(await screen.findByText('Start a strategy')).toBeInTheDocument()
})
it('Home scopes cached work to browser workspace identity even when the API object is unchanged',async()=>{
  let identity={organization_id:'first',user:{id:'person',display_name:'Person'}}
  const identityHook=vi.spyOn(browserAuth,'useBrowserIdentity').mockImplementation(()=>identity as never)
  try{
    const snapshots:string[]=[]
    function Observe(){useLayoutEffect(()=>{snapshots.push(document.body.textContent ?? '')});return <HomeWorkspace api={fixture.api}/>}
    const fixture=homeFixture();const view=render(<MemoryRouter><Observe/></MemoryRouter>);await screen.findByText('Continue your draft')
    fixture.client.projects.mockReturnValue(new Promise(()=>{}));identity={...identity,organization_id:'second'}
    snapshots.length=0;view.rerender(<MemoryRouter><Observe/></MemoryRouter>)
    expect(snapshots.every(text=>!text.includes(graph.display_name))).toBe(true)
    expect(screen.queryByText(graph.display_name)).not.toBeInTheDocument();expect(screen.getByRole('status')).toHaveTextContent('Loading your workspace')
  }finally{identityHook.mockRestore()}
})
it('Home does not claim an empty workspace when strategy loading fails',async()=>{
  const fixture=homeFixture();fixture.client.graphs.mockRejectedValue(new Error('unavailable'));homeRender(fixture.api)
  expect(await screen.findByText('Your strategies are unavailable')).toBeInTheDocument();expect(screen.queryByText('Start a strategy')).not.toBeInTheDocument()
  expect(screen.getByRole('button',{name:'Retry workspace'})).toBeEnabled()
})

it('Home ignores a superseded response after another API context has loaded',async()=>{
  let resolve!:(value:unknown[])=>void
  const old=homeFixture();old.client.projects.mockReturnValue(new Promise<unknown[]>(done=>{resolve=done}))
  const next=homeFixture();next.client.projects.mockResolvedValue([])
  const view=homeRender(old.api);view.rerender(<MemoryRouter><HomeWorkspace api={next.api}/></MemoryRouter>)
  await screen.findByText('Start a strategy')
  await act(async()=>resolve([project]));expect(screen.queryByText(graph.display_name)).not.toBeInTheDocument();expect(screen.getByText('Start a strategy')).toBeInTheDocument()
})
it('Home refuses a strategy index belonging to a different project',async()=>{
  const fixture=homeFixture();fixture.client.graphs.mockResolvedValue({project_id:'other',items:[{...fixture.saved,display_name:'PRIVATE FOREIGN GRAPH'}],next_cursor:null});homeRender(fixture.api)
  expect(await screen.findByText('Your strategies are unavailable')).toBeInTheDocument();expect(screen.queryByText('PRIVATE FOREIGN GRAPH')).not.toBeInTheDocument();expect(fixture.client.v2Draft).not.toHaveBeenCalled()
})

it('saves the research risk policy from its real menu and keeps it disabled during save', async () => {
  const values = { research_capital: 100000, seed: 0, min_trades: 20, n_folds: 5, min_positive_fold_frac: .6, risk_policy: 'none' as const }
  const revision = { owner_id: 'owner.a', graph_identifier: null, revision: 1, enabled: true, values, content_address: `sha256:${'a'.repeat(64)}` }
  let finish!:(value:unknown)=>void
  const save = vi.fn().mockImplementation(()=>new Promise(done=>{finish=done}))
  const api={workspaceResearchSettings:vi.fn().mockResolvedValue(revision),saveResearchSettings:save} as unknown as StrategyApi
  render(<ResearchSettings api={api}/>)
  await waitFor(()=>expect(screen.getByRole('combobox',{name:'Risk policy'})).toBeEnabled())
  await chooseSelect('Risk policy','pine-v4-reversal/1')
  expect(screen.getByRole('combobox',{name:'Risk policy'})).toHaveTextContent('V4 stops and reversals · 1 unit')
  fireEvent.click(screen.getByRole('button',{name:'Save settings'}))
  await waitFor(()=>expect(save).toHaveBeenCalledOnce())
  expect(save.mock.calls[0][0].values.risk_policy).toBe('pine-v4-reversal/1')
  expect(screen.getByRole('combobox',{name:'Risk policy'})).toBeDisabled()
  fireEvent.keyDown(screen.getByRole('combobox',{name:'Risk policy'}),{key:'ArrowDown'})
  expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  await act(async()=>finish({...revision,revision:2,values:{...values,risk_policy:'pine-v4-reversal/1'}}))
  expect(screen.getByRole('combobox',{name:'Risk policy'})).toBeEnabled()
})

describe('Home links into strategy work', () => {
  it('opens saved draft work in Build and follows a later Backtest link without starting a run', async () => {
    const path = `/strategies/${project.project_id}/${graph.identifier}`
    const router = await routed(`${path}?view=build`, { ...graph, current_version: 2 })
    await screen.findByRole('heading', { name: graph.display_name })
    const sections = screen.getByRole('navigation', { name: 'Selected strategy sections' })
    expect(within(sections).getByRole('button', { name: 'Build' })).toHaveAttribute('aria-current', 'page')
    await act(async () => { await router.navigate(`${path}?view=backtest`) })
    await waitFor(() => expect(within(sections).getByRole('button', { name: 'Backtest' })).toHaveAttribute('aria-current', 'page'))
    const fetch = vi.mocked(globalThis.fetch)
    expect(fetch.mock.calls.map(([url]) => String(url))).not.toContain(
      `/api/v1/ir/projects/${project.project_id}/graphs/${graph.identifier}/versions/2/research-operations`)
  })

  it('ignores an unsupported view and opens the normal saved-strategy overview', async () => {
    await routed(`/strategies/${project.project_id}/${graph.identifier}?view=live`, { ...graph, current_version: 2 })
    await screen.findByRole('heading', { name: graph.display_name })
    expect(within(screen.getByRole('navigation', { name: 'Selected strategy sections' }))
      .getByRole('button', { name: 'Overview' })).toHaveAttribute('aria-current', 'page')
  })
})

function proposalFixture() {
  const fixture = signalSettingsFixture()
  const baseline = { ...fixture.version, graph_version: 2, graph_address: fixture.initial.graph_address,
    content_address: `sha256:${'9'.repeat(64)}`, document: { ...fixture.initial.document, strategy_version: 2 } }
  const selected: OptimizationSelection = {
    coordinates: { axis_000: '30' }, parameters: [{ node_id: 'ema', parameter_id: 'length', value: 30, normalized_value: '30' }],
    content_address: fixture.saved.content_address, graph_address: fixture.saved.graph_address, lineage: {},
    canonical_document: { ...baseline.document, nodes: fixture.saved.document.nodes },
  }
  const proposal: ParameterProposal = { runId: 7, baseline: { project_id: project.project_id, identifier: graph.identifier, version: 2, content_address: baseline.content_address }, selection: selected }
  const rows = signalParameters(fixture.initial, fixture.catalogue)
  return { ...fixture, baseline, proposal, rows }
}

it('distinguishes an isolated development peak from mixed and broad local support', async () => {
  const result = parseCanonicalOptimizationEvidence(optimizationFixture, optimizationFixture.selected.canonical_document.strategy_id)
  const view = render(<OptimizationNeighborhood result={result} />)
  expect(screen.getByText('Isolated high score in this tested grid.')).toBeInTheDocument()
  expect(screen.getByText('1 of 3 tested settings are within 10% of the selected development score.')).toBeInTheDocument()
  expect(within(screen.getByRole('table')).getAllByRole('row')).toHaveLength(4)
  const mixed = { ...result, final_development_trials: result.final_development_trials.map((row, index) => ({ ...row, objective: [80, 100, 95][index] })) }
  view.rerender(<OptimizationNeighborhood result={mixed} />)
  expect(screen.getByText('Mixed sensitivity in this tested grid.')).toBeInTheDocument()
  expect(screen.getByText('2 of 3 tested settings are within 10% of the selected development score.')).toBeInTheDocument()
  await chooseSelect('Score comparison tolerance', '20')
  expect(screen.getByText('Similar scores across this tested grid.')).toBeInTheDocument()
  expect(screen.getByText('3 of 3 tested settings are within 20% of the selected development score.')).toBeInTheDocument()
  expect(screen.getByText(/not a research gate/)).toHaveTextContent('does not prove a setting is safe')
})

it('does not infer a plateau from incomplete, ineligible or nonpositive scores', () => {
  const result = parseCanonicalOptimizationEvidence(optimizationFixture, optimizationFixture.selected.canonical_document.strategy_id)
  for (const score of [null, 0, -1]) {
    const changed = { ...result, final_development_trials: result.final_development_trials.map((row) => ({ ...row, objective: score })) }
    expect(developmentNeighborhood(changed, 10).comparable).toBe(false)
    expect(developmentNeighborhood(changed, 10).near).toBe(0)
  }
  const partial = { ...result, final_development_trials: result.final_development_trials.slice(0, 1) }
  const view = render(<OptimizationNeighborhood result={partial} />)
  expect(screen.getByText(/search has not evaluated the complete grid/)).toBeInTheDocument()
  expect(screen.getAllByText('Not eligible or not evaluated')).toHaveLength(2)
  view.rerender(<OptimizationNeighborhood result={{ ...result, final_development_trials: result.final_development_trials.map((row) => ({ ...row, objective: -1 })) }} />)
  expect(screen.getByText(/selected score is not positive/)).toBeInTheDocument()
})

it('prepares exactly the reviewed candidate parameter delta against the immutable run baseline', () => {
  const fixture = proposalFixture()
  const edits = proposalParameterEdits(fixture.proposal, fixture.initial, fixture.baseline, fixture.rows)
  expect(edits).toEqual({ '["ema","length"]': { mode: 'set', raw: '30' } })
  expect(prepareParameterEdits(fixture.rows, edits).commands).toEqual(fixture.commands)
  expect(fixture.initial.document.nodes[0].parameters).toEqual({ length: 20 })
  expect(fixture.proposal.selection.canonical_document.nodes[0].parameters).toEqual({ length: 30 })
})

it.each(['version', 'unsaved', 'owner-project', 'graph', 'content', 'draft-rules', 'extra-rule', 'missing-node', 'duplicate', 'limits'])(
  'refuses an optimization suggestion with a changed %s boundary', (change) => {
    const fixture = proposalFixture()
    const draft = structuredClone(fixture.initial), baseline = structuredClone(fixture.baseline), proposal = structuredClone(fixture.proposal)
    if (change === 'version') Object.assign(draft, { current_version: 3 })
    if (change === 'unsaved') Object.assign(draft, { published_revision: 4 })
    if (change === 'owner-project') Object.assign(draft, { project_id: 'another-project' })
    if (change === 'graph') Object.assign(draft, { graph_identifier: 'another-graph' })
    if (change === 'content') baseline.content_address = `sha256:${'8'.repeat(64)}`
    if (change === 'draft-rules') Object.assign(draft.document.nodes[0].parameters, { enabled: true })
    if (change === 'extra-rule') Object.assign(proposal.selection.canonical_document.nodes[0].parameters, { enabled: true })
    if (change === 'missing-node') Object.assign(proposal.selection.parameters[0], { node_id: 'absent' })
    if (change === 'duplicate') Object.assign(proposal.selection, { parameters: [...proposal.selection.parameters, proposal.selection.parameters[0]] })
    if (change === 'limits') { Object.assign(proposal.selection.parameters[0], { value: 101 }); Object.assign(proposal.selection.canonical_document.nodes[0].parameters, { length: 101 }) }
    expect(() => proposalParameterEdits(proposal, draft, baseline, fixture.rows)).toThrow()
  },
)

it('reviews an optimization suggestion without writes and saves only after the user accepts the values', async () => {
  const fixture = proposalFixture(), onPublished = vi.fn(), onOpenBuilder = vi.fn()
  fixture.client.v2Version.mockReset().mockResolvedValueOnce(fixture.baseline).mockResolvedValue(fixture.version)
  render(<SignalParameterSettings api={fixture.api} projectId={project.project_id} graphId={graph.identifier} currentVersion={2}
    proposal={fixture.proposal} onPublished={onPublished} onOpenBuilder={onOpenBuilder} />)
  const field = await screen.findByRole('spinbutton', { name: signalLengthLabel })
  expect(field).toHaveValue(30)
  expect(screen.getByText(/Review the parameters suggested by run 7/)).toBeInTheDocument()
  expect(screen.getByText('Saved: 20 · Strategy value · Pending edit')).toBeInTheDocument()
  expect(fixture.client.mutateV2).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Save parameters and version' }))
  await waitFor(() => expect(onPublished).toHaveBeenCalledWith({ project_id: project.project_id, identifier: graph.identifier, version: 3, content_address: fixture.saved.content_address }))
  expect(fixture.client.mutateV2.mock.calls[0][3]).toEqual(fixture.commands)
  expect(fixture.client.publishV2).toHaveBeenCalledOnce()
  expect(await screen.findByText(/Saved strategy version 3. New backtests/)).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Open full builder' }))
  expect(onOpenBuilder).toHaveBeenCalledOnce()
})

it('keeps a newer draft untouched when reviewing a stale optimization result', async () => {
  const fixture = proposalFixture()
  fixture.client.v2Draft.mockReset().mockResolvedValue(fixture.current)
  fixture.client.v2Version.mockResolvedValue(fixture.baseline)
  render(<SignalParameterSettings api={fixture.api} projectId={project.project_id} graphId={graph.identifier} currentVersion={3} proposal={fixture.proposal} />)
  expect(await screen.findByRole('status')).toHaveTextContent('changed since the optimization run')
  expect(screen.getByRole('button', { name: 'Save new version' })).toBeDisabled()
  expect(fixture.client.mutateV2).not.toHaveBeenCalled()
  expect(fixture.client.publishV2).not.toHaveBeenCalled()
})

it('connects the selected optimization result to reviewed parameter publication and the updated builder', async () => {
  const fixture = proposalFixture(), onPublished = vi.fn(), onOpenBuilder = vi.fn()
  fixture.client.v2Version.mockReset().mockResolvedValueOnce(fixture.baseline).mockResolvedValue(fixture.version)
  const original = parseCanonicalOptimizationEvidence(optimizationFixture, optimizationFixture.selected.canonical_document.strategy_id)
  const search = { ...original, selected: fixture.proposal.selection }
  const run = { run_id: 7, graph: fixture.proposal.baseline, status: 'completed', decision: 'archive', evidence_state: 'verified', canonical_optimization: search }
  const api = { ...fixture.client, experiment: vi.fn().mockResolvedValue(run) } as unknown as StrategyApi
  render(<CanonicalOptimizationResults api={api} projectId={project.project_id} runId={7} onPublished={onPublished} onOpenBuilder={onOpenBuilder} />)
  fireEvent.click(await screen.findByRole('button', { name: 'Review selected parameters' }))
  expect(await screen.findByRole('spinbutton', { name: signalLengthLabel })).toHaveValue(30)
  expect(fixture.client.mutateV2).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Save parameters and version' }))
  expect(await screen.findByText('New research version 3 saved')).toBeInTheDocument()
  expect(onPublished).toHaveBeenCalledOnce()
  await waitFor(() => expect(screen.getByRole('button', { name: 'Open full builder' })).toBeEnabled())
  fireEvent.click(screen.getByRole('button', { name: 'Open full builder' }))
  expect(onOpenBuilder).toHaveBeenCalledOnce()
})

it('shows an unqualified real-data outcome without inventing a chart or a holdout pass', async () => {
  const run = { run_id: 7, graph: { project_id: project.project_id, version: 5 }, evidence_state: 'verified', status: 'completed', decision: 'archive',
    research_outcome: { qualified: 0, validated: 0, total_bars: 248, rejected: [{ instrument: 'ci_private_key', reason: 'insufficient trades (4<10)' }] } }
  const experiment = vi.fn().mockResolvedValue(run)
  const view = render(<CanonicalOptimizationResults api={{ experiment } as unknown as StrategyApi} projectId={project.project_id} runId={7} />)
  expect(await screen.findByText('Did not meet development requirements.')).toBeInTheDocument()
  expect(screen.getByText('Only 4 development trades; at least 10 were required.')).toBeInTheDocument()
  expect(screen.getByText(/Later-window validation did not run/)).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Review selected parameters' })).not.toBeInTheDocument()
  expect(document.body.textContent).not.toContain('ci_private_key')
  experiment.mockResolvedValue({ ...run, run_id: 8, research_outcome: { ...run.research_outcome, qualified: 1, validated: 0, rejected: [] } })
  view.rerender(<CanonicalOptimizationResults api={{ experiment } as unknown as StrategyApi} projectId={project.project_id} runId={8} />)
  expect(await screen.findByText(/1 instrument checks qualified on development data; 0 passed later validation/)).toBeInTheDocument()
})


it('explains that baseline rejection prevented candidate evaluation', async () => {
  const search = parseCanonicalOptimizationEvidence(optimizationFixture, optimizationFixture.selected.canonical_document.strategy_id)
  const run = { run_id: 7, graph: { project_id: project.project_id }, status: 'completed', decision: 'archive', evidence_state: 'verified',
    canonical_optimization: { ...search, state: 'not_qualified', reason_code: 'BASELINE_NOT_QUALIFIED', selected: null, nested_trials: [], final_development_trials: [], n_trials: 0 } }
  render(<CanonicalOptimizationResults api={{ experiment: vi.fn().mockResolvedValue(run) } as unknown as StrategyApi} projectId={project.project_id} runId={7} />)
  expect(await screen.findByText('Baseline did not qualify; search did not start')).toBeInTheDocument()
  expect(screen.getByText(/Neighboring candidates were not evaluated/)).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Review selected parameters' })).not.toBeInTheDocument()
})


it('injects the data connection client into the watchlist draft search', async () => {
  transport()
  const api = new StrategyApi()
  await api.bootstrap(new AbortController().signal)
  const profile = structuredClone(providerManifest())
  Object.assign(profile.capabilities.static_watchlists, { state: 'ENABLED_WITH_LIMIT', ui_navigation: true })
  vi.spyOn(api, 'projects').mockResolvedValue([{ ...project, status: 'active' }])
  vi.spyOn(api, 'staticScopes').mockResolvedValue({ items: [], next_cursor: null })
  vi.spyOn(api, 'researchDatasets').mockResolvedValue([])
  vi.spyOn(api, 'graphs').mockResolvedValue({ schema: 'strategy-os-graph-index/1', project_id: project.project_id, items: [], next_cursor: null })
  const provider = vi.spyOn(api, 'dataConnectionTransport').mockResolvedValue({ status: 200,
    headers: { contentType: 'application/json', cacheControl: 'no-store' },
    body: { schema: 'strategy-os-provider-instrument-search/2', provider: 'ZERODHA', reference_type: 'CURRENT_PROVIDER_REFERENCE',
      query: 'NIFTY', exchange: 'ALL', available_exchanges: ['NSE', 'MCX'], has_more: false, items: [] } })
  const router = createMemoryRouter(productRouteObjects({ api, manifest: profile, restoreFocus: true }), { initialEntries: [`/watchlists/${project.project_id}`] })
  render(<RouterProvider router={router} />)
  fireEvent.click(await screen.findByRole('button', { name: 'New watchlist' }))
  fireEvent.change(screen.getByRole('searchbox', { name: 'Provider symbol or name' }), { target: { value: 'nifty' } })
  fireEvent.click(screen.getByRole('button', { name: 'Search provider' }))
  expect(await screen.findByText('No instruments matched. Try another symbol or name.')).toBeInTheDocument()
  expect(provider).toHaveBeenCalledWith(expect.objectContaining({ method: 'GET', path: '/api/v1/data-connections/instruments?query=nifty&exchange=ALL&limit=20' }))
  router.dispose()
})
