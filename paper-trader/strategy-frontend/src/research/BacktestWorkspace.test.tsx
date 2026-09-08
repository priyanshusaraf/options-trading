import { chooseSelect } from '../test/select'
import type { StaticScope, StaticScopeMemberContext } from '../features/static-scopes/staticScopeContracts'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { ApiError, type StrategyApi } from '../shell/api'
import type { GraphSummary, Project } from '../shell/contracts'
import { BacktestWorkspace } from './BacktestWorkspace'
import { ResearchWorkspace } from './ResearchWorkspace'
import { parseResearchRecovery } from './preparedResearchContracts'

vi.mock('./CanonicalOptimizationResults', () => ({ CanonicalOptimizationResults: ({ runId, onPublished }: { runId: number; onPublished?: (version: unknown) => void }) => <div data-testid="search-result-run">{runId}{onPublished && <button onClick={() => onPublished({ project_id: 'project.a', identifier: 'strategy.a', version: 2, content_address: `sha256:${'c'.repeat(64)}` })}>Accept verified test suggestion</button>}</div> }))

const project: Project = { project_id: 'project.a', name: 'A', description: '', status: 'active' }
const graph: GraphSummary = { identifier: 'strategy.a', display_name: 'A', draft_revision: 1, current_version: 1 }
const savedVersion = { format_version: 2, graph_identifier: graph.identifier, graph_version: 1,
  content_address: `sha256:${'b'.repeat(64)}`, document: { format_version: 2, strategy_id: graph.identifier, metadata: { tags: [] }, graph_inputs: [{ port_id: 'frame', direction: 'input', semantic_role: 'market_frame' }] } }
const settingsValues = { research_capital: 100000, seed: 0, min_trades: 10, n_folds: 4, min_positive_fold_frac: .6, risk_policy: 'none' as const }
const settingsPreview = { workspace: { owner_id: 'owner.a', graph_identifier: null, revision: 1, enabled: true, values: settingsValues, content_address: `sha256:${'1'.repeat(64)}` },
  strategy: { owner_id: 'owner.a', graph_identifier: graph.identifier, revision: 0, enabled: true, values: {}, content_address: `sha256:${'2'.repeat(64)}` }, values: settingsValues, sources: {} }
const operationId = 'd'.repeat(64)
const receipt = { request_id: 'request', operation_id: operationId, status: 'pending' }
function operation(status: string, completed_run_ids: number[] = []) {
  return { operation_id: operationId, status, stage: 'experiments', completed_run_ids, cancel_requested: false, error: null }
}
afterEach(() => { cleanup(); vi.useRealTimers() })

it('shows truthful empty dataset and pending run states without stale numbers', async () => {
  const api = { researchRecovery: vi.fn().mockResolvedValue({ complete: true, requests: [] }), strategyResearchSettings: vi.fn().mockResolvedValue(settingsPreview), v2Version: vi.fn().mockResolvedValue(savedVersion), researchDatasets: vi.fn().mockResolvedValue([]), experiments: vi.fn().mockResolvedValue({ runs: [{ run_id: 4, spec_id: 'a'.repeat(32), status: 'running', decision: null, evidence_state: 'running', graph: { project_id: project.project_id, identifier: graph.identifier, version: 1, content_address: `sha256:${'b'.repeat(64)}` }, dataset_bindings: [], contract: null }] }), visualization: vi.fn().mockResolvedValue({ schema: 'strategy-os-backtest-visualization/1', state: 'PENDING', status: 'running' }) } as unknown as StrategyApi
  render(<BacktestWorkspace api={api} project={project} graph={graph} />)
  expect(await screen.findByRole('heading', { name: 'No dataset is ready for backtesting' })).toBeInTheDocument(); expect(await screen.findByRole('heading', { name: 'Research is pending' })).toBeInTheDocument()
  expect(screen.queryByText(/Net return|INR 0/)).not.toBeInTheDocument()
})

it('pages trades, keeps trader facts without internal records, and refuses incomparable overlays', async () => {
  const run = (id: number) => ({ run_id: id, spec_id: String(id).repeat(32), status: 'completed', decision: 'archive', evidence_state: 'verified',
    graph: { project_id: project.project_id, identifier: graph.identifier, version: 1, content_address: `sha256:${'b'.repeat(64)}` }, dataset_bindings: [], contract: null })
  const trade = (cursor: number) => ({ cursor, direction: 'LONG', entry_time: cursor, entry_price: 100, exit_time: cursor + 1, exit_price: 101,
    quantity: 1, gross_pnl: 10, charges: 1, net_pnl: 9, return_pct: 9, mae_pct: 1, bars_held: 2, exit_reason: 'STRATEGY_EXIT', open_at_end: false })
  const base = { schema: 'strategy-os-backtest-visualization/1', state: 'AVAILABLE', visualization_address: `sha256:${'c'.repeat(64)}`,
    identity: { terminal_evidence_address: `sha256:${'d'.repeat(64)}`, graph_content_address: `sha256:${'b'.repeat(64)}`,
      component_registry_address: `sha256:${'e'.repeat(64)}`, seed: 7, calculation_schema: 'canonical-calculation/1', dataset_bindings: { canonical_bindings: { role: 'dataset' } }, charge_model: { id: 'schedule' } },
    summary: { net_return_pct: 1, max_close_to_close_drawdown_pct: 2, trades: 2 }, series: { net_equity: { points: [{ time: 1, value: 100 }, { time: 3, value: 118 }], original_count: 2 },
      drawdown: { points: [{ time: 1, value: 0, absolute: 0 }, { time: 3, value: 0, absolute: 0 }], original_count: 2 }, benchmark: { state: 'UNAVAILABLE' },
      trade_events: [{ cursor: 1, event_kind: 'ENTRY', time: 1, direction: 'LONG' }, { cursor: 1, event_kind: 'EXIT', time: 2, direction: 'LONG' }] },
    costs: { charges_total: 2, breakdown: { reason_code: 'UNAVAILABLE' }, slippage: { bps: 5, multiplier: 2, mean_stressed_net: 8, passed: true } },
    folds: [{ fold_index: 0, role: 'OOS', start_time: 1, end_time: 3, bars: 10, oos_trades: 2, oos_net_pnl: 18, oos_return_pct: 1,
      oos_expectancy: 9, oos_max_drawdown_pct: 2, selected_parameter_address: `sha256:${'f'.repeat(64)}`, gate_results: { min_oos_trades: { passed: true, value: 2 }, slippage_stress_2x: { passed: false, value: .5 } } }],
    provenance: { graph: { identifier: graph.identifier }, canonical_dataset_bindings: { role: 'dataset' }, resolved_charge_schedule: { id: 'schedule' }, versions: ['q', 'o', 'v', 's'] } }
  const page1 = { ...base, trade_page: { items: [trade(1)], next_cursor: 1, total: 2, detail_reason: null } }
  const page2 = { ...base, trade_page: { items: [trade(2)], next_cursor: null, total: 2, detail_reason: null } }
  const visualization = vi.fn().mockResolvedValueOnce(page1).mockResolvedValueOnce(page2).mockResolvedValue(page1)
  const compareVersions = vi.fn().mockResolvedValue({ equivalent: false, incomparable: ['COST_ASSUMPTIONS_CHANGED'], differences: [] })
  const api = { researchRecovery: vi.fn().mockResolvedValue({ complete: true, requests: [] }), strategyResearchSettings: vi.fn().mockResolvedValue(settingsPreview), v2Version: vi.fn().mockResolvedValue(savedVersion), researchDatasets: vi.fn().mockResolvedValue([]), experiments: vi.fn().mockResolvedValue({ runs: [run(1), run(2)] }), visualization, compareVersions } as unknown as StrategyApi
  const { container } = render(<BacktestWorkspace api={api} project={project} graph={graph} />)
  expect(await screen.findByRole('heading', { name: 'Net equity and close-to-close drawdown' })).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Trades' })); fireEvent.click(screen.getByRole('button', { name: 'Load next trades after 1' }))
  expect(await screen.findByText('2 of 2 persisted trades loaded.')).toBeInTheDocument(); expect(visualization).toHaveBeenCalledWith(project.project_id, 1, 1, expect.any(AbortSignal))
  fireEvent.click(screen.getByRole('button', { name: 'Costs' })); expect(screen.getByRole('heading', { name: 'Trading costs' })).toBeInTheDocument(); expect(screen.getByText('INR 2.00', { selector: 'dd' })).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'OOS' })); expect(screen.getByText('0 · OOS')).toBeInTheDocument(); expect(screen.getByText('Minimum out-of-sample trades: Passed · 2')).toBeInTheDocument(); expect(screen.getByText('Double-slippage check: Failed · 0.5')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Provenance' })).not.toBeInTheDocument()
  expect(container.querySelector('.backtest-results pre, .backtest-results code, .dataset-facts code, [aria-label="Run selector"] code')).toBeNull()
  expect(container.textContent).not.toMatch(/sha256:|component registry|terminal evidence|producer provenance|"role":|"id":/i)
  fireEvent.click(screen.getByRole('button', { name: 'Compare' })); await chooseSelect('Second run', '2'); fireEvent.click(screen.getByRole('button', { name: 'Check and compare' }))
  expect(await screen.findByRole('heading', { name: 'Runs are incomparable' })).toBeInTheDocument(); expect(screen.getByText('These runs use different trading costs.')).toBeInTheDocument(); expect(container.textContent).not.toMatch(/canonical/i); expect(visualization).toHaveBeenCalledTimes(2)
  vi.mocked(compareVersions).mockResolvedValueOnce({ equivalent: true, incomparable: [], differences: [] }); fireEvent.click(screen.getByRole('button', { name: 'Check and compare' }))
  await waitFor(() => expect(visualization).toHaveBeenCalledTimes(3)); expect(await screen.findByText(/DASHED run 2/)).toBeInTheDocument()
  await chooseSelect('Second run', '')
  expect(screen.getByRole('button', { name: 'Check and compare' })).toBeDisabled()
  expect(screen.queryByText(/DASHED run 2/)).not.toBeInTheDocument()
})

const dataset = { manifest_address: `sha256:${'a'.repeat(64)}`, as_of: '2026-01-31T00:00:00Z', canonical_instrument_label: 'NIFTY 50', interval: '1d', bar_count: 5000, event_start: '2020-01-01', event_end: '2025-12-31', backtest_eligibility: 'ELIGIBLE_Q03', refusal_code: null }

it('submits only supported preparation inputs and polls until a real run completes', async () => {
  vi.useFakeTimers()
  const prepareResearchFromSettings = vi.fn().mockResolvedValue(receipt)
  const researchOperation = vi.fn().mockResolvedValueOnce({ ...operation('pending'), settingsSnapshotAddress: `sha256:${'f'.repeat(64)}` }).mockResolvedValueOnce(operation('running')).mockResolvedValueOnce(operation('completed', [9]))
  const visualization = vi.fn().mockResolvedValue({ schema: 'strategy-os-backtest-visualization/1', state: 'PENDING', status: 'running' })
  const api = { researchRecovery: vi.fn().mockResolvedValue({ complete: true, requests: [] }), strategyResearchSettings: vi.fn().mockResolvedValue(settingsPreview), v2Version: vi.fn().mockResolvedValue(savedVersion), researchDatasets: vi.fn().mockResolvedValue([dataset]), experiments: vi.fn().mockResolvedValue({ runs: [] }), prepareResearchFromSettings, researchOperation, visualization } as unknown as StrategyApi
  render(<BacktestWorkspace api={api} project={project} graph={graph} />)
  await act(async () => {})
  expect(screen.getByLabelText('Walk-forward folds')).toHaveValue(4)
  expect(screen.queryByLabelText('Slippage per side (basis points)')).not.toBeInTheDocument()
  expect(screen.queryByLabelText('Optimize parameters inside each walk-forward fold')).not.toBeInTheDocument()
  expect(screen.getByText(/Choose bounded development search below/)).toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('Research capital (INR)'), { target: { value: '250000' } })
  fireEvent.change(screen.getByLabelText('Walk-forward folds'), { target: { value: '8' } })
  fireEvent.change(screen.getByLabelText('Minimum out-of-sample trades'), { target: { value: '25' } })
  fireEvent.change(screen.getByLabelText('Minimum profitable folds (%)'), { target: { value: '75' } })
  fireEvent.change(screen.getByLabelText('Reproducibility seed'), { target: { value: '42' } })
  fireEvent.click(screen.getByRole('button', { name: 'Run version 1' }))
  await act(async () => {})
  expect(screen.getByText('Research queued. The worker has not started.')).toBeInTheDocument()
  expect(screen.getByRole('combobox', { name: 'Research risk policy' })).toBeDisabled()
  fireEvent.keyDown(screen.getByRole('combobox', { name: 'Research risk policy' }), { key: 'ArrowDown' })
  expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  expect(visualization).not.toHaveBeenCalled()
  expect(prepareResearchFromSettings).toHaveBeenCalledWith(project.project_id, graph.identifier, 1, {
    request_id: expect.stringMatching(/^[0-9a-f-]{36}$/), dataset_manifest_address: dataset.manifest_address, dataset_as_of: dataset.as_of,
    hypothesis: 'Test the saved strategy on historical data.', expected_workspace_revision: 1, expected_strategy_revision: 0,
    run_overrides: { research_capital: 250000, seed: 42, min_trades: 25, n_folds: 8, min_positive_fold_frac: .75 },
  }, expect.any(AbortSignal))
  await act(async () => { await vi.advanceTimersByTimeAsync(1000) })
  expect(screen.getByText(/Research running/)).toBeInTheDocument(); expect(visualization).not.toHaveBeenCalled()
  expect(researchOperation.mock.calls[1][1].settings.snapshotAddress).toBe(`sha256:${'f'.repeat(64)}`)
  await act(async () => { await vi.advanceTimersByTimeAsync(1000) })
  expect(screen.getByText('Backtest run 9 completed. Loading its persisted result.')).toBeInTheDocument()
  expect(visualization).toHaveBeenCalledWith(project.project_id, 9, 0, expect.any(AbortSignal))
  const originalId = prepareResearchFromSettings.mock.calls[0][3].request_id
  fireEvent.click(screen.getByRole('button', { name: 'Review same-data rerun' }))
  await act(async () => {})
  expect(screen.getByLabelText('Historical dataset')).toBeDisabled()
  expect(prepareResearchFromSettings).toHaveBeenCalledTimes(1)
  expect(screen.getByLabelText('Research capital (INR)')).toHaveValue(settingsPreview.values.research_capital)
  fireEvent.click(screen.getByRole('button', { name: 'Run version 1' }))
  await act(async () => {})
  expect(prepareResearchFromSettings).toHaveBeenCalledTimes(2)
  const rerun = prepareResearchFromSettings.mock.calls[1][3]
  expect(rerun.request_id).not.toBe(originalId)
  expect(rerun.dataset_manifest_address).toBe(dataset.manifest_address)
  expect(rerun.dataset_as_of).toBe(dataset.as_of)
})

it('blocks invalid bounds with associated errors and keeps technical language out of routine copy', async () => {
  const prepareResearchFromSettings = vi.fn(); const api = { researchRecovery: vi.fn().mockResolvedValue({ complete: true, requests: [] }), strategyResearchSettings: vi.fn().mockResolvedValue(settingsPreview), v2Version: vi.fn().mockResolvedValue(savedVersion), researchDatasets: vi.fn().mockResolvedValue([dataset]), experiments: vi.fn().mockResolvedValue({ runs: [] }), prepareResearchFromSettings } as unknown as StrategyApi
  const { container } = render(<BacktestWorkspace api={api} project={project} graph={graph} />); await waitFor(() => expect(screen.getByRole('button', { name: 'Run version 1' })).toBeEnabled()); fireEvent.change(screen.getByLabelText('Walk-forward folds'), { target: { value: '33' } }); fireEvent.click(screen.getByRole('button', { name: 'Run version 1' })); expect(await screen.findByText('Enter a whole number from 2 to 32.')).toHaveAttribute('id', 'folds-error'); expect(screen.getByRole('spinbutton', { name: /Walk-forward folds/ })).toHaveAttribute('aria-describedby', 'folds-error'); expect(prepareResearchFromSettings).not.toHaveBeenCalled()
  const routineText = [...container.querySelectorAll('*')].filter((element) => !element.closest('details')).map((element) => element.childNodes.length === 1 ? element.textContent ?? '' : '').join(' '); expect(routineText).not.toMatch(/canonical|Q03|sha256|revision/i)
})

it('opens Market context for the selected verified saved run through the sole API', async () => {
  const run = { run_id: 4, spec_id: 'a'.repeat(32), status: 'completed', decision: 'archive', evidence_state: 'verified', graph: { project_id: project.project_id, identifier: graph.identifier, version: 1, content_address: `sha256:${'b'.repeat(64)}` }, dataset_bindings: [], contract: null }
  const visualization = { schema: 'strategy-os-backtest-visualization/1', state: 'AVAILABLE', visualization_address: `sha256:${'c'.repeat(64)}`, identity: { terminal_evidence_address: `sha256:${'d'.repeat(64)}` }, summary: { net_return_pct: 1, max_close_to_close_drawdown_pct: 1, trades: 0 }, series: { net_equity: { points: [{ time: 1, value: 1 }], original_count: 1 }, drawdown: { points: [{ time: 1, value: 0, absolute: 0 }], original_count: 1 }, benchmark: {}, trade_events: [] }, trade_page: { items: [], next_cursor: null, total: 0, detail_reason: null }, costs: { charges_total: 0, breakdown: {}, slippage: {} }, folds: [], provenance: {} }
  const marketContext = vi.fn().mockResolvedValue({ schema: 'strategy-os-market-context/1', state: 'EMPTY', market_context_address: `sha256:${'e'.repeat(64)}`, bars: [] })
  const api = { researchRecovery: vi.fn().mockResolvedValue({ complete: true, requests: [] }), strategyResearchSettings: vi.fn().mockResolvedValue(settingsPreview), v2Version: vi.fn().mockResolvedValue(savedVersion), researchDatasets: vi.fn().mockResolvedValue([]), experiments: vi.fn().mockResolvedValue({ runs: [run] }), visualization: vi.fn().mockResolvedValue(visualization), marketContext, chartAnnotations: vi.fn().mockResolvedValue([]) } as unknown as StrategyApi
  render(<BacktestWorkspace api={api} project={project} graph={graph} />)
  fireEvent.click(await screen.findByRole('button', { name: 'Market context' }))
  expect(await screen.findByRole('heading', { name: 'No verified candles are linked to this result' })).toBeInTheDocument()
  expect(marketContext).toHaveBeenCalledWith(project.project_id, 4, null, expect.any(AbortSignal))
})


it('refreshes imported history and explains index and volume limits before a run', async () => {
  const index = { ...dataset, fields: ['OPEN', 'HIGH', 'LOW', 'CLOSE'], source_type: 'USER_SUPPLIED',
    backtest_eligibility: 'UNAVAILABLE', research_compatibility: 'BENCHMARK_INPUT_ONLY' }
  const inspection = { schema: 'strategy-os-user-csv-inspection/1', source_type: 'USER_SUPPLIED', source_sha256: 'd'.repeat(64), byte_count: 100,
    row_count: 248, source_order: 'DESCENDING', fields: ['OPEN', 'HIGH', 'LOW', 'CLOSE'], interval: 'day', event_start: '2025-09-04T18:30:00Z', event_end: '2026-09-03T18:30:00Z',
    historical_source_availability: 'NOT_SUPPLIED', calendar_coverage: 'NOT_ASSERTED', rights_scope: 'PERSONAL_RESEARCH_ONLY' }
  const researchDatasets = vi.fn().mockResolvedValueOnce([]).mockResolvedValue([index])
  const importDailyCsv = vi.fn().mockResolvedValue({ ...inspection, schema: 'strategy-os-user-csv-import/1', project_id: project.project_id,
    manifest_address: dataset.manifest_address, instrument_address: `sha256:${'b'.repeat(64)}`, imported_at: '2026-09-05T00:00:00Z', ready_as_of: '2026-09-05T00:00:00Z' })
  const prepareResearchFromSettings = vi.fn()
  const api = { researchRecovery: vi.fn().mockResolvedValue({ complete: true, requests: [] }), strategyResearchSettings: vi.fn().mockResolvedValue(settingsPreview), v2Version: vi.fn().mockResolvedValue(savedVersion), researchDatasets, experiments: vi.fn().mockResolvedValue({ runs: [] }), inspectDailyCsv: vi.fn().mockResolvedValue(inspection), importDailyCsv, prepareResearchFromSettings } as unknown as StrategyApi
  render(<BacktestWorkspace api={api} project={project} graph={graph} />)
  await screen.findByRole('heading', { name: 'No dataset is ready for backtesting' })
  fireEvent.click(screen.getByText('Import daily CSV', { selector: 'summary' }))
  fireEvent.change(screen.getByLabelText('CSV file'), { target: { files: [new File(['Date,Open,High,Low,Close'], 'nifty.csv')] } })
  fireEvent.click(screen.getByRole('button', { name: 'Inspect CSV' }))
  fireEvent.click(await screen.findByRole('button', { name: 'Import inspected CSV' }))
  await waitFor(() => expect(researchDatasets).toHaveBeenCalledTimes(2))
  expect(await screen.findByText('Volume is absent. Rules that require volume need a different dataset.')).toBeInTheDocument()
  expect(screen.getByText(/cross-instrument strategy binding is not yet available/)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Run version 1' })).toBeDisabled()
  expect(prepareResearchFromSettings).not.toHaveBeenCalled()
  expect(importDailyCsv).toHaveBeenCalledWith(project.project_id, expect.any(File), expect.objectContaining({ columns: expect.objectContaining({ volume: null }) }), expect.any(AbortSignal), undefined)
})


it('reuses the request UUID after uncertain POST failure and sends the explicitly chosen risk policy', async () => {
  const { ApiError } = await import('../shell/api')
  const prepareResearchFromSettings = vi.fn().mockRejectedValueOnce(new ApiError('network', 'offline')).mockResolvedValue(receipt)
  const api = { researchRecovery: vi.fn().mockResolvedValue({ complete: true, requests: [] }), strategyResearchSettings: vi.fn().mockResolvedValue(settingsPreview), v2Version: vi.fn().mockResolvedValue({ ...savedVersion, document: { ...savedVersion.document, metadata: { tags: ['expanding-z-v4'] }, graph_inputs: [{ port_id: 'frame', direction: 'input', semantic_role: 'market_frame' }] } }),
    researchDatasets: vi.fn().mockResolvedValue([dataset]), experiments: vi.fn().mockResolvedValue({ runs: [] }), prepareResearchFromSettings,
    researchOperation: vi.fn().mockResolvedValue(operation('failed')) } as unknown as StrategyApi
  render(<BacktestWorkspace api={api} project={project} graph={graph} />)
  await waitFor(() => expect(screen.getByRole('button', { name: 'Run version 1' })).toBeEnabled())
  expect(screen.getByLabelText('Research risk policy')).toHaveTextContent('None — authored signal exits only')
  await chooseSelect('Research risk policy', 'pine-v4-ratchet/1')
  fireEvent.click(screen.getByRole('button', { name: 'Run version 1' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('No request was confirmed')
  fireEvent.click(screen.getByRole('button', { name: 'Run version 1' }))
  await waitFor(() => expect(prepareResearchFromSettings).toHaveBeenCalledTimes(2))
  expect(prepareResearchFromSettings.mock.calls[1][3].request_id).toBe(prepareResearchFromSettings.mock.calls[0][3].request_id)
  expect(prepareResearchFromSettings.mock.calls[1][3].run_overrides.risk_policy).toBe('pine-v4-ratchet/1')
  expect(await screen.findByText(/Research preparation failed/)).toBeInTheDocument()
  await waitFor(() => expect(screen.getByRole('button', { name: 'Run version 1' })).toBeEnabled())
  await chooseSelect('Research risk policy', 'none')
  fireEvent.click(screen.getByRole('button', { name: 'Run version 1' }))
  await waitFor(() => expect(prepareResearchFromSettings).toHaveBeenCalledTimes(3))
  expect(prepareResearchFromSettings.mock.calls[2][3].run_overrides).not.toHaveProperty('risk_policy')
  expect(prepareResearchFromSettings.mock.calls[2][3].request_id).not.toBe(prepareResearchFromSettings.mock.calls[1][3].request_id)
})

it('confirms durable cancellation and ignores an older status response', async () => {
  let resolve!: (value: ReturnType<typeof operation>) => void
  const researchOperation = vi.fn().mockImplementationOnce(() => new Promise((done) => { resolve = done }))
  const cancelResearchOperation = vi.fn().mockResolvedValue(operation('cancelled'))
  const visualization = vi.fn().mockResolvedValue({ schema: 'strategy-os-backtest-visualization/1', state: 'PENDING', status: 'running' })
  const api = { researchRecovery: vi.fn().mockResolvedValue({ complete: true, requests: [] }), strategyResearchSettings: vi.fn().mockResolvedValue(settingsPreview), v2Version: vi.fn().mockResolvedValue(savedVersion), researchDatasets: vi.fn().mockResolvedValue([dataset]),
    experiments: vi.fn().mockResolvedValue({ runs: [] }), prepareResearchFromSettings: vi.fn().mockResolvedValue(receipt), researchOperation, cancelResearchOperation, visualization } as unknown as StrategyApi
  render(<BacktestWorkspace api={api} project={project} graph={graph} />)
  await waitFor(() => expect(screen.getByRole('button', { name: 'Run version 1' })).toBeEnabled())
  fireEvent.click(screen.getByRole('button', { name: 'Run version 1' }))
  await waitFor(() => expect(researchOperation).toHaveBeenCalledOnce())
  fireEvent.click(await screen.findByRole('button', { name: 'Cancel research' }))
  expect(await screen.findByText('Research cancelled. No completed result is being presented.')).toBeInTheDocument()
  expect(researchOperation.mock.calls[0][2].aborted).toBe(true)
  await act(async () => resolve(operation('completed', [91])))
  expect(visualization).not.toHaveBeenCalled(); expect(cancelResearchOperation).toHaveBeenCalledOnce()
})

it('ignores a late preparation receipt after the saved version changes', async () => {
  let resolve!: (value: typeof receipt) => void
  const prepareResearchFromSettings = vi.fn().mockImplementationOnce(() => new Promise((done) => { resolve = done }))
  const researchOperation = vi.fn()
  const api = { researchRecovery: vi.fn().mockResolvedValue({ complete: true, requests: [] }), strategyResearchSettings: vi.fn().mockResolvedValue(settingsPreview), v2Version: vi.fn().mockResolvedValueOnce(savedVersion).mockResolvedValue({ ...savedVersion, graph_version: 2 }),
    researchDatasets: vi.fn().mockResolvedValue([dataset]), experiments: vi.fn().mockResolvedValue({ runs: [] }), prepareResearchFromSettings, researchOperation } as unknown as StrategyApi
  const view = render(<BacktestWorkspace api={api} project={project} graph={graph} />)
  await waitFor(() => expect(screen.getByRole('button', { name: 'Run version 1' })).toBeEnabled())
  fireEvent.click(screen.getByRole('button', { name: 'Run version 1' }))
  view.rerender(<BacktestWorkspace api={api} project={project} graph={{ ...graph, current_version: 2 }} />)
  expect(prepareResearchFromSettings.mock.calls[0][4].aborted).toBe(true)
  await act(async () => resolve(receipt))
  expect(researchOperation).not.toHaveBeenCalled()
  expect(screen.queryByText(/Backtest run/)).not.toBeInTheDocument()
})

it('keeps unknown status pending and retries the same operation', async () => {
  const { ApiError } = await import('../shell/api')
  const researchOperation = vi.fn().mockRejectedValueOnce(new ApiError('network', 'offline')).mockResolvedValueOnce({ ...operation('failed'), error: { code: 'NO_DATA', message: 'The required daily history is missing.' } })
  const prepareResearchFromSettings = vi.fn().mockResolvedValue(receipt)
  const api = { researchRecovery: vi.fn().mockResolvedValue({ complete: true, requests: [] }), strategyResearchSettings: vi.fn().mockResolvedValue(settingsPreview), v2Version: vi.fn().mockResolvedValue(savedVersion), researchDatasets: vi.fn().mockResolvedValue([dataset]), experiments: vi.fn().mockResolvedValue({ runs: [] }), prepareResearchFromSettings, researchOperation } as unknown as StrategyApi
  render(<BacktestWorkspace api={api} project={project} graph={graph} />)
  await waitFor(() => expect(screen.getByRole('button', { name: 'Run version 1' })).toBeEnabled())
  fireEvent.click(screen.getByRole('button', { name: 'Run version 1' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('research status is unknown')
  expect(screen.getByRole('button', { name: 'Running backtest' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: 'Retry status' }))
  expect(await screen.findByText(/The required daily history is missing/)).toBeInTheDocument()
  expect(prepareResearchFromSettings).toHaveBeenCalledOnce(); expect(researchOperation.mock.calls[1][0]).toBe(researchOperation.mock.calls[0][0])
})

it('keeps cancellation failures actionable while polling and waits for confirmed cancellation', async () => {
  const { ApiError } = await import('../shell/api')
  let resolve!: (value: ReturnType<typeof operation>) => void
  const researchOperation = vi.fn().mockResolvedValueOnce(operation('running')).mockResolvedValueOnce(operation('running'))
    .mockImplementationOnce(() => new Promise((done) => { resolve = done }))
  const cancelResearchOperation = vi.fn().mockRejectedValueOnce(new ApiError('network', 'offline'))
    .mockResolvedValueOnce({ ...operation('running'), cancel_requested: true })
  const api = { researchRecovery: vi.fn().mockResolvedValue({ complete: true, requests: [] }), strategyResearchSettings: vi.fn().mockResolvedValue(settingsPreview), v2Version: vi.fn().mockResolvedValue(savedVersion), researchDatasets: vi.fn().mockResolvedValue([dataset]), experiments: vi.fn().mockResolvedValue({ runs: [] }),
    prepareResearchFromSettings: vi.fn().mockResolvedValue(receipt), researchOperation, cancelResearchOperation } as unknown as StrategyApi
  render(<BacktestWorkspace api={api} project={project} graph={graph} />)
  await waitFor(() => expect(screen.getByRole('button', { name: 'Run version 1' })).toBeEnabled())
  fireEvent.click(screen.getByRole('button', { name: 'Run version 1' }))
  fireEvent.click(await screen.findByRole('button', { name: 'Cancel research' }))
  await waitFor(() => expect(researchOperation).toHaveBeenCalledTimes(2))
  expect(await screen.findByRole('alert')).toHaveTextContent('Cancellation was not confirmed')
  fireEvent.click(screen.getByRole('button', { name: 'Cancel research' }))
  expect(await screen.findByText('Cancellation requested. Waiting for the worker to stop.')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Cancel research' })).toBeDisabled()
  await act(async () => resolve(operation('cancelled')))
  expect(await screen.findByText('Research cancelled. No completed result is being presented.')).toBeInTheDocument()
})

it('refuses mismatched saved-version metadata and retries verification before launch', async () => {
  const v2Version = vi.fn().mockResolvedValueOnce({ ...savedVersion, graph_version: 2 }).mockResolvedValueOnce(savedVersion)
  const prepareResearchFromSettings = vi.fn()
  const api = { researchRecovery: vi.fn().mockResolvedValue({ complete: true, requests: [] }), strategyResearchSettings: vi.fn().mockResolvedValue(settingsPreview), v2Version, researchDatasets: vi.fn().mockResolvedValue([dataset]), experiments: vi.fn().mockResolvedValue({ runs: [] }), prepareResearchFromSettings } as unknown as StrategyApi
  render(<BacktestWorkspace api={api} project={project} graph={graph} />)
  expect(await screen.findByRole('alert')).toHaveTextContent('saved version must be verified')
  expect(screen.getByRole('button', { name: 'Run version 1' })).toBeDisabled()
  expect(prepareResearchFromSettings).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Retry saved version' }))
  await waitFor(() => expect(screen.getByRole('button', { name: 'Run version 1' })).toBeEnabled())
})

function raceVisualization(netReturn: number, next: number | null = null) {
  return { schema: 'strategy-os-backtest-visualization/1', state: 'AVAILABLE', visualization_address: `sha256:${'c'.repeat(64)}`,
    identity: { terminal_evidence_address: `sha256:${'d'.repeat(64)}` }, summary: { net_return_pct: netReturn, max_close_to_close_drawdown_pct: 1, trades: 0 },
    series: { net_equity: { points: [{ time: 1, value: 100 }], original_count: 1 }, drawdown: { points: [{ time: 1, value: 0, absolute: 0 }], original_count: 1 }, benchmark: {}, trade_events: [] },
    trade_page: { items: next === null ? [] : [{ cursor: 1, direction: 'LONG', entry_time: 1, exit_time: 2, gross_pnl: 1, charges: 0, net_pnl: 1, mae_pct: 0, exit_reason: 'SIGNAL' }], next_cursor: next, total: 2, detail_reason: 'No trades.' },
    costs: { charges_total: 0, breakdown: {}, slippage: {} }, folds: [], provenance: {} }
}
function raceRuns() {
  return [1, 2, 3].map((id) => ({ run_id: id, spec_id: 'a'.repeat(32), status: 'completed', decision: 'archive', evidence_state: 'verified',
    graph: { project_id: project.project_id, identifier: graph.identifier, version: 1, content_address: `sha256:${'b'.repeat(64)}` }, dataset_bindings: [], contract: null }))
}

it('discards an old trade page after another run is selected', async () => {
  let resolve!: (value: ReturnType<typeof raceVisualization>) => void
  const visualization = vi.fn().mockResolvedValueOnce(raceVisualization(7, 1))
    .mockImplementationOnce(() => new Promise((done) => { resolve = done })).mockResolvedValueOnce(raceVisualization(22))
  const api = { researchRecovery: vi.fn().mockResolvedValue({ complete: true, requests: [] }), strategyResearchSettings: vi.fn().mockResolvedValue(settingsPreview), v2Version: vi.fn().mockResolvedValue(savedVersion), researchDatasets: vi.fn().mockResolvedValue([]), experiments: vi.fn().mockResolvedValue({ runs: raceRuns() }), visualization } as unknown as StrategyApi
  render(<BacktestWorkspace api={api} project={project} graph={graph} />)
  await screen.findByText('7.00%')
  fireEvent.click(screen.getByRole('button', { name: 'Trades' })); fireEvent.click(screen.getByRole('button', { name: 'Load next trades after 1' }))
  await chooseSelect('Selected run', '2')
  await screen.findByText('22.00%')
  await act(async () => resolve(raceVisualization(7)))
  expect(screen.getByText('Net return').parentElement).toHaveTextContent('22.00%')
  expect(visualization.mock.calls[1][3].aborted).toBe(true)
})

it('discards an old comparison after the base run changes', async () => {
  let resolve!: (value: { incomparable: string[] }) => void
  const compareVersions = vi.fn().mockImplementationOnce(() => new Promise((done) => { resolve = done }))
  const visualization = vi.fn().mockResolvedValueOnce(raceVisualization(11)).mockResolvedValueOnce(raceVisualization(33))
  const api = { researchRecovery: vi.fn().mockResolvedValue({ complete: true, requests: [] }), strategyResearchSettings: vi.fn().mockResolvedValue(settingsPreview), v2Version: vi.fn().mockResolvedValue(savedVersion), researchDatasets: vi.fn().mockResolvedValue([]), experiments: vi.fn().mockResolvedValue({ runs: raceRuns() }), visualization, compareVersions } as unknown as StrategyApi
  render(<BacktestWorkspace api={api} project={project} graph={graph} />)
  await screen.findByText('11.00%')
  fireEvent.click(screen.getByRole('button', { name: 'Compare' })); await chooseSelect('Second run', '2'); fireEvent.click(screen.getByRole('button', { name: 'Check and compare' }))
  await chooseSelect('Selected run', '3')
  await screen.findByText('33.00%')
  await act(async () => resolve({ incomparable: ['DATASET_IDENTITY_CHANGED'] }))
  expect(screen.queryByText('These runs use different datasets.')).not.toBeInTheDocument()
  expect(compareVersions.mock.calls[0][6].aborted).toBe(true)
})

it('discards an old comparison result after the comparison target changes', async () => {
  let resolve!: (value: ReturnType<typeof raceVisualization>) => void
  const visualization = vi.fn().mockResolvedValueOnce(raceVisualization(11)).mockImplementationOnce(() => new Promise((done) => { resolve = done }))
  const api = { researchRecovery: vi.fn().mockResolvedValue({ complete: true, requests: [] }), strategyResearchSettings: vi.fn().mockResolvedValue(settingsPreview), v2Version: vi.fn().mockResolvedValue(savedVersion), researchDatasets: vi.fn().mockResolvedValue([]), experiments: vi.fn().mockResolvedValue({ runs: raceRuns() }), visualization,
    compareVersions: vi.fn().mockResolvedValue({ incomparable: [] }) } as unknown as StrategyApi
  render(<BacktestWorkspace api={api} project={project} graph={graph} />)
  await screen.findByText('11.00%')
  fireEvent.click(screen.getByRole('button', { name: 'Compare' })); await chooseSelect('Second run', '2'); fireEvent.click(screen.getByRole('button', { name: 'Check and compare' }))
  await waitFor(() => expect(visualization).toHaveBeenCalledTimes(2))
  await chooseSelect('Second run', '3')
  await act(async () => resolve(raceVisualization(22)))
  expect(screen.queryByText(/DASHED run 3/)).not.toBeInTheDocument()
  expect(visualization.mock.calls[1][3].aborted).toBe(true)
})

const recoveredRequest = { request_id: '12345678-1234-4234-8234-123456789abc', dataset_manifest_address: dataset.manifest_address,
  dataset_as_of: dataset.as_of, hypothesis: 'The saved request hypothesis.', research_capital: 250000, seed: 42,
  min_trades: 25, n_folds: 8, min_positive_fold_frac: .75, risk_policy: 'pine-v4-ratchet/1' as const }
function activeResearch(id = operationId, graphId = graph.identifier) {
  const { request_id, dataset_manifest_address, dataset_as_of, risk_policy, ...experiment } = recoveredRequest
  return { operation_id: id, trigger: 'v2_graph', status: 'running', stage: 'planning', completed_run_ids: [], error: null, cancel_requested_at: null,
    plan: { schema: 'v2-graph-research-operation/2', experiment_count: 1, v2_graphs: [{ project_id: project.project_id, graph_identifier: graphId,
      graph_version: 1, content_address: savedVersion.content_address, request_id, dataset_manifest_address, dataset_as_of,
      experiment, execution_policy: { risk: { risk_policy, capital: experiment.research_capital } } }] } }
}
function recoveryApi(active: ReturnType<typeof activeResearch>[] = [], complete = true) {
  return { strategyResearchSettings: vi.fn().mockResolvedValue(settingsPreview), v2Version: vi.fn().mockResolvedValue(savedVersion), researchDatasets: vi.fn().mockResolvedValue([dataset]),
    experiments: vi.fn().mockResolvedValue({ runs: [] }), prepareResearchFromSettings: vi.fn(), visualization: vi.fn().mockResolvedValue({ state: 'PENDING', status: 'running' }),
    researchRecovery: vi.fn().mockImplementation(async (context) => parseResearchRecovery({ active_operations: active, active_complete: complete }, context)),
    researchOperation: vi.fn().mockImplementation(async (id) => ({ ...operation('running'), operation_id: id })),
    cancelRecoveryOperation: vi.fn().mockResolvedValue({ status: 'cancelled' }),
  }
}

it('restores the exact active request after remount without another POST', async () => {
  const api = recoveryApi([activeResearch()])
  const props = { api: api as unknown as StrategyApi, project, graph }
  const first = render(<BacktestWorkspace {...props} />)
  await screen.findByText(/Research running/)
  expect(screen.getByLabelText('Hypothesis')).toHaveValue(recoveredRequest.hypothesis)
  expect(screen.getByLabelText('Research capital (INR)')).toHaveValue(250000)
  expect(screen.getByLabelText('Walk-forward folds')).toHaveValue(8)
  expect(screen.getByLabelText('Minimum out-of-sample trades')).toHaveValue(25)
  expect(screen.getByLabelText('Reproducibility seed')).toHaveValue(42)
  expect(screen.getByLabelText('Minimum profitable folds (%)')).toHaveValue(75)
  expect(screen.getByLabelText('Research risk policy')).toHaveTextContent('Pine V4 ratchet stops')
  expect(api.strategyResearchSettings).not.toHaveBeenCalled()
  expect(api.researchOperation.mock.calls[0][1].request).toEqual(recoveredRequest)
  first.unmount()
  render(<BacktestWorkspace {...props} />)
  await screen.findByText(/Research running/)
  expect(api.researchOperation.mock.calls[1][0]).toBe(operationId)
  expect(api.prepareResearchFromSettings).not.toHaveBeenCalled()
})

it('requires a complete lookup before a fresh request and does not resume another graph', async () => {
  const api = recoveryApi([activeResearch(operationId, 'another.graph')])
  let resolve!: (value: { complete: boolean; requests: [] }) => void
  api.researchRecovery.mockImplementationOnce(() => new Promise((done) => { resolve = done }))
  render(<BacktestWorkspace api={api as unknown as StrategyApi} project={project} graph={graph} />)
  await screen.findByText(/Checking active research before/)
  expect(screen.getByRole('button', { name: 'Run version 1' })).toBeDisabled()
  await act(async () => resolve({ complete: false, requests: [] }))
  expect(screen.getByText(/active research list is incomplete/)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Run version 1' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: 'Retry active research' }))
  await waitFor(() => expect(screen.getByRole('button', { name: 'Run version 1' })).toBeEnabled())
  expect(api.researchOperation).not.toHaveBeenCalled(); expect(api.prepareResearchFromSettings).not.toHaveBeenCalled()
})

it('requires a choice among matching active requests and preserves both server jobs', async () => {
  const otherId = 'e'.repeat(64), api = recoveryApi([activeResearch(), activeResearch(otherId)])
  render(<BacktestWorkspace api={api as unknown as StrategyApi} project={project} graph={graph} />)
  await screen.findByLabelText('Active research request')
  expect(api.researchOperation).not.toHaveBeenCalled()
  expect(screen.getByRole('button', { name: 'Run version 1' })).toBeDisabled()
  await chooseSelect('Active research request', otherId)
  await waitFor(() => expect(api.researchOperation).toHaveBeenCalled())
  expect(api.researchOperation.mock.calls[0][0]).toBe(otherId)
  expect(api.cancelRecoveryOperation).not.toHaveBeenCalled(); expect(api.prepareResearchFromSettings).not.toHaveBeenCalled()
})

it('keeps an unsupported matching request blocked and cancellable', async () => {
  const unsupported = activeResearch(); unsupported.plan.schema = 'v2-graph-research-operation/1'
  const api = recoveryApi([unsupported])
  render(<BacktestWorkspace api={api as unknown as StrategyApi} project={project} graph={graph} />)
  expect(await screen.findByRole('alert')).toHaveTextContent('active request cannot be verified')
  expect(screen.getByRole('button', { name: 'Run version 1' })).toBeDisabled()
  expect(api.researchOperation).not.toHaveBeenCalled()
  api.researchRecovery.mockResolvedValueOnce({ complete: true, requests: [] })
  fireEvent.click(screen.getByRole('button', { name: 'Cancel unavailable request' }))
  await waitFor(() => expect(screen.getByRole('button', { name: 'Run version 1' })).toBeEnabled())
  expect(api.cancelRecoveryOperation).toHaveBeenCalledWith(operationId, expect.any(AbortSignal))
  expect(api.prepareResearchFromSettings).not.toHaveBeenCalled()
})

it('ignores a recovery response for the previous graph version', async () => {
  const api = recoveryApi()
  let resolve!: (value: ReturnType<typeof parseResearchRecovery>) => void
  api.researchRecovery.mockImplementationOnce(() => new Promise((done) => { resolve = done }))
  const view = render(<BacktestWorkspace api={api as unknown as StrategyApi} project={project} graph={graph} />)
  await screen.findByText(/Checking active research before/)
  api.v2Version.mockResolvedValueOnce({ ...savedVersion, graph_version: 2 })
  view.rerender(<BacktestWorkspace api={api as unknown as StrategyApi} project={project} graph={{ ...graph, current_version: 2 }} />)
  const oldContext = api.researchRecovery.mock.calls[0][0]
  await act(async () => resolve(parseResearchRecovery({ active_operations: [activeResearch()], active_complete: true }, oldContext)))
  expect(api.researchRecovery.mock.calls[0][1].aborted).toBe(true)
  await waitFor(() => expect(screen.getByRole('button', { name: 'Run version 2' })).toBeEnabled())
  expect(api.researchOperation).not.toHaveBeenCalled(); expect(api.prepareResearchFromSettings).not.toHaveBeenCalled()
})

it('blocks a new launch when active research lookup fails and supports retry', async () => {
  const { ApiError } = await import('../shell/api')
  const api = recoveryApi()
  api.researchRecovery.mockRejectedValueOnce(new ApiError('network', 'offline'))
  render(<BacktestWorkspace api={api as unknown as StrategyApi} project={project} graph={graph} />)
  expect(await screen.findByRole('alert')).toHaveTextContent('Active research could not be verified')
  expect(screen.getByRole('button', { name: 'Run version 1' })).toBeDisabled()
  expect(api.prepareResearchFromSettings).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Retry active research' }))
  await waitFor(() => expect(screen.getByRole('button', { name: 'Run version 1' })).toBeEnabled())
})

it('preserves a recovered dataset when the current dataset list arrives later', async () => {
  const active = activeResearch(), manifest = `sha256:${'f'.repeat(64)}`
  active.plan.v2_graphs[0].dataset_manifest_address = manifest
  const api = recoveryApi([active])
  let resolve!: (value: typeof dataset[]) => void
  api.researchDatasets.mockImplementationOnce(() => new Promise((done) => { resolve = done }))
  render(<BacktestWorkspace api={api as unknown as StrategyApi} project={project} graph={graph} />)
  await screen.findByText(/Research running/)
  await act(async () => resolve([dataset]))
  expect(screen.getByLabelText('Historical dataset')).toHaveTextContent('Requested dataset · not in the current list')
  expect(screen.getAllByRole('combobox').some((control) => control.textContent?.includes('Requested dataset · not in the current list'))).toBe(true)
  expect(api.researchOperation.mock.calls[0][1].request.dataset_manifest_address).toBe(manifest)
  expect(api.prepareResearchFromSettings).not.toHaveBeenCalled()
})


it('ignores a stale recovery lookup after the API client changes', async () => {
  const first = recoveryApi(), next = recoveryApi()
  let resolve!: (value: ReturnType<typeof parseResearchRecovery>) => void
  first.researchRecovery.mockImplementationOnce(() => new Promise((done) => { resolve = done }))
  const view = render(<BacktestWorkspace api={first as unknown as StrategyApi} project={project} graph={graph} />)
  await screen.findByText(/Checking active research before/)
  view.rerender(<BacktestWorkspace api={next as unknown as StrategyApi} project={project} graph={graph} />)
  await waitFor(() => expect(screen.getByRole('button', { name: 'Run version 1' })).toBeEnabled())
  await act(async () => resolve(parseResearchRecovery({ active_operations: [activeResearch()], active_complete: true }, first.researchRecovery.mock.calls[0][0])))
  expect(next.researchOperation).not.toHaveBeenCalled()
  expect(screen.getByRole('button', { name: 'Run version 1' })).toBeEnabled()
})

it('rechecks the active list after a recovered request completes before enabling another launch', async () => {
  const context = { projectId: project.project_id, graphId: graph.identifier, version: 1, contentAddress: savedVersion.content_address }
  const api = recoveryApi([activeResearch()])
  api.researchRecovery.mockResolvedValueOnce(parseResearchRecovery({ active_operations: [activeResearch()], active_complete: true }, context))
    .mockResolvedValueOnce({ complete: true, requests: [] })
  api.researchOperation.mockResolvedValueOnce(operation('completed', [9]))
  render(<BacktestWorkspace api={api as unknown as StrategyApi} project={project} graph={graph} />)
  await waitFor(() => expect(api.researchRecovery).toHaveBeenCalledTimes(2))
  await waitFor(() => expect(screen.getByRole('button', { name: 'Run version 1' })).toBeEnabled())
  expect(api.prepareResearchFromSettings).not.toHaveBeenCalled()
  expect(api.visualization).toHaveBeenCalledWith(project.project_id, 9, 0, expect.any(AbortSignal))
})

it('ignores cancellation from a previously selected recovered request', async () => {
  const otherId = 'e'.repeat(64), base = recoveryApi([activeResearch(), activeResearch(otherId)])
  let resolve!: (value: ReturnType<typeof operation>) => void
  const cancelResearchOperation = vi.fn().mockImplementationOnce(() => new Promise((done) => { resolve = done }))
  const api = { ...base, cancelResearchOperation }
  render(<BacktestWorkspace api={api as unknown as StrategyApi} project={project} graph={graph} />)
  await screen.findByLabelText('Active research request')
  await chooseSelect('Active research request', operationId)
  fireEvent.click(await screen.findByRole('button', { name: 'Cancel research' }))
  await chooseSelect('Active research request', otherId)
  await waitFor(() => expect(api.researchOperation).toHaveBeenCalledTimes(2))
  expect(cancelResearchOperation.mock.calls[0][2].aborted).toBe(true)
  await act(async () => resolve(operation('cancelled')))
  expect(screen.getByLabelText('Active research request')).toHaveTextContent('Request 2')
  expect(screen.queryByText('Research cancelled. No completed result is being presented.')).not.toBeInTheDocument()
})


it('refuses new research while defaults fail and preserves edits through retry', async () => {
  const api = recoveryApi()
  api.strategyResearchSettings.mockRejectedValueOnce(new Error('Settings temporarily unavailable'))
  render(<BacktestWorkspace api={api as unknown as StrategyApi} project={project} graph={graph} />)
  expect(await screen.findByText(/Research defaults must be available/)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Run version 1' })).toBeDisabled()
  fireEvent.change(screen.getByLabelText('Hypothesis'), { target: { value: 'Keep this research question' } })
  fireEvent.click(screen.getByRole('button', { name: 'Reload research defaults' }))
  await waitFor(() => expect(screen.getByRole('button', { name: 'Run version 1' })).toBeEnabled())
  expect(screen.getByLabelText('Hypothesis')).toHaveValue('Keep this research question')
  fireEvent.change(screen.getByLabelText('Research capital (INR)'), { target: { value: '345678' } })
  fireEvent.click(screen.getByRole('button', { name: 'Reload research defaults' }))
  await waitFor(() => expect(api.strategyResearchSettings).toHaveBeenCalledTimes(3))
  expect(screen.getByLabelText('Research capital (INR)')).toHaveValue(345678)
  expect(api.prepareResearchFromSettings).not.toHaveBeenCalled()
})


it('restores a /3 snapshot after refresh without reading newer settings or resubmitting', async () => {
  const active = activeResearch()
  const item = active.plan.v2_graphs[0]
  const { request_id: _id, dataset_manifest_address: _dataset, dataset_as_of: _asOf, hypothesis: _hypothesis, ...values } = recoveredRequest
  const revision = { schema: 'research-settings-revision/1', owner_id: 'owner.a', graph_identifier: null, revision: 0, expected_revision: 0,
    request_id: null, enabled: true, values: settingsValues, content_address: `sha256:${'1'.repeat(64)}` }
  const snapshot = { schema: 'research-settings-snapshot/1', owner_id: 'owner.a', graph_identifier: graph.identifier, workspace: revision,
    strategy: { ...revision, graph_identifier: graph.identifier, values: {}, content_address: `sha256:${'2'.repeat(64)}` },
    run_overrides: values, values, sources: Object.fromEntries(Object.keys(values).map((key) => [key, 'run'])), content_address: `sha256:${'3'.repeat(64)}` }
  const saved = { ...active, plan: { ...active.plan, schema: 'v2-graph-research-operation/3', v2_graphs: [{ ...item, owner_id: 'owner.a', settings_snapshot: snapshot, execution_policy: { schema: 'v2-research-execution-policy/1', risk: { ...item.execution_policy.risk, sizing_model: 'one_lot_or_cash_budget_v1', fill: 'existing-next-bar-open', overlay: { schema: 'v2-research-risk-policy/1', policy_id: recoveredRequest.risk_policy } } } }] } }
  const api = recoveryApi()
  api.researchRecovery.mockImplementation(async (context) => parseResearchRecovery({ active_operations: [saved], active_complete: true }, context))
  api.strategyResearchSettings.mockRejectedValue(new Error('New defaults must not be read'))
  const props = { api: api as unknown as StrategyApi, project, graph }
  const first = render(<BacktestWorkspace {...props} />)
  await screen.findByText(/Research running/)
  expect(screen.getByLabelText('Research capital (INR)')).toHaveValue(250000)
  expect(api.researchOperation.mock.calls[0][1].settings.snapshotAddress).toBe(snapshot.content_address)
  first.unmount(); render(<BacktestWorkspace {...props} />)
  await screen.findByText(/Research running/)
  expect(api.strategyResearchSettings).not.toHaveBeenCalled()
  expect(api.prepareResearchFromSettings).not.toHaveBeenCalled()
  expect(api.researchOperation.mock.calls[1][1].request).toEqual(recoveredRequest)
})


it.each([false, true])('keeps unchanged values inherited and sends only changed capital (changed=%s)', async (changed) => {
  const api = recoveryApi()
  api.prepareResearchFromSettings.mockResolvedValue(receipt)
  render(<BacktestWorkspace api={api as unknown as StrategyApi} project={project} graph={graph} />)
  await waitFor(() => expect(screen.getByRole('button', { name: 'Run version 1' })).toBeEnabled())
  if (changed) fireEvent.change(screen.getByLabelText('Research capital (INR)'), { target: { value: '130000' } })
  fireEvent.click(screen.getByRole('button', { name: 'Run version 1' }))
  await waitFor(() => expect(api.prepareResearchFromSettings).toHaveBeenCalledOnce())
  expect(api.prepareResearchFromSettings.mock.calls[0][3].run_overrides).toEqual(changed ? { research_capital: 130000 } : {})
  await waitFor(() => expect(api.researchOperation).toHaveBeenCalled())
  expect(api.researchOperation.mock.calls[0][1].request.research_capital).toBe(changed ? 130000 : 100000)
})


it('reloads a stale preview without discarding run edits and starts with the reviewed revisions', async () => {
  const { ApiError } = await import('../shell/api')
  const api = recoveryApi()
  api.prepareResearchFromSettings.mockRejectedValueOnce(new ApiError('input', 'Conflict', { code: 'RESEARCH_SETTINGS_CONFLICT', message: 'Changed' })).mockResolvedValue(receipt)
  api.strategyResearchSettings.mockResolvedValueOnce(settingsPreview).mockResolvedValue({ ...settingsPreview,
    workspace: { ...settingsPreview.workspace, revision: 2, content_address: `sha256:${'4'.repeat(64)}`, values: { ...settingsValues, research_capital: 200000 } },
    values: { ...settingsValues, research_capital: 200000 } })
  render(<BacktestWorkspace api={api as unknown as StrategyApi} project={project} graph={graph} />)
  await waitFor(() => expect(screen.getByRole('button', { name: 'Run version 1' })).toBeEnabled())
  fireEvent.change(screen.getByLabelText('Research capital (INR)'), { target: { value: '130000' } })
  fireEvent.click(screen.getByRole('button', { name: 'Run version 1' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Reload research defaults')
  fireEvent.click(screen.getByRole('button', { name: 'Reload research defaults' }))
  await waitFor(() => expect(api.strategyResearchSettings).toHaveBeenCalledTimes(2))
  await waitFor(() => expect(screen.getByRole('button', { name: 'Run version 1' })).toBeEnabled())
  expect(screen.getByLabelText('Research capital (INR)')).toHaveValue(130000)
  fireEvent.click(screen.getByRole('button', { name: 'Run version 1' }))
  await waitFor(() => expect(api.prepareResearchFromSettings).toHaveBeenCalledTimes(2))
  const before = api.prepareResearchFromSettings.mock.calls[0][3], after = api.prepareResearchFromSettings.mock.calls[1][3]
  expect(after.expected_workspace_revision).toBe(2)
  expect(after.run_overrides).toEqual({ research_capital: 130000 })
  expect(after.request_id).not.toBe(before.request_id)
})


it('offers reversal as an explicit run override with the matching sizing explanation', async () => {
  const api = recoveryApi(); api.prepareResearchFromSettings.mockResolvedValue(receipt)
  render(<BacktestWorkspace api={api as unknown as StrategyApi} project={project} graph={graph} />)
  await waitFor(() => expect(screen.getByRole('button', { name: 'Run version 1' })).toBeEnabled())
  expect(screen.getByLabelText('Research risk policy')).toHaveTextContent('None — authored signal exits only')
  await chooseSelect('Research risk policy', 'pine-v4-reversal/1')
  expect(screen.getByText(/Sizing uses one unit/)).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Run version 1' }))
  await waitFor(() => expect(api.prepareResearchFromSettings).toHaveBeenCalledOnce())
  expect(api.prepareResearchFromSettings.mock.calls[0][3].run_overrides).toEqual({ risk_policy: 'pine-v4-reversal/1' })
})


it('does not reuse a previous API settings preview for a new session scope', async () => {
  const firstApi = recoveryApi()
  const nextApi = recoveryApi()
  let finish!: (value: typeof settingsPreview) => void
  nextApi.strategyResearchSettings.mockImplementation(() => new Promise((resolve) => { finish = resolve }))
  const view = render(<BacktestWorkspace api={firstApi as unknown as StrategyApi} project={project} graph={graph} />)
  await waitFor(() => expect(screen.getByRole('button', { name: 'Run version 1' })).toBeEnabled())
  view.rerender(<BacktestWorkspace api={nextApi as unknown as StrategyApi} project={project} graph={graph} />)
  expect(screen.getByRole('button', { name: 'Run version 1' })).toBeDisabled()
  await waitFor(() => expect(nextApi.strategyResearchSettings).toHaveBeenCalledOnce())
  await act(async () => finish({ ...settingsPreview, values: { ...settingsValues, research_capital: 220000 } }))
  await waitFor(() => expect(screen.getByRole('button', { name: 'Run version 1' })).toBeEnabled())
  expect(screen.getByLabelText('Research capital (INR)')).toHaveValue(220000)
  expect(firstApi.prepareResearchFromSettings).not.toHaveBeenCalled()
})

const primaryHistory = { ...dataset, instrument_address: `sha256:${'7'.repeat(64)}`, canonical_instrument_label: 'RELIANCE', asset_class: 'EQUITY', fields: ['OPEN', 'HIGH', 'LOW', 'CLOSE', 'VOLUME'], research_compatibility: 'PRIMARY_BACKTEST' }
const benchmarkHistory = { ...primaryHistory, instrument_address: `sha256:${'8'.repeat(64)}`, manifest_address: `sha256:${'e'.repeat(64)}`, canonical_instrument_label: 'NIFTY 50', asset_class: 'INDEX', fields: ['OPEN', 'HIGH', 'LOW', 'CLOSE'],
  as_of: '2026-02-01T00:00:00Z', backtest_eligibility: 'UNAVAILABLE', research_compatibility: 'BENCHMARK_INPUT_ONLY' }
const inputVersion = { ...savedVersion, document: { ...savedVersion.document,
  graph_inputs: ['frame', 'benchmark'].map((port_id) => ({ port_id, direction: 'input', semantic_role: 'market_frame' })) } }
function inputApi(histories = [primaryHistory, benchmarkHistory]) {
  const api = recoveryApi()
  api.v2Version.mockResolvedValue(inputVersion)
  api.researchDatasets.mockResolvedValue(histories)
  return { ...api, prepareResearchFromInputs: vi.fn().mockResolvedValue(receipt), cancelResearchOperation: vi.fn().mockResolvedValue(operation('cancelled')) }
}
async function chooseInputHistory() {
  await screen.findByLabelText('Frame dataset')
  await chooseSelect('Frame dataset', primaryHistory.manifest_address)
  await chooseSelect('Benchmark dataset', benchmarkHistory.manifest_address)
  await waitFor(() => expect(screen.getByRole('button', { name: 'Run version 1' })).toBeEnabled())
}

it('submits separate saved graph inputs with a shared explicit cutoff and pinned settings through /4', async () => {
  const api = inputApi()
  render(<BacktestWorkspace api={api as unknown as StrategyApi} project={project} graph={graph} />)
  await screen.findByLabelText('Frame dataset')
  expect(screen.queryByLabelText('Historical dataset')).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Run version 1' })).toBeDisabled()
  await chooseInputHistory()
  expect(screen.getByLabelText('Primary input')).toHaveTextContent('Frame')
  expect(screen.getByLabelText('Data available as of (UTC)')).toHaveValue('2026-02-01T00:00')
  fireEvent.change(screen.getByLabelText('Data available as of (UTC)'), { target: { value: '2026-02-02T12:30:45' } })
  fireEvent.change(screen.getByLabelText('Research capital (INR)'), { target: { value: '125000' } })
  fireEvent.click(screen.getByRole('button', { name: 'Run version 1' }))
  await waitFor(() => expect(api.prepareResearchFromInputs).toHaveBeenCalledOnce())
  expect(api.prepareResearchFromInputs.mock.calls[0].slice(0, 3)).toEqual([project.project_id, graph.identifier, 1])
  const request = api.prepareResearchFromInputs.mock.calls[0][3]
  expect(request).toEqual({ request_id: expect.any(String), input_datasets: [
    { graph_input_id: 'benchmark', dataset_manifest_address: benchmarkHistory.manifest_address },
    { graph_input_id: 'frame', dataset_manifest_address: primaryHistory.manifest_address },
  ], primary_input: 'frame', dataset_as_of: '2026-02-02T12:30:45Z', hypothesis: 'Test the saved strategy on historical data.',
  expected_workspace_revision: 1, expected_strategy_revision: 0, run_overrides: { research_capital: 125000 } })
  expect(api.prepareResearchFromSettings).not.toHaveBeenCalled()
  expect(screen.getByLabelText('Frame dataset')).toBeDisabled()
  await screen.findByText(/Research running/)
  fireEvent.click(screen.getByRole('button', { name: 'Cancel research' }))
  await waitFor(() => expect(api.cancelResearchOperation).toHaveBeenCalledOnce())
  expect(api.cancelResearchOperation.mock.calls[0][1].request.input_datasets).toEqual(request.input_datasets)
})

it('rejects duplicate input history and index primary without claiming data readiness', async () => {
  const api = inputApi()
  render(<BacktestWorkspace api={api as unknown as StrategyApi} project={project} graph={graph} />)
  await chooseInputHistory()
  expect(screen.queryByText(/cross-instrument strategy binding is not yet available/)).not.toBeInTheDocument()
  expect(screen.getByText(/Bar alignment, warmup and required fields are checked/)).toBeInTheDocument()
  await chooseSelect('Frame dataset', benchmarkHistory.manifest_address)
  expect(screen.getByText('Choose a distinct dataset for each input.')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Run version 1' })).toBeDisabled()
  await chooseSelect('Frame dataset', primaryHistory.manifest_address)
  await chooseSelect('Primary input', 'benchmark')
  expect(screen.getByText('Choose an equity dataset ready for backtesting as the primary input.')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Run version 1' })).toBeDisabled()
  expect(api.prepareResearchFromInputs).not.toHaveBeenCalled()
  await chooseSelect('Benchmark dataset', primaryHistory.manifest_address)
  await chooseSelect('Frame dataset', benchmarkHistory.manifest_address)
  expect(screen.getByRole('button', { name: 'Run version 1' })).toBeEnabled()
  fireEvent.click(screen.getByRole('button', { name: 'Run version 1' }))
  await waitFor(() => expect(api.prepareResearchFromInputs).toHaveBeenCalledOnce())
  expect(api.prepareResearchFromInputs.mock.calls[0][3]).toMatchObject({ primary_input: 'benchmark', input_datasets: [
    { graph_input_id: 'benchmark', dataset_manifest_address: primaryHistory.manifest_address },
    { graph_input_id: 'frame', dataset_manifest_address: benchmarkHistory.manifest_address },
  ] })
})

it.each([
  [{ interval: '1h' }, 'Choose datasets with the same bar interval.'],
  [{ event_start: '2026-01-01', event_end: '2026-02-01' }, 'The selected histories do not overlap. Choose histories covering the same period.'],
  [{ research_compatibility: 'UNAVAILABLE' }, 'One selected dataset is not supported by this research path.'],
] as const)('explains incompatible input histories before sending a request %j', async (change, reason) => {
  const api = inputApi([primaryHistory, { ...benchmarkHistory, ...change }])
  render(<BacktestWorkspace api={api as unknown as StrategyApi} project={project} graph={graph} />)
  await screen.findByLabelText('Frame dataset')
  await chooseSelect('Frame dataset', primaryHistory.manifest_address)
  await chooseSelect('Benchmark dataset', benchmarkHistory.manifest_address)
  expect(screen.getByText(reason)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Run version 1' })).toBeDisabled()
  expect(api.prepareResearchFromInputs).not.toHaveBeenCalled()
})

it('retains explicit input cutoff and bindings after failed /4 submission and reuses only unchanged request identity', async () => {
  const newer = { ...benchmarkHistory, manifest_address: `sha256:${'f'.repeat(64)}`, as_of: '2026-03-01T00:00:00Z' }
  const api = inputApi([primaryHistory, benchmarkHistory, newer])
  api.prepareResearchFromInputs.mockRejectedValue(new Error('Temporary failure'))
  render(<BacktestWorkspace api={api as unknown as StrategyApi} project={project} graph={graph} />)
  await chooseInputHistory()
  fireEvent.change(screen.getByLabelText('Data available as of (UTC)'), { target: { value: '2026-02-03T11:12:13' } })
  fireEvent.click(screen.getByRole('button', { name: 'Run version 1' }))
  await screen.findByRole('alert')
  const first = api.prepareResearchFromInputs.mock.calls[0][3]
  fireEvent.click(screen.getByRole('button', { name: 'Run version 1' }))
  await waitFor(() => expect(api.prepareResearchFromInputs).toHaveBeenCalledTimes(2))
  await screen.findByRole('alert')
  expect(api.prepareResearchFromInputs.mock.calls[1][3]).toEqual(first)
  await chooseSelect('Benchmark dataset', newer.manifest_address)
  expect(screen.getByLabelText('Data available as of (UTC)')).toHaveValue('2026-02-03T11:12:13.000')
  fireEvent.click(screen.getByRole('button', { name: 'Run version 1' }))
  await waitFor(() => expect(api.prepareResearchFromInputs).toHaveBeenCalledTimes(3))
  expect(api.prepareResearchFromInputs.mock.calls[2][3].request_id).not.toBe(first.request_id)
  expect(api.prepareResearchFromSettings).not.toHaveBeenCalled()
})

it('requires a valid explicit cutoff and supported saved input metadata for /4', async () => {
  const api = inputApi()
  const view = render(<BacktestWorkspace api={api as unknown as StrategyApi} project={project} graph={graph} />)
  await chooseInputHistory()
  fireEvent.change(screen.getByLabelText('Data available as of (UTC)'), { target: { value: '' } })
  expect(screen.getByText('Choose a valid shared data cutoff in UTC.')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Run version 1' })).toBeDisabled()
  view.unmount()
  api.v2Version.mockResolvedValue({ ...inputVersion, document: { ...inputVersion.document, graph_inputs: [{ ...inputVersion.document.graph_inputs[0], semantic_role: 'derived_value' }, inputVersion.document.graph_inputs[1]] } })
  render(<BacktestWorkspace api={api as unknown as StrategyApi} project={project} graph={graph} />)
  expect(await screen.findByText('This saved version has an input that cannot use historical market bars.')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Run version 1' })).toBeDisabled()
})

it('restores every /4 dataset, explicit primary and cutoff before newer lists arrive without resubmitting', async () => {
  const active = activeResearch()
  const { dataset_manifest_address: _manifest, ...item } = active.plan.v2_graphs[0]
  const { request_id: _request, dataset_manifest_address: _dataset, dataset_as_of: _asOf, hypothesis: _hypothesis, ...values } = recoveredRequest
  const revision = { schema: 'research-settings-revision/1', owner_id: 'owner.a', graph_identifier: null, revision: 0, expected_revision: 0,
    request_id: null, enabled: true, values: settingsValues, content_address: `sha256:${'1'.repeat(64)}` }
  const snapshot = { schema: 'research-settings-snapshot/1', owner_id: 'owner.a', graph_identifier: graph.identifier, workspace: revision,
    strategy: { ...revision, graph_identifier: graph.identifier, values: {}, content_address: `sha256:${'2'.repeat(64)}` },
    run_overrides: values, values, sources: Object.fromEntries(Object.keys(values).map((key) => [key, 'run'])), content_address: `sha256:${'3'.repeat(64)}` }
  const input_datasets = [{ graph_input_id: 'benchmark', dataset_manifest_address: primaryHistory.manifest_address },
    { graph_input_id: 'frame', dataset_manifest_address: benchmarkHistory.manifest_address }]
  const saved = { ...active, plan: { ...active.plan, schema: 'v2-graph-research-operation/4', v2_graphs: [{ ...item,
    input_datasets, primary_input: 'benchmark', dataset_as_of: '2026-02-02T12:30:45Z', owner_id: 'owner.a', settings_snapshot: snapshot,
    execution_policy: { schema: 'v2-research-execution-policy/1', risk: { ...item.execution_policy.risk, sizing_model: 'one_lot_or_cash_budget_v1', fill: 'existing-next-bar-open', overlay: { schema: 'v2-research-risk-policy/1', policy_id: recoveredRequest.risk_policy } } } }] } }
  const api = inputApi()
  let finish!: (value: typeof primaryHistory[]) => void
  api.researchDatasets.mockImplementation(() => new Promise((resolve) => { finish = resolve }))
  api.researchRecovery.mockImplementation(async (context) => parseResearchRecovery({ active_operations: [saved], active_complete: true }, context))
  api.strategyResearchSettings.mockRejectedValue(new Error('New defaults must not be read'))
  render(<BacktestWorkspace api={api as unknown as StrategyApi} project={project} graph={graph} />)
  await screen.findByText(/Research running/)
  expect(screen.getByLabelText('Frame dataset')).toHaveTextContent('Requested dataset · not in the current list')
  expect(screen.getByLabelText('Benchmark dataset')).toHaveTextContent('Requested dataset · not in the current list')
  expect(screen.getByLabelText('Primary input')).toHaveTextContent('Benchmark')
  expect(screen.getByLabelText('Data available as of (UTC)')).toHaveValue('2026-02-02T12:30:45.000')
  expect(screen.getByLabelText('Frame dataset')).toBeDisabled()
  await act(async () => finish([primaryHistory]))
  expect(screen.getByLabelText('Benchmark dataset')).toHaveTextContent('RELIANCE')
  expect(screen.getByLabelText('Frame dataset')).toHaveTextContent('Requested dataset · not in the current list')
  expect(screen.getAllByRole('combobox').some((control) => control.textContent?.includes('Requested dataset · not in the current list'))).toBe(true)
  expect(api.researchOperation.mock.calls[0][1].request.input_datasets).toEqual(input_datasets)
  expect(api.researchOperation.mock.calls[0][1].settings.snapshotAddress).toBe(snapshot.content_address)
  expect(api.strategyResearchSettings).not.toHaveBeenCalled()
  expect(api.prepareResearchFromInputs).not.toHaveBeenCalled()
  expect(api.prepareResearchFromSettings).not.toHaveBeenCalled()
})

function memberHandoff(history = primaryHistory): { scope: StaticScope; context: StaticScopeMemberContext } {
  const scope: StaticScope = { scope_id: 'scope.member', name: 'Research members', status: 'active', current_revision: 1,
    address: `sha256:${'5'.repeat(64)}`, membership_address: `sha256:${'6'.repeat(64)}`,
    member_labels: [{ instrument_address: history.instrument_address, display_name: null }],
    snapshot: { schema: 'static-instrument-scope/1', owner_id: 'owner.a', project_id: project.project_id, scope_id: 'scope.member', revision: 1, predecessor: null, members: [history.instrument_address] } }
  return { scope, context: { schema: 'static-scope-member-context/1', project_id: project.project_id, graph_id: graph.identifier, graph_version: 1,
    scope_id: scope.scope_id, revision: 1, address: scope.address, membership_address: scope.membership_address, instrument_address: history.instrument_address, dataset_manifest_address: history.manifest_address } }
}
it('applies a verified watchlist member to scalar setup without adding scope metadata to /3', async () => {
  const { scope, context } = memberHandoff()
  const api = { ...recoveryApi(), staticScope: vi.fn().mockResolvedValue(scope) }
  api.researchDatasets.mockResolvedValue([{ ...primaryHistory, manifest_address: `sha256:${'f'.repeat(64)}` }, primaryHistory])
  api.prepareResearchFromSettings.mockResolvedValue(receipt)
  render(<BacktestWorkspace api={api as unknown as StrategyApi} project={project} graph={graph} scopeContext={context} />)
  await screen.findByText(/Opened from Research members, revision 1/)
  await waitFor(() => expect(screen.getByLabelText('Historical dataset')).toHaveTextContent('RELIANCE'))
  expect(api.staticScope.mock.calls[0].slice(0, 3)).toEqual([project.project_id, scope.scope_id, 1])
  fireEvent.click(screen.getByRole('button', { name: 'Run version 1' }))
  await waitFor(() => expect(api.prepareResearchFromSettings).toHaveBeenCalledOnce())
  expect(api.prepareResearchFromSettings.mock.calls[0][3]).toMatchObject({ dataset_manifest_address: primaryHistory.manifest_address, dataset_as_of: primaryHistory.as_of })
  expect(Object.keys(api.prepareResearchFromSettings.mock.calls[0][3])).toEqual(['request_id', 'dataset_manifest_address', 'dataset_as_of', 'hypothesis', 'expected_workspace_revision', 'expected_strategy_revision', 'run_overrides'])
})
it.each(['revision', 'member', 'dataset', 'project', 'graph'] as const)('refuses an unverifiable watchlist %s before applying history', async (failure) => {
  const { scope, context } = memberHandoff()
  const value = failure === 'revision' ? { ...scope, address: `sha256:${'f'.repeat(64)}` }
    : failure === 'member' ? { ...scope, snapshot: { ...scope.snapshot, members: [benchmarkHistory.instrument_address] } } : scope
  const selected = failure === 'project' ? { ...context, project_id: 'project.foreign' } : failure === 'graph' ? { ...context, graph_id: 'graph.foreign' } : context
  const api = { ...recoveryApi(), staticScope: vi.fn().mockResolvedValue(value) }
  api.researchDatasets.mockResolvedValue([failure === 'dataset' ? { ...primaryHistory, instrument_address: benchmarkHistory.instrument_address } : primaryHistory])
  render(<BacktestWorkspace api={api as unknown as StrategyApi} project={project} graph={graph} scopeContext={selected} />)
  expect(await screen.findByRole('alert')).toHaveTextContent('selected watchlist revision, member or history could not be verified')
  expect(screen.getByRole('button', { name: 'Run version 1' })).toBeDisabled()
  expect(api.prepareResearchFromSettings).not.toHaveBeenCalled()
  if (failure === 'project' || failure === 'graph') expect(api.staticScope).not.toHaveBeenCalled()
})
it('preserves active /4 bindings and applies a watchlist member only to primary after explicit cancellation', async () => {
  const { scope, context } = memberHandoff(benchmarkHistory)
  const api = { ...inputApi(), staticScope: vi.fn().mockResolvedValue(scope) }
  const props = { api: api as unknown as StrategyApi, project, graph }
  const view = render(<BacktestWorkspace {...props} />)
  await chooseInputHistory(); fireEvent.click(screen.getByRole('button', { name: 'Run version 1' }))
  await screen.findByText(/Research running/)
  const original = api.prepareResearchFromInputs.mock.calls[0][3]
  view.rerender(<BacktestWorkspace {...props} scopeContext={context} />)
  await screen.findByText(/Opened from Research members/)
  expect(screen.getByLabelText('Frame dataset')).toHaveTextContent('RELIANCE')
  expect(screen.getByLabelText('Benchmark dataset')).toHaveTextContent('NIFTY 50')
  expect(screen.getByRole('button', { name: 'Use member for next run' })).toBeDisabled()
  expect(api.prepareResearchFromInputs).toHaveBeenCalledOnce()
  fireEvent.click(screen.getByRole('button', { name: 'Cancel research' }))
  await waitFor(() => expect(screen.getByRole('button', { name: 'Use member for next run' })).toBeEnabled())
  expect(api.cancelResearchOperation.mock.calls[0][1].request.input_datasets).toEqual(original.input_datasets)
  fireEvent.click(screen.getByRole('button', { name: 'Use member for next run' }))
  expect(screen.getByLabelText('Primary input')).toHaveTextContent('Frame')
  expect(screen.getByLabelText('Frame dataset')).toHaveTextContent('NIFTY 50')
  expect(screen.getByLabelText('Benchmark dataset')).toHaveTextContent('NIFTY 50')
  expect(screen.getByText('Choose a distinct dataset for each input.')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Run version 1' })).toBeDisabled()
  expect(api.prepareResearchFromInputs).toHaveBeenCalledOnce()
})
it('keeps an uncertain /4 POST retryable with the same identity when a new watchlist context arrives', async () => {
  const nextHistory = { ...primaryHistory, manifest_address: `sha256:${'f'.repeat(64)}`, instrument_address: `sha256:${'9'.repeat(64)}` }
  const { scope, context } = memberHandoff(nextHistory)
  const api = { ...inputApi([primaryHistory, benchmarkHistory, nextHistory]), staticScope: vi.fn().mockResolvedValue(scope) }
  api.prepareResearchFromInputs.mockRejectedValue(new ApiError('network', 'Unknown submission'))
  const props = { api: api as unknown as StrategyApi, project, graph }
  const view = render(<BacktestWorkspace {...props} />)
  await chooseInputHistory(); fireEvent.click(screen.getByRole('button', { name: 'Run version 1' }))
  await screen.findByRole('alert')
  const original = api.prepareResearchFromInputs.mock.calls[0][3]
  view.rerender(<BacktestWorkspace {...props} scopeContext={context} />)
  await screen.findByText(/Opened from Research members/)
  expect(screen.getByLabelText('Frame dataset')).toHaveTextContent('RELIANCE')
  expect(screen.getByLabelText('Benchmark dataset')).toHaveTextContent('NIFTY 50')
  expect(screen.getByRole('button', { name: 'Use member for next run' })).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Run version 1' })).toBeEnabled()
  fireEvent.click(screen.getByRole('button', { name: 'Run version 1' }))
  await waitFor(() => expect(api.prepareResearchFromInputs).toHaveBeenCalledTimes(2))
  expect(api.prepareResearchFromInputs.mock.calls[1][3]).toEqual(original)
})

it.each([0, 9])('explains unsupported saved input count %s without marking the valid version corrupt', async (count) => {
  const api = recoveryApi()
  api.v2Version.mockResolvedValue({ ...savedVersion, document: { ...savedVersion.document, graph_inputs: Array.from({ length: count }, (_, index) => ({ port_id: `input${index}`, direction: 'input', semantic_role: 'market_frame' })) } })
  render(<BacktestWorkspace api={api as unknown as StrategyApi} project={project} graph={graph} />)
  const reason = count === 0 ? 'Add a market-data input in Build before running.' : 'This research path supports at most eight market-data inputs.'
  expect(await screen.findAllByText(reason)).not.toHaveLength(0)
  expect(screen.queryByText(/server response could not be verified|saved version must be verified/)).not.toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('Hypothesis'), { target: { value: 'Keep this setup for the edited strategy.' } })
  expect(screen.getByLabelText('Hypothesis')).toHaveValue('Keep this setup for the edited strategy.')
  expect(screen.getByRole('button', { name: 'Run version 1' })).toBeDisabled()
  expect(api.prepareResearchFromSettings).not.toHaveBeenCalled()
})

it('keeps an unavailable recovered request disabled in the real selection menu', async () => {
  const unavailable = activeResearch('e'.repeat(64)); unavailable.plan.schema = 'v2-graph-research-operation/1'
  const api = recoveryApi([activeResearch(), unavailable])
  render(<BacktestWorkspace api={api as unknown as StrategyApi} project={project} graph={graph} />)
  fireEvent.keyDown(await screen.findByRole('combobox', { name: 'Active research request' }), { key: 'ArrowDown' })
  const option = await screen.findByRole('option', { name: /setup unavailable/ })
  expect(option).toHaveAttribute('aria-disabled', 'true')
  fireEvent.click(option); expect(api.researchOperation).not.toHaveBeenCalled()
  fireEvent.keyDown(screen.getByRole('listbox'), { key: 'Escape' })
  await chooseSelect('Active research request', operationId)
  await waitFor(() => expect(api.researchOperation).toHaveBeenCalled())
  expect(api.researchOperation.mock.calls[0][0]).toBe(operationId)
})

it('chooses and clears scalar history through the real menu without changing manifest identity', async () => {
  const other = { ...dataset, manifest_address: `sha256:${'f'.repeat(64)}`, canonical_instrument_label: 'Other history', as_of: '2026-02-01T00:00:00Z' }
  const api = recoveryApi(); api.researchDatasets.mockResolvedValue([dataset, other]); api.prepareResearchFromSettings.mockResolvedValue(receipt)
  render(<BacktestWorkspace api={api as unknown as StrategyApi} project={project} graph={graph} />)
  await waitFor(() => expect(screen.getByRole('button', { name: 'Run version 1' })).toBeEnabled())
  await chooseSelect('Historical dataset', other.manifest_address)
  expect(screen.getByRole('combobox', { name: 'Historical dataset' })).toHaveTextContent('Other history')
  await chooseSelect('Historical dataset', '')
  expect(screen.getByRole('button', { name: 'Run version 1' })).toBeDisabled()
  await chooseSelect('Historical dataset', other.manifest_address)
  fireEvent.click(screen.getByRole('button', { name: 'Run version 1' }))
  await waitFor(() => expect(api.prepareResearchFromSettings).toHaveBeenCalledOnce())
  expect(api.prepareResearchFromSettings.mock.calls[0][3]).toMatchObject({ dataset_manifest_address: other.manifest_address, dataset_as_of: other.as_of })
})

function optimizationLaunchApi() {
  const api = recoveryApi()
  const document = { format_version: 2, strategy_id: graph.identifier, strategy_version: 1,
    metadata: { metadata_version: 1, name: 'EMA research', description: '', tags: [] },
    graph_inputs: [{ port_id: 'frame', direction: 'input', semantic_flow: 'value', semantic_role: 'market_frame', type_ref: { type_id: 'market.frame', type_version: 1 }, shape: 'series' }],
    graph_outputs: [], edges: [], nodes: [{ node_id: 'ema', component: { component_id: 'indicators.ema', component_version: 1 }, parameters: { length: 42 } }] }
  api.v2Version.mockResolvedValue({ ...savedVersion, document })
  api.prepareResearchFromSettings.mockResolvedValue(receipt)
  return { ...api, catalogue: vi.fn().mockResolvedValue({ groups: [{ components: [{ component_id: 'indicators.ema', component_version: 1, display_name: 'Moving average',
    help: { customisation: { parameters: [{ name: 'length', type: 'int', required: false, default: 20, enum: null, domain: { minimum: 1, maximum: 100 }, units: 'bars', serialization: 'canonical-json' }] } } }] }] }) }
}

it('discovers optimization parameters in backtest and pins the selected run-only search without changing saved defaults', async () => {
  const api = optimizationLaunchApi()
  render(<BacktestWorkspace api={api as unknown as StrategyApi} project={project} graph={graph} />)
  await waitFor(() => expect(screen.getByRole('button', { name: 'Run version 1' })).toBeEnabled())
  expect(api.catalogue).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Choose optimization parameters' }))
  const enable = await screen.findByRole('checkbox', { name: 'Enable bounded development search' })
  await waitFor(() => expect(enable).toBeEnabled())
  fireEvent.click(enable)
  await chooseSelect('Add optimization parameter', JSON.stringify(['ema', 'length']))
  for (const [field, value] of [['step', '1'], ['minimum', '1'], ['maximum', '100']]) {
    fireEvent.change(screen.getByRole('textbox', { name: new RegExp(` ${field}$`) }), { target: { value } })
  }
  expect(screen.getByText('Baseline in version 1: 42')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Hide optimization parameters' }))
  fireEvent.click(screen.getByRole('button', { name: 'Run version 1' }))
  await waitFor(() => expect(api.prepareResearchFromSettings).toHaveBeenCalledOnce())
  expect(api.prepareResearchFromSettings.mock.calls[0][3].run_overrides).toEqual({ optimization: {
    schema: 'canonical-local-development-search/1', enabled: true,
    axes: [{ node_id: 'ema', parameter_id: 'length', step: '1', minimum: '1', maximum: '100' }],
  } })
  expect(settingsPreview.values).not.toHaveProperty('optimization')
})

it('refuses a backtest with enabled but incomplete optimization axes and preserves the form', async () => {
  const api = optimizationLaunchApi()
  render(<BacktestWorkspace api={api as unknown as StrategyApi} project={project} graph={graph} />)
  await waitFor(() => expect(screen.getByRole('button', { name: 'Run version 1' })).toBeEnabled())
  fireEvent.click(screen.getByRole('button', { name: 'Choose optimization parameters' }))
  const enable = await screen.findByRole('checkbox', { name: 'Enable bounded development search' })
  await waitFor(() => expect(enable).toBeEnabled()); fireEvent.click(enable)
  fireEvent.click(screen.getByRole('button', { name: 'Run version 1' }))
  expect(screen.getByText('Check the optimization parameters, steps and bounds before starting.')).toBeInTheDocument()
  expect(enable).toBeChecked()
  expect(api.prepareResearchFromSettings).not.toHaveBeenCalled()
})


it('opens the updated builder after an accepted research suggestion', async () => {
  const onPublished = vi.fn()
  const api = { researchRecovery: vi.fn().mockResolvedValue({ complete: true, requests: [] }), strategyResearchSettings: vi.fn().mockResolvedValue(settingsPreview),
    v2Version: vi.fn().mockResolvedValue(savedVersion), researchDatasets: vi.fn().mockResolvedValue([]),
    experiments: vi.fn().mockResolvedValue({ runs: [{ run_id: 7, graph: { identifier: graph.identifier, version: 1 }, dataset_bindings: [], contract: null }] }),
    visualization: vi.fn().mockResolvedValue({ state: 'PENDING', status: 'running' }), v2Draft: vi.fn().mockRejectedValue(new Error('Draft is loading')), catalogue: vi.fn().mockRejectedValue(new Error('Catalogue is loading')) } as unknown as StrategyApi
  render(<ResearchWorkspace api={api} project={project} graph={graph} backtestEnabled reviewEnabled onPublished={onPublished} initialView="backtest" />)
  fireEvent.click(await screen.findByRole('button', { name: 'Accept verified test suggestion' }))
  expect(onPublished).toHaveBeenCalledWith({ project_id: project.project_id, identifier: graph.identifier, version: 2, content_address: `sha256:${'c'.repeat(64)}` })
  expect(screen.getByRole('button', { name: 'Build' })).toHaveAttribute('aria-current', 'page')
  expect(screen.queryByRole('button', { name: 'Run version 1' })).not.toBeInTheDocument()
})
