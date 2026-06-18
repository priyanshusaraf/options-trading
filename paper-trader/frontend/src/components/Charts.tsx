import { useEffect, useRef } from 'react'
import { createChart, ColorType, type IChartApi, type ISeriesApi } from 'lightweight-charts'

const BASE = {
  layout: { background: { type: ColorType.Solid, color: 'transparent' }, textColor: '#8b93a7', fontFamily: 'ui-monospace, monospace', fontSize: 10 },
  grid: { vertLines: { color: '#161a22' }, horzLines: { color: '#161a22' } },
  rightPriceScale: { borderColor: '#232733' },
  timeScale: { borderColor: '#232733', timeVisible: true, secondsVisible: false },
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

  useEffect(() => {
    const el = ref.current!
    const chart = createChart(el, { ...BASE, height, width: el.clientWidth })
    chartRef.current = chart
    priceRef.current = area
      ? chart.addAreaSeries({ lineColor: '#3b82f6', topColor: 'rgba(59,130,246,0.22)', bottomColor: 'rgba(59,130,246,0.02)', lineWidth: 2, priceLineVisible: false })
      : chart.addCandlestickSeries({ upColor: '#2ebd85', downColor: '#f6465d', wickUpColor: '#2ebd85', wickDownColor: '#f6465d', borderVisible: false })
    emaRef.current = chart.addLineSeries({ color: '#e0b341', lineWidth: 1, priceLineVisible: false, lastValueVisible: false })
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
    chartRef.current?.timeScale().fitContent()
  }, [candles, ema, markers, area])

  return <div ref={ref} style={{ width: '100%' }} />
}

export function LineChart({ data, height = 220, color = '#3b82f6', area = true, priceLines = [] }:
  { data: Pt[]; height?: number; color?: string; area?: boolean; priceLines?: { price: number; color: string; title: string }[] }) {
  const ref = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const sRef = useRef<ISeriesApi<any> | null>(null)

  useEffect(() => {
    const el = ref.current!
    const chart = createChart(el, { ...BASE, height, width: el.clientWidth })
    chartRef.current = chart
    sRef.current = area
      ? chart.addAreaSeries({ lineColor: color, topColor: color + '33', bottomColor: color + '05', lineWidth: 2, priceLineVisible: false })
      : chart.addLineSeries({ color, lineWidth: 2, priceLineVisible: false })
    const teardown = observe(el, chart, height)
    return () => { teardown(); chartRef.current = null; sRef.current = null }
  }, [color, area, height])

  useEffect(() => {
    if (!sRef.current) return
    sRef.current.setData(data as any)
    priceLines.forEach((pl) => sRef.current!.createPriceLine({ price: pl.price, color: pl.color, lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: pl.title } as any))
    chartRef.current?.timeScale().fitContent()
  }, [data])

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
