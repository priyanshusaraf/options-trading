import { chooseSelect } from '../test/select'
import { readFileSync } from 'node:fs'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, type StrategyApi } from '../shell/api'
import type { StaticScope } from '../features/static-scopes/staticScopeContracts'
import type { AvailableVisualization, ExperimentPage, GraphSummary, Project, PublishedGraph, ReviewTimeline, V2Draft, V2Presentation, VerifiedCatalogue } from '../shell/contracts'
import { parseExperimentStart } from '../shell/contracts'
import { ResearchWorkspace } from './ResearchWorkspace'

// jsdom has no layout matrix; canvas geometry is checked in browser QA.
const updateNodeInternals = vi.hoisted(() => vi.fn())
vi.mock('@xyflow/react', async () => {
  const actual = await vi.importActual<typeof import('@xyflow/react')>('@xyflow/react')
  return { ...actual, useUpdateNodeInternals: () => updateNodeInternals }
})

async function watchlistMenu() {
  fireEvent.keyDown(await screen.findByRole('combobox', { name: 'Saved watchlist' }), { key: 'ArrowDown' })
  return screen.findByRole('listbox')
}

async function selectLength() {
  if (!screen.queryByLabelText('Length')) fireEvent.click((await screen.findByText('Component 1', { selector: '.workstation-node-heading strong' })).closest('.react-flow__node')!)
  return screen.getByLabelText('Length')
}

const address = (digit: string) => `sha256:${digit.repeat(64)}`
const project: Project = { project_id: 'project.synthetic', name: 'Research desk', description: '', status: 'active' }
const graph: GraphSummary = { identifier: 'strategy.owner-authored', display_name: 'Owner authored', draft_revision: 1, current_version: 2 }
const published: PublishedGraph = { project_id: project.project_id, identifier: graph.identifier, version: 2, content_address: address('a') }
const groups = ['TYPE_4', 'TYPE_2', 'TYPE_3', 'TYPE_5', 'TYPE_1'].map((family, index) => ({ order: index + 1, visible_family: family, display_name: `Family ${index + 1}`, components: [{
  component_kind: 'LEAF' as const, component_id: `component.${index}`, component_version: 1, component_address: address(String(index + 1)), display_name: `Component ${index + 1}`,
  visible_family: family, presentation_group_name: `Family ${index + 1}`, descriptor: { component_id: `component.${index}`, component_version: 1,
    ports: [{ port_id: 'value', direction: index === 0 ? 'output' : 'input', semantic_flow: 'value', semantic_role: 'value', type_ref: { type_id: 'number', type_version: 1 }, shape: 'series' }],
    parameters: index === 0 ? { length: { type: 'int', default: 20, units: 'bars' } } : {} }, help: { component_id: `component.${index}`, component_version: 1, implementation_binding: address('e'), semantic_kind: 'LOGICAL_OPERATION' as const,
    description: 'Returns the reviewed fixture result when inputs are valid.', semantic_text: 'Return the exact reviewed fixture result.', sources: [{ source_record_id: 'strategy-os-type5-evaluator-v1', title: 'Strategy OS logic evaluator', authors_or_organization: 'Strategy OS', publication_or_version: 'First-party evaluator version 1', year: 2026, url: null, claim_scope: `Defines component.${index}.` }],
    customisation: { parameters: index === 0 ? [{ name: 'length', type: 'int', required: false, default: 20, enum: null, domain: { minimum: 1, maximum: 100 }, units: 'bars', serialization: 'canonical-json' }] : [], guidance: index === 0 ? 'Set only this authored parameter: length.' : 'This built-in has no parameters.', built_in_code_immutable: true as const, immutable_boundary: 'This is an immutable built-in. You can change only the listed parameters; you cannot edit its code here.' }, availability: { status: 'AVAILABLE' as const, authority: 'NONE' as const, condition: 'Available within the declared research contract when required inputs are valid.' } }, data_requirement: {}, availability: { status: 'AVAILABLE' as const,
    authority: 'NONE' as const, provider_support_verified: false as const, data_rights_verified: false as const, backtest_eligible: false as const },
}] }))
const catalogue: VerifiedCatalogue = { schema: 'strategy-os-verified-language-catalogue/1', registry_identity: address('c'), catalogue_identity: address('d'), groups }
const v2Draft: V2Draft = { project_id: project.project_id, graph_identifier: graph.identifier, semantic_revision: 1, current_version: 2, published_revision: 1,
  document: { format_version: 2, strategy_id: graph.identifier, strategy_version: 3, metadata: { metadata_version: 1, name: graph.display_name, description: '', tags: [] }, graph_inputs: [{ port_id: 'frame', direction: 'input', semantic_flow: 'data', semantic_role: 'market_frame', type_ref: { type_id: 'market_frame', type_version: 1 }, shape: 'series' }], graph_outputs: [],
    nodes: [{ node_id: 'n_signal', component: { component_id: 'component.0', component_version: 1 }, parameters: { length: 20 } }], edges: [] }, content_address: address('a'), graph_address: address('b') }
const v2Presentation: V2Presentation = { schema: 'strategy-os-v2-presentation-state/1', semantic_revision: 1, presentation_revision: 0,
  presentation: { positions: { n_signal: { x: 0, y: 0 } }, groups: {}, viewport: { x: 0, y: 0, zoom: 1 }, selection: { nodes: [], edges: [], outputs: [] } }, presentation_address: address('f'),
  orphaned_references: { positions: [], groups: [], selection_nodes: [], selection_edges: [], selection_outputs: [] }, executable_identity: false }
const contract = { charge_model: 'zerodha_charges_v1' as const, sizing_model: 'one_lot_or_cash_budget_v1' as const, slippage_bps: 5, slippage_multiplier: 2,
  gates: { min_oos_trades: 10, n_folds: 3, min_positive_fold_fraction: .6, optimize_search: false, pbo_threshold: .3, sibling_trials: 1 } }
const runs: ExperimentPage = { runs: [{ run_id: 7, spec_id: 'e'.repeat(32), status: 'completed', decision: 'archive', evidence_state: 'verified', graph: published, dataset_bindings: [], contract }] }
const review: ReviewTimeline = { project_id: project.project_id, as_of: '2026-08-28T12:00:00Z', next_cursor: null, source_errors: [], events: [{ event_id: 'graph:2', type: 'graph_version_published', occurred_at: '2026-08-28T11:00:00Z', status: 'published', summary: 'Published owner-authored version 2' }] }
const visualization: AvailableVisualization = { schema: 'strategy-os-backtest-visualization/1', state: 'AVAILABLE', visualization_address: address('9'),
  identity: { terminal_evidence_address: address('8'), calculation_schema: 'strategy-os-net-equity-close-drawdown/1' },
  summary: { net_return_pct: 1.5, max_close_to_close_drawdown_pct: 2, trades: 1 }, series: { net_equity: { points: [{ time: 1, value: 100000 }, { time: 2, value: 101500 }], original_count: 2 },
    drawdown: { points: [{ time: 1, value: 0, absolute: 0 }, { time: 2, value: 0, absolute: 0 }], original_count: 2 }, benchmark: { state: 'UNAVAILABLE' }, trade_events: [] },
  trade_page: { items: [], next_cursor: null, total: 1, detail_reason: 'TRADE_DETAIL_UNAVAILABLE_OVER_LIMIT' }, costs: { charges_total: 42, breakdown: { reason_code: 'ITEMIZED_CHARGE_LEGS_NOT_PERSISTED' }, slippage: { bps: 5, multiplier: 2, mean_stressed_net: 12, passed: true } }, folds: [], provenance: {} }

function api() { return {
  strategyResearchSettings: vi.fn().mockResolvedValue({ workspace: { owner_id: 'owner.a', graph_identifier: null, revision: 0, enabled: true, values: {}, content_address: address('1') }, strategy: { owner_id: 'owner.a', graph_identifier: graph.identifier, revision: 0, enabled: true, values: {}, content_address: address('2') }, values: { research_capital: 100000, seed: 0, min_trades: 10, n_folds: 4, min_positive_fold_frac: .6, risk_policy: 'none' }, sources: {} }),
  researchRecovery: vi.fn().mockResolvedValue({ complete: true, requests: [] }),
  v2Version: vi.fn().mockResolvedValue({ format_version: 2, graph_identifier: graph.identifier, graph_version: 2, content_address: address('a'), document: v2Draft.document }), experiments: vi.fn().mockResolvedValue(runs), catalogue: vi.fn().mockResolvedValue(catalogue), v2Draft: vi.fn().mockResolvedValue(v2Draft), v2Presentation: vi.fn().mockResolvedValue(v2Presentation),
  validateV2: vi.fn().mockResolvedValue({ schema: 'strategy-os-v2-semantic-receipt/2', commit_state: 'DRY_RUN_ROLLED_BACK', intent: 'EDIT', base_semantic_revision: 1, result_semantic_revision: 2,
    base_content_address: address('a'), result_content_address: address('2'), base_graph_address: address('b'), result_graph_address: address('3'), forward_commands: [], inverse_commands: [], receipt_address: address('4') }),
  researchDatasets: vi.fn().mockResolvedValue([{ manifest_address: address('1'), instrument_address: address('f'), canonical_instrument_label: 'XNSE · EQUITY SPOT · ffffffffffff', asset_class: 'EQUITY', contract_kind: 'SPOT', interval: '15minute', event_start: '2026-01-01T00:00:00+00:00', event_end: '2026-01-02T00:00:00+00:00', availability_end: '2026-01-02T00:15:00+00:00', as_of: '2026-01-03T00:00:00+00:00', bar_count: 100, fields: ['close', 'high', 'low', 'open', 'volume'], provider_evidence_state: 'VERIFIED_REFERENCES_PRESENT', market_truth_state: 'VERIFIED_REFERENCES_PRESENT', gaps: [], backtest_eligibility: 'ELIGIBLE_Q03', refusal_code: null }]),
  prepareResearchFromSettings: vi.fn().mockResolvedValue({ request_id: 'request', operation_id: 'd'.repeat(64), status: 'pending' }), researchOperation: vi.fn().mockResolvedValue({ operation_id: 'd'.repeat(64), status: 'completed', stage: 'completed', completed_run_ids: [8], cancel_requested: false, error: null }), visualization: vi.fn().mockResolvedValue(visualization), compareVersions: vi.fn(), review: vi.fn().mockResolvedValue(review),
} as unknown as StrategyApi }

afterEach(cleanup)

describe('real-data Precision Slate research workspace', () => {
  it('keeps user-facing JSX, display literals and generated CSS in plain language', () => {
    const sources = [
      ['ResearchWorkspace.tsx', readFileSync('src/research/ResearchWorkspace.tsx', 'utf8')],
      ['graph.tsx', readFileSync('src/components/graph.tsx', 'utf8')],
      ['surfaces.tsx', readFileSync('src/components/surfaces.tsx', 'utf8')],
      ['precision.css', readFileSync('src/shell/precision.css', 'utf8')],
    ]
    if (process.env.PLAIN_LANGUAGE_ABLATION === 'jsx') {
      sources.push(['isolated-ablation.tsx', '<p>Canonical strategy copy</p>'])
    }
    const renderablePatterns = [
      />\s*[^<{]*\bcanonical\b[^<{]*\s*</i,
      /\b(?:aria-label|title|eyebrow|detail|label|sub)\s*=\s*["'][^"']*\bcanonical\b[^"']*["']/i,
      /\b(?:title|eyebrow|detail|label|sub)\s*:\s*["'][^"']*\bcanonical\b[^"']*["']/i,
      /\bcontent\s*:\s*["'][^"']*\bcanonical\b[^"']*["']/i,
    ]
    const violations = sources.flatMap(([path, source]) => renderablePatterns
      .filter((pattern) => pattern.test(source))
      .map((pattern) => `${path}: ${pattern.source}`))
    expect(violations).toEqual([])
    const sourceByPath = Object.fromEntries(sources)
    expect(sourceByPath['ResearchWorkspace.tsx']).toContain('Your saved versions and backtest history.')
    expect(sourceByPath['ResearchWorkspace.tsx']).toContain('Loading builder…')
    expect(sourceByPath['graph.tsx']).toContain("sub: 'Strategy binding'")
    expect(sourceByPath['surfaces.tsx']).toContain('eyebrow="Instrument roles"')
    expect(sourceByPath['surfaces.tsx']).toContain("label: 'Resolved instruments'")
    expect(sourceByPath['precision.css']).toContain('Open an existing strategy to build with the verified palette.')
  })

  it('parses accepted Q03 bindings without truncating canonical identities', () => { const parsed = parseExperimentStart({ spec_id: 'e'.repeat(32), run_id: 7, decision: 'archive', binding: { graph: published,
    canonical_dataset_bindings: { schema: 'canonical-dataset-bindings/1', codec: 'strategy-os-observation-candle-index/1', adapter_contract: 'q03-provider-provenance-index-encoding/1', adapter_source_address: address('9'), bindings: { key: { manifest_address: address('1'), instrument_address: address('f'), as_of: '2026-08-28T10:00:00+00:00', time_interpretation: { resolution_seconds: 900 } } } },
    cost_assumptions: { capital: 100000, charge_model: 'zerodha_charges_v1', sizing_model: 'one_lot_or_cash_budget_v1', slippage_bps: 5, slippage_multiplier: 2 }, gates: { min_oos_trades: 10, n_folds: 3, min_positive_fold_fraction: .6, optimize_search: false, pbo_threshold: .3, sibling_trials: 1 } } })
    expect(parsed.dataset_bindings[0].manifest_address).toBe(address('1')) })

  it('builds from server families, validates one staged batch, selects real history, and opens persisted results', async () => {
    const client = api(); render(<ResearchWorkspace api={client} project={project} graph={graph} onPublished={vi.fn()} backtestEnabled reviewEnabled />)
    expect(await screen.findByText('Version 2')).toBeInTheDocument(); expect(screen.getByText('Run 7')).toBeInTheDocument(); expect(document.body.textContent).not.toContain(address('a')); fireEvent.click(screen.getByRole('button', { name: 'Build' }))
    expect(await screen.findByRole('heading', { name: 'Build strategy' })).toBeInTheDocument()
    HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', '') }; HTMLDialogElement.prototype.close = function () { this.removeAttribute('open') }
    fireEvent.click(screen.getByRole('button', { name: 'Add component' }))
    expect([...document.querySelectorAll('.component-explorer summary')].map((node) => node.firstChild?.textContent)).toEqual(['Data', 'Indicators', 'Market structure', 'Logic', 'Execution'])
    fireEvent.click(screen.getByRole('button', { name: 'Close component explorer' }))
    fireEvent.click((await screen.findByText('Component 1', { selector: '.workstation-node-heading strong' })).closest('.react-flow__node')!)
    fireEvent.change(await selectLength(), { target: { value: '30' } }); fireEvent.blur(screen.getByLabelText('Length')); fireEvent.click(screen.getByRole('button', { name: 'Check strategy' }))
    await waitFor(() => expect(client.validateV2).toHaveBeenCalledWith(project.project_id, graph.identifier, 1, [expect.objectContaining({ command: 'set_parameter', value: 30 })], expect.any(AbortSignal)))
    expect(await screen.findByText(/Strategy check completed. Nothing was saved/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Backtest' })); expect(await screen.findByText('Ready for backtesting')).toBeInTheDocument(); await waitFor(() => expect(screen.getByRole('button', { name: 'Run version 2' })).toBeEnabled()); fireEvent.click(screen.getByRole('button', { name: 'Run version 2' })); await waitFor(() => expect(client.prepareResearchFromSettings).toHaveBeenCalled())
    expect(JSON.stringify(vi.mocked(client.prepareResearchFromSettings).mock.calls[0][3])).not.toMatch(/provider|broker|order|position/); expect(await screen.findByText('Net equity and close-to-close drawdown')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Review' })); expect(await screen.findByText('Published owner-authored version 2')).toBeInTheDocument()
  })
})


it('opens an unpublished strategy in Build and preserves a chosen tab across draft and publication updates', async () => {
  const client = api(), draftGraph = { ...graph, current_version: null }
  vi.mocked(client.v2Draft).mockResolvedValue({ ...v2Draft, current_version: null, published_revision: null })
  const props = { api: client, project, graph: draftGraph, onPublished: vi.fn(), backtestEnabled: true, reviewEnabled: true }
  const view = render(<ResearchWorkspace {...props} />)
  expect(screen.getByRole('button', { name: 'Build' })).toHaveAttribute('aria-current', 'page')
  expect(await screen.findByRole('heading', { name: 'Build strategy' })).toBeInTheDocument()
  expect(client.v2Version).not.toHaveBeenCalled()
  const overview = screen.getByRole('button', { name: 'Overview' })
  overview.focus(); fireEvent.click(overview)
  expect(await screen.findByText('Save a version in Build when you are ready to backtest.')).toBeInTheDocument()
  const draftCalls = vi.mocked(client.v2Draft).mock.calls.length
  view.rerender(<ResearchWorkspace {...props} graph={{ ...draftGraph, draft_revision: 2 }} />)
  expect(overview).toHaveAttribute('aria-current', 'page')
  expect(overview).toHaveFocus()
  view.rerender(<ResearchWorkspace {...props} graph={{ ...graph, draft_revision: 2 }} />)
  expect(overview).toHaveAttribute('aria-current', 'page')
  expect(client.v2Draft).toHaveBeenCalledTimes(draftCalls)
})

it('keeps published Overview readable without internal identifiers or invented backtests', async () => {
  const client = api(); vi.mocked(client.experiments).mockResolvedValue({ runs: [] })
  render(<ResearchWorkspace api={client} project={project} graph={graph} onPublished={vi.fn()} backtestEnabled reviewEnabled />)
  expect(screen.getByRole('button', { name: 'Overview' })).toHaveAttribute('aria-current', 'page')
  expect(await screen.findByText('No backtests yet for this strategy.')).toBeInTheDocument()
  expect(screen.queryByText(/Saved strategy evidence|evidence plane|immutable V2|Graph identity/)).not.toBeInTheDocument()
  for (const value of [project.project_id, graph.identifier, address('a')]) {
    expect(screen.queryByText(value)).not.toBeInTheDocument()
  }
  expect(screen.queryByText('Run 7')).not.toBeInTheDocument()
  expect(await screen.findByText('Version 2')).toBeInTheDocument()
  expect(document.querySelector('.overview-plane pre, .overview-plane code, .overview-plane details')).toBeNull()
})

it('composes real run charts with the builder and retains edits across pane controls', async () => {
  const client = api()
  render(<ResearchWorkspace api={client} project={project} graph={graph} onPublished={vi.fn()} backtestEnabled reviewEnabled />)
  fireEvent.click(screen.getByRole('button', { name: 'Build' }))
  expect(await screen.findByRole('heading', { name: 'Build strategy' })).toBeInTheDocument()
  expect(screen.getByText(/Select a run to inspect/)).toBeInTheDocument()
  expect(client.visualization).not.toHaveBeenCalled()
  fireEvent.change(await selectLength(), { target: { value: '35' } }); fireEvent.blur(screen.getByLabelText('Length'))
  fireEvent.click(await screen.findByRole('button', { name: 'Run 7 Version 2 · completed' }))
  expect(await screen.findByText('Net equity and close-to-close drawdown')).toBeInTheDocument()
  expect(client.visualization).toHaveBeenCalledWith(project.project_id, 7, 0, expect.any(AbortSignal))
  const width = screen.getByRole('separator', { name: 'Lists pane width' })
  fireEvent.keyDown(width, { key: 'End' }); expect(width).toHaveAttribute('aria-valuenow', '70')
  fireEvent.keyDown(width, { key: 'ArrowRight' }); expect(width).toHaveAttribute('aria-valuenow', '70')
  fireEvent.keyDown(width, { key: 'Home' }); expect(width).toHaveAttribute('aria-valuenow', '20')
  const height = screen.getByRole('separator', { name: 'Chart pane height' })
  fireEvent.keyDown(height, { key: 'ArrowUp' }); expect(height).toHaveAttribute('aria-valuenow', '43')
  fireEvent.keyDown(height, { key: 'x' }); expect(height).toHaveAttribute('aria-valuenow', '43')
  for (const pane of ['chart', 'runs', 'builder']) {
    fireEvent.click(screen.getByRole('button', { name: `Maximize ${pane} pane` }))
    expect(document.querySelector('.studio-panes')).toHaveAttribute('data-expanded', pane)
    fireEvent.click(screen.getByRole('button', { name: `Restore ${pane} pane` }))
  }
  expect(screen.getByLabelText('Length')).toHaveValue('35')
  fireEvent.click(screen.getByRole('button', { name: 'Reset panes' }))
  expect(screen.getByRole('separator', { name: 'Lists pane width' })).toHaveAttribute('aria-valuenow', '24')
  expect(screen.getByRole('separator', { name: 'Chart pane height' })).toHaveAttribute('aria-valuenow', '45')
})

it('excludes unrelated runs and explains unavailable charts without synthetic series', async () => {
  const client = api()
  vi.mocked(client.experiments).mockResolvedValue({ runs: [...runs.runs, { ...runs.runs[0], run_id: 99, graph: { ...published, identifier: 'other-strategy' } }] })
  vi.mocked(client.visualization).mockResolvedValue({ schema: 'strategy-os-backtest-visualization/1', state: 'UNAVAILABLE', reason_code: 'NO_EVIDENCE' })
  render(<ResearchWorkspace api={client} project={project} graph={graph} onPublished={vi.fn()} backtestEnabled reviewEnabled />)
  fireEvent.click(screen.getByRole('button', { name: 'Build' }))
  fireEvent.click(await screen.findByRole('button', { name: 'Run 7 Version 2 · completed' }))
  expect(await screen.findByText(/This run has no persisted chart/)).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /Run 99/ })).not.toBeInTheDocument()
  expect(screen.queryByText('Net equity and close-to-close drawdown')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Backtest' }))
  expect(screen.getByRole('button', { name: 'Backtest' })).toHaveAttribute('aria-current', 'page')
})

it('resizes by pointer and stops on cancellation, then opens the selected run price source', async () => {
  const client = api()
  client.marketContext = vi.fn().mockRejectedValue(new Error('Price source unavailable'))
  render(<ResearchWorkspace api={client} project={project} graph={graph} onPublished={vi.fn()} backtestEnabled reviewEnabled />)
  fireEvent.click(screen.getByRole('button', { name: 'Build' }))
  const width = screen.getByRole('separator', { name: 'Lists pane width' })
  Object.defineProperty(width, 'setPointerCapture', { configurable: true, value: vi.fn() })
  vi.spyOn(width.parentElement!, 'getBoundingClientRect').mockReturnValue({ width: 1000, height: 800 } as DOMRect)
  const pointer = (type: string, x: number, button = 0) => fireEvent(width, new MouseEvent(type, { clientX: x, button, bubbles: true }))
  pointer('pointerdown', 100, 1); pointer('pointermove', 200); expect(width).toHaveAttribute('aria-valuenow', '24')
  pointer('pointerdown', 100); pointer('pointermove', 200); expect(width).toHaveAttribute('aria-valuenow', '34')
  pointer('pointercancel', 200); pointer('pointermove', 500); expect(width).toHaveAttribute('aria-valuenow', '34')
  pointer('pointerdown', 100); pointer('pointermove', -1000); expect(width).toHaveAttribute('aria-valuenow', '20')
  pointer('pointerup', -1000); pointer('pointermove', 200); expect(width).toHaveAttribute('aria-valuenow', '20')
  fireEvent.click(await screen.findByRole('button', { name: 'Run 7 Version 2 · completed' }))
  expect(await screen.findByText('Net equity and close-to-close drawdown')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Price' }))
  expect(await screen.findByRole('heading', { name: 'Market context unavailable' })).toBeInTheDocument()
  expect(client.marketContext).toHaveBeenCalledWith(project.project_id, 7, null, expect.any(AbortSignal))
  fireEvent.click(screen.getByRole('button', { name: 'Results' }))
  expect(screen.getByText('Net equity and close-to-close drawdown')).toBeInTheDocument()
})

it('keeps pending runs truthful and refreshes their chart after a run refresh', async () => {
  const client = api()
  vi.mocked(client.visualization).mockResolvedValue({ schema: 'strategy-os-backtest-visualization/1', state: 'PENDING' })
  render(<ResearchWorkspace api={client} project={project} graph={graph} onPublished={vi.fn()} backtestEnabled={false} reviewEnabled={false} />)
  fireEvent.click(screen.getByRole('button', { name: 'Build' }))
  fireEvent.click(await screen.findByRole('button', { name: 'Run 7 Version 2 · completed' }))
  expect(await screen.findByText(/This run is still being prepared/)).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Open Backtest' })).not.toBeInTheDocument()
  vi.mocked(client.visualization).mockResolvedValue(visualization)
  fireEvent.click(screen.getByRole('button', { name: 'Refresh runs' }))
  expect(await screen.findByText('Net equity and close-to-close drawdown')).toBeInTheDocument()
})

async function studioWatchlistClient() {
  const client = api()
  const original = (await client.researchDatasets(project.project_id, new AbortController().signal))[0]
  const equity = { ...original, instrument_display_name: 'RELIANCE' }
  const index = { ...equity, manifest_address: address('3'), instrument_address: address('4'), instrument_display_name: 'NIFTY 50', asset_class: 'INDEX', backtest_eligibility: 'UNAVAILABLE' as const, research_compatibility: 'BENCHMARK_INPUT_ONLY' as const }
  const scope: StaticScope = { scope_id: 'scope.studio', name: 'Research list', status: 'active', current_revision: 1, address: address('5'), membership_address: address('6'),
    member_labels: [index.instrument_address, address('7'), equity.instrument_address].map((instrument_address) => ({ instrument_address, display_name: null })),
    snapshot: { schema: 'static-instrument-scope/1', owner_id: 'owner.a', project_id: project.project_id, scope_id: 'scope.studio', revision: 1, predecessor: null, members: [index.instrument_address, address('7'), equity.instrument_address] } }
  vi.mocked(client.researchDatasets).mockClear().mockResolvedValue([equity, index])
  client.staticScopes = vi.fn().mockResolvedValue({ items: [scope], next_cursor: null })
  client.staticScope = vi.fn().mockResolvedValue(scope)
  return { client, equity, index, scope }
}

async function openStudioWatchlists(client: StrategyApi, chosenGraph = graph, backtestEnabled = true) {
  const view = render(<ResearchWorkspace api={client} project={project} graph={chosenGraph} onPublished={vi.fn()} backtestEnabled={backtestEnabled} reviewEnabled />)
  if (chosenGraph.current_version !== null) fireEvent.click(screen.getByRole('button', { name: 'Build' }))
  expect(await screen.findByRole('heading', { name: 'Build strategy' })).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Watchlists' }))
  return view
}

it('opens one real watchlist member through the existing verified Backtest context without running it', async () => {
  const { client, scope, equity } = await studioWatchlistClient()
  await openStudioWatchlists(client)
  expect(client.staticScopes).toHaveBeenCalledWith(project.project_id, null, false, expect.any(AbortSignal))
  await chooseSelect('Saved watchlist', scope.scope_id)
  fireEvent.click(screen.getByRole('button', { name: 'RELIANCE' }))
  expect(screen.getByRole('button', { name: 'Open member Backtest' })).toBeDisabled()
  await chooseSelect('Member history', equity.manifest_address)
  fireEvent.click(screen.getByRole('button', { name: 'Open member Backtest' }))
  expect(await screen.findByText(/Opened from Research list, revision 1/)).toBeInTheDocument()
  expect(client.staticScope).toHaveBeenCalledWith(project.project_id, scope.scope_id, 1, expect.any(AbortSignal))
  fireEvent.keyDown(await screen.findByRole('combobox', { name: 'Historical dataset' }), { key: 'ArrowDown' })
  const historyMenu = await screen.findByRole('listbox')
  await waitFor(() => expect(historyMenu.querySelector('[data-state=checked]')).toHaveAttribute('data-value', equity.manifest_address))
  fireEvent.keyDown(historyMenu, { key: 'Escape' })
  expect(client.prepareResearchFromSettings).not.toHaveBeenCalled()
})

it('explains benchmark and missing-history members and retains staged graph edits across list views', async () => {
  const { client, scope, index } = await studioWatchlistClient()
  await openStudioWatchlists(client)
  fireEvent.change(await selectLength(), { target: { value: '37' } }); fireEvent.blur(screen.getByLabelText('Length'))
  await chooseSelect('Saved watchlist', scope.scope_id)
  expect(screen.getByRole('button', { name: 'Instrument name unavailable' })).toBeDisabled()
  expect(screen.getByText('No owned history available.')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'NIFTY 50' }))
  await chooseSelect('Member history', index.manifest_address)
  expect(screen.getByText(/This index is a benchmark input/)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Open member Backtest' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: 'Maximize watchlists pane' }))
  fireEvent.click(screen.getByRole('button', { name: 'Restore watchlists pane' }))
  fireEvent.click(screen.getByRole('button', { name: 'Runs' }))
  expect(screen.getByLabelText('Length')).toHaveValue('37')
})

it('shows unsupported watchlists without reading datasets and retries a failed read', async () => {
  const { client, scope } = await studioWatchlistClient()
  vi.mocked(client.staticScopes).mockRejectedValueOnce(new ApiError('manifest', 'Unavailable')).mockResolvedValue({ items: [scope], next_cursor: null })
  await openStudioWatchlists(client)
  expect(await screen.findByText('Static watchlists are not available in this server release.')).toBeInTheDocument()
  expect(client.researchDatasets).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
  expect(await screen.findByLabelText('Saved watchlist')).toBeInTheDocument()
})

it('paginates watchlists and clears member context when changing pages', async () => {
  const { client, scope, equity } = await studioWatchlistClient()
  const next: StaticScope = { ...scope, scope_id: 'scope.z', name: 'Second list', address: address('8'), snapshot: { ...scope.snapshot, scope_id: 'scope.z' } }
  const firstPage = [scope, ...Array.from({ length: 49 }, (_, index) => ({ ...scope, scope_id: `scope.y${String(index).padStart(2, '0')}`, name: `Saved list ${index + 1}` }))]
  const cursor = firstPage.at(-1)!.scope_id
  vi.mocked(client.staticScopes).mockResolvedValueOnce({ items: firstPage, next_cursor: cursor }).mockResolvedValueOnce({ items: [next], next_cursor: null }).mockResolvedValue({ items: firstPage, next_cursor: cursor })
  await openStudioWatchlists(client)
  await chooseSelect('Saved watchlist', scope.scope_id)
  fireEvent.click(screen.getByRole('button', { name: 'RELIANCE' })); await chooseSelect('Member history', equity.manifest_address)
  fireEvent.click(screen.getByRole('button', { name: 'Next watchlists' }))
  await waitFor(() => expect(client.staticScopes).toHaveBeenLastCalledWith(project.project_id, cursor, false, expect.any(AbortSignal)))
  const nextMenu = await watchlistMenu(); expect(screen.getByRole('option', { name: 'Second list · 3 members' })).toBeInTheDocument(); fireEvent.keyDown(nextMenu, { key: 'Escape' })
  expect(screen.queryByLabelText('Member history')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Previous watchlists' }))
  await watchlistMenu(); expect(screen.getByRole('option', { name: 'Research list · 3 members' })).toBeInTheDocument()
})

it('keeps a late response from a replaced client out of the watchlist pane', async () => {
  const previous = await studioWatchlistClient(), next = await studioWatchlistClient()
  let resolve: (value: { items: StaticScope[]; next_cursor: null }) => void = () => {}
  vi.mocked(previous.client.staticScopes).mockImplementationOnce(() => new Promise((done) => { resolve = done }))
  vi.mocked(next.client.staticScopes).mockResolvedValue({ items: [{ ...next.scope, name: 'Current list' }], next_cursor: null })
  const view = await openStudioWatchlists(previous.client)
  view.rerender(<ResearchWorkspace api={next.client} project={project} graph={graph} onPublished={vi.fn()} backtestEnabled reviewEnabled />)
  await watchlistMenu(); expect(screen.getByRole('option', { name: 'Current list · 3 members' })).toBeInTheDocument()
  await act(async () => { resolve({ items: [{ ...previous.scope, name: 'Previous list' }], next_cursor: null }) })
  expect(screen.getByRole('option', { name: 'Current list · 3 members' })).toBeInTheDocument()
  expect(screen.queryByRole('option', { name: /Previous list/ })).not.toBeInTheDocument()
})

it('requires the exact saved watchlist revision again before enabling the member research setup', async () => {
  const { client, scope, equity } = await studioWatchlistClient()
  vi.mocked(client.staticScope).mockResolvedValue({ ...scope, address: address('9') })
  await openStudioWatchlists(client)
  await chooseSelect('Saved watchlist', scope.scope_id)
  fireEvent.click(screen.getByRole('button', { name: 'RELIANCE' }))
  await chooseSelect('Member history', equity.manifest_address)
  fireEvent.click(screen.getByRole('button', { name: 'Open member Backtest' }))
  expect(await screen.findByText(/selected watchlist revision, member or history could not be verified/)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Run version 2' })).toBeDisabled()
  expect(client.prepareResearchFromSettings).not.toHaveBeenCalled()
})

it.each(['unavailable history', 'unsaved strategy', 'disabled backtest'])('explains %s before a member can open a primary backtest', async (refusal) => {
  const { client, scope, equity } = await studioWatchlistClient()
  if (refusal === 'unsaved strategy') vi.mocked(client.v2Draft).mockResolvedValue({ ...v2Draft, current_version: null, published_revision: null, document: { ...v2Draft.document, strategy_version: 1 } })
  if (refusal === 'unavailable history') vi.mocked(client.researchDatasets).mockResolvedValue([{ ...equity, backtest_eligibility: 'UNAVAILABLE' }])
  await openStudioWatchlists(client, refusal === 'unsaved strategy' ? { ...graph, current_version: null } : graph, refusal !== 'disabled backtest')
  await chooseSelect('Saved watchlist', scope.scope_id)
  fireEvent.click(screen.getByRole('button', { name: 'RELIANCE' }))
  await chooseSelect('Member history', equity.manifest_address)
  expect(screen.getByRole('button', { name: 'Open member Backtest' })).toBeDisabled()
  const reason = refusal === 'unavailable history' ? /This history is unavailable for a primary backtest/ : refusal === 'unsaved strategy' ? /Save a strategy version in Build/ : /Backtesting is unavailable in this server release/
  expect(screen.getByText(reason)).toBeInTheDocument()
})

it('keeps a Backtest link within the enabled capability and opens Build links for saved versions', async () => {
  const client = api()
  const view = render(<ResearchWorkspace api={client} project={project} graph={graph} initialView="backtest"
    backtestEnabled={false} reviewEnabled={true} onPublished={vi.fn()} />)
  expect(screen.getByRole('button', { name: 'Overview' })).toHaveAttribute('aria-current', 'page')
  expect(screen.queryByRole('button', { name: 'Backtest' })).not.toBeInTheDocument()
  expect(client.prepareResearchFromSettings).not.toHaveBeenCalled()
  view.rerender(<ResearchWorkspace api={client} project={project} graph={graph} initialView="build"
    backtestEnabled={false} reviewEnabled={true} onPublished={vi.fn()} />)
  await waitFor(() => expect(screen.getByRole('button', { name: 'Build' })).toHaveAttribute('aria-current', 'page'))
})


it('shows unresolved provider instruments in Studio without borrowing a matching dataset hash', async () => {
  const { client, equity } = await studioWatchlistClient()
  const selectionAddress = address('9')
  const member = { kind: 'PROVIDER_REFERENCE' as const, selection_address: selectionAddress }
  const scope: StaticScope = { scope_id: 'scope.provider', name: 'Any provider instrument', status: 'active', current_revision: 1,
    address: address('a'), membership_address: address('b'),
    snapshot: { schema: 'static-instrument-scope/2', owner_id: 'owner.a', project_id: project.project_id, scope_id: 'scope.provider', revision: 1, predecessor: null, members: [member] },
    member_labels: [{ member, display_name: 'UNKNOWN FUT · MCX · 2026-12-30', observed_at: '2026-09-06T06:00:00+00:00',
      provider_reference: { token: 77, symbol: 'UNKNOWN_FUT', name: 'Unmapped provider future', exchange: 'MCX', segment: 'MCX-FUT', instrument_type: 'FUT', expiry: '2026-12-30', strike: '0', lot_size: '100', tick_size: '0.05' } }] }
  vi.mocked(client.staticScopes).mockResolvedValue({ items: [scope], next_cursor: null })
  vi.mocked(client.researchDatasets).mockResolvedValue([{ ...equity, instrument_address: selectionAddress }])
  await openStudioWatchlists(client); await chooseSelect('Saved watchlist', scope.scope_id)
  fireEvent.click(screen.getByRole('button', { name: 'UNKNOWN FUT · MCX · 2026-12-30' }))
  expect(screen.getByText(/This instrument is saved. Backtests need verified instrument details/)).toBeInTheDocument()
  expect(screen.getByText(/Saved instrument · Not ready for research/)).toHaveTextContent('MCX-FUT')
  expect(screen.getByRole('button', { name: 'Open member Backtest' })).toBeDisabled()
  expect(screen.getByRole('combobox', { name: 'Member history' })).toHaveTextContent('Choose historical data')
  expect(client.prepareResearchFromSettings).not.toHaveBeenCalled()
})
