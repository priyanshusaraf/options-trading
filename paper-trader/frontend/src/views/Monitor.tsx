import { useEffect, useState } from 'react'
import { useLive } from '../state/LiveContext'
import { getInstruments, toggleInstrument, getCandles, getOptionCandles } from '../lib/api'
import { PriceChart, LineChart } from '../components/Charts'
import InstrumentTile from '../components/InstrumentTile'
import type { InstrumentMeta, InstrState } from '../lib/types'
import { inr, num, signedInr, pnlColor } from '../lib/format'

export default function Monitor() {
  const { state } = useLive()
  const [meta, setMeta] = useState<InstrumentMeta[]>([])
  const [expanded, setExpanded] = useState<string | null>(null)

  useEffect(() => {
    const load = () => getInstruments().then((d) => setMeta(d.instruments || []))
    load()
    const t = setInterval(load, 5000)
    return () => clearInterval(t)
  }, [])

  const toggle = async (key: string, enabled: boolean) => {
    setMeta((m) => m.map((i) => (i.key === key ? { ...i, enabled } : i)))
    await toggleInstrument(key, enabled)
  }

  const enabled = meta.filter((m) => m.enabled)
  const states = state?.states || {}

  return (
    <div className="flex flex-col gap-3">
      {/* instrument selector */}
      <div className="card p-3">
        <div className="stat-label mb-2">Instruments — click to enable / disable trading</div>
        <div className="flex flex-wrap gap-2">
          {meta.map((m) => (
            <button key={m.key} onClick={() => toggle(m.key, !m.enabled)}
              className={`px-2.5 py-1 rounded text-xs border transition-colors ${m.enabled
                ? 'border-up/50 bg-up/10 text-up' : 'border-edge bg-panel2 text-muted hover:text-zinc-300'}`}>
              <span className="opacity-60 mr-1">#{m.priority}</span>{m.name}
            </button>
          ))}
        </div>
      </div>

      {/* grid */}
      {enabled.length === 0 ? (
        <div className="card p-8 text-center text-muted">No instruments enabled — pick some above.</div>
      ) : (
        <div className="grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(330px, 1fr))' }}>
          {enabled.map((m) => {
            const st: InstrState = states[m.key] || {
              instrument: m.key, name: m.name, segment: m.segment, time: 0, close: m.close || 0,
              ema: 0, z: m.z || 0, z_prev: null, slope: 0, std: 0, trend: m.trend || 'flat',
              signal: m.signal || 'NONE', long_exit: false, short_exit: false, position: m.position,
            }
            return <InstrumentTile key={m.key} st={st} onExpand={setExpanded} />
          })}
        </div>
      )}

      {expanded && <Expanded k={expanded} st={states[expanded]} onClose={() => setExpanded(null)} />}
    </div>
  )
}

function Expanded({ k, st, onClose }: { k: string; st?: InstrState; onClose: () => void }) {
  const [mode, setMode] = useState<'spot' | 'opt'>('spot')
  const [under, setUnder] = useState<any>({ candles: [], ema: [], markers: [] })
  const [opt, setOpt] = useState<any>(null)
  const [tick, setTick] = useState<any>(null)
  const pos = st?.position

  useEffect(() => {
    getCandles(k).then(setUnder)
    if (pos) getOptionCandles(k).then(setOpt)
  }, [k, !!pos])

  // live per-instrument WebSocket — opened ONLY while expanded
  useEffect(() => {
    const ws = new WebSocket(`ws://${location.host}/ws/instrument/${k}`)
    ws.onmessage = (e) => setTick(JSON.parse(e.data))
    return () => ws.close()
  }, [k])

  const priceLines = pos ? [
    { price: pos.entry_premium, color: '#8b93a7', title: 'entry' },
    { price: pos.stop_price, color: '#f6465d', title: 'SL' },
    { price: pos.target_price, color: '#2ebd85', title: 'TP' },
  ] : []

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="card w-full max-w-5xl p-4 flex flex-col gap-3" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-lg font-semibold text-zinc-100">{st?.name || k}</span>
            <span className="badge bg-zinc-700/40 text-muted">{st?.segment}</span>
            <span className="flex items-center gap-1 text-xs text-up"><span className="w-2 h-2 rounded-full bg-up animate-pulse" />LIVE WS</span>
          </div>
          <button onClick={onClose} className="btn">✕ close</button>
        </div>

        <div className="flex items-center gap-6 text-sm">
          <div><span className="stat-label">Spot </span><span className="font-semibold tabular-nums">{tick ? num(tick.spot) : '—'}</span></div>
          {pos && <div><span className="stat-label">Option </span><span className="font-semibold tabular-nums">{tick?.option_premium != null ? num(tick.option_premium) : '—'}</span></div>}
          {pos && <div><span className="stat-label">Position </span>
            <span className={pos.direction === 'LONG' ? 'text-up' : 'text-down'}>{pos.direction} {pos.option_type}</span></div>}
          {pos && <div><span className="stat-label">Unrealized </span><span className={pnlColor(pos.unrealized_pnl)}>{signedInr(pos.unrealized_pnl)}</span></div>}
          {pos && <div className="text-muted">{pos.tradingsymbol} · inv {inr(pos.entry_cost)}</div>}
          <div className="ml-auto flex gap-1">
            <button onClick={() => setMode('spot')} className={`badge ${mode === 'spot' ? 'bg-blue-500/25 text-blue-300' : 'bg-zinc-700/40 text-muted'}`}>UNDERLYING</button>
            <button disabled={!pos} onClick={() => setMode('opt')} className={`badge ${mode === 'opt' ? 'bg-blue-500/25 text-blue-300' : 'bg-zinc-700/40 text-muted'} ${!pos ? 'opacity-40' : ''}`}>OPTION</button>
          </div>
        </div>

        {mode === 'spot'
          ? <PriceChart candles={under.candles} ema={under.ema} markers={under.markers} height={360} />
          : <LineChart data={(opt?.candles) || []} height={360} color="#e0b341" priceLines={priceLines} />}
      </div>
    </div>
  )
}
