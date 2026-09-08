import { ContractError, type ResearchDataset } from '../../shell/contracts'
import { canonicalJson, contentAddress } from '../../shell/contentAddress'
import { parseProviderReference, providerObservedAt, providerReferenceLabel, type ProviderInstrumentReference } from '../connections/dataConnectionClient'

function record(input: unknown): Record<string, unknown> {
  if (!input || typeof input !== 'object' || Array.isArray(input)) throw new ContractError()
  return input as Record<string, unknown>
}
function keys(input: Record<string, unknown>, expected: readonly string[]) {
  if (Object.keys(input).length !== expected.length || expected.some((key) => !Object.hasOwn(input, key))) throw new ContractError()
}
function text(input: unknown, limit = 128): string {
  if (typeof input !== 'string' || !input.trim() || input !== input.trim() || input.length > limit || /[\u0000-\u001f]/.test(input)) throw new ContractError()
  return input
}
function address(input: unknown): string {
  const value = text(input, 71)
  if (!/^sha256:[a-f0-9]{64}$/.test(value)) throw new ContractError()
  return value
}
function revision(input: unknown): number {
  if (!Number.isSafeInteger(input) || Number(input) < 1) throw new ContractError()
  return Number(input)
}
function scopeId(input: unknown): string {
  const value = text(input, 64)
  if (!/^scope\.[A-Za-z0-9][A-Za-z0-9._-]{0,57}$/.test(value)) throw new ContractError()
  return value
}
function members(input: unknown): readonly string[] {
  if (!Array.isArray(input) || input.length < 1 || input.length > 32) throw new ContractError()
  const values = input.map(address)
  if (values.some((value, index) => index > 0 && values[index - 1] >= value)) throw new ContractError()
  return Object.freeze(values)
}
export type ScopeMember = Readonly<{ kind: 'CANONICAL'; instrument_address: string }>
  | Readonly<{ kind: 'PROVIDER_REFERENCE'; selection_address: string }>
export type ScopeMemberLabel = Readonly<{ instrument_address: string; display_name: string | null }>
export type TypedScopeMemberLabel = Readonly<{ member: ScopeMember; display_name: string | null;
  provider_reference: ProviderInstrumentReference | null; observed_at: string | null }>
type SnapshotIdentity = Readonly<{ owner_id: string; project_id: string; scope_id: string; revision: number; predecessor: string | null }>
type SnapshotV1 = SnapshotIdentity & Readonly<{ schema: 'static-instrument-scope/1'; members: readonly string[] }>
type SnapshotV2 = SnapshotIdentity & Readonly<{ schema: 'static-instrument-scope/2'; members: readonly ScopeMember[] }>
type ScopeIdentity = Readonly<{ scope_id: string; name: string; status: 'active' | 'archived'; current_revision: number; address: string; membership_address: string }>
export type StaticScope = ScopeIdentity & (Readonly<{ snapshot: SnapshotV1; member_labels: readonly ScopeMemberLabel[] }>
  | Readonly<{ snapshot: SnapshotV2; member_labels: readonly TypedScopeMemberLabel[] }>)
export function scopeMemberAddress(member: ScopeMember): string {
  return member.kind === 'CANONICAL' ? member.instrument_address : member.selection_address
}
export function scopeMemberIdentity(member: ScopeMember): string {
  return `${member.kind}:${scopeMemberAddress(member)}`
}
export function parseScopeMember(input: unknown): ScopeMember {
  const value = record(input)
  if (value.kind === 'CANONICAL') {
    keys(value, ['kind', 'instrument_address'])
    return Object.freeze({ kind: 'CANONICAL', instrument_address: address(value.instrument_address) })
  }
  if (value.kind === 'PROVIDER_REFERENCE') {
    keys(value, ['kind', 'selection_address'])
    return Object.freeze({ kind: 'PROVIDER_REFERENCE', selection_address: address(value.selection_address) })
  }
  throw new ContractError()
}
function typedMembers(input: unknown): readonly ScopeMember[] {
  if (!Array.isArray(input) || input.length < 1 || input.length > 32) throw new ContractError()
  const selected = input.map(parseScopeMember)
  const identifiers = selected.map(scopeMemberIdentity)
  if (identifiers.some((value, index) => index > 0 && identifiers[index - 1] >= value)) throw new ContractError()
  return Object.freeze(selected)
}
async function digest(value: Record<string, unknown>) {
  try { return await contentAddress(value) }
  catch { throw new ContractError() }
}
function snapshot(input: unknown, projectId: string, id: string): SnapshotV1 | SnapshotV2 {
  const value = record(input)
  keys(value, ['schema', 'owner_id', 'project_id', 'scope_id', 'revision', 'predecessor', 'members'])
  if (value.project_id !== projectId || value.scope_id !== id) throw new ContractError()
  const version = revision(value.revision)
  const predecessor = value.predecessor === null ? null : address(value.predecessor)
  if ((version === 1) !== (predecessor === null)) throw new ContractError()
  const identity = { owner_id: text(value.owner_id, 64), project_id: projectId, scope_id: id, revision: version, predecessor }
  if (value.schema === 'static-instrument-scope/1') return Object.freeze({ ...identity, schema: value.schema, members: members(value.members) })
  if (value.schema === 'static-instrument-scope/2') return Object.freeze({ ...identity, schema: value.schema, members: typedMembers(value.members) })
  throw new ContractError()
}
function selectedRevision(selected: number, current: number, expected?: number) {
  if (selected !== (expected ?? current) || selected > current) throw new ContractError()
}
function memberLabels(input: unknown, selected: readonly string[]): readonly ScopeMemberLabel[] {
  if (!Array.isArray(input) || input.length !== selected.length) throw new ContractError()
  return Object.freeze(input.map((item, index) => {
    const value = record(item)
    keys(value, ['instrument_address', 'display_name'])
    if (address(value.instrument_address) !== selected[index]) throw new ContractError()
    return Object.freeze({ instrument_address: selected[index], display_name: value.display_name === null ? null : text(value.display_name, 256) })
  }))
}
function typedMemberLabel(input: unknown, expected: ScopeMember): TypedScopeMemberLabel {
  const value = record(input)
  keys(value, ['member', 'display_name', 'provider_reference', 'observed_at'])
  const member = parseScopeMember(value.member)
  if (scopeMemberIdentity(member) !== scopeMemberIdentity(expected)) throw new ContractError()
  const display_name = value.display_name === null ? null : text(value.display_name, 512)
  if (member.kind === 'CANONICAL') {
    if (value.provider_reference !== null || value.observed_at !== null) throw new ContractError()
    return Object.freeze({ member, display_name, provider_reference: null, observed_at: null })
  }
  try {
    return Object.freeze({ member, display_name, provider_reference: parseProviderReference(value.provider_reference), observed_at: providerObservedAt(value.observed_at) })
  } catch { throw new ContractError() }
}
function typedMemberLabels(input: unknown, selected: readonly ScopeMember[]): readonly TypedScopeMemberLabel[] {
  if (!Array.isArray(input) || input.length !== selected.length) throw new ContractError()
  return Object.freeze(input.map((item, index) => typedMemberLabel(item, selected[index])))
}
export async function parseStaticScope(input: unknown, projectId: string, expectedId?: string, expectedRevision?: number): Promise<StaticScope> {
  text(projectId, 64)
  const value = record(input)
  keys(value, ['scope_id', 'name', 'status', 'current_revision', 'address', 'membership_address', 'snapshot', 'member_labels'])
  const id = scopeId(value.scope_id), current = revision(value.current_revision)
  if (expectedId !== undefined && id !== expectedId) throw new ContractError()
  const status = value.status
  if (status !== 'active' && status !== 'archived') throw new ContractError()
  const selected = snapshot(value.snapshot, projectId, id)
  selectedRevision(selected.revision, current, expectedRevision)
  const membershipSchema = selected.schema === 'static-instrument-scope/1' ? 'static-instrument-membership/1' : 'static-instrument-membership/2'
  const hashes = await Promise.all([digest(selected), digest({ schema: membershipSchema, members: selected.members })])
  if (address(value.address) !== hashes[0] || address(value.membership_address) !== hashes[1]) throw new ContractError()
  const identity: ScopeIdentity = { scope_id: id, name: text(value.name), status, current_revision: current, address: hashes[0], membership_address: hashes[1] }
  if (selected.schema === 'static-instrument-scope/1') return Object.freeze({ ...identity, snapshot: selected, member_labels: memberLabels(value.member_labels, selected.members) })
  return Object.freeze({ ...identity, snapshot: selected, member_labels: typedMemberLabels(value.member_labels, selected.members) })
}
export function scopeMembers(scope: StaticScope): readonly ScopeMember[] {
  return scope.snapshot.schema === 'static-instrument-scope/1'
    ? scope.snapshot.members.map((instrument_address) => ({ kind: 'CANONICAL' as const, instrument_address })) : scope.snapshot.members
}
export function scopeLabels(scope: StaticScope): readonly TypedScopeMemberLabel[] {
  return scope.member_labels.map((item) => 'member' in item ? item : {
    member: { kind: 'CANONICAL' as const, instrument_address: item.instrument_address }, display_name: item.display_name, provider_reference: null, observed_at: null })
}
export function hasCanonicalScopeMember(scope: StaticScope, instrumentAddress: string): boolean {
  return scopeMembers(scope).some((member) => member.kind === 'CANONICAL' && member.instrument_address === instrumentAddress)
}

export async function parseStaticScopePage(input: unknown, projectId: string, after: string | null) {
  const value = record(input)
  keys(value, ['items', 'next_cursor'])
  if (!Array.isArray(value.items) || value.items.length > 50) throw new ContractError()
  const items = await Promise.all(value.items.map((item) => parseStaticScope(item, projectId)))
  if (items.some((item, index) => item.scope_id <= (index ? items[index - 1].scope_id : after ?? ''))) throw new ContractError()
  const next_cursor = value.next_cursor === null ? null : scopeId(value.next_cursor)
  if (next_cursor !== null && (items.length !== 50 || next_cursor !== items.at(-1)?.scope_id)) throw new ContractError()
  return Object.freeze({ items: Object.freeze(items), next_cursor })
}
export type StaticScopePage = Awaited<ReturnType<typeof parseStaticScopePage>>
export type ScopeDraft = Readonly<{ name: string; members: readonly string[] | readonly ScopeMember[] }>
export type ScopeWrite =
  | Readonly<{ kind: 'create'; scopeId: string; draft: ScopeDraft }>
  | Readonly<{ kind: 'revise'; scopeId: string; draft: ScopeDraft; base: StaticScope }>
  | Readonly<{ kind: 'archive'; scopeId: string; base: StaticScope }>

export function scopeWriteOutcome(intent: ScopeWrite, value: StaticScope): 'saved' | 'retry' | 'conflict' {
  if (value.scope_id !== intent.scopeId || value.snapshot.revision !== value.current_revision) throw new ContractError()
  if (intent.kind === 'create') return value.current_revision === 1 && value.status === 'active' && sameDraft(intent.draft, value) ? 'saved' : 'conflict'
  return existingWriteOutcome(intent, value)
}
function existingWriteOutcome(intent: Exclude<ScopeWrite, { kind: 'create' }>, value: StaticScope): 'saved' | 'retry' | 'conflict' {
  if (value.snapshot.owner_id !== intent.base.snapshot.owner_id || value.snapshot.project_id !== intent.base.snapshot.project_id) throw new ContractError()
  if (value.current_revision === intent.base.current_revision && value.address === intent.base.address) return unchangedWriteOutcome(intent, value)
  if (intent.kind === 'revise') return revisedWriteOutcome(intent, value)
  return 'conflict'
}
function unchangedWriteOutcome(intent: Exclude<ScopeWrite, { kind: 'create' }>, value: StaticScope): 'saved' | 'retry' | 'conflict' {
  if (intent.kind === 'archive' && value.status === 'archived') return 'saved'
  return value.status === 'active' ? 'retry' : 'conflict'
}
function revisedWriteOutcome(intent: Extract<ScopeWrite, { kind: 'revise' }>, value: StaticScope): 'saved' | 'conflict' {
  return value.status === 'active' && value.current_revision === intent.base.current_revision + 1
    && value.snapshot.predecessor === intent.base.address && sameDraft(intent.draft, value) ? 'saved' : 'conflict'
}
function sameDraft(draft: ScopeDraft, value: StaticScope) {
  const sorted = [...draft.members].sort((left, right) => {
    const a = typeof left === 'string' ? left : scopeMemberIdentity(left)
    const b = typeof right === 'string' ? right : scopeMemberIdentity(right)
    return a < b ? -1 : a > b ? 1 : 0
  })
  return draft.name === value.name && canonicalJson(sorted) === canonicalJson(value.snapshot.members)
}

function datasetName(item: ResearchDataset): string | null {
  if (item.instrument_display_name) return item.instrument_display_name
  if (item.source_type !== 'USER_SUPPLIED') return null
  const parts = item.canonical_instrument_label.split(' · ')
  return parts.length === 4 && /^[a-f0-9]{12}$/.test(parts[3]) ? parts.slice(0, 3).join(' · ') : null
}
export function instrumentCandidates(datasets: readonly ResearchDataset[]) {
  const byAddress = new Map<string, { address: string; label: string | null; datasets: ResearchDataset[] }>()
  for (const item of datasets) {
    const name = datasetName(item)
    const label = name
    const existing = byAddress.get(item.instrument_address)
    if (existing) { existing.datasets.push(item); if (existing.label !== label) existing.label = null }
    else byAddress.set(item.instrument_address, { address: item.instrument_address, label, datasets: [item] })
  }
  return uniqueCandidateNames([...byAddress.values()])
}
function uniqueCandidateNames(items: { address: string; label: string | null; datasets: ResearchDataset[] }[]) {
  const labels = items.map((item) => item.label)
  return items.map((item) => ({ ...item, label: item.label && labels.indexOf(item.label) === labels.lastIndexOf(item.label) ? item.label : null }))
}

export function watchlistCandidates(datasets: readonly ResearchDataset[], labels: readonly ScopeMemberLabel[]): InstrumentCandidate[] {
  const candidates = instrumentCandidates(datasets)
  const known = new Set(candidates.map((item) => item.address))
  for (const item of labels) {
    if (!known.has(item.instrument_address)) {
      candidates.push({ address: item.instrument_address, label: item.display_name, datasets: [] })
      known.add(item.instrument_address)
    }
  }
  return uniqueCandidateNames(candidates)
}
export type WatchlistMemberCandidate = Readonly<{ member: ScopeMember; label: string | null; datasets: readonly ResearchDataset[];
  provider_reference: ProviderInstrumentReference | null; observed_at: string | null }>
export function watchlistMemberCandidates(datasets: readonly ResearchDataset[], labels: readonly TypedScopeMemberLabel[]): WatchlistMemberCandidate[] {
  const canonicalLabels: ScopeMemberLabel[] = []
  for (const item of labels) if (item.member.kind === 'CANONICAL') canonicalLabels.push({ instrument_address: item.member.instrument_address, display_name: item.display_name })
  const result: WatchlistMemberCandidate[] = watchlistCandidates(datasets, canonicalLabels).map((item) => ({
    member: { kind: 'CANONICAL', instrument_address: item.address }, label: item.label, datasets: item.datasets, provider_reference: null, observed_at: null }))
  for (const item of labels) {
    if (item.member.kind !== 'PROVIDER_REFERENCE') continue
    const selection = item.member.selection_address
    result.push({ member: item.member, label: item.display_name ?? (item.provider_reference ? providerReferenceLabel(item.provider_reference) : null),
      datasets: datasets.filter((dataset) => dataset.provider_selection_address === selection),
      provider_reference: item.provider_reference, observed_at: item.observed_at })
  }
  return result
}
export type InstrumentCandidate = ReturnType<typeof instrumentCandidates>[number]
export type StaticScopeMemberContext = Readonly<{
  schema: 'static-scope-member-context/1'; project_id: string; graph_id: string; graph_version: number
  scope_id: string; revision: number; address: string; membership_address: string; instrument_address: string; dataset_manifest_address: string
}>
export function parseScopeMemberContext(input: unknown, projectId: string, graphId: string): StaticScopeMemberContext {
  const value = record(input)
  keys(value, ['schema', 'project_id', 'graph_id', 'graph_version', 'scope_id', 'revision', 'address', 'membership_address', 'instrument_address', 'dataset_manifest_address'])
  if (value.schema !== 'static-scope-member-context/1' || text(value.project_id, 64) !== projectId || text(value.graph_id) !== graphId) throw new ContractError()
  return Object.freeze({ schema: 'static-scope-member-context/1', project_id: projectId, graph_id: graphId, graph_version: revision(value.graph_version),
    scope_id: scopeId(value.scope_id), revision: revision(value.revision), address: address(value.address), membership_address: address(value.membership_address),
    instrument_address: address(value.instrument_address), dataset_manifest_address: address(value.dataset_manifest_address) })
}
function matchingScopeMember(context: StaticScopeMemberContext, scope: StaticScope, graphVersion: number | null) {
  return graphVersion === context.graph_version && scope.scope_id === context.scope_id && scope.snapshot.project_id === context.project_id
    && scope.address === context.address && scope.membership_address === context.membership_address
    && scope.snapshot.revision === context.revision
}
export function verifyScopeMember(context: StaticScopeMemberContext, scope: StaticScope, datasets: readonly ResearchDataset[], graphVersion: number | null) {
  if (!matchingScopeMember(context, scope, graphVersion)) throw new ContractError()
  const dataset = datasets.find((item) => item.manifest_address === context.dataset_manifest_address)
  if (!dataset || dataset.instrument_address !== context.instrument_address) throw new ContractError()
  const memberMatches = hasCanonicalScopeMember(scope, context.instrument_address) || scopeMembers(scope).some((member) =>
    member.kind === 'PROVIDER_REFERENCE' && member.selection_address === dataset.provider_selection_address)
  if (!memberMatches) throw new ContractError()
  return dataset
}
