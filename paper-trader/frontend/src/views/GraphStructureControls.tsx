import { useMemo, useState } from 'react'
import type {
  IrEditorDocument,
  IrEditorOperation,
  IrSocketRef,
} from '../lib/api'

const socketValue = (ref: { readonly instance_id: string; readonly identifier: string }) => (
  `${ref.instance_id}\u0000${ref.identifier}`
)
const parseSocket = (value: string): IrSocketRef => {
  const [instance_id, socket] = value.split('\u0000')
  return { instance_id, socket }
}

export function GraphStructureControls({
  document,
  disabled,
  onSemantic,
}: {
  document: IrEditorDocument
  disabled: boolean
  onSemantic: (operations: readonly IrEditorOperation[]) => void
}) {
  const firstComponent = document.component_catalogue[0]
  const [component, setComponent] = useState(
    firstComponent ? `${firstComponent.identifier}\u0000${firstComponent.version}` : '',
  )
  const [instanceId, setInstanceId] = useState('')
  const authored = document.editable_nodes
  const [removeId, setRemoveId] = useState(authored[0]?.instance_id ?? '')
  const sockets = useMemo(() => [
    ...document.graph_sockets,
    ...authored.flatMap((node) => node.sockets.map((socket) => ({
      ...socket, instance_id: node.instance_id,
    }))),
  ], [document.graph_sockets, authored])
  const outputs = sockets.filter((socket) => socket.direction === 'output')
  const inputs = sockets.filter((socket) => socket.direction === 'input')
  const [source, setSource] = useState(
    outputs[0] ? socketValue(outputs[0]) : '',
  )
  const [target, setTarget] = useState(
    inputs[0] ? socketValue(inputs[0]) : '',
  )
  const edges = document.authored_graph.edges ?? []
  const [edgeIndex, setEdgeIndex] = useState('0')

  const addNode = () => {
    const [identifier, rawVersion] = component.split('\u0000')
    if (!identifier || !instanceId.trim()) return
    onSemantic([{
      operation: 'add_node',
      instance_id: instanceId.trim(),
      identifier,
      version: Number(rawVersion),
      overrides: {},
      domain: null,
      secret_params: [],
    }])
  }
  const connect = () => {
    if (!source || !target) return
    onSemantic([{ operation: 'connect', source: parseSocket(source), target: parseSocket(target) }])
  }
  const disconnect = () => {
    const edge = edges[Number(edgeIndex)]
    if (!edge) return
    onSemantic([{
      operation: 'disconnect',
      source: { instance_id: edge.source.instance, socket: edge.source.socket },
      target: { instance_id: edge.target.instance, socket: edge.target.socket },
    }])
  }
  const inputClass = 'rounded border border-edge bg-bg px-2 py-1.5 text-xs text-zinc-200'
  const buttonClass = 'rounded border border-edge px-3 py-1.5 text-xs font-medium text-zinc-200 disabled:opacity-50'

  return (
    <section aria-labelledby="graph-structure-title" className="card mb-4 space-y-4 p-4">
      <h2 id="graph-structure-title" className="text-sm font-semibold">Graph structure</h2>
      <div className="grid gap-3 md:grid-cols-3">
        <label className="grid gap-1 text-xs">Component and version
          <select className={inputClass} value={component} disabled={disabled} onChange={(event) => setComponent(event.target.value)}>
            {document.component_catalogue.map((item) => (
              <option key={`${item.identifier}:${item.version}`} value={`${item.identifier}\u0000${item.version}`}>
                {item.display_name} · {item.identifier} v{item.version}
              </option>
            ))}
          </select>
        </label>
        <label className="grid gap-1 text-xs">Authored instance ID
          <input className={inputClass} value={instanceId} disabled={disabled} onChange={(event) => setInstanceId(event.target.value)} />
        </label>
        <button type="button" className={buttonClass} disabled={disabled || !component || !instanceId.trim()} onClick={addNode}>Add authored node</button>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <label className="grid gap-1 text-xs">Authored node to remove
          <select className={inputClass} value={removeId} disabled={disabled} onChange={(event) => setRemoveId(event.target.value)}>
            {authored.map((node) => <option key={node.instance_id}>{node.instance_id}</option>)}
          </select>
        </label>
        <button type="button" className={buttonClass} disabled={disabled || !removeId} onClick={() => onSemantic([{ operation: 'remove_node', instance_id: removeId }])}>
          Remove node and incident edges
        </button>
      </div>

      <div className="grid gap-3 md:grid-cols-3">
        <label className="grid gap-1 text-xs">Source output socket
          <select className={inputClass} value={source} disabled={disabled} onChange={(event) => setSource(event.target.value)}>
            {outputs.map((socket) => <option key={socketValue(socket)} value={socketValue(socket)}>{socket.instance_id}.{socket.identifier}</option>)}
          </select>
        </label>
        <label className="grid gap-1 text-xs">Target input socket
          <select className={inputClass} value={target} disabled={disabled} onChange={(event) => setTarget(event.target.value)}>
            {inputs.map((socket) => <option key={socketValue(socket)} value={socketValue(socket)}>{socket.instance_id}.{socket.identifier}</option>)}
          </select>
        </label>
        <button type="button" className={buttonClass} disabled={disabled || !source || !target} onClick={connect}>Connect typed sockets</button>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <label className="grid gap-1 text-xs">Existing semantic edge
          <select className={inputClass} value={edgeIndex} disabled={disabled} onChange={(event) => setEdgeIndex(event.target.value)}>
            {edges.map((edge, index) => (
              <option key={`${edge.source.instance}:${edge.source.socket}:${edge.target.instance}:${edge.target.socket}`} value={index}>
                {edge.source.instance}.{edge.source.socket} → {edge.target.instance}.{edge.target.socket}
              </option>
            ))}
          </select>
        </label>
        <button type="button" className={buttonClass} disabled={disabled || edges.length === 0} onClick={disconnect}>Disconnect typed sockets</button>
      </div>
    </section>
  )
}
