/** Read models only. These types confer no graph or research authority. */
export type CapabilityState = 'ENABLED' | 'ENABLED_WITH_LIMIT' | 'INTERNAL' | 'UNAVAILABLE' | 'BLOCKED'
export type Capability = Readonly<{ state: CapabilityState; ui_navigation?: boolean; reason?: string }>
export type ReleaseManifest = Readonly<{
  schema: 'strategy-os-release-profile/1'
  release_profile: 'v0_research_signal'
  research_enabled: true
  service_role: 'api'
  execution_authority: false
  capabilities: Readonly<Record<string, Capability>>
}>
export type Project = Readonly<{ project_id: string; name: string; description: string; status: 'active' | 'archived' }>
export type ProjectPage = Readonly<{
  schema: 'strategy-os-research-project-page/1'; items: readonly Project[]; next_cursor: string | null
}>
export type GraphSummary = Readonly<{
  identifier: string; display_name: string; draft_revision: number; current_version: number | null
}>
export type GraphPage = Readonly<{
  schema: 'strategy-os-graph-index/1'; project_id: string; items: readonly GraphSummary[]; next_cursor: string | null
}>
export type PublishedGraph = Readonly<{
  project_id: string; identifier: string; version: number; content_address: string
}>
export type CatalogueHelpSource = Readonly<{
  source_record_id: string; title: string; authors_or_organization: string
  publication_or_version: string; year: number | null; url: string | null; claim_scope: string
}>
export type CatalogueHelpParameter = Readonly<{
  name: string; type: string; required: boolean; default: unknown; enum: unknown
  domain: unknown; units: string; serialization: string
}>
export type CatalogueHelp = Readonly<{
  component_id: string; component_version: number
  semantic_kind: 'MATHEMATICAL_FORMULA' | 'FIELD_SELECTION' | 'FIELD_SPLITTER' | 'LOGICAL_OPERATION' | 'INTENT_BEHAVIOR'
  description: string; semantic_text: string; sources: readonly CatalogueHelpSource[]
  customisation: Readonly<{
    parameters: readonly CatalogueHelpParameter[]; guidance: string
    built_in_code_immutable: true; immutable_boundary: string
  }>
  availability: Readonly<{
    status: 'AVAILABLE' | 'CONDITIONAL'; authority: 'NONE' | 'MONITORING_ONLY'; condition: string
  }>
}> & (Readonly<{ implementation_binding: string; composition_binding?: never }> | Readonly<{
  implementation_binding: null; composition_binding: Readonly<{ component_address: string; registry_identity: string }>
}>)
export type CatalogueComponent = Readonly<{
  component_kind: 'LEAF' | 'COMPOUND'
  component_id: string; component_version: number; component_address: string; display_name: string
  visible_family: string; presentation_group_name: string; descriptor: Readonly<Record<string, unknown>>
  data_requirement: Readonly<Record<string, unknown>> | null; help: CatalogueHelp; availability: Readonly<{
    status: 'AVAILABLE' | 'CONDITIONAL'; authority: 'NONE' | 'MONITORING_ONLY';
    provider_support_verified: false; data_rights_verified: false; backtest_eligible: false
  }>
}>
export type CatalogueGroup = Readonly<{
  order: number; visible_family: string; display_name: string; components: readonly CatalogueComponent[]
}>
export type VerifiedCatalogue = Readonly<{
  schema: 'strategy-os-verified-language-catalogue/1' | 'strategy-os-verified-language-catalogue/2'; registry_identity: string
  catalogue_identity: string; groups: readonly CatalogueGroup[]
}>
export type EditorParameter = Readonly<{
  identifier: string; kind: string; default: unknown; value: unknown; overridden: boolean
}>
export type EditorSocket = Readonly<{
  identifier: string; display_name: string; direction: 'input' | 'output'
  wire_type: Readonly<Record<string, unknown>>; has_default_source: boolean
}>
export type ComponentDescriptor = Readonly<{
  identifier: string; version: number; display_name: string
  parameters: readonly Readonly<{ identifier: string; display_name: string; kind: string; default: unknown; panel_path: readonly string[] }>[]
  sockets: readonly EditorSocket[]
}>
export type EditorNode = Readonly<{
  instance_id: string; label: string; component_identifier: string; component_version: number
  parameters: readonly EditorParameter[]; sockets: readonly EditorSocket[]; layer: number; row: number
}>
export type EditorEdge = Readonly<{
  source: string; target: string; source_socket: string; target_socket: string; derived: boolean
}>
export type EditorLayout = Readonly<{
  revision: number; positions: readonly Readonly<{ instance_id: string; x: number; y: number }>[]
  groups: readonly Readonly<{ identifier: string; display_name: string; collapsed: boolean; members: readonly string[]
    frame: Readonly<{ x: number; y: number; width: number; height: number }> }>[]
}>
export type CommandReceipt = Readonly<{
  semantic_forward_operations: readonly Readonly<Record<string, unknown>>[]
  semantic_inverse_operations: readonly Readonly<Record<string, unknown>>[]
  presentation_delta: Readonly<{ forward_operations: readonly Readonly<Record<string, unknown>>[]; inverse_operations: readonly Readonly<Record<string, unknown>>[] }>
  draft_revision: number; version: number; presentation_revision: number; content_address: string
}>
export type EditorDocument = Readonly<{
  project_id: string; identifier: string; display_name: string; draft_revision: number
  version: number; content_address: string; presentation_revision: number; nodes: readonly EditorNode[]
  edges: readonly EditorEdge[]; component_catalogue: readonly ComponentDescriptor[]
  graph_sockets?: readonly Readonly<EditorSocket & { instance_id: 'io_in' | 'io_out' }>[]
  layout: EditorLayout; command_receipt: CommandReceipt | null
}>
export type EditorValidation = Readonly<{
  schema: 'strategy-os-editor-validation/1'; valid: boolean; base_revision: number; base_version: number
  predicted_content_address: string | null; nonauthority: 'VALIDATION_DOES_NOT_PUBLISH_OR_GRANT_AUTHORITY'
  violations: readonly Readonly<{ operation_index: number | null; clause: string | null; path: readonly (string | number)[]; message: string }>[]
}>
export type V2Endpoint = Readonly<{ scope: 'node'; node_id: string; port_id: string }>
export type V2Port = Readonly<{
  port_id: string; direction: 'input' | 'output'; semantic_flow: string; semantic_role: string
  type_ref: Readonly<Record<string, unknown>>; shape: unknown
  connections?: Readonly<Record<string, unknown>>; default?: unknown
}>
export type V2Node = Readonly<{
  node_id: string
  component: Readonly<{ component_id: string; component_version: number }>
  parameters: Readonly<Record<string, unknown>>
}>
export type V2Edge = Readonly<{
  edge_id: string; source: Readonly<Record<string, unknown>>; target: Readonly<Record<string, unknown>>
  binding: Readonly<Record<string, unknown>>
}>
export type V2Document = Readonly<{
  format_version: 2; strategy_id: string; strategy_version: number
  metadata: Readonly<{ metadata_version: number; name: string; description: string | null; tags: readonly string[] }>
  graph_inputs: readonly V2Port[]; graph_outputs: readonly V2Port[]
  nodes: readonly V2Node[]; edges: readonly V2Edge[]
}>
export type V2Draft = Readonly<{
  project_id: string; graph_identifier: string; semantic_revision: number
  current_version: number | null; published_revision: number | null
  document: V2Document; content_address: string; graph_address: string
}>
export type V2SemanticReceipt = Readonly<Record<string, unknown> & {
  schema: 'strategy-os-v2-semantic-receipt/2'; commit_state: 'DRAFT_COMMITTED' | 'DRY_RUN_ROLLED_BACK'
  intent: 'EDIT' | 'UNDO' | 'REDO' | 'REPLAY'; base_semantic_revision: number; result_semantic_revision: number
  base_content_address: string; result_content_address: string; base_graph_address: string; result_graph_address: string
  forward_commands: readonly Readonly<Record<string, unknown>>[]; inverse_commands: readonly Readonly<Record<string, unknown>>[]
  receipt_address: string
}>
export type V2PublishReceipt = Readonly<Record<string, unknown> & {
  schema: 'strategy-os-v2-publish-receipt/1'; project_id: string; graph_identifier: string
  graph_version: number; semantic_revision: number; content_address: string; graph_address: string
  canonical_document: V2Document; receipt_address: string
}>
export type V2Presentation = Readonly<{
  schema: 'strategy-os-v2-presentation-state/1'; semantic_revision: number; presentation_revision: number
  presentation: Readonly<{ positions: Readonly<Record<string, Readonly<{ x: number; y: number }>>>; groups: Readonly<Record<string, unknown>>
    viewport: Readonly<{ x: number; y: number; zoom: number }> | null; selection: Readonly<Record<string, readonly string[]>> }>
  presentation_address: string; orphaned_references: Readonly<Record<string, readonly string[]>>; executable_identity: false
}>
export type V2PresentationReceipt = Readonly<Record<string, unknown> & {
  schema: 'strategy-os-v2-presentation-receipt/1'; commit_state: 'PRESENTATION_COMMITTED'
  intent: 'EDIT' | 'UNDO' | 'REDO' | 'REPLAY'; base_presentation_revision: number; result_presentation_revision: number
  forward_commands: readonly Readonly<Record<string, unknown>>[]; inverse_commands: readonly Readonly<Record<string, unknown>>[]
  receipt_address: string
}>
export type ResearchDataset = Readonly<{
  manifest_address: string; instrument_address: string; canonical_instrument_label: string; instrument_display_name?: string | null
  provider_selection_address?: string | null
  asset_class: string; contract_kind: string; interval: string; event_start: string; event_end: string
  availability_end: string; as_of: string; bar_count: number; fields: readonly string[]
  provider_evidence_state: 'VERIFIED_REFERENCES_PRESENT' | 'USER_CSV_SHAPE_VALIDATED'
  market_truth_state: 'VERIFIED_REFERENCES_PRESENT' | 'RECONSTRUCTED_WITH_GAPS'
  source_type?: 'PROVIDER_AUTHORITY' | 'USER_SUPPLIED'
  historical_source_availability?: 'DECLARED' | 'NOT_SUPPLIED'
  calendar_coverage?: 'DECLARED' | 'NOT_ASSERTED'
  rights_scope?: 'PROVIDER_CONTRACT' | 'PERSONAL_RESEARCH_ONLY'
  research_compatibility?: 'PRIMARY_BACKTEST' | 'BENCHMARK_INPUT_ONLY' | 'UNAVAILABLE'
  gaps: readonly Readonly<Record<string, unknown>>[]; backtest_eligibility: 'ELIGIBLE_Q03' | 'UNAVAILABLE'; refusal_code: string | null
}>
export type ResearchDatasetPage = Readonly<{
  schema: 'strategy-os-canonical-dataset-index/1'; project_id: string; items: readonly ResearchDataset[]; next_cursor: string | null
}>
export type ProviderHistoryRequest = Readonly<{ selection_address: string; start_date: string; end_date: string; interval: 'day' }>
export type ProviderHistoryReceipt = Readonly<{
  schema: 'strategy-os-provider-history-import/1'; project_id: string; selection_address: string; reused: boolean
  requested_start: string; requested_end: string; returned_start: string; returned_end: string
  request_count: number; empty_request_count: number; request_window_days: number; application_bar_limit: number
  provider_retention: 'UNKNOWN'; item: ResearchDataset
}>
export type VisualizationState = Readonly<{ schema: 'strategy-os-backtest-visualization/1'; state: 'PENDING' | 'UNAVAILABLE'; reason_code?: string; status?: string }>
export type AvailableVisualization = Readonly<{
  schema: 'strategy-os-backtest-visualization/1'; state: 'AVAILABLE'; visualization_address: string
  identity: Readonly<Record<string, unknown>>; summary: Readonly<Record<string, number | boolean | null>>
  series: Readonly<{ net_equity: Readonly<{ points: readonly Readonly<{ time: number; value: number }>[]; original_count: number }>
    drawdown: Readonly<{ points: readonly Readonly<{ time: number; value: number; absolute: number }>[]; original_count: number }>
    benchmark: Readonly<Record<string, unknown>>; trade_events: readonly Readonly<Record<string, unknown>>[] }>
  trade_page: Readonly<{ items: readonly Readonly<Record<string, unknown>>[]; next_cursor: number | null; total: number; detail_reason: string | null }>
  costs: Readonly<{ charges_total: number; breakdown: Readonly<Record<string, unknown>>; slippage: Readonly<Record<string, unknown>> }>
  folds: readonly Readonly<Record<string, unknown>>[]; provenance: Readonly<Record<string, unknown>>
}>
export type ResearchVisualization = VisualizationState | AvailableVisualization
export type MarketContextBar = Readonly<{
  cursor: number; event_time: string; completed_at: string
  open: number; high: number; low: number; close: number; volume: number
}>
export type MarketContext = Readonly<{
  schema: 'strategy-os-market-context/1'; state: 'AVAILABLE' | 'EMPTY'
  market_context_address: string; projection_address: string
  source: Readonly<{ kind: 'VERIFIED_SAVED_RUN'; address: string }>
  graph: Readonly<Record<string, unknown>>; dataset_manifest_address: string
  canonical_instrument_address: string; instrument_label: string
  timeframe_seconds: number; source_as_of: string; replay_at: string
  bars: readonly MarketContextBar[]
  page: Readonly<{ after: number; limit: number; next_cursor: number | null; visible_count: number }>
}>
export type ChartAnnotation = Readonly<{
  annotation_id: string; revision: number; geometry: Readonly<Record<string, unknown>>
  geometry_address: string; applicability: Readonly<Record<string, unknown>>
  applicability_address: string; created_at: string; updated_at: string
}>
export type ChartAnnotationPage = Readonly<{
  schema: 'strategy-os-chart-annotation-presentation/1'; market_context_address: string
  items: readonly ChartAnnotation[]; next_cursor: string | null
}>
export type OptimizationParameter = Readonly<{ node_id: string; parameter_id: string; value: number; normalized_value: string }>
export type OptimizationCandidate = Readonly<{ coordinates: Readonly<Record<string, string>>; parameters: readonly OptimizationParameter[]; content_address: string; graph_address: string
  state: 'pending' | 'running' | 'evaluated' | 'failed' | 'cancelled'; lineage?: Readonly<Record<string, unknown>>; reason_code?: string }>
export type OptimizationTrial = Readonly<{ params: Readonly<Record<string, string>>; fold_index: number; objective: number | null; trades: number; is_sharpe: number | null; selected: boolean }>
export type OptimizationSelection = Readonly<{ coordinates: Readonly<Record<string, string>>; parameters: readonly OptimizationParameter[]; content_address: string; graph_address: string; canonical_document: V2Document; lineage: Readonly<Record<string, unknown>> }>
export type OptimizationPartition = Readonly<{ development_bars: number; development_end_ts: number | null; validation_bars: number; validation_start_ts: number | null; validation_end_ts: number | null }>
export type CanonicalOptimizationEvidence = Readonly<{ schema: 'canonical-development-search-evidence/1'; state: 'pending' | 'running' | 'failed' | 'cancelled' | 'refused' | 'not_qualified' | 'selected'
  recipe_address: string; candidates: readonly OptimizationCandidate[]; nested_trials: readonly OptimizationTrial[]; final_development_trials: readonly OptimizationTrial[]; selected: OptimizationSelection | null
  partition: OptimizationPartition | null; performance_matrix: readonly (readonly number[])[]; n_trials: number; var_sr: number; reason_code?: string }>
export type OptimizationResearchGates = Readonly<{ instrument: string; passed: boolean | null; gates: Readonly<Record<string, Readonly<{ passed: boolean; value: number | string }>>> }>
export type ExperimentRun = Readonly<{
  canonical_optimization?: CanonicalOptimizationEvidence; optimization_research_gates?: readonly OptimizationResearchGates[]
  research_outcome?: Readonly<{ qualified: number; validated: number; total_bars: number
    rejected: readonly Readonly<{ instrument: string; reason: string }>[] }>
  run_id: number; spec_id: string; status: string; decision: string | null
  evidence_state: 'verified' | 'legacy_unbound' | 'corrupt' | 'pending' | 'running'
  graph: PublishedGraph; dataset_bindings: readonly Readonly<{
    instrument_address: string; manifest_address: string; as_of: string; interval: string
  }>[]; contract: ExperimentContract | null
}>
export type ExperimentContract = Readonly<{
  charge_model: 'zerodha_charges_v1'; sizing_model: 'one_lot_or_cash_budget_v1'
  slippage_bps: number; slippage_multiplier: number
  gates: Readonly<{ min_oos_trades: number; n_folds: number; min_positive_fold_fraction: number
    optimize_search: boolean; pbo_threshold: number; sibling_trials: number }>
}>
export type ExperimentPage = Readonly<{ runs: readonly ExperimentRun[] }>
export type ResearchRunPage = Readonly<{
  schema: 'strategy-os-research-run-page/1'; project_id: string; runs: readonly ExperimentRun[]; next_cursor: number | null
}>
export type ExperimentStart = Readonly<{
  spec_id: string; run_id: number; decision: 'propose' | 'archive'; graph: PublishedGraph
  dataset_bindings: readonly Readonly<{ instrument_address: string; manifest_address: string; as_of: string; interval: string }>[]
  contract: ExperimentContract
}>
export type VersionComparison = Readonly<{
  equivalent: boolean; incomparable: readonly string[]
  differences: readonly Readonly<{ dimension: string; path: readonly (string | number)[]; left: unknown; right: unknown }>[]
}>
export type ReviewTimeline = Readonly<{
  project_id: string; as_of: string; events: readonly Readonly<{
    event_id: string; type: string; occurred_at: string | null; status: string; summary: string
  }>[]; next_cursor: string | null; source_errors: readonly string[]
}>
export type ApiErrorDetail = Readonly<{ loc: readonly (string | number)[]; type: string; msg: string }>
export type ApiErrorEnvelope = Readonly<{ code: string; message: string; detail?: readonly ApiErrorDetail[] }>
export type BrowserIdentity = Readonly<{
  user: Readonly<{ id: string; display_name: string }>
  organization_id: string
  memberships: readonly Readonly<{ organization_id: string; name: string; role: string }>[]
  expires_at: string
}>

export function parseBrowserSession(input: unknown): { identity: BrowserIdentity; csrf: string } {
  const value = object(input)
  keys(value, ['user', 'organization_id', 'memberships', 'expires_at', 'csrf'])
  const user = object(value.user); keys(user, ['id', 'display_name'])
  const organization_id = text(value.organization_id, 64)
  requireValue(Array.isArray(value.memberships) && value.memberships.length > 0 && value.memberships.length <= 1000)
  const seen = new Set<string>()
  const memberships = value.memberships.map((raw) => {
    const row = object(raw); keys(row, ['organization_id', 'name', 'role'])
    const id = text(row.organization_id, 64)
    requireValue(!seen.has(id)); seen.add(id)
    const role = text(row.role, 16)
    requireValue(['owner', 'admin', 'member', 'viewer'].includes(role))
    return Object.freeze({ organization_id: id, name: text(row.name, 128), role })
  })
  requireValue(seen.has(organization_id))
  const expires_at = text(value.expires_at, 40)
  requireValue(Number.isFinite(Date.parse(expires_at)))
  const csrf = text(value.csrf, 64)
  requireValue(/^[0-9a-f]{64}$/.test(csrf))
  return { identity: Object.freeze({ user: Object.freeze({ id: text(user.id, 64), display_name: text(user.display_name, 128) }),
    organization_id, memberships: Object.freeze(memberships), expires_at }), csrf }
}

export class ContractError extends Error {
  constructor() { super('The server response could not be verified.'); this.name = 'ContractError' }
}
function requireValue(condition: unknown): asserts condition {
  if (!condition) throw new ContractError()
}
function object(value: unknown): Record<string, unknown> {
  requireValue(value !== null && typeof value === 'object' && !Array.isArray(value))
  return value as Record<string, unknown>
}
function keys(value: Record<string, unknown>, required: string[], optional: string[] = []) {
  requireValue(required.every((key) => Object.hasOwn(value, key)))
  requireValue(Object.keys(value).every((key) => required.includes(key) || optional.includes(key)))
}
function text(value: unknown, max: number, empty = false): string {
  requireValue(typeof value === 'string' && value.length <= max && (empty || value.trim().length > 0))
  return value
}
function integer(value: unknown, minimum: number): number {
  requireValue(typeof value === 'number' && Number.isInteger(value) && Number.isSafeInteger(value) && value >= minimum)
  return value
}
function exactSet(value: unknown, expected: string[]) {
  requireValue(Array.isArray(value) && value.length === expected.length && new Set(value).size === expected.length)
  requireValue(expected.every((item) => value.includes(item)))
}

/** Closed diagnostic projection. Callers may branch on code, but never display server text directly. */
export function parseApiErrorEnvelope(input: unknown): ApiErrorEnvelope | null {
  try {
    const outer = object(input)
    if (Object.keys(outer).length === 1 && Object.hasOwn(outer, 'detail')
        && outer.detail !== null && typeof outer.detail === 'object' && !Array.isArray(outer.detail)) {
      const detail = object(outer.detail)
      keys(detail, ['code', 'message'], ['path', 'current_revision'])
      const code = text(detail.code, 64)
      requireValue(/^[A-Z][A-Z0-9_]*$/.test(code))
      const message = text(detail.message, 512)
      if (Object.hasOwn(detail, 'path')) text(detail.path, 512)
      if (Object.hasOwn(detail, 'current_revision')) integer(detail.current_revision, 0)
      return Object.freeze({ code, message })
    }
    const value = outer
    keys(value, ['code', 'message'], ['detail'])
    const code = text(value.code, 64)
    requireValue(/^[A-Z][A-Z0-9_]*$/.test(code))
    const message = text(value.message, 512)
    if (!Object.hasOwn(value, 'detail')) return Object.freeze({ code, message })
    requireValue(Array.isArray(value.detail) && value.detail.length <= 32)
    const detail = value.detail.map((raw) => {
      const row = object(raw); keys(row, ['loc', 'type', 'msg'])
      requireValue(Array.isArray(row.loc) && row.loc.length <= 12)
      const loc = row.loc.map((part) => {
        requireValue((typeof part === 'string' && part.length > 0 && part.length <= 64)
          || (typeof part === 'number' && Number.isSafeInteger(part) && part >= 0))
        return part as string | number
      })
      return Object.freeze({ loc: Object.freeze(loc), type: text(row.type, 64), msg: text(row.msg, 256) })
    })
    return Object.freeze({ code, message, detail: Object.freeze(detail) })
  } catch {
    return null
  }
}

const states: readonly string[] = ['ENABLED', 'ENABLED_WITH_LIMIT', 'INTERNAL', 'UNAVAILABLE', 'BLOCKED']
const legacyCapabilityNames = ['strategy_graph', 'backtesting', 'research_review', 'provider_connections',
  'static_watchlists', 'monitoring', 'signals', 'execution', 'orders', 'positions', 'execution_stream', 'capital_admission']
const capabilityNames = [...legacyCapabilityNames, 'data_provider_onboarding']

export function parseManifest(input: unknown): ReleaseManifest {
  const value = object(input)
  keys(value, ['schema', 'release_profile', 'research_enabled', 'service_role', 'allowed_service_roles',
    'required_readiness_planes', 'capabilities', 'route_rules', 'execution_authority'])
  requireValue(value.schema === 'strategy-os-release-profile/1' && value.release_profile === 'v0_research_signal')
  requireValue(value.research_enabled === true && value.service_role === 'api' && value.execution_authority === false)
  exactSet(value.allowed_service_roles, ['api', 'research_worker', 'monitor', 'scheduler'])
  exactSet(value.required_readiness_planes, ['execution', 'ledger', 'research'])
  const rawCapabilities = object(value.capabilities)
  const hasProviderOnboarding = Object.hasOwn(rawCapabilities, 'data_provider_onboarding')
  keys(rawCapabilities, hasProviderOnboarding ? capabilityNames : legacyCapabilityNames)
  const capabilities: Record<string, Capability> = {}
  for (const [name, raw] of Object.entries(rawCapabilities)) {
    const capability = object(raw)
    keys(capability, ['state'], ['ui_navigation', 'reason'])
    requireValue(typeof capability.state === 'string' && states.includes(capability.state))
    requireValue(!Object.hasOwn(capability, 'ui_navigation') || typeof capability.ui_navigation === 'boolean')
    if (Object.hasOwn(capability, 'reason')) text(capability.reason, 1024)
    if (capability.state === 'BLOCKED') text(capability.reason, 1024)
    if (capability.ui_navigation === true) requireValue(['ENABLED', 'ENABLED_WITH_LIMIT'].includes(capability.state))
    capabilities[name] = Object.freeze({ ...capability }) as Capability
  }
  if (!hasProviderOnboarding) capabilities.data_provider_onboarding = Object.freeze({
    state: 'BLOCKED', ui_navigation: false, reason: 'Data provider onboarding is not published by this server.',
  })
  for (const name of ['execution', 'orders', 'positions', 'execution_stream']) {
    requireValue(capabilities[name].state === 'UNAVAILABLE' && capabilities[name].ui_navigation !== true)
  }
  requireValue(capabilities.capital_admission.state === 'INTERNAL' && capabilities.capital_admission.ui_navigation !== true)
  requireValue(Array.isArray(value.route_rules) && value.route_rules.length > 0 && value.route_rules.length <= 256)
  const seen = new Set<string>()
  for (const raw of value.route_rules) {
    const rule = object(raw)
    keys(rule, ['method', 'template', 'state', 'capability', 'reason'])
    requireValue(['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'WEBSOCKET', '*'].includes(text(rule.method, 16)))
    requireValue(/^\/(api\/|ws(?:\/|$))/.test(text(rule.template, 256)))
    requireValue(rule.state === 'UNAVAILABLE')
    text(rule.capability, 128); text(rule.reason, 1024)
    const identity = `${rule.method} ${rule.template}`
    requireValue(!seen.has(identity)); seen.add(identity)
  }
  return Object.freeze({ schema: value.schema, release_profile: value.release_profile,
    research_enabled: true, service_role: 'api', execution_authority: false, capabilities: Object.freeze(capabilities) })
}

export function strategiesEnabled(manifest: ReleaseManifest): boolean {
  const capability = manifest.capabilities.strategy_graph
  return ['ENABLED', 'ENABLED_WITH_LIMIT'].includes(capability.state) && capability.ui_navigation === true
}

export function staticScopesEnabled(manifest: ReleaseManifest): boolean {
  return ['ENABLED', 'ENABLED_WITH_LIMIT'].includes(manifest.capabilities.static_watchlists?.state)
}

export function providerOnboardingEnabled(manifest: ReleaseManifest): boolean {
  const capability = manifest.capabilities.data_provider_onboarding
  return capability?.state === 'ENABLED_WITH_LIMIT' && capability.ui_navigation === true
}

export function parseProjects(input: unknown): readonly Project[] {
  requireValue(Array.isArray(input) && input.length <= 10000)
  const seen = new Set<string>()
  return Object.freeze(input.map((raw) => {
    const value = object(raw)
    keys(value, ['project_id', 'name', 'description', 'status'])
    const project_id = text(value.project_id, 64)
    requireValue(!seen.has(project_id)); seen.add(project_id)
    requireValue(value.status === 'active' || value.status === 'archived')
    return Object.freeze({ project_id, name: text(value.name, 128), description: text(value.description, 4000, true), status: value.status })
  }))
}

export function parseProjectPage(input: unknown, after: string | null, limit: number): ProjectPage {
  const value = object(input); keys(value, ['schema', 'items', 'next_cursor'])
  requireValue(value.schema === 'strategy-os-research-project-page/1' && Array.isArray(value.items) && value.items.length <= limit)
  const items = parseProjects(value.items)
  requireValue(items.every((item) => item.project_id !== after))
  const next_cursor = value.next_cursor === null ? null : text(value.next_cursor, 64)
  requireValue(next_cursor === null || (items.length === limit && next_cursor === items.at(-1)?.project_id))
  return Object.freeze({ schema: value.schema, items, next_cursor })
}

export function parseGraphPage(input: unknown, projectId: string, after: string | null, limit: number): GraphPage {
  const value = object(input)
  keys(value, ['schema', 'project_id', 'items', 'next_cursor'])
  requireValue(value.schema === 'strategy-os-graph-index/1' && value.project_id === projectId)
  requireValue(Array.isArray(value.items) && value.items.length <= limit)
  const seen = new Set<string>()
  const items = value.items.map((raw) => {
    const row = object(raw)
    keys(row, ['identifier', 'display_name', 'draft_revision', 'current_version'])
    const identifier = text(row.identifier, 128)
    requireValue(!seen.has(identifier) && identifier !== after); seen.add(identifier)
    return Object.freeze({ identifier, display_name: text(row.display_name, 128),
      draft_revision: integer(row.draft_revision, 0), current_version: row.current_version === null ? null : integer(row.current_version, 1) })
  })
  const next_cursor = value.next_cursor === null ? null : text(value.next_cursor, 128)
  requireValue(next_cursor === null || (items.length === limit && next_cursor === items.at(-1)?.identifier))
  return Object.freeze({ schema: value.schema, project_id: projectId, items: Object.freeze(items), next_cursor })
}

function address(value: unknown): string {
  const result = text(value, 71)
  requireValue(/^sha256:[0-9a-f]{64}$/.test(result))
  return result
}

function specIdentifier(value: unknown): string {
  const result = text(value, 128)
  requireValue(/^[a-zA-Z0-9._:-]+$/.test(result))
  return result
}

function timestamp(value: unknown): string {
  const result = text(value, 40)
  requireValue(Number.isFinite(Date.parse(result)))
  return result
}

function publishedGraph(input: unknown): PublishedGraph {
  const value = object(input)
  const v2 = Object.hasOwn(value, 'format_version')
  keys(value, ['project_id', 'identifier', 'version', 'content_address', ...(v2 ? ['format_version', 'graph_address'] : [])], ['graph'])
  if (v2) { requireValue(value.format_version === 2); address(value.graph_address) }
  return Object.freeze({ project_id: text(value.project_id, 64), identifier: text(value.identifier, 128),
    version: integer(value.version, 1), content_address: address(value.content_address) })
}

function datasetBindings(input: unknown): ExperimentRun['dataset_bindings'] {
  if (input === undefined) return Object.freeze([])
  const container = object(input)
  keys(container, ['schema', 'codec', 'adapter_contract', 'adapter_source_address', 'bindings'])
  requireValue(container.schema === 'canonical-dataset-bindings/1'
    && container.codec === 'strategy-os-observation-candle-index/1'
    && container.adapter_contract === 'q03-provider-provenance-index-encoding/1')
  address(container.adapter_source_address)
  const raw = object(container.bindings)
  requireValue(Object.keys(raw).length <= 8)
  const seen = new Set<string>()
  return Object.freeze(Object.entries(raw).sort(([left], [right]) => left.localeCompare(right)).map(([, item]) => {
    const row = object(item)
    const instrument_address = address(row.instrument_address)
    requireValue(!seen.has(instrument_address)); seen.add(instrument_address)
    const interpretation = object(row.time_interpretation)
    const seconds = integer(interpretation.resolution_seconds, 1)
    const interval = ({ 900: '15minute', 1800: '30minute', 3600: '60minute' } as Record<number, string>)[seconds]
    requireValue(interval !== undefined)
    return Object.freeze({ instrument_address, manifest_address: address(row.manifest_address),
      as_of: timestamp(row.as_of), interval })
  }))
}

function finiteNumber(value: unknown, minimum: number, maximum: number): number {
  requireValue(typeof value === 'number' && Number.isFinite(value) && value >= minimum && value <= maximum)
  return value
}

function experimentContract(source: Record<string, unknown>): ExperimentContract {
  const costs = object(source.cost_assumptions)
  keys(costs, ['capital', 'slippage_bps', 'slippage_multiplier', 'charge_model', 'sizing_model'])
  finiteNumber(costs.capital, 1, 1_000_000_000)
  requireValue(costs.charge_model === 'zerodha_charges_v1' && costs.sizing_model === 'one_lot_or_cash_budget_v1')
  const gates = object(source.gates)
  keys(gates, ['min_oos_trades', 'n_folds', 'min_positive_fold_fraction', 'optimize_search', 'pbo_threshold', 'sibling_trials'])
  requireValue(typeof gates.optimize_search === 'boolean')
  return Object.freeze({ charge_model: costs.charge_model, sizing_model: costs.sizing_model,
    slippage_bps: finiteNumber(costs.slippage_bps, 0, 10_000), slippage_multiplier: finiteNumber(costs.slippage_multiplier, 0, 100),
    gates: Object.freeze({ min_oos_trades: integer(gates.min_oos_trades, 1), n_folds: integer(gates.n_folds, 2),
      min_positive_fold_fraction: finiteNumber(gates.min_positive_fold_fraction, 0, 1), optimize_search: gates.optimize_search,
      pbo_threshold: finiteNumber(gates.pbo_threshold, 0, 1), sibling_trials: integer(gates.sibling_trials, 1) }) })
}

export function parsePublishedGraph(input: unknown): PublishedGraph {
  const value = object(input)
  keys(value, ['project_id', 'identifier', 'version', 'content_address', 'graph'])
  return publishedGraph(value)
}

export function parseVersions(input: unknown): readonly PublishedGraph[] {
  requireValue(Array.isArray(input) && input.length <= 10000)
  return Object.freeze(input.map(publishedGraph))
}

const helpKinds = ['MATHEMATICAL_FORMULA', 'FIELD_SELECTION', 'FIELD_SPLITTER', 'LOGICAL_OPERATION', 'INTENT_BEHAVIOR'] as const
const helpBoundary = 'This is an immutable built-in. You can change only the listed parameters; you cannot edit its code here.'
const rawHelpAddress = /(?:sha256:)?[0-9a-f]{64}/i
export function sameJson(left: unknown, right: unknown): boolean {
  if (left === right) return true
  if (Array.isArray(left) || Array.isArray(right)) return Array.isArray(left) && Array.isArray(right)
    && left.length === right.length && left.every((value, index) => sameJson(value, right[index]))
  if (left !== null && right !== null && typeof left === 'object' && typeof right === 'object') {
    const a = left as Record<string, unknown>; const b = right as Record<string, unknown>
    const aKeys = Object.keys(a).sort(); const bKeys = Object.keys(b).sort()
    return aKeys.length === bKeys.length && aKeys.every((key, index) => key === bKeys[index] && sameJson(a[key], b[key]))
  }
  return false
}
function parseCompositionBinding(raw: unknown, componentAddress: unknown, registryIdentity: string) {
  const binding = object(raw)
  keys(binding, ['component_address', 'registry_identity'])
  requireValue(address(binding.component_address) === componentAddress)
  requireValue(address(binding.registry_identity) === registryIdentity)
  return Object.freeze({ component_address: binding.component_address as string, registry_identity: registryIdentity })
}
function parseHelpBinding(help: Record<string, unknown>, row: Record<string, unknown>, registryIdentity: string) {
  if (row.component_kind === 'COMPOUND') {
    requireValue(help.implementation_binding === null)
    const composition_binding = parseCompositionBinding(help.composition_binding, row.component_address, registryIdentity)
    return { implementation_binding: null, composition_binding } as const
  }
  const implementation_binding = address(help.implementation_binding)
  requireValue(implementation_binding === row.implementation_address)
  return { implementation_binding } as const
}
function parseHelpSource(raw: unknown): CatalogueHelpSource {
  const source = object(raw)
  keys(source, ['source_record_id', 'title', 'authors_or_organization', 'publication_or_version', 'year', 'url', 'claim_scope'])
  const source_record_id = text(source.source_record_id, 256); const title = text(source.title, 1024)
  const authors_or_organization = text(source.authors_or_organization, 1024)
  const publication_or_version = text(source.publication_or_version, 1024); const claim_scope = text(source.claim_scope, 1024)
  requireValue(![source_record_id, title, authors_or_organization, publication_or_version, claim_scope].some((value) => rawHelpAddress.test(value)))
  requireValue(source.year === null || (typeof source.year === 'number' && Number.isSafeInteger(source.year) && source.year >= 1800 && source.year <= 2200))
  const url = source.url === null ? null : text(source.url, 2048)
  requireValue(url === null || (url.startsWith('https://') && !rawHelpAddress.test(url)))
  return Object.freeze({ source_record_id, title, authors_or_organization, publication_or_version, year: source.year as number | null, url, claim_scope })
}
function parseHelpSources(raw: unknown) {
  requireValue(Array.isArray(raw) && raw.length > 0 && raw.length <= 16)
  const sources = (raw as unknown[]).map(parseHelpSource)
  requireValue(new Set(sources.map((source) => source.source_record_id)).size === sources.length)
  return Object.freeze(sources)
}
function parseHelpParameter(raw: unknown, descriptorParameters: Record<string, unknown>): CatalogueHelpParameter {
  const parameter = object(raw)
  keys(parameter, ['name', 'type', 'required', 'default', 'enum', 'domain', 'units', 'serialization'])
  const name = text(parameter.name, 128); const source = object(descriptorParameters[name])
  keys(source, ['type', 'required', 'default', 'enum', 'domain', 'units', 'serialization'])
  requireValue(typeof parameter.required === 'boolean' && parameter.required === source.required)
  for (const field of ['type', 'units', 'serialization'] as const) requireValue(text(parameter[field], 128) === source[field])
  for (const field of ['default', 'enum', 'domain'] as const) requireValue(sameJson(parameter[field], source[field]))
  return Object.freeze({ name, type: parameter.type as string, required: parameter.required as boolean,
    default: parameter.default, enum: parameter.enum, domain: parameter.domain,
    units: parameter.units as string, serialization: parameter.serialization as string })
}
function parseHelpCustomisation(raw: unknown, descriptor: Record<string, unknown>): CatalogueHelp['customisation'] {
  const customisation = object(raw)
  keys(customisation, ['parameters', 'guidance', 'built_in_code_immutable', 'immutable_boundary'])
  requireValue(customisation.built_in_code_immutable === true && customisation.immutable_boundary === helpBoundary)
  const descriptorParameters = object(descriptor.parameters)
  requireValue(Array.isArray(customisation.parameters) && customisation.parameters.length === Object.keys(descriptorParameters).length)
  const parameters = (customisation.parameters as unknown[]).map((value) => parseHelpParameter(value, descriptorParameters))
  const names = new Set(parameters.map((parameter) => parameter.name))
  requireValue(names.size === parameters.length && Object.keys(descriptorParameters).every((name) => names.has(name)))
  const guidance = text(customisation.guidance, 1024)
  if (!parameters.length) requireValue(guidance === 'This built-in has no parameters.')
  return Object.freeze({ parameters: Object.freeze(parameters), guidance, built_in_code_immutable: true, immutable_boundary: helpBoundary })
}
function parseHelpAvailability(raw: unknown, availability: Record<string, unknown>): CatalogueHelp['availability'] {
  const value = object(raw); keys(value, ['status', 'authority', 'condition'])
  requireValue(value.status === availability.status && value.authority === availability.authority)
  return Object.freeze({ status: value.status as 'AVAILABLE' | 'CONDITIONAL', authority: value.authority as 'NONE' | 'MONITORING_ONLY', condition: text(value.condition, 2048) })
}
function displaySemanticText(componentId: string, kind: string, description: string, semanticText: string) {
  if (componentId !== 'analytical.ohlcv') return semanticText
  requireValue(kind === 'FIELD_SPLITTER')
  requireValue(description === 'Splits each fully completed candle into five named outputs: open, high, low, close and volume. It does not calculate an indicator.')
  requireValue(semanticText === 'Return separately named canonical completed-bar open, high, low, close and volume series. No DataFrame hidden under a scalar value port.')
  return 'Return separately named completed-bar open, high, low, close and volume series. No DataFrame hidden under a scalar value port.'
}
function parseCatalogueHelp(raw: unknown, row: Record<string, unknown>, descriptor: Record<string, unknown>, availability: Record<string, unknown>, registryIdentity: string): CatalogueHelp {
  const help = object(raw)
  const fields = ['component_id', 'component_version', 'implementation_binding', 'semantic_kind', 'description', 'semantic_text', 'sources', 'customisation', 'availability']
  if (row.component_kind === 'COMPOUND') fields.push('composition_binding')
  keys(help, fields)
  const component_id = text(help.component_id, 128); const component_version = integer(help.component_version, 1)
  requireValue(component_id === row.component_id && component_version === row.component_version)
  const binding = parseHelpBinding(help, row, registryIdentity)
  const semantic_kind = text(help.semantic_kind, 32) as CatalogueHelp['semantic_kind']
  requireValue(helpKinds.includes(semantic_kind))
  const description = text(help.description, 4096)
  const semantic_text = displaySemanticText(component_id, semantic_kind, description, text(help.semantic_text, 16384))
  return Object.freeze({ component_id, component_version, ...binding, semantic_kind, description, semantic_text,
    sources: parseHelpSources(help.sources), customisation: parseHelpCustomisation(help.customisation, descriptor),
    availability: parseHelpAvailability(help.availability, availability) })
}
const catalogueLegacyCounts = { groups: 5, components: 243, analytical_v2: 108, type_3: 63, type_5: 60,
  monitoring_type_1_v2: 12, analytical_unavailable: 17, legacy_type_1_excluded: 61 }
const catalogueCurrentCounts = { ...catalogueLegacyCounts, components: 269, original_primitives: 24, original_compounds: 2 }
const catalogueGapCounts = { ...catalogueCurrentCounts, components: 270, type_3: 64 }
function parseCatalogueAvailability(raw: unknown) {
  const value = object(raw)
  keys(value, ['status', 'authority', 'provider_support_verified', 'data_rights_verified', 'backtest_eligible'])
  requireValue(['AVAILABLE', 'CONDITIONAL'].includes(String(value.status)))
  requireValue(['NONE', 'MONITORING_ONLY'].includes(String(value.authority)))
  requireValue(value.provider_support_verified === false && value.data_rights_verified === false && value.backtest_eligible === false)
  return value
}
function validateLeafCatalogueRow(row: Record<string, unknown>, current: boolean) {
  for (const key of ['node_contract', 'data_requirement', 'mode_eligibility', 'resource_profile']) object(row[key])
  requireValue(Array.isArray(row.provider_requirements))
  address(row.implementation_address); address(row.node_contract_address); address(row.data_requirement_address)
  if (current) requireValue(row.composition_binding === null)
}
function catalogueRowKind(row: Record<string, unknown>, descriptor: Record<string, unknown>, current: boolean, registryIdentity: string): 'LEAF' | 'COMPOUND' {
  const kind = current ? row.component_kind : 'LEAF'
  requireValue(kind === 'LEAF' || kind === 'COMPOUND')
  if (kind === 'LEAF') {
    requireValue(descriptor.compound == null)
    validateLeafCatalogueRow(row, current)
    return kind
  }
  const compound = object(descriptor.compound); keys(compound, ['body', 'parameter_bindings'])
  object(compound.body); requireValue(Array.isArray(compound.parameter_bindings))
  for (const key of ['implementation_address', 'node_contract', 'node_contract_address', 'contract_binding', 'contract_binding_address', 'data_requirement', 'data_requirement_address', 'mode_eligibility', 'provider_requirements', 'resource_profile']) requireValue(row[key] === null)
  parseCompositionBinding(row.composition_binding, row.component_address, registryIdentity)
  return kind
}
function parseCatalogueRow(raw: unknown, group: Record<string, unknown>, current: boolean, registryIdentity: string): CatalogueComponent {
  const row = object(raw)
  const fields = ['component_id', 'component_version', 'component_address', 'display_name', 'visible_family', 'presentation_group_order', 'presentation_group_name', 'domain_family', 'structural_role', 'descriptor', 'node_contract', 'node_contract_address', 'implementation_address', 'contract_binding', 'contract_binding_address', 'data_requirement', 'data_requirement_address', 'mode_eligibility', 'provider_requirements', 'resource_profile', 'availability', 'help']
  if (current) fields.push('component_kind', 'composition_binding')
  keys(row, fields)
  requireValue(row.visible_family === group.visible_family && row.presentation_group_order === group.order && row.presentation_group_name === group.display_name)
  const descriptor = object(row.descriptor)
  requireValue(descriptor.component_id === row.component_id && descriptor.component_version === row.component_version)
  const component_kind = catalogueRowKind(row, descriptor, current, registryIdentity)
  const availability = parseCatalogueAvailability(row.availability)
  if (component_kind === 'COMPOUND') requireValue(availability.status === 'CONDITIONAL' && availability.authority === 'NONE')
  return Object.freeze({ component_kind, component_id: text(row.component_id, 128), component_version: integer(row.component_version, 1),
    component_address: address(row.component_address), display_name: text(row.display_name, 128),
    visible_family: text(row.visible_family, 16), presentation_group_name: text(row.presentation_group_name, 128),
    descriptor: Object.freeze(descriptor), data_requirement: component_kind === 'COMPOUND' ? null : Object.freeze(object(row.data_requirement)),
    help: parseCatalogueHelp(row.help, row, descriptor, availability, registryIdentity),
    availability: Object.freeze({ status: availability.status as 'AVAILABLE' | 'CONDITIONAL', authority: availability.authority as 'NONE' | 'MONITORING_ONLY', provider_support_verified: false, data_rights_verified: false, backtest_eligible: false }) })
}
function parseCatalogueGroup(raw: unknown, index: number, current: boolean, registryIdentity: string): CatalogueGroup {
  const group = object(raw); keys(group, ['order', 'visible_family', 'display_name', 'components'])
  requireValue(group.order === index + 1 && Array.isArray(group.components) && group.components.length <= 500)
  return Object.freeze({ order: index + 1, visible_family: text(group.visible_family, 16), display_name: text(group.display_name, 128),
    components: Object.freeze((group.components as unknown[]).map((row) => parseCatalogueRow(row, group, current, registryIdentity))) })
}
const originalPrimitiveV2 = ['close', 'high', 'low', 'true_range'] as const
const originalPrimitiveV1 = ['value', 'ema_first_close', 'rolling_stddev_population', 'lag', 'subtract', 'divide', 'abs', 'gt', 'lt', 'and', 'or', 'fallback_zero', 'fallback_false', 'rma_sma_seed', 'nearest_rank', 'multiply', 'maximum', 'le', 'fallback_value', 'optional_condition'] as const
const originalCatalogueIdentities = new Set([
  ...originalPrimitiveV2.map((name) => `strategy_math.${name}@2`), ...originalPrimitiveV1.map((name) => `strategy_math.${name}@1`),
  'strategy.trend_impulse_v3@1', 'strategy.expanding_z_v4_pine@1',
])
function validateOriginalCatalogue(components: readonly CatalogueComponent[]) {
  const originals = components.filter((row) => row.component_id.startsWith('strategy_math.') || row.component_kind === 'COMPOUND')
  requireValue(originals.length === originalCatalogueIdentities.size)
  requireValue(originals.every((row) => originalCatalogueIdentities.has(`${row.component_id}@${row.component_version}`)))
  requireValue(originals.filter((row) => row.component_kind === 'COMPOUND').length === 2)
}
function expectedCatalogueCounts(components: readonly CatalogueComponent[], current: boolean) {
  if (!current) return catalogueLegacyCounts
  const gap = components.find((row) => row.component_id === 'structure.historical_daily_gaps')
  if (!gap) return catalogueCurrentCounts
  requireValue(gap.component_version === 2 && gap.visible_family === 'TYPE_3')
  return catalogueGapCounts
}
function validateCatalogueCounts(value: Record<string, unknown>, components: readonly CatalogueComponent[], current: boolean) {
  const expected = expectedCatalogueCounts(components, current)
  requireValue(components.length === expected.components)
  requireValue(new Set(components.map((row) => `${row.component_id}@${row.component_version}`)).size === components.length)
  const kinds = current ? { MATHEMATICAL_FORMULA: expected === catalogueGapCounts ? 181 : 180, FIELD_SELECTION: 29, FIELD_SPLITTER: 1, LOGICAL_OPERATION: 47, INTENT_BEHAVIOR: 12 }
    : { MATHEMATICAL_FORMULA: 167, FIELD_SELECTION: 26, FIELD_SPLITTER: 1, LOGICAL_OPERATION: 37, INTENT_BEHAVIOR: 12 }
  for (const kind of helpKinds) requireValue(components.filter((row) => row.help.semantic_kind === kind).length === kinds[kind])
  requireValue(components.filter((row) => row.help.customisation.parameters.length).length === (current ? 170 : 161))
  if (current) validateOriginalCatalogue(components)
  const counts = object(value.counts); keys(counts, Object.keys(expected)); requireValue(sameJson(counts, expected))
}
function catalogueExclusionIdentity(raw: unknown) {
  const exclusion = object(raw)
  keys(exclusion, ['kind', 'component_id', 'component_version', 'visible_family', 'reason_code', 'executable', 'authority'], ['replacement_component_version'])
  requireValue(exclusion.kind === 'ANALYTICAL_V2_UNAVAILABLE' || exclusion.kind === 'LEGACY_TYPE_1_EXCLUDED')
  requireValue(typeof exclusion.reason_code === 'string' && exclusion.reason_code.length > 0 && exclusion.executable === false && exclusion.authority === 'NONE')
  return `${text(exclusion.component_id, 128)}@${integer(exclusion.component_version, 1)}`
}
function validateCatalogueExclusions(raw: unknown) {
  requireValue(Array.isArray(raw) && raw.length === 78)
  const identities = (raw as unknown[]).map(catalogueExclusionIdentity)
  requireValue(new Set(identities).size === identities.length)
}
export function parseCatalogue(input: unknown): VerifiedCatalogue {
  const value = object(input)
  keys(value, ['schema', 'registry_identity', 'groups', 'exclusions', 'counts', 'nonauthority', 'catalogue_identity'])
  requireValue(value.schema === 'strategy-os-verified-language-catalogue/1' || value.schema === 'strategy-os-verified-language-catalogue/2')
  const current = value.schema === 'strategy-os-verified-language-catalogue/2'; const registry_identity = address(value.registry_identity)
  requireValue(Array.isArray(value.groups) && value.groups.length === 5)
  const groups = (value.groups as unknown[]).map((raw, index) => parseCatalogueGroup(raw, index, current, registry_identity))
  validateCatalogueCounts(value, groups.flatMap((group) => group.components), current)
  validateCatalogueExclusions(value.exclusions)
  const nonauthority = object(value.nonauthority)
  keys(nonauthority, ['execution_authority', 'provider_conformance', 'data_rights', 'backtest_eligibility', 'monitoring_runtime', 'deployment_authority'])
  requireValue(Object.values(nonauthority).every((state) => state === false))
  return Object.freeze({ schema: value.schema as VerifiedCatalogue['schema'], registry_identity, catalogue_identity: address(value.catalogue_identity), groups: Object.freeze(groups) })
}

export function parseEditor(input: unknown, projectId: string, graphId: string): EditorDocument {
  const value = object(input)
  keys(value, ['project_id', 'identifier', 'display_name', 'draft_revision', 'version', 'content_address',
    'authored_graph', 'view', 'editable_nodes', 'component_catalogue', 'graph_sockets', 'layout', 'command_receipt'])
  requireValue(value.project_id === projectId && value.identifier === graphId && Array.isArray(value.editable_nodes))
  const layout = object(value.layout); keys(layout, ['graph_identifier', 'graph_version', 'revision', 'positions', 'groups'])
  requireValue(layout.graph_identifier === graphId && layout.graph_version === value.version
    && Array.isArray(layout.positions) && Array.isArray(layout.groups))
  requireValue(Array.isArray(value.component_catalogue) && Array.isArray(value.graph_sockets))
  const view = object(value.view); keys(view, ['identifier', 'version', 'display_name', 'warmup', 'layers', 'inputs', 'outputs', 'nodes', 'edges'])
  requireValue(view.identifier === graphId && Array.isArray(view.nodes) && Array.isArray(view.edges))
  const viewNodes = new Map((view.nodes as unknown[]).map((raw) => {
    const row = object(raw); keys(row, ['instance_id', 'label', 'container', 'definition', 'params', 'warmup', 'purity', 'cache_id', 'derived', 'layer', 'row', 'placed'])
    return [text(row.instance_id, 128), row] as const
  }))
  const socket = (raw: unknown): EditorSocket => {
    const row = object(raw); keys(row, ['identifier', 'display_name', 'direction', 'wire_type', 'has_default_source'])
    requireValue(row.direction === 'input' || row.direction === 'output'); requireValue(typeof row.has_default_source === 'boolean')
    return Object.freeze({ identifier: text(row.identifier, 128), display_name: text(row.display_name, 128), direction: row.direction,
      wire_type: Object.freeze(object(row.wire_type)), has_default_source: row.has_default_source })
  }
  const nodes = value.editable_nodes.map((raw) => {
    const row = object(raw)
    keys(row, ['instance_id', 'component_identifier', 'component_version', 'parameters', 'sockets'])
    requireValue(Array.isArray(row.parameters) && Array.isArray(row.sockets))
    const parameters = row.parameters.map((candidate) => {
      const parameter = object(candidate)
      keys(parameter, ['identifier', 'kind', 'default', 'value', 'overridden'])
      requireValue(typeof parameter.overridden === 'boolean')
      return Object.freeze({ identifier: text(parameter.identifier, 128), kind: text(parameter.kind, 64),
        default: parameter.default, value: parameter.value, overridden: parameter.overridden })
    })
    const instance_id = text(row.instance_id, 128); const rendered = viewNodes.get(instance_id); requireValue(rendered !== undefined)
    return Object.freeze({ instance_id, label: text(rendered.label, 128), component_identifier: text(row.component_identifier, 128),
      component_version: integer(row.component_version, 1), parameters: Object.freeze(parameters),
      sockets: Object.freeze(row.sockets.map(socket)), layer: integer(rendered.layer, 0), row: integer(rendered.row, 0) })
  })
  const edges = (view.edges as unknown[]).filter((raw) => !object(raw).derived).map((raw) => {
    const row = object(raw); keys(row, ['source', 'target', 'source_socket', 'target_socket', 'derived']); requireValue(typeof row.derived === 'boolean')
    return Object.freeze({ source: text(row.source, 128), target: text(row.target, 128), source_socket: text(row.source_socket, 128),
      target_socket: text(row.target_socket, 128), derived: row.derived })
  })
  const positions = (layout.positions as unknown[]).map((raw) => { const row = object(raw); keys(row, ['instance_id', 'x', 'y'])
    return Object.freeze({ instance_id: text(row.instance_id, 128), x: finiteNumber(row.x, -1_000_000, 1_000_000), y: finiteNumber(row.y, -1_000_000, 1_000_000) }) })
  const groups = (layout.groups as unknown[]).map((raw) => { const row = object(raw); keys(row, ['identifier', 'display_name', 'frame', 'collapsed', 'members'])
    const frame = object(row.frame); keys(frame, ['x', 'y', 'width', 'height']); requireValue(typeof row.collapsed === 'boolean' && Array.isArray(row.members))
    return Object.freeze({ identifier: text(row.identifier, 128), display_name: text(row.display_name, 128), collapsed: row.collapsed,
      members: Object.freeze(row.members.map((item) => text(item, 128))), frame: Object.freeze({ x: finiteNumber(frame.x, -1_000_000, 1_000_000),
        y: finiteNumber(frame.y, -1_000_000, 1_000_000), width: finiteNumber(frame.width, 0.000001, 1_000_000), height: finiteNumber(frame.height, 0.000001, 1_000_000) }) }) })
  const component_catalogue = (value.component_catalogue as unknown[]).map((raw) => { const row = object(raw); keys(row, ['identifier', 'version', 'display_name', 'parameters', 'sockets'])
    requireValue(Array.isArray(row.parameters) && Array.isArray(row.sockets)); return Object.freeze({ identifier: text(row.identifier, 128), version: integer(row.version, 1),
      display_name: text(row.display_name, 128), parameters: Object.freeze(row.parameters.map((candidate) => { const p = object(candidate); keys(p, ['identifier', 'display_name', 'kind', 'default', 'panel_path']); requireValue(Array.isArray(p.panel_path))
        return Object.freeze({ identifier: text(p.identifier, 128), display_name: text(p.display_name, 128), kind: text(p.kind, 64), default: p.default,
          panel_path: Object.freeze(p.panel_path.map((item) => text(item, 128))) }) })), sockets: Object.freeze(row.sockets.map(socket)) }) })
  const graph_sockets = (value.graph_sockets as unknown[]).map((raw) => { const row = object(raw); keys(row, ['instance_id', 'identifier', 'display_name', 'direction', 'wire_type', 'has_default_source'])
    requireValue(row.instance_id === 'io_in' || row.instance_id === 'io_out'); return Object.freeze({ ...socket({ identifier: row.identifier, display_name: row.display_name,
      direction: row.direction, wire_type: row.wire_type, has_default_source: row.has_default_source }), instance_id: row.instance_id }) })
  let command_receipt: CommandReceipt | null = null
  if (value.command_receipt !== null) { const receipt = object(value.command_receipt)
    requireValue(Array.isArray(receipt.semantic_forward_operations) && Array.isArray(receipt.semantic_inverse_operations)); const delta = object(receipt.presentation_delta)
    requireValue(Array.isArray(delta.forward_operations) && Array.isArray(delta.inverse_operations))
    command_receipt = Object.freeze({ semantic_forward_operations: Object.freeze(receipt.semantic_forward_operations.map((item) => Object.freeze(object(item)))),
      semantic_inverse_operations: Object.freeze(receipt.semantic_inverse_operations.map((item) => Object.freeze(object(item)))), presentation_delta: Object.freeze({
        forward_operations: Object.freeze(delta.forward_operations.map((item) => Object.freeze(object(item)))), inverse_operations: Object.freeze(delta.inverse_operations.map((item) => Object.freeze(object(item)))) }),
      draft_revision: integer(receipt.draft_revision, 0), version: integer(receipt.version, 1), presentation_revision: integer(receipt.presentation_revision, 0), content_address: address(receipt.content_address) }) }
  return Object.freeze({ project_id: projectId, identifier: graphId, display_name: text(value.display_name, 128),
    draft_revision: integer(value.draft_revision, 0), version: integer(value.version, 1), content_address: address(value.content_address),
    presentation_revision: integer(layout.revision, 0), nodes: Object.freeze(nodes), edges: Object.freeze(edges), component_catalogue: Object.freeze(component_catalogue),
    graph_sockets: Object.freeze(graph_sockets), layout: Object.freeze({ revision: integer(layout.revision, 0), positions: Object.freeze(positions), groups: Object.freeze(groups) }), command_receipt })
}

function parseExperimentSummary(input: unknown): ExperimentRun {
  const value = object(input)
  keys(value, ['run_id', 'spec_id', 'status', 'decision', 'evidence_state', 'graph', 'candidate'], ['evidence'])
  const state = text(value.evidence_state, 32)
  requireValue(['verified', 'legacy_unbound', 'corrupt', 'pending', 'running'].includes(state))
  let bindings: ExperimentRun['dataset_bindings'] = Object.freeze([])
  let contract: ExperimentContract | null = null
  if (Object.hasOwn(value, 'evidence') && value.evidence !== null) {
    const evidence = object(value.evidence)
    const provenance = object(evidence.provenance)
    const graphProvenance = object(provenance.graph_provenance)
    bindings = datasetBindings(graphProvenance.canonical_dataset_bindings)
    contract = experimentContract(provenance)
  }
  return Object.freeze({ run_id: integer(value.run_id, 1), spec_id: specIdentifier(value.spec_id), status: text(value.status, 64),
    decision: value.decision === null ? null : text(value.decision, 64), evidence_state: state,
    graph: publishedGraph(value.graph), dataset_bindings: bindings, contract }) as ExperimentRun
}

export function parseExperimentPage(input: unknown): ExperimentPage {
  const value = object(input); keys(value, ['runs'])
  requireValue(Array.isArray(value.runs) && value.runs.length <= 10000)
  return Object.freeze({ runs: Object.freeze(value.runs.map(parseExperimentSummary)) })
}

export function parseResearchRunPage(input: unknown, projectId: string, limit: number): ResearchRunPage {
  const value = object(input); keys(value, ['schema', 'project_id', 'runs', 'next_cursor'])
  requireValue(value.schema === 'strategy-os-research-run-page/1' && value.project_id === projectId
    && Array.isArray(value.runs) && value.runs.length <= limit)
  const runs = value.runs.map(parseExperimentSummary)
  requireValue(runs.every((run) => run.graph.project_id === projectId))
  const next_cursor = value.next_cursor === null ? null : integer(value.next_cursor, 1)
  return Object.freeze({ schema: value.schema, project_id: projectId, runs: Object.freeze(runs), next_cursor })
}

export function parseExperimentDetail(input: unknown): ExperimentRun {
  const summary = parseExperimentSummary(input), envelope = object(input)
  if (envelope.evidence === undefined || envelope.evidence === null) return summary
  const raw = object(envelope.evidence).results
  if (raw === null || typeof raw !== 'object' || Array.isArray(raw)) return summary
  const results = object(raw)
  const outcome = researchOutcome(summary, object(envelope.evidence), results)
  const detail = { ...summary, ...(outcome ? { research_outcome: outcome } : {}) }
  if (!Object.hasOwn(results, 'canonical_optimization')) return Object.freeze(detail)
  requireValue(summary.evidence_state === 'verified')
  return Object.freeze({ ...detail, canonical_optimization: parseCanonicalOptimizationEvidence(results.canonical_optimization, summary.graph.identifier),
    optimization_research_gates: optimizationResearchGates(results.instruments) })
}

function outcomeInstruments(input: unknown): readonly string[] {
  requireValue(Array.isArray(input) && input.length <= 10000)
  const values = (input as unknown[]).map((value) => text(value, 256))
  requireValue(new Set(values).size === values.length)
  return values
}

function requireOutcomeIdentity(summary: ExperimentRun, evidence: Record<string, unknown>) {
  requireValue(summary.evidence_state === 'verified' && summary.status === 'completed' && evidence.spec_id === summary.spec_id)
  const run = object(evidence.run)
  requireValue(run.id === summary.run_id && run.status === summary.status && run.decision === summary.decision)
  const graph = object(object(evidence.provenance).graph_provenance).graph
  requireValue(sameJson(publishedGraph(graph), summary.graph))
}

function researchOutcome(summary: ExperimentRun, evidence: Record<string, unknown>, results: Record<string, unknown>): ExperimentRun['research_outcome'] {
  if (!Object.hasOwn(results, 'rejected')) return undefined
  requireOutcomeIdentity(summary, evidence)
  const qualified = outcomeInstruments(results.qualified), validated = outcomeInstruments(results.validated)
  requireValue(validated.every((name) => qualified.includes(name)))
  requireValue(Array.isArray(results.rejected) && results.rejected.length <= 10000)
  const rejected = (results.rejected as unknown[]).map((input) => {
    const row = object(input); keys(row, ['instrument', 'reason'])
    return Object.freeze({ instrument: text(row.instrument, 256), reason: text(row.reason, 2000) })
  })
  return Object.freeze({ qualified: qualified.length, validated: validated.length,
    total_bars: integer(results.total_bars, 0), rejected: Object.freeze(rejected) })
}

export function parseExperimentStart(input: unknown): ExperimentStart {
  const value = object(input); keys(value, ['spec_id', 'run_id', 'decision', 'binding'])
  requireValue(value.decision === 'propose' || value.decision === 'archive')
  const binding = object(value.binding)
  return Object.freeze({ spec_id: specIdentifier(value.spec_id), run_id: integer(value.run_id, 1), decision: value.decision,
    graph: publishedGraph(binding.graph), dataset_bindings: datasetBindings(binding.canonical_dataset_bindings),
    contract: experimentContract(binding) })
}

export function parseComparison(input: unknown): VersionComparison {
  const value = object(input); keys(value, ['equivalent', 'incomparable', 'differences'], ['left', 'right'])
  requireValue(typeof value.equivalent === 'boolean' && Array.isArray(value.incomparable) && Array.isArray(value.differences))
  const incomparable = value.incomparable.map((item) => text(item, 128))
  const differences = value.differences.map((raw) => {
    const row = object(raw); keys(row, ['dimension', 'path', 'left', 'right'])
    requireValue(Array.isArray(row.path) && row.path.length <= 64)
    const path = row.path.map((item) => { requireValue(typeof item === 'string' || Number.isSafeInteger(item)); return item as string | number })
    return Object.freeze({ dimension: text(row.dimension, 64), path: Object.freeze(path), left: row.left, right: row.right })
  })
  return Object.freeze({ equivalent: value.equivalent, incomparable: Object.freeze(incomparable), differences: Object.freeze(differences) })
}

export function parseReview(input: unknown, projectId: string): ReviewTimeline {
  const value = object(input); keys(value, ['project_id', 'as_of', 'timeline', 'queues', 'operations', 'source_errors'])
  requireValue(value.project_id === projectId && Array.isArray(value.source_errors))
  const timeline = object(value.timeline); keys(timeline, ['events', 'next_cursor'])
  requireValue(Array.isArray(timeline.events) && timeline.events.length <= 100)
  const events = timeline.events.map((raw) => {
    const row = object(raw); keys(row, ['event_id', 'type', 'occurred_at', 'status', 'summary', 'references'])
    return Object.freeze({ event_id: text(row.event_id, 256), type: text(row.type, 64),
      occurred_at: row.occurred_at === null ? null : timestamp(row.occurred_at), status: text(row.status, 64), summary: text(row.summary, 512) })
  })
  return Object.freeze({ project_id: projectId, as_of: timestamp(value.as_of), events: Object.freeze(events),
    next_cursor: timeline.next_cursor === null ? null : text(timeline.next_cursor, 1024),
    source_errors: Object.freeze(value.source_errors.map((item) => text(item, 512))) })
}

export function parseEditorValidation(input: unknown): EditorValidation {
  const value = object(input); keys(value, ['schema', 'valid', 'base_revision', 'base_version', 'predicted_content_address', 'violations', 'nonauthority'])
  requireValue(value.schema === 'strategy-os-editor-validation/1' && typeof value.valid === 'boolean' && Array.isArray(value.violations)
    && value.violations.length <= 128 && value.nonauthority === 'VALIDATION_DOES_NOT_PUBLISH_OR_GRANT_AUTHORITY')
  const violations = value.violations.map((raw) => { const row = object(raw); keys(row, ['operation_index', 'clause', 'path', 'message']); requireValue(Array.isArray(row.path))
    return Object.freeze({ operation_index: row.operation_index === null ? null : integer(row.operation_index, 0), clause: row.clause === null ? null : text(row.clause, 128),
      path: Object.freeze(row.path.map((part) => { requireValue(typeof part === 'string' || Number.isSafeInteger(part)); return part as string | number })), message: text(row.message, 512) }) })
  const predicted = value.predicted_content_address === null ? null : address(value.predicted_content_address)
  requireValue(value.valid === (predicted !== null && violations.length === 0))
  return Object.freeze({ schema: value.schema, valid: value.valid, base_revision: integer(value.base_revision, 0), base_version: integer(value.base_version, 1),
    predicted_content_address: predicted, violations: Object.freeze(violations), nonauthority: value.nonauthority })
}

const datasetSourceFields = ['source_type', 'historical_source_availability', 'calendar_coverage', 'rights_scope', 'research_compatibility']
type DatasetSource = Required<Pick<ResearchDataset, 'source_type' | 'historical_source_availability' | 'calendar_coverage' | 'rights_scope' | 'research_compatibility'>>

function datasetChoice<T extends string>(value: unknown, choices: readonly T[]): T {
  requireValue(typeof value === 'string' && choices.includes(value as T))
  return value as T
}

function assertUserDatasetSource(row: Record<string, unknown>, source: DatasetSource) {
  requireValue(row.provider_evidence_state === 'USER_CSV_SHAPE_VALIDATED' && row.market_truth_state === 'RECONSTRUCTED_WITH_GAPS')
  requireValue(source.historical_source_availability === 'NOT_SUPPLIED' && source.calendar_coverage === 'NOT_ASSERTED' && source.rights_scope === 'PERSONAL_RESEARCH_ONLY')
}

function assertProviderDatasetSource(row: Record<string, unknown>, source: DatasetSource) {
  requireValue(row.provider_evidence_state === 'VERIFIED_REFERENCES_PRESENT' && source.rights_scope === 'PROVIDER_CONTRACT')
  const historical = source.historical_source_availability === 'NOT_SUPPLIED' && source.calendar_coverage === 'NOT_ASSERTED'
  requireValue(historical || (source.historical_source_availability === 'DECLARED' && source.calendar_coverage === 'DECLARED'
    && row.market_truth_state === 'VERIFIED_REFERENCES_PRESENT'))
}

function parseDatasetSource(row: Record<string, unknown>): Partial<ResearchDataset> {
  if (!datasetSourceFields.some((key) => key in row)) {
    requireValue(row.provider_evidence_state === 'VERIFIED_REFERENCES_PRESENT' && row.market_truth_state === 'VERIFIED_REFERENCES_PRESENT')
    return {}
  }
  const source_type = datasetChoice(row.source_type, ['PROVIDER_AUTHORITY', 'USER_SUPPLIED'] as const)
  const historical_source_availability = datasetChoice(row.historical_source_availability, ['DECLARED', 'NOT_SUPPLIED'] as const)
  const calendar_coverage = datasetChoice(row.calendar_coverage, ['DECLARED', 'NOT_ASSERTED'] as const)
  const rights_scope = datasetChoice(row.rights_scope, ['PROVIDER_CONTRACT', 'PERSONAL_RESEARCH_ONLY'] as const)
  const research_compatibility = datasetChoice(row.research_compatibility, ['PRIMARY_BACKTEST', 'BENCHMARK_INPUT_ONLY', 'UNAVAILABLE'] as const)
  const source = { source_type, historical_source_availability, calendar_coverage, rights_scope, research_compatibility }
  if (source_type === 'USER_SUPPLIED') assertUserDatasetSource(row, source)
  else assertProviderDatasetSource(row, source)
  return source
}

function parseResearchDataset(input: unknown): ResearchDataset {
  const row = object(input)
  keys(row, ['manifest_address', 'instrument_address', 'canonical_instrument_label', 'asset_class', 'contract_kind',
    'interval', 'event_start', 'event_end', 'availability_end', 'as_of', 'bar_count', 'fields', 'provider_evidence_state',
    'market_truth_state', 'gaps', 'backtest_eligibility', 'refusal_code'], [...datasetSourceFields, 'instrument_display_name', 'provider_selection_address'])
  requireValue(Array.isArray(row.fields) && Array.isArray(row.gaps))
  const provider_evidence_state = datasetChoice(row.provider_evidence_state, ['VERIFIED_REFERENCES_PRESENT', 'USER_CSV_SHAPE_VALIDATED'] as const)
  const market_truth_state = datasetChoice(row.market_truth_state, ['VERIFIED_REFERENCES_PRESENT', 'RECONSTRUCTED_WITH_GAPS'] as const)
  const backtest_eligibility = datasetChoice(row.backtest_eligibility, ['ELIGIBLE_Q03', 'UNAVAILABLE'] as const)
  const provider_selection_address = parseDatasetSelection(row)
  return Object.freeze({ ...parseDatasetSource(row), manifest_address: address(row.manifest_address), instrument_address: address(row.instrument_address),
    ...provider_selection_address,
    canonical_instrument_label: text(row.canonical_instrument_label, 256),
    ...(Object.hasOwn(row, 'instrument_display_name') ? { instrument_display_name: row.instrument_display_name === null ? null : text(row.instrument_display_name, 256) } : {}), asset_class: text(row.asset_class, 32), contract_kind: text(row.contract_kind, 32),
    interval: text(row.interval, 32), event_start: timestamp(row.event_start), event_end: timestamp(row.event_end), availability_end: timestamp(row.availability_end),
    as_of: timestamp(row.as_of), bar_count: integer(row.bar_count, 1), fields: Object.freeze(row.fields.map((item) => text(item, 64))),
    provider_evidence_state, market_truth_state, gaps: Object.freeze(row.gaps.map((item) => Object.freeze(object(item)))),
    backtest_eligibility, refusal_code: row.refusal_code === null ? null : text(row.refusal_code, 128) })
}

function parseDatasetSelection(row: Record<string, unknown>): Partial<ResearchDataset> {
  if (!Object.hasOwn(row, 'provider_selection_address')) return {}
  if (row.provider_selection_address === null) return { provider_selection_address: null }
  requireValue(row.source_type === 'PROVIDER_AUTHORITY')
  return { provider_selection_address: address(row.provider_selection_address) }
}

export function validHistoryDate(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || value.startsWith('0000')) return false
  const instant = Date.parse(`${value}T00:00:00Z`)
  return Number.isFinite(instant) && new Date(instant).toISOString().slice(0, 10) === value
}

export function assertProviderHistoryRequest(request: ProviderHistoryRequest): void {
  keys(object(request), ['selection_address', 'start_date', 'end_date', 'interval'])
  address(request.selection_address)
  requireValue(request.interval === 'day' && validHistoryDate(request.start_date)
    && validHistoryDate(request.end_date) && request.start_date <= request.end_date)
}

function providerHistoryRange(value: Record<string, unknown>, request: ProviderHistoryRequest, item: ResearchDataset) {
  const requested_start = timestamp(value.requested_start), requested_end = timestamp(value.requested_end)
  const returned_start = timestamp(value.returned_start), returned_end = timestamp(value.returned_end)
  requireValue(Date.parse(requested_start) === Date.parse(`${request.start_date}T00:00:00+05:30`)
    && Date.parse(requested_end) === Date.parse(`${request.end_date}T23:59:59+05:30`))
  requireValue(Date.parse(returned_start) >= Date.parse(requested_start) && Date.parse(returned_end) <= Date.parse(requested_end)
    && Date.parse(returned_start) <= Date.parse(returned_end))
  requireValue(Date.parse(item.event_start) === Date.parse(returned_start)
    && Date.parse(item.event_end) === Date.parse(returned_end) + 86400000)
  return { requested_start, requested_end, returned_start, returned_end }
}

export function parseProviderHistoryReceipt(input: unknown, projectId: string, request: ProviderHistoryRequest): ProviderHistoryReceipt {
  assertProviderHistoryRequest(request)
  const value = object(input)
  keys(value, ['schema', 'project_id', 'selection_address', 'requested_start', 'requested_end', 'returned_start', 'returned_end',
    'request_count', 'empty_request_count', 'request_window_days', 'application_bar_limit', 'provider_retention', 'reused', 'item'])
  requireValue(value.schema === 'strategy-os-provider-history-import/1' && value.project_id === projectId
    && value.selection_address === request.selection_address && value.provider_retention === 'UNKNOWN')
  requireValue(typeof value.reused === 'boolean')
  const item = parseResearchDataset(value.item)
  requireValue(item.provider_selection_address === request.selection_address && item.interval === 'day'
    && item.source_type === 'PROVIDER_AUTHORITY')
  const request_count = integer(value.request_count, 1), empty_request_count = integer(value.empty_request_count, 0)
  requireValue(request_count <= 64 && empty_request_count < request_count)
  requireValue(value.request_window_days === 1900 && value.application_bar_limit === 2000 && item.bar_count <= 2000)
  return Object.freeze({ schema: value.schema, project_id: projectId, selection_address: request.selection_address,
    ...providerHistoryRange(value, request, item), request_count, empty_request_count, request_window_days: 1900,
    application_bar_limit: 2000, provider_retention: 'UNKNOWN', reused: value.reused, item })
}

export function parseResearchDatasetPage(input: unknown, projectId: string, limit: number): ResearchDatasetPage {
  const value = object(input); keys(value, ['schema', 'project_id', 'items', 'next_cursor'])
  requireValue(value.schema === 'strategy-os-canonical-dataset-index/1' && value.project_id === projectId && Array.isArray(value.items) && value.items.length <= limit)
  const next_cursor = value.next_cursor === null ? null : address(value.next_cursor)
  return Object.freeze({ schema: value.schema, project_id: projectId, items: Object.freeze(value.items.map(parseResearchDataset)), next_cursor })
}

export function parseResearchVisualization(input: unknown): ResearchVisualization {
  const value = object(input); requireValue(value.schema === 'strategy-os-backtest-visualization/1')
  if (value.state === 'PENDING' || value.state === 'UNAVAILABLE') {
    requireValue(value.state !== 'UNAVAILABLE' || typeof value.reason_code === 'string')
    return Object.freeze({ schema: value.schema, state: value.state,
      ...(typeof value.reason_code === 'string' ? { reason_code: text(value.reason_code, 128) } : {}),
      ...(typeof value.status === 'string' ? { status: text(value.status, 64) } : {}) })
  }
  requireValue(value.state === 'AVAILABLE')
  keys(value, ['schema', 'state', 'identity', 'summary', 'series', 'trade_page', 'costs', 'folds', 'provenance', 'visualization_address'], ['run_id', 'spec_id'])
  const identity = object(value.identity); address(identity.terminal_evidence_address); address(value.visualization_address)
  const summary = object(value.summary); requireValue(Object.values(summary).every((item) => item === null || typeof item === 'boolean' || (typeof item === 'number' && Number.isFinite(item))))
  const series = object(value.series); keys(series, ['net_equity', 'drawdown', 'benchmark', 'trade_events'])
  const parsePoints = (raw: unknown, drawdown: boolean) => { const container = object(raw); keys(container, ['points', 'original_count']); requireValue(Array.isArray(container.points) && container.points.length <= 2000)
    const points = container.points.map((candidate) => { const point = object(candidate); keys(point, drawdown ? ['time', 'value', 'absolute'] : ['time', 'value'])
      return Object.freeze({ time: integer(point.time, 0), value: finiteNumber(point.value, -1e15, 1e15), ...(drawdown ? { absolute: finiteNumber(point.absolute, 0, 1e15) } : {}) }) })
    return Object.freeze({ points: Object.freeze(points), original_count: integer(container.original_count, points.length) }) }
  requireValue(Array.isArray(series.trade_events) && Array.isArray(value.folds))
  const tradePage = object(value.trade_page); keys(tradePage, ['items', 'next_cursor', 'total', 'detail_reason']); requireValue(Array.isArray(tradePage.items) && tradePage.items.length <= 100)
  const costs = object(value.costs); keys(costs, ['charges_total', 'breakdown', 'slippage'])
  return Object.freeze({ schema: value.schema, state: 'AVAILABLE', visualization_address: address(value.visualization_address), identity: Object.freeze(identity),
    summary: Object.freeze(summary) as AvailableVisualization['summary'], series: Object.freeze({ net_equity: parsePoints(series.net_equity, false), drawdown: parsePoints(series.drawdown, true),
      benchmark: Object.freeze(object(series.benchmark)), trade_events: Object.freeze(series.trade_events.map((item) => Object.freeze(object(item)))) }) as AvailableVisualization['series'],
    trade_page: Object.freeze({ items: Object.freeze(tradePage.items.map((item) => Object.freeze(object(item)))), next_cursor: tradePage.next_cursor === null ? null : integer(tradePage.next_cursor, 1),
      total: integer(tradePage.total, 0), detail_reason: tradePage.detail_reason === null ? null : text(tradePage.detail_reason, 128) }),
    costs: Object.freeze({ charges_total: finiteNumber(costs.charges_total, 0, 1e15), breakdown: Object.freeze(object(costs.breakdown)), slippage: Object.freeze(object(costs.slippage)) }),
    folds: Object.freeze(value.folds.map((item) => Object.freeze(object(item)))), provenance: Object.freeze(object(value.provenance)) })
}

export function parseMarketContext(input: unknown, after: number, limit: number): MarketContext {
  const value = object(input)
  keys(value, ['schema', 'state', 'market_context_address', 'source', 'graph',
    'dataset_manifest_address', 'canonical_instrument_address', 'instrument_label',
    'timeframe_seconds', 'source_as_of', 'replay_at', 'bars', 'projection_address', 'page'])
  requireValue(value.schema === 'strategy-os-market-context/1'
    && (value.state === 'AVAILABLE' || value.state === 'EMPTY') && Array.isArray(value.bars)
    && value.bars.length <= limit)
  const source = object(value.source); keys(source, ['kind', 'address'])
  requireValue(source.kind === 'VERIFIED_SAVED_RUN')
  const sourceAsOf = timestamp(value.source_as_of); const replayAt = timestamp(value.replay_at)
  requireValue(Date.parse(replayAt) <= Date.parse(sourceAsOf))
  let prior = after
  const bars = value.bars.map((raw) => {
    const row = object(raw); keys(row, ['cursor', 'event_time', 'completed_at', 'open', 'high', 'low', 'close', 'volume'])
    const cursor = integer(row.cursor, 1); requireValue(cursor > prior); prior = cursor
    const event_time = timestamp(row.event_time); const completed_at = timestamp(row.completed_at)
    requireValue(Date.parse(event_time) < Date.parse(completed_at) && Date.parse(completed_at) <= Date.parse(replayAt))
    const open = finiteNumber(row.open, 0, 1e15); const high = finiteNumber(row.high, 0, 1e15)
    const low = finiteNumber(row.low, 0, 1e15); const close = finiteNumber(row.close, 0, 1e15)
    const volume = finiteNumber(row.volume, 0, 1e18)
    requireValue(low <= Math.min(open, close) && Math.max(open, close) <= high)
    return Object.freeze({ cursor, event_time, completed_at, open, high, low, close, volume })
  })
  const page = object(value.page); keys(page, ['after', 'limit', 'next_cursor', 'visible_count'])
  requireValue(page.after === after && page.limit === limit)
  const visible_count = integer(page.visible_count, bars.length)
  const next_cursor = page.next_cursor === null ? null : integer(page.next_cursor, 1)
  requireValue(next_cursor === null || (bars.length === limit && next_cursor === bars.at(-1)?.cursor))
  return Object.freeze({ schema: value.schema, state: value.state,
    market_context_address: address(value.market_context_address), projection_address: address(value.projection_address),
    source: Object.freeze({ kind: source.kind, address: address(source.address) }), graph: Object.freeze(object(value.graph)),
    dataset_manifest_address: address(value.dataset_manifest_address),
    canonical_instrument_address: address(value.canonical_instrument_address),
    instrument_label: text(value.instrument_label, 256), timeframe_seconds: integer(value.timeframe_seconds, 1),
    source_as_of: sourceAsOf, replay_at: replayAt, bars: Object.freeze(bars),
    page: Object.freeze({ after, limit, next_cursor, visible_count }) })
}

function parseAnnotation(input: unknown): ChartAnnotation {
  const value = object(input)
  keys(value, ['annotation_id', 'revision', 'geometry', 'geometry_address', 'applicability',
    'applicability_address', 'created_at', 'updated_at'])
  const annotation_id = text(value.annotation_id, 36)
  requireValue(/^[0-9a-f-]{36}$/.test(annotation_id))
  return Object.freeze({ annotation_id, revision: integer(value.revision, 1),
    geometry: Object.freeze(object(value.geometry)), geometry_address: address(value.geometry_address),
    applicability: Object.freeze(object(value.applicability)), applicability_address: address(value.applicability_address),
    created_at: timestamp(value.created_at), updated_at: timestamp(value.updated_at) })
}

export function parseChartAnnotationPage(input: unknown, contextAddress: string, limit: number): ChartAnnotationPage {
  const value = object(input); keys(value, ['schema', 'market_context_address', 'items', 'next_cursor'])
  requireValue(value.schema === 'strategy-os-chart-annotation-presentation/1'
    && value.market_context_address === contextAddress && Array.isArray(value.items) && value.items.length <= limit)
  const items = value.items.map(parseAnnotation)
  const next_cursor = value.next_cursor === null ? null : text(value.next_cursor, 36)
  requireValue(next_cursor === null || (items.length === limit && next_cursor === items.at(-1)?.annotation_id))
  return Object.freeze({ schema: value.schema, market_context_address: contextAddress,
    items: Object.freeze(items), next_cursor })
}

export function parseChartAnnotation(input: unknown): ChartAnnotation { return parseAnnotation(input) }

function v2Port(input: unknown): V2Port {
  const row = object(input)
  const required = ['port_id', 'direction', 'semantic_flow', 'semantic_role', 'type_ref', 'shape']
  for (const key of required) requireValue(Object.hasOwn(row, key))
  requireValue(row.direction === 'input' || row.direction === 'output')
  return Object.freeze({ port_id: text(row.port_id, 128), direction: row.direction,
    semantic_flow: text(row.semantic_flow, 128), semantic_role: text(row.semantic_role, 128),
    type_ref: Object.freeze(object(row.type_ref)), shape: row.shape,
    ...(Object.hasOwn(row, 'connections') ? { connections: Object.freeze(object(row.connections)) } : {}),
    ...(Object.hasOwn(row, 'default') ? { default: row.default } : {}) })
}

export function v2Document(input: unknown, graphId: string): V2Document {
  const value = object(input)
  keys(value, ['format_version', 'strategy_id', 'strategy_version', 'metadata', 'graph_inputs', 'graph_outputs', 'nodes', 'edges'])
  requireValue(value.format_version === 2 && value.strategy_id === graphId && Array.isArray(value.graph_inputs)
    && Array.isArray(value.graph_outputs) && Array.isArray(value.nodes) && Array.isArray(value.edges))
  const metadata = object(value.metadata); keys(metadata, ['metadata_version', 'name', 'description', 'tags']); requireValue(Array.isArray(metadata.tags))
  const nodes = value.nodes.map((raw) => { const row = object(raw); keys(row, ['node_id', 'component', 'parameters']); const component = object(row.component)
    keys(component, ['component_id', 'component_version']); return Object.freeze({ node_id: text(row.node_id, 128), component: Object.freeze({
      component_id: text(component.component_id, 128), component_version: integer(component.component_version, 1) }), parameters: Object.freeze(object(row.parameters)) }) })
  const edges = value.edges.map((raw) => { const row = object(raw); keys(row, ['edge_id', 'source', 'target', 'binding'])
    return Object.freeze({ edge_id: text(row.edge_id, 256), source: Object.freeze(object(row.source)), target: Object.freeze(object(row.target)), binding: Object.freeze(object(row.binding)) }) })
  return Object.freeze({ format_version: 2, strategy_id: graphId, strategy_version: integer(value.strategy_version, 1),
    metadata: Object.freeze({ metadata_version: integer(metadata.metadata_version, 1), name: text(metadata.name, 128), description: metadata.description === null ? null : text(metadata.description, 4000, true),
      tags: Object.freeze(metadata.tags.map((item) => text(item, 128))) }), graph_inputs: Object.freeze(value.graph_inputs.map(v2Port)),
    graph_outputs: Object.freeze(value.graph_outputs.map(v2Port)), nodes: Object.freeze(nodes), edges: Object.freeze(edges) })
}

export function parseV2Draft(input: unknown, projectId: string, graphId: string): V2Draft {
  const value = object(input); keys(value, ['project_id', 'graph_identifier', 'semantic_revision', 'current_version', 'published_revision', 'document', 'content_address', 'graph_address'])
  requireValue(value.project_id === projectId && value.graph_identifier === graphId)
  return Object.freeze({ project_id: projectId, graph_identifier: graphId, semantic_revision: integer(value.semantic_revision, 0),
    current_version: value.current_version === null ? null : integer(value.current_version, 1),
    published_revision: value.published_revision === null ? null : integer(value.published_revision, 0),
    document: v2Document(value.document, graphId), content_address: address(value.content_address), graph_address: address(value.graph_address) })
}

export function parseV2SemanticReceipt(input: unknown): V2SemanticReceipt {
  const value = object(input); requireValue(value.schema === 'strategy-os-v2-semantic-receipt/2'
    && (value.commit_state === 'DRAFT_COMMITTED' || value.commit_state === 'DRY_RUN_ROLLED_BACK')
    && ['EDIT', 'UNDO', 'REDO', 'REPLAY'].includes(String(value.intent)) && Array.isArray(value.forward_commands) && Array.isArray(value.inverse_commands))
  ;['base_content_address', 'result_content_address', 'base_graph_address', 'result_graph_address', 'receipt_address'].forEach((key) => address(value[key]))
  return Object.freeze({ ...value, schema: value.schema, commit_state: value.commit_state, intent: value.intent,
    base_semantic_revision: integer(value.base_semantic_revision, 0), result_semantic_revision: integer(value.result_semantic_revision, 0),
    base_content_address: address(value.base_content_address), result_content_address: address(value.result_content_address),
    base_graph_address: address(value.base_graph_address), result_graph_address: address(value.result_graph_address),
    forward_commands: Object.freeze(value.forward_commands.map((item) => Object.freeze(object(item)))),
    inverse_commands: Object.freeze(value.inverse_commands.map((item) => Object.freeze(object(item)))), receipt_address: address(value.receipt_address) }) as V2SemanticReceipt
}

export function parseV2PublishReceipt(input: unknown, projectId: string, graphId: string): V2PublishReceipt {
  const value = object(input); requireValue(value.schema === 'strategy-os-v2-publish-receipt/1' && value.project_id === projectId && value.graph_identifier === graphId)
  return Object.freeze({ ...value, schema: value.schema, project_id: projectId, graph_identifier: graphId,
    graph_version: integer(value.graph_version, 1), semantic_revision: integer(value.semantic_revision, 0), content_address: address(value.content_address),
    graph_address: address(value.graph_address), canonical_document: v2Document(value.canonical_document, graphId), receipt_address: address(value.receipt_address) }) as V2PublishReceipt
}

export function parseV2Presentation(input: unknown): V2Presentation {
  const value = object(input); keys(value, ['schema', 'format_version', 'semantic_revision', 'presentation_revision', 'presentation', 'presentation_address', 'orphaned_references', 'executable_identity'])
  requireValue(value.schema === 'strategy-os-v2-presentation-state/1' && value.format_version === 2 && value.executable_identity === false)
  const presentation = object(value.presentation); keys(presentation, ['schema', 'positions', 'groups', 'viewport', 'selection']); requireValue(presentation.schema === 'strategy-os-v2-presentation/1')
  const positions = object(presentation.positions); const parsedPositions: Record<string, Readonly<{ x: number; y: number }>> = {}
  for (const [id, raw] of Object.entries(positions)) { const point = object(raw); keys(point, ['x', 'y']); parsedPositions[text(id, 128)] = Object.freeze({ x: finiteNumber(point.x, -1e9, 1e9), y: finiteNumber(point.y, -1e9, 1e9) }) }
  const selection = object(presentation.selection); requireValue(Object.values(selection).every(Array.isArray))
  return Object.freeze({ schema: value.schema, semantic_revision: integer(value.semantic_revision, 0), presentation_revision: integer(value.presentation_revision, 0),
    presentation: Object.freeze({ positions: Object.freeze(parsedPositions), groups: Object.freeze(object(presentation.groups)), viewport: presentation.viewport === null ? null : Object.freeze(object(presentation.viewport)) as V2Presentation['presentation']['viewport'],
      selection: Object.freeze(selection) as V2Presentation['presentation']['selection'] }), presentation_address: address(value.presentation_address),
    orphaned_references: Object.freeze(object(value.orphaned_references)) as V2Presentation['orphaned_references'], executable_identity: false })
}

export function parseV2PresentationReceipt(input: unknown): V2PresentationReceipt {
  const value = object(input); requireValue(value.schema === 'strategy-os-v2-presentation-receipt/1' && value.commit_state === 'PRESENTATION_COMMITTED'
    && ['EDIT', 'UNDO', 'REDO', 'REPLAY'].includes(String(value.intent)) && Array.isArray(value.forward_commands) && Array.isArray(value.inverse_commands))
  return Object.freeze({ ...value, schema: value.schema, commit_state: value.commit_state, intent: value.intent,
    base_presentation_revision: integer(value.base_presentation_revision, 0), result_presentation_revision: integer(value.result_presentation_revision, 0),
    forward_commands: Object.freeze(value.forward_commands.map((item) => Object.freeze(object(item)))), inverse_commands: Object.freeze(value.inverse_commands.map((item) => Object.freeze(object(item)))),
    receipt_address: address(value.receipt_address) }) as V2PresentationReceipt
}

export type OptimizationAxis = Readonly<{ node_id: string; parameter_id: string; step: string; minimum: string; maximum: string }>
export type CanonicalOptimizationSettings = Readonly<{ schema: 'canonical-local-development-search/1'; enabled: boolean; axes: readonly OptimizationAxis[] }>
export function disabledOptimization(): CanonicalOptimizationSettings {
  return Object.freeze({ schema: 'canonical-local-development-search/1', enabled: false, axes: Object.freeze([]) })
}
export function normalizedOptimizationDecimal(input: unknown): string {
  requireValue(typeof input === 'string' && input.length <= 128 && /^-?(?:0|[1-9]\d*)(?:\.\d*[1-9])?$/.test(input) && input !== '-0')
  return input as string
}
function optimizationAxis(input: unknown): OptimizationAxis {
  const value = object(input); keys(value, ['node_id', 'parameter_id', 'step', 'minimum', 'maximum'])
  return Object.freeze({ node_id: text(value.node_id, 128), parameter_id: text(value.parameter_id, 128),
    step: normalizedOptimizationDecimal(value.step), minimum: normalizedOptimizationDecimal(value.minimum), maximum: normalizedOptimizationDecimal(value.maximum) })
}
function compareCodepoints(left: string, right: string) {
  const a = Array.from(left, (character) => character.codePointAt(0)!), b = Array.from(right, (character) => character.codePointAt(0)!)
  for (let index = 0; index < Math.min(a.length, b.length); index += 1) {
    if (a[index] !== b[index]) return a[index] - b[index]
  }
  return a.length - b.length
}
export function compareOptimizationAxes(left: Pick<OptimizationAxis, 'node_id' | 'parameter_id'>, right: Pick<OptimizationAxis, 'node_id' | 'parameter_id'>) {
  return compareCodepoints(left.node_id, right.node_id) || compareCodepoints(left.parameter_id, right.parameter_id)
}
export function parseOptimizationSettings(input: unknown): CanonicalOptimizationSettings {
  const value = object(input); keys(value, ['schema', 'enabled', 'axes'])
  requireValue(value.schema === 'canonical-local-development-search/1' && typeof value.enabled === 'boolean' && Array.isArray(value.axes))
  const raw = value.axes as unknown[]
  requireValue(value.enabled ? raw.length >= 1 && raw.length <= 4 : raw.length === 0)
  const axes = raw.map(optimizationAxis)
  requireValue(axes.every((axis, index) => index === 0 || compareOptimizationAxes(axes[index - 1], axis) < 0))
  return Object.freeze({ schema: value.schema as CanonicalOptimizationSettings['schema'], enabled: value.enabled as boolean, axes: Object.freeze(axes) })
}

export type ResearchValues = Readonly<{
  research_capital: number; seed: number; min_trades: number; n_folds: number
  stop_loss_pct?: number; take_profit_pct?: number; optimization?: CanonicalOptimizationSettings
  min_positive_fold_frac: number; risk_policy: 'none' | 'pine-v4-ratchet/1' | 'pine-v4-reversal/1'
}>
export type ResearchSettingsRevision = Readonly<{
  supportedValuesSchema?: "research-values/2" | "research-values/3"
  schema?: "research-settings-revision/1" | "research-settings-revision/2" | "research-settings-revision/3"
  owner_id: string; graph_identifier: string | null; revision: number; enabled: boolean
  values: Partial<ResearchValues>; content_address: string
}>
const researchValueKeys = ['research_capital', 'seed', 'min_trades', 'n_folds', 'min_positive_fold_frac', 'risk_policy']
function researchNumber(item: unknown, bound: readonly [number, number, boolean]) {
  const [min, max, whole] = bound
  requireValue(typeof item === 'number' && Number.isFinite(item) && item >= min && item <= max)
  requireValue(!whole || Number.isInteger(item))
}
function researchRevisionIdentity(value: Record<string, unknown>, revision: number) {
  requireValue(revision <= 2_147_483_647 && value.expected_revision === Math.max(0, revision - 1))
  requireValue(revision === 0 ? value.request_id === null : typeof value.request_id === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(value.request_id))
}
export function assertResearchSettingsSave(saved: ResearchSettingsRevision, expectedRevision: number, values: Partial<ResearchValues>, enabled: boolean) {
  requireValue(saved.revision === expectedRevision + 1 && saved.enabled === enabled)
  const submitted = saved.graph_identifier === null ? { ...researchValueDefaults(saved.schema === "research-settings-revision/3" ? 3 : saved.schema === "research-settings-revision/2" ? 2 : 1), ...values } : values
  requireValue(Object.keys(saved.values).length === Object.keys(submitted).length)
  requireValue(Object.entries(submitted).every(([key, expected]) => sameJson(saved.values[key as keyof ResearchValues], expected)))
}
function researchField(key: string, item: unknown, bounds: Record<string, readonly [number, number, boolean]>) {
  if (key === 'risk_policy') { requireValue(item === 'none' || item === 'pine-v4-ratchet/1' || item === 'pine-v4-reversal/1'); return }
  if (key === 'stop_loss_pct' || key === 'take_profit_pct') { researchNumber(item, [0, 1, false]); requireValue((item as number) < 1); return }
  researchNumber(item, bounds[key])
}
function researchValueDefaults(version: number): Partial<ResearchValues> {
  if (version === 1) return {}
  return { stop_loss_pct: 0, take_profit_pct: 0, ...(version === 3 ? { optimization: disabledOptimization() } : {}) }
}
function researchValues(input: unknown, sparse: boolean, version = 1): Partial<ResearchValues> {
  const value = object(input)
  const names = [...researchValueKeys, ...Object.keys(researchValueDefaults(version))]
  keys(value, sparse ? [] : names, sparse ? names : [])
  const bounds: Record<string, readonly [number, number, boolean]> = {
    research_capital: [Number.MIN_VALUE, 1_000_000_000, false], seed: [0, 2_147_483_647, true],
    min_trades: [1, 100_000, true], n_folds: [2, 32, true], min_positive_fold_frac: [0, 1, false],
  }
  for (const [key, item] of Object.entries(value)) { if (key !== "optimization") researchField(key, item, bounds) }
  const optimization = Object.hasOwn(value, "optimization") ? { optimization: parseOptimizationSettings(value.optimization) } : {}

  return Object.freeze({ ...value, ...optimization }) as Partial<ResearchValues>
}
export function parseResearchSettingsRevision(input: unknown, graphId: string | null): ResearchSettingsRevision {
  const value = object(input)
  keys(value, ['schema', 'owner_id', 'graph_identifier', 'revision', 'expected_revision', 'request_id', 'enabled', 'values', 'content_address'])
  const version = ['research-settings-revision/1', 'research-settings-revision/2', 'research-settings-revision/3'].indexOf(String(value.schema)) + 1
  requireValue(version > 0 && value.graph_identifier === graphId)
  const revision = integer(value.revision, 0)
  researchRevisionIdentity(value, revision)
  requireValue(typeof value.enabled === 'boolean' && (graphId !== null || value.enabled))
  const values = researchValues(value.values, graphId !== null, version)
  requireValue(graphId !== null || !values.optimization?.enabled)
  requireValue(revision !== 0 || (value.enabled && (graphId === null || Object.keys(values).length === 0)))
  return Object.freeze({ schema: value.schema as ResearchSettingsRevision['schema'], owner_id: text(value.owner_id, 128), graph_identifier: graphId, revision,
    enabled: value.enabled, values, content_address: address(value.content_address) })
}
export function parseWorkspaceResearchSettings(input: unknown) {
  const value = object(input); keys(value, ['workspace', 'fixed_assumptions'], ['supported_values_schema'])
  requireValue(value.supported_values_schema === undefined || value.supported_values_schema === 'research-values/2' || value.supported_values_schema === 'research-values/3')
  const revision = parseResearchSettingsRevision(value.workspace, null)
  return value.supported_values_schema === undefined ? revision : Object.freeze({ ...revision, supportedValuesSchema: value.supported_values_schema as ResearchSettingsRevision['supportedValuesSchema'] })
}
export function parseStrategyResearchSettings(input: unknown, graphId: string) {
  const value = object(input); keys(value, ['workspace', 'strategy', 'values', 'sources', 'fixed_assumptions'])
  const workspace = parseResearchSettingsRevision(value.workspace, null)
  const strategy = parseResearchSettingsRevision(value.strategy, graphId)
  requireValue(workspace.owner_id === strategy.owner_id)
  const preview = object(value.values)
  const version = Object.hasOwn(preview, "optimization") ? 3 : Object.hasOwn(preview, "stop_loss_pct") ? 2 : 1
  const values = researchValues(value.values, false, version) as ResearchValues
  const overrides = strategy.enabled ? strategy.values : {}
  const effective = { ...researchValueDefaults(version), ...workspace.values, ...overrides }, sources = object(value.sources)
  const names = Object.keys(values)
  keys(sources, names)
  for (const key of names) {
    requireValue(sameJson(values[key as keyof ResearchValues], effective[key as keyof ResearchValues]))
    requireValue(sources[key] === (Object.hasOwn(overrides, key) ? 'strategy' : 'workspace'))
  }
  return Object.freeze({ workspace, strategy, values, sources: Object.freeze({ ...sources }) })
}


function optimizationCoordinates(input: unknown): Readonly<Record<string, string>> {
  const value = object(input), names = Object.keys(value).sort()
  requireValue(names.length >= 1 && names.length <= 4)
  requireValue(names.every((name, index) => name === `axis_${String(index).padStart(3, '0')}`))
  return Object.freeze(Object.fromEntries(names.map((name) => [name, normalizedOptimizationDecimal(value[name])])))
}
function optimizationParameters(input: unknown, coordinates: Readonly<Record<string, string>>): readonly OptimizationParameter[] {
  requireValue(Array.isArray(input) && input.length === Object.keys(coordinates).length)
  const rows = (input as unknown[]).map((raw, index) => {
    const row = object(raw); keys(row, ['node_id', 'parameter_id', 'value', 'normalized_value'])
    const normalized = normalizedOptimizationDecimal(row.normalized_value), value = finiteNumber(row.value, -Number.MAX_VALUE, Number.MAX_VALUE)
    requireValue(normalized === coordinates[`axis_${String(index).padStart(3, '0')}`] && Number(normalized) === value)
    return Object.freeze({ node_id: text(row.node_id, 128), parameter_id: text(row.parameter_id, 128), value, normalized_value: normalized })
  })
  requireValue(rows.every((row, index) => index === 0 || compareOptimizationAxes(rows[index - 1], row) < 0))
  return Object.freeze(rows)
}
function optimizationLineage(input: unknown, contentAddress: string, graphAddress: string) {
  const value = object(input)
  requireValue(value.content_address === contentAddress && value.graph_address === graphAddress)
  return Object.freeze({ ...value })
}
function optimizationCandidate(input: unknown): OptimizationCandidate {
  const value = object(input); keys(value, ['coordinates', 'parameters', 'content_address', 'graph_address', 'state'], ['lineage', 'reason_code'])
  const coordinates = optimizationCoordinates(value.coordinates), contentAddress = address(value.content_address), graphAddress = address(value.graph_address)
  requireValue(['pending', 'running', 'evaluated', 'failed', 'cancelled'].includes(String(value.state)))
  const lineage = Object.hasOwn(value, 'lineage') ? optimizationLineage(value.lineage, contentAddress, graphAddress) : undefined
  requireValue(value.state !== 'evaluated' || lineage !== undefined)
  return Object.freeze({ coordinates, parameters: optimizationParameters(value.parameters, coordinates), content_address: contentAddress, graph_address: graphAddress,
    state: value.state as OptimizationCandidate['state'], ...(lineage ? { lineage } : {}), ...(value.reason_code === undefined ? {} : { reason_code: text(value.reason_code, 128) }) })
}
function optimizationTrial(input: unknown, candidate: OptimizationCandidate, fold: number): OptimizationTrial {
  const value = object(input); keys(value, ['params', 'fold_index', 'objective', 'trades', 'is_sharpe', 'selected'])
  const params = object(value.params); keys(params, [...Object.keys(candidate.coordinates), 'candidate_graph_address'])
  requireValue(sameJson(params, { ...candidate.coordinates, candidate_graph_address: candidate.graph_address }) && value.fold_index === fold && typeof value.selected === 'boolean')
  return Object.freeze({ params: Object.freeze({ ...params }) as Readonly<Record<string, string>>, fold_index: fold,
    objective: value.objective === null ? null : finiteNumber(value.objective, -Number.MAX_VALUE, Number.MAX_VALUE), trades: integer(value.trades, 0),
    is_sharpe: value.is_sharpe === null ? null : finiteNumber(value.is_sharpe, -Number.MAX_VALUE, Number.MAX_VALUE), selected: value.selected as boolean })
}
function optimizationTrials(input: unknown, candidates: readonly OptimizationCandidate[], final: boolean) {
  requireValue(Array.isArray(input) && input.length <= candidates.length * (final ? 1 : 32))
  return Object.freeze((input as unknown[]).map((row, index) => optimizationTrial(row, candidates[index % candidates.length], final ? -1 : Math.floor(index / candidates.length))))
}
function optimizationSelection(input: unknown, graphId: string, candidates: readonly OptimizationCandidate[]): OptimizationSelection {
  const value = object(input); keys(value, ['coordinates', 'parameters', 'canonical_document', 'content_address', 'graph_address', 'lineage'])
  const contentAddress = address(value.content_address), graphAddress = address(value.graph_address)
  const candidate = candidates.find((row) => row.graph_address === graphAddress)
  requireValue(candidate !== undefined && candidate.content_address === contentAddress && sameJson(candidate.coordinates, value.coordinates) && sameJson(candidate.parameters, value.parameters))
  const document = v2Document(value.canonical_document, graphId)
  for (const parameter of candidate!.parameters) {
    const node = document.nodes.find((row) => row.node_id === parameter.node_id)
    requireValue(node !== undefined && Object.hasOwn(node.parameters, parameter.parameter_id) && sameJson(node.parameters[parameter.parameter_id], parameter.value))
  }
  return Object.freeze({ coordinates: candidate!.coordinates, parameters: candidate!.parameters, canonical_document: document, content_address: contentAddress, graph_address: graphAddress,
    lineage: optimizationLineage(value.lineage, contentAddress, graphAddress) })
}
function optimizationPartition(input: unknown): OptimizationPartition | null {
  if (input === null) return null
  const value = object(input); keys(value, ['development_bars', 'development_end_ts', 'validation_bars', 'validation_start_ts', 'validation_end_ts'])
  const instant = (item: unknown) => item === null ? null : finiteNumber(item, -8_640_000_000_000, 8_640_000_000_000)
  const development = integer(value.development_bars, 0), validation = integer(value.validation_bars, 0)
  const end = instant(value.development_end_ts), start = instant(value.validation_start_ts), last = instant(value.validation_end_ts)
  requireValue((development === 0) === (end === null) && (validation === 0) === (start === null) && (validation === 0) === (last === null))
  requireValue(start === null || (end !== null && end < start && last !== null && start <= last))
  return Object.freeze({ development_bars: development, development_end_ts: end, validation_bars: validation, validation_start_ts: start, validation_end_ts: last })
}
function optimizationMatrix(input: unknown, count: number) {
  requireValue(Array.isArray(input) && (input.length === 0 || input.length === 8))
  return Object.freeze((input as unknown[]).map((row) => {
    requireValue(Array.isArray(row) && row.length === count)
    return Object.freeze((row as unknown[]).map((value) => finiteNumber(value, -Number.MAX_VALUE, Number.MAX_VALUE)))
  }))
}
function requireSelectedSearch(value: CanonicalOptimizationEvidence) {
  if (value.state !== 'selected') { requireValue(value.selected === null); return }
  const count = value.candidates.length, folds = value.n_trials / count
  requireValue(value.selected !== null && value.partition !== null && Number.isInteger(folds) && folds >= 2 && folds <= 32)
  requireValue(value.candidates.every((row) => row.state === 'evaluated') && value.nested_trials.length === value.n_trials && value.final_development_trials.length === count)
  requireSelectedTrials(value, count, folds)
}
function requireSelectedTrials(value: CanonicalOptimizationEvidence, count: number, folds: number) {
  const final = value.final_development_trials.filter((row) => row.selected)
  requireValue(final.length === 1 && final[0].params.candidate_graph_address === value.selected!.graph_address)
  for (let fold = 0; fold < folds; fold++) requireValue(value.nested_trials.slice(fold * count, (fold + 1) * count).filter((row) => row.selected).length === 1)
}

function requireOptimizationPopulation(candidates: readonly OptimizationCandidate[]) {
  requireValue(new Set(candidates.map((row) => row.graph_address)).size === candidates.length)
  const identities = (row: OptimizationCandidate) => row.parameters.map(({ node_id, parameter_id }) => [node_id, parameter_id])
  for (const row of candidates) requireValue(sameJson(Object.keys(row.coordinates), Object.keys(candidates[0].coordinates)) && sameJson(identities(row), identities(candidates[0])))
}
export function parseCanonicalOptimizationEvidence(input: unknown, graphId: string): CanonicalOptimizationEvidence {
  const value = object(input); keys(value, ['schema', 'state', 'recipe_address', 'candidates', 'nested_trials', 'final_development_trials', 'selected', 'partition', 'performance_matrix', 'n_trials', 'var_sr'], ['reason_code'])
  requireValue(value.schema === 'canonical-development-search-evidence/1' && ['pending', 'running', 'failed', 'cancelled', 'refused', 'not_qualified', 'selected'].includes(String(value.state)))
  requireValue(Array.isArray(value.candidates) && value.candidates.length >= 2 && value.candidates.length <= 81)
  const candidates = (value.candidates as unknown[]).map(optimizationCandidate)
  requireOptimizationPopulation(candidates)
  const result: CanonicalOptimizationEvidence = Object.freeze({ schema: 'canonical-development-search-evidence/1', state: value.state as CanonicalOptimizationEvidence['state'], recipe_address: address(value.recipe_address), candidates: Object.freeze(candidates),
    nested_trials: optimizationTrials(value.nested_trials, candidates, false), final_development_trials: optimizationTrials(value.final_development_trials, candidates, true),
    selected: value.selected === null ? null : optimizationSelection(value.selected, graphId, candidates), partition: optimizationPartition(value.partition),
    performance_matrix: optimizationMatrix(value.performance_matrix, candidates.length), n_trials: integer(value.n_trials, 0), var_sr: finiteNumber(value.var_sr, 0, Number.MAX_VALUE),
    ...(value.reason_code === undefined ? {} : { reason_code: text(value.reason_code, 128) }) })
  requireSelectedSearch(result)
  return result
}
function optimizationResearchGates(input: unknown): readonly OptimizationResearchGates[] {
  requireValue(Array.isArray(input) && input.length <= 1)
  return Object.freeze((input as unknown[]).map((raw) => {
    const item = object(raw), validation = item.validation
    if (validation === null) return Object.freeze({ instrument: text(item.instrument, 256), passed: null, gates: Object.freeze({}) })
    const value = object(validation); keys(value, ['passed', 'gates', 'params']); requireValue(typeof value.passed === 'boolean')
    const gates = object(value.gates); requireValue(Object.keys(gates).length <= 32)
    const rows = Object.fromEntries(Object.entries(gates).map(([name, rawGate]) => {
      const gate = object(rawGate); keys(gate, ['passed', 'value']); requireValue(typeof gate.passed === 'boolean')
      const observed = typeof gate.value === 'number' ? finiteNumber(gate.value, -Number.MAX_VALUE, Number.MAX_VALUE) : text(gate.value, 512, true)
      return [text(name, 128), Object.freeze({ passed: gate.passed, value: observed })]
    }))
    return Object.freeze({ instrument: text(item.instrument, 256), passed: value.passed as boolean, gates: Object.freeze(rows) })
  }))
}
