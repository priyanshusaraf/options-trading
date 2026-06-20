import { useEffect, useRef } from 'react'
import { createChart, ColorType, type IChartApi, type ISeriesApi, type IPriceLine } from 'lightweight-charts'

// lightweight-charts renders timestamps in UTC by default. Our data epochs are
// true instants, so format the axis + crosshair explicitly in IST — an Indian
// market app must always show the real session clock regardless of viewer tz.
const IST = 'Asia/Kolkata'
const istTime = (t: number) =>
  new Date((t as number) * 1000).toLocaleTimeString('en-IN', { timeZone: IST, hour: '2-digit', minute: '2-digit', hour12: false })
const istDate = (t: number) =>
  new Date((t as number) * 1000).toLocaleDateString('en-IN', { timeZone: IST, day: '2-digit', month: 'short' })
// tickMarkType: 0 Year, 1 Month, 2 DayOfMonth, 3 Time, 4 TimeWithSeconds
const tickMarkFormatter = (t: any, tickMarkType: number) =>
  tickMarkType <= 2 ? istDate(t) : istTime(t)

const BASE = {
  layout: { background: { type: ColorType.Solid, color: 'transparent' }, textColor: '#8b93a7', fontFamily: 'ui-monospace, monospace', fontSize: 10 },
  grid: { vertLines: { color: '#161a22' }, horzLines: { color: '#161a22' } },
  rightPriceScale: { borderColor: '#232733' },
  timeScale: { borderColor: '#232733', timeVisible: true, secondsVisible: false, tickMarkFormatter },
  localization: { timeFormatter: (t: any) => `${istDate(t)} ${istTime(t)}` },
  crosshair: { mode: 0 as const },
}

// Attach a ResizeObserver that is safely torn down BEFORE chart.remove(), with a
// disposed guard — avoids lightweight-charts' "Object is disposed" on unmount.
function observe(el: HTMLDivElement, chart: IChartApi, height: number) {
  let disposed = false
  const ro = new ResizeObserver(() => { if (!disposed) chart.applyOptions({ width: el.clientWidth, height }) })
  ro.observe(el)
  return () => { disposed = true; ro.disconnect(); chart.remove() }
}

interface Candle { time: number; open: number; high: number; low: number; close: number }
interface Pt { time: number; value: number }
interface Marker { time: number; position: string; color: string; shape: string; text: string }

export function PriceChart({ candles, ema = [], markers = [], height = 280, area = false }:
  { candles: Candle[]; ema?: Pt[]; markers?: Marker[]; height?: number; area?: boolean }) {
  const ref = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const priceRef = useRef<ISeriesApi<any> | null>(null)
  const emaRef = useRef<ISeriesApi<any> | null>(null)
  // Track the first bar's time so we only auto-fit when the DATASET changes
  // (new instrument / interval) — never on a live tick append, which would
  // otherwise snap the view back and fight the user's zoom/pan.
  const firstTimeRef = useRef<number | null>(null)

  useEffect(() => {
    const el = ref.current!
    const chart = createChart(el, { ...BASE, height, width: el.clientWidth })
    chartRef.current = chart
    priceRef.current = area
      ? chart.addAreaSeries({ lineColor: '#3b82f6', topColor: 'rgba(59,130,246,0.22)', bottomColor: 'rgba(59,130,246,0.02)', lineWidth: 2, priceLineVisible: false })
      : chart.addCandlestickSeries({ upColor: '#2ebd85', downColor: '#f6465d', wickUpColor: '#2ebd85', wickDownColor: '#f6465d', borderVisible: false })
    emaRef.current = chart.addLineSeries({ color: '#e0b341', lineWidth: 1, priceLineVisible: false, lastValueVisible: false })
    firstTimeRef.current = null
    const teardown = observe(el, chart, height)
    return () => { teardown(); chartRef.current = null; priceRef.current = null; emaRef.current = null }
  }, [area, height])

  useEffect(() => {
    const ps = priceRef.current
    if (!ps) return
    if (area) ps.setData(candles.map((c) => ({ time: c.time as any, value: c.close })))
    else ps.setData(candles as any)
    emaRef.current?.setData(ema as any)
    if (!area && markers.length) ps.setMarkers(markers as any)
    const first = candles.length ? candles[0].time : null
    if (first !== null && first !== firstTimeRef.current) {
      firstTimeRef.current = first
      chartRef.current?.timeScale().fitContent()   // new dataset only
    }
  }, [candles, ema, markers, area])

  return <div ref={ref} style={{ width: '100%' }} />
}

export function LineChart({ data, height = 220, color = '#3b82f6', area = true, priceLines = [] }:
  { data: Pt[]; height?: number; color?: string; area?: boolean; priceLines?: { price: number; color: string; title: string }[] }) {
  const ref = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const sRef = useRef<ISeriesApi<any> | null>(null)
  const lineRefs = useRef<IPriceLine[]>([])
  const firstTimeRef = useRef<number | null>(null)

  useEffect(() => {
    const el = ref.current!
    const chart = createChart(el, { ...BASE, height, width: el.clientWidth })
    chartRef.current = chart
    sRef.current = area
      ? chart.addAreaSeries({ lineColor: color, topColor: color + '33', bottomColor: color + '05', lineWidth: 2, priceLineVisible: false })
      : chart.addLineSeries({ color, lineWidth: 2, priceLineVisible: false })
    lineRefs.current = []
    firstTimeRef.current = null
    const teardown = observe(el, chart, height)
    return () => { teardown(); chartRef.current = null; sRef.current = null; lineRefs.current = [] }
  }, [color, area, height])

  useEffect(() => {
    const s = sRef.current
    if (!s) return
    s.setData(data as any)
    // remove stale price lines before re-adding (otherwise they accumulate on
    // every data update / tick)
    lineRefs.current.forEach((pl) => { try { s.removePriceLine(pl) } catch { /* disposed */ } })
    lineRefs.current = priceLines.map((pl) =>
      s.createPriceLine({ price: pl.price, color: pl.color, lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: pl.title } as any))
    const first = data.length ? data[0].time : null
    if (first !== null && first !== firstTimeRef.current) {
      firstTimeRef.current = first
      chartRef.current?.timeScale().fitContent()
    }
  }, [data, priceLines])

  return <div ref={ref} style={{ width: '100%' }} />
}

export function MultiLineChart({ series, height = 300 }:
  { series: { name: string; data: Pt[]; color: string }[]; height?: number }) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = ref.current!
    const chart = createChart(el, { ...BASE, height, width: el.clientWidth })
    series.forEach((s) => {
      const ls = chart.addLineSeries({ color: s.color, lineWidth: 2, priceLineVisible: false, lastValueVisible: false })
      ls.setData(s.data as any)
    })
    chart.timeScale().fitContent()
    return observe(el, chart, height)
  }, [series, height])

  return <div ref={ref} style={{ width: '100%' }} />
}
