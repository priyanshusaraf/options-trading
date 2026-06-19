import { useEffect, useState } from 'react'
import { getCandles, getOptionCandles } from '../lib/api'
import { PriceChart } from './Charts'
import type { InstrState, LiveTick } from '../lib/types'
import { inr, num, signalStyle, signedInr, pnlColor } from '../lib/format'
import { epochSeconds, mergeLiveCandle, type LiveCandle } from '../lib/liveSeries'

function Field({ label, v, cls = '' }: { label: string; v: string; cls?: string }) {
  return <div className="min-w-0"><div className="stat-label">{label}</div>
    <div className={`font-semibold truncate ${cls}`}>{v}</div></div>
}

export default function InstrumentTile({ st, onExpand, liveTick }:
  { st: InstrState; onExpand: (k: string) => void; liveTick?: LiveTick }) {
  const key = st.instrument
  const pos = st.position
  const [mode, setMode] = useState<'spot' | 'opt'>('spot')
  const [data, setData] = useState<{ candles: LiveCandle[]; ema: any[]; markers: any[] }>({ candles: [], ema: [], markers: [] })

  useEffect(() => {
    let alive = true
    const load = async () => {
      try {
        if (mode === 'opt' && pos) {
          const d = await getOptionCandles(key)
          if (alive) setData({ candles: (d.candles || []).map((p: any) => ({ time: p.time, close: p.value })), ema: [], markers: [] })
        } else {
          const d = await getCandles(key)
          if (alive) setData({ candles: d.candles || [], ema: d.ema || [], markers: d.markers || [] })
        }
      } catch { /* ignore */ }
    }
    load()
    const t = setInterval(load, 12000)  // tiles are static-ish; expand for live ticks
    return () => { alive = false; clearInterval(t) }
  }, [key, mode, !!pos])

  useEffect(() => {
    if (!liveTick) return
    const price = mode === 'opt' ? liveTick.option_premium : liveTick.spot
    if (price == null) return
    const time = epochSeconds(liveTick.time)
    setData((prev) => ({ ...prev, candles: mergeLiveCandle(prev.candles, time, price) }))
  }, [liveTick?.time, liveTick?.spot, liveTick?.option_premium, mode])

  return (
    <div className="tile">
      <div className="flex items-center justify-between">
        <button onClick={() => onExpand(key)} className="flex items-center gap-2 group">
          <span className="font-semibold text-zinc-100 group-hover:text-white">{st.name}</span>
          <span className="badge bg-zinc-700/40 text-muted">{st.segment}</span>
        </button>
        <span className={`badge ${signalStyle(st.signal)}`}>
          {st.signal === 'NONE' ? (st.trend?.toUpperCase() || '—') : st.signal.replace('_', ' ')}
        </span>
      </div>

      <div className="grid grid-cols-3 gap-2 text-[11px]">
        <Field label="Position" v={pos ? `${pos.direction} ${pos.option_type}` : 'FLAT'}
               cls={pos ? (pos.direction === 'LONG' ? 'text-up' : 'text-down') : 'text-muted'} />
        <Field label="Invested" v={pos ? inr(pos.entry_cost) : '—'} />
        <Field label="Unrealized" v={pos ? signedInr(pos.unrealized_pnl) : '—'} cls={pos ? pnlColor(pos.unrealized_pnl) : ''} />
      </div>
      {pos && (
        <div className="text-[11px] text-muted truncate" title={pos.tradingsymbol}>
          ▸ {pos.tradingsymbol} @ {num(pos.entry_premium)} · exp {pos.expiry} · now {num(pos.last_premium)}
        </div>
      )}

      <div className="relative">
        <PriceChart candles={data.candles} ema={data.ema} markers={data.markers} height={132} area />
        <div className="absolute top-1 right-1 flex gap-1">
          <button onClick={() => setMode('spot')} className={`badge ${mode === 'spot' ? 'bg-blue-500/25 text-blue-300' : 'bg-zinc-700/40 text-muted'}`}>SPOT</button>
          <button disabled={!pos} onClick={() => setMode('opt')}
                  className={`badge ${mode === 'opt' ? 'bg-blue-500/25 text-blue-300' : 'bg-zinc-700/40 text-muted'} ${!pos ? 'opacity-40 cursor-not-allowed' : ''}`}>OPT</button>
        </div>
      </div>

      <div className="flex justify-between text-[11px] text-muted tabular-nums">
        <span>z {num(st.z)}</span><span>slope {num(st.slope, 1)}</span><span>px {num(st.close)}</span>
      </div>
    </div>
  )
}
