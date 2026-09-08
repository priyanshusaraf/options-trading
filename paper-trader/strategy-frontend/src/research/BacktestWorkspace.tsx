import { TraderSelect } from '../components/TraderSelect'
import { CanonicalOptimizationResults } from './CanonicalOptimizationResults'
import { OptimizationSettingsFields, optimizationInputProblem } from './OptimizationSettingsFields'
import { ScopeMemberStatus, scopeMemberKey, scopeMemberReady, useScopeMember } from '../features/static-scopes/ScopeMemberContext'
import type { StaticScopeMemberContext } from '../features/static-scopes/staticScopeContracts'
import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import { FlaskConical, RefreshCw } from 'lucide-react'
import { ApiError, errorMessage, type StrategyApi } from '../shell/api'
import type { AvailableVisualization, ExperimentRun, GraphSummary, Project, PublishedGraph, ResearchValues, ResearchDataset, ResearchVisualization } from '../shell/contracts'
import { disabledOptimization, sameJson, type CanonicalOptimizationSettings } from '../shell/contracts'
import { ResearchSeriesChart } from './ResearchSeriesChart'
import { DailyCsvImport } from '../features/data/DailyCsvImport'
import { inputSettingsPreparation, isInputPreparation, parseResearchCutoff, settingsPreparation, parseSavedResearchPolicy, type PreparedOperation, type PreparationReceipt, type ResearchPreparation, type InputResearchPreparation, type ResearchRequest, type ResearchSelection, type RiskPolicy, type ResearchRecovery, type SavedResearchContext, type RecoverableResearch } from './preparedResearchContracts'
import { MarketContext } from '../features/chart-context/MarketContext'

type Load<T> = { kind: 'loading' } | { kind: 'error'; message: string } | { kind: 'ready'; value: T }
type ResultTab = 'performance' | 'market' | 'trades' | 'costs' | 'oos' | 'compare'

function money(value: unknown) { return typeof value === 'number' ? `INR ${value.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : 'Unavailable' }
function percent(value: unknown) { return typeof value === 'number' ? `${value.toFixed(2)}%` : 'Unavailable' }
function plainProduct(value: string) { return value.replace(/canonical/gi, 'verified') }
const comparisonReasons: Record<string, string> = { DATASET_IDENTITY_CHANGED: 'These runs use different datasets.', COST_ASSUMPTIONS_CHANGED: 'These runs use different trading costs.', GATE_CONTRACT_CHANGED: 'These runs use different validation rules.' }
const gateLabels: Record<string, string> = { min_oos_trades: 'Minimum out-of-sample trades', confident_edge: 'Confidence', temporal_stability: 'Stability across periods', slippage_stress_2x: 'Double-slippage check', pbo: 'Overfitting check' }
function FoldGates({ value }: { value: unknown }) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return <span>Unavailable</span>
  const gates = Object.entries(value).filter((entry): entry is [string, { passed: boolean; value?: unknown }] => Boolean(entry[1]) && typeof entry[1] === 'object' && typeof entry[1].passed === 'boolean')
  return gates.length ? <ul>{gates.map(([name, gate]) => <li key={name}>{gateLabels[name] ?? name.replaceAll('_', ' ')}: {gate.passed ? 'Passed' : 'Failed'}{typeof gate.value === 'number' && Number.isFinite(gate.value) ? ` · ${gate.value}` : ''}</li>)}</ul> : <span>Unavailable</span>
}

function ResultState({ visualization, retry }: { visualization: Load<ResearchVisualization>; retry: () => void }) {
  if (visualization.kind === 'loading') return <p role="status" className="workstation-state">Loading backtest results…</p>
  if (visualization.kind === 'error') return <div className="workstation-state"><p role="alert">{visualization.message}</p><button onClick={retry}>Retry</button></div>
  if (visualization.value.state === 'PENDING') return <div className="workstation-unavailable"><h3>Research is pending</h3><p>Prior run values are hidden. Refresh this run when its results are ready.</p></div>
  if (visualization.value.state === 'UNAVAILABLE') return <div className="workstation-unavailable"><h3>Visualization unavailable</h3><p>Numeric results are not available for this run.</p></div>
  return null
}

function replayDescription(policy: RiskPolicy) {
  return policy === 'pine-v4-reversal/1'
    ? 'Sizing uses one unit. Opposite signals close and replace the position at the next bar open.'
    : 'Sizing uses one lot or the available cash budget. Signal decisions fill at the next bar open.'
}

function datasetAvailability(item: ResearchDataset) {
  if (item.research_compatibility === 'BENCHMARK_INPUT_ONLY') return 'Benchmark only'
  return item.backtest_eligibility === 'ELIGIBLE_Q03' ? 'Ready for backtesting' : 'Not ready for backtesting'
}

function DatasetFacts({ item, inputSet = false }: { item: ResearchDataset; inputSet?: boolean }) {
  const availability = inputSet && item.backtest_eligibility === 'ELIGIBLE_Q03' ? 'Available for selection' : datasetAvailability(item)
  return <div className="dataset-facts"><span>{item.event_start} → {item.event_end}</span><span>{availability}</span>
    {item.source_type === 'USER_SUPPLIED' && <p>Personal CSV import. Historical publication times and exchange-calendar coverage have not been verified.</p>}
    {item.fields && !item.fields.some((field) => field.toLowerCase() === 'volume') && <p>Volume is absent. Rules that require volume need a different dataset.</p>}
    {item.research_compatibility === 'BENCHMARK_INPUT_ONLY' && <p>{inputSet ? 'This index is available as a benchmark. Choose equity history for the primary input.' : 'This index can be a benchmark input. A direct backtest needs an equity dataset; cross-instrument strategy binding is not yet available.'}</p>}
    {item.research_compatibility === 'UNAVAILABLE' && <p>This history is not supported by the current research path. Import daily equity OHLC data to continue.</p>}
  </div>
}

function NumericRunField({ label, id, value, minimum, maximum, step, error, disabled, onChange }: {
  label: string; id: string; value: string; minimum: number; maximum: number; step?: number
  error?: string; disabled?: boolean; onChange: (value: string) => void
}) {
  const errorId = `${id}-error`
  return <label>{label}<input type="number" min={minimum} max={maximum} step={step} value={value} disabled={disabled}
    aria-invalid={Boolean(error)} aria-describedby={error ? errorId : undefined} onChange={(event) => onChange(event.target.value)} />
    {error && <small id={errorId} role="alert">{error}</small>}</label>
}

type RunFields = { capital: string; n_folds: string; min_trades: string; min_positive_fold_frac: string; seed: string }
const RUN_BOUNDS: Record<keyof RunFields, readonly [number, number, boolean]> = {
  capital: [1, 1_000_000_000, false], n_folds: [2, 32, true], min_trades: [1, 100_000, true],
  min_positive_fold_frac: [0, 100, false], seed: [0, 2_147_483_647, true],
}
function validRunField(raw: string, [minimum, maximum, integer]: readonly [number, number, boolean]) {
  const value = Number(raw)
  return raw.trim() !== '' && Number.isFinite(value) && value >= minimum && value <= maximum && (!integer || Number.isInteger(value))
}
function runFieldErrors(values: RunFields, hypothesis: string) {
  const errors: Record<string, string> = {}
  for (const field of Object.keys(RUN_BOUNDS) as (keyof RunFields)[]) {
    const bound = RUN_BOUNDS[field]
    if (!validRunField(values[field], bound)) errors[field] = `Enter ${bound[2] ? 'a whole number' : 'a number'} from ${bound[0]} to ${bound[1]}.`
  }
  if (!hypothesis.trim() || hypothesis.length > 4000) errors.hypothesis = 'Enter a hypothesis of 1 to 4,000 characters.'
  return errors
}
function terminalOperation(operation: PreparedOperation | null) {
  return operation !== null && ['completed', 'failed', 'cancelled'].includes(operation.status)
}
function preparationError(error: unknown) {
  if (error instanceof ApiError) {
    const reasons: Record<string, string> = {
      RESEARCH_SETTINGS_CONFLICT: 'Research settings changed. Reload research defaults, review this run setup, then try again.',
      REQUEST_ID_REUSED: 'This request reference already belongs to different inputs. Change the setup to start a new request.',
      V2_GRAPH_NOT_FOUND: 'This saved strategy version is unavailable. Return to Build and save a version before retrying.',
      V2_GRAPH_CORRUPT: 'The saved strategy could not be verified. Save a new version in Build.',
      V2_DATASET_NOT_FOUND: 'The selected dataset is unavailable in this workspace. Refresh the data list and choose an owned dataset.',
      V2_PREPARATION_INVALID: 'The saved strategy, data or research assumptions do not meet the supported preparation contract. Check the selected version, dataset and optimization axes.',
    }
    const message = reasons[error.envelope?.code ?? '']
    if (message) return message
  }
  return errorMessage(error)
}
function usePreparedResearch(api: StrategyApi, onCompleted: (runId: number) => void, onTerminal: () => void) {
  const [accepted, setAccepted] = useState<{ receipt: PreparationReceipt; selection: ResearchSelection } | null>(null)
  const [value, setValue] = useState<PreparedOperation | null>(null)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [cancelPending, setCancelPending] = useState(false)
  const [cancelError, setCancelError] = useState<string | null>(null)
  const [pollAttempt, setPollAttempt] = useState(0)
  const busy = useRef(false)
  const post = useRef<AbortController | null>(null)
  const monitor = useRef<AbortController | null>(null)
  const cancellation = useRef<AbortController | null>(null)
  const completedId = useRef<string | null>(null)
  const verifiedSelection = useRef<{ api: StrategyApi; id: string; selection: ResearchSelection } | null>(null)
  const completion = useRef(onCompleted); completion.current = onCompleted
  const terminal = useRef(onTerminal); terminal.current = onTerminal
  const terminalId = useRef<string | null>(null)
  useEffect(() => () => { post.current?.abort(); monitor.current?.abort(); cancellation.current?.abort() }, [api])

  function selectionFor(id: string, fallback: ResearchSelection) {
    const verified = verifiedSelection.current
    return verified?.api === api && verified.id === id ? verified.selection : fallback
  }
  function consume(next: PreparedOperation) {
    setValue(next); setError(null)
    if (next.cancel_requested || terminalOperation(next)) setCancelError(null)
    if (!terminalOperation(next)) return
    busy.current = false; setPending(false)
    if (terminalId.current !== next.operation_id) { terminalId.current = next.operation_id; terminal.current() }
    if (next.status === 'completed' && completedId.current !== next.operation_id) {
      completedId.current = next.operation_id; completion.current(next.completed_run_ids[0])
    }
  }
  useEffect(() => {
    if (!accepted || cancellation.current || terminalId.current === accepted.receipt.operation_id) return
    const controller = new AbortController(); monitor.current = controller
    let timer: ReturnType<typeof setTimeout> | undefined
    async function refresh() {
      if (controller.signal.aborted) return
      try {
        const id = accepted!.receipt.operation_id
        const selection = selectionFor(id, accepted!.selection)
        const next = await api.researchOperation(id, selection, controller.signal)
        if (controller.signal.aborted) return
        if (selection.settings && next.settingsSnapshotAddress) verifiedSelection.current = { api, id, selection: { ...selection, settings: { ...selection.settings, snapshotAddress: next.settingsSnapshotAddress } } }
        consume(next)
        if (!terminalOperation(next)) timer = setTimeout(() => void refresh(), 1000)
      } catch (caught) {
        if (!controller.signal.aborted) setError(`${preparationError(caught)} The research status is unknown; retry status or request cancellation.`)
      }
    }
    void refresh()
    return () => { controller.abort(); clearTimeout(timer) }
  }, [api, accepted, pollAttempt])

  function restore(selection: ResearchSelection, snapshot: PreparedOperation) {
    if (accepted?.receipt.operation_id === snapshot.operation_id) return false
    post.current?.abort(); monitor.current?.abort(); cancellation.current?.abort()
    cancellation.current = null; setCancelPending(false)
    busy.current = true; setPending(true); setError(null); setCancelError(null); setValue(snapshot)
    setAccepted({ selection, receipt: { request_id: selection.request.request_id, operation_id: snapshot.operation_id, status: snapshot.status } })
    return true
  }
  async function launch(selection: ResearchSelection) {
    if (busy.current) return
    busy.current = true; setPending(true); setError(null); setCancelError(null); setValue(null); setAccepted(null); monitor.current?.abort()
    const controller = new AbortController(); post.current = controller
    try {
      const receipt = isInputPreparation(selection.request)
        ? await api.prepareResearchFromInputs(selection.projectId, selection.graphId, selection.version, inputSettingsPreparation(selection), controller.signal)
        : await api.prepareResearchFromSettings(selection.projectId, selection.graphId, selection.version, settingsPreparation(selection), controller.signal)
      if (!controller.signal.aborted) setAccepted({ receipt, selection })
    } catch (caught) {
      if (!controller.signal.aborted) { busy.current = false; setPending(false); setError(`${preparationError(caught)} No request was confirmed. Retrying unchanged inputs reuses the same request reference.`) }
    }
  }
  function consumeCancellation(next: PreparedOperation) {
    consume(next)
    if (terminalOperation(next)) monitor.current?.abort()
    else setPollAttempt((attempt) => attempt + 1)
  }
  async function cancel() {
    if (!accepted || cancellation.current) return
    const controller = new AbortController(); cancellation.current = controller
    monitor.current?.abort(); setCancelPending(true); setError(null); setCancelError(null)
    try {
      const selection = selectionFor(accepted.receipt.operation_id, accepted.selection)
      const next = await api.cancelResearchOperation(accepted.receipt.operation_id, selection, controller.signal)
      if (controller.signal.aborted) return
      consumeCancellation(next)
    } catch (caught) {
      if (!controller.signal.aborted) { setCancelError(`${preparationError(caught)} Cancellation was not confirmed.`); setPollAttempt((attempt) => attempt + 1) }
    } finally {
      if (!controller.signal.aborted) { cancellation.current = null; setCancelPending(false) }
    }
  }
  return { value, pending, error: cancelError ?? error, cancelPending, accepted: accepted !== null, selection: accepted?.selection, launch, restore, cancel, retry: () => setPollAttempt((attempt) => attempt + 1) }
}
function requestForSetup(previous: { key: string; body: ResearchRequest } | null, key: string,
  body: Omit<ResearchPreparation, 'request_id'> | Omit<InputResearchPreparation, 'request_id'>, completed: boolean) {
  if (previous && previous.key === key && !completed) return previous
  return { key, body: { ...body, request_id: crypto.randomUUID() } }
}
function operationMessage(value: PreparedOperation | null) {
  if (!value) return 'Submitting the research preparation request…'
  if (value.cancel_requested && !terminalOperation(value)) return 'Cancellation requested. Waiting for the worker to stop.'
  const messages: Record<string, string> = { pending: 'Research queued. The worker has not started.',
    running: 'Research running. Preparation and experiment evidence are not complete yet.',
    cancelled: 'Research cancelled. No completed result is being presented.' }
  if (messages[value.status]) return messages[value.status]
  if (value.status === 'failed') return `${value.error?.message ?? 'Research preparation failed.'} Check the saved version and selected dataset before starting a new request.`
  return `Backtest run ${value.completed_run_ids[0]} completed. Loading its persisted result.`
}
function PreparationStatus({ operation }: { operation: ReturnType<typeof usePreparedResearch> }) {
  if (!operation.pending && !operation.value && !operation.error) return null
  return <section aria-label="Research operation" className="workstation-state">
    {(operation.pending || operation.value) && <p role="status">{operationMessage(operation.value)}</p>}
    {operation.error && <p role="alert">{operation.error}</p>}
    {operation.error && operation.accepted && <button onClick={operation.retry}>Retry status</button>}
    {operation.pending && operation.accepted && <button disabled={operation.cancelPending || operation.value?.cancel_requested} onClick={() => void operation.cancel()}>{operation.cancelPending ? 'Requesting cancellation…' : 'Cancel research'}</button>}
  </section>
}

function useResearchRecovery(api: StrategyApi, context: SavedResearchContext | null,
  onRecovered: (selection: ResearchSelection, operation: PreparedOperation) => void) {
  const [snapshot, setSnapshot] = useState<{ context: SavedResearchContext | null; value: Load<ResearchRecovery> }>({ context: null, value: { kind: 'loading' } })
  const [attempt, setAttempt] = useState(0)
  const [cancelError, setCancelError] = useState<string | null>(null)
  const [cancelling, setCancelling] = useState<string | null>(null)
  const selected = useRef('')
  const cancellation = useRef<AbortController | null>(null)
  const recovered = useRef(onRecovered); recovered.current = onRecovered
  useEffect(() => {
    setCancelling(null); setCancelError(null)
    return () => { cancellation.current?.abort(); cancellation.current = null }
  }, [api, context])
  function select(request: RecoverableResearch) {
    if (!request.selection || !request.operation) return
    selected.current = request.operationId
    recovered.current(request.selection, request.operation)
  }
  function refresh() {
    setSnapshot({ context, value: { kind: 'loading' } }); setAttempt((value) => value + 1)
  }
  useEffect(() => {
    if (!context) return
    const controller = new AbortController()
    setSnapshot({ context, value: { kind: 'loading' } })
    void api.researchRecovery(context, controller.signal).then((value) => {
      if (controller.signal.aborted) return
      setSnapshot({ context, value: { kind: 'ready', value } })
      const previous = value.requests.find((item) => item.operationId === selected.current)
      const candidate = previous ?? (value.requests.length === 1 ? value.requests[0] : null)
      if (candidate) select(candidate)
      else selected.current = ''
    }).catch((error: unknown) => {
      if (!controller.signal.aborted) setSnapshot({ context, value: { kind: 'error', message: preparationError(error) } })
    })
    return () => controller.abort()
  }, [api, context, attempt])
  async function cancel(request: RecoverableResearch) {
    if (cancellation.current) return
    const controller = new AbortController(); cancellation.current = controller
    setCancelling(request.operationId); setCancelError(null)
    try {
      await api.cancelRecoveryOperation(request.operationId, controller.signal)
      if (!controller.signal.aborted) refresh()
    } catch (error) {
      if (!controller.signal.aborted) setCancelError(`${preparationError(error)} Cancellation was not confirmed. Retry the lookup or cancellation.`)
    } finally {
      if (!controller.signal.aborted) { cancellation.current = null; setCancelling(null) }
    }
  }
  const state: Load<ResearchRecovery> = snapshot.context === context ? snapshot.value : { kind: 'loading' }
  const canStart = state.kind === 'ready' && state.value.complete && state.value.requests.length === 0
  return { state, canStart, selected: selected.current, cancelling, cancelError, select, cancel, refresh }
}
function RecoveryStatus({ recovery }: { recovery: ReturnType<typeof useResearchRecovery> }) {
  const state = recovery.state
  if (state.kind === 'loading') return <p role="status">Checking active research before allowing a new request…</p>
  if (state.kind === 'error') return <section className="workstation-state"><p role="alert">{state.message} Active research could not be verified. Retry before starting a new request.</p><button onClick={recovery.refresh}>Retry active research</button></section>
  if (state.value.requests.length === 0 && state.value.complete) return null
  return <section className="workstation-state" aria-label="Active research recovery">
    {!state.value.complete && <p role="alert">The active research list is incomplete. Known requests can be inspected, but another request cannot start until a complete lookup succeeds.</p>}
    {state.value.requests.length > 1 && <label>Active research request<TraderSelect label="Active research request" value={recovery.selected} onValueChange={(value) => {
      const request = state.value.requests.find((item) => item.operationId === value)
      if (request) recovery.select(request)
    }} options={[{ value: '', label: 'Choose a request to inspect' }, ...state.value.requests.map((item, index) => ({ value: item.operationId, disabled: !item.selection,
      label: `Request ${index + 1} · ${item.status}${item.selection ? ` · ${item.selection.request.hypothesis.slice(0, 80)}` : ' · setup unavailable'}` }))]} /></label>}
    {state.value.requests.filter((item) => item.reason).map((item) => <div key={item.operationId}><p role="alert">{item.reason}</p><button disabled={recovery.cancelling !== null} onClick={() => void recovery.cancel(item)}>Cancel unavailable request</button></div>)}
    {recovery.cancelError && <p role="alert">{recovery.cancelError}</p>}
    <button onClick={recovery.refresh}>Retry active research</button>
  </section>
}

type ComparisonState = Load<AvailableVisualization> | { kind: 'refused'; dimensions: readonly string[] }
function comparisonPair(first: ExperimentRun | undefined, runs: Load<readonly ExperimentRun[]>, otherId: number | null) {
  if (!first || runs.kind !== 'ready') return null
  const other = runs.value.find((run) => run.run_id === otherId)
  return other ? { first, other } : null
}
async function loadComparison(api: StrategyApi, projectId: string, graphId: string,
  pair: NonNullable<ReturnType<typeof comparisonPair>>, signal: AbortSignal): Promise<ComparisonState | null> {
  const authority = await api.compareVersions(projectId, pair.first.graph.version, pair.other.graph.version,
    pair.first.run_id, pair.other.run_id, graphId, signal)
  if (signal.aborted) return null
  if (authority.incomparable.length) return { kind: 'refused', dimensions: authority.incomparable }
  const result = await api.visualization(projectId, pair.other.run_id, 0, signal)
  if (result.state !== 'AVAILABLE') return { kind: 'error', message: `Run ${pair.other.run_id} visualization is ${result.state.toLowerCase()}.` }
  return { kind: 'ready', value: result }
}
function appendTradePage(base: AvailableVisualization, next: ResearchVisualization): AvailableVisualization {
  if (next.state !== 'AVAILABLE') throw new Error('Trade page became unavailable')
  return { ...base, trade_page: { ...next.trade_page, items: Object.freeze([...base.trade_page.items, ...next.trade_page.items]) } }
}
function currentResultRequest(current: AbortController | null, owned: AbortController) {
  return current === owned && !owned.signal.aborted
}

type SavedInput = ReturnType<typeof parseSavedResearchPolicy>['inputs'][number]
function inputLabel(id: string) { return id.replace(/[_-]+/g, ' ').replace(/^./, (character) => character.toUpperCase()) }
function inputCutoff(value: string) {
  try { return parseResearchCutoff(`${value.length === 16 ? `${value}:00` : value}Z`).replace(/\.0+Z$/, 'Z') } catch { return null }
}
function savedInputReason(inputs: readonly SavedInput[]) {
  if (!inputs.length) return 'Add a market-data input in Build before running.'
  if (inputs.length > 8) return 'This research path supports at most eight market-data inputs.'
  if (inputs.some((input) => input.role !== 'market_frame')) return 'This saved version has an input that cannot use historical market bars.'
  return null
}
function savedInputsReady(state: Load<ReturnType<typeof parseSavedResearchPolicy>>) {
  return state.kind === 'ready' && savedInputReason(state.value.inputs) === null
}
function inputSetupError(inputs: readonly SavedInput[], bindings: Readonly<Record<string, string>>, primary: string, cutoff: string, datasets: readonly ResearchDataset[]) {
  const refusal = savedInputReason(inputs)
  if (refusal) return refusal
  const rows = inputs.map((input) => datasets.find((item) => item.manifest_address === bindings[input.id]))
  if (rows.some((row) => !row)) return 'Choose an available dataset for every input.'
  const selected = rows as ResearchDataset[]
  if (new Set(selected.map((item) => item.manifest_address)).size !== inputs.length) return 'Choose a distinct dataset for each input.'
  const primaryRow = datasets.find((item) => item.manifest_address === bindings[primary])
  if (!inputs.some((input) => input.id === primary) || primaryRow?.asset_class !== 'EQUITY' || primaryRow.backtest_eligibility !== 'ELIGIBLE_Q03') return 'Choose an equity dataset ready for backtesting as the primary input.'
  if (!inputCutoff(cutoff)) return 'Choose a valid shared data cutoff in UTC.'
  return selectedHistoryError(selected)
}
function selectedHistoryError(selected: readonly ResearchDataset[]) {
  if (selected.some((item) => item.backtest_eligibility !== 'ELIGIBLE_Q03' && item.research_compatibility !== 'BENCHMARK_INPUT_ONLY')) return 'One selected dataset is not supported by this research path.'
  if (new Set(selected.map((item) => item.interval)).size !== 1) return 'Choose datasets with the same bar interval.'
  if (Math.max(...selected.map((item) => Date.parse(item.event_start))) > Math.min(...selected.map((item) => Date.parse(item.event_end)))) return 'The selected histories do not overlap. Choose histories covering the same period.'
  return null
}

function optimizationFields(optimization: ResearchValues['optimization'] | null) {
  return optimization ? { optimization } : {}
}
function percentageBands(values: ResearchValues) {
  return values.stop_loss_pct === undefined ? {} : { stop_loss_pct: values.stop_loss_pct, take_profit_pct: values.take_profit_pct }
}
function readyDatasets(datasets: Load<readonly ResearchDataset[]>) { return datasets.kind === 'ready' ? datasets.value : undefined }
type BacktestProps = { api: StrategyApi; project: Project; graph: GraphSummary; scopeContext?: StaticScopeMemberContext
  onPublished?: (version: PublishedGraph) => void; onOpenBuilder?: () => void }

function BacktestWorkspaceBody({ api, project, graph, scopeContext, onPublished, onOpenBuilder }: BacktestProps) {
  const [datasets, setDatasets] = useState<Load<readonly ResearchDataset[]>>({ kind: 'loading' })
  const [runs, setRuns] = useState<Load<readonly ExperimentRun[]>>({ kind: 'loading' })
  const [selectedDataset, setSelectedDataset] = useState('')
  const [appliedScope, setAppliedScope] = useState<string | null>(null)
  const scopeApplied = appliedScope === scopeMemberKey(scopeContext)
  const scopeMember = useScopeMember(api, scopeContext, readyDatasets(datasets), graph.current_version, project.project_id, graph.identifier)
  const [inputDatasets, setInputDatasets] = useState<Readonly<Record<string, string>>>({})
  const [primaryInput, setPrimaryInput] = useState('')
  const [inputAsOf, setInputAsOf] = useState('')
  const [selectedRun, setSelectedRun] = useState<number | null>(null)
  const [visualization, setVisualization] = useState<Load<ResearchVisualization> | null>(null)
  const [tab, setTab] = useState<ResultTab>('performance')
  const [hypothesis, setHypothesis] = useState('Test the saved strategy on historical data.')
  const [capital, setCapital] = useState('100000')
  const [nFolds, setNFolds] = useState('4')
  const [minOosTrades, setMinOosTrades] = useState('10')
  const [minPositiveFoldFraction, setMinPositiveFoldFraction] = useState('60')
  const [seed, setSeed] = useState('0')
  const [optimizationOverride, setOptimizationOverride] = useState<CanonicalOptimizationSettings | null>(null)
  const [showOptimization, setShowOptimization] = useState(false)
  const [fieldErrors, setFieldErrors] = useState<Readonly<Record<string, string>>>({})
  const [feedback, setFeedback] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)
  const [compareRun, setCompareRun] = useState<number | null>(null)
  const [comparison, setComparison] = useState<ComparisonState | null>(null)
  const [tradePending, setTradePending] = useState(false)
  const tradeRequest = useRef<AbortController | null>(null)
  const comparisonRequest = useRef<AbortController | null>(null)
  useEffect(() => () => { tradeRequest.current?.abort(); comparisonRequest.current?.abort() }, [])
  const [policyResult, setPolicyResult] = useState<{ api: StrategyApi; value: Load<ReturnType<typeof parseSavedResearchPolicy>> }>({ api, value: { kind: 'loading' } })
  const savedPolicy: Load<ReturnType<typeof parseSavedResearchPolicy>> = policyResult.api === api ? policyResult.value : { kind: 'loading' }
  const setSavedPolicy = (value: Load<ReturnType<typeof parseSavedResearchPolicy>>) => setPolicyResult({ api, value })
  const [policyAttempt, setPolicyAttempt] = useState(0)
  const [riskPolicy, setRiskPolicy] = useState<RiskPolicy>('none')
  const [settingsResult, setSettingsResult] = useState<{ api: StrategyApi; value: Load<Awaited<ReturnType<StrategyApi['strategyResearchSettings']>>> }>({ api, value: { kind: 'loading' } })
  const settingsPreview: Load<Awaited<ReturnType<StrategyApi['strategyResearchSettings']>>> = settingsResult.api === api ? settingsResult.value : { kind: 'loading' }
  const setSettingsPreview = (value: Load<Awaited<ReturnType<StrategyApi['strategyResearchSettings']>>>) => setSettingsResult({ api, value })
  const [settingsAttempt, setSettingsAttempt] = useState(0)
  const settingsApplied = useRef<StrategyApi | null>(null)
  const requestIdentity = useRef<{ key: string; body: ResearchRequest } | null>(null)
  const [rerunData, setRerunData] = useState<ResearchRequest | null>(null)
  const restoredDataset = useRef<string | null>(null)
  const recoveryContext = useMemo(() => savedPolicy.kind === 'ready' && graph.current_version !== null
    ? { projectId: project.project_id, graphId: graph.identifier, version: graph.current_version, contentAddress: savedPolicy.value.contentAddress, inputIds: savedPolicy.value.inputs.map((input) => input.id) } : null,
  [savedPolicy, project.project_id, graph.identifier, graph.current_version])
  const operation = usePreparedResearch(api, (runId) => {
    chooseRun(runId); setAttempt((value) => value + 1)
  }, (): void => { restoredDataset.current = null; recovery.refresh() })
  const recovery = useResearchRecovery(api, recoveryContext, (selection, snapshot) => {
    if (!operation.restore(selection, snapshot)) return
    const request = selection.request
    settingsApplied.current = api
    if (isInputPreparation(request)) {
      setInputDatasets(Object.fromEntries(request.input_datasets.map((item) => [item.graph_input_id, item.dataset_manifest_address])))
      setPrimaryInput(request.primary_input); setInputAsOf(new Date(request.dataset_as_of).toISOString().slice(0, 19))
    } else { restoredDataset.current = request.dataset_manifest_address; setSelectedDataset(request.dataset_manifest_address) }
    setHypothesis(request.hypothesis); setCapital(String(request.research_capital))
    setNFolds(String(request.n_folds)); setMinOosTrades(String(request.min_trades)); setMinPositiveFoldFraction(String(request.min_positive_fold_frac * 100))
    setSeed(String(request.seed)); setRiskPolicy(request.risk_policy)
    setOptimizationOverride(request.optimization ?? null)
    requestIdentity.current = { key: '', body: request }
    chooseRun(null)
  })
  const pending = operation.pending
  useEffect(() => {
    if (graph.current_version === null) return
    const controller = new AbortController()
    void api.v2Version(project.project_id, graph.identifier, graph.current_version, controller.signal).then((value) => {
      if (controller.signal.aborted) return
      const policy = parseSavedResearchPolicy(value, graph.identifier, graph.current_version!)
      setSavedPolicy({ kind: 'ready', value: policy })
      setPrimaryInput((current) => policy.inputs.some((input) => input.id === current) ? current : policy.inputs.find((input) => input.id === 'frame')?.id ?? policy.inputs[0]?.id ?? '')
    }).catch((error: unknown) => { if (!controller.signal.aborted) setSavedPolicy({ kind: 'error', message: errorMessage(error) }) })
    return () => controller.abort()
  }, [api, project.project_id, graph.identifier, graph.current_version, policyAttempt])
  useEffect(() => {
    if (!recovery.canStart) return
    const controller = new AbortController()
    setSettingsPreview({ kind: 'loading' })
    void api.strategyResearchSettings(project.project_id, graph.identifier, controller.signal).then((value) => {
      if (controller.signal.aborted) return
      setSettingsPreview({ kind: 'ready', value })
      if (settingsApplied.current !== api) {
        settingsApplied.current = api
        setCapital(String(value.values.research_capital)); setSeed(String(value.values.seed))
        setMinOosTrades(String(value.values.min_trades)); setNFolds(String(value.values.n_folds))
        setMinPositiveFoldFraction(String(value.values.min_positive_fold_frac * 100)); setRiskPolicy(value.values.risk_policy)
      }
    }).catch((error: unknown) => { if (!controller.signal.aborted) setSettingsPreview({ kind: 'error', message: errorMessage(error) }) })
    return () => controller.abort()
  }, [api, project.project_id, graph.identifier, recovery.canStart, settingsAttempt])
  const errorSummary = useRef<HTMLDivElement>(null)
  useEffect(() => { const controller = new AbortController()
    Promise.all([api.researchDatasets(project.project_id, controller.signal), api.experiments(project.project_id, controller.signal)])
      .then(([nextDatasets, nextRuns]) => { if (!controller.signal.aborted) { const graphRuns = nextRuns.runs.filter((run) => run.graph.identifier === graph.identifier); setDatasets({ kind: 'ready', value: nextDatasets }); setRuns({ kind: 'ready', value: graphRuns });
        setSelectedDataset((current) => restoredDataset.current ?? (scopeContext ? current : nextDatasets.some((item) => item.manifest_address === current) ? current : nextDatasets.find((item) => item.backtest_eligibility === 'ELIGIBLE_Q03')?.manifest_address ?? nextDatasets[0]?.manifest_address ?? '')); setSelectedRun((current) => current ?? graphRuns[0]?.run_id ?? null) } })
      .catch((error: unknown) => { if (!controller.signal.aborted) { const message = errorMessage(error); setDatasets({ kind: 'error', message }); setRuns({ kind: 'error', message }) } })
    return () => controller.abort() }, [api, project.project_id, graph.identifier, attempt])
  useEffect(() => { if (selectedRun === null) return; const controller = new AbortController()
    api.visualization(project.project_id, selectedRun, 0, controller.signal).then((value) => { if (!controller.signal.aborted) setVisualization({ kind: 'ready', value }) })
      .catch((error: unknown) => { if (!controller.signal.aborted) setVisualization({ kind: 'error', message: errorMessage(error) }) }); return () => controller.abort() }, [api, project.project_id, selectedRun, attempt])
  const savedInputs = savedPolicy.kind === 'ready' ? savedPolicy.value.inputs : []
  const multipleInputs = savedInputs.length > 1
  const inputError = inputSetupError(savedInputs, inputDatasets, primaryInput, inputAsOf, datasets.kind === 'ready' ? datasets.value : [])
  const selectedDatasetRow = datasets.kind === 'ready' ? datasets.value.find((item) => item.manifest_address === selectedDataset) : undefined
  const selectedRunRow = runs.kind === 'ready' ? runs.value.find((item) => item.run_id === selectedRun) : undefined
  const available = !pending && visualization?.kind === 'ready' && visualization.value.state === 'AVAILABLE' ? visualization.value : null
  function canApplyScopeMember() { return !pending && !operation.error && recovery.canStart }
  function scopeSetupReady() { return scopeMemberReady(scopeContext, scopeMember.state, scopeApplied, operation.accepted || Boolean(operation.error)) }
  function applyScopeMember() {
    if (scopeMember.state.kind !== 'ready' || !canApplyScopeMember()) return
    const manifest = scopeMember.state.dataset.manifest_address
    if (multipleInputs) chooseInput(primaryInput, manifest)
    else setSelectedDataset(manifest)
    setAppliedScope(scopeMemberKey(scopeContext))
  }
  useEffect(() => {
    if (!scopeApplied && !operation.accepted && !operation.error && scopeMember.state.kind === 'ready' && recovery.canStart) applyScopeMember()
  }, [scopeMember.state, scopeApplied, operation.accepted, operation.error, recovery.canStart, multipleInputs, primaryInput])
  function preparationData() {
    return rerunData ? (isInputPreparation(rerunData) ? { input_datasets: rerunData.input_datasets, primary_input: rerunData.primary_input, dataset_as_of: rerunData.dataset_as_of } : { dataset_manifest_address: rerunData.dataset_manifest_address, dataset_as_of: rerunData.dataset_as_of }) : multipleInputs ? { input_datasets: savedInputs.map((input) => ({ graph_input_id: input.id, dataset_manifest_address: inputDatasets[input.id] })), primary_input: primaryInput, dataset_as_of: inputCutoff(inputAsOf)! }
      : { dataset_manifest_address: selectedDatasetRow!.manifest_address, dataset_as_of: selectedDatasetRow!.as_of }
  }
  function reviewOptimizationSetup(optimization: ResearchValues['optimization']) {
    if (!optimization || !optimizationInputProblem(optimization)) return true
    setFeedback('Check the optimization parameters, steps and bounds before starting.'); setShowOptimization(true)
    return false
  }
  function submit(event: FormEvent) {
    event.preventDefault()
    if (!canLaunch() || graph.current_version === null || savedPolicy.kind !== 'ready' || settingsPreview.kind !== 'ready') return
    const values = { capital, n_folds: nFolds, min_trades: minOosTrades, min_positive_fold_frac: minPositiveFoldFraction, seed }
    const errors = runFieldErrors(values, hypothesis)
    setFieldErrors(errors)
    if (Object.keys(errors).length) { setFeedback('Check the highlighted run setup fields.'); requestAnimationFrame(() => errorSummary.current?.focus()); return }
    const optimization = optimizationOverride ?? settingsPreview.value.values.optimization
    if (!reviewOptimizationSetup(optimization)) return
    const data = preparationData()
    const bands = percentageBands(settingsPreview.value.values)
    const body = { ...data, ...bands, ...optimizationFields(optimization), hypothesis: hypothesis.trim(), research_capital: Number(capital), seed: Number(seed), min_trades: Number(minOosTrades),
      n_folds: Number(nFolds), min_positive_fold_frac: Number(minPositiveFoldFraction) / 100, risk_policy: riskPolicy }
    const { workspace, strategy } = settingsPreview.value
    const runValues = { research_capital: body.research_capital, seed: body.seed, min_trades: body.min_trades, n_folds: body.n_folds, min_positive_fold_frac: body.min_positive_fold_frac, risk_policy: body.risk_policy,
      ...optimizationFields(optimizationOverride) }
    const runOverrides = Object.fromEntries(Object.entries(runValues).filter(([key, value]) => !sameJson(value, settingsPreview.value.values[key as keyof ResearchValues])))
    const settings = { workspace, strategy, runOverrides }
    const key = JSON.stringify({ body, settings })
    requestIdentity.current = requestForSetup(requestIdentity.current, key, body, terminalOperation(operation.value))
    chooseRun(null)
    void operation.launch({ projectId: project.project_id, graphId: graph.identifier, version: graph.current_version,
      contentAddress: savedPolicy.value.contentAddress, request: requestIdentity.current!.body, settings })
  }
  function reviewSameData() {
    const previous = operation.selection?.request
    if (!previous || operation.value?.status !== 'completed') return
    setRerunData(previous)
    if (isInputPreparation(previous)) {
      setInputDatasets(Object.fromEntries(previous.input_datasets.map((item) => [item.graph_input_id, item.dataset_manifest_address])))
      setPrimaryInput(previous.primary_input); setInputAsOf(new Date(previous.dataset_as_of).toISOString().slice(0, 19))
    } else setSelectedDataset(previous.dataset_manifest_address)
    setHypothesis(previous.hypothesis); settingsApplied.current = null; setSettingsAttempt((value) => value + 1)
    setFeedback('The original data inputs and cutoff are pinned. Review current settings, then start a new run of this saved version.')
  }
  function chooseRun(runId: number | null) {
    tradeRequest.current?.abort(); comparisonRequest.current?.abort()
    setTradePending(false); setComparison(null); setFeedback(null); setSelectedRun(runId)
    setVisualization(runId === null ? null : { kind: 'loading' })
  }
  function chooseComparison(runId: number | null) {
    comparisonRequest.current?.abort(); setComparison(null); setCompareRun(runId)
  }
  async function compare() {
    const pair = comparisonPair(selectedRunRow, runs, compareRun)
    if (!pair) return
    comparisonRequest.current?.abort()
    const controller = new AbortController(); comparisonRequest.current = controller
    const isCurrent = () => currentResultRequest(comparisonRequest.current, controller)
    setComparison({ kind: 'loading' })
    try {
      const result = await loadComparison(api, project.project_id, graph.identifier, pair, controller.signal)
      if (isCurrent() && result) setComparison(result)
    } catch (error) { if (isCurrent()) setComparison({ kind: 'error', message: errorMessage(error) }) }
  }
  async function nextTrades() {
    if (!available || selectedRun === null || available.trade_page.next_cursor === null) return
    tradeRequest.current?.abort()
    const controller = new AbortController(); tradeRequest.current = controller
    const isCurrent = () => currentResultRequest(tradeRequest.current, controller)
    setTradePending(true)
    try {
      const next = await api.visualization(project.project_id, selectedRun, available.trade_page.next_cursor, controller.signal)
      if (!isCurrent()) return
      setVisualization({ kind: 'ready', value: appendTradePage(available, next) })
    } catch (error) { if (isCurrent()) setFeedback(errorMessage(error)) }
    finally { if (isCurrent()) setTradePending(false) }
  }
  const metricRows = useMemo(() => !available ? [] : [
    ['Net return', percent(available.summary.net_return_pct)], ['Close-to-close drawdown', percent(available.summary.max_close_to_close_drawdown_pct)],
    ['Trades', String(available.summary.trades)], ['Charges', money(available.costs.charges_total)], ['OOS folds', String(available.folds.length)],
  ], [available])
  function renderRerun() {
    return <>    {operation.value?.status === 'completed' && <button disabled={pending || !recovery.canStart} onClick={reviewSameData}>Review same-data rerun</button>}
    {selectedRun && !operation.selection && <p>The complete input mapping and cutoff for this saved result are unavailable here. Review the data above before starting another run.</p>}
    {rerunData && <p role="status">Original data and cutoff pinned. <button disabled={pending} onClick={() => setRerunData(null)}>Choose different data</button></p>}</>
  }
  function renderSavedPolicy() {
    const refusal = savedPolicy.kind === 'ready' && savedPolicy.value.inputs.length <= 1 ? savedInputReason(savedPolicy.value.inputs) : null
    return <>{refusal && <p role="status">{refusal}</p>}{savedPolicy.kind === 'loading' && graph.current_version !== null && <p role="status">Checking the saved version and its risk policy…</p>}
        {savedPolicy.kind === 'error' && <div><p role="alert">{savedPolicy.message} The saved version must be verified before starting research.</p><button type="button" onClick={() => { setSavedPolicy({ kind: 'loading' }); setPolicyAttempt((value) => value + 1) }}>Retry saved version</button></div>}</>
  }
  function datasetOptions() {
    return [{ value: '', label: 'Select history ready for backtesting' },
      ...(selectedDataset && !selectedDatasetRow ? [{ value: selectedDataset, label: 'Requested dataset · not in the current list' }] : []),
      ...(datasets.kind === 'ready' ? datasets.value.map((item) => ({ value: item.manifest_address,
        label: `${plainProduct(item.canonical_instrument_label)} · ${item.interval} · ${item.bar_count.toLocaleString()} bars${item.backtest_eligibility === 'UNAVAILABLE' ? ` · ${datasetAvailability(item)}` : ''}` })) : [])]
  }

  function canLaunch() {
    return scopeSetupReady() && !pending && (multipleInputs ? inputError === null : selectedDatasetRow?.backtest_eligibility === 'ELIGIBLE_Q03') && graph.current_version !== null
      && savedInputsReady(savedPolicy) && recovery.canStart && settingsPreview.kind === 'ready'
  }
  function renderSettingsStatus() {
    return <>
        {recovery.canStart && settingsPreview.kind === 'loading' && <p role="status">Loading research defaults…</p>}
        {recovery.canStart && settingsPreview.kind === 'error' && <p role="alert">{settingsPreview.message} Research defaults must be available before a new run can start.</p>}
        {recovery.canStart && <button type="button" disabled={pending || settingsPreview.kind === 'loading'} onClick={() => setSettingsAttempt((value) => value + 1)}>Reload research defaults</button>}
        {recovery.canStart && settingsPreview.kind === 'ready' && settingsPreview.value.values.stop_loss_pct !== undefined && <p>Percentage exits: stop loss {100 * settingsPreview.value.values.stop_loss_pct}%, take profit {100 * (settingsPreview.value.values.take_profit_pct ?? 0)}%. Zero disables the band. Close confirmed; filled at next open. Change these in Settings before starting.</p>}
        {recovery.canStart && settingsPreview.kind === 'ready' && !showOptimization && (optimizationOverride ?? settingsPreview.value.values.optimization)?.enabled && <p>Development search is enabled. Choose optimization parameters below to review the values for this run.</p>}
        {recovery.canStart && settingsPreview.kind === 'ready' && <p>Run setup starts from your saved research settings. Changes here apply only to this run.</p>}
    </>
  }
  function chooseInput(id: string, manifest: string) {
    const next = { ...inputDatasets, [id]: manifest }
    setInputDatasets(next)
    if (datasets.kind !== 'ready' || inputAsOf) return
    const rows = savedInputs.map((input) => datasets.value.find((item) => item.manifest_address === next[input.id]))
    if (rows.every((row) => row)) setInputAsOf(new Date(Math.max(...rows.map((row) => Date.parse(row!.as_of)))).toISOString().slice(0, 19))
  }
  function renderInputDatasets() {
    const disabled = pending || Boolean(rerunData) || datasets.kind !== 'ready'
    return <fieldset disabled={disabled}><legend>Data inputs</legend>
      {savedInputs.map((input) => {
        const selected = datasets.kind === 'ready' ? datasets.value.find((item) => item.manifest_address === inputDatasets[input.id]) : undefined
        return <div key={input.id}><label>{inputLabel(input.id)} dataset<TraderSelect label={`${inputLabel(input.id)} dataset`} value={inputDatasets[input.id] ?? ''} disabled={disabled} onValueChange={(value) => chooseInput(input.id, value)} options={[
          { value: '', label: 'Choose history' },
          ...(inputDatasets[input.id] && !selected ? [{ value: inputDatasets[input.id], label: 'Requested dataset · not in the current list' }] : []),
          ...(datasets.kind === 'ready' ? datasets.value.map((item) => ({ value: item.manifest_address, label: `${plainProduct(item.canonical_instrument_label)} · ${item.interval} · ${item.bar_count.toLocaleString()} bars` })) : []),
        ]} /></label>{selected && <DatasetFacts item={selected} inputSet />}</div>
      })}
      <label>Primary input<TraderSelect label="Primary input" value={primaryInput} onValueChange={setPrimaryInput} disabled={disabled} options={savedInputs.map((input) => ({ value: input.id, label: inputLabel(input.id) }))} /></label>
      <label>Data available as of (UTC)<input type="datetime-local" step="1" value={inputAsOf} onChange={(event) => setInputAsOf(event.target.value)} /></label>
      <p>One cutoff applies to every input. Bar alignment, warmup and required fields are checked when the run is prepared.</p>
      {inputError && <p role="status">{inputError}</p>}
    </fieldset>
  }
  function renderLaunch() {
    const runSetupDisabled = pending || (settingsApplied.current !== api && settingsPreview.kind !== 'ready')
    return <div className="backtest-launch"><form noValidate onSubmit={(event) => void submit(event)}>{multipleInputs ? renderInputDatasets() : <><label>Historical dataset<TraderSelect label="Historical dataset" value={selectedDataset} onValueChange={setSelectedDataset} disabled={pending || Boolean(rerunData) || datasets.kind !== 'ready'} options={datasetOptions()} /></label>
        {selectedDatasetRow && <DatasetFacts item={selectedDatasetRow} />}</>}
        <label>Hypothesis<textarea value={hypothesis} required maxLength={4000} disabled={pending} aria-invalid={Boolean(fieldErrors.hypothesis)} onChange={(event) => setHypothesis(event.target.value)} />{fieldErrors.hypothesis && <small role="alert">{fieldErrors.hypothesis}</small>}</label>
        <fieldset className="run-setup" disabled={runSetupDisabled}><legend>Run setup</legend><div className="run-setup-grid">
          <NumericRunField label="Research capital (INR)" id="capital" value={capital} minimum={1} maximum={1000000000} error={fieldErrors.capital} onChange={setCapital} />
          <NumericRunField label="Walk-forward folds" id="folds" value={nFolds} minimum={2} maximum={32} error={fieldErrors.n_folds} onChange={setNFolds} />
          <NumericRunField label="Minimum out-of-sample trades" id="trades" value={minOosTrades} minimum={1} maximum={100000} error={fieldErrors.min_trades} onChange={setMinOosTrades} />
          <NumericRunField label="Minimum profitable folds (%)" id="positive" value={minPositiveFoldFraction} minimum={0} maximum={100} error={fieldErrors.min_positive_fold_frac} onChange={setMinPositiveFoldFraction} step={0.01} />
          <NumericRunField label="Reproducibility seed" id="seed" value={seed} minimum={0} maximum={2147483647} error={fieldErrors.seed} onChange={setSeed} />
        </div><label>Research risk policy<TraderSelect label="Research risk policy" value={riskPolicy} onValueChange={(value) => setRiskPolicy(value as RiskPolicy)} disabled={runSetupDisabled || savedPolicy.kind !== 'ready'} options={[{ value: 'none', label: 'None — authored signal exits only' }, { value: 'pine-v4-ratchet/1', label: 'Pine V4 ratchet stops' }, { value: 'pine-v4-reversal/1', label: 'V4 ratchet with next-open reversal (one unit)' }]} /></label>
        {savedPolicy.kind === 'ready' && savedPolicy.value.riskPolicy === 'pine-v4-ratchet/1' && <p>This preset recommends ratchet stops. Choose None to test its signal exits alone.</p>}
        <details className="run-assumptions"><summary>Costs and validation</summary><p>Research charges apply, with 5 basis points of slippage and a stress check at twice that amount. {replayDescription(riskPolicy)}</p><p>Walk-forward folds evaluate the research setup. Choose bounded development search below. Monte Carlo is not available in this form.</p></details>
        {renderOptimizationSetup(runSetupDisabled)}
        </fieldset>
        {renderSavedPolicy()}
        {renderSettingsStatus()}
        <button aria-label={pending ? 'Running backtest' : `Run version ${graph.current_version ?? 'unpublished'}`} className="workstation-primary" disabled={!canLaunch()}><FlaskConical aria-hidden="true" />{pending ? 'Research in progress…' : 'Start backtest'}</button></form>
      <aside aria-label="Run selector"><h3>Saved runs</h3>{runs.kind === 'loading' ? <p role="status">Loading runs…</p> : runs.kind === 'error' ? <p role="alert">{runs.message}</p> : runs.value.length === 0 ? <p>No backtests for this strategy yet.</p> : <label>Selected run<TraderSelect label="Selected run" value={String(selectedRun ?? '')} onValueChange={(value) => chooseRun(Number(value))} options={runs.value.map((run) => ({ value: String(run.run_id), label: `Run ${run.run_id} · Version ${run.graph.version} · ${run.status}` }))} /></label>}
        {selectedRunRow && <p>Saved version {selectedRunRow.graph.version} · {selectedRunRow.evidence_state === 'verified' ? 'Result verified' : 'Result not verified'}</p>}</aside></div>
  }
  function renderOptimizationSetup(disabled: boolean) {
    const inherited = settingsPreview.kind === 'ready' ? settingsPreview.value.values.optimization : undefined
    return <><button type="button" aria-expanded={showOptimization} onClick={() => setShowOptimization((current) => !current)}>{showOptimization ? 'Hide optimization parameters' : 'Choose optimization parameters'}</button>
      {showOptimization && <OptimizationSettingsFields api={api} strategy={{ projectId: project.project_id, graphId: graph.identifier }} currentVersion={graph.current_version}
        value={optimizationOverride ?? inherited ?? disabledOptimization()} disabled={disabled}
        onChange={(update) => setOptimizationOverride((current) => update(current ?? inherited ?? disabledOptimization()))} />}</>
  }

  function renderTrades(available: AvailableVisualization) {
    return <section className="result-plane"><h3>Persisted trade ledger</h3>{available.trade_page.items.length ? <><div className="table-scroll"><table><thead><tr><th>Direction</th><th>Entry UTC</th><th>Exit UTC</th><th>Gross P&amp;L</th><th>Charges</th><th>Net P&amp;L</th><th>MAE</th><th>Exit</th></tr></thead><tbody>{available.trade_page.items.map((item) => <tr key={String(item.cursor)}><td>{plainProduct(String(item.direction))}</td><td>{new Date(Number(item.entry_time) * 1000).toISOString()}</td><td>{new Date(Number(item.exit_time) * 1000).toISOString()}</td><td>{money(item.gross_pnl)}</td><td>{money(item.charges)}</td><td>{money(item.net_pnl)}</td><td>{percent(item.mae_pct)}</td><td>{plainProduct(String(item.exit_reason))}</td></tr>)}</tbody></table></div>{available.trade_page.next_cursor !== null && <button onClick={() => void nextTrades()} disabled={tradePending}>{tradePending ? 'Loading next trades…' : `Load next trades after ${available.trade_page.next_cursor}`}</button>}<p>{available.trade_page.items.length} of {available.trade_page.total} persisted trades loaded.</p></> : <p>{plainProduct(available.trade_page.detail_reason ?? 'This run contains zero trades.')}</p>}</section>
  }

  function renderComparison(available: AvailableVisualization) {
    return <section className="result-plane"><h3>Comparable run overlay</h3><div className="compare-control"><label>Second run<TraderSelect label="Second run" value={String(compareRun ?? '')} onValueChange={(value) => chooseComparison(value ? Number(value) : null)} options={[{ value: '', label: 'Select one run' }, ...(runs.kind === 'ready' ? runs.value.filter((run) => run.run_id !== selectedRun).map((run) => ({ value: String(run.run_id), label: `Run ${run.run_id}` })) : [])]} /></label><button disabled={compareRun === null} onClick={() => void compare()}>Check and compare</button></div>
        {comparison?.kind === 'loading' && <p role="status">Checking comparison dimensions…</p>}{comparison?.kind === 'error' && <p role="alert">{comparison.message}</p>}{comparison?.kind === 'refused' && <div className="workstation-unavailable"><h4>Runs are incomparable</h4><ul>{comparison.dimensions.map((item) => <li key={item}>{comparisonReasons[item] ?? 'These runs do not have matching comparison conditions.'}</li>)}</ul></div>}{comparison?.kind === 'ready' && <ResearchSeriesChart equity={available.series.net_equity.points} drawdown={available.series.drawdown.points} comparison={{ label: `run ${compareRun}`, equity: comparison.value.series.net_equity.points, drawdown: comparison.value.series.drawdown.points }} />}</section>
  }

  function renderResults(available: AvailableVisualization) {
    return <><div className="metric-rail">{metricRows.map(([label, value]) => <div key={label}><span>{label}</span><strong>{value}</strong></div>)}</div><nav className="result-tabs" aria-label="Research result views">{(['performance', 'market', 'trades', 'costs', 'oos', 'compare'] as ResultTab[]).map((item) => <button key={item} aria-current={tab === item ? 'page' : undefined} onClick={() => setTab(item)}>{item === 'oos' ? 'OOS' : item === 'market' ? 'Market context' : item[0].toUpperCase() + item.slice(1)}</button>)}</nav>
      {tab === 'performance' && <ResearchSeriesChart equity={available.series.net_equity.points} drawdown={available.series.drawdown.points} events={available.series.trade_events} />}
      {tab === 'market' && selectedRun !== null && <MarketContext api={api} projectId={project.project_id} runId={selectedRun} tradeEvents={available.series.trade_events} />}
      {tab === 'trades' && renderTrades(available)}
      {tab === 'costs' && <section className="result-plane"><h3>Trading costs</h3><dl><div><dt>Total charges deducted from net equity</dt><dd>{money(available.costs.charges_total)}</dd></div><div><dt>Itemized charges</dt><dd>Unavailable for this result</dd></div><div><dt>Slippage</dt><dd>Stress scenario · {String(available.costs.slippage.bps)} bps × {String(available.costs.slippage.multiplier)} · mean stressed net {money(available.costs.slippage.mean_stressed_net)} · {available.costs.slippage.passed ? 'passed' : 'failed'}</dd></div></dl></section>}
      {tab === 'oos' && <section className="result-plane"><h3>Out-of-sample folds</h3>{available.folds.length ? <div className="table-scroll"><table><thead><tr><th>Fold / role</th><th>UTC range</th><th>Bars</th><th>Trades</th><th>Net P&amp;L</th><th>Return</th><th>Expectancy</th><th>Drawdown</th><th>Gate results</th></tr></thead><tbody>{available.folds.map((fold) => <tr key={String(fold.fold_index)}><td>{String(fold.fold_index)} · {String(fold.role)}</td><td>{new Date(Number(fold.start_time) * 1000).toISOString()} → {new Date(Number(fold.end_time) * 1000).toISOString()}</td><td>{String(fold.bars)}</td><td>{String(fold.oos_trades)}</td><td>{money(fold.oos_net_pnl)}</td><td>{percent(fold.oos_return_pct)}</td><td>{money(fold.oos_expectancy)}</td><td>{percent(fold.oos_max_drawdown_pct)}</td><td><FoldGates value={fold.gate_results} /></td></tr>)}</tbody></table></div> : <p>Fold evidence is unavailable for this result.</p>}</section>}
      {tab === 'compare' && renderComparison(available)}
      </>
  }

  return <section className="backtest-workstation" aria-labelledby="backtest-title">
    <header className="workstation-command"><div><h2 id="backtest-title">Backtest</h2></div><button disabled={pending} onClick={() => { setDatasets({ kind: 'loading' }); setRuns({ kind: 'loading' }); chooseRun(selectedRun); setAttempt((value) => value + 1) }}><RefreshCw aria-hidden="true" />Refresh records</button></header>
    <div className="backtest-studio"><aside className="backtest-setup" aria-label="Backtest setup">
    <details className="research-import"><summary>Import daily CSV</summary><DailyCsvImport key={project.project_id} api={api} projectId={project.project_id} disabled={pending} onImported={() => setAttempt((value) => value + 1)} /></details>
    {savedPolicy.kind === 'ready' && <RecoveryStatus recovery={recovery} />}
    <PreparationStatus operation={operation} />
    {renderRerun()}
    <ScopeMemberStatus state={scopeMember.state} applied={scopeApplied} canApply={canApplyScopeMember()} onApply={applyScopeMember} retry={scopeMember.retry} />
    {renderLaunch()}
    {datasets.kind === 'ready' && datasets.value.length === 0 && <div className="workstation-unavailable"><h3>No dataset is ready for backtesting</h3><p>Import a daily equity CSV above to start. Keep volume unmapped when the file does not contain it.</p></div>}
    </aside><div className="backtest-results" aria-label="Backtest results">
    {!available && !visualization && <div className="backtest-empty"><h3>Your results appear here</h3><p>Select compatible history and run a saved strategy version.</p></div>}
    {available && renderResults(available)}
    {selectedRun !== null && <CanonicalOptimizationResults api={api} projectId={project.project_id} runId={selectedRun} onPublished={onPublished} onOpenBuilder={onOpenBuilder} />}
    {visualization && !available && <ResultState visualization={visualization} retry={() => setAttempt((value) => value + 1)} />}
    </div></div>
    {feedback && <div ref={errorSummary} tabIndex={-1} className="workstation-feedback" role="status">{feedback}</div>}
  </section>
}


export function BacktestWorkspace(props: BacktestProps) {
  return <BacktestWorkspaceBody key={`${props.project.project_id}:${props.graph.identifier}:${props.graph.current_version}`} {...props} />
}
