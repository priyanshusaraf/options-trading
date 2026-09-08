import { useMemo, useState } from 'react'
import type { ChartAnnotation, MarketContextBar } from '../../shell/contracts'

const WIDTH = 1200
const PRICE_HEIGHT = 430
const VOLUME_HEIGHT = 90

function numeric(value: unknown): number | null {
  if (typeof value === 'string') { const parsed = Number(value); return Number.isFinite(parsed) ? parsed : null }
  if (value && typeof value === 'object') {
    const row = value as Record<string, unknown>; const numerator = Number(row.numerator); const denominator = Number(row.denominator)
    if (Number.isFinite(numerator) && Number.isFinite(denominator) && denominator !== 0) return numerator / denominator
  }
  return null
}
function plainProduct(value: unknown) { return String(value).replace(/canonical/gi, 'verified') }

export function MarketContextChart({ bars, annotations, tradeEvents = [] }: {
  bars: readonly MarketContextBar[]; annotations: readonly ChartAnnotation[]
  tradeEvents?: readonly Readonly<Record<string, unknown>>[]
}) {
  const [tableOffset, setTableOffset] = useState(0)
  const domain = useMemo(() => {
    const lows = bars.map((bar) => bar.low); const highs = bars.map((bar) => bar.high)
    const minimum = lows.length ? Math.min(...lows) : 0; const maximum = highs.length ? Math.max(...highs) : 1
    const padding = Math.max((maximum - minimum) * 0.06, maximum * 0.002, 1)
    return { minimum: minimum - padding, maximum: maximum + padding,
      maxVolume: Math.max(...bars.map((bar) => bar.volume), 1) }
  }, [bars])
  const xForTime = (time: string) => { const timestamp = Date.parse(time); const first = Date.parse(bars[0]?.event_time ?? time); const last = Date.parse(bars.at(-1)?.event_time ?? time)
    return last === first ? WIDTH / 2 : ((timestamp - first) / (last - first)) * WIDTH }
  const y = (price: number) => PRICE_HEIGHT - ((price - domain.minimum) / (domain.maximum - domain.minimum)) * PRICE_HEIGHT
  const candleWidth = Math.max(1.2, Math.min(9, WIDTH / Math.max(bars.length, 1) * 0.62))
  const summary = bars.length ? `${bars.length.toLocaleString()} completed candles. ${bars[0].close.toFixed(2)} to ${bars.at(-1)!.close.toFixed(2)} in price units.` : 'No completed candles are visible.'
  const table = bars.slice(tableOffset, tableOffset + 100)
  const middleBar = bars[Math.floor((bars.length - 1) / 2)]
  return <section className="market-chart" aria-labelledby="market-chart-title">
    <header><div><h3 id="market-chart-title">Completed price and volume</h3><p>{summary}</p></div><div className="market-chart-key" aria-label="Chart key"><span><i className="key-up" />Close at or above open</span><span><i className="key-down" />Close below open</span><span><i className="key-review" />Review drawing</span></div></header>
    {bars.length ? <div className="market-chart-frame">
      <svg viewBox={`0 0 ${WIDTH} ${PRICE_HEIGHT + VOLUME_HEIGHT}`} role="img" aria-label={summary} preserveAspectRatio="none">
        <title>Completed OHLCV candles with review drawings</title>
        <path className="market-grid" d={`M0 86H${WIDTH}M0 172H${WIDTH}M0 258H${WIDTH}M0 344H${WIDTH}M0 ${PRICE_HEIGHT}H${WIDTH}`} />
        <g className="market-axis" aria-hidden="true">
          <text x="10" y="20">{domain.maximum.toFixed(2)} price</text>
          <text x="10" y={PRICE_HEIGHT / 2}>{((domain.minimum + domain.maximum) / 2).toFixed(2)} price</text>
          <text x="10" y={PRICE_HEIGHT - 9}>{domain.minimum.toFixed(2)} price</text>
          <text x="10" y={PRICE_HEIGHT + 18}>Volume · units</text>
          <text x="10" y={PRICE_HEIGHT + VOLUME_HEIGHT - 5}>{bars[0]?.completed_at.slice(11, 16)} UTC</text>
          <text x={WIDTH / 2} textAnchor="middle" y={PRICE_HEIGHT + VOLUME_HEIGHT - 5}>{middleBar?.completed_at.slice(11, 16)} UTC</text>
          <text x={WIDTH - 10} textAnchor="end" y={PRICE_HEIGHT + VOLUME_HEIGHT - 5}>{bars.at(-1)?.completed_at.slice(11, 16)} UTC</text>
        </g>
        <g className="causal-playhead"><line x1={WIDTH - 2} x2={WIDTH - 2} y1="0" y2={PRICE_HEIGHT + VOLUME_HEIGHT} vectorEffect="non-scaling-stroke" /><path d={`M${WIDTH-11},12l9,-9l9,9l-9,9z`}><title>Latest completed candle</title></path></g>
        {bars.map((bar, index) => { const x = bars.length === 1 ? WIDTH / 2 : index / (bars.length - 1) * WIDTH; const rising = bar.close >= bar.open
          const bodyTop = y(Math.max(bar.open, bar.close)); const bodyHeight = Math.max(1.5, Math.abs(y(bar.open) - y(bar.close)))
          const volumeHeight = bar.volume / domain.maxVolume * (VOLUME_HEIGHT - 12)
          return <g key={bar.cursor} className={rising ? 'candle candle--up' : 'candle candle--down'}>
            <line x1={x} x2={x} y1={y(bar.high)} y2={y(bar.low)} vectorEffect="non-scaling-stroke" />
            <rect x={x - candleWidth / 2} y={bodyTop} width={candleWidth} height={bodyHeight} />
            <rect className="volume" x={x - candleWidth / 2} y={PRICE_HEIGHT + VOLUME_HEIGHT - volumeHeight} width={candleWidth} height={volumeHeight} />
          </g> })}
        {annotations.map((annotation) => {
          const geometry = annotation.geometry; const kind = String(geometry.kind)
          if (kind === 'LEVEL') { const price = numeric(geometry.price); return price === null ? null : <line key={annotation.annotation_id} className="review-level" x1="0" x2={WIDTH} y1={y(price)} y2={y(price)} vectorEffect="non-scaling-stroke"><title>Review drawing: level</title></line> }
          if (kind === 'ZONE') { const lower = numeric(geometry.lower); const upper = numeric(geometry.upper); return lower === null || upper === null ? null : <rect key={annotation.annotation_id} className="review-zone" x="0" width={WIDTH} y={y(upper)} height={Math.max(1, y(lower) - y(upper))}><title>Review drawing: zone</title></rect> }
          const start = geometry.start as Record<string, unknown> | undefined; const end = geometry.end as Record<string, unknown> | undefined
          const line = kind === 'CHANNEL' ? geometry.center as Record<string, unknown> : geometry
          const lineStart = (line?.start ?? start) as Record<string, unknown> | undefined; const lineEnd = (line?.end ?? end) as Record<string, unknown> | undefined
          if (kind === 'LINE' || kind === 'CHANNEL') { const p1 = numeric(lineStart?.price); const p2 = numeric(lineEnd?.price); if (p1 === null || p2 === null) return null
            const x1 = xForTime(String(lineStart?.time)); const x2 = xForTime(String(lineEnd?.time)); const width = kind === 'CHANNEL' ? numeric(geometry.half_width) ?? 0 : 0
            return <g key={annotation.annotation_id} className="review-line"><line x1={x1} x2={x2} y1={y(p1)} y2={y(p2)} vectorEffect="non-scaling-stroke"><title>{`Review drawing: ${kind.toLowerCase()}`}</title></line>{kind === 'CHANNEL' && <><line x1={x1} x2={x2} y1={y(p1 + width)} y2={y(p2 + width)} /><line x1={x1} x2={x2} y1={y(p1 - width)} y2={y(p2 - width)} /></>}</g> }
          if (kind === 'FIBONACCI' && Array.isArray(geometry.levels)) return <g key={annotation.annotation_id} className="review-fibonacci">{geometry.levels.map((level, index) => { const price = numeric(level); return price === null ? null : <line key={index} x1="0" x2={WIDTH} y1={y(price)} y2={y(price)}><title>{`Review drawing: Fibonacci level ${index + 1}`}</title></line> })}</g>
          return null
        })}
        {tradeEvents.slice(0, 400).map((event, index) => { const time = Number(event.time) * 1000; const price = Number(event.price); if (!Number.isFinite(time) || !Number.isFinite(price)) return null
          const iso = new Date(time).toISOString(); const x = xForTime(iso); if (x < 0 || x > WIDTH) return null
          return String(event.event_kind) === 'EXIT' ? <rect key={index} className="market-trade market-trade--exit" x={x - 5} y={y(price) - 5} width="10" height="10"><title>{`Exit trade ${plainProduct(event.cursor)}`}</title></rect>
            : <path key={index} className="market-trade market-trade--entry" d={`M${x},${y(price)-7}l7,14h-14z`}><title>{`Entry trade ${plainProduct(event.cursor)}`}</title></path> })}
      </svg>
    </div> : <p className="market-context-state">No verified candles are linked to this result</p>}
    <details className="chart-table"><summary>Open candle data table</summary><div className="table-scroll"><table><caption>Loaded completed candles in UTC with exact displayed units</caption><thead><tr><th scope="col">Candle closed (UTC)</th><th scope="col">Open (price)</th><th scope="col">High (price)</th><th scope="col">Low (price)</th><th scope="col">Close (price)</th><th scope="col">Volume (units)</th></tr></thead><tbody>{table.map((bar) => <tr key={bar.cursor}><td>{bar.completed_at}</td><td>{bar.open}</td><td>{bar.high}</td><td>{bar.low}</td><td>{bar.close}</td><td>{bar.volume}</td></tr>)}</tbody></table></div><div className="chart-table-pagination"><button disabled={tableOffset === 0} onClick={() => setTableOffset((value) => Math.max(0, value - 100))}>Previous candles</button><span>{bars.length ? tableOffset + 1 : 0}–{Math.min(tableOffset + 100, bars.length)} of {bars.length}</span><button disabled={tableOffset + 100 >= bars.length} onClick={() => setTableOffset((value) => value + 100)}>Next candles</button></div></details>
  </section>
}
