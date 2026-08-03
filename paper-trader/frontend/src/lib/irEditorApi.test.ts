import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  EditorApiError,
  getIrEditorDocument,
  postIrEditorOperations,
  postIrPresentationOperations,
  type IrEditorDocument,
} from './api'

export const DOCUMENT: IrEditorDocument = {
  project_id: 'project.repository_catalogue',
  identifier: 'strategy.example',
  display_name: 'Example',
  draft_revision: 3,
  version: 7,
  content_address: 'sha256:document',
  authored_graph: {
    identifier: 'strategy.example',
    version: 7,
    display_name: 'Example',
    nodes: [{
      instance_id: 'n_ema',
      component: { identifier: 'indicator.ema', version: 1 },
      overrides: { length: 50 },
    }],
  },
  view: {
    identifier: 'strategy.example',
    version: 7,
    display_name: 'Example',
    warmup: 50,
    layers: 1,
    inputs: ['close'],
    outputs: ['signal'],
    nodes: [{
      instance_id: 'n_ema',
      label: 'n_ema',
      container: '',
      definition: 'indicator.ema v1',
      params: { length: 50 },
      warmup: 50,
      purity: 'pure',
      cache_id: 'sha256:node',
      derived: false,
      layer: 0,
      row: 0,
      placed: null,
    }],
    edges: [],
  },
  editable_nodes: [{
    instance_id: 'n_ema',
    component_identifier: 'indicator.ema',
    component_version: 1,
    parameters: [{
      identifier: 'length',
      kind: 'length',
      default: 50,
      value: 50,
      overridden: true,
    }],
    sockets: [],
  }],
  component_catalogue: [],
  graph_sockets: [],
  layout: {
    graph_identifier: 'strategy.example',
    graph_version: 7,
    revision: 1,
    positions: [{ instance_id: 'n_ema', x: 12, y: 24 }],
    groups: [],
  },
  command_receipt: null,
}

afterEach(() => vi.unstubAllGlobals())

describe('IR editor transport', () => {
  it('loads one coherent document through encoded project and graph paths', async () => {
    const fetchEditor = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => DOCUMENT,
    } as Response)
    vi.stubGlobal('fetch', fetchEditor)

    await expect(
      getIrEditorDocument('project/catalogue', 'strategy/future graph'),
    ).resolves.toEqual(DOCUMENT)
    expect(fetchEditor).toHaveBeenCalledWith(
      '/api/ir/projects/project%2Fcatalogue/graphs/strategy%2Ffuture%20graph/editor',
      { headers: {} },
    )
  })

  it('posts only the server revision and complete closed operation batch', async () => {
    const accepted = {
      ...DOCUMENT,
      draft_revision: 4,
      version: 8,
      command_receipt: {
        applied_operations: [{ operation: 'set_display_name', display_name: 'Renamed' }],
        inverse_operations: [{ operation: 'set_display_name', display_name: 'Example' }],
        base_revision: 3,
        draft_revision: 4,
        version: 8,
        content_address: 'sha256:renamed',
        semantic_forward_operations: [{ operation: 'set_display_name', display_name: 'Renamed' }],
        semantic_inverse_operations: [{ operation: 'set_display_name', display_name: 'Example' }],
        presentation_delta: { forward_operations: [], inverse_operations: [] },
        base_version: 7,
        base_presentation_revision: 1,
        presentation_revision: 1,
      },
    } satisfies IrEditorDocument
    const publish = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => accepted,
    } as Response)
    vi.stubGlobal('fetch', publish)

    await expect(postIrEditorOperations(
      'project.repository_catalogue',
      'strategy.example',
      3,
      1,
      [{ operation: 'set_display_name', display_name: 'Renamed' }],
    )).resolves.toEqual(accepted)
    expect(publish).toHaveBeenCalledWith(
      '/api/ir/projects/project.repository_catalogue/graphs/strategy.example/edits',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          base_revision: 3,
          base_presentation_revision: 1,
          edits: [{ operation: 'set_display_name', display_name: 'Renamed' }],
          presentation_edits: [],
        }),
      },
    )
  })

  it('posts presentation commands without executable identity fields', async () => {
    const publish = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => DOCUMENT,
    } as Response)
    vi.stubGlobal('fetch', publish)

    await postIrPresentationOperations(
      'project.repository_catalogue',
      'strategy.example',
      3,
      1,
      [{
        operation: 'remove_group',
        identifier: 'g_signal',
      }],
    )

    expect(publish).toHaveBeenCalledWith(
      '/api/ir/projects/project.repository_catalogue/graphs/strategy.example/presentation-edits',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          base_revision: 3,
          base_presentation_revision: 1,
          edits: [{ operation: 'remove_group', identifier: 'g_signal' }],
        }),
      },
    )
  })

  it('decodes exact conflict and validation envelopes', async () => {
    const conflictEnvelope = {
      code: 'DRAFT_REVISION_CONFLICT',
      message: 'Graph draft revision conflict',
      current_revision: 9,
      errors: [],
    } as const
    const validationEnvelope = {
      code: 'IR_VALIDATION_FAILED',
      message: 'Graph validation failed',
      current_revision: null,
      errors: [{
        operation_index: 0,
        clause: 'C11',
        path: ['n_ema', 'overrides', 'length'],
        message: 'Expected a positive integer',
      }],
    } as const
    const fetchEditor = vi.fn()
      .mockResolvedValueOnce({
        ok: false, status: 409, json: async () => conflictEnvelope,
      } as Response)
      .mockResolvedValueOnce({
        ok: false, status: 422, json: async () => validationEnvelope,
      } as Response)
    vi.stubGlobal('fetch', fetchEditor)

    const conflict = await postIrEditorOperations(
      'project', 'graph', 3, 1,
      [{ operation: 'set_display_name', display_name: 'Stale' }],
    ).catch((reason: unknown) => reason)
    expect(conflict).toBeInstanceOf(EditorApiError)
    expect(conflict).toMatchObject({ category: 'conflict', envelope: conflictEnvelope })

    const validation = await postIrEditorOperations(
      'project', 'graph', 3, 1,
      [{ operation: 'set_override', instance_id: 'n_ema', parameter: 'length', value: -1 }],
    ).catch((reason: unknown) => reason)
    expect(validation).toBeInstanceOf(EditorApiError)
    expect(validation).toMatchObject({ category: 'validation', envelope: validationEnvelope })
  })

  it('distinguishes non-JSON server failures from network failures', async () => {
    const fetchEditor = vi.fn()
      .mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => { throw new SyntaxError('not JSON') },
      } as unknown as Response)
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => { throw new SyntaxError('truncated JSON') },
      } as unknown as Response)
      .mockRejectedValueOnce(new Error('offline'))
    vi.stubGlobal('fetch', fetchEditor)

    const server = await getIrEditorDocument('project', 'graph')
      .catch((reason: unknown) => reason)
    expect(server).toBeInstanceOf(EditorApiError)
    expect(server).toMatchObject({ category: 'non-json-server' })
    expect((server as Error).message).toBe('Editor request failed (500)')

    const malformedSuccess = await getIrEditorDocument('project', 'graph')
      .catch((reason: unknown) => reason)
    expect(malformedSuccess).toBeInstanceOf(EditorApiError)
    expect(malformedSuccess).toMatchObject({ category: 'non-json-server' })
    expect((malformedSuccess as Error).message).toBe('Editor request failed (200)')

    const network = await getIrEditorDocument('project', 'graph')
      .catch((reason: unknown) => reason)
    expect(network).toBeInstanceOf(EditorApiError)
    expect(network).toMatchObject({ category: 'network' })
    expect((network as Error).message).toBe('offline')
  })
})
