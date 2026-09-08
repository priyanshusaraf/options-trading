import { expect, it } from 'vitest'
import release from '../test/releaseManifest.json'
import { ContractError, parseCatalogue, parseManifest, parseMarketContext,
  parseV2Draft, parseResearchDatasetPage, providerOnboardingEnabled, parseExperimentDetail, parseExperimentPage,
  assertProviderHistoryRequest, parseProviderHistoryReceipt, validHistoryDate } from './contracts'

const address = (index: number) => `sha256:${index.toString(16).padStart(64, '0')}`
const kinds = [
  ...Array(167).fill('MATHEMATICAL_FORMULA'),
  ...Array(26).fill('FIELD_SELECTION'),
  'FIELD_SPLITTER',
  ...Array(37).fill('LOGICAL_OPERATION'),
  ...Array(12).fill('INTENT_BEHAVIOR'),
] as string[]
const families = [
  ['TYPE_4', 'Price, Instrument & Market Data', 5],
  ['TYPE_2', 'Indicators & Derived Features', 103],
  ['TYPE_3', 'Market Structure, Derivatives & Cross-Instrument', 63],
  ['TYPE_5', 'Logic, Math & State', 60],
  ['TYPE_1', 'Execution & Position', 12],
] as const

function parameter(name: string) {
  return { name, type: 'int', required: false, default: 14, enum: null, domain: { minimum: 1, maximum: 4096 }, units: 'bars', serialization: 'canonical-json' }
}
function fixture() {
  let cursor = 0
  const groups = families.map(([visible_family, display_name, count], groupIndex) => ({ order: groupIndex + 1, visible_family, display_name,
    components: Array.from({ length: count }, () => {
      const index = cursor++; const isOhlcv = kinds[index] === 'FIELD_SPLITTER'; const component_id = isOhlcv ? 'analytical.ohlcv' : `fixture.component_${index}`
      const parameters = index < 161 ? { window: { type: 'int', required: false, default: 14, enum: null, domain: { minimum: 1, maximum: 4096 }, units: 'bars', serialization: 'canonical-json' } } : {}
      const status = index % 2 ? 'AVAILABLE' : 'CONDITIONAL'; const authority = visible_family === 'TYPE_1' ? 'MONITORING_ONLY' : 'NONE'
      return { component_id, component_version: 2, component_address: address(1000 + index), display_name: isOhlcv ? 'OHLCV' : `Component ${index}`,
        visible_family, presentation_group_order: groupIndex + 1, presentation_group_name: display_name, domain_family: 'fixture', structural_role: 'transform',
        descriptor: { component_id, component_version: 2, ports: [], parameters }, node_contract: {}, node_contract_address: address(2000 + index), implementation_address: address(3000 + index),
        contract_binding: null, contract_binding_address: null, data_requirement: {}, data_requirement_address: address(4000 + index), mode_eligibility: {}, provider_requirements: [], resource_profile: {},
        availability: { status, authority, provider_support_verified: false, data_rights_verified: false, backtest_eligible: false },
        help: { component_id, component_version: 2, implementation_binding: address(3000 + index), semantic_kind: kinds[index],
          description: isOhlcv ? 'Splits each fully completed candle into five named outputs: open, high, low, close and volume. It does not calculate an indicator.' : 'Returns the reviewed result when required inputs are valid.',
          semantic_text: isOhlcv ? 'Return separately named canonical completed-bar open, high, low, close and volume series. No DataFrame hidden under a scalar value port.' : 'Return the exact reviewed result.',
          sources: [{ source_record_id: 'strategy-os-fixture', title: 'Strategy OS semantics', authors_or_organization: 'Strategy OS', publication_or_version: 'Version 1', year: 2026, url: null, claim_scope: `Defines ${component_id}.` }],
          customisation: { parameters: index < 161 ? [parameter('window')] : [], guidance: index < 161 ? 'Set only this authored parameter: window.' : 'This built-in has no parameters.', built_in_code_immutable: true, immutable_boundary: 'This is an immutable built-in. You can change only the listed parameters; you cannot edit its code here.' },
          availability: { status, authority, condition: status === 'CONDITIONAL' ? 'Conditional on declared data.' : 'Available in research.' } } }
    }) }))
  const exclusions = Array.from({ length: 78 }, (_, index) => ({ kind: index < 17 ? 'ANALYTICAL_V2_UNAVAILABLE' : 'LEGACY_TYPE_1_EXCLUDED', component_id: `excluded.${index}`, component_version: index < 17 ? 2 : 1, visible_family: index < 17 ? 'TYPE_2' : 'TYPE_1', reason_code: 'TYPED_UNAVAILABLE', executable: false, authority: 'NONE' }))
  return { schema: 'strategy-os-verified-language-catalogue/1', registry_identity: address(1), groups, exclusions,
    counts: { groups: 5, components: 243, analytical_v2: 108, type_3: 63, type_5: 60, monitoring_type_1_v2: 12, analytical_unavailable: 17, legacy_type_1_excluded: 61 },
    nonauthority: { execution_authority: false, provider_conformance: false, data_rights: false, backtest_eligibility: false, monitoring_runtime: false, deployment_authority: false }, catalogue_identity: address(2) }
}

it('strictly parses the exact closed 243-row help projection', () => {
  const parsed = parseCatalogue(fixture())
  const rows = parsed.groups.flatMap((group) => group.components)
  expect(rows).toHaveLength(243)
  expect(rows.filter((row) => row.help.customisation.parameters.length)).toHaveLength(161)
  expect(rows.find((row) => row.component_id === 'analytical.ohlcv')?.help.semantic_kind).toBe('FIELD_SPLITTER')
  expect(rows.find((row) => row.component_id === 'analytical.ohlcv')?.help.semantic_text).toBe(
    'Return separately named completed-bar open, high, low, close and volume series. No DataFrame hidden under a scalar value port.',
  )
})

it.each([
  (value: any) => { delete value.groups[0].components[0].help },
  (value: any) => { delete value.groups[0].components[0].help.description },
  (value: any) => { value.groups[0].components[0].help.extra = true },
  (value: any) => { value.groups[0].components[0].help.component_version = 3 },
  (value: any) => { value.groups[0].components[0].help.implementation_binding = address(9999) },
  (value: any) => { value.groups[0].components[0].help.sources[0].title = `sha256:${'a'.repeat(64)}` },
  (value: any) => { value.groups[0].components[0].help.sources[0].extra = 'unsafe' },
  (value: any) => { value.groups[0].components[0].help.customisation.parameters[0].default = 99 },
])('rejects incomplete, extra, mismatched, unsafe and descriptor-divergent help', (mutate) => {
  const value = fixture(); mutate(value)
  expect(() => parseCatalogue(value)).toThrow(ContractError)
})

it('records the mixed-version rollout boundary for the strict legacy row shape', () => {
  const row = fixture().groups[0].components[0]
  const legacyFields = new Set([
    'component_id', 'component_version', 'component_address', 'display_name', 'visible_family',
    'presentation_group_order', 'presentation_group_name', 'domain_family', 'structural_role',
    'descriptor', 'node_contract', 'node_contract_address', 'implementation_address',
    'contract_binding', 'contract_binding_address', 'data_requirement', 'data_requirement_address',
    'mode_eligibility', 'provider_requirements', 'resource_profile', 'availability',
  ])
  expect(Object.keys(row).filter((field) => !legacyFields.has(field))).toEqual(['help'])
  const oldResponse = fixture(); delete (oldResponse.groups[0].components[0] as any).help
  expect(() => parseCatalogue(oldResponse)).toThrow(ContractError)
})

it('rejects forged OHLCV wording', () => {
  const value = fixture(); const row = value.groups.flatMap((group) => group.components).find((component) => component.component_id === 'analytical.ohlcv')!
  row.help.description = 'Returns an indicator from a forming candle.'
  expect(() => parseCatalogue(value)).toThrow(ContractError)
})

it('keeps legacy manifests closed and accepts only the explicit limited provider capability', () => {
  const legacy = parseManifest(release)
  expect(providerOnboardingEnabled(legacy)).toBe(false)
  expect(legacy.capabilities.data_provider_onboarding.state).toBe('BLOCKED')
  const enabled = structuredClone(release)
  ;(enabled.capabilities as Record<string, any>).data_provider_onboarding = {
    state: 'ENABLED_WITH_LIMIT', ui_navigation: true,
    reason: 'Local encrypted onboarding only.',
  }
  expect(providerOnboardingEnabled(parseManifest(enabled))).toBe(true)
  ;(enabled.capabilities as Record<string, any>).data_provider_onboarding.state = 'ENABLED'
  expect(providerOnboardingEnabled(parseManifest(enabled))).toBe(false)
})

it('accepts the backend-authorized empty V2 graph description without relaxing its type or bound', () => {
  const document = { format_version: 2, strategy_id: 'empty-description', strategy_version: 1,
    metadata: { metadata_version: 1, name: 'Empty description', description: '', tags: [] },
    graph_inputs: [], graph_outputs: [], nodes: [], edges: [] }
  const response = { project_id: 'project.a', graph_identifier: 'empty-description', semantic_revision: 0,
    current_version: null, published_revision: null, document, content_address: address(21), graph_address: address(22) }
  expect(parseV2Draft(response, 'project.a', 'empty-description').document.metadata.description).toBe('')
  for (const invalid of [undefined, 1, 'x'.repeat(4001)]) {
    const changed = structuredClone(response) as any
    if (invalid === undefined) delete changed.document.metadata.description
    else changed.document.metadata.description = invalid
    expect(() => parseV2Draft(changed, 'project.a', 'empty-description')).toThrow(ContractError)
  }
})

it('accepts only bounded causal completed-candle Market context pages', () => {
  const value = { schema: 'strategy-os-market-context/1', state: 'AVAILABLE',
    market_context_address: address(1), projection_address: address(2),
    source: { kind: 'VERIFIED_SAVED_RUN', address: address(3) }, graph: {},
    dataset_manifest_address: address(4), canonical_instrument_address: address(5),
    instrument_label: 'XNSE · EQUITY · SPOT', timeframe_seconds: 60,
    source_as_of: '2026-01-01T10:02:00Z', replay_at: '2026-01-01T10:01:00Z',
    bars: [{ cursor: 1, event_time: '2026-01-01T10:00:00Z',
      completed_at: '2026-01-01T10:01:00Z', open: 100, high: 102, low: 99,
      close: 101, volume: 10 }],
    page: { after: 0, limit: 500, next_cursor: null, visible_count: 1 } }
  expect(parseMarketContext(value, 0, 500).bars).toHaveLength(1)
  expect(() => parseMarketContext({ ...value, replay_at: '2026-01-01T10:00:30Z' }, 0, 500)).toThrow(ContractError)
  expect(() => parseMarketContext({ ...value, bars: [{ ...value.bars[0], close: Infinity }] }, 0, 500)).toThrow(ContractError)
  expect(() => parseMarketContext({ ...value, unknown: true }, 0, 500)).toThrow(ContractError)
})


function importedDatasetPage() {
  return { schema: 'strategy-os-canonical-dataset-index/1', project_id: 'project.a', next_cursor: null, items: [{
    manifest_address: address(10), instrument_address: address(11), canonical_instrument_label: 'NIFTY 50', asset_class: 'INDEX', contract_kind: 'SPOT',
    interval: 'day', event_start: '2025-09-04T18:30:00Z', event_end: '2026-09-03T18:30:00Z', availability_end: '2026-09-05T00:00:00Z', as_of: '2026-09-05T00:00:00Z',
    bar_count: 248, fields: ['CLOSE', 'HIGH', 'LOW', 'OPEN'], provider_evidence_state: 'USER_CSV_SHAPE_VALIDATED', market_truth_state: 'RECONSTRUCTED_WITH_GAPS',
    gaps: [{ reason: 'HISTORICAL_SOURCE_AVAILABILITY_NOT_SUPPLIED' }], backtest_eligibility: 'UNAVAILABLE', refusal_code: 'CANONICAL_INDEX_BENCHMARK_ONLY',
    source_type: 'USER_SUPPLIED', historical_source_availability: 'NOT_SUPPLIED', calendar_coverage: 'NOT_ASSERTED', rights_scope: 'PERSONAL_RESEARCH_ONLY', research_compatibility: 'BENCHMARK_INPUT_ONLY',
  }] }
}

it('preserves imported data limitations and absent volume when reading the project index', () => {
  const row = parseResearchDatasetPage(importedDatasetPage(), 'project.a', 50).items[0]
  expect(row.source_type).toBe('USER_SUPPLIED')
  expect(row.research_compatibility).toBe('BENCHMARK_INPUT_ONLY')
  expect(row.backtest_eligibility).toBe('UNAVAILABLE')
  expect(row.fields).toEqual(['CLOSE', 'HIGH', 'LOW', 'OPEN'])
  expect(row.rights_scope).toBe('PERSONAL_RESEARCH_ONLY')
})

it.each([
  (row: Record<string, unknown>) => { delete row.calendar_coverage },
  (row: Record<string, unknown>) => { row.rights_scope = 'PROVIDER_CONTRACT' },
  (row: Record<string, unknown>) => { row.provider_evidence_state = 'VERIFIED_REFERENCES_PRESENT' },
  (row: Record<string, unknown>) => { row.research_compatibility = 'TRADABLE_INDEX' },
  (row: Record<string, unknown>) => { row.unexpected = 'extra' },
])('rejects incomplete or falsely certified import metadata', (change) => {
  const page = importedDatasetPage(); change(page.items[0])
  expect(() => parseResearchDatasetPage(page, 'project.a', 50)).toThrow(ContractError)
})

it('keeps the previous provider index shape readable without inventing source declarations', () => {
  const page = importedDatasetPage(); const row = page.items[0] as Record<string, unknown>
  for (const field of ['source_type', 'historical_source_availability', 'calendar_coverage', 'rights_scope', 'research_compatibility']) delete row[field]
  row.provider_evidence_state = 'VERIFIED_REFERENCES_PRESENT'; row.market_truth_state = 'VERIFIED_REFERENCES_PRESENT'
  expect(parseResearchDatasetPage(page, 'project.a', 50).items[0].source_type).toBeUndefined()
})

function currentCatalogueFixture() {
  const value: any = fixture()
  value.schema = 'strategy-os-verified-language-catalogue/2'
  for (const group of value.groups) for (const row of group.components) Object.assign(row, { component_kind: 'LEAF', composition_binding: null })
  const field = ['close', 'high', 'low']
  const math = ['true_range', 'value', 'ema_first_close', 'rolling_stddev_population', 'rma_sma_seed', 'nearest_rank', 'subtract', 'divide', 'multiply', 'maximum', 'abs']
  const logic = ['gt', 'lt', 'le', 'and', 'or', 'lag', 'fallback_zero', 'fallback_false', 'fallback_value', 'optional_condition']
  const parameterized = new Set(['value', 'ema_first_close', 'rolling_stddev_population', 'rma_sma_seed', 'nearest_rank', 'lag', 'optional_condition'])
  const additions = [...field, ...math, ...logic].map((name, index) => ({ id: `strategy_math.${name}`, version: ['close', 'high', 'low', 'true_range'].includes(name) ? 2 : 1,
    family: ['close', 'high', 'low', 'true_range'].includes(name) ? 0 : 1,
    kind: field.includes(name) ? 'FIELD_SELECTION' : math.includes(name) ? 'MATHEMATICAL_FORMULA' : 'LOGICAL_OPERATION',
    hasParameter: parameterized.has(name), compound: false, index }))
  additions.push(...['strategy.trend_impulse_v3', 'strategy.expanding_z_v4_pine'].map((id, index) => ({ id, version: 1, family: 1, kind: 'MATHEMATICAL_FORMULA', hasParameter: true, compound: true, index: 24 + index })))
  for (const addition of additions) {
    const group = value.groups[addition.family]
    const row = structuredClone(value.groups[0].components[0])
    const { name: _name, ...definition } = parameter('length')
    const parameters = addition.hasParameter ? { length: definition } : {}
    Object.assign(row, { component_kind: addition.compound ? 'COMPOUND' : 'LEAF', component_id: addition.id, component_version: addition.version,
      component_address: address(6000 + addition.index), display_name: addition.id,
      visible_family: group.visible_family, presentation_group_order: group.order, presentation_group_name: group.display_name,
      descriptor: { component_id: addition.id, component_version: addition.version, ports: [], parameters },
      availability: { status: 'CONDITIONAL', authority: 'NONE', provider_support_verified: false, data_rights_verified: false, backtest_eligible: false } })
    row.help = { ...row.help, component_id: addition.id, component_version: addition.version, semantic_kind: addition.kind,
      customisation: { ...row.help.customisation, parameters: addition.hasParameter ? [parameter('length')] : [], guidance: addition.hasParameter ? 'Set length.' : 'This built-in has no parameters.' },
      availability: { status: 'CONDITIONAL', authority: 'NONE', condition: 'Resolve the required inputs before research.' } }
    if (addition.compound) {
      row.descriptor.compound = { body: { graph_inputs: [], graph_outputs: [], nodes: [], edges: [] }, parameter_bindings: [] }
      for (const name of ['node_contract', 'node_contract_address', 'implementation_address', 'contract_binding', 'contract_binding_address', 'data_requirement', 'data_requirement_address', 'mode_eligibility', 'provider_requirements', 'resource_profile']) row[name] = null
      row.composition_binding = { component_address: row.component_address, registry_identity: value.registry_identity }
      row.help.implementation_binding = null
      row.help.composition_binding = { ...row.composition_binding }
    }
    group.components.push(row)
  }
  Object.assign(value.counts, { components: 269, original_primitives: 24, original_compounds: 2 })
  return value
}

it('parses both closed catalogue versions and keeps compound identity separate', () => {
  expect(parseCatalogue(fixture()).schema).toBe('strategy-os-verified-language-catalogue/1')
  const parsed = parseCatalogue(currentCatalogueFixture())
  const rows = parsed.groups.flatMap((group) => group.components)
  expect(rows).toHaveLength(269)
  const compounds = rows.filter((row) => row.component_kind === 'COMPOUND')
  expect(compounds).toHaveLength(2)
  for (const row of compounds) {
    expect(row.help.implementation_binding).toBeNull()
    expect(row.help.composition_binding?.component_address).toBe(row.component_address)
    expect(row.help.composition_binding?.registry_identity).toBe(parsed.registry_identity)
    expect(row.data_requirement).toBeNull()
  }
})

it.each([
  (row: any) => { row.implementation_address = row.component_address },
  (row: any) => { row.help.implementation_binding = row.component_address },
  (row: any) => { row.composition_binding.registry_identity = address(999) },
  (row: any) => { row.help.composition_binding.component_address = address(999) },
  (row: any) => { row.node_contract = {} },
  (row: any) => { delete row.descriptor.compound },
  (row: any) => { delete row.help },
  (row: any) => { row.component_kind = 'LEAF' },
])('rejects forged or incomplete compound identity', (mutate) => {
  const value = currentCatalogueFixture()
  const row = value.groups.flatMap((group: any) => group.components).find((item: any) => item.component_kind === 'COMPOUND')
  mutate(row)
  expect(() => parseCatalogue(value)).toThrow(ContractError)
})

it('rejects missing, duplicated and unknown original catalogue identities', () => {
  const unknown = currentCatalogueFixture()
  const row = unknown.groups[1].components.find((item: any) => item.component_id === 'strategy_math.value')
  row.component_id = row.descriptor.component_id = row.help.component_id = 'strategy_math.unknown'
  expect(() => parseCatalogue(unknown)).toThrow(ContractError)
  const duplicate = currentCatalogueFixture(); duplicate.groups[0].components[1] = duplicate.groups[0].components[0]
  expect(() => parseCatalogue(duplicate)).toThrow(ContractError)
  const missing = currentCatalogueFixture(); missing.groups[1].components.pop()
  expect(() => parseCatalogue(missing)).toThrow(ContractError)
})

it.each([
  (value: any) => { value.groups[0].components[0].component_kind = 'UNKNOWN' },
  (value: any) => { value.groups[0].components[0].node_contract = null },
  (value: any) => { value.groups[0].components[0].provider_requirements = {} },
  (value: any) => { value.groups[0].components[0].composition_binding = {} },
  (value: any) => { value.groups[0].components[0].help.sources = [] },
  (value: any) => { const help = value.groups[0].components[0].help; help.sources.push(help.sources[0]) },
  (value: any) => { value.groups[0].components[0].help.sources[0].year = 1799 },
  (value: any) => { value.groups[0].components[0].help.sources[0].url = 'http://example.test/source' },
  (value: any) => { value.groups[0].components[0].help.customisation.built_in_code_immutable = false },
  (value: any) => { value.groups[0].components[0].help.customisation.parameters[0].required = true },
  (value: any) => { value.registry_identity = 'not-an-address' },
  (value: any) => { value.counts.unreviewed = 1 },
  (value: any) => { value.nonauthority.execution_authority = true },
  (value: any) => { value.groups[0].components[0].availability.backtest_eligible = true },
])('keeps catalogue identity, source, immutability and nonauthority boundaries closed', (mutate) => {
  const value = currentCatalogueFixture(); mutate(value)
  expect(() => parseCatalogue(value)).toThrow(ContractError)
})

// Settings must reconstruct locally before controls can claim inheritance.
import { parseStrategyResearchSettings, parseWorkspaceResearchSettings } from './contracts'
const settingsDefaults = { research_capital: 100000, seed: 0, min_trades: 10, n_folds: 4, min_positive_fold_frac: .6, risk_policy: 'none' }
function settingsResponse() {
  const revision = { schema: 'research-settings-revision/1', owner_id: 'owner.a', graph_identifier: null,
    revision: 0, expected_revision: 0, request_id: null, enabled: true, values: settingsDefaults, content_address: `sha256:${'a'.repeat(64)}` }
  return { workspace: revision, strategy: { ...revision, revision: 1, request_id: '12345678-1234-4234-8234-123456789abc', graph_identifier: 'strategy.a', values: { n_folds: 8 } },
    values: { ...settingsDefaults, n_folds: 8 }, sources: Object.fromEntries(Object.keys(settingsDefaults).map((key) => [key, key === 'n_folds' ? 'strategy' : 'workspace'])), fixed_assumptions: {} }
}
it('checks inherited settings and retained disabled overrides', () => {
  const response = settingsResponse()
  expect(parseStrategyResearchSettings(response, 'strategy.a').values.n_folds).toBe(8)
  response.strategy.enabled = false
  response.values.n_folds = 4; response.sources.n_folds = 'workspace'
  expect(parseStrategyResearchSettings(response, 'strategy.a').strategy.values.n_folds).toBe(8)
  expect(parseStrategyResearchSettings(response, 'strategy.a').values.n_folds).toBe(4)
  expect(parseWorkspaceResearchSettings({ workspace: response.workspace, fixed_assumptions: {} }).revision).toBe(0)
})
it('rejects inconsistent settings identity, values and attribution', () => {
  const wrongOwner = settingsResponse(); wrongOwner.strategy.owner_id = 'owner.b'
  expect(() => parseStrategyResearchSettings(wrongOwner, 'strategy.a')).toThrow()
  expect(() => parseStrategyResearchSettings(settingsResponse(), 'strategy.b')).toThrow()
  const wrongValues = settingsResponse(); wrongValues.values.n_folds = 9
  expect(() => parseStrategyResearchSettings(wrongValues, 'strategy.a')).toThrow()
  const wrongSource = settingsResponse(); wrongSource.sources.n_folds = 'workspace'
  expect(() => parseStrategyResearchSettings(wrongSource, 'strategy.a')).toThrow()
})
it.each([0, Infinity, NaN, 1000000001])('rejects invalid research capital %s', (capital) => {
  const response = settingsResponse()
  response.workspace.values = { ...settingsDefaults, research_capital: capital }
  expect(() => parseWorkspaceResearchSettings({ workspace: response.workspace, fixed_assumptions: {} })).toThrow()
})


it.each([
  { revision: 2147483648 }, { expected_revision: 2 }, { request_id: 'bad' },
  { enabled: false }, { values: { ...settingsDefaults, seed: 1.5 } },
  { values: { ...settingsDefaults, n_folds: 1 } }, { values: { ...settingsDefaults, risk_policy: 'unknown' } },
  { values: { ...settingsDefaults, extra: 1 } }, { values: {} },
])('refuses invalid workspace revision or values', (change) => {
  const result = settingsResponse()
  expect(() => parseWorkspaceResearchSettings({ workspace: { ...result.workspace, ...change }, fixed_assumptions: {} })).toThrow()
})

it.each(['none', 'pine-v4-ratchet/1', 'pine-v4-reversal/1'])('accepts the exact supported risk policy %s', (risk_policy) => {
  const result = settingsResponse()
  expect(parseWorkspaceResearchSettings({ workspace: { ...result.workspace, values: { ...settingsDefaults, risk_policy } }, fixed_assumptions: {} }).values.risk_policy).toBe(risk_policy)
})

it('accepts the exact historical daily-gap addition while preserving the prior catalogue', () => {
  const value = currentCatalogueFixture()
  const group = value.groups.find((item: any) => item.visible_family === 'TYPE_3')
  const row = structuredClone(group.components[0])
  row.component_id = 'structure.historical_daily_gaps'; row.component_address = address(9000)
  row.descriptor = { ...row.descriptor, component_id: row.component_id, parameters: {} }
  row.help = { ...row.help, component_id: row.component_id, semantic_kind: 'MATHEMATICAL_FORMULA',
    customisation: { ...row.help.customisation, parameters: [], guidance: 'This built-in has no parameters.' } }
  group.components.push(row)
  Object.assign(value.counts, { components: 270, type_3: 64 })
  expect(parseCatalogue(value).groups.flatMap((item) => item.components)).toHaveLength(270)
  expect(parseCatalogue(currentCatalogueFixture()).groups.flatMap((item) => item.components)).toHaveLength(269)
  const wrong = structuredClone(value)
  const changed = wrong.groups.flatMap((item: any) => item.components).find((item: any) => item.component_id === row.component_id)
  changed.component_version = 3; changed.descriptor.component_version = 3; changed.help.component_version = 3
  expect(() => parseCatalogue(wrong)).toThrow(ContractError)
})

function completedV2Run() {
  const graph = { project_id: 'project.a', identifier: 'ema-z', version: 5, content_address: address(91), format_version: 2, graph_address: address(92) }
  return { run_id: 1, spec_id: 'a'.repeat(32), status: 'completed', decision: 'archive', evidence_state: 'verified', graph, candidate: null,
    evidence: { spec_id: 'a'.repeat(32), run: { id: 1, status: 'completed', decision: 'archive' },
      provenance: { graph_provenance: { schema: 'saved-v2-graph-research-provenance/1', graph },
        cost_assumptions: { capital: 100000, slippage_bps: 5, slippage_multiplier: 2, charge_model: 'zerodha_charges_v1', sizing_model: 'one_lot_or_cash_budget_v1' },
        gates: { min_oos_trades: 10, n_folds: 4, min_positive_fold_fraction: 0.6, optimize_search: false, pbo_threshold: 0.3, sibling_trials: 1 } },
      results: { qualified: [] as string[], validated: [] as string[], rejected: [{ instrument: 'RELIANCE', reason: 'insufficient trades (4<10)' }], total_bars: 248 } } }
}

it('reads a completed V2 run and its failed development conclusion using the actual API graph shape', () => {
  const value = completedV2Run()
  const run = parseExperimentDetail(value)
  expect(run.graph).toEqual({ project_id: 'project.a', identifier: 'ema-z', version: 5, content_address: address(91) })
  expect(run.research_outcome).toEqual({ qualified: 0, validated: 0, total_bars: 248, rejected: value.evidence.results.rejected })
  expect(parseExperimentPage({ runs: [value] }).runs[0].run_id).toBe(1)
  expect(run.canonical_optimization).toBeUndefined()
})

it.each(['version', 'address', 'extra', 'spec', 'run', 'status', 'decision', 'graph', 'validated', 'duplicate', 'reason'])(
  'refuses a misleading V2 research result at the %s boundary', (fault) => {
    const value = completedV2Run()
    if (fault === 'version') value.graph.format_version = 3
    if (fault === 'address') value.graph.graph_address = 'not-an-address'
    if (fault === 'extra') Object.assign(value.graph, { unknown: true })
    if (fault === 'spec') value.evidence.spec_id = 'b'.repeat(32)
    if (fault === 'run') value.evidence.run.id = 2
    if (fault === 'status') value.evidence.run.status = 'running'
    if (fault === 'decision') value.evidence.run.decision = 'propose'
    if (fault === 'graph') value.evidence.provenance.graph_provenance.graph = { ...value.graph, content_address: address(93) }
    if (fault === 'validated') value.evidence.results.validated = ['not-qualified']
    if (fault === 'duplicate') value.evidence.results.qualified = ['RELIANCE', 'RELIANCE']
    if (fault === 'reason') value.evidence.results.rejected[0].reason = ''
    expect(() => parseExperimentDetail(value)).toThrow(ContractError)
  },
)

const historyRequest = { selection_address: address(20), start_date: '2025-01-01', end_date: '2025-12-31', interval: 'day' as const }
function providerHistoryReceipt() {
  return { schema: 'strategy-os-provider-history-import/1', reused: false, project_id: 'project.a', selection_address: historyRequest.selection_address,
    requested_start: '2024-12-31T18:30:00+00:00', requested_end: '2025-12-31T18:29:59+00:00',
    returned_start: '2025-01-01T18:30:00+00:00', returned_end: '2025-12-30T18:30:00+00:00',
    request_count: 2, empty_request_count: 1, request_window_days: 1900, application_bar_limit: 2000, provider_retention: 'UNKNOWN',
    item: { ...importedDatasetPage().items[0], provider_selection_address: historyRequest.selection_address, interval: 'day',
      event_start: '2025-01-01T18:30:00+00:00', event_end: '2025-12-31T18:30:00+00:00',
      source_type: 'PROVIDER_AUTHORITY', provider_evidence_state: 'VERIFIED_REFERENCES_PRESENT', rights_scope: 'PROVIDER_CONTRACT' } }
}
it.each(['RECONSTRUCTED_WITH_GAPS', 'VERIFIED_REFERENCES_PRESENT'])('reads retained provider history without claiming publication or calendar proof: %s', (truth) => {
  const receipt = providerHistoryReceipt(); receipt.item.market_truth_state = truth
  const result = parseProviderHistoryReceipt(receipt, 'project.a', historyRequest)
  expect(result.item.provider_selection_address).toBe(historyRequest.selection_address)
  expect(result.item.historical_source_availability).toBe('NOT_SUPPLIED')
  expect(result.item.calendar_coverage).toBe('NOT_ASSERTED')
  expect(result.item.market_truth_state).toBe(truth)
  expect(result.empty_request_count).toBe(1)
  expect(result.provider_retention).toBe('UNKNOWN')
})
it.each([
  { project_id: 'other' }, { selection_address: address(21) }, { requested_start: '2025-01-01T00:00:00Z' },
  { requested_end: '2025-12-31T00:00:00Z' }, { returned_start: '2024-12-01T18:30:00Z' },
  { returned_end: '2026-01-01T18:30:00Z' }, { returned_end: '2024-12-01T18:30:00Z' },
  { request_count: 0 }, { request_count: 65 }, { request_count: 1.5 }, { empty_request_count: 2 }, { empty_request_count: -1 },
  { request_window_days: 2000 }, { application_bar_limit: 1900 }, { provider_retention: '1900_DAYS' }, { extra: 'unverified' },
])('refuses a mismatched or unsupported provider history receipt %j', (change) => {
  expect(() => parseProviderHistoryReceipt({ ...providerHistoryReceipt(), ...change }, 'project.a', historyRequest)).toThrow(ContractError)
})
it.each([
  { provider_selection_address: null }, { provider_selection_address: address(21) }, { provider_selection_address: '77' },
  { event_start: '2025-01-02T18:30:00Z' }, { event_end: '2026-01-01T18:30:00Z' }, { interval: '15m' }, { bar_count: 2001 },
  { calendar_coverage: 'DECLARED' }, { historical_source_availability: 'DECLARED' }, { source_type: 'USER_SUPPLIED' },
  { provider_evidence_state: 'USER_CSV_SHAPE_VALIDATED' }, { rights_scope: 'PERSONAL_RESEARCH_ONLY' },
])('refuses dataset substitution or unsupported source claims %j', (change) => {
  const receipt = providerHistoryReceipt()
  expect(() => parseProviderHistoryReceipt({ ...receipt, item: { ...receipt.item, ...change } }, 'project.a', historyRequest)).toThrow(ContractError)
})
it.each(['2025-02-29', '2025-02-30', '2026-13-01', '0000-01-01', '2026-1-1', '', 'not a date'])('refuses impossible or incomplete history dates %s', (date) => {
  expect(validHistoryDate(date)).toBe(false)
  expect(() => assertProviderHistoryRequest({ ...historyRequest, start_date: date })).toThrow(ContractError)
})
it('accepts leap days and rejects reverse ranges and unsupported request fields', () => {
  expect(validHistoryDate('2024-02-29')).toBe(true)
  expect(() => assertProviderHistoryRequest({ ...historyRequest, start_date: '2026-01-01' })).toThrow(ContractError)
  expect(() => assertProviderHistoryRequest({ ...historyRequest, interval: '15m' } as never)).toThrow(ContractError)
  expect(() => assertProviderHistoryRequest({ ...historyRequest, token: 77 } as never)).toThrow(ContractError)
  const page = importedDatasetPage()
  expect(parseResearchDatasetPage({ ...page, items: [{ ...page.items[0], provider_selection_address: null }] }, 'project.a', 50).items[0].provider_selection_address).toBeNull()
  expect(() => parseResearchDatasetPage({ ...page, items: [{ ...page.items[0], provider_selection_address: address(20) }] }, 'project.a', 50)).toThrow(ContractError)
})

it.each([true, false])('preserves the explicit saved-history reuse flag %s', (reused) => {
  expect(parseProviderHistoryReceipt({ ...providerHistoryReceipt(), reused }, 'project.a', historyRequest).reused).toBe(reused)
})
it.each([undefined, null, 0, 1, 'false', 'true'])('refuses an absent or non-boolean saved-history reuse flag %j', (reused) => {
  expect(() => parseProviderHistoryReceipt({ ...providerHistoryReceipt(), reused }, 'project.a', historyRequest)).toThrow(ContractError)
})
it('requires a reuse decision in every history response', () => {
  const { reused: _reused, ...receipt } = providerHistoryReceipt()
  expect(() => parseProviderHistoryReceipt(receipt, 'project.a', historyRequest)).toThrow(ContractError)
})
