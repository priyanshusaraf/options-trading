import { useEffect, useRef, useState } from 'react'
import {
  compareResearchVersions,
  createResearchFinding,
  createResearchReviewNote,
  createResearchReviewSavedView,
  decideResearchCandidate,
  deleteResearchReviewNote,
  deleteResearchReviewSavedView,
  getResearchReview,
  getResearchReviewNotes,
  getResearchReviewSavedViews,
  getResearchRun,
  getResearchFindings,
  getResearchGraphVersions,
  getResearchRuns,
  reviseResearchFinding,
  updateResearchReviewNote,
  type ResearchComparison,
  type ResearchFinding,
  type ResearchGraphVersion,
  type ResearchOperationReceipt,
  type ResearchOperationStatus,
  type ResearchReview,
  type ResearchReviewEventType,
  type ResearchReviewFilters,
  type ResearchReviewNote,
  type ResearchReviewSavedView,
  type ResearchRunDetail,
  type ResearchRunSummary,
  type ResearchVersionSelection,
} from '../lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'

const readable = (value: unknown) => JSON.stringify(value, null, 2)

export function mergeResearchReview(
  current: ResearchReview,
  response: ResearchReview,
  mode: 'append' | 'preserve',
): ResearchReview {
  const incoming = [...current.timeline.events, ...response.timeline.events]
  const events = Array.from(new Map(incoming.map((event) => [event.event_id, event])).values())
    .sort((left, right) => (
      right.occurred_at.localeCompare(left.occurred_at)
      || right.event_id.localeCompare(left.event_id)
    ))
  return {
    ...response,
    timeline: {
      events,
      next_cursor: mode === 'append'
        ? response.timeline.next_cursor
        : current.timeline.next_cursor,
    },
  }
}

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
  review = null,
  reviewFilters = {},
  reviewError = null,
  reviewNotes = [],
  savedViews = [],
  noteEventId = null,
  editingNoteId = null,
  noteDraft = '',
  savedViewName = '',
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
  onReviewFilters,
  onReviewMore,
  onStartNote,
  onEditNote,
  onCancelNote,
  onNoteDraft,
  onSubmitNote,
  onDeleteNote,
  onSavedViewName,
  onSaveView,
  onApplyView,
  onDeleteView,
}: {
  runs: readonly ResearchRunSummary[]
  detail: ResearchRunDetail | null
  comparison: ResearchComparison | null
  findings?: readonly ResearchFinding[]
  versions?: readonly ResearchGraphVersion[]
  operationStatus?: ResearchOperationStatus | null
  operationError?: string | null
  review?: ResearchReview | null
  reviewFilters?: ResearchReviewFilters
  reviewError?: string | null
  reviewNotes?: readonly ResearchReviewNote[]
  savedViews?: readonly ResearchReviewSavedView[]
  noteEventId?: string | null
  editingNoteId?: string | null
  noteDraft?: string
  savedViewName?: string
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
  onReviewFilters?: (filters: ResearchReviewFilters) => void
  onReviewMore?: () => void
  onStartNote?: (eventId: string) => void
  onEditNote?: (note: ResearchReviewNote) => void
  onCancelNote?: () => void
  onNoteDraft?: (body: string) => void
  onSubmitNote?: () => void
  onDeleteNote?: (note: ResearchReviewNote) => void
  onSavedViewName?: (name: string) => void
  onSaveView?: () => void
  onApplyView?: (view: ResearchReviewSavedView) => void
  onDeleteView?: (view: ResearchReviewSavedView) => void
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
        <section aria-label="Daily research review" className="space-y-3">
          <div className="stat-label">Daily research review</div>
          <p className="text-muted">Project facts and current queues derived from persisted server ledgers.</p>
          {reviewError && <p role="alert" className="text-amber-300">{reviewError}</p>}
          {review?.source_errors.map((item) => <p
            role="alert" className="text-amber-300" key={`${item.source}:${item.source_id}`}
          >{item.code}: {item.source} {item.source_id}</p>)}
          {review && <>
            <div className="grid min-w-0 grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-4">
              <div className="rounded border border-edge p-2">
                <p className="font-medium">Failed operation</p>
                {review.queues.failed_operation
                  ? <p role="alert" className="break-words text-amber-300">
                    {review.queues.failed_operation.failure?.code} · {review.queues.failed_operation.stage}
                  </p>
                  : <p className="text-muted">None</p>}
              </div>
              <div className="rounded border border-edge p-2">
                <p className="font-medium">Runs needing review · {review.queues.review_needed_runs.length}</p>
                {review.queues.review_needed_runs.map((item) => <button
                  type="button" className="btn mt-1" key={item.run_id}
                  onClick={() => onSelect?.(item.run_id)}
                >Run {item.run_id} · {item.status}</button>)}
              </div>
              <div className="rounded border border-edge p-2">
                <p className="font-medium">Pending decisions · {review.queues.pending_candidates.length}</p>
                {review.queues.pending_candidates.map((item) => <button
                  type="button" className="btn mt-1" key={item.candidate_id}
                  onClick={() => onSelect?.(item.run_id)}
                >Candidate {item.candidate_id} · run {item.run_id}</button>)}
              </div>
              <div className="rounded border border-edge p-2">
                <p className="font-medium">Active findings · {review.queues.active_findings.length}</p>
                {review.queues.active_findings.map((item) => <button
                  type="button" className="btn mt-1" key={item.finding_id}
                  onClick={() => onSelect?.(item.evidence_run_id)}
                >Finding {item.finding_id} · run {item.evidence_run_id}</button>)}
              </div>
            </div>
            <section aria-label="Saved review views" className="space-y-2 rounded border border-edge p-2">
              <p className="font-medium">Saved review views</p>
              <div className="flex min-w-0 flex-wrap gap-2">
                <label htmlFor="saved-review-name">View name</label>
                <input
                  id="saved-review-name" maxLength={80} value={savedViewName}
                  onChange={(event) => onSavedViewName?.(event.target.value)}
                />
                <button
                  type="button" className="btn" disabled={busy || !savedViewName.trim()}
                  onClick={onSaveView}
                >Save current filters</button>
              </div>
              {savedViews.length === 0 && <p className="text-muted">No saved views.</p>}
              <ul className="flex min-w-0 flex-wrap gap-2">
                {savedViews.map((view) => <li key={view.view_id} className="break-words">
                  <button type="button" className="btn" onClick={() => onApplyView?.(view)}>
                    Apply {view.name}
                  </button>{' '}
                  <button type="button" className="btn" onClick={() => onDeleteView?.(view)}>
                    Delete {view.name}
                  </button>
                </li>)}
              </ul>
            </section>
            <div className="flex min-w-0 flex-wrap gap-2">
              <label>Event type <select
                value={reviewFilters.event_type ?? ''}
                onChange={(event) => onReviewFilters?.({
                  ...reviewFilters,
                  event_type: (event.target.value || undefined) as ResearchReviewEventType | undefined,
                  cursor: undefined,
                })}
              >
                <option value="">All event types</option>
                <option value="graph_version_published">Graph publications</option>
                <option value="experiment_run">Experiment runs</option>
                <option value="finding_created">Findings</option>
                <option value="candidate_created">Candidate creation</option>
                <option value="candidate_decided">Candidate decisions</option>
              </select></label>
              <label>Status <select
                value={reviewFilters.status ?? ''}
                onChange={(event) => onReviewFilters?.({
                  ...reviewFilters, status: event.target.value || undefined, cursor: undefined,
                })}
              >
                <option value="">All statuses</option>
                {['published', 'pending', 'running', 'failed', 'completed', 'needs_review',
                  'active', 'superseded', 'created', 'shadow', 'approved', 'rejected'].map(
                  (value) => <option key={value} value={value}>{value.replace('_', ' ')}</option>,
                )}
              </select></label>
              <label>After (UTC) <input
                type="datetime-local" value={reviewFilters.after ?? ''}
                onChange={(event) => onReviewFilters?.({
                  ...reviewFilters, after: event.target.value || undefined, cursor: undefined,
                })}
              /></label>
              <label>Before (UTC) <input
                type="datetime-local" value={reviewFilters.before ?? ''}
                onChange={(event) => onReviewFilters?.({
                  ...reviewFilters, before: event.target.value || undefined, cursor: undefined,
                })}
              /></label>
            </div>
            {review.timeline.events.length === 0
              ? <p className="text-muted">No project events match these filters.</p>
              : <ol aria-label="Project event timeline" className="space-y-2">
                {review.timeline.events.map((item) => <li
                  className="min-w-0 rounded border border-edge p-2" key={item.event_id}
                >
                  <p className="break-words font-medium">{item.summary}</p>
                  <p className="break-all text-muted">{item.occurred_at} · {item.status}</p>
                  {item.references.run_id !== null && <button
                    type="button" className="btn mt-1"
                    onClick={() => onSelect?.(item.references.run_id!)}
                  >Open run {item.references.run_id}</button>}
                  {item.references.graph && <p className="break-all text-muted">
                    {item.references.graph.identifier} v{item.references.graph.version} · {' '}
                    {item.references.graph.content_address}
                  </p>}
                  {item.references.graph && orderedVersions.some((version) => (
                    version.identifier === item.references.graph?.identifier
                    && version.version === item.references.graph.version
                  )) && <button type="button" className="btn mt-1" onClick={() => {
                    setRightVersion(item.references.graph!.version)
                    setRightRun(null)
                  }}>Use version {item.references.graph.version} in comparison</button>}
                  <div className="mt-2 space-y-1 border-t border-edge/50 pt-2">
                    {reviewNotes.filter((note) => note.event_id === item.event_id).map((note) => (
                      <div key={note.note_id} className="rounded bg-panel2 p-2">
                        <p className="whitespace-pre-wrap break-words">{note.body}</p>
                        <button type="button" className="btn mt-1" onClick={() => onEditNote?.(note)}>
                          Edit note
                        </button>{' '}
                        <button type="button" className="btn mt-1" onClick={() => onDeleteNote?.(note)}>
                          Delete note
                        </button>
                      </div>
                    ))}
                    <button type="button" className="btn" onClick={() => onStartNote?.(item.event_id)}>
                      Add note
                    </button>
                  </div>
                </li>)}
              </ol>}
            {review.timeline.next_cursor && <button
              type="button" className="btn" onClick={onReviewMore}
            >Load older events</button>}
            {reviewNotes.some((note) => note.anchor_state === 'missing') && <section
              aria-label="Notes with missing source events" className="space-y-2"
            >
              <p className="font-medium">Notes with missing source events</p>
              {reviewNotes.filter((note) => note.anchor_state === 'missing').map((note) => <div
                key={note.note_id} className="rounded border border-amber-500/40 p-2"
              >
                <p className="text-amber-300">Source event unavailable · {note.event_id}</p>
                <p className="whitespace-pre-wrap break-words">{note.body}</p>
                <button type="button" className="btn mt-1" onClick={() => onEditNote?.(note)}>
                  Edit note
                </button>{' '}
                <button type="button" className="btn mt-1" onClick={() => onDeleteNote?.(note)}>
                  Delete note
                </button>
              </div>)}
            </section>}
            {noteEventId && <section aria-label="Review note editor" className="space-y-2 rounded border border-edge p-2">
              <label htmlFor="review-note-body">
                {editingNoteId ? 'Edit review note' : 'Add review note'}
              </label>
              <textarea
                id="review-note-body" className="min-h-20 w-full rounded border border-edge bg-panel2 p-2"
                maxLength={4000} value={noteDraft}
                onChange={(event) => onNoteDraft?.(event.target.value)}
              />
              <button
                type="button" className="btn" disabled={busy || !noteDraft.trim()}
                onClick={onSubmitNote}
              >Save note</button>{' '}
              <button type="button" className="btn" disabled={busy} onClick={onCancelNote}>
                Cancel note
              </button>
            </section>}
          </>}
        </section>
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
  const [review, setReview] = useState<ResearchReview | null>(null)
  const reviewRef = useRef<ResearchReview | null>(null)
  const reviewRequest = useRef(0)
  const [reviewFilters, setReviewFilters] = useState<ResearchReviewFilters>({ limit: 25 })
  const [reviewError, setReviewError] = useState<string | null>(null)
  const [reviewNotes, setReviewNotes] = useState<ResearchReviewNote[]>([])
  const [savedViews, setSavedViews] = useState<ResearchReviewSavedView[]>([])
  const [noteEventId, setNoteEventId] = useState<string | null>(null)
  const [editingNoteId, setEditingNoteId] = useState<string | null>(null)
  const [noteDraft, setNoteDraft] = useState('')
  const [savedViewName, setSavedViewName] = useState('')
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

  const refreshReviewArtifacts = async () => {
    const [notes, views] = await Promise.allSettled([
      getResearchReviewNotes(projectId), getResearchReviewSavedViews(projectId),
    ])
    if (notes.status === 'fulfilled') setReviewNotes(notes.value.notes)
    if (views.status === 'fulfilled') setSavedViews(views.value.views)
    const rejected = [notes, views].find((result) => result.status === 'rejected')
    if (rejected?.status === 'rejected') {
      setError(rejected.reason instanceof Error
        ? rejected.reason.message : 'Review writing request failed')
    }
  }

  useEffect(() => {
    refresh().catch((cause) => {
      setError(cause instanceof Error ? cause.message : 'Research history request failed')
    })
    void refreshReviewArtifacts()
  }, [projectId, graphIdentifier])

  const loadReview = async (
    filters: ResearchReviewFilters, append = false, preservePage = false,
  ) => {
    const requestId = ++reviewRequest.current
    setReviewError(null)
    try {
      const currentCount = reviewRef.current?.timeline.events.length ?? 0
      const requestFilters = preservePage && currentCount > (filters.limit ?? 25)
        ? { ...filters, limit: Math.min(100, currentCount) }
        : filters
      const response = await getResearchReview(projectId, requestFilters)
      if (requestId !== reviewRequest.current) return
      const next = reviewRef.current && (append || preservePage)
        ? mergeResearchReview(reviewRef.current, response, append ? 'append' : 'preserve')
        : response
      reviewRef.current = next
      setReview(next)
    } catch (cause) {
      if (requestId !== reviewRequest.current) return
      setReviewError(cause instanceof Error ? cause.message : 'Daily review request failed')
    }
  }

  useEffect(() => {
    let disposed = false
    const poll = () => {
      if (!disposed) void loadReview(reviewFilters, false, true)
    }
    poll()
    const timer = window.setInterval(poll, 10_000)
    return () => {
      disposed = true
      window.clearInterval(timer)
    }
  }, [projectId, reviewFilters.event_type, reviewFilters.status,
    reviewFilters.after, reviewFilters.before, reviewFilters.limit])

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
      await loadReview(reviewFilters)
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
      await loadReview(reviewFilters)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Finding request failed')
    } finally { setBusy(false) }
  }

  const cancelNote = () => {
    setNoteEventId(null)
    setEditingNoteId(null)
    setNoteDraft('')
  }

  const submitNote = async () => {
    if (!noteEventId || !noteDraft.trim()) return
    setBusy(true); setError(null)
    try {
      if (editingNoteId) {
        const note = reviewNotes.find((item) => item.note_id === editingNoteId)
        if (!note) return
        await updateResearchReviewNote(
          projectId, note.note_id, note.revision, noteDraft.trim(),
        )
      } else {
        await createResearchReviewNote(projectId, noteEventId, noteDraft.trim())
      }
      setReviewNotes((await getResearchReviewNotes(projectId)).notes)
      cancelNote()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Review note request failed')
    } finally { setBusy(false) }
  }

  const removeNote = async (note: ResearchReviewNote) => {
    setBusy(true); setError(null)
    try {
      await deleteResearchReviewNote(projectId, note.note_id, note.revision)
      setReviewNotes((await getResearchReviewNotes(projectId)).notes)
      if (editingNoteId === note.note_id) cancelNote()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Review note delete failed')
    } finally { setBusy(false) }
  }

  const saveView = async () => {
    if (!savedViewName.trim()) return
    setBusy(true); setError(null)
    try {
      const { cursor: _cursor, ...filters } = reviewFilters
      await createResearchReviewSavedView(projectId, savedViewName.trim(), filters)
      setSavedViews((await getResearchReviewSavedViews(projectId)).views)
      setSavedViewName('')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Saved view request failed')
    } finally { setBusy(false) }
  }

  const removeView = async (view: ResearchReviewSavedView) => {
    setBusy(true); setError(null)
    try {
      await deleteResearchReviewSavedView(projectId, view.view_id, view.revision)
      setSavedViews((await getResearchReviewSavedViews(projectId)).views)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Saved view delete failed')
    } finally { setBusy(false) }
  }

  return <ResearchEvidenceSurface
    runs={runs}
    detail={detail}
    comparison={comparison}
    findings={findings}
    versions={versions}
    operationStatus={review?.global_operations ?? null}
    operationError={null}
    review={review}
    reviewFilters={reviewFilters}
    reviewError={reviewError}
    reviewNotes={reviewNotes}
    savedViews={savedViews}
    noteEventId={noteEventId}
    editingNoteId={editingNoteId}
    noteDraft={noteDraft}
    savedViewName={savedViewName}
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
    onReviewFilters={setReviewFilters}
    onReviewMore={() => {
      if (!review?.timeline.next_cursor) return
      void loadReview({ ...reviewFilters, cursor: review.timeline.next_cursor }, true)
    }}
    onStartNote={(eventId) => {
      setNoteEventId(eventId); setEditingNoteId(null); setNoteDraft(''); setError(null)
    }}
    onEditNote={(note) => {
      setNoteEventId(note.event_id); setEditingNoteId(note.note_id)
      setNoteDraft(note.body); setError(null)
    }}
    onCancelNote={cancelNote}
    onNoteDraft={setNoteDraft}
    onSubmitNote={submitNote}
    onDeleteNote={removeNote}
    onSavedViewName={setSavedViewName}
    onSaveView={saveView}
    onApplyView={(view) => setReviewFilters({
      event_type: view.filters.event_type ?? undefined,
      status: view.filters.status ?? undefined,
      after: view.filters.after?.slice(0, 16) ?? undefined,
      before: view.filters.before?.slice(0, 16) ?? undefined,
      limit: view.filters.limit,
    })}
    onDeleteView={removeView}
  />
}
