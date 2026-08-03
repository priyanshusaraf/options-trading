import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import type { IrEditorDocument, IrGraphLayout, IrGraphView } from '../lib/api'
import {
  GraphCanvas,
  GraphViewState,
  movePointFromPointer,
  movePointWithKey,
} from './GraphView'
import { beginGraphEditor } from './graphEditorState'

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

const LAYOUT: IrGraphLayout = {
  graph_identifier: GRAPH.identifier,
  graph_version: GRAPH.version,
  revision: 3,
  positions: [
    { instance_id: 'prices', x: 444, y: 55 },
    // A derived-node override cannot be authored through the backend contract.
    // Keep the renderer closed even if a malformed response reaches the client.
    { instance_id: 'risk/threshold', x: 999, y: 999 },
  ],
}

const EDITOR_DOCUMENT: IrEditorDocument = {
  project_id: 'project.catalogue',
  identifier: GRAPH.identifier,
  display_name: GRAPH.display_name,
  draft_revision: 2,
  version: GRAPH.version,
  content_address: 'sha256:graph',
  authored_graph: {
    identifier: GRAPH.identifier,
    version: GRAPH.version,
    display_name: GRAPH.display_name,
    nodes: [{
      instance_id: 'prices',
      component: { identifier: 'source.close', version: 1 },
      overrides: { window: 20 },
    }],
  },
  view: GRAPH,
  editable_nodes: [{
    instance_id: 'prices',
    component_identifier: 'source.close',
    component_version: 1,
    parameters: [{
      identifier: 'window', kind: 'length', default: 10, value: 20, overridden: true,
    }],
  }],
  layout: LAYOUT,
  command_receipt: null,
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

  it('applies sparse authored coordinates without mutating graph identity fields', () => {
    const identityBefore = JSON.stringify(GRAPH)

    const html = renderToStaticMarkup(React.createElement(GraphCanvas, {
      graph: GRAPH,
      layout: LAYOUT,
    }))

    expect(html).toContain('left:444px;top:55px')
    expect(html).not.toContain('left:999px;top:999px')
    expect(JSON.stringify(GRAPH)).toBe(identityBefore)
  })

  it('exposes a move handle only for authored nodes', () => {
    const html = renderToStaticMarkup(React.createElement(GraphCanvas, {
      graph: GRAPH,
      layout: LAYOUT,
      onMove: () => undefined,
    }))

    expect(html).toContain('aria-label="Move prices"')
    expect(html).not.toContain('aria-label="Move risk/threshold"')
  })

  it('maps keyboard and pointer movement to deterministic canvas coordinates', () => {
    expect(movePointWithKey({ x: 40, y: 50 }, 'ArrowRight', false)).toEqual({ x: 50, y: 50 })
    expect(movePointWithKey({ x: 40, y: 50 }, 'ArrowUp', true)).toEqual({ x: 40, y: 49 })
    expect(movePointWithKey({ x: 40, y: 50 }, 'Enter', false)).toBeNull()
    expect(movePointFromPointer(
      { x: 40, y: 50 },
      { x: 100, y: 120 },
      { x: 145, y: 105 },
    )).toEqual({ x: 85, y: 35 })
  })

  it('explains an edge-free graph instead of rendering an unexplained empty table', () => {
    const html = renderToStaticMarkup(React.createElement(GraphCanvas, {
      graph: { ...GRAPH, edges: [] },
    }))

    expect(html).toContain('No connections')
  })
})

describe('GraphViewState', () => {
  it('renders coherent persistent editing controls with the accepted graph', () => {
    const html = renderToStaticMarkup(React.createElement(GraphViewState, {
      graph: GRAPH,
      layout: LAYOUT,
      graphEditor: beginGraphEditor(EDITOR_DOCUMENT),
      error: null,
      onDisplayName: () => undefined,
      onSetOverride: () => undefined,
      onClearOverride: () => undefined,
      onUndo: () => undefined,
      onRedo: () => undefined,
      onEditorReload: () => undefined,
    }))

    expect(html).toContain('Graph editing')
    expect(html).toContain('Graph display name')
    expect(html).toContain('aria-label="Set prices window override"')
    expect(html).toContain('Example Strategy')
  })

  it('announces loading while no response has arrived', () => {
    const html = renderToStaticMarkup(React.createElement(GraphViewState, {
      graph: null,
      error: null,
    }))

    expect(html).toContain('aria-label="Loading strategy graph"')
    expect(html).toContain('aria-live="polite"')
  })

  it('keeps announcing loading while the graph layout is still pending', () => {
    const html = renderToStaticMarkup(React.createElement(GraphViewState, {
      graph: GRAPH,
      layout: null,
      error: null,
    }))

    expect(html).toContain('aria-label="Loading strategy graph"')
  })

  it('announces unsaved layout work', () => {
    const html = renderToStaticMarkup(React.createElement(GraphViewState, {
      graph: GRAPH,
      layout: LAYOUT,
      phase: 'dirty',
      error: null,
      onMove: () => undefined,
      onSave: () => undefined,
    }))

    expect(html).toContain('role="status"')
    expect(html).toContain('Unsaved layout')
    expect(html).toContain('Save layout')
  })

  it('renders saving, saved, conflict, and error states without hiding recovery', () => {
    const saving = renderToStaticMarkup(React.createElement(GraphViewState, {
      graph: GRAPH,
      layout: LAYOUT,
      phase: 'saving',
      error: null,
    }))
    const saved = renderToStaticMarkup(React.createElement(GraphViewState, {
      graph: GRAPH,
      layout: LAYOUT,
      phase: 'saved',
      error: null,
    }))
    const conflict = renderToStaticMarkup(React.createElement(GraphViewState, {
      graph: GRAPH,
      layout: LAYOUT,
      phase: 'conflict',
      message: 'revision 7',
      error: null,
      onSave: () => undefined,
      onReload: () => undefined,
    }))
    const failed = renderToStaticMarkup(React.createElement(GraphViewState, {
      graph: GRAPH,
      layout: LAYOUT,
      phase: 'error',
      message: 'network unavailable',
      error: null,
      onSave: () => undefined,
      onReload: () => undefined,
    }))

    expect(saving).toContain('Saving layout')
    expect(saved).toContain('Layout saved')
    expect(conflict).toContain('Local positions are retained')
    expect(conflict).toContain('Retry against latest')
    expect(conflict).toContain('Reload server')
    expect(failed).toContain('network unavailable')
    expect(failed).toContain('Retry save')
    expect(failed).toContain('Reload server')
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
