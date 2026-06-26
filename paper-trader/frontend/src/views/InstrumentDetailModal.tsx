import { useEffect, useState } from 'react'
import { getInstrumentDetail } from '../lib/api'
import { inr, signedInr, pnlColor, num, dt } from '../lib/format'
import type { InstrumentDetailDTO } from '../lib/types'

export default function InstrumentDetailModal(
  { instrumentKey, segment, strategy, period, onClose }:
  { instrumentKey: string; segment?: string; strategy?: string; period?: string; onClose: () => void }) {
  const [d, setD] = useState<InstrumentDetailDTO | null>(null)
  useEffect(() => {
    getInstrumentDetail(instrumentKey, segment, strategy, period).then(setD).catch(() => setD(null))
  }, [instrumentKey, segment, strategy, period])

  const Stat = ({ label, v, cls = '' }: { label: string; v: string; cls?: string }) => (
    <div className="bg-panel2 rounded p-2">
      <div className="stat-label">{label}</div>
      <div className={`tabular-nums font-semibold ${cls}`}>{v}</div>
    </div>
  )

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="card w-full max-w-4xl p-4 flex flex-col gap-3 max-h-[92vh] overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between shrink-0">
          <span className="text-lg font-semibold text-zinc-100">{d?.name || instrumentKey}</span>
          <button onClick={onClose} className="btn">&#x2715; close</button>
        </div>
        {!d ? <div className="text-muted text-xs py-10 text-center">loading…</div> : (
          <>
            <div className="grid gap-2 shrink-0" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(110px,1fr))' }}>
              <Stat label="Trades" v={String(d.stats.trades)} />
              <Stat label="Win rate" v={`${d.stats.win_rate}%`} />
              <Stat label="Net P&L" v={signedInr(d.stats.net)} cls={pnlColor(d.stats.net)} />
              <Stat label="Gross" v={signedInr(d.stats.gross)} />
              <Stat label="Charges" v={inr(d.stats.charges)} cls="text-down" />
              <Stat label="Avg P&L / trade" v={signedInr(d.stats.avg_pnl)} cls={pnlColor(d.stats.avg_pnl)} />
              <Stat label="Avg win" v={signedInr(d.stats.avg_win)} cls="text-up" />
              <Stat label="Avg loss" v={signedInr(d.stats.avg_loss)} cls="text-down" />
              <Stat label="Best" v={signedInr(d.stats.best)} cls="text-up" />
              <Stat label="Worst" v={signedInr(d.stats.worst)} cls="text-down" />
              <Stat label="Avg hold (min)" v={num(d.stats.avg_holding_minutes, 0)} />
            </div>
            <div className="card p-2 overflow-auto">
              <table className="w-full text-xs">
                <thead className="text-muted text-left"><tr className="[&>th]:py-1 [&>th]:pr-3">
                  <th>Exit</th><th>Dir</th><th>Contract</th><th>Reason</th><th>Ret%</th><th>Net</th></tr></thead>
                <tbody>
                  {d.trades.length === 0 && <tr><td colSpan={6} className="py-4 text-center text-muted">no trades for this view</td></tr>}
                  {d.trades.map((t) => (
                    <tr key={t.id} className="border-t border-edge [&>td]:py-1 [&>td]:pr-3 tabular-nums">
                      <td>{dt(t.exit_time)}</td>
                      <td>{t.direction}</td>
                      <td className="text-muted">{t.tradingsymbol}</td>
                      <td className="text-muted">{t.exit_reason}</td>
                      <td className={pnlColor(t.return_pct)}>{num(t.return_pct, 1)}</td>
                      <td className={pnlColor(t.net_pnl)}>{signedInr(t.net_pnl)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
