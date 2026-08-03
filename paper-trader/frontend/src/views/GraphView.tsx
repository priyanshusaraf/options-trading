import {
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type PointerEvent,
} from 'react'
import {
  EditorApiError,
  getIrEditorDocument,
  getIrGraphLayout,
  postIrEditorOperations,
  postIrPresentationOperations,
  putIrGraphLayout,
  type IrGraphLayout,
  type IrGraphView,
  type IrEditorOperation,
  type IrPresentationOperation,
  type IrViewNode,
} from '../lib/api'
import {
  beginLayoutEditor,
  failLayoutSave,
  moveLayoutNode,
  persistLayoutEditor,
  reloadLayoutEditor,
  startLayoutSave,
  type LayoutEditorPhase,
  type LayoutEditorState,
} from './graphLayoutState'
import { GraphEditControls } from './GraphEditControls'
import { GraphGroupControls } from './GraphGroupControls'
import { GraphStructureControls } from './GraphStructureControls'
import ResearchEvidencePanel from './ResearchEvidencePanel'
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
  startSemanticCommand,
  type GraphEditorState,
  type StartedEditorRequest,
} from './graphEditorState'
import { Badge } from '../components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import { Skeleton } from '../components/ui/skeleton'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '../components/ui/table'
import { cn } from '../lib/utils'

const GRAPH_IDENTIFIER = 'strategy.expanding_z_impulse'
const PROJECT_ID = 'project.repository_catalogue'
const NODE_WIDTH = 288
const NODE_HEIGHT = 340
const X_GAP = 88
const Y_GAP = 40
const MARGIN = 24

interface Point {
  x: number
  y: number
}

export function movePointWithKey(point: Point, key: string, precise: boolean): Point | null {
  const step = precise ? 1 : 10
  const delta: Record<string, Point> = {
    ArrowLeft: { x: -step, y: 0 },
    ArrowRight: { x: step, y: 0 },
    ArrowUp: { x: 0, y: -step },
    ArrowDown: { x: 0, y: step },
  }
  const movement = delta[key]
  if (!movement) return null
  return {
    x: Math.max(0, point.x + movement.x),
    y: Math.max(0, point.y + movement.y),
  }
}

export function movePointFromPointer(
  point: Point,
  pointerStart: Point,
  pointerNow: Point,
): Point {
  return {
    x: Math.max(0, point.x + pointerNow.x - pointerStart.x),
    y: Math.max(0, point.y + pointerNow.y - pointerStart.y),
  }
}

function nodePosition(node: IrViewNode): Point {
  if (node.placed) return { x: node.placed[0], y: node.placed[1] }
  return {
    x: MARGIN + node.layer * (NODE_WIDTH + X_GAP),
    y: MARGIN + node.row * (NODE_HEIGHT + Y_GAP),
  }
}

function authoredPath(node: IrViewNode): string {
  return node.container ? `${node.container}/${node.label}` : node.label
}

function paramValue(value: unknown): string {
  const encoded = JSON.stringify(value)
  return encoded === undefined ? String(value) : encoded
}

function plural(value: number, singular: string, many = `${singular}s`): string {
  return `${value} ${value === 1 ? singular : many}`
}

function purityLabel(purity: IrViewNode['purity']): string {
  return purity === 'pure' ? 'Pure' : `Impure · ${purity.replace('_', ' ')}`
}

function NodeCard({ node, point, onMove }: {
  node: IrViewNode
  point: Point
  onMove?: (instanceId: string, point: Point) => void
}) {
  const params = Object.entries(node.params)
  const impure = node.purity !== 'pure'
  const titleId = useId()
  const drag = useRef<{ point: Point; pointer: Point } | null>(null)

  const moveFromKey = (event: KeyboardEvent<HTMLButtonElement>) => {
    const moved = movePointWithKey(point, event.key, event.shiftKey)
    if (!moved || !onMove) return
    event.preventDefault()
    onMove(node.instance_id, moved)
  }

  const startDrag = (event: PointerEvent<HTMLButtonElement>) => {
    if (!onMove) return
    event.currentTarget.setPointerCapture(event.pointerId)
    drag.current = {
      point,
      pointer: { x: event.clientX, y: event.clientY },
    }
  }

  const continueDrag = (event: PointerEvent<HTMLButtonElement>) => {
    if (!onMove || !drag.current || !event.currentTarget.hasPointerCapture(event.pointerId)) return
    onMove(node.instance_id, movePointFromPointer(
      drag.current.point,
      drag.current.pointer,
      { x: event.clientX, y: event.clientY },
    ))
  }

  const stopDrag = (event: PointerEvent<HTMLButtonElement>) => {
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId)
    }
    drag.current = null
  }

  return (
    <article
      data-node-path={authoredPath(node)}
      className="absolute"
      style={{ left: point.x, top: point.y, width: NODE_WIDTH, minHeight: NODE_HEIGHT }}
      aria-labelledby={titleId}
    >
      <Card className={cn(
        'min-h-[340px] overflow-hidden border-edge bg-panel/95 shadow-lg',
        node.derived && 'border-sky-500/70 bg-sky-950/20',
        impure && 'border-amber-500/80',
      )}>
        <CardHeader className="space-y-3 p-4 pb-3">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <CardTitle id={titleId} className="break-all text-sm leading-5">
              {authoredPath(node)}
            </CardTitle>
            <p className="mt-1 break-all text-[11px] text-muted">{node.definition}</p>
          </div>
          <div className="flex shrink-0 flex-col items-end gap-1">
            {!node.derived && onMove && (
              <button
                type="button"
                aria-label={`Move ${authoredPath(node)}`}
                title="Drag, or use arrow keys. Hold Shift for 1px steps."
                className="touch-none cursor-move rounded border border-edge px-2 py-1 text-[10px] uppercase tracking-wide text-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400"
                onKeyDown={moveFromKey}
                onPointerDown={startDrag}
                onPointerMove={continueDrag}
                onPointerUp={stopDrag}
                onPointerCancel={stopDrag}
              >
                Move
              </button>
            )}
            {node.derived && (
              <Badge variant="chip" className="bg-sky-500/20 text-sky-300">Derived</Badge>
            )}
            <Badge
              variant="chip"
              className={impure
                ? 'bg-amber-500/20 text-amber-300'
                : 'bg-emerald-500/15 text-emerald-300'}
            >
              {purityLabel(node.purity)}
            </Badge>
          </div>
        </div>
        <div className="flex flex-wrap gap-3 text-[11px] text-muted">
          <span><span className="text-zinc-400">Warmup</span> {node.warmup} bars</span>
          <span><span className="text-zinc-400">Layer</span> {node.layer}</span>
        </div>
        </CardHeader>
        <CardContent className="space-y-3 p-4 pt-0">
        <div>
          <div className="stat-label mb-1">Bound parameters</div>
          {params.length === 0 ? (
            <p className="text-xs text-muted">None</p>
          ) : (
            <dl className="space-y-1 text-xs">
              {params.map(([key, value]) => (
                <div key={key} className="grid grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)] gap-2">
                  <dt className="break-all text-muted">{key}</dt>
                  <dd className="break-all text-right text-zinc-300">{paramValue(value)}</dd>
                </div>
              ))}
            </dl>
          )}
        </div>
        <div>
          <div className="stat-label mb-1">Cache identity</div>
          <code className="block break-all text-[10px] leading-4 text-zinc-400">{node.cache_id}</code>
        </div>
        </CardContent>
      </Card>
    </article>
  )
}

export function GraphCanvas({ graph, layout, onMove }: {
  graph: IrGraphView
  layout?: IrGraphLayout
  onMove?: (instanceId: string, point: Point) => void
}) {
  const points = useMemo(
    () => {
      const layoutMatches = layout?.graph_identifier === graph.identifier
        && layout.graph_version === graph.version
      const overrides = new Map(
        layoutMatches
          ? layout.positions.map((position) => [position.instance_id, position] as const)
          : [],
      )
      return new Map(graph.nodes.map((node) => {
        const override = node.derived ? undefined : overrides.get(node.instance_id)
        return [
          node.instance_id,
          override ? { x: override.x, y: override.y } : nodePosition(node),
        ]
      }))
    },
    [graph, layout],
  )
  const dimensions = useMemo(() => {
    const positioned = [...points.values()]
    const groups = layout?.groups ?? []
    return {
      width: Math.max(
        720,
        ...positioned.map(({ x }) => x + NODE_WIDTH + MARGIN),
        ...groups.map((group) => group.frame.x + group.frame.width + MARGIN),
      ),
      height: Math.max(
        420,
        ...positioned.map(({ y }) => y + NODE_HEIGHT + MARGIN),
        ...groups.map((group) => group.frame.y + group.frame.height + MARGIN),
      ),
    }
  }, [points, layout?.groups])

  return (
    <section aria-labelledby="strategy-graph-title" className="space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="stat-label">Component IR · layout editor</p>
          <h1 id="strategy-graph-title" className="mt-1 text-xl font-semibold text-zinc-100">
            {graph.display_name}
          </h1>
          <p className="mt-1 text-xs text-muted">{graph.identifier} v{graph.version}</p>
        </div>
        <div className="flex flex-wrap gap-2 text-xs">
          <Badge variant="outline">{plural(graph.nodes.length, 'node')}</Badge>
          <Badge variant="outline">{plural(graph.edges.length, 'edge')}</Badge>
          <Badge variant="outline">{plural(graph.layers, 'layer')}</Badge>
          <Badge variant="outline">{graph.warmup} bars warmup</Badge>
        </div>
      </header>

      <div className="grid gap-2 text-xs text-muted sm:grid-cols-2">
        <p><span className="text-zinc-400">Inputs:</span> {graph.inputs.join(', ') || 'none'}</p>
        <p><span className="text-zinc-400">Outputs:</span> {graph.outputs.join(', ') || 'none'}</p>
      </div>

      <div className="overflow-x-auto rounded-lg border border-edge bg-bg/50">
        <div
          className="relative"
          style={{ width: dimensions.width, height: dimensions.height }}
          data-testid="graph-canvas"
        >
          {(layout?.groups ?? []).map((group) => (
            <div
              key={group.identifier}
              className="pointer-events-none absolute rounded-lg border border-dashed border-violet-400/70 bg-violet-500/5"
              style={{
                left: group.frame.x,
                top: group.frame.y,
                width: group.frame.width,
                height: group.collapsed ? 36 : group.frame.height,
              }}
              role="group"
              aria-label={`${group.display_name} visual group${group.collapsed ? ', collapsed' : ''}`}
            >
              <span className="m-2 inline-block rounded bg-bg/90 px-2 py-1 text-[11px] text-violet-200">
                {group.display_name} · {group.members.length} members
              </span>
            </div>
          ))}
          <svg
            aria-hidden="true"
            focusable="false"
            className="pointer-events-none absolute inset-0"
            width={dimensions.width}
            height={dimensions.height}
            viewBox={`0 0 ${dimensions.width} ${dimensions.height}`}
          >
            {graph.edges.map((edge, index) => {
              const source = points.get(edge.source)
              const target = points.get(edge.target)
              if (!source || !target) return null
              const x1 = source.x + NODE_WIDTH
              const y1 = source.y + NODE_HEIGHT / 2
              const x2 = target.x
              const y2 = target.y + NODE_HEIGHT / 2
              const bend = Math.max(44, Math.abs(x2 - x1) / 2)
              return (
                <path
                  key={`${edge.source}:${edge.source_socket}:${edge.target}:${edge.target_socket}:${index}`}
                  d={`M ${x1} ${y1} C ${x1 + bend} ${y1}, ${x2 - bend} ${y2}, ${x2} ${y2}`}
                  fill="none"
                  stroke={edge.derived ? '#38bdf8' : '#71717a'}
                  strokeWidth="2"
                  strokeDasharray={edge.derived ? '7 5' : undefined}
                  vectorEffect="non-scaling-stroke"
                />
              )
            })}
          </svg>
          {graph.nodes.map((node) => (
            <NodeCard
              key={node.instance_id}
              node={node}
              point={points.get(node.instance_id)!}
              onMove={onMove}
            />
          ))}
        </div>
      </div>

      <Card>
        <CardHeader className="p-4 pb-2">
          <CardTitle className="text-sm">Connections</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <caption className="sr-only">
              {plural(graph.edges.length, 'connection')} in {graph.display_name}
            </caption>
            <TableHeader>
              <TableRow>
                <TableHead scope="col">Source socket</TableHead>
                <TableHead scope="col">Target socket</TableHead>
                <TableHead scope="col">Kind</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {graph.edges.length === 0 && (
                <TableRow>
                  <TableCell colSpan={3} className="text-center text-xs text-muted">
                    No connections
                  </TableCell>
                </TableRow>
              )}
              {graph.edges.map((edge, index) => (
                <TableRow key={`${edge.source}:${edge.source_socket}:${edge.target}:${edge.target_socket}:${index}`}>
                  <TableCell className="break-all font-mono text-xs">
                    {edge.source}.{edge.source_socket}
                  </TableCell>
                  <TableCell className="break-all font-mono text-xs">
                    {edge.target}.{edge.target_socket}
                  </TableCell>
                  <TableCell>
                    {edge.derived
                      ? <Badge variant="chip" className="bg-sky-500/20 text-sky-300">Derived connection</Badge>
                      : <span className="text-xs text-muted">Authored</span>}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </section>
  )
}

export function GraphViewState({
  graph,
  layout,
  graphEditor,
  phase = 'clean',
  message = null,
  error,
  onMove,
  onSave,
  onReload,
  onDisplayName,
  onSetOverride,
  onClearOverride,
  onUndo,
  onRedo,
  onEditorReload,
  onSemantic,
  onPresentation,
}: {
  graph: IrGraphView | null
  layout?: IrGraphLayout | null
  graphEditor?: GraphEditorState | null
  phase?: LayoutEditorPhase
  message?: string | null
  error: string | null
  onMove?: (instanceId: string, point: Point) => void
  onSave?: () => void
  onReload?: () => void
  onDisplayName?: (displayName: string) => void
  onSetOverride?: (instanceId: string, parameter: string, source: string) => void
  onClearOverride?: (instanceId: string, parameter: string) => void
  onUndo?: () => void
  onRedo?: () => void
  onEditorReload?: () => void
  onSemantic?: (operations: readonly IrEditorOperation[]) => void
  onPresentation?: (operations: readonly IrPresentationOperation[]) => void
}) {
  if (error) {
    return (
      <Card role="alert" className="border-destructive/60">
        <CardHeader><CardTitle className="text-base">Strategy graph unavailable</CardTitle></CardHeader>
        <CardContent className="text-sm text-muted">{error}</CardContent>
      </Card>
    )
  }
  if (!graph || layout === null) {
    return (
      <section aria-label="Loading strategy graph" aria-live="polite" className="space-y-3">
        <Skeleton className="h-7 w-72" />
        <Skeleton className="h-[420px] w-full" />
      </section>
    )
  }
  if (graph.nodes.length === 0) {
    return <p role="status" className="card p-4 text-sm text-muted">This strategy graph has no nodes.</p>
  }
  const buttonClass = 'rounded border border-edge px-3 py-1.5 text-xs font-medium text-zinc-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400'
  return (
    <>
      {graphEditor
        && onDisplayName
        && onSetOverride
        && onClearOverride
        && onUndo
        && onRedo
        && onEditorReload
        && (
          <GraphEditControls
            state={graphEditor}
            onDisplayName={onDisplayName}
            onSetOverride={onSetOverride}
            onClearOverride={onClearOverride}
            onUndo={onUndo}
            onRedo={onRedo}
            onReload={onEditorReload}
          />
        )}
      {graphEditor?.accepted && onSemantic && onPresentation && (
        <>
          <GraphStructureControls
            document={graphEditor.accepted}
            disabled={Boolean(graphEditor.pending) || ['dirty', 'saving', 'conflict', 'error'].includes(phase)}
            onSemantic={onSemantic}
          />
          <GraphGroupControls
            document={graphEditor.accepted}
            disabled={Boolean(graphEditor.pending) || ['dirty', 'saving', 'conflict', 'error'].includes(phase)}
            onPresentation={onPresentation}
          />
        </>
      )}
      {phase === 'dirty' && (
        <div className="mb-3 flex items-center justify-between gap-3" role="status">
          <span className="text-xs font-medium text-amber-300">Unsaved layout</span>
          {onSave && <button type="button" className={buttonClass} onClick={onSave}>Save layout</button>}
        </div>
      )}
      {phase === 'saving' && (
        <p role="status" aria-live="polite" className="mb-3 text-xs text-muted">Saving layout…</p>
      )}
      {phase === 'saved' && (
        <p role="status" aria-live="polite" className="mb-3 text-xs text-emerald-300">Layout saved</p>
      )}
      {(phase === 'conflict' || phase === 'error') && (
        <div role="alert" className="mb-3 rounded border border-amber-500/60 p-3 text-xs">
          <p className="font-medium text-amber-200">
            {phase === 'conflict'
              ? 'Layout changed elsewhere. Local positions are retained.'
              : `${message ?? 'Layout request failed'}. Local positions are retained.`}
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            {onSave && (
              <button type="button" className={buttonClass} onClick={onSave}>
                {phase === 'conflict' ? 'Retry against latest' : 'Retry save'}
              </button>
            )}
            {onReload && (
              <button type="button" className={buttonClass} onClick={onReload}>Reload server</button>
            )}
          </div>
        </div>
      )}
      <GraphCanvas
        graph={graph}
        layout={layout ?? undefined}
        onMove={phase === 'saving' ? undefined : onMove}
      />
    </>
  )
}

export default function GraphView({ researchEnabled = false }: { researchEnabled?: boolean }) {
  const [graphEditor, setGraphEditor] = useState<GraphEditorState | null>(null)
  const [layoutEditor, setLayoutEditor] = useState<LayoutEditorState | null>(null)
  const [error, setError] = useState<string | null>(null)
  const latestRequest = useRef(0)

  useEffect(() => {
    let current = true
    getIrEditorDocument(PROJECT_ID, GRAPH_IDENTIFIER)
      .then((document) => {
        if (!current) return
        setGraphEditor(beginGraphEditor(document))
        setLayoutEditor(beginLayoutEditor(document.layout))
      })
      .catch((reason: unknown) => {
        if (current) setError(reason instanceof Error ? reason.message : 'The graph could not be loaded')
      })
    return () => { current = false }
  }, [])

  const moveNode = (instanceId: string, point: Point) => {
    setLayoutEditor((current) => current ? moveLayoutNode(current, instanceId, point) : current)
  }

  const saveLayout = async () => {
    if (!layoutEditor || layoutEditor.phase === 'saving') return
    const draft = layoutEditor
    setLayoutEditor(startLayoutSave(draft))
    const result = await persistLayoutEditor(draft, putIrGraphLayout)
    setLayoutEditor((current) => (
      current?.layout.graph_version === result.layout.graph_version ? result : current
    ))
  }

  const reloadLayout = async () => {
    const graph = graphEditor?.accepted?.view
    if (!graph || !layoutEditor) return
    const current = layoutEditor
    try {
      const reloaded = await getIrGraphLayout(graph.identifier, graph.version)
      setLayoutEditor((latest) => (
        latest && latest.layout.graph_version !== reloaded.graph_version
          ? latest
          : reloadLayoutEditor(latest ?? current, reloaded)
      ))
    } catch (reason: unknown) {
      setLayoutEditor((latest) => failLayoutSave(latest ?? current, reason))
    }
  }

  const runPublication = (started: StartedEditorRequest | null) => {
    if (!started) return
    latestRequest.current = started.requestId
    setGraphEditor(started.state)
    const request = started.request.kind === 'semantic'
      ? postIrEditorOperations(
          PROJECT_ID,
          GRAPH_IDENTIFIER,
          started.request.baseRevision,
          started.request.basePresentationRevision,
          started.request.semanticOperations,
          started.request.presentationOperations,
        )
      : postIrPresentationOperations(
          PROJECT_ID,
          GRAPH_IDENTIFIER,
          started.request.baseRevision,
          started.request.basePresentationRevision,
          started.request.presentationOperations,
        )
    request.then((document) => {
      if (latestRequest.current !== started.requestId) return
      setGraphEditor((current) => current
        ? acceptPublication(current, started.requestId, document)
        : current)
      setLayoutEditor(beginLayoutEditor(document.layout))
    }).catch((reason: unknown) => {
      if (latestRequest.current !== started.requestId) return
      const failure = reason instanceof EditorApiError
        ? reason
        : new EditorApiError(
            'network',
            reason instanceof Error ? reason.message : 'Editor request failed',
            null,
            reason,
          )
      setGraphEditor((current) => current
        ? failEditorRequest(current, started.requestId, failure)
        : current)
    })
  }

  const publishDraft = (drafted: GraphEditorState) => {
    setGraphEditor(drafted)
    runPublication(startPublish(drafted, layoutEditor?.phase))
  }

  const updateDisplayName = (displayName: string) => {
    if (graphEditor) publishDraft(draftDisplayName(graphEditor, displayName))
  }

  const setOverride = (instanceId: string, parameter: string, source: string) => {
    if (graphEditor) publishDraft(
      draftSetOverrideJson(graphEditor, instanceId, parameter, source),
    )
  }

  const clearOverride = (instanceId: string, parameter: string) => {
    if (graphEditor) publishDraft(
      draftClearOverride(graphEditor, instanceId, parameter),
    )
  }

  const undo = () => {
    if (graphEditor) runPublication(startUndo(graphEditor, layoutEditor?.phase))
  }

  const redo = () => {
    if (graphEditor) runPublication(startRedo(graphEditor, layoutEditor?.phase))
  }

  const submitSemantic = (operations: readonly IrEditorOperation[]) => {
    if (graphEditor) runPublication(startSemanticCommand(
      graphEditor, operations, [], layoutEditor?.phase,
    ))
  }

  const submitPresentation = (operations: readonly IrPresentationOperation[]) => {
    if (graphEditor) runPublication(startPresentationCommand(
      graphEditor, operations, layoutEditor?.phase,
    ))
  }

  const reloadEditor = () => {
    if (!graphEditor) return
    const started = startReload(graphEditor)
    latestRequest.current = started.requestId
    setGraphEditor(started.state)
    getIrEditorDocument(PROJECT_ID, GRAPH_IDENTIFIER)
      .then((document) => {
        if (latestRequest.current !== started.requestId) return
        setGraphEditor((current) => current
          ? acceptReload(current, started.requestId, document)
          : current)
        setLayoutEditor((current) => reloadLayoutEditor(
          current ?? beginLayoutEditor(document.layout), document.layout,
        ))
      })
      .catch((reason: unknown) => {
        if (latestRequest.current !== started.requestId) return
        const failure = reason instanceof EditorApiError
          ? reason
          : new EditorApiError(
              'network',
              reason instanceof Error ? reason.message : 'Editor reload failed',
              null,
              reason,
            )
        setGraphEditor((current) => current
          ? failEditorRequest(current, started.requestId, failure)
          : current)
      })
  }

  const graph = graphEditor?.accepted?.view ?? null

  return (
    <>
      {researchEnabled && <ResearchEvidencePanel
        projectId={PROJECT_ID} graphIdentifier={GRAPH_IDENTIFIER}
      />}
      <GraphViewState
        graph={graph}
        layout={layoutEditor?.layout ?? null}
        graphEditor={graphEditor}
        phase={layoutEditor?.phase}
        message={layoutEditor?.message}
        error={error}
        onMove={moveNode}
        onSave={saveLayout}
        onReload={reloadLayout}
        onDisplayName={updateDisplayName}
        onSetOverride={setOverride}
        onClearOverride={clearOverride}
        onUndo={undo}
        onRedo={redo}
        onEditorReload={reloadEditor}
        onSemantic={submitSemantic}
        onPresentation={submitPresentation}
      />
    </>
  )
}
