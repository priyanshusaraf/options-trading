import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  compareResearchRuns,
  compareResearchVersions,
  createResearchFinding,
  decideResearchCandidate,
  getResearchOperationStatus,
  getResearchReview,
  getResearchRun,
  getResearchGraphVersions,
  reviseResearchFinding,
} from './api'

afterEach(() => vi.unstubAllGlobals())

describe('research evidence transport', () => {
  it('loads the project review with bounded server filters only', async () => {
    const review = { project_id: 'project.alpha', timeline: { events: [] } }
    const request = vi.fn().mockResolvedValue({
      ok: true, json: async () => review,
    } as Response)
    vi.stubGlobal('fetch', request)

    await expect(getResearchReview('project/alpha', {
      event_type: 'experiment_run', status: 'failed', after: '2026-08-01', limit: 25,
    })).resolves.toEqual(review)
    expect(request).toHaveBeenCalledWith(
      '/api/ir/projects/project%2Falpha/review?event_type=experiment_run&status=failed&after=2026-08-01&limit=25',
      { headers: {} },
    )
  })

  it('loads operation receipts from the closed read-only status route', async () => {
    const status = { state: 'never_run', active: null, last: null }
    const request = vi.fn().mockResolvedValue({
      ok: true, json: async () => status,
    } as Response)
    vi.stubGlobal('fetch', request)

    await expect(getResearchOperationStatus()).resolves.toEqual(status)
    expect(request).toHaveBeenCalledWith(
      '/api/research/operations/status',
      { headers: {} },
    )
  })

  it('loads persisted detail from an encoded project-owned path', async () => {
    const detail = { run_id: 4, evidence_state: 'verified' }
    const request = vi.fn().mockResolvedValue({
      ok: true, json: async () => detail,
    } as Response)
    vi.stubGlobal('fetch', request)

    await expect(getResearchRun('project/alpha', 4)).resolves.toEqual(detail)
    expect(request).toHaveBeenCalledWith(
      '/api/ir/projects/project%2Falpha/experiments/4',
      { headers: {} },
    )
  })

  it('submits run ids only for server-authoritative comparison', async () => {
    const response = { equivalent: true, incomparable: [], differences: [] }
    const request = vi.fn().mockResolvedValue({
      ok: true, json: async () => response,
    } as Response)
    vi.stubGlobal('fetch', request)

    await expect(compareResearchRuns('project.alpha', 3, 7)).resolves.toEqual(response)
    expect(request).toHaveBeenCalledWith(
      '/api/ir/projects/project.alpha/experiments/comparisons',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ left_run_id: 3, right_run_id: 7 }),
      },
    )
  })

  it('lists server-owned versions and submits selectors without graph identity claims', async () => {
    const response = { equivalent: true, incomparable: [], differences: [] }
    const request = vi.fn().mockResolvedValue({
      ok: true, json: async () => response,
    } as Response)
    vi.stubGlobal('fetch', request)

    await getResearchGraphVersions('project.alpha', 'strategy/alpha')
    await compareResearchVersions(
      'project.alpha',
      { graph_identifier: 'strategy/alpha', graph_version: 2, run_id: 7 },
      { graph_identifier: 'strategy/alpha', graph_version: 3, run_id: 9 },
    )

    expect(request).toHaveBeenNthCalledWith(
      1,
      '/api/ir/projects/project.alpha/graphs/strategy%2Falpha/versions',
      { headers: {} },
    )
    expect(request).toHaveBeenNthCalledWith(
      2,
      '/api/ir/projects/project.alpha/version-comparisons',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          left: { graph_identifier: 'strategy/alpha', graph_version: 2, run_id: 7 },
          right: { graph_identifier: 'strategy/alpha', graph_version: 3, run_id: 9 },
        }),
      },
    )
  })

  it('submits a pending decision and reason without client evidence or scorecard', async () => {
    const response = { candidate_id: 8, status: 'rejected', decision: {} }
    const request = vi.fn().mockResolvedValue({
      ok: true, json: async () => response,
    } as Response)
    vi.stubGlobal('fetch', request)

    await decideResearchCandidate('project.alpha', 8, 'rejected', 'Insufficient breadth')

    expect(request).toHaveBeenCalledWith(
      '/api/ir/projects/project.alpha/candidates/8/decisions',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          expected_status: 'pending',
          decision: 'rejected',
          reason: 'Insufficient breadth',
        }),
      },
    )
  })

  it('surfaces exact server conflict feedback', async () => {
    const request = vi.fn().mockResolvedValue({
      ok: false,
      status: 409,
      json: async () => ({
        code: 'CANDIDATE_STATUS_CONFLICT',
        message: 'candidate is not pending at the expected status',
      }),
    } as Response)
    vi.stubGlobal('fetch', request)

    await expect(
      decideResearchCandidate('project.alpha', 8, 'approved', 'Reviewed'),
    ).rejects.toThrow('candidate is not pending at the expected status')
  })

  it('submits finding interpretation and revision intent without identity claims', async () => {
    const request = vi.fn().mockResolvedValue({
      ok: true, json: async () => ({ finding_id: 4 }),
    } as Response)
    vi.stubGlobal('fetch', request)

    await createResearchFinding('project.alpha', 12, 'Evidence is narrow', 'negative')
    await reviseResearchFinding('project.alpha', 4, 'Evidence is broader', 'positive')

    expect(request).toHaveBeenNthCalledWith(
      1,
      '/api/ir/projects/project.alpha/experiments/12/findings',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ statement: 'Evidence is narrow', polarity: 'negative' }),
      },
    )
    expect(request).toHaveBeenNthCalledWith(
      2,
      '/api/ir/projects/project.alpha/findings/4/revisions',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          expected_superseded_by: null,
          statement: 'Evidence is broader',
          polarity: 'positive',
        }),
      },
    )
  })
})
