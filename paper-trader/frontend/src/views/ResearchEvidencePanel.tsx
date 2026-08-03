import { useEffect, useState } from 'react'
import {
  compareResearchRuns,
  createResearchFinding,
  decideResearchCandidate,
  getResearchRun,
  getResearchFindings,
  getResearchRuns,
  reviseResearchFinding,
  type ResearchComparison,
  type ResearchFinding,
  type ResearchRunDetail,
  type ResearchRunSummary,
} from '../lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'

const readable = (value: unknown) => JSON.stringify(value, null, 2)

export function ResearchEvidenceSurface({
  runs,
  detail,
  comparison,
  findings = [],
  reason,
  findingStatement = '',
  findingPolarity = 'negative',
  editingFindingId = null,
  busy = false,
  error = null,
  onSelect,
  onCompare,
  onReason,
  onDecision,
  onFindingStatement,
  onFindingPolarity,
  onStartRevision,
  onCancelRevision,
  onFindingSubmit,
}: {
  runs: readonly ResearchRunSummary[]
  detail: ResearchRunDetail | null
  comparison: ResearchComparison | null
  findings?: readonly ResearchFinding[]
  reason: string
  findingStatement?: string
  findingPolarity?: 'positive' | 'negative'
  editingFindingId?: number | null
  busy?: boolean
  error?: string | null
  onSelect?: (runId: number) => void
  onCompare?: (leftRunId: number, rightRunId: number) => void
  onReason?: (reason: string) => void
  onDecision?: (decision: 'approved' | 'rejected') => void
  onFindingStatement?: (statement: string) => void
  onFindingPolarity?: (polarity: 'positive' | 'negative') => void
  onStartRevision?: (finding: ResearchFinding) => void
  onCancelRevision?: () => void
  onFindingSubmit?: () => void
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
  const selectedFindings = detail
    ? findings.filter((finding) => finding.evidence_run_id === detail.run_id)
    : []

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

            <section aria-label="Finding history" className="space-y-2 border-t border-edge/50 pt-3">
              <div className="stat-label">Finding history</div>
              {selectedFindings.length === 0 && (
                <p className="text-muted">No persisted interpretations for this run.</p>
              )}
              <ol className="space-y-2">
                {selectedFindings.map((finding) => (
                  <li key={finding.finding_id} className="rounded border border-edge p-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <span>Finding {finding.finding_id}</span>
                      <span className="badge bg-zinc-700/40">{finding.polarity}</span>
                      <span className="badge bg-zinc-700/40">{finding.status}</span>
                      <span>confidence {finding.confidence.toFixed(3)}</span>
                    </div>
                    <p className="my-1 text-zinc-300">{finding.statement}</p>
                    <code className="break-all text-[10px] text-muted">
                      {finding.binding.evidence_content_address}
                    </code>
                    {finding.superseded_by !== null && (
                      <p className="text-muted">Superseded by finding {finding.superseded_by}</p>
                    )}
                    {finding.status === 'active' && (
                      <button className="btn mt-2" onClick={() => onStartRevision?.(finding)}>
                        Revise finding {finding.finding_id}
                      </button>
                    )}
                  </li>
                ))}
              </ol>
              {detail.status === 'completed' && detail.evidence_state === 'verified' && (
                <div className="space-y-2 rounded border border-edge p-2">
                  <label className="block font-medium" htmlFor="finding-statement">
                    {editingFindingId === null
                      ? 'Record an interpretation'
                      : `Revise finding ${editingFindingId}`}
                  </label>
                  <textarea
                    id="finding-statement"
                    className="min-h-20 w-full rounded border border-edge bg-panel2 p-2"
                    maxLength={4000}
                    value={findingStatement}
                    onChange={(event) => onFindingStatement?.(event.target.value)}
                  />
                  <label>Polarity {' '}
                    <select
                      aria-label="Finding polarity"
                      value={findingPolarity}
                      onChange={(event) => onFindingPolarity?.(
                        event.target.value as 'positive' | 'negative',
                      )}
                    >
                      <option value="positive">Positive</option>
                      <option value="negative">Negative</option>
                    </select>
                  </label>
                  <div className="flex gap-2">
                    <button
                      className="btn"
                      disabled={busy || !findingStatement.trim()}
                      onClick={onFindingSubmit}
                    >
                      {editingFindingId === null ? 'Record finding' : 'Save finding revision'}
                    </button>
                    {editingFindingId !== null && (
                      <button className="btn" disabled={busy} onClick={onCancelRevision}>
                        Cancel revision
                      </button>
                    )}
                  </div>
                </div>
              )}
            </section>

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
  const [findings, setFindings] = useState<ResearchFinding[]>([])
  const [reason, setReason] = useState('')
  const [findingStatement, setFindingStatement] = useState('')
  const [findingPolarity, setFindingPolarity] = useState<'positive' | 'negative'>('negative')
  const [editingFindingId, setEditingFindingId] = useState<number | null>(null)
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
    const [runResponse, findingResponse] = await Promise.all([
      getResearchRuns(projectId), getResearchFindings(projectId),
    ])
    setRuns(runResponse.runs)
    setFindings(findingResponse.findings)
    const runId = preferredRunId ?? detail?.run_id ?? runResponse.runs[0]?.run_id
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

  const startRevision = (finding: ResearchFinding) => {
    setEditingFindingId(finding.finding_id)
    setFindingStatement(finding.statement)
    setFindingPolarity(finding.polarity)
    setError(null)
  }

  const cancelRevision = () => {
    setEditingFindingId(null)
    setFindingStatement('')
    setFindingPolarity('negative')
  }

  const submitFinding = async () => {
    if (!detail || !findingStatement.trim()) return
    setBusy(true); setError(null)
    try {
      if (editingFindingId === null) {
        await createResearchFinding(
          projectId, detail.run_id, findingStatement.trim(), findingPolarity,
        )
      } else {
        await reviseResearchFinding(
          projectId, editingFindingId, findingStatement.trim(), findingPolarity,
        )
      }
      cancelRevision()
      const response = await getResearchFindings(projectId)
      setFindings(response.findings)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Finding request failed')
    } finally { setBusy(false) }
  }

  return <ResearchEvidenceSurface
    runs={runs}
    detail={detail}
    comparison={comparison}
    findings={findings}
    reason={reason}
    findingStatement={findingStatement}
    findingPolarity={findingPolarity}
    editingFindingId={editingFindingId}
    busy={busy}
    error={error}
    onSelect={loadDetail}
    onCompare={compare}
    onReason={setReason}
    onDecision={decide}
    onFindingStatement={setFindingStatement}
    onFindingPolarity={setFindingPolarity}
    onStartRevision={startRevision}
    onCancelRevision={cancelRevision}
    onFindingSubmit={submitFinding}
  />
}
