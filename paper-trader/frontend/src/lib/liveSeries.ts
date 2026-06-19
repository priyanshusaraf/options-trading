export interface LiveCandle {
  time: number
  open?: number
  high?: number
  low?: number
  close: number
}

export interface LivePoint {
  time: number
  value: number
}

export const epochSeconds = (iso: string) => Math.floor(new Date(iso).getTime() / 1000)

export function mergeLiveCandle(candles: LiveCandle[], time: number, price: number, limit = 300): LiveCandle[] {
  if (!Number.isFinite(price) || !Number.isFinite(time)) return candles
  const prev = candles[candles.length - 1]
  if (!prev) return [{ time, open: price, high: price, low: price, close: price }]
  if (time <= prev.time) {
    const updated = {
      ...prev,
      high: Math.max(prev.high ?? prev.close, price),
      low: Math.min(prev.low ?? prev.close, price),
      close: price,
    }
    return [...candles.slice(0, -1), updated]
  }
  const next = { time, open: prev.close, high: Math.max(prev.close, price), low: Math.min(prev.close, price), close: price }
  return [...candles, next].slice(-limit)
}

export function mergeLivePoint(points: LivePoint[], time: number, value: number, limit = 300): LivePoint[] {
  if (!Number.isFinite(value) || !Number.isFinite(time)) return points
  const prev = points[points.length - 1]
  if (!prev) return [{ time, value }]
  if (time <= prev.time) return [...points.slice(0, -1), { time: prev.time, value }]
  return [...points, { time, value }].slice(-limit)
}
