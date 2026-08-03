import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { EditorApiError, type IrEditorDocument } from '../lib/api'
import { GraphEditControls } from './GraphEditControls'
import { beginGraphEditor, type GraphEditorState } from './graphEditorState'

const DOCUMENT: IrEditorDocument = {
  project_id: 'project.catalogue',
  identifier: 'strategy.example',
  display_name: 'Example',
  draft_revision: 3,
  version: 7,
  content_address: 'sha256:example',
  authored_graph: {
    identifier: 'strategy.example', version: 7, display_name: 'Example',
    nodes: [{
      instance_id: 'n_ema',
      component: { identifier: 'indicator.ema', version: 1 },
      overrides: { length: 50 },
    }],
  },
  view: {
    identifier: 'strategy.example', version: 7, display_name: 'Example',
    warmup: 50, layers: 1, inputs: [], outputs: [],
    nodes: [{
      instance_id: 'n_ema/n_internal', label: 'internal', container: 'n_ema',
      definition: 'smoothing.wilder v1', params: { length: 14 }, warmup: 14,
      purity: 'pure', cache_id: 'sha256:derived', derived: true,
      layer: 0, row: 0, placed: null,
    }],
    edges: [],
  },
  editable_nodes: [{
    instance_id: 'n_ema',
    component_identifier: 'indicator.ema',
    component_version: 1,
    parameters: [{
      identifier: 'length', kind: 'length', default: 20, value: 50, overridden: true,
    }, {
      identifier: 'offset', kind: 'integer', default: 0, value: 0, overridden: false,
    }],
  }],
  layout: {
    graph_identifier: 'strategy.example', graph_version: 7, revision: 1, positions: [],
  },
  command_receipt: null,
}

const renderControls = (state: GraphEditorState) => renderToStaticMarkup(
  React.createElement(GraphEditControls, {
    state,
    onDisplayName: () => undefined,
    onSetOverride: () => undefined,
    onClearOverride: () => undefined,
    onUndo: () => undefined,
    onRedo: () => undefined,
    onReload: () => undefined,
  }),
)

describe('GraphEditControls', () => {
  it('renders accessible display-name and authored parameter controls', () => {
    const html = renderControls(beginGraphEditor(DOCUMENT))

    expect(html).toContain('<label for="graph-display-name"')
    expect(html).toContain('name="graph-display-name"')
    expect(html).toContain('Update display name')
    expect(html).toContain('Explicit override')
    expect(html).toContain('Inherited/default')
    expect(html).toContain('aria-label="Set n_ema length override"')
    expect(html).toContain('aria-label="Clear n_ema length override"')
    expect(html).toContain('aria-label="Set n_ema offset override"')
    expect(html).not.toContain('Set n_ema/n_internal length override')
  })

  it('uses keyboard-operable history buttons with native disabled semantics', () => {
    const html = renderControls(beginGraphEditor(DOCUMENT))

    expect(html).toMatch(/<button[^>]*disabled=""[^>]*>Undo<\/button>/)
    expect(html).toMatch(/<button[^>]*disabled=""[^>]*>Redo<\/button>/)
    expect(html).toContain('Reload server')
  })

  it('disables mutations and announces pending publication', () => {
    const ready = beginGraphEditor(DOCUMENT)
    const state: GraphEditorState = {
      ...ready,
      phase: 'saving',
      pending: { requestId: 1, kind: 'publish', historyReceipt: null },
    }
    const html = renderControls(state)

    expect(html).toContain('Publishing editor changes')
    expect(html).toContain('aria-live="polite"')
    expect(html).toMatch(/aria-label="Set n_ema length override"[^>]*disabled=""/)
  })

  it('associates exact validation details with the affected field', () => {
    const ready = beginGraphEditor(DOCUMENT)
    const failure = new EditorApiError('validation', 'Graph validation failed', {
      code: 'IR_VALIDATION_FAILED',
      message: 'Graph validation failed',
      current_revision: null,
      errors: [{
        operation_index: 0,
        clause: 'C11',
        path: ['n_ema', 'overrides', 'length'],
        message: 'Expected a positive integer',
      }],
    })
    const state: GraphEditorState = {
      ...ready,
      phase: 'validation-error',
      draft: {
        kind: 'set-override', instanceId: 'n_ema', parameter: 'length',
        rawValue: '-1', operations: [],
      },
      failure,
    }
    const html = renderControls(state)

    expect(html).toContain('role="alert"')
    expect(html).toContain('C11')
    expect(html).toContain('n_ema.overrides.length')
    expect(html).toContain('Expected a positive integer')
    expect(html).toContain('aria-describedby="override-error-n_ema-length"')
  })

  it('shows conflict recovery without discarding local intent', () => {
    const state: GraphEditorState = {
      ...beginGraphEditor(DOCUMENT),
      phase: 'conflicted',
      failure: new EditorApiError('conflict', 'Graph draft revision conflict'),
    }
    const html = renderControls(state)

    expect(html).toContain('role="alert"')
    expect(html).toContain('Graph draft revision conflict')
    expect(html).toContain('Reload server')
  })
})
