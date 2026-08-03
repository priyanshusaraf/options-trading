import { describe, expect, it } from 'vitest'
import {
  EditorApiError,
  type IrCommandReceipt,
  type IrEditorDocument,
} from '../lib/api'
import {
  acceptPublication,
  acceptReload,
  beginGraphEditor,
  draftClearOverride,
  draftDisplayName,
  draftSetOverrideJson,
  failEditorRequest,
  startPublish,
  startPresentationCommand,
  startRedo,
  startReload,
  startUndo,
} from './graphEditorState'

const RECEIPT: IrCommandReceipt = {
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
}

const DOCUMENT: IrEditorDocument = {
  project_id: 'project.catalogue',
  identifier: 'strategy.example',
  display_name: 'Example',
  draft_revision: 3,
  version: 7,
  content_address: 'sha256:example',
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
    identifier: 'strategy.example', version: 7, display_name: 'Example',
    warmup: 50, layers: 1, inputs: [], outputs: [], nodes: [], edges: [],
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
    sockets: [],
  }],
  component_catalogue: [],
  graph_sockets: [],
  layout: {
    graph_identifier: 'strategy.example', graph_version: 7, revision: 1,
    positions: [{ instance_id: 'n_ema', x: 10, y: 20 }],
    groups: [],
  },
  command_receipt: null,
}

const acceptedDocument = (
  receipt: IrCommandReceipt = RECEIPT,
): IrEditorDocument => ({
  ...DOCUMENT,
  display_name: 'Renamed',
  draft_revision: receipt.draft_revision,
  version: receipt.version,
  content_address: receipt.content_address,
  authored_graph: {
    ...DOCUMENT.authored_graph,
    version: receipt.version,
    display_name: 'Renamed',
  },
  view: { ...DOCUMENT.view, version: receipt.version, display_name: 'Renamed' },
  layout: { ...DOCUMENT.layout, graph_version: receipt.version, revision: 1 },
  command_receipt: receipt,
})

describe('graph editor state', () => {
  it('creates closed display-name, set, and clear command drafts', () => {
    const ready = beginGraphEditor(DOCUMENT)
    expect(draftDisplayName(ready, 'Renamed').draft?.operations).toEqual([
      { operation: 'set_display_name', display_name: 'Renamed' },
    ])
    expect(draftSetOverrideJson(ready, 'n_ema', 'offset', '2').draft?.operations).toEqual([
      { operation: 'set_override', instance_id: 'n_ema', parameter: 'offset', value: 2 },
    ])
    expect(draftClearOverride(ready, 'n_ema', 'length').draft?.operations).toEqual([
      { operation: 'clear_override', instance_id: 'n_ema', parameter: 'length' },
    ])
  })

  it('retains invalid JSON intent without producing a publishable request', () => {
    const invalid = draftSetOverrideJson(
      beginGraphEditor(DOCUMENT), 'n_ema', 'offset', 'not-json',
    )

    expect(invalid.phase).toBe('validation-error')
    expect(invalid.draft).toMatchObject({ rawValue: 'not-json', operations: [] })
    expect(startPublish(invalid)).toBeNull()
  })

  it('blocks publication while local layout intent is unresolved', () => {
    const drafted = draftDisplayName(beginGraphEditor(DOCUMENT), 'Renamed')

    expect(startPublish(drafted, 'dirty')).toBeNull()
    expect(startPublish(drafted, 'saving')).toBeNull()
    expect(startPublish(drafted, 'conflict')).toBeNull()
  })

  it('starts presentation-only commands against both accepted revisions', () => {
    const started = startPresentationCommand(beginGraphEditor(DOCUMENT), [{
      operation: 'remove_group', identifier: 'g_signal',
    }])!

    expect(started.request).toEqual({
      kind: 'presentation',
      baseRevision: 3,
      basePresentationRevision: 1,
      semanticOperations: [],
      presentationOperations: [{
        operation: 'remove_group', identifier: 'g_signal',
      }],
    })
  })

  it('adopts only the matching publication and clears redo after a new edit', () => {
    const drafted = draftDisplayName(beginGraphEditor(DOCUMENT), 'Renamed')
    const pending = startPublish({ ...drafted, redo: [RECEIPT] })!
    const accepted = acceptPublication(
      pending.state, pending.requestId, acceptedDocument(),
    )

    expect(pending.request).toEqual({
      kind: 'semantic',
      baseRevision: 3,
      basePresentationRevision: 1,
      semanticOperations: [{ operation: 'set_display_name', display_name: 'Renamed' }],
      presentationOperations: [],
    })
    expect(accepted.phase).toBe('ready-clean')
    expect(accepted.accepted?.version).toBe(8)
    expect(accepted.undo).toEqual([RECEIPT])
    expect(accepted.redo).toEqual([])
    expect(accepted.draft).toBeNull()
  })

  it('ignores a stale publication after reload has issued a newer request', () => {
    const publish = startPublish(
      draftDisplayName(beginGraphEditor(DOCUMENT), 'Renamed'),
    )!
    const reload = startReload(publish.state)
    const reloaded = acceptReload(reload.state, reload.requestId, DOCUMENT)

    expect(acceptPublication(
      reloaded, publish.requestId, acceptedDocument(),
    )).toBe(reloaded)
  })

  it('retains local intent and history on validation, transport, and conflict', () => {
    const drafted = {
      ...draftDisplayName(beginGraphEditor(DOCUMENT), 'Renamed'),
      undo: [RECEIPT],
    }
    for (const [category, phase] of [
      ['validation', 'validation-error'],
      ['network', 'transport-error'],
      ['conflict', 'conflicted'],
    ] as const) {
      const pending = startPublish(drafted)!
      const failed = failEditorRequest(
        pending.state,
        pending.requestId,
        new EditorApiError(category, category),
      )
      expect(failed.phase).toBe(phase)
      expect(failed.draft).toBe(drafted.draft)
      expect(failed.undo).toBe(drafted.undo)
      if (category === 'conflict') expect(startPublish(failed)).toBeNull()
    }
  })

  it('publishes undo inverse and redo forward operations against current revision', () => {
    const withHistory = {
      ...beginGraphEditor(acceptedDocument()),
      undo: [RECEIPT],
    }
    const undo = startUndo(withHistory)!
    expect(undo.request).toEqual({
      kind: 'semantic',
      baseRevision: 4,
      basePresentationRevision: 1,
      semanticOperations: RECEIPT.semantic_inverse_operations,
      presentationOperations: [],
    })
    const undoneDocument = acceptedDocument({
      ...RECEIPT,
      applied_operations: RECEIPT.inverse_operations,
      inverse_operations: RECEIPT.applied_operations,
      semantic_forward_operations: RECEIPT.semantic_inverse_operations,
      semantic_inverse_operations: RECEIPT.semantic_forward_operations,
      base_revision: 4,
      draft_revision: 5,
      version: 9,
      content_address: 'sha256:undone',
    })
    const undone = acceptPublication(undo.state, undo.requestId, undoneDocument)
    expect(undone.undo).toEqual([])
    expect(undone.redo).toEqual([RECEIPT])

    const redo = startRedo(undone)!
    expect(redo.request).toEqual({
      kind: 'semantic',
      baseRevision: 5,
      basePresentationRevision: 1,
      semanticOperations: RECEIPT.semantic_forward_operations,
      presentationOperations: [],
    })
    const redone = acceptPublication(
      redo.state,
      redo.requestId,
      acceptedDocument({ ...RECEIPT, base_revision: 5, draft_revision: 6, version: 10 }),
    )
    expect(redone.undo).toEqual([RECEIPT])
    expect(redone.redo).toEqual([])
  })

  it('explicit reload discards local intent and external-revision history', () => {
    const dirty = {
      ...draftDisplayName(beginGraphEditor(DOCUMENT), 'Local'),
      undo: [RECEIPT],
      redo: [RECEIPT],
    }
    const reload = startReload(dirty)
    const remote = { ...DOCUMENT, draft_revision: 12, version: 16 }
    const reloaded = acceptReload(reload.state, reload.requestId, remote)

    expect(reloaded.accepted).toBe(remote)
    expect(reloaded.draft).toBeNull()
    expect(reloaded.undo).toEqual([])
    expect(reloaded.redo).toEqual([])
    expect(reloaded.phase).toBe('ready-clean')
  })
})
