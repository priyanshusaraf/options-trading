import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'
import {
  Background, BackgroundVariant, Controls, Handle, NodeResizer, NodeToolbar, Position,
  ReactFlow, addEdge, reconnectEdge, useEdgesState, useNodesState,
  type Connection, type Edge, type EdgeChange, type FinalConnectionState, type Node,
  type NodeChange, type NodeProps, type ReactFlowInstance, type XYPosition,
} from '@xyflow/react'
import {
  CheckCircle2, ChevronDown, Code2, Copy, FileUp, Filter, Focus, Grip, PanelLeftClose,
  PanelLeftOpen, PanelRightClose, PanelRightOpen, Plus, RotateCcw, Search,
  ShieldCheck, SlidersHorizontal, Trash2, X,
} from 'lucide-react'
import type { GNode, NodeKind, Strategy } from '../data/model'
import { connectionForInsertedNode, type PendingConnection } from './graphUtils'
import { Badge, Button, IconButton, KeyValue, Panel, PanelHeader, Segmented, cx } from './ui'

type Projection = 'graph' | 'form' | 'tree' | 'code'

interface FlowNodeData extends Record<string, unknown> {
  node: GNode
  onFieldChange?: (id: string, label: string, value: string) => void
  onTitleChange?: (id: string, value: string) => void
  onDuplicate?: (id: string) => void
  onDelete?: (id: string) => void
}

type StrategyFlowNode = Node<FlowNodeData, 'strategyNode'>

interface NodeTemplate {
  title: string
  kind: NodeKind
  sub: string
  fields: [string, string][]
}

interface QuickAddContext {
  canvasPosition: XYPosition
  flowPosition: XYPosition
  connection: PendingConnection
}

interface CsvImportState {
  tone: 'ready' | 'error'
  message: string
}

const nodeTemplates: Array<{ group: string; items: NodeTemplate[] }> = [
  { group: 'Inputs', items: [
    { title: 'Market data', kind: 'data', sub: 'Completed bars', fields: [['role', 'UNDERLYING'], ['timeframe', '5m'], ['freshness', '< 15 sec']] },
    { title: 'Options chain', kind: 'options', sub: 'Point-in-time chain', fields: [['expiry', 'nearest weekly'], ['greeks', 'enabled'], ['depth', '5 levels']] },
    { title: 'Event calendar', kind: 'data', sub: 'Scheduled events', fields: [['source', 'rulebook'], ['window', '± 30m'], ['missing', 'reject']] },
  ] },
  { group: 'Signals', items: [
    { title: 'Opening range', kind: 'indicator', sub: 'Session range', fields: [['window', '15m'], ['reset', 'daily'], ['input', 'completed bar']] },
    { title: 'Breadth', kind: 'indicator', sub: 'Constituent breadth', fields: [['universe', 'point-in-time'], ['threshold', '58%'], ['missing', 'reject']] },
    { title: 'Realised volatility', kind: 'indicator', sub: 'Rolling estimate', fields: [['window', '20 bars'], ['method', 'close-close'], ['annualise', 'yes']] },
  ] },
  { group: 'Logic', items: [
    { title: 'AND gate', kind: 'logic', sub: 'All inputs required', fields: [['inputs', '2'], ['null', 'false'], ['short circuit', 'yes']] },
    { title: 'Session state', kind: 'state', sub: 'Stateful session rule', fields: [['initial', 'waiting'], ['reset', 'session open'], ['persist', 'research run']] },
    { title: 'Once per day', kind: 'state', sub: 'Entry counter', fields: [['limit', '1 / side'], ['reset', 'next session'], ['scope', 'strategy']] },
  ] },
  { group: 'Risk', items: [
    { title: 'ATR protection', kind: 'risk', sub: 'Initial and trailing', fields: [['initial', '2.0 ATR'], ['trail', '1.6 ATR'], ['priority', 'exit first']] },
    { title: 'Time stop', kind: 'risk', sub: 'Mandatory flatten', fields: [['time', '15:20 IST'], ['grace', '30 sec'], ['priority', 'exit first']] },
    { title: 'Portfolio budget', kind: 'risk', sub: 'Capital floor', fields: [['risk', '0.75%'], ['drawdown', '9%'], ['precedence', 'strictest']] },
  ] },
  { group: 'Execution', items: [
    { title: 'Order intent', kind: 'execution', sub: 'Non-authoritative intent', fields: [['type', 'marketable limit'], ['timeout', '8 sec'], ['role', 'EXECUTION_MARKET']] },
    { title: 'Instrument role', kind: 'execution', sub: 'Strategy binding', fields: [['role', 'EXECUTION_MARKET'], ['resolve', 'at preflight'], ['fallback', 'none']] },
    { title: 'Paper adapter', kind: 'execution', sub: 'Synthetic execution', fields: [['mode', 'paper only'], ['slippage', '1.8 bps'], ['money', 'synthetic']] },
  ] },
]

const kindTone: Record<NodeKind, 'violet' | 'info' | 'good' | 'warn' | 'neutral'> = {
  data: 'info', indicator: 'violet', logic: 'good', state: 'neutral', risk: 'warn', execution: 'neutral', options: 'violet',
}

function StrategyNodeView({ id, data, selected }: NodeProps<StrategyFlowNode>) {
  const node = data.node
  return (
    <div className={cx('strategy-flow-node', selected && 'is-selected')} data-kind={node.kind}>
      <NodeResizer isVisible={selected} minWidth={172} minHeight={120} lineClassName="strategy-flow-resize-line" handleClassName="strategy-flow-resize-handle" />
      <NodeToolbar isVisible={selected} position={Position.Top} align="end" className="strategy-flow-toolbar">
        <button type="button" aria-label={`Duplicate ${node.title}`} onClick={() => data.onDuplicate?.(id)}><Copy size={12} /></button>
        <button type="button" aria-label={`Delete ${node.title}`} onClick={() => data.onDelete?.(id)}><Trash2 size={12} /></button>
      </NodeToolbar>
      <header className="strategy-flow-node__drag"><Grip size={12} /><span>{node.kind}</span>{node.badge ? <b>{node.badge}</b> : null}</header>
      <div className="strategy-flow-node__identity">
        <input className="nodrag nowheel" aria-label={`${node.title} title`} value={node.title} onChange={(event) => data.onTitleChange?.(id, event.target.value)} />
        <small>{node.sub}</small>
      </div>
      <div className="strategy-flow-node__fields">
        {(node.fields ?? []).map(([label, value], index) => (
          <label key={label}>
            <Handle aria-label={`Connect to ${node.title} ${label}`} className="strategy-flow-handle strategy-flow-handle--target" type="target" position={Position.Left} id={`input-${index}`} />
            <span>{label}</span>
            <input className="nodrag nowheel" aria-label={`${node.title} ${label}`} value={value} onChange={(event) => data.onFieldChange?.(id, label, event.target.value)} />
          </label>
        ))}
      </div>
      <div className="strategy-flow-node__output">
        <span>output</span><b>{node.kind === 'risk' ? 'protected intent' : node.kind === 'execution' ? 'paper record' : 'typed value'}</b>
        <Handle aria-label={`Connect ${node.title} output`} className="strategy-flow-handle strategy-flow-handle--source" type="source" position={Position.Right} id="output" />
      </div>
    </div>
  )
}

const nodeTypes = { strategyNode: StrategyNodeView }

function toFlowNodes(strategy: Strategy): StrategyFlowNode[] {
  return strategy.graph.nodes.map((node) => ({
    id: node.id,
    type: 'strategyNode',
    position: { x: node.x, y: node.y },
    data: { node: structuredClone(node) },
    style: { width: node.w ?? 190 },
  }))
}

function toFlowEdges(strategy: Strategy): Edge[] {
  return strategy.graph.edges.map((edge, index) => ({
    id: `${edge.from}-${edge.to}-${index}`,
    source: edge.from,
    target: edge.to,
    sourceHandle: 'output',
    targetHandle: 'input-0',
    label: edge.label,
    type: 'smoothstep',
    className: `strategy-flow-edge strategy-flow-edge--${edge.kind ?? 'data'}`,
  }))
}

function FormProjection({ strategy }: { strategy: Strategy }) {
  return <div className="projection-form">{strategy.graph.nodes.map((node, index) => <section key={node.id}><div className="projection-form__index">{String(index + 1).padStart(2, '0')}</div><div><Badge tone={kindTone[node.kind]}>{node.kind}</Badge><h3>{node.title}</h3><p>{node.sub}</p></div><div>{node.fields?.map(([label, value]) => <KeyValue key={label} label={label} value={value} mono />)}</div></section>)}</div>
}

function TreeProjection({ strategy }: { strategy: Strategy }) {
  return <div className="projection-tree"><div className="projection-tree__root"><ChevronDown size={14} /><strong>{strategy.code}</strong><Badge tone="violet">immutable strategy IR</Badge></div>{strategy.graph.nodes.map((node) => <div className="projection-tree__row" key={node.id}><span className="tree-stem" /><ChevronDown size={13} /><Badge tone={kindTone[node.kind]}>{node.kind}</Badge><strong>{node.title}</strong><span>{node.sub}</span></div>)}</div>
}

function CodeProjection({ strategy }: { strategy: Strategy }) {
  return <pre className="projection-code" aria-label="Read-only code projection"><code>{`strategy "${strategy.code}" {
  version = "${strategy.draftId}"
  authority = "research-only"

${strategy.graph.nodes.map((node) => `  ${node.kind} "${node.id}" {
    title = "${node.title}"
${(node.fields ?? []).map(([key, value]) => `    ${key} = "${value}"`).join('\n')}
  }`).join('\n\n')}

  // Projection only. Saving creates a new immutable draft.
}`}</code></pre>
}

function QuickAdd({ query, context, onQuery, onAdd, onClose }: { query: string; context: QuickAddContext | null; onQuery: (value: string) => void; onAdd: (template: NodeTemplate) => void; onClose: () => void }) {
  const items = nodeTemplates.flatMap((group) => group.items).filter((item) => `${item.title} ${item.kind}`.toLowerCase().includes(query.toLowerCase()))
  const inputRef = useRef<HTMLInputElement>(null)
  useEffect(() => {
    inputRef.current?.focus()
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      event.preventDefault()
      onClose()
    }
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [onClose])
  const style = context ? ({ '--quick-add-x': `${context.canvasPosition.x}px`, '--quick-add-y': `${context.canvasPosition.y}px` } as CSSProperties) : undefined
  const contextCopy = context ? `${context.connection.handleType === 'target' ? 'Insert before' : 'Insert after'} ${context.connection.nodeTitle}` : null
  return (
    <div className={cx('graph-quick-add', context && 'is-anchored')} style={style} role="dialog" aria-label="Add node" aria-describedby={contextCopy ? 'quick-add-context' : undefined}>
      <header><Search size={14} /><input ref={inputRef} value={query} onChange={(event) => onQuery(event.target.value)} placeholder="Add a node" /><kbd>Shift A</kbd><IconButton label="Close node palette" onClick={onClose}><X size={14} /></IconButton></header>
      {contextCopy ? <p className="graph-quick-add__context" id="quick-add-context">{contextCopy}<span>The new node will be connected automatically.</span></p> : null}
      <div>{items.map((item) => <button type="button" key={`${item.kind}-${item.title}`} onClick={() => onAdd(item)}><span data-kind={item.kind}>{item.kind}</span><div><strong>{item.title}</strong><small>{item.sub}</small></div><Plus size={13} /></button>)}{!items.length ? <p>No matching node</p> : null}</div>
    </div>
  )
}

function pointerFromEvent(event: MouseEvent | TouchEvent): XYPosition | null {
  if ('clientX' in event) return { x: event.clientX, y: event.clientY }
  const touch = event.changedTouches[0] ?? event.touches[0]
  return touch ? { x: touch.clientX, y: touch.clientY } : null
}

function parseCsvRow(row: string): string[] {
  const values: string[] = []
  let value = ''
  let quoted = false
  for (let index = 0; index < row.length; index += 1) {
    const character = row[index]
    if (character === '"') {
      if (quoted && row[index + 1] === '"') { value += '"'; index += 1 }
      else quoted = !quoted
    } else if (character === ',' && !quoted) {
      values.push(value.trim())
      value = ''
    } else value += character
  }
  values.push(value.trim())
  return values
}

function csvTemplate(file: File, source: string): NodeTemplate {
  if (file.size > 10 * 1024 * 1024) throw new Error('CSV must be smaller than 10 MB.')
  const lines = source.split(/\r?\n/).filter((line) => line.trim().length > 0)
  if (lines.length < 2) throw new Error('CSV needs a header and at least one data row.')
  const headers = parseCsvRow(lines[0]).filter(Boolean)
  if (headers.length < 2) throw new Error('CSV needs at least two named columns.')
  const preview = headers.slice(0, 4).join(' · ') + (headers.length > 4 ? ` · +${headers.length - 4}` : '')
  return {
    title: 'CSV dataset',
    kind: 'data',
    sub: 'Local dataset staging',
    fields: [
      ['file', file.name],
      ['rows', String(lines.length - 1)],
      ['columns', preview],
      ['authority', 'local only'],
    ],
  }
}

export function NodeBuilder({ strategy }: { strategy: Strategy }) {
  const initialNodes = useMemo(() => toFlowNodes(strategy), [strategy])
  const initialEdges = useMemo(() => toFlowEdges(strategy), [strategy])
  const [nodes, setNodes, onNodesChange] = useNodesState<StrategyFlowNode>(initialNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>(initialEdges)
  const [projection, setProjection] = useState<Projection>('graph')
  const [selectedId, setSelectedId] = useState<string | undefined>(strategy.graph.nodes[3]?.id ?? strategy.graph.nodes[0]?.id)
  const [libraryOpen, setLibraryOpen] = useState(true)
  const [inspectorOpen, setInspectorOpen] = useState(true)
  const [focusMode, setFocusMode] = useState(false)
  const [quickAddOpen, setQuickAddOpen] = useState(false)
  const [quickAddQuery, setQuickAddQuery] = useState('')
  const [quickAddContext, setQuickAddContext] = useState<QuickAddContext | null>(null)
  const [csvImport, setCsvImport] = useState<CsvImportState | null>(null)
  const [layoutDirty, setLayoutDirty] = useState(false)
  const [semanticDirty, setSemanticDirty] = useState(false)
  const [saved, setSaved] = useState(false)
  const [connectTarget, setConnectTarget] = useState('')
  const [flow, setFlow] = useState<ReactFlowInstance<StrategyFlowNode, Edge> | null>(null)
  const nextId = useRef(20)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    setNodes(toFlowNodes(strategy))
    setEdges(toFlowEdges(strategy))
  }, [strategy, setEdges, setNodes])

  useEffect(() => {
    const openPalette = (event: KeyboardEvent) => {
      if (!event.shiftKey || event.key.toLowerCase() !== 'a') return
      const target = event.target
      if (target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || target instanceof HTMLSelectElement) return
      event.preventDefault()
      setProjection('graph')
      setQuickAddOpen(true)
      setQuickAddQuery('')
      setQuickAddContext(null)
    }
    window.addEventListener('keydown', openPalette)
    return () => window.removeEventListener('keydown', openPalette)
  }, [])

  useEffect(() => {
    if (!flow || projection !== 'graph') return
    const timer = window.setTimeout(() => flow.fitView({ padding: focusMode ? .12 : .2, duration: 0 }), 40)
    return () => window.clearTimeout(timer)
  }, [flow, focusMode, inspectorOpen, libraryOpen, projection])

  const updateField = useCallback((id: string, label: string, value: string) => {
    setNodes((current) => current.map((item) => item.id === id ? { ...item, data: { ...item.data, node: { ...item.data.node, fields: item.data.node.fields?.map(([key, old]) => key === label ? [key, value] : [key, old]) } } } : item))
    setSemanticDirty(true); setSaved(false)
  }, [setNodes])

  const updateTitle = useCallback((id: string, value: string) => {
    setNodes((current) => current.map((item) => item.id === id ? { ...item, data: { ...item.data, node: { ...item.data.node, title: value } } } : item))
    setSemanticDirty(true); setSaved(false)
  }, [setNodes])

  const deleteNode = useCallback((id: string) => {
    setNodes((current) => current.filter((item) => item.id !== id))
    setEdges((current) => current.filter((edge) => edge.source !== id && edge.target !== id))
    setSelectedId((current) => current === id ? undefined : current)
    setSemanticDirty(true); setSaved(false)
  }, [setEdges, setNodes])

  const duplicateNode = useCallback((id: string) => {
    setNodes((current) => {
      const source = current.find((item) => item.id === id)
      if (!source) return current
      const next = `${source.id}-copy-${nextId.current++}`
      return [...current, { ...source, id: next, selected: false, position: { x: source.position.x + 34, y: source.position.y + 34 }, data: { node: { ...structuredClone(source.data.node), id: next, title: `${source.data.node.title} copy` } } }]
    })
    setSemanticDirty(true); setSaved(false)
  }, [setNodes])

  const renderNodes = useMemo(() => nodes.map((item) => ({ ...item, data: { ...item.data, onFieldChange: updateField, onTitleChange: updateTitle, onDuplicate: duplicateNode, onDelete: deleteNode } })), [deleteNode, duplicateNode, nodes, updateField, updateTitle])
  const selectedFlowNode = nodes.find((node) => node.id === selectedId)
  const selected = selectedFlowNode?.data.node

  const insertTemplate = useCallback((template: NodeTemplate, context: QuickAddContext | null) => {
    const id = `node-${nextId.current++}`
    const host = document.querySelector('.node-canvas')?.getBoundingClientRect()
    const position = context?.flowPosition ?? (flow && host ? flow.screenToFlowPosition({ x: host.left + host.width / 2, y: host.top + host.height / 2 }) : { x: 380, y: 180 })
    const node: GNode = { id, x: position.x, y: position.y, w: 190, title: template.title, kind: template.kind, sub: template.sub, fields: structuredClone(template.fields) }
    setNodes((current) => [...current, { id, type: 'strategyNode', position, data: { node }, style: { width: 190 }, selected: true }])
    if (context?.connection) {
      const connection = connectionForInsertedNode(context.connection, id)
      setEdges((current) => addEdge({ ...connection, type: 'smoothstep', className: 'strategy-flow-edge strategy-flow-edge--signal' }, current))
    }
    setSelectedId(id)
    setQuickAddOpen(false)
    setQuickAddContext(null)
    setSemanticDirty(true)
    setSaved(false)
    return id
  }, [flow, setEdges, setNodes])

  const addTemplate = useCallback((template: NodeTemplate) => insertTemplate(template, quickAddContext), [insertTemplate, quickAddContext])

  const closeQuickAdd = useCallback(() => {
    setQuickAddOpen(false)
    setQuickAddContext(null)
    setQuickAddQuery('')
  }, [])

  const onConnectEnd = useCallback((event: MouseEvent | TouchEvent, connectionState: FinalConnectionState) => {
    if (connectionState.toHandle || !connectionState.fromNode || !connectionState.fromHandle || !flow) return
    const screenPoint = pointerFromEvent(event)
    const host = document.querySelector('.node-canvas')?.getBoundingClientRect()
    if (!screenPoint || !host) return
    const paletteWidth = Math.min(390, Math.max(0, host.width - 28))
    const paletteHeight = Math.min(420, Math.max(0, host.height - 28))
    const relativeX = screenPoint.x - host.left
    const relativeY = screenPoint.y - host.top
    const canvasPosition = {
      x: Math.min(Math.max(14, relativeX), Math.max(14, host.width - paletteWidth - 14)),
      y: Math.min(Math.max(14, relativeY), Math.max(14, host.height - paletteHeight - 14)),
    }
    const source = nodes.find((node) => node.id === connectionState.fromNode?.id)
    setProjection('graph')
    setQuickAddContext({
      canvasPosition,
      flowPosition: flow.screenToFlowPosition(screenPoint),
      connection: {
        nodeId: connectionState.fromNode.id,
        nodeTitle: source?.data.node.title ?? connectionState.fromNode.id,
        handleId: connectionState.fromHandle.id ?? null,
        handleType: connectionState.fromHandle.type,
      },
    })
    setQuickAddQuery('')
    setQuickAddOpen(true)
  }, [flow, nodes])

  const handleCsvImport = useCallback(async (file: File | undefined) => {
    if (!file) return
    try {
      if (!file.name.toLowerCase().endsWith('.csv') && file.type !== 'text/csv') throw new Error('Choose a .csv file.')
      const template = csvTemplate(file, await file.text())
      insertTemplate(template, null)
      const rowCount = template.fields.find(([label]) => label === 'rows')?.[1] ?? '0'
      setCsvImport({ tone: 'ready', message: `${file.name} · ${Number(rowCount).toLocaleString('en-IN')} rows staged locally` })
    } catch (error) {
      setCsvImport({ tone: 'error', message: error instanceof Error ? error.message : 'CSV could not be read.' })
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }, [insertTemplate])

  const projectedStrategy = useMemo<Strategy>(() => ({ ...strategy, graph: { nodes: nodes.map((node) => ({ ...node.data.node, x: node.position.x, y: node.position.y, w: typeof node.measured?.width === 'number' ? node.measured.width : node.data.node.w })), edges: edges.map((edge) => ({ from: edge.source, to: edge.target, label: typeof edge.label === 'string' ? edge.label : undefined, kind: edge.className?.includes('--order') ? 'order' : edge.className?.includes('--signal') ? 'signal' : 'data' })) } }), [edges, nodes, strategy])

  const onConnect = useCallback((connection: Connection) => {
    setEdges((current) => addEdge({ ...connection, type: 'smoothstep', className: 'strategy-flow-edge strategy-flow-edge--signal' }, current))
    setSemanticDirty(true); setSaved(false)
  }, [setEdges])

  const updateLayout = useCallback((id: string, key: 'x' | 'y' | 'width', raw: string) => {
    const value = Number(raw)
    if (!Number.isFinite(value)) return
    setNodes((current) => current.map((item) => {
      if (item.id !== id) return item
      if (key === 'width') return { ...item, style: { ...item.style, width: Math.max(160, Math.min(440, value)) } }
      return { ...item, position: { ...item.position, [key]: value } }
    }))
    setLayoutDirty(true)
  }, [setNodes])

  const handleNodesChange = useCallback((changes: NodeChange<StrategyFlowNode>[]) => {
    if (changes.some((change) => change.type === 'remove')) { setSemanticDirty(true); setSaved(false) }
    if (changes.some((change) => change.type === 'position' || change.type === 'dimensions')) setLayoutDirty(true)
    onNodesChange(changes)
  }, [onNodesChange])

  const handleEdgesChange = useCallback((changes: EdgeChange<Edge>[]) => {
    if (changes.some((change) => change.type === 'remove')) { setSemanticDirty(true); setSaved(false) }
    onEdgesChange(changes)
  }, [onEdgesChange])

  const connectSelected = () => {
    if (!selectedId || !connectTarget || selectedId === connectTarget) return
    onConnect({ source: selectedId, target: connectTarget, sourceHandle: 'output', targetHandle: 'input-0' })
    setConnectTarget('')
  }

  return (
    <div className={cx('builder-shell', !libraryOpen && 'library-hidden', !inspectorOpen && 'inspector-hidden', focusMode && 'is-focus')}>
      {libraryOpen && !focusMode ? <Panel className="builder-library">
        <PanelHeader title="Node library" eyebrow="Shift+A anywhere" compact action={<IconButton label="Filter nodes"><Filter size={14} /></IconButton>} />
        <label className="input-shell"><Search size={14} /><input aria-label="Search nodes" placeholder="Search nodes" /></label>
        {nodeTemplates.map(({ group, items }) => <details open={group === 'Signals' || group === 'Risk'} key={group}><summary>{group}<ChevronDown size={13} /></summary>{items.map((item) => <button type="button" className="library-item" key={item.title} onClick={() => addTemplate(item)}><Plus size={12} />{item.title}<Grip size={12} /></button>)}</details>)}
      </Panel> : null}

      <Panel className="builder-main">
        <div className="builder-toolbar">
          <div className="builder-toolbar__left"><div className="builder-pane-controls"><IconButton label={libraryOpen ? 'Hide node library' : 'Show node library'} onClick={() => { setFocusMode(false); setLibraryOpen((value) => !value) }}>{libraryOpen ? <PanelLeftClose size={14} /> : <PanelLeftOpen size={14} />}</IconButton><IconButton label={inspectorOpen ? 'Hide inspector' : 'Show inspector'} onClick={() => { setFocusMode(false); setInspectorOpen((value) => !value) }}>{inspectorOpen ? <PanelRightClose size={14} /> : <PanelRightOpen size={14} />}</IconButton><IconButton label={focusMode ? 'Exit canvas focus' : 'Focus canvas'} className={focusMode ? 'is-active' : ''} onClick={() => setFocusMode((value) => !value)}><Focus size={14} /></IconButton></div><Segmented value={projection} onChange={setProjection} ariaLabel="Strategy projection" items={[{ value: 'graph', label: 'Graph' }, { value: 'form', label: 'Form' }, { value: 'tree', label: 'Tree' }, { value: 'code', label: 'Code' }]} /></div>
          <div className="builder-toolbar__right"><input ref={fileInputRef} hidden type="file" accept=".csv,text/csv" onChange={(event) => void handleCsvImport(event.target.files?.[0])} /><button type="button" className="builder-import-csv" onClick={() => fileInputRef.current?.click()}><FileUp size={13} /> Import CSV</button><button type="button" className="builder-add-shortcut" onClick={() => { setProjection('graph'); setQuickAddContext(null); setQuickAddQuery(''); setQuickAddOpen(true) }}><Plus size={13} /> Add node <kbd>⇧ A</kbd></button>{(layoutDirty || semanticDirty) ? <span className="builder-dirty">{semanticDirty ? 'Draft edited' : 'Layout edited'}</span> : <span className="builder-clean">No unsaved edits</span>}<IconButton label="Reset graph view" onClick={() => flow?.fitView({ padding: .18, duration: 180 })}><RotateCcw size={14} /></IconButton></div>
        </div>
        <div className={cx('node-canvas', `node-canvas--${projection}`)}>
          {projection === 'graph' ? <ReactFlow<StrategyFlowNode, Edge> nodes={renderNodes} edges={edges} nodeTypes={nodeTypes} onInit={setFlow} onNodesChange={handleNodesChange} onEdgesChange={handleEdgesChange} onConnect={onConnect} onConnectEnd={onConnectEnd} onReconnect={(oldEdge, connection) => { setEdges((current) => reconnectEdge(oldEdge, connection, current)); setSemanticDirty(true); setSaved(false) }} onNodeClick={(_, node) => setSelectedId(node.id)} onNodeDragStop={() => setLayoutDirty(true)} onNodeDoubleClick={(_, node) => setSelectedId(node.id)} onPaneClick={() => setSelectedId(undefined)} fitView fitViewOptions={{ padding: .2 }} minZoom={.28} maxZoom={1.7} connectionRadius={32} snapToGrid={false} deleteKeyCode={['Backspace', 'Delete']} isValidConnection={(connection) => connection.source !== connection.target} elevateNodesOnSelect selectionOnDrag panOnScroll zoomOnPinch zoomOnDoubleClick={false} proOptions={{ hideAttribution: true }}>
            <Background variant={BackgroundVariant.Dots} gap={22} size={1} className="strategy-flow-background" />
            <Controls position="bottom-left" showInteractive={false} className="strategy-flow-controls" />
          </ReactFlow> : null}
          {projection === 'form' ? <FormProjection strategy={projectedStrategy} /> : null}
          {projection === 'tree' ? <TreeProjection strategy={projectedStrategy} /> : null}
          {projection === 'code' ? <CodeProjection strategy={projectedStrategy} /> : null}
          {quickAddOpen ? <QuickAdd query={quickAddQuery} context={quickAddContext} onQuery={setQuickAddQuery} onAdd={addTemplate} onClose={closeQuickAdd} /> : null}
        </div>
        <div className="builder-status"><span><ShieldCheck size={12} />{nodes.length} nodes · {edges.length} edges</span><span>{semanticDirty ? 'Unsaved draft semantics' : 'Typed graph valid'}</span>{csvImport ? <span className={cx('builder-file-state', csvImport.tone === 'error' && 'is-error')} role="status" title={csvImport.message}>{csvImport.message}</span> : <span>{layoutDirty ? 'Layout changed · identity unaffected' : 'Layout stored outside identity'}</span>}</div>
      </Panel>

      {inspectorOpen && !focusMode ? <Panel className="builder-inspector">
        <PanelHeader title="Inspector" eyebrow={selected?.kind ?? 'No selection'} compact action={<SlidersHorizontal size={15} />} />
        {selected && selectedFlowNode ? <><div className="inspector-title"><Badge tone={kindTone[selected.kind]}>{selected.kind}</Badge><label className="field"><span>Node title</span><input value={selected.title} onChange={(event) => updateTitle(selected.id, event.target.value)} /></label><p>{selected.sub}</p></div><div className="inspector-section"><span className="label">Parameters</span>{selected.fields?.map(([label, value]) => <label className="field" key={label}><span>{label}</span><input value={value} onChange={(event) => updateField(selected.id, label, event.target.value)} /></label>)}</div><div className="inspector-section"><span className="label">Canvas layout</span><div className="inspector-layout-grid"><label className="field"><span>X</span><input type="number" value={Math.round(selectedFlowNode.position.x)} onChange={(event) => updateLayout(selected.id, 'x', event.target.value)} /></label><label className="field"><span>Y</span><input type="number" value={Math.round(selectedFlowNode.position.y)} onChange={(event) => updateLayout(selected.id, 'y', event.target.value)} /></label><label className="field"><span>Width</span><input type="number" min="160" max="440" value={Math.round(Number(selectedFlowNode.measured?.width ?? selectedFlowNode.style?.width ?? 190))} onChange={(event) => updateLayout(selected.id, 'width', event.target.value)} /></label></div><small className="inspector-help">Keyboard alternative to dragging and resizing. Layout stays outside strategy identity.</small></div><div className="inspector-section"><span className="label">Connect output</span><div className="inspector-connect"><select aria-label="Connect selected node output" value={connectTarget} onChange={(event) => setConnectTarget(event.target.value)}><option value="">Choose target node</option>{nodes.filter((item) => item.id !== selected.id).map((item) => <option value={item.id} key={item.id}>{item.data.node.title}</option>)}</select><Button disabled={!connectTarget} onClick={connectSelected}>Connect</Button></div><small className="inspector-help">Keyboard alternative to dragging a connector.</small></div><div className="inspector-section"><span className="label">Port contract</span><KeyValue label="Input structure" value={selected.kind === 'data' ? 'Completed bar series' : 'Typed signal'} /><KeyValue label="Output" value={selected.kind === 'risk' ? 'Protected intent' : 'Deterministic value'} /><KeyValue label="Clock" value="NSE session · IST" /></div><div className="inspector-section"><span className="label">Component lineage</span><KeyValue label="Component" value={`core/${selected.id}`} mono /><KeyValue label="Resolved version" value="2.4.1" mono /><KeyValue label="Authored node" value={selected.id} mono /></div><div className="inspector-section"><span className="label">Authority</span><KeyValue label="Projection" value={strategy.draftId} mono /><KeyValue label="May affect" value="New research runs" /><KeyValue label="May not affect" value="Existing paper deployment" /></div><div className="inspector-section"><span className="label">Validation</span><div className="validation-line"><CheckCircle2 size={13} /><span>Inputs resolve</span></div><div className="validation-line"><CheckCircle2 size={13} /><span>Completed-bar causal</span></div><div className="validation-line"><CheckCircle2 size={13} /><span>Parameter bounds valid</span></div></div><Button variant="primary" onClick={() => { setSemanticDirty(false); setSaved(true) }}><Code2 size={14} /> Create draft revision</Button>{saved ? <p className="builder-save-result">Draft revision staged locally. No deployment changed.</p> : null}</> : <p className="muted-copy">Select a node to edit its parameters and inspect its contract.</p>}
      </Panel> : null}
    </div>
  )
}
