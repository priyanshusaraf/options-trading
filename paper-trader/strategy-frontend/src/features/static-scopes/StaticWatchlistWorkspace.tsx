import { TraderSelect } from '../../components/TraderSelect'
import { useEffect, useRef, useState, type FormEvent } from 'react'
import { ApiError, errorMessage, type StrategyApi } from '../../shell/api'
import { ContractError, type GraphSummary, type Project, type ResearchDataset } from '../../shell/contracts'
import type { DataConnectionClient, SavedProviderSelection } from '../connections/dataConnectionClient'
import { ScopeProviderSearch } from './ScopeProviderSearch'
import { WatchlistMonitorTable } from './WatchlistMonitorTable'
import type { WatchlistMonitorClient } from './watchlistMonitorTypes'
import { ProviderHistoryForm, formatIndiaTimestamp, historyCount, historyDatasetLabel } from './ProviderHistoryForm'
import { scopeLabels, scopeMembers, scopeMemberIdentity, watchlistMemberCandidates, scopeWriteOutcome, type ScopeMember, type TypedScopeMemberLabel, type WatchlistMemberCandidate, type ScopeDraft, type ScopeWrite, type StaticScope, type StaticScopeMemberContext, type StaticScopePage } from './staticScopeContracts'
import { providerReferenceLabel } from '../connections/dataConnectionClient'
import './static-scopes.css'

type Draft = { scopeId: string; base: StaticScope | null; name: string; version: 1 | 2; members: readonly ScopeMember[]; labels: readonly TypedScopeMemberLabel[] }
function editDraft(scope: StaticScope): Draft {
  return { scopeId: scope.scope_id, base: scope, name: scope.name, version: scope.snapshot.schema === 'static-instrument-scope/1' ? 1 : 2,
    members: scopeMembers(scope), labels: scopeLabels(scope) }
}
function draftPayload(draft: Draft): ScopeDraft {
  const members = [...draft.members].sort((a, b) => scopeMemberIdentity(a).localeCompare(scopeMemberIdentity(b)))
  if (draft.version === 2) return { name: draft.name.trim(), members }
  return { name: draft.name.trim(), members: members.map((member) => {
    if (member.kind !== 'CANONICAL') throw new ContractError()
    return member.instrument_address
  }) }
}
function includesMember(members: readonly ScopeMember[], member: ScopeMember): boolean {
  return members.some((value) => scopeMemberIdentity(value) === scopeMemberIdentity(member))
}
function draftChoices(candidates: readonly WatchlistMemberCandidate[], members: readonly ScopeMember[]): WatchlistMemberCandidate[] {
  const missing = members.filter((member) => !candidates.some((item) => scopeMemberIdentity(item.member) === scopeMemberIdentity(member)))
  return [...candidates, ...missing.map((member) => ({ member, label: null, datasets: [], provider_reference: null, observed_at: null }))]
}
function memberHistory(item: WatchlistMemberCandidate | undefined): string {
  if (item?.member.kind === 'PROVIDER_REFERENCE' && !item.datasets.length) return 'Saved instrument · Not ready for research'
  return item?.datasets.length ? historyCount(item.datasets.length, 'dataset') : 'No owned history available'
}
type MutationState = { api: StrategyApi; kind: 'idle' | 'busy' | 'uncertain' | 'retry' | 'conflict'; message: string; intent?: ScopeWrite }
function scopeError(error: unknown) {
  if (error instanceof ApiError) {
    if (error.envelope?.code === 'STATIC_SCOPE_INVALID') return 'Check the name and choose 1–32 distinct, identified instruments.'
    if (error.envelope?.code === 'STATIC_SCOPE_CONFLICT') return 'The watchlist name or revision changed. Check the saved state before retrying.'
    if (error.envelope?.code === 'STATIC_SCOPE_NOT_FOUND') return 'This watchlist or project is unavailable in your workspace.'
  }
  return errorMessage(error)
}
async function writeScope(api: StrategyApi, projectId: string, intent: ScopeWrite, signal: AbortSignal) {
  if (intent.kind === 'create') return api.createStaticScope(projectId, intent.scopeId, intent.draft, signal)
  if (intent.kind === 'revise') return api.reviseStaticScope(projectId, intent.scopeId, intent.base.current_revision, intent.draft, signal)
  return api.archiveStaticScope(projectId, intent.scopeId, intent.base.current_revision, signal)
}
async function verifySavedScope(api: StrategyApi, projectId: string, intent: ScopeWrite, receipt: StaticScope, signal: AbortSignal) {
  if (scopeWriteOutcome(intent, receipt) !== 'saved') throw new ContractError()
  const saved = await api.staticScope(projectId, intent.scopeId, receipt.snapshot.revision, signal)
  if (saved.address !== receipt.address || scopeWriteOutcome(intent, saved) !== 'saved') throw new ContractError()
  return saved
}
function saveFailure(api: StrategyApi, intent: ScopeWrite, error: unknown): MutationState {
  const invalid = error instanceof ApiError && error.envelope?.code === 'STATIC_SCOPE_INVALID'
  if (invalid) return { api, kind: 'idle', message: `${scopeError(error)} Your draft is retained.` }
  return { api, kind: 'uncertain', intent, message: `${scopeError(error)} Save status is not confirmed. Check saved state before retrying.` }
}
function recoveryFailure(api: StrategyApi, intent: ScopeWrite, error: unknown): MutationState {
  const absent = intent.kind === 'create' && error instanceof ApiError && error.envelope?.code === 'STATIC_SCOPE_NOT_FOUND'
  if (absent) return { api, kind: 'retry', intent, message: 'No matching watchlist was found. Retry the same create request.' }
  return { api, kind: 'uncertain', intent, message: `${scopeError(error)} Saved state is still unknown.` }
}
function recoveryOutcome(api: StrategyApi, intent: ScopeWrite, outcome: 'retry' | 'conflict'): MutationState {
  return { api, kind: outcome, intent, message: outcome === 'retry' ? 'No matching save is recorded yet. Retry the same save.' : 'The watchlist changed elsewhere. Your draft is retained; load the current list to continue.' }
}
function useScopeMutation(api: StrategyApi, projectId: string, onSaved: (value: StaticScope) => void) {
  const [stored, setStored] = useState<MutationState>({ api, kind: 'idle', message: '' })
  const request = useRef<AbortController | null>(null)
  const complete = useRef(onSaved); complete.current = onSaved
  useEffect(() => () => { request.current?.abort(); request.current = null }, [api, projectId])
  const state = stored.api === api ? stored : { api, kind: 'idle' as const, message: '' }
  function finish(value: StaticScope, message: string) { setStored({ api, kind: 'idle', message }); complete.current(value) }
  async function save(intent: ScopeWrite) {
    if (request.current) return
    const controller = new AbortController(); request.current = controller
    setStored({ api, kind: 'busy', message: 'Saving watchlist…', intent })
    try {
      const receipt = await writeScope(api, projectId, intent, controller.signal)
      const saved = await verifySavedScope(api, projectId, intent, receipt, controller.signal)
      if (!controller.signal.aborted) finish(saved, intent.kind === 'archive' ? 'Watchlist archived.' : `Saved revision ${saved.snapshot.revision}.`)
    } catch (error) {
      if (!controller.signal.aborted) setStored(saveFailure(api, intent, error))
    } finally { if (request.current === controller) request.current = null }
  }
  async function check() {
    const intent = state.intent
    if (!intent || request.current) return
    const controller = new AbortController(); request.current = controller
    setStored({ api, kind: 'busy', message: 'Checking saved state…', intent })
    try {
      const current = await api.staticScope(projectId, intent.scopeId, null, controller.signal)
      const outcome = scopeWriteOutcome(intent, current)
      if (outcome === 'saved') {
        const saved = await verifySavedScope(api, projectId, intent, current, controller.signal)
        if (!controller.signal.aborted) finish(saved, `Confirmed revision ${saved.snapshot.revision}.`)
      } else if (!controller.signal.aborted) setStored(recoveryOutcome(api, intent, outcome))
    } catch (error) {
      if (!controller.signal.aborted) setStored(recoveryFailure(api, intent, error))
    } finally { if (request.current === controller) request.current = null }
  }
  async function loadCurrent() {
    if (!state.intent || request.current) return
    const controller = new AbortController(); request.current = controller
    try {
      const current = await api.staticScope(projectId, state.intent.scopeId, null, controller.signal)
      if (!controller.signal.aborted) finish(current, 'Loaded the current watchlist.')
    } catch (error) { if (!controller.signal.aborted) setStored({ ...state, message: scopeError(error) }) }
    finally { if (request.current === controller) request.current = null }
  }
  return { state, save, check, loadCurrent, locked: Boolean(state.intent) }
}
function MutationStatus({ mutation }: { mutation: ReturnType<typeof useScopeMutation> }) {
  const { state } = mutation
  if (!state.message) return null
  return <div className="scope-feedback"><p role={['uncertain', 'conflict'].includes(state.kind) ? 'alert' : 'status'}>{state.message}</p>
    {(state.kind === 'uncertain' || state.kind === 'retry') && <button onClick={() => void mutation.check()}>Check saved state</button>}
    {state.kind === 'retry' && state.intent && <button onClick={() => void mutation.save(state.intent!)}>Retry same save</button>}
    {state.kind === 'conflict' && <button onClick={() => void mutation.loadCurrent()}>Load current list</button>}
  </div>
}
async function graphChoices(api: StrategyApi, projectId: string, signal: AbortSignal) {
  const graphs: GraphSummary[] = []
  let after: string | null = null
  for (let page = 0; page < 20; page += 1) {
    const result = await api.graphs(projectId, after, signal)
    graphs.push(...result.items)
    if (result.next_cursor === null) return graphs.filter((graph) => graph.current_version !== null)
    after = result.next_cursor
  }
  throw new ContractError()
}
type ProjectData = { api: StrategyApi; page?: StaticScopePage; datasets?: readonly ResearchDataset[]; graphs?: readonly GraphSummary[]; error?: string }
function projectDataLoading(data: ProjectData, api: StrategyApi) {
  return data.api !== api || (!data.page && !data.error)
}
function ScopeProject({ api, project, onBacktest, backtestEnabled, providerClient, monitorClient }: { monitorClient?: WatchlistMonitorClient | null; providerClient?: DataConnectionClient | null; api: StrategyApi; project: Project; onBacktest: (context: StaticScopeMemberContext) => void; backtestEnabled: boolean }) {
  const activeApi = useRef(api); activeApi.current = api
  const [data, setData] = useState<ProjectData>({ api })
  const [cursors, setCursors] = useState<(string | null)[]>([null])
  const [archived, setArchived] = useState(false)
  const [attempt, setAttempt] = useState(0)
  const [selected, setSelected] = useState<StaticScope | null>(null)
  const [draft, setDraft] = useState<Draft | null>(null)
  const [readError, setReadError] = useState('')
  const [readPending, setReadPending] = useState(false)
  const read = useRef<AbortController | null>(null)
  const after = cursors.at(-1) ?? null
  useEffect(() => { setSelected(null); setDraft(null); return () => read.current?.abort() }, [api])
  useEffect(() => {
    const controller = new AbortController(); setData({ api })
    void Promise.all([api.staticScopes(project.project_id, after, archived, controller.signal), api.researchDatasets(project.project_id, controller.signal), graphChoices(api, project.project_id, controller.signal)])
      .then(([page, datasets, graphs]) => { if (!controller.signal.aborted) { setData({ api, page, datasets, graphs }); setSelected((value) => value ?? page.items[0] ?? null) } })
      .catch((error) => { if (!controller.signal.aborted) setData({ api, error: scopeError(error) }) })
    return () => controller.abort()
  }, [api, project.project_id, after, archived, attempt])
  const mutation = useScopeMutation(api, project.project_id, (value) => { setSelected(value); setDraft(null); setAttempt((value) => value + 1) })
  const locked = mutation.locked || readPending
  async function select(id: string, version: number | null = null) {
    read.current?.abort(); const controller = new AbortController(); read.current = controller
    setReadPending(true); setReadError('')
    try {
      const value = await api.staticScope(project.project_id, id, version, controller.signal)
      if (!controller.signal.aborted) { setSelected(value); setDraft(null) }
    } catch (error) { if (!controller.signal.aborted) setReadError(scopeError(error)) }
    finally { if (read.current === controller) { read.current = null; setReadPending(false) } }
  }
  function startDraft() { setDraft({ scopeId: `scope.${crypto.randomUUID().replaceAll('-', '')}`, base: null, name: '', version: 1, members: [], labels: [] }); setReadError('') }
  function saveDraft(event: FormEvent) {
    event.preventDefault()
    if (!draft || locked) return
    const value = draftPayload(draft)
    if (!value.name || !value.members.length || value.members.length > 32) return
    void mutation.save(draft.base ? { kind: 'revise', scopeId: draft.scopeId, base: draft.base, draft: value } : { kind: 'create', scopeId: draft.scopeId, draft: value })
  }
  function addMember(value: SavedProviderSelection) {
    if (!selected || locked || activeApi.current !== api) return
    const next = editDraft(selected), member: ScopeMember = { kind: 'PROVIDER_REFERENCE', selection_address: value.selection_address }
    if (next.members.length >= 32 || includesMember(next.members, member)) return
    next.version = 2; next.members = [...next.members, member]
    void mutation.save({ kind: 'revise', scopeId: selected.scope_id, base: selected, draft: draftPayload(next) })
  }
  function removeMember(member: ScopeMember) {
    if (!selected || locked || activeApi.current !== api) return
    const next = editDraft(selected)
    if (next.members.length <= 1) return
    next.members = next.members.filter((item) => scopeMemberIdentity(item) !== scopeMemberIdentity(member))
    void mutation.save({ kind: 'revise', scopeId: selected.scope_id, base: selected, draft: draftPayload(next) })
  }
  const candidates = watchlistMemberCandidates(data.datasets ?? [], draft?.labels ?? (selected ? scopeLabels(selected) : []))
  return <>
    <MutationStatus mutation={mutation} />
    {project.status === 'archived' && <p>This project is archived. Watchlists are read only.</p>}
    {projectDataLoading(data, api) ? <p role="status">Loading watchlists and owned history…</p> : data.error ? <div><p role="alert">{data.error}</p><button onClick={() => setAttempt((value) => value + 1)}>Retry watchlists</button></div> : <div className="scope-columns">
      <aside aria-label="Saved watchlists"><div className="scope-list-actions"><button disabled={locked || project.status !== 'active'} onClick={startDraft}>New watchlist</button><label><input type="checkbox" checked={archived} disabled={locked} onChange={(event) => { setArchived(event.target.checked); setCursors([null]) }} />Show archived</label></div>
        {data.page!.items.length ? <ul className="scope-list">{data.page!.items.map((scope) => <li key={scope.scope_id}><button aria-label={`Open ${scope.name}`} aria-pressed={selected?.scope_id === scope.scope_id} disabled={locked} onClick={() => void select(scope.scope_id)}><strong>{scope.name}</strong><span>{historyCount(scope.snapshot.members.length, 'instrument')} · Revision {scope.current_revision}{scope.status === 'archived' ? ' · Archived' : ''}</span></button></li>)}</ul> : <p>No watchlists here yet.</p>}
        <div className="scope-pagination">{cursors.length > 1 && <button disabled={locked} onClick={() => setCursors((values) => values.slice(0, -1))}>Previous watchlists</button>}{data.page!.next_cursor && <button disabled={locked} onClick={() => setCursors((values) => [...values, data.page!.next_cursor])}>Next watchlists</button>}</div>
      </aside>
      <section aria-label="Watchlist details">{readPending && <p role="status">Loading saved revision…</p>}{readError && <p role="alert">{readError}</p>}
        {draft ? <ScopeEditor key={draft.scopeId} providerClient={providerClient} draft={draft} candidates={candidates} locked={locked || project.status !== 'active'} onChange={(value) => { if (activeApi.current === api) setDraft(value) }} onSubmit={saveDraft} onDiscard={() => setDraft(null)} /> : selected ? <ScopeDetails api={api} monitorClient={monitorClient} providerClient={providerClient} onAdd={addMember} onRemove={removeMember} onDatasets={(datasets) => { if (activeApi.current === api) setData((value) => ({ ...value, datasets })) }} scope={selected} editable={project.status === 'active'} candidates={candidates} graphs={data.graphs ?? []} locked={locked} onRevision={(version) => void select(selected.scope_id, version)}
          onEdit={() => setDraft(editDraft(selected))}
          onArchive={() => void mutation.save({ kind: 'archive', scopeId: selected.scope_id, base: selected })} onBacktest={onBacktest} backtestEnabled={backtestEnabled} /> : <p>Select a saved watchlist or create one from your data provider or owned history.</p>}
      </section>
    </div>}
  </>
}
function ScopeEditor({ draft, candidates, locked, onChange, onSubmit, onDiscard, providerClient }: { providerClient?: DataConnectionClient | null; draft: Draft; candidates: WatchlistMemberCandidate[]; locked: boolean; onChange: (draft: Draft) => void; onSubmit: (event: FormEvent) => void; onDiscard: () => void }) {
  const heading = useRef<HTMLHeadingElement>(null)
  useEffect(() => { heading.current?.focus() }, [draft.scopeId])
  const choices = draftChoices(candidates, draft.members)
  function addProvider(value: SavedProviderSelection) {
    const member: ScopeMember = { kind: 'PROVIDER_REFERENCE', selection_address: value.selection_address }
    if (locked || draft.members.length >= 32 || includesMember(draft.members, member)) return
    onChange({ ...draft, version: 2, members: [...draft.members, member],
      labels: [...draft.labels.filter((item) => scopeMemberIdentity(item.member) !== scopeMemberIdentity(member)),
        { member, display_name: providerReferenceLabel(value.selection.reference), provider_reference: value.selection.reference, observed_at: value.selection.observed_at }] })
  }
  return <form className="scope-editor" onSubmit={onSubmit}><h2 ref={heading} tabIndex={-1}>{draft.base ? 'Edit watchlist' : 'New watchlist'}</h2><fieldset disabled={locked}><legend className="scope-sr-only">Watchlist members</legend><label>Watchlist name<input required maxLength={128} value={draft.name} onChange={(event) => onChange({ ...draft, name: event.target.value })} /></label>
    <p>Choose 1–32 watchlist members. {draft.members.length} selected.</p>
    {providerClient && <ScopeProviderSearch client={providerClient} disabled={locked || draft.members.length >= 32} onSelected={addProvider} />}
    <div className="scope-member-choices">{choices.map((item) => <label key={scopeMemberIdentity(item.member)}><input type="checkbox"
      checked={includesMember(draft.members, item.member)} disabled={!includesMember(draft.members, item.member) && (!item.label || draft.members.length >= 32)}
      onChange={(event) => onChange({ ...draft, members: event.target.checked ? [...draft.members, item.member] : draft.members.filter((member) => scopeMemberIdentity(member) !== scopeMemberIdentity(item.member)) })} />
      <span>{item.label ?? 'Instrument name unavailable'}{item.member.kind === 'PROVIDER_REFERENCE' && <small>Saved instrument · Not ready for research</small>}</span></label>)}</div>
    {!choices.length && <p>Add an instrument from your data provider, or import daily CSV data in Backtest.</p>}
    <div className="scope-actions"><button disabled={!draft.name.trim() || !draft.members.length}>Save watchlist</button><button type="button" onClick={onDiscard}>Discard draft</button></div>
  </fieldset></form>
}
function savedCandidates(scope: StaticScope, candidates: readonly WatchlistMemberCandidate[]): WatchlistMemberCandidate[] {
  return scopeMembers(scope).map((member) => candidates.find((item) => scopeMemberIdentity(item.member) === scopeMemberIdentity(member))
    ?? { member, label: null, datasets: [], provider_reference: null, observed_at: null })
}
function ScopeDetails({ api, monitorClient, providerClient, onAdd, onRemove, onDatasets, scope, editable, candidates, graphs, locked, onRevision, onEdit, onArchive, onBacktest, backtestEnabled }: {
  api: StrategyApi; monitorClient?: WatchlistMonitorClient | null; providerClient?: DataConnectionClient | null;
  onAdd: (value: SavedProviderSelection) => void; onRemove: (member: ScopeMember) => void;
  onDatasets: (datasets: readonly ResearchDataset[]) => void; scope: StaticScope; editable: boolean; candidates: WatchlistMemberCandidate[];
  graphs: readonly GraphSummary[]; locked: boolean; onRevision: (version: number) => void; onEdit: () => void; onArchive: () => void;
  onBacktest: (context: StaticScopeMemberContext) => void; backtestEnabled: boolean
}) {
  const heading = useRef<HTMLHeadingElement>(null), history = useRef<HTMLDetailsElement>(null)
  useEffect(() => { heading.current?.focus() }, [scope.address])
  const [version, setVersion] = useState(String(scope.snapshot.revision))
  const [member, setMember] = useState(''), [datasetId, setDatasetId] = useState(''), [graphId, setGraphId] = useState('')
  useEffect(() => { setVersion(String(scope.snapshot.revision)); setMember(''); setDatasetId(''); if (history.current) history.current.open = false }, [scope.address])
  const members = savedCandidates(scope, candidates)
  const selected = members.find((item) => scopeMemberIdentity(item.member) === member)
  const current = editable && scope.snapshot.revision === scope.current_revision && scope.status === 'active'
  function details(pointer: ScopeMember) {
    setMember(scopeMemberIdentity(pointer)); setDatasetId('')
    if (history.current) history.current.open = true
  }
  return <div className="scope-details"><header><h2 ref={heading} tabIndex={-1}>{scope.name}</h2>
    <span>{historyCount(members.length, 'instrument')}{scope.status === 'archived' ? ' · Archived' : ''}</span></header>
    <div className="scope-actions"><details className="scope-inline-add"><summary>Add instrument</summary>
      {providerClient ? <ScopeProviderSearch key={scope.address} client={providerClient} disabled={locked || !current || members.length >= 32} onSelected={onAdd} />
        : <p>Connect your data account to search and add instruments. You can also use Edit current list to add owned history.</p>}</details>
      <button disabled={locked || !current} onClick={onEdit}>Edit current list</button></div>
    <WatchlistMonitorTable api={api} client={monitorClient} context={{ projectId: scope.snapshot.project_id, scopeId: scope.scope_id,
      scopeRevision: scope.snapshot.revision, scopeAddress: scope.address, membershipAddress: scope.membership_address }}
      members={members} graphs={graphs} locked={locked} readOnly={!current} onDetails={details} onRemove={onRemove} canRemove={current && members.length > 1} />
    <details className="scope-secondary" ref={history}><summary>History and research details{selected?.label ? ` · ${selected.label}` : ''}</summary>
      {selected ? <><p>{memberHistory(selected)}</p>{selected.observed_at && <p>Saved snapshot observed {formatIndiaTimestamp(selected.observed_at)}</p>}
        {selected.member.kind === 'PROVIDER_REFERENCE' && <ProviderHistoryForm key={`${scope.address}:${selected.member.selection_address}`}
          api={api} projectId={scope.snapshot.project_id} selectionAddress={selected.member.selection_address} disabled={locked || !editable || scope.status !== 'active'}
          onSaved={(receipt, datasets) => { onDatasets(datasets); if (receipt) setDatasetId(receipt.item.manifest_address) }} />}
        <ScopeResearchControls scope={scope} selected={selected} graphs={graphs} locked={locked} backtestEnabled={backtestEnabled}
          datasetId={datasetId} graphId={graphId} onDataset={setDatasetId} onGraph={setGraphId} onBacktest={onBacktest} /></>
        : <p>Choose an instrument row to inspect its history or open a backtest.</p>}
    </details>
    <details className="scope-secondary"><summary>Watchlist history and settings</summary>
      <div className="scope-actions"><label>Saved revision<input type="number" min={1} max={scope.current_revision} value={version} disabled={locked} onChange={(event) => setVersion(event.target.value)} /></label>
        <button disabled={locked || !Number.isSafeInteger(Number(version)) || Number(version) < 1 || Number(version) > scope.current_revision} onClick={() => onRevision(Number(version))}>Open revision</button>
        <button disabled={locked || !current} onClick={onArchive}>Archive watchlist</button></div>
      {scope.snapshot.revision !== scope.current_revision && <p>Showing saved members from revision {scope.snapshot.revision}. The list name is current.</p>}
    </details>
  </div>
}
function ScopeResearchControls({ scope, selected, graphs, locked, backtestEnabled, datasetId, graphId, onDataset, onGraph, onBacktest }: {
  scope: StaticScope; selected: WatchlistMemberCandidate | undefined; graphs: readonly GraphSummary[]; locked: boolean; backtestEnabled: boolean;
  datasetId: string; graphId: string; onDataset: (value: string) => void; onGraph: (value: string) => void; onBacktest: (context: StaticScopeMemberContext) => void
}) {
  const dataset = selected?.datasets.find((item) => item.manifest_address === datasetId)
  const graph = graphs.find((item) => item.identifier === graphId && item.current_version !== null)
  function openBacktest() {
    if (!backtestEnabled || !selected?.label || !dataset || !graph || graph.current_version === null) return
    onBacktest({ schema: 'static-scope-member-context/1', project_id: scope.snapshot.project_id, graph_id: graph.identifier, graph_version: graph.current_version,
      scope_id: scope.scope_id, revision: scope.snapshot.revision, address: scope.address, membership_address: scope.membership_address,
      instrument_address: dataset.instrument_address, dataset_manifest_address: dataset.manifest_address })
  }
  return <>
    {selected?.member.kind === 'PROVIDER_REFERENCE' && !selected.datasets.length && <p role="status">This instrument is saved. Backtests need verified instrument details and compatible historical data.</p>}
    <div className="scope-research"><h3>Research one member</h3><label>Historical dataset<TraderSelect label="Historical dataset" value={datasetId} disabled={locked || !selected?.label} onValueChange={onDataset} options={[{ value: '', label: 'Choose history for the selected member' }, ...(selected?.datasets.map((item) => ({ value: item.manifest_address, label: historyDatasetLabel(item) })) ?? [])]} /></label>
      <label>Saved strategy<TraderSelect label="Saved strategy" value={graphId} disabled={locked} onValueChange={onGraph} options={[{ value: '', label: 'Choose a saved strategy version' }, ...graphs.map((item) => ({ value: item.identifier, label: `${item.display_name} · Version ${item.current_version}` }))]} /></label>
      <button disabled={locked || !backtestEnabled || !selected?.label || !dataset || !graph} onClick={openBacktest}>Open Backtest</button><p>{backtestEnabled ? 'Backtest requires owned history for the selected member. This opens one member with the selected history. It does not run the whole watchlist or start monitoring.' : 'Backtesting is not available in this server release.'}</p>
    </div>
  </>
}

export function StaticWatchlistWorkspace({ api, enabled, projectId, onProject, onBacktest, backtestEnabled, providerClient, monitorClient }: { monitorClient?: WatchlistMonitorClient | null; providerClient?: DataConnectionClient | null; api: StrategyApi; enabled: boolean; projectId?: string; onProject: (projectId: string) => void; onBacktest: (context: StaticScopeMemberContext) => void; backtestEnabled: boolean }) {
  if (!enabled) return <section className="scope-workspace"><h1>Watchlists</h1><p role="status">Static watchlists are not available in this server release.</p></section>
  return <EnabledWatchlists api={api} projectId={projectId} onProject={onProject} onBacktest={onBacktest} backtestEnabled={backtestEnabled} providerClient={providerClient} monitorClient={monitorClient} />
}
function EnabledWatchlists({ api, projectId, onProject, onBacktest, backtestEnabled, providerClient, monitorClient }: { monitorClient?: WatchlistMonitorClient | null; providerClient?: DataConnectionClient | null; api: StrategyApi; projectId?: string; onProject: (projectId: string) => void; onBacktest: (context: StaticScopeMemberContext) => void; backtestEnabled: boolean }) {
  const [state, setState] = useState<{ api: StrategyApi; projects?: readonly Project[]; error?: string }>({ api })
  const [attempt, setAttempt] = useState(0)
  useEffect(() => { const controller = new AbortController(); setState({ api }); void api.projects(controller.signal).then((projects) => { if (!controller.signal.aborted) setState({ api, projects }) }).catch((error) => { if (!controller.signal.aborted) setState({ api, error: scopeError(error) }) }); return () => controller.abort() }, [api, attempt])
  const selected = state.projects?.find((project) => project.project_id === (projectId ?? state.projects?.[0]?.project_id))
  return <section className="scope-workspace"><h1>Watchlists</h1>{state.api !== api || (!state.projects && !state.error) ? <p role="status">Loading projects…</p> : state.error ? <div><p role="alert">{state.error}</p><button onClick={() => setAttempt((value) => value + 1)}>Retry projects</button></div> : <>
    <label className="scope-project">Project<TraderSelect label="Project" value={selected?.project_id ?? ''} onValueChange={onProject} options={[{ value: '', label: 'Select a project', disabled: true }, ...state.projects!.map((project) => ({ value: project.project_id, label: project.name }))]} /></label>
    {selected ? <ScopeProject key={selected.project_id} providerClient={providerClient} monitorClient={monitorClient} api={api} project={selected} onBacktest={onBacktest} backtestEnabled={backtestEnabled} /> : <p>{projectId ? 'This project is unavailable in your workspace.' : 'Create a project in Strategies before saving a watchlist.'}</p>}
  </>}</section>
}
