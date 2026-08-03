import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import type {
  ResearchComparison,
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

describe('ResearchEvidenceSurface', () => {
  it('surfaces persisted rejection, gates, provenance, comparison, and accessible decisions', () => {
    const html = renderToStaticMarkup(React.createElement(ResearchEvidenceSurface, {
      runs: [RUN, { ...RUN, run_id: 11 }],
      detail: DETAIL,
      comparison: COMPARISON,
      reason: 'Reviewed evidence',
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
})
