import { useEffect, useMemo, useState } from 'react'
import { getTrades } from '../lib/api'
import { num, signedInr, pnlColor } from '../lib/format'
import type { TradeDTO } from '../lib/types'

type Filter = 'all' | 'win' | 'loss'

const n = (v: number | null | undefined) => (v == null ? '—' : num(v))
const pct = (v: number | null | undefined) =>
  v == null ? '—' : `${v > 0 ? '+' : ''}${v.toFixed(2)}%`

export default function TradesView() {
  const [trades, setTrades] = useState<TradeDTO[]>([])
  const [filter, setFilter] = useState<Filter>('all')
  const [inst, setInst] = useState('all')

  useEffect(() => {
    const load = () => getTrades(1000).then((d) => setTrades(d.trades || [])).catch(() => {})
    load(); const t = setInterval(load, 5000); return () => clearInterval(t)
  }, [])

  const instruments = useMemo(
    () => Array.from(new Set(trades.map((t) => t.instrument_key))).sort(), [trades])

  const rows = useMemo(() => trades.filter((t) =>
    (filter === 'all' || (filter === 'win' ? t.win : !t.win)) &&
    (inst === 'all' || t.instrument_key === inst)), [trades, filter, inst])

  const count = rows.length
  const wins = rows.filter((t) => t.win).length
  const net = rows.reduce((a, t) => a + t.net_pnl, 0)

  return (
    <div className="flex flex-col gap-3">
      <div className="card p-3 flex items-center gap-3 flex-wrap">
        <div className="stat-label">Trade log — every trade the bot has executed</div>
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

      <div className="card p-0 overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="text-muted">
            <tr className="border-b border-edge">
              <th className="text-left p-2">Exit time</th>
              <th className="text-left p-2">Underlying</th>
              <th className="text-left p-2">Contract</th>
              <th className="text-right p-2">Underlying entry → exit</th>
              <th className="text-right p-2">Spot %</th>
              <th className="text-right p-2">Option entry → exit</th>
              <th className="text-right p-2">Option %</th>
              <th className="text-left p-2">Reason</th>
              <th className="text-right p-2">Net P&amp;L</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((t) => (
              <tr key={t.id} className="border-b border-edge/40 hover:bg-panel2/40">
                <td className="p-2 whitespace-nowrap text-muted">{new Date(t.exit_time).toLocaleString()}</td>
                <td className="p-2 whitespace-nowrap">{t.instrument_key}
                  <span className={`badge ml-1 ${t.direction === 'LONG' ? 'bg-up/15 text-up' : 'bg-down/15 text-down'}`}>
                    {t.direction} {t.option_type}</span>
                  {t.held_overnight && <span className="badge ml-1 bg-indigo-400/15 text-indigo-300">🌙</span>}
                </td>
                <td className="p-2 text-muted whitespace-nowrap">{t.tradingsymbol} ·{t.qty}</td>
                <td className="p-2 text-right tabular-nums whitespace-nowrap">{n(t.entry_spot)} → {n(t.exit_spot)}</td>
                <td className={`p-2 text-right tabular-nums ${pnlColor(t.spot_move_pct ?? 0)}`}>{pct(t.spot_move_pct)}</td>
                <td className="p-2 text-right tabular-nums whitespace-nowrap">{n(t.entry_premium)} → {n(t.exit_premium)}</td>
                <td className={`p-2 text-right tabular-nums ${pnlColor(t.premium_move_pct ?? 0)}`}>{pct(t.premium_move_pct)}</td>
                <td className="p-2 text-muted whitespace-nowrap">{t.exit_reason}</td>
                <td className={`p-2 text-right tabular-nums font-semibold ${pnlColor(t.net_pnl)}`}>{signedInr(t.net_pnl)}</td>
              </tr>
            ))}
            {!rows.length && (
              <tr><td colSpan={9} className="p-6 text-center text-muted">No trades match these filters yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
