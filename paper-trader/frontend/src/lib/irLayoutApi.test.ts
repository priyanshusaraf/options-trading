import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  IrLayoutConflict,
  getIrGraphLayout,
  putIrGraphLayout,
  type IrGraphLayout,
} from './api'

const LAYOUT: IrGraphLayout = {
  graph_identifier: 'strategy.example',
  graph_version: 4,
  revision: 2,
  positions: [{ instance_id: 'signal', x: 120, y: 48 }],
  groups: [],
}

afterEach(() => vi.unstubAllGlobals())

describe('IR graph layout transport', () => {
  it('loads a versioned layout through an encoded graph path', async () => {
    const fetchLayout = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => LAYOUT,
    } as Response)
    vi.stubGlobal('fetch', fetchLayout)

    await expect(getIrGraphLayout('strategy/future graph', 4)).resolves.toEqual(LAYOUT)
    expect(fetchLayout).toHaveBeenCalledWith(
      '/api/ir/graphs/strategy%2Ffuture%20graph/versions/4/layout',
      { headers: {} },
    )
  })

  it('replaces sparse positions against the caller revision', async () => {
    const fetchLayout = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ ...LAYOUT, revision: 3 }),
    } as Response)
    vi.stubGlobal('fetch', fetchLayout)

    await putIrGraphLayout('strategy.example', 4, 2, LAYOUT.positions)

    expect(fetchLayout).toHaveBeenCalledWith(
      '/api/ir/graphs/strategy.example/versions/4/layout',
      {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ base_revision: 2, positions: LAYOUT.positions }),
      },
    )
  })

  it('exposes a 409 as a typed conflict with the server revision', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 409,
      json: async () => ({
        detail: 'layout revision conflict',
        current_revision: 7,
      }),
    } as Response))

    const failure = await putIrGraphLayout(
      'strategy.example', 4, 2, LAYOUT.positions,
    ).catch((reason: unknown) => reason)

    expect(failure).toBeInstanceOf(IrLayoutConflict)
    expect(failure).toMatchObject({ currentRevision: 7 })
  })

  it('rejects other failed responses with the backend detail', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      json: async () => ({ detail: 'layout contains an unknown node' }),
    } as Response))

    await expect(getIrGraphLayout('strategy.example', 4)).rejects.toThrow(
      'layout contains an unknown node',
    )
  })
})
