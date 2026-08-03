import { useEffect, useState } from 'react'
import {
  compareResearchVersions,
  createResearchFinding,
  decideResearchCandidate,
  getResearchOperationStatus,
  getResearchRun,
  getResearchFindings,
  getResearchGraphVersions,
  getResearchRuns,
  reviseResearchFinding,
  type ResearchComparison,
  type ResearchFinding,
  type ResearchGraphVersion,
  type ResearchOperationReceipt,
  type ResearchOperationStatus,
  type ResearchRunDetail,
  type ResearchRunSummary,
  type ResearchVersionSelection,
} from '../lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'

const readable = (value: unknown) => JSON.stringify(value, null, 2)

function OperationReceipt({
  label, receipt, onSelect,
}: {
  label: string
  receipt: ResearchOperationReceipt
  onSelect?: (runId: number) => void
}) {
  const trigger = receipt.trigger.replace('_', ' ')
  return <div className="rounded border border-edge p-2">
    <p className="font-medium">
      {label} · {label === 'Running' ? receipt.stage : `${receipt.state} · ${receipt.stage}`} · {trigger}
    </p>
    <p className="text-muted">
      {receipt.started_at}{receipt.completed_at ? ` → ${receipt.completed_at}` : ''}
      {' · '}build {receipt.build} · provider {receipt.provider_mode}
    </p>
    {receipt.plan && <p>
      {receipt.plan.experiment_count} planned · <code className="break-all">{receipt.plan.content_address}</code>
    </p>}
    {receipt.completed_run_ids.length > 0 && <div className="mt-1 flex flex-wrap gap-2">
      {receipt.completed_run_ids.map((runId) => <button
        type="button" className="btn" key={runId} onClick={() => onSelect?.(runId)}
      >Run {runId}</button>)}
    </div>}
    {receipt.failure && <p role="alert" className="text-amber-300">
      {receipt.failure.code}: {receipt.failure.message}
    </p>}
  </div>
}

export function ResearchEvidenceSurface({
  runs,
  detail,
  comparison,
  findings = [],
  versions = [],
  operationStatus = null,
  operationError = null,
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
  versions?: readonly ResearchGraphVersion[]
  operationStatus?: ResearchOperationStatus | null
  operationError?: string | null
  reason: string
  findingStatement?: string
  findingPolarity?: 'positive' | 'negative'
  editingFindingId?: number | null
  busy?: boolean
  error?: string | null
  onSelect?: (runId: number) => void
  onCompare?: (left: ResearchVersionSelection, right: ResearchVersionSelection) => void
  onReason?: (reason: string) => void
  onDecision?: (decision: 'approved' | 'rejected') => void
  onFindingStatement?: (statement: string) => void
  onFindingPolarity?: (polarity: 'positive' | 'negative') => void
  onStartRevision?: (finding: ResearchFinding) => void
  onCancelRevision?: () => void
  onFindingSubmit?: () => void
}) {
  const orderedVersions = versions.length > 0
    ? [...versions].sort((a, b) => a.version - b.version)
    : Array.from(new Map(runs.map((run) => [run.graph.version, {
        project_id: run.graph.project_id,
        identifier: run.graph.identifier,
        version: run.graph.version,
        content_address: run.graph.content_address,
      }])).values()).sort((a, b) => a.version - b.version)
  const latestVersion = orderedVersions[orderedVersions.length - 1]
  const previousVersion = orderedVersions[orderedVersions.length - 2]
  const [leftVersion, setLeftVersion] = useState<number | null>(
    previousVersion?.version ?? latestVersion?.version ?? null,
  )
  const [rightVersion, setRightVersion] = useState<number | null>(
    latestVersion?.version ?? null,
  )
  const [leftRun, setLeftRun] = useState<number | null>(null)
  const [rightRun, setRightRun] = useState<number | null>(null)
  const leftIdentity = orderedVersions.find((item) => item.version === leftVersion)
  const rightIdentity = orderedVersions.find((item) => item.version === rightVersion)
  useEffect(() => {
    if (orderedVersions.length === 0) {
      setLeftVersion(null)
      setRightVersion(null)
      return
    }
    if (!orderedVersions.some((version) => version.version === leftVersion)) {
      setLeftVersion(previousVersion?.version ?? latestVersion!.version)
      setLeftRun(null)
    }
    if (!orderedVersions.some((version) => version.version === rightVersion)) {
      setRightVersion(latestVersion!.version)
      setRightRun(null)
    }
  }, [versions, runs, leftVersion, rightVersion])
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
        <section aria-label="Research operation status" className="space-y-2">
          <div className="stat-label">Research operation status</div>
          {operationError && <p role="alert" className="text-amber-300">{operationError}</p>}
          {operationStatus?.state === 'never_run' && (
            <p className="text-muted">No bounded research operation has run yet.</p>
          )}
          {operationStatus?.active && <OperationReceipt
            label="Running" receipt={operationStatus.active} onSelect={onSelect}
          />}
          {operationStatus?.last && <OperationReceipt
            label="Last" receipt={operationStatus.last} onSelect={onSelect}
          />}
        </section>
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

        {orderedVersions.length >= 1 && (
          <section aria-label="Compare immutable versions and evidence" className="space-y-2 border-t border-edge/50 pt-3">
            <div className="stat-label">Compare immutable versions and evidence</div>
            <div className="flex flex-wrap gap-2">
              <label>Left version <select value={leftVersion ?? ''} onChange={(event) => {
                setLeftVersion(Number(event.target.value)); setLeftRun(null)
              }}>
                {orderedVersions.map((version) => <option key={version.version} value={version.version}>
                  v{version.version}
                </option>)}
              </select></label>
              <label>Left evidence <select value={leftRun ?? ''} onChange={(event) => {
                setLeftRun(event.target.value ? Number(event.target.value) : null)
              }}>
                <option value="">Graph only</option>
                {runs.filter((run) => (
                  run.graph.version === leftVersion
                  && run.graph.identifier === leftIdentity?.identifier
                )).map((run) => (
                  <option key={run.run_id} value={run.run_id}>Run {run.run_id}</option>
                ))}
              </select></label>
              <label>Right version <select value={rightVersion ?? ''} onChange={(event) => {
                setRightVersion(Number(event.target.value)); setRightRun(null)
              }}>
                {orderedVersions.map((version) => <option key={version.version} value={version.version}>
                  v{version.version}
                </option>)}
              </select></label>
              <label>Right evidence <select value={rightRun ?? ''} onChange={(event) => {
                setRightRun(event.target.value ? Number(event.target.value) : null)
              }}>
                <option value="">Graph only</option>
                {runs.filter((run) => (
                  run.graph.version === rightVersion
                  && run.graph.identifier === rightIdentity?.identifier
                )).map((run) => (
                  <option key={run.run_id} value={run.run_id}>Run {run.run_id}</option>
                ))}
              </select></label>
              <button
                className="btn"
                disabled={
                  busy || leftVersion === null || rightVersion === null
                  || ((leftRun === null) !== (rightRun === null))
                }
                onClick={() => {
                  if (!leftIdentity || !rightIdentity) return
                  onCompare?.(
                    {
                      graph_identifier: leftIdentity.identifier,
                      graph_version: leftIdentity.version,
                      ...(leftRun === null ? {} : { run_id: leftRun }),
                    },
                    {
                      graph_identifier: rightIdentity.identifier,
                      graph_version: rightIdentity.version,
                      ...(rightRun === null ? {} : { run_id: rightRun }),
                    },
                  )
                }}
              >Compare versions</button>
            </div>
            {comparison && (
              <div role="status">
                <p>{comparison.equivalent
                  ? 'Selected versions and evidence are exactly equivalent.'
                  : 'Selected versions or evidence differ.'}</p>
                {comparison.incomparable.length > 0 && (
                  <p className="text-amber-300">Not like-for-like: {comparison.incomparable.join(', ')}</p>
                )}
                <ul className="min-w-0 list-disc break-all pl-5">
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

export default function ResearchEvidencePanel({
  projectId, graphIdentifier,
}: { projectId: string; graphIdentifier: string }) {
  const [runs, setRuns] = useState<ResearchRunSummary[]>([])
  const [detail, setDetail] = useState<ResearchRunDetail | null>(null)
  const [comparison, setComparison] = useState<ResearchComparison | null>(null)
  const [findings, setFindings] = useState<ResearchFinding[]>([])
  const [versions, setVersions] = useState<ResearchGraphVersion[]>([])
  const [operationStatus, setOperationStatus] = useState<ResearchOperationStatus | null>(null)
  const [operationError, setOperationError] = useState<string | null>(null)
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
    const [runResponse, findingResponse, versionResponse] = await Promise.all([
      getResearchRuns(projectId), getResearchFindings(projectId),
      getResearchGraphVersions(projectId, graphIdentifier),
    ])
    setRuns(runResponse.runs)
    setFindings(findingResponse.findings)
    setVersions(versionResponse)
    const runId = preferredRunId ?? detail?.run_id ?? runResponse.runs[0]?.run_id
    if (runId) await loadDetail(runId)
  }

  useEffect(() => {
    refresh().catch((cause) => {
      setError(cause instanceof Error ? cause.message : 'Research history request failed')
    })
  }, [projectId, graphIdentifier])

  useEffect(() => {
    let disposed = false
    const loadOperation = () => {
      setOperationError(null)
      getResearchOperationStatus().then((status) => {
        if (!disposed) setOperationStatus(status)
      }).catch((cause) => {
        if (!disposed) {
          setOperationStatus(null)
          setOperationError(
            cause instanceof Error ? cause.message : 'Research operation status request failed',
          )
        }
      })
    }
    loadOperation()
    const timer = window.setInterval(loadOperation, 10_000)
    return () => {
      disposed = true
      window.clearInterval(timer)
    }
  }, [])

  const compare = async (left: ResearchVersionSelection, right: ResearchVersionSelection) => {
    setBusy(true); setError(null); setComparison(null)
    try { setComparison(await compareResearchVersions(projectId, left, right)) }
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
    versions={versions}
    operationStatus={operationStatus}
    operationError={operationError}
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
