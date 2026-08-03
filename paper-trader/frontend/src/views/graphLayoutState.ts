import {
  IrLayoutConflict,
  type IrGraphLayout,
  type IrLayoutPosition,
} from '../lib/api'

export type LayoutEditorPhase =
  | 'clean'
  | 'dirty'
  | 'saving'
  | 'saved'
  | 'conflict'
  | 'error'

export interface LayoutEditorState {
  readonly layout: IrGraphLayout
  readonly phase: LayoutEditorPhase
  readonly message: string | null
  readonly retryRevision: number | null
}

export const beginLayoutEditor = (layout: IrGraphLayout): LayoutEditorState => ({
  layout,
  phase: 'clean',
  message: null,
  retryRevision: null,
})

export function moveLayoutNode(
  state: LayoutEditorState,
  instanceId: string,
  point: { readonly x: number; readonly y: number },
): LayoutEditorState {
  const moved: IrLayoutPosition = {
    instance_id: instanceId,
    x: point.x,
    y: point.y,
  }
  const positions = [
    ...state.layout.positions.filter((position) => position.instance_id !== instanceId),
    moved,
  ].sort((left, right) => left.instance_id.localeCompare(right.instance_id))
  return {
    layout: { ...state.layout, positions },
    phase: 'dirty',
    message: null,
    retryRevision: state.retryRevision,
  }
}

export const startLayoutSave = (state: LayoutEditorState): LayoutEditorState => ({
  ...state,
  phase: 'saving',
  message: null,
})

export const finishLayoutSave = (
  _state: LayoutEditorState,
  layout: IrGraphLayout,
): LayoutEditorState => ({
  layout,
  phase: 'saved',
  message: null,
  retryRevision: null,
})

export function failLayoutSave(
  state: LayoutEditorState,
  reason: unknown,
): LayoutEditorState {
  if (reason instanceof IrLayoutConflict) {
    return {
      ...state,
      phase: 'conflict',
      message: reason.message,
      retryRevision: reason.currentRevision,
    }
  }
  return {
    ...state,
    phase: 'error',
    message: reason instanceof Error ? reason.message : 'Layout request failed',
  }
}

export const reloadLayoutEditor = (
  _state: LayoutEditorState,
  layout: IrGraphLayout,
): LayoutEditorState => beginLayoutEditor(layout)

export function adoptEditorLayout(
  state: LayoutEditorState,
  layout: IrGraphLayout,
): LayoutEditorState {
  const retainsLocalPositions = (
    state.phase === 'dirty'
    || state.phase === 'saving'
    || state.phase === 'conflict'
    || state.phase === 'error'
  )
  if (!retainsLocalPositions) return beginLayoutEditor(layout)
  return {
    layout: { ...layout, positions: state.layout.positions },
    phase: 'dirty',
    message: null,
    retryRevision: null,
  }
}

export const saveBaseRevision = (state: LayoutEditorState): number =>
  state.retryRevision ?? state.layout.revision

export type LayoutPersist = (
  identifier: string,
  version: number,
  baseRevision: number,
  positions: readonly IrLayoutPosition[],
) => Promise<IrGraphLayout>

export async function persistLayoutEditor(
  state: LayoutEditorState,
  persist: LayoutPersist,
): Promise<LayoutEditorState> {
  const saving = startLayoutSave(state)
  try {
    const saved = await persist(
      state.layout.graph_identifier,
      state.layout.graph_version,
      saveBaseRevision(state),
      state.layout.positions,
    )
    return finishLayoutSave(saving, saved)
  } catch (reason: unknown) {
    return failLayoutSave(saving, reason)
  }
}
