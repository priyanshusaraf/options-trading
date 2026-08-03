import { useEffect, useState } from 'react'
import {
  compareResearchRuns,
  decideResearchCandidate,
  getResearchRun,
  getResearchRuns,
  type ResearchComparison,
  type ResearchRunDetail,
  type ResearchRunSummary,
} from '../lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'

const readable = (value: unknown) => JSON.stringify(value, null, 2)

export function ResearchEvidenceSurface({
  runs,
  detail,
  comparison,
  reason,
  busy = false,
  error = null,
  onSelect,
  onCompare,
  onReason,
  onDecision,
}: {
  runs: readonly ResearchRunSummary[]
  detail: ResearchRunDetail | null
  comparison: ResearchComparison | null
  reason: string
  busy?: boolean
  error?: string | null
  onSelect?: (runId: number) => void
  onCompare?: (leftRunId: number, rightRunId: number) => void
  onReason?: (reason: string) => void
  onDecision?: (decision: 'approved' | 'rejected') => void
}) {
  const [left, setLeft] = useState<number | null>(runs[0]?.run_id ?? null)
  const [right, setRight] = useState<number | null>(runs[1]?.run_id ?? runs[0]?.run_id ?? null)
  useEffect(() => {
    if (runs.length === 0) {
      setLeft(null)
      setRight(null)
      return
    }
    if (!runs.some((run) => run.run_id === left)) setLeft(runs[0].run_id)
    if (!runs.some((run) => run.run_id === right)) {
      setRight(runs[1]?.run_id ?? runs[0].run_id)
    }
  }, [runs, left, right])
  const evidence = detail?.evidence
  const provenance = evidence?.provenance
  const results = evidence?.results
  const instruments = Array.isArray(results?.instruments) ? results.instruments : []
  const rejected = Array.isArray(results?.rejected) ? results.rejected : []
  const failure = results?.failure
  const candidate = detail?.candidate

  return (
    <Card aria-label="Research evidence" className="mb-4 border-sky-700/40">
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Research evidence and decisions</CardTitle>
        <p className="text-xs text-muted">
          Persisted server evidence only. Reads and comparisons do not rerun the strategy.
        </p>
      </CardHeader>
      <CardContent className="space-y-4 text-xs">
        {error && <p role="alert" className="text-amber-300">{error}</p>}
        {runs.length === 0 ? (
          <p className="text-muted">No graph-bound experiments yet.</p>
        ) : (
          <div>
            <div className="stat-label mb-1">Experiment history</div>
            <div className="flex flex-wrap gap-2">
              {runs.map((run) => (
                <button
                  type="button"
                  key={run.run_id}
                  className="btn"
                  aria-pressed={detail?.run_id === run.run_id}
                  onClick={() => onSelect?.(run.run_id)}
                >
                  Run {run.run_id} · graph v{run.graph.version} · {run.status}
                </button>
              ))}
            </div>
          </div>
        )}

        {detail && (
          <section aria-label={`Evidence for run ${detail.run_id}`} className="space-y-3">
            <div className="flex flex-wrap gap-2">
              <span className="badge bg-zinc-700/40">{detail.evidence_state}</span>
              <span>Decision: {detail.decision ?? 'not terminal'}</span>
              <span>Candidate: {candidate?.status ?? 'none'}</span>
            </div>
            {failure && (
              <div role="alert" className="rounded border border-amber-500/50 p-2 text-amber-200">
                {failure.code}: {failure.message} ({failure.stage})
              </div>
            )}
            {rejected.length > 0 && (
              <div>
                <div className="stat-label">Exact rejection reasons</div>
                <ul className="list-disc pl-5">
                  {rejected.map((item: any) => (
                    <li key={`${item.instrument}:${item.reason}`}>
                      {item.instrument}: {item.reason}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {instruments.length > 0 && (
              <div className="overflow-x-auto">
                <table className="w-full text-left">
                  <caption className="stat-label mb-1 text-left">Qualification and validation</caption>
                  <thead><tr><th>Instrument</th><th>Qualification</th><th>Gates / score</th></tr></thead>
                  <tbody>
                    {instruments.map((item: any) => (
                      <tr key={item.instrument} className="border-t border-edge/50 align-top">
                        <td>{item.instrument}</td>
                        <td>{item.qualification?.qualified ? 'qualified' : item.qualification?.reason}</td>
                        <td><pre className="whitespace-pre-wrap">{readable({
                          gates: item.validation?.gates,
                          scorecard: item.scorecard,
                        })}</pre></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {evidence && (
              <details>
                <summary className="cursor-pointer font-medium">Exact provenance and result JSON</summary>
                <pre className="mt-2 max-h-80 overflow-auto whitespace-pre-wrap rounded bg-panel2 p-2">
                  {readable({ provenance, results })}
                </pre>
              </details>
            )}

            {candidate?.status === 'pending' && (
              <div className="space-y-2 rounded border border-edge p-2">
                <label className="block font-medium" htmlFor="candidate-decision-reason">
                  Decision reason
                </label>
                <textarea
                  id="candidate-decision-reason"
                  className="min-h-20 w-full rounded border border-edge bg-panel2 p-2"
                  value={reason}
                  maxLength={400}
                  onChange={(event) => onReason?.(event.target.value)}
                />
                <div className="flex gap-2">
                  <button className="btn" disabled={busy || !reason.trim()} onClick={() => onDecision?.('approved')}>
                    Approve research candidate
                  </button>
                  <button className="btn" disabled={busy || !reason.trim()} onClick={() => onDecision?.('rejected')}>
                    Reject research candidate
                  </button>
                </div>
              </div>
            )}
            {candidate?.decision?.evidence && (
              <p>
                {candidate.decision.evidence.decision} by {candidate.decision.evidence.actor}: {' '}
                {candidate.decision.evidence.reason}
              </p>
            )}
          </section>
        )}

        {runs.length >= 1 && (
          <section aria-label="Compare experiments" className="space-y-2 border-t border-edge/50 pt-3">
            <div className="stat-label">Compare persisted runs</div>
            <div className="flex flex-wrap gap-2">
              <label>Left run <select value={left ?? ''} onChange={(event) => setLeft(Number(event.target.value))}>
                {runs.map((run) => <option key={run.run_id} value={run.run_id}>{run.run_id}</option>)}
              </select></label>
              <label>Right run <select value={right ?? ''} onChange={(event) => setRight(Number(event.target.value))}>
                {runs.map((run) => <option key={run.run_id} value={run.run_id}>{run.run_id}</option>)}
              </select></label>
              <button
                className="btn"
                disabled={busy || left === null || right === null}
                onClick={() => left !== null && right !== null && onCompare?.(left, right)}
              >Compare runs</button>
            </div>
            {comparison && (
              <div role="status">
                <p>{comparison.equivalent ? 'Evidence is exactly equivalent.' : 'Evidence differs.'}</p>
                {comparison.incomparable.length > 0 && (
                  <p className="text-amber-300">Not like-for-like: {comparison.incomparable.join(', ')}</p>
                )}
                <ul className="list-disc pl-5">
                  {comparison.differences.map((difference, index) => (
                    <li key={`${difference.dimension}:${difference.path.join('.')}:${index}`}>
                      {difference.dimension}.{difference.path.join('.')}: {' '}
                      {readable(difference.left)} → {readable(difference.right)}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </section>
        )}
      </CardContent>
    </Card>
  )
}

export default function ResearchEvidencePanel({ projectId }: { projectId: string }) {
  const [runs, setRuns] = useState<ResearchRunSummary[]>([])
  const [detail, setDetail] = useState<ResearchRunDetail | null>(null)
  const [comparison, setComparison] = useState<ResearchComparison | null>(null)
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadDetail = async (runId: number) => {
    setError(null)
    try {
      setDetail(await getResearchRun(projectId, runId))
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Research evidence request failed')
    }
  }

  const refresh = async (preferredRunId?: number) => {
    const response = await getResearchRuns(projectId)
    setRuns(response.runs)
    const runId = preferredRunId ?? detail?.run_id ?? response.runs[0]?.run_id
    if (runId) await loadDetail(runId)
  }

  useEffect(() => {
    refresh().catch((cause) => {
      setError(cause instanceof Error ? cause.message : 'Research history request failed')
    })
  }, [projectId])

  const compare = async (left: number, right: number) => {
    setBusy(true); setError(null)
    try { setComparison(await compareResearchRuns(projectId, left, right)) }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Comparison failed') }
    finally { setBusy(false) }
  }

  const decide = async (decision: 'approved' | 'rejected') => {
    if (!detail?.candidate || !reason.trim()) return
    setBusy(true); setError(null)
    try {
      await decideResearchCandidate(
        projectId, detail.candidate.candidate_id, decision, reason.trim(),
      )
      setReason('')
      await refresh(detail.run_id)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Candidate decision failed')
    } finally { setBusy(false) }
  }

  return <ResearchEvidenceSurface
    runs={runs}
    detail={detail}
    comparison={comparison}
    reason={reason}
    busy={busy}
    error={error}
    onSelect={loadDetail}
    onCompare={compare}
    onReason={setReason}
    onDecision={decide}
  />
}
