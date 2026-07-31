/* Data components — §6.2
 *
 * The important one is StatCell: "No metric in this product renders outside a
 * StatCell." That is enforced here rather than by convention — the component
 * takes a `Stat`, not a number, so there is no way to render a metric without
 * carrying its sample size and interval along with it.
 */

import { useMemo, type ReactNode } from 'react'
import type { Stat } from '../../domain/metrics'
import './data.css'

// ── NumericCell ───────────────────────────────────────────────────────────
// §6.2 Tabular figures, sign-aware colour, R/₹ unit toggle, right-aligned,
// never truncated.

export function fmtR(r: number | null | undefined, digits = 1): string {
  if (r == null || !Number.isFinite(r)) return '—'
  const s = r.toFixed(digits)
  return r > 0 ? `+${s}` : s
}

export function fmtRupees(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return '—'
  const abs = Math.abs(Math.round(v))
  const s = abs.toLocaleString('en-IN')
  return `${v < 0 ? '−' : v > 0 ? '+' : ''}₹${s}`
}

export function fmtPct(v: number | null | undefined, digits = 0): string {
  if (v == null || !Number.isFinite(v)) return '—'
  return `${(v * 100).toFixed(digits)}%`
}

export function signClass(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v) || v === 0) return 'flat'
  return v > 0 ? 'pos' : 'neg'
}

export function NumericCell({
  value,
  unit = 'R',
  digits,
  muted,
}: {
  value: number | null
  unit?: 'R' | '₹' | '%' | 'x' | 'raw'
  digits?: number
  muted?: boolean
}) {
  const text =
    unit === 'R' ? fmtR(value, digits ?? 1)
    : unit === '₹' ? fmtRupees(value)
    : unit === '%' ? fmtPct(value, digits ?? 0)
    : value == null ? '—'
    : value.toFixed(digits ?? 2)
  return (
    <span className={`num ${muted ? 'faint' : signClass(value)}`}>{text}</span>
  )
}

// ── StatCell ──────────────────────────────────────────────────────────────
// §5.7 "Below n=20 a metric renders as ░░░ n=9 with no number at all."
// §0.5 "No metric ever displays without n and an interval."

export function StatCell({
  stat,
  label,
  format = 'R',
  hint,
  spark,
  compact,
}: {
  stat: Stat
  label?: string
  format?: 'R' | '%' | '₹' | 'x' | 'raw'
  /** §5.7 Each analysis carries a plain-language "what this would change" line. */
  hint?: string
  spark?: number[]
  compact?: boolean
}) {
  const insufficient = stat.state === 'insufficient'

  const value =
    format === 'R' ? fmtR(stat.value, 2)
    : format === '%' ? fmtPct(stat.value, 0)
    : format === '₹' ? fmtRupees(stat.value)
    : format === 'x' ? `${stat.value.toFixed(2)}×`
    : stat.value.toFixed(2)

  const interval =
    format === '%' ? `±${(stat.ci * 100).toFixed(0)}%` : `±${stat.ci.toFixed(2)}`

  return (
    <div className={`stat ${compact ? 'stat--compact' : ''} stat--${stat.state}`}>
      {label && <div className="label stat__label">{label}</div>}
      <div className="stat__row">
        {insufficient ? (
          // No number at all. This will occasionally annoy you; it is
          // protecting you from revising a strategy on nine observations.
          <span className="stat__blocks mono" title="Not yet evidence">
            ░░░
          </span>
        ) : (
          <span className={`stat__value num ${signClass(stat.value)}`}>
            {value}
          </span>
        )}
        <span className="stat__n mono">n={stat.n}</span>
        {!insufficient && stat.n > 1 && (
          <span className="stat__ci mono">{interval}</span>
        )}
        {spark && spark.length > 1 && <Sparkline values={spark} />}
      </div>
      {insufficient && (
        <div className="stat__notyet">not yet evidence</div>
      )}
      {hint && <div className="stat__hint">{hint}</div>}
    </div>
  )
}

// ── Sparkline ─────────────────────────────────────────────────────────────
// §6.2 64×16, no axes, single hue, last point marked.

export function Sparkline({
  values,
  width = 64,
  height = 16,
}: {
  values: number[]
  width?: number
  height?: number
}) {
  const path = useMemo(() => {
    if (values.length < 2) return null
    const min = Math.min(...values)
    const max = Math.max(...values)
    const span = max - min || 1
    const step = width / (values.length - 1)
    const pts = values.map((v, i) => {
      const x = i * step
      const y = height - 1 - ((v - min) / span) * (height - 2)
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    return { d: `M${pts.join('L')}`, last: pts[pts.length - 1].split(',') }
  }, [values, width, height])

  if (!path) return null
  return (
    <svg className="spark" width={width} height={height} aria-hidden="true">
      <path d={path.d} fill="none" stroke="currentColor" strokeWidth="1" />
      <circle
        cx={path.last[0]}
        cy={path.last[1]}
        r="1.5"
        fill="currentColor"
      />
    </svg>
  )
}

/** Block sparkline used by the playbook rows (▁▃▅▆▇). §5.6 */
export function BlockSpark({ values }: { values: number[] }) {
  const blocks = '▁▂▃▄▅▆▇█'
  if (!values.length) return <span className="mono faint">░░░░░</span>
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1
  return (
    <span className="mono">
      {values
        .map((v) => blocks[Math.min(7, Math.floor(((v - min) / span) * 7))])
        .join('')}
    </span>
  )
}

// ── Distribution ──────────────────────────────────────────────────────────
// §6.2 Histogram with baseline only, no gridlines, optional highlight window.

export function Distribution({
  bins,
  highlight,
  height = 96,
}: {
  bins: { from: number; to: number; count: number }[]
  /** §5.7 "your last 20 highlighted" */
  highlight?: { from: number; to: number; count: number }[]
  height?: number
}) {
  if (!bins.length) return <div className="faint">—</div>
  const max = Math.max(...bins.map((b) => b.count), 1)
  return (
    <div className="dist" style={{ height }}>
      <div className="dist__bars">
        {bins.map((b, i) => {
          const hl = highlight?.[i]?.count ?? 0
          return (
            <div className="dist__col" key={i} title={`${b.from.toFixed(1)}R to ${b.to.toFixed(1)}R · ${b.count}`}>
              <div
                className={`dist__bar ${b.from < 0 ? 'neg' : 'pos'}`}
                style={{ height: `${(b.count / max) * 100}%` }}
              >
                {hl > 0 && (
                  <div
                    className="dist__hl"
                    style={{ height: `${(hl / b.count) * 100}%` }}
                  />
                )}
              </div>
            </div>
          )
        })}
      </div>
      <div className="dist__baseline" />
      <div className="dist__axis">
        <span className="mono faint">{bins[0].from.toFixed(1)}R</span>
        <span className="mono faint">
          {bins[bins.length - 1].to.toFixed(1)}R
        </span>
      </div>
    </div>
  )
}

// ── Heatmap ───────────────────────────────────────────────────────────────
// §6.2 The year grid and the setup × regime matrix share one component.

export interface HeatCell {
  key: string
  /** Null renders as an empty cell, not as zero — absence is not a value. */
  value: number | null
  n?: number
  label?: string
  /** §5.5 cell border = amber if unreviewed */
  flagged?: boolean
  /** Below the evidence threshold, cells are greyed. §5.7 */
  insufficient?: boolean
}

export function Heatmap({
  cells,
  columns,
  cellSize = 11,
  gap = 2,
  onSelect,
  scale,
}: {
  cells: HeatCell[]
  columns: number
  cellSize?: number
  gap?: number
  onSelect?: (key: string) => void
  scale?: number
}) {
  const extent =
    scale ??
    Math.max(
      0.001,
      ...cells.map((c) => Math.abs(c.value ?? 0)).filter(Number.isFinite),
    )
  return (
    <div
      className="heat"
      style={{
        gridTemplateColumns: `repeat(${columns}, ${cellSize}px)`,
        gap,
      }}
    >
      {cells.map((c) => {
        const v = c.value
        const intensity = v == null ? 0 : Math.min(1, Math.abs(v) / extent)
        const hue =
          v == null || v === 0 ? 'var(--neutral-fill)'
          : v > 0 ? 'var(--long)'
          : 'var(--short)'
        return (
          <button
            key={c.key}
            className={`heat__cell ${c.flagged ? 'is-flagged' : ''} ${
              c.insufficient ? 'is-insufficient' : ''
            }`}
            style={{
              width: cellSize,
              height: cellSize,
              background:
                v == null
                  ? 'transparent'
                  : `color-mix(in srgb, ${hue} ${Math.round(
                      12 + intensity * 76,
                    )}%, transparent)`,
              borderColor: v == null ? 'var(--border)' : 'transparent',
            }}
            title={c.label ?? c.key}
            onClick={() => onSelect?.(c.key)}
          />
        )
      })}
    </div>
  )
}

// ── ReliabilityCurve ──────────────────────────────────────────────────────
// §6.2 Calibration only; diagonal reference is a hairline, not a legend.

export function ReliabilityCurve({
  points,
  width = 220,
  height = 160,
}: {
  points: { stated: number; realised: number; n: number }[]
  width?: number
  height?: number
}) {
  const pad = 18
  const x = (v: number) => pad + v * (width - pad * 2)
  const y = (v: number) => height - pad - v * (height - pad * 2)
  const usable = points.filter((p) => p.n > 0)

  return (
    <svg className="reliability" width={width} height={height}>
      <line
        x1={x(0)} y1={y(0)} x2={x(1)} y2={y(1)}
        stroke="var(--border-strong)" strokeWidth="1"
      />
      <line x1={x(0)} y1={y(0)} x2={x(1)} y2={y(0)} stroke="var(--border)" />
      <line x1={x(0)} y1={y(0)} x2={x(0)} y2={y(1)} stroke="var(--border)" />
      {usable.length > 1 && (
        <path
          d={`M${usable.map((p) => `${x(p.stated)},${y(p.realised)}`).join('L')}`}
          fill="none"
          stroke="var(--interactive)"
          strokeWidth="1.5"
        />
      )}
      {usable.map((p, i) => (
        <circle
          key={i}
          cx={x(p.stated)}
          cy={y(p.realised)}
          // Radius carries n, so sample size is visible without a legend.
          r={Math.max(2, Math.min(6, Math.sqrt(p.n)))}
          fill="var(--interactive)"
          opacity={p.n >= 20 ? 0.95 : 0.35}
        >
          <title>{`stated ${(p.stated * 100).toFixed(0)}% · realised ${(
            p.realised * 100
          ).toFixed(0)}% · n=${p.n}`}</title>
        </circle>
      ))}
      <text x={x(0)} y={height - 4} className="axis-text">stated</text>
      <text x={2} y={y(1) - 4} className="axis-text">realised</text>
    </svg>
  )
}

// ── EquityTrack ───────────────────────────────────────────────────────────
// §6.2 R-based cumulative line; drawdown shaded at 6% opacity; no y-axis
// labels until hover.

export function EquityTrack({
  values,
  width = 640,
  height = 120,
}: {
  values: number[]
  width?: number
  height?: number
}) {
  const geom = useMemo(() => {
    if (values.length < 2) return null
    const min = Math.min(0, ...values)
    const max = Math.max(0, ...values)
    const span = max - min || 1
    const step = width / (values.length - 1)
    const px = (i: number) => i * step
    const py = (v: number) => height - ((v - min) / span) * height

    // Drawdown ribbon: the area between the running peak and the curve.
    let peak = -Infinity
    const peaks = values.map((v) => (peak = Math.max(peak, v)))
    const ddPath =
      `M${values.map((v, i) => `${px(i)},${py(v)}`).join('L')}` +
      `L${px(values.length - 1)},${py(peaks[peaks.length - 1])}` +
      `${peaks
        .slice()
        .reverse()
        .map((v, i) => `L${px(values.length - 1 - i)},${py(v)}`)
        .join('')}Z`

    return {
      line: `M${values.map((v, i) => `${px(i)},${py(v)}`).join('L')}`,
      dd: ddPath,
      zeroY: py(0),
      min,
      max,
    }
  }, [values, width, height])

  if (!geom) return <div className="faint">—</div>

  return (
    <svg
      className="equity"
      width="100%"
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
    >
      <line
        x1="0" y1={geom.zeroY} x2={width} y2={geom.zeroY}
        stroke="var(--border)" strokeWidth="1" vectorEffect="non-scaling-stroke"
      />
      <path d={geom.dd} fill="var(--short)" opacity="0.06" />
      <path
        d={geom.line}
        fill="none"
        stroke="var(--text-muted)"
        strokeWidth="1.5"
        vectorEffect="non-scaling-stroke"
      />
      <title>{`${geom.min.toFixed(1)}R to ${geom.max.toFixed(1)}R`}</title>
    </svg>
  )
}

// ── RMeter ────────────────────────────────────────────────────────────────
// §6.4 A small horizontal track showing MAE, entry, exit, MFE on one line.
// "Reads in half a second, replaces a chart."

export function RMeter({
  mae,
  mfe,
  realised,
  width = 160,
}: {
  mae: number | null
  mfe: number | null
  realised: number | null
  width?: number
}) {
  const lo = Math.min(-0.5, mae ?? 0, realised ?? 0)
  const hi = Math.max(1, mfe ?? 0, realised ?? 0)
  const span = hi - lo || 1
  const pct = (v: number) => ((v - lo) / span) * 100

  return (
    <div className="rmeter" style={{ width }} title="MAE · entry · exit · MFE">
      <div className="rmeter__track" />
      <div className="rmeter__zero" style={{ left: `${pct(0)}%` }} />
      {mae != null && (
        <div className="rmeter__mae" style={{
          left: `${pct(Math.min(0, mae))}%`,
          width: `${Math.abs(pct(0) - pct(Math.min(0, mae)))}%`,
        }} />
      )}
      {mfe != null && (
        <div className="rmeter__mfe" style={{
          left: `${pct(0)}%`,
          width: `${Math.abs(pct(Math.max(0, mfe)) - pct(0))}%`,
        }} />
      )}
      {realised != null && (
        <div
          className={`rmeter__exit ${signClass(realised)}`}
          style={{ left: `${pct(realised)}%` }}
        />
      )}
    </div>
  )
}

// ── Virtualised list ──────────────────────────────────────────────────────
// §3.4 "blotter scroll at 10,000 rows must stay at 60fps (virtualised)".
// Written by hand rather than pulled in as a dependency: the windowing this
// product needs is fixed-height rows and nothing else.

export function useWindow(
  total: number,
  rowHeight: number,
  viewportHeight: number,
  scrollTop: number,
  overscan = 8,
) {
  const first = Math.max(0, Math.floor(scrollTop / rowHeight) - overscan)
  const visible = Math.ceil(viewportHeight / rowHeight) + overscan * 2
  const last = Math.min(total, first + visible)
  return { first, last, padTop: first * rowHeight, padBottom: (total - last) * rowHeight }
}

export function Peek({ children }: { children: ReactNode }) {
  return <div className="peek glass">{children}</div>
}
