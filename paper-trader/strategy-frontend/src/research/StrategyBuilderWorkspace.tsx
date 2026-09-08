import { TraderSelect, type SelectOption } from '../components/TraderSelect'
import { parseSavedResearchPolicy } from './preparedResearchContracts'
import { record, descriptor, parameterRows, labelFor, SaveVerificationError, stageParameterCommand, parameterKey, requireSemanticCommit, requirePublication, publishedAddress, requirePublishedDraft } from './builderParameterContracts'
import { memo, useCallback, useDeferredValue, useEffect, useLayoutEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react'
import { Background, Controls, Handle, Position, ReactFlow, useNodesState, useUpdateNodeInternals, type Connection, type Node, type NodeChange, type NodeProps, type ReactFlowInstance } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import './node-families.css'
import { Check, LayoutGrid, Redo2, RotateCcw, Search, Trash2, Undo2, Plus, X } from 'lucide-react'
import { ApiError, errorMessage, type StrategyApi } from '../shell/api'
import type { CatalogueComponent, CatalogueHelp, GraphSummary, Project, PublishedGraph, V2Draft, V2Presentation, V2PresentationReceipt, V2SemanticReceipt, VerifiedCatalogue } from '../shell/contracts'

type Load<T> = { kind: 'loading' } | { kind: 'error'; message: string } | { kind: 'ready'; value: T }
type Command = Readonly<Record<string, unknown>>
type EditSnapshot = { semantic: Command[]; layout: Command[]; selectedId: string | null }
type EditHistory = { past: EditSnapshot[]; future: EditSnapshot[] }
type Port = Readonly<{ port_id: string; direction: 'input' | 'output'; semantic_flow: string; semantic_role: string; type_ref: unknown; shape: unknown }>
type WorkingNode = Readonly<{ node_id: string; label: string; visible_family: string; component_id: string; component_version: number; parameters: Readonly<Record<string, unknown>>; ports: readonly Port[]; help: CatalogueHelp }>
type WorkingEdge = Readonly<{ edge_id: string; source: Readonly<{ node_id: string; port_id: string }>; target: Readonly<{ node_id: string; port_id: string }>; binding: Readonly<Record<string, unknown>> }>
type WorkingGraph = Readonly<{ nodes: readonly WorkingNode[]; edges: readonly WorkingEdge[] }>
interface FlowData extends Record<string, unknown> { node: WorkingNode; selectedPath: boolean; onHelp: (node: WorkingNode, invoker: HTMLButtonElement) => void }
type StrategyFlowNode = Node<FlowData, 'strategy'>
const familyNames = new Map([['TYPE_1', 'Execution'], ['TYPE_2', 'Indicators'], ['TYPE_3', 'Market structure'], ['TYPE_4', 'Data'], ['TYPE_5', 'Logic']])

function nodeFamily(value: string) {
  const name = familyNames.get(value)
  return name ? { key: value, label: name, description: name } : { key: 'UNKNOWN', label: 'Unclassified', description: 'Unknown node family' }
}

function ports(component: CatalogueComponent): readonly Port[] {
  const rows = descriptor(component).ports
  if (!Array.isArray(rows)) return []
  return rows.flatMap((value) => { const row = record(value)
    return typeof row.port_id === 'string' && (row.direction === 'input' || row.direction === 'output')
      ? [{ port_id: row.port_id, direction: row.direction, semantic_flow: String(row.semantic_flow ?? ''), semantic_role: String(row.semantic_role ?? ''), type_ref: row.type_ref, shape: row.shape }]
      : [] })
}
function samePortType(source: Port, target: Port) { return source.direction === 'output' && target.direction === 'input' && source.semantic_flow === target.semantic_flow && JSON.stringify(source.type_ref) === JSON.stringify(target.type_ref) && JSON.stringify(source.shape) === JSON.stringify(target.shape) }
function presentText(value: string) {
  return value
    .replace(/\bcanonical datasets?\b/gi, (match) => match.toLowerCase().endsWith('s') ? 'historical datasets' : 'historical dataset')
    .replace(/\bcanonical instruments?\b/gi, (match) => match.toLowerCase().endsWith('s') ? 'instruments' : 'instrument')
    .replace(/\bcanonical strategy graphs?\b/gi, (match) => match.toLowerCase().endsWith('s') ? 'strategy graphs' : 'strategy graph')
    .replace(/\bcanonical strategies\b/gi, 'strategies')
    .replace(/\bcanonical strategy\b/gi, 'strategy')
    .replace(/\bcanonical\b/gi, 'verified')
}

function NodePorts({ ports: nodePorts }: { ports: readonly Port[] }) {
  const inputs = nodePorts.filter((port) => port.direction === 'input')
  const outputs = nodePorts.filter((port) => port.direction === 'output')
  return <div className="workstation-node-ports">{Array.from({ length: Math.max(inputs.length, outputs.length) }, (_, index) => {
    const input = inputs[index], output = outputs[index]
    return <div className="workstation-port-row" key={index}>
      <span>{input && <><Handle id={input.port_id} type="target" position={Position.Left} style={{ top: '50%' }} aria-label={`${input.port_id} input`} />{labelFor(input.port_id)}</>}</span>
      <span>{output && <>{labelFor(output.port_id)}<Handle id={output.port_id} type="source" position={Position.Right} style={{ top: '50%' }} aria-label={`${output.port_id} output`} /></>}</span>
    </div>
  })}</div>
}

const StrategyNode = memo(function StrategyNode({ id, data, selected }: NodeProps<StrategyFlowNode>) {
  const updateNodeInternals = useUpdateNodeInternals()
  const family = nodeFamily(data.node.visible_family)
  useLayoutEffect(() => updateNodeInternals(id), [id, data.node.ports, updateNodeInternals])
  return <div data-node-family={family.key} className={`workstation-node${data.selectedPath ? ' workstation-node--trace' : ''}${selected ? ' workstation-node--selected' : ''}`}>
    <div className="workstation-node-heading"><strong>{presentText(data.node.label)}</strong>
      <span className="node-family-label" title={family.description} aria-label={`${family.label}: ${family.description}`}>{family.label}</span>
      <button type="button" className="node-help-control nodrag" aria-label={`Help for ${presentText(data.node.label)}`} onPointerDown={(event) => event.stopPropagation()} onClick={(event) => { event.stopPropagation(); data.onHelp(data.node, event.currentTarget) }}>?</button>
    </div>
    <NodePorts ports={data.node.ports} />
  </div>
})

const nodeTypes = { strategy: StrategyNode }
const FlowCanvas = memo(function FlowCanvas({ nodes, edges, onSelect, onConnect, onDragFrame, onDragEnd, onReady }: { nodes: readonly Node<FlowData>[]; edges: readonly Readonly<Record<string, unknown>>[]; onSelect: (id: string | null) => void; onConnect: (connection: Connection) => void; onDragFrame: (id: string, x: number, y: number) => void; onDragEnd: (id: string, x: number, y: number) => void; onReady: (instance: ReactFlowInstance<Node<FlowData>>, element: HTMLDivElement) => void }) {
  const host = useRef<HTMLDivElement>(null)
  const viewport = useRef<ReactFlowInstance<Node<FlowData>> | null>(null)
  const pan = (x: number, y: number) => { const instance = viewport.current; if (!instance) return; const view = instance.getViewport(); void instance.setViewport({ ...view, x: view.x + x, y: view.y + y }) }
  const panKey = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.target !== event.currentTarget) return
    const delta = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[event.key]
    if (!delta) return
    event.preventDefault(); const step = event.shiftKey ? 64 : 32; pan(delta[0] * step, delta[1] * step)
  }
  const [visibleNodes, setVisibleNodes, applyVisibleNodeChanges] = useNodesState<Node<FlowData>>([...nodes])
  useEffect(() => setVisibleNodes([...nodes]), [nodes, setVisibleNodes])
  const trackControlledPositions = useCallback((changes: NodeChange<Node<FlowData>>[]) => {
    applyVisibleNodeChanges(changes)
    for (const change of changes) {
      if (change.type === 'position' && change.position !== undefined) {
        if (change.dragging === false) onDragEnd(change.id, change.position.x, change.position.y)
        else onDragFrame(change.id, change.position.x, change.position.y)
      }
    }
  }, [applyVisibleNodeChanges, onDragEnd, onDragFrame])
  return <div ref={host} className="canvas-pane" tabIndex={0} onKeyDown={panKey} aria-label="Strategy graph canvas"><ReactFlow nodes={visibleNodes} edges={edges as never} nodeTypes={nodeTypes} onInit={(instance) => { viewport.current = instance; if (host.current) onReady(instance, host.current) }} onNodesChange={trackControlledPositions} onNodeClick={(_, node) => onSelect(node.id)} onPaneClick={() => onSelect(null)} onConnect={onConnect} panOnDrag={[0, 1]} panActivationKeyCode="Space" selectionOnDrag={false} fitView fitViewOptions={{ maxZoom: 1, padding: .2 }} minZoom={.15} maxZoom={1.8} snapToGrid={false} deleteKeyCode={null} onlyRenderVisibleElements proOptions={{ hideAttribution: true }}><Background gap={24} size={1} /><Controls showInteractive={false} fitViewOptions={{ maxZoom: 1, padding: .2 }} /></ReactFlow>

  </div>
})

function instanceId(component: CatalogueComponent, existing: ReadonlySet<string>) { const stem = component.component_id.replace(/[^a-zA-Z0-9]+/g, '_').replace(/^_+|_+$/g, '').toLowerCase() || 'node'; let candidate = stem; let index = 2; while (existing.has(candidate)) { candidate = `${stem}_${index}`; index += 1 } return candidate }
function edgeId(source: { node_id: string; port_id: string }, target: { node_id: string; port_id: string }) { return `staged:${source.node_id}:${source.port_id}:${target.node_id}:${target.port_id}` }
function workingProjection(draft: V2Draft, catalogue: VerifiedCatalogue, commands: readonly Command[]): WorkingGraph {
  const byIdentity = new Map(catalogue.groups.flatMap((group) => group.components).map((item) => [`${item.component_id}@${item.component_version}`, item]))
  let nodes: WorkingNode[] = draft.document.nodes.map((node) => { const component = byIdentity.get(`${node.component.component_id}@${node.component.component_version}`); if (!component) throw new Error('The strategy node is not present in the verified help catalogue.'); return { node_id: node.node_id, label: component.display_name, visible_family: component.visible_family, component_id: node.component.component_id, component_version: node.component.component_version, parameters: node.parameters, ports: ports(component), help: component.help } })
  let edges: WorkingEdge[] = draft.document.edges.flatMap((edge) => edge.source.scope === 'node' && edge.target.scope === 'node' ? [{ edge_id: edge.edge_id, source: edge.source as WorkingEdge['source'], target: edge.target as WorkingEdge['target'], binding: edge.binding }] : [])
  for (const command of commands) {
    if (command.command === 'add_node') { const component = byIdentity.get(`${command.component_id}@${command.component_version}`); if (component && !nodes.some((node) => node.node_id === command.node_id)) nodes = [...nodes, { node_id: String(command.node_id), label: component.display_name, visible_family: component.visible_family, component_id: component.component_id, component_version: component.component_version, parameters: record(command.parameters), ports: ports(component), help: component.help }] }
    if (command.command === 'remove_node') { const id = String(command.node_id); nodes = nodes.filter((node) => node.node_id !== id); edges = edges.filter((edge) => edge.source.node_id !== id && edge.target.node_id !== id) }
    if (command.command === 'connect') { const source = record(command.source) as WorkingEdge['source']; const target = record(command.target) as WorkingEdge['target']; if (!edges.some((edge) => edge.source.node_id === source.node_id && edge.source.port_id === source.port_id && edge.target.node_id === target.node_id && edge.target.port_id === target.port_id)) edges = [...edges, { edge_id: edgeId(source, target), source, target, binding: record(command.binding) }] }
    if (command.command === 'disconnect') { const source = record(command.source); const target = record(command.target); edges = edges.filter((edge) => !(edge.source.node_id === source.node_id && edge.source.port_id === source.port_id && edge.target.node_id === target.node_id && edge.target.port_id === target.port_id)) }
    if (command.command === 'set_parameter' || command.command === 'clear_parameter') nodes = nodes.map((node) => node.node_id !== command.node_id ? node : { ...node, parameters: Object.freeze(command.command === 'clear_parameter' ? Object.fromEntries(Object.entries(node.parameters).filter(([key]) => key !== command.parameter_id)) : { ...node.parameters, [String(command.parameter_id)]: command.value }) })
  }
  return Object.freeze({ nodes: Object.freeze(nodes), edges: Object.freeze(edges) })
}
function traceIds(selected: string | null, graph: WorkingGraph | null) { const traced = new Set<string>(); if (!selected || !graph) return traced; const adjacent = new Map<string, Set<string>>(); for (const edge of graph.edges) { const source = edge.source.node_id; const target = edge.target.node_id; if (!adjacent.has(source)) adjacent.set(source, new Set()); if (!adjacent.has(target)) adjacent.set(target, new Set()); adjacent.get(source)!.add(target); adjacent.get(target)!.add(source) } const queue = [selected]; traced.add(selected); for (let index = 0; index < queue.length; index += 1) for (const id of adjacent.get(queue[index]) ?? []) if (!traced.has(id)) { traced.add(id); queue.push(id) } return traced }

function PaletteFamily({ group, initiallyOpen, forceOpen, onAdd }: { group: VerifiedCatalogue['groups'][number]; initiallyOpen: boolean; forceOpen: boolean; onAdd: (component: CatalogueComponent) => void }) {
  const [open, setOpen] = useState(initiallyOpen); const visible = forceOpen || open
  return <details open={visible} onToggle={(event) => { if (!forceOpen) setOpen(event.currentTarget.open) }}><summary>{familyNames.get(group.visible_family) ?? presentText(group.display_name)}<small>{group.components.length}</small></summary>{visible && <ul>{group.components.map((component) => <li key={`${component.component_id}:${component.component_version}`}><button onClick={() => onAdd(component)}><strong>{presentText(component.display_name)}</strong><small>{component.availability.status === 'AVAILABLE' ? 'Available' : component.availability.status}</small></button></li>)}</ul>}</details>
}

function ComponentExplorer({ open, onClose, searchInput, children }: { open: boolean; onClose: () => void; searchInput: React.RefObject<HTMLInputElement | null>; children: React.ReactNode }) {
  const dialog = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    if (!open || !dialog.current) return
    const element = dialog.current, invoker = document.activeElement
    element.showModal(); searchInput.current?.focus()
    return () => { element.close(); if (invoker instanceof HTMLElement) invoker.focus() }
  }, [open, searchInput])
  return <dialog ref={dialog} className="component-explorer" aria-labelledby="component-explorer-title" onCancel={(event) => { event.preventDefault(); onClose() }}>
    <header><h2 id="component-explorer-title">Add component</h2><button type="button" aria-label="Close component explorer" onClick={onClose}><X size={16} aria-hidden="true" /></button></header>
    {children}
  </dialog>
}

const NODE_CARD_WIDTH = 230
const COLLISION_STEP = 24
function estimatedNodeHeight(nodePorts: readonly Port[]) {
  const inputs = nodePorts.filter((port) => port.direction === 'input').length
  return 61 + Math.max(inputs, nodePorts.length - inputs) * 24
}
function arrangedPositions(nodes: readonly WorkingNode[], measured: readonly Node<FlowData>[]) {
  const dimensions = new Map(measured.map((node) => [node.id, node.measured]))
  let x = 0, y = 0, rowHeight = 0
  return nodes.map((node, index) => {
    if (index > 0 && index % 6 === 0) { y += rowHeight + 40; x = 0; rowHeight = 0 }
    const size = dimensions.get(node.node_id)
    const position = { command: 'set_position', node_id: node.node_id, x, y }
    x += (size?.width ?? NODE_CARD_WIDTH) + 40
    rowHeight = Math.max(rowHeight, size?.height ?? estimatedNodeHeight(node.ports))
    return position
  })
}
function centredPosition(centre: { x: number; y: number }, positions: readonly { x: number; y: number }[], nodePorts: readonly Port[]) {
  const origin = { x: centre.x - NODE_CARD_WIDTH / 2, y: centre.y - estimatedNodeHeight(nodePorts) / 2 }
  const offsets = [{ x: 0, y: 0 }, { x: COLLISION_STEP, y: 0 }, { x: 0, y: COLLISION_STEP }, { x: -COLLISION_STEP, y: 0 }, { x: 0, y: -COLLISION_STEP }]
  return offsets.map((offset) => ({ x: origin.x + offset.x, y: origin.y + offset.y })).find((candidate) => !positions.some((position) => Math.abs(position.x - candidate.x) < COLLISION_STEP && Math.abs(position.y - candidate.y) < COLLISION_STEP)) ?? { x: origin.x + COLLISION_STEP, y: origin.y + COLLISION_STEP }
}
const EDITABLE_SELECTOR = 'input, textarea, select, [contenteditable]:not([contenteditable="false"]), [role="textbox"], [role="combobox"], [role="listbox"], [role="option"], dialog, [role="dialog"]'
function isEditableEvent(event: Event) {
  if (event.target instanceof Element && event.target.closest(EDITABLE_SELECTOR)) return true
  return event.composedPath().some((entry) => entry instanceof Element && Boolean(entry.closest(EDITABLE_SELECTOR)))
}

function helpValue(value: unknown) { return presentText(value === null ? 'None' : typeof value === 'string' ? value : JSON.stringify(value)) }
function NodeHelpDialog({ node, onClose, closeRef, dialogRef }: { node: WorkingNode; onClose: () => void; closeRef: React.RefObject<HTMLButtonElement | null>; dialogRef: React.RefObject<HTMLDivElement | null> }) {
  const help = node.help
  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Escape') { event.preventDefault(); onClose(); return }
    if (event.key !== 'Tab' || !dialogRef.current) return
    const focusable = [...dialogRef.current.querySelectorAll<HTMLElement>('a[href], button:not([disabled])')]
    if (!focusable.length) return
    const first = focusable[0]; const last = focusable.at(-1)!
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus() }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
  }
  return <div className="node-help-backdrop"><div ref={dialogRef} className="node-help-dialog" role="dialog" aria-modal="true" aria-labelledby="node-help-title" aria-describedby="node-help-description" onKeyDown={onKeyDown}>
    <header><div><span className="slate-eyebrow">Built-in node help</span><h2 id="node-help-title">{presentText(node.label)}</h2></div><button ref={closeRef} type="button" onClick={onClose}>Close</button></header>
    <p id="node-help-description">{presentText(help.description)}</p>
    <section aria-labelledby="node-help-semantics"><h3 id="node-help-semantics">Exact semantics</h3><p>{presentText(help.semantic_text)}</p></section>
    <section aria-labelledby="node-help-sources"><h3 id="node-help-sources">Sources</h3><ul>{help.sources.map((source) => <li key={source.source_record_id}><strong>{source.url ? <a href={source.url} target="_blank" rel="noreferrer">{presentText(source.title)}</a> : presentText(source.title)}</strong><span>{presentText(source.authors_or_organization)} · {presentText(source.publication_or_version)}{source.year === null ? '' : ` · ${source.year}`}</span></li>)}</ul></section>
    <section aria-labelledby="node-help-customisation"><h3 id="node-help-customisation">Parameters and customisation</h3><p>{presentText(help.customisation.guidance)}</p>{help.customisation.parameters.length ? <dl>{help.customisation.parameters.map((parameter) => <div key={parameter.name}><dt>{presentText(parameter.name)}</dt><dd>Type {presentText(parameter.type)}; {parameter.required ? 'required' : 'optional'}; default {helpValue(parameter.default)}; units {presentText(parameter.units)}; domain {helpValue(parameter.domain)}{parameter.enum === null ? '' : `; allowed values ${helpValue(parameter.enum)}`}</dd></div>)}</dl> : <p>No parameters.</p>}<p>{presentText(help.customisation.immutable_boundary)}</p></section>
    <section aria-labelledby="node-help-availability"><h3 id="node-help-availability">Availability</h3><p><strong>{help.availability.status === 'CONDITIONAL' ? 'Conditional' : 'Available'}</strong> · {presentText(help.availability.condition)}</p></section>
  </div></div>
}

function connectionOptions(nodes: readonly WorkingNode[], direction: 'input' | 'output'): SelectOption[] {
  const counts = new Map<string, number>(), seen = new Map<string, number>()
  for (const node of nodes) { const label = presentText(node.label); counts.set(label, (counts.get(label) ?? 0) + 1) }
  return nodes.flatMap((node) => {
    const label = presentText(node.label), ordinal = (seen.get(label) ?? 0) + 1; seen.set(label, ordinal)
    if (!node.ports.some((port) => port.direction === direction)) return []
    return [{ value: node.node_id, label: counts.get(label)! > 1 ? `${label} (${ordinal})` : label }]
  })
}

function connectionChoice(nodes: readonly WorkingNode[], nodeId: string, portId: string, direction: 'input' | 'output', fallback?: WorkingNode | null) {
  const node = nodes.find((item) => item.node_id === nodeId) ?? fallback ?? nodes.find((item) => item.ports.some((port) => port.direction === direction))
  const ports = node?.ports.filter((port) => port.direction === direction) ?? []
  return { node, ports, port: ports.find((item) => item.port_id === portId) ?? ports[0] }
}
function compatibleConnection(source?: WorkingNode, target?: WorkingNode, sourcePort?: Port, targetPort?: Port) {
  return Boolean(source && target && sourcePort && targetPort && source.node_id !== target.node_id && samePortType(sourcePort, targetPort))
}

function builderError(error: unknown) { return error instanceof SaveVerificationError ? error.message : errorMessage(error) }

function requireLayoutCommit(receipt: V2PresentationReceipt, base: V2Presentation) {
  if (receipt.intent !== 'EDIT' || receipt.base_presentation_revision !== base.presentation_revision) throw new SaveVerificationError('The layout save could not be verified.')
}

export function StrategyBuilderWorkspace({ api, project, graph, onPublished }: { api: StrategyApi; project: Project; graph: GraphSummary; onPublished: (published: PublishedGraph) => void }) {
  const [catalogue, setCatalogue] = useState<Load<VerifiedCatalogue>>({ kind: 'loading' }); const [draft, setDraft] = useState<Load<V2Draft>>({ kind: 'loading' }); const [presentation, setPresentation] = useState<Load<V2Presentation>>({ kind: 'loading' })
  const [attempt, setAttempt] = useState(0); const [query, setQuery] = useState(''); const [selectedId, setSelectedId] = useState<string | null>(null); const deferredSelection = useDeferredValue(selectedId)
  const [semantic, setSemantic] = useState<Command[]>([]); const [layout, setLayout] = useState<Command[]>([]); const [dragPositions, setDragPositions] = useState<Readonly<Record<string, Readonly<{ x: number; y: number }>>>>({}); const [feedback, setFeedback] = useState<string | null>(null); const [pending, setPending] = useState(false)
  const [editHistory, setEditHistory] = useState<EditHistory>({ past: [], future: [] })
  const [inputVersion, setInputVersion] = useState(0)
  const [semanticReceipt, setSemanticReceipt] = useState<V2SemanticReceipt | null>(null); const [semanticRedo, setSemanticRedo] = useState<V2SemanticReceipt | null>(null); const [layoutReceipt, setLayoutReceipt] = useState<V2PresentationReceipt | null>(null); const [redoLayoutCommands, setRedoLayoutCommands] = useState<readonly Command[]>([])
  const [connectionSource, setConnectionSource] = useState(''); const [connectionSourcePort, setConnectionSourcePort] = useState(''); const [connectionTarget, setConnectionTarget] = useState(''); const [connectionTargetPort, setConnectionTargetPort] = useState('')
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [saveBlocked, setSaveBlocked] = useState(false)
  const [libraryChanged, setLibraryChanged] = useState(false)
  const [libraryTarget, setLibraryTarget] = useState<string | null>(null)
  const [parameterErrors, setParameterErrors] = useState<Readonly<Record<string, boolean>>>({})
  const saveRequest = useRef<AbortController | null>(null)
  const savePhase = useRef<'draft' | 'layout' | 'readback' | 'publish' | 'published'>('draft')
  const observedVersion = useRef<number | null>(graph.current_version)
  useEffect(() => () => saveRequest.current?.abort(), [api, project.project_id, graph.identifier])
  const [helpNode, setHelpNode] = useState<WorkingNode | null>(null)
  const errorSummary = useRef<HTMLDivElement>(null); const removalFocus = useRef<string | null | undefined>(undefined)
  const builderRoot = useRef<HTMLElement>(null); const searchInput = useRef<HTMLInputElement>(null); const flowInstance = useRef<ReactFlowInstance<Node<FlowData>> | null>(null); const flowHost = useRef<HTMLDivElement | null>(null)
  const helpInvoker = useRef<HTMLButtonElement | null>(null); const helpClose = useRef<HTMLButtonElement>(null); const helpDialog = useRef<HTMLDivElement>(null)
  const focusFeedback = (message: string) => { setFeedback(message); requestAnimationFrame(() => errorSummary.current?.focus()) }
  const observePublished = async (current: V2Draft, signal: AbortSignal) => {
    const version = current.current_version
    if (version === null || version === observedVersion.current || current.published_revision !== current.semantic_revision) return
    const row = await api.v2Version(project.project_id, graph.identifier, version, signal)
    if (signal.aborted) return
    const contentAddress = publishedAddress(row, graph.identifier, version, current.graph_address)
    observedVersion.current = version
    onPublished({ project_id: project.project_id, identifier: graph.identifier, version, content_address: contentAddress })
  }
  const reload = useCallback(() => { if (saveRequest.current) return; setLibraryChanged(false); setLibraryTarget(null); setSaveBlocked(false); setParameterErrors({}); setSemantic([]); setLayout([]); setEditHistory({ past: [], future: [] }); setDragPositions({}); setCatalogue({ kind: 'loading' }); setDraft({ kind: 'loading' }); setPresentation({ kind: 'loading' }); setAttempt((value) => value + 1) }, [])
  useEffect(() => { const controller = new AbortController(); Promise.all([api.catalogue(controller.signal), api.v2Draft(project.project_id, graph.identifier, controller.signal), api.v2Presentation(project.project_id, graph.identifier, controller.signal)])
    .then(async ([nextCatalogue, nextDraft, nextPresentation]) => { await observePublished(nextDraft, controller.signal); if (!controller.signal.aborted) { setCatalogue({ kind: 'ready', value: nextCatalogue }); setDraft({ kind: 'ready', value: nextDraft }); setPresentation({ kind: 'ready', value: nextPresentation }); setSelectedId((current) => current && nextDraft.document.nodes.some((node) => node.node_id === current) ? current : null) } })
    .catch((error: unknown) => { if (!controller.signal.aborted) { const message = builderError(error); setCatalogue({ kind: 'error', message }); setDraft({ kind: 'error', message }); setPresentation({ kind: 'error', message }) } }); return () => controller.abort()
  }, [api, project.project_id, graph.identifier, attempt])
  const readyDraft = draft.kind === 'ready' ? draft.value : null; const readyCatalogue = catalogue.kind === 'ready' ? catalogue.value : null; const readyPresentation = presentation.kind === 'ready' ? presentation.value : null
  useEffect(() => {
    if (graph.current_version === null || !readyCatalogue) return
    const controller = new AbortController()
    Promise.resolve().then(() => api.v2Version(project.project_id, graph.identifier, graph.current_version!, controller.signal)).then((raw) => {
      parseSavedResearchPolicy(raw, graph.identifier, graph.current_version!)
      const registry = record(raw).registry_snapshot_address
      if (typeof registry !== 'string' || !/^sha256:[0-9a-f]{64}$/.test(registry)) return
      if (!controller.signal.aborted && observedVersion.current === graph.current_version && registry !== readyCatalogue.registry_identity) { setLibraryChanged(true); setLibraryTarget(readyCatalogue.registry_identity) }
    }).catch(() => { /* Normal publication still verifies the library on the server. */ })
    return () => controller.abort()
  }, [api, project.project_id, graph.identifier, graph.current_version, readyCatalogue])
  const working = useMemo(() => readyDraft && readyCatalogue ? workingProjection(readyDraft, readyCatalogue, semantic) : null, [readyDraft, readyCatalogue, semantic]); const selected = working?.nodes.find((node) => node.node_id === selectedId) ?? null; const traced = useMemo(() => traceIds(deferredSelection, working), [deferredSelection, working])
  useEffect(() => { const target = removalFocus.current; if (target === undefined) return; removalFocus.current = undefined; const nextNode = target ? builderRoot.current?.querySelector<HTMLElement>(`.react-flow__node[data-id="${CSS.escape(target)}"]`) : null; (nextNode ?? flowHost.current)?.focus() }, [working])
  useEffect(() => { const root = builderRoot.current; if (!root) return; const onKeyDown = (event: globalThis.KeyboardEvent) => { if (event.defaultPrevented || event.isComposing || event.repeat || event.ctrlKey || event.altKey || event.metaKey || !event.shiftKey || event.key.toLowerCase() !== 'a' || isEditableEvent(event)) return; event.preventDefault(); setPaletteOpen(true) }; root.addEventListener('keydown', onKeyDown); return () => root.removeEventListener('keydown', onKeyDown) }, [working])
  useEffect(() => { if (helpNode) requestAnimationFrame(() => helpClose.current?.focus()) }, [helpNode])
  const positionMap = useMemo(() => { const values = new Map(Object.entries(readyPresentation?.presentation.positions ?? {})); for (const command of layout) if (command.command === 'set_position') values.set(String(command.node_id), { x: Number(command.x), y: Number(command.y) }); return values }, [layout, readyPresentation])
  const openHelp = useCallback((node: WorkingNode, invoker: HTMLButtonElement) => { helpInvoker.current = invoker; setHelpNode(node) }, [])
  const closeHelp = useCallback(() => { setHelpNode(null); requestAnimationFrame(() => helpInvoker.current?.focus()) }, [])
  const flowNodes = useMemo(() => {
    const defaults = arrangedPositions(working?.nodes ?? [], [])
    return working?.nodes.map((node, index) => ({ id: node.node_id, type: 'strategy', position: dragPositions[node.node_id] ?? positionMap.get(node.node_id) ?? { x: defaults[index].x, y: defaults[index].y }, data: { node, selectedPath: traced.has(node.node_id), onHelp: openHelp }, selected: node.node_id === deferredSelection })) ?? []
  }, [deferredSelection, dragPositions, openHelp, positionMap, traced, working])
  const flowEdges = useMemo(() => working?.edges.map((edge) => ({ id: edge.edge_id, source: edge.source.node_id, sourceHandle: edge.source.port_id, target: edge.target.node_id, targetHandle: edge.target.port_id, label: `${edge.source.port_id} → ${edge.target.port_id}`, className: traced.has(edge.source.node_id) && traced.has(edge.target.node_id) ? 'workstation-edge--trace' : '' })) ?? [], [traced, working])
  const normalizedQuery = query.trim().toLowerCase(); const groups = useMemo(() => !readyCatalogue ? [] : readyCatalogue.groups.map((group) => ({ ...group, components: group.components.filter((component) => !normalizedQuery || [component.display_name, component.component_id, ...Object.keys(parameterRows(component))].some((value) => value.toLowerCase().includes(normalizedQuery))) })), [normalizedQuery, readyCatalogue])
  const rememberEdit = useCallback(() => {
    setEditHistory((history) => ({ past: [...history.past, { semantic, layout, selectedId }], future: [] }))
  }, [semantic, layout, selectedId])
  const restoreEdit = (direction: 'past' | 'future') => {
    const target = editHistory[direction].at(-1)
    if (!target) return false
    const current = { semantic, layout, selectedId }
    setEditHistory(direction === 'past'
      ? { past: editHistory.past.slice(0, -1), future: [...editHistory.future, current] }
      : { past: [...editHistory.past, current], future: editHistory.future.slice(0, -1) })
    setSemantic(target.semantic); setLayout(target.layout); setSelectedId(target.selectedId)
    setDragPositions({}); setParameterErrors({}); setInputVersion((version) => version + 1)
    removalFocus.current = target.selectedId
    setFeedback(direction === 'past' ? 'Change undone.' : 'Change restored.')
    return true
  }
  const stageAdd = (component: CatalogueComponent) => { if (!working) return; const instance = flowInstance.current; const host = flowHost.current; if (!instance || !host) { focusFeedback('The strategy canvas is not ready. Try adding the node again.'); return } const rect = host.getBoundingClientRect(); if (rect.width <= 0 || rect.height <= 0) { focusFeedback('The strategy canvas is not ready. Try adding the node again.'); return } const centre = instance.screenToFlowPosition({ x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 }); const position = centredPosition(centre, [...positionMap.values()], ports(component)); const id = instanceId(component, new Set(working.nodes.map((node) => node.node_id))); rememberEdit(); setSemantic((commands) => [...commands, { command: 'add_node', node_id: id, component_id: component.component_id, component_version: component.component_version, parameters: {} }]); setLayout((commands) => [...commands, { command: 'set_position', node_id: id, ...position }]); setSelectedId(id); setPaletteOpen(false); setFeedback(`${presentText(component.display_name)} is staged on the visible canvas.`) }
  const connect = useCallback((connection: Connection) => { if (!connection.source || !connection.target || !connection.sourceHandle || !connection.targetHandle) return; rememberEdit(); setSemantic((commands) => [...commands, { command: 'connect', source: { node_id: connection.source, port_id: connection.sourceHandle }, target: { node_id: connection.target, port_id: connection.targetHandle }, binding: { kind: 'single' } }]); setFeedback('Strategy connection staged. The server will validate the final batch.') }, [rememberEdit])
  const disconnect = useCallback((edge: WorkingEdge) => { rememberEdit(); setSemantic((commands) => [...commands, { command: 'disconnect', source: edge.source, target: edge.target, binding: edge.binding }]) }, [rememberEdit])
  const clearDragPosition = useCallback((id: string) => setDragPositions((current) => { if (!Object.hasOwn(current, id)) return current; const next = { ...current }; delete next[id]; return next }), [])
  const stagePosition = useCallback((id: string, x: number, y: number) => { clearDragPosition(id); rememberEdit(); setLayout((commands) => [...commands, { command: 'set_position', node_id: id, x, y }]) }, [clearDragPosition, rememberEdit])
  const trackDrag = useCallback((id: string, x: number, y: number) => setDragPositions((current) => { const previous = current[id]; return previous?.x === x && previous.y === y ? current : { ...current, [id]: { x, y } } }), [])
  const removeSelected = useCallback(() => { if (saveRequest.current || !selected || !working) return; const index = working.nodes.findIndex((node) => node.node_id === selected.node_id); const remaining = working.nodes.filter((node) => node.node_id !== selected.node_id); const next = remaining[Math.min(index, remaining.length - 1)] ?? null; removalFocus.current = next?.node_id ?? null; rememberEdit(); clearDragPosition(selected.node_id); setParameterErrors((errors) => Object.fromEntries(Object.entries(errors).filter(([key]) => JSON.parse(key)[0] !== selected.node_id))); setSemantic((commands) => [...commands, { command: 'remove_node', node_id: selected.node_id }]); setSelectedId(next?.node_id ?? null); setFeedback(`Removal of ${presentText(selected.label)} and its connections is staged.`) }, [clearDragPosition, rememberEdit, selected, working])
  useLayoutEffect(() => { const onDelete = (event: globalThis.KeyboardEvent) => { if (event.defaultPrevented || event.isComposing || event.repeat || event.ctrlKey || event.altKey || event.metaKey || event.shiftKey || helpNode || paletteOpen || !selected || !['Delete', 'Backspace'].includes(event.key) || isEditableEvent(event)) return; event.preventDefault(); removeSelected() }; window.addEventListener('keydown', onDelete); return () => window.removeEventListener('keydown', onDelete) }, [helpNode, paletteOpen, removeSelected, selected])
  const arrange = () => { if (!working) return; rememberEdit(); setLayout(arrangedPositions(working.nodes, flowInstance.current?.getNodes() ?? [])); setFeedback('Layout staged. Strategy behavior is unchanged.') }
  const readPair = async (signal: AbortSignal) => {
    const [nextDraft, nextPresentation] = await Promise.all([api.v2Draft(project.project_id, graph.identifier, signal), api.v2Presentation(project.project_id, graph.identifier, signal)])
    if (signal.aborted) throw new DOMException('Save cancelled', 'AbortError')
    return { nextDraft, nextPresentation }
  }
  const acceptPair = (pair: { nextDraft: V2Draft; nextPresentation: V2Presentation }) => {
    setDraft({ kind: 'ready', value: pair.nextDraft }); setPresentation({ kind: 'ready', value: pair.nextPresentation })
    return pair
  }
  const refreshServer = async () => acceptPair(await readPair(new AbortController().signal))

  const validate = async () => { if (!readyDraft || !semantic.length) return; setPending(true); try { await api.validateV2(project.project_id, graph.identifier, readyDraft.semantic_revision, semantic, new AbortController().signal); focusFeedback('Strategy check completed. Nothing was saved.') } catch (error) { focusFeedback(errorMessage(error)) } finally { setPending(false) } }
  const readSaved = async (expected: V2Draft, signal: AbortSignal, presentationRevision?: number) => {
    const { nextDraft, nextPresentation } = await readPair(signal)
    if (nextDraft.semantic_revision !== expected.semantic_revision || nextDraft.content_address !== expected.content_address || nextDraft.graph_address !== expected.graph_address
      || nextDraft.current_version !== expected.current_version || (presentationRevision !== undefined && nextPresentation.presentation_revision !== presentationRevision)) {
      throw new SaveVerificationError('The saved draft changed during this save. Reload and review it before continuing.')
    }
    return acceptPair({ nextDraft, nextPresentation })
  }
  const commitSemantic = async (current: { nextDraft: V2Draft; nextPresentation: V2Presentation }, signal: AbortSignal) => {
    if (!semantic.length) return current
    savePhase.current = 'draft'
    const committed = await api.mutateV2(project.project_id, graph.identifier, current.nextDraft.semantic_revision, semantic, 'EDIT', null, signal)
    if (signal.aborted) throw new DOMException('Save cancelled', 'AbortError')
    requireSemanticCommit(committed, current.nextDraft)
    setSemanticReceipt(committed); setSemanticRedo(null)
    savePhase.current = 'readback'
    const saved = await readSaved({ ...current.nextDraft, semantic_revision: committed.result_semantic_revision, content_address: committed.result_content_address, graph_address: committed.result_graph_address }, signal)
    setSemantic((commands) => commands.slice(semantic.length))
    setEditHistory({ past: layout.length ? [{ semantic: [], layout: [], selectedId }] : [], future: [] })
    return saved
  }
  const commitLayout = async (current: { nextDraft: V2Draft; nextPresentation: V2Presentation }, signal: AbortSignal) => {
    if (!layout.length) return current
    savePhase.current = 'layout'
    const receipt = await api.mutateV2Presentation(project.project_id, graph.identifier, current.nextDraft.semantic_revision, current.nextPresentation.presentation_revision, layout, 'EDIT', null, signal)
    if (signal.aborted) throw new DOMException('Save cancelled', 'AbortError')
    requireLayoutCommit(receipt, current.nextPresentation)
    setLayoutReceipt(receipt); setRedoLayoutCommands(receipt.forward_commands); setEditHistory({ past: [], future: [] })
    savePhase.current = 'readback'
    const saved = await readSaved(current.nextDraft, signal, receipt.result_presentation_revision)
    setLayout((commands) => commands.slice(layout.length))
    return saved
  }
  const refreshPublished = async (saved: V2Draft, version: number, signal: AbortSignal) => {
    const pair = await readPair(signal), current = pair.nextDraft
    requirePublishedDraft(current, saved, version)
    acceptPair(pair)
  }
  const publishSaved = async (saved: V2Draft, signal: AbortSignal, target?: string) => {
    if (target === undefined && saved.published_revision === saved.semantic_revision) { focusFeedback('Layout saved. The strategy version is unchanged.'); return }
    savePhase.current = 'publish'
    const receipt = await api.publishV2(project.project_id, graph.identifier, saved.semantic_revision, saved.current_version, signal, ...(target === undefined ? [] : [target]))
    if (signal.aborted) throw new DOMException('Save cancelled', 'AbortError')
    requirePublication(receipt, saved)
    setLibraryChanged(false); setLibraryTarget(null)
    setSemanticReceipt(null); setSemanticRedo(null)
    observedVersion.current = receipt.graph_version
    onPublished({ project_id: project.project_id, identifier: graph.identifier, version: receipt.graph_version, content_address: receipt.content_address })
    savePhase.current = 'published'
    await refreshPublished(saved, receipt.graph_version, signal)
    focusFeedback(`Saved strategy version ${receipt.graph_version}.`)
  }
  const saveFailure = (error: unknown) => {
    const uncertain = ['readback', 'published'].includes(savePhase.current) || !(error instanceof ApiError && error.kind === 'input')
    if (uncertain) setSaveBlocked(true)
    const message = savePhase.current === 'published' ? `Version ${observedVersion.current} is saved. Reload to refresh the draft.`
      : uncertain ? 'Save status is uncertain. Local changes are retained. Reload to check before saving again.'
      : savePhase.current === 'publish' ? 'The draft is saved, but the version was not saved. Try Save version again.'
        : savePhase.current === 'layout' ? 'The layout was not saved. Retry to save the remaining changes.' : 'Your changes were not saved.'
    focusFeedback(`${message} ${builderError(error)}`)
  }
  const refreshLibrary = async (signal: AbortSignal) => {
    setLibraryChanged(true); setLibraryTarget(null)
    focusFeedback('Your components have changed. Your edits are retained. Earlier results belong to the old version. Review the current components, then save an updated version and run a new backtest.')
    try {
      const current = await api.catalogue(signal)
      if (!signal.aborted) { setCatalogue({ kind: 'ready', value: current }); setLibraryTarget(current.registry_identity) }
    } catch (error) { if (!signal.aborted) focusFeedback(`Current components could not be loaded. Retry the review. ${builderError(error)}`) }
  }
  const reviewLibrary = async () => {
    if (saveRequest.current) return
    const controller = new AbortController(); saveRequest.current = controller; setPending(true)
    try { await refreshLibrary(controller.signal) }
    finally { if (saveRequest.current === controller) { saveRequest.current = null; setPending(false) } }
  }
  const handleSaveFailure = async (error: unknown, signal: AbortSignal) => {
    if (signal.aborted) return
    if (savePhase.current === 'draft' && error instanceof ApiError && error.envelope?.code === 'RECEIPT_SEAL_UNAVAILABLE') {
      focusFeedback('The server cannot save edits until the workspace configuration is fixed. Your changes are retained. Contact the workspace administrator, then retry saving.')
      return
    }
    if (error instanceof ApiError && error.envelope?.code === 'STRATEGY_LIBRARY_CHANGED') await refreshLibrary(signal)
    else saveFailure(error)
  }
  const save = async (publishVersion: boolean, base: { nextDraft: V2Draft; nextPresentation: V2Presentation }, target?: string) => {
    if (saveRequest.current || saveBlocked || Object.keys(parameterErrors).length) return
    const controller = new AbortController(); saveRequest.current = controller
    setPending(true); savePhase.current = 'draft'
    try {
      const semanticSaved = await commitSemantic(base, controller.signal)
      const saved = await commitLayout(semanticSaved, controller.signal)
      if (publishVersion) await publishSaved(saved.nextDraft, controller.signal, target)
      else focusFeedback('Draft applied.')
    } catch (error) { await handleSaveFailure(error, controller.signal) }
    finally { if (saveRequest.current === controller) { setPending(false); saveRequest.current = null } }
  }
  const stageParameter = (nodeId: string, parameterId: string, rawValue: string, notify = true) => {
    const key = parameterKey(nodeId, parameterId)
    try {
      const value: unknown = JSON.parse(rawValue)
      const commands = stageParameterCommand(semantic, { command: 'set_parameter', node_id: nodeId, parameter_id: parameterId, value })
      setParameterErrors((errors) => Object.fromEntries(Object.entries(errors).filter(([name]) => name !== key)))
      if (JSON.stringify(commands) === JSON.stringify(semantic)) return
      rememberEdit(); setSemantic(commands)
    } catch { setParameterErrors((errors) => ({ ...errors, [key]: true })); if (notify) focusFeedback(`${parameterId} must be valid JSON.`) }
  }

  const undo = async () => { if (pending || saveBlocked || saveRequest.current) return; if (restoreEdit('past')) return; if (semantic.length || layout.length || editHistory.future.length || !readyDraft || !semanticReceipt || semanticRedo) return; setPending(true); try { if (layoutReceipt) await api.mutateV2Presentation(project.project_id, graph.identifier, readyDraft.semantic_revision, layoutReceipt.result_presentation_revision, layoutReceipt.inverse_commands, 'UNDO', layoutReceipt, new AbortController().signal); const receipt = await api.mutateV2(project.project_id, graph.identifier, readyDraft.semantic_revision, semanticReceipt.inverse_commands, 'UNDO', semanticReceipt, new AbortController().signal); setSemanticRedo(receipt); await refreshServer(); focusFeedback('Undo restored the prior draft and layout.') } catch (error) { focusFeedback(errorMessage(error)); await refreshServer().catch(() => undefined) } finally { setPending(false) } }
  const redo = async () => { if (pending || saveBlocked || saveRequest.current) return; if (restoreEdit('future')) return; if (semantic.length || layout.length || !readyDraft || !semanticRedo) return; setPending(true); try { const receipt = await api.mutateV2(project.project_id, graph.identifier, readyDraft.semantic_revision, semanticRedo.inverse_commands, 'REDO', semanticRedo, new AbortController().signal); setSemanticReceipt(receipt); setSemanticRedo(null); const currentPresentation = await api.v2Presentation(project.project_id, graph.identifier, new AbortController().signal); if (redoLayoutCommands.length) { const nextLayout = await api.mutateV2Presentation(project.project_id, graph.identifier, receipt.result_semantic_revision, currentPresentation.presentation_revision, redoLayoutCommands, 'EDIT', null, new AbortController().signal); setLayoutReceipt(nextLayout) } await refreshServer(); focusFeedback('Redo restored the strategy graph and layout.') } catch (error) { focusFeedback(errorMessage(error)); await refreshServer().catch(() => undefined) } finally { setPending(false) } }

  useEffect(() => {
    const onHistoryKey = (event: globalThis.KeyboardEvent) => {
      if (event.defaultPrevented || event.isComposing || event.repeat || event.altKey || !(event.metaKey || event.ctrlKey) || event.key.toLowerCase() !== 'z') return
      if (helpNode || paletteOpen || isEditableEvent(event)) return
      if (event.target instanceof Element && !builderRoot.current?.contains(event.target)) return
      event.preventDefault(); void (event.shiftKey ? redo() : undo())
    }
    window.addEventListener('keydown', onHistoryKey)
    return () => window.removeEventListener('keydown', onHistoryKey)
  }, [helpNode, paletteOpen, undo, redo])

  const searchKey = (event: KeyboardEvent<HTMLInputElement>) => { if (event.key !== 'Enter') return; const first = groups.flatMap((group) => group.components)[0]; if (first) { event.preventDefault(); stageAdd(first) } }
  if ([catalogue, draft, presentation].some((state) => state.kind === 'loading')) return <p role="status" className="workstation-state">Loading strategy builder…</p>
  const failed = [catalogue, draft, presentation].find((state) => state.kind === 'error'); if (failed?.kind === 'error') return <div className="workstation-state"><p role="alert">{failed.message}</p><button onClick={reload}>Retry</button></div>
  if (!working || !readyDraft || !readyCatalogue || !readyPresentation) return null
  const { node: sourceNode, ports: sourcePorts, port: sourcePort } = connectionChoice(working.nodes, connectionSource, connectionSourcePort, 'output')
  const { node: targetNode, ports: targetPorts, port: targetPort } = connectionChoice(working.nodes, connectionTarget, connectionTargetPort, 'input', selected)
  const compatible = compatibleConnection(sourceNode, targetNode, sourcePort, targetPort)
  const stageKeyboardConnection = () => { if (!sourceNode || !targetNode || !sourcePort || !targetPort) return; if (!compatible) { focusFeedback('Connection refused before publish: the port type, flow or shape differs.'); return } connect({ source: sourceNode.node_id, sourceHandle: sourcePort.port_id, target: targetNode.node_id, targetHandle: targetPort.port_id } as Connection) }
  const selectedComponent = selected ? readyCatalogue.groups.flatMap((group) => group.components).find((component) => component.component_id === selected.component_id && component.component_version === selected.component_version) : undefined
  function renderHistoryActions(writesBlocked: boolean, changesStaged: boolean) {
    const canUndo = editHistory.past.length > 0 || (!changesStaged && !editHistory.future.length && semanticReceipt !== null && semanticRedo === null)
    const canRedo = editHistory.future.length > 0 || (!changesStaged && semanticRedo !== null)
    return <><button aria-label="Undo draft" title="Undo (⌘Z / Ctrl+Z)" aria-keyshortcuts="Meta+Z Control+Z" onClick={() => void undo()} disabled={writesBlocked || !canUndo}><Undo2 aria-hidden="true" /></button><button aria-label="Redo draft" title="Redo (⇧⌘Z / Ctrl+Shift+Z)" aria-keyshortcuts="Meta+Shift+Z Control+Shift+Z" onClick={() => void redo()} disabled={writesBlocked || !canRedo}><Redo2 aria-hidden="true" /></button></>
  }
  function renderActions(currentDraft: V2Draft, currentPresentation: V2Presentation) {
    const writesBlocked = pending || saveBlocked
    const invalidParameters = Object.keys(parameterErrors).length > 0
    const changesStaged = Boolean(semantic.length || layout.length)
    return <div className="workstation-actions"><button onClick={() => setPaletteOpen(true)} aria-haspopup="dialog" aria-keyshortcuts="Shift+A"><Plus aria-hidden="true" />Add component</button>
    {renderHistoryActions(writesBlocked, changesStaged)}<button onClick={reload} aria-label={saveBlocked && changesStaged ? 'Discard staged changes and reload' : 'Reload'} title={saveBlocked && changesStaged ? 'Discard staged changes and reload' : 'Reload'}><RotateCcw aria-hidden="true" /></button><button aria-label="Arrange" title="Arrange components" onClick={arrange}><LayoutGrid aria-hidden="true" /></button><button onClick={() => void validate()} disabled={writesBlocked || !semantic.length}><Check aria-hidden="true" />Check strategy</button><button onClick={() => void save(false, { nextDraft: currentDraft, nextPresentation: currentPresentation })} disabled={writesBlocked || invalidParameters || !changesStaged}>Apply draft</button><button className="workstation-primary" onClick={() => void save(true, { nextDraft: currentDraft, nextPresentation: currentPresentation })} disabled={libraryChanged || writesBlocked || invalidParameters || (!changesStaged && currentDraft.published_revision === currentDraft.semantic_revision)}>Save version</button>{libraryChanged && <><p>Components have changed. Earlier results belong to the old version. Save an updated version, then run a new backtest.</p>{libraryTarget ? <button disabled={writesBlocked || invalidParameters} onClick={() => void save(true, { nextDraft: currentDraft, nextPresentation: currentPresentation }, libraryTarget)}>Save updated version</button> : <button disabled={writesBlocked} onClick={() => void reviewLibrary()}>Review current components</button>}</>}
  </div>
  }
  function renderInspector(currentGraph: WorkingGraph) {
    return <aside key={`${selectedId}:${inputVersion}`} className="inspector-pane" aria-label="Component settings" onKeyDown={(event) => { if (event.key === 'Escape' && !event.defaultPrevented) { event.preventDefault(); setSelectedId(null); flowHost.current?.focus() } }}><header><h3>{selected ? presentText(selected.label) : 'Component'}</h3><button aria-label="Close component settings" onClick={() => { setSelectedId(null); flowHost.current?.focus() }}><X size={15} aria-hidden="true" /></button></header>{selected ? <><h4>Parameters</h4>{Object.entries(parameterRows(selectedComponent)).length ? Object.entries(parameterRows(selectedComponent)).map(([parameterId, raw]) => { const definition = record(raw); const value = Object.hasOwn(selected.parameters, parameterId) ? selected.parameters[parameterId] : definition.default; return <label key={parameterKey(selected.node_id, parameterId)}>{labelFor(parameterId)}<input defaultValue={JSON.stringify(value)} aria-invalid={Boolean(parameterErrors[parameterKey(selected.node_id, parameterId)])} onChange={(event) => stageParameter(selected.node_id, parameterId, event.currentTarget.value, false)} onBlur={(event) => stageParameter(selected.node_id, parameterId, event.currentTarget.value)} /></label> }) : <p>No editable parameters.</p>}
      <h4>Keyboard connection</h4><div className="inspector-control-grid"><label>Source node<TraderSelect label="Source node" value={sourceNode?.node_id ?? ''} onValueChange={(value) => { setConnectionSource(value); setConnectionSourcePort('') }} options={connectionOptions(currentGraph.nodes, 'output')} /></label><label>Source port<TraderSelect label="Source port" value={sourcePort?.port_id ?? ''} onValueChange={setConnectionSourcePort} options={sourcePorts.map((port) => ({ value: port.port_id, label: labelFor(port.port_id) }))} /></label><label>Target node<TraderSelect label="Target node" value={targetNode?.node_id ?? ''} onValueChange={(value) => { setConnectionTarget(value); setConnectionTargetPort('') }} options={connectionOptions(currentGraph.nodes, 'input')} /></label><label>Target port<TraderSelect label="Target port" value={targetPort?.port_id ?? ''} onValueChange={setConnectionTargetPort} options={targetPorts.map((port) => ({ value: port.port_id, label: labelFor(port.port_id) }))} /></label></div><button onClick={stageKeyboardConnection} disabled={!sourceNode || !sourcePort || !targetNode || !targetPort}>Stage typed connection</button>
      {currentGraph.edges.filter((edge) => edge.source.node_id === selected.node_id || edge.target.node_id === selected.node_id).map((edge) => <button key={edge.edge_id} onClick={() => disconnect(edge)}>Disconnect {presentText(currentGraph.nodes.find((node) => node.node_id === edge.source.node_id)?.label ?? 'component')} → {presentText(currentGraph.nodes.find((node) => node.node_id === edge.target.node_id)?.label ?? 'component')}</button>)}
      <button className="workstation-danger" aria-keyshortcuts="Delete Backspace" onClick={removeSelected}><Trash2 aria-hidden="true" />Stage node removal <kbd aria-hidden="true">Delete</kbd></button></> : <p>Select a node to inspect its identity and ports.</p>}</aside>
  }
  function renderFeedback() { return feedback ? <div ref={errorSummary} tabIndex={-1} className="workstation-feedback" role="status">{feedback}</div> : null }
  return <section ref={builderRoot} inert={pending} className="builder-workstation" aria-labelledby="builder-title">{helpNode && <NodeHelpDialog node={helpNode} onClose={closeHelp} closeRef={helpClose} dialogRef={helpDialog} />}<header className="workstation-command"><div><span className="slate-eyebrow">Strategy graph workspace</span><h2 id="builder-title">Build strategy</h2></div>{renderActions(readyDraft, readyPresentation)}<span className="staged-summary">{semantic.length + layout.length ? 'Unsaved changes' : 'Draft saved'}</span></header><ComponentExplorer open={paletteOpen} onClose={() => setPaletteOpen(false)} searchInput={searchInput}><div className="palette-content"><label htmlFor="node-search">Search node library</label><div className="workstation-search"><Search aria-hidden="true" /><input ref={searchInput} id="node-search" value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={searchKey} placeholder="Search components" /></div>{groups.map((group, index) => <PaletteFamily key={group.visible_family} group={group} initiallyOpen={index === 0} forceOpen={Boolean(normalizedQuery)} onAdd={stageAdd} />)}</div></ComponentExplorer><div className="builder-grid">
    <FlowCanvas nodes={flowNodes} edges={flowEdges} onSelect={setSelectedId} onConnect={connect} onDragFrame={trackDrag} onDragEnd={stagePosition} onReady={(instance, element) => { flowInstance.current = instance; flowHost.current = element }} />
    {selected && renderInspector(working)}</div>
    {renderFeedback()}
  </section>
}
