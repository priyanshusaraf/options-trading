import { afterEach, describe, expect, it, vi } from 'vitest'
import { getIrGraph, type IrGraphView } from './api'

const GRAPH: IrGraphView = {
  identifier: 'strategy.expanding_z_impulse',
  version: 4,
  display_name: 'Expanding Z Impulse',
  warmup: 302,
  layers: 6,
  inputs: ['bars'],
  outputs: ['signal'],
  nodes: [],
  edges: [],
}

afterEach(() => vi.unstubAllGlobals())

describe('getIrGraph', () => {
  it('requests an encoded graph identifier and returns the typed view', async () => {
    const fetchGraph = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => GRAPH,
    } as Response)
    vi.stubGlobal('fetch', fetchGraph)

    await expect(getIrGraph('strategy/future graph')).resolves.toEqual(GRAPH)
    expect(fetchGraph).toHaveBeenCalledWith(
      '/api/ir/graphs/strategy%2Ffuture%20graph',
      { headers: {} },
    )
  })

  it('rejects a non-success response instead of treating its body as a graph', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({ detail: "no IR graph named 'missing'" }),
    } as Response))

    await expect(getIrGraph('missing')).rejects.toThrow("no IR graph named 'missing'")
  })
})
