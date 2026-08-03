import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import type {
  ResearchComparison,
  ResearchFinding,
  ResearchOperationStatus,
  ResearchReview,
  ResearchReviewNote,
  ResearchReviewSavedView,
  ResearchReviewSearch,
  ResearchRunDetail,
  ResearchRunSummary,
} from '../lib/api'
import { mergeResearchReview, ResearchEvidenceSurface } from './ResearchEvidencePanel'

const RUN: ResearchRunSummary = {
  run_id: 12,
  spec_id: 'spec-12',
  status: 'completed',
  decision: 'archive',
  evidence_state: 'verified',
  graph: {
    project_id: 'project.alpha',
    identifier: 'strategy.alpha',
    version: 4,
    content_address: 'sha256:graph',
  },
  candidate: {
    candidate_id: 7,
    status: 'pending',
    decision: null,
  },
}

const DETAIL: ResearchRunDetail = {
  ...RUN,
  evidence: {
    provenance: {
      datasets: { NIFTY: { content_hash: 'data-1' } },
      cost_assumptions: { slippage_bps: 5 },
      gates: { pbo_threshold: 0.3 },
    },
    results: {
      rejected: [{ instrument: 'NIFTY', reason: 'failed validation: pbo' }],
      breadth: { n_effective: 1.4 },
      instruments: [{
        instrument: 'NIFTY',
        qualification: { qualified: true, trades: 33 },
        validation: { gates: { pbo: { passed: false, value: 0.51 } } },
        scorecard: { dsr: 0.12 },
      }],
    },
  },
}

const COMPARISON: ResearchComparison = {
  equivalent: false,
  incomparable: ['DATASET_IDENTITY_CHANGED'],
  differences: [{
    dimension: 'datasets',
    path: ['identities', 'NIFTY', 'content_hash'],
    left: 'data-1',
    right: 'data-2',
  }],
}

const FINDINGS: ResearchFinding[] = [{
  finding_id: 21,
  statement: 'Initial narrow interpretation',
  polarity: 'negative',
  confidence: 0.52,
  evidence_run_id: 12,
  superseded_by: 22,
  status: 'superseded',
  created_at: '2026-08-03T00:00:00',
  binding: {
    run_id: 12,
    spec_id: 'spec-12',
    evidence_content_address: 'sha256:evidence-12',
    graph: RUN.graph,
  },
}, {
  finding_id: 22,
  statement: 'Revised exact interpretation',
  polarity: 'positive',
  confidence: 0.52,
  evidence_run_id: 12,
  superseded_by: null,
  status: 'active',
  created_at: '2026-08-03T00:01:00',
  binding: {
    run_id: 12,
    spec_id: 'spec-12',
    evidence_content_address: 'sha256:evidence-12',
    graph: RUN.graph,
  },
}]

const OPERATION: ResearchOperationStatus = {
  state: 'available',
  active: {
    operation_id: 'op-running', trigger: 'nightly', state: 'running',
    stage: 'experiments', started_at: '2026-08-03T01:00:00Z', completed_at: null,
    build: 'abc123', provider_mode: 'mock', plan: null,
    completed_run_ids: [12], failure: null,
  },
  last: {
    operation_id: 'op-last', trigger: 'manual_script', state: 'failed',
    stage: 'generation', started_at: '2026-08-02T01:00:00Z',
    completed_at: '2026-08-02T01:05:00Z', build: 'def456', provider_mode: 'kite',
    plan: null, completed_run_ids: [11],
    failure: { stage: 'generation', code: 'RESEARCH_GENERATION_FAILED', message: 'research generation failed' },
  },
}

const REVIEW: ResearchReview = {
  project_id: 'project.alpha',
  as_of: '2026-08-03T02:00:00Z',
  timeline: {
    events: [{
      event_id: 'candidate:7', type: 'candidate_created',
      occurred_at: '2026-08-03T01:30:00Z', status: 'created',
      summary: 'Candidate 7: created',
      references: {
        graph: { identifier: 'strategy.alpha', version: 4, content_address: 'sha256:graph' },
        run_id: 12, finding_id: null, candidate_id: 7,
      },
    }],
    next_cursor: 'opaque-next',
  },
  queues: {
    review_needed_runs: [{
      run_id: 12, status: 'needs_review', evidence_state: 'verified',
      graph: { identifier: 'strategy.alpha', version: 4, content_address: 'sha256:graph' },
    }],
    pending_candidates: [{
      candidate_id: 7, run_id: 12, status: 'pending',
      graph: { identifier: 'strategy.alpha', version: 4, content_address: 'sha256:graph' },
    }],
    active_findings: [{
      finding_id: 22, evidence_run_id: 12, polarity: 'positive', confidence: 0.52,
      graph: { identifier: 'strategy.alpha', version: 4, content_address: 'sha256:graph' },
    }],
    failed_operation: {
      operation_id: 'op-last', trigger: 'manual_script', stage: 'generation',
      completed_at: '2026-08-02T01:05:00Z', failure: OPERATION.last!.failure,
    },
  },
  global_operations: OPERATION,
  source_errors: [{ source: 'candidate', source_id: '8', code: 'CANDIDATE_DECISION_CORRUPT' }],
}

const REVIEW_NOTES: ResearchReviewNote[] = [{
  note_id: 'note.1', project_id: 'project.alpha', event_id: 'candidate:7',
  event_type: 'candidate_created', body: 'Check the breadth before deciding.',
  created_by: 'owner', revision: 0, anchor_state: 'available',
  created_at: '2026-08-03T02:00:00Z', updated_at: '2026-08-03T02:00:00Z',
}, {
  note_id: 'note.2', project_id: 'project.alpha', event_id: 'run:missing',
  event_type: 'experiment_run', body: 'Retained after source restore.',
  created_by: 'owner', revision: 1, anchor_state: 'missing',
  created_at: '2026-08-03T02:01:00Z', updated_at: '2026-08-03T02:02:00Z',
}]

const SAVED_VIEWS: ResearchReviewSavedView[] = [{
  view_id: 'view.1', project_id: 'project.alpha', name: 'Failed runs',
  filters: {
    event_type: 'experiment_run', status: 'failed', after: null, before: null, limit: 25,
  },
  created_by: 'owner', revision: 0,
  created_at: '2026-08-03T02:00:00Z', updated_at: '2026-08-03T02:00:00Z',
}]

const REVIEW_SEARCH: ResearchReviewSearch = {
  project_id: 'project.alpha',
  query: 'breadth',
  results: [{
    result_id: 'note:note.1', kind: 'note', event_id: 'candidate:7',
    event_type: 'candidate_created', text: 'Check the breadth before deciding.',
    timestamp: '2026-08-03T02:00:00.000000Z', anchor_state: 'available',
    reference: { run_id: null, finding_id: null, candidate_id: null },
  }, {
    result_id: 'event:run:12', kind: 'event', event_id: 'run:12',
    event_type: 'experiment_run', text: 'Run 12 needs review',
    timestamp: '2026-08-03T01:00:00.000000Z', anchor_state: 'available',
    reference: { run_id: 12, finding_id: null, candidate_id: null },
  }, {
    result_id: 'note:note.2', kind: 'note', event_id: 'run:missing',
    event_type: 'experiment_run', text: 'Retained human note',
    timestamp: '2026-08-03T00:00:00.000000Z', anchor_state: 'missing',
    reference: { run_id: null, finding_id: null, candidate_id: null },
  }],
  next_cursor: 'search-next',
  source_errors: [{
    source: 'graph_version', source_id: 'broken', code: 'GRAPH_VERSION_CORRUPT',
  }],
}

describe('ResearchEvidenceSurface', () => {
  it('polling refresh retains loaded older events while updating current facts', () => {
    const old = REVIEW.timeline.events[0]
    const current = {
      ...REVIEW,
      timeline: { events: [old], next_cursor: 'oldest-position' },
    }
    const response = {
      ...REVIEW,
      timeline: {
        events: [
          { ...old, status: 'approved', summary: 'Candidate 7: approved' },
          { ...old, event_id: 'run:13', occurred_at: '2026-08-03T01:31:00Z', summary: 'Run 13' },
        ],
        next_cursor: 'new-page-cursor',
      },
    }

    const merged = mergeResearchReview(current, response, 'preserve')

    expect(merged.timeline.events.map((event) => event.event_id)).toEqual(['run:13', 'candidate:7'])
    expect(merged.timeline.events[1].status).toBe('approved')
    expect(merged.timeline.next_cursor).toBe('oldest-position')
  })

  it('renders accessible queues, closed filters, timeline links and contained source errors', () => {
    const html = renderToStaticMarkup(React.createElement(ResearchEvidenceSurface, {
      runs: [RUN], detail: null, comparison: null, reason: '', review: REVIEW,
      reviewFilters: { event_type: 'candidate_created', status: 'created' },
      reviewNotes: REVIEW_NOTES, savedViews: SAVED_VIEWS,
      noteEventId: 'candidate:7', noteDraft: 'Keep this draft after conflict',
      savedViewName: 'Current review',
      onSelect: () => undefined, onReviewFilters: () => undefined, onReviewMore: () => undefined,
    }))

    expect(html).toContain('Daily research review')
    expect(html).toContain('Failed operation')
    expect(html).toContain('Runs needing review · 1')
    expect(html).toContain('Pending decisions · 1')
    expect(html).toContain('Active findings · 1')
    expect(html).toContain('CANDIDATE_DECISION_CORRUPT')
    expect(html).toContain('aria-label="Project event timeline"')
    expect(html).toContain('Candidate 7: created')
    expect(html).toContain('Open run 12')
    expect(html).toContain('Use version 4 in comparison')
    expect(html).toContain('Load older events')
    expect(html).toContain('Event type')
    expect(html).toContain('Status')
    expect(html).toContain('Saved review views')
    expect(html).toContain('Apply Failed runs')
    expect(html).toContain('Save current filters')
    expect(html).toContain('Check the breadth before deciding.')
    expect(html).toContain('Notes with missing source events')
    expect(html).toContain('Retained after source restore.')
    expect(html).toContain('Keep this draft after conflict')
    expect(html).toContain('Save note')
    expect(html).toContain('grid-cols-1')
    expect(html).toContain('min-w-0')
    expect(html).toContain('break-all')
    expect(html).not.toContain('Start research')
  })

  it('renders accessible bounded search independently with exact feedback and links', () => {
    const html = renderToStaticMarkup(React.createElement(ResearchEvidenceSurface, {
      runs: [RUN], detail: null, comparison: null, reason: '', review: REVIEW,
      searchQuery: 'keep this query', search: REVIEW_SEARCH,
      searchError: 'review search query must contain 2 to 120 normalized characters',
      onSearchQuery: () => undefined, onSearch: () => undefined,
      onSearchClear: () => undefined, onSearchMore: () => undefined,
      onSelect: () => undefined,
    }))

    expect(html).toContain('aria-label="Project review search"')
    expect(html).toContain('for="project-review-search-query"')
    expect(html).toContain('value="keep this query"')
    expect(html).toContain('Search review')
    expect(html).toContain('Clear search')
    expect(html).toContain('review search query must contain 2 to 120 normalized characters')
    expect(html).toContain('Check the breadth before deciding.')
    expect(html).toContain('Open run 12')
    expect(html).toContain('Source event unavailable')
    expect(html).toContain('GRAPH_VERSION_CORRUPT')
    expect(html).toContain('Load more search results')
    expect(html).toContain('min-w-0')
    expect(html).toContain('break-words')
  })

  it('shows explicit never-run state and a completed last receipt', () => {
    const never = renderToStaticMarkup(React.createElement(ResearchEvidenceSurface, {
      runs: [], detail: null, comparison: null, reason: '',
      operationStatus: { state: 'never_run', active: null, last: null },
    }))
    expect(never).toContain('No bounded research operation has run yet.')

    const completed: ResearchOperationStatus = {
      state: 'available', active: null,
      last: { ...OPERATION.last!, state: 'completed', stage: 'completed', failure: null },
    }
    const done = renderToStaticMarkup(React.createElement(ResearchEvidenceSurface, {
      runs: [RUN], detail: null, comparison: null, reason: '',
      operationStatus: completed,
    }))
    expect(done).toContain('Last · completed · completed · manual script')
  })

  it('shows current and last server receipts without operation controls', () => {
    const html = renderToStaticMarkup(React.createElement(ResearchEvidenceSurface, {
      runs: [RUN], detail: DETAIL, comparison: null, reason: '',
      operationStatus: OPERATION,
    }))

    expect(html).toContain('Research operation status')
    expect(html).toContain('Running · experiments · nightly')
    expect(html).toContain('Last · failed · generation · manual script')
    expect(html).toContain('RESEARCH_GENERATION_FAILED: research generation failed')
    expect(html).toContain('Run 12')
    expect(html).not.toContain('Start research')
    expect(html).not.toContain('Cancel research')
  })

  it('contains operation receipt failure without hiding experiment evidence', () => {
    const html = renderToStaticMarkup(React.createElement(ResearchEvidenceSurface, {
      runs: [RUN], detail: DETAIL, comparison: null, reason: '',
      operationStatus: null,
      operationError: 'research operation status is unavailable because its receipt is invalid',
    }))

    expect(html).toContain('research operation status is unavailable')
    expect(html).toContain('Experiment history')
    expect(html).toContain('failed validation: pbo')
  })

  it('surfaces persisted rejection, gates, provenance, comparison, and accessible decisions', () => {
    const html = renderToStaticMarkup(React.createElement(ResearchEvidenceSurface, {
      runs: [RUN, { ...RUN, run_id: 11 }],
      detail: DETAIL,
      comparison: COMPARISON,
      findings: FINDINGS,
      reason: 'Reviewed evidence',
      findingStatement: 'A new interpretation',
      versions: [
        { project_id: 'project.alpha', identifier: 'strategy.alpha', version: 3, content_address: 'sha256:v3' },
        { project_id: 'project.alpha', identifier: 'strategy.alpha', version: 4, content_address: 'sha256:v4' },
      ],
      onSelect: () => undefined,
      onCompare: () => undefined,
      onReason: () => undefined,
      onDecision: () => undefined,
    }))

    expect(html).toContain('Persisted server evidence only')
    expect(html).toContain('failed validation: pbo')
    expect(html).toContain('&quot;pbo&quot;')
    expect(html).toContain('&quot;n_effective&quot;')
    expect(html).toContain('DATASET_IDENTITY_CHANGED')
    expect(html).toContain('datasets.identities.NIFTY.content_hash')
    expect(html).toContain('for="candidate-decision-reason"')
    expect(html).toContain('Approve research candidate')
    expect(html).toContain('Reject research candidate')
    expect(html).toContain('Initial narrow interpretation')
    expect(html).toContain('Superseded by finding 22')
    expect(html).toContain('Revised exact interpretation')
    expect(html).toContain('sha256:evidence-12')
    expect(html).toContain('Record an interpretation')
    expect(html).toContain('Record finding')
    expect(html).toContain('Revise finding 22')
    expect(html).toContain('Compare immutable versions and evidence')
    expect(html).toContain('Left version')
    expect(html).toContain('Right version')
    expect(html).toContain('Graph only')
  })

  it('shows the persisted terminal reason without offering another decision', () => {
    const decided: ResearchRunDetail = {
      ...DETAIL,
      candidate: {
        candidate_id: 7,
        status: 'rejected',
        decision: {
          content_address: 'sha256:decision',
          evidence: {
            actor: 'owner',
            decision: 'rejected',
            decided_at: '2026-08-03T00:00:00Z',
            reason: 'Insufficient breadth.',
          },
        },
      },
    }
    const html = renderToStaticMarkup(React.createElement(ResearchEvidenceSurface, {
      runs: [decided], detail: decided, comparison: null, reason: '',
    }))

    expect(html).toContain('rejected by owner')
    expect(html).toContain('Insufficient breadth.')
    expect(html).not.toContain('Approve research candidate')
  })

  it('renders terminal pipeline failure feedback exactly', () => {
    const failed = {
      ...DETAIL,
      status: 'failed',
      decision: 'needs_review',
      candidate: null,
      evidence: {
        provenance: DETAIL.evidence?.provenance,
        results: { failure: {
          stage: 'validation',
          code: 'RESEARCH_VALIDATION_FAILED',
          message: 'research validation failed',
        } },
      },
    } as ResearchRunDetail
    const html = renderToStaticMarkup(React.createElement(ResearchEvidenceSurface, {
      runs: [failed], detail: failed, comparison: null, reason: '',
    }))

    expect(html).toContain('RESEARCH_VALIDATION_FAILED')
    expect(html).toContain('research validation failed (validation)')
  })

  it('retains revision intent while showing exact server conflict feedback', () => {
    const html = renderToStaticMarkup(React.createElement(ResearchEvidenceSurface, {
      runs: [RUN],
      detail: DETAIL,
      comparison: null,
      findings: FINDINGS,
      reason: '',
      findingStatement: 'Keep this revised interpretation',
      findingPolarity: 'positive',
      editingFindingId: 22,
      error: 'finding was already superseded',
    }))

    expect(html).toContain('role="alert"')
    expect(html).toContain('finding was already superseded')
    expect(html).toContain('Keep this revised interpretation')
    expect(html).toContain('Revise finding 22')
    expect(html).toContain('Save finding revision')
    expect(html).toContain('Cancel revision')
    expect(html).toContain('overflow-x-auto')
  })
})
