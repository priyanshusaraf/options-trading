import type { InstrState, LiveTick } from '../lib/types'
import { inr, num, signalStyle, signedInr, pnlColor } from '../lib/format'

function Field({ label, v, cls = '' }: { label: string; v: string; cls?: string }) {
  return <div className="min-w-0"><div className="stat-label">{label}</div>
    <div className={`font-semibold truncate ${cls}`}>{v}</div></div>
}

// Chartless summary card — click the name to open the detail modal (which is the
// ONLY place charts load). Always-on mini charts were removed so list rows stay
// lightweight and never fetch candle data.
export default function InstrumentTile({ st, onExpand, liveTick }:
  { st: InstrState; onExpand: (k: string) => void; liveTick?: LiveTick }) {
  const key = st.instrument
  const pos = st.position
  const liveSpot = liveTick?.spot ?? st.close

  return (
    <div className="tile cursor-pointer" onClick={() => onExpand(key)}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 group">
          <span className="font-semibold text-zinc-100 group-hover:text-white">{st.name}</span>
          <span className="badge bg-zinc-700/40 text-muted">{st.segment}</span>
        </div>
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
          ▸ {pos.tradingsymbol} @ {num(pos.entry_premium)} · SL {num(pos.stop_price)} · now {num(liveTick?.option_premium ?? pos.last_premium)}
        </div>
      )}

      <div className="flex justify-between text-[11px] text-muted tabular-nums pt-1 border-t border-edge/50">
        <span>z {num(st.z)}</span><span>slope {num(st.slope, 1)}</span><span>px {num(liveSpot)}</span>
        <span className="text-blue-300/70">open ↗</span>
      </div>
    </div>
  )
}
