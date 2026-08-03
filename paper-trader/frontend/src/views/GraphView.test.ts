import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import type { IrGraphView } from '../lib/api'
import { GraphCanvas, GraphViewState } from './GraphView'

const GRAPH: IrGraphView = {
  identifier: 'strategy.example',
  version: 4,
  display_name: 'Example Strategy',
  warmup: 21,
  layers: 2,
  inputs: ['close'],
  outputs: ['signal'],
  nodes: [
    {
      instance_id: 'prices',
      label: 'prices',
      container: '',
      definition: 'source.close v1',
      params: {},
      warmup: 0,
      purity: 'pure',
      cache_id: 'sha256:source-cache-id',
      derived: false,
      layer: 0,
      row: 0,
      placed: null,
    },
    {
      instance_id: 'risk/threshold',
      label: 'threshold',
      container: 'risk',
      definition: 'signal.threshold v3',
      params: { period: 20, bands: [1.5, 2] },
      warmup: 21,
      purity: 'account_state',
      cache_id: 'sha256:full-target-cache-id',
      derived: true,
      layer: 1,
      row: 0,
      placed: null,
    },
  ],
  edges: [{
    source: 'prices',
    target: 'risk/threshold',
    source_socket: 'close',
    target_socket: 'value',
    derived: true,
  }],
}

describe('GraphCanvas', () => {
  it('renders the graph identity, contract totals, and every inspection field', () => {
    const html = renderToStaticMarkup(React.createElement(GraphCanvas, { graph: GRAPH }))

    expect(html).toContain('<article')
    expect(html).toContain('Example Strategy')
    expect(html).toContain('strategy.example v4')
    expect(html).toContain('2 nodes')
    expect(html).toContain('1 edge')
    expect(html).toContain('2 layers')
    expect(html).toContain('21 bars')
    expect(html).toContain('risk/threshold')
    expect(html).toContain('signal.threshold v3')
    expect(html).toContain('period')
    expect(html).toContain('20')
    expect(html).toContain('bands')
    expect(html).toContain('[1.5,2]')
    expect(html).toContain('sha256:full-target-cache-id')
    expect(html).toContain('Derived')
    expect(html).toContain('Impure · account state')
  })

  it('keeps wires decorative and exposes their sockets in a table', () => {
    const html = renderToStaticMarkup(React.createElement(GraphCanvas, { graph: GRAPH }))

    expect(html).toContain('<svg')
    expect(html).toContain('aria-hidden="true"')
    expect(html).toContain('<table')
    expect(html).toContain('prices.close')
    expect(html).toContain('risk/threshold.value')
    expect(html).toContain('Derived connection')
  })

  it('contains a canvas wider than 390px inside its own horizontal scroller', () => {
    const html = renderToStaticMarkup(React.createElement(GraphCanvas, { graph: GRAPH }))

    expect(html).toMatch(/overflow-x-auto[^>]*><div class="relative" style="width:720px/)
  })

  it('explains an edge-free graph instead of rendering an unexplained empty table', () => {
    const html = renderToStaticMarkup(React.createElement(GraphCanvas, {
      graph: { ...GRAPH, edges: [] },
    }))

    expect(html).toContain('No connections')
  })
})

describe('GraphViewState', () => {
  it('announces loading while no response has arrived', () => {
    const html = renderToStaticMarkup(React.createElement(GraphViewState, {
      graph: null,
      error: null,
    }))

    expect(html).toContain('aria-label="Loading strategy graph"')
    expect(html).toContain('aria-live="polite"')
  })

  it('renders fetch failures as alerts', () => {
    const html = renderToStaticMarkup(React.createElement(GraphViewState, {
      graph: null,
      error: 'route unavailable',
    }))

    expect(html).toContain('role="alert"')
    expect(html).toContain('route unavailable')
  })

  it('renders a successful empty graph as an explicit status', () => {
    const html = renderToStaticMarkup(React.createElement(GraphViewState, {
      graph: { ...GRAPH, nodes: [], edges: [] },
      error: null,
    }))

    expect(html).toContain('role="status"')
    expect(html).toContain('has no nodes')
  })
})
