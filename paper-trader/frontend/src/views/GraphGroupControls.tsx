import { useState } from 'react'
import type { IrEditorDocument, IrPresentationOperation, IrVisualGroup } from '../lib/api'

const inputClass = 'rounded border border-edge bg-bg px-2 py-1.5 text-xs text-zinc-200'
const buttonClass = 'rounded border border-edge px-3 py-1.5 text-xs font-medium text-zinc-200 disabled:opacity-50'

function GroupEditor({
  group,
  authoredIds,
  disabled,
  onPresentation,
}: {
  group: IrVisualGroup
  authoredIds: readonly string[]
  disabled: boolean
  onPresentation: (operations: readonly IrPresentationOperation[]) => void
}) {
  const [name, setName] = useState(group.display_name)
  const [member, setMember] = useState(authoredIds[0] ?? '')
  const [frame, setFrame] = useState(group.frame)
  const number = (field: keyof typeof frame, value: string) => setFrame({
    ...frame, [field]: Number(value),
  })
  return (
    <fieldset className="space-y-3 rounded border border-edge p-3">
      <legend className="px-1 text-xs font-semibold">{group.identifier}</legend>
      <div className="grid gap-2 md:grid-cols-3">
        <label className="grid gap-1 text-xs">Group label
          <input className={inputClass} value={name} disabled={disabled} onChange={(event) => setName(event.target.value)} />
        </label>
        <button type="button" className={buttonClass} disabled={disabled || !name.trim()} onClick={() => onPresentation([{
          operation: 'rename_group', identifier: group.identifier, display_name: name.trim(),
        }])}>Rename visual group</button>
        <button type="button" className={buttonClass} disabled={disabled} onClick={() => onPresentation([{
          operation: 'remove_group', identifier: group.identifier,
        }])}>Remove visual group</button>
      </div>
      <div className="grid gap-2 md:grid-cols-3">
        <label className="grid gap-1 text-xs">Authored group member
          <select className={inputClass} value={member} disabled={disabled} onChange={(event) => setMember(event.target.value)}>
            {authoredIds.map((instanceId) => <option key={instanceId}>{instanceId}</option>)}
          </select>
        </label>
        <button type="button" className={buttonClass} disabled={disabled || !member || group.members.includes(member)} onClick={() => onPresentation([{
          operation: 'add_group_member', identifier: group.identifier, instance_id: member,
        }])}>Add member</button>
        <button type="button" className={buttonClass} disabled={disabled || !member || !group.members.includes(member)} onClick={() => onPresentation([{
          operation: 'remove_group_member', identifier: group.identifier, instance_id: member,
        }])}>Remove member</button>
      </div>
      <div className="grid gap-2 sm:grid-cols-5">
        {(['x', 'y', 'width', 'height'] as const).map((field) => (
          <label key={field} className="grid gap-1 text-xs">Frame {field}
            <input type="number" className={inputClass} value={frame[field]} disabled={disabled} onChange={(event) => number(field, event.target.value)} />
          </label>
        ))}
        <button type="button" className={buttonClass} disabled={disabled || frame.width <= 0 || frame.height <= 0} onClick={() => onPresentation([{
          operation: 'set_group_frame', identifier: group.identifier, frame,
        }])}>Update frame</button>
      </div>
      <label className="flex items-center gap-2 text-xs">
        <input type="checkbox" checked={group.collapsed} disabled={disabled} onChange={(event) => onPresentation([{
          operation: 'set_group_collapsed', identifier: group.identifier,
          collapsed: event.target.checked,
        }])} />
        Collapse visual group
      </label>
    </fieldset>
  )
}

export function GraphGroupControls({
  document,
  disabled,
  onPresentation,
}: {
  document: IrEditorDocument
  disabled: boolean
  onPresentation: (operations: readonly IrPresentationOperation[]) => void
}) {
  const [identifier, setIdentifier] = useState('')
  const [displayName, setDisplayName] = useState('')
  const authoredIds = document.editable_nodes.map((node) => node.instance_id)
  return (
    <section aria-labelledby="graph-groups-title" className="card mb-4 space-y-4 p-4">
      <h2 id="graph-groups-title" className="text-sm font-semibold">Visual groups</h2>
      <div className="grid gap-3 md:grid-cols-3">
        <label className="grid gap-1 text-xs">Group identifier
          <input className={inputClass} value={identifier} disabled={disabled} onChange={(event) => setIdentifier(event.target.value)} />
        </label>
        <label className="grid gap-1 text-xs">Group label
          <input className={inputClass} value={displayName} disabled={disabled} onChange={(event) => setDisplayName(event.target.value)} />
        </label>
        <button type="button" className={buttonClass} disabled={disabled || !identifier.trim() || !displayName.trim()} onClick={() => onPresentation([{
          operation: 'create_group',
          identifier: identifier.trim(),
          display_name: displayName.trim(),
          members: [],
          frame: { x: 24, y: 24, width: 420, height: 420 },
          collapsed: false,
        }])}>Create visual group</button>
      </div>
      {document.layout.groups.map((group) => (
        <GroupEditor
          key={group.identifier}
          group={group}
          authoredIds={authoredIds}
          disabled={disabled}
          onPresentation={onPresentation}
        />
      ))}
    </section>
  )
}
