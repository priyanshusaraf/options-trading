import { useMemo, useState } from 'react'
import { Minus, Plus, RotateCcw } from 'lucide-react'

type EquityPoint = Readonly<{ time: number; value: number }>
type DrawdownPoint = Readonly<{ time: number; value: number; absolute: number }>

type Domain = { minTime: number; maxTime: number; min: number; max: number }
function domain(points: readonly EquityPoint[]): Domain {
  const values = points.map((point) => point.value)
  return { minTime: points[0]?.time ?? 0, maxTime: points.at(-1)?.time ?? 0,
    min: values.length ? Math.min(...values) : 0, max: values.length ? Math.max(...values) : 0 }
}
function path(points: readonly EquityPoint[], width: number, height: number, shared = domain(points)) {
  if (!points.length) return ''
  const x = (time: number) => shared.maxTime === shared.minTime ? 0 : ((time - shared.minTime) / (shared.maxTime - shared.minTime)) * width
  const y = (value: number) => shared.max === shared.min ? height / 2 : height - ((value - shared.min) / (shared.max - shared.min)) * height
  return points.map((point, index) => `${index ? 'L' : 'M'}${x(point.time).toFixed(2)},${y(point.value).toFixed(2)}`).join(' ')
}

export function ResearchSeriesChart({ equity, drawdown, events = [], comparison }: {
  equity: readonly EquityPoint[]; drawdown: readonly DrawdownPoint[]; events?: readonly Readonly<Record<string, unknown>>[]
  comparison?: Readonly<{ label: string; equity: readonly EquityPoint[]; drawdown: readonly DrawdownPoint[] }>
}) {
  const [zoom, setZoom] = useState(1)
  const [tableOffset, setTableOffset] = useState(0)
  const visible = useMemo(() => { const count = Math.max(2, Math.ceil(equity.length / zoom)); return equity.slice(-count) }, [equity, zoom])
  const visibleDrawdown = useMemo(() => { const from = visible[0]?.time ?? 0; return drawdown.filter((point) => point.time >= from) }, [drawdown, visible])
  const equityDomain = useMemo(() => domain(comparison ? [...visible, ...comparison.equity].sort((a, b) => a.time - b.time) : visible), [comparison, visible])
  const drawdownDomain = useMemo(() => domain(comparison ? [...visibleDrawdown, ...comparison.drawdown].sort((a, b) => a.time - b.time) : visibleDrawdown), [comparison, visibleDrawdown])
  const summary = visible.length ? `Net equity from INR ${visible[0].value.toLocaleString('en-IN')} to INR ${visible.at(-1)!.value.toLocaleString('en-IN')}. Worst visible close-to-close drawdown ${Math.max(...visibleDrawdown.map((point) => point.value), 0).toFixed(2)} percent.` : 'No persisted series points are available.'
  const tablePoints = visible.slice(tableOffset, tableOffset + 100)
  return <section className="series-chart" aria-labelledby="performance-chart-title">
    <header><div><h3 id="performance-chart-title">Net equity and close-to-close drawdown</h3><p>{summary}</p></div><div className="chart-controls" aria-label="Chart range controls">
      <button aria-label="Zoom in chart" onClick={() => { setTableOffset(0); setZoom((value) => Math.min(8, value * 2)) }}><Plus aria-hidden="true" /></button>
      <button aria-label="Zoom out chart" onClick={() => { setTableOffset(0); setZoom((value) => Math.max(1, value / 2)) }}><Minus aria-hidden="true" /></button>
      <button onClick={() => { setTableOffset(0); setZoom(1) }}><RotateCcw aria-hidden="true" />Reset</button></div></header>
    {visible.length ? <div className="chart-stack">
      <svg viewBox="0 0 1000 300" role="img" aria-label={summary} preserveAspectRatio="none"><title>Net equity in Indian rupees</title><path className="chart-gridline" d="M0 75H1000M0 150H1000M0 225H1000" /><path className="chart-equity" d={path(visible, 1000, 280, equityDomain)} vectorEffect="non-scaling-stroke" />
        {comparison && <path className="chart-equity chart-equity--comparison" d={path(comparison.equity, 1000, 280, equityDomain)} vectorEffect="non-scaling-stroke" />}
        <text x="12" y="24">NET EQUITY · INR{comparison ? ` · SOLID CURRENT / DASHED ${comparison.label}` : ''}</text>{events.slice(0, 400).map((event, index) => { const time = Number(event.time); const start = visible[0].time; const end = visible.at(-1)!.time; if (!Number.isFinite(time) || time < start || time > end) return null
          const x = end === start ? 0 : ((time - start) / (end - start)) * 1000; const kind = String(event.event_kind).toLowerCase()
          return kind === 'exit' ? <rect key={index} className={`chart-event chart-event--exit chart-event--${String(event.direction).toLowerCase()}`} x={x - 5} y="258" width="10" height="10"><title>{`Exit ${event.direction} trade ${event.cursor}`}</title></rect>
            : <path key={index} className={`chart-event chart-event--entry chart-event--${String(event.direction).toLowerCase()}`} d={`M${x},256l6,11l-12,0z`}><title>{`Entry ${event.direction} trade ${event.cursor}`}</title></path> })}</svg>
      <svg viewBox="0 0 1000 150" role="img" aria-label="Close-to-close drawdown in percent" preserveAspectRatio="none"><title>Close-to-close drawdown percentage</title><path className="chart-gridline" d="M0 50H1000M0 100H1000" /><path className="chart-drawdown" d={path(visibleDrawdown, 1000, 130, drawdownDomain)} vectorEffect="non-scaling-stroke" />{comparison && <path className="chart-drawdown chart-drawdown--comparison" d={path(comparison.drawdown, 1000, 130, drawdownDomain)} vectorEffect="non-scaling-stroke" />}<text x="12" y="22">DRAWDOWN · %</text></svg>
    </div> : <p className="workstation-unavailable">Series unavailable.</p>}
    <details className="chart-table"><summary>Open chart data table</summary><div className="table-scroll"><table><thead><tr><th scope="col">UTC time</th><th scope="col">Net equity (INR)</th><th scope="col">Drawdown (%)</th><th scope="col">Drawdown (INR)</th></tr></thead><tbody>{tablePoints.map((point, index) => { const absoluteIndex = tableOffset + index; return <tr key={`${point.time}:${absoluteIndex}`}><td>{new Date(point.time * 1000).toISOString()}</td><td>{point.value.toFixed(2)}</td><td>{visibleDrawdown[absoluteIndex]?.value.toFixed(4) ?? 'Unavailable'}</td><td>{visibleDrawdown[absoluteIndex]?.absolute.toFixed(2) ?? 'Unavailable'}</td></tr> })}</tbody></table></div><div className="chart-table-pagination"><button disabled={tableOffset === 0} onClick={() => setTableOffset((value) => Math.max(0, value - 100))}>Previous chart points</button><span>{tableOffset + 1}–{Math.min(tableOffset + 100, visible.length)} of {visible.length}</span><button disabled={tableOffset + 100 >= visible.length} onClick={() => setTableOffset((value) => value + 100)}>Next chart points</button></div></details>
  </section>
}
