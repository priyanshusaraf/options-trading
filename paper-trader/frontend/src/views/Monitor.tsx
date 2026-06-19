import { useEffect, useMemo, useState } from 'react'
import { useLive } from '../state/LiveContext'
import {
  getSignals, toggleInstrument, getCandles, getOptionCandles, setLiveInterval, blockEntries,
} from '../lib/api'
import { PriceChart, LineChart } from '../components/Charts'
import type { InstrState, SignalRow, ProviderHealth } from '../lib/types'
import { inr, num, signedInr, pnlColor, signalStyle } from '../lib/format'
import { epochSeconds, mergeLiveCandle, mergeLivePoint } from '../lib/liveSeries'

const LIVE_INTERVALS = ['5minute', '15minute', '30minute', '60minute']

// Per-instrument live-interval dropdown (reused in the list rows + detail header).
export function IntervalSelect({ k, value, onChange }:
  { k: string; value: string; onChange?: (iv: string) => void }) {
  const [v, setV] = useState(value)
  useEffect(() => setV(value), [value])
  return (
    <select value={v} onClick={(e) => e.stopPropagation()}
      onChange={(e) => { setV(e.target.value); setLiveInterval(k, e.target.value); onChange?.(e.target.value) }}
      className="bg-panel2 border border-edge rounded px-1 py-0.5 text-[11px] tabular-nums">
      {LIVE_INTERVALS.map((iv) => <option key={iv} value={iv}>{iv.replace('minute', 'm')}</option>)}
    </select>
  )
}

type FilterKey = 'positions' | 'signals' | 'nosignal' | 'stale' | 'options' | 'enabled'
const FILTERS: [FilterKey, string][] = [
  ['positions', 'Active positions'], ['signals', 'Signals now'], ['nosignal', 'No signal'],
  ['stale', 'Stale / error'], ['options', 'Options-tradable'], ['enabled', 'Enabled only'],
]

function HealthPill({ health }: { health: ProviderHealth | null }) {
  if (!health) return null
  const bad = (health.quote?.consecutive_failures || 0) > 0 || (health.candle?.consecutive_failures || 0) > 0
  return (
    <span className={`badge ${bad ? 'bg-down/15 text-down' : 'bg-up/15 text-up'}`} title={
      `quote fails ${health.quote?.consecutive_failures ?? 0} · candle fails ${health.candle?.consecutive_failures ?? 0}` +
      (health.quote?.last_error ? `\n${health.quote.last_error}` : '')}>
      data {bad ? 'degraded' : 'healthy'}
    </span>
  )
}

export default function Monitor() {
  const { state, liveTicks, health } = useLive()
  const [rows, setRows] = useState<SignalRow[]>([])
  const [expanded, setExpanded] = useState<string | null>(null)
  const [active, setActive] = useState<Set<FilterKey>>(new Set())

  useEffect(() => {
    const load = () => getSignals().then((d) => setRows(d.instruments || [])).catch(() => {})
    load()
    const t = setInterval(load, 2500)   // lightweight: server never fetches candles for this
    return () => clearInterval(t)
  }, [])

  const toggleFilter = (f: FilterKey) =>
    setActive((s) => { const n = new Set(s); n.has(f) ? n.delete(f) : n.add(f); return n })

  const view = useMemo(() => rows.filter((r) => {
    if (active.has('positions') && !r.has_position) return false
    if (active.has('signals') && r.signal === 'NONE') return false
    if (active.has('nosignal') && r.signal !== 'NONE') return false
    if (active.has('stale') && !r.stale) return false
    if (active.has('options') && !r.has_options) return false
    if (active.has('enabled') && !r.enabled) return false
    return true
  }), [rows, active])

  const states = state?.states || {}

  return (
    <div className="flex flex-col gap-3">
      <div className="card p-3 flex items-center gap-2 flex-wrap">
        <span className="stat-label mr-1">Filters</span>
        {FILTERS.map(([f, label]) => (
          <button key={f} onClick={() => toggleFilter(f)}
            className={`badge ${active.has(f) ? 'bg-blue-500/25 text-blue-300' : 'bg-zinc-700/40 text-muted hover:text-zinc-200'}`}>
            {label}
          </button>
        ))}
        <span className="ml-auto flex items-center gap-2">
          <HealthPill health={health} />
          <span className="text-[11px] text-muted">{view.length} of {rows.length}</span>
        </span>
      </div>

      <div className="card p-3 overflow-auto">
        <table className="w-full text-xs">
          <thead className="text-muted border-b border-edge text-left">
            <tr className="[&>th]:py-1 [&>th]:pr-3">
              <th>Instrument</th><th>Live TF</th><th>Signal</th><th className="text-right">z</th>
              <th>Trend</th><th>Position</th><th>Options</th><th>Data</th><th>Entries</th><th></th>
            </tr>
          </thead>
          <tbody>
            {view.length === 0 && (
              <tr><td colSpan={10} className="py-8 text-center text-muted">no instruments match the filters</td></tr>
            )}
            {view.map((r) => (
              <tr key={r.key} onClick={() => setExpanded(r.key)}
                className={`border-t border-edge tabular-nums cursor-pointer hover:bg-panel2/50 [&>td]:py-1 [&>td]:pr-3 ${r.enabled ? '' : 'opacity-50'}`}>
                <td className="font-semibold text-zinc-100">{r.name}
                  <span className="badge bg-zinc-700/40 text-muted ml-1">{r.segment}</span></td>
                <td><IntervalSelect k={r.key} value={r.interval} /></td>
                <td><span className={`badge ${signalStyle(r.signal)}`}>{r.signal === 'NONE' ? '—' : r.signal.replace('_', ' ')}</span></td>
                <td className="text-right">{num(r.z)}</td>
                <td className="text-muted">{r.trend || '—'}</td>
                <td>{r.has_position ? <span className="text-up">● held</span> : <span className="text-muted">flat</span>}</td>
                <td className={r.has_options ? '' : 'text-amber-400/80'}>{r.has_options ? 'yes' : 'track'}</td>
                <td>{r.stale ? <span className="text-amber-400">stale</span> : <span className="text-up/80">live</span>}</td>
                <td onClick={(e) => e.stopPropagation()}>
                  <button onClick={() => blockEntries(r.key, !r.entries_blocked).then(() => getSignals().then((d) => setRows(d.instruments || [])))}
                    className={`badge ${r.entries_blocked ? 'bg-down/15 text-down' : 'bg-zinc-700/40 text-muted hover:text-zinc-200'}`}>
                    {r.entries_blocked ? 'blocked' : 'allow'}
                  </button>
                </td>
                <td onClick={(e) => e.stopPropagation()}>
                  <button onClick={() => toggleInstrument(r.key, !r.enabled).then(() => getSignals().then((d) => setRows(d.instruments || [])))}
                    className={`badge ${r.enabled ? 'bg-up/15 text-up' : 'bg-zinc-700/40 text-muted'}`}>
                    {r.enabled ? 'on' : 'off'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {expanded && <Expanded k={expanded} st={states[expanded]} onClose={() => setExpanded(null)}
        liveTick={liveTicks[expanded]} />}
    </div>
  )
}

export function Expanded({ k, st, onClose }: { k: string; st?: InstrState; onClose: () => void; liveTick?: any }) {
  const [mode, setMode] = useState<'spot' | 'opt'>('spot')
  const [under, setUnder] = useState<any>({ candles: [], ema: [], markers: [] })
  const [opt, setOpt] = useState<any>(null)
  const [tick, setTick] = useState<any>(null)
  const pos = st?.position

  // charts load ONLY here, on open — never in the list rows
  useEffect(() => {
    getCandles(k).then(setUnder)
    if (pos) getOptionCandles(k).then(setOpt)
  }, [k, !!pos])

  useEffect(() => {
    const ws = new WebSocket(`ws://${location.host}/ws/instrument/${k}`)
    ws.onmessage = (e) => setTick(JSON.parse(e.data))
    return () => ws.close()
  }, [k])

  useEffect(() => {
    if (!tick?.time) return
    const time = epochSeconds(tick.time)
    if (tick.spot != null) setUnder((prev: any) => ({ ...prev, candles: mergeLiveCandle(prev.candles || [], time, tick.spot) }))
    if (tick.option_premium != null) setOpt((prev: any) => ({ ...(prev || {}), candles: mergeLivePoint(prev?.candles || [], time, tick.option_premium) }))
  }, [tick?.time, tick?.spot, tick?.option_premium])

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
            {st?.interval && <span className="badge bg-blue-500/20 text-blue-300">{st.interval.replace('minute', 'm')}</span>}
            <span className="flex items-center gap-1 text-xs text-up"><span className="w-2 h-2 rounded-full bg-up animate-pulse" />LIVE WS</span>
          </div>
          <button onClick={onClose} className="btn">✕ close</button>
        </div>

        <div className="flex items-center gap-6 text-sm flex-wrap">
          <div><span className="stat-label">Spot </span><span className="font-semibold tabular-nums">{tick ? num(tick.spot) : '—'}</span></div>
          {pos && <div><span className="stat-label">Option </span><span className="font-semibold tabular-nums">{tick?.option_premium != null ? num(tick.option_premium) : '—'}</span></div>}
          {pos && <div><span className="stat-label">Position </span><span className={pos.direction === 'LONG' ? 'text-up' : 'text-down'}>{pos.direction} {pos.option_type}</span></div>}
          {pos && <div><span className="stat-label">Unrealized </span><span className={pnlColor(pos.unrealized_pnl)}>{signedInr(pos.unrealized_pnl)}</span></div>}
          {pos && <div className="text-muted">{pos.tradingsymbol} · inv {inr(pos.entry_cost)} · SL {num(pos.stop_price)}</div>}
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
