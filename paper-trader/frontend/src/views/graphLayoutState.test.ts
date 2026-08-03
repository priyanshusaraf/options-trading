import { describe, expect, it, vi } from 'vitest'
import { IrLayoutConflict, type IrGraphLayout } from '../lib/api'
import {
  beginLayoutEditor,
  adoptEditorLayout,
  failLayoutSave,
  finishLayoutSave,
  moveLayoutNode,
  persistLayoutEditor,
  reloadLayoutEditor,
  saveBaseRevision,
  startLayoutSave,
} from './graphLayoutState'

const LAYOUT: IrGraphLayout = {
  graph_identifier: 'strategy.example',
  graph_version: 4,
  revision: 2,
  positions: [{ instance_id: 'signal', x: 10, y: 20 }],
  groups: [],
}

describe('graph layout editor state', () => {
  it('records sparse movement without mutating the loaded layout', () => {
    const editor = beginLayoutEditor(LAYOUT)
    const moved = moveLayoutNode(editor, 'signal', { x: 80, y: 90 })

    expect(moved.phase).toBe('dirty')
    expect(moved.layout.positions).toEqual([{ instance_id: 'signal', x: 80, y: 90 }])
    expect(LAYOUT.positions).toEqual([{ instance_id: 'signal', x: 10, y: 20 }])
  })

  it('retains local positions on conflict and retries against the reported revision', () => {
    const moved = moveLayoutNode(beginLayoutEditor(LAYOUT), 'signal', { x: 80, y: 90 })
    const failed = failLayoutSave(
      startLayoutSave(moved),
      new IrLayoutConflict(7),
    )

    expect(failed.phase).toBe('conflict')
    expect(failed.layout).toBe(moved.layout)
    expect(saveBaseRevision(failed)).toBe(7)
  })

  it('retains local positions on transport failure', () => {
    const moved = moveLayoutNode(beginLayoutEditor(LAYOUT), 'signal', { x: 80, y: 90 })
    const failed = failLayoutSave(startLayoutSave(moved), new Error('network unavailable'))

    expect(failed.phase).toBe('error')
    expect(failed.layout).toBe(moved.layout)
    expect(failed.message).toBe('network unavailable')
    expect(saveBaseRevision(failed)).toBe(2)
  })

  it('adopts the saved revision only after success', () => {
    const moved = moveLayoutNode(beginLayoutEditor(LAYOUT), 'signal', { x: 80, y: 90 })
    const savedLayout = { ...moved.layout, revision: 3 }
    const saved = finishLayoutSave(startLayoutSave(moved), savedLayout)

    expect(saved.phase).toBe('saved')
    expect(saved.layout).toBe(savedLayout)
    expect(saveBaseRevision(saved)).toBe(3)
  })

  it('calls the save transport with the complete draft and caller revision', async () => {
    const moved = moveLayoutNode(beginLayoutEditor(LAYOUT), 'signal', { x: 80, y: 90 })
    const persisted = { ...moved.layout, revision: 3 }
    const save = vi.fn().mockResolvedValue(persisted)

    await expect(persistLayoutEditor(moved, save)).resolves.toMatchObject({
      phase: 'saved',
      layout: persisted,
    })
    expect(save).toHaveBeenCalledWith(
      'strategy.example',
      4,
      2,
      moved.layout.positions,
    )
  })

  it('discards local work only through explicit reload', () => {
    const moved = moveLayoutNode(beginLayoutEditor(LAYOUT), 'signal', { x: 80, y: 90 })
    const remote = { ...LAYOUT, revision: 7, positions: [] }
    const reloaded = reloadLayoutEditor(moved, remote)

    expect(reloaded.phase).toBe('clean')
    expect(reloaded.layout).toBe(remote)
  })

  it('adopts a coherent server layout when local presentation state is clean', () => {
    const remote = {
      ...LAYOUT,
      graph_version: 5,
      revision: 1,
      positions: [{ instance_id: 'signal', x: 30, y: 40 }],
    }

    const adopted = adoptEditorLayout(beginLayoutEditor(LAYOUT), remote)

    expect(adopted.phase).toBe('clean')
    expect(adopted.layout).toBe(remote)
  })

  it('retains dirty positions but adopts the response version and revision', () => {
    const dirty = moveLayoutNode(beginLayoutEditor(LAYOUT), 'signal', { x: 80, y: 90 })
    const remote = {
      ...LAYOUT,
      graph_version: 5,
      revision: 1,
      positions: [{ instance_id: 'signal', x: 30, y: 40 }],
    }

    const adopted = adoptEditorLayout(dirty, remote)

    expect(adopted.phase).toBe('dirty')
    expect(adopted.layout).toEqual({
      ...remote,
      positions: dirty.layout.positions,
    })
    expect(saveBaseRevision(adopted)).toBe(1)
  })

  it('does not let an in-flight old-version save erase positions after publication', () => {
    const dirty = moveLayoutNode(beginLayoutEditor(LAYOUT), 'signal', { x: 80, y: 90 })
    const saving = startLayoutSave(dirty)
    const remote = { ...LAYOUT, graph_version: 5, revision: 1, positions: [] }

    const adopted = adoptEditorLayout(saving, remote)

    expect(adopted.phase).toBe('dirty')
    expect(adopted.layout.positions).toEqual(dirty.layout.positions)
    expect(adopted.layout.graph_version).toBe(5)
  })
})
