import { useEffect, useMemo, useState } from 'react'
import { useLive } from '../state/LiveContext'
import { getPositions, getSignals, getAnalytics, closePosition, blockEntries, manualOpen, setPositionSLTP } from '../lib/api'
import { inr, num, signedInr, pnlColor } from '../lib/format'
import type { PositionRow, SignalRow, AnalyticsSplit } from '../lib/types'

function AnalyticsStrip() {
  const [a, setA] = useState<AnalyticsSplit | null>(null)
  useEffect(() => { const f = () => getAnalytics().then(setA).catch(() => {}); f(); const t = setInterval(f, 5000); return () => clearInterval(t) }, [])
  if (!a) return null
  const cell = (label: string, v: string, cls = '') =>
    <div><div className="stat-label">{label}</div><div className={`text-sm font-semibold tabular-nums ${cls}`}>{v}</div></div>
  return (
    <div className="card p-3 grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(120px,1fr))' }}>
      <div className="stat-label col-span-full">Where the P&amp;L comes from — intraday vs overnight</div>
      {cell('Intraday net', signedInr(a.intraday.net_pnl), pnlColor(a.intraday.net_pnl))}
      {cell('Intraday trades', `${a.intraday.trades} · ${a.intraday.win_rate}%`)}
      {cell('Overnight net', signedInr(a.overnight.net_pnl), pnlColor(a.overnight.net_pnl))}
      {cell('Overnight trades', `${a.overnight.trades} · ${a.overnight.win_rate}%`)}
      {cell('Overnight gap P&L', signedInr(a.overnight_gap_pnl), pnlColor(a.overnight_gap_pnl))}
      {cell('Reinforced trades', String(a.reinforced_trades))}
      {cell('Option dataset', `${a.option_dataset.rows.toLocaleString()} rows`)}
    </div>
  )
}

function holdingTime(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime()
  const m = Math.max(0, Math.floor(ms / 60000))
  return m < 60 ? `${m}m` : `${Math.floor(m / 60)}h ${m % 60}m`
}

function Cell({ label, v, cls = '' }: { label: string; v: string; cls?: string }) {
  return <div><div className="stat-label">{label}</div>
    <div className={`text-sm font-semibold tabular-nums ${cls}`}>{v}</div></div>
}

function SLTPEditor({ p, onChanged }: { p: PositionRow; onChanged: () => void }) {
  const [stop, setStop] = useState(String(p.stop_price))
  const [target, setTarget] = useState(String(p.target_price))
  const [msg, setMsg] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  // re-sync when the engine ratchets the stop, unless the field is mid-edit
  useEffect(() => { setStop(String(p.stop_price)) }, [p.stop_price])
  useEffect(() => { setTarget(String(p.target_price)) }, [p.target_price])
  const save = async () => {
    setBusy(true); setMsg(null)
    const res = await setPositionSLTP(p.instrument_key, {
      stop_price: parseFloat(stop), target_price: parseFloat(target),
    })
    setBusy(false)
    if (res?.error) setMsg(res.error)
    else onChanged()
  }
  return (
    <div className="flex items-center gap-2 pt-1 border-t border-edge/50 flex-wrap">
      <span className="stat-label">Set SL / TP</span>
      <input type="number" step="any" value={stop} onChange={(e) => setStop(e.target.value)}
        title="stop-loss premium"
        className="w-24 bg-panel2 border border-down/40 rounded px-2 py-1 text-xs tabular-nums" />
      <input type="number" step="any" value={target} onChange={(e) => setTarget(e.target.value)}
        title="take-profit premium"
        className="w-24 bg-panel2 border border-up/40 rounded px-2 py-1 text-xs tabular-nums" />
      <button disabled={busy} onClick={save} className="btn">{busy ? '…' : 'Set'}</button>
      {p.manual_target && <span className="badge bg-blue-500/15 text-blue-300" title="target pinned by you — reinforcement won't move it">TP pinned</span>}
      {msg && <span className="text-xs text-down">✕ {msg}</span>}
    </div>
  )
}

function PositionCard({ p, onChanged }: { p: PositionRow; onChanged: () => void }) {
  const [busy, setBusy] = useState(false)
  const prem = p.live_premium ?? p.last_premium
  const act = async (fn: () => Promise<any>) => { setBusy(true); await fn(); setBusy(false); onChanged() }
  return (
    <div className="card p-3 flex flex-col gap-2">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-zinc-100">{p.instrument_key}</span>
          <span className={`badge ${p.direction === 'LONG' ? 'bg-up/15 text-up' : 'bg-down/15 text-down'}`}>{p.direction} {p.option_type}</span>
          <span className="text-[11px] text-muted">{p.tradingsymbol} · {p.qty}u</span>
          {!!p.reinforcement_count && <span className="badge bg-blue-500/15 text-blue-300" title="reinforcements">⊕ ×{p.reinforcement_count}</span>}
          {p.held_overnight && <span className="badge bg-indigo-400/15 text-indigo-300" title="held overnight">🌙 overnight</span>}
          {p.stale && <span className="badge bg-amber-400/15 text-amber-400">stale{p.stale_age != null ? ` ${p.stale_age}s` : ''}</span>}
        </div>
        <span className={`text-sm font-semibold ${pnlColor(p.unrealized_pnl)}`}>{signedInr(p.unrealized_pnl)}</span>
      </div>

      <div className="grid gap-2" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(92px,1fr))' }}>
        <Cell label="Entry" v={num(p.entry_premium)} />
        <Cell label="Option LTP" v={num(prem)} />
        <Cell label="Spot" v={num(p.live_spot ?? p.last_spot)} />
        <Cell label="High water" v={num(p.high_water_premium)} cls="text-up/80" />
        <Cell label="Stop (trail)" v={num(p.stop_price)} cls="text-down" />
        <Cell label="Target" v={num(p.target_price)} cls="text-up" />
        <Cell label="→ stop" v={num(p.dist_to_stop)} />
        <Cell label="→ target" v={num(p.dist_to_target)} />
        <Cell label="Entry cost" v={inr(p.entry_cost)} />
        <Cell label="Held" v={holdingTime(p.entry_time)} />
      </div>

      <SLTPEditor p={p} onChanged={onChanged} />

      <div className="flex items-center gap-2 pt-1 border-t border-edge/50">
        <button disabled={busy} onClick={() => act(() => closePosition(p.instrument_key))}
          className="btn border-down/50 text-down">{busy ? '…' : '✕ Close now'}</button>
        <button disabled={busy} onClick={() => act(() => blockEntries(p.instrument_key, true))}
          className="btn">⊘ Disable new entries</button>
        <span className="ml-auto text-[11px] text-muted">last update {p.last_mark_time ? new Date(p.last_mark_time).toLocaleTimeString() : '—'}</span>
      </div>
    </div>
  )
}

function ManualEntry({ tradable, onDone }: { tradable: SignalRow[]; onDone: () => void }) {
  const [key, setKey] = useState('')
  const [dir, setDir] = useState<'LONG' | 'SHORT'>('LONG')
  const [msg, setMsg] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const submit = async () => {
    if (!key) return
    setBusy(true); setMsg(null)
    const res = await manualOpen(key, dir)
    setBusy(false)
    if (res.error) setMsg(`✕ ${res.error}`)
    else { setMsg(`✓ opened ${res.tradingsymbol}`); onDone() }
  }
  return (
    <div className="card p-3 flex items-end gap-3 flex-wrap">
      <div className="flex flex-col gap-1">
        <span className="stat-label">Manual paper entry (1 lot, capital-checked)</span>
        <div className="flex items-center gap-2">
          <select value={key} onChange={(e) => setKey(e.target.value)}
            className="bg-panel2 border border-edge rounded px-2 py-1 text-xs">
            <option value="">select instrument…</option>
            {tradable.map((t) => <option key={t.key} value={t.key}>{t.name}{t.has_position ? ' (held)' : ''}</option>)}
          </select>
          <button onClick={() => setDir('LONG')} className={`badge ${dir === 'LONG' ? 'bg-up/20 text-up' : 'bg-zinc-700/40 text-muted'}`}>LONG</button>
          <button onClick={() => setDir('SHORT')} className={`badge ${dir === 'SHORT' ? 'bg-down/20 text-down' : 'bg-zinc-700/40 text-muted'}`}>SHORT</button>
          <button disabled={busy || !key} onClick={submit} className="btn border-up/50 text-up">{busy ? 'opening…' : '+ open paper position'}</button>
        </div>
      </div>
      {msg && <span className={`text-xs ${msg.startsWith('✓') ? 'text-up' : 'text-down'}`}>{msg}</span>}
      <span className="ml-auto text-[11px] text-amber-400/70">paper only — never places a real Kite order</span>
    </div>
  )
}

export default function ActivePositionsView() {
  const { positionTicks } = useLive()
  const [rows, setRows] = useState<PositionRow[]>([])
  const [tradable, setTradable] = useState<SignalRow[]>([])

  const load = () => {
    getPositions().then((d) => setRows(d.positions || [])).catch(() => {})
    getSignals().then((d) => setTradable((d.instruments || []).filter((i: SignalRow) => i.has_options))).catch(() => {})
  }
  useEffect(() => { load(); const t = setInterval(load, 2000); return () => clearInterval(t) }, [])

  // overlay the fast-lane position ticks (sub-2s) on top of the polled rows
  const merged = useMemo(() => rows.map((p) => {
    const t = positionTicks[p.instrument_key]
    return t ? { ...p, live_premium: t.option_premium, live_spot: t.spot,
      unrealized_pnl: t.unrealized_pnl, stop_price: t.stop_price, target_price: t.target_price,
      high_water_premium: t.high_water_premium, stale: t.stale, stale_age: t.stale_age } : p
  }), [rows, positionTicks])

  return (
    <div className="flex flex-col gap-3">
      <AnalyticsStrip />
      <ManualEntry tradable={tradable} onDone={load} />
      {merged.length === 0 ? (
        <div className="card p-8 text-center text-muted">No open positions. The engine opens one on the next fresh signal, or open one manually above.</div>
      ) : (
        <div className="grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(420px, 1fr))' }}>
          {merged.map((p) => <PositionCard key={p.instrument_key} p={p} onChanged={load} />)}
        </div>
      )}
    </div>
  )
}
