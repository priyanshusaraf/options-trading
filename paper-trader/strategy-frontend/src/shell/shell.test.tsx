import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import release from '../test/releaseManifest.json'
import { chooseSelect } from '../test/select'
import { ApiError, StrategyApi, type RestMethod } from './api'
import { parseGraphPage, parseManifest, parseProjects, type GraphSummary } from './contracts'

const signal = () => new AbortController().signal
const session = { user: { id: 'synthetic.user', display_name: 'Synthetic user' }, organization_id: 'synthetic.org',
  memberships: [{ organization_id: 'synthetic.org', name: 'Test workspace', role: 'owner' }], expires_at: '2026-08-30T00:00:00Z', csrf: 'a'.repeat(64) }
const accountStatus = { schema: 'account-commerce-status/1', profile_state: 'COMPLETE',
  satisfied_field_codes: ['profile.country', 'profile.full_name'], profile_attested_at: '2026-08-29T00:00:00Z',
  trial_state: 'USED_ACTIVE', trial_source: 'BETA_TRIAL', trial_expires_at: '2026-09-13T00:00:00Z',
  access_state: 'ACTIVE', access_expires_at: '2026-09-13T00:00:00Z', evaluated_at: '2026-08-29T00:00:00Z' }
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'content-type': 'application/json', 'cache-control': 'no-store' } })
const project = { project_id: 'project.test-a', name: 'Research desk', description: 'Server description', status: 'active' }
const second = { ...project, project_id: 'project.test-b', name: 'Second desk' }
const graph: GraphSummary = { identifier: 'graph.canonical-a', display_name: 'Canonical graph', draft_revision: 3, current_version: null }
const page = (items = [graph], projectId = project.project_id) => ({ schema: 'strategy-os-graph-index/1', project_id: projectId, items, next_cursor: null })
const projectPage = (items: unknown) => ({ schema: 'strategy-os-research-project-page/1', items, next_cursor: null })
const runPage = (projectId = project.project_id) => ({ schema: 'strategy-os-research-run-page/1', project_id: projectId, runs: [], next_cursor: null })
function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((res) => { resolve = res })
  return { promise, resolve }
}
function transport(projects: unknown = [project], graphs: unknown = page()) {
  const fetch = vi.fn(async (url: string, _options?: RequestInit) => {
    if (url === '/api/v1/auth/session') return json(session)
    if (url === '/api/v1/release-profile') return json(release)
    if (url === '/api/v1/account-commerce/status') return json(accountStatus)
    if (url === '/api/v1/ir/projects/research-spine/index?limit=50') return json(projectPage(projects))
    if (url === `/api/v1/ir/projects/${project.project_id}/graphs?limit=50`) return json(graphs)
    if (url === `/api/v1/ir/projects/${project.project_id}/graphs/${graph.identifier}/versions`) return json([])
    if (url === `/api/v1/ir/projects/${project.project_id}/research-spine/experiments?limit=25`) return json(runPage())
    throw new Error(`Unexpected request: ${url}`)
  })
  vi.stubGlobal('fetch', fetch)
  return fetch
}
function renderStrategies() {
  history.replaceState(null, '', '/strategies')
  return render(<App />)
}
// JSDOM does not implement native dialogs; native focus is verified in Chromium.
const dialogMethods = ['showModal', 'close'] as const
const dialogDescriptors = dialogMethods.map(name => Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype, name))
beforeEach(() => {
  Object.defineProperty(HTMLDialogElement.prototype, 'showModal', { configurable: true, value() { this.open = true } })
  Object.defineProperty(HTMLDialogElement.prototype, 'close', { configurable: true, value() { this.open = false; this.dispatchEvent(new Event('close')) } })
})
afterEach(() => {
  cleanup(); vi.unstubAllGlobals(); vi.useRealTimers()
  history.replaceState(null, '', '/')
  dialogMethods.forEach((name, i) => { const descriptor = dialogDescriptors[i]; if (descriptor) Object.defineProperty(HTMLDialogElement.prototype, name, descriptor); else Reflect.deleteProperty(HTMLDialogElement.prototype, name) })
})

describe('manifest-first production shell', () => {
  it('manifest barrier keeps every product component closed during loading', async () => {
    const pending = deferred<Response>()
    const fetch = vi.fn().mockReturnValue(pending.promise)
    vi.stubGlobal('fetch', fetch)
    render(<App />)
    expect(screen.getByRole('status')).toHaveTextContent('Loading release information')
    expect(screen.queryByText('Strategies', { exact: true })).not.toBeInTheDocument()
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Project')).not.toBeInTheDocument()
    expect(fetch.mock.calls.map((call) => call[0])).toEqual(['/api/v1/release-profile'])
    await act(async () => pending.resolve(json(null)))
    expect(await screen.findByRole('heading', { name: 'Release unavailable' })).toBeInTheDocument()
  })

  it.each([null, {}, { ...release, release_profile: 'standard' }, { ...release, execution_authority: true },
    { ...release, capabilities: { strategy_graph: { state: 'ENABLED', ui_navigation: true } } }])('refuses malformed/non-V0 truth %#', async (value) => {
    const fetch = vi.fn().mockResolvedValue(json(value)); vi.stubGlobal('fetch', fetch)
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'Release unavailable' })).toBeInTheDocument()
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Project')).not.toBeInTheDocument()
    expect(fetch).toHaveBeenCalledTimes(1)
  })

  it('shows only a server-owned blocked reason when strategy navigation is disabled', async () => {
    const manifest = structuredClone(release)
    Object.assign(manifest.capabilities.strategy_graph, { state: 'BLOCKED', ui_navigation: false, reason: 'Server policy: strategies are paused.' })
    const fetch = vi.fn().mockResolvedValue(json(manifest)); vi.stubGlobal('fetch', fetch)
    render(<App />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Server policy: strategies are paused.')
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument()
    expect(fetch).toHaveBeenCalledTimes(1)
  })

  it('recovers a failed release request by verifying again before project access', async () => {
    const fetch = transport([])
    fetch.mockRejectedValueOnce(new TypeError('network failed'))
    renderStrategies()
    expect(await screen.findByRole('alert')).toHaveTextContent('could not be reached')
    fireEvent.click(screen.getByRole('button', { name: 'Retry release check' }))
    expect(await screen.findByRole('heading', { name: 'No projects available' })).toBeInTheDocument()
    expect(fetch.mock.calls.map((call) => call[0])).toEqual(['/api/v1/release-profile', '/api/v1/release-profile', '/api/v1/auth/session', '/api/v1/account-commerce/status', '/api/v1/ir/projects/research-spine/index?limit=50'])
  })

  it('creates an empty authenticated V2 graph without a raw document fallback', async () => {
    vi.spyOn(crypto, 'randomUUID').mockReturnValue('a1111111-1111-4111-8111-111111111111')
    const createdProject = { ...project, project_id: 'project.created', name: 'Created desk' }
    const createdGraph = { ...graph, identifier: 'a1111111-1111-4111-8111-111111111111', display_name: 'Created graph' }
    let projectExists = false
    let graphExists = false
    const requests: Array<{ url: string; body?: unknown }> = []
    const fetch = vi.fn(async (url: string, options?: RequestInit) => {
      requests.push({ url, body: typeof options?.body === 'string' ? JSON.parse(options.body) : undefined })
      if (url === '/api/v1/release-profile') return json(release)
      if (url === '/api/v1/auth/session') return json(session)
      if (url === '/api/v1/account-commerce/status') return json(accountStatus)
      if (url === '/api/v1/ir/projects/research-spine/index?limit=50') return json(projectPage(projectExists ? [createdProject] : []))
      if (url === '/api/v1/ir/projects' && options?.method === 'POST') { projectExists = true; return json(createdProject, 201) }
      if (url === `/api/v1/ir/projects/${createdProject.project_id}/graphs?limit=50`) return json(page(graphExists ? [createdGraph] : [], createdProject.project_id))
      if (url === `/api/v1/ir/projects/${createdProject.project_id}/graphs/v2/create` && options?.method === 'POST') {
        graphExists = true; return json({ project_id: createdProject.project_id, graph_identifier: createdGraph.identifier, semantic_revision: 0,
          current_version: null, published_revision: null, document: { format_version: 2, strategy_id: createdGraph.identifier, strategy_version: 1,
            metadata: { metadata_version: 1, name: createdGraph.display_name, description: 'Owner research graph', tags: [] }, graph_inputs: [], graph_outputs: [], nodes: [], edges: [] },
          content_address: `sha256:${'a'.repeat(64)}`, graph_address: `sha256:${'b'.repeat(64)}` }, 201)
      }
      if (url === `/api/v1/ir/projects/${createdProject.project_id}/graphs/${createdGraph.identifier}/versions`) return json([])
      if (url === `/api/v1/ir/projects/${createdProject.project_id}/research-spine/experiments?limit=25`) return json(runPage(createdProject.project_id))
      throw new Error(`Unexpected request: ${url}`)
    })
    vi.stubGlobal('fetch', fetch)
    renderStrategies()
    expect(await screen.findByRole('heading', { name: 'No projects available' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Create project' }))
    fireEvent.change(screen.getByLabelText('Project name'), { target: { value: createdProject.name } })
    fireEvent.change(screen.getByLabelText('Description'), { target: { value: 'Owner research' } })
    fireEvent.click(screen.getByRole('button', { name: 'Create project' }))
    expect(await screen.findByRole('heading', { name: 'No graphs in this project' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'New strategy' }))
    fireEvent.click(screen.getByRole('button', { name: /Start fresh/ }))
    fireEvent.change(screen.getByLabelText('Strategy name'), { target: { value: createdGraph.display_name } })
    fireEvent.change(screen.getByLabelText(/Description/), { target: { value: 'Owner research graph' } })
    fireEvent.click(screen.getByRole('button', { name: 'Create strategy' }))
    expect(await screen.findByRole('heading', { name: createdGraph.display_name })).toBeInTheDocument()
    const graphWrite = requests.find((request) => request.url.endsWith(`/${createdProject.project_id}/graphs/v2/create`) && request.body)
    expect(graphWrite?.body).toEqual({ format_version: 2, identifier: createdGraph.identifier, name: createdGraph.display_name, description: 'Owner research graph' })
    expect(JSON.stringify(graphWrite?.body)).not.toMatch(/fixture|provider|execution|broker|capital|order|position/)
    expect(screen.queryByLabelText(/graph json/i)).not.toBeInTheDocument()
  })

  it('does not select or invent a project or graph, and shows empty graph truth', async () => {
    const fetch = transport([project], page([]))
    renderStrategies()
    expect(await screen.findByRole('heading', { name: 'Select a project' })).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: 'Project' })).toHaveTextContent('Select a project')
    expect(fetch).toHaveBeenCalledTimes(4)
    await chooseSelect('Project', project.project_id)
    expect(await screen.findByRole('heading', { name: 'No graphs in this project' })).toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: 'Selected strategy sections' })).not.toBeInTheDocument()
  })

  it('opens real record facts and preserves current navigation boundaries', async () => {
    const fetch = transport()
    renderStrategies()
    await screen.findByLabelText('Project')
    await chooseSelect('Project', project.project_id)
    fireEvent.click(await screen.findByRole('button', { name: `Open ${graph.display_name}` }))
    expect(await screen.findByRole('heading', { name: graph.display_name })).toHaveFocus()
    expect(screen.getByRole('navigation', { name: 'Selected strategy sections' })).toHaveTextContent('Overview')
    expect(screen.getByRole('button', { name: /^Build$/ })).toHaveAttribute('aria-current', 'page')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Context' }))
    const context = screen.getByRole('dialog', { name: 'Strategy context' })
    expect(within(context).getByText('Saved version')).toBeInTheDocument()
    expect(within(context).getByText('Not saved yet')).toBeInTheDocument()
    expect(within(context).getByText(project.name)).toBeInTheDocument()
    fireEvent.click(within(context).getByRole('button', { name: 'Close context' }))
    const globalNavigation = within(screen.getByRole('navigation', { name: 'Global navigation' }))
    expect(globalNavigation.getByRole('button', { name: 'Portfolio' })).toBeInTheDocument()
    expect(globalNavigation.queryByRole('button', { name: 'Watchlists' })).not.toBeInTheDocument()
    expect(within(screen.getByRole('navigation', { name: 'Studio lists' })).getByRole('button', { name: 'Watchlists' })).toBeInTheDocument()
    for (const name of ['Deploy', 'Live', 'Workspace', 'Chart', 'Signals', 'Robustness']) {
      expect(screen.queryByRole('button', { name })).not.toBeInTheDocument()
    }
    fireEvent.click(screen.getByRole('button', { name: 'Collapse navigation' }))
    expect(screen.getByRole('button', { name: 'Expand navigation' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'All strategies' }))
    expect(await screen.findByRole('heading', { name: 'Strategies' })).toHaveFocus()
    expect(screen.queryByRole('navigation', { name: 'Selected strategy sections' })).not.toBeInTheDocument()
    expect(fetch.mock.calls.every((call) => !call[0].includes('/ws'))).toBe(true)
  })

  it('discards a delayed graph response after switching project', async () => {
    const pending = deferred<Response>()
    const fetch = transport([project, second])
    fetch.mockImplementation(async (url) => {
      if (url.endsWith('auth/session')) return json(session)
      if (url.endsWith('release-profile')) return json(release)
      if (url.endsWith('account-commerce/status')) return json(accountStatus)
      if (url.includes('/ir/projects/research-spine/index?')) return json(projectPage([project, second]))
      if (url.includes(project.project_id)) return pending.promise
      return json(page([], second.project_id))
    })
    renderStrategies(); await screen.findByLabelText('Project')
    await chooseSelect('Project', project.project_id)
    await screen.findByLabelText('Project')
    expect(screen.getByRole('status')).toHaveTextContent('Loading graphs')
    await chooseSelect('Project', second.project_id)
    await screen.findByRole('heading', { name: 'No graphs in this project' })
    await act(async () => pending.resolve(json(page())))
    expect(screen.queryByText(graph.display_name)).not.toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: 'Project' })).toHaveTextContent(second.name)
  })

  it.each([401, 403, 500])('shows failed project access without a fake project for HTTP %s', async (status) => {
    const fetch = transport(); fetch.mockResolvedValueOnce(json(release)).mockResolvedValueOnce(json(session)).mockResolvedValueOnce(json(accountStatus)).mockResolvedValueOnce(json({}, status))
    renderStrategies()
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(screen.queryByLabelText('Project')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: status === 500 ? 'Retry' : 'Retry release check' }))
    expect(await screen.findByLabelText('Project')).toBeInTheDocument()
  })

  it('shows graph error and recovers without retaining old graph facts', async () => {
    const fetch = transport([project], { ...page(), project_id: second.project_id })
    renderStrategies(); await screen.findByLabelText('Project')
    await chooseSelect('Project', project.project_id)
    expect(await screen.findByRole('alert')).toHaveTextContent('could not be verified')
    expect(screen.queryByText(graph.display_name)).not.toBeInTheDocument()
    fetch.mockResolvedValueOnce(json(page()))
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(await screen.findByText(graph.display_name)).toBeInTheDocument()
  })

  it('pages using only server cursors and returns to the previous page', async () => {
    const items = Array.from({ length: 50 }, (_, i) => ({ ...graph, identifier: `graph.${i}`, display_name: `Graph ${i}` }))
    const first = { ...page(items), next_cursor: items[49].identifier }
    const fetch = transport([project], first)
    fetch.mockImplementation(async (url) => url.endsWith('auth/session') ? json(session) : url.endsWith('release-profile') ? json(release) : url.endsWith('account-commerce/status') ? json(accountStatus) : url.includes('/ir/projects/research-spine/index?') ? json(projectPage([project])) : url.includes('after=') ? json(page()) : json(first))
    renderStrategies(); await screen.findByLabelText('Project')
    await chooseSelect('Project', project.project_id)
    fireEvent.click(await screen.findByRole('button', { name: 'Next graphs' }))
    expect(await screen.findByText(graph.display_name)).toBeInTheDocument()
    expect(fetch.mock.calls.at(-1)?.[0]).toContain('after=graph.49')
    fireEvent.click(screen.getByRole('button', { name: 'Previous graphs' }))
    expect(await screen.findByText('Graph 0')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Saved graphs' })).toHaveFocus()
  })
})

describe('access generation revalidation', () => {
  it.each([401, 403])('drops retained manifest on HTTP %s and requires bootstrap', async (status) => {
    const fetch = transport(); const api = new StrategyApi(); await api.bootstrap(signal())
    fetch.mockResolvedValueOnce(json({}, status))
    await expect(api.graphs(project.project_id, null, signal())).rejects.toMatchObject({ kind: 'access' })
    const calls = fetch.mock.calls.length
    await expect(api.projects(signal())).rejects.toMatchObject({ kind: 'manifest' })
    expect(fetch).toHaveBeenCalledTimes(calls)
  })

  it.each([401, 403])('unmounts project facts on graph HTTP %s, then checks manifest before projects', async (status) => {
    const fetch = transport(); renderStrategies(); await screen.findByLabelText('Project')
    const original = fetch.getMockImplementation()!
    const refusedGraphUrl = `/api/v1/ir/projects/${project.project_id}/graphs?limit=50`
    let graphRefused = false
    fetch.mockImplementation(async (url, options) => {
      if (url === refusedGraphUrl && !graphRefused) { graphRefused = true; return json({}, status) }
      return original(url, options)
    })
    await chooseSelect('Project', project.project_id)
    expect(await screen.findByRole('alert')).toHaveTextContent('session no longer has access')
    expect(graphRefused).toBe(true)
    expect(screen.queryByLabelText('Project')).not.toBeInTheDocument()
    expect(screen.queryByText(project.description)).not.toBeInTheDocument()
    const calls = fetch.mock.calls.length
    fireEvent.click(screen.getByRole('button', { name: 'Retry release check' }))
    expect(await screen.findByRole('combobox', { name: 'Project' })).toHaveTextContent(project.name)
    await screen.findByText(graph.display_name)
    expect(fetch.mock.calls.slice(calls).map(call => call[0])).toEqual(['/api/v1/release-profile', '/api/v1/auth/session', '/api/v1/account-commerce/status', '/api/v1/ir/projects/research-spine/index?limit=50', `/api/v1/ir/projects/${project.project_id}/graphs?limit=50`])
  })

  it('rejects late old-generation project success even when transport ignores abort', async () => {
    const fetch = transport(); const api = new StrategyApi(); await api.bootstrap(signal())
    const pending = deferred<Response>(); fetch.mockReturnValueOnce(pending.promise)
    const old = api.projects(signal()); const assertion = expect(old).rejects.toMatchObject({ name: 'AbortError' })
    fetch.mockResolvedValueOnce(json({}, 403))
    await expect(api.graphs(project.project_id, null, signal())).rejects.toMatchObject({ kind: 'access' })
    await api.bootstrap(signal())
    pending.resolve(json([project])); await assertion
  })

  it('cannot restore a manifest from a delayed JSON body after a later check fails', async () => {
    const fetch = transport(); const api = new StrategyApi(); const body = deferred<unknown>()
    const response = json(release); vi.spyOn(response, 'json').mockReturnValue(body.promise)
    fetch.mockResolvedValueOnce(response)
    const old = api.bootstrap(signal()); const assertion = expect(old).rejects.toMatchObject({ name: 'AbortError' })
    await act(async () => {})
    fetch.mockResolvedValueOnce(json({}))
    await expect(api.bootstrap(signal())).rejects.toThrow('could not be verified')
    body.resolve(release); await assertion
    await expect(api.projects(signal())).rejects.toMatchObject({ kind: 'manifest' })
  })

  it('ignores stale access denial after a newer successful bootstrap', async () => {
    const fetch = transport(); const api = new StrategyApi(); await api.bootstrap(signal())
    const pending = deferred<Response>(); fetch.mockReturnValueOnce(pending.promise)
    const old = api.projects(signal()); const assertion = expect(old).rejects.toMatchObject({ name: 'AbortError' })
    await api.bootstrap(signal()); pending.resolve(json({}, 401)); await assertion
    await expect(api.projects(signal())).resolves.toEqual([project])
  })

  it('refresh clears facts while closed, then restores the verified URL selection after a successful retry', async () => {
    const fetch = transport(); renderStrategies(); await screen.findByLabelText('Project')
    await chooseSelect('Project', project.project_id)
    fireEvent.click(await screen.findByRole('button', { name: `Open ${graph.display_name}` }))
    await screen.findByRole('heading', { name: graph.display_name })
    fireEvent.click(screen.getByRole('button', { name: 'Context' }))
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    // Recheck is normally invoked after closing the modal. The direct event also
    // proves invalidation removes a mounted drawer rather than retaining its facts.
    const pending = deferred<Response>(); fetch.mockReturnValueOnce(pending.promise)
    fireEvent.click(screen.getByRole('button', { name: 'Refresh access and records', hidden: true }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.queryByText(graph.display_name)).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Project')).not.toBeInTheDocument()
    await act(async () => pending.resolve(json({})))
    expect(await screen.findByRole('alert')).toHaveTextContent('could not be verified')
    expect(screen.queryByText(project.name)).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Retry release check' }))
    expect(await screen.findByRole('combobox', { name: 'Project' })).toHaveTextContent(project.name)
    expect(await screen.findByRole('heading', { name: graph.display_name })).toHaveFocus()
  })

  it('access denial also removes an already mounted graph overview and context drawer', async () => {
    const fetch = transport(); const requests = vi.spyOn(StrategyApi.prototype, 'graphs')
    try {
      renderStrategies(); await screen.findByLabelText('Project')
      await chooseSelect('Project', project.project_id)
      fireEvent.click(await screen.findByRole('button', { name: `Open ${graph.display_name}` }))
      await screen.findByRole('heading', { name: graph.display_name })
      fireEvent.click(screen.getByRole('button', { name: 'Context' }))
      const api = requests.mock.contexts[0]
      if (!(api instanceof StrategyApi)) throw new Error('Expected the mounted shell API instance')
      fetch.mockResolvedValueOnce(json({}, 403))
      await act(async () => { await expect(api.graphs(project.project_id, null, signal())).rejects.toMatchObject({ kind: 'access' }) })
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      expect(screen.queryByText(graph.display_name)).not.toBeInTheDocument()
      expect(screen.queryByLabelText('Project')).not.toBeInTheDocument()
      expect(screen.getByRole('heading', { name: 'Release unavailable' })).toHaveFocus()
    } finally { requests.mockRestore() }
  })

  it('network failure stays distinct from access denial and does not revoke the manifest', async () => {
    const fetch = transport(); const api = new StrategyApi(); await api.bootstrap(signal())
    fetch.mockRejectedValueOnce(new TypeError('offline'))
    await expect(api.projects(signal())).rejects.toMatchObject({ kind: 'network' })
    await expect(api.projects(signal())).resolves.toEqual([project])
  })
})

describe('deep read contracts', () => {
  it('accepts the current server manifest and freezes the retained projection', () => {
    const result = parseManifest(release)
    expect(Object.isFrozen(result.capabilities.strategy_graph)).toBe(true)
  })
  it.each(Object.keys(release))('refuses a missing manifest field: %s', (key) => {
    const value: Record<string, unknown> = structuredClone(release); delete value[key]
    expect(() => parseManifest(value)).toThrow()
  })
  it.each(Object.keys(release.capabilities))('refuses a missing or malformed capability: %s', (key) => {
    const value = structuredClone(release)
    const capabilities = value.capabilities as Record<string, unknown>
    delete capabilities[key]; expect(() => parseManifest(value)).toThrow()
    capabilities[key] = { state: 'ENABLED', ui_navigation: 'true' }; expect(() => parseManifest(value)).toThrow()
  })
  it.each(['method', 'template', 'state', 'capability', 'reason'])('refuses missing or malformed rule field: %s', (key) => {
    const value = structuredClone(release)
    const rule = value.route_rules[0] as Record<string, unknown>
    delete rule[key]; expect(() => parseManifest(value)).toThrow()
    rule[key] = 1; expect(() => parseManifest(value)).toThrow()
  })
  it.each([{ route_rules: [] }, { allowed_service_roles: ['api'] }, { required_readiness_planes: ['execution', 'research'] },
    { research_enabled: 'true' }, { service_role: 'research_worker' }, { schema: 'unknown' }, { extra: true }])('refuses inconsistent manifest metadata %#', (patch) => {
    expect(() => parseManifest({ ...release, ...patch })).toThrow()
  })
  it('refuses duplicate rules, arrays as objects, unsafe states and wrong nested reasons', () => {
    expect(() => parseManifest({ ...release, route_rules: [release.route_rules[0], release.route_rules[0]] })).toThrow()
    expect(() => parseManifest({ ...release, capabilities: [] })).toThrow()
    for (const name of ['execution', 'orders', 'positions', 'execution_stream', 'capital_admission']) {
      expect(() => parseManifest({ ...release, capabilities: { ...release.capabilities, [name]: { state: 'ENABLED' } } })).toThrow()
    }
    expect(() => parseManifest({ ...release, capabilities: { ...release.capabilities, signals: { state: 'BLOCKED', reason: null } } })).toThrow()
  })
  it('rejects malformed projects, duplicate identities, mixed project pages and invalid facts', () => {
    for (const value of [null, {}, [project, project], [{ ...project, project_id: '' }], [{ ...project, status: 'unknown' }]]) expect(() => parseProjects(value)).toThrow()
    for (const value of [{ ...page(), project_id: second.project_id }, page([graph, graph]), page([{ ...graph, current_version: 0 }]),
      page([{ ...graph, draft_revision: -1 }]), { ...page(), next_cursor: 'invented' }]) expect(() => parseGraphPage(value, project.project_id, null, 50)).toThrow()
  })
})

describe('sole API client', () => {
  it('denies product requests before bootstrap and after revalidation fails', async () => {
    const fetch = transport(); const api = new StrategyApi()
    await expect(api.projects(signal())).rejects.toThrow('until the server release is verified')
    await expect(api.graphs(project.project_id, null, signal())).rejects.toThrow()
    expect(fetch).not.toHaveBeenCalled()
    await api.bootstrap(signal()); await api.projects(signal())
    fetch.mockResolvedValueOnce(json({}))
    await expect(api.bootstrap(signal())).rejects.toThrow()
    const calls = fetch.mock.calls.length
    await expect(api.projects(signal())).rejects.toThrow()
    expect(fetch).toHaveBeenCalledTimes(calls)
  })
  it.each([new Response('<html>fallback</html>', { headers: { 'content-type': 'text/html' } }), new Response('{broken', { headers: { 'content-type': 'application/json' } })])('refuses HTML fallback and invalid JSON %#', async (value) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(value))
    await expect(new StrategyApi().bootstrap(signal())).rejects.toThrow('could not be verified')
  })
  it('owns request timeout and cancellation', async () => {
    vi.useFakeTimers()
    vi.stubGlobal('fetch', vi.fn((_url, options) => new Promise((_resolve, reject) => options.signal.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError'))))))
    const result = new StrategyApi().bootstrap(signal())
    const assertion = expect(result).rejects.toThrow('did not respond in time')
    await vi.advanceTimersByTimeAsync(10000); await assertion
  })
  it('encodes server project identity and cursor as data, never as routing', async () => {
    const fetch = transport(); const api = new StrategyApi(); await api.bootstrap(signal())
    fetch.mockResolvedValueOnce(json(page([], 'project.a/b')))
    await api.graphs('project.a/b', 'a&b', signal())
    expect(fetch.mock.calls.at(-1)?.[0]).toBe('/api/v1/ir/projects/project.a%2Fb/graphs?limit=50&after=a%26b')
  })

  it('uses explicit REST verbs, bounded JSON bodies and in-memory CSRF on every session mutation', async () => {
    class ExposedApi extends StrategyApi {
      call(method: RestMethod, body?: Record<string, string>) {
        return this.request(method, 'test/resource', signal(), body)
      }
    }
    const fetch = transport(); const api = new ExposedApi()
    await api.bootstrap(signal()); await api.session(signal())
    for (const method of ['GET', 'POST', 'PATCH', 'PUT', 'DELETE'] as const) {
      fetch.mockResolvedValueOnce(json({ ok: true }))
      await api.call(method, method === 'GET' ? undefined : { value: method })
      const [, options] = fetch.mock.calls.at(-1)!
      if (!options) throw new Error('Expected REST request options')
      expect(options).toMatchObject({ method })
      if (method === 'GET') expect(options.headers).not.toHaveProperty('X-Strategy-CSRF')
      else expect(options.headers).toHaveProperty('X-Strategy-CSRF', session.csrf)
    }
    const calls = fetch.mock.calls.length
    await expect(api.call('POST', { value: 'x'.repeat(70_000) })).rejects.toMatchObject({ kind: 'input' })
    expect(fetch).toHaveBeenCalledTimes(calls)
  })

  it('retains only a closed typed error envelope and never trusts server text as the UI message', async () => {
    class ExposedApi extends StrategyApi {
      call() { return this.request('PATCH', 'test/resource', signal(), { value: 'safe' }) }
    }
    const fetch = transport(); const api = new ExposedApi()
    await api.bootstrap(signal()); await api.session(signal())
    fetch.mockResolvedValueOnce(json({ code: 'REVISION_CONFLICT', message: 'server diagnostic', detail: [{ loc: ['body', 'base_revision'], type: 'value_error', msg: 'Invalid value' }] }, 409))
    await expect(api.call()).rejects.toMatchObject({ kind: 'server', message: 'The server could not complete this request.', envelope: { code: 'REVISION_CONFLICT' } })
    fetch.mockResolvedValueOnce(json({ detail: { code: 'SEMANTIC_REVISION_CONFLICT', message: 'untrusted server diagnostic', path: '$.base_revision', current_revision: 4 } }, 409))
    await expect(api.call()).rejects.toMatchObject({ kind: 'server', message: 'The server could not complete this request.', envelope: { code: 'SEMANTIC_REVISION_CONFLICT' } })
    fetch.mockResolvedValueOnce(json({ code: 'REVISION_CONFLICT', message: '<untrusted>', extra: 'secret' }, 409))
    try { await api.call() } catch (error) {
      expect(error).toBeInstanceOf(ApiError)
      expect((error as ApiError).envelope).toBeNull()
      expect((error as ApiError).message).not.toContain('untrusted')
    }
  })

  it('rejects a delayed old-generation error envelope before it can invalidate newer access', async () => {
    class ExposedApi extends StrategyApi {
      call() { return this.request('GET', 'test/resource', signal()) }
    }
    const fetch = transport(); const api = new ExposedApi(); await api.bootstrap(signal())
    const body = deferred<string>()
    const response = json({ code: 'OLD_ACCESS', message: 'stale' }, 403)
    vi.spyOn(response, 'text').mockReturnValue(body.promise)
    fetch.mockResolvedValueOnce(response)
    const old = api.call(); const assertion = expect(old).rejects.toMatchObject({ name: 'AbortError' })
    await act(async () => {})
    await api.bootstrap(signal())
    body.resolve(JSON.stringify({ code: 'OLD_ACCESS', message: 'stale' })); await assertion
    await expect(api.projects(signal())).resolves.toEqual([project])
  })
})
