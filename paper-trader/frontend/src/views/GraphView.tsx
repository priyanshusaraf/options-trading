import { useEffect, useId, useMemo, useState } from 'react'
import { getIrGraph, type IrGraphView, type IrViewNode } from '../lib/api'
import { Badge } from '../components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import { Skeleton } from '../components/ui/skeleton'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '../components/ui/table'
import { cn } from '../lib/utils'

const GRAPH_IDENTIFIER = 'strategy.expanding_z_impulse'
const NODE_WIDTH = 288
const NODE_HEIGHT = 340
const X_GAP = 88
const Y_GAP = 40
const MARGIN = 24

interface Point {
  x: number
  y: number
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

function NodeCard({ node, point }: { node: IrViewNode; point: Point }) {
  const params = Object.entries(node.params)
  const impure = node.purity !== 'pure'
  const titleId = useId()
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

export function GraphCanvas({ graph }: { graph: IrGraphView }) {
  const points = useMemo(
    () => new Map(graph.nodes.map((node) => [node.instance_id, nodePosition(node)])),
    [graph.nodes],
  )
  const dimensions = useMemo(() => {
    const positioned = [...points.values()]
    return {
      width: Math.max(720, ...positioned.map(({ x }) => x + NODE_WIDTH + MARGIN)),
      height: Math.max(420, ...positioned.map(({ y }) => y + NODE_HEIGHT + MARGIN)),
    }
  }, [points])

  return (
    <section aria-labelledby="strategy-graph-title" className="space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="stat-label">Component IR · read-only</p>
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
            <NodeCard key={node.instance_id} node={node} point={points.get(node.instance_id)!} />
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

export function GraphViewState({ graph, error }: {
  graph: IrGraphView | null
  error: string | null
}) {
  if (error) {
    return (
      <Card role="alert" className="border-destructive/60">
        <CardHeader><CardTitle className="text-base">Strategy graph unavailable</CardTitle></CardHeader>
        <CardContent className="text-sm text-muted">{error}</CardContent>
      </Card>
    )
  }
  if (!graph) {
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
  return <GraphCanvas graph={graph} />
}

export default function GraphView() {
  const [graph, setGraph] = useState<IrGraphView | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let current = true
    getIrGraph(GRAPH_IDENTIFIER)
      .then((view) => { if (current) setGraph(view) })
      .catch((reason: unknown) => {
        if (current) setError(reason instanceof Error ? reason.message : 'The graph could not be loaded')
      })
    return () => { current = false }
  }, [])

  return <GraphViewState graph={graph} error={error} />
}
