import { ContractError } from '../../shell/contracts'
import type { StrategyApi } from '../../shell/api'
import { parseScopeMember, scopeMemberIdentity, type ScopeMember } from './staticScopeContracts'
import type { WatchlistMonitorClient, WatchlistMonitorContext, WatchlistMonitorRow, WatchlistStrategySelection } from './watchlistMonitorTypes'

function object(input: unknown, fields: string[]): Record<string, unknown> {
  if (!input || typeof input !== 'object' || Array.isArray(input)) throw new ContractError()
  const value = input as Record<string, unknown>
  if (Object.keys(value).length !== fields.length || fields.some((key) => !Object.hasOwn(value, key))) throw new ContractError()
  return value
}
function text(input: unknown, maximum = 512): string {
  if (typeof input !== 'string' || !input.trim() || input.length > maximum || /[\u0000-\u001f\u007f]/.test(input)) throw new ContractError()
  return input
}
function matching(input: unknown, pattern: RegExp): string {
  const value = text(input)
  if (!pattern.test(value)) throw new ContractError()
  return value
}
const address = (input: unknown) => matching(input, /^sha256:[0-9a-f]{64}$/)
const identifier = (input: unknown) => matching(input, /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/)
function count(input: unknown, minimum = 0): number {
  if (!Number.isSafeInteger(input) || Number(input) < minimum || Number(input) > 2147483647) throw new ContractError()
  return Number(input)
}
function boolean(input: unknown): boolean {
  if (typeof input !== 'boolean') throw new ContractError()
  return input
}
function choice<T extends string>(input: unknown, values: readonly T[]): T {
  if (!values.includes(input as T)) throw new ContractError()
  return input as T
}
function nullable<T>(input: unknown, parse: (input: unknown) => T): T | null { return input === null ? null : parse(input) }
const timeframe = (input: unknown) => choice(input, ['15minute', '30minute', '60minute', 'day'] as const)
function clock(input: unknown): string {
  const value = matching(input, /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)$/)
  const parsed = Date.parse(value)
  if (!Number.isFinite(parsed) || new Date(parsed).toISOString().slice(0, 19) !== value.slice(0, 19)) throw new ContractError()
  return value
}
export function watchlistContextBody(context: WatchlistMonitorContext) {
  return { project_id: text(context.projectId, 64), scope_id: matching(context.scopeId, /^scope\.[A-Za-z0-9][A-Za-z0-9._-]{0,57}$/),
    scope_revision: count(context.scopeRevision, 1), scope_address: address(context.scopeAddress), membership_address: address(context.membershipAddress) }
}
export function watchlistMonitoringPath(context: WatchlistMonitorContext, list = false) {
  const body = watchlistContextBody(context)
  const path = `ir/projects/${encodeURIComponent(body.project_id)}/static-scopes/${encodeURIComponent(body.scope_id)}/monitoring-rows`
  return list ? `${path}?${new URLSearchParams({ scope_revision: String(body.scope_revision), scope_address: body.scope_address, membership_address: body.membership_address })}` : path
}
function contextEcho(input: unknown, expected: WatchlistMonitorContext) {
  const body = watchlistContextBody(expected), value = object(input, Object.keys(body))
  if (Object.entries(body).some(([key, item]) => value[key] !== item)) throw new ContractError()
}
function graph(input: unknown): NonNullable<WatchlistMonitorRow['graph']> {
  const value = object(input, ['graph_id', 'graph_version', 'graph_version_address', 'label'])
  return { graphId: identifier(value.graph_id), graphVersion: count(value.graph_version, 1), graphVersionAddress: address(value.graph_version_address), label: text(value.label, 128) }
}
function warmup(input: unknown) {
  const value = object(input, ['available', 'required'])
  return { available: count(value.available), required: count(value.required, 1) }
}
function result(input: unknown): WatchlistMonitorRow['result'] {
  const value = object(input, ['kind', 'label', 'evaluated_at', 'assignment_id', 'graph_version_address', 'reason', 'warmup'])
  return { kind: choice(value.kind, ['NOT_EVALUATED', 'HOLD', 'SIGNAL', 'WARMUP', 'STALE', 'ERROR'] as const), label: text(value.label, 128),
    evaluatedAt: nullable(value.evaluated_at, clock), assignmentId: nullable(value.assignment_id, identifier),
    graphVersionAddress: nullable(value.graph_version_address, address), reason: nullable(value.reason, text), warmup: nullable(value.warmup, warmup) }
}
function timeframes(input: unknown) {
  if (!Array.isArray(input) || input.length > 4) throw new ContractError()
  const values = input.map((item) => { const value = object(item, ['value', 'label']); return { value: timeframe(value.value), label: text(value.label, 64) } })
  if (new Set(values.map((item) => item.value)).size !== values.length) throw new ContractError()
  return values
}
function row(input: unknown): WatchlistMonitorRow {
  const value = object(input, ['member_key', 'configuration_revision', 'pinned', 'graph', 'timeframe', 'supported_timeframes', 'assignment_id', 'monitoring', 'can_configure', 'can_pin', 'can_set_monitoring', 'reason', 'result'])
  const parsed = { memberKey: matching(value.member_key, /^(?:CANONICAL|PROVIDER_REFERENCE):sha256:[0-9a-f]{64}$/), configurationRevision: count(value.configuration_revision),
    pinned: boolean(value.pinned), graph: nullable(value.graph, graph), timeframe: nullable(value.timeframe, timeframe), supportedTimeframes: timeframes(value.supported_timeframes),
    assignmentId: nullable(value.assignment_id, identifier), monitoring: choice(value.monitoring, ['OFF', 'ON', 'STARTING', 'PAUSED', 'BLOCKED'] as const),
    canConfigure: boolean(value.can_configure), canPin: boolean(value.can_pin), canSetMonitoring: boolean(value.can_set_monitoring), reason: nullable(value.reason, text), result: result(value.result) }
  verifyResult(parsed)
  return parsed
}
function verifyResult(value: WatchlistMonitorRow) {
  const evidence = value.result
  if (evidence.assignmentId !== null && evidence.assignmentId !== value.assignmentId) throw new ContractError()
  if (evidence.graphVersionAddress !== null && evidence.graphVersionAddress !== value.graph?.graphVersionAddress) throw new ContractError()
  if (['HOLD', 'SIGNAL', 'STALE'].includes(evidence.kind)) verifyEvaluatedResult(evidence)
}
function verifyEvaluatedResult(evidence: WatchlistMonitorRow['result']) {
  if (!evidence.assignmentId || !evidence.graphVersionAddress || !evidence.evaluatedAt) throw new ContractError()
}
export function parseWatchlistMonitoringRows(input: unknown, context: WatchlistMonitorContext) {
  const value = object(input, ['schema', 'context', 'rows'])
  if (value.schema !== 'watchlist-monitoring-rows/1' || !Array.isArray(value.rows) || value.rows.length > 32) throw new ContractError()
  contextEcho(value.context, context)
  const rows = value.rows.map(row)
  if (new Set(rows.map((item) => item.memberKey)).size !== rows.length) throw new ContractError()
  return { context, rows }
}
export function parseWatchlistMonitoringRow(input: unknown, context: WatchlistMonitorContext, member: ScopeMember, revision: number) {
  const value = object(input, ['schema', 'context', 'row'])
  if (value.schema !== 'watchlist-monitoring-row/1') throw new ContractError()
  contextEcho(value.context, context)
  const parsed = row(value.row)
  if (parsed.memberKey !== scopeMemberIdentity(parseScopeMember(member)) || parsed.configurationRevision !== revision + 1) throw new ContractError()
  return parsed
}
export function watchlistCommandBody(context: WatchlistMonitorContext, member: ScopeMember, expectedRevision: number,
  operation: 'CONFIGURE' | 'PIN' | 'MONITOR', selection: WatchlistStrategySelection | null, flag: boolean | null) {
  const selected = selection === null ? null : { graph_id: identifier(selection.graphId), graph_version: count(selection.graphVersion, 1), timeframe: timeframe(selection.timeframe) }
  if ((operation === 'CONFIGURE') !== (selected !== null) || (operation === 'CONFIGURE') !== (flag === null)) throw new ContractError()
  return { context: watchlistContextBody(context), member: parseScopeMember(member), command: { operation, expected_revision: count(expectedRevision), selection: selected, flag: nullable(flag, boolean) }, request_id: crypto.randomUUID() }
}
export function createWatchlistMonitorClient(api: StrategyApi): WatchlistMonitorClient {
  return { list: (context, signal) => api.watchlistMonitoringRows(context, signal),
    configure: (context, member, revision, selection, signal) => api.writeWatchlistMonitoringRow(context, member, revision, 'CONFIGURE', selection, null, signal),
    pin: (context, member, revision, flag, signal) => api.writeWatchlistMonitoringRow(context, member, revision, 'PIN', null, flag, signal),
    setMonitoring: (context, member, revision, flag, signal) => api.writeWatchlistMonitoringRow(context, member, revision, 'MONITOR', null, flag, signal) }
}
