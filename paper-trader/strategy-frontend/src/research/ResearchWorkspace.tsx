import { TraderSelect } from '../components/TraderSelect'
import { providerReferenceLabel } from '../features/connections/dataConnectionClient'
import { scopeMembers, scopeLabels, scopeMemberIdentity, watchlistMemberCandidates, type StaticScope, type StaticScopeMemberContext, type StaticScopePage } from '../features/static-scopes/staticScopeContracts'
import { lazy, Suspense, useEffect, useMemo, useRef, useState, type CSSProperties, type PointerEvent, type ReactNode } from 'react'
import { History, LoaderCircle, Maximize2, Minimize2, RotateCcw } from 'lucide-react'
import { ApiError, errorMessage, type StrategyApi } from '../shell/api'
import type { ExperimentRun, GraphSummary, Project, PublishedGraph, ResearchDataset, ReviewTimeline } from '../shell/contracts'
import './research-workstation.css'
import './build-studio.css'
import { ResearchSeriesChart } from './ResearchSeriesChart'
import { MarketContext } from '../features/chart-context/MarketContext'
import { SettingsWorkspace } from './SettingsWorkspace'

const StrategyBuilderWorkspace = lazy(() => import('./StrategyBuilderWorkspace').then((module) => ({ default: module.StrategyBuilderWorkspace })))
const BacktestWorkspace = lazy(() => import('./BacktestWorkspace').then((module) => ({ default: module.BacktestWorkspace })))

type Load<T> = { kind: 'loading' } | { kind: 'error'; message: string } | { kind: 'ready'; value: T }
type Tab = 'overview' | 'build' | 'backtest' | 'review' | 'settings'

function State<T>({ state, retry, children }: { state: Load<T>; retry: () => void; children: (value: T) => ReactNode }) {
  if (state.kind === 'loading') return <p className="workstation-state" role="status"><LoaderCircle aria-hidden="true" />Loading records…</p>
  if (state.kind === 'error') return <div className="workstation-state"><p role="alert">{state.message}</p><button onClick={retry}>Retry</button></div>
  return <>{children(state.value)}</>
}

function useLoad<T>(load: (signal: AbortSignal) => Promise<T>, key: string): [Load<T>, () => void] {
  const [attempt, setAttempt] = useState(0); const [state, setState] = useState<Load<T>>({ kind: 'loading' })
  useEffect(() => { const controller = new AbortController(); setState({ kind: 'loading' }); load(controller.signal).then((value) => { if (!controller.signal.aborted) setState({ kind: 'ready', value }) })
    .catch((error: unknown) => { if (!controller.signal.aborted) setState({ kind: 'error', message: errorMessage(error) }) }); return () => controller.abort()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, attempt]); return [state, () => setAttempt((value) => value + 1)]
}

function Overview({ api, project, graph }: { api: StrategyApi; project: Project; graph: GraphSummary }) {
  const [versions, retryVersions] = useLoad(async (signal) => graph.current_version === null ? [] : [await api.v2Version(project.project_id, graph.identifier, graph.current_version, signal)], `${graph.identifier}:${graph.current_version}`)
  const [runs, retryRuns] = useLoad((signal) => api.experiments(project.project_id, signal), project.project_id)
  const graphRuns = useMemo(() => runs.kind === 'ready' ? runs.value.runs.filter((run) => run.graph.identifier === graph.identifier) : [], [graph.identifier, runs])
  return <section className="overview-plane" aria-labelledby="overview-title"><header><h2 id="overview-title">Overview</h2><p>Your saved versions and backtest history.</p></header>
    <div className="overview-columns"><section><h3>Strategy</h3><p>{graph.display_name}</p>
      <p>{project.name}</p><p>Draft revision {graph.draft_revision} · {graph.current_version === null ? 'No saved version' : `Saved version ${graph.current_version}`}</p></section>
      <section><h3>Saved version</h3><State state={versions} retry={retryVersions}>{(items) => items.length ? <ol className="evidence-list">{items.map((item) => { const row = item as Record<string, unknown>; return <li key={String(row.graph_version)}><strong>Version {String(row.graph_version)}</strong></li> })}</ol> : <p>Save a version in Build when you are ready to backtest.</p>}</State></section>
      <section><h3>Backtest history</h3><State state={runs} retry={retryRuns}>{() => graphRuns.length ? <ol className="evidence-list">{graphRuns.map((run: ExperimentRun) => <li key={run.run_id}><strong>Run {run.run_id}</strong><span>{run.status}</span><span>Version {run.graph.version} · {run.evidence_state === 'verified' ? 'Result verified' : 'Result not verified'}</span></li>)}</ol> : <p>No backtests yet for this strategy.</p>}</State></section></div>
  </section>
}

function Review({ api, project }: { api: StrategyApi; project: Project }) {
  const [review, retry] = useLoad((signal) => api.review(project.project_id, signal), project.project_id)
  return <section className="review-plane" aria-labelledby="review-title"><header><span className="slate-eyebrow">Research-only timeline</span><h2 id="review-title">Review evidence</h2></header><State state={review} retry={retry}>{(value: ReviewTimeline) => <>{value.source_errors.length > 0 && <p role="alert">Some evidence sources are unavailable: {value.source_errors.join(', ')}</p>}{value.events.length ? <ol className="review-timeline">{value.events.map((event) => <li key={event.event_id}><History aria-hidden="true" /><div><strong>{event.summary}</strong><span>{event.type} · {event.status}</span><time>{event.occurred_at ?? 'Time unavailable'}</time></div></li>)}</ol> : <p>No review event is persisted for this project.</p>}</>}</State></section>
}

type WorkspaceProps = {
  api: StrategyApi; project: Project; graph: GraphSummary; backtestEnabled: boolean; reviewEnabled: boolean
  onPublished: (published: PublishedGraph) => void; scopeContext?: StaticScopeMemberContext; initialView?: 'build' | 'backtest'
}

type StudioPane = 'runs' | 'chart' | 'builder'

function StudioDivider({ axis, value, onChange }: { axis: 'columns' | 'rows'; value: number; onChange: (value: number) => void }) {
  const start = useRef<{ coordinate: number; value: number; size: number } | null>(null)
  const change = (next: number) => onChange(Math.max(20, Math.min(70, next)))
  const coordinate = (event: PointerEvent) => axis === 'columns' ? event.clientX : event.clientY
  return <div className={`studio-divider studio-divider--${axis}`} role="separator" tabIndex={0} aria-label={axis === 'columns' ? 'Lists pane width' : 'Chart pane height'} aria-orientation={axis === 'columns' ? 'vertical' : 'horizontal'} aria-valuemin={20} aria-valuemax={70} aria-valuenow={Math.round(value)}
    onPointerDown={(event) => { if (event.button !== 0) return; const box = event.currentTarget.parentElement!.getBoundingClientRect(); start.current = { coordinate: coordinate(event), value, size: axis === 'columns' ? box.width : box.height }; event.currentTarget.setPointerCapture(event.pointerId); event.preventDefault() }}
    onPointerMove={(event) => { const origin = start.current; if (origin && origin.size > 0) change(origin.value + (coordinate(event) - origin.coordinate) / origin.size * 100) }}
    onPointerUp={() => { start.current = null }} onPointerCancel={() => { start.current = null }} onLostPointerCapture={() => { start.current = null }}
    onKeyDown={(event) => { const moves: Record<string, number> = axis === 'columns' ? { ArrowLeft: -2, ArrowRight: 2 } : { ArrowUp: -2, ArrowDown: 2 }; if (event.key === 'Home') { event.preventDefault(); change(20) } else if (event.key === 'End') { event.preventDefault(); change(70) } else if (moves[event.key]) { event.preventDefault(); change(value + moves[event.key]) } }} />
}

function StudioRunChart({ api, projectId, run }: { api: StrategyApi; projectId: string; run: ExperimentRun }) {
  const [mode, setMode] = useState<'results' | 'price'>('results')
  const [result, retry] = useLoad((signal) => api.visualization(projectId, run.run_id, 0, signal), `${projectId}:${run.run_id}`)
  return <><p className="studio-run-context">Run {run.run_id} · Saved version {run.graph.version}{run.dataset_bindings.length > 0 && ` · ${[...new Set(run.dataset_bindings.map((binding) => binding.interval))].join(', ')}`}</p>
    <nav aria-label="Studio chart view"><button aria-pressed={mode === 'results'} onClick={() => setMode('results')}>Results</button><button aria-pressed={mode === 'price'} onClick={() => setMode('price')}>Price</button></nav>
    <State state={result} retry={retry}>{(value) => value.state === 'AVAILABLE' ? mode === 'price' ? <MarketContext api={api} projectId={projectId} runId={run.run_id} tradeEvents={value.series.trade_events} /> : <ResearchSeriesChart equity={value.series.net_equity.points} drawdown={value.series.drawdown.points} events={value.series.trade_events} /> : <p role="status">{value.state === 'PENDING' ? 'This run is still being prepared. Refresh runs after it finishes.' : 'This run has no persisted chart. Choose another run or open Backtest to inspect its evidence.'}</p>}</State>
  </>
}

function useStudioWatchlists(api: StrategyApi, projectId: string, after: string | null) {
  type Value = { page: StaticScopePage; datasets: readonly ResearchDataset[] }
  const [attempt, setAttempt] = useState(0)
  const [stored, setStored] = useState<{ api: StrategyApi; key: string; state: Load<Value> }>({ api, key: '', state: { kind: 'loading' } })
  const key = `${projectId}/${after ?? ''}/${attempt}`
  useEffect(() => {
    const controller = new AbortController(); setStored({ api, key, state: { kind: 'loading' } })
    async function load() {
      const page = await api.staticScopes(projectId, after, false, controller.signal)
      const datasets = page.items.length ? await api.researchDatasets(projectId, controller.signal) : []
      if (!controller.signal.aborted) setStored({ api, key, state: { kind: 'ready', value: { page, datasets } } })
    }
    void load().catch((error: unknown) => { if (!controller.signal.aborted) setStored({ api, key, state: { kind: 'error', message: error instanceof ApiError && error.kind === 'manifest' ? 'Static watchlists are not available in this server release.' : errorMessage(error) } }) })
    return () => controller.abort()
  }, [api, projectId, after, key])
  const state: Load<Value> = stored.api === api && stored.key === key ? stored.state : { kind: 'loading' }
  return { state, retry: () => setAttempt((value) => value + 1) }
}

function memberBacktestReason(project: Project, graph: GraphSummary, enabled: boolean, dataset: ResearchDataset | undefined) {
  if (!enabled) return 'Backtesting is unavailable in this server release.'
  if (project.status !== 'active') return 'This project is archived. Use an active project for a new backtest.'
  if (graph.current_version === null) return 'Save a strategy version in Build before opening a member backtest.'
  if (!dataset) return 'Choose history for the selected member.'
  if (dataset.asset_class === 'INDEX' || dataset.research_compatibility === 'BENCHMARK_INPUT_ONLY') return 'This index is a benchmark input. Choose equity history for the primary backtest input.'
  if (dataset.asset_class !== 'EQUITY' || dataset.backtest_eligibility !== 'ELIGIBLE_Q03') return 'This history is unavailable for a primary backtest. Review compatible equity history in Backtest.'
  return null
}

function StudioScopeMembers({ scope, datasets, project, graph, backtestEnabled, onBacktest }: {
  scope: StaticScope; datasets: readonly ResearchDataset[]; project: Project; graph: GraphSummary; backtestEnabled: boolean; onBacktest: (context: StaticScopeMemberContext) => void
}) {
  const [member, setMember] = useState(''), [datasetId, setDatasetId] = useState('')
  const candidates = watchlistMemberCandidates(datasets, scopeLabels(scope))
  const selected = candidates.find((item) => scopeMemberIdentity(item.member) === member && scopeMembers(scope).some((pointer) => scopeMemberIdentity(pointer) === member))
  const dataset = selected?.datasets.find((item) => item.manifest_address === datasetId)
  const reason = selected?.member.kind === 'PROVIDER_REFERENCE' ? 'This instrument is saved. Backtests need verified instrument details and compatible historical data.' : memberBacktestReason(project, graph, backtestEnabled, dataset)
  function openMember() {
    if (reason || !dataset || !selected?.label || selected.member.kind !== 'CANONICAL' || graph.current_version === null) return
    const context: StaticScopeMemberContext = { schema: 'static-scope-member-context/1', project_id: project.project_id,
      graph_id: graph.identifier, graph_version: graph.current_version, scope_id: scope.scope_id, revision: scope.snapshot.revision,
      address: scope.address, membership_address: scope.membership_address, instrument_address: selected.member.instrument_address, dataset_manifest_address: dataset.manifest_address }
    onBacktest(context)
  }
  return <div className="studio-scope-members"><p>{scope.name} · Revision {scope.snapshot.revision}</p><ul aria-label="Watchlist members">{scopeMembers(scope).map((pointer) => {
    const address = scopeMemberIdentity(pointer), candidate = candidates.find((item) => scopeMemberIdentity(item.member) === address)
    return <li key={address}><button disabled={!candidate?.label} aria-pressed={member === address} onClick={() => { setMember(address); setDatasetId('') }}>{candidate?.label ?? 'Instrument name unavailable'}</button>{pointer.kind === 'PROVIDER_REFERENCE' ? <small>Saved instrument · Not ready for research{candidate?.provider_reference && ` · ${providerReferenceLabel(candidate.provider_reference)}`}</small> : !candidate?.datasets.length && <small>No owned history available.</small>}</li>
  })}</ul><label>Member history<TraderSelect label="Member history" value={datasetId} disabled={!selected?.label} onValueChange={setDatasetId} options={[{ value: '', label: 'Choose historical data' }, ...(selected?.datasets.map((item) => ({ value: item.manifest_address, label: `${item.interval} · ${item.bar_count} bars · ${item.event_start.slice(0, 10)} to ${item.event_end.slice(0, 10)}` })) ?? [])]} /></label>
    {reason && <p className="studio-member-reason">{reason}</p>}<button disabled={Boolean(reason) || !selected?.label} onClick={openMember}>Open member Backtest</button><p className="studio-member-note">Opens this saved strategy and one member's history. It does not run the watchlist.</p>
  </div>
}

function StudioWatchlists({ api, project, graph, backtestEnabled, onBacktest }: {
  api: StrategyApi; project: Project; graph: GraphSummary; backtestEnabled: boolean; onBacktest: (context: StaticScopeMemberContext) => void
}) {
  const [cursors, setCursors] = useState<(string | null)[]>([null]), [selected, setSelected] = useState('')
  const after = cursors.at(-1) ?? null
  const { state, retry } = useStudioWatchlists(api, project.project_id, after)
  function page(change: (current: (string | null)[]) => (string | null)[]) { setSelected(''); setCursors(change) }
  return <div className="studio-watchlists"><button onClick={() => { setSelected(''); retry() }}>Refresh watchlists</button><State state={state} retry={retry}>{({ page: values, datasets }) => {
    const scope = values.items.find((item) => item.scope_id === selected)
    return <>{values.items.length ? <label>Saved watchlist<TraderSelect label="Saved watchlist" value={selected} onValueChange={setSelected} options={[{ value: '', label: 'Choose a watchlist' }, ...values.items.map((item) => ({ value: item.scope_id, label: `${item.name} · ${item.snapshot.members.length} members` }))]} /></label> : <p>No saved watchlists in this project. Create one from your provider or owned history in Watchlists.</p>}
      <div className="studio-watchlist-pages">{cursors.length > 1 && <button onClick={() => page((current) => current.slice(0, -1))}>Previous watchlists</button>}{values.next_cursor && <button onClick={() => page((current) => [...current, values.next_cursor])}>Next watchlists</button>}</div>
      {scope && <StudioScopeMembers key={scope.address} scope={scope} datasets={datasets} project={project} graph={graph} backtestEnabled={backtestEnabled} onBacktest={onBacktest} />}
    </>
  }}</State></div>
}

function BuildStudio({ api, project, graph, onPublished, backtestEnabled, onMemberBacktest }: WorkspaceProps & { onMemberBacktest: (context: StaticScopeMemberContext) => void }) {
  const [runs, retry] = useLoad((signal) => api.experiments(project.project_id, signal), `${project.project_id}:${graph.current_version}`)
  const [selected, setSelected] = useState<number | null>(null)
  const [leftView, setLeftView] = useState<'runs' | 'watchlists'>('runs')
  const [expanded, setExpanded] = useState<StudioPane | null>(null)
  const [left, setLeft] = useState(24), [top, setTop] = useState(45)
  const graphRuns = runs.kind === 'ready' ? runs.value.runs.filter((run) => run.graph.identifier === graph.identifier) : []
  const run = graphRuns.find((item) => item.run_id === selected)
  const maximize = (pane: StudioPane) => <button aria-label={`${expanded === pane ? 'Restore' : 'Maximize'} ${pane === 'runs' ? leftView : pane} pane`} aria-pressed={expanded === pane} onClick={() => setExpanded(expanded === pane ? null : pane)}>{expanded === pane ? <Minimize2 size={14} aria-hidden="true" /> : <Maximize2 size={14} aria-hidden="true" />}</button>
  return <section className="build-studio" aria-label="Build studio">
    <div className="studio-panes" data-expanded={expanded ?? undefined} style={{ '--studio-left': `${left}%`, '--studio-top': `${top}%` } as CSSProperties}>
      <aside className="studio-pane studio-runs" hidden={expanded !== null && expanded !== 'runs'} aria-label="Studio watchlists and runs"><header><nav className="studio-left-tabs" aria-label="Studio lists"><button aria-pressed={leftView === 'runs'} onClick={() => setLeftView('runs')}>Runs</button><button aria-pressed={leftView === 'watchlists'} onClick={() => setLeftView('watchlists')}>Watchlists</button></nav><div className="studio-pane-actions"><button onClick={() => { setLeft(24); setTop(45); setExpanded(null) }} aria-label="Reset panes" title="Reset pane layout"><RotateCcw size={14} aria-hidden="true" /></button>{maximize('runs')}</div></header>
        {leftView === 'watchlists' ? <StudioWatchlists api={api} project={project} graph={graph} backtestEnabled={backtestEnabled} onBacktest={onMemberBacktest} /> : <><button onClick={retry}>Refresh runs</button><State state={runs} retry={retry}>{() => graphRuns.length ? <ol>{graphRuns.map((item) => <li key={item.run_id}><button aria-label={`Run ${item.run_id} Version ${item.graph.version} · ${item.status}`} aria-pressed={selected === item.run_id} onClick={() => setSelected(item.run_id)}><strong>Run {item.run_id}</strong><span>Version {item.graph.version} · {item.status}</span></button></li>)}</ol> : <p>No backtests yet for this strategy. Save a version, then open Backtest to select your data.</p>}</State></>}
      </aside>
      {!expanded && <StudioDivider axis="columns" value={left} onChange={setLeft} />}
      <section className="studio-pane studio-chart" hidden={expanded !== null && expanded !== 'chart'} aria-label="Studio chart"><header><h2>Chart</h2>{maximize('chart')}</header>{run ? <StudioRunChart key={run.run_id} api={api} projectId={project.project_id} run={run} /> : <p>Select a run to inspect its recorded price context and results. Unsaved draft edits do not change earlier results.</p>}</section>
      {!expanded && <StudioDivider axis="rows" value={top} onChange={setTop} />}
      <section className="studio-pane studio-builder" hidden={expanded !== null && expanded !== 'builder'} aria-label="Studio builder"><header>{maximize('builder')}</header><Suspense fallback={<p role="status" className="workstation-state">Loading builder…</p>}><StrategyBuilderWorkspace api={api} project={project} graph={graph} onPublished={onPublished} /></Suspense></section>
    </div>
  </section>
}

function requestedTab(view: WorkspaceProps['initialView'], backtestEnabled: boolean, fromWatchlist: boolean): Tab | undefined {
  if (fromWatchlist && backtestEnabled) return 'backtest'
  if (view === 'build') return 'build'
  if (view === 'backtest' && backtestEnabled) return 'backtest'
}

function ResearchWorkspaceBody({ api, project, graph, backtestEnabled, reviewEnabled, onPublished, scopeContext, initialView }: WorkspaceProps) {
  const [memberSelection, setMemberSelection] = useState<{ source: StaticScopeMemberContext | undefined; context: StaticScopeMemberContext } | null>(null)
  const selectedScope = memberSelection && memberSelection.source === scopeContext ? memberSelection.context : scopeContext
  const requested = requestedTab(initialView, backtestEnabled, Boolean(scopeContext))
  const [tab, setTab] = useState<Tab>(() => requested ?? (graph.current_version === null ? 'build' : 'overview'))
  useEffect(() => { if (requested) setTab(requested) }, [requested])
  const tabs = ([['overview', 'Overview'], ['build', 'Build'], ['settings', 'Settings'], ...(backtestEnabled ? [['backtest', 'Backtest']] : []), ...(reviewEnabled ? [['review', 'Review']] : [])] as [Tab, string][])
  return <div className="research-workspace"><nav className="research-tabs" aria-label="Selected strategy sections">{tabs.map(([id, label]) => <button key={id} aria-current={tab === id ? 'page' : undefined} onClick={() => setTab(id)}>{label}</button>)}</nav>
    {tab === 'overview' && <Overview api={api} project={project} graph={graph} />}
    {tab === 'build' && <BuildStudio api={api} project={project} graph={graph} onPublished={onPublished} backtestEnabled={backtestEnabled} reviewEnabled={reviewEnabled} onMemberBacktest={(context) => { setMemberSelection({ source: scopeContext, context }); setTab('backtest') }} />}
    {tab === 'settings' && <SettingsWorkspace api={api} currentVersion={graph.current_version} strategy={{ projectId: project.project_id, graphId: graph.identifier }} onPublished={onPublished} onEditSignals={() => setTab('build')} onBacktest={backtestEnabled ? () => setTab('backtest') : undefined} />}
    {tab === 'backtest' && backtestEnabled && <Suspense fallback={<p role="status" className="workstation-state">Loading backtest…</p>}><BacktestWorkspace api={api} project={project} graph={graph} scopeContext={selectedScope} onPublished={(version) => { onPublished?.(version); setTab('build') }} onOpenBuilder={() => setTab('build')} /></Suspense>}
    {tab === 'review' && reviewEnabled && <Review api={api} project={project} />}
  </div>
}


export function ResearchWorkspace(props: WorkspaceProps) {
  return <ResearchWorkspaceBody key={`${props.project.project_id}:${props.graph.identifier}`} {...props} />
}
