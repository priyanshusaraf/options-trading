import releaseManifest from '../test/releaseManifest.json'
import { useEffect, useState } from 'react'
import { parseManifest } from './contracts'
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { beforeAll, afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, StrategyApi } from './api'
import { CreateDraft } from '../features/presets/CreateDraft'
import { NewStrategy } from '../features/presets/NewStrategy'
import { PresetLibrary } from '../features/presets/PresetLibrary'
import { parsePresetCopy, parsePresets } from '../features/presets/presetContracts'
import { PrecisionFrame, PrecisionShell } from './PrecisionShell'
import { TraderSelect } from '../components/TraderSelect'
import { chooseSelect } from '../test/select'

afterEach(() => cleanup())

describe('PrecisionFrame', () => {
  it.each(['strategies', 'account'] as const)('shares navigation and shell landmarks for %s', (active) => {
    const navigate = vi.fn()
    render(<PrecisionFrame api={new StrategyApi()} active={active} onNavigate={navigate}>
      <h1>{active === 'account' ? 'Account' : 'Strategies'}</h1>
    </PrecisionFrame>)
    expect(screen.getByRole('link', { name: 'Skip to content' })).toHaveAttribute('href', '#main-content')
    expect(screen.getByRole('main')).toHaveAttribute('id', 'main-content')
    expect(screen.queryByRole('banner')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('link', { name: 'Skip to content' }))
    expect(screen.getByRole('main')).toHaveFocus()
    expect(window.location.hash).toBe('#main-content')
    for (const navigation of screen.getAllByRole('navigation')) {
      const selected = within(navigation).getByRole('button', {
        name: active === 'account' ? 'Account' : 'Strategies',
      })
      expect(selected).toHaveAttribute('aria-current', 'page')
    }
    fireEvent.click(within(screen.getAllByRole('navigation')[0]).getByRole('button', { name: 'Account' }))
    expect(navigate).toHaveBeenCalledWith('/account')
    expect(screen.queryByText(/Account and strategy records only|V0 · Research only/)).not.toBeInTheDocument()
    fireEvent.click(within(screen.getAllByRole('navigation')[0]).getByRole('button', { name: 'Home' }))
    expect(navigate).toHaveBeenCalledWith('/')
  })

  it('makes the desktop sidebar useful, collapsible, and limited to real V0 destinations', () => {
    const navigate = vi.fn()
    const api = new StrategyApi()
    const recheck = vi.spyOn(api, 'recheck').mockImplementation(() => undefined)
    const { container } = render(<PrecisionFrame api={api} active="provider" onNavigate={navigate}
      providerOnboarding context={{ project: 'Momentum lab', graph: 'Opening range' }}>
      <h1>Provider</h1>
    </PrecisionFrame>)
    const global = screen.getByRole('navigation', { name: 'Global navigation' })
    expect(within(global).getByRole('button', { name: 'Strategies' })).toBeInTheDocument()
    expect(within(global).getByRole('button', { name: 'Account' })).toBeInTheDocument()
    const provider = within(global).getByRole('button', { name: 'Data provider' })
    expect(provider.textContent).toBe('Data')
    expect(provider).toHaveAttribute('aria-current', 'page')
    fireEvent.click(provider)
    expect(navigate).toHaveBeenCalledWith('/account/provider')
    expect(within(screen.getByRole('complementary')).getByRole('region', { name: 'Current workspace' })).toHaveTextContent('Momentum lab')
    expect(screen.getByText('Opening range')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Refresh access and records' }))
    expect(recheck).toHaveBeenCalledOnce()
    const collapse = screen.getByRole('button', { name: 'Collapse navigation' })
    expect(collapse).toHaveAttribute('aria-expanded', 'true')
    expect(collapse.closest('.slate-brand')).toHaveTextContent('STRATEGY OS')
    expect(collapse).toHaveTextContent('')
    fireEvent.click(collapse)
    expect(container.firstChild).toHaveClass('slate-shell--collapsed')
    expect(screen.getByRole('button', { name: 'Expand navigation' })).toHaveAttribute('aria-expanded', 'false')
    for (const unavailable of ['Alerts', 'Paper', 'Admin', 'Deployments']) expect(screen.queryByRole('button', { name: unavailable })).not.toBeInTheDocument()
  })
})

beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', ''); this.querySelector<HTMLElement>('[autofocus]')?.focus() }
  HTMLDialogElement.prototype.close = function () { this.removeAttribute('open') }
})

const preset = { preset_id: 'trend_impulse_v3', name: 'Original V3', description: 'Original EMA slope and z-score rules',
  parameters: { length: 50 }, provenance: { semantic_version: 1, source: 'signals.py', source_sha256: 'a'.repeat(64), scope: undefined }, available: true }

function copied(identifier: string) { return { project_id: 'p', identifier, display_name: 'My strategy' } }

describe('desktop strategy creation', () => {
  it('offers a choice in a dialog, restores focus on Escape and opens the separate library', () => {
    const api = new StrategyApi(); const browse = vi.fn()
    render(<NewStrategy api={api} onCreated={vi.fn()} onPresets={browse} />)
    const trigger = screen.getByRole('button', { name: 'New strategy' }); trigger.focus(); fireEvent.click(trigger)
    expect(screen.getByRole('dialog')).toHaveAccessibleName('How would you like to start?')
    expect(screen.getByRole('button', { name: /Start fresh/ })).toBeInTheDocument()
    fireEvent(screen.getByRole('dialog'), new Event('cancel', { bubbles: false, cancelable: true }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument(); expect(trigger).toHaveFocus()
    fireEvent.click(trigger); fireEvent.click(screen.getByRole('button', { name: /Use a preset/ }))
    expect(browse).toHaveBeenCalledOnce(); expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('creates a private project only on confirmation and reuses it and the identifier after a failed draft request', async () => {
    const api = new StrategyApi()
    const project = vi.spyOn(api, 'createProject').mockResolvedValue({ project_id: 'p', name: 'My research', description: '', status: 'active' })
    const create = vi.spyOn(api, 'createV2Graph').mockRejectedValueOnce(new ApiError('network', 'offline'))
      .mockImplementationOnce(async (_project, identifier) => ({ graph_identifier: identifier }) as Awaited<ReturnType<StrategyApi['createV2Graph']>>)
    const onCreated = vi.fn()
    render(<NewStrategy api={api} onCreated={onCreated} onPresets={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: 'New strategy' })); fireEvent.click(screen.getByRole('button', { name: /Start fresh/ }))
    expect(project).not.toHaveBeenCalled(); expect(screen.queryByLabelText('Graph identifier')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Strategy name')).toHaveFocus()
    fireEvent.change(screen.getByLabelText('Strategy name'), { target: { value: 'My idea' } })
    fireEvent.change(screen.getByLabelText(/Description/), { target: { value: 'Trend research' } })
    fireEvent.click(screen.getByRole('button', { name: 'Create strategy' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/server could not be reached/)
    expect(screen.getByLabelText('Strategy name')).toHaveValue('My idea')
    fireEvent.click(screen.getByRole('button', { name: 'Create strategy' }))
    await vi.waitFor(() => expect(onCreated).toHaveBeenCalledOnce())
    expect(project).toHaveBeenCalledOnce(); expect(project).toHaveBeenCalledWith('My research', '', expect.any(AbortSignal))
    expect(create.mock.calls[0][1]).toMatch(/^[0-9a-f-]{36}$/)
    expect(create.mock.calls[1][1]).toBe(create.mock.calls[0][1])
    expect(onCreated).toHaveBeenCalledWith('p', create.mock.calls[0][1])
  })

  it('does not create a graph from a late project response after cancel', async () => {
    const api = new StrategyApi(); let resolve!: (value: Awaited<ReturnType<StrategyApi['createProject']>>) => void
    const project = vi.spyOn(api, 'createProject').mockImplementation(() => new Promise((done) => { resolve = done }))
    const create = vi.spyOn(api, 'createV2Graph'); const cancel = vi.fn()
    render(<CreateDraft api={api} onCreated={vi.fn()} onCancel={cancel} />)
    fireEvent.change(screen.getByLabelText('Strategy name'), { target: { value: 'Idea' } })
    fireEvent.click(screen.getByRole('button', { name: 'Create strategy' })); fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(project.mock.calls[0][2].aborted).toBe(true)
    await act(async () => resolve({ project_id: 'p', name: 'My research', description: '', status: 'active' }))
    expect(create).not.toHaveBeenCalled(); expect(cancel).toHaveBeenCalledOnce()
  })

  it('browses without a project and opens a named editable copy using the selected project', async () => {
    const api = new StrategyApi(); vi.spyOn(api, 'presets').mockResolvedValue([preset])
    const project = vi.spyOn(api, 'createProject'); const copy = vi.spyOn(api, 'copyPreset').mockImplementation(async (_p, _preset, id) => copied(id))
    const onCreated = vi.fn()
    render(<PresetLibrary api={api} projectId="p" onCreated={onCreated} />)
    await screen.findByRole('heading', { name: 'Original V3' })
    expect(project).not.toHaveBeenCalled(); expect(copy).not.toHaveBeenCalled()
    expect(screen.getByText('Included with your plan')).toBeInTheDocument()
    expect(screen.queryByText('Source details')).not.toBeInTheDocument()
    expect(screen.queryByText(preset.provenance.source_sha256)).not.toBeInTheDocument()
    expect(screen.getByText(/Choose a starting strategy, make it yours, and backtest it with your data/)).toBeInTheDocument()
    expect(screen.getByText('How it works').closest('details')).not.toHaveAttribute('open')
    fireEvent.click(screen.getByRole('button', { name: 'Use this preset' }))
    expect(screen.getByLabelText('Strategy name')).toHaveValue('Original V3')
    fireEvent.change(screen.getByLabelText('Strategy name'), { target: { value: 'My version' } })
    fireEvent.click(screen.getByRole('button', { name: 'Create strategy' }))
    await vi.waitFor(() => expect(onCreated).toHaveBeenCalledOnce())
    expect(copy).toHaveBeenCalledWith('p', preset.preset_id, expect.any(String), 'My version', expect.any(AbortSignal))
    expect(project).not.toHaveBeenCalled(); expect(onCreated).toHaveBeenCalledWith('p', copy.mock.calls[0][2])
  })

  it('separates complete strategy templates from unimplemented reusable component definitions', async () => {
    const api = new StrategyApi(); vi.spyOn(api, 'presets').mockResolvedValue([preset])
    const copy = vi.spyOn(api, 'copyPreset')
    render(<PresetLibrary api={api} projectId="p" onCreated={vi.fn()} />)
    await screen.findByRole('heading', { name: 'Original V3' })
    expect(screen.queryByText('End-to-end verification pending')).not.toBeInTheDocument()
    const sections = within(screen.getByRole('navigation', { name: 'Preset sections' }))
    fireEvent.click(sections.getByRole('button', { name: 'Strategy components' }))
    expect(screen.getByRole('heading', { name: 'Historical gap overlay' })).toBeVisible()
    expect(screen.getByRole('heading', { name: 'Bullish / bearish trend state' })).toBeVisible()
    expect(screen.getByText(/planned components will be added to an existing strategy as one expandable node/)).toBeVisible()
    expect(screen.getAllByText('Planned for a later release')).toHaveLength(3)
    expect(screen.queryByRole('button', { name: 'Use this preset' })).not.toBeInTheDocument()
    expect(copy).not.toHaveBeenCalled()
    fireEvent.click(sections.getByRole('button', { name: /^Strategies$/ }))
    expect(screen.getByRole('heading', { name: 'Original V3' })).toBeVisible()
  })

  it('copies once, preserves its reference on conflict and does not pretend the conflict is success', async () => {
    const api = new StrategyApi(); let reject!: (error: unknown) => void
    const copy = vi.spyOn(api, 'copyPreset').mockImplementationOnce(() => new Promise((_done, fail) => { reject = fail }))
      .mockRejectedValueOnce(new ApiError('server', 'hidden', { code: 'GRAPH_ALREADY_EXISTS', message: 'hidden' }))
    const onCreated = vi.fn()
    render(<CreateDraft api={api} projectId="p" preset={preset} onCreated={onCreated} onCancel={vi.fn()} />)
    const form = screen.getByLabelText('Strategy name').closest('form')!
    fireEvent.submit(form); fireEvent.submit(form); expect(copy).toHaveBeenCalledOnce()
    await act(async () => reject(new ApiError('server', 'hidden', { code: 'GRAPH_ALREADY_EXISTS', message: 'hidden' })))
    expect(await screen.findByRole('alert')).toHaveTextContent('Close this window and start again')
    expect(screen.getByLabelText('Strategy name')).toHaveValue('Original V3')
    fireEvent.submit(form); await screen.findByRole('alert')
    expect(copy.mock.calls[1][2]).toBe(copy.mock.calls[0][2]); expect(onCreated).not.toHaveBeenCalled()
  })

  it('suppresses stale copy completion and permits creation in the new project', async () => {
    const api = new StrategyApi(); let resolve!: (value: ReturnType<typeof copied>) => void
    const copy = vi.spyOn(api, 'copyPreset').mockImplementationOnce(() => new Promise((done) => { resolve = done }))
      .mockImplementationOnce(async (_p, _preset, id) => copied(id))
    const onCreated = vi.fn(); const props = { api, preset, onCreated, onCancel: vi.fn() }
    const view = render(<CreateDraft {...props} projectId="p" />)
    fireEvent.click(screen.getByRole('button', { name: 'Create strategy' }))
    view.rerender(<CreateDraft {...props} projectId="next" />)
    expect(copy.mock.calls[0][4].aborted).toBe(true)
    await act(async () => resolve(copied('old'))); expect(onCreated).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Create strategy' }))
    await vi.waitFor(() => expect(onCreated).toHaveBeenCalledOnce())
    expect(copy.mock.calls[1][0]).toBe('next')
  })

  it('supports library retry and empty results', async () => {
    const api = new StrategyApi(); vi.spyOn(api, 'presets').mockRejectedValueOnce(new ApiError('network', 'offline')).mockResolvedValueOnce([])
    render(<PresetLibrary api={api} onCreated={vi.fn()} />)
    expect(await screen.findByRole('alert')).toHaveTextContent(/server could not be reached/)
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByRole('heading', { name: 'No presets yet' })).toBeInTheDocument()
  })
})

describe('preset receipt boundaries', () => {
  const copy = { project_id: 'p', identifier: 'draft', display_name: 'Draft', revision: 0,
    current_version: null, graph: { format_version: 2, strategy_id: 'draft', strategy_version: 1 } }
  it.each([
    { project_id: 'other' }, { identifier: 'other' }, { revision: 1 }, { current_version: 1 },
    { authority: 'LIVE' }, { graph: { ...copy.graph, format_version: 1 } },
    { graph: { ...copy.graph, strategy_id: 'other' } }, { graph: { ...copy.graph, strategy_version: 2 } },
    { display_name: '' }, { graph: null },
  ])('rejects a copy that is not the requested unpublished draft', (change) => {
    expect(parsePresetCopy(copy, 'p', 'draft')).toEqual({ project_id: 'p', identifier: 'draft', display_name: 'Draft' })
    expect(() => parsePresetCopy({ ...copy, ...change }, 'p', 'draft')).toThrow()
  })
  it('validates source provenance and typed finite parameters', () => {
    const preset = { preset_id: 'v3', name: 'V3', description: 'Rules', parameters: { length: 50, enabled: true },
      provenance: { semantic_version: 1, source: 'signals.py', source_sha256: 'a'.repeat(64), scope: 'Daily check' }, available: true }
    expect(parsePresets({ presets: [preset] })[0].provenance.scope).toBe('Daily check')
    for (const change of [{ provenance: { ...preset.provenance, semantic_version: 0 } },
      { provenance: { ...preset.provenance, source_sha256: 'bad' } }, { parameters: { length: Infinity } }]) {
      expect(() => parsePresets({ presets: [{ ...preset, ...change }] })).toThrow()
    }
  })
})


vi.mock('../research/ResearchWorkspace', () => ({
  ResearchWorkspace: ({ backtestEnabled }: { backtestEnabled: boolean }) => <section aria-label="Research workspace"><button disabled={!backtestEnabled}>Backtest</button></section>,
}))

it.each(['ENABLED', 'ENABLED_WITH_LIMIT', 'BLOCKED'] as const)('shows names in Context and preserves %s backtest gating', async (state) => {
  const project = { project_id: 'project.private-id', name: 'My project', description: '', status: 'active' }
  const graph = { identifier: 'graph.private-id', display_name: 'My strategy', draft_revision: 2, current_version: null }
  const api = { projects: vi.fn(async () => [project]), graphs: vi.fn(async () => ({ items: [graph], next_cursor: null })), recheck: vi.fn() } as unknown as StrategyApi
  const manifest = structuredClone(releaseManifest)
  Object.assign(manifest.capabilities.backtesting, { state, reason: 'the current cockpit mixes research results with execution-watchlist controls' })
  render(<PrecisionShell api={api} manifest={parseManifest(manifest)} selection={{ projectId: project.project_id, graphId: graph.identifier }} onNavigate={vi.fn()} onGlobalNavigate={vi.fn()} />)
  await screen.findByRole('heading', { name: graph.display_name })
  expect(screen.queryByText(/Selected strategy|Saved graph identity and version facts|Backtesting limit:|cockpit mixes/)).not.toBeInTheDocument()
  expect(screen.queryByText(project.project_id)).not.toBeInTheDocument()
  expect(screen.queryByText(graph.identifier)).not.toBeInTheDocument()
  const backtest = screen.getByRole('button', { name: 'Backtest' })
  if (state === 'BLOCKED') {
    expect(backtest).toBeDisabled()
    expect(screen.getByText('Backtesting is unavailable in this version. You can continue building your strategy.')).toBeInTheDocument()
  } else {
    expect(backtest).toBeEnabled()
    expect(screen.queryByText(/Backtesting is unavailable/)).not.toBeInTheDocument()
  }
  fireEvent.click(screen.getByRole('button', { name: 'Context' }))
  const context = screen.getByRole('dialog', { name: 'Strategy context' })
  expect(within(context).queryByText(project.project_id)).not.toBeInTheDocument()
  expect(within(context).getByText(project.name)).toBeInTheDocument()
  expect(within(context).queryByText(graph.identifier)).not.toBeInTheDocument()
  expect(within(context).getByText(graph.display_name)).toBeInTheDocument()
  expect(within(context).getByText('Not saved yet')).toBeInTheDocument()
})

it('exposes Watchlists navigation only for the enabled static feature', () => {
  const navigate = vi.fn()
  render(<PrecisionFrame api={new StrategyApi()} active="watchlists" staticWatchlists onNavigate={navigate}><h1>Watchlists</h1></PrecisionFrame>)
  const button = within(screen.getByRole('navigation', { name: 'Global navigation' })).getByRole('button', { name: 'Watchlists' })
  expect(button).toHaveAttribute('aria-current', 'page')
  fireEvent.click(button)
  expect(navigate).toHaveBeenCalledWith('/watchlists')
})

it('shows the stored Alerts destination only when enabled and navigates to its real route', () => {
  const navigate = vi.fn()
  render(<PrecisionFrame api={new StrategyApi()} active="alerts" alerts onNavigate={navigate}><h1>Stored alerts</h1></PrecisionFrame>)
  const button = within(screen.getByRole('navigation', { name: 'Global navigation' })).getByRole('button', { name: 'Alerts' })
  expect(button).toHaveAttribute('aria-current', 'page')
  fireEvent.click(button); expect(navigate).toHaveBeenCalledWith('/alerts')
})

describe('trader select library integration', () => {
  const options = [{ value: '', label: 'Choose a period' }, { value: '20', label: '20 days' },
    { value: '50', label: '50 days' }, { value: '100', label: '100 days', disabled: true }]

  it('supports keyboard opening, selection and clearing with exact form values', async () => {
    const change = vi.fn()
    const { container } = render(<form><label htmlFor="period">Period</label><TraderSelect id="period" label="Period" name="period"
      defaultValue="20" options={options} onValueChange={change} /></form>)
    expect(screen.getByRole('combobox', { name: 'Period' })).toHaveTextContent('20 days')
    await chooseSelect('Period', '50')
    expect(change).toHaveBeenLastCalledWith('50')
    expect(new FormData(container.querySelector('form')!).get('period')).toBe('50')
    await chooseSelect('Period', '')
    expect(screen.getByRole('combobox', { name: 'Period' })).toHaveTextContent('Choose a period')
    expect(new FormData(container.querySelector('form')!).get('period')).toBe('')
  })

  it('returns focus on Escape and does not select disabled options', async () => {
    const change = vi.fn()
    render(<TraderSelect label="Period" value="20" options={options} onValueChange={change} />)
    const trigger = screen.getByRole('combobox', { name: 'Period' })
    fireEvent.keyDown(trigger, { key: 'ArrowDown' })
    const option = await screen.findByRole('option', { name: '100 days' })
    expect(option).toHaveAttribute('aria-disabled', 'true')
    fireEvent.click(option)
    expect(change).not.toHaveBeenCalled()
    fireEvent.keyDown(screen.getByRole('listbox'), { key: 'Escape' })
    await vi.waitFor(() => expect(trigger).toHaveFocus())
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  })

  it('preserves controlled updates and disabled field semantics', () => {
    const view = render(<TraderSelect label="Period" value="20" options={options} disabled invalid describedBy="period-error" />)
    const trigger = screen.getByRole('combobox', { name: 'Period' })
    expect(trigger).toBeDisabled()
    expect(trigger).toHaveAttribute('aria-invalid', 'true')
    expect(trigger).toHaveAttribute('aria-describedby', 'period-error')
    view.rerender(<TraderSelect label="Period" value="50" options={options} />)
    expect(screen.getByRole('combobox', { name: 'Period' })).toHaveTextContent('50 days')
    expect(screen.getByRole('combobox', { name: 'Period' })).not.toHaveAttribute('aria-invalid')
  })
})

it('keeps asynchronously restored selection without emitting an empty change', async () => {
  const changed = vi.fn()
  function HistoryField() {
    const [value, setValue] = useState(''), [loaded, setLoaded] = useState(false)
    useEffect(() => { void Promise.resolve().then(() => { setLoaded(true); setValue('saved') }) }, [])
    return <form><TraderSelect label="History" value={value} disabled={!loaded}
      options={[{ value: '', label: 'Choose history' }, ...(loaded ? [{ value: 'saved', label: 'Saved history' }] : [])]}
      onValueChange={(next) => { changed(next); setValue(next) }} /></form>
  }
  render(<HistoryField />)
  await vi.waitFor(() => expect(screen.getByRole('combobox', { name: 'History' })).toHaveTextContent('Saved history'))
  expect(changed).not.toHaveBeenCalled()
  await chooseSelect('History', '')
  expect(changed).toHaveBeenCalledWith('')
  expect(screen.getByRole('combobox', { name: 'History' })).toHaveTextContent('Choose history')
})
