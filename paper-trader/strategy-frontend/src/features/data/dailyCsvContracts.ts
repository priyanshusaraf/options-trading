import { ContractError, sameJson } from '../../shell/contracts'

export const DAILY_CSV_LIMIT_BYTES = 1024 * 1024

export function dailyCsvFilesError(file: File, sessions?: File) {
  if (file.size > DAILY_CSV_LIMIT_BYTES) return 'Choose a CSV no larger than 1 MiB.'
  if (sessions && sessions.size > DAILY_CSV_LIMIT_BYTES) return 'Choose session metadata no larger than 1 MiB.'
  if (file.size + (sessions?.size ?? 0) > DAILY_CSV_LIMIT_BYTES) return 'Keep the two files together within 1 MiB to leave room for the upload form.'
  return ''
}

export type DailySessionMetadata = Readonly<{
  state: 'USER_DECLARED_COMPLETE'
  schema: 'user-declared-daily-sessions/1'
  source: string
  row_count: number
  source_sha256: string
  byte_count: number
}>

export type DailyCsvMetadata = Readonly<{
  instrument: string
  source_label?: string
  venue_code: 'XNSE' | 'XBOM'
  asset_class: 'EQUITY' | 'INDEX'
  columns: Readonly<{
    instrument: string | null
    date: string
    open: string
    high: string
    low: string
    close: string
    volume: string | null
  }>
  date_format: '%d %b %Y' | '%Y-%m-%d'
  date_timezone: 'Asia/Kolkata'
  interval: 'day'
  contract_kind: 'SPOT'
  currency: 'INR'
}>

export type DailyCsvInspection = Readonly<{
  schema: 'strategy-os-user-csv-inspection/1' | 'strategy-os-user-csv-inspection/2'
  session_metadata?: DailySessionMetadata
  source_type: 'USER_SUPPLIED'
  source_sha256: string
  byte_count: number
  row_count: number
  source_order: 'ASCENDING' | 'DESCENDING'
  fields: readonly string[]
  interval: 'day'
  event_start: string
  event_end: string
  historical_source_availability: 'NOT_SUPPLIED'
  calendar_coverage: 'NOT_ASSERTED'
  rights_scope: 'PERSONAL_RESEARCH_ONLY'
}>

export type DailyCsvImport = Omit<DailyCsvInspection, 'schema'> & Readonly<{
  schema: 'strategy-os-user-csv-import/1' | 'strategy-os-user-csv-import/2'
  project_id: string
  manifest_address: string
  instrument_address: string
  imported_at: string
  ready_as_of: string
}>

function record(value: unknown): Record<string, unknown> {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) throw new ContractError()
  return value as Record<string, unknown>
}

function exactKeys(value: Record<string, unknown>, expected: readonly string[]) {
  if (Object.keys(value).length !== expected.length || !expected.every((key) => Object.hasOwn(value, key))) throw new ContractError()
}

const INSPECTION_KEYS = ['schema', 'source_type', 'source_sha256', 'byte_count', 'row_count',
  'source_order', 'fields', 'interval', 'event_start', 'event_end',
  'historical_source_availability', 'calendar_coverage', 'rights_scope'] as const

function boundedWhole(value: unknown, minimum: number, maximum: number) {
  return Number.isSafeInteger(value) && Number(value) >= minimum && Number(value) <= maximum
}

function validDate(value: unknown) {
  return typeof value === 'string' && Number.isFinite(Date.parse(value))
}

function sourceHash(value: unknown) {
  return typeof value === 'string' && /^[0-9a-f]{64}$/.test(value)
}

function inspectionFields(value: unknown) {
  if (!Array.isArray(value)) return false
  const expected = value.includes('VOLUME')
    ? ['OPEN', 'HIGH', 'LOW', 'CLOSE', 'VOLUME'] : ['OPEN', 'HIGH', 'LOW', 'CLOSE']
  return value.length === expected.length && expected.every((field, index) => value[index] === field)
}

function inspectionSource(item: Record<string, unknown>, schema: string) {
  const expected = { schema, source_type: 'USER_SUPPLIED', interval: 'day', historical_source_availability: 'NOT_SUPPLIED',
    calendar_coverage: 'NOT_ASSERTED', rights_scope: 'PERSONAL_RESEARCH_ONLY' }
  return Object.entries(expected).every(([key, value]) => item[key] === value)
    && ['ASCENDING', 'DESCENDING'].includes(String(item.source_order))
}

function sessionMetadata(value: unknown, rowCount: unknown): DailySessionMetadata {
  const item = record(value)
  exactKeys(item, ['state', 'schema', 'source', 'row_count', 'source_sha256', 'byte_count'])
  if (item.state !== 'USER_DECLARED_COMPLETE' || item.schema !== 'user-declared-daily-sessions/1'
    || typeof item.source !== 'string' || !item.source.trim() || item.source.length > 2048
    || item.row_count !== rowCount || !sourceHash(item.source_sha256)
    || !boundedWhole(item.byte_count, 1, DAILY_CSV_LIMIT_BYTES)) throw new ContractError()
  return Object.freeze(item) as DailySessionMetadata
}

function inspectionVersion(item: Record<string, unknown>, prefix: string) {
  const version = item.schema === `${prefix}/2` ? 2 : 1
  return { schema: `${prefix}/${version}`, version,
    keys: version === 2 ? [...INSPECTION_KEYS, 'session_metadata'] : INSPECTION_KEYS }
}

function inspection(value: unknown, prefix: string) {
  const item = { ...record(value) }
  const { schema, version, keys } = inspectionVersion(item, prefix)
  if (!inspectionSource(item, schema) || !sourceHash(item.source_sha256)
    || !boundedWhole(item.byte_count, 1, DAILY_CSV_LIMIT_BYTES) || !boundedWhole(item.row_count, 1, 2000)
    || !inspectionFields(item.fields) || ![item.event_start, item.event_end].every(validDate)) throw new ContractError()
  if (version === 2) item.session_metadata = sessionMetadata(item.session_metadata, item.row_count)
  return { item, keys }
}

export function parseDailyCsvInspection(value: unknown): DailyCsvInspection {
  const { item, keys } = inspection(value, 'strategy-os-user-csv-inspection')
  exactKeys(item, keys)
  return Object.freeze(item) as DailyCsvInspection
}

export function parseDailyCsvImport(value: unknown, projectId: string): DailyCsvImport {
  const { item, keys } = inspection(value, 'strategy-os-user-csv-import')
  exactKeys(item, [...keys, 'project_id', 'manifest_address', 'instrument_address', 'imported_at', 'ready_as_of'])
  if (item.project_id !== projectId
    || typeof item.manifest_address !== 'string' || !/^sha256:[0-9a-f]{64}$/.test(item.manifest_address)
    || typeof item.instrument_address !== 'string' || !/^sha256:[0-9a-f]{64}$/.test(item.instrument_address)
    || ![item.imported_at, item.ready_as_of].every(validDate)) throw new ContractError()
  return Object.freeze(item) as DailyCsvImport
}

export function requireMatchingCsvImport(inspected: DailyCsvInspection, imported: DailyCsvImport) {
  const keys = [...INSPECTION_KEYS.filter((key) => key !== 'schema'), 'session_metadata'] as const
  if (!keys.every((key) => sameJson(inspected[key], imported[key]))) throw new ContractError()
}

export function requireSessionInspection(inspected: DailyCsvInspection, hasSessionFile: boolean) {
  if (Boolean(inspected.session_metadata) !== hasSessionFile) throw new ContractError()
}
