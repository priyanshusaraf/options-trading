import { useState } from 'react'
import { TraderSelect } from '../components/TraderSelect'
import type { CanonicalOptimizationEvidence, OptimizationCandidate } from '../shell/contracts'
import { labelFor } from './builderParameterContracts'

export function developmentNeighborhood(result: CanonicalOptimizationEvidence, tolerance: number) {
  const selected = result.final_development_trials.find((trial) => trial.params.candidate_graph_address === result.selected?.graph_address)
  const best = selected?.objective
  const complete = result.state === 'selected' && result.final_development_trials.length === result.candidates.length
  const comparable = complete && typeof best === 'number' && best > 0
  const rows = result.candidates.map((candidate, index) => {
    const trial = result.final_development_trials.find((item) => item.params.candidate_graph_address === candidate.graph_address)
    const score = trial?.objective ?? null
    const drop = comparable && score !== null ? 100 * (1 - score / best) : null
    return { candidate, index, score, trades: trial?.trades ?? null, drop, near: drop !== null && drop <= tolerance,
      selected: candidate.graph_address === result.selected?.graph_address }
  })
  return { rows, comparable, complete, near: rows.filter((row) => row.near).length }
}

function parameterLabel(candidate: OptimizationCandidate) {
  return candidate.parameters.map((parameter) => `${labelFor(parameter.parameter_id)}: ${parameter.normalized_value}`).join(', ')
}

function NeighborhoodReading({ count, near }: { count: number; near: number }) {
  if (near === 1) return <p><strong>Isolated high score in this tested grid.</strong> The other tested settings fall outside your comparison tolerance. Inspect more nearby values before preferring this setting.</p>
  if (near === count) return <p><strong>Similar scores across this tested grid.</strong> This supports local parameter stability under your chosen tolerance; it does not establish performance outside these values.</p>
  return <p><strong>Mixed sensitivity in this tested grid.</strong> Some tested settings remain close to the selected score. Compare their values and test the boundaries of that region.</p>
}

export function OptimizationNeighborhood({ result }: { result: CanonicalOptimizationEvidence }) {
  const [tolerance, setTolerance] = useState('10')
  const summary = developmentNeighborhood(result, Number(tolerance))
  return <section aria-label="Parameter neighborhood"><h4>Parameter neighborhood</h4>
    <p>Compare every tested setting before choosing a change. These are development scores, not returns or probabilities.</p>
    <label>Score comparison tolerance<TraderSelect label="Score comparison tolerance" value={tolerance} onValueChange={setTolerance}
      options={['5', '10', '20'].map((value) => ({ value, label: `Within ${value}% of the selected score` }))} /></label>
    {summary.comparable ? <><p>{summary.near} of {summary.rows.length} tested settings are within {tolerance}% of the selected development score.</p>
      <NeighborhoodReading count={summary.rows.length} near={summary.near} /></> : <p>{summary.complete ? 'The selected score is not positive, so a percentage comparison is not meaningful. Inspect the recorded scores directly.' : 'The search has not evaluated the complete grid. No neighborhood conclusion is available.'}</p>}
    <div className="result-table-wrap"><table><caption>Parameter combinations and recorded scores</caption><thead><tr><th scope="col">Candidate</th><th scope="col">Parameters</th><th scope="col">Development score</th><th scope="col">Trades</th><th scope="col">Comparison</th></tr></thead><tbody>
      {summary.rows.map((row) => <tr key={row.candidate.graph_address}><th scope="row">{row.index === 0 ? 'Baseline' : `Candidate ${row.index + 1}`}{row.selected ? ' · Selected' : ''}</th>
        <td>{parameterLabel(row.candidate)}</td><td>{row.score === null ? 'Not eligible or not evaluated' : row.score.toPrecision(6)}</td><td>{row.trades ?? 'Not recorded'}</td>
        <td>{row.drop === null ? 'Not comparable' : row.near ? 'Within tolerance' : 'Outside tolerance'}</td></tr>)}
    </tbody></table></div>
    <p>The tolerance is your display choice, not a research gate. A plateau does not prove a setting is safe. Repeated parameter or instrument selection also uses information; evaluate the final choice on data that has not guided those choices.</p>
  </section>
}
