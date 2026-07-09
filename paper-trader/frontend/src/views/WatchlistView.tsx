import { useEffect, useMemo, useState } from 'react'
import { useLive } from '../state/LiveContext'
import {
  getSignals, toggleInstrument, getCandles, getOptionCandles, setLiveInterval, blockEntries,
  addToPortfolio, removeFromPortfolio, getStatus,
  getStrategies, setProduct, setPriorityFlag, setOvertradeFlag, setInstrumentStrategy,
} from '../lib/api'
import { PriceChart, LineChart } from '../components/Charts'
import SessionBanner from '../components/SessionBanner'
import ModeChip from '../components/ModeChip'
import type { InstrState, SignalRow, ProviderHealth, StrategyMeta } from '../lib/types'
import { inr, num, signedInr, pnlColor, signalStyle } from '../lib/format'
import { epochSeconds, mergeLiveCandle, mergeLivePoint } from '../lib/liveSeries'

// Unified Watchlist — the merge of the old Home + Monitor screens. They showed the
// SAME state.states data and opened the SAME chart modal; the only real difference
// was Home = pinned subset + add/pin controls, Monitor = all instruments + ops
// toggles. So this is one screen: every instrument is a row you can pin inline, a
// "pinned only" toggle gives the old Home glance, and the add box brings in new
// names (e.g. a backtest winner). Default landing tab.

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

// "degraded Ns ago" — derived client-side from health.*.last_ok (DV-6) so the
// trader sees HOW LONG the feed has been down, and the pill reflects BOTH the
// candle and quote feeds (the row column only knows candle freshness).
function ago(lastOk: string | null | undefined): string {
  if (!lastOk) return ''
  const anchored = /([zZ]|[+-]\d{2}:?\d{2})$/.test(lastOk) ? lastOk : lastOk + '+05:30'
  const secs = Math.max(0, Math.round((Date.now() - Date.parse(anchored)) / 1000))
  if (Number.isNaN(secs)) return ''
  if (secs < 90) return `${secs}s ago`
  if (secs < 5400) return `${Math.round(secs / 60)}m ago`
  return `${Math.round(secs / 3600)}h ago`
}

function HealthPill({ health }: { health: ProviderHealth | null }) {
  if (!health) return null
  const q = health.quote, c = health.candle
  const authExpired = !!q?.auth_error || !!c?.auth_error
  const bad = (q?.consecutive_failures || 0) > 0 || (c?.consecutive_failures || 0) > 0
  // worst (oldest) last_ok across the two feeds, for the duration hint
  const oldestOk = [q?.last_ok, c?.last_ok].filter(Boolean).sort()[0] as string | undefined
  const dur = bad ? ago(oldestOk) : ''
  const label = authExpired ? 'session expired' : bad ? `degraded${dur ? ` ${dur}` : ''}` : 'healthy'
  return (
    <span className={`badge ${bad || authExpired ? 'bg-down/15 text-down' : 'bg-up/15 text-up'}`} title={
      `candle fails ${c?.consecutive_failures ?? 0} · quote fails ${q?.consecutive_failures ?? 0}` +
      (authExpired ? '\nKite session expired — re-authenticate' : '') +
      (c?.last_error ? `\n${c.last_error}` : '') +
      (q?.last_error ? `\n${q.last_error}` : '')}>
      data {label}
    </span>
  )
}

export default function Watchlist() {
  const { state, liveTicks, health } = useLive()
  const [rows, setRows] = useState<SignalRow[]>([])
  const [expanded, setExpanded] = useState<string | null>(null)
  const [active, setActive] = useState<Set<FilterKey>>(new Set())
  const [pinnedOnly, setPinnedOnly] = useState(false)
  const [adding, setAdding] = useState('')
  const [busy, setBusy] = useState(false)
  const [authed, setAuthed] = useState<boolean | null>(null)
  const [strategies, setStrategies] = useState<StrategyMeta[]>([])

  const load = () => getSignals().then((d) => setRows(d.instruments || [])).catch(() => {})
  useEffect(() => {
    load()
    const t = setInterval(load, 2500)   // lightweight: server never fetches candles for this
    return () => clearInterval(t)
  }, [])
  useEffect(() => { getStrategies().then((d) => setStrategies(d.strategies || [])).catch(() => {}) }, [])

  // Poll auth so the session-expired banner shows on the DEFAULT landing page even
  // pre-market, when no candle scan has failed yet to set health.auth_error (KITE-1).
  useEffect(() => {
    const f = () => getStatus().then((s) => setAuthed(!!s.authenticated)).catch(() => {})
    f(); const t = setInterval(f, 5000); return () => clearInterval(t)
  }, [])

  // Optimistic row toggle: flip locally now, let the 2.5s poll reconcile — no
  // racing getSignals() refetch that made the badge flicker (MON-2).
  const patchRow = (key: string, patch: Partial<SignalRow>) =>
    setRows((rs) => rs.map((r) => (r.key === key ? { ...r, ...patch } : r)))

  const toggleEnabled = (r: SignalRow) => {
    patchRow(r.key, { enabled: !r.enabled })
    toggleInstrument(r.key, !r.enabled).catch(() => patchRow(r.key, { enabled: r.enabled }))
  }
  const toggleBlock = (r: SignalRow) => {
    patchRow(r.key, { entries_blocked: !r.entries_blocked })
    blockEntries(r.key, !r.entries_blocked).catch(() => patchRow(r.key, { entries_blocked: r.entries_blocked }))
  }
  // dual-segment / multi-strategy per-instrument config (optimistic + reconcile)
  const togglePriority = (r: SignalRow) => {
    const next = !r.priority_flag
    patchRow(r.key, { priority_flag: next })
    setPriorityFlag(r.key, next).catch(() => patchRow(r.key, { priority_flag: r.priority_flag }))
  }
  const toggleOvertrade = (r: SignalRow) => {
    const next = !r.overtrade_flag
    patchRow(r.key, { overtrade_flag: next })
    setOvertradeFlag(r.key, next).catch(() => patchRow(r.key, { overtrade_flag: r.overtrade_flag }))
  }
  const changeProduct = (r: SignalRow, product: 'options' | 'equity_intraday') => {
    patchRow(r.key, { product })
    setProduct(r.key, product).catch(() => patchRow(r.key, { product: r.product }))
  }
  const changeStrategy = (r: SignalRow, strategy_key: string | null) => {
    patchRow(r.key, { strategy_key })
    setInstrumentStrategy(r.key, strategy_key).catch(() => patchRow(r.key, { strategy_key: r.strategy_key }))
  }
  // Pin = add to the curated portfolio (also enables trading, matching the old
  // Home behavior). Unpin = remove (also disables); a user-added name then drops
  // from the universe on the next poll. Reconcile from the server either way.
  const togglePin = (r: SignalRow) => {
    if (r.pinned) {
      patchRow(r.key, { pinned: false, enabled: false })
      removeFromPortfolio(r.key).then(load).catch(load)
    } else {
      patchRow(r.key, { pinned: true, enabled: true })
      addToPortfolio(r.key, true).then(load).catch(load)
    }
  }

  const add = async () => {
    const key = adding.trim().toUpperCase()
    if (!key) return
    setBusy(true)
    const res = await addToPortfolio(key, true).catch(() => ({ error: 'request failed' }))
    setBusy(false)
    if (res?.error) { alert(res.error); return }
    setAdding(''); load()
  }

  const toggleFilter = (f: FilterKey) =>
    setActive((s) => { const n = new Set(s); n.has(f) ? n.delete(f) : n.add(f); return n })

  const view = useMemo(() => rows.filter((r) => {
    if (pinnedOnly && !r.pinned) return false
    if (active.has('positions') && !r.has_position) return false
    if (active.has('signals') && r.signal === 'NONE') return false
    if (active.has('nosignal') && r.signal !== 'NONE') return false
    // "Stale / error" means a genuine feed problem — exclude benign market-closed
    // staleness so the filter doesn't match every row overnight (OPS-R2-1).
    if (active.has('stale') && (!r.stale || r.market_open === false)) return false
    if (active.has('options') && !r.has_options) return false
    if (active.has('enabled') && !r.enabled) return false
    return true
  }), [rows, active, pinnedOnly])

  const pinnedCount = useMemo(() => rows.filter((r) => r.pinned).length, [rows])
  const states = state?.states || {}

  return (
    <div className="flex flex-col gap-3">
      <SessionBanner authenticated={authed} />

      {/* add a name (e.g. a backtest winner) to the curated portfolio */}
      <div className="card p-3 flex items-center gap-2 flex-wrap">
        <span className="stat-label mr-1">Add instrument</span>
        <input value={adding} onChange={(e) => setAdding(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && add()}
          placeholder="symbol or key (e.g. RELIANCE, NIFTY)"
          className="bg-panel2 border border-edge rounded px-2 py-1 text-xs w-64" />
        <button onClick={add} disabled={busy || !adding.trim()}
          className="btn border-up/50 text-up">{busy ? 'adding…' : '+ add & pin'}</button>
        <span className="text-[11px] text-muted ml-1">pinned names are tracked &amp; tradable; ★ any row to pin it</span>
      </div>

      <div className="card p-3 flex items-center gap-2 flex-wrap">
        <button onClick={() => setPinnedOnly((v) => !v)}
          className={`badge ${pinnedOnly ? 'bg-amber-400/20 text-amber-300 border border-amber-400/40' : 'bg-zinc-700/40 text-muted hover:text-zinc-200'}`}
          title="Show only your pinned portfolio (the old Home glance).">
          {pinnedOnly ? '★ pinned only' : '☆ pinned only'} ({pinnedCount})
        </button>
        <span className="stat-label mx-1">Filters</span>
        {FILTERS.map(([f, label]) => (
          <button key={f} onClick={() => toggleFilter(f)}
            className={`badge ${active.has(f) ? 'bg-blue-500/25 text-blue-300' : 'bg-zinc-700/40 text-muted hover:text-zinc-200'}`}>
            {label}
          </button>
        ))}
        <span className="ml-auto flex items-center gap-2">
          {state?.any_market_open === false && (
            <span className="badge bg-zinc-700/40 text-muted"
              title="All enabled markets are closed — no new candles print, so rows read 'closed' (idle, not broken).">
              ● markets closed
            </span>
          )}
          <ModeChip mode={state?.broker_mode} />
          <HealthPill health={health} />
          <span className="text-[11px] text-muted">{view.length} of {rows.length}</span>
        </span>
      </div>

      <div className="card p-3 overflow-auto">
        <table className="w-full text-xs">
          <thead className="text-muted border-b border-edge text-left">
            <tr className="[&>th]:py-1 [&>th]:pr-3">
              <th></th><th>Instrument</th><th>Live TF</th><th>Signal</th><th className="text-right">z</th>
              <th>Trend</th><th>Position</th><th>Entries</th><th>Options</th><th>Data</th><th>Segment / Strategy</th><th></th>
            </tr>
          </thead>
          <tbody>
            {view.length === 0 && (
              <tr><td colSpan={12} className="py-8 text-center text-muted">
                {pinnedOnly ? 'no pinned instruments — ★ a row or add one above' : 'no instruments match the filters'}
              </td></tr>
            )}
            {view.map((r) => (
              <tr key={r.key} onClick={() => setExpanded(r.key)}
                className={`border-t border-edge tabular-nums cursor-pointer hover:bg-panel2/50 [&>td]:py-1 [&>td]:pr-3 ${r.enabled ? '' : 'opacity-50'}`}>
                <td onClick={(e) => e.stopPropagation()}>
                  <button onClick={() => togglePin(r)} title={r.pinned ? 'unpin from portfolio (also disables trading)' : 'pin to portfolio'}
                    className={r.pinned ? 'text-amber-300 hover:text-amber-200' : 'text-muted hover:text-zinc-300'}>
                    {r.pinned ? '★' : '☆'}
                  </button>
                </td>
                <td className="font-semibold text-zinc-100">{r.name}
                  <span className="badge bg-zinc-700/40 text-muted ml-1">{r.segment}</span></td>
                <td><IntervalSelect k={r.key} value={r.interval} /></td>
                <td><span className={`badge ${signalStyle(r.signal)}`}>{r.signal === 'NONE' ? '—' : r.signal.replace('_', ' ')}</span></td>
                <td className="text-right">{num(r.z)}</td>
                <td className="text-muted">{r.trend || '—'}</td>
                <td>{r.has_position ? <span className="text-up">● held</span> : <span className="text-muted">flat</span>}</td>
                <td onClick={(e) => e.stopPropagation()}>
                  <button onClick={() => toggleBlock(r)}
                    title={r.entries_blocked
                      ? 'entries BLOCKED — the bot will NOT open new positions on this symbol; click to allow'
                      : 'BLOCK the bot from opening new positions on this symbol (this is the real stop — not the red flag)'}
                    className={`badge ${r.entries_blocked ? 'bg-down/15 text-down' : 'bg-zinc-700/40 text-muted hover:text-zinc-200'}`}>
                    {r.entries_blocked ? 'blocked' : 'allow'}
                  </button>
                </td>
                <td className={r.has_options ? '' : 'text-amber-400/80'}>{r.has_options ? 'yes' : 'track'}</td>
                <td>{r.market_open === false
                  ? <span className="text-muted" title="market closed — no new candle prints; not a feed fault">closed</span>
                  : r.stale
                    ? <span className="text-amber-400">stale</span>
                    : <span className="text-up/80">live</span>}</td>
                <td onClick={(e) => e.stopPropagation()}>
                  <div className="flex items-center gap-1">
                    <button onClick={() => togglePriority(r)}
                      title={r.priority_flag ? 'purple priority ON — intraday selection always takes this name, sized at the top of the band' : 'flag as purple intraday priority'}
                      className={`text-sm leading-none ${r.priority_flag ? 'text-purple-300' : 'text-zinc-600 hover:text-purple-300'}`}>
                      {r.priority_flag ? '🟣' : '○'}
                    </button>
                    <button onClick={() => toggleOvertrade(r)}
                      title={r.overtrade_flag
                        ? 'red overtrading flag ON — advisory only (does NOT block); to actually stop entries use "blocked" on the left'
                        : (r.overtrade_suggested
                            ? `high signal count (today ${r.signals_today ?? 0} · 7d ${r.signals_rolling ?? 0}) — consider flagging red (advisory only)`
                            : 'flag as red (overtrading) — advisory only, does NOT block')}
                      className={`text-sm leading-none ${r.overtrade_flag ? 'text-red-400'
                        : r.overtrade_suggested ? 'text-red-400/70 hover:text-red-400 animate-pulse'
                        : 'text-zinc-600 hover:text-red-400'}`}>
                      {r.overtrade_flag ? '🔴' : '○'}
                    </button>
                    <span className={`badge text-[10px] ${r.overtrade_suggested ? 'bg-red-500/20 text-red-300' : 'bg-zinc-700/40 text-muted'}`}
                      title="entry signals: today · last 7 days">
                      {r.signals_today ?? 0}·{r.signals_rolling ?? 0}
                    </span>
                    <button onClick={() => changeProduct(r, r.product === 'equity_intraday' ? 'options' : 'equity_intraday')}
                      title="trading segment: options vs MIS intraday equity"
                      className={`badge ${r.product === 'equity_intraday' ? 'bg-purple-500/20 text-purple-200' : 'bg-zinc-700/40 text-muted hover:text-zinc-200'}`}>
                      {r.product === 'equity_intraday' ? 'INTRA' : 'OPT'}
                    </button>
                    <select value={r.strategy_key || ''} onClick={(e) => e.stopPropagation()}
                      onChange={(e) => changeStrategy(r, e.target.value || null)}
                      title="strategy this instrument trades (default = Trend Impulse V3)"
                      className="bg-panel2 border border-edge rounded px-1 py-0.5 text-[11px] max-w-[120px]">
                      <option value="">default</option>
                      {strategies.map((s) => <option key={s.key} value={s.key}>{s.display_name}</option>)}
                    </select>
                  </div>
                </td>
                <td onClick={(e) => e.stopPropagation()}>
                  <button onClick={() => toggleEnabled(r)}
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
    const TOKEN = import.meta.env.VITE_PT_TOKEN as string | undefined
    const ws = new WebSocket(
      `ws://${location.host}/ws/instrument/${k}${TOKEN ? `?token=${encodeURIComponent(TOKEN)}` : ''}`,
    )
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
