import { useId } from 'react'
import { cx } from './ui'

function points(values: number[], width: number, height: number, inset = 4) {
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1
  const innerW = width - inset * 2
  const innerH = height - inset * 2
  return values.map((value, index) => {
    const x = inset + (index / Math.max(values.length - 1, 1)) * innerW
    const y = inset + innerH - ((value - min) / span) * innerH
    return `${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' ')
}

export function Sparkline({ values, tone = 'violet', height = 48, className }: { values: number[]; tone?: 'violet' | 'good' | 'warn' | 'bad' | 'muted'; height?: number; className?: string }) {
  return (
    <svg className={cx('sparkline', className)} viewBox={`0 0 180 ${height}`} preserveAspectRatio="none" aria-hidden="true">
      <line x1="0" x2="180" y1={height - 1} y2={height - 1} className="chart-axis" />
      <polyline points={points(values, 180, height)} className={cx('chart-line', `chart-line--${tone}`)} />
    </svg>
  )
}

export function EquityChart({ values, benchmark, height = 220, labels = true }: { values: number[]; benchmark?: number[]; height?: number; labels?: boolean }) {
  const width = 760
  const chartId = useId()
  const current = values.at(-1) ?? 0
  const start = values[0] ?? 1
  const delta = ((current / start) - 1) * 100
  return (
    <div className="equity-chart">
      {labels ? <div className="chart-legend"><span><i className="legend-dot legend-dot--violet" />Net equity</span>{benchmark ? <span><i className="legend-dot legend-dot--muted" />Benchmark</span> : null}<strong>{delta >= 0 ? '+' : ''}{delta.toFixed(1)}%</strong></div> : null}
      <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" role="img" aria-labelledby={chartId}>
        <title id={chartId}>Equity curve</title>
        {[0.25, 0.5, 0.75].map((part) => <line key={part} x1="0" x2={width} y1={height * part} y2={height * part} className="chart-grid-line" />)}
        {benchmark ? <polyline points={points(benchmark, width, height, 8)} className="chart-line chart-line--muted chart-line--dashed" /> : null}
        <polyline points={points(values, width, height, 8)} className="chart-line chart-line--violet chart-line--strong" />
      </svg>
    </div>
  )
}

export function MiniBars({ values, labels, tone = 'violet' }: { values: number[]; labels?: string[]; tone?: 'violet' | 'good' | 'warn' | 'bad' }) {
  const max = Math.max(...values.map((value) => Math.abs(value)), 1)
  return (
    <div className="mini-bars">
      {values.map((value, index) => (
        <div className="mini-bars__item" key={`${labels?.[index] ?? index}-${value}`}>
          <div className="mini-bars__track">
            <span className={cx('mini-bars__bar', `mini-bars__bar--${value < 0 ? 'bad' : tone}`)} style={{ height: `${Math.max(8, Math.abs(value) / max * 100)}%` }} />
          </div>
          {labels?.[index] ? <small>{labels[index]}</small> : null}
        </div>
      ))}
    </div>
  )
}

export function Heatmap({ xs, ys, grid, current }: { xs: number[]; ys: number[]; grid: number[][]; current?: { x: number; y: number } }) {
  const flat = grid.flat()
  const min = Math.min(...flat)
  const max = Math.max(...flat)
  const span = max - min || 1
  return (
    <div className="heatmap" style={{ gridTemplateColumns: `54px repeat(${xs.length}, minmax(38px, 1fr))` }}>
      <span />
      {xs.map((x) => <span className="heatmap__axis" key={`x-${x}`}>{x}</span>)}
      {ys.flatMap((y, row) => [
        <span className="heatmap__axis" key={`y-${y}`}>{y}</span>,
        ...xs.map((x, column) => {
          const value = grid[row]?.[column] ?? 0
          const bucket = Math.max(0, Math.min(5, Math.round(((value - min) / span) * 5)))
          return <button type="button" key={`${x}-${y}`} className={cx('heatmap__cell', `heatmap__cell--${bucket}`, current?.x === x && current.y === y && 'is-current')} title={`${x} × ${y}: ${value.toFixed(2)}`}><strong>{value.toFixed(2)}</strong></button>
        }),
      ])}
    </div>
  )
}

export function MonteCarloChart({ p5, p50, p95 }: { p5: number[]; p50: number[]; p95: number[] }) {
  return (
    <div className="mc-chart">
      <div className="chart-legend"><span><i className="legend-dot legend-dot--muted" />5th–95th percentile</span><span><i className="legend-dot legend-dot--violet" />Median</span></div>
      <svg viewBox="0 0 600 180" preserveAspectRatio="none" role="img" aria-label="Monte Carlo percentile paths">
        {[45, 90, 135].map((y) => <line key={y} x1="0" x2="600" y1={y} y2={y} className="chart-grid-line" />)}
        <polyline points={points(p95, 600, 180, 8)} className="chart-line chart-line--muted" />
        <polyline points={points(p5, 600, 180, 8)} className="chart-line chart-line--muted" />
        <polyline points={points(p50, 600, 180, 8)} className="chart-line chart-line--violet chart-line--strong" />
      </svg>
    </div>
  )
}
