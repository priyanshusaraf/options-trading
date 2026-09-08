import { ContractError, disabledOptimization, parseOptimizationSettings, sameJson, parseResearchSettingsRevision, type ResearchSettingsRevision, type ResearchValues } from '../shell/contracts'

export type RiskPolicy = 'none' | 'pine-v4-ratchet/1' | 'pine-v4-reversal/1'
export type ResearchPreparation = Readonly<{
  request_id: string; dataset_manifest_address: string; dataset_as_of: string; hypothesis: string
  research_capital: number; seed: number; min_trades: number; n_folds: number
  stop_loss_pct?: number; take_profit_pct?: number; optimization?: ResearchValues['optimization']
  min_positive_fold_frac: number; risk_policy: RiskPolicy
}>
export type InputDataset = Readonly<{ graph_input_id: string; dataset_manifest_address: string }>
export type InputResearchPreparation = Omit<ResearchPreparation, 'dataset_manifest_address'> & Readonly<{ input_datasets: readonly InputDataset[]; primary_input: string }>
export type ResearchRequest = ResearchPreparation | InputResearchPreparation
export type SettingsSelection = Readonly<{ workspace: ResearchSettingsRevision; strategy: ResearchSettingsRevision; runOverrides: Partial<ResearchValues>; snapshotAddress?: string }>
export type SettingsPreparation = Pick<ResearchPreparation, 'request_id' | 'dataset_manifest_address' | 'dataset_as_of' | 'hypothesis'> & Readonly<{ expected_workspace_revision: number; expected_strategy_revision: number; run_overrides: Partial<ResearchValues> }>
export type InputSettingsPreparation = Omit<SettingsPreparation, 'dataset_manifest_address'> & Readonly<{ input_datasets: readonly InputDataset[]; primary_input: string }>
export type ResearchSelection = Readonly<{ projectId: string; graphId: string; version: number; contentAddress: string; request: ResearchRequest; settings?: SettingsSelection }>

export function settingsPreparation(selection: ResearchSelection): SettingsPreparation {
  if (!selection.settings || isInputPreparation(selection.request)) throw new ContractError()
  const { request_id, dataset_manifest_address, dataset_as_of, hypothesis } = selection.request
  return { request_id, dataset_manifest_address, dataset_as_of, hypothesis,
    expected_workspace_revision: selection.settings.workspace.revision, expected_strategy_revision: selection.settings.strategy.revision,
    run_overrides: selection.settings.runOverrides }
}
export function isInputPreparation(request: ResearchRequest): request is InputResearchPreparation {
  return 'input_datasets' in request
}
export function inputSettingsPreparation(selection: ResearchSelection): InputSettingsPreparation {
  if (!selection.settings || !isInputPreparation(selection.request)) throw new ContractError()
  const { request_id, input_datasets, primary_input, dataset_as_of, hypothesis } = selection.request
  validateInputSelection(input_datasets, primary_input)
  return { request_id, input_datasets, primary_input, dataset_as_of: parseResearchCutoff(dataset_as_of), hypothesis,
    expected_workspace_revision: selection.settings.workspace.revision, expected_strategy_revision: selection.settings.strategy.revision,
    run_overrides: selection.settings.runOverrides }
}
export type PreparationReceipt = Readonly<{ request_id: string; operation_id: string; status: OperationStatus }>
export type OperationStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
export type PreparedOperation = Readonly<{
  operation_id: string; status: OperationStatus; stage: string; completed_run_ids: readonly number[]
  settingsSnapshotAddress?: string
  cancel_requested: boolean; error: Readonly<{ code: string; message: string }> | null
}>

function record(value: unknown): Record<string, unknown> {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) throw new ContractError()
  return value as Record<string, unknown>
}
function text(value: unknown, limit = 2000): string {
  if (typeof value !== 'string' || !value.length || value.length > limit) throw new ContractError()
  return value
}
function address(value: unknown): string {
  if (!/^sha256:[a-f0-9]{64}$/.test(text(value, 71))) throw new ContractError()
  return value as string
}
export function operationId(value: unknown): string {
  if (!/^[a-f0-9]{64}$/.test(text(value, 64))) throw new ContractError()
  return value as string
}
function status(value: unknown): OperationStatus {
  const result = text(value, 16)
  if (!['pending', 'running', 'completed', 'failed', 'cancelled'].includes(result)) throw new ContractError()
  return result as OperationStatus
}
function matches(value: Record<string, unknown>, expected: Record<string, unknown>) {
  if (!Object.entries(expected).every(([key, entry]) => value[key] === entry)) throw new ContractError()
}
function savedInputs(value: unknown) {
  if (!Array.isArray(value)) throw new ContractError()
  const inputs = value.map((raw) => {
    const input = record(raw)
    matches(input, { direction: 'input' })
    return Object.freeze({ id: text(input.port_id, 128), role: text(input.semantic_role, 128) })
  })
  if (new Set(inputs.map((input) => input.id)).size !== inputs.length) throw new ContractError()
  return Object.freeze(inputs.sort((a, b) => a.id < b.id ? -1 : 1))
}
export function parseSavedResearchPolicy(value: unknown, graphId: string, version: number) {
  const item = record(value)
  matches(item, { format_version: 2, graph_identifier: graphId, graph_version: version })
  const document = record(item.document)
  matches(document, { format_version: 2, strategy_id: graphId })
  const tags = record(document.metadata).tags
  if (!Array.isArray(tags) || tags.length > 100 || !tags.every((tag) => typeof tag === 'string')) throw new ContractError()
  return Object.freeze({ contentAddress: address(item.content_address), inputs: savedInputs(document.graph_inputs),
    riskPolicy: tags.includes('expanding-z-v4') ? 'pine-v4-ratchet/1' as const : 'none' as const })
}
export function parsePreparationReceipt(value: unknown, requestId: string): PreparationReceipt {
  const item = record(value), id = operationId(item.operation_id)
  matches(item, { request_id: requestId, status_url: `/api/research/operations/${id}`, cancel_url: `/api/research/operations/${id}/cancel` })
  return Object.freeze({ request_id: requestId, operation_id: id, status: status(item.status) })
}
function operationSelection(plan: unknown, expected: ResearchSelection) {
  return isInputPreparation(expected.request) ? inputOperationSelection(plan, expected, expected.request)
    : scalarOperationSelection(plan, expected, expected.request)
}
function scalarOperationSelection(plan: unknown, expected: ResearchSelection, request: ResearchPreparation) {
  const item = record(plan)
  if (!expected.settings && expected.request.risk_policy === 'pine-v4-reversal/1') throw new ContractError()
  matches(item, { schema: expected.settings ? 'v2-graph-research-operation/3' : 'v2-graph-research-operation/2', experiment_count: 1 })
  if (!Array.isArray(item.v2_graphs) || item.v2_graphs.length !== 1) throw new ContractError()
  const graph = record(item.v2_graphs[0])
  matches(graph, { project_id: expected.projectId, graph_identifier: expected.graphId, graph_version: expected.version,
    content_address: expected.contentAddress, request_id: request.request_id, dataset_manifest_address: request.dataset_manifest_address })
  if (Date.parse(text(graph.dataset_as_of)) !== Date.parse(request.dataset_as_of)) throw new ContractError()
  const { request_id: _id, dataset_manifest_address: _manifest, dataset_as_of: _asOf, risk_policy, stop_loss_pct: _stop, take_profit_pct: _target, optimization: _optimization, ...experiment } = request
  const actualExperiment = record(graph.experiment)
  if (Object.keys(actualExperiment).length !== Object.keys(experiment).length) throw new ContractError()
  matches(actualExperiment, experiment)
  matches(record(record(graph.execution_policy).risk), { risk_policy, capital: request.research_capital })
  if (expected.settings) {
    validateSettingsExecution(graph.execution_policy, request)
    return validateSettingsSnapshot(graph, expected.settings, request)
  }
}
function validateInputSelection(input: unknown, primary: unknown): readonly InputDataset[] {
  if (!Array.isArray(input) || input.length < 2 || input.length > 8) throw new ContractError()
  const inputs = input.map((raw) => {
    const item = record(raw)
    closed(item, ['graph_input_id', 'dataset_manifest_address'])
    return { graph_input_id: text(item.graph_input_id, 128), dataset_manifest_address: address(item.dataset_manifest_address) }
  })
  const ids = inputs.map((item) => item.graph_input_id)
  if (new Set(ids).size !== ids.length || new Set(inputs.map((item) => item.dataset_manifest_address)).size !== inputs.length) throw new ContractError()
  if (!ids.includes(text(primary, 128)) || ids.some((id, index) => index > 0 && ids[index - 1] >= id)) throw new ContractError()
  return Object.freeze(inputs)
}
function inputOperationSelection(plan: unknown, expected: ResearchSelection, request: InputResearchPreparation) {
  if (!expected.settings) throw new ContractError()
  const item = record(plan)
  matches(item, { schema: 'v2-graph-research-operation/4', experiment_count: 1 })
  if (!Array.isArray(item.v2_graphs) || item.v2_graphs.length !== 1) throw new ContractError()
  const graph = record(item.v2_graphs[0])
  matches(graph, { project_id: expected.projectId, graph_identifier: expected.graphId, graph_version: expected.version,
    content_address: expected.contentAddress, request_id: request.request_id, primary_input: request.primary_input })
  if (Object.hasOwn(graph, 'dataset_manifest_address')) throw new ContractError()
  const inputs = validateInputSelection(graph.input_datasets, graph.primary_input)
  const selected = validateInputSelection(request.input_datasets, request.primary_input)
  if (JSON.stringify(inputs) !== JSON.stringify(selected) || Date.parse(parseResearchCutoff(graph.dataset_as_of)) !== Date.parse(parseResearchCutoff(request.dataset_as_of))) throw new ContractError()
  const { request_id: _id, input_datasets: _inputs, primary_input: _primary, dataset_as_of: _asOf, risk_policy, stop_loss_pct: _stop, take_profit_pct: _target, optimization: _optimization, ...experiment } = request
  equalFields(record(graph.experiment), experiment)
  matches(record(record(graph.execution_policy).risk), { risk_policy, capital: request.research_capital })
  validateSettingsExecution(graph.execution_policy, request)
  return validateSettingsSnapshot(graph, expected.settings, request)
}
function validateProtectiveBand(policy: Record<string, unknown>, risk: Record<string, unknown>, request: ResearchRequest) {
  const active = Boolean(request.stop_loss_pct || request.take_profit_pct)
  matches(policy, { schema: active ? 'v2-research-execution-policy/2' : 'v2-research-execution-policy/1' })
  if (active) matches(risk, { schema: 'research-risk-assumption/2' })
  if (active) equalFields(record(risk.protective_band), { schema: 'research-percentage-exit-policy/1',
    stop_loss_pct: request.stop_loss_pct ?? 0, take_profit_pct: request.take_profit_pct ?? 0,
    basis: 'slipped-entry-fill', trigger: 'completed-close-after-entry-bar', fill: 'next-bar-open-adverse-slippage',
    intrabar: 'not-evaluated', precedence: 'stop-target-ratchet-strategy' })
  else if (Object.hasOwn(risk, 'protective_band')) throw new ContractError()
}
function validateSettingsExecution(input: unknown, request: ResearchRequest) {
  const riskPolicy = request.risk_policy
  const policy = record(input), risk = record(policy.risk), overlay = record(risk.overlay)
  const reversal = riskPolicy === 'pine-v4-reversal/1'
  validateProtectiveBand(policy, risk, request)
  matches(risk, { sizing_model: reversal ? 'fixed_unit_v1' : 'one_lot_or_cash_budget_v1',
    fill: reversal ? 'next-bar-open-reversal/1' : 'existing-next-bar-open' })
  matches(overlay, { schema: reversal ? 'v2-research-risk-policy/2' : 'v2-research-risk-policy/1', policy_id: riskPolicy })
  if (reversal) matches(overlay, { replay_policy: 'pine-reversal-fixed-unit/1' })
  else if (Object.hasOwn(overlay, 'replay_policy')) throw new ContractError()
}
const settingKeys = ['research_capital', 'seed', 'min_trades', 'n_folds', 'min_positive_fold_frac', 'risk_policy'] as const
function closed(value: Record<string, unknown>, names: readonly string[]) {
  if (Object.keys(value).length !== names.length || !names.every((key) => Object.hasOwn(value, key))) throw new ContractError()
}
function equalFields(actual: Record<string, unknown>, expected: Record<string, unknown>) {
  closed(actual, Object.keys(expected)); if (!sameJson(actual, expected)) throw new ContractError()
}
function snapshotKeys(snapshot: Record<string, unknown>): (keyof ResearchValues)[] {
  if (snapshot.schema === 'research-settings-snapshot/1') return [...settingKeys]
  return [...settingKeys, 'stop_loss_pct', 'take_profit_pct', ...(snapshot.schema === 'research-settings-snapshot/3' ? ['optimization'] as const : [])]
}
function snapshotSelection(graph: Record<string, unknown>): SettingsSelection {
  const snapshot = record(graph.settings_snapshot)
  closed(snapshot, ['schema', 'owner_id', 'graph_identifier', 'workspace', 'strategy', 'run_overrides', 'values', 'sources', 'content_address'])
  if (!['research-settings-snapshot/1', 'research-settings-snapshot/2', 'research-settings-snapshot/3'].includes(String(snapshot.schema))) throw new ContractError()
  matches(snapshot, { owner_id: graph.owner_id, graph_identifier: graph.graph_identifier })
  const graphId = text(graph.graph_identifier, 128)
  const workspace = parseResearchSettingsRevision(snapshot.workspace, null)
  const strategy = parseResearchSettingsRevision(snapshot.strategy, graphId)
  const version = Number(String(snapshot.schema).split('/').at(-1))
  if ([workspace, strategy].some((row) => Number(row.schema?.split('/').at(-1)) > version)) throw new ContractError()
  if (workspace.owner_id !== snapshot.owner_id || strategy.owner_id !== snapshot.owner_id) throw new ContractError()
  const runOverrides = { ...record(snapshot.run_overrides) }
  if (Object.keys(runOverrides).some((key) => !snapshotKeys(snapshot).includes(key as keyof ResearchValues))) throw new ContractError()
  if (Object.hasOwn(runOverrides, "optimization")) runOverrides.optimization = parseOptimizationSettings(runOverrides.optimization)
  return Object.freeze({ workspace, strategy, runOverrides: Object.freeze({ ...runOverrides }) as Partial<ResearchValues>, snapshotAddress: address(snapshot.content_address) })
}
function sameRevision(actual: ResearchSettingsRevision, expected: ResearchSettingsRevision) {
  matches(actual, { owner_id: expected.owner_id, graph_identifier: expected.graph_identifier, revision: expected.revision,
    enabled: expected.enabled, content_address: expected.content_address })
  equalFields(actual.values, expected.values)
}
function settingSource(key: keyof ResearchValues, run: Partial<ResearchValues>, strategy: Partial<ResearchValues>) {
  if (Object.hasOwn(run, key)) return 'run'
  return Object.hasOwn(strategy, key) ? 'strategy' : 'workspace'
}
function requestedSetting(request: ResearchRequest, key: keyof ResearchValues) {
  if (key === "optimization") return request.optimization ?? disabledOptimization()
  return request[key] ?? (["stop_loss_pct", "take_profit_pct"].includes(key) ? 0 : undefined)
}
function effectiveSnapshotValues(snapshot: Record<string, unknown>, actual: SettingsSelection, strategyValues: Partial<ResearchValues>) {
  return { ...(snapshot.schema !== "research-settings-snapshot/1" ? { stop_loss_pct: 0, take_profit_pct: 0 } : {}), ...(snapshot.schema === "research-settings-snapshot/3" ? { optimization: disabledOptimization() } : {}), ...actual.workspace.values, ...strategyValues, ...actual.runOverrides }
}
function validateSettingsSnapshot(graph: Record<string, unknown>, expected: SettingsSelection, request: ResearchRequest) {
  const actual = snapshotSelection(graph), snapshot = record(graph.settings_snapshot)
  sameRevision(actual.workspace, expected.workspace); sameRevision(actual.strategy, expected.strategy)
  equalFields(actual.runOverrides, expected.runOverrides)
  if (expected.snapshotAddress && actual.snapshotAddress !== expected.snapshotAddress) throw new ContractError()
  const strategyValues = actual.strategy.enabled ? actual.strategy.values : {}
  const effective = effectiveSnapshotValues(snapshot, actual, strategyValues)
  const values = record(snapshot.values), sources = record(snapshot.sources)
  const names = snapshotKeys(snapshot)
  closed(values, names); closed(sources, names)
  if (snapshot.schema === "research-settings-snapshot/3") {
    parseOptimizationSettings(values.optimization)
    equalFields(record(record(graph.execution_policy).slippage), { schema: "research-slippage-assumption/1", basis_points: 5, challenge_multiplier: 2, application: "existing-research-kernel" })
  }
  for (const key of names) {
    if (!sameJson(values[key], effective[key]) || !sameJson(values[key], requestedSetting(request, key))) throw new ContractError()
    const source = settingSource(key, actual.runOverrides, strategyValues)
    if (sources[key] !== source) throw new ContractError()
  }
  return actual.snapshotAddress
}
function completedRuns(value: unknown, currentStatus: OperationStatus) {
  if (!Array.isArray(value) || value.length > 1 || !value.every((id) => Number.isSafeInteger(id) && id > 0)) throw new ContractError()
  if (currentStatus === 'completed' && value.length !== 1) throw new ContractError()
  return Object.freeze([...value]) as readonly number[]
}
function operationError(value: unknown) {
  if (value === null) return null
  const error = record(value)
  return Object.freeze({ code: text(error.code, 120), message: text(error.message) })
}
export function parsePreparedOperation(value: unknown, id: string, selection: ResearchSelection): PreparedOperation {
  const item = record(value)
  matches(item, { operation_id: operationId(id), trigger: 'v2_graph' })
  const settingsSnapshotAddress = operationSelection(item.plan, selection)
  const currentStatus = status(item.status)
  if (item.cancel_requested_at !== null && !Number.isFinite(Date.parse(text(item.cancel_requested_at)))) throw new ContractError()
  return Object.freeze({ operation_id: id, status: currentStatus, stage: text(item.stage, 100),
    completed_run_ids: completedRuns(item.completed_run_ids, currentStatus),
    cancel_requested: item.cancel_requested_at !== null, error: operationError(item.error),
    ...(settingsSnapshotAddress ? { settingsSnapshotAddress } : {}) })
}

export type SavedResearchContext = Omit<ResearchSelection, 'request' | 'settings'> & Readonly<{ inputIds?: readonly string[] }>
export type RecoverableResearch = Readonly<{
  operationId: string; status: 'pending' | 'running'; reason: string | null
  selection: ResearchSelection | null; operation: PreparedOperation | null
}>
export type ResearchRecovery = Readonly<{ complete: boolean; requests: readonly RecoverableResearch[] }>

function boundedNumber(value: unknown, minimum: number, maximum: number, integer = false) {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < minimum || value > maximum) throw new ContractError()
  if (integer && !Number.isInteger(value)) throw new ContractError()
  return value
}
export function parseResearchCutoff(value: unknown) {
  const result = text(value, 64), instant = Date.parse(result)
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.0+)?(?:Z|\+00:00)$/.test(result) || !Number.isFinite(instant)) throw new ContractError()
  const normalized = result.replace('+00:00', 'Z').replace(/\.0+Z$/, 'Z')
  if (new Date(instant).toISOString().replace('.000Z', 'Z') !== normalized) throw new ContractError()
  return result
}
function restoredValues(graph: Record<string, unknown>): Omit<ResearchPreparation, 'dataset_manifest_address'> {
  const id = text(graph.request_id, 36)
  if (!/^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/.test(id)) throw new ContractError()
  const experiment = record(graph.experiment), risk = record(record(graph.execution_policy).risk)
  const hypothesis = text(experiment.hypothesis, 4000)
  const riskPolicy = text(risk.risk_policy, 32)
  if (!hypothesis.trim() || !['none', 'pine-v4-ratchet/1', 'pine-v4-reversal/1'].includes(riskPolicy)) throw new ContractError()
  const asOf = parseResearchCutoff(graph.dataset_as_of)
  return Object.freeze({ request_id: id, dataset_as_of: asOf,
    hypothesis, research_capital: boundedNumber(experiment.research_capital, Number.MIN_VALUE, 1_000_000_000),
    seed: boundedNumber(experiment.seed, 0, 2_147_483_647, true), min_trades: boundedNumber(experiment.min_trades, 1, 100_000, true),
    n_folds: boundedNumber(experiment.n_folds, 2, 32, true), min_positive_fold_frac: boundedNumber(experiment.min_positive_fold_frac, 0, 1),
    risk_policy: riskPolicy as RiskPolicy, ...restoredSettingsExtensions(graph) })
}
function restoredSettingsExtensions(graph: Record<string, unknown>): Partial<ResearchValues> {
  if (!graph.settings_snapshot) return {}
  const schema = record(graph.settings_snapshot).schema
  if (schema === 'research-settings-snapshot/1') return {}
  const values = record(record(graph.settings_snapshot).values)
  const stop_loss_pct = boundedNumber(values.stop_loss_pct, 0, 1), take_profit_pct = boundedNumber(values.take_profit_pct, 0, 1)
  if (stop_loss_pct === 1 || take_profit_pct === 1) throw new ContractError()
  return { stop_loss_pct, take_profit_pct, ...(schema === "research-settings-snapshot/3" ? { optimization: parseOptimizationSettings(values.optimization) } : {}) }
}
function restoredRequest(graph: Record<string, unknown>, inputSet: boolean): ResearchRequest {
  const values = restoredValues(graph)
  if (!inputSet) return Object.freeze({ ...values, dataset_manifest_address: address(graph.dataset_manifest_address) })
  return Object.freeze({ ...values, input_datasets: validateInputSelection(graph.input_datasets, graph.primary_input), primary_input: text(graph.primary_input, 128) })
}
function matchingRecoveryGraph(item: Record<string, unknown>, context: SavedResearchContext) {
  if (item.trigger !== 'v2_graph') { text(item.trigger, 100); return null }
  const graphs = record(item.plan).v2_graphs
  if (!Array.isArray(graphs) || graphs.length !== 1) throw new ContractError()
  const graph = record(graphs[0])
  text(graph.project_id, 128); text(graph.graph_identifier, 128)
  boundedNumber(graph.graph_version, 1, Number.MAX_SAFE_INTEGER, true)
  return graph.project_id === context.projectId && graph.graph_identifier === context.graphId && graph.graph_version === context.version ? graph : null
}
function recoveredSelection(graph: Record<string, unknown>, context: SavedResearchContext, schema: unknown) {
  const settings = ['v2-graph-research-operation/3', 'v2-graph-research-operation/4'].includes(String(schema)) ? snapshotSelection(graph) : undefined
  const request = restoredRequest(graph, schema === 'v2-graph-research-operation/4')
  if (isInputPreparation(request) && JSON.stringify(request.input_datasets.map((item) => item.graph_input_id)) !== JSON.stringify(context.inputIds)) throw new ContractError()
  return Object.freeze({ ...context, request, ...(settings ? { settings } : {}) })
}
function recoverableOperation(input: unknown, context: SavedResearchContext): RecoverableResearch | null {
  const item = record(input), id = operationId(item.operation_id), currentStatus = status(item.status)
  if (currentStatus !== 'pending' && currentStatus !== 'running') throw new ContractError()
  const graph = matchingRecoveryGraph(item, context)
  if (!graph) return null
  try {
    const selection = recoveredSelection(graph, context, record(item.plan).schema)
    const operation = parsePreparedOperation(item, id, selection)
    return Object.freeze({ operationId: id, status: currentStatus, selection, operation, reason: null })
  } catch (error) {
    if (!(error instanceof ContractError)) throw error
    return Object.freeze({ operationId: id, status: currentStatus, selection: null, operation: null,
      reason: 'This active request cannot be verified against the saved version and supported research setup. Retry the lookup or cancel this request before starting another.' })
  }
}
export function parseResearchRecovery(input: unknown, context: SavedResearchContext): ResearchRecovery {
  const item = record(input), active = item.active_operations
  if (!Array.isArray(active) || active.length > 21 || typeof item.active_complete !== 'boolean') throw new ContractError()
  if (item.active_complete && active.length > 20) throw new ContractError()
  const ids = active.map((entry) => operationId(record(entry).operation_id))
  if (new Set(ids).size !== ids.length) throw new ContractError()
  const requests = active.map((entry) => recoverableOperation(entry, context)).filter((entry): entry is RecoverableResearch => entry !== null)
  return Object.freeze({ complete: item.active_complete, requests: Object.freeze(requests) })
}
export function parseRecoveryCancellation(input: unknown, id: string) {
  const item = record(input)
  matches(item, { operation_id: operationId(id) })
  return Object.freeze({ status: status(item.status) })
}
