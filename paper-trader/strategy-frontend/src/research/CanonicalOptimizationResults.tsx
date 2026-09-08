import { useEffect, useState } from 'react'
import { errorMessage, type StrategyApi } from '../shell/api'
import type { CanonicalOptimizationEvidence, ExperimentRun, OptimizationTrial, OptimizationCandidate, PublishedGraph } from '../shell/contracts'
import { labelFor, SaveVerificationError } from './builderParameterContracts'
import { OptimizationNeighborhood } from './OptimizationNeighborhood'
import { SignalParameterSettings } from './SignalParameterSettings'

type PublicationActions = { onPublished?: (version: PublishedGraph) => void; onOpenBuilder?: () => void }

const stateLabels: Record<CanonicalOptimizationEvidence['state'], string> = {
  pending: 'Search not started', running: 'Search was in progress', failed: 'Search failed', cancelled: 'Search cancelled', refused: 'Search refused',
  not_qualified: 'Baseline did not qualify; search did not start', selected: 'Candidate selected on development data',
}
function searchReason(code: string | undefined) {
  if (code === 'BASELINE_NOT_QUALIFIED') return 'The saved baseline failed development qualification. Neighboring candidates were not evaluated. Review the research conclusion before changing the experiment.'
  if (code === 'CANONICAL_SEARCH_RESOURCE_REFUSED') return 'Reduce parameters or folds, or use fewer bars, to fit the replay budget.'
  if (code === 'INSUFFICIENT_DEVELOPMENT_HISTORY') return 'Add development history or reduce the number of folds.'
  if (code === 'CANDIDATE_CANCELLED') return 'The search stopped. The retained rows show how far it reached.'
  return code ? 'The search could not finish. Review the retained candidates and run setup before starting another run.' : null
}
function trialParameters(row: OptimizationTrial, candidates: readonly OptimizationCandidate[]) {
  const candidate = candidates.find((item) => item.graph_address === row.params.candidate_graph_address)
  return candidate?.parameters.map((parameter) => `${labelFor(parameter.parameter_id)}: ${parameter.normalized_value}`).join(', ') ?? 'Parameters unavailable'
}
function TrialTable({ rows, candidates }: { rows: readonly OptimizationTrial[]; candidates: readonly OptimizationCandidate[] }) {
  return <div className="result-table-wrap"><table><thead><tr><th>Fold</th><th>Parameters</th><th>Trades</th><th>Development objective</th><th>Selected</th></tr></thead><tbody>
    {rows.map((row, index) => <tr key={index}><td>{row.fold_index < 0 ? 'Final development' : row.fold_index + 1}</td>
      <td>{trialParameters(row, candidates)}</td>
      <td>{row.trades}</td><td>{row.objective === null ? 'Not eligible' : row.objective.toPrecision(6)}</td><td>{row.selected ? 'Yes' : 'No'}</td></tr>)}
  </tbody></table></div>
}
function searchDate(value: number | null) {
  if (value === null) return 'Not recorded'
  const date = new Date(value * 1000)
  return Number.isFinite(date.valueOf()) ? `${date.toISOString().replace('T', ' ').replace('.000Z', '')} UTC` : 'Date unavailable'
}
function SearchWindow({ partition }: { partition: NonNullable<CanonicalOptimizationEvidence['partition']> }) {
  return <div><p>Recorded split: {partition.development_bars} development bars, then {partition.validation_bars} bars in the later locked window.</p>
    <dl><div><dt>Development data through</dt><dd>{searchDate(partition.development_end_ts)}</dd></div><div><dt>Later test window</dt><dd>{searchDate(partition.validation_start_ts)} to {searchDate(partition.validation_end_ts)}</dd></div></dl></div>
}

function rejectionReason(reason: string) {
  const trades = /^insufficient trades \((\d+)<(\d+)\)$/.exec(reason)
  return trades ? `Only ${trades[1]} development trades; at least ${trades[2]} were required.` : reason
}

function ResearchConclusion({ run }: { run: ExperimentRun }) {
  const outcome = run.research_outcome
  if (!outcome) return null
  return <section aria-label="Research conclusion"><h3>Research conclusion</h3>
    <p>Run {run.run_id} · Saved version {run.graph.version} · {outcome.total_bars} input bars</p>
    {outcome.qualified === 0 ? <><p><strong>Did not meet development requirements.</strong> Later-window validation did not run.</p>
      <p>Use more development history or revisit the entry rules before another run. This result does not establish a validated edge.</p></>
      : <p>{outcome.qualified} instrument checks qualified on development data; {outcome.validated} passed later validation. Review the recorded gates before preferring a revision.</p>}
    {outcome.rejected.length > 0 && <ul>{outcome.rejected.map((row, index) => <li key={`${row.instrument}:${index}`}>{rejectionReason(row.reason)}</li>)}</ul>}
  </section>
}
function SelectedParameters({ api, run, result, onPublished, onOpenBuilder }: PublicationActions & { api: StrategyApi; run: ExperimentRun; result: CanonicalOptimizationEvidence }) {
  const [review, setReview] = useState(false)
  const [savedVersion, setSavedVersion] = useState<number | null>(null)
  const selected = result.selected
  if (!selected) return null
  function published(version: PublishedGraph) { setSavedVersion(version.version); onPublished?.(version) }
  return <div><h4>{savedVersion === null ? 'Selected parameters — not published' : `New research version ${savedVersion} saved`}</h4><dl>{selected.parameters.map((parameter) => <div key={`${parameter.node_id}:${parameter.parameter_id}`}><dt>{labelFor(parameter.parameter_id)}</dt><dd>{parameter.normalized_value}</dd></div>)}</dl>
    <p>You can review this suggestion for further research even if later gates failed. Saving it does not turn a failed result into a pass.</p>
    {savedVersion !== null && <p>The values above remain this run’s original suggestion. Your saved revision contains the values you accepted in the editor.</p>}
    {!review ? <button type="button" onClick={() => setReview(true)}>Review selected parameters</button> : <SignalParameterSettings api={api}
      projectId={run.graph.project_id} graphId={run.graph.identifier} currentVersion={run.graph.version}
      proposal={{ runId: run.run_id, baseline: run.graph, selection: selected }} onPublished={published} onOpenBuilder={onOpenBuilder} />}
  </div>
}

function SearchResult({ api, run, result, onPublished, onOpenBuilder }: PublicationActions & { api: StrategyApi; run: ExperimentRun; result: CanonicalOptimizationEvidence }) {
  const selected = result.selected, reason = searchReason(result.reason_code)
  return <section className="canonical-optimization-results" aria-labelledby="development-search-result"><h3 id="development-search-result">Development search</h3>
    <p><strong>{stateLabels[result.state]}</strong> · Run {run.run_id}: {run.status}{run.decision ? ` · Decision: ${run.decision}` : ''}</p>
    <p>Selection uses development data only. A selected candidate is not a holdout pass. Review any proposed change before saving a new strategy version.</p>
    {reason && <p>{reason}</p>}
    <p>{result.candidates.length} candidates · {result.nested_trials.length} nested development trials · {result.final_development_trials.length} final development trials</p>
    {result.partition && <SearchWindow partition={result.partition} />}
    <OptimizationNeighborhood result={result} />
    {selected && <SelectedParameters api={api} run={run} result={result} onPublished={onPublished} onOpenBuilder={onOpenBuilder} />}
    <details><summary>Candidate population ({result.candidates.length})</summary><div className="result-table-wrap"><table><thead><tr><th>Candidate</th><th>Parameters</th><th>State</th></tr></thead><tbody>
      {result.candidates.map((candidate, index) => <tr key={candidate.graph_address}><td>{index === 0 ? 'Baseline' : `Candidate ${index + 1}`}</td><td>{candidate.parameters.map((parameter) => `${labelFor(parameter.parameter_id)}: ${parameter.normalized_value}`).join(', ')}</td><td>{candidate.state}</td></tr>)}
    </tbody></table></div></details>
    <details><summary>Nested development trials ({result.nested_trials.length})</summary><TrialTable rows={result.nested_trials} candidates={result.candidates} /></details>
    <details><summary>Final development trials ({result.final_development_trials.length})</summary><TrialTable rows={result.final_development_trials} candidates={result.candidates} /></details>
    <h4>Research gates</h4><p>The later locked window is evaluated after selection. The PBO gate uses development trials, so the gate set is not exclusively holdout statistics.</p>
    {run.optimization_research_gates?.length ? run.optimization_research_gates.map((entry) => <div key={entry.instrument}><strong>{entry.instrument}: {entry.passed === null ? 'Evaluation not recorded' : entry.passed ? 'Passed' : 'Did not pass'}</strong>
      <dl>{Object.entries(entry.gates).map(([name, gate]) => <div key={name}><dt>{labelFor(name)}</dt><dd>{gate.passed ? 'Passed' : 'Failed'} · {String(gate.value)}</dd></div>)}</dl></div>) : <p>No later research gate result was recorded.</p>}
  </section>
}
export function CanonicalOptimizationResults({ api, projectId, runId, onPublished, onOpenBuilder }: PublicationActions & { api: StrategyApi; projectId: string; runId: number }) {
  const [attempt, setAttempt] = useState(0)
  const [result, setResult] = useState<{ api: StrategyApi; projectId: string; runId: number; run?: ExperimentRun; error?: string } | null>(null)
  const current = result?.api === api && result.projectId === projectId && result.runId === runId ? result : null
  useEffect(() => {
    const controller = new AbortController()
    setResult(null)
    void Promise.resolve().then(() => api.experiment(projectId, runId, controller.signal)).then((run) => {
      if (run.run_id !== runId || run.graph.project_id !== projectId) throw new SaveVerificationError('The returned run does not match this selection.')
      if (run.canonical_optimization && run.evidence_state !== 'verified') throw new SaveVerificationError('Search evidence has not been verified.')
      if (!controller.signal.aborted) setResult({ api, projectId, runId, run })
    })
      .catch((error) => { if (!controller.signal.aborted) setResult({ api, projectId, runId, error: error instanceof SaveVerificationError ? error.message : errorMessage(error) }) })
    return () => controller.abort()
  }, [api, projectId, runId, attempt])
  if (current?.error) return <section><p role="status">Research details are unavailable. {current.error}</p><button onClick={() => setAttempt((value) => value + 1)}>Retry search details</button></section>
  if (!current?.run) return null
  return <><ResearchConclusion run={current.run} />{current.run.canonical_optimization && <SearchResult key={runId} api={api} run={current.run} result={current.run.canonical_optimization} onPublished={onPublished} onOpenBuilder={onOpenBuilder} />}</>
}
