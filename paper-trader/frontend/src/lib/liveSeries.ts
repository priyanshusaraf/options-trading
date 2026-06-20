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

// Backend timestamps are IST. A naive ISO string (no offset/"Z") would be parsed
// by the browser as LOCAL time, which diverges from the backend's true-instant
// epochs for any non-IST viewer (and broke live-candle merge: live ticks looked
// 5:30 "earlier" than history, so new bars never formed). Pin naive strings to
// IST (+05:30) so live ticks and historical bars share one timeline.
export const epochSeconds = (iso: string) => {
  const hasTz = /([zZ]|[+-]\d{2}:?\d{2})$/.test(iso)
  return Math.floor(new Date(hasTz ? iso : iso + '+05:30').getTime() / 1000)
}

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
