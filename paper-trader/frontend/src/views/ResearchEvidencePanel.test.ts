import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import type {
  ResearchComparison,
  ResearchFinding,
  ResearchRunDetail,
  ResearchRunSummary,
} from '../lib/api'
import { ResearchEvidenceSurface } from './ResearchEvidencePanel'

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

describe('ResearchEvidenceSurface', () => {
  it('surfaces persisted rejection, gates, provenance, comparison, and accessible decisions', () => {
    const html = renderToStaticMarkup(React.createElement(ResearchEvidenceSurface, {
      runs: [RUN, { ...RUN, run_id: 11 }],
      detail: DETAIL,
      comparison: COMPARISON,
      findings: FINDINGS,
      reason: 'Reviewed evidence',
      findingStatement: 'A new interpretation',
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
