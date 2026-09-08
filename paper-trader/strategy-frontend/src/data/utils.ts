export function mulberry32(seed: number) {
  let a = seed >>> 0
  return () => {
    a |= 0
    a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

export function genEquity(
  seed: number,
  n: number,
  start: number,
  dailyDrift: number,
  dailyVol: number,
): number[] {
  const rnd = mulberry32(seed)
  const out: number[] = []
  let v = start
  for (let i = 0; i < n; i++) {
    const shock = (rnd() + rnd() + rnd() - 1.5) / 1.5
    v = v * (1 + dailyDrift + dailyVol * shock)
    if (i === Math.floor(n * 0.62)) v *= 1 - dailyVol * 4.2
    if (i === Math.floor(n * 0.31)) v *= 1 - dailyVol * 2.6
    out.push(Math.round(v))
  }
  return out
}

export function drawdownFrom(equity: number[]): number[] {
  let peak = equity[0] ?? 0
  return equity.map((v) => {
    peak = Math.max(peak, v)
    return peak === 0 ? 0 : ((v - peak) / peak) * 100
  })
}

export function monthlyFromEquity(equity: number[], buckets = 8): number[] {
  const size = Math.floor(equity.length / buckets)
  const out: number[] = []
  for (let b = 0; b < buckets; b++) {
    const a = equity[b * size]
    const z = equity[Math.min((b + 1) * size, equity.length - 1)]
    out.push(((z - a) / a) * 100)
  }
  return out
}

export function mcBands(
  seed: number,
  days: number,
  start: number,
  drift: number,
  vol: number,
): { p5: number[]; p50: number[]; p95: number[] } {
  const rnd = mulberry32(seed)
  const p5: number[] = []
  const p50: number[] = []
  const p95: number[] = []
  for (let d = 0; d <= days; d++) {
    const t = d / days
    const mid = start * Math.exp(drift * d)
    const spread = start * vol * Math.sqrt(d) * 1.645
    p5.push(Math.round(mid - spread - start * 0.02 * t))
    p50.push(Math.round(mid))
    p95.push(Math.round(mid + spread))
  }
  void rnd
  return { p5, p50, p95 }
}

export function sweepGrid(
  seed: number,
  xs: number[],
  ys: number[],
  ridgeX: number,
  ridgeY: number,
  base: number,
): number[][] {
  const rnd = mulberry32(seed)
  return ys.map((y) =>
    xs.map((x) => {
      const dx = (x - ridgeX) / (xs[xs.length - 1] - xs[0])
      const dy = (y - ridgeY) / (ys[ys.length - 1] - ys[0])
      const d = dx * dx + dy * dy * 0.55
      return +(base + 0.85 * Math.exp(-d * 9) - 0.35 * d - rnd() * 0.12).toFixed(2)
    }),
  )
}

const inr = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 })

export function fmtINR(n: number): string {
  const sign = n < 0 ? '−' : ''
  return `${sign}₹${inr.format(Math.abs(Math.round(n)))}`
}

export function fmtINRShort(n: number): string {
  const sign = n < 0 ? '−' : ''
  const a = Math.abs(n)
  if (a >= 1e7) return `${sign}₹${(a / 1e7).toFixed(2)}Cr`
  if (a >= 1e5) return `${sign}₹${(a / 1e5).toFixed(2)}L`
  if (a >= 1e3) return `${sign}₹${(a / 1e3).toFixed(1)}K`
  return `${sign}₹${inr.format(a)}`
}

export function fmtPct(n: number, digits = 1, signed = true): string {
  const s = signed && n > 0 ? '+' : n < 0 ? '−' : ''
  return `${s}${Math.abs(n).toFixed(digits)}%`
}

export function fmtNum(n: number, digits = 2): string {
  return n.toLocaleString('en-IN', { maximumFractionDigits: digits, minimumFractionDigits: digits })
}

export function clamp(v: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, v))
}
