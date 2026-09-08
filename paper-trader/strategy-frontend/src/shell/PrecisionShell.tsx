import type { StaticScopeMemberContext } from '../features/static-scopes/staticScopeContracts'
import { NewStrategy } from '../features/presets/NewStrategy'
import { createContext, useContext, useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { flushSync } from 'react-dom'
import { Asterisk, Bell, ChartNoAxesCombined, ChevronLeft, ChevronRight, Database, Folder, GitBranch, Home, Info, LayoutTemplate, List, PanelLeftClose, PanelLeftOpen, RefreshCw, Settings, UserRound, X } from 'lucide-react'
import { errorMessage, type StrategyApi } from './api'
import { providerOnboardingEnabled, type GraphPage, type GraphSummary, type Project, type ReleaseManifest } from './contracts'
import { ResearchWorkspace } from '../research/ResearchWorkspace'
import { TraderSelect } from '../components/TraderSelect'
type Load<T> = { kind: 'loading' } | { kind: 'error'; message: string } | { kind: 'ready'; value: T }
const FrameContext = createContext(false)

export type GlobalPath = '/alerts' | '/settings' | '/' | '/watchlists' | '/portfolio' | '/strategies' | '/presets' | '/account' | '/account/provider'

function GlobalNavigation({ active, onNavigate, staticWatchlists, alerts, providerOnboarding }: { active: string; onNavigate: (path: GlobalPath) => void; staticWatchlists: boolean; alerts: boolean; providerOnboarding: boolean }) {
  return <>
    <button title="Home" aria-label="Home" aria-current={active === 'home' ? 'page' : undefined} onClick={() => onNavigate('/')}><Home size={19} aria-hidden="true" /><span>Home</span></button>
    <button title="Portfolio" aria-label="Portfolio" aria-current={active === 'portfolio' ? 'page' : undefined} onClick={() => onNavigate('/portfolio')}><ChartNoAxesCombined size={19} aria-hidden="true" /><span>Portfolio</span></button>
    <button title="Strategies" aria-label="Strategies"
      aria-current={active === 'strategies' ? 'page' : undefined}
      onClick={() => onNavigate('/strategies')}>
      <GitBranch size={19} aria-hidden="true" /><span>Strategies</span>
    </button>
    {staticWatchlists && <button title="Watchlists" aria-label="Watchlists" aria-current={active === 'watchlists' ? 'page' : undefined} onClick={() => onNavigate('/watchlists')}><List size={19} aria-hidden="true" /><span>Watchlists</span></button>}
    {alerts && <button title="Alerts" aria-label="Alerts" aria-current={active === 'alerts' ? 'page' : undefined} onClick={() => onNavigate('/alerts')}><Bell size={19} aria-hidden="true" /><span>Alerts</span></button>}
    <button title="Presets" aria-label="Presets" aria-current={active === 'presets' ? 'page' : undefined} onClick={() => onNavigate('/presets')}>
      <LayoutTemplate size={19} aria-hidden="true" /><span>Presets</span>
    </button>
    {providerOnboarding && <button title="Data provider" aria-label="Data provider"
      aria-current={active === 'provider' ? 'page' : undefined}
      onClick={() => onNavigate('/account/provider')}>
      <Database size={19} aria-hidden="true" /><span>Data</span>
    </button>}
    <button title="Settings" aria-label="Settings" aria-current={active === 'settings' ? 'page' : undefined} onClick={() => onNavigate('/settings')}><Settings size={19} aria-hidden="true" /><span>Settings</span></button>
    <button title="Account" aria-label="Account"
      aria-current={active === 'account' ? 'page' : undefined}
      onClick={() => onNavigate('/account')}>
      <UserRound size={19} aria-hidden="true" /><span>Account</span>
    </button>
  </>
}

export function PrecisionFrame({ api, active, onNavigate, children, overlay, providerOnboarding = false, staticWatchlists = false, alerts = false, context }: {
  api: StrategyApi
  active: 'alerts' | 'settings' | 'home' | 'watchlists' | 'portfolio' | 'strategies' | 'presets' | 'account' | 'provider'
  onNavigate: (path: GlobalPath) => void
  children: ReactNode
  overlay?: ReactNode
  staticWatchlists?: boolean
  alerts?: boolean
  providerOnboarding?: boolean
  context?: Readonly<{ project?: string; graph?: string }>
}) {
  const nested = useContext(FrameContext)
  const [collapsed, setCollapsed] = useState(false)
  const mainContent = useRef<HTMLElement>(null)
  const navigation = <GlobalNavigation active={active} onNavigate={onNavigate} staticWatchlists={staticWatchlists} alerts={alerts} providerOnboarding={providerOnboarding} />
  if (nested) return <>{children}{overlay}</>
  return <FrameContext.Provider value={true}><div className={`slate-shell${collapsed ? ' slate-shell--collapsed' : ''}`} data-product-surface="precision-slate">
    <a className="slate-skip" href="#main-content" onClick={(event) => {
      event.preventDefault()
      window.history.replaceState(
        window.history.state,
        '',
        `${window.location.pathname}${window.location.search}#main-content`,
      )
      mainContent.current?.focus()
    }}>Skip to content</a>
    <aside id="global-sidebar" className="slate-sidebar">
      <div className="slate-brand"><Asterisk size={22} aria-hidden="true" /><span>STRATEGY <b>OS</b></span>
        <button className="slate-collapse" onClick={() => setCollapsed(!collapsed)} aria-label={collapsed ? 'Expand navigation' : 'Collapse navigation'} title={collapsed ? 'Expand navigation' : 'Collapse navigation'} aria-expanded={!collapsed} aria-controls="global-sidebar">
          {collapsed ? <PanelLeftOpen size={18} aria-hidden="true" /> : <PanelLeftClose size={18} aria-hidden="true" />}
        </button>
      </div>
      <nav aria-label="Global navigation">{navigation}</nav>
      {context && <section className="slate-sidebar-context" aria-label="Current workspace"><span>Current workspace</span><strong>{context.project ?? 'Strategies'}</strong>{context.graph && <small>{context.graph}</small>}</section>}
      <div className="slate-sidebar-utilities">
        <button className="slate-refresh" onClick={() => api.recheck()} aria-label="Refresh access and records"><RefreshCw size={18} aria-hidden="true" /><span>Refresh</span></button>
      </div>
    </aside>
    <div className="slate-body">
      <main ref={mainContent} id="main-content" className="slate-content" tabIndex={-1}>{children}</main>
    </div>
    <nav className="slate-mobile-nav" aria-label="Mobile navigation">{navigation}</nav>
    {overlay}
  </div></FrameContext.Provider>
}

function LoadMessage({ state, retry, children }: { state: Load<unknown>; retry: () => void; children: ReactNode }) {
  if (state.kind === 'loading') return <p className="slate-state" role="status">{children}</p>
  if (state.kind === 'error') return <div className="slate-state"><p role="alert">{state.message}</p><button onClick={retry}>Retry</button></div>
  return null
}

function Graphs({ api, project, onSelect }: { api: StrategyApi; project: Project; onSelect: (graph: GraphSummary) => void }) {
  const [cursors, setCursors] = useState<(string | null)[]>([null])
  const [pageChanged, setPageChanged] = useState(false)
  const after = cursors.at(-1) ?? null
  return <GraphList key={after ?? 'first'} api={api} project={project} after={after} onSelect={onSelect} restoreFocus={pageChanged}
    onNext={(cursor) => { setPageChanged(true); setCursors([...cursors, cursor]) }}
    onPrevious={cursors.length > 1 ? () => { setPageChanged(true); setCursors(cursors.slice(0, -1)) } : undefined} />
}

function GraphList({ api, project, after, onSelect, onNext, onPrevious, restoreFocus }: {
  api: StrategyApi; project: Project; after: string | null; onSelect: (graph: GraphSummary) => void
  onNext: (cursor: string) => void; onPrevious?: () => void
  restoreFocus: boolean
}) {
  const [state, setState] = useState<Load<GraphPage>>({ kind: 'loading' })
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    api.graphs(project.project_id, after, controller.signal).then((value) => {
      if (!controller.signal.aborted) setState({ kind: 'ready', value })
    }).catch((error: unknown) => {
      if (!controller.signal.aborted) setState({ kind: 'error', message: errorMessage(error) })
    })
    return () => controller.abort()
  }, [api, project.project_id, after, attempt])
  const title = useRef<HTMLHeadingElement>(null)
  useEffect(() => { if (restoreFocus) title.current?.focus() }, [restoreFocus])
  return <section aria-label="Project strategies" className="slate-registry">
    <div className="slate-section-heading"><h2 ref={title} tabIndex={-1}>Saved graphs</h2><span>Read only</span></div>
    <LoadMessage state={state} retry={() => { setState({ kind: 'loading' }); setAttempt(attempt + 1) }}>Loading graphs…</LoadMessage>
    {state.kind === 'ready' && <>
      {state.value.items.length === 0 ? <div className="slate-state"><h3>{after === null ? 'No graphs in this project' : 'No more graphs'}</h3><p>{after === null ? 'No saved graphs were returned for this project.' : 'The project may have changed since the previous page.'}</p></div> : <>
        <div className="slate-list-head" aria-hidden="true"><span>Strategy graph</span><span>Draft revision</span><span>Published version</span><span /></div>
        <ul className="slate-graph-list">{state.value.items.map((graph) => <li key={graph.identifier}>
          <button className="slate-graph-row" onClick={() => onSelect(graph)} aria-label={`Open ${graph.display_name}`}>
            <span className="slate-graph-name"><GitBranch size={19} aria-hidden="true" /><span><strong>{graph.display_name}</strong></span></span>
            <span><small className="slate-mobile-label">Draft revision</small>{graph.draft_revision}</span>
            <span><small className="slate-mobile-label">Published version</small>{graph.current_version ?? 'Not published'}</span>
            <ChevronRight size={16} aria-hidden="true" />
          </button>
        </li>)}</ul>
      </>}
      <div className="slate-pagination">
        {onPrevious && <button onClick={onPrevious}><ChevronLeft size={15} aria-hidden="true" />Previous graphs</button>}
        {state.value.next_cursor !== null && <button onClick={() => onNext(state.value.next_cursor!)}>Next graphs<ChevronRight size={15} aria-hidden="true" /></button>}
      </div>
    </>}
  </section>
}

function GraphFacts({ graph, project }: { graph: GraphSummary; project: Project }) {
  return <dl className="slate-facts">
    <div><dt>Project</dt><dd>{project.name}</dd></div>
    <div><dt>Saved version</dt><dd>{graph.current_version ?? 'Not saved yet'}</dd></div>
  </dl>
}

function ContextDrawer({ project, graph, onClose }: { project: Project; graph: GraphSummary; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    const element = dialog.current
    element?.showModal()
    return () => element?.close()
  }, [])
  return <dialog ref={dialog} className="slate-drawer" aria-labelledby="context-title" onClose={(event) => { if (!event.currentTarget.open) onClose() }}>
    <header><h2 id="context-title">Strategy context</h2><button autoFocus aria-label="Close context" onClick={() => dialog.current?.close()}><X size={18} aria-hidden="true" /></button></header>
    <h3>{graph.display_name}</h3>
    <GraphFacts project={project} graph={graph} />
  </dialog>
}

type RouteSelection = Readonly<{ projectId?: string; graphId?: string; view?: 'build' | 'backtest' }>
type AttributedGraphLoad =
  | { kind: 'idle' }
  | { kind: 'loading' | 'error'; projectId: string; graphId: string; message?: string }
  | { kind: 'ready'; projectId: string; graphId: string; value: GraphSummary }

function CreateProject({ api, onCreated }: { api: StrategyApi; onCreated: (project: Project) => void }) {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [pending, setPending] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const submit = async (event: FormEvent) => {
    event.preventDefault(); setPending(true); setMessage(null)
    try {
      const project = await api.createProject(name, description, new AbortController().signal)
      onCreated(project); setName(''); setDescription(''); setOpen(false)
    } catch (error) { setMessage(errorMessage(error)) } finally { setPending(false) }
  }
  if (!open) return <button onClick={() => setOpen(true)}>Create project</button>
  return <form className="research-form slate-create-form" onSubmit={(event) => void submit(event)}>
    <label>Project name<input required maxLength={128} value={name} onChange={(event) => setName(event.target.value)} /></label>
    <label>Description<textarea maxLength={4000} value={description} onChange={(event) => setDescription(event.target.value)} /></label>
    <div><button disabled={pending}>{pending ? 'Creating…' : 'Create project'}</button><button type="button" onClick={() => setOpen(false)}>Cancel</button></div>
    {message && <p role="alert">{message}</p>}
  </form>
}

function attributedGraphState(state: AttributedGraphLoad, projectId: string, graphId: string): Load<GraphSummary> {
  if (state.kind === 'idle' || state.projectId !== projectId || state.graphId !== graphId) return { kind: 'loading' }
  if (state.kind === 'ready') return { kind: 'ready', value: state.value }
  if (state.kind === 'error') return { kind: 'error', message: state.message ?? 'This graph could not be loaded.' }
  return { kind: 'loading' }
}

function ProjectArea({ api, projects, manifest, restoreFocus, selection, scopeContext, onNavigate, onGlobalNavigate, onProjectCreated }: {
  api: StrategyApi; projects: readonly Project[]; manifest: ReleaseManifest; restoreFocus: boolean; scopeContext?: StaticScopeMemberContext
  selection?: RouteSelection; onNavigate?: (projectId?: string, graphId?: string) => void
  onGlobalNavigate: (path: GlobalPath) => void
  onProjectCreated: (project: Project) => void
}) {
  const [localProjectId, setLocalProjectId] = useState('')
  const [localGraph, setLocalGraph] = useState<GraphSummary | null>(null)
  const [routeGraphLoad, setRouteGraphLoad] = useState<AttributedGraphLoad>({ kind: 'idle' })
  const [graphAttempt, setGraphAttempt] = useState(0)
  const [contextOpen, setContextOpen] = useState(false)
  const projectId = selection?.projectId ?? localProjectId
  const graphId = selection?.graphId
  const project = projects.find((item) => item.project_id === projectId)
  const currentRouteGraphLoad = onNavigate && project && graphId
    ? attributedGraphState(routeGraphLoad, project.project_id, graphId) : null
  // Route attribution is checked during render, before effects. A prior graph can
  // never commit under a new URL/project picker identity.
  const graph = onNavigate
    ? currentRouteGraphLoad?.kind === 'ready' ? currentRouteGraphLoad.value : null
    : localGraph
  const heading = useRef<HTMLHeadingElement>(null)
  const previousGraph = useRef<GraphSummary | null>(null)
  useEffect(() => { if (restoreFocus) heading.current?.focus() }, [restoreFocus])
  const go = (nextProjectId?: string, nextGraphId?: string) => {
    flushSync(() => {
      setContextOpen(false)
      // Clear attributed graph bytes before the browser URL can move. This also
      // prevents late research-panel state from committing under a new route.
      setRouteGraphLoad({ kind: 'idle' })
      setLocalGraph(null)
    })
    if (onNavigate) onNavigate(nextProjectId, nextGraphId)
    else { setLocalProjectId(nextProjectId ?? ''); setLocalGraph(nextGraphId ? graph : null) }
  }
  const openGraph = (next: GraphSummary) => {
    if (onNavigate) go(project?.project_id, next.identifier)
    else { setLocalGraph(next); setContextOpen(false) }
  }
  useEffect(() => {
    if (!onNavigate || !project || !graphId) return
    const controller = new AbortController()
    void (async () => {
      try {
        let after: string | null = null
        for (let pageNumber = 0; pageNumber < 20; pageNumber += 1) {
          const page = await api.graphs(project.project_id, after, controller.signal)
          const match = page.items.find((item) => item.identifier === graphId)
          if (match) {
            if (!controller.signal.aborted) setRouteGraphLoad({ kind: 'ready', projectId: project.project_id, graphId, value: match })
            return
          }
          if (page.next_cursor === null) break
          after = page.next_cursor
        }
        if (!controller.signal.aborted) setRouteGraphLoad({ kind: 'error', projectId: project.project_id, graphId,
          message: 'This graph is unavailable in the selected project. Return to the project strategy list.' })
      } catch (error) {
        if (!controller.signal.aborted) setRouteGraphLoad({ kind: 'error', projectId: project.project_id, graphId, message: errorMessage(error) })
      }
    })()
    return () => controller.abort()
  }, [api, project, graphId, onNavigate, graphAttempt])
  useEffect(() => {
    if (graph || previousGraph.current) heading.current?.focus()
    previousGraph.current = graph
  }, [graph])
  const strategies = () => go(project?.project_id)
  const allStrategies = () => go()
  function renderHeading() {
    return <div className="slate-heading">{graph && <button className="slate-strategy-back" onClick={strategies} aria-label="All strategies" title="All strategies"><ChevronLeft size={18} aria-hidden="true" /></button>}<div><h1 ref={heading} tabIndex={-1}>{graph ? graph.display_name : 'Strategies'}</h1>{!graph && <p>Your ideas, saved as strategies. Start fresh or explore a preset.</p>}</div>
          {!graph && <NewStrategy api={api} projectId={project?.project_id} onCreated={(createdProject, identifier) => { go(createdProject, identifier) }} onPresets={() => onGlobalNavigate('/presets')} />}
          {graph && <button onClick={() => setContextOpen(true)}><Info size={17} aria-hidden="true" />Context</button>}
        </div>
  }
  function renderContents() {
    return projects.length === 0 ? <section className="slate-state"><h2>No projects available</h2><p>Create a project to organize your strategies.</p><CreateProject api={api} onCreated={(created) => { onProjectCreated(created); go(created.project_id) }} /></section>
          : projectId && !project ? <section className="slate-state"><h2>Project unavailable</h2><p role="alert">This project is not available in the verified workspace.</p><button onClick={allStrategies}>Return to Strategies</button></section>
          : !project ? <section className="slate-state"><h2>Select a project</h2><p>Choose where you want to work.</p></section>
          : graphId && currentRouteGraphLoad?.kind !== 'ready' ? <section className="slate-state"><h2>Strategy record</h2><LoadMessage state={currentRouteGraphLoad ?? { kind: 'loading' }} retry={() => {
            setRouteGraphLoad({ kind: 'loading', projectId: project.project_id, graphId }); setGraphAttempt((value) => value + 1)
          }}>Loading strategy…</LoadMessage>{currentRouteGraphLoad?.kind === 'error' && <button onClick={strategies}>Return to project strategies</button>}</section>
          : graph ? <>
          {!['ENABLED', 'ENABLED_WITH_LIMIT'].includes(manifest.capabilities.backtesting.state) && <p className="slate-note">Backtesting is unavailable in this version. You can continue building your strategy.</p>}
          <div className="slate-overview"><ResearchWorkspace api={api} project={project} graph={graph} scopeContext={scopeContext} initialView={selection?.view}
            backtestEnabled={['ENABLED', 'ENABLED_WITH_LIMIT'].includes(manifest.capabilities.backtesting.state)}
            reviewEnabled={['ENABLED', 'ENABLED_WITH_LIMIT'].includes(manifest.capabilities.research_review.state)}
            onPublished={() => setGraphAttempt((value) => value + 1)} /></div>
        </> : <>{project.description && <p className="slate-description">{project.description}</p>}<div className="slate-section-heading"><h2>Project strategies</h2></div><Graphs key={project.project_id} api={api} project={project} onSelect={openGraph} /></>
  }
  return <PrecisionFrame api={api} active="strategies" onNavigate={onGlobalNavigate}
    providerOnboarding={providerOnboardingEnabled(manifest)}
    context={{ project: project?.name, graph: graph?.display_name }}
    overlay={contextOpen && project && graph ? <ContextDrawer project={project} graph={graph} onClose={() => setContextOpen(false)} /> : undefined}>
        <section className={graph ? 'slate-strategy-workspace' : 'slate-strategy-library'}>
        <header className="slate-workspace-header">{renderHeading()}
        <div className="slate-project-picker"><Folder size={18} aria-hidden="true" /><label htmlFor="project-picker">Project</label>
          <TraderSelect id="project-picker" label="Project" value={projectId} disabled={projects.length === 0} onValueChange={(value) => go(value || undefined)}
            options={[{ value: '', label: 'Select a project', disabled: true }, ...projects.map((item) => ({ value: item.project_id, label: item.name }))]} />
        </div></header>
        {renderContents()}
        </section>
  </PrecisionFrame>
}

export function PrecisionShell({ api, manifest, restoreFocus = false, selection, scopeContext, onNavigate, onGlobalNavigate }: {
  api: StrategyApi; manifest: ReleaseManifest; restoreFocus?: boolean; scopeContext?: StaticScopeMemberContext
  selection?: RouteSelection; onNavigate?: (projectId?: string, graphId?: string) => void
  onGlobalNavigate: (path: GlobalPath) => void
}) {
  const [state, setState] = useState<Load<readonly Project[]>>({ kind: 'loading' })
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    setState({ kind: 'loading' })
    api.projects(controller.signal).then((value) => {
      if (!controller.signal.aborted) setState({ kind: 'ready', value })
    }).catch((error: unknown) => {
      if (!controller.signal.aborted) setState({ kind: 'error', message: errorMessage(error) })
    })
    return () => controller.abort()
  }, [api, attempt, selection?.projectId])
  if (state.kind !== 'ready') return <PrecisionFrame api={api} active="strategies" onNavigate={onGlobalNavigate} providerOnboarding={providerOnboardingEnabled(manifest)}><section className="slate-state"><span className="slate-eyebrow">Strategies</span><h1>Project access</h1><LoadMessage state={state} retry={() => { setState({ kind: 'loading' }); setAttempt(attempt + 1) }}>Loading projects…</LoadMessage></section></PrecisionFrame>
  return <ProjectArea api={api} manifest={manifest} scopeContext={scopeContext} projects={state.value} restoreFocus={restoreFocus} selection={selection} onNavigate={onNavigate}
    onGlobalNavigate={onGlobalNavigate}
    onProjectCreated={(project) => setState({ kind: 'ready', value: Object.freeze([...state.value, project]) })} />
}
