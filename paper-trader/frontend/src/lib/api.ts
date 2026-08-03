const TOKEN = import.meta.env.VITE_PT_TOKEN as string | undefined

export type IrPurity = 'pure' | 'account_state' | 'broker_state' | 'wall_clock'

export interface IrViewNode {
  readonly instance_id: string
  readonly label: string
  readonly container: string
  readonly definition: string
  readonly params: Readonly<Record<string, unknown>>
  readonly warmup: number
  readonly purity: IrPurity
  readonly cache_id: string
  readonly derived: boolean
  readonly layer: number
  readonly row: number
  readonly placed: readonly [number, number] | null
}

export interface IrViewEdge {
  readonly source: string
  readonly target: string
  readonly source_socket: string
  readonly target_socket: string
  readonly derived: boolean
}

export interface IrGraphView {
  readonly identifier: string
  readonly version: number
  readonly display_name: string
  readonly warmup: number
  readonly layers: number
  readonly inputs: readonly string[]
  readonly outputs: readonly string[]
  readonly nodes: readonly IrViewNode[]
  readonly edges: readonly IrViewEdge[]
}

export interface IrLayoutPosition {
  readonly instance_id: string
  readonly x: number
  readonly y: number
}

export interface IrGraphLayout {
  readonly graph_identifier: string
  readonly graph_version: number
  readonly revision: number
  readonly positions: readonly IrLayoutPosition[]
  readonly groups: readonly IrVisualGroup[]
}

export interface IrGroupFrame {
  readonly x: number
  readonly y: number
  readonly width: number
  readonly height: number
}

export interface IrVisualGroup {
  readonly identifier: string
  readonly display_name: string
  readonly frame: IrGroupFrame
  readonly collapsed: boolean
  readonly members: readonly string[]
}

export interface IrAuthoredNode {
  readonly instance_id: string
  readonly component: {
    readonly identifier: string
    readonly version: number
  }
  readonly overrides: Readonly<Record<string, unknown>>
}

export interface IrAuthoredGraph {
  readonly identifier: string
  readonly version: number
  readonly display_name: string
  readonly nodes: readonly IrAuthoredNode[]
  readonly edges?: readonly {
    readonly source: { readonly instance: string; readonly socket: string }
    readonly target: { readonly instance: string; readonly socket: string }
  }[]
}

export interface IrEditableParameter {
  readonly identifier: string
  readonly kind: string
  readonly default: unknown
  readonly value: unknown
  readonly overridden: boolean
}

export interface IrEditableNode {
  readonly instance_id: string
  readonly component_identifier: string
  readonly component_version: number
  readonly parameters: readonly IrEditableParameter[]
  readonly sockets: readonly IrSocketDescriptor[]
}

export interface IrSocketDescriptor {
  readonly identifier: string
  readonly display_name: string
  readonly direction: 'input' | 'output'
  readonly wire_type: Readonly<Record<string, unknown>>
  readonly has_default_source: boolean
}

export interface IrBoundarySocketDescriptor extends IrSocketDescriptor {
  readonly instance_id: 'io_in' | 'io_out'
}

export interface IrParameterDescriptor {
  readonly identifier: string
  readonly display_name: string
  readonly kind: string
  readonly default: unknown
  readonly panel_path: readonly string[]
}

export interface IrComponentDescriptor {
  readonly identifier: string
  readonly version: number
  readonly display_name: string
  readonly parameters: readonly IrParameterDescriptor[]
  readonly sockets: readonly IrSocketDescriptor[]
}

export interface IrSocketRef {
  readonly instance_id: string
  readonly socket: string
}

export type IrEditorOperation =
  | { readonly operation: 'set_display_name'; readonly display_name: string }
  | {
      readonly operation: 'set_override'
      readonly instance_id: string
      readonly parameter: string
      readonly value: unknown
    }
  | {
      readonly operation: 'clear_override'
      readonly instance_id: string
      readonly parameter: string
    }
  | {
      readonly operation: 'add_node'
      readonly instance_id: string
      readonly identifier: string
      readonly version: number
      readonly overrides: Readonly<Record<string, unknown>>
      readonly domain: Readonly<Record<string, string>> | null
      readonly secret_params: readonly string[]
      readonly node_index?: number
    }
  | { readonly operation: 'remove_node'; readonly instance_id: string }
  | {
      readonly operation: 'connect'
      readonly source: IrSocketRef
      readonly target: IrSocketRef
      readonly edge_index?: number
    }
  | {
      readonly operation: 'disconnect'
      readonly source: IrSocketRef
      readonly target: IrSocketRef
    }

export type IrPresentationOperation =
  | {
      readonly operation: 'create_group' | 'put_group'
      readonly identifier: string
      readonly display_name: string
      readonly members: readonly string[]
      readonly frame: IrGroupFrame
      readonly collapsed: boolean
    }
  | {
      readonly operation: 'rename_group'
      readonly identifier: string
      readonly display_name: string
    }
  | { readonly operation: 'remove_group'; readonly identifier: string }
  | {
      readonly operation: 'add_group_member' | 'remove_group_member'
      readonly identifier: string
      readonly instance_id: string
    }
  | {
      readonly operation: 'set_group_frame'
      readonly identifier: string
      readonly frame: IrGroupFrame
    }
  | {
      readonly operation: 'set_group_collapsed'
      readonly identifier: string
      readonly collapsed: boolean
    }
  | {
      readonly operation: 'set_position'
      readonly instance_id: string
      readonly x: number
      readonly y: number
    }
  | { readonly operation: 'clear_position'; readonly instance_id: string }

export interface IrCommandReceipt {
  readonly applied_operations: readonly IrEditorOperation[]
  readonly inverse_operations: readonly IrEditorOperation[]
  readonly base_revision: number
  readonly draft_revision: number
  readonly version: number
  readonly content_address: string
  readonly semantic_forward_operations: readonly IrEditorOperation[]
  readonly semantic_inverse_operations: readonly IrEditorOperation[]
  readonly presentation_delta: {
    readonly forward_operations: readonly IrPresentationOperation[]
    readonly inverse_operations: readonly IrPresentationOperation[]
  }
  readonly base_version: number
  readonly base_presentation_revision: number
  readonly presentation_revision: number
}

export interface IrEditorDocument {
  readonly project_id: string
  readonly identifier: string
  readonly display_name: string
  readonly draft_revision: number
  readonly version: number
  readonly content_address: string
  readonly authored_graph: IrAuthoredGraph
  readonly view: IrGraphView
  readonly editable_nodes: readonly IrEditableNode[]
  readonly component_catalogue: readonly IrComponentDescriptor[]
  readonly graph_sockets: readonly IrBoundarySocketDescriptor[]
  readonly layout: IrGraphLayout
  readonly command_receipt: IrCommandReceipt | null
}

export interface IrEditorErrorItem {
  readonly operation_index: number | null
  readonly clause: string | null
  readonly path: readonly (string | number)[]
  readonly message: string
}

export interface IrEditorErrorEnvelope {
  readonly code:
    | 'DRAFT_REVISION_CONFLICT'
    | 'PRESENTATION_REVISION_CONFLICT'
    | 'PRESENTATION_VALIDATION_FAILED'
    | 'EDITOR_NOT_PUBLISHED'
    | 'EDITOR_HAS_UNPUBLISHED_DRAFT'
    | 'EDITOR_ARCHIVED'
    | 'REQUEST_VALIDATION_FAILED'
    | 'IR_VALIDATION_FAILED'
    | 'EDITOR_DOCUMENT_FAILED'
  readonly message: string
  readonly current_revision: number | null
  readonly current_presentation_revision: number | null
  readonly errors: readonly IrEditorErrorItem[]
}

export type EditorApiErrorCategory =
  | 'conflict'
  | 'validation'
  | 'server'
  | 'non-json-server'
  | 'network'

export class EditorApiError extends Error {
  readonly category: EditorApiErrorCategory
  readonly envelope: IrEditorErrorEnvelope | null
  readonly originalCause: unknown

  constructor(
    category: EditorApiErrorCategory,
    message: string,
    envelope: IrEditorErrorEnvelope | null = null,
    originalCause?: unknown,
  ) {
    super(message)
    this.name = 'EditorApiError'
    this.category = category
    this.envelope = envelope
    this.originalCause = originalCause
  }
}

const editorPath = (projectId: string, identifier: string) =>
  `/api/ir/projects/${encodeURIComponent(projectId)}/graphs/${encodeURIComponent(identifier)}`

const editorHeaders = (): Record<string, string> =>
  TOKEN ? { Authorization: `Bearer ${TOKEN}` } : {}

const editorEnvelope = async (response: Response): Promise<IrEditorErrorEnvelope> => {
  try {
    return await response.json() as IrEditorErrorEnvelope
  } catch (cause: unknown) {
    throw new EditorApiError(
      'non-json-server',
      `Editor request failed (${response.status})`,
      null,
      cause,
    )
  }
}

const editorFailure = async (response: Response): Promise<never> => {
  const envelope = await editorEnvelope(response)
  const category: EditorApiErrorCategory = response.status === 409
    ? 'conflict'
    : response.status === 422
      ? 'validation'
      : 'server'
  throw new EditorApiError(category, envelope.message, envelope)
}

const editorFetch = async (
  url: string,
  init: RequestInit,
): Promise<IrEditorDocument> => {
  let response: Response
  try {
    response = await fetch(url, init)
  } catch (cause: unknown) {
    const message = cause instanceof Error ? cause.message : 'Editor network request failed'
    throw new EditorApiError('network', message, null, cause)
  }
  if (!response.ok) return editorFailure(response)
  try {
    return await response.json() as IrEditorDocument
  } catch (cause: unknown) {
    throw new EditorApiError(
      'non-json-server',
      `Editor request failed (${response.status})`,
      null,
      cause,
    )
  }
}

export const getIrEditorDocument = async (
  projectId: string,
  identifier: string,
): Promise<IrEditorDocument> => editorFetch(
  `${editorPath(projectId, identifier)}/editor`,
  { headers: editorHeaders() },
)

export const postIrEditorOperations = async (
  projectId: string,
  identifier: string,
  baseRevision: number,
  basePresentationRevision: number,
  edits: readonly IrEditorOperation[],
  presentationEdits: readonly IrPresentationOperation[] = [],
): Promise<IrEditorDocument> => editorFetch(
  `${editorPath(projectId, identifier)}/edits`,
  {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...editorHeaders(),
    },
    body: JSON.stringify({
      base_revision: baseRevision,
      base_presentation_revision: basePresentationRevision,
      edits,
      presentation_edits: presentationEdits,
    }),
  },
)

export const postIrPresentationOperations = async (
  projectId: string,
  identifier: string,
  baseRevision: number,
  basePresentationRevision: number,
  edits: readonly IrPresentationOperation[],
): Promise<IrEditorDocument> => editorFetch(
  `${editorPath(projectId, identifier)}/presentation-edits`,
  {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...editorHeaders(),
    },
    body: JSON.stringify({
      base_revision: baseRevision,
      base_presentation_revision: basePresentationRevision,
      edits,
    }),
  },
)

interface IrLayoutFailureBody {
  readonly detail?: unknown
  readonly current_revision?: unknown
}

export class IrLayoutConflict extends Error {
  readonly currentRevision: number

  constructor(currentRevision: number) {
    super(`Layout changed on the server (revision ${currentRevision})`)
    this.name = 'IrLayoutConflict'
    this.currentRevision = currentRevision
  }
}

const layoutPath = (identifier: string, version: number) =>
  `/api/ir/graphs/${encodeURIComponent(identifier)}/versions/${version}/layout`

const layoutFailureBody = async (response: Response): Promise<IrLayoutFailureBody> => {
  try {
    return await response.json() as IrLayoutFailureBody
  } catch {
    return {}
  }
}

const layoutFailureMessage = (response: Response, body: IrLayoutFailureBody): string =>
  typeof body.detail === 'string'
    ? body.detail
    : `Layout request failed (${response.status})`

export const getIrGraphLayout = async (
  identifier: string,
  version: number,
): Promise<IrGraphLayout> => {
  const response = await fetch(layoutPath(identifier, version), {
    headers: TOKEN ? { Authorization: `Bearer ${TOKEN}` } : {},
  })
  if (!response.ok) {
    const body = await layoutFailureBody(response)
    throw new Error(layoutFailureMessage(response, body))
  }
  return response.json() as Promise<IrGraphLayout>
}

export const putIrGraphLayout = async (
  identifier: string,
  version: number,
  baseRevision: number,
  positions: readonly IrLayoutPosition[],
): Promise<IrGraphLayout> => {
  const response = await fetch(layoutPath(identifier, version), {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      ...(TOKEN ? { Authorization: `Bearer ${TOKEN}` } : {}),
    },
    body: JSON.stringify({ base_revision: baseRevision, positions }),
  })
  if (!response.ok) {
    const body = await layoutFailureBody(response)
    if (response.status === 409 && typeof body.current_revision === 'number') {
      throw new IrLayoutConflict(body.current_revision)
    }
    throw new Error(layoutFailureMessage(response, body))
  }
  return response.json() as Promise<IrGraphLayout>
}

export const getIrGraph = async (identifier: string): Promise<IrGraphView> => {
  const response = await fetch(`/api/ir/graphs/${encodeURIComponent(identifier)}`, {
    headers: TOKEN ? { Authorization: `Bearer ${TOKEN}` } : {},
  })
  if (!response.ok) {
    let message = `Graph request failed (${response.status})`
    try {
      const body = await response.json() as { detail?: unknown }
      if (typeof body.detail === 'string') message = body.detail
    } catch {
      // A non-JSON error still fails with the HTTP status above.
    }
    throw new Error(message)
  }
  return response.json() as Promise<IrGraphView>
}

const j = (u: string) =>
  fetch(u, { headers: TOKEN ? { Authorization: `Bearer ${TOKEN}` } : {} }).then((r) => r.json())
const post = (u: string, body: any) =>
  fetch(u, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(TOKEN ? { Authorization: `Bearer ${TOKEN}` } : {}),
    },
    body: JSON.stringify(body),
  }).then((r) => r.json())
const put = (u: string, body: any) =>
  fetch(u, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      ...(TOKEN ? { Authorization: `Bearer ${TOKEN}` } : {}),
    },
    body: JSON.stringify(body),
  }).then((r) => r.json())
export const del = (path: string) =>
  fetch(path, {
    method: 'DELETE',
    headers: TOKEN ? { Authorization: `Bearer ${TOKEN}` } : {},
  }).then((r) => {
    if (!r.ok) throw new Error(`${r.status}`)
    return r.json()
  })

export const getStatus = () => j('/api/status')
/** DB size + growth. Null on failure so the UI shows "unknown", never a stale size. */
export const getStorage = () =>
  fetch('/api/storage', { headers: TOKEN ? { Authorization: `Bearer ${TOKEN}` } : {} })
    .then((r) => r.json())
    .catch(() => null)
/**
 * The readiness probe. Deliberately tolerant in BOTH directions:
 *
 * - a 503 body is the interesting case, not an error — that is the probe doing
 *   its job, and `j()` would happily parse it, but being explicit here stops
 *   someone "fixing" this later by adding an r.ok check that throws away the
 *   only response that matters;
 * - a network/parse failure resolves to null so the UI can render "Unknown"
 *   rather than silently keeping the last good verdict on screen. A stale green
 *   badge is worse than an honest question mark.
 */
export const getHealth = () =>
  fetch('/api/health', { headers: TOKEN ? { Authorization: `Bearer ${TOKEN}` } : {} })
    .then((r) => r.json())
    .catch(() => null)
export const getExecState = () => j('/api/execution/state')
export const armBot = (armed: boolean) => post('/api/execution/arm', { armed })
export const killBot = () => post('/api/execution/kill', {})
export const getInstruments = () => j('/api/instruments')
export const getSignals = () => j('/api/signals')
export const getEarnings = () => j('/api/earnings')
// Scheduled-event blackouts in force today (EIA releases, index weekdays, bullion into
// expiry, results days). Lets the cockpit explain a sit-out BEFORE the bot skips a signal.
export const getEventRisk = (day?: string) =>
  j(`/api/event-risk${day ? `?day=${day}` : ''}`)
export const getPositions = (segment?: string) =>
  j(`/api/positions${segment ? `?segment=${segment}` : ''}`)
export const getProviderHealth = () => j('/api/provider-health')
export const setLiveInterval = (key: string, interval: string) =>
  post(`/api/instruments/${key}/interval`, { interval })
export const blockEntries = (key: string, blocked: boolean) =>
  post(`/api/instruments/${key}/block-entries`, { blocked })
// dual-segment / multi-strategy per-instrument controls (Phase 3)
export const getStrategies = () => j('/api/strategies')
export const setProduct = (key: string, product: string) =>
  post(`/api/instruments/${key}/product`, { product })
export const setPriorityFlag = (key: string, priority_flag: boolean) =>
  post(`/api/instruments/${key}/priority`, { priority_flag })
export const setOvertradeFlag = (key: string, flag: boolean) =>
  post(`/api/instruments/${key}/overtrade`, { flag })
export const setInstrumentStrategy = (key: string, strategy_key: string | null) =>
  post(`/api/instruments/${key}/strategy`, { strategy_key })
export const closePosition = (key: string) => post(`/api/positions/${key}/close`, {})
export const setPositionSLTP = (
  key: string,
  body: { stop_price?: number; target_price?: number; stop_pct?: number; target_pct?: number },
) => post(`/api/positions/${key}/sltp`, body)
export const setNoTakeProfit = (key: string, enabled: boolean) =>
  post(`/api/positions/${key}/no-take-profit`, { enabled })
export const manualOpen = (key: string, direction: string) =>
  post('/api/positions/manual-open', { key, direction })
export const getSettings = () => j('/api/settings')
export const setSetting = (key: string, value: any) => post('/api/settings', { key, value })
export const resetSetting = (key: string) => post('/api/settings/reset', { key })
export const getAnalytics = (segment?: string) =>
  j(`/api/analytics${segment ? `?segment=${segment}` : ''}`)
export const getCandles = (key: string) => j(`/api/candles/${key}`)
export const getOptionCandles = (key: string) => j(`/api/option-candles/${key}`)
export const getOptionsCalc = (key: string) => j(`/api/options-calc/${key}`)
export const getDashboard = (segment?: string, strategy?: string, period?: string) => {
  const q = new URLSearchParams()
  if (segment) q.set('segment', segment)
  if (strategy) q.set('strategy', strategy)
  if (period && period !== 'all') q.set('period', period)
  const qs = q.toString()
  return j(`/api/dashboard${qs ? `?${qs}` : ''}`)
}
export const getInstrumentDetail = (key: string, segment?: string, strategy?: string, period?: string) => {
  const q = new URLSearchParams()
  if (segment) q.set('segment', segment)
  if (strategy) q.set('strategy', strategy)
  if (period && period !== 'all') q.set('period', period)
  const qs = q.toString()
  return j(`/api/instrument/${key}${qs ? `?${qs}` : ''}`)
}
export const getAccountPnl = () => j('/api/account-pnl')
export const getTrades = (n = 1000) => j(`/api/trades?limit=${n}`)
export const getCalendar = (days = 120) => j(`/api/calendar?days=${days}`)
export const getLogs = (n = 300) => j(`/api/logs?limit=${n}`)

export const toggleInstrument = (key: string, enabled: boolean) =>
  post(`/api/instruments/${key}/toggle`, { enabled })

// ── customizable homepage / portfolio universe ──────────────────────────────
export const getHome = () => j('/api/portfolio/home')
export const addToPortfolio = (key: string, on_home = true, interval?: string) =>
  post('/api/portfolio/add', { key, on_home, interval })
export const removeFromPortfolio = (key: string) =>
  post('/api/portfolio/remove', { key, on_home: false })
export const addBulkToPortfolio = (items: Array<{
  key: string; interval?: string; strategy_key?: string | null; product?: string; on_home?: boolean
}>) => post('/api/portfolio/add-bulk', { items })

// ── backtest sweep ──────────────────────────────────────────────────────────
export interface SweepOpts {
  instruments?: string[]; lookback_days?: number | null
  start_date?: string; end_date?: string; strategies?: string[]
}
export const startSweep = (scope: string, intervals: string[], capital = 50000,
  opts: SweepOpts = {}) =>
  post('/api/backtest/sweep', { scope, intervals, capital, ...opts })
export const getSweepInstruments = (scope = 'liquid') =>
  j(`/api/backtest/instruments?scope=${scope}`)
export const getSweepStatus = (runId?: number) =>
  j(`/api/backtest/status${runId ? `?run_id=${runId}` : ''}`)
export const getSweepRuns = () => j('/api/backtest/runs')
export const sweepExportUrl = (runId?: number) =>
  `/api/backtest/export${runId ? `?run_id=${runId}` : ''}`

export interface ResultFilters {
  run_id?: number; interval?: string; strategy?: string
  min_win_rate?: number; min_profit_factor?: number
  max_drawdown?: number; min_return?: number; min_trades?: number; sort?: string
}
export const getSweepResults = (f: ResultFilters = {}) => {
  const q = new URLSearchParams()
  Object.entries(f).forEach(([k, v]) => { if (v !== undefined && v !== '') q.set(k, String(v)) })
  return j(`/api/backtest/results?${q.toString()}`)
}
export const getSweepResult = (key: string, interval: string, runId?: number, strategy?: string) => {
  const q = new URLSearchParams()
  if (runId) q.set('run_id', String(runId))
  if (strategy) q.set('strategy', strategy)
  const qs = q.toString()
  return j(`/api/backtest/result/${key}/${interval}${qs ? `?${qs}` : ''}`)
}

// ── Project-owned research evidence and decisions ────────────────────────────
export interface ResearchRunCandidate {
  readonly candidate_id: number
  readonly status: 'shadow' | 'pending' | 'approved' | 'rejected'
  readonly decision: {
    readonly content_address: string
    readonly evidence: {
      readonly actor: string
      readonly decision: 'approved' | 'rejected'
      readonly decided_at: string
      readonly reason: string
    }
  } | null
}

export interface ResearchRunSummary {
  readonly run_id: number
  readonly spec_id: string
  readonly status: string
  readonly decision: string | null
  readonly evidence_state: 'verified' | 'legacy_unbound' | 'corrupt' | 'pending' | 'running'
  readonly graph: {
    readonly project_id: string
    readonly identifier: string
    readonly version: number
    readonly content_address: string
  }
  readonly candidate: ResearchRunCandidate | null
}

export interface ResearchRunDetail extends ResearchRunSummary {
  readonly evidence: Record<string, any> | null
}

export interface ResearchComparisonDifference {
  readonly dimension: string
  readonly path: readonly (string | number)[]
  readonly left: unknown
  readonly right: unknown
}

export interface ResearchComparison {
  readonly equivalent: boolean
  readonly incomparable: readonly string[]
  readonly differences: readonly ResearchComparisonDifference[]
}

export interface ResearchGraphVersion {
  readonly project_id: string
  readonly identifier: string
  readonly version: number
  readonly content_address: string
}

export interface ResearchVersionSelection {
  readonly graph_identifier: string
  readonly graph_version: number
  readonly run_id?: number
}

export interface ResearchVersionComparison extends ResearchComparison {
  readonly left: ResearchVerifiedVersionSelection
  readonly right: ResearchVerifiedVersionSelection
}

export interface ResearchVerifiedVersionSelection {
  readonly project_id: string
  readonly graph_identifier: string
  readonly graph_version: number
  readonly content_address: string
  readonly run_id: number | null
}

export interface ResearchFinding {
  readonly finding_id: number
  readonly statement: string
  readonly polarity: 'positive' | 'negative'
  readonly confidence: number
  readonly evidence_run_id: number
  readonly superseded_by: number | null
  readonly status: 'active' | 'superseded'
  readonly created_at: string | null
  readonly binding: {
    readonly run_id: number
    readonly spec_id: string
    readonly evidence_content_address: string
    readonly graph: ResearchRunSummary['graph']
  }
}

export interface ResearchOperationReceipt {
  readonly operation_id: string
  readonly trigger: 'nightly' | 'manual_script'
  readonly state: 'running' | 'completed' | 'failed'
  readonly stage: string
  readonly started_at: string
  readonly completed_at: string | null
  readonly build: string
  readonly provider_mode: string
  readonly plan: {
    readonly content_address: string
    readonly experiment_count: number
    readonly items: readonly Record<string, unknown>[]
  } | null
  readonly completed_run_ids: readonly number[]
  readonly failure: {
    readonly stage: string
    readonly code: string
    readonly message: string
  } | null
}

export interface ResearchOperationStatus {
  readonly state: 'never_run' | 'available'
  readonly active: ResearchOperationReceipt | null
  readonly last: ResearchOperationReceipt | null
}

export type ResearchReviewEventType =
  | 'graph_version_published' | 'experiment_run' | 'finding_created'
  | 'candidate_created' | 'candidate_decided'

export interface ResearchReviewEvent {
  readonly event_id: string
  readonly type: ResearchReviewEventType
  readonly occurred_at: string
  readonly status: string
  readonly summary: string
  readonly references: {
    readonly graph: Omit<ResearchRunSummary['graph'], 'project_id'> | null
    readonly run_id: number | null
    readonly finding_id: number | null
    readonly candidate_id: number | null
  }
}

export interface ResearchReviewFilters {
  readonly event_type?: ResearchReviewEventType
  readonly status?: string
  readonly after?: string
  readonly before?: string
  readonly cursor?: string
  readonly limit?: number
}

export interface ResearchReview {
  readonly project_id: string
  readonly as_of: string
  readonly timeline: {
    readonly events: readonly ResearchReviewEvent[]
    readonly next_cursor: string | null
  }
  readonly queues: {
    readonly review_needed_runs: readonly {
      readonly run_id: number; readonly status: string; readonly evidence_state: string
      readonly graph: ResearchReviewEvent['references']['graph']
    }[]
    readonly pending_candidates: readonly {
      readonly candidate_id: number; readonly run_id: number; readonly status: string
      readonly graph: ResearchReviewEvent['references']['graph']
    }[]
    readonly active_findings: readonly {
      readonly finding_id: number; readonly evidence_run_id: number
      readonly polarity: string; readonly confidence: number
      readonly graph: ResearchReviewEvent['references']['graph']
    }[]
    readonly failed_operation: {
      readonly operation_id: string; readonly trigger: string; readonly stage: string
      readonly completed_at: string; readonly failure: ResearchOperationReceipt['failure']
    } | null
  }
  readonly global_operations: ResearchOperationStatus | null
  readonly source_errors: readonly {
    readonly source: string; readonly source_id: string; readonly code: string
  }[]
}

export interface ResearchReviewNote {
  readonly note_id: string
  readonly project_id: string
  readonly event_id: string
  readonly event_type: ResearchReviewEventType
  readonly body: string
  readonly created_by: 'owner'
  readonly revision: number
  readonly anchor_state: 'available' | 'missing'
  readonly created_at: string
  readonly updated_at: string
}

export interface ResearchReviewSavedView {
  readonly view_id: string
  readonly project_id: string
  readonly name: string
  readonly filters: Required<Pick<ResearchReviewFilters, 'limit'>> & {
    readonly event_type: ResearchReviewEventType | null
    readonly status: string | null
    readonly after: string | null
    readonly before: string | null
  }
  readonly created_by: 'owner'
  readonly revision: number
  readonly created_at: string
  readonly updated_at: string
}

const researchPath = (projectId: string) =>
  `/api/ir/projects/${encodeURIComponent(projectId)}`

const researchFetch = async <T>(url: string, init?: RequestInit): Promise<T> => {
  const response = await fetch(url, {
    ...init,
    headers: {
      ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
      ...editorHeaders(),
      ...init?.headers,
    },
  })
  const body = response.status === 204 ? undefined : await response.json()
  if (!response.ok) {
    throw new Error(typeof body.message === 'string'
      ? body.message
      : `Research request failed (${response.status})`)
  }
  return body as T
}

export const getResearchOperationStatus = (): Promise<ResearchOperationStatus> =>
  researchFetch('/api/research/operations/status')

export const getResearchReview = (
  projectId: string, filters: ResearchReviewFilters = {},
): Promise<ResearchReview> => {
  const query = new URLSearchParams()
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== '') query.append(key, String(value))
  })
  const suffix = query.toString()
  return researchFetch(`${researchPath(projectId)}/review${suffix ? `?${suffix}` : ''}`)
}

export const getResearchReviewNotes = (
  projectId: string,
): Promise<{ notes: ResearchReviewNote[] }> => researchFetch(
  `${researchPath(projectId)}/review/notes`,
)

export const createResearchReviewNote = (
  projectId: string, eventId: string, body: string,
): Promise<ResearchReviewNote> => researchFetch(
  `${researchPath(projectId)}/review/notes`,
  { method: 'POST', body: JSON.stringify({ event_id: eventId, body }) },
)

export const updateResearchReviewNote = (
  projectId: string, noteId: string, baseRevision: number, body: string,
): Promise<ResearchReviewNote> => researchFetch(
  `${researchPath(projectId)}/review/notes/${encodeURIComponent(noteId)}`,
  { method: 'PATCH', body: JSON.stringify({ base_revision: baseRevision, body }) },
)

export const deleteResearchReviewNote = (
  projectId: string, noteId: string, baseRevision: number,
): Promise<void> => researchFetch(
  `${researchPath(projectId)}/review/notes/${encodeURIComponent(noteId)}`,
  { method: 'DELETE', body: JSON.stringify({ base_revision: baseRevision }) },
)

export const getResearchReviewSavedViews = (
  projectId: string,
): Promise<{ views: ResearchReviewSavedView[] }> => researchFetch(
  `${researchPath(projectId)}/review/views`,
)

export const createResearchReviewSavedView = (
  projectId: string, name: string, filters: ResearchReviewFilters,
): Promise<ResearchReviewSavedView> => researchFetch(
  `${researchPath(projectId)}/review/views`,
  { method: 'POST', body: JSON.stringify({ name, filters }) },
)

export const updateResearchReviewSavedView = (
  projectId: string, viewId: string, baseRevision: number,
  name: string, filters: ResearchReviewFilters,
): Promise<ResearchReviewSavedView> => researchFetch(
  `${researchPath(projectId)}/review/views/${encodeURIComponent(viewId)}`,
  { method: 'PATCH', body: JSON.stringify({ base_revision: baseRevision, name, filters }) },
)

export const deleteResearchReviewSavedView = (
  projectId: string, viewId: string, baseRevision: number,
): Promise<void> => researchFetch(
  `${researchPath(projectId)}/review/views/${encodeURIComponent(viewId)}`,
  { method: 'DELETE', body: JSON.stringify({ base_revision: baseRevision }) },
)

export const getResearchRuns = (projectId: string): Promise<{ runs: ResearchRunSummary[] }> =>
  researchFetch(`${researchPath(projectId)}/experiments`)

export const getResearchRun = (
  projectId: string, runId: number,
): Promise<ResearchRunDetail> => researchFetch(
  `${researchPath(projectId)}/experiments/${runId}`,
)

export const compareResearchRuns = (
  projectId: string, leftRunId: number, rightRunId: number,
): Promise<ResearchComparison> => researchFetch(
  `${researchPath(projectId)}/experiments/comparisons`,
  {
    method: 'POST',
    body: JSON.stringify({ left_run_id: leftRunId, right_run_id: rightRunId }),
  },
)

export const getResearchGraphVersions = (
  projectId: string, identifier: string,
): Promise<ResearchGraphVersion[]> => researchFetch(
  `${researchPath(projectId)}/graphs/${encodeURIComponent(identifier)}/versions`,
)

export const compareResearchVersions = (
  projectId: string,
  left: ResearchVersionSelection,
  right: ResearchVersionSelection,
): Promise<ResearchVersionComparison> => researchFetch(
  `${researchPath(projectId)}/version-comparisons`,
  { method: 'POST', body: JSON.stringify({ left, right }) },
)

export const decideResearchCandidate = (
  projectId: string,
  candidateId: number,
  decision: 'approved' | 'rejected',
  reason: string,
) => researchFetch<{
  candidate_id: number
  status: 'approved' | 'rejected'
  decision: ResearchRunCandidate['decision']
}>(`${researchPath(projectId)}/candidates/${candidateId}/decisions`, {
  method: 'POST',
  body: JSON.stringify({ expected_status: 'pending', decision, reason }),
})

export const getResearchFindings = (
  projectId: string,
): Promise<{ findings: ResearchFinding[] }> => researchFetch(
  `${researchPath(projectId)}/findings`,
)

export const createResearchFinding = (
  projectId: string,
  runId: number,
  statement: string,
  polarity: 'positive' | 'negative',
): Promise<ResearchFinding> => researchFetch(
  `${researchPath(projectId)}/experiments/${runId}/findings`,
  {
    method: 'POST',
    body: JSON.stringify({ statement, polarity }),
  },
)

export const reviseResearchFinding = (
  projectId: string,
  findingId: number,
  statement: string,
  polarity: 'positive' | 'negative',
): Promise<{ superseded: ResearchFinding; successor: ResearchFinding }> => researchFetch(
  `${researchPath(projectId)}/findings/${findingId}/revisions`,
  {
    method: 'POST',
    body: JSON.stringify({ expected_superseded_by: null, statement, polarity }),
  },
)

// ── Portfolio: promotions (approve→deploy), watchlists, strategy archive ──────
export interface Promotion {
  id: number; run_id: number; status: string
  strategy_key: string; interval: string; params: Record<string, any>
  qualified_universe: string[]
  validated_universe: { instrument: string; dsr: number; scorecard?: any }[]
  best?: { instrument: string; dsr: number } | null
  generated: boolean
  composition?: any | null
  generated_source?: string | null
  explanation: {
    strategy_key: string; display_name: string; thesis: string
    primitives: string[]; rules: string[]; caveats: string; note?: string
  }
  created_at?: string | null
}
export interface Watchlist {
  id: number; name: string; strategy_key: string; status: string
  interval: string | null; instruments: string[]
}
export interface ArchiveStrategy {
  strategy_key: string; status: string; source: string
  deployed_watchlist_id: number | null; last_dsr: number | null; note: string
}

export const getPromotions = (): Promise<{ promotions: Promotion[] }> =>
  j('/api/portfolio/promotions')
export const deployPromotion = (
  id: number, body: { watchlist_name?: string; dry_run?: boolean } = {},
) => post(`/api/portfolio/promotions/${id}/deploy`, body)
export const getWatchlists = (): Promise<{ watchlists: Watchlist[] }> =>
  j('/api/portfolio/watchlists')
export const getArchive = (): Promise<{ strategies: ArchiveStrategy[] }> =>
  j('/api/portfolio/archive')
export const setWatchlistStatus = (name: string, status: string) =>
  post(`/api/portfolio/watchlists/${encodeURIComponent(name)}/status`, { status })
export const setArchiveStatus = (strategyKey: string, status: string) =>
  post(`/api/portfolio/archive/${encodeURIComponent(strategyKey)}/status`, { status })
