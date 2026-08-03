import {
  EditorApiError,
  type IrCommandReceipt,
  type IrEditorDocument,
  type IrEditorOperation,
  type IrPresentationOperation,
} from '../lib/api'

export type EditorPhase =
  | 'loading'
  | 'ready-clean'
  | 'ready-dirty'
  | 'saving'
  | 'conflicted'
  | 'validation-error'
  | 'transport-error'
  | 'reloading'

export interface EditorCommandDraft {
  readonly kind: 'set-display-name' | 'set-override' | 'clear-override'
  readonly operations: readonly IrEditorOperation[]
  readonly instanceId?: string
  readonly parameter?: string
  readonly rawValue?: string
}

type PendingKind = 'publish' | 'undo' | 'redo' | 'reload'

interface PendingEditorRequest {
  readonly requestId: number
  readonly kind: PendingKind
  readonly historyReceipt: IrCommandReceipt | null
}

export interface GraphEditorState {
  readonly phase: EditorPhase
  readonly accepted: IrEditorDocument | null
  readonly draft: EditorCommandDraft | null
  readonly undo: readonly IrCommandReceipt[]
  readonly redo: readonly IrCommandReceipt[]
  readonly nextRequestId: number
  readonly pending: PendingEditorRequest | null
  readonly failure: EditorApiError | null
}

export interface EditorPublicationRequest {
  readonly kind: 'semantic' | 'presentation'
  readonly baseRevision: number
  readonly basePresentationRevision: number
  readonly semanticOperations: readonly IrEditorOperation[]
  readonly presentationOperations: readonly IrPresentationOperation[]
}

export interface StartedEditorRequest {
  readonly state: GraphEditorState
  readonly requestId: number
  readonly request: EditorPublicationRequest
}

export interface StartedReload {
  readonly state: GraphEditorState
  readonly requestId: number
}

export const beginGraphEditor = (document: IrEditorDocument): GraphEditorState => ({
  phase: 'ready-clean',
  accepted: document,
  draft: null,
  undo: [],
  redo: [],
  nextRequestId: 1,
  pending: null,
  failure: null,
})

const canDraft = (state: GraphEditorState): boolean =>
  state.phase !== 'saving' && state.phase !== 'reloading' && state.phase !== 'conflicted'

export const draftDisplayName = (
  state: GraphEditorState,
  displayName: string,
): GraphEditorState => canDraft(state) ? {
  ...state,
  phase: 'ready-dirty',
  draft: {
    kind: 'set-display-name',
    operations: [{ operation: 'set_display_name', display_name: displayName }],
  },
  failure: null,
} : state

export const draftClearOverride = (
  state: GraphEditorState,
  instanceId: string,
  parameter: string,
): GraphEditorState => canDraft(state) ? {
  ...state,
  phase: 'ready-dirty',
  draft: {
    kind: 'clear-override',
    instanceId,
    parameter,
    operations: [{
      operation: 'clear_override',
      instance_id: instanceId,
      parameter,
    }],
  },
  failure: null,
} : state

export function draftSetOverrideJson(
  state: GraphEditorState,
  instanceId: string,
  parameter: string,
  source: string,
): GraphEditorState {
  if (!canDraft(state)) return state
  try {
    const value: unknown = JSON.parse(source)
    return {
      ...state,
      phase: 'ready-dirty',
      draft: {
        kind: 'set-override',
        instanceId,
        parameter,
        rawValue: source,
        operations: [{
          operation: 'set_override',
          instance_id: instanceId,
          parameter,
          value,
        }],
      },
      failure: null,
    }
  } catch (cause: unknown) {
    return {
      ...state,
      phase: 'validation-error',
      draft: {
        kind: 'set-override',
        instanceId,
        parameter,
        rawValue: source,
        operations: [],
      },
      failure: new EditorApiError(
        'validation', 'Override value must be valid JSON', null, cause,
      ),
    }
  }
}

const start = (
  state: GraphEditorState,
  kind: PendingKind,
  commandKind: 'semantic' | 'presentation',
  semanticOperations: readonly IrEditorOperation[],
  presentationOperations: readonly IrPresentationOperation[],
  historyReceipt: IrCommandReceipt | null,
): StartedEditorRequest | null => {
  if (!state.accepted || state.pending || state.phase === 'conflicted') return null
  const requestId = state.nextRequestId
  return {
    requestId,
    request: {
      baseRevision: state.accepted.draft_revision,
      basePresentationRevision: state.accepted.layout.revision,
      kind: commandKind,
      semanticOperations,
      presentationOperations,
    },
    state: {
      ...state,
      phase: 'saving',
      nextRequestId: requestId + 1,
      pending: { requestId, kind, historyReceipt },
      failure: null,
    },
  }
}

export const startPublish = (
  state: GraphEditorState,
  layoutPhase: string = 'clean',
): StartedEditorRequest | null =>
  state.draft && state.draft.operations.length > 0
    && !['dirty', 'saving', 'conflict', 'error'].includes(layoutPhase)
    ? start(state, 'publish', 'semantic', state.draft.operations, [], null)
    : null

export const startPresentationCommand = (
  state: GraphEditorState,
  operations: readonly IrPresentationOperation[],
  layoutPhase: string = 'clean',
): StartedEditorRequest | null => operations.length > 0
  && !['dirty', 'saving', 'conflict', 'error'].includes(layoutPhase)
  ? start(state, 'publish', 'presentation', [], operations, null)
  : null

export const startSemanticCommand = (
  state: GraphEditorState,
  operations: readonly IrEditorOperation[],
  presentationOperations: readonly IrPresentationOperation[] = [],
  layoutPhase: string = 'clean',
): StartedEditorRequest | null => operations.length > 0
  && !['dirty', 'saving', 'conflict', 'error'].includes(layoutPhase)
  ? start(
      state, 'publish', 'semantic', operations, presentationOperations, null,
    )
  : null

export const startUndo = (
  state: GraphEditorState,
  layoutPhase: string = 'clean',
): StartedEditorRequest | null => {
  const receipt = state.undo[state.undo.length - 1]
  if (!receipt) return null
  const semantic = receipt.semantic_inverse_operations
  if (semantic.length > 0 && ['dirty', 'saving', 'conflict', 'error'].includes(layoutPhase)) {
    return null
  }
  return start(
    state,
    'undo',
    semantic.length > 0 ? 'semantic' : 'presentation',
    semantic,
    receipt.presentation_delta.inverse_operations,
    receipt,
  )
}

export const startRedo = (
  state: GraphEditorState,
  layoutPhase: string = 'clean',
): StartedEditorRequest | null => {
  const receipt = state.redo[state.redo.length - 1]
  if (!receipt) return null
  const semantic = receipt.semantic_forward_operations
  if (semantic.length > 0 && ['dirty', 'saving', 'conflict', 'error'].includes(layoutPhase)) {
    return null
  }
  return start(
    state,
    'redo',
    semantic.length > 0 ? 'semantic' : 'presentation',
    semantic,
    receipt.presentation_delta.forward_operations,
    receipt,
  )
}

export function acceptPublication(
  state: GraphEditorState,
  requestId: number,
  document: IrEditorDocument,
): GraphEditorState {
  if (state.pending?.requestId !== requestId || state.pending.kind === 'reload') {
    return state
  }
  const receipt = document.command_receipt
  if (!receipt) {
    return {
      ...state,
      phase: 'transport-error',
      pending: null,
      failure: new EditorApiError(
        'server', 'Accepted editor response contained no command receipt',
      ),
    }
  }
  if (state.pending.kind === 'undo') {
    const original = state.pending.historyReceipt!
    return {
      ...state,
      phase: 'ready-clean',
      accepted: document,
      draft: null,
      undo: state.undo.slice(0, -1),
      redo: [...state.redo, original],
      pending: null,
      failure: null,
    }
  }
  if (state.pending.kind === 'redo') {
    const original = state.pending.historyReceipt!
    return {
      ...state,
      phase: 'ready-clean',
      accepted: document,
      draft: null,
      undo: [...state.undo, original],
      redo: state.redo.slice(0, -1),
      pending: null,
      failure: null,
    }
  }
  return {
    ...state,
    phase: 'ready-clean',
    accepted: document,
    draft: null,
    undo: [...state.undo, receipt],
    redo: [],
    pending: null,
    failure: null,
  }
}

export function failEditorRequest(
  state: GraphEditorState,
  requestId: number,
  failure: EditorApiError,
): GraphEditorState {
  if (state.pending?.requestId !== requestId) return state
  const phase: EditorPhase = failure.category === 'conflict'
    ? 'conflicted'
    : failure.category === 'validation'
      ? 'validation-error'
      : 'transport-error'
  return { ...state, phase, pending: null, failure }
}

export function startReload(state: GraphEditorState): StartedReload {
  const requestId = state.nextRequestId
  return {
    requestId,
    state: {
      ...state,
      phase: 'reloading',
      nextRequestId: requestId + 1,
      pending: { requestId, kind: 'reload', historyReceipt: null },
      failure: null,
    },
  }
}

export function acceptReload(
  state: GraphEditorState,
  requestId: number,
  document: IrEditorDocument,
): GraphEditorState {
  if (state.pending?.requestId !== requestId || state.pending.kind !== 'reload') {
    return state
  }
  return {
    ...state,
    phase: 'ready-clean',
    accepted: document,
    draft: null,
    undo: [],
    redo: [],
    pending: null,
    failure: null,
  }
}
