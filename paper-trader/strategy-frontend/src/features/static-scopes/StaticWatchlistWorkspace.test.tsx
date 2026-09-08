import { useLayoutEffect } from 'react'
import { DataConnectionRequestError, type DataConnectionClient, type ProviderInstrumentSearchResult, providerReferenceLabel, type ProviderInstrumentReference, type SavedProviderSelection } from '../connections/dataConnectionClient'
import { chooseSelect } from '../../test/select'
import { createHash, webcrypto } from 'node:crypto'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { ApiError, type StrategyApi } from '../../shell/api'
import { ContractError, type ProviderHistoryReceipt, type ResearchDataset } from '../../shell/contracts'
import { StaticWatchlistWorkspace } from './StaticWatchlistWorkspace'
import { WatchlistMonitorTable, verifyWatchlistMonitorSnapshot, matchesWatchlistFilter } from './WatchlistMonitorTable'
import type { WatchlistMonitorClient, WatchlistMonitorContext, WatchlistMonitorRow } from './watchlistMonitorTypes'
import { ProviderHistoryForm, providerHistoryDates, formatIndiaTimestamp, historyCount, historyDatasetLabel } from './ProviderHistoryForm'
import { instrumentCandidates, watchlistCandidates, watchlistMemberCandidates, scopeLabels, parseScopeMemberContext, parseStaticScope, scopeWriteOutcome, verifyScopeMember, scopeMemberIdentity, type ScopeMember, type TypedScopeMemberLabel, type StaticScope } from './staticScopeContracts'

const project = { project_id: 'project.a', name: 'Research', description: '', status: 'active' }
const graph = { identifier: 'strategy.a', display_name: 'Momentum', draft_revision: 1, current_version: 1 }
const address = (digit: string) => `sha256:${digit.repeat(64)}`
const hash = (value: Record<string, unknown>) => `sha256:${createHash('sha256').update(JSON.stringify(Object.fromEntries(Object.entries(value).sort(([a], [b]) => a < b ? -1 : 1)))).digest('hex')}`
const first: ResearchDataset = { manifest_address: address('a'), instrument_address: address('1'), canonical_instrument_label: 'RELIANCE · XNSE · EQUITY SPOT · 111111111111', instrument_display_name: 'RELIANCE · XNSE · EQUITY SPOT',
  asset_class: 'EQUITY', contract_kind: 'SPOT', interval: '1d', event_start: '2025-01-01T00:00:00Z', event_end: '2025-12-31T00:00:00Z', availability_end: '2026-01-01T00:00:00Z', as_of: '2026-01-02T00:00:00Z', bar_count: 248,
  fields: ['OPEN', 'HIGH', 'LOW', 'CLOSE'], provider_evidence_state: 'USER_CSV_SHAPE_VALIDATED', market_truth_state: 'RECONSTRUCTED_WITH_GAPS', source_type: 'USER_SUPPLIED', historical_source_availability: 'NOT_SUPPLIED', calendar_coverage: 'NOT_ASSERTED', rights_scope: 'PERSONAL_RESEARCH_ONLY', research_compatibility: 'PRIMARY_BACKTEST', gaps: [], backtest_eligibility: 'ELIGIBLE_Q03', refusal_code: null }
const second: ResearchDataset = { ...first, manifest_address: address('b'), instrument_address: address('2'), canonical_instrument_label: 'TCS · XNSE · EQUITY SPOT · 222222222222', instrument_display_name: null }
function scopeValue(id = 'scope.main', version = 1, name = 'Growth', members = [first.instrument_address], predecessor: string | null = null, status: 'active' | 'archived' = 'active'): Extract<StaticScope, { snapshot: { schema: 'static-instrument-scope/1' } }> {
  const snapshot = { schema: 'static-instrument-scope/1' as const, owner_id: 'owner.a', project_id: project.project_id, scope_id: id, revision: version, predecessor, members: [...members].sort() }
  return { scope_id: id, name, status, current_revision: version, address: hash(snapshot), membership_address: hash({ schema: 'static-instrument-membership/1', members: snapshot.members }), snapshot, member_labels: snapshot.members.map((instrument_address) => ({ instrument_address, display_name: null })) }
}
const initial = scopeValue()
function apiFor(scopes: StaticScope[] = [initial]) {
  return { projects: vi.fn().mockResolvedValue([project]), staticScopes: vi.fn().mockResolvedValue({ items: scopes, next_cursor: null }),
    researchDatasets: vi.fn().mockResolvedValue([first, second]), graphs: vi.fn().mockResolvedValue({ items: [graph], next_cursor: null }),
    staticScope: vi.fn().mockResolvedValue(initial), createStaticScope: vi.fn(), reviseStaticScope: vi.fn(), archiveStaticScope: vi.fn(), importProviderHistory: vi.fn() }
}
function show(api = apiFor(), extra: Partial<Parameters<typeof StaticWatchlistWorkspace>[0]> = {}) {
  const onBacktest = vi.fn()
  render(<StaticWatchlistWorkspace api={api as unknown as StrategyApi} enabled backtestEnabled projectId={project.project_id} onProject={vi.fn()} onBacktest={onBacktest} {...extra} />)
  return { api, onBacktest }
}
function openScopeSettings() {
  const summary = screen.getByText('Watchlist history and settings', { selector: 'summary' })
  if (!(summary.parentElement as HTMLDetailsElement).open) fireEvent.click(summary)
}
async function openInitial() {
  fireEvent.click(await screen.findByRole('button', { name: 'Open Growth' }))
  await waitFor(() => expect(screen.queryByText('Loading saved revision…')).not.toBeInTheDocument())
  await screen.findByRole('heading', { name: 'Growth' })
  openScopeSettings()
}
async function newDraft(name = 'New list') {
  fireEvent.click(await screen.findByRole('button', { name: 'New watchlist' }))
  expect(screen.getByRole('heading', { name: 'New watchlist' })).toHaveFocus()
  fireEvent.change(screen.getByLabelText('Watchlist name'), { target: { value: name } })
  fireEvent.click(screen.getByRole('checkbox', { name: first.instrument_display_name! }))
}
beforeEach(() => { vi.stubGlobal('crypto', webcrypto); vi.spyOn(webcrypto, 'randomUUID').mockReturnValueOnce('11111111-1111-4111-8111-111111111111').mockReturnValue('22222222-2222-4222-8222-222222222222') })
afterEach(() => { cleanup(); vi.useRealTimers(); vi.restoreAllMocks(); vi.unstubAllGlobals() })

it('shows the real capability refusal without reading records when blocked', () => {
  const { api } = show(apiFor(), { enabled: false })
  expect(screen.getByRole('status')).toHaveTextContent('Static watchlists are not available in this server release.')
  expect(api.projects).not.toHaveBeenCalled()
  expect(screen.queryByRole('button', { name: 'New watchlist' })).not.toBeInTheDocument()
})
it('creates one list from owned human-labelled instruments and verifies its saved revision', async () => {
  const api = apiFor([]), id = 'scope.11111111111141118111111111111111'
  const saved = scopeValue(id, 1, 'New list')
  api.createStaticScope.mockResolvedValue(saved); api.staticScope.mockResolvedValue(saved)
  show(api); await newDraft()
  fireEvent.click(screen.getByRole('button', { name: 'Save watchlist' }))
  expect(await screen.findByText('Saved revision 1.')).toBeInTheDocument()
  expect(await screen.findByRole('heading', { name: 'New list' })).toHaveFocus()
  expect(api.createStaticScope.mock.calls[0].slice(0, 3)).toEqual([project.project_id, id, { name: 'New list', members: [first.instrument_address] }])
  expect(api.staticScope.mock.calls[0].slice(0, 3)).toEqual([project.project_id, id, 1])
  expect(document.body.textContent).not.toMatch(/sha256:|111111111111|222222222222/)
})
it('keeps a retained create reference and frozen draft through unknown-write recovery', async () => {
  const api = apiFor([]), saved = scopeValue('scope.11111111111141118111111111111111', 1, 'New list')
  api.createStaticScope.mockRejectedValueOnce(new ApiError('network', 'Lost response')).mockResolvedValue(saved)
  api.staticScope.mockRejectedValueOnce(new ApiError('server', 'Absent', { code: 'STATIC_SCOPE_NOT_FOUND', message: 'Watchlist or project not found.' })).mockResolvedValue(saved)
  show(api); await newDraft(); fireEvent.click(screen.getByRole('button', { name: 'Save watchlist' }))
  await screen.findByRole('alert')
  expect(screen.getByLabelText('Watchlist name')).toHaveValue('New list')
  expect(screen.getByLabelText('Watchlist name')).toBeDisabled()
  expect(screen.queryByRole('button', { name: 'Retry same save' })).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Check saved state' }))
  fireEvent.click(await screen.findByRole('button', { name: 'Retry same save' }))
  await screen.findByText('Saved revision 1.')
  expect(api.createStaticScope).toHaveBeenCalledTimes(2)
  expect(api.createStaticScope.mock.calls[1].slice(0, 3)).toEqual(api.createStaticScope.mock.calls[0].slice(0, 3))
})
it('recovers an already recorded create after failed readback without repeating the POST', async () => {
  const api = apiFor([]), saved = scopeValue('scope.11111111111141118111111111111111', 1, 'New list')
  api.createStaticScope.mockResolvedValue(saved)
  api.staticScope.mockRejectedValueOnce(new ApiError('network', 'Readback lost')).mockResolvedValue(saved)
  show(api); await newDraft(); fireEvent.click(screen.getByRole('button', { name: 'Save watchlist' }))
  await screen.findByRole('alert'); fireEvent.click(screen.getByRole('button', { name: 'Check saved state' }))
  await screen.findByText('Confirmed revision 1.')
  expect(api.createStaticScope).toHaveBeenCalledOnce()
  expect(api.staticScope.mock.calls.map((call) => call[2])).toEqual([1, null, 1])
})
it('retains editable values after a definite validation refusal', async () => {
  const api = apiFor([])
  api.createStaticScope.mockRejectedValue(new ApiError('server', 'Invalid', { code: 'STATIC_SCOPE_INVALID', message: 'Invalid members' }))
  show(api); await newDraft(); fireEvent.click(screen.getByRole('button', { name: 'Save watchlist' }))
  await screen.findByText(/Check the name and choose 1–32/)
  expect(screen.getByLabelText('Watchlist name')).toHaveValue('New list')
  expect(screen.getByLabelText('Watchlist name')).toBeEnabled()
  expect(screen.getByRole('checkbox', { name: first.instrument_display_name! })).toBeChecked()
})
it('appends with CAS, reads back the exact revision and keeps historical revisions read only', async () => {
  const api = apiFor(), revised = scopeValue(initial.scope_id, 2, 'Revised', [second.instrument_address], initial.address)
  api.reviseStaticScope.mockResolvedValue(revised)
  api.staticScope.mockResolvedValueOnce(initial).mockResolvedValueOnce(revised).mockResolvedValue({ ...initial, name: revised.name, current_revision: 2 })
  show(api); await openInitial(); fireEvent.click(screen.getByRole('button', { name: 'Edit current list' }))
  fireEvent.change(screen.getByLabelText('Watchlist name'), { target: { value: 'Revised' } })
  fireEvent.click(screen.getByRole('checkbox', { name: 'TCS · XNSE · EQUITY SPOT' }))
  fireEvent.click(screen.getByRole('checkbox', { name: first.instrument_display_name! }))
  fireEvent.click(screen.getByRole('button', { name: 'Save watchlist' }))
  await screen.findByText('Saved revision 2.')
  expect(api.reviseStaticScope.mock.calls[0].slice(0, 4)).toEqual([project.project_id, initial.scope_id, 1, { name: 'Revised', members: [second.instrument_address] }])
  await screen.findByLabelText('Saved revision')
  openScopeSettings()
  fireEvent.change(screen.getByLabelText('Saved revision'), { target: { value: '1' } })
  fireEvent.click(screen.getByRole('button', { name: 'Open revision' }))
  await waitFor(() => expect(screen.getByRole('button', { name: 'Edit current list' })).toBeDisabled())
  expect(api.staticScope.mock.calls.at(-1)?.[2]).toBe(1)
  expect(screen.getByRole('button', { name: 'Archive watchlist' })).toBeDisabled()
})
it('requires state readback before retrying an uncertain revision and preserves the same CAS', async () => {
  const api = apiFor(), revised = scopeValue(initial.scope_id, 2, 'Revised', [first.instrument_address], initial.address)
  api.reviseStaticScope.mockRejectedValueOnce(new ApiError('network', 'Lost response')).mockResolvedValue(revised)
  api.staticScope.mockResolvedValueOnce(initial).mockResolvedValueOnce(initial).mockResolvedValue(revised)
  show(api); await openInitial(); fireEvent.click(screen.getByRole('button', { name: 'Edit current list' }))
  fireEvent.change(screen.getByLabelText('Watchlist name'), { target: { value: 'Revised' } }); fireEvent.click(screen.getByRole('button', { name: 'Save watchlist' }))
  await screen.findByRole('alert'); fireEvent.click(screen.getByRole('button', { name: 'Check saved state' }))
  fireEvent.click(await screen.findByRole('button', { name: 'Retry same save' }))
  await screen.findByText('Saved revision 2.')
  expect(api.reviseStaticScope.mock.calls[1].slice(0, 4)).toEqual(api.reviseStaticScope.mock.calls[0].slice(0, 4))
})
it('preserves a conflicted draft until the user explicitly loads the newer list', async () => {
  const api = apiFor(), other = scopeValue(initial.scope_id, 2, 'Changed elsewhere', [second.instrument_address], initial.address)
  api.reviseStaticScope.mockRejectedValue(new ApiError('server', 'Conflict', { code: 'STATIC_SCOPE_CONFLICT', message: 'Expected revision conflict' }))
  api.staticScope.mockResolvedValueOnce(initial).mockResolvedValue(other)
  show(api); await openInitial(); fireEvent.click(screen.getByRole('button', { name: 'Edit current list' }))
  fireEvent.change(screen.getByLabelText('Watchlist name'), { target: { value: 'My draft' } }); fireEvent.click(screen.getByRole('button', { name: 'Save watchlist' }))
  await screen.findByRole('alert'); fireEvent.click(screen.getByRole('button', { name: 'Check saved state' }))
  await screen.findByText(/The watchlist changed elsewhere/)
  expect(screen.getByLabelText('Watchlist name')).toHaveValue('My draft')
  expect(screen.getByLabelText('Watchlist name')).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: 'Load current list' }))
  expect(await screen.findByRole('heading', { name: 'Changed elsewhere' })).toBeInTheDocument()
  expect(api.reviseStaticScope).toHaveBeenCalledOnce()
})
it('archives with the selected current revision and verifies persisted status', async () => {
  const api = apiFor(), archived = { ...initial, status: 'archived' as const }
  api.archiveStaticScope.mockResolvedValue(archived)
  api.staticScope.mockResolvedValueOnce(initial).mockResolvedValue(archived)
  show(api); await openInitial(); fireEvent.click(screen.getByRole('button', { name: 'Archive watchlist' }))
  await screen.findByText('Watchlist archived.')
  expect(api.archiveStaticScope.mock.calls[0].slice(0, 3)).toEqual([project.project_id, initial.scope_id, 1])
  expect(api.staticScope.mock.calls.at(-1)?.[2]).toBe(1)
  fireEvent.click(await screen.findByRole('checkbox', { name: 'Show archived' }))
  await waitFor(() => expect(api.staticScopes.mock.calls.at(-1)?.[2]).toBe(true))
})
it('opens only an explicit member, dataset and saved strategy with immutable context metadata', async () => {
  const { onBacktest } = show()
  await openInitial(); fireEvent.click(screen.getByRole('button', { name: first.instrument_display_name! }))
  await chooseSelect('Historical dataset', first.manifest_address)
  await chooseSelect('Saved strategy', graph.identifier)
  fireEvent.click(screen.getByRole('button', { name: 'Open Backtest' }))
  expect(onBacktest).toHaveBeenCalledWith({ schema: 'static-scope-member-context/1', project_id: project.project_id, graph_id: graph.identifier, graph_version: 1,
    scope_id: initial.scope_id, revision: 1, address: initial.address, membership_address: initial.membership_address, instrument_address: first.instrument_address, dataset_manifest_address: first.manifest_address })
  expect(screen.getByText(/does not run the whole watchlist or start monitoring/)).toBeInTheDocument()
})
it('keeps nameless or ambiguous instruments unavailable instead of using raw addresses', async () => {
  const api = apiFor([])
  api.researchDatasets.mockResolvedValue([first, { ...first, instrument_address: address('3'), manifest_address: address('c') }, { ...second, source_type: 'PROVIDER_AUTHORITY' }])
  show(api); fireEvent.click(await screen.findByRole('button', { name: 'New watchlist' }))
  expect(screen.getAllByRole('checkbox', { name: 'Instrument name unavailable' })).toHaveLength(3)
  for (const checkbox of screen.getAllByRole('checkbox', { name: 'Instrument name unavailable' })) expect(checkbox).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Save watchlist' })).toBeDisabled()
  expect(document.body.textContent).not.toMatch(/sha256:|111111111111|222222222222/)
})
it('verifies membership identity and rejects tampered revision bytes', async () => {
  expect(await parseStaticScope(initial, project.project_id, initial.scope_id)).toEqual(initial)
  await expect(parseStaticScope({ ...initial, snapshot: { ...initial.snapshot, members: [second.instrument_address] } }, project.project_id)).rejects.toThrow()
  await expect(parseStaticScope({ ...initial, membership_address: address('f') }, project.project_id)).rejects.toThrow()
  const context = { schema: 'static-scope-member-context/1', project_id: project.project_id, graph_id: graph.identifier, graph_version: 1,
    scope_id: initial.scope_id, revision: 1, address: initial.address, membership_address: initial.membership_address, instrument_address: first.instrument_address, dataset_manifest_address: first.manifest_address }
  const selected = parseScopeMemberContext(context, project.project_id, graph.identifier)
  expect(verifyScopeMember(selected, initial, [first], 1)).toBe(first)
  expect(() => parseScopeMemberContext(context, 'other-project', graph.identifier)).toThrow()
  expect(() => verifyScopeMember({ ...selected, instrument_address: second.instrument_address }, initial, [first], 1)).toThrow()
  expect(() => verifyScopeMember(selected, initial, [{ ...first, instrument_address: second.instrument_address }], 1)).toThrow()
  expect(() => verifyScopeMember(selected, initial, [first], 2)).toThrow()
  expect(() => verifyScopeMember({ ...selected, address: address('f') }, initial, [first], 1)).toThrow()
  expect(() => verifyScopeMember({ ...selected, membership_address: address('f') }, initial, [first], 1)).toThrow()
})
it('does not treat a newer, different or foreign revision as a successful write', () => {
  const intent = { kind: 'revise' as const, scopeId: initial.scope_id, base: initial, draft: { name: 'Revised', members: [first.instrument_address] } }
  const next = scopeValue(initial.scope_id, 2, 'Revised', [first.instrument_address], initial.address)
  expect(scopeWriteOutcome(intent, next)).toBe('saved')
  expect(scopeWriteOutcome(intent, initial)).toBe('retry')
  expect(scopeWriteOutcome(intent, { ...next, name: 'Different' })).toBe('conflict')
  expect(scopeWriteOutcome(intent, scopeValue(initial.scope_id, 2, 'Revised', [second.instrument_address], initial.address))).toBe('conflict')
  expect(scopeWriteOutcome(intent, scopeValue(initial.scope_id, 2, 'Revised', [first.instrument_address], address('f')))).toBe('conflict')
  expect(scopeWriteOutcome(intent, { ...next, current_revision: 3, snapshot: { ...next.snapshot, revision: 3 } })).toBe('conflict')
  expect(() => scopeWriteOutcome(intent, { ...next, snapshot: { ...next.snapshot, owner_id: 'foreign' } })).toThrow()
  expect(instrumentCandidates([second])[0].label).toBe('TCS · XNSE · EQUITY SPOT')
})

it('keeps archived-project watchlists readable while disabling writes', async () => {
  const api = apiFor()
  api.projects.mockResolvedValue([{ ...project, status: 'archived' }])
  show(api)
  expect(await screen.findByText('This project is archived. Watchlists are read only.')).toBeInTheDocument()
  expect(await screen.findByRole('button', { name: 'New watchlist' })).toBeDisabled()
  await openInitial()
  expect(screen.getByRole('button', { name: 'Edit current list' })).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Archive watchlist' })).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Open revision' })).toBeEnabled()
})

it('hides the previous project immediately across client and project switches', async () => {
  const api = apiFor(), other = apiFor([]), onBacktest = vi.fn(), onProject = vi.fn()
  const props = { api: api as unknown as StrategyApi, enabled: true, backtestEnabled: true, projectId: project.project_id, onProject, onBacktest }
  const view = render(<StaticWatchlistWorkspace {...props} />)
  await openInitial()
  let finish!: (value: typeof project[]) => void
  other.projects.mockImplementation(() => {
    expect(screen.queryByLabelText('Project')).not.toBeInTheDocument()
    return new Promise((resolve) => { finish = resolve })
  })
  view.rerender(<StaticWatchlistWorkspace {...props} api={other as unknown as StrategyApi} />)
  expect(screen.queryByText('Growth')).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Open Growth' })).not.toBeInTheDocument()
  await waitFor(() => expect(other.projects).toHaveBeenCalledOnce())
  await act(async () => finish([{ ...project, project_id: 'project.other', name: 'Other project' }]))
  await screen.findByText('This project is unavailable in your workspace.')
  expect(other.staticScopes).not.toHaveBeenCalled()
  view.rerender(<StaticWatchlistWorkspace {...props} api={other as unknown as StrategyApi} projectId="project.other" />)
  await screen.findByText('No watchlists here yet.')
  expect(screen.queryByRole('heading', { name: 'Growth' })).not.toBeInTheDocument()
})

it('ignores a late watchlist page from the previous project', async () => {
  const api = apiFor(), nextProject = { ...project, project_id: 'project.other', name: 'Other project' }
  api.projects.mockResolvedValue([project, nextProject])
  let finish!: (value: { items: StaticScope[]; next_cursor: null }) => void
  api.staticScopes.mockImplementationOnce(() => new Promise((resolve) => { finish = resolve })).mockResolvedValue({ items: [], next_cursor: null })
  const props = { api: api as unknown as StrategyApi, enabled: true, backtestEnabled: true, projectId: project.project_id, onProject: vi.fn(), onBacktest: vi.fn() }
  const view = render(<StaticWatchlistWorkspace {...props} />)
  await waitFor(() => expect(api.staticScopes).toHaveBeenCalledOnce())
  await chooseSelect('Project', nextProject.project_id)
  expect(props.onProject).toHaveBeenCalledWith(nextProject.project_id)
  view.rerender(<StaticWatchlistWorkspace {...props} projectId={nextProject.project_id} />)
  await screen.findByText('No watchlists here yet.')
  await act(async () => finish({ items: [initial], next_cursor: null }))
  expect(screen.queryByRole('button', { name: 'Open Growth' })).not.toBeInTheDocument()
  expect(screen.getByRole('combobox', { name: 'Project' })).toHaveTextContent(nextProject.name)
})

it('limits a draft to 32 owned instruments without silently dropping selections', async () => {
  const api = apiFor([])
  const histories = Array.from({ length: 33 }, (_, index) => ({ ...first, instrument_address: `sha256:${index.toString(16).padStart(64, '0')}`,
    manifest_address: `sha256:${(index + 100).toString(16).padStart(64, '0')}`, instrument_display_name: `Stock ${index + 1} · XNSE · EQUITY SPOT` }))
  api.researchDatasets.mockResolvedValue(histories)
  show(api); fireEvent.click(await screen.findByRole('button', { name: 'New watchlist' }))
  fireEvent.change(screen.getByLabelText('Watchlist name'), { target: { value: 'My research list' } })
  const checkboxes = screen.getAllByRole('checkbox', { name: /^Stock / })
  for (const checkbox of checkboxes.slice(0, 32)) fireEvent.click(checkbox)
  expect(checkboxes[32]).toBeDisabled()
  expect(screen.getByText(/32 selected/)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Save watchlist' })).toBeEnabled()
})

it('uses the actual current revision for later edits', async () => {
  const head = scopeValue(initial.scope_id, 2, 'Growth', [first.instrument_address], initial.address)
  const saved = scopeValue(initial.scope_id, 3, 'Third revision', [first.instrument_address], head.address)
  const api = apiFor([head]); api.staticScope.mockResolvedValueOnce(head).mockResolvedValue(saved); api.reviseStaticScope.mockResolvedValue(saved)
  show(api); await openInitial(); fireEvent.click(screen.getByRole('button', { name: 'Edit current list' }))
  fireEvent.change(screen.getByLabelText('Watchlist name'), { target: { value: 'Third revision' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save watchlist' }))
  await screen.findByText('Saved revision 3.')
  expect(api.reviseStaticScope.mock.calls[0][2]).toBe(2)
  expect(api.staticScope.mock.calls.at(-1)?.[2]).toBe(3)
})

it('never commits previous-project details before the next project request starts', async () => {
  const api = apiFor(), nextProject = { ...project, project_id: 'project.next', name: 'Next project' }
  api.projects.mockResolvedValue([project, nextProject])
  api.staticScopes.mockImplementation(async (projectId) => {
    if (projectId === project.project_id) return { items: [initial], next_cursor: null }
    expect(screen.queryByRole('heading', { name: 'Growth' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Open Growth' })).not.toBeInTheDocument()
    return { items: [], next_cursor: null }
  })
  const props = { api: api as unknown as StrategyApi, enabled: true, backtestEnabled: true, projectId: project.project_id, onProject: vi.fn(), onBacktest: vi.fn() }
  const view = render(<StaticWatchlistWorkspace {...props} />)
  await openInitial()
  view.rerender(<StaticWatchlistWorkspace {...props} projectId={nextProject.project_id} />)
  await screen.findByText('No watchlists here yet.')
})


const canonicalLabel = { instrument_address: address('8'), display_name: 'Known canonical root' }
const smallcap: ProviderInstrumentReference = { token: 77, symbol: 'SMALLCAP', name: 'छोटी कंपनी', exchange: 'NSE', segment: 'NSE', instrument_type: 'EQ',
  expiry: null, strike: '0', lot_size: '1', tick_size: '0.05' }
function stableHash(value: unknown): string {
  const json = JSON.stringify(value, (_key, item) => item && typeof item === 'object' && !Array.isArray(item)
    ? Object.fromEntries(Object.entries(item).sort(([a], [b]) => a < b ? -1 : 1)) : item)
  return `sha256:${createHash('sha256').update(json).digest('hex')}`
}
function providerSelection(reference = smallcap): SavedProviderSelection {
  const selection = { schema: 'owner-provider-instrument-selection/1' as const, owner_id: 'owner.a', data_account_id: 'data.a', connection_id: 7,
    provider: 'ZERODHA' as const, reference, observed_at: '2026-09-06T06:00:00.123456+00:00' }
  return { schema: 'strategy-os-provider-selection/1', selection_address: stableHash(selection), selection, research_resolution: 'UNRESOLVED' }
}
function providerSearchResult(reference = smallcap): ProviderInstrumentSearchResult {
  return { schema: 'strategy-os-provider-instrument-search/2', provider: 'ZERODHA', reference_type: 'CURRENT_PROVIDER_REFERENCE',
    query: reference.symbol, exchange: 'ALL', available_exchanges: ['NSE', 'MCX', 'NFO', 'NEW_EX'], has_more: false, items: [reference] }
}
function providerClient(reference = smallcap) {
  return { searchInstruments: vi.fn().mockResolvedValue(providerSearchResult(reference)), selectInstrument: vi.fn().mockResolvedValue(providerSelection(reference)),
    resolveInstrument: vi.fn() } as unknown as DataConnectionClient
}
function scopeV2(id: string, version: number, name: string, input: readonly ScopeMember[], predecessor: string | null = null, reference = smallcap): StaticScope {
  const members = [...input].sort((a, b) => scopeMemberIdentity(a) < scopeMemberIdentity(b) ? -1 : 1)
  const snapshot = { schema: 'static-instrument-scope/2' as const, owner_id: 'owner.a', project_id: project.project_id, scope_id: id, revision: version, predecessor, members }
  const member_labels: TypedScopeMemberLabel[] = members.map((member) => member.kind === 'CANONICAL'
    ? { member, display_name: first.instrument_display_name ?? null, provider_reference: null, observed_at: null }
    : { member, display_name: providerReferenceLabel(reference), provider_reference: reference, observed_at: providerSelection(reference).selection.observed_at })
  return { scope_id: id, name, status: 'active', current_revision: version, address: stableHash(snapshot),
    membership_address: stableHash({ schema: 'static-instrument-membership/2', members }), snapshot, member_labels }
}
const providerPointer = (reference = smallcap): ScopeMember => ({ kind: 'PROVIDER_REFERENCE', selection_address: providerSelection(reference).selection_address })
const addName = (reference = smallcap) => `Add ${providerReferenceLabel(reference)}`
async function providerDraft(reference = smallcap) {
  fireEvent.click(await screen.findByRole('button', { name: 'New watchlist' }))
  fireEvent.change(screen.getByLabelText('Watchlist name'), { target: { value: 'Any list' } })
  fireEvent.change(screen.getByRole('searchbox', { name: 'Provider symbol or name' }), { target: { value: reference.symbol } })
  fireEvent.click(screen.getByRole('button', { name: 'Search provider' }))
  await screen.findByRole('button', { name: addName(reference) })
}
it.each([
  smallcap,
  { ...smallcap, token: 88, symbol: 'SYNTH_FUT', exchange: 'MCX', segment: 'MCX-FUT', instrument_type: 'FUT', expiry: '2026-12-30', lot_size: '100' },
  { ...smallcap, token: 99, symbol: 'SYNTH_CE', exchange: 'NFO', segment: 'NFO-OPT', instrument_type: 'CE', expiry: '2026-09-24', strike: '100.25' },
  { ...smallcap, token: 100, symbol: '<UNKNOWN>', exchange: 'NEW_EX', segment: 'CUSTOM', instrument_type: 'PROVIDER_NEW', strike: null },
])('saves and reloads any provider instrument without datasets or canonical resolution: $symbol', async (reference) => {
  const api = apiFor([]), client = providerClient(reference), pointer = providerPointer(reference)
  api.researchDatasets.mockResolvedValue([])
  const saved = scopeV2('scope.11111111111141118111111111111111', 1, 'Any list', [pointer], null, reference)
  api.createStaticScope.mockResolvedValue(saved); api.staticScope.mockResolvedValue(saved)
  show(api, { providerClient: client }); await providerDraft(reference)
  expect(screen.getByText(/You can save any instrument from your provider/)).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: addName(reference) }))
  expect(await screen.findByRole('checkbox', { name: new RegExp(reference.symbol.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')) })).toBeChecked()
  expect(client.selectInstrument).toHaveBeenCalledWith(reference, expect.any(AbortSignal))
  expect(client.resolveInstrument).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Save watchlist' }))
  await screen.findByText('Saved revision 1.')
  expect(api.createStaticScope.mock.calls[0][2]).toEqual({ name: 'Any list', members: [pointer] })
  expect(api.createStaticScope.mock.calls[0][2].members[0]).not.toHaveProperty('instrument_address')
  cleanup(); api.staticScopes.mockResolvedValue({ items: [saved], next_cursor: null })
  show(api)
  fireEvent.click(await screen.findByRole('button', { name: 'Open Any list' }))
  fireEvent.click(await screen.findByRole('button', { name: providerReferenceLabel(reference) }))
  expect(screen.getByRole('button', { name: 'Open Backtest' })).toBeDisabled()
  expect(screen.getByText('Saved instrument · Not ready for research')).toBeInTheDocument()
  expect(screen.getByText(/Saved snapshot observed 6 September 2026(?:,| at) 11:30:00 IST/)).toBeInTheDocument()
  expect(screen.getByText(/This instrument is saved. Backtests need verified instrument details/)).toBeInTheDocument()
})
it('upgrades a v1 draft to typed mixed membership and never silently downgrades a v2 revision', async () => {
  const api = apiFor(), client = providerClient(), pointer = providerPointer()
  const canonical: ScopeMember = { kind: 'CANONICAL', instrument_address: first.instrument_address }
  const mixed = scopeV2(initial.scope_id, 2, initial.name, [canonical, pointer], initial.address)
  api.staticScope.mockResolvedValueOnce(initial).mockResolvedValue(mixed); api.reviseStaticScope.mockResolvedValue(mixed)
  show(api, { providerClient: client }); await openInitial(); fireEvent.click(screen.getByRole('button', { name: 'Edit current list' }))
  fireEvent.change(screen.getByRole('searchbox'), { target: { value: smallcap.symbol } }); fireEvent.click(screen.getByRole('button', { name: 'Search provider' }))
  fireEvent.click(await screen.findByRole('button', { name: addName() })); await screen.findByRole('checkbox', { name: /SMALLCAP/ })
  fireEvent.click(screen.getByRole('button', { name: 'Save watchlist' })); await screen.findByText('Saved revision 2.')
  expect(api.reviseStaticScope.mock.calls[0][3]).toEqual({ name: initial.name, members: [canonical, pointer] })
  fireEvent.click(screen.getByRole('button', { name: 'Edit current list' })); fireEvent.click(screen.getByRole('checkbox', { name: /SMALLCAP/ }))
  const next = scopeV2(initial.scope_id, 3, initial.name, [canonical], mixed.address)
  api.reviseStaticScope.mockResolvedValue(next); api.staticScope.mockResolvedValue(next)
  fireEvent.click(screen.getByRole('button', { name: 'Save watchlist' })); await screen.findByText('Saved revision 3.')
  expect(api.reviseStaticScope.mock.calls[1][3]).toEqual({ name: initial.name, members: [canonical] })
})
it('keeps the latest draft name during selection and avoids duplicate pointers', async () => {
  const api = apiFor([]), client = providerClient()
  let finish!: (value: SavedProviderSelection) => void
  vi.mocked(client.selectInstrument).mockImplementationOnce(() => new Promise((resolve) => { finish = resolve }))
  show(api, { providerClient: client }); await providerDraft(); fireEvent.click(screen.getByRole('button', { name: addName() }))
  fireEvent.change(screen.getByLabelText('Watchlist name'), { target: { value: 'Updated name' } })
  await act(async () => finish(providerSelection()))
  expect(screen.getByLabelText('Watchlist name')).toHaveValue('Updated name')
  fireEvent.click(screen.getByRole('button', { name: addName() })); await waitFor(() => expect(client.selectInstrument).toHaveBeenCalledTimes(2))
  expect(screen.getAllByRole('checkbox', { name: /SMALLCAP/ })).toHaveLength(1)
  expect(screen.getByText(/1 selected/)).toBeInTheDocument()
})
it.each([
  [409, 'INSTRUMENT_SELECTION_UNAVAILABLE', /instrument details changed or are unavailable/],
  [409, 'DATA_REAUTH_REQUIRED', /Reconnect your data provider/],
  [409, 'DATA_CONNECTION_UNAVAILABLE', /Your data connection is unavailable/],
  [401, null, /Sign in again/], [422, 'INVALID_PROVIDER_REFERENCE', /instrument details are incomplete/], [422, 'INVALID_INSTRUMENT_SEARCH', /Enter 2–64/], [503, null, /provider response could not be verified/],
] as const)('retains the draft after provider selection refusal %s %s', async (status, code, message) => {
  const api = apiFor([]), client = providerClient()
  vi.mocked(client.selectInstrument).mockRejectedValueOnce(new DataConnectionRequestError(status, code)).mockResolvedValue(providerSelection())
  show(api, { providerClient: client }); await providerDraft(); fireEvent.click(screen.getByRole('button', { name: addName() }))
  expect(await screen.findByRole('alert')).toHaveTextContent(message)
  expect(screen.getByLabelText('Watchlist name')).toHaveValue('Any list')
  expect(screen.getByRole('searchbox')).toHaveValue(smallcap.symbol)
  expect(screen.queryByRole('checkbox', { name: /SMALLCAP/ })).not.toBeInTheDocument()
  expect(api.createStaticScope).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: addName() }))
  expect(await screen.findByRole('checkbox', { name: /SMALLCAP/ })).toBeChecked()
})
it('keeps a typed draft and the same intent through uncertain save recovery', async () => {
  const api = apiFor([]), client = providerClient(), saved = scopeV2('scope.11111111111141118111111111111111', 1, 'Any list', [providerPointer()])
  api.createStaticScope.mockRejectedValueOnce(new ApiError('network', 'Lost')).mockResolvedValue(saved)
  api.staticScope.mockRejectedValueOnce(new ApiError('server', 'Absent', { code: 'STATIC_SCOPE_NOT_FOUND', message: 'Absent' })).mockResolvedValue(saved)
  show(api, { providerClient: client }); await providerDraft(); fireEvent.click(screen.getByRole('button', { name: addName() }))
  await screen.findByRole('checkbox', { name: /SMALLCAP/ }); fireEvent.click(screen.getByRole('button', { name: 'Save watchlist' })); await screen.findByRole('alert')
  expect(screen.getByRole('checkbox', { name: /SMALLCAP/ })).toBeChecked()
  fireEvent.click(screen.getByRole('button', { name: 'Check saved state' })); fireEvent.click(await screen.findByRole('button', { name: 'Retry same save' }))
  await screen.findByText('Saved revision 1.')
  expect(api.createStaticScope.mock.calls[1][2]).toEqual(api.createStaticScope.mock.calls[0][2])
})
it('discards a late selection after a query edit', async () => {
  const api = apiFor([]), client = providerClient(); let finish!: (value: SavedProviderSelection) => void
  vi.mocked(client.selectInstrument).mockImplementation(() => new Promise((resolve) => { finish = resolve }))
  show(api, { providerClient: client }); await providerDraft(); fireEvent.click(screen.getByRole('button', { name: addName() }))
  const signal = vi.mocked(client.selectInstrument).mock.calls[0][1]
  fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'other' } }); expect(signal.aborted).toBe(true)
  await act(async () => finish(providerSelection()))
  expect(screen.queryByRole('checkbox', { name: /SMALLCAP/ })).not.toBeInTheDocument()
})
it('hides prior client input/results during render and ignores its late selection', async () => {
  const api = apiFor([]), client = providerClient(), other = providerClient(); let finish!: (value: SavedProviderSelection) => void
  vi.mocked(client.selectInstrument).mockImplementation(() => new Promise((resolve) => { finish = resolve }))
  const props = { api: api as unknown as StrategyApi, enabled: true, backtestEnabled: true, projectId: project.project_id, onProject: vi.fn(), onBacktest: vi.fn() }
  function Probe({ subject }: { subject: DataConnectionClient }) {
    useLayoutEffect(() => { if (subject === other) {
      expect(screen.queryByRole('button', { name: addName() })).not.toBeInTheDocument()
      expect(screen.getByRole('searchbox')).toHaveValue('')
    } }, [subject])
    return <StaticWatchlistWorkspace {...props} providerClient={subject} />
  }
  const view = render(<Probe subject={client} />); await providerDraft(); fireEvent.click(screen.getByRole('button', { name: addName() }))
  view.rerender(<Probe subject={other} />); await act(async () => finish(providerSelection()))
  expect(screen.queryByRole('checkbox', { name: /SMALLCAP/ })).not.toBeInTheDocument()
  expect(screen.getByLabelText('Watchlist name')).toHaveValue('Any list')
})
it('ignores provider selection from the previous project', async () => {
  const api = apiFor([]), client = providerClient(), next = { ...project, project_id: 'project.next' }; let finish!: (value: SavedProviderSelection) => void
  api.projects.mockResolvedValue([project, next]); vi.mocked(client.selectInstrument).mockImplementation(() => new Promise((resolve) => { finish = resolve }))
  const props = { api: api as unknown as StrategyApi, enabled: true, backtestEnabled: true, onProject: vi.fn(), onBacktest: vi.fn(), providerClient: client }
  const view = render(<StaticWatchlistWorkspace {...props} projectId={project.project_id} />); await providerDraft(); fireEvent.click(screen.getByRole('button', { name: addName() }))
  view.rerender(<StaticWatchlistWorkspace {...props} projectId={next.project_id} />); await screen.findByText('No watchlists here yet.')
  await act(async () => finish(providerSelection())); fireEvent.click(screen.getByRole('button', { name: 'New watchlist' }))
  expect(screen.queryByRole('checkbox', { name: /SMALLCAP/ })).not.toBeInTheDocument()
})
it('retains dynamic exchanges and handles empty/error searches without submitting the watchlist on Enter', async () => {
  const api = apiFor([]), client = providerClient()
  vi.mocked(client.searchInstruments).mockResolvedValueOnce({ ...providerSearchResult(), items: [] }).mockRejectedValueOnce(new Error('offline'))
  show(api, { providerClient: client }); fireEvent.click(await screen.findByRole('button', { name: 'New watchlist' }))
  const query = screen.getByRole('searchbox'); fireEvent.change(query, { target: { value: 'empty' } }); fireEvent.keyDown(query, { key: 'Enter' })
  await screen.findByText('No instruments matched. Try another symbol or name.')
  fireEvent.change(screen.getByRole('combobox', { name: 'Provider exchange' }), { target: { value: 'MCX' } })
  expect(screen.getByRole('option', { name: 'NFO' })).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Search provider' })); await screen.findByRole('alert')
  expect(client.searchInstruments).toHaveBeenLastCalledWith('empty', 'MCX', expect.any(AbortSignal))
  expect(api.createStaticScope).not.toHaveBeenCalled()
})
it('verifies typed hashes and refuses provider hashes as canonical research members', async () => {
  const saved = scopeV2('scope.mixed', 1, 'Mixed', [{ kind: 'CANONICAL', instrument_address: first.instrument_address }, providerPointer()])
  expect(await parseStaticScope(saved, project.project_id)).toEqual(saved)
  const badDataset = { ...first, instrument_address: providerSelection().selection_address }
  const context = { schema: 'static-scope-member-context/1' as const, project_id: project.project_id, graph_id: graph.identifier, graph_version: 1,
    scope_id: saved.scope_id, revision: 1, address: saved.address, membership_address: saved.membership_address,
    instrument_address: badDataset.instrument_address, dataset_manifest_address: badDataset.manifest_address }
  expect(() => verifyScopeMember(context, saved, [badDataset], 1)).toThrow()
  expect(verifyScopeMember({ ...context, instrument_address: first.instrument_address }, saved, [first], 1)).toEqual(first)
})
it.each(['missing_metadata', 'wrong_member', 'canonical_metadata', 'legacy_hash', 'untyped_member'] as const)('rejects a malformed v2 scope: %s', async (change) => {
  const saved = scopeV2('scope.mixed', 1, 'Mixed', [{ kind: 'CANONICAL', instrument_address: first.instrument_address }, providerPointer()])
  const value = JSON.parse(JSON.stringify(saved))
  if (change === 'missing_metadata') value.member_labels[1].provider_reference = null
  if (change === 'wrong_member') value.member_labels[1].member = { kind: 'PROVIDER_REFERENCE', selection_address: address('f') }
  if (change === 'canonical_metadata') value.member_labels[0].observed_at = providerSelection().selection.observed_at
  if (change === 'legacy_hash') value.membership_address = stableHash({ schema: 'static-instrument-membership/1', members: saved.snapshot.members })
  if (change === 'untyped_member') { value.snapshot.members = [first.instrument_address]; value.address = stableHash(value.snapshot) }
  await expect(parseStaticScope(value, project.project_id)).rejects.toThrow()
})
it('keeps dataset ambiguity closed while adding registry-only labels', () => {
  const labels = [{ instrument_address: first.instrument_address, display_name: 'Registry fallback' },
    { instrument_address: canonicalLabel.instrument_address, display_name: canonicalLabel.display_name }]
  const conflict = { ...first, manifest_address: address('9'), instrument_display_name: 'Conflicting name' }
  const items = watchlistCandidates([first, conflict], labels)
  expect(items.find((item) => item.address === first.instrument_address)?.label).toBeNull()
  expect(items.find((item) => item.address === canonicalLabel.instrument_address)).toEqual({ address: canonicalLabel.instrument_address, label: canonicalLabel.display_name, datasets: [] })
  expect(watchlistCandidates([first], [{ instrument_address: canonicalLabel.instrument_address, display_name: first.instrument_display_name ?? null }]).every((item) => item.label === null)).toBe(true)
})
it.each([
  [], [{ instrument_address: address('2'), display_name: 'Foreign member' }],
  [{ instrument_address: first.instrument_address, display_name: '' }],
  [{ instrument_address: first.instrument_address, display_name: 'x'.repeat(257) }],
  [{ instrument_address: first.instrument_address, display_name: 'Invalid\nname' }],
  [{ instrument_address: first.instrument_address, display_name: 'Name', token: 256265 }],
].map((member_labels) => ({ member_labels })))('rejects malformed or misattributed member labels $member_labels', async ({ member_labels }) => {
  await expect(parseStaticScope({ ...initial, member_labels }, project.project_id)).rejects.toThrow()
})
it('accepts nullable labels and verifies that display-only changes preserve snapshot identity', async () => {
  const named = await parseStaticScope({ ...initial, member_labels: [{ instrument_address: first.instrument_address, display_name: 'New display name' }] }, project.project_id)
  expect(named.address).toBe(initial.address)
  expect(named.membership_address).toBe(initial.membership_address)
  expect(named.snapshot).toEqual(initial.snapshot)
  expect((await parseStaticScope(initial, project.project_id)).member_labels[0].display_name).toBeNull()
})

function historyReceipt(): ProviderHistoryReceipt {
  return { schema: 'strategy-os-provider-history-import/1', reused: false, project_id: project.project_id, selection_address: providerSelection().selection_address,
    requested_start: '2024-12-31T18:30:00Z', requested_end: '2025-12-31T18:29:59Z',
    returned_start: '2025-01-01T18:30:00Z', returned_end: '2025-12-30T18:30:00Z', request_count: 2, empty_request_count: 1,
    request_window_days: 1900, application_bar_limit: 2000, provider_retention: 'UNKNOWN', item: { ...first,
      provider_selection_address: providerSelection().selection_address, source_type: 'PROVIDER_AUTHORITY',
      provider_evidence_state: 'VERIFIED_REFERENCES_PRESENT', rights_scope: 'PROVIDER_CONTRACT' } }
}
function setHistoryDates() {
  fireEvent.change(screen.getByLabelText('Start date'), { target: { value: '2025-01-01' } })
  fireEvent.change(screen.getByLabelText('End date'), { target: { value: '2025-12-31' } })
}
it.each([
  ['2026-09-06T18:29:59Z', '2026-09-05'], ['2026-09-06T18:30:00Z', '2026-09-06'],
  ['2026-01-01T00:00:00Z', '2025-12-31'], ['2024-03-01T00:00:00Z', '2024-02-29'],
])('defaults history to yesterday in India across the date boundary %s', (now, end) => {
  expect(providerHistoryDates(new Date(now)).end).toBe(end)
})
it('fetches history for the exact saved provider selection and opens its canonical dataset without rewriting membership', async () => {
  const saved = scopeV2('scope.history', 1, 'History', [providerPointer()]), api = apiFor([saved]), receipt = historyReceipt()
  api.staticScope.mockResolvedValue(saved); api.researchDatasets.mockResolvedValueOnce([]).mockResolvedValue([receipt.item])
  api.importProviderHistory.mockResolvedValue(receipt)
  const { onBacktest } = show(api)
  fireEvent.click(await screen.findByRole('button', { name: 'Open History' }))
  fireEvent.click(await screen.findByRole('button', { name: providerReferenceLabel(smallcap) }))
  setHistoryDates(); fireEvent.click(screen.getByRole('button', { name: 'Fetch daily history' }))
  expect(await screen.findByText('Saved 248 daily bars.')).toBeInTheDocument()
  expect(api.importProviderHistory.mock.calls[0].slice(0, 2)).toEqual([project.project_id, {
    selection_address: providerSelection().selection_address, start_date: '2025-01-01', end_date: '2025-12-31', interval: 'day' }])
  expect(api.researchDatasets).toHaveBeenCalledTimes(2)
  expect(screen.getByLabelText('Start date')).toHaveValue('2025-01-01')
  expect(screen.getByText('1 Jan 2025 → 31 Dec 2025')).toBeInTheDocument()
  expect(screen.getByText('2 Jan 2025 → 31 Dec 2025')).toBeInTheDocument()
  expect(screen.getByText('2 provider requests; 1 returned no bars.')).toBeInTheDocument()
  expect(screen.getByText(/Missing trading sessions have not been verified/)).toBeInTheDocument()
  expect(screen.getByText(/windows of up to 1,900 days.*2,000 bars.*retention is unknown/)).toBeInTheDocument()
  await chooseSelect('Saved strategy', graph.identifier)
  fireEvent.click(screen.getByRole('button', { name: 'Open Backtest' }))
  const context = onBacktest.mock.calls[0][0]
  expect(context.instrument_address).toBe(receipt.item.instrument_address)
  expect(context.dataset_manifest_address).toBe(receipt.item.manifest_address)
  expect(verifyScopeMember(context, saved, [receipt.item], 1)).toEqual(receipt.item)
  expect(api.reviseStaticScope).not.toHaveBeenCalled()
  expect(saved.snapshot.members).toEqual([providerPointer()])
})
it('retains dates and the saved watchlist after an unavailable root or grant refusal', async () => {
  const api = apiFor(), onSaved = vi.fn()
  api.importProviderHistory.mockRejectedValue(new ApiError('server', 'refused', {
    code: 'HISTORICAL_FETCH_ROOT_UNAVAILABLE', message: 'This saved instrument has no supported research definition yet.' }))
  render(<ProviderHistoryForm api={api as unknown as StrategyApi} projectId={project.project_id} selectionAddress={providerSelection().selection_address} disabled={false} onSaved={onSaved} />)
  setHistoryDates(); fireEvent.click(screen.getByRole('button', { name: 'Fetch daily history' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('This saved instrument has no supported research definition yet. Your dates are retained.')
  expect(screen.getByLabelText('Start date')).toHaveValue('2025-01-01'); expect(screen.getByLabelText('End date')).toHaveValue('2025-12-31')
  expect(onSaved).not.toHaveBeenCalled(); expect(api.researchDatasets).not.toHaveBeenCalled()
  expect(screen.queryByRole('button', { name: 'Refresh saved history' })).not.toBeInTheDocument()
  expect(screen.queryByText(/request may still finish/)).not.toBeInTheDocument()
})
it('retries only the dataset list after a successful import with an unconfirmed refresh', async () => {
  const api = apiFor(), receipt = historyReceipt(), onSaved = vi.fn()
  api.importProviderHistory.mockResolvedValue(receipt)
  api.researchDatasets.mockResolvedValueOnce([{ ...receipt.item, provider_selection_address: address('f') }]).mockResolvedValue([receipt.item])
  render(<ProviderHistoryForm api={api as unknown as StrategyApi} projectId={project.project_id} selectionAddress={receipt.selection_address} disabled={false} onSaved={onSaved} />)
  setHistoryDates(); fireEvent.click(screen.getByRole('button', { name: 'Fetch daily history' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('History was saved, but the dataset list could not be refreshed.')
  expect(onSaved).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Refresh saved history' }))
  await waitFor(() => expect(onSaved).toHaveBeenCalledWith(receipt, [receipt.item]))
  expect(api.importProviderHistory).toHaveBeenCalledTimes(1)
  expect(screen.queryByRole('button', { name: 'Refresh saved history' })).not.toBeInTheDocument()
})
it.each(['api', 'project', 'selection', 'unmount'] as const)('aborts history work and ignores its late success after %s changes', async (change) => {
  const api = apiFor(), receipt = historyReceipt(), onSaved = vi.fn()
  let finish!: (value: ProviderHistoryReceipt) => void
  api.importProviderHistory.mockImplementation(() => new Promise((resolve) => { finish = resolve }))
  const props = { api: api as unknown as StrategyApi, projectId: project.project_id, selectionAddress: receipt.selection_address, disabled: false, onSaved }
  const view = render(<ProviderHistoryForm {...props} />)
  setHistoryDates(); fireEvent.click(screen.getByRole('button', { name: 'Fetch daily history' }))
  const signal = api.importProviderHistory.mock.calls[0][2] as AbortSignal
  if (change === 'unmount') view.unmount()
  else view.rerender(<ProviderHistoryForm {...props} api={change === 'api' ? apiFor() as unknown as StrategyApi : props.api}
    projectId={change === 'project' ? 'project.other' : props.projectId} selectionAddress={change === 'selection' ? address('f') : props.selectionAddress} />)
  expect(signal.aborted).toBe(true)
  await act(async () => finish(receipt))
  expect(api.researchDatasets).not.toHaveBeenCalled(); expect(onSaved).not.toHaveBeenCalled()
  expect(screen.queryByText('Saved 248 daily bars.')).not.toBeInTheDocument()
})
it('matches datasets by exact saved selection while retaining revision, graph and root checks', () => {
  const saved = scopeV2('scope.history', 1, 'History', [providerPointer()]), item = historyReceipt().item
  const candidates = watchlistMemberCandidates([item, { ...item, manifest_address: address('b'), provider_selection_address: address('f') }], scopeLabels(saved))
  expect(candidates.find((candidate) => candidate.member.kind === 'PROVIDER_REFERENCE')?.datasets).toEqual([item])
  const context = parseScopeMemberContext({ schema: 'static-scope-member-context/1', project_id: project.project_id,
    graph_id: graph.identifier, graph_version: 1, scope_id: saved.scope_id, revision: 1, address: saved.address,
    membership_address: saved.membership_address, instrument_address: item.instrument_address, dataset_manifest_address: item.manifest_address }, project.project_id, graph.identifier)
  expect(verifyScopeMember(context, saved, [item], 1)).toBe(item)
  for (const changes of [{ provider_selection_address: null }, { provider_selection_address: address('f') }, { instrument_address: address('f') }]) {
    expect(() => verifyScopeMember(context, saved, [{ ...item, ...changes }], 1)).toThrow()
  }
  for (const changes of [{ revision: 2 }, { project_id: 'project.other' }, { membership_address: address('f') }, { address: address('f') }, { scope_id: 'scope.other' }]) {
    expect(() => verifyScopeMember({ ...context, ...changes }, saved, [item], 1)).toThrow()
  }
  expect(() => verifyScopeMember(context, saved, [item], 2)).toThrow()
})

it('offers a read-only history refresh after a lost POST response without assuming publication failed', async () => {
  const api = apiFor(), receipt = historyReceipt(), onSaved = vi.fn()
  api.importProviderHistory.mockRejectedValue(new ApiError('timeout', 'timed out'))
  api.researchDatasets.mockResolvedValue([receipt.item])
  render(<ProviderHistoryForm api={api as unknown as StrategyApi} projectId={project.project_id} selectionAddress={receipt.selection_address} disabled={false} onSaved={onSaved} />)
  setHistoryDates(); fireEvent.click(screen.getByRole('button', { name: 'Fetch daily history' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('The request may still finish')
  fireEvent.click(screen.getByRole('button', { name: 'Refresh saved history' }))
  await waitFor(() => expect(onSaved).toHaveBeenCalledWith(undefined, [receipt.item]))
  expect(api.importProviderHistory).toHaveBeenCalledTimes(1)
  expect(screen.queryByText('Saved 248 daily bars.')).not.toBeInTheDocument()
  expect(screen.getByRole('status')).toHaveTextContent('the previous request may still be finishing')
  expect(screen.getByRole('button', { name: 'Refresh saved history' })).toBeEnabled()
})

it.each(['access', 'input', 'manifest'] as const)('shows a definite %s refusal without suggesting that history was saved', async (kind) => {
  const api = apiFor()
  api.importProviderHistory.mockRejectedValue(new ApiError(kind, 'refused'))
  render(<ProviderHistoryForm api={api as unknown as StrategyApi} projectId={project.project_id} selectionAddress={providerSelection().selection_address} disabled={false} onSaved={vi.fn()} />)
  setHistoryDates(); fireEvent.click(screen.getByRole('button', { name: 'Fetch daily history' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Your dates are retained.')
  expect(screen.getByLabelText('End date')).toHaveValue('2025-12-31')
  expect(screen.queryByRole('button', { name: 'Refresh saved history' })).not.toBeInTheDocument()
  expect(screen.queryByText(/request may still finish/)).not.toBeInTheDocument()
})
it.each(['network', 'server', 'unverified receipt'] as const)('offers a read-only check after an uncertain %s result', async (kind) => {
  const api = apiFor()
  api.importProviderHistory.mockRejectedValue(kind === 'unverified receipt' ? new ContractError() : new ApiError(kind, 'unknown outcome'))
  render(<ProviderHistoryForm api={api as unknown as StrategyApi} projectId={project.project_id} selectionAddress={providerSelection().selection_address} disabled={false} onSaved={vi.fn()} />)
  setHistoryDates(); fireEvent.click(screen.getByRole('button', { name: 'Fetch daily history' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('The request may still finish.')
  expect(screen.getByRole('button', { name: 'Refresh saved history' })).toBeEnabled()
  expect(api.importProviderHistory).toHaveBeenCalledTimes(1)
})

it('labels a reused publication and its original capture without claiming another provider fetch', async () => {
  const api = apiFor(), receipt = { ...historyReceipt(), reused: true }, onSaved = vi.fn()
  api.importProviderHistory.mockResolvedValue(receipt); api.researchDatasets.mockResolvedValue([receipt.item])
  render(<ProviderHistoryForm api={api as unknown as StrategyApi} projectId={project.project_id} selectionAddress={receipt.selection_address} disabled={false} onSaved={onSaved} />)
  setHistoryDates(); fireEvent.click(screen.getByRole('button', { name: 'Fetch daily history' }))
  expect(await screen.findByText('Reused saved history: 248 daily bars.')).toBeInTheDocument()
  expect(screen.queryByText('Saved 248 daily bars.')).not.toBeInTheDocument()
  expect(screen.getByText('Original capture: 2 provider requests; 1 returned no bars.')).toBeInTheDocument()
  expect(onSaved).toHaveBeenCalledWith(receipt, [receipt.item])
  expect(screen.getByLabelText('Start date')).toHaveValue('2025-01-01')
})

it.each([
  ['2026-09-06T06:00:00.123456+00:00', /^6 September 2026(?:,| at) 11:30:00 IST$/],
  ['2024-06-06T18:29:59.999999Z', /^6 June 2024(?:,| at) 23:59:59 IST$/],
  ['2024-06-06T18:30:00Z', /^7 June 2024(?:,| at) 00:00:00 IST$/],
] as const)('formats a saved observation in India time without raw ISO fractions: %s', (value, expected) => {
  expect(formatIndiaTimestamp(value)).toMatch(expected)
})
it.each([
  ['day', '2024-06-05T18:30:00Z', '2024-06-06T18:30:00Z', '6 Jun 2024 → 6 Jun 2024'],
  ['1d', '2024-02-28T18:30:00Z', '2024-02-29T18:30:00Z', '29 Feb 2024 → 29 Feb 2024'],
  ['day', '2024-12-30T18:30:00Z', '2024-12-31T18:30:00Z', '31 Dec 2024 → 31 Dec 2024'],
])('shows the inclusive daily end for %s without changing dataset clocks', (interval, event_start, event_end, period) => {
  const dataset = Object.freeze({ ...first, interval, event_start, event_end, bar_count: 1 })
  expect(historyDatasetLabel(dataset)).toBe(`Daily · 1 bar · ${period}`)
  expect(dataset.event_start).toBe(event_start)
  expect(dataset.event_end).toBe(event_end)
  expect(dataset.manifest_address).toBe(first.manifest_address)
})
it('preserves the exclusive intraday end across India midnight', () => {
  expect(historyDatasetLabel({ ...first, interval: '15minute', bar_count: 2,
    event_start: '2024-06-06T18:15:00Z', event_end: '2024-06-06T18:30:00Z' })).toMatch(
    /^15minute · 2 bars · 6 June 2024(?:,| at) 23:45:00 IST → 7 June 2024(?:,| at) 00:00:00 IST \(end exclusive\)$/)
})
it.each([[0, 'dataset', '0 datasets'], [1, 'dataset', '1 dataset'], [2, 'dataset', '2 datasets'],
  [1, 'instrument', '1 instrument'], [2, 'instrument', '2 instruments'], [1000, 'bar', '1,000 bars']])(
  'uses count-aware watchlist labels for %s %s', (count, unit, expected) => {
    expect(historyCount(Number(count), String(unit))).toBe(expected)
  })
it.each([1, 2])('shows correct instrument and dataset counts in the watchlist for %s', async (count) => {
  const members = count === 1 ? [first.instrument_address] : [first.instrument_address, second.instrument_address]
  const saved = scopeValue('scope.counts', 1, 'Counts', members), api = apiFor([saved])
  const dataset = { ...first, interval: 'day', event_start: '2024-06-05T18:30:00Z', event_end: '2024-06-06T18:30:00Z', bar_count: 1 }
  api.staticScope.mockResolvedValue(saved)
  api.researchDatasets.mockResolvedValue(count === 1 ? [dataset] : [dataset, { ...dataset, manifest_address: address('c') }, second])
  show(api)
  expect(await screen.findByText(`${count} ${count === 1 ? 'instrument' : 'instruments'} · Revision 1`)).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Open Counts' }))
  fireEvent.click(await screen.findByRole('button', { name: first.instrument_display_name! }))
  expect(screen.getByText(`${count} ${count === 1 ? 'dataset' : 'datasets'}`)).toBeInTheDocument()
  fireEvent.keyDown(screen.getByRole('combobox', { name: 'Historical dataset' }), { key: 'ArrowDown' })
  expect((await screen.findAllByRole('option', { name: 'Daily · 1 bar · 6 Jun 2024 → 6 Jun 2024' }))).toHaveLength(count)
  expect(document.body.textContent).not.toContain('2024-06-06T18:30:00Z')
})
it('uses singular bar and request labels in a one-bar saved receipt', async () => {
  const api = apiFor(), receipt = { ...historyReceipt(), request_count: 1, empty_request_count: 0, item: { ...historyReceipt().item, bar_count: 1 } }
  api.importProviderHistory.mockResolvedValue(receipt); api.researchDatasets.mockResolvedValue([receipt.item])
  render(<ProviderHistoryForm api={api as unknown as StrategyApi} projectId={project.project_id} selectionAddress={receipt.selection_address} disabled={false} onSaved={vi.fn()} />)
  setHistoryDates(); fireEvent.click(screen.getByRole('button', { name: 'Fetch daily history' }))
  expect(await screen.findByText('Saved 1 daily bar.')).toBeInTheDocument()
  expect(screen.getByText('1 provider request; 0 returned no bars.')).toBeInTheDocument()
})

function monitorContext(scope = initial): WatchlistMonitorContext {
  return { projectId: scope.snapshot.project_id, scopeId: scope.scope_id, scopeRevision: scope.snapshot.revision,
    scopeAddress: scope.address, membershipAddress: scope.membership_address }
}
function monitoringRow(kind: WatchlistMonitorRow['result']['kind'] = 'NOT_EVALUATED'): WatchlistMonitorRow {
  const evaluated = ['HOLD', 'SIGNAL', 'STALE'].includes(kind), assignmentId = evaluated ? 'monitor.a' : null
  return { memberKey: scopeMemberIdentity({ kind: 'CANONICAL', instrument_address: first.instrument_address }), configurationRevision: 1,
    pinned: false, graph: { graphId: graph.identifier, graphVersion: 1, graphVersionAddress: address('4'), label: graph.display_name },
    timeframe: '15minute', supportedTimeframes: [{ value: '15minute', label: '15 min' }, { value: '30minute', label: '30 min' }],
    assignmentId, monitoring: 'OFF', canConfigure: true, canPin: true, canSetMonitoring: true, reason: null,
    result: { kind, label: { NOT_EVALUATED: 'Not evaluated', HOLD: 'HOLD', SIGNAL: 'Buy signal', WARMUP: 'Warming up', STALE: 'Stale result', ERROR: 'Provider error' }[kind],
      evaluatedAt: evaluated ? '2026-09-07T04:30:00Z' : null, assignmentId, graphVersionAddress: evaluated ? address('4') : null,
      reason: kind === 'ERROR' ? 'Reconnect your data account.' : null, warmup: kind === 'WARMUP' ? { available: 3, required: 20 } : null } }
}
function monitorClient(row = monitoringRow()) {
  return { list: vi.fn().mockResolvedValue({ context: monitorContext(), rows: [row] }), configure: vi.fn(), pin: vi.fn(), setMonitoring: vi.fn() }
}
function monitorProps(client: WatchlistMonitorClient | null = monitorClient()) {
  return { api: apiFor() as unknown as StrategyApi, client, context: monitorContext(),
    members: watchlistMemberCandidates([first], scopeLabels(initial)), graphs: [graph], locked: false,
    canRemove: false, onDetails: vi.fn(), onRemove: vi.fn() }
}
it('makes instrument results the primary view and keeps history tools secondary without inventing monitoring', async () => {
  show()
  const table = await screen.findByRole('table', { name: 'Saved instruments' })
  expect(table).toHaveTextContent('Strategy'); expect(table).toHaveTextContent('Timeframe'); expect(table).toHaveTextContent('Latest result')
  expect(screen.getByRole('switch', { name: `${first.instrument_display_name} monitoring` })).toBeDisabled()
  expect(screen.getByText(/Monitoring controls are not connected yet/)).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Open Backtest' })).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: first.instrument_display_name! }))
  expect(screen.getByRole('button', { name: 'Open Backtest' })).toBeVisible()
})
it('pins a row through its configuration revision without enabling monitoring', async () => {
  const original = monitoringRow(), pinned = { ...original, pinned: true, configurationRevision: 2 }, client = monitorClient(original)
  client.list.mockResolvedValueOnce({ context: monitorContext(), rows: [original] }).mockResolvedValue({ context: monitorContext(), rows: [pinned] })
  client.pin.mockResolvedValue(pinned)
  const props = monitorProps(client); render(<WatchlistMonitorTable {...props} />)
  const pin = await screen.findByRole('button', { name: `Pin ${first.instrument_display_name}` })
  await waitFor(() => expect(pin).toBeEnabled()); fireEvent.click(pin)
  expect(await screen.findByRole('button', { name: `Unpin ${first.instrument_display_name}` })).toHaveAttribute('aria-pressed', 'true')
  expect(client.pin).toHaveBeenCalledWith(monitorContext(), props.members[0].member, 1, true, expect.any(AbortSignal))
  expect(client.setMonitoring).not.toHaveBeenCalled()
  expect(screen.getByRole('switch')).toHaveAttribute('aria-checked', 'false')
})
it('saves an explicit strategy version and timeframe then reads back the row', async () => {
  const row = monitoringRow(), client = monitorClient(row), saved = { ...row, configurationRevision: 2,
    graph: { ...row.graph!, graphVersion: 2, graphVersionAddress: address('5') }, timeframe: '30minute' }
  client.configure.mockResolvedValue(saved)
  client.list.mockResolvedValueOnce({ context: monitorContext(), rows: [row] }).mockResolvedValue({ context: monitorContext(), rows: [saved] })
  render(<WatchlistMonitorTable {...monitorProps(client)} graphs={[{ ...graph, current_version: 2 }]} />)
  await waitFor(() => expect(screen.getByRole('combobox', { name: `${first.instrument_display_name} strategy` })).toBeEnabled())
  await chooseSelect(`${first.instrument_display_name} strategy`, JSON.stringify([graph.identifier, 2]))
  await chooseSelect(`${first.instrument_display_name} timeframe`, '30minute')
  fireEvent.click(screen.getByRole('button', { name: `Apply strategy and timeframe for ${first.instrument_display_name}` }))
  await waitFor(() => expect(client.list).toHaveBeenCalledTimes(2))
  expect(client.configure).toHaveBeenCalledWith(monitorContext(), { kind: 'CANONICAL', instrument_address: first.instrument_address }, 1,
    { graphId: graph.identifier, graphVersion: 2, timeframe: '30minute' }, expect.any(AbortSignal))
  expect(client.setMonitoring).not.toHaveBeenCalled()
})
it('turns monitoring on and off only after confirmed row writes', async () => {
  const row = monitoringRow(), client = monitorClient(row), on = { ...row, monitoring: 'ON' as const, configurationRevision: 2, assignmentId: 'monitor.a' }
  const off = { ...on, monitoring: 'OFF' as const, configurationRevision: 3 }
  client.list.mockResolvedValueOnce({ context: monitorContext(), rows: [row] }).mockResolvedValueOnce({ context: monitorContext(), rows: [on] }).mockResolvedValue({ context: monitorContext(), rows: [off] })
  client.setMonitoring.mockResolvedValueOnce(on).mockResolvedValue(off)
  render(<WatchlistMonitorTable {...monitorProps(client)} />)
  const toggle = screen.getByRole('switch'); await waitFor(() => expect(toggle).toBeEnabled())
  fireEvent.click(toggle); await waitFor(() => expect(toggle).toHaveAttribute('aria-checked', 'true'))
  expect(screen.getByText('Not evaluated')).toBeInTheDocument(); expect(screen.queryByText('HOLD')).not.toBeInTheDocument()
  fireEvent.click(toggle); await waitFor(() => expect(toggle).toHaveAttribute('aria-checked', 'false'))
  expect(client.setMonitoring.mock.calls.map((call) => call.slice(2, 4))).toEqual([[1, true], [2, false]])
})
it.each(['NOT_EVALUATED', 'HOLD', 'SIGNAL', 'WARMUP', 'STALE', 'ERROR'] as const)('renders the exact backend result state %s', async (kind) => {
  const row = monitoringRow(kind)
  render(<WatchlistMonitorTable {...monitorProps(monitorClient(row))} />)
  expect(await screen.findByText(row.result.label)).toBeInTheDocument()
  if (kind === 'HOLD') expect(screen.getByText('Evaluated · no new signal')).toBeInTheDocument()
  if (kind === 'WARMUP') expect(screen.getByText('3 / 20 warmup bars')).toBeInTheDocument()
  if (kind === 'ERROR') expect(screen.getByText('Reconnect your data account.')).toBeInTheDocument()
})
it('filters exact current row facts without treating HOLD or stale results as new signals', () => {
  expect(matchesWatchlistFilter(undefined, 'ALL')).toBe(true)
  expect(matchesWatchlistFilter(undefined, 'ATTENTION')).toBe(true)
  expect(matchesWatchlistFilter(monitoringRow('HOLD'), 'SIGNALS')).toBe(false)
  expect(matchesWatchlistFilter(monitoringRow('STALE'), 'SIGNALS')).toBe(false)
  expect(matchesWatchlistFilter(monitoringRow('SIGNAL'), 'SIGNALS')).toBe(true)
  expect(matchesWatchlistFilter(monitoringRow(), 'PINNED')).toBe(false)
  expect(matchesWatchlistFilter({ ...monitoringRow(), pinned: true }, 'PINNED')).toBe(true)
  expect(matchesWatchlistFilter(monitoringRow('WARMUP'), 'ATTENTION')).toBe(true)
})
it('retains row choices and requires readback after an uncertain write instead of repeating it', async () => {
  const client = monitorClient()
  client.configure.mockRejectedValue(new ApiError('network', 'lost response'))
  render(<WatchlistMonitorTable {...monitorProps(client)} graphs={[{ ...graph, current_version: 2 }]} />)
  await waitFor(() => expect(screen.getByRole('combobox', { name: `${first.instrument_display_name} strategy` })).toBeEnabled())
  await chooseSelect(`${first.instrument_display_name} strategy`, JSON.stringify([graph.identifier, 2]))
  fireEvent.click(screen.getByRole('button', { name: `Apply strategy and timeframe for ${first.instrument_display_name}` }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Refresh rows to check the saved state')
  expect(screen.getByRole('combobox', { name: `${first.instrument_display_name} strategy` })).toHaveTextContent('v2')
  expect(screen.getByRole('switch')).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: 'Refresh rows' }))
  await waitFor(() => expect(screen.getByRole('switch')).toBeEnabled())
  expect(client.configure).toHaveBeenCalledTimes(1)
  expect(screen.getByRole('combobox', { name: `${first.instrument_display_name} strategy` })).toHaveTextContent('v2')
})
it.each(['owner', 'scope'] as const)('ignores a late row write after the active %s context changes', async (change) => {
  const client = monitorClient(), props = monitorProps(client)
  let finish!: (row: WatchlistMonitorRow) => void
  client.pin.mockImplementation(() => new Promise((resolve) => { finish = resolve }))
  const view = render(<WatchlistMonitorTable {...props} />)
  const pin = screen.getByRole('button', { name: `Pin ${first.instrument_display_name}` }); await waitFor(() => expect(pin).toBeEnabled()); fireEvent.click(pin)
  const signal = client.pin.mock.calls[0][4] as AbortSignal
  const next = { ...props, api: change === 'owner' ? apiFor() as unknown as StrategyApi : props.api,
    context: change === 'scope' ? { ...props.context, scopeRevision: 2, scopeAddress: address('f') } : props.context }
  client.list.mockResolvedValue({ context: next.context, rows: [monitoringRow()] })
  view.rerender(<WatchlistMonitorTable {...next} />)
  expect(signal.aborted).toBe(true)
  await act(async () => finish({ ...monitoringRow(), pinned: true, configurationRevision: 2 }))
  expect(screen.queryByRole('button', { name: `Unpin ${first.instrument_display_name}` })).not.toBeInTheDocument()
})
it('rejects foreign scope, substituted member and mismatched assignment or graph result identity', () => {
  const props = monitorProps(), context = monitorContext(), row = monitoringRow('SIGNAL')
  expect(verifyWatchlistMonitorSnapshot({ context, rows: [row] }, context, props.members)).toEqual([row])
  const invalid = [
    { context: { ...context, scopeAddress: address('f') }, rows: [row] },
    { context, rows: [] }, { context, rows: [{ ...row, memberKey: 'foreign' }] },
    { context, rows: [{ ...row, configurationRevision: -1 }] },
    { context, rows: [{ ...row, result: { ...row.result, assignmentId: 'monitor.other' } }] },
    { context, rows: [{ ...row, result: { ...row.result, graphVersionAddress: address('f') } }] },
    { context, rows: [{ ...row, result: { ...row.result, assignmentId: null } }] },
  ]
  for (const value of invalid) expect(() => verifyWatchlistMonitorSnapshot(value, context, props.members)).toThrow(ContractError)
})
it('polls requested monitoring without overlapping requests or resetting draft selections', async () => {
  const row = { ...monitoringRow(), monitoring: 'STARTING' as const }, client = monitorClient(row)
  const props = monitorProps(client)
  render(<WatchlistMonitorTable {...props} graphs={[{ ...graph, current_version: 2 }]} />)
  await waitFor(() => expect(screen.getByRole('switch')).toBeEnabled())
  await chooseSelect(`${first.instrument_display_name} strategy`, JSON.stringify([graph.identifier, 2]))
  let finish!: (snapshot: { context: WatchlistMonitorContext; rows: WatchlistMonitorRow[] }) => void
  client.list.mockImplementationOnce(() => new Promise((resolve) => { finish = resolve }))
  // Restart the timer under the fake clock without changing the saved configuration.
  vi.useFakeTimers()
  fireEvent.click(screen.getByRole('button', { name: 'Refresh rows' }))
  await act(async () => finish({ context: props.context, rows: [row] }))
  client.list.mockImplementationOnce(() => new Promise((resolve) => { finish = resolve }))
  await act(async () => { await vi.advanceTimersByTimeAsync(5_000) })
  expect(client.list).toHaveBeenCalledTimes(3)
  await act(async () => { await vi.advanceTimersByTimeAsync(20_000) })
  expect(client.list).toHaveBeenCalledTimes(3)
  const signal = { ...monitoringRow('SIGNAL'), monitoring: 'ON' as const, configurationRevision: 2 }
  await act(async () => finish({ context: props.context, rows: [signal] }))
  expect(screen.getByText('Buy signal')).toBeInTheDocument()
  expect(screen.getByRole('combobox', { name: `${first.instrument_display_name} strategy` })).toHaveTextContent('v2')
  expect(screen.getByRole('button', { name: `Apply strategy and timeframe for ${first.instrument_display_name}` })).toBeEnabled()
  await act(async () => { await vi.advanceTimersByTimeAsync(5_000) })
  expect(client.list).toHaveBeenCalledTimes(4)
})
it.each(['owner', 'scope', 'client', 'unmount'] as const)('cancels polling and ignores late results after %s changes', async (change) => {
  const row = { ...monitoringRow('HOLD'), monitoring: 'ON' as const }, client = monitorClient(row), props = monitorProps(client)
  vi.useFakeTimers()
  const view = render(<WatchlistMonitorTable {...props} />)
  await act(async () => {})
  let finish!: (snapshot: { context: WatchlistMonitorContext; rows: WatchlistMonitorRow[] }) => void
  client.list.mockImplementationOnce(() => new Promise((resolve) => { finish = resolve }))
  await act(async () => { await vi.advanceTimersByTimeAsync(5_000) })
  const signal = client.list.mock.calls[1][1] as AbortSignal
  const next = { ...props, api: change === 'owner' ? apiFor() as unknown as StrategyApi : props.api,
    context: change === 'scope' ? { ...props.context, scopeRevision: 2, scopeAddress: address('f') } : props.context,
    client: change === 'client' ? monitorClient() : client }
  client.list.mockResolvedValue({ context: next.context, rows: [monitoringRow()] })
  if (change === 'unmount') view.unmount()
  else view.rerender(<WatchlistMonitorTable {...next} />)
  expect(signal.aborted).toBe(true)
  await act(async () => finish({ context: props.context, rows: [monitoringRow('SIGNAL')] }))
  expect(screen.queryByText('Buy signal')).not.toBeInTheDocument()
  const count = client.list.mock.calls.length
  await act(async () => { await vi.advanceTimersByTimeAsync(20_000) })
  expect(client.list).toHaveBeenCalledTimes(count)
})
it('does not poll unbound rows and stops after an invalid monitoring response', async () => {
  const client = monitorClient(), props = monitorProps(client)
  vi.useFakeTimers()
  render(<WatchlistMonitorTable {...props} />)
  await act(async () => {})
  await act(async () => { await vi.advanceTimersByTimeAsync(20_000) })
  expect(client.list).toHaveBeenCalledTimes(1)
  client.list.mockResolvedValueOnce({ context: props.context, rows: [{ ...monitoringRow(), monitoring: 'ON' }] })
  fireEvent.click(screen.getByRole('button', { name: 'Refresh rows' }))
  await act(async () => {})
  client.list.mockResolvedValueOnce({ context: { ...props.context, scopeRevision: 99 }, rows: [monitoringRow('SIGNAL')] })
  await act(async () => { await vi.advanceTimersByTimeAsync(5_000) })
  expect(screen.queryByText('Buy signal')).not.toBeInTheDocument()
  expect(screen.getByRole('alert')).toHaveTextContent('Refresh rows')
  expect(screen.getByRole('switch')).toBeDisabled()
  await act(async () => { await vi.advanceTimersByTimeAsync(20_000) })
  expect(client.list).toHaveBeenCalledTimes(3)
})
it('continues polling when the client reuses the same snapshot and rows array', async () => {
  const row = { ...monitoringRow('HOLD'), monitoring: 'PAUSED' as const }, client = monitorClient(row)
  vi.useFakeTimers()
  render(<WatchlistMonitorTable {...monitorProps(client)} />)
  await act(async () => {})
  for (let count = 2; count <= 4; count++) {
    await act(async () => { await vi.advanceTimersByTimeAsync(5_000) })
    expect(client.list).toHaveBeenCalledTimes(count)
  }
})
it.each(['network', 'timeout', 'server'] as const)('recovers automatically from %s reads with capped backoff and locked writes', async (kind) => {
  const row = { ...monitoringRow('HOLD'), monitoring: 'ON' as const }, client = monitorClient(row)
  vi.useFakeTimers()
  render(<WatchlistMonitorTable {...monitorProps(client)} />)
  await act(async () => {})
  for (let attempt = 0; attempt < 5; attempt++) client.list.mockRejectedValueOnce(new ApiError(kind, 'Temporary failure'))
  await act(async () => { await vi.advanceTimersByTimeAsync(5_000) })
  expect(screen.getByText('HOLD')).toBeInTheDocument()
  expect(screen.getByRole('switch')).toBeDisabled()
  expect(screen.getByRole('alert')).toHaveTextContent('retry automatically')
  let count = 2
  for (const delay of [5_000, 10_000, 20_000, 30_000, 30_000]) {
    await act(async () => { await vi.advanceTimersByTimeAsync(delay - 1) })
    expect(client.list).toHaveBeenCalledTimes(count)
    await act(async () => { await vi.advanceTimersByTimeAsync(1) })
    expect(client.list).toHaveBeenCalledTimes(++count)
  }
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  expect(screen.getByRole('switch')).toBeEnabled()
  await act(async () => { await vi.advanceTimersByTimeAsync(5_000) })
  expect(client.list).toHaveBeenCalledTimes(count + 1)
  expect(client.setMonitoring).not.toHaveBeenCalled()
})
it('retries a temporary initial read failure without waiting for saved monitoring rows', async () => {
  const client = monitorClient()
  client.list.mockRejectedValueOnce(new ApiError('network', 'Temporary failure'))
  vi.useFakeTimers()
  render(<WatchlistMonitorTable {...monitorProps(client)} />)
  await act(async () => {})
  expect(screen.getByRole('switch')).toBeDisabled()
  await act(async () => { await vi.advanceTimersByTimeAsync(5_000) })
  expect(client.list).toHaveBeenCalledTimes(2)
  expect(screen.getByRole('switch')).toBeEnabled()
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
})
it.each([new ContractError(), new ApiError('access', 'Permission denied'),
  new ApiError('server', 'Scope changed', { code: 'WATCHLIST_MONITORING_CONFLICT', message: 'Scope changed' }),
  new ApiError('server', 'Scope missing', { code: 'STATIC_SCOPE_NOT_FOUND', message: 'Scope missing' }),
])('stops automatic reads after a permanent error: %s', async (error) => {
  const client = monitorClient({ ...monitoringRow('HOLD'), monitoring: 'ON' })
  vi.useFakeTimers()
  render(<WatchlistMonitorTable {...monitorProps(client)} />)
  await act(async () => {})
  client.list.mockRejectedValueOnce(error)
  await act(async () => { await vi.advanceTimersByTimeAsync(5_000) })
  expect(screen.getByRole('switch')).toBeDisabled()
  expect(screen.getByText('HOLD')).toBeInTheDocument()
  await act(async () => { await vi.advanceTimersByTimeAsync(60_000) })
  expect(client.list).toHaveBeenCalledTimes(2)
  fireEvent.click(screen.getByRole('button', { name: 'Refresh rows' }))
  await act(async () => {})
  expect(screen.getByRole('switch')).toBeEnabled()
  await act(async () => { await vi.advanceTimersByTimeAsync(5_000) })
  expect(client.list).toHaveBeenCalledTimes(4)
})
it('keeps an uncertain save separate from automatic read recovery and never retries the write', async () => {
  const client = monitorClient({ ...monitoringRow('HOLD'), monitoring: 'ON' })
  client.pin.mockRejectedValue(new ApiError('network', 'Lost write response'))
  vi.useFakeTimers()
  render(<WatchlistMonitorTable {...monitorProps(client)} />)
  await act(async () => {})
  fireEvent.click(screen.getByRole('button', { name: `Pin ${first.instrument_display_name}` }))
  await act(async () => {})
  expect(screen.getByRole('alert')).toHaveTextContent('Refresh rows to check the saved state')
  await act(async () => { await vi.advanceTimersByTimeAsync(60_000) })
  expect(client.pin).toHaveBeenCalledTimes(1)
  expect(client.list).toHaveBeenCalledTimes(1)
  fireEvent.click(screen.getByRole('button', { name: 'Refresh rows' }))
  await act(async () => {})
  expect(screen.getByRole('switch')).toBeEnabled()
  expect(client.pin).toHaveBeenCalledTimes(1)
})
it('adds and removes members inline through immutable scope revisions without trading controls', async () => {
  const api = apiFor(), provider = providerClient(), pointer = providerPointer()
  const added = scopeV2(initial.scope_id, 2, initial.name, [{ kind: 'CANONICAL', instrument_address: first.instrument_address }, pointer], initial.address)
  const removed = scopeV2(initial.scope_id, 3, initial.name, [{ kind: 'CANONICAL', instrument_address: first.instrument_address }], added.address)
  api.reviseStaticScope.mockResolvedValueOnce(added).mockResolvedValue(removed)
  api.staticScope.mockResolvedValueOnce(added).mockResolvedValueOnce(removed)
  show(api, { providerClient: provider })
  fireEvent.click(await screen.findByText('Add instrument', { selector: 'summary' }))
  fireEvent.change(screen.getByRole('searchbox', { name: 'Provider symbol or name' }), { target: { value: smallcap.symbol } })
  fireEvent.click(screen.getByRole('button', { name: 'Search provider' }))
  fireEvent.click(await screen.findByRole('button', { name: addName() }))
  await screen.findByText('Saved revision 2.')
  expect(api.reviseStaticScope.mock.calls[0].slice(0, 3)).toEqual([project.project_id, initial.scope_id, 1])
  fireEvent.click(await screen.findByRole('button', { name: `Remove ${providerReferenceLabel(smallcap)}` }))
  await screen.findByText('Saved revision 3.')
  expect(api.reviseStaticScope.mock.calls[1][3].members).toEqual([{ kind: 'CANONICAL', instrument_address: first.instrument_address }])
})
