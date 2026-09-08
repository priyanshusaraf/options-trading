import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowUpRight, FilePenLine, FolderOpen, LayoutTemplate, Plus } from 'lucide-react'
import { useBrowserIdentity } from '../../auth/AuthGate'
import { errorMessage, type StrategyApi } from '../../shell/api'
import type { ExperimentRun, BrowserIdentity, GraphSummary, Project, ResearchDataset } from '../../shell/contracts'
import './home-workspace.css'

type HomeStrategy = { projectId: string; projectName: string; graph: GraphSummary; draft: 'unfinished' | 'saved' | 'unavailable' }
type HomeProject = { project: Project; strategies: HomeStrategy[]; runs: readonly ExperimentRun[] | null; datasets: readonly ResearchDataset[] | null; unavailable: string[]; moreStrategies: boolean }
type HomeRecords = { projects: HomeProject[]; projectCount: number }
type NextStep = { strategy: HomeStrategy; title: string; detail: string; action: string; view: 'build' | 'backtest' }
const MAX_PROJECTS = 3
const MAX_STRATEGIES = 3

function strategyPath(strategy: HomeStrategy, view?: NextStep['view']) {
  const path = `/strategies/${encodeURIComponent(strategy.projectId)}/${encodeURIComponent(strategy.graph.identifier)}`
  return view ? `${path}?view=${view}` : path
}
async function loadDraft(api: StrategyApi, project: Project, graph: GraphSummary, signal: AbortSignal): Promise<HomeStrategy> {
  const strategy = { projectId: project.project_id, projectName: project.name, graph }
  try {
    const draft = await api.v2Draft(project.project_id, graph.identifier, signal)
    if (draft.project_id !== project.project_id || draft.graph_identifier !== graph.identifier) throw new Error('Mismatched draft')
    return { ...strategy, graph: { ...graph, display_name: draft.document.metadata.name, draft_revision: draft.semantic_revision, current_version: draft.current_version },
      draft: draft.current_version === null || draft.published_revision !== draft.semantic_revision ? 'unfinished' : 'saved' }
  } catch { return { ...strategy, draft: 'unavailable' } }
}
function projectRuns(result: PromiseSettledResult<Awaited<ReturnType<StrategyApi['experiments']>>>, projectId: string) {
  if (result.status !== 'fulfilled') return null
  return result.value.runs.every((run) => run.graph.project_id === projectId) ? result.value.runs : null
}
function projectGraphPage(result: PromiseSettledResult<Awaited<ReturnType<StrategyApi['graphs']>>>, projectId: string) {
  return result.status === 'fulfilled' && result.value.project_id === projectId ? result.value : null
}
function unavailableParts(page: unknown, runs: readonly ExperimentRun[] | null, datasets: PromiseSettledResult<unknown>, strategies: HomeStrategy[]) {
  return [!page && 'Strategies', runs === null && 'Backtests', datasets.status === 'rejected' && 'History', strategies.some((row) => row.draft === 'unavailable') && 'Draft details'].filter(Boolean) as string[]
}
function hasMoreStrategies(page: Awaited<ReturnType<StrategyApi['graphs']>> | null) {
  return Boolean(page && (page.next_cursor !== null || page.items.length > MAX_STRATEGIES))
}
async function loadProject(api: StrategyApi, project: Project, signal: AbortSignal): Promise<HomeProject> {
  const [graphs, runs, datasets] = await Promise.allSettled([
    Promise.resolve().then(() => api.graphs(project.project_id, null, signal)),
    Promise.resolve().then(() => api.experiments(project.project_id, signal)),
    Promise.resolve().then(() => api.researchDatasets(project.project_id, signal)),
  ])
  const page = projectGraphPage(graphs, project.project_id)
  const strategies = await Promise.all((page?.items ?? []).slice(0, MAX_STRATEGIES).map((graph) => loadDraft(api, project, graph, signal)))
  const verifiedRuns = projectRuns(runs, project.project_id)
  const unavailable = unavailableParts(page, verifiedRuns, datasets, strategies)
  return { project, strategies, runs: verifiedRuns, datasets: datasets.status === 'fulfilled' ? datasets.value : null, unavailable,
    moreStrategies: hasMoreStrategies(page) }
}
async function loadHome(api: StrategyApi, signal: AbortSignal): Promise<HomeRecords> {
  const projects = (await api.projects(signal)).filter((project) => project.status === 'active')
  return { projects: await Promise.all(projects.slice(0, MAX_PROJECTS).map((project) => loadProject(api, project, signal))), projectCount: projects.length }
}
function runsFor(strategy: HomeStrategy, runs: readonly ExperimentRun[]) {
  return runs.filter((run) => run.graph.identifier === strategy.graph.identifier).toSorted((a, b) => b.run_id - a.run_id)
}
function primaryHistory(dataset: ResearchDataset) {
  return dataset.backtest_eligibility === 'ELIGIBLE_Q03' && dataset.asset_class === 'EQUITY' && (dataset.research_compatibility === undefined || dataset.research_compatibility === 'PRIMARY_BACKTEST')
}
function runStep(strategy: HomeStrategy, run: ExperimentRun): NextStep {
  const base = { strategy, view: 'backtest' as const }
  if (run.status === 'pending' || run.status === 'running') return { ...base, title: 'Check your research', detail: `Run ${run.run_id} is ${run.status === 'pending' ? 'queued' : 'running'}. Open Backtest to follow its progress.`, action: 'Check backtest' }
  if (run.evidence_state === 'corrupt') return { ...base, title: 'Review a result issue', detail: `Run ${run.run_id} could not be verified. Open Backtest to review the recorded issue.`, action: 'Review backtests' }
  if (run.status === 'failed') return { ...base, title: 'Review an unfinished run', detail: `Run ${run.run_id} failed. Review its reason before starting another run.`, action: 'Review backtests' }
  return { ...base, title: 'Review your research', detail: `Run ${run.run_id} used version ${run.graph.version}. Review its evidence before changing the strategy.`, action: 'Review backtests' }
}
function nextStep(strategy: HomeStrategy, project: HomeProject): NextStep {
  const base = { strategy, view: 'build' as const }
  if (strategy.draft === 'unfinished') return { ...base, title: 'Continue your draft', detail: 'Your draft is saved. Continue editing, then save a version when you are ready to backtest.', action: 'Resume draft' }
  if (strategy.draft === 'unavailable') return { ...base, title: 'Open your strategy', detail: 'Draft details are unavailable. Open the strategy to check its current saved work.', action: 'Open strategy' }
  const latest = project.runs === null ? null : runsFor(strategy, project.runs).find((run) => run.graph.version === strategy.graph.current_version)
  if (latest) return runStep(strategy, latest)
  if (project.runs === null || project.datasets === null) return { strategy, view: 'backtest', title: 'Check your backtest setup', detail: 'Some research information is unavailable. Open Backtest to check your data and runs.', action: 'Open Backtest' }
  if (!project.datasets.some(primaryHistory)) return { strategy, view: 'backtest', title: 'Add backtest history', detail: 'This project has no eligible primary equity history. Add history in Backtest before setting up a run.', action: 'Add history' }
  return { strategy, view: 'backtest', title: 'Backtest your saved version', detail: `Version ${strategy.graph.current_version} is saved and primary equity history is available. Review the data requirements and run settings.`, action: 'Set up backtest' }
}
function allSteps(records: HomeRecords) {
  return records.projects.flatMap((project) => project.strategies.map((strategy) => nextStep(strategy, project)))
}
function runLabel(run: ExperimentRun) {
  if (run.evidence_state === 'corrupt') return 'Evidence unavailable'
  if (run.status === 'completed' && run.evidence_state !== 'verified') return 'Legacy result'
  return ({ pending: 'Queued', running: 'Running', completed: 'Completed', failed: 'Failed' } as Record<string, string>)[run.status] ?? 'Review status'
}
function runTone(run: ExperimentRun) {
  if (run.evidence_state === 'corrupt' || run.status === 'failed') return 'issue'
  if (run.status === 'completed' && run.evidence_state === 'verified') return 'complete'
  return run.status === 'pending' || run.status === 'running' ? 'active' : 'neutral'
}
function RunSummary({ records }: { records: HomeRecords }) {
  const runs = records.projects.flatMap((project) => project.runs ?? [])
  const groups = [
    { label: 'In progress', tone: 'active', count: runs.filter((run) => runTone(run) === 'active').length },
    { label: 'Completed', tone: 'complete', count: runs.filter((run) => runTone(run) === 'complete').length },
    { label: 'Needs a look', tone: 'issue', count: runs.filter((run) => runTone(run) === 'issue').length },
    { label: 'Other records', tone: 'neutral', count: runs.filter((run) => runTone(run) === 'neutral').length },
  ]
  return <aside className="home-work-summary" aria-labelledby="home-research-heading"><h2 id="home-research-heading">Research at a glance</h2>
    {runs.length ? <><div className="home-run-distribution" role="img" aria-label={groups.map((group) => `${group.count} ${group.label.toLowerCase()}`).join(', ')}>{groups.filter((group) => group.count > 0).map((group) => <span key={group.tone} className={`home-tone-${group.tone}`} style={{ flex: group.count }} />)}</div>
      <dl>{groups.filter((group) => group.count > 0).map((group) => <div key={group.tone}><dt><i className={`home-tone-${group.tone}`} aria-hidden="true" />{group.label}</dt><dd>{group.count}</dd></div>)}</dl></> : <p>{records.projects.some((project) => project.runs === null) ? 'Backtest history is not fully available.' : 'No backtests in these projects yet.'}</p>}
    <p className="home-scope-note">From the {records.projects.length === 1 ? 'project' : `${records.projects.length} projects`} shown below.</p>
  </aside>
}
function ContinueWork({ step, unavailable }: { step: NextStep | undefined; unavailable: boolean }) {
  if (!step && unavailable) return <section className="home-continue"><span className="home-section-label">Continue your work</span><h2>Your strategies are unavailable</h2><p>Retry the workspace to load your saved work.</p></section>
  if (!step) return <section className="home-continue"><span className="home-section-label">Start a study</span><h2>Start a strategy</h2><p>Start with your own rules or explore a preset. Your work will be saved as a draft.</p><Link className="home-primary-action" to="/strategies"><Plus aria-hidden="true" />Open Strategies<ArrowUpRight aria-hidden="true" /></Link></section>
  return <section className="home-continue"><span className="home-section-label">{step.title}</span><h2>{step.strategy.graph.display_name}</h2><p className="home-work-context">{step.strategy.projectName} · {step.strategy.graph.current_version === null ? 'Draft' : `Saved version ${step.strategy.graph.current_version}`}</p><p>{step.detail}</p><Link className="home-primary-action" to={strategyPath(step.strategy, step.view)}><FilePenLine aria-hidden="true" />{step.action}<ArrowUpRight aria-hidden="true" /></Link></section>
}
function RecentRuns({ records }: { records: HomeRecords }) {
  const runs = records.projects.flatMap((project) => (project.runs ?? []).map((run) => ({ run, project }))).toSorted((a, b) => b.run.run_id - a.run.run_id).slice(0, 5)
  return <section className="home-recent-runs" aria-labelledby="home-runs-heading"><header className="home-section-header"><h2 id="home-runs-heading">Recent backtests</h2></header>
    {runs.length ? <ol>{runs.map(({ run, project }) => {
      const strategy = project.strategies.find((item) => item.graph.identifier === run.graph.identifier)
      return <li key={`${project.project.project_id}:${run.run_id}`}><span className={`home-run-marker home-tone-${runTone(run)}`} aria-hidden="true" /><div><strong>{strategy?.graph.display_name ?? 'Saved strategy'}</strong><span>Run {run.run_id} · Version {run.graph.version} · {project.project.name}</span></div><span className="home-run-status">{runLabel(run)}</span><Link aria-label={`Review backtests for ${strategy?.graph.display_name ?? 'saved strategy'}, run ${run.run_id}`} to={`/strategies/${encodeURIComponent(project.project.project_id)}/${encodeURIComponent(run.graph.identifier)}?view=backtest`}><ArrowUpRight aria-hidden="true" /></Link></li>
    })}</ol> : <p>{records.projects.some((project) => project.runs === null) ? 'Backtests could not be fully loaded. Retry the workspace to check them.' : 'Your completed and running backtests will appear here.'}</p>}
  </section>
}
function StrategyWork({ records }: { records: HomeRecords }) {
  const steps = allSteps(records)
  return <section className="home-strategy-work" aria-labelledby="home-work-heading"><header className="home-section-header"><h2 id="home-work-heading">Your strategy work</h2><Link to="/strategies">View all<ArrowUpRight aria-hidden="true" /></Link></header>
    {steps.length ? <ul>{steps.map((step) => <li key={strategyPath(step.strategy)}><div><Link to={strategyPath(step.strategy)}><strong>{step.strategy.graph.display_name}</strong></Link><span>{step.strategy.projectName} · {step.strategy.draft === 'unfinished' ? 'Draft work to continue' : step.strategy.draft === 'saved' ? `Version ${step.strategy.graph.current_version} saved` : 'Draft details unavailable'}</span></div><Link className="home-work-action" to={strategyPath(step.strategy, step.view)}>{step.action}<ArrowUpRight aria-hidden="true" /></Link></li>)}</ul> : <p>{records.projects.some((project) => project.unavailable.includes('Strategies')) ? 'Strategies could not be loaded.' : 'No saved strategies yet. Open Strategies to create your first one.'}</p>}
  </section>
}
function HomeContent({ records, retry }: { records: HomeRecords; retry: () => void }) {
  const steps = allSteps(records), primary = steps.find((step) => step.strategy.draft === 'unfinished') ?? steps[0]
  const unavailable = records.projects.filter((project) => project.unavailable.length > 0)
  return <>{unavailable.length > 0 && <div className="home-partial-state"><p role="status">Some workspace information is unavailable. {unavailable.map((project) => `${project.project.name}: ${project.unavailable.join(', ')}.`).join(' ')}</p><button onClick={retry}>Retry workspace</button></div>}
    <div className="home-work-top"><ContinueWork step={primary} unavailable={records.projects.some((project) => project.unavailable.includes('Strategies'))} /><RunSummary records={records} /></div>
    <div className="home-work-bottom"><StrategyWork records={records} /><RecentRuns records={records} /></div>
    {records.projectCount > records.projects.length && <p className="home-scope-note">Showing {records.projects.length} of {records.projectCount} active projects. Open Strategies for the full workspace.</p>}
    {records.projects.some((project) => project.moreStrategies) && <p className="home-scope-note">Showing up to {MAX_STRATEGIES} strategies per project. View all strategies to continue other work.</p>}
  </>
}
type HomeState = { api: StrategyApi; scope: string; records?: HomeRecords; error?: string }
function identityScope(identity: BrowserIdentity | null) { return JSON.stringify([identity?.organization_id, identity?.user.id]) }
function HomeView({ name, current, retry }: { name: string | undefined; current: HomeState | null; retry: () => void }) {
  return <section className="home-workspace" aria-labelledby="home-heading" aria-busy={!current}>
    <header className="home-heading"><div>{name && <p>{name}</p>}<h1 id="home-heading">Your workspace</h1><p>Continue a draft or review a backtest.</p></div><nav aria-label="Quick actions"><Link to="/strategies"><FolderOpen aria-hidden="true" />Strategies</Link><Link to="/presets"><LayoutTemplate aria-hidden="true" />Presets</Link></nav></header>
    {!current && <div className="home-loading"><p role="status">Loading your workspace…</p></div>}
    {current?.error && <div className="home-partial-state"><p role="alert">{current.error}</p><button onClick={retry}>Retry workspace</button></div>}
    {current?.records && <HomeContent records={current.records} retry={retry} />}
  </section>
}
export function HomeWorkspace({ api }: { api: StrategyApi }) {
  const identity = useBrowserIdentity(), scope = identityScope(identity)
  const [state, setState] = useState<HomeState | null>(null)
  const [attempt, setAttempt] = useState(0)
  const current = state?.api === api && state.scope === scope ? state : null
  useEffect(() => {
    const controller = new AbortController(); setState(null)
    void loadHome(api, controller.signal).then((records) => { if (!controller.signal.aborted) setState({ api, scope, records }) })
      .catch((error: unknown) => { if (!controller.signal.aborted) setState({ api, scope, error: errorMessage(error) }) })
    return () => controller.abort()
  }, [api, scope, attempt])
  const retry = () => { setState(null); setAttempt((value) => value + 1) }
  return <HomeView name={identity?.user.display_name} current={current} retry={retry} />
}
