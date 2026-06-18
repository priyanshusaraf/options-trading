import { useLive } from '../state/LiveContext'
import LogStream from '../components/LogStream'
import { num, signalStyle, signedInr, pnlColor } from '../lib/format'
import { prio } from '../lib/constants'
import type { InstrState } from '../lib/types'

export default function EngineView() {
  const { state } = useLive()
  const rows: InstrState[] = Object.values(state?.states || {}).sort(
    (a, b) => prio(a.instrument) - prio(b.instrument))

  return (
    <div className="grid gap-3" style={{ gridTemplateColumns: 'minmax(0,1.7fr) minmax(0,1fr)' }}>
      <div className="card p-3 overflow-auto">
        <div className="stat-label mb-2">
          Strategy engine — EMA50 + displacement z-score per instrument (every tick)
        </div>
        <table className="w-full text-xs">
          <thead className="text-muted text-left">
            <tr className="[&>th]:py-1 [&>th]:pr-3 [&>th]:font-medium">
              <th>Instrument</th><th>Close</th><th>EMA50</th><th>z</th><th>z[-1]</th>
              <th>slope</th><th>trend</th><th>signal</th><th>exit</th><th>position</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && <tr><td colSpan={10} className="py-6 text-center text-muted">warming up…</td></tr>}
            {rows.map((s) => (
              <tr key={s.instrument} className="border-t border-edge [&>td]:py-1 [&>td]:pr-3 tabular-nums">
                <td className="font-semibold text-zinc-100">{s.name}</td>
                <td>{num(s.close)}</td>
                <td>{num(s.ema)}</td>
                <td className={s.z > 1 ? 'text-up' : s.z < -1 ? 'text-down' : ''}>{num(s.z)}</td>
                <td className="text-muted">{num(s.z_prev)}</td>
                <td>{num(s.slope, 1)}</td>
                <td className={s.trend === 'bull' ? 'text-up' : s.trend === 'bear' ? 'text-down' : 'text-muted'}>{s.trend}</td>
                <td><span className={`badge ${signalStyle(s.signal)}`}>{s.signal === 'NONE' ? '—' : s.signal.replace('_', ' ')}</span></td>
                <td className="text-muted">{[s.long_exit && 'L', s.short_exit && 'S'].filter(Boolean).join('/') || '—'}</td>
                <td>{s.position
                  ? <span className={s.position.direction === 'LONG' ? 'text-up' : 'text-down'}>
                      {s.position.direction} {s.position.option_type} <span className={pnlColor(s.position.unrealized_pnl)}>{signedInr(s.position.unrealized_pnl)}</span>
                    </span>
                  : <span className="text-muted">flat</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <LogStream />
    </div>
  )
}
