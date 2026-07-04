import { useEffect, useMemo, useState } from 'react'
import { getTrades } from '../lib/api'
import { num, signedInr, pnlColor } from '../lib/format'
import type { TradeDTO } from '../lib/types'

type Filter = 'all' | 'win' | 'loss'
type Mode = 'paper' | 'live'

const n = (v: number | null | undefined) => (v == null ? '—' : num(v))
const pct = (v: number | null | undefined) =>
  v == null ? '—' : `${v > 0 ? '+' : ''}${v.toFixed(2)}%`
// old rows predate the mode column → default them to paper (the only ledger that existed).
const modeOf = (t: TradeDTO): Mode => (t.mode === 'live' ? 'live' : 'paper')

export default function TradesView() {
  const [trades, setTrades] = useState<TradeDTO[]>([])
  const [mode, setMode] = useState<Mode>('paper')   // the two windows: paper ledger vs real ledger
  const [filter, setFilter] = useState<Filter>('all')
  const [inst, setInst] = useState('all')

  useEffect(() => {
    const load = () => getTrades(1000).then((d) => setTrades(d.trades || [])).catch(() => {})
    load(); const t = setInterval(load, 5000); return () => clearInterval(t)
  }, [])

  const paperCount = useMemo(() => trades.filter((t) => modeOf(t) === 'paper').length, [trades])
  const liveCount = useMemo(() => trades.filter((t) => modeOf(t) === 'live').length, [trades])

  // this window's ledger first, then the win/loss + instrument filters
  const ledger = useMemo(() => trades.filter((t) => modeOf(t) === mode), [trades, mode])
  const instruments = useMemo(
    () => Array.from(new Set(ledger.map((t) => t.instrument_key))).sort(), [ledger])
  const rows = useMemo(() => ledger.filter((t) =>
    (filter === 'all' || (filter === 'win' ? t.win : !t.win)) &&
    (inst === 'all' || t.instrument_key === inst)), [ledger, filter, inst])

  const count = rows.length
  const wins = rows.filter((t) => t.win).length
  const net = rows.reduce((a, t) => a + t.net_pnl, 0)
  const isLive = mode === 'live'

  return (
    <div className="flex flex-col gap-3">
      {/* the two windows — paper ledger vs real ledger, always kept apart */}
      <div className="flex items-center gap-2">
        {(['paper', 'live'] as Mode[]).map((m) => {
          const active = mode === m
          const live = m === 'live'
          return (
            <button key={m} onClick={() => { setMode(m); setInst('all') }}
              className={`px-3 py-1.5 rounded text-xs font-semibold border transition-colors ${active
                ? (live ? 'bg-down/20 text-down border-down/50' : 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40')
                : 'bg-panel2 text-muted border-edge hover:text-zinc-300'}`}>
              {live ? '🔴 Real trades' : '📝 Paper trades'}
              <span className="ml-1.5 opacity-70">({live ? liveCount : paperCount})</span>
            </button>
          )
        })}
        <span className="ml-auto text-[11px] text-muted">
          Two separate ledgers — every trade is permanently tagged by the broker that executed it.
        </span>
      </div>

      {isLive && (
        <div className="card p-2.5 border-down/40 bg-down/10 text-xs text-down">
          🔴 <b>Real-money ledger.</b> These are actual Kite fills. {liveCount === 0
            ? 'None yet — the bot has only ever paper-traded (live execution is gated off).'
            : 'Verify each against your Zerodha order book.'}
        </div>
      )}

      <div className="card p-3 flex items-center gap-3 flex-wrap">
        <div className="stat-label">
          {isLive ? 'Real trade log — actual orders filled on your account'
                  : 'Paper trade log — simulated fills, no real money'}
        </div>
        <div className="flex gap-1">
          {(['all', 'win', 'loss'] as Filter[]).map((f) => (
            <button key={f} onClick={() => setFilter(f)}
              className={`badge ${filter === f ? 'bg-panel2 text-zinc-100 border border-edge' : 'text-muted'}`}>
              {f === 'all' ? 'All' : f === 'win' ? 'Profitable' : 'Losses'}
            </button>
          ))}
        </div>
        <select value={inst} onChange={(e) => setInst(e.target.value)}
          className="bg-panel2 border border-edge rounded px-2 py-1 text-xs">
          <option value="all">All underlyings</option>
          {instruments.map((k) => <option key={k} value={k}>{k}</option>)}
        </select>
        <span className="ml-auto text-xs text-muted">
          {count} trades · win rate <b className="text-zinc-200">{count ? Math.round(100 * wins / count) : 0}%</b>
          {' '}· net <b className={pnlColor(net)}>{signedInr(net)}</b>
        </span>
      </div>

      <div className={`card p-0 overflow-x-auto ${isLive ? 'border-down/30' : ''}`}>
        <table className="w-full text-xs">
          <thead className="text-muted">
            <tr className="border-b border-edge">
              <th className="text-left p-2">Exit time</th>
              <th className="text-left p-2 hidden md:table-cell">Ledger</th>
              <th className="text-left p-2">Underlying</th>
              <th className="text-left p-2 hidden md:table-cell">Contract</th>
              <th className="text-right p-2 hidden md:table-cell">Underlying entry → exit</th>
              <th className="text-right p-2 hidden md:table-cell">Spot %</th>
              <th className="text-right p-2 hidden md:table-cell">Option entry → exit</th>
              <th className="text-right p-2 hidden md:table-cell">Option %</th>
              <th className="text-left p-2">Reason</th>
              <th className="text-right p-2">Net P&amp;L</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((t) => (
              <tr key={t.id} className="border-b border-edge/40 hover:bg-panel2/40">
                <td className="p-2 whitespace-nowrap text-muted">{new Date(t.exit_time).toLocaleString()}</td>
                <td className="p-2 hidden md:table-cell">
                  <span className={`badge ${modeOf(t) === 'live'
                    ? 'bg-down/20 text-down' : 'bg-emerald-500/15 text-emerald-300'}`}>
                    {modeOf(t) === 'live' ? 'REAL' : 'PAPER'}</span>
                </td>
                <td className="p-2 whitespace-nowrap">{t.instrument_key}
                  <span className={`badge ml-1 ${t.direction === 'LONG' ? 'bg-up/15 text-up' : 'bg-down/15 text-down'}`}>
                    {t.direction} {t.option_type}</span>
                  {t.held_overnight && <span className="badge ml-1 bg-indigo-400/15 text-indigo-300">🌙</span>}
                </td>
                <td className="p-2 text-muted whitespace-nowrap hidden md:table-cell">{t.tradingsymbol} ·{t.qty}</td>
                <td className="p-2 text-right tabular-nums whitespace-nowrap hidden md:table-cell">{n(t.entry_spot)} → {n(t.exit_spot)}</td>
                <td className={`p-2 text-right tabular-nums hidden md:table-cell ${pnlColor(t.spot_move_pct ?? 0)}`}>{pct(t.spot_move_pct)}</td>
                <td className="p-2 text-right tabular-nums whitespace-nowrap hidden md:table-cell">{n(t.entry_premium)} → {n(t.exit_premium)}</td>
                <td className={`p-2 text-right tabular-nums hidden md:table-cell ${pnlColor(t.premium_move_pct ?? 0)}`}>{pct(t.premium_move_pct)}</td>
                <td className="p-2 text-muted whitespace-nowrap">{t.exit_reason}</td>
                <td className={`p-2 text-right tabular-nums font-semibold ${pnlColor(t.net_pnl)}`}>{signedInr(t.net_pnl)}</td>
              </tr>
            ))}
            {!rows.length && (
              <tr><td colSpan={10} className="p-6 text-center text-muted">
                No {isLive ? 'real' : 'paper'} trades match these filters yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
